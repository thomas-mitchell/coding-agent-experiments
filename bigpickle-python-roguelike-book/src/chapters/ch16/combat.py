"""Combat system for the roguelike."""
from __future__ import annotations
from typing import TYPE_CHECKING

import tcod.constants
import tcod.map
from tcod.ecs import Entity

from actions import BumpAction, WaitAction, PickupAction, UseItemAction
from components import (
    AI,
    Fighter,
    Inventory,
    Item,
    Name,
    Position,
    Renderable,
    XP,
    get_defense,
    get_power,
)
from items import use_first_consumable
from message_log import MessageLog

if TYPE_CHECKING:
    from game_map import GameMap

FOV_RADIUS = 8


def compute_fov(game_map: GameMap, x: int, y: int) -> None:
    """Compute the field of view from (x, y) and mark explored tiles."""
    game_map.visible[:] = tcod.map.compute_fov(
        transparency=game_map.tiles["transparent"],
        pov=(y, x),
        radius=FOV_RADIUS,
        algorithm=tcod.constants.FOV_SYMMETRIC_SHADOWCAST,
    )
    game_map.explored |= game_map.visible


def attack(attacker: tcod.ecs.Entity, target: tcod.ecs.Entity) -> str:
    """Resolve an attack using equipment-modified stats and return a message."""
    attacker_name = attacker.components[Name].name
    target_name = target.components[Name].name

    power = get_power(attacker)
    defense = get_defense(target)
    damage = max(0, power - defense)

    if damage > 0:
        target.components[Fighter].hp -= damage
        return f"{attacker_name} attacks {target_name} for {damage} damage."
    return f"{attacker_name} attacks {target_name} but does no damage."


def process_player_action(
    action: BumpAction | WaitAction | PickupAction | UseItemAction,
    registry: tcod.ecs.Registry,
    game_map: GameMap,
    log: MessageLog,
) -> bool:
    """Handle a player-generated action. Returns True if a turn was spent."""
    if isinstance(action, WaitAction):
        return True

    if isinstance(action, BumpAction):
        return _player_bump(action, registry, game_map, log)

    if isinstance(action, PickupAction):
        return _player_pickup(action, registry, game_map, log)

    if isinstance(action, UseItemAction):
        return _player_use_item(action, registry, game_map, log)

    return False


def _player_bump(
    action: BumpAction,
    registry: tcod.ecs.Registry,
    game_map: GameMap,
    log: MessageLog,
) -> bool:
    pos = action.entity.components[Position]
    target_x = pos.x + action.dx
    target_y = pos.y + action.dy

    if not game_map.is_walkable(target_x, target_y):
        return False

    for other, other_pos, fighter in registry.Q[Entity, Position, Fighter]:
        if (
            other_pos.x == target_x
            and other_pos.y == target_y
            and other is not action.entity
        ):
            log.add(attack(attacker=action.entity, target=other))
            return True

    pos.x = target_x
    pos.y = target_y
    return True


def _player_pickup(
    action: PickupAction,
    registry: tcod.ecs.Registry,
    game_map: GameMap,
    log: MessageLog,
) -> bool:
    player = action.entity
    if Inventory not in player.components:
        return False
    inv = player.components[Inventory]
    ppos = player.components[Position]

    for item_entity, ipos, item in registry.Q[Entity, Position, Item]:
        if ipos.x == ppos.x and ipos.y == ppos.y:
            if len(inv.items) >= inv.capacity:
                log.add("Your inventory is full.", (255, 255, 0))
                return False
            inv.items.append(item_entity)
            # Remove the item from the map while keeping its identity
            # (so Equipment/Equippable/Consumable data survive the pickup).
            item_entity.components.pop(Position, None)
            item_entity.components.pop(Renderable, None)
            log.add(f"You pick up the {item.name}.")
            return True
    log.add("There is nothing here to pick up.", (255, 255, 0))
    return False


def _player_use_item(
    action: UseItemAction,
    registry: tcod.ecs.Registry,
    game_map: GameMap,
    log: MessageLog,
) -> bool:
    return use_first_consumable(action.entity, registry, game_map, log)


def resolve_enemy_attacks(
    registry: tcod.ecs.Registry,
    game_map: GameMap,
    player: tcod.ecs.Entity,
    log: MessageLog,
) -> None:
    """Let every enemy adjacent to (or overlapping) the player attack it."""
    ppos = player.components[Position]

    for entity, pos, fighter, ai in registry.Q[Entity, Position, Fighter, AI]:
        if entity is player:
            continue
        if fighter.hp <= 0:
            continue

        dx = pos.x - ppos.x
        dy = pos.y - ppos.y
        distance = max(abs(dx), abs(dy))

        if distance == 0:
            log.add(attack(attacker=entity, target=player))
            _push_back(entity, pos, game_map, registry, player)
        elif distance == 1:
            log.add(attack(attacker=entity, target=player))


def _push_back(
    entity: tcod.ecs.Entity,
    pos: Position,
    game_map: GameMap,
    registry: tcod.ecs.Registry,
    player: tcod.ecs.Entity,
) -> None:
    """Move an overlapping enemy to a free adjacent tile if possible."""
    ppos = player.components[Position]
    for dx, dy in [(0, 1), (0, -1), (1, 0), (-1, 0)]:
        tx, ty = ppos.x + dx, ppos.y + dy
        if not game_map.is_walkable(tx, ty):
            continue
        occupied = any(
            other is not player
            and other is not entity
            and other.components[Position].x == tx
            and other.components[Position].y == ty
            for other in registry.Q.all_of(components=[Position])
        )
        if not occupied:
            pos.x, pos.y = tx, ty
            return


def remove_dead_entities(
    registry: tcod.ecs.Registry,
    log: MessageLog,
    player: tcod.ecs.Entity,
) -> None:
    """Remove defeated entities and award XP for slain enemies."""
    xp = player.components.get(XP)

    for entity in registry.Q.all_of(components=[Fighter]):
        fighter = entity.components[Fighter]
        if fighter.hp > 0:
            continue
        name = entity.components[Name].name if Name in entity.components else "Unknown"
        log.add(f"{name} has been defeated!")

        if xp is not None and XP in entity.components:
            value = entity.components[XP].xp_value
            if value:
                xp.current += value
                log.add(f"You gain {value} XP.")
                _check_level_up(xp, log)

        entity.components.clear()
        entity.tags.clear()


def _check_level_up(xp: XP, log: MessageLog) -> None:
    while xp.current >= xp.xp_to_next:
        xp.current -= xp.xp_to_next
        xp.level += 1
        xp.xp_to_next = int(xp.xp_to_next * 1.5)
        log.add(f"You reach level {xp.level}!")

"""Combat system for the roguelike."""
from __future__ import annotations

from typing import TYPE_CHECKING

import tcod.constants
import tcod.map
from tcod.ecs import Entity

from actions import (
    BumpAction,
    EquipAction,
    PickupAction,
    UseItemAction,
    WaitAction,
)
from components import (
    Equipment,
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
from equipment import equip_item, unequip_item
from items import use_consumable
from palette import BLUE, DIM_GRAY, LIGHT_RED, ORANGE, RED, WHITE, YELLOW

if TYPE_CHECKING:
    from game_map import GameMap

FOV_RADIUS = 8


def compute_fov(game_map: "GameMap", x: int, y: int) -> None:
    """Compute the field of view from (x, y) and mark explored tiles."""
    game_map.visible[:] = tcod.map.compute_fov(
        transparency=game_map.tiles["transparent"],
        pov=(y, x),
        radius=FOV_RADIUS,
        algorithm=tcod.constants.FOV_SYMMETRIC_SHADOWCAST,
    )
    game_map.explored |= game_map.visible


def attack(attacker: Entity, target: Entity) -> tuple[str, tuple[int, int, int]]:
    """Resolve a melee attack. Returns a (message, color) pair."""
    attacker_name = attacker.components[Name].name
    target_name = target.components[Name].name

    power = get_power(attacker)
    defense = get_defense(target)
    damage = max(0, power - defense)

    if damage > 0:
        target.components[Fighter].hp -= damage
        return (
            f"{attacker_name} attacks {target_name} for {damage} damage.",
            YELLOW if "player" in attacker.tags else RED,
        )
    return (
        f"{attacker_name} attacks {target_name} but does no damage.",
        DIM_GRAY,
    )


def heal(entity: Entity, amount: int) -> int:
    """Restore ``amount`` HP to ``entity`` (capped at max_hp).

    Returns the number of HP actually restored (0 if the entity is at full
    health). Used by consumable items via the message log.
    """
    fighter = entity.components[Fighter]
    healed = min(amount, fighter.max_hp - fighter.hp)
    fighter.hp += healed
    return healed


def process_player_action(
    action,
    registry,
    game_map: "GameMap",
    log,
) -> bool:
    """Handle a player-generated action. Returns True if a turn was spent."""
    if isinstance(action, WaitAction):
        return True

    if isinstance(action, BumpAction):
        return _player_bump(action, registry, game_map, log)

    if isinstance(action, PickupAction):
        return _player_pickup(action, registry, log)

    if isinstance(action, UseItemAction):
        return _player_use_item(action, registry, game_map, log)

    if isinstance(action, EquipAction):
        return _player_equip(action, registry, log)

    return False


def _player_bump(action, registry, game_map: "GameMap", log) -> bool:
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
            msg, color = attack(attacker=action.entity, target=other)
            log.add(msg, color)
            return True

    pos.x = target_x
    pos.y = target_y
    return True


def _player_pickup(action, registry, log) -> bool:
    player = action.entity
    if Inventory not in player.components:
        return False
    inv = player.components[Inventory]
    ppos = player.components[Position]

    for item_entity, ipos, item in registry.Q[Entity, Position, Item]:
        if ipos.x == ppos.x and ipos.y == ppos.y:
            if len(inv.items) >= inv.capacity:
                log.add("Your inventory is full.", ORANGE)
                return False
            inv.items.append(item_entity)
            _remove_from_map(item_entity)
            log.add(f"You pick up the {item.name}.", ORANGE)
            return True
    log.add("There is nothing here to pick up.", WHITE)
    return False


def _remove_from_map(item_entity: Entity) -> None:
    """Take a lying item off the map (stop rendering / positioning it)."""
    for comp in (Position, Renderable):
        item_entity.components.pop(comp, None)


def _player_use_item(action, registry, game_map: "GameMap", log) -> bool:
    player = action.entity
    inv = player.components.get(Inventory)
    if inv is None or not inv.items:
        log.add("You have nothing to use.", WHITE)
        return False

    # Use either a targeted item passed in, or the first consumable in hand.
    item = action.item
    if item is None:
        for candidate in inv.items:
            if has_consumable(candidate):
                item = candidate
                break
    if item is None or not has_consumable(item):
        log.add("You have no usable item.", WHITE)
        return False

    return use_consumable(registry, game_map, player, item, log)


def has_consumable(item: Entity) -> bool:
    from components import Consumable

    return Consumable in item.components


def _player_equip(action, registry, log) -> bool:
    player = action.entity
    inv = player.components.get(Inventory)
    if inv is None or not inv.items:
        log.add("You have nothing to equip.", WHITE)
        return False

    item = action.item
    if item is None and inv.items:
        # Default: equip the first equippable item in the inventory.
        from components import Equippable

        for candidate in inv.items:
            if Equippable in candidate.components:
                item = candidate
                break
    if item is None:
        log.add("You have nothing to equip.", WHITE)
        return False

    from components import Equippable

    if Equippable not in item.components:
        log.add(f"The {_item_name(item)} cannot be equipped.", WHITE)
        return False

    return equip_item(player, item, log)


def _item_name(item: Entity) -> str:
    if Name in item.components:
        return item.components[Name].name
    return "item"


def resolve_enemy_attacks(
    registry,
    game_map: "GameMap",
    player: Entity,
    log,
) -> None:
    """Let every enemy adjacent to (or overlapping) the player attack it."""
    ppos = player.components[Position]

    for entity, pos, fighter in registry.Q[Entity, Position, Fighter]:
        if entity is player:
            continue
        if fighter.hp <= 0:
            continue

        dx = pos.x - ppos.x
        dy = pos.y - ppos.y
        distance = max(abs(dx), abs(dy))

        if distance == 1:
            msg, color = attack(attacker=entity, target=player)
            log.add(msg, color)
        elif distance == 0:
            # The AI moved onto the player's tile: attack and push back.
            msg, color = attack(attacker=entity, target=player)
            log.add(msg, color)
            _push_back(entity, pos, game_map, registry, player)


def _push_back(
    entity: Entity,
    pos: Position,
    game_map: "GameMap",
    registry,
    player: Entity,
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


def remove_dead_entities(registry, log, player: Entity) -> None:
    """Remove defeated entities and award XP for slain enemies."""
    xp = player.components.get(XP)

    for entity in registry.Q.all_of(components=[Fighter]):
        fighter = entity.components[Fighter]
        if fighter.hp > 0:
            continue
        name = entity.components[Name].name if Name in entity.components else "Unknown"
        log.add(f"{name} has been defeated!", LIGHT_RED)

        if xp is not None and XP in entity.components:
            value = entity.components[XP].xp_value
            if value:
                xp.current += value
                log.add(f"You gain {value} XP.", BLUE)
                _check_level_up(xp, log)

        entity.components.clear()
        entity.tags.clear()


def _check_level_up(xp: XP, log) -> None:
    while xp.current >= xp.xp_to_next:
        xp.current -= xp.xp_to_next
        xp.level += 1
        xp.xp_to_next = int(xp.xp_to_next * 1.5)
        log.add(f"You reach level {xp.level}!", BLUE)

"""Combat and healing for the roguelike."""
from __future__ import annotations

from typing import TYPE_CHECKING

import tcod.constants
import tcod.map
from tcod.ecs import Entity

from components import Fighter, Name, Position, XP
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


def attack(attacker: Entity, target: Entity) -> str:
    """Resolve a melee attack and return a human-readable message."""
    attacker_fighter = attacker.components[Fighter]
    target_fighter = target.components[Fighter]
    attacker_name = attacker.components[Name].name
    target_name = target.components[Name].name

    damage = max(0, attacker_fighter.power - target_fighter.defense)
    if damage > 0:
        target_fighter.hp -= damage
        return f"{attacker_name} attacks {target_name} for {damage} damage."
    return f"{attacker_name} attacks {target_name} but does no damage."


def process_bump(
    registry,
    game_map: GameMap,
    entity: Entity,
    dx: int,
    dy: int,
    log: MessageLog,
) -> bool:
    """Try to move the entity by (dx, dy), attacking anything in the way.

    Returns True if the entity's turn was spent (a move or an attack).
    """
    pos = entity.components[Position]
    target_x = pos.x + dx
    target_y = pos.y + dy

    if not game_map.is_walkable(target_x, target_y):
        return False

    for other, other_pos, fighter in registry.Q[Entity, Position, Fighter]:
        if (
            other_pos.x == target_x
            and other_pos.y == target_y
            and other is not entity
        ):
            log.add(attack(attacker=entity, target=other))
            return True

    pos.x = target_x
    pos.y = target_y
    return True


def damage(entity: Entity, amount: int, log: MessageLog) -> int:
    """Apply raw damage to an entity and append a log message.

    Returns the amount of damage actually dealt.
    """
    fighter = entity.components[Fighter]
    dealt = max(0, min(amount, fighter.hp))
    fighter.hp -= dealt
    name = entity.components[Name].name
    log.add(f"{name} takes {dealt} damage.", fg=(255, 80, 80))
    return dealt


def heal(entity: Entity, amount: int, log: MessageLog) -> bool:
    """Restore an entity's HP. Returns True if any HP was restored."""
    fighter = entity.components[Fighter]
    amount = min(amount, fighter.max_hp - fighter.hp)
    if amount <= 0:
        return False
    fighter.hp += amount
    log.add(f"You feel your wounds close. (+{amount} HP)", fg=(0, 255, 0))
    return True


def resolve_enemy_attacks(
    registry,
    game_map: GameMap,
    player: Entity,
    log: MessageLog,
) -> None:
    """Let every enemy adjacent to (or overlapping) the player attack it."""
    ppos = player.components[Position]

    for entity, pos, fighter, ai in registry.Q[Entity, Position, Fighter, XP]:
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
    entity: Entity,
    pos: Position,
    game_map: GameMap,
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


def remove_dead_entities(registry, log: MessageLog, player: Entity) -> None:
    """Remove defeated entities, award XP, and drop their items."""
    from components import Inventory

    for entity in list(registry.Q.all_of(components=[Fighter])):
        fighter = entity.components[Fighter]
        if fighter.hp > 0:
            continue
        name = entity.components[Name].name if Name in entity.components else "Unknown"
        log.add(f"{name} has been defeated!", fg=(180, 180, 180))

        xp = player.components.get(XP)
        if xp is not None and XP in entity.components:
            value = entity.components[XP].xp_value
            if value:
                xp.current += value
                log.add(f"You gain {value} XP.", fg=(255, 255, 0))
                _check_level_up(xp, log)

        _drop_carried_items(entity)

        entity.components.clear()
        entity.tags.clear()


def _drop_carried_items(entity: Entity) -> None:
    """Put any items a dying entity carries back onto the floor."""
    from components import Inventory, Position

    if Inventory not in entity.components:
        return
    inv = entity.components[Inventory]
    pos = entity.components[Position] if Position in entity.components else None
    if pos is None:
        return
    for item in list(inv.items):
        item.components[Position] = Position(x=pos.x, y=pos.y)
        item.tags.add("item")
    inv.items.clear()


def _check_level_up(xp: XP, log: MessageLog) -> None:
    while xp.current >= xp.xp_to_next:
        xp.current -= xp.xp_to_next
        xp.level += 1
        xp.xp_to_next = int(xp.xp_to_next * 1.5)
        log.add(f"You reach level {xp.level}!", fg=(0, 255, 255))

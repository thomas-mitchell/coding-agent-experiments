"""Spell effects shared by scrolls and other magical items."""
from __future__ import annotations

from typing import TYPE_CHECKING

from tcod.ecs import Entity

from components import AI, AIKind, Consumable, Fighter, Inventory, Name, Position
from color import GREEN, PURPLE, RED, YELLOW

if TYPE_CHECKING:
    import tcod.ecs
    from game_map import GameMap


def cast_heal(entity: Entity, item: Entity, amount: int, log) -> bool:
    """Restore HP to ``entity``. Returns True if the spell had an effect."""
    from combat import heal

    healed = heal(entity, amount)
    if healed == 0:
        log.add("Your health is already full.", YELLOW)
        return False
    log.add(
        f"You drink the {_item_name(item)} and recover {healed} HP.",
        GREEN,
    )
    return True


def cast_confusion(
    registry: "tcod.ecs.Registry",
    game_map: "GameMap",
    entity: Entity,
    item: Entity,
    log,
) -> bool:
    """Confuse the nearest visible enemy. Returns True if one was affected."""
    ppos = entity.components[Position]

    best_entity: Entity | None = None
    best_distance: int | None = None
    for other, pos, ai in registry.Q[Entity, Position, AI]:
        if other is entity:
            continue
        if Fighter not in other.components:
            continue
        if not game_map.visible[pos.y, pos.x]:
            continue
        dist = abs(pos.x - ppos.x) + abs(pos.y - ppos.y)
        if best_distance is None or dist < best_distance:
            best_distance = dist
            best_entity = other

    if best_entity is None:
        log.add("The scroll fizzles; no enemy is in sight.", YELLOW)
        return False

    ai = best_entity.components[AI]
    ai.previous_kind = ai.kind
    ai.kind = AIKind.CONFUSED
    ai.confused_turns = 10

    target_name = best_entity.components[Name].name
    log.add(
        f"You read the {_item_name(item)}. {target_name} is confused!",
        PURPLE,
    )
    return True


def cast_fireball(
    registry: "tcod.ecs.Registry",
    game_map: "GameMap",
    entity: Entity,
    item: Entity,
    target: tuple[int, int],
    damage: int,
    radius: int,
    log,
) -> bool:
    """Blast every enemy within ``radius`` of ``target`` tile.

    Returns True if at least one enemy was hit.
    """
    tx, ty = target
    hit_any = False

    for other, pos, fighter in registry.Q[Entity, Position, Fighter]:
        if other is entity:
            continue
        if fighter.hp <= 0:
            continue
        dist = max(abs(pos.x - tx), abs(pos.y - ty))
        if dist > radius:
            continue
        fighter.hp -= damage
        name = other.components[Name].name
        log.add(f"The fireball blasts {name} for {damage} damage.", RED)
        hit_any = True

    if not hit_any:
        log.add("The fireball explodes on empty ground.", RED)
        return True  # the spell is still spent

    log.add(f"You hurl the {_item_name(item)}!", PURPLE)
    return True


def _item_name(item: Entity) -> str:
    if Name in item.components:
        return item.components[Name].name
    return "item"

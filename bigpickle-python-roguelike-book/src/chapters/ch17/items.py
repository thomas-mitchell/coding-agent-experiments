"""Items, consumables, and their use effects."""
from __future__ import annotations

from typing import TYPE_CHECKING

from tcod.ecs import Entity

from components import (
    AI,
    AIKind,
    Consumable,
    Fighter,
    Inventory,
    Name,
    Position,
)
from palette import GREEN, PURPLE, RED, YELLOW

if TYPE_CHECKING:
    import tcod.ecs
    from game_map import GameMap


def use_consumable(
    registry: "tcod.ecs.Registry",
    game_map: "GameMap",
    entity: Entity,
    item: Entity,
    log,
) -> bool:
    """Use a consumable item. Returns True if it was consumed."""
    consumable = item.components[Consumable]
    if consumable.use_function == "heal":
        return _use_heal(entity, item, consumable, log)
    if consumable.use_function == "confusion":
        return _use_confusion(registry, game_map, entity, item, log)
    if consumable.use_function == "fireball":
        return _use_fireball(registry, game_map, entity, item, consumable, log)
    log.add("Nothing happens.", YELLOW)
    return False


def _use_heal(entity: Entity, item: Entity, consumable: Consumable, log) -> bool:
    from combat import heal

    amount = consumable.heal_amount
    healed = heal(entity, amount)
    if healed == 0:
        log.add("Your health is already full.", YELLOW)
        return False

    log.add(f"You drink the {_item_name(item)} and recover {healed} HP.", GREEN)
    _consume(entity, item)
    return True


def _use_confusion(
    registry: "tcod.ecs.Registry",
    game_map: "GameMap",
    entity: Entity,
    item: Entity,
    log,
) -> bool:
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
    _consume(entity, item)
    return True


def _use_fireball(
    registry: "tcod.ecs.Registry",
    game_map: "GameMap",
    entity: Entity,
    item: Entity,
    consumable: Consumable,
    log,
) -> bool:
    ppos = entity.components[Position]
    hit_any = False

    for other, pos, fighter in registry.Q[Entity, Position, Fighter]:
        if other is entity:
            continue
        if fighter.hp <= 0:
            continue
        dist = max(abs(pos.x - ppos.x), abs(pos.y - ppos.y))
        if dist > consumable.radius:
            continue
        if not game_map.visible[pos.y, pos.x]:
            continue
        fighter.hp -= consumable.damage
        name = other.components[Name].name
        log.add(f"The fireball blasts {name} for {consumable.damage} damage.", RED)
        hit_any = True

    if not hit_any:
        log.add("The fireball fizzles; no enemy is in range.", YELLOW)
        return False

    log.add(f"You hurl the {_item_name(item)}!", PURPLE)
    _consume(entity, item)
    return True


def _consume(entity: Entity, item: Entity) -> None:
    """Remove a used item from the actor's inventory and the registry's view."""
    inv = entity.components.get(Inventory)
    if inv is not None and item in inv.items:
        inv.items.remove(item)
    item.components.clear()
    item.tags.clear()


def _item_name(item: Entity) -> str:
    if Name in item.components:
        return item.components[Name].name
    return "item"

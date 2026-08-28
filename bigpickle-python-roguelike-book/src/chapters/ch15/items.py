"""Item pickup, drop, and use logic."""
from __future__ import annotations

from typing import TYPE_CHECKING

from tcod.ecs import Entity

from combat import damage, heal
from components import (
    AI,
    AIKind,
    Consumable,
    ConsumableEffect,
    Fighter,
    Inventory,
    Item,
    Name,
    Position,
)
from message_log import MessageLog

if TYPE_CHECKING:
    import tcod.ecs
    from game_map import GameMap


def pickup_item(registry: tcod.ecs.Registry, player: Entity, log: MessageLog) -> bool:
    """Pick up the first item on the player's tile, if any."""
    inv = player.components[Inventory]
    ppos = player.components[Position]

    for item_entity, ipos, item in registry.Q[Entity, Position, Item]:
        if ipos.x == ppos.x and ipos.y == ppos.y:
            if len(inv.items) >= inv.capacity:
                log.add("Your inventory is full.", fg=(255, 100, 100))
                return False
            inv.items.append(item_entity)
            # Carried items lose their map position but keep their identity,
            # so they render inside the inventory panel instead of the floor.
            item_entity.components.pop(Position, None)
            item_entity.tags.discard("item")
            item_entity.tags.add("inventory")
            log.add(f"You pick up the {item.name}.", fg=(200, 200, 200))
            return True

    log.add("There is nothing here to pick up.", fg=(200, 200, 200))
    return False


def drop_item(
    registry: tcod.ecs.Registry, player: Entity, item_index: int, log: MessageLog
) -> bool:
    """Drop the inventory item at the given index onto the current tile."""
    inv = player.components[Inventory]
    if not (0 <= item_index < len(inv.items)):
        return False

    item = inv.items.pop(item_index)
    ppos = player.components[Position]
    item.components[Position] = Position(x=ppos.x, y=ppos.y)
    item.tags.discard("inventory")
    item.tags.add("item")
    name = item.components[Name].name if Name in item.components else "Unknown"
    log.add(f"You drop the {name}.", fg=(200, 200, 200))
    return True


def use_item(
    registry: tcod.ecs.Registry,
    player: Entity,
    item_index: int,
    game_map: GameMap,
    log: MessageLog,
) -> bool:
    """Use a consumable item from the inventory. Returns True on success."""
    inv = player.components[Inventory]
    if inv is None:
        return False
    if not (0 <= item_index < len(inv.items)):
        log.add("You have nothing there.", fg=(200, 200, 200))
        return False

    item = inv.items[item_index]
    if Consumable not in item.components:
        log.add("There is nothing to use there.", fg=(200, 200, 200))
        return False

    consumable = item.components[Consumable]
    handlers = {
        ConsumableEffect.HEAL: _use_heal,
        ConsumableEffect.LIGHTNING: _use_lightning,
        ConsumableEffect.FIREBALL: _use_fireball,
        ConsumableEffect.CONFUSION: _use_confusion,
    }
    handler = handlers.get(consumable.effect)
    if handler is None:
        return False

    name = item.components[Name].name if Name in item.components else "item"
    if handler(registry, player, consumable, game_map, log):
        inv.items.pop(item_index)
        item.components.clear()
        item.tags.clear()
        log.add(f"You use the {name}.", fg=(200, 180, 50))
        return True
    return False


def _use_heal(
    registry: tcod.ecs.Registry,
    player: Entity,
    consumable: Consumable,
    game_map: GameMap,
    log: MessageLog,
) -> bool:
    return heal(player, consumable.amount, log)


def _use_lightning(
    registry: tcod.ecs.Registry,
    player: Entity,
    consumable: Consumable,
    game_map: GameMap,
    log: MessageLog,
) -> bool:
    target = _nearest_visible_enemy(registry, game_map, player, consumable.range)
    if target is None:
        log.add("No enemy is within range.", fg=(200, 200, 200))
        return False
    name = target.components[Name].name
    dealt = damage(target, consumable.amount, log)
    log.add(f"A lightning bolt strikes the {name} for {dealt} damage!", fg=(255, 255, 0))
    return True


def _use_fireball(
    registry: tcod.ecs.Registry,
    player: Entity,
    consumable: Consumable,
    game_map: GameMap,
    log: MessageLog,
) -> bool:
    center = _nearest_visible_enemy(registry, game_map, player, consumable.range)
    if center is None:
        log.add("No enemy is within range.", fg=(200, 200, 200))
        return False
    cx, cy = center.components[Position].x, center.components[Position].y

    hit_any = False
    for entity, pos, fighter in registry.Q[Entity, Position, Fighter]:
        if entity is player or fighter.hp <= 0:
            continue
        dist_sq = (pos.x - cx) ** 2 + (pos.y - cy) ** 2
        if dist_sq <= consumable.radius ** 2:
            damage(entity, consumable.amount, log)
            hit_any = True

    if not hit_any:
        log.add("The fireball engulfs you! (missed)", fg=(255, 255, 0))
        return True
    return True


def _use_confusion(
    registry: tcod.ecs.Registry,
    player: Entity,
    consumable: Consumable,
    game_map: GameMap,
    log: MessageLog,
) -> bool:
    target = _nearest_visible_enemy(registry, game_map, player, consumable.range)
    if target is None:
        log.add("No enemy is within range.", fg=(200, 200, 200))
        return False
    ai = target.components[AI]
    ai.previous_kind = ai.kind
    ai.kind = AIKind.CONFUSED
    ai.confused_turns = consumable.duration
    name = target.components[Name].name
    log.add(f"The {name} starts wandering in a daze!", fg=(255, 100, 255))
    return True


def _nearest_visible_enemy(
    registry: tcod.ecs.Registry,
    game_map: GameMap,
    player: Entity,
    max_range: int,
) -> Entity | None:
    """Find the closest enemy within range that the player can see."""
    ppos = player.components[Position]
    best: Entity | None = None
    best_distance: int | None = None

    for entity, pos, fighter in registry.Q[Entity, Position, Fighter]:
        if entity is player or fighter.hp <= 0:
            continue
        if not game_map.in_bounds(pos.x, pos.y):
            continue
        if not game_map.visible[pos.y, pos.x]:
            continue
        dist = abs(pos.x - ppos.x) + abs(pos.y - ppos.y)
        if dist > max_range:
            continue
        if best_distance is None or dist < best_distance:
            best_distance = dist
            best = entity
    return best

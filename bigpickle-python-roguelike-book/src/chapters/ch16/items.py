"""Item usage and inventory selection logic."""
from __future__ import annotations
from typing import TYPE_CHECKING

from tcod.ecs import Entity

from components import (
    AI,
    AIKind,
    Consumable,
    Equipment,
    Fighter,
    Inventory,
    Name,
    Position,
)
from equipment import equip_item, unequip_item
from message_log import MessageLog

if TYPE_CHECKING:
    from game_map import GameMap


def equip_selection(
    entity: Entity,
    index: int,
    message_log: MessageLog,
) -> bool:
    """Equip the item at the given inventory index. Returns True if valid."""
    inventory = entity.components.get(Inventory)
    if inventory is None:
        return False
    if index < 0 or index >= len(inventory.items):
        return False
    equip_item(entity, index, message_log)
    return True


def unequip_selection(
    entity: Entity,
    index: int,
    message_log: MessageLog,
) -> bool:
    """Unequip the equipped item selected by index (weapon, then armor)."""
    equip = entity.components.get(Equipment)
    slots: list[str] = []
    if equip is not None:
        if equip.weapon is not None:
            slots.append("weapon")
        if equip.armor is not None:
            slots.append("armor")
    if index < 0 or index >= len(slots):
        return False
    unequip_item(entity, slots[index], message_log)
    return True


def use_selection(
    entity: Entity,
    index: int,
    registry,
    game_map: GameMap,
    message_log: MessageLog,
) -> bool:
    """Consume the item at the given inventory index. Returns True on success."""
    inventory = entity.components.get(Inventory)
    if inventory is None:
        return False
    if index < 0 or index >= len(inventory.items):
        return False

    item = inventory.items[index]
    consumable = item.components.get(Consumable)
    if consumable is None:
        message_log.add("You can't use that.", (255, 255, 0))
        return False

    if consumable.use_function == "confusion":
        return _cast_confusion(entity, registry, game_map, item, message_log)
    if consumable.use_function == "heal":
        return _heal(entity, item, consumable, message_log)
    return False


def use_first_consumable(
    entity: Entity,
    registry,
    game_map: GameMap,
    message_log: MessageLog,
) -> bool:
    """Use the first consumable in the actor's inventory."""
    inventory = entity.components.get(Inventory)
    if inventory is None:
        return False
    for index, item in enumerate(inventory.items):
        if Consumable in item.components:
            return use_selection(entity, index, registry, game_map, message_log)
    message_log.add("You have nothing to use.", (255, 255, 0))
    return False


def _cast_confusion(
    player: Entity,
    registry,
    game_map: GameMap,
    item: Entity,
    message_log: MessageLog,
) -> bool:
    ppos = player.components[Position]

    best_entity: Entity | None = None
    best_distance: int | None = None
    for entity, pos, fighter in registry.Q[Entity, Position, Fighter]:
        if entity is player:
            continue
        if not game_map.visible[pos.y, pos.x]:
            continue
        dist = abs(pos.x - ppos.x) + abs(pos.y - ppos.y)
        if best_distance is None or dist < best_distance:
            best_distance = dist
            best_entity = entity

    if best_entity is None:
        message_log.add("The scroll fizzles; no enemy is in sight.", (255, 255, 0))
        return False

    ai = best_entity.components[AI]
    ai.previous_kind = ai.kind
    ai.kind = AIKind.CONFUSED
    ai.confused_turns = 10

    target_name = best_entity.components[Name].name
    item_name = item.components[Name].name
    _remove_item(player, item)
    message_log.add(f"You read the {item_name}. The {target_name} is confused!", (255, 255, 255))
    return True


def _heal(
    entity: Entity,
    item: Entity,
    consumable: Consumable,
    message_log: MessageLog,
) -> bool:
    fighter = entity.components[Fighter]
    if fighter.hp >= fighter.max_hp:
        message_log.add("You are already at full health.", (255, 255, 0))
        return False
    healed = min(consumable.heal_amount, fighter.max_hp - fighter.hp)
    fighter.hp += healed
    _remove_item(entity, item)
    message_log.add(f"You feel better. (+{healed} HP)", (0, 255, 0))
    return True


def _remove_item(entity: Entity, item: Entity) -> None:
    entity.components[Inventory].items.remove(item)

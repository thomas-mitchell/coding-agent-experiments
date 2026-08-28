"""Equipment system."""
from __future__ import annotations
from typing import TYPE_CHECKING

from components import Equipment, Equippable, Inventory, Name
from message_log import MessageLog

if TYPE_CHECKING:
    import tcod.ecs


def equip_item(
    entity: tcod.ecs.Entity,
    item_index: int,
    message_log: MessageLog,
) -> None:
    """Equip an item from inventory."""
    inventory = entity.components.get(Inventory)
    equip = entity.components.get(Equipment)
    
    if inventory is None or equip is None:
        return
    
    if item_index >= len(inventory.items):
        return
    
    item = inventory.items[item_index]
    equippable = item.components.get(Equippable)
    
    if equippable is None:
        message_log.add("You can't equip that.", (255, 255, 0))
        return
    
    item_name = item.components[Name].name
    
    if equippable.slot == "weapon":
        if equip.weapon is not None:
            # Swap
            old_weapon = equip.weapon
            old_name = old_weapon.components[Name].name
            inventory.items[item_index] = old_weapon
            equip.weapon = item
            message_log.add(f"You equip the {item_name} and unequip the {old_name}.", (200, 200, 200))
        else:
            equip.weapon = item
            inventory.items.pop(item_index)
            message_log.add(f"You equip the {item_name}.", (200, 200, 200))
    elif equippable.slot == "armor":
        if equip.armor is not None:
            old_armor = equip.armor
            old_name = old_armor.components[Name].name
            inventory.items[item_index] = old_armor
            equip.armor = item
            message_log.add(f"You equip the {item_name} and unequip the {old_name}.", (200, 200, 200))
        else:
            equip.armor = item
            inventory.items.pop(item_index)
            message_log.add(f"You equip the {item_name}.", (200, 200, 200))


def unequip_item(
    entity: tcod.ecs.Entity,
    slot: str,
    message_log: MessageLog,
) -> None:
    """Unequip an item from a slot."""
    inventory = entity.components.get(Inventory)
    equip = entity.components.get(Equipment)
    
    if inventory is None or equip is None:
        return
    
    if len(inventory.items) >= inventory.capacity:
        message_log.add("Your inventory is full.", (255, 255, 0))
        return
    
    if slot == "weapon" and equip.weapon is not None:
        item = equip.weapon
        item_name = item.components[Name].name
        inventory.items.append(item)
        equip.weapon = None
        message_log.add(f"You unequip the {item_name}.", (200, 200, 200))
    elif slot == "armor" and equip.armor is not None:
        item = equip.armor
        item_name = item.components[Name].name
        inventory.items.append(item)
        equip.armor = None
        message_log.add(f"You unequip the {item_name}.", (200, 200, 200))

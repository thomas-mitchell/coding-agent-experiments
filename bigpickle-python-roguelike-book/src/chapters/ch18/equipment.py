from __future__ import annotations

from typing import TYPE_CHECKING

from .components import Equippable, Equipment, Fighter, Inventory, Name

if TYPE_CHECKING:
    from tcod.ecs import World


def equip(item_id: int, world: World) -> str:
    player = world["player"]
    inventory = world[player, "Inventory"]
    equipment = world[player, "Equipment"]
    equipable = world[item_id, "Equippable"]
    item_name = world[item_id, "Name"].name

    target_slot = "weapon" if equipable.power_bonus > 0 else "armor"

    if getattr(equipment, target_slot) is not None:
        unequip_item_id = getattr(equipment, target_slot)
        current_name = world[unequip_item_id, "Name"].name
        old_equipable = world[unequip_item_id, "Equippable"]

        fighter = world[player, "Fighter"]
        if target_slot == "weapon":
            fighter.power -= old_equipable.power_bonus
        else:
            fighter.defense -= old_equipable.defense_bonus

        setattr(equipment, target_slot, None)
        result = f"You unequip the {current_name}."
    else:
        result = ""

    setattr(equipment, target_slot, item_id)
    fighter = world[player, "Fighter"]
    if target_slot == "weapon":
        fighter.power += equipable.power_bonus
    else:
        fighter.defense += equipable.defense_bonus

    return f"{result} You equip the {item_name}." if result else f"You equip the {item_name}."


def unequip(item_id: int, world: World) -> str:
    player = world["player"]
    equipment = world[player, "Equipment"]
    item_name = world[item_id, "Name"].name
    equipable = world[item_id, "Equippable"]

    target_slot = "weapon" if equipable.power_bonus > 0 else "armor"

    if getattr(equipment, target_slot) == item_id:
        setattr(equipment, target_slot, None)
        fighter = world[player, "Fighter"]
        if target_slot == "weapon":
            fighter.power -= equipable.power_bonus
        else:
            fighter.defense -= equipable.defense_bonus
        return f"You unequip the {item_name}."
    return f"The {item_name} is not equipped."

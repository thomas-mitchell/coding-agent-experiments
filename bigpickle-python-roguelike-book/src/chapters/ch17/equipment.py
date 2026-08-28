"""Equipment system: equipping and unequipping items into slots."""
from __future__ import annotations

from tcod.ecs import Entity

from components import Equipment, Equippable, Inventory, Name
from palette import CYAN, YELLOW


def equip_item(
    player: Entity,
    item: Entity,
    log,
) -> bool:
    """Equip an item from the inventory into its slot. Returns True if successful."""
    equip = player.components.get(Equipment)
    if equip is None:
        log.add("You have no equipment slots.", YELLOW)
        return False

    equippable = item.components.get(Equippable)
    if equippable is None:
        log.add(f"The {_item_name(item)} cannot be equipped.", YELLOW)
        return False

    slot = equippable.slot
    inv = player.components[Inventory]
    if item not in inv.items:
        log.add(f"You are not carrying the {_item_name(item)}.", YELLOW)
        return False

    # Unequip whatever currently occupies this slot (put it back in inventory).
    current = getattr(equip, slot, None)
    if current is not None:
        inv.items.append(current)
        setattr(equip, slot, None)
        log.add(f"You unequip the {_item_name(current)}.", CYAN)

    # Equip the new item.
    setattr(equip, slot, item)
    inv.items.remove(item)

    if equippable.power_bonus:
        log.add(
            f"You equip the {_item_name(item)} (+{equippable.power_bonus} power).",
            CYAN,
        )
    else:
        log.add(
            f"You equip the {_item_name(item)} (+{equippable.defense_bonus} defense).",
            CYAN,
        )
    return True


def unequip_item(
    player: Entity,
    item: Entity,
    log,
) -> bool:
    """Unequip a currently-equipped item, returning it to the inventory."""
    equip = player.components.get(Equipment)
    if equip is None:
        return False

    inv = player.components[Inventory]
    if item is equip.weapon:
        equip.weapon = None
        inv.items.append(item)
        log.add(f"You unequip the {_item_name(item)}.", CYAN)
        return True
    if item is equip.armor:
        equip.armor = None
        inv.items.append(item)
        log.add(f"You unequip the {_item_name(item)}.", CYAN)
        return True
    return False


def _item_name(item: Entity) -> str:
    if Name in item.components:
        return item.components[Name].name
    return "item"

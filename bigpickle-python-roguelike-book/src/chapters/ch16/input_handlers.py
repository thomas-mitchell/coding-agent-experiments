"""Input handler converting events to actions."""
from __future__ import annotations
from typing import TYPE_CHECKING
import tcod.event

from actions import (
    Action,
    BumpAction,
    EquipmentMenuAction,
    MenuCancelAction,
    MenuSelectAction,
    PickupAction,
    UnequipMenuAction,
    UseItemAction,
    WaitAction,
)

if TYPE_CHECKING:
    import tcod.ecs


VI_KEYS: dict[tcod.event.KeySym, tuple[int, int]] = {
    tcod.event.KeySym.h: (-1, 0),
    tcod.event.KeySym.j: (0, 1),
    tcod.event.KeySym.k: (0, -1),
    tcod.event.KeySym.l: (1, 0),
    tcod.event.KeySym.y: (-1, -1),
    tcod.event.KeySym.u: (1, -1),
    tcod.event.KeySym.b: (-1, 1),
    tcod.event.KeySym.n: (1, 1),
}

# Map letter keys to menu indices (a..j select entries 0..9).
MENU_KEYS: dict[tcod.event.KeySym, int] = {
    tcod.event.KeySym.a: 0,
    tcod.event.KeySym.b: 1,
    tcod.event.KeySym.c: 2,
    tcod.event.KeySym.d: 3,
    tcod.event.KeySym.e: 4,
    tcod.event.KeySym.f: 5,
    tcod.event.KeySym.g: 6,
    tcod.event.KeySym.h: 7,
    tcod.event.KeySym.i: 8,
    tcod.event.KeySym.j: 9,
}


def handle_menu_input(
    event: tcod.event.KeyDown, entity: tcod.ecs.Entity
) -> Action | None:
    """Convert a key event into an action while a menu is open."""
    if event.sym in MENU_KEYS:
        return MenuSelectAction(entity=entity, index=MENU_KEYS[event.sym])
    if event.sym == tcod.event.KeySym.ESCAPE:
        return MenuCancelAction(entity=entity)
    return None


def handle_input(
    event: tcod.event.KeyDown, entity: tcod.ecs.Entity
) -> Action | None:
    """Convert a key event into an action for the given entity."""
    # Arrow-key movement.
    if event.sym == tcod.event.KeySym.UP:
        return BumpAction(entity=entity, dx=0, dy=-1)
    elif event.sym == tcod.event.KeySym.DOWN:
        return BumpAction(entity=entity, dx=0, dy=1)
    elif event.sym == tcod.event.KeySym.LEFT:
        return BumpAction(entity=entity, dx=-1, dy=0)
    elif event.sym == tcod.event.KeySym.RIGHT:
        return BumpAction(entity=entity, dx=1, dy=0)
    # Vi-keys movement.
    elif event.sym in VI_KEYS:
        dx, dy = VI_KEYS[event.sym]
        return BumpAction(entity=entity, dx=dx, dy=dy)
    # Wait.
    elif event.sym == tcod.event.KeySym.PERIOD:
        return WaitAction(entity=entity)
    # Pick up an item.
    elif event.sym == tcod.event.KeySym.g:
        return PickupAction(entity=entity)
    # Use a consumable.
    elif event.sym == tcod.event.KeySym.f:
        return UseItemAction(entity=entity)
    # Open the equip / unequip menus.
    elif event.sym == tcod.event.KeySym.e:
        return EquipmentMenuAction(entity=entity)
    elif event.sym == tcod.event.KeySym.r:
        return UnequipMenuAction(entity=entity)

    return None

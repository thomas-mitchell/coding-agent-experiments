"""Input handler converting events to actions."""
from __future__ import annotations
from typing import TYPE_CHECKING
import tcod.event

from actions import Action, BumpAction, WaitAction, PickupAction, UseItemAction

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

# Number keys for inventory use (1-9)
INVENTORY_KEYS = {
    tcod.event.KeySym.KEY_1: 0,
    tcod.event.KeySym.KEY_2: 1,
    tcod.event.KeySym.KEY_3: 2,
    tcod.event.KeySym.KEY_4: 3,
    tcod.event.KeySym.KEY_5: 4,
    tcod.event.KeySym.KEY_6: 5,
    tcod.event.KeySym.KEY_7: 6,
    tcod.event.KeySym.KEY_8: 7,
    tcod.event.KeySym.KEY_9: 8,
}


def handle_input(
    event: tcod.event.KeyDown, entity: tcod.ecs.Entity
) -> Action | None:
    """Convert a key event into an action for the given entity."""
    # Movement keys
    if event.sym == tcod.event.KeySym.UP:
        return BumpAction(entity=entity, dx=0, dy=-1)
    elif event.sym == tcod.event.KeySym.DOWN:
        return BumpAction(entity=entity, dx=0, dy=1)
    elif event.sym == tcod.event.KeySym.LEFT:
        return BumpAction(entity=entity, dx=-1, dy=0)
    elif event.sym == tcod.event.KeySym.RIGHT:
        return BumpAction(entity=entity, dx=1, dy=0)
    # Vi keys
    elif event.sym in VI_KEYS:
        dx, dy = VI_KEYS[event.sym]
        return BumpAction(entity=entity, dx=dx, dy=dy)
    # Wait
    elif event.sym == tcod.event.KeySym.PERIOD:
        return WaitAction(entity=entity)
    # Pick up
    elif event.sym == tcod.event.KeySym.g:
        return PickupAction(entity=entity)
    # Use inventory item (number keys)
    elif event.sym in INVENTORY_KEYS:
        index = INVENTORY_KEYS[event.sym]
        return UseItemAction(entity=entity, item_index=index)

    return None

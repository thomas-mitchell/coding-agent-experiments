"""Input handler converting events into actions."""
from __future__ import annotations

from typing import TYPE_CHECKING

import tcod.event

from actions import (
    Action,
    BumpAction,
    DropAction,
    PickupAction,
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

# Maps the top-row number keys '1'..'9' to inventory slot indices 0..8.
NUMBER_KEYS: dict[tcod.event.KeySym, int] = {
    getattr(tcod.event.KeySym, f"N{i}"): i - 1 for i in range(1, 10)
}


def handle_input(
    event: tcod.event.KeyDown,
    entity: tcod.ecs.Entity,
    drop_mode: bool = False,
) -> Action | None:
    """Convert a key event into an action for the given entity.

    When drop_mode is True, the number keys 1-9 produce DropAction instances
    so the player can choose which item to drop.
    """
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
    # Wait in place.
    elif event.sym == tcod.event.KeySym.PERIOD:
        return WaitAction(entity=entity)
    # Pick up an item.
    elif event.sym == tcod.event.KeySym.g:
        return PickupAction(entity=entity)

    # In the drop menu, the number keys choose which item to drop.
    if drop_mode:
        if event.sym in NUMBER_KEYS:
            return DropAction(entity=entity, index=NUMBER_KEYS[event.sym])
        return None

    # Out of the drop menu: 'd' opens it and 1-9 use an inventory item.
    if event.sym == tcod.event.KeySym.d:
        return DropAction(entity=entity, index=-1)
    if event.sym in NUMBER_KEYS:
        return UseItemAction(entity=entity, index=NUMBER_KEYS[event.sym])

    return None

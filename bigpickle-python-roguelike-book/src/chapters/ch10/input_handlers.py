"""Input handler converting events to actions."""
from __future__ import annotations
from typing import TYPE_CHECKING
import tcod.event

from actions import Action, BumpAction, WaitAction

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


def handle_input(
    event: tcod.event.KeyDown, entity: tcod.ecs.Entity
) -> Action | None:
    """Convert a key event into an action for the given entity."""
    if event.sym == tcod.event.KeySym.UP:
        return BumpAction(entity=entity, dx=0, dy=-1)
    elif event.sym == tcod.event.KeySym.DOWN:
        return BumpAction(entity=entity, dx=0, dy=1)
    elif event.sym == tcod.event.KeySym.LEFT:
        return BumpAction(entity=entity, dx=-1, dy=0)
    elif event.sym == tcod.event.KeySym.RIGHT:
        return BumpAction(entity=entity, dx=1, dy=0)
    elif event.sym in VI_KEYS:
        dx, dy = VI_KEYS[event.sym]
        return BumpAction(entity=entity, dx=dx, dy=dy)
    elif event.sym == tcod.event.KeySym.PERIOD:
        return WaitAction(entity=entity)

    return None

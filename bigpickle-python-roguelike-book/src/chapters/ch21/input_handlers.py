"""Input handler converting events to actions."""
from __future__ import annotations

from typing import TYPE_CHECKING

import tcod.event

from actions import (
    Action,
    BumpAction,
    DescendAction,
    EquipAction,
    LevelUpChoiceAction,
    PickupAction,
    UseItemAction,
    WaitAction,
)
from components import DEFENSE_CHOICE, HP_CHOICE, POWER_CHOICE

if TYPE_CHECKING:
    import tcod.ecs

    from targeting import TargetingState


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
    event: tcod.event.KeyDown,
    entity: tcod.ecs.Entity,
) -> Action | None:
    """Convert a key event into an action for the given entity."""
    # Arrow-key movement.
    if event.sym == tcod.event.KeySym.UP:
        return BumpAction(entity=entity, dx=0, dy=-1)
    if event.sym == tcod.event.KeySym.DOWN:
        return BumpAction(entity=entity, dx=0, dy=1)
    if event.sym == tcod.event.KeySym.LEFT:
        return BumpAction(entity=entity, dx=-1, dy=0)
    if event.sym == tcod.event.KeySym.RIGHT:
        return BumpAction(entity=entity, dx=1, dy=0)
    # Vi-keys movement.
    if event.sym in VI_KEYS:
        dx, dy = VI_KEYS[event.sym]
        return BumpAction(entity=entity, dx=dx, dy=dy)
    # Wait a turn.
    if event.sym == tcod.event.KeySym.PERIOD:
        return WaitAction(entity=entity)
    # Pick up an item at the player's feet.
    if event.sym == tcod.event.KeySym.g:
        return PickupAction(entity=entity)
    # Use the first usable item (health potion, scroll, ...).
    if event.sym in (tcod.event.KeySym.f, tcod.event.KeySym.u):
        return UseItemAction(entity=entity)
    # Equip the first equippable item (weapon / armor).
    if event.sym == tcod.event.KeySym.e:
        return EquipAction(entity=entity)
    # Descend the staircase to the next floor.
    if event.sym == tcod.event.KeySym.GREATER:
        return DescendAction(entity=entity)

    return None


# Keys that spend a pending level-up on a particular upgrade.
_LEVEL_UP_KEYS: dict[tcod.event.KeySym, str] = {
    tcod.event.KeySym.a: HP_CHOICE,
    tcod.event.KeySym.b: POWER_CHOICE,
    tcod.event.KeySym.c: DEFENSE_CHOICE,
    tcod.event.KeySym.N1: HP_CHOICE,
    tcod.event.KeySym.N2: POWER_CHOICE,
    tcod.event.KeySym.N3: DEFENSE_CHOICE,
    tcod.event.KeySym.KP_1: HP_CHOICE,
    tcod.event.KeySym.KP_2: POWER_CHOICE,
    tcod.event.KeySym.KP_3: DEFENSE_CHOICE,
}


def handle_level_up_input(
    event: tcod.event.KeyDown,
    entity: tcod.ecs.Entity,
) -> LevelUpChoiceAction | None:
    """Convert a key event into a level-up choice action.

    Called while the game is in the ``LEVEL_UP`` state. Returns ``None`` for
    any unrelated key (e.g. arrows), so only the a/b/c or 1/2/3 choices move
    the game forward.
    """
    choice = _LEVEL_UP_KEYS.get(event.sym)
    if choice is not None:
        return LevelUpChoiceAction(entity=entity, choice=choice)
    return None


def handle_targeting_input(
    event: tcod.event.KeyDown,
    state: "TargetingState",
    map_width: int,
    map_height: int,
) -> str:
    """Handle input while targeting mode is active.

    Returns one of:
      * "move"   -- the cursor moved; the screen should be re-rendered.
      * "cast"   -- the player confirmed a target; cast the spell.
      * "cancel" -- the player aborted; spend no turn.
      * "none"   -- no relevant key was pressed.
    """
    from targeting import move_cursor

    if event.sym == tcod.event.KeySym.UP or event.sym == tcod.event.KeySym.k:
        move_cursor(state, 0, -1, map_width, map_height)
        return "move"
    if event.sym == tcod.event.KeySym.DOWN or event.sym == tcod.event.KeySym.j:
        move_cursor(state, 0, 1, map_width, map_height)
        return "move"
    if event.sym == tcod.event.KeySym.LEFT or event.sym == tcod.event.KeySym.h:
        move_cursor(state, -1, 0, map_width, map_height)
        return "move"
    if event.sym == tcod.event.KeySym.RIGHT or event.sym == tcod.event.KeySym.l:
        move_cursor(state, 1, 0, map_width, map_height)
        return "move"
    # Diagonal movement with Vi-keys.
    if event.sym in VI_KEYS:
        dx, dy = VI_KEYS[event.sym]
        move_cursor(state, dx, dy, map_width, map_height)
        return "move"
    # Confirm the target (or cancel if the cursor is out of range).
    if event.sym in (tcod.event.KeySym.RETURN, tcod.event.KeySym.SPACE):
        return "cast"
    if event.sym == tcod.event.KeySym.ESCAPE:
        return "cancel"

    return "none"

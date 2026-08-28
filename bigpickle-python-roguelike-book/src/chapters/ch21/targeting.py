"""Targeting mode: aiming a targeted spell with a moveable cursor."""
from __future__ import annotations

import attrs

from components import TargetingMode


@attrs.define
class TargetingState:
    """Holds the state of an in-progress targeting session.

    When ``active`` is True the game enters a special mode where arrow keys
    move a cursor across the map. The player confirms a target (Return/Space)
    to cast, or cancels (Escape) to abort and spend no turn.
    """

    active: bool = False
    mode: TargetingMode = TargetingMode.NONE
    item: object = None
    cursor_x: int = 0
    cursor_y: int = 0
    max_range: int = 0
    radius: int = 0

    @property
    def target(self) -> tuple[int, int]:
        return self.cursor_x, self.cursor_y

    @property
    def is_area(self) -> bool:
        return self.mode == TargetingMode.AREA


def begin_targeting(
    item,
    origin_x: int,
    origin_y: int,
    mode: TargetingMode,
    max_range: int,
    radius: int = 0,
) -> TargetingState:
    """Create a targeting session aimed at a tile."""
    return TargetingState(
        active=True,
        mode=mode,
        item=item,
        cursor_x=origin_x,
        cursor_y=origin_y,
        max_range=max_range,
        radius=radius,
    )


def move_cursor(state: TargetingState, dx: int, dy: int, map_width: int, map_height: int) -> bool:
    """Move the targeting cursor. Returns True if it actually moved."""
    nx = state.cursor_x + dx
    ny = state.cursor_y + dy
    if 0 <= nx < map_width and 0 <= ny < map_height:
        state.cursor_x = nx
        state.cursor_y = ny
        return True
    return False


def range_to_origin(state: TargetingState, origin_x: int, origin_y: int) -> int:
    return max(abs(state.cursor_x - origin_x), abs(state.cursor_y - origin_y))


def in_range(state: TargetingState, origin_x: int, origin_y: int) -> bool:
    """Return True if the cursor is within the spell's maximum range."""
    if state.max_range <= 0:
        return True
    return range_to_origin(state, origin_x, origin_y) <= state.max_range


def cancel_targeting(state: TargetingState) -> None:
    """Abort the targeting session without casting."""
    state.active = False
    state.item = None

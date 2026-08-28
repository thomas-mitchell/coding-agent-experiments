"""Action classes for the roguelike."""
from __future__ import annotations

from typing import TYPE_CHECKING

import attrs

if TYPE_CHECKING:
    import tcod.ecs


@attrs.define
class Action:
    entity: tcod.ecs.Entity


@attrs.define
class BumpAction(Action):
    dx: int = 0
    dy: int = 0


@attrs.define
class WaitAction(Action):
    pass


@attrs.define
class PickupAction(Action):
    """Pick up whatever item is on the actor's tile."""

    pass


@attrs.define
class UseItemAction(Action):
    """Use the consumable in the inventory slot given by index."""

    index: int = 0


@attrs.define
class DropAction(Action):
    """Drop the inventory item at the given index onto the floor.

    An index of -1 signals "open the drop menu" (no turn is spent).
    """

    index: int = -1

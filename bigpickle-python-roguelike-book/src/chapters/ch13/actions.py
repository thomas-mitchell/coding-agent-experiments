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
    pass


@attrs.define
class UseItemAction(Action):
    item_index: int = 0


@attrs.define
class DropAction(Action):
    item_index: int = 0

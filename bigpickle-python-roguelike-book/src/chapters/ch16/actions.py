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
    """Use the first consumable-like item in the actor's inventory."""

    item: tcod.ecs.Entity | None = None


@attrs.define
class EquipmentMenuAction(Action):
    """Open the equip-item menu."""


@attrs.define
class UnequipMenuAction(Action):
    """Open the unequip-item menu."""


@attrs.define
class MenuSelectAction(Action):
    """Select an entry (by index) from the currently open menu."""

    index: int = 0


@attrs.define
class MenuCancelAction(Action):
    """Close the currently open menu without selecting anything."""

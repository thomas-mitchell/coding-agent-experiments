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
    """Use a consumable item carried by the actor.

    ``item`` may be ``None``, in which case the first usable item in the
    actor's inventory is used.
    """

    item: tcod.ecs.Entity | None = None


@attrs.define
class EquipAction(Action):
    """Equip or unequip an item into its slot."""

    item: tcod.ecs.Entity | None = None


@attrs.define
class DescendAction(Action):
    """Descend the staircase to the next dungeon level.

    Only meaningful when the actor is standing on a tile that carries a
    ``Stairs`` component.
    """


@attrs.define
class CastAction(Action):
    """Confirm a spell cast at a chosen target tile.

    Produced by the targeting mode after the player aims and confirms with a
    targeted scroll (for example a fireball). ``target`` is the ``(x, y)``
    tile the spell is centred on.
    """

    item: tcod.ecs.Entity | None = None
    target: tuple[int, int] | None = None


@attrs.define
class LevelUpChoiceAction(Action):
    """Spend one pending level-up on an upgrade.

    ``choice`` is one of ``HP_CHOICE``, ``POWER_CHOICE`` or ``DEFENSE_CHOICE``
    (defined in :mod:`components`). The player makes this choice from the
    level-up menu that appears whenever XP banks a new level.
    """

    choice: str = "hp"

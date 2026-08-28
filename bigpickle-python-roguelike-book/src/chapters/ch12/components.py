"""Component classes for the roguelike ECS."""
from __future__ import annotations

import attrs
import enum


class AIKind(enum.Enum):
    """The type of artificial intelligence driving an entity."""

    HOSTILE = "hostile"
    NEUTRAL = "neutral"
    FLEEING = "fleeing"


@attrs.define
class Position:
    """The tile coordinates of an entity on the map."""

    x: int = 0
    y: int = 0


@attrs.define
class Renderable:
    """How an entity is drawn on the screen."""

    char: str = "?"
    fg: tuple[int, int, int] = (255, 255, 255)


@attrs.define
class Name:
    """The display name of an entity."""

    name: str = "Unknown"


@attrs.define
class Description:
    """A longer, flavor text description of an entity."""

    description: str = ""


@attrs.define
class Fighter:
    """Stats for any entity that can fight and take damage."""

    hp: int = 1
    max_hp: int = 1
    power: int = 1
    defense: int = 0


@attrs.define
class XP:
    """Experience and leveling information for an entity."""

    current: int = 0
    level: int = 1
    xp_to_next: int = 0


@attrs.define
class AI:
    """Marks an entity as controlled by the computer with a given behavior."""

    kind: AIKind = AIKind.NEUTRAL


@attrs.define
class Item:
    """Marks an entity as an item that can be picked up and used."""

    name: str = "Item"
    description: str = ""


@attrs.define
class Inventory:
    """Holds the list of item entities an entity is carrying."""

    capacity: int = 0
    items: list = attrs.Factory(list)

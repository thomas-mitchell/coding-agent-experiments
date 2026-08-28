"""Item components: pickable objects and entity inventories."""
from __future__ import annotations

import attrs


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

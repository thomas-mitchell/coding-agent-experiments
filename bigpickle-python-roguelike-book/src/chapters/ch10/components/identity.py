"""Identity components: names and descriptions for entities."""
from __future__ import annotations

import attrs


@attrs.define
class Name:
    """The display name of an entity."""

    name: str = "Unknown"


@attrs.define
class Description:
    """A longer, flavor text description of an entity."""

    description: str = ""

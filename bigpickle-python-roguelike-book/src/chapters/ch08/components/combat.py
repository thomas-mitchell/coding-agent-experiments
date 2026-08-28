"""Combat components: health, attack, defense and experience."""
from __future__ import annotations

import attrs


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

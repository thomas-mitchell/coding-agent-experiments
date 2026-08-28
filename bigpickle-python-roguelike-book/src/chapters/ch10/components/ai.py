"""AI components: behavior kinds for non-player entities."""
from __future__ import annotations

import attrs
import enum


class AIKind(enum.Enum):
    """The type of artificial intelligence driving an entity."""

    HOSTILE = "hostile"
    NEUTRAL = "neutral"
    FLEEING = "fleeing"


@attrs.define
class AI:
    """Marks an entity as controlled by the computer with a given behavior."""

    kind: AIKind = AIKind.NEUTRAL

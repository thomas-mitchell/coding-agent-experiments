"""Components for the roguelike."""
from __future__ import annotations

from enum import Enum

import attrs


@attrs.define
class Position:
    x: int = 0
    y: int = 0


@attrs.define
class Renderable:
    char: str = "?"
    fg: tuple[int, int, int] = (255, 255, 255)
    render_order: int = 0


@attrs.define
class Name:
    name: str = "Unknown"


@attrs.define
class Description:
    text: str = ""


class AIKind(Enum):
    HOSTILE = "hostile"
    CONFUSED = "confused"
    FLEEING = "fleeing"
    STATIONARY = "stationary"


@attrs.define
class AI:
    kind: AIKind = AIKind.HOSTILE
    previous_kind: AIKind | None = None
    confused_turns: int = 0
    flee_threshold: float = 0.25  # Flee when below 25% HP


@attrs.define
class Fighter:
    hp: int = 10
    max_hp: int = 10
    power: int = 3
    defense: int = 0


@attrs.define
class XP:
    current: int = 0
    level: int = 1
    xp_to_next: int = 100
    xp_value: int = 0  # XP awarded on kill


@attrs.define
class Item:
    """Marks an entity as a ground or carried item."""

    name: str = ""
    description: str = ""


class ConsumableEffect(Enum):
    HEAL = "heal"
    LIGHTNING = "lightning"
    FIREBALL = "fireball"
    CONFUSION = "confusion"


@attrs.define
class Consumable:
    """Describes what an item does when used."""

    effect: ConsumableEffect = ConsumableEffect.HEAL
    amount: int = 10      # Heal amount, lightning/fireball damage
    radius: int = 3       # Fireball blast radius
    range: int = 5        # Lightning bolt maximum reach
    duration: int = 10    # Confusion duration in turns


@attrs.define
class Inventory:
    items: list = attrs.Factory(list)
    capacity: int = 10

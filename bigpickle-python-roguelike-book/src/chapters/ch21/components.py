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


@attrs.define
class Stairs:
    """Marks a tile as the downwards staircase for this level.

    When the player stands on a tile occupied by an entity carrying this
    component, they may press ``>`` to descend to the next dungeon level.
    """


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
    flee_threshold: float = 0.25


@attrs.define
class Fighter:
    hp: int = 10
    max_hp: int = 10
    power: int = 3
    defense: int = 0


@attrs.define
class XP:
    """Tracks a creature's experience and level.

    ``current`` holds the progress toward the next level. ``xp_to_next`` is
    the amount of XP required to reach the next level. ``level_ups_pending``
    records how many unspent level-up choices the player still owes.

    ``xp_value`` is how many XP this entity awards when slain (nonzero on
    enemies, always zero on the player).
    """

    current: int = 0
    level: int = 1
    xp_to_next: int = 100
    xp_value: int = 0
    level_ups_pending: int = 0


# --- Level-up choices ------------------------------------------------------
# The player may spend a pending level-up on one of these upgrades.
HP_CHOICE = "hp"
POWER_CHOICE = "power"
DEFENSE_CHOICE = "defense"


class TargetingMode(Enum):
    """How a spell selects its target."""

    NONE = "none"
    AREA = "area"     # fire a blast centered on a chosen tile
    LINE = "line"     # zapping a straight line / nearest visible enemy


@attrs.define
class Spell:
    """Definition of a castable spell."""

    name: str = ""
    use_function: str = "heal"
    damage: int = 0
    radius: int = 0
    heal_amount: int = 0
    max_range: int = 0
    targeting_mode: TargetingMode = TargetingMode.NONE


@attrs.define
class Item:
    name: str = ""
    description: str = ""


@attrs.define
class Consumable:
    heal_amount: int = 0
    damage: int = 0
    radius: int = 0
    max_range: int = 0
    use_function: str = "heal"
    targeting_mode: TargetingMode = TargetingMode.NONE


@attrs.define
class Equippable:
    power_bonus: int = 0
    defense_bonus: int = 0
    slot: str = "weapon"


@attrs.define
class Equipment:
    weapon: object = None
    armor: object = None


@attrs.define
class Inventory:
    items: list = attrs.Factory(list)
    capacity: int = 10


@attrs.define
class Message:
    text: str
    color: tuple[int, int, int] = (255, 255, 255)


@attrs.define
class MessageLog:
    messages: list[Message] = attrs.Factory(list)
    max_messages: int = 100
    history_offset: int = 0

    def add(self, text: str, color: tuple[int, int, int] = (255, 255, 255)) -> None:
        self.messages.append(Message(text=text, color=color))
        if len(self.messages) > self.max_messages:
            self.messages.pop(0)

    @property
    def recent(self) -> list[Message]:
        return self.messages[-5:]

    def get_visible(self, count: int = 5) -> list[Message]:
        """Get messages for display."""
        if not self.messages:
            return []
        start = max(0, len(self.messages) - count)
        return self.messages[start:]


@attrs.define
class GameWorld:
    """Global state that survives a level transition."""

    dungeon_level: int = 1


def get_power(entity) -> int:
    fighter = entity.components[Fighter]
    equip = entity.components.get(Equipment)
    bonus = 0
    if equip:
        if equip.weapon and hasattr(equip.weapon, "components"):
            eq = equip.weapon.components.get(Equippable)
            if eq:
                bonus += eq.power_bonus
        if equip.armor and hasattr(equip.armor, "components"):
            eq = equip.armor.components.get(Equippable)
            if eq:
                bonus += eq.power_bonus
    return fighter.power + bonus


def get_defense(entity) -> int:
    fighter = entity.components[Fighter]
    equip = entity.components.get(Equipment)
    bonus = 0
    if equip:
        if equip.weapon and hasattr(equip.weapon, "components"):
            eq = equip.weapon.components.get(Equippable)
            if eq:
                bonus += eq.defense_bonus
        if equip.armor and hasattr(equip.armor, "components"):
            eq = equip.armor.components.get(Equippable)
            if eq:
                bonus += eq.defense_bonus
    return fighter.defense + bonus

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
    flee_threshold: float = 0.25


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
    xp_value: int = 0


@attrs.define
class Item:
    name: str = ""
    description: str = ""


@attrs.define
class Consumable:
    heal_amount: int = 0
    damage: int = 0
    radius: int = 0
    use_function: str = "heal"


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


def get_power(entity) -> int:
    fighter = entity.components[Fighter]
    equip = entity.components.get(Equipment)
    bonus = 0
    if equip:
        if equip.weapon and hasattr(equip.weapon, 'components'):
            eq = equip.weapon.components.get(Equippable)
            if eq:
                bonus += eq.power_bonus
        if equip.armor and hasattr(equip.armor, 'components'):
            eq = equip.armor.components.get(Equippable)
            if eq:
                bonus += eq.power_bonus
    return fighter.power + bonus


def get_defense(entity) -> int:
    fighter = entity.components[Fighter]
    equip = entity.components.get(Equipment)
    bonus = 0
    if equip:
        if equip.weapon and hasattr(equip.weapon, 'components'):
            eq = equip.weapon.components.get(Equippable)
            if eq:
                bonus += eq.defense_bonus
        if equip.armor and hasattr(equip.armor, 'components'):
            eq = equip.armor.components.get(Equippable)
            if eq:
                bonus += eq.defense_bonus
    return fighter.defense + bonus

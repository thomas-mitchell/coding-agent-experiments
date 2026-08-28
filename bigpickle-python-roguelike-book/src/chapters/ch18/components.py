from __future__ import annotations

from dataclasses import dataclass, field
from enum import Enum, auto
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from .game_map import GameMap


class AIKind(Enum):
    HOSTILE = auto()
    CONFUSED = auto()


@dataclass
class Position:
    x: int = 0
    y: int = 0


@dataclass
class Renderable:
    char: str = "?"
    color: tuple[int, int, int] = (255, 255, 255)
    render_order: int = 0  # 0=item, 1=corpse, 2=actor


@dataclass
class Name:
    name: str = "Unknown"


@dataclass
class Description:
    text: str = ""


@dataclass
class AI:
    kind: AIKind = AIKind.HOSTILE
    path: list[tuple[int, int]] = field(default_factory=list)


@dataclass
class Fighter:
    hp: int = 10
    max_hp: int = 10
    defense: int = 0
    power: int = 3


@dataclass
class XP:
    current: int = 0
    level: int = 1
    level_up_base: int = 200
    level_up_factor: int = 150

    @property
    def level_up_xp(self) -> int:
        return self.level_up_base + self.level * self.level_up_factor


@dataclass
class Item:
    pass


@dataclass
class Consumable:
    healing_amount: int = 0
    damage_amount: int = 0
    radius: int = 0
    max_range: int = 0
    is_confusion: bool = False


@dataclass
class Equippable:
    power_bonus: int = 0
    defense_bonus: int = 0


@dataclass
class Equipment:
    weapon: int | None = None
    armor: int | None = None


@dataclass
class Inventory:
    capacity: int = 20
    items: list[int] = field(default_factory=list)


@dataclass
class Message:
    text: str = ""
    color: tuple[int, int, int] = (255, 255, 255)


@dataclass
class MessageLog:
    messages: list[Message] = field(default_factory=list)
    max_messages: int = 50

    def add(self, text: str, color: tuple[int, int, int] = (255, 255, 255)) -> None:
        self.messages.append(Message(text=text, color=color))
        if len(self.messages) > self.max_messages:
            self.messages = self.messages[-self.max_messages:]

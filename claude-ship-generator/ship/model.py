"""Core data structures shared by the generation stages and the game."""

from __future__ import annotations

from dataclasses import dataclass, field
from enum import Enum

import numpy as np


@dataclass(frozen=True)
class Rect:
    """A wall-bounded region. Edges are wall tiles; ``x2``/``y2`` are inclusive.

    Neighbouring rects share an edge line, so compartments are separated by a
    single wall rather than empty space.
    """

    x: int
    y: int
    x2: int
    y2: int

    @property
    def w(self) -> int:
        return self.x2 - self.x + 1

    @property
    def h(self) -> int:
        return self.y2 - self.y + 1

    @property
    def inner_w(self) -> int:
        return self.w - 2

    @property
    def inner_h(self) -> int:
        return self.h - 2

    @property
    def inner_area(self) -> int:
        return max(0, self.inner_w) * max(0, self.inner_h)

    @property
    def center(self) -> tuple[int, int]:
        return (self.x + self.x2) // 2, (self.y + self.y2) // 2

    def inner_slices(self) -> tuple[slice, slice]:
        return slice(self.x + 1, self.x2), slice(self.y + 1, self.y2)


class ZoneKind(Enum):
    COMMAND = "Command"
    HABITATION = "Habitation"
    SCIENCE = "Science"
    CARGO = "Cargo"
    ENGINEERING = "Engineering"


@dataclass
class Block:
    """A zone-owned region between corridors, waiting to be partitioned."""

    rect: Rect
    zone: ZoneKind


@dataclass
class Room:
    id: int
    rect: Rect
    zone: ZoneKind
    type: str = "Unassigned"
    doors: list[tuple[int, int]] = field(default_factory=list)


CORRIDOR_NODE = 0  # graph node representing the whole corridor network


@dataclass
class Ship:
    seed: int
    width: int
    height: int
    tiles: np.ndarray  # shape (width, height), tile ids from ship.tiles
    blocks: list[Block] = field(default_factory=list)
    rooms: list[Room] = field(default_factory=list)
    graph: dict[int, set[int]] = field(default_factory=dict)
    spawn: tuple[int, int] = (0, 0)
    room_at: np.ndarray | None = None  # room id per tile, 0 where there is no room
    attempts: int = 1

    def room(self, room_id: int) -> Room | None:
        return self.rooms[room_id - 1] if room_id > 0 else None

    def rooms_of_type(self, type_: str) -> list[Room]:
        return [r for r in self.rooms if r.type == type_]

    def connect(self, a: int, b: int) -> None:
        self.graph.setdefault(a, set()).add(b)
        self.graph.setdefault(b, set()).add(a)

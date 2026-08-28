"""
2D discrete spatial math, vectors, bounding boxes, distance metrics, and raycasting.
"""

from __future__ import annotations
from dataclasses import dataclass
from typing import Iterator, Sequence
import math


@dataclass(frozen=True, slots=True)
class Vec2:
    """Immutable 2D integer vector for discrete grid coordinates."""
    x: int
    y: int

    def __add__(self, other: Vec2 | tuple[int, int]) -> Vec2:
        if isinstance(other, Vec2):
            return Vec2(self.x + other.x, self.y + other.y)
        return Vec2(self.x + other[0], self.y + other[1])

    def __sub__(self, other: Vec2 | tuple[int, int]) -> Vec2:
        if isinstance(other, Vec2):
            return Vec2(self.x - other.x, self.y - other.y)
        return Vec2(self.x - other[0], self.y - other[1])

    def __mul__(self, scalar: int) -> Vec2:
        return Vec2(self.x * scalar, self.y * scalar)

    def __neg__(self) -> Vec2:
        return Vec2(-self.x, -self.y)

    def chebyshev_dist(self, other: Vec2) -> int:
        """Chebyshev distance (King's move metric on 8-way grid)."""
        return max(abs(self.x - other.x), abs(self.y - other.y))

    def manhattan_dist(self, other: Vec2) -> int:
        """Manhattan distance (Taxicab metric on 4-way grid)."""
        return abs(self.x - other.x) + abs(self.y - other.y)

    def euclidean_dist(self, other: Vec2) -> float:
        """Euclidean continuous distance."""
        return math.hypot(self.x - other.x, self.y - other.y)

    def neighbors_8(self) -> list[Vec2]:
        """Returns the 8 adjacent neighboring coordinates (Moore neighborhood)."""
        return [
            Vec2(self.x + dx, self.y + dy)
            for dx in (-1, 0, 1)
            for dy in (-1, 0, 1)
            if not (dx == 0 and dy == 0)
        ]

    def neighbors_4(self) -> list[Vec2]:
        """Returns the 4 cardinal neighboring coordinates (von Neumann neighborhood)."""
        return [
            Vec2(self.x + 1, self.y),
            Vec2(self.x - 1, self.y),
            Vec2(self.x, self.y + 1),
            Vec2(self.x, self.y - 1),
        ]

    def step_towards(self, target: Vec2) -> Vec2:
        """Returns a unit directional step towards target."""
        dx = (target.x > self.x) - (target.x < self.x)
        dy = (target.y > self.y) - (target.y < self.y)
        return Vec2(dx, dy)


# Cardinal and diagonal direction constants
CARDINALS: tuple[Vec2, ...] = (
    Vec2(0, -1),  # North
    Vec2(1, 0),   # East
    Vec2(0, 1),   # South
    Vec2(-1, 0),  # West
)

DIAGONALS: tuple[Vec2, ...] = (
    Vec2(1, -1),  # North-East
    Vec2(1, 1),   # South-East
    Vec2(-1, 1),  # South-West
    Vec2(-1, -1), # North-West
)

DIRECTIONS_8: tuple[Vec2, ...] = CARDINALS + DIAGONALS


@dataclass(frozen=True, slots=True)
class Rect:
    """Axis-aligned integer rectangle on a discrete 2D grid."""
    x: int
    y: int
    width: int
    height: int

    @property
    def x1(self) -> int:
        return self.x

    @property
    def y1(self) -> int:
        return self.y

    @property
    def x2(self) -> int:
        return self.x + self.width

    @property
    def y2(self) -> int:
        return self.y + self.height

    @property
    def center(self) -> Vec2:
        return Vec2(self.x + self.width // 2, self.y + self.height // 2)

    def contains(self, point: Vec2) -> bool:
        return self.x1 <= point.x < self.x2 and self.y1 <= point.y < self.y2

    def intersects(self, other: Rect) -> bool:
        return (
            self.x1 < other.x2
            and self.x2 > other.x1
            and self.y1 < other.y2
            and self.y2 > other.y1
        )

    def iter_points(self) -> Iterator[Vec2]:
        for y in range(self.y1, self.y2):
            for x in range(self.x1, self.x2):
                yield Vec2(x, y)


def bresenham_line(start: Vec2, end: Vec2) -> list[Vec2]:
    """
    Standard Bresenham line algorithm returning all points from start to end inclusive.
    """
    points: list[Vec2] = []
    x0, y0 = start.x, start.y
    x1, y1 = end.x, end.y

    dx = abs(x1 - x0)
    dy = abs(y1 - y0)
    sx = 1 if x0 < x1 else -1
    sy = 1 if y0 < y1 else -1
    err = dx - dy

    curr_x, curr_y = x0, y0
    while True:
        points.append(Vec2(curr_x, curr_y))
        if curr_x == x1 and curr_y == y1:
            break
        e2 = 2 * err
        if e2 > -dy:
            err -= dy
            curr_x += sx
        if e2 < dx:
            err += dx
            curr_y += sy

    return points

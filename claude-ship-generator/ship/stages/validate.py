"""Stage 7 (of the core pipeline): gameplay validation.

A failed check means the pipeline throws the ship away and regenerates.
"""

from __future__ import annotations

from collections import deque

import numpy as np

from .. import tiles as T
from ..model import Ship

REQUIRED_TYPES = ("Bridge", "Reactor", "Main Engineering", "Airlock")


def reachable_mask(ship: Ship, start: tuple[int, int]) -> np.ndarray:
    walkable = T.WALKABLE[ship.tiles]
    seen = np.zeros_like(walkable)
    if not walkable[start]:
        return seen
    seen[start] = True
    queue = deque([start])
    while queue:
        x, y = queue.popleft()
        for dx in (-1, 0, 1):
            for dy in (-1, 0, 1):
                nx, ny = x + dx, y + dy
                if 0 <= nx < ship.width and 0 <= ny < ship.height and walkable[nx, ny] and not seen[nx, ny]:
                    seen[nx, ny] = True
                    queue.append((nx, ny))
    return seen


def validate(ship: Ship) -> list[str]:
    """Return a list of problems; empty means the ship is playable."""
    problems = [f"missing {t}" for t in REQUIRED_TYPES if not ship.rooms_of_type(t)]
    if problems:
        return problems
    seen = reachable_mask(ship, ship.spawn)
    for room in ship.rooms:
        if not seen[room.rect.center]:
            problems.append(f"{room.type} #{room.id} unreachable")
    return problems

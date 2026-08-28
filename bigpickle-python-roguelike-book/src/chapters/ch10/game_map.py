"""Game map with field of view support."""
from __future__ import annotations

import numpy as np
import tcod.map

from tile_types import TILE_DTYPE, VOID


class GameMap:
    def __init__(self, width: int, height: int) -> None:
        self.width = width
        self.height = height
        self.tiles = np.full((height, width), fill_value=VOID, dtype=TILE_DTYPE)
        self.visible = np.full((height, width), fill_value=False, dtype=np.bool_)
        self.explored = np.full((height, width), fill_value=False, dtype=np.bool_)

    def in_bounds(self, x: int, y: int) -> bool:
        return 0 <= x < self.width and 0 <= y < self.height

    def is_walkable(self, x: int, y: int) -> bool:
        if self.in_bounds(x, y):
            return bool(self.tiles[y, x]["walkable"])
        return False

    def is_transparent(self, x: int, y: int) -> bool:
        if self.in_bounds(x, y):
            return bool(self.tiles[y, x]["transparent"])
        return False

    def compute_fov(self, x: int, y: int, radius: int = 8) -> None:
        """Compute field of view from position (x, y)."""
        fov = tcod.map.Map(self.width, self.height)
        fov.walkable[:] = self.tiles["walkable"]
        fov.transparent[:] = self.tiles["transparent"]
        fov.compute_fov(x=x, y=y, radius=radius, algorithm=0)  # SYMMETRIC_SHADOWCAST
        self.visible[:] = fov.fov
        self.explored |= self.visible

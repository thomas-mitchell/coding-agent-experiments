from __future__ import annotations

from typing import TYPE_CHECKING

import numpy as np
import tcod

from . import tile_types

if TYPE_CHECKING:
    from tcod.ecs import World


class GameMap:
    def __init__(self, width: int, height: int) -> None:
        self.width = width
        self.height = height
        self.tiles = np.full((width, height), fill_value=tile_types.VOID, order="F")
        self.explored = np.full((width, height), fill_value=False, order="F")
        self.fov = np.zeros((width, height), dtype=np.bool_)

    def in_bounds(self, x: int, y: int) -> bool:
        return 0 <= x < self.width and 0 <= y < self.height

    def compute_fov(self, world: World, origin_x: int, origin_y: int, radius: int = 8) -> None:
        self.fov = tcod.map.compute_fov(
            transparency=self.tiles["transparent"],
            pov=(origin_x, origin_y),
            radius=radius,
        )
        self.explored |= self.fov

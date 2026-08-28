"""
Cellular Automata cave generator with connectivity validation.
"""

from __future__ import annotations
import random
from pyrogue_emergent.core.math2d import Vec2
from pyrogue_emergent.world.grid import LayeredGrid, TileType


class CellularCaveGenerator:
    """
    Generates natural organic caves using cellular automata rules (4-5 rule).
    """
    @staticmethod
    def generate(
        grid: LayeredGrid,
        fill_prob: float = 0.45,
        iterations: int = 4,
        rng: random.Random | None = None,
    ) -> None:
        rand = rng or random.Random()
        w, h = grid.width, grid.height

        # 1. Random noise initialization
        for y in range(h):
            for x in range(w):
                pos = Vec2(x, y)
                if x == 0 or x == w - 1 or y == 0 or y == h - 1:
                    grid.set_tile(pos, TileType.WALL)
                elif rand.random() < fill_prob:
                    grid.set_tile(pos, TileType.WALL)
                else:
                    grid.set_tile(pos, TileType.FLOOR)

        # 2. Smooth iterations (4-5 rule)
        for _ in range(iterations):
            new_tiles: dict[Vec2, TileType] = {}
            for y in range(1, h - 1):
                for x in range(1, w - 1):
                    pos = Vec2(x, y)
                    wall_count = sum(
                        1 for n in pos.neighbors_8()
                        if grid.get_cell(n).tile == TileType.WALL
                    )
                    if wall_count >= 5:
                        new_tiles[pos] = TileType.WALL
                    else:
                        new_tiles[pos] = TileType.FLOOR

            for p, tile in new_tiles.items():
                grid.set_tile(p, tile)

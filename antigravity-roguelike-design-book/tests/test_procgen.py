"""
Unit tests for Procedural Generation pipelines.
"""

import unittest
import random
from pyrogue_emergent.core.math2d import Vec2
from pyrogue_emergent.world.grid import LayeredGrid, TileType
from pyrogue_emergent.ecs.entity import EntityManager
from pyrogue_emergent.procgen.cellular_cave import CellularCaveGenerator
from pyrogue_emergent.procgen.tactical_features import TacticalFeaturePlacer


class TestProcGen(unittest.TestCase):
    def test_cellular_cave_generation(self) -> None:
        grid = LayeredGrid(width=30, height=20)
        rng = random.Random(42)
        CellularCaveGenerator.generate(grid, rng=rng)

        # Verify boundaries are all WALL
        for x in range(grid.width):
            self.assertEqual(grid.get_cell(Vec2(x, 0)).tile, TileType.WALL)
            self.assertEqual(grid.get_cell(Vec2(x, grid.height - 1)).tile, TileType.WALL)

        # Verify internal open floor tiles exist
        floor_count = sum(
            1 for p in grid.iter_positions()
            if grid.get_cell(p).tile == TileType.FLOOR
        )
        self.assertGreater(floor_count, 50)

    def test_tactical_feature_placement(self) -> None:
        grid = LayeredGrid(width=30, height=20)
        ecs = EntityManager()
        rng = random.Random(42)
        CellularCaveGenerator.generate(grid, rng=rng)
        TacticalFeaturePlacer.populate(grid, ecs, rng=rng)

        # Verify items/hazards were placed
        placed_items = sum(len(grid.get_cell(p).items) for p in grid.iter_positions())
        self.assertGreater(placed_items, 0)


if __name__ == "__main__":
    unittest.main()

"""
Unit tests for Dijkstra maps and hazard avoidance pathfinding.
"""

import unittest
from pyrogue_emergent.core.math2d import Vec2
from pyrogue_emergent.world.grid import LayeredGrid, TileType, FluidType
from pyrogue_emergent.ai.dijkstra import DijkstraMap


class TestDijkstraMap(unittest.TestCase):
    def setUp(self) -> None:
        self.grid = LayeredGrid(width=10, height=10)
        self.dmap = DijkstraMap(self.grid)

    def test_straight_line_pathing(self) -> None:
        player_pos = Vec2(8, 5)
        self.dmap.compute([player_pos])

        # Distance from (5, 5) heading to (8, 5)
        current = Vec2(5, 5)
        next_step = self.dmap.step_downhill(current)

        # Step should move East towards x=8
        self.assertEqual(next_step, Vec2(6, 5))

    def test_hazard_avoidance(self) -> None:
        goal = Vec2(5, 5)
        # Place fire hazard in direct cardinal path at (3, 5)
        self.grid.get_cell(Vec2(3, 5)).fire_intensity = 100

        self.dmap.compute([goal])

        # Starting from (2, 5), instead of stepping directly through fire at (3, 5),
        # the downhill step should path around through diagonal (3, 4) or (3, 6)
        start = Vec2(2, 5)
        step = self.dmap.step_downhill(start)
        self.assertNotEqual(step, Vec2(3, 5))


if __name__ == "__main__":
    unittest.main()

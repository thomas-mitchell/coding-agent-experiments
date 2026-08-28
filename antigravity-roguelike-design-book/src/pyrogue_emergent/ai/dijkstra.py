"""
Tactical Dijkstra maps for pathfinding, tactical retreat, sound propagation, and hazard avoidance.
"""

from __future__ import annotations
import heapq
from typing import Callable, Iterable
from pyrogue_emergent.core.math2d import Vec2
from pyrogue_emergent.world.grid import LayeredGrid, TileType, FluidType


class DijkstraMap:
    """
    Two-dimensional distance field supporting arbitrary goal sets,
    custom movement costs (hazards/fluids), and downhill gradient pathing.
    """
    INFINITY = 999999

    def __init__(self, grid: LayeredGrid) -> None:
        self.grid = grid
        self.width = grid.width
        self.height = grid.height
        self._values: list[int] = [self.INFINITY] * (self.width * self.height)

    def _index(self, pos: Vec2) -> int:
        return pos.y * self.width + pos.x

    def get(self, pos: Vec2) -> int:
        if not self.grid.in_bounds(pos):
            return self.INFINITY
        return self._values[self._index(pos)]

    def compute(
        self,
        goals: Iterable[Vec2],
        hazard_cost_fn: Callable[[Vec2], int] | None = None,
    ) -> None:
        """
        Computes Dijkstra distances from a set of goal coordinates.
        """
        self._values = [self.INFINITY] * (self.width * self.height)
        heap: list[tuple[int, int, int]] = []  # (cost, x, y)

        for goal in goals:
            if self.grid.in_bounds(goal):
                idx = self._index(goal)
                self._values[idx] = 0
                heapq.heappush(heap, (0, goal.x, goal.y))

        while heap:
            cost, x, y = heapq.heappop(heap)
            curr = Vec2(x, y)

            if cost > self._values[self._index(curr)]:
                continue

            for neighbor in curr.neighbors_8():
                if not self.grid.in_bounds(neighbor):
                    continue

                cell = self.grid.get_cell(neighbor)
                if cell.tile in (TileType.WALL, TileType.DOOR_CLOSED):
                    continue

                # Step cost: 10 for cardinal, 14 for diagonal
                base_step = 14 if (neighbor.x != x and neighbor.y != y) else 10

                # Environmental hazard penalty
                hazard_penalty = 0
                if hazard_cost_fn:
                    hazard_penalty = hazard_cost_fn(neighbor)
                else:
                    if cell.fire_intensity > 0:
                        hazard_penalty += 200
                    if cell.fluid_type == FluidType.ACID:
                        hazard_penalty += 150

                new_cost = cost + base_step + hazard_penalty
                n_idx = self._index(neighbor)

                if new_cost < self._values[n_idx]:
                    self._values[n_idx] = new_cost
                    heapq.heappush(heap, (new_cost, neighbor.x, neighbor.y))

    def step_downhill(self, current_pos: Vec2) -> Vec2:
        """
        Finds the adjacent tile with the lowest Dijkstra cost (approaching the goal).
        """
        best_pos = current_pos
        best_cost = self.get(current_pos)

        for neighbor in current_pos.neighbors_8():
            if not self.grid.in_bounds(neighbor):
                continue
            cost = self.get(neighbor)
            if cost < best_cost:
                best_cost = cost
                best_pos = neighbor

        return best_pos

    def step_uphill(self, current_pos: Vec2) -> Vec2:
        """
        Finds the adjacent tile with the highest Dijkstra cost (fleeing away from danger).
        """
        best_pos = current_pos
        best_cost = self.get(current_pos)

        for neighbor in current_pos.neighbors_8():
            if not self.grid.in_bounds(neighbor):
                continue
            cell = self.grid.get_cell(neighbor)
            if cell.blocks_movement:
                continue

            cost = self.get(neighbor)
            if cost != self.INFINITY and cost > best_cost:
                best_cost = cost
                best_pos = neighbor

        return best_pos

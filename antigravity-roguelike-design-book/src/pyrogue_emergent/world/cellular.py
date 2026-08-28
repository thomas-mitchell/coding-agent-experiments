"""
Cellular Automata simulation for Fire, Fluids, Gases, and Thermodynamic exchange.
"""

from __future__ import annotations
import copy
from pyrogue_emergent.core.math2d import Vec2
from pyrogue_emergent.world.grid import LayeredGrid, CellState, TileType, FluidType, GasType


class CellularSimulator:
    """
    Simulates environmental dynamics using double-buffered cellular automata updates.
    """
    def __init__(self, grid: LayeredGrid) -> None:
        self.grid = grid

    def step(self) -> list[str]:
        """
        Advances the cellular simulation by one discrete tick.
        Returns a list of environmental event log messages.
        """
        logs: list[str] = []
        width, height = self.grid.width, self.grid.height
        next_cells = [copy.deepcopy(self.grid.get_cell(Vec2(x, y))) for y in range(height) for x in range(width)]

        def get_next(p: Vec2) -> CellState:
            return next_cells[p.y * width + p.x]

        # 1. Fire, Combustion, and Thermodynamics
        for pos in self.grid.iter_positions():
            curr = self.grid.get_cell(pos)
            nxt = get_next(pos)

            # Active combustion
            if curr.fire_intensity > 0:
                nxt.temperature = min(1000, curr.temperature + curr.fire_intensity * 5)
                nxt.fire_fuel = max(0, curr.fire_fuel - 1)

                # Generate smoke
                if nxt.gas_type in (GasType.NONE, GasType.SMOKE):
                    nxt.gas_type = GasType.SMOKE
                    nxt.gas_density = min(100, nxt.gas_density + 15)

                # Burn out if fuel depleted
                if nxt.fire_fuel == 0:
                    nxt.fire_intensity = 0
                    if nxt.fluid_type == FluidType.OIL:
                        nxt.fluid_type = FluidType.NONE
                        nxt.fluid_volume = 0
                    logs.append(f"Fire at ({pos.x}, {pos.y}) burned out.")

                # Spread fire to flammable neighbors
                for neighbor in pos.neighbors_8():
                    if not self.grid.in_bounds(neighbor):
                        continue
                    n_curr = self.grid.get_cell(neighbor)
                    n_next = get_next(neighbor)

                    if n_curr.tile == TileType.WALL:
                        continue

                    # Spread to oil/alcohol
                    if n_curr.fluid_type in (FluidType.OIL, FluidType.ALCOHOL) and n_curr.fluid_volume > 0 and n_next.fire_intensity == 0:
                        n_next.fire_intensity = 80
                        n_next.fire_fuel = n_curr.fluid_volume // 2 + 5
                        n_next.temperature = max(n_next.temperature, 250)
                        logs.append(f"Oil ignited into a blaze at ({neighbor.x}, {neighbor.y})!")

                    # Ignite flammable vapor / gas
                    if n_curr.gas_type == GasType.FLAMMABLE_VAPOR and n_curr.gas_density > 10:
                        n_next.fire_intensity = 100
                        n_next.fire_fuel = 3
                        n_next.gas_type = GasType.SMOKE
                        n_next.gas_density = 80
                        logs.append(f"Vapor ignited in a flash fire at ({neighbor.x}, {neighbor.y})!")

            # Extinguish fire on water
            if curr.fire_intensity > 0 and curr.fluid_type == FluidType.WATER and curr.fluid_volume > 10:
                nxt.fire_intensity = 0
                nxt.fire_fuel = 0
                nxt.fluid_volume = max(0, nxt.fluid_volume - 15)
                nxt.gas_type = GasType.STEAM
                nxt.gas_density = min(100, nxt.gas_density + 50)
                logs.append(f"Water hissed into steam at ({pos.x}, {pos.y})!")

            # Phase changes: Heat turns Water to Steam
            if curr.fluid_type == FluidType.WATER and curr.temperature > 100 and curr.fluid_volume > 0:
                nxt.fluid_volume = max(0, curr.fluid_volume - 20)
                if nxt.fluid_volume == 0:
                    nxt.fluid_type = FluidType.NONE
                nxt.gas_type = GasType.STEAM
                nxt.gas_density = min(100, nxt.gas_density + 30)

            # Phase changes: Cold turns Water to Ice
            if curr.fluid_type == FluidType.WATER and curr.temperature < 0 and curr.tile == TileType.WATER_SHALLOW:
                nxt.tile = TileType.ICE
                nxt.fluid_type = FluidType.NONE
                nxt.fluid_volume = 0
                logs.append(f"Water froze into solid ice at ({pos.x}, {pos.y}).")

            # Thermal decay towards ambient room temperature (20°C)
            if nxt.temperature > 20 and nxt.fire_intensity == 0:
                nxt.temperature = max(20, nxt.temperature - 5)
            elif nxt.temperature < 20:
                nxt.temperature = min(20, nxt.temperature + 2)

        # 2. Gas Diffusion & Decay
        for pos in self.grid.iter_positions():
            curr = self.grid.get_cell(pos)
            if curr.gas_density <= 0 or curr.gas_type == GasType.NONE:
                continue

            nxt = get_next(pos)
            # Gas decay
            nxt.gas_density = max(0, nxt.gas_density - 2)
            if nxt.gas_density == 0:
                nxt.gas_type = GasType.NONE

            # Diffusion to open neighbors
            open_neighbors = [
                n for n in pos.neighbors_4()
                if self.grid.in_bounds(n) and self.grid.get_cell(n).tile != TileType.WALL
            ]
            if open_neighbors and curr.gas_density > 10:
                diffuse_amount = curr.gas_density // (len(open_neighbors) + 2)
                for n_pos in open_neighbors:
                    n_next = get_next(n_pos)
                    if n_next.gas_type == GasType.NONE:
                        n_next.gas_type = curr.gas_type
                        n_next.gas_density = min(100, n_next.gas_density + diffuse_amount)
                    elif n_next.gas_type == curr.gas_type:
                        n_next.gas_density = min(100, n_next.gas_density + diffuse_amount // 2)

        # 3. Fluid Spreading (Equalization)
        for pos in self.grid.iter_positions():
            curr = self.grid.get_cell(pos)
            if curr.fluid_volume <= 10 or curr.fluid_type == FluidType.NONE:
                continue

            open_neighbors = [
                n for n in pos.neighbors_4()
                if self.grid.in_bounds(n) and self.grid.get_cell(n).tile not in (TileType.WALL, TileType.CHASM)
            ]
            for n_pos in open_neighbors:
                n_curr = self.grid.get_cell(n_pos)
                n_next = get_next(n_pos)
                if n_curr.fluid_type == FluidType.NONE and curr.fluid_volume > 20:
                    flow = curr.fluid_volume // 4
                    n_next.fluid_type = curr.fluid_type
                    n_next.fluid_volume += flow
                    get_next(pos).fluid_volume -= flow

        # Commit double buffer in-place
        for y in range(height):
            for x in range(width):
                pos = Vec2(x, y)
                idx = self.grid._index(pos)
                curr_cell = self.grid._cells[idx]
                nxt_cell = next_cells[idx]
                curr_cell.tile = nxt_cell.tile
                curr_cell.fluid_type = nxt_cell.fluid_type
                curr_cell.fluid_volume = nxt_cell.fluid_volume
                curr_cell.gas_type = nxt_cell.gas_type
                curr_cell.gas_density = nxt_cell.gas_density
                curr_cell.temperature = nxt_cell.temperature
                curr_cell.fire_intensity = nxt_cell.fire_intensity
                curr_cell.fire_fuel = nxt_cell.fire_fuel
                curr_cell.items = nxt_cell.items
                curr_cell.actor = nxt_cell.actor

        return logs

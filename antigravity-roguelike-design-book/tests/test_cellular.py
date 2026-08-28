"""
Unit tests for Cellular Automata dynamics (Fire, Fluid, Gas, Phase Changes).
"""

import unittest
from pyrogue_emergent.core.math2d import Vec2
from pyrogue_emergent.world.grid import LayeredGrid, TileType, FluidType, GasType
from pyrogue_emergent.world.cellular import CellularSimulator


class TestCellularSimulator(unittest.TestCase):
    def setUp(self) -> None:
        self.grid = LayeredGrid(width=10, height=10)
        self.sim = CellularSimulator(self.grid)

    def test_fire_spreads_to_oil(self) -> None:
        # Tile (1, 1) is on fire
        c1 = self.grid.get_cell(Vec2(1, 1))
        c1.fire_intensity = 80
        c1.fire_fuel = 10

        # Neighbor (1, 2) has oil
        c2 = self.grid.get_cell(Vec2(1, 2))
        c2.fluid_type = FluidType.OIL
        c2.fluid_volume = 50

        self.sim.step()

        # Check neighbor caught fire
        self.assertGreater(c2.fire_intensity, 0)
        self.assertGreater(c2.temperature, 20)

    def test_water_extinguishes_fire_to_steam(self) -> None:
        c = self.grid.get_cell(Vec2(3, 3))
        c.fire_intensity = 80
        c.fire_fuel = 10
        c.fluid_type = FluidType.WATER
        c.fluid_volume = 40

        self.sim.step()

        self.assertEqual(c.fire_intensity, 0)
        self.assertEqual(c.gas_type, GasType.STEAM)
        self.assertGreater(c.gas_density, 0)

    def test_gas_diffusion(self) -> None:
        c = self.grid.get_cell(Vec2(5, 5))
        c.gas_type = GasType.SMOKE
        c.gas_density = 80

        self.sim.step()

        # Adjacent cell should have received diffused smoke
        c_north = self.grid.get_cell(Vec2(5, 4))
        self.assertEqual(c_north.gas_type, GasType.SMOKE)
        self.assertGreater(c_north.gas_density, 0)


if __name__ == "__main__":
    unittest.main()

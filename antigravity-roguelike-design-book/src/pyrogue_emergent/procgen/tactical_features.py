"""
Placement of systemic affordances: oil slicks, water puddles, explosive barrels, and gas vents.
"""

from __future__ import annotations
import random
from pyrogue_emergent.core.math2d import Vec2
from pyrogue_emergent.world.grid import LayeredGrid, TileType, FluidType, GasType
from pyrogue_emergent.ecs.entity import EntityManager
from pyrogue_emergent.ecs.components import Position, Renderable, Physics, Material, MaterialType, Flammable


class TacticalFeaturePlacer:
    """
    Scatters interactive environmental hazards and affordances across valid floor tiles.
    """
    @staticmethod
    def populate(
        grid: LayeredGrid,
        ecs: EntityManager,
        rng: random.Random | None = None,
    ) -> None:
        rand = rng or random.Random()
        floor_positions = [
            pos for pos in grid.iter_positions()
            if grid.get_cell(pos).tile == TileType.FLOOR and grid.get_cell(pos).actor is None
        ]
        if not floor_positions:
            return

        rand.shuffle(floor_positions)

        # 1. Place Oil Puddles (clusters)
        oil_centers = floor_positions[:3]
        for center in oil_centers:
            for n in [center] + center.neighbors_4():
                if grid.in_bounds(n) and grid.get_cell(n).tile == TileType.FLOOR:
                    cell = grid.get_cell(n)
                    cell.fluid_type = FluidType.OIL
                    cell.fluid_volume = 50

        # 2. Place Water Puddles (conductive hazards)
        water_centers = floor_positions[3:6]
        for center in water_centers:
            for n in [center] + center.neighbors_4():
                if grid.in_bounds(n) and grid.get_cell(n).tile == TileType.FLOOR:
                    cell = grid.get_cell(n)
                    cell.fluid_type = FluidType.WATER
                    cell.fluid_volume = 60

        # 3. Place Explosive Barrels
        barrel_positions = floor_positions[6:10]
        for b_pos in barrel_positions:
            barrel = ecs.create_entity(name="Explosive Red Barrel", tags={"explosive", "container"})
            ecs.add_component(barrel.id, Position(b_pos))
            ecs.add_component(barrel.id, Renderable(glyph="O", color="red", name="Explosive Barrel", render_order=5))
            ecs.add_component(barrel.id, Physics(weight=25.0, fragile=True, explosive=True, explosion_radius=2, explosion_damage=40))
            ecs.add_component(barrel.id, Material(material_type=MaterialType.WOOD, flammability=0.8))
            ecs.add_component(barrel.id, Flammable(fuel=15, ignition_temp=120))
            grid.add_item(barrel.id, b_pos)

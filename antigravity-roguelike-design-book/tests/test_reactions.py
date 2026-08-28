"""
Integration tests for multi-system emergent cascades.
"""

import unittest
from pyrogue_emergent.core.math2d import Vec2
from pyrogue_emergent.core.event_bus import EventBus
from pyrogue_emergent.world.grid import LayeredGrid, FluidType, TileType
from pyrogue_emergent.ecs.entity import EntityManager
from pyrogue_emergent.ecs.components import (
    Position, Physics, LiquidContainer, CombatStats, Flammable
)
from pyrogue_emergent.mechanics.affordances import AffordanceSystem, ActionEvent
from pyrogue_emergent.mechanics.status_effects import StatusEffectSystem, StatusType


class TestEmergentReactions(unittest.TestCase):
    def setUp(self) -> None:
        self.grid = LayeredGrid(width=15, height=15)
        self.ecs = EntityManager()
        self.bus = EventBus()
        self.affordances = AffordanceSystem(self.ecs, self.grid, self.bus)
        self.statuses = StatusEffectSystem(self.ecs, self.grid)

    def test_shatter_potion_and_ignite_cascade(self) -> None:
        target_pos = Vec2(5, 5)

        # Set tile on fire
        target_cell = self.grid.get_cell(target_pos)
        target_cell.fire_intensity = 50

        # Create fragile oil potion
        potion = self.ecs.create_entity(name="Oil Potion")
        self.ecs.add_component(potion.id, Physics(fragile=True))
        self.ecs.add_component(potion.id, LiquidContainer(capacity=50, fluid_type=FluidType.OIL, volume=50))

        # Throw potion onto burning tile
        throw_event = ActionEvent(
            actor_id=1,
            verb="throw",
            target_pos=target_pos,
            data={"item_id": potion.id}
        )
        self.bus.dispatch_full_pipeline(throw_event)
        self.bus.flush_cascades()

        # The potion should be shattered/destroyed
        self.assertIsNone(self.ecs.get_entity(potion.id))
        # The tile should now have higher fire intensity and fuel from oil ignition
        self.assertGreater(target_cell.fire_intensity, 50)
        self.assertGreater(target_cell.fire_fuel, 0)

    def test_electrical_conduction_across_water_puddle(self) -> None:
        # Create 3-tile puddle of water
        p1 = Vec2(3, 3)
        p2 = Vec2(3, 4)
        p3 = Vec2(3, 5)

        for p in (p1, p2, p3):
            cell = self.grid.get_cell(p)
            cell.fluid_type = FluidType.WATER
            cell.fluid_volume = 40

        # Place actor at far end of puddle (p3)
        actor = self.ecs.create_entity(name="Unlucky Goblin")
        self.ecs.add_component(actor.id, Position(p3))
        stats = CombatStats(hp=30, max_hp=30)
        self.ecs.add_component(actor.id, stats)
        self.grid.place_actor(actor.id, p3)

        # Zap electrical spark at p1
        shock_event = ActionEvent(
            actor_id=0,
            verb="electrify",
            target_pos=p1,
            data={"shock_power": 18}
        )
        self.bus.dispatch_full_pipeline(shock_event)

        # Actor at p3 should have taken damage via conduction
        self.assertEqual(stats.hp, 12)

    def test_compound_status_wet_and_shock_stuns(self) -> None:
        actor = self.ecs.create_entity(name="Target")
        self.ecs.add_component(actor.id, CombatStats(hp=40, max_hp=40))

        # Apply wet then shocked
        self.statuses.apply_status(actor.id, StatusType.WET, duration=5)
        self.statuses.apply_status(actor.id, StatusType.SHOCKED, duration=3)

        # Status container should now contain STUNNED
        container = self.statuses.ecs.get_component(actor.id, self.statuses.ecs.get_component(actor.id, type(self.statuses.ecs.get_component(actor.id, self.statuses.ecs.get_component(actor.id, None)))))
        from pyrogue_emergent.mechanics.status_effects import StatusContainer
        c = self.ecs.get_component(actor.id, StatusContainer)
        self.assertIsNotNone(c)
        self.assertIn(StatusType.STUNNED, c.statuses)


if __name__ == "__main__":
    unittest.main()

"""
Interactive / Headless Demo showcasing systemic emergence in pyrogue_emergent.
"""

from __future__ import annotations
import random
import sys
import os

# Ensure src is in sys.path
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "src")))

from pyrogue_emergent.core.math2d import Vec2
from pyrogue_emergent.core.event_bus import EventBus
from pyrogue_emergent.world.grid import LayeredGrid, TileType, FluidType
from pyrogue_emergent.world.cellular import CellularSimulator
from pyrogue_emergent.world.fov import SymmetricShadowcasting
from pyrogue_emergent.ecs.entity import EntityManager
from pyrogue_emergent.ecs.components import Position, Renderable, CombatStats, Faction
from pyrogue_emergent.mechanics.affordances import AffordanceSystem, ActionEvent
from pyrogue_emergent.mechanics.status_effects import StatusEffectSystem, StatusType
from pyrogue_emergent.procgen.cellular_cave import CellularCaveGenerator
from pyrogue_emergent.procgen.tactical_features import TacticalFeaturePlacer
from pyrogue_emergent.procgen.ecosystem_populator import EcosystemPopulator
from pyrogue_emergent.ui.terminal import TerminalRenderer


def run_emergence_showcase() -> None:
    print("=" * 60)
    print("  PYROGUE-EMERGENT: SYSTEMIC ROGUELIKE SIMULATION DEMO")
    print("=" * 60)

    # 1. Initialize Engine Components
    grid = LayeredGrid(width=30, height=12)
    ecs = EntityManager()
    bus = EventBus()
    sim = CellularSimulator(grid)
    affordances = AffordanceSystem(ecs, grid, bus)
    statuses = StatusEffectSystem(ecs, grid)
    logs: list[str] = []

    # 2. Generate Map
    rng = random.Random(1337)
    CellularCaveGenerator.generate(grid, iterations=3, rng=rng)
    TacticalFeaturePlacer.populate(grid, ecs, rng=rng)

    # 3. Spawn Entities
    player_id = EcosystemPopulator.spawn_player(grid, ecs, Vec2(5, 5))
    goblin_id = EcosystemPopulator.spawn_goblin(grid, ecs, Vec2(10, 5))
    potion_id = EcosystemPopulator.spawn_oil_potion(grid, ecs, Vec2(5, 5))

    logs.append("Spawned Player, Goblin Scout, and Oil Potion.")

    # 4. Compute FOV
    def is_blocking(p: Vec2) -> bool:
        if not grid.in_bounds(p):
            return True
        return grid.get_cell(p).blocks_vision

    visible = SymmetricShadowcasting.compute_fov(Vec2(5, 5), max_radius=10, is_blocking=is_blocking)

    print("\n[STEP 0] Initial State:")
    print(TerminalRenderer.render_map(grid, ecs, visible, logs))

    # 5. Emergent Action: Throw Oil Potion near goblin (Vec2(9, 5))
    print("\n" + "-" * 60)
    print(">>> ACTION: Player throws Potion of Lamp Oil at (9, 5) near Goblin...")
    throw_event = ActionEvent(
        actor_id=player_id,
        verb="throw",
        target_pos=Vec2(9, 5),
        data={"item_id": potion_id}
    )
    bus.dispatch_full_pipeline(throw_event)
    bus.flush_cascades()
    if throw_event.message:
        logs.append(throw_event.message)

    # Apply Oiled status to Goblin
    logs.extend(statuses.apply_status(goblin_id, StatusType.OILED, duration=10))

    visible = SymmetricShadowcasting.compute_fov(Vec2(5, 5), max_radius=10, is_blocking=is_blocking)
    print(TerminalRenderer.render_map(grid, ecs, visible, logs))

    # 6. Emergent Action: Ignite Oil Puddle with Torch / Fire Spell
    print("\n" + "-" * 60)
    print(">>> ACTION: Player casts Spark / Flame at (9, 5)...")
    ignite_event = ActionEvent(
        actor_id=player_id,
        verb="ignite",
        target_pos=Vec2(9, 5),
        target_id=goblin_id
    )
    bus.dispatch_full_pipeline(ignite_event)
    bus.flush_cascades()
    if ignite_event.message:
        logs.append(ignite_event.message)

    # Apply Burning status (escalates to Inferno because of Oiled!)
    logs.extend(statuses.apply_status(goblin_id, StatusType.BURNING, duration=5, intensity=2))

    # 7. Advance Cellular Simulation (Fire spreads, smoke billows)
    print("\n" + "-" * 60)
    print(">>> SIMULATION TICK: Advancing 2 Cellular Automata Turns...")
    for tick in range(2):
        logs.extend(sim.step())
        logs.extend(statuses.tick_entity(goblin_id))

    visible = SymmetricShadowcasting.compute_fov(Vec2(5, 5), max_radius=10, is_blocking=is_blocking)
    print(TerminalRenderer.render_map(grid, ecs, visible, logs))

    print("\n" + "=" * 60)
    print("  SIMULATION DEMO COMPLETED SUCCESSFULLY")
    print("=" * 60)


if __name__ == "__main__":
    run_emergence_showcase()

"""
Spawns actors, items, and ecological factions into the generated dungeon.
"""

from __future__ import annotations
import random
from pyrogue_emergent.core.math2d import Vec2
from pyrogue_emergent.world.grid import LayeredGrid, TileType, FluidType
from pyrogue_emergent.ecs.entity import EntityManager, Entity
from pyrogue_emergent.ecs.components import (
    Position, Renderable, CombatStats, Faction, SensoryProfile,
    Physics, LiquidContainer, Flammable, Material, MaterialType
)


class EcosystemPopulator:
    """
    Spawns actors and items into appropriate locations in the dungeon.
    """
    @staticmethod
    def spawn_player(grid: LayeredGrid, ecs: EntityManager, pos: Vec2) -> int:
        player = ecs.create_entity(name="Player", tags={"actor", "player"})
        ecs.add_component(player.id, Position(pos))
        ecs.add_component(player.id, Renderable(glyph="@", color="yellow", name="Player", render_order=10))
        ecs.add_component(player.id, CombatStats(hp=50, max_hp=50, attack=10, defense=3))
        ecs.add_component(player.id, Faction("player"))
        ecs.add_component(player.id, SensoryProfile(vision_radius=8))
        ecs.add_component(player.id, Material(material_type=MaterialType.FLESH))
        grid.place_actor(player.id, pos)
        return player.id

    @staticmethod
    def spawn_goblin(grid: LayeredGrid, ecs: EntityManager, pos: Vec2) -> int:
        goblin = ecs.create_entity(name="Goblin Scout", tags={"actor", "goblin"})
        ecs.add_component(goblin.id, Position(pos))
        ecs.add_component(goblin.id, Renderable(glyph="g", color="green", name="Goblin", render_order=10))
        ecs.add_component(goblin.id, CombatStats(hp=20, max_hp=20, attack=6, defense=1))
        ecs.add_component(goblin.id, Faction("goblin"))
        ecs.add_component(goblin.id, SensoryProfile(vision_radius=6))
        ecs.add_component(goblin.id, Material(material_type=MaterialType.FLESH))
        grid.place_actor(goblin.id, pos)
        return goblin.id

    @staticmethod
    def spawn_oil_potion(grid: LayeredGrid, ecs: EntityManager, pos: Vec2) -> int:
        potion = ecs.create_entity(name="Potion of Lamp Oil", tags={"item", "potion", "throwable"})
        ecs.add_component(potion.id, Position(pos))
        ecs.add_component(potion.id, Renderable(glyph="!", color="brown", name="Oil Potion", render_order=5))
        ecs.add_component(potion.id, Physics(weight=0.5, fragile=True))
        ecs.add_component(potion.id, LiquidContainer(capacity=50, fluid_type=FluidType.OIL, volume=50))
        grid.add_item(potion.id, pos)
        return potion.id

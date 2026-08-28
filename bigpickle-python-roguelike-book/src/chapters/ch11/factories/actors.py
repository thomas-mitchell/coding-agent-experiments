"""Actor entity factories."""
from __future__ import annotations
import random
from typing import TYPE_CHECKING
from components import Position, Renderable, Name, Fighter, XP, AI, AIKind

if TYPE_CHECKING:
    import tcod.ecs


def _create_actor(
    registry: tcod.ecs.Registry,
    x: int, y: int,
    char: str, fg: tuple[int, int, int],
    name: str,
    hp: int, power: int, defense: int,
    xp_reward: int = 0,
    tags: frozenset[str] = frozenset({"enemy", "blocks_movement"}),
) -> tcod.ecs.Entity:
    entity = registry.new_entity()
    entity.components |= {
        Position: Position(x=x, y=y),
        Renderable: Renderable(char=char, fg=fg),
        Name: Name(name=name),
        Fighter: Fighter(hp=hp, max_hp=hp, power=power, defense=defense),
        XP: XP(current=0, level=1, xp_to_next=100),
        AI: AI(kind=AIKind.HOSTILE),
    }
    entity.tags |= tags
    return entity


def create_kobold(registry: tcod.ecs.Registry, x: int, y: int) -> tcod.ecs.Entity:
    return _create_actor(registry, x, y, "k", (0, 127, 0), "Kobold", hp=8, power=3, defense=0, xp_reward=10)


def create_orc(registry: tcod.ecs.Registry, x: int, y: int) -> tcod.ecs.Entity:
    return _create_actor(registry, x, y, "o", (63, 127, 63), "Orc", hp=15, power=5, defense=2, xp_reward=25)


def create_troll(registry: tcod.ecs.Registry, x: int, y: int) -> tcod.ecs.Entity:
    return _create_actor(registry, x, y, "T", (0, 127, 0), "Troll", hp=30, power=8, defense=4, xp_reward=50)


def create_goblin(registry: tcod.ecs.Registry, x: int, y: int) -> tcod.ecs.Entity:
    return _create_actor(registry, x, y, "g", (63, 191, 63), "Goblin", hp=6, power=2, defense=0, xp_reward=8)


def create_skeleton(registry: tcod.ecs.Registry, x: int, y: int) -> tcod.ecs.Entity:
    return _create_actor(registry, x, y, "s", (191, 191, 191), "Skeleton", hp=12, power=4, defense=1, xp_reward=20)


ENEMY_FACTORIES = [create_kobold, create_goblin, create_skeleton, create_orc, create_troll]


def spawn_random_enemy(registry: tcod.ecs.Registry, x: int, y: int, dungeon_level: int = 1) -> tcod.ecs.Entity:
    """Spawn a random enemy appropriate for the dungeon level."""
    # Weight toward harder enemies on deeper levels
    max_index = min(dungeon_level, len(ENEMY_FACTORIES) - 1)
    factory = random.choice(ENEMY_FACTORIES[:max_index + 1])
    return factory(registry, x, y)

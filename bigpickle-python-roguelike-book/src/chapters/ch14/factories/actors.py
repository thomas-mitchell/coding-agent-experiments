"""Factory functions for creating actors (player and enemies)."""
from __future__ import annotations

import random
from typing import TYPE_CHECKING

from components import (
    AI,
    AIKind,
    Fighter,
    Inventory,
    Name,
    Position,
    Renderable,
    XP,
)

if TYPE_CHECKING:
    import tcod.ecs
    from game_map import GameMap

# (char, fg, name, hp, power, defense, xp_value, ai_kind)
ENEMY_TEMPLATES = [
    ("r", (200, 120, 120), "Rat", 4, 2, 0, 10, AIKind.HOSTILE),   # fragile -> flees
    ("k", (255, 0, 0), "Kobold", 8, 3, 0, 20, AIKind.HOSTILE),
    ("o", (180, 0, 0), "Orc", 15, 5, 2, 40, AIKind.HOSTILE),
    ("T", (0, 128, 0), "Troll", 25, 8, 4, 80, AIKind.HOSTILE),
    ("G", (120, 200, 255), "Guardian", 30, 6, 6, 60, AIKind.STATIONARY),
]


def create_player(registry: tcod.ecs.Registry, x: int, y: int) -> tcod.ecs.Entity:
    """Spawn the player entity."""
    player = registry.new_entity()
    player.components |= {
        Position: Position(x=x, y=y),
        Renderable: Renderable(char="@", fg=(255, 255, 255), render_order=10),
        Name: Name(name="Player"),
        Fighter: Fighter(hp=30, max_hp=30, power=5, defense=2),
        XP: XP(current=0, level=1, xp_to_next=100, xp_value=0),
        Inventory: Inventory(items=[], capacity=10),
    }
    player.tags.add("player")
    return player


def place_enemies(
    registry: tcod.ecs.Registry,
    dungeon: GameMap,
    skip_room: int = 0,
) -> None:
    """Place 2-4 enemies in each room except the player's starting room."""
    for i, room in enumerate(dungeon.rooms):
        if i == skip_room:
            continue
        num_enemies = random.randint(2, 4)
        placed = 0
        attempts = 0
        while placed < num_enemies and attempts < 50:
            attempts += 1
            x = random.randint(room.x + 1, room.x + room.w - 2)
            y = random.randint(room.y + 1, room.y + room.h - 2)
            if _is_occupied(registry, x, y):
                continue
            (
                char,
                fg,
                name,
                hp,
                power,
                defense,
                xp_value,
                ai_kind,
            ) = random.choice(ENEMY_TEMPLATES)
            entity = registry.new_entity()
            entity.components |= {
                Position: Position(x=x, y=y),
                Renderable: Renderable(char=char, fg=fg),
                Name: Name(name=name),
                Fighter: Fighter(hp=hp, max_hp=hp, power=power, defense=defense),
                XP: XP(xp_value=xp_value),
                AI: AI(kind=ai_kind),
            }
            entity.tags.add("enemy")
            placed += 1


def _is_occupied(registry: tcod.ecs.Registry, x: int, y: int) -> bool:
    for entity in registry.Q.all_of(components=[Position]):
        pos = entity.components[Position]
        if pos.x == x and pos.y == y:
            return True
    return False

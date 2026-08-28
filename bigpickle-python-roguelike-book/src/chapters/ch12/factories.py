"""Factory functions for creating game entities."""
from __future__ import annotations

import random
from typing import TYPE_CHECKING

from components import Position, Renderable, Name, Fighter, XP, AI, AIKind

if TYPE_CHECKING:
    import tcod.ecs
    from game_map import GameMap


ENEMY_TEMPLATES = [
    ("k", (255, 0, 0), "Kobold", 8, 3, 0),
    ("o", (180, 0, 0), "Orc", 15, 5, 2),
    ("T", (0, 128, 0), "Troll", 25, 8, 4),
]


def create_player(registry: tcod.ecs.Registry, x: int, y: int) -> tcod.ecs.Entity:
    """Spawn the player entity."""
    player = registry.new_entity()
    player.components |= {
        Position: Position(x=x, y=y),
        Renderable: Renderable(char="@", fg=(255, 255, 255)),
        Name: Name(name="Player"),
        Fighter: Fighter(hp=30, max_hp=30, power=5, defense=2),
        XP: XP(),
    }
    player.tags.add("player")
    return player


def place_enemies(
    registry: tcod.ecs.Registry,
    dungeon: GameMap,
    skip_room: int = 0,
) -> None:
    """Place 2-4 enemies in each room except the one the player starts in."""
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
            # Check that no entity already occupies this tile.
            occupied = False
            for ent, pos in registry.Q[Position]:
                if pos.x == x and pos.y == y:
                    occupied = True
                    break
            if occupied:
                continue
            char, fg, name, hp, power, defense = random.choice(ENEMY_TEMPLATES)
            entity = registry.new_entity()
            entity.components |= {
                Position: Position(x=x, y=y),
                Renderable: Renderable(char=char, fg=fg),
                Name: Name(name=name),
                Fighter: Fighter(hp=hp, max_hp=hp, power=power, defense=defense),
                AI: AI(kind=AIKind.HOSTILE),
            }
            entity.tags.add("enemy")
            placed += 1

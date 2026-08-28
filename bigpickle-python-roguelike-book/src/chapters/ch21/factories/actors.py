"""Factory functions for creating actors (player and enemies), scaled by depth."""
from __future__ import annotations

import random
from typing import TYPE_CHECKING

from components import (
    AI,
    AIKind,
    Equipment,
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
# base stats; the factory scales them up as the player descends.
ENEMY_TEMPLATES = {
    "rat": ("r", (200, 120, 120), "Rat", 4, 2, 0, 10, AIKind.HOSTILE),
    "kobold": ("k", (255, 0, 0), "Kobold", 8, 3, 0, 20, AIKind.HOSTILE),
    "skeleton": ("s", (230, 230, 230), "Skeleton", 12, 4, 1, 30, AIKind.HOSTILE),
    "orc": ("o", (180, 0, 0), "Orc", 15, 5, 2, 40, AIKind.HOSTILE),
    "troll": ("T", (0, 128, 0), "Troll", 25, 8, 4, 80, AIKind.HOSTILE),
    "ogre": ("O", (128, 64, 0), "Ogre", 30, 9, 3, 100, AIKind.HOSTILE),
    "guardian": ("G", (120, 200, 255), "Guardian", 30, 6, 6, 60, AIKind.STATIONARY),
}

# Enemy types available at each dungeon level. Duplicate entries bias the
# random choice so weak foes dominate the early floors.
ENEMY_SPAWN_TABLE: dict[int, list[str]] = {
    1: ["rat", "rat", "kobold"],
    2: ["rat", "kobold", "skeleton", "kobold"],
    3: ["kobold", "kobold", "skeleton", "orc"],
    4: ["kobold", "skeleton", "orc", "orc"],
    5: ["orc", "orc", "troll", "skeleton"],
    6: ["orc", "troll", "troll", "ogre"],
    7: ["troll", "troll", "ogre", "ogre"],
    8: ["troll", "ogre", "ogre", "guardian"],
}


def get_enemy_pool(dungeon_level: int) -> list[str]:
    """Return the enemy template names available on a given floor."""
    if dungeon_level in ENEMY_SPAWN_TABLE:
        return list(ENEMY_SPAWN_TABLE[dungeon_level])
    max_level = max(ENEMY_SPAWN_TABLE.keys())
    return list(ENEMY_SPAWN_TABLE[max_level])


def create_player(registry: "tcod.ecs.Registry", x: int, y: int) -> "tcod.ecs.Entity":
    """Spawn the player entity with equipment slots and an XP ledger."""
    player = registry.new_entity()
    player.components |= {
        Position: Position(x=x, y=y),
        Renderable: Renderable(char="@", fg=(255, 255, 255), render_order=10),
        Name: Name(name="Player"),
        Fighter: Fighter(hp=30, max_hp=30, power=5, defense=2),
        XP: XP(current=0, level=1, xp_to_next=100, xp_value=0, level_ups_pending=0),
        Inventory: Inventory(items=[], capacity=10),
        Equipment: Equipment(),
    }
    player.tags.add("player")
    return player


def create_enemy(
    registry: "tcod.ecs.Registry",
    x: int,
    y: int,
    template_name: str,
    dungeon_level: int = 1,
) -> "tcod.ecs.Entity":
    """Spawn a single enemy from a template, scaled by dungeon depth."""
    char, fg, name, hp, power, defense, xp_value, ai_kind = ENEMY_TEMPLATES[
        template_name
    ]

    # Scale stats with dungeon level.
    level_bonus = dungeon_level - 1
    hp += level_bonus * 2
    power += level_bonus
    defense += level_bonus // 2
    xp_value += level_bonus * 5

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
    entity.tags.add("blocks_movement")
    return entity


def place_enemies(
    registry: "tcod.ecs.Registry",
    dungeon: "GameMap",
    dungeon_level: int = 1,
    skip_room: int = 0,
) -> None:
    """Place enemies in each room except the player's starting room.

    The number of enemies per room grows with the dungeon level, and the
    selection of enemy types is drawn from the spawn table for that depth.
    """
    pool = get_enemy_pool(dungeon_level)

    for i, room in enumerate(dungeon.rooms):
        if i == skip_room:
            continue
        # Enemy counts scale with depth: a few early on, more later.
        num_enemies = random.randint(1 + dungeon_level // 2, 2 + dungeon_level)
        placed = 0
        attempts = 0
        while placed < num_enemies and attempts < 80:
            attempts += 1
            x = random.randint(room.x + 1, room.x + room.w - 2)
            y = random.randint(room.y + 1, room.y + room.h - 2)
            if _is_occupied(registry, x, y):
                continue
            create_enemy(
                registry, x, y, random.choice(pool), dungeon_level=dungeon_level
            )
            placed += 1


def _is_occupied(registry: "tcod.ecs.Registry", x: int, y: int) -> bool:
    for entity in registry.Q.all_of(components=[Position]):
        pos = entity.components[Position]
        if pos.x == x and pos.y == y:
            return True
    return False

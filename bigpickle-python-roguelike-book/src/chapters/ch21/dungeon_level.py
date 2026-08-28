"""Dungeon level management: descending the staircase and scaling difficulty.

The player entity persists between levels; its position and stats survive.
Everything tied to a single floor (enemies, items, the staircase) is cleared
and regenerated, harder, each time the player descends.
"""
from __future__ import annotations

from typing import TYPE_CHECKING

import tcod.ecs

from components import Name, Position, Stairs, Renderable
from color import MAGENTA

if TYPE_CHECKING:
    from tcod.ecs import Entity, Registry

    from game_map import GameMap


def create_stairs(registry: Registry, x: int, y: int) -> Entity:
    """Spawn a downwards staircase entity on the given tile.

    The stairs are a minimal entity: a position, a renderable (``>``), a name,
    and the ``Stairs`` component the game checks when the player tries to
    descend. No combat stats, no AI, no inventory.
    """
    entity = registry.new_entity()
    entity.components |= {
        Position: Position(x=x, y=y),
        Renderable: Renderable(char=">", fg=MAGENTA, render_order=0),
        Name: Name(name="Stairs"),
        Stairs: Stairs(),
    }
    entity.tags.add("staircase")
    return entity


# Floor-specific tags that are destroyed when the player moves to a new level.
_FLOOR_TAGS = ("enemy", "item", "staircase")


def clear_floor(registry: Registry) -> None:
    """Remove every entity that belongs to the current floor.

    tcod-ecs has no ``Registry.clear_entity``; clearing an entity's components
    and tags removes it from every query that would otherwise return it.
    """
    for tag in _FLOOR_TAGS:
        for entity in list(registry.Q.all_of(tags=[tag])):
            entity.clear()


def adjust_difficulty(
    enemy_stats: dict,
    dungeon_level: int,
) -> dict:
    """Return a copy of ``enemy_stats`` scaled for the given depth.

    This is a lightweight helper exposing the difficulty curve used by the
    factured actors: HP gains +2 per level beyond the first, power +1, and
    defense +1 every two levels.
    """
    level_bonus = dungeon_level - 1
    return {
        "hp": enemy_stats["hp"] + level_bonus * 2,
        "power": enemy_stats["power"] + level_bonus,
        "defense": enemy_stats["defense"] + level_bonus // 2,
        "xp": enemy_stats["xp"] + level_bonus * 5,
    }


def number_of_enemies(dungeon_level: int) -> int:
    """The multiplier used when spacing enemies, growing with depth."""
    return 2 + dungeon_level


def descend_level(
    registry: Registry,
    game_map: "GameMap",
    player: Entity,
    dungeon_level: int,
    log,
) -> tuple["GameMap", int]:
    """Generate and populate the next dungeon floor.

    Steps:
      1. Lift the player off the map.
      2. Destroy all floor-specific entities (enemies, items, stairs).
      3. Generate a fresh dungeon.
      4. Reposition the player in the first room.
      5. Spawn enemies and items scaled to the new depth.
      6. Drop the staircase in the last room.

    Returns the new ``(game_map, dungeon_level)``.
    """
    from factories import place_enemies, place_items
    from procgen import generate_dungeon, player_start, stairs_position

    new_level = dungeon_level + 1

    # Clear the current floor's temporary entities.
    clear_floor(registry)

    game_map = generate_dungeon(
        max_rooms=30,
        room_min_size=6,
        room_max_size=10,
        map_width=game_map.width,
        map_height=game_map.height,
    )

    # Reposition the player in the first (safe) room.
    sx, sy = player_start(game_map)
    player.components[Position].x = sx
    player.components[Position].y = sy

    # Recompute the player's field of view elsewhere; FOV is computed by caller.
    from combat import compute_fov

    compute_fov(game_map, sx, sy)

    log.add(f"You descend to floor {new_level}.", MAGENTA)

    # Populate the new floor, scaled to its depth.
    place_enemies(registry, game_map, dungeon_level=new_level, skip_room=0)
    place_items(registry, game_map, dungeon_level=new_level, skip_room=0)

    # Drop the staircase in the last room so the player can go deeper still.
    px, py = stairs_position(game_map)
    create_stairs(registry, px, py)

    return game_map, new_level

"""Procedural dungeon generation using BSP, now with factory-based placement."""
from __future__ import annotations

import random
import tcod.bsp
import tcod.ecs

from game_map import GameMap, Room
from tile_types import FLOOR, WALL
from factories.actors import spawn_random_enemy
from factories.items import (
    create_health_potion,
    create_scroll_fireball,
    create_scroll_lightning,
    create_sword,
    create_shield,
)

ITEM_FACTORIES = [
    create_health_potion,
    create_health_potion,
    create_scroll_fireball,
    create_scroll_lightning,
    create_sword,
    create_shield,
]


def generate_dungeon(
    max_rooms: int,
    room_min_size: int,
    room_max_size: int,
    map_width: int,
    map_height: int,
    registry: tcod.ecs.Registry,
    dungeon_level: int = 1,
) -> GameMap:
    """Generate a dungeon using BSP partitioning."""
    dungeon = GameMap(map_width, map_height)

    # Create BSP tree
    root = tcod.bsp.BSP(x=1, y=1, width=map_width - 2, height=map_height - 2)
    root.split_recursive(
        depth=5,
        min_width=room_min_size + 2,
        min_height=room_min_size + 2,
        max_ratio=1.5,
    )

    # Create rooms in leaf nodes
    for node in root.leaves:
        room_w = random.randint(room_min_size, min(room_max_size, node.width - 1))
        room_h = random.randint(room_min_size, min(room_max_size, node.height - 1))
        room_x = random.randint(node.x, node.x + node.width - room_w - 1)
        room_y = random.randint(node.y, node.y + node.height - room_h - 1)

        # Carve room
        dungeon.tiles[room_y:room_y + room_h, room_x:room_x + room_w] = FLOOR

        # Store room for corridor generation
        dungeon.rooms.append(Room(x=room_x, y=room_y, w=room_w, h=room_h))

    # Connect rooms with corridors
    for i in range(len(dungeon.rooms) - 1):
        r1 = dungeon.rooms[i]
        r2 = dungeon.rooms[i + 1]
        cx1, cy1 = r1.center
        cx2, cy2 = r2.center

        # Horizontal then vertical corridor
        if random.random() < 0.5:
            _carve_h_tunnel(dungeon, cx1, cx2, cy1)
            _carve_v_tunnel(dungeon, cy1, cy2, cx2)
        else:
            _carve_v_tunnel(dungeon, cy1, cy2, cx1)
            _carve_h_tunnel(dungeon, cx1, cx2, cy2)

    return dungeon


def place_entities(
    registry: tcod.ecs.Registry,
    dungeon: GameMap,
    dungeon_level: int = 1,
    skip_room: int = 0,
) -> None:
    """Place enemies and items in every room except skip_room."""
    for i, room in enumerate(dungeon.rooms):
        if i == skip_room:
            continue

        _place_enemies(registry, dungeon, room, dungeon_level)
        _place_items(registry, dungeon, room)


def _is_occupied(registry: tcod.ecs.Registry, x: int, y: int) -> bool:
    from components import Position

    for _ent, pos in registry.Q[Position]:
        if pos.x == x and pos.y == y:
            return True
    return False


def _random_floor(
    registry: tcod.ecs.Registry, dungeon: GameMap, room: Room
) -> tuple[int, int] | None:
    """Return a random walkable tile in the room that has no entity on it, or None."""
    for _ in range(50):
        x = random.randint(room.x + 1, room.x + room.w - 2)
        y = random.randint(room.y + 1, room.y + room.h - 2)
        if dungeon.is_walkable(x, y) and not _is_occupied(registry, x, y):
            return x, y
    return None


def _place_enemies(
    registry: tcod.ecs.Registry,
    dungeon: GameMap,
    room: Room,
    dungeon_level: int,
) -> None:
    num_enemies = random.randint(2, 4)
    for _ in range(num_enemies):
        pos = _random_floor(registry, dungeon, room)
        if pos is not None:
            spawn_random_enemy(registry, pos[0], pos[1], dungeon_level)


def _place_items(
    registry: tcod.ecs.Registry,
    dungeon: GameMap,
    room: Room,
) -> None:
    num_items = random.randint(0, 2)
    for _ in range(num_items):
        pos = _random_floor(registry, dungeon, room)
        if pos is not None:
            factory = random.choice(ITEM_FACTORIES)
            factory(registry, pos[0], pos[1])


def _carve_h_tunnel(dungeon: GameMap, x1: int, x2: int, y: int) -> None:
    for x in range(min(x1, x2), max(x1, x2) + 1):
        if dungeon.in_bounds(x, y):
            dungeon.tiles[y, x] = FLOOR


def _carve_v_tunnel(dungeon: GameMap, y1: int, y2: int, x: int) -> None:
    for y in range(min(y1, y2), max(y1, y2) + 1):
        if dungeon.in_bounds(x, y):
            dungeon.tiles[y, x] = FLOOR

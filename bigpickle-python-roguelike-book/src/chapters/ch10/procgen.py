"""Procedural dungeon generation using BSP."""
from __future__ import annotations

import random
import tcod.bsp

from game_map import GameMap
from tile_types import FLOOR


def generate_dungeon(
    max_rooms: int,
    room_min_size: int,
    room_max_size: int,
    map_width: int,
    map_height: int,
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
    rooms: list[tuple[int, int, int, int]] = []
    for node in root.leaves:
        room_w = random.randint(room_min_size, min(room_max_size, node.width - 1))
        room_h = random.randint(room_min_size, min(room_max_size, node.height - 1))
        room_x = random.randint(node.x, node.x + node.width - room_w - 1)
        room_y = random.randint(node.y, node.y + node.height - room_h - 1)

        # Carve room
        dungeon.tiles[room_y:room_y + room_h, room_x:room_x + room_w] = FLOOR

        rooms.append((room_x, room_y, room_w, room_h))

    # Connect rooms with corridors
    for i in range(len(rooms) - 1):
        x1, y1, w1, h1 = rooms[i]
        x2, y2, w2, h2 = rooms[i + 1]
        cx1, cy1 = x1 + w1 // 2, y1 + h1 // 2
        cx2, cy2 = x2 + w2 // 2, y2 + h2 // 2

        # Horizontal then vertical corridor
        if random.random() < 0.5:
            _carve_h_tunnel(dungeon, cx1, cx2, cy1)
            _carve_v_tunnel(dungeon, cy1, cy2, cx2)
        else:
            _carve_v_tunnel(dungeon, cy1, cy2, cx1)
            _carve_h_tunnel(dungeon, cx1, cx2, cy2)

    return dungeon, rooms


def _carve_h_tunnel(dungeon: GameMap, x1: int, x2: int, y: int) -> None:
    for x in range(min(x1, x2), max(x1, x2) + 1):
        if dungeon.in_bounds(x, y):
            dungeon.tiles[y, x] = FLOOR


def _carve_v_tunnel(dungeon: GameMap, y1: int, y2: int, x: int) -> None:
    for y in range(min(y1, y2), max(y1, y2) + 1):
        if dungeon.in_bounds(x, y):
            dungeon.tiles[y, x] = FLOOR

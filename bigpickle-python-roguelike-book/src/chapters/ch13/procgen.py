"""Procedural dungeon generation."""
from __future__ import annotations

import random

from game_map import GameMap, Room
from tile_types import FLOOR, WALL


def generate_dungeon(
    max_rooms: int,
    room_min_size: int,
    room_max_size: int,
    map_width: int,
    map_height: int,
) -> GameMap:
    """Generate a dungeon with rectangular rooms connected by L-shaped corridors."""
    dungeon = GameMap(map_width, map_height)

    for _ in range(max_rooms):
        w = random.randint(room_min_size, room_max_size)
        h = random.randint(room_min_size, room_max_size)
        x = random.randint(1, map_width - w - 1)
        y = random.randint(1, map_height - h - 1)

        new_room = Room(x=x, y=y, w=w, h=h)

        # Check for overlap with any existing room.
        if any(new_room.intersects(r) for r in dungeon.rooms):
            continue

        # Carve the room.
        dungeon.tiles[y : y + h, x : x + w] = FLOOR

        if dungeon.rooms:
            # Connect to the previous room with an L-shaped corridor.
            cx1, cy1 = dungeon.rooms[-1].center
            cx2, cy2 = new_room.center

            if random.random() < 0.5:
                _carve_h_tunnel(dungeon, cx1, cx2, cy1)
                _carve_v_tunnel(dungeon, cy1, cy2, cx2)
            else:
                _carve_v_tunnel(dungeon, cy1, cy2, cx1)
                _carve_h_tunnel(dungeon, cx1, cx2, cy2)

        dungeon.rooms.append(new_room)

    # Surround all floor tiles with walls where needed.
    _add_walls(dungeon)

    return dungeon


def _carve_h_tunnel(dungeon: GameMap, x1: int, x2: int, y: int) -> None:
    for x in range(min(x1, x2), max(x1, x2) + 1):
        if dungeon.in_bounds(x, y):
            dungeon.tiles[y, x] = FLOOR


def _carve_v_tunnel(dungeon: GameMap, y1: int, y2: int, x: int) -> None:
    for y in range(min(y1, y2), max(y1, y2) + 1):
        if dungeon.in_bounds(x, y):
            dungeon.tiles[y, x] = FLOOR


def _add_walls(dungeon: GameMap) -> None:
    """Place wall tiles around every floor tile that borders the void."""
    height, width = dungeon.tiles.shape
    for y in range(height):
        for x in range(width):
            if dungeon.tiles[y, x]["walkable"]:
                # Check 8 neighbours; any void neighbour gets a wall.
                for dy in (-1, 0, 1):
                    for dx in (-1, 0, 1):
                        ny, nx = y + dy, x + dx
                        if dungeon.in_bounds(nx, ny) and not dungeon.tiles[ny, nx]["walkable"]:
                            # Only place wall if it's void (not already a floor).
                            if not dungeon.tiles[ny, nx]["walkable"]:
                                dungeon.tiles[ny, nx] = WALL

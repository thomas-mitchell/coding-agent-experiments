from __future__ import annotations

import random
from typing import TYPE_CHECKING

import numpy as np

from . import tile_types
from .game_map import GameMap

if TYPE_CHECKING:
    from tcod.ecs import World


def place_entities(
    game_map: GameMap,
    world: World,
    room_x1: int,
    room_y1: int,
    room_x2: int,
    room_y2: int,
    floor: int,
    max_monsters: int,
    max_items: int,
) -> None:
    from .factories.actors import create_orc, create_troll
    from .factories.items import (
        create_confusion_scroll,
        create_fireball_scroll,
        create_health_potion,
        create_lightning_scroll,
        create_shield,
        create_sword,
    )

    number_of_monsters = random.randint(0, min(max_monsters, (room_x2 - room_x1) * (room_y2 - room_y1) // 6))
    number_of_items = random.randint(0, min(max_items, (room_x2 - room_x1) * (room_y2 - room_y1) // 8))

    monster_chances = {
        "orc": 80 - floor * 5,
        "troll": 20 + floor * 10,
    }
    item_chances = {
        "health_potion": 35,
        "lightning_scroll": max(10, 15 - floor * 2),
        "fireball_scroll": max(10, 15 - floor * 2),
        "confusion_scroll": max(10, 20 - floor * 2),
        "sword": max(5, 10 - floor),
        "shield": max(5, 10 - floor),
    }

    for _ in range(number_of_monsters):
        x = random.randint(room_x1, room_x2)
        y = random.randint(room_y1, room_y2)

        if not any(game_map.tiles[x, y] == tile_types.FLOOR):
            continue
        if any(world[ent, "Position"].x == x and world[ent, "Position"].y == y
               for ent in world.Q.all_of(components=[("Position",)])):
            continue

        choice = random.choices(list(monster_chances.keys()), list(monster_chances.values()))[0]
        if choice == "orc":
            create_orc(world, x, y)
        else:
            create_troll(world, x, y)

    for _ in range(number_of_items):
        x = random.randint(room_x1, room_x2)
        y = random.randint(room_y1, room_y2)

        if not any(game_map.tiles[x, y] == tile_types.FLOOR):
            continue
        if any(world[ent, "Position"].x == x and world[ent, "Position"].y == y
               for ent in world.Q.all_of(components=[("Position",)])):
            continue

        choice = random.choices(list(item_chances.keys()), list(item_chances.values()))[0]
        item_factories = {
            "health_potion": lambda: create_health_potion(world, x, y),
            "lightning_scroll": lambda: create_lightning_scroll(world, x, y),
            "fireball_scroll": lambda: create_fireball_scroll(world, x, y),
            "confusion_scroll": lambda: create_confusion_scroll(world, x, y),
            "sword": lambda: create_sword(world, x, y),
            "shield": lambda: create_shield(world, x, y),
        }
        item_factories[choice]()


class Room:
    def __init__(self, x1: int, y1: int, x2: int, y2: int) -> None:
        self.x1 = x1
        self.y1 = y1
        self.x2 = x2
        self.y2 = y2

    @property
    def center(self) -> tuple[int, int]:
        return (self.x1 + self.x2) // 2, (self.y1 + self.y2) // 2

    @property
    def inner(self) -> tuple[slice, slice]:
        return slice(self.x1 + 1, self.x2), slice(self.y1 + 1, self.y2)

    def intersects(self, other: Room) -> bool:
        return (self.x1 <= other.x2 and self.x2 >= other.x1 and
                self.y1 <= other.y2 and self.y2 >= other.y1)


def generate_dungeon(
    world: World,
    max_rooms: int,
    room_min_size: int,
    room_max_size: int,
    map_width: int,
    map_height: int,
    max_monsters_per_room: int,
    max_items_per_room: int,
    floor: int = 1,
) -> GameMap:
    game_map = GameMap(map_width, map_height)
    rooms: list[Room] = []

    for _ in range(max_rooms):
        room_width = random.randint(room_min_size, room_max_size)
        room_height = random.randint(room_min_size, room_max_size)
        x = random.randint(0, map_width - room_width - 1)
        y = random.randint(0, map_height - room_height - 1)

        new_room = Room(x, y, x + room_width, y + room_height)

        if any(new_room.intersects(existing) for existing in rooms):
            continue

        game_map.tiles[new_room.inner] = tile_types.FLOOR

        if rooms:
            prev_x, prev_y = rooms[-1].center
            cur_x, cur_y = new_room.center

            if random.randint(0, 1) == 1:
                game_map.tiles[prev_x, slice(min(prev_y, cur_y), max(prev_y, cur_y) + 1)] = tile_types.FLOOR
                game_map.tiles[slice(min(prev_x, cur_x), max(prev_x, cur_x) + 1), cur_y] = tile_types.FLOOR
            else:
                game_map.tiles[slice(min(prev_x, cur_x), max(prev_x, cur_x) + 1), cur_y] = tile_types.FLOOR
                game_map.tiles[prev_x, slice(min(prev_y, cur_y), max(prev_y, cur_y) + 1)] = tile_types.FLOOR

        place_entities(game_map, world, *new_room.inner, floor, max_monsters_per_room, max_items_per_room)
        rooms.append(new_room)

    player_pos = world[world["player"], "Position"]
    player_pos.x, player_pos.y = rooms[0].center

    return game_map

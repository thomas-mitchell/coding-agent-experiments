from __future__ import annotations

from typing import TYPE_CHECKING

from .components import AI, AIKind, Consumable, Description, Equippable, Equipment, Fighter, Inventory, Item, Name, Position, Renderable, XP
from .combat import attack
from .game_map import GameMap

if TYPE_CHECKING:
    from tcod.ecs import World


def process_ai(world: World, game_map: GameMap, player: int) -> None:
    player_pos = world[player, "Position"]

    for entity, (ai, pos, fighter) in world.Q.all_of(components=[AI, Position, Fighter]):
        if entity == player:
            continue

        if fighter.hp <= 0:
            continue

        dx = player_pos.x - pos.x
        dy = player_pos.y - pos.y
        distance = (dx ** 2 + dy ** 2) ** 0.5

        if game_map.fov[pos.x, pos.y]:
            if distance <= 1.5:
                attack(entity, player, world)
                continue

            if ai.kind == AIKind.HOSTILE:
                ai.path = _path_to_target(pos.x, pos.y, player_pos.x, player_pos.y, game_map)
                if ai.path:
                    next_x, next_y = ai.path[0]
                    if not _entity_at(next_x, next_y, world, exclude=entity):
                        pos.x, pos.y = next_x, next_y
                        ai.path = ai.path[1:]
        else:
            ai.path = []


def _path_to_target(start_x: int, start_y: int, target_x: int, target_y: int, game_map: GameMap) -> list[tuple[int, int]]:
    import heapq

    frontier: list[tuple[int, int, int]] = []
    heapq.heappush(frontier, (0, start_x, start_y))
    came_from: dict[tuple[int, int], tuple[int, int] | None] = {(start_x, start_y): None}
    cost_so_far: dict[tuple[int, int], int] = {(start_x, start_y): 0}

    while frontier:
        _, current_x, current_y = heapq.heappop(frontier)

        if current_x == target_x and current_y == target_y:
            break

        for dx, dy in [(-1, 0), (1, 0), (0, -1), (0, 1)]:
            nx, ny = current_x + dx, current_y + dy
            if not game_map.in_bounds(nx, ny):
                continue
            if not game_map.tiles[nx, ny]["walkable"]:
                continue

            new_cost = cost_so_far[(current_x, current_y)] + 1
            if (nx, ny) not in cost_so_far or new_cost < cost_so_far[(nx, ny)]:
                cost_so_far[(nx, ny)] = new_cost
                priority = new_cost + abs(target_x - nx) + abs(target_y - ny)
                heapq.heappush(frontier, (priority, nx, ny))
                came_from[(nx, ny)] = (current_x, current_y)

    if (target_x, target_y) not in came_from:
        return []

    path: list[tuple[int, int]] = []
    current = (target_x, target_y)
    while current != (start_x, start_y):
        path.append(current)
        current = came_from[current]
    path.reverse()
    return path


def _entity_at(x: int, y: int, world: World, exclude: int | None = None) -> int | None:
    for entity, pos in world.Q.all_of(components=[Position]):
        if entity == exclude:
            continue
        if pos.x == x and pos.y == y:
            return entity
    return None

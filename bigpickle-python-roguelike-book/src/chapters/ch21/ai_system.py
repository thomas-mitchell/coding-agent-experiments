"""AI system with multiple behavior types, reporting changes to the message log."""
from __future__ import annotations

import random
from typing import TYPE_CHECKING

import tcod.path
from tcod.ecs import Entity

from components import AI, AIKind, Fighter, Name, Position
from color import LIGHT_RED, PURPLE

if TYPE_CHECKING:
    from game_map import GameMap


def get_path(
    graph: tcod.path.SimpleGraph,
    start: tuple[int, int],
    goal: tuple[int, int],
) -> list[tuple[int, int]]:
    """Get path from start to goal using A* pathfinding.

    The modern tcod pathfinder uses (y, x) ordering internally, so the
    (x, y) coordinates used by the rest of the game are translated here.
    """
    pf = tcod.path.Pathfinder(graph)
    pf.add_root((start[1], start[0]))
    path = pf.path_to((goal[1], goal[0]))
    if path.size == 0:
        return []
    return [(x, y) for y, x in path]


def create_pathfinder(game_map: "GameMap") -> tcod.path.SimpleGraph:
    """Create a pathfinder graph from the game map."""
    import numpy as np

    # A cost of zero marks a tile as impassable; walkable tiles cost 1.
    cost = np.where(game_map.tiles["walkable"], 1, 0).astype(np.int32)
    return tcod.path.SimpleGraph(cost=cost, cardinal=2, diagonal=3, greed=1)


def process_ai_turns(
    registry,
    game_map: "GameMap",
    player: Entity,
    graph: tcod.path.SimpleGraph,
    log,
) -> None:
    """Process AI turns for all entities with AI component."""
    player_pos = player.components[Position]

    for entity, pos, fighter, ai in registry.Q[Entity, Position, Fighter, AI]:
        if entity is player:
            continue
        if fighter.hp <= 0:
            continue

        # Check the flee condition: a hurt hostile monster runs away.
        if (
            ai.kind == AIKind.HOSTILE
            and fighter.hp < fighter.max_hp * ai.flee_threshold
        ):
            ai.previous_kind = ai.kind
            ai.kind = AIKind.FLEEING
            log.add(
                f"The {_name(entity)} flees in terror!",
                LIGHT_RED,
            )

        # Process based on AI type.
        if ai.kind == AIKind.HOSTILE:
            _process_hostile(entity, pos, fighter, ai, game_map, player_pos, graph)
        elif ai.kind == AIKind.CONFUSED:
            _process_confused(entity, pos, ai, game_map, player_pos, log)
        elif ai.kind == AIKind.FLEEING:
            _process_fleeing(entity, pos, ai, game_map, player_pos, graph)
        elif ai.kind == AIKind.STATIONARY:
            pass  # Attacks handled in the combat system.


def _process_hostile(
    entity: Entity,
    pos: Position,
    fighter: Fighter,
    ai: AI,
    game_map: "GameMap",
    player_pos: Position,
    graph: tcod.path.SimpleGraph,
) -> None:
    """Hostile AI: chase the player if visible, wander otherwise."""
    if not game_map.visible[pos.y, pos.x]:
        _wander(pos, game_map)
        return

    path = get_path(graph, (pos.x, pos.y), (player_pos.x, player_pos.y))
    if len(path) > 1:
        next_x, next_y = path[1]
        if game_map.is_walkable(next_x, next_y):
            pos.x, pos.y = next_x, next_y


def _process_confused(
    entity: Entity,
    pos: Position,
    ai: AI,
    game_map: "GameMap",
    player_pos: Position,
    log,
) -> None:
    """Confused AI: wander randomly until the effect wears off."""
    if ai.confused_turns > 0:
        ai.confused_turns -= 1
        _wander(pos, game_map)
    else:
        # Revert to the previous AI behaviour once confusion fades.
        if ai.previous_kind is not None:
            ai.kind = ai.previous_kind
            ai.previous_kind = None
            log.add(f"The {_name(entity)} shakes off its confusion!", PURPLE)


def _process_fleeing(
    entity: Entity,
    pos: Position,
    ai: AI,
    game_map: "GameMap",
    player_pos: Position,
    graph: tcod.path.SimpleGraph,
) -> None:
    """Fleeing AI: run away from the player."""
    if not game_map.visible[pos.y, pos.x]:
        _wander(pos, game_map)
        return

    dx = max(-1, min(1, pos.x - player_pos.x))
    dy = max(-1, min(1, pos.y - player_pos.y))

    target_x, target_y = pos.x + dx, pos.y + dy
    if game_map.is_walkable(target_x, target_y):
        pos.x, pos.y = target_x, target_y
    else:
        for try_dx, try_dy in [(dx, 0), (0, dy), (-dy, dx), (dy, -dx)]:
            tx, ty = pos.x + try_dx, pos.y + try_dy
            if game_map.is_walkable(tx, ty):
                pos.x, pos.y = tx, ty
                break


def _wander(pos: Position, game_map: "GameMap") -> None:
    """Move in a random walkable direction."""
    directions = [(0, 1), (0, -1), (1, 0), (-1, 0)]
    random.shuffle(directions)
    for dx, dy in directions:
        target_x = pos.x + dx
        target_y = pos.y + dy
        if game_map.is_walkable(target_x, target_y):
            pos.x, pos.y = target_x, target_y
            break


def _name(entity: Entity) -> str:
    if Name in entity.components:
        return entity.components[Name].name
    return "creature"

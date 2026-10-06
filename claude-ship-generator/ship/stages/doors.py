"""Stage 6: doors, bulkheads and the room connectivity graph.

Rooms facing a corridor usually open onto it. Rooms that don't get connected
through a neighbour (a spanning tree grown outward from the corridors), and a
few extra doors create loops. The reactor is only reachable via engineering.
"""

from __future__ import annotations

from itertools import combinations

from .. import tiles as T
from ..geometry import edge_tiles, pick_middle, shared_wall, tile_at
from ..model import CORRIDOR_NODE, Room, Ship

CORRIDOR_DOOR_CHANCE = 0.8
LOOP_DOOR_CHANCE = 0.12
NO_CORRIDOR_ACCESS = {"Reactor"}


def _corridor_sites(ship: Ship, room: Room) -> list[tuple[int, int]]:
    return [
        (x, y)
        for (x, y), (dx, dy) in edge_tiles(room.rect)
        if ship.tiles[x, y] == T.WALL and tile_at(ship.tiles, x + dx, y + dy) == T.CORRIDOR
    ]


def _add_door(rng, ship: Ship, sites: list[tuple[int, int]], a: Room, b: Room | None) -> None:
    x, y = pick_middle(rng, sites)
    ship.tiles[x, y] = T.DOOR
    a.doors.append((x, y))
    if b is None:
        ship.connect(CORRIDOR_NODE, a.id)
    else:
        b.doors.append((x, y))
        ship.connect(a.id, b.id)


def place_doors(rng, ship: Ship) -> None:
    ship.graph = {CORRIDOR_NODE: set()} | {r.id: set() for r in ship.rooms}

    neighbours: dict[int, dict[int, list[tuple[int, int]]]] = {r.id: {} for r in ship.rooms}
    for a, b in combinations(ship.rooms, 2):
        wall = [p for p in shared_wall(a.rect, b.rect) if ship.tiles[p] == T.WALL]
        if wall:
            neighbours[a.id][b.id] = wall
            neighbours[b.id][a.id] = wall

    # Hard rule: the reactor opens onto main engineering.
    for reactor in ship.rooms_of_type("Reactor"):
        for eng in ship.rooms_of_type("Main Engineering"):
            if eng.id in neighbours[reactor.id]:
                _add_door(rng, ship, neighbours[reactor.id][eng.id], reactor, eng)

    for room in ship.rooms:
        if room.type in NO_CORRIDOR_ACCESS:
            continue
        sites = _corridor_sites(ship, room)
        if sites and rng.random() < CORRIDOR_DOOR_CHANCE:
            _add_door(rng, ship, sites, room, None)

    # Spanning tree: connect every remaining room through an already-connected neighbour.
    connected = _reachable_nodes(ship)
    progress = True
    while progress:
        progress = False
        # The reactor is excluded: it is reached only through main engineering.
        pending = [r for r in ship.rooms if r.id not in connected and r.type not in NO_CORRIDOR_ACCESS]
        rng.shuffle(pending)
        for room in pending:
            options = [n for n in neighbours[room.id] if n in connected and ship.room(n).type not in NO_CORRIDOR_ACCESS]
            if not options:
                # Fall back to the corridor for rooms walled in by the reactor, etc.
                sites = _corridor_sites(ship, room) if room.type not in NO_CORRIDOR_ACCESS else []
                if not sites:
                    continue
                _add_door(rng, ship, sites, room, None)
            else:
                other = ship.room(rng.choice(options))
                _add_door(rng, ship, neighbours[room.id][other.id], room, other)
            connected.add(room.id)
            progress = True

    # A few extra doors so the ship has loops rather than being a pure tree.
    for a, b in combinations(ship.rooms, 2):
        if b.id in neighbours[a.id] and b.id not in ship.graph[a.id]:
            if NO_CORRIDOR_ACCESS & {a.type, b.type}:
                continue
            if rng.random() < LOOP_DOOR_CHANCE:
                _add_door(rng, ship, neighbours[a.id][b.id], a, b)


def _reachable_nodes(ship: Ship) -> set[int]:
    seen, stack = {CORRIDOR_NODE}, [CORRIDOR_NODE]
    while stack:
        for n in ship.graph[stack.pop()]:
            if n not in seen:
                seen.add(n)
                stack.append(n)
    seen.discard(CORRIDOR_NODE)
    return seen

"""Stage 5: assign a purpose to every partitioned rectangle.

Each zone has an ordered list of room types. Anchored types are placed by rule
first (bridge at the bow, reactor at the stern, airlock on the hull); the rest
are dealt out largest-room-first, with a filler type for any leftovers.
"""

from __future__ import annotations

from .. import tiles as T
from ..geometry import shared_wall, tile_at
from ..model import Room, Ship, ZoneKind

ZONE_ROOMS = {
    ZoneKind.COMMAND: (["Command", "Comms", "Briefing", "Captain's Quarters"], "Officers' Quarters"),
    ZoneKind.HABITATION: (["Mess", "Medbay", "Crew Quarters"], "Crew Quarters"),
    ZoneKind.SCIENCE: (["Lab", "Research", "Specimen Storage"], "Lab"),
    ZoneKind.CARGO: (["Cargo Hold", "Armoury", "Storage"], "Storage"),
    ZoneKind.ENGINEERING: (["Coolant", "Power Distribution", "Workshop"], "Parts Storage"),
}


def _on_lower_hull(ship: Ship, room: Room) -> list[tuple[int, int]]:
    """Bottom-wall hull tiles of ``room`` with open space beyond (airlock sites)."""
    r = room.rect
    return [
        (x, r.y2)
        for x in range(r.x + 1, r.x2)
        if tile_at(ship.tiles, x, r.y2) == T.HULL and tile_at(ship.tiles, x, r.y2 + 1) == T.VOID
    ]


def assign_rooms(rng, ship: Ship) -> None:
    by_zone: dict[ZoneKind, list[Room]] = {z: [] for z in ZoneKind}
    for room in ship.rooms:
        by_zone[room.zone].append(room)

    def take(zone: ZoneKind, room: Room | None, type_: str) -> None:
        if room is not None:
            room.type = type_
            by_zone[zone].remove(room)

    # Bridge: the bow-most command compartment.
    command = by_zone[ZoneKind.COMMAND]
    take(ZoneKind.COMMAND, min(command, key=lambda r: (r.rect.x, -r.rect.inner_area), default=None), "Bridge")

    # Reactor at the stern, with main engineering right next to it.
    eng = by_zone[ZoneKind.ENGINEERING]
    reactor = max(eng, key=lambda r: (r.rect.x2, r.rect.inner_area), default=None)
    take(ZoneKind.ENGINEERING, reactor, "Reactor")
    if reactor is not None:
        neighbours = [r for r in eng if shared_wall(r.rect, reactor.rect)]
        take(ZoneKind.ENGINEERING, max(neighbours, key=lambda r: r.rect.inner_area, default=None), "Main Engineering")

    # Airlock: the smallest cargo compartment that touches the outer hull.
    hull_rooms = [r for r in by_zone[ZoneKind.CARGO] if _on_lower_hull(ship, r)]
    airlock = min(hull_rooms, key=lambda r: r.rect.inner_area, default=None)
    if airlock is not None:
        take(ZoneKind.CARGO, airlock, "Airlock")
        sites = _on_lower_hull(ship, airlock)
        x, y = sites[len(sites) // 2]
        ship.tiles[x, y] = T.AIRLOCK
        ship.spawn = (x, y - 1)

    for zone, rooms in by_zone.items():
        types, filler = ZONE_ROOMS[zone]
        for room, type_ in zip(sorted(rooms, key=lambda r: -r.rect.inner_area), types + [filler] * len(rooms)):
            room.type = type_

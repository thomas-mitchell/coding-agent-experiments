"""Draw the ship, the player and the status bar onto a tcod console."""

from __future__ import annotations

import numpy as np
import tcod

from ship import Ship, ZoneKind
from ship import tiles as T

from .entity import Player

ZONE_FLOOR_BG = {
    ZoneKind.COMMAND: (14, 22, 44),
    ZoneKind.HABITATION: (14, 34, 20),
    ZoneKind.SCIENCE: (32, 18, 42),
    ZoneKind.CARGO: (40, 30, 14),
    ZoneKind.ENGINEERING: (44, 16, 14),
}
TEXT = (200, 200, 210)
DIM = (120, 120, 135)
LABEL = (150, 150, 160)


def _ship_graphics(ship: Ship) -> np.ndarray:
    """Tile graphics with room floors tinted by their zone."""
    g = T.GRAPHICS[ship.tiles]
    zone_bg = np.zeros((len(ship.rooms) + 1, 3), dtype=np.uint8)
    for room in ship.rooms:
        zone_bg[room.id] = ZONE_FLOOR_BG[room.zone]
    floor = (ship.tiles == T.FLOOR) & (ship.room_at > 0)
    g["bg"][floor] = zone_bg[ship.room_at[floor]]
    return g


def location_name(ship: Ship, x: int, y: int) -> str:
    room = ship.room(int(ship.room_at[x, y]))
    if room is not None:
        return f"{room.type} ({room.zone.value})"
    return {T.CORRIDOR: "Corridor", T.DOOR: "Doorway", T.AIRLOCK: "Airlock hatch"}.get(int(ship.tiles[x, y]), "")


def render(console: tcod.console.Console, ship: Ship, player: Player, show_labels: bool) -> None:
    ox = (console.width - ship.width) // 2
    oy = 1
    console.rgb[ox : ox + ship.width, oy : oy + ship.height] = _ship_graphics(ship)

    if show_labels:
        for room in ship.rooms:
            label = room.type if len(room.type) <= room.rect.inner_w else room.type[: room.rect.inner_w]
            cx, cy = room.rect.center
            console.print(ox + cx - (len(label) - 1) // 2, oy + cy, label, fg=LABEL)

    console.print(ox + player.x, oy + player.y, player.char, fg=player.color)

    status_y = oy + ship.height + 1
    console.print(ox, status_y, f"Seed {ship.seed}", fg=DIM)
    console.print(ox + 14, status_y, location_name(ship, player.x, player.y), fg=TEXT)
    console.print(
        ox, status_y + 1, "Move: arrows / numpad / hjklyubn   Tab: labels   R: new ship   Esc: quit", fg=DIM
    )

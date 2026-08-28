"""Rendering functions with FOV support."""
from __future__ import annotations
from typing import TYPE_CHECKING

import numpy as np
import tcod.console

if TYPE_CHECKING:
    import tcod.ecs
    from game_map import GameMap


def render_map(
    console: tcod.console.Console,
    game_map: GameMap,
    camera_x: int,
    camera_y: int,
) -> None:
    """Render the map tiles with visibility."""
    map_h, map_w = game_map.tiles.shape
    con_w, con_h = console.width, console.height

    y_start = max(camera_y, 0)
    y_end = min(camera_y + con_h, map_h)
    x_start = max(camera_x, 0)
    x_end = min(camera_x + con_w, map_w)

    cy_start = y_start - camera_y
    cy_end = y_end - camera_y
    cx_start = x_start - camera_x
    cx_end = x_end - camera_x

    tiles = game_map.tiles[y_start:y_end, x_start:x_end]
    visible = game_map.visible[y_start:y_end, x_start:x_end]
    explored = game_map.explored[y_start:y_end, x_start:x_end]

    is_lit = visible

    # Build char codes: wall = '#', floor = ' '
    char_codes = np.full(tiles.shape, ord(" "), dtype=np.uint32)
    wall_mask = ~tiles["walkable"] & explored
    char_codes[wall_mask] = ord("#")

    console.rgb[cy_start:cy_end, cx_start:cx_end]["ch"] = char_codes

    # Foreground: light if visible, dark if only explored.
    fg = np.where(
        is_lit[:, :, np.newaxis],
        tiles["light_fg"],
        tiles["dark_fg"],
    )
    console.rgb[cy_start:cy_end, cx_start:cx_end]["fg"] = fg

    # Background: light if visible, dark if only explored.
    bg = np.where(
        is_lit[:, :, np.newaxis],
        tiles["light_bg"],
        tiles["dark_bg"],
    )
    console.rgb[cy_start:cy_end, cx_start:cx_end]["bg"] = bg

    # Tiles that are neither visible nor explored are black.
    hidden = ~explored
    console.rgb[cy_start:cy_end, cx_start:cx_end]["fg"][hidden] = (0, 0, 0)
    console.rgb[cy_start:cy_end, cx_start:cx_end]["bg"][hidden] = (0, 0, 0)


def render_entities(
    console: tcod.console.Console,
    registry: tcod.ecs.Registry,
    camera_x: int,
    camera_y: int,
) -> None:
    """Draw all positioned, renderable entities that are currently visible."""
    from components import Position, Renderable
    from game_map import GameMap

    game_map: GameMap | None = registry.context.get("game_map")
    if game_map is None:
        return

    for entity in registry.Q.all_of(components=[Position, Renderable]):
        pos: Position = entity.components[Position]
        ren: Renderable = entity.components[Renderable]
        if not game_map.in_bounds(pos.x, pos.y):
            continue
        if not game_map.visible[pos.y, pos.x]:
            continue
        sx = pos.x - camera_x
        sy = pos.y - camera_y
        if 0 <= sx < console.width and 0 <= sy < console.height:
            console.print(x=sx, y=sy, string=ren.char, fg=ren.fg)


def render_all(
    console: tcod.console.Console,
    game_map: GameMap,
    registry: tcod.ecs.Registry,
    player: tcod.ecs.Entity,
) -> None:
    """Orchestrate all rendering: map, then entities, centred on the player."""
    from components import Position

    console.clear()

    pos: Position = player.components[Position]

    cam_x = pos.x - console.width // 2
    cam_y = pos.y - console.height // 2

    render_map(console, game_map, cam_x, cam_y)
    render_entities(console, registry, cam_x, cam_y)

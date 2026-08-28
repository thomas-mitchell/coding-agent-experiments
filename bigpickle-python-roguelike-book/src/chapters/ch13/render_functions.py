"""Rendering functions for drawing the map, entities, and UI."""
from __future__ import annotations
from typing import TYPE_CHECKING

import numpy as np
import tcod.console
import tcod.ecs

from game_map import GameMap
from message_log import MessageLog

if TYPE_CHECKING:
    pass

PANEL_HEIGHT = 10  # Bottom panel for messages + stats


def render_map(
    console: tcod.console.Console,
    game_map: GameMap,
    camera_x: int,
    camera_y: int,
    view_height: int,
) -> None:
    """Draw the map tiles onto the console, respecting visibility and exploration."""
    map_h, map_w = game_map.tiles.shape
    con_w = console.width
    con_h = view_height  # Only render into the top portion above the panel.

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

    char_codes = np.full(tiles.shape, ord(" "), dtype=np.uint32)
    wall_mask = ~tiles["walkable"] & explored
    char_codes[wall_mask] = ord("#")
    floor_mask = tiles["walkable"] & explored
    char_codes[floor_mask] = ord(" ")

    console.rgb[cy_start:cy_end, cx_start:cx_end]["ch"] = char_codes

    fg = np.where(
        is_lit[:, :, np.newaxis],
        tiles["light_fg"],
        tiles["dark_fg"],
    )
    console.rgb[cy_start:cy_end, cx_start:cx_end]["fg"] = fg

    bg = np.where(
        is_lit[:, :, np.newaxis],
        tiles["light_bg"],
        tiles["dark_bg"],
    )
    console.rgb[cy_start:cy_end, cx_start:cx_end]["bg"] = bg

    hidden = ~explored
    console.rgb[cy_start:cy_end, cx_start:cx_end]["fg"][hidden] = (0, 0, 0)
    console.rgb[cy_start:cy_end, cx_start:cx_end]["bg"][hidden] = (0, 0, 0)


def render_entities(
    console: tcod.console.Console,
    registry: tcod.ecs.Registry,
    camera_x: int,
    camera_y: int,
    view_height: int,
) -> None:
    """Draw all positioned, renderable entities that are currently visible."""
    from components import Position, Renderable

    game_map: GameMap | None = registry.context.get("game_map")
    if game_map is None:
        return

    for entity in registry.Q.all_of(components=[Position, Renderable]):
        pos: Position = entity.components[Position]
        ren: Renderable = entity.components[Renderable]
        if not game_map.in_bounds(pos.x, pos.y):
            continue
        if not game_map.explored[pos.y, pos.x]:
            continue
        sx = pos.x - camera_x
        sy = pos.y - camera_y
        if 0 <= sx < console.width and 0 <= sy < view_height:
            if game_map.visible[pos.y, pos.x]:
                console.print(x=sx, y=sy, string=ren.char, fg=ren.fg)
            else:
                dim_fg = tuple(c // 2 for c in ren.fg)
                console.print(x=sx, y=sy, string=ren.char, fg=dim_fg)


def render_panel(
    console: tcod.console.Console,
    player: tcod.ecs.Entity,
    message_log: MessageLog,
) -> None:
    """Render the bottom panel with stats and messages."""
    from components import Fighter, Inventory

    panel_y = console.height - PANEL_HEIGHT

    # Draw a separator line.
    console.print(x=0, y=panel_y, string="=" * console.width, fg=(100, 100, 100))

    # Player stats.
    fighter = player.components[Fighter]
    stats = f"HP: {fighter.hp}/{fighter.max_hp}  Power: {fighter.power}  Defense: {fighter.defense}"
    console.print(x=1, y=panel_y + 1, string=stats, fg=(255, 255, 255))

    # Inventory.
    inventory = player.components[Inventory]
    if inventory.items:
        inv_parts = []
        for i, item_entity in enumerate(inventory.items):
            from components import Name
            item_name = item_entity.components[Name].name
            inv_parts.append(f"{i + 1}:{item_name}")
        inv_str = "  ".join(inv_parts)
        console.print(
            x=1, y=panel_y + 2,
            string=f"[{inv_str}]",
            fg=(200, 200, 0),
        )
    else:
        console.print(x=1, y=panel_y + 2, string="[empty]", fg=(100, 100, 100))

    # Recent messages.
    recent = message_log.recent
    msg_y = panel_y + 4
    for i, msg in enumerate(recent):
        console.print(
            x=1,
            y=msg_y + i,
            string=msg.text[: console.width - 2],
            fg=msg.color,
        )


def render_all(
    console: tcod.console.Console,
    game_map: GameMap,
    registry: tcod.ecs.Registry,
    player: tcod.ecs.Entity,
    message_log: MessageLog,
) -> None:
    """Orchestrate all rendering: map, then entities, then UI panel."""
    from components import Position

    console.clear()

    pos: Position = player.components[Position]

    view_height = console.height - PANEL_HEIGHT

    # Centre the camera on the player (within the map area).
    cam_x = pos.x - console.width // 2
    cam_y = pos.y - view_height // 2

    render_map(console, game_map, cam_x, cam_y, view_height)
    render_entities(console, registry, cam_x, cam_y, view_height)
    render_panel(console, player, message_log)

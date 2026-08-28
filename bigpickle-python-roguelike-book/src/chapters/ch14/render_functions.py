"""Rendering functions for drawing the map, entities, and HUD."""
from __future__ import annotations
from typing import TYPE_CHECKING

import numpy as np
import tcod.console
import tcod.ecs

from components import AI, AIKind, Fighter, Name, Position, Renderable, XP

if TYPE_CHECKING:
    from game_map import GameMap


def render_map(
    console: tcod.console.Console,
    game_map: GameMap,
    camera_x: int,
    camera_y: int,
) -> None:
    """Draw the map tiles onto the console, respecting visibility."""
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

    char_codes = np.full(tiles.shape, ord(" "), dtype=np.uint32)
    char_codes[~tiles["walkable"] & explored] = ord("#")
    char_codes[tiles["walkable"] & explored] = ord(" ")

    console.rgb[cy_start:cy_end, cx_start:cx_end]["ch"] = char_codes

    console.rgb[cy_start:cy_end, cx_start:cx_end]["fg"] = np.where(
        is_lit[:, :, np.newaxis], tiles["light_fg"], tiles["dark_fg"]
    )
    console.rgb[cy_start:cy_end, cx_start:cx_end]["bg"] = np.where(
        is_lit[:, :, np.newaxis], tiles["light_bg"], tiles["dark_bg"]
    )

    hidden = ~explored
    console.rgb[cy_start:cy_end, cx_start:cx_end]["fg"][hidden] = (0, 0, 0)
    console.rgb[cy_start:cy_end, cx_start:cx_end]["bg"][hidden] = (0, 0, 0)


def render_entities(
    console: tcod.console.Console,
    registry: tcod.ecs.Registry,
    game_map: GameMap,
    camera_x: int,
    camera_y: int,
) -> None:
    """Draw all positioned, renderable entities that have been explored."""
    for entity in registry.Q.all_of(components=[Position, Renderable]):
        pos: Position = entity.components[Position]
        ren: Renderable = entity.components[Renderable]
        if not game_map.in_bounds(pos.x, pos.y):
            continue
        if not game_map.explored[pos.y, pos.x]:
            continue
        sx = pos.x - camera_x
        sy = pos.y - camera_y
        if 0 <= sx < console.width and 0 <= sy < console.height:
            if game_map.visible[pos.y, pos.x]:
                console.print(x=sx, y=sy, string=ren.char, fg=ren.fg)
            else:
                dim_fg = tuple(c // 2 for c in ren.fg)
                console.print(x=sx, y=sy, string=ren.char, fg=dim_fg)


def render_messages(
    console: tcod.console.Console,
    messages: list[str],
    x: int,
    y: int,
    width: int,
    height: int,
) -> None:
    """Render the message log inside a bordered panel."""
    console.draw_frame(x=x, y=y, width=width, height=height, title="Log")
    y_offset = y + height - 1
    for message in messages:
        console.print(x=x + 1, y=y_offset, string=message[: width - 2], fg=(200, 200, 200))
        y_offset -= 1
        if y_offset <= y:
            break


def render_hud(
    console: tcod.console.Console,
    registry: tcod.ecs.Registry,
    player: tcod.ecs.Entity,
    game_map: GameMap,
    x: int,
    y: int,
    width: int,
) -> None:
    """Render the player status line and visible-enemy AI summary."""
    fighter = player.components[Fighter]
    xp = player.components.get(XP)
    hp_text = f"HP: {fighter.hp}/{fighter.max_hp}"
    if xp is not None:
        hp_text += f"  LVL: {xp.level}  XP: {xp.current}/{xp.xp_to_next}"
    console.print(x=x, y=y, string=hp_text, fg=(255, 255, 255))

    # Count visible enemies by AI behaviour so multiple AI types are obvious.
    ppos = player.components[Position]
    counts: dict[AIKind, int] = {kind: 0 for kind in AIKind}
    for entity, pos, ai in registry.Q[tcod.ecs.Entity, Position, AI]:
        if entity is player:
            continue
        if Fighter not in entity.components:
            continue
        if not game_map.visible[pos.y, pos.x]:
            continue
        counts[ai.kind] += 1

    labels: list[tuple[AIKind, str]] = [
        (AIKind.HOSTILE, "Hostile"),
        (AIKind.FLEEING, "Fleeing"),
        (AIKind.CONFUSED, "Confused"),
        (AIKind.STATIONARY, "Stationary"),
    ]
    parts = [f"{name}:{counts[kind]}" for kind, name in labels if counts[kind] > 0]
    summary = "  ".join(parts) if parts else "Enemies near: none"
    console.print(x=x, y=y + 1, string=summary[: width - 1], fg=(200, 200, 200))


def render_all(
    console: tcod.console.Console,
    game_map: GameMap,
    registry: tcod.ecs.Registry,
    player: tcod.ecs.Entity,
    messages: list[str],
) -> None:
    """Orchestrate all rendering, centred on the player."""
    console.clear()
    pos: Position = player.components[Position]
    cam_x = pos.x - console.width // 2
    cam_y = pos.y - console.height // 2

    hud_height = 3
    log_height = 8

    render_map(console, game_map, cam_x, cam_y)
    render_entities(console, registry, game_map, cam_x, cam_y)

    render_hud(
        console,
        registry,
        player,
        game_map,
        x=1,
        y=console.height - hud_height,
        width=console.width,
    )
    render_messages(
        console,
        messages,
        x=1,
        y=console.height - hud_height - log_height,
        width=console.width - 2,
        height=log_height,
    )

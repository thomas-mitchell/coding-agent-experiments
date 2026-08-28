"""Rendering functions with message log, floor counter, and targeting overlay."""
from __future__ import annotations

import tcod.console
import tcod.ecs

from color import AREA_FG, PANEL_BORDER, PANEL_SUBTEXT, TARGET_BG, TARGET_FG

PANEL_HEIGHT = 7
MAP_HEIGHT = 43  # SCREEN_HEIGHT - PANEL_HEIGHT


def render_map(console, game_map, camera_x, camera_y):
    """Render the map tiles with visibility."""
    for y in range(max(0, camera_y), min(game_map.height, camera_y + MAP_HEIGHT)):
        for x in range(max(0, camera_x), min(game_map.width, camera_x + console.width)):
            screen_x = x - camera_x
            screen_y = y - camera_y
            if game_map.visible[y, x]:
                tile = game_map.tiles[y, x]
                console.print(x=screen_x, y=screen_y, string=" ",
                    fg=tile["light_fg"], bg=tile["light_bg"])
            elif game_map.explored[y, x]:
                tile = game_map.tiles[y, x]
                console.print(x=screen_x, y=screen_y, string=" ",
                    fg=tile["dark_fg"], bg=tile["dark_bg"])


def render_entities(console, registry, game_map, camera_x, camera_y):
    """Render entities on visible tiles.

    The registry query must name ``tcod.ecs.Entity`` explicitly so that each
    yielded tuple contains the entity object followed by its components.
    """
    from components import Position, Renderable
    for entity, pos, rend in registry.Q[tcod.ecs.Entity, Position, Renderable]:
        if game_map.in_bounds(pos.x, pos.y) and game_map.visible[pos.y, pos.x]:
            screen_x = pos.x - camera_x
            screen_y = pos.y - camera_y
            if 0 <= screen_x < console.width and 0 <= screen_y < MAP_HEIGHT:
                console.print(x=screen_x, y=screen_y, string=rend.char, fg=rend.fg)


def render_targeting(console, game_map, camera_x, camera_y, targeting):
    """Draw the targeting cursor and, for area spells, the blast radius ring."""
    if targeting is None or not targeting.active:
        return

    from targeting import range_to_origin

    # Centre of the screen is where the cursor starts (player origin).
    origin_x = camera_x + console.width // 2
    origin_y = camera_y + MAP_HEIGHT // 2

    # Highlight the radius ring for area spells.
    if targeting.is_area and targeting.radius > 0:
        radius = targeting.radius
        for dy in range(-radius, radius + 1):
            for dx in range(-radius, radius + 1):
                if max(abs(dx), abs(dy)) != radius:
                    continue
                tx = targeting.cursor_x + dx
                ty = targeting.cursor_y + dy
                if not game_map.in_bounds(tx, ty):
                    continue
                if not game_map.visible[ty, tx]:
                    continue
                sx = tx - camera_x
                sy = ty - camera_y
                if 0 <= sx < console.width and 0 <= sy < MAP_HEIGHT:
                    console.print(x=sx, y=sy, string="*", fg=AREA_FG)

    # Draw the cursor itself.
    sx = targeting.cursor_x - camera_x
    sy = targeting.cursor_y - camera_y
    if 0 <= sx < console.width and 0 <= sy < MAP_HEIGHT:
        in_range = range_to_origin(targeting, origin_x, origin_y) <= targeting.max_range
        fg = TARGET_FG
        bg = TARGET_BG
        if not in_range:
            fg = (128, 128, 128)
        console.print(x=sx, y=sy, string="X", fg=fg, bg=bg)


def render_panel(console, player, message_log, dungeon_level):
    """Render the bottom panel with stats, floor, and messages."""
    panel_y = MAP_HEIGHT

    # Separator line
    for x in range(console.width):
        console.print(x=x, y=panel_y, string="─", fg=PANEL_BORDER)

    # Player stats
    from components import Fighter, Name, Equipment
    fighter = player.components[Fighter]
    name = player.components[Name].name
    stats = f"{name}  HP: {fighter.hp}/{fighter.max_hp}"
    console.print(x=1, y=panel_y + 1, string=stats, fg=(255, 255, 255))

    # Floor number (right-aligned) -- shown prominently in the UI.
    floor_str = f"Floor: {dungeon_level}"
    console.print(
        x=console.width - len(floor_str) - 1,
        y=panel_y + 1,
        string=floor_str,
        fg=(200, 200, 120),
    )

    # Equipment
    equip = player.components.get(Equipment)
    if equip:
        weapon_name = equip.weapon.components[Name].name if equip.weapon else "None"
        armor_name = equip.armor.components[Name].name if equip.armor else "None"
        equip_str = f"Weapon: {weapon_name}  Armor: {armor_name}"
        console.print(x=1, y=panel_y + 2, string=equip_str, fg=PANEL_SUBTEXT)

    # Messages
    messages = message_log.get_visible(4)
    for i, msg in enumerate(messages):
        console.print(x=1, y=panel_y + 3 + i, string=msg.text[:console.width - 2], fg=msg.color)


def render_all(console, game_map, registry, player, message_log, dungeon_level, targeting=None):
    """Render everything."""
    from components import Position
    player_pos = player.components[Position]
    camera_x = player_pos.x - console.width // 2
    camera_y = player_pos.y - MAP_HEIGHT // 2
    camera_x = max(0, min(camera_x, game_map.width - console.width))
    camera_y = max(0, min(camera_y, game_map.height - MAP_HEIGHT))

    console.clear()
    render_map(console, game_map, camera_x, camera_y)
    render_entities(console, registry, game_map, camera_x, camera_y)
    if targeting is not None and targeting.active:
        render_targeting(console, game_map, camera_x, camera_y, targeting)
    render_panel(console, player, message_log, dungeon_level)

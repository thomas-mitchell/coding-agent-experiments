"""Rendering functions with message log."""
from __future__ import annotations
from typing import TYPE_CHECKING
import tcod.console
import tcod.ecs

if TYPE_CHECKING:
    from game_map import GameMap
    from components import MessageLog


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


def render_panel(console, player, message_log):
    """Render the bottom panel with stats and messages."""
    panel_y = MAP_HEIGHT

    # Separator line
    for x in range(console.width):
        console.print(x=x, y=panel_y, string="─", fg=(100, 100, 100))

    # Player stats
    from components import Fighter, Name, Equipment, Equippable
    fighter = player.components[Fighter]
    name = player.components[Name].name
    stats = f"{name}  HP: {fighter.hp}/{fighter.max_hp}"
    console.print(x=1, y=panel_y + 1, string=stats, fg=(255, 255, 255))

    # Equipment
    equip = player.components.get(Equipment)
    if equip:
        weapon_name = equip.weapon.components[Name].name if equip.weapon else "None"
        armor_name = equip.armor.components[Name].name if equip.armor else "None"
        equip_str = f"Weapon: {weapon_name}  Armor: {armor_name}"
        console.print(x=1, y=panel_y + 2, string=equip_str, fg=(180, 180, 180))

    # Messages
    messages = message_log.get_visible(4)
    for i, msg in enumerate(messages):
        console.print(x=1, y=panel_y + 3 + i, string=msg.text[:console.width - 2], fg=msg.color)


def render_all(console, game_map, registry, player, message_log):
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
    render_panel(console, player, message_log)

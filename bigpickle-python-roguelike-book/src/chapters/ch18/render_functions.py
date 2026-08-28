from __future__ import annotations

from typing import TYPE_CHECKING

import numpy as np
import tcod.console

from . import color as colors
from .components import AI, Consumable, Description, Equippable, Equipment, Fighter, Inventory, Name, Position, Renderable
from .input_handlers import MenuState


def render_all(
    console: tcod.console.Console,
    world: World,
    game_map: GameMap,
    player: int,
    menu_state: MenuState,
    look_cursor_x: int,
    look_cursor_y: int,
    selected_index: int,
) -> None:
    console.clear()

    if menu_state == MenuState.LEVEL_UP:
        render_level_up_menu(console, world, player)
        return

    render_map(console, game_map, world)
    render_entities(console, game_map, world)

    if menu_state == MenuState.INVENTORY:
        render_inventory_menu(console, world, player, selected_index)
    elif menu_state == MenuState.EQUIPMENT:
        render_equipment_menu(console, world, player, selected_index)
    elif menu_state == MenuState.DROP:
        render_drop_menu(console, world, player, selected_index)
    elif menu_state == MenuState.LOOK:
        render_look_mode(console, world, game_map, look_cursor_x, look_cursor_y, player)
    elif menu_state == MenuState.LOG_HISTORY:
        render_log_history(console, world, player, selected_index)
    elif menu_state == MenuState.DEATH:
        render_death_screen(console, world, player)
    else:
        render_panel(console, world, game_map, player)


def render_map(console: tcod.console.Console, game_map: GameMap, world: World) -> None:
    map_width = min(game_map.width, console.width - 22)
    map_height = min(game_map.height, console.height - 7)

    for x in range(map_width):
        for y in range(map_height):
            tile = game_map.tiles[x, y]
            if game_map.fov[x, y]:
                console.tiles_rgb["fg"][x, y] = tile["light"]
                console.tiles_rgb["bg"][x, y] = (20, 20, 30)
            elif game_map.explored[x, y]:
                console.tiles_rgb["fg"][x, y] = tile["dark"]
                console.tiles_rgb["bg"][x, y] = (10, 10, 15)
            else:
                console.tiles_rgb["fg"][x, y] = (0, 0, 0)
                console.tiles_rgb["bg"][x, y] = (0, 0, 0)


def render_entities(console: tcod.console.Console, game_map: GameMap, world: World) -> None:
    entities_with_pos = []
    for entity, (pos, rend) in world.Q.all_of(components=[Position, Renderable]):
        if game_map.fov[pos.x, pos.y]:
            entities_with_pos.append((rend.render_order, pos, rend))

    entities_with_pos.sort(key=lambda x: x[0])

    for _, pos, rend in entities_with_pos:
        if pos.x < console.width - 22 and pos.y < console.height - 7:
            console.print(pos.x, pos.y, rend.char, fg=rend.color)


def render_panel(console: tcod.console.Console, world: World, game_map: GameMap, player: int) -> None:
    panel_x = console.width - 22
    panel_y = 0
    panel_w = 22
    panel_h = console.height

    panel = tcod.console.Console(panel_w, panel_h)
    panel.bg = colors.panel_bg.tuple
    panel.fg = colors.white.tuple

    fighter = world[player, "Fighter"]
    name = world[player, "Name"]
    xp = world[player, "XP"] if "XP" in world[player].components else None

    panel.print(1, 1, f"{name.name} (Lvl {xp.level})", fg=colors.white.tuple)

    hp_bar_width = panel_w - 4
    hp = fighter.hp
    max_hp = fighter.max_hp
    hp_filled = int(hp_bar_width * hp / max_hp) if max_hp > 0 else 0

    for i in range(hp_bar_width):
        if i < hp_filled:
            panel.print(1 + i, 3, "=", fg=colors.health_green.tuple)
        else:
            panel.print(1 + i, 3, "=", fg=colors.health_red.tuple)

    panel.print(1, 3, f" HP: {hp}/{max_hp}", fg=colors.white.tuple)

    if xp:
        xp_bar_width = panel_w - 4
        xp_needed = xp.level_up_xp
        xp_filled = int(xp_bar_width * xp.current / xp_needed) if xp_needed > 0 else 0

        for i in range(xp_bar_width):
            if i < xp_filled:
                panel.print(1 + i, 4, "=", fg=colors.yellow.tuple)
            else:
                panel.print(1 + i, 4, "=", fg=colors.dark_grey.tuple)

        panel.print(1, 4, f" XP: {xp.current}/{xp_needed}", fg=colors.white.tuple)

    equipment = world[player, "Equipment"] if "Equipment" in world[player].components else None
    if equipment:
        weapon_name = world[equipment.weapon, "Name"].name if equipment.weapon else "None"
        armor_name = world[equipment.armor, "Name"].name if equipment.armor else "None"
        panel.print(1, 6, f"Weapon: {weapon_name}", fg=colors.light_grey.tuple)
        panel.print(1, 7, f"Armor:  {armor_name}", fg=colors.light_grey.tuple)

    panel.print(1, 9, f"ATK: {fighter.power}  DEF: {fighter.defense}", fg=colors.light_grey.tuple)

    panel.print(0, 11, "=" * (panel_w - 1), fg=colors.panel_border.tuple)

    msg_log = world["message_log"]
    y = 12
    for msg in msg_log.messages[-5:]:
        msg_text = msg.text
        if len(msg_text) > panel_w - 2:
            msg_text = msg_text[: panel_w - 5] + "..."
        panel.print(1, y, msg_text, fg=msg.color)
        y += 1

    panel.print(0, panel_h - 1, "=" * (panel_w - 1), fg=colors.panel_border.tuple)

    help_text = "i:nv e:quip d:rop v:look z:log"
    panel.print(1, panel_h - 2, help_text, fg=colors.grey.tuple)

    console.blit(panel, dest_x=panel_x, dest_y=panel_y)


def render_inventory_menu(console: tcod.console.Console, world: World, player: int, selected_index: int) -> None:
    inventory = world[player, "Inventory"]

    menu_w = 40
    menu_h = len(inventory.items) + 4
    if menu_h < 6:
        menu_h = 6

    menu_x = (console.width - menu_w) // 2
    menu_y = (console.height - menu_h) // 2

    panel = tcod.console.Console(menu_w, menu_h)
    panel.bg = colors.menu_bg.tuple
    panel.fg = colors.white.tuple

    panel.print(1, 0, "=" * (menu_w - 2), fg=colors.panel_border.tuple)
    panel.print(1, 1, " INVENTORY ", fg=colors.yellow.tuple)
    panel.print(1, 2, "=" * (menu_w - 2), fg=colors.panel_border.tuple)

    if not inventory.items:
        panel.print(2, 4, "Your inventory is empty.", fg=colors.grey.tuple)
    else:
        for idx, item_id in enumerate(inventory.items):
            item_name = world[item_id, "Name"].name
            marker = "> " if idx == selected_index else "  "
            fg = colors.yellow.tuple if idx == selected_index else colors.white.tuple
            panel.print(1, 3 + idx, f"{marker}[{idx + 1}] {item_name}", fg=fg)

    panel.print(1, menu_h - 1, "ENTER:use ESC:close", fg=colors.grey.tuple)

    console.blit(panel, dest_x=menu_x, dest_y=menu_y)


def render_equipment_menu(console: tcod.console.Console, world: World, player: int, selected_index: int) -> None:
    inventory = world[player, "Inventory"]
    equipment = world[player, "Equipment"]

    menu_w = 40
    menu_h = len(inventory.items) + 6
    if menu_h < 8:
        menu_h = 8

    menu_x = (console.width - menu_w) // 2
    menu_y = (console.height - menu_h) // 2

    panel = tcod.console.Console(menu_w, menu_h)
    panel.bg = colors.menu_bg.tuple
    panel.fg = colors.white.tuple

    panel.print(1, 0, "=" * (menu_w - 2), fg=colors.panel_border.tuple)
    panel.print(1, 1, " EQUIPMENT ", fg=colors.yellow.tuple)
    panel.print(1, 2, "=" * (menu_w - 2), fg=colors.panel_border.tuple)

    weapon_name = world[equipment.weapon, "Name"].name if equipment.weapon else "Empty"
    armor_name = world[equipment.armor, "Name"].name if equipment.armor else "Empty"
    panel.print(1, 3, f"Weapon: {weapon_name}", fg=colors.light_grey.tuple)
    panel.print(1, 4, f"Armor:  {armor_name}", fg=colors.light_grey.tuple)

    panel.print(0, 5, "-" * (menu_w - 1), fg=colors.grey.tuple)

    if not inventory.items:
        panel.print(2, 6, "No items to equip.", fg=colors.grey.tuple)
    else:
        for idx, item_id in enumerate(inventory.items):
            item_name = world[item_id, "Name"].name
            marker = "> " if idx == selected_index else "  "
            fg = colors.yellow.tuple if idx == selected_index else colors.white.tuple
            panel.print(1, 6 + idx, f"{marker}[{chr(ord('a') + idx)}] {item_name}", fg=fg)

    panel.print(1, menu_h - 1, "ENTER:equip ESC:close", fg=colors.grey.tuple)

    console.blit(panel, dest_x=menu_x, dest_y=menu_y)


def render_drop_menu(console: tcod.console.Console, world: World, player: int, selected_index: int) -> None:
    inventory = world[player, "Inventory"]

    menu_w = 40
    menu_h = len(inventory.items) + 4
    if menu_h < 6:
        menu_h = 6

    menu_x = (console.width - menu_w) // 2
    menu_y = (console.height - menu_h) // 2

    panel = tcod.console.Console(menu_w, menu_h)
    panel.bg = colors.menu_bg.tuple
    panel.fg = colors.white.tuple

    panel.print(1, 0, "=" * (menu_w - 2), fg=colors.panel_border.tuple)
    panel.print(1, 1, " DROP ITEM ", fg=colors.yellow.tuple)
    panel.print(1, 2, "=" * (menu_w - 2), fg=colors.panel_border.tuple)

    if not inventory.items:
        panel.print(2, 4, "Nothing to drop.", fg=colors.grey.tuple)
    else:
        for idx, item_id in enumerate(inventory.items):
            item_name = world[item_id, "Name"].name
            marker = "> " if idx == selected_index else "  "
            fg = colors.yellow.tuple if idx == selected_index else colors.white.tuple
            panel.print(1, 3 + idx, f"{marker}[{chr(ord('a') + idx)}] {item_name}", fg=fg)

    panel.print(1, menu_h - 1, "ENTER:drop ESC:close", fg=colors.grey.tuple)

    console.blit(panel, dest_x=menu_x, dest_y=menu_y)


def render_look_mode(
    console: tcod.console.Console,
    world: World,
    game_map: GameMap,
    cursor_x: int,
    cursor_y: int,
    player: int,
) -> None:
    render_panel(console, world, game_map, player)

    if 0 <= cursor_x < console.width - 22 and 0 <= cursor_y < console.height - 7:
        console.print(cursor_x, cursor_y, " ", bg=colors.white.tuple)

    info_x = console.width - 22
    info_y = 0
    info_w = 22
    info_h = 7

    info = tcod.console.Console(info_w, info_h)
    info.bg = colors.menu_bg.tuple
    info.fg = colors.white.tuple

    info.print(0, 0, f"X:{cursor_x} Y:{cursor_y}", fg=colors.yellow.tuple)

    if game_map.in_bounds(cursor_x, cursor_y):
        if game_map.fov[cursor_x, cursor_y] or game_map.explored[cursor_x, cursor_y]:
            tile = game_map.tiles[cursor_x, cursor_y]
            tile_name = "Floor" if tile["walkable"] else "Wall"
            info.print(0, 1, f"Tile: {tile_name}", fg=colors.light_grey.tuple)

            for entity, (pos, rend, name) in world.Q.all_of(components=[Position, Renderable, Name]):
                if pos.x == cursor_x and pos.y == cursor_y:
                    if game_map.fov[cursor_x, cursor_y]:
                        desc = world[entity, "Description"].text if "Description" in world[entity].components else ""
                        info.print(0, 2, name.name, fg=rend.color)
                        if desc:
                            words = desc.split()
                            line = ""
                            y = 3
                            for word in words:
                                if len(line) + len(word) + 1 > info_w:
                                    info.print(0, y, line, fg=colors.light_grey.tuple)
                                    y += 1
                                    line = word
                                else:
                                    line = f"{line} {word}" if line else word
                            if line:
                                info.print(0, y, line, fg=colors.light_grey.tuple)
                        break
        else:
            info.print(0, 1, "Unknown", fg=colors.grey.tuple)

    console.blit(info, dest_x=info_x, dest_y=info_y)


def render_log_history(console: tcod.console.Console, world: World, player: int, selected_index: int) -> None:
    msg_log = world["message_log"]

    menu_w = console.width - 4
    menu_h = console.height - 4

    menu_x = 2
    menu_y = 2

    panel = tcod.console.Console(menu_w, menu_h)
    panel.bg = colors.menu_bg.tuple
    panel.fg = colors.white.tuple

    panel.print(1, 0, "=" * (menu_w - 2), fg=colors.panel_border.tuple)
    panel.print(1, 1, " MESSAGE LOG ", fg=colors.yellow.tuple)
    panel.print(1, 2, "=" * (menu_w - 2), fg=colors.panel_border.tuple)

    messages = msg_log.messages
    visible_lines = menu_h - 5

    max_scroll = max(0, len(messages) - visible_lines)
    selected_index = min(selected_index, max_scroll)

    for i in range(visible_lines):
        msg_idx = i + selected_index
        if msg_idx < len(messages):
            msg = messages[msg_idx]
            msg_text = msg.text
            if len(msg_text) > menu_w - 4:
                msg_text = msg_text[: menu_w - 7] + "..."
            panel.print(2, 3 + i, msg_text, fg=msg.color)

    panel.print(1, menu_h - 2, f"Scroll: {selected_index}/{max_scroll}", fg=colors.grey.tuple)
    panel.print(1, menu_h - 1, "j/k:scroll ESC:close", fg=colors.grey.tuple)

    console.blit(panel, dest_x=menu_x, dest_y=menu_y)


def render_level_up_menu(console: tcod.console.Console, world: World, player: int) -> None:
    menu_w = 40
    menu_h = 8
    menu_x = (console.width - menu_w) // 2
    menu_y = (console.height - menu_h) // 2

    panel = tcod.console.Console(menu_w, menu_h)
    panel.bg = colors.menu_bg.tuple
    panel.fg = colors.white.tuple

    panel.print(1, 0, "=" * (menu_w - 2), fg=colors.panel_border.tuple)
    panel.print(1, 1, " LEVEL UP! ", fg=colors.yellow.tuple)
    panel.print(1, 2, "=" * (menu_w - 2), fg=colors.panel_border.tuple)
    panel.print(2, 3, "a) +20 HP", fg=colors.light_green.tuple)
    panel.print(2, 4, "b) +1 ATK", fg=colors.light_red.tuple)
    panel.print(2, 5, "c) +1 DEF", fg=colors.light_blue.tuple)
    panel.print(1, 7, "Choose a stat to increase.", fg=colors.grey.tuple)

    console.blit(panel, dest_x=menu_x, dest_y=menu_y)


def render_death_screen(console: tcod.console.Console, world: World, player: int) -> None:
    menu_w = 40
    menu_h = 5
    menu_x = (console.width - menu_w) // 2
    menu_y = (console.height - menu_h) // 2

    panel = tcod.console.Console(menu_w, menu_h)
    panel.bg = colors.menu_bg.tuple
    panel.fg = colors.red.tuple

    panel.print(1, 0, "=" * (menu_w - 2), fg=colors.dark_red.tuple)
    panel.print(1, 1, " YOU HAVE DIED! ", fg=colors.red.tuple)
    panel.print(1, 2, "=" * (menu_w - 2), fg=colors.dark_red.tuple)
    panel.print(2, 3, "Press ESC to quit.", fg=colors.grey.tuple)

    console.blit(panel, dest_x=menu_x, dest_y=menu_y)

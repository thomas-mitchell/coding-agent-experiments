"""Chapter 16: Equipment system."""
from __future__ import annotations

from pathlib import Path
from typing import TYPE_CHECKING

import numpy as np
import tcod
import tcod.ecs
import tcod.event

from actions import (
    BumpAction,
    EquipmentMenuAction,
    MenuCancelAction,
    MenuSelectAction,
    UnequipMenuAction,
    WaitAction,
)
from ai_system import create_pathfinder, process_ai_turns
from combat import (
    compute_fov,
    process_player_action,
    remove_dead_entities,
    resolve_enemy_attacks,
)
from components import Equipment, Fighter, Position
from items import equip_selection, unequip_selection
from factories import create_player, place_enemies, place_items
from game_map import GameMap
from input_handlers import handle_input, handle_menu_input
from message_log import MessageLog
from procgen import generate_dungeon
from render_functions import render_all

if TYPE_CHECKING:
    import tcod.tileset

SCREEN_WIDTH = 80
SCREEN_HEIGHT = 50


def _load_tileset() -> tcod.tileset.Tileset:
    """Load a font for the console, building one procedurally if none exists."""
    candidates = [
        Path(__file__).parent / "data" / "fonts" / "dejavu10x10.ttf",
        Path(__file__).parent / "data" / "fonts" / "dejavu.ttf",
        Path("C:/Windows/Fonts/consola.ttf"),
        Path("C:/Windows/Fonts/arial.ttf"),
        Path("/usr/share/fonts/truetype/dejavu/DejaVuSansMono.ttf"),
        Path("/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf"),
        Path("/Library/Fonts/Arial.ttf"),
    ]
    for path in candidates:
        if path.exists():
            return tcod.tileset.load_truetype_font(
                str(path), tile_width=16, tile_height=16
            )
    return _build_pil_tileset(candidates)


def _build_pil_tileset(candidates: list[Path]) -> tcod.tileset.Tileset:
    """Render an ASCII tileset with PIL so the game runs without asset files."""
    from PIL import Image, ImageDraw, ImageFont

    size = 16
    font = None
    for candidate in candidates:
        if candidate.suffix.lower() in (".ttf", ".otf") and candidate.exists():
            try:
                font = ImageFont.truetype(str(candidate), size - 2)
                break
            except Exception:
                continue
    if font is None:
        font = ImageFont.load_default()

    tileset = tcod.tileset.Tileset(size, size)
    for codepoint in range(32, 127):
        img = Image.new("RGB", (size, size), (0, 0, 0))
        draw = ImageDraw.Draw(img)
        glyph = chr(codepoint)
        bbox = draw.textbbox((0, 0), glyph, font=font)
        box_w = bbox[2] - bbox[0]
        box_h = bbox[3] - bbox[1]
        draw.text(
            ((size - box_w) / 2 - bbox[0], (size - box_h) / 2 - bbox[1]),
            glyph,
            fill=(255, 255, 255),
            font=font,
        )
        tileset.set_tile(codepoint, np.array(img, dtype=np.uint8))
    return tileset


def main() -> None:
    registry = tcod.ecs.Registry()
    log = MessageLog(capacity=8)

    # --- Generate the dungeon. ------------------------------------------
    dungeon = generate_dungeon(
        max_rooms=30,
        room_min_size=6,
        room_max_size=10,
        map_width=SCREEN_WIDTH,
        map_height=SCREEN_HEIGHT,
    )

    # --- Create the player in the first room. ---------------------------
    first_room = dungeon.rooms[0]
    player_x, player_y = first_room.center
    player = create_player(registry, player_x, player_y)

    # --- Populate the dungeon with enemies and items. -------------------
    place_enemies(registry, dungeon, skip_room=0)
    place_items(registry, dungeon, skip_room=0)

    compute_fov(dungeon, player_x, player_y)

    # --- Pathfinder used by the hostile/fleeing AI. ---------------------
    graph = create_pathfinder(dungeon)

    console = tcod.console.Console(SCREEN_WIDTH, SCREEN_HEIGHT, order="C")
    tileset = _load_tileset()
    game_over = False
    current_menu: str | None = None

    with tcod.context.new(
        console=console,
        tileset=tileset,
        title="Chapter 16: Equipment",
    ) as context:
        needs_render = True

        while True:
            if needs_render:
                render_all(console, dungeon, registry, player, list(log), menu=current_menu)
                if game_over:
                    console.print(
                        x=SCREEN_WIDTH // 2 - 12,
                        y=SCREEN_HEIGHT // 2,
                        string="[ press any key to exit ]",
                        fg=(255, 255, 0),
                    )
                context.present(console)
                needs_render = False

            for event in tcod.event.wait():
                if isinstance(event, tcod.event.Quit):
                    raise SystemExit()
                if not isinstance(event, tcod.event.KeyDown):
                    continue
                if game_over:
                    raise SystemExit()

                if current_menu is not None:
                    action = handle_menu_input(event, player)
                    if isinstance(action, MenuCancelAction):
                        current_menu = None
                        needs_render = True
                        continue
                    if isinstance(action, MenuSelectAction):
                        if current_menu == "equip":
                            equip_selection(player, action.index, log)
                        elif current_menu == "unequip":
                            unequip_selection(player, action.index, log)
                        current_menu = None
                        turn_spent = True
                    else:
                        continue
                else:
                    if event.sym == tcod.event.KeySym.ESCAPE:
                        raise SystemExit()

                    action = handle_input(event, player)
                    if action is None:
                        continue

                    if isinstance(action, EquipmentMenuAction):
                        current_menu = "equip"
                        needs_render = True
                        continue
                    if isinstance(action, UnequipMenuAction):
                        current_menu = "unequip"
                        needs_render = True
                        continue

                    turn_spent = process_player_action(
                        action, registry, dungeon, log
                    )
                    if not turn_spent:
                        continue

                # ---- Update the field of view. ----------------------
                ppos = player.components[Position]
                compute_fov(dungeon, ppos.x, ppos.y)

                # ---- Monster AI turns (pathfinding + behaviours). ---
                process_ai_turns(registry, dungeon, player, graph)

                # ---- Resolve melee from adjacent/overlapping foes. --
                resolve_enemy_attacks(registry, dungeon, player, log)

                # ---- Clean up the dead and award XP. ----------------
                remove_dead_entities(registry, log, player)

                if player.components[Fighter].hp <= 0:
                    log.add("You have been defeated!", (255, 0, 0))
                    game_over = True

                needs_render = True


if __name__ == "__main__":
    main()

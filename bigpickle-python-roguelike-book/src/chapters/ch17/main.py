"""Chapter 17: The Message Log."""
from __future__ import annotations

from pathlib import Path
from typing import TYPE_CHECKING

import numpy as np
import tcod
import tcod.ecs
import tcod.event

from actions import BumpAction, WaitAction
from ai_system import create_pathfinder, process_ai_turns
from combat import (
    compute_fov,
    process_player_action,
    remove_dead_entities,
    resolve_enemy_attacks,
)
from components import Fighter, MessageLog, Position
from factories import create_player, place_enemies, place_items
from input_handlers import handle_input
from palette import GRAY, HISTORY_HINT, PANEL_TEXT, WHITE
from procgen import generate_dungeon
from render_functions import MAP_HEIGHT, PANEL_HEIGHT, render_all

if TYPE_CHECKING:
    import tcod.tileset

SCREEN_WIDTH = 80
SCREEN_HEIGHT = MAP_HEIGHT + PANEL_HEIGHT


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


def _add_welcome(log: MessageLog) -> None:
    """Print the opening messages and a control summary."""
    log.add("You descend into the dungeon.", WHITE)
    log.add(
        "g:pickup  f/u:use  e:equip  .:wait  v:log history  ?:controls",
        GRAY,
    )


def render_history(
    console: tcod.console.Console,
    log: MessageLog,
    offset: int,
) -> None:
    """Render the full, scrollable message log over the whole screen."""
    console.clear()
    console.draw_frame(
        x=0,
        y=0,
        width=console.width,
        height=console.height,
        title="Message Log",
        fg=PANEL_TEXT,
        bg=(40, 40, 40),
    )

    total = len(log.messages)
    inner_width = console.width - 4
    inner_height = console.height - 5
    end = max(0, total - offset)
    start = max(0, end - inner_height)
    visible = log.messages[start:end]

    for i, msg in enumerate(visible):
        y = 1 + i
        console.print(x=2, y=y, string=msg.text[:inner_width], fg=msg.color)

    page_start = total - len(visible)
    footer = (
        f"Showing {page_start + 1}-{page_start + len(visible)} of {total}   "
        f"[up/down] scroll   [esc/space] close"
    )
    console.print(x=2, y=console.height - 2, string=footer[: inner_width], fg=HISTORY_HINT)


def main() -> None:
    registry = tcod.ecs.Registry()
    log = MessageLog(max_messages=100)
    _add_welcome(log)

    # --- Generate the dungeon. ------------------------------------------
    dungeon = generate_dungeon(
        max_rooms=30,
        room_min_size=6,
        room_max_size=10,
        map_width=SCREEN_WIDTH,
        map_height=MAP_HEIGHT,
    )

    # --- Create the player in the first room. ---------------------------
    first_room = dungeon.rooms[0]
    player_x, player_y = first_room.center
    player = create_player(registry, player_x, player_y)

    # --- Populate the dungeon with enemies and items. -------------------
    place_enemies(registry, dungeon, skip_room=0)
    place_items(registry, dungeon, skip_room=0)

    compute_fov(dungeon, player_x, player_y)

    graph = create_pathfinder(dungeon)

    console = tcod.console.Console(SCREEN_WIDTH, SCREEN_HEIGHT, order="C")
    tileset = _load_tileset()
    game_over = False
    viewing_history = False
    history_offset = 0

    with tcod.context.new(
        console=console,
        tileset=tileset,
        title="Chapter 17: The Message Log",
    ) as context:
        needs_render = True

        while True:
            if needs_render:
                if viewing_history:
                    render_history(console, log, history_offset)
                else:
                    render_all(console, dungeon, registry, player, log)
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

                # --- Global keys. -------------------------------------
                if event.sym == tcod.event.KeySym.ESCAPE:
                    if viewing_history:
                        viewing_history = False
                        needs_render = True
                        continue
                    raise SystemExit()

                # --- Log history view controls. ------------------------
                if viewing_history:
                    if event.sym in (
                        tcod.event.KeySym.UP,
                        tcod.event.KeySym.k,
                        tcod.event.KeySym.PAGEUP,
                    ):
                        history_offset += 3
                        needs_render = True
                    elif event.sym in (
                        tcod.event.KeySym.DOWN,
                        tcod.event.KeySym.j,
                        tcod.event.KeySym.PAGEDOWN,
                    ):
                        history_offset = max(0, history_offset - 3)
                        needs_render = True
                    elif event.sym in (
                        tcod.event.KeySym.SPACE,
                        tcod.event.KeySym.RETURN,
                        tcod.event.KeySym.v,
                    ):
                        viewing_history = False
                        needs_render = True
                    continue

                if game_over:
                    raise SystemExit()

                # --- Open the history view. ----------------------------
                if event.sym == tcod.event.KeySym.v:
                    viewing_history = True
                    history_offset = 0
                    needs_render = True
                    continue

                action = handle_input(event, player)
                if action is None:
                    continue

                # ---- Player turn. --------------------------------------
                turn_spent = process_player_action(
                    action, registry, dungeon, log
                )
                if not turn_spent:
                    continue

                # ---- Update the field of view. -------------------------
                ppos = player.components[Position]
                compute_fov(dungeon, ppos.x, ppos.y)

                # ---- Monster AI turns. ---------------------------------
                process_ai_turns(registry, dungeon, player, graph, log)

                # ---- Resolve melee from adjacent/overlapping foes. -----
                resolve_enemy_attacks(registry, dungeon, player, log)

                # ---- Clean up the dead and award XP. -------------------
                remove_dead_entities(registry, log, player)

                if player.components[Fighter].hp <= 0:
                    log.add("You have been defeated!", (255, 0, 0))
                    game_over = True

                needs_render = True


if __name__ == "__main__":
    main()

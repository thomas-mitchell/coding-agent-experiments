"""Chapter 21: Experience, Leveling, and Skills."""
from __future__ import annotations

from pathlib import Path
from typing import TYPE_CHECKING

import numpy as np
import tcod
import tcod.ecs
import tcod.event

from actions import CastAction, LevelUpChoiceAction
from ai_system import create_pathfinder, process_ai_turns
from color import GRAY, HISTORY_HINT, MAGENTA, PANEL_TEXT, WHITE
from combat import (
    ActionResult,
    compute_fov,
    process_player_action,
    remove_dead_entities,
    resolve_enemy_attacks,
)
from components import Fighter, GameWorld, MessageLog, Position
from dungeon_level import descend_level
from factories import create_player, place_enemies, place_items
from input_handlers import handle_input, handle_level_up_input, handle_targeting_input
from procgen import generate_dungeon, player_start, stairs_position
from render_functions import MAP_HEIGHT, PANEL_HEIGHT, render_all

if TYPE_CHECKING:
    import tcod.tileset

SCREEN_WIDTH = 80
SCREEN_HEIGHT = MAP_HEIGHT + PANEL_HEIGHT

# The game alternates between a normal "playing" state and the modal level-up
# menu that appears whenever the player banks a new level.
PLAYING = "playing"
LEVEL_UP = "level_up"


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


def _build_first_level(registry, game_map, dungeon_level):
    """Generate and populate the very first dungeon floor."""
    sx, sy = player_start(game_map)
    player = create_player(registry, sx, sy)
    place_enemies(registry, game_map, dungeon_level=dungeon_level, skip_room=0)
    place_items(registry, game_map, dungeon_level=dungeon_level, skip_room=0)
    px, py = stairs_position(game_map)
    from dungeon_level import create_stairs

    create_stairs(registry, px, py)
    compute_fov(game_map, sx, sy)
    return player


def _add_welcome(log: MessageLog) -> None:
    """Print the opening messages and a control summary."""
    log.add("You descend into the dungeon.", WHITE)
    log.add(
        "g:pickup  f/u:use  e:equip  .:wait  >:stairs  v:log history  ?:controls",
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

    world = registry.new_entity()
    world.components[GameWorld] = GameWorld(dungeon_level=1)
    dungeon_level = 1

    # --- Generate the first dungeon. ------------------------------------
    dungeon = generate_dungeon(
        max_rooms=30,
        room_min_size=6,
        room_max_size=10,
        map_width=SCREEN_WIDTH,
        map_height=MAP_HEIGHT,
    )
    player = _build_first_level(registry, dungeon, dungeon_level)

    graph = create_pathfinder(dungeon)

    console = tcod.console.Console(SCREEN_WIDTH, SCREEN_HEIGHT, order="C")
    tileset = _load_tileset()
    game_over = False
    game_state = PLAYING
    viewing_history = False
    history_offset = 0
    targeting = None

    with tcod.context.new(
        console=console,
        tileset=tileset,
        title="Chapter 21: Experience, Leveling, and Skills",
    ) as context:
        needs_render = True

        while True:
            if needs_render:
                if viewing_history:
                    render_history(console, log, history_offset)
                elif game_state == LEVEL_UP:
                    render_all(
                        console,
                        dungeon,
                        registry,
                        player,
                        log,
                        dungeon_level,
                        targeting,
                        level_up=True,
                    )
                else:
                    render_all(
                        console,
                        dungeon,
                        registry,
                        player,
                        log,
                        dungeon_level,
                        targeting,
                    )
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
                    if game_state == LEVEL_UP and not game_over:
                        # Escape defers the choice: the level-up menu returns
                        # once the player next spends a turn.
                        game_state = PLAYING
                        needs_render = True
                        continue
                    if targeting is not None and targeting.active:
                        from targeting import cancel_targeting

                        cancel_targeting(targeting)
                        targeting = None
                        needs_render = True
                        continue
                    if viewing_history:
                        viewing_history = False
                        needs_render = True
                        continue
                    raise SystemExit()

                # --- Loop back into level-up selection. -----------------
                if game_state == LEVEL_UP and not game_over:
                    choice = handle_level_up_input(event, player)
                    if choice is not None:
                        process_player_action(choice, registry, dungeon, log)
                        from components import XP

                        player_xp = player.components[XP]
                        if player_xp.level_ups_pending > 0:
                            needs_render = True
                            continue
                        # No more pending level-ups: resume play.
                        game_state = PLAYING
                        needs_render = True
                    continue

                # --- Targeting mode. ------------------------------------
                if targeting is not None and targeting.active:
                    cmd = handle_targeting_input(
                        event,
                        targeting,
                        dungeon.width,
                        dungeon.height,
                    )
                    if cmd == "move":
                        needs_render = True
                        continue
                    if cmd == "cancel":
                        from targeting import cancel_targeting

                        cancel_targeting(targeting)
                        targeting = None
                        needs_render = True
                        continue
                    if cmd == "cast":
                        cast_result = _do_cast(
                            event,
                            targeting,
                            player,
                            registry,
                            dungeon,
                            log,
                        )
                        new_targeting, turn_spent, new_dungeon, new_level = cast_result
                        targeting = new_targeting
                        if new_dungeon is not None:
                            dungeon = new_dungeon
                            graph = create_pathfinder(dungeon)
                        if new_level is not None:
                            dungeon_level = new_level
                        if turn_spent:
                            needs_render = _resolve_turn(
                                player,
                                registry,
                                dungeon,
                                graph,
                                log,
                            )
                            if player.components[Fighter].hp <= 0:
                                game_over = True
                            needs_render = True
                        continue
                    continue

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
                result = process_player_action(action, registry, dungeon, log)

                # Enter targeting mode for a targeted spell.
                if result.targeting is not None:
                    targeting = result.targeting
                    needs_render = True
                    continue

                if result.descend:
                    dungeon, dungeon_level = descend_level(
                        registry, dungeon, player, dungeon_level, log
                    )
                    graph = create_pathfinder(dungeon)
                    needs_render = True
                    continue

                if not result.spent_turn:
                    continue

                # ---- Resolve the consequences of a spent turn. --------
                needs_render = _resolve_turn(player, registry, dungeon, graph, log)

                if player.components[Fighter].hp <= 0:
                    log.add("You have been defeated!", (255, 0, 0))
                    game_over = True

                # If leveling up is pending, show the level-up menu.
                from components import XP

                if player.components[XP].level_ups_pending > 0 and not game_over:
                    game_state = LEVEL_UP

                needs_render = True


def _do_cast(event, targeting, player, registry, dungeon, log):
    """Confirm a targeted cast from the targeting mode.

    Returns ``(new_targeting, turn_spent, new_dungeon, new_level)``.
    """
    from targeting import cancel_targeting

    # The cursor must be within the spell's range to cast.
    origin_x, origin_y = player.components[Position].x, player.components[Position].y
    if targeting.max_range > 0:
        if max(abs(targeting.cursor_x - origin_x), abs(targeting.cursor_y - origin_y)) > targeting.max_range:
            log.add("That is out of range.", GRAY)
            return targeting, False, None, None

    cast_action = CastAction(
        entity=player,
        item=targeting.item,
        target=(targeting.cursor_x, targeting.cursor_y),
    )
    result = process_player_action(cast_action, registry, dungeon, log)
    cancel_targeting(targeting)
    return None, result.spent_turn, None, None


def _resolve_turn(player, registry, dungeon, graph, log) -> bool:
    """Run the AI and cleanup after the player spends a turn."""
    ppos = player.components[Position]
    compute_fov(dungeon, ppos.x, ppos.y)

    process_ai_turns(registry, dungeon, player, graph, log)
    resolve_enemy_attacks(registry, dungeon, player, log)
    remove_dead_entities(registry, log, player)
    return True


if __name__ == "__main__":
    main()

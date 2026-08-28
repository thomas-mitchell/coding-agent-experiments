"""Chapter 15: Items and Inventory."""
from __future__ import annotations

from pathlib import Path
from typing import TYPE_CHECKING

import numpy as np
import tcod
import tcod.ecs
import tcod.event

from actions import (
    Action,
    BumpAction,
    DropAction,
    PickupAction,
    UseItemAction,
    WaitAction,
)
from ai_system import create_pathfinder, process_ai_turns
from combat import (
    compute_fov,
    process_bump,
    remove_dead_entities,
    resolve_enemy_attacks,
)
from components import Fighter, Position
from factories import create_player, place_enemies, place_items
from game_map import GameMap
from input_handlers import handle_input
from items import drop_item, pickup_item, use_item
from message_log import MessageLog
from procgen import generate_dungeon
from render_functions import render_all

if TYPE_CHECKING:
    import tcod.tileset

SCREEN_WIDTH = 80
SCREEN_HEIGHT = 50


def _load_tileset() -> tcod.tileset.Tileset:
    """Load a font for the console, building one procedurally if absent."""
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
    """Render an ASCII tileset with PIL so the game runs without assets."""
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


def _is_action_success(
    action: Action,
    registry: tcod.ecs.Registry,
    dungeon: GameMap,
    log: MessageLog,
    player,
) -> bool:
    """Process a player action. Returns True if a turn was spent."""
    if isinstance(action, BumpAction):
        return process_bump(registry, dungeon, player, action.dx, action.dy, log)
    if isinstance(action, WaitAction):
        return True
    if isinstance(action, PickupAction):
        return pickup_item(registry, player, log)
    if isinstance(action, UseItemAction):
        return use_item(registry, player, action.index, dungeon, log)
    if isinstance(action, DropAction) and action.index >= 0:
        return drop_item(registry, player, action.index, log)
    return False


def main() -> None:
    registry = tcod.ecs.Registry()
    log = MessageLog(capacity=10)

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

    # Give the player a health potion to start with.
    from components import Inventory
    from factories.items import create_health_potion
    starter = create_health_potion(registry, player_x, player_y)
    player.components[Inventory].items.append(starter)
    starter.components.clear()
    starter.tags.clear()

    compute_fov(dungeon, player_x, player_y)

    # --- Pathfinder used by the hostile/fleeing AI. ---------------------
    graph = create_pathfinder(dungeon)

    console = tcod.console.Console(SCREEN_WIDTH, SCREEN_HEIGHT, order="C")
    tileset = _load_tileset()
    game_over = False
    show_inventory = False
    drop_mode = False

    with tcod.context.new(
        console=console,
        tileset=tileset,
        title="Chapter 15: Items and Inventory",
    ) as context:
        needs_render = True

        while True:
            if needs_render:
                render_all(
                    console,
                    dungeon,
                    registry,
                    player,
                    log,
                    show_inventory=show_inventory,
                    drop_mode=drop_mode,
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
                if game_over:
                    raise SystemExit()

                # Mode toggles handled at top level.
                if event.sym == tcod.event.KeySym.ESCAPE:
                    if drop_mode:
                        drop_mode = False
                        needs_render = True
                        continue
                    if show_inventory:
                        show_inventory = False
                        needs_render = True
                        continue
                    raise SystemExit()

                if drop_mode:
                    action = handle_input(event, player, drop_mode=True)
                    if isinstance(action, DropAction) and action.index >= 0:
                        spent = _is_action_success(
                            action, registry, dungeon, log, player
                        )
                        drop_mode = False
                        show_inventory = False
                        if not spent:
                            needs_render = True
                            continue
                        _advance_after_turn(
                            registry, dungeon, log, player, graph
                        )
                        needs_render = True
                    else:
                        needs_render = True
                    continue

                if event.sym == tcod.event.KeySym.d:
                    if len(player.components[Inventory].items) > 0:
                        drop_mode = True
                        show_inventory = True
                        needs_render = True
                    continue

                if event.sym == tcod.event.KeySym.i:
                    show_inventory = not show_inventory
                    needs_render = True
                    continue

                action = handle_input(event, player)
                if action is None:
                    continue

                # ---- Player turn. ------------------------------------
                turn_spent = _is_action_success(
                    action, registry, dungeon, log, player
                )
                if not turn_spent:
                    needs_render = True
                    continue

                _advance_after_turn(registry, dungeon, log, player, graph)

                if player.components[Fighter].hp <= 0:
                    log.add("You have been defeated!", fg=(255, 0, 0))
                    game_over = True

                needs_render = True


def _advance_after_turn(
    registry: tcod.ecs.Registry,
    dungeon: GameMap,
    log: MessageLog,
    player,
    graph,
) -> None:
    """Run everything that happens after the player spends a turn."""
    import items as _items

    # Update the field of view.
    ppos = player.components[Position]
    compute_fov(dungeon, ppos.x, ppos.y)

    # Monster AI turns (pathfinding + behaviours).
    process_ai_turns(registry, dungeon, player, graph)

    # Resolve melee from adjacent/overlapping foes.
    resolve_enemy_attacks(registry, dungeon, player, log)

    # Clean up the dead, awarding XP and dropping carried items.
    remove_dead_entities(registry, log, player)


if __name__ == "__main__":
    main()

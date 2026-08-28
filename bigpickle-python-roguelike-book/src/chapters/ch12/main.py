"""Chapter 12: The Turn-Based Game Loop with Enemy AI."""
from __future__ import annotations

import tcod
import tcod.ecs
import tcod.event

from actions import BumpAction, WaitAction
from components import Fighter, Position
from factories import create_player, place_enemies
from game_map import GameMap
from input_handlers import handle_input
from procgen import generate_dungeon
from render_functions import render_all
from systems import (
    compute_fov,
    process_action,
    process_enemy_turns,
    remove_dead_entities,
)

SCREEN_WIDTH = 80
SCREEN_HEIGHT = 50

TILESET = tcod.tileset.load_truetype_font(
    "data/fonts/dejavu10x10.ttf", tile_width=16, tile_height=16
)


def main() -> None:
    registry = tcod.ecs.Registry()
    message_log: list[str] = []

    # --- Generate the dungeon -------------------------------------------
    dungeon = generate_dungeon(
        max_rooms=30,
        room_min_size=6,
        room_max_size=10,
        map_width=SCREEN_WIDTH,
        map_height=SCREEN_HEIGHT,
    )

    # --- Create the player in the first room ---------------------------
    first_room = dungeon.rooms[0]
    player_x, player_y = first_room.center
    player = create_player(registry, player_x, player_y)

    # --- Populate the remaining rooms with enemies ---------------------
    place_enemies(registry, dungeon, skip_room=0)

    # Store the map on the registry so render_functions can access it.
    registry.context["game_map"] = dungeon

    # Initial field-of-view computation.
    compute_fov(dungeon, player_x, player_y)

    console = tcod.console.Console(SCREEN_WIDTH, SCREEN_HEIGHT, order="C")
    game_over = False

    with tcod.context.new(
        console=console,
        tileset=TILESET,
        title="Chapter 12: The Turn-Based Game Loop",
    ) as context:
        needs_render = True

        while True:
            # ---- Render ------------------------------------------------
            if needs_render:
                render_all(console, dungeon, registry, player)

                # HUD -- hit points.
                hp = player.components[Fighter]
                console.print(
                    x=1,
                    y=SCREEN_HEIGHT - 1,
                    string=f"HP: {hp.hp}/{hp.max_hp}",
                    fg=(255, 255, 255),
                )

                # Recent message log (last 4 lines, drawn above HP).
                visible_msgs = message_log[-4:]
                for i, msg in enumerate(visible_msgs):
                    console.print(
                        x=1,
                        y=SCREEN_HEIGHT - 5 - (len(visible_msgs) - 1 - i),
                        string=msg,
                        fg=(200, 200, 200),
                    )

                if game_over:
                    console.print(
                        x=SCREEN_WIDTH // 2 - 10,
                        y=SCREEN_HEIGHT // 2,
                        string="[ press any key to exit ]",
                        fg=(255, 255, 0),
                    )

                context.present(console)
                needs_render = False

            # ---- Handle events -----------------------------------------
            for event in tcod.event.wait():
                if isinstance(event, tcod.event.Quit):
                    raise SystemExit()

                if not isinstance(event, tcod.event.KeyDown):
                    continue

                if event.sym == tcod.event.KeySym.ESCAPE:
                    raise SystemExit()

                if game_over:
                    raise SystemExit()

                action = handle_input(event, player)
                if action is None:
                    continue

                # ---- Process one full turn ------------------------------
                turn_spent = process_action(action, registry, dungeon)
                if not turn_spent:
                    continue

                # 1. Update field of view.
                ppos = player.components[Position]
                compute_fov(dungeon, ppos.x, ppos.y)

                # 2. Let every visible enemy take its turn.
                process_enemy_turns(registry, dungeon, player)

                # 3. Remove anything that has been killed.
                dead_messages = remove_dead_entities(registry)
                message_log.extend(dead_messages)

                # 4. Check whether the player has died.
                if player.components[Fighter].hp <= 0:
                    message_log.append("You have been defeated!")
                    game_over = True

                needs_render = True


if __name__ == "__main__":
    main()

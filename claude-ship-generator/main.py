"""Ship roguelike skeleton: generate a ship and walk around it."""

from __future__ import annotations

import argparse
import random
from pathlib import Path

import tcod

from game.entity import Player
from game.input import MOVE_KEYS, QUIT_KEY, REGENERATE_KEY, TOGGLE_LABELS_KEY
from game.render import render
from ship import Ship, generate_ship

CONSOLE_W, CONSOLE_H = 96, 46
FONT = Path("C:/Windows/Fonts/consola.ttf")


def load_tileset() -> tcod.tileset.Tileset | None:
    if FONT.exists():
        return tcod.tileset.load_truetype_font(FONT, 10, 18)
    return None  # tcod falls back to its built-in font


def new_game(seed: int) -> tuple[Ship, Player]:
    ship = generate_ship(seed)
    return ship, Player(*ship.spawn)


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--seed", type=int, default=None)
    args = parser.parse_args()

    seed = args.seed if args.seed is not None else random.randrange(1_000_000)
    ship, player = new_game(seed)
    show_labels = True

    console = tcod.console.Console(CONSOLE_W, CONSOLE_H, order="F")
    with tcod.context.new(console=console, tileset=load_tileset(), title="Derelict", vsync=True) as context:
        while True:
            console.clear()
            render(console, ship, player, show_labels)
            context.present(console, keep_aspect=True)

            for event in tcod.event.wait():
                if isinstance(event, tcod.event.Quit):
                    raise SystemExit
                if not isinstance(event, tcod.event.KeyDown):
                    continue
                if event.sym == QUIT_KEY:
                    raise SystemExit
                if event.sym == REGENERATE_KEY:
                    ship, player = new_game(random.randrange(1_000_000))
                elif event.sym == TOGGLE_LABELS_KEY:
                    show_labels = not show_labels
                elif event.sym in MOVE_KEYS:
                    player.try_move(ship, *MOVE_KEYS[event.sym])


if __name__ == "__main__":
    main()

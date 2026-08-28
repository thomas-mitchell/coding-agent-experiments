"""Chapter 4: Hello tcod - A simple movable player on screen."""
from __future__ import annotations

import tcod
import tcod.event

SCREEN_WIDTH = 80
SCREEN_HEIGHT = 50

TILESET = tcod.tileset.load_truetype_font(
    "data/fonts/dejavu10x10.ttf", tile_width=16, tile_height=16
)


def main() -> None:
    player_x = SCREEN_WIDTH // 2
    player_y = SCREEN_HEIGHT // 2

    console = tcod.console.Console(SCREEN_WIDTH, SCREEN_HEIGHT, order="C")

    with tcod.context.new(
        console=console,
        tileset=TILESET,
        title="Chapter 4: Hello tcod",
    ) as context:
        while True:
            console.clear()
            console.print(
                x=player_x, y=player_y, string="@", fg=(255, 255, 255)
            )
            console.print(
                x=1, y=0, string="Arrow keys to move. ESC to quit.",
                fg=(128, 128, 128),
            )

            context.present(console)

            for event in tcod.event.wait():
                if isinstance(event, tcod.event.Quit):
                    raise SystemExit()
                elif isinstance(event, tcod.event.KeyDown):
                    if event.sym == tcod.event.KeySym.ESCAPE:
                        raise SystemExit()
                    elif event.sym == tcod.event.KeySym.UP:
                        player_y = max(0, player_y - 1)
                    elif event.sym == tcod.event.KeySym.DOWN:
                        player_y = min(SCREEN_HEIGHT - 1, player_y + 1)
                    elif event.sym == tcod.event.KeySym.LEFT:
                        player_x = max(0, player_x - 1)
                    elif event.sym == tcod.event.KeySym.RIGHT:
                        player_x = min(SCREEN_WIDTH - 1, player_x + 1)


if __name__ == "__main__":
    main()

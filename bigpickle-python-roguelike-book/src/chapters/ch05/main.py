"""Chapter 5: Game State - ECS-based state management."""
from __future__ import annotations

import attrs
import tcod
import tcod.ecs
import tcod.event


@attrs.define
class Position:
    x: int = 0
    y: int = 0


@attrs.define
class GameState:
    current_state: str = "in_game"


SCREEN_WIDTH = 80
SCREEN_HEIGHT = 50

TILESET = tcod.tileset.load_truetype_font(
    "data/fonts/dejavu10x10.ttf", tile_width=16, tile_height=16
)


def main() -> None:
    registry = tcod.ecs.Registry()

    # Global game state stored on registry[None]
    global_entity = registry[None]
    global_entity.components[GameState] = GameState(current_state="in_game")

    # Player entity
    player = registry.new_entity()
    player.components[Position] = Position(
        x=SCREEN_WIDTH // 2, y=SCREEN_HEIGHT // 2
    )
    player.tags.add("player")

    console = tcod.console.Console(SCREEN_WIDTH, SCREEN_HEIGHT, order="C")

    with tcod.context.new(
        console=console,
        tileset=TILESET,
        title="Chapter 5: Game State",
    ) as context:
        while True:
            current_state = registry[None].components[GameState].current_state

            if current_state == "in_game":
                console.clear()
                # Draw player from ECS
                for entity in registry.Q.all_of(tags=["player"]):
                    pos = entity.components[Position]
                    console.print(x=pos.x, y=pos.y, string="@", fg=(255, 255, 255))

                console.print(
                    x=1, y=0, string="Arrow keys: move | ESC: quit",
                    fg=(128, 128, 128),
                )
                context.present(console)

            for event in tcod.event.wait():
                if isinstance(event, tcod.event.Quit):
                    raise SystemExit()
                elif isinstance(event, tcod.event.KeyDown):
                    if event.sym == tcod.event.KeySym.ESCAPE:
                        raise SystemExit()

                    if current_state == "in_game":
                        for entity in registry.Q.all_of(tags=["player"]):
                            pos = entity.components[Position]
                            if event.sym == tcod.event.KeySym.UP:
                                pos.y = max(0, pos.y - 1)
                            elif event.sym == tcod.event.KeySym.DOWN:
                                pos.y = min(SCREEN_HEIGHT - 1, pos.y + 1)
                            elif event.sym == tcod.event.KeySym.LEFT:
                                pos.x = max(0, pos.x - 1)
                            elif event.sym == tcod.event.KeySym.RIGHT:
                                pos.x = min(SCREEN_WIDTH - 1, pos.x + 1)


if __name__ == "__main__":
    main()

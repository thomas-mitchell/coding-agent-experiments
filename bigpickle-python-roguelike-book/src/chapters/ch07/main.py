"""Chapter 7: Movement and Input - action-based movement with the ECS."""
from __future__ import annotations

import tcod
import tcod.ecs
import tcod.event

from components import Position, Renderable, Name, Fighter, XP, AI, AIKind
from actions import BumpAction, WaitAction
from input_handlers import handle_input

SCREEN_WIDTH = 80
SCREEN_HEIGHT = 50

TILESET = tcod.tileset.load_truetype_font(
    "data/fonts/dejavu10x10.ttf", tile_width=16, tile_height=16
)


def create_player(registry: tcod.ecs.Registry) -> tcod.ecs.Entity:
    player = registry.new_entity()
    player.components |= {
        Position: Position(x=40, y=25),
        Renderable: Renderable(char="@", fg=(255, 255, 255)),
        Name: Name(name="Player"),
        Fighter: Fighter(hp=30, max_hp=30, power=5, defense=2),
        XP: XP(),
    }
    player.tags.add("player")
    player.tags.add("blocks_movement")
    return player


def create_enemies(registry: tcod.ecs.Registry) -> None:
    enemies = [
        (15, 10, "k", (255, 0, 0), "Kobold", 8, 3, 0),
        (60, 30, "o", (180, 0, 0), "Orc", 15, 5, 2),
        (25, 35, "T", (0, 128, 0), "Troll", 25, 8, 4),
    ]
    for x, y, char, fg, name, hp, power, defense in enemies:
        entity = registry.new_entity()
        entity.components |= {
            Position: Position(x=x, y=y),
            Renderable: Renderable(char=char, fg=fg),
            Name: Name(name=name),
            Fighter: Fighter(hp=hp, max_hp=hp, power=power, defense=defense),
            AI: AI(kind=AIKind.HOSTILE),
        }
        entity.tags.add("enemy")
        entity.tags.add("blocks_movement")


def process_action(action: BumpAction | WaitAction, registry: tcod.ecs.Registry) -> bool:
    """Process an action. Returns True if the action consumed a turn."""
    if isinstance(action, WaitAction):
        return True

    if isinstance(action, BumpAction):
        pos = action.entity.components[Position]
        target_x = pos.x + action.dx
        target_y = pos.y + action.dy

        # Check map bounds
        if target_x < 0 or target_x >= SCREEN_WIDTH or target_y < 1 or target_y >= SCREEN_HEIGHT:
            return False

        # Check entity collision
        for other in registry.Q.all_of(tags=["blocks_movement"]):
            other_pos = other.components[Position]
            if other_pos.x == target_x and other_pos.y == target_y and other is not action.entity:
                # Bumped into something - combat will come later
                return False

        # Move
        pos.x = target_x
        pos.y = target_y
        return True

    return False


def main() -> None:
    registry = tcod.ecs.Registry()
    player = create_player(registry)
    create_enemies(registry)

    console = tcod.console.Console(SCREEN_WIDTH, SCREEN_HEIGHT, order="C")

    with tcod.context.new(
        console=console,
        tileset=TILESET,
        title="Chapter 7: Movement and Input",
    ) as context:
        needs_render = True

        while True:
            if needs_render:
                console.clear()
                console.print(x=1, y=0, string="Vi keys: h/j/k/l/y/u/b/n  |  Arrows: move  |  .: wait  |  ESC: quit", fg=(128, 128, 128))

                for entity, pos, rend in registry.Q[Position, Renderable]:
                    if 0 <= pos.x < SCREEN_WIDTH and 1 <= pos.y < SCREEN_HEIGHT:
                        console.print(x=pos.x, y=pos.y, string=rend.char, fg=rend.fg)

                context.present(console)
                needs_render = False

            for event in tcod.event.wait():
                if isinstance(event, tcod.event.Quit):
                    raise SystemExit()
                elif isinstance(event, tcod.event.KeyDown):
                    if event.sym == tcod.event.KeySym.ESCAPE:
                        raise SystemExit()

                    action = handle_input(event, player)
                    if action is not None:
                        consumed = process_action(action, registry)
                        if consumed:
                            needs_render = True


if __name__ == "__main__":
    main()

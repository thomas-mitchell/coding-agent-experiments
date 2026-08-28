"""Chapter 9: Procedural Dungeon Generation with BSP."""
from __future__ import annotations

import random
import tcod
import tcod.ecs
import tcod.event

from components import Position, Renderable, Name, Fighter, XP, AI, AIKind
from actions import BumpAction, WaitAction
from game_map import GameMap, Room
from procgen import generate_dungeon
from input_handlers import handle_input
from render_functions import render_all

SCREEN_WIDTH = 80
SCREEN_HEIGHT = 50

TILESET = tcod.tileset.load_truetype_font(
    "data/fonts/dejavu10x10.ttf", tile_width=16, tile_height=16
)

ENEMY_TEMPLATES = [
    ("k", (255, 0, 0), "Kobold", 8, 3, 0),
    ("o", (180, 0, 0), "Orc", 15, 5, 2),
    ("T", (0, 128, 0), "Troll", 25, 8, 4),
]


def create_player(registry: tcod.ecs.Registry, x: int, y: int) -> tcod.ecs.Entity:
    player = registry.new_entity()
    player.components |= {
        Position: Position(x=x, y=y),
        Renderable: Renderable(char="@", fg=(255, 255, 255)),
        Name: Name(name="Player"),
        Fighter: Fighter(hp=30, max_hp=30, power=5, defense=2),
        XP: XP(),
    }
    player.tags.add("player")
    player.tags.add("blocks_movement")
    return player


def place_enemies(
    registry: tcod.ecs.Registry,
    dungeon: GameMap,
    skip_room: int = 0,
) -> None:
    """Place 2-4 enemies in each room except the one the player starts in."""
    for i, room in enumerate(dungeon.rooms):
        if i == skip_room:
            continue
        num_enemies = random.randint(2, 4)
        placed = 0
        attempts = 0
        while placed < num_enemies and attempts < 50:
            attempts += 1
            x = random.randint(room.x + 1, room.x + room.w - 2)
            y = random.randint(room.y + 1, room.y + room.h - 2)
            # Check that no entity already occupies this tile.
            occupied = False
            for ent, pos in registry.Q[Position]:
                if pos.x == x and pos.y == y:
                    occupied = True
                    break
            if occupied:
                continue
            char, fg, name, hp, power, defense = random.choice(ENEMY_TEMPLATES)
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
            placed += 1


def process_action(
    action: BumpAction | WaitAction,
    registry: tcod.ecs.Registry,
    dungeon: GameMap,
) -> bool:
    """Process an action. Returns True if the action consumed a turn."""
    if isinstance(action, WaitAction):
        return True

    if isinstance(action, BumpAction):
        pos = action.entity.components[Position]
        target_x = pos.x + action.dx
        target_y = pos.y + action.dy

        # Check map bounds and walkability.
        if not dungeon.is_walkable(target_x, target_y):
            return False

        # Check entity collision.
        for other in registry.Q.all_of(tags=["blocks_movement"]):
            other_pos = other.components[Position]
            if other_pos.x == target_x and other_pos.y == target_y and other is not action.entity:
                # Bumped into something - combat will come later.
                return False

        # Move.
        pos.x = target_x
        pos.y = target_y
        return True

    return False


def main() -> None:
    registry = tcod.ecs.Registry()

    dungeon = generate_dungeon(
        max_rooms=30,
        room_min_size=6,
        room_max_size=10,
        map_width=SCREEN_WIDTH,
        map_height=SCREEN_HEIGHT,
    )

    # Place player at the center of the first room.
    first_room = dungeon.rooms[0]
    player_x, player_y = first_room.center
    player = create_player(registry, player_x, player_y)

    # Place enemies in the remaining rooms.
    place_enemies(registry, dungeon, skip_room=0)

    # Store the map on the registry context for render_functions.
    registry.context["game_map"] = dungeon

    # Mark all tiles as explored (FOV comes in the next chapter).
    dungeon.explored[:] = True
    dungeon.visible[:] = True

    console = tcod.console.Console(SCREEN_WIDTH, SCREEN_HEIGHT, order="C")

    with tcod.context.new(
        console=console,
        tileset=TILESET,
        title="Chapter 9: Procedural Dungeon Generation",
    ) as context:
        needs_render = True

        while True:
            if needs_render:
                render_all(console, dungeon, registry, player)

                # Draw a simple HUD line at the bottom.
                fighter = player.components[Fighter]
                hp_bar = f"HP: {fighter.hp}/{fighter.max_hp}"
                console.print(x=1, y=SCREEN_HEIGHT - 1, string=hp_bar, fg=(255, 255, 255))

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
                        if process_action(action, registry, dungeon):
                            needs_render = True


if __name__ == "__main__":
    main()

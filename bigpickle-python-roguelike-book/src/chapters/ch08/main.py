"""Chapter 8 -- game map, tile rendering, and camera scrolling."""
from __future__ import annotations

import tcod
import tcod.console
import tcod.context
import tcod.ecs
import tcod.event

from actions import Action, BumpAction, WaitAction
from components.physical import Position, Renderable
from components.identity import Name
from components.ai import AI, AIKind
from components.combat import Fighter
from game_map import GameMap
from input_handlers import handle_input
from render_functions import render_all

MAP_WIDTH = 80
MAP_HEIGHT = 45
SCREEN_WIDTH = 80
SCREEN_HEIGHT = 50


def make_test_map(width: int, height: int) -> GameMap:
    """Create a simple rectangular room with walls around the edges."""
    from tile_types import FLOOR, WALL

    game_map = GameMap(width, height)

    # Fill the interior with floor tiles.
    game_map.tiles[1 : height - 1, 1 : width - 1] = FLOOR

    # The top and bottom rows are walls.
    game_map.tiles[0, :] = WALL
    game_map.tiles[height - 1, :] = WALL

    # The left and right columns are walls.
    game_map.tiles[:, 0] = WALL
    game_map.tiles[:, width - 1] = WALL

    # Add an inner room to make things more interesting.
    game_map.tiles[10:20, 10:30] = FLOOR
    game_map.tiles[10, 10:30] = WALL
    game_map.tiles[19, 10:30] = WALL
    game_map.tiles[10:20, 10] = WALL
    game_map.tiles[10:20, 29] = WALL
    # Doorway in the south wall.
    game_map.tiles[19, 18:22] = FLOOR

    # A corridor along the bottom.
    game_map.tiles[30:38, 40:70] = FLOOR
    game_map.tiles[30, 40:70] = WALL
    game_map.tiles[37, 40:70] = WALL
    game_map.tiles[30:38, 40] = WALL
    game_map.tiles[30:38, 69] = WALL
    # Doorway in the west wall.
    game_map.tiles[33:36, 40] = FLOOR

    # Mark every tile as explored so the player can see the whole map for now.
    game_map.explored[:] = True

    return game_map


def create_player(registry: tcod.ecs.Registry) -> tcod.ecs.Entity:
    """Spawn the player entity."""
    entity = registry.new_entity()
    entity.components[Position] = Position(x=40, y=22)
    entity.components[Renderable] = Renderable(char="@", fg=(255, 255, 255))
    entity.components[Name] = Name(name="Player")
    entity.components[Fighter] = Fighter(hp=30, max_hp=30, power=5, defense=2)
    return entity


def create_orcs(registry: tcod.ecs.Registry, game_map: GameMap) -> None:
    """Place a handful of orc entities on walkable tiles."""
    orc_positions = [
        (15, 14),
        (20, 14),
        (50, 34),
        (55, 34),
        (60, 34),
    ]
    for x, y in orc_positions:
        if not game_map.is_walkable(x, y):
            continue
        entity = registry.new_entity()
        entity.components[Position] = Position(x=x, y=y)
        entity.components[Renderable] = Renderable(char="o", fg=(63, 127, 63))
        entity.components[Name] = Name(name="Orc")
        entity.components[Fighter] = Fighter(hp=10, max_hp=10, power=3, defense=0)
        entity.components[AI] = AI(kind=AIKind.HOSTILE)


def try_move(entity: tcod.ecs.Entity, dx: int, dy: int, game_map: GameMap) -> None:
    """Move an entity if the destination tile is walkable."""
    pos: Position = entity.components[Position]
    new_x, new_y = pos.x + dx, pos.y + dy
    if game_map.is_walkable(new_x, new_y):
        pos.x = new_x
        pos.y = new_y


def main() -> None:
    # --- Registry (ECS world) ---
    registry = tcod.ecs.Registry()

    # --- Game map ---
    game_map = make_test_map(MAP_WIDTH, MAP_HEIGHT)
    registry.context["game_map"] = game_map

    # --- Entities ---
    player = create_player(registry)
    create_orcs(registry, game_map)

    # --- tcod context ---
    tileset = tcod.tileset.load_truetype_font(
        "data/fonts/dejavu10x10.ttf", tile_width=16, tile_height=16
    )
    with tcod.context.new(
        columns=SCREEN_WIDTH,
        rows=SCREEN_HEIGHT,
        tileset=tileset,
        title="Chapter 8 -- The Game Map",
    ) as context:
        console = tcod.console.Console(SCREEN_WIDTH, SCREEN_HEIGHT, order="C")

        running = True
        while running:
            render_all(console, game_map, registry, player)
            context.present(console)

            for event in tcod.event.wait():
                if isinstance(event, tcod.event.Quit):
                    running = False
                elif isinstance(event, tcod.event.KeyDown):
                    action = handle_input(event, player)
                    if action is None:
                        continue

                    if isinstance(action, BumpAction):
                        try_move(action.entity, action.dx, action.dy, game_map)
                    elif isinstance(action, WaitAction):
                        pass
                    elif isinstance(action, Action):
                        # Placeholder for future actions (pickup, drop, etc.).
                        pass


if __name__ == "__main__":
    main()

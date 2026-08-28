# Chapter 8: The Game Map

In the previous chapters, we built the ECS registry, defined a component library, and wired up a basic game loop. The player exists as an entity with position and renderable data. But the player moves through empty space---there are no walls, no floors, no rooms. The game has entities but no world.

This chapter gives the game a world. We build a tile-based map using numpy arrays, define tile types that describe walls and floors, create a `GameMap` class that wraps the data, and implement a render system that draws the map to the console. By the end, the player will walk through a room with visible walls, a camera that follows them, and a fog of war that remembers what they have explored.

## Map Data Structure

A roguelike map is a 2D grid. Each cell in the grid is a tile---a floor tile you can walk on, a wall tile that blocks movement and vision, or an empty tile that represents unexplored space. The map stores the properties of every tile in the dungeon.

We use numpy arrays for map storage. Numpy is already a dependency of tcod, so there is no additional installation required. More importantly, numpy arrays give us efficient element-wise operations that matter for field of view calculations and map generation. When we compute visibility in Chapter 9, we will pass entire arrays to tcod's shadowcasting functions rather than looping over individual tiles.

Each tile in the map has two fundamental properties:

**Walkable** -- Can an entity move through this tile? Floor tiles are walkable. Wall tiles are not. This property is checked by the movement system every time an entity attempts to change position.

**Transparent** -- Does light pass through this tile? This determines whether the tile blocks line of sight. Floor tiles are transparent. Walls are not. Transparent tiles allow the field of view algorithm to see through them; opaque tiles cast shadows.

A third property tracks exploration state, but this is not stored per-tile as part of the tile definition. Instead, the map maintains separate arrays for visibility (what the player can see right now) and exploration (what the player has ever seen). These arrays are the fog of war system.

The key insight is that the map is static data. Tiles do not move, do not change during a turn, and do not have behaviors. They are the stage on which entities perform. Entities are dynamic---they move, attack, pick up items. Tiles are the ground they stand on. This separation keeps the game logic clean: the movement system checks `map.tiles[y, x].walkable` to decide if a destination is valid, but it never modifies the tile itself.

## Defining Tile Types

Before we build the map, we need to define what a tile looks like. A tile type is a template that describes a category of terrain: wall, floor, void. Each template specifies the visual appearance in two states---when the tile is currently visible to the player and when it has been explored but is outside the player's current field of view.

We use `NamedTuple` for tile types. This gives us immutable instances that are lightweight and hashable, which matters when we later store them in arrays and compare them:

```python
# src/tile_types.py

from __future__ import annotations

import numpy as np
from typing import NamedTuple


class Tile(NamedTuple):
    """A template for a type of terrain tile."""

    walkable: bool
    transparent: bool
    dark_fg: tuple[int, int, int]  # Color when explored but not visible
    dark_bg: tuple[int, int, int]
    light_fg: tuple[int, int, int]  # Color when currently visible
    light_bg: tuple[int, int, int]


VOID = Tile(
    walkable=False,
    transparent=False,
    dark_fg=(0, 0, 0),
    dark_bg=(0, 0, 0),
    light_fg=(0, 0, 0),
    light_bg=(0, 0, 0),
)

FLOOR = Tile(
    walkable=True,
    transparent=True,
    dark_fg=(50, 50, 150),
    dark_bg=(0, 0, 10),
    light_fg=(200, 200, 200),
    light_bg=(50, 50, 100),
)

WALL = Tile(
    walkable=False,
    transparent=False,
    dark_fg=(0, 0, 100),
    dark_bg=(0, 0, 50),
    light_fg=(130, 110, 50),
    light_bg=(200, 180, 50),
)
```

Each tile has two pairs of colors: `dark_fg`/`dark_bg` for tiles that have been explored but are not currently in the player's field of view, and `light_fg`/`light_bg` for tiles that are currently visible. The dark colors are dimmer---they suggest memory rather than presence. The bright colors are vivid---they represent what the player sees right now.

The `VOID` tile is completely black in both states. It represents the space outside the map boundaries or ungenerated areas. The `FLOOR` tile uses blue-ish tones that suggest stone. The `WALL` tile uses warm gold tones that suggest lit stone walls. These color choices are arbitrary---swap them for any palette you prefer. The important thing is that walls and floors are visually distinct.

We define these as module-level constants rather than generating them dynamically. In a roguelike, you typically have a small number of tile types. Procedural generation might place doors, water, lava, or traps, but each of those is a new `Tile` constant added to this module. The constants are never modified at runtime---they are templates that the map creation code copies into the map's tile array.

> **Note:** We use `NamedTuple` instead of `attrs` for tile types because tiles need to be stored in numpy arrays as elements. NamedTuples work naturally with numpy's structured arrays and element-wise operations. attrs classes would require more setup to achieve the same integration. For components that attach to entities, attrs is the right choice. For tile templates that live in numpy arrays, NamedTuples are simpler.

## The GameMap Class

The `GameMap` class wraps the numpy arrays into a single object that the rest of the game can use. It owns the tile data, the visibility state, and the exploration memory. It provides properties for the map dimensions and methods for converting between coordinate systems.

```python
# src/engine/game_map.py

from __future__ import annotations

import numpy as np

from tile_types import VOID, FLOOR, WALL


class GameMap:
    """A 2D tile map representing a dungeon level."""

    def __init__(self, width: int, height: int) -> None:
        self.width = width
        self.height = height

        # Tile properties: separate arrays for efficient computation
        self.walkable = np.full(
            (height, width), fill_value=VOID.walkable, dtype=bool
        )
        self.transparent = np.full(
            (height, width), fill_value=VOID.transparent, dtype=bool
        )

        # Color arrays: (height, width, 3) for RGB
        self.dark_fg = np.full((height, width, 3), 0, dtype=np.uint8)
        self.dark_bg = np.full((height, width, 3), 0, dtype=np.uint8)
        self.light_fg = np.full((height, width, 3), 0, dtype=np.uint8)
        self.light_bg = np.full((height, width, 3), 0, dtype=np.uint8)

        # Fog of war arrays
        self.visible = np.full((height, width), fill_value=False, dtype=bool)
        self.explored = np.full((height, width), fill_value=False, dtype=bool)

    def in_bounds(self, x: int, y: int) -> bool:
        """Check if a position is within the map boundaries."""
        return 0 <= x < self.width and 0 <= y < self.height

    def is_walkable(self, x: int, y: int) -> bool:
        """Check if a tile can be moved through."""
        return self.walkable[y, x]

    def is_transparent(self, x: int, y: int) -> bool:
        """Check if a tile allows line of sight."""
        return self.transparent[y, x]
```

The constructor allocates the arrays and fills them with void tiles. The map starts empty. The procedural generator (or our test setup) will then carve rooms and corridors by setting individual tiles to floor or wall.

The `in_bounds`, `is_walkable`, and `is_transparent` methods are convenience wrappers. They take individual `x, y` coordinates and index into the numpy arrays. Systems that need bulk operations---like computing field of view---work directly with the numpy arrays. Systems that check individual tiles use these methods for clarity.

The `visible` and `explored` arrays are not part of the tile definition. They are runtime state managed by the field of view system (Chapter 9) and the render system (this chapter). The field of view system sets `visible[y, x] = True` for every tile the player can currently see. The render system reads both `visible` and `explored` to decide which colors to use when drawing each tile.

The `explored` array is write-once. Once a tile is explored, it stays explored for the duration of the dungeon level. When the player descends to a new level, a fresh `GameMap` is created with a new `explored` array, resetting the fog of war.

## Map Rendering

With the map data structure in place, we can draw it. The render system iterates over every tile that falls within the console's viewport and decides what to draw based on the tile's visibility state.

The rendering rules are:

1. If `visible[y, x]` is `True`, draw the tile using its `light_fg` and `light_bg` colors. The player can see this tile right now.
2. If `explored[y, x]` is `True` but `visible[y, x]` is `False`, draw the tile using its `dark_fg` and `dark_bg` colors. The player has seen this tile before but cannot currently see it.
3. If `explored[y, x]` is `False`, draw nothing. The player has never seen this tile, and the console has already been cleared to blank.

We also need a camera system. The test map fits on a single screen, but real dungeons are much larger than the console. A typical dungeon might be 80x50 tiles while the console might be 80x24 tiles after accounting for the HUD. The camera calculates an offset that centers the player on the screen, stopping at map edges so the view never shows outside the map boundaries.

The camera offset converts map coordinates to screen coordinates:

```
camera_x = player_x - view_width // 2
camera_y = player_y - view_height // 2
```

Clamped to map boundaries:

```python
camera_x = max(0, min(camera_x, map_width - view_width))
camera_y = max(0, min(camera_y, map_height - view_height))
```

A tile at map position `(mx, my)` appears on screen at `(mx - camera_x, my - camera_y)`. When the map is smaller than the console, the camera clamps to `(0, 0)` and the map draws at its natural position.

Here is the render function with camera support:

```python
# src/systems/render.py

import tcod.console

from engine.game_map import GameMap


def render_map(
    console: tcod.console.Console,
    game_map: GameMap,
    camera_x: int,
    camera_y: int,
) -> None:
    """Draw the game map to the console with camera offset."""
    view_width = console.width
    view_height = console.height

    for screen_y in range(view_height):
        for screen_x in range(view_width):
            map_x = screen_x + camera_x
            map_y = screen_y + camera_y

            if not game_map.in_bounds(map_x, map_y):
                continue

            if game_map.visible[map_y, map_x]:
                fg = tuple(game_map.light_fg[map_y, map_x])
                bg = tuple(game_map.light_bg[map_y, map_x])
                console.print(x=screen_x, y=screen_y, string=".", fg=fg, bg=bg)
            elif game_map.explored[map_y, map_x]:
                fg = tuple(game_map.dark_fg[map_y, map_x])
                bg = tuple(game_map.dark_bg[map_y, map_x])
                console.print(x=screen_x, y=screen_y, string=".", fg=fg, bg=bg)
```

The loop iterates over screen coordinates and converts each to map coordinates. If the map coordinate is out of bounds (which can happen when the map is smaller than the console), we skip it. Tiles that are in bounds but not explored are also skipped, leaving them blank.

> **Note:** We use `"."` as the floor character here. In a full game, you would draw different characters for walls (e.g., `"#"` or box-drawing characters) and floors. We will refine the character choices when we add procedural generation. For now, every tile draws as `"."` to keep the rendering logic focused on the visibility system rather than character selection.

The function takes the console, the map, and the camera offset as parameters and returns nothing. This is the rendering convention we established in Chapter 5: render functions are side-effecting functions that draw to the console. They do not return data, modify game state, or trigger events. This separation keeps rendering testable and debuggable.

## Map Tiles vs Entities

The game map and entities occupy the same coordinate space, but they are fundamentally different. Understanding the distinction matters for rendering order, collision detection, and game logic.

**Tiles are static.** A floor tile at position (5, 3) is always a floor tile. It does not move, does not take damage, and does not have AI. Walls are permanent obstacles (until we add destructible terrain, which is a special case). The map is the fixed stage on which the game unfolds.

**Entities are dynamic.** The player moves. Monsters chase. Items are picked up and dropped. Entities have position, appearance, and behavior. They are the actors on the stage.

The render system must draw both, in the correct order. Tiles go first---they form the background. Entities are drawn on top, in the order determined by their `render_order` component (defined in Chapter 6). Items at order 0, enemies at order 1, the player at order 2. This ensures the player is always visible, even when standing on a tile that another entity also occupies.

The complete rendering pipeline is: clear the console, compute the camera, draw tiles, draw entities, draw the HUD, present the console. In this chapter we implement the tile drawing and camera computation. Entity and HUD rendering come in later chapters when we have the components and UI systems to support them.

## Creating a Test Map

Before we wire up procedural generation, we need a map to render. A hardcoded test map lets us verify the rendering pipeline without the complexity of dungeon algorithms. We create a simple room with walls around the edges and floor tiles in the interior, then place the player in the center.

```python
# src/engine/map_factory.py

import tcod.ecs

from engine.game_map import GameMap
from components.physical import Position, Renderable
from tile_types import FLOOR, WALL


def create_test_map(
    registry: tcod.ecs.Registry,
    width: int = 40,
    height: int = 20,
) -> GameMap:
    """Create a simple rectangular room for testing.

    The room is surrounded by walls with floor tiles inside.
    The player is placed in the center of the room.
    """
    game_map = GameMap(width, height)

    # Carve out the interior as floor
    for y in range(1, height - 1):
        for x in range(1, width - 1):
            game_map.walkable[y, x] = FLOOR.walkable
            game_map.transparent[y, x] = FLOOR.transparent
            game_map.dark_fg[y, x] = FLOOR.dark_fg
            game_map.dark_bg[y, x] = FLOOR.dark_bg
            game_map.light_fg[y, x] = FLOOR.light_fg
            game_map.light_bg[y, x] = FLOOR.light_bg

    # The border is already void from the constructor, but we can
    # explicitly set wall colors for the border tiles
    for y in range(height):
        for x in range(width):
            if y == 0 or y == height - 1 or x == 0 or x == width - 1:
                game_map.walkable[y, x] = WALL.walkable
                game_map.transparent[y, x] = WALL.transparent
                game_map.dark_fg[y, x] = WALL.dark_fg
                game_map.dark_bg[y, x] = WALL.dark_bg
                game_map.light_fg[y, x] = WALL.light_fg
                game_map.light_bg[y, x] = WALL.light_bg

    # Mark all tiles as explored so we can see the whole room
    # (In a real game, the FOV system would handle this)
    game_map.explored[:, :] = True
    game_map.visible[:, :] = True

    # Place the player in the center
    player = registry["player"]
    center_x = width // 2
    center_y = height // 2
    player.components[Position] = Position(x=center_x, y=center_y)

    return game_map
```

This function creates a rectangular room. The border tiles are walls. The interior tiles are floor. Every tile is marked as both visible and explored so the entire room is drawn---this is a testing convenience, not game behavior. In a real game, only tiles within the player's field of view would be visible.

The function takes the registry as a parameter and places the player entity at the center of the room. This ties map creation to entity setup, which is appropriate for a factory function that creates a complete, playable level.

The `game_map.explored[:, :] = True` line uses numpy slice notation to set every element of the explored array to `True`. This is more efficient than looping over individual tiles. It is also more readable once you understand numpy's indexing syntax.

## The Render System

The render system is a dedicated function that draws the entire game to the console. It is called once per frame, after the console has been cleared and before the context presents it to the window. It separates rendering from game logic: the render function does not modify entities, does not process input, and does not advance the game state. It reads the current state and draws it.

Here is the complete render system, including entity rendering:

```python
# src/systems/render.py

import tcod.console
import tcod.ecs

from components.physical import Position, Renderable
from engine.game_map import GameMap


def render_map(
    console: tcod.console.Console,
    game_map: GameMap,
    camera_x: int,
    camera_y: int,
) -> None:
    """Draw the game map tiles to the console."""
    view_width = console.width
    view_height = console.height

    for screen_y in range(view_height):
        for screen_x in range(view_width):
            map_x = screen_x + camera_x
            map_y = screen_y + camera_y

            if not game_map.in_bounds(map_x, map_y):
                continue

            if game_map.visible[map_y, map_x]:
                fg = tuple(game_map.light_fg[map_y, map_x])
                bg = tuple(game_map.light_bg[map_y, map_x])
                console.print(x=screen_x, y=screen_y, string=".", fg=fg, bg=bg)
            elif game_map.explored[map_y, map_x]:
                fg = tuple(game_map.dark_fg[map_y, map_x])
                bg = tuple(game_map.dark_bg[map_y, map_x])
                console.print(x=screen_x, y=screen_y, string=".", fg=fg, bg=bg)


def render_entities(
    console: tcod.console.Console,
    registry: tcod.ecs.Registry,
    camera_x: int,
    camera_y: int,
    game_map: GameMap,
) -> None:
    """Draw all visible entities to the console."""
    for entity, (pos, rend) in registry.Q[Position, Renderable].results:
        # Convert map position to screen position
        screen_x = pos.x - camera_x
        screen_y = pos.y - camera_y

        # Skip entities outside the viewport
        if screen_x < 0 or screen_x >= console.width:
            continue
        if screen_y < 0 or screen_y >= console.height:
            continue

        # Only draw entities on tiles the player can see
        if game_map.visible[pos.y, pos.x]:
            console.print(
                x=screen_x,
                y=screen_y,
                string=rend.char,
                fg=rend.fg,
            )


def render_all(
    console: tcod.console.Console,
    registry: tcod.ecs.Registry,
) -> None:
    """Render the complete game frame.

    This is the top-level render function called each frame.
    It computes the camera, draws the map, draws entities,
    and prepares the console for presentation.
    """
    console.clear()

    world = registry[None]
    game_map = world.components.get(GameMap)
    if game_map is None:
        return

    player = registry["player"]
    player_pos = player.components[Position]

    # Compute camera position
    camera_x = player_pos.x - console.width // 2
    camera_y = player_pos.y - console.height // 2
    camera_x = max(0, min(camera_x, game_map.width - console.width))
    camera_y = max(0, min(camera_y, game_map.height - console.height))

    # Draw layers in order
    render_map(console, game_map, camera_x, camera_y)
    render_entities(console, registry, camera_x, camera_y, game_map)
```

The `render_all` function is the entry point. It is called from the main loop once per frame. It clears the console, retrieves the game map and player position from the registry, computes the camera offset, and delegates to `render_map` and `render_entities`.

Notice the layering order. Tiles are drawn first, forming the background. Entities are drawn on top, so they appear to stand on the map. Within entities, the `render_order` field on the `Renderable` component determines draw order---items first, then enemies, then the player. We did not sort by `render_order` in `render_entities` above because the query results come in a consistent order. If ordering becomes an issue, adding a `sorted()` call on the results by `rend.render_order` is straightforward.

The camera computation lives in `render_all` rather than in a separate function for clarity. It reads the player position, calculates the offset, clamps to map boundaries, and passes the result to the drawing functions. If the map is smaller than the console, the camera clamps to `(0, 0)` and the map is drawn at its natural position.

The `world.components.get(GameMap)` call uses `.get()` rather than direct indexing because the map might not exist yet (e.g., during the main menu before a game is started). If there is no map, the function returns early without drawing anything. This is defensive programming---the render system should never crash because game state is missing.

## Wiring It All Together

Here is the complete main function that creates the registry, generates the test map, and runs the game loop with the render system:

```python
# src/main.py

import tcod
import tcod.console
import tcod.context
import tcod.event
import tcod.tileset
import tcod.ecs

from components.physical import Position, Renderable
from components.combat import Health
from engine.game_map import GameMap
from engine.map_factory import create_test_map
from systems.render import render_all


def main() -> None:
    tileset = tcod.tileset.load_tilesheet(
        path="dejavu10x10_gs_tc.png",
        columns=32,
        rows=8,
        charmap=tcod.tileset.CHARMAP_TCOD,
    )

    # Set up the ECS registry
    registry = tcod.ecs.Registry()

    # Create the player entity
    player = registry.new_entity(key="player")
    player.components[Position] = Position(x=0, y=0)
    player.components[Renderable] = Renderable(
        char="@", fg=(255, 255, 255), render_order=2
    )
    player.components[Health] = Health(hp=30, max_hp=30, power=5, defense=2)
    player.tags.add("player")
    player.tags.add("blocks_movement")

    # Create the test map
    game_map = create_test_map(registry, width=40, height=20)

    # Store the map on the world entity
    world = registry[None]
    world.components[GameMap] = game_map
    world.tags.add("in_game")

    # Set up the window
    view_width = 40
    view_height = 20

    with tcod.context.new(
        columns=view_width,
        rows=view_height,
        tileset=tileset,
        title="Roguelike",
    ) as context:
        console = tcod.console.Console(view_width, view_height, order="F")

        while True:
            render_all(console, registry)
            context.present(console)

            for event in tcod.event.wait():
                if isinstance(event, tcod.event.Quit):
                    return

                if isinstance(event, tcod.event.KeyDown):
                    player_pos = player.components[Position]

                    if event.sym == tcod.event.KeySym.UP:
                        if game_map.is_walkable(
                            player_pos.x, player_pos.y - 1
                        ):
                            player_pos.y -= 1
                    elif event.sym == tcod.event.KeySym.DOWN:
                        if game_map.is_walkable(
                            player_pos.x, player_pos.y + 1
                        ):
                            player_pos.y += 1
                    elif event.sym == tcod.event.KeySym.LEFT:
                        if game_map.is_walkable(
                            player_pos.x - 1, player_pos.y
                        ):
                            player_pos.x -= 1
                    elif event.sym == tcod.event.KeySym.RIGHT:
                        if game_map.is_walkable(
                            player_pos.x + 1, player_pos.y
                        ):
                            player_pos.x += 1
                    elif event.sym == tcod.event.KeySym.ESCAPE:
                        return


if __name__ == "__main__":
    main()
```

The main loop is simple: render, present, wait for input, process movement. The movement logic checks `game_map.is_walkable` before updating the player position. This prevents the player from walking through walls. There is no entity collision yet---the player can walk through enemies---but that is a system-level concern for a later chapter.

The window dimensions match the test map dimensions (40x20), so the camera is always at `(0, 0)` and the entire map fits on screen. When we add larger procedural maps, we will increase the console size or rely on the camera system to handle scrolling.

## Exercises

**Exercise 1: A Larger Test Map**

Modify `create_test_map` to generate a map with two rooms connected by a corridor. The first room should be in the upper-left area and the second in the lower-right. A narrow corridor (one tile wide) connects them. Place the player in the first room. Verify that the camera scrolls when the player moves toward the second room.

Hints:
- Use nested loops to place walls and floors for each room.
- For the corridor, connect the bottom-right of the first room to the top-left of the second room with a horizontal segment and a vertical segment.
- Remember to mark corridor tiles as walkable and transparent.

**Exercise 2: A Minimap Overlay**

Implement a minimap that shows the entire explored map in a small corner of the console. The minimap should be a fixed size (e.g., 15x15 tiles) and should scale the map down to fit. Use `explored` to determine which tiles to show. Draw explored walls as a bright pixel and explored floors as a dim pixel. Place the minimap in the upper-right corner of the console.

Hints:
- Calculate a scale factor: `scale_x = map_width / minimap_width`.
- For each minimap pixel, map it back to the corresponding map tile.
- Use `console.print` or direct cell access to draw the minimap overlay after drawing the main map.

**Exercise 3: Map Scrolling at Edges**

Currently, the camera only follows the player when they move. Implement edge-based scrolling: when the player reaches the edge of the console viewport (within 2 tiles of the boundary), the camera scrolls to keep the player within the center region. This creates a smoother exploration feel for maps that are much larger than the console.

Hints:
- Define a "scroll zone" around the center of the console (e.g., 2 tiles from any edge).
- Check if the player's screen position falls within the scroll zone before updating the camera.
- The camera update should be immediate, not animated---this is a turn-based game.
- You will need to recompute the camera after every player movement, not just when the player crosses the zone boundary.

**Exercise 4: Tile Characters**

Replace the `"."` floor character with something more appropriate. Draw walls as `"#"` and floors as `"."`. Adjust the render function to choose the character based on whether the tile is walkable or not. This is a small change but it makes the map immediately more readable.

Hints:
- Store the tile character on the `GameMap` alongside the other tile data, or compute it from the walkable array.
- A wall that is visible might use a different character than a wall that is only explored (e.g., a bright `"#"` vs a dim `"#"`).
- Consider adding the character data to the `Tile` namedtuple so each tile type defines its own display character.

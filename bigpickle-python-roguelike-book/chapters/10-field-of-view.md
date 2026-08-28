# Chapter 10: Field of View

The player stands in a corridor. Ahead, darkness. Behind, a room they have already cleared. To the left, a passage they have not explored. They press right, stepping into the unknown, and the darkness peels back to reveal a new room with an orc guarding a treasure chest. The orc has not noticed them yet. That moment---the transition from darkness to light, the reveal of something hidden---is the entire emotional core of exploration in a roguelike. Without field of view, the dungeon is fully visible from the start, and there is nothing to discover.

This chapter replaces the placeholder visibility system from Chapter 8 with a real field of view algorithm. We will use tcod's shadowcasting to compute which tiles the player can see, integrate FOV into the game map, and build the rendering pipeline that distinguishes visible tiles from explored tiles from unknown tiles. By the end, the dungeon is dark, exploration has tension, and the player discovers the map one step at a time.

## Why Field of View?

A dungeon that is fully visible from the start is a solved problem. The player sees every room, every corridor, every enemy, and every item before they take a single step. There is no mystery, no risk in venturing forward, no relief in finding a safe room. The game becomes a pure optimization puzzle with no surprise. That might work for a tactics game, but it kills a roguelike.

Field of view creates three distinct regions of the map:

**Visible** -- Tiles the player can see right now. These are lit, animated, and full of information. Enemies move, traps are detectable, and the terrain is clear. The visible region is where immediate gameplay happens.

**Explored** -- Tiles the player has seen before but cannot currently see. These are drawn dimly, as a memory of what was there. The player knows the layout of the dungeon behind them, but they cannot see whether an enemy has moved into a previously clear corridor. Explored tiles are the map the player builds in their mind as they play.

**Unknown** -- Tiles the player has never seen. These are drawn as black void. The player does not know what is there---it could be a room full of treasure or a corridor choked with monsters. Unknown tiles are the source of tension and exploration incentives.

The interplay between these three states is what makes exploration work. The player must balance the safety of known territory against the rewards of the unknown. Every step forward is a small risk. Every new room is a small discovery. Field of view turns a static map into a living experience.

Strategically, line of sight matters for combat and stealth. An enemy behind a wall cannot be seen, and the player cannot target it with a ranged attack. A corridor with a bend hides what is around the corner. The geometry of the dungeon---its walls, corners, and doorways---becomes tactically relevant when field of view is in play. A narrow corridor funnels enemies into a chokepoint. A pillar in a room provides cover. These emergent tactical properties arise naturally from FOV interacting with the dungeon layout.

## FOV Algorithms

Computing field of view means answering a simple question for each tile on the map: can the player see it from their current position? "See" means there is an unobstructed line from the player's tile to the target tile, passing only through transparent tiles. Walls, pillars, and other opaque terrain block the line of sight.

There are several algorithms for computing this, each with different tradeoffs in speed, accuracy, and visual quality.

### Symmetric Shadowcasting

Symmetric shadowcasting is the algorithm tcod uses by default, and it is the one we will use. It is fast, accurate, and produces a symmetric field of view---if tile A can see tile B, then tile B can see tile A. This symmetry matters for gameplay fairness: if the player can see an enemy, the enemy's AI should logically be able to see the player.

The algorithm works by casting shadows from the origin outward in octants. The map is divided into eight triangular wedges (octants) radiating from the player's position. Within each octant, the algorithm scans outward from the origin row by row. For each row, it tracks the start and end of visible spans---continuous runs of transparent tiles. When it encounters an opaque tile, it narrows the visible span. The shadow cast by the opaque tile is subtracted from the span in subsequent rows, creating a shadow cone behind the wall.

The key insight is that shadows are represented as rational numbers (start/end fractions of the current row), not as individual tiles. This makes the algorithm precise---it does not miss tiles that are partially visible, and it does not include tiles that are partially hidden. The result is a clean, accurate field of view with no visual artifacts.

Symmetric shadowcasting runs in O(n) time where n is the number of visible tiles. On a typical dungeon with a view radius of 8, it computes roughly 200 tiles in microseconds. Even on large maps with radius 30, it completes in well under a millisecond. This makes it practical to recompute every turn without performance concerns.

### Recursive Shadowcasting

Recursive shadowcasting is the older variant that symmetric shadowcasting improves upon. It uses the same octant-based approach but tracks shadows recursively, splitting and merging shadow ranges as it descends. It produces similar results but can miss certain edge cases---a tile that is technically visible might be marked as hidden if it falls on the exact boundary of two shadow ranges. For most gameplay purposes, the difference is imperceptible. Symmetric shadowcasting is preferred because it eliminates these edge cases entirely.

### Ray Casting

Ray casting is the simplest FOV algorithm to understand: cast rays from the player in every direction, marking tiles as visible until a ray hits an opaque tile. The number of rays determines the resolution---too few rays and tiles between rays are missed; too many and the computation is wasteful.

Ray casting produces an accurate field of view for the tiles it hits, but it has a fundamental limitation: it cannot see between rays. A tile that falls between two rays is invisible even if it should be visible. Increasing the number of rays reduces this problem but never eliminates it entirely. Ray casting is also not symmetric---the set of tiles the player can see from position A may differ from the set of tiles visible from position B, even if A and B are adjacent.

For a roguelike, these limitations are unacceptable. Players will notice tiles flickering in and out of visibility as they move. Ray casting is fine for simple prototypes or games where visual precision is not important, but tcod's shadowcasting is strictly better for production use.

### Permissive FOV

Permissive field of view algorithms take a different approach: instead of casting shadows, they check each tile individually against a visibility criterion. A tile is visible if there exists at least one unobstructed line from the origin to any part of the tile. "Permissive" means the algorithm is lenient---it considers a tile visible even if only a small portion of it is in line of sight.

Permissive FOV produces a wider, more inclusive field of view than shadowcasting. Tiles at the edges of walls are more likely to be visible, which some players prefer visually. The tradeoff is that permissive FOV can reveal tiles that feel like they should be hidden---a tile just around a corner might be visible even though the player cannot see the corner itself.

tcod provides a permissive FOV algorithm (`FOV_PERMISSIVE_0` through `FOV_PERMISSIVE_4`, with increasing permissiveness) as an alternative to symmetric shadowcasting. For our game, symmetric shadowcasting is the right default. It produces the most tactically predictable results, and its symmetry ensures that what the player sees matches what enemies could plausibly see.

### Why tcod Uses Symmetric Shadowcasting

tcod's default FOV algorithm is symmetric shadowcasting because it satisfies three properties that matter for roguelikes:

**Accuracy.** Every tile that is geometrically visible is marked as visible. No false negatives. No tiles hidden that should be seen.

**Symmetry.** If tile A can see tile B, then tile B can see tile A. This is essential for fair AI. An enemy should never be attacked by a player it cannot see, and vice versa.

**Performance.** The algorithm runs in O(n) time, where n is the number of tiles within the view radius. For typical roguelike parameters (radius 8 to 20), this is a few hundred to a few thousand tiles, computed in microseconds.

These properties make symmetric shadowcasting the standard choice for modern roguelikes. We will use it throughout this book.

## Using tcod.map.Map

tcod provides a `Map` class that wraps the arrays needed for FOV computation. The map stores two properties per tile that FOV needs:

- **walkable** -- Whether an entity can move through the tile. This is not directly used by FOV, but it is useful to keep walkable and transparent in sync on the same map object.
- **transparent** -- Whether light and line of sight pass through the tile. This is the property FOV algorithms use to determine which tiles block vision.

The tcod map is a lightweight container that holds numpy arrays in the shape `(height, width)`. We create it from our existing `GameMap` data, copying the tile properties into the format tcod expects.

```python
import tcod.map

def create_fov_map(game_map: GameMap) -> tcod.map.Map:
    """Create a tcod FOV map from the game map's tile properties."""
    fov = tcod.map.Map(width=game_map.width, height=game_map.height)

    for y in range(game_map.height):
        for x in range(game_map.width):
            fov.walkable[y, x] = game_map.is_transparent(x, y)
            fov.transparent[y, x] = game_map.is_transparent(x, y)

    return fov
```

This function iterates over every tile in the game map and copies the transparency property into the tcod map. In this implementation, `walkable` and `transparent` are set to the same value because our tile types treat them as equivalent---floors are both walkable and transparent, walls are neither. In a more complex game, these could differ: a closed door might be transparent (you can see through it) but not walkable (you cannot move through it until you open it).

The creation function copies the map once. When the map changes---a door opens, a wall is destroyed---we need to update the corresponding tiles in the tcod map. For a static dungeon (no destructible terrain), the map is created once per level and never modified.

### Using tcod.map.Map Directly on GameMap

In practice, we often skip the standalone `tcod.map.Map` and use `GameMap` as the source of truth for tile properties. The key is that tcod's `compute_fov` method needs a `Map` object. We can also build the FOV map more efficiently using numpy:

```python
import tcod.map
import numpy as np


def create_fov_map(game_map: GameMap) -> tcod.map.Map:
    """Create a tcod FOV map from the game map using numpy operations."""
    fov = tcod.map.Map(width=game_map.width, height=game_map.height)

    # Copy transparency values in bulk using numpy
    # The transparent field is a boolean array of shape (height, width)
    fov.transparent[:] = game_map.tiles["transparent"]

    return fov
```

This version uses numpy slicing to copy the entire `transparent` array in one operation, rather than iterating tile by tile. For a 80x50 map, this is roughly 4000 assignments collapsed into a single numpy operation. The performance difference is negligible at this scale, but it establishes a pattern that matters when maps grow larger or FOV is recomputed frequently.

## Computing FOV

Once we have a `tcod.map.Map`, computing FOV is a single method call:

```python
import tcod.constants

fov_map.compute_fov(
    x=player_x,
    y=player_y,
    radius=8,
    algorithm=tcod.constants.FOV_SYMMETRIC_SHADOWCAST,
)
```

After this call, `fov_map.fov` is a boolean array of shape `(height, width)`. Each element is `True` if the tile at that position is currently visible from `(player_x, player_y)`, `False` otherwise. The `radius` parameter limits the view distance---tiles farther than `radius` tiles from the origin are not visible even if there is a clear line of sight.

The `algorithm` parameter specifies which FOV algorithm to use. `FOV_SYMMETRIC_SHADOWCAST` is tcod's default and the one we recommend. tcod also provides `FOV Recursive` (the older recursive variant), `FOV Shadow` (basic shadowcasting), and `FOV Permissive 0` through `FOV Permissive 4`. For our purposes, symmetric shadowcasting is the right choice.

Here is how we integrate FOV computation into the game loop:

```python
def update_fov(
    game_map: GameMap,
    fov_map: tcod.map.Map,
    player_x: int,
    player_y: int,
    view_radius: int = 8,
) -> None:
    """Recompute field of view and update the game map's visibility arrays."""
    # Reset visibility---nothing is visible until proven otherwise
    game_map.visible[:] = False

    # Compute new FOV from the player's position
    fov_map.compute_fov(
        x=player_x,
        y=player_y,
        radius=view_radius,
        algorithm=tcod.constants.FOV_SYMMETRIC_SHADOWCAST,
    )

    # Copy the result into the game map's visible array
    game_map.visible[:] = fov_map.fov

    # Mark any newly visible tiles as explored
    game_map.explored |= game_map.visible
```

This function does three things. First, it resets the `visible` array to all `False`. Every turn, visibility starts from scratch. Second, it computes FOV from the player's position with the given radius. Third, it copies the result into the game map and updates the `explored` array.

The `explored |= game_map.visible` line is worth pausing on. This is a numpy bitwise OR operation that sets any tile that is currently visible to also be explored. Once a tile is explored, it stays explored permanently---the `|=` operation never unsets a bit. This is the write-once property of the explored array: tiles accumulate exploration over time, and only reset when a new dungeon level is generated.

## Integration with GameMap

The GameMap class already has `visible` and `explored` arrays from Chapter 8. We need to add one more piece: a way to store the tcod FOV map and recompute FOV when the player moves.

Here is the updated `GameMap` class:

```python
# src/engine/game_map.py

from __future__ import annotations

import numpy as np
import tcod.map

from tile_types import VOID, FLOOR, WALL


class GameMap:
    """A 2D tile map representing a dungeon level."""

    def __init__(self, width: int, height: int) -> None:
        self.width = width
        self.height = height

        # Tile properties
        self.walkable = np.full(
            (height, width), fill_value=VOID.walkable, dtype=bool
        )
        self.transparent = np.full(
            (height, width), fill_value=VOID.transparent, dtype=bool
        )

        # Color arrays
        self.dark_fg = np.full((height, width, 3), 0, dtype=np.uint8)
        self.dark_bg = np.full((height, width, 3), 0, dtype=np.uint8)
        self.light_fg = np.full((height, width, 3), 0, dtype=np.uint8)
        self.light_bg = np.full((height, width, 3), 0, dtype=np.uint8)

        # Fog of war
        self.visible = np.full((height, width), fill_value=False, dtype=bool)
        self.explored = np.full((height, width), fill_value=False, dtype=bool)

        # FOV map for tcod shadowcasting
        self._fov_map: tcod.map.Map | None = None

    @property
    def fov_map(self) -> tcod.map.Map:
        """Lazily create and return the tcod FOV map."""
        if self._fov_map is None:
            self._fov_map = tcod.map.Map(
                width=self.width, height=self.height
            )
            self._fov_map.transparent[:] = self.transparent
        return self._fov_map

    def recompute_fov(
        self, x: int, y: int, radius: int = 8
    ) -> None:
        """Recompute field of view from the given position.

        Updates self.visible and self.explored in place.
        """
        import tcod.constants

        self.visible[:] = False
        self.fov_map.compute_fov(
            x=x,
            y=y,
            radius=radius,
            algorithm=tcod.constants.FOV_SYMMETRIC_SHADOWCAST,
        )
        self.visible[:] = self.fov_map.fov
        self.explored |= self.visible

    def in_bounds(self, x: int, y: int) -> bool:
        return 0 <= x < self.width and 0 <= y < self.height

    def is_walkable(self, x: int, y: int) -> bool:
        return bool(self.walkable[y, x])

    def is_transparent(self, x: int, y: int) -> bool:
        return bool(self.transparent[y, x])
```

The key additions are the `_fov_map` attribute, the `fov_map` property, and the `recompute_fov` method. The FOV map is created lazily---the first time `fov_map` is accessed, it is built from the current `transparent` array. Subsequent accesses return the cached object.

The `recompute_fov` method encapsulates the entire FOV update sequence: reset visible, compute FOV, copy results, update explored. This is the only method that modifies `visible`, which keeps the visibility logic in one place rather than scattered across the game loop.

Note that we import `tcod.constants` inside the method rather than at module level. This is a deliberate choice: the `GameMap` class is a data container that should not depend on specific algorithm constants unless it is actively using them. The import inside the method keeps the module-level namespace clean and makes the dependency explicit at the point of use.

### Calling FOV on Player Movement

FOV should be recomputed whenever the player moves. In our action system from Chapter 7, the player's movement is processed by the action handler. We add an FOV update after a successful move:

```python
def process_action(
    action: BumpAction | WaitAction,
    registry: tcod.ecs.Registry,
    game_map: GameMap,
) -> bool:
    """Process an action. Returns True if the action consumed a turn."""
    if isinstance(action, WaitAction):
        return True

    if isinstance(action, BumpAction):
        pos = action.entity.components[Position]
        target_x = pos.x + action.dx
        target_y = pos.y + action.dy

        if not game_map.is_walkable(target_x, target_y):
            return False

        for other in registry.Q.all_of(tags=["blocks_movement"]):
            other_pos = other.components[Position]
            if (other_pos.x == target_x
                    and other_pos.y == target_y
                    and other is not action.entity):
                return False

        pos.x = target_x
        pos.y = target_y

        # Recompute FOV after the player moves
        if action.entity.tags.get("player"):
            game_map.recompute_fov(pos.x, pos.y)

        return True

    return False
```

The FOV update is gated on the `"player"` tag so it only runs when the player moves. If we later add NPCs that also need FOV (for AI line-of-sight checks), we would recompute from their position separately---or compute once from the player and check distances for AI visibility. For now, the player's FOV is all we need.

FOV should also be computed once at the start of each level, before the first render. This ensures the player's starting position is visible immediately:

```python
# After placing the player and generating the dungeon
player_x, player_y = first_room.center
game_map.recompute_fov(player_x, player_y, radius=8)
```

Without this initial computation, the first frame would show a completely black screen because `visible` is all `False` and no tiles are explored yet.

## Torch Radius and Lighting

The `radius` parameter in `recompute_fov` controls how far the player can see. A radius of 8 means the player can see 8 tiles in every direction---a 17x17 diamond-shaped region centered on the player. This simulates a torch or ambient light source without implementing actual lighting calculations.

Different radius values create different gameplay feels:

- **Radius 5-6:** Very claustrophobic. The player can only see a few tiles ahead. Corridors are barely visible. Rooms reveal themselves only when the player is already inside them. This creates high tension but can be frustrating in large rooms.

- **Radius 8-10:** The standard roguelike range. The player can see most of a typical room from the doorway. Corridors are visible for a reasonable distance. This balances tension with playability.

- **Radius 12-15:** Generous visibility. The player sees most of the screen from any position. This reduces tension but makes navigation easier. Good for beginners or games that emphasize combat over exploration.

- **Radius 20+:** Effectively unlimited. The entire screen is visible from the center. This removes the fog of war mechanic entirely and turns FOV into a pure aesthetic effect.

The radius does not need to be a property of the player entity---it is a game design parameter that can be adjusted by difficulty settings, items, or environmental effects. For now, we pass it as a constant:

```python
PLAYER_VIEW_RADIUS = 8

# In the main loop, after processing a turn:
game_map.recompute_fov(
    player.components[Position].x,
    player.components[Position].y,
    radius=PLAYER_VIEW_RADIUS,
)
```

### Multiple Light Sources

A more advanced game might have multiple entities that emit light. Torches on walls, glowing items, magical effects---each with its own radius and position. tcod supports this by calling `compute_fov` multiple times and merging the results:

```python
def compute_multi_source_fov(
    game_map: GameMap,
    light_sources: list[tuple[int, int, int]],
) -> None:
    """Compute FOV from multiple light sources.

    Args:
        game_map: The game map to update.
        light_sources: List of (x, y, radius) tuples.
    """
    game_map.visible[:] = False

    for x, y, radius in light_sources:
        game_map.fov_map.compute_fov(
            x=x,
            y=y,
            radius=radius,
            algorithm=tcod.constants.FOV_SYMMETRIC_SHADOWCAST,
        )
        game_map.visible |= game_map.fov_map.fov

    game_map.explored |= game_map.visible
```

Each light source computes its own FOV independently. The results are merged with a bitwise OR---a tile is visible if *any* light source can see it. This lets a torch on a wall illuminate a corridor even when the player is around a corner.

For our game, the player is the only light source. The multi-source pattern is here for reference---it is a natural extension when the game grows to include environmental lighting.

### Torch Flicker

A subtle but effective visual enhancement is torch flicker: randomly varying the light radius by one or two tiles each turn. This creates the impression of a flickering torch without any actual animation code:

```python
import random

def get_flicker_radius(base_radius: int) -> int:
    """Return the view radius with a random flicker effect."""
    # 70% chance of base radius, 15% chance of base+1, 15% chance of base-1
    roll = random.random()
    if roll < 0.15 and base_radius > 1:
        return base_radius - 1
    elif roll > 0.85:
        return base_radius + 1
    return base_radius
```

Call this each turn to get a slightly different radius:

```python
radius = get_flicker_radius(PLAYER_VIEW_RADIUS)
game_map.recompute_fov(player_x, player_y, radius=radius)
```

The flicker is subtle---the player sees tiles at the edge of their vision blink in and out of existence. It adds atmosphere without affecting gameplay in a meaningful way. The `base_radius - 1` check prevents the radius from dropping to zero, which would blind the player entirely.

## Rendering with FOV

The render system from Chapter 8 already handles three visibility states. Now that FOV is working, those states actually mean something. Let us review the rendering rules with the context of real FOV data:

1. If `visible[y, x]` is `True`, the tile is currently in the player's line of sight. Draw it using `light_fg` and `light_bg` colors---the bright, vivid palette. The player can see this tile clearly.

2. If `explored[y, x]` is `True` but `visible[y, x]` is `False`, the tile was seen before but is currently in darkness. Draw it using `dark_fg` and `dark_bg` colors---the dim, muted palette. The player remembers this tile but cannot see its current state.

3. If `explored[y, x]` is `False`, the tile has never been seen. Draw nothing. The console is already cleared to black, so unexplored tiles naturally appear as void.

Here is the render function with FOV-aware coloring:

```python
# src/systems/render.py

import numpy as np
import tcod.console

from engine.game_map import GameMap


def render_map(
    console: tcod.console.Console,
    game_map: GameMap,
    camera_x: int,
    camera_y: int,
) -> None:
    """Draw the game map to the console with FOV-based coloring."""
    view_width = console.width
    view_height = console.height
    map_height, map_w = game_map.walkable.shape

    # Compute the visible slice of the map
    y_start = max(camera_y, 0)
    y_end = min(camera_y + view_height, map_height)
    x_start = max(camera_x, 0)
    x_end = min(camera_x + view_width, map_w)

    # Corresponding console coordinates
    cy_start = y_start - camera_y
    cy_end = y_end - camera_y
    cx_start = x_start - camera_x
    cx_end = x_end - camera_x

    # Slice the arrays to the visible region
    visible = game_map.visible[y_start:y_end, x_start:x_end]
    explored = game_map.explored[y_start:y_end, x_start:x_end]
    walkable = game_map.walkable[y_start:y_end, x_start:x_end]

    # Choose characters: '#' for walls, '.' for floors
    char_codes = np.full(visible.shape, ord(" "), dtype=np.uint32)
    wall_mask = ~walkable & explored
    char_codes[wall_mask] = ord("#")
    floor_mask = walkable & explored
    char_codes[floor_mask] = ord(".")

    # Set characters on the console
    console.rgb[cy_start:cy_end, cx_start:cx_end]["ch"] = char_codes

    # Choose foreground colors: light if visible, dark if only explored
    tiles = game_map._tiles_slice(y_start, y_end, x_start, x_end)
    fg = np.where(
        visible[:, :, np.newaxis],
        tiles["light_fg"],
        tiles["dark_fg"],
    )
    console.rgb[cy_start:cy_end, cx_start:cx_end]["fg"] = fg

    # Choose background colors
    bg = np.where(
        visible[:, :, np.newaxis],
        tiles["light_bg"],
        tiles["dark_bg"],
    )
    console.rgb[cy_start:cy_end, cx_start:cx_end]["bg"] = bg

    # Unexplored tiles are black
    hidden = ~explored
    console.rgb[cy_start:cy_end, cx_start:cx_end]["fg"][hidden] = (0, 0, 0)
    console.rgb[cy_start:cy_end, cx_start:cx_end]["bg"][hidden] = (0, 0, 0)
```

The numpy `np.where` operation is the core of the coloring logic. It selects between two color arrays based on the `visible` mask. Where `visible` is `True`, it uses the light colors. Where `visible` is `False`, it uses the dark colors. This is a single vectorized operation that processes the entire visible region at once.

The `hidden` mask then overwrites any tile that is neither visible nor explored with black. This handles the third state---unknown tiles are drawn as pure black void.

The result is a dungeon that is dark around the player, remembered in previously explored areas, and completely black in unexplored territory. As the player moves, the visible region shifts, new tiles become visible, and the explored map grows.

## Entity Visibility

Entities should only be drawn on tiles the player can currently see. An orc standing in a dark corridor is invisible---the player does not know it is there. An orc standing in a lit room is visible and dangerous.

The render function for entities filters by visibility:

```python
def render_entities(
    console: tcod.console.Console,
    registry: tcod.ecs.Registry,
    camera_x: int,
    camera_y: int,
    game_map: GameMap,
) -> None:
    """Draw all visible entities to the console."""
    from components.physical import Position, Renderable

    for entity, (pos, rend) in registry.Q[Position, Renderable].results:
        # Skip entities outside the map
        if not game_map.in_bounds(pos.x, pos.y):
            continue

        # Only draw entities on visible tiles
        if not game_map.visible[pos.y, pos.x]:
            continue

        # Convert to screen coordinates
        sx = pos.x - camera_x
        sy = pos.y - camera_y

        if 0 <= sx < console.width and 0 <= sy < console.height:
            console.print(x=sx, y=sy, string=rend.char, fg=rend.fg)
```

The critical line is `if not game_map.visible[pos.y, pos.x]: continue`. This skips any entity whose tile is not currently visible. Enemies in dark corridors, items in unexplored rooms, and NPCs behind walls are all invisible.

This is a simple approach that works well for most roguelikes. The player only sees what their character would actually see. There is no information leakage through the UI---no minimap dots for hidden enemies, no health bars for off-screen monsters.

### Remembered Entities

A more advanced approach is to remember entities the player has seen before, drawing them dimly when they are not currently visible. This is analogous to how tiles work---visible tiles are bright, explored-but-not-visible tiles are dim.

To implement remembered entities, we would need to store which entities were last seen at which positions. When an entity moves out of the player's FOV, we retain its last known position and draw it at half brightness. When the player's FOV re-covers that position, the entity is drawn at full brightness if it is still there, or not drawn at all if it has moved.

This adds visual richness but also complexity. The player gets information about enemy positions that may be stale---the orc was there five turns ago, but it might have moved since. This creates interesting tactical decisions: do you rush to where the orc was, hoping it is still there? Or do you proceed cautiously in case it has moved closer?

For our game, we will start with the simple approach---only draw visible entities---and add remembered entities as an exercise.

## FOV Performance

For a typical roguelike with a map of 80x50 tiles and a view radius of 8, FOV computation is fast enough to run every turn without concern. The shadowcasting algorithm touches roughly 200 tiles per computation, which takes microseconds on modern hardware. Even on a map of 200x200 with radius 30, FOV completes in under a millisecond.

That said, there are several optimizations worth understanding for larger maps or more frequent recomputation:

### Recompute Only When the Player Moves

FOV should not be recomputed every frame. In a turn-based game, the player's position changes only when they take an action. Compute FOV once per turn, not once per render frame. This is already handled by our integration: `recompute_fov` is called from `process_action`, which runs when the player acts.

In a real-time game (which roguelikes are not, but the principle is worth knowing), FOV would need to be recomputed at a fixed rate or whenever the player's position changes, whichever is less frequent.

### Cache the FOV Result

The `visible` and `explored` arrays are the cached FOV result. Render functions should read from these arrays rather than recomputing FOV themselves. This separation---compute once, read many times---is essential for performance. The render function accesses `game_map.visible[y, x]` directly instead of calling `fov_map.compute_fov()` inside the render loop.

### Batch Operations with Numpy

Where possible, use numpy operations instead of Python loops. The `np.where` call in our render function processes the entire visible region in a single vectorized operation. A Python loop over individual tiles would be orders of magnitude slower for large viewports. When in doubt, prefer numpy array operations over explicit iteration.

### Large Maps and Spatial Partitioning

Maps larger than a few hundred tiles in each dimension may benefit from spatial partitioning---dividing the map into chunks and only computing FOV for chunks near the player. For a map of 500x500, the player's radius-8 FOV only covers a tiny fraction of the total area. Computing FOV for the entire map is wasteful when only 200 tiles matter.

tcod does not provide built-in spatial partitioning for FOV, but you can implement it by clipping the FOV computation to a region of interest. For most roguelikes, maps are small enough that this optimization is unnecessary. It becomes relevant for games with very large, continuous worlds---hundreds of tiles in each dimension---where the map is too large to fit in cache.

## The Complete Integration

Here is the complete `main.py` with FOV integrated into the game loop. This replaces the placeholder `explored[:] = True` from Chapter 9 with real FOV computation:

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


PLAYER_VIEW_RADIUS = 8


def main() -> None:
    tileset = tcod.tileset.load_tilesheet(
        path="dejavu10x10_gs_tc.png",
        columns=32,
        rows=8,
        charmap=tcod.tileset.CHARMAP_TCOD,
    )

    registry = tcod.ecs.Registry()

    # Create the player
    player = registry.new_entity(key="player")
    player.components[Position] = Position(x=0, y=0)
    player.components[Renderable] = Renderable(
        char="@", fg=(255, 255, 255), render_order=2
    )
    player.components[Health] = Health(hp=30, max_hp=30, power=5, defense=2)
    player.tags.add("player")
    player.tags.add("blocks_movement")

    # Create the game map (with FOV support)
    game_map = create_test_map(registry, width=40, height=20)

    # Store the map on the world entity
    world = registry[None]
    world.components[GameMap] = game_map
    world.tags.add("in_game")

    # Compute initial FOV from the player's starting position
    player_pos = player.components[Position]
    game_map.recompute_fov(
        player_pos.x, player_pos.y, radius=PLAYER_VIEW_RADIUS
    )

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
                    pos = player.components[Position]
                    moved = False

                    if event.sym == tcod.event.KeySym.UP:
                        if game_map.is_walkable(pos.x, pos.y - 1):
                            pos.y -= 1
                            moved = True
                    elif event.sym == tcod.event.KeySym.DOWN:
                        if game_map.is_walkable(pos.x, pos.y + 1):
                            pos.y += 1
                            moved = True
                    elif event.sym == tcod.event.KeySym.LEFT:
                        if game_map.is_walkable(pos.x - 1, pos.y):
                            pos.x -= 1
                            moved = True
                    elif event.sym == tcod.event.KeySym.RIGHT:
                        if game_map.is_walkable(pos.x + 1, pos.y):
                            pos.x += 1
                            moved = True
                    elif event.sym == tcod.event.KeySym.ESCAPE:
                        return

                    if moved:
                        game_map.recompute_fov(
                            pos.x, pos.y, radius=PLAYER_VIEW_RADIUS
                        )
```

The difference from Chapter 9 is small but significant. The placeholder lines `dungeon.explored[:] = True` and `dungeon.visible[:] = True` are gone. Instead, `game_map.recompute_fov` is called after every player movement and once at startup. The result is a dungeon that starts dark and reveals itself as the player explores.

The render function remains unchanged---it already handles the three visibility states correctly. The FOV computation feeds data into the `visible` and `explored` arrays, and the render function reads from them. This clean separation means the rendering code does not need to know how FOV is computed. It only needs to know which tiles are visible, which are explored, and which are unknown.

## Exercises

**Exercise 1: Experiment with FOV Radii**

Change the `PLAYER_VIEW_RADIUS` constant to different values and observe the effect on gameplay. Try radius 4 (very dark, high tension), radius 12 (generous visibility), and radius 20 (effectively unlimited). Note how the mood of the game changes with each value. Consider adding a difficulty setting that adjusts the radius---hard mode uses radius 6, normal uses 8, easy uses 12.

**Exercise 2: Torch Flicker Effect**

Implement the `get_flicker_radius` function from the "Torch Flicker" section and integrate it into the game loop. Each turn, the view radius should randomly vary by plus or minus one tile. Observe how the edge of the player's vision subtly shifts, creating the impression of a flickering light source. Ensure the radius never drops below 3---below that, the player can barely see anything.

**Exercise 3: Multi-Source FOV**

Add a torch entity to the game. Place a torch in the center of one room, implemented as a non-player entity with a `Position` component and a new `LightSource` component:

```python
@attrs.define
class LightSource:
    radius: int = 6
```

Modify the FOV computation to include both the player's light and all torch light sources. Use the `compute_multi_source_fov` pattern from the "Multiple Light Sources" section. Verify that a torch in a room illuminates that room even when the player is in a different room with no direct line of sight.

**Exercise 4: Remembered Entities**

Modify `render_entities` to draw entities that were visible on a previous turn but are not currently visible. To do this, you will need to track the last known positions of entities:

1. Add a `last_seen_x` and `last_seen_y` attribute to the `Renderable` component.
2. When rendering, if an entity is currently visible, update its `last_seen` position.
3. When an entity is not visible but has a valid `last_seen` position, draw it at that position using dimmed colors (half brightness).
4. When an entity moves out of the player's FOV, it remains visible at its last known position until the player's FOV no longer covers that position, at which point it disappears entirely.

This creates a "memory" system where the player sees enemies at their last known positions, adding tactical depth to corridor navigation.

**Exercise 5: Ambient Exploration**

Instead of the entire map starting as unknown, reveal the tiles immediately around the player's starting position as explored. This gives the player a small area of visibility when they begin a new level, preventing the disorienting experience of starting in complete darkness:

```python
# After placing the player
game_map.explored[
    player_y - 2 : player_y + 3,
    player_x - 2 : player_x + 3,
] = True
```

This reveals a 5x5 area around the player as explored (but not visible until FOV is computed). Combine this with the initial FOV computation to ensure the starting room is immediately visible.

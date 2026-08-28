# Chapter 9: Procedural Dungeon Generation

Up to this point, every level in our game has been hand-crafted or generated with trivially simple algorithms. That works for testing, but it is not a roguelike. The core promise of the genre is that every playthrough is different. You descend into a dungeon you have never seen before, fight enemies you did not expect, and find items in places that were not there last time. That promise depends on procedural generation: algorithms that produce unique, playable levels from compact code and random seeds.

This chapter builds the dungeon generator for our game. We will use Binary Space Partitioning (BSP) as the primary algorithm, implement it step by step, and integrate it with the ECS registry so that every level is populated with the player, enemies, items, and stairs. By the end, you will have a generator that produces hundreds of unique dungeon layouts, each one different from the last.

## Why Procedural Generation?

A hand-designed dungeon level is a static artifact. You can make it excellent, but you can only play it once before you know every room, every corridor, and every ambush. Roguelikes reject this. The value of a roguelike is exploration---the feeling that what lies beyond the visible map is unknown and possibly dangerous. Procedural generation is how we create that feeling at scale.

Consider the math. A modest dungeon generator that produces maps with 10 to 20 rooms, where each room can vary in size, position, and contents, creates billions of possible layouts. A more complex generator with multiple room types, variable connectivity, and themed zones multiplies that number further. From a few hundred lines of code, you get a game with effectively infinite content.

This density matters. A roguelike that lasts twenty minutes per run needs enough variety to feel fresh after the hundredth playthrough. Hand-designing a hundred unique levels is months of work. A well-tuned procedural generator produces them in milliseconds.

The tradeoff is control. A hand-designed level guarantees a specific experience: a dramatic entrance, a carefully balanced combat encounter, a hidden reward. Procedural generation offers no such guarantees. The skill of the designer shifts from placing individual rooms to designing the algorithm itself---tuning parameters, defining constraints, and building feedback loops that produce levels that are not just random, but playable and interesting.

## Approaches to Dungeon Generation

There are many algorithms for generating dungeon-like spaces. Each produces different aesthetics and gameplay patterns. Understanding the options helps you choose the right one---or combine several.

**Binary Space Partitioning (BSP)** recursively divides the map into smaller rectangles, then places rooms inside the resulting cells. The result is a classic "rooms and corridors" dungeon with guaranteed connectivity and well-proportioned rooms. BSP is deterministic, fast, and produces reliable layouts. It is our primary algorithm.

**Cellular Automata** starts with a random grid of walls and floor, then applies rules that simulate erosion or growth. Cells surrounded by floor become floor; cells surrounded by walls become walls. After several iterations, the grid settles into cave-like patterns with organic shapes and winding passages. Cellular automata excels at producing natural-looking caves but offers less control over room placement and connectivity.

**Drunkard's Walk** places a virtual "drunkard" on the map who stumbles randomly, carving floor tiles as he goes. The result is a single connected region with an irregular, wandering shape. Drunkard's walk is simple to implement and produces organic tunnels, but it does not create rooms---it is best used as a component of a larger generator, adding winding passages between structured areas.

**Wave Function Collapse (WFC)** treats the map as a grid of cells, each of which can hold a tile type. It places tiles one at a time, choosing each based on constraints from its neighbors. WFC can produce highly structured, tileset-aware layouts with coherent architecture, but it is complex to implement and tune. It is best suited for games where the dungeon has a strong visual theme that requires consistent tile adjacency.

We will implement BSP as our primary generator and explore the other algorithms as exercises. BSP gives us the best combination of reliability, simplicity, and gameplay quality for a traditional roguelike.

## Binary Space Partitioning (BSP)

The BSP algorithm works by recursively splitting the map into smaller and smaller rectangles, then placing a room inside each leaf node. Rooms in sibling nodes are connected with corridors. The recursive splitting guarantees that rooms are reasonably sized and evenly distributed, and the tree structure provides a natural way to connect them.

Here is the intuition. Imagine a large rectangular dungeon level. We cut it in half, either vertically or horizontally, producing two smaller rectangles. We cut each of those in half again. We keep cutting until the rectangles are small enough to hold a single room. Now we have a grid-like arrangement of rooms with empty space between them. We carve corridors through the empty space to connect each pair of sibling rooms. The result is a connected dungeon.

The BSP tree is the data structure that tracks this process. Each node in the tree represents a rectangle on the map. Internal nodes are rectangles that were split. Leaf nodes are rectangles that are small enough to contain a room. The tree structure tells us which rooms to connect: every pair of sibling nodes in the tree needs a corridor.

### The BSP Algorithm Step by Step

Let us walk through the algorithm in detail before writing any code.

**Step 1: Start with the full map.** The root node of the BSP tree covers the entire map rectangle. At this point, the tree has one node and no splits.

**Step 2: Choose a split direction.** We decide whether to split the current node horizontally or vertically. The choice can be random, or it can favor one direction based on the node's aspect ratio. A node that is much wider than it is tall should be split vertically to produce more square children. A node that is much taller than it is wide should be split horizontally.

**Step 3: Choose a split position.** We pick a point along the chosen axis to divide the node. The split point is random but constrained: each child must be at least `min_size` tiles wide and tall. This prevents the algorithm from creating impossibly thin nodes that cannot hold a room.

**Step 4: Recurse on each child.** We repeat steps 2 and 3 for each child node. The recursion continues until a node is too small to split---both its width and height are below `min_size * 2`, or we have reached a maximum recursion depth.

**Step 5: Place rooms in leaf nodes.** Each leaf node becomes a room. The room is smaller than the node by a margin, ensuring that walls from adjacent rooms do not overlap. The room's position within the node is random, giving each level a different layout even with the same BSP tree.

**Step 6: Connect sibling rooms.** We walk back up the tree. For each internal node, we connect the rooms in its two children with a corridor. The corridor is L-shaped: it goes horizontally from one room's center to the midpoint, then vertically to the other room's center. The order (horizontal first or vertical first) is random.

This produces a dungeon where every room is reachable from every other room. The BSP tree guarantees connectivity because every leaf node is connected to its sibling, and every pair of siblings shares a parent that connects them to the rest of the tree.

### Using tcod.bsp

tcod provides a `BSP` class that implements the tree structure and the recursive splitting. This saves us from writing the splitting logic ourselves, though we still need to implement room placement and corridor carving.

```python
import tcod.bsp

root = tcod.bsp.BSP(x=0, y=0, width=80, height=45)
root.split_recursive(
    depth=5,
    min_width=15,
    min_height=15,
    max_ratio=1.5,
)
```

The `split_recursive` method does the heavy lifting. It takes four parameters:

- **`depth`** -- The maximum recursion depth. A depth of 5 means the tree can split up to 5 times, producing up to 32 leaf nodes. More depth means more, smaller rooms. Less depth means fewer, larger rooms. A depth of 4 to 6 works well for most dungeon sizes.

- **`min_width` and `min_height`** -- The minimum size of a leaf node in tiles. Nodes smaller than this will not be split further. This controls the minimum room size indirectly: a room must fit inside its node, so the node must be at least a few tiles larger than the minimum room size.

- **`max_ratio`** -- The maximum allowed aspect ratio of a child node after splitting. A ratio of 1.5 means a node that is 30 tiles wide will not be split vertically at a position that would produce a child wider than 45 tiles (30 * 1.5). This prevents extremely elongated nodes.

After `split_recursive` completes, the BSP tree is ready. We iterate over the leaf nodes to place rooms and traverse the tree to generate corridors.

## Room Placement

Each leaf node in the BSP tree becomes a room. The room is smaller than the node, leaving a margin for walls and corridors. The room's position within the node is randomized, which is what gives each dungeon its unique layout even when the BSP tree structure is the same.

Here is the room placement function:

```python
import random
from dataclasses import dataclass


@dataclass
class Room:
    """A rectangular room in the dungeon."""

    x: int
    y: int
    width: int
    height: int

    @property
    def center(self) -> tuple[int, int]:
        """Return the center tile of the room."""
        return (self.x + self.width // 2, self.y + self.height // 2)

    @property
    def inner(self) -> list[tuple[int, int]]:
        """Return all tiles inside the room (excluding walls)."""
        tiles = []
        for x in range(self.x + 1, self.x + self.width - 1):
            for y in range(self.y + 1, self.y + self.height - 1):
                tiles.append((x, y))
        return tiles
```

The `Room` class is a simple data container. The `center` property returns the coordinates of the room's center tile, which we use for corridor connections and entity placement. The `inner` property returns all tiles strictly inside the room, excluding the border tiles that serve as walls.

Placing a room inside a leaf node:

```python
def place_room(node: tcod.bsp.BSP, room_min: int = 6, room_max: int = 10) -> Room | None:
    """Place a random room inside a BSP leaf node.

    Returns None if the node is too small for a room.
    """
    margin = 2
    max_w = min(room_max, node.width - margin * 2)
    max_h = min(room_max, node.height - margin * 2)

    if max_w < room_min or max_h < room_min:
        return None

    w = random.randint(room_min, max_w)
    h = random.randint(room_min, max_h)

    x = random.randint(node.x + margin, node.x + node.width - w - margin)
    y = random.randint(node.y + margin, node.y + node.height - h - margin)

    return Room(x=x, y=y, width=w, height=h)
```

The margin ensures that rooms do not touch the edges of their nodes, leaving space for corridors. We clamp the room dimensions to fit inside the node. If the node is too small to hold a minimum-sized room, we return `None`---this is rare with properly tuned BSP parameters but important to handle.

The room position is random within the valid range. This means two runs with the same BSP tree structure produce different room layouts. The rooms are in different places, corridors take different paths, and the gameplay experience is different.

## Corridor Generation

Corridors connect the centers of sibling rooms. Each pair of rooms that share a parent node in the BSP tree gets a corridor. The corridor is L-shaped: it travels horizontally from one room's center to a midpoint, then vertically to the other room's center.

```python
def carve_horizontal_tunnel(
    tiles: list[list[int]], x1: int, x2: int, y: int
) -> None:
    """Carve a horizontal tunnel between x1 and x2 at row y."""
    for x in range(min(x1, x2), max(x1, x2) + 1):
        tiles[y][x] = 0  # Floor tile
        if y > 0:
            tiles[y - 1][x] = 1  # Wall above
        if y < len(tiles) - 1:
            tiles[y + 1][x] = 1  # Wall below


def carve_vertical_tunnel(
    tiles: list[list[int]], y1: int, y2: int, x: int
) -> None:
    """Carve a vertical tunnel between y1 and y2 at column x."""
    for y in range(min(y1, y2), max(y1, y2) + 1):
        tiles[y][x] = 0  # Floor tile
        if x > 0:
            tiles[y][x - 1] = 1  # Wall left
        if x < len(tiles[0]) - 1:
            tiles[y][x + 1] = 1  # Wall right


def carve_corridor(
    tiles: list[list[int]], x1: int, y1: int, x2: int, y2: int
) -> None:
    """Carve an L-shaped corridor between two points."""
    if random.random() < 0.5:
        # Horizontal first, then vertical
        carve_horizontal_tunnel(tiles, x1, x2, y1)
        carve_vertical_tunnel(tiles, y1, y2, x2)
    else:
        # Vertical first, then horizontal
        carve_vertical_tunnel(tiles, y1, y2, x1)
        carve_horizontal_tunnel(tiles, x1, x2, y2)
```

The corridor carving functions operate directly on the tile grid. A `0` represents a floor tile and a `1` represents a wall. When we carve a tunnel, we set the tunnel tiles to floor and ensure that the tiles above, below, left, and right of the tunnel are walls. This guarantees that corridors are properly enclosed.

The `carve_corridor` function creates an L-shaped path by combining a horizontal and vertical tunnel. The random choice of which direction comes first adds variety to the corridor layout. The midpoint of the L is the corner where the horizontal and vertical segments meet.

The two endpoints of the corridor are the centers of the rooms being connected. Because room centers are guaranteed to be floor tiles (they are inside the room), the corridor always connects two valid floor locations.

## Building the Complete Generator

Now we combine BSP splitting, room placement, and corridor carving into a single `generate_dungeon` function. This function takes parameters that control the dungeon's characteristics and returns a complete game map ready for play.

```python
# src/dungeon.py

from __future__ import annotations

import random
from dataclasses import dataclass, field

import tcod.bsp

# Tile constants
WALL = 1
FLOOR = 0


@dataclass
class DungeonLayout:
    """The output of dungeon generation.

    Contains the tile map and lists of positions for placing entities.
    """

    tiles: list[list[int]]
    rooms: list[Room]
    enemy_positions: list[tuple[int, int]]
    item_positions: list[tuple[int, int]]
    stairs_pos: tuple[int, int]
    start_pos: tuple[int, int]


def generate_dungeon(
    map_width: int,
    map_height: int,
    max_rooms: int,
    room_min_size: int,
    room_max_size: int,
    max_enemies: int,
    max_items: int,
    dungeon_level: int = 1,
) -> DungeonLayout:
    """Generate a complete dungeon level using BSP.

    Args:
        map_width: Width of the map in tiles.
        map_height: Height of the map in tiles.
        max_rooms: Maximum number of rooms to place.
        room_min_size: Minimum room dimension in tiles.
        room_max_size: Maximum room dimension in tiles.
        max_enemies: Maximum number of enemies to place.
        max_items: Maximum number of items to place.
        dungeon_level: Current dungeon floor (affects difficulty).

    Returns:
        A DungeonLayout with the tile grid and entity positions.
    """
    # Initialize the tile map with walls
    tiles = [[WALL for _ in range(map_width)] for _ in range(map_height)]

    # Create and split the BSP tree
    root = tcod.bsp.BSP(x=0, y=0, width=map_width, height=map_height)
    root.split_recursive(
        depth=5,
        min_width=room_min_size + 4,
        min_height=room_min_size + 4,
        max_ratio=1.5,
    )

    # Collect leaf nodes and place rooms
    rooms: list[Room] = []
    for node in root.leaves:
        if len(rooms) >= max_rooms:
            break
        room = place_room(node, room_min_size, room_max_size)
        if room is not None:
            # Check for overlap with existing rooms
            if not any(rooms_overlap(room, existing) for existing in rooms):
                carve_room(tiles, room)
                rooms.append(room)

    # Connect rooms with corridors
    for node in root.pre_order():
        if node.children:
            left_room = find_room_in_node(node.children[0], rooms)
            right_room = find_room_in_node(node.children[1], rooms)
            if left_room and right_room:
                x1, y1 = left_room.center
                x2, y2 = right_room.center
                carve_corridor(tiles, x1, y1, x2, y2)

    if not rooms:
        # Fallback: create a single room if BSP failed to produce any
        room = Room(x=1, y=1, width=map_width - 2, height=map_height - 2)
        carve_room(tiles, room)
        rooms.append(room)

    # Place entities
    start_pos = rooms[0].center
    stairs_pos = rooms[-1].center

    enemy_positions = place_entities(rooms, max_enemies, dungeon_level)
    item_positions = place_entities(rooms, max_items, dungeon_level)

    return DungeonLayout(
        tiles=tiles,
        rooms=rooms,
        enemy_positions=enemy_positions,
        item_positions=item_positions,
        stairs_pos=stairs_pos,
        start_pos=start_pos,
    )
```

This function is the entry point for all dungeon generation. It takes parameters that control the shape and density of the level, and returns a `DungeonLayout` that contains everything the game needs to set up a new floor.

The BSP depth is fixed at 5, but the room sizes are parameterized. Larger `room_min_size` and `room_max_size` values produce fewer, bigger rooms. Smaller values produce more, tighter rooms. The `max_rooms` parameter provides an upper bound on room count regardless of BSP depth.

The corridor generation walks the BSP tree in pre-order, connecting each parent node's children. This ensures every room is connected to at least one other room, and the tree structure guarantees that the entire dungeon is reachable.

### Helper Functions

The `generate_dungeon` function calls several helpers that we need to define:

```python
def rooms_overlap(a: Room, b: Room) -> bool:
    """Check if two rooms overlap, with a 1-tile buffer."""
    return (
        a.x - 1 < b.x + b.width
        and a.x + a.width + 1 > b.x
        and a.y - 1 < b.y + b.height
        and a.y + a.height + 1 > b.y
    )


def carve_room(tiles: list[list[int]], room: Room) -> None:
    """Carve a room into the tile map."""
    for x in range(room.x, room.x + room.width):
        for y in range(room.y, room.y + room.height):
            tiles[y][x] = FLOOR


def find_room_in_node(
    node: tcod.bsp.BSP, rooms: list[Room]
) -> Room | None:
    """Find the room whose center falls inside a BSP node."""
    cx, cy = node.x + node.width // 2, node.y + node.height // 2
    for room in rooms:
        rx, ry = room.center
        if rx == cx and ry == cy:
            return room
    # If no exact match, find any room that overlaps the node
    for room in rooms:
        if (room.x < node.x + node.width
                and room.x + room.width > node.x
                and room.y < node.y + node.height
                and room.y + room.height > node.y):
            return room
    return None
```

The `rooms_overlap` function checks whether two rooms intersect, with a 1-tile buffer to prevent shared walls. The `carve_room` function sets all tiles inside a room to floor. The `find_room_in_node` function maps BSP leaf nodes back to their rooms by matching center coordinates.

### Placing Entities

Entities are placed at random floor tiles inside rooms. The number of enemies and items scales with the dungeon level, making deeper floors more dangerous.

```python
def place_entities(
    rooms: list[Room],
    max_entities: int,
    dungeon_level: int,
) -> list[tuple[int, int]]:
    """Place entities at random positions inside rooms.

    The number of placed entities scales with dungeon level.
    """
    positions: list[tuple[int, int]] = []
    num_entities = random.randint(0, max_entities)

    for _ in range(num_entities):
        room = random.choice(rooms)
        x = random.randint(room.x + 1, room.x + room.width - 2)
        y = random.randint(room.y + 1, room.y + room.height - 2)
        if (x, y) not in positions:
            positions.append((x, y))

    return positions
```

This function returns a list of `(x, y)` tuples. The caller is responsible for creating actual entities from these positions. This separation keeps the dungeon generator independent of the ECS registry and the entity definitions. The generator produces coordinates; the game code turns those coordinates into entities with the appropriate components.

## Placing Features

Beyond generic enemies and items, certain features have fixed rules for placement.

**Stairs down** go in the last room. This is a convention in roguelikes: the player explores the level, finds the stairs, and descends. Placing the stairs in the last room means the player must traverse most of the dungeon to reach them, encouraging exploration.

```python
def place_stairs(rooms: list[Room]) -> tuple[int, int]:
    """Place stairs in the center of the last room."""
    return rooms[-1].center
```

**The starting position** goes in the first room. The player spawns in a known, safe location at the start of each level.

```python
def place_player(rooms: list[Room]) -> tuple[int, int]:
    """Place the player in the center of the first room."""
    return rooms[0].center
```

**Enemies** are distributed across rooms with density that increases with dungeon level. Early floors have few enemies. Later floors have many. Within a floor, enemies are placed at random floor tiles, with a check to avoid placing two enemies on the same tile.

**Items** follow a similar distribution to enemies but are less numerous. A typical ratio is one item for every two or three enemies. Items are placed before enemies to ensure that items always have valid floor positions.

### Entity Placement with the Registry

When we integrate the generator with the ECS registry, we create entities from the positions returned by the generator:

```python
def spawn_entities(
    registry: tcod.ecs.Registry,
    dungeon: DungeonLayout,
    dungeon_level: int,
) -> None:
    """Create ECS entities from a generated dungeon layout."""
    from components import (
        Position, Renderable, Name, Fighter, AI, AIKind,
        Item, XP,
    )

    # Spawn enemies
    enemy_templates = [
        ("k", (255, 0, 0), "Kobold", 8, 3, 0),
        ("o", (180, 0, 0), "Orc", 15, 5, 2),
        ("T", (0, 128, 0), "Troll", 25, 8, 4),
    ]

    for x, y in dungeon.enemy_positions:
        template = random.choice(enemy_templates)
        char, fg, name, hp, power, defense = template

        # Scale stats with dungeon level
        hp += dungeon_level * 2
        power += dungeon_level

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

    # Spawn items
    item_templates = [
        ("!", (128, 0, 255), "healing potion", "heal"),
        ("?", (255, 255, 0), "scroll of fireball", "fireball"),
    ]

    for x, y in dungeon.item_positions:
        template = random.choice(item_templates)
        char, fg, name, use_function = template

        entity = registry.new_entity()
        entity.components |= {
            Position: Position(x=x, y=y),
            Renderable: Renderable(char=char, fg=fg),
            Name: Name(name=name),
            Item: Item(name=name, use_function=use_function),
        }
        entity.tags.add("item")
```

This function bridges the gap between the generator and the ECS. The generator produces positions; this function creates entities with the right components and tags. Enemy stats scale with dungeon level, making deeper floors progressively harder. The templates are deliberately simple---the point is to show the integration pattern, not to design a full bestiary.

## Map Templates

Not every dungeon should look the same. A "rooms and corridors" dungeon feels different from a cave, which feels different from a vault. We can vary the dungeon's appearance by changing the generator's parameters and behavior.

**Rooms and Corridors** is our BSP generator with default parameters. It produces rectangular rooms connected by L-shaped corridors. This is the classic roguelike dungeon.

**Open Caves** can be produced by increasing room sizes and reducing the BSP depth, creating fewer, larger rooms that feel like open caverns. Alternatively, a cellular automata pass can replace the BSP output with organic cave shapes.

```python
def generate_cave(
    map_width: int,
    map_height: int,
    fill_probability: int = 45,
    iterations: int = 5,
) -> list[list[int]]:
    """Generate a cave using cellular automata.

    Args:
        map_width: Width of the map in tiles.
        map_height: Height of the map in tiles.
        fill_probability: Initial chance (0-100) of a tile being floor.
        iterations: Number of automata passes.

    Returns:
        A 2D tile grid (0 = floor, 1 = wall).
    """
    tiles = [[WALL for _ in range(map_width)] for _ in range(map_height)]

    # Random initial state
    for y in range(1, map_height - 1):
        for x in range(1, map_width - 1):
            if random.randint(0, 100) < fill_probability:
                tiles[y][x] = FLOOR

    # Apply cellular automata rules
    for _ in range(iterations):
        new_tiles = [row[:] for row in tiles]
        for y in range(1, map_height - 1):
            for x in range(1, map_width - 1):
                walls = count_walls(tiles, x, y)
                if walls > 4:
                    new_tiles[y][x] = WALL
                elif walls < 4:
                    new_tiles[y][x] = FLOOR
        tiles = new_tiles

    # Ensure border is all walls
    for x in range(map_width):
        tiles[0][x] = WALL
        tiles[map_height - 1][x] = WALL
    for y in range(map_height):
        tiles[y][0] = WALL
        tiles[y][map_width - 1] = WALL

    return tiles


def count_walls(tiles: list[list[int]], x: int, y: int) -> int:
    """Count the number of wall tiles in the 8 surrounding tiles."""
    count = 0
    for dy in range(-1, 2):
        for dx in range(-1, 2):
            if dx == 0 and dy == 0:
                continue
            if tiles[y + dy][x + dx] == WALL:
                count += 1
    return count
```

The cellular automata cave generator starts with a random grid and applies two rules: a tile surrounded by more than 4 walls becomes a wall, and a tile surrounded by fewer than 4 walls becomes floor. After several iterations, the grid settles into a natural-looking cave pattern. The result is always connected (assuming a reasonable fill probability and iteration count), but it does not produce discrete rooms---it is one continuous space with winding passages and open areas.

**Vaults** use a hybrid approach: BSP for the overall structure, but with larger rooms and thicker walls between them, giving the impression of a heavily fortified underground complex. The vault style uses the same BSP generator with adjusted parameters---larger minimum room sizes, a smaller BSP depth, and wider corridors.

## The Full BSP Generator

Here is the complete BSP dungeon generator, assembled from all the pieces above into a single module:

```python
# src/dungeon.py

from __future__ import annotations

import random
from dataclasses import dataclass

import tcod.bsp


WALL = 1
FLOOR = 0


@dataclass
class Room:
    """A rectangular room in the dungeon."""

    x: int
    y: int
    width: int
    height: int

    @property
    def center(self) -> tuple[int, int]:
        """Return the center tile of the room."""
        return (self.x + self.width // 2, self.y + self.height // 2)

    @property
    def inner(self) -> list[tuple[int, int]]:
        """Return all tiles strictly inside the room."""
        tiles = []
        for x in range(self.x + 1, self.x + self.width - 1):
            for y in range(self.y + 1, self.y + self.height - 1):
                tiles.append((x, y))
        return tiles


@dataclass
class DungeonLayout:
    """The output of dungeon generation."""

    tiles: list[list[int]]
    rooms: list[Room]
    enemy_positions: list[tuple[int, int]]
    item_positions: list[tuple[int, int]]
    stairs_pos: tuple[int, int]
    start_pos: tuple[int, int]


def rooms_overlap(a: Room, b: Room) -> bool:
    """Check if two rooms overlap, with a 1-tile buffer."""
    return (
        a.x - 1 < b.x + b.width
        and a.x + a.width + 1 > b.x
        and a.y - 1 < b.y + b.height
        and a.y + a.height + 1 > b.y
    )


def carve_room(tiles: list[list[int]], room: Room) -> None:
    """Carve a room into the tile map."""
    for x in range(room.x, room.x + room.width):
        for y in range(room.y, room.y + room.height):
            tiles[y][x] = FLOOR


def carve_horizontal_tunnel(
    tiles: list[list[int]], x1: int, x2: int, y: int
) -> None:
    """Carve a horizontal tunnel."""
    for x in range(min(x1, x2), max(x1, x2) + 1):
        tiles[y][x] = FLOOR
        if y > 0:
            tiles[y - 1][x] = WALL
        if y < len(tiles) - 1:
            tiles[y + 1][x] = WALL


def carve_vertical_tunnel(
    tiles: list[list[int]], y1: int, y2: int, x: int
) -> None:
    """Carve a vertical tunnel."""
    for y in range(min(y1, y2), max(y1, y2) + 1):
        tiles[y][x] = FLOOR
        if x > 0:
            tiles[y][x - 1] = WALL
        if x < len(tiles[0]) - 1:
            tiles[y][x + 1] = WALL


def carve_corridor(
    tiles: list[list[int]], x1: int, y1: int, x2: int, y2: int
) -> None:
    """Carve an L-shaped corridor between two points."""
    if random.random() < 0.5:
        carve_horizontal_tunnel(tiles, x1, x2, y1)
        carve_vertical_tunnel(tiles, y1, y2, x2)
    else:
        carve_vertical_tunnel(tiles, y1, y2, x1)
        carve_horizontal_tunnel(tiles, x1, x2, y2)


def place_room(
    node: tcod.bsp.BSP, room_min: int = 6, room_max: int = 10
) -> Room | None:
    """Place a random room inside a BSP leaf node."""
    margin = 2
    max_w = min(room_max, node.width - margin * 2)
    max_h = min(room_max, node.height - margin * 2)

    if max_w < room_min or max_h < room_min:
        return None

    w = random.randint(room_min, max_w)
    h = random.randint(room_min, max_h)
    x = random.randint(node.x + margin, node.x + node.width - w - margin)
    y = random.randint(node.y + margin, node.y + node.height - h - margin)

    return Room(x=x, y=y, width=w, height=h)


def find_room_in_node(
    node: tcod.bsp.BSP, rooms: list[Room]
) -> Room | None:
    """Find a room that overlaps a BSP node."""
    for room in rooms:
        if (
            room.x < node.x + node.width
            and room.x + room.width > node.x
            and room.y < node.y + node.height
            and room.y + room.height > node.y
        ):
            return room
    return None


def place_entities(
    rooms: list[Room],
    max_entities: int,
    dungeon_level: int,
) -> list[tuple[int, int]]:
    """Place entities at random positions inside rooms."""
    positions: list[tuple[int, int]] = []
    num_entities = random.randint(0, max_entities)

    for _ in range(num_entities):
        room = random.choice(rooms)
        x = random.randint(room.x + 1, room.x + room.width - 2)
        y = random.randint(room.y + 1, room.y + room.height - 2)
        if (x, y) not in positions:
            positions.append((x, y))

    return positions


def generate_dungeon(
    map_width: int,
    map_height: int,
    max_rooms: int,
    room_min_size: int,
    room_max_size: int,
    max_enemies: int,
    max_items: int,
    dungeon_level: int = 1,
) -> DungeonLayout:
    """Generate a complete dungeon level using BSP.

    Returns a DungeonLayout with the tile grid and entity positions.
    """
    tiles = [[WALL for _ in range(map_width)] for _ in range(map_height)]

    root = tcod.bsp.BSP(x=0, y=0, width=map_width, height=map_height)
    root.split_recursive(
        depth=5,
        min_width=room_min_size + 4,
        min_height=room_min_size + 4,
        max_ratio=1.5,
    )

    rooms: list[Room] = []
    for node in root.leaves:
        if len(rooms) >= max_rooms:
            break
        room = place_room(node, room_min_size, room_max_size)
        if room is not None:
            if not any(rooms_overlap(room, existing) for existing in rooms):
                carve_room(tiles, room)
                rooms.append(room)

    for node in root.pre_order():
        if node.children:
            left_room = find_room_in_node(node.children[0], rooms)
            right_room = find_room_in_node(node.children[1], rooms)
            if left_room and right_room:
                x1, y1 = left_room.center
                x2, y2 = right_room.center
                carve_corridor(tiles, x1, y1, x2, y2)

    if not rooms:
        room = Room(x=1, y=1, width=map_width - 2, height=map_height - 2)
        carve_room(tiles, room)
        rooms.append(room)

    start_pos = rooms[0].center
    stairs_pos = rooms[-1].center
    enemy_positions = place_entities(rooms, max_enemies, dungeon_level)
    item_positions = place_entities(rooms, max_items, dungeon_level)

    return DungeonLayout(
        tiles=tiles,
        rooms=rooms,
        enemy_positions=enemy_positions,
        item_positions=item_positions,
        stairs_pos=stairs_pos,
        start_pos=start_pos,
    )
```

This is the complete generator. It is roughly 180 lines of code, and it produces an unlimited number of unique dungeon layouts. The BSP algorithm guarantees connectivity and reasonable room sizes. The random room placement and corridor direction ensure variety. The parameterized interface lets the caller control room count, size, and entity density.

## Multiple Dungeon Levels

A roguelike is not a single level. It is a stack of descending floors, each harder than the last. The generator supports this through the `dungeon_level` parameter, which scales enemy count and stats. But the game needs more than just harder enemies to feel like it is progressing.

Each level should be slightly different from the last. This can be achieved by varying the generator parameters:

```python
def get_level_params(dungeon_level: int) -> dict:
    """Return generator parameters that scale with dungeon depth."""
    return {
        "map_width": 80,
        "map_height": 45,
        "max_rooms": min(10 + dungeon_level, 20),
        "room_min_size": 6,
        "room_max_size": 12,
        "max_enemies": 2 + dungeon_level * 2,
        "max_items": 1 + dungeon_level,
        "dungeon_level": dungeon_level,
    }
```

This function returns a parameter dictionary that the game passes to `generate_dungeon` when creating a new floor. The `max_rooms` increases with depth, producing larger, more complex dungeons. The enemy and item counts scale linearly, making each floor progressively more dangerous and rewarding.

### Seed-Based Generation

For debugging and sharing, it is useful to be able to reproduce a specific dungeon. This is done by seeding the random number generator:

```python
import random

def generate_level(dungeon_level: int, seed: int | None = None) -> DungeonLayout:
    """Generate a dungeon level with an optional seed for reproducibility."""
    if seed is not None:
        random.seed(seed + dungeon_level)

    params = get_level_params(dungeon_level)
    return generate_dungeon(**params)
```

By combining a base seed with the dungeon level, we get a different layout for each floor but the same layout every time the same seed is used. This is invaluable for testing: you can reproduce a specific dungeon to debug an issue, then discard the seed for normal play.

### Integrating with the Game Loop

The final piece is connecting the generator to the game loop. When the player descends the stairs, the game generates a new level and transitions to it:

```python
def descend_stairs(
    registry: tcod.ecs.Registry,
    dungeon_level: int,
) -> None:
    """Generate the next dungeon level and populate it."""
    from dungeon import generate_dungeon, get_level_params
    from components import Position, Renderable, Name, Fighter, XP

    # Clear existing entities (except player and world)
    for entity in list(registry.Q.all_of(tags=["enemy"])):
        registry.clear_entity(entity)
    for entity in list(registry.Q.all_of(tags=["item"])):
        registry.clear_entity(entity)
    for entity in list(registry.Q.all_of(tags=["staircase"])):
        registry.clear_entity(entity)

    # Generate new level
    params = get_level_params(dungeon_level)
    dungeon = generate_dungeon(**params)

    # Update world entity with new map
    world = registry[None]
    world.components[GameMap] = GameMap(tiles=dungeon.tiles)

    # Move player to new starting position
    player = registry["player"]
    player.components[Position] = Position(
        x=dungeon.start_pos[0], y=dungeon.start_pos[1]
    )

    # Spawn entities
    spawn_entities(registry, dungeon, dungeon_level)
```

This function clears the old level's entities, generates a new layout, updates the world map, repositions the player, and spawns new entities. The player entity and the world entity persist across levels---only the floor-specific entities are destroyed and recreated.

## Exercises

**Exercise 1: Cellular Automata Cave Generator**

Implement a cave generator using cellular automata. Start with a random grid where each tile has a 45% chance of being floor. Apply the automata rule (more than 4 neighboring walls becomes wall, fewer than 4 becomes floor) for 5 iterations. Ensure the border is all walls. Find the largest connected region of floor tiles and fill isolated pockets with walls.

**Exercise 2: Circular Room Variant**

Modify the room placement to produce circular rooms instead of rectangles. For each room, calculate which tiles fall within a given radius of the room's center. Only carve tiles within the radius. This produces rounded rooms that feel more organic than rectangular ones. You will need to adjust corridor carving to handle the curved room edges.

**Exercise 3: Drunkard's Walk Generator**

Implement a drunkard's walk generator. Place a virtual walker at the map center. On each step, the walker moves in a random direction and carves the tile it enters. After carving a configurable number of tiles (e.g., 30% of the total map area), stop. Ensure the result is a single connected region by running a flood fill from the start position and checking that it reaches all floor tiles. If not, run the drunkard's walk again.

**Exercise 4: Dungeon Statistics**

Write a function that analyzes a generated dungeon and prints statistics: number of rooms, average room size, total corridor length, distance from start to stairs, and the number of dead-end tiles (floor tiles with only one adjacent floor tile). Use this to tune your generator parameters and compare different algorithms.

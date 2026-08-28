# Chapter 20: Dungeon Levels and Stairs

A single dungeon level is a game. Multiple levels are a journey. The difference matters because a journey has progression---the player grows stronger, the dungeon grows harder, and the tension between those two curves is what keeps the player descending. A roguelike without multiple levels is a loop. A roguelike with them is an arc.

This chapter adds multi-level dungeons to our game. We build a stairs entity, wire up level transitions, scale difficulty with depth, and handle the state that persists across floors. By the end, the player can descend from floor to floor, fighting tougher enemies and finding better loot, with the current floor displayed in the UI at all times.

## Multi-Level Dungeons

The classic roguelike structure is a vertical descent. The player starts on floor 1, finds the stairs, and descends to floor 2. Each floor is a new map generated with the same algorithm but tuned to be harder. The dungeon grows deeper, the enemies grow stronger, and the loot grows richer. The player's goal is to reach the bottom---or at least to get as deep as possible before dying.

This structure works because it pairs naturally with difficulty scaling. Early floors are simple: few rooms, weak enemies, basic items. Later floors are complex: more rooms, tougher enemies, better equipment. The player's power grows linearly (more HP, better gear, higher levels), while the dungeon's difficulty grows faster. This creates an escalating challenge where the player must keep up or fall behind.

Each level is a fresh procedural generation. The player does not return to the same map. When they descend, the old floor is discarded and a new one is created. This simplifies state management enormously: we do not need to store explored maps for revisiting. The tradeoff is that backtracking is impossible in the simplest implementation, which we address later in the exercises.

## The Stairs Entity

Stairs are entities just like enemies and items. They live in the registry, have components, and are rendered to the map. The player interacts with them through a specific key press, not by bumping into them.

We need a new component to mark stairs, and a factory function to create them:

```python
# src/components/level.py

from __future__ import annotations

import attrs


@attrs.define
class Stairs:
    """Marks an entity as stairs leading to another dungeon floor."""

    floor: int = 1
```

The `floor` field records which floor the stairs lead to. For downward stairs, this is `current_floor + 1`. This field becomes useful later if we add branching paths or portals that lead to non-sequential floors. For now, it always points one level deeper.

The factory function creates a stairs entity at a given position:

```python
# src/factories/objects.py

from __future__ import annotations

import tcod.ecs

from components import Name, Position, Renderable
from components.level import Stairs


def create_stairs(
    registry: tcod.ecs.Registry,
    x: int,
    y: int,
    floor: int = 1,
) -> tcod.ecs.Entity:
    """Create a downward staircase entity."""
    entity = registry.new_entity()
    entity.components |= {
        Position: Position(x=x, y=y),
        Renderable: Renderable(char=">", fg=(200, 200, 0), render_order=0),
        Name: Name(name="Stairs"),
        Stairs: Stairs(floor=floor),
    }
    entity.tags.add("staircase")
    entity.tags.add("blocks_movement")
    return entity
```

The `">"` glyph is the traditional roguelike convention for downward stairs. The yellow color distinguishes it from most other floor objects. The `"staircase"` tag lets systems query for stairs without needing to check the `Stairs` component. The `"blocks_movement"` tag prevents the player from walking through the stairs tile---the player must explicitly press `>` to descend, not just walk over it.

Stairs are placed during dungeon generation, in the last room. The last room is the furthest from the starting position in most BSP layouts, so placing stairs there encourages the player to explore the full level before descending:

```python
# Inside generate_dungeon (from Chapter 9):

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
    # ... BSP generation and room placement ...

    start_pos = rooms[0].center
    stairs_pos = rooms[-1].center  # Last room gets the stairs

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

The `DungeonLayout` already includes `stairs_pos` from Chapter 9. Now we actually use it to create the stairs entity during level setup.

## Level Transitions

The core of multi-level dungeons is the level transition function. When the player descends, the game must clean up the current floor, generate a new one, and set up the player in the new environment. This is a single function that orchestrates several steps:

```python
# src/level_manager.py

from __future__ import annotations

import tcod.ecs

from components import (
    Inventory,
    Name,
    Position,
    Renderable,
    Fighter,
    XP,
)
from components.level import Stairs
from dungeon import generate_dungeon, get_level_params
from factories.actors import spawn_enemies
from factories.items import place_items
from factories.objects import create_stairs


def clear_floor_entities(registry: tcod.ecs.Registry) -> None:
    """Remove all enemies, items, and stairs from the current floor.

    The player entity and world entity are preserved.
    """
    for entity in list(registry.Q.all_of(tags=["enemy"])):
        registry.clear_entity(entity)
    for entity in list(registry.Q.all_of(tags=["item"])):
        registry.clear_entity(entity)
    for entity in list(registry.Q.all_of(tags=["staircase"])):
        registry.clear_entity(entity)


def descend_stairs(
    registry: tcod.ecs.Registry,
    dungeon_level: int,
) -> int:
    """Generate the next dungeon floor and populate it.

    Returns the new dungeon level number.
    """
    from engine.game_map import GameMap
    from components.world import GameWorld

    new_level = dungeon_level + 1

    # Step 1: Remove all floor-specific entities
    clear_floor_entities(registry)

    # Step 2: Generate a new map
    params = get_level_params(new_level)
    dungeon = generate_dungeon(**params)

    # Step 3: Update the world entity with the new map
    world = registry[None]
    gw = world.components[GameWorld]
    gw.current_map = GameMap(tiles=dungeon.tiles, rooms=dungeon.rooms)
    gw.dungeon_level = new_level

    # Step 4: Move the player to the starting position
    player = registry["player"]
    player.components[Position] = Position(
        x=dungeon.start_pos[0], y=dungeon.start_pos[1],
    )

    # Step 5: Create stairs in the last room
    create_stairs(
        registry,
        x=dungeon.stairs_pos[0],
        y=dungeon.stairs_pos[1],
        floor=new_level + 1,
    )

    # Step 6: Spawn enemies and items scaled to the new level
    spawn_enemies(registry, dungeon, new_level)
    place_items(registry, dungeon, skip_room=0)

    return new_level
```

The function follows a strict order. First, all floor-specific entities are destroyed. This includes enemies, items on the ground, and any existing stairs. The player entity and the world entity are untouched---they persist across floors. Second, a new map is generated using parameters scaled to the new floor number. Third, the world entity's map is replaced with the freshly generated one. Fourth, the player is repositioned to the first room. Fifth, stairs are placed in the last room. Sixth, enemies and items are spawned.

This function returns the new dungeon level, which the caller stores and passes back on the next descent. The caller is responsible for recomputing FOV after the transition, since the entire map has changed.

The order matters. Generating the map before clearing entities would be wasteful---we would create entities only to destroy them. Clearing before generating means there is a brief moment where the registry has no enemies, no items, and no map. This is safe because the transition is atomic from the player's perspective: the key press triggers the full sequence before the screen is redrawn.

## Difficulty Scaling

Deeper floors must be harder. The `get_level_params` function controls this by adjusting the generation parameters based on the floor number:

```python
# src/dungeon.py

def get_level_params(dungeon_level: int) -> dict:
    """Return dungeon generation parameters scaled to floor depth."""
    return {
        "map_width": 80,
        "map_height": 45,
        "max_rooms": min(8 + dungeon_level * 2, 25),
        "room_min_size": 6,
        "room_max_size": 12,
        "max_enemies": 2 + dungeon_level * 2,
        "max_items": 1 + dungeon_level,
        "dungeon_level": dungeon_level,
    }
```

Each parameter scales differently. `max_rooms` increases by 2 per floor, capped at 25 to keep maps navigable. `max_enemies` increases by 2 per floor, making combat encounters denser. `max_items` increases by 1 per floor, ensuring the player finds enough resources to keep up.

The enemy stats themselves also scale. In `spawn_enemies`, the factory adjusts hit points and power based on the dungeon level:

```python
# src/factories/actors.py

def spawn_enemies(
    registry: tcod.ecs.Registry,
    dungeon: "DungeonLayout",
    dungeon_level: int,
) -> None:
    """Create enemy entities from dungeon positions, scaled to floor depth."""
    # Available enemy types unlock at deeper floors
    enemy_pool = [
        ("kobold", 1),   # Available from floor 1
        ("orc", 3),       # Available from floor 3
        ("troll", 5),     # Available from floor 5
        ("ogre", 7),      # Available from floor 7
        ("dragon", 10),   # Available from floor 10
    ]

    available = [name for name, min_floor in enemy_pool if dungeon_level >= min_floor]

    for x, y in dungeon.enemy_positions:
        choice = random.choice(available)
        factory = ENEMY_FACTORIES[choice]
        entity = factory(registry, x, y)

        # Scale stats with floor depth
        fighter = entity.components[Fighter]
        level_bonus = dungeon_level - 1
        fighter.hp += level_bonus * 2
        fighter.max_hp = fighter.hp
        fighter.power += level_bonus
```

The `enemy_pool` list defines which enemy types are available at each floor depth. Kobolds appear from the start. Orcs appear at floor 3. Trolls at floor 5. This gating ensures the player encounters new threats at a steady pace, keeping the dungeon feeling fresh as they descend.

The stat scaling is simple but effective. Each floor adds 2 HP and 1 power to every enemy. A kobold with 8 HP on floor 1 becomes a kobold with 12 HP and 5 power on floor 3. The same enemy type feels more threatening at depth because it hits harder and survives longer.

### The Scaling Curve

The scaling creates two curves that interact. The player's power grows through leveling and equipment: each level adds HP and power, each new weapon adds more damage. The dungeon's difficulty grows through enemy density and stats: more enemies per floor, stronger enemies unlocked, all enemies scaled.

The player must stay ahead of the curve to survive. If they descend too quickly without leveling up, they face enemies that outscale them. If they farm too long on easy floors, they outlevel the challenges and the game becomes trivial. The sweet spot is descending at a pace that keeps the difficulty challenging but survivable.

The enemy pool gating is especially important here. By locking stronger enemy types behind floor thresholds, we prevent the player from encountering a dragon on floor 2. But we also prevent the dungeon from feeling stale. By the time the player reaches floor 5, they have fought dozens of kobolds and a handful of orcs. The introduction of trolls on floor 5 is a fresh threat that demands new tactics. Each new enemy type is a milestone in the player's journey.

The stat scaling on top of the pool gating ensures that even familiar enemies remain dangerous. A kobold on floor 8 has 22 HP and 10 power---roughly triple its floor-1 stats. The player who remembers kobolds as trivial will be surprised by how much damage they deal at depth. This keeps the player alert without introducing entirely new mechanics.

## Storing Game State Between Levels

The ECS registry is the central store for all game state. When transitioning between levels, some state persists and some is discarded.

**What persists:**

- The player entity and all its components (Position, Fighter, XP, Inventory, Equipment)
- The world entity and its global state (TurnCounter, GameState)
- The dungeon level number on the world entity

**What is discarded:**

- All enemy entities on the current floor
- All item entities on the ground
- The stairs entity
- The current GameMap

This separation is natural in ECS. Floor-specific entities are created during generation and destroyed during transitions. The player and world entities are created once at game start and live for the entire session. The key is that `clear_floor_entities` only targets entities with the `"enemy"`, `"item"`, or `"staircase"` tags, leaving everything else untouched.

The player's position is overwritten to the new floor's starting position. Their inventory, equipment, stats, and experience are untouched. This is the ECS advantage: the player's Position component is just one piece of data among many. Replacing it does not affect the others.

The world entity's `GameWorld` component holds the current map and floor number. Both are replaced on each transition. The turn counter continues to increment across floors, giving a measure of total game time.

## The Stairs Action

The player descends by standing on the stairs tile and pressing `>`. This requires two conditions: the player must be on a tile with a staircase entity, and the player must press the correct key.

The input handler translates the key into a `DescendAction`:

```python
# src/actions.py

import attrs


@attrs.define
class DescendAction(Action):
    """Descend the stairs to the next dungeon floor."""

    pass
```

The input handler checks for the `>` key (which is `KeySym.PERIOD` with the shift modifier in tcod):

```python
# src/input_handlers.py

    elif event.sym == tcod.event.KeySym.PERIOD and tcod.event.KMOD_SHIFT & event.mod:
        return DescendAction(entity=entity)
```

The main loop dispatches the action to the level manager:

```python
# src/main.py

from actions import DescendAction
from level_manager import descend_stairs


def _is_action_success(
    action: Action,
    registry: tcod.ecs.Registry,
    log: MessageLog,
) -> bool:
    if isinstance(action, DescendAction):
        return _handle_descend(registry, log)
    # ... other action branches ...


def _handle_descend(
    registry: tcod.ecs.Registry,
    log: MessageLog,
) -> bool:
    """Process the player's attempt to descend stairs."""
    from engine.game_map import GameMap
    from components.world import GameWorld

    player = registry["player"]
    ppos = player.components[Position]
    world = registry[None]
    game_map = world.components[GameWorld].current_map

    # Check that stairs exist at the player's position
    for entity, pos, stairs in registry.Q[Entity, Position, Stairs]:
        if pos.x == ppos.x and pos.y == ppos.y:
            new_level = descend_stairs(
                registry,
                world.components[GameWorld].dungeon_level,
            )
            log.add(
                f"You descend to floor {new_level}...",
                fg=(200, 200, 0),
            )
            return True

    log.add("There are no stairs here.", fg=(200, 200, 200))
    return False
```

The handler queries for staircase entities at the player's position. If one is found, it calls `descend_stairs` and logs the transition. If no stairs are present, it logs a message and returns `False` so no turn is spent.

After the transition, FOV must be recomputed because the entire map has changed. The main loop handles this by checking whether the map changed after each action:

```python
# After processing any action in the main loop:

def _advance_after_action(
    registry: tcod.ecs.Registry,
    log: MessageLog,
) -> None:
    """Run post-action systems: AI turns, FOV, cleanup."""
    from systems.fov import recompute_fov
    from systems.enemy_turns import process_enemy_turns
    from systems.death import remove_dead_entities

    process_enemy_turns(registry)
    remove_dead_entities(registry)
    recompute_fov(registry)
```

The FOV recomputation uses the new map automatically, since it reads from `registry[None].components[GameWorld].current_map`, which was replaced during the transition.

## Persistent Data

The distinction between persistent and transient data is what makes level transitions work cleanly. Here is the full picture:

| Data | Stored on | Persists? | Notes |
|------|-----------|-----------|-------|
| Player position | Player entity | Replaced each floor | Set to new floor's start |
| Player HP, stats | Player entity | Yes | Carries across all floors |
| Player inventory | Player entity | Yes | Items travel between floors |
| Player equipment | Player entity | Yes | Gear persists |
| Player XP and level | Player entity | Yes | Progress is permanent |
| Dungeon level | World entity | Replaced each floor | Incremented on descent |
| GameMap | World entity | Replaced each floor | New map generated |
| Turn counter | World entity | Yes | Counts total game turns |
| Enemy entities | Registry | No | Destroyed on descent |
| Item entities | Registry | No | Destroyed on descent |
| Stairs entity | Registry | No | Destroyed on descent |

The pattern is straightforward: data attached to the player or world entity persists. Data attached to floor-specific entities is destroyed. This works because the ECS naturally separates "who is the player" from "what is on this floor."

Items the player carries in their inventory are entities too, but they live in the player's `Inventory` component list, not on the map. They have no `Position` component and no `"item"` tag. The `clear_floor_entities` function does not touch them. A health potion carried from floor 1 is still in the player's inventory on floor 10.

This design has a useful side effect: items on the ground are ephemeral, but items in hand are permanent. The player cannot drop an item on floor 3, descend to floor 4, and return to find it waiting. This is a deliberate trade---it simplifies state management at the cost of making the descent a one-way decision. The player commits their inventory when they step on the stairs.

If you want items to persist on the ground (for a backtracking mechanic), you would need to store the floor's entity state separately from the registry. A dictionary keyed by floor number, mapping to a list of serialized entities, gives you that capability. The serialization is straightforward because our components are plain attrs classes with primitive fields. But that is an exercise, not a requirement---the base game works fine with ephemeral floors.

## Level Indicators

The player needs to know which floor they are on. The HUD should display the current dungeon level alongside the player's HP and other stats:

```python
# src/render_functions.py

def render_hud(
    console: tcod.console.Console,
    registry: tcod.ecs.Registry,
    player: tcod.ecs.Entity,
    x: int,
    y: int,
    width: int,
) -> None:
    """Render the player status bar with floor indicator."""
    from components.world import GameWorld
    from components import Fighter, Inventory, XP

    fighter = player.components[Fighter]
    xp = player.components.get(XP)
    inv = player.components.get(Inventory)
    world = registry[None]
    gw = world.components[GameWorld]

    parts = [f"HP: {fighter.hp}/{fighter.max_hp}"]
    parts.append(f"Floor: {gw.dungeon_level}")

    if xp is not None:
        parts.append(f"LVL: {xp.level}")
        parts.append(f"XP: {xp.current}/{xp.xp_to_next}")

    if inv is not None:
        parts.append(f"[I]nv: {len(inv.items)}/{inv.capacity}")

    hud_text = "  ".join(parts)
    console.print(x=x, y=y, string=hud_text[:width], fg=(255, 255, 255))

    # Hint line
    hint = "g:pickup  d:drop  i:inv  >:descend  1-9:use  .:wait"
    console.print(x=x, y=y + 1, string=hint[:width], fg=(180, 180, 180))
```

The `Floor: N` text is inserted into the HUD alongside the other status information. The player sees it at all times during gameplay. When they descend, the number updates on the next render.

We can also vary the visual theme per floor depth. Deeper floors can use different color palettes to suggest increasing danger:

```python
# src/tile_types.py

def get_floor_palette(dungeon_level: int) -> dict:
    """Return tile colors that shift with dungeon depth."""
    # Base colors for floor 1
    floor_dark_bg = (50, 50, 100)
    floor_light_bg = (50, 50, 100)

    # Shift toward red as depth increases
    depth = min(dungeon_level - 1, 20)
    red_shift = depth * 5

    return {
        "floor_dark_bg": (
            floor_dark_bg[0] + red_shift,
            floor_dark_bg[1],
            floor_dark_bg[2],
        ),
        "floor_light_bg": (
            floor_light_bg[0] + red_shift,
            floor_light_bg[1],
            floor_light_bg[2],
        ),
    }
```

This is optional polish. The palette shift is subtle on early floors and pronounced by floor 10, where the dungeon background has a warm, dangerous glow. The implementation hooks into the map rendering system, which reads the palette when drawing tiles.

## Special Levels

Not every floor should be a standard dungeon. Special floors appear at fixed intervals to break up the monotony and provide unique challenges or rewards.

The simplest approach is a modulo check on the floor number:

```python
# src/level_manager.py

def get_floor_type(dungeon_level: int) -> str:
    """Determine the type of floor based on the dungeon level."""
    if dungeon_level % 5 == 0:
        return "boss"
    elif dungeon_level % 7 == 0:
        return "treasure"
    elif dungeon_level % 10 == 0:
        return "shop"
    return "dungeon"


def descend_stairs(
    registry: tcod.ecs.Registry,
    dungeon_level: int,
) -> int:
    new_level = dungeon_level + 1
    floor_type = get_floor_type(new_level)

    clear_floor_entities(registry)

    if floor_type == "boss":
        _generate_boss_floor(registry, new_level)
    elif floor_type == "treasure":
        _generate_treasure_floor(registry, new_level)
    elif floor_type == "shop":
        _generate_shop_floor(registry, new_level)
    else:
        _generate_standard_floor(registry, new_level)

    return new_level
```

Each floor type has its own generation function. The boss floor creates a single large room with a powerful enemy. The treasure floor generates a small map packed with items. The shop floor places a friendly NPC that trades with the player. The standard floor uses our existing BSP generator.

### Boss Floors

Boss floors appear every 5 levels. They use a different generator that produces a single large arena:

```python
# src/level_manager.py

def _generate_boss_floor(
    registry: tcod.ecs.Registry,
    dungeon_level: int,
) -> None:
    """Generate a boss floor with a single large room and a powerful enemy."""
    from engine.game_map import GameMap
    from components.world import GameWorld
    from components import Position
    from factories.actors import create_boss

    # Generate a simple open map
    map_width, map_height = 40, 30
    tiles = [[1] * map_width for _ in range(map_height)]

    # Carve a large rectangular room
    for y in range(3, map_height - 3):
        for x in range(3, map_width - 3):
            tiles[y][x] = 0  # Floor

    world = registry[None]
    gw = world.components[GameWorld]
    gw.current_map = GameMap(tiles=tiles)
    gw.dungeon_level = dungeon_level

    # Place the player at the entrance
    player = registry["player"]
    player.components[Position] = Position(x=5, y=15)

    # Place the boss in the center
    boss_level = dungeon_level // 5
    create_boss(registry, x=30, y=15, tier=boss_level)

    # Place stairs behind the boss
    create_stairs(registry, x=35, y=15, floor=dungeon_level + 1)
```

The boss floor is a departure from the corridor-and-room layout. The single room forces a direct confrontation. The boss is placed in the center, the player at the entrance, and the stairs behind the boss. The player must defeat the boss to reach the stairs.

### Treasure Floors

Treasure floors appear every 7 levels. They are small maps filled with items but few enemies:

```python
def _generate_treasure_floor(
    registry: tcod.ecs.Registry,
    dungeon_level: int,
) -> None:
    """Generate a treasure floor with many items and few enemies."""
    from engine.game_map import GameMap
    from components.world import GameWorld
    from components import Position

    map_width, map_height = 30, 20
    tiles = [[1] * map_width for _ in range(map_height)]

    # Carve a medium room
    for y in range(2, map_height - 2):
        for x in range(2, map_width - 2):
            tiles[y][x] = 0

    world = registry[None]
    gw = world.components[GameWorld]
    gw.current_map = GameMap(tiles=tiles)
    gw.dungeon_level = dungeon_level

    player = registry["player"]
    player.components[Position] = Position(x=3, y=10)

    # Place many items, few enemies
    from factories.items import place_items

    # Create a fake DungeonLayout for item placement
    from dungeon import Room
    fake_room = Room(x=2, y=2, width=map_width - 4, height=map_height - 4)
    fake_dungeon = type("D", (), {
        "rooms": [fake_room],
        "item_positions": [],
    })()

    # Place 8-12 items
    for _ in range(random.randint(8, 12)):
        ix = random.randint(4, map_width - 5)
        iy = random.randint(4, map_height - 5)
        if tiles[iy][ix] == 0:
            from factories.items import create_random_item
            create_random_item(registry, ix, iy)

    # Place a single guardian
    from factories.actors import create_orc
    create_orc(registry, x=15, y=10)

    create_stairs(registry, x=map_width - 4, y=10, floor=dungeon_level + 1)
```

Treasure floors are a reward. The player enters a room with more items than they can carry and must choose what to take. The single guardian is a speed bump, not a real threat. The floor rewards exploration and inventory management.

## The Full Transition Sequence

Here is the complete flow when the player presses `>` on the stairs:

1. The input handler produces a `DescendAction`.
2. The main loop dispatches to `_handle_descend`.
3. `_handle_descend` checks for a staircase entity at the player's position.
4. If found, it calls `descend_stairs` with the current floor number.
5. `descend_stairs` increments the floor number and determines the floor type.
6. `clear_floor_entities` destroys all enemies, items, and stairs.
7. A new map is generated (standard, boss, treasure, or shop).
8. The world entity's `GameMap` and `dungeon_level` are updated.
9. The player's `Position` is set to the new floor's starting position.
10. Stairs are placed in the last room (or appropriate location for special floors).
11. Enemies and items are spawned, scaled to the new floor depth.
12. `descend_stairs` returns the new floor number.
13. The message log records the descent.
14. The action is marked as successful, triggering a turn advance.
15. Enemy turns process (if any exist on the new floor).
16. FOV is recomputed for the new map.
17. The screen is redrawn with the new floor, new entities, and updated HUD.

Steps 5 through 11 happen inside `descend_stairs`. Steps 12 through 17 happen in the main loop's post-action sequence. The player sees a message, the map changes, and the floor counter increments in the HUD. The transition takes a single key press.

## Summary

Multi-level dungeons turn a single-floor dungeon crawl into a descending journey with escalating stakes. The stairs entity is the bridge between floors: a simple marker in the last room that the player activates with `>`. The `descend_stairs` function is the engine of transition: it clears the old floor, generates the new one, and repositions the player.

Difficulty scaling ties the dungeon's challenge to the floor number. More rooms, more enemies, stronger enemy types, and scaled stats ensure that each floor feels harder than the last. The player's power must keep pace through leveling and equipment, or the dungeon will overwhelm them.

The persistence model is clean: player data and world data survive transitions. Floor-specific entities do not. The ECS makes this natural, because floor entities live in the registry with tags that identify them, and `clear_floor_entities` removes them without touching the player or world.

Special floors---boss arenas, treasure vaults, shops---break up the standard dungeon generation at fixed intervals. They offer variety, challenge, and reward in proportions that the standard generator cannot. They are optional polish, but they transform the descent from a repetition into a rhythm with peaks and valleys.

The HUD displays the current floor at all times, grounding the player in their descent. Every key press on a deeper floor carries the weight of knowing that the next floor will be harder.

## Exercises

**Exercise 1: Implement a Back Mechanic**

Add the ability to return to previous dungeon floors. When the player presses `<` on an upward staircase, they ascend to the previous floor. This requires storing the previous floor's map, entities, and the player's position on that floor. Consider using a stack of floor states: each time the player descends, push the current floor state onto the stack. Each time they ascend, pop and restore. Decide what persists in the saved state (map only? enemies too?) and what is regenerated.

**Exercise 2: Add Branch Dungeons**

Instead of a single linear descent, offer the player a choice of two staircases on certain floors. One leads to an easy path with fewer enemies and worse loot. The other leads to a hard path with more enemies and better loot. Both converge at a boss floor every 5 levels. Implement this by placing two staircase entities on branching floors and tracking which path the player chose.

**Exercise 3: Create Themed Levels**

Implement three distinct floor themes that rotate or appear at specific depths. A fire theme uses red floor tiles, lava hazards (tiles that deal damage when walked on), and fire-resistant enemies. An ice theme uses blue tiles, slippery movement (the player slides one extra tile when moving), and frost enemies. A forest theme uses green tiles, dense vegetation that blocks line of sight, and animal enemies. Each theme modifies the tile palette, the enemy pool, and adds one unique mechanic.

**Exercise 4: Implement Floor Memory**

Store a snapshot of each floor the player has visited: the explored tile array, the positions of remembered entities, and the player's position when they left. When the player returns to a previous floor (Exercise 1), restore these snapshots instead of regenerating. This creates a persistent world where the player's actions have lasting effects on the dungeon layout.

**Exercise 5: Scaling Formula**

Replace the linear scaling in `get_level_params` with a curve. Use a formula like `base + int(level ** 1.5)` for enemy count and `base + level * 1.5` for stat bonuses. Graph the output for floors 1 through 20 and compare it to the linear version. Tune the formula until early floors feel manageable and late floors feel punishing. Consider making the curve configurable per difficulty setting.

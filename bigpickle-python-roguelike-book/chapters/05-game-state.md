# Chapter 5: Managing Game State with the ECS Registry

In Chapter 4, we built a working game loop. The player moves across a procedurally generated map, enemies stand around doing nothing interesting, and the game renders to a tcod console. It works, but every piece of state lives as a bare variable at the top of a function or as an attribute on a class that knows too much. The player position is `player_x` and `player_y`. The map is a local variable inside `generate_dungeon`. The game level is an integer passed through function arguments.

This is fine for a prototype. It is not fine for a game.

This chapter makes the first real architectural move: we replace scattered variables with a central data store and adopt the ECS pattern we introduced in Chapter 2. By the end, every entity in the game -- the player, monsters, items, the game world itself -- lives inside a single registry that any system can read and write. This is the foundation that everything in Part II builds on.

## Why Separate Game State?

Consider what happens when you want to add a simple feature: displaying the player's health in the HUD. In the Chapter 4 code, you would need to thread a health value through every function that might need it. The render function needs it. The input handler might need it to decide whether to show a death screen. The combat system needs it to apply damage. Each function gets another parameter, another thing to remember, another opportunity for a mismatch.

Now consider adding a second creature with health. Now you need `player_health` and `enemy_health`. When you add a third creature, you need a list. When you add items, you need separate tracking for those. When you add dungeon levels, each level needs its own set of entities. The state management problem grows combinatorially.

The ECS Registry solves this by being the single place where all game data lives. Every system reads from it. Every system writes to it. No function needs to know where data came from or who else is using it. The registry is the game's memory.

## The ECS Registry as Game State

We met the registry briefly in Chapter 2. Now we will use it for real.

```python
import tcod.ecs

registry = tcod.ecs.Registry()
```

That single line creates an empty container. It holds nothing. But it is ready to hold everything: every entity, every component, every tag, every relationship in the game.

Entities are created with a call to `new_entity()`:

```python
player = registry.new_entity()
goblin = registry.new_entity()
sword = registry.new_entity()
```

Each call returns a reference to a new, unique entity. These references are lightweight objects that serve as keys into the registry's storage. You do not need to store them in variables if you do not plan to use them immediately -- the registry keeps them alive.

You can also create entities with explicit string keys for easier debugging and later retrieval:

```python
player = registry.new_entity(key="player")
goblin = registry.new_entity(key="goblin_01")
```

String keys let you look up entities by name:

```python
same_player = registry["player"]
```

This will be essential when we need to find the player entity from deep inside a system function, without threading it through every call.

**The Global Entity**

Every registry has a special "global" entity accessed via `registry[None]`. This entity has no key of its own -- it is the null entity, the place to store data that belongs to the game as a whole rather than to any specific entity. We will use it extensively for game-wide state like the current map, the dungeon level, and the turn counter.

```python
world = registry[None]
```

Think of `registry[None]` as the game's whiteboard. Any system can read or write data here without needing a reference passed in. If the movement system needs to know which map to check for walls, it reads from `registry[None]`. If the render system needs to know the current dungeon level, it reads from `registry[None]`.

## Defining the Game State

Let us plan out what lives where before we write component classes.

The **world entity** (`registry[None]`) holds global state that is not tied to any specific creature or item:

- The current game map (a numpy array of tiles)
- The dungeon floor number
- The total number of turns elapsed
- The current game state (is the player in a menu, playing, or dead?)

The **player entity** (`registry["player"]`) holds everything about the player:

- Position on the map
- Health (current and maximum)
- Appearance (what character and color to render)
- A tag marking it as the player

**Monster entities** hold their own positions, health, and appearance, plus an AI tag or component that determines their behavior.

**Item entities** hold their position and appearance, plus data about what they do when used.

This separation means that the movement system does not need to know whether an entity is a player, a monster, or a wandering shopkeeper. It queries for entities with a `Position` component and processes them all the same way. The rendering system does not need to know about health or AI. It queries for entities with `Position` and `Renderable` and draws them.

## Introducing attrs for Components

Components in our ECS are plain data classes. We could write them as standard Python classes with `__init__` methods, or use the `dataclasses` module from the standard library. But we use **attrs** instead, and there are good reasons for it.

```python
from attrs import define
```

The `@define` decorator from attrs generates `__init__`, `__repr__`, `__eq__`, and other dunder methods automatically. It also provides `frozen` (immutable instances), `slots` (memory-efficient attribute storage), and built-in validation -- features that `dataclasses` either lacks or implements less cleanly.

Here is why each matters for game components:

- **`slots`**: Components are created and destroyed frequently. Slots reduce memory overhead per instance, which matters when you have hundreds of entities each carrying multiple components.
- **`frozen`**: Immutable components prevent accidental modification. When a system reads a component, it can trust that no other system is modifying it in place at the same time. For mutable components, attrs still gives you a clean `__init__` and `__repr__`.
- **`repr`**: When debugging, you want to see `Position(x=5, y=3)`, not `<object at 0x7f3b2c1d4e58>`. attrs gives you readable output for free.

The dependency is already installed from Chapter 3. If it is not in your environment, run `uv add attrs` or `pip install attrs`.

## Creating Our First Components

Start with the most basic components. These are small, focused data classes that each describe one aspect of an entity.

```python
from attrs import define

@define
class Position:
    """Where an entity is on the map."""
    x: int = 0
    y: int = 0

@define
class Renderable:
    """How an entity appears on screen."""
    char: str = "?"
    color: tuple[int, int, int] = (255, 255, 255)

@define
class Health:
    """How much damage an entity can take."""
    current: int = 10
    maximum: int = 10
```

Each component does one thing. `Position` stores coordinates. `Renderable` stores display data. `Health` stores hit points. None of them contain logic. None of them know about each other.

Now add components for game-wide state:

```python
@define
class GameWorld:
    """Global state for the game."""
    current_map: object = None
    dungeon_level: int = 1
    turn_count: int = 0
```

The `current_map` field holds a reference to whatever map object we generate. For now it can be `None` -- we will populate it when we wire up map generation.

**File organization**

Create a file for your component definitions. Following the project structure from Chapter 3:

```
src/components/
    __init__.py
    physical.py    # Position, Renderable
    combat.py      # Health, Power
```

For now, keep all components in a single file if you prefer. The important thing is that they live in a dedicated location, not scattered across the files that use them.

## Storing and Retrieving Components

Components are stored on entities using the entity's `components` dictionary, keyed by the component class itself:

```python
player = registry.new_entity(key="player")

# Attach components
player.components[Position] = Position(x=5, y=3)
player.components[Renderable] = Renderable(char="@", color=(255, 255, 0))
player.components[Health] = Health(current=30, maximum=30)
```

The type of the component class is the key. This means each entity can have at most one component of each type. If you call `player.components[Position] = Position(x=10, y=10)` again, it replaces the previous value. This is by design -- an entity has one position, one health, one appearance. If you need multiple values of the same type (like multiple equipment slots), use named components as described in Chapter 2.

Retrieving components is equally straightforward:

```python
pos = player.components[Position]
print(f"Player is at ({pos.x}, {pos.y})")

hp = player.components[Health]
print(f"Player has {hp.current}/{hp.maximum} HP")
```

Accessing a component that does not exist raises a `KeyError`. If you are not sure whether an entity has a particular component, use `.get()`:

```python
health = player.components.get(Health)
if health is not None:
    print(f"HP: {health.current}")
```

**Mutating components**

Since attrs classes are mutable by default (unless you use `frozen=True`), you can modify component fields in place:

```python
hp = player.components[Health]
hp.current -= 5
print(hp.current)  # 25
```

Or replace the entire component:

```python
player.components[Health] = Health(current=25, maximum=30)
```

Both approaches work. Modifying in place is slightly more efficient. Replacing the component is cleaner when you want to ensure a consistent state. Choose based on context.

## Tags as Flags

Some properties are boolean. An entity is either alive or dead. It either blocks movement or it does not. It is either the player or it is not. Tags handle these cases without the overhead of a full component class.

```python
player = registry.new_entity(key="player")

# Add tags
player.tags.add("alive")
player.tags.add("player")
player.tags.add("blocks_movement")

# Check tags
if "alive" in player.tags:
    print("Player is alive")

# Remove a tag
player.tags.discard("blocks_movement")

# Check after removal
print("blocks_movement" in player.tags)  # False
```

Tags are strings. They are stored in a set on each entity, so adding and checking them is fast. Use `add()` to set a tag, `discard()` to remove it (without error if it is missing), and `in` to test for presence.

Here are common tag patterns for a roguelike:

```python
# Entity categories
player.tags.add("player")
enemy.tags.add("hostile")
item.tags.add("pickupable")

# State flags
entity.tags.add("alive")
entity.tags.add("paralyzed")
entity.tags.add("poisoned")

# Physical properties
wall.tags.add("blocks_movement")
wall.tags.add("blocks_light")
door.tags.add("blocks_movement")
door.tags.add("transparent")
```

Tags are also queryable, which means the movement system can skip entities tagged `"paralyzed"` and the render system can distinguish `"visible"` from `"explored"` tiles. We will see this in action when we build the query-based systems in Part II.

## Global Game State

The world entity stores data that belongs to the game as a whole:

```python
# Create the world entity (always accessible via registry[None])
world = registry[None]

# Attach game-wide state
world.components[GameWorld] = GameWorld(
    dungeon_level=1,
    turn_count=0,
)
world.tags.add("in_game")
```

Any system can now access global state without receiving it as a parameter:

```python
def advance_turn(registry: tcod.ecs.Registry) -> None:
    """Increment the turn counter after the player acts."""
    world = registry[None]
    gw = world.components[GameWorld]
    gw.turn_count += 1
    print(f"Turn {gw.turn_count}")
```

This pattern eliminates the need to pass game state through long chains of function calls. The registry is the single source of truth, and `registry[None]` is the place for data that has no owner.

You can attach other entities for global references too:

```python
# Store a reference to the player entity on the world entity
# so any system can find it
world.relation_tag["player"] = registry["player"]
```

This relation means any system can find the player with `registry[None].relation_tag["player"]`, which returns the player entity reference. No need to pass it through arguments or search for it by tag every frame.

## Game State Machine

Most roguelikes have distinct screens: a main menu, the game itself, a death screen, an inventory screen. The game loops through these states, processing input and rendering differently depending on which state is active.

The simplest approach is to represent states as tags on the world entity:

```python
# Start in the main menu
world.tags.add("main_menu")
world.tags.discard("in_game")
world.tags.discard("game_over")

# Transition to gameplay
def start_game(registry: tcod.ecs.Registry) -> None:
    world = registry[None]
    world.tags.discard("main_menu")
    world.tags.add("in_game")

# Transition to game over
def end_game(registry: tcod.ecs.Registry) -> None:
    world = registry[None]
    world.tags.discard("in_game")
    world.tags.add("game_over")
```

The main loop checks the current state to decide what to process:

```python
while True:
    console.clear()
    world = registry[None]

    if "main_menu" in world.tags:
        render_main_menu(console)
    elif "in_game" in world.tags:
        render_game(console, registry)
        process_input(registry)
    elif "game_over" in world.tags:
        render_game_over(console)

    context.present(console)

    for event in tcod.event.wait():
        if isinstance(event, tcod.event.Quit):
            return
```

This is a minimal state machine. Each state is a string tag. Transitions add and remove tags. The main loop dispatches based on which tag is present. It is simple, but it scales well -- adding a new state (like an inventory screen or a settings menu) means adding another tag check.

For more complex state data, use a component instead of a tag:

```python
@define
class GameState:
    """Tracks which screen is active."""
    current: str = "main_menu"
```

Then attach it to the world entity:

```python
world.components[GameState] = GameState(current="main_menu")
```

The main loop reads `world.components[GameState].current` and switches on its value. This approach lets you carry additional data with the state -- for example, a `GameState` component could also hold a selected menu item index or a death cause message.

## Refactoring Chapter 4's Code

Let us see the transformation in concrete terms. Here is the core of the Chapter 4 game, simplified to show the key state variables:

```python
# Chapter 4 style -- scattered state
player_x, player_y = 10, 5
player_hp = 30
player_max_hp = 30
game_map = generate_dungeon(width=80, height=45)
dungeon_level = 1
turn_count = 0
```

Every function that touches game state receives these as parameters or reads them from a class instance. The render function needs `player_x`, `player_y`, and `game_map`. The combat function needs `player_hp`. The map generation function returns `game_map`. Adding a new piece of state means adding a parameter to every function that needs it.

Here is the same state expressed with the ECS registry:

```python
import tcod.ecs
from attrs import define

@define
class Position:
    x: int = 0
    y: int = 0

@define
class Renderable:
    char: str = "?"
    color: tuple[int, int, int] = (255, 255, 255)

@define
class Health:
    current: int = 10
    maximum: int = 10

@define
class GameWorld:
    current_map: object = None
    dungeon_level: int = 1
    turn_count: int = 0

# Set up the registry
registry = tcod.ecs.Registry()

# Player entity
player = registry.new_entity(key="player")
player.components[Position] = Position(x=10, y=5)
player.components[Renderable] = Renderable(char="@", color=(255, 255, 0))
player.components[Health] = Health(current=30, maximum=30)
player.tags.add("player")
player.tags.add("alive")

# World entity
world = registry[None]
world.components[GameWorld] = GameWorld(
    current_map=generate_dungeon(width=80, height=45),
    dungeon_level=1,
    turn_count=0,
)
```

The state is no longer scattered across variables. It lives on entities inside the registry. Now any system can access what it needs:

```python
def render_player(console: tcod.console.Console, registry: tcod.ecs.Registry) -> None:
    """Render the player character."""
    player = registry["player"]
    pos = player.components[Position]
    rend = player.components[Renderable]
    console.print(x=pos.x, y=pos.y, string=rend.char, fg=rend.color)

def advance_turn(registry: tcod.ecs.Registry) -> None:
    """Increment the turn counter."""
    gw = registry[None].components[GameWorld]
    gw.turn_count += 1

def apply_damage(registry: tcod.ecs.Registry, target_key: str, damage: int) -> None:
    """Apply damage to an entity."""
    target = registry[target_key]
    hp = target.components[Health]
    hp.current -= damage
    if hp.current <= 0:
        target.tags.discard("alive")
        target.tags.add("dead")
```

Notice what changed: none of these functions take `player_x` or `game_map` as parameters. They take the registry and find what they need. This is the architectural shift. Systems do not depend on the shape of the data that was passed to them. They depend on the query they run.

**Side-by-side comparison**

| Chapter 4 | Chapter 5 |
|-----------|-----------|
| `player_x = 10` | `player.components[Position] = Position(x=10, y=5)` |
| `player_hp = 30` | `player.components[Health] = Health(current=30, maximum=30)` |
| `game_map = generate_dungeon(...)` | `world.components[GameWorld].current_map = generate_dungeon(...)` |
| `dungeon_level = 1` | `world.components[GameWorld].dungeon_level = 1` |
| `render(player_x, player_y, game_map)` | `render(registry)` |
| `combat(player_hp, enemy_power)` | `combat(registry)` |

The left column requires threading state through function calls. The right column requires only the registry.

## Building the Full Setup

Let us assemble everything into a complete setup function that replaces the Chapter 4 initialization. This function creates the registry, defines the game state, and returns the registry ready for use.

```python
import tcod.ecs
from attrs import define
from components.physical import Position, Renderable
from components.combat import Health
from components.world import GameWorld
from procgen import generate_dungeon

def create_game() -> tcod.ecs.Registry:
    """Initialize a new game and return the populated registry."""
    registry = tcod.ecs.Registry()

    # Create the player
    player = registry.new_entity(key="player")
    player.components[Position] = Position(x=0, y=0)  # Will be set by dungeon gen
    player.components[Renderable] = Renderable(char="@", color=(255, 255, 0))
    player.components[Health] = Health(current=30, maximum=30)
    player.tags.add("player")
    player.tags.add("alive")

    # Generate the first dungeon level
    game_map = generate_dungeon(width=80, height=45)

    # Place the player in the first room
    start_x, start_y = game_map.get_player_start()
    player.components[Position] = Position(x=start_x, y=start_y)

    # Set up global game state
    world = registry[None]
    world.components[GameWorld] = GameWorld(
        current_map=game_map,
        dungeon_level=1,
        turn_count=0,
    )
    world.tags.add("in_game")
    world.relation_tag["player"] = player

    return registry
```

The main function then becomes:

```python
import tcod
import tcod.console
import tcod.context
import tcod.tileset

def main() -> None:
    tileset = tcod.tileset.load_tilesheet(
        path="dejavu10x10_gs_tc.png",
        columns=32,
        rows=8,
        charmap=tcod.tileset.CHARMAP_TCOD,
    )

    registry = create_game()

    with tcod.context.new(
        columns=80,
        height=24,
        tileset=tileset,
        title="Roguelike",
    ) as context:
        console = tcod.console.Console(80, 24, order="F")

        while True:
            console.clear()
            world = registry[None]

            if "in_game" in world.tags:
                render_game(console, registry)
            elif "game_over" in world.tags:
                render_game_over(console)

            context.present(console)

            for event in tcod.event.wait():
                if isinstance(event, tcod.event.Quit):
                    return
                if isinstance(event, tcod.event.KeyDown):
                    handle_input(event, registry)
```

The main loop no longer owns any state. It delegates to the registry. This is a clean separation: the loop manages the window and event flow, while the registry holds all game data. When we add new screens, new entities, or new systems, the main loop does not change. Only the registry and the systems that operate on it grow.

## Exercises

**Exercise 1: Total Moves Counter**

Add a `MoveCounter` component to the world entity that tracks the total number of times the player has moved (not the same as turns, if you want to distinguish moving from waiting). Write a system function that increments this counter whenever the player changes position. Display the count in the HUD.

**Exercise 2: Settings Entity**

Create a "settings" entity with components for screen width, screen height, and whether tile-based rendering is enabled. Store this entity on the world entity using a relation:

```python
settings = registry.new_entity(key="settings")
settings.components[ScreenSize] = ScreenSize(width=80, height=45)
registry[None].relation_tag["settings"] = settings
```

Write a function that reads these settings and applies them to the tcod console and context.

**Exercise 3: Map Overview Toggle**

Implement a simple state toggle: when the player presses `M`, the game switches to a "map overview" state that renders the full dungeon map (ignoring field of view). Pressing `M` again returns to normal gameplay.

Hints:

- Use the tag approach for game states: add and remove tags like `"map_overview"` on the world entity.
- In the render function, check for this tag and render differently.
- The map overview can use a different set of colors (dim the explored tiles, brighten the full map).

**Exercise 4: Entity Counter**

Write a function `count_entities(registry)` that returns a dictionary mapping tag names to the number of entities that have each tag. For example, `{"alive": 5, "hostile": 3, "item": 12}`. Call this function periodically and print the result. This is a debugging tool that will be invaluable as your game grows.

**Exercise 5: Refactor the Chapter 4 Game**

If you have not already done so as you read through this chapter, take the complete Chapter 4 game and refactor it to use the ECS registry. Replace every global or instance variable with a component on an entity. Replace every function that takes state as a parameter with a system that takes the registry. Verify that the game still works identically after the refactor.

This is the most important exercise in the chapter. The act of refactoring forces you to confront every design decision and understand why the ECS pattern works the way it does.

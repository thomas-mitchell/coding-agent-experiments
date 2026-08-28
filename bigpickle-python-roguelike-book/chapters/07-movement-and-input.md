# Chapter 7: Movement and Input

The player presses the right arrow key. The `@` character moves one tile to the right. That simple interaction is the entire point of the game. Everything else---procedural generation, combat, inventory, field of view---depends on movement working correctly.

This chapter builds the action system: a pattern that converts raw keyboard input into game actions, processes them through a pipeline of systems, and updates the game state. By the end, the player moves through a dungeon, bumps into walls and enemies, and the camera follows along.

## The Action Pattern

The most common mistake in roguelike input handling is putting movement logic directly in the event loop:

```python
# The naive approach---avoid this
for event in tcod.event.wait():
    if isinstance(event, tcod.event.KeyDown):
        if event.sym == tcod.event.KeySym.LEFT:
            player_pos.x -= 1
        elif event.sym == tcod.event.KeySym.RIGHT:
            player_pos.x += 1
```

This works for a prototype. It fails for a real game. The event loop becomes a dumping ground for movement, item use, inventory management, and menu navigation. Testing is impossible because you cannot call the movement logic without synthesizing a keyboard event. And if AI needs the same movement logic, you are stuck duplicating code.

The action pattern solves this by separating *what the player wants to do* from *how the game does it*. Instead of handling input directly, we convert each input event into an **Action** object---a plain data structure that describes an intent. A `BumpAction` says "this entity wants to move in direction (dx, dy)." A `WaitAction` says "this entity wants to skip its turn." The event loop creates actions. A separate system processes them.

The key insight is that actions are data, not side effects. A `BumpAction` does not move anything. It is a request. The movement system reads the request, checks whether it is valid, and then either moves the entity or rejects the action. This separation gives us several benefits:

**Replay systems.** Because actions are data, you can record them. Save a list of actions to a file, replay them later, and get the same game state. This is invaluable for debugging---reproduce a crash by replaying the inputs that caused it.

**Shared AI and player actions.** The AI system creates the same `BumpAction` that the player creates. The movement system does not care whether the action came from a keyboard event or from an AI decision. This eliminates duplicated movement logic.

**Testability.** You can test movement by creating a `BumpAction` and running it through the movement system. No keyboard event needed. No window needed. No game loop needed. Just a registry, an entity, and an action.

**Undo systems.** Record actions forward, reverse them to go backward. Each action carries enough information to compute its inverse.

## Defining Actions

Actions are simple data classes. We use attrs to define them, consistent with how we define components.

```python
# src/actions.py

from __future__ import annotations

from typing import TYPE_CHECKING

import attrs

if TYPE_CHECKING:
    from tcod.ecs import Entity


@attrs.define
class Action:
    """Base class for all game actions."""

    entity: Entity


@attrs.define
class BumpAction(Action):
    """Request to move an entity by (dx, dy)."""

    dx: int = 0
    dy: int = 0


@attrs.define
class WaitAction(Action):
    """Request to skip a turn."""
    pass


@attrs.define
class PickupAction(Action):
    """Request to pick up an item at the entity's position."""
    pass


@attrs.define
class DropAction(Action):
    """Request to drop an item from the entity's inventory."""

    item: Entity | None = None
```

Every action inherits from `Action`, which holds a reference to the entity performing it. This is the one piece of shared state all actions need: who is acting. The subclass adds whatever data the specific action requires.

`BumpAction` carries `dx` and `dy`---the direction of attempted movement. These are tile offsets, not absolute positions. A `BumpAction(dx=1, dy=0)` means "move one tile to the right." The movement system computes the actual destination by adding these offsets to the entity's current position.

`WaitAction` carries no additional data. The entity does nothing for one turn. `PickupAction` likewise carries no data; the system looks for items at the entity's position. `DropAction` carries a reference to the item being dropped, defaulting to the most recently picked up item if unspecified.

Notice that the `TYPE_CHECKING` guard protects the `Entity` import. This avoids a circular import between `actions.py` and the tcod-ecs module at runtime, while still providing type information to static analysis tools.

## Input Handling

tcod delivers input as events. The `tcod.event.KeyDown` event fires when a key is pressed. The `event.sym` attribute identifies which key was pressed, using `tcod.event.KeySym` constants.

The input handler receives a `KeyDown` event and returns an `Action` (or `None` if the key does not correspond to an action):

```python
# src/input.py

from __future__ import annotations

from typing import TYPE_CHECKING

import tcod.event

from src.actions import BumpAction, DropAction, PickupAction, WaitAction

if TYPE_CHECKING:
    from tcod.ecs import Entity


def handle_input(
    event: tcod.event.KeyDown,
    player: Entity,
) -> Action | None:
    """Convert a keyboard event into a game action."""
    match event.sym:
        # Arrow keys
        case tcod.event.KeySym.UP:
            return BumpAction(entity=player, dx=0, dy=-1)
        case tcod.event.KeySym.DOWN:
            return BumpAction(entity=player, dx=0, dy=1)
        case tcod.event.KeySym.LEFT:
            return BumpAction(entity=player, dx=-1, dy=0)
        case tcod.event.KeySym.RIGHT:
            return BumpAction(entity=player, dx=1, dy=0)

        # Vi keys
        case tcod.event.KeySym.h:
            return BumpAction(entity=player, dx=-1, dy=0)
        case tcod.event.KeySym.j:
            return BumpAction(entity=player, dx=0, dy=1)
        case tcod.event.KeySym.k:
            return BumpAction(entity=player, dx=0, dy=-1)
        case tcod.event.KeySym.l:
            return BumpAction(entity=player, dx=1, dy=0)

        # Vi diagonals
        case tcod.event.KeySym.y:
            return BumpAction(entity=player, dx=-1, dy=-1)
        case tcod.event.KeySym.u:
            return BumpAction(entity=player, dx=1, dy=-1)
        case tcod.event.KeySym.b:
            return BumpAction(entity=player, dx=-1, dy=1)
        case tcod.event.KeySym.n:
            return BumpAction(entity=player, dx=1, dy=1)

        # Numpad (with numlock on)
        case tcod.event.KeySym.KP_8:
            return BumpAction(entity=player, dx=0, dy=-1)
        case tcod.event.KeySym.KP_2:
            return BumpAction(entity=player, dx=0, dy=1)
        case tcod.event.KeySym.KP_4:
            return BumpAction(entity=player, dx=-1, dy=0)
        case tcod.event.KeySym.KP_6:
            return BumpAction(entity=player, dx=1, dy=0)
        case tcod.event.KeySym.KP_7:
            return BumpAction(entity=player, dx=-1, dy=-1)
        case tcod.event.KeySym.KP_9:
            return BumpAction(entity=player, dx=1, dy=-1)
        case tcod.event.KeySym.KP_1:
            return BumpAction(entity=player, dx=-1, dy=1)
        case tcod.event.KeySym.KP_3:
            return BumpAction(entity=player, dx=1, dy=1)

        # Wait and actions
        case tcod.event.KeySym.PERIOD | tcod.event.KeySym.KP_5:
            return WaitAction(entity=player)
        case tcod.event.KeySym.g:
            return PickupAction(entity=player)
        case tcod.event.KeySym.d:
            return DropAction(entity=player)

        case _:
            return None
```

The `match` statement is clean and readable. Arrow keys handle cardinal movement. The vi keys (`hjkl` and diagonals `yubn`) handle all eight directions. Numpad handles all eight directions with the number pad. Period and numpad 5 handle waiting. `g` picks up items. `d` drops them.

This function has no side effects. It does not modify the game state. It reads the player entity reference (needed to attach to the action) and returns a data object. This purity is what makes it testable and composable.

Multiple key bindings can be collapsed into a single case using `|`:

```python
case tcod.event.KeySym.UP | tcod.event.KeySym.KP_8 | tcod.event.KeySym.k:
    return BumpAction(entity=player, dx=0, dy=-1)
```

Arrow keys, numpad keys, and vi keys all map to the same `BumpAction`. The player can use whichever scheme they prefer.

## Vi Key Movement

The vi key layout comes from the vi text editor and has been the traditional roguelike control scheme since the genre began:

```
y k l        NW  N  NE
 \|/
h . u    =>  W  .  E
 /|\        SW  S  SE
b j n
```

The keys form a spatial map on the keyboard. `h` is left (west), `j` is down (south), `k` is up (north), `l` is right (east). The diagonal keys fill in the corners: `y` is northwest, `u` is northeast, `b` is southwest, `n` is southeast. The period key sits in the center, meaning "stand still."

Many experienced roguelike players prefer vi keys because the hands never leave the home row. Movement becomes muscle memory. If you are building a traditional roguelike, supporting vi keys is not optional---it is expected.

The numpad layout mirrors the spatial arrangement:

```
KP7  KP8  KP9
  \  |  /
KP4  KP5  KP6
  /  |  \
KP1  KP2  KP3
```

Numpad 5 (or period with numlock off) is wait.

## The Movement System

The movement system is where actions become state changes. It processes `BumpAction` instances, checks whether movement is valid, and updates positions.

```python
# src/systems/movement.py

from __future__ import annotations

from typing import TYPE_CHECKING

import tcod.ecs

from src.actions import BumpAction
from src.components.physical import Position
from src.components.world import GameMap

if TYPE_CHECKING:
    pass


def movement_system(registry: tcod.ecs.Registry) -> None:
    """Process all pending BumpActions in the registry."""
    world = registry[None]
    game_map = world.components.get(GameMap)

    for entity, (pos, action) in registry.Q[Position, BumpAction].results:
        dest_x = pos.x + action.dx
        dest_y = pos.y + action.dy

        if not is_walkable(game_map, dest_x, dest_y):
            continue

        if entity_has_blocking_entity(registry, dest_x, dest_y):
            continue

        pos.x = dest_x
        pos.y = dest_y

        del entity.components[BumpAction]
```

The ECS query automatically joins these two component types, returning pairs of (entity, (position, action)). The system does not need to know which entities have pending actions---the query delivers exactly the entities that need processing.

For each entity, the system computes the destination tile by adding `dx` and `dy` to the current position. It checks whether the destination is walkable and whether a blocking entity is there. If either check fails, the action is consumed without moving---the entity spent its turn. If both checks pass, the position is updated and the action is removed.

### Walkability Check

The walkability check verifies that a tile is passable. This depends on the game map, which we will build fully in Chapter 8:

```python
def is_walkable(game_map: GameMap, x: int, y: int) -> bool:
    """Check if the tile at (x, y) is passable."""
    if game_map is None:
        return False
    if x < 0 or x >= game_map.width or y < 0 or y >= game_map.height:
        return False
    return not game_map.tiles[y, x].blocks_movement
```

Bounds are checked first---moving off the edge of the map is not allowed. Then the tile itself is checked. Walls block. Floors do not.

### Entity Collision Detection

The second check determines whether another entity occupies the target tile:

```python
def entity_has_blocking_entity(
    registry: tcod.ecs.Registry,
    x: int,
    y: int,
) -> bool:
    """Check if any entity at (x, y) has the blocks_movement tag."""
    for entity, (pos,) in registry.Q[Position].results:
        if pos.x == x and pos.y == y:
            if "blocks_movement" in entity.tags:
                return True
    return False
```

The `blocks_movement` tag is important: items on the ground have a `Position` but not the tag, so the player can walk over them. Enemies have `blocks_movement`, so the player cannot walk through them.

## Action Processing Pipeline

The full cycle from input to state change follows a pipeline:

```
Input Event  ->  Action Creation  ->  Action Dispatch  ->  System Processing  ->  State Update  ->  Render
```

The `process_action` function is a thin dispatcher that attaches the action to the acting entity as a component:

```python
def process_action(registry: tcod.ecs.Registry, action: Action) -> None:
    """Execute an action by attaching it to the acting entity."""
    action.entity.components[type(action)] = action
```

This is the crucial detail. Processing an action means *attaching it to the entity as a component*. The action does not execute immediately. It sits on the entity as a pending request, waiting for the appropriate system to process it. The `movement_system` queries for entities with `BumpAction` components. The pickup system (Chapter 15) will query for entities with `PickupAction` components. Each system processes only the actions it cares about.

Why not execute the action immediately? Because separating dispatch from execution keeps the pipeline flexible. You can add pre-processing (action validation, resource costs), post-processing (animation triggers, sound effects), or action queuing without changing the dispatch logic.

Systems run in a defined order:

```python
def run_systems(registry: tcod.ecs.Registry) -> None:
    """Run all game systems in order."""
    movement_system(registry)
    # pickup_system(registry)       # Chapter 15
    # combat_system(registry)       # Chapter 13
    # ai_system(registry)           # Chapter 14
```

After all systems run, the pending actions are cleared:

```python
def clear_actions(registry: tcod.ecs.Registry) -> None:
    """Remove all pending actions from every entity."""
    action_types = (BumpAction, WaitAction, PickupAction, DropAction)
    for entity in registry.Q[:].results:
        for action_type in action_types:
            entity.components.pop(action_type, None)
```

This prevents stale actions from being processed in future turns.

## The Main Loop

Here is how the main loop ties these stages together:

```python
def main_loop(
    registry: tcod.ecs.Registry,
    context: tcod.context.Context,
    console: tcod.console.Console,
) -> None:
    """The main game loop."""
    player = registry["player"]

    while True:
        console.clear()
        render_game(console, registry)
        context.present(console)

        for event in tcod.event.wait():
            if isinstance(event, tcod.event.Quit):
                return

            if isinstance(event, tcod.event.KeyDown):
                action = handle_input(event, player)

                if action is not None:
                    process_action(registry, action)
                    run_systems(registry)
                    clear_actions(registry)
```

The loop is clean and linear. Input creates an action. The action is attached to the entity. Systems process all pending actions. Actions are cleared. The state is rendered.

## Camera Follow

A game map is typically larger than the screen. The console might be 80 by 50 tiles, but the dungeon could be 100 by 100. The camera system determines which portion of the map is visible. For a roguelike, the simplest approach is to keep the player roughly centered.

```python
# src/systems/camera.py

from __future__ import annotations

from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from src.components.physical import Position


def calculate_camera_offset(
    player_pos: Position,
    screen_width: int,
    screen_height: int,
    map_width: int,
    map_height: int,
) -> tuple[int, int]:
    """Calculate the camera offset to center the player on screen.

    Returns (camera_x, camera_y) -- the top-left corner of the visible
    area in world coordinates.
    """
    camera_x = player_pos.x - screen_width // 2
    camera_y = player_pos.y - screen_height // 2

    # Clamp to map bounds
    camera_x = max(0, min(camera_x, map_width - screen_width))
    camera_y = max(0, min(camera_y, map_height - screen_height))

    return camera_x, camera_y
```

Center the player by subtracting half the screen dimensions from the player position. Clamp to the map boundaries so the camera does not show empty space beyond the edges.

When rendering entities, subtract the camera offset from their world positions:

```python
def render_entities(
    console: tcod.console.Console,
    registry: tcod.ecs.Registry,
    camera_x: int,
    camera_y: int,
) -> None:
    """Render all visible entities, adjusted for camera offset."""
    for entity, (pos, rend) in registry.Q[Position, Renderable].results:
        screen_x = pos.x - camera_x
        screen_y = pos.y - camera_y

        if screen_x < 0 or screen_x >= console.width:
            continue
        if screen_y < 0 or screen_y >= console.height:
            continue

        console.print(x=screen_x, y=screen_y, string=rend.char, fg=rend.fg)
```

An entity at world position `(50, 30)` with a camera at `(10, 5)` appears at screen position `(40, 25)`. Entities outside the visible area are skipped. The same offset applies to tile rendering.

## Entity Collision with Combat Preview

When the player bumps into an entity that blocks movement, the movement system currently does nothing. In a real game, bumping into an enemy triggers an attack. We will implement combat fully in Chapter 13, but here is the pattern:

```python
def movement_system(registry: tcod.ecs.Registry) -> None:
    """Process all pending BumpActions with combat support."""
    world = registry[None]
    game_map = world.components.get(GameMap)

    for entity, (pos, action) in registry.Q[Position, BumpAction].results:
        dest_x = pos.x + action.dx
        dest_y = pos.y + action.dy

        if not is_walkable(game_map, dest_x, dest_y):
            del entity.components[BumpAction]
            continue

        target = get_entity_at(registry, dest_x, dest_y)
        if target is not None and "blocks_movement" in target.tags:
            if "enemy" in target.tags:
                attack(registry, entity, target)
            del entity.components[BumpAction]
            continue

        pos.x = dest_x
        pos.y = dest_y
        del entity.components[BumpAction]
```

Movement now has three outcomes. The tile is unwalkable: do nothing. The tile has a blocking entity: attack. The tile is open: move. Each outcome consumes the action.

The supporting functions:

```python
def get_entity_at(
    registry: tcod.ecs.Registry,
    x: int,
    y: int,
) -> tcod.ecs.Entity | None:
    """Return the first blocking entity at (x, y), or None."""
    for entity, (pos,) in registry.Q[Position].results:
        if pos.x == x and pos.y == y:
            if "blocks_movement" in entity.tags:
                return entity
    return None


def attack(
    registry: tcod.ecs.Registry,
    attacker: tcod.ecs.Entity,
    defender: tcod.ecs.Entity,
) -> None:
    """Handle an attack. Stub for Chapter 13."""
    from src.components.combat import Fighter
    from src.components.identity import Name

    attacker_fighter = attacker.components[Fighter]
    defender_fighter = defender.components[Fighter]
    defender_name = defender.components[Name].name

    damage = max(1, attacker_fighter.power - defender_fighter.defense)
    defender_fighter.hp -= damage

    print(f"You attack the {defender_name} for {damage} damage.")

    if defender_fighter.hp <= 0:
        print(f"The {defender_name} is dead!")
        defender.tags.discard("blocks_movement")
        defender.tags.add("dead")
```

The `attack` function is a stub using the formula from Chapter 6. Chapter 13 will replace it with critical hits, status effects, and death processing.

## Handling the Wait Action

The wait action consumes the player's turn without changing position. This advances the game clock so enemies take their turns.

```python
def wait_system(registry: tcod.ecs.Registry) -> None:
    """Process all pending WaitActions."""
    for entity, (action,) in registry.Q[WaitAction].results:
        del entity.components[WaitAction]
```

The system does nothing to the entity---it simply removes the action. The important side effect is that `run_systems` triggers AI turns afterward, so enemies move even though the player stood still.

Without the wait action, the player has no way to skip a turn. Sometimes the best move is to let the enemy come to you, or to let a status effect expire.

## Input Handler as a Class

As the game grows, the input handler accumulates state. Menu navigation needs a cursor position. Targeting mode needs a selected tile. The handler benefits from becoming a class:

```python
class InputHandler:
    """Converts keyboard events into game actions."""

    def __init__(self, player: Entity) -> None:
        self.player = player
        self.mode: str = "play"

    def handle(self, event: tcod.event.KeyDown) -> Action | None:
        match self.mode:
            case "play":
                return self._handle_play(event)
            case "inventory":
                return self._handle_inventory(event)
            case _:
                return None

    def _handle_play(self, event: tcod.event.KeyDown) -> Action | None:
        # Same match statement as handle_input, using self.player
        match event.sym:
            case tcod.event.KeySym.UP | tcod.event.KeySym.KP_8 | tcod.event.KeySym.k:
                return BumpAction(entity=self.player, dx=0, dy=-1)
            # ... all other key bindings ...
            case _:
                return None

    def _handle_inventory(self, event: tcod.event.KeyDown) -> Action | None:
        match event.sym:
            case tcod.event.KeySym.ESCAPE:
                self.mode = "play"
            case _:
                pass
        return None
```

Each input mode gets its own handler method. The `mode` attribute controls which handler runs. Switching modes is as simple as setting `self.mode = "inventory"`. The inventory handler is a stub, but it shows the pattern: each mode has its own key bindings and its own way to return to play mode.

## Summary

This chapter established the action pattern for input handling:

- **Actions are data structures** describing player intent. `BumpAction`, `WaitAction`, `PickupAction`, and `DropAction` capture the basic actions a player can take.

- **The input handler converts events to actions.** It maps keyboard inputs to action objects using a clean match statement. No side effects, no state mutation.

- **Actions are attached to entities as components.** The `process_action` function places the action on the acting entity, where systems can query for it.

- **Systems process actions in order.** The movement system handles `BumpAction`. The pickup system will handle `PickupAction`. Each system queries for its action type and processes only relevant entities.

- **The camera follows the player.** A simple offset calculation keeps the player centered on screen, clamped to map bounds.

- **Entity collision triggers combat.** When movement is blocked, the bump becomes an attack (preview of Chapter 13).

## Exercises

**Exercise 1: Diagonal Movement with Numpad**

Verify that all eight numpad directions work correctly. Create a test that creates a player entity at position (10, 10), attaches a `BumpAction(dx=1, dy=1)`, runs the movement system, and asserts the player ends up at the correct position. What happens if the diagonal destination is blocked?

**Exercise 2: Auto-Explore**

Implement an auto-explore feature. When the player presses `X`, the game automatically moves the player toward the nearest unexplored tile, one step per turn. You need a BFS pathfinding function, a component or tag marking the auto-explore intent, and a system that computes the next step each turn and creates a `BumpAction` in the right direction. Auto-explore should stop when an enemy comes into view, when the player reaches the unexplored tile, or when no path exists.

**Exercise 3: Movement History for Replay**

Record every action the player takes during a session in a list (`action_history: list[Action] = []`). Each time the input handler returns an action, append it. Then implement a `replay` function that takes the registry and the action list, creates each action in sequence, and processes it through the systems. Replay should produce the same final game state as playing manually.

**Exercise 4: Shift for Alternate Actions**

Add support for modifier keys. When the player holds Shift and presses a movement key, the action should differ---for example, Shift+Arrow could run (move two tiles in one turn if the intervening tile is clear), or Shift+g could search for traps. The `tcod.event.KeyDown` event has a `mod` attribute (a bitmask of active modifiers). Use `event.mod & tcod.event.KMOD_SHIFT` to test for Shift.

**Exercise 5: Key Remapping**

Store the key-to-action mapping in a dictionary instead of hardcoding it in the match statement. The dictionary maps `tcod.event.KeySym` values to action factory functions:

```python
KEY_MAP: dict[tcod.event.KeySym, Callable] = {
    tcod.event.KeySym.UP: lambda p: BumpAction(entity=p, dx=0, dy=-1),
    tcod.event.KeySym.DOWN: lambda p: BumpAction(entity=p, dx=0, dy=1),
    # ...
}
```

Build a simple remapping screen that lets the player rebind keys at runtime.

# Chapter 12: The Turn-Based Game Loop

The game loop from Chapter 7 runs when the player presses a key: the input is converted to an action, the action is processed, the screen is redrawn. Enemies stand still. The world does not respond. This is a demo, not a game.

A real roguelike needs a heartbeat. The player acts, then every enemy acts, then the world updates---effects tick, statuses expire, the map refreshes. This cycle repeats dozens of times per minute, each iteration a discrete unit of time called a **turn**. The turn-based game loop is the engine that drives every interaction in the game. Without it, combat is meaningless, AI is pointless, and the dungeon is a static painting.

This chapter builds the complete turn cycle: player input, enemy AI processing, effect resolution, death handling, and game-over detection. By the end, the dungeon is alive---enemies patrol corridors, attacks deal damage, and the game ends when the player dies.

## Turn-Based vs Real-Time

Roguelikes are turn-based. This is not a stylistic preference; it is a defining characteristic of the genre. When the player presses a key to move left, the game does not immediately advance. It waits. The player's action is a command: "move left." Only after the player issues this command does the game execute it---and then every other entity in the dungeon gets to act as well.

This creates a rhythm that real-time games lack. In a real-time game, the player reacts to stimuli as they happen. The game runs at a fixed frame rate, and the player must keep up. In a turn-based game, the player has unlimited time to think. There is no clock ticking down. No enemies rushing toward you between keystrokes. The only pressure is your own indecision.

This simplicity is the foundation of roguelike tactics. Because the game waits for you, you can plan. You can count tiles, evaluate escape routes, weigh risk against reward. The tactical depth of a roguelike comes from this pause---the ability to consider every action before committing.

Each turn follows a strict order:

1. The player chooses an action (input).
2. The player's action is executed.
3. Every enemy in the dungeon takes its turn.
4. World effects resolve (poison ticks, fire spreads, statuses expire).
5. The turn counter advances.
6. The game state is rendered.

Steps 3 and 4 are automatic. The player never sees them happen in real time---they execute instantly between the player's action and the next render. But they are real. An enemy that moves toward you during step 3 is a threat. A poison effect that deals damage during step 4 is dangerous. The turn cycle is the invisible engine that makes these interactions possible.

## The Turn Order

Turn order determines who acts when. In a traditional roguelike, the order is simple and fixed:

**Player first.** The player always acts before anything else. This is a design choice, not a technical limitation. It ensures the player never loses a turn to an enemy acting before them. It also gives the player a feeling of control---you are the protagonist, and the world reacts to you.

**Enemies second.** After the player's action resolves, every enemy takes its turn. The order among enemies does not matter for most games---all enemies move before the world effects tick. Some games sort enemies by distance to the player, so nearby threats act first. For now, we process all enemies in the order the registry returns them.

**Effects third.** Status effects, environmental hazards, and time-based mechanics resolve after all entities have acted. This ensures that an enemy does not die to poison before it gets to attack. Effects are applied, damage is dealt, and durations are decremented.

**World state update last.** FOV is recomputed, the message log is flushed, and the screen is redrawn. This is the transition between turns---the moment where the game state becomes visible to the player again.

This order is not arbitrary. It prevents subtle bugs. If enemies acted before the player, an enemy could kill the player before the player's action resolved. If effects ticked before enemies, a poison effect could kill an enemy before it had a chance to flee. The order ensures that each phase of the turn has a clear, predictable relationship to the others.

## Energy-Based Turns

Before we build the simple turn system, it is worth understanding the more complex alternative: energy-based turns.

In an energy-based system, every entity has an energy counter. Each turn, every entity gains energy---the amount determined by its speed stat. When an entity accumulates enough energy, it can act. Different actions cost different amounts of energy: moving costs 100 energy, attacking costs 100, waiting costs 50. An entity with speed 150 gains 150 energy per turn, so it can act more often than an entity with speed 100.

This creates natural variation in entity speed without special-casing. A fast enemy acts twice for every action a slow enemy takes. A player with a haste buff moves more frequently. A slowed enemy falls behind.

Energy-based turns are powerful but complex. They require tracking energy per entity, defining energy costs per action, and handling the case where an entity has enough energy for multiple actions in a single turn. For a first roguelike, this complexity is premature. We will use a simpler system: a flat turn counter where every entity acts exactly once per turn.

The energy system is covered in the exercises at the end of this chapter. If you want speed variation, that is where to start.

## The Simple Turn Counter

Our turn system uses a single integer counter on the world entity. Every time the player acts and enemies respond, the counter increments. This gives us a reliable measure of elapsed time and provides a foundation for time-based mechanics later.

```python
# src/components/world.py

from __future__ import annotations

import attrs


@attrs.define
class TurnCounter:
    """Tracks the current turn number."""
    count: int = 0
```

Attach it to the world entity:

```python
world = registry[None]
world.components[TurnCounter] = TurnCounter(count=0)
```

After each complete turn cycle (player acts, enemies act, effects resolve), increment the counter:

```python
def advance_turn(registry: tcod.ecs.Registry) -> None:
    """Advance the turn counter by one."""
    world = registry[None]
    counter = world.components[TurnCounter]
    counter.count += 1
```

This is the simplest possible turn tracking. The counter is just an integer. But it becomes the backbone for everything that depends on time: status effect durations, cooldowns, scoring, and performance tracking.

## Processing Enemy Turns

The enemy turn system is where the dungeon comes alive. After the player acts, every entity with an `AI` component and an `"enemy"` tag gets to act. The system iterates over all enemy entities, queries their AI behavior, and executes the appropriate action.

Here is the core system:

```python
# src/systems/enemy_turns.py

from __future__ import annotations

from typing import TYPE_CHECKING

import tcod.ecs

from components import AI, AIKind, Fighter, Name, Position

if TYPE_CHECKING:
    pass


def process_enemy_turns(
    registry: tcod.ecs.Registry,
    game_map: GameMap,
    player: tcod.ecs.Entity,
) -> None:
    """Process turns for all enemy entities."""
    player_pos = player.components[Position]

    for entity in registry.Q.all_of(tags=["enemy"]):
        ai = entity.components.get(AI)
        if ai is None:
            continue

        # Skip dead entities
        if "dead" in entity.tags:
            continue

        fighter = entity.components.get(Fighter)
        if fighter is not None and fighter.hp <= 0:
            continue

        pos = entity.components[Position]

        if ai.kind == AIKind.HOSTILE:
            _process_hostile_ai(entity, pos, player_pos, game_map, registry)
        elif ai.kind == AIKind.CONFUSED:
            _process_confused_ai(entity, pos, game_map)
        elif ai.kind == AIKind.FLEEING:
            _process_fleeing_ai(entity, pos, player_pos, game_map)
```

The function receives the registry, the current game map, and a reference to the player entity. It loops over every entity tagged `"enemy"`, reads its AI component, and dispatches to the appropriate behavior function based on the `AIKind` enum.

The dead-entity check is critical. Without it, the system would try to process actions for entities that have already been killed. We check both the `"dead"` tag and the `Fighter.hp` field to be safe---the tag is the primary mechanism, but the hp check catches edge cases where a system marks an entity as dead without adding the tag.

### Hostile AI

The hostile behavior is the most common enemy pattern. When an enemy can see the player (the player's tile is in the enemy's field of view), it moves one tile closer. If it is already adjacent to the player, it attacks.

```python
def _process_hostile_ai(
    entity: tcod.ecs.Entity,
    pos: Position,
    player_pos: Position,
    game_map: GameMap,
    registry: tcod.ecs.Registry,
) -> None:
    """Basic hostile AI: chase the player and attack when adjacent."""
    # Only act if the enemy can see the player
    if not game_map.visible[pos.y, pos.x]:
        return

    dx = player_pos.x - pos.x
    dy = player_pos.y - pos.y

    distance = abs(dx) + abs(dy)

    if distance <= 1:
        # Adjacent to player -- attack
        attack(entity, player, registry)
        return

    # Move one step toward the player
    dx = max(-1, min(1, dx))
    dy = max(-1, min(1, dy))

    target_x = pos.x + dx
    target_y = pos.y + dy

    if game_map.is_walkable(target_x, target_y):
        # Check that no other entity is blocking the destination
        blocked = False
        for other in registry.Q.all_of(tags=["blocks_movement"]):
            other_pos = other.components[Position]
            if other_pos.x == target_x and other_pos.y == target_y:
                blocked = True
                break

        if not blocked:
            pos.x = target_x
            pos.y = target_y
```

The behavior is simple but effective. The enemy only acts when it can see the player---if the player is outside its field of view, it does nothing. This prevents enemies from "cheating" by moving toward the player through walls.

The distance check uses Manhattan distance (`abs(dx) + abs(dy)`). A distance of 1 means the enemy is adjacent---left, right, up, or down. At this distance, the enemy attacks instead of moving.

Movement is constrained to one tile per turn. The `dx` and `dy` values are clamped to the range `[-1, 1]` using `max(-1, min(1, dx))`. This prevents diagonal movement for now---enemies move in cardinal directions only. Diagonal movement can be enabled by removing the clamp, but it changes the feel of combat significantly.

The walkability check and entity collision check mirror the player's movement system. An enemy cannot walk through walls or through other entities. If the destination is blocked, the enemy wastes its turn standing still.

### Confused AI

Confused enemies move randomly. They do not target the player and do not avoid obstacles intelligently. This behavior is useful for status effects---applying confusion to a hostile enemy turns it into a unpredictable hazard.

```python
import random


def _process_confused_ai(
    entity: tcod.ecs.Entity,
    pos: Position,
    game_map: GameMap,
) -> None:
    """Confused AI: move in a random direction."""
    dx = random.choice([-1, 0, 1])
    dy = random.choice([-1, 0, 1])

    if dx == 0 and dy == 0:
        return  # Stay still

    target_x = pos.x + dx
    target_y = pos.y + dy

    if game_map.is_walkable(target_x, target_y):
        pos.x = target_x
        pos.y = target_y
```

A confused entity picks a random direction each turn. If the destination is unwalkable, it stays still. There is no pathfinding, no intelligence, just randomness. This makes confusion a meaningful debuff---the enemy becomes harmless to itself and dangerous to anyone nearby, including other enemies.

### Fleeing AI

Fleeing enemies move away from the player. They are triggered when an enemy's health drops below a threshold, creating a self-preservation instinct.

```python
def _process_fleeing_ai(
    entity: tcod.ecs.Entity,
    pos: Position,
    player_pos: Position,
    game_map: GameMap,
) -> None:
    """Fleeing AI: move away from the player."""
    dx = pos.x - player_pos.x
    dy = pos.y - player_pos.y

    # Move in the opposite direction of the player
    dx = max(-1, min(1, dx))
    dy = max(-1, min(1, dy))

    target_x = pos.x + dx
    target_y = pos.y + dy

    if game_map.is_walkable(target_x, target_y):
        pos.x = target_x
        pos.y = target_y
```

The fleeing AI is the mirror of hostile AI. Instead of moving toward the player, it moves away. The direction is computed by subtracting the player position from the enemy position (the reverse of the hostile formula). If the enemy is cornered---all adjacent tiles are walls or other entities---it stays still and waits to die.

### Integrating Enemy Turns into the Game Loop

The enemy turn system plugs into the game loop after the player's action resolves. Here is the updated loop structure:

```python
def main() -> None:
    registry = tcod.ecs.Registry()
    dungeon = generate_dungeon(...)
    player = create_player(registry, ...)

    world = registry[None]
    world.components[TurnCounter] = TurnCounter(count=0)

    console = tcod.console.Console(SCREEN_WIDTH, SCREEN_HEIGHT, order="C")

    with tcod.context.new(
        console=console,
        tileset=TILESET,
        title="Roguelike",
    ) as context:
        needs_render = True

        while True:
            if needs_render:
                render_all(console, dungeon, registry, player)
                context.present(console)
                needs_render = False

            for event in tcod.event.wait():
                if isinstance(event, tcod.event.Quit):
                    raise SystemExit()
                if isinstance(event, tcod.event.KeyDown):
                    if event.sym == tcod.event.KeySym.ESCAPE:
                        raise SystemExit()

                    action = handle_input(event, player)
                    if action is not None:
                        turn_consumed = process_action(action, registry, dungeon)

                        if turn_consumed:
                            # Enemy turns
                            process_enemy_turns(registry, dungeon, player)

                            # Advance the turn counter
                            advance_turn(registry)

                            # Update game state
                            update_fov(dungeon, player)
                            check_dead_entities(registry)

                            # Check for game over
                            if check_game_over(registry, player):
                                return

                        needs_render = True
```

The flow is linear and predictable. The player acts. If the action consumed a turn, enemies act. The turn counter advances. FOV is updated. Dead entities are cleaned up. The game checks for a game-over condition. Then the screen is redrawn.

The `turn_consumed` flag is the gatekeeper. Not every action advances the turn. Opening inventory, looking at a tooltip, or pressing an unbound key should not cause enemies to move. Only actions that represent a meaningful commitment---moving, waiting, attacking---consume a turn.

## Action Consumption

Some actions consume a turn; others do not. This distinction is fundamental to the turn-based loop.

**Turn-consuming actions:** Moving (`BumpAction`), waiting (`WaitAction`), attacking (a `BumpAction` that hits an enemy), picking up an item (`PickupAction`). These represent meaningful commitments. The player chose to do something, and the world should respond.

**Non-turn-consuming actions:** Opening the inventory, looking at the map, examining an item, navigating a menu. These are information-gathering actions. The player is thinking, not acting. Enemies should not move while the player reads their inventory.

The `process_action` function returns a boolean indicating whether the action consumed a turn:

```python
def process_action(
    action: Action,
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

        if not dungeon.is_walkable(target_x, target_y):
            return False

        # Check for entity collision
        target = get_entity_at(registry, target_x, target_y)
        if target is not None:
            if "enemy" in target.tags:
                attack(action.entity, target, registry)
                return True  # Attack consumes a turn
            return False  # Bumped into non-attackable entity

        # Move
        pos.x = target_x
        pos.y = target_y
        return True

    if isinstance(action, PickupAction):
        return True  # Pickup always consumes a turn

    return False  # Unknown actions do not consume a turn
```

The function returns `True` for moves, waits, and attacks. It returns `False` for wall collisions and unknown actions. This boolean is what controls whether the enemy turn system runs.

## The Attack Function

Attacks are the primary interaction between the player and enemies. When the player bumps into an enemy (or vice versa), an attack occurs. The attack function applies damage based on the attacker's power and the defender's defense.

```python
# src/systems/combat.py

from __future__ import annotations

from typing import TYPE_CHECKING

import tcod.ecs

from components import Fighter, Name, Position

if TYPE_CHECKING:
    pass


def attack(
    attacker: tcod.ecs.Entity,
    defender: tcod.ecs.Entity,
    registry: tcod.ecs.Registry,
) -> None:
    """Execute an attack from attacker against defender."""
    attacker_fighter = attacker.components[Fighter]
    defender_fighter = defender.components[Fighter]

    damage = max(1, attacker_fighter.power - defender_fighter.defense)

    defender_fighter.hp -= damage

    # Build the attack message
    attacker_name = attacker.components[Name].name
    defender_name = defender.components[Name].name

    if "player" in attacker.tags:
        message = f"You attack the {defender_name} for {damage} hit points."
    elif "player" in defender.tags:
        message = f"The {attacker_name} attacks you for {damage} hit points."
    else:
        message = f"The {attacker_name} attacks the {defender_name} for {damage} hit points."

    add_message(registry, message)

    if defender_fighter.hp <= 0:
        handle_death(defender, registry)
```

The damage formula is `max(1, power - defense)`. The minimum of 1 ensures that combat always makes progress, even when an attacker's power is lower than the defender's defense. This prevents stalled fights where neither side can damage the other.

The message varies based on who is attacking whom. The player sees "You attack the goblin." The goblin sees "The goblin attacks you." This feedback is essential---the player needs to know what happened and how much damage was dealt.

### Handling Death

When an entity's hp drops to zero, it dies. Death processing removes the entity from the game, drops any items it was carrying, and awards experience to the player.

```python
def handle_death(entity: tcod.ecs.Entity, registry: tcod.ecs.Registry) -> None:
    """Process the death of an entity."""
    name = entity.components[Name].name

    if "player" in entity.tags:
        add_message(registry, "You have died!")
        entity.tags.add("dead")
        return

    add_message(registry, f"The {name} is dead!")

    # Remove the entity from the game
    entity.tags.discard("blocks_movement")
    entity.tags.discard("enemy")
    entity.tags.add("dead")

    # Award experience to the player
    player = registry.Q.one(tags=["player"])
    xp = player.components.get(XP)
    if xp is not None:
        # Simple XP formula: base 10 + 5 per level of the enemy
        fighter = entity.components[Fighter]
        xp_gain = 10 + fighter.max_hp
        xp.current += xp_gain
        add_message(registry, f"You gain {xp_gain} experience points.")
```

Dead entities are not removed from the registry immediately. Instead, they are tagged `"dead"` and have their `"blocks_movement"` and `"enemy"` tags removed. This keeps them in the registry for rendering (the death might be visible to the player) but prevents them from participating in future turns.

The player's death is handled differently. The `"dead"` tag is added, but the entity is not stripped of its other tags. The game-over check will detect this tag and end the game.

### The Dead Entity Cleanup System

After enemy turns resolve, a cleanup system removes entities that have been dead for at least one full turn. This prevents visual artifacts from lingering corpses and keeps the registry from accumulating dead entities indefinitely.

```python
# src/systems/cleanup.py

from __future__ import annotations

import tcod.ecs

from components import Position, Renderable


def check_dead_entities(registry: tcod.ecs.Registry) -> None:
    """Remove entities that have been tagged as dead."""
    to_remove = []
    for entity in registry.Q.all_of(tags=["dead"]):
        # Don't remove the player -- game over handles that
        if "player" in entity.tags:
            continue
        to_remove.append(entity)

    for entity in to_remove:
        # Remove components to free memory
        entity.components.clear()
        entity.tags.clear()
```

This system runs once per turn, after all actions and effects have resolved. It finds every entity tagged `"dead"` (except the player) and strips their components and tags. The entity still exists in the registry as an empty shell, but it has no data and no tags, so no query will return it.

A more aggressive approach would call `registry.clear()` or use a dedicated entity removal API, but tcod-ecs does not provide a straightforward way to delete entities. Clearing components and tags achieves the same practical effect: the entity becomes invisible to all queries and consumes negligible memory.

## Game State Updates

After each turn, several pieces of game state need to be updated. These updates happen automatically as part of the turn cycle, but it is worth understanding what they do and why they matter.

### Field of View Recalculation

The player's field of view changes every time they move. A tile that was visible from position (5, 5) might not be visible from position (6, 5). FOV must be recomputed after every movement action.

```python
def update_fov(game_map: GameMap, player: tcod.ecs.Entity) -> None:
    """Recalculate field of view from the player's position."""
    player_pos = player.components[Position]
    game_map.compute_fov(player_pos.x, player_pos.y)
```

The `compute_fov` method was introduced in Chapter 8. It uses tcod's shadowcasting algorithm to determine which tiles are visible from the given position, then updates the `visible` and `explored` arrays accordingly.

FOV is not recomputed for non-movement actions. Waiting does not change your position, so FOV stays the same. Attacking an adjacent enemy does not change your position, so FOV stays the same. Only movement triggers a recomputation.

### Message Log

The message log is the game's communication channel. Every significant event---attacks, damage, item pickups, level transitions---is reported through the log. Messages are accumulated during a turn and displayed together at the bottom of the screen.

```python
# src/components/ui.py

from __future__ import annotations

import attrs


@attrs.define
class MessageLog:
    """Accumulates messages for display in the UI."""
    messages: list[str] = attrs.Factory(list)
    max_messages: int = 50


def add_message(registry: tcod.ecs.Registry, message: str) -> None:
    """Add a message to the log."""
    world = registry[None]
    log = world.components.get(MessageLog)
    if log is not None:
        log.messages.append(message)
        # Keep only the most recent messages
        if len(log.messages) > log.max_messages:
            log.messages = log.messages[-log.max_messages:]
```

The log is stored on the world entity because it is global state---messages belong to the game, not to any individual entity. The `add_message` function appends to the list and trims it to the maximum length. This prevents unbounded memory growth during long games.

### HUD Updates

The HUD displays the player's current status: health, level, position, and turn count. These values are read from components on every render cycle. The HUD does not need explicit "update" logic because it always reads fresh data from the registry.

```python
def render_hud(
    console: tcod.console.Console,
    registry: tcod.ecs.Registry,
    screen_height: int,
) -> None:
    """Render the heads-up display at the bottom of the screen."""
    player = registry.Q.one(tags=["player"])
    fighter = player.components[Fighter]
    xp = player.components.get(XP)

    # Health bar
    hp_text = f"HP: {fighter.hp}/{fighter.max_hp}"
    console.print(x=1, y=screen_height - 1, string=hp_text, fg=(255, 255, 255))

    # Turn counter
    world = registry[None]
    counter = world.components.get(TurnCounter)
    if counter is not None:
        turn_text = f"Turn: {counter.count}"
        console.print(
            x=SCREEN_WIDTH - 15,
            y=screen_height - 1,
            string=turn_text,
            fg=(200, 200, 200),
        )

    # Level and XP
    if xp is not None:
        level_text = f"Lvl: {xp.level}  XP: {xp.current}/{xp.xp_to_next}"
        console.print(
            x=SCREEN_WIDTH // 2 - 10,
            y=screen_height - 1,
            string=level_text,
            fg=(200, 200, 200),
        )
```

The HUD is rendered on every frame, not just on turn transitions. This ensures it stays responsive even when the player opens a menu or examines the map.

## Game Over Detection

The game ends under two conditions: the player dies, or the player reaches the stairs and descends to the next level. Death is the primary game-over condition.

```python
# src/systems/game_over.py

from __future__ import annotations

import tcod.ecs

from components import Fighter, Name


def check_game_over(
    registry: tcod.ecs.Registry,
    player: tcod.ecs.Entity,
) -> bool:
    """Check if the game is over. Returns True if the game should end."""
    world = registry[None]

    # Check if the player is dead
    if "dead" in player.tags:
        world.tags.discard("in_game")
        world.tags.add("game_over")
        return True

    # Check if the player's hp reached zero
    fighter = player.components.get(Fighter)
    if fighter is not None and fighter.hp <= 0:
        handle_death(player, registry)
        world.tags.discard("in_game")
        world.tags.add("game_over")
        return True

    return False
```

The check runs at the end of every turn cycle. If the player's hp is zero or less, the player is marked as dead, the game state transitions to `"game_over"`, and the function returns `True` to signal the game loop to stop.

The game-over screen is a simple overlay:

```python
def render_game_over(
    console: tcod.console.Console,
    registry: tcod.ecs.Registry,
) -> None:
    """Render the game-over screen."""
    # Dim the game view
    console.print(
        x=SCREEN_WIDTH // 2 - 10,
        y=SCREEN_HEIGHT // 2 - 1,
        string="YOU HAVE DIED",
        fg=(255, 0, 0),
    )
    console.print(
        x=SCREEN_WIDTH // 2 - 15,
        y=SCREEN_HEIGHT // 2 + 1,
        string="Press ESC to quit",
        fg=(200, 200, 200),
    )
```

The game-over screen renders on top of the game view. The player can see their final position, the enemies that killed them, and the dungeon as it was when they died. Pressing Escape exits the game.

### Level Transitions

Descending to the next level is the other form of "game over" for a single floor. When the player steps onto the stairs and presses the descend key, the current level is cleared and a new one is generated.

```python
# src/systems/stairs.py

from __future__ import annotations

import tcod.ecs

from components import Position, Name


def check_stairs(
    registry: tcod.ecs.Registry,
    player: tcod.ecs.Entity,
) -> bool:
    """Check if the player is on stairs. Returns True if they should descend."""
    pos = player.components[Position]

    for entity in registry.Q.all_of(tags=["staircase"]):
        stair_pos = entity.components[Position]
        if stair_pos.x == pos.x and stair_pos.y == pos.y:
            return True

    return False
```

This function is called when the player presses the descend key (commonly `>` or `.` with Shift). If the player is on a staircase, the game generates a new level, removes all entities from the current level, and places the player at the start of the new one. Level transitions are covered in detail in Chapter 16.

## The Complete Game Loop

Here is the full game loop, integrating every system we have built in this chapter. This is the central piece of code that ties the game together.

```python
# src/main.py

from __future__ import annotations

import tcod
import tcod.console
import tcod.context
import tcod.ecs
import tcod.event
import tcod.tileset

from actions import BumpAction, WaitAction
from components import AI, AIKind, Fighter, Name, Position, Renderable, XP
from components.world import TurnCounter
from game_map import GameMap
from input_handlers import handle_input
from procgen import generate_dungeon
from render_functions import render_all
from systems.cleanup import check_dead_entities
from systems.combat import attack, handle_death
from systems.enemy_turns import process_enemy_turns
from systems.game_over import check_game_over
from systems.ui import add_message, render_hud

SCREEN_WIDTH = 80
SCREEN_HEIGHT = 50

TILESET = tcod.tileset.load_truetype_font(
    "data/fonts/dejavu10x10.ttf", tile_width=16, tile_height=16
)


def process_action(
    action: Action,
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

        if not dungeon.is_walkable(target_x, target_y):
            return False

        target = get_entity_at(registry, target_x, target_y)
        if target is not None:
            if "enemy" in target.tags:
                attack(action.entity, target, registry)
                return True
            return False

        pos.x = target_x
        pos.y = target_y
        return True

    return False


def get_entity_at(
    registry: tcod.ecs.Registry,
    x: int,
    y: int,
) -> tcod.ecs.Entity | None:
    """Return the first blocking entity at (x, y), or None."""
    for entity in registry.Q.all_of(tags=["blocks_movement"]):
        pos = entity.components[Position]
        if pos.x == x and pos.y == y:
            return entity
    return None


def main() -> None:
    registry = tcod.ecs.Registry()

    dungeon = generate_dungeon(
        max_rooms=30,
        room_min_size=6,
        room_max_size=10,
        map_width=SCREEN_WIDTH,
        map_height=SCREEN_HEIGHT,
    )

    first_room = dungeon.rooms[0]
    player_x, player_y = first_room.center
    player = create_player(registry, player_x, player_y)

    place_enemies(registry, dungeon, skip_room=0)

    registry.context["game_map"] = dungeon

    world = registry[None]
    world.components[TurnCounter] = TurnCounter(count=0)
    world.components[MessageLog] = MessageLog()
    world.tags.add("in_game")
    world.relation_tag["player"] = player

    dungeon.explored[:] = True
    dungeon.visible[:] = True

    console = tcod.console.Console(SCREEN_WIDTH, SCREEN_HEIGHT, order="C")

    with tcod.context.new(
        console=console,
        tileset=TILESET,
        title="Roguelike",
    ) as context:
        needs_render = True

        while True:
            world = registry[None]

            if needs_render:
                console.clear()
                render_all(console, dungeon, registry, player)
                render_hud(console, registry, SCREEN_HEIGHT)

                if "game_over" in world.tags:
                    render_game_over(console, registry)

                context.present(console)
                needs_render = False

            for event in tcod.event.wait():
                if isinstance(event, tcod.event.Quit):
                    raise SystemExit()
                if isinstance(event, tcod.event.KeyDown):
                    if event.sym == tcod.event.KeySym.ESCAPE:
                        raise SystemExit()

                    if "game_over" in world.tags:
                        continue

                    action = handle_input(event, player)
                    if action is not None:
                        turn_consumed = process_action(action, registry, dungeon)

                        if turn_consumed:
                            process_enemy_turns(registry, dungeon, player)
                            advance_turn(registry)
                            update_fov(dungeon, player)
                            check_dead_entities(registry)

                            if check_game_over(registry, player):
                                needs_render = True
                                continue

                        needs_render = True


if __name__ == "__main__":
    main()
```

The loop structure is clear and linear. There are no hidden state transitions, no callback chains, no event queues. Each iteration of the loop represents one turn (or part of one turn, if the player is navigating a menu). The code reads top to bottom: render, wait for input, process action, process enemies, advance time, check for death, repeat.

This is the heartbeat of the game. Everything else---combat, AI, items, traps, spells---plugs into this loop as additional systems that run during the appropriate phase of the turn cycle.

## Exercises

**Exercise 1: Energy-Based Turn System**

Replace the simple turn counter with an energy-based system. Create an `Energy` component with `current` and `speed` fields. Each turn, every entity with an `Energy` component gains `speed` energy. An entity can act only when its `current` energy is at least 100 (the cost of one action). After acting, subtract 100 from `current`. Give the player speed 100 and enemies speed 80. How does this change the feel of combat?

**Exercise 2: Surprise Mechanic**

Implement a "surprise" mechanic. When an enemy first sees the player (transitions from not-visible to visible), it should not act on that turn. This gives the player a free turn to attack or reposition before the enemy responds. Track this with a `"surprised"` tag that is added when the enemy first enters the player's FOV and removed after the enemy's first turn.

**Exercise 3: Turn Counter Display**

Add the turn counter to the HUD. Display it as "Turn: 42" in the bottom-right corner of the screen. Also display the total number of enemies alive on the current level. This gives the player context for their progress.

**Exercise 4: Enemy AI Variation**

Add a new `AIKind.STATIONARY` behavior. Stationary enemies never move---they attack only when the player bumps into them. Create a "guard" entity type with this behavior: high hp and defense, but zero movement. Place one in each room. How does this change room-clearing strategy?

**Exercise 5: Death Screen with Stats**

When the player dies, display a summary screen showing: total turns taken, total enemies killed (track this in a component on the player), the dungeon floor reached, and total XP earned. This gives the player feedback on their performance and motivation to try again.

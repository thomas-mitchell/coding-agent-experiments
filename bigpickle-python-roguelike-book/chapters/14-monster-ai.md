# Chapter 14: Monster AI Behaviors

Chapter 12 introduced the turn-based game loop and built a basic enemy AI system: hostile enemies chase the player, confused enemies wander randomly, and fleeing enemies run away. These three behaviors work, but they produce enemies that all feel the same. Every hostile enemy charges straight at the player with no variation, no coordination, no self-preservation. The dungeon is a collection of identical threats, not a roster of distinct creatures.

This chapter expands the AI system into something richer. We will add pathfinding so enemies navigate around walls instead of walking into them. We will build an AI state machine so enemies transition between behaviors based on conditions. We will implement pack AI so enemies coordinate their attacks. And we will design enemy archetypes where each creature type has a distinct behavioral personality. By the end of this chapter, a kobold feels different from an orc, a skeleton feels different from a goblin, and the dungeon is a place where each encounter demands a different tactic.

## AI Design Philosophy

The goal of monster AI in a roguelike is not realism. Realistic AI is complex, slow, and often boring. A goblin that carefully evaluates sightlines, considers flanking positions, and calculates optimal engagement distances is indistinguishable from a goblin that charges the player---the player only sees the end result.

The goal is **readability**. The player should be able to look at an enemy's behavior and immediately understand why it did what it did. An orc charges because it is aggressive. A kobold flees because it is cowardly. A skeleton never retreats because it is mindless. These behaviors are simple rules, but they create the illusion of personality.

The second goal is **emergence**. Simple rules interacting with a complex environment produce complex behavior. A hostile enemy that chases the player and a confused enemy that moves randomly are both simple individually. But when a confusion spell turns an orc into a random walker in a room full of other orcs, the result is chaos---the confused orc bumps into allies, blocks corridors, and creates unpredictable dynamics. The player did not program that complexity. It emerged from the interaction of simple systems.

The third goal is **debuggability**. When an enemy does something unexpected, you need to understand why. If the AI is a monolithic function with dozens of branches, debugging is painful. If the AI is a state machine with clear transitions and each behavior is a small, isolated function, you can trace the decision chain in seconds. Design for the moment when something goes wrong, because it will.

## AI Component Design

The AI component from Chapter 6 needs to carry more data. A simple `AIKind` enum is enough for three behaviors, but once enemies have states, parameters, and memory, the component needs to grow.

Here is the expanded AI component:

```python
# src/components/ai.py

from __future__ import annotations

from enum import Enum

import attrs


class AIKind(Enum):
    """The type of AI behavior an entity uses."""

    HOSTILE = "hostile"
    CONFUSED = "confused"
    FLEEING = "fleeing"
    STATIONARY = "stationary"


class AIState(Enum):
    """The current behavioral state of an AI entity."""

    IDLE = "idle"
    CHASING = "chasing"
    ATTACKING = "attacking"
    FLEEING = "fleeing"
    CONFUSED = "confused"
    WANDERING = "wandering"


@attrs.define
class AI:
    """Marks an entity as having autonomous behavior."""

    kind: AIKind = AIKind.HOSTILE
    state: AIState = AIState.IDLE
    previous_ai: AIKind | None = None
    state_turns_remaining: int = 0
    wander_dx: int = 0
    wander_dy: int = 0
    alert_allies: bool = False
    flee_threshold: float = 0.25
    pack_id: str = ""
```

The new fields serve specific purposes:

- `state` tracks the current behavioral state within the AI kind. A hostile AI can be IDLE, CHASING, or ATTACKING. A confused AI is always CONFUSED. The state determines which behavior function runs this turn.
- `previous_ai` stores the AI kind before a status effect changed it. When a confusion spell expires, the entity reverts to its previous AI kind.
- `state_turns_remaining` counts down turns for temporary states. Confusion lasts for a number of turns, then wears off.
- `wander_dx` and `wander_dy` store the last movement direction for wandering behavior. An idle enemy that wanders picks a direction and sticks with it for a few turns, producing more natural patrol-like movement than random direction changes every turn.
- `alert_allies` controls whether this enemy alerts nearby pack members when it spots the player.
- `flee_threshold` is the fraction of maximum hp at which the enemy switches to fleeing behavior. The default of 0.25 means the enemy flees when hp drops below 25%.
- `pack_id` links enemies into coordination groups. Enemies with the same `pack_id` share awareness of the player.

## Hostile AI

The hostile behavior from Chapter 12 was simple: chase the player if visible, attack if adjacent. The improved version adds pathfinding and a state machine.

```python
# src/systems/ai_behaviors.py

from __future__ import annotations

import random
from typing import TYPE_CHECKING

import tcod.ecs
from tcod.path import SimpleGraph, AStar

from components import AI, AIKind, AIState, Fighter, Name, Position

if TYPE_CHECKING:
    from game_map import GameMap


def _process_hostile_ai(
    entity: tcod.ecs.Entity,
    game_map: GameMap,
    player: tcod.ecs.Entity,
    registry: tcod.ecs.Registry,
) -> None:
    """Hostile AI: chase player, attack when adjacent, wander when idle."""
    ai = entity.components[AI]
    pos = entity.components[Position]
    player_pos = player.components[Position]

    can_see_player = game_map.visible[pos.y, pos.x]

    if can_see_player:
        dx = player_pos.x - pos.x
        dy = player_pos.y - pos.y
        distance = abs(dx) + abs(dy)

        if distance <= 1:
            ai.state = AIState.ATTACKING
            _attack(entity, player, registry)
            return

        ai.state = AIState.CHASING
        _chase_with_pathfinding(entity, player, game_map, registry)
    else:
        if ai.state == AIState.CHASING:
            ai.state = AIState.WANDERING
        _wander(entity, game_map)
```

The function now checks whether the enemy can see the player before making decisions. If the player is visible and adjacent, the enemy attacks. If the player is visible but not adjacent, the enemy chases using pathfinding. If the player is not visible, the enemy wanders in place or along a corridor.

The state transitions are explicit. The enemy transitions from IDLE to CHASING when it spots the player, from CHASING to ATTACKING when it reaches the player, and from CHASING to WANDERING when the player leaves its field of view. These transitions are logged in the AI component so other systems---and the debugger---can inspect them.

## Using tcod Pathfinding

The naive chase behavior from Chapter 12 moves toward the player one tile at a time, choosing the axis with the greater distance. This works in open rooms but fails around corners and walls. An enemy on one side of a wall will walk into the wall every turn, unable to reach the player on the other side.

tcod provides a pathfinding system built on the same graph structure as its field of view computation. The `SimpleGraph` class represents the walkability of the map, and `AStar` computes shortest paths through it.

```python
from tcod.path import SimpleGraph, AStar


def _build_pathfinder(game_map: GameMap) -> AStar:
    """Build an A* pathfinder from the current game map."""
    graph = SimpleGraph(
        width=game_map.width,
        height=game_map.height,
        walkable=game_map.tiles["walkable"],
    )
    return AStar(graph)


def _chase_with_pathfinding(
    entity: tcod.ecs.Entity,
    player: tcod.ecs.Entity,
    game_map: GameMap,
    registry: tcod.ecs.Registry,
) -> None:
    """Move one step toward the player using A* pathfinding."""
    pos = entity.components[Position]
    player_pos = player.components[Position]

    astar = _build_pathfinder(game_map)
    path = astar.path(
        start=(pos.x, pos.y),
        goal=(player_pos.x, player_pos.y),
    )

    if len(path) < 2:
        return

    # path[0] is the start position, path[1] is the next step
    next_x, next_y = path[1]

    # Check that no other entity blocks the destination
    for other in registry.Q.all_of(tags=["blocks_movement"]):
        other_pos = other.components[Position]
        if other_pos.x == next_x and other_pos.y == next_y:
            return  # Blocked, stay still this turn

    pos.x = next_x
    pos.y = next_y
```

The pathfinder is rebuilt every turn. This is intentional. The map does not change between turns in most roguelikes, so the pathfinder could be cached. But rebuilding it is fast---A* on a typical 80x50 dungeon completes in microseconds---and caching introduces invalidation complexity that is not worth the performance gain. If performance becomes a concern on larger maps, the pathfinder can be cached on the world entity and rebuilt only when the map changes.

The `path` method returns a list of `(x, y)` tuples from the start to the goal. The first element is always the entity's current position. The second element is the next step on the shortest path. We move one step per turn, so we only read `path[1]`.

The entity collision check prevents pathfinding from moving an enemy onto a tile occupied by another entity. If the next step is blocked, the enemy waits. This is a simplification---a more sophisticated AI would path around other entities---but it works for most cases. Enemies in corridors will wait for the path to clear rather than walking through allies.

Note that the `SimpleGraph` is initialized with `game_map.tiles["walkable"]`, which is a numpy boolean array. This array is already computed by the game map and accounts for walls, closed doors, and other impassable terrain. The pathfinder respects these constraints automatically.

## Confused AI

Confusion is a status effect, not a permanent behavior. When a confusion spell hits an enemy, the enemy's AI kind changes from its current type to CONFUSED, and the previous type is saved for later restoration.

```python
def _process_confused_ai(
    entity: tcod.ecs.Entity,
    game_map: GameMap,
    registry: tcod.ecs.Registry,
) -> None:
    """Confused AI: move randomly for a limited duration."""
    ai = entity.components[AI]
    pos = entity.components[Position]

    if ai.state_turns_remaining <= 0:
        # Confusion has worn off, revert to previous AI
        if ai.previous_ai is not None:
            ai.kind = ai.previous_ai
            ai.previous_ai = None
            ai.state = AIState.IDLE
        return

    ai.state_turns_remaining -= 1
    ai.state = AIState.CONFUSED

    dx = random.choice([-1, 0, 1])
    dy = random.choice([-1, 0, 1])

    if dx == 0 and dy == 0:
        return

    target_x = pos.x + dx
    target_y = pos.y + dy

    if game_map.is_walkable(target_x, target_y):
        # Check for entity collision -- confused enemies attack anyone
        target = _get_entity_at(registry, target_x, target_y)
        if target is not None:
            _attack(entity, target, registry)
        else:
            pos.x = target_x
            pos.y = target_y
```

The confusion effect decrements `state_turns_remaining` each turn. When it reaches zero, the enemy reverts to its previous AI kind. This means a confused orc becomes a hostile orc again, picking up its behavior from where it left off.

The entity collision check in the confused AI is different from the hostile AI. A confused enemy does not check whether the target is a friend or foe. It attacks whatever is in the way. This makes confusion strategically valuable: cast it on an orc standing next to another orc, and the confused orc might attack its ally.

Applying confusion requires storing the previous AI and setting the new kind:

```python
def apply_confusion(
    entity: tcod.ecs.Entity,
    duration: int = 10,
) -> None:
    """Apply a confusion effect to an entity."""
    ai = entity.components.get(AI)
    if ai is None:
        return

    ai.previous_ai = ai.kind
    ai.kind = AIKind.CONFUSED
    ai.state = AIState.CONFUSED
    ai.state_turns_remaining = duration
```

The `previous_ai` field ensures the effect is reversible. Without it, confusion would be permanent---the entity would wander forever with no way to recover.

## Fleeing AI

Fleeing is a self-preservation instinct. When an enemy's hp drops below a threshold, it abandons combat and runs. The threshold is defined per-entity through the `flee_threshold` field on the AI component.

```python
def _process_fleeing_ai(
    entity: tcod.ecs.Entity,
    game_map: GameMap,
    player: tcod.ecs.Entity,
    registry: tcod.ecs.Registry,
) -> None:
    """Fleeing AI: move away from the player when hp is low."""
    ai = entity.components[AI]
    pos = entity.components[Position]
    fighter = entity.components.get(Fighter)
    player_pos = player.components[Position]

    if fighter is None:
        return

    # Check if hp is above the flee threshold -- stop fleeing
    if fighter.hp > fighter.max_hp * ai.flee_threshold:
        ai.kind = AIKind.HOSTILE
        ai.state = AIState.IDLE
        return

    ai.state = AIState.FLEEING

    dx = pos.x - player_pos.x
    dy = pos.y - player_pos.y

    dx = max(-1, min(1, dx))
    dy = max(-1, min(1, dy))

    target_x = pos.x + dx
    target_y = pos.y + dy

    if game_map.is_walkable(target_x, target_y):
        for other in registry.Q.all_of(tags=["blocks_movement"]):
            other_pos = other.components[Position]
            if other_pos.x == target_x and other_pos.y == target_y:
                return

        pos.x = target_x
        pos.y = target_y
```

The fleeing AI checks hp every turn. If hp rises above the threshold---perhaps the enemy was healed by an ally---it switches back to hostile behavior. This creates an interesting dynamic: enemies that can heal each other will flee, get healed, and re-engage.

The movement direction is the reverse of the hostile chase. Instead of moving toward the player, the enemy moves away. The direction is clamped to [-1, 1] to prevent multi-tile movement. If all adjacent tiles are blocked, the enemy stays still---cornered and vulnerable.

To configure an enemy with fleeing behavior:

```python
def create_cowardly_kobold(
    registry: tcod.ecs.Registry, x: int, y: int
) -> tcod.ecs.Entity:
    entity = registry.new_entity()
    entity.components |= {
        Position: Position(x=x, y=y),
        Renderable: Renderable(char="k", fg=(255, 128, 0), render_order=1),
        Name: Name(name="kobold"),
        Fighter: Fighter(hp=8, max_hp=8, power=3, defense=0),
        AI: AI(kind=AIKind.HOSTILE, flee_threshold=0.5),
    }
    entity.tags |= {"enemy", "blocks_movement"}
    return entity
```

This kobold flees when hp drops below 50%---twice the default threshold. It runs early and often, making it difficult to kill in a straight fight. The player must corner it or use ranged attacks.

## Stationary AI

Stationary enemies never move. They attack only when the player bumps into them or when the player is adjacent. This behavior is useful for turrets, traps disguised as entities, and defensive enemies like guards that hold a position.

```python
def _process_stationary_ai(
    entity: tcod.ecs.Entity,
    game_map: GameMap,
    player: tcod.ecs.Entity,
    registry: tcod.ecs.Registry,
) -> None:
    """Stationary AI: attack adjacent enemies, never move."""
    pos = entity.components[Position]
    player_pos = player.components[Position]

    if not game_map.visible[pos.y, pos.x]:
        return

    dx = player_pos.x - pos.x
    dy = player_pos.y - pos.y
    distance = abs(dx) + abs(dy)

    if distance <= 1:
        _attack(entity, player, registry)
```

The stationary AI is the simplest behavior. It checks whether the player is adjacent and within its field of view. If so, it attacks. If not, it does nothing. There is no movement, no pathfinding, no state machine. The entity is a fixed hazard that the player must plan around.

Stationary enemies are interesting from a level design perspective. A room with a stationary troll guarding a treasure chest forces the player to find a way past the troll---either by fighting it head-on, luring it out of position (if it can be provoked), or finding an alternate route.

## Pack AI

Pack AI creates coordination between enemies. When one enemy in a pack spots the player, nearby pack members become alerted and begin chasing as well. This simulates enemies that watch each other's backs and respond to shared threats.

Pack behavior is built on two mechanisms: a shared `pack_id` on the AI component, and an alert system that propagates awareness between pack members.

```python
def _alert_pack_members(
    entity: tcod.ecs.Entity,
    registry: tcod.ecs.Registry,
    game_map: GameMap,
) -> None:
    """Alert nearby pack members that the player has been spotted."""
    ai = entity.components.get(AI)
    if ai is None or not ai.alert_allies or not ai.pack_id:
        return

    pos = entity.components[Position]
    alert_radius = 8

    for other in registry.Q.all_of(tags=["enemy"]):
        other_ai = other.components.get(AI)
        if other_ai is None:
            continue
        if other_ai.pack_id != ai.pack_id:
            continue
        if other_ai.state in (AIState.CHASING, AIState.ATTACKING):
            continue  # Already alert

        other_pos = other.components[Position]
        dx = other_pos.x - pos.x
        dy = other_pos.y - pos.y
        if abs(dx) + abs(dy) <= alert_radius:
            other_ai.state = AIState.CHASING
```

The alert function iterates over all enemies in the registry and checks whether each one shares the same `pack_id`. Pack members within the alert radius are set to the CHASING state, even if they cannot see the player themselves. This means an enemy around a corner will begin moving toward the player once a pack mate spots them.

The alert only triggers once per encounter. Once an enemy is in the CHASING or ATTACKING state, it does not get alerted again. This prevents infinite alert cascading.

The hostile AI calls the alert function when it first spots the player:

```python
def _process_hostile_ai(
    entity: tcod.ecs.Entity,
    game_map: GameMap,
    player: tcod.ecs.Entity,
    registry: tcod.ecs.Registry,
) -> None:
    """Hostile AI with pack alerting."""
    ai = entity.components[AI]
    pos = entity.components[Position]
    player_pos = player.components[Position]

    can_see_player = game_map.visible[pos.y, pos.x]

    if can_see_player:
        if ai.state != AIState.CHASING and ai.state != AIState.ATTACKING:
            _alert_pack_members(entity, registry, game_map)

        dx = player_pos.x - pos.x
        dy = player_pos.y - pos.y
        distance = abs(dx) + abs(dy)

        if distance <= 1:
            ai.state = AIState.ATTACKING
            _attack(entity, player, registry)
            return

        ai.state = AIState.CHASING
        _chase_with_pathfinding(entity, player, game_map, registry)
    else:
        if ai.state == AIState.CHASING:
            ai.state = AIState.WANDERING
        _wander(entity, game_map)
```

The alert check uses `ai.state` to determine whether the enemy has already been alerted. If it is already chasing or attacking, it does not re-alert its pack. The alert fires only on the transition from not-chasing to chasing---the moment the enemy first spots the player.

Pack members are defined at entity creation time:

```python
def create_wolf(registry: tcod.ecs.Registry, x: int, y: int) -> tcod.ecs.Entity:
    entity = registry.new_entity()
    entity.components |= {
        Position: Position(x=x, y=y),
        Renderable: Renderable(char="w", fg=(128, 128, 128), render_order=1),
        Name: Name(name="wolf"),
        Fighter: Fighter(hp=10, max_hp=10, power=4, defense=1),
        AI: AI(kind=AIKind.HOSTILE, alert_allies=True, pack_id="wolves"),
    }
    entity.tags |= {"enemy", "blocks_movement"}
    return entity
```

Every wolf shares `pack_id="wolves"` and has `alert_allies=True`. When one wolf spots the player, every wolf within 8 tiles begins chasing. The player faces a coordinated pack, not a series of isolated enemies.

## Wandering Behavior

Enemies that lose sight of the player do not stand still indefinitely. They wander, moving in a consistent direction for a few turns before picking a new one. This simulates patrol behavior and keeps the dungeon feeling alive even when the player is not in direct combat.

```python
def _wander(entity: tcod.ecs.Entity, game_map: GameMap) -> None:
    """Wander in a consistent direction, changing direction periodically."""
    ai = entity.components[AI]
    pos = entity.components[Position]

    # Pick a new direction every few turns
    ai.state_turns_remaining -= 1
    if ai.state_turns_remaining <= 0:
        ai.wander_dx = random.choice([-1, 0, 1])
        ai.wander_dy = random.choice([-1, 0, 1])
        ai.state_turns_remaining = random.randint(2, 5)

    if ai.wander_dx == 0 and ai.wander_dy == 0:
        return

    target_x = pos.x + ai.wander_dx
    target_y = pos.y + ai.wander_dy

    if game_map.is_walkable(target_x, target_y):
        pos.x = target_x
        pos.y = target_y
    else:
        # Hit a wall, pick a new direction immediately
        ai.state_turns_remaining = 0
```

The wander function picks a random direction and moves in it for 2 to 5 turns. When the timer expires, it picks a new direction. If the enemy hits a wall, it picks a new direction immediately. This produces natural-looking patrol patterns: an enemy walks down a corridor, turns when it reaches an intersection, and continues until it hits another wall.

## The AI System

The AI system ties all behaviors together. It iterates over every entity with an AI component and dispatches to the appropriate behavior function.

```python
# src/systems/ai_system.py

from __future__ import annotations

from typing import TYPE_CHECKING

import tcod.ecs

from components import AI, AIKind, Fighter, Position

if TYPE_CHECKING:
    from game_map import GameMap


def process_ai_turns(
    registry: tcod.ecs.Registry,
    game_map: GameMap,
    player: tcod.ecs.Entity,
) -> None:
    """Process AI turns for all enemy entities."""
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

        # Skip if no position
        if Position not in entity.components:
            continue

        # Check for flee condition before dispatching to AI kind
        if ai.kind == AIKind.HOSTILE and _should_flee(entity):
            ai.kind = AIKind.FLEEING

        # Dispatch to the appropriate behavior
        if ai.kind == AIKind.HOSTILE:
            _process_hostile_ai(entity, game_map, player, registry)
        elif ai.kind == AIKind.CONFUSED:
            _process_confused_ai(entity, game_map, registry)
        elif ai.kind == AIKind.FLEEING:
            _process_fleeing_ai(entity, game_map, player, registry)
        elif ai.kind == AIKind.STATIONARY:
            _process_stationary_ai(entity, game_map, player, registry)


def _should_flee(entity: tcod.ecs.Entity) -> bool:
    """Check if an entity should switch to fleeing behavior."""
    ai = entity.components.get(AI)
    fighter = entity.components.get(Fighter)
    if ai is None or fighter is None:
        return False

    return fighter.hp <= fighter.max_hp * ai.flee_threshold
```

The system checks the flee condition before dispatching. This means any hostile enemy can transition to fleeing based on its hp, regardless of which behavior function would normally run. The flee check is centralized in the system rather than duplicated in each behavior function.

The dead-entity check prevents the system from processing actions for entities that have been killed but not yet cleaned up. This is a safety check---the enemy turn system should not encounter dead entities, but defensive programming prevents crashes from edge cases.

## Debugging AI

When an enemy does something unexpected, you need to understand why. The AI system has several debugging mechanisms that can be toggled on and off.

**Console logging.** Print each AI decision to the console during development:

```python
def _debug_ai_decision(
    entity: tcod.ecs.Entity,
    action: str,
) -> None:
    """Print AI decisions to the console for debugging."""
    name = entity.components.get(Name)
    ai = entity.components.get(AI)
    if name is None or ai is None:
        return

    print(f"  {name.name}: state={ai.state.value}, action={action}")
```

Call this at the end of each behavior function with a description of what the AI decided to do. During normal gameplay, these prints are suppressed by a debug flag. When investigating a bug, toggle the flag and watch the decision log scroll in the terminal.

**Visual state indicators.** Change the enemy's color based on its AI state:

```python
AI_STATE_COLORS = {
    AIState.IDLE: (128, 128, 128),       # Gray
    AIState.CHASING: (255, 0, 0),        # Red
    AIState.ATTACKING: (255, 64, 0),     # Orange-red
    AIState.FLEEING: (0, 128, 255),      # Blue
    AIState.CONFUSED: (191, 0, 191),     # Purple
    AIState.WANDERING: (128, 128, 0),    # Olive
}


def update_ai_visual_debug(
    registry: tcod.ecs.Registry,
) -> None:
    """Update entity colors based on AI state for visual debugging."""
    for entity in registry.Q.all_of(tags=["enemy"]):
        ai = entity.components.get(AI)
        renderable = entity.components.get(Renderable)
        if ai is None or renderable is None:
            continue

        color = AI_STATE_COLORS.get(ai.state)
        if color is not None:
            renderable.fg = color
```

When enabled, enemies change color based on their current state. Chasing enemies are red. Fleeing enemies are blue. Confused enemies are purple. This makes AI behavior visible at a glance without reading log output.

**Hover tooltips.** In the rendering system, display AI state when the mouse hovers over an enemy:

```python
def render_ai_tooltip(
    console: tcod.console.Console,
    entity: tcod.ecs.Entity,
    x: int,
    y: int,
) -> None:
    """Render AI state tooltip at the given screen position."""
    ai = entity.components.get(AI)
    name = entity.components.get(Name)
    if ai is None or name is None:
        return

    lines = [
        name.name,
        f"State: {ai.state.value}",
        f"AI: {ai.kind.value}",
    ]

    for i, line in enumerate(lines):
        console.print(x=x, y=y + i, string=line, fg=(255, 255, 255))
```

The tooltip shows the entity's name, current state, and AI kind. This is useful during testing and can be left enabled as a player-facing examine feature.

## Enemy Variety by Behavior

The combination of AI kinds, states, and parameters produces distinct enemy personalities. Here are five archetypes that demonstrate the range of the system.

**Kobold.** Small, cowardly, dangerous in groups. The kobold uses hostile AI with a high flee threshold and pack alerting:

```python
def create_kobold(registry: tcod.ecs.Registry, x: int, y: int) -> tcod.ecs.Entity:
    entity = registry.new_entity()
    entity.components |= {
        Position: Position(x=x, y=y),
        Renderable: Renderable(char="k", fg=(255, 0, 0), render_order=1),
        Name: Name(name="kobold"),
        Fighter: Fighter(hp=8, max_hp=8, power=3, defense=0),
        AI: AI(
            kind=AIKind.HOSTILE,
            flee_threshold=0.5,
            alert_allies=True,
            pack_id="kobolds",
        ),
    }
    entity.tags |= {"enemy", "blocks_movement"}
    return entity
```

The kobold flees at 50% hp and alerts nearby kobolds when it spots the player. A lone kobold runs away. A pack of kobolds rushes the player from multiple directions, with the wounded ones retreating while fresh ones take their place. This creates a dynamic where the player must thin the pack quickly or be overwhelmed.

**Orc.** Standard melee enemy. Aggressive, no flee behavior, no pack coordination:

```python
def create_orc(registry: tcod.ecs.Registry, x: int, y: int) -> tcod.ecs.Entity:
    entity = registry.new_entity()
    entity.components |= {
        Position: Position(x=x, y=y),
        Renderable: Renderable(char="o", fg=(63, 127, 63), render_order=1),
        Name: Name(name="orc"),
        Fighter: Fighter(hp=15, max_hp=15, power=5, defense=2),
        AI: AI(kind=AIKind.HOSTILE, flee_threshold=0.0),
    }
    entity.tags |= {"enemy", "blocks_movement"}
    return entity
```

The orc has `flee_threshold=0.0`, meaning it never flees. It fights to the death. This makes orcs reliable threats---the player knows an orc will always charge and never run. The orc's higher stats (15 hp, 5 power, 2 defense) compensate for its straightforward behavior.

**Troll.** Slow, powerful, stationary until provoked:

```python
def create_troll(registry: tcod.ecs.Registry, x: int, y: int) -> tcod.ecs.Entity:
    entity = registry.new_entity()
    entity.components |= {
        Position: Position(x=x, y=y),
        Renderable: Renderable(char="T", fg=(0, 128, 0), render_order=1),
        Name: Name(name="troll"),
        Fighter: Fighter(hp=25, max_hp=25, power=8, defense=4),
        AI: AI(kind=AIKind.STATIONARY),
    }
    entity.tags |= {"enemy", "blocks_movement"}
    return entity
```

The troll starts as stationary. It stands in a room and attacks anything that comes within melee range. The player must decide whether to fight the troll head-on or find a way around it. If the game design calls for trolls that become hostile after being attacked, the troll can be switched to HOSTILE dynamically when it takes damage:

```python
def on_troll_damaged(entity: tcod.ecs.Entity) -> None:
    """Switch a troll from stationary to hostile when it takes damage."""
    ai = entity.components.get(AI)
    if ai is not None and ai.kind == AIKind.STATIONARY:
        ai.kind = AIKind.HOSTILE
        ai.state = AIState.CHASING
```

**Goblin.** Fast, hits and retreats. The goblin uses hostile AI with a moderate flee threshold:

```python
def create_goblin(registry: tcod.ecs.Registry, x: int, y: int) -> tcod.ecs.Entity:
    entity = registry.new_entity()
    entity.components |= {
        Position: Position(x=x, y=y),
        Renderable: Renderable(char="g", fg=(0, 200, 0), render_order=1),
        Name: Name(name="goblin"),
        Fighter: Fighter(hp=8, max_hp=8, power=4, defense=0),
        AI: AI(kind=AIKind.HOSTILE, flee_threshold=0.4),
    }
    entity.tags |= {"enemy", "blocks_movement"}
    return entity
```

The goblin has high power relative to its hp and defense. It charges, attacks, and flees when wounded. The player must chase it down or use area attacks to catch it before it escapes. The goblin's low defense means the player can kill it in one or two hits, but only if they can land them.

**Skeleton.** Mindless, immune to confusion, always hostile:

```python
def create_skeleton(registry: tcod.ecs.Registry, x: int, y: int) -> tcod.ecs.Entity:
    entity = registry.new_entity()
    entity.components |= {
        Position: Position(x=x, y=y),
        Renderable: Renderable(char="s", fg=(200, 200, 200), render_order=1),
        Name: Name(name="skeleton"),
        Fighter: Fighter(hp=10, max_hp=10, power=4, defense=1),
        AI: AI(kind=AIKind.HOSTILE, flee_threshold=0.0),
    }
    entity.tags |= {"enemy", "blocks_movement", "immune_to_confusion"}
    return entity
```

The skeleton has `flee_threshold=0.0` and the `"immune_to_confusion"` tag. When the confusion system checks whether to apply confusion, it checks for this tag and skips the entity. The skeleton is a relentless enemy that cannot be debuffed---the player must fight it with raw damage.

The confusion application system checks for immunity:

```python
def apply_confusion(
    entity: tcod.ecs.Entity,
    duration: int = 10,
) -> None:
    """Apply a confusion effect to an entity, respecting immunity."""
    if "immune_to_confusion" in entity.tags:
        return

    ai = entity.components.get(AI)
    if ai is None:
        return

    ai.previous_ai = ai.kind
    ai.kind = AIKind.CONFUSED
    ai.state = AIState.CONFUSED
    ai.state_turns_remaining = duration
```

## The Complete AI System

Here is the full AI module, integrating all behaviors, pathfinding, pack alerting, wandering, and the state machine:

```python
# src/systems/ai_system.py

from __future__ import annotations

import random
from typing import TYPE_CHECKING

import tcod.ecs
from tcod.path import AStar, SimpleGraph

from components import AI, AIKind, AIState, Fighter, Name, Position, Renderable

if TYPE_CHECKING:
    from game_map import GameMap


def process_ai_turns(
    registry: tcod.ecs.Registry,
    game_map: GameMap,
    player: tcod.ecs.Entity,
) -> None:
    """Process AI turns for all enemy entities."""
    for entity in registry.Q.all_of(tags=["enemy"]):
        ai = entity.components.get(AI)
        if ai is None or "dead" in entity.tags:
            continue

        fighter = entity.components.get(Fighter)
        if fighter is not None and fighter.hp <= 0:
            continue

        if Position not in entity.components:
            continue

        if ai.kind == AIKind.HOSTILE and _should_flee(entity):
            ai.kind = AIKind.FLEEING

        if ai.kind == AIKind.HOSTILE:
            _process_hostile_ai(entity, game_map, player, registry)
        elif ai.kind == AIKind.CONFUSED:
            _process_confused_ai(entity, game_map, registry)
        elif ai.kind == AIKind.FLEEING:
            _process_fleeing_ai(entity, game_map, player, registry)
        elif ai.kind == AIKind.STATIONARY:
            _process_stationary_ai(entity, game_map, player, registry)


def _should_flee(entity: tcod.ecs.Entity) -> bool:
    ai = entity.components.get(AI)
    fighter = entity.components.get(Fighter)
    if ai is None or fighter is None:
        return False
    return fighter.hp <= fighter.max_hp * ai.flee_threshold


def _process_hostile_ai(
    entity: tcod.ecs.Entity,
    game_map: GameMap,
    player: tcod.ecs.Entity,
    registry: tcod.ecs.Registry,
) -> None:
    ai = entity.components[AI]
    pos = entity.components[Position]
    player_pos = player.components[Position]

    can_see_player = game_map.visible[pos.y, pos.x]

    if can_see_player:
        if ai.state not in (AIState.CHASING, AIState.ATTACKING):
            _alert_pack_members(entity, registry)

        dx = player_pos.x - pos.x
        dy = player_pos.y - pos.y
        distance = abs(dx) + abs(dy)

        if distance <= 1:
            ai.state = AIState.ATTACKING
            _attack(entity, player, registry)
            return

        ai.state = AIState.CHASING
        _chase_with_pathfinding(entity, player, game_map, registry)
    else:
        if ai.state == AIState.CHASING:
            ai.state = AIState.WANDERING
        _wander(entity, game_map)


def _chase_with_pathfinding(
    entity: tcod.ecs.Entity,
    player: tcod.ecs.Entity,
    game_map: GameMap,
    registry: tcod.ecs.Registry,
) -> None:
    pos = entity.components[Position]
    player_pos = player.components[Position]

    graph = SimpleGraph(
        width=game_map.width,
        height=game_map.height,
        walkable=game_map.tiles["walkable"],
    )
    astar = AStar(graph)
    path = astar.path(start=(pos.x, pos.y), goal=(player_pos.x, player_pos.y))

    if len(path) < 2:
        return

    next_x, next_y = path[1]

    for other in registry.Q.all_of(tags=["blocks_movement"]):
        other_pos = other.components[Position]
        if other_pos.x == next_x and other_pos.y == next_y:
            return

    pos.x = next_x
    pos.y = next_y


def _process_confused_ai(
    entity: tcod.ecs.Entity,
    game_map: GameMap,
    registry: tcod.ecs.Registry,
) -> None:
    ai = entity.components[AI]

    if ai.state_turns_remaining <= 0:
        if ai.previous_ai is not None:
            ai.kind = ai.previous_ai
            ai.previous_ai = None
            ai.state = AIState.IDLE
        return

    ai.state_turns_remaining -= 1
    pos = entity.components[Position]

    dx = random.choice([-1, 0, 1])
    dy = random.choice([-1, 0, 1])
    if dx == 0 and dy == 0:
        return

    target_x = pos.x + dx
    target_y = pos.y + dy

    if game_map.is_walkable(target_x, target_y):
        target = _get_entity_at(registry, target_x, target_y)
        if target is not None:
            _attack(entity, target, registry)
        else:
            pos.x = target_x
            pos.y = target_y


def _process_fleeing_ai(
    entity: tcod.ecs.Entity,
    game_map: GameMap,
    player: tcod.ecs.Entity,
    registry: tcod.ecs.Registry,
) -> None:
    ai = entity.components[AI]
    fighter = entity.components.get(Fighter)
    if fighter is None:
        return

    if fighter.hp > fighter.max_hp * ai.flee_threshold:
        ai.kind = AIKind.HOSTILE
        ai.state = AIState.IDLE
        return

    ai.state = AIState.FLEEING
    pos = entity.components[Position]
    player_pos = player.components[Position]

    dx = pos.x - player_pos.x
    dy = pos.y - player_pos.y
    dx = max(-1, min(1, dx))
    dy = max(-1, min(1, dy))

    target_x = pos.x + dx
    target_y = pos.y + dy

    if game_map.is_walkable(target_x, target_y):
        for other in registry.Q.all_of(tags=["blocks_movement"]):
            other_pos = other.components[Position]
            if other_pos.x == target_x and other_pos.y == target_y:
                return
        pos.x = target_x
        pos.y = target_y


def _process_stationary_ai(
    entity: tcod.ecs.Entity,
    game_map: GameMap,
    player: tcod.ecs.Entity,
    registry: tcod.ecs.Registry,
) -> None:
    pos = entity.components[Position]
    player_pos = player.components[Position]

    if not game_map.visible[pos.y, pos.x]:
        return

    dx = player_pos.x - pos.x
    dy = player_pos.y - pos.y
    distance = abs(dx) + abs(dy)

    if distance <= 1:
        _attack(entity, player, registry)


def _wander(entity: tcod.ecs.Entity, game_map: GameMap) -> None:
    ai = entity.components[AI]
    pos = entity.components[Position]

    ai.state_turns_remaining -= 1
    if ai.state_turns_remaining <= 0:
        ai.wander_dx = random.choice([-1, 0, 1])
        ai.wander_dy = random.choice([-1, 0, 1])
        ai.state_turns_remaining = random.randint(2, 5)

    if ai.wander_dx == 0 and ai.wander_dy == 0:
        return

    target_x = pos.x + ai.wander_dx
    target_y = pos.y + ai.wander_dy

    if game_map.is_walkable(target_x, target_y):
        pos.x = target_x
        pos.y = target_y
    else:
        ai.state_turns_remaining = 0


def _alert_pack_members(
    entity: tcod.ecs.Entity,
    registry: tcod.ecs.Registry,
) -> None:
    ai = entity.components[AI]
    if not ai.alert_allies or not ai.pack_id:
        return

    pos = entity.components[Position]
    alert_radius = 8

    for other in registry.Q.all_of(tags=["enemy"]):
        other_ai = other.components.get(AI)
        if other_ai is None or other_ai.pack_id != ai.pack_id:
            continue
        if other_ai.state in (AIState.CHASING, AIState.ATTACKING):
            continue

        other_pos = other.components[Position]
        dx = other_pos.x - pos.x
        dy = other_pos.y - pos.y
        if abs(dx) + abs(dy) <= alert_radius:
            other_ai.state = AIState.CHASING


def _attack(
    attacker: tcod.ecs.Entity,
    defender: tcod.ecs.Entity,
    registry: tcod.ecs.Registry,
) -> None:
    attacker_fighter = attacker.components.get(Fighter)
    defender_fighter = defender.components.get(Fighter)
    if attacker_fighter is None or defender_fighter is None:
        return

    damage = max(1, attacker_fighter.power - defender_fighter.defense)
    defender_fighter.hp -= damage

    attacker_name = attacker.components[Name].name
    defender_name = defender.components[Name].name

    if "player" in defender.tags:
        message = f"The {attacker_name} attacks you for {damage} hit points."
    elif "player" in attacker.tags:
        message = f"You attack the {defender_name} for {damage} hit points."
    else:
        message = (
            f"The {attacker_name} attacks the {defender_name} "
            f"for {damage} hit points."
        )

    _add_message(registry, message)

    if defender_fighter.hp <= 0:
        _handle_death(defender, registry)


def _handle_death(entity: tcod.ecs.Entity, registry: tcod.ecs.Registry) -> None:
    name = entity.components[Name].name

    if "player" in entity.tags:
        _add_message(registry, "You have died!")
        entity.tags.add("dead")
        return

    _add_message(registry, f"The {name} is dead!")
    entity.tags.discard("blocks_movement")
    entity.tags.discard("enemy")
    entity.tags.add("dead")


def _get_entity_at(
    registry: tcod.ecs.Registry, x: int, y: int
) -> tcod.ecs.Entity | None:
    for entity in registry.Q.all_of(tags=["blocks_movement"]):
        pos = entity.components[Position]
        if pos.x == x and pos.y == y:
            return entity
    return None


def _add_message(registry: tcod.ecs.Registry, message: str) -> None:
    world = registry[None]
    log = world.components.get("MessageLog")
    if log is not None:
        log.messages.append(message)
```

The system is approximately 250 lines. Each behavior is a small, focused function. The dispatch logic in `process_ai_turns` is a flat if-elif chain---no inheritance, no polymorphism, no design patterns beyond simple function dispatch. This is intentional. The system is easy to read, easy to modify, and easy to debug.

## Exercises

**Exercise 1: Ranged AI**

Implement a ranged AI behavior. Create an `AIKind.RANGED` behavior where the enemy attacks from a distance using a bow or magic bolt. The enemy should maintain a preferred distance of 3-5 tiles from the player. If the player is within melee range, the enemy retreats. If the player is beyond preferred range, the enemy advances. If the player is at preferred range, the enemy attacks. Create a `RangedAttack` action that reduces the defender's hp without requiring adjacency. Place ranged enemies in the game and observe how they change combat dynamics compared to melee-only enemies.

**Exercise 2: Berserker AI**

Create a berserker AI that grows stronger as its hp drops. Add a `berserker` boolean field to the AI component. When `berserker` is True, the entity gains power equal to `max_hp - hp`---the more damaged it is, the harder it hits. A berserker orc with 15 max_hp and 5 current hp would have its effective power increased by 10. Display the berserker rage as a color shift: the entity becomes progressively redder as it takes damage. This creates a high-risk target that the player must kill quickly before it becomes too dangerous.

**Exercise 3: Item-Using AI**

Implement an AI that uses items from an inventory. Give certain enemies an `Inventory` component and a `"uses_items"` tag. Each turn, the AI checks whether it should use an item: drink a healing potion when hp is below 50%, throw a bomb when the player is 3 tiles away, or read a scroll of teleportation when cornered. The AI evaluates available items, picks the best one for the current situation, and uses it. This requires extending the item use system to work with non-player entities, which exercises the separation between item effects and the inventory that holds them.

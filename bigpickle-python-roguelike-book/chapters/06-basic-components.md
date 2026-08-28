# Chapter 6: Building the Component Library

## Designing Components

In the previous chapters, we established the ECS architecture and set up our project. Now we need the actual data that makes up our game entities. Every enemy, item, trap, door, and staircase in the game is described by a combination of components. The systems we build in later chapters---movement, combat, AI, inventory management, field of view---all operate on these components. If the components are well-designed, the systems write themselves. If the components are poorly designed, every system becomes a struggle.

This chapter establishes the core component types that every system in the rest of the book will depend on. Getting these right is worth the effort. They are the vocabulary of our game. Every interaction, every mechanic, every system will express itself through these data structures.

The rules for component design are simple:

**Components are pure data.** A component holds values. It does not contain methods, does not perform calculations, and does not call other functions. A `Position` component stores `x` and `y`. A `Fighter` component stores `hp`, `max_hp`, `power`, and `defense`. Any logic that operates on these values lives in systems, not in the components themselves.

**Each component represents a single concern.** A `Position` component describes where an entity is in the world. It does not also describe how the entity looks. That is a separate `Renderable` component. This separation means you can query for every entity with a position without accidentally including entities that only have visual data but no spatial representation.

**Think of components as columns in a database table.** Each entity is a row. Each component type is a column. An entity with `Position` and `Fighter` components is like a row that has values in the "position" and "fighter" columns but is null in the "inventory" and "AI" columns. Queries are SQL-like: "give me every row that has non-null values in the position and fighter columns."

**Group related components into modules.** We will not put every component in a single file. Instead, we organize components by category: physical components in one module, combat components in another, item components in a third. This keeps files small, makes imports explicit, and helps you find what you need when building a new system.

## Physical Components

Physical components describe an entity's presence in the world: where it is, how it looks, and whether it blocks other entities.

```python
# src/components/physical.py

from __future__ import annotations

import attrs


@attrs.define
class Position:
    """A 2D position in the game world."""

    x: int = 0
    y: int = 0


@attrs.define
class Renderable:
    """How an entity appears on screen."""

    char: str = "?"
    fg: tuple[int, int, int] = (255, 255, 255)
    render_order: int = 0  # Lower values render first (behind higher values)
```

`Position` is self-explanatory. Every entity that exists on the game map has one. The coordinates are in tile space: `x=0, y=0` is the top-left corner of the map. Positions are always integers because the game is tile-based---there are no sub-tile positions.

When an entity moves, a system updates its `Position` component directly. There is no animation or interpolation at the component level. If we later add smooth movement animation, it will be a rendering concern, not a component concern. The component stores the destination, and the renderer interpolates the visual representation between frames.

`Renderable` controls the visual representation. The `char` field is a single character from the tileset. The `fg` tuple is an RGB color. The `render_order` field determines draw order when multiple entities occupy the same tile. Items render at order 0, actors at order 1, the player at order 2. This ensures the player always appears on top of items and enemies on the same tile.

We use `render_order` as an integer rather than an enum because it gives us fine-grained control. If we later add a new entity type that should render between items and actors, we just assign it order 0 or 1 as needed. Enums would require modifying the enum definition every time we add a new render layer.

These two components---`Position` and `Renderable`---are the minimum needed for an entity to appear on the game map. An entity without a `Position` exists only in the registry, not in the world. An entity without a `Renderable` exists in the world but is invisible. Most entities have both.

## Identity Components

Identity components describe what an entity is and provide descriptive text for the player.

```python
# src/components/identity.py

from __future__ import annotations

import attrs


@attrs.define
class Name:
    """The display name of an entity."""

    name: str = "Unknown"


@attrs.define
class Description:
    """A text description shown to the player on inspection."""

    text: str = ""
```

`Name` is used in the message log. When the player attacks a goblin, the log says "You attack the goblin." When the player picks up a sword, the log says "You pick up the longsword." Every entity that the player can interact with should have a `Name` component.

`Description` is used for the examine or look command. It holds longer text that describes the entity in detail. A healing potion might have the description "A swirling red liquid that restores 20 hit points when consumed." Not every entity needs a description, but every entity that the player might want to inspect should have one.

These two components could be a single component with both fields, but separating them keeps things clean. The message log needs names constantly. Descriptions are accessed rarely. Separating them means we can query for entities with names without pulling description data into memory for entities that do not need it.

## Combat Components

Combat components describe an entity's ability to fight and its progress through the game.

```python
# src/components/combat.py

from __future__ import annotations

import attrs


@attrs.define
class Fighter:
    """Combat statistics for an entity that can fight."""

    hp: int = 10
    max_hp: int = 10
    power: int = 3
    defense: int = 0


@attrs.define
class XP:
    """Experience points and level tracking."""

    current: int = 0
    level: int = 1
    xp_to_next: int = 100
```

`Fighter` is the core combat component. Every entity that can deal or receive damage has one. The fields are straightforward:

- `hp` -- Current hit points. When this reaches zero, the entity dies.
- `max_hp` -- The upper bound for hp. Healing effects restore hp up to this value.
- `power` -- Base damage dealt in melee combat. Modified by weapon bonuses.
- `defense` -- Damage reduction. An attack dealing 10 damage to an entity with defense 3 deals 7 damage.

Notice that `hp` and `max_hp` are separate fields rather than having only `hp` and deriving max from somewhere else. This is deliberate. Some effects temporarily raise or lower maximum hp (a berserk rage might increase max_hp by 10 and heal the difference). Keeping them separate makes these effects straightforward to implement.

The combat system uses `power` and `defense` to calculate damage in a simple formula: `damage = max(1, attacker.power - defender.defense)`. This means a fighter with power 5 attacking a fighter with defense 3 deals 2 damage. The minimum of 1 ensures that combat always makes progress---even heavily armored entities take at least 1 damage per hit. More complex formulas can be layered on later by systems that check equipment, status effects, and other factors, but the base calculation lives in the combat system, not in the component.

`XP` tracks progression. Only the player entity needs this component, but we define it here so that the level-up system can query for it generically. The fields are:

- `current` -- Accumulated experience points.
- `level` -- The entity's current level. Starts at 1.
- `xp_to_next` -- The amount of XP needed to reach the next level. This value increases as the level rises, creating a curve where early levels come quickly and later levels require significantly more effort.

## AI Components

AI components describe an entity's autonomous behavior.

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


@attrs.define
class AI:
    """Marks an entity as having autonomous behavior."""

    kind: AIKind = AIKind.HOSTILE
    previous_position: tuple[int, int] | None = None
```

`AIKind` is an enum that selects between behavior patterns. We start with three kinds:

- `HOSTILE` -- The default. The entity chases the player and attacks when adjacent. This covers goblins, orcs, dragons, and most enemies.
- `CONFUSED` -- The entity moves randomly for a limited duration. Used when a confusion spell or effect is applied. The AI system ignores the player and picks random valid directions.
- `FLEEING` -- The entity moves away from the player. Used when an entity's hp drops below a threshold, creating cowardly enemies that run when wounded.

The `previous_position` field stores where the entity was before its current turn. This is used by the confused AI to avoid backtracking. A confused entity that moved left last turn should not immediately move right this turn. By tracking the previous position, the AI can filter out the backtrack direction and make movement feel less jittery.

We use an enum for `AIKind` rather than string constants because enums are type-safe. If someone misspells `"hostile"` as `"hostlie"`, a string constant fails silently at runtime. An enum catches the mistake immediately.

## Item Components

Item components describe entities that can be picked up, carried, and used.

```python
# src/components/items.py

from __future__ import annotations

import attrs


@attrs.define
class Item:
    """Marks an entity as a pickupable item."""

    name: str = ""
    description: str = ""
    use_function: str = ""  # Will become richer in later chapters


@attrs.define
class Inventory:
    """A container for carrying items."""

    items: list = attrs.Factory(list)
    capacity: int = 10


@attrs.define
class Equipment:
    """Tracks what an entity has equipped in each slot."""

    slots: dict[str, object] = attrs.Factory(dict)
```

`Item` marks an entity as something the player can pick up. The `use_function` field starts as a string identifier. Later, when we build the consumable system, this will map to actual game effects. For now, it is a placeholder that tells us what happens when the item is used: `"heal"` for healing potions, `"fireball"` for fireball scrolls, and so on.

`Inventory` is a container that holds item entities. The `items` field is a list of entity references. The `capacity` field limits how many items can be carried. When the player tries to pick up an item and the inventory is full, the system rejects the pickup and displays a message.

`Equipment` tracks what is currently worn or wielded. The `slots` dictionary maps slot names to item entities. A typical configuration might look like `{"weapon": sword_entity, "armor": chainmail_entity, "shield": shield_entity}`. An empty slot has no entry in the dictionary rather than storing `None`, which keeps the data compact.

## Tags for Behavior Flags

Not every piece of entity state needs a component. Boolean flags---properties that are either true or false---are better represented as tags. Tags are lightweight string markers with no associated data.

We use the following tags throughout the game:

**`"blocks_movement"`** -- The entity occupies its tile and prevents other entities from moving there. Walls, closed doors, and most actors have this tag. Items and open doors do not.

**`"blocks_fov"`** -- The entity blocks line of sight. This is separate from blocking movement because some entities block vision but not movement (a column of smoke, for example) and some block movement but not vision (a low fence). Walls and closed doors block both. Open doors block vision but not movement.

**`"player"`** -- Marks the player entity. Only one entity in the game should have this tag. Systems use it to identify the player without querying by entity key.

**`"enemy"`** -- Marks hostile entities. The AI system queries for entities with this tag plus an `AI` component. The combat system uses it to identify valid attack targets.

**`"item"`** -- Marks pickupable entities. The inventory system queries for this tag when the player attempts to pick up what is on the ground.

**`"staircase"`** -- Marks level transition entities. When the player moves onto a tile with a staircase entity and presses the descend key, the game generates a new level and moves the player down.

These tags are the behavioral vocabulary of the game. When you add a new entity type, you decide which tags apply. A new door entity might get `"blocks_movement"` when closed and lose it when opened. A new trap might get neither tag because traps are invisible until triggered. The tags describe what the entity does, not what it is---this distinction is important because the same entity can change behavior as the game state evolves.

```python
# Tags in use

# A goblin entity
goblin.components[Position] = Position(x=5, y=3)
goblin.components[Renderable] = Renderable(char="g", fg=(0, 255, 0))
goblin.components[Name] = Name(name="goblin")
goblin.components[Fighter] = Fighter(hp=10, max_hp=10, power=3, defense=0)
goblin.components[AI] = AI(kind=AIKind.HOSTILE)
goblin.tags.add("blocks_movement")
goblin.tags.add("enemy")

# A healing potion
potion.components[Position] = Position(x=8, y=12)
potion.components[Renderable] = Renderable(char="!", fg=(128, 0, 255))
potion.components[Name] = Name(name="healing potion")
potion.components[Item] = Item(name="healing potion", use_function="heal")
potion.tags.add("item")
```

Notice that we do not have a `blocks_movement` component that holds a boolean value. A tag achieves the same result with less overhead. Tags are strings, so they are easy to inspect during debugging. Adding or removing a tag is a single operation. There is no need to instantiate a component class just to set a flag to `True`.

## Organizing Components into Modules

Our component library is organized into modules by category. Each module contains related components and nothing else.

```
src/components/
    __init__.py
    physical.py
    identity.py
    combat.py
    ai.py
    items.py
```

The `__init__.py` re-exports every component so that other parts of the codebase can import from the components package directly:

```python
# src/components/__init__.py

from src.components.ai import AI, AIKind
from src.components.combat import Fighter, XP
from src.components.identity import Description, Name
from src.components.items import Equipment, Inventory, Item
from src.components.physical import Position, Renderable

__all__ = [
    "AI",
    "AIKind",
    "Description",
    "Equipment",
    "Fighter",
    "Inventory",
    "Item",
    "Name",
    "Position",
    "Renderable",
    "XP",
]
```

This pattern means systems import what they need from a single location:

```python
from src.components import Position, Fighter, AI

# Not this:
# from src.components.physical import Position
# from src.components.combat import Fighter
# from src.components.ai import AI
```

The individual module files still exist for organization and readability. The `__init__.py` just provides a convenient facade. If a module grows large, you can split it further without changing import statements in the rest of the codebase.

This organizational pattern scales well. As the game grows, you might add `status.py` for status effect components, `doors.py` for door-related components, or `lighting.py` for light source components. Each new module gets added to the `__init__.py` re-exports, and existing imports remain unchanged.

One final note on module organization: keep the modules flat. Do not nest `components/physical/position.py` inside `components/physical/`. A roguelike component library rarely exceeds twenty or thirty component types, and flat modules are easier to navigate. If a single module file exceeds a few hundred lines, consider splitting it---but do not split prematurely.

## Component Design Principles

These principles have emerged from building and maintaining games with ECS. Follow them unless you have a specific reason not to.

**Keep components small and focused.** A component should describe one thing. If you find yourself adding fields to a component to cover unrelated concerns, split it. A `Position` component should not also contain `hp`. Those are separate concerns belonging to separate components.

**Use attrs for all components.** The `@attrs.define` decorator gives us `__init__`, `__repr__`, `__eq__`, and other methods for free. It also provides clear, explicit field declarations with defaults. We use `frozen=False` (the default) because components are mutable---systems modify component values during gameplay.

**Avoid storing complex logic in components.** Components are data. If a component needs a method to calculate something, that calculation probably belongs in a system. The one exception is simple computed properties that derive from the component's own fields, and even those should be used sparingly.

**Use tags for boolean flags instead of bool components.** A component like `IsAlive(alive=True)` adds overhead for no benefit. The tag `"alive"` achieves the same thing with less ceremony. Reserve components for data that has multiple fields or varies in value.

**Named components for multiple instances of the same type.** If an entity needs two components of the same class---for example, two `Inventory` components for weapons and potions---use named components with the `("type", "name")` tuple key. This was covered in Chapter 2 and will appear frequently as we build the equipment and inventory systems.

**Default values matter.** Every field in a component should have a sensible default. This lets you create components with minimal configuration:

```python
# Position defaults to (0, 0) -- usable as-is
pos = Position()

# Fighter with custom stats
fighter = Fighter(hp=30, max_hp=30, power=5, defense=2)
```

Good defaults reduce boilerplate in factory functions and make it easy to create test entities with minimal setup.

**Prefer composition over inheritance.** If you find yourself wanting a component that is a superset of two existing components, do not create a new component that inherits from both. Instead, attach both components to the same entity. A `BossEnemy` is not a subclass of `Enemy`---it is an entity with `Position`, `Renderable`, `Name`, `Fighter`, `AI`, and `BossStats` components. The `BossStats` component adds whatever additional data a boss needs without modifying the existing components.

**Keep components serializable.** Since we use pickle for save and load (Chapter 16), every component must be picklable. This means no lambdas, no open file handles, no references to non-serializable objects. Standard attrs classes with primitive field types are always safe. This constraint is easy to satisfy if you follow the rule of keeping components as pure data.

## Complete Example: Building Entities

Here is how all these components come together when creating game entities. These examples show the patterns we will use throughout the book.

```python
# Creating a player entity

def create_player(registry: tcod.ecs.Registry) -> tcod.ecs.Entity:
    """Create the player entity with all required components."""
    player = registry.new_entity(key="player")

    player.components[Position] = Position(x=0, y=0)
    player.components[Renderable] = Renderable(char="@", fg=(255, 255, 255), render_order=2)
    player.components[Name] = Name(name="Player")
    player.components[Fighter] = Fighter(hp=30, max_hp=30, power=5, defense=2)
    player.components[XP] = XP(current=0, level=1, xp_to_next=100)
    player.components[Inventory] = Inventory(items=[], capacity=20)
    player.components[Equipment] = Equipment(slots={})

    player.tags.add("player")
    player.tags.add("blocks_movement")

    return player
```

```python
# Creating an enemy entity

def create_goblin(registry: tcod.ecs.Registry, x: int, y: int) -> tcod.ecs.Entity:
    """Create a goblin enemy at the given position."""
    goblin = registry.new_entity(key=f"goblin_{x}_{y}")

    goblin.components[Position] = Position(x=x, y=y)
    goblin.components[Renderable] = Renderable(char="g", fg=(0, 255, 0), render_order=1)
    goblin.components[Name] = Name(name="goblin")
    goblin.components[Description] = Description(text="A small, green-skinned humanoid with a rusty dagger.")
    goblin.components[Fighter] = Fighter(hp=10, max_hp=10, power=3, defense=0)
    goblin.components[AI] = AI(kind=AIKind.HOSTILE)

    goblin.tags.add("enemy")
    goblin.tags.add("blocks_movement")

    return goblin
```

```python
# Creating an item entity

def create_healing_potion(
    registry: tcod.ecs.Registry, x: int, y: int
) -> tcod.ecs.Entity:
    """Create a healing potion at the given position."""
    potion = registry.new_entity(key=f"potion_{x}_{y}")

    potion.components[Position] = Position(x=x, y=y)
    potion.components[Renderable] = Renderable(char="!", fg=(128, 0, 255), render_order=0)
    potion.components[Name] = Name(name="healing potion")
    potion.components[Item] = Item(name="healing potion", use_function="heal")

    potion.tags.add("item")

    return potion
```

Notice the render order values. Items are 0, enemies are 1, the player is 2. This ensures the player always appears on top when multiple entities share a tile. The healing potion renders first (behind), the goblin renders second, and the player renders last (in front).

Also notice that the goblin has both a `Name` and a `Description` component, while the healing potion has only a `Name`. Descriptions are optional---only entities that benefit from an examine screen get one. The player does not need a description because the player already knows what they are.

Here are two more entity types to round out the picture:

```python
# Creating an orc enemy (stronger than a goblin)

def create_orc(registry: tcod.ecs.Registry, x: int, y: int) -> tcod.ecs.Entity:
    """Create an orc enemy at the given position."""
    orc = registry.new_entity(key=f"orc_{x}_{y}")

    orc.components[Position] = Position(x=x, y=y)
    orc.components[Renderable] = Renderable(char="o", fg=(63, 127, 63), render_order=1)
    orc.components[Name] = Name(name="orc")
    orc.components[Description] = Description(text="A hulking brute with tusks and a heavy axe.")
    orc.components[Fighter] = Fighter(hp=20, max_hp=20, power=6, defense=2)
    orc.components[AI] = AI(kind=AIKind.HOSTILE)

    orc.tags.add("enemy")
    orc.tags.add("blocks_movement")

    return orc


# Creating a sword item

def create_sword(registry: tcod.ecs.Registry, x: int, y: int) -> tcod.ecs.Entity:
    """Create a longsword at the given position."""
    sword = registry.new_entity(key=f"sword_{x}_{y}")

    sword.components[Position] = Position(x=x, y=y)
    sword.components[Renderable] = Renderable(char="/", fg=(192, 192, 192), render_order=0)
    sword.components[Name] = Name(name="longsword")
    sword.components[Description] = Description(text="A straight double-edged blade. Reliable and sharp.")
    sword.components[Item] = Item(name="longsword", use_function="equip")

    sword.tags.add("item")

    return sword
```

The pattern is consistent. Every entity creation function follows the same structure: create the entity, attach components, add tags, return it. The factory functions in `src/factories/` will wrap these patterns and add parameterization for variation in stats, positions, and properties.

## Querying Components in Systems

With the component library established, here is a preview of how systems will use these components. This is not a complete system implementation---just a taste of the query patterns that appear in later chapters.

```python
# A render system that draws all visible entities

def render_entities(
    registry: tcod.ecs.Registry,
    console: tcod.console.Console,
) -> None:
    """Draw every entity with Position and Renderable to the console."""
    for entity, (pos, rend) in registry.Q[Position, Renderable].results:
        console.print(x=pos.x, y=pos.y, string=rend.char, fg=rend.fg)
```

```python
# A movement system that processes entity actions

def process_movement(
    registry: tcod.ecs.Registry,
    dx: int,
    dy: int,
) -> None:
    """Move the player by (dx, dy) if the destination is not blocked."""
    for entity, (pos,) in registry.Q[Position].results:
        if "player" not in entity.tags:
            continue

        new_x = pos.x + dx
        new_y = pos.y + dy

        # Check if any entity blocks the destination
        blocked = False
        for other, (other_pos,) in registry.Q[Position].results:
            if other_pos.x == new_x and other_pos.y == new_y:
                if "blocks_movement" in other.tags:
                    blocked = True
                    break

        if not blocked:
            pos.x = new_x
            pos.y = new_y
```

These systems are intentionally simple. They demonstrate the core pattern: query for entities with specific components, filter by tags if needed, and process the results. Every system in the book follows this pattern. The complexity lies in the logic, not the structure.

Here is one more example---an AI system that processes enemy turns:

```python
# An AI system that makes enemies take actions

def process_ai(
    registry: tcod.ecs.Registry,
    player_pos: Position,
) -> None:
    """Have all hostile entities with AI take their turn."""
    for entity, (pos, ai) in registry.Q[Position, AI].results:
        if "enemy" not in entity.tags:
            continue

        if ai.kind == AIKind.HOSTILE:
            # Chase the player: move one tile closer
            dx = 0
            dy = 0
            if pos.x < player_pos.x:
                dx = 1
            elif pos.x > player_pos.x:
                dx = -1
            if pos.y < player_pos.y:
                dy = 1
            elif pos.y > player_pos.y:
                dy = -1

            # In a real system, we would check for collisions here
            # and handle melee attacks if adjacent
            pos.x += dx
            pos.y += dy

        elif ai.kind == AIKind.CONFUSED:
            # Move in a random direction
            import random
            dx = random.choice([-1, 0, 1])
            dy = random.choice([-1, 0, 1])
            pos.x += dx
            pos.y += dy
```

This system demonstrates the same query-filter-process pattern. It queries for entities with `Position` and `AI`, filters by the `"enemy"` tag, then branches on the `AIKind` enum to determine behavior. This is the structure that every AI behavior in the game will follow.

## Exercises

**Exercise 1: Add a Level Component**

Create a `Level` component that tracks the current dungeon floor number. It should have a `floor` field (default 1) and a `max_floor` field (default 26, matching the 26 floors of a traditional roguelike). Attach it to the player entity. Write a query that retrieves it and prints the current floor. Consider where this component belongs in the module structure---does it fit in an existing module, or does it warrant a new one?

**Exercise 2: Create a LightSource Component**

Design a `LightSource` component with a `radius` field (how far the light reaches, in tiles) and an `intensity` field (a brightness value from 0.0 to 1.0). Attach it to the player with radius 8 and intensity 1.0. Attach a weaker version to a torch item with radius 4 and intensity 0.6. Write a query that finds all entities with `Position` and `LightSource` and prints their positions and radii. What happens if you attach the `LightSource` to an entity without a `Position`? Why is that a problem, and how would you document it?

**Exercise 3: Design an Effect Component**

Design an `Effect` component that represents a buff or debuff applied to an entity. It should have fields for the effect type (a string like `"poison"`, `"burning"`, or `"haste"`), the remaining duration in turns, and a power value that the effect system will use for damage or stat modification. Attach a poison effect to a goblin with 5 turns remaining and power 2. Write a query that finds all entities with an `Effect` component and prints the effect type and remaining duration.

**Exercise 4: Component Comparison**

Review the component library in this chapter. For each component, write one sentence explaining why it exists and what system or user-facing feature depends on it. This exercise forces you to think about the purpose of each component. If you cannot explain why a component exists, it probably should not be one.

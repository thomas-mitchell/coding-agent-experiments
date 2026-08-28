# Chapter 2: Entity-Component-System Architecture

## Why Architecture Matters

Every game project starts with enthusiasm and momentum. The first few hours are magical: you spawn a player, render a map, and watch your character move across the screen. But somewhere around the third or fourth feature, the cracks begin to show. You want to add a door that blocks movement. You want items that can be picked up. You want enemies that chase the player. Each new feature interacts with every existing feature in ways you did not anticipate.

This is the moment where architecture matters.

Roguelikes are among the most architecturally demanding game genres. A typical roguelike needs to model hundreds of distinct entity types: players, monsters of varying abilities, items with different effects, terrain with special properties, traps, doors, projectiles, and status effects. These entities interact through dozens of systems: movement, combat, inventory management, field of view, pathfinding, and message logging. The combinatorial explosion of these interactions is staggering.

Poor architecture creates technical debt. You add a "paralyzed" status effect by placing a boolean flag on the actor class, then realize you need the same mechanism for "sleeping," "frozen," and "charmed." You copy the pattern four times. Later, when you want a generic status effect system, you discover that each status is hardcoded into different places throughout the codebase. Refactoring becomes dangerous because every change risks breaking something you cannot predict.

Good architecture does not eliminate complexity. It manages it. It gives you a consistent pattern for adding new features without rewriting existing code. It makes it natural to ask questions like "give me every entity that has both a Position and a Health component" and get a correct answer instantly.

## The Problem with Traditional OOP

Object-oriented programming seems like the natural fit for game development. A `Player` class inherits from `Actor`, which inherits from `Entity`. A `Sword` class inherits from `Weapon`, which inherits from `Item`. The hierarchy mirrors how we think about game objects.

This approach works until it does not. Let us examine why.

**Deep Inheritance Hierarchies**

Consider a basic entity hierarchy:

```python
class Entity:
    def __init__(self, x: int, y: int):
        self.x = x
        self.y = y

class Actor(Entity):
    def __init__(self, x: int, y: int, hp: int, power: int):
        super().__init__(x, y)
        self.hp = hp
        self.power = power

class Player(Actor):
    def __init__(self, x: int, y: int, hp: int, power: int, inventory: list):
        super().__init__(x, y, hp, power)
        self.inventory = inventory

class HostileActor(Actor):
    def __init__(self, x: int, y: int, hp: int, power: int, ai: AI):
        super().__init__(x, y, hp, power)
        self.ai = ai

class Goblin(HostileActor):
    def __init__(self, x: int, y: int):
        super().__init__(x, y, hp=10, power=3, ai=ChaseAI())
```

This is five classes deep, and we have not even modeled items, doors, traps, or any of the other dozens of entities a roguelike needs. Each new entity type requires another class. Every shared behavior must be pushed up the hierarchy or duplicated.

**The Diamond Problem**

Suppose you want a `DroppedItem` that is both an `Item` and sits at a `Position` on the map. You also want a `ThrownProjectile` that has physics behavior and deals damage. These entities need traits from multiple branches of your hierarchy. Python resolves this through MRO (Method Resolution Order), but the result is often unintuitive and fragile.

**God Classes**

As features accumulate, certain classes grow to accommodate every new requirement. The `Actor` class gains `is_paralyzed`, `is_sleeping`, `is_frozen`, `resistances`, `immunities`, `buffs`, `debuffs`. It becomes a god class that knows too much and does too little coherently. Every new status effect means adding another field to this class, another branch to every method that checks actor state, and another set of interactions to test.

**Composition as a Dismantled Hammer**

The OOP response to these problems is usually "favor composition over inheritance." This is good advice, but implementing composition manually in a traditional OOP style leads to boilerplate. You end up creating wrapper methods that delegate to contained objects, managing attachment and detachment manually, and writing custom serialization for every composed entity.

ECS takes this idea to its logical conclusion.

## Entities, Components, and Systems

The Entity-Component-System pattern separates the three concerns that OOP entangles:

**Entities** are unique identifiers. An entity is not an object with methods, state, and behavior. An entity is a key. It is an integer, a label, a way to group related data together. In tcod-ecs, an entity is a reference to a slot in a registry, identified by a hashable key.

```python
import tcod.ecs

registry = tcod.ecs.Registry()
player = registry.new_entity()  # This is an entity. Just an ID.
```

That is all an entity is. No methods, no `__init__`, no class definition. Just an identifier.

**Components** are pure data attached to entities. A component is an instance of a data class that describes one aspect of an entity. A `Position` component describes where an entity is. A `Health` component describes how much damage an entity can take. A `Renderable` component describes how an entity looks on screen.

```python
from attrs import define

@define
class Position:
    x: int = 0
    y: int = 0

@define
class Health:
    current: int = 10
    maximum: int = 10

# Attach components to the entity
player.components[Position] = Position(x=5, y=3)
player.components[Health] = Health(current=20, maximum=20)
```

Components have no methods. They do not contain logic. They are data containers. This is a deliberate and important constraint.

**Systems** are functions that process entities matching specific component queries. A movement system finds every entity with both a `Position` and a `Velocity` component and updates their positions. A combat system finds every entity with `Health` and `AttackPower` and processes damage.

```python
def movement_system(registry: tcod.ecs.Registry):
    """Process movement for all entities with Position and Velocity."""
    for entity, (pos, vel) in registry.Q[Position, Velocity].results:
        pos.x += vel.dx
        pos.y += vel.dy
        vel.dx = 0
        vel.dy = 0

def render_system(registry: tcod.ecs.Registry):
    """Render all entities with Position and Renderable."""
    for entity, (pos, rend) in registry.Q[Position, Renderable].results:
        console.print(x=pos.x, y=pos.y, string=rend.char, fg=rend.color)
```

Systems do not belong to any entity. They are standalone functions that operate on collections of entities. This separation means you can add new behavior by writing a new system without modifying any existing code.

## Introducing tcod-ecs

We will use `tcod-ecs`, a library included in the tcod ecosystem. It is written by the same author as tcod itself, and it is designed specifically for roguelike development. The library provides a registry, entity references, component storage, tag storage, relations, and a query system.

You do not need to build an ECS framework from scratch. The hard problems -- storage, indexing, query optimization -- are already solved. You can focus on designing components, writing systems, and building your game.

## The Registry

The registry is the central container for all entities, components, tags, and relations. Every ECS operation goes through the registry.

```python
import tcod.ecs

# Create a new registry
registry = tcod.ecs.Registry()

# Create entities
player = registry.new_entity()
goblin = registry.new_entity()
sword = registry.new_entity()

# Entities are hashable keys
print(player)  # EntityKey(1)
print(goblin)  # EntityKey(2)
```

You can also create entities with explicit string keys for easier debugging and serialization:

```python
# Use string keys for readability
player = registry.new_entity(key="player")
goblin = registry.new_entity(key="goblin_01")
dungeon_level_1 = registry.new_entity(key="level_1")

# Reference entities by their key
same_player = registry["player"]
assert player is same_player
```

Explicit keys are valuable for roguelikes. When you serialize your game state and reload it, you can reconstruct entity references by their keys rather than relying on integer IDs that change between sessions.

## Components

Components are stored on entities using type-based indexing. The type of the component class serves as the key.

```python
from attrs import define

@define
class Position:
    x: int = 0
    y: int = 0

@define
class Health:
    current: int = 10
    maximum: int = 10

@define
class Name:
    name: str = ""

# Attach components
player = registry.new_entity(key="player")
player.components[Position] = Position(x=10, y=5)
player.components[Health] = Health(current=30, maximum=30)
player.components[Name] = Name(name="Player")

# Retrieve components
pos = player.components[Position]
print(f"Player is at ({pos.x}, {pos.y})")

hp = player.components[Health]
print(f"Player has {hp.current}/{hp.maximum} HP")
```

Components must be classes. You cannot attach raw values directly. This constraint keeps the system type-safe and queryable.

**Using attrs for Components**

We use `@attrs.define` (or `@define` from attrs) to create component classes. This gives us concise syntax, automatic `__init__`, `__repr__`, `__eq__`, and other dunder methods for free.

```python
from attrs import define, field

@define
class Inventory:
    items: list = field(factory=list)
    capacity: int = 10

@define
class AI:
    behavior: str = "chase"
    alert_radius: int = 5

@define
class Renderable:
    char: str = "?"
    color: tuple[int, int, int] = (255, 255, 255)
    render_order: int = 0
```

The `field(factory=list)` syntax creates a new list for each instance rather than sharing a single mutable default across instances.

**Component Overwriting**

Assigning a component of the same type replaces the previous value:

```python
player.components[Health] = Health(current=30, maximum=30)
# Later, after healing
player.components[Health] = Health(current=50, maximum=50)
```

This is by design. An entity has at most one component of each type. If you need multiple values, create a component that holds them all.

## Tags

Tags are lightweight markers with no data. They are useful for flags and states that do not need associated information.

```python
# Add tags
player = registry.new_entity(key="player")
player.tags.add("alive")
player.tags.add("player_controlled")
player.tags.add("can_move")

# Check tags
print("alive" in player.tags)  # True
print("dead" in player.tags)   # False

# Remove tags
player.tags.discard("can_move")
```

Tags are strings. They are simple, fast, and easy to inspect during debugging. Use tags for boolean properties: alive, dead, paralyzed, sleeping, in_combat, visible, explored.

```python
# Common tag patterns
enemy.tags.add("alive")
enemy.tags.add("hostile")
enemy.tags.add("aware_of_player")

# Status effects as tags
enemy.tags.add("poisoned")
enemy.tags.add("slowed")

# Map state
tile.tags.add("explored")
tile.tags.add("visible")
tile.tags.add("blocked")
```

Tags integrate with queries, which we will cover shortly.

## Named Components

Sometimes you need multiple components of the same type on a single entity. Named components solve this by using a tuple of `(type, name)` as the storage key.

Consider an entity with equipment slots:

```python
@define
class EquipmentSlot:
    item: object = None
    slot_type: str = ""

# Store multiple equipment slots using named components
player.components[("slot", "head")] = EquipmentSlot(slot_type="head")
player.components[("slot", "body")] = EquipmentSlot(slot_type="body")
player.components[("slot", "weapon")] = EquipmentSlot(slot_type="weapon")
player.components[("slot", "off_hand")] = EquipmentSlot(slot_type="off_hand")

# Access a specific slot
weapon_slot = player.components[("slot", "weapon")]
```

Another common use case is multi-level inventories or categorized storage:

```python
# Multiple inventories by category
player.components[("inventory", "weapons")] = Inventory(capacity=5)
player.components[("inventory", "potions")] = Inventory(capacity=10)
player.components[("inventory", "scrolls")] = Inventory(capacity=10)
```

Named components are a powerful pattern. They let you attach multiple instances of the same data type to a single entity, distinguished by name.

## Relations

Relations connect entities to each other. They are essential for modeling ownership, membership, targeting, and other inter-entity associations.

**Relation Tags**

Relation tags associate a string tag with a target entity:

```python
player = registry.new_entity(key="player")
goblin = registry.new_entity(key="goblin")
sword = registry.new_entity(key="sword")

# The goblin is targeting the player
goblin.relation_tag["targeting"] = player

# The sword is owned by the player
sword.relation_tag["owned_by"] = player

# Query: what is the goblin targeting?
target = goblin.relation_tag["targeting"]
print(target)  # EntityKey(player)
```

**Relation Components**

Relation components attach data to a relationship between two entities:

```python
@define
class RelationData:
    value: int = 0
    label: str = ""

# The goblin has a "deal_damage" relation to the player with associated data
goblin.relation_components[DealDamage][player] = DealData(damage=5, type="slash")

# The player has an "inventory_contains" relation to the sword
player.relation_components[InventoryContains][sword] = InventoryData(slot="weapon")
```

Relations are particularly useful for modeling:

- **Ownership**: `entity.relation_tag["owned_by"] = owner`
- **Targeting**: `entity.relation_tag["targeting"] = target`
- **Equipment**: `entity.relation_components[Equipped][slot_entity] = EquipmentData(...)`
- **Spells**: `caster.relation_components[Casting][spell_entity] = CastData(power=10)`
- **Level structure**: `room.relation_tag["part_of"] = level_entity`

## Queries

Queries are how you find entities in the registry. The query API is the most important part of ECS in practice, because systems need to efficiently locate the entities they operate on.

**Basic Component Queries**

```python
# Find every entity that has both Position and Health
for entity, (pos, hp) in registry.Q[Position, Health].results:
    print(f"{entity} at ({pos.x}, {pos.y}) with {hp.current} HP")
```

The `Q` attribute on the registry creates a query builder. Indexing it with component types returns a query that matches entities possessing all specified components. The `results` property yields tuples of `(entity, (component_values...))`.

**Tag Filtering**

```python
# Find all alive entities with Position and Health
for entity, (pos, hp) in registry.Q[Position, Health].results:
    if "alive" in entity.tags:
        pos.x += 1  # Move all living entities right
```

You can also filter by tags in the query itself:

```python
# Using all_of to require tags
for entity in registry.Q.all_of(tags=["alive", "hostile"]):
    # Process hostile alive entities
    process_hostile(entity)

# Using none_of to exclude tags
for entity in registry.Q.none_of(tags=["dead", "hidden"]):
    # Process visible, living entities
    process_visible(entity)
```

**Combining Component and Tag Queries**

```python
# Alive entities with both Position and AI
for entity, (pos, ai) in registry.Q[Position, AI].results:
    if "alive" in entity.tags:
        update_ai(entity, pos, ai)
```

**Named Component Queries**

```python
# Query named components
for entity, (slot,) in registry.Q[("slot", "weapon")].results:
    if slot.item is not None:
        print(f"{entity} has a weapon equipped")
```

**Filtering with Predicates**

The query system supports filtering to narrow results:

```python
# Find all entities with Health below their maximum (damaged entities)
for entity, (hp,) in registry.Q[Health].results:
    if hp.current < hp.maximum:
        print(f"{entity} is damaged: {hp.current}/{hp.maximum}")
```

**Query Caching**

Queries in tcod-ecs are efficient. They use the component storage's internal indices to avoid scanning every entity in the registry. When you write `registry.Q[Position, Health]`, the library identifies the smallest component set to iterate over and uses that as the starting point.

## Why ECS for a Roguelike

The ECS pattern offers specific advantages for roguelike development:

**Flexible Entity Composition**

In a traditional OOP roguelike, adding a new entity type means creating a new class. In ECS, you compose entities from components. A new entity is just a new combination of existing components:

```python
# A new type of entity: a healing potion
potion = registry.new_entity(key="healing_potion")
potion.components[Position] = Position(x=3, y=7)
potion.components[Name] = Name(name="Healing Potion")
potion.components[Renderable] = Renderable(char="!", color=(128, 0, 255))
potion.components[Consumable] = Consumable(effect="heal", power=10)
potion.tags.add("item")
potion.tags.add("pickupable")
```

No new class. No new inheritance hierarchy. Just new data combinations.

**Easy Feature Addition**

When you want to add a new feature -- say, a poison system -- you do not modify existing entity classes. You create a new `Poison` component, attach it to entities that are poisoned, and write a `poison_system` function that processes it. The existing movement system, rendering system, and combat system continue to work unchanged.

**Serialization**

ECS state is fundamentally data. Components are data classes. Tags are strings. Relations are dictionaries of entity references. The entire registry can be serialized with Python's `pickle` module:

```python
import pickle

# Save game state
with open("save.pkl", "wb") as f:
    pickle.dump(registry, f)

# Load game state
with open("save.pkl", "rb") as f:
    registry = pickle.load(f)
```

This is one of the reasons we chose tcod-ecs. Serialization works out of the box with minimal configuration.

**Performance**

Systems iterate over narrow queries rather than checking every entity. If only fifteen entities have both `Position` and `AI`, the AI system processes only those fifteen entities, not every entity in the game. For a roguelike with hundreds of entities, this selective processing keeps frame times low.

**Debuggability**

When something goes wrong, you can inspect any entity's complete state by examining its components and tags. There is no hidden state buried in method calls or overridden behavior. The data is right there.

## Exercises

**Exercise 1: Build an Entity**

Create a registry and define five component classes: `Position`, `Health`, `Name`, `Renderable`, and `AI`. Create three entities (a player, a goblin, and a dragon) with different combinations of these components. Attach appropriate tags to mark which entities are alive, hostile, or player-controlled.

**Exercise 2: Write a Query**

Using the registry from Exercise 1, write a query that finds all entities with both `Position` and `Health` that are tagged as "alive." Print each entity's name and health.

**Exercise 3: Model Equipment**

Use named components to model a player entity with four equipment slots: head, body, weapon, and off_hand. Write a query that finds the player and prints the item in each slot. Create a second entity representing a sword and assign it to the player's weapon slot using a relation component.

These exercises reinforce the core ECS concepts. Take time to experiment. Change component values, add new tags, write different queries. The more fluently you work with the ECS API, the easier the rest of this book will be.

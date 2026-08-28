# Chapter 11: Entity Factories

By the end of Chapter 10, the game has a dungeon generator that produces positions and a `spawn_entities` function that turns those positions into ECS entities. The function works, but it has a problem: every entity is built inline with a long sequence of component assignments. A single enemy entity requires six or seven lines of component setup. An item requires four or five. As the game grows and we add more entity types, this inline construction becomes a liability.

This chapter solves that problem with entity factories: dedicated functions and data structures that encapsulate the creation of each entity type. A factory knows everything about what makes an orc an orc, or what makes a healing potion a healing potion. The game code calls the factory, passes a position, and gets back a fully configured entity. This separation between definition and placement makes the codebase easier to extend, easier to balance, and easier to debug.

## The Problem with Inline Entity Creation

Here is what the `spawn_entities` function from Chapter 9 looks like when we expand it to handle multiple entity types:

```python
def spawn_entities(
    registry: tcod.ecs.Registry,
    dungeon: DungeonLayout,
    dungeon_level: int,
) -> None:
    for x, y in dungeon.enemy_positions:
        choice = random.choice(["kobold", "orc", "troll"])

        if choice == "kobold":
            entity = registry.new_entity()
            entity.components |= {
                Position: Position(x=x, y=y),
                Renderable: Renderable(char="k", fg=(255, 0, 0)),
                Name: Name(name="kobold"),
                Fighter: Fighter(hp=8, max_hp=8, power=3, defense=0),
                AI: AI(kind=AIKind.HOSTILE),
            }
            entity.tags |= {"enemy", "blocks_movement"}

        elif choice == "orc":
            entity = registry.new_entity()
            entity.components |= {
                Position: Position(x=x, y=y),
                Renderable: Renderable(char="o", fg=(63, 127, 63)),
                Name: Name(name="orc"),
                Fighter: Fighter(hp=15, max_hp=15, power=5, defense=2),
                AI: AI(kind=AIKind.HOSTILE),
            }
            entity.tags |= {"enemy", "blocks_movement"}

        elif choice == "troll":
            entity = registry.new_entity()
            entity.components |= {
                Position: Position(x=x, y=y),
                Renderable: Renderable(char="T", fg=(0, 128, 0)),
                Name: Name(name="troll"),
                Fighter: Fighter(hp=25, max_hp=25, power=8, defense=4),
                AI: AI(kind=AIKind.HOSTILE),
            }
            entity.tags |= {"enemy", "blocks_movement"}
```

Three enemy types, and the code is already 30 lines of nearly identical blocks. Each block follows the same pattern: create entity, set Position, set Renderable, set Name, set Fighter, set AI, add tags. The only things that change are the literal values---the character, the color, the name, the stats.

This repetition creates several concrete problems:

**Duplication is error-prone.** If you decide that all enemies should have a `Description` component, you must remember to add it to every branch. Miss one and that enemy type silently lacks descriptions. The inconsistency will not surface until you try to examine that enemy in-game.

**Modifying entities requires touching spawn code.** Changing an orc's stats means editing the `spawn_entities` function. That function is supposed to be about placement, not definition. Mixing these concerns means every stat change risks breaking the placement logic.

**Adding new entity types inflates the function.** Each new enemy adds another `elif` branch. The function grows linearly with the number of entity types. Eventually it becomes so long that scrolling through it to find a specific enemy type is tedious.

**Testing is difficult.** To verify that an orc has the right stats, you must call `spawn_entities` with a dungeon layout that includes orc positions. You cannot test an orc in isolation.

The solution is to extract entity creation into its own layer: factory functions that define entity blueprints independently of where they are placed.

## Factory Functions

A factory function is a function that creates and returns a fully configured entity. It takes a registry and the variable parameters---typically position---and returns a new entity with all the right components and tags.

The simplest factory functions follow the same structure as the inline creation code, but isolated into a single, focused function:

```python
def create_orc(registry: tcod.ecs.Registry, x: int, y: int) -> tcod.ecs.Entity:
    """Create an orc entity at the given position."""
    entity = registry.new_entity()
    entity.components |= {
        Position: Position(x=x, y=y),
        Renderable: Renderable(char="o", fg=(63, 127, 63), render_order=1),
        Name: Name(name="orc"),
        Description: Description(text="A hulking brute with tusks and a heavy axe."),
        Fighter: Fighter(hp=15, max_hp=15, power=5, defense=2),
        AI: AI(kind=AIKind.HOSTILE),
    }
    entity.tags |= {"enemy", "blocks_movement"}
    return entity
```

The function does one thing: it creates an orc. Everything you need to know about an orc---its character, color, name, description, combat stats, and behavior---is defined in this single function. To change the orc's stats, you edit one function. To add a new component, you add one line. To test that an orc is correct, you call this function with a mock registry and assert on the returned entity.

Here is the same pattern applied to other enemy types:

```python
def create_kobold(registry: tcod.ecs.Registry, x: int, y: int) -> tcod.ecs.Entity:
    """Create a kobold entity at the given position."""
    entity = registry.new_entity()
    entity.components |= {
        Position: Position(x=x, y=y),
        Renderable: Renderable(char="k", fg=(255, 0, 0), render_order=1),
        Name: Name(name="kobold"),
        Description: Description(text="A small, snarling creature with sharp teeth."),
        Fighter: Fighter(hp=8, max_hp=8, power=3, defense=0),
        AI: AI(kind=AIKind.HOSTILE),
    }
    entity.tags |= {"enemy", "blocks_movement"}
    return entity


def create_troll(registry: tcod.ecs.Registry, x: int, y: int) -> tcod.ecs.Entity:
    """Create a troll entity at the given position."""
    entity = registry.new_entity()
    entity.components |= {
        Position: Position(x=x, y=y),
        Renderable: Renderable(char="T", fg=(0, 128, 0), render_order=1),
        Name: Name(name="troll"),
        Description: Description(text="A massive creature with regenerative flesh and clubbed fists."),
        Fighter: Fighter(hp=25, max_hp=25, power=8, defense=4),
        AI: AI(kind=AIKind.HOSTILE),
    }
    entity.tags |= {"enemy", "blocks_movement"}
    return entity
```

Each factory is self-contained. The spawn function no longer needs to know how to build an orc---it only needs to call `create_orc`:

```python
def spawn_entities(
    registry: tcod.ecs.Registry,
    dungeon: DungeonLayout,
    dungeon_level: int,
) -> None:
    enemy_factories = [create_kobold, create_orc, create_troll]

    for x, y in dungeon.enemy_positions:
        factory = random.choice(enemy_factories)
        factory(registry, x, y)

    item_factories = [create_health_potion, create_scroll_of_fireball]

    for x, y in dungeon.item_positions:
        factory = random.choice(item_factories)
        factory(registry, x, y)
```

The spawn function is now 12 lines. It does not know what a kobold looks like or how many hit points an orc has. It picks a factory at random and calls it. The entity definitions live in factory functions. The placement logic lives in `spawn_entities`. The two concerns are cleanly separated.

## Actor Factories

Actors are entities that take turns: the player, enemies, and any other entity with AI or that participates in combat. The factory pattern for actors is straightforward because most actors share the same set of components. The differences are in the values.

Let us build a complete set of actor factories for the game. We start with the enemies and then create the player:

```python
# src/factories/actors.py

from __future__ import annotations

import random

import tcod.ecs

from components import (
    AI,
    AIKind,
    Description,
    Equipment,
    Fighter,
    Inventory,
    Name,
    Position,
    Renderable,
    XP,
)


def create_kobold(
    registry: tcod.ecs.Registry, x: int, y: int
) -> tcod.ecs.Entity:
    entity = registry.new_entity()
    entity.components |= {
        Position: Position(x=x, y=y),
        Renderable: Renderable(char="k", fg=(255, 0, 0), render_order=1),
        Name: Name(name="kobold"),
        Description: Description(text="A small, snarling creature with sharp teeth."),
        Fighter: Fighter(hp=8, max_hp=8, power=3, defense=0),
        AI: AI(kind=AIKind.HOSTILE),
    }
    entity.tags |= {"enemy", "blocks_movement"}
    return entity


def create_orc(
    registry: tcod.ecs.Registry, x: int, y: int
) -> tcod.ecs.Entity:
    entity = registry.new_entity()
    entity.components |= {
        Position: Position(x=x, y=y),
        Renderable: Renderable(char="o", fg=(63, 127, 63), render_order=1),
        Name: Name(name="orc"),
        Description: Description(text="A hulking brute with tusks and a heavy axe."),
        Fighter: Fighter(hp=15, max_hp=15, power=5, defense=2),
        AI: AI(kind=AIKind.HOSTILE),
    }
    entity.tags |= {"enemy", "blocks_movement"}
    return entity


def create_troll(
    registry: tcod.ecs.Registry, x: int, y: int
) -> tcod.ecs.Entity:
    entity = registry.new_entity()
    entity.components |= {
        Position: Position(x=x, y=y),
        Renderable: Renderable(char="T", fg=(0, 128, 0), render_order=1),
        Name: Name(name="troll"),
        Description: Description(text="A massive creature with regenerative flesh and clubbed fists."),
        Fighter: Fighter(hp=25, max_hp=25, power=8, defense=4),
        AI: AI(kind=AIKind.HOSTILE),
    }
    entity.tags |= {"enemy", "blocks_movement"}
    return entity


def create_ogre(
    registry: tcod.ecs.Registry, x: int, y: int
) -> tcod.ecs.Entity:
    entity = registry.new_entity()
    entity.components |= {
        Position: Position(x=x, y=y),
        Renderable: Renderable(char="O", fg=(127, 127, 0), render_order=1),
        Name: Name(name="ogre"),
        Description: Description(text="A towering brute wielding a massive bone club."),
        Fighter: Fighter(hp=30, max_hp=30, power=10, defense=3),
        AI: AI(kind=AIKind.HOSTILE),
    }
    entity.tags |= {"enemy", "blocks_movement"}
    return entity


def create_skeleton(
    registry: tcod.ecs.Registry, x: int, y: int
) -> tcod.ecs.Entity:
    entity = registry.new_entity()
    entity.components |= {
        Position: Position(x=x, y=y),
        Renderable: Renderable(char="s", fg=(200, 200, 200), render_order=1),
        Name: Name(name="skeleton"),
        Description: Description(text="A shambling corpse animated by dark magic."),
        Fighter: Fighter(hp=10, max_hp=10, power=4, defense=1),
        AI: AI(kind=AIKind.HOSTILE),
    }
    entity.tags |= {"enemy", "blocks_movement"}
    return entity
```

Notice that every factory follows the same structure. The component set is identical: Position, Renderable, Name, Description, Fighter, AI. The tags are identical: `"enemy"` and `"blocks_movement"`. The only variation is in the literal values. This consistency is not accidental---it reflects the ECS principle that entity types are defined by their component composition, not by inheritance hierarchies. All enemies have the same components because they all participate in the same systems. The systems do not care whether an entity is a kobold or a troll. They query for entities with `Fighter` and `AI` and process them uniformly.

The player factory follows the same pattern but with additional components:

```python
def create_player(
    registry: tcod.ecs.Registry, x: int, y: int
) -> tcod.ecs.Entity:
    entity = registry.new_entity(key="player")
    entity.components |= {
        Position: Position(x=x, y=y),
        Renderable: Renderable(char="@", fg=(255, 255, 255), render_order=2),
        Name: Name(name="Player"),
        Description: Description(text="You, the brave adventurer."),
        Fighter: Fighter(hp=30, max_hp=30, power=5, defense=2),
        XP: XP(current=0, level=1, xp_to_next=100),
        Inventory: Inventory(items=[], capacity=20),
        Equipment: Equipment(slots={}),
    }
    entity.tags |= {"player", "blocks_movement"}
    return entity
```

The player entity has `XP`, `Inventory`, and `Equipment` components that enemies do not need. This is fine. Entities are defined by their component composition, not by a fixed schema. The player gets what the player needs. The `render_order=2` ensures the player renders on top of enemies when sharing a tile. The explicit `key="player"` makes the entity retrievable with `registry["player"]`.

## Item Factories

Items follow the same factory pattern but with a different component set. Items do not have `Fighter` or `AI` components. Instead, they have `Item` components with `use_function` strings that identify what happens when the item is consumed or equipped.

```python
# src/factories/items.py

from __future__ import annotations

import tcod.ecs

from components import (
    Description,
    Item,
    Name,
    Position,
    Renderable,
)


def create_health_potion(
    registry: tcod.ecs.Registry, x: int, y: int
) -> tcod.ecs.Entity:
    entity = registry.new_entity()
    entity.components |= {
        Position: Position(x=x, y=y),
        Renderable: Renderable(char="!", fg=(127, 0, 255), render_order=0),
        Name: Name(name="Health Potion"),
        Description: Description(text="A swirling red liquid that restores 10 hit points."),
        Item(name="Health Potion", use_function="heal", value=10),
    }
    entity.tags.add("item")
    return entity


def create_scroll_of_fireball(
    registry: tcod.ecs.Registry, x: int, y: int
) -> tcod.ecs.Entity:
    entity = registry.new_entity()
    entity.components |= {
        Position: Position(x=x, y=y),
        Renderable: Renderable(char="?", fg=(255, 63, 0), render_order=0),
        Name: Name(name="Scroll of Fireball"),
        Description: Description(
            text="A scorched parchment that unleashes a ball of fire."
        ),
        Item(name="Scroll of Fireball", use_function="fireball", value=12),
    }
    entity.tags.add("item")
    return entity


def create_scroll_of_lightning(
    registry: tcod.ecs.Registry, x: int, y: int
) -> tcod.ecs.Entity:
    entity = registry.new_entity()
    entity.components |= {
        Position: Position(x=x, y=y),
        Renderable: Renderable(char="?", fg=(255, 255, 0), render_order=0),
        Name: Name(name="Scroll of Lightning"),
        Description: Description(
            text="Crackling energy dances across this ancient scroll."
        ),
        Item(name="Scroll of Lightning", use_function="lightning", value=20),
    }
    entity.tags.add("item")
    return entity


def create_scroll_of_teleportation(
    registry: tcod.ecs.Registry, x: int, y: int
) -> tcod.ecs.Entity:
    entity = registry.new_entity()
    entity.components |= {
        Position: Position(x=x, y=y),
        Renderable: Renderable(char="?", fg=(0, 127, 255), render_order=0),
        Name: Name(name="Scroll of Teleportation"),
        Description: Description(
            text="Strange symbols shimmer on this translucent parchment."
        ),
        Item(name="Scroll of Teleportation", use_function="teleport"),
    }
    entity.tags.add("item")
    return entity
```

Equipment items use the same pattern but with different `use_function` values and additional fields for stat bonuses:

```python
def create_leather_armor(
    registry: tcod.ecs.Registry, x: int, y: int
) -> tcod.ecs.Entity:
    entity = registry.new_entity()
    entity.components |= {
        Position: Position(x=x, y=y),
        Renderable: Renderable(char="[", fg=(139, 90, 43), render_order=0),
        Name: Name(name="Leather Armor"),
        Description: Description(
            text="Light armor made from hardened leather. Offers basic protection."
        ),
        Item(name="Leather Armor", use_function="equip", slot="armor", defense_bonus=1),
    }
    entity.tags.add("item")
    return entity


def create_chain_mail(
    registry: tcod.ecs.Registry, x: int, y: int
) -> tcod.ecs.Entity:
    entity = registry.new_entity()
    entity.components |= {
        Position: Position(x=x, y=y),
        Renderable: Renderable(char="[", fg=(160, 160, 160), render_order=0),
        Name: Name(name="Chain Mail"),
        Description: Description(
            text="Interlocking metal rings. Heavy but reliable."
        ),
        Item(name="Chain Mail", use_function="equip", slot="armor", defense_bonus=3),
    }
    entity.tags.add("item")
    return entity


def create_long_sword(
    registry: tcod.ecs.Registry, x: int, y: int
) -> tcod.ecs.Entity:
    entity = registry.new_entity()
    entity.components |= {
        Position: Position(x=x, y=y),
        Renderable: Renderable(char="/", fg=(192, 192, 192), render_order=0),
        Name: Name(name="Longsword"),
        Description: Description(
            text="A straight double-edged blade. Reliable and sharp."
        ),
        Item(name="Longsword", use_function="equip", slot="weapon", power_bonus=3),
    }
    entity.tags.add("item")
    return entity
```

The `Item` component now carries additional fields like `slot`, `power_bonus`, and `defense_bonus`. These fields are meaningful to the equipment system, which reads them when the item is equipped. The factory function is responsible for setting these values correctly. This is one of the key advantages of the factory pattern: the definition of a longsword---including its stat bonuses---lives in one place, not scattered across equipment handling code.

## Data-Driven Definitions

The factory functions work well, but they have a limitation: every entity type is baked into Python code. Changing a stat requires editing a `.py` file. Adding a new enemy type requires writing a new function. For a small game this is fine. For a game where you want to tune balance, allow modding, or iterate quickly on design, a data-driven approach is better.

A data-driven definition separates the entity data from the code that processes it. Instead of writing a function for each entity type, you define entity templates as data---dictionaries, dataclasses, or configuration files---and write a single factory function that reads the data and creates entities.

Here is a dictionary-based approach:

```python
# src/factories/definitions.py

ENEMY_TEMPLATES: dict[str, dict] = {
    "kobold": {
        "char": "k",
        "fg": (255, 0, 0),
        "name": "kobold",
        "description": "A small, snarling creature with sharp teeth.",
        "hp": 8,
        "power": 3,
        "defense": 0,
        "ai_kind": AIKind.HOSTILE,
    },
    "orc": {
        "char": "o",
        "fg": (63, 127, 63),
        "name": "orc",
        "description": "A hulking brute with tusks and a heavy axe.",
        "hp": 15,
        "power": 5,
        "defense": 2,
        "ai_kind": AIKind.HOSTILE,
    },
    "troll": {
        "char": "T",
        "fg": (0, 128, 0),
        "name": "troll",
        "description": "A massive creature with regenerative flesh and clubbed fists.",
        "hp": 25,
        "power": 8,
        "defense": 4,
        "ai_kind": AIKind.HOSTILE,
    },
    "ogre": {
        "char": "O",
        "fg": (127, 127, 0),
        "name": "ogre",
        "description": "A towering brute wielding a massive bone club.",
        "hp": 30,
        "power": 10,
        "defense": 3,
        "ai_kind": AIKind.HOSTILE,
    },
    "skeleton": {
        "char": "s",
        "fg": (200, 200, 200),
        "name": "skeleton",
        "description": "A shambling corpse animated by dark magic.",
        "hp": 10,
        "power": 4,
        "defense": 1,
        "ai_kind": AIKind.HOSTILE,
    },
}


ITEM_TEMPLATES: dict[str, dict] = {
    "health_potion": {
        "char": "!",
        "fg": (127, 0, 255),
        "name": "Health Potion",
        "description": "A swirling red liquid that restores 10 hit points.",
        "use_function": "heal",
        "value": 10,
    },
    "scroll_of_fireball": {
        "char": "?",
        "fg": (255, 63, 0),
        "name": "Scroll of Fireball",
        "description": "A scorched parchment that unleashes a ball of fire.",
        "use_function": "fireball",
        "value": 12,
    },
    "scroll_of_lightning": {
        "char": "?",
        "fg": (255, 255, 0),
        "name": "Scroll of Lightning",
        "description": "Crackling energy dances across this ancient scroll.",
        "use_function": "lightning",
        "value": 20,
    },
    "scroll_of_teleportation": {
        "char": "?",
        "fg": (0, 127, 255),
        "name": "Scroll of Teleportation",
        "description": "Strange symbols shimmer on this translucent parchment.",
        "use_function": "teleport",
    },
    "leather_armor": {
        "char": "[",
        "fg": (139, 90, 43),
        "name": "Leather Armor",
        "description": "Light armor made from hardened leather. Offers basic protection.",
        "use_function": "equip",
        "slot": "armor",
        "defense_bonus": 1,
    },
    "chain_mail": {
        "char": "[",
        "fg": (160, 160, 160),
        "name": "Chain Mail",
        "description": "Interlocking metal rings. Heavy but reliable.",
        "use_function": "equip",
        "slot": "armor",
        "defense_bonus": 3,
    },
    "longsword": {
        "char": "/",
        "fg": (192, 192, 192),
        "name": "Longsword",
        "description": "A straight double-edged blade. Reliable and sharp.",
        "use_function": "equip",
        "slot": "weapon",
        "power_bonus": 3,
    },
}
```

A single generic factory function reads from these templates:

```python
def create_enemy_from_template(
    registry: tcod.ecs.Registry,
    x: int,
    y: int,
    template_name: str,
) -> tcod.ecs.Entity:
    """Create an enemy entity from a template definition."""
    template = ENEMY_TEMPLATES[template_name]

    entity = registry.new_entity()
    entity.components |= {
        Position: Position(x=x, y=y),
        Renderable: Renderable(
            char=template["char"], fg=template["fg"], render_order=1
        ),
        Name: Name(name=template["name"]),
        Description: Description(text=template["description"]),
        Fighter: Fighter(
            hp=template["hp"],
            max_hp=template["hp"],
            power=template["power"],
            defense=template["defense"],
        ),
        AI: AI(kind=template["ai_kind"]),
    }
    entity.tags |= {"enemy", "blocks_movement"}
    return entity


def create_item_from_template(
    registry: tcod.ecs.Registry,
    x: int,
    y: int,
    template_name: str,
) -> tcod.ecs.Entity:
    """Create an item entity from a template definition."""
    template = ITEM_TEMPLATES[template_name]

    entity = registry.new_entity()
    entity.components |= {
        Position: Position(x=x, y=y),
        Renderable: Renderable(
            char=template["char"], fg=template["fg"], render_order=0
        ),
        Name: Name(name=template["name"]),
        Description: Description(text=template["description"]),
        Item(
            name=template["name"],
            use_function=template["use_function"],
            value=template.get("value", 0),
            slot=template.get("slot", ""),
            power_bonus=template.get("power_bonus", 0),
            defense_bonus=template.get("defense_bonus", 0),
        ),
    }
    entity.tags.add("item")
    return entity
```

The spawn function now reads from the template dictionaries:

```python
ENEMY_TYPES = list(ENEMY_TEMPLATES.keys())
ITEM_TYPES = list(ITEM_TEMPLATES.keys())


def spawn_entities(
    registry: tcod.ecs.Registry,
    dungeon: DungeonLayout,
    dungeon_level: int,
) -> None:
    for x, y in dungeon.enemy_positions:
        template_name = random.choice(ENEMY_TYPES)
        create_enemy_from_template(registry, x, y, template_name)

    for x, y in dungeon.item_positions:
        template_name = random.choice(ITEM_TYPES)
        create_item_from_template(registry, x, y, template_name)
```

Adding a new enemy type now requires zero code changes---just add a new entry to `ENEMY_TEMPLATES`. The generic factory function handles the rest. This is the preview of the YAML/JSON modding system we will build in Chapter 26. The dictionary templates are the in-code version of what will eventually be external configuration files that modders can edit without touching Python.

The `.get()` calls with defaults handle optional fields gracefully. Not every item has a `slot` or a `power_bonus`. The template dictionary only includes the fields relevant to that item type, and the factory function falls back to sensible defaults for missing fields.

## Enemy Scaling

Enemies in a roguelike must get harder as the player descends. A kobold on floor 1 is a genuine threat. A kobold on floor 10 is a speed bump. The factory system supports scaling through two mechanisms: stat multipliers applied at creation time, and access to different template pools based on dungeon level.

The simplest approach is to scale stats at creation time:

```python
def create_enemy_from_template(
    registry: tcod.ecs.Registry,
    x: int,
    y: int,
    template_name: str,
    dungeon_level: int = 1,
) -> tcod.ecs.Entity:
    """Create an enemy entity from a template, scaled by dungeon level."""
    template = ENEMY_TEMPLATES[template_name]

    # Scale stats with dungeon level
    level_bonus = dungeon_level - 1
    hp = template["hp"] + level_bonus * 2
    power = template["power"] + level_bonus
    defense = template["defense"] + level_bonus // 2

    entity = registry.new_entity()
    entity.components |= {
        Position: Position(x=x, y=y),
        Renderable: Renderable(
            char=template["char"], fg=template["fg"], render_order=1
        ),
        Name: Name(name=template["name"]),
        Description: Description(text=template["description"]),
        Fighter: Fighter(hp=hp, max_hp=hp, power=power, defense=defense),
        AI: AI(kind=template["ai_kind"]),
    }
    entity.tags |= {"enemy", "blocks_movement"}
    return entity
```

The scaling formula is simple: hp gains 2 per level, power gains 1 per level, and defense gains 1 every 2 levels. This ensures that enemies become more dangerous without becoming mathematically invincible. A floor 1 orc has 15 hp. A floor 5 orc has 23 hp. A floor 10 orc has 33 hp. The player must keep finding better equipment and gaining levels to keep pace.

For more interesting scaling, we can restrict which enemy types appear on each floor. Early floors should have only weak enemies. Stronger enemies should appear only after the player has descended further:

```python
# Enemy types available at each dungeon level
ENEMY_SPAWN_TABLE: dict[int, list[str]] = {
    1: ["kobold", "kobold", "skeleton"],
    2: ["kobold", "skeleton", "orc"],
    3: ["kobold", "orc", "orc", "skeleton"],
    4: ["orc", "orc", "troll", "skeleton"],
    5: ["orc", "troll", "ogre", "skeleton"],
}


def get_enemy_pool(dungeon_level: int) -> list[str]:
    """Return the list of enemy types available on a given floor."""
    if dungeon_level in ENEMY_SPAWN_TABLE:
        return ENEMY_SPAWN_TABLE[dungeon_level]
    # For floors beyond the table, use the highest entry
    max_level = max(ENEMY_SPAWN_TABLE.keys())
    return ENEMY_SPAWN_TABLE[max_level]
```

The spawn table uses duplicate entries to control probability. Floor 1 has two `"kobold"` entries and one `"skeleton"` entry, meaning kobolds appear twice as often as skeletons. Floor 3 has two `"orc"` entries, making orcs the most common threat. This is a simple but effective way to tune encounter frequency without writing probability distributions.

The spawn function uses this table:

```python
def spawn_entities(
    registry: tcod.ecs.Registry,
    dungeon: DungeonLayout,
    dungeon_level: int,
) -> None:
    enemy_pool = get_enemy_pool(dungeon_level)

    for x, y in dungeon.enemy_positions:
        template_name = random.choice(enemy_pool)
        create_enemy_from_template(
            registry, x, y, template_name, dungeon_level
        )
```

The combination of stat scaling and spawn tables produces floors that feel progressively harder. Floor 1 is mostly kobolds with low stats. Floor 5 has ogres and trolls with scaled-up stats. The player feels the difficulty curve because the enemies are not just more numerous---they are individually stronger.

### Variant Enemies

A simple way to add depth to the enemy roster is a rare variant system. A small percentage of enemies spawn as upgraded variants with boosted stats and a distinct appearance:

```python
VARIANT_CHANCE = 0.10  # 10% chance of a variant

VARIANT_MODIFIERS: dict[str, dict] = {
    "elite": {
        "name_prefix": "Elite ",
        "fg_tint": (0, 0, 63),  # Slightly bluer
        "hp_multiplier": 1.5,
        "power_multiplier": 1.25,
        "xp_multiplier": 2.0,
    },
}


def create_enemy_from_template(
    registry: tcod.ecs.Registry,
    x: int,
    y: int,
    template_name: str,
    dungeon_level: int = 1,
) -> tcod.ecs.Entity:
    """Create an enemy, possibly as a rare variant."""
    template = ENEMY_TEMPLATES[template_name]

    level_bonus = dungeon_level - 1
    hp = template["hp"] + level_bonus * 2
    power = template["power"] + level_bonus
    defense = template["defense"] + level_bonus // 2

    # Check for variant
    is_variant = random.random() < VARIANT_CHANCE
    name = template["name"]
    fg = template["fg"]

    if is_variant:
        variant = VARIANT_MODIFIERS["elite"]
        name = variant["name_prefix"] + name
        fg = tuple(min(255, c + t) for c, t in zip(fg, variant["fg_tint"]))
        hp = int(hp * variant["hp_multiplier"])
        power = int(power * variant["power_multiplier"])

    entity = registry.new_entity()
    entity.components |= {
        Position: Position(x=x, y=y),
        Renderable: Renderable(char=template["char"], fg=fg, render_order=1),
        Name(name=name),
        Description(text=template["description"]),
        Fighter(hp=hp, max_hp=hp, power=power, defense=defense),
        AI(kind=template["ai_kind"]),
    }
    entity.tags |= {"enemy", "blocks_movement"}

    if is_variant:
        entity.tags.add("variant")

    return entity
```

The variant check is a single random roll. When it succeeds, the enemy's name gets an "Elite " prefix, its color shifts slightly, and its stats increase. The `"variant"` tag lets systems query for variant enemies specifically---for example, to award bonus XP or to spawn a special loot drop.

## Item Variants

Items can follow the same variant pattern, but item variation is more interesting when it affects the item's function rather than just its stats. A fireball scroll that does more damage is a minor upgrade. A fireball scroll that has a different effect entirely is a new item.

Here is a set of item factories that cover the major consumable and equipment categories:

```python
def create_healing_potion(
    registry: tcod.ecs.Registry, x: int, y: int
) -> tcod.ecs.Entity:
    entity = registry.new_entity()
    entity.components |= {
        Position: Position(x=x, y=y),
        Renderable: Renderable(char="!", fg=(127, 0, 255), render_order=0),
        Name: Name(name="Health Potion"),
        Description: Description(
            text="A swirling red liquid that restores hit points."
        ),
        Item(name="Health Potion", use_function="heal", value=10),
    }
    entity.tags.add("item")
    return entity


def create_greater_health_potion(
    registry: tcod.ecs.Registry, x: int, y: int
) -> tcod.ecs.Entity:
    entity = registry.new_entity()
    entity.components |= {
        Position: Position(x=x, y=y),
        Renderable: Renderable(char="!", fg=(255, 0, 0), render_order=0),
        Name: Name(name="Greater Health Potion"),
        Description: Description(
            text="A rich crimson potion that restores a large amount of health."
        ),
        Item(name="Greater Health Potion", use_function="heal", value=25),
    }
    entity.tags.add("item")
    return entity


def create_scroll_of_fireball(
    registry: tcod.ecs.Registry, x: int, y: int
) -> tcod.ecs.Entity:
    entity = registry.new_entity()
    entity.components |= {
        Position: Position(x=x, y=y),
        Renderable: Renderable(char="?", fg=(255, 63, 0), render_order=0),
        Name: Name(name="Scroll of Fireball"),
        Description: Description(
            text="A scorched parchment that unleashes a ball of fire in an area."
        ),
        Item(name="Scroll of Fireball", use_function="fireball", value=12),
    }
    entity.tags.add("item")
    return entity


def create_scroll_of_lightning(
    registry: tcod.ecs.Registry, x: int, y: int
) -> tcod.ecs.Entity:
    entity = registry.new_entity()
    entity.components |= {
        Position: Position(x=x, y=y),
        Renderable: Renderable(char="?", fg=(255, 255, 0), render_order=0),
        Name: Name(name="Scroll of Lightning"),
        Description: Description(
            text="Crackling energy dances across this ancient scroll."
        ),
        Item(name="Scroll of Lightning", use_function="lightning", value=20),
    }
    entity.tags.add("item")
    return entity


def create_scroll_of_confusion(
    registry: tcod.ecs.Registry, x: int, y: int
) -> tcod.ecs.Entity:
    entity = registry.new_entity()
    entity.components |= {
        Position: Position(x=x, y=y),
        Renderable: Renderable(char="?", fg=(191, 0, 191), render_order=0),
        Name: Name(name="Scroll of Confusion"),
        Description: Description(
            text="Whispers emanate from this paper, warping perception."
        ),
        Item(name="Scroll of Confusion", use_function="confuse"),
    }
    entity.tags.add("item")
    return entity


def create_scroll_of_teleportation(
    registry: tcod.ecs.Registry, x: int, y: int
) -> tcod.ecs.Entity:
    entity = registry.new_entity()
    entity.components |= {
        Position: Position(x=x, y=y),
        Renderable: Renderable(char="?", fg=(0, 127, 255), render_order=0),
        Name: Name(name="Scroll of Teleportation"),
        Description: Description(
            text="Strange symbols shimmer on this translucent parchment."
        ),
        Item(name="Scroll of Teleportation", use_function="teleport"),
    }
    entity.tags.add("item")
    return entity


def create_leather_armor(
    registry: tcod.ecs.Registry, x: int, y: int
) -> tcod.ecs.Entity:
    entity = registry.new_entity()
    entity.components |= {
        Position: Position(x=x, y=y),
        Renderable: Renderable(char="[", fg=(139, 90, 43), render_order=0),
        Name: Name(name="Leather Armor"),
        Description: Description(
            text="Light armor made from hardened leather. Defense bonus: +1."
        ),
        Item(
            name="Leather Armor",
            use_function="equip",
            slot="armor",
            defense_bonus=1,
        ),
    }
    entity.tags.add("item")
    return entity


def create_chain_mail(
    registry: tcod.ecs.Registry, x: int, y: int
) -> tcod.ecs.Entity:
    entity = registry.new_entity()
    entity.components |= {
        Position: Position(x=x, y=y),
        Renderable: Renderable(char="[", fg=(160, 160, 160), render_order=0),
        Name: Name(name="Chain Mail"),
        Description: Description(
            text="Interlocking metal rings. Heavy but reliable. Defense bonus: +3."
        ),
        Item(
            name="Chain Mail",
            use_function="equip",
            slot="armor",
            defense_bonus=3,
        ),
    }
    entity.tags.add("item")
    return entity


def create_plate_armor(
    registry: tcod.ecs.Registry, x: int, y: int
) -> tcod.ecs.Entity:
    entity = registry.new_entity()
    entity.components |= {
        Position: Position(x=x, y=y),
        Renderable: Renderable(char="[", fg=(128, 128, 128), render_order=0),
        Name: Name(name="Plate Armor"),
        Description: Description(
            text="Heavy articulated plates of steel. Defense bonus: +5."
        ),
        Item(
            name="Plate Armor",
            use_function="equip",
            slot="armor",
            defense_bonus=5,
        ),
    }
    entity.tags.add("item")
    return entity


def create_rusty_dagger(
    registry: tcod.ecs.Registry, x: int, y: int
) -> tcod.ecs.Entity:
    entity = registry.new_entity()
    entity.components |= {
        Position: Position(x=x, y=y),
        Renderable: Renderable(char="/", fg=(128, 100, 75), render_order=0),
        Name: Name(name="Rusty Dagger"),
        Description: Description(
            text="A short blade with a corroded edge. Power bonus: +1."
        ),
        Item(
            name="Rusty Dagger",
            use_function="equip",
            slot="weapon",
            power_bonus=1,
        ),
    }
    entity.tags.add("item")
    return entity


def create_long_sword(
    registry: tcod.ecs.Registry, x: int, y: int
) -> tcod.ecs.Entity:
    entity = registry.new_entity()
    entity.components |= {
        Position: Position(x=x, y=y),
        Renderable: Renderable(char="/", fg=(192, 192, 192), render_order=0),
        Name: Name(name="Longsword"),
        Description: Description(
            text="A straight double-edged blade. Reliable and sharp. Power bonus: +3."
        ),
        Item(
            name="Longsword",
            use_function="equip",
            slot="weapon",
            power_bonus=3,
        ),
    }
    entity.tags.add("item")
    return entity


def create_war_hammer(
    registry: tcod.ecs.Registry, x: int, y: int
) -> tcod.ecs.Entity:
    entity = registry.new_entity()
    entity.components |= {
        Position: Position(x=x, y=y),
        Renderable: Renderable(char="/", fg=(139, 90, 43), render_order=0),
        Name: Name(name="War Hammer"),
        Description: Description(
            text="A heavy two-handed hammer. Devastating but slow. Power bonus: +5."
        ),
        Item(
            name="War Hammer",
            use_function="equip",
            slot="weapon",
            power_bonus=5,
        ),
    }
    entity.tags.add("item")
    return entity
```

The item pool gives the game variety at every tier. The player starts with a rusty dagger and leather armor, finds a longsword and chain mail on the mid floors, and discovers plate armor and war hammers in the deepest levels. The healing potions scale similarly: health potions restore 10 hp, greater health potions restore 25. The scrolls provide tactical options---fireball for groups, lightning for single targets, confusion for crowd control, and teleportation for escape.

## The Factory Module

Organizing factories into a dedicated module keeps the codebase clean and the imports simple. The module structure mirrors the component organization from Chapter 6:

```
src/
    factories/
        __init__.py
        actors.py
        items.py
```

The `actors.py` file contains all actor factory functions. The `items.py` file contains all item factory functions. The `__init__.py` re-exports everything so that consumers can import from the package directly:

```python
# src/factories/__init__.py

from src.factories.actors import (
    create_kobold,
    create_orc,
    create_troll,
    create_ogre,
    create_skeleton,
    create_player,
)
from src.factories.items import (
    create_health_potion,
    create_greater_health_potion,
    create_scroll_of_fireball,
    create_scroll_of_lightning,
    create_scroll_of_confusion,
    create_scroll_of_teleportation,
    create_leather_armor,
    create_chain_mail,
    create_plate_armor,
    create_rusty_dagger,
    create_long_sword,
    create_war_hammer,
)

__all__ = [
    "create_chain_mail",
    "create_greater_health_potion",
    "create_health_potion",
    "create_kobold",
    "create_leather_armor",
    "create_long_sword",
    "create_orc",
    "create_ogre",
    "create_plate_armor",
    "create_player",
    "create_rusty_dagger",
    "create_scroll_of_confusion",
    "create_scroll_of_fireball",
    "create_scroll_of_lightning",
    "create_scroll_of_teleportation",
    "create_skeleton",
    "create_troll",
    "create_war_hammer",
]
```

Other parts of the game import from this single location:

```python
from factories import create_orc, create_health_potion, create_player
```

This pattern scales. As you add new entity types, you add new functions to the appropriate module file and update the `__init__.py` re-exports. The import statement for consumers never changes. If the factory module grows too large, you can split it further---`factories/enemies.py`, `factories/npcs.py`, `factories/consumables.py`, `factories/equipment.py`---and update the `__init__.py` to aggregate from the new submodules.

## Entity Templates in Practice

The factories connect to the rest of the game through the dungeon generation pipeline. When the generator produces positions, the spawn function picks factories and calls them:

```python
def spawn_entities(
    registry: tcod.ecs.Registry,
    dungeon: DungeonLayout,
    dungeon_level: int,
) -> None:
    enemy_pool = get_enemy_pool(dungeon_level)

    for x, y in dungeon.enemy_positions:
        template_name = random.choice(enemy_pool)
        create_enemy_from_template(
            registry, x, y, template_name, dungeon_level
        )

    item_pool = get_item_pool(dungeon_level)

    for x, y in dungeon.item_positions:
        template_name = random.choice(item_pool)
        create_item_from_template(registry, x, y, template_name)

    # Always place stairs in the last room
    sx, sy = dungeon.stairs_pos
    create_stairs(registry, sx, sy)
```

The item pool works the same way as the enemy pool---a dictionary mapping dungeon levels to lists of available item types:

```python
ITEM_SPAWN_TABLE: dict[int, list[str]] = {
    1: ["health_potion", "health_potion", "rusty_dagger"],
    2: ["health_potion", "scroll_of_fireball", "rusty_dagger", "leather_armor"],
    3: ["health_potion", "scroll_of_fireball", "scroll_of_lightning", "long_sword"],
    4: [
        "health_potion",
        "greater_health_potion",
        "scroll_of_fireball",
        "scroll_of_confusion",
        "chain_mail",
        "long_sword",
    ],
    5: [
        "greater_health_potion",
        "scroll_of_fireball",
        "scroll_of_lightning",
        "scroll_of_teleportation",
        "plate_armor",
        "war_hammer",
    ],
}


def get_item_pool(dungeon_level: int) -> list[str]:
    """Return the list of item types available on a given floor."""
    if dungeon_level in ITEM_SPAWN_TABLE:
        return ITEM_SPAWN_TABLE[dungeon_level]
    max_level = max(ITEM_SPAWN_TABLE.keys())
    return ITEM_SPAWN_TABLE[max_level]
```

The staircase entity needs its own factory since it is neither an enemy nor an item:

```python
def create_stairs(
    registry: tcod.ecs.Registry, x: int, y: int
) -> tcod.ecs.Entity:
    entity = registry.new_entity()
    entity.components |= {
        Position: Position(x=x, y=y),
        Renderable: Renderable(char=">", fg=(255, 255, 0), render_order=0),
        Name: Name(name="Stairs"),
    }
    entity.tags.add("staircase")
    return entity
```

The stairs entity is minimal---it has a position, a renderable, and a name, with the `"staircase"` tag that the game loop checks when the player attempts to descend. No combat stats, no AI, no inventory. Just enough components to appear on the map and be recognized.

When the player descends, the game clears all floor-specific entities and generates a new level:

```python
def descend_stairs(
    registry: tcod.ecs.Registry,
    dungeon_level: int,
) -> None:
    """Clear the current floor and generate the next one."""
    # Remove floor-specific entities
    for tag in ["enemy", "item", "staircase"]:
        for entity in list(registry.Q.all_of(tags=[tag])):
            registry.clear_entity(entity)

    # Generate new level
    params = get_level_params(dungeon_level)
    dungeon = generate_dungeon(**params)

    # Update world map
    world = registry[None]
    world.components[GameMap] = GameMap(tiles=dungeon.tiles)

    # Reposition player
    player = registry["player"]
    sx, sy = dungeon.start_pos
    player.components[Position] = Position(x=sx, y=sy)

    # Spawn new entities
    spawn_entities(registry, dungeon, dungeon_level)
```

The player entity persists across levels. Its `Position` is updated to the new starting location. Everything else is destroyed and recreated. The factory functions handle the creation. The spawn function handles the placement. The descent function orchestrates the transition.

## The Value of the Factory Pattern

The factory pattern provides several concrete benefits that compound as the game grows:

**Centralized definitions.** Every entity type is defined in one place. Changing an orc's stats means editing one function. There is no risk of missing a branch in a 200-line `spawn_entities` function.

**Testability.** You can test entity creation in isolation. Create a registry, call a factory function, and assert that the returned entity has the expected components and tags. No dungeon layout or map generation needed.

**Composability.** Factory functions return entities that are ready to use. Other code does not need to know what components an orc has. It calls `create_orc` and gets an orc. This makes it easy to place enemies in hand-crafted test rooms, in scripted encounters, or in debug scenarios.

**Extensibility.** Adding a new entity type means writing one factory function and adding it to the module. The rest of the codebase is unchanged. If you use data-driven templates, adding a new entity type means adding a dictionary entry with no code changes at all.

**Consistency.** Every entity of a given type is guaranteed to have the same set of components and tags. You cannot accidentally create an orc without an AI component because the factory always attaches one.

These benefits matter most when the game is large enough that you cannot hold the entire entity catalog in your head. With 5 enemy types and 5 item types, inline creation is manageable. With 30 enemy types, 40 item types, and a handful of NPCs, the factory pattern is essential.

## Exercises

**Exercise 1: Five New Enemy Types**

Create five new enemy types using factory functions. Design enemies that fill different gameplay roles: a fast but fragile enemy (high power, low hp), a tank (high hp, low power), a support enemy that does not attack but heals nearby allies, an enemy that flees when wounded, and an enemy that becomes stronger as it takes damage. Give each one a unique character, color, name, description, and stat line. Place them in `src/factories/actors.py` and add them to the `ENEMY_TEMPLATES` dictionary.

**Exercise 2: Five New Item Types**

Create five new item types. Include a: scroll that reveals the entire map, a key that opens a locked door, a torch that increases the player's field of view, a bomb that destroys walls in a radius, and a shield that provides a defense bonus. Give each one appropriate `use_function` strings and values. Add them to `src/factories/items.py` and the `ITEM_TEMPLATES` dictionary.

**Exercise 3: Rare Variant System**

Implement a rare variant system. Each enemy has a 10% chance of spawning as a rare variant. Rare variants get a name prefix ("Rare "), a different foreground color (brighter or shifted), and boosted stats (50% more hp, 25% more power, 25% more defense). Rare variants should award double XP when killed. Add a `"rare"` tag to rare variants so the XP system can query for them. Modify the `create_enemy_from_template` function to incorporate this logic.

**Exercise 4: Scaling Item Quality**

Extend the item scaling system so that equipment items found on deeper floors have better stat bonuses. Instead of a fixed `defense_bonus` of 3 for chain mail, scale the bonus based on dungeon level: `bonus = base_bonus + (dungeon_level - 1)`. Apply this scaling in the `create_item_from_template` function. The base item templates should store base bonuses, and the factory applies the level modifier. Update the item description dynamically to reflect the actual bonus value.

# Chapter 13: The Combat System

The game loop from Chapter 12 processes turns, moves enemies, and handles death. But the combat system inside that loop is bare-bones: power minus defense, minimum one, apply damage. There is no randomness, no critical hits, no loot drops, no healing items, and no feedback beyond a flat damage number in the message log. The system works, but it does not feel like combat.

This chapter transforms that arithmetic into a system. We add randomness to damage rolls, introduce critical hits for moments of excitement, build a loot drop system, implement health potions as a survival mechanic, and create color-coded combat messages. By the end, every fight produces a stream of readable, varied feedback.

## Designing Combat

The foundation is power versus defense. Damage is the difference between them, with a floor of one. We extend this with three layers:

**Randomness.** Without it, combat is deterministic. A small random component means the same matchup produces different results each time.

**Critical hits.** A rare, high-damage event that creates excitement or dread. They change the emotional texture of combat.

**Dodge chance.** A design alternative to defense where attacks have a percentage chance to miss entirely. We leave dodge as an exercise.

The key principle: the player should always understand why they dealt or took the damage they did. Complexity comes from item interactions, enemy variety, and positioning, not from opaque formulas.

## Melee Combat

Melee combat in a traditional roguelike is triggered by bumping. The player presses a movement key toward an enemy tile. Instead of moving, the player attacks the entity occupying it. The player does not select an "attack" command---they walk into the enemy.

The bump-to-attack pattern means positioning is combat. Every adjacent tile is a potential attack.

### The Bump Attack Flow

When the player presses a movement key, the input handler creates a `BumpAction`. The action processor checks whether the destination tile contains an enemy. If so, it calls `attack` instead of moving:

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
```

The same pattern applies to enemies. When an enemy is adjacent to the player during its turn, the hostile AI calls `attack(enemy, player, registry)`. Both sides use the same function---the attacker and defender are just two entities with `Fighter` components.

## The Damage Formula

The base formula from Chapter 12 is `damage = max(1, power - defense)`. We extend it with randomness and critical hits.

### Adding Randomness

A flat damage value means every attack deals the same amount. Adding a small random component creates variation without obscuring the formula:

```python
import random

damage = max(1, attacker.power - target.defense + random.randint(-1, 1))
```

The `random.randint(-1, 1)` adds variance of minus one, zero, or plus one. With power 5 and defense 2, the base damage is 3. With randomness, it becomes 2, 3, or 4 with equal probability. The player still understands the matchup---the randomness creates texture, not uncertainty.

### Critical Hits

Critical hits are a 10% chance to deal 1.5x damage:

```python
base_damage = max(1, attacker.power - target.defense + random.randint(-1, 1))
is_critical = random.random() < 0.1

if is_critical:
    damage = int(base_damage * 1.5)
else:
    damage = base_damage
```

Roughly one in ten attacks is critical. In a typical fight lasting five to eight attacks, the player sees a critical hit about once per fight. Frequent enough to be noticeable, rare enough to remain exciting.

The 1.5x multiplier is conservative. A critical hit with base damage 4 becomes 6. More extreme multipliers (2x or 3x) create swings that feel unfair. The 1.5x multiplier keeps critical hits as a spice, not the main course.

### Equipment Modifiers

Equipment bonuses from Chapter 11 modify effective power and defense. The combat system reads these bonuses when calculating damage:

```python
def get_effective_power(entity: tcod.ecs.Entity) -> int:
    """Calculate total power including Fighter bonuses and equipment."""
    fighter = entity.components[Fighter]
    power = fighter.power + fighter.power_bonus

    equipment = entity.components.get(Equipment)
    if equipment is not None:
        for item_entity in equipment.slots.values():
            item = item_entity.components[Item]
            power += getattr(item, "power_bonus", 0)

    return power


def get_effective_defense(entity: tcod.ecs.Entity) -> int:
    """Calculate total defense including Fighter bonuses and equipment."""
    fighter = entity.components[Fighter]
    defense = fighter.defense + fighter.defense_bonus

    equipment = entity.components.get(Equipment)
    if equipment is not None:
        for item_entity in equipment.slots.values():
            item = item_entity.components[Item]
            defense += getattr(item, "defense_bonus", 0)

    return defense
```

These functions iterate over equipped items and sum their stat bonuses. The `Fighter` component's `power_bonus` and `defense_bonus` fields are applied first, then equipment bonuses. The layering is: base stat, Fighter bonus, equipment bonus.

## Death and Respawn

Death processing handles removing the entity from gameplay, dropping inventory items, and awarding XP.

```python
def handle_death(entity: tcod.ecs.Entity, registry: tcod.ecs.Registry) -> None:
    """Process the death of an entity."""
    name = entity.components[Name].name

    if "player" in entity.tags:
        add_message(registry, "You have died!", COLOR_DEATH)
        entity.tags.add("dead")
        return

    add_message(registry, f"The {name} is dead!", COLOR_DEATH)

    roll_loot(entity, registry)
    drop_inventory(entity, registry)

    entity.tags.discard("blocks_movement")
    entity.tags.discard("enemy")
    entity.tags.add("dead")

    player = registry.Q.one(tags=["player"])
    xp = player.components.get(XP)
    if xp is not None:
        fighter = entity.components[Fighter]
        xp_gain = 10 + fighter.max_hp
        xp.current += xp_gain
        add_message(
            registry,
            f"You gain {xp_gain} experience points.",
            COLOR_LOOT,
        )
```

The player death case prints a message and adds the `"dead"` tag. The game-over check detects this and ends the game. We do not strip the player's other tags because the entity needs to remain renderable for the game-over screen.

Enemy death removes the `"blocks_movement"` and `"enemy"` tags, adds `"dead"`, drops loot, drops inventory, and awards XP based on the enemy's `max_hp`.

### Dropping Inventory on Death

Enemies that carry items drop them when they die:

```python
def drop_inventory(entity: tcod.ecs.Entity, registry: tcod.ecs.Registry) -> None:
    """Drop all items from a dead entity's inventory onto the ground."""
    inventory = entity.components.get(Inventory)
    if inventory is None:
        return

    pos = entity.components[Position]

    for item_entity in inventory.items:
        item_entity.components[Position] = Position(x=pos.x, y=pos.y)
        item_entity.tags.discard("in_inventory")
        item_entity.tags.add("item")

    inventory.items.clear()
```

Each item gets positioned at the dead entity's location. The `"in_inventory"` tag is removed and `"item"` is added so items appear on the map. The items stack on the tile and the player walks over them to collect.

### The Dead Entity Cleanup System

Dead entities are tagged `"dead"` and stripped of behavioral tags, but the entity remains for one turn. The cleanup system removes them at the end of each turn cycle:

```python
# src/systems/cleanup.py

def check_dead_entities(registry: tcod.ecs.Registry) -> None:
    """Remove entities that have been tagged as dead."""
    to_remove = []
    for entity in registry.Q.all_of(tags=["dead"]):
        if "player" in entity.tags:
            continue
        to_remove.append(entity)

    for entity in to_remove:
        entity.components.clear()
        entity.tags.clear()
```

The one-turn delay means the death message is visible to the player. The corpse lingers for one turn, then disappears.

## Loot Drops

Enemies have a chance to drop items when they die. The loot system adds a reward incentive beyond XP---the player fights not just to survive but to acquire.

### Loot Tables

A loot table is a list of items with associated drop rates:

```python
# src/systems/loot.py

import random

LOOT_TABLES: dict[str, list[tuple[str, float]]] = {
    "kobold": [
        ("health_potion", 0.20),
        ("gold_coin", 0.50),
    ],
    "orc": [
        ("health_potion", 0.30),
        ("rusty_dagger", 0.10),
        ("leather_armor", 0.05),
        ("gold_coin", 0.80),
    ],
    "troll": [
        ("health_potion", 0.50),
        ("long_sword", 0.15),
        ("chain_mail", 0.10),
        ("gold_coin", 1.00),
    ],
    "skeleton": [
        ("health_potion", 0.15),
        ("gold_coin", 0.60),
    ],
}
```

Each entry is `(item_template_name, drop_chance)`. The drop chance is a probability between 0.0 and 1.0. Each roll is independent---an orc could theoretically drop all four items.

### Processing Loot Drops

The loot function rolls against each entry and spawns items that succeed:

```python
from factories import create_item_from_template


def roll_loot(entity: tcod.ecs.Entity, registry: tcod.ecs.Registry) -> None:
    """Roll the loot table for a dead entity and spawn items."""
    name = entity.components[Name].name
    table = LOOT_TABLES.get(name.lower())
    if table is None:
        return

    pos = entity.components[Position]

    for template_name, drop_chance in table:
        if random.random() < drop_chance:
            item = create_item_from_template(registry, pos.x, pos.y, template_name)
            item_name = item.components[Name].name
            add_message(registry, f"The {name} drops a {item_name}.", COLOR_LOOT)
```

The function looks up the loot table by the enemy's lowercase name. For each entry, it rolls against the drop chance. Successful rolls create items at the enemy's position using the template factory from Chapter 11.

The loot roll is called from `handle_death` before `drop_inventory`. Loot from the table and items from the inventory all drop on the ground.

### Rarity System

Different loot tiers create anticipation. The rarity system is implicit in the drop chances---lower chances mean rarer items. For explicit rarity tiers, add a rarity field to item templates and display it in messages. A message like "The troll drops a rare longsword!" is more exciting than "The troll drops a longsword."

## Health Potions

Health potions are the primary survival tool. Without healing, every fight is permanent attrition toward death. With healing, the player makes strategic decisions about when to use limited resources.

### Using a Health Potion

Health potions are items with `use_function="heal"`. When the player activates one, the use system reads the item's `value` and restores that many hit points:

```python
# src/systems/items.py

def use_health_potion(
    user: tcod.ecs.Entity,
    item_entity: tcod.ecs.Entity,
    registry: tcod.ecs.Registry,
) -> None:
    """Use a health potion to restore hit points."""
    fighter = user.components[Fighter]
    item = item_entity.components[Item]
    heal_amount = item.value

    if fighter.hp >= fighter.max_hp:
        add_message(registry, "You are already at full health.")
        return

    old_hp = fighter.hp
    fighter.hp = min(fighter.hp + heal_amount, fighter.max_hp)
    actual_heal = fighter.hp - old_hp

    user_name = user.components[Name].name
    add_message(
        registry,
        f"{user_name} drinks the {item.name} and recovers {actual_heal} HP.",
        COLOR_HEAL,
    )

    inventory = user.components[Inventory]
    inventory.items.remove(item_entity)
```

The function checks whether the user is already at full health. If so, the potion is not consumed. The `min()` call prevents overhealing---a potion with value 10 used when 8 hp is missing heals only 8 but is still consumed.

Greater health potions restore 25 hp instead of 10. They use the same `use_function="heal"` but a higher `value`.

## Combat Messages

The message log is the player's window into what happened during a turn. Without it, the player would see HP values change with no context. The log tells the story: who attacked whom, how much damage was dealt, whether a critical hit landed.

### Color-Coded Messages

Not all messages are equal. Color-coded messages let the player scan the log and immediately identify important events:

```python
# src/components/ui.py

import attrs


@attrs.define
class Message:
    """A single message with associated color."""
    text: str
    color: tuple[int, int, int] = (200, 200, 200)


@attrs.define
class MessageLog:
    """Accumulates messages for display in the UI."""
    messages: list[Message] = attrs.Factory(list)
    max_messages: int = 50


def add_message(
    registry: tcod.ecs.Registry,
    text: str,
    color: tuple[int, int, int] = (200, 200, 200),
) -> None:
    """Add a colored message to the log."""
    world = registry[None]
    log = world.components.get(MessageLog)
    if log is not None:
        log.messages.append(Message(text=text, color=color))
        if len(log.messages) > log.max_messages:
            log.messages = log.messages[-log.max_messages:]
```

The `Message` class pairs text with a color. The `MessageLog` stores messages and trims to the maximum length.

```python
COLOR_DAMAGE = (255, 80, 80)       # Red for damage dealt
COLOR_HEAL = (80, 255, 80)         # Green for healing
COLOR_CRITICAL = (255, 255, 0)     # Yellow for critical hits
COLOR_DEATH = (255, 0, 0)          # Bright red for death
COLOR_LOOT = (255, 200, 0)         # Gold for loot drops
COLOR_DEFAULT = (200, 200, 200)    # Gray for general messages
```

Critical hits appear in yellow. Regular attacks appear in red. Death messages use bright red. Healing uses green.

### Rendering Messages

The message log renders at the bottom of the screen, showing the most recent messages first:

```python
def render_messages(
    console: tcod.console.Console,
    registry: tcod.ecs.Registry,
    x: int,
    y: int,
    width: int,
    height: int,
) -> None:
    """Render the message log in the given rectangle."""
    world = registry[None]
    log = world.components.get(MessageLog)
    if log is None:
        return

    messages_to_show = log.messages[-height:]

    for i, msg in enumerate(messages_to_show):
        console.print(
            x=x,
            y=y + i,
            string=msg.text[:width],
            fg=msg.color,
        )
```

A typical layout allocates the bottom three rows for messages. Three rows show the most recent combat actions. Older messages scroll off the top but remain in the log for later review.

## The Fighter Component Revisited

The `Fighter` component from Chapter 6 stores base combat stats. It needs fields for temporary modifiers:

```python
# src/components/combat.py

import attrs


@attrs.define
class Fighter:
    """Combat statistics for an entity that can fight."""
    hp: int = 10
    max_hp: int = 10
    power: int = 3
    defense: int = 0

    # Temporary modifiers (set by buffs/debuffs)
    power_bonus: int = 0
    defense_bonus: int = 0
```

The `power_bonus` and `defense_bonus` fields are temporary modifiers applied by status effects, spells, or environmental conditions. They are separate from equipment bonuses.

### Buff and Debuff Preview

These bonus fields are the foundation for a buff and debuff system. A buff temporarily increases a stat; a debuff decreases it. Here is a preview using a `StatusEffect` component:

```python
@attrs.define
class StatusEffect:
    """A temporary effect applied to an entity."""
    effect_type: str = ""
    duration: int = 0
    power: int = 0


def apply_buff(
    entity: tcod.ecs.Entity, effect_type: str, power: int, duration: int
) -> None:
    """Apply a temporary buff to an entity."""
    effect = StatusEffect(effect_type=effect_type, duration=duration, power=power)

    if effect_type == "strength":
        entity.components[Fighter].power_bonus += power
    elif effect_type == "shield":
        entity.components[Fighter].defense_bonus += power

    entity.components[StatusEffect] = effect


def tick_effects(entity: tcod.ecs.Entity) -> None:
    """Decrement effect durations and remove expired effects."""
    effect = entity.components.get(StatusEffect)
    if effect is None:
        return

    effect.duration -= 1
    if effect.duration <= 0:
        if effect.effect_type == "strength":
            entity.components[Fighter].power_bonus -= effect.power
        elif effect.effect_type == "shield":
            entity.components[Fighter].defense_bonus -= effect.power

        entity.components.pop(StatusEffect, None)
```

The effect modifies `Fighter` bonuses when applied and reverses the modification when it expires. `tick_effects` runs during the world-effects phase of the turn cycle.

### Equipment Bonuses

Equipment bonuses are calculated at attack time by `get_effective_power` and `get_effective_defense`. The `Item` component stores the bonuses:

```python
@attrs.define
class Item:
    """Marks an entity as a pickupable item."""
    name: str = ""
    use_function: str = ""
    value: int = 0
    slot: str = ""
    power_bonus: int = 0
    defense_bonus: int = 0
```

The combat system reads `power_bonus` and `defense_bonus` from equipped items. The full equipment system is covered in Chapter 18.

## Integrating with the Game Loop

The combat system plugs into the game loop from Chapter 12. The attack function is called during action processing and enemy turns. The message log is rendered every frame. Dead entity cleanup runs at the end of each turn cycle:

```python
if turn_consumed:
    process_enemy_turns(registry, dungeon, player)
    tick_all_effects(registry)
    advance_turn(registry)
    update_fov(dungeon, player)
    check_dead_entities(registry)

    if check_game_over(registry, player):
        return
```

Combat messages accumulate in the `MessageLog` during action processing and enemy turns. When the screen is redrawn, the message log renderer displays them with their colors.

## Complete Combat Module

```python
# src/systems/combat.py

from __future__ import annotations

import random
from typing import TYPE_CHECKING

import tcod.ecs

from components import Equipment, Fighter, Inventory, Item, Name, Position, XP
from systems.ui import add_message

if TYPE_CHECKING:
    pass


COLOR_DAMAGE = (255, 80, 80)
COLOR_HEAL = (80, 255, 80)
COLOR_CRITICAL = (255, 255, 0)
COLOR_DEATH = (255, 0, 0)
COLOR_LOOT = (255, 200, 0)
COLOR_DEFAULT = (200, 200, 200)


def get_effective_power(entity: tcod.ecs.Entity) -> int:
    """Calculate total power including Fighter bonuses and equipment."""
    fighter = entity.components[Fighter]
    power = fighter.power + fighter.power_bonus

    equipment = entity.components.get(Equipment)
    if equipment is not None:
        for item_entity in equipment.slots.values():
            item = item_entity.components[Item]
            power += getattr(item, "power_bonus", 0)

    return power


def get_effective_defense(entity: tcod.ecs.Entity) -> int:
    """Calculate total defense including Fighter bonuses and equipment."""
    fighter = entity.components[Fighter]
    defense = fighter.defense + fighter.defense_bonus

    equipment = entity.components.get(Equipment)
    if equipment is not None:
        for item_entity in equipment.slots.values():
            item = item_entity.components[Item]
            defense += getattr(item, "defense_bonus", 0)

    return defense


def attack(
    attacker: tcod.ecs.Entity,
    target: tcod.ecs.Entity,
    registry: tcod.ecs.Registry,
) -> None:
    """Execute an attack from attacker against target."""
    atk_power = get_effective_power(attacker)
    tgt_defense = get_effective_defense(target)

    base_damage = max(1, atk_power - tgt_defense + random.randint(-1, 1))

    is_critical = random.random() < 0.1
    if is_critical:
        damage = int(base_damage * 1.5)
    else:
        damage = base_damage

    attacker_name = attacker.components[Name].name
    target_name = target.components[Name].name

    if "player" in attacker.tags:
        prefix = "You"
    else:
        prefix = f"The {attacker_name}"

    if "player" in target.tags:
        suffix = "you"
    else:
        suffix = f"the {target_name}"

    if is_critical:
        message = (
            f"{prefix} land"
            f"{'s' if 'player' not in attacker.tags else ''}"
            f" a critical hit on {suffix} for {damage} damage!"
        )
        color = COLOR_CRITICAL
    else:
        message = (
            f"{prefix} attack"
            f"{'s' if 'player' not in attacker.tags else ''}"
            f" {suffix} for {damage} damage."
        )
        color = COLOR_DAMAGE

    target.components[Fighter].hp -= damage
    add_message(registry, message, color)

    if target.components[Fighter].hp <= 0:
        handle_death(target, registry)


def handle_death(entity: tcod.ecs.Entity, registry: tcod.ecs.Registry) -> None:
    """Process the death of an entity."""
    name = entity.components[Name].name

    if "player" in entity.tags:
        add_message(registry, "You have died!", COLOR_DEATH)
        entity.tags.add("dead")
        return

    add_message(registry, f"The {name} is dead!", COLOR_DEATH)

    roll_loot(entity, registry)
    drop_inventory(entity, registry)

    entity.tags.discard("blocks_movement")
    entity.tags.discard("enemy")
    entity.tags.add("dead")

    player = registry.Q.one(tags=["player"])
    xp = player.components.get(XP)
    if xp is not None:
        fighter = entity.components[Fighter]
        xp_gain = 10 + fighter.max_hp
        xp.current += xp_gain
        add_message(
            registry,
            f"You gain {xp_gain} experience points.",
            COLOR_LOOT,
        )


def drop_inventory(entity: tcod.ecs.Entity, registry: tcod.ecs.Registry) -> None:
    """Drop all items from a dead entity's inventory onto the ground."""
    inventory = entity.components.get(Inventory)
    if inventory is None:
        return

    pos = entity.components[Position]

    for item_entity in inventory.items:
        item_entity.components[Position] = Position(x=pos.x, y=pos.y)
        item_entity.tags.discard("in_inventory")
        item_entity.tags.add("item")

    inventory.items.clear()
```

This module is self-contained. Other systems call `attack` when a bump collision occurs or when an AI decides to attack. All combat state changes flow through this module.

## Exercises

**Exercise 1: Implement a Dodge System**

Add a `speed` field to the `Fighter` component. When an attack is processed, compare the attacker's speed to the defender's speed. If the defender's speed exceeds the attacker's by a threshold (e.g., 5 or more), there is a chance the attack misses entirely. A miss prints "The kobold dodges your attack!" and deals no damage. Experiment with different threshold values to find what feels fair. Consider how dodge interacts with defense---should a fast, heavily armored entity be nearly untouchable?

**Exercise 2: Add Elemental Damage Types**

Extend the damage system to support fire, ice, and lightning. Add an `element` field to the `Item` component for weapons. Modify the attack function to apply elemental damage as a bonus on top of physical damage. Add resistance fields to the `Fighter` component: `fire_resistance`, `ice_resistance`, `lightning_resistance`. An entity with fire resistance 50 takes half damage from fire attacks. Display the element in the combat message: "Your flaming sword burns the orc for 7 fire damage!"

**Exercise 3: Create a Combat Log**

Implement a combat log that can be reviewed after combat. Create a separate `CombatLog` component on the world entity that stores every combat event in the current fight. When the player presses a key (e.g., `L`), display the full combat history. Clear the log when the player moves to a new floor or after 20 turns without combat. This gives the player a way to review what happened and learn from their mistakes.

**Exercise 4: Damage Number Animation**

When damage is dealt, briefly display the damage number on the target's tile. Create a `DamageNumber` component with a position, text, and a frame counter. The render system checks for entities with `DamageNumber` and draws the number above the entity's tile. The frame counter decrements each render, and the component is removed when it reaches zero. Critical hits should display in a brighter style.

**Exercise 5: Multi-Hit Attacks**

Some weapons should attack multiple times per turn. Add a `hits` field to the `Item` component (default 1). When a weapon with `hits=2` is equipped, the attack function executes twice, each hit independent with its own damage roll and crit chance. Modify the attack message: "You strike the orc twice for 4 and 5 damage!" Implement this by calling the damage calculation in a loop within the attack function.

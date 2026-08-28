# Chapter 15: Items and Inventory

Combat in Chapter 13 and the monster AI in Chapter 14 gave the player enemies to fight and ways to lose health, but no way to get it back. The player's health potion was a fixed, hard-coded survival mechanic---no spare to carry, no choice about when to drink it, no scroll to end a fight from a distance. The game is a series of unavoidable melee exchanges with no resource management.

This chapter turns consumables into a real system. We add an `Item` component that marks anything the player can carry, a `Consumable` component that describes what an item does when used, and an `Inventory` component that limits what the player can hold. We implement picking up with `g`, using with the `1-9` number keys, dropping with `d`, and an inventory panel that lists everything carried. By the end, the player navigates the dungeon making real decisions: drink that potion now or save it, burn the fireball scroll on a crowded room or hoard it for a boss. Before this chapter the only decision was move or attack; now there are choices layered on top of every encounter.

## Item Design Philosophy

Items create meaningful choices. The simplest way to make an item interesting is to make it limited and to make using it cost something. A potion that healed the player to full with no downside would be trivially spammed. A potion that heals a flat amount, occupies inventory space, and disappears when drunk forces the player to think about *when*.

Consumables are used once. Every potion and scroll is a decision about the present versus the future. Drink the potion now to survive this fight, or save it for the worse fight you know is coming? Because a consumable vanishes on use, there is no way to "optimize later"---every use permanently spends the resource, so the player must make the call now. Equipment stays equipped permanently (we cover it in Chapter 16); consumables are about *when* to act, equipment is about *what the character is*.

The inventory limit forces the player to choose carefully. With a capacity of ten, the player cannot carry everything they find. A clutter of potions crowds out scrolls; a full inventory means picking up something new requires dropping something old. The limit is the pressure valve that makes item variety matter---without it, the player would hoard everything and never decide.

Three design rules guide the implementation. **Items must be discoverable**, so the player can tell what an item is from its tile glyph and its description. **Items must be predictable**, so a fireball scroll behaves the same way every time it is used. **The inventory must be legible**, because a list the player can read, number, and reason about in a second is more valuable than a powerful system the player cannot parse.

## Item Components

Items are entities with several attrs components. The three that matter for this chapter are `Item`, `Consumable`, and `Inventory`.

The `Item` component marks an entity as something that can be picked up and carried. It holds display data---a name and a description---so the inventory panel and message log can refer to it without coupling to rendering internals:

```python
# src/components.py

import attrs


@attrs.define
class Item:
    """Marks an entity as a ground or carried item."""

    name: str = ""
    description: str = ""
```

The `Consumable` component describes what an item does when it is used. Rather than storing a raw function, it stores an effect enum plus the numeric parameters that effect needs. This is data-driven: a factory decides what an item does by choosing an effect and tuning the numbers, and the use system dispatches on the enum.

```python
from enum import Enum


class ConsumableEffect(Enum):
    HEAL = "heal"
    LIGHTNING = "lightning"
    FIREBALL = "fireball"
    CONFUSION = "confusion"


@attrs.define
class Consumable:
    """Describes what an item does when used."""

    effect: ConsumableEffect = ConsumableEffect.HEAL
    amount: int = 10      # Heal amount, lightning/fireball damage
    radius: int = 3       # Fireball blast radius
    range: int = 5        # Lightning bolt maximum reach
    duration: int = 10    # Confusion duration in turns
```

Notice what each field means changes with the effect. For a health potion, `amount` is how much HP is restored. For a lightning scroll, `amount` is the bolt's damage and `range` is how far it reaches. For a fireball, `amount` is the blast damage and `radius` is the blast radius. For a confusion scroll, `duration` is how many turns the target wanders. One component carries everything a consumable needs without demanding irrelevant fields be filled.

Finally, the `Inventory` component is attached to the player and holds the list of carried item entities, bounded by a capacity:

```python
@attrs.define
class Inventory:
    items: list = attrs.Factory(list)
    capacity: int = 10
```

The inventory is a plain list of entity references. Order matters---the number keys `1-9` address items by their index in this list, so stable ordering is what makes the inventory panel and the use/drop commands agree about what an item is.

The player is created with an empty inventory in the actor factory:

```python
# src/factories/actors.py

from components import Inventory

# ...

def create_player(
    registry: tcod.ecs.Registry, x: int, y: int, inventory_capacity: int = 10
) -> tcod.ecs.Entity:
    player = registry.new_entity()
    player.components |= {
        Position: Position(x=x, y=y),
        Renderable: Renderable(char="@", fg=(255, 255, 255), render_order=10),
        Name: Name(name="Player"),
        Fighter: Fighter(hp=30, max_hp=30, power=5, defense=2),
        XP: XP(current=0, level=1, xp_to_next=100, xp_value=0),
        Inventory: Inventory(items=[], capacity=inventory_capacity),
    }
    player.tags.add("player")
    return player
```

The `Inventory` component is a pure container. It knows nothing about the map, rendering, or item use. All of that lives in the item system, which reads the inventory and decides what to do.

## Picking Up Items

Pressing `g` picks up the first item on the player's tile. The input handler translates the key into a `PickupAction`:

```python
# src/input_handlers.py

from actions import PickupAction

# Inside handle_input:
    # Pick up an item.
    elif event.sym == tcod.event.KeySym.g:
        return PickupAction(entity=entity)
```

The action carries only the entity that performed it. It has no coordinates and no reference to the item---the pickup logic figures those out. The action class is deliberately thin:

```python
# src/actions.py

import attrs


@attrs.define
class PickupAction(Action):
    """Pick up whatever item is on the actor's tile."""

    pass
```

The actual work happens in `items.py`. The pickup function queries the registry for items at the player's position, checks capacity, and moves the first match into the inventory:

```python
# src/items.py

from tcod.ecs import Entity

from components import Inventory, Item, Position
from message_log import MessageLog


def pickup_item(registry: tcod.ecs.Registry, player: Entity, log: MessageLog) -> bool:
    """Pick up the first item on the player's tile, if any."""
    inv = player.components[Inventory]
    ppos = player.components[Position]

    for item_entity, ipos, item in registry.Q[Entity, Position, Item]:
        if ipos.x == ppos.x and ipos.y == ppos.y:
            if len(inv.items) >= inv.capacity:
                log.add("Your inventory is full.", fg=(255, 100, 100))
                return False
            inv.items.append(item_entity)
            # Carried items lose their map position but keep their identity,
            # so they render inside the inventory panel instead of the floor.
            item_entity.components.pop(Position, None)
            item_entity.tags.discard("item")
            item_entity.tags.add("inventory")
            log.add(f"You pick up the {item.name}.", fg=(200, 200, 200))
            return True

    log.add("There is nothing here to pick up.", fg=(200, 200, 200))
    return False
```

The `registry.Q[Entity, Position, Item]` query returns `(entity, Position, Item)` for every entity with all three components; we look for one at the player's tile. Two subtle things happen on a successful pickup. First, the item's `Position` component is removed (`item_entity.components.pop(Position, None)`). This is the ECS-clean way to say "no longer on the map"---the item stops matching the `Position` query, so every system that iterates map entities automatically stops seeing it. The `None` default guards against an item with no position.

Second, we swap tags: the item loses `"item"` and gains `"inventory"`. Tags mark broad lifecycle state---tagged `"item"` means on the floor, tagged `"inventory"` means carried. Combined with the removed `Position`, a carried item is never mistaken for floor loot.

The function returns a boolean. `True` means a turn was spent; `False` means nothing happened and the world should not advance. This convention is shared by every action processor in `main.py` and is what stops a failed pickup on an empty tile from letting monsters act for free. The capacity check runs *before* the item is appended, so a full inventory logs a message and returns `False` without consuming the turn.

## Using Items

Pressing one of the number keys `1-9` uses the item in that inventory slot. The input handler maps the top-row number keys to zero-based index slots:

```python
# src/input_handlers.py

# Maps the top-row number keys '1'..'9' to inventory slot indices 0..8.
NUMBER_KEYS: dict[tcod.event.KeySym, int] = {
    getattr(tcod.event.KeySym, f"N{i}"): i - 1 for i in range(1, 10)
}
```

This builds the mapping programmatically: `KeySym.N1` maps to index `0`, `KeySym.N2` to index `1`, and so on up to the ninth key, subtracting one to convert the human one-based choice to a Python zero-based list index.

When a number key is pressed outside a menu, the handler emits a `UseItemAction`:

```python
from actions import UseItemAction

# Omit the pickup code for brevity; the relevant branch is:

    if event.sym in NUMBER_KEYS:
        return UseItemAction(entity=entity, index=NUMBER_KEYS[event.sym])
```

The main loop dispatches the action to the item system:

```python
# src/main.py

from items import drop_item, pickup_item, use_item

# ...

def _is_action_success(
    action: Action,
    registry: tcod.ecs.Registry,
    dungeon: GameMap,
    log: MessageLog,
    player,
) -> bool:
    """Process a player action. Returns True if a turn was spent."""
    if isinstance(action, BumpAction):
        return process_bump(registry, dungeon, player, action.dx, action.dy, log)
    if isinstance(action, WaitAction):
        return True
    if isinstance(action, PickupAction):
        return pickup_item(registry, player, log)
    if isinstance(action, UseItemAction):
        return use_item(registry, player, action.index, dungeon, log)
    if isinstance(action, DropAction) and action.index >= 0:
        return drop_item(registry, player, action.index, log)
    return False
```

The `use_item` function is the heart of the use system. It validates the slot, checks that the item is a consumable, dispatches to the right effect, and removes the item from the inventory if the effect succeeded:

```python
# src/items.py

from components import Consumable


def use_item(
    registry: tcod.ecs.Registry,
    player: Entity,
    item_index: int,
    game_map: GameMap,
    log: MessageLog,
) -> bool:
    """Use a consumable item from the inventory. Returns True on success."""
    inv = player.components[Inventory]
    if inv is None:
        return False
    if not (0 <= item_index < len(inv.items)):
        log.add("You have nothing there.", fg=(200, 200, 200))
        return False

    item = inv.items[item_index]
    if Consumable not in item.components:
        log.add("There is nothing to use there.", fg=(200, 200, 200))
        return False

    consumable = item.components[Consumable]
    handlers = {
        ConsumableEffect.HEAL: _use_heal,
        ConsumableEffect.LIGHTNING: _use_lightning,
        ConsumableEffect.FIREBALL: _use_fireball,
        ConsumableEffect.CONFUSION: _use_confusion,
    }
    handler = handlers.get(consumable.effect)
    if handler is None:
        return False

    name = item.components[Name].name if Name in item.components else "item"
    if handler(registry, player, consumable, game_map, log):
        inv.items.pop(item_index)
        item.components.clear()
        item.tags.clear()
        log.add(f"You use the {name}.", fg=(200, 180, 50))
        return True
    return False
```

The dispatch table is the ECS-flavored equivalent of a `use_function` field. Instead of storing a Python callable on the component (awkward to serialize, hard to reason about), the table maps the `ConsumableEffect` enum to the function that implements it, looked up at use time. This keeps `Consumable` purely data and the behavior in one place.

Consumable items are removed after use. When the handler returns `True`, the item is popped from the inventory list and its components and tags are cleared. The entity object still exists but is now empty---no `Item`, no `Name`, no `Renderable`, no `Position`. It no longer matches any query and the registry eventually reaps it. We call this "consuming" the item.

The removal only happens when the handler *succeeds*. Drinking a potion at full health makes `_use_heal` return `False`, so the item stays and the turn is not spent. This guard prevents wasting scarce resources on no-ops and keeps the player from accidentally destroying an item they meant to keep.

## Item Types

The consumables available in this chapter share a common factory helper. Each type is a thin wrapper around `_make_consumable`, which assembles the item's components and tags:

```python
# src/factories/items.py

import random

from components import (
    Consumable,
    ConsumableEffect,
    Description,
    Item,
    Name,
    Position,
    Renderable,
)

# ...

def _make_consumable(
    registry: tcod.ecs.Registry,
    x: int,
    y: int,
    char: str,
    fg: tuple[int, int, int],
    name: str,
    description: str,
    consumable: Consumable,
) -> tcod.ecs.Entity:
    """Shared helper that builds a consumable item entity."""
    entity = registry.new_entity()
    entity.components |= {
        Position: Position(x=x, y=y),
        Renderable: Renderable(char=char, fg=fg),
        Name: Name(name=name),
        Description: Description(text=description),
        Item: Item(name=name, description=description),
        Consumable: consumable,
    }
    entity.tags.add("item")
    return entity
```

Every item gets a `Position` and `Renderable` (so it appears on the floor as a glyph), a `Name` and `Description` (so the inventory panel and log can refer to it), an `Item` (so it can be picked up), and a `Consumable` (so it can be used). The `"item"` tag places it on the floor. Equipment---permanent stat items like a dagger or leather armor---is deliberately left for Chapter 16, which covers the equipment and stat systems in detail.

### Health Potion

The survival staple. A `"!"` glyph, green coloring, and a heal effect with an `amount` default of 25:

```python
def create_health_potion(
    registry: tcod.ecs.Registry, x: int, y: int, amount: int = 25
) -> tcod.ecs.Entity:
    """Spawn a health potion item at the given tile."""
    return _make_consumable(
        registry,
        x,
        y,
        char="!",
        fg=(0, 200, 0),
        name="Health Potion",
        description=f"Restores {amount} HP when drunk.",
        consumable=Consumable(effect=ConsumableEffect.HEAL, amount=amount),
    )
```

The player also starts with one in hand. In `main.py`, after the dungeon and item population are generated, a starter potion is created and immediately placed into the inventory:

```python
# src/main.py

from components import Inventory
from factories.items import create_health_potion

# Give the player a health potion to start with.
starter = create_health_potion(registry, player_x, player_y)
player.components[Inventory].items.append(starter)
starter.components.clear()
starter.tags.clear()
```

The potion is created at the player's coordinates, then its `Position` and `"item"` tag are stripped so it begins life as a carried item rather than floor loot sitting on the player's own tile.

### Scroll of Lightning

A single-target burst that strikes the nearest visible enemy the player can see. Its glyph is a `"~"` scroll in yellow. A bolt has an `amount` (the damage) and a `range` (how far it can reach):

```python
def create_lightning_scroll(
    registry: tcod.ecs.Registry,
    x: int,
    y: int,
    damage: int = 20,
    reach: int = 5,
) -> tcod.ecs.Entity:
    """Spawn a scroll that zaps the nearest visible enemy."""
    return _make_consumable(
        registry,
        x,
        y,
        char="~",
        fg=(255, 255, 0),
        name="Lightning Scroll",
        description=f"Strikes the nearest visible enemy for {damage} damage.",
        consumable=Consumable(
            effect=ConsumableEffect.LIGHTNING, amount=damage, range=reach
        ),
    )
```

The use handler finds the nearest visible enemy within `range` tiles, deals `amount` damage to it, and reports the result in yellow:

```python
def _use_lightning(
    registry: tcod.ecs.Registry,
    player: Entity,
    consumable: Consumable,
    game_map: GameMap,
    log: MessageLog,
) -> bool:
    target = _nearest_visible_enemy(registry, game_map, player, consumable.range)
    if target is None:
        log.add("No enemy is within range.", fg=(200, 200, 200))
        return False
    name = target.components[Name].name
    dealt = damage(target, consumable.amount, log)
    log.add(f"A lightning bolt strikes the {name} for {dealt} damage!", fg=(255, 255, 0))
    return True
```

If no enemy is in range, the handler logs that and returns `False`, so the scroll is not consumed. This is a kindness to the player: an unusable scroll should not disappear.

### Scroll of Fireball

An area-of-effect blast centered on the nearest visible enemy. It has an `amount` (the damage), a `radius` (the blast radius in tiles), and a generous `range` of 8 so it can reach across a room:

```python
def create_fireball_scroll(
    registry: tcod.ecs.Registry,
    x: int,
    y: int,
    damage: int = 12,
    radius: int = 3,
) -> tcod.ecs.Entity:
    """Spawn a scroll that blasts enemies around the nearest target."""
    return _make_consumable(
        registry,
        x,
        y,
        char="~",
        fg=(255, 0, 0),
        name="Fireball Scroll",
        description=f"Deals {damage} damage in a radius {radius} blast.",
        consumable=Consumable(
            effect=ConsumableEffect.FIREBALL, amount=damage, radius=radius, range=8
        ),
    )
```

The handler finds the target enemy as the blast center, then damages every other entity within the radius:

```python
from components import Fighter


def _use_fireball(
    registry: tcod.ecs.Registry,
    player: Entity,
    consumable: Consumable,
    game_map: GameMap,
    log: MessageLog,
) -> bool:
    center = _nearest_visible_enemy(registry, game_map, player, consumable.range)
    if center is None:
        log.add("No enemy is within range.", fg=(200, 200, 200))
        return False
    cx, cy = center.components[Position].x, center.components[Position].y

    hit_any = False
    for entity, pos, fighter in registry.Q[Entity, Position, Fighter]:
        if entity is player or fighter.hp <= 0:
            continue
        dist_sq = (pos.x - cx) ** 2 + (pos.y - cy) ** 2
        if dist_sq <= consumable.radius ** 2:
            damage(entity, consumable.amount, log)
            hit_any = True

    if not hit_any:
        log.add("The fireball engulfs you! (missed)", fg=(255, 255, 0))
        return True
    return True
```

The distance check avoids a square root by comparing squared distances: an entity at radius exactly `3` tiles away has `dist_sq = 9`, which is `<= 3 ** 2`, so it is included. The fireball can never hit the player---`if entity is player: continue` skips them, making it a safe, player-friendly blast. The "missed" branch fires when the blast lands where an enemy was expected but none now stands; the scroll is still consumed, since a cast was attempted.

### Scroll of Confusion

Turns the nearest visible enemy into a random wanderer for a fixed number of turns. It carries a `duration` and a `range`:

```python
def create_confusion_scroll(
    registry: tcod.ecs.Registry,
    x: int,
    y: int,
    duration: int = 10,
) -> tcod.ecs.Entity:
    """Spawn a scroll that confuses the nearest visible enemy."""
    return _make_consumable(
        registry,
        x,
        y,
        char="~",
        fg=(200, 120, 255),
        name="Confusion Scroll",
        description=f"Confuses the nearest visible enemy for {duration} turns.",
        consumable=Consumable(
            effect=ConsumableEffect.CONFUSION, duration=duration, range=5
        ),
    )
```

The handler swaps the target's AI kind to `CONFUSED`, stashing the old kind and recording the remaining duration:

```python
from components import AI, AIKind


def _use_confusion(
    registry: tcod.ecs.Registry,
    player: Entity,
    consumable: Consumable,
    game_map: GameMap,
    log: MessageLog,
) -> bool:
    target = _nearest_visible_enemy(registry, game_map, player, consumable.range)
    if target is None:
        log.add("No enemy is within range.", fg=(200, 200, 200))
        return False
    ai = target.components[AI]
    ai.previous_kind = ai.kind
    ai.kind = AIKind.CONFUSED
    ai.confused_turns = consumable.duration
    name = target.components[Name].name
    log.add(f"The {name} starts wandering in a daze!", fg=(255, 100, 255))
    return True
```

The confused behavior itself lives in the AI system from Chapter 14. Each turn, a confused enemy decrements `confused_turns` and wanders randomly; when it reaches zero, it reverts to `previous_kind`. The scroll just sets up the state. This is a clean separation: the item system says *what* to do, the AI system already knew *how* to wander, and the two connect through the `AI` component.

## Drop Items

Pressing `d` opens the drop menu, then pressing a number drops that item onto the floor at the player's position. The input handler distinguishes two cases with a single `DropAction` whose `index` means different things:

```python
# src/actions.py

import attrs


@attrs.define
class DropAction(Action):
    """Drop the inventory item at the given index onto the floor.

    An index of -1 signals "open the drop menu" (no turn is spent).
    """

    index: int = -1
```

Inside `handle_input`, when drop mode is active the number keys produce a concrete `DropAction`:

```python
# src/input_handlers.py

from actions import DropAction

def handle_input(
    event: tcod.event.KeyDown,
    entity: tcod.ecs.Entity,
    drop_mode: bool = False,
) -> Action | None:
    """Convert a key event into an action for the given entity.

    When drop_mode is True, the number keys 1-9 produce DropAction instances
    so the player can choose which item to drop.
    """
    # ... movement and pickup branches omitted ...

    # In the drop menu, the number keys choose which item to drop.
    if drop_mode:
        if event.sym in NUMBER_KEYS:
            return DropAction(entity=entity, index=NUMBER_KEYS[event.sym])
        return None

    # Out of the drop menu: 'd' opens it and 1-9 use an inventory item.
    if event.sym == tcod.event.KeySym.d:
        return DropAction(entity=entity, index=-1)
    if event.sym in NUMBER_KEYS:
        return UseItemAction(entity=entity, index=NUMBER_KEYS[event.sym])
    return None
```

The `drop_mode` flag is what changes the meaning of the number keys. Outside drop mode, `1-9` means "use this item." Inside drop mode, `1-9` means "drop this item." The `d` key alone returns a `DropAction` with index `-1`, which the main loop interprets as "enter drop mode," not "drop item minus-one."

The main loop manages the drop-mode state machine:

```python
# src/main.py

if drop_mode:
    action = handle_input(event, player, drop_mode=True)
    if isinstance(action, DropAction) and action.index >= 0:
        spent = _is_action_success(
            action, registry, dungeon, log, player
        )
        drop_mode = False
        show_inventory = False
        if not spent:
            needs_render = True
            continue
        _advance_after_turn(
            registry, dungeon, log, player, graph
        )
        needs_render = True
    else:
        needs_render = True
    continue

if event.sym == tcod.event.KeySym.d:
    if len(player.components[Inventory].items) > 0:
        drop_mode = True
        show_inventory = True
        needs_render = True
    continue
```

Pressing `d` when the inventory is not empty enters drop mode and shows the inventory panel. From there the player picks a number, the drop resolves, and drop mode exits. Pressing `d` with an empty inventory does nothing. ESC exits drop mode without dropping anything (handled earlier in the main loop).

The drop itself reverses the pickup process. `drop_item` pops the item out of the inventory, gives it a `Position` at the player's tile, and flips its tags back to `"item"`:

```python
from components import Name


def drop_item(
    registry: tcod.ecs.Registry, player: Entity, item_index: int, log: MessageLog
) -> bool:
    """Drop the inventory item at the given index onto the current tile."""
    inv = player.components[Inventory]
    if not (0 <= item_index < len(inv.items)):
        return False

    item = inv.items.pop(item_index)
    ppos = player.components[Position]
    item.components[Position] = Position(x=ppos.x, y=ppos.y)
    item.tags.discard("inventory")
    item.tags.add("item")
    name = item.components[Name].name if Name in item.components else "Unknown"
    log.add(f"You drop the {name}.", fg=(200, 200, 200))
    return True
```

The item lands on the player's own tile. Because pickup scans for items at the player's position, the player can walk away and come back, or immediately pick the item up again with `g`. Dropping is the release valve for a full inventory: a player who finds something better while carrying ten items drops one to make room.

Note that dropping spends a turn (`True` is returned and the world advances), while opening the drop menu with `d` does not. The player can open and cancel the menu freely, but actually committing to a drop advances the game.

## Inventory UI

Two panels communicate the inventory state. The HUD, always visible at the bottom of the screen, shows the count against capacity:

```python
# src/render_functions.py

def render_hud(
    console: tcod.console.Console,
    registry: tcod.ecs.Registry,
    player: tcod.ecs.Entity,
    game_map: GameMap,
    x: int,
    y: int,
    width: int,
    drop_mode: bool = False,
) -> None:
    """Render the player status line and inventory summary."""
    fighter = player.components[Fighter]
    xp = player.components.get(XP)
    hp_text = f"HP: {fighter.hp}/{fighter.max_hp}"
    if xp is not None:
        hp_text += f"  LVL: {xp.level}  XP: {xp.current}/{xp.xp_to_next}"

    inv = player.components.get(Inventory)
    if inv is not None:
        hp_text += f"  [I]nv: {len(inv.items)}/{inv.capacity}"

    console.print(x=x, y=y, string=hp_text, fg=(255, 255, 255))

    mode_text = "DROP MODE: press 1-9 to drop, ESC to cancel" if drop_mode else (
        "g:pickup  d:drop  i:inv  1-9:use  .:wait  arrows/vi:move"
    )
    console.print(x=x, y=y + 1, string=mode_text[: width - 1], fg=(180, 180, 180))
```

The HUD tells the player how many of ten slots are occupied at a glance. It also changes its hint line in drop mode so the player knows the number keys now mean "drop."

Pressing `i` opens the full inventory panel. `render_inventory` draws a centered, bordered pop-up listing every carried item with a slot number:

```python
def render_inventory(
    console: tcod.console.Console,
    player: tcod.ecs.Entity,
    drop_mode: bool = False,
) -> None:
    """Render a pop-up panel listing the player's inventory."""
    inv = player.components[Inventory] if Inventory in player.components else None
    if inv is None:
        return

    width = 34
    height = max(7, min(20, len(inv.items) + 5))
    x = console.width // 2 - width // 2
    y = console.height // 2 - height // 2

    title = "Drop which item?" if drop_mode else "Inventory"
    console.draw_frame(x=x, y=y, width=width, height=height, title=title)

    if not inv.items:
        console.print(x=x + 2, y=y + 2, string="Your inventory is empty.",
                      fg=(200, 200, 200))
        if drop_mode:
            console.print(x=x + 2, y=y + 3, string="Press ESC to cancel.",
                          fg=(180, 180, 180))
        return

    max_rows = height - 3
    for i, item in enumerate(inv.items[:max_rows]):
        name = item.components[Name].name if Name in item.components else "Unknown"
        row = f"[{i + 1}] {name}"
        fg = (255, 255, 0) if drop_mode else (200, 200, 200)
        console.print(x=x + 2, y=y + 2 + i, string=row[: width - 4], fg=fg)

    hint = "Press 1-9 to drop, ESC to cancel" if drop_mode else "Press 1-9 to use"
    console.print(x=x + 2, y=y + height - 2, string=hint, fg=(180, 180, 180))
```

Each row shows the slot number in brackets (`[1] Health Potion`) followed by the item name. The highlighted color changes in drop mode to make the intent obvious. The panel height grows with the number of items, capped so it never swallows the screen. The same panel serves double duty: it lists items for using and, in drop mode, for dropping.

The `render_all` orchestrator draws the map, entities, HUD, and message log as before, then overlays the inventory panel only when a flag is set. The item-relevant tail is simply:

```python
# render_all (excerpt): only the item-related branch.
if show_inventory or drop_mode:
    render_inventory(console, player, drop_mode=drop_mode)
```

The panel overlays the map and entities, giving the player a modal moment to review their items before choosing one.

## The Use Item System

The use system is the dispatcher that turns an inventory selection and an `Index` into a real game effect. It is split into three layers.

The **entry point** is `use_item`, which validates the selection and looks up a handler. We saw it above; its job is coordination, not effect logic. It answers three questions in order: Is there an item in that slot? Is it a consumable? Does it have a known effect? Only when all three answers are "yes" does it delegate to a handler and, on success, remove the item.

The **handlers** are the per-effect functions `_use_heal`, `_use_lightning`, `_use_fireball`, and `_use_confusion`. Each takes the same signature---`registry`, `player`, `consumable`, `game_map`, `log`---reads what it needs from the `consumable` component, and applies the effect. Two of them delegate further:

```python
def _use_heal(
    registry: tcod.ecs.Registry,
    player: Entity,
    consumable: Consumable,
    game_map: GameMap,
    log: MessageLog,
) -> bool:
    return heal(player, consumable.amount, log)
```

`_use_heal` is a one-line pass-through to the `heal` helper in `combat.py`. Healing is already a well-defined operation from Chapter 13; the item handler just parameterizes it with the consumable's `amount`:```python
# src/combat.py

def heal(entity: Entity, amount: int, log: MessageLog) -> bool:
    """Restore an entity's HP. Returns True if any HP was restored."""
    fighter = entity.components[Fighter]
    amount = min(amount, fighter.max_hp - fighter.hp)
    if amount <= 0:
        return False
    fighter.hp += amount
    log.add(f"You feel your wounds close. (+{amount} HP)", fg=(0, 255, 0))
    return True
```

`heal` caps the amount so the player never exceeds `max_hp`, and returns `False` if nothing was restored---so a full-health potion use is rejected upstream and the potion is preserved.

The **targeting helper** `_nearest_visible_enemy` is shared by lightning, fireball, and confusion. It scans every fighter-bearing entity and returns the closest one that the player can see and that is within range:

```python
def _nearest_visible_enemy(
    registry: tcod.ecs.Registry,
    game_map: GameMap,
    player: Entity,
    max_range: int,
) -> Entity | None:
    """Find the closest enemy within range that the player can see."""
    ppos = player.components[Position]
    best: Entity | None = None
    best_distance: int | None = None

    for entity, pos, fighter in registry.Q[Entity, Position, Fighter]:
        if entity is player or fighter.hp <= 0:
            continue
        if not game_map.in_bounds(pos.x, pos.y):
            continue
        if not game_map.visible[pos.y, pos.x]:
            continue
        dist = abs(pos.x - ppos.x) + abs(pos.y - ppos.y)
        if dist > max_range:
            continue
        if best_distance is None or dist < best_distance:
            best_distance = dist
            best = entity
    return best
```

Three filters decide eligibility: the enemy must be alive, must be within the map bounds, and must be inside the field of view (`game_map.visible`). The player cannot zap or blast an enemy they cannot see---no wall-hacking spells. Among the eligible enemies it picks the nearest by Manhattan distance (`|dx| + |dy|`), which matches how the game measures grid distances for targeting.

This is the complete use-item flow:

1. The player presses a number key, producing a `UseItemAction(index)`.
2. `main.py` routes it to `use_item`, which validates the slot and dispatches on the `ConsumableEffect`.
3. The handler targets (or heals) and applies the effect, returning success or failure.
4. On success, the item is removed from the inventory and its components cleared.
5. On failure, the item stays and nothing else changes.

The distinction between "use attempted" and "use succeeded" is what makes the system robust. A failed cast (no enemy in range, already at full health) does not destroy the item and does not advance the turn. A successful cast spends both the item and the turn---exactly the cost the player should pay.

## Scattering Items in the Dungeon

Items are useless if the player never finds any. The `place_items` factory walks every room but the player's starting room and scatters between one and three random consumables into each:

```python
# src/factories/items.py

def place_items(
    registry: tcod.ecs.Registry,
    dungeon: GameMap,
    skip_room: int = 0,
) -> None:
    """Scatter assorted consumables through every room but the start."""
    item_factories = [
        lambda reg, x, y: create_health_potion(reg, x, y),
        lambda reg, x, y: create_lightning_scroll(reg, x, y),
        lambda reg, x, y: create_fireball_scroll(reg, x, y),
        lambda reg, x, y: create_confusion_scroll(reg, x, y),
    ]

    for i, room in enumerate(dungeon.rooms):
        if i == skip_room:
            continue
        num_items = random.randint(1, 3)
        placed = 0
        attempts = 0
        while placed < num_items and attempts < 50:
            attempts += 1
            x = random.randint(room.x + 1, room.x + room.w - 2)
            y = random.randint(room.y + 1, room.y + room.h - 2)
            if _is_occupied(registry, x, y):
                continue
            factory = random.choice(item_factories)
            factory(registry, x, y)
            placed += 1
```

Like enemy placement in Chapter 14, items are placed within each room's inner bounds and skipped if a tile is already occupied, so an enemy never spawns on top of a potion. The `attempts` cap keeps the loop from spinning forever if a room is too crowded.

Item density follows the room count, so bigger dungeons are richer. Combined with the inventory capacity of ten, the player must be selective: a sprawling dungeon yields far more than ten items, and choosing what to take is a recurring decision that deepens the game.

## Integrating with the Main Loop

The item system slots into `main.py` through the existing action-processing pipeline from Chapter 12. There is no new loop and no special-case turn handling. The new actions are ordinary branches in `_is_action_success` (shown in the Using Items section), and the pickup/use/drop functions all return the boolean "was a turn spent" convention the loop already understands.

The inventory state flows through the render pipeline as two flags threaded from the event loop to `render_all`. `show_inventory` toggles with `i`; `drop_mode` toggles with `d`. Opening the inventory (or the drop menu) sets the flag and re-renders, but does not spend a turn and does not trigger the end-of-turn sequence. Only a successful pickup, use, or drop returns `True` from `_is_action_success`, which then runs the usual end-of-turn steps---FOV update, AI turns, enemy attacks, dead cleanup---exactly as in Chapter 12.

Because drinking a potion spends a turn, the trap is real: an enemy that was adjacent when you healed may bite you during the resolution that follows. Healing is a tactical choice with a cost in timing, not a free out-of-combat action.

There is one more seam worth noting. When a monster dies while carrying items, those items fall back to the floor through `_drop_carried_items` in `combat.py` (death drops were covered in Chapter 13):

```python
def _drop_carried_items(entity: Entity) -> None:
    """Put any items a dying entity carries back onto the floor."""
    from components import Inventory, Position

    if Inventory not in entity.components:
        return
    inv = entity.components[Inventory]
    pos = entity.components[Position] if Position in entity.components else None
    if pos is None:
        return
    for item in list(inv.items):
        item.components[Position] = Position(x=pos.x, y=pos.y)
        item.tags.add("item")
    inv.items.clear()
```

This uses the same tag-flipping and position-reinstating pattern as the player's `drop_item`, so any item a monster was carrying lands where it died and the player picks it up like any other floor loot. The inventory system and the death system share one mental model: an item on the floor has a `Position` and the `"item"` tag.

## Summary

Items and inventory turn a pure combat slog into a game of resource management. The `Item` component marks what can be carried. The `Consumable` component describes what an item does, using an effect enum plus its numeric parameters. The `Inventory` component imposes a capacity that forces choices.

Picking up (`g`) pulls item entities from the floor into the inventory by removing their `Position` and swapping tags. Using (`1-9`) validates the selection, dispatches on the `ConsumableEffect` enum, applies the effect, and consumes the item on success. Dropping (`d` then a number) reverses pickup, reinstating the item on the floor. The inventory UI---a HUD count plus a pop-up panel---keeps the player informed and lets them act with number keys.

The system's consistency comes from its two shared conventions: items on the floor always have a `Position` and the `"item"` tag, items in hand never do; and every action returns "did a turn happen so the world can advance." Everything else is a detail layered on top of those rules.

## Exercises

**Exercise 1: Add Unidentified Items**

Make some scrolls start unidentified. A scroll might be created with a `Name` of "Unidentified Scroll" and a `Description` of "A scroll of unknown magic." On the first use, reveal its true effect by replacing the `Name` and `Description` and logging a discovery message like "You identify the scroll as a Scroll of Fireball!" Add an `identified` boolean to the `Item` or `Consumable` component, and make `use_item` reveal the item before applying its effect. Consider whether the reveal should still consume the item or whether identifying something new should feel like getting more value for it.

**Exercise 2: Implement Item Stacking**

Make identical items stack in a single inventory slot. Add a `count` field to the `Item` component (or use a separate `Stackable` component). When picking up an item identical to one already carried (same name, same effect, same parameters), increment the count instead of adding a new slot. Update the inventory panel to show "Health Potion x3," the HUD count to reflect total items, and `drop_item` / `use_item` to decrement the count and only remove the slot when it reaches zero. Decide whether stacking should still count once against the capacity or each item individually.

**Exercise 3: Create a Food System with Hunger**

Add a persistent hunger meter and food items that replenish it. Give the player a `Hunger` component with a value that decreases each turn (or every N turns). When hunger reaches zero, subtract health each turn---the player must eat or starve. Add a `create_ration` factory producing a `Ration` item with a `heal_amount` for hunger. Treat hunger restoration as a new `ConsumableEffect` (for example `ConsumableEffect.FOOD`) with its own `_use_food` handler that raises the hunger value. Display hunger in the HUD ("Hunger: 70/100") and consider how an inventory limited to ten slots interacts with the new need to always carry food.

**Exercise 4: Sort and Filter the Inventory**

Currently the inventory shows items in pickup order. Add sorting so items group by type (potions, scrolls, then food) or alphabetically, making the panel easier to scan at a glance. Then add a filter mode: pressing `f` while the inventory is open cycles between "all," "potions," "scrolls," and "food," showing only matching items. Filtering makes the number-key mapping trickier---slot indices must map through the filtered list back to the real inventory list. This is a good exercise in keeping the panel legible while the underlying data stays a flat list.

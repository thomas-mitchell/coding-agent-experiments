# Chapter 19: Targeting and Spells

Chapter 15 introduced consumables---potions and scrolls the player carries, uses with the number keys, and discards. The system works, but every spell auto-targets the nearest visible enemy. The player cannot choose *where* to throw a fireball, cannot aim a lightning bolt at a specific goblin, and cannot decide which of three orcs to confuse. The targeting is automatic, which means the player has no control over the hardest decisions magic creates.

This chapter adds a targeting mode. The player presses `f` (or uses a fireball scroll) to enter a cursor-driven targeting state, moves a crosshair to a position on the map, sees the spell's area of effect highlighted, and confirms or cancels with a key press. We add four distinct spell types with different targeting requirements: a self-heal that needs no target, a lightning bolt that auto-fires at the nearest enemy, a fireball that demands the player choose an area of effect center, and a confusion scroll that requires a single target. By the end, casting a spell is a deliberate, spatial decision---the player reads the room, picks a spot, and watches the result.

## Magic System Design

The spell system builds on the consumable infrastructure from Chapter 15. Scrolls remain the delivery mechanism: the player picks them up, carries them in the inventory, and activates them with a number key. What changes is how the spell resolves. Instead of immediately finding the nearest enemy and applying an effect, the system may pause, enter a targeting mode, and wait for the player to choose a location.

Three targeting modes cover the spell vocabulary:

**Self.** The spell affects the caster. A heal scroll restores the player's hit points. No cursor, no target selection---the effect applies immediately on use. This is the simplest mode and the one the consumable system already handles.

**Single target.** The spell affects one entity at a chosen position. A lightning bolt fires at a specific enemy; a confusion scroll turns a specific creature into a random wanderer. The player must move the cursor onto a valid target and confirm. If the cursor lands on empty ground or an out-of-range tile, the system rejects the cast.

**Area of effect.** The spell affects every entity within a radius of a chosen point. A fireball damages all enemies in a blast. The player picks a center position, and the system highlights the affected tiles before the player confirms. This mode is the most spatial---the player must consider where allies stand, which walls block the blast, and how many enemies fit inside the radius.

The design principle is that each mode maps to a different player decision. Self-targeting is automatic. Single targeting is about priority. Area targeting is about geometry. Mixing these modes in a single inventory creates tactical variety: a scroll of healing is a safe, immediate action; a scroll of fireball is a powerful, deliberate one.

Scrolls are consumed on use, regardless of whether the spell hits anything. This is intentional. A fireball that hits no enemies still costs the scroll. The player must decide whether the potential reward justifies the expense, not whether the shot is guaranteed. If the system allowed cancellation after entering targeting mode without consuming the scroll, every fireball would be used with zero risk. The cost creates the decision.

## Targeting Mode

Targeting mode is a modal state. When active, the normal movement keys move a cursor instead of the player, the number keys do nothing, and two new keys appear: Enter to confirm and Escape to cancel. The game renders a cursor glyph on the map and, for area spells, highlights the affected tiles.

### Entering Targeting Mode

Two paths lead to targeting mode. The player can press `f` to manually enter targeting mode (useful for planning or when the game adds targeted abilities beyond scrolls). Or the player can use a fireball scroll, which automatically enters targeting mode because the spell requires a target location.

The input handler produces an `EnterTargetingMode` action:

```python
# src/actions.py

import attrs


@attrs.define
class EnterTargetingMode(Action):
    """Enter the targeting cursor mode."""
    pass
```

The action carries no parameters---the game already knows which spell to cast from the inventory selection. The targeting state is tracked in the main loop with a few flags:

```python
# In main.py

targeting_mode = False
target_x = player.components[Position].x
target_y = player.components[Position].y
targeting_spell_index = -1  # inventory index of the scroll being aimed
targeting_radius = 0         # AoE radius for area spells
targeting_max_range = 8      # maximum targeting distance
```

When the player presses `f` outside of any menu, the main loop sets `targeting_mode = True` and centers the cursor on the player:

```python
# src/input_handlers.py

def handle_input(
    event: tcod.event.KeyDown,
    entity: tcod.ecs.Entity,
    targeting: bool = False,
) -> Action | None:
    """Convert a key event into an action."""
    if targeting:
        if event.sym == tcod.event.KeySym.RETURN:
            return ConfirmTargetAction(entity=entity)
        elif event.sym == tcod.event.KeySym.ESCAPE:
            return CancelTargetingAction(entity=entity)
        else:
            dx, dy = _movement_keys.get(event.sym, (0, 0))
            if dx != 0 or dy != 0:
                return MoveCursorAction(entity=entity, dx=dx, dy=dy)
        return None

    # Normal (non-targeting) input handling ...
```

The `targeting` flag switches the input handler into a different branch. Movement keys produce `MoveCursorAction` instead of `BumpAction`. Enter produces `ConfirmTargetAction`. Escape produces `CancelTargetingAction`. Nothing else is handled---the player cannot open inventory, pick up items, or do anything else while targeting.

The cursor movement action is thin:

```python
@attrs.define
class MoveCursorAction(Action):
    """Move the targeting cursor by (dx, dy)."""
    dx: int = 0
    dy: int = 0
```

Confirm and cancel actions are similarly minimal:

```python
@attrs.define
class ConfirmTargetAction(Action):
    """Confirm the current cursor position as the spell target."""
    pass


@attrs.define
class CancelTargetingAction(Action):
    """Exit targeting mode without casting."""
    pass
```

All three carry only the entity. The cursor position and spell parameters live in the main loop's targeting state, not in the actions. Actions describe *what the player did*, not *what the game state looks like*.

### Cursor Movement and Bounds Clamping

The cursor moves one tile at a time, clamped to the map boundaries:

```python
# In main.py, inside the targeting branch of _is_action_success:

if isinstance(action, MoveCursorAction):
    target_x = max(0, min(dungeon.width - 1, target_x + action.dx))
    target_y = max(0, min(dungeon.height - 1, target_y + action.dy))
    return False  # Moving the cursor does not spend a turn
```

The cursor cannot leave the map. The `max` and `min` calls clamp the position. Returning `False` means the cursor movement does not advance the game---enemies do not act, turns do not pass. Targeting is a planning state, not an action.

### Rendering the Targeting Cursor

The targeting overlay draws three things: the cursor glyph itself, the affected area for AoE spells, and a range indicator. The rendering happens in `render_all` when targeting mode is active:

```python
# src/render_functions.py

import tcod.los


def render_targeting(
    console: tcod.console.Console,
    game_map: GameMap,
    camera_x: int,
    camera_y: int,
    cursor_x: int,
    cursor_y: int,
    max_range: int,
    radius: int = 0,
    player_x: int = 0,
    player_y: int = 0,
) -> None:
    """Render the targeting overlay: cursor, AoE highlight, and range line."""
    # Draw range line from player to cursor
    for tx, ty in tcod.los.bresenham(player_x, player_y, cursor_x, cursor_y):
        sx = tx - camera_x
        sy = ty - camera_y
        if 0 <= sx < console.width and 0 <= sy < console.height:
            if game_map.explored[ty, tx]:
                if game_map.visible[ty, tx]:
                    char = console.rgb["ch"][sy, sx]
                    bg = console.rgb["bg"][sy, sx]
                    console.print(
                        x=sx, y=sy, string=char if char != " " else ".",
                        fg=(200, 200, 200), bg=bg,
                    )

    # Draw AoE radius highlight
    if radius > 0:
        for tx in range(max(0, cursor_x - radius), min(game_map.width, cursor_x + radius + 1)):
            for ty in range(max(0, cursor_y - radius), min(game_map.height, cursor_y + radius + 1)):
                dist_sq = (tx - cursor_x) ** 2 + (ty - cursor_y) ** 2
                if dist_sq <= radius ** 2:
                    sx = tx - camera_x
                    sy = ty - camera_y
                    if 0 <= sx < console.width and 0 <= sy < console.height:
                        bg = console.rgb["bg"][sy, sx]
                        console.print(
                            x=sx, y=sy, string="#",
                            fg=(255, 100, 0), bg=bg,
                        )

    # Draw cursor crosshair
    sx = cursor_x - camera_x
    sy = cursor_y - camera_y
    if 0 <= sx < console.width and 0 <= sy < console.height:
        bg = console.rgb["bg"][sy, sx]
        console.print(x=sx, y=sy, string="X", fg=(255, 255, 255), bg=bg)

    # Draw range indicator text
    distance = abs(cursor_x - player_x) + abs(cursor_y - player_y)
    in_range = distance <= max_range
    range_color = (0, 255, 0) if in_range else (255, 0, 0)
    range_text = f"Range: {distance}/{max_range}"
    console.print(x=1, y=0, string=range_text, fg=range_color)
```

Three layers stack on top of the normal map render. The range line draws a Bresenham line from the player to the cursor, showing the path the spell would travel. The AoE highlight fills every tile within the blast radius with orange `#` characters, giving the player a clear picture of what will be affected. The cursor itself is a white `X` at the target position. Finally, a range indicator in the upper-left corner shows the distance from the player to the cursor and whether it falls within the spell's maximum range---green if valid, red if out of range.

The `render_all` function calls `render_targeting` when targeting mode is active, layering it over the normal map and entity render:

```python
def render_all(console, game_map, registry, player, message_log, targeting=False, **targeting_kwargs):
    """Render everything."""
    player_pos = player.components[Position]
    camera_x = player_pos.x - console.width // 2
    camera_y = player_pos.y - MAP_HEIGHT // 2
    camera_x = max(0, min(camera_x, game_map.width - console.width))
    camera_y = max(0, min(camera_y, game_map.height - MAP_HEIGHT))

    console.clear()
    render_map(console, game_map, camera_x, camera_y)
    render_entities(console, registry, game_map, camera_x, camera_y)
    render_panel(console, player, message_log)

    if targeting:
        render_targeting(console, game_map, camera_x, camera_y, **targeting_kwargs)
```

The `**targeting_kwargs` pass-through keeps `render_all` from needing a dozen explicit parameters. The main loop builds a dictionary with the cursor position, range, radius, and player position, and passes it in. This pattern avoids long parameter lists while keeping the interface explicit.

## Line of Sight for Targeting

The targeting system uses tcod's line-of-sight utilities for two purposes: drawing the range line and validating that the target is reachable.

### Bresenham Line Drawing

`tcod.los.bresenham(x0, y0, x1, y1)` returns an iterator of integer coordinates along a Bresenham line. We use it to draw the visible path from the player to the cursor:

```python
import tcod.los

for tx, ty in tcod.los.bresenham(player_x, player_y, cursor_x, cursor_y):
    # Render each tile along the line
    ...
```

Bresenham's algorithm produces a one-pixel-wide line that is fast and deterministic. For targeting purposes, it gives the player a visual path showing which tiles the spell crosses. This is especially useful for line-of-sight spells like lightning---the player can see whether the bolt passes through walls or obstacles.

### Range Validation

Each spell has a maximum range. The targeting system computes the Manhattan distance from the player to the cursor and compares it against the spell's range:

```python
distance = abs(cursor_x - player_x) + abs(cursor_y - player_y)
in_range = distance <= max_range
```

Manhattan distance matches the tile-based movement model. A spell with range 5 can reach any tile within five steps of cardinal movement, which is how the player intuitively measures distance. The range indicator in the upper-left corner of the targeting overlay shows this distance in real time as the cursor moves.

If the cursor is out of range when the player presses Enter, the system rejects the cast and logs a message:

```python
if isinstance(action, ConfirmTargetAction):
    distance = abs(target_x - player.components[Position].x) + \
               abs(target_y - player.components[Position].y)
    if distance > targeting_max_range:
        message_log.add("Target is out of range.", (255, 255, 0))
        return False
```

The player stays in targeting mode after a rejected cast, so they can move the cursor closer or cancel. The scroll is not consumed.

### Valid Target Indicators

For single-target spells, the cursor changes color when it is over a valid target---an enemy entity the player can see. The render function checks for an entity at the cursor position:

```python
# Inside render_targeting, after drawing the cursor:

# Check for entity at cursor
for entity, pos, fighter in registry.Q[Entity, Position, Fighter]:
    if pos.x == cursor_x and pos.y == cursor_y and game_map.visible[pos.y, pos.x]:
        if "enemy" in entity.tags and fighter.hp > 0:
            name = entity.components[Name].name
            console.print(x=sx, y=sy, string="X", fg=(255, 0, 0), bg=bg)
            console.print(
                x=sx, y=sy - 1, string=f"Target: {name}",
                fg=(255, 100, 100), bg=(0, 0, 0),
            )
            break
```

When the cursor lands on an enemy, the crosshair turns red and the enemy's name appears above the cursor. This gives the player immediate feedback about what they are about to hit. If the cursor is on empty ground or a friendly entity, the crosshair stays white and no target label appears.

## Spell Types

Four spell types cover the core roguelike magic vocabulary. Each type has a different targeting mode and a different effect function.

### Heal (Self)

Heal is the simplest spell. It restores the player's hit points and requires no target selection. When the player uses a scroll of healing, the effect applies immediately:

```python
# src/spells.py

from __future__ import annotations
from typing import TYPE_CHECKING

import tcod.ecs

from components import Fighter, Name, Position

if TYPE_CHECKING:
    from game_map import GameMap
    from message_log import MessageLog


def cast_heal(
    player: tcod.ecs.Entity,
    amount: int,
    log: MessageLog,
) -> bool:
    """Restore HP to the player. Returns True on success."""
    fighter = player.components[Fighter]
    if fighter.hp >= fighter.max_hp:
        log.add("You are already at full health.", (255, 255, 0))
        return False

    old_hp = fighter.hp
    fighter.hp = min(fighter.max_hp, fighter.hp + amount)
    healed = fighter.hp - old_hp
    log.add(f"You feel your wounds close. (+{healed} HP)", (0, 255, 0))
    return True
```

The function checks whether the player is already at full health. If so, it returns `False` and the scroll is not consumed. This is the same guard from Chapter 15's `_use_heal`---the logic has moved into the spells module but the behavior is unchanged. Healing never wastes a scroll on a no-op.

### Lightning (Single Target, Auto-Targeting)

Lightning does not require manual targeting. It strikes the nearest visible enemy within range automatically. The spell is powerful but limited: if no enemy is in range, the scroll fizzles:

```python
def cast_lightning(
    registry: tcod.ecs.Registry,
    player: tcod.ecs.Entity,
    damage: int,
    max_range: int,
    game_map: GameMap,
    log: MessageLog,
) -> bool:
    """Strike the nearest visible enemy with lightning. Returns True on success."""
    ppos = player.components[Position]
    target = None
    best_distance = None

    for entity, pos, fighter in registry.Q[Position, Fighter]:
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
            target = entity

    if target is None:
        log.add("No enemy is within range.", (255, 255, 0))
        return False

    name = target.components[Name].name
    target.components[Fighter].hp -= damage
    log.add(
        f"A lightning bolt strikes the {name} for {damage} damage!",
        (255, 255, 0),
    )

    if target.components[Fighter].hp <= 0:
        from combat import handle_death
        handle_death(target, registry)

    return True
```

The auto-targeting logic mirrors `_nearest_visible_enemy` from Chapter 15. It scans every entity with a `Position` and `Fighter`, filters by visibility and range, and returns the closest match. The player cannot choose which enemy to hit---the spell picks the nearest one. This is a design trade-off: lightning is easy to use (no aiming required) but inflexible (the player cannot prioritize a distant high-value target).

### Fireball (Area of Effect)

Fireball is the spell that demands the most from the targeting system. The player picks a center point, and every enemy within the blast radius takes damage. The cast function takes the target coordinates directly:

```python
def cast_fireball(
    registry: tcod.ecs.Registry,
    player: tcod.ecs.Entity,
    center_x: int,
    center_y: int,
    radius: int,
    damage: int,
    game_map: GameMap,
    log: MessageLog,
) -> bool:
    """Cast fireball at the given center point. Returns True on success."""
    hit_any = False
    for entity, pos, fighter in registry.Q[Position, Fighter]:
        if entity is player or fighter.hp <= 0:
            continue
        if not game_map.visible[pos.y, pos.x]:
            continue
        dist_sq = (pos.x - center_x) ** 2 + (pos.y - center_y) ** 2
        if dist_sq <= radius ** 2:
            name = entity.components[Name].name
            fighter.hp -= damage
            log.add(
                f"The fireball hits the {name} for {damage} damage!",
                (255, 127, 0),
            )
            hit_any = True
            if fighter.hp <= 0:
                from combat import handle_death
                handle_death(entity, registry)

    if not hit_any:
        log.add("The fireball explodes harmlessly.", (255, 127, 0))
    return True
```

The function iterates every fighter-bearing entity and checks the squared distance against the squared radius. The squared-distance trick avoids a square root---an entity at exactly the blast radius has `dist_sq == radius ** 2` and is included. The player is always excluded with `if entity is player: continue`.

Unlike the auto-targeting fireball from Chapter 15 (which centered on the nearest enemy), this version takes explicit coordinates. The targeting mode is responsible for getting those coordinates from the player's cursor position. This separation keeps the spell function pure---it does not know about cursors or input modes, only coordinates.

### Confusion (Single Target, Manual Targeting)

Confusion targets a single entity and changes its AI to random wandering. The player must aim the cursor at a visible enemy:

```python
def cast_confusion(
    registry: tcod.ecs.Registry,
    target_x: int,
    target_y: int,
    duration: int,
    game_map: GameMap,
    log: MessageLog,
) -> bool:
    """Confuse the entity at the target position. Returns True on success."""
    from components import AI, AIKind

    target = None
    for entity, pos, fighter in registry.Q[Position, Fighter]:
        if pos.x == target_x and pos.y == target_y:
            if game_map.visible[pos.y, pos.x] and fighter.hp > 0:
                target = entity
                break

    if target is None:
        log.add("There is nothing there to confuse.", (255, 255, 0))
        return False

    if "player" in target.tags:
        log.add("You cannot confuse yourself.", (255, 255, 0))
        return False

    ai = target.components.get(AI)
    if ai is None:
        log.add("That creature is not affected.", (255, 255, 0))
        return False

    ai.previous_ai = ai.kind
    ai.kind = AIKind.CONFUSED
    ai.state_turns_remaining = duration

    name = target.components[Name].name
    log.add(f"The {name} starts wandering in a daze!", (200, 120, 255))
    return True
```

Unlike lightning's auto-targeting, confusion requires the player to aim. The function looks for an entity at the exact target coordinates. If nothing is there, or if the target is the player or has no AI, the spell fails and the scroll is not consumed. The `previous_ai` field stashes the entity's original AI kind so it can revert when confusion expires---the same mechanism from Chapter 15, now driven by an explicit target instead of auto-selection.

## Area of Effect Spells

The fireball is the canonical area of effect spell, but the AoE targeting mode is reusable for any spell that affects a region. The targeting overlay highlights the affected area so the player can make an informed decision.

### Showing the Affected Area

The AoE highlight fills every tile within the blast radius with a distinct color. The render function computes the circle using squared-distance comparison:

```python
# Inside render_targeting:

if radius > 0:
    for tx in range(max(0, cursor_x - radius), min(game_map.width, cursor_x + radius + 1)):
        for ty in range(max(0, cursor_y - radius), min(game_map.height, cursor_y + radius + 1)):
            dist_sq = (tx - cursor_x) ** 2 + (ty - cursor_y) ** 2
            if dist_sq <= radius ** 2:
                sx = tx - camera_x
                sy = ty - camera_y
                if 0 <= sx < console.width and 0 <= sy < console.height:
                    existing_bg = console.rgb["bg"][sy, sx]
                    console.print(
                        x=sx, y=sy, string="#",
                        fg=(255, 100, 0), bg=existing_bg,
                    )
```

The nested loops cover a square bounding box around the cursor, then filter to a circle using the squared-distance check. Tiles inside the circle get an orange `#` overlay. Tiles outside the circle are left untouched. The player sees a clear, circular region of affected tiles---the same region the spell will damage.

The bounding box is clamped to the map edges so the loop never reads outside the map array. The `existing_bg` preserves the underlying tile color, so the overlay blends with the map instead of replacing it.

### AoE and Wall Interactions

For a more advanced implementation, the AoE highlight could account for walls---fireballs do not pass through walls, so tiles behind a wall from the blast center should not be highlighted. This would require line-of-sight checks from the center to each tile in the radius. For now, the highlight is a simple circle without wall occlusion. The spell itself damages all entities in the circle regardless of walls, which is consistent with a "burst" fireball that radiates from a point.

An exercise at the end of this chapter explores adding wall-aware AoE highlighting.

## The Spell System

The spell system is a dispatcher that connects scroll usage to spell functions. It lives in `spells.py` alongside the spell implementations and ties into the consumable system from Chapter 15.

### Scroll Integration

Using a scroll triggers the appropriate spell. The `use_item` function from Chapter 15 dispatches on `ConsumableEffect`. With targeting, the dispatch now has two paths: immediate spells (heal, lightning) resolve instantly, while targeted spells (fireball, confusion) enter targeting mode.

```python
# src/items.py

def use_item(
    registry: tcod.ecs.Registry,
    player: Entity,
    item_index: int,
    game_map: GameMap,
    log: MessageLog,
    targeting_state: dict | None = None,
) -> bool | str:
    """Use a consumable from the inventory.

    Returns True on success, False on failure, or "targeting" if
    the item requires the player to select a target.
    """
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

    if consumable.effect == ConsumableEffect.HEAL:
        from spells import cast_heal
        success = cast_heal(player, consumable.amount, log)
        if success:
            _consume_item(inv, item_index, item, log)
        return success

    if consumable.effect == ConsumableEffect.LIGHTNING:
        from spells import cast_lightning
        success = cast_lightning(
            registry, player, consumable.amount, consumable.range, game_map, log
        )
        if success:
            _consume_item(inv, item_index, item, log)
        return success

    if consumable.effect in (ConsumableEffect.FIREBALL, ConsumableEffect.CONFUSION):
        if targeting_state is not None:
            targeting_state["spell_index"] = item_index
            targeting_state["radius"] = consumable.radius
            targeting_state["max_range"] = consumable.range
            targeting_state["effect"] = consumable.effect
        return "targeting"

    return False
```

The key change is the return value. Immediate spells return `True` or `False` as before. Targeted spells return the string `"targeting"`, which signals the main loop to enter targeting mode. The `targeting_state` dictionary is populated with the spell's parameters so the main loop knows what kind of targeting to display.

### Confirming a Targeted Spell

When the player presses Enter in targeting mode, the main loop reads the targeting state and dispatches to the appropriate cast function:

```python
# In main.py, inside the targeting branch:

if isinstance(action, ConfirmTargetAction):
    distance = abs(target_x - player.components[Position].x) + \
               abs(target_y - player.components[Position].y)
    if distance > targeting_state["max_range"]:
        message_log.add("Target is out of range.", (255, 255, 0))
        return False

    effect = targeting_state["effect"]
    spell_index = targeting_state["spell_index"]

    if effect == ConsumableEffect.FIREBALL:
        from spells import cast_fireball
        success = cast_fireball(
            registry, player, target_x, target_y,
            targeting_state["radius"], consumable.amount,
            dungeon, message_log,
        )
    elif effect == ConsumableEffect.CONFUSION:
        from spells import cast_confusion
        success = cast_confusion(
            registry, target_x, target_y, consumable.duration,
            dungeon, message_log,
        )
    else:
        success = False

    if success:
        _consume_item(player.components[Inventory], spell_index,
                      player.components[Inventory].items[spell_index], message_log)

    targeting_mode = False
    return success
```

The range check runs first. If the target is out of range, the system logs a message and stays in targeting mode. On a successful cast, the scroll is consumed. On failure (no target at position, target immune), the scroll is preserved. The `targeting_mode` flag is cleared in both cases.

Cancelling targeting mode is straightforward:

```python
if isinstance(action, CancelTargetingAction):
    targeting_mode = False
    message_log.add("Spell cancelled.", (180, 180, 180))
    return False
```

Escape exits targeting mode without spending a turn or consuming the scroll. The player can re-enter targeting mode or use the scroll for a different purpose.

### The Consume Helper

The consume helper removes a scroll from the inventory after a successful cast:

```python
def _consume_item(inv: Inventory, index: int, item: Entity, log: MessageLog) -> None:
    """Remove a consumed item from the inventory."""
    name = item.components[Name].name if Name in item.components else "item"
    inv.items.pop(index)
    item.components.clear()
    item.tags.clear()
    log.add(f"You use the {name}.", (200, 180, 50))
```

This is the same pattern from Chapter 15: pop the item from the list, clear its components and tags, and let the registry garbage-collect the empty entity. The name is logged as confirmation.

## Range Limits

Every spell has a maximum range that limits how far the cursor can reach. The range is stored on the `Consumable` component and passed into the targeting state when a targeted scroll is used.

The range check runs at two points. First, the targeting overlay shows a real-time distance indicator so the player knows before confirming whether the target is in range. Second, the confirm handler rejects out-of-range targets with a message.

The range uses Manhattan distance, matching the game's tile-based movement:

```python
distance = abs(cursor_x - player_x) + abs(cursor_y - player_y)
in_range = distance <= max_range
```

Different spells have different ranges. The scroll factory controls this:

| Spell      | Range | Radius | Behavior                         |
|------------|-------|--------|----------------------------------|
| Heal       | 0     | 0      | Self-targeted, no range needed   |
| Lightning  | 5     | 0      | Auto-target nearest in range     |
| Fireball   | 8     | 3      | Manual targeting, 8-tile reach   |
| Confusion  | 5     | 0      | Manual targeting, 5-tile reach   |

The ranges are tuned for gameplay. Lightning reaches across a small room. Fireball reaches across a large room. Confusion is shorter-ranged, forcing the player to get closer. These numbers are easily adjusted in the factory functions.

## Visual Effects for Spells

The message log narrates the spell's result, but the player also needs immediate visual feedback on the map. A fireball should flash the affected tiles. A lightning bolt should momentarily highlight the struck enemy.

### Tile Flashing

The simplest visual effect is a brief color overlay on affected tiles. After the spell resolves, the affected tiles flash for one frame before the normal render resumes:

```python
def flash_tiles(
    console: tcod.console.Console,
    tiles: list[tuple[int, int]],
    color: tuple[int, int, int],
    camera_x: int,
    camera_y: int,
    duration_ms: int = 200,
) -> None:
    """Briefly highlight a set of tiles with a color flash."""
    for tx, ty in tiles:
        sx = tx - camera_x
        sy = ty - camera_y
        if 0 <= sx < console.width and 0 <= sy < console.height:
            console.print(x=sx, y=sy, string="*", fg=color)

    context.present(console)
    import time
    time.sleep(duration_ms / 1000)
```

The flash draws `*` characters over the affected tiles and presents the console for a short duration. This is a synchronous, blocking approach---the game freezes for the duration of the flash. It is simple and effective for a text-based game. Chapter 24 introduces a proper animation system with frame-by-frame rendering, but for now the blocking flash is adequate.

To integrate the flash into a fireball cast, the cast function collects the affected tile positions and flashes them:

```python
# Inside cast_fireball, after processing damage:

affected_tiles = []
for entity, pos, fighter in registry.Q[Position, Fighter]:
    if entity is player or fighter.hp <= 0:
        continue
    dist_sq = (pos.x - center_x) ** 2 + (pos.y - center_y) ** 2
    if dist_sq <= radius ** 2:
        affected_tiles.append((pos.x, pos.y))

# Add the center tile itself
affected_tiles.append((center_x, center_y))

flash_tiles(console, affected_tiles, (255, 127, 0), camera_x, camera_y)
```

This is a preview of the animation work in Chapter 24. The synchronous flash is a stopgap---it works, but it blocks the event loop and does not support overlapping animations. For a polished game, the animation system in Chapter 24 will handle this with proper timing and layering.

### Screen Shake for Big Impacts

For powerful spells, a brief screen shake adds weight. The camera position jitters for a few frames before settling back:

```python
def screen_shake(
    console: tcod.console.Console,
    render_func,
    intensity: int = 2,
    frames: int = 3,
) -> None:
    """Briefly shake the screen by offsetting the camera."""
    import random
    for _ in range(frames):
        offset_x = random.randint(-intensity, intensity)
        offset_y = random.randint(-intensity, intensity)
        render_func(offset_x=offset_x, offset_y=offset_y)
        import time
        time.sleep(50 / 1000)
    render_func(offset_x=0, offset_y=0)
```

The `render_func` is the normal `render_all` callable. The shake offsets the camera by a random amount for each frame, creating a jittery effect. After the shake, the camera returns to its normal position. This is also a preview---the full animation system in Chapter 24 will manage these effects without blocking.

For now, the screen shake is called synchronously after a large fireball hits multiple targets:

```python
if len(affected_tiles) > 3:
    screen_shake(console, render_all_callable, intensity=2, frames=3)
```

A fireball that hits one or two enemies does not shake. A fireball that hits four or more does. The threshold keeps the effect special---if every spell shakes the screen, the effect loses its impact.

## Integrating with the Main Loop

The targeting state lives in the main loop as a handful of local variables. The full state machine has three states: normal play, targeting mode, and inventory/drop mode (from Chapter 15). Targeting mode is entered from normal play and returns to normal play.

```python
# src/main.py (excerpt)

targeting_mode = False
target_x = 0
target_y = 0
targeting_state: dict = {}

# Main loop event handling:
if event.sym == tcod.event.KeySym.f:
    if not targeting_mode and not show_inventory:
        targeting_mode = True
        target_x = player.components[Position].x
        target_y = player.components[Position].y
        targeting_state = {}
        needs_render = True
    continue

if targeting_mode:
    action = handle_input(event, player, targeting=True)
    if action is not None:
        spent = _is_action_success(
            action, registry, dungeon, log, player,
            targeting_state=targeting_state,
        )
        if isinstance(action, ConfirmTargetAction) or isinstance(action, CancelTargetingAction):
            targeting_mode = False
        if spent:
            _advance_after_turn(registry, dungeon, log, player, graph)
        needs_render = True
    continue
```

The state machine is clean. Pressing `f` enters targeting mode and centers the cursor on the player. While targeting, all input routes through `handle_input` with `targeting=True`. Confirming or cancelling exits targeting mode. A successful spell cast spends a turn and advances the world.

The `targeting_state` dictionary is the communication channel between `use_item` and the targeting confirm handler. When `use_item` returns `"targeting"`, it populates `targeting_state` with the spell's parameters. When the player confirms a target, the confirm handler reads those parameters and dispatches to the correct cast function. This avoids threading targeting parameters through the entire action pipeline.

## Exercises

**Exercise 1: Wall of Fire (Persistent AoE)**

Add a spell that creates a persistent area of effect. A scroll of wall of fire places burning tiles at the target location that damage any entity that steps on them for several turns. Create a `WallOfFire` component with `duration`, `damage_per_turn`, and `center_x`/`center_y`/`radius` fields. Attach it to the world entity. During the world-effects phase of the turn loop, iterate entities with `WallOfFire`, check which fighters stand on burning tiles, and apply damage. Decrement the duration each turn and remove the component when it expires. The targeting mode is the same as fireball---the player picks a center and sees the radius. The visual effect draws the burning tiles in a flickering red-orange until the wall expires.

**Exercise 2: Teleport Spell**

Implement a teleport spell that moves the player to a targeted position. When the player uses a scroll of teleportation, the targeting mode activates. The player picks a destination tile. If the tile is walkable and within the spell's range, the player's `Position` is updated to that location. If the tile is not walkable (inside a wall), the spell fails. The flash effect highlights both the origin and destination tiles. Consider whether teleportation should reveal the fog of war at the destination, and whether the spell should work through walls (long-range teleport) or only to visible tiles.

**Exercise 3: Summoning Spell**

Create a summoning spell that spawns an allied entity at a targeted position. When the player uses a scroll of summoning, the targeting mode activates and the player picks a tile within range. If the tile is walkable and unoccupied, spawn an ally entity (such as a friendly skeleton or a spectral wolf) at that position with an `AI` component set to `HOSTILE` but tagged `"ally"` instead of `"enemy"`. The ally takes turns after the player, moves toward enemies, and attacks them. The entity factory for summoned creatures should define their `Fighter` stats, `Renderable` glyph, and `Name`. Consider adding a duration to summoned creatures---they disappear after N turns, preventing the player from building an invincible army.

**Exercise 4: Chain Lightning**

Extend the lightning spell to hit multiple targets. A scroll of chain lightning strikes the nearest visible enemy, then jumps to the next nearest enemy within a reduced range, then jumps again. Each jump reduces the damage by a fixed amount (e.g., 5). Add a `jumps` field to the `Consumable` component and a `damage_decay` field. The cast function iterates: find the nearest enemy, deal damage, then find the nearest *remaining* enemy within the reduced range, deal reduced damage, and repeat until no more targets are in range or the jump count is exhausted. Display each jump with a brief flash between the affected entities.

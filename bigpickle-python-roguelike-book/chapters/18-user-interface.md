# Chapter 18: The User Interface

Chapters 15 through 17 gave us items, equipment, and a message log---three systems that each added depth to the game. But they were bolted on one at a time, each with its own panel, its own rendering path, and its own keyboard mode. The screen is now a patchwork. Nothing is wrong, exactly, but nothing is cohesive.

This chapter pulls the entire interface together. We define a screen layout where every element has a fixed position. We build a HUD panel with stats, equipment, and dungeon floor. We replace the raw HP number with a color-coded bar. We add menu systems for inventory, equipment, and dropping---all sharing one rendering pattern. We implement look mode, a cursor for inspecting entities and tiles. We build a character sheet that summarizes the player's full state. We centralize every color in the palette so the whole game reads as one visual language.

## UI Design Principles

A roguelike is a text game rendered on a grid. Every cell the player has to decode costs attention. The principles below are not aesthetic preferences; they are constraints that keep the interface from becoming a second dungeon to navigate.

**Information density.** The player should see everything they need without pressing a key. HP, level, equipment, and messages should all be visible at all times. Roguelikes are information games---the map, the log, and the stats are the three channels through which the player understands the world.

**Consistency.** The same key always does the same thing. `i` always opens inventory. `Escape` always closes or cancels. The player should never have to wonder what a key does in the current context.

**Minimalism.** The screen is 80 columns by 50 rows. Every cell dedicated to chrome---borders, labels, spacing---is a cell not showing the dungeon. We need thin separator lines and tight padding, not decorative frames.

**Accessibility.** High contrast between text and background. Distinct colors for distinct meanings. No color is reused for two unrelated concepts. Red means danger. Green means healing. Yellow means the player's actions. Gray means ambient information.

These principles pull in different directions. High density fights minimalism. Consistency sometimes demands a mode that temporarily violates density. The art is in finding the balance: show everything, change modes rarely, and make every mode self-documenting.

## Screen Layout

The screen is divided into three fixed regions. The game map occupies the top 43 rows. Below a separator line, the bottom seven rows are split vertically: a 20-column stats panel on the left and a message area filling the remainder.

```
┌────────────────────────────────────────────┐
│                                            │
│            Game Map (80x43)                │
│                                            │
├────────────┬───────────────────────────────┤
│ Stats      │ Messages (last 4)             │
│ HP: 25/30  │ You attack the Orc for 5.     │
│ Lvl: 3     │ The Orc attacks you for 3.    │
│ ATK: 8     │ You pick up the Potion.       │
│ DEF: 4     │                               │
└────────────┴───────────────────────────────┘
```

We define these dimensions as constants so every rendering function references the same source of truth:

```python
# src/render_functions.py

SCREEN_WIDTH = 80
SCREEN_HEIGHT = 50

PANEL_HEIGHT = 7
MAP_HEIGHT = SCREEN_HEIGHT - PANEL_HEIGHT  # 43

STATS_WIDTH = 20
STATS_HEIGHT = PANEL_HEIGHT - 1  # 6 (excluding separator)

MESSAGE_X = STATS_WIDTH
MESSAGE_WIDTH = SCREEN_WIDTH - STATS_WIDTH
MESSAGE_HEIGHT = STATS_HEIGHT
```

Defining the layout through arithmetic rather than hard-coded numbers means changing `SCREEN_WIDTH` or `PANEL_HEIGHT` in one place cascades to every element.

## The Color Palette

Before building UI elements, we need a consistent color language. We extend the palette from Chapter 17 with constants for the HUD, HP bar, and menus:

```python
# src/palette.py

"""Shared color palette for console output and the UI."""

# --- Base colors ---------------------------------------------------------
WHITE = (255, 255, 255)
GRAY = (200, 200, 200)
DIM_GRAY = (128, 128, 128)
BLACK = (0, 0, 0)

# --- Feedback colors (carried from Chapter 17) --------------------------
YELLOW = (255, 255, 0)
CYAN = (0, 255, 255)
GREEN = (0, 255, 0)
RED = (255, 0, 0)
LIGHT_RED = (255, 120, 120)
ORANGE = (255, 165, 0)
BLUE = (150, 150, 255)
PURPLE = (200, 120, 255)

# --- Panel / HUD colors --------------------------------------------------
PANEL_BORDER = (100, 100, 100)
PANEL_TEXT = (255, 255, 255)
PANEL_SUBTEXT = (180, 180, 180)
PANEL_BG = (20, 20, 40)
PANEL_FG = (180, 180, 180)
HUD_LABEL = (180, 180, 180)
HUD_VALUE = (255, 255, 255)

# --- HP bar colors -------------------------------------------------------
HEALTH_GREEN = (0, 200, 0)
HEALTH_YELLOW = (200, 200, 0)
HEALTH_RED = (200, 0, 0)
HP_BAR_BG = (60, 0, 0)

# --- Menu colors ---------------------------------------------------------
MENU_TITLE = (255, 255, 255)
MENU_ITEM = (200, 200, 200)
MENU_HIGHLIGHT = (255, 255, 0)
MENU_HINT = (150, 150, 150)

# --- Look mode / history -------------------------------------------------
LOOK_CURSOR = (255, 255, 0)
LOOK_INFO_BG = (30, 30, 50)
HISTORY_HINT = (150, 150, 150)
```

Every color used in the UI is named here. No rendering function ever uses a raw tuple. The consistency is what makes the interface learnable: `MENU_HIGHLIGHT` is always yellow, `HEALTH_RED` is always the same red. The player builds a mental model of what each color means, and the interface becomes readable at a glance.

## The HUD Panel

The HUD panel is always visible---even when menus are open. It shows the player's name, HP bar, level, equipment, and dungeon floor.

```python
# src/render_functions.py

from palette import (
    HUD_LABEL, HUD_VALUE, HEALTH_GREEN, HEALTH_YELLOW,
    HEALTH_RED, HP_BAR_BG, PANEL_BORDER, PANEL_SUBTEXT, WHITE,
)


def render_hud(
    console: tcod.console.Console,
    player: tcod.ecs.Entity,
    floor: int = 1,
) -> None:
    """Render the bottom HUD panel with stats, HP bar, and equipment."""
    from components import (
        Equipment, Fighter, Inventory, Name, XP, get_defense, get_power,
    )

    panel_y = MAP_HEIGHT
    fighter = player.components[Fighter]
    name = player.components[Name].name

    # Separator line
    for x in range(console.width):
        console.print(x=x, y=panel_y, string="─", fg=PANEL_BORDER)

    # Row 1: Name + HP bar
    console.print(x=1, y=panel_y + 1, string=name, fg=HUD_VALUE)
    _render_hp_bar(console, x=1 + len(name) + 2, y=panel_y + 1,
                   width=20, hp=fighter.hp, max_hp=fighter.max_hp)

    # Row 2: Level, XP, floor
    xp = player.components.get(XP)
    if xp is not None:
        console.print(x=1, y=panel_y + 2,
                      string=f"Lvl: {xp.level}", fg=HUD_VALUE)
        console.print(x=12, y=panel_y + 2,
                      string=f"XP: {xp.current}/{xp.xp_to_next}", fg=PANEL_SUBTEXT)
    floor_str = f"Floor: {floor}"
    console.print(x=console.width - len(floor_str) - 1, y=panel_y + 2,
                  string=floor_str, fg=PANEL_SUBTEXT)

    # Row 3: ATK / DEF
    console.print(x=1, y=panel_y + 3,
                  string=f"ATK: {get_power(player)}  DEF: {get_defense(player)}",
                  fg=HUD_VALUE)

    # Row 4: Equipment
    equip = player.components.get(Equipment)
    weapon_name = "bare hands" if equip is None or equip.weapon is None else equip.weapon.components[Name].name
    armor_name = "none" if equip is None or equip.armor is None else equip.armor.components[Name].name
    console.print(x=1, y=panel_y + 4,
                  string=f"W: {weapon_name}  A: {armor_name}"[:38], fg=PANEL_SUBTEXT)

    # Row 5: Inventory count
    inv = player.components.get(Inventory)
    if inv is not None:
        console.print(x=1, y=panel_y + 5,
                      string=f"Inventory: {len(inv.items)}/{inv.capacity}", fg=PANEL_SUBTEXT)

    # Row 6: Control hints
    console.print(x=1, y=panel_y + 6,
                  string="i:inv e:equip d:drop l:look v:log c:stats"[:console.width - 2],
                  fg=HUD_LABEL)
```

The HUD is six rows of tightly packed information. Row 1 shows the name and HP bar side by side. Row 2 shows level and XP on the left, floor on the right. Row 3 shows ATK and DEF. Row 4 shows equipment. Row 5 shows inventory count. Row 6 shows control hints. Every piece of information the player needs is visible without pressing a single key.

## The HP Bar

A raw HP number like "HP: 25/30" communicates exact values, but not urgency. A player scanning the screen has to read the number, compare it to the maximum, and decide. A color-coded bar communicates urgency instantly: green means safe, yellow means caution, red means critical.

```python
def _render_hp_bar(
    console: tcod.console.Console,
    x: int, y: int, width: int,
    hp: int, max_hp: int,
) -> None:
    """Render a color-coded HP bar with text overlay."""
    ratio = hp / max_hp if max_hp > 0 else 0
    filled = int(ratio * (width - 2))

    if ratio > 0.6:
        bar_color = HEALTH_GREEN
    elif ratio > 0.3:
        bar_color = HEALTH_YELLOW
    else:
        bar_color = HEALTH_RED

    console.print(x=x, y=y, string="[", fg=PANEL_SUBTEXT)
    for i in range(width - 2):
        char = "█" if i < filled else "░"
        fg = bar_color if i < filled else HP_BAR_BG
        console.print(x=x + 1 + i, y=y, string=char, fg=fg)
    console.print(x=x + width - 1, y=y, string="]", fg=PANEL_SUBTEXT)

    # Overlay centered text
    hp_text = f"{hp}/{max_hp}"
    text_x = x + (width - 2 - len(hp_text)) // 2 + 1
    console.print(x=text_x, y=y, string=hp_text, fg=WHITE)
```

The bar is `width` characters wide, including brackets. The interior is `width - 2` cells, each either a filled block in the bar color or an empty block in the background color. The color thresholds are deliberately generous: green dominates above 60%, yellow covers 30-60%, red kicks in below 30%. The bar stays green for most of the fight and only shifts to yellow when the player has taken meaningful damage.

## Menu Systems

Rather than building a separate renderer for each menu, we build one generic renderer that takes a title, a list of entries, and a selected index.

### The Generic Menu Renderer

```python
def render_menu(
    console: tcod.console.Console,
    title: str,
    entries: list[str],
    x: int, y: int, width: int, height: int,
    selected: int = -1,
    hint: str = "[Esc] close",
) -> None:
    """Render a bordered menu with a title and scrollable entries."""
    console.draw_frame(x=x, y=y, width=width, height=height,
                       title=title, fg=MENU_TITLE, bg=PANEL_BG)

    inner_height = height - 3
    scroll_offset = max(0, selected - inner_height + 2) if selected >= 0 else 0

    for i in range(inner_height):
        idx = i + scroll_offset
        if idx >= len(entries):
            break
        fg = MENU_HIGHLIGHT if idx == selected else MENU_ITEM
        console.print(x=x + 2, y=y + 2 + i,
                      string=entries[idx][:width - 4], fg=fg)

    console.print(x=x + 2, y=y + height - 2,
                  string=hint[:width - 4], fg=MENU_HINT)
```

When `selected` is -1, no entry is highlighted. When `selected` is a valid index, that entry is highlighted in yellow and the list scrolls if needed. This renderer is reused by inventory, equipment, dropping, and the character sheet.

### Inventory Menu

Pressing `i` opens the inventory. Pressing `d` opens it in drop mode.

```python
def render_inventory(
    console: tcod.console.Console,
    player: tcod.ecs.Entity,
    drop_mode: bool = False,
) -> None:
    """Render the inventory or drop menu centered on screen."""
    from components import Inventory, Name

    inv = player.components.get(Inventory)
    if inv is None:
        return

    title = "Drop which item?" if drop_mode else "Inventory"
    entries = [
        f"[{i + 1}] {item.components[Name].name if Name in item.components else '?'}"
        for i, item in enumerate(inv.items)
    ] or ["(empty)"]

    hint = "Press 1-9 to drop, Esc to cancel" if drop_mode else "Press 1-9 to use, Esc to close"
    w, h = 36, min(len(entries) + 4, 20)
    render_menu(console, title, entries,
                console.width // 2 - w // 2, console.height // 2 - h // 2,
                w, h, hint=hint)
```

### Equipment Menu

Pressing `e` opens the equipment menu, showing only items with an `Equippable` component.

```python
def render_equipment_menu(
    console: tcod.console.Console,
    player: tcod.ecs.Entity,
) -> None:
    """Render the equipment selection menu."""
    from components import Equippable, Inventory, Name

    inv = player.components.get(Inventory)
    if inv is None:
        return

    entries: list[str] = []
    for item in inv.items:
        eq = item.components.get(Equippable)
        if eq is None:
            continue
        name = item.components[Name].name if Name in item.components else "Unknown"
        slot = eq.slot.capitalize()
        bonuses = []
        if eq.power_bonus:
            bonuses.append(f"+{eq.power_bonus} Atk")
        if eq.defense_bonus:
            bonuses.append(f"+{eq.defense_bonus} Def")
        bonus_str = f" ({', '.join(bonuses)})" if bonuses else ""
        entries.append(f"[{len(entries) + 1}] {name} ({slot}{bonus_str})")

    if not entries:
        entries = ["(no equippable items)"]

    w, h = 44, min(len(entries) + 4, 20)
    render_menu(console, "Equip", entries,
                console.width // 2 - w // 2, console.height // 2 - h // 2, w, h)
```

Each entry includes the slot name and stat bonuses so the player can compare weapons or armor without opening the character sheet.

## Look Mode

Look mode is a cursor the player moves around the map to inspect tiles and entities. Pressing `l` or `x` enters look mode. The cursor appears as a highlighted `X` at the player's position. Arrow keys and vi-keys move the cursor. A small info panel shows the name, HP, and description of whatever is under it. Escape exits look mode.

### Look Mode State

Look mode is tracked by three variables in the main loop:

```python
looking = False
look_x = 0
look_y = 0
```

When activated, `look_x` and `look_y` are set to the player's position. During look mode, movement keys update the cursor instead of the player.

### Look Mode Rendering

```python
def render_look_mode(
    console: tcod.console.Console,
    game_map: GameMap,
    registry: tcod.ecs.Registry,
    player: tcod.ecs.Entity,
    cursor_x: int, cursor_y: int,
) -> None:
    """Render the map with a cursor and info panel for look mode."""
    from components import Description, Fighter, Name, Position, Renderable

    player_pos = player.components[Position]
    cam_x = max(0, min(player_pos.x - console.width // 2, game_map.width - console.width))
    cam_y = max(0, min(player_pos.y - MAP_HEIGHT // 2, game_map.height - MAP_HEIGHT))

    render_map(console, game_map, cam_x, cam_y)
    render_entities(console, registry, game_map, cam_x, cam_y)

    # Cursor highlight
    sx, sy = cursor_x - cam_x, cursor_y - cam_y
    if 0 <= sx < console.width and 0 <= sy < MAP_HEIGHT and game_map.in_bounds(cursor_x, cursor_y):
        console.print(x=sx, y=sy, string="X", fg=LOOK_CURSOR)

    # Build info panel lines
    lines = [f"({cursor_x}, {cursor_y})"]
    if not game_map.in_bounds(cursor_x, cursor_y):
        lines.append("Out of bounds")
    elif not game_map.explored[cursor_y, cursor_x]:
        lines.append("Not explored")
    elif not game_map.visible[cursor_y, cursor_x]:
        lines.append("Explored (not visible)")
    else:
        found = False
        for entity, pos, _rend in registry.Q[tcod.ecs.Entity, Position, Renderable]:
            if pos.x == cursor_x and pos.y == cursor_y:
                lines.append(entity.components[Name].name if Name in entity.components else "Unknown")
                if Fighter in entity.components:
                    f = entity.components[Fighter]
                    lines.append(f"HP: {f.hp}/{f.max_hp}")
                if Description in entity.components:
                    desc = entity.components[Description].text
                    while desc:
                        lines.append(desc[:30])
                        desc = desc[30:]
                found = True
                break
        if not found:
            lines.append("Floor" if game_map.tiles[cursor_y, cursor_x]["walkable"] else "Wall")

    # Draw the info panel
    pw, ph = 32, len(lines) + 2
    px = min(sx + 2, console.width - pw - 1)
    py = max(0, min(sy, MAP_HEIGHT - ph - 1))
    console.draw_frame(x=px, y=py, width=pw, height=ph, fg=PANEL_BORDER, bg=LOOK_INFO_BG)
    for i, line in enumerate(lines):
        console.print(x=px + 1, y=py + 1 + i, string=line[:pw - 2], fg=WHITE)

    console.print(x=1, y=MAP_HEIGHT - 1,
                  string="Move cursor: arrows/vi   [Esc] exit look mode"[:console.width - 2],
                  fg=HUD_LABEL)
```

The info panel is positioned to the right of and below the cursor, clamped so it never goes off screen. The cursor is a bright yellow `X` that stands out against dark tiles without obscuring what is underneath.

### Look Mode Input

The main loop handles look mode input before any other input:

```python
if looking:
    if event.sym in (tcod.event.KeySym.UP, tcod.event.KeySym.k):
        look_y = max(0, look_y - 1)
    elif event.sym in (tcod.event.KeySym.DOWN, tcod.event.KeySym.j):
        look_y = min(game_map.height - 1, look_y + 1)
    elif event.sym in (tcod.event.KeySym.LEFT, tcod.event.KeySym.h):
        look_x = max(0, look_x - 1)
    elif event.sym in (tcod.event.KeySym.RIGHT, tcod.event.KeySym.l):
        look_x = min(game_map.width - 1, look_x + 1)
    elif event.sym in (tcod.event.KeySym.ESCAPE, tcod.event.KeySym.RETURN, tcod.event.KeySym.SPACE):
        looking = False
    needs_render = True
    continue
```

The `continue` is critical. While in look mode, no other keys are processed. The movement keys move the cursor, not the player. The game does not advance. This is the same pattern used by the message log history in Chapter 17: a modal overlay that captures input until the player explicitly exits.

## The Character Sheet

Pressing `c` opens a full-screen summary of the player's state: every stat, every equipment bonus, and the inventory summary.

```python
def render_character_sheet(
    console: tcod.console.Console,
    player: tcod.ecs.Entity,
    floor: int = 1,
) -> None:
    """Render the full-screen character sheet."""
    from components import (
        Equipment, Equippable, Fighter, Inventory, Name, XP,
        get_defense, get_power,
    )

    console.clear()
    w, h = 50, 24
    x = console.width // 2 - w // 2
    y = console.height // 2 - h // 2
    console.draw_frame(x=x, y=y, width=w, height=h,
                       title="Character Sheet", fg=MENU_TITLE, bg=PANEL_BG)

    row = y + 2
    fighter = player.components[Fighter]
    name = player.components[Name].name
    console.print(x=x + 2, y=row, string=f"Name: {name}", fg=HUD_VALUE)
    row += 1

    xp = player.components.get(XP)
    if xp is not None:
        console.print(x=x + 2, y=row,
                      string=f"Level: {xp.level}  XP: {xp.current}/{xp.xp_to_next}",
                      fg=HUD_VALUE)
        row += 1
    row += 1

    # HP bar
    console.print(x=x + 2, y=row, string=f"HP: {fighter.hp}/{fighter.max_hp}", fg=HUD_VALUE)
    _render_hp_bar(console, x=x + 14, y=row, width=20, hp=fighter.hp, max_hp=fighter.max_hp)
    row += 2

    # Combat stats
    console.print(x=x + 2, y=row, string=f"Base Power: {fighter.power}", fg=HUD_VALUE); row += 1
    console.print(x=x + 2, y=row, string=f"Base Defense: {fighter.defense}", fg=HUD_VALUE); row += 1
    console.print(x=x + 2, y=row, string=f"Total ATK: {get_power(player)}", fg=GREEN); row += 1
    console.print(x=x + 2, y=row, string=f"Total DEF: {get_defense(player)}", fg=GREEN); row += 1

    # Equipment breakdown
    equip = player.components.get(Equipment)
    if equip is not None:
        row += 1
        console.print(x=x + 2, y=row, string="Equipment:", fg=PANEL_SUBTEXT); row += 1
        for slot_name, slot_entity in [("Weapon", equip.weapon), ("Armor", equip.armor)]:
            item_name = "none" if slot_entity is None else slot_entity.components[Name].name
            bonus = ""
            if slot_entity is not None:
                eq = slot_entity.components.get(Equippable)
                if eq is not None:
                    parts = []
                    if eq.power_bonus:
                        parts.append(f"+{eq.power_bonus} Atk")
                    if eq.defense_bonus:
                        parts.append(f"+{eq.defense_bonus} Def")
                    bonus = f" ({', '.join(parts)})" if parts else ""
            console.print(x=x + 2, y=row, string=f"  {slot_name}: {item_name}{bonus}", fg=HUD_VALUE)
            row += 1

    # Inventory summary
    inv = player.components.get(Inventory)
    if inv is not None:
        row += 1
        console.print(x=x + 2, y=row, string="Inventory:", fg=PANEL_SUBTEXT); row += 1
        console.print(x=x + 2, y=row,
                      string=f"  {len(inv.items)}/{inv.capacity} items carried", fg=HUD_VALUE)
        row += 1

    row += 1
    console.print(x=x + 2, y=row, string=f"Dungeon Floor: {floor}", fg=PANEL_SUBTEXT)
    console.print(x=x + 2, y=y + h - 2, string="[Esc or c] close", fg=MENU_HINT)
```

The character sheet clears the console and draws a centered frame. Base and total combat stats are shown with totals in green. The equipment section shows each slot with its bonus breakdown. The character sheet is modal: pressing `c` or `Escape` closes it without spending a turn.

## Tooltip and Hover Information

A tooltip shows entity details near the cursor in look mode. It is simpler than the full info panel---just the name and HP:

```python
def render_tooltip(
    console: tcod.console.Console,
    game_map: GameMap,
    registry: tcod.ecs.Registry,
    cursor_x: int, cursor_y: int,
    camera_x: int, camera_y: int,
) -> None:
    """Render a tooltip near the cursor showing entity info."""
    from components import Fighter, Name, Position, Renderable

    if not game_map.in_bounds(cursor_x, cursor_y):
        return
    if not game_map.visible[cursor_y, cursor_x]:
        return

    for entity, pos, _rend in registry.Q[tcod.ecs.Entity, Position, Renderable]:
        if pos.x == cursor_x and pos.y == cursor_y:
            name = entity.components[Name].name if Name in entity.components else "?"
            hp = ""
            if Fighter in entity.components:
                f = entity.components[Fighter]
                hp = f"  HP:{f.hp}/{f.max_hp}"
            text = f"{name}{hp}"
            sx, sy = cursor_x - camera_x, cursor_y - camera_y
            ty = sy - 2 if sy >= 3 else sy + 2
            tx = max(0, min(sx, console.width - len(text) - 2))
            console.print(x=tx, y=ty, string=f" {text} ", fg=WHITE, bg=PANEL_BG)
            return
```

The tooltip is positioned two rows above the cursor, flipping below if near the top. The background color ensures readability against any tile.

## Responsive Design

tcod's context manages the SDL window and handles pixel scaling. The console size is fixed at `SCREEN_WIDTH x SCREEN_HEIGHT`, and tcod scales the rendered console to fit the window. The player can resize freely---tcod stretches the tile grid to fill it. We handle `WindowResized` events by re-rendering:

```python
if isinstance(event, tcod.event.WindowResized):
    needs_render = True
    continue
```

No relayout logic is needed. The fixed console dimensions mean the UI works at any window size. At 80x50 with 16x16 tiles, the minimum window is 1280x800 pixels. Below that, tcod clips the edges. The player can scale up, and tcod scales proportionally.

## Integrating with the Main Loop

All UI modes are state variables in the main loop. The rendering function checks which mode is active and calls the appropriate renderer:

```python
looking = False
look_x = look_y = 0
show_inventory = False
drop_mode = False
show_equipment = False
show_character = False
show_history = False
history_offset = 0

# ... inside the event loop, mode-specific input handling ...

if looking:
    # ... look mode input ...
    continue
if show_history:
    # ... history input from Chapter 17 ...
    continue
if show_character:
    if event.sym in (tcod.event.KeySym.ESCAPE, tcod.event.KeySym.c):
        show_character = False
        needs_render = True
    continue
if show_inventory or drop_mode:
    if event.sym == tcod.event.KeySym.ESCAPE:
        show_inventory = drop_mode = False
        needs_render = True
        continue
    # ... number key handling for use/drop ...
    continue
if show_equipment:
    if event.sym == tcod.event.KeySym.ESCAPE:
        show_equipment = False
        needs_render = True
        continue
    # ... equipment selection ...
    continue

# --- Normal mode input. ---
if event.sym == tcod.event.KeySym.ESCAPE:
    raise SystemExit()
if event.sym in (tcod.event.KeySym.l, tcod.event.KeySym.x):
    looking = True
    look_x, look_y = player.components[Position].x, player.components[Position].y
elif event.sym == tcod.event.KeySym.i:
    show_inventory = True
elif event.sym == tcod.event.KeySym.e:
    show_equipment = True
elif event.sym == tcod.event.KeySym.c:
    show_character = True
elif event.sym == tcod.event.KeySym.v:
    show_history = True
    history_offset = 0
needs_render = True
```

The rendering dispatch mirrors the input modes:

```python
if needs_render:
    if looking:
        render_look_mode(console, dungeon, registry, player, look_x, look_y)
    elif show_history:
        render_history(console, log, history_offset)
    elif show_character:
        render_character_sheet(console, player, floor=floor)
    elif show_inventory or drop_mode:
        render_all(console, dungeon, registry, player, log, floor=floor)
        render_inventory(console, player, drop_mode=drop_mode)
    elif show_equipment:
        render_all(console, dungeon, registry, player, log, floor=floor)
        render_equipment_menu(console, player)
    else:
        render_all(console, dungeon, registry, player, log, floor=floor)

    if game_over:
        console.print(x=SCREEN_WIDTH // 2 - 14, y=SCREEN_HEIGHT // 2,
                      string="[ press any key to exit ]", fg=YELLOW)
    context.present(console)
    needs_render = False
```

`render_all` draws the map, entities, and HUD. Modal menus overlay the normal view. Character sheet and look mode replace the view entirely. The `floor` parameter threads through `render_all` and `render_hud` so the HUD displays the current dungeon floor.

## The Complete Rendering Pipeline

The render functions module now contains:

- `render_map` -- dungeon tiles with visibility
- `render_entities` -- positioned, renderable entities
- `render_hud` -- bottom panel with stats, HP bar, equipment
- `_render_hp_bar` -- color-coded health bar
- `render_panel` -- message area (from Chapter 17)
- `render_menu` -- generic bordered menu
- `render_inventory` -- inventory/drop menu
- `render_equipment_menu` -- equipment selection
- `render_look_mode` -- map with cursor and info panel
- `render_tooltip` -- single-line entity tooltip
- `render_character_sheet` -- full-screen stat summary
- `render_all` -- orchestrator for normal play

The orchestrator ties them together:

```python
def render_all(
    console: tcod.console.Console,
    game_map: GameMap,
    registry: tcod.ecs.Registry,
    player: tcod.ecs.Entity,
    message_log: MessageLog,
    floor: int = 1,
) -> None:
    """Render the full game screen: map, entities, HUD, and messages."""
    from components import Position
    console.clear()
    pos = player.components[Position]
    cam_x = max(0, min(pos.x - console.width // 2, game_map.width - console.width))
    cam_y = max(0, min(pos.y - MAP_HEIGHT // 2, game_map.height - MAP_HEIGHT))

    render_map(console, game_map, cam_x, cam_y)
    render_entities(console, registry, game_map, cam_x, cam_y)
    render_hud(console, player, floor=floor)
    render_panel(console, player, message_log, cam_x, cam_y)
```

Every rendering function takes the console as its first argument and draws onto it. No function creates its own console. No function calls `context.present`. The main loop owns the present call. This separation means the render functions are pure drawing code---they do not manage state, they do not handle input, and they do not touch the SDL window.

## Exercises

**Exercise 1: Mini-Map Overlay**

Add a mini-map that shows the explored portion of the dungeon in a small corner of the screen---perhaps 15x15 characters, where each character represents a 2x2 or 3x3 tile area. Press `m` to toggle the overlay. Mark the player's position with a bright character. Consider using numpy to downsample the `explored` array.

**Exercise 2: Animated HP Bar**

Replace the static HP bar with an animated transition. When HP changes, the bar should smoothly fill or drain over several frames. Use a timer in the main loop to advance the animation---update the displayed HP by one point every 50 milliseconds until it reaches the actual HP. During animation, the HUD still shows the target HP number, but the bar visually catches up.

**Exercise 3: Entity Comparison in Look Mode**

When the cursor is on an entity in look mode, show a comparison with the player. If the entity has a `Fighter` component, display its ATK and DEF alongside the player's. Use color to indicate which side has the advantage: green for the higher stat, red for the lower.

**Exercise 4: Status Effect Indicators**

Add a `StatusEffects` component that tracks active effects on an entity (poisoned, burning, confused). Display active effects as colored glyphs next to the entity name in the HUD or tooltip. Each effect has a duration displayed as a countdown. Consider how effects interact with the HP bar color.

**Exercise 5: Context-Sensitive Hints**

Replace the static control hints in the HUD with context-sensitive ones. When standing on an item, show "g: pick up". When adjacent to an enemy, show "bump: attack". When the inventory is full, show "d: drop". The hints should reflect what the player *can* do right now, not a fixed list of all keys.

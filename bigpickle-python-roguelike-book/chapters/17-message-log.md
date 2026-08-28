# Chapter 17: The Message Log

Roguelikes are fundamentally text games. The map is a grid of glyphs, the items are named tokens, and the story of every turn unfolds as a stream of sentences. When the player bumps into an orc, the game needs to say what happened. When a fireball blasts three goblins at once, the game needs to say that too. Any game can show numbers changing on a health bar, but a roguelike communicates through the written word.

That written channel is the **message log**, and this chapter gives it the attention it deserves. We replace the ad-hoc, purely-gray log from earlier chapters with a proper system: a `Message` component that pairs text with a color, a `MessageLog` that stores and trims history, color-coded messages so the player can scan the log at a glance, a panel that renders the newest messages at the bottom of the screen, a full-screen scrollable history view, and contextual messages that describe different actions differently.

By the end of this chapter the log stops being a debugging convenience and becomes a first-class part of the game's interface---one the player can read, rely on, and page through.

## Why a Message Log?

Imagine a fight without a message log. The player bumps an orc, the orc's hit points drop, the player's drop, and neither party learns anything beyond the changing numbers on the panel. The player cannot tell whether an attack landed, whether it was deflected, whether the enemy is confused, fleeing, or dead. Each turn becomes a mystery that the player must reverse-engineer from the positions of glyphs on the map.

The message log solves this by narrating the turn. Every significant event produces a sentence: who attacked whom, how much damage was dealt, what item was picked up, what effect a scroll had. This is not flavor text---it is *information*. In a dense dungeon with half a dozen enemies on screen, the log is the only reliable record of what just happened.

The log also does something subtle and powerful: it gives the world a sense of causality. When an orc flees, the log explains why ("The orc flees in terror!"). When a scroll fizzles for lack of a target, the log explains that too. The player always understands the why, not just the what. That understanding is what turns a collection of systems into a believable world.

Finally, the log has a memory. The window at the bottom of the screen shows only the newest few messages, but the full history persists---up to a hundred messages in this chapter's implementation. The player can page back through the entire record of the descent, reviewing mistakes and clarifying exactly what happened several turns ago.

## Message Component

A message is two things: the text the player reads and the color it is rendered in. We model both with a `Message` attrs class:

```python
from __future__ import annotations
import attrs


@attrs.define
class Message:
    text: str
    color: tuple[int, int, int] = (255, 255, 255)
```

The `text` is the sentence to display. The `color` is an RGB triple, defaulting to white. Because it is an `attrs.define` class, we get value semantics for free: two `Message` instances with the same text and color compare equal, and the class is immutable by convention. That immutability matters because messages are accumulated over time and re-rendered on demand; once created, a message should never change.

The RGB triple deserves a moment of attention. tcod's `console.print` accepts foreground and background colors as `(r, g, b)` tuples, and the `Message.color` we store is passed straight through to that call. This is the same color representation we have used for `Renderable.fg` since Chapter 6, so there is nothing new here---just the same 24-bit RGB convention applied to text.

With `Message` defined, we can create a little example of how it will be used:

```python
msg = Message(text="You pick up the Health Potion.", color=(255, 165, 0))
```

The message is now self-contained: everything the renderer needs—the words and the hue---travels together as one value.

## Message Log Component

A single message is ephemeral unless something stores it. That something is the `MessageLog`, also defined in the components module:

```python
@attrs.define
class MessageLog:
    messages: list[Message] = attrs.Factory(list)
    max_messages: int = 100
    history_offset: int = 0

    def add(self, text: str, color: tuple[int, int, int] = (255, 255, 255)) -> None:
        self.messages.append(Message(text=text, color=color))
        if len(self.messages) > self.max_messages:
            self.messages.pop(0)

    @property
    def recent(self) -> list[Message]:
        return self.messages[-5:]

    def get_visible(self, count: int = 5) -> list[Message]:
        """Get messages for display."""
        if not self.messages:
            return []
        start = max(0, len(self.messages) - count)
        return self.messages[start:]
```

There are four moving parts here.

**`messages`** is the backing list. `attrs.Factory(list)` gives each `MessageLog` its own fresh list rather than sharing a single class-level list---a classic Python footgun that `attrs` sidesteps for us.

**`add()`** is the one way messages enter the log. It wraps the given text and color in a `Message` and appends it. The trim logic is simple: if the list would exceed `max_messages`, we pop the *oldest* message off the front. A roguelike session can generate text faster than the player can read it, and without a bound the log would grow without limit. The cap of 100 messages keeps memory and rendering predictable.

**`recent`** is a read-only property returning the last five messages. It is convenient for quick inspections of the newest state. (In this chapter's panel we use `get_visible` instead, because it lets the caller choose the count, but `recent` documents the intent that "a handful of recent messages" is the common case.)

**`get_visible()`** is what the renderer actually calls. It takes a `count` and returns up to `count` of the newest messages, computing a start index that never goes negative. When the log is empty it returns an empty list rather than erroring. This keeps the boundary conditions safe: an empty log, a log shorter than the display window, and a full log all render without special-casing in the rendering code.

## Color-Coded Messages

The whole point of adding a color to each message is that the player can scan the log and grasp the situation at a glance. Damage-in is not the same as damage-out, which is not the same as healing, which is not the same as a hint. Color makes those categories visually distinct before the player reads a single word.

We centralize the palette in a dedicated module rather than scattering raw tuples through the codebase:

```python
"""Shared color palette for console output and the message log."""
from __future__ import annotations

# --- Base colors ---------------------------------------------------------
WHITE = (255, 255, 255)
GRAY = (200, 200, 200)
DIM_GRAY = (128, 128, 128)
BLACK = (0, 0, 0)

# --- Feedback colors -----------------------------------------------------
YELLOW = (255, 255, 0)          # player dealing damage
LIGHT_CYAN = (120, 200, 255)    # informative hints
CYAN = (0, 255, 255)            # equipment / magic
GREEN = (0, 255, 0)             # healing
RED = (255, 0, 0)               # player taking damage
LIGHT_RED = (255, 120, 120)
ORANGE = (255, 165, 0)          # item pickups
BLUE = (150, 150, 255)          # XP / level ups
PURPLE = (200, 120, 255)        # magical scrolls

# --- Panel accent colors -------------------------------------------------
PANEL_BORDER = (100, 100, 100)
PANEL_TEXT = (255, 255, 255)
PANEL_SUBTEXT = (180, 180, 180)

# --- Log history window --------------------------------------------------
HISTORY_FG = (200, 200, 255)
HISTORY_BG = (0, 0, 0)
HISTORY_TITLE = (255, 255, 255)
HISTORY_HINT = (150, 150, 150)
```

Naming these constants does two jobs. It makes call sites readable---`log.add("...", GREEN)` is self-documenting where `log.add("...", (0, 255, 0))` forces the reader to decode a tuple. And it makes the color scheme a single point of truth: to retheme the whole game, change the constants here and nowhere else.

The mapping we use throughout the game:

| Color | Meaning |
|-------|---------|
| `WHITE` | Neutral narration and world text |
| `GRAY` | Help and control hints |
| `YELLOW` | The player dealing damage, warnings, blocked actions |
| `RED` | The player taking damage |
| `LIGHT_RED` | Defeated enemies and fleeing creatures |
| `GREEN` | Healing |
| `ORANGE` | Item pickups and inventory feedback |
| `BLUE` | XP gains and level ups |
| `PURPLE` | Magical events (scrolls, confusion) |
| `CYAN` | Equipment and magic items |

The consistency is what matters. Red always means "you are being hurt." Green always means "you are healing." The player internalizes these mappings over time, and the log becomes readable at a glance---which is exactly the goal.

## Message Rendering

A log full of colored messages is useless if it never reaches the screen. Rendering the log means printing the newest `N` messages at the bottom of the console, in order, newest last.

In Chapter 16 the renderer drew a handful of fixed rows at the bottom. This chapter formalizes that into a proper panel with a separator line, the player's stats, and the recent messages:

```python
"""Rendering functions with message log."""
from __future__ import annotations
from typing import TYPE_CHECKING
import tcod.console

if TYPE_CHECKING:
    import tcod.ecs
    from game_map import GameMap
    from components import MessageLog


PANEL_HEIGHT = 7
MAP_HEIGHT = 43  # SCREEN_HEIGHT - PANEL_HEIGHT
```

The screen is split into two fixed regions. `MAP_HEIGHT` (43 rows) is where the dungeon renders, and `PANEL_HEIGHT` (7 rows) is the panel below it. Their sum is the total console height. Dividing the screen this way guarantees the map never overlaps the log.

The map and entity rendering are unchanged from earlier chapters, so we focus on the panel:

```python
def render_panel(console, player, message_log):
    """Render the bottom panel with stats and messages."""
    panel_y = MAP_HEIGHT

    # Separator line
    for x in range(console.width):
        console.print(x=x, y=panel_y, string="─", fg=(100, 100, 100))

    # Player stats
    from components import Fighter, Name, Equipment, Equippable
    fighter = player.components[Fighter]
    name = player.components[Name].name
    stats = f"{name}  HP: {fighter.hp}/{fighter.max_hp}"
    console.print(x=1, y=panel_y + 1, string=stats, fg=(255, 255, 255))

    # Equipment
    equip = player.components.get(Equipment)
    if equip:
        weapon_name = equip.weapon.components[Name].name if equip.weapon else "None"
        armor_name = equip.armor.components[Name].name if equip.armor else "None"
        equip_str = f"Weapon: {weapon_name}  Armor: {armor_name}"
        console.print(x=1, y=panel_y + 2, string=equip_str, fg=(180, 180, 180))

    # Messages
    messages = message_log.get_visible(4)
    for i, msg in enumerate(messages):
        console.print(x=1, y=panel_y + 3 + i, string=msg.text[:console.width - 2], fg=msg.color)
```

The panel is seven rows tall, laid out as follows:

- Row 0 is the separator line, a horizontal rule of box-drawing characters in gray.
- Row 1 is the player's name and hit points.
- Row 2 is the currently equipped weapon and armor.
- Rows 3 through 6 are the four newest messages.

The message rendering deserves close attention. We call `get_visible(4)` to fetch the newest four messages. For each we call `console.print`, passing the message's stored color directly as `fg`. We slice the text to `console.width - 2` so a long message cannot wrap (or worse, overflow) past the console edge. The loop assigns rows starting at `panel_y + 3`, so the newest message in the list occupies the last of the four rows---right where the eye lands after reading the stats.

Because `get_visible` returns newest-last, message zero is the fourth-newest and message three is the newest. The newest words appear on the bottom row, directly above the screen edge, which matches how terminal scrollback and most chat logs present new content.

`render_all` glues it together, rendering the map, the entities, and finally the panel on top:

```python
def render_all(console, game_map, registry, player, message_log):
    """Render everything."""
    from components import Position
    player_pos = player.components[Position]
    camera_x = player_pos.x - console.width // 2
    camera_y = player_pos.y - MAP_HEIGHT // 2
    camera_x = max(0, min(camera_x, game_map.width - console.width))
    camera_y = max(0, min(camera_y, game_map.height - MAP_HEIGHT))

    console.clear()
    render_map(console, game_map, camera_x, camera_y)
    render_entities(console, registry, game_map, camera_x, camera_y)
    render_panel(console, player, message_log)
```

The panel renders last, so it always draws over anything beneath it. The camera is clamped to the map bounds so it never scrolls past the map's edges, and the panel always sits at the fixed screen-bottom region.

## The Message Log UI

With the log component defined and the panel rendering it, we wire the log into the game's main loop. The game creates a single `MessageLog`, seeds it with welcome text, and passes it to every system that needs to narrate events.

At the top of `main.py`:

```python
def _add_welcome(log: MessageLog) -> None:
    """Print the opening messages and a control summary."""
    log.add("You descend into the dungeon.", WHITE)
    log.add(
        "g:pickup  f/u:use  e:equip  .:wait  v:log history  ?:controls",
        GRAY,
    )
```

The welcome message sets the scene and the hint line reminds the player of the controls---including the `v` key that opens the full history view we build next.

In `main()` we create the log and pass it into every system that produces narration:

```python
registry = tcod.ecs.Registry()
log = MessageLog(max_messages=100)
_add_welcome(log)
```

The screen constants now derive from the render functions:

```python
from render_functions import MAP_HEIGHT, PANEL_HEIGHT, render_all

SCREEN_WIDTH = 80
SCREEN_HEIGHT = MAP_HEIGHT + PANEL_HEIGHT
```

Defining `SCREEN_HEIGHT` as the sum of the two regions keeps the map height and panel height in a single source of truth instead of hard-coded magic numbers scattered through the file.

The turn loop passes the log into the combat, AI, and item systems so every action can report on itself:

```python
turn_spent = process_player_action(action, registry, dungeon, log)
...
process_ai_turns(registry, dungeon, player, graph, log)
resolve_enemy_attacks(registry, dungeon, player, log)
remove_dead_entities(registry, log, player)

if player.components[Fighter].hp <= 0:
    log.add("You have been defeated!", (255, 0, 0))
    game_over = True

needs_render = True
```

Every one of those functions takes `log` as a parameter and calls `log.add(...)` to narrate. The log is a single shared object threaded through the systems, so every subsystem---combat, AI, items, equipment, death---writes into the same accumulated record. This is the ECS philosophy applied to the UI: systems stay decoupled from one another, but all of them communicate through one shared, well-typed channel.

The `log` is deliberately *not* stored on the world entity here. Passing it explicitly makes the dependency visible at every call site, which keeps the flow of data easy to trace. Whether the log lives as a parameter or as a component on the world entity is a design choice; the parameter approach keeps this chapter's systems explicit and self-contained.

## Log History

Four rows of messages is enough to follow a fight in real time, but not enough to answer questions like "did I actually pick up that sword two minutes ago?" For that, the player needs the full record. We add a full-screen, scrollable history view that we can open and close at will.

The history renderer draws the entire log into a framed window over the whole console:

```python
def render_history(
    console: tcod.console.Console,
    log: MessageLog,
    offset: int,
) -> None:
    """Render the full, scrollable message log over the whole screen."""
    console.clear()
    console.draw_frame(
        x=0,
        y=0,
        width=console.width,
        height=console.height,
        title="Message Log",
        fg=PANEL_TEXT,
        bg=(40, 40, 40),
    )

    total = len(log.messages)
    inner_width = console.width - 4
    inner_height = console.height - 5
    end = max(0, total - offset)
    start = max(0, end - inner_height)
    visible = log.messages[start:end]

    for i, msg in enumerate(visible):
        y = 1 + i
        console.print(x=2, y=y, string=msg.text[:inner_width], fg=msg.color)

    page_start = total - len(visible)
    footer = (
        f"Showing {page_start + 1}-{page_start + len(visible)} of {total}   "
        f"[up/down] scroll   [esc/space] close"
    )
    console.print(x=2, y=console.height - 2, string=footer[: inner_width], fg=HISTORY_HINT)
```

`console.draw_frame` draws a border around the whole console with the title "Message Log" in the top border---an instantly recognizable framing that tells the player they have changed modes.

The scrolling math is worth unpacking. `total` is the number of messages in the log. The `offset` parameter is how many of the *newest* messages we have scrolled past. `end` is therefore `total - offset`, and `start` backs up `inner_height` rows from there, but never below zero. The slice `messages[start:end]` is the visible page: the most recent messages, or a page scrolled up into history when `offset` is large.

The footer reports the visible range ("Showing 12-30 of 45") so the player always knows how far back they are, and it lists the scrolling and close keys as a reminder. This is exactly the "current page / total" convention from a terminal pager like `less`.

The window into the log lives in the main loop's state. We track whether we are viewing history and how far we have scrolled:

```python
viewing_history = False
history_offset = 0
```

While `viewing_history` is true, the loop renders `render_history` instead of `render_all`:

```python
if needs_render:
    if viewing_history:
        render_history(console, log, history_offset)
    else:
        render_all(console, dungeon, registry, player, log)
    context.present(console)
    needs_render = False
```

The key handling branches on the mode. In normal play, pressing `v` opens the history view and resets the scroll to the newest page:

```python
if event.sym == tcod.event.KeySym.v:
    viewing_history = True
    history_offset = 0
    needs_render = True
    continue
```

While viewing history, `Page Up` (or `k` / `Up`) scrolls up toward older messages, `Page Down` (or `j` / `Down`) scrolls back down toward newer ones, and `Escape`, `Space`, `Return`, or `v` closes the view:

```python
if viewing_history:
    if event.sym in (
        tcod.event.KeySym.UP,
        tcod.event.KeySym.k,
        tcod.event.KeySym.PAGEUP,
    ):
        history_offset += 3
        needs_render = True
    elif event.sym in (
        tcod.event.KeySym.DOWN,
        tcod.event.KeySym.j,
        tcod.event.KeySym.PAGEDOWN,
    ):
        history_offset = max(0, history_offset - 3)
        needs_render = True
    elif event.sym in (
        tcod.event.KeySym.SPACE,
        tcod.event.KeySym.RETURN,
        tcod.event.KeySym.v,
    ):
        viewing_history = False
        needs_render = True
    continue
```

Scrolling by three rows per key press matches the panel's windowing---you page up in roughly the same chunk you see at once. The `max(0, ...)` clamp on the downward scroll keeps `history_offset` from dipping below zero, mirroring how `render_history` clamps the slice bounds. The `continue` after the block is essential: while the history is open, *no* other keys are interpreted as gameplay input. The `v`, `k`, and `j` keys become page controls rather than their normal gameplay meanings, and returning from history modes is a deliberate action, not an accidental side effect.

Note that `Escape` is handled before the history block:

```python
if event.sym == tcod.event.KeySym.ESCAPE:
    if viewing_history:
        viewing_history = False
        needs_render = True
        continue
    raise SystemExit()
```

So Escape closes the history view if one is open, and only quits the game when the history is already closed. That is a friendly touch: the "escape" key's meaning depends on context, and it always does the least disruptive thing.

## Contextual Messages

A good message log does not just report numbers---it reports *meaning*. This chapter differentiates messages by what happened, choosing both the words and the color to match the context. Let us trace the major categories through the actual systems.

### Attacking

The `attack` function in `combat.py` composes its message based on who is attacking whom. It returns a `(text, color)` pair so the caller can log it:

```python
def attack(attacker: Entity, target: Entity) -> tuple[str, tuple[int, int, int]]:
    """Resolve a melee attack. Returns a (message, color) pair."""
    attacker_name = attacker.components[Name].name
    target_name = target.components[Name].name

    power = get_power(attacker)
    defense = get_defense(target)
    damage = max(0, power - defense)

    if damage > 0:
        target.components[Fighter].hp -= damage
        return (
            f"{attacker_name} attacks {target_name} for {damage} damage.",
            YELLOW if attacker.tags.contains("player") else RED,
        )
    return (
        f"{attacker_name} attacks {target_name} but does no damage.",
        DIM_GRAY,
    )
```

Two details make this contextual rather than generic. First, the color depends on *whose* attack it is: when the player lands a hit it shows in `YELLOW` (you dealt damage), but when the player is hit it shows in `RED` (you took damage). Second, a hit that is entirely blocked by defense reports zero damage with the words "but does no damage" in a dull `DIM_GRAY`---a distinct, muted message that tells the player they got no value from the exchange.

The caller in `_player_bump` takes that pair and logs it:

```python
msg, color = attack(attacker=action.entity, target=other)
log.add(msg, color)
return True
```

### Picking Up Items

Picking up an item reports---and colors---the action:

```python
inv.items.append(item_entity)
_remove_from_map(item_entity)
log.add(f"You pick up the {item.name}.", ORANGE)
return True
```

An `ORANGE` pickup message stands out against the gray and white of ambient text, so the player notices every acquisition. And when something goes wrong, the message explains it:

```python
if len(inv.items) >= inv.capacity:
    log.add("Your inventory is full.", ORANGE)
    return False
...
log.add("There is nothing here to pick up.", WHITE)
return False
```

Note that the "inventory full" and "nothing here" cases do *not* spend a turn (`return False`). Contextual messaging is not just about words---it also tells the player, through the turn system, that these were non-actions.

### Healing

`_use_heal` in `items.py` reports healing distinctively:

```python
if fighter.hp >= fighter.max_hp:
    log.add("Your health is already full.", YELLOW)
    return False

fighter.hp = min(fighter.max_hp, fighter.hp + amount)
log.add(f"You drink the {_item_name(item)} and recover {amount} HP.", GREEN)
_consume(entity, item)
return True
```

A successful heal narrates in `GREEN`---the universal sign of restoration---and tells the player exactly how much was recovered. Wasting a potion on full health narrates in `YELLOW` as a warning and refuses to consume the item, so the player does not squander resources.

### Magic and Confusion

Scrolls are magic, and magic gets `PURPLE`. The confusion scroll:

```python
log.add(
    f"You read the {_item_name(item)}. {target_name} is confused!",
    PURPLE,
)
```

And the fireball:

```python
log.add(f"You hurl the {_item_name(item)}!", PURPLE)
```

Even the failure cases are contextual. When the confusion scroll finds no enemy, it *fizzles*:

```python
log.add("The scroll fizzles; no enemy is in sight.", YELLOW)
```

The verb changes with the situation: a scroll with no target "fizzles," a fireball with nothing in range "fizzles" too in `items.py`, a potion on full health "does nothing." Choosing the right word for the right outcome is what makes the log feel alive instead of templated.

### Enemy Behavior

The AI system reports changes in enemy state. When a hurt hostile breaks and runs, the log explains the new behavior in `LIGHT_RED`:

```python
ai.kind = AIKind.FLEEING
log.add(
    f"The {_name(entity)} flees in terror!",
    LIGHT_RED,
)
```

And when confusion wears off, the log narrates the return to normal in `PURPLE`, matching the magic that caused it:

```python
log.add(f"The {_name(entity)} shakes off its confusion!", PURPLE)
```

These messages do more than decorate: they teach the player the rules. If a goblin suddenly "flees in terror," the player learns the fleeing AI mechanic. If a confused creature "shakes off its confusion," the player learns that confusion is temporary. The log is how the game communicates its own rules to the player.

### Death and XP

`remove_dead_entities` in `combat.py` narrates each victory and each reward, using two different colors:

```python
log.add(f"{name} has been defeated!", LIGHT_RED)
...
log.add(f"You gain {value} XP.", BLUE)
_check_level_up(xp, log)
```

And the level-up message uses `BLUE` too:

```python
log.add(f"You reach level {xp.level}!", BLUE)
```

A chain of kills produces a stream readers can follow: `LIGHT_RED` for each defeated enemy, then `BLUE` for the XP and level gains. The player can read the story of a fight entirely in color.

### Equipment

Equipment swaps report in `CYAN`, the book's color for equipment and magic:

```python
log.add(
    f"You equip the {_item_name(item)} (+{equippable.power_bonus} power).",
    CYAN,
)
```

And failures warn in `YELLOW`:

```python
log.add(f"You have no equipment slots.", YELLOW)
log.add(f"The {_item_name(item)} cannot be equipped.", YELLOW)
```

### The Color Convention in Practice

Stepping back, the thread running through every one of these examples is a *convention*. The game has decided, once, that:

- `YELLOW` means "you did something that changed the world, or something went wrong with your attempt."
- `RED` means "you are being hurt."
- `GREEN` means "you are healing."
- `PURPLE` means "magic is at work."
- `CYAN` means "equipment and items."
- `BLUE` means "progress and reward."
- `ORANGE` means "acquisitions."

Because the convention is defined once in `palette.py` and followed consistently everywhere, the player learns a color language that reads at a glance. That is the payoff of centralizing the palette: not just a single place to edit colors, but a single vocabulary the whole game adheres to.

## Exercises

**Exercise 1: Message Filtering**

Add a `category` field to the `Message` class (e.g., `"combat"`, `"pickup"`, `"level", "system"`). Add methods to `MessageLog`--`def clear_category(self, category)` and a display flag--so the player can mute a category of noise. For example, a toggle key could hide all `"pickup"` messages so the log only shows combat and leveling. Consider which categories should be filterable and which (like "player is being hurt") should never be hidden.

**Exercise 2: Log Search**

Extend the history view with a search mode. When the player presses a key (e.g., `/`), let them type a filter term at the bottom of the history window. Only messages whose text contains the term are shown, and the footer count reflects the filtered total: "Showing 1-6 of 6 matches." Navigate forward and backward between matches. This turns the log from a passive record into a queryable history of the run.

**Exercise 3: Timestamps and Turn Numbers**

Add a `turn` integer field to `Message`, and record the current global turn counter when `add()` is called. Display the turn number as a dim prefix in the history view (e.g., `[t42] The orc attacks you for 5 damage.`). Then, as a stretch goal, store timestamps---the real wall-clock time the message was generated---so the player can see not only when in the run something happened but how long a fight actually took.

**Exercise 4: Message Stacking**

Adjacent identical messages are repetitive ("The orc attacks you for 5 damage." ten times in a row). Implement *stacking*: when a new message exactly matches the most recent message, increment a hidden count instead of appending a new line, and render the count as a suffix (e.g., "The orc attacks you for 5 damage. x3"). Because `Message` is an `attrs.define`, equality comparison works for free---use it to detect identical consecutive messages.

**Exercise 5: Filtered Log Categories**

Build on Exercise 1 to add *color-coded category filtering*. Give each message a category derived from its section (combat, pickup, equipment, magic, leveling). Add two-key toggles (e.g., press `c` then `x` to mute a category). Because each category already has a consistent color, let the player mute categories by color family. This turns the entire color scheme into an active interface rather than passive styling.

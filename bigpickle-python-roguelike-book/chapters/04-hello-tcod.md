# Chapter 4: Hello tcod

We have set up the project, installed the dependencies, and verified that a window opens. Now it is time to understand what is inside that window. This chapter introduces the tcod library in depth: its architecture, its core abstractions, and the API you will use in every chapter that follows. By the end, you will have a working program that draws a player character on screen and moves it with the arrow keys.

That may sound simple, and it is. But the patterns underneath are not. The game loop, the console, the tileset, the context, the event system---these are the building blocks of every roguelike you will ever build with tcod. Understanding them now pays dividends for the rest of the book.

## Understanding the tcod Architecture

tcod is a Python wrapper around **libtcod**, a C library originally written for the game *Dungeon Hack* in the early 2000s. libtcod handles the low-level work of rendering tile-based graphics, managing fonts, and processing input. tcod wraps libtcod using **cffi** (C Foreign Function Interface for Python), which gives us a Pythonic API while retaining the performance of a native library.

Modern tcod (version 13 and later) uses a **context-based API**. Earlier versions of tcod relied on module-level global state---a `tcod.console_init_root()` call that set up a single global window, with all subsequent operations referencing that implicit context. The current API replaces this with an explicit `Context` object that manages the SDL window and rendering. This is a cleaner design: it makes it possible to have multiple windows, avoids hidden global state, and integrates properly with Python's context manager protocol.

The library is organized into several key modules. You do not need to memorize all of them, but you should know where to look:

- **`tcod.context`** -- Manages the application window and the connection between your console and the display. This is where windows are created and frames are presented.
- **`tcod.console`** -- Provides the `Console` class, a 2D grid of characters that serves as the canvas for all rendering. Everything in your game is drawn to a console.
- **`tcod.tileset`** -- Loads and manages tilesets: the image files that define what each character looks like on screen. A tileset maps character codes to pixel data.
- **`tcod.event`** -- The event system. Handles keyboard input, mouse input, window close events, and other SDL events. This is how your game receives player input.
- **`tcod.color`** -- Color utilities, though in practice we usually use plain RGB tuples instead.

We will use all of these modules in this chapter. Let us start with the most fundamental: the console.

## The Console

The `Console` is a 2D grid of character cells. Think of it as a rectangular array of slots, where each slot holds a character, a foreground color, and a background color. You write to the console, then tell tcod to render that console to the window.

Creating a console is straightforward:

```python
import tcod.console

console = tcod.console.Console(width=80, height=50)
```

This creates an 80-column, 50-row console. Each cell in this grid can hold three pieces of data:

- **char** -- The character displayed in the cell. This can be a string (like `"@"` or `"#"`), an integer (an ordinal like `ord("@")` which is 64), or a Unicode code point.
- **fg** -- The foreground color. This is the color of the character itself. Specified as an RGB tuple like `(255, 255, 255)` for white, or `(0, 0, 0)` for black.
- **bg** -- The background color. The color behind the character. Specified the same way as fg.

### Printing Styled Text

The simplest way to write to the console is the `print` method:

```python
console.print(x=1, y=1, string="Hello, Dungeon!", fg=(255, 255, 255))
```

This places the string starting at column 1, row 1, with white text on the default black background. The `fg` parameter is optional; omitting it uses the default white. You can also set `bg` to color the background behind the text:

```python
console.print(x=1, y=1, string="HP: 20/20", fg=(0, 255, 0), bg=(50, 50, 50))
```

The `print` method handles string wrapping and clipping automatically. If the string is too long to fit on the console, it is clipped rather than causing an error.

### Direct Cell Access

For individual characters, you can access cells directly using bracket notation:

```python
console[5, 3] = (ord("@"), (255, 255, 255), (0, 0, 0))
```

This sets the character at column 5, row 3 to `@` with white foreground and black background. The tuple format is `(char, fg, bg)`. Note that the indexing is `[y, x]`, not `[x, y]`---this matches the row-major convention of the underlying C array.

You can also set individual properties:

```python
console[5, 3].ch = ord("@")
console[5, 3].fg = (255, 255, 255)
console[5, 3].bg = (0, 0, 0)
```

Direct cell access is useful when you are drawing individual tiles---placing walls, items, enemies, and the player character on a map. The `print` method is better for longer strings like messages and UI labels.

### Console Attributes

The console exposes its dimensions as attributes:

```python
console.width   # 80
console.height  # 50
```

These are useful when you need to center text or calculate positions relative to the screen edges. For example, to center a string horizontally:

```python
x = (console.width - len("Game Over")) // 2
console.print(x=x, y=25, string="Game Over", fg=(255, 0, 0))
```

### Clearing the Console

Before drawing a new frame, you typically clear the console to remove the previous frame's contents:

```python
console.clear()
```

This resets every cell to its default: a null character with default foreground and background colors. You must clear the console each frame before redrawing, or you will see stale content.

## The Tileset

A tileset is an image file that contains a grid of character glyphs. tcod uses the tileset to convert character codes (like `ord("@")`) into pixels on screen. Without a tileset, the console has no visual representation.

tcod provides three ways to load a tileset:

### TrueType Fonts

If you have a `.ttf` or `.otf` font file, you can load it directly:

```python
import tcod.tileset

tileset = tcod.tileset.load_truetype_font(
    path="path/to/font.ttf",
    tile_width=16,
    tile_height=16,
)
```

This rasterizes the font at the specified tile size, creating a tileset where each character fits within a 16x16 pixel cell. TrueType fonts give you flexibility in choosing typefaces, but you need to ensure the font supports the characters you are using.

### Tilesheet Images

Most roguelike tilesets are stored as tilesheet images---PNG files containing a grid of pre-rendered character glyphs. To load a tilesheet:

```python
tileset = tcod.tileset.load_tilesheet(
    path="dejavu10x10_gs_tc.png",
    columns=32,
    rows=8,
    charmap=tcod.tileset.CHARMAP_TCOD,
)
```

The `columns` and `rows` parameters specify the grid dimensions of the image. The `charmap` parameter tells tcod how to map grid positions to character codes. `CHARMAP_TCOD` is the standard mapping used by libtcod's built-in font. There is also `CHARMAP_CP437` for the CP437 character set, which maps the 256 characters of the IBM PC's original character encoding.

### Default Tileset

If you do not have a tileset file handy, tcod provides a built-in default:

```python
tileset = tcod.tileset.get_default()
```

This loads the terminal font that ships with tcod. It works, but it is limited in appearance. For any real project, you will want to use a custom tileset.

### CP437 and Character Maps

CP437 is the character encoding used by the original IBM PC. It includes not just letters and numbers, but also box-drawing characters, card suits, Greek letters, and various symbols. Many roguelike tilesets are arranged in CP437 order, which means the tile at position 0 in the image corresponds to character code 0 in CP437, position 1 corresponds to code 1, and so on.

When you use `CHARMAP_CP437`, tcod uses this standard mapping. When you use `CHARMAP_TCOD`, tcod uses libtcod's custom mapping, which is similar but not identical. Make sure your tileset image matches the charmap you specify, or your characters will be scrambled.

## The Context

The `Context` is the bridge between your console and the operating system's window. It manages the SDL window, handles rendering, and coordinates the display. In modern tcod, you always create a context explicitly.

```python
import tcod.context

with tcod.context.new(
    columns=80,
    rows=50,
    tileset=tileset,
    title="My Roguelike",
) as context:
    # Game loop goes here
    pass
```

The `context.new()` function creates a new context and the associated window. The `columns` and `rows` parameters set the window size in tiles (not pixels). The `tileset` parameter specifies which tileset to use for rendering. The `title` parameter sets the window title.

The `with` statement is important. The context is a **context manager**, which means it handles setup and teardown automatically. When you enter the `with` block, the window is created. When you exit the block (either normally or due to an exception), the window is destroyed and resources are cleaned up. This prevents resource leaks and ensures the window is always properly closed.

### Presenting the Console

To render your console to the window, call `context.present()`:

```python
context.present(console)
```

This takes the console's current state---every character, every color---and renders it to the window using the tileset. The window updates in one atomic operation, so the player never sees a partially drawn frame.

The typical pattern is: clear the console, draw everything, present the context:

```python
console.clear()
console.print(x=1, y=1, string="Hello, World!")
context.present(console)
```

## Event Handling

tcod uses SDL for event handling. The `tcod.event` module provides access to keyboard events, mouse events, window events, and more. The core function is `tcod.event.wait()`, which blocks until at least one event is available:

```python
import tcod.event

for event in tcod.event.wait():
    if isinstance(event, tcod.event.Quit):
        return  # Exit the game
    if isinstance(event, tcod.event.KeyDown):
        print(f"Key pressed: {event.sym}")
```

`tcod.event.wait()` returns a list of events. You iterate over them and check their type using `isinstance()`. The most common event types are:

- **`tcod.event.Quit`** -- The player closed the window or pressed Alt+F4. Handle this by exiting the game loop.
- **`tcod.event.KeyDown`** -- A key was pressed. The `event.sym` attribute gives you the key's symbolic value.
- **`tcod.event.KeyUp`** -- A key was released. Less commonly used in roguelikes, which are typically turn-based.
- **`tcod.event.WindowResized`** -- The window was resized. You may want to handle this to adjust your rendering.

### Reading Key Input

The `event.sym` attribute on a `KeyDown` event is an enum value from `tcod.event.KeySym`. This gives you a platform-independent identifier for the key:

```python
if event.sym == tcod.event.KeySym.UP:
    # Move up
    pass
elif event.sym == tcod.event.KeySym.DOWN:
    # Move down
    pass
elif event.sym == tcod.event.KeySym.LEFT:
    # Move left
    pass
elif event.sym == tcod.event.KeySym.RIGHT:
    # Move right
    pass
elif event.sym == tcod.event.KeySym.ESCAPE:
    # Quit the game
    return
```

You can also use arrow key names, letter keys, and special keys:

```python
tcod.event.KeySym.a          # The 'a' key
tcod.event.KeySym.SPACE      # The spacebar
tcod.event.KeySym.RETURN     # The Enter key
tcod.event.KeySym.ESCAPE     # The Escape key
```

The full list of key symbols is documented in the tcod reference, but you will only use a handful regularly. For a roguelike, the arrow keys, letter keys, Escape, and Enter cover most input needs.

### Non-Blocking vs. Blocking Input

`tcod.event.wait()` is **blocking**---it pauses execution until an event arrives. In a turn-based roguelike, this is exactly what you want. The game waits for the player to act, processes the action, then waits again. No events means no processing, which means the game consumes almost no CPU while waiting.

If you were building a real-time game, you would use `tcod.event.poll()` instead, which returns immediately even if no events are available. For our roguelike, `wait()` is the right choice.

## Building a Game Loop

Now we have all the pieces. Let us assemble them into a working program, building up in stages from a bare window to a movable player character.

### Stage 1: Hello World

The smallest tcod program opens a window, displays text, and closes when the player exits:

```python
import tcod
import tcod.console
import tcod.context
import tcod.event
import tcod.tileset


def main() -> None:
    tileset = tcod.tileset.get_default()

    with tcod.context.new(
        columns=80,
        rows=50,
        tileset=tileset,
        title="Hello tcod",
    ) as context:
        console = tcod.console.Console(80, 50)

        console.print(x=1, y=1, string="Hello, tcod!", fg=(255, 255, 255))
        context.present(console)

        while True:
            for event in tcod.event.wait():
                if isinstance(event, tcod.event.Quit):
                    return


if __name__ == "__main__":
    main()
```

Run this and you should see "Hello, tcod!" displayed in the upper-left corner of the window. The program waits for you to close the window before exiting.

Notice the structure: create the tileset, open the context, create a console, draw to the console, present it, then enter a loop that waits for events. This structure is the skeleton of every tcod program.

### Stage 2: A Player Character

Let us add a player character---the iconic `@` symbol---at the center of the screen:

```python
import tcod
import tcod.console
import tcod.context
import tcod.event
import tcod.tileset


def main() -> None:
    tileset = tcod.tileset.get_default()

    with tcod.context.new(
        columns=80,
        rows=50,
        tileset=tileset,
        title="Hello tcod",
    ) as context:
        console = tcod.console.Console(80, 50)

        player_x = 40
        player_y = 25

        console.clear()
        console[player_y, player_x] = (ord("@"), (255, 255, 255), (0, 0, 0))
        context.present(console)

        while True:
            for event in tcod.event.wait():
                if isinstance(event, tcod.event.Quit):
                    return


if __name__ == "__main__":
    main()
```

The player is placed at position (40, 25), which is near the center of an 80x50 console. We draw it using direct cell access: `console[y, x] = (char, fg, bg)`. The `@` appears as a white character on a black background.

### Stage 3: Movement

Now let us make the player move when arrow keys are pressed:

```python
import tcod
import tcod.console
import tcod.context
import tcod.event
import tcod.tileset


def main() -> None:
    tileset = tcod.tileset.get_default()

    with tcod.context.new(
        columns=80,
        rows=50,
        tileset=tileset,
        title="Hello tcod",
    ) as context:
        console = tcod.console.Console(80, 50)

        player_x = 40
        player_y = 25

        while True:
            console.clear()
            console[player_y, player_x] = (ord("@"), (255, 255, 255), (0, 0, 0))
            context.present(console)

            for event in tcod.event.wait():
                if isinstance(event, tcod.event.Quit):
                    return

                if isinstance(event, tcod.event.KeyDown):
                    if event.sym == tcod.event.KeySym.UP:
                        player_y -= 1
                    elif event.sym == tcod.event.KeySym.DOWN:
                        player_y += 1
                    elif event.sym == tcod.event.KeySym.LEFT:
                        player_x -= 1
                    elif event.sym == tcod.event.KeySym.RIGHT:
                        player_x += 1
                    elif event.sym == tcod.event.KeySym.ESCAPE:
                        return


if __name__ == "__main__":
    main()
```

This is a significant change. The `console.clear()`, draw, and `present()` calls are now inside the `while True` loop, which means they run every frame. Each time the player presses an arrow key, the position variables update, the console is redrawn, and the context presents the new frame.

The game loop now has a clear structure:

1. **Clear** the console.
2. **Draw** the game state (the player at its current position).
3. **Present** the console to the window.
4. **Wait** for input.
5. **Process** the input (update game state).
6. **Repeat.**

This is the classic roguelike game loop. It is turn-based: nothing happens until the player acts. The game sits in `tcod.event.wait()`, consuming negligible CPU, until a key is pressed.

### Stage 4: Boundary Checking

There is a problem with the current code: the player can move off the edge of the screen. If the player reaches position (-1, 25) or (80, 25), the console will either raise an error or draw outside its bounds. Let us add boundary checking:

```python
import tcod
import tcod.console
import tcod.context
import tcod.event
import tcod.tileset


def main() -> None:
    tileset = tcod.tileset.get_default()

    with tcod.context.new(
        columns=80,
        rows=50,
        tileset=tileset,
        title="Hello tcod",
    ) as context:
        console = tcod.console.Console(80, 50)

        player_x = 40
        player_y = 25

        while True:
            console.clear()
            console[player_y, player_x] = (ord("@"), (255, 255, 255), (0, 0, 0))
            context.present(console)

            for event in tcod.event.wait():
                if isinstance(event, tcod.event.Quit):
                    return

                if isinstance(event, tcod.event.KeyDown):
                    if event.sym == tcod.event.KeySym.UP:
                        player_y = max(0, player_y - 1)
                    elif event.sym == tcod.event.KeySym.DOWN:
                        player_y = min(console.height - 1, player_y + 1)
                    elif event.sym == tcod.event.KeySym.LEFT:
                        player_x = max(0, player_x - 1)
                    elif event.sym == tcod.event.KeySym.RIGHT:
                        player_x = min(console.width - 1, player_x + 1)
                    elif event.sym == tcod.event.KeySym.ESCAPE:
                        return


if __name__ == "__main__":
    main()
```

The `max(0, ...)` and `min(console.width - 1, ...)` calls clamp the position to valid console coordinates. `max(0, player_y - 1)` prevents negative indices. `min(console.height - 1, player_y + 1)` prevents indices at or beyond the console boundary. The player now bounces off the edges of the screen instead of walking off into the void.

Notice that we use `console.width` and `console.height` for the boundary values instead of hardcoding 80 and 50. This makes it easy to change the window size later without hunting for magic numbers.

## Complete Code

Here is the final, complete program. It opens an 80x50 window, draws a white `@` at the center, and lets the player move it with the arrow keys. The `@` cannot leave the screen. Press Escape or close the window to quit.

```python
import tcod
import tcod.console
import tcod.context
import tcod.event
import tcod.tileset


def main() -> None:
    tileset = tcod.tileset.get_default()

    with tcod.context.new(
        columns=80,
        rows=50,
        tileset=tileset,
        title="Hello tcod",
    ) as context:
        console = tcod.console.Console(80, 50)

        player_x = 40
        player_y = 25

        while True:
            console.clear()
            console[player_y, player_x] = (ord("@"), (255, 255, 255), (0, 0, 0))
            context.present(console)

            for event in tcod.event.wait():
                if isinstance(event, tcod.event.Quit):
                    return

                if isinstance(event, tcod.event.KeyDown):
                    if event.sym == tcod.event.KeySym.UP:
                        player_y = max(0, player_y - 1)
                    elif event.sym == tcod.event.KeySym.DOWN:
                        player_y = min(console.height - 1, player_y + 1)
                    elif event.sym == tcod.event.KeySym.LEFT:
                        player_x = max(0, player_x - 1)
                    elif event.sym == tcod.event.KeySym.RIGHT:
                        player_x = min(console.width - 1, player_x + 1)
                    elif event.sym == tcod.event.KeySym.ESCAPE:
                        return


if __name__ == "__main__":
    main()
```

Save this as `main.py` and run it:

```bash
python main.py
```

You should see a window with a white `@` in the center. Arrow keys move the character. Escape closes the program.

This is a small program, but it contains every major concept you need for tcod-based roguelike development: the console for rendering, the tileset for character display, the context for window management, the event system for input, and the game loop that ties them all together. Every chapter from here on builds on this foundation.

## Exercises

**Exercise 1: A Stationary Entity**

Add a second entity to the screen---a red `g` representing a goblin. Place it at position (20, 15). The player should be able to walk around the goblin but not through it. You will need to add boundary checking for the goblin's position as well as the player's. Hint: check whether the player's target position matches the goblin's position before allowing movement.

**Exercise 2: Custom Window Size**

Change the window dimensions to 100 columns by 40 rows. Update the player's starting position to the new center. Verify that boundary checking still works correctly at the new edges.

**Exercise 3: Keyboard Hints**

Use `console.print()` to display a help message at the bottom of the screen, such as "Arrow keys: move | Escape: quit". Choose a position that does not interfere with the player's movement area. Experiment with different foreground colors for the hint text.

# Chapter 3: Project Setup and Tooling

## Prerequisites

Before you begin, ensure you have the following installed on your system:

- **Python 3.12 or newer.** tcod and tcod-ecs require modern Python features. Check your version with `python --version`.
- **pip or uv.** pip comes bundled with Python. uv is a faster alternative that we will use throughout this book. Install uv with `pip install uv`.
- **A terminal.** You need a command-line interface to run Python, install packages, and launch your game. On Windows, use PowerShell or Windows Terminal. On macOS, use Terminal. On Linux, use your distribution's default terminal emulator.
- **A text editor or IDE.** We recommend VS Code with the Python extension. Any editor with Python support works.

You do not need prior experience with tcod, ECS, or roguelike development. We will cover everything from the ground up.

## Creating the Project

We will use uv for project scaffolding and dependency management. If you prefer pip, the manual setup steps are included as well.

**Using uv (recommended):**

```bash
uv init roguelike
cd roguelike
```

This creates a basic Python project with a `pyproject.toml` and a starter `main.py`. We will replace these files as we build out the project structure.

**Manual setup:**

```bash
mkdir roguelike
cd roguelike
```

Then create the files by hand as described in the following sections. Both approaches produce the same result.

## Virtual Environment

A virtual environment isolates your project's dependencies from the global Python installation. This prevents version conflicts between projects and ensures reproducible builds.

**Creating with uv:**

```bash
uv venv
```

uv creates a `.venv` directory in your project root and configures itself to use it automatically. You do not need to activate it manually when using uv.

**Creating with Python:**

```bash
python -m venv .venv
```

Then activate it before installing packages:

```bash
# Windows (PowerShell)
.venv\Scripts\Activate.ps1

# macOS / Linux
source .venv/bin/activate
```

You should see the virtual environment name in your terminal prompt when it is active.

## Dependencies

Install the core libraries your roguelike needs:

```bash
# With uv
uv add tcod tcod-ecs numpy attrs

# With pip (with venv activated)
pip install tcod tcod-ecs numpy attrs
```

Here is what each dependency provides:

- **tcod** -- The tile-based console library. Handles rendering, input, and the main game loop.
- **tcod-ecs** -- The Entity-Component-System framework. Manages entities, components, queries, and relations.
- **numpy** -- Array operations for the game map. tcod uses numpy arrays for tile data.
- **attrs** -- Concise class definitions for components and data structures.

If you are using pip, save your dependencies to a requirements file:

```bash
pip freeze > requirements.txt
```

This lets you or a collaborator reinstall the exact same versions later.

## Project Structure

The directory tree below shows the full structure we will build throughout this book. Each directory serves a clear purpose. Files are organized by their architectural role rather than by feature.

```
roguelike/
├── src/
│   ├── __init__.py
│   ├── main.py
│   ├── engine.py
│   ├── game_map.py
│   ├── tile_types.py
│   ├── components/
│   │   ├── __init__.py
│   │   ├── physical.py
│   │   ├── combat.py
│   │   ├── items.py
│   │   └── ai.py
│   ├── systems/
│   │   ├── __init__.py
│   │   ├── movement.py
│   │   ├── combat.py
│   │   └── ai.py
│   ├── factories/
│   │   ├── __init__.py
│   │   ├── actors.py
│   │   └── items.py
│   ├── procgen.py
│   ├── color.py
│   ├── input_handlers.py
│   └── render_functions.py
├── saves/
├── pyproject.toml
└── README.md
```

Let us walk through each directory and file:

**`src/`** -- The main source directory. All game code lives here.

**`src/main.py`** -- The entry point. Initializes tcod, creates the engine, and runs the main loop.

**`src/engine.py`** -- The central game engine. Owns the registry, manages systems, and coordinates updates between input, logic, and rendering.

**`src/game_map.py`** -- The game map class. Wraps the numpy array of tiles and provides methods for querying walkability, line of sight, and other map properties.

**`src/tile_types.py`** -- Tile definitions. Each tile type is a named numpy structured array entry with properties like walkable, transparent, and dark/light appearance.

**`src/components/`** -- Component definitions organized by category:
- `physical.py` -- `Position`, `Renderable`, `Velocity`
- `combat.py` -- `Health`, `Power`, `Defense`
- `items.py` -- `Consumable`, `Equipment`, `Inventory`
- `ai.py` -- `AI`, `PatrolPath`

**`src/systems/`** -- System functions that process entities:
- `movement.py` -- Processes entity movement and collision
- `combat.py` -- Handles damage calculation and death
- `ai.py` -- Runs enemy AI behavior

**`src/factories/`** -- Entity creation functions:
- `actors.py` -- Functions to spawn the player, enemies, and NPCs
- `items.py` -- Functions to spawn items, potions, and equipment

**`src/procgen.py`** -- Procedural map generation algorithms.

**`src/color.py`** -- Named color constants used throughout the game.

**`src/input_handlers.py`** -- Input processing and event dispatch.

**`src/render_functions.py`** -- Rendering functions for the UI, HUD, and map.

**`saves/`** -- Directory for serialized game saves.

**`pyproject.toml`** -- Project metadata and dependency configuration.

**`README.md`** -- Project description and basic instructions.

To create this structure, run:

```bash
# Windows (PowerShell)
New-Item -ItemType Directory -Force -Path "src\components", "src\systems", "src\factories", "saves"

# macOS / Linux
mkdir -p src/components src/systems src/factories saves
```

Then create the `__init__.py` files:

```bash
# Windows
"" | Out-File -FilePath "src\__init__.py" -Encoding utf8
"" | Out-File -FilePath "src\components\__init__.py" -Encoding utf8
"" | Out-File -FilePath "src\systems\__init__.py" -Encoding utf8
"" | Out-File -FilePath "src\factories\__init__.py" -Encoding utf8

# macOS / Linux
touch src/__init__.py src/components/__init__.py src/systems/__init__.py src/factories/__init__.py
```

## pyproject.toml

The `pyproject.toml` file is the single source of truth for project metadata, dependencies, and tool configuration. Replace the default content with this:

```toml
[project]
name = "roguelike"
version = "0.1.0"
description = "A roguelike game built with tcod and ECS"
readme = "README.md"
requires-python = ">=3.12"
dependencies = [
    "tcod>=13.0",
    "tcod-ecs>=1.0",
    "numpy>=1.26",
    "attrs>=23.0",
]

[project.scripts]
roguelike = "src.main:main"

[tool.uv]
dev-dependencies = []

[tool.ruff]
line-length = 100

[tool.ruff.lint]
select = ["E", "F", "I", "UP"]

[tool.mypy]
python_version = "3.12"
strict = true
```

Key points:

- `requires-python = ">=3.12"` ensures the correct Python version.
- The `dependencies` list pins minimum versions for each library.
- The `[tool.ruff]` section configures the linter. ruff is a fast Python linter that we will use for code quality.
- The `[tool.mypy]` section configures the type checker. Strict mode catches more bugs.

If you are using uv, run `uv sync` after creating this file to install dependencies and generate the lock file. If you are using pip, run `pip install -r requirements.txt` after generating the requirements file.

## Your First Run

Let us create a minimal `main.py` that opens a tcod window. This verifies that your environment is set up correctly before we build anything complex.

Create `src/main.py` with the following content:

```python
import tcod
import tcod.console
import tcod.context
import tcod.tileset

def main() -> None:
    tileset = tcod.tileset.load_tilesheet(
        path="dejavu10x10_gs_tc.png",
        columns=32,
        rows=8,
        charmap=tcod.tileset.CHARMAP_TCOD,
    )

    with tcod.context.new(
        columns=80,
        height=24,
        tileset=tileset,
        title="Roguelike",
    ) as context:
        console = tcod.console.Console(80, 24, order="F")
        console.print(x=0, y=0, string="Hello, Roguelike!")

        while True:
            console.clear()
            console.print(x=0, y=0, string="Hello, Roguelike!")
            context.present(console)

            for event in tcod.event.wait():
                if isinstance(event, tcod.event.Quit):
                    return

if __name__ == "__main__":
    main()
```

You also need a tileset image. The standard choice is `dejavu10x10_gs_tc.png`, which is available in the tcod package or from the libtcod resources. Download it from the tcod repository or use:

```bash
# With uv
uv run python -c "import tcod; import shutil; shutil.copy(tcod.__path__[0] + '/terminal.png', 'dejavu10x10_gs_tc.png')"
```

Alternatively, you can use tcod's built-in font loading:

```python
import importlib.resources

font_path = importlib.resources.files("tcod") / "terminal.png"
tileset = tcod.tileset.load_tilesheet(
    path=str(font_path),
    columns=32,
    rows=8,
    charmap=tcod.tileset.CHARMAP_TCOD,
)
```

Run the game:

```bash
# With uv
uv run python src/main.py

# With pip/venv activated
python src/main.py
```

A window should appear displaying "Hello, Roguelike!" on a dark background. Press the window close button or Alt+F4 to exit.

If you see an error about the tileset image not being found, ensure the image file is in the same directory where you are running the command, or use the `importlib.resources` approach shown above.

## IDE Setup

**VS Code (recommended):**

Install the following extensions:

- **Python** (ms-python.python) -- Provides IntelliSense, debugging, and virtual environment detection.
- **Pylance** (ms-python.vscode-pylance) -- Fast type checking and code navigation.
- **Ruff** (charliermarsh.ruff) -- Linting and formatting integration.

Open the `roguelike` folder as a workspace in VS Code. It should automatically detect the virtual environment. If not, press Ctrl+Shift+P, search for "Python: Select Interpreter," and choose the one inside `.venv`.

Create a `.vscode/settings.json` to configure consistent behavior for the project:

```json
{
    "python.analysis.typeCheckingMode": "strict",
    "python.analysis.autoImportCompletions": true,
    "editor.formatOnSave": true,
    "[python]": {
        "editor.defaultFormatter": "charliermarsh.ruff",
        "editor.codeActionsOnSave": {
            "source.fixAll.ruff": "explicit",
            "source.organizeImports.ruff": "explicit"
        }
    }
}
```

**Other editors:**

Any editor with Python LSP support works. The key is that your editor can:
- Detect the virtual environment and use the correct Python interpreter.
- Run the type checker (mypy) and linter (ruff).
- Provide code navigation and autocomplete for tcod and numpy.

## Version Control

Initialize a git repository and create a `.gitignore` file tailored for Python projects:

```bash
git init
```

Create `.gitignore` with the following content:

```gitignore
# Python
__pycache__/
*.py[cod]
*$py.class
*.so

# Virtual environment
.venv/
venv/
ENV/

# Distribution
dist/
build/
*.egg-info/
*.egg

# IDE
.vscode/
.idea/
*.swp
*.swo
*~

# OS
.DS_Store
Thumbs.db

# Project specific
saves/*.pkl
*.png
!dejavu10x10_gs_tc.png

# uv
.python-version
uv.lock
```

Make your first commit:

```bash
git add .
git commit -m "Initial project structure"
```

Do not commit the `saves/` directory contents. Game saves are local state that should not be tracked in version control. The `.gitignore` pattern `saves/*.pkl` ensures pickle files are excluded.

Consider also adding `dejavu10x10_gs_tc.png` to the repository or using the `importlib.resources` approach so that collaborators do not need to source the font file separately.

## Exercises

**Exercise 1: Set Up the Project**

Follow the steps in this chapter to create the project structure, install dependencies, and verify the Hello World window opens. If you encounter errors, check:

- Is the correct Python version installed? Run `python --version`.
- Is the virtual environment activated? You should see `(roguelike)` in your prompt.
- Are the dependencies installed? Run `python -c "import tcod; print(tcod.__version__)"`.

**Exercise 2: Modify the Window**

Change the window dimensions from 80x24 to 120x40. Change the message from "Hello, Roguelike!" to "Welcome to the Dungeon." Verify the changes appear when you run the game.

**Exercise 3: Add a Color**

Modify the print call to display text in a color other than the default white. Consult the tcod documentation for the `console.print` method to find the `fg` parameter. Try displaying the text in green `(0, 255, 0)` or a custom color `(100, 150, 200)`.

These exercises confirm that your development environment is fully functional. In the next chapter, we will begin building the actual game.

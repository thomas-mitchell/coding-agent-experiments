# Chapter 23: Save and Load

A roguelike without save and load forces players to complete the game in one sitting. While permadeath is a genre staple, the ability to save progress and resume later makes the game accessible to more players. We implement a save system using Python's pickle module, leveraging the fact that tcod-ecs Registries are pickleable.

## Why Save and Load?

Roguelike sessions can last hours. Players need to:
- Pause and resume later
- Experiment with different strategies (save scumming, if desired)
- Protect against crashes and power failures
- Share save files with friends

## Serialization with Pickle

The tcod-ecs `Registry` can be serialized with Python's built-in `pickle` module:

```python
import pickle

# Save
data = pickle.dumps(registry)
with open("save.dat", "wb") as f:
    f.write(data)

# Load
with open("save.dat", "rb") as f:
    data = f.read()
registry = pickle.loads(data)
```

This works because all our components (attrs classes, enums, numpy arrays) are pickleable.

## Version Compatibility

Save files from older versions may not load correctly. We add a version tag:

```python
SAVE_VERSION = 2

def save_game(registry: tcod.ecs.Registry, filepath: str) -> None:
    """Save the game state to a file."""
    save_data = {
        "version": SAVE_VERSION,
        "registry": registry,
    }
    with open(filepath, "wb") as f:
        pickle.dump(save_data, f)


def load_game(filepath: str) -> tcod.ecs.Registry | None:
    """Load the game state from a file. Returns None if loading fails."""
    try:
        with open(filepath, "rb") as f:
            save_data = pickle.load(f)
        
        if save_data.get("version") != SAVE_VERSION:
            print(f"Warning: Save file is from version {save_data['version']}, expected {SAVE_VERSION}")
            # Could implement migration here
            return None
        
        return save_data["registry"]
    except (FileNotFoundError, pickle.UnpicklingError, EOFError) as e:
        print(f"Failed to load save: {e}")
        return None
```

## Save Slots

We support multiple save slots so players can maintain several runs:

```python
import os

SAVE_DIR = "saves"
SAVE_SLOTS = [
    os.path.join(SAVE_DIR, "save_slot_1.dat"),
    os.path.join(SAVE_DIR, "save_slot_2.dat"),
    os.path.join(SAVE_DIR, "save_slot_3.dat"),
]


def ensure_save_dir() -> None:
    """Create the save directory if it doesn't exist."""
    os.makedirs(SAVE_DIR, exist_ok=True)


def get_save_info(filepath: str) -> dict | None:
    """Get metadata about a save file without fully loading it."""
    try:
        with open(filepath, "rb") as f:
            save_data = pickle.load(f)
        registry = save_data["registry"]
        
        # Extract key info for display
        player = None
        for entity in registry.Q.all_of(tags=["player"]):
            player = entity
            break
        
        if player is None:
            return None
        
        fighter = player.components.get(Fighter)
        xp = player.components.get(XP)
        
        return {
            "hp": f"{fighter.hp}/{fighter.max_hp}" if fighter else "?",
            "level": xp.level if xp else 1,
            "floor": 1,  # Could store on registry[None]
            "exists": True,
        }
    except Exception:
        return None
```

## Auto-Save

We auto-save on key events like descending stairs:

```python
def auto_save(registry: tcod.ecs.Registry, slot_index: int = 0) -> None:
    """Auto-save the current game."""
    ensure_save_dir()
    save_game(registry, SAVE_SLOTS[slot_index])
```

## The Main Menu

The main menu allows players to start a new game, continue the last save, or load a specific slot:

```
┌─────────────────────────────────┐
│      DUNGEON CRAWLER            │
│                                 │
│  1. New Game                    │
│  2. Continue                    │
│  3. Load Game                   │
│  4. Quit                        │
│                                 │
│  Slot 1: Level 5, HP 20/30     │
│  Slot 2: Level 3, HP 15/25     │
│  Slot 3: (empty)                │
└─────────────────────────────────┘
```

## Loading a Game

Loading restores the entire game state:

```python
def start_loaded_game(filepath: str) -> tcod.ecs.Registry | None:
    """Load and validate a saved game."""
    registry = load_game(filepath)
    if registry is None:
        return None
    
    # Verify critical entities exist
    player_exists = any(True for _ in registry.Q.all_of(tags=["player"]))
    if not player_exists:
        print("Save file is corrupted: no player entity found.")
        return None
    
    return registry
```

## Exercises

- Implement save file compression with gzip
- Add cloud save support using a simple HTTP API
- Create a save file viewer that displays run statistics
- Implement automatic save rotation (keep last 3 auto-saves)
- Add save file encryption to prevent tampering

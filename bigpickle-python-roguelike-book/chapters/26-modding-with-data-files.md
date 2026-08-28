# Chapter 26: Modding with Data Files

A moddable game lives longer. By defining entities, items, and enemies in external data files instead of hardcoded Python, players and designers can create new content without modifying source code. This chapter covers data-driven design using YAML and JSON.

## Why Data-Driven Design?

Data-driven design separates *content* from *logic*:

- **Content** (what exists): YAML/JSON files defining entity stats, item effects, enemy behaviors
- **Logic** (how it works): Python code that processes data

Benefits:
- Non-programmers can create content
- Hot-reload during development
- Community modding support
- Easier balancing and testing

## YAML Entity Definitions

Define entities in YAML files:

```yaml
# data/entities/enemies.yaml
enemies:
  kobold:
    char: "k"
    fg: [0, 127, 0]
    name: "Kobold"
    fighter:
      hp: 8
      max_hp: 8
      power: 3
      defense: 0
    ai: "hostile"
    xp_value: 10
    tags: ["enemy", "blocks_movement"]

  orc:
    char: "o"
    fg: [63, 127, 63]
    name: "Orc"
    fighter:
      hp: 15
      max_hp: 15
      power: 5
      defense: 2
    ai: "hostile"
    xp_value: 25
    tags: ["enemy", "blocks_movement"]
```

## JSON Item Definitions

```json
{
  "items": {
    "health_potion": {
      "char": "!",
      "fg": [127, 0, 255],
      "name": "Health Potion",
      "description": "Restores 10 HP",
      "consumable": {
        "use_function": "heal",
        "heal_amount": 10
      },
      "tags": ["item"]
    }
  }
}
```

## The Data Loader

```python
import yaml
from pathlib import Path

class DataLoader:
    def __init__(self, data_dir: str = "data"):
        self.data_dir = Path(data_dir)
    
    def load_enemies(self) -> dict:
        """Load all enemy definitions."""
        filepath = self.data_dir / "entities" / "enemies.yaml"
        with open(filepath) as f:
            return yaml.safe_load(f)
    
    def load_items(self) -> dict:
        """Load all item definitions."""
        filepath = self.data_dir / "entities" / "items.json"
        with open(filepath) as f:
            import json
            return json.load(f)
```

## Spawning from Data

```python
def spawn_from_template(registry, template: dict, x: int, y: int) -> tcod.ecs.Entity:
    """Create an entity from a data template."""
    entity = registry.new_entity()
    entity.components[Position] = Position(x=x, y=y)
    entity.components[Renderable] = Renderable(
        char=template["char"],
        fg=tuple(template["fg"]),
    )
    entity.components[Name] = Name(name=template["name"])
    
    if "fighter" in template:
        f = template["fighter"]
        entity.components[Fighter] = Fighter(
            hp=f["hp"], max_hp=f["max_hp"],
            power=f["power"], defense=f["defense"],
        )
    
    for tag in template.get("tags", []):
        entity.tags.add(tag)
    
    return entity
```

## Mod Structure

A mod is a directory of YAML/JSON files:

```
mods/
  my_mod/
    mod.yaml          # Mod metadata
    entities/
      enemies.yaml    # New enemy types
      items.yaml      # New item types
    data/
      loot_tables.yaml
```

## Loading Mods

```python
def load_mods(registry, mods_dir: str = "mods"):
    """Load all mods from the mods directory."""
    mods_path = Path(mods_dir)
    if not mods_path.exists():
        return
    
    for mod_dir in mods_path.iterdir():
        if mod_dir.is_dir():
            load_single_mod(registry, mod_dir)
```

## Exercises

- Create a mod that adds a new enemy type (Dragon with fire breath)
- Add item crafting recipes defined in YAML
- Create a mod that changes all tile colors to a different palette
- Add hot-reload support (watch files for changes)

"""Factory functions for creating items (equippable and consumable)."""
from __future__ import annotations

import random
from typing import TYPE_CHECKING

from components import (
    Consumable,
    Description,
    Equippable,
    Item,
    Name,
    Position,
    Renderable,
)

if TYPE_CHECKING:
    import tcod.ecs
    from game_map import GameMap


def create_sword(registry: tcod.ecs.Registry, x: int, y: int) -> tcod.ecs.Entity:
    """Spawn a basic sword (weapon slot, +power)."""
    name = "Iron Sword"
    desc = "A sturdy iron blade. (+2 power)"
    entity = registry.new_entity()
    entity.components |= {
        Position: Position(x=x, y=y),
        Renderable: Renderable(char="!", fg=(210, 210, 210)),
        Name: Name(name=name),
        Description: Description(text=desc),
        Item: Item(name=name, description=desc),
        Equippable: Equippable(power_bonus=2, defense_bonus=0, slot="weapon"),
    }
    entity.tags.add("item")
    entity.tags.add("equippable")
    return entity


def create_leather_armor(registry: tcod.ecs.Registry, x: int, y: int) -> tcod.ecs.Entity:
    """Spawn leather armor (armor slot, +defense)."""
    name = "Leather Armor"
    desc = "Sturdy boiled leather. (+1 defense)"
    entity = registry.new_entity()
    entity.components |= {
        Position: Position(x=x, y=y),
        Renderable: Renderable(char="[", fg=(160, 120, 60)),
        Name: Name(name=name),
        Description: Description(text=desc),
        Item: Item(name=name, description=desc),
        Equippable: Equippable(power_bonus=0, defense_bonus=1, slot="armor"),
    }
    entity.tags.add("item")
    entity.tags.add("equippable")
    return entity


def create_confusion_scroll(registry: tcod.ecs.Registry, x: int, y: int) -> tcod.ecs.Entity:
    """Spawn a consumable confusion scroll."""
    name = "Confusion Scroll"
    desc = "A scroll of confusion. Reading it confuses the nearest monster, "
    "making it wander aimlessly for a short while."
    entity = registry.new_entity()
    entity.components |= {
        Position: Position(x=x, y=y),
        Renderable: Renderable(char="?", fg=(200, 120, 255)),
        Name: Name(name=name),
        Description: Description(text=desc),
        Item: Item(name=name, description=desc),
        Consumable: Consumable(use_function="confusion"),
    }
    entity.tags.add("item")
    entity.tags.add("consumable")
    return entity


def _make_item(registry: tcod.ecs.Registry, x: int, y: int) -> None:
    """Randomly create one item type (equippable or consumable)."""
    roll = random.random()
    if roll < 0.35:
        create_sword(registry, x, y)
    elif roll < 0.65:
        create_leather_armor(registry, x, y)
    else:
        create_confusion_scroll(registry, x, y)


def place_items(
    registry: tcod.ecs.Registry,
    dungeon: GameMap,
    skip_room: int = 0,
) -> None:
    """Scatter equipment (and the odd scroll) through the dungeon."""
    for i, room in enumerate(dungeon.rooms):
        if i == skip_room:
            continue
        if random.random() < 0.7:
            x = random.randint(room.x + 1, room.x + room.w - 2)
            y = random.randint(room.y + 1, room.y + room.h - 2)
            occupied = any(
                entity.components[Position].x == x
                and entity.components[Position].y == y
                for entity in registry.Q.all_of(components=[Position])
            )
            if not occupied:
                _make_item(registry, x, y)

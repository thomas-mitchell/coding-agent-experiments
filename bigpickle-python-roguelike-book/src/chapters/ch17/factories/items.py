"""Factory functions for creating and placing items."""
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
)

if TYPE_CHECKING:
    import tcod.ecs
    from game_map import GameMap


def create_health_potion(registry: "tcod.ecs.Registry", x: int, y: int) -> "tcod.ecs.Entity":
    """Spawn a health potion at the given tile."""
    entity = registry.new_entity()
    entity.components |= {
        Position: Position(x=x, y=y),
        Name: Name(name="Health Potion"),
        Description: Description(text="A bubbling red potion that restores 6 HP."),
        Item: Item(name="Health Potion", description="Restores 6 HP."),
        Consumable: Consumable(heal_amount=6, use_function="heal"),
    }
    entity.tags.add("item")
    return entity


def create_confusion_scroll(registry: "tcod.ecs.Registry", x: int, y: int) -> "tcod.ecs.Entity":
    """Spawn a confusion scroll at the given tile."""
    entity = registry.new_entity()
    entity.components |= {
        Position: Position(x=x, y=y),
        Name: Name(name="Confusion Scroll"),
        Description: Description(
            text="Reading it confuses the nearest monster, making it wander aimlessly."
        ),
        Item: Item(
            name="Confusion Scroll",
            description="Confuses the nearest monster in view.",
        ),
        Consumable: Consumable(use_function="confusion"),
    }
    entity.tags.add("item")
    return entity


def create_fireball_scroll(registry: "tcod.ecs.Registry", x: int, y: int) -> "tcod.ecs.Entity":
    """Spawn a fireball scroll at the given tile."""
    entity = registry.new_entity()
    entity.components |= {
        Position: Position(x=x, y=y),
        Name: Name(name="Fireball Scroll"),
        Description: Description(
            text="Unleashes a fiery blast damaging every enemy in a small radius."
        ),
        Item: Item(
            name="Fireball Scroll",
            description="Damages all enemies within a radius.",
        ),
        Consumable: Consumable(damage=6, radius=2, use_function="fireball"),
    }
    entity.tags.add("item")
    return entity


def create_dagger(registry: "tcod.ecs.Registry", x: int, y: int) -> "tcod.ecs.Entity":
    """Spawn a dagger weapon."""
    entity = registry.new_entity()
    entity.components |= {
        Position: Position(x=x, y=y),
        Name: Name(name="Dagger"),
        Description: Description(text="A small, sharp blade. +1 power."),
        Item: Item(name="Dagger", description="A weapon. +1 power."),
        Equippable: Equippable(power_bonus=1, slot="weapon"),
    }
    entity.tags.add("item")
    return entity


def create_sword(registry: "tcod.ecs.Registry", x: int, y: int) -> "tcod.ecs.Entity":
    """Spawn a sword weapon."""
    entity = registry.new_entity()
    entity.components |= {
        Position: Position(x=x, y=y),
        Name: Name(name="Sword"),
        Description: Description(text="A fine steel blade. +3 power."),
        Item: Item(name="Sword", description="A weapon. +3 power."),
        Equippable: Equippable(power_bonus=3, slot="weapon"),
    }
    entity.tags.add("item")
    return entity


def create_leather_armor(registry: "tcod.ecs.Registry", x: int, y: int) -> "tcod.ecs.Entity":
    """Spawn a leather armor body piece."""
    entity = registry.new_entity()
    entity.components |= {
        Position: Position(x=x, y=y),
        Name: Name(name="Leather Armor"),
        Description: Description(text="Sturdy leather. +1 defense."),
        Item: Item(name="Leather Armor", description="Armor. +1 defense."),
        Equippable: Equippable(defense_bonus=1, slot="armor"),
    }
    entity.tags.add("item")
    return entity


# Weights give potions/scrolls a high chance and make equipment more rare.
_ITEM_CREATORS = [
    (create_health_potion, 5),
    (create_confusion_scroll, 3),
    (create_fireball_scroll, 2),
    (create_dagger, 2),
    (create_sword, 1),
    (create_leather_armor, 1),
]


def _weighted_creator():
    total = sum(w for _, w in _ITEM_CREATORS)
    roll = random.randint(1, total)
    for creator, weight in _ITEM_CREATORS:
        if roll <= weight:
            return creator
        roll -= weight
    return create_health_potion


def place_items(
    registry: "tcod.ecs.Registry",
    dungeon: "GameMap",
    skip_room: int = 0,
) -> None:
    """Scatter a random selection of items through the dungeon."""
    for i, room in enumerate(dungeon.rooms):
        if i == skip_room:
            continue
        if random.random() < 0.6:
            x = random.randint(room.x + 1, room.x + room.w - 2)
            y = random.randint(room.y + 1, room.y + room.h - 2)
            occupied = any(
                entity.components[Position].x == x
                and entity.components[Position].y == y
                for entity in registry.Q.all_of(components=[Position])
            )
            if not occupied:
                creator = _weighted_creator()
                creator(registry, x, y)

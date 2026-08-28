"""Factory functions for creating items."""
from __future__ import annotations

import random
from typing import TYPE_CHECKING

from components import (
    Consumable,
    ConsumableEffect,
    Description,
    Item,
    Name,
    Position,
    Renderable,
)

if TYPE_CHECKING:
    import tcod.ecs
    from game_map import GameMap


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


def _is_occupied(registry: tcod.ecs.Registry, x: int, y: int) -> bool:
    for entity in registry.Q.all_of(components=[Position]):
        pos = entity.components[Position]
        if pos.x == x and pos.y == y:
            return True
    return False

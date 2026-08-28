"""Factory functions for creating items."""
from __future__ import annotations

import random
from typing import TYPE_CHECKING

from components import Description, Item, Name, Position, Renderable

if TYPE_CHECKING:
    import tcod.ecs
    from game_map import GameMap

CONFUSION_SCROLL = (
    "?", (200, 120, 255), "Confusion Scroll",
    "A scroll of confusion. Reading it confuses the nearest monster, "
    "making it wander aimlessly for a short while.",
)


def create_confusion_scroll(registry: tcod.ecs.Registry, x: int, y: int) -> tcod.ecs.Entity:
    """Spawn a confusion scroll item at the given tile."""
    char, fg, name, desc = CONFUSION_SCROLL
    entity = registry.new_entity()
    entity.components |= {
        Position: Position(x=x, y=y),
        Renderable: Renderable(char=char, fg=fg),
        Name: Name(name=name),
        Description: Description(text=desc),
        Item: Item(name=name, description=desc),
    }
    entity.tags.add("item")
    return entity


def place_items(
    registry: tcod.ecs.Registry,
    dungeon: GameMap,
    skip_room: int = 0,
) -> None:
    """Scatter a few confusion scrolls through the dungeon."""
    for i, room in enumerate(dungeon.rooms):
        if i == skip_room:
            continue
        if random.random() < 0.5:
            x = random.randint(room.x + 1, room.x + room.w - 2)
            y = random.randint(room.y + 1, room.y + room.h - 2)
            occupied = any(
                entity.components[Position].x == x
                and entity.components[Position].y == y
                for entity in registry.Q.all_of(components=[Position])
            )
            if not occupied:
                create_confusion_scroll(registry, x, y)

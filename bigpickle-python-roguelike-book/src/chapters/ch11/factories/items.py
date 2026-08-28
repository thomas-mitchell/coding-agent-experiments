"""Item entity factories."""
from __future__ import annotations
from typing import TYPE_CHECKING
from components import Position, Renderable, Name, Item, Inventory

if TYPE_CHECKING:
    import tcod.ecs


def create_health_potion(registry: tcod.ecs.Registry, x: int, y: int) -> tcod.ecs.Entity:
    entity = registry.new_entity()
    entity.components |= {
        Position: Position(x=x, y=y),
        Renderable: Renderable(char="!", fg=(127, 0, 255)),
        Name: Name(name="Health Potion"),
        Item: Item(name="Health Potion", description="Restores 10 HP"),
    }
    entity.tags.add("item")
    return entity


def create_scroll_fireball(registry: tcod.ecs.Registry, x: int, y: int) -> tcod.ecs.Entity:
    entity = registry.new_entity()
    entity.components |= {
        Position: Position(x=x, y=y),
        Renderable: Renderable(char="?", fg=(255, 127, 0)),
        Name: Name(name="Scroll of Fireball"),
        Item: Item(name="Scroll of Fireball", description="Deals 12 damage to all adjacent enemies"),
    }
    entity.tags.add("item")
    return entity


def create_scroll_lightning(registry: tcod.ecs.Registry, x: int, y: int) -> tcod.ecs.Entity:
    entity = registry.new_entity()
    entity.components |= {
        Position: Position(x=x, y=y),
        Renderable: Renderable(char="?", fg=(255, 255, 0)),
        Name: Name(name="Scroll of Lightning"),
        Item: Item(name="Scroll of Lightning", description="Deals 20 damage to the nearest enemy"),
    }
    entity.tags.add("item")
    return entity


def create_sword(registry: tcod.ecs.Registry, x: int, y: int) -> tcod.ecs.Entity:
    entity = registry.new_entity()
    entity.components |= {
        Position: Position(x=x, y=y),
        Renderable: Renderable(char="/", fg=(191, 191, 191)),
        Name: Name(name="Sword"),
        Item: Item(name="Sword", description="A sharp blade (+2 power)"),
    }
    entity.tags.add("item")
    entity.tags.add("equipment")
    return entity


def create_shield(registry: tcod.ecs.Registry, x: int, y: int) -> tcod.ecs.Entity:
    entity = registry.new_entity()
    entity.components |= {
        Position: Position(x=x, y=y),
        Renderable: Renderable(char="(", fg=(127, 127, 191)),
        Name: Name(name="Shield"),
        Item: Item(name="Shield", description="A sturdy shield (+2 defense)"),
    }
    entity.tags.add("item")
    entity.tags.add("equipment")
    return entity

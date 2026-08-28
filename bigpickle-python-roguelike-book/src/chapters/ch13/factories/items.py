"""Item entity factories."""
from __future__ import annotations
from typing import TYPE_CHECKING
from components import Position, Renderable, Name, Item, Consumable

if TYPE_CHECKING:
    import tcod.ecs


def create_health_potion(registry: tcod.ecs.Registry, x: int, y: int) -> tcod.ecs.Entity:
    entity = registry.new_entity()
    entity.components |= {
        Position: Position(x=x, y=y),
        Renderable: Renderable(char="!", fg=(127, 0, 255)),
        Name: Name(name="Health Potion"),
        Item: Item(name="Health Potion", description="Restores 10 HP"),
        Consumable: Consumable(heal_amount=10),
    }
    entity.tags.add("item")
    return entity

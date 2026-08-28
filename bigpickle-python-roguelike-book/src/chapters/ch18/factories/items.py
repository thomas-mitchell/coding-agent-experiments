from __future__ import annotations

from typing import TYPE_CHECKING

from .components import Consumable, Description, Equippable, Item, Name, Position, Renderable
from . import color

if TYPE_CHECKING:
    from tcod.ecs import World


def create_health_potion(world: World, x: int, y: int) -> int:
    entity = world.create_entity(
        Position(x=x, y=y),
        Renderable(char="!", color=color.potion_color, render_order=0),
        Name(name="Health Potion"),
        Description(text="A swirling red potion that restores 4 HP when consumed."),
        Item(),
        Consumable(healing_amount=4),
    )
    return entity


def create_lightning_scroll(world: World, x: int, y: int) -> int:
    entity = world.create_entity(
        Position(x=x, y=y),
        Renderable(char="~", color=color.lightning_color, render_order=0),
        Name(name="Lightning Scroll"),
        Description(text="A scroll crackling with electricity. Deals 20 damage to the nearest enemy."),
        Item(),
        Consumable(damage_amount=20, max_range=5),
    )
    return entity


def create_fireball_scroll(world: World, x: int, y: int) -> int:
    entity = world.create_entity(
        Position(x=x, y=y),
        Renderable(char="~", color=color.fireball_color, render_order=0),
        Name(name="Fireball Scroll"),
        Description(text="A scroll smelling of sulfur. Launches a fireball dealing 12 damage in a radius."),
        Item(),
        Consumable(damage_amount=12, radius=3),
    )
    return entity


def create_confusion_scroll(world: World, x: int, y: int) -> int:
    entity = world.create_entity(
        Position(x=x, y=y),
        Renderable(char="~", color=color.confusion_color, render_order=0),
        Name(name="Confusion Scroll"),
        Description(text="A scroll with strange, swirling symbols."),
        Item(),
        Consumable(is_confusion=True),
    )
    return entity


def create_sword(world: World, x: int, y: int) -> int:
    entity = world.create_entity(
        Position(x=x, y=y),
        Renderable(char="/", color=color.sword_color, render_order=0),
        Name(name="Sword"),
        Description(text="A sharp steel sword. Grants +2 power."),
        Item(),
        Equippable(power_bonus=2),
    )
    return entity


def create_shield(world: World, x: int, y: int) -> int:
    entity = world.create_entity(
        Position(x=x, y=y),
        Renderable(char="[", color=color.shield_color, render_order=0),
        Name(name="Shield"),
        Description(text="A sturdy wooden shield. Grants +1 defense."),
        Item(),
        Equippable(defense_bonus=1),
    )
    return entity

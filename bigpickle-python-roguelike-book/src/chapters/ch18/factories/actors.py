from __future__ import annotations

import random
from typing import TYPE_CHECKING

from .components import AI, AIKind, Consumable, Equippable, Equipment, Fighter, Inventory, Item, Name, Position, Renderable, XP
from . import color

if TYPE_CHECKING:
    from tcod.ecs import World


def create_orc(world: World, x: int, y: int) -> int:
    entity = world.create_entity(
        Position(x=x, y=y),
        Renderable(char="o", color=color.orc_color, render_order=2),
        Name(name="Orc"),
        Description(text="A snarling orc."),
        AI(kind=AIKind.HOSTILE),
        Fighter(hp=10, max_hp=10, defense=0, power=3),
        XP(level=1),
    )
    return entity


def create_troll(world: World, x: int, y: int) -> int:
    entity = world.create_entity(
        Position(x=x, y=y),
        Renderable(char="T", color=color.troll_color, render_order=2),
        Name(name="Troll"),
        Description(text="A massive, foul-smelling troll."),
        AI(kind=AIKind.HOSTILE),
        Fighter(hp=16, max_hp=16, defense=1, power=4),
        XP(level=2),
    )
    return entity


def create_player(world: World, x: int, y: int) -> int:
    player = world.create_entity(
        Position(x=x, y=y),
        Renderable(char="@", color=color.player_color, render_order=2),
        Name(name="Player"),
        Description(text="You, the brave adventurer."),
        Fighter(hp=30, max_hp=30, defense=2, power=5),
        XP(level=1),
        Equipment(),
        Inventory(capacity=20),
    )
    return player

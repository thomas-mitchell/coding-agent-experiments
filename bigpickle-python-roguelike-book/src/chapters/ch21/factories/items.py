"""Factory functions for creating and placing items, scaled by depth."""
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
    TargetingMode,
)

if TYPE_CHECKING:
    import tcod.ecs
    from game_map import GameMap


def create_health_potion(
    registry: "tcod.ecs.Registry",
    x: int,
    y: int,
    dungeon_level: int = 1,
) -> "tcod.ecs.Entity":
    """Spawn a health potion at the given tile."""
    amount = 6 + (dungeon_level - 1) * 2
    entity = registry.new_entity()
    entity.components |= {
        Position: Position(x=x, y=y),
        Name: Name(name="Health Potion"),
        Description: Description(text=f"A bubbling red potion that restores {amount} HP."),
        Item: Item(name="Health Potion", description=f"Restores {amount} HP."),
        Consumable: Consumable(
            heal_amount=amount, use_function="heal", targeting_mode=TargetingMode.NONE
        ),
    }
    entity.tags.add("item")
    return entity


def create_confusion_scroll(
    registry: "tcod.ecs.Registry",
    x: int,
    y: int,
    dungeon_level: int = 1,
) -> "tcod.ecs.Entity":
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
        Consumable: Consumable(
            use_function="confusion", targeting_mode=TargetingMode.NONE
        ),
    }
    entity.tags.add("item")
    return entity


def create_fireball_scroll(
    registry: "tcod.ecs.Registry",
    x: int,
    y: int,
    dungeon_level: int = 1,
) -> "tcod.ecs.Entity":
    """Spawn a fireball scroll at the given tile.

    The fireball is a *targeted area spell*: it must be aimed with the
    targeting cursor before it is unleashed.
    """
    damage = 6 + (dungeon_level - 1) * 2
    radius = 2
    entity = registry.new_entity()
    entity.components |= {
        Position: Position(x=x, y=y),
        Name: Name(name="Fireball Scroll"),
        Description: Description(
            text="Aim it at a tile to unleash a fiery blast in every direction."
        ),
        Item: Item(
            name="Fireball Scroll",
            description=f"Targets a tile, damaging all enemies within {radius} tiles.",
        ),
        Consumable: Consumable(
            damage=damage,
            radius=radius,
            max_range=10,
            use_function="fireball",
            targeting_mode=TargetingMode.AREA,
        ),
    }
    entity.tags.add("item")
    return entity


def create_dagger(
    registry: "tcod.ecs.Registry",
    x: int,
    y: int,
    dungeon_level: int = 1,
) -> "tcod.ecs.Entity":
    """Spawn a dagger weapon, with a small bonus at depth for later floors."""
    bonus = 1 + (dungeon_level - 1) // 3
    entity = registry.new_entity()
    entity.components |= {
        Position: Position(x=x, y=y),
        Name: Name(name="Dagger"),
        Description: Description(text=f"A small, sharp blade. +{bonus} power."),
        Item: Item(name="Dagger", description=f"A weapon. +{bonus} power."),
        Equippable: Equippable(power_bonus=bonus, slot="weapon"),
    }
    entity.tags.add("item")
    return entity


def create_sword(
    registry: "tcod.ecs.Registry",
    x: int,
    y: int,
    dungeon_level: int = 1,
) -> "tcod.ecs.Entity":
    """Spawn a sword weapon, with a bonus that grows with depth."""
    bonus = 3 + (dungeon_level - 1) // 2
    entity = registry.new_entity()
    entity.components |= {
        Position: Position(x=x, y=y),
        Name: Name(name="Sword"),
        Description: Description(text=f"A fine steel blade. +{bonus} power."),
        Item: Item(name="Sword", description=f"A weapon. +{bonus} power."),
        Equippable: Equippable(power_bonus=bonus, slot="weapon"),
    }
    entity.tags.add("item")
    return entity


def create_leather_armor(
    registry: "tcod.ecs.Registry",
    x: int,
    y: int,
    dungeon_level: int = 1,
) -> "tcod.ecs.Entity":
    """Spawn a leather armor body piece, with a bonus that grows with depth."""
    bonus = 1 + (dungeon_level - 1) // 3
    entity = registry.new_entity()
    entity.components |= {
        Position: Position(x=x, y=y),
        Name: Name(name="Leather Armor"),
        Description: Description(text=f"Sturdy leather. +{bonus} defense."),
        Item: Item(name="Leather Armor", description=f"Armor. +{bonus} defense."),
        Equippable: Equippable(defense_bonus=bonus, slot="armor"),
    }
    entity.tags.add("item")
    return entity


# Items available at each dungeon level. Potions and scrolls are common,
# equipment is rarer and becomes more available deeper down.
ITEM_SPAWN_TABLE: dict[int, list[str]] = {
    1: ["health_potion", "health_potion", "confusion_scroll", "dagger"],
    2: ["health_potion", "confusion_scroll", "fireball_scroll", "dagger", "leather_armor"],
    3: ["health_potion", "fireball_scroll", "sword", "leather_armor"],
    4: ["health_potion", "health_potion", "fireball_scroll", "sword", "leather_armor"],
    5: ["health_potion", "fireball_scroll", "sword", "leather_armor", "leather_armor"],
}


def get_item_pool(dungeon_level: int) -> list[str]:
    """Return the item template names that can spawn on a given floor."""
    if dungeon_level in ITEM_SPAWN_TABLE:
        return list(ITEM_SPAWN_TABLE[dungeon_level])
    max_level = max(ITEM_SPAWN_TABLE.keys())
    return list(ITEM_SPAWN_TABLE[max_level])


_ITEM_CREATORS = {
    "health_potion": create_health_potion,
    "confusion_scroll": create_confusion_scroll,
    "fireball_scroll": create_fireball_scroll,
    "dagger": create_dagger,
    "sword": create_sword,
    "leather_armor": create_leather_armor,
}


def place_items(
    registry: "tcod.ecs.Registry",
    dungeon: "GameMap",
    dungeon_level: int = 1,
    skip_room: int = 0,
) -> None:
    """Scatter a random selection of items through the dungeon."""
    pool = get_item_pool(dungeon_level)

    for i, room in enumerate(dungeon.rooms):
        if i == skip_room:
            continue
        items_this_room = 1 if random.random() < 0.65 else 0
        if dungeon_level >= 3 and random.random() < 0.3:
            items_this_room += 1
        for _ in range(items_this_room):
            x = random.randint(room.x + 1, room.x + room.w - 2)
            y = random.randint(room.y + 1, room.y + room.h - 2)
            occupied = any(
                entity.components[Position].x == x
                and entity.components[Position].y == y
                for entity in registry.Q.all_of(components=[Position])
            )
            if not occupied:
                creator = _ITEM_CREATORS[random.choice(pool)]
                creator(registry, x, y, dungeon_level=dungeon_level)

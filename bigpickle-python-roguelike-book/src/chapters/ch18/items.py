from __future__ import annotations

from typing import TYPE_CHECKING

from .components import AI, AIKind, Consumable, Description, Equippable, Equipment, Fighter, Inventory, Item, Name, Position, Renderable
from .combat import attack, heal
from .game_map import GameMap

if TYPE_CHECKING:
    from tcod.ecs import World


def use_item(item_id: int, target_x: int | None, target_y: int | None, world: World, game_map: GameMap) -> list[str]:
    messages: list[str] = []
    consumable = world[item_id, "Consumable"]
    item_name = world[item_id, "Name"].name

    if consumable.healing_amount > 0:
        player = world["player"]
        result = heal(player, consumable.healing_amount, world)
        messages.append(result)
        world[player, "Inventory"].items.remove(item_id)
        world.destroy_entity(item_id)

    elif consumable.damage_amount > 0:
        if consumable.radius > 0:
            _cast_fireball(item_id, target_x, target_y, world, game_map, messages)
        else:
            _cast_lightning(item_id, world, game_map, messages)

    elif consumable.is_confusion:
        _cast_confusion(item_id, world, game_map, messages)

    return messages


def _cast_fireball(item_id: int, target_x: int | None, target_y: int, world: World, game_map: GameMap, messages: list[str]) -> None:
    consumable = world[item_id, "Consumable"]
    player = world["player"]
    player_pos = world[player, "Position"]

    if target_x is None or target_y is None:
        return

    if not game_map.fov[target_x, target_y]:
        messages.append("You cannot target a tile outside your field of view.")
        return

    messages.append(f"The fireball explodes, burning everything within {consumable.radius} tiles!")

    for entity, (pos, fighter) in world.Q.all_of(components=[Position, Fighter]):
        if entity == player:
            continue
        distance = max(abs(pos.x - target_x), abs(pos.y - target_y))
        if distance <= consumable.radius:
            messages.append(f"The {world[entity, 'Name'].name} is engulfed in a glob of fire! {consumable.damage_amount} damage!")
            fighter.hp -= consumable.damage_amount
            if fighter.hp <= 0:
                messages.append(f"The {world[entity, 'Name'].name} is killed!")
                _kill_entity(entity, world, game_map)

    world[player, "Inventory"].items.remove(item_id)
    world.destroy_entity(item_id)


def _cast_lightning(item_id: int, world: World, game_map: GameMap, messages: list[str]) -> None:
    consumable = world[item_id, "Consumable"]
    player = world["player"]
    player_pos = world[player, "Position"]

    closest_distance = consumable.max_range + 1.0
    target = None

    for entity, (pos, fighter) in world.Q.all_of(components=[Position, Fighter]):
        if entity == player:
            continue
        if fighter.hp <= 0:
            continue
        if not game_map.fov[pos.x, pos.y]:
            continue
        distance = ((pos.x - player_pos.x) ** 2 + (pos.y - player_pos.y) ** 2) ** 0.5
        if distance < closest_distance:
            closest_distance = distance
            target = entity

    if target is None:
        messages.append("No enemy is close enough to strike.")
        return

    target_name = world[target, "Name"].name
    target_fighter = world[target, "Fighter"]
    messages.append(f"A lightning bolt strikes the {target_name} with a loud crack! {consumable.damage_amount} damage!")
    target_fighter.hp -= consumable.damage_amount
    if target_fighter.hp <= 0:
        messages.append(f"The {target_name} is killed!")
        _kill_entity(target, world, game_map)

    world[player, "Inventory"].items.remove(item_id)
    world.destroy_entity(item_id)


def _cast_confusion(item_id: int, world: World, game_map: GameMap, messages: list[str]) -> None:
    player = world["player"]

    closest_distance = 5.0 + 1.0
    target = None

    for entity, (ai, pos, fighter) in world.Q.all_of(components=[AI, Position, Fighter]):
        if entity == player:
            continue
        if fighter.hp <= 0:
            continue
        if not game_map.fov[pos.x, pos.y]:
            continue
        player_pos = world[player, "Position"]
        distance = ((pos.x - player_pos.x) ** 2 + (pos.y - player_pos.y) ** 2) ** 0.5
        if distance < closest_distance:
            closest_distance = distance
            target = entity

    if target is None:
        messages.append("There are no enemies nearby to confuse.")
        return

    ai = world[target, "AI"]
    ai.kind = AIKind.CONFUSED
    ai.path = []
    target_name = world[target, "Name"].name
    messages.append(f"The eyes of the {target_name} look vacant, as it starts to stumble around!")

    world[player, "Inventory"].items.remove(item_id)
    world.destroy_entity(item_id)


def _kill_entity(entity: int, world: World, game_map: GameMap) -> None:
    name = world[entity, "Name"]
    char = world[entity, "Renderable"]
    pos = world[entity, "Position"]

    name.name = f"remains of {name.name}"
    char.char = "%"
    char.color = (128, 0, 0)
    char.render_order = 1

    for component_name in list(world[entity].components.keys()):
        if component_name in ("AI",):
            del world[entity, component_name]

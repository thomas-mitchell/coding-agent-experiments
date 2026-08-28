from __future__ import annotations

from typing import TYPE_CHECKING

import numpy as np
import tcod
import tcod.console
import tcod.context
import tcod.ecs
import tcod.event
import tcod.tileset

from . import color as colors
from .actions import (
    CancelAction,
    DropItemAction,
    EquipAction,
    ExitAction,
    LevelUpAction,
    LookAction,
    LogAction,
    MoveAction,
    PickupAction,
    UseAction,
    WaitAction,
)
from .combat import attack, heal
from .components import (
    Consumable,
    Description,
    Equippable,
    Equipment,
    Fighter,
    Inventory,
    Name,
    Position,
    Renderable,
    XP,
)
from .equipment import equip, unequip
from .factories.actors import create_player
from .game_map import GameMap
from .input_handlers import InputHandler, MenuState
from .items import use_item
from .procgen import generate_dungeon
from .render_functions import render_all

if TYPE_CHECKING:
    pass

SCREEN_WIDTH = 100
SCREEN_HEIGHT = 50
MAP_WIDTH = 80
MAP_HEIGHT = 45
BAR_WIDTH = 20
PANEL_HEIGHT = 7
MESSAGE_X = BAR_WIDTH + 2
MESSAGE_WIDTH = SCREEN_WIDTH - BAR_WIDTH - 2
MSG_HEIGHT = PANEL_HEIGHT - 1


def main() -> None:
    world = tcod.ecs.GameWorld()

    world["message_log"] = tcod.ecs.Entity(world=world)

    tileset = tcod.tileset.load_tilesheet(
        "data/fonts/dejavu10x10_gs_tc.png",
        32,
        8,
        tcod.tileset.CHARMAP_TCOD,
    )

    context = tcod.context.new(
        columns=SCREEN_WIDTH,
        rows=SCREEN_HEIGHT,
        tileset=tileset,
        title="Roguelike - Chapter 18",
    )
    console = tcod.console.Console(SCREEN_WIDTH, SCREEN_HEIGHT, order="F")

    player = create_player(world, 0, 0)
    world["player"] = player

    game_map = generate_dungeon(
        world=world,
        max_rooms=30,
        room_min_size=6,
        room_max_size=10,
        map_width=MAP_WIDTH,
        map_height=MAP_HEIGHT,
        max_monsters_per_room=3,
        max_items_per_room=2,
        floor=1,
    )

    game_map.compute_fov(world, world[player, "Position"].x, world[player, "Position"].y)

    input_handler = InputHandler(world)
    input_handler.menu_state = MenuState.PLAY

    turn_count = 0

    from .components import MessageLog
    world["message_log"].components["MessageLog"] = MessageLog()

    msg_log = world["message_log", "MessageLog"]
    msg_log.add("Welcome to the dungeon! Be careful...", colors.yellow.tuple)
    msg_log.add("Arrow keys/WASD: move. g/.> : pick up.", colors.grey.tuple)

    game_over = False

    while True:
        render_all(
            console=console,
            world=world,
            game_map=game_map,
            player=player,
            menu_state=input_handler.menu_state,
            look_cursor_x=input_handler.look_cursor_x,
            look_cursor_y=input_handler.look_cursor_y,
            selected_index=input_handler.selected_index,
        )

        context.present(console)

        action = input_handler.handle_events()

        if action is None:
            continue

        player_pos = world[player, "Position"]

        if isinstance(action, ExitAction):
            break

        if input_handler.menu_state == MenuState.PLAY:
            if isinstance(action, MoveAction):
                dest_x = player_pos.x + action.kwargs["dx"]
                dest_y = player_pos.y + action.kwargs["dy"]

                if game_map.in_bounds(dest_x, dest_y) and game_map.tiles[dest_x, dest_y]["walkable"]:
                    target = None
                    for entity, pos in world.Q.all_of(components=[Position]):
                        if entity == player:
                            continue
                        if pos.x == dest_x and pos.y == dest_y:
                            if "Fighter" in world[entity].components and world[entity, "Fighter"].hp > 0:
                                target = entity
                                break

                    if target is not None:
                        messages = attack(player, target, world)
                        for msg in messages:
                            msg_log.add(msg, colors.white.tuple)

                        target_fighter = world[target, "Fighter"]
                        if target_fighter.hp <= 0:
                            from .items import _kill_entity
                            _kill_entity(target, world, game_map)
                    else:
                        player_pos.x = dest_x
                        player_pos.y = dest_y

                    turn_count += 1

            elif isinstance(action, PickupAction):
                items_on_ground = []
                for entity, pos in world.Q.all_of(components=[Position]):
                    if pos.x == player_pos.x and pos.y == player_pos.y:
                        if "Item" in world[entity].components:
                            items_on_ground.append(entity)

                if items_on_ground:
                    inventory = world[player, "Inventory"]
                    for item_id in items_on_ground:
                        if len(inventory.items) < inventory.capacity:
                            inventory.items.append(item_id)
                            item_name = world[item_id, "Name"].name
                            msg_log.add(f"You pick up the {item_name}.", colors.yellow.tuple)
                            item_pos = world[item_id, "Position"]
                            item_pos.x = -1
                            item_pos.y = -1
                        else:
                            msg_log.add("Your inventory is full.", colors.red.tuple)
                    turn_count += 1
                else:
                    msg_log.add("There is nothing here to pick up.", colors.grey.tuple)

            elif isinstance(action, WaitAction):
                turn_count += 1

        if input_handler.menu_state == MenuState.PLAY or isinstance(action, (CancelAction, ExitAction)):
            if turn_count > 0 and not game_over:
                from .ai_system import process_ai
                process_ai(world, game_map, player)

                player_fighter = world[player, "Fighter"]
                if player_fighter.hp <= 0:
                    msg_log.add("You have died!", colors.red.tuple)
                    input_handler.menu_state = MenuState.DEATH
                    game_over = True
                else:
                    game_map.compute_fov(world, player_pos.x, player_pos.y)
                turn_count = 0

        if isinstance(action, UseAction):
            item_id = action.kwargs["item_id"]
            if "Consumable" in world[item_id].components:
                messages = use_item(item_id, player_pos.x, player_pos.y, world, game_map)
                for msg in messages:
                    msg_log.add(msg, colors.white.tuple)
                game_map.compute_fov(world, player_pos.x, player_pos.y)
                turn_count += 1

        if isinstance(action, EquipAction):
            item_id = action.kwargs["item_id"]
            if "Equippable" in world[item_id].components:
                msg = equip(item_id, world)
                msg_log.add(msg, colors.yellow.tuple)
                turn_count += 1
            else:
                msg_log.add("You cannot equip that item.", colors.red.tuple)

        if isinstance(action, DropItemAction):
            item_id = action.kwargs["item_id"]
            inventory = world[player, "Inventory"]
            if item_id in inventory.items:
                inventory.items.remove(item_id)
                item_name = world[item_id, "Name"].name
                item_pos = world[item_id, "Position"]
                item_pos.x = player_pos.x
                item_pos.y = player_pos.y
                msg_log.add(f"You drop the {item_name}.", colors.yellow.tuple)
                turn_count += 1

        if isinstance(action, LevelUpAction):
            stat = action.kwargs["stat"]
            player_fighter = world[player, "Fighter"]
            if stat == "hp":
                player_fighter.max_hp += 20
                player_fighter.hp += 20
                msg_log.add("Your health increases!", colors.light_green.tuple)
            elif stat == "power":
                player_fighter.power += 1
                msg_log.add("You feel stronger!", colors.light_red.tuple)
            elif stat == "defense":
                player_fighter.defense += 1
                msg_log.add("Your skin grows tougher!", colors.light_blue.tuple)
            input_handler.menu_state = MenuState.PLAY
            turn_count += 1

        if isinstance(action, (LookAction, LogAction)):
            pass

        if isinstance(action, CancelAction):
            input_handler.menu_state = MenuState.PLAY

    context.quit()


if __name__ == "__main__":
    main()

"""Chapter 13: The Combat System."""
from __future__ import annotations

import tcod
import tcod.ecs
import tcod.event

from actions import BumpAction, WaitAction, PickupAction, UseItemAction
from components import Fighter, Position, Inventory, Consumable, Name
from factories.actors import spawn_random_enemy
from factories.items import create_health_potion
from game_map import GameMap
from input_handlers import handle_input
from message_log import MessageLog
from procgen import generate_dungeon
from render_functions import render_all, PANEL_HEIGHT
from systems import (
    compute_fov,
    process_action,
    process_enemy_turns,
    remove_dead_entities,
)
from combat import heal_player

SCREEN_WIDTH = 80
SCREEN_HEIGHT = 50

TILESET = tcod.tileset.load_truetype_font(
    "data/fonts/dejavu10x10.ttf", tile_width=16, tile_height=16
)


def create_player(registry: tcod.ecs.Registry, x: int, y: int) -> tcod.ecs.Entity:
    """Spawn the player entity."""
    player = registry.new_entity()
    player.components |= {
        Position: Position(x=x, y=y),
        Name: Name(name="Player"),
        Fighter: Fighter(hp=30, max_hp=30, power=5, defense=2),
        Inventory: Inventory(capacity=20),
    }
    player.tags.add("player")
    # Renderable is separate so it doesn't conflict with entities.json.
    from components import Renderable
    player.components[Renderable] = Renderable(char="@", fg=(255, 255, 255))
    return player


def place_enemies(
    registry: tcod.ecs.Registry,
    dungeon: GameMap,
    skip_room: int = 0,
) -> None:
    """Place 1-3 enemies in each room except the one the player starts in."""
    from components import Position as Pos
    for i, room in enumerate(dungeon.rooms):
        if i == skip_room:
            continue
        num_enemies = 1 + (i % 3)  # 1-3 enemies per room
        placed = 0
        attempts = 0
        while placed < num_enemies and attempts < 50:
            attempts += 1
            x = room.x + 1 + (attempts % max(1, room.w - 2))
            y = room.y + 1 + (attempts // max(1, room.w - 2)) % max(1, room.h - 2)
            if not dungeon.in_bounds(x, y) or not dungeon.is_walkable(x, y):
                continue
            occupied = False
            for ent, epos in registry.Q[Pos]:
                if epos.x == x and epos.y == y:
                    occupied = True
                    break
            if occupied:
                continue
            spawn_random_enemy(registry, x, y)
            placed += 1


def place_items(
    registry: tcod.ecs.Registry,
    dungeon: GameMap,
    skip_room: int = 0,
) -> None:
    """Place health potions in rooms."""
    from components import Position as Pos
    for i, room in enumerate(dungeon.rooms):
        if i == skip_room:
            continue
        if i % 2 == 0:  # Potion in every other room
            x = room.x + 1 + (i % max(1, room.w - 2))
            y = room.y + 1 + (i % max(1, room.h - 2))
            if dungeon.in_bounds(x, y) and dungeon.is_walkable(x, y):
                occupied = False
                for ent, epos in registry.Q[Pos]:
                    if epos.x == x and epos.y == y:
                        occupied = True
                        break
                if not occupied:
                    create_health_potion(registry, x, y)


def main() -> None:
    registry = tcod.ecs.Registry()
    message_log = MessageLog()

    # --- Generate the dungeon -------------------------------------------
    dungeon = generate_dungeon(
        max_rooms=30,
        room_min_size=6,
        room_max_size=10,
        map_width=SCREEN_WIDTH,
        map_height=SCREEN_HEIGHT - PANEL_HEIGHT,
    )

    # --- Create the player in the first room ---------------------------
    first_room = dungeon.rooms[0]
    player_x, player_y = first_room.center
    player = create_player(registry, player_x, player_y)

    # --- Populate with enemies and items --------------------------------
    place_enemies(registry, dungeon, skip_room=0)
    place_items(registry, dungeon, skip_room=0)

    # Store the map on the registry so render_functions can access it.
    registry.context["game_map"] = dungeon

    # Initial field-of-view computation.
    compute_fov(dungeon, player_x, player_y)

    message_log.add("Welcome to the dungeon! Find and defeat your enemies.", (0, 200, 255))

    console = tcod.console.Console(SCREEN_WIDTH, SCREEN_HEIGHT, order="C")
    game_over = False

    with tcod.context.new(
        console=console,
        tileset=TILESET,
        title="Chapter 13: The Combat System",
    ) as context:
        needs_render = True

        while True:
            # ---- Render ------------------------------------------------
            if needs_render:
                render_all(console, dungeon, registry, player, message_log)

                if game_over:
                    console.print(
                        x=SCREEN_WIDTH // 2 - 15,
                        y=SCREEN_HEIGHT // 2,
                        string="[ YOU HAVE DIED - press any key to exit ]",
                        fg=(255, 0, 0),
                    )

                context.present(console)
                needs_render = False

            # ---- Handle events -----------------------------------------
            for event in tcod.event.wait():
                if isinstance(event, tcod.event.Quit):
                    raise SystemExit()

                if not isinstance(event, tcod.event.KeyDown):
                    continue

                if event.sym == tcod.event.KeySym.ESCAPE:
                    raise SystemExit()

                if game_over:
                    raise SystemExit()

                action = handle_input(event, player)
                if action is None:
                    continue

                # ---- Handle item use -----------------------------------
                if isinstance(action, UseItemAction):
                    inventory = player.components[Inventory]
                    if 0 <= action.item_index < len(inventory.items):
                        item_entity = inventory.items[action.item_index]
                        if Consumable in item_entity.components:
                            consumable = item_entity.components[Consumable]
                            if consumable.heal_amount > 0:
                                heal_player(player, consumable.heal_amount, message_log)
                            # Remove the item from inventory and the world.
                            inventory.items.pop(action.item_index)
                            # Clear the item's world components so it disappears.
                            item_entity.components.clear()
                            item_entity.tags.clear()
                            # Item use also consumes a turn.
                            turn_spent = True
                        else:
                            message_log.add("You can't use that.", (150, 150, 150))
                            turn_spent = False
                    else:
                        turn_spent = False

                    if not turn_spent:
                        continue

                # ---- Handle pickup -------------------------------------
                elif isinstance(action, PickupAction):
                    pos = player.components[Position]
                    from components import Item
                    picked_up = False
                    for item_entity, item_pos in registry.Q[Position]:
                        if (
                            item_pos.x == pos.x
                            and item_pos.y == pos.y
                            and Item in item_entity.components
                        ):
                            inventory = player.components[Inventory]
                            if len(inventory.items) < inventory.capacity:
                                inventory.items.append(item_entity)
                                item_name = item_entity.components[Name].name
                                message_log.add(f"You pick up the {item_name}.", (0, 200, 0))
                                # Remove from the map (clear position).
                                item_entity.components.pop(Position, None)
                                picked_up = True
                                break
                            else:
                                message_log.add("Your inventory is full.", (255, 255, 0))
                                picked_up = True
                                break
                    if not picked_up:
                        message_log.add("Nothing to pick up here.", (150, 150, 150))
                        continue  # No turn spent.
                    turn_spent = True

                # ---- Handle bump / wait --------------------------------
                else:
                    turn_spent = process_action(action, registry, dungeon, message_log)

                if not turn_spent:
                    continue

                # ---- End-of-turn processing ----------------------------
                # 1. Update field of view.
                ppos = player.components[Position]
                compute_fov(dungeon, ppos.x, ppos.y)

                # 2. Let every visible enemy take its turn.
                process_enemy_turns(registry, dungeon, player, message_log)

                # 3. Remove anything that has been killed.
                player_died = remove_dead_entities(registry, message_log)

                # 4. Check whether the player has died.
                if player_died or player.components[Fighter].hp <= 0:
                    message_log.add("You have been defeated!", (255, 0, 0))
                    game_over = True

                needs_render = True


if __name__ == "__main__":
    main()

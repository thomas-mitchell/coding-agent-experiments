"""Game systems for the turn-based loop."""
from __future__ import annotations
from typing import TYPE_CHECKING

import tcod.constants
import tcod.map

from actions import BumpAction, WaitAction
from combat import attack
from components import AI, AIKind, Fighter, Name, Position
from message_log import MessageLog

if TYPE_CHECKING:
    import tcod.ecs
    from game_map import GameMap


FOV_RADIUS = 8


def compute_fov(game_map: GameMap, x: int, y: int) -> None:
    """Compute field of view from the given position and update explored tiles."""
    game_map.visible[:] = tcod.map.compute_fov(
        transparency=game_map.tiles["transparent"],
        pov=(y, x),
        radius=FOV_RADIUS,
        algorithm=tcod.constants.FOV_SYMMETRIC_SHADOWCAST,
    )
    game_map.explored |= game_map.visible


def process_action(
    action: BumpAction | WaitAction,
    registry: tcod.ecs.Registry,
    game_map: GameMap,
    message_log: MessageLog,
) -> bool:
    """Process a player action.  Returns True if the action consumed a turn."""
    if isinstance(action, WaitAction):
        return True

    if isinstance(action, BumpAction):
        pos = action.entity.components[Position]
        target_x = pos.x + action.dx
        target_y = pos.y + action.dy

        if not game_map.is_walkable(target_x, target_y):
            return False

        # Check for an entity at the target position -- if one exists, attack.
        for other, other_pos in registry.Q[Position]:
            if (
                other_pos.x == target_x
                and other_pos.y == target_y
                and other is not action.entity
                and Fighter in other.components
            ):
                attack(attacker=action.entity, target=other, message_log=message_log)
                return True

        # No obstacle -- move.
        pos.x = target_x
        pos.y = target_y
        return True

    return False


def process_enemy_turns(
    registry: tcod.ecs.Registry,
    game_map: GameMap,
    player: tcod.ecs.Entity,
    message_log: MessageLog,
) -> None:
    """Process turns for every enemy entity that can see the player."""
    player_pos = player.components[Position]

    for entity, pos, fighter, ai in registry.Q[Position, Fighter, AI]:
        if entity is player:
            continue
        if fighter.hp <= 0:
            continue

        # Only act when the enemy is inside the player's field of view.
        if not game_map.visible[pos.y, pos.x]:
            continue

        if ai.kind == AIKind.HOSTILE:
            # Simple chase: move one tile toward the player.
            dx = max(-1, min(1, player_pos.x - pos.x))
            dy = max(-1, min(1, player_pos.y - pos.y))

            target_x = pos.x + dx
            target_y = pos.y + dy

            # Adjacent to the player -- attack.
            if target_x == player_pos.x and target_y == player_pos.y:
                attack(attacker=entity, target=player, message_log=message_log)
            elif game_map.is_walkable(target_x, target_y):
                # Make sure no other entity is in the way.
                blocked = False
                for other, other_pos in registry.Q[Position]:
                    if (
                        other_pos.x == target_x
                        and other_pos.y == target_y
                        and other is not entity
                    ):
                        blocked = True
                        break
                if not blocked:
                    pos.x = target_x
                    pos.y = target_y


def remove_dead_entities(
    registry: tcod.ecs.Registry,
    message_log: MessageLog,
) -> bool:
    """Strip components from every entity whose HP has fallen to zero.

    Adds death messages to the log.  Returns True if the player died.
    """
    player_died = False
    to_remove: list[tcod.ecs.Entity] = []

    for entity, fighter in registry.Q[Fighter]:
        if fighter.hp <= 0:
            name = entity.components[Name].name if Name in entity.components else "Unknown"
            if "player" in entity.tags:
                message_log.add(f"{name} has been defeated!", (255, 0, 0))
                player_died = True
            else:
                message_log.add(f"{name} has been defeated!", (255, 150, 0))
                to_remove.append(entity)

    for entity in to_remove:
        entity.components.clear()
        entity.tags.clear()

    return player_died

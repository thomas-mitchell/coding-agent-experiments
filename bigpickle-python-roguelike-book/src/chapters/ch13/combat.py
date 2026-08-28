"""Combat system."""
from __future__ import annotations
import random
from typing import TYPE_CHECKING

from components import Fighter, Name, Position
from message_log import MessageLog

if TYPE_CHECKING:
    import tcod.ecs


DAMAGE_COLOR = (255, 100, 100)
CRITICAL_COLOR = (255, 200, 0)
HEAL_COLOR = (100, 255, 100)
INFO_COLOR = (200, 200, 200)


def attack(
    attacker: tcod.ecs.Entity,
    target: tcod.ecs.Entity,
    message_log: MessageLog,
) -> None:
    """Execute an attack from attacker to target."""
    atk_fighter = attacker.components[Fighter]
    tgt_fighter = target.components[Fighter]
    atk_name = attacker.components[Name].name
    tgt_name = target.components[Name].name

    # Base damage
    damage = max(1, atk_fighter.power - tgt_fighter.defense)

    # Randomness
    damage += random.randint(-1, 1)
    damage = max(1, damage)

    # Critical hit (10% chance)
    is_critical = random.random() < 0.1
    if is_critical:
        damage = int(damage * 1.5)
        message_log.add(
            f"{atk_name} lands a CRITICAL HIT on {tgt_name} for {damage} damage!",
            CRITICAL_COLOR,
        )
    else:
        message_log.add(
            f"{atk_name} attacks {tgt_name} for {damage} damage.",
            DAMAGE_COLOR,
        )

    tgt_fighter.hp -= damage


def heal(entity: tcod.ecs.Entity, amount: int, message_log: MessageLog) -> None:
    """Heal an entity."""
    fighter = entity.components[Fighter]
    name = entity.components[Name].name

    if fighter.hp >= fighter.max_hp:
        message_log.add(f"{name} is already at full health.", INFO_COLOR)
        return

    healed = min(amount, fighter.max_hp - fighter.hp)
    fighter.hp += healed
    message_log.add(f"{name} heals for {healed} HP.", HEAL_COLOR)


def heal_player(player: tcod.ecs.Entity, amount: int, message_log: MessageLog) -> None:
    """Heal the player entity."""
    heal(player, amount, message_log)

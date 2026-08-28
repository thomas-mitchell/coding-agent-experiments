from __future__ import annotations

from typing import TYPE_CHECKING

from . import color

if TYPE_CHECKING:
    from tcod.ecs import World


def attack(attacker: int, target: int, world: World) -> list[str]:
    messages: list[str] = []
    attacker_fighter = world[attacker, "Fighter"]
    target_fighter = world[target, "Fighter"]
    attacker_name = world[attacker, "Name"].name
    target_name = world[target, "Name"].name

    damage = attacker_fighter.power - target_fighter.defense

    if damage > 0:
        target_fighter.hp -= damage
        messages.append(f"{attacker_name} attacks {target_name} for {damage} hit points.")
        if target_fighter.hp <= 0:
            messages.append(f"{target_name} is dead!")
            if "XP" in world[attacker].components:
                xp_comp = world[attacker, "XP"]
                target_xp = world[target, "XP"]
                xp_comp.current += target_xp.level_up_xp
                messages.append(f"{attacker_name} gains {target_xp.level_up_xp} XP.")
    else:
        messages.append(f"{attacker_name} attacks {target_name} but does no damage.")

    return messages


def heal(target: int, amount: int, world: World) -> str:
    fighter = world[target, "Fighter"]
    name = world[target, "Name"].name
    if fighter.hp >= fighter.max_hp:
        return f"{name} is already at full health."
    healed = min(amount, fighter.max_hp - fighter.hp)
    fighter.hp += healed
    return f"{name} recovers {healed} HP."

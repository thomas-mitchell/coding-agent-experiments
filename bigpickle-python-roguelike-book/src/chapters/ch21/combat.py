"""Combat system, XP awarding, and player action processing."""
from __future__ import annotations

from typing import TYPE_CHECKING

import attrs
import tcod.constants
import tcod.map
from tcod.ecs import Entity

from actions import (
    BumpAction,
    CastAction,
    DescendAction,
    EquipAction,
    LevelUpChoiceAction,
    PickupAction,
    UseItemAction,
    WaitAction,
)
from components import (
    DEFENSE_CHOICE,
    Equipment,
    Fighter,
    HP_CHOICE,
    Inventory,
    Item,
    Name,
    Position,
    POWER_CHOICE,
    Renderable,
    Stairs,
    XP,
    get_defense,
    get_power,
)
from color import BLUE, CYAN, DIM_GRAY, GREEN, LIGHT_RED, ORANGE, RED, WHITE, YELLOW
from equipment import equip_item, unequip_item
from items import use_consumable

if TYPE_CHECKING:
    from targeting import TargetingState

    from game_map import GameMap

FOV_RADIUS = 8

# The world's total XP requirement grows by this factor per level.
XP_GROWTH = 1.5


@attrs.define
class ActionResult:
    """The outcome of processing a single player action."""

    spent_turn: bool = False      # a turn passed (movement, attack, cast, ...)
    descend: bool = False         # the player stepped onto the stairs and left
    targeting: object = None      # a TargetingState to enter, if applicable


def compute_fov(game_map: "GameMap", x: int, y: int) -> None:
    """Compute the field of view from (x, y) and mark explored tiles."""
    game_map.visible[:] = tcod.map.compute_fov(
        transparency=game_map.tiles["transparent"],
        pov=(y, x),
        radius=FOV_RADIUS,
        algorithm=tcod.constants.FOV_SYMMETRIC_SHADOWCAST,
    )
    game_map.explored |= game_map.visible


def attack(attacker: Entity, target: Entity) -> tuple[str, tuple[int, int, int]]:
    """Resolve a melee attack. Returns a (message, color) pair."""
    attacker_name = attacker.components[Name].name
    target_name = target.components[Name].name

    power = get_power(attacker)
    defense = get_defense(target)
    damage = max(0, power - defense)

    if damage > 0:
        target.components[Fighter].hp -= damage
        return (
            f"{attacker_name} attacks {target_name} for {damage} damage.",
            YELLOW if "player" in attacker.tags else RED,
        )
    return (
        f"{attacker_name} attacks {target_name} but does no damage.",
        DIM_GRAY,
    )


def heal(entity: Entity, amount: int) -> int:
    """Restore ``amount`` HP to ``entity`` (capped at max_hp).

    Returns the number of HP actually restored (0 if the entity is at full
    health). Used by consumable items via the message log.
    """
    fighter = entity.components[Fighter]
    healed = min(amount, fighter.max_hp - fighter.hp)
    fighter.hp += healed
    return healed


def grant_xp(xp: XP, value: int, log) -> int:
    """Award ``value`` XP and bank any level-ups.

    Whenever ``current`` reaches ``xp_to_next`` the character gains a level and
    a pending level-up choice (so the player can pick a stat bonus). Multiple
    levels may be gained at once from a single large award. Returns the number
    of pending level-ups now owed.
    """
    xp.current += value
    log.add(f"You gain {value} XP.", BLUE)

    while xp.current >= xp.xp_to_next:
        xp.current -= xp.xp_to_next
        xp.level += 1
        xp.xp_to_next = int(xp.xp_to_next * XP_GROWTH)
        xp.level_ups_pending += 1
        log.add(f"You reach level {xp.level}! Choose a bonus.", BLUE)

    return xp.level_ups_pending


def apply_level_up_choice(xp: XP, fighter: Fighter, choice: str, log) -> None:
    """Spend one pending level-up choice on a stat upgrade."""
    if choice == HP_CHOICE:
        fighter.max_hp += 2
        fighter.hp += 2
        log.add("Your health grows! +2 max HP.", GREEN)
    elif choice == POWER_CHOICE:
        fighter.power += 1
        log.add("Your power grows! +1 attack strength.", BLUE)
    elif choice == DEFENSE_CHOICE:
        fighter.defense += 1
        log.add("Your defense grows! +1 armor.", CYAN)
    else:
        log.add("Nothing happens.", YELLOW)
    xp.level_ups_pending = max(0, xp.level_ups_pending - 1)


def process_player_action(
    action,
    registry,
    game_map: "GameMap",
    log,
) -> ActionResult:
    """Handle a player-generated action and report its outcome."""
    if isinstance(action, WaitAction):
        return ActionResult(spent_turn=True)

    if isinstance(action, BumpAction):
        return ActionResult(spent_turn=_player_bump(action, registry, game_map, log))

    if isinstance(action, PickupAction):
        return ActionResult(spent_turn=_player_pickup(action, registry, log))

    if isinstance(action, UseItemAction):
        spent, targeting = _player_use_item(action, registry, game_map, log)
        return ActionResult(spent_turn=spent, targeting=targeting)

    if isinstance(action, CastAction):
        spent = _player_cast(action, registry, game_map, log)
        return ActionResult(spent_turn=spent)

    if isinstance(action, EquipAction):
        return ActionResult(spent_turn=_player_equip(action, registry, log))

    if isinstance(action, LevelUpChoiceAction):
        return ActionResult(
            spent_turn=_player_level_up_choice(action, registry, log)
        )

    if isinstance(action, DescendAction):
        return ActionResult(spent_turn=False, descend=_player_descend(action, registry, log))

    return ActionResult()


def _player_level_up_choice(action, registry, log) -> bool:
    """Apply a level-up choice (does not spend a turn)."""
    xp = action.entity.components.get(XP)
    fighter = action.entity.components.get(Fighter)
    if xp is None or fighter is None:
        return False
    if xp.level_ups_pending <= 0:
        log.add("You have no level-up to spend.", YELLOW)
        return False
    apply_level_up_choice(xp, fighter, action.choice, log)
    return True


def _player_bump(action, registry, game_map: "GameMap", log) -> bool:
    pos = action.entity.components[Position]
    target_x = pos.x + action.dx
    target_y = pos.y + action.dy

    if not game_map.is_walkable(target_x, target_y):
        return False

    for other, other_pos, fighter in registry.Q[Entity, Position, Fighter]:
        if (
            other_pos.x == target_x
            and other_pos.y == target_y
            and other is not action.entity
        ):
            msg, color = attack(attacker=action.entity, target=other)
            log.add(msg, color)
            return True

    pos.x = target_x
    pos.y = target_y
    return True


def _player_pickup(action, registry, log) -> bool:
    player = action.entity
    if Inventory not in player.components:
        return False
    inv = player.components[Inventory]
    ppos = player.components[Position]

    for item_entity, ipos, item in registry.Q[Entity, Position, Item]:
        if ipos.x == ppos.x and ipos.y == ppos.y:
            if len(inv.items) >= inv.capacity:
                log.add("Your inventory is full.", ORANGE)
                return False
            inv.items.append(item_entity)
            _remove_from_map(item_entity)
            log.add(f"You pick up the {item.name}.", ORANGE)
            return True
    log.add("There is nothing here to pick up.", WHITE)
    return False


def _remove_from_map(item_entity: Entity) -> None:
    """Take a lying item off the map (stop rendering / positioning it)."""
    for comp in (Position, Renderable):
        item_entity.components.pop(comp, None)


def _player_use_item(action, registry, game_map: "GameMap", log) -> tuple[bool, "TargetingState | None"]:
    player = action.entity
    inv = player.components.get(Inventory)
    if inv is None or not inv.items:
        log.add("You have nothing to use.", WHITE)
        return False, None

    # Use either a targeted item passed in, or the first consumable in hand.
    item = action.item
    if item is None:
        for candidate in inv.items:
            if has_consumable(candidate):
                item = candidate
                break
    if item is None or not has_consumable(item):
        log.add("You have no usable item.", WHITE)
        return False, None

    return use_consumable(registry, game_map, player, item, log)


def _player_cast(action, registry, game_map: "GameMap", log) -> bool:
    """Confirm a targeted spell cast (produced by the targeting mode)."""
    player = action.entity
    item = action.item
    if item is None or not has_consumable(item):
        log.add("You have no spell to cast.", WHITE)
        return False

    spent, targeting = use_consumable(
        registry, game_map, player, item, log, target=action.target
    )
    return spent


def _player_descend(action, registry, log) -> bool:
    """Attempt to descend the staircase on the player's tile."""
    pos = action.entity.components[Position]

    for other, other_pos, _stairs in registry.Q[Entity, Position, Stairs]:
        if other_pos.x == pos.x and other_pos.y == pos.y:
            return True

    log.add("There are no stairs here. Look for a '>'.", CYAN)
    return False


def has_consumable(item: Entity) -> bool:
    from components import Consumable

    return Consumable in item.components


def _player_equip(action, registry, log) -> bool:
    player = action.entity
    inv = player.components.get(Inventory)
    if inv is None or not inv.items:
        log.add("You have nothing to equip.", WHITE)
        return False

    item = action.item
    if item is None and inv.items:
        # Default: equip the first equippable item in the inventory.
        from components import Equippable

        for candidate in inv.items:
            if Equippable in candidate.components:
                item = candidate
                break
    if item is None:
        log.add("You have nothing to equip.", WHITE)
        return False

    from components import Equippable

    if Equippable not in item.components:
        log.add(f"The {_item_name(item)} cannot be equipped.", WHITE)
        return False

    return equip_item(player, item, log)


def _item_name(item: Entity) -> str:
    if Name in item.components:
        return item.components[Name].name
    return "item"


def resolve_enemy_attacks(
    registry,
    game_map: "GameMap",
    player: Entity,
    log,
) -> None:
    """Let every enemy adjacent to (or overlapping) the player attack it."""
    ppos = player.components[Position]

    for entity, pos, fighter in registry.Q[Entity, Position, Fighter]:
        if entity is player:
            continue
        if fighter.hp <= 0:
            continue

        dx = pos.x - ppos.x
        dy = pos.y - ppos.y
        distance = max(abs(dx), abs(dy))

        if distance == 1:
            msg, color = attack(attacker=entity, target=player)
            log.add(msg, color)
        elif distance == 0:
            # The AI moved onto the player's tile: attack and push back.
            msg, color = attack(attacker=entity, target=player)
            log.add(msg, color)
            _push_back(entity, pos, game_map, registry, player)


def _push_back(
    entity: Entity,
    pos: Position,
    game_map: "GameMap",
    registry,
    player: Entity,
) -> None:
    """Move an overlapping enemy to a free adjacent tile if possible."""
    ppos = player.components[Position]
    for dx, dy in [(0, 1), (0, -1), (1, 0), (-1, 0)]:
        tx, ty = ppos.x + dx, ppos.y + dy
        if not game_map.is_walkable(tx, ty):
            continue
        occupied = any(
            other is not player
            and other is not entity
            and other.components[Position].x == tx
            and other.components[Position].y == ty
            for other in registry.Q.all_of(components=[Position])
        )
        if not occupied:
            pos.x, pos.y = tx, ty
            return


def remove_dead_entities(registry, log, player: Entity) -> None:
    """Remove defeated entities and award XP for slain enemies."""
    xp = player.components.get(XP)

    for entity in registry.Q.all_of(components=[Fighter]):
        fighter = entity.components[Fighter]
        if fighter.hp > 0:
            continue
        name = entity.components[Name].name if Name in entity.components else "Unknown"
        log.add(f"{name} has been defeated!", LIGHT_RED)

        # Award the slayer XP equal to the victim's xp_value.
        if xp is not None and XP in entity.components:
            value = entity.components[XP].xp_value
            if value:
                grant_xp(xp, value, log)

        entity.components.clear()
        entity.tags.clear()

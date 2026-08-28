"""Items, consumables, and their use effects."""
from __future__ import annotations

from typing import TYPE_CHECKING

from tcod.ecs import Entity

from components import (
    Consumable,
    Inventory,
    Name,
    Position,
    TargetingMode,
)
from color import YELLOW

if TYPE_CHECKING:
    import tcod.ecs
    from game_map import GameMap


def use_consumable(
    registry: "tcod.ecs.Registry",
    game_map: "GameMap",
    entity: Entity,
    item: Entity,
    log,
    target: tuple[int, int] | None = None,
) -> tuple[bool, "TargetingState | None"]:
    """Use a consumable item.

    Returns a ``(turn_spent, targeting_state)`` pair. For targeted spells
    (fireball) the item is not consumed immediately: a targeting session is
    returned so the game can enter targeting mode. The confirmed cast is then
    re-dispatched with a ``target`` supplied.

    ``target`` is the (x, y) tile a targeted spell is centred on. When it is
    ``None`` and the item needs a target, a targeting session is started.
    """
    from targeting import begin_targeting

    consumable = item.components[Consumable]

    if consumable.use_function == "heal":
        return _dispatch_heal(entity, item, consumable, log), None

    # Targeted spells must be aimed first. If no target is supplied yet,
    # begin a targeting session and do not spend a turn.
    if target is None and consumable.targeting_mode != TargetingMode.NONE:
        px, py = entity.components[Position].x, entity.components[Position].y
        state = begin_targeting(
            item=item,
            origin_x=px,
            origin_y=py,
            mode=consumable.targeting_mode,
            max_range=consumable.max_range,
            radius=consumable.radius,
        )
        return False, state

    if consumable.use_function == "confusion":
        return _dispatch_confusion(registry, game_map, entity, item, log), None

    if consumable.use_function == "fireball":
        if target is None:
            log.add("The fireball needs a target.", YELLOW)
            return False, None
        return _dispatch_fireball(
            registry, game_map, entity, item, target, consumable, log
        ), None

    log.add("Nothing happens.", YELLOW)
    return False, None


def _dispatch_heal(entity: Entity, item: Entity, consumable: Consumable, log) -> bool:
    from spells import cast_heal

    used = cast_heal(entity, item, consumable.heal_amount, log)
    if used:
        _consume(entity, item)
    return used


def _dispatch_confusion(
    registry: "tcod.ecs.Registry",
    game_map: "GameMap",
    entity: Entity,
    item: Entity,
    log,
) -> bool:
    from spells import cast_confusion

    used = cast_confusion(registry, game_map, entity, item, log)
    if used:
        _consume(entity, item)
    return used


def _dispatch_fireball(
    registry: "tcod.ecs.Registry",
    game_map: "GameMap",
    entity: Entity,
    item: Entity,
    target: tuple[int, int],
    consumable: Consumable,
    log,
) -> bool:
    from spells import cast_fireball

    used = cast_fireball(
        registry,
        game_map,
        entity,
        item,
        target,
        consumable.damage,
        consumable.radius,
        log,
    )
    if used:
        _consume(entity, item)
    return used


def _consume(entity: Entity, item: Entity) -> None:
    """Remove a used item from the actor's inventory and the registry's view."""
    inv = entity.components.get(Inventory)
    if inv is not None and item in inv.items:
        inv.items.remove(item)
    item.components.clear()
    item.tags.clear()

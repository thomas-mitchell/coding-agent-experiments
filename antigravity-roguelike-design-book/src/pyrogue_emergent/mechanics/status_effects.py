"""
Reactive status effects, modifier stacks, and compounding status interactions.
"""

from __future__ import annotations
from dataclasses import dataclass, field
from enum import Enum, auto
from typing import Callable, Any
from pyrogue_emergent.ecs.entity import EntityManager
from pyrogue_emergent.ecs.components import CombatStats, Flammable, Position
from pyrogue_emergent.world.grid import LayeredGrid, GasType


class StatusType(Enum):
    BURNING = auto()
    WET = auto()
    OILED = auto()
    SHOCKED = auto()
    FROZEN = auto()
    POISONED = auto()
    STUNNED = auto()


@dataclass
class ActiveStatus:
    status_type: StatusType
    duration: int
    intensity: int = 1


@dataclass
class StatusContainer:
    """Component holding all active status effects for an entity."""
    statuses: dict[StatusType, ActiveStatus] = field(default_factory=dict)


class StatusEffectSystem:
    """
    Manages status effect lifecycles, compounding reactions, and tick damage.
    """
    def __init__(self, ecs: EntityManager, grid: LayeredGrid) -> None:
        self.ecs = ecs
        self.grid = grid

    def apply_status(self, entity_id: int, status_type: StatusType, duration: int, intensity: int = 1) -> list[str]:
        """
        Applies a status to an entity, checking for compound status interactions.
        """
        logs: list[str] = []
        container = self.ecs.get_component(entity_id, StatusContainer)
        if not container:
            container = StatusContainer()
            self.ecs.add_component(entity_id, container)

        existing = container.statuses

        # Compound rule 1: Wet + Burning -> Extinguish & create Steam
        if status_type == StatusType.WET and StatusType.BURNING in existing:
            del existing[StatusType.BURNING]
            pos_comp = self.ecs.get_component(entity_id, Position)
            if pos_comp and self.grid.in_bounds(pos_comp.pos):
                cell = self.grid.get_cell(pos_comp.pos)
                cell.gas_type = GasType.STEAM
                cell.gas_density = min(100, cell.gas_density + 40)
            logs.append(f"Entity {entity_id}'s flames were extinguished in a cloud of steam!")
            return logs

        if status_type == StatusType.BURNING and StatusType.WET in existing:
            del existing[StatusType.WET]
            logs.append(f"The water on Entity {entity_id} boiled away, stopping the fire!")
            return logs

        # Compound rule 2: Oiled + Burning -> Inferno
        if status_type == StatusType.BURNING and StatusType.OILED in existing:
            del existing[StatusType.OILED]
            intensity *= 2
            duration += 3
            logs.append(f"The oil on Entity {entity_id} caught fire with explosive fury!")

        # Compound rule 3: Wet + Shocked -> Stunned
        if (status_type == StatusType.SHOCKED and StatusType.WET in existing) or (status_type == StatusType.WET and StatusType.SHOCKED in existing):
            existing[StatusType.STUNNED] = ActiveStatus(StatusType.STUNNED, duration=2, intensity=1)
            logs.append(f"Electric current surged through the water on Entity {entity_id}, stunning them!")

        # Store or refresh status
        existing[status_type] = ActiveStatus(status_type, duration=duration, intensity=intensity)
        logs.append(f"Entity {entity_id} is now {status_type.name.lower()} (duration: {duration}).")
        return logs

    def tick_entity(self, entity_id: int) -> list[str]:
        """Processes one turn of status decay and active tick effects."""
        logs: list[str] = []
        container = self.ecs.get_component(entity_id, StatusContainer)
        if not container or not container.statuses:
            return logs

        stats = self.ecs.get_component(entity_id, CombatStats)
        pos = self.ecs.get_component(entity_id, Position)
        expired: list[StatusType] = []

        for st_type, status in container.statuses.items():
            # Apply tick effect
            match st_type:
                case StatusType.BURNING:
                    dmg = 3 * status.intensity
                    if stats:
                        stats.hp -= dmg
                        logs.append(f"Entity {entity_id} takes {dmg} burning damage (HP: {stats.hp}/{stats.max_hp})!")
                    if pos and self.grid.in_bounds(pos.pos):
                        cell = self.grid.get_cell(pos.pos)
                        cell.fire_intensity = max(cell.fire_intensity, 40)
                        cell.fire_fuel += 2

                case StatusType.POISONED:
                    dmg = 2 * status.intensity
                    if stats:
                        stats.hp -= dmg
                        logs.append(f"Entity {entity_id} suffers {dmg} poison damage!")

            status.duration -= 1
            if status.duration <= 0:
                expired.append(st_type)

        for st_type in expired:
            del container.statuses[st_type]
            logs.append(f"Entity {entity_id} is no longer {st_type.name.lower()}.")

        return logs

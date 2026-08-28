"""
Affordance resolution and verb-noun interaction pipeline.
"""

from __future__ import annotations
from dataclasses import dataclass
from typing import Callable, Any
from pyrogue_emergent.core.event_bus import EventBus, Event, Phase
from pyrogue_emergent.core.math2d import Vec2
from pyrogue_emergent.ecs.entity import EntityManager, Entity
from pyrogue_emergent.ecs.components import (
    Position, Physics, Material, Flammable, Conductive, LiquidContainer, CombatStats
)
from pyrogue_emergent.world.grid import LayeredGrid, FluidType, GasType, TileType


@dataclass
class ActionEvent(Event):
    actor_id: int = 0
    verb: str = ""
    target_id: int | None = None
    target_pos: Vec2 | None = None
    applied_damage: int = 0
    message: str = ""


class AffordanceSystem:
    """
    Resolves verbs against entities based on their dynamic components and environment.
    """
    def __init__(self, ecs: EntityManager, grid: LayeredGrid, bus: EventBus) -> None:
        self.ecs = ecs
        self.grid = grid
        self.bus = bus
        self._register_handlers()

    def _register_handlers(self) -> None:
        self.bus.subscribe(ActionEvent, Phase.EXECUTE, self._execute_action, priority=50)

    def _execute_action(self, event: ActionEvent, phase: Phase) -> None:
        match event.verb:
            case "ignite":
                self._handle_ignite(event)
            case "electrify":
                self._handle_electrify(event)
            case "throw":
                self._handle_throw(event)
            case "shatter":
                self._handle_shatter(event)
            case "dip":
                self._handle_dip(event)

    def _handle_ignite(self, event: ActionEvent) -> None:
        pos = event.target_pos
        if pos and self.grid.in_bounds(pos):
            cell = self.grid.get_cell(pos)
            cell.fire_intensity = max(cell.fire_intensity, 70)
            cell.fire_fuel += 10
            cell.temperature = max(cell.temperature, 250)
            event.message = f"Flame erupts at ({pos.x}, {pos.y})!"

        if event.target_id:
            flammable = self.ecs.get_component(event.target_id, Flammable)
            if flammable:
                flammable.is_burning = True
                event.message = f"Entity {event.target_id} catches fire!"

            physics = self.ecs.get_component(event.target_id, Physics)
            if physics and physics.explosive:
                # Trigger explosive cascade
                self._trigger_explosion(event.target_id, pos or Vec2(0, 0), physics, event)

    def _handle_electrify(self, event: ActionEvent) -> None:
        pos = event.target_pos
        if not pos or not self.grid.in_bounds(pos):
            return

        shock_damage = event.data.get("shock_power", 20)
        cell = self.grid.get_cell(pos)

        # Conduct across connected conductive fluid puddle
        if cell.is_conductive:
            event.message = f"Lightning conducts wildly across the {cell.fluid_type.name.lower()} puddle!"
            # Find connected conductive tiles (flood fill)
            visited: set[Vec2] = {pos}
            queue = [pos]
            while queue:
                curr = queue.pop(0)
                # Damage actor on this conductive tile
                c_cell = self.grid.get_cell(curr)
                if c_cell.actor:
                    stats = self.ecs.get_component(c_cell.actor, CombatStats)
                    if stats:
                        stats.hp -= shock_damage
                        event.message += f" Actor {c_cell.actor} shocked for {shock_damage} HP!"

                for neighbor in curr.neighbors_4():
                    if self.grid.in_bounds(neighbor) and neighbor not in visited:
                        n_cell = self.grid.get_cell(neighbor)
                        if n_cell.is_conductive:
                            visited.add(neighbor)
                            queue.append(neighbor)

    def _handle_throw(self, event: ActionEvent) -> None:
        item_id = event.data.get("item_id")
        target_pos = event.target_pos
        if not item_id or not target_pos:
            return

        physics = self.ecs.get_component(item_id, Physics)
        if physics and physics.fragile:
            # Shatter the item on impact
            shatter_event = ActionEvent(
                actor_id=event.actor_id,
                verb="shatter",
                target_id=item_id,
                target_pos=target_pos,
                data={"shattered_by": event.actor_id}
            )
            self.bus.queue_cascade(shatter_event, event)
        else:
            # Drop onto tile
            self.ecs.add_component(item_id, Position(target_pos))
            self.grid.add_item(item_id, target_pos)
            event.message = f"Item {item_id} landed at ({target_pos.x}, {target_pos.y})."

    def _handle_shatter(self, event: ActionEvent) -> None:
        item_id = event.target_id
        pos = event.target_pos
        if not item_id or not pos:
            return

        container = self.ecs.get_component(item_id, LiquidContainer)
        if container and container.volume > 0 and container.fluid_type != FluidType.NONE:
            # Spill liquid into the target cell
            cell = self.grid.get_cell(pos)
            cell.fluid_type = container.fluid_type
            cell.fluid_volume += container.volume
            event.message = f"Potion shattered, splashing {container.volume} units of {container.fluid_type.name.lower()} onto the floor!"

            # If spilled liquid is oil and cell is on fire -> instant ignition cascade
            if container.fluid_type == FluidType.OIL and cell.fire_intensity > 0:
                ignite_event = ActionEvent(
                    actor_id=event.actor_id,
                    verb="ignite",
                    target_pos=pos,
                    data={"fuel": container.volume}
                )
                self.bus.queue_cascade(ignite_event, event)

        # Destroy item entity
        self.ecs.destroy_entity(item_id)

    def _trigger_explosion(self, entity_id: int, pos: Vec2, physics: Physics, parent_event: Event) -> None:
        radius = physics.explosion_radius
        damage = physics.explosion_damage
        event = ActionEvent(
            actor_id=entity_id,
            verb="explosion",
            target_pos=pos,
            message=f"BOOM! Explosive barrel detonated at ({pos.x}, {pos.y})!"
        )
        self.bus.queue_cascade(event, parent_event)

        # Apply radial damage & ignite tiles
        for dy in range(-radius, radius + 1):
            for dx in range(-radius, radius + 1):
                p = Vec2(pos.x + dx, pos.y + dy)
                if self.grid.in_bounds(p) and pos.chebyshev_dist(p) <= radius:
                    cell = self.grid.get_cell(p)
                    cell.fire_intensity = max(cell.fire_intensity, 90)
                    cell.fire_fuel += 8
                    cell.temperature += 400
                    if cell.actor:
                        stats = self.ecs.get_component(cell.actor, CombatStats)
                        if stats:
                            stats.hp -= damage

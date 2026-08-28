"""
Energy-based tick scheduler for turn-based roguelikes with variable actor speeds.
"""

from __future__ import annotations
from dataclasses import dataclass, field
from typing import Iterator
import heapq


STANDARD_ENERGY_COST = 1000
BASE_SPEED = 1000


@dataclass(order=True)
class ScheduledActor:
    """Actor entry in the priority heap, ordered by next execution tick."""
    ready_tick: int
    actor_id: int = field(compare=False)
    speed: int = field(default=BASE_SPEED, compare=False)
    energy: int = field(default=0, compare=False)


class EnergyScheduler:
    """
    Time scheduler based on accumulated energy ticks.
    Actors act when their accumulated energy reaches STANDARD_ENERGY_COST.
    Supports variable speeds, haste, slow, and deterministic execution ordering.
    """
    def __init__(self) -> None:
        self.current_tick: int = 0
        self.turn_count: int = 0
        self._actors: dict[int, ScheduledActor] = {}
        self._heap: list[ScheduledActor] = []

    def add_actor(self, actor_id: int, speed: int = BASE_SPEED, initial_delay: int = 0) -> None:
        """Registers a new actor into the scheduling timeline."""
        ready_tick = self.current_tick + initial_delay
        actor = ScheduledActor(
            ready_tick=ready_tick,
            actor_id=actor_id,
            speed=max(100, speed),
            energy=0,
        )
        self._actors[actor_id] = actor
        heapq.heappush(self._heap, actor)

    def remove_actor(self, actor_id: int) -> None:
        """Removes an actor from the scheduler."""
        if actor_id in self._actors:
            del self._actors[actor_id]
            # Stale entries in the heap are ignored upon pop

    def update_speed(self, actor_id: int, new_speed: int) -> None:
        """Dynamically updates an actor's speed (e.g. haste/slow/frozen)."""
        if actor_id in self._actors:
            self._actors[actor_id].speed = max(100, new_speed)

    def next_actor(self) -> int | None:
        """
        Advances the simulation clock to the next ready actor and returns its ID.
        Returns None if no actors are active.
        """
        while self._heap:
            entry = heapq.heappop(self._heap)
            # Verify actor is still registered
            if entry.actor_id not in self._actors:
                continue

            actor = self._actors[entry.actor_id]
            self.current_tick = max(self.current_tick, entry.ready_tick)
            return actor.actor_id

        return None

    def complete_turn(self, actor_id: int, cost_multiplier: float = 1.0) -> None:
        """
        Completes an actor's action, calculating the next tick they become active.
        """
        if actor_id not in self._actors:
            return

        actor = self._actors[actor_id]
        cost = int(STANDARD_ENERGY_COST * cost_multiplier)
        # Delay ticks until next turn based on speed
        # delay = (cost * 1000) // speed
        ticks_delay = max(1, (cost * BASE_SPEED) // actor.speed)
        actor.ready_tick = self.current_tick + ticks_delay
        heapq.heappush(self._heap, ScheduledActor(
            ready_tick=actor.ready_tick,
            actor_id=actor.actor_id,
            speed=actor.speed,
        ))

    def advance_turn_counter(self) -> None:
        self.turn_count += 1

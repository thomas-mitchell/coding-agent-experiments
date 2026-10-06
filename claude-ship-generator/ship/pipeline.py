"""The ship generation pipeline.

SHIP ARCHETYPE → DECK SHAPE → FUNCTIONAL ZONES → CORRIDOR NETWORK
→ RECTANGULAR PARTITIONING → ASSIGN ROOMS → DOORS / CONNECTIVITY GRAPH
→ TEMPLATES / FURNISHING* → VENT NETWORK* → VALIDATION → DISASTER*

(* not implemented yet; see stages/stubs.py)
"""

from __future__ import annotations

import random

import numpy as np

from .model import Ship
from .stages import assign, corridors, deck, doors, partition, stubs, validate, zones

MAX_ATTEMPTS = 25


class GenerationError(RuntimeError):
    pass


def _build(seed: int, rng: random.Random) -> Ship:
    layout = deck.frigate(rng)
    ship = deck.build_hull(seed, layout)
    plan = zones.plan_zones(rng, layout)
    cross = corridors.plan_cross_corridors(rng, layout, plan)
    corridors.carve_corridors(ship, layout, cross)
    ship.blocks = corridors.extract_blocks(layout, plan, cross)
    partition.partition(rng, ship, ship.blocks)
    assign.assign_rooms(rng, ship)
    doors.place_doors(rng, ship)
    ship = stubs.apply_templates_and_furnish(rng, ship)
    ship = stubs.build_vent_network(rng, ship)
    return ship


def _index_rooms(ship: Ship) -> None:
    ship.room_at = np.zeros(ship.tiles.shape, dtype=np.int32)
    for room in ship.rooms:
        ship.room_at[room.rect.inner_slices()] = room.id


def generate_ship(seed: int) -> Ship:
    """Generate a validated ship. Deterministic for a given seed."""
    last_problems: list[str] = []
    for attempt in range(MAX_ATTEMPTS):
        rng = random.Random(f"{seed}:{attempt}")
        ship = _build(seed, rng)
        last_problems = validate.validate(ship)
        if not last_problems:
            ship = stubs.apply_disaster(rng, ship)
            _index_rooms(ship)
            ship.attempts = attempt + 1
            return ship
    raise GenerationError(f"seed {seed}: no valid ship after {MAX_ATTEMPTS} attempts: {last_problems}")

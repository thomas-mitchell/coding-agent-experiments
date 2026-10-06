"""Later pipeline stages, present as no-ops so the pipeline's shape is visible.

Each takes and returns the ship; fill them in as the game grows.
"""

from __future__ import annotations

from ..model import Ship


def apply_templates_and_furnish(rng, ship: Ship) -> Ship:
    """TODO: stamp room templates (door sockets, fixed features) and furnish by purpose.

    e.g. crew quarters: beds against walls, lockers beside beds, clear path between doors.
    """
    return ship


def build_vent_network(rng, ship: Ship) -> Ship:
    """TODO: a second connectivity graph of vents/maintenance ducts between rooms."""
    return ship


def apply_disaster(rng, ship: Ship) -> Ship:
    """TODO: wreck the orderly ship: welded doors, hull breaches, collapses, lockdowns."""
    return ship

"""Stage 2: functional zoning.

Zones are decided before rooms so that related compartments cluster together:
command at the bow, engineering at the stern, habitation/science above the
spine and cargo below it (against the hull, where airlocks can go).
"""

from __future__ import annotations

from dataclasses import dataclass

from ..model import ZoneKind
from .deck import Deck


@dataclass
class ZonePlan:
    command_end: int  # first module column that is not command
    engineering_start: int  # first module column that is engineering
    science_start: int  # upper side: habitation before this column, science from it

    def zone_for(self, side: str, col: int) -> ZoneKind:
        if col < self.command_end:
            return ZoneKind.COMMAND
        if col >= self.engineering_start:
            return ZoneKind.ENGINEERING
        if side == "lower":
            return ZoneKind.CARGO
        return ZoneKind.HABITATION if col < self.science_start else ZoneKind.SCIENCE

    def boundaries(self, side: str) -> list[int]:
        """Module columns where one zone meets another on the given side."""
        if side == "upper":
            return [self.command_end, self.science_start, self.engineering_start]
        return [self.command_end, self.engineering_start]


def plan_zones(rng, deck: Deck) -> ZonePlan:
    command_end = rng.choice([3, 4])
    engineering_start = rng.choice([deck.cols - 3, deck.cols - 2])
    science_start = rng.randint(command_end + 1, engineering_start - 1)
    return ZonePlan(command_end, engineering_start, science_start)

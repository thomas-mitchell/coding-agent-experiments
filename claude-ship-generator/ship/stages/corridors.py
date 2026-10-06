"""Stage 3: the corridor skeleton, carved before any rooms exist.

A wide main spine runs bow to stern, and narrower cross corridors branch off it
on module lines (always at zone boundaries, sometimes elsewhere). Whatever the
corridors leave behind becomes a set of zone-owned blocks to be subdivided.
"""

from __future__ import annotations

from .. import tiles as T
from ..model import Block, Rect, Ship
from .deck import MODULE, Deck
from .zones import ZonePlan

SIDES = ("upper", "lower")
EXTRA_CROSS_CHANCE = {"upper": 0.4, "lower": 0.75}


def plan_cross_corridors(rng, deck: Deck, zones: ZonePlan) -> dict[str, list[int]]:
    """Module columns (as x = col*MODULE lines) that get a cross corridor, per side."""
    result = {}
    for side in SIDES:
        cols = set(zones.boundaries(side))
        candidates = [
            c
            for c in range(2, deck.cols - 1)
            if deck.extents[c - 1] == deck.extents[c] and all(abs(c - o) > 1 for o in cols)
        ]
        if candidates and rng.random() < EXTRA_CROSS_CHANCE[side]:
            cols.add(rng.choice(candidates))
        result[side] = sorted(cols)
    return result


def carve_corridors(ship: Ship, deck: Deck, cross: dict[str, list[int]]) -> None:
    y0, y1 = deck.spine
    ship.tiles[MODULE + 1 : ship.width - MODULE - 1, y0 : y1 + 1] = T.CORRIDOR
    for side, cols in cross.items():
        step, y = (-1, y0 - 1) if side == "upper" else (1, y1 + 1)
        for c in cols:
            x = c * MODULE
            yy = y
            while ship.tiles[x, yy] != T.HULL:
                ship.tiles[x, yy] = T.CORRIDOR
                yy += step


def extract_blocks(deck: Deck, zones: ZonePlan, cross: dict[str, list[int]]) -> list[Block]:
    """Split the non-corridor deck into rectangles, each owned by one zone."""
    last = deck.cols - 1
    blocks = [
        Block(Rect(0, deck.col_top(0), MODULE, deck.col_bottom(0)), zones.zone_for("full", 0)),
        Block(
            Rect(last * MODULE, deck.col_top(last), deck.width - 1, deck.col_bottom(last)),
            zones.zone_for("full", last),
        ),
    ]
    y0, y1 = deck.spine
    for side in SIDES:
        # Segment edges between the bow block, each cross corridor and the stern block.
        edges = [MODULE]
        for c in cross[side]:
            edges += [c * MODULE - 1, c * MODULE + 1]
        edges.append(last * MODULE)
        for xa, xb in zip(edges[::2], edges[1::2]):
            # Further split wherever the hull extent changes between module columns.
            first_col, last_col = xa // MODULE, (xb - 1) // MODULE
            start = xa
            for c in range(first_col, last_col + 1):
                end = xb if c == last_col or deck.extents[c] != deck.extents[c + 1] else None
                if end is None:
                    continue
                if c != last_col:
                    end = (c + 1) * MODULE
                if side == "upper":
                    rect = Rect(start, deck.col_top(c), end, y0 - 1)
                else:
                    rect = Rect(start, y1 + 1, end, deck.col_bottom(c))
                blocks.append(Block(rect, zones.zone_for(side, (start + end) // 2 // MODULE)))
                start = end
    return blocks

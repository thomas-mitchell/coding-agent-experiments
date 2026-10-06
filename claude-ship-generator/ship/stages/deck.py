"""Stage 1: ship archetype and deck shape.

The deck is laid out on a coarse structural grid of MODULE×MODULE tiles. Each
module column has a vertical extent (in module rows), which gives the hull its
silhouette: a stepped, tapering bow and a square or narrowed engine stern.
"""

from __future__ import annotations

from dataclasses import dataclass

import numpy as np

from .. import tiles as T
from ..model import Ship

MODULE = 8


@dataclass
class Deck:
    cols: int
    rows: int
    extents: list[tuple[int, int]]  # per column: (top module row, bottom module row exclusive)
    spine: tuple[int, int]  # inclusive tile rows of the main spine corridor

    @property
    def width(self) -> int:
        return self.cols * MODULE + 1

    @property
    def height(self) -> int:
        return self.rows * MODULE + 1

    def col_top(self, col: int) -> int:
        return self.extents[col][0] * MODULE

    def col_bottom(self, col: int) -> int:
        return self.extents[col][1] * MODULE


def frigate(rng) -> Deck:
    """The only archetype so far: an 11×5 module frigate with a tapered bow."""
    cols, rows = 11, 5
    extents = [(0, rows)] * cols
    extents[0] = rng.choice([(1, 4), (2, 3)])
    if extents[0] == (2, 3):
        extents[1] = rng.choice([(1, 4), (0, 5)])
    elif rng.random() < 0.4:
        extents[1] = (1, 4)
    if rng.random() < 0.4:
        extents[-1] = (1, 4)
    centre = rows * MODULE // 2
    return Deck(cols, rows, extents, spine=(centre - 1, centre + 1))


def build_hull(seed: int, deck: Deck) -> Ship:
    """Fill the deck with solid wall and outline it with hull plating."""
    w, h = deck.width, deck.height
    mask = np.zeros((w, h), dtype=bool)
    for c, (top, bottom) in enumerate(deck.extents):
        mask[c * MODULE : c * MODULE + MODULE + 1, top * MODULE : bottom * MODULE + 1] = True

    # A deck tile is interior only if all 8 neighbours are deck too.
    padded = np.pad(mask, 1, constant_values=False)
    interior = mask.copy()
    for dx in (-1, 0, 1):
        for dy in (-1, 0, 1):
            interior &= padded[1 + dx : 1 + dx + w, 1 + dy : 1 + dy + h]

    tiles = np.full((w, h), T.VOID, dtype=np.uint8)
    tiles[mask] = T.HULL
    tiles[interior] = T.WALL
    return Ship(seed=seed, width=w, height=h, tiles=tiles)

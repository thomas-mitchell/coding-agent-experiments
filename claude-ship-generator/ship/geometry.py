"""Small geometry helpers used by several stages."""

from __future__ import annotations

import numpy as np

from . import tiles as T
from .model import Rect


def shared_wall(a: Rect, b: Rect) -> list[tuple[int, int]]:
    """Wall tiles between ``a`` and ``b`` that open into both interiors."""
    if a.x2 == b.x or b.x2 == a.x:
        x = a.x2 if a.x2 == b.x else a.x
        lo, hi = max(a.y, b.y) + 1, min(a.y2, b.y2) - 1
        return [(x, y) for y in range(lo, hi + 1)]
    if a.y2 == b.y or b.y2 == a.y:
        y = a.y2 if a.y2 == b.y else a.y
        lo, hi = max(a.x, b.x) + 1, min(a.x2, b.x2) - 1
        return [(x, y) for x in range(lo, hi + 1)]
    return []


def edge_tiles(r: Rect) -> list[tuple[tuple[int, int], tuple[int, int]]]:
    """Every non-corner edge tile of ``r`` paired with its outward direction."""
    out = []
    for y in range(r.y + 1, r.y2):
        out.append(((r.x, y), (-1, 0)))
        out.append(((r.x2, y), (1, 0)))
    for x in range(r.x + 1, r.x2):
        out.append(((x, r.y), (0, -1)))
        out.append(((x, r.y2), (0, 1)))
    return out


def tile_at(tiles: np.ndarray, x: int, y: int) -> int:
    w, h = tiles.shape
    return int(tiles[x, y]) if 0 <= x < w and 0 <= y < h else T.VOID


def pick_middle(rng, candidates: list):
    """Pick a candidate, biased away from the ends (i.e. away from wall corners)."""
    n = len(candidates)
    margin = n // 4
    return candidates[rng.randint(margin, n - 1 - margin)]

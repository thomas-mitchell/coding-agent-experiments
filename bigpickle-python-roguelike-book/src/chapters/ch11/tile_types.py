"""Tile type definitions for the game map."""
from __future__ import annotations

import numpy as np

# Tile dtype: walkable, transparent, dark_fg(3), dark_bg(3), light_fg(3), light_bg(3)
TILE_DTYPE = np.dtype([
    ("walkable", bool),
    ("transparent", bool),
    ("dark_fg", "(3,)u1"),
    ("dark_bg", "(3,)u1"),
    ("light_fg", "(3,)u1"),
    ("light_bg", "(3,)u1"),
])


def _tile(
    walkable: bool,
    transparent: bool,
    dark_fg: tuple[int, int, int],
    dark_bg: tuple[int, int, int],
    light_fg: tuple[int, int, int],
    light_bg: tuple[int, int, int],
) -> np.ndarray:
    return np.array(
        (walkable, transparent, dark_fg, dark_bg, light_fg, light_bg),
        dtype=TILE_DTYPE,
    )


VOID = _tile(False, False, (0, 0, 0), (0, 0, 0), (0, 0, 0), (0, 0, 0))
FLOOR = _tile(True, True, (50, 50, 150), (0, 0, 10), (200, 200, 200), (50, 50, 100))
WALL = _tile(False, False, (0, 0, 100), (0, 0, 50), (130, 110, 50), (200, 180, 50))

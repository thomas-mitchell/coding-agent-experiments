from __future__ import annotations

import numpy as np

dt = np.dtype(
    [
        ("walkable", bool),
        ("transparent", bool),
        ("dark", "3int8"),
        ("light", "3int8"),
    ]
)


def new_tile(
    *,
    walkable: bool,
    transparent: bool,
    dark: tuple[int, int, int],
    light: tuple[int, int, int],
) -> np.ndarray:
    return np.array((walkable, transparent, dark, light), dtype=dt)


VOID = new_tile(
    walkable=False,
    transparent=False,
    dark=(0, 0, 0),
    light=(0, 0, 0),
)

FLOOR = new_tile(
    walkable=True,
    transparent=True,
    dark=(50, 50, 80),
    light=(130, 120, 110),
)

WALL = new_tile(
    walkable=False,
    transparent=False,
    dark=(0, 0, 60),
    light=(180, 160, 140),
)

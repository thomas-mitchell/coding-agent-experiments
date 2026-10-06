"""Tile types and their static properties.

Tiles are stored as small integer ids in a numpy array; these lookup arrays map
an id to its properties so movement checks and rendering are plain indexing.
"""

import numpy as np

VOID = 0
HULL = 1
WALL = 2
FLOOR = 3
CORRIDOR = 4
DOOR = 5
AIRLOCK = 6

# Matches tcod's console ``rgb`` dtype so ``GRAPHICS[tiles]`` can be blitted directly.
graphic_dt = np.dtype([("ch", np.int32), ("fg", "3B"), ("bg", "3B")])

_TABLE = {
    #          walkable, glyph, fg,              bg
    VOID:     (False, " ", (0, 0, 0),       (0, 0, 0)),
    HULL:     (False, "▓", (105, 110, 125), (38, 40, 48)),
    WALL:     (False, "#", (140, 145, 155), (28, 30, 36)),
    FLOOR:    (True,  ".", (70, 72, 80),    (12, 12, 16)),
    CORRIDOR: (True,  "·", (120, 115, 85),  (20, 20, 16)),
    DOOR:     (True,  "+", (230, 185, 60),  (45, 34, 12)),
    AIRLOCK:  (True,  "=", (80, 210, 230),  (10, 40, 50)),
}

WALKABLE = np.array([_TABLE[i][0] for i in range(len(_TABLE))], dtype=bool)
GRAPHICS = np.array(
    [(ord(_TABLE[i][1]), _TABLE[i][2], _TABLE[i][3]) for i in range(len(_TABLE))],
    dtype=graphic_dt,
)
ASCII = [_TABLE[i][1] for i in range(len(_TABLE))]

"""Map key presses to game actions."""

from __future__ import annotations

from tcod.event import KeySym as K

MOVE_KEYS: dict[K, tuple[int, int]] = {
    # Arrows
    K.UP: (0, -1), K.DOWN: (0, 1), K.LEFT: (-1, 0), K.RIGHT: (1, 0),
    K.HOME: (-1, -1), K.END: (-1, 1), K.PAGEUP: (1, -1), K.PAGEDOWN: (1, 1),
    # Numpad
    K.KP_8: (0, -1), K.KP_2: (0, 1), K.KP_4: (-1, 0), K.KP_6: (1, 0),
    K.KP_7: (-1, -1), K.KP_9: (1, -1), K.KP_1: (-1, 1), K.KP_3: (1, 1),
    # Vi keys
    K.K: (0, -1), K.J: (0, 1), K.H: (-1, 0), K.L: (1, 0),
    K.Y: (-1, -1), K.U: (1, -1), K.B: (-1, 1), K.N: (1, 1),
}

REGENERATE_KEY = K.R
TOGGLE_LABELS_KEY = K.TAB
QUIT_KEY = K.ESCAPE

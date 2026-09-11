"""How the 192 visible scanlines are divided, and the game-Y <-> screen-row flip.

    rows   0..7      SCRKER    six score digits
    rows   8..161    the play area, TOPSCN+1 == 154 lines
    rows 162..191    SCANDS    the scanner strip and the fuel bar

That adds up to SCNSIZ ($99 + 39 = 192), which is the count the screen-protect
path paints (asm:4988) -- so it is the assembly's own arithmetic, not a guess.

The game's Y counts UP from the BOTTOM of the play area, with TOPSCN ($99) at
the top.  This is the only place that gets flipped.
"""

from ..state import TOPSCN

SCORE_TOP = 0
SCORE_ROWS = 8

PLAY_TOP = SCORE_TOP + SCORE_ROWS
PLAY_ROWS = TOPSCN + 1

SCAN_TOP = PLAY_TOP + PLAY_ROWS
SCAN_ROWS = 192 - SCAN_TOP


def play_row(game_y):
    """Screen row for a game Y.  Below the play area the result is off-screen,
    which the framebuffer clips."""
    return PLAY_TOP + (TOPSCN - game_y)

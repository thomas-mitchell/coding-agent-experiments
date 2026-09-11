"""CHART (asm:4051) -- the star chart.

The chart is a 6-wide by 8-tall grid of cells packed two per byte in CHTBLK,
each holding an icon index into CHTAB8.  CHTSRV fills in the walls from CHTAB4
and SMRJOY draws the fleets and your cursor on top, so by the time the kernel
runs there is nothing left to decide -- it just paints the 48 cells.

CHTAB7[level] gives the background colour, which is how each level's map reads
as a different region of space.
"""

from .. import romdata as rom
from ..state import CHTBLK, NEWLEV
from .layout import PLAY_TOP, SCAN_TOP

CHTAB7 = rom.tab("CHTAB7")
CHTAB8 = rom.LABELS["CHTAB8"]      # page-aligned at $F100: index == page offset

COLS = 6
ROWS = 8
CELL_W = 16                        # 6 x 16 = 96 pixels of grid...
CELL_H = 16                        # ... and 8 x 16 = 128 of the 154 available
LEFT = (160 - COLS * CELL_W) // 2
TOP = PLAY_TOP + ((SCAN_TOP - PLAY_TOP) - ROWS * CELL_H) // 2
ICON_COLOUR = 0x0E


def draw(mach, frame):
    m = mach.m
    background = CHTAB7[m[NEWLEV]]
    frame.fill_rows(PLAY_TOP, SCAN_TOP - 1, background)

    for cell in range(COLS * ROWS):
        packed = m[CHTBLK + (cell >> 1)]
        icon = (packed >> 4) if (cell & 1) else (packed & 0x0F)
        if icon == 0:
            continue
        # The cell index increases by one going LEFT and by six going UP, which
        # is the same geometry FINDV's route steps use.
        col = COLS - 1 - (cell % COLS)
        row = ROWS - 1 - (cell // COLS)
        _icon(frame, icon, LEFT + col * CELL_W, TOP + row * CELL_H)

    for row in range(PLAY_TOP, SCAN_TOP):
        frame.end_scanline()


def _icon(frame, icon, x, y):
    """One 8x8 glyph from CHTAB8, drawn at double height so the grid fills the
    screen the way the real kernel's two-line-per-row loop does."""
    for k in range(8):
        bits = rom.DATA[CHTAB8 + icon * 8 + (7 - k)]
        if not isinstance(bits, int) or bits == 0:
            continue
        frame.player(y + k * 2, x, bits, ICON_COLOUR, group=0)
        frame.player(y + k * 2 + 1, x, bits, ICON_COLOUR, group=0)

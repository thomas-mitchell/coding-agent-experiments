"""SCRKER (asm:3963) and SCANDS (asm:4227) -- the score line and the scanner strip.

SCRKER draws six BCD digits across the top from the glyph pointers MESSRV left
in PNTR1..PNTR6, using both players three-copies-wide so two sprites make six
glyphs.  PNTR6 is leftmost; PNTR1 is a hard-coded '0', which is why every score
in the game is a multiple of ten.

SCANDS draws, in a 16-line box:
  * the TARGET ICON (player 0) from CHTAB8 via SCNTB2, masked by MASKTB, its
    vertical position within the box showing whether the target is above or
    below you;
  * two glyphs (player 1, two copies 64 pixels apart) -- direction arrows on the
    upper half, the two-digit RANGE on the lower half, switched by bit 7 of
    TACTB2;
  * the box itself as a playfield pattern from TACTB1.
Then the lives count (LIVTAB) and the fuel bar (FUELT1) as playfield, with the
word FUEL spelled out by FUELT2..FUELT5.

Horizontal positions
--------------------
The kernel positions everything with RESPx-strobe timing, which the port does
not reproduce.  Where the assembly encodes a position in a table the port uses
it: XTABLE's entries match CRAZY entries 1, 3, 5 ... so the scanner blip moves
two pixels per step, and that spacing is exact.  The absolute origins below are
chosen to sit the strip in the middle of the screen; they are the one part of
this file not derived from the ROM.
"""

from .. import romdata as rom
from ..state import (ATRACT, CENTER, FUEL, HGRAP0, HHORP0, HVERP0, LIVES,
                     ONESHT, PNTR1, PNTR2, PNTR3, PNTR4, PNTR5, PNTR6, PROGST,
                     PROGST_OVER, RANDOM, TARNUM, ZPOSP0)
from .layout import SCAN_TOP, SCORE_ROWS, SCORE_TOP

SCRTAB = rom.LABELS["SCRTAB"]       # page-aligned at $F000: index == page offset
CHTAB8 = rom.LABELS["CHTAB8"]       # page-aligned at $F100
MASKTB = rom.LABELS["MASKTB"]
SCNTB1 = rom.tab("SCNTB1")
SCNTB2 = rom.tab("SCNTB2")
SCNTB4 = rom.tab("SCNTB4")
TACTB1 = rom.tab("TACTB1")
TACTB2 = rom.tab("TACTB2")
LIVTAB = rom.tab("LIVTAB")
FUELT1 = rom.tab("FUELT1")
FUELT2 = rom.tab("FUELT2")
FUELT3 = rom.tab("FUELT3")
FUELT4 = rom.tab("FUELT4")
FUELT5 = rom.tab("FUELT5")

SCORE_X0 = 8            # leftmost digit; the six run at an 8-pixel pitch
SCORE_COLOUR = 0x1E

BOX_TOP = SCAN_TOP + 4  # the 16 scanner lines
BOX_ROWS = 16
GLYPH_LEFT = 44         # player 1, two copies wide -- 64 pixels apart
GLYPH_RIGHT = GLYPH_LEFT + 64
BLIP_X0 = 60            # XTABLE index 0; two pixels per step
STRIP_BACKGROUND = 0xF2
FUEL_ROWS = 5


def draw_score(mach, frame):
    """SCRKER.  Six glyphs, most significant on the left."""
    m = mach.m
    frame.fill_rows(SCORE_TOP, SCORE_TOP + SCORE_ROWS - 1, 0x00)
    pointers = (m[PNTR6], m[PNTR5], m[PNTR4], m[PNTR3], m[PNTR2], m[PNTR1])
    for i, offset in enumerate(pointers):
        for y in range(SCORE_ROWS):
            bits = rom.DATA[SCRTAB + ((offset + y) & 0xFF)]
            if isinstance(bits, int):
                frame.player(SCORE_TOP + (SCORE_ROWS - 1 - y),
                             SCORE_X0 + i * 8, bits, SCORE_COLOUR,
                             group=i & 1)
    for row in range(SCORE_TOP, SCORE_TOP + SCORE_ROWS):
        frame.end_scanline()


def draw_scanner(mach, frame):
    """SCANDS."""
    m = mach.m
    frame.fill_rows(SCAN_TOP, 191, STRIP_BACKGROUND)
    if m[PROGST] & PROGST_OVER:
        return                          # the title screen draws its own thing

    x = m[TARNUM]
    _scanner_box(m, frame, x)
    _lives_and_fuel(m, frame)


def _range_glyphs(m, x):
    """The two range digits, from the locked target's distance."""
    a = m[ZPOSP0 - 1 + x]
    if a >= 0x40:
        a = ((a + 0x3F + 1) >> 1) | 0x80    # ADC #$3F with C=1, then ROR
        a &= 0xFF
    return ((a >> 1) & 0x78), SCNTB1[a & 0x0F]


def _arrow_glyphs(m, x):
    """Which way the target lies: left/right and up/down, or X for dead ahead.

    Both are folded into the same 0..$14 index the blip position uses.
    """
    horiz = (m[HHORP0 - 1 + x] - m[CENTER] + 0x28) & 0xFF
    if horiz >= 0x50:
        horiz = 0x50 if horiz < 0xA8 else 0x00
    index = horiz >> 1
    if index == 0x13:
        left = 0x70 - 9                 # X: dead ahead
    elif index > 0x13:
        left = 0x68 - 9                 # right arrow
    else:
        left = 0x58 - 9                 # left arrow

    vert = ((m[HVERP0 - 1 + x] + 0x48) & 0xFF) >> 4
    if vert == 0x08:
        right = 0x70 - 9                # X: level
    elif vert > 0x08:
        right = 0x60 - 9                # up arrow
    else:
        right = 0x50 - 9                # down arrow
    return index, left, right, vert


def _scanner_box(m, frame, x):
    index, left, right, vert = _arrow_glyphs(m, x)
    digit_lo, digit_hi = _range_glyphs(m, x)

    cls = (m[HGRAP0 - 1 + x] & 0x78) >> 3
    icon_base = SCNTB2[cls]
    # ONESHT bit 6 means you are damaged, so the scanner colour flickers
    accent = m[RANDOM] if (m[ONESHT] & 0x40) else SCNTB4[cls]

    for y in range(BOX_ROWS - 1, -1, -1):
        row = BOX_TOP + (BOX_ROWS - 1 - y)
        priority = TACTB2[y]
        if priority & 0x80:
            # bit 7 flips the two glyphs from arrows to the range digits
            left, right = digit_lo, digit_hi
        frame.fill_row(row, accent if (priority & 0x80) else STRIP_BACKGROUND)

        # the box outline: PF1 is a constant $03 and PF2 comes from TACTB1
        frame.playfield(row, 0x00, 0x03, TACTB1[y], 0x00,
                        reflect=bool(priority & 0x01))

        icon = rom.DATA[CHTAB8 + ((icon_base - vert + y) & 0xFF)]
        mask = rom.DATA[MASKTB + 2 - vert + y]
        if isinstance(icon, int) and isinstance(mask, int):
            frame.player(row, BLIP_X0 + index * 2, icon & mask, 0x0E, group=0)

        for gx, offset in ((GLYPH_LEFT, left), (GLYPH_RIGHT, right)):
            bits = rom.DATA[SCRTAB + ((offset + y) & 0xFF)]
            if isinstance(bits, int):
                frame.player(row, gx, bits, 0xB8, group=1)
        frame.end_scanline()


def _lives_and_fuel(m, frame):
    """The lives icons and the fuel bar are one playfield line, then the word
    FUEL is spelled out by two players over five more."""
    fuel_scaled = m[FUEL] >> 3
    row = BOX_TOP + BOX_ROWS

    # LIVTAB turns the remaining-ship count into a playfield pattern; note the
    # kernel reads LIVTAB[LIVES] and LIVTAB[LIVES+1] into PF0 and PF1.
    lives = m[LIVES]
    frame.playfield(row, LIVTAB[lives], LIVTAB[lives + 1],
                    FUELT1[fuel_scaled >> 2], 0x0E, reflect=False)
    frame.end_scanline()

    # below $20 fuel the bar flashes in time with the frame counter
    low = 0 < m[FUEL] < 0x20
    bar_colour = 0xF2 if (low and (m[ATRACT] & 0x10)) else 0x1A

    for i in range(FUEL_ROWS):
        y = FUEL_ROWS - 1 - i
        r = row + 2 + i
        frame.fill_row(r, STRIP_BACKGROUND)
        frame.player(r, 24, FUELT3[y], 0x8E, group=0)
        frame.player(r, 32, FUELT4[y], 0x8E, group=0)
        frame.player(r, 40, FUELT2[y], 0x8E, group=1)
        frame.player(r, 56, FUELT5[y], bar_colour, group=0)
        frame.end_scanline()

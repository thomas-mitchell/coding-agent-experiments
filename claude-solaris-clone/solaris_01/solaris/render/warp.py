"""HYPER (asm:9419) -- the hyperwarp tunnel.

Your ship in the middle, a field of streaking stars, and a colour-cycling
background that SHPSRV computed from the throttle (SHPTB1) or, once the takeoff
clock is running, from SHPTB2.

The streaks are two star objects -- the ball and missile 0 -- given a fixed
HMOVE nudge every scanline (`HDELM2 = $70`, `HDELM0 = $50`, i.e. seven and five
pixels left per line).  They are switched on and off by bit 4 of LINTB4, which
is what breaks the two sweeps into dashes.  Under it, SHPSRV lifts your ship up
the screen and swaps in the smaller SHP4..SHP1 graphics as the jump builds.
"""

from .. import romdata as rom
from ..state import HCOLP1, HGRAP1, HHORP1, HVERP1, TOPSCN
from .frame import WIDTH
from .layout import PLAY_TOP, SCAN_TOP
from .sprites import named

LINTB4 = rom.tab("LINTB4")     # the tunnel's star pattern; only bit 4 matters
LINTB3 = rom.tab("LINTB3")     # the ship graphic per takeoff step
JOYTB9 = rom.tab("JOYTB9")     # ... and the three ordinary ship graphics

STAR_MASK = 0x10               # CROSP1, set to $10 by HYPER
STAR_SLOPE = (7, 5)            # HDELM2 and HDELM0, in pixels left per scanline
STAR_START = (0x70, 0x50)      # where HYPER first positions them
STAR_COLOUR = 0x0E

# SHPSRV stores `graphic_pointer - HVERP1` into HGRAP1, so adding the ship's Y
# back recovers the pointer and identifies the graphic exactly.
_SHIP_BY_LOW = {}
for _entry in [LINTB3[i] for i in range(8)] + [JOYTB9[i] for i in range(3)]:
    if not isinstance(_entry, int):
        _SHIP_BY_LOW[rom.low(_entry)] = _entry.name


def draw(mach, frame):
    background = getattr(mach, "takeoff_colour", None)
    if background is None:
        background = getattr(mach, "tunnel_colour", 0x00)
    frame.fill_rows(PLAY_TOP, SCAN_TOP - 1, background)

    _stars(mach, frame)
    _ship(mach, frame)

    for _ in range(PLAY_TOP, SCAN_TOP):
        frame.end_scanline()


def _stars(mach, frame):
    """The two sweeping streaks."""
    x = list(STAR_START)
    for row in range(PLAY_TOP, SCAN_TOP):
        game_y = TOPSCN - (row - PLAY_TOP)
        lit = LINTB4[game_y & 0x3F] & STAR_MASK
        for i, slope in enumerate(STAR_SLOPE):
            x[i] = (x[i] - slope) % WIDTH
            if lit:
                frame.missile(row, x[i], STAR_COLOUR, width=2 if i else 1)


def _ship(mach, frame):
    """Your ship, lifted up the screen by the takeoff clock."""
    m = mach.m
    pointer = (m[HGRAP1] + m[HVERP1]) & 0xFF
    label = _SHIP_BY_LOW.get(pointer, "YGR1")
    rows = named(label)
    # the ordinary ship graphics are anchored one line lower than the takeoff
    # ones, because JOYTB9 points two bytes past the block and LINTB3 only one
    anchor = 3 if label.startswith("YGR") else 2
    top = m[HVERP1] - anchor
    for k, bits in enumerate(rows):
        row = PLAY_TOP + (TOPSCN - (top - k))
        frame.player(row, m[HHORP1], bits, m[HCOLP1] or 0x0E, group=1)

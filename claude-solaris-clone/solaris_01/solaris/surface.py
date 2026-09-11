"""PLNSRV / TRNSRV / TRNHLP (asm:10547) -- per-frame surface setup.

PLNSRV first decides which surface we are on: PROGST bit 6 clear means space and
there is nothing to do; bit 3 then selects planet (set) or trench (clear).

Both pick the ground pattern, set the horizon, advance the ground scroll, and
choose the sky and ground colours.  The results are left where the display
kernel expects them, in bytes that mean something else the rest of the time:

    IQPATH-1    the ground pattern pointer
    XDELP0-1    the mountain colour
    YDELP0-1    the star probability
    ZDELP0-1    the background colour
    PNTR3+1     the object limit CLOSE uses (TEMP13)
    BOTSCN      the horizon scanline

During a planet BLOW-UP (SHIPST bit 6) it also drives the flashing colours, the
rumble queued on channel 0 and the occasional burst on channel 1.
"""

from . import byte as b
from . import romdata as rom
from .state import (ATRACT, BOTSCN, CENTER, CH0SHD, CH1PTR, GAMEST, HCOLP1,
                    HHORP1, IQWARP, MTNTOP, ONESHT, PLINES, PROGST,
                    PROGST_SURFACE, RANDOM, SHIPST, STARS, TEMP13, TRNTOP,
                    VWALL, XDELP0, YDELP0, ZDELP0, ZPOSP1)

PLANT1 = rom.tab("PLANT1")   # the planet colour, cycled on the frame counter
PTABL4 = rom.tab("PTABL4")   # throttle -> how often the blow-up bursts

J = rom.LABELS["AUDTAB"]
AUDEX6 = rom.LABELS["AUDEX6"] - J
AUDEXP = rom.LABELS["AUDEXP"] - J

SURTB3 = rom.LABELS["SURTB3"]
SURTB4 = rom.LABELS["SURTB4"]
SURTB5 = rom.LABELS["SURTB5"]
STARTB_LOW = rom.ADDR["STARTB"] & 0xFF

SKYCOL = 0x70        # your own planet's sky
ENEMY_SKY = 0x50     # everyone else's


def plnsrv(mach):
    """PLNSRV.  Does nothing at all in space."""
    m = mach.m
    if not (m[PROGST] & PROGST_SURFACE):
        return
    if not (m[PROGST] & 0x08):
        trnsrv(mach)
        return

    detail = _trnhlp(mach, top=MTNTOP, close_limit=0x56)
    mach.ground_pattern = SURTB4 if detail else SURTB3

    # PORTB bit 3 is the console COLOUR / BLACK-AND-WHITE switch
    if mach.portb & 0x08:
        m[XDELP0 - 1] = 0x00                     # mountain colour
        sky = SKYCOL if (m[GAMEST] & 0x40) else ENEMY_SKY
    else:
        m[XDELP0 - 1] = 0x02                     # black and white
        sky = 0x00

    if m[ONESHT] == 0x99:
        sky = (m[RANDOM] & 0x76) | 0x40          # the stars-end recolour
    m[ZDELP0 - 1] = sky
    mach.sky_colour = sky

    colour = PLANT1[m[ATRACT] & 0x03]
    stars = 0xC0
    if (m[SHIPST] & 0x40) and not (m[SHIPST] & 0x80):
        colour, stars = _blowup(mach, colour, stars)
    m[HCOLP1] = colour                           # the planet colour
    m[YDELP0 - 1] = stars                        # the star probability


def _blowup(mach, colour, stars):
    """The planet is blowing up under you."""
    m = mach.m
    y = m[IQWARP]
    if not (y & 0x80):
        return colour, stars
    flash, _ = b.lsr(m[ATRACT])
    colour, _ = b.adc(flash & 0x02, 0x40, c=False)
    if (m[ATRACT] & 0x07) == 0:
        v, _ = b.asl(PTABL4[y - 0xE0])
        if not (v & 0x80):
            m[CH1PTR] = AUDEX6                   # an occasional loud burst
    m[CH0SHD] = AUDEXP                           # and a constant rumble
    stars, _ = b.asl(y)
    return colour, stars


def trnsrv(mach):
    """TRNSRV: the trench.  Two moving walls whose gap is at VWALL."""
    m = mach.m
    mach.sky_colour = 0x00
    detail = _trnhlp(mach, top=TRNTOP, close_limit=(m[VWALL] - 2) & 0xFF)
    mach.ground_pattern = SURTB5 + 1 if detail else SURTB5

    # if the camera has drifted far from the trench centre and the far photon is
    # close, switch the photon off -- it would only have hit a wall
    off, _ = b.sbc(m[CENTER], 0x40, c=True)
    far, _ = b.cmp(off, 0x20)
    if far:
        close, _ = b.cmp(m[ZPOSP1 + 1], 0x16)
        if close:
            m[ZPOSP1 + 1] = 0x80


def _trnhlp(mach, top, close_limit):
    """TRNHLP: set the horizon, hand CLOSE its object limit, and advance the
    ground scroll.  Returns True when the high-detail pattern is due."""
    m = mach.m
    m[TEMP13] = close_limit                      # PNTR3+1, read by CLOSE
    m[BOTSCN] = top
    m[STARS] = (STARTB_LOW - 0x71) & 0xFF
    m[HHORP1 + 3] = 0x3A
    # `LDA IQWARP / CMP #$80 / ADC PLINES` -- the throttle itself is what
    # scrolls the ground, and the CMP just supplies its sign as the carry.
    carry, _ = b.cmp(m[IQWARP], 0x80)
    v, _ = b.adc(m[IQWARP], m[PLINES], carry)
    m[PLINES] = v
    scrolled, _ = b.asl(v)
    return bool(scrolled & 0x80)

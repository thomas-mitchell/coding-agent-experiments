"""MOVER (asm:10315) -- integrate every object once per frame, and stir the PRNG.

The first thing the frame loop calls.  For each of the five slots and each of
the three axes it does

    code      = delta & $1F
    delta    += MOVTBn[code]        (the sub-pixel accumulator)
    position += MOVTBn+1[code]      (the whole-pixel step, plus the carry)

so the packed velocity is never unpacked.  Clamps: Z holds at $F1 rather than
wrapping (an object that reached the camera stays there), and Y clamps at
$F1/$00 so nothing wraps off a screen edge.

Surface mode takes the shorter path: no Z clamp, no shared P1+3 slot, and the
vertical integration is done only for the planet photon, separately at the end.
"""

from . import byte as b
from . import romdata as rom
from .state import (ATRACT, BOTSCN, GAMTIM, HGRAP0, HHORP0, HVERP0, PNTR1,
                    PROGST, PROGST_SURFACE, RANDOM, TEMP4, TEMP5, TEMP11,
                    TEMP13, VWALL, XDELP0, YDELP0, ZDELP0, ZPOSP0)
from .vmath import MOVTB4, MOVTB5, MOVTB6, MOVTB7

GRATB5 = rom.tab("GRATB5")   # the animation phase source, sampled twice a frame

# `ADC $FE00,Y` (asm:10345) mixes in a byte of raw ROM from page $FE of the
# current bank as extra entropy.  Reproducing the exact bytes would mean
# assembling all four banks, which this port does not do -- so it uses 256 bytes
# of real Solaris bank-4 data instead.  It is the one place the port cannot be
# byte-exact without a ROM image; the assembly's own note says "any decent PRNG
# substitutes", and the mixing structure around it is reproduced exactly.
RNDPAGE = [v for v in rom.DATA if isinstance(v, int)][-256:]


def mover(mach):
    """MOVER.  `mach.rtimer` stands in for the RIOT timer value MAIN latched."""
    m = mach.m

    # RANDOM+1 is given a defined value here so the horizontal positioning code
    # has something to work with during a chart screen or a takeoff.
    m[RANDOM + 1] = 0x2B
    m[BOTSCN] = 0
    m[TEMP5] = 0      # the slot GRAPH should leave alone: none
    m[PNTR1] = 0      # GRAPH's running "nearest scanner target" distance
    mach.tia.clear()

    _stir_random(mach)
    _sample_animation_phase(m)

    m[VWALL] = 0x56   # default: no trench wall

    if m[PROGST] & 0xB3:
        # chart, game over, screen protect or a frozen pause: nothing moves
        return

    surface = bool(m[PROGST] & PROGST_SURFACE)
    x = 4
    while x >= 0:
        _move_x(m, x)
        a, carry = _step_z(m, x)

        if surface:
            m[ZPOSP0 - 1 + x] = a
            x -= 1
            if x == 0:
                _planet_photon_fix(m)
                return
            continue

        # An object that reached the camera is HELD at $F1 rather than wrapping.
        # Doug's own "H,V OOPS!" marks the exception: an object already flagged
        # off screen skips the store entirely and keeps its stale Z.
        held, _ = b.cmp(a, 0xF1)
        if not (held and not (m[HGRAP0 - 1 + x] & 0x80)):
            m[ZPOSP0 - 1 + x] = a

        _move_y(m, x)
        x -= 1


def _stir_random(mach):
    """The PRNG reseed.  Not an LFSR -- it mixes the frame counter, the game
    clock, its own previous value and a ROM byte, then increments."""
    m = mach.m
    y = m[ATRACT]
    a, c = b.adc(mach.rtimer, m[GAMTIM], c=False)
    a, c = b.adc(a, m[ATRACT], c)
    a, c = b.adc(a, m[RANDOM], c)
    a, c = b.adc(a, RNDPAGE[y], c)
    m[RANDOM] = a
    m.inc(RANDOM)


def _sample_animation_phase(m):
    """GRATB5 sampled at two different shifts of the frame counter becomes the
    three phase values GRAPH hands to its animation handlers.  Sharing one
    source is why every object of a class animates in step."""
    atract = m[ATRACT]
    x = atract >> 1
    a = GRATB5[(x >> 2) & 0x07]
    m[TEMP4] = a
    m[TEMP13] = (a << 4) & 0xFF
    m[TEMP11] = GRATB5[x & 0x07]


def _move_x(m, x):
    code = m[XDELP0 - 1 + x] & 0x1F
    v, c = b.adc(MOVTB6[code], m[XDELP0 - 1 + x], c=False)
    m[XDELP0 - 1 + x] = v
    v, _ = b.adc(MOVTB7[code], m[HHORP0 - 1 + x], c)
    m[HHORP0 - 1 + x] = v


def _step_z(m, x):
    """Z uses its own table pair because the depth scale differs.  Returns the
    new Z and the carry, so the caller can apply the clamp."""
    code = m[ZDELP0 - 1 + x] & 0x1F
    v, c = b.adc(MOVTB4[code], m[ZDELP0 - 1 + x], c=False)
    m[ZDELP0 - 1 + x] = v
    return b.adc(MOVTB5[code], m[ZPOSP0 - 1 + x], c)


def _move_y(m, x):
    code = m[YDELP0 - 1 + x] & 0x1F
    v, c = b.adc(MOVTB6[code], m[YDELP0 - 1 + x], c=False)
    m[YDELP0 - 1 + x] = v
    a, _ = b.adc(MOVTB7[code], m[HVERP0 - 1 + x], c)
    over, _ = b.cmp(a, 0xF1)
    if over:
        # wrapped: pin to whichever edge it came from
        a = 0xF0 if (m[HVERP0 - 1 + x] & 0x80) else 0x00
    m[HVERP0 - 1 + x] = a


def _planet_photon_fix(m):
    """MOVER3's tail: on a surface only the planet photon gets integrated
    vertically, and it is clamped to the top half of the byte."""
    code = m[YDELP0] & 0x1F
    v, c = b.adc(MOVTB6[code], m[YDELP0], c=False)
    m[YDELP0] = v
    a, _ = b.adc(MOVTB7[code], m[HVERP0], c)
    if a & 0x80:
        a = 0x00
    m[HVERP0] = a

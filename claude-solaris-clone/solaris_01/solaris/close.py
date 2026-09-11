"""CLOSE (asm:2959) -- vertical overlap resolution.

The companion to BRAIN's swap logic.  All five P0-class objects were drawn by
ONE hardware player, so they had to be vertically sorted and non-overlapping;
BRAIN reorders them, and CLOSE is what notices when they need reordering.

The invariant it maintains, for slots 1..4 walking upward:

    obj[i].y + height(obj[i]) <= obj[i+1].y

An object that would overlap the one above it has its Y pushed up to the
boundary; if that pushes it off the top of the screen the pair is marked for
exchange.  PNTRP1 is left holding the highest slot still on screen, which the
planet kernel uses as its object count.

REQUST, consumed by BRAIN next frame:
    bits 2..0   the slot index
    bit 6       graphic-aware exchange
    bit 7       forced exchange
Larger values win, so the most urgent request survives the frame.
"""

from . import byte as b
from . import romdata as rom
from .state import (GAMEST, HGRAP0, HGRAP1, HOLDM0, HVERP0, HVERP1, IQPNTR,
                    PBLK, PNTRP1, PROGST, PROGST_SURFACE, REQUST, TEMP4,
                    TEMP13, TOPSCN, YDELP0, ZDELP0, ZPOSP0, ZVIS)

BRNTB6 = rom.tab("BRNTB6")     # size and flags, space
BRNTB9 = rom.tab("BRNTB9")     # size and flags, surface
CLSTB1 = rom.tab("CLSTB1")     # slot index -> REQUST payload

W = rom.LABELS["TYPTAB"]
ATTSB1 = rom.LABELS["ATTSB1"] - W   # the "five in a row" attack script
CRATYP = rom.LABELS["CRATYP"] - W   # the crater script, used to abort an enemy planet


def close(mach):
    m = mach.m

    # A Y that wrapped past the top is the known jump-up bug; clamp it to 0.
    over, _ = b.cmp(m[HVERP0 + 0], 0xF3)
    if over:
        m[HVERP0 + 0] = 0

    m[REQUST] = 0
    m[PNTRP1] = 0

    y = m[HGRAP0 + 0] & 0x7F
    m[TEMP4] = BRNTB6[y]           # TEMP4 carries the PREVIOUS object's flags
    if m[TEMP4] == 0:
        m[HVERP0 + 0] = 0          # height 0 means the front slot is empty

    if m[PROGST] & PROGST_SURFACE:
        _surface_loop(m, y)
        return

    _shared_slot(m)
    _space_loop(m)


def _shared_slot(m):
    """The P1+3 slot (Saturn rings / big moon / warp graphic).  Clamp it so it
    never overlaps the far photon; a big moon that would is switched off."""
    y = m[HGRAP1 + 3] & 0x7F
    a = BRNTB6[y] & 0x3F
    m[HOLDM0] = a                  # handed on to HITSRV as the P1+3 height
    a, _ = b.adc(a, m[HVERP1 + 2], c=False)
    overlap, _ = b.cmp(a, m[HVERP1 + 3])
    if overlap:
        m[HVERP1 + 3] = a
        big_moon, _ = b.cmp(y, 0x40)
        if big_moon:
            m[HGRAP1 + 3] = PBLK


def _space_loop(m):
    """CLOSE1: walk the consecutive pairs (1,2), (2,3), (3,4)."""
    x = 1
    while x < 4:
        offscreen, _ = b.cmp(m[HVERP0 + x], TOPSCN)
        if offscreen:
            _offscreen_tail(m, x)
            return

        y = m[HGRAP0 + x] & 0x7F
        flags = BRNTB6[y]
        if flags == 0:
            _empty_gap(m, x, flags)
            x += 1
            continue

        a, _ = b.adc(flags & 0x3F, m[HVERP0 - 1 + x], c=False)
        clear, _ = b.cmp(a, m[HVERP0 + x])
        if not clear:
            m[TEMP4] = flags
            m[PNTRP1] = x
            x += 1
            continue

        m[HVERP0 + x] = a
        pushed_off, _ = b.cmp(a, TOPSCN)
        if pushed_off:
            _offscreen_tail(m, x)
            return

        if _request(m, x, flags):
            m[PNTRP1] = x
        m[TEMP4] = flags
        x += 1


def _request(m, x, flags):
    """The exchange-request decision.  Which style is needed depends on the flag
    bits of THIS object and of the previous one.  Returns False when the object
    was cleared outright instead (CLOS11), which skips the `STX PNTRP1`."""
    prev = m[TEMP4]

    if flags & 0x80:
        # CLOSE6: this class is top-anchored.  Do not bother swapping something
        # that is already off screen.
        if m[HGRAP0 + x] & 0x80:
            return True
        if prev & 0x80:
            _file(m, x, 0x40)
            return True
        if prev & 0x40:
            return True
        _forced_exchange(m, x)
        return True

    if prev & 0x80:
        # CLOS11: a downward-growing object that is also moving downward has
        # nowhere to go, so it is cleared rather than exchanged.
        if not (m[YDELP0 + x] & 0x10):
            return True
        m[HGRAP0 + x] = PBLK
        _empty_gap(m, x, flags)
        return False

    if flags & 0x40:
        _forced_exchange(m, x)
    return True


def _forced_exchange(m, x):
    """CLOSE7: clear the lower slot and file the top-priority request."""
    m[HGRAP0 - 1 + x] = PBLK
    _file(m, x, 0x80)


def _file(m, x, style):
    a = style | CLSTB1[x - 1]
    higher, _ = b.cmp(a, m[REQUST])
    if higher:
        m[REQUST] = a


def _empty_gap(m, x, flags):
    """CLOSE3: leave a 2-line gap below an empty slot so the kernel does not
    glitch, and carry the flags forward."""
    a, _ = b.adc(0x02, m[HVERP0 - 1 + x], c=False)
    m[HVERP0 + x] = a
    m[TEMP4] = flags


def _offscreen_tail(m, x):
    """CLOS10/CLOSE2: objects already off the top get pulled down onto their
    neighbour, with a low-priority exchange request."""
    a = m[HVERP0 + x]
    while x < 4:
        above, _ = b.cmp(a, m[HVERP0 - 1 + x])
        if not above:
            m[HVERP0 + x] = m[HVERP0 - 1 + x]
            if m[REQUST] == 0:
                m[REQUST] = CLSTB1[x - 1]
        x += 1
        if x < 4:
            a = m[HVERP0 + x]


def _surface_loop(m, y):
    """CLOS30/CLOS33.  A simpler body: objects sit on the horizon anyway, so the
    work is snapping them to a 2-line grid, clearing anything that has crowded
    the front of the screen, and keeping the same non-overlap invariant with
    BRNTB9's surface heights."""
    x = 1
    while True:
        if BRNTB9[y] & 0x20:
            # this class must sit on an even scanline: force even, then odd
            v, _ = b.lsr(m[HVERP0 - 1 + x])
            m[HVERP0 - 1 + x] = v
            v, _ = b.rol(m[HVERP0 - 1 + x], True)
            m[HVERP0 - 1 + x] = v

        if x == 4:
            return

        above_type = _surface_body(m, x)
        if above_type is not None:
            y = above_type
        # When the slot above is empty the assembly never reaches its TAY, so Y
        # -- and therefore the next even-scanline test -- keeps the PREVIOUS
        # object's type.  Preserved deliberately.
        x += 1


def _surface_body(m, x):
    """One slot of the surface loop.

    Returns the type byte of the object above, which the next iteration's
    even-scanline test uses -- or None when that slot is empty, because the
    assembly's `BEQ CLOS35` skips the TAY and leaves Y holding the previous
    object's type.
    """
    a, _ = b.adc(m[ZPOSP0 - 1 + x], 0x10, c=False)
    far, _ = b.cmp(a, 0x12)
    if not far:
        # crowded right at the camera: clear this slot, and raise the spawn
        # script's priority so something new comes in behind it
        cls = m[HGRAP0 - 1 + x] & 0x78
        script = ATTSB1
        if cls == 0x18 and not (m[GAMEST] & 0x40):
            script = CRATYP        # the man may not trigger the enemy-planet script
        if cls <= 0x18:
            higher, _ = b.cmp(script, m[IQPNTR])
            if not higher:
                m[IQPNTR] = script
        m[HGRAP0 - 1 + x] = PBLK

    above = m[HGRAP0 + x]
    if above == PBLK:
        a, _ = b.adc(m[HVERP0 - 1 + x], 0x01, c=True)
        y = None
        _push_up(m, x, a)
    else:
        y = above & 0x7F
        a, _ = b.adc(BRNTB9[y] & 0x1F, m[HVERP0 - 1 + x], c=False)
        clear, _ = b.cmp(a, m[HVERP0 + x])
        if clear:
            _push_up(m, x, a)

    # PNTRP1 tracks the highest slot inside the kernel's object limit
    within, _ = b.cmp(m[HVERP0 + x], m[TEMP13])
    if not within:
        m[PNTRP1] = x
    return y


def _push_up(m, x, a):
    """CLOS36: the object above is pushed up to the boundary and stopped from
    drifting down again.  The far photon is too near to be pushed, so it is left
    alone."""
    m[HVERP0 + x] = a
    if x == 0x03:
        too_near, _ = b.cmp(m[ZPOSP0 + 3], ZVIS - 1)
        if too_near:
            return
    m[ZDELP0 + x] = 0xFF

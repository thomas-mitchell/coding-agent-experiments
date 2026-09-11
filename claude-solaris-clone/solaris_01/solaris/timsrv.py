"""INIT and TIMSRV (asm:4729, 5048) -- reset, and the between-frames state machine.

TIMSRV owns everything that happens outside the picture:
  * the Game Reset switch
  * PAUTIM, the explosion pause -- and the two-stage timer that ends a life
  * the ship takeoff / landing state machine, which is where a finished
    hyperwarp turns into a new sector (DOOR)
  * "this sector is empty", which scores the cleared planet and moves the fleet
    marker off the chart
  * the ATRACT frame counter, and the screen-protect bit when it wraps

INIT is five nested entry points, coldest first:
  INIT    power on: zero everything, PROGST = $CE, four lives, build the chart
  INIT2   reset or select: the same, but PROGST comes from the caller
  INIT3   you died and the game is not over: full fuel, no damage, one life less
  INIT8   the game IS over: PROGST = $CA
  INIT4   a takeoff finished: rebuild the four slots from INTAB1 / INTAB2
  INIT5   the sector was empty: just tidy up and carry on
"""

from . import romdata as rom
from .score import addful, addsc3
from .smarts import door, door2, door24
from .state import (ATRACT, CENTER, CH0SHD, CH1SHD, CURSOR, FUEL, GAMEST,
                    HCOLP1, HGRAP0, HGRAP1, HHORP0, HVERP1, IQPATH,
                    IQPNTR, IQSTAK, IQWARP, JMPTIM, LIVES, MAZRAM, NEWATT,
                    NOCLER, ONESHT, PAUTIM, PBLK, PLINES, PROGST,
                    PROGST_GAMEOVER, PROGST_NEWGAME, PROGST_POWERUP, SHIPST,
                    VELOC, VSHIP, XDELP0, ZDELP0, ZPOSP0, ZPOSP1)

INTAB1 = rom.tab("INTAB1")   # the four starting distances after a takeoff
INTAB2 = rom.tab("INTAB2")   # ... and the four starting X positions
LD107 = rom.tab("LD107")     # fleet+1 -> its MAZRAM bit

W = rom.LABELS["TYPTAB"]
CRATYP = rom.LABELS["CRATYP"] - W
MONTYP = rom.LABELS["MONTYP"] - W


def init(mach):
    """INIT: cold start."""
    init2(mach, start=0x00, progst=PROGST_POWERUP)


def init2(mach, start, progst):
    """INIT2.  `start` is where the RAM sweep begins -- 0 on a cold start (which
    on hardware also walks the TIA registers), NOCLER on a warm one.

    Note that a warm start is very nearly a cold one anyway: everything INIT2
    goes on to write is exactly what the sweep would have preserved.
    """
    m = mach.m
    m.clear_from(start)
    m[PROGST] = progst

    m[JMPTIM] = 0x60
    m[CURSOR] = 0x15                 # your home sector
    m[LIVES] = 0x04
    door24(mach, 0x07)               # build the initial star chart
    init3(mach)


def init3(mach):
    """INIT3: you died, but the game is not over."""
    m = mach.m
    m[FUEL] = 0xFF
    m[ONESHT] = 0x00                 # clear all damage and every latch
    m[CENTER] = 0x50
    graphic = 0x40                   # craters are the default scenery
    x = VSHIP
    if m.dec(LIVES) == 0:
        x = 0x00
        init8(mach, x, graphic)
        return
    _init6(mach, x, graphic)


def init8(mach, x=VSHIP, graphic=0x40):
    """INIT8: the game is over."""
    mach.m[PROGST] = PROGST_GAMEOVER
    _init6(mach, x, graphic)


def _init6(mach, x, graphic):
    m = mach.m
    m[HVERP1] = x
    if m[PROGST] & 0x84:
        # The game always begins with you standing on your own friendly planet:
        # $CE, $CA and $4E all have one of these bits set.
        m[IQPNTR] = CRATYP
        m[GAMEST] = 0x40             # YOUR PLANET
        init4(mach, x, graphic)
        return
    _init7(mach)


def init4(mach, x, graphic):
    """INIT4: a takeoff finished, so rebuild the four object slots."""
    m = mach.m
    m[HVERP1] = x
    m[HGRAP1 + 3] = PBLK
    for i in range(3, -1, -1):
        m[XDELP0 + i] = 0
        m[ZDELP0 + i] = 0
        m[ZPOSP0 + i] = INTAB1[i]
        m[HHORP0 + i] = INTAB2[i]
        m[HGRAP0 + i] = graphic
    _init7(mach)


def _init7(mach):
    m = mach.m
    m[PLINES] = 0x58
    m[ZPOSP1] = 0x80                 # both photons off
    m[ZPOSP1 + 1] = 0x80
    init5(mach)


def init5(mach):
    """INIT5: the sector turned out to be empty."""
    m = mach.m
    # SHIPST $30 collapses to $20: a wormhole's "jump again" becomes a plain
    # queued jump.
    m[SHIPST] = ((m[SHIPST] & 0x10) << 1) & m[SHIPST]
    m[VELOC] = 0
    m[CH0SHD] = 0
    m[CH1SHD] = 0


# ---------------------------------------------------------------------------
# TIMSRV
# ---------------------------------------------------------------------------

def timsrv(mach):
    """TIMSRV.  Returns False when it restarted the game or otherwise consumed
    the frame, so the caller skips the rest of the overscan chain."""
    m = mach.m

    # GAME RESET.  The test is (ONESHT bit 1) XOR (PORTB bit 0), so the fire
    # button at game over restarts too -- PHOTON sets that latch.
    c = ((m[ONESHT] >> 1) ^ mach.portb) & 0x01
    if c == 0:
        init2(mach, start=NOCLER, progst=PROGST_NEWGAME)
        return False

    if m[PAUTIM] != 0:
        if m.dec(PAUTIM) == 0 and m[HVERP1] == 0:
            before = m[PROGST]
            m[PROGST] |= 0x02
            if m[PROGST] == before:
                init3(mach)          # the latch was already set: you really died
                return False
            m[PAUTIM] = 0x30         # otherwise hold the pause a little longer

    if m[SHIPST] & 0x80:
        if m[HCOLP1 + 1] == 0x70:
            _takeoff_done(mach)
            return False
    elif m[SHIPST] & 0x01:
        _sector_empty(mach)
        return False

    _atract(mach)
    return True


def _takeoff_done(mach):
    """The takeoff animation has finished, so work out where we arrived."""
    m = mach.m
    m[IQSTAK] = 0
    m[PROGST] = 0x00                 # back to the default in-space state
    m[GAMEST] = 0x00
    m[IQPNTR] = MONTYP               # the default empty-space script
    m[NEWATT] &= 0xF8

    x = 0xF2
    if m[SHIPST] != 0xB0:            # $B0 is a wormhole, which skips all of this
        if not (m[SHIPST] & 0x10):
            # a hyperwarp rather than a planet takeoff, so the JUMP QUALITY
            # SHPSRV left in IQPATH-1 decides how well we arrived
            m[GAMEST] = m[IQPATH - 1] & 0x03
            addful(mach, m[GAMEST] ^ 0xFF)     # a bad jump costs fuel
            door(mach)
        x = 0xE1                     # the throttle a new sector starts at
    timsr7(mach, x)


def timsr7(mach, x=0xE1):
    """TIMSR7.  Also HITSRV's entry when you land on a trench entrance."""
    m = mach.m
    m[IQWARP] = x
    init4(mach, VSHIP, PBLK)


def _sector_empty(mach):
    """SHIPST bit 0: this sector is now clear."""
    m = mach.m
    if m[SHIPST] & 0x20:
        addsc3(mach, 0x08, 1)        # a cleared planet or trench is worth 8000

    x = m[NEWATT] & 0x07
    m[MAZRAM] ^= LD107[x]            # clear that fleet from the chart

    t = m[NEWATT]
    rolled = ((t << 1) | (t >> 7)) & 0xFF
    rolled = ((rolled << 1) | (rolled >> 7)) & 0xFF
    rolled = ((rolled << 1) | (rolled >> 7)) & 0xFF
    if ((rolled ^ t) & 0x07) == 0:
        m[NEWATT] = 0
    else:
        m[NEWATT] = t & 0xC0

    door2(mach)                      # recompute the chart, maybe a new level
    init5(mach)


def _atract(mach):
    """TIMSR9: advance the frame counter, and turn on screen protect when the
    full 16-bit counter wraps -- about 18 minutes of no input."""
    m = mach.m
    before = m[PROGST]
    if m.inc(ATRACT) == 0:
        if m.inc(ATRACT + 1) == 0:
            m[PROGST] = before | 0x01

    if m[PROGST] & 0x93:
        m[IQWARP] = 0                # nothing moves on the title or chart

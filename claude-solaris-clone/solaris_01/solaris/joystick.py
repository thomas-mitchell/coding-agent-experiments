"""JOYSTK, SHPSRV and PHOTON (asm:7737, 8066, 8200) -- everything you control.

Your ship never actually moves in space: JOYSTK moves the CAMERA (CENTER,
clamped $2D..$74) and leaves JOYRMH/JOYRMV behind as "how much the world slides
this frame because you steered", which BRAIN then adds into every object.  Once
the camera hits a clamp the starfield scrolls instead, so steering keeps feeling
like motion at the edges.

Carry is load-bearing here.  `INC IQWARP / BCC ... / DEC IQWARP` does NOT
re-test the increment -- INC leaves the carry alone, so the branch is really
testing the carry from the CMP several instructions earlier.  That is what makes
the throttle settle at $F9 in space and back off above $FC, and it is
reproduced exactly rather than rewritten as a clamp.
"""

from . import byte as b
from . import romdata as rom
from .state import (ATRACT, CENTER, CH0PTR, CH1PTR, FUEL, GAMEST, HCOLP1,
                    HGRAP1, HHORM2, HHORP1, HOLDM0, HOLDM2, HPOSL, HVERP1,
                    IQPATH, IQREAP, IQWARP, JOYRMH, JOYRMV, MAZSTA, NEWAVE,
                    ONESHT, PAUTIM, PBLK, PLINES, PROGST, PROGST_SURFACE,
                    RANDOM, SHIPST, STARS, TARNUM, TEMP12, THGRP1, VECTP1,
                    VELOC, VSHIP, ZDELP0, ZPOSP1, YDELP0)

JOYTB1 = rom.tab("JOYTB1")   # starfield X step, by vertical stick bits
JOYTB2 = rom.tab("JOYTB2")   # ... and its wrap amount
JOYTB3 = rom.tab("JOYTB3")   # star pattern pointer step
JOYTB4 = rom.tab("JOYTB4")   # camera step
JOYTB5 = rom.tab("JOYTB5")   # starfield step once the camera is clamped
JOYTB6 = rom.tab("JOYTB6")   # ... and its wrap
JOYTB7 = rom.tab("JOYTB7")   # star pattern pointer wrap
JOYTB8 = rom.tab("JOYTB8")   # ship X offset per bank angle
JOYTB9 = rom.tab("JOYTB9")   # ship graphic per bank angle
JOYT11 = rom.tab("JOYT11")   # world vertical drift
JOYT12 = rom.tab("JOYT12")   # world horizontal drift at a camera clamp
JOYT13 = rom.tab("JOYT13")   # surface throttle clamp
JOYT14 = rom.tab("JOYT14")   # velocity forced at a camera clamp
SHPTB1 = rom.tab("SHPTB1")   # hyperwarp tunnel background ramp
SHPTB2 = rom.tab("SHPTB2")   # takeoff background ramp
SHPTB4 = rom.tab("SHPTB4")   # late-takeoff colour flicker
SHPTB5 = rom.tab("SHPTB5")   # per-difficulty hyperwarp camera drift
LINTB3 = rom.tab("LINTB3")   # ship graphic during takeoff
LINTB5 = rom.tab("LINTB5")   # ship colour during takeoff
PHOTB1 = rom.tab("PHOTB1")
PHOTB3 = rom.tab("PHOTB3")   # minimum vertical gap between your two shots
ZOOMTB = rom.tab("ZOOMTB")

J = rom.LABELS["AUDTAB"]
AUDTAK = rom.LABELS["AUDTAK"] - J
AUDPHN = rom.LABELS["AUDPHN"] - J

# The starfield pattern pointer lives in the ROM's own address space; STARTB's
# real address is known, so the wrap comparisons work on the same numbers the
# hardware used.
STARTB_LOW = rom.ADDR["STARTB"] & 0xFF

CENTER_MIN = 0x2D
CENTER_MAX = 0x74


def joystk(mach):
    """JOYSTK (asm:7737)."""
    m = mach.m
    m[JOYRMH] = 0
    m[JOYRMV] = 0

    a = mach.porta
    if a != 0xFF:
        m[ATRACT + 1] = 0                    # any input resets the attract timer
        m[PROGST] = (m[PROGST] >> 1 << 1) & 0xFF   # LSR/ASL clears bit 0
    if not (m[MAZSTA] & 0x80):
        a ^= 0xFF                            # NEGATIVE UNIVERSE reverses everything
    m[TEMP12] = a
    y = (a >> 4) & 0x03                      # the two vertical bits

    if m[PROGST] & 0xB3:
        return                               # chart, hyperwarp, frozen, game over
    if m[ATRACT] & 0x07:
        _vertical(mach, y)                   # the throttle moves once every 8 frames
    elif _throttle(mach, y):
        return                               # a hyperwarp was committed
    else:
        m[JOYRMV] = JOYT11[y]
    _horizontal(mach)


def _throttle(mach, y):
    """The speed section.  Returns True when it committed a hyperwarp, which
    ends the frame's input handling."""
    m = mach.m
    x = m[IQWARP]
    if not (x & 0x80):
        m.dec(IQWARP)                        # JOYS31: positive means coasting down
        m[JOYRMV] = JOYT11[y]
        return False

    armed = m[SHIPST] & 0x30
    if armed:
        ready, _ = b.cmp(x, 0xE0)
        if ready:
            m.dec(IQWARP)
            m[JOYRMV] = JOYT11[y]
            return False
        if not (armed & 0x10):
            tunnel, _ = b.cmp(x, 0xD9)
            if tunnel:
                m.dec(IQWARP)
                m[JOYRMV] = JOYT11[y]
                return False
            # COMMIT THE HYPERWARP: the two photons become the tunnel stars
            m[PROGST] = 0x10
            m[ZDELP0 + 1] = 0x28
            m[ZDELP0] = 0x30
            m[YDELP0] = 0x4B
            m[YDELP0 + 1] = 0x49
            m[CH0PTR] = AUDTAK
        m[CH1PTR] = AUDTAK
        m[IQWARP] = 0x05
        m[HCOLP1 + 1] = 0x00                 # the takeoff animation clock starts
        m[SHIPST] |= 0x80
        return True

    _speed_notch(mach, x)
    m[JOYRMV] = JOYT11[y]
    return False


def _speed_notch(mach, x):
    """JOYS40: one notch of throttle, with the carry threaded through the INC
    exactly as the assembly leaves it."""
    m = mach.m
    carry, _ = b.cmp(x, 0xF1)
    if not carry:
        _bump(m, carry=False)                # still slow: always speed up
        return

    step = (m[GAMEST] & 0x1C) >> 2
    total, carry = b.adc(step, m[IQWARP], c=False)
    if carry:
        m.dec(IQWARP)                        # JOYS31
        return
    x = total

    carry, _ = b.cmp(x, 0xF4)
    if not carry:
        _bump(m, carry=False)
        return
    carry, _ = b.cmp(x, 0xFC)
    if carry:
        _bump(m, carry=True)                 # above $FC the throttle backs off
        return

    if m[PROGST] & PROGST_SURFACE:
        y = (m[TEMP12] >> 4) & 0x03
        v, carry = b.asl(JOYT13[y])
        if v != 0:
            _bump(m, carry)                  # holding the stick clamps the speed
            return
    carry, zero = b.cmp(x, 0xF9)
    if zero:
        return                               # the hold point
    _bump(m, carry)


def _bump(m, carry):
    """JOYS32: `INC IQWARP / BCC done / DEC IQWARP` then falling into JOYS31's
    second DEC.  INC does not touch the carry, so a set carry on entry turns a
    speed-up into a net slow-down."""
    m.inc(IQWARP)
    if carry:
        m.dec(IQWARP)
        m.dec(IQWARP)


def _vertical(mach, y):
    """JOYS77: scroll the starfield, then hand BRAIN the world's vertical drift."""
    m = mach.m
    if m[ATRACT] & 0x01:                     # odd frames only
        h, carry = b.adc(m[HHORM2], JOYTB1[y], c=False)
        if carry or h >= 0xA0:
            h, _ = b.sbc(h, JOYTB2[y], c=True)
        m[HHORM2] = h

        s, _ = b.adc(m[STARS], JOYTB3[y], c=False)
        wrapped, _ = b.cmp(s, (STARTB_LOW + 2) & 0xFF)
        m[STARS] = rom.low(JOYTB7[y]) if wrapped else s
    m[JOYRMV] = JOYT11[y]


def _horizontal(mach):
    """JOYSTK's horizontal section (asm:7862).

    The bank angle and the camera step use DIFFERENT index registers: `LDX #$01`
    at JOYST7 overwrites the bank index with one derived from the sign of your
    velocity, so JOYTB4/JOYTB5 are indexed by which way you are drifting, not by
    which way you are pushing.
    """
    m = mach.m
    raw = m[TEMP12]
    x = 1
    m[THGRP1] = 1
    y = m[VELOC]

    if raw & 0x80 and not (raw & 0x40):
        # RIGHT
        if y == 0x1F:
            _camera(mach, x, carry=True)     # already at maximum: CPY set Z and C
            return
        y = (y + 1) & 0xFF
        m[HCOLP1] = 0x4E
    elif raw & 0x40 and not (raw & 0x80):
        # LEFT
        x = 2
        if y == 0xE0:
            _settle(mach, x, y)
            return
        y = (y - 1) & 0xFF
        m[HCOLP1] = 0x4E
    else:
        # NULL: decay toward zero.  Note this shares JOYST3/JOYST5 with the
        # thrusting cases, so the engine flame flashes while decaying too.
        x = 0
        if y & 0x80:
            y = (y + 1) & 0xFF
            m[HCOLP1] = 0x4E
        elif y != 0:
            y = (y - 1) & 0xFF
            m[HCOLP1] = 0x4E

    _settle(mach, x, y)


def _settle(mach, bank, velocity):
    """JOYST7: commit the bank angle and speed, then accumulate the sub-pixel
    remainder; its carry is the camera's whole-pixel step."""
    m = mach.m
    m[THGRP1] = bank
    m[VELOC] = velocity

    x = 1 if not (velocity & 0x80) else 2
    acc, carry = b.adc(m[HPOSL], (velocity << 3) & 0xFF, c=False)
    m[HPOSL] = acc
    _camera(mach, x, carry)


def _camera(mach, x, carry):
    """JOYS11: step CENTER, or fall through to the clamp behaviour."""
    m = mach.m
    new, _ = b.adc(JOYTB4[x - 1], m[CENTER], carry)
    high, _ = b.cmp(new, CENTER_MAX)
    low, _ = b.cmp(new, CENTER_MIN)
    if not high and low:
        m[CENTER] = new
        return
    _clamped(mach, x)


def _clamped(mach, x):
    """JOYST9: the camera is against a clamp, so scroll the starfield instead --
    which is what makes the world feel wider than the camera's range."""
    m = mach.m
    h, _ = b.adc(m[HHORM2], JOYTB5[x - 1], c=False)
    wrapped, _ = b.cmp(h, 0xA0)
    if wrapped:
        h = JOYTB6[x - 1]
    m[HHORM2] = h

    if m[THGRP1] == 0:
        return
    # drifting against the direction you are banking: kill the residual speed
    m[VELOC] = 0x00 if x != m[THGRP1] else JOYT14[x - 1]
    if m[PROGST] == PROGST_SURFACE:
        return                               # in the trench the world never slides
    m[JOYRMH] = JOYT12[x - 1]


# ---------------------------------------------------------------------------
# SHPSRV -- your ship's graphic, position and the hyperwarp tunnel
# ---------------------------------------------------------------------------

def shpsrv(mach):
    """SHPSRV (asm:8066)."""
    m = mach.m
    if m[SHIPST] & 0x80:
        _takeoff(mach)
        return
    if m[SHIPST] == 0x20:
        a = _warp_cursor(mach)
    else:
        a = m[CENTER]
    _place_ship(mach, a)


def _warp_cursor(mach):
    """The hyperwarp is armed: show the jump cursor, work out the jump QUALITY
    from how far the camera has drifted from centre, and drift it some more."""
    m = mach.m
    m[TARNUM] = 0x05
    m[IQREAP] = PBLK
    m[PLINES] = 0x50

    x = 0xFF
    a, carry = b.sbc(0x50, m[CENTER], c=False)
    if not carry:
        x = 0x01
        a = b.neg(a)
    a >>= 1
    over, _ = b.cmp(a, 0x04)
    if over:
        x = 0x00
        a = 0x03
    m[IQPATH - 1] = a                        # the displayed jump quality, 0..3

    _, c = b.lsr(m[ATRACT] >> 2)
    t, carry = b.rol(m[IQWARP], c)
    t, carry = b.sbc(t, 0xAE, carry)
    inrange, _ = b.cmp(t, 0x31)
    if not inrange:
        idx = min(t, 0x0F)
        mach.tunnel_colour = SHPTB1[idx]     # COLBK for the hyperwarp renderer
        drift, _ = b.cmp(m[RANDOM], SHPTB5[m[NEWAVE]])
        if not drift:
            v, _ = b.adc(x, m[CENTER], c=False)
            m[CENTER] = v
    return 0x50 if (m[ATRACT] & 0x01) else m[CENTER]


def _place_ship(mach, a):
    """SHPS20: the ship follows the camera, offset a little by its bank angle."""
    m = mach.m
    x = m[THGRP1]
    m[RANDOM + 1] = a                        # "HOLD CENTER" for the fine positioning
    v, _ = b.adc(a, JOYTB8[x], c=False)
    m[HHORP1] = v
    _bias_graphic(m, rom.low(JOYTB9[x]))


def _bias_graphic(m, pointer):
    """SHPSR5: pre-bias the graphic pointer by the ship's Y so the kernel can
    index straight into the sprite."""
    v, _ = b.sbc(pointer, m[HVERP1], c=True)
    m[HGRAP1] = v


def _takeoff(mach):
    """SHPSR1: the takeoff / hyperwarp animation.  HCOLP1+1 is the clock, and
    TIMSRV ends the sequence when it reaches $70."""
    m = mach.m
    y = m[HCOLP1 + 1]
    if m[PROGST] & PROGST_SURFACE:
        early, _ = b.cmp(y, 0x13)
        if not early:
            m.inc(HVERP1)                    # planet takeoffs need one extra line

    colour = SHPTB4[m[RANDOM] & 0x03]
    late, _ = b.cmp(y, 0x20)
    if not late:
        colour = SHPTB2[y]
    mach.takeoff_colour = colour
    m[ZDELP0 - 1] = colour                   # HOLD BAK COLOR
    m[HCOLP1] = 0x4A

    lift = (m[HOLDM0] >> 4) & 0x07
    v, _ = b.adc(lift, m[HVERP1], c=False)
    m[HVERP1] = v

    step = min(y >> 2, 0x07)
    m.inc(HCOLP1 + 1)
    v, _ = b.sbc(rom.low(LINTB5[step]), m[HVERP1], c=True)
    m[ATRACT + 1] = v                        # SHIP COLOR PNTR
    _bias_graphic(m, rom.low(LINTB3[step]))


# ---------------------------------------------------------------------------
# PHOTON -- fire and advance your torpedoes
# ---------------------------------------------------------------------------

def photon(mach):
    """PHOTON (asm:8200).  Two shots may be in flight: a near one (P1+1) and a
    far one (P1+2).  Firing loads the near slot; once the near shot is far
    enough it is TRANSFERRED to the far slot, freeing the near one again.

    ONESHT bit 7 is the button's release latch, so holding fire does not
    auto-fire, and bit 2 alternates so only every OTHER shot costs fuel.
    """
    m = mach.m
    if m[SHIPST] & 0x80:
        return                               # the ship RAM is in use during takeoff

    trig = mach.trig0
    handled = False
    if not (trig & 0x80):
        m[ATRACT + 1] = 0                    # any press clears the attract timer
        if m[ONESHT] & 0x80:                 # ... but only on the button's edge
            if m[PROGST] & 0x80:
                # PHOT55: game over, so the button asks TIMSRV for a restart
                if m[PAUTIM] == 0:
                    m[ONESHT] |= 0x02
            elif m[HVERP1] != 0:
                before = m[PROGST]
                m[PROGST] = before & 0xF8
                if m[PROGST] == before:      # the press did not merely unfreeze
                    handled = _fire(mach)

    if not handled:
        _latch(m, trig)
    _advance(m)


def _fire(mach):
    """PHOT44 / PHOT56.  Returns True when the press was consumed."""
    m = mach.m
    if not (m[ZPOSP1] & 0x80):
        # the near slot is busy; push it along if the far one has room
        room, _ = b.cmp(m[ZPOSP1 + 1], 0x31)
        if room:
            _transfer(m)
        return True

    m[CH0PTR] = AUDPHN
    m[ZPOSP1] = 0x00                         # switch the near photon on
    a = (m[ONESHT] & 0x7F) ^ 0x04            # clear the fire latch, flip bit 2
    m[ONESHT] = a
    a &= 0x04
    if a and m[FUEL] != 0:
        m.dec(FUEL)                          # only every OTHER shot costs fuel
    v, _ = b.adc(a, m[CENTER], c=True)
    m[HOLDM2] = v                            # the muzzle X, jittering by four
    m[HVERP1 + 1] = VSHIP + 0x09
    return True


def _latch(m, trig):
    """PHOTN5: shift the button state into ONESHT bit 7, then transfer a near
    shot that has travelled far enough."""
    v, _ = b.asl(m[ONESHT])
    m[ONESHT] = v
    _, carry = b.asl(trig)
    v, _ = b.ror(m[ONESHT], carry)
    m[ONESHT] = v

    if m[ZPOSP1] & 0x80:
        return
    far_enough, _ = b.cmp(m[ZPOSP1], 0x09)
    if not far_enough:
        return
    if not (m[ZPOSP1 + 1] & 0x80):
        return
    _transfer(m)


def _transfer(m):
    m[ZPOSP1 + 1] = m[ZPOSP1]
    m[HVERP1 + 2] = m[HVERP1 + 1]
    m[HHORP1 + 2] = m[HHORP1 + 1]
    m[ZPOSP1] = 0x80                         # free the near slot


def _advance(m):
    """PHOTN1: both shots recede one step, rise up the screen by an amount the
    zoom table gives, and pick the graphic for their new distance."""
    m[HCOLP1 + 1] = 0x08
    y = 0x08
    for x in (1, 2):
        z = m[ZPOSP1 - 1 + x]
        if z & 0x80:
            # switched off, but the muzzle still needs somewhere to be
            a = m[HVERP1 - 1 + x] or VSHIP
            v, _ = b.adc(a, 0x06, c=False)
            m[HVERP1 + x] = v
            y = 0x08
        else:
            rise = (m[VECTP1 - 1 + x] & 0x70) >> 4
            v, _ = b.adc(rise, m[HVERP1 + x], c=False)
            m[HVERP1 + x] = v
            m.inc(ZPOSP1 - 1 + x)
            step = z >> 2
            far, _ = b.cmp(step, 0x08)
            if far:
                y = 0x07                     # the smallest graphic
            else:
                m[HCOLP1 + 1] = 0x0E         # close shots get the bright colour
                y = step
        v, _ = b.sbc(rom.low(PHOTB1[y]), m[HVERP1 + x], c=True)
        m[HGRAP1 + x] = v

    _spacing(m, y)


def _spacing(m, y):
    """PHOT80: keep the two shots from merging, and retire the far one once it
    has climbed past maximum range."""
    a, carry = b.sbc(m[HVERP1 + 2], PHOTB3[y], c=True)
    clear, _ = b.cmp(a, m[HVERP1 + 1])
    if clear:
        return
    m.inc(HVERP1 + 2)                        # too close: push the far one up
    m.dec(HGRAP1 + 2)                        # and keep its graphic pointer in step

    limit = 0x4B if (m[PROGST] & PROGST_SURFACE) else 0x4D
    reached, _ = b.cmp(m[HVERP1 + 1], limit)
    if not reached:
        return
    if m[ZPOSP1] & 0x80:
        return
    m[ZPOSP1 + 1] = 0x80

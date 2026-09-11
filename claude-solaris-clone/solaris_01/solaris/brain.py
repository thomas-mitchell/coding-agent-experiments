"""BRAIN (asm:1508) -- per-object AI, one object per frame.

Three separate jobs share one routine:

  1. SERVICE THE PENDING SWAP REQUEST that CLOSE filed.  The display kernel can
     only draw obj[1..4] in increasing screen Y with no overlap, so when two
     objects cross, CLOSE files a request and BRAIN performs the exchange.
  2. DECIDE WHETHER AN ENEMY FIRES, on one frame in sixteen.
  3. RUN THE AI FOR EXACTLY ONE OBJECT, chosen by the low two bits of the frame
     counter -- so each slot is serviced every fourth frame.  That four-frame
     round robin is why enemies in Solaris steer in a slightly laggy, stepped
     way; reproducing it is what makes the motion feel right.

The generic ship handler is the interesting one.  obj.path's low nibble selects
a row in BRNTB1/BRNTB2/BRNTB3, which give a target Z, a target Y and a target X
plus per-axis speed limits -- that triple IS the flight path.  The high nibble
is a phase counter; when it overflows the path either advances or is re-rolled.
Each axis then runs DIVIDE -> PREHLP/ZHELP -> POSTHP to slew toward the target.
"""

from . import byte as b
from . import romdata as rom
from .state import (ATRACT, CENTER, CH1PTR, GAMEST, GAMTIM, HGRAP0, HGRAP1,
                    HHORP0, HVERP0, HVERP1, IQPATH, IQWARP, JOYRMH, JOYRMV,
                    NEWAVE, PAUTIM, PBLK, PNTR1, PROGST, PROGST_SURFACE,
                    RANDOM, REQUST, SHIPST, TEMP4, TEMP5, TEMP7, TEMP10,
                    TEMP12, TEMP13, TOPSCN, VCENT, XDELP0, YDELP0,
                    ZDELP0, ZPOSP0, ZPOSP1)
from .vmath import (divide, exchn1, exchng, posth1, posthp, prehl5, prehlp,
                    zhelp, zhelp1, zhelp2)

BRNTB1 = rom.tab("BRNTB1")   # path -> target Z (low nibble the Z speed limit)
BRNTB2 = rom.tab("BRNTB2")   # path -> target Y, bit 0 the X response curve
BRNTB3 = rom.tab("BRNTB3")   # path -> target X (low nibble the X speed limit)
BRNTB4 = rom.tab("BRNTB4")   # class -> AI handler
BRNTB6 = rom.tab("BRNTB6")   # size and flags, space
BRNTB8 = rom.tab("BRNTB8")   # fixed closing speeds at maximum throttle
BRNTB9 = rom.tab("BRNTB9")   # size and flags, surface
BRNT10 = rom.tab("BRNT10")   # difficulty -> how far an enemy leads its shot
BRNT11 = rom.tab("BRNT11")   # class -> first path row
BRNT12 = rom.tab("BRNT12")   # class -> base path value when re-rolling
BRNT13 = rom.tab("BRNT13")   # class -> random mask (negative = retire it)
BRNT14 = rom.tab("BRNT14")   # sign to apply to a photon's drift
BRNT15 = rom.tab("BRNT15")   # difficulty -> minimum range at which enemies fire
BRNT16 = rom.tab("BRNT16")   # difficulty -> warper timing bias
BRNT17 = rom.tab("BRNT17")   # difficulty -> maximum closing speed
SWAPT1 = rom.tab("SWAPT1")
SWAPT2 = rom.tab("SWAPT2")   # slot -> the LOW Y bound of its band
SWAPT3 = rom.tab("SWAPT3")   # slot -> the HIGH Y bound
SWAPT4 = rom.tab("SWAPT4")   # slot -> the partner when it is above the band
SWAPT5 = rom.tab("SWAPT5")   # slot -> the partner when it is below
ZOOMTB = rom.tab("ZOOMTB")

PH6 = rom.LABELS["PH6"] - rom.LABELS["BRNTB1"]   # the horizontal warpers
AUDSHT = rom.LABELS["AUDSHT"] - rom.LABELS["AUDTAB"]


def brain(mach, spawn):
    """BRAIN.  `spawn` is NEWOBJ, called when the AI finds an empty slot."""
    m = mach.m
    if m[PROGST] & 0x30:
        return                       # the chart and hyperwarp screens skip all AI

    if not (m[PROGST] & PROGST_SURFACE) and m[REQUST]:
        if _service_request(mach, m[REQUST]):
            return
    _phase_work(mach, spawn)


# ---------------------------------------------------------------------------
# 1. the swap request
# ---------------------------------------------------------------------------

def _service_request(mach, request):
    """Returns True when the request consumed the whole frame."""
    m = mach.m
    x = request & 0x07
    if request & 0x80:
        _forced_swap(m, x)
        return True
    if request & 0x40:
        return _graphic_swap(m, x)

    # simple exchange: nudge this object up two lines and swap it with the one
    # above, using the no-vertical-exchange variant so the nudge sticks
    v, _ = b.sbc(m[HVERP0 - 1 + x], 0x02, c=True)
    m[HVERP0 - 1 + x] = v
    exchn1(m, x + 1)
    return True


def _forced_swap(m, x):
    """BRAN17: push the object down and exchange unconditionally."""
    y = x
    x += 1
    m[YDELP0 - 1 + x] = 0x18
    _swap(m, x, y)


def _graphic_swap(m, x):
    """BRAN19.  Returns True if it consumed the frame, False to carry on into
    the phase-gated work."""
    a = m[HGRAP0 - 1 + x]
    if a & 0x80:
        # already off screen: push it below its neighbour and swap outright
        v, _ = b.adc(m[HVERP0 + x], 0x03, c=False)
        m[HVERP0 - 1 + x] = v
        exchng(m, x + 1)
        return True

    y = a & 0x7F
    if (a & 0x78) == 0x38:
        return False                 # explosions play out in place
    if ZOOMTB[y] & 0x80:
        return False                 # already double size: too big to reorder
    height, _ = b.adc(BRNTB6[y] & 0x3F, m[HVERP1 + 2], c=False)
    too_low, _ = b.cmp(height, m[HVERP0 - 1 + x])
    if too_low:
        # BRAN10: cosmetic tidy-up of the far photon after a crossing
        near, _ = b.cmp(m[ZPOSP1 + 1], 0x20)
        if near:
            m[ZPOSP1 + 1] = 0x80
        return False
    if m[HGRAP1 + 3] != PBLK:
        return False                 # the shared slot is in use; leave well alone

    slow, _ = b.cmp(m[YDELP0 + 1 + x], 0x10)
    if not slow:
        m[YDELP0 + 1 + x] = 0x1A     # push the neighbour down...
    m[ZDELP0 - 1 + x] = 0x01
    m[YDELP0 - 1 + x] = 0x08         # ...and this one up, so they separate
    _swap(m, x, 0)
    _forced_swap(m, x)
    return True


# ---------------------------------------------------------------------------
# 2. the phase-gated work
# ---------------------------------------------------------------------------

def _phase_work(mach, spawn):
    m = mach.m
    if m[PROGST] & 0x83:
        return                       # game over, frozen, or dimmed

    phase = m[ATRACT] & 0x0F
    if phase == 0:
        if not (m[PROGST] & PROGST_SURFACE) and m[HVERP0] == 0:
            _rotate_down(m)
            return
        _one_object(mach, phase, spawn)
        return
    if phase != 0x03:
        _one_object(mach, phase, spawn)
        return
    _maybe_fire(mach, spawn)


def _rotate_down(m):
    """The bottom object has fallen off, so shuffle everything down one slot and
    open a fresh empty slot at the top."""
    for x in (2, 3, 4):
        exchng(m, x)
    m[HVERP0 + 3] = 0xEF             # above the top, so GRAPH retires it


def _rotate_up(m):
    for x in (4, 3, 2):
        exchng(m, x)
    m[HVERP0] = 0x01


def _maybe_fire(mach, spawn):
    """The nearest enemy fires at you if it is close enough, you are alive, and
    the front slot is not already an explosion."""
    m = mach.m
    if m[HVERP1] == 0:
        _rotate_check(mach, spawn)
        return
    z = m[ZPOSP0]
    far, _ = b.cmp(z, 0x50)
    in_range, _ = b.cmp(z, BRNT15[m[NEWAVE]])
    if far or not in_range or (m[HGRAP0] & 0x80):
        _rotate_check(mach, spawn)
        return

    m[TEMP13] = z
    y = m[HGRAP0]
    if m[PROGST] & PROGST_SURFACE:
        m[TEMP13] >>= 1              # the surface view is compressed
        flags = BRNTB9[y]
        v, _ = b.adc(flags & 0x1F, 0x03, c=True)
        m[TEMP4] = v
        if not (flags & 0x40):
            _rotate_check(mach, spawn)
            return
        speed = 0x15
    else:
        flags = BRNTB6[y]
        allowed, _ = b.cmp(flags, 0xC0)
        m[TEMP4] = flags & 0x3F
        if not allowed:
            _rotate_check(mach, spawn)
            return
        band, _ = b.sbc(m[HVERP0], 0x30, c=True)
        outside, _ = b.cmp(band, 0x28)
        if outside:
            _rotate_check(mach, spawn)
            return
        speed = 0x18
    m[TEMP12] = speed
    _fire(mach, spawn)


def _fire(mach, spawn):
    """BRAN51: make room by swapping the front slots down, then build the
    photon in slot 1 and aim it."""
    m = mach.m
    x, y = 3, 4
    if not (m[HGRAP0 + 3] & 0x40):
        if not (m[HGRAP0 + 2] & 0x40):
            _rotate_check(mach, spawn)
            return
        x, y = 2, 3

    while True:
        _swap(m, x, y)
        y -= 1
        x -= 1
        if x == 0:
            break

    m[HGRAP0] = 0x37                 # the enemy photon graphic
    m[ZDELP0] = m[TEMP12]
    m[YDELP0] = 0x00

    sign_index = 0
    a, carry = b.sbc(m[CENTER], m[HHORP0], c=True)
    if not carry:
        a = b.neg(a)
        sign_index = 1
    a >>= 3
    y = 0x0F
    while True:
        a, _ = b.adc(a, 0x02, c=False)
        reaches, _ = b.cmp(a, m[TEMP13])
        if reaches:
            break
        y -= 1
        if y == 0:
            break
    y += 1
    a = y
    capped, _ = b.cmp(a, BRNT10[m[NEWAVE]])
    if capped:
        a = BRNT10[m[NEWAVE]]
    m[XDELP0] = a ^ BRNT14[sign_index]

    v, carry = b.sbc(m[HVERP0 + 1], m[TEMP4], c=True)
    v, _ = b.adc(v, 0x03, c=True)
    m[HVERP0] = v
    lsound(m, AUDSHT)
    _rotate_check(mach, spawn)


def lsound(m, offset):
    """LSOUND: request a sound on channel 1, but only if it is idle."""
    if (m[CH1PTR] >> 1) == 0:
        m[CH1PTR] = offset


def _rotate_check(mach, spawn):
    """BRAN64: if the top object has run off the top, shuffle everything up.

    Note the `LDA #$03` at the top: reaching here always services slot 4 next,
    whatever the frame phase was -- unless an explosion pause diverts it.
    """
    m = mach.m
    a = 0x03
    gone, _ = b.cmp(m[HVERP0 + 3], 0xF0)
    if gone:
        if m[PAUTIM] == 0:
            _rotate_up(m)
            return
        a = m[PAUTIM]                # do not rotate while an explosion freezes
    _one_object(mach, a, spawn)


# ---------------------------------------------------------------------------
# 3. the AI for one object
# ---------------------------------------------------------------------------

def _one_object(mach, a, spawn):
    """BRAN70.  The slot is 1 + (a & 3), so each is serviced every fourth frame."""
    m = mach.m
    x = (a & 0x03) + 1

    # Prepare the perspective-divide inputs every handler shares.
    sign = 0xFF
    z = m[ZPOSP0 - 1 + x] >> 2
    m[TEMP4] = z
    scaled = 0x00
    if z < 0x10:
        v, carry = b.asl(m[ZDELP0 - 1 + x])
        v, c2 = b.asl(v)
        v, c3 = b.asl(v)
        v, c4 = b.asl(v)
        if c4:
            sign = 0x00
            v ^= 0xF0
        scaled = 0x70 if (v & 0x80) else v
    m[TEMP5] = scaled
    m[PNTR1] = sign

    cls = (m[HGRAP0 - 1 + x] & 0x78) >> 2
    surface = bool(m[PROGST] & PROGST_SURFACE)
    y = cls + (1 if surface else 0)
    handler = BRNTB4[y].name

    if m[SHIPST] & 0x30:
        # a takeoff or hyperwarp is armed
        if not (m[HGRAP0 - 1 + x] & 0x80):
            _wander_path(m, x, y)    # still on screen: let it drift
            _HANDLERS[handler](mach, x, surface, spawn)
            return
        # off screen: blank the slot so it does not fight the animation
        m[HGRAP0 - 1 + x] = PBLK

    # classes at or below $27 are the visible enemies
    in_view, _ = b.cmp(0x27, m[HGRAP0 - 1 + x])
    if m[GAMEST] & 0x80:
        if not in_view:
            _wander_path(m, x, y)    # wandering, and still out of sight
            _HANDLERS[handler](mach, x, surface, spawn)
            return
        m[GAMEST] &= 0x7F            # it came into view, so stop wandering
    _normal_path(m, x, y)
    _HANDLERS[handler](mach, x, surface, spawn)


def _wander_path(m, x, y):
    """BRAN47: an invisible or wandering object gets a pseudo-random path index,
    mixed with the game clock so the drift changes over time."""
    m[TEMP13] = (y ^ m[GAMTIM]) & 0x03


def _normal_path(m, x, y):
    m[TEMP13] = ((m[IQPATH - 1 + x] & 0x07) + BRNT11[y]) & 0xFF


# --- the handlers ----------------------------------------------------------

def _bran36(mach, x, surface, spawn):
    """Enemy photon: no horizontal steering, only vertical tracking."""
    mach.m[JOYRMV] = 0x00
    _vertical(mach, x, spawn)


def _bran31(mach, x, surface, spawn):
    """Blockader: drifts sideways away from the camera, faster with difficulty."""
    m = mach.m
    if m[ZPOSP0 - 1 + x] == 0:
        lsound(m, AUDSHT)
    a, _ = b.adc(m[NEWAVE], 0x03, c=False)
    away, _ = b.cmp(m[HHORP0 - 1 + x], m[CENTER])
    if not away:
        a = b.neg(a)
    _bran15(mach, x, surface, spawn, a)


def _bran15(mach, x, surface, spawn, drift=0x00):
    """Scenery: it does not chase you.  It closes at a rate derived from the
    throttle and slides sideways under perspective."""
    m = mach.m
    m[JOYRMH] = drift

    a = m[IQWARP]
    carry, _ = b.cmp(a, 0x80)
    a, _ = b.ror(a, carry)
    a, _ = b.sbc(a, 0x02, c=True)
    top, _ = b.cmp(a, 0xF7)
    if top:
        m[TEMP5] = BRNTB8[a - 0xF7]  # the fixed speeds at maximum throttle
    zhelp2(m, a)
    v, _ = posth1(m, m[ZDELP0 - 1 + x])
    m[ZDELP0 - 1 + x] = v

    off, _ = b.sbc(m[HHORP0 - 1 + x], m[CENTER], c=True)
    _horizontal(mach, x, divide(m, off, m[TEMP4], m[TEMP5], m[PNTR1]), spawn)


def _horizontal(mach, x, drift, spawn):
    """BRAN35: perspective drift plus your own motion, packed and slewed."""
    m = mach.m
    a, _ = b.adc(drift, m[JOYRMH], c=False)
    prehl5(m, a)
    v, _ = posth1(m, m[XDELP0 - 1 + x])
    m[XDELP0 - 1 + x] = v
    _vertical(mach, x, spawn)


def _vertical(mach, x, spawn):
    """BRAN38: converge on the vertical vanishing point."""
    m = mach.m
    off, _ = b.sbc(m[HVERP0 - 1 + x], VCENT, c=True)
    a = divide(m, off, m[TEMP4], m[TEMP5], m[PNTR1])
    a, _ = b.adc(a, m[JOYRMV], c=False)
    prehl5(m, a)
    v, _ = posth1(m, m[YDELP0 - 1 + x])
    m[YDELP0 - 1 + x] = v
    _swap_logic(mach, x, spawn)


def _bran30(mach, x, surface, spawn):
    """An empty slot: zero every velocity, then fall into the swap logic, which
    is what actually calls the spawner."""
    m = mach.m
    m[ZDELP0 - 1 + x] = 0x00
    m[XDELP0 - 1 + x] = 0x00
    m[YDELP0 - 1 + x] = 0x00
    _swap_logic(mach, x, spawn)


def _bran42(mach, x, surface, spawn):
    """The warp graphic is decorative and driven by SHPSRV."""
    _swap_logic(mach, x, spawn)


def _brn100(mach, x, surface, spawn):
    """Trench tower: clear the phase counter so it never re-rolls its path."""
    m = mach.m
    m[IQPATH - 1 + x] &= 0xE0
    _bran32(mach, x, surface, spawn)


def _bran32(mach, x, surface, spawn):
    """Planet / terrain: closes at the throttle speed and, in the trench, steers
    toward a lane derived from its path byte."""
    m = mach.m
    zhelp1(m, x, m[IQWARP])
    v, _ = posth1(m, m[ZDELP0 - 1 + x])
    m[ZDELP0 - 1 + x] = v

    if m[PROGST] != 0x40:
        _horizontal(mach, x, 0x00, spawn)
        return

    m[TEMP10] = 0x00
    limit, carry = b.sbc(0xF9, m[IQWARP], c=True)
    m[TEMP7] = limit                 # maximum lateral speed falls as speed rises
    a = 0x4C                         # the centre lane
    if carry:
        near, _ = b.cmp(m[ZPOSP0 - 1 + x], 0x54)
        if not near:
            a, _ = b.adc(m[IQPATH - 1 + x] >> 2, 0x2B, c=False)
    _steer_to(mach, x, a, spawn)


def _brain9(mach, x, surface, spawn):
    """Darter: below graphic $14 it is still warping in, so it does not steer."""
    m = mach.m
    warping, _ = b.cmp(m[HGRAP0 - 1 + x], 0x14)
    if not warping:
        _swap_logic(mach, x, spawn)
        return
    _bran11(mach, x, surface, spawn)


def _bran11(mach, x, surface, spawn):
    """The generic enemy ship: path bookkeeping, then three axes of steering."""
    m = mach.m
    if m[PROGST] == 0x40:
        _brn100(mach, x, surface, spawn)   # in the trench, ships are terrain
        return

    _path_phase(m, x)
    _close_z(m, x)
    _steer_x(mach, x, spawn)


def _path_phase(m, x):
    """Add $10 to the phase nibble every other frame; on overflow either advance
    the path or roll a new one, as BRNTB1 bit 0 says.

    Every $F0 frames the gate is forced open so all the objects re-sync and do
    not gradually drift out of step with each other.
    """
    y = m[TEMP13]
    gate = m[ATRACT] & 0xFC
    resync = (gate == 0xF0)
    if not resync and (gate & 0x04):
        return                       # only every other frame

    a = ((gate & 0x04) | m[IQPATH - 1 + x]) & 0xFF
    a, carry = b.adc(a, 0x10, c=False)
    m[IQPATH - 1 + x] = a
    if not carry:
        return                       # the phase nibble did not overflow

    _, advance = b.lsr(BRNTB1[y])
    if advance:
        # step the path index on by the amount in BRNT12's high nibble
        a, _ = b.adc(BRNT12[y] & 0xF0, m[IQPATH - 1 + x], c=True)
    else:
        # BRAN74: re-roll.  A negative mask means retire the object instead --
        # that is how the darter removes itself.
        mask = BRNT13[y]
        if mask & 0x80:
            m[HGRAP0 - 1 + x] = mask
            return
        a = (mask & m[RANDOM]) | BRNT12[y]
        if y == PH6:
            a, _ = b.sbc(a, BRNT16[m[NEWAVE]], c=True)   # the warpers
    m[IQPATH - 1 + x] = a


def _close_z(m, x):
    """The Z axis: slew the closing speed toward the path's target distance."""
    v, _ = b.adc(m[IQWARP], 0x07, c=False)
    m[TEMP10] = v
    y = m[TEMP13]
    target = BRNTB1[y]
    m[TEMP7] = target & 0x0F
    if not (target & 0x80):
        capped, _ = b.cmp(target, BRNT17[m[NEWAVE]])
        if capped:
            target = BRNT17[m[NEWAVE]]
    err, _ = b.sbc(target, m[ZPOSP0 - 1 + x], c=True)
    zhelp(m, x, err)
    # two POSTHP calls in a row is the type 2 response: double acceleration
    v, _ = posthp(m, m[ZDELP0 - 1 + x], carry=True)
    v, _ = posthp(m, v, carry=True)
    m[ZDELP0 - 1 + x] = v

    # FROM BEHIND KLUDGE FIX: an object that wrapped past the camera is
    # teleported to whichever side is further away, so it does not appear to
    # fly through you.
    if (v & 0x1F) >= 0x10:
        return
    wrapped, _ = b.cmp(m[ZPOSP0 - 1 + x], 0xF8)
    if not wrapped:
        return
    right, _ = b.cmp(m[HHORP0 - 1 + x], 0x50)
    m[HHORP0 - 1 + x] = 0xA0 if right else 0x00


def _steer_x(mach, x, spawn):
    """The X axis: perspective drift, your own motion counted twice, then the
    path's target X."""
    m = mach.m
    off, _ = b.sbc(m[HHORP0 - 1 + x], m[CENTER], c=True)
    a = divide(m, off, m[TEMP4], m[TEMP5], m[PNTR1])
    a, _ = b.adc(a, m[JOYRMH], c=False)
    a, _ = b.adc(a, m[JOYRMH], c=False)   # deliberately twice
    m[TEMP10] = a

    y = m[TEMP13]
    m[TEMP12] = BRNTB2[y]
    m[TEMP7] = BRNTB3[y] & 0x0F

    warper, _ = b.cmp(y, PH6)
    if warper:
        mirror = m[RANDOM] & 0x20    # warpers pick their side at random
        carry = True                 # ... and always steer relative to the camera
    else:
        # bit 0 of the target-X byte decides camera-relative vs fixed-screen
        _, carry = b.lsr(BRNTB3[y] & 0x0F)
        mirror = 0xFF if (m[IQPATH - 1 + x] & 0x08) else 0x00

    a = mirror ^ BRNTB3[y]
    if carry:
        a, _ = b.adc(a, m[CENTER], c=False)     # mirrored: relative to the camera
    else:
        a, _ = b.adc(a, 0x50, c=False)          # otherwise a fixed screen position
    _steer_to(mach, x, a, spawn)


def _steer_to(mach, x, target, spawn):
    """BRAN21: the shared "A = the target X" tail, used by terrain too.

    The assembly bails out here if the frame timer is nearly expired, because
    the routine is long enough to overrun the display.  The port has no beam to
    race, so it always steers -- which is what the hardware does on all but the
    tightest frames.
    """
    m = mach.m
    err, _ = b.sbc(target, m[HHORP0 - 1 + x], c=True)
    prehlp(m, err)
    curve, _ = b.lsr(m[TEMP12])
    m[TEMP12] = curve
    v, _ = posthp(m, m[XDELP0 - 1 + x], carry=curve)
    m[XDELP0 - 1 + x] = v
    _steer_y(mach, x, spawn)


def _steer_y(mach, x, spawn):
    """The Y axis: the same pipeline, against the path's target Y."""
    m = mach.m
    off, _ = b.sbc(m[HVERP0 - 1 + x], VCENT, c=True)
    a = divide(m, off, m[TEMP4], m[TEMP5], m[PNTR1])
    a, _ = b.adc(a, m[JOYRMV], c=False)
    a, _ = b.adc(a, m[JOYRMV], c=False)   # "TWICE WHY?" -- Doug's own note
    m[TEMP10] = a

    target, _ = b.asl(m[TEMP12])
    m[TEMP7] = target & 0x0F
    err, _ = b.sbc(target, m[HVERP0 - 1 + x], c=True)
    prehlp(m, err)
    # during an explosion pause the gentle response curve is used instead
    curve, _ = b.cmp(m[PAUTIM], 0x01)
    v, _ = posthp(m, m[YDELP0 - 1 + x], carry=curve)
    m[YDELP0 - 1 + x] = v
    _swap_logic(mach, x, spawn)


_HANDLERS = {
    "BRAN11": _bran11, "BRAIN9": _brain9, "BRAN32": _bran32, "BRAN31": _bran31,
    "BRN100": _brn100, "BRAN36": _bran36, "BRAN30": _bran30, "BRAN15": _bran15,
    "BRAN42": _bran42,
}


# ---------------------------------------------------------------------------
# The swap logic -- and the hook that calls the spawner
# ---------------------------------------------------------------------------

def _swap_logic(mach, x, spawn):
    """BRAN46 (asm:2180).  Keeps obj[1..4] sorted by screen Y with no overlap.

    This exists only because the kernel reuses one hardware player for all five
    P0 objects, but it is load-bearing gameplay: it is what makes enemies
    visibly shuffle past each other, and it is where an empty slot gets filled.
    """
    m = mach.m
    if m[HGRAP0 - 1 + x] != PBLK:
        _occupied(mach, x)
        return
    _empty(mach, x, spawn)


def _empty(mach, x, spawn):
    """BRN105: an empty slot.  Whether something may spawn here depends on the
    shared P1+3 object."""
    m = mach.m
    y = m[HGRAP1 + 3]
    if not (y & 0x80):
        _empty_onscreen(mach, x, y, spawn)
        return
    if y != PBLK:
        # BRAN26: P1+3 has run off the top, so cascade every slot upward
        if m[HVERP1 + 3] < TOPSCN:
            return
        while x != 4:
            _swap(m, x + 1, x)
            x += 1
        _mark_top(m, x)
        return
    spawn(mach, x)


def _empty_onscreen(mach, x, y, spawn):
    """BRAN24: check a new object would actually fit between P1+3 and this slot."""
    m = mach.m
    big, _ = b.cmp(y, 0x48)
    if big:
        spawn(mach, x)               # Saturn and the big moons always fit
        return

    # Doug's note "NO LOAD P0+0 BUG": this reads HVERP0-2,X where HVERP0+0,X was
    # surely meant.  It shipped that way, so it stays.
    height, carry = b.adc(BRNTB6[y] & 0x3F, m[HVERP0 - 2 + x], c=False)
    if carry:
        return                       # "OOPS LOOK OUT!" -- overflowed the screen
    over, _ = b.cmp(height, m[HVERP1 + 3])
    if over:
        return
    if x >= 4:
        _mark_top(m, x)
        return

    y2 = m[HGRAP0 + x] & 0x7F
    stacked, carry = b.adc(BRNTB6[y2] & 0x3F, m[HVERP1 + 3], c=False)
    room, _ = b.cmp(stacked, m[HVERP0 + x])
    if not room:
        _mark_top(m, x)              # two empty slots in a row: safe to cascade
        return
    if m[HGRAP0 - 2 + x] != PBLK:
        return
    _swap(m, x + 1, x)


def _mark_top(m, x):
    """BRAN85: mark the top of the chain so GRAPH retires it."""
    m[YDELP0 - 1] = 0x80
    _swap(m, 0, x)


def _occupied(mach, x):
    """BRAN23: has this object crossed a neighbour and need exchanging?

    SWAPT2/SWAPT3 give the band of screen Y each slot is allowed to occupy, and
    SWAPT4/SWAPT5 name the partner to swap with above or below it.
    """
    m = mach.m
    y = SWAPT5[x - 1]
    if m[PROGST] & PROGST_SURFACE:
        distant, _ = b.cmp(m[ZPOSP0 - 1 + x], 0x77)
        if distant:
            return
        if m[HGRAP0 - 1 + y] == PBLK:
            _swap(m, x, y)
        return

    v = m[HVERP0 - 1 + x]
    below, _ = b.cmp(v, SWAPT2[x - 1])
    if not below:
        _try_swap(m, x, y)
        return
    inside, _ = b.cmp(v, SWAPT3[x - 1])
    if not inside:
        return                       # inside its band: nothing to do

    if x != 0x01:
        # single-scanline jitter fix: recompute with the real object height so
        # something exactly one line out does not oscillate
        flags = BRNTB6[m[HGRAP0 - 1 + x] & 0x7F]
        if flags & 0x80:
            h, _ = b.adc(flags & 0x3F, 0x01, c=True)
            h, _ = b.adc(h, m[HVERP0 - 2 + x], c=False)
            settled, _ = b.cmp(h, m[HVERP0 - 1 + x])
            if settled:
                return
    _try_swap(m, x, SWAPT4[x - 1])


def _try_swap(m, x, y):
    """BRAN28: the partner must be empty, or at least safe to exchange with."""
    partner = m[HGRAP0 - 1 + y]
    if partner == PBLK:
        _swap(m, x, y)
        return
    if SWAPT1[y - 1] != 0:
        return                       # slots 1 and 4 are special; leave them
    if BRNTB6[partner & 0x7F] >= 0x40:
        return                       # too big to swap without looking wrong
    _swap(m, x, y)


def _swap(m, x, y):
    """BRAN22: move every field of obj[x] into obj[y], leaving obj[x] empty.

    Note this is NOT an exchange -- obj[x] becomes PBLK rather than receiving
    obj[y]'s old contents.
    """
    for field in (HGRAP0, ZDELP0, XDELP0, YDELP0, IQPATH, HHORP0, ZPOSP0, HVERP0):
        m[field - 1 + y] = m[field - 1 + x]
        if field is HGRAP0:
            m[field - 1 + x] = PBLK

"""GRAPH (asm:2416) -- animation frame selection, off-screen culling, collision X.

Runs over all five slots (X = 4 down to 0).  For each object:

  1. Decide whether it is still visible.  Not visible means ZPOS >= ZVIS, or
     Y >= TOPSCN, or X outside 4..$9B.  Invisible objects shrink to their
     smallest graphic, or retire to PBLK once past POFF.
  2. Pick the ANIMATION FRAME: distance (ZPOS >> 2, clamped to $13) run through
     a per-class handler chosen from GRATB6.
  3. Compute HHITP0, the X used for collision, because the visible sprite is not
     centred on the logical X.
  4. Track TARNUM, the slot the scanner locks onto: the nearest object of a
     class below $40, i.e. a real ship rather than scenery.

It also does two motion nudges that logically belong to the AI but are cheaper
here: a downward vector nudge in space, and forcing the low path bits on in
surface mode.

The assembly sets the V flag ONCE at the top of the loop and every handler
relies on it still meaning "surface mode" ("WARNING DONT REDEFINE V FLAG",
line 2426).  Here that is an explicit `surface` argument.
"""

from . import byte as b
from . import romdata as rom
from .state import (ATRACT, CH0SHD, EXPNTR, GAMEST, HGRAP0, HGRAP1, HHITP0,
                    HHORP0, HHORP1, HVERP0, HVERP1, IQPATH, PAUTIM, PBLK,
                    PNTR1, PNTR3, POFF, PROGST, PROGST_SURFACE, TARNUM, TEMP4,
                    TEMP5, TEMP7, TEMP11, TEMP12, TEMP13, TOPSCN,
                    VWALL, XDELP0, YDELP0, ZPOSP0, ZVIS)

BRNTB6 = rom.tab("BRNTB6")   # size and flags, SPACE mode
BRNTB9 = rom.tab("BRNTB9")   # size and flags, SURFACE mode
GRATB1 = rom.tab("GRATB1")   # distance -> frame for static scenery
GRATB2 = rom.tab("GRATB2")   # distance -> frame for planet photons
GRATB3 = rom.tab("GRATB3")   # per-class collision-X nudge, classes $40 and up
GRATB4 = rom.tab("GRATB4")   # distance -> frame for ships
GRATB6 = rom.tab("GRATB6")   # class -> animation handler
SURTB2 = rom.tab("SURTB2")   # distance -> the horizon line an object sits on
EXPTAB = rom.tab("EXPTAB")   # the four explosion scripts
EXPOFF = rom.tab("EXPOFF")   # explosion frame -> horizontal offset

EXPREG = rom.LABELS["EXPREG"] - rom.LABELS["EXPTAB"]   # the standard explosion
AUDVAR = rom.LABELS["AUDVAR"] - rom.LABELS["AUDTAB"]   # the darter's own sound


def graph(mach, entry_x=1):
    """GRAPH.  `entry_x` is the value X has on entry (1 normally, from HYPSRV)."""
    m = mach.m
    m[TARNUM] = entry_x                     # default scanner target
    surface = bool(m[PROGST] & PROGST_SURFACE)

    for x in range(4, -1, -1):
        _pre_nudge(m, x, surface)
        _one_object(mach, x, surface)


def _pre_nudge(m, x, surface):
    """GRAPH1/GRAPH3: the two cheap motion effects done here rather than in BRAIN."""
    carry, _ = b.cmp(x, m[TEMP5])
    if carry or x == 0:                     # the caller's reserved slot, and slot 0
        return
    if surface:
        # pin terrain to its lane by forcing the two low path bits on
        m[IQPATH - 1 + x] |= 0x03
        return
    # space: nudge YDEL downward a notch so free-floating objects sink
    a = m[YDELP0 - 1 + x] ^ 0x1F
    carry, _ = b.cmp(a, m[YDELP0 - 1 + x])
    if carry:
        m[YDELP0 - 1 + x] = a


def _one_object(mach, x, surface):
    m = mach.m
    a = m[HGRAP0 - 1 + x]
    if a == PBLK:
        _commit(m, x, PBLK, surface)
        return

    a &= 0x7F                               # strip the off-screen bit
    z = m[ZPOSP0 - 1 + x]
    if a < 0x40:
        # classes below $40 are ships, so they are valid scanner targets
        carry, _ = b.cmp(z, m[PNTR1])
        if carry:
            m[PNTR1] = z
            m[TARNUM] = x

    if not _visible(m, x, z, surface):
        # GRAPH6: shrink to the smallest size, or retire the slot entirely
        a |= 0x87
        past_end, _ = b.cmp(a, POFF)
        _commit(m, x, PBLK if (past_end or surface) else a, surface)
        return

    m[HGRAP0 - 1 + x] = a
    m[TEMP7] = a & 0x78                     # the class bits, restored by the tail
    handler = GRATB6[((a & 0x78) >> 2) + (1 if surface else 0)]

    if surface:
        m[TEMP12] = SURTB2[z]               # the horizon line this object sits on
        frame = z >> 1
    else:
        frame = z
    frame >>= 1
    if frame > 0x13:
        frame = 0x13                        # 20 animation steps maximum

    _HANDLERS[handler.name](mach, x, frame, surface)


def _visible(m, x, z, surface):
    """GRAPH5's visibility test."""
    carry, _ = b.cmp(z, ZVIS)
    if carry:
        return False
    carry, _ = b.cmp(m[HVERP0 - 1 + x], TOPSCN)
    if carry:
        return False
    hx = m[HHORP0 - 1 + x]
    carry, _ = b.cmp(hx, 0x04)              # the margin is a big-moon fix
    if not carry:
        return False
    carry, _ = b.cmp(hx, 0x9C)
    return not carry


def _commit(m, x, value, surface):
    """GRAPH4: write the type byte, then park a surface object on the horizon so
    it reappears correctly when it comes back into range."""
    m[HGRAP0 - 1 + x] = value
    if surface:
        z = m[ZPOSP0 - 1 + x]
        carry, _ = b.cmp(z, ZVIS)
        if carry:
            z = ZVIS - 1
        m[HVERP0 - 1 + x] = SURTB2[z]


# ---------------------------------------------------------------------------
# The per-class animation handlers, dispatched through GRATB6.
# Every one of them ends by calling _frame() or _set_type().
# ---------------------------------------------------------------------------

def _frame(mach, x, a, surface):
    """GRAP42: low 3 bits are the new frame, reattach the class bits."""
    _set_type(mach, x, (a & 0x07) | mach.m[TEMP7], surface)


def _set_type(mach, x, a, surface):
    """GRAP43: commit the type byte and compute the collision X.

    On a surface the object is first pinned to the horizon line GRAPH worked out
    from its distance; in space it is left where it is.
    """
    m = mach.m
    m[HGRAP0 - 1 + x] = a
    if surface:
        m[HVERP0 - 1 + x] = m[TEMP12]
        _collision_x_surface(m, x)
    else:
        _collision_x_space(m, x, a)


def _set_type_explosion(mach, x, a, surface):
    """GRAP51: the explosion entry.  It commits the type but skips the horizon
    pin, and in space takes its horizontal offset from EXPOFF rather than the
    sprite width."""
    m = mach.m
    sprite = a & 0x07
    m[HGRAP0 - 1 + x] = a
    if surface:
        _collision_x_surface(m, x)
    else:
        _grap53(m, x, EXPOFF[sprite])


def _collision_x_surface(m, x):
    """GRAP52: classes $40 and up take a signed nudge from GRATB3; below that,
    bit 7 of the BRNTB9 flags means a fixed -4 and anything else means none."""
    y = m[HGRAP0 - 1 + x]
    carry, _ = b.cmp(y, 0x40)
    if carry:
        _grap53(m, x, GRATB3[y - 0x40])
    else:
        _grap55(m, x, BRNTB9[y])


def _collision_x_space(m, x, a):
    """GRAP97: in space the nudge scales with the sprite width at this distance,
    so it comes from ZOOMTB.  Slot 0 is the shared P1+3 object, which has no
    collision X of its own."""
    if x == 0:
        return
    _grap55(m, x, _ZOOMTB[a])


def _grap55(m, x, v):
    """`AND #$80 / BEQ / LDA #$FC` -- the nudge is either -4 or nothing."""
    _grap53(m, x, 0xFC if (v & 0x80) else 0x00)


def _grap53(m, x, nudge):
    a, _ = b.adc(nudge, m[HHORP0 - 1 + x], c=False)
    over, _ = b.cmp(a, 0xA0)
    m[HHITP0 - 1 + x] = 0x00 if over else a   # wrapped past the right edge


_ZOOMTB = rom.tab("ZOOMTB")


def _grap20(mach, x, frame, surface):
    """Saturn rings.  Drawn in the shared P1+3 slot, so copy the position over
    and switch off once it reaches the top."""
    m = mach.m
    a = m[HGRAP1 + 3] & 0x7F
    carry, _ = b.cmp(a, 0x48)
    if carry:
        m[HGRAP1 + 3] = 0x48
        m[HHORP1 + 3] = m[HHORP0 - 1 + x]
        m[ZPOSP0 - 1] = m[ZPOSP0 - 1 + x]
        v, _ = b.sbc(m[HVERP0 - 1 + x], 0x01)
        m[HVERP1 + 3] = v
        gone, _ = b.cmp(v, TOPSCN - 3)
        if gone:
            _commit(m, x, PBLK, surface)
            return
    _grap36(mach, x, frame, surface)


def _grap23(mach, x, frame, surface):
    """Space fighter and friends.  Close up the full phase is used; past frame 9
    it drops to a single bit so distant sprites do not flicker."""
    _grap65(mach, x, frame, surface, mach.m[TEMP4])


def _grap26(mach, x, frame, surface):
    """Blockader."""
    _grap65(mach, x, frame, surface, mach.m[TEMP11])


def _grap65(mach, x, frame, surface, a):
    if frame >= 0x09:
        a &= 0x01
        _grap60(mach, x, frame, surface, a, 0x0E)
    else:
        _grap61(mach, x, frame, surface, a)


def _grap24(mach, x, frame, surface):
    """Planet pirate."""
    _grap70(mach, x, frame, surface, mach.m[TEMP4])


def _grap71(mach, x, frame, surface):
    """Planet fighter / misc graphic."""
    _grap70(mach, x, frame, surface, mach.m[TEMP13])


def _grap70(mach, x, frame, surface, a):
    _grap60(mach, x, frame, surface, a, 0x11)


def _grap60(mach, x, frame, surface, a, limit):
    if frame >= limit:
        a = 0x00
    _grap61(mach, x, frame, surface, a)


def _grap61(mach, x, frame, surface, a):
    a, _ = b.adc(a, GRATB4[frame], c=False)
    if surface:
        a >>= 4
    _frame(mach, x, a, surface)


def _grap21(mach, x, frame, surface):
    """The man.  Decorative on a planet, but IN THE TRENCH he is the moving wall
    segment: VWALL comes from his Y, and a matching wind is pushed into YDELP0-1
    so your ship is dragged toward the wall."""
    m = mach.m
    if (m[PROGST] & 0xFD) == 0x40:          # in the trench
        if m[ATRACT] & 0x01:                # alternate frames only
            a, _ = b.adc(m[PNTR3], 0x04, c=True)
            a &= 0xFE
            hi, _ = b.cmp(a, 0x56)
            lo, _ = b.cmp(a, 0x0C)
            if not hi and lo:
                m[VWALL] = a
                door_open = bool(m[GAMEST] & 0x01)
                w = m[VWALL]
                if not door_open:
                    w, _ = b.adc(w, 0x56, c=False)
                    w >>= 1
                m[YDELP0 - 1] = w
                m.dec(YDELP0 - 1)           # VWIND
    _grap22(mach, x, frame, surface)


def _grap22(mach, x, frame, surface):
    """Trench tower."""
    mach.m[TEMP5] = x
    _grap71(mach, x, frame, surface)


def _grap29(mach, x, frame, surface):
    """Planet photon: clamp it to the terrain height, then alternate two frames."""
    m = mach.m
    carry, _ = b.cmp(m[HVERP0 - 1 + x], m[TEMP12])
    if not carry:
        m[TEMP12] = m[HVERP0 - 1 + x]
    _grap41(mach, x, frame, surface)


def _grap41(mach, x, frame, surface):
    a = ((mach.m[ATRACT] >> 1) & 0x01) | GRATB2[frame]
    _frame(mach, x, a, surface)


def _grap28(mach, x, frame, surface):
    """Space photon.  When the animation index reaches zero it has arrived:
    start an explosion and freeze the world."""
    m = mach.m
    if frame != 0 or m[PAUTIM] != 0:
        _grap41(mach, x, frame, surface)
        return
    m[EXPNTR] = EXPREG
    m[PAUTIM] = 0x20
    _set_type(mach, x, 0x3F, surface)       # $3F = the explosion graphic


def _grap27(mach, x, frame, surface):
    """Darter, or the warp-in effect below graphic $14."""
    m = mach.m
    carry, _ = b.cmp(m[HGRAP0 - 1 + x], 0x14)
    if not carry:
        _grap46(mach, x, frame, surface)
        return
    m[CH0SHD] = AUDVAR                      # the darter has a continuous sound
    a = ((m[ATRACT] >> 2) & 0x01) | 0x04
    if frame >= 0x10:
        a |= 0x02
    _frame(mach, x, a, surface)


def _grap46(mach, x, frame, surface):
    """The warp-in effect: track the P1+3 slot until the two meet, then hand the
    slot over to the real object."""
    m = mach.m
    m[TEMP5] = x
    m[HVERP0 - 1 + x] = m[HVERP1 + 3]
    carry, _ = b.cmp(m[HHORP0 - 1 + x], m[HHORP1 + 3])
    if carry:
        _set_type(mach, x, m[HGRAP0 - 1 + x], surface)
        return
    m[HGRAP1 + 3] = PBLK
    m[XDELP0 - 1 + x] = 0x00
    _set_type(mach, x, 0x18, surface)


def _grap30(mach, x, frame, surface):
    """Moons.  They have twice the frame count of anything else, so the phase
    byte is used a nibble at a time depending on the slot."""
    m = mach.m
    a = GRATB1[frame]
    if x >= 0x01:
        a >>= 4
    else:
        a, _ = b.adc(a, 0x04, c=False)
        m[ZPOSP0 - 1] = 0xA0
    a &= 0x0F
    carry, _ = b.cmp(m[HGRAP0 - 1 + x], 0x54)
    if carry:
        a, _ = b.adc(a, 0x0B, c=True)       # the second moon set
    a, _ = b.adc(a, 0x48, c=False)          # moon graphics start at $48
    _set_type(mach, x, a, surface)


def _grap32(mach, x, frame, surface):
    """Space explosion."""
    mach.m[TEMP5] = x
    _grap33(mach, x, frame, surface)


def _grap33(mach, x, frame, surface):
    """Explosions are SCRIPTED, not procedural.  EXPNTR walks EXPTAB, where a
    byte >= $80 is a new frame (its low 3 bits the sprite, the rest a vertical
    rise) and a byte < $80 is a timestamp to hold until PAUTIM reaches it."""
    m = mach.m
    y = m[EXPNTR]
    a = EXPTAB[y]
    if a & 0x80:
        if a == PBLK:
            _set_type_explosion(mach, x, PBLK, surface)   # end of script
            return
        rise, _ = b.sbc(a >> 3, 0x18, c=True)
        v, _ = b.adc(rise, m[HVERP0 - 1 + x], c=False)
        m[HVERP0 - 1 + x] = v
        m.inc(EXPNTR)
    else:
        y -= 1
        if a == m[PAUTIM]:
            m.inc(EXPNTR)
    a = (EXPTAB[y] & 0x07) | 0x38            # class $38 = explosion
    _set_type_explosion(mach, x, a, surface)


def _grap34(mach, x, frame, surface):
    """Landing zone."""
    _grap35(mach, x, frame, surface)


def _grap35(mach, x, frame, surface):
    """Crater."""
    mach.m[TEMP5] = x
    _grap36(mach, x, frame, surface)


def _grap36(mach, x, frame, surface):
    """Planet killer and the rest of the static scenery: the frame is a straight
    function of distance."""
    _frame(mach, x, GRATB1[frame], surface)


_HANDLERS = {
    "GRAP20": _grap20, "GRAP21": _grap21, "GRAP22": _grap22, "GRAP23": _grap23,
    "GRAP24": _grap24, "GRAP26": _grap26, "GRAP27": _grap27, "GRAP28": _grap28,
    "GRAP29": _grap29, "GRAP30": _grap30, "GRAP32": _grap32, "GRAP33": _grap33,
    "GRAP34": _grap34, "GRAP35": _grap35, "GRAP36": _grap36, "GRAP71": _grap71,
}

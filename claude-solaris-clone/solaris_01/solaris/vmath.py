"""The fixed-point motion model: DIVIDE, ZHELP, PREHLP, POSTHP, EXCHNG.

These four routines (solaris_annotated.asm:3501-3810) are the whole of Solaris'
movement.  Everything else -- BRAIN, MOVER, the spawner -- just calls them.

Packed velocities
-----------------
XDEL / YDEL / ZDEL are not plain signed speeds.  Each byte is

    bits 7..5   a 3-bit sub-pixel accumulator (fractional position)
    bits 4..0   a 5-bit signed speed CODE, not a speed

The code decodes through BRNTB5:

    $00..$0F  ->  positive, magnitude BRNTB5[code]
    $10..$1F  ->  negative, magnitude BRNTB5[code EOR $1F]

The curve is linear 0..8 then steps of 4, so slow speeds are finely
controllable and fast ones are coarse.

MOVER never unpacks: MOVTB4..MOVTB7 are 32-entry tables indexed by
`delta & $1F` giving (accumulator increment, position increment), so one lookup
and two ADCs advance an object by one frame.

The steering pipeline
---------------------
    DIVIDE   perspective divide -- how fast the object appears to drift purely
             because the camera is closing on it
    PREHLP   "how fast do I want to be going" (X and Y); ZHELP is the Z twin and
             also applies the automatic slow-down near the camera
    POSTHP   "slew towards it", at most one notch per call

Carry is an argument, not leftover state: `POSTHP(..., carry=False)` is the
type-1 response (snap to the target) and `carry=True` is type-2 (one notch).
BRAIN calls POSTHP twice in a row to get type-2 acceleration.
"""

from . import byte as b
from . import romdata as rom
from .state import (GAMEST, GAMEST_WANDER, HGRAP0, HVERP0, HHORP0, IQPATH,
                    IQWARP, PROGST, PROGST_SURFACE, TEMP7,
                    TEMP10, TEMP11, XDELP0, YDELP0, ZDELP0, ZPOSP0, ZVIS,
                    ATRACT)

# The tables, straight out of the ROM.  These are `Table` views onto the global
# data stream rather than slices, because several of them are indexed past their
# own end on purpose and must read whatever the assembler placed next.
DIVTB1 = rom.tab("DIVTB1")     # the perspective-divide lookup, indexed 0..$FF
BRNTB5 = rom.tab("BRNTB5")     # speed code -> magnitude
BRNTB7 = rom.tab("BRNTB7")     # magnitude -> speed code (PREHL3)
BRNT20 = rom.tab("BRNT20")     # |delta| -> clamped magnitude index
MOVTB4 = rom.tab("MOVTB4")     # Z: accumulator increment
MOVTB5 = rom.tab("MOVTB5")     # Z: whole-step increment
MOVTB6 = rom.tab("MOVTB6")     # X/Y: accumulator increment
MOVTB7 = rom.tab("MOVTB7")     # X/Y: whole-step increment


def unpack_speed(delta):
    """The real signed magnitude a packed velocity byte represents.

    Used for reading, never for integrating -- MOVER works on the packed form.
    """
    code = delta & 0x1F
    if code < 0x10:
        return BRNTB5[code]
    return -BRNTB5[code ^ 0x1F]


def divide(m, a, temp4, temp5, sign):
    """DIVIDE (asm:3516).  The perspective divide.

    `a`      signed screen offset from the centre of projection
    `temp4`  the zoomed distance nibble
    `temp5`  the closing-speed nibble
    `sign`   $00 or $FF, EOR-ed into the result (the ROM keeps it in PNTR1)

    Returns the apparent drift: offset * closing_speed / distance.

    Negative inputs are handled by the ROM's usual trick -- complement, recurse,
    complement back -- which is off by one against true negation, and that
    asymmetry is part of how the game feels.
    """
    if a & 0x80:
        return b.neg(_divide_positive(b.neg(a), temp4, temp5, sign))
    return _divide_positive(a, temp4, temp5, sign)


def _divide_positive(a, temp4, temp5, sign):
    """DIVID1: `a` is known non-negative here."""
    a, carry = b.asl(a)           # move the high nibble into index position
    if carry:
        a = 0xF0                  # saturate for inputs above 127
    y = (a & 0xF0) | (temp4 & 0x0F)
    a = DIVTB1[y]
    y = (a & 0x0F) | (temp5 & 0xF0)
    a = DIVTB1[y] >> 4
    return BRNTB5[a] ^ (sign & 0xFF)


def zhelp(m, x, a):
    """ZHELP (asm:3567).  Prepare a desired CLOSING speed.

    `a` is the raw speed error; m[TEMP7] is the per-path Z speed limit and
    m[TEMP10] the caller's baseline.  Leaves the packed 5-bit code in TEMP10.

    The sign trick: TEMP11 is $00 or $FF and is EOR-ed in and out so one code
    path serves both signs; `ROL TEMP11` then feeds the sign back into the
    carry for the following ADC.
    """
    m[TEMP11] = 0x00
    carry, _ = b.cmp(a, 0x70)      # $70 and up counts as negative here
    if carry:
        m[TEMP11] = 0xFF
    a ^= m[TEMP11]                 # make it positive
    carry, _ = b.cmp(a, m[TEMP7])
    if carry:
        a = m[TEMP7]               # clamp to the path speed limit
    a ^= m[TEMP11]                 # restore the sign
    _, sign_carry = b.rol(m[TEMP11], False)
    a, _ = b.adc(a, m[TEMP10], sign_carry)
    return zhelp1(m, x, a)


def zhelp1(m, x, a):
    """ZHELP1 (asm:3584).  The automatic slow-down entry.

    An object that has come closer than ZVIS is decelerated so it does not shoot
    past the camera -- unless it is wandering, on a surface, or already behind
    you, each of which decelerates on its own schedule.
    """
    y = m[ZPOSP0 - 1 + x]
    carry, _ = b.cmp(y, ZVIS)
    if not carry:
        return zhelp2(m, a)        # still far away: no slow-down needed

    if (m[PROGST] & PROGST_SURFACE) or (m[GAMEST] & GAMEST_WANDER):
        # ZHELP7: surfaces and wandering objects alternate their deceleration
        a = ((m[ATRACT] >> 2) & 0x01) | 0xFE
    else:
        carry, _ = b.cmp(y, 0xD0)
        if carry:
            return zhelp2(m, a)    # past $D0 it is behind the camera; leave it
        a = 0xFE                   # decelerate by one notch

    # ZHELP8: unless the throttle is already near maximum, go a little faster
    carry, _ = b.cmp(m[IQWARP], 0xF6)
    if not carry:
        a, _ = b.sbc(a, 0x01, c=False)   # ;C=0 -- so this subtracts two
    return zhelp2(m, a)


def zhelp2(m, a):
    """ZHELP2 (asm:3609).  Clamp to +-$0F/$F0 and reduce to the 5-bit code."""
    if a & 0x80:
        carry, _ = b.cmp(a, 0xF0)
        if not carry:
            a = 0xF0
    else:
        carry, _ = b.cmp(a, 0x10)
        if carry:
            a = 0x0F
    m[TEMP10] = a & 0x1F
    return m[TEMP10]


def prehlp(m, a):
    """PREHLP (asm:3639).  The X and Y twin of ZHELP.

    `a` is the raw error, m[TEMP7] the per-path speed limit, m[TEMP10] the
    baseline.  Leaves the packed code in TEMP10.
    """
    m[TEMP11] = 0x00
    carry, _ = b.cmp(a, 0x80)      # $80 and up counts as negative
    if carry:
        m[TEMP11] = 0xFF
    a ^= m[TEMP11]                 # absolute value
    a >>= 1                        # X and Y are less sensitive than Z, so
    a >>= 1                        # scale down by four
    carry, _ = b.cmp(a, m[TEMP7])
    if carry:
        a = m[TEMP7]
    a = BRNT20[a]
    a ^= m[TEMP11]
    _, sign_carry = b.rol(m[TEMP11], False)
    a, _ = b.adc(a, m[TEMP10], sign_carry)
    return prehl5(m, a)


def prehl5(m, a):
    """PREHL5 (asm:3659).  Pack only.

    Negatives are packed as a positive magnitude and then flipped with EOR $1F,
    which is exactly the negative-code convention.
    """
    if a & 0x80:
        prehl3(m, b.neg(a))
        m[TEMP10] ^= 0x1F
    else:
        prehl3(m, a)
    return m[TEMP10]


def prehl3(m, a):
    """PREHL3 (asm:3667).  Magnitude -> 5-bit code, saturating above $27."""
    carry, _ = b.cmp(a, 0x28)
    if carry:
        a = 0x27
    m[TEMP10] = BRNTB7[a]
    return m[TEMP10]


def posthp(m, a, carry):
    """POSTHP (asm:3696).  Slew a velocity toward the one PREHLP/ZHELP asked for.

    `a`      the object's CURRENT packed delta
    m[TEMP10] the DESIRED speed code
    `carry`  the response curve.  False is type 1 (snap straight to it), True is
             type 2 (move one notch, so acceleration is limited).  BRAIN calls
             this twice with carry=True to get two notches.

    Returns (new_delta, changed).  The sub-pixel accumulator in bits 7..5 always
    survives, which is why an object never loses its fractional position when it
    changes speed.
    """
    temp11 = a
    want = (a & 0xE0) | m[TEMP10]        # keep the accumulator, splice the code
    if not carry:
        return want, False               # POSTH2: type 1 takes it as is
    if want == temp11:
        return want, False               # already there
    step = 0xFE if ((want ^ temp11) & 0x10) else 0x00
    # POSTH4/POSTH3: the carry that picked the branch also selects the direction
    carry_now, _ = b.cmp(want, temp11)
    if not carry_now:
        step = b.neg(step)
    result, _ = b.adc(step, temp11, carry_now)
    return result, True


def posth1(m, a):
    """POSTH1 (asm:3694): `CLC` then POSTHP -- the type 1 entry."""
    return posthp(m, a, carry=False)


# Every parallel field of an object, in the order EXCHNG swaps them.
_FIELDS = (ZDELP0, HHORP0, ZPOSP0, YDELP0, XDELP0, HGRAP0, IQPATH)


def exchng(m, x):
    """EXCHNG (asm:3727).  Swap every field of obj[x-1] with obj[x-2].

    In Python that is `objs[i-1], objs[i-2] = objs[i-2], objs[i-1]`, but the
    array is eight parallel byte arrays, so it is done field by field.
    """
    _swap(m, HVERP0, x)
    exchn1(m, x)


def exchn1(m, x):
    """EXCHN1 (asm:3733).  The same swap, but leaving the Y coordinates alone --
    used when the caller has already adjusted them by hand."""
    for field in _FIELDS:
        _swap(m, field, x)


def _swap(m, field, x):
    a, c = field - 1 + x, field - 2 + x
    m[a], m[c] = m[c], m[a]

"""NEWOBJ (asm:998) -- the wave-spawn bytecode VM, and the spawner it drives.

Every encounter in Solaris is a little program in TYPTAB.  BRAIN calls NEWOBJ
whenever the swap logic finds an empty object slot, and the VM runs ONE
instruction: either an opcode, or a SPAWN DESCRIPTOR that fills the slot.

The opcode byte is literally the low byte of its handler's address, which is why
the scripts read like assembly (`LVS $0F`, `BRN ENETYP+3-W`).  The port keeps
them symbolic and dispatches by name.

    SUB t       call: IQSTAK = PC; PC = t          (one deep)
    GTO t       PC = t
    RET         PC = IQSTAK + 2; IQSTAK = 0
    STO addr,v  mem[addr] = v
    ENB addr,m  mem[addr] |= m
    LVS n       IQREAP = NEWT11[n + NEWAVE]        loop count, difficulty-scaled
    BRN t       if --IQREAP >= 0: PC = t
    RNW p,t     if p >= RANDOM: PC = t             a p/256 branch
    EMP v,t     if v >= HGRAP0+3: PC = t           "the screen is full"
    RND b       spawn one of NEWTB7[b + rand(0..3) - $E0]
    INL         award an extra ship, capped at five

A descriptor is any byte with bit 7 set:

    bit 7       always 1
    bits 6..2   the CLASS/GRAPHIC to create
    bit 2       ALSO "use slot 4 not slot 3" on a surface (the LZ and the man)
    bits 1..0   the CROWDING LIMIT: how full the screen may already be

$CB is the fallback: spawn a plain moon or crater and DO NOT advance the program
counter, so the same spawn is retried next frame.  That is how a script waits
for room.
"""

from . import byte as b
from . import romdata as rom
from .brain import _swap as bran22
from .mover import RNDPAGE
from .state import (CENTER, CH1PTR, CH1SHD, GAMEST, HGRAP0, HGRAP1, HHORP0,
                    HHORP1, HVERP0, HVERP1, IQPNTR, IQREAP, IQSTAK, IQWARP,
                    IQPATH, LIVES, NEWAVE, PBLK, PROGST, RANDOM, TEMP4,
                    TEMP5, TEMP10,
                    TOPSCN, XDELP0, YDELP0, ZDELP0, ZPOSP0)

TYPTAB = rom.tab("TYPTAB")
NEWT11 = rom.tab("NEWT11")   # loop counts, five bases x five difficulty tiers
NEWTB1 = rom.tab("NEWTB1")   # per-slot bias on the random spawn Y
NEWTB3 = rom.tab("NEWTB3")   # jump quality -> base spawn distance
NEWTB4 = rom.tab("NEWTB4")   # jump quality -> random X spread mask
NEWTB5 = rom.tab("NEWTB5")   # per-class wander probability
NEWTB7 = rom.tab("NEWTB7")   # the RND descriptor pool
NEWTB8 = rom.tab("NEWTB8")   # the two Saturn-rings variants
NEWT10 = rom.tab("NEWT10")   # jump quality -> random X spread bias
BRNTB6 = rom.tab("BRNTB6")
SWAPT1 = rom.tab("SWAPT1")

J = rom.LABELS["AUDTAB"]
AUDMAN = rom.LABELS["AUDMAN"] - J
AUDLNH = rom.LABELS["AUDLNH"] - J
AUDJMP = rom.LABELS["AUDJMP"] - J

FALLBACK = 0xCB              # a moon or crater, and retry next frame
WARPER = 0x92


def newobj(mach, x):
    """Run one VM instruction.  `x` is the empty slot BRAIN found."""
    m = mach.m
    y = m[IQPNTR]
    inst = TYPTAB[y]
    if isinstance(inst, int):
        if inst & 0x80:
            _spawn(mach, x, inst)
            return
        # An operand byte the program counter walked onto.  On hardware this
        # would be dispatched as an address; here it can only be a data byte
        # that is not a descriptor, so treat it as a one-byte no-op.
        _advance(m, y, 1)
        return
    _OPCODES[inst.name](mach, x, y)


def _advance(m, y, n):
    m[IQPNTR] = (y + n) & 0xFF


def _operand(y, n=1):
    return TYPTAB[y + n]


# ---------------------------------------------------------------------------
# the opcodes
# ---------------------------------------------------------------------------

def _sub(mach, x, y):
    mach.m[IQSTAK] = y
    _gto(mach, x, y)


def _gto(mach, x, y):
    mach.m[IQPNTR] = _operand(y)


def _ret(mach, x, y):
    """Pop the one-deep stack and resume just past the SUB that called us."""
    m = mach.m
    saved = m[IQSTAK]
    m[IQSTAK] = 0
    _advance(m, saved, 2)


def _sto(mach, x, y):
    m = mach.m
    m[_operand(y)] = _operand(y, 2)
    _advance(m, y, 3)


def _enb(mach, x, y):
    m = mach.m
    addr = _operand(y)
    m[addr] |= _operand(y, 2)
    _advance(m, y, 3)


def _lvs(mach, x, y):
    """Load the loop counter, scaled by difficulty -- which is how one script
    gets longer as NEWAVE rises."""
    m = mach.m
    idx, _ = b.adc(_operand(y), m[NEWAVE], c=False)
    m[IQREAP] = NEWT11[idx]
    _advance(m, y, 2)


def _brn(mach, x, y):
    m = mach.m
    if (m.dec(IQREAP) & 0x80) == 0:
        m[IQPNTR] = _operand(y)
        return
    _advance(m, y, 2)


def _rnw(mach, x, y):
    """A probabilistic branch: taken with probability p/256."""
    m = mach.m
    taken, _ = b.cmp(_operand(y), m[RANDOM])
    _branch(m, y, taken)


def _emp(mach, x, y):
    """Only ever written `EMP PBLK-1,t`, i.e. "the last slot is occupied"."""
    m = mach.m
    taken, _ = b.cmp(_operand(y), m[HGRAP0 + 3])
    _branch(m, y, taken)


def _branch(m, y, taken):
    if taken:
        m[IQPNTR] = _operand(y, 2)
    else:
        _advance(m, y, 3)


def _inl(mach, x, y):
    """Award an extra ship, capped at five."""
    m = mach.m
    if m[LIVES] < 0x05:
        m.inc(LIVES)
    _advance(m, y, 1)


def _rnd(mach, x, y):
    """Pick one of four descriptors at random and spawn it."""
    m = mach.m
    idx, _ = b.adc(m[RANDOM] & 0x03, _operand(y), c=False)
    _spawn(mach, x, NEWTB7[idx - 0xE0])


_OPCODES = {
    "NEWOB1": _sub, "NEWOB2": _gto, "NEWOB5": _ret, "NEWB41": _sto,
    "NEWOB4": _enb, "NEWB50": _lvs, "NEWB51": _brn, "NEWB78": _rnw,
    "NEWB55": _emp, "NEWB81": _inl, "NEWB40": _rnd,
}


# ---------------------------------------------------------------------------
# NEWOB3 -- the spawner
# ---------------------------------------------------------------------------

def _spawn(mach, x, descriptor):
    m = mach.m
    if descriptor >= 0xE0:
        _advance(m, m[IQPNTR], 1)    # a stray RND operand byte; just skip it
        return
    carry = True
    if descriptor < 0xA8:
        # everything but the moons needs the throttle near maximum
        carry, _ = b.cmp(m[IQWARP], 0xF1)
        if not carry:
            descriptor = FALLBACK
    m[TEMP10] = descriptor

    # count the free slots.  TEMP4 ends up as 5 - free, so 1 means all four are
    # empty and 5 means none are.
    m[TEMP4] = 0x05
    for y in range(5, 1, -1):
        v, _ = b.asl(m[HGRAP0 - 2 + y])
        if v & 0x80:                 # bit 6 of the type: PBLK has it set
            m.dec(TEMP4)

    if m[PROGST] & 0x40:
        _surface(mach, x)
        return
    _space(mach, x, carry)


def _surface(mach, x):
    """The destination slot is fixed on a surface: 3, or 4 for the landing zone
    and the man."""
    m = mach.m
    x = 0x03
    if m[TEMP10] & 0x04:
        x = 0x04

    room, _ = b.cmp(m[TEMP10] & 0x03, m[TEMP4])
    if not room:
        m[TEMP10] = FALLBACK         # too crowded: a crater instead

    if m[HGRAP0 - 1 + x] != PBLK:
        return                       # the destination is not actually free
    high, _ = b.cmp(m[HVERP0 - 2 + x], 0x4E)
    if high:
        return                       # no room below it

    graphic = m[TEMP10] & 0x7C
    terrain, _ = b.cmp(graphic, 0x40)
    if terrain:
        # $40 and up means "use the terrain graphic": $40 on a planet, $28 in
        # the trench, derived straight from PROGST
        v, _ = b.sbc(m[PROGST], 0x08, c=True)
        graphic = v & 0x68
    m[HGRAP0 - 1 + x] = graphic
    m[HVERP0 - 1 + x] = 0x56         # always just above the horizon

    if x == 0x04:
        m[CH1SHD] = AUDMAN           # the man appears
        if m[NEWAVE] != 0:
            _place_ship(mach, x, m[GAMEST] & 0x03)
            return
    _place(mach, x, 0x04)


def _space(mach, x, carry):
    """NEWB13: X is the empty slot BRAIN handed us.

    The carry threaded in from the descriptor checks changes what `SBC #$21`
    subtracts, so it is passed rather than assumed.
    """
    m = mach.m
    below, _ = b.sbc(m[HGRAP0 - 2 + x], 0x21, c=carry)
    darter, _ = b.cmp(below, 0x07)
    if not darter:
        _darter(mach, x, below)
        return

    room, _ = b.cmp(m[TEMP10] & 0x03, m[TEMP4])
    if not room:
        # not crowded enough for a real enemy, so force a moon -- and only if
        # the neighbouring object is small
        y = SWAPT1[x - 1]
        if y != 0:
            if (m[HGRAP0 - 1 + y] & 0x7F) < 0x28:
                _abort(m, x)
                return
        # NEWB21: `LDA #$02 / CMP TEMP4 / BCC NEWB16` -- even a moon needs at
        # least three of the four slots free
        enough, _ = b.cmp(0x02, m[TEMP4])
        if not enough:
            _abort(m, x)
            return
        m[TEMP10] = FALLBACK         # a moon, and do not advance the PC

    _choose_graphic(mach, x)


def _darter(mach, x, below):
    """A darter spawns attached to the object below it, sitting just under its
    parent rather than at a random height."""
    m = mach.m
    y = x
    x -= 1
    bran22(m, x, y)              # BRAN22 moves obj[x] into obj[y]
    # BRAN22 leaves the moved object's Y in A, and the carry is still clear
    # from the class test above, so this really subtracts four.
    v, carry = b.sbc(m[HVERP0 - 1 + y], 0x03, c=False)
    m[HVERP0 - 1 + x] = v
    if not carry:
        _abort(m, x)             # it would land off the bottom
        return
    m[CH1SHD] = AUDLNH
    m[HGRAP0 - 1 + x] = 0x14
    _path(mach, x)


def _abort(m, x):
    """Leave the slot empty and return.  The script PC is NOT advanced, so the
    same spawn is retried on a later frame."""
    m[HGRAP0 - 1 + x] = PBLK


def _choose_graphic(mach, x):
    m = mach.m
    graphic = m[TEMP10] & 0x7C
    if graphic == 0x40:
        graphic ^= NEWTB8[x - 1]     # the Saturn rings variant
    m[HGRAP0 - 1 + x] = graphic
    _vertical(mach, x)


def _vertical(mach, x):
    """The new object must fit in the gap between the objects above and below.
    The default is the midpoint; a random Y is used instead when it also fits.
    This is what keeps obj[1..4] sorted for the display kernel."""
    m = mach.m
    if x >= 0x04:
        top = TOPSCN
    else:
        y = m[HGRAP0 + x] & 0x7F
        height = (BRNTB6[y] & 0x3F) ^ 0xFF
        top, _ = b.adc(height, m[HVERP0 + x], c=False)
    m[TEMP4] = top

    if x < 0x02:
        bottom = 0x00
    else:
        bottom, _ = b.adc(m[HVERP0 - 2 + x], 0x07, c=True)
    m[TEMP5] = bottom

    fits, _ = b.cmp(bottom, top)
    if fits:
        _abort(m, x)                 # min > max: no room at all
        return
    mid, carry = b.adc(bottom, top, c=False)
    mid, _ = b.ror(mid, carry)
    m[HVERP0 - 1 + x] = mid

    # `LDA NEWOB3,Y` reads a ROM byte at a random offset as a cheap extra
    # source of randomness; the port substitutes real bank-4 ROM (see
    # mover.RNDPAGE for the same substitution in the PRNG itself).
    r = RNDPAGE[m[RANDOM]] & 0x0F
    r, _ = b.adc(r, NEWTB1[x], c=False)
    above, _ = b.cmp(r, m[TEMP5])
    below, _ = b.cmp(r, m[TEMP4])
    if above and not below:
        m[HVERP0 - 1 + x] = r

    _per_class(mach, x)


def _per_class(mach, x):
    m = mach.m
    descriptor = m[TEMP10]
    if descriptor == WARPER:
        _warper(mach, x)
        return
    if descriptor >= 0xA8:
        _moon(mach, x)
        return
    _space_enemy(mach, x, descriptor)


def _warper(mach, x):
    """The hyperspace warper: a scripted entrance that sets up BOTH the warper
    and the warp graphic in the shared P1+3 slot, so the pair animates together."""
    m = mach.m
    v = m[HVERP0 - 1 + x]
    low, _ = b.cmp(v, m[HVERP0 - 2])
    if not low:
        _abort(m, x)
        return
    high, _ = b.cmp(v, TOPSCN - 0x10)
    if high:
        _abort(m, x)
        return
    m[HVERP1 + 3] = v
    m[HHORP1 + 3] = 0x08
    m[ZPOSP0 - 1 + x] = 0x08
    m[ZPOSP0 - 1] = 0x08
    m[CH1PTR] = AUDJMP
    m[HHORP0 - 1 + x] = 0x98
    m[ZDELP0 - 1 + x] = 0x00
    m[ZDELP0 - 1] = 0x00
    m[YDELP0 - 1 + x] = 0x05
    m[YDELP0 - 1] = 0x05
    m[HGRAP1 + 3] = 0x10             # the warp graphic
    m[XDELP0 - 1] = 0x0D
    drift = (m[RANDOM] & 0x03) | 0x10
    _commit_drift(mach, x, drift)


def _moon(mach, x):
    """Moons get a fixed distance band chosen from the throttle, and an X near
    the camera."""
    m = mach.m
    band = 0x28
    v, _ = b.adc(m[IQWARP], 0x1F, c=True)
    if v & 0x80:
        band = 0x18
    m[ZPOSP0 - 1 + x] = band

    a, carry = b.lsr(m[RANDOM])
    a, carry = b.adc(a, 0x10, carry)
    a, carry = b.adc(a, m[CENTER], carry)
    a, _ = b.ror(a, carry)
    _finish(mach, x, a)


def _space_enemy(mach, x, descriptor):
    """Ordinary space enemies, which may be set WANDERING instead of attacking."""
    m = mach.m
    y = (descriptor >> 3) & 0x07
    if m[NEWAVE] != 0:
        v, carry = b.asl(m[GAMEST])  # rotate the old wander flag out...
        m[GAMEST] = v
        if not carry:
            carry, _ = b.cmp(m[RANDOM], NEWTB5[y])   # ...roll a new one...
        v, _ = b.ror(m[GAMEST], carry)
        m[GAMEST] = v                # ...and rotate it back into bit 7
    _place_ship(mach, x, m[GAMEST] & 0x03)


def _place_ship(mach, x, quality):
    """NEWB29/NEWB10.  Y is the JUMP QUALITY -- how accurately you arrived.  A
    bad jump drops enemies closer and more spread out."""
    _place(mach, x, quality)


def _place(mach, x, quality):
    m = mach.m
    m[ZPOSP0 - 1 + x] = NEWTB3[quality]
    a, carry = b.adc(m[RANDOM] & NEWTB4[quality], NEWT10[quality], c=False)
    a, carry = b.lsr(a)
    if carry:
        a ^= 0xFF                    # mirror it to the other side of the camera
    a, _ = b.adc(a, m[CENTER], c=carry)
    _finish(mach, x, a)


def _finish(mach, x, hx):
    m = mach.m
    m[HHORP0 - 1 + x] = hx
    jitter, _ = b.adc(m[RANDOM] & 0x0F, m[ZPOSP0 - 1 + x], c=False)
    m[ZPOSP0 - 1 + x] = jitter

    a = m[IQWARP]
    if a & 0x80:
        fast, _ = b.cmp(a, 0xF0)
        if not fast:
            a = 0x10                 # clamped so nothing hangs motionless
    m[ZDELP0 - 1 + x] = a & 0x1F
    m[YDELP0 - 1 + x] = 0x00
    _commit_drift(mach, x, 0x00)


def _commit_drift(mach, x, drift):
    m = mach.m
    m[XDELP0 - 1 + x] = drift
    if m[TEMP10] != FALLBACK:
        m.inc(IQPNTR)                # a real descriptor is consumed
    _path(mach, x)


def _path(mach, x):
    """NEWB92: pick the flight path.  In the trench everything flies down one
    fixed lane; elsewhere a random path id with the phase counter preset."""
    m = mach.m
    a = m[RANDOM]
    if m[PROGST] == 0x40:
        m[HHORP0 - 1 + x] = 0x4C
    else:
        a = (a & 0x09) | 0xC0
    m[IQPATH - 1 + x] = a

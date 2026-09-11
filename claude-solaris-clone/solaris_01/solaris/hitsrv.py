"""HITSRV (asm:6029) -- did anything hit you, and did you hit anything?

Runs once per frame during overscan.  It does NOT use the TIA latches for the
vertical test -- those are too coarse -- but the HORIZONTAL test is genuine
hardware collision: the display kernel stored CXPPMM into each object's HHITP0
as it finished drawing, so `HHITP0[i] < 0` means "that object's pixels touched
your ship or a photon this frame".  Everything else here is a range and class
lookup on top of that.

Structure:
  HITSRV..HITSR1  set up the vertical band.  On a surface it comes from VWALL,
                  so flying into the trench wall counts; in space from your ship
                  Y plus the P1+3 height CLOSE left in HOLDM0.
  HITSR1          loop over the four slots, skipping explosions and craters.
  HITSR5          work out WHAT it hit: your ship, or one of the two photons.
  HITSR7          it hit YOUR SHIP -- the man, the landing zone, a moon, or a
                  fatal impact.  Damage accumulates in ONESHT bits 4..6 and the
                  fourth hit destroys you.
  HITSR8          YOUR PHOTON hit it -- range-check, score, sound, explosion.
"""

from . import byte as b
from . import romdata as rom
from .score import addfl2, addscr
from .state import (CENTER, CH0PTR, CH1PTR, CH1SHD, EXPNTR, FUEL, GAMEST,
                    HGRAP0, HGRAP1, HHITP0, HHORP0, HOLDM0, HVERP0, HVERP1,
                    IQPATH, IQPNTR, IQWARP, NEWAVE, ONESHT, PAUTIM, PBLK,
                    PROGST, PROGST_SURFACE, RANDOM, SHIPST, TEMP4, TEMP5,
                    TEMP6, TEMP7, TEMP9, VSHIP, VWALL, XDELP0, YDELP0, ZDELP0,
                    ZPOSP0, ZPOSP1)

HITAB1 = rom.tab("HITAB1")   # class -> packed (sound index, BCD score)
HITAB2 = rom.tab("HITAB2")   # class -> maximum photon range
HITAB3 = rom.tab("HITAB3")   # class -> minimum photon range
HITAB4 = rom.tab("HITAB4")   # explosion sound
HITAB5 = rom.tab("HITAB5")   # difficulty -> GAMEST when you catch the man

J = rom.LABELS["AUDTAB"]
AUDCTH = rom.LABELS["AUDCTH"] - J
AUDFUL = rom.LABELS["AUDFUL"] - J
AUDBMP = rom.LABELS["AUDBMP"] - J
AUDEX4 = rom.LABELS["AUDEX4"] - J
AUDEXP = rom.LABELS["AUDEXP"] - J

W = rom.LABELS["TYPTAB"]
TRNTY1 = rom.LABELS["TRNTY1"] - W

EXPTAB = rom.LABELS["EXPTAB"]
EXPPLN = rom.LABELS["EXPPLN"] - EXPTAB
EXPTRN = rom.LABELS["EXPTRN"] - EXPTAB
EXPREG = rom.LABELS["EXPREG"] - EXPTAB
EXPFAR = rom.LABELS["EXPFAR"] - EXPTAB


def hitsrv(mach):
    """HITSRV."""
    m = mach.m
    if m[HVERP1] == 0:
        return                       # already dead
    if m[SHIPST] != 0:
        return                       # no collisions during a takeoff
    if m[FUEL] == 0:
        _destroyed(mach, 0)          # out of fuel: you are already blowing up
        return
    if m[PROGST] & 0xB1:
        return                       # game over, screen protect, hyperwarp, chart

    if not (m[PROGST] & PROGST_SURFACE):
        y, a = 0x7F, 0x00
    else:
        y = m[VWALL]
        scraped, _ = b.cmp(y, 0x13)
        if not scraped:
            _trench_wall(mach)
            return
        y -= 2
        a = 0x60
    m[TEMP5] = a                     # the class bias: 0 in space, $60 on a surface

    if m[HGRAP1 + 3] & 0x80:
        m[TEMP4] = y
    else:
        # HOLDM0 is the shared P1+3 object's height, which CLOSE computed.
        # Doug's own note at asm:6054 says it is "NOT DEFINED FOR PLN/TRN" --
        # a stale value on a surface.  Kept as-is.
        v = (y ^ m[HOLDM0]) | 0xC0
        v, _ = b.adc(v, m[HVERP1 + 3], c=True)
        m[TEMP4] = v

    m[HHITP0] = mach.tia.mipl        # the last object's latch, never stored by
                                     # the kernel because nothing follows it

    for x in range(3, -1, -1):
        if not (m[HHITP0 + x] & 0x80):
            continue                 # the kernel saw no overlap for this slot
        if m[HGRAP0 + x] & 0x80:
            continue                 # off screen
        cls = m[HGRAP0 + x] & 0x78
        if cls == 0x38:
            continue                 # explosions cannot hit you
        v, _ = b.adc(cls, m[TEMP5], c=False)
        m[TEMP6] = v
        if v == 0xA0:
            continue                 # a crater is scenery
        inside, _ = b.cmp(m[HVERP0 + x], m[TEMP4])
        if inside:
            continue
        _resolve(mach, x)
        return


def _resolve(mach, x):
    """HITSR4/HITSR5: which of your three things did it reach?"""
    m = mach.m
    v, _ = b.adc(m[TEMP6], 0x06, c=False)
    m[TEMP7] = v
    for y in (2, 1, 0):
        reached, _ = b.cmp(m[HVERP1 + y], m[TEMP7])
        if reached:
            continue
        if y == 0:
            _hit_ship(mach, x)
        elif not (m[ZPOSP1 - 1 + y] & 0x80):
            _hit_by_photon(mach, x, y)
        return


# ---------------------------------------------------------------------------
# It hit your ship
# ---------------------------------------------------------------------------

def _hit_ship(mach, x):
    """HITSR7."""
    m = mach.m
    cls = m[TEMP6]
    if cls == 0x10:
        # the darter reaches you at any range.  The carry from that compare is
        # SET, so HITS45 takes the "hit moon" branch: damage, not death.
        _damage_only(mach, x)
        return

    close, _ = b.cmp(m[ZPOSP0 + x], 0x0C)
    if close:
        return                       # everything else needs very close range

    if cls == 0x78:
        _the_man(mach, x)
        return
    if cls == 0x80:
        _landing_zone(mach, x)
        return

    # HITS13: nothing can touch you at very high throttle
    fast, _ = b.cmp(m[IQWARP], 0xF0)
    if not fast:
        return
    moon, _ = b.cmp(m[HGRAP0 + x], 0x40)
    if moon:
        _damage_only(mach, x)        # the moons are always an impact
        return

    # the nearer the object, the likelier the hit is fatal
    survived, _ = b.cmp(m[RANDOM] & 0x3F, m[ZPOSP0 + 1])
    if survived:
        _destroyed(mach, x)
        return
    if m[NEWAVE] == 0:
        _damage_only(mach, x)        # tier 0 never kills outright
        return
    dmg = ((m[ONESHT] >> 1) & 0x70) | 0x40
    m[ONESHT] |= dmg
    if m[ONESHT] & 0x10:
        _destroyed(mach, x)          # the fourth hit is fatal
        return
    _damage_only(mach, x)


def _the_man(mach, x):
    """HITMAN: on a planet he simply vanishes; in the TRENCH you caught him,
    which opens the door and sets your escape speed."""
    m = mach.m
    m[CH1SHD] = AUDCTH
    if m[PROGST] & 0x08:
        m[HGRAP0 + x] = PBLK
        return
    m[GAMEST] = HITAB5[m[NEWAVE]]    # SPEED + OPEN DOOR
    m[IQWARP] = 0xFC


def _landing_zone(mach, x):
    """HITS10: land -- refuel on your own planet, or enter the trench."""
    m = mach.m
    close, _ = b.cmp(m[ZPOSP0 + x], 0x0D)
    if close:
        return
    off, _ = b.sbc(m[CENTER], m[HHORP0 + x], c=False)
    missed, _ = b.cmp(off, 0x04)
    if missed:
        m[CH1PTR] = AUDBMP           # you missed the pad
        m[IQWARP] = 0x04
        return
    if m[GAMEST] & 0x40:
        _refuel(mach)
        return
    # an enemy planet's pad is the TRENCH ENTRANCE
    m[IQPNTR] = TRNTY1
    from .timsrv import timsr7       # late, to break the import cycle
    timsr7(mach)


def _refuel(mach):
    m = mach.m
    if m.inc(FUEL) == 0:
        m.dec(FUEL)                  # tank full
        m[ONESHT] &= 0x8F            # a full refuel repairs all damage
        return
    m[PROGST] |= 0x02                # freeze until you press fire to lift off
    m[CH1SHD] = AUDFUL


def _damage_only(mach, x):
    """HITS26: the sound, -15 fuel, and a normal explosion."""
    m = mach.m
    m[CH0PTR] = AUDEX4
    addfl2(mach)
    _start_explosion(mach, x, EXPREG)


def _destroyed(mach, x):
    """HITS25: your ship becomes an explosion at the camera, and HVERP1 = 0 is
    the flag TIMSRV reads to know you died."""
    m = mach.m
    m[HHORP0 + x] = m[CENTER]
    m[ZPOSP0 + x] = 0x0C
    m[HVERP0 + x] = VSHIP + 1
    m[CH1PTR] = AUDEXP
    m[HVERP1] = 0x00
    m[CH0PTR] = AUDEXP
    addfl2(mach)
    _start_explosion(mach, x, EXPREG)


def _trench_wall(mach):
    """HITS43: you touched the trench door.  Bit 0 of GAMEST flips: if it comes
    up set you got through the gap, otherwise the wall kills you."""
    m = mach.m
    m[GAMEST] ^= 0x01
    m[IQWARP] = 0xE8
    if m[GAMEST] & 0x01:
        return                       # MADE IT THRU
    _destroyed(mach, 0)


# ---------------------------------------------------------------------------
# Your photon hit it
# ---------------------------------------------------------------------------

def _hit_by_photon(mach, x, photon):
    """HITSR8."""
    m = mach.m
    m[TEMP9] = photon
    cls = m[TEMP6]

    if cls != 0x10:                  # the darter is always a hit
        idx = cls >> 2
        if idx >= 0x08:
            idx = 0x07
        surface, _ = b.cmp(cls, 0x60)
        z = m[ZPOSP0 + x]
        if surface:
            z >>= 1                  # the surface view is compressed
        too_far, _ = b.cmp(z, HITAB2[idx])
        if too_far:
            return
        too_near, _ = b.cmp(z, HITAB3[idx])
        if not too_near:
            return

    # HITS51
    k = cls >> 3
    if k == 0x0F:
        return                       # the man cannot be shot
    if k == 0x10:
        if not (m[GAMEST] & 0x40):
            return                   # the trench entrance, not a target
        from .smarts import blowz
        blowz(mach)                  # shooting your own pad destroys the planet

    v = HITAB1[k]
    m[CH1PTR] = HITAB4[v & 0x03]
    addscr(mach, (v >> 1) & 0x7E)

    long_range, _ = b.cmp(m[ZPOSP1 - 1 + photon], 0x18)
    m[ZPOSP1 - 1 + photon] = 0x80    # switch off the photon that scored

    if (m[PROGST] ^ 0x40) == 0:
        script = EXPTRN
    elif long_range:
        script = EXPFAR
    else:
        script = EXPREG
    _start_explosion(mach, x, script)


def _start_explosion(mach, x, script):
    """HITS22/HITS23: pick the surface variant if we are on one, cancel every
    other running explosion, and turn the target into this one."""
    m = mach.m
    if m[PROGST] & PROGST_SURFACE:
        script = EXPPLN
        v = (m[IQPATH + x] & 0x03) ^ 0x03
        if v == 0:
            m[IQWARP] = 0            # "=0 VISUAL COSMETIC?"
    m[EXPNTR] = script

    for y in range(4, 0, -1):
        if (m[HGRAP0 - 1 + y] & 0x78) == 0x38:
            m[HGRAP0 - 1 + y] = PBLK
    m[PAUTIM] = 0x20                 # freeze the world
    m[HGRAP0 + x] = 0x3F             # the explosion graphic
    m[XDELP0 + x] = 0
    m[YDELP0 + x] = 0
    m[ZDELP0 + x] = 0

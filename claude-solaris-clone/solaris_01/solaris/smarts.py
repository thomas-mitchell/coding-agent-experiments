"""SMARTS, DOOR, FINDV and CHTSRV -- the strategic layer above the dogfight.

The star chart is not stored as a map of contents.  It is stored as eight
ROUTES: each enemy fleet has a fixed starting cell (NCHTB5), a sign bitmap
(NCHTB1) and a direction bitmap (NCHTB2), all indexed by [fleet][level].  FINDV
replays a route as many steps as that fleet has taken and reports where it is
now.  So "what is in this sector" is computed on demand, never stored -- which
is how a whole galaxy fits in eight bytes of RAM.

The grid is 6 wide by 8 tall, 48 cells.  FINDV's `+1 / +6 / -6 / -1` steps and
SJOYT1's cursor deltas are the same four numbers, which is what pins the width.

SMARTS owns:
  * the JMPTIM countdown (BCD).  When it expires the fleets move, GAMTIM
    advances, and a fleet that reached a friendly planet destroys it (BLOWZ).
  * the NEGATIVE UNIVERSE effect (MAZSTA bit 7): random flashes, a noise burst,
    and every flight control reversed.
  * toggling the chart on and off, saving and restoring the object velocities
    that CHTBLK overlays.
  * SMRJOY, the chart cursor and the jump commit.
  * SMRHLP, the fleet AI: one fleet per jump-timer tick.
"""

from . import byte as b
from . import romdata as rom
from .score import addfl2
from .state import (ATRACT, CENTER, CH1PTR, CHTBLK, CURSOR, GAMEST, GAMTIM,
                    HGRAP1, IQPNTR, IQSTAK, JMPCNT, JMPTIM, LSTCUR, MAZRAM,
                    MAZSTA, NEWATT, NEWLEV, ONESHT, PAUTIM, PROGST,
                    PROGST_SURFACE, RANDOM, SHIPST, TEMP4, TEMP5, TEMP6,
                    TEMP7, TEMP9)

SMSKTB = rom.tab("SMSKTB")   # fleet index -> its MAZRAM bit
LD107 = rom.tab("LD107")     # the same masks, offset by one (fleet+1)
FINTB2 = rom.tab("FINTB2")   # fleet -> which of JMPCNT/MAZSTA holds its counter
SMHTB2 = rom.tab("SMHTB2")   # how far to advance a fleet, per timer phase
NCHTB1 = rom.tab("NCHTB1")   # route sign bits; also the chart's wall bitmap
NCHTB2 = rom.tab("NCHTB2")   # route direction bits
NCHTB5 = rom.tab("NCHTB5")   # starting cell per fleet per level
SJOYT1 = rom.tab("SJOYT1")   # stick direction -> cursor delta
SJOYT2 = rom.tab("SJOYT2")   # ... and the wall bit that blocks it
DORTB1 = rom.tab("DORTB1")   # icon -> PROGST for that encounter
DORTB2 = rom.tab("DORTB2")   # icon -> the spawn script: WHAT you fight
DORTB3 = rom.tab("DORTB3")   # wormhole destinations
DORTB4 = rom.tab("DORTB4")   # the level progression table, two nibbles per byte
DORTB6 = rom.tab("DORTB6")   # the initial MAZRAM bytes
DORTB8 = rom.tab("DORTB8")   # new-level starting cursor
DORTB9 = rom.tab("DORTB9")   # the four cells that start a new level
DORT11 = rom.tab("DORT11")   # level -> difficulty tier and time budget
DORT12 = rom.tab("DORT12")   # time band -> fleet speed
CHTAB1 = rom.tab("CHTAB1")   # the velocities restored when the chart closes
CHTAB4 = rom.tab("CHTAB4")   # the chart's wall layout, per level
CHTAB7 = rom.tab("CHTAB7")   # the chart's background colour, per level

J = rom.LABELS["AUDTAB"]
AUDEX6 = rom.LABELS["AUDEX6"] - J
AUDHLP = rom.LABELS["AUDHLP"] - J

W = rom.LABELS["TYPTAB"]
MONTYP = rom.LABELS["MONTYP"] - W
CRATYP = rom.LABELS["CRATYP"] - W
BLOWIT = rom.LABELS["BLOWIT"] - W
HYPSUB = rom.LABELS["HYPSUB"] - W
ATTSUB = rom.LABELS["ATTSUB"] - W

ICON_FRIENDLY = 0x03
ICON_WORMHOLE = 0x0A
ICON_WALL = 0x0C


def smarts(mach):
    """SMARTS (asm:5214).  Returns False when it consumed the frame, in which
    case BRAIN does not run (the assembly reaches BRAIN by falling through)."""
    m = mach.m
    y = m[PROGST]
    if (m[SHIPST] | m[PAUTIM]) != 0:
        m[PROGST] = y & 0xDF          # takeoff or explosion: force the chart off
        return True

    if y == 0 and (m[MAZSTA] & 0x80):
        _negative_universe(mach)

    if (y & 0x83) == 0:
        if (m[ATRACT] & 0x1F) == 0:
            return _jump_timer(mach)
        if (m[ATRACT] & 0x1F) == m[JMPTIM] and m[JMPTIM] < 0x05:
            smrhlp(mach)
            return True
    return _chart_toggle(mach)


def _negative_universe(mach):
    m = mach.m
    colour = 0x42
    if m[RANDOM] < 0x0C:
        m[CH1PTR] = AUDEX6            # an occasional noise burst
        colour = 0x8E
    mach.background_flash = colour


def _jump_timer(mach):
    """The strategic clock.  Returns False only when BLOWZ consumed the frame."""
    m = mach.m
    v, _ = b.bcd_sbc(m[JMPTIM], 0x01, c=True)
    if v != 0:
        m[JMPTIM] = v
        return True

    m.inc(GAMTIM)
    if m[NEWATT] == 0:
        m.inc(GAMTIM)                 # time runs twice as fast with nothing pending
    if m[NEWATT] >= 0x40:
        blowz(mach)                   # a friendly planet has been under attack
        return False
    addfl2(mach)                      # losing time costs 15 fuel
    m[JMPTIM] = 0x50                  # about 25 seconds
    return True


def blowz(mach):
    """BLOWZ (asm:5266).  A friendly planet is destroyed."""
    m = mach.m
    m[NEWATT] &= 0x3F
    m[CH1PTR] = AUDHLP                # the distress call
    if m[GAMEST] & 0x40:
        m[IQPNTR] = BLOWIT            # you are standing on it, so blow it up under you
    blowl1(mach)


def blowl1(mach):
    m = mach.m
    m[MAZRAM] &= 0x7F                 # the friendly planet is gone
    m[MAZSTA] |= 0x80                 # ... and the universe turns negative


def _chart_toggle(mach):
    """SMART1: open or close the star chart.

    The trigger is the RISING EDGE of "GAMEST bit 5 set, or the second
    controller's button pressed".  GAMEST bit 5 is a one-shot the spawn scripts
    set when a wave has finished, which is what makes the chart pop up by itself
    between encounters.
    """
    m = mach.m
    if m[HGRAP1 + 3] == 0x10:
        return True                   # the cobra locks the chart out

    before = m[GAMEST]
    m[GAMEST] = before & 0xDF
    carry = m[GAMEST] >= before        # CMP: set when bit 5 was already clear
    a, _ = b.ror(m[GAMEST], carry)
    latch = m[ONESHT] & 0x01
    m[ONESHT] >>= 1
    a &= mach.trig1

    if (a & 0x80) or latch == 0:
        # SMART9: no toggle; fold the button state back into the latch
        v, c = b.asl(a)
        v2, _ = b.rol(m[ONESHT], c)
        m[ONESHT] = v2
        if not (m[PROGST] & 0x20):
            return True               # the chart is not up, so run BRAIN
        smrjoy(mach)
        return True

    v, _ = b.asl(m[ONESHT])
    m[ONESHT] = v
    smar22(mach)
    return True


def smar22(mach):
    """SMAR22: flip the chart on or off."""
    m = mach.m
    m[PROGST] ^= 0x20
    if m[PROGST] & 0x20:
        m[ATRACT] = 0x40              # Doug's "HACK": park the frame counter
        m[MAZSTA] |= 0x40             # and ask for a chart redraw
        return
    # leaving: restore the 17 velocity bytes CHTBLK was overlaying
    for x in range(0x10, -1, -1):
        m[0xE7 + x] = CHTAB1[x]       # XDELP0-1 + x


# ---------------------------------------------------------------------------
# SMRJOY -- the chart cursor and the jump
# ---------------------------------------------------------------------------

def smrjoy(mach):
    """SMRJOY (asm:5359)."""
    m = mach.m
    a = m[ATRACT]
    if a & 0x80:
        m[ATRACT] = a & 0xBF          # "BIG HACK"
        a &= 0xBF
        if not (mach.trig0 & 0x80):
            _commit_jump(mach)
            return
    else:
        m[0xE3] = 0x01                # EXPNTR: reset the cursor auto-repeat

    _blink_fleet(mach, a & 0x07)
    _cursor(mach)


def _commit_jump(mach):
    """The fire button on the chart: arm a hyperwarp and close the chart."""
    m = mach.m
    m[IQPNTR] = CRATYP if (m[PROGST] & PROGST_SURFACE) else MONTYP
    m[SHIPST] = 0x20                  # hyperwarp queued
    v, _ = b.asl(m[ONESHT])           # swallow the press so it does not also fire
    m[ONESHT] = v >> 1
    m[CENTER] = 0x50                  # recentre for the new sector
    smar22(mach)


def _blink_fleet(mach, x):
    """Erase and sometimes redraw one fleet icon, which is what makes it blink."""
    m = mach.m
    if not (m[MAZRAM] & SMSKTB[x]):
        return
    cell = findv(mach, x)
    icon = m[TEMP6]
    cell = chters(m, cell)
    if cell == 0 and m[CURSOR] != 0x06 and (m[RANDOM] & 0x40):
        return
    chtdrw(m, cell, icon)


def _cursor(mach):
    """SMRJ22: count the auto-repeat delay down, read the stick, and blink the
    cursor itself."""
    m = mach.m
    if (m.dec(0xE3) & 0x80) == 0:     # EXPNTR still counting
        _draw_cursor(m, 0x02)
        return
    m.inc(0xE3)

    a = mach.porta                    # RAW: the negative universe does NOT
    x = 3                             # reverse the chart cursor
    while x >= 0:
        v, carry = b.asl(a)
        if not carry:
            _move_cursor(mach, x)
            return
        a = v
        x -= 1
    _blink_cursor(m)


def _blink_cursor(m):
    """SMRJ30: the cursor glyph alternates with the frame counter."""
    phase = m[ATRACT] & 0x3F
    if phase == 0x21:
        _draw_cursor(m, 0x00)
    elif phase > 0x21:
        return
    else:
        _draw_cursor(m, 0x02)


def _draw_cursor(m, icon):
    cell = chters(m, m[CURSOR])
    chtdrw(m, cell, icon)


def _move_cursor(mach, x):
    """SMRJY2: one cell, refusing moves off the grid, through a wall, or away
    from an occupied cell to anywhere but the one you came from."""
    m = mach.m
    dest, _ = b.adc(m[CURSOR], SJOYT1[x], c=False)
    off_grid, _ = b.cmp(dest, 0x30)
    if off_grid:
        _draw_cursor(m, 0x02)
        return
    if NCHTB1[dest] & SJOYT2[x]:
        _draw_cursor(m, 0x02)         # a wall on that side
        return

    nib = m[CHTBLK + (dest >> 1)]
    nib = (nib >> 4) if (dest & 1) else nib
    nib &= 0x0F
    if nib >= ICON_WALL:
        _draw_cursor(m, 0x02)
        return

    if (dest ^ m[LSTCUR]) & 0x80:
        # already sitting on an occupied cell: the only legal move is back
        if ((dest ^ m[LSTCUR]) << 1) & 0xFF:
            _blink_cursor(m)
            return

    m[LSTCUR] = m[CURSOR]
    v, c = b.asl(m[LSTCUR])
    occupied, _ = b.cmp(nib, 0x01)
    v, _ = b.ror(v, occupied)
    m[LSTCUR] = v                     # bit 7 = the destination was NOT empty
    m[CURSOR] = dest
    m[0xE3] = 0x0F                    # EXPNTR: the auto-repeat delay
    chters(m, dest)


def chtdrw(m, cell, icon):
    """CHTDRW: draw icon at a chart cell.  Two cells share a byte."""
    i = cell >> 1
    v = (icon << 4) & 0xF0 if (cell & 1) else (icon & 0x0F)
    m[CHTBLK + i] |= v


def chters(m, cell):
    """CHTERS: clear a chart cell.  Returns the cell, which callers rely on."""
    i = cell >> 1
    m[CHTBLK + i] &= 0x0F if (cell & 1) else 0xF0
    return cell


# ---------------------------------------------------------------------------
# FINDV -- where is fleet X, and what is it?
# ---------------------------------------------------------------------------

def findv(mach, x):
    """FINDV (asm:5524).  Returns the chart cell; leaves the icon in TEMP6 and
    the step count in TEMP9."""
    m = mach.m
    y = ((x << 4) | m[NEWLEV]) & 0xFF

    if x >= 0x04:
        # FINDV1: a STATIC fleet, with no route to replay
        steps, carry = 0, False
    else:
        half = FINTB2[x]
        raw = m[JMPCNT + half]        # JMPCNT and MAZSTA read as one 2-byte array
        if x >= 0x02:
            raw >>= 3
        steps = raw & 0x07
        m[TEMP9] = steps
        m[TEMP7] = NCHTB1[y]          # SIGN
        m[TEMP4] = NCHTB2[y]          # DIR
        carry = True

    start = NCHTB5[y]
    icon, _ = b.adc(start & 0x07, 0x03, carry)
    m[TEMP6] = icon
    cell = start >> 2

    for _ in range(steps):
        cell = _findv_step(m, cell)
    return cell & 0xFF


def findv6(mach, cell):
    """FINDV6: look one more step ahead, which is how SMRHLP knows where a
    fleet is going before it gets there."""
    return _findv_step(mach.m, cell) & 0xFF


def _findv_step(m, cell):
    """One route step.  The four outcomes are +1, +6, -6 and -1 -- the same
    deltas the cursor uses, which is what makes the grid six wide."""
    sign, carry = b.lsr(m[TEMP7])
    m[TEMP7] = sign
    a = cell
    if not carry:
        a, carry = b.adc(a, 0x08, c=False)
    a, carry = b.adc(a, 0xF9, carry)
    direction, dcarry = b.lsr(m[TEMP4])
    m[TEMP4] = direction
    if not dcarry:
        a, _ = b.adc(a, 0x05, c=False)
    return a


# ---------------------------------------------------------------------------
# SMRHLP -- the enemy fleet AI
# ---------------------------------------------------------------------------

def smrhlp(mach):
    """SMRHLP (asm:5816).  One fleet advances per jump-timer tick."""
    m = mach.m
    phase = m[JMPTIM]
    diff = (phase ^ m[NEWATT]) & 0xFF
    if diff >= 0x40:
        return                        # already attacking a friendly planet
    if (diff & 0x07) == 0:
        return
    fleet = phase - 1
    if not (m[MAZRAM] & LD107[phase]):
        return                        # that fleet is dead

    here = findv(mach, fleet)
    nxt = findv6(mach, here)
    if m[TEMP9] == 0x07:
        return                        # a fleet that finished its route stops

    m[TEMP4] = nxt
    if nxt == m[CURSOR] or ((nxt ^ m[LSTCUR]) & 0x7F) == 0:
        irqreq(mach, HYPSUB)          # CROSS FIRE: three warpers ambush you
        return

    if m[PROGST] & 0x20:
        chters(m, here)               # the chart is up, so erase the old icon

    half = FINTB2[phase]
    v, _ = b.adc(m[JMPCNT + half], SMHTB2[phase - 1], c=False)
    m[JMPCNT + half] = v

    if not (m[MAZRAM] & 0x80):
        return                        # no friendly planet left to attack
    friendly = NCHTB5[0x70 + m[NEWLEV]] >> 2
    if friendly != nxt:
        return

    door60(mach, (here << 3 | here >> 5) & 0x03)
    m[CH1PTR] = AUDHLP
    m[JMPTIM] = 0x85                  # a longer countdown to respond
    if m[GAMEST] & 0x40:
        smrhl4(mach)


def smrhl4(mach):
    """SMRHL4: you are on a friendly planet that is under attack."""
    m = mach.m
    m[GAMEST] |= 0x40
    if m[NEWATT] == 0:
        return
    door60(mach, ((m[NEWATT] << 3) | (m[NEWATT] >> 5)) & 0x03)
    irqreq(mach, ATTSUB)


def irqreq(mach, script):
    """IRQREQ: a software interrupt into the spawn VM.  Refused if the one-deep
    stack is already in use."""
    m = mach.m
    if m[IQSTAK] != 0:
        return
    m[IQSTAK] = (m[IQPNTR] - 2) & 0xFF
    m[IQPNTR] = script


# ---------------------------------------------------------------------------
# DOOR -- what is in this sector?
# ---------------------------------------------------------------------------

def door(mach):
    """DOOR (asm:5755).  Called from TIMSRV the moment a hyperwarp finishes."""
    m = mach.m
    if not (m[LSTCUR] & 0x80):
        door2(mach)                   # you did not actually move
        return
    for x in range(7, -1, -1):
        if not (m[MAZRAM] & SMSKTB[x]):
            continue
        m[TEMP5] = x
        cell = findv(mach, x)
        if cell == m[CURSOR]:
            _door4(mach, x, cell)
            return
    swap1(mach)                       # "SHOULDNT BE ABLE TO GET HERE, BAIL OUT!!!"


def _door4(mach, x, cell):
    m = mach.m
    icon = m[TEMP6]
    if icon == ICON_WORMHOLE:
        m[CURSOR] = DORTB3[cell & 0x03]
        m[SHIPST] = 0x30              # JMP AGAIN
        return
    # THIS is the single place the game decides what you are about to fight.
    m[PROGST] = DORTB1[icon - 3]
    m[IQPNTR] = DORTB2[icon - 3]
    if icon == ICON_FRIENDLY:
        _door50(mach)
        return
    door60(mach, x + 1)


def door60(mach, value):
    m = mach.m
    m[NEWATT] |= value


def _door50(mach):
    """A friendly planet -- or, at cursor 0, the end of the star lanes."""
    m = mach.m
    if m[CURSOR] != 0:
        smrhl4(mach)
        return
    m[ONESHT] = 0x18                  # the stars-end flag
    from .timsrv import init8         # late, to break the import cycle
    init8(mach)                       # you reached the end of the star lanes


def door2(mach):
    """DOOR2: the sector is empty.  Four cells start a NEW LEVEL."""
    m = mach.m
    for y in range(3, -1, -1):
        if m[CURSOR] == DORTB9[y]:
            door21(mach, y)
            return
    swap1(mach)


def door21(mach, y):
    """DOOR21: advance the level."""
    m = mach.m
    if m[NEWATT] >= 0x40:
        blowl1(mach)                  # a fleet got there while you were jumping
    swap(mach)
    m[CURSOR] = DORTB8[y]

    index = ((y << 4) | m[NEWLEV]) & 0xFF
    packed = DORTB4[index >> 1]
    nib = (packed >> 4) if (m[NEWLEV] & 1) else packed
    nib &= 0x0F
    rolled, _ = b.cmp(nib, 0x08)
    m[NEWLEV] = nib ^ m[NEWLEV]       # the table stores XOR DELTAS
    if rolled:
        door24(mach, 0x0F)            # reload the whole chart
        return
    door23(mach)


def door24(mach, y):
    """DOOR24: load the eight chart bytes from DORTB6.  Also INIT's entry."""
    m = mach.m
    for x in range(7, -1, -1):
        m[MAZRAM + x] = DORTB6[y]
        y -= 1
    door23(mach)


def door23(mach):
    """DOOR23: reset the attack state and set how fast the fleets now advance,
    based on how long you took over the last level."""
    m = mach.m
    swap(mach)
    m[NEWATT] = 0
    x = 0
    a, carry = b.sbc(m[GAMTIM], DORT11[m[NEWLEV]], c=True)
    if carry:
        while True:
            a, carry = b.sbc(a, 0x04, c=True)
            if not carry:
                break
            x += 1
            if x >= 4:
                break
        if x < 4 and (m[MAZRAM] & 0x03):
            blowl1(mach)              # far too long: lose a friendly planet
        m[JMPTIM] = 0x05
    m[JMPCNT] = DORT12[x]
    m[MAZSTA] = DORT12[x] | (0x00 if (m[MAZRAM] & 0x80) else 0x80)


def swap(mach):
    """SWAP: exchange MAZRAM[0] with MAZRAM[level & 7] -- which is how the same
    eight bytes describe a different universe on every level."""
    m = mach.m
    x = m[NEWLEV] & 0x07
    m[MAZRAM], m[MAZRAM + x] = m[MAZRAM + x], m[MAZRAM]
    swap1(mach)


def swap1(mach):
    m = mach.m
    m[LSTCUR] = m[CURSOR]             # this also clears LSTCUR bit 7


# ---------------------------------------------------------------------------
# CHTSRV -- rebuild the chart bitmap
# ---------------------------------------------------------------------------

def chtsrv(mach):
    """CHTSRV (asm:10461).  With the chart up, MOVER calls this instead of
    moving objects: it unpacks CHTAB4's wall layout into CHTBLK."""
    m = mach.m
    if not (m[PROGST] & 0x20):
        return
    mach.chart_colour = CHTAB7[m[NEWLEV]]
    if not (m[MAZSTA] & 0x40):
        return
    m[MAZSTA] &= 0xBF

    y = m[NEWLEV] * 6                 # six CHTAB4 bytes per level
    bit = 0
    byte = CHTAB4[y]
    for x in range(0x17, -1, -1):
        v = 0x00
        for mask in (0xC0, 0x0C):
            if byte & 0x80:
                v |= mask
            byte = (byte << 1) & 0xFF
            bit += 1
            if bit == 8:
                bit = 0
                y += 1
                byte = CHTAB4[y]
        m[CHTBLK + x] = v             # $C0 / $0C is icon $0C, the WALL glyph

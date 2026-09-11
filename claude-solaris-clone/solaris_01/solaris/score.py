"""MESSRV, ADDSCR and ADDFUL -- the score, and the fuel tank.

The score is three bytes of packed BCD, little-endian, and MESSRV unpacks it
into six glyph pointers for the score kernel.  The least significant of those
six is hard-coded to the '0' glyph (asm:4650), which is why every score value in
HITAB1 is one tenth of what the player sees.
"""

from . import byte as b
from . import romdata as rom
from .state import (ATRACT, FUEL, NEWATT, PNTR1, PNTR2, PNTR3, PNTR4, PNTR5,
                    PNTR6, PROGST, SCORE)

SCRTAB = rom.LABELS["SCRTAB"]
BLANK_GLYPH = 0x78          # glyph 15 in SCRTAB
POWERUP = 0xCE


def messrv(mach):
    """MESSRV (asm:4614).  Unpack SCORE into PNTR1..PNTR6, blanking leading zeros.

    PNTR6 is the leftmost digit on screen and PNTR1 the rightmost.
    """
    m = mach.m
    if m[NEWATT] >= 0x40 and not (m[ATRACT] & 0x80):
        return                       # attract mode shows the SCANNER banner instead

    m[PNTR2] = (m[SCORE] & 0x0F) << 3
    m[PNTR3] = (m[SCORE] & 0xF0) >> 1
    m[PNTR4] = (m[SCORE + 1] & 0x0F) << 3
    m[PNTR5] = (m[SCORE + 1] & 0xF0) >> 1
    m[PNTR6] = (m[SCORE + 2] & 0x0F) << 3
    # the trailing digit is a literal '0' -- except on the power-up screen,
    # where it is blanked with everything else
    m[PNTR1] = BLANK_GLYPH if m[PROGST] == POWERUP else 0x00

    # walk down from the most significant digit, blanking zeros until the first
    # non-zero one.  PNTR1 is never reached, so the trailing '0' always shows.
    for addr in (PNTR6, PNTR5, PNTR4, PNTR3, PNTR2):
        if m[addr] != 0:
            break
        m[addr] = BLANK_GLYPH


def addscr(mach, amount):
    """ADDSCR (asm:5970): add to the score in decimal mode."""
    addsc3(mach, amount, 0)


def addsc3(mach, amount, index):
    """ADDSC3: the same, starting at a chosen byte of SCORE -- which is how
    `+8000 for a cleared planet` is written as $08 into SCORE[1]."""
    m = mach.m
    while index < 3:
        v, carry = b.bcd_adc(m[SCORE + index], amount, c=False)
        m[SCORE + index] = v
        if not carry:
            return
        amount = 0x01
        index += 1


def addful(mach, amount):
    """ADDFUL (asm:6331).  `SEC` then `ADC`, so the amount is really amount+1.

    There is NO upper clamp: refuelling relies on noticing the wrap to $00
    (HITS41, asm:6161), so keep the wraparound.
    """
    m = mach.m
    total = m[FUEL] + (amount & 0xFF) + 1
    m[FUEL] = total & 0xFF if total > 0xFF else 0x00


def addfl2(mach):
    """ADDFL2: the standard -15 fuel penalty."""
    addful(mach, 0xF0)

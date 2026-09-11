"""6502 arithmetic, exactly as the ROM does it.

Solaris' feel comes out of 8-bit wraparound: packed velocities roll their
sub-pixel bits into the position byte, positions wrap at $FF, the score is
packed BCD, and carry is passed between routines as a boolean *argument* (a bare
`SEC` or `CLC` before a `JSR` is a parameter, not leftover state -- see the
assembly's own reading notes, section 9).

Python ints do none of that, so every ported routine goes through these.
Each returns `(result, carry)` where the 6502 would have left a carry behind.
"""


def adc(a, b, c=0):
    """ADC: a + b + carry, 8-bit.  Returns (result, carry_out)."""
    t = (a & 0xFF) + (b & 0xFF) + (1 if c else 0)
    return t & 0xFF, t > 0xFF


def sbc(a, b, c=1):
    """SBC: a - b - (1 - carry), 8-bit.  Returns (result, carry_out).

    Carry IN is a *borrow-not* flag, so `SEC / SBC #1` subtracts one and
    `CLC / SBC #1` subtracts two.  The assembly's `;C=0` comments mark the
    places Doug relied on that.
    """
    t = (a & 0xFF) - (b & 0xFF) - (0 if c else 1)
    return t & 0xFF, t >= 0


def cmp(a, b):
    """CMP: the carry and zero flags only.  Returns (carry, zero).

    Carry set means a >= b *unsigned*, which is what every `BCS`/`BCC` in the
    ROM tests.
    """
    a, b = a & 0xFF, b & 0xFF
    return a >= b, a == b


def asl(a, c=0):
    """ASL: shift left, bit 7 into carry.  `c` is ignored (use `rol` to feed)."""
    return (a << 1) & 0xFF, bool(a & 0x80)


def lsr(a):
    """LSR: shift right, bit 0 into carry."""
    return (a >> 1) & 0x7F, bool(a & 0x01)


def rol(a, c):
    """ROL: shift left through carry."""
    return ((a << 1) & 0xFF) | (1 if c else 0), bool(a & 0x80)


def ror(a, c):
    """ROR: shift right through carry."""
    return ((a >> 1) & 0x7F) | (0x80 if c else 0), bool(a & 0x01)


def s8(v):
    """Read a byte as a signed value, the way BPL/BMI treat it."""
    v &= 0xFF
    return v - 0x100 if v & 0x80 else v


def neg(a):
    """EOR #$FF -- the ROM's usual stand-in for negation (it is off by one, and
    the following ADC with carry set is what completes it)."""
    return (a ^ 0xFF) & 0xFF


def bcd_adc(a, b, c=0):
    """ADC in decimal mode (SED), as ADDSCR uses for the score."""
    lo = (a & 0x0F) + (b & 0x0F) + (1 if c else 0)
    carry_lo = lo > 9
    if carry_lo:
        lo += 6
    hi = (a >> 4) + (b >> 4) + (1 if carry_lo else 0)
    carry = hi > 9
    if carry:
        hi += 6
    return ((hi << 4) | (lo & 0x0F)) & 0xFF, carry


def bcd_sbc(a, b, c=1):
    """SBC in decimal mode, as the JMPTIM countdown uses."""
    lo = (a & 0x0F) - (b & 0x0F) - (0 if c else 1)
    borrow_lo = lo < 0
    if borrow_lo:
        lo -= 6
    hi = (a >> 4) - (b >> 4) - (1 if borrow_lo else 0)
    borrow = hi < 0
    if borrow:
        hi -= 6
    return ((hi << 4) | (lo & 0x0F)) & 0xFF, not borrow

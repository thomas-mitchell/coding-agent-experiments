"""The fixed-point motion model, checked against the assembly's own tables."""

from solaris import byte as b
from solaris import romdata as rom
from solaris import vmath
from solaris.state import Mem, TEMP7, TEMP10


def test_byte_arithmetic_wraps_like_a_6502():
    assert b.adc(0xFF, 0x01, c=False) == (0x00, True)
    assert b.adc(0x7F, 0x01, c=False) == (0x80, False)
    # SEC then SBC #1 subtracts one; CLC then SBC #1 subtracts two
    assert b.sbc(0x10, 0x01, c=True) == (0x0F, True)
    assert b.sbc(0x10, 0x01, c=False) == (0x0E, True)
    assert b.sbc(0x00, 0x01, c=True) == (0xFF, False)
    # CMP is unsigned, which is what every BCS/BCC in the ROM tests
    assert b.cmp(0x80, 0x7F) == (True, False)
    assert b.cmp(0x7F, 0x80) == (False, False)
    assert b.cmp(0x40, 0x40) == (True, True)


def test_bcd_matches_decimal_mode():
    assert b.bcd_adc(0x09, 0x01, c=False) == (0x10, False)
    assert b.bcd_adc(0x99, 0x01, c=False) == (0x00, True)
    assert b.bcd_sbc(0x60, 0x01, c=True) == (0x59, True)
    assert b.bcd_sbc(0x00, 0x01, c=True) == (0x99, False)


def test_packed_velocity_decodes_through_brntb5():
    """Codes $00..$0F are positive, $10..$1F negative via `code EOR $1F`."""
    assert vmath.unpack_speed(0x00) == 0
    assert vmath.unpack_speed(0x08) == 8
    assert vmath.unpack_speed(0x0F) == 0x24
    assert vmath.unpack_speed(0x1F) == 0          # $1F ^ $1F == 0
    assert vmath.unpack_speed(0x10) == -0x24
    # the accumulator bits in 7..5 are ignored
    assert vmath.unpack_speed(0xE5) == vmath.unpack_speed(0x05)


def test_posthp_type_1_snaps_and_type_2_steps():
    m = Mem()
    m[TEMP10] = 0x02
    # type 1 takes the target immediately, keeping the accumulator bits
    assert vmath.posthp(m, 0x45, carry=False) == (0x42, False)
    # type 2 moves exactly one notch toward it
    result, changed = vmath.posthp(m, 0x45, carry=True)
    assert changed and result == 0x44
    # and stops once it arrives
    assert vmath.posthp(m, 0x42, carry=True) == (0x42, False)


def test_posthp_preserves_the_subpixel_accumulator():
    m = Mem()
    m[TEMP10] = 0x07
    for accumulator in (0x00, 0x20, 0x40, 0x60, 0x80, 0xA0, 0xC0, 0xE0):
        out, _ = vmath.posth1(m, accumulator | 0x03)
        assert out & 0xE0 == accumulator


def test_prehlp_packs_and_signs():
    m = Mem()
    m[TEMP7] = 0x0F
    m[TEMP10] = 0x00
    positive = vmath.prehlp(m, 0x20)
    m[TEMP10] = 0x00
    negative = vmath.prehlp(m, 0xE0)
    # a negative error must come back as a negative code (bit 4 set) or zero
    assert positive < 0x10
    assert negative == 0x00 or negative >= 0x10


def test_zhelp2_clamps_to_the_five_bit_code():
    m = Mem()
    assert vmath.zhelp2(m, 0x40) == 0x0F         # clamped high
    assert vmath.zhelp2(m, 0x80) == 0x10         # clamped low ($F0 & $1F)
    assert vmath.zhelp2(m, 0x07) == 0x07         # in range


def test_divide_is_offset_times_speed_over_distance():
    """DIVIDE gets bigger with the offset and smaller with distance."""
    m = Mem()
    near = vmath.divide(m, 0x40, temp4=0x02, temp5=0x40, sign=0x00)
    far = vmath.divide(m, 0x40, temp4=0x0E, temp5=0x40, sign=0x00)
    assert near >= far
    small = vmath.divide(m, 0x10, temp4=0x02, temp5=0x40, sign=0x00)
    assert small <= near
    # the sign mask flips the result, the way PNTR1 does for a receding object
    flipped = vmath.divide(m, 0x40, temp4=0x02, temp5=0x40, sign=0xFF)
    assert flipped == (near ^ 0xFF)


def test_exchange_swaps_every_field():
    m = Mem()
    fields = (0xA5, 0xAE, 0xB7, 0xBF, 0xC4, 0xE8, 0xED, 0xF2)   # the object arrays
    for i, f in enumerate(fields):
        m[f + 0] = 0x10 + i          # slot 1
        m[f + 1] = 0x20 + i          # slot 2
    vmath.exchng(m, 2)               # obj[1] <-> obj[0] in the -1,X convention
    for i, f in enumerate(fields):
        assert m[f + 0] == 0x20 + i
        assert m[f + 1] == 0x10 + i


def test_exchn1_leaves_the_y_coordinates_alone():
    m = Mem()
    HVERP0 = 0xB7
    m[HVERP0 + 0], m[HVERP0 + 1] = 0x30, 0x50
    vmath.exchn1(m, 2)
    assert (m[HVERP0 + 0], m[HVERP0 + 1]) == (0x30, 0x50)

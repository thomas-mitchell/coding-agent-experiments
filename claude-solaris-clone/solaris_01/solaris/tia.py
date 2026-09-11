"""The parts of the TIA the game logic can actually observe.

Not a cycle-accurate emulation -- the port drops all the beam timing.  What it
cannot drop is:

  * the NTSC palette, because every colour in the game is a TIA colour byte
  * the COLLISION LATCHES, because Solaris' enemy-vs-player collision detection
    is genuine per-pixel player overlap.  The display kernel stores CXPPMM into
    HHITP0 as each object finishes drawing (DIS400, asm:6772) and HITSRV then
    tests bit 7.  Without rendering the objects there is nothing to collide.
  * the audio channels, which are two polynomial-counter tone generators driven
    straight from AUDC/AUDF/AUDV.
"""

# --- NTSC palette -----------------------------------------------------------
# The standard 2600 NTSC colours.  A TIA colour byte is hue<<4 | luminance<<1,
# so bit 0 is unused and there are 128 distinct colours.
NTSC = (
    0x000000, 0x4A4A4A, 0x6F6F6F, 0x8E8E8E, 0xAAAAAA, 0xC0C0C0, 0xD6D6D6, 0xECECEC,
    0x484800, 0x69690F, 0x86861D, 0xA2A22A, 0xBBBB35, 0xD2D240, 0xE8E84A, 0xFCFC54,
    0x7C2C00, 0x904811, 0xA26221, 0xB47A30, 0xC3903D, 0xD2A44A, 0xDFB755, 0xECC860,
    0x901C00, 0xA33915, 0xB55328, 0xC66C3A, 0xD5824A, 0xE39759, 0xF0AA67, 0xFCBC74,
    0x940000, 0xA71A1A, 0xB83232, 0xC84848, 0xD65C5C, 0xE46F6F, 0xF08080, 0xFC9090,
    0x840064, 0x97197A, 0xA8308F, 0xB846A2, 0xC659B3, 0xD46CC3, 0xE07CD2, 0xEC8CE0,
    0x500084, 0x68199A, 0x7D30AD, 0x9246C0, 0xA459D0, 0xB56CE0, 0xC57CEE, 0xD48CFC,
    0x140090, 0x331AA3, 0x4E32B5, 0x6848C6, 0x7F5CD5, 0x956FE3, 0xA980F0, 0xBC90FC,
    0x000094, 0x181AA7, 0x2D32B8, 0x4248C8, 0x545CD6, 0x656FE4, 0x7580F0, 0x8490FC,
    0x001C88, 0x183B9D, 0x2D57B0, 0x4272C2, 0x548AD2, 0x65A0E1, 0x75B5EF, 0x84C8FC,
    0x003064, 0x185080, 0x2D6D98, 0x4288B0, 0x54A0C5, 0x65B7D9, 0x75CCEB, 0x84E0FC,
    0x004030, 0x18624E, 0x2D8169, 0x429E82, 0x54B899, 0x65D1AE, 0x75E7C2, 0x84FCD4,
    0x004400, 0x1A661A, 0x328432, 0x48A048, 0x5CBA5C, 0x6FD26F, 0x80E880, 0x90FC90,
    0x143C00, 0x355F18, 0x527E2D, 0x6E9C42, 0x87B754, 0x9ED065, 0xB3E775, 0xC8FC84,
    0x303800, 0x505916, 0x6D762B, 0x88923E, 0xA0AB4F, 0xB7C25F, 0xCCD86E, 0xE0EC7C,
    0x482C00, 0x694D14, 0x866A26, 0xA28638, 0xBB9F47, 0xD2B656, 0xE8CC63, 0xFCE070,
)


def rgb(colour_byte):
    """A TIA colour byte -> a packed 0xRRGGBB value."""
    return NTSC[(colour_byte & 0xFE) >> 1]


# CXPPMM ($37 in this disassembly's register names, called MIPL there).
CX_P0P1 = 0x80      # player 0 touched player 1 -- the one Solaris cares about
CX_M0M1 = 0x40


class Collisions:
    """The TIA's collision latches: sticky until HITCLR.

    Only player-player matters to Solaris, but keeping the register shape means
    `LDA MIPL` in the port reads the same byte the assembly read.
    """

    __slots__ = ("cxppmm",)

    def __init__(self):
        self.cxppmm = 0

    def clear(self):
        """HITCLR."""
        self.cxppmm = 0

    def note_players(self, overlapped):
        if overlapped:
            self.cxppmm |= CX_P0P1

    @property
    def mipl(self):
        return self.cxppmm


# --- audio ------------------------------------------------------------------
# The TIA has two identical channels, each with a 4-bit volume (AUDV), a 5-bit
# frequency divider (AUDF) and a 4-bit waveform selector (AUDC).  The waveforms
# come from three polynomial shift registers and a couple of fixed dividers;
# reproducing them is what makes Solaris sound like Solaris rather than like
# square waves.
#
# The channels are clocked at 30 times the horizontal rate, i.e. 3.579545 MHz
# / 114 = 31400 Hz.

AUDIO_CLOCK = 31400


def _poly(taps, bits, length):
    """Generate a maximal-length polynomial sequence, LSB out."""
    reg = 1
    out = []
    for _ in range(length):
        out.append(reg & 1)
        feedback = 0
        for t in taps:
            feedback ^= (reg >> t) & 1
        reg = (reg >> 1) | (feedback << (bits - 1))
    return out


POLY4 = _poly((0, 1), 4, 15)
POLY5 = _poly((0, 2), 5, 31)
POLY9 = _poly((0, 4), 9, 511)
# The "divide by 31" waveform is not a polynomial at all: it is 18 low samples
# then 13 high ones.
DIV31 = [0] * 18 + [1] * 13


class SoundChannel:
    """One TIA audio channel."""

    __slots__ = ("audc", "audf", "audv", "_div", "_p4", "_p5", "_p9",
                 "_d31", "_three", "_out")

    def __init__(self):
        self.audc = 0
        self.audf = 0
        self.audv = 0
        self._div = 0
        self._p4 = 0
        self._p5 = 0
        self._p9 = 0
        self._d31 = 0
        self._three = 0
        self._out = 0

    def clock(self):
        """Advance one 31.4 kHz tick and return the sample, -1..1 scaled by volume."""
        self._div += 1
        if self._div <= self.audf:
            return self._out * self.audv
        self._div = 0
        self._step()
        return self._out * self.audv

    def _step(self):
        c = self.audc
        if c in (0x00, 0x0B):
            self._out = 1                    # a constant tone: silence unless
            return                           # something else is modulating it
        if c in (0x04, 0x05):
            self._out ^= 1                   # divide by two: a pure square
            return
        if c in (0x0C, 0x0D):
            self._three += 1                 # divide by six
            if self._three >= 3:
                self._three = 0
                self._out ^= 1
            return
        if c in (0x06, 0x0A):
            self._d31 = (self._d31 + 1) % 31
            self._out = DIV31[self._d31]
            return
        if c == 0x0E:
            self._three += 1                 # divide by 31, then by six
            if self._three < 3:
                return
            self._three = 0
            self._d31 = (self._d31 + 1) % 31
            self._out = DIV31[self._d31]
            return
        if c == 0x01:
            self._p4 = (self._p4 + 1) % 15
            self._out = POLY4[self._p4]
            return
        if c == 0x02:
            self._d31 = (self._d31 + 1) % 31
            if DIV31[self._d31]:
                self._p4 = (self._p4 + 1) % 15
                self._out = POLY4[self._p4]
            return
        if c == 0x03:
            self._p5 = (self._p5 + 1) % 31
            if POLY5[self._p5]:
                self._p4 = (self._p4 + 1) % 15
                self._out = POLY4[self._p4]
            return
        if c in (0x07, 0x09):
            self._p5 = (self._p5 + 1) % 31
            self._out = POLY5[self._p5]
            return
        if c == 0x0F:
            self._three += 1
            if self._three < 3:
                return
            self._three = 0
            self._p5 = (self._p5 + 1) % 31
            self._out = POLY5[self._p5]
            return
        # 0x08: the 9-bit polynomial, i.e. white noise
        self._p9 = (self._p9 + 1) % 511
        self._out = POLY9[self._p9]


class Sound:
    """The pair of channels, plus a buffer of samples for the host to play."""

    def __init__(self, sample_rate=31400):
        self.channels = (SoundChannel(), SoundChannel())
        self.sample_rate = sample_rate
        self._accum = 0.0
        self._step = AUDIO_CLOCK / float(sample_rate)

    def registers(self, index):
        return self.channels[index]

    def render(self, samples):
        """Produce `samples` mono samples in the -1..1 range, as a list."""
        out = []
        c0, c1 = self.channels
        for _ in range(samples):
            self._accum += self._step
            v = 0
            while self._accum >= 1.0:
                self._accum -= 1.0
                v = c0.clock() + c1.clock()
            # The TIA's output is unipolar, so centre it before handing it to
            # a sound card; otherwise every note starts with a DC thump.
            bias = c0.audv + c1.audv
            out.append((2.0 * v - bias) / 30.0)
        return out

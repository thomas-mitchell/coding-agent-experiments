"""The 160x192 picture, plus the per-scanline player overlap that feeds collisions.

The display kernels are hand-timed 6502 racing the electron beam; none of that
timing survives the port.  What does survive is *what they put on screen*, and
-- critically -- the fact that player0-vs-player1 overlap is latched while they
draw.  So drawing a scanline records which pixels each player group covered, and
`end_scanline` ANDs the two masks into the collision latch exactly as the TIA
would have.

Coordinates here are screen rows, 0 at the top.  The game's own Y counts UP from
the bottom (TOPSCN = $99 is the top); the kernel modules do that flip.
"""

WIDTH = 160
HEIGHT = 192


class Frame:
    """An indexed framebuffer of TIA colour bytes."""

    __slots__ = ("px", "collisions", "_p0", "_p1")

    def __init__(self, collisions):
        self.px = bytearray(WIDTH * HEIGHT)
        self.collisions = collisions
        self._p0 = 0
        self._p1 = 0

    def clear(self, colour=0x00):
        for i in range(len(self.px)):
            self.px[i] = colour

    # -- whole rows ----------------------------------------------------------
    def fill_row(self, row, colour):
        if 0 <= row < HEIGHT:
            base = row * WIDTH
            self.px[base:base + WIDTH] = bytes([colour]) * WIDTH

    def fill_rows(self, first, last, colour):
        for row in range(max(0, first), min(HEIGHT, last + 1)):
            self.fill_row(row, colour)

    # -- single pixels -------------------------------------------------------
    def pixel(self, row, x, colour):
        if 0 <= row < HEIGHT and 0 <= x < WIDTH:
            self.px[row * WIDTH + x] = colour

    # -- players -------------------------------------------------------------
    def player(self, row, x, bits, colour, group, double=False, reflect=False):
        """Draw one 8-bit player row at pixel `x`.

        `group` is 0 or 1 and selects which collision mask this contributes to.
        `double` is the NUSIZ "double sized player" the kernel selects for
        objects that carry an HMOVE delta stream (DIS460, asm:6858).
        """
        if bits == 0:
            return
        if reflect:
            bits = _REVERSE[bits]
        step = 2 if double else 1
        mask = 0
        for bit in range(8):
            if not (bits & (0x80 >> bit)):
                continue
            px = x + bit * step
            for k in range(step):
                if 0 <= px + k < WIDTH:
                    mask |= 1 << (px + k)
                    if 0 <= row < HEIGHT:
                        self.px[row * WIDTH + px + k] = colour
        if group:
            self._p1 |= mask
        else:
            self._p0 |= mask

    def missile(self, row, x, colour, width=1):
        """A missile or the ball: a solid run of `width` pixels."""
        for k in range(width):
            self.pixel(row, x + k, colour)

    def playfield(self, row, pf0, pf1, pf2, colour, reflect=True):
        """The 20-bit playfield expanded to 160 pixels, four pixels per bit.

        The TIA's bit order is genuinely irregular: PF0 is drawn from bit 4
        upward, PF1 from bit 7 downward, PF2 from bit 0 upward.  With CTRLPF's
        REF bit set the right half mirrors the left; without it, it repeats.
        """
        bits = []
        for i in range(4, 8):
            bits.append((pf0 >> i) & 1)
        for i in range(7, -1, -1):
            bits.append((pf1 >> i) & 1)
        for i in range(0, 8):
            bits.append((pf2 >> i) & 1)

        right = list(reversed(bits)) if reflect else bits
        for i, on in enumerate(bits + right):
            if on:
                for k in range(4):
                    self.pixel(row, i * 4 + k, colour)

    # -- collisions ----------------------------------------------------------
    def end_scanline(self):
        """Latch this scanline's player-player overlap, then reset the masks."""
        self.collisions.note_players(self._p0 & self._p1)
        self._p0 = 0
        self._p1 = 0


def _build_reverse():
    out = []
    for v in range(256):
        r = 0
        for i in range(8):
            if v & (1 << i):
                r |= 0x80 >> i
        out.append(r)
    return tuple(out)


_REVERSE = _build_reverse()

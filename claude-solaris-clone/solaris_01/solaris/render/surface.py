"""PLNSRV / TRNSRV kernels (asm:8860-9430) -- the planet and the trench.

The same vectored state machine as the space kernel, with three surface
additions:

  * a HORIZON.  Objects do not float; they sit on the ground line, which SURTB2
    gives as a function of distance (GRAPH already pinned each object's Y to it)
    and which SURTB3 / SURTB4 / SURTB5 draw as playfield.
  * the star pattern is ANDed with CROSP1, so stars only appear in the sky.
  * a background split: the sky colour above the horizon, the ground below.

The TRENCH is the same kernel with two moving walls, whose gap is at VWALL.

Objects use the surface sprite index (PTABL1..PTABL4), not the space one, and
the collision latching works exactly as it does in space -- PLN460's
`LDA MIPL / STA HHITP0+1,X / STA HITCLR` is the same sequence as DIS400's.
"""

from .. import romdata as rom
from ..state import (HCOLP1, HGRAP0, HHITP0, HHORP1, HVERP0,
                     HVERP1, MTNTOP, PLINES, PNTRP1, PROGST, STARS, TOPSCN,
                     VWALL, XDELP0)
from .layout import PLAY_TOP, SCAN_TOP
from .sprites import named, sprite_for

SURCOL = 0x62
TRNCOL = 0x84
STAR_PAGE = rom.index_for_addr(0xF300)
SURTB1 = rom.tab("SURTB1")     # the mountain silhouette
SURFACE_STAR_X = 0x88          # MAIN pins the starfield here on a surface
MOUNTAIN_ROWS = 8


def draw(mach, frame):
    m = mach.m
    trench = (m[PROGST] & 0x08) == 0
    sky = getattr(mach, "sky_colour", 0x70)
    ground = TRNCOL if trench else SURCOL
    horizon_row = PLAY_TOP + (TOPSCN - MTNTOP)

    frame.fill_rows(PLAY_TOP, horizon_row - 1, sky)
    frame.fill_rows(horizon_row, SCAN_TOP - 1, ground)

    _stars(mach, frame, horizon_row)
    if not trench:
        _mountains(mach, frame, horizon_row)
    _terrain(mach, frame, horizon_row, trench)
    if trench:
        _walls(mach, frame, horizon_row)

    p0 = _SurfaceChain(mach)
    p1 = _ship_and_photons(mach)

    for row in range(PLAY_TOP, SCAN_TOP):
        game_y = TOPSCN - (row - PLAY_TOP)
        p0.scanline(frame, row, game_y)
        _draw_p1(frame, p1, row, game_y)
        frame.end_scanline()


def _stars(mach, frame, horizon_row):
    """Stars, but only in the sky: the kernel ANDs the pattern with CROSP1, and
    on a surface MAIN pins the ball's X at $88 instead of letting it scroll."""
    m = mach.m
    for row in range(PLAY_TOP, horizon_row):
        game_y = TOPSCN - (row - PLAY_TOP)
        pattern = rom.DATA[STAR_PAGE + m[STARS] + game_y]
        # CROSP1, from SURTB1, decides which sky rows may hold a star at all
        mask = SURTB1[(m[PLINES] >> 3) & 0x07]
        if isinstance(pattern, int) and (pattern & mask & 0xFE):
            frame.pixel(row, SURFACE_STAR_X, 0xF2)


def _mountains(mach, frame, horizon_row):
    """The mountain range along the horizon.

    PLN140 points MOON2 at the SAME ground table two bytes lower and paints it
    in the mountain colour PLNSRV left in XDELP0-1, so the silhouette is the
    ground texture read at a small offset -- which is why the peaks line up with
    the ridges below them.
    """
    m = mach.m
    base = getattr(mach, "ground_pattern", None)
    if base is None:
        return
    colour = m[XDELP0 - 1]
    for k in range(MOUNTAIN_ROWS):
        row = horizon_row - MOUNTAIN_ROWS + k
        if row < PLAY_TOP:
            continue
        game_y = TOPSCN - (row - PLAY_TOP)
        pattern = rom.DATA[base - 2 + (game_y & 0x7F)]
        if not isinstance(pattern, int):
            continue
        frame.playfield(row, 0x00, pattern, pattern, colour, reflect=True)


def _terrain(mach, frame, horizon_row, trench):
    """The ground texture.

    PLN140 hands the kernel the pattern as a pointer in STARS, so the ground is
    read exactly the way the starfield is -- one byte per scanline, indexed by
    the scanline counter.  PLNSRV picks SURTB3 or SURTB4 (or SURTB5 in the
    trench) one byte apart as PLINES advances, and that one-byte offset IS the
    ground scroll.
    """
    base = getattr(mach, "ground_pattern", None)
    if base is None:
        return
    colour = TRNCOL if trench else 0x0A
    for row in range(horizon_row, SCAN_TOP):
        game_y = TOPSCN - (row - PLAY_TOP)
        pattern = rom.DATA[base + (game_y & 0x7F)]
        if not isinstance(pattern, int):
            continue
        frame.playfield(row, 0x00, pattern, pattern, colour, reflect=True)


def _walls(mach, frame, horizon_row):
    """The trench walls: two vertical faces whose gap is centred on VWALL."""
    m = mach.m
    gap = m[VWALL]
    for row in range(horizon_row, SCAN_TOP):
        depth = row - horizon_row
        half = 8 + (depth * (gap >> 3)) // 24
        left = max(0, 80 - half)
        right = min(159, 80 + half)
        for x in range(0, left):
            frame.pixel(row, x, TRNCOL)
        for x in range(right, 160):
            frame.pixel(row, x, TRNCOL)


class _SurfaceChain:
    """The four object slots, drawn in the same one-at-a-time chain the space
    kernel uses -- including the collision latch handoff."""

    def __init__(self, mach):
        self.m = mach.m
        self.collisions = mach.tia
        self.x = mach.m[PNTRP1]
        self.sprite = None
        self.top = None
        self.hx = 0
        self.done = False
        self._latch()

    def _latch(self):
        self.m[HHITP0 + 1 + self.x] = self.collisions.mipl
        self.collisions.clear()

    def scanline(self, frame, row, game_y):
        if self.done:
            return
        if self.sprite is None:
            if game_y >= self.m[HVERP0 + self.x]:
                return
            self._begin(game_y)
            if self.sprite is None:
                return
        k = self.top - game_y
        if k >= self.sprite.height:
            self._next(game_y)
            return
        frame.player(row, self.hx, self.sprite.rows[k], self.sprite.colours[k],
                     group=0, double=self.sprite.width == 2)

    def _begin(self, game_y):
        sprite = sprite_for(self.m[HGRAP0 + self.x], surface=True)
        if sprite is None:
            self._next(game_y)
            return
        self.sprite = sprite
        self.top = self.m[HVERP0 + self.x] - 2
        self.hx = self.m[HHITP0 + self.x]

    def _next(self, game_y):
        if self.x == 0:
            self.done = True
            return
        self.x -= 1
        self.sprite = None
        self._latch()
        if game_y < self.m[HVERP0 + self.x]:
            self._begin(game_y)


def _ship_and_photons(mach):
    m = mach.m
    items = []
    for slot in (2, 1):
        if m[0xBC + slot - 1] & 0x80:            # ZPOSP1-1+slot
            continue
        items.append((m[HVERP1 + slot] - 2, m[HHORP1 + slot],
                      [0x18, 0x18], [m[HCOLP1 + 1]] * 2))
    rows = named("YGR1")
    items.append((m[HVERP1] - 3, m[HHORP1], rows, [m[HCOLP1] or 0x0E] * len(rows)))
    return items


def _draw_p1(frame, items, row, game_y):
    for top, x, rows, colours in items:
        k = top - game_y
        if 0 <= k < len(rows):
            frame.player(row, x, rows[k], colours[k], group=1)
            return

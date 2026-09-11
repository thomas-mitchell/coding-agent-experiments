"""DISPLY (asm:7590) -- the space view: starfield, enemies, your ship, photons.

The kernel is two interleaved chains of fragments, each ending in `JMP (VECTPn)`,
which between them draw:

  P0 chain   the four enemy/scenery slots, from PNTRP1 downward.  All four share
             ONE hardware player, so they must already be sorted by Y and not
             overlap -- which is what BRAIN's swaps and CLOSE exist to guarantee.
  P1 chain   the shared P1+3 object (Saturn rings / big moon / warp graphic),
             then the far photon, the near photon, and your ship at the bottom.

The port keeps the chain STRUCTURE, because two things depend on it:

  * an object cannot start drawing until the one above it has finished, which is
    what makes the vertical sort matter;
  * as each P0 object's setup runs, the accumulated player-player collision
    latch is stored into the PREVIOUS object's HHITP0 and then cleared
    (DIS400, asm:6772).  HITSRV reads those bytes back as "this object touched
    you".  Getting the store points wrong would break collision detection.

The starfield is the ball, enabled per scanline from `(STARS),Y`.  That pointer
walks a page of the delta tables -- the star "pattern" is literally other tables'
bytes reused, which the assembly notes at STARTB.
"""

from .. import romdata as rom
from ..state import (HCOLP1, HGRAP0, HGRAP1, HHITP0, HHORM2, HHORP1, HVERP0,
                     MAZSTA,
                     HVERP1, PNTRP1, SCLR, STARS, THGRP1, TOPSCN, ZPOSP1)
from .layout import PLAY_TOP, SCAN_TOP
from .sprites import named, sprite_for

# `(STARS),Y` reads with STARS+1 forced to >STARTB, so the whole fetch lives in
# the page that starts at $F300 -- the NULL/RDL1/KDL/XDL delta tables, reused.
STAR_PAGE = rom.index_for_addr(0xF300)

# Your ship's three graphics, selected by THGRP1 (0 level, 1 right, 2 left).
# JOYTB9 points at `<YGRn+2`, two bytes further on than the object pointers, so
# the ship's top row lands one scanline lower: top_y = shipY - 3.
SHIP_GRAPHICS = ("YGR1", "YGR2", "YGR3")
SHIP_ANCHOR = 2
OBJECT_ANCHOR = 1

PHOTB1 = rom.tab("PHOTB1")

# Your ship's colour ramp, the block the assembly labels "; SHIP COLOR"
# (asm:9883).  Stored bottom-row-first like every other graphic stream.
SHCL = named("SHCL")

# DISPLY's special case: P1+3 types $48 and up are the big moons, which use one
# fixed colour instead of their own ramp (asm:7639).
_MOON_COLOUR = rom.DATA[rom.LABELS["CC4"] + 0x0D - 2]


def draw(mach, frame):
    m = mach.m
    # COLBK is black in space, except in the NEGATIVE UNIVERSE, where SMARTS
    # flashes it (asm:5228)
    frame.fill_rows(PLAY_TOP, SCAN_TOP - 1, _background(mach))

    p0 = _P0Chain(mach)
    p1 = _P1Chain(mach)

    for row in range(PLAY_TOP, SCAN_TOP):
        game_y = TOPSCN - (row - PLAY_TOP)
        _star(m, frame, row, game_y)
        p0.scanline(frame, row, game_y)
        p1.scanline(frame, row, game_y)
        frame.end_scanline()


def _background(mach):
    if mach.m[MAZSTA] & 0x80:
        return getattr(mach, "background_flash", 0x00)
    return 0x00


def _star(m, frame, row, game_y):
    """One ball pixel, on when the pattern bit is set.  COLPF takes the pattern
    ORed with SCLR, so the star's colour flickers with the pattern itself."""
    pattern = rom.DATA[STAR_PAGE + m[STARS] + game_y]
    if not isinstance(pattern, int) or not (pattern & 0x02):
        return
    frame.missile(row, m[HHORM2], (pattern | SCLR) & 0xFF)


class _P0Chain:
    """Slots PNTRP1..0 -- that is, object slots PNTRP1+1 down to 1 -- drawn in
    order, one at a time, exactly as the kernel's stack-pointer cursor does."""

    def __init__(self, mach):
        self.m = mach.m
        self.collisions = mach.tia
        self.x = mach.m[PNTRP1]
        self.sprite = None
        self.top = None
        self.done = False
        self._latch()

    def _latch(self):
        """DIS400: hand the accumulated collision latch to the object that just
        finished, then clear it for the next one."""
        self.m[HHITP0 + 1 + self.x] = self.collisions.mipl
        self.collisions.clear()

    def scanline(self, frame, row, game_y):
        if self.done:
            return
        if self.sprite is None:
            # waiting for the beam to reach this slot's Y
            if game_y >= self.m[HVERP0 + self.x]:
                return
            self._begin(game_y)
            if self.sprite is None:
                return
        k = self.top - game_y
        if k >= self.sprite.height:
            self._next(game_y)
            return
        frame.player(row, (self.hx + self._offsets[k]) & 0xFF,
                     self.sprite.rows[k], self.sprite.colours[k],
                     group=0, double=self.sprite.width == 2)

    def _begin(self, game_y):
        sprite = sprite_for(self.m[HGRAP0 + self.x])
        if sprite is None:
            self._next(game_y)          # DIS201's "NO DISPLAY" path
            return
        self.sprite = sprite
        self._offsets = sprite.x_offsets()
        self.top = self.m[HVERP0 + self.x] - 1 - OBJECT_ANCHOR
        # DIS400 latches HHITP0 into MOON2 as the object's screen X *before* the
        # next object's setup overwrites that byte with a collision latch.
        self.hx = self.m[HHITP0 + self.x]

    def _next(self, game_y):
        if self.x == 0:
            self.done = True
            return
        self.x -= 1
        self.sprite = None
        self._latch()
        # the next object may already be due on this very scanline
        if game_y < self.m[HVERP0 + self.x]:
            self._begin(game_y)


class _P1Chain:
    """P1+3, then the far photon, the near photon, and your ship."""

    def __init__(self, mach):
        m = mach.m
        self.m = m
        self.items = []

        shared = m[HGRAP1 + 3]
        sprite = sprite_for(shared)
        if sprite is not None:
            colours = ([_MOON_COLOUR] * sprite.height
                       if (shared & 0x7F) >= 0x48 else sprite.colours)
            self.items.append((m[HVERP1 + 3] - 1 - OBJECT_ANCHOR, m[HHORP1 + 3],
                               sprite.rows, colours, sprite.width == 2,
                               sprite.x_offsets()))

        for slot in (2, 1):
            rows = _photon_rows(m, slot)
            if rows:
                self.items.append((m[HVERP1 + slot] - 1 - OBJECT_ANCHOR,
                                   m[HHORP1 + slot], rows,
                                   [m[HCOLP1 + 1]] * len(rows), False,
                                   [0] * len(rows)))

        rows = named(SHIP_GRAPHICS[min(m[THGRP1], 2)])
        # DIS730 latches HCOLP1 into COLPM1 just before the ship draws, and
        # DIS500 then takes a colour per scanline from the ship's own ramp.
        colours = [m[HCOLP1]] + [SHCL[k] for k in range(len(rows) - 1)]
        self.items.append((m[HVERP1] - 1 - SHIP_ANCHOR, m[HHORP1], rows,
                           colours, False, [0] * len(rows)))
        self.index = 0

    def scanline(self, frame, row, game_y):
        while self.index < len(self.items):
            top, x, rows, colours, double, offs = self.items[self.index]
            if game_y > top:
                return                  # not reached yet
            k = top - game_y
            if k < len(rows):
                frame.player(row, (x + offs[k]) & 0xFF, rows[k], colours[k],
                             group=1, double=double)
                return
            self.index += 1             # finished; the next one may start here


# PHOTN1 stores `PHOTB1[zoom] - HVERP1` into HGRAP1+slot, so adding the Y back
# recovers the pointer's low byte, and that identifies the graphic exactly --
# no need to re-derive the zoom step the kernel already resolved.
_PHOTON_BY_LOW = {rom.low(e): e.name
                  for e in (PHOTB1[i] for i in range(9))
                  if not isinstance(e, int)}


def _photon_rows(m, slot):
    """Your photon's graphic, or None when that shot is switched off."""
    if m[ZPOSP1 - 1 + slot] & 0x80:
        return None
    ptr = (m[HGRAP1 + slot] + m[HVERP1 + slot]) & 0xFF
    label = _PHOTON_BY_LOW.get(ptr)
    return named(label) if label else None

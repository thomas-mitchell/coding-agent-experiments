"""The sprite database: MTABL1..MTABL4 and PTABL1..PTABL4 turned into shapes.

There are two of these indexes, because the space kernel and the surface kernel
have completely different art for the same class numbers:

  * SPACE   MTABL1/MTABL3 the graphic, MTABL2 the colour ramp, MTABL4 an HMOVE
            delta stream (asm:7504-7573).  96 entries, type bytes $00..$5F.
  * SURFACE PTABL1/PTABL3 the graphic, PTABL2 the colour ramp, PTABL4 a NUSIZ0
            value giving the width directly (asm:9753-9845).  72 entries, type
            bytes $00..$47.

Reading direction
-----------------
All the streams are stored BOTTOM ROW FIRST with the label sitting AFTER the
data, and the kernel pre-biases each pointer by the object's Y.  Working through
DIS150 -> DIS102 (asm:6552-6570): the kernel waits for Y to drop below the
object's Y, then DEYs once more before its first fetch, so the first address is

    MTABL1[type] - 2  ==  LABEL + 1 - 2  ==  LABEL - 1

which is the last byte of the block, i.e. the sprite's TOP row.  Successive rows
walk backwards to lower addresses, and the $00 pad at the start of the block is
what the kernel's `BEQ` sees as "this object is finished".  Colour ramps and
delta streams are read the same way, so row k of every stream is at `base - k`.

Delta streams
-------------
Each entry is written to HMP0 and strobed, so it nudges the player sideways by
one HMOVE step *and the nudges accumulate down the object*.  That is how
craters, rings and explosions get wider than the eight pixels a player gives
you.  Only the high nibble matters, as a signed 4-bit value, and HMOVE moves the
object LEFT by that amount.

Objects whose delta stream lives at KDL8 or later are also drawn double width
(DIS460's `CMP #<KDL8-1` then NUSIZ0 = $0D, asm:6858).
"""

from .. import romdata as rom

# The threshold DIS460 compares MTABL4 against.  Everything from the planet
# killer's delta stream onward is a "big" object drawn at double width.
_DOUBLE_FROM = rom.LABELS["KDL8"] - 1


def _stream_base(entry):
    """Where row 0 (the top row) of a stream lives in the data.

    `entry` is an R(label, offset) from one of the master tables; the kernel's
    first fetch is two bytes below it.  A plain 0 means "no stream".
    """
    if isinstance(entry, int):
        return None
    return rom.LABELS[entry.name] + entry.offset - 2


def _read_down(base, count):
    return [rom.DATA[base - k] for k in range(count)]


class Sprite:
    """One object type's drawable shape."""

    __slots__ = ("rows", "colours", "deltas", "width", "height")

    def __init__(self, rows, colours, deltas, width):
        self.rows = rows
        self.colours = colours
        self.deltas = deltas
        self.width = width          # 1 = normal player, 2 = double sized
        self.height = len(rows)

    def x_offsets(self):
        """The accumulated horizontal offset of each row, in pixels.

        HMOVE moves the player LEFT by the signed high nibble, so a stream of
        $F0 bytes walks the object steadily to the right.
        """
        if not self.deltas:
            return [0] * self.height
        offsets, x = [], 0
        for d in self.deltas:
            hm = (d >> 4) & 0x0F
            if hm >= 8:
                hm -= 16
            x -= hm
            offsets.append(x)
        return offsets


def _rows_at(base):
    rows = []
    k = 0
    while True:
        v = rom.DATA[base - k]
        if not isinstance(v, int) or v == 0:
            break                        # the $00 pad terminates the object
        rows.append(v)
        k += 1
    return rows


def _build_space(type_byte, gt, ct, dt):
    base = _stream_base(gt[type_byte])
    if base is None:
        return None                      # an unused type byte
    rows = _rows_at(base)
    if not rows:
        return None

    cbase = _stream_base(ct[type_byte])
    colours = _read_down(cbase, len(rows)) if cbase is not None else [0x0E] * len(rows)

    entry = dt[type_byte]
    dbase = _stream_base(entry)
    if dbase is None:
        return Sprite(rows, colours, None, 1)
    deltas = _read_down(dbase, len(rows))
    addr = rom.LABELS[entry.name] + entry.offset
    return Sprite(rows, colours, deltas, 2 if addr >= _DOUBLE_FROM else 1)


def _build_surface(type_byte, gt, ct, nusiz):
    base = _stream_base(gt[type_byte])
    if base is None:
        return None
    rows = _rows_at(base)
    if not rows:
        return None
    cbase = _stream_base(ct[type_byte])
    colours = _read_down(cbase, len(rows)) if cbase is not None else [0x0E] * len(rows)
    # PTABL4 is written straight to NUSIZ0; bits 0..2 select the player size,
    # and 5 is the "double sized player" the bigger surface objects use.
    width = 2 if (nusiz[type_byte] & 0x07) == 0x05 else 1
    return Sprite(rows, colours, None, width)


_MTABL1, _MTABL2, _MTABL4 = rom.tab("MTABL1"), rom.tab("MTABL2"), rom.tab("MTABL4")
_PTABL1, _PTABL2, _PTABL4 = rom.tab("PTABL1"), rom.tab("PTABL2"), rom.tab("PTABL4")

# MTABL1 runs $00..$5F (96 entries: twelve classes of eight frames);
# PTABL1 runs $00..$47 (nine classes).  A type byte outside its table belongs
# to the other screen mode and is never looked up there.
SPACE_SPRITES = [_build_space(t, _MTABL1, _MTABL2, _MTABL4) for t in range(96)]
SURFACE_SPRITES = [_build_surface(t, _PTABL1, _PTABL2, _PTABL4) for t in range(72)]


def sprite_for(type_byte, surface=False):
    """The sprite for an object type, or None when the slot is off screen,
    empty, or the type has no art in this screen mode."""
    if type_byte & 0x80:
        return None                      # bit 7 = off screen / inactive
    t = type_byte & 0x7F
    table = SURFACE_SPRITES if surface else SPACE_SPRITES
    return table[t] if t < len(table) else None


def named(label, count=None):
    """A standalone graphic addressed by label, for the shapes the kernels draw
    directly rather than through the master tables (your ship, the photons, the
    chart icons, the digits)."""
    return _rows_at(rom.LABELS[label] - 1) if count is None else \
        _read_down(rom.LABELS[label] - 1, count)

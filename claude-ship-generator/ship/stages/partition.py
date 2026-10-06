"""Stage 4: rectangular space partitioning.

Rather than scattering rooms and joining them up, every block is recursively
subdivided until all of its space belongs to some compartment. Split lines
prefer the structural module grid so bulkheads line up across the ship.
"""

from __future__ import annotations

from .. import tiles as T
from ..model import Block, Rect, Room, Ship, ZoneKind
from .deck import MODULE

MIN_INNER = 3  # smallest interior dimension of a room
MAX_AREA = 48  # interior area above which a block is always split
SOFT_MAX_AREA = 90  # below this, a block may randomly stay whole
KEEP_CHANCE = 0.35
ALIGN_CHANCE = 0.6
AREA_SCALE = {ZoneKind.CARGO: 1.8, ZoneKind.ENGINEERING: 1.5, ZoneKind.COMMAND: 1.2}


def _split_lines(lo: int, hi: int) -> list[int]:
    """Wall positions strictly inside [lo, hi] leaving MIN_INNER on both sides."""
    return list(range(lo + MIN_INNER + 1, hi - MIN_INNER))


def _subdivide(rng, rect: Rect, scale: float, out: list[Rect]) -> None:
    iw, ih = rect.inner_w, rect.inner_h
    xs, ys = _split_lines(rect.x, rect.x2), _split_lines(rect.y, rect.y2)
    thin = max(iw, ih) > 3 * min(iw, ih)
    area = rect.inner_area
    if not xs and not ys:
        out.append(rect)
        return
    if not thin and (area <= MAX_AREA * scale or (area <= SOFT_MAX_AREA * scale and rng.random() < KEEP_CHANCE)):
        out.append(rect)
        return

    if xs and ys:
        vertical = iw > ih if abs(iw - ih) > 2 else rng.random() < 0.5
    else:
        vertical = bool(xs)
    lines = xs if vertical else ys
    aligned = [v for v in lines if v % MODULE == 0]
    if aligned and rng.random() < ALIGN_CHANCE:
        at = rng.choice(aligned)
    else:
        # Average of two picks biases toward the middle, avoiding slivers.
        at = lines[(rng.randrange(len(lines)) + rng.randrange(len(lines))) // 2]

    if vertical:
        a, b = Rect(rect.x, rect.y, at, rect.y2), Rect(at, rect.y, rect.x2, rect.y2)
    else:
        a, b = Rect(rect.x, rect.y, rect.x2, at), Rect(rect.x, at, rect.x2, rect.y2)
    _subdivide(rng, a, scale, out)
    _subdivide(rng, b, scale, out)


def partition(rng, ship: Ship, blocks: list[Block]) -> None:
    for block in blocks:
        leaves: list[Rect] = []
        _subdivide(rng, block.rect, AREA_SCALE.get(block.zone, 1.0), leaves)
        for rect in leaves:
            room = Room(id=len(ship.rooms) + 1, rect=rect, zone=block.zone)
            ship.rooms.append(room)
            ship.tiles[rect.inner_slices()] = T.FLOOR

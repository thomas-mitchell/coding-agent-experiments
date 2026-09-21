"""Turning a LayoutDelta into movement.

The rearrangement is not something to hide. A card is drawn, the cards around
it slide apart, the roads redraw themselves, and the new card drops onto the
board. Each stage sits in the 300-600ms band -- long enough to read, short
enough that nobody watches the solver think.
"""

from __future__ import annotations

from dataclasses import dataclass

from .slots import SlotGrid

REMOVE_MS = 320.0
MOVE_MS = 450.0
ADD_MS = 400.0
PATH_MS = 350.0
PATH_LEAD_MS = 160.0  # roads start redrawing slightly before the cards settle


def ease_out_cubic(t: float) -> float:
    return 1.0 - (1.0 - t) ** 3


def ease_in_cubic(t: float) -> float:
    return t * t * t


def ease_out_back(t: float) -> float:
    c1, c3 = 1.70158, 2.70158
    return 1.0 + c3 * (t - 1) ** 3 + c1 * (t - 1) ** 2


def _phase(now: float, start: float, duration: float) -> float:
    if duration <= 0:
        return 1.0
    return max(0.0, min(1.0, (now - start) / duration))


@dataclass
class CardState:
    pos: tuple[float, float]
    alpha: float = 1.0
    scale: float = 1.0
    lift: float = 0.0  # 0..1, how far off the board the card is (drives shadow)


@dataclass
class _Move:
    start_px: tuple[float, float]
    end_px: tuple[float, float]
    start: float


@dataclass
class _Fade:
    pos: tuple[float, float]
    start: float


class BoardAnimator:
    def __init__(self, grid: SlotGrid) -> None:
        self.grid = grid
        self.time = 0.0
        self.total = 0.0
        self.moves: dict[str, _Move] = {}
        self.adds: dict[str, _Fade] = {}
        self.ghosts: dict[str, _Fade] = {}
        self.path_start = 0.0

    # -- building ---------------------------------------------------------

    def apply(self, delta) -> None:
        """Schedule the animation for a layout change."""
        self.time = 0.0
        self.moves.clear()
        self.adds.clear()
        self.ghosts.clear()

        cursor = 0.0
        if delta.removed:
            for loc_id, slot in delta.removed.items():
                self.ghosts[loc_id] = _Fade(self.grid.slot_to_pixel(slot), cursor)
            cursor += REMOVE_MS

        move_start = cursor
        if delta.moved:
            for loc_id, (old, new) in delta.moved.items():
                self.moves[loc_id] = _Move(
                    self.grid.slot_to_pixel(old),
                    self.grid.slot_to_pixel(new),
                    move_start,
                )
            cursor += MOVE_MS

        add_start = cursor
        if delta.added:
            for loc_id, slot in delta.added.items():
                self.adds[loc_id] = _Fade(self.grid.slot_to_pixel(slot), add_start)
            cursor += ADD_MS

        self.path_start = max(0.0, cursor - PATH_LEAD_MS)
        self.total = max(cursor, self.path_start + PATH_MS)

    def update(self, dt_ms: float) -> None:
        if self.busy:
            self.time = min(self.total, self.time + dt_ms)

    def finish(self) -> None:
        self.time = self.total

    @property
    def busy(self) -> bool:
        return self.time < self.total

    # -- queries ----------------------------------------------------------

    def card_state(self, loc_id: str, slot) -> CardState:
        now = self.time
        ghost = self.ghosts.get(loc_id)
        if ghost is not None:
            p = _phase(now, ghost.start, REMOVE_MS)
            return CardState(ghost.pos, alpha=1.0 - p, scale=1.0 - 0.18 * p, lift=p)

        pos = self.grid.slot_to_pixel(slot)
        move = self.moves.get(loc_id)
        if move is not None:
            p = ease_out_cubic(_phase(now, move.start, MOVE_MS))
            pos = (
                move.start_px[0] + (move.end_px[0] - move.start_px[0]) * p,
                move.start_px[1] + (move.end_px[1] - move.start_px[1]) * p,
            )
            return CardState(pos, lift=0.35 * (1.0 - abs(2 * p - 1)))

        add = self.adds.get(loc_id)
        if add is not None:
            raw = _phase(now, add.start, ADD_MS)
            if raw <= 0.0:
                return CardState(pos, alpha=0.0, scale=1.0)
            p = ease_out_cubic(raw)
            drop = 1.0 - p
            return CardState(
                (pos[0], pos[1] - 26.0 * drop),
                alpha=min(1.0, raw * 2.2),
                scale=1.0 + 0.16 * drop,
                lift=drop,
            )
        return CardState(pos)

    @property
    def new_path_alpha(self) -> float:
        return ease_out_cubic(_phase(self.time, self.path_start, PATH_MS))

    @property
    def old_path_alpha(self) -> float:
        """The previous roads, fading out so as to overlap the new ones.

        They have to outlast the gap before the new paths start drawing, or the
        board is briefly left with no roads on it at all.
        """
        if not self.busy:
            return 0.0
        fade_start = max(0.0, self.path_start - PATH_LEAD_MS)
        return 1.0 - _phase(self.time, fade_start, PATH_MS * 0.75)

    def is_ghost(self, loc_id: str) -> bool:
        return loc_id in self.ghosts

    def ghost_ids(self) -> list[str]:
        return list(self.ghosts)

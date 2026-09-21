"""The invisible grid of card slots.

Cards are never placed at arbitrary coordinates. They are assigned to integer
slots, and the grid is the only thing that knows how a slot becomes pixels.
The gutters between slots are deliberately generous -- that is where the
connection paths get routed.
"""

from __future__ import annotations

CARD_W = 168
CARD_H = 112
GUTTER_X = 72
GUTTER_Y = 64

PITCH_X = CARD_W + GUTTER_X  # 240
PITCH_Y = CARD_H + GUTTER_Y  # 176

# Slot-space distances are compared against each other constantly, so a step
# sideways and a step down should mean roughly the same thing. Rows are shorter
# than columns, so scale the row axis when measuring.
ROW_ASPECT = PITCH_Y / PITCH_X

Slot = tuple[int, int]

ORTHO: tuple[Slot, ...] = ((1, 0), (-1, 0), (0, 1), (0, -1))


class SlotGrid:
    """A bounded lattice of card slots centred on (0, 0)."""

    def __init__(self, half_cols: int = 6, half_rows: int = 4) -> None:
        self.half_cols = half_cols
        self.half_rows = half_rows

    # -- geometry ---------------------------------------------------------

    def slot_to_pixel(self, slot: Slot) -> tuple[float, float]:
        """Centre of a slot in world pixels."""
        col, row = slot
        return (col * PITCH_X, row * PITCH_Y)

    def pixel_to_slot(self, pos: tuple[float, float]) -> Slot:
        x, y = pos
        return (round(x / PITCH_X), round(y / PITCH_Y))

    def card_rect(self, slot: Slot) -> tuple[float, float, float, float]:
        """``(left, top, width, height)`` of the card occupying a slot."""
        cx, cy = self.slot_to_pixel(slot)
        return (cx - CARD_W / 2, cy - CARD_H / 2, CARD_W, CARD_H)

    def board_pixel_rect(self, slots) -> tuple[float, float, float, float]:
        """Bounding rect in world pixels covering every given slot's card."""
        slots = list(slots)
        if not slots:
            return (-CARD_W / 2, -CARD_H / 2, CARD_W, CARD_H)
        lefts, tops, rights, bottoms = [], [], [], []
        for slot in slots:
            l, t, w, h = self.card_rect(slot)
            lefts.append(l)
            tops.append(t)
            rights.append(l + w)
            bottoms.append(t + h)
        left, top = min(lefts), min(tops)
        return (left, top, max(rights) - left, max(bottoms) - top)

    # -- slot-space metrics ----------------------------------------------

    @staticmethod
    def distance(a: Slot, b: Slot) -> float:
        """Euclidean distance in slot units, corrected for the row pitch."""
        dx = a[0] - b[0]
        dy = (a[1] - b[1]) * ROW_ASPECT
        return (dx * dx + dy * dy) ** 0.5

    @staticmethod
    def manhattan(a: Slot, b: Slot) -> int:
        return abs(a[0] - b[0]) + abs(a[1] - b[1])

    # -- bounds -----------------------------------------------------------

    def contains(self, slot: Slot) -> bool:
        col, row = slot
        return abs(col) <= self.half_cols and abs(row) <= self.half_rows

    def outside_by(self, slot: Slot) -> int:
        """How far a slot falls beyond the board edge (0 when inside)."""
        col, row = slot
        return max(0, abs(col) - self.half_cols) + max(0, abs(row) - self.half_rows)

    def expand(self, amount: int = 1) -> None:
        self.half_cols += amount
        self.half_rows += amount

    def all_slots(self) -> list[Slot]:
        return [
            (c, r)
            for r in range(-self.half_rows, self.half_rows + 1)
            for c in range(-self.half_cols, self.half_cols + 1)
        ]

    # -- neighbourhoods ---------------------------------------------------

    @staticmethod
    def ring(slot: Slot, radius: int) -> list[Slot]:
        """Slots at exactly Chebyshev ``radius`` from ``slot``."""
        col, row = slot
        if radius <= 0:
            return [slot]
        out: list[Slot] = []
        for d in range(-radius, radius + 1):
            out.append((col + d, row - radius))
            out.append((col + d, row + radius))
        for d in range(-radius + 1, radius):
            out.append((col - radius, row + d))
            out.append((col + radius, row + d))
        return out

    def within(self, slot: Slot, radius: int, include_self: bool = True) -> list[Slot]:
        out: list[Slot] = [slot] if include_self else []
        for r in range(1, radius + 1):
            out.extend(self.ring(slot, r))
        return out

    def free_slots_near(
        self,
        occupied,
        anchors,
        radius: int = 3,
        allow_outside: bool = False,
    ) -> list[Slot]:
        """Unoccupied slots within ``radius`` of any anchor, nearest first.

        Ordered deterministically so the same board always yields the same
        candidate list -- the solver must not wobble between runs.
        """
        occupied = set(occupied)
        anchors = list(anchors)
        if not anchors:
            return []
        seen: set[Slot] = set()
        out: list[Slot] = []
        for anchor in anchors:
            for slot in self.within(anchor, radius):
                if slot in seen or slot in occupied:
                    continue
                if not allow_outside and not self.contains(slot):
                    continue
                seen.add(slot)
                out.append(slot)
        centroid = (
            sum(a[0] for a in anchors) / len(anchors),
            sum(a[1] for a in anchors) / len(anchors),
        )
        out.sort(key=lambda s: (self.distance(s, centroid), s[1], s[0]))
        return out

    def occupied_slots_near(self, placements, anchors, radius: int = 2) -> list[Slot]:
        """Slots that currently hold a card, near the anchors, nearest first."""
        by_slot = {slot: loc_id for loc_id, slot in placements.items()}
        anchors = list(anchors)
        seen: set[Slot] = set()
        out: list[Slot] = []
        for anchor in anchors:
            for slot in self.within(anchor, radius):
                if slot in seen or slot not in by_slot:
                    continue
                seen.add(slot)
                out.append(slot)
        centroid = (
            sum(a[0] for a in anchors) / len(anchors),
            sum(a[1] for a in anchors) / len(anchors),
        ) if anchors else (0.0, 0.0)
        out.sort(key=lambda s: (self.distance(s, centroid), s[1], s[0]))
        return out

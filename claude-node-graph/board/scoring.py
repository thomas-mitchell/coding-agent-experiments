"""The cost model that decides whether a layout is any good.

    cost = edge_length
         + edge_crossing
         + edge_over_card
         + card_overlap
         + board_boundary
         + movement
         + region

``movement`` is weighted heavily on purpose. The solver is not answering "what
is the prettiest arrangement of this graph?" -- it is answering "what is the
least disruptive change that accommodates this new card?". Preserving the
player's mental map of the board beats mathematical elegance every time.
"""

from __future__ import annotations

from dataclasses import dataclass

from .slots import ROW_ASPECT, Slot, SlotGrid

# Tunable weights. The debug overlay (F1) shows the resulting breakdown.
W_EDGE_LENGTH = 4.0
W_EDGE_CROSSING = 9.0
W_EDGE_OVER_CARD = 8.0
W_CARD_OVERLAP = 1_000_000.0
W_BOARD_BOUNDARY = 8.0
W_COMPACTNESS = 0.9
W_MOVEMENT = 45.0
W_REGION = 4.0
W_GROUP = 1.5


@dataclass
class CostBreakdown:
    edge_length: float = 0.0
    edge_crossing: float = 0.0
    edge_over_card: float = 0.0
    card_overlap: float = 0.0
    board_boundary: float = 0.0
    movement: float = 0.0
    region: float = 0.0

    # Raw counts, kept for the debug overlay and for the tier-1 accept test.
    longest_edge: float = 0.0
    crossings: int = 0
    moved_cards: int = 0

    @property
    def total(self) -> float:
        return (
            self.edge_length
            + self.edge_crossing
            + self.edge_over_card
            + self.card_overlap
            + self.board_boundary
            + self.movement
            + self.region
        )

    def rows(self) -> list[tuple[str, float]]:
        return [
            ("edge length", self.edge_length),
            ("crossings", self.edge_crossing),
            ("over cards", self.edge_over_card),
            ("overlap", self.card_overlap),
            ("boundary", self.board_boundary),
            ("movement", self.movement),
            ("region", self.region),
            ("TOTAL", self.total),
        ]


def _point(slot) -> tuple[float, float]:
    """Slot centre in aspect-corrected slot space."""
    return (float(slot[0]), slot[1] * ROW_ASPECT)


def _segments_cross(p1, p2, p3, p4) -> bool:
    """Proper crossing test, ignoring segments that merely share an endpoint."""
    if p1 in (p3, p4) or p2 in (p3, p4):
        return False
    # Cheap rejection first: this runs hundreds of thousands of times per solve.
    if (
        max(p1[0], p2[0]) < min(p3[0], p4[0])
        or max(p3[0], p4[0]) < min(p1[0], p2[0])
        or max(p1[1], p2[1]) < min(p3[1], p4[1])
        or max(p3[1], p4[1]) < min(p1[1], p2[1])
    ):
        return False

    def orient(a, b, c) -> float:
        return (b[0] - a[0]) * (c[1] - a[1]) - (b[1] - a[1]) * (c[0] - a[0])

    d1 = orient(p3, p4, p1)
    d2 = orient(p3, p4, p2)
    d3 = orient(p1, p2, p3)
    d4 = orient(p1, p2, p4)
    return ((d1 > 0) != (d2 > 0)) and ((d3 > 0) != (d4 > 0))


def _segment_hits_slot(p1, p2, slot: Slot) -> bool:
    """Does a path between two cards run straight over a third card?"""
    cx, cy = _point(slot)
    # Card half-extents in aspect-corrected slot space, inset so that merely
    # grazing a corner does not count -- the real road is routed around the
    # card anyway, so this term measures awkwardness, not impossibility.
    hw = 0.30
    hh = 0.30 * ROW_ASPECT
    left, right = cx - hw, cx + hw
    top, bottom = cy - hh, cy + hh

    # Liang-Barsky clip of the segment against the card box.
    dx = p2[0] - p1[0]
    dy = p2[1] - p1[1]
    t0, t1 = 0.0, 1.0
    clips = (
        (-dx, p1[0] - left),
        (dx, right - p1[0]),
        (-dy, p1[1] - top),
        (dy, bottom - p1[1]),
    )
    for p, q in clips:
        if p == 0:
            if q < 0:
                return False
            continue
        t = q / p
        if p < 0:
            if t > t1:
                return False
            t0 = max(t0, t)
        else:
            if t < t0:
                return False
            t1 = min(t1, t)
    return t0 <= t1


_REGION_RULES = {
    "north": lambda c, r: max(0.0, r + 1.0),
    "south": lambda c, r: max(0.0, 1.0 - r),
    "west": lambda c, r: max(0.0, c + 1.0),
    "east": lambda c, r: max(0.0, 1.0 - c),
    "centre": lambda c, r: abs(c) + abs(r),
    "center": lambda c, r: abs(c) + abs(r),
}


def placement_cost(
    placements: dict[str, Slot],
    graph,
    grid: SlotGrid,
    previous: dict[str, Slot] | None = None,
    focus: set[str] | None = None,
) -> CostBreakdown:
    """Score a complete candidate layout.

    ``focus`` restricts the (expensive) edge terms to edges touching those
    locations. Every candidate for a single insertion is scored with the same
    focus, so their relative ordering is unaffected -- it just avoids
    re-measuring the half of the board that nobody touched.
    """
    cost = CostBreakdown()
    links = graph.links()

    # -- overlap: two cards in one slot is not a layout, it is a bug -------
    by_slot: dict[Slot, list[str]] = {}
    for loc_id, slot in placements.items():
        by_slot.setdefault(slot, []).append(loc_id)
    duplicates = sum(len(ids) - 1 for ids in by_slot.values() if len(ids) > 1)
    cost.card_overlap = duplicates * W_CARD_OVERLAP

    # -- edge length ------------------------------------------------------
    scored = []
    for a, b, _two_way in links:
        if a not in placements or b not in placements:
            continue
        pa = _point(placements[a])
        pb = _point(placements[b])
        scored.append((a, b, pa, pb))
        if focus is not None and a not in focus and b not in focus:
            continue
        d = grid.distance(placements[a], placements[b])
        loc_a = graph.locations.get(a)
        loc_b = graph.locations.get(b)
        ideal = max(
            getattr(loc_a, "preferred_distance", 1) or 1,
            getattr(loc_b, "preferred_distance", 1) or 1,
        )
        over = max(0.0, d - ideal)
        cost.edge_length += W_EDGE_LENGTH * (over ** 1.6)
        cost.longest_edge = max(cost.longest_edge, d)

    # -- crossings, and paths running over cards --------------------------
    points = [(loc_id, slot, _point(slot)) for loc_id, slot in placements.items()]
    crossings = 0
    for i, (a1, b1, p1, p2) in enumerate(scored):
        interesting = focus is None or a1 in focus or b1 in focus
        rest = scored[i + 1:]
        if interesting:
            for a2, b2, p3, p4 in rest:
                if _segments_cross(p1, p2, p3, p4):
                    crossings += 1
            # Only cards whose centre falls near this road can be run over.
            lo_x, hi_x = min(p1[0], p2[0]) - 0.5, max(p1[0], p2[0]) + 0.5
            lo_y, hi_y = min(p1[1], p2[1]) - 0.5, max(p1[1], p2[1]) + 0.5
            for loc_id, slot, centre in points:
                if loc_id in (a1, b1):
                    continue
                if not (lo_x <= centre[0] <= hi_x and lo_y <= centre[1] <= hi_y):
                    continue
                if _segment_hits_slot(p1, p2, slot):
                    cost.edge_over_card += W_EDGE_OVER_CARD
        else:
            # Still count crossings caused *by* a focused edge against this one.
            for a2, b2, p3, p4 in rest:
                if (a2 in focus or b2 in focus) and _segments_cross(p1, p2, p3, p4):
                    crossings += 1
    cost.crossings = crossings
    cost.edge_crossing = crossings * W_EDGE_CROSSING

    # -- board boundary and compactness -----------------------------------
    outside = sum(grid.outside_by(slot) for slot in placements.values())
    cost.board_boundary = outside * W_BOARD_BOUNDARY
    if placements:
        cols = [s[0] for s in placements.values()]
        rows = [s[1] for s in placements.values()]
        span = (max(cols) - min(cols) + 1) * (max(rows) - min(rows) + 1)
        slack = max(0.0, span - len(placements))
        cost.board_boundary += W_COMPACTNESS * slack

    # -- movement: the term that keeps the board still --------------------
    if previous:
        moved = 0
        total = 0
        for loc_id, slot in placements.items():
            old = previous.get(loc_id)
            if old is None or old == slot:
                continue
            moved += 1
            total += grid.manhattan(old, slot)
        cost.moved_cards = moved
        cost.movement = total * W_MOVEMENT

    # -- soft hints -------------------------------------------------------
    groups: dict[str, list[Slot]] = {}
    for loc_id, slot in placements.items():
        loc = graph.locations.get(loc_id)
        if loc is None:
            continue
        rule = _REGION_RULES.get((loc.region or "").lower())
        if rule is not None:
            cost.region += W_REGION * rule(slot[0], slot[1])
        if loc.layout_group:
            groups.setdefault(loc.layout_group, []).append(slot)
    for slots in groups.values():
        if len(slots) < 2:
            continue
        cx = sum(s[0] for s in slots) / len(slots)
        cy = sum(s[1] for s in slots) / len(slots)
        cost.region += W_GROUP * sum(grid.distance(s, (cx, cy)) for s in slots)

    return cost

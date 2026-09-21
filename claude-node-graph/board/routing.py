"""Edge routing: turning "these two cards are connected" into a printed road.

Placement and routing are separate problems. Once the cards are in slots, the
gutters between them form a street network; each connection is routed through
it with A*, preferring straight runs and avoiding lanes other roads already
use, so paths read as deliberate rather than as a tangle of straight lines.
"""

from __future__ import annotations

import heapq
from dataclasses import dataclass, field

from .slots import CARD_H, CARD_W, PITCH_X, PITCH_Y, Slot, SlotGrid

LANE_DIV = 4
LANE_X = PITCH_X / LANE_DIV  # 60px
LANE_Y = PITCH_Y / LANE_DIV  # 44px

# A card blocks the 3x3 block of lane nodes around its slot centre, which
# leaves exactly one clear lane running down the middle of each gutter.
BLOCK_RADIUS = 1

STEP_TURN_PENALTY = 1.15
LANE_REUSE_PENALTY = 2.2
CORNER_RADIUS = 20.0

DIRS = ((1, 0), (-1, 0), (0, 1), (0, -1))

Lane = tuple[int, int]


@dataclass
class Route:
    a: str
    b: str
    two_way: bool
    points: list[tuple[float, float]] = field(default_factory=list)
    routed: bool = True


def lane_to_pixel(lane: Lane) -> tuple[float, float]:
    return (lane[0] * LANE_X, lane[1] * LANE_Y)


def slot_to_lane(slot: Slot) -> Lane:
    return (slot[0] * LANE_DIV, slot[1] * LANE_DIV)


class Router:
    """Routes every connection on the board, in a stable order."""

    def __init__(self, grid: SlotGrid) -> None:
        self.grid = grid

    def routes(self, graph, placements: dict[str, Slot]) -> list[Route]:
        blocked: set[Lane] = set()
        for slot in placements.values():
            cx, cy = slot_to_lane(slot)
            for di in range(-BLOCK_RADIUS, BLOCK_RADIUS + 1):
                for dj in range(-BLOCK_RADIUS, BLOCK_RADIUS + 1):
                    blocked.add((cx + di, cy + dj))

        if placements:
            lanes = [slot_to_lane(s) for s in placements.values()]
            lo = (min(l[0] for l in lanes) - 10, min(l[1] for l in lanes) - 10)
            hi = (max(l[0] for l in lanes) + 10, max(l[1] for l in lanes) + 10)
        else:
            lo, hi = (0, 0), (0, 0)

        usage: dict[Lane, int] = {}
        out: list[Route] = []
        for a, b, two_way in graph.links():
            if a not in placements or b not in placements:
                continue
            src, dst = placements[a], placements[b]
            lanes = self._astar(src, dst, blocked, usage, lo, hi)
            if lanes:
                for lane in lanes:
                    usage[lane] = usage.get(lane, 0) + 1
                points = [lane_to_pixel(l) for l in lanes]
                points = _drop_collinear(points)
                points = self._attach_ends(src, dst, points)
                out.append(Route(a, b, two_way, _round_corners(points), routed=True))
            else:
                sa = self.grid.slot_to_pixel(src)
                sb = self.grid.slot_to_pixel(dst)
                points = [_card_anchor(sa, sb), _card_anchor(sb, sa)]
                out.append(Route(a, b, two_way, points, routed=False))
        return out

    # -- routing ----------------------------------------------------------

    def _ring_nodes(self, slot: Slot, blocked: set[Lane]) -> list[Lane]:
        """The free lane nodes hugging a card -- where a road can join it."""
        cx, cy = slot_to_lane(slot)
        r = BLOCK_RADIUS + 1
        out = []
        for di in range(-r, r + 1):
            for dj in range(-r, r + 1):
                if max(abs(di), abs(dj)) != r:
                    continue
                node = (cx + di, cy + dj)
                if node not in blocked:
                    out.append(node)
        return out

    @staticmethod
    def _h(node: Lane, goal: Lane) -> float:
        return (abs(node[0] - goal[0]) * LANE_X + abs(node[1] - goal[1]) * LANE_Y) / 50.0

    def _astar(self, src, dst, blocked, usage, lo, hi) -> list[Lane] | None:
        starts = self._ring_nodes(src, blocked)
        goals = set(self._ring_nodes(dst, blocked))
        if not starts or not goals:
            return None
        goal_centre = slot_to_lane(dst)

        open_set: list[tuple[float, float, Lane, tuple[int, int] | None]] = []
        came: dict[tuple[Lane, tuple[int, int] | None], tuple] = {}
        best: dict[tuple[Lane, tuple[int, int] | None], float] = {}
        for node in starts:
            state = (node, None)
            best[state] = 0.0
            heapq.heappush(open_set, (self._h(node, goal_centre), 0.0, node, None))

        while open_set:
            _f, g, node, direction = heapq.heappop(open_set)
            state = (node, direction)
            if g > best.get(state, float("inf")):
                continue
            if node in goals:
                return _unwind(came, state)
            for nd in DIRS:
                nxt = (node[0] + nd[0], node[1] + nd[1])
                if not (lo[0] <= nxt[0] <= hi[0] and lo[1] <= nxt[1] <= hi[1]):
                    continue
                if nxt in blocked:
                    continue
                step = (LANE_X if nd[0] else LANE_Y) / 50.0
                if direction is not None and nd != direction:
                    step += STEP_TURN_PENALTY
                step += LANE_REUSE_PENALTY * usage.get(nxt, 0)
                ng = g + step
                nstate = (nxt, nd)
                if ng < best.get(nstate, float("inf")):
                    best[nstate] = ng
                    came[nstate] = state
                    heapq.heappush(
                        open_set, (ng + self._h(nxt, goal_centre), ng, nxt, nd)
                    )
        return None

    def _attach_ends(self, src: Slot, dst: Slot, points):
        """Clip the first and last leg back to the card borders."""
        if not points:
            return points
        start_centre = self.grid.slot_to_pixel(src)
        end_centre = self.grid.slot_to_pixel(dst)
        head = _card_anchor(start_centre, points[0])
        tail = _card_anchor(end_centre, points[-1])
        return _drop_collinear([head] + points + [tail])


# -- geometry helpers -----------------------------------------------------


def _unwind(came, state) -> list[Lane]:
    out = [state[0]]
    while state in came:
        state = came[state]
        out.append(state[0])
    out.reverse()
    return out


def _card_anchor(centre, toward, inset: float = 1.0):
    """Where a road meets the edge of the card sitting at ``centre``."""
    cx, cy = centre
    tx, ty = toward
    dx, dy = tx - cx, ty - cy
    if dx == 0 and dy == 0:
        return (cx, cy)
    hw = CARD_W / 2 - inset
    hh = CARD_H / 2 - inset
    scale = float("inf")
    if dx:
        scale = min(scale, hw / abs(dx))
    if dy:
        scale = min(scale, hh / abs(dy))
    if scale == float("inf") or scale > 1.0:
        scale = min(1.0, scale)
    return (cx + dx * scale, cy + dy * scale)


def _drop_collinear(points):
    if len(points) < 3:
        return list(points)
    out = [points[0]]
    for prev, cur, nxt in zip(points, points[1:], points[2:]):
        ax, ay = cur[0] - prev[0], cur[1] - prev[1]
        bx, by = nxt[0] - cur[0], nxt[1] - cur[1]
        if abs(ax * by - ay * bx) > 1e-6:
            out.append(cur)
    out.append(points[-1])
    return out


def _round_corners(points, radius: float = CORNER_RADIUS, samples: int = 5):
    """Replace each right angle with a short quadratic arc."""
    if len(points) < 3:
        return list(points)
    out = [points[0]]
    for prev, cur, nxt in zip(points, points[1:], points[2:]):
        r1 = _shorten(cur, prev, radius)
        r2 = _shorten(cur, nxt, radius)
        out.append(r1)
        for i in range(1, samples):
            t = i / samples
            mt = 1 - t
            out.append(
                (
                    mt * mt * r1[0] + 2 * mt * t * cur[0] + t * t * r2[0],
                    mt * mt * r1[1] + 2 * mt * t * cur[1] + t * t * r2[1],
                )
            )
        out.append(r2)
    out.append(points[-1])
    return out


def _shorten(origin, toward, amount):
    dx, dy = toward[0] - origin[0], toward[1] - origin[1]
    length = (dx * dx + dy * dy) ** 0.5
    if length <= 1e-6:
        return origin
    f = min(amount, length / 2) / length
    return (origin[0] + dx * f, origin[1] + dy * f)

"""Derived state: which slot each location's card occupies.

The layout is downstream of the game model and can be thrown away and rebuilt
without touching the game. When the topology changes, the layout escalates
through four tiers, and stops at the first one that produces a decent board:

    1. free slot        -- place the card, move nothing
    2. local shuffle    -- nudge one or two neighbours aside
    3. expand board     -- grow the grid, try again
    4. full relayout    -- hill-climb everything, still paying movement cost

Nothing here produces pixels. ``update()`` returns a ``LayoutDelta`` describing
what changed; animating that is the renderer's job.
"""

from __future__ import annotations

import random
from dataclasses import dataclass, field
from time import perf_counter

from .scoring import CostBreakdown, placement_cost
from .slots import Slot, SlotGrid

# A tier-1 placement is good enough if the new card's own roads are short, it
# adds almost no crossings, and no path ends up running over another card.
ACCEPT_MAX_EDGE = 2.2
ACCEPT_MAX_NEW_CROSSINGS = 1
LOOSE_MAX_EDGE = 3.2

TIER1_RADIUS = 3
TIER3_RADIUS = 5
MAX_TIER1_CANDIDATES = 60
MAX_TIER2_COMBOS = 220
TIER4_ITERATIONS = 250
RELAYOUT_ITERATIONS = 800

TIER_NAMES = {
    0: "no change",
    1: "free slot",
    2: "local shuffle",
    3: "expand board",
    4: "full relayout",
}


@dataclass
class LayoutDelta:
    """What changed between two layouts."""

    added: dict[str, Slot] = field(default_factory=dict)
    removed: dict[str, Slot] = field(default_factory=dict)
    moved: dict[str, tuple[Slot, Slot]] = field(default_factory=dict)
    tier: int = 0
    cost: CostBreakdown | None = None
    elapsed_ms: float = 0.0
    candidates: list[tuple[Slot, float]] = field(default_factory=list)

    @property
    def tier_name(self) -> str:
        return TIER_NAMES.get(self.tier, str(self.tier))

    @property
    def is_empty(self) -> bool:
        return not (self.added or self.removed or self.moved)

    def __bool__(self) -> bool:
        return not self.is_empty


class BoardLayout:
    def __init__(self, grid: SlotGrid | None = None) -> None:
        self.grid = grid or SlotGrid()
        self.placements: dict[str, Slot] = {}
        self.last_delta: LayoutDelta | None = None
        self._seen_edges: set[tuple[str, str]] = set()
        self._seen_version = -1

    # -- public API -------------------------------------------------------

    def update(self, graph, force_tier: int | None = None) -> LayoutDelta:
        """Bring the layout back in line with the graph."""
        started = perf_counter()
        before = dict(self.placements)

        for loc_id in list(self.placements):
            if loc_id not in graph.locations:
                del self.placements[loc_id]

        tier = 0
        cost: CostBreakdown | None = None
        candidates: list[tuple[Slot, float]] = []
        for loc_id in graph.locations:
            if loc_id in self.placements:
                continue
            t, c, cands = self._insert(graph, loc_id, force_tier)
            tier = max(tier, t)
            cost = c
            candidates = cands

        # A new or closed road between two cards that are already on the table
        # changes no placements at all. The road is simply drawn where the
        # cards are -- moving a card the player already knows the position of
        # costs far more than a tidy edge is worth.
        self._seen_edges = set(graph.edges)
        self._seen_version = graph.version

        delta = self._diff(before, tier, cost, candidates)
        delta.elapsed_ms = (perf_counter() - started) * 1000.0
        self.last_delta = delta
        return delta

    def relayout(self, graph, iterations: int = RELAYOUT_ITERATIONS) -> LayoutDelta:
        """Rebuild the whole board from scratch, ignoring the current layout.

        Only used by the demo's ``R`` key, to show what the board looks like
        when nothing is preserved -- which is exactly the churn the tiered
        insertion exists to avoid.
        """
        started = perf_counter()
        before = dict(self.placements)
        self.placements = self._greedy_layout(graph)
        self._hill_climb(graph, previous=None, iterations=iterations, seed=graph.version)
        cost = placement_cost(self.placements, graph, self.grid, previous=before)
        delta = self._diff(before, 4, cost, [])
        delta.elapsed_ms = (perf_counter() - started) * 1000.0
        self.last_delta = delta
        return delta

    def seed(self, placements: dict[str, Slot], graph=None) -> None:
        """Adopt a known arrangement -- a saved board, or a test fixture."""
        self.placements = dict(placements)
        if graph is not None:
            self._seen_edges = set(graph.edges)
            self._seen_version = graph.version

    def slot_of(self, loc_id: str) -> Slot | None:
        return self.placements.get(loc_id)

    def location_at(self, slot: Slot) -> str | None:
        for loc_id, s in self.placements.items():
            if s == slot:
                return loc_id
        return None

    def reset(self) -> None:
        self.placements.clear()
        self._seen_edges.clear()
        self._seen_version = -1
        self.last_delta = None

    # -- insertion --------------------------------------------------------

    def _insert(self, graph, loc_id: str, force_tier: int | None):
        """Find a home for one new card, escalating only as far as needed."""
        placed = self.placements
        if not placed:
            placed[loc_id] = (0, 0)
            cost = placement_cost(placed, graph, self.grid)
            return 1, cost, [((0, 0), cost.total)]

        anchors = [placed[n] for n in sorted(graph.linked(loc_id)) if n in placed]
        radius = TIER1_RADIUS
        if not anchors:
            # Nothing to hang it off -- tuck it against the existing board.
            anchors = sorted(set(placed.values()))
            radius = 1

        focus = {loc_id} | {n for n in graph.linked(loc_id) if n in placed}
        baseline = placement_cost(placed, graph, self.grid, previous=placed, focus=focus)

        # -- tier 1: somewhere free, nothing moves ------------------------
        best, scores = self._best_free_slot(graph, loc_id, anchors, radius, focus)
        if best is not None:
            slot, cost = best
            if force_tier in (None, 1) and self._acceptable(
                graph, loc_id, slot, cost, baseline, ACCEPT_MAX_EDGE
            ):
                placed[loc_id] = slot
                return 1, cost, scores

        # -- tier 2: ask one or two neighbours to budge -------------------
        if force_tier is None or force_tier >= 2:
            shuffled = self._best_local_shuffle(graph, loc_id, anchors, focus, baseline)
            if shuffled is not None:
                trial, cost = shuffled
                if force_tier == 2 or self._prefers_shuffle(graph, loc_id, best, trial):
                    self.placements = trial
                    return 2, cost, scores

        # -- still tier 1: a free slot that is merely imperfect -----------
        # Settling for a slightly long road beats growing the board or
        # shuffling the town around, so this is checked before escalating.
        if best is not None and force_tier is None:
            slot, cost = best
            if self._acceptable(graph, loc_id, slot, cost, baseline, LOOSE_MAX_EDGE):
                placed[loc_id] = slot
                return 1, cost, scores

        # -- tier 3: the board is simply too small ------------------------
        if best is None or force_tier == 3:
            if force_tier is None or force_tier >= 3:
                self.grid.expand(1)
                grown, grown_scores = self._best_free_slot(
                    graph, loc_id, anchors, TIER3_RADIUS, focus
                )
                if grown is not None:
                    slot, cost = grown
                    if force_tier == 3 or self._acceptable(
                        graph, loc_id, slot, cost, baseline, LOOSE_MAX_EDGE
                    ):
                        self.placements[loc_id] = slot
                        return 3, cost, grown_scores
                    best, scores = grown, grown_scores

        # -- tier 4: give up on inertia, but still pay for it -------------
        if best is not None:
            self.placements[loc_id] = best[0]
        else:
            self.placements[loc_id] = self._any_free_slot(anchors)
        previous = {k: v for k, v in self.placements.items() if k != loc_id}
        self._hill_climb(graph, previous=previous, iterations=TIER4_ITERATIONS, seed=graph.version)
        cost = placement_cost(self.placements, graph, self.grid, previous=previous)
        return 4, cost, scores

    def _best_free_slot(self, graph, loc_id, anchors, radius, focus):
        occupied = set(self.placements.values())
        candidates = self.grid.free_slots_near(occupied, anchors, radius=radius)
        best = None
        scores: list[tuple[Slot, float]] = []
        for slot in candidates[:MAX_TIER1_CANDIDATES]:
            trial = dict(self.placements)
            trial[loc_id] = slot
            cost = placement_cost(
                trial, graph, self.grid, previous=self.placements, focus=focus
            )
            scores.append((slot, cost.total))
            if best is None or cost.total < best[1].total:
                best = (slot, cost)
        return best, scores

    def _best_local_shuffle(self, graph, loc_id, anchors, focus, baseline):
        """Try placing the card on an occupied slot and sliding cards aside."""
        placed = self.placements
        by_slot = {slot: lid for lid, slot in placed.items()}
        occupied = set(placed.values())
        best = None
        combos = 0

        for target in self.grid.occupied_slots_near(placed, anchors, radius=2):
            occupant = by_slot[target]
            occupant_focus = focus | {occupant} | {
                n for n in graph.linked(occupant) if n in placed
            }

            # One card steps aside into a free slot.
            for dest in self.grid.free_slots_near(occupied, [target], radius=2)[:8]:
                trial = dict(placed)
                trial[occupant] = dest
                trial[loc_id] = target
                cost = placement_cost(
                    trial, graph, self.grid, previous=placed, focus=occupant_focus
                )
                combos += 1
                if cost.card_overlap == 0 and (best is None or cost.total < best[1].total):
                    best = (trial, cost)
                if combos >= MAX_TIER2_COMBOS:
                    return best

            # Two cards step aside: the occupant pushes a neighbour along.
            for second in self.grid.occupied_slots_near(placed, [target], radius=1):
                if second == target:
                    continue
                pushed = by_slot[second]
                chain_focus = occupant_focus | {pushed} | {
                    n for n in graph.linked(pushed) if n in placed
                }
                for dest in self.grid.free_slots_near(occupied, [second], radius=2)[:4]:
                    trial = dict(placed)
                    trial[pushed] = dest
                    trial[occupant] = second
                    trial[loc_id] = target
                    cost = placement_cost(
                        trial, graph, self.grid, previous=placed, focus=chain_focus
                    )
                    combos += 1
                    if cost.card_overlap == 0 and (
                        best is None or cost.total < best[1].total
                    ):
                        best = (trial, cost)
                    if combos >= MAX_TIER2_COMBOS:
                        return best
        return best

    def _prefers_shuffle(self, graph, loc_id, best_free, trial) -> bool:
        """Is sliding cards aside actually better than the best free slot?

        Focused costs are only comparable within one focus set, and a shuffle
        is scored over a wider focus than a plain insertion, so the two are
        compared here on a full-board cost instead.
        """
        if best_free is None:
            return True
        placed = self.placements
        stay = dict(placed)
        stay[loc_id] = best_free[0]
        stay_cost = placement_cost(stay, graph, self.grid, previous=placed)
        move_cost = placement_cost(trial, graph, self.grid, previous=placed)
        return move_cost.total < stay_cost.total

    def _acceptable(self, graph, loc_id, slot, cost, baseline, max_edge) -> bool:
        if cost.card_overlap > 0 or not self.grid.contains(slot):
            return False
        if cost.edge_over_card > baseline.edge_over_card:
            return False
        if cost.crossings - baseline.crossings > ACCEPT_MAX_NEW_CROSSINGS:
            return False
        for neighbour in graph.linked(loc_id):
            other = self.placements.get(neighbour)
            if other is None:
                continue
            if self.grid.distance(slot, other) > max_edge:
                return False
        return True

    def _any_free_slot(self, anchors) -> Slot:
        occupied = set(self.placements.values())
        free = self.grid.free_slots_near(occupied, anchors, radius=8, allow_outside=True)
        return free[0] if free else (self.grid.half_cols + 1, 0)

    # -- whole-board solving ----------------------------------------------

    def _greedy_layout(self, graph) -> dict[str, Slot]:
        """Breadth-first greedy placement, used as a seed for a full relayout."""
        ids = list(graph.locations)
        if not ids:
            return {}
        placements: dict[str, Slot] = {}
        remaining = set(ids)
        while remaining:
            root = min(remaining, key=lambda lid: (-len(graph.linked(lid)), lid))
            queue = [root]
            seen = {root}
            while queue:
                loc_id = queue.pop(0)
                remaining.discard(loc_id)
                anchors = [
                    placements[n] for n in sorted(graph.linked(loc_id)) if n in placements
                ]
                if not placements:
                    placements[loc_id] = (0, 0)
                elif not anchors:
                    anchors = sorted(set(placements.values()))
                    placements[loc_id] = self._greedy_pick(graph, loc_id, anchors, placements, 1)
                else:
                    placements[loc_id] = self._greedy_pick(graph, loc_id, anchors, placements, 3)
                for n in sorted(graph.linked(loc_id)):
                    if n not in seen:
                        seen.add(n)
                        queue.append(n)
        return placements

    def _greedy_pick(self, graph, loc_id, anchors, placements, radius) -> Slot:
        occupied = set(placements.values())
        focus = {loc_id} | {n for n in graph.linked(loc_id) if n in placements}
        free = self.grid.free_slots_near(occupied, anchors, radius=radius)
        if not free:
            self.grid.expand(1)
            free = self.grid.free_slots_near(occupied, anchors, radius=radius + 2)
        best = None
        for slot in free[:40]:
            trial = dict(placements)
            trial[loc_id] = slot
            cost = placement_cost(trial, graph, self.grid, focus=focus)
            if best is None or cost.total < best[1]:
                best = (slot, cost.total)
        return best[0] if best else (0, 0)

    def _hill_climb(self, graph, previous, iterations: int, seed: int) -> None:
        """Nudge the whole board downhill for a fixed number of proposals.

        Deliberately unsophisticated: a board holds 20-50 locations, which does
        not warrant a heroic graph-theory algorithm. The budget is counted in
        iterations rather than milliseconds so that the same board always
        produces the same layout, whatever the machine is doing.
        """
        ids = [lid for lid in graph.locations if lid in self.placements]
        if len(ids) < 2:
            return
        rng = random.Random(seed)
        current = self.placements
        for _ in range(iterations):
            if rng.random() < 0.65:
                loc_id = rng.choice(ids)
                anchors = [
                    current[n] for n in sorted(graph.linked(loc_id)) if n in current
                ] or [current[loc_id]]
                occupied = set(current.values()) - {current[loc_id]}
                free = self.grid.free_slots_near(occupied, anchors, radius=2)
                if not free:
                    continue
                touched = {loc_id}
                trial = dict(current)
                trial[loc_id] = rng.choice(free[: min(10, len(free))])
            else:
                a, b = rng.sample(ids, 2)
                touched = {a, b}
                trial = dict(current)
                trial[a], trial[b] = current[b], current[a]

            focus = set(touched)
            for lid in touched:
                focus |= {n for n in graph.linked(lid) if n in current}
            before = placement_cost(current, graph, self.grid, previous=previous, focus=focus)
            after = placement_cost(trial, graph, self.grid, previous=previous, focus=focus)
            if after.total < before.total:
                current = trial
        self.placements = current

    # -- bookkeeping ------------------------------------------------------

    def _diff(self, before, tier, cost, candidates) -> LayoutDelta:
        delta = LayoutDelta(tier=tier, cost=cost, candidates=candidates)
        for loc_id, slot in self.placements.items():
            old = before.get(loc_id)
            if old is None:
                delta.added[loc_id] = slot
            elif old != slot:
                delta.moved[loc_id] = (old, slot)
        for loc_id, slot in before.items():
            if loc_id not in self.placements:
                delta.removed[loc_id] = slot
        if delta.is_empty:
            delta.tier = 0
        return delta

"""Shared test fixtures.

Living at the project root so that ``import board`` works from the tests.
"""

from __future__ import annotations

import pytest

from board import scenario
from board.graph import BoardGraph, Location
from board.layout import BoardLayout
from board.slots import SlotGrid


def make_board(ids, grid: SlotGrid | None = None):
    """A graph of bare locations plus an empty layout."""
    graph = BoardGraph()
    for loc_id in ids:
        graph.add_location(Location(loc_id, loc_id.upper()))
    return graph, BoardLayout(grid or SlotGrid())


def play_deck():
    """Deal the opening board and play every card in the demo deck."""
    graph = BoardGraph()
    layout = BoardLayout(SlotGrid())
    scenario.setup(graph)
    layout.update(graph)
    tiers = []
    for card in scenario.DECK:
        scenario.play(graph, card)
        tiers.append(layout.update(graph).tier)
    return graph, layout, tiers


@pytest.fixture(scope="module")
def dealt():
    return play_deck()

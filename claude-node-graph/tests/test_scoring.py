"""The cost model, and in particular the thing it exists to get right:
a prettier board is not worth disturbing one the player already knows.
"""

from board.graph import BoardGraph, Location
from board.scoring import placement_cost
from board.slots import SlotGrid


def crossing_graph():
    graph = BoardGraph()
    for loc_id in "abcd":
        graph.add_location(Location(loc_id, loc_id.upper()))
    graph.connect("a", "b", two_way=True)
    graph.connect("c", "d", two_way=True)
    return graph


# a and b sit on one diagonal, c and d on the other, so their roads cross.
CROSSED = {"a": (0, 0), "b": (1, 1), "c": (1, 0), "d": (0, 1)}
# Laying each pair out along a row removes the crossing entirely.
CLEAN = {"a": (0, 0), "b": (1, 0), "c": (0, 1), "d": (1, 1)}


def test_crossings_are_penalised():
    graph, grid = crossing_graph(), SlotGrid()
    crossed = placement_cost(CROSSED, graph, grid)
    clean = placement_cost(CLEAN, graph, grid)

    assert crossed.crossings == 1
    assert clean.crossings == 0
    assert clean.total < crossed.total


def test_movement_outweighs_a_prettier_board():
    """The whole thesis: tidying up is not worth moving cards for."""
    graph, grid = crossing_graph(), SlotGrid()

    stay = placement_cost(CROSSED, graph, grid, previous=CROSSED)
    tidy = placement_cost(CLEAN, graph, grid, previous=CROSSED)

    assert stay.movement == 0
    assert tidy.moved_cards == 3
    assert stay.total < tidy.total


def test_two_cards_in_one_slot_is_effectively_infinite():
    graph, grid = crossing_graph(), SlotGrid()
    overlapping = dict(CROSSED, d=(1, 0))
    assert placement_cost(overlapping, graph, grid).card_overlap > 1000


def test_long_roads_cost_more_than_short_ones():
    graph, grid = crossing_graph(), SlotGrid()
    near = {"a": (0, 0), "b": (1, 0), "c": (0, 2), "d": (1, 2)}
    far = {"a": (0, 0), "b": (4, 0), "c": (0, 2), "d": (1, 2)}
    assert placement_cost(far, graph, grid).edge_length > placement_cost(near, graph, grid).edge_length


def test_region_hint_pulls_a_card_north():
    graph = BoardGraph()
    graph.add_location(Location("a", "A", region="north"))
    graph.add_location(Location("b", "B"))
    graph.connect("a", "b", two_way=True)
    grid = SlotGrid()

    north = placement_cost({"a": (0, -1), "b": (0, 0)}, graph, grid)
    south = placement_cost({"a": (0, 1), "b": (0, 0)}, graph, grid)
    assert north.region < south.region


def test_focus_only_narrows_the_work_not_the_ranking():
    """Candidates scored with the same focus must rank the same as full costs."""
    graph, grid = crossing_graph(), SlotGrid()
    focus = {"c", "d"}
    full = placement_cost(CLEAN, graph, grid).total - placement_cost(CROSSED, graph, grid).total
    part = (
        placement_cost(CLEAN, graph, grid, focus=focus).total
        - placement_cost(CROSSED, graph, grid, focus=focus).total
    )
    assert (full < 0) == (part < 0)

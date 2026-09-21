import pytest

from board.graph import BoardGraph, Location


def test_connections_are_directed():
    graph = BoardGraph()
    graph.add_location(Location("a", "A"))
    graph.add_location(Location("b", "B"))
    graph.connect("a", "b")

    assert graph.has_edge("a", "b")
    assert not graph.has_edge("b", "a")
    assert graph.successors("a") == ["b"]
    assert graph.predecessors("b") == ["a"]


def test_two_way_connects_both_directions():
    graph = BoardGraph()
    graph.add_location(Location("a", "A"))
    graph.add_location(Location("b", "B"))
    graph.connect("a", "b", two_way=True)

    assert graph.has_edge("a", "b") and graph.has_edge("b", "a")
    assert graph.links() == [("a", "b", True)]


def test_linked_ignores_direction():
    """The layout solver only cares that two cards need a road between them."""
    graph = BoardGraph()
    for loc_id in "abc":
        graph.add_location(Location(loc_id, loc_id.upper()))
    graph.connect("a", "b")
    graph.connect("c", "a")

    assert graph.linked("a") == {"b", "c"}


def test_links_lists_each_pair_once():
    graph = BoardGraph()
    for loc_id in "abc":
        graph.add_location(Location(loc_id, loc_id.upper()))
    graph.connect("a", "b", two_way=True)
    graph.connect("b", "c")

    assert graph.links() == [("a", "b", True), ("b", "c", False)]


def test_removing_a_location_removes_its_roads():
    graph = BoardGraph()
    for loc_id in "abc":
        graph.add_location(Location(loc_id, loc_id.upper()))
    graph.connect("a", "b", two_way=True)
    graph.connect("b", "c", two_way=True)

    graph.remove_location("b")

    assert "b" not in graph
    assert graph.edges == set()
    assert len(graph) == 2


def test_rejects_duplicates_and_self_connection():
    graph = BoardGraph()
    graph.add_location(Location("a", "A"))
    with pytest.raises(ValueError):
        graph.add_location(Location("a", "Another A"))
    with pytest.raises(ValueError):
        graph.connect("a", "a")
    with pytest.raises(KeyError):
        graph.connect("a", "nowhere")


def test_locations_carry_hints_not_coordinates():
    location = Location("graveyard", "Graveyard", region="north", layout_group="old_town")
    assert not hasattr(location, "x")
    assert not hasattr(location, "y")
    assert location.region == "north"

"""The insertion behaviour the whole design hangs on."""

from conftest import make_board, play_deck

from board.graph import Location
from board.layout import BoardLayout
from board.slots import SlotGrid


def test_first_card_anchors_the_board():
    graph, layout = make_board(["a"])
    layout.update(graph)
    assert layout.placements == {"a": (0, 0)}


def test_card_with_one_anchor_lands_next_to_it_and_moves_nothing():
    graph, layout = make_board(["a"])
    layout.update(graph)

    graph.add_location(Location("b", "B"))
    graph.connect("a", "b", two_way=True)
    delta = layout.update(graph)

    assert delta.moved == {}
    assert delta.tier == 1
    assert layout.grid.manhattan(layout.placements["a"], layout.placements["b"]) == 1


def test_free_slot_wins_over_a_prettier_rearrangement():
    """The worked example from the design conversation.

        [A] [B] [C]          [A] [B] [C]
                      + F ->
        [D] [E] [ ]          [D] [E] [F]

    F connects to C and E. The empty slot is adjacent to both, so it is taken
    and not one existing card moves -- even though some globally tidier
    arrangement may exist.
    """
    graph, layout = make_board(["a", "b", "c", "d", "e"])
    graph.connect("a", "b", two_way=True)
    graph.connect("b", "c", two_way=True)
    graph.connect("d", "e", two_way=True)
    graph.connect("b", "e", two_way=True)
    before = {"a": (0, 0), "b": (1, 0), "c": (2, 0), "d": (0, 1), "e": (1, 1)}
    layout.seed(before, graph)

    graph.add_location(Location("f", "F"))
    graph.connect("f", "c", two_way=True)
    graph.connect("f", "e", two_way=True)
    delta = layout.update(graph)

    assert layout.placements["f"] == (2, 1)
    assert delta.moved == {}
    assert delta.tier == 1
    assert {k: v for k, v in layout.placements.items() if k != "f"} == before


def test_removing_a_card_frees_its_slot():
    graph, layout, _tiers = play_deck()
    slot = layout.placements["docks"]

    graph.remove_location("docks")
    delta = layout.update(graph)

    assert delta.removed == {"docks": slot}
    assert "docks" not in layout.placements
    assert slot not in layout.placements.values()


def test_a_full_board_escalates_and_grows():
    """No free slot anywhere means the board itself has to get bigger."""
    grid = SlotGrid(half_cols=2, half_rows=2)
    ids = [f"n{c}_{r}" for r in range(-2, 3) for c in range(-2, 3)]
    graph, layout = make_board(ids, grid)
    layout.seed({f"n{c}_{r}": (c, r) for r in range(-2, 3) for c in range(-2, 3)}, graph)
    assert len(layout.placements) == len(grid.all_slots())

    graph.add_location(Location("late", "Late Arrival"))
    graph.connect("late", "n0_0", two_way=True)
    delta = layout.update(graph)

    assert delta.tier >= 3
    assert grid.half_cols > 2
    assert "late" in layout.placements
    assert len(set(layout.placements.values())) == len(layout.placements)


def test_forcing_tier_two_shuffles_neighbours_aside():
    graph, layout = make_board(["a", "b", "c"])
    graph.connect("a", "b", two_way=True)
    graph.connect("b", "c", two_way=True)
    layout.seed({"a": (0, 0), "b": (1, 0), "c": (2, 0)}, graph)

    graph.add_location(Location("d", "D"))
    graph.connect("d", "b", two_way=True)
    delta = layout.update(graph, force_tier=2)

    assert delta.tier == 2
    assert delta.moved
    assert len(set(layout.placements.values())) == 4


def test_a_new_road_does_not_rearrange_the_board():
    """Connecting two cards already on the table moves nothing.

    The road is simply drawn where the cards are. Dragging a card the player
    has already learned the position of costs far more than a tidy edge is
    worth, so the layout leaves it alone and lets the route be long.
    """
    graph, layout = make_board(["a", "b", "c", "d", "e"])
    graph.connect("a", "b", two_way=True)
    before = {"a": (0, 0), "b": (1, 0), "c": (2, 0), "d": (3, 0), "e": (4, 0)}
    layout.seed(before, graph)

    graph.connect("a", "e", two_way=True)
    delta = layout.update(graph)

    assert delta.is_empty
    assert layout.placements == before


def test_whole_deck_leaves_a_valid_board():
    graph, layout, tiers = play_deck()

    assert set(layout.placements) == set(graph.locations)
    assert len(set(layout.placements.values())) == len(layout.placements)
    # Inertia is the point: playing the deck should barely move anything.
    assert tiers.count(1) >= len(tiers) - 2


def test_same_board_twice_gives_the_same_layout():
    first = play_deck()[1].placements
    second = play_deck()[1].placements
    assert first == second


def test_relayout_ignores_the_current_arrangement():
    graph, layout, _tiers = play_deck()
    before = dict(layout.placements)

    delta = layout.relayout(graph, iterations=200)

    assert set(layout.placements) == set(before)
    assert len(set(layout.placements.values())) == len(layout.placements)
    assert delta.tier == 4

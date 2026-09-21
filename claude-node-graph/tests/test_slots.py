from board.slots import CARD_H, CARD_W, PITCH_X, PITCH_Y, SlotGrid


def test_pixel_round_trip():
    grid = SlotGrid()
    for slot in [(0, 0), (3, -2), (-4, 4)]:
        assert grid.pixel_to_slot(grid.slot_to_pixel(slot)) == slot


def test_gutters_are_wide_enough_for_roads():
    """Adjacent cards must leave a clear lane between them."""
    assert PITCH_X - CARD_W >= 48
    assert PITCH_Y - CARD_H >= 48


def test_rings_grow_as_expected():
    grid = SlotGrid()
    assert grid.ring((0, 0), 1) and len(grid.ring((0, 0), 1)) == 8
    assert len(grid.ring((2, 2), 2)) == 16
    assert len(grid.within((0, 0), 2)) == 1 + 8 + 16


def test_bounds_and_expansion():
    grid = SlotGrid(half_cols=2, half_rows=1)
    assert grid.contains((2, 1))
    assert not grid.contains((3, 1))
    assert grid.outside_by((4, 1)) == 2

    grid.expand(1)
    assert grid.contains((3, 2))


def test_free_slots_skip_occupied_and_come_nearest_first():
    grid = SlotGrid()
    occupied = {(0, 0), (1, 0)}
    free = grid.free_slots_near(occupied, [(0, 0)], radius=1)

    assert (0, 0) not in free and (1, 0) not in free
    assert len(free) == 7
    # The row pitch is shorter than the column pitch, so vertical neighbours
    # are genuinely nearer and should be offered first.
    assert free[0] in {(0, -1), (0, 1)}


def test_free_slots_respect_board_bounds():
    grid = SlotGrid(half_cols=1, half_rows=1)
    free = grid.free_slots_near(set(), [(1, 1)], radius=2)
    assert all(grid.contains(slot) for slot in free)
    assert grid.free_slots_near(set(), [(1, 1)], radius=2, allow_outside=True) != free


def test_board_rect_covers_every_card():
    grid = SlotGrid()
    left, top, w, h = grid.board_pixel_rect([(0, 0), (2, 1)])
    assert left == -CARD_W / 2
    assert top == -CARD_H / 2
    assert w == 2 * PITCH_X + CARD_W
    assert h == PITCH_Y + CARD_H

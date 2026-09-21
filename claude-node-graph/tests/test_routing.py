"""Roads must stay in the gutters and point the right way."""

from conftest import play_deck

from board.routing import Router


def sample_points(points, per_segment=6):
    """Points along the polyline, excluding the two card anchors."""
    out = []
    for a, b in zip(points, points[1:]):
        for i in range(1, per_segment):
            t = i / per_segment
            out.append((a[0] + (b[0] - a[0]) * t, a[1] + (b[1] - a[1]) * t))
    return out


def test_every_connection_gets_a_routed_path(dealt):
    graph, layout, _tiers = dealt
    routes = Router(layout.grid).routes(graph, layout.placements)

    assert len(routes) == len(graph.links())
    assert all(route.routed for route in routes)
    assert all(len(route.points) >= 2 for route in routes)


def test_roads_never_run_across_a_card(dealt):
    graph, layout, _tiers = dealt
    grid = layout.grid
    routes = Router(grid).routes(graph, layout.placements)

    for route in routes:
        for loc_id, slot in layout.placements.items():
            if loc_id in (route.a, route.b):
                continue
            left, top, w, h = grid.card_rect(slot)
            for x, y in sample_points(route.points):
                inside = left <= x <= left + w and top <= y <= top + h
                assert not inside, f"{route.a}->{route.b} crosses {loc_id}"


def test_one_way_roads_run_from_source_to_target(dealt):
    """The arrowhead is drawn at the end of the polyline, so the polyline has
    to start at the card the road leaves."""
    graph, layout, _tiers = dealt
    grid = layout.grid
    routes = Router(grid).routes(graph, layout.placements)

    for route in routes:
        if route.two_way:
            continue
        assert graph.has_edge(route.a, route.b)
        assert not graph.has_edge(route.b, route.a)
        start_rect = grid.card_rect(layout.placements[route.a])
        end_rect = grid.card_rect(layout.placements[route.b])
        assert _touches(route.points[0], start_rect)
        assert _touches(route.points[-1], end_rect)


def test_routing_is_stable_for_the_same_board(dealt):
    graph, layout, _tiers = dealt
    first = Router(layout.grid).routes(graph, layout.placements)
    second = Router(layout.grid).routes(graph, layout.placements)
    assert [r.points for r in first] == [r.points for r in second]


def _touches(point, rect, slack=2.0):
    left, top, w, h = rect
    return (
        left - slack <= point[0] <= left + w + slack
        and top - slack <= point[1] <= top + h + slack
    )

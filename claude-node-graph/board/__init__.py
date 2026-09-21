"""A dynamic board of location cards, laid out automatically.

    board = BoardGraph()
    board.add_location(hospital)
    board.connect(hospital, church)
    board.connect(hospital, town_square)

    layout.update(board)

The graph is the game. The layout is derived, disposable, and the only thing
that ever thinks about where a card sits.
"""

from .graph import BoardGraph, Location
from .layout import BoardLayout, LayoutDelta
from .routing import Route, Router
from .slots import SlotGrid

__all__ = [
    "BoardGraph",
    "Location",
    "BoardLayout",
    "LayoutDelta",
    "Router",
    "Route",
    "SlotGrid",
]

"""Physical components: where things are and how they look."""
from __future__ import annotations

import attrs


@attrs.define
class Position:
    """The tile coordinates of an entity on the map."""

    x: int = 0
    y: int = 0


@attrs.define
class Renderable:
    """How an entity is drawn on the screen."""

    char: str = "?"
    fg: tuple[int, int, int] = (255, 255, 255)


@attrs.define
class Camera:
    """Tracks the top-left corner of the viewport for scrolling the map."""

    x: int = 0
    y: int = 0

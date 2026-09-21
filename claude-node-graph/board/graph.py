"""The game model: a directed graph of locations.

Nothing in this module knows anything about screen coordinates. A location
connects to other locations; where the card ends up on the board is somebody
else's problem (see ``board.layout``).
"""

from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class Location:
    """A place the investigators can stand, rendered as a card.

    The ``region`` / ``layout_group`` / ``preferred_distance`` fields are *soft*
    layout hints. They express intent ("the graveyard belongs up north", "these
    cards belong together") without ever naming a coordinate.
    """

    id: str
    name: str
    subtitle: str = ""
    kind: str = "street"
    region: str | None = None
    layout_group: str | None = None
    preferred_distance: int = 1
    placement: str = "near_connected_nodes"


def _loc_id(location: Location | str) -> str:
    return location.id if isinstance(location, Location) else location


class BoardGraph:
    """Locations plus directed connections between them."""

    def __init__(self) -> None:
        self.locations: dict[str, Location] = {}
        self.edges: set[tuple[str, str]] = set()
        # Bumped on every mutation so derived state can tell it is stale.
        self.version: int = 0

    # -- mutation ---------------------------------------------------------

    def add_location(self, location: Location) -> Location:
        if location.id in self.locations:
            raise ValueError(f"duplicate location id: {location.id!r}")
        self.locations[location.id] = location
        self.version += 1
        return location

    def remove_location(self, location: Location | str) -> None:
        loc_id = _loc_id(location)
        if loc_id not in self.locations:
            raise KeyError(loc_id)
        del self.locations[loc_id]
        self.edges = {(a, b) for (a, b) in self.edges if a != loc_id and b != loc_id}
        self.version += 1

    def connect(self, a: Location | str, b: Location | str, two_way: bool = False) -> None:
        a_id, b_id = _loc_id(a), _loc_id(b)
        if a_id not in self.locations:
            raise KeyError(a_id)
        if b_id not in self.locations:
            raise KeyError(b_id)
        if a_id == b_id:
            raise ValueError("a location cannot connect to itself")
        self.edges.add((a_id, b_id))
        if two_way:
            self.edges.add((b_id, a_id))
        self.version += 1

    def disconnect(self, a: Location | str, b: Location | str, both: bool = True) -> None:
        a_id, b_id = _loc_id(a), _loc_id(b)
        self.edges.discard((a_id, b_id))
        if both:
            self.edges.discard((b_id, a_id))
        self.version += 1

    # -- queries ----------------------------------------------------------

    def has_edge(self, a: Location | str, b: Location | str) -> bool:
        return (_loc_id(a), _loc_id(b)) in self.edges

    def successors(self, location: Location | str) -> list[str]:
        loc_id = _loc_id(location)
        return sorted(b for (a, b) in self.edges if a == loc_id)

    def predecessors(self, location: Location | str) -> list[str]:
        loc_id = _loc_id(location)
        return sorted(a for (a, b) in self.edges if b == loc_id)

    def linked(self, location: Location | str) -> set[str]:
        """Undirected neighbourhood -- what the layout solver cares about.

        A one-way road still has to be drawn between two cards, so for layout
        purposes direction is irrelevant.
        """
        loc_id = _loc_id(location)
        out: set[str] = set()
        for a, b in self.edges:
            if a == loc_id:
                out.add(b)
            elif b == loc_id:
                out.add(a)
        return out

    def links(self) -> list[tuple[str, str, bool]]:
        """Undirected edge list as ``(a, b, two_way)``, in a stable order.

        Each pair appears once. ``two_way`` is true when both directions exist;
        otherwise the edge runs ``a -> b``.
        """
        seen: set[tuple[str, str]] = set()
        out: list[tuple[str, str, bool]] = []
        for a, b in sorted(self.edges):
            key = (a, b) if a < b else (b, a)
            if key in seen:
                continue
            seen.add(key)
            two_way = (b, a) in self.edges
            out.append((a, b, two_way))
        return out

    def __contains__(self, location: Location | str) -> bool:
        return _loc_id(location) in self.locations

    def __len__(self) -> int:
        return len(self.locations)

    def __iter__(self):
        return iter(self.locations.values())

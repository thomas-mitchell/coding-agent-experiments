"""The demo deck.

The opening board is the one from the design conversation -- Church, Town
Square, Graveyard, Library, Docks, with the same connections. Everything after
that is a location card waiting to be drawn, each carrying its own placement
instruction, exactly as a physical card would.
"""

from __future__ import annotations

from dataclasses import dataclass

from .graph import BoardGraph, Location


@dataclass(frozen=True)
class DeckCard:
    location: Location
    # (other_id, "both" | "to" that location | "from" that location)
    connections: tuple[tuple[str, str], ...]
    text: str = ""


STARTING_LOCATIONS = (
    Location("town_square", "Town Square", "The heart of Arkham.", "civic", region="centre"),
    Location("church", "Church", "South Church, doors always open.", "civic"),
    Location("graveyard", "Graveyard", "Christchurch Cemetery.", "occult", region="north"),
    Location("library", "Library", "Orne Library, restricted stacks.", "civic"),
    Location("docks", "Docks", "River Street wharves.", "dock", region="south"),
)

# Church -> Town Square, Town Square -> Church, Town Square -> Library,
# Graveyard -> Church, Docks -> Town Square.
STARTING_CONNECTIONS = (
    ("church", "town_square", True),
    ("town_square", "library", False),
    ("graveyard", "church", False),
    ("docks", "town_square", False),
)


DECK = (
    DeckCard(
        Location("north_road", "North Road", "The way out of town.", "street", region="north"),
        (("graveyard", "both"), ("town_square", "both")),
        "Place the North Road connected to the Graveyard and the Town Square.",
    ),
    DeckCard(
        Location("hospital", "St Mary's Hospital", "Overworked and underlit.", "civic"),
        (("church", "both"), ("town_square", "both")),
        "Place the Hospital connected to the Church and the Town Square.",
    ),
    DeckCard(
        Location("rail_yard", "Rail Yard", "Freight in, questions out.", "street", region="south"),
        (("docks", "both"), ("town_square", "both")),
        "Place the Rail Yard connected to the Docks and the Town Square.",
    ),
    DeckCard(
        Location("curiosity_shoppe", "Curiosity Shoppe", "Everything has a price.", "occult"),
        (("town_square", "both"), ("library", "both")),
        "Place the Shoppe connected to the Town Square and the Library.",
    ),
    DeckCard(
        Location(
            "sanatorium",
            "Abandoned Sanatorium",
            "Empty since the fire.",
            "occult",
            region="north",
        ),
        (("graveyard", "both"), ("north_road", "both")),
        "Place the Sanatorium connected to the Graveyard and the North Road.",
    ),
    DeckCard(
        Location("old_mill", "Old Mill", "The wheel still turns.", "wild", region="north"),
        (("north_road", "both"),),
        "Place the Old Mill connected to the North Road.",
    ),
    DeckCard(
        Location("harbour_market", "Harbour Market", "Fish, rope, rumour.", "dock", region="south"),
        (("docks", "both"), ("rail_yard", "both"), ("town_square", "both")),
        "Place the Market connected to the Docks, the Rail Yard and the Town Square.",
    ),
    DeckCard(
        Location("university", "Miskatonic University", "Do not read aloud.", "civic"),
        (("library", "both"), ("hospital", "both")),
        "Place the University connected to the Library and the Hospital.",
    ),
    DeckCard(
        Location("witch_house", "Witch House", "Angles that do not add up.", "occult"),
        (("curiosity_shoppe", "both"),),
        "Place the Witch House connected to the Curiosity Shoppe.",
    ),
    DeckCard(
        Location("lodge", "Silver Twilight Lodge", "Members only.", "occult"),
        (("university", "both"), ("curiosity_shoppe", "to")),
        "Place the Lodge connected to the University, with a one-way door to the Shoppe.",
    ),
    DeckCard(
        Location("drowned_wharf", "Drowned Wharf", "Half of it is underwater.", "dock", region="south"),
        (("docks", "both"), ("harbour_market", "both")),
        "Place the Wharf connected to the Docks and the Harbour Market.",
    ),
    DeckCard(
        Location("black_cave", "Black Cave", "It goes down further than that.", "wild", region="north"),
        (("old_mill", "from"),),
        "Place the Cave. The Mill leads to it; nothing leads back.",
    ),
    DeckCard(
        Location("asylum_gate", "Asylum Gate", "Locked from the outside.", "civic"),
        (("sanatorium", "both"), ("hospital", "both")),
        "Place the Gate connected to the Sanatorium and the Hospital.",
    ),
    DeckCard(
        Location(
            "other_dimension",
            "Another Dimension",
            "Not in Arkham at all.",
            "otherworld",
            layout_group="other_world",
            preferred_distance=2,
        ),
        (("black_cave", "from"), ("witch_house", "from")),
        "Place Another Dimension. The Cave and the Witch House lead there.",
    ),
    DeckCard(
        Location(
            "yhtill",
            "The Gate of Yhtill",
            "A city that remembers you.",
            "otherworld",
            layout_group="other_world",
        ),
        (("other_dimension", "both"),),
        "Place the Gate of Yhtill connected to Another Dimension.",
    ),
)


def setup(graph: BoardGraph) -> BoardGraph:
    """Deal the opening board."""
    for location in STARTING_LOCATIONS:
        graph.add_location(location)
    for a, b, two_way in STARTING_CONNECTIONS:
        graph.connect(a, b, two_way=two_way)
    return graph


def play(graph: BoardGraph, card: DeckCard) -> None:
    """Put a drawn card onto the board with the connections it names."""
    graph.add_location(card.location)
    for other, direction in card.connections:
        if other not in graph.locations:
            continue
        if direction == "from":
            graph.connect(other, card.location.id)
        else:
            graph.connect(card.location.id, other, two_way=(direction == "both"))

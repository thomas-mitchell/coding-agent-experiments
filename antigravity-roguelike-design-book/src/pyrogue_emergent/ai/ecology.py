"""
Faction disposition matrix, predator-prey hierarchies, and ecological infighting.
"""

from __future__ import annotations
from enum import Enum, auto


class Disposition(Enum):
    HOSTILE = auto()
    NEUTRAL = auto()
    FRIENDLY = auto()
    PREY = auto()


class FactionSystem:
    """
    Evaluates ecological relationships between creature factions.
    """
    _DEFAULT_RELATIONS: dict[tuple[str, str], Disposition] = {
        ("goblin", "player"): Disposition.HOSTILE,
        ("player", "goblin"): Disposition.HOSTILE,
        ("wolf", "player"): Disposition.HOSTILE,
        ("wolf", "goblin"): Disposition.PREY,    # Wolves hunt goblins
        ("goblin", "wolf"): Disposition.HOSTILE,  # Goblins fight wolves
        ("undead", "player"): Disposition.HOSTILE,
        ("undead", "goblin"): Disposition.HOSTILE,# Undead attack all living
        ("undead", "wolf"): Disposition.HOSTILE,
    }

    @classmethod
    def get_disposition(cls, faction_a: str, faction_b: str) -> Disposition:
        if faction_a == faction_b:
            return Disposition.FRIENDLY
        return cls._DEFAULT_RELATIONS.get((faction_a, faction_b), Disposition.NEUTRAL)

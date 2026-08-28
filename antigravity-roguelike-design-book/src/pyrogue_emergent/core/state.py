"""
Deterministic RNG stream management, game state persistence, and snapshotting.
"""

from __future__ import annotations
from dataclasses import dataclass, field
from enum import Enum, auto
import random
import json
from typing import Any


class RNGChannel(Enum):
    """Isolated RNG channels to prevent action desync across systems."""
    WORLD_GEN = auto()
    COMBAT = auto()
    AI = auto()
    CELLULAR = auto()
    LOOT = auto()
    GENERAL = auto()


class RNGManager:
    """
    Manages deterministic, partitioned pseudo-random number generator streams.
    Seeding the root seed derives deterministic sub-seeds for each channel.
    """
    def __init__(self, master_seed: int = 1337) -> None:
        self.master_seed = master_seed
        self._streams: dict[RNGChannel, random.Random] = {}
        self.reseed(master_seed)

    def reseed(self, master_seed: int) -> None:
        """Initializes all sub-streams from the master seed."""
        self.master_seed = master_seed
        master_rng = random.Random(master_seed)
        for channel in RNGChannel:
            sub_seed = master_rng.randint(0, 2**31 - 1)
            self._streams[channel] = random.Random(sub_seed)

    def get(self, channel: RNGChannel = RNGChannel.GENERAL) -> random.Random:
        """Returns the isolated RNG stream for a specific subsystem."""
        return self._streams[channel]

    def randint(self, a: int, b: int, channel: RNGChannel = RNGChannel.GENERAL) -> int:
        return self._streams[channel].randint(a, b)

    def choice(self, seq: list[Any], channel: RNGChannel = RNGChannel.GENERAL) -> Any:
        return self._streams[channel].choice(seq)

    def random(self, channel: RNGChannel = RNGChannel.GENERAL) -> float:
        return self._streams[channel].random()

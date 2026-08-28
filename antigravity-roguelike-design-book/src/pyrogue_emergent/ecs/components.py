"""
Core component definitions modeling physical properties, affordances, combat, and perception.
"""

from __future__ import annotations
from dataclasses import dataclass, field
from enum import Enum, auto
from pyrogue_emergent.core.math2d import Vec2
from pyrogue_emergent.world.grid import FluidType, GasType


class MaterialType(Enum):
    WOOD = auto()
    IRON = auto()
    FLESH = auto()
    GLASS = auto()
    STONE = auto()
    CLOTH = auto()
    ICE = auto()
    GOLD = auto()


@dataclass
class Position:
    pos: Vec2


@dataclass
class Renderable:
    glyph: str
    color: str = "white"
    name: str = "unnamed"
    render_order: int = 10  # 1 = corpse, 5 = item, 10 = actor


@dataclass
class Physics:
    weight: float = 1.0        # Weight in kg
    buoyant: bool = False      # Does it float on water?
    fragile: bool = False      # Does it shatter on impact?
    explosive: bool = False    # Does it explode on heat/impact?
    explosion_radius: int = 2
    explosion_damage: int = 35


@dataclass
class Material:
    material_type: MaterialType = MaterialType.FLESH
    conductivity: float = 0.0     # 0.0 to 1.0 (electricity propagation)
    flammability: float = 0.0     # 0.0 to 1.0 (combustion ease)
    hardness: float = 1.0         # resistance to physical breakage
    melting_point: int = 1000     # Degrees Celsius


@dataclass
class Flammable:
    fuel: int = 10
    ignition_temp: int = 150
    is_burning: bool = False


@dataclass
class Conductive:
    shock_multiplier: float = 1.0


@dataclass
class LiquidContainer:
    capacity: int = 100
    fluid_type: FluidType = FluidType.NONE
    volume: int = 0
    sealed: bool = True


@dataclass
class GasEmitter:
    gas_type: GasType = GasType.SMOKE
    rate: int = 10
    remaining_ticks: int = 5


@dataclass
class CombatStats:
    hp: int = 30
    max_hp: int = 30
    attack: int = 5
    defense: int = 2


@dataclass
class Inventory:
    items: list[int] = field(default_factory=list)
    max_weight: float = 50.0


@dataclass
class Faction:
    name: str = "neutral"  # player, goblin, beast, undead, neutral


@dataclass
class SensoryProfile:
    vision_radius: int = 8
    has_infravision: bool = False
    has_hearing: bool = True

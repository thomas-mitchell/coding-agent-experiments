"""
Layered 2D grid representing physical topology, fluids, gases, items, and actors.
"""

from __future__ import annotations
from dataclasses import dataclass, field
from enum import Enum, auto
from typing import Iterator
from pyrogue_emergent.core.math2d import Vec2, Rect


class TileType(Enum):
    WALL = auto()
    FLOOR = auto()
    CHASM = auto()
    DOOR_CLOSED = auto()
    DOOR_OPEN = auto()
    WATER_SHALLOW = auto()
    WATER_DEEP = auto()
    ICE = auto()
    LAVA = auto()


class FluidType(Enum):
    NONE = auto()
    WATER = auto()
    OIL = auto()
    ACID = auto()
    BLOOD = auto()
    ALCOHOL = auto()


class GasType(Enum):
    NONE = auto()
    SMOKE = auto()
    POISON_GAS = auto()
    STEAM = auto()
    FLAMMABLE_VAPOR = auto()
    MIASMA = auto()


@dataclass(slots=True)
class CellState:
    """Represents the multi-layer physical state of a single discrete coordinate."""
    tile: TileType = TileType.FLOOR
    fluid_type: FluidType = FluidType.NONE
    fluid_volume: int = 0         # Volume in units (e.g. 0-100)
    gas_type: GasType = GasType.NONE
    gas_density: int = 0          # Gas density (0-100)
    temperature: int = 20         # Degrees Celsius (room temp default)
    fire_intensity: int = 0       # 0 = no fire, 1-100 = active combustion
    fire_fuel: int = 0            # Remaining burn fuel
    items: list[int] = field(default_factory=list)  # Entity IDs of items on this tile
    actor: int | None = None      # Entity ID of actor occupying this tile

    @property
    def blocks_movement(self) -> bool:
        return self.tile in (TileType.WALL, TileType.DOOR_CLOSED) or self.actor is not None

    @property
    def blocks_vision(self) -> bool:
        if self.tile in (TileType.WALL, TileType.DOOR_CLOSED):
            return True
        # Dense smoke blocks vision
        if self.gas_type == GasType.SMOKE and self.gas_density > 60:
            return True
        return False

    @property
    def is_flammable_surface(self) -> bool:
        if self.fluid_type in (FluidType.OIL, FluidType.ALCOHOL) and self.fluid_volume > 0:
            return True
        return False

    @property
    def is_conductive(self) -> bool:
        return self.fluid_type in (FluidType.WATER, FluidType.ACID, FluidType.BLOOD) and self.fluid_volume > 0


class LayeredGrid:
    """
    Two-dimensional layered world grid managing spatial queries and cellular layers.
    """
    def __init__(self, width: int, height: int) -> None:
        self.width = width
        self.height = height
        self.bounds = Rect(0, 0, width, height)
        self._cells: list[CellState] = [CellState() for _ in range(width * height)]

    def _index(self, pos: Vec2) -> int:
        return pos.y * self.width + pos.x

    def in_bounds(self, pos: Vec2) -> bool:
        return 0 <= pos.x < self.width and 0 <= pos.y < self.height

    def get_cell(self, pos: Vec2) -> CellState:
        if not self.in_bounds(pos):
            raise IndexError(f"Position {pos} out of grid bounds ({self.width}x{self.height})")
        return self._cells[self._index(pos)]

    def set_tile(self, pos: Vec2, tile: TileType) -> None:
        if self.in_bounds(pos):
            self._cells[self._index(pos)].tile = tile

    def place_actor(self, actor_id: int, pos: Vec2) -> bool:
        cell = self.get_cell(pos)
        if cell.blocks_movement:
            return False
        cell.actor = actor_id
        return True

    def remove_actor(self, pos: Vec2) -> None:
        if self.in_bounds(pos):
            self._cells[self._index(pos)].actor = None

    def move_actor(self, actor_id: int, from_pos: Vec2, to_pos: Vec2) -> bool:
        to_cell = self.get_cell(to_pos)
        if to_cell.blocks_movement:
            return False
        self.remove_actor(from_pos)
        to_cell.actor = actor_id
        return True

    def add_item(self, item_id: int, pos: Vec2) -> None:
        if self.in_bounds(pos):
            self._cells[self._index(pos)].items.append(item_id)

    def remove_item(self, item_id: int, pos: Vec2) -> bool:
        if self.in_bounds(pos):
            cell = self._cells[self._index(pos)]
            if item_id in cell.items:
                cell.items.remove(item_id)
                return True
        return False

    def iter_positions(self) -> Iterator[Vec2]:
        for y in range(self.height):
            for x in range(self.width):
                yield Vec2(x, y)

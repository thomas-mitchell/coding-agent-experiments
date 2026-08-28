"""
Field of View (FOV) calculation using Symmetric Shadowcasting algorithm.
"""

from __future__ import annotations
import math
from typing import Callable, Set
from pyrogue_emergent.core.math2d import Vec2


class SymmetricShadowcasting:
    """
    Computes precise field of view ensuring symmetry: if A sees B, then B sees A.
    """
    @staticmethod
    def compute_fov(
        origin: Vec2,
        max_radius: int,
        is_blocking: Callable[[Vec2], bool],
    ) -> set[Vec2]:
        """
        Calculates all visible coordinates from origin up to max_radius.
        """
        visible: set[Vec2] = {origin}

        # Scan 8 octants
        for octant in range(8):
            SymmetricShadowcasting._scan_octant(
                octant=octant,
                origin=origin,
                radius=max_radius,
                row=1,
                start_slope=-1.0,
                end_slope=1.0,
                is_blocking=is_blocking,
                visible=visible,
            )

        return visible

    @staticmethod
    def _transform_octant(row: int, col: int, octant: int) -> tuple[int, int]:
        """Maps (row, col) in canonical octant to global grid offset (dx, dy)."""
        match octant:
            case 0: return (col, -row)
            case 1: return (row, -col)
            case 2: return (row, col)
            case 3: return (col, row)
            case 4: return (-col, row)
            case 5: return (-row, col)
            case 6: return (-row, -col)
            case 7: return (-col, -row)
            case _: return (0, 0)

    @staticmethod
    def _scan_octant(
        octant: int,
        origin: Vec2,
        radius: int,
        row: int,
        start_slope: float,
        end_slope: float,
        is_blocking: Callable[[Vec2], bool],
        visible: set[Vec2],
    ) -> None:
        if start_slope >= end_slope or row > radius:
            return

        first_col = int(math.floor(row * start_slope + 0.5))
        last_col = int(math.ceil(row * end_slope - 0.5))
        previous_tile_blocked = False

        for col in range(first_col, last_col + 1):
            dx, dy = SymmetricShadowcasting._transform_octant(row, col, octant)
            pos = Vec2(origin.x + dx, origin.y + dy)

            # Check distance limit
            if origin.euclidean_dist(pos) <= radius:
                visible.add(pos)

            tile_blocked = is_blocking(pos)

            if previous_tile_blocked:
                if tile_blocked:
                    pass
                else:
                    # Transition from blocked to clear
                    previous_tile_blocked = False
                    start_slope = (col - 0.5) / (row + 0.5)
            else:
                if tile_blocked:
                    # Transition from clear to blocked
                    previous_tile_blocked = True
                    new_end_slope = (col - 0.5) / (row - 0.5)
                    SymmetricShadowcasting._scan_octant(
                        octant=octant,
                        origin=origin,
                        radius=radius,
                        row=row + 1,
                        start_slope=start_slope,
                        end_slope=new_end_slope,
                        is_blocking=is_blocking,
                        visible=visible,
                    )

        if not previous_tile_blocked:
            SymmetricShadowcasting._scan_octant(
                octant=octant,
                origin=origin,
                radius=radius,
                row=row + 1,
                start_slope=start_slope,
                end_slope=end_slope,
                is_blocking=is_blocking,
                visible=visible,
            )

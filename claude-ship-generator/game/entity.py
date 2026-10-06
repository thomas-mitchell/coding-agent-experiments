from __future__ import annotations

from dataclasses import dataclass

from ship import Ship
from ship.tiles import WALKABLE


@dataclass
class Player:
    x: int
    y: int
    char: str = "@"
    color: tuple[int, int, int] = (255, 255, 255)

    def try_move(self, ship: Ship, dx: int, dy: int) -> bool:
        nx, ny = self.x + dx, self.y + dy
        if not (0 <= nx < ship.width and 0 <= ny < ship.height) or not WALKABLE[ship.tiles[nx, ny]]:
            return False
        self.x, self.y = nx, ny
        return True

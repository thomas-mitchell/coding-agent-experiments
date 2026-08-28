"""
ANSI terminal renderer and HUD display for systemic roguelike simulation.
"""

from __future__ import annotations
import sys
from pyrogue_emergent.core.math2d import Vec2
from pyrogue_emergent.world.grid import LayeredGrid, TileType, FluidType, GasType
from pyrogue_emergent.ecs.entity import EntityManager
from pyrogue_emergent.ecs.components import Position, Renderable, CombatStats


class TerminalRenderer:
    """
    Renders the layered grid, FOV, actors, items, and status HUD using ANSI escape colors.
    """
    # ANSI Color constants
    RESET = "\033[0m"
    BOLD = "\033[1m"
    DIM = "\033[2m"
    RED = "\033[31m"
    GREEN = "\033[32m"
    YELLOW = "\033[33m"
    BLUE = "\033[34m"
    MAGENTA = "\033[35m"
    CYAN = "\033[36m"
    WHITE = "\033[37m"
    BG_RED = "\033[41m"
    BG_BLUE = "\033[44m"
    BG_YELLOW = "\033[43m"

    @staticmethod
    def render_map(
        grid: LayeredGrid,
        ecs: EntityManager,
        visible_tiles: set[Vec2],
        message_log: list[str] | None = None,
    ) -> str:
        output_lines: list[str] = []

        for y in range(grid.height):
            line_chars: list[str] = []
            for x in range(grid.width):
                pos = Vec2(x, y)
                cell = grid.get_cell(pos)
                is_visible = pos in visible_tiles

                if not is_visible:
                    line_chars.append(f"{TerminalRenderer.DIM} {TerminalRenderer.RESET}")
                    continue

                # 1. Fire on tile
                if cell.fire_intensity > 0:
                    line_chars.append(f"{TerminalRenderer.RED}{TerminalRenderer.BOLD}^{TerminalRenderer.RESET}")
                    continue

                # 2. Actor on tile
                if cell.actor:
                    renderable = ecs.get_component(cell.actor, Renderable)
                    glyph = renderable.glyph if renderable else "@"
                    line_chars.append(f"{TerminalRenderer.YELLOW}{TerminalRenderer.BOLD}{glyph}{TerminalRenderer.RESET}")
                    continue

                # 3. Item on tile
                if cell.items:
                    top_item = cell.items[-1]
                    renderable = ecs.get_component(top_item, Renderable)
                    glyph = renderable.glyph if renderable else "!"
                    line_chars.append(f"{TerminalRenderer.CYAN}{glyph}{TerminalRenderer.RESET}")
                    continue

                # 4. Gas layer
                if cell.gas_type != GasType.NONE and cell.gas_density > 20:
                    gas_char = "%" if cell.gas_density < 50 else "&"
                    match cell.gas_type:
                        case GasType.SMOKE:
                            line_chars.append(f"{TerminalRenderer.WHITE}{gas_char}{TerminalRenderer.RESET}")
                        case GasType.POISON_GAS:
                            line_chars.append(f"{TerminalRenderer.GREEN}{gas_char}{TerminalRenderer.RESET}")
                        case GasType.STEAM:
                            line_chars.append(f"{TerminalRenderer.CYAN}{gas_char}{TerminalRenderer.RESET}")
                        case _:
                            line_chars.append(gas_char)
                    continue

                # 5. Fluid layer
                if cell.fluid_type != FluidType.NONE and cell.fluid_volume > 0:
                    match cell.fluid_type:
                        case FluidType.WATER:
                            line_chars.append(f"{TerminalRenderer.BLUE}~{TerminalRenderer.RESET}")
                        case FluidType.OIL:
                            line_chars.append(f"{TerminalRenderer.YELLOW}o{TerminalRenderer.RESET}")
                        case FluidType.ACID:
                            line_chars.append(f"{TerminalRenderer.GREEN}*{TerminalRenderer.RESET}")
                        case _:
                            line_chars.append("~")
                    continue

                # 6. Base Terrain
                match cell.tile:
                    case TileType.WALL:
                        line_chars.append(f"{TerminalRenderer.WHITE}#{TerminalRenderer.RESET}")
                    case TileType.FLOOR:
                        line_chars.append(f"{TerminalRenderer.DIM}.{TerminalRenderer.RESET}")
                    case TileType.ICE:
                        line_chars.append(f"{TerminalRenderer.CYAN}_{TerminalRenderer.RESET}")
                    case TileType.DOOR_CLOSED:
                        line_chars.append(f"{TerminalRenderer.YELLOW}+{TerminalRenderer.RESET}")
                    case TileType.DOOR_OPEN:
                        line_chars.append(f"{TerminalRenderer.YELLOW}/{TerminalRenderer.RESET}")
                    case _:
                        line_chars.append(" ")

            output_lines.append("".join(line_chars))

        # Append recent message log lines
        if message_log:
            output_lines.append("\n" + "=" * 50)
            output_lines.append(f"{TerminalRenderer.BOLD}Log Messages:{TerminalRenderer.RESET}")
            for msg in message_log[-5:]:
                output_lines.append(f"- {msg}")

        return "\n".join(output_lines)

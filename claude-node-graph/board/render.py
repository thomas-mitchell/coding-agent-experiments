"""Drawing the board: parchment cards on a dark table, roads underneath.

Everything here is downstream of the layout. The renderer asks the animator
where a card currently is and draws it; it never decides anything.
"""

from __future__ import annotations

import math
from dataclasses import dataclass

import pygame

from .slots import CARD_H, CARD_W, SlotGrid

# -- palette --------------------------------------------------------------

TABLE = (18, 19, 26)
TABLE_EDGE = (10, 10, 15)
GRID_DOT = (44, 46, 60)

ROAD_CASING = (30, 27, 24)
ROAD = (152, 133, 96)
ROAD_UNROUTED = (128, 86, 86)

PARCHMENT = (216, 205, 179)
PARCHMENT_SHADE = (198, 185, 157)
CARD_EDGE = (120, 106, 82)
CARD_SHADOW = (0, 0, 0)

INK = (46, 39, 31)
INK_SOFT = (108, 96, 80)
TITLE_INK = (238, 232, 216)

HUD_BG = (24, 25, 34)
HUD_INK = (206, 202, 192)
HUD_DIM = (128, 126, 138)
ACCENT = (206, 170, 92)
WARN = (208, 108, 92)

KIND_COLOURS = {
    "street": (108, 96, 84),
    "civic": (74, 96, 128),
    "occult": (104, 68, 118),
    "wild": (76, 108, 82),
    "dock": (66, 106, 112),
    "otherworld": (132, 62, 62),
}


def kind_colour(kind: str) -> tuple[int, int, int]:
    return KIND_COLOURS.get(kind, KIND_COLOURS["street"])


# -- camera ---------------------------------------------------------------


class Camera:
    """Maps world pixels (where the slot grid lives) to the screen."""

    def __init__(self, screen_size: tuple[int, int]) -> None:
        self.screen_size = screen_size
        self.centre = [0.0, 0.0]
        self.zoom = 1.0

    def world_to_screen(self, p) -> tuple[float, float]:
        w, h = self.screen_size
        return (
            (p[0] - self.centre[0]) * self.zoom + w / 2,
            (p[1] - self.centre[1]) * self.zoom + h / 2,
        )

    def screen_to_world(self, p) -> tuple[float, float]:
        w, h = self.screen_size
        return (
            (p[0] - w / 2) / self.zoom + self.centre[0],
            (p[1] - h / 2) / self.zoom + self.centre[1],
        )

    def pan_pixels(self, dx: float, dy: float) -> None:
        self.centre[0] -= dx / self.zoom
        self.centre[1] -= dy / self.zoom

    def zoom_at(self, factor: float, screen_pos) -> None:
        before = self.screen_to_world(screen_pos)
        self.zoom = max(0.28, min(2.2, self.zoom * factor))
        after = self.screen_to_world(screen_pos)
        self.centre[0] += before[0] - after[0]
        self.centre[1] += before[1] - after[1]

    def fit(self, rect, margin: int = 130) -> None:
        left, top, w, h = rect
        self.centre = [left + w / 2, top + h / 2]
        sw, sh = self.screen_size
        if w <= 0 or h <= 0:
            self.zoom = 1.0
            return
        self.zoom = max(0.28, min(1.4, min((sw - margin) / w, (sh - margin) / h)))


# -- HUD state ------------------------------------------------------------


@dataclass
class HudState:
    hovered: str | None = None
    selected: str | None = None
    connect_from: str | None = None
    message: str = ""
    deck_remaining: int = 0
    next_card: str = ""
    debug: bool = False
    forced_tier: int | None = None


# -- renderer -------------------------------------------------------------


class BoardRenderer:
    def __init__(self, grid: SlotGrid, screen_size: tuple[int, int]) -> None:
        self.grid = grid
        self.screen_size = screen_size
        # Long names shrink rather than get chopped -- "Abandoned Sanatorium"
        # has to fit on the card as printed.
        self.title_fonts = [
            pygame.font.SysFont("georgia,timesnewroman,serif", size, bold=True)
            for size in (20, 18, 16, 14, 12)
        ]
        self.font_title = self.title_fonts[0]
        self.font_body = pygame.font.SysFont("georgia,timesnewroman,serif", 15)
        self.font_small = pygame.font.SysFont("consolas,couriernew,monospace", 13)
        self.font_hud = pygame.font.SysFont("consolas,couriernew,monospace", 14)
        self.font_hud_small = pygame.font.SysFont("consolas,couriernew,monospace", 12)
        self._card_cache: dict[tuple, pygame.Surface] = {}
        # Cards mid-removal: the graph has already forgotten them, but they are
        # still fading off the table. {loc_id: (Location, link_count)}
        self.ghosts: dict[str, tuple] = {}
        self._road_layer = pygame.Surface(screen_size, pygame.SRCALPHA)
        self._vignette = _make_vignette(screen_size)

    # -- public -----------------------------------------------------------

    def draw(self, surface, graph, layout, animator, routes, old_routes, camera, hud):
        surface.fill(TABLE)
        if hud.debug:
            self._draw_slot_grid(surface, camera, layout)
            self._draw_candidates(surface, camera, layout)

        new_alpha = animator.new_path_alpha if animator.busy else 1.0
        old_alpha = animator.old_path_alpha
        if old_routes and old_alpha > 0.01:
            self._draw_routes(surface, old_routes, camera, old_alpha, animator, layout, stale=True)
        if routes:
            self._draw_routes(surface, routes, camera, new_alpha, animator, layout)

        self._draw_cards(surface, graph, layout, animator, camera, hud)
        surface.blit(self._vignette, (0, 0))
        self._draw_hud(surface, graph, layout, hud)
        if hud.debug:
            self._draw_debug_panel(surface, layout)

    # -- board ------------------------------------------------------------

    def _draw_slot_grid(self, surface, camera, layout):
        occupied = set(layout.placements.values())
        for slot in self.grid.all_slots():
            x, y = camera.world_to_screen(self.grid.slot_to_pixel(slot))
            if not (-40 < x < self.screen_size[0] + 40 and -40 < y < self.screen_size[1] + 40):
                continue
            if slot in occupied:
                continue
            pygame.draw.circle(surface, GRID_DOT, (int(x), int(y)), max(1, int(3 * camera.zoom)))

    def _draw_candidates(self, surface, camera, layout):
        delta = layout.last_delta
        if not delta or not delta.candidates:
            return
        totals = [t for _s, t in delta.candidates]
        lo, hi = min(totals), max(totals)
        span = max(1e-6, hi - lo)
        w = int(CARD_W * camera.zoom * 0.5)
        h = int(CARD_H * camera.zoom * 0.5)
        for slot, total in delta.candidates:
            t = (total - lo) / span
            colour = (int(70 + 150 * t), int(170 - 110 * t), 90, 70)
            x, y = camera.world_to_screen(self.grid.slot_to_pixel(slot))
            chip = pygame.Surface((w, h), pygame.SRCALPHA)
            chip.fill(colour)
            surface.blit(chip, (x - w / 2, y - h / 2))

    def _draw_routes(self, surface, routes, camera, alpha, animator, layout, stale=False):
        layer = self._road_layer
        layer.fill((0, 0, 0, 0))
        casing_w = max(3, int(13 * camera.zoom))
        core_w = max(2, int(7 * camera.zoom))
        for route in routes:
            if not stale and (animator.is_ghost(route.a) or animator.is_ghost(route.b)):
                continue
            pts = [camera.world_to_screen(p) for p in route.points]
            if len(pts) < 2:
                continue
            colour = ROAD if route.routed else ROAD_UNROUTED
            pygame.draw.lines(layer, ROAD_CASING, False, pts, casing_w)
            pygame.draw.lines(layer, colour, False, pts, core_w)
            if not route.two_way:
                _draw_arrow(layer, pts, colour, camera.zoom)
        layer.set_alpha(int(255 * max(0.0, min(1.0, alpha)) * (0.75 if stale else 1.0)))
        surface.blit(layer, (0, 0))

    def _draw_cards(self, surface, graph, layout, animator, camera, hud):
        order = [(0, loc_id) for loc_id in animator.ghost_ids()]
        for loc_id in layout.placements:
            order.append((1 if loc_id not in animator.adds else 2, loc_id))
        order.sort()

        for _z, loc_id in order:
            location = graph.locations.get(loc_id)
            links = len(graph.linked(loc_id)) if location else 0
            if location is None:
                ghost = self.ghosts.get(loc_id)
                if ghost is None:
                    continue
                location, links = ghost
            slot = layout.placements.get(loc_id)
            if slot is None and not animator.is_ghost(loc_id):
                continue
            state = animator.card_state(loc_id, slot)
            if state.alpha <= 0.01:
                continue
            highlight = 0
            if loc_id == hud.connect_from:
                highlight = 2
            elif loc_id == hud.selected:
                highlight = 3
            elif loc_id == hud.hovered:
                highlight = 1
            self._blit_card(surface, camera, location, links, state, highlight)

    def _blit_card(self, surface, camera, location, links, state, highlight):
        base = self._card_surface(location, links, highlight)
        scale = camera.zoom * state.scale
        w = max(1, int(CARD_W * scale))
        h = max(1, int(CARD_H * scale))
        img = base if (w, h) == base.get_size() else pygame.transform.smoothscale(base, (w, h))
        if state.alpha < 0.999:
            img = img.copy()
            img.set_alpha(int(255 * state.alpha))
        cx, cy = camera.world_to_screen(state.pos)

        lift = state.lift
        shadow_off = (4 + 10 * lift) * camera.zoom
        shadow = pygame.Surface((w + 8, h + 8), pygame.SRCALPHA)
        pygame.draw.rect(
            shadow,
            (0, 0, 0, int(110 * state.alpha)),
            shadow.get_rect(),
            border_radius=max(2, int(10 * scale)),
        )
        surface.blit(shadow, (cx - w / 2 - 4 + shadow_off * 0.4, cy - h / 2 - 4 + shadow_off))
        surface.blit(img, (cx - w / 2, cy - h / 2))

    def _card_surface(self, location, links, highlight) -> pygame.Surface:
        key = (location.id, location.name, links, highlight)
        cached = self._card_cache.get(key)
        if cached is not None:
            return cached

        surf = pygame.Surface((CARD_W, CARD_H), pygame.SRCALPHA)
        rect = surf.get_rect()
        pygame.draw.rect(surf, PARCHMENT, rect, border_radius=9)
        pygame.draw.rect(surf, PARCHMENT_SHADE, rect.inflate(-10, -10), border_radius=6)
        pygame.draw.rect(surf, PARCHMENT, rect.inflate(-14, -14), border_radius=5)

        bar = pygame.Rect(0, 0, CARD_W, 28)
        pygame.draw.rect(
            surf,
            kind_colour(location.kind),
            bar,
            border_top_left_radius=9,
            border_top_right_radius=9,
        )
        title = _fit_text(self.title_fonts, location.name, CARD_W - 16)
        surf.blit(title, title.get_rect(center=(CARD_W // 2, 14)))

        y = 38
        for line in _wrap(self.font_body, location.subtitle, CARD_W - 26)[:2]:
            img = self.font_body.render(line, True, INK)
            surf.blit(img, img.get_rect(center=(CARD_W // 2, y)))
            y += 18

        tags = []
        if location.region:
            tags.append(location.region)
        if location.layout_group:
            tags.append(location.layout_group.replace("_", " "))
        footer = f"{links} way" + ("s" if links != 1 else "")
        if tags:
            footer += "  |  " + " ".join(tags)
        img = self.font_small.render(footer, True, INK_SOFT)
        surf.blit(img, img.get_rect(center=(CARD_W // 2, CARD_H - 15)))

        border = CARD_EDGE
        width = 2
        if highlight == 1:
            border, width = (170, 150, 110), 3
        elif highlight == 2:
            border, width = ACCENT, 4
        elif highlight == 3:
            border, width = (238, 228, 200), 3
        pygame.draw.rect(surf, border, rect, width=width, border_radius=9)

        self._card_cache[key] = surf
        return surf

    # -- chrome -----------------------------------------------------------

    def _draw_hud(self, surface, graph, layout, hud):
        w, h = self.screen_size
        panel = pygame.Surface((w, 30), pygame.SRCALPHA)
        panel.fill((*HUD_BG, 225))
        surface.blit(panel, (0, 0))

        delta = layout.last_delta
        tier = f"{delta.tier} {delta.tier_name}" if delta else "-"
        solve = f"{delta.elapsed_ms:5.1f}ms" if delta else "  -  "
        moved = len(delta.moved) if delta else 0
        left = (
            f" {len(graph)} cards   {len(graph.links())} links   "
            f"grid {self.grid.half_cols * 2 + 1}x{self.grid.half_rows * 2 + 1}"
        )
        mid = f"tier {tier}   moved {moved}   solve {solve}"
        surface.blit(self.font_hud.render(left, True, HUD_INK), (8, 7))
        surface.blit(
            self.font_hud.render(mid, True, ACCENT if moved else HUD_DIM),
            (int(w * 0.42), 7),
        )
        if hud.deck_remaining:
            right = f"deck {hud.deck_remaining}  next: {hud.next_card} "
        else:
            right = "deck empty "
        img = self.font_hud.render(right, True, HUD_DIM)
        surface.blit(img, (w - img.get_width() - 8, 7))

        keys = (
            "[A] draw card   [Del] remove   [C] connect (+Shift two-way)   [X] disconnect   "
            "[R] full relayout   [Space] replay   [1-4] force tier   [F] fit   [F1] debug"
        )
        bar = pygame.Surface((w, 26), pygame.SRCALPHA)
        bar.fill((*HUD_BG, 225))
        surface.blit(bar, (0, h - 26))
        surface.blit(self.font_hud_small.render(keys, True, HUD_DIM), (8, h - 20))

        if hud.message:
            img = self.font_hud.render(hud.message, True, TITLE_INK)
            box = pygame.Surface((img.get_width() + 24, img.get_height() + 14), pygame.SRCALPHA)
            box.fill((*HUD_BG, 232))
            pygame.draw.rect(box, ACCENT, box.get_rect(), width=1, border_radius=3)
            box.blit(img, (12, 7))
            surface.blit(box, ((w - box.get_width()) // 2, h - 70))

    def _draw_debug_panel(self, surface, layout):
        delta = layout.last_delta
        if not delta or delta.cost is None:
            return
        lines = [("last insertion", 0.0)] + delta.cost.rows()
        width, line_h = 216, 17
        panel = pygame.Surface((width, line_h * (len(lines) + 2) + 10), pygame.SRCALPHA)
        panel.fill((*HUD_BG, 232))
        pygame.draw.rect(panel, (70, 72, 92), panel.get_rect(), width=1)
        y = 8
        for label, value in lines:
            if value == 0.0 and label == "last insertion":
                panel.blit(self.font_hud_small.render(label.upper(), True, ACCENT), (10, y))
            else:
                colour = TITLE_INK if label == "TOTAL" else HUD_DIM
                panel.blit(self.font_hud_small.render(label, True, colour), (10, y))
                img = self.font_hud_small.render(f"{value:9.1f}", True, colour)
                panel.blit(img, (width - img.get_width() - 10, y))
            y += line_h
        extra = f"crossings {delta.cost.crossings}  longest {delta.cost.longest_edge:.2f}"
        panel.blit(self.font_hud_small.render(extra, True, HUD_DIM), (10, y + 4))
        surface.blit(panel, (8, 40))


# -- small helpers --------------------------------------------------------


def _draw_arrow(surface, pts, colour, zoom):
    """Arrowhead on the last segment of a one-way road."""
    end = pts[-1]
    prev = pts[max(0, len(pts) - 2)]
    dx, dy = end[0] - prev[0], end[1] - prev[1]
    length = math.hypot(dx, dy)
    if length < 1e-3:
        return
    ux, uy = dx / length, dy / length
    size = max(7.0, 13.0 * zoom)
    tip = (end[0] - ux * 2, end[1] - uy * 2)
    left = (tip[0] - ux * size + -uy * size * 0.5, tip[1] - uy * size + ux * size * 0.5)
    right = (tip[0] - ux * size - -uy * size * 0.5, tip[1] - uy * size - ux * size * 0.5)
    pygame.draw.polygon(surface, colour, [tip, left, right])


def _wrap(font, text, max_width):
    if not text:
        return []
    words = text.split()
    lines, current = [], ""
    for word in words:
        trial = f"{current} {word}".strip()
        if font.size(trial)[0] <= max_width or not current:
            current = trial
        else:
            lines.append(current)
            current = word
    if current:
        lines.append(current)
    return lines


def _fit_text(fonts, text, max_width):
    """Render a title at the largest size that fits, ellipsising as a last resort."""
    if not isinstance(fonts, (list, tuple)):
        fonts = [fonts]
    for font in fonts:
        if font.size(text)[0] <= max_width:
            return font.render(text, True, TITLE_INK)
    font = fonts[-1]
    trimmed = text
    while trimmed and font.size(trimmed + "...")[0] > max_width:
        trimmed = trimmed[:-1]
    return font.render(trimmed + "...", True, TITLE_INK)


def _make_vignette(size):
    """A smooth darkening towards the edges of the table."""
    w, h = size
    small_w, small_h = 96, 64
    small = pygame.Surface((small_w, small_h), pygame.SRCALPHA)
    for j in range(small_h):
        ny = (j + 0.5) / small_h * 2 - 1
        for i in range(small_w):
            nx = (i + 0.5) / small_w * 2 - 1
            r = min(1.0, math.hypot(nx * 0.92, ny * 0.92))
            t = max(0.0, (r - 0.45) / 0.55)
            small.set_at((i, j), (*TABLE_EDGE, int(150 * t * t)))
    return pygame.transform.smoothscale(small, size)

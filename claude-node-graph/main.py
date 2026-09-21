"""Dynamic board layout sandbox.

    python main.py              interactive
    python main.py --script     headless: play the whole deck, save board_final.png

Draw location cards with [A] and watch the board accommodate them. The point of
the exercise is what *doesn't* happen: cards already on the table stay where the
player left them.
"""

from __future__ import annotations

import os
import sys

HEADLESS = "--script" in sys.argv
if HEADLESS:
    os.environ.setdefault("SDL_VIDEODRIVER", "dummy")

import pygame  # noqa: E402

from board import scenario  # noqa: E402
from board.animation import BoardAnimator  # noqa: E402
from board.graph import BoardGraph  # noqa: E402
from board.layout import BoardLayout  # noqa: E402
from board.render import BoardRenderer, Camera, HudState  # noqa: E402
from board.routing import Router  # noqa: E402
from board.slots import SlotGrid  # noqa: E402

WINDOW = (1440, 900)
FPS = 60
MESSAGE_MS = 4200


class Sandbox:
    def __init__(self, size=WINDOW) -> None:
        pygame.init()
        pygame.display.set_caption("Arkham-style dynamic board layout")
        self.screen = pygame.display.set_mode(size, pygame.RESIZABLE)
        self.clock = pygame.time.Clock()

        self.graph = BoardGraph()
        self.grid = SlotGrid()
        self.layout = BoardLayout(self.grid)
        self.router = Router(self.grid)
        self.animator = BoardAnimator(self.grid)
        self.camera = Camera(size)
        self.renderer = BoardRenderer(self.grid, size)

        self.deck = list(scenario.DECK)
        self.routes: list = []
        self.old_routes: list = []
        self.hud = HudState()
        self.history: list[tuple[str, int, int, float]] = []

        self.mode: str | None = None
        self.connect_from: str | None = None
        self.selected: str | None = None
        self.forced_tier: int | None = None
        self.message_timer = 0.0
        self.panning = False
        self.running = True

        scenario.setup(self.graph)
        self.apply_changes("The board is dealt. Press [A] to draw a location card.")
        self.animator.finish()
        self.fit()

    # -- model changes ----------------------------------------------------

    def apply_changes(self, message: str | None = None, force_tier: int | None = None) -> None:
        stashed = {
            loc_id: self.graph.locations.get(loc_id) for loc_id in self.layout.placements
        }
        link_counts = {lid: len(self.graph.linked(lid)) for lid in self.layout.placements}

        delta = self.layout.update(self.graph, force_tier=force_tier)

        self.renderer.ghosts = {
            loc_id: (stashed[loc_id], link_counts.get(loc_id, 0))
            for loc_id in delta.removed
            if stashed.get(loc_id) is not None
        }
        self.old_routes = self.routes
        self.routes = self.router.routes(self.graph, self.layout.placements)
        self.animator.apply(delta)

        if message is None:
            message = f"tier {delta.tier} ({delta.tier_name}) - {len(delta.moved)} cards moved"
        self.set_message(message)

    def set_message(self, text: str) -> None:
        self.hud.message = text
        self.message_timer = MESSAGE_MS

    def draw_card(self) -> None:
        if not self.deck:
            self.set_message("The deck is empty.")
            return
        card = self.deck.pop(0)
        scenario.play(self.graph, card)
        forced = self.forced_tier
        self.apply_changes(card.text, force_tier=forced)
        self.forced_tier = None
        delta = self.layout.last_delta
        self.history.append((card.location.name, delta.tier, len(delta.moved), delta.elapsed_ms))

    def remove_card(self, loc_id: str | None) -> None:
        if not loc_id or loc_id not in self.graph.locations:
            return
        name = self.graph.locations[loc_id].name
        self.graph.remove_location(loc_id)
        if self.selected == loc_id:
            self.selected = None
        self.apply_changes(f"{name} is gone. The board closes the gap.")

    def connect_cards(self, a: str, b: str, two_way: bool) -> None:
        if a == b:
            return
        self.graph.connect(a, b, two_way=two_way)
        arrow = "<->" if two_way else "->"
        self.apply_changes(
            f"{self.graph.locations[a].name} {arrow} {self.graph.locations[b].name}"
        )

    def disconnect_cards(self, a: str, b: str) -> None:
        if not (self.graph.has_edge(a, b) or self.graph.has_edge(b, a)):
            self.set_message("Those two are not connected.")
            return
        self.graph.disconnect(a, b, both=True)
        self.apply_changes(
            f"The road between {self.graph.locations[a].name} and "
            f"{self.graph.locations[b].name} is closed."
        )

    # -- view -------------------------------------------------------------

    def fit(self) -> None:
        rect = self.grid.board_pixel_rect(self.layout.placements.values())
        self.camera.fit(rect)

    def location_at(self, screen_pos):
        world = self.camera.screen_to_world(screen_pos)
        for loc_id, slot in self.layout.placements.items():
            left, top, w, h = self.grid.card_rect(slot)
            if left <= world[0] <= left + w and top <= world[1] <= top + h:
                return loc_id
        return None

    def resize(self, size) -> None:
        self.screen = pygame.display.set_mode(size, pygame.RESIZABLE)
        self.camera.screen_size = size
        self.renderer = BoardRenderer(self.grid, size)

    # -- input ------------------------------------------------------------

    def handle_event(self, event) -> None:
        if event.type == pygame.QUIT:
            self.running = False
        elif event.type == pygame.VIDEORESIZE:
            self.resize((event.w, event.h))
        elif event.type == pygame.KEYDOWN:
            self.handle_key(event)
        elif event.type == pygame.MOUSEBUTTONDOWN:
            self.handle_mouse_down(event)
        elif event.type == pygame.MOUSEBUTTONUP:
            if event.button in (1, 2, 3):
                self.panning = False
        elif event.type == pygame.MOUSEMOTION:
            if self.panning:
                self.camera.pan_pixels(*event.rel)
            self.hud.hovered = self.location_at(event.pos)
        elif event.type == pygame.MOUSEWHEEL:
            self.camera.zoom_at(1.1 if event.y > 0 else 1 / 1.1, pygame.mouse.get_pos())

    def handle_key(self, event) -> None:
        key = event.key
        if key == pygame.K_ESCAPE:
            if self.mode:
                self.mode = None
                self.connect_from = None
                self.set_message("")
            else:
                self.running = False
        elif key == pygame.K_a:
            self.draw_card()
        elif key in (pygame.K_DELETE, pygame.K_BACKSPACE):
            self.remove_card(self.selected or self.hud.hovered)
        elif key == pygame.K_c:
            self.mode = "connect"
            self.connect_from = None
            self.set_message("Connect: click two cards (hold Shift for a two-way road).")
        elif key == pygame.K_x:
            self.mode = "disconnect"
            self.connect_from = None
            self.set_message("Disconnect: click two connected cards.")
        elif key == pygame.K_r:
            self.old_routes = self.routes
            delta = self.layout.relayout(self.graph)
            self.routes = self.router.routes(self.graph, self.layout.placements)
            self.animator.apply(delta)
            self.set_message(
                f"Full relayout from scratch - {len(delta.moved)} cards moved. "
                "This is the churn the tiers exist to avoid."
            )
        elif key == pygame.K_SPACE:
            if self.layout.last_delta:
                self.animator.apply(self.layout.last_delta)
        elif key in (pygame.K_1, pygame.K_2, pygame.K_3, pygame.K_4):
            tier = key - pygame.K_0
            self.forced_tier = None if self.forced_tier == tier else tier
            if self.forced_tier:
                self.set_message(f"Next card will be forced to tier {tier}.")
            else:
                self.set_message("Tier forcing off.")
        elif key == pygame.K_f:
            self.fit()
        elif key == pygame.K_F1:
            self.hud.debug = not self.hud.debug

    def handle_mouse_down(self, event) -> None:
        if event.button in (2, 3):
            self.panning = True
            return
        if event.button != 1:
            return
        loc_id = self.location_at(event.pos)
        if loc_id is None:
            self.panning = True
            self.selected = None
            return
        if self.mode in ("connect", "disconnect"):
            if self.connect_from is None:
                self.connect_from = loc_id
                self.set_message(f"...from {self.graph.locations[loc_id].name}")
                return
            source, self.connect_from = self.connect_from, None
            mode, self.mode = self.mode, None
            if mode == "connect":
                shift = pygame.key.get_mods() & pygame.KMOD_SHIFT
                self.connect_cards(source, loc_id, two_way=bool(shift))
            else:
                self.disconnect_cards(source, loc_id)
            return
        self.selected = None if self.selected == loc_id else loc_id

    # -- loop -------------------------------------------------------------

    def step(self, dt_ms: float) -> None:
        self.animator.update(dt_ms)
        if not self.animator.busy:
            self.old_routes = []
            self.renderer.ghosts = {}
        if self.message_timer > 0:
            self.message_timer -= dt_ms
            if self.message_timer <= 0:
                self.hud.message = ""

        self.hud.selected = self.selected
        self.hud.connect_from = self.connect_from
        self.hud.deck_remaining = len(self.deck)
        self.hud.next_card = self.deck[0].location.name if self.deck else ""
        self.hud.forced_tier = self.forced_tier

    def render_frame(self) -> None:
        self.renderer.draw(
            self.screen,
            self.graph,
            self.layout,
            self.animator,
            self.routes,
            self.old_routes,
            self.camera,
            self.hud,
        )

    def run(self) -> None:
        while self.running:
            dt = self.clock.tick(FPS)
            for event in pygame.event.get():
                self.handle_event(event)
            self.step(dt)
            self.render_frame()
            pygame.display.flip()
        pygame.quit()


def run_script(out_path: str = "board_final.png") -> int:
    """Play the entire deck with no window and save a picture of the result."""
    app = Sandbox()
    while app.deck:
        app.draw_card()
        app.animator.finish()
        app.step(0.0)
    app.fit()
    app.render_frame()
    pygame.image.save(app.screen, out_path)

    print(f"{'card':<24} {'tier':<16} {'moved':>5} {'solve':>9}")
    print("-" * 58)
    total_moved = 0
    for name, tier, moved, ms in app.history:
        from board.layout import TIER_NAMES

        total_moved += moved
        print(f"{name:<24} {tier} {TIER_NAMES[tier]:<14} {moved:>5} {ms:>7.1f}ms")
    print("-" * 58)
    print(
        f"{len(app.graph)} locations, {len(app.graph.links())} links, "
        f"{total_moved} card moves across {len(app.history)} insertions"
    )
    unrouted = sum(1 for r in app.routes if not r.routed)
    print(f"routes: {len(app.routes)} ({unrouted} fell back to straight lines)")
    print(f"saved {out_path}")
    pygame.quit()
    return 0


if __name__ == "__main__":
    if HEADLESS:
        args = [a for a in sys.argv[1:] if a != "--script"]
        sys.exit(run_script(args[0] if args else "board_final.png"))
    Sandbox().run()

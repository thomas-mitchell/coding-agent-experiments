"""
Tetris in Python (Pygame)
A full-featured, modern implementation of classic Tetris with procedural chiptune audio.

Features:
- Procedural 8-bit sound effects (move, rotate, hard drop, lock, line clears, game over)
- Authentic polyphonic Korobeiniki (Tetris Theme A) background music
- Standard 7-bag piece randomization
- Ghost piece (drop projection)
- Hold piece functionality (C / Shift)
- Wall kicks and smooth rotation
- Level and speed progression
- Line clear animations and scoring
- High score persistence
- Audio mute toggle (M)
- Modern retro arcade visual design
"""

import sys
import json
import random
import pygame
from sound_engine import SoundEngine

# ---------------------------------------------------------
# CONSTANTS & CONFIGURATION
# ---------------------------------------------------------
GRID_WIDTH = 10
GRID_HEIGHT = 20
CELL_SIZE = 32

BOARD_WIDTH = GRID_WIDTH * CELL_SIZE   # 320 px
BOARD_HEIGHT = GRID_HEIGHT * CELL_SIZE # 640 px
SIDEBAR_WIDTH = 260
WINDOW_PADDING = 30

SCREEN_WIDTH = BOARD_WIDTH + SIDEBAR_WIDTH + (WINDOW_PADDING * 3) # 670 px
SCREEN_HEIGHT = BOARD_HEIGHT + (WINDOW_PADDING * 2)               # 700 px
FPS = 60

# High score save file
HIGHSCORE_FILE = "highscore.json"

# Palette (RGB)
COLOR_BG = (18, 18, 26)
COLOR_GRID_BG = (12, 12, 18)
COLOR_GRID_LINE = (30, 32, 45)
COLOR_PANEL_BG = (24, 25, 38)
COLOR_PANEL_BORDER = (45, 48, 70)
COLOR_TEXT_PRIMARY = (240, 243, 255)
COLOR_TEXT_MUTED = (140, 145, 170)
COLOR_TEXT_ACCENT = (255, 215, 0)
COLOR_TEXT_GREEN = (46, 204, 113)
COLOR_TEXT_RED = (231, 76, 60)
COLOR_GHOST = (60, 65, 90)

# Tetromino colors
SHAPE_COLORS = {
    'I': (0, 230, 230),    # Cyan
    'J': (33, 115, 255),   # Blue
    'L': (255, 140, 0),    # Orange
    'O': (255, 215, 0),    # Yellow
    'S': (46, 204, 113),   # Green
    'T': (155, 89, 182),   # Purple
    'Z': (231, 76, 60),    # Red
}

# Standard rotation definitions centered around bounding boxes
PIECE_MATRICES = {
    'I': [
        [(0, 1), (1, 1), (2, 1), (3, 1)],
        [(2, 0), (2, 1), (2, 2), (2, 3)],
        [(0, 2), (1, 2), (2, 2), (3, 2)],
        [(1, 0), (1, 1), (1, 2), (1, 3)]
    ],
    'O': [
        [(0, 0), (1, 0), (0, 1), (1, 1)],
        [(0, 0), (1, 0), (0, 1), (1, 1)],
        [(0, 0), (1, 0), (0, 1), (1, 1)],
        [(0, 0), (1, 0), (0, 1), (1, 1)]
    ],
    'T': [
        [(1, 0), (0, 1), (1, 1), (2, 1)],
        [(1, 0), (1, 1), (2, 1), (1, 2)],
        [(0, 1), (1, 1), (2, 1), (1, 2)],
        [(1, 0), (0, 1), (1, 1), (1, 2)]
    ],
    'S': [
        [(1, 0), (2, 0), (0, 1), (1, 1)],
        [(1, 0), (1, 1), (2, 1), (2, 2)],
        [(1, 1), (2, 1), (0, 2), (1, 2)],
        [(0, 0), (0, 1), (1, 1), (1, 2)]
    ],
    'Z': [
        [(0, 0), (1, 0), (1, 1), (2, 1)],
        [(2, 0), (1, 1), (2, 1), (1, 2)],
        [(0, 1), (1, 1), (1, 2), (2, 2)],
        [(1, 0), (0, 1), (1, 1), (0, 2)]
    ],
    'J': [
        [(0, 0), (0, 1), (1, 1), (2, 1)],
        [(1, 0), (2, 0), (1, 1), (1, 2)],
        [(0, 1), (1, 1), (2, 1), (2, 2)],
        [(1, 0), (1, 1), (0, 2), (1, 2)]
    ],
    'L': [
        [(2, 0), (0, 1), (1, 1), (2, 1)],
        [(1, 0), (1, 1), (1, 2), (2, 2)],
        [(0, 1), (1, 1), (2, 1), (0, 2)],
        [(0, 0), (1, 0), (1, 1), (1, 2)]
    ]
}


# ---------------------------------------------------------
# HELPER FUNCTIONS
# ---------------------------------------------------------
def load_high_score() -> int:
    """Load the saved high score from local storage."""
    try:
        with open(HIGHSCORE_FILE, 'r') as f:
            data = json.load(f)
            return int(data.get("high_score", 0))
    except (FileNotFoundError, json.JSONDecodeError, ValueError):
        return 0


def save_high_score(score: int) -> None:
    """Save high score to file."""
    try:
        with open(HIGHSCORE_FILE, 'w') as f:
            json.dump({"high_score": score}, f, indent=2)
    except OSError:
        pass


def draw_beveled_block(surface: pygame.Surface, x: int, y: int, size: int, color: tuple, ghost: bool = False) -> None:
    """Draw an individual block with polished beveled highlights and shading."""
    rect = pygame.Rect(x, y, size, size)

    if ghost:
        # Ghost piece: Subtle outline and translucent fill
        ghost_surf = pygame.Surface((size, size), pygame.SRCALPHA)
        ghost_surf.fill((*color, 35))
        surface.blit(ghost_surf, (x, y))
        pygame.draw.rect(surface, (*color, 120), rect, width=1, border_radius=3)
        return

    # Base block fill
    pygame.draw.rect(surface, color, rect, border_radius=4)

    # Highlight (Top and Left edges)
    r, g, b = color
    highlight = (min(255, int(r * 1.35 + 25)), min(255, int(g * 1.35 + 25)), min(255, int(b * 1.35 + 25)))
    shadow = (max(0, int(r * 0.65)), max(0, int(g * 0.65)), max(0, int(b * 0.65)))

    # Inner bevel
    pad = 2
    bevel_w = 3
    pygame.draw.line(surface, highlight, (x + pad, y + pad), (x + size - pad - 1, y + pad), bevel_w)
    pygame.draw.line(surface, highlight, (x + pad, y + pad), (x + pad, y + size - pad - 1), bevel_w)

    pygame.draw.line(surface, shadow, (x + size - pad - 1, y + pad), (x + size - pad - 1, y + size - pad - 1), bevel_w)
    pygame.draw.line(surface, shadow, (x + pad, y + size - pad - 1), (x + size - pad - 1, y + size - pad - 1), bevel_w)

    # Dark subtle border
    pygame.draw.rect(surface, (0, 0, 0, 100), rect, width=1, border_radius=4)


# ---------------------------------------------------------
# TETROMINO CLASS
# ---------------------------------------------------------
class Piece:
    """Represents an active or preview Tetromino piece."""

    def __init__(self, shape_key: str):
        self.shape_key = shape_key
        self.color = SHAPE_COLORS[shape_key]
        self.rotation = 0
        # Start centered at top
        self.x = (GRID_WIDTH // 2) - 2
        self.y = 0

    @property
    def blocks(self) -> list[tuple[int, int]]:
        """Return absolute grid coordinates [(x, y), ...] for current state."""
        offsets = PIECE_MATRICES[self.shape_key][self.rotation]
        return [(self.x + ox, self.y + oy) for ox, oy in offsets]

    def get_blocks_at(self, x: int, y: int, rotation: int) -> list[tuple[int, int]]:
        """Return block positions for hypothetical position and rotation."""
        offsets = PIECE_MATRICES[self.shape_key][rotation % 4]
        return [(x + ox, y + oy) for ox, oy in offsets]

    def rotate(self, clockwise: bool = True) -> int:
        """Calculate next rotation index."""
        delta = 1 if clockwise else -1
        return (self.rotation + delta) % 4


# ---------------------------------------------------------
# GAME ENGINE CLASS
# ---------------------------------------------------------
class TetrisGame:
    """Encapsulates full game state, physics, rules, and logic."""

    def __init__(self, sound_engine: SoundEngine):
        self.sound = sound_engine
        self.high_score = load_high_score()
        self.reset()

    def reset(self):
        """Reset the game state to play again."""
        # 10 columns x 20 rows grid; None means empty, otherwise contains (R, G, B)
        self.grid = [[None for _ in range(GRID_WIDTH)] for _ in range(GRID_HEIGHT)]
        self.bag = []
        self.current_piece = self._next_piece_from_bag()
        self.next_piece = self._next_piece_from_bag()
        self.hold_piece_key = None
        self.can_hold = True

        self.score = 0
        self.lines_cleared = 0
        self.level = 0

        self.game_over = False
        self.paused = False

        # Drop timing (milliseconds)
        self.last_drop_time = pygame.time.get_ticks()

        # Animation states
        self.clearing_rows = []
        self.clear_anim_timer = 0

        # Start background music
        self.sound.start_music()

    def _generate_bag(self) -> list[str]:
        """Generate a shuffled 7-bag of tetrominoes."""
        bag = list(PIECE_MATRICES.keys())
        random.shuffle(bag)
        return bag

    def _next_piece_from_bag(self) -> Piece:
        """Fetch next piece respecting 7-bag randomizer."""
        if not self.bag:
            self.bag = self._generate_bag()
        return Piece(self.bag.pop())

    def get_drop_interval(self) -> int:
        """Calculate drop interval in ms based on current level."""
        return max(70, int((0.8 - (self.level * 0.007)) ** self.level * 1000))

    def is_valid_position(self, piece: Piece, x: int = None, y: int = None, rotation: int = None) -> bool:
        """Check if hypothetical placement is valid (in-bounds & no collision)."""
        x = piece.x if x is None else x
        y = piece.y if y is None else y
        rotation = piece.rotation if rotation is None else rotation

        for bx, by in piece.get_blocks_at(x, y, rotation):
            if bx < 0 or bx >= GRID_WIDTH or by < 0 or by >= GRID_HEIGHT:
                return False
            if self.grid[by][bx] is not None:
                return False
        return True

    def move_horizontal(self, delta_x: int) -> bool:
        """Move piece left (-1) or right (+1) if valid."""
        if self.game_over or self.paused or self.clearing_rows:
            return False
        if self.is_valid_position(self.current_piece, x=self.current_piece.x + delta_x):
            self.current_piece.x += delta_x
            self.sound.play_sfx('move')
            return True
        return False

    def rotate_piece(self, clockwise: bool = True) -> bool:
        """Rotate piece with wall-kick test offsets."""
        if self.game_over or self.paused or self.clearing_rows:
            return False

        new_rot = self.current_piece.rotate(clockwise)

        # Standard SRS wall-kick test offsets (dx, dy)
        kick_tests = [(0, 0), (-1, 0), (1, 0), (-2, 0), (2, 0), (0, -1), (-1, -1), (1, -1)]

        for dx, dy in kick_tests:
            test_x = self.current_piece.x + dx
            test_y = self.current_piece.y + dy
            if self.is_valid_position(self.current_piece, x=test_x, y=test_y, rotation=new_rot):
                self.current_piece.x = test_x
                self.current_piece.y = test_y
                self.current_piece.rotation = new_rot
                self.sound.play_sfx('rotate')
                return True
        return False

    def soft_drop(self) -> bool:
        """Move piece down one step; adds 1 soft-drop point."""
        if self.game_over or self.paused or self.clearing_rows:
            return False

        if self.is_valid_position(self.current_piece, y=self.current_piece.y + 1):
            self.current_piece.y += 1
            self.score += 1
            return True
        else:
            self.lock_piece()
            return False

    def hard_drop(self) -> int:
        """Instantly drop piece to bottom and lock; adds 2 points per row."""
        if self.game_over or self.paused or self.clearing_rows:
            return 0

        drop_distance = 0
        while self.is_valid_position(self.current_piece, y=self.current_piece.y + 1):
            self.current_piece.y += 1
            drop_distance += 1

        self.score += drop_distance * 2
        self.sound.play_sfx('hard_drop')
        self.lock_piece(play_lock_sfx=False)
        return drop_distance

    def get_ghost_y(self) -> int:
        """Calculate the lowest valid Y position for the ghost piece."""
        ghost_y = self.current_piece.y
        while self.is_valid_position(self.current_piece, y=ghost_y + 1):
            ghost_y += 1
        return ghost_y

    def hold_current_piece(self) -> bool:
        """Swap active piece with hold slot."""
        if not self.can_hold or self.game_over or self.paused or self.clearing_rows:
            return False

        cur_key = self.current_piece.shape_key
        if self.hold_piece_key is None:
            self.hold_piece_key = cur_key
            self.current_piece = self.next_piece
            self.next_piece = self._next_piece_from_bag()
        else:
            self.hold_piece_key, self.current_piece = cur_key, Piece(self.hold_piece_key)

        self.can_hold = False
        self.sound.play_sfx('hold')
        return True

    def lock_piece(self, play_lock_sfx: bool = True):
        """Lock current piece into grid, check line clears, spawn next piece."""
        for bx, by in self.current_piece.blocks:
            if 0 <= by < GRID_HEIGHT and 0 <= bx < GRID_WIDTH:
                self.grid[by][bx] = self.current_piece.color

        # Check full rows
        full_rows = [r for r in range(GRID_HEIGHT) if all(self.grid[r][c] is not None for c in range(GRID_WIDTH))]

        if full_rows:
            self.clearing_rows = full_rows
            self.clear_anim_timer = pygame.time.get_ticks()
            if len(full_rows) == 4:
                self.sound.play_sfx('tetris_clear')
            else:
                self.sound.play_sfx('line_clear')
        else:
            if play_lock_sfx:
                self.sound.play_sfx('drop')
            self._spawn_next()

    def _spawn_next(self):
        """Spawn next tetromino and check game over condition."""
        self.current_piece = self.next_piece
        self.next_piece = self._next_piece_from_bag()
        self.can_hold = True

        # If spawn position is blocked -> Game Over
        if not self.is_valid_position(self.current_piece):
            self.game_over = True
            self.sound.pause_music()
            self.sound.play_sfx('game_over')
            if self.score > self.high_score:
                self.high_score = self.score
                save_high_score(self.high_score)

    def _process_line_clears(self):
        """Remove cleared lines, calculate score, shift rows down."""
        lines_count = len(self.clearing_rows)
        if lines_count == 0:
            return

        prev_level = self.level

        # Modern standard scoring table
        score_table = {1: 100, 2: 300, 3: 500, 4: 800}
        base_points = score_table.get(lines_count, lines_count * 200)
        self.score += base_points * (self.level + 1)

        # Update lines & level progression
        self.lines_cleared += lines_count
        self.level = self.lines_cleared // 10

        if self.level > prev_level:
            self.sound.play_sfx('level_up')

        if self.score > self.high_score:
            self.high_score = self.score
            save_high_score(self.high_score)

        # Filter out full rows and prepend new empty rows
        new_grid = [row for r_idx, row in enumerate(self.grid) if r_idx not in self.clearing_rows]
        for _ in range(lines_count):
            new_grid.insert(0, [None for _ in range(GRID_WIDTH)])
        self.grid = new_grid

        self.clearing_rows = []
        self._spawn_next()

    def update(self):
        """Update game step timing and animations."""
        if self.game_over or self.paused:
            return

        # Line clear flash animation (150 ms)
        if self.clearing_rows:
            now = pygame.time.get_ticks()
            if now - self.clear_anim_timer > 150:
                self._process_line_clears()
            return

        # Gravity drop
        now = pygame.time.get_ticks()
        if now - self.last_drop_time > self.get_drop_interval():
            self.last_drop_time = now
            if self.is_valid_position(self.current_piece, y=self.current_piece.y + 1):
                self.current_piece.y += 1
            else:
                self.lock_piece()


# ---------------------------------------------------------
# UI & GRAPHICS RENDERER
# ---------------------------------------------------------
class TetrisRenderer:
    """Handles all drawing, UI layout, fonts, and visual polish."""

    def __init__(self, screen: pygame.Surface):
        self.screen = screen
        self.font_large = pygame.font.SysFont("segoeui, arial, helvetica, sans-serif", 32, bold=True)
        self.font_medium = pygame.font.SysFont("segoeui, arial, helvetica, sans-serif", 20, bold=True)
        self.font_small = pygame.font.SysFont("segoeui, arial, helvetica, sans-serif", 15)
        self.font_micro = pygame.font.SysFont("segoeui, arial, helvetica, sans-serif", 13)

        # Board position
        self.board_x = WINDOW_PADDING
        self.board_y = WINDOW_PADDING

        # Sidebar position
        self.sidebar_x = self.board_x + BOARD_WIDTH + WINDOW_PADDING
        self.sidebar_y = WINDOW_PADDING

    def draw_game(self, game: TetrisGame):
        """Main render loop."""
        self.screen.fill(COLOR_BG)

        self._draw_board(game)
        self._draw_sidebar(game)

        if game.paused:
            self._draw_overlay("PAUSED", "Press 'P' or 'ESC' to resume")
        elif game.game_over:
            self._draw_overlay("GAME OVER", "Press 'R' to Restart")

    def _draw_board(self, game: TetrisGame):
        """Render matrix background, grid lines, locked blocks, ghost, and active piece."""
        board_rect = pygame.Rect(self.board_x, self.board_y, BOARD_WIDTH, BOARD_HEIGHT)

        # Board background & border
        pygame.draw.rect(self.screen, COLOR_GRID_BG, board_rect, border_radius=6)
        pygame.draw.rect(self.screen, COLOR_PANEL_BORDER, board_rect, width=2, border_radius=6)

        # Grid lines
        for r in range(1, GRID_HEIGHT):
            py = self.board_y + r * CELL_SIZE
            pygame.draw.line(self.screen, COLOR_GRID_LINE, (self.board_x, py), (self.board_x + BOARD_WIDTH, py), 1)
        for c in range(1, GRID_WIDTH):
            px = self.board_x + c * CELL_SIZE
            pygame.draw.line(self.screen, COLOR_GRID_LINE, (px, self.board_y), (px, self.board_y + BOARD_HEIGHT), 1)

        # Draw placed blocks
        for r in range(GRID_HEIGHT):
            # Check line clear flash animation
            is_flashing = r in game.clearing_rows
            for c in range(GRID_WIDTH):
                color = game.grid[r][c]
                if color:
                    draw_color = (255, 255, 255) if is_flashing else color
                    bx = self.board_x + c * CELL_SIZE
                    by = self.board_y + r * CELL_SIZE
                    draw_beveled_block(self.screen, bx, by, CELL_SIZE, draw_color)

        # Draw Ghost Piece & Active Piece (only if not clearing lines or game over)
        if not game.game_over and not game.clearing_rows:
            ghost_y = game.get_ghost_y()
            # Ghost piece
            for bx, by in game.current_piece.get_blocks_at(game.current_piece.x, ghost_y, game.current_piece.rotation):
                if 0 <= by < GRID_HEIGHT:
                    gx = self.board_x + bx * CELL_SIZE
                    gy = self.board_y + by * CELL_SIZE
                    draw_beveled_block(self.screen, gx, gy, CELL_SIZE, game.current_piece.color, ghost=True)

            # Active piece
            for bx, by in game.current_piece.blocks:
                if 0 <= by < GRID_HEIGHT:
                    ax = self.board_x + bx * CELL_SIZE
                    ay = self.board_y + by * CELL_SIZE
                    draw_beveled_block(self.screen, ax, ay, CELL_SIZE, game.current_piece.color)

    def _draw_panel(self, x: int, y: int, width: int, height: int, title: str) -> int:
        """Draw a sleek UI card panel with header."""
        rect = pygame.Rect(x, y, width, height)
        pygame.draw.rect(self.screen, COLOR_PANEL_BG, rect, border_radius=8)
        pygame.draw.rect(self.screen, COLOR_PANEL_BORDER, rect, width=1, border_radius=8)

        # Title
        title_surf = self.font_small.render(title.upper(), True, COLOR_TEXT_MUTED)
        self.screen.blit(title_surf, (x + 14, y + 10))
        return y + 34

    def _draw_sidebar(self, game: TetrisGame):
        """Render side stats: Next piece, Hold piece, Score, Level, Lines, Audio status, Controls."""
        curr_y = self.sidebar_y

        # 1. SCORE & HIGH SCORE PANEL
        panel_h = 100
        content_y = self._draw_panel(self.sidebar_x, curr_y, SIDEBAR_WIDTH, panel_h, "Score")

        score_text = f"{game.score:,}"
        score_surf = self.font_large.render(score_text, True, COLOR_TEXT_PRIMARY)
        self.screen.blit(score_surf, (self.sidebar_x + 14, content_y))

        high_text = f"HIGH: {game.high_score:,}"
        high_surf = self.font_micro.render(high_text, True, COLOR_TEXT_ACCENT)
        self.screen.blit(high_surf, (self.sidebar_x + 14, content_y + 38))

        curr_y += panel_h + 14

        # 2. NEXT PIECE & HOLD PIECE (Side by side)
        box_w = (SIDEBAR_WIDTH - 10) // 2
        box_h = 110

        # Next Piece Box
        next_content_y = self._draw_panel(self.sidebar_x, curr_y, box_w, box_h, "Next")
        self._draw_preview_piece(game.next_piece.shape_key, self.sidebar_x + (box_w // 2), next_content_y + 35)

        # Hold Piece Box
        hold_x = self.sidebar_x + box_w + 10
        hold_content_y = self._draw_panel(hold_x, curr_y, box_w, box_h, "Hold")
        if game.hold_piece_key:
            hold_color = SHAPE_COLORS[game.hold_piece_key] if game.can_hold else COLOR_TEXT_MUTED
            self._draw_preview_piece(game.hold_piece_key, hold_x + (box_w // 2), hold_content_y + 35, color_override=hold_color)

        curr_y += box_h + 14

        # 3. LEVEL, LINES & AUDIO STATS
        stats_h = 80
        stats_content_y = self._draw_panel(self.sidebar_x, curr_y, SIDEBAR_WIDTH, stats_h, "Stats")

        col1_x = self.sidebar_x + 14
        col2_x = self.sidebar_x + 95
        col3_x = self.sidebar_x + 175

        lvl_lbl = self.font_micro.render("LEVEL", True, COLOR_TEXT_MUTED)
        lvl_val = self.font_medium.render(str(game.level), True, COLOR_TEXT_PRIMARY)
        self.screen.blit(lvl_lbl, (col1_x, stats_content_y))
        self.screen.blit(lvl_val, (col1_x, stats_content_y + 16))

        lines_lbl = self.font_micro.render("LINES", True, COLOR_TEXT_MUTED)
        lines_val = self.font_medium.render(str(game.lines_cleared), True, COLOR_TEXT_PRIMARY)
        self.screen.blit(lines_lbl, (col2_x, stats_content_y))
        self.screen.blit(lines_val, (col2_x, stats_content_y + 16))

        audio_lbl = self.font_micro.render("AUDIO", True, COLOR_TEXT_MUTED)
        is_muted = game.sound.muted or not game.sound.enabled
        audio_text = "MUTED" if is_muted else "ON"
        audio_color = COLOR_TEXT_RED if is_muted else COLOR_TEXT_GREEN
        audio_val = self.font_medium.render(audio_text, True, audio_color)
        self.screen.blit(audio_lbl, (col3_x, stats_content_y))
        self.screen.blit(audio_val, (col3_x, stats_content_y + 16))

        curr_y += stats_h + 14

        # 4. CONTROLS GUIDE PANEL
        ctrl_h = 240
        ctrl_content_y = self._draw_panel(self.sidebar_x, curr_y, SIDEBAR_WIDTH, ctrl_h, "Controls")

        controls = [
            ("◄ / ►", "Move Left / Right"),
            ("▲ / W", "Rotate CW"),
            ("Z", "Rotate CCW"),
            ("▼ / S", "Soft Drop"),
            ("SPACE", "Hard Drop"),
            ("C / Shift", "Hold Piece"),
            ("M", "Toggle Sound/Music"),
            ("P / ESC", "Pause / Resume"),
            ("R", "Restart Game"),
        ]

        row_y = ctrl_content_y
        for key_text, desc_text in controls:
            k_surf = self.font_micro.render(key_text, True, COLOR_TEXT_ACCENT)
            d_surf = self.font_micro.render(desc_text, True, COLOR_TEXT_MUTED)
            self.screen.blit(k_surf, (self.sidebar_x + 14, row_y))
            self.screen.blit(d_surf, (self.sidebar_x + 95, row_y))
            row_y += 22

    def _draw_preview_piece(self, shape_key: str, center_x: int, center_y: int, color_override: tuple = None):
        """Draw a centered miniature piece inside a preview box."""
        if not shape_key or shape_key not in PIECE_MATRICES:
            return

        offsets = PIECE_MATRICES[shape_key][0]
        color = color_override or SHAPE_COLORS[shape_key]
        mini_size = 18

        # Calculate bounding box to perfectly center the piece
        min_x = min(x for x, y in offsets)
        max_x = max(x for x, y in offsets)
        min_y = min(y for x, y in offsets)
        max_y = max(y for x, y in offsets)

        piece_w = (max_x - min_x + 1) * mini_size
        piece_h = (max_y - min_y + 1) * mini_size

        start_x = center_x - (piece_w // 2) - (min_x * mini_size)
        start_y = center_y - (piece_h // 2) - (min_y * mini_size)

        for ox, oy in offsets:
            bx = start_x + (ox * mini_size)
            by = start_y + (oy * mini_size)
            draw_beveled_block(self.screen, bx, by, mini_size, color)

    def _draw_overlay(self, title: str, subtitle: str):
        """Draw translucent modal overlay over the board."""
        overlay = pygame.Surface((BOARD_WIDTH, BOARD_HEIGHT), pygame.SRCALPHA)
        overlay.fill((10, 10, 15, 210))
        self.screen.blit(overlay, (self.board_x, self.board_y))

        title_surf = self.font_large.render(title, True, COLOR_TEXT_ACCENT)
        t_rect = title_surf.get_rect(center=(self.board_x + BOARD_WIDTH // 2, self.board_y + BOARD_HEIGHT // 2 - 25))
        self.screen.blit(title_surf, t_rect)

        sub_surf = self.font_small.render(subtitle, True, COLOR_TEXT_PRIMARY)
        s_rect = sub_surf.get_rect(center=(self.board_x + BOARD_WIDTH // 2, self.board_y + BOARD_HEIGHT // 2 + 25))
        self.screen.blit(sub_surf, s_rect)


# ---------------------------------------------------------
# MAIN GAME LOOP
# ---------------------------------------------------------
def main():
    """Initialize Pygame and run the main event loop."""
    pygame.init()
    pygame.font.init()

    # Initialize Sound Engine
    sound_engine = SoundEngine()

    screen = pygame.display.set_mode((SCREEN_WIDTH, SCREEN_HEIGHT))
    pygame.display.set_caption("Tetris")

    clock = pygame.time.Clock()
    game = TetrisGame(sound_engine)
    renderer = TetrisRenderer(screen)

    # Enable key repeat for responsive DAS (Delayed Auto Shift)
    # Delay: 170ms, Interval: 45ms
    pygame.key.set_repeat(170, 45)

    running = True
    while running:
        # 1. EVENT HANDLING
        for event in pygame.event.get():
            if event.type == pygame.QUIT:
                running = False

            elif event.type == pygame.KEYDOWN:
                # Global controls
                if event.key in (pygame.K_ESCAPE, pygame.K_p):
                    if not game.game_over:
                        game.paused = not game.paused
                        if game.paused:
                            sound_engine.pause_music()
                        else:
                            sound_engine.unpause_music()

                elif event.key == pygame.K_m:
                    sound_engine.toggle_mute()

                elif event.key == pygame.K_r:
                    game.reset()

                elif event.key == pygame.K_q and game.game_over:
                    running = False

                # Active gameplay controls (only when not paused / game over)
                elif not game.paused and not game.game_over:
                    if event.key in (pygame.K_LEFT, pygame.K_a):
                        game.move_horizontal(-1)

                    elif event.key in (pygame.K_RIGHT, pygame.K_d):
                        game.move_horizontal(1)

                    elif event.key in (pygame.K_UP, pygame.K_w, pygame.K_x):
                        game.rotate_piece(clockwise=True)

                    elif event.key == pygame.K_z:
                        game.rotate_piece(clockwise=False)

                    elif event.key in (pygame.K_DOWN, pygame.K_s):
                        game.soft_drop()

                    elif event.key == pygame.K_SPACE:
                        game.hard_drop()

                    elif event.key in (pygame.K_c, pygame.K_LSHIFT, pygame.K_RSHIFT):
                        game.hold_current_piece()

        # 2. LOGIC UPDATE
        game.update()

        # 3. RENDERING
        renderer.draw_game(game)
        pygame.display.flip()
        clock.tick(FPS)

    pygame.quit()
    sys.exit()


if __name__ == "__main__":
    main()

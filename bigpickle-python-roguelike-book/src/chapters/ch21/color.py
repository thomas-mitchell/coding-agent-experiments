"""Shared color palette for console output and the message log."""
from __future__ import annotations

# --- Base colors ---------------------------------------------------------
WHITE = (255, 255, 255)
GRAY = (200, 200, 200)
DIM_GRAY = (128, 128, 128)
BLACK = (0, 0, 0)

# --- Feedback colors -----------------------------------------------------
YELLOW = (255, 255, 0)          # player dealing damage
LIGHT_CYAN = (120, 200, 255)    # informative hints
CYAN = (0, 255, 255)            # equipment / magic
GREEN = (0, 255, 0)             # healing
RED = (255, 0, 0)               # player taking damage
LIGHT_RED = (255, 120, 120)
ORANGE = (255, 165, 0)          # item pickups
BLUE = (150, 150, 255)          # XP / level ups
PURPLE = (200, 120, 255)        # magical scrolls

# --- XP / leveling -------------------------------------------------------
XP_BAR_FILL = (150, 150, 255)   # filled portion of the XP bar
XP_BAR_EMPTY = (40, 40, 80)     # empty portion of the XP bar
LEVEL_UP_FG = (255, 255, 0)     # "Level Up!" title
LEVEL_UP_BG = (40, 0, 40)
CHOICE_FG = (200, 200, 200)
CHOICE_HINT = (150, 150, 150)

# --- Stairs / levels -----------------------------------------------------
MAGENTA = (255, 0, 255)         # the descending staircase
FLOOR_HINT = (200, 200, 120)    # "You are on floor N" banner

# --- Targeting overlay ---------------------------------------------------
TARGET_FG = (255, 255, 255)
TARGET_BG = (255, 0, 0)         # cursor highlight
AREA_FG = (255, 120, 0)         # area-of-effect ring

# --- Panel accent colors -------------------------------------------------
PANEL_BORDER = (100, 100, 100)
PANEL_TEXT = (255, 255, 255)
PANEL_SUBTEXT = (180, 180, 180)

# --- Log history window --------------------------------------------------
HISTORY_FG = (200, 200, 255)
HISTORY_BG = (0, 0, 0)
HISTORY_TITLE = (255, 255, 255)
HISTORY_HINT = (150, 150, 150)

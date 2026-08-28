from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True, slots=True)
class Color:
    """An RGB color value."""

    r: int
    g: int
    b: int

    def __iter__(self):
        yield self.r
        yield self.g
        yield self.b

    def __getitem__(self, index: int) -> int:
        return (self.r, self.g, self.b)[index]

    def __len__(self) -> int:
        return 3

    @property
    def tuple(self) -> tuple[int, int, int]:
        return (self.r, self.g, self.b)


white = Color(255, 255, 255)
black = Color(0, 0, 0)
grey = Color(128, 128, 128)
dark_grey = Color(50, 50, 50)
light_grey = Color(180, 180, 180)

red = Color(255, 0, 0)
dark_red = Color(128, 0, 0)
light_red = Color(255, 100, 100)

green = Color(0, 255, 0)
dark_green = Color(0, 128, 0)
light_green = Color(100, 255, 100)

blue = Color(0, 0, 255)
dark_blue = Color(0, 0, 128)
light_blue = Color(100, 100, 255)

yellow = Color(255, 255, 0)
dark_yellow = Color(128, 128, 0)

orange = Color(255, 165, 0)

purple = Color(128, 0, 128)
light_purple = Color(180, 100, 255)

# UI Colors
health_red = Color(200, 50, 50)
health_green = Color(50, 200, 50)
health_bg = Color(80, 0, 0)

panel_bg = Color(20, 20, 30)
panel_border = Color(80, 80, 120)

menu_bg = Color(10, 10, 20)
menu_highlight = Color(60, 60, 100)

# Entity colors
player_color = white
orc_color = green
troll_color = dark_green

# Item colors
potion_color = light_blue
scroll_color = yellow
sword_color = light_grey
shield_color = dark_grey
lightning_color = yellow
fireball_color = orange
confusion_color = light_purple

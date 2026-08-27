"""
Python Snake Game - Enhanced Edition
Features:
- Dynamic Color Gradients (multi-stop snake gradients & pulsating food)
- Customizable Themes (Cyberpunk, Emerald Viper, Solar Flare, Cosmic Galaxy)
- Built-in Retro Sound Effects via Windows winsound (asynchronous & non-blocking)
- Particle Burst Animations on scoring
- Neon Glow borders and Matrix grid dots
- Session High Score, Pause, Mute, and Instant Restart
"""

import math
import random
import threading
import time
import turtle

# ==============================================================================
# SOUND SYSTEM (Asynchronous & Cross-Platform Safe)
# ==============================================================================
try:
    import winsound
    HAS_WINSOUND = True
except ImportError:
    HAS_WINSOUND = False

sound_enabled = True


def play_sound(sound_type):
    """Play retro 8-bit sound effects asynchronously to prevent game lag."""
    if not sound_enabled or not HAS_WINSOUND:
        return

    def _worker():
        try:
            if sound_type == "eat":
                winsound.Beep(587, 35)   # D5
                winsound.Beep(880, 50)   # A5
            elif sound_type == "milestone":
                winsound.Beep(523, 30)   # C5
                winsound.Beep(659, 30)   # E5
                winsound.Beep(784, 30)   # G5
                winsound.Beep(1046, 60)  # C6
            elif sound_type == "game_over":
                winsound.Beep(370, 70)   # F#4
                winsound.Beep(293, 80)   # D4
                winsound.Beep(220, 90)   # A3
                winsound.Beep(146, 160)  # D3
            elif sound_type == "pause":
                winsound.Beep(523, 40)   # C5
            elif sound_type == "theme":
                winsound.Beep(698, 30)   # F5
                winsound.Beep(880, 45)   # A5
            elif sound_type == "restart":
                winsound.Beep(440, 40)   # A4
                winsound.Beep(660, 60)   # E5
        except Exception:
            pass

    threading.Thread(target=_worker, daemon=True).start()


# ==============================================================================
# COLOR & GRADIENT ENGINE
# ==============================================================================
def lerp_color(c1, c2, t):
    """Linearly interpolate between two RGB tuples (0-255)."""
    return (
        int(c1[0] + (c2[0] - c1[0]) * t),
        int(c1[1] + (c2[1] - c1[1]) * t),
        int(c1[2] + (c2[2] - c1[2]) * t),
    )


def sample_gradient(color_stops, t):
    """
    Interpolate smoothly across a multi-stop color palette.
    t is clamped between 0.0 (head) and 1.0 (tail).
    """
    t = max(0.0, min(1.0, t))
    if len(color_stops) == 1:
        return color_stops[0]

    scaled = t * (len(color_stops) - 1)
    idx = int(scaled)
    if idx >= len(color_stops) - 1:
        return color_stops[-1]

    local_t = scaled - idx
    return lerp_color(color_stops[idx], color_stops[idx + 1], local_t)


# Color Themes with multi-stop gradients
THEMES = [
    {
        "name": "Cyberpunk Neon",
        "bg": (14, 17, 26),
        "grid_dot": (28, 35, 55),
        "border_outer": (90, 20, 150),
        "border_inner": (0, 230, 255),
        "snake_stops": [
            (0, 255, 200),    # Bright Cyan Head
            (0, 190, 255),    # Electric Blue
            (140, 80, 255),   # Vivid Purple
            (255, 0, 140),    # Neon Magenta
            (255, 90, 0),     # Hot Orange Tail
        ],
        "food_stops": [
            (255, 50, 80),    # Crimson Red
            (255, 140, 0),    # Bright Orange
            (255, 220, 0),    # Golden Amber
        ],
        "accent": (0, 255, 200),
    },
    {
        "name": "Emerald Viper",
        "bg": (10, 22, 18),
        "grid_dot": (20, 45, 35),
        "border_outer": (15, 60, 40),
        "border_inner": (0, 255, 140),
        "snake_stops": [
            (57, 255, 20),    # Neon Lime Head
            (0, 240, 150),    # Emerald
            (0, 180, 160),    # Sea Green
            (0, 120, 130),    # Deep Teal
            (10, 60, 70),     # Dark Forest Tail
        ],
        "food_stops": [
            (255, 75, 75),    # Ruby Red
            (255, 170, 0),    # Bright Amber
            (255, 235, 59),   # Electric Yellow
        ],
        "accent": (57, 255, 20),
    },
    {
        "name": "Solar Flare",
        "bg": (20, 12, 12),
        "grid_dot": (45, 25, 25),
        "border_outer": (120, 30, 20),
        "border_inner": (255, 150, 0),
        "snake_stops": [
            (255, 240, 100),  # Bright Sun Gold
            (255, 165, 0),    # Vibrant Orange
            (255, 70, 40),    # Lava Coral
            (200, 20, 60),    # Deep Crimson
            (100, 10, 50),    # Dark Wine Tail
        ],
        "food_stops": [
            (0, 240, 255),    # Electric Aqua
            (100, 150, 255),  # Ice Blue
            (200, 100, 255),  # Lilac Glow
        ],
        "accent": (255, 200, 50),
    },
    {
        "name": "Cosmic Galaxy",
        "bg": (12, 10, 25),
        "grid_dot": (30, 25, 55),
        "border_outer": (60, 20, 90),
        "border_inner": (180, 100, 255),
        "snake_stops": [
            (220, 150, 255),  # Electric Lavender
            (140, 70, 255),   # Deep Purple
            (60, 120, 255),   # Royal Blue
            (0, 210, 240),    # Cyan
            (0, 255, 180),    # Mint Tail
        ],
        "food_stops": [
            (255, 60, 140),   # Neon Rose
            (255, 120, 80),   # Peach
            (255, 215, 0),    # Starlight Gold
        ],
        "accent": (200, 130, 255),
    },
]

current_theme_idx = 0


# ==============================================================================
# CONFIGURATION & CONSTANTS
# ==============================================================================
WINDOW_WIDTH = 640
WINDOW_HEIGHT = 680
GRID_SIZE = 20
INITIAL_DELAY = 0.09
MIN_DELAY = 0.035
SPEEDUP_RATE = 0.002

# Play Area Bounds
PLAY_MIN_X = -280
PLAY_MAX_X = 280
PLAY_MIN_Y = -280
PLAY_MAX_Y = 200

# Game State
score = 0
high_score = 0
delay = INITIAL_DELAY
game_over = False
is_paused = False
frame_count = 0
segments = []

# ==============================================================================
# TURTLE SETUP
# ==============================================================================
screen = turtle.Screen()
screen.title("Python Snake Game - Neon Gradient Edition")
turtle.colormode(255)
screen.setup(width=WINDOW_WIDTH, height=WINDOW_HEIGHT)
screen.tracer(0)

# Background & Grid Turtle
bg_drawer = turtle.Turtle()
bg_drawer.speed(0)
bg_drawer.hideturtle()

# Snake Head
head = turtle.Turtle()
head.speed(0)
head.shape("square")
head.shapesize(0.92, 0.92)  # Slight spacing for modern segmented look
head.penup()
head.goto(0, -40)
head.direction = "stop"

# Snake Food
food = turtle.Turtle()
food.speed(0)
food.shape("circle")
food.shapesize(0.85, 0.85)
food.penup()

# Scoreboard Pen
pen = turtle.Turtle()
pen.speed(0)
pen.penup()
pen.hideturtle()

# Center Message Pen (Game Over & Pause)
msg_pen = turtle.Turtle()
msg_pen.speed(0)
msg_pen.penup()
msg_pen.hideturtle()

# Particle System Pool (Reused for eat effects)
MAX_PARTICLES = 10
particles = []
for _ in range(MAX_PARTICLES):
    p = turtle.Turtle()
    p.speed(0)
    p.shape("circle")
    p.shapesize(0.35, 0.35)
    p.penup()
    p.hideturtle()
    particles.append({"turtle": p, "x": 0, "y": 0, "vx": 0, "vy": 0, "life": 0, "color": (255, 255, 255)})


# ==============================================================================
# DRAWING & RENDERING
# ==============================================================================
def draw_board():
    """Renders background, matrix grid dots, and glowing gradient borders."""
    theme = THEMES[current_theme_idx]
    screen.bgcolor(theme["bg"])
    bg_drawer.clear()
    bg_drawer.penup()

    # Draw subtle matrix grid dots
    bg_drawer.color(theme["grid_dot"])
    for x in range(PLAY_MIN_X, PLAY_MAX_X + 1, GRID_SIZE):
        for y in range(PLAY_MIN_Y, PLAY_MAX_Y + 1, GRID_SIZE):
            bg_drawer.goto(x, y)
            bg_drawer.dot(2)

    # Draw Outer Glow Border
    bg_drawer.color(theme["border_outer"])
    bg_drawer.pensize(5)
    bg_drawer.goto(PLAY_MIN_X - 10, PLAY_MAX_Y + 10)
    bg_drawer.pendown()
    bg_drawer.goto(PLAY_MAX_X + 10, PLAY_MAX_Y + 10)
    bg_drawer.goto(PLAY_MAX_X + 10, PLAY_MIN_Y - 10)
    bg_drawer.goto(PLAY_MIN_X - 10, PLAY_MIN_Y - 10)
    bg_drawer.goto(PLAY_MIN_X - 10, PLAY_MAX_Y + 10)
    bg_drawer.penup()

    # Draw Inner Neon Border
    bg_drawer.color(theme["border_inner"])
    bg_drawer.pensize(2)
    bg_drawer.goto(PLAY_MIN_X - 10, PLAY_MAX_Y + 10)
    bg_drawer.pendown()
    bg_drawer.goto(PLAY_MAX_X + 10, PLAY_MAX_Y + 10)
    bg_drawer.goto(PLAY_MAX_X + 10, PLAY_MIN_Y - 10)
    bg_drawer.goto(PLAY_MIN_X - 10, PLAY_MIN_Y - 10)
    bg_drawer.goto(PLAY_MIN_X - 10, PLAY_MAX_Y + 10)
    bg_drawer.penup()


def update_scoreboard():
    """Renders the top HUD with score, high score, theme name, and audio status."""
    theme = THEMES[current_theme_idx]
    pen.clear()

    # Main Score & High Score
    pen.goto(0, 270)
    pen.color((255, 255, 255))
    pen.write(
        f"SCORE: {score:03d}     HIGH SCORE: {high_score:03d}",
        align="center",
        font=("Courier", 17, "bold"),
    )

    # Theme & Sound Status Bar
    pen.goto(0, 240)
    sound_status = "ON 🔊" if sound_enabled else "OFF 🔇"
    pen.color(theme["accent"])
    pen.write(
        f"Theme [T]: {theme['name']}   |   Sound [M]: {sound_status}",
        align="center",
        font=("Courier", 11, "normal"),
    )


def apply_snake_gradient():
    """Colors each snake segment dynamically along the theme's gradient stops."""
    theme = THEMES[current_theme_idx]
    stops = theme["snake_stops"]
    head_color = stops[0]
    head.color(head_color)

    num_segments = len(segments)
    if num_segments == 0:
        return

    for idx, seg in enumerate(segments):
        # Calculate t parameter from 0.0 (near head) to 1.0 (tail)
        t = (idx + 1) / max(1, num_segments)
        seg_color = sample_gradient(stops, t)
        seg.color(seg_color)


def get_food_pulsing_color():
    """Returns an oscillating gradient color for the food orb."""
    theme = THEMES[current_theme_idx]
    stops = theme["food_stops"]
    # Create a smooth sine-wave oscillation between 0.0 and 1.0
    pulse_t = (math.sin(frame_count * 0.2) + 1.0) / 2.0
    return sample_gradient(stops, pulse_t)


def show_banner(main_text, sub_text=""):
    """Displays a stylized banner message in the center of the screen."""
    msg_pen.clear()
    if main_text:
        msg_pen.goto(0, -10)
        msg_pen.color((255, 60, 90))
        msg_pen.write(main_text, align="center", font=("Arial", 26, "bold"))
    if sub_text:
        msg_pen.goto(0, -50)
        msg_pen.color((255, 255, 255))
        msg_pen.write(sub_text, align="center", font=("Arial", 13, "normal"))


def clear_banner():
    """Clears the center banner."""
    msg_pen.clear()


# ==============================================================================
# PARTICLE SYSTEM
# ==============================================================================
def trigger_particle_burst(x, y, base_color):
    """Spawns an energetic radial particle burst when food is eaten."""
    for p_data in particles:
        angle = random.uniform(0, 2 * math.pi)
        speed = random.uniform(3, 8)
        p_data["x"] = x
        p_data["y"] = y
        p_data["vx"] = math.cos(angle) * speed
        p_data["vy"] = math.sin(angle) * speed
        p_data["life"] = random.randint(5, 9)
        p_data["color"] = base_color
        p = p_data["turtle"]
        p.goto(x, y)
        p.color(base_color)
        p.showturtle()


def update_particles():
    """Updates positions and lifetimes of active particles."""
    for p_data in particles:
        if p_data["life"] > 0:
            p_data["x"] += p_data["vx"]
            p_data["y"] += p_data["vy"]
            p_data["life"] -= 1
            p = p_data["turtle"]
            p.goto(p_data["x"], p_data["y"])
            if p_data["life"] <= 0:
                p.hideturtle()


# ==============================================================================
# GAMEPLAY LOGIC
# ==============================================================================
def get_random_food_position():
    """Generate a grid-aligned random position inside the playable bounds."""
    x = random.randint(PLAY_MIN_X // GRID_SIZE, PLAY_MAX_X // GRID_SIZE) * GRID_SIZE
    y = random.randint(PLAY_MIN_Y // GRID_SIZE, PLAY_MAX_Y // GRID_SIZE) * GRID_SIZE
    return x, y


def place_food():
    """Place food on an empty grid tile not occupied by snake."""
    while True:
        fx, fy = get_random_food_position()
        collision = head.distance(fx, fy) < GRID_SIZE or any(
            seg.distance(fx, fy) < GRID_SIZE for seg in segments
        )
        if not collision:
            food.goto(fx, fy)
            break


def go_up():
    if head.direction != "down" and not game_over and not is_paused:
        head.direction = "up"


def go_down():
    if head.direction != "up" and not game_over and not is_paused:
        head.direction = "down"


def go_left():
    if head.direction != "right" and not game_over and not is_paused:
        head.direction = "left"


def go_right():
    if head.direction != "left" and not game_over and not is_paused:
        head.direction = "right"


def toggle_pause():
    global is_paused
    if game_over:
        return
    is_paused = not is_paused
    play_sound("pause")
    if is_paused:
        show_banner("PAUSED", "Press SPACE or P to resume")
    else:
        clear_banner()


def toggle_sound():
    global sound_enabled
    sound_enabled = not sound_enabled
    if sound_enabled:
        play_sound("pause")
    update_scoreboard()


def cycle_theme():
    """Switches to the next gradient theme palette in real time."""
    global current_theme_idx
    current_theme_idx = (current_theme_idx + 1) % len(THEMES)
    draw_board()
    apply_snake_gradient()
    update_scoreboard()
    play_sound("theme")


def move():
    """Moves the snake head forward by one grid unit."""
    if head.direction == "up":
        head.sety(head.ycor() + GRID_SIZE)
    elif head.direction == "down":
        head.sety(head.ycor() - GRID_SIZE)
    elif head.direction == "left":
        head.setx(head.xcor() - GRID_SIZE)
    elif head.direction == "right":
        head.setx(head.xcor() + GRID_SIZE)


def reset_game():
    """Resets the game after game over."""
    global score, delay, game_over, segments, is_paused

    time.sleep(0.15)
    for seg in segments:
        seg.goto(1000, 1000)
    segments.clear()

    head.goto(0, -40)
    head.direction = "stop"
    score = 0
    delay = INITIAL_DELAY
    game_over = False
    is_paused = False

    place_food()
    clear_banner()
    apply_snake_gradient()
    update_scoreboard()
    play_sound("restart")


def handle_game_over():
    """Triggers the game over state with sound and visual banner."""
    global game_over
    game_over = True
    head.direction = "stop"
    play_sound("game_over")
    show_banner("GAME OVER", "Press SPACE or R to play again")


def restart_or_unpause():
    """Handles space bar: restarts if game over, else toggles pause."""
    if game_over:
        reset_game()
    else:
        toggle_pause()


# ==============================================================================
# KEYBOARD BINDINGS
# ==============================================================================
screen.listen()

# Direction Controls (Arrows & WASD)
screen.onkeypress(go_up, "Up")
screen.onkeypress(go_down, "Down")
screen.onkeypress(go_left, "Left")
screen.onkeypress(go_right, "Right")

screen.onkeypress(go_up, "w")
screen.onkeypress(go_up, "W")
screen.onkeypress(go_down, "s")
screen.onkeypress(go_down, "S")
screen.onkeypress(go_left, "a")
screen.onkeypress(go_left, "A")
screen.onkeypress(go_right, "d")
screen.onkeypress(go_right, "D")

# Game Management Keys
screen.onkeypress(restart_or_unpause, "space")
screen.onkeypress(toggle_pause, "p")
screen.onkeypress(toggle_pause, "P")
screen.onkeypress(reset_game, "r")
screen.onkeypress(reset_game, "R")
screen.onkeypress(cycle_theme, "t")
screen.onkeypress(cycle_theme, "T")
screen.onkeypress(toggle_sound, "m")
screen.onkeypress(toggle_sound, "M")


# ==============================================================================
# MAIN GAME LOOP
# ==============================================================================
def main():
    global score, high_score, delay, frame_count

    # Initialize Graphics
    draw_board()
    place_food()
    apply_snake_gradient()
    update_scoreboard()

    running = True
    while running:
        try:
            frame_count += 1

            # 1. Animate pulsating food gradient
            food_color = get_food_pulsing_color()
            food.color(food_color)

            # 2. Update particle burst animations
            update_particles()

            # 3. Game State Updates (when not paused/game over)
            if not is_paused and not game_over:
                # Boundary Collision Check
                if (
                    head.xcor() > PLAY_MAX_X
                    or head.xcor() < PLAY_MIN_X
                    or head.ycor() > PLAY_MAX_Y
                    or head.ycor() < PLAY_MIN_Y
                ):
                    handle_game_over()

                # Food Collision Check
                elif head.distance(food) < GRID_SIZE:
                    trigger_particle_burst(food.xcor(), food.ycor(), food_color)
                    place_food()

                    # Add new body segment
                    new_segment = turtle.Turtle()
                    new_segment.speed(0)
                    new_segment.shape("square")
                    new_segment.shapesize(0.92, 0.92)
                    new_segment.penup()
                    segments.append(new_segment)

                    # Update delay (speed up)
                    delay = max(MIN_DELAY, delay - SPEEDUP_RATE)

                    # Update Score
                    score += 10
                    if score > high_score:
                        high_score = score
                    update_scoreboard()

                    # Sound trigger
                    if score % 50 == 0:
                        play_sound("milestone")
                    else:
                        play_sound("eat")

                    # Re-apply color gradient across all segments
                    apply_snake_gradient()

                # Move Snake Body Segments
                if not game_over and head.direction != "stop":
                    for i in range(len(segments) - 1, 0, -1):
                        x = segments[i - 1].xcor()
                        y = segments[i - 1].ycor()
                        segments[i].goto(x, y)

                    if len(segments) > 0:
                        x = head.xcor()
                        y = head.ycor()
                        segments[0].goto(x, y)

                    # Move Snake Head
                    move()

                    # Self-Collision Check
                    for segment in segments:
                        if segment.distance(head) < 14:
                            handle_game_over()
                            break

            # Render frame
            screen.update()
            time.sleep(delay)

        except (turtle.Terminator, turtle.tkinter.TclError):
            running = False
            break


if __name__ == "__main__":
    main()

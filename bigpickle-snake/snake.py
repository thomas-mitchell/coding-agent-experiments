import pygame
import random
import sys
import numpy as np

pygame.init()
pygame.mixer.init(frequency=44100, size=-16, channels=1, buffer=512)

CELL = 20
COLS, ROWS = 30, 20
WIDTH, HEIGHT = COLS * CELL, ROWS * CELL
FPS = 10

WHITE = (255, 255, 255)
GREEN = (0, 200, 0)
DARK_GREEN = (0, 155, 0)
RED = (220, 30, 30)
BLACK = (20, 20, 20)
GRAY = (40, 40, 40)

screen = pygame.display.set_mode((WIDTH, HEIGHT))
pygame.display.set_caption("Snake")
clock = pygame.time.Clock()
font = pygame.font.SysFont("consolas", 24, bold=True)


SAMPLE_RATE = 44100


def make_sound(duration, gen_fn, volume=0.3):
    n = int(SAMPLE_RATE * duration)
    t = np.linspace(0, duration, n, dtype=np.float32)
    samples = gen_fn(t)
    samples = (samples * volume * 32767).astype(np.int16)
    return pygame.mixer.Sound(buffer=samples)


def eat_gen(t):
    freq = 880 + 440 * (t / 0.15)
    return np.sin(2 * np.pi * freq * t) * np.clip(1 - t / 0.15, 0, 1)


def die_gen(t):
    freq = 440 * np.exp(-3 * t)
    return np.sin(2 * np.pi * freq * t) * np.clip(1 - t / 0.5, 0, 1)


def bgm_gen(t):
    bpm = 140
    beat = bpm / 60
    notes = np.array([262, 330, 392, 330, 349, 330, 294, 262], dtype=np.float32)
    note_idx = (np.int_(t * beat) % len(notes)).astype(int)
    freq = notes[note_idx]
    return np.sin(2 * np.pi * freq * t) * 0.08


snd_eat = make_sound(0.15, eat_gen, 0.3)
snd_die = make_sound(0.5, die_gen, 0.4)

bgm_buf = make_sound(4.0, bgm_gen, 0.15)
bgm_channel = None


def play_bgm():
    global bgm_channel
    bgm_channel = bgm_buf.play(-1)


def stop_bgm():
    if bgm_channel:
        bgm_channel.stop()


def spawn_food(snake):
    while True:
        pos = (random.randint(0, COLS - 1), random.randint(0, ROWS - 1))
        if pos not in snake:
            return pos


def main():
    snake = [(COLS // 2, ROWS // 2)]
    direction = (1, 0)
    food = spawn_food(snake)
    score = 0
    alive = True

    play_bgm()

    while True:
        for event in pygame.event.get():
            if event.type == pygame.QUIT:
                stop_bgm()
                pygame.quit()
                sys.exit()
            if event.type == pygame.KEYDOWN:
                key = event.key
                if key in (pygame.K_ESCAPE, pygame.K_q):
                    stop_bgm()
                    pygame.quit()
                    sys.exit()
                if not alive:
                    if key == pygame.K_r:
                        main()
                    continue
                if key == pygame.K_UP and direction != (0, 1):
                    direction = (0, -1)
                elif key == pygame.K_DOWN and direction != (0, -1):
                    direction = (0, 1)
                elif key == pygame.K_LEFT and direction != (1, 0):
                    direction = (-1, 0)
                elif key == pygame.K_RIGHT and direction != (-1, 0):
                    direction = (1, 0)

        if not alive:
            draw(snake, food, score, alive)
            msg = font.render("GAME OVER  Press R to restart", True, RED)
            screen.blit(msg, (WIDTH // 2 - msg.get_width() // 2, HEIGHT // 2 - 12))
            pygame.display.flip()
            clock.tick(FPS)
            continue

        head = (snake[0][0] + direction[0], snake[0][1] + direction[1])

        if head[0] < 0 or head[0] >= COLS or head[1] < 0 or head[1] >= ROWS:
            alive = False
            stop_bgm()
            snd_die.play()
            continue
        if head in snake:
            alive = False
            stop_bgm()
            snd_die.play()
            continue

        snake.insert(0, head)
        if head == food:
            score += 1
            snd_eat.play()
            food = spawn_food(snake)
        else:
            snake.pop()

        draw(snake, food, score, alive)
        pygame.display.flip()
        clock.tick(FPS)


def draw(snake, food, score, alive):
    screen.fill(BLACK)

    for x in range(0, WIDTH, CELL):
        for y in range(0, HEIGHT, CELL):
            if (x // CELL + y // CELL) % 2 == 0:
                pygame.draw.rect(screen, GRAY, (x, y, CELL, CELL))

    fx, fy = food
    pygame.draw.rect(screen, RED, (fx * CELL + 2, fy * CELL + 2, CELL - 4, CELL - 4), border_radius=4)

    for i, (sx, sy) in enumerate(snake):
        color = GREEN if i == 0 else DARK_GREEN
        rect = pygame.Rect(sx * CELL + 1, sy * CELL + 1, CELL - 2, CELL - 2)
        pygame.draw.rect(screen, color, rect, border_radius=3)

    score_surf = font.render(f"Score: {score}", True, WHITE)
    screen.blit(score_surf, (8, 4))


if __name__ == "__main__":
    main()

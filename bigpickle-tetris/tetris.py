import pygame
import random
import sys
import numpy as np

CELL = 30
COLS = 10
ROWS = 20
SIDEBAR = 200
WIDTH = COLS * CELL + SIDEBAR
HEIGHT = ROWS * CELL
FPS = 60
SAMPLE_RATE = 44100

SHAPES = [
    [[1, 1, 1, 1]],
    [[1, 1], [1, 1]],
    [[0, 1, 0], [1, 1, 1]],
    [[1, 0, 0], [1, 1, 1]],
    [[0, 0, 1], [1, 1, 1]],
    [[1, 1, 0], [0, 1, 1]],
    [[0, 1, 1], [1, 1, 0]],
]

COLORS = [
    (0, 240, 240),
    (240, 240, 0),
    (160, 0, 240),
    (0, 0, 240),
    (240, 160, 0),
    (0, 240, 0),
    (240, 0, 0),
]

DARK = (20, 20, 30)
GRID_COLOR = (40, 40, 55)
BORDER_COLOR = (80, 80, 100)
BG = (15, 15, 25)
WHITE = (220, 220, 230)
GRAY = (120, 120, 140)
GHOST_ALPHA = 50


def _samples(dur):
    return int(SAMPLE_RATE * dur)


def _sine(freq, dur, vol=0.3):
    t = np.linspace(0, dur, _samples(dur), False)
    return np.sin(2 * np.pi * freq * t) * vol


def _triangle(freq, dur, vol=0.3):
    t = np.linspace(0, dur, _samples(dur), False)
    return (2 * np.abs(2 * ((t * freq) % 1.0) - 1) - 1) * vol


def _pulse(freq, dur, vol=0.3, duty=0.25):
    t = np.linspace(0, dur, _samples(dur), False)
    phase = (t * freq) % 1.0
    return np.where(phase < duty, vol, -vol)


def _square(freq, dur, vol=0.3):
    return _pulse(freq, dur, vol, 0.5)


def _adsr(dur, attack=0.005, decay=0.05, sustain=0.7, release=0.05):
    n = _samples(dur)
    env = np.ones(n)
    a = min(_samples(attack), n)
    d = min(_samples(decay), n - a)
    r = min(_samples(release), n)
    s = n - a - d - r
    if a > 0:
        env[:a] = np.linspace(0, 1, a)
    if d > 0:
        env[a:a + d] = np.linspace(1, sustain, d)
    if s > 0:
        env[a + d:a + d + s] = sustain
    if r > 0:
        env[-r:] = np.linspace(sustain, 0, r)
    return env


def _to_sound(samples):
    peak = np.max(np.abs(samples))
    if peak > 0:
        samples = samples / peak * 0.9
    raw = (samples * 32767).astype(np.int16)
    return pygame.sndarray.make_sound(np.column_stack((raw, raw)))


def _note_sound(freq, dur, vol, wave_fn, duty=None):
    if freq <= 0:
        return np.zeros(_samples(dur))
    if duty is not None:
        wave = wave_fn(freq, dur, vol, duty)
    else:
        wave = wave_fn(freq, dur, vol)
    return wave * _adsr(dur)


def _melody_sound(notes, note_dur, volume, wave_fn):
    parts = []
    for freq in notes:
        parts.append(_note_sound(freq, note_dur, volume, wave_fn))
    return _to_sound(np.concatenate(parts))


class SoundManager:
    def __init__(self):
        self.sfx = {}
        self._gen_sfx()
        self._gen_music()

    def _gen_sfx(self):
        s = _note_sound(880, 0.04, 0.10, _pulse)
        self.sfx["move"] = _to_sound(s)

        s = _note_sound(660, 0.05, 0.10, _pulse)
        self.sfx["rotate"] = _to_sound(s)

        thud = np.concatenate([_sine(120, 0.06, 0.18), _sine(70, 0.1, 0.13)])
        self.sfx["drop"] = _to_sound(_note_sound(0, 0.16, 0, _sine) + thud * _adsr(0.16))

        self.sfx["clear1"] = _melody_sound([523, 659, 784], 0.1, 0.13, _pulse)
        self.sfx["clear4"] = _melody_sound([523, 659, 784, 1047, 1319], 0.12, 0.15, _pulse)
        self.sfx["hold"] = _to_sound(_note_sound(1200, 0.03, 0.08, _pulse))
        self.sfx["levelup"] = _melody_sound([440, 554, 659, 880], 0.1, 0.13, _pulse)
        self.sfx["gameover"] = _melody_sound([440, 392, 349, 330, 294, 262], 0.2, 0.15, _pulse)

    def _gen_music(self):
        # Frequencies (A minor)
        E5, B4, C5, D5, A4 = 659.25, 493.88, 523.25, 587.33, 440.00
        Ab4, G4 = 415.30, 392.00
        F5, G5, A5 = 698.46, 783.99, 880.00
        E3, A2, B2, C3, D3 = 164.81, 110.00, 123.47, 130.81, 146.83
        R = 0

        # durations: 1 = eighth note, 0.5 = sixteenth, 2 = quarter
        e = 1
        s = 0.5
        q = 2

        # Korobeiniki A section (melody)
        A_mel = [
            (E5,e),(B4,e),(C5,e),(D5,e),(C5,e),(B4,e),(A4,q),
            (A4,e),(C5,e),(E5,e),(D5,e),(C5,q),(B4,q),
            (C5,e),(D5,e),(E5,e),(C5,e),(A4,q),(A4,q),
            (D5,e),(F5,e),(A5,e),(G5,e),(F5,q),(E5,q),
            (C5,e),(E5,e),(D5,e),(C5,e),(B4,q),(R,q),
            (B4,e),(C5,e),(D5,e),(E5,e),(C5,e),(A4,e),(A4,q),
        ]

        # Korobeiniki B section (bridge)
        B_mel = [
            (E5,e),(C5,e),(D5,e),(B4,e),(C5,e),(A4,e),(Ab4,e),(B4,e),
            (E5,e),(C5,e),(D5,e),(B4,e),(C5,e),(E5,e),(A4,q),
        ]

        melody_seq = A_mel + A_mel + B_mel

        bass_line = [
            (E3,q),(A2,q),(C3,q),(A2,q),
            (A2,q),(C3,q),(A2,q),(A2,q),
            (D3,q),(A2,q),(A2,q),(A2,q),
            (A2,q),(C3,q),(A2,q),(A2,q),
            (D3,q),(A2,q),(E3,q),(A2,q),
            (A2,q),(C3,q),(A2,q),(A2,q),
            (D3,q),(A2,q),(A2,q),(A2,q),
        ]

        eighth = 0.2

        mel_parts = []
        for freq, beats in melody_seq:
            dur = beats * eighth
            mel_parts.append(_note_sound(freq, dur, 0.06, _pulse, 0.25))
        mel_wave = np.concatenate(mel_parts)

        bass_parts = []
        for freq, beats in bass_line:
            dur = beats * eighth
            bass_parts.append(_triangle(freq, dur, 0.04) * _adsr(dur, 0.005, 0.03, 0.8, 0.03))
        bass_wave = np.concatenate(bass_parts)

        max_len = max(len(mel_wave), len(bass_wave))
        mel_wave = np.pad(mel_wave, (0, max_len - len(mel_wave)))
        bass_wave = np.pad(bass_wave, (0, max_len - len(bass_wave)))
        mixed = mel_wave + bass_wave
        self.music_sound = _to_sound(mixed)

    def play(self, name):
        if name in self.sfx:
            self.sfx[name].play()


def rotate(matrix):
    return [list(row) for row in zip(*matrix[::-1])]


class Piece:
    def __init__(self):
        idx = random.randint(0, len(SHAPES) - 1)
        self.shape = [row[:] for row in SHAPES[idx]]
        self.color = COLORS[idx]
        self.x = COLS // 2 - len(self.shape[0]) // 2
        self.y = 0

    def rotated(self):
        return rotate(self.shape)


class Board:
    def __init__(self):
        self.grid = [[None] * COLS for _ in range(ROWS)]

    def valid(self, shape, ox, oy):
        for r, row in enumerate(shape):
            for c, cell in enumerate(row):
                if cell:
                    x, y = ox + c, oy + r
                    if x < 0 or x >= COLS or y >= ROWS:
                        return False
                    if y >= 0 and self.grid[y][x] is not None:
                        return False
        return True

    def lock(self, piece):
        for r, row in enumerate(piece.shape):
            for c, cell in enumerate(row):
                if cell:
                    y = piece.y + r
                    x = piece.x + c
                    if 0 <= y < ROWS and 0 <= x < COLS:
                        self.grid[y][x] = piece.color

    def clear_lines(self):
        cleared = 0
        new_grid = []
        for row in self.grid:
            if all(cell is not None for cell in row):
                cleared += 1
            else:
                new_grid.append(row)
        for _ in range(cleared):
            new_grid.insert(0, [None] * COLS)
        self.grid = new_grid
        return cleared


class Game:
    def __init__(self, sound=None):
        self.sound = sound
        self.board = Board()
        self.current = Piece()
        self.next_piece = Piece()
        self.held = None
        self.can_hold = True
        self.score = 0
        self.lines = 0
        self.level = 1
        self.game_over = False
        self.drop_timer = 0
        self.das_timer = 0
        self.das_dir = 0
        self.das_delay = 170
        self.das_repeat = 50
        self.das_charged = False

    def drop_interval(self):
        return max(50, 500 - (self.level - 1) * 40)

    def lock_current(self):
        self.board.lock(self.current)
        cleared = self.board.clear_lines()
        if cleared:
            points = {1: 100, 2: 300, 3: 500, 4: 800}
            self.score += points.get(cleared, 0) * self.level
            self.lines += cleared
            if self.sound:
                self.sound.play("clear4" if cleared >= 4 else "clear1")
            old_level = self.level
            self.level = self.lines // 10 + 1
            if self.level > old_level and self.sound:
                self.sound.play("levelup")
        self.current = self.next_piece
        self.next_piece = Piece()
        self.can_hold = True
        self.drop_timer = 0
        if not self.board.valid(self.current.shape, self.current.x, self.current.y):
            self.game_over = True
            if self.sound:
                self.sound.play("gameover")

    def ghost_y(self):
        y = self.current.y
        while self.board.valid(self.current.shape, self.current.x, y + 1):
            y += 1
        return y

    def try_rotate(self):
        new_shape = self.current.rotated()
        if self.board.valid(new_shape, self.current.x, self.current.y):
            self.current.shape = new_shape
            if self.sound:
                self.sound.play("rotate")
            return
        for dx in (-1, 1, -2, 2):
            if self.board.valid(new_shape, self.current.x + dx, self.current.y):
                self.current.x += dx
                self.current.shape = new_shape
                if self.sound:
                    self.sound.play("rotate")
                return

    def hold(self):
        if not self.can_hold:
            return
        self.can_hold = False
        if self.sound:
            self.sound.play("hold")
        if self.held is None:
            self.held = Piece()
            self.held.shape = [row[:] for row in self.current.shape]
            self.held.color = self.current.color
            self.current = self.next_piece
            self.next_piece = Piece()
        else:
            tmp = Piece()
            tmp.shape = [row[:] for row in self.current.shape]
            tmp.color = self.current.color
            self.current = Piece()
            self.current.shape = [row[:] for row in self.held.shape]
            self.current.color = self.held.color
            self.held = tmp
        self.drop_timer = 0
        if not self.board.valid(self.current.shape, self.current.x, self.current.y):
            self.game_over = True
            if self.sound:
                self.sound.play("gameover")

    def hard_drop(self):
        while self.board.valid(self.current.shape, self.current.x, self.current.y + 1):
            self.current.y += 1
            self.score += 2
        if self.sound:
            self.sound.play("drop")
        self.lock_current()

    def update(self, dt):
        if self.game_over:
            return
        self.drop_timer += dt
        if self.drop_timer >= self.drop_interval():
            self.drop_timer = 0
            if self.board.valid(self.current.shape, self.current.x, self.current.y + 1):
                self.current.y += 1
            else:
                self.lock_current()


def draw_block(surface, x, y, color, alpha=255):
    rect = pygame.Rect(x * CELL, y * CELL, CELL, CELL)
    if alpha < 255:
        s = pygame.Surface((CELL, CELL), pygame.SRCALPHA)
        s.fill((*color, alpha))
        surface.blit(s, rect.topleft)
    else:
        surface.fill(color, rect)
        lighter = tuple(min(c + 30, 255) for c in color)
        darker = tuple(max(c - 30, 0) for c in color)
        pygame.draw.rect(surface, lighter, (x * CELL + 1, y * CELL + 1, CELL - 2, 4))
        pygame.draw.rect(surface, lighter, (x * CELL + 1, y * CELL + 1, 4, CELL - 2))
        pygame.draw.rect(surface, darker, (x * CELL + CELL - 5, y * CELL + 1, 4, CELL - 2))
        pygame.draw.rect(surface, darker, (x * CELL + 1, y * CELL + CELL - 5, CELL - 2, 4))


def draw_shape(surface, shape, color, ox, oy, cell_size, alpha=255):
    for r, row in enumerate(shape):
        for c, cell in enumerate(row):
            if cell:
                rect = pygame.Rect(ox + c * cell_size, oy + r * cell_size, cell_size, cell_size)
                if alpha < 255:
                    s = pygame.Surface((cell_size, cell_size), pygame.SRCALPHA)
                    s.fill((*color, alpha))
                    surface.blit(s, rect.topleft)
                else:
                    surface.fill(color, rect)
                    lighter = tuple(min(v + 30, 255) for v in color)
                    darker = tuple(max(v - 30, 0) for v in color)
                    pygame.draw.rect(surface, lighter, (rect.x + 1, rect.y + 1, cell_size - 2, 3))
                    pygame.draw.rect(surface, lighter, (rect.x + 1, rect.y + 1, 3, cell_size - 2))
                    pygame.draw.rect(surface, darker, (rect.x + cell_size - 4, rect.y + 1, 3, cell_size - 2))
                    pygame.draw.rect(surface, darker, (rect.x + 1, rect.y + cell_size - 4, cell_size - 2, 3))
                pygame.draw.rect(surface, BORDER_COLOR, rect, 1)


def draw_board(surface, board):
    for r in range(ROWS):
        for c in range(COLS):
            rect = pygame.Rect(c * CELL, r * CELL, CELL, CELL)
            if board.grid[r][c] is not None:
                draw_block(surface, c, r, board.grid[r][c])
            else:
                surface.fill(DARK, rect)
            pygame.draw.rect(surface, GRID_COLOR, rect, 1)


def draw_sidebar(surface, game, font):
    sx = COLS * CELL + 15

    label = font.render("NEXT", True, GRAY)
    surface.blit(label, (sx, 10))
    if game.next_piece:
        draw_shape(surface, game.next_piece.shape, game.next_piece.color, sx, 35, 22)

    label = font.render("HOLD", True, GRAY)
    surface.blit(label, (sx, 110))
    if game.held:
        draw_shape(surface, game.held.shape, game.held.color, sx, 135, 22, 255 if game.can_hold else 80)

    label = font.render("SCORE", True, GRAY)
    surface.blit(label, (sx, 220))
    val = font.render(str(game.score), True, WHITE)
    surface.blit(val, (sx, 242))

    label = font.render("LINES", True, GRAY)
    surface.blit(label, (sx, 282))
    val = font.render(str(game.lines), True, WHITE)
    surface.blit(val, (sx, 304))

    label = font.render("LEVEL", True, GRAY)
    surface.blit(label, (sx, 342))
    val = font.render(str(game.level), True, WHITE)
    surface.blit(val, (sx, 364))


def draw_game_over(surface, font, big_font):
    overlay = pygame.Surface((WIDTH, HEIGHT), pygame.SRCALPHA)
    overlay.fill((0, 0, 0, 150))
    surface.blit(overlay, (0, 0))
    text = big_font.render("GAME OVER", True, (255, 80, 80))
    rect = text.get_rect(center=(COLS * CELL // 2, HEIGHT // 2 - 20))
    surface.blit(text, rect)
    text2 = font.render("Press R to restart", True, GRAY)
    rect2 = text2.get_rect(center=(COLS * CELL // 2, HEIGHT // 2 + 20))
    surface.blit(text2, rect2)


def main():
    pygame.init()
    pygame.mixer.set_num_channels(16)
    screen = pygame.display.set_mode((WIDTH, HEIGHT))
    pygame.display.set_caption("Tetris")
    clock = pygame.time.Clock()
    font = pygame.font.SysFont("consolas", 18, bold=True)
    big_font = pygame.font.SysFont("consolas", 32, bold=True)

    sound = SoundManager()
    music_channel = pygame.mixer.Channel(0)
    music_channel.play(sound.music_sound, -1)

    game = Game(sound)

    while True:
        dt = clock.tick(FPS)

        for event in pygame.event.get():
            if event.type == pygame.QUIT:
                pygame.quit()
                sys.exit()

            if event.type == pygame.KEYDOWN:
                if event.key == pygame.K_r:
                    music_channel.stop()
                    music_channel.play(sound.music_sound, -1)
                    game = Game(sound)
                    continue

                if game.game_over:
                    continue

                if event.key == pygame.K_LEFT:
                    if game.board.valid(game.current.shape, game.current.x - 1, game.current.y):
                        game.current.x -= 1
                        if game.sound:
                            game.sound.play("move")
                    game.das_dir = -1
                    game.das_timer = 0
                    game.das_charged = False

                elif event.key == pygame.K_RIGHT:
                    if game.board.valid(game.current.shape, game.current.x + 1, game.current.y):
                        game.current.x += 1
                        if game.sound:
                            game.sound.play("move")
                    game.das_dir = 1
                    game.das_timer = 0
                    game.das_charged = False

                elif event.key == pygame.K_DOWN:
                    if game.board.valid(game.current.shape, game.current.x, game.current.y + 1):
                        game.current.y += 1
                        game.score += 1

                elif event.key == pygame.K_UP:
                    game.try_rotate()

                elif event.key == pygame.K_SPACE:
                    game.hard_drop()

                elif event.key in (pygame.K_c, pygame.K_LSHIFT, pygame.K_RSHIFT):
                    game.hold()

            if event.type == pygame.KEYUP:
                if event.key in (pygame.K_LEFT, pygame.K_RIGHT):
                    game.das_dir = 0
                    game.das_timer = 0
                    game.das_charged = False

        if not game.game_over:
            keys = pygame.key.get_pressed()
            if game.das_dir != 0:
                game.das_timer += dt
                if not game.das_charged:
                    if game.das_timer >= game.das_delay:
                        game.das_charged = True
                        game.das_timer = 0
                else:
                    if game.das_timer >= game.das_repeat:
                        game.das_timer = 0
                        dx = game.das_dir
                        if game.board.valid(game.current.shape, game.current.x + dx, game.current.y):
                            game.current.x += dx
                            if game.sound:
                                game.sound.play("move")

            if keys[pygame.K_DOWN]:
                if game.board.valid(game.current.shape, game.current.x, game.current.y + 1):
                    game.current.y += 1

            game.update(dt)

        screen.fill(BG)
        draw_board(screen, game.board)

        if not game.game_over:
            gy = game.ghost_y()
            draw_shape(screen, game.current.shape, game.current.color, game.current.x * CELL, gy * CELL, CELL, GHOST_ALPHA)
            draw_shape(screen, game.current.shape, game.current.color, game.current.x * CELL, game.current.y * CELL, CELL)

        draw_sidebar(screen, game, font)

        if game.game_over:
            draw_game_over(screen, font, big_font)

        pygame.display.flip()


if __name__ == "__main__":
    main()

# 🤖 AGENTS.md

> Agent and developer guide for the **Python Tetris** project.

---

## 📌 Project Overview

This repository contains a modern, self-contained implementation of classic **Tetris** built with Python and Pygame (`pygame-ce`). The game includes standard competitive mechanics (7-bag piece generation, SRS wall kicks, ghost piece, hold queue, dynamic gravity scaling, high score persistence) and a real-time procedural 8-bit chiptune audio engine with zero external asset dependencies.

---

## 🛠️ Environment & Tooling

- **Language**: Python 3.10+ (tested and compatible with Python 3.12, 3.13, 3.14)
- **Primary Library**: `pygame-ce` (Pygame Community Edition)
- **Dependencies**: Managed via `requirements.txt`
- **Audio Interface**: Raw 16-bit signed PCM buffers generated procedurally via standard library `math`, `array`, and `struct`.

### Quick Setup

```bash
# Install dependencies
pip install -r requirements.txt

# Run the game
python main.py
```

### Headless Verification & Testing

Since this is a GUI application, agents can verify syntax and game state logic headlessly without opening an interactive window:

```bash
# 1. Syntax & Bytecode compilation
python -m py_compile main.py sound_engine.py

# 2. Headless engine simulation test
python -c "import os; os.environ['SDL_VIDEODRIVER'] = 'dummy'; import main, pygame; pygame.init(); pygame.font.init(); screen = pygame.display.set_mode((100, 100)); game = main.TetrisGame(main.SoundEngine()); game.move_horizontal(1); game.rotate_piece(); game.hard_drop(); renderer = main.TetrisRenderer(screen); renderer.draw_game(game); print('Headless test passed!')"
```

---

## 🏛️ Codebase Architecture

```text
tetris/
├── main.py            # Main application: entry point, game loop, logic, piece matrices, renderer
├── sound_engine.py    # Audio engine: real-time procedural 8-bit SFX & Korobeiniki theme generator
├── requirements.txt   # Python dependency specifications
├── highscore.json     # Local persistent high score storage (auto-generated)
├── README.md          # User-facing documentation & controls
└── AGENTS.md          # AI agent & developer guidelines (this document)
```

### Module Responsibilities

#### 1. [`main.py`](main.py)
- **`Piece`**: Represents active/preview tetrominoes. Encapsulates rotation matrices, grid positions, and bounding boxes.
- **`TetrisGame`**: State machine managing the 10x20 board grid, 7-bag randomizer, gravity timer, collision detection, wall kicks, line clearing animations, scoring, and hold slot.
- **`TetrisRenderer`**: Handles UI layout, dark slate retro aesthetics, beveled block drawing with lighting highlights/shadows, translucent ghost piece, sidebar HUD cards, and modal pause/game-over overlays.
- **`main()`**: Pygame event loop, keyboard dispatching (DAS key repeat), and frame timing (60 FPS).

#### 2. [`sound_engine.py`](sound_engine.py)
- **`SoundEngine`**: Manages Pygame mixer channels and procedural audio synthesis.
- **Audio Synthesizer**: Converts mathematical waveforms (square, pulse, triangle, saw) into 16-bit PCM stereo sample buffers fed to `pygame.mixer.Sound`.
- **Music Generator**: Plays a 2-channel polyphonic rendition of *Korobeiniki* (lead pulse melody + triangle bassline) looping on channel 0.
- **SFX**: Synthesizes 9 distinct sound effects (move, rotate, soft drop, hard drop punch, hold swap, line clear arpeggio, tetris clear fanfare, level up, game over).

---

## 🎮 Game Rules & Mechanics

### Tetromino Definition & Matrix
- Standard 7 pieces: `I`, `J`, `L`, `O`, `S`, `T`, `Z`.
- Grid size: 10 columns by 20 rows (`GRID_WIDTH = 10`, `GRID_HEIGHT = 20`).
- Rotations: Precomputed 4-state matrices defined in `PIECE_MATRICES`.

### 7-Bag Randomizer
- Pieces are generated in shuffled sets of all 7 tetrominoes, guaranteeing no droughts and at most 2 of the same piece in succession.

### Wall-Kick Offsets
- When a piece rotation collides with an edge or placed block, the engine tests kick offsets in order: `[(0, 0), (-1, 0), (1, 0), (-2, 0), (2, 0), (0, -1), (-1, -1), (1, -1)]`.

### Scoring & Gravity Formula
- **Single Line**: `100 × (level + 1)`
- **Double Line**: `300 × (level + 1)`
- **Triple Line**: `500 × (level + 1)`
- **Tetris (4 Lines)**: `800 × (level + 1)`
- **Soft Drop**: `+1 pt` per cell
- **Hard Drop**: `+2 pts` per cell
- **Level Calculation**: `level = lines_cleared // 10`
- **Drop Interval Formula**: `max(70, int((0.8 - (level * 0.007)) ** level * 1000))` (in ms)

---

## 🧑‍💻 Guidelines for Contributing Agents

1. **Zero External Assets**:
   - Do not add `.mp3`, `.wav`, `.png`, or `.ttf` files unless explicitly instructed.
   - All visual elements must be drawn dynamically using Pygame surfaces, geometries, and fonts.
   - All audio must remain procedural via `sound_engine.py`.

2. **Clean Separation of Concerns**:
   - Keep game logic in `TetrisGame` decoupled from rendering in `TetrisRenderer`.
   - `TetrisGame` should only communicate with `SoundEngine` by calling semantic methods like `.play_sfx('name')` or `.start_music()`.

3. **Graceful Degradation**:
   - Audio initialization must always be wrapped in a `try/except` block so the game continues to run smoothly on systems without an active audio device or driver.

4. **Keyboard & Event Handling**:
   - Key repetitions for lateral moves use `pygame.key.set_repeat(170, 45)`.
   - Always support both Arrow keys and standard WASD alternatives.

5. **Style & Types**:
   - Follow standard Python PEP 8 style conventions.
   - Use clear type hints for function arguments and return types.
   - Keep docstrings informative and concise.

# 🐍 Python Snake Game — Neon Gradient Edition

An enhanced, retro-arcade Snake game in Python featuring **dynamic color gradients**, **particle burst animations**, **pulsating food**, and **8-bit sound effects**.

**Zero installation required!** Runs completely out of the box on standard Python 3 with no third-party libraries needed.

---

## 🎨 Visual & Audio Enhancements

- 🌈 **Dynamic Color Gradients**: The snake body dynamically renders a smooth multi-stop color gradient from head to tail.
- 🎭 **Live Theme Switching**: Press `T` anytime to cycle through 4 distinct gradient palettes:
  - **Cyberpunk Neon** (Cyan ➔ Blue ➔ Purple ➔ Magenta ➔ Orange)
  - **Emerald Viper** (Neon Lime ➔ Emerald ➔ Sea Green ➔ Teal)
  - **Solar Flare** (Sun Gold ➔ Orange ➔ Coral ➔ Crimson)
  - **Cosmic Galaxy** (Lavender ➔ Violet ➔ Royal Blue ➔ Cyan)
- ✨ **Particle Burst Effects**: Scoring triggers an animated radial particle burst.
- 🔮 **Pulsating Energy Food**: Smooth sine-wave color oscillations on food items.
- 🔊 **Retro 8-Bit Sound Effects**:
  - 🍎 **Eat Food**: Crisp, pleasant dual-tone chime.
  - ⭐ **Milestone**: Celebratory 4-note ascending fanfare every 50 points.
  - 💥 **Game Over**: Classic descending defeat arpeggio.
  - ⏯️ **Pause / Theme**: Feedback beeps.
  - 🔇 **Mute / Unmute**: Press `M` to toggle sound on or off with live HUD indicator.
  - *(Sound runs on asynchronous background threads to guarantee zero animation lag)*

---

## 🚀 How to Run

### 1. Prerequisites
Ensure you have standard Python 3 installed. You can check by running:
```bash
python --version
```

### 2. Launch the Game

Open your terminal or command prompt in this directory and run:

```bash
python snake.py
```

> **Windows Shortcut**: You can simply double-click [`snake.py`](file:///D:/Playing/antigravity-intro/snake.py) in File Explorer to play!

---

## 🕹️ Controls

| Key | Action |
| :--- | :--- |
| **`↑` / `W`** | Move Up |
| **`↓` / `S`** | Move Down |
| **`←` / `A`** | Move Left |
| **`→` / `D`** | Move Right |
| **`T`** | Cycle Gradient Theme |
| **`M`** | Toggle Sound (Mute / Unmute) |
| **`Space`** | Pause / Resume *(or Restart on Game Over)* |
| **`P`** | Pause / Resume |
| **`R`** | Restart Game |

---

## 📜 Game Rules

1. Guide your glowing snake towards the pulsating food orb.
2. Each apple collected awards **+10 points**, triggers a particle burst, and extends your gradient body.
3. Every **50 points**, enjoy a celebratory milestone chime!
4. Avoid colliding with the neon boundary walls or your own tail.
5. Try to beat your session High Score!

---

## 🛠️ Code Structure

- [`snake.py`](file:///D:/Playing/antigravity-intro/snake.py):
  - **Sound System**: Safe, non-blocking asynchronous audio using Python's standard `winsound`.
  - **Gradient Engine**: Multi-stop linear RGB interpolation (`lerp_color` & `sample_gradient`).
  - **Particle Pool**: Lightweight, pre-allocated particle system for collision bursts.
  - **Game Loop**: Smooth buffered rendering with `screen.tracer(0)` and `screen.update()`.

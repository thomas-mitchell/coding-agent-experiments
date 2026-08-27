# 🕹️ Classic Tetris in Python

A modern, polished, and fully featured implementation of classic **Tetris** built with Python and Pygame, featuring **real-time procedural 8-bit chiptune sound effects and background music**.

![Python](https://img.shields.io/badge/Python-3.10%2B-3776AB?style=for-the-badge&logo=python&logoColor=white)
![Pygame](https://img.shields.io/badge/Pygame--ce-2.5%2B-yellow?style=for-the-badge&logo=python&logoColor=white)
![Audio](https://img.shields.io/badge/Audio-Procedural%208--Bit-brightgreen?style=for-the-badge)
![License](https://img.shields.io/badge/License-MIT-blue?style=for-the-badge)

---

## ✨ Features

- 🎵 **Procedural Chiptune Audio**: Authentic 8-bit synthesized polyphonic *Korobeiniki* (Tetris Theme A) background music with zero external audio files required.
- 🔊 **Rich Sound Effects**: Procedurally generated arcade SFX for lateral movement, piece rotation, hard drop punch, soft drop, hold swapping, line clears, 4-line Tetris victory fanfares, level-up jingles, and game-over descending slides.
- 🎨 **Modern Retro-Arcade Aesthetics**: Deep slate palette, beveled tetrominoes with specular lighting & edge shadows.
- 🎯 **Ghost Piece Projection**: Real-time translucent drop projection showing where your piece will land.
- 🔄 **Hold Piece System**: Swap and hold pieces on the fly with `C` or `Shift`.
- 🎲 **7-Bag Randomizer**: Modern standard piece generation to prevent droughts and unfair repeats.
- 📐 **Wall Kicks & Smooth Rotations**: Intuitive rotation mechanics that adapt near walls and placed blocks.
- 📈 **Level Progression & Dynamic Speed**: Falling speed dynamically accelerates every 10 lines cleared.
- 🏆 **High Score Tracking**: Automatically saves and loads your best score to `highscore.json`.
- ⚡ **Responsive DAS (Delayed Auto Shift)**: Smooth lateral piece movement when holding arrow keys.
- 🔇 **Mute / Audio Toggle**: Easily toggle sound and music on/off anytime with `M`.
- ⏸️ **Pause & Restart Support**: Easily pause (`P`/`ESC`) or restart (`R`) at any time.

---

## 🎮 Controls

| Action | Primary Key | Secondary Key |
| :--- | :--- | :--- |
| **Move Left** | `◄ Left Arrow` | `A` |
| **Move Right** | `► Right Arrow` | `D` |
| **Rotate Clockwise** | `▲ Up Arrow` | `W` or `X` |
| **Rotate Counter-Clockwise** | `Z` | — |
| **Soft Drop** | `▼ Down Arrow` | `S` |
| **Hard Drop** | `Spacebar` | — |
| **Hold Piece** | `C` | `Left Shift` / `Right Shift` |
| **Toggle Sound / Music** | `M` | — |
| **Pause / Resume** | `P` | `Escape` |
| **Restart Game** | `R` | — |
| **Quit Game** | `Q` (on Game Over) | Window Close Button |

---

## 🚀 Quick Start

### 1. Prerequisites
- Python 3.10 or higher installed on your system.

### 2. Installation
Clone or navigate to the project directory:

```bash
cd tetris
```

Install the required dependencies:

```bash
pip install -r requirements.txt
```

*(Note: `pygame-ce` is used as it provides full support for the latest Python versions, including Python 3.12, 3.13, and 3.14)*.

### 3. Run the Game

```bash
python main.py
```

---

## 🎼 Audio Engine Highlights

The audio engine ([`sound_engine.py`](sound_engine.py)) uses procedural synthesis with Pygame's raw 16-bit PCM buffer interface:
- **Polyphonic Theme**: Synthesizes the melody pulse channel and bassline triangle channel in real-time.
- **Dynamic SFX**: Synthesizes pitch sweeps, arpeggios, and filtered noise pulses for tactile gameplay feedback.
- **Zero Assets**: No MP3/WAV files to download, locate, or miss—100% self-contained in pure Python.

---

## 📊 Scoring & Progression

### Line Clears
Points scale directly with the current **Level**:

| Lines Cleared | Base Points | Level 0 | Level 1 | Level 5 |
| :--- | :--- | :--- | :--- | :--- |
| **1 Line (Single)** | 100 × (Level + 1) | 100 | 200 | 600 |
| **2 Lines (Double)** | 300 × (Level + 1) | 300 | 600 | 1,800 |
| **3 Lines (Triple)** | 500 × (Level + 1) | 500 | 1,000 | 3,000 |
| **4 Lines (Tetris!)** | 800 × (Level + 1) | 800 | 1,600 | 4,800 |

### Drop Bonuses
- **Soft Drop**: `+1 point` for each cell dropped.
- **Hard Drop**: `+2 points` for each cell dropped.

### Levels
- Cleared lines count towards leveling up (`Level = Lines Cleared // 10`).
- Each level shortens the piece drop interval, increasing gravity and difficulty.

---

## 📂 Project Structure

```text
tetris/
├── main.py            # Complete game engine, piece definitions, renderer, and event loop
├── sound_engine.py    # Procedural 8-bit sound synthesizer & Korobeiniki music engine
├── requirements.txt   # Python dependencies (pygame-ce)
├── highscore.json     # Saved high score file (generated on game over)
└── README.md          # Project documentation and guide
```

---

## 🛠️ Customization

You can easily customize various constants inside [`main.py`](main.py) and [`sound_engine.py`](sound_engine.py):

- **Grid Dimensions**: Modify `GRID_WIDTH` and `GRID_HEIGHT` (default: 10x20).
- **Block Size**: Modify `CELL_SIZE` (default: 32px) to scale window dimensions.
- **Colors**: Adjust `SHAPE_COLORS` or `COLOR_BG` to create your own visual themes.
- **Music Tempo**: Adjust `bpm` in `sound_engine.py` to speed up or slow down the theme music.

---

## 📜 License

This project is open-source and available under the [MIT License](https://opensource.org/licenses/MIT).

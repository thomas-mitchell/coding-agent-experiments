# Building Roguelikes in Python with tcod

A comprehensive, intermediate-to-advanced guide to building a complete, playable
roguelike game from scratch using Python and the [tcod](https://github.com/libtcod/python-tcod)
library. This book takes you from an empty project folder all the way to a
polished, packaged, moddable game with procedural dungeons, tactical combat,
spellcasting, a data-driven modding system, and a full release build.

The book is built around a real, working game that grows one chapter at a time.
Each chapter introduces a focused concept and immediately applies it to the
project, so by the end you have not just knowledge but a finished, extensible
codebase. The architecture uses a proper Entity-Component-System (ECS) design
via [tcod-ecs](https://github.com/libtcod/python-tcod-ecs), which keeps systems
decoupled, makes the code testable, and lays the groundwork for modding and
performance work later in the book.

This book is for developers who are comfortable with Python's basics and want to
level up their software architecture skills while building something fun. You do
not need any prior game development experience, but you should be at ease with
classes, modules, and basic command-line work. If you have ever wanted to
understand how classic roguelikes like NetHack or Dungeon Crawl Stone Soup are
structured under the hood, this is the book for you.

## Table of Contents

### Part I: Foundations
- Chapter 0: Introduction to Roguelikes
- Chapter 1: The Roguelike Genre and Design Principles
- Chapter 2: Entity-Component-System Architecture
- Chapter 3: Project Setup and Tooling
- Chapter 4: tcod Basics — Console, Input, and Rendering
- Chapter 5: Game State and the Main Loop
- Chapter 6: Defining Components and the ECS World

### Part II: Core Systems
- Chapter 7: Movement and Input Handling
- Chapter 8: The Game Map and Tile Model
- Chapter 9: Procedural Dungeon Generation
- Chapter 10: Field of View and Exploration
- Chapter 11: Entity Factories and Spawning
- Chapter 12: The Turn-Based Game Loop
- Chapter 13: Combat Systems
- Chapter 14: Monster AI and Behavior

### Part III: Game Features
- Chapter 15: Items and Inventory
- Chapter 16: Equipment and Stats
- Chapter 17: The Message Log
- Chapter 18: User Interface and Panels
- Chapter 19: Targeting and Spellcasting
- Chapter 20: Dungeon Levels and Descending
- Chapter 21: Experience, Leveling, and Skills
- Chapter 22: Procedural Quests
- Chapter 23: Save and Load

### Part IV: Advanced Topics
- Chapter 24: Animations and Visual Effects
- Chapter 25: Sound and Audio
- Chapter 26: Modding with Data Files
- Chapter 27: Performance Optimization
- Chapter 28: Packaging and Distribution

### Appendix
- Appendix A: Algorithm Deep Dives

## Prerequisites

- **Python 3.12 or newer** installed and working from the command line.
- **Basic object-oriented programming knowledge**: classes, methods,
  inheritance, and modules. You should be comfortable reading and writing
  Python code without hand-holding.
- **Familiarity with the command line** (creating directories, running scripts,
  using a text editor or IDE of your choice).
- No prior game development or graphics experience is required.
- A curiosity about how games are architected and a willingness to read and
  modify real code.

## How to Use This Book

The chapters are designed to be read in order. Each one builds cumulatively on
the previous, and the codebase grows chapter by chapter. To follow along:

1. Clone or download this repository.
2. Create and activate a virtual environment (see the project structure below).
3. Install the dependencies listed in `requirements.txt`.
4. Read the chapter, then open the matching source snapshot in
   `src/chapters/chNN/` to see the full, runnable code as it stood at the end
   of that chapter.
5. Run the game from a chapter snapshot to experiment with the feature you just
   learned.

The `src/` directory contains the continuously evolving project, while
`src/chapters/chNN/` contains frozen snapshots so you can always compare your
work against a known-good reference. If you get stuck, diff your code against
the relevant chapter snapshot.

## Tech Stack

| Technology | Version | Purpose |
|------------|---------|---------|
| Python     | 3.12+   | Primary language |
| tcod       | 21.x    | Terminal rendering, input, FOV, RNG |
| tcod-ecs   | latest  | Entity-Component-System framework |
| numpy      | latest  | Efficient grid and array math for maps |
| attrs      | latest  | Concise, declarative component classes |

## Project Structure

```
bigpickle-python-roguelike-book/
├── README.md
├── requirements.txt
├── chapters/                 # Book manuscript, one file per chapter
│   ├── ch00-introduction.md
│   ├── ch01-genre.md
│   └── ...
└── src/
    ├── game/                 # The continuously evolving project
    │   ├── main.py
    │   ├── components/
    │   ├── systems/
    │   └── ...
    └── chapters/
        ├── ch00/             # Frozen source snapshot for Chapter 0
        ├── ch01/             # Frozen source snapshot for Chapter 1
        └── ...
        └── ch28/             # Frozen source snapshot for Chapter 28
```

Each `src/chapters/chNN/` directory is a self-contained, runnable copy of the
project as it exists at the end of that chapter, so you can run any chapter's
code independently.

## License

- **Book content** (everything in `chapters/`, plus this README) is licensed
  under **Creative Commons Attribution 4.0 International (CC BY 4.0)**. You are
  free to share and adapt the text as long as you provide appropriate credit.
- **Source code** (everything in `src/`) is licensed under the **MIT License**.
  You are free to use, modify, and distribute the code for any purpose,
  including commercial projects.

See the `LICENSE` and `LICENSE-CODE` files for the full license texts.

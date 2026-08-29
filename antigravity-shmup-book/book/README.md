# Architecting the 2D Shmup
### *Systems, Choreography, and Engine Design for High-Performance Scrolling Shooters*

Welcome to **Architecting the 2D Shmup**. This book is an advanced, engineering-centric guide to building high-performance, commercial-grade 2D Shoot 'Em Up (Shmup) games and custom engines.

---

## 🎯 Target Audience & Philosophy

This text assumes you are a **competent software engineer** familiar with data structures, algorithms, linear algebra, and systems programming concepts. We will not waste your time explaining what a vector is, how a `for` loop works, or how to install a compiler.

Instead, we focus on the **hard systems-engineering challenges** unique to scrolling shooters:
- Sustaining tens of thousands of active projectiles and entities at a rock-solid 60/120+ FPS with zero runtime allocations.
- Designing deterministic fixed-timestep game loops and state snapshotting architectures.
- Crafting smooth parametric spline path-following systems stabilized via numerical arc-length integration.
- Formulating complex danmaku (bullet curtain) mathematics and reactive emitter domain-specific languages (DSLs).
- Structuring time-indexed level timelines, event queues, and deterministic replay systems.
- Designing multi-phase, hierarchical, destructible boss encounters using Hierarchical State Machines (HSMs) and dynamic difficulty (Rank) systems.
- Architecting an in-engine Level & Wave Editor featuring interactive spline control points, timeline scrubbers, and live hot-reloading.
- Engineering low-latency game feel ("juice"), screen trauma systems, and audio voice-coalescing mixers.

```
                    ┌─────────────────────────────────────────────────────────┐
                    │                   MASTER ENGINE LOOP                    │
                    │   Fixed-Timestep Accumulator (1/60s or 1/120s Ticks)    │
                    └────────────────────────────┬────────────────────────────┘
                                                 │
         ┌───────────────────────────────────────┼──────────────────────────────────────┐
         ▼                                       ▼                                      ▼
┌──────────────────┐                   ┌──────────────────┐                   ┌──────────────────┐
│  SPATIAL BROAD   │                   │    DANMAKU &     │                   │  TIMELINE & WAVE │
│  PARTITIONING    │                   │ SPLINE KINEMATICS│                   │   CHOREOGRAPHY   │
│ Multi-Grid / BVH │                   │ Arc-Length LUTs  │                   │ Event Queues     │
└────────┬─────────┘                   └────────┬─────────┘                   └────────┬─────────┘
         │                                      │                                      │
         └──────────────────────────────────────┼──────────────────────────────────────┘
                                                 │
                                                 ▼
                                ┌──────────────────────────────────┐
                                │     HIGH-VELOCITY COLLISION      │
                                │   Narrow SAT / Graze / CCD       │
                                └────────────────┬─────────────────┘
                                                 │
                                                 ▼
                                ┌──────────────────────────────────┐
                                │     BATCHED GPU RENDER PIPELINE  │
                                │  Instanced Sprites / FX Shaders  │
                                └──────────────────────────────────┘
```

---

## 💡 Pseudocode & Code Policy

To remain universally applicable across modern systems languages (such as C++, Rust, C#, Zig, or custom engine environments), code throughout this book is presented in **typed, idiomatic algorithmic pseudocode**. 

We explicitly **do not provide a monolithic, copy-pasteable codebase**. Turning these mathematical models, cache-conscious data layouts, and state machine architectures into a functioning game engine is the reader's implementation journey.

---

## 📚 Table of Contents

| Chapter | Title | Primary Focus |
| :--- | :--- | :--- |
| **[Chapter 1](file:///D:/Playing/coding-agent-experiments/antigravity-shmup-book/book/ch01_anatomy_of_a_shmup.md)** | **The Anatomy of a Modern 2D Shmup** | Genre taxonomy, gameplay pillars, frame budgets, latency mitigation. |
| **[Chapter 2](file:///D:/Playing/coding-agent-experiments/antigravity-shmup-book/book/ch02_engine_architecture_and_core_loop.md)** | **Engine Architecture & Core Simulation Loop** | Fixed timestep accumulators, ECS vs. DOD, zero-alloc object pools, generational handles. |
| **[Chapter 3](file:///D:/Playing/coding-agent-experiments/antigravity-shmup-book/book/ch03_spatial_partitioning_and_collision.md)** | **High-Performance Collision & Spatial Partitioning** | Spatial hash grids, dynamic BVH, SAT narrow phase, graze mechanics, Continuous Collision Detection (CCD). |
| **[Chapter 4](file:///D:/Playing/coding-agent-experiments/antigravity-shmup-book/book/ch04_bullet_choreography_and_danmaku_math.md)** | **Bullet Choreography & Danmaku Mathematics** | Polar transformations, spiral/curtain trigonometry, parametric trajectories, emitter DSLs. |
| **[Chapter 5](file:///D:/Playing/coding-agent-experiments/antigravity-shmup-book/book/ch05_path_following_and_formation_flight.md)** | **Enemy Path Following, Kinematics & Formation Flight** | Bézier and Catmull-Rom splines, arc-length LUT parameterization, Reynolds steering, formation anchoring. |
| **[Chapter 6](file:///D:/Playing/coding-agent-experiments/antigravity-shmup-book/book/ch06_level_representation_and_scripting.md)** | **Level Representation, Timeline Sequencing & Scripting** | Time-indexed streams vs spatial scrolling, declarative schemas, coroutines, deterministic replays. |
| **[Chapter 7](file:///D:/Playing/coding-agent-experiments/antigravity-shmup-book/book/ch07_boss_architecture_and_choreography.md)** | **Boss Architecture & Choreography** | Hierarchical State Machines, multi-part scene graphs, attack telegraphing, Battle Rank calculus. |
| **[Chapter 8](file:///D:/Playing/coding-agent-experiments/antigravity-shmup-book/book/ch08_level_editor_architecture_and_tooling.md)** | **Level Editor Architecture & Tooling** | In-engine tooling, timeline scrubbers, interactive spline handles, command pattern undo/redo, hot reloading. |
| **[Chapter 9](file:///D:/Playing/coding-agent-experiments/antigravity-shmup-book/book/ch09_vfx_audio_and_game_feel.md)** | **Visual FX, Audio, and "Game Feel" (Juice)** | GPU sprite batching, screen-space distortion shaders, trauma-decay screen shake, voice coalescing. |
| **[Chapter 10](file:///D:/Playing/coding-agent-experiments/antigravity-shmup-book/book/ch10_synthesis_and_implementation_exercises.md)** | **Synthesis & Implementation Exercises** | Complete engine blueprint, 5-phase milestone roadmap, capstone challenges, and bibliography. |

---

## 🛠 Prerequisites

To extract maximum value from this material, you should be comfortable with:
1. **Linear Algebra & Vector Calculus**: Dot products, cross/perp products, matrix transformations, polar coordinates, parametric curves, numerical integration.
2. **Systems Programming & Memory Topologies**: Cache lines (L1/L2/L3), CPU prefetchers, contiguous arrays vs linked structures, memory fragmentation, structure-of-arrays (SoA) layouts.
3. **State Machine Formulations**: Finite State Machines (FSM), Hierarchical State Machines (HSM), and Behavior Trees.

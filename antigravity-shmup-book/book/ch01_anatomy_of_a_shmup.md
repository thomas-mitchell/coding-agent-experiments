# Chapter 1: The Anatomy of a Modern 2D Shmup

The Shoot 'Em Up (colloquially **shmup**, or STG in Japan for *Shooting Game*) is one of video game history's purest algorithmic genres. Stripped of complex narrative branches, physical ragdoll simulation, and dynamic 3D lighting pipelines, the shmup operates as an ultra-high-velocity, deterministic choreography of thousands of active mathematical entities. 

To the casual observer, a shmup is simply moving a ship and firing lasers. To the systems engineer, a shmup is a **real-time spatial simulation engine** with strict sub-millisecond per-frame budgets, zero-allocation memory constraints, high-density collision culling, and microsecond-level input responsiveness.

---

## 1.1 Taxonomy and Lineage of Scrolling Shooters

Understanding the technical design requirements begins with classifying the mechanical sub-genres. The engineering requirements differ significantly depending on the archetype.

```
                                  ┌─────────────────────────────┐
                                  │      2D SHMUP TAXONOMY      │
                                  └──────────────┬──────────────┘
                                                 │
         ┌───────────────────────────────────────┼───────────────────────────────────────┐
         ▼                                       ▼                                       ▼
┌──────────────────┐                   ┌──────────────────┐                    ┌──────────────────┐
│ CLASSIC ARCADE   │                   │  DANMAKU (HELL)  │                    │   EUROSHMUP      │
│ (Toaplan/Raiden) │                   │ (Cave / Touhou)  │                    │ (Tyrian/Xenon 2) │
├──────────────────┤                   ├──────────────────┤                    ├──────────────────┤
│ • Fast, sparse   │                   │ • Dense, slow    │                    │ • Shield bars    │
│   projectiles    │                   │   curtains       │                    │ • Inertial drift │
│ • Large hitboxes │                   │ • Microscopic    │                    │ • Shop/Upgrades  │
│ • Spatial memo-  │                   │   core hitbox    │                    │ • Large hitboxes │
│   rization       │                   │ • Grazing system │                    │ • Health sponge  │
└──────────────────┘                   └──────────────────┘                    └──────────────────┘
```

### 1. Danmaku / Bullet Hell (Cave, Touhou, Takumi)
- **Visual & Spatial Characteristics**: The screen is saturated with thousands of slow to medium-velocity projectiles forming geometric tapestries (spirals, rings, roses, rosettes).
- **Core Player Paradigm**: The player sprite might be $64 \times 64$ pixels, but the lethal hitbox is an infinitesimal dot ($2 \times 2$ to $4 \times 4$ pixels) centered at the core.
- **Architectural Implications**: Extreme projectile count ($10,000\text{--}50,000$ active entities), demanding $O(1)$ allocation pools, efficient SIMD transform evaluations, and optimized spatial broad-phase culling.

### 2. Classic Arcade / Toaplan-Style (Raiden, Truxton, Batsugun)
- **Visual & Spatial Characteristics**: Lower projectile counts ($50\text{--}300$ active bullets), but bullets travel at extreme velocities, often traversing half the screen in a few frames.
- **Core Player Paradigm**: Player hitbox closely mirrors the physical sprite hull ($20 \times 30$ pixels). Precision positioning and macro-routing dominate over micro-dodging.
- **Architectural Implications**: Demands Continuous Collision Detection (CCD) or swept-volume raycasts to prevent high-velocity projectiles from tunneling through the player ship between discrete simulation ticks.

### 3. Euroshmup (Tyrian, Project-X, Xenon 2)
- **Visual & Spatial Characteristics**: Heavy momentum/inertia on player movement, health bars/shields rather than single-hit-kill mechanics, persistent currency/shop upgrades.
- **Architectural Implications**: Requires continuous kinematic physics integration (drag, mass, acceleration curves) rather than instantaneous discrete arcade velocity vectors.

### 4. Gimmick / Polarity Shooters (Ikaruga, Radiant Silvergun)
- **Visual & Spatial Characteristics**: State-switching mechanics (e.g., Black/White polarity where opposing color bullets kill, but matching color bullets are absorbed to charge a super-weapon).
- **Architectural Implications**: Dual-layer collision pipelines and instantaneous entity state transforms, requiring bitmask-based collision filtering.

---

## 1.2 Fundamental Mechanics and Micro-Rules

A high-performance shmup engine is constructed around precise, non-negotiable micro-mechanics.

```
               ┌─────────────────────────────────────────────────┐
               │              PLAYER SHIP SCHEMATIC              │
               │                                                 │
               │                   ▲ (Nose)                      │
               │                  / \                            │
               │                 /   \                           │
               │                / ░░░ \     <--- Visual Sprite   │
               │               / ░░░░░ \         (64x64 px)      │
               │              / ░░( )░░ \                        │
               │             / ░░( ● )░░ \  <--- Core Hitbox     │
               │            / ░░░░( )░░░░ \      (3x3 px)        │
               │           /═══════════════\                     │
               │          /                 \ <--- Graze Hull    │
               │         ▀▀▀               ▀▀▀    (32x32 px)     │
               └─────────────────────────────────────────────────┘
```

### Hitbox vs. Hurtbox vs. Graze-Box Disparity
In modern shmups, an entity possesses multiple concentric geometric collision boundaries:

$$\text{Hitbox}_{\text{Core}} \subset \text{Hitbox}_{\text{Graze}} \subset \text{Sprite}_{\text{Visual}}$$

1. **Lethal Hitbox**: A tiny geometric circle or Axis-Aligned Bounding Box (AABB) centered on the player's pilot cockpit. Touching an enemy projectile's lethal radius triggers life loss or bomb auto-trigger.
2. **Graze-Box (Scratch Aura)**: A larger concentric hull. When an enemy bullet intersects the graze-box *without* intersecting the lethal hitbox:
   - A graze event is dispatched.
   - The bullet is tagged as `grazed = true` (or assigned a cooldown timer) to prevent awarding millions of points per second from a single stationary bullet.
   - Global multiplier counters increment, building hyper-meter gauge.
3. **Enemy Hurtbox**: Large polygon or composite multi-hull structure mapping to the physical hull of enemy ships, destructible turrets, and weak-points.

### Battle Rank (Dynamic Difficulty Adjustment)
Top-tier shmups (such as *Battle Garegga*, *Armed Police Batrider*, and *Crimson Clover*) implement an internal **Rank Variable** ($R \in [0.0, 1.0]$ or an integer accumulator $R \in [0, 2^{32}-1]$).

$$R_{t+1} = \text{clamp}\left( R_t + \sum \Delta R_{\text{actions}} - \sum \Delta R_{\text{penalties}}, \; R_{\min}, \; R_{\max} \right)$$

- **Rank Increases when**: The player stays alive per second, picks up power-up items, upgrades shot power, or collects point medals.
- **Rank Decreases when**: The player expends a bomb or loses a life.
- **Rank Directly Modulates Engine Systems**:
  - Emitter firing rates ($f_{\text{fire}} = f_{\text{base}} \times (1.0 + \alpha R)$).
  - Projectile velocities ($v = v_{\text{base}} \times (1.0 + \beta R)$).
  - Bullet density (number of ways in a radial spread $N = N_{\text{base}} + \lfloor \gamma R \rfloor$).
  - Enemy health pools ($HP = HP_{\text{base}} \times (1.0 + \delta R)$).

---

## 1.3 Technical Constraints and Real-Time Budgets

A commercial shmup engine operates under tighter deterministic timing constraints than almost any other genre.

```
                          16.66 ms Total Budget (60 FPS)
  ┌────────────┬───────────┬───────────┬───────────┬───────────────────────────┐
  │ Input/Sim  │ Spatial   │ Collision │ VFX/Audio │ Render Submission         │
  │ ~1.5 ms    │ ~2.0 ms   │ ~2.5 ms   │ ~1.5 ms   │ ~4.0 ms                   │
  └────────────┴───────────┴───────────┴───────────┴───────────────────────────┘
  [══════════════════════ 11.5 ms Simulation ═══════════════════════][~5ms Headroom]
```

### The 60 / 120 / 240 Hz Frame Budgets

| Target Refresh Rate | Total Frame Budget | Max Simulation Budget | Max Render Budget | Target Entity Capacity |
| :--- | :--- | :--- | :--- | :--- |
| **60 FPS** | $16.66\text{ ms}$ | $10.0\text{ ms}$ | $4.5\text{ ms}$ | 50,000 projectiles |
| **120 FPS** | $8.33\text{ ms}$ | $5.0\text{ ms}$ | $2.5\text{ ms}$ | 30,000 projectiles |
| **240 FPS** | $4.16\text{ ms}$ | $2.5\text{ ms}$ | $1.2\text{ ms}$ | 15,000 projectiles |

### The Zero-Allocation Mandate
During gameplay:
- **Zero dynamic heap allocations** (`malloc`, `new`, vector resizing, string concatenations) may occur within the simulation tick.
- Managed runtimes (C#, Java) must produce **zero garbage collection pressure**; any GC collection pause ($>2\text{ ms}$) will cause a dropped frame, instantly resulting in an unfair player death.
- All entity pools, bullet buffers, particle arrays, spatial hash grids, and audio event queues must be **pre-allocated at level load** into contiguous flat buffers.

---

## 1.4 Input Latency and Controller Polling Dynamics

In a bullet hell shooter, a player must navigate gaps measuring fractions of a millimeter between bullets traveling at hundreds of pixels per second. A delay of 2 frames ($33.3\text{ ms}$) renders high-level micro-dodging impossible.

```
POOR ARCHITECTURE: 3-Frame Input Lag
Frame 0: OS Poll ──────> Frame 1: Simulation ──────> Frame 2: Render ──────> Frame 3: Display

OPTIMAL ENGINE ARCHITECTURE: Sub-Frame / 1-Frame Latency Pipeline
Frame 0 [Poll Input ──> Fixed Sim ──> Render Submission] ──> Frame 1 [Display V-Sync Flip]
```

### Key Latency Reduction Principles
1. **Poll Directly Before Simulation**: Query hardware raw input (DirectInput, XInput, evdev, SDL GameController) immediately before executing the fixed simulation tick, rather than caching it in an OS event queue.
2. **Double Buffering vs. Triple Buffering**: Triple buffering introduces an extra frame of latency ($+16.6\text{ ms}$). Engines targeting competitive play utilize strict V-Sync synchronization with speculative wait loops (`WaitableSwapchain` in DX12/Vulkan) or Variable Refresh Rate (G-Sync/FreeSync) presentation.
3. **Sub-Frame Input Timestamps**: For high-end arcade replay fidelity, capture hardware input with high-resolution microsecond timestamps ($\mu\text{s}$). If an input arrives halfway through a frame, apply sub-tick fractional movement or queue it precisely for the next simulation tick.

---

## 1.5 Summary Checklist for Engine Architects

Before writing a single line of rendering code, ensure your architecture answers these five questions:
1. **Memory**: Is every simulation entity pre-allocated in contiguous arrays with zero runtime allocations?
2. **Determinism**: Can the simulation run headlessly without a GPU at 10,000 ticks/sec and produce bit-identical replays?
3. **Collision**: Can the broad-phase structure cull 20,000 bullets against 500 enemy hurtboxes in $<2.5\text{ ms}$?
4. **Kinematics**: Does the path-following engine support constant-velocity spline traversal via arc-length parameterization?
5. **Tooling**: Can a level designer scrub the game timeline back and forth like a video editor while tweaking bullet emitters?

In **[Chapter 2](file:///D:/Playing/coding-agent-experiments/antigravity-shmup-book/book/ch02_engine_architecture_and_core_loop.md)**, we construct the foundation: the deterministic fixed-timestep game loop, Data-Oriented ECS architecture, and zero-allocation object pools.

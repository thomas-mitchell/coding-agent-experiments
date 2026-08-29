# Chapter 6: Level Representation, Timeline Sequencing & Scripting

In platformers and RPGs, levels are defined spatially: tiles, collision polygons, and triggers placed across a 2D grid. In a classic 2D scrolling shooter, spatial position is secondary. A shmup level is fundamentally a **musical score of choreographed time events**.

This chapter explores how to represent, sequence, script, and replay entire stages with sub-frame precision.

---

## 6.1 Spatial vs. Timeline-Driven Level Models

Early 1980s shooters tied enemy spawns directly to camera scroll distance:

$$\text{Spawn Condition}: Y_{\text{camera}} \ge Y_{\text{trigger}} \quad \text{[SPATIAL MODEL]}$$

```
                SPATIAL MODEL (Flawed for Modern Shmups)
           ┌─────────────────────────────────────────────────┐
           │ Tilemap Y=4000: Boss Spawn Trigger              │
           │                                                 │
           │ Tilemap Y=2500: Mid-Boss (Camera must stop)     │
           │                 [Camera frozen, but time ticks] │
           │ Tilemap Y=1000: Wave 1 Spawn                    │
           └─────────────────────────────────────────────────┘
```

### Why Pure Spatial Scrolling Breaks Down
1. **Camera Pauses (Mid-Boss Encounters)**: When the camera halts for a 45-second boss battle, distance stops advancing ($\Delta Y = 0$), yet internal attack patterns, adds, and timers continue running.
2. **Variable Camera Speeds & Acceleration**: Modern shmups frequently modulate scroll velocity (e.g., hyper-speed hyperspace dashes, zero-G drift sections, or reverse scrolling).
3. **Pacing Gating (Clear-to-Advance)**: High-tempo arcade games hold the camera until all enemies in a wave are eliminated, rewarding skilled speed-runners with faster level progression.

### The Modern Master Timeline Model
A modern shmup stage is modeled as a **Time-Indexed Event Stream** driven by a master level clock $t_{\text{stage}}$:

```
                            MASTER LEVEL TIMELINE
  t=0.0s          t=5.2s         t=12.0s        t=25.0s               t=45.0s
 ───┼───────────────┼──────────────┼──────────────┼─────────────────────┼───► Time
    │               │              │              │                     │
 [Music Start]  [Wave 1: Pop]  [Wave 2: V]   [Camera Accel]       [Mid-Boss Barrier]
 (BGM Track)    (Spline A)     (Spline B)    (Scroll -> 350px/s)  (Yield until dead)
```

---

## 6.2 Multi-Track Timeline Sequencing Data Structures

To organize complex stage choreographies without creating monolithic script files, we decompose the level into **Parallel Timeline Tracks**.

```
┌────────────────────────────────────────────────────────────────────────┐
│ TRACK 0: ENEMY SPAWNS    ──[W1: 4 Drone]────[W2: 2 Heavy]────[W3: Swarm]│
│ TRACK 1: CAMERA VELOCITY ──[200 px/s]───────[400 px/s]───────[PAUSE: 0]│
│ TRACK 2: ENVIRONMENT/FX  ──[Cloud Layer]────[Asteroid Storm]─[Warning!]│
│ TRACK 3: SCRIPT TRIGGERS ───────────────────[Save Point 1]───[Gate: W2]│
└────────────────────────────────────────────────────────────────────────┘
```

### The Min-Heap / Priority Queue Timeline Dispatcher
Because events are scheduled chronologically, we store un-triggered timeline events in a **Min-Heap sorted by trigger timestamp**. At every simulation tick, we peek at the top of the heap; if `event.timestamp <= current_time`, we pop and execute it in $O(1)$ amortized time.

```rust
// Priority Queue Stage Event Dispatcher
enum StageEventPayload {
    SpawnSquadron { squadron_def_id: u32, spline_id: u32, speed: f32 },
    SetScrollSpeed { new_speed: f32, transition_time: f32 },
    PlayDialogue { voice_id: u32, portrait_id: u32, duration: f32 },
    LockCameraAtBarrier { barrier_id: u32 },
    TriggerBossPhase { boss_id: u32, phase_index: u8 },
}

struct StageEvent {
    timestamp: f64,          // Exact trigger time in seconds
    payload: StageEventPayload,
}

struct StageTimeline {
    current_time: f64,
    event_queue: BinaryMinHeap<StageEvent>, // Sorted ascending by timestamp
    active_gates: Array<GateCondition, 8>,
}

impl StageTimeline {
    fn tick(&mut self, dt: f64, engine: &mut Engine) {
        // If a barrier gate is blocking time progression, check its condition
        if self.is_gated(engine) {
            return;
        }

        self.current_time += dt;

        // Drain all events whose timestamp has passed
        while let Some(event) = self.event_queue.peek() {
            if event.timestamp <= self.current_time {
                let ready_event = self.event_queue.pop().unwrap();
                self.dispatch_event(ready_event, engine);
            } else {
                break; // Earliest upcoming event is in the future
            }
        }
    }

    fn dispatch_event(&mut self, event: StageEvent, engine: &mut Engine) {
        match event.payload {
            StageEventPayload::SpawnSquadron { squadron_def_id, spline_id, speed } => {
                engine.spawn_squadron(squadron_def_id, spline_id, speed);
            }
            StageEventPayload::SetScrollSpeed { new_speed, transition_time } => {
                engine.camera_system.set_target_speed(new_speed, transition_time);
            }
            StageEventPayload::LockCameraAtBarrier { barrier_id } => {
                self.active_gates.push(GateCondition::WaitForBarrierDestruction(barrier_id));
            }
            // ... remaining payload handlers
        }
    }
}
```

---

## 6.3 Scripting Engines & Coroutine Level Orchestration

Declarative timelines (JSON/YAML) are fantastic for static wave spawns, but dynamic level pacing (e.g., *"wait until all 4 escort cruisers are dead, then spawn 3 heavy mechs"* or *"if player has Rank > 80%, spawn elite red battalion"*) is vastly simpler to write imperatively using **Coroutines** (Lua, Wren, or C#/Rust async state machines).

```
COROUTINE EXECUTION FLOW:
[Spawn Wave 1] ──► Yield: Wait(5.0s) ──► [Spawn Escorts] ──► Yield: WaitForAllDead(Wave 2)
                                                                       │
                                                                 (Resumes instantly
                                                                  when last enemy dies)
```

```rust
// Pseudocode: Stage Scripting Coroutine DSL
async fn execute_stage_1(stage: &mut StageContext) {
    // 00:00 - Introduction & Ambient Starfield
    stage.set_background("deep_space_nebula");
    stage.set_scroll_speed(150.0, 0.0);
    stage.wait_seconds(3.0).await;

    // 00:03 - Opening Wave: Pincer Formation
    let w1_left  = stage.spawn_squadron("drone_scout", "spline_left_dive", 300.0);
    let w1_right = stage.spawn_squadron("drone_scout", "spline_right_dive", 300.0);
    stage.wait_seconds(4.0).await;

    // 00:07 - Dynamic Difficulty Check (Rank Scaling)
    if stage.get_battle_rank() > 0.75 {
        // High rank bonus wave
        stage.spawn_squadron("elite_stealth_fighter", "spline_swoop_center", 450.0);
    }

    // 00:15 - Gated Mid-Boss Encounter
    stage.set_scroll_speed(0.0, 2.0); // Decelerate camera to a halt
    let mid_boss = stage.spawn_boss("crustacean_dreadnought_v1", Vec2::new(320.0, -100.0));
    
    // Engine halts stage timeline progression until mid-boss entity is destroyed
    stage.wait_until_destroyed(mid_boss).await;

    // Resume high-speed scroll after midboss kill
    stage.trigger_screen_flash(1.0, 1.0, 1.0);
    stage.set_scroll_speed(600.0, 1.0); // Warp speed transition
    stage.wait_seconds(2.0).await;
}
```

---

## 6.4 Deterministic State Snapshotting & Input-Frame Replay

Replays in high-level shmups are not video recordings. They are **Input-Stream Logs**. An entire 45-minute playthrough can be stored in a file measuring less than **$500\text{ KB}$**.

```
                       REPLAY ARCHITECTURE
Play Session: [ Input Poller ] ──────► Save to File: [ Replay Stream (.rpl) ]
                                                            │
Playback:     [ Fixed Sim Loop ] ◄──── Read from File ──────┘
              (Zero GPU / Headless Verification capable at 10,000 FPS)
```

### 1. The Input Frame Buffer Format
At every fixed simulation tick ($60\text{ Hz}$), we pack player input into a compact 16-bit struct:

```rust
// Compact 2-Byte Input Frame Representation
struct InputFrame {
    buttons: u8, // Bitfield: [Shot:1, Bomb:1, Focus/Slow:1, WeaponSwitch:1, Start:1]
    axis_x: i8,  // Clamped -127 to +127 (or -1, 0, 1 for digital d-pad)
    axis_y: i8,  // Clamped -127 to +127
}
```

### 2. Seeded Deterministic PRNG
Never call standard library non-deterministic random functions (`rand()` or `Math.random()`). Use a seedable, fast, deterministic generator such as **PCG32** or **xoshiro256\*\***.

```rust
// Seedable Deterministic PCG32 PRNG
struct PCG32 {
    state: u64,
    inc: u64,
}

impl PCG32 {
    fn new(seed: u64, sequence: u64) -> Self {
        let mut pcg = PCG32 { state: 0, inc: (sequence << 1) | 1 };
        pcg.next_u32();
        pcg.state += seed;
        pcg.next_u32();
        pcg
    }

    fn next_u32(&mut self) -> u32 {
        let old_state = self.state;
        self.state = old_state.wrapping_mul(6364136223846793005).wrapping_add(self.inc);
        let xorshifted = (((old_state >> 18) ^ old_state) >> 27) as u32;
        let rot = (old_state >> 59) as u32;
        (xorshifted >> rot) | (xorshifted << ((!rot + 1) & 31))
    }

    fn next_f32_range(&mut self, min: f32, max: f32) -> f32 {
        let val = (self.next_u32() as f64) / (u32::MAX as f64);
        (min + (val as f32) * (max - min))
    }
}
```

### 3. Savestates & Instant Practice Mode Snapshots
To implement a professional "Practice Mode" where players can jump instantly to any phase of a boss or section of a level, the engine serializes the complete simulation state:

```rust
// Complete Simulation Savestate Snapshot
struct SimulationSnapshot {
    tick_index: u64,
    timeline_time: f64,
    prng_state: PCG32,
    player_data: PlayerState,
    active_bullets: ProjectilePool,
    active_enemies: EnemyPool,
    spatial_grid: SpatialGrid,
    event_bus: EventBus,
}
```

Because our architecture uses flat, contiguous arrays and generational handles with zero heap pointers, saving and restoring a state is an instantaneous memory block copy (`memcpy`), taking under **$0.1\text{ ms}$**.

---

## 6.5 Chapter Takeaways & Pipeline Checklist

1. **Decouple time from camera scroll**: Use a timeline clock $t_{\text{stage}}$ with priority-queue event dispatch.
2. **Support asynchronous barrier gating**: Allow coroutines to pause time progression until wave conditions or boss phases are resolved.
3. **Replay by logging inputs**: Capture a 2-byte input struct per tick; combine with a seeded PRNG for 100% deterministic replays.
4. **Instant savestates**: Flat data layouts enable zero-cost `memcpy` snapshotting for practice modes and tool debugging.

In **[Chapter 7](file:///D:/Playing/coding-agent-experiments/antigravity-shmup-book/book/ch07_boss_architecture_and_choreography.md)**, we examine the climax of every stage: multi-phase boss architecture, hierarchical scene graphs, and dynamic difficulty rank calculus.

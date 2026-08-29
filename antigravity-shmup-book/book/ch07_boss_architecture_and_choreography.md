# Chapter 7: Boss Architecture & Choreography

The boss encounter is the theatrical and mechanical crescendo of a shmup stage. From the multi-stage mechanical behemoths of *Darius* and *R-Type* to the divine, pattern-weaving avatars of *Touhou Project* and *Mushihimesama*, boss battles test the player's routing, reaction speed, and nerve.

Engineering a boss requires coordinating **Hierarchical State Machines (HSMs)**, multi-part 2D scene graphs, bullet clear/cancel transitions, visual telegraphing, and dynamic difficulty scaling.

---

## 7.1 Control Architectures: HSMs vs. Behavior Trees

A boss is not a simple linear enemy. It progresses through multiple distinct health bars, reveals new attack forms, reacts to player proximity, and enters desperation states when near death.

```
                          BOSS LIFECYCLE STATE MACHINE
┌──────────────────┐      ┌────────────────────────┐      ┌────────────────────────┐
│  ENTRANCE PHASE  │ ───► │  ATTACK PHASE 1 (100%) │ ───► │ PHASE BREAK / CANCEL   │
│  - Screen Sweep  │      │  - 3-Way Spiral        │      │ - Invulnerability      │
│  - Siren / BGM   │      │  - Wing Turret Salvo   │      │ - Bullets -> Score     │
└──────────────────┘      └────────────────────────┘      └───────────┬────────────┘
                                                                      │
┌──────────────────┐      ┌────────────────────────┐                  │
│ DEFEAT SEQUENCE  │ ◄─── │ FINAL ENRAGE / SPELL   │ ◄────────────────┘
│ - Staggered Booms│      │ - Health < 25%         │
│ - Screen Whiteout│      │ - Maximum Density      │
└──────────────────┘      └────────────────────────┘
```

### Hierarchical State Machine (HSM) vs. Behavior Trees (BT)
While Behavior Trees are common in 3D open-world AI, **Hierarchical State Machines (HSMs)** are far superior for shmup bosses:
- **Deterministic Predictability**: Shmup patterns must be strictly choreographed so players can memorize dodging geometry.
- **Hierarchical Scoping**: A boss can share global sub-states (e.g., *Core Taking Damage Flash*, *Timer Countdown*, *Parts Orbiting*) while switching specific attack sub-states.

```rust
// Hierarchical Boss State Pattern
enum BossPhaseState {
    Entrance { timer: f32, target_pos: Vec2 },
    Phase1_DualSpirals { cycle_timer: f32, attack_variant: u8 },
    PhaseTransition { timer: f32, next_phase: u8 },
    Phase2_LaserSweeps { sweep_angle: f32, direction: f32 },
    Enrage_BulletTornado { intensity: f32 },
    Defeated { explosion_timer: f32, step: usize },
}

struct BossController {
    current_phase: BossPhaseState,
    phase_index: u8,
    max_phases: u8,
    health_current: f32,
    health_max_per_phase: f32,
    phase_timeout_seconds: f32,
    phase_timer: f32,
    is_invulnerable: bool,
}

impl BossController {
    fn update(&mut self, dt: f32, engine: &mut Engine) {
        self.phase_timer += dt;

        // Check for Phase Timeout (Prevent infinite stalling)
        if self.phase_timer >= self.phase_timeout_seconds && !self.is_invulnerable {
            self.trigger_phase_transition(engine, true /* timed_out */);
            return;
        }

        // Check for Health Depletion
        if self.health_current <= 0.0 && !self.is_invulnerable {
            self.trigger_phase_transition(engine, false /* killed */);
            return;
        }

        // Execute phase-specific logic
        match &mut self.current_phase {
            BossPhaseState::Phase1_DualSpirals { cycle_timer, attack_variant } => {
                *cycle_timer += dt;
                // Dispatch emitter barrages...
            }
            BossPhaseState::PhaseTransition { timer, next_phase } => {
                *timer -= dt;
                if *timer <= 0.0 {
                    self.enter_phase(*next_phase, engine);
                }
            }
            // ... remaining state logic
        }
    }
}
```

---

## 7.2 Multi-Part Hierarchical Scene Graphs & Destructible Entities

Iconic shmup bosses are massive composite structures. A single boss might consist of a main chassis, two destructible armored wings, four independently aiming laser turrets, and an exposed core.

```
                           BOSS SCENE GRAPH TOPOLOGY
                                  [ Main Core ]
                                 (Root Transform)
                                  /            \
                   [ Left Wing ]                 [ Right Wing ]
                  (Local: -120, +20)             (Local: +120, +20)
                   /           \                 /            \
          [Laser Turret]   [Armor Plate]   [Laser Turret]   [Armor Plate]
```

### 2D Forward Kinematics Matrix Propagation
Each child part maintains a **Local Transform** $(\vec{p}_{\text{local}}, \theta_{\text{local}}, \vec{s}_{\text{local}})$. The engine updates the hierarchy using standard 2D homogeneous transformation matrices:

$$\mathbf{M}_{\text{world}, \text{child}} = \mathbf{M}_{\text{world}, \text{parent}} \times \mathbf{M}_{\text{local}, \text{child}}$$

```rust
// 2D Hierarchical Scene Node
struct SceneNode2D {
    local_pos: Vec2,
    local_rotation: f32,
    world_matrix: Mat3x2,
    parent_index: Option<usize>,
    is_destructible: bool,
    health: f32,
    is_alive: bool,
    emitter_id: Option<usize>,
}

fn update_scene_hierarchy(nodes: &mut [SceneNode2D]) {
    for i in 0..nodes.len() {
        let local_matrix = Mat3x2::from_pos_rot(nodes[i].local_pos, nodes[i].local_rotation);
        
        nodes[i].world_matrix = match nodes[i].parent_index {
            Some(parent_idx) => nodes[parent_idx].world_matrix * local_matrix,
            None => local_matrix, // Root node
        };
    }
}
```

### Mechanical Consequences of Sub-Component Destruction
Destruction of a sub-component should dynamically reshape the boss's mechanics:
- **Disabling Attacks**: Destroying the left missile bay disables that emitter entirely.
- **Enrage Compensation**: When both wings are severed, the core enters an aggressive rapid-fire state.
- **Score & Secret Routing**: Destroying all parts before destroying the core awards a lucrative *Technical Destruction Bonus* or unlocks secret second-loop paths.

---

## 7.3 Phase Transitions, Timeouts, and Enrage Choreography

Phase transitions require careful state handling to prevent unfair player deaths.

```
PHASE 1 FINISH ──► 1. Trigger Bullet-Cancel (All bullets -> Gems/Items)
                   2. Grant Boss Invulnerability (I-Frames)
                   3. Play Stagger/VFX Animation
                   4. Reposition Boss to Phase 2 Origin
                   5. Initialize Phase 2 Health Bar & Emitters
```

```rust
// Bullet Cancel & Score Conversion Routine
fn cancel_all_enemy_bullets(pool: &mut ProjectilePool, engine: &mut Engine) {
    for i in 0..pool.count {
        if pool.is_active(i) {
            let pos = pool.get_position(i);
            pool.deactivate(i);
            
            // Spawn Score Crystal / Gem at bullet position
            engine.spawn_score_pickup(pos, PickupType::ScoreGem);
            // Spawn subtle dissipation particle
            engine.particle_system.spawn_dissipate(pos);
        }
    }
}
```

---

## 7.4 Visual Telegraphing and Fairness Rules

High-density bullet hell games maintain a sacred contract with the player: **every death must be the player's fault**. Unavoidable attacks, off-screen snipes, and deceptive hitboxes break this contract.

```
                      TELEGRAPHING LASER BEAM LIFECYCLE
Frame 0..30 (Charge & Aim):
Emitter [■] - - - - - - - - - - - - - - - - - - - - - - - - - - - ► (Low-Alpha Guide Line, 0 Damage)

Frame 31..60 (Lethal Fire):
Emitter [■]======================================================► (Solid Lethal Plasma Beam, Heavy Damage)
```

### Core Telegraphing Principles
1. **Low-Alpha Pre-Fire Guides**: Super-lasers and sniper shots must project a transparent tracking line or aiming laser $30\text{--}60$ frames before turning lethal.
2. **Audio Stingers & Pitch Shifts**: High-threat attacks should precede with an unmistakable audio charge-up sound.
3. **Palette & Contrast Isolation**:
   - Boss bullets must use high-contrast vibrant colors (e.g., magenta, cyan, bright amber) with white cores.
   - Backgrounds behind bosses must be desaturated or dimmed to guarantee immediate bullet silhouette visibility.

---

## 7.5 Battle Rank: Dynamic Difficulty Adjustment (DDA) Calculus

To challenge world-class arcade veterans without alienating beginners, commercial shmup bosses scale dynamically according to the **Battle Rank Formula**.

```
                        DYNAMIC RANK MODULATION
             Rank Value (R) in [0.0, 1.0]
                   │
         ┌─────────┼─────────┬─────────┐
         ▼         ▼         ▼         ▼
    Bullet Count Speed  Spread Arc   Health
     N = N0*(1+R) v=v0*(1+0.5R)  Phi=Phi0*(1-0.2R) HP=HP0*(1+0.3R)
```

```rust
// Dynamic Difficulty Rank Calculator
struct RankSystem {
    current_rank: f32, // Normalized 0.0 (Easiest) to 1.0 (Hardest)
    rank_per_second: f32,
    rank_per_powerup: f32,
    rank_loss_per_death: f32,
    rank_loss_per_bomb: f32,
}

impl RankSystem {
    // Compute scaled bullet count for an emitter based on rank
    fn scale_bullet_count(&self, base_count: usize, max_bonus: usize) -> usize {
        base_count + ((max_bonus as f32) * self.current_rank).round() as usize
    }

    // Compute scaled bullet velocity based on rank
    fn scale_bullet_speed(&self, base_speed: f32, max_multiplier: f32) -> f32 {
        base_speed * (1.0 + (max_multiplier - 1.0) * self.current_rank)
    }

    // Compute boss health scaling
    fn scale_boss_health(&self, base_health: f32) -> f32 {
        base_health * (1.0 + 0.5 * self.current_rank)
    }
}
```

---

## 7.6 Chapter Takeaways & Boss Design Checklist

1. **Use HSMs for phase control**: Keep attack states strictly separated from entrance and defeat choreography.
2. **Transform hierarchies via 2D matrix multiplication**: Model wings, turrets, and armor plates as child scene nodes.
3. **Always cancel bullets on phase clear**: Reward the player with score gems and visual breathing room.
4. **Telegraph high-speed attacks**: Never fire instant-kill beams without a pre-fire guide laser or audio cue.
5. **Tune patterns via Battle Rank**: Make bullet count and velocity scale cleanly with player skill.

In **[Chapter 8](file:///D:/Playing/coding-agent-experiments/antigravity-shmup-book/book/ch08_level_editor_architecture_and_tooling.md)**, we build the engine's creative control center: the in-engine level editor, timeline scrubber, interactive spline handles, and command pattern undo/redo systems.

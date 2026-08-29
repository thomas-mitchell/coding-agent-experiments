# Chapter 8: Level Editor Architecture & Tooling

A game engine is only as expressive as its authoring tools. Handcrafting thousands of spline coordinates, enemy wave timings, and bullet emitter parameters in raw JSON or code files is slow, tedious, and prone to calibration errors.

This chapter details the architecture of an **In-Engine Level & Wave Editor**, featuring multi-track timeline scrubbing, interactive Bézier tangent gizmos, a robust Command-Pattern undo/redo stack, and live simulation hot-reloading.

---

## 8.1 In-Engine Immediate GUI vs. External Editor Architecture

When building tooling for a high-performance 2D shmup, developers face a classic architectural choice: an **External Standalone IDE** (Qt, WPF, Electron) vs. an **In-Engine Embedded Editor** (Dear ImGui, Nuklear).

```
                          TOOLING PARADIGMS COMPARED
                          
   [ External Editor (Qt/Electron) ]             [ In-Engine Editor (Dear ImGui) ]
   ┌───────────────────────────────┐             ┌───────────────────────────────┐
   │ Tooling UI (Separate Process) │             │ Game Viewport & Simulation    │
   │      │ (IPC / Sockets)        │             │  ┌─────────────────────────┐  │
   │      ▼                        │             │  │ Dear ImGui Overlay UI   │  │
   │ Game Runtime Preview          │             │  └─────────────────────────┘  │
   └───────────────────────────────┘             └───────────────────────────────┘
   • High development cost                       • Zero IPC latency
   • Divergent render pipelines                  • Exact pixel/shader fidelity
   • Serialization desync bugs                   • Instant single-key Play/Edit toggle
```

### Why In-Engine Immediate-Mode Tooling Reigns Supreme
1. **Zero IPC / Serialization Friction**: The editor runs in the same memory space as the engine, directly mutating live entity pools and spline LUTs without network sockets or inter-process pipes.
2. **Exact Physics & Shader Fidelity**: What the designer sees while dragging a spline handle is rendered using the exact GPU shaders, particle buffers, and post-processing passes as the final game.
3. **Instant Play-Edit Toggle**: Pressing `F1` or `Spacebar` toggles between pausing the timeline to tweak a curve and instantly testing the dodge routing in real time.

---

## 8.2 Multi-Track Timeline Scrubber with Scrubbing & Step Precision

The core of a shmup editor is the **Multi-Track Timeline Canvas**. Designers must be able to drag a scrubber needle across time, jump between wave markers, and step forward or backward by single simulation ticks ($16.6\text{ ms}$).

```
TIMELINE SCRUBBER UI MOCKUP
[◄ Step] [► Play/Pause] [Step ►]  Time: [ 00:14.333 / 03:00.000 ]  Tick: #860
┌────────────────────────────────────────────────────────────────────────┐
│ ▼ WAVE TRACKS                                    Current Needle: 14.3s │
│   Squadron A: 4 Drones  [====Spline A====]                 │           │
│   Squadron B: 2 Heavies                   [===Spline B===] │           │
│ ▼ CAMERA TRACK                                             │           │
│   Scroll Speed          [ 150 px/s       ][ 400 px/s     ] │           │
│ ▼ SCRIPT EVENTS                                            │           │
│   BGM Stinger                             [ Stinger 1 ]    │           │
└────────────────────────────────────────────────────────────┴───────────┘
```

### The Bidirectional Time-Scrubbing Algorithm
Moving forward in time is simple (advance simulation ticks). Scrubbing *backwards* in time is mathematically non-trivial in a mutable simulation.

We solve reverse scrubbing using **Keyframe State Snapping + Fast-Forward Re-Simulation**:

```
                 SCRUBBING BACKWARDS FROM t=14.3s TO t=11.0s
1. Find nearest previous snapshot:       Keyframe at t=10.0s (Tick 600)
2. Fast-copy snapshot memory:            memcpy(live_sim, snapshot_10s)
3. Headless fast-forward simulation:     Run 60 ticks without rendering
4. Arrive at target time:                Exact state reconstructed at t=11.0s!
```

```rust
// Timeline Scrubbing Engine
struct EditorScrubber {
    timeline_duration: f64,
    current_time: f64,
    is_paused: bool,
    playback_speed: f64, // 0.25x, 0.5x, 1.0x, 2.0x
    snapshot_interval: f64, // Snapshot every 5.0 seconds
    snapshots: Map<u64, SimulationSnapshot>,
}

impl EditorScrubber {
    fn scrub_to_time(&mut self, target_time: f64, engine: &mut Engine) {
        self.current_time = clamp(target_time, 0.0, self.timeline_duration);
        let target_tick = (self.current_time * 60.0).round() as u64;

        // 1. Locate the closest preceding keyframe snapshot
        let snapshot_key = (target_tick / 300) * 300; // Snapshots every 300 ticks (5s)
        
        if let Some(snapshot) = self.snapshots.get(&snapshot_key) {
            engine.restore_snapshot(snapshot);
            
            // 2. Fast-forward headless simulation ticks to exact target
            let ticks_to_advance = target_tick - snapshot.tick_index;
            for _ in 0..ticks_to_advance {
                engine.headless_fixed_update(1.0 / 60.0);
            }
        }
    }
}
```

---

## 8.3 Interactive Bezier/Spline Canvas & Tangent Handle Gizmos

Designing enemy flight paths requires direct spatial manipulation of spline control points and tangent handles directly on the game viewport.

```
                  INTERACTIVE BÉZIER TANGENT GIZMOS
                             P1 (Tangent Handle)
                              ▲
                             /
                            /
                           ● P0 (Anchor Node)
                          /
                         /
                        ▼
                   P_prev (Mirrored Tangent Handle)
```

### Screen-to-World Ray Picking and Handle Selection
When the designer clicks the mouse on the viewport:

```rust
// Handle Picking & Tangent Constraint System
enum TangentConstraint {
    Mirrored, // Opposite handle matches angle and length
    Aligned,  // Opposite handle matches angle, free length
    Free,     // Tangents completely independent (sharp corners)
}

struct SplineGizmo {
    selected_spline_id: Option<usize>,
    selected_node_idx: Option<usize>,
    selected_handle: Option<HandleType>, // Anchor, InTangent, OutTangent
}

fn handle_viewport_click(gizmo: &mut SplineGizmo, splines: &[Spline], mouse_world: Vec2) {
    const PICK_RADIUS: f32 = 12.0;

    for (s_idx, spline) in splines.iter().enumerate() {
        for (n_idx, node) in spline.nodes.iter().enumerate() {
            if distance(mouse_world, node.anchor) <= PICK_RADIUS {
                gizmo.selected_spline_id = Some(s_idx);
                gizmo.selected_node_idx = Some(n_idx);
                gizmo.selected_handle = Some(HandleType::Anchor);
                return;
            }
            if distance(mouse_world, node.out_tangent) <= PICK_RADIUS {
                gizmo.selected_spline_id = Some(s_idx);
                gizmo.selected_node_idx = Some(n_idx);
                gizmo.selected_handle = Some(HandleType::OutTangent);
                return;
            }
        }
    }
}
```

### Live Ghosting and Speed Heatmaps
As a designer drags a tangent handle, the editor immediately:
1. Re-bakes the Arc-Length Look-Up Table (LUT) in $<10\mu\text{s}$.
2. Renders a **Ghost Trail**: a dotted visualization along the curve where the distance between dots represents physical velocity, and color shifts from green to red based on centrifugal curvature acceleration ($\kappa = \frac{\|\mathbf{B}' \times \mathbf{B}''\|}{\|\mathbf{B}'\|^3}$).

---

## 8.4 The Command Pattern for Unlimited Undo/Redo

Every mutation performed in the editor—moving a control point, modifying a bullet emitter angle, inserting an enemy wave—must be recorded as a command on an **Undo/Redo Stack**.

```
                        COMMAND STACK TOPOLOGY
   [ Move Node P0 ] ──► [ Change Emitter Type ] ──► [ Add Wave 3 ]
                                                         ▲ (Undo Pointer)
   Undo: Reverts "Add Wave 3" -> moves pointer left.
   Redo: Re-executes "Add Wave 3" -> moves pointer right.
```

### Merging Continuous Mouse Drag Actions (Transaction Coalescing)
If a user drags a spline handle across the screen for 2 seconds, generating 120 mouse move events, we must not flood the undo stack with 120 tiny steps. We implement **Command Merging**:

```rust
// Editor Command Pattern with Continuous Action Coalescing
trait EditorCommand {
    fn execute(&mut self, stage: &mut StageData);
    fn undo(&mut self, stage: &mut StageData);
    fn can_merge_with(&self, next: &dyn EditorCommand) -> bool;
    fn merge_with(&mut self, next: Box<dyn EditorCommand>);
}

struct MoveSplineNodeCommand {
    spline_id: usize,
    node_idx: usize,
    old_position: Vec2,
    new_position: Vec2,
    timestamp: f64,
}

impl EditorCommand for MoveSplineNodeCommand {
    fn execute(&mut self, stage: &mut StageData) {
        stage.splines[self.spline_id].nodes[self.node_idx].anchor = self.new_position;
        stage.rebake_spline_lut(self.spline_id);
    }

    fn undo(&mut self, stage: &mut StageData) {
        stage.splines[self.spline_id].nodes[self.node_idx].anchor = self.old_position;
        stage.rebake_spline_lut(self.spline_id);
    }

    fn can_merge_with(&self, next: &dyn EditorCommand) -> bool {
        // Merge drag updates on the same node occurring within 0.5s of each other
        if let Some(other) = next.as_any().downcast_ref::<MoveSplineNodeCommand>() {
            return self.spline_id == other.spline_id &&
                   self.node_idx == other.node_idx &&
                   (other.timestamp - self.timestamp) < 0.5;
        }
        false
    }

    fn merge_with(&mut self, next: Box<dyn EditorCommand>) {
        let other = next.as_any().downcast_ref::<MoveSplineNodeCommand>().unwrap();
        self.new_position = other.new_position;
        self.timestamp = other.timestamp;
    }
}
```

---

## 8.5 Live Simulation Hot-Reloading & In-Situ State Injection

To maximize iteration speed, the engine must support **Live Asset Hot-Reloading**. When a designer saves a stage file or tweaks an emitter script in an external text editor:

```
[ File System Watcher ] ──(FileModifiedEvent)──► [ Asset Manager ]
                                                        │
                                                        ▼
                                           [ In-Situ State Injection ]
                                           - Reload Spline LUTs
                                           - Recompile Emitter Bytecode
                                           - Preserve Active Player Coordinates
```

```rust
// Hot-Reloading Stage Watcher
fn check_asset_hot_reloads(engine: &mut Engine, file_watcher: &FileWatcher) {
    for modified_path in file_watcher.poll_events() {
        if modified_path.ends_with(".stage.json") {
            println!("Hot-reloading stage schema: {}", modified_path);
            let updated_stage = load_stage_file(&modified_path);
            
            // In-situ reload: preserve active player and camera, reload future timeline events
            engine.stage_timeline.hot_swap_remaining_events(updated_stage.timeline);
            engine.spline_library.reload_luts(updated_stage.splines);
        }
    }
}
```

---

## 8.6 Chapter Takeaways & Tooling Checklist

1. **Embed tools directly in-engine**: Use immediate-mode GUI overlays (Dear ImGui) for zero IPC latency and identical graphics fidelity.
2. **Implement bidirectional scrubbing**: Combine keyframe snapshots with headless forward ticks to scrub time backwards smoothly.
3. **Coalesce continuous commands**: Prevent drag events from cluttering the undo/redo stack.
4. **Provide visual feedback**: Render speed-colored ghost trails and arc-length tangent handles on the live viewport.

In **[Chapter 9](file:///D:/Playing/coding-agent-experiments/antigravity-shmup-book/book/ch09_vfx_audio_and_game_feel.md)**, we explore the sensory art and engineering of "juice": GPU particle batching, shockwave distortion shaders, trauma-decay screen shake, and audio voice coalescing.

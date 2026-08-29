# Chapter 3: High-Performance Collision & Spatial Partitioning

In a 2D shmup, collision detection is the primary computational bottleneck. When twenty thousand enemy bullets, five hundred high-fire-rate player shot pellets, forty enemy ships, and multi-segmented laser beams exist simultaneously, an unoptimized naive collision test will cripple even high-end desktop CPUs.

This chapter details the math and algorithms needed to cull, partition, and resolve tens of thousands of collision queries in under **$2.0\text{ ms}$**.

---

## 3.1 The Collision Complexity Crisis

A naive collision loop performs pairwise tests between every projectile and every target entity:

$$\text{Comparisons}_{\text{naive}} = N_{\text{player\_bullets}} \times M_{\text{enemies}} + N_{\text{enemy\_bullets}} \times M_{\text{player\_hulls}}$$

For $500$ player bullets against $300$ enemy targets, plus $25,000$ enemy bullets against the player's core hitbox and graze aura:

$$\text{Comparisons} = (500 \times 300) + (25,000 \times 2) = 150,000 + 50,000 = 200,000 \text{ checks/frame}$$

At 60 frames per second, this demands **$12,000,000$ geometric intersection tests every second**. If complex polygon or oriented bounding box checks are used, frame rates collapse.

We conquer this using a two-stage pipeline:
1. **Broad-Phase Culling**: Rapidly discards $99.8\%$ of non-colliding pairs using spatial partitioning in $O(N)$ time.
2. **Narrow-Phase Geometry**: Evaluates exact mathematical intersections only for surviving candidate pairs using SIMD-accelerated geometric algorithms.

```
┌────────────────────────────────────────────────────────┐
│  ALL ACTIVE ENTITIES (25,000 Projectiles + 300 Ships)  │
└───────────────────────────┬────────────────────────────┘
                            │
                            ▼
┌────────────────────────────────────────────────────────┐
│  BROAD-PHASE SPATIAL PARTITIONING (Uniform Hash Grid)  │
│  - Bin entities into spatial buckets                   │
│  - Reject distant pairs in O(1) per entity             │
└───────────────────────────┬────────────────────────────┘
                            │ (Only ~120 Candidate Pairs)
                            ▼
┌────────────────────────────────────────────────────────┐
│  NARROW-PHASE GEOMETRIC RESOLUTION                     │
│  - Circle-vs-Circle (Squared Distance)                 │
│  - Oriented Bounding Box (SAT Theorem)                 │
│  - Swept-Capsule Continuous Collision Detection (CCD)  │
└───────────────────────────┬────────────────────────────┘
                            │
                            ▼
┌────────────────────────────────────────────────────────┐
│  DISPATCH HIT / GRAZE / DAMAGE EVENTS                  │
└────────────────────────────────────────────────────────┘
```

---

## 3.2 Broad-Phase Spatial Partitioning Data Structures

Selecting the correct spatial structure requires analyzing the motion characteristics of a shmup:
- Almost **100% of all entities move every single frame**.
- Tree structures (like Quadtrees or Dynamic BVH trees) suffer massive performance degradation because nodes must be re-inserted, re-balanced, and memory allocated every tick.

| Spatial Structure | Update Cost ($N$ moving items) | Query Cost | Memory Overhead | Cache Locality | Verdict for Shmups |
| :--- | :--- | :--- | :--- | :--- | :--- |
| **Naive All-Pairs** | $O(1)$ | $O(N \times M)$ | Zero | Excellent | ❌ Unusable for $>500$ entities |
| **Quadtree** | $O(N \log N)$ (rebuild/rebalance) | $O(\log N)$ | High (node pointers) | Poor (pointer chasing) | ⚠️ Acceptable for static terrain |
| **Dynamic BVH** | $O(N \log N)$ (tree rotations) | $O(\log N)$ | Moderate | Moderate | ⚠️ Great for large composite bosses |
| **Uniform Spatial Hash Grid** | $O(N)$ (flat array write) | $O(1)$ average | Very Low (flat arrays) | **Optimal (Contiguous)** | ✅ **Industry Standard for Danmaku** |

### The Uniform Spatial Hash Grid Architecture
A spatial hash grid subdivides the 2D playfield into uniform cells of size $S_{\text{cell}}$ (typically $32 \times 32$ or $64 \times 64$ pixels).

```
PLAYFIELD (e.g., 640x960 px)
Cell Size = 64px (10 columns x 15 rows = 150 Cells)

Cell Index = (y / CellSize) * GridWidth + (x / CellSize)

┌────┬────┬────┬────┬────┐
│ 0  │ 1  │ 2  │ 3  │ 4  │   Enemy Ship in Cell 2
├────┼────┼────┼────┼────┤
│ 5  │ 6  │ 7  │ 8  │ 9  │   Player Bullet queries only Cells [1,2,3, 6,7,8]
├────┼────┼────┼────┼────┤
│ 10 │ 11 │ 12 │ 13 │ 14 │
└────┴────┴────┴────┴────┘
```

### Zero-Allocation Spatial Hash Implementation
Instead of using dynamic vectors inside each grid cell (which causes memory fragmentation), we implement the grid using two pre-allocated flat integer arrays: **Cell Heads** and **Next Pointers** (a flattened linked-list over array indices).

```rust
// High-Performance Flat Spatial Hash Grid
const CELL_SIZE: f32 = 64.0;
const GRID_COLS: usize = 16;  // e.g., 1024px width
const GRID_ROWS: usize = 20;  // e.g., 1280px height
const TOTAL_CELLS: usize = GRID_COLS * GRID_ROWS;
const MAX_ENTITIES: usize = 32768;

struct SpatialGrid {
    cell_heads: Array<i32, TOTAL_CELLS>,  // Index to first entity in cell (-1 if empty)
    entity_next: Array<i32, MAX_ENTITIES>, // Pointer to next entity in same cell
}

impl SpatialGrid {
    fn clear(&mut self) {
        // Fast SIMD memset to -1
        fill_memory(&mut self.cell_heads, -1);
    }

    // Compute 1D bucket index from 2D coordinates
    fn cell_coord(&self, x: f32, y: f32) -> Option<usize> {
        if x < 0.0 || y < 0.0 { return None; }
        let cx = (x / CELL_SIZE) as usize;
        let cy = (y / CELL_SIZE) as usize;
        if cx < GRID_COLS && cy < GRID_ROWS {
            Some(cy * GRID_COLS + cx)
        } else {
            None
        }
    }

    // Insert entity in O(1) time without heap allocation
    fn insert(&mut self, entity_idx: usize, pos_x: f32, pos_y: f32) {
        if let Some(cell_idx) = self.cell_coord(pos_x, pos_y) {
            self.entity_next[entity_idx] = self.cell_heads[cell_idx];
            self.cell_heads[cell_idx] = entity_idx as i32;
        }
    }

    // Query all entities within neighboring 3x3 cells
    fn query_range<F>(&self, pos_x: f32, pos_y: f32, radius: f32, mut visitor: F)
    where F: FnMut(usize) {
        let min_cx = max(0, ((pos_x - radius) / CELL_SIZE) as i32);
        let max_cx = min(GRID_COLS as i32 - 1, ((pos_x + radius) / CELL_SIZE) as i32);
        let min_cy = max(0, ((pos_y - radius) / CELL_SIZE) as i32);
        let max_cy = min(GRID_ROWS as i32 - 1, ((pos_y + radius) / CELL_SIZE) as i32);

        for cy in min_cy..=max_cy {
            for cx in min_cx..=max_cx {
                let cell_idx = (cy as usize) * GRID_COLS + (cx as usize);
                let mut curr = self.cell_heads[cell_idx];
                while curr != -1 {
                    visitor(curr as usize);
                    curr = self.entity_next[curr as usize];
                }
            }
        }
    }
}
```

---

## 3.3 Narrow-Phase Primitives and Separating Axis Theorem (SAT)

Once broad-phase culling yields candidate pairs, narrow-phase checks determine precise intersection.

```
                    ┌────────────────────────────┐
                    │   NARROW-PHASE HIERARCHY   │
                    └─────────────┬──────────────┘
                                  │
         ┌────────────────────────┼────────────────────────┐
         ▼                        ▼                        ▼
┌──────────────────┐    ┌──────────────────┐    ┌──────────────────┐
│ Circle vs Circle │    │ Circle vs OBB    │    │ OBB vs OBB (SAT) │
│ - 90% of bullets │    │ - Bullets vs     │    │ - Rotated ships  │
│ - Distance^2     │    │   rotated wings  │    │   vs giant beams │
└──────────────────┘    └──────────────────┘    └──────────────────┘
```

### 1. Circle-vs-Circle Test (Squared Distance Optimization)
Never call square root (`sqrt`) in bullet collision loops. Compare squared distance against squared radius sums:

$$\Delta x = x_2 - x_1, \quad \Delta y = y_2 - y_1$$

$$\text{Colliding} \iff (\Delta x^2 + \Delta y^2) \le (r_1 + r_2)^2$$

### 2. Separating Axis Theorem (SAT) for Oriented Bounding Boxes (OBB)
When enemy bosses rotate, their rectangular wings and laser turrets rotate. Axis-Aligned Bounding Boxes (AABB) become overly loose, leading to false hits. We must test **Oriented Bounding Boxes (OBBs)** using the **Separating Axis Theorem (SAT)**.

> **Theorem (SAT)**: Two convex 2D polygons do *not* intersect if and only if there exists a 1D axis along which the projections of the two polygons do not overlap.

For two 2D oriented rectangles $A$ and $B$, we only need to test **4 candidate projection axes**: the 2 local normal axes of $A$, and the 2 local normal axes of $B$.

```
         Axis of Projection (L)
         ───┬───────────┬──────────────┬───────────┬───►
            │           │              │           │
          [   Proj(A)   ]              [  Proj(B)  ]
                           ▲ (Gap exists! Not colliding)
```

```rust
// 2D Separating Axis Theorem (SAT) for Oriented Bounding Boxes
struct OBB {
    center: Vec2,
    extents: Vec2,    // Half-width and half-height (unrotated)
    rotation: f32,    // Radians
}

fn intersect_obb_obb(a: &OBB, b: &OBB) -> bool {
    // Compute unit orientation vectors (local axes)
    let axes_a = [
        Vec2::new(cos(a.rotation), sin(a.rotation)),
        Vec2::new(-sin(a.rotation), cos(a.rotation)),
    ];
    let axes_b = [
        Vec2::new(cos(b.rotation), sin(b.rotation)),
        Vec2::new(-sin(b.rotation), cos(b.rotation)),
    ];

    let distance_vector = b.center - a.center;

    // Test all 4 potential separating axes
    for axis in [axes_a[0], axes_a[1], axes_b[0], axes_b[1]] {
        // Project center distance onto current axis
        let projected_distance = abs(dot(distance_vector, axis));

        // Project half-extents of OBB A onto current axis
        let radius_a = a.extents.x * abs(dot(axes_a[0], axis)) +
                       a.extents.y * abs(dot(axes_a[1], axis));

        // Project half-extents of OBB B onto current axis
        let radius_b = b.extents.x * abs(dot(axes_b[0], axis)) +
                       b.extents.y * abs(dot(axes_b[1], axis));

        // If a separating gap exists along this axis, no collision occurs
        if projected_distance > (radius_a + radius_b) {
            return false;
        }
    }

    true // Overlap confirmed along all 4 axes -> Collision detected!
}
```

---

## 3.4 Continuous Collision Detection (CCD) for High-Velocity Beams

In arcade-style shooters, high-velocity sniper bullets and player lasers travel at speeds exceeding $2,000\text{ pixels/sec}$. In a discrete $60\text{ Hz}$ simulation, an entity advances by $\ge 35\text{ pixels}$ per tick. If a player's hitbox radius is $3\text{ pixels}$, a projectile will skip clean through the ship between ticks without triggering a collision. This is known as **bullet tunneling**.

```
Frame N: Bullet (Pos A)                  Player Ship (3px radius)      Frame N+1: Bullet (Pos B)
        ●                                         [ (•) ]                         ●
        └──────────────────────── Skipped over! ──────────────────────────────────┘
```

### Swept-Circle vs. Circle Continuous Test (Capsule Intersection)
Instead of testing point-in-circle at frame $N+1$, we model the bullet's motion from $\vec{A}$ to $\vec{B}$ as a **capsule** (a line segment swept by the bullet's radius $r_{\text{bullet}}$).

```
          Pos A ────► Bullet Travel Vector ────► Pos B
         ( ●══════════════════════════════════════● )  <--- Swept Capsule Hull
                      \             /
                       \ [ Target ]/  <--- Point-to-Segment Distance Test
```

```rust
// Continuous Collision Detection: Swept Circle vs Stationary Target Circle
fn intersect_swept_circle(
    start_pos: Vec2,
    end_pos: Vec2,
    bullet_radius: f32,
    target_pos: Vec2,
    target_radius: f32,
) -> bool {
    let segment = end_pos - start_pos;
    let to_target = target_pos - start_pos;
    let seg_len_sq = dot(segment, segment);

    // If bullet is stationary, perform static circle test
    if seg_len_sq < 0.0001 {
        let dist_sq = dot(to_target, to_target);
        let total_r = bullet_radius + target_radius;
        return dist_sq <= (total_r * total_r);
    }

    // Project target center onto bullet motion segment, clamped to [0.0, 1.0]
    let t = clamp(dot(to_target, segment) / seg_len_sq, 0.0, 1.0);

    // Find closest point on swept trajectory segment to target center
    let closest_point = start_pos + segment * t;
    let delta = target_pos - closest_point;
    let dist_sq = dot(delta, delta);

    let total_radius = bullet_radius + target_radius;
    dist_sq <= (total_radius * total_radius)
}
```

---

## 3.5 Multi-Hull Architecture: Hitbox, Hurtbox, and Graze-Box

Entities register multiple collision layers using a **Collision Bitmask Matrix**.

```rust
// Bitflags for Collision Layers and Filter Masks
const LAYER_PLAYER_HITBOX: u32    = 1 << 0;
const LAYER_PLAYER_GRAZEBOX: u32  = 1 << 1;
const LAYER_PLAYER_BULLET: u32    = 1 << 2;
const LAYER_ENEMY_HURTBOX: u32    = 1 << 3;
const LAYER_ENEMY_BULLET: u32     = 1 << 4;
const LAYER_ITEM_PICKUP: u32      = 1 << 5;

// Layer Interaction Mask Matrix:
// LAYER_ENEMY_BULLET interacts with (LAYER_PLAYER_HITBOX | LAYER_PLAYER_GRAZEBOX)
// LAYER_PLAYER_BULLET interacts with (LAYER_ENEMY_HURTBOX)
```

```rust
// Multi-Hull Player Evaluation Routine
fn evaluate_enemy_bullet_vs_player(
    bullet_pos: Vec2, 
    bullet_r: f32, 
    player: &Player, 
    bus: &mut EventBus
) {
    let dist_sq = distance_squared(bullet_pos, player.core_pos);

    // 1. Test Lethal Core Hitbox First (Highest Priority)
    let lethal_r = bullet_r + player.core_radius;
    if dist_sq <= (lethal_r * lethal_r) {
        bus.publish(GameEvent::PlayerDied { player_id: player.id, death_pos: player.core_pos });
        return;
    }

    // 2. Test Outer Graze Aura (Only if lethal test missed)
    let graze_r = bullet_r + player.graze_radius;
    if dist_sq <= (graze_r * graze_r) {
        bus.publish(GameEvent::BulletGrazed { player_id: player.id, bullet_pos });
    }
}
```

---

## 3.6 Chapter Takeaways & Performance Targets

1. **Broad-phase culling is non-negotiable**: A $64\text{px}$ Uniform Spatial Hash Grid reduces pairwise queries from $200,000$ to $<200$ per tick.
2. **Never allocate during collision ticks**: Maintain flat index-linked buckets in pre-allocated static arrays.
3. **Squared distance over sqrt**: Omit square roots across all circle-circle calculations.
4. **Use CCD for hyper-velocity projectiles**: Swept-circle capsule tests eliminate bullet tunneling.

With collision and spatial indexing running at microsecond speeds, we turn to **[Chapter 4](file:///D:/Playing/coding-agent-experiments/antigravity-shmup-book/book/ch04_bullet_choreography_and_danmaku_math.md)** to explore the trigonometry, vector calculus, and emitter choreography behind complex danmaku patterns.

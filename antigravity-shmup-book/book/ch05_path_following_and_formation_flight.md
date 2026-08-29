# Chapter 5: Enemy Path Following, Kinematics & Formation Flight

A defining characteristic of arcade shmups is the acrobatic entrance and exit maneuvers of enemy waves. In games like *Galaga*, *Gradius*, *Ikaruga*, and *DoDonPachi*, enemy squadrons swoop across the screen in tight geometric formations, bank gracefully along curving trajectories, and break off into tactical attack runs.

Implementing this requires solving a notorious computer graphics and kinematics challenge: **Arc-Length Parameterized Spline Traversal**.

---

## 5.1 Parametric Splines in 2D Space

Linear waypoint interpolation (`pos = lerp(A, B, t)`) produces sharp, robotic corners that look jarring. To achieve smooth cinematic flight, we use **Parametric Splines**.

```
       QUADRATIC BÉZIER (3 Points)                    CUBIC BÉZIER (4 Points)
               P1 (Control)                            P1                   P2
               ▲                                       ▲                    ▲
              / \                                     /                      \
             /   \                                   /                        \
            /     \                                 /                          \
           ●───────●                               ●────────────────────────────●
          P0       P2                             P0                            P3
```

### 1. Cubic Bézier Curves
A Cubic Bézier curve is defined by four control points: $\mathbf{P}_0$ (start), $\mathbf{P}_1$ (start tangent handle), $\mathbf{P}_2$ (end tangent handle), and $\mathbf{P}_3$ (end):

$$\mathbf{B}(t) = (1-t)^3 \mathbf{P}_0 + 3(1-t)^2 t \mathbf{P}_1 + 3(1-t) t^2 \mathbf{P}_2 + t^3 \mathbf{P}_3, \quad t \in [0, 1]$$

Its velocity vector (first derivative) is:

$$\mathbf{B}'(t) = 3(1-t)^2 (\mathbf{P}_1 - \mathbf{P}_0) + 6(1-t)t (\mathbf{P}_2 - \mathbf{P}_1) + 3t^2 (\mathbf{P}_3 - \mathbf{P}_2)$$

### 2. Centripetal Catmull-Rom Splines
While Bézier curves are ideal for designer-authored standalone paths, **Catmull-Rom Splines** are preferred when stitching together long sequences of waypoints because the curve is guaranteed to pass *directly* through every control point with $C^1$ tangential continuity.

Standard uniform Catmull-Rom splines suffer from cusps and self-intersections when control points are spaced unevenly. We utilize the **Centripetal formulation** ($\alpha = 0.5$):

$$t_{i+1} = t_i + \|\mathbf{P}_{i+1} - \mathbf{P}_i\|^{\alpha}$$

```rust
// Centripetal Catmull-Rom Segment Evaluation
fn evaluate_catmull_rom(
    p0: Vec2, p1: Vec2, p2: Vec2, p3: Vec2, 
    t: f32 // Normalized segment parameter [0, 1]
) -> Vec2 {
    let t2 = t * t;
    let t3 = t2 * t;

    // Standard Catmull-Rom Basis Matrix
    let v0 = (p2 - p0) * 0.5;
    let v1 = (p3 - p1) * 0.5;

    p1 * (2.0 * t3 - 3.0 * t2 + 1.0) +
    p2 * (-2.0 * t3 + 3.0 * t2) +
    v0 * (t3 - 2.0 * t2 + t) +
    v1 * (t3 - t2)
}
```

---

## 5.2 The Arc-Length Parameterization Problem & Speed Stabilization

The most common rookie engine bug in path-following is incrementing $t$ linearly over time:

$$t_{\text{next}} = t_{\text{curr}} + \frac{\text{speed}}{\text{total\_time}} \cdot \Delta t \quad \text{[INCORRECT!]}$$

Because $\mathbf{B}(t)$ is non-linear in spatial distance, evaluating equal increments of $t$ causes the enemy ship to **violently accelerate through stretched sections and crawl through tight curves**.

```
NAIVE EVALUATION (Equal dt produces unequal spatial steps):
P0 ●───●───────●─────────────●─────────────────────────────● P3
   t=0.1  t=0.2     t=0.3                 t=0.4               t=1.0
   [Slow]              [Accelerating...]               [Supersonic Warp]

DESIRED BEHAVIOR (Constant physical velocity v):
P0 ●─────●─────●─────●─────●─────●─────●─────●─────●─────● P3
   s=10  s=20  s=30  s=40  s=50  s=60  s=70  s=80  s=90  s=100 px
```

### The Arc-Length Integral
The physical distance $s(t)$ traveled along a curve from parameter $0$ to $t$ is the integral of the speed:

$$s(t) = \int_{0}^{t} \|\mathbf{B}'(u)\| \, du = \int_{0}^{t} \sqrt{\left(\frac{dx}{du}\right)^2 + \left(\frac{dy}{du}\right)^2} \, du$$

This integral has no general closed-form analytical solution for cubic polynomials. We must compute it numerically.

---

## 5.3 Look-Up Table (LUT) Inversion and Simpson's Rule Integration

To achieve $O(1)$ constant-speed path sampling at runtime, we pre-calculate an **Arc-Length Look-Up Table (LUT)** when baking or loading the level.

```
       FORWARD INTEGRATION                         LUT INVERSION
       t in [0.0, 1.0]                           Distance s in [0, L]
              │                                           │
              ▼ (Numerical Simpson's Rule)                ▼ (Binary Search + Lerp)
     Cumulative Length s(t)                      Exact Curve Parameter t(s)
```

```rust
// Arc-Length Parameterization Data Structure
const LUT_SAMPLES: usize = 128; // 128 samples provides sub-pixel precision

struct SplinePathLUT {
    samples_t: Array<f32, LUT_SAMPLES>,
    samples_dist: Array<f32, LUT_SAMPLES>,
    total_length: f32,
}

// Numerical Integration using Composite Simpson's Rule
fn bake_spline_lut(p0: Vec2, p1: Vec2, p2: Vec2, p3: Vec2) -> SplinePathLUT {
    let mut lut = SplinePathLUT::default();
    lut.samples_t[0] = 0.0;
    lut.samples_dist[0] = 0.0;

    let mut cumulative_dist = 0.0;
    let n = LUT_SAMPLES - 1;
    let dt = 1.0 / (n as f32);

    for i in 1..=n {
        let t_curr = (i as f32) * dt;
        let t_prev = ((i - 1) as f32) * dt;
        let t_mid = (t_prev + t_curr) * 0.5;

        // Composite Simpson's rule: (dt / 6) * (f(a) + 4f(m) + f(b))
        let speed_prev = evaluate_derivative(p0, p1, p2, p3, t_prev).length();
        let speed_mid  = evaluate_derivative(p0, p1, p2, p3, t_mid).length();
        let speed_curr = evaluate_derivative(p0, p1, p2, p3, t_curr).length();

        let step_dist = (dt / 6.0) * (speed_prev + 4.0 * speed_mid + speed_curr);
        cumulative_dist += step_dist;

        lut.samples_t[i] = t_curr;
        lut.samples_dist[i] = cumulative_dist;
    }

    lut.total_length = cumulative_dist;
    lut
}
```

### Inverting the LUT at Runtime
To sample the curve at an exact physical distance $d \in [0, \text{total\_length}]$:

```rust
// Invert Arc-Length Table: Given Distance -> Return Normalized Parameter t
fn sample_spline_at_distance(lut: &SplinePathLUT, distance: f32) -> f32 {
    let clamped_d = clamp(distance, 0.0, lut.total_length);

    // Binary search to locate the bounding distance interval [dist[i], dist[i+1]]
    let mut low = 0;
    let mut high = LUT_SAMPLES - 1;

    while low < high - 1 {
        let mid = (low + high) / 2;
        if lut.samples_dist[mid] <= clamped_d {
            low = mid;
        } else {
            high = mid;
        }
    }

    // Linearly interpolate between the two closest sample points
    let d0 = lut.samples_dist[low];
    let d1 = lut.samples_dist[high];
    let segment_alpha = if (d1 - d0) > 0.0001 { (clamped_d - d0) / (d1 - d0) } else { 0.0 };

    let t0 = lut.samples_t[low];
    let t1 = lut.samples_t[high];

    t0 + segment_alpha * (t1 - t0)
}
```

---

## 5.4 Autonomous Steering Behaviors and Target Interception

Not all enemies follow rigid, pre-baked splines. Interceptor drones, suicide craft, and elite escorts utilize **Reynolds Autonomous Steering Behaviors**.

$$\vec{F}_{\text{steering}} = \text{truncate}\left(\vec{v}_{\text{desired}} - \vec{v}_{\text{current}}, \; F_{\max}\right)$$

```
                       REYNOLDS ARRIVE BEHAVIOR
                Slowing Radius R
             ┌─────────────────────┐
             │                     │
             │           Target ●  │
             │          /          │
             │         / (Decelerate)
             │        ▲            │
             └───────/─────────────┘
                    / (Max Speed)
                   ● Current Ship
```

```rust
// 2D Reynolds Steering Behaviors
struct SteeringAgent {
    position: Vec2,
    velocity: Vec2,
    max_speed: f32,
    max_force: f32,
}

impl SteeringAgent {
    // Seek with Arrival Deceleration Zone
    fn arrive(&self, target: Vec2, slowing_radius: f32) -> Vec2 {
        let to_target = target - self.position;
        let distance = to_target.length();

        if distance < 0.001 {
            return -self.velocity; // Stop completely
        }

        // Ramp down speed inside slowing radius
        let target_speed = if distance < slowing_radius {
            self.max_speed * (distance / slowing_radius)
        } else {
            self.max_speed
        };

        let desired_velocity = (to_target / distance) * target_speed;
        let steering_force = desired_velocity - self.velocity;

        truncate_vector(steering_force, self.max_force)
    }

    // Path Following with Predictive Lookahead Point
    fn follow_path(&self, lut: &SplinePathLUT, current_dist: &mut f32, lookahead_dist: f32, dt: f32) -> Vec2 {
        // Advance virtual anchor point along spline
        *current_dist += self.max_speed * dt;
        let target_dist = *current_dist + lookahead_dist;
        
        let t_target = sample_spline_at_distance(lut, target_dist);
        let target_pos = evaluate_spline_position(t_target);

        self.arrive(target_pos, 40.0)
    }
}
```

---

## 5.5 Squadron Hierarchy and Formation Flight Matrices

Authoring complex wave swoops for a 5-ship squadron does not require 5 individual spline paths. Instead, we choreograph **one Virtual Leader Anchor**, and evaluate follower positions using **Local Transform Offsets**.

```
                             SQUADRON V-FORMATION
                             
                                [Virtual Anchor] (Follows Arc-Length Spline)
                                       ▲ (Heading θ)
                                      / \
                       Offset (-40, -30)  Offset (+40, -30)
                         [Wingman 1]        [Wingman 2]
                             /                    \
              Offset (-80, -60)                  Offset (+80, -60)
                [Wingman 3]                        [Wingman 4]
```

### The 2D Formation Transformation Equation
Let the virtual anchor have position $\vec{P}_{\text{anchor}}(t)$ and heading angle $\theta_{\text{anchor}}(t)$ (derived from the spline tangent derivative $\mathbf{B}'(t)$).

For a squadron member with local formation offset $\vec{O}_i = (x_{\text{local}}, y_{\text{local}})$:

$$\mathbf{R}(\theta) = \begin{bmatrix} \cos(\theta) & -\sin(\theta) \\ \sin(\theta) & \cos(\theta) \end{bmatrix}$$

$$\vec{P}_{\text{world}, i} = \vec{P}_{\text{anchor}} + \mathbf{R}(\theta) \cdot \vec{O}_i$$

```rust
// Squadron Formation Update Routine
struct FormationWingman {
    entity_handle: EntityHandle,
    local_offset: Vec2,
    bank_angle_bias: f32,
}

struct Squadron {
    virtual_anchor_dist: f32,
    speed: f32,
    spline_lut_id: usize,
    wingmen: Array<FormationWingman, 8>,
    count: usize,
}

fn update_squadron_formation(squad: &mut Squadron, engine: &mut Engine, dt: f32) {
    squad.virtual_anchor_dist += squad.speed * dt;
    
    let lut = engine.get_spline_lut(squad.spline_lut_id);
    let t = sample_spline_at_distance(lut, squad.virtual_anchor_dist);
    
    let anchor_pos = evaluate_spline_position(lut, t);
    let anchor_tangent = evaluate_spline_tangent(lut, t);
    let heading_angle = atan2(anchor_tangent.y, anchor_tangent.x);

    let cos_h = cos(heading_angle);
    let sin_h = sin(heading_angle);

    for i in 0..squad.count {
        let wingman = &squad.wingmen[i];
        if let Some(entity) = engine.get_entity_mut(wingman.entity_handle) {
            // Apply 2D rotation matrix: R(theta) * offset
            let rotated_x = wingman.local_offset.x * cos_h - wingman.local_offset.y * sin_h;
            let rotated_y = wingman.local_offset.x * sin_h + wingman.local_offset.y * cos_h;

            entity.transform.position = anchor_pos + Vec2::new(rotated_x, rotated_y);
            // Point ship sprite in direction of flight with banking roll
            entity.transform.rotation = heading_angle;
        }
    }
}
```

---

## 5.6 Chapter Takeaways & Kinematics Checklist

1. **Never step raw $t$ on splines**: Always construct an Arc-Length Look-Up Table (LUT) with numerical Simpson's rule integration.
2. **Prefer Centripetal Catmull-Rom for multi-point paths**: Eliminates loop artifacts and cusps.
3. **Use Virtual Leader Anchors for squadrons**: Saves CPU memory and makes formation editing intuitive for designers.
4. **Blend splines with steering**: Allow enemy craft to follow splines for entrance choreographies, then smoothly detach into Reynolds steering behaviors for aggressive targeting runs.

In **[Chapter 6](file:///D:/Playing/coding-agent-experiments/antigravity-shmup-book/book/ch06_level_representation_and_scripting.md)**, we construct the stage timeline engine: event queues, trigger systems, level scripting DSLs, and deterministic replay capture.

# Chapter 4: Bullet Choreography & Danmaku Mathematics

Danmaku (*bullet curtain*) is the visual poetry and mathematical soul of the modern shooting game. What appears to a player as an overwhelming, chaotic wall of neon energy is, in reality, a collection of elegant parametric equations executed in polar coordinates.

This chapter uncovers the mathematics of bullet emitters, trigonometric geometries, quadratic target interception, segmented laser kinematics, and domain-specific scripting architectures.

---

## 4.1 Polar Coordinate Geometry and Radial Emitters

While game rendering takes place in 2D Cartesian space $(x, y)$, bullet choreography is almost exclusively authored in **Polar Coordinate Space** $(r, \theta)$:

$$x = x_{\text{origin}} + r \cos(\theta), \quad y = y_{\text{origin}} + r \sin(\theta)$$

$$\vec{v} = (s \cos(\theta), \; s \sin(\theta))$$

where $s$ is linear velocity (speed), and $\theta$ is the trajectory angle in radians.

```
                         θ = 3π/2 (-Y, Up)
                                ▲
                                │
   θ = π (-X, Left) ◄───────────┼───────────► θ = 0 (+X, Right)
                                │
                                ▼
                         θ = π/2 (+Y, Down)
```

```
                          RADIAL EMISSION GEOMETRIES
        N-Way Arc Spread                        Full Radial Ring (360°)
              \  |  /                                     ▲
             \ \ | / /                                 \  │  /
            ─── (•) ───                             ◄─── (•) ───►
               /   \                                   /  │  \
                                                          ▼
```

### 1. The $N$-Way Arc Spread
To fire an $N$-way spread of bullets centered around a base targeting angle $\theta_0$ with a total spread arc of $\Phi$:

$$\Delta \theta = \frac{\Phi}{N - 1} \quad (\text{for } N > 1)$$

$$\theta_i = \left( \theta_0 - \frac{\Phi}{2} \right) + i \cdot \Delta \theta, \quad \text{for } i \in [0, N-1]$$

### 2. The Rotating Spiral Emitter
A multi-arm rotating spiral updates its base angle incrementally on every firing tick:

$$\theta_{\text{base}}(t) = \theta_0 + \omega \cdot t$$

$$\theta_{i, \text{arm}}(t) = \theta_{\text{base}}(t) + i \cdot \left( \frac{2\pi}{M} \right), \quad \text{for } i \in [0, M-1]$$

where $\omega$ is the angular velocity in radians/second, and $M$ is the number of spiral arms.

### 3. Complex Geometric Curves (Rhodonea / Rose Patterns)
By modulating emission speed or angular offsets using trigonometric polynomials, we generate harmonic curtain patterns. 

A **Rhodonea (Rose) Curve** emitter modulates bullet speed or offset as a function of the emission angle:

$$r(\theta) = A \cos(k \theta)$$

```rust
// Pseudocode: Harmonic Rose Emitter Generator
fn emit_rose_pattern(
    pool: &mut ProjectilePool,
    origin: Vec2,
    base_angle: f32,
    petals: f32,       // Parameter 'k'
    bullet_count: usize,
    base_speed: f32,
) {
    let angle_step = (2.0 * PI) / (bullet_count as f32);

    for i in 0..bullet_count {
        let theta = base_angle + (i as f32) * angle_step;
        // Modulate bullet speed based on petal harmonic function
        let speed = base_speed * (0.4 + 0.6 * abs(cos(petals * theta * 0.5)));
        
        let velocity = Vec2::new(speed * cos(theta), speed * sin(theta));
        pool.spawn_bullet(origin, velocity, BulletType::Needle);
    }
}
```

---

## 4.2 Non-Linear Trajectories and Trigonometric Transforms

Linear bullets traveling at constant velocities produce rigid patterns. Elite danmaku engines incorporate time-dependent parametric transforms.

```
                         PARAMETRIC TRAJECTORY STYLES
     Decelerate & Turn                     Sinusoidal Wavy Beam
           ──┐                                  ~ ~ ~ ~ ~ ~ ~ ►
             │                                   (Oscillating)
             └──► (Delayed Aim)
```

### 1. Velocity Staging (Pause-and-Aim / Acceleration Curves)
Bullets often spawn with high initial velocity, decelerate to a complete stop, recalculate their angle toward the player, and accelerate outward:

$$s(t) = \begin{cases} 
s_0 - a_{\text{brake}} \cdot t & \text{if } t < t_{\text{stop}} \\
0 & \text{if } t_{\text{stop}} \le t < t_{\text{resume}} \\
a_{\text{accel}} \cdot (t - t_{\text{resume}}) & \text{if } t \ge t_{\text{resume}}
\end{cases}$$

### 2. Curvilinear Angular Drift
Instead of moving in a straight line, bullets can have a non-zero angular derivative $\dot{\theta}(t)$:

$$\theta_{t + \Delta t} = \theta_t + \omega_{\text{drift}} \cdot \Delta t$$

$$\vec{v}_{t + \Delta t} = (s \cos(\theta_{t + \Delta t}), \; s \sin(\theta_{t + \Delta t}))$$

### 3. Sinusoidal Perturbation (Wavy Trajectories)
To create serpentine, undulating streams, we apply a perpendicular sinusoidal displacement vector to the primary motion vector $\vec{v}_{\text{forward}}$:

$$\vec{n}_{\perp} = (-\sin(\theta), \; \cos(\theta))$$

$$\vec{P}(t) = \vec{P}_0 + \vec{v}_{\text{forward}} \cdot t + \vec{n}_{\perp} \cdot \left( A \sin(\omega t + \phi) \right)$$

---

## 4.3 Interception Mathematics: Leading Target Trajectories

Aiming directly at the player's current position ($\theta = \text{atan2}(y_P - y_E, x_P - x_E)$) is trivial for players to dodge by streaming (tapping slightly in one direction). High-threat enemies calculate **predictive leading trajectories** to intercept a moving player.

```
                           INTERCEPTION GEOMETRY
                                               Predicted Intercept Point
                                                       ● P_target(t)
                                                      / ^
                                                     /  │
                                    Bullet Path     /   │ Player Vector (v_T * t)
                                    (Speed s_B * t)/    │
                                                  /     │
                                                 /      │
                                                ●───────●
                                             Emitter   Player Current
                                              P_E        P_T
```

### Mathematical Derivation of Quadratic Interception
Let the player ship be at position $\vec{P}_T$ moving with constant velocity $\vec{v}_T$.
Let the emitter be at position $\vec{P}_E$. The enemy fires a bullet with known speed $s_B$ at time $t=0$.

We seek the future time $t > 0$ such that the bullet reaches the player's future position:

$$\vec{P}_T(t) = \vec{P}_T + \vec{v}_T \cdot t$$

$$\|\vec{P}_T(t) - \vec{P}_E\| = s_B \cdot t$$

Let relative displacement be $\vec{D} = \vec{P}_T - \vec{P}_E$. Squaring both sides:

$$\|\vec{D} + \vec{v}_T \cdot t\|^2 = (s_B \cdot t)^2$$

$$(\vec{D} \cdot \vec{D}) + 2(\vec{D} \cdot \vec{v}_T)t + (\vec{v}_T \cdot \vec{v}_T)t^2 = s_B^2 t^2$$

Rearranging into standard quadratic form $a t^2 + b t + c = 0$:

$$a = (\vec{v}_T \cdot \vec{v}_T) - s_B^2$$

$$b = 2(\vec{D} \cdot \vec{v}_T)$$

$$c = (\vec{D} \cdot \vec{D})$$

```rust
// Predictive Interception Calculation
fn calculate_lead_angle(
    emitter_pos: Vec2,
    target_pos: Vec2,
    target_vel: Vec2,
    bullet_speed: f32,
) -> Option<f32> {
    let d = target_pos - emitter_pos;
    
    let a = dot(target_vel, target_vel) - (bullet_speed * bullet_speed);
    let b = 2.0 * dot(d, target_vel);
    let c = dot(d, d);

    let discriminant = b * b - 4.0 * a * c;

    // If discriminant < 0, target is traveling faster than bullet speed and moving away
    if discriminant < 0.0 {
        return None; // Cannot intercept; fallback to direct aiming
    }

    let sqrt_disc = sqrt(discriminant);
    let t1 = (-b - sqrt_disc) / (2.0 * a);
    let t2 = (-b + sqrt_disc) / (2.0 * a);

    // Select the smallest positive arrival time t
    let t = match (t1 > 0.0, t2 > 0.0) {
        (true, true) => min(t1, t2),
        (true, false) => t1,
        (false, true) => t2,
        (false, false) => return None,
    };

    // Calculate future target position and resulting firing angle
    let intercept_point = target_pos + target_vel * t;
    let aim_vector = intercept_point - emitter_pos;
    
    Some(atan2(aim_vector.y, aim_vector.x))
}
```

---

## 4.4 Segmented Kinematic Beams and Laser Whips

Continuous curved lasers (such as the sweeping lasers in *Gradius V* or *DoDonPachi*) cannot be represented by simple circles or static boxes. They are modeled as **Kinematic Spline Node Chains**.

```
    Emitter ────► Node 1 ────► Node 2 ────► Node 3 ────► Node 4 (Laser Tip)
       [■]========(●)==========(●)==========(●)==========(●)
            Capsule 1    Capsule 2    Capsule 3    Capsule 4
```

### Mechanics of the Laser Node Chain
1. A head node updates its position and orientation according to the emitter's transform.
2. Trailing nodes follow previous positions from a fixed-length circular history buffer (distance-constrained kinematic chain).
3. Collision narrow-phase tests each link as a swept capsule segment between node $i$ and node $i+1$.
4. The GPU renders the laser by generating a dynamic triangle strip with UV coordinates mapped along the segment chain length.

---

## 4.5 Declarative Bullet Scripting & Emitter DSL Architecture

Hardcoding complex patterns in imperative code makes choreography rigid and painful to balance. Production shmup engines utilize a **Declarative Emitter Domain-Specific Language (DSL)** or a bytecode-compiled virtual machine (similar to *BulletML* or Lua coroutine choreographers).

```
                      EMITTER SCRIPT DOMAIN HIERARCHY
┌────────────────────────────────────────────────────────────────────────┐
│ <Emitter>                                                              │
│   ├── <Action name="SpiralBarrage">                                    │
│   │     ├── <Repeat count="36">                                        │
│   │     │     ├── <Fire angle="prev + 10" speed="350" type="Orb"/>     │
│   │     │     └── <Wait ticks="3"/>                                    │
│   │     └── </Repeat>                                                  │
│   └── </Action>                                                        │
└────────────────────────────────────────────────────────────────────────┘
```

### A Micro-Interpreter for Emitter Bytecode
Instead of allocating memory for string parsing at runtime, scripts are compiled offline into a dense byte stream executed by a stack-based **Emitter Virtual Machine**.

```rust
// Emitter VM Bytecode Instructions
enum EmitterOpcode {
    Fire { angle_offset: f32, speed: f32, bullet_type: u16 },
    SetAngularVelocity { omega: f32 },
    WaitTicks { count: u16 },
    LoopStart { count: u16 },
    LoopEnd,
    AimAtPlayer,
    Halt,
}

struct EmitterInstance {
    bytecode_ptr: usize,
    wait_counter: u16,
    loop_stack: Array<LoopFrame, 4>,
    loop_depth: usize,
    current_angle: f32,
    angular_speed: f32,
    position: Vec2,
}

fn step_emitter_vm(
    instance: &mut EmitterInstance, 
    program: &[EmitterOpcode], 
    pool: &mut ProjectilePool,
    player_pos: Vec2
) {
    if instance.wait_counter > 0 {
        instance.wait_counter -= 1;
        instance.current_angle += instance.angular_speed;
        return;
    }

    while instance.bytecode_ptr < program.len() {
        match program[instance.bytecode_ptr] {
            EmitterOpcode::Fire { angle_offset, speed, bullet_type } => {
                let theta = instance.current_angle + angle_offset;
                let vel = Vec2::new(speed * cos(theta), speed * sin(theta));
                pool.spawn_bullet(instance.position, vel, bullet_type);
                instance.bytecode_ptr += 1;
            }
            EmitterOpcode::WaitTicks { count } => {
                instance.wait_counter = count;
                instance.bytecode_ptr += 1;
                break; // Yield execution until next tick
            }
            EmitterOpcode::AimAtPlayer => {
                let delta = player_pos - instance.position;
                instance.current_angle = atan2(delta.y, delta.x);
                instance.bytecode_ptr += 1;
            }
            EmitterOpcode::LoopStart { count } => {
                instance.loop_stack[instance.loop_depth] = LoopFrame {
                    start_ptr: instance.bytecode_ptr + 1,
                    remaining: count,
                };
                instance.loop_depth += 1;
                instance.bytecode_ptr += 1;
            }
            EmitterOpcode::LoopEnd => {
                let frame = &mut instance.loop_stack[instance.loop_depth - 1];
                frame.remaining -= 1;
                if frame.remaining > 0 {
                    instance.bytecode_ptr = frame.start_ptr;
                } else {
                    instance.loop_depth -= 1;
                    instance.bytecode_ptr += 1;
                }
            }
            EmitterOpcode::Halt => {
                break;
            }
        }
    }
}
```

---

## 4.6 Chapter Takeaways & Pattern Design Checklist

1. **Polar coordinates dominate**: Author bullet emitters in terms of angular step $(\Delta \theta)$, radial speed $(s)$, and base rotation $(\theta_0)$.
2. **Predictive aiming stops streaming**: Interception calculation via quadratic equations punishes players who mindlessly tap across the screen.
3. **Use bytecode VM or coroutines**: Decouple emitter choreography from engine code; compile declarative scripts into flat bytecode.
4. **Modulate harmonics**: Rose curves, epicycloids, and angular derivatives create organic, geometric bullet curtains without extra collision overhead.

In **[Chapter 5](file:///D:/Playing/coding-agent-experiments/antigravity-shmup-book/book/ch05_path_following_and_formation_flight.md)**, we shift from projectile dynamics to enemy choreography: parametric splines, arc-length parameterization, and squadron formation flight.

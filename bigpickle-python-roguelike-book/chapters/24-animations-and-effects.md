# Chapter 24: Animations and Visual Effects

Animations bring a roguelike to life. While the game is turn-based, visual effects provide feedback, emphasize actions, and create atmosphere. This chapter covers frame-based animations, particle effects, screen shake, and tweened movement.

## Why Animations Matter

Even in a turn-based game, visual feedback is crucial:
- Attack animations confirm your action registered
- Damage numbers floating upward make combat feel impactful
- Screen shake on critical hits adds weight
- Particle effects for spells make magic feel powerful

## Frame-Based Animation System

We store animation data on entities and process them each frame:

```python
@attrs.define
class Animation:
    frames: list = attrs.Factory(list)      # list of (char, fg, bg) tuples
    current_frame: int = 0
    frame_duration: float = 0.15            # seconds per frame
    elapsed: float = 0.0
    loop: bool = False
    on_complete: str = ""                   # callback function name
```

The animation system updates each frame:

```python
def process_animations(dt: float) -> None:
    """Update all active animations."""
    for entity in list(active_animations):
        anim = entity.components[Animation]
        anim.elapsed += dt
        
        if anim.elapsed >= anim.frame_duration:
            anim.elapsed -= anim.frame_duration
            anim.current_frame += 1
            
            if anim.current_frame >= len(anim.frames):
                if anim.loop:
                    anim.current_frame = 0
                else:
                    active_animations.remove(entity)
```

## Floating Damage Numbers

Damage numbers float upward and fade out:

```python
@attrs.define
class FloatingText:
    text: str
    color: tuple[int, int, int]
    start_y: int
    elapsed: float = 0.0
    duration: float = 1.0
    speed: float = 5.0   # tiles per second


def create_floating_text(registry, x, y, text, color):
    """Create a floating damage number."""
    entity = registry.new_entity()
    entity.components[Position] = Position(x=x, y=y)
    entity.components[FloatingText] = FloatingText(
        text=text, color=color, start_y=y
    )
    return entity


def update_floating_text(entity, dt):
    """Move floating text upward and check expiry."""
    ft = entity.components[FloatingText]
    pos = entity.components[Position]
    ft.elapsed += dt
    pos.y = ft.start_y - int(ft.elapsed * ft.speed)
    
    if ft.elapsed >= ft.duration:
        # Remove entity
        return True  # signal removal
    return False
```

## Screen Shake

Screen shake adds impact to big moments:

```python
class ScreenShake:
    def __init__(self):
        self.intensity: int = 0
        self.duration: float = 0.0
        self.elapsed: float = 0.0
    
    def trigger(self, intensity: int = 3, duration: float = 0.3) -> None:
        self.intensity = intensity
        self.duration = duration
        self.elapsed = 0.0
    
    def get_offset(self) -> tuple[int, int]:
        """Get current shake offset."""
        if self.elapsed >= self.duration:
            return (0, 0)
        
        import random
        progress = self.elapsed / self.duration
        current_intensity = int(self.intensity * (1 - progress))
        
        return (
            random.randint(-current_intensity, current_intensity),
            random.randint(-current_intensity, current_intensity),
        )
    
    def update(self, dt: float) -> None:
        self.elapsed += dt
```

## Tweened Movement

Instead of teleporting, entities can move smoothly between tiles:

```python
@attrs.define
class Tween:
    start_x: int = 0
    start_y: int = 0
    target_x: int = 0
    target_y: int = 0
    elapsed: float = 0.0
    duration: float = 0.15
    
    @property
    def progress(self) -> float:
        return min(1.0, self.elapsed / self.duration)
    
    def get_position(self) -> tuple[float, float]:
        """Get interpolated position."""
        t = self.progress
        # Ease-out cubic
        t = 1 - (1 - t) ** 3
        x = self.start_x + (self.target_x - self.start_x) * t
        y = self.start_y + (self.target_y - self.start_y) * t
        return (x, y)
```

## Spell Visual Effects

Fireball creates expanding ring particles:

```python
import math

def create_fireball_effect(registry, center_x, center_y, radius):
    """Create fireball particle effect."""
    particles = []
    for angle in range(0, 360, 15):
        rad = math.radians(angle)
        for r in range(1, radius + 1):
            px = center_x + int(r * math.cos(rad))
            py = center_y + int(r * math.sin(rad))
            particles.append((px, py, (255, 127, 0)))
    return particles
```

## Tile Flashing

Briefly highlight tiles when something happens:

```python
@attrs.define
class TileFlash:
    x: int = 0
    y: int = 0
    color: tuple[int, int, int] = (255, 255, 255)
    elapsed: float = 0.0
    duration: float = 0.3
```

## Exercises

- Add spell casting animations (progressive particle spread)
- Implement entity death animations (fade out, dissolve)
- Create ambient particle effects (dust motes, dripping water)
- Add weather effects (rain, snow) using particles

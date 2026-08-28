# Chapter 25: Sound and Audio

Sound transforms a silent roguelike into an atmospheric experience. The sound of a sword striking, a potion being quaffed, or ambient dungeon dripping creates immersion that visuals alone cannot achieve. This chapter covers the tcod SDL audio system.

## Audio Architecture

tcod provides low-level SDL audio bindings through `tcod.sdl.audio`. We need:
- An audio device (output)
- Sound effects (short clips for actions)
- Music (longer tracks for atmosphere)
- Volume control

## Setting Up Audio

```python
import tcod.sdl.audio

def init_audio():
    """Initialize the audio system."""
    device = tcod.sdl.audio.open(
        allowed_changes=tcod.sdl.audio.AllowedChanges.ANY,
    )
    return device
```

## Loading Sound Effects

Sound effects are loaded from WAV files:

```python
class SoundManager:
    def __init__(self, device: tcod.sdl.audio.AudioDevice):
        self.device = device
        self.sounds: dict[str, tcod.sdl.audio.AudioStream] = {}
        self.music: tcod.sdl.audio.AudioStream | None = None
        self.sfx_volume: float = 0.7
        self.music_volume: float = 0.3
    
    def load_sound(self, name: str, filepath: str) -> None:
        """Load a WAV sound effect."""
        import tcod.sdl.audio
        audio = tcod.sdl.audio.AudioStream(filepath)
        audio.master_gain = self.sfx_volume
        self.sounds[name] = audio
    
    def play(self, name: str) -> None:
        """Play a sound effect."""
        if name in self.sounds:
            self.sounds[name].seek(0)
            self.sounds[name].queue_audio([])  # restart
```

## Sound Effects Library

Define sounds for common actions:

| Event               | Sound File         | Description           |
|---------------------|--------------------|-----------------------|
| Player attacks      | `sfx_hit.wav`      | Sharp impact sound    |
| Player takes damage  | `sfx_hurt.wav`     | Pain grunt            |
| Pick up item        | `sfx_pickup.wav`   | Quick chime           |
| Use potion          | `sfx_quaff.wav`    | Liquid splash         |
| Cast spell          | `sfx_cast.wav`     | Magical whoosh        |
| Enemy dies          | `sfx_death.wav`    | Fading groan          |
| Door opens          | `sfx_door.wav`     | Creaking wood         |
| Level up            | `sfx_levelup.wav`  | Triumphant fanfare    |
| Game over           | `sfx_gameover.wav` | Somber tone           |

## Music Tracks

Background music sets the atmosphere:

```python
def load_music(self, filepath: str) -> None:
    """Load a music track (OGG or WAV)."""
    self.music = tcod.sdl.audio.AudioStream(filepath)
    self.music.master_gain = self.music_volume
    self.music.loop = True  # Loop indefinitely

def play_music(self) -> None:
    """Start playing the current music track."""
    if self.music:
        self.music.seek(0)
```

Music tracks:
- `music_title.wav` — main menu theme
- `music_dungeon_1.wav` — early dungeon floors
- `music_dungeon_2.wav` — deeper, more dangerous floors
- `music_combat.wav` — intense battle music
- `music_boss.wav` — boss encounter

## Volume Control

```python
def set_sfx_volume(self, volume: float) -> None:
    """Set sound effects volume (0.0 to 1.0)."""
    self.sfx_volume = max(0.0, min(1.0, volume))
    for sound in self.sounds.values():
        sound.master_gain = self.sfx_volume

def set_music_volume(self, volume: float) -> None:
    """Set music volume (0.0 to 1.0)."""
    self.music_volume = max(0.0, min(1.0, volume))
    if self.music:
        self.music.master_gain = self.music_volume
```

## Positional Audio

For atmosphere, sounds can be louder when the source is closer:

```python
def play_at_position(self, name: str, source_x: int, source_y: int, listener_x: int, listener_y: int) -> None:
    """Play a sound with distance-based volume attenuation."""
    distance = ((source_x - listener_x) ** 2 + (source_y - listener_y) ** 2) ** 0.5
    max_distance = 20.0  # tiles
    
    if distance > max_distance:
        return  # Too far to hear
    
    volume_scale = 1.0 - (distance / max_distance)
    # Apply volume and play
```

## Exercises

- Add reverb effects for cave environments
- Implement crossfading between music tracks
- Create a sound test menu for volume adjustment
- Add footstep sounds with different surface types

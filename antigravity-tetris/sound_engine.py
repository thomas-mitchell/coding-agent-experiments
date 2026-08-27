"""
Procedural 8-Bit Chiptune Sound Engine for Tetris (Pygame)
Generates retro sound effects and the iconic Korobeiniki theme music in real time.
Zero external audio files required!
"""

import math
import array
import pygame

SAMPLE_RATE = 44100

# Note Frequencies (in Hz)
NOTE_FREQS = {
    'A2': 110.00, 'B2': 123.47, 'C3': 130.81, 'D3': 146.83, 'E3': 164.81, 'F3': 174.61, 'G#3': 207.65, 'A3': 220.00,
    'B3': 246.94, 'C4': 261.63, 'D4': 293.66, 'E4': 329.63, 'F4': 349.23, 'G4': 392.00, 'G#4': 415.30, 'A4': 440.00,
    'B4': 493.88, 'C5': 523.25, 'D5': 587.33, 'E5': 659.25, 'F5': 698.46, 'G#5': 830.61, 'A5': 880.00, 'B5': 987.77,
    'C6': 1046.50, 'E6': 1318.51, 'REST': 0
}

# Korobeiniki Melody: (Note, Eighth-Note Counts)
KOROBEINIKI_LEAD = [
    ('E5', 2), ('B4', 1), ('C5', 1), ('D5', 2), ('C5', 1), ('B4', 1),
    ('A4', 2), ('A4', 1), ('C5', 1), ('E5', 2), ('D5', 1), ('C5', 1),
    ('B4', 3), ('C5', 1), ('D5', 2), ('E5', 2),
    ('C5', 2), ('A4', 2), ('A4', 2), ('REST', 2),
    ('D5', 3), ('F5', 1), ('A5', 2), ('G#5', 1), ('F5', 1),
    ('E5', 3), ('C5', 1), ('E5', 2), ('D5', 1), ('C5', 1),
    ('B4', 2), ('B4', 1), ('C5', 1), ('D5', 2), ('E5', 2),
    ('C5', 2), ('A4', 2), ('A4', 2), ('REST', 2)
]

# Complementary Bassline: (Note, Eighth-Note Counts)
KOROBEINIKI_BASS = [
    ('E3', 2), ('B2', 2), ('E3', 2), ('G#3', 2),
    ('A2', 2), ('E3', 2), ('A2', 2), ('C3', 2),
    ('G#3', 2), ('E3', 2), ('B2', 2), ('E3', 2),
    ('A2', 2), ('E3', 2), ('A2', 2), ('REST', 2),
    ('D3', 2), ('A2', 2), ('D3', 2), ('F3', 2),
    ('C3', 2), ('G3', 2), ('C3', 2), ('E3', 2),
    ('B2', 2), ('E3', 2), ('G#3', 2), ('E3', 2),
    ('A2', 2), ('E3', 2), ('A2', 2), ('REST', 2)
]


class SoundEngine:
    """Manages audio initialization, procedural SFX, and looping background music."""

    def __init__(self):
        self.enabled = False
        self.muted = False
        self.music_channel = None
        self.music_sound = None
        self.sfx = {}

        try:
            if not pygame.mixer.get_init():
                pygame.mixer.init(frequency=SAMPLE_RATE, size=-16, channels=2, buffer=512)
            pygame.mixer.set_num_channels(16)
            self.music_channel = pygame.mixer.Channel(0)
            self.enabled = True
            self._generate_sfx()
            self._generate_music()
        except Exception:
            # Fallback gracefully if system audio device is unavailable
            self.enabled = False

    def _generate_sfx(self):
        """Synthesize all game sound effects."""
        self.sfx['move'] = self._create_pitch_slide_sfx(start_freq=260, end_freq=220, duration=0.035, vol=0.15)
        self.sfx['rotate'] = self._create_pitch_slide_sfx(start_freq=340, end_freq=520, duration=0.06, vol=0.20)
        self.sfx['drop'] = self._create_pitch_slide_sfx(start_freq=180, end_freq=70, duration=0.065, vol=0.25)
        self.sfx['hard_drop'] = self._create_hard_drop_sfx()
        self.sfx['hold'] = self._create_arpeggio_sfx([400, 600], note_dur=0.04, vol=0.22)
        self.sfx['line_clear'] = self._create_arpeggio_sfx([523, 659, 784, 1046], note_dur=0.05, vol=0.28)
        self.sfx['tetris_clear'] = self._create_arpeggio_sfx([523, 659, 784, 1046, 1318, 1568], note_dur=0.06, vol=0.32)
        self.sfx['level_up'] = self._create_arpeggio_sfx([440, 554, 659, 880], note_dur=0.07, vol=0.30)
        self.sfx['game_over'] = self._create_pitch_slide_sfx(start_freq=450, end_freq=90, duration=0.45, vol=0.30, wave_type='saw')

    def _create_pitch_slide_sfx(self, start_freq: float, end_freq: float, duration: float, vol: float = 0.25, wave_type: str = 'square') -> pygame.mixer.Sound:
        """Create a sound effect that sweeps between two frequencies."""
        n_samples = int(SAMPLE_RATE * duration)
        buf = array.array('h')

        phase = 0.0
        for i in range(n_samples):
            progress = i / n_samples
            freq = start_freq + (end_freq - start_freq) * progress
            phase += freq / SAMPLE_RATE

            if wave_type == 'square':
                val = 1.0 if (phase % 1.0) < 0.5 else -1.0
            elif wave_type == 'saw':
                val = 2.0 * (phase % 1.0) - 1.0
            else:
                val = math.sin(2.0 * math.pi * phase)

            # Decay envelope
            env = 1.0 - progress
            sample = int(val * env * vol * 32767)
            buf.append(sample)
            buf.append(sample)

        return pygame.mixer.Sound(buffer=buf.tobytes())

    def _create_hard_drop_sfx(self) -> pygame.mixer.Sound:
        """Create a punchy hard-drop impact sound."""
        duration = 0.09
        n_samples = int(SAMPLE_RATE * duration)
        buf = array.array('h')

        phase = 0.0
        for i in range(n_samples):
            progress = i / n_samples
            freq = 240.0 * (1.0 - (progress ** 0.5)) + 40.0
            phase += freq / SAMPLE_RATE

            # Blend square wave punch with subtle noise
            sq = 1.0 if (phase % 1.0) < 0.5 else -1.0
            env = (1.0 - progress) ** 1.8
            sample = int(sq * env * 0.32 * 32767)
            buf.append(sample)
            buf.append(sample)

        return pygame.mixer.Sound(buffer=buf.tobytes())

    def _create_arpeggio_sfx(self, frequencies: list[float], note_dur: float = 0.05, vol: float = 0.25) -> pygame.mixer.Sound:
        """Create a bright ascending or descending arpeggio chime."""
        buf = array.array('h')
        samples_per_note = int(SAMPLE_RATE * note_dur)

        for freq in frequencies:
            for i in range(samples_per_note):
                t = i / SAMPLE_RATE
                phase = (t * freq) % 1.0
                # 25% duty cycle pulse wave for classic crisp arcade chime
                val = 1.0 if phase < 0.25 else -1.0
                env = 1.0 - (i / samples_per_note) * 0.8
                sample = int(val * env * vol * 32767)
                buf.append(sample)
                buf.append(sample)

        return pygame.mixer.Sound(buffer=buf.tobytes())

    def _generate_music(self):
        """Synthesize the full polyphonic Korobeiniki 8-bit background track."""
        bpm = 145
        beat_sec = 60.0 / (bpm * 2)  # Duration of an eighth note in seconds
        total_lead_beats = sum(dur for _, dur in KOROBEINIKI_LEAD)
        total_samples = int(total_lead_beats * beat_sec * SAMPLE_RATE)

        # Pre-allocate buffer for stereo track
        mix_lead = [0.0] * total_samples
        mix_bass = [0.0] * total_samples

        # 1. Render Lead Melody Track (Pulse wave)
        current_sample = 0
        for note, dur in KOROBEINIKI_LEAD:
            freq = NOTE_FREQS.get(note, 0)
            note_samples = int(dur * beat_sec * SAMPLE_RATE)
            if freq > 0:
                for i in range(note_samples):
                    if current_sample + i >= total_samples:
                        break
                    t = i / SAMPLE_RATE
                    phase = (t * freq) % 1.0
                    val = 0.6 if phase < 0.5 else -0.6
                    # Envelope with short attack and slight release
                    attack = min(1.0, i / (0.008 * SAMPLE_RATE + 1))
                    decay = min(1.0, (note_samples - i) / (0.03 * SAMPLE_RATE + 1))
                    mix_lead[current_sample + i] = val * attack * decay * 0.16
            current_sample += note_samples

        # 2. Render Bassline Track (Triangle / Low Pulse)
        current_sample = 0
        for note, dur in KOROBEINIKI_BASS:
            freq = NOTE_FREQS.get(note, 0)
            note_samples = int(dur * beat_sec * SAMPLE_RATE)
            if freq > 0:
                for i in range(note_samples):
                    if current_sample + i >= total_samples:
                        break
                    t = i / SAMPLE_RATE
                    # Triangle wave for rich smooth bass
                    phase = (t * freq) % 1.0
                    val = 4.0 * abs(phase - 0.5) - 1.0
                    attack = min(1.0, i / (0.01 * SAMPLE_RATE + 1))
                    decay = min(1.0, (note_samples - i) / (0.04 * SAMPLE_RATE + 1))
                    mix_bass[current_sample + i] = val * attack * decay * 0.14
            current_sample += note_samples

        # 3. Combine into final 16-bit stereo PCM buffer
        buf = array.array('h')
        for i in range(total_samples):
            mixed = mix_lead[i] + mix_bass[i]
            # Soft clamp
            mixed = max(-1.0, min(1.0, mixed))
            sample = int(mixed * 32767)
            buf.append(sample)
            buf.append(sample)

        self.music_sound = pygame.mixer.Sound(buffer=buf.tobytes())

    def play_sfx(self, name: str):
        """Play a registered sound effect."""
        if not self.enabled or self.muted:
            return
        snd = self.sfx.get(name)
        if snd:
            # Find an available SFX channel (channels 1 to 15)
            for ch_idx in range(1, 16):
                ch = pygame.mixer.Channel(ch_idx)
                if not ch.get_busy():
                    ch.play(snd)
                    break

    def start_music(self):
        """Start playing background music on loop."""
        if not self.enabled or self.muted or not self.music_sound:
            return
        if self.music_channel and not self.music_channel.get_busy():
            self.music_channel.play(self.music_sound, loops=-1)

    def pause_music(self):
        """Pause background music."""
        if self.enabled and self.music_channel:
            self.music_channel.pause()

    def unpause_music(self):
        """Unpause background music."""
        if self.enabled and not self.muted and self.music_channel:
            self.music_channel.unpause()

    def toggle_mute(self) -> bool:
        """Toggle mute state for all sound and music. Returns new mute state."""
        self.muted = not self.muted
        if self.muted:
            if self.music_channel:
                self.music_channel.pause()
        else:
            if self.music_channel:
                if self.music_channel.get_busy():
                    self.music_channel.unpause()
                else:
                    self.start_music()
        return self.muted

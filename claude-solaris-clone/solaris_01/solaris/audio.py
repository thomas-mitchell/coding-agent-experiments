"""AUDIO (asm:8365) -- the two-channel sound sequencer.

One channel is serviced per frame, alternating on the frame counter, so each
updates at 30 Hz.  A channel's "program" is a run of bytes in AUDTAB:

    $00        end of sequence.  The SHADOW register is promoted to the
               pointer and cleared -- and that is the whole sound-priority
               scheme: a routine that wants a sound NOW writes CHnPTR, one that
               wants it NEXT writes CHnSHD.
    $01..$04   a WAVEFORM: written straight to AUDC.
    $05        JUMP: continue at the offset in the following byte.
    $10        a REST (volume zero).
    $11..$FF   a NOTE: the whole byte is the frequency, and its high nibble is
               the volume.

Sequences at or after AUDHLP are held for two frames per note, which is what
makes the distress call slower than everything else.

Layered on top, whenever channel 1 is not busy with a real sound, is the ENGINE:
its pitch comes straight from IQWARP (the throttle) and its volume from SPDVOL.
During a hyperwarp the same engine is doubled onto channel 0 one step detuned,
and the beating between them is the sound of the jump.
"""

from . import byte as b
from . import romdata as rom
from .state import (ATRACT, CH0PTR, CH0SHD, IQWARP, PROGST, SHIPST)

AUDTAB = rom.tab("AUDTAB")
SPDVOL = rom.tab("SPDVOL")   # throttle -> engine volume, channel 1
SPDVL1 = rom.tab("SPDVL1")   # ... and channel 0, during a hyperwarp

J = rom.LABELS["AUDTAB"]
AUDHLP = rom.LABELS["AUDHLP"] - J


def audio(mach):
    """AUDIO."""
    m = mach.m
    sound = mach.audio
    x = m[ATRACT] & 0x01                 # alternate channels every frame
    y = m[CH0PTR + x]
    a = AUDTAB[y]

    if a == 0:
        if m[PROGST] & 0x81:
            _volume(sound, x, (m[PROGST] & 0x81) >> 2)   # forced silence
        else:
            # end of sequence: promote the shadow and clear it
            m[CH0PTR + x] = m[CH0SHD + x]
            m[CH0SHD + x] = 0
            return
    else:
        m.inc(CH0PTR + x)
        if a < 0x10:
            if a == 0x05:
                m[CH0PTR + x] = AUDTAB[y + 1]        # JUMP
                return
            _waveform(sound, x, a)
            return
        if a == 0x10:
            _volume(sound, x, 0x10)                  # a rest
        else:
            _frequency(sound, x, a)
            _volume(sound, x, a >> 4)
        # sequences from AUDHLP on hold each note for two frames
        held, _ = b.cmp(y, AUDHLP)
        if held and (m[ATRACT] & 0x1E) != 0:
            m.dec(CH0PTR + x)

    _engine(mach)


def _waveform(sound, x, value):
    if sound is not None:
        sound.channels[x].audc = value & 0x0F


def _frequency(sound, x, value):
    if sound is not None:
        sound.channels[x].audf = value & 0x1F


def _volume(sound, x, value):
    if sound is not None:
        sound.channels[x].audv = value & 0x0F


def _engine(mach):
    """AUDIO9: the engine drone, layered onto channel 1 whenever nothing else
    is using it."""
    m = mach.m
    sound = mach.audio
    busy, _ = b.cmp(m[CH1PTR_ADDR], 0x02)
    if busy:
        return
    y = m[IQWARP]
    if not (y & 0x80):
        return                           # not under thrust

    a = y
    high, _ = b.cmp(a, 0xF2)
    if not high:
        a, carry = b.adc(a, 0x3A, c=False)   # scale into the engine pitch range
        a, _ = b.ror(a, carry)
    x = a
    _frequency(sound, 1, a)

    if m[SHIPST] == 0x20 and m[CH0PTR] < 0x02:
        # during a hyperwarp the engine is doubled onto channel 0, one step
        # detuned -- the beating between them IS the jump sound
        _frequency(sound, 0, (x - 1) & 0xFF)
        _waveform(sound, 0, 0x08)
        _volume(sound, 0, SPDVL1[y - 0xD8] >> 4)

    _waveform(sound, 1, 0x08)
    vol = SPDVOL[y - 0xD8] >> 4
    if mach.porta != 0xFF:
        vol += 1                         # moving the stick adds one
    _volume(sound, 1, vol)


CH1PTR_ADDR = 0xE0

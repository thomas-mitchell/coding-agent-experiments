"""The machine: RAM, the TIA bits the game can observe, and the console inputs.

Everything the ported routines need that is not a zero-page byte lives here --
the collision latches they read back out of the display, the joystick and
console switches, and the two stand-ins for hardware the port does not model
(the RIOT interval timer, which seeds the PRNG, and the audio synth).
"""

from .state import Mem
from .tia import Collisions

# PORTA joystick bits, ACTIVE LOW: $FF is a centred stick (asm:7741).
JOY_RIGHT = 0x80
JOY_LEFT = 0x40
JOY_DOWN = 0x20
JOY_UP = 0x10

# PORTB console switches, also active low.  Solaris reads only bit 0.
SW_RESET = 0x01


class Machine:
    def __init__(self):
        self.m = Mem()
        self.tia = Collisions()

        # inputs, in the form the game reads them
        self.porta = 0xFF        # joystick, active low
        self.portb = 0xFF        # console switches, active low
        self.trig0 = 0x80        # fire button, bit 7 set = NOT pressed
        self.trig1 = 0x80        # second controller's button: the star chart

        # `LDY RTIMER ;FOR RANDOM` (asm:4855) samples the RIOT interval timer
        # part-way through the frame, so its value depends on how long the
        # previous frame's work took -- genuine entropy on hardware.  The port
        # does not cycle-count, so this is a deterministic stand-in that still
        # varies every frame.  See mover.RNDPAGE for the other half of the PRNG.
        self.rtimer = 0x00

        self.audio = None        # attached by the audio module
        self.frame_count = 0

    def tick_timer(self):
        """Advance the RIOT stand-in once per frame."""
        self.rtimer = (self.rtimer * 5 + 0x3B) & 0xFF

    # -- input helpers -------------------------------------------------------
    def set_joystick(self, up=False, down=False, left=False, right=False):
        v = 0xFF
        if up:
            v &= ~JOY_UP
        if down:
            v &= ~JOY_DOWN
        if left:
            v &= ~JOY_LEFT
        if right:
            v &= ~JOY_RIGHT
        self.porta = v & 0xFF

    def set_fire(self, pressed):
        self.trig0 = 0x00 if pressed else 0x80

    def set_chart_button(self, pressed):
        self.trig1 = 0x00 if pressed else 0x80

    def set_reset_switch(self, pressed):
        self.portb = (self.portb & ~SW_RESET) if pressed else (self.portb | SW_RESET)

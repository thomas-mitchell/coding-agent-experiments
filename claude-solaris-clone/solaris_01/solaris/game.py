"""MAIN (asm:4845) -- one NTSC frame, and the order everything happens in.

Collapsing the bank-switch trampolines away, a frame is:

    MOVER       integrate every object; reseed the PRNG        (or CHTSRV)
    HYPSRV      cache the zoom values; drive the warp tunnel
    GRAPH       animation frames, off-screen culling, collision X
    PLNSRV      surface parameters, when we are on one
    CLOSE       vertical overlap fix-ups and swap requests
    MESSRV      build the score digits
    SHPSRV      your ship's graphic and position
    PHOTON      fire and advance your torpedoes
    <kernel>    the picture -- and, with it, the collision latches
    MAIN2       overscan: flame colour, difficulty tier
    TIMSRV      console switches, death timer, takeoff/landing
    HITSRV      what hit what
    JOYSTK      the stick, steering, throttle
    AUDIO       the two sound sequencers
    SMARTS      the star chart and the strategic AI
    BRAIN       per-object AI, one object per frame
    NEWOBJ      the wave-spawn VM, when BRAIN finds an empty slot

SHPSRV really runs at the tail of the *previous* frame's kernel, but since
nothing between reads its output that is the same as running it here, just
before the picture it feeds.

The CRAZY table conversions MAIN does (asm:4878, 4900) are pure horizontal
positioning plumbing -- `x = pixel` -- so they are dropped, and the renderer
uses the raw coordinates.  Note that dropping them also keeps HHITP0 intact for
the kernel, which overwrites it with collision latches as it draws.
"""

from . import audio as audio_mod
from . import brain as brain_mod
from . import close as close_mod
from . import graph as graph_mod
from . import hitsrv as hitsrv_mod
from . import hyper as hyper_mod
from . import joystick as joystick_mod
from . import mover as mover_mod
from . import newobj as newobj_mod
from . import romdata as rom
from . import score as score_mod
from . import smarts as smarts_mod
from . import surface as surface_mod
from . import timsrv as timsrv_mod
from .machine import Machine
from .render import chart as chart_render
from .render import space as space_render
from .render import status as status_render
from .render import surface as surface_render
from .render import warp as warp_render
from .render.frame import Frame
from .state import (ATRACT, HCOLP1, NEWAVE, NEWLEV, PROGST, PROGST_CHART,
                    PROGST_HYPER, PROGST_PROTECT, PROGST_SURFACE)

DORT11 = rom.tab("DORT11")


class Game:
    def __init__(self):
        self.mach = Machine()
        self.frame = Frame(self.mach.tia)
        timsrv_mod.init(self.mach)

    def step(self):
        """Run one frame and leave the picture in `self.frame`."""
        mach = self.mach
        m = mach.m
        mach.tick_timer()

        # --- vertical blank: think -----------------------------------------
        if m[PROGST] & 0xB3:
            mover_mod.mover(mach)        # the PRNG still gets stirred
            smarts_mod.chtsrv(mach)
        else:
            mover_mod.mover(mach)
        if hyper_mod.hypsrv(mach):
            if m[PROGST] & PROGST_SURFACE:
                surface_mod.plnsrv(mach)
            graph_mod.graph(mach)
        close_mod.close(mach)
        score_mod.messrv(mach)
        joystick_mod.shpsrv(mach)
        joystick_mod.photon(mach)

        # --- the picture ---------------------------------------------------
        self._draw()

        # --- overscan: housekeeping ----------------------------------------
        m[HCOLP1] = 0x00 if (m[ATRACT] & 0x03) == 0 else 0x12   # engine flame
        m[NEWAVE] = DORT11[m[NEWLEV]] & 0x07                    # difficulty tier

        if not timsrv_mod.timsrv(mach):
            return
        hitsrv_mod.hitsrv(mach)
        joystick_mod.joystk(mach)
        audio_mod.audio(mach)
        if smarts_mod.smarts(mach):
            brain_mod.brain(mach, newobj_mod.newobj)
        mach.frame_count += 1

    def _draw(self):
        m = self.mach.m
        frame = self.frame

        if m[PROGST] & PROGST_PROTECT:
            # SCREEN PROTECT: slowly shifting colour bars instead of a picture,
            # so an idle machine does not burn a CRT
            bars = ((m[ATRACT] & 0xC0) ^ m[ATRACT + 1]) & 0xC7
            frame.clear(bars)
            return

        status_render.draw_score(self.mach, frame)
        if m[PROGST] & PROGST_CHART:
            chart_render.draw(self.mach, frame)
        elif m[PROGST] & PROGST_HYPER:
            warp_render.draw(self.mach, frame)
        elif m[PROGST] & PROGST_SURFACE:
            surface_render.draw(self.mach, frame)
        else:
            space_render.draw(self.mach, frame)
        status_render.draw_scanner(self.mach, frame)

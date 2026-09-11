"""End-to-end checks: the frame loop runs, and it runs the same way every time."""

import hashlib

from solaris import score, timsrv
from solaris.game import Game
from solaris.machine import Machine
from solaris.state import (CENTER, CURSOR, FUEL, GAMEST, HGRAP0, HHORP0, JMPTIM,
                           LIVES, NEWLEV, PBLK, PROGST, PROGST_POWERUP, SCORE,
                           ZPOSP0, ZPOSP1)


def test_power_up_state():
    """INIT's own values, from asm:4729-4818."""
    g = Game()
    m = g.mach.m
    assert m[PROGST] == PROGST_POWERUP        # the title screen
    assert m[LIVES] == 3                      # four ships, one of them in play
    assert m[FUEL] == 0xFF
    assert m[CENTER] == 0x50
    assert m[CURSOR] == 0x15                  # your home sector
    # INIT2 writes JMPTIM = $60, but DOOR23 may immediately reset it to $05
    # depending on a carry that nothing initialises before the reset vector --
    # so both values are legitimate here.  Same on hardware.
    assert m[JMPTIM] in (0x60, 0x05)
    assert m[GAMEST] == 0x40                  # you begin on YOUR planet
    assert m[NEWLEV] == 0
    assert m[ZPOSP1] == 0x80 and m[ZPOSP1 + 1] == 0x80   # both photons off
    # the four slots start as craters at INTAB1 / INTAB2
    assert [m[ZPOSP0 + i] for i in range(4)] == [0x05, 0x14, 0x27, 0x48]
    assert [m[HHORP0 + i] for i in range(4)] == [0x78, 0x28, 0x68, 0x3B]
    assert all(m[HGRAP0 + i] == 0x40 for i in range(4))


def test_a_frame_runs():
    g = Game()
    g.step()
    assert len(g.frame.px) == 160 * 192


def test_the_game_is_deterministic():
    """Two runs from the same inputs must produce the same state."""
    def run():
        g = Game()
        for i in range(240):
            g.mach.set_fire(i in (30, 31, 90, 91))
            g.mach.set_joystick(up=(i > 120), right=(i % 37 == 0))
            g.step()
        return bytes(g.mach.m.ram), hashlib.sha256(bytes(g.frame.px)).hexdigest()

    assert run() == run()


def test_a_long_run_stays_healthy():
    """A thousand frames of play: no exception, and the invariants hold."""
    g = Game()
    m = g.mach.m
    for i in range(1000):
        g.mach.set_fire(i in (30, 31, 90, 91) or i % 53 == 0)
        g.mach.set_joystick(up=(i > 120), left=(i % 91 < 10))
        g.step()
        for k in range(4):
            assert m[HGRAP0 + k] == PBLK or 0 <= m[HGRAP0 + k] <= 0xFF
        assert 0x2D <= m[CENTER] < 0x74       # the camera clamp
        assert m[LIVES] <= 5                  # INL caps extra ships at five


def test_takeoff_reaches_space():
    """Title -> fire -> your planet -> fire -> throttle up -> in space."""
    g = Game()
    m = g.mach.m
    for i in range(700):
        g.mach.set_fire(i in (30, 31, 90, 91))
        g.mach.set_joystick(up=(i > 120))
        g.step()
        if m[PROGST] == 0x00:
            break
    assert m[PROGST] == 0x00, f"still on a surface: PROGST {m[PROGST]:02X}"
    assert m[SHIPST_ADDR] == 0x00


SHIPST_ADDR = 0xD3


def test_score_is_bcd_and_shown_times_ten():
    """Every HITAB1 value is a tenth of what the player sees, because MESSRV
    hard-codes the last digit to '0' (asm:4650)."""
    mach = Machine()
    score.addscr(mach, 0x30)
    assert mach.m[SCORE] == 0x30              # displayed as 300
    score.addscr(mach, 0x80)
    assert mach.m[SCORE] == 0x10              # 30 + 80 = 110 in BCD
    assert mach.m[SCORE + 1] == 0x01
    # the 8000-point planet bonus goes into the second byte
    score.addsc3(mach, 0x08, 1)
    assert mach.m[SCORE + 1] == 0x09


def test_fuel_clamps_at_zero_but_not_at_the_top():
    mach = Machine()
    mach.m[FUEL] = 0x08
    score.addfl2(mach)                        # -15
    assert mach.m[FUEL] == 0x00
    mach.m[FUEL] = 0x20
    score.addfl2(mach)
    assert mach.m[FUEL] == 0x11


def test_losing_your_last_life_ends_the_game():
    mach = Machine()
    timsrv.init(mach)
    mach.m[LIVES] = 1
    timsrv.init3(mach)
    assert mach.m[PROGST] == 0xCA             # the game-over state

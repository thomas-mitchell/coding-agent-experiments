# Solaris

A 1:1 Python port of *Solaris* (Atari 2600, 1986, Douglas Neubauer), built from
the annotated disassembly in `../solaris_annotated.asm`.

No features are added and none are removed. Where the original had a bug, this
has the same bug, with a comment pointing at the line it came from.

## Running it

```
pip install -r requirements.txt
python main.py
```

| key | |
| --- | --- |
| arrows / WASD | steer, and push up to open the throttle |
| space | fire |
| tab | star chart (the 2600's second controller button) |
| F1 | Game Reset |
| F3 (hold) | colour / black-and-white switch |
| escape | quit |

```
python main.py --scale 2                          a bigger window
python main.py --mute                             no sound
python main.py --debug                            print the game state each second
python main.py --headless --frames 3600           run without a window
python main.py --headless --frames 300 --screenshot shot.png
pytest                                            the test suite
```

## Playing it

Power on to the title screen and press fire to start. You begin standing on your
own planet, frozen; press fire again to release, then hold up to open the
throttle. Past `$D9` on the throttle the hyperwarp tunnel opens and you jump.

Press tab for the star chart, move the cursor to a neighbouring sector, and
press fire to jump there. What you find is decided entirely by which enemy fleet
happens to be sitting on that cell — see `DORTB1` / `DORTB2` in `smarts.py`.

Fuel drains on every other shot and on every hit; land on your own planet's pad
to refill, which also repairs accumulated damage. Clearing an enemy planet is
worth an extra ship, up to five.

## How it is built

```
tools/extract_tables.py   parses the assembly into solaris/romdata.py
solaris/
  romdata.py              GENERATED: every .byte table in the ROM
  byte.py                 6502 arithmetic: adc/sbc/rol/ror, BCD, carry as an argument
  state.py                the 128 bytes of zero page, addressed as the assembly does
  machine.py              RAM + the TIA bits the game reads back + the inputs
  vmath.py                DIVIDE, PREHLP, ZHELP, POSTHP -- the whole motion model
  mover.py graph.py close.py    the per-frame object pipeline
  brain.py                per-object AI, one object per frame
  newobj.py               the wave-spawn bytecode VM
  joystick.py             JOYSTK, SHPSRV, PHOTON
  timsrv.py               INIT and the between-frames state machine
  smarts.py               the star chart, the enemy fleets, DOOR, FINDV
  hitsrv.py score.py      collisions, scoring, fuel
  hyper.py surface.py     hyperwarp and surface setup
  audio.py tia.py         the sound sequencer and the TIA itself
  render/                 the four display kernels, as pictures rather than beam timing
  game.py                 MAIN: the frame loop
```

Three decisions are worth knowing about.

**The tables are extracted, not transcribed.** There are about 1,025 `.byte`
directives in the disassembly. `tools/extract_tables.py` parses them into
`solaris/romdata.py`, keeping `<LABEL` entries symbolic so a dispatch table
becomes a list of handler *names* rather than meaningless address bytes. Rerun it
after editing the assembly; the generated file is committed so the game runs
without it.

**The state is one byte array, not named attributes.** Solaris overlaps its RAM
deliberately, and the game depends on the overlaps: `STARS+1` *is* `NEWAVE`,
`HGRAP1+3` *is* the byte the object loops reach at index 0, `CHTBLK` overlays the
velocity arrays, `HHITP0` means two different things at two points in the frame.
Un-aliasing all that would be a rewrite, so `state.py` keeps one array and the
ported code addresses it by the assembly's own constants: `m[HGRAP0 - 1 + x]`
reads as `LDA HGRAP0-1,X`, which makes it checkable line by line against the
source.

**The display feeds the collision detection.** Enemy-versus-player collision in
Solaris is genuine per-pixel TIA overlap: the kernel stores `CXPPMM` into each
object's `HHITP0` as it finishes drawing it, and `HITSRV` reads those bytes back.
So the renderer is not decoration -- it produces pixels *and* collision latches,
and it draws the objects in the same one-at-a-time chain the kernel used.

## Fidelity

Reproduced: the packed fixed-point velocities and their tables, the four-frame AI
round robin, the vertical sort that made five objects share one hardware player,
the spawn VM and all its scripts, the star chart's route-replay model, BCD
scoring, the TIA's polynomial-counter sound, and the NTSC palette.

Two things cannot be byte-exact without a ROM image, because they read the
assembled *code* as data:

* `MOVER`'s PRNG mixes in a byte of ROM at `$FE00,Y`. The port substitutes 256
  bytes of real bank-4 data (`mover.RNDPAGE`); the mixing around it is exact.
* the RIOT interval timer value `MAIN` samples to seed that PRNG depends on how
  long the previous frame's work took. `Machine.rtimer` is a deterministic
  stand-in, which also makes the game reproducible frame for frame.

Horizontal positions that the ROM encodes as RESPx strobe timing rather than as a
number (the score digits, the scanner strip's origins) are placed by hand; where
the assembly gives a spacing in a table -- `XTABLE`'s two-pixel scanner steps, for
instance -- that spacing is used exactly.

See `NOTES.md` for the porting notes, and the module docstrings for the details.

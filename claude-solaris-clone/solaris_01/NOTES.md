# Porting notes

Things that were not obvious from the assembly header, or that took real work to
pin down. Line numbers are into `../solaris_annotated.asm`.

## The sprite storage convention

Sprites are stored **bottom row first**, and the label sits **after** its block:

```asm
       .byte $00,$00,$24,$66,$FF,$18,$3C,$5E,$0F,$5E,$3C,$18
RPL8   .byte $00,$00,$24,$66,$FF,$18,$3C,$66,$DB,$66,$3C,$18
RPL7   ...
```

so the line *labelled* `RPL8` actually holds `RPL7`'s bitmap. The top row is at
`RPL8 - 1` and successive rows walk backwards to the `$00` pad, which is what the
kernel's `BEQ` sees as "this object is finished".

Working that out from the kernel rather than by eye: `MTABL1[type]` is
`<LABEL+1`, `DIS150` waits for `Y < objY` and `DIS102` then `DEY`s once more
before its first fetch, so the first address is `MTABL1[type] - 2 == LABEL - 1`.
Your ship is the exception -- `JOYTB9` points at `<YGRn+2`, two bytes further on,
so its top row lands one scanline lower.

Colour ramps and HMOVE delta streams are read exactly the same way, so row *k* of
all three streams is at `base - k`.

## There are two sprite indexes, not one

`MTABL1..MTABL4` (96 entries, bank 2) is the SPACE art. `PTABL1..PTABL4` (72
entries, bank 4) is the SURFACE art, indexed by the same class numbers. They are
completely different pictures: class `$20` is the planet killer in space and the
landing zone on a surface.

`MTABL4` is a per-scanline HMOVE delta stream, which is how craters, rings and
explosions get wider than the eight pixels a player gives you. `PTABL4` is not --
it is a NUSIZ0 value, so surface objects get their width directly.

## `HGRAP1+3` is not a pad byte

The assembly header calls index 0 of the `FOO-1,X` object loops a "pad byte" whose
writes are harmless no-ops. It is not: `HGRAP1+3` *is* that byte, and it is the
shared extra object slot -- Saturn's rings, a big moon, or the hyperwarp graphic.
`MOVER` integrating "slot 0" is exactly how that object moves, and `MOVER3` skips
it on a surface (`DEX / BNE MOVER1`, "NO P1+3") because there is no such object
down there.

## Collision detection is the display

`DIS400` (asm:6772), and its surface and hyperwarp twins at 8877 and 9279:

```asm
       TSX
       LDA    MIPL
       STA    HHITP0+1,X
       STA    HITCLR
```

`MIPL` is `CXPPMM`, whose bit 7 is player0-touched-player1. As each object
finishes drawing, the accumulated latch is stored into the *previous* object's
`HHITP0` and cleared. `HITSRV` then tests `HHITP0[i]` for negative.

So `HHITP0` has two lifetimes per frame: a collision X that `GRAPH` computes, and
then TIA latch bits that the kernel writes over it. The kernel reads the X back
for positioning *before* the next object's setup clobbers that byte, which is why
the order works. `HITSRV`'s own `LDA MIPL / STA HHITP0` picks up the last
object's latch, which nothing else would have stored.

The practical consequence: the renderer cannot be skipped or reordered. It draws
the P0 objects in the same one-at-a-time chain, from `PNTRP1` downward, and
latches at the same points.

## `CRAZY` is plumbing, but its absence has a consequence

`CRAZY[x]` turns a pixel X into RESPx coarse/fine positioning data, so in Python
`x = pixel` and the table goes away. But `MAIN` writes the converted values back
over `HHORP1` and `HHITP0`, so dropping the conversion also *keeps those bytes
intact* -- which is what lets the kernel use `HHITP0` for the collision latch.

One consequence is load-bearing for the picture: the ship's conversion is
`CRAZY-$2D,Y`, which would put it in the left 45% of the screen. It cannot be,
because collision detection needs the ship's pixels to line up with an object at
`HHORP0 == CENTER`. The `-$2D` is a strobe-timing offset in that particular
kernel fragment, not a coordinate, so the port uses `HHORP1` directly.

## Carry is an argument

A bare `SEC` or `CLC` before a `JSR` is passing a parameter. `POSTHP`'s carry
picks the response curve -- clear is "snap to the target", set is "move one
notch" -- and `BRAIN` calls it twice in a row to get double acceleration.

Carry also survives instructions that look like they would clear it. In `JOYSTK`:

```asm
JOYS32 INC    IQWARP
       BCC    JOYS30
       DEC    IQWARP
JOYS31 DEC    IQWARP
```

`INC` does not touch the carry, so the branch is testing a `CMP` several
instructions earlier -- and a set carry turns a speed-up into a net *slow-down*.
That is what makes the throttle settle at `$F9` and back off above `$FC`. Written
as a clamp it would feel wrong.

## Low-byte comparisons need real addresses

A few tests compare against a label's low byte (`CMP #<[STARTB+2]`). Data indices
are not addresses, so the extractor tracks the real assembly address wherever an
`ORG`/`RORG` is followed by a contiguous run of `.byte` -- 218 of the 428 labels.
`STARTB` comes out at `$F398`, which is what makes the starfield scroll over the
right range.

That also settles a smaller question: `MTABL4` entries at or past `KDL8`
(`$F31C`) select double-width drawing, and the ones before it (`RDL1`, and plain
zero) do not.

## The starfield is other tables

`(STARS),Y` reads across the page at `$F300`, which is the `NULL`/`RDL1`/`KDL`/
`XDL` delta tables. The star "pattern" is literally those bytes reused, exactly
as the `STARTB` comment says. `STARS` scrolls over `$00..$99` -- 154 values, one
per play scanline.

## Bugs that shipped, and are kept

* `NEWB24` (asm:2224) reads `HVERP0-2,X` where `HVERP0+0,X` was surely meant.
  Doug's own comment says "NO LOAD P0+0 BUG".
* `MOVER`'s Z clamp skips its store entirely for an object already flagged off
  screen, leaving a stale Z. Marked "H,V OOPS!".
* `HITSRV` folds `HOLDM0` into the vertical hit band on a surface, where `CLOSE`
  never defined it: "FROM CLOSE!, NOT DEFINED FOR PLN/TRN" (asm:6054).
* `HITS45` is reached from the darter branch with the carry left set by
  `CPY #$10`, so a darter hit takes the "hit moon" path -- damage, never death,
  despite the comment calling it lethal.
* `HITSR7`'s fatality roll compares against `ZPOSP0+1` absolute, not `ZPOSP0,X`,
  so it is always slot 2's distance that decides.
* At power-up nothing initialises the carry before `DOOR23`'s `SBC DORT11,Y`, so
  `JMPTIM` ends as either `$60` or `$05`. The test allows both.

## What could not be reproduced exactly

Two reads treat the assembled code as data, and there is no ROM image here:

* `ADC $FE00,Y` in `MOVER`'s PRNG.
* `LDA NEWOB3,Y` in the spawner's random Y.

Both use `mover.RNDPAGE`, 256 bytes of real bank-4 data, and the arithmetic
around them is exact. The assembly's own note is "any decent PRNG substitutes".

`BRAN21` also bails out of steering when the frame timer is nearly expired. The
port has no beam to race, so it always steers -- which is what the hardware does
on all but the tightest frames.

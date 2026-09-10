;===============================================================================
;  S O L A R I S   (Atari 2600, 1986)  --  Douglas Neubauer
;  ANNOTATED COPY.  The pristine original lives in reference/solaris.asm.
;===============================================================================
;
;  WHO THIS IS FOR
;  ---------------
;  These comments are written for a coding agent that is going to reimplement
;  Solaris in Python.  They try to answer "what does this mean" rather than
;  "what does this opcode do".  Anything that is a pure Atari-2600 hardware
;  chore (cycle counting, HMOVE, WSYNC, bank switching) is labelled PLUMBING
;  and can be dropped by the port; anything carrying game meaning is spelled
;  out in Python terms.
;
;  Every comment in this file was ADDED.  No code byte was changed: strip all
;  comments from this file and from reference/solaris.asm and the two are
;  byte-for-byte identical.
;
;
;-------------------------------------------------------------------------------
;  1.  THE ONE THING TO UNDERSTAND FIRST: THE OBJECT ARRAY
;-------------------------------------------------------------------------------
;
;  Solaris keeps EIGHT display objects.  They are stored as eight parallel
;  arrays in zero page, and each array is laid out as
;
;        <P1 part: 3 bytes> <1 pad byte> <P0 part: 4 bytes>
;
;  so the eight entries of one field are contiguous in memory.  Example:
;
;        HGRAP1+0  HGRAP1+1  HGRAP1+2   (pad)   HGRAP0+0 .. HGRAP0+3
;
;  Almost all game code walks the array with index register X in 0..4 and
;  addresses it as   HGRAP0-1,X   (or -2,X for "the previous one").  Because
;  HGRAP0-1 IS the pad byte, X=0 lands on the pad and X=1..4 lands on
;  HGRAP0+0..+3.  Several routines deliberately let X reach 0 so that a write
;  becomes a harmless no-op instead of needing a branch.
;
;  Read every  FOO-1,X  as  obj[X].foo.
;
;  Slot roles (indices as used by the -1,X convention):
;
;     index 0        pad / scratch.  Writes here are intentional no-ops.
;     index 1..4     the four enemy/scenery slots (HGRAP0+0..+3): fighters,
;                    pirates, moons, craters, the landing zone, the man,
;                    explosions, enemy photons -- whatever the wave spawner
;                    decided to put there.
;     HGRAP1+0       YOUR SHIP.
;     HGRAP1+1       your photon torpedo, near.
;     HGRAP1+2       your photon torpedo, far (the transferred shot).
;     HGRAP1+3       shared extra slot: Saturn rings, a big moon, or the
;                    hyperwarp graphic, depending on mode.
;
;  Per-object fields (all one byte, all parallel arrays):
;
;     HGRAP0-1,X   type/graphic id.  $E0 (PBLK) means EMPTY SLOT.  See sec. 4.
;     HHORP0-1,X   screen X, 0..$9F (160 pixels wide).
;     HVERP0-1,X   screen Y.  BOTTOM OF SCREEN IS 0 and Y counts UP; TOPSCN
;                  ($99) is the top.  Invert this for a Python renderer.
;     ZPOSP0-1,X   depth.  0 = in your face, larger = further away.
;                  ZVIS ($78) is the far visibility cutoff.
;     XDELP0-1,X   packed horizontal velocity      (see sec. 3)
;     YDELP0-1,X   packed vertical velocity
;     ZDELP0-1,X   packed depth velocity (closing speed)
;     IQPATH-1,X   AI state.  Low nibble = which flight path, high nibble = a
;                  phase counter that advances that path.
;     HHITP0-1,X   scratch: X position recomputed for collision, filled by
;                  GRAPH and consumed by HITSRV.
;
;  Python shape:
;
;     class Obj: type, x, y, z, dx, dy, dz, path, hitx
;     objs = [Obj() for _ in range(8)]      # index 0 is the scratch slot
;
;
;-------------------------------------------------------------------------------
;  2.  FRAME LOOP
;-------------------------------------------------------------------------------
;
;  One NTSC frame = VSYNC, ~37 lines of vertical blank, 192 lines of picture,
;  ~30 lines of overscan.  Solaris thinks during the blank periods.  The order
;  below IS the Python main loop; everything else is a subroutine of it.
;
;     MAIN                  start of frame, VSYNC, position the star missile
;       MOVER               integrate every object position from its packed
;                           velocity; also reseed RANDOM            (bank 4)
;       GRAPH               pick each object animation frame, cull the ones
;                           that went off screen, precompute collision X
;       CLOSE               vertical overlap fix-ups and swap requests
;       MESSRV              build the score digits for the score kernel
;       <screen kernel>     one of
;                             SCRKER + DISPLY   normal space view    (bank 2)
;                             SCRKER + PLNSRV   planet / trench      (bank 4)
;                             SCRKER + HYPER    hyperwarp tunnel     (bank 4)
;                             CHART  + SCANDS   star chart           (bank 3)
;       MAIN2               overscan begins
;       TIMSRV              console switches, death timer, takeoff/landing
;                           state machine, ATRACT frame counter
;       JOYSTK              read the stick, steer the ship, set throttle
;       AUDIO               advance the two sound sequencers
;       SMARTS              star-chart cursor logic and strategic AI
;       BRAIN               per-object AI (one object per frame)
;       NEWOBJ              wave-spawn bytecode VM: fill empty slots
;     back to MAIN
;
;  The real call graph is obscured by bank switching (sec. 8); the list above
;  is what it collapses to once the trampolines are removed.
;
;
;-------------------------------------------------------------------------------
;  3.  PACKED VELOCITIES  (the trickiest encoding in the game)
;-------------------------------------------------------------------------------
;
;  XDEL / YDEL / ZDEL are NOT plain signed velocities.  Each byte is
;
;        bits 7..5   a 3-bit sub-pixel accumulator (fractional position)
;        bits 4..0   a 5-bit signed speed CODE (not a speed)
;
;  The speed code decodes through tables:
;
;     code $00..$0F -> positive, magnitude BRNTB5[code]
;                      = 0,1,2,3,4,5,6,7,8,$0C,$10,$14,$18,$1C,$20,$24
;     code $10..$1F -> negative, magnitude BRNTB5[code EOR $1F]
;
;  MOVER integrates without ever unpacking.  MOVTB4..MOVTB7 are 32-entry
;  tables indexed by (delta AND $1F) giving (accumulator increment, position
;  increment), so one lookup and two ADCs advance an object one frame.
;
;  Steering is a three-stage pipeline used all over BRAIN:
;
;     DIVIDE   perspective divide.  A = signed screen offset from centre,
;              TEMP4 = zoomed Z, TEMP5 = |ZDEL|, PNTR1 = sign.  Returns the
;              apparent drift this object gets purely from the camera moving.
;              Python: offset * closing_speed / distance.
;
;     PREHLP   "how fast do I want to be going": clamp the desired delta to
;              TEMP7 (a per-path speed limit) and PACK it into a 5-bit code
;              left in TEMP10.  ZHELP is the same thing for the Z axis and
;              additionally applies the automatic slow-down near the camera.
;
;     POSTHP   "slew towards it": merge the desired code in TEMP10 with the
;              object current delta, moving at most one step per frame, while
;              preserving the accumulator bits.  Carry on entry picks the
;              response curve: C=0 is type 1 (gentle), C=1 is type 2.  BRAIN
;              calls POSTHP twice in a row to get type 2 acceleration.
;              POSTH1 is just "CLC then POSTHP".
;
;  Python equivalent of the whole pipeline:
;
;     desired = clamp(target_speed, -limit, limit)
;     current += sign(desired - current) * step
;
;
;-------------------------------------------------------------------------------
;  4.  THE OBJECT TYPE / GRAPHIC BYTE
;-------------------------------------------------------------------------------
;
;  HGRAP0-1,X holds one byte that is BOTH the object identity and its current
;  animation frame:
;
;     bit 7      1 = off screen / inactive this frame.  The whole byte $E0
;                (PBLK = $60+$80) means EMPTY SLOT and is compared against
;                constantly:  CMP #PBLK / BEQ empty.
;     bits 6..3  the object CLASS.  Code extracts it with AND #$78 then LSR
;                LSR to index a dispatch table.
;     bits 2..0  animation frame within the class.
;
;  Two big tables are indexed by the low 7 bits of this byte:
;
;     BRNTB6   object size and flags, SPACE mode.
;              low 6 bits ($3F) = object height in scanlines;
;              bits 7 and 6 are per-class flags consumed by CLOSE and BRAIN
;              (bit 7 roughly "extends downward / needs special swap
;              handling", bit 6 roughly "is a solid target").
;     BRNTB9   the same table for PLANET / TRENCH mode.
;
;  Dispatch tables indexed by class:
;
;     BRNTB4   low byte of the AI handler in BRAIN.
;     GRATB6   low byte of the animation handler in GRAPH  (GRATB7 supplies
;              the ninth address bit -- see the note at GRAPH7).
;
;  A Python port should precompute TYPE_INFO[graphic_byte] = (height, flags,
;  sprite, palette) by walking BRNTB6/BRNTB9 plus MTABL1..MTABL4 (sec. 7).
;
;
;-------------------------------------------------------------------------------
;  5.  PROGST -- THE GAME MODE BITS
;-------------------------------------------------------------------------------
;
;  PROGST is read on nearly every frame.  Meanings deduced from all its uses:
;
;     bit 0  $01   screen-protect / attract dimming.  Set when the ATRACT
;                  frame counter wraps; makes MAIN paint colour bars.
;     bit 1  $02   "an event just ended" latch: you died, you finished
;                  refuelling, a pause expired.  TIMSRV consumes and clears it.
;     bit 3  $08   surface sub-mode.  With bit 6 set, 0 = trench, 1 = planet
;                  (PLNSRV does AND #$08 / BEQ TRNSRV).
;     bit 4  $10   HYPERWARP screen is up.
;     bit 5  $20   STAR CHART screen is up.  SMARTS toggles it with EOR #$20.
;     bit 6  $40   SURFACE MODE: on a planet or in the trench.  The famous one.
;                  Tested with  BIT PROGST / BVS ...  because V takes bit 6.
;                  Several loops carry a warning not to clobber V, because they
;                  rely on this test staying valid for the whole loop.
;                  PROGST == $40 exactly means TRENCH.
;     bit 7  $80   game over / power-up / attract.  $CE is the power-up state,
;                  $CA is the game-over state.
;
;  Python: an enum for the active screen (SPACE / CHART / HYPER / SURFACE)
;  plus a small set of booleans.
;
;
;-------------------------------------------------------------------------------
;  6.  GLOBALS WORTH KNOWING BEFORE READING ANY ROUTINE
;-------------------------------------------------------------------------------
;
;     RANDOM    2 bytes.  Not an LFSR: MOVER stirs it each frame by adding
;               GAMTIM, ATRACT, itself, and a byte read out of ROM at $FE00,Y.
;               Any decent PRNG substitutes.
;     ATRACT    2-byte free-running FRAME COUNTER and the game master phase
;               clock.  LDA ATRACT / AND #$0F / BNE skip means "do this once
;               every 16 frames".  AND #$03 gates the four-way round robin
;               that makes BRAIN service one object per frame.
;     CENTER    the horizontal camera position, clamped to $2D..$74.  Objects
;               are positioned relative to it; steering moves CENTER.
;     IQWARP    THROTTLE / warp speed, treated as SIGNED.  $80..$FF is forward
;               thrust with $FF fastest.  It gates nearly every speed decision
;               in the game.  JOYSTK increments and decrements it.
;     GAMEST    mission state bits.  bit 6 = this is YOUR (friendly) planet,
;               bit 7 = objects are in wander mode, low bits = jump quality
;               and trench door state.
;     SHIPST    ship state machine.  $20 = hyperwarp queued, $30 = jump again
;               (wormhole), bit 7 = takeoff in progress, bit 4 = takeoff was
;               from a planet, bit 6 = the planet is blowing up.
;     ONESHT    edge-detect latches: button held, damage taken, stars-end.
;     NEWAVE    difficulty tier 0..7 for the current level.  Indexes most of
;               the "how hard is this" tables (BRNT10, BRNT15..BRNT17, HITAB5).
;     FUEL      0..$FF.  ADDFUL adds a signed amount, ADDFL2 subtracts 15.
;     SCORE     3 bytes, packed BCD, little-endian.  ADDSCR adds in decimal
;               mode (SED).  Python: keep an int and format it.
;     LIVES     remaining ships.
;     TARNUM    which slot the scanner is currently locked onto.
;     PAUTIM    freeze timer used during explosions.
;     CH0PTR/CH1PTR/CH0SHD/CH1SHD  two sound channels and their queued
;               (shadow) follow-up sounds.  See AUDIO.
;     MAZRAM(8), CURSOR, LSTCUR, JMPCNT, MAZSTA, NEWLEV, NEWATT
;               the star-chart universe: sector contents, your cursor position,
;               enemy fleet progress, current level, and the attack state.
;
;
;-------------------------------------------------------------------------------
;  7.  DISPLAY KERNELS -- WHAT THEY DRAW  (deliberately not how)
;-------------------------------------------------------------------------------
;
;  Four kernels exist, one per screen.  They are hand-timed 6502 racing the
;  electron beam and NONE of that timing needs to survive the port.  What DOES
;  need to survive:
;
;  a) All five P0-class objects are drawn by ONE reused hardware player, so
;     they must be vertically sorted and must not overlap.  That constraint is
;     enforced by GAME code, not by the kernel: BRAIN swap logic (BRAN22) and
;     CLOSE request logic exist purely to keep obj[1..4] in increasing screen Y
;     with no vertical overlap.  A Python port can draw freely, but if it does,
;     motion will feel different -- objects will stop shuffling past each
;     other.  Keep the sort if you want the original feel.
;
;  b) Sprite bitmaps are stored BOTTOM-ROW-FIRST and are addressed by a pointer
;     that has already had the object screen Y subtracted from it.  For a block
;     ending in a label such as RPL8:
;        the byte at  RPL8-1  is the TOP row of the sprite,
;        earlier bytes are successively lower rows,
;        the two $00 bytes at the START of the block terminate the object --
;        the kernel does BEQ on the fetched byte to know it is finished.
;     To extract a sprite in Python: walk BACKWARDS from LABEL-1 until the $00
;     pad; that gives the rows top to bottom.
;
;  c) MTABL1/MTABL3 give the graphic pointer (low/high) per type byte, MTABL2
;     gives the per-scanline COLOUR table pointer, and MTABL4 gives the
;     per-scanline HMOVE delta table pointer.  The delta tables (KDL*, XDL*,
;     RDL1, CDL*) are what make explosions, rings and craters wider than eight
;     pixels: each scanline nudges the player sideways.  In Python these become
;     wide multi-column sprites; treat a delta stream as shape data.
;
;  d) The kernels are state machines, not loops.  VECTP0 and VECTP1 hold the
;     LOW BYTE of the next fragment to run and every fragment ends in
;     JMP (VECTPn).  Read them as a flow chart of what is on screen right now,
;     not linearly.
;
;  e) The score/status kernel (SCRKER) draws six BCD digits from SCRTAB.
;     SCANDS draws the scanner strip: range bar, direction arrow, target icon,
;     lives (LIVTAB) and the fuel bar (FUELT1..FUELT5).
;
;  f) CRAZY is a horizontal-position table indexed by pixel X: high nibble is
;     the HMOVE fine adjustment, low nibble is a delay-loop count.  Every
;     LDY <xpos> / LDA CRAZY,Y is just "put this thing at pixel x".  Pure
;     PLUMBING -- in Python assign the X coordinate and move on.
;
;
;-------------------------------------------------------------------------------
;  8.  BANK SWITCHING -- ALL PLUMBING
;-------------------------------------------------------------------------------
;
;  The cartridge is 16K in four 4K banks, hot-swapped by touching $FFF6..$FFF9
;  (STROB1..STROB4).  Writing one of those addresses swaps the bank UNDER the
;  running code, so the instruction after the STA is already in the new bank.
;  That is why the source is full of
;
;        STA  STROB3        ; the JMP that lands here lives in the OTHER bank
;
;  followed by an apparently unreachable JSR or JMP.  The EXIT1..EXIT9 and
;  PON1..PON4 stubs at the end of each bank are nothing but trampolines.
;
;  For Python: delete all of it, put every routine in one module, call it
;  directly.  The bank contents are:
;
;     bank 1   spawn VM (NEWOBJ), AI (BRAIN), animation (GRAPH), collision
;              (CLOSE), the fixed-point math helpers, most gameplay tables.
;     bank 2   space-view display kernel, starfield, JOYSTK, SHPSRV (your ship
;              graphic plus photon firing), AUDIO.
;     bank 3   score/scanner/chart kernels, INIT, MAIN, TIMSRV, SMARTS, star
;              chart navigation (DOOR/FINDV), player collision (HITSRV),
;              scoring and fuel.
;     bank 4   planet/trench display kernel, hyperwarp kernel, MOVER, PLNSRV,
;              and all surface-mode sprite data.
;
;  Also PLUMBING and safe to ignore: the IFNCONST BURN block of development
;  jump vectors, HACKCLI / HACKSEI (one-byte patch points the development
;  system poked CLI/SEI into), the "MUST BE ON PAGE BOUNDARY" warnings, and
;  all the ORG/RORG juggling.
;
;
;-------------------------------------------------------------------------------
;  9.  READING NOTES
;-------------------------------------------------------------------------------
;
;  * Doug original comments are preserved verbatim.  Where one is a question
;    mark or an OOPS, that is the author being unsure, and those spots are
;    usually real bugs that shipped.  They are annotated where found.
;  * Carry is used as a boolean ARGUMENT everywhere.  A bare SEC or CLC just
;    before a JSR is passing a parameter, not leftover state.
;  * ADC #$xx with a trailing ;C=1 means the author knows carry is set and is
;    really adding xx+1.  Likewise SBC with ;C=0 subtracts xx+1.
;  * Table reads of the form  LDA TABLE-$40,Y  are a fused subtract-then-index.
;    In Python that is TABLE[y - 0x40].
;  * Tables marked ;SHARE 1 or ;SHARE 2 deliberately overlap: the last N bytes
;    of one table are also the first N bytes of the next, to save ROM.  Do not
;    merge them blindly when extracting data.
;  * Self-modifying and stack-abusing tricks: PNTRP1 and the 6502 stack pointer
;    double as loop counters inside the kernels (TSX/TXS), and STAK1..STAK4
;    deliberately live inside the stack page.
;  * .wy / .w suffixes are DASM addressing-mode overrides (force absolute).
;    They exist so an instruction takes a known number of cycles or so it can
;    index past the zero page.  No semantic meaning; ignore them.
;
;===============================================================================
;

      processor 6502
      seg.u stella

;LIST ON
;PW 80
;PL 253
;SYNTAX 6502
;CODE
;RADIX 10
;ABSOLUTE
;  VERSION 19.4 DATE 22-FEB-86
;
; BEGINS 07-JAN-83
; SCREEN 11-MAR-83
; ENDS ????????
;
;  ********************************
;    BURN = 1 THEN BURN PROMS, BURN = 0 THEN ASSEMBLE FOR DEVELOPMENT SYSTEM
BURN EQU 1
;  ********************************
;
;
; The map below is DOUG's ROM budget note, not code.  It lists which sprite
; graphic sets live at which offset inside banks 2 and 4, keyed by the object
; CLASS value from the type byte (sec. 4 of the header).  It is the quickest
; index there is from "class nibble" to "which creature this is":
;
;   class $00  fighter          (bank 2 space art / bank 4 planet art)
;   class $08  pirate
;   class $10  warp graphic     / miscellaneous graphics
;   class $14  darter
;   class $18  hyperjumper      / the MAN and the KEY on the surface
;   class $20  planet killer    / the LANDING ZONE
;   class $28  blockader        / the trench TOWER
;   class $30  enemy photon
;   class $38  explosions
;   class $40  Saturn rings     / crater
;   class $48  moon type 1
;   class $54  moon type 2
;   $E0        PBLK, the empty-slot sentinel
;
;      BANK2         BANK4
; 0   FIGHTER       PLN FIG
; 8   PIRATE        PLN PIR
; 10  WARP GRA.     MISC GRAPH
; 14  DARTER        ----
; 18  HYPERJUMPER   MAN + KEY
; 20  P KILLER      LANDING ZONE
; 28  BLOCKADER     TRN TOWER
; 30  ENEMY PHOTON  ENE PHOTON
; 38  EXPLOSIONS    EXPLOS
; 40  SATURN RINGS  CRATER
; 48-53  MOON1
; 54-5F  MOON2
; E0  PBLK   (60+80)
;
;
;
;-------------------------------------------------------------------------------
; ZERO PAGE RAM MAP  ($80..$FF)
;
; This is the ENTIRE state of the game -- the 2600 has 128 bytes of RAM and
; Solaris uses essentially all of them, with heavy aliasing (see the two
; EQUATE blocks further down, where the same bytes get a second name during
; vertical blank and a third name during the display kernel).
;
; A Python port should NOT reproduce the aliasing.  Give every logical variable
; its own attribute; the overlaps exist only because the 2600 ran out of RAM.
; They are documented here because the code jumps between the aliases freely
; and you cannot follow it otherwise.
;
; Layout is load-bearing in three places, all called out below:
;   - MAZSTA must follow JMPCNT           (FINDV indexes across the pair)
;   - the P1/pad/P0 interleave            (the object array, header sec. 1)
;   - STAK1..STAK4 live inside the stack  (the kernels use TSX/TXS as a loop
;     counter and the stack grows down into these on purpose)
;-------------------------------------------------------------------------------
;  *** ZERO PAGE RAM ***
;
;   BEGIN DATA SECTION
;DATA
;
      ORG $80  ;Zero page starts at $80.  DS n reserves n bytes (no initialiser).
MAZRAM DS 8  ;STAR CHART: 8 bytes = the sector grid.  Each bit is one occupied
;   sector; SMSKTB turns an index 0..7 into the bit mask.  bit 7 of MAZRAM+0
;   also doubles as the "friendly presence" flag.
CURSOR DS 1  ;Chart cursor = where YOUR ship is, 0..$2F (a 6-wide x 8-tall grid).
JMPCNT DS 1  ;Enemy fleet advance counters (see FINDV / SMRHLP).
MAZSTA DS 1 ;MUST BE RIGHT AFTER JMPCNT (FOR FINDV) -- Chart status. bit 7 = negative universe, bit 6 = redraw needed.
RANDOM DS 2  ;PRNG state, 2 bytes.  Reseeded every frame in MOVER, see header 6.
PROGST DS 1  ;GAME MODE BITS.  Decoded in full in header section 5.  Read this
;   one first -- almost every routine branches on it.
HCOLP1 DS 2  ;+0 ship/flame colour, +1 hyperwarp Z (also ship-takeoff progress).
JMPTIM DS 1  ;Countdown (BCD) to the next enemy fleet move on the chart.
;
; --- everything from here down survives a WARM start (game reset / select) ---
NOCLER
             ; DONT CLEAR PREVIOUS RAM ON WARM START
NEWLEV DS 1  ;NO CLEAR ON GAME SEL.
PNTR1  DS 2  ;PNTR1..PNTR6: six general 16-bit scratch pointers.  During vblank
;   they are aliased as TEMP4..TEMP13 / JOYRMH / JOYRMV, and during the display
;   kernel as VECTP0 / MISC1 / MOON1..MOON3 etc.  Same bytes, three lifetimes.
PNTR2  DS 2
PNTR3  DS 2
PNTR4  DS 2
PNTR5  DS 2
PNTR6  DS 2
ATRACT DS 2  ;2 BYTE FRAME TIMER -- FRAME COUNTER and master phase clock.  See header section 6.
ONESHT DS 1  ;Edge-detect latches: fire held, damage taken, stars-end flag.
;
;
; --- THE OBJECT ARRAY (header section 1) ------------------------------------
; Eight parallel arrays.  Each is  P1[0..2] , 1 pad byte , P0[0..3]  so that
; the whole eight-entry field is contiguous and can be walked as  FIELD-1,X
; with X = 0..4.  X=0 hits the pad byte, which the code uses as a scratch
; write target on purpose.
HGRAP1 DS 3  ; PLAYER TYPE -- obj.type for your ship (+0), near photon (+1), far photon (+2).
       DS 1  ;the pad byte -- this is what FOO-1,X with X=0 addresses.
HGRAP0 DS 4  ;obj.type for the four enemy/scenery slots.  $E0 = PBLK = empty.
IQREAP DS 1  ;ALSO HWARF TARGET NUM. -- Reused: spawn scratch in NEWOBJ, and the hyperwarp target number.
;
HHORP1 DS 3  ; PLAYER X -- obj.x, 0..$9F.
       DS 1
HHORP0 DS 4  ;obj.x for the four enemy slots.
PLINES DS 1  ;Number of scanlines of planet surface currently drawn.
;
HVERP1 DS 3  ; PLAYER Y -- obj.y.  BOTTOM of screen is 0, Y counts UP.  TOPSCN ($99) is top.
       DS 1
HVERP0 DS 4  ;obj.y for the four enemy slots.
VWALL  DS 1  ;Trench wall position (surface mode only).
;
ZPOSP1 DS 2  ; PHOTON Z -- obj.z, your two photons.  bit 7 set = that photon is OFF.
       DS 1
ZPOSP0 DS 4  ;obj.z for the four enemy slots.  0 = at the camera, ZVIS = cutoff.
       DS 1  ;IQPATH-1 -- the pad byte for IQPATH, addressed as IQPATH-1.
IQPATH DS 4  ;obj.path: low nibble = flight path id, high nibble = phase.
;
;  TEMPORARY STUFF  *********
;
; --- short-lived globals ----------------------------------------------------
STARS  DS 2  ;STAR PNTR -- Pointer into the starfield table STARTB (scrolls with the camera).
;   NOTE: STARS+1 is aliased as NEWAVE, the difficulty tier.  Same byte.
REQUST DS 1  ;Pending object SWAP request from CLOSE, consumed by BRAIN.
;   bit 7 / bit 6 select which kind of swap, low 3 bits are the slot index.
BOTSCN DS 1  ;Scanline number at which the picture ends (kernel loop bound).
HHORM2 DS 1  ; STAR HPOS -- X position of the star missile (M2), scrolls with the camera.
NEWATT DS 1  ;Attack state.  Low 3 bits = which enemy is inbound, bit 6/7 =
;   the enemy fleet is attacking a friendly planet.
PAUTIM DS 1  ;Freeze timer.  Non-zero = the world is paused (explosion playing).
CENTER DS 1  ; HORIZ ZOOM BYTE -- THE CAMERA X.  Clamped $2D..$74 in JOYSTK.  Everything is
;   positioned relative to this.
IQPNTR DS 1  ;IQ RAM -- Program counter of the NEWOBJ spawn VM (an offset into TYPTAB).
IQSTAK DS 1  ;The VM one-deep call stack (0 = empty).  See NEWOBJ / IRQREQ.
IQWARP DS 1  ;THROTTLE, signed.  $80..$FF = forward thrust, $FF fastest.
SHIPST DS 1  ;Ship state machine.  See header section 6.
HOLDM2 DS 1  ;Scratch: holds a pixel X for the CRAZY positioning table.
HOLDM0 DS 1  ;Scratch: holds a zoom byte handed from HYPSRV to SHPSRV.
;  END TEMP ******************
;
GAMTIM DS 1  ;Elapsed game time, used to pace the enemy fleet (see SMARTS).
LSTCUR DS 1  ;Previous chart cursor.  bit 7 = we moved, bit 0 = direction.
GAMEST DS 1  ;Mission state bits.  See header section 6.
LIVES  DS 1  ;Remaining ships.
TARNUM DS 1  ;Slot index the scanner is locked onto (set by GRAPH).
FUEL   DS 1  ;0..$FF.  Drains on damage, refills at a friendly landing zone.
SCORE  DS 3  ;3 bytes of packed BCD, little-endian.  ADDSCR adds with SED.
CH0PTR DS 1  ;Sound channel 0 / 1 program counters (offsets into AUDTAB).
CH1PTR DS 1
CH0SHD DS 1  ;Sound channel 0 / 1 QUEUED follow-up sound, played when the
;   current sequence ends.  This is the game two-slot sound priority scheme.
CH1SHD DS 1
;
; --- the CHART BLOCK --------------------------------------------------------
; $E4..$FB does double duty.  On the star chart screen it is CHTBLK, a 24-byte
; packed bitmap of the sector grid (two 4-bit cells per byte).  Everywhere else
; it is the per-object velocity arrays plus kernel pointers.  CHTSRV rebuilds
; CHTBLK from CHTAB4 when the chart is opened; SMAR23 restores the velocities
; from CHTAB1 when it is closed.
 ORG $E3
; BEGIN CHART BLOCK
EXPNTR DS 1  ; ALSO USED AS CHART TIMER -- Explosion animation pointer.  Doubles as the chart redraw timer.
CHTBLK
VECTP1 DS 2  ;Kernel: low/high byte of the next P1 kernel fragment to run.
PNTRP1 DS 1  ;Kernel: saved fragment pointer while an object is being drawn.
       DS 1
XDELP0 DS 4  ;obj.dx, packed velocity (header section 3).
       DS 1
YDELP0 DS 4  ;obj.dy, packed velocity.
       DS 1
ZDELP0 DS 4  ; SPEED OF OBJS. -- obj.dz, packed velocity = closing speed.
VELOC  DS 1  ; FOR HORIZ SHIP -- Your ship horizontal velocity, signed, $E0..$1F.
HPOSL  DS 1  ; FOR HORIZ SHIP -- Sub-pixel accumulator for the ship horizontal motion.
HHITP0 DS 4  ; USES STAK1 TOO ,ALSO USED FOR STACK IN BRAIN, 4LEV DEEP -- Collision X per object, computed by GRAPH, consumed by HITSRV.
; END CHART BLOCK
; FOLLOWING VARIABLES RESIDE IN STACK
STAK1  DS 1  ;STAK1..STAK4 sit INSIDE the 6502 stack page on purpose: the
;   kernels use the stack pointer itself as an object loop counter (TSX/TXS),
;   so these four bytes are safe scratch as long as nesting stays shallow.
STAK2  DS 1
STAK3  DS 1
STAK4  DS 1
;
;
;  END DATA SECTION
;; CODE
;
;
;
;-------------------------------------------------------------------------------
; TIA AND RIOT HARDWARE REGISTER NAMES.
; Pure PLUMBING for a Python port -- these are the video/audio/IO chip
; registers, not game variables.  Worth knowing only so you can recognise a
; store to one and skip it:
;   VSYNC/VBLANK/WSYNC   frame and scanline timing
;   COLPM0/1 COLPF COLBK player, playfield and background COLOURS
;   GRAFP0/1 GRAFM0/1/2  the 8-bit sprite shift registers (what is drawn now)
;   HPOSP0.. HDELP0..    coarse and fine horizontal positioning
;   SIZPM0/1 REFP0/1     sprite width/replication and mirroring
;   VDELP0/1 ADDEL       vertical delay and HMOVE strobes
;   M0PL..MIPL           COLLISION latches, read by HITSRV
;   TRIG0/TRIG1          the two fire buttons
;   PORTA                joystick directions (active low, $FF = centred)
;   PORTB                console switches (reset, select, colour/BW)
;   RTIMER, STIM64 ...   the RIOT interval timer, used to pace the frame
;-------------------------------------------------------------------------------
;  VCS EQUATES
VSYNC  EQU 0
VBLANK EQU 1
WSYNC  EQU 2
SIZPM0 EQU 4
SIZPM1 EQU 5
COLPM0 EQU 6
COLPM1 EQU 7
COLPF  EQU 8
COLBK  EQU 9
PRIOR  EQU $A
REFP0  EQU $B
REFP1  EQU $C
GRFPF0 EQU $D
GRFPF1 EQU $E
GRFPF2 EQU $F
HPOSP0 EQU $10
HPOSP1 EQU $11
HPOSM0 EQU $12
HPOSM1 EQU $13
HPOSM2 EQU $14
AUDC0  EQU $15
AUDC1  EQU $16
AUDF0  EQU $17
AUDF1  EQU $18
AUDV0  EQU $19
AUDV1  EQU $1A
GRAFP0 EQU $1B
GRAFP1 EQU $1C
GRAFM0 EQU $1D
GRAFM1 EQU $1E
GRAFM2 EQU $1F
HDELP0 EQU $20
HDELP1 EQU $21
HDELM0 EQU $22
HDELM1 EQU $23
HDELM2 EQU $24
VDELP0 EQU $25
VDELP1 EQU $26
VDELM2 EQU $27
GCTLM0 EQU $28
GCTLM1 EQU $29
ADDEL  EQU $2A
CLRDEL EQU $2B
HITCLR EQU $2C
M0PL   EQU $30
M1PL   EQU $31
P0PF   EQU $32
P1PF   EQU $33
M0PF   EQU $34
M1PF   EQU $35
M2PF   EQU $36
MIPL   EQU $37
POT0   EQU $38
POT1   EQU $39
POT2   EQU $3A
POT3   EQU $3B
TRIG0  EQU $3C
TRIG1  EQU $3D
PORTA  EQU $280
RACTL  EQU $281
PORTB  EQU $282
PBCTL  EQU $283
RTIMER EQU $284
RFLAG  EQU $285
STIME1 EQU $294
STIME8 EQU $295
STIM64 EQU $296
ST1024 EQU $297
FTIME1 EQU $29C
FTIME8 EQU $29D
FTIM64 EQU $29E
FT1024 EQU $29F
;
;
;
;-------------------------------------------------------------------------------
; BANK SELECT.  PLUMBING -- see header section 8.
; With BURN=1 (the shipped ROM) all four banks live at $F000 and only the
; STROBn address distinguishes them.  With BURN=0 the development system maps
; them at $C000/$D000/$E000/$F000 so a debugger can see all four at once.
;-------------------------------------------------------------------------------
;  BANK SELECT EQUATES

 IFCONST BURN
BANK1 EQU $F000
BANK2 EQU $F000
BANK3 EQU $F000
BANK4 EQU $F000
 ELSE
BANK1 EQU $C000
BANK2 EQU $D000
BANK3 EQU $E000
BANK4 EQU $F000
 ENDIF
STROB1 EQU $FFF6
STROB2 EQU $FFF8
STROB3 EQU $FFF7
STROB4 EQU $FFF9
;
;
;
;-------------------------------------------------------------------------------
; GAME CONSTANTS.  These are the real tuning numbers.
;-------------------------------------------------------------------------------
;  GAME EQUATES
NUMCOL EQU 3+4
K      EQU 8   ; CHTRAM POS. OF HOME PLANET -- Chart grid index of your home planet.
U      EQU 1  ;The literal 1.  Used as +U in table maths to keep offsets legible.
TOPSCN EQU $99  ;TOP scanline of the play area.  Screen Y runs TOPSCN..0 downward.
SCNSIZ EQU TOPSCN+39  ;Total play-area height, TOPSCN+39 scanlines.
MTNTOP EQU $62  ;Y of the mountain horizon on a planet.
TRNTOP EQU $62  ;Y of the top of the trench walls.
VSHIP  EQU $1D  ;Your ship resting Y.  The ship never moves vertically in space.
ZVIS   EQU $78  ;Far visibility cutoff.  ZPOS >= ZVIS means not drawn.
PBLK   EQU $60+$80  ; BLANK P0 -- THE EMPTY-SLOT SENTINEL.  HGRAP == PBLK means the slot is free.
;   $60 is the class, $80 is the off-screen bit.  Compared everywhere.
POFF   EQU $A8   ;NEW P0 -- Threshold above which an off-screen object is retired entirely.
SCLR   EQU $F2  ;STAR COLOR
VCENT  EQU $53 ;VERT ZOOM CENTR OF SCRN -- The vertical vanishing point.  Objects converge on this Y as
;   they recede; BRAIN steers dy toward (obj.y - VCENT).
SKYCOL EQU $70
SURCOL EQU $62
TRNCOL EQU $84
; Z= USED IN BANK2
; EQUATE Q= BRNTB1
; EQUATE W= TYPTAB
; EQUATE J= AUDTAB
; BOTTOM OF SCREEN = 0
;
;
;-------------------------------------------------------------------------------
; ALIAS SET 1 -- names used during VERTICAL BLANK (the thinking phase).
; These are the SAME BYTES as PNTR1..PNTR6 and STARS above.  In Python give
; each of them a real local variable; the sharing is a RAM-saving hack.
;   TEMP4..TEMP13   general scratch.  The math helpers have fixed contracts:
;                   TEMP4 = zoomed Z, TEMP5 = |ZDEL| or the min/max bound,
;                   TEMP7 = the per-path speed LIMIT, TEMP10 = the packed
;                   result, TEMP11 = the sign flag, TEMP13 = the path index.
;   JOYRMH/JOYRMV   this frame joystick contribution to horizontal/vertical
;                   object drift -- i.e. how much the world slides because YOU
;                   moved.  Added into every object dx/dy in BRAIN.
;   THGRP1          which of the three ship graphics to draw (0 level,
;                   1 bank right, 2 bank left).
;   NEWAVE          difficulty tier 0..7.  NOTE this aliases STARS+1.
;-------------------------------------------------------------------------------
; VBLANK EQUATES
;
TEMP4    EQU PNTR5+0
TEMP5    EQU PNTR2+1
TEMP6    EQU PNTR1+0
TEMP7    EQU PNTR1+1
TEMP9    EQU PNTR4+0
TEMP10   EQU PNTR4+1
JOYRMH   EQU PNTR6+0
JOYRMV   EQU PNTR6+1
TEMP11   EQU PNTR2+0
TEMP12   EQU PNTR3+0
TEMP13   EQU PNTR3+1
THGRP1   EQU PNTR5+1  ;SHIP GRAPHIC 0,1,2
NEWAVE   EQU STARS+1
;
;
;
;-------------------------------------------------------------------------------
; ALIAS SET 2 -- names used during the DISPLAY KERNEL.  Same bytes again.
;   VECTP0/VECTP1   low byte of the next kernel fragment for the P0 / P1 chain
;   VERTP0/VERTP1   screen Y at which the current P0 / P1 object starts
;   MISC1/MISC2     graphic and colour pointers for the P1 object being drawn
;   MOON1/MOON2/MOON3  graphic, HMOVE-delta and colour pointers for the P0
;                   object being drawn (named for moons, used for everything)
;   HOLDP1/CROSP1   fine-position remainder and a star-masking value
;-------------------------------------------------------------------------------
;  SCREEN EQUATES
VECTP0 EQU PNTR1
HOLDP1 EQU PNTR2+0
CROSP1 EQU PNTR2+1
VERTP0 EQU PNTR3+0
VERTP1 EQU PNTR3+1
MISC1  EQU PNTR4
MOON2  EQU PNTR5
MOON1  EQU PNTR6
MOON3  EQU STAK1  ;AND STAK2
MISC2  EQU STAK3  ;AND STAK4
;
;
;
; .BEGIN PROGRAM
;
; LIST OFF
; INCLUDE B:BANK2.ASM
;
;
; LIST OFF
; INCLUDE B:BANK3.ASM
;
;
; LIST OFF
; INCLUDE B:BANK4.ASM
;
;
; LIST OFF
; INCLUDE B:BANK1.ASM
;
;
; LIST OFF
;
; PLUMBING: development-system-only jump vectors, assembled out of the shipped
; ROM by BURN=1.  When all four banks were visible at once on the dev machine
; these stubs stood in for the bank-switch trampolines.  Skip entirely.

 IFNCONST BURN
;  JUMP VECTORS FOR UNIV.ASM DURNING DEVELOPMENT
; BK3
 ORG BANK3+$FCC
 JMP BANK2+$FCF
 JMP BANK1+$FD2
 JMP BANK4+$FD5
 ORG BANK3+$FEA
 JMP BANK2+$FED
 JMP BANK4+$FF0
; BK1
 ORG BANK1+$FCF
 JMP BANK4+$FD2
 ORG BANK1+$FD5
 JMP BANK3+$FD8
 ORG BANK1+$FDE
 JMP BANK2+$FE1
 ORG BANK1+$FF0
 JMP BANK3+$FF3
; BK4
 ORG BANK4+$FD2
 JMP BANK3+$FD5
 ORG BANK4+$FD8
 JMP BANK1+$FDB
 ORG BANK4+$FE4
 JMP BANK3+$FE7
 ORG BANK4+$FEA
 JMP BANK1+$FED
 JMP BANK3+$FF0
; BK2
 ORG BANK2+$FCC
 JMP BANK1+$FCF
 ORG BANK2+$FD5
 JMP BANK3+$FD8
 ORG BANK2+$FDE
 JMP BANK4+$FE1
 ORG BANK2+$FE4
 JMP BANK4+$FE7
;   DEFINE PC (FOR DEVELOPMENT SYSTEM)
 ORG $9C04
 DW INIT
;   FOR HALT DURING VBLANK
 ORG HACKCLI
 CLI
 ORG HACKSEI
 SEI
 ENDIF

;.END

;
;===============================================================================
; B A N K   1  --  GAMEPLAY LOGIC
;
; Everything that decides what happens (as opposed to what is drawn) lives
; here: the wave-spawn VM, the per-object AI, animation selection, collision
; bookkeeping, and the fixed-point math helpers.  For a Python port this bank
; is roughly 70% of the work and the display kernels are the other 30%.
;===============================================================================
; bank 1
       seg bank1
       ORG $0000
       rorg $f000
;
;-------------------------------------------------------------------------------
; DIVTB1 -- the PERSPECTIVE DIVIDE table, used only by DIVIDE.
;
; It is a 128-entry table addressed as a pair of 16-entry rows, i.e. a two-pass
; 4-bit x 4-bit divide:
;
;   pass 1:  index = (|screen offset| high nibble) | (zoomed Z low nibble)
;            -> a byte whose LOW nibble is the partial quotient
;   pass 2:  index = (that nibble) | (|ZDEL| low nibble)
;            -> a byte whose HIGH nibble is the final code
;
; The final code indexes BRNTB5 to become a real magnitude.  Net effect:
;
;   drift = screen_offset * closing_speed / distance
;
; In Python just do the float division and skip the table entirely.
;-------------------------------------------------------------------------------
DIVTB1 
       .byte $08,$03,$02,$01,$01,$01,$00,$00
       .byte $00,$00,$00,$00,$00,$00,$00,$00
       .byte $0C,$08,$05,$13,$13,$12,$12,$22
       .byte $22,$31,$41,$51,$61,$71,$80,$F0
       .byte $0E,$09,$18,$16,$14,$24,$23,$33
       .byte $32,$42,$62,$72,$82,$91,$91,$F1
       .byte $0F,$0B,$19,$18,$26,$25,$34,$34
       .byte $43,$63,$73,$82,$92,$92,$A2,$F2
       .byte $0F,$1C,$19,$28,$38,$37,$46,$45
       .byte $54,$74,$83,$93,$A3,$A3,$B2,$F2
       .byte $0F,$1D,$1B,$29,$38,$48,$47,$56
       .byte $65,$85,$94,$A4,$B4,$B3,$C3,$F3
       .byte $0F,$1E,$2B,$3A,$39,$48,$58,$67
       .byte $76,$95,$95,$A4,$B4,$C4,$D3,$F3
       .byte $0F,$1F,$2C,$3A,$49,$59,$68,$78
       .byte $87,$96,$A6,$B5,$C5,$D4,$E4,$F4
;
;-------------------------------------------------------------------------------
; ZOOMTB -- indexed by ZPOS (depth), gives a PACKED SIZE/ZOOM byte:
;     bit 7      set = this object is drawn at double width
;     bits 6..4  the vertical zoom step, i.e. how many scanlines tall
;     bits 3..0  the TIA NUSIZ value (sprite replication/stretch)
; Used three ways: by GRAPH to pick a scale, by BRAIN to reject a swap when an
; object is already double-size, and by HYPSRV to shrink the photons as they
; recede.  Python: a distance -> scale factor lookup.
;-------------------------------------------------------------------------------
ZOOMTB 
       .byte $0F,$7F,$5D,$4B,$3A,$29,$29,$28
       .byte $28,$17,$17,$16,$15,$15,$15,$04
       .byte $1F,$0F,$1E,$0B,$9A,$89,$99,$89
       .byte $08,$18,$07,$07,$06,$16,$05,$05
       .byte $8F,$8F,$9C,$8C,$0B,$0A,$09,$09
       .byte $08,$18,$08,$07,$07,$06,$06,$05
       .byte $0F,$0F,$1F,$0C,$0B,$0A,$0A,$09
       .byte $89,$88,$88,$88,$07,$07,$06,$06
       .byte $9F,$8F,$8F,$8D,$0C,$0B,$0A,$09
       .byte $89,$89,$88,$88,$08,$07,$07,$06
       .byte $0F,$0F,$0F,$0E,$8C,$8B,$8A,$9A
       .byte $09,$09,$09,$08,$08,$08,$07,$07
       .byte $0F,$0F,$0F,$0E,$0C,$0B,$0A,$0A
;
; GRATB7 -- companion to GRATB6 (see GRAPH7).  Only its top bit matters: it
; supplies the NINTH address bit of the animation handler, letting the 24
; handlers straddle two pages.  Pure PLUMBING.
GRATB7 
       .byte $09,$09,$89,$08,$88,$08,$08,$07
       .byte $8F,$8F,$0F,$0F,$8D,$0C,$8B,$8A
       .byte $0A,$89,$89,$89,$88,$88,$88,$88
;
;
;
;
;===============================================================================
; N E W O B J  --  THE WAVE-SPAWN BYTECODE VM
;
; This is the most important thing in the file.  It is a tiny interpreter whose
; program is the TYPTAB byte array and whose job is to decide WHAT enemy or
; scenery to put into an empty object slot, and when.
;
; Called from BRAIN (label BRAN50) whenever the swap logic finds an empty slot,
; with X = the index of that slot.  Runs exactly one instruction chain per
; call and returns; it is not a loop over the whole script.
;
; VM STATE
;   IQPNTR   the program counter: a byte offset into TYPTAB.
;   IQSTAK   a ONE-DEEP call stack.  0 means "not inside a subroutine".
;   IQREAP   the loop counter used by LVS and BRN.
;   X        the destination slot (space mode).  Forced to 3 or 4 on a surface.
;
; INSTRUCTION FORMAT
;   Read the byte at TYPTAB[IQPNTR].
;     bit 7 SET  -> it is a SPAWN DESCRIPTOR; go to NEWOB3 and create an object.
;     bit 7 CLEAR-> it is an OPCODE.  The byte IS THE LOW BYTE OF THE HANDLER
;                   ADDRESS.  The dispatcher builds a pointer from it plus the
;                   page of NEWOB1 and does JMP (PNTR3).  That is why the
;                   opcode EQUates below are all  < LABEL  (low byte of).
;                   The operand byte follows in A; carry is cleared on entry.
;
; OPCODE SET (byte lengths noted; PC advances by that much unless stated)
;
;   GTO t        2   IQPNTR = t.                       goto
;   SUB t        2   IQSTAK = IQPNTR; IQPNTR = t.      call (one deep)
;   RET          1   IQPNTR = IQSTAK + 2; IQSTAK = 0.  return past the SUB
;   STO addr,v   3   mem[addr] = v.                    poke a global
;   ENB addr,m   3   mem[addr] |= m.                   set bits in a global
;   LVS n        2   IQREAP = NEWT11[n + NEWAVE].      load loop count, scaled
;                    by the difficulty tier -- harder levels get more enemies
;   BRN t        2   if --IQREAP >= 0: IQPNTR = t.     loop back
;   RNW p,t      3   if p >= RANDOM: IQPNTR = t.       branch with probability
;                    p/256, else fall through
;   EMP v,t      3   if v >= HGRAP0+3: IQPNTR = t.     used only as EMP PBLK-1,t
;                    which means "if the last slot is NOT empty, branch"
;   RND b        2   pick one of NEWTB7[b + rand(0..3) - $E0] and treat that
;                    byte as a spawn descriptor.  The operand byte is >= $E0 so
;                    that if the PC ever lands on it, NEWOB3 skips it harmlessly
;   INL          1   award an extra life, capped at 5
;
; Python sketch:
;
;   def newobj(slot):
;       while True:
;           op = TYPTAB[pc]
;           if op & 0x80: return spawn(op, slot)
;           ... dispatch on OPCODE_NAMES[op] ...
;
; The scripts themselves are at TYPTAB (BLKTYP, PIRTYP, MONTYP, ...) -- one
; script per encounter type, selected by DOOR when you arrive in a sector.
;===============================================================================
;   SUBROUTINES FOR BANK 1
;
; SUB t -- call.  Y still holds the PC, so save it, then fall into GTO.
NEWOB1
;  SUB.
       STY    IQSTAK
;
; GTO t -- unconditional jump.  A = the target offset.
NEWOB2
; GTO
       STA    IQPNTR 
;
;
; The dispatcher.  Fetch, classify, and either spawn or vector to a handler.
NEWOBJ
       LDY    IQPNTR  ;Y = the VM program counter.
       LDA    TYPTAB,Y  ;Fetch the instruction byte.
       BMI    NEWOB3  ;bit 7 set -> spawn descriptor, not an opcode.
       STA    PNTR3  ;Opcode byte IS the low byte of its handler address...
       LDA    #>NEWOB1  ;...and every handler lives in the same page as NEWOB1.
       STA    PNTR3+1 
       CLC  ;Handlers are entered with carry CLEAR; several rely on it.
       LDA    TYPTAB+1,Y  ;A = the operand byte (the one after the opcode).
       JMP.ind (PNTR3)  ;Vectored call into the handler chosen above.
;
; EMP v,t -- compare the operand against the LAST slot type and share the
; branch tail with RNW.  Only ever used as EMP PBLK-1,t = "branch if the last
; slot is occupied", i.e. "the screen is full, go do something else".
NEWB55
;  EMP
       CMP    HGRAP0+3
       JMP    NEWB62
;
; RNW p,t -- probabilistic branch.  C=1 (branch taken) when p >= RANDOM, so the
; branch probability is p/256.
NEWB78
;  RNW
       CMP    RANDOM 
NEWB62
       LDA    TYPTAB+2,Y  ;Shared tail: A = the 3rd byte, the branch target.
       BCC    NEWB61  ;Not taken: skip all 3 bytes and continue.
       BCS    NEWOB2  ;JMP -- Taken: re-enter as a GTO to the target.
;
; LVS n -- load the loop counter, scaled by difficulty.  NEWT11 is a 5x5 table
; (5 base values x 5 difficulty tiers) so the same script gets harder as
; NEWAVE rises.
NEWB50
;  LVS
       ADC    NEWAVE  ;operand + difficulty tier
       TAX
       LDA    NEWT11,X  ;NEWT11[n + NEWAVE] = how many times to repeat
       STA    IQREAP 
       JMP    NEWOB7
;
; BRN t -- decrement the loop counter and branch back while it is still >= 0.
NEWB51
;  BRN
       DEC    IQREAP 
       BPL    NEWOB2
       BMI    NEWOB7  ;JMP
;
; RET -- pop the one-deep stack and resume just past the SUB that called us.
NEWOB5
;  RET
       LDY    IQSTAK  ;Y = the saved PC (which points AT the SUB opcode)
       LDA    #$00 
       STA    IQSTAK  ;mark the stack empty again
       BEQ    NEWOB7  ;JMP -- fall into the +2 tail so we resume after the SUB operand
;
; INL -- award an extra ship, capped at 5.  A one-byte instruction.
NEWB81
;  INL
       LDA    LIVES 
       CMP    #$05 
       BCS    NEWOB8
       INC    LIVES 
       BCC    NEWOB8  ;JMP
;
; STO addr,v -- write a literal into a zero page global.  Shares its tail with
; ENB by loading 0 and then ORing the value in.
NEWB41
;  STO
       TAX
       LDA    #$00 
       BEQ    NEWB60  ;JMP
;
; ENB addr,m -- OR a bit mask into a zero page global.
NEWOB4
;  ENB
       TAX  ;X = the target zero page address (from the operand)
       LDA    0,X  ;read the current value...
NEWB60
       ORA    TYPTAB+2,Y  ;...OR in the mask from the 3rd byte...
NEWB54
       STA    0,X  ;...and store it back.
;
; PC advance tail.  Fall-through chain: NEWB61 adds 3, NEWOB7 adds 2,
; NEWOB8 adds 1.  Each handler jumps into the right rung for its length.
NEWB61
       INY  ;+3 (three-byte instruction)
NEWOB7
       INY  ;+2 (two-byte instruction)
NEWOB8
       INY  ;+1 (one-byte instruction)
       STY    IQPNTR  ;commit the new program counter
NEWB58
       RTS
;
; RND b -- choose one of four spawn descriptors at random and fall straight
; into the spawner.  NEWTB7 is the descriptor pool; the -$E0 bias exists so
; the operand byte is always >= $E0 and therefore self-skipping if executed.
NEWB40
;  RND
       LDA    RANDOM 
       AND    #$03  ;rand 0..3
       ADC    TYPTAB+1,Y  ;+ the operand base
       TAY
       LDA    NEWTB7-$E0,Y  ;fetch the chosen descriptor and fall into NEWOB3
;  FALL THRU TO NEWOB3
;
; The opcode name table.  Each EQU takes the LOW BYTE of a handler address --
; that is literally the opcode number.  TYPTAB scripts read almost like
; assembly because of this.
;    EQUATES ****
SUB EQU <NEWOB1
GTO EQU <NEWOB2
ENB EQU <NEWOB4
STO EQU <NEWB41
RET EQU <NEWOB5
RNW EQU <NEWB78
LVS EQU <NEWB50
RND EQU <NEWB40
BRN EQU <NEWB51
EMP EQU <NEWB55
INL EQU <NEWB81
;
;
;
;-------------------------------------------------------------------------------
; N E W O B 3  --  THE SPAWNER
;
; A = a SPAWN DESCRIPTOR byte (bit 7 set).  Layout:
;
;     bit 7      always 1 (marks it as a descriptor, not an opcode)
;     bits 6..2  the object CLASS/GRAPHIC to create  (AND #$7C)
;     bit 2      ALSO doubles as "use slot 4 instead of slot 3" on a surface
;                (the landing zone and the man live in slot 4)
;     bits 1..0  CROWDING LIMIT: how full the screen may already be.
;                Larger = more tolerant.  Checked against the free-slot count.
;
; Special descriptor values:
;     $CB        the fallback: spawn a plain moon/crater AND DO NOT ADVANCE THE
;                PC, so the script retries next frame.  Substituted whenever
;                conditions are wrong (too fast, too crowded, no room).
;     $92        the hyperspace warper -- a whole special case below.
;     >= $A8     the moons, which are allowed at any throttle.
;     >= $E0     not a descriptor at all: a stray RND operand byte.  Skipped.
;
; On entry X = the destination slot when in space (BRAIN passes the empty slot
; it found).  In surface mode X is forced to 3 or 4 here.
;
; Every exit labelled ABORT restores PBLK to the slot, leaving it empty.
;-------------------------------------------------------------------------------
NEWOB3
;  BEGIN LOAD
       CMP    #$E0  ;>= $E0: a RND operand byte that the PC walked onto.  Just skip it.
       BCS    NEWOB8  ;2ND BYTE OF RND
       CMP    #$A8    ;? -- >= $A8 (the moons) may spawn at any speed.
       BCS    NEWB94
       LDY    IQWARP  ;Everything else requires the throttle to be near maximum...
       CPY    #$F1 
       BCS    NEWB94
       LDA    #$CB    ;TOO FAST -- ...otherwise fall back to $CB and retry next frame.
NEWB94
       STA    TEMP10  ;TEMP10 = the descriptor for the rest of the routine.
       LDY    #$05 
       STY    TEMP4 
; Count how many of the four enemy slots are free.  TEMP4 ends up as
; 5 - free_count, so TEMP4 = 1 means all four are empty and 5 means none are.
NEWB18
       LDA.wy HGRAP0-2,Y  ;Y = 5..2 walks HGRAP0+3 down to HGRAP0+0.
       ASL  ;Shift bit 6 into bit 7.  PBLK ($E0) has bit 6 set.
       BPL    NEWB19  ;bit 6 clear -> slot is occupied, do not count it.
       DEC    TEMP4 
NEWB19
       DEY
       BNE    NEWB18
       BIT    PROGST  ;V = PROGST bit 6 = "we are on a planet or in the trench".
       BVC    NEWB13
;
; ---- SURFACE SPAWN (planet / trench) --------------------------------------
; Destination slot is fixed: 3 normally, 4 for the landing zone or the man.
;  PLANET/TRENCH
       LDX    #$03  ;default destination slot
       LDA    TEMP10 
       AND    #$04  ;descriptor bit 2 = the landing-zone / man flag
       BEQ    NEWB52
       INX    ;LZ OR MAN -- use slot 4 instead
NEWB52
       LDA    TEMP10 
       AND    #$03  ;crowding limit from the descriptor...
       CMP    TEMP4  ;...must be >= 5 - free_count, i.e. enough slots are free
       BCS    NEWB48
       LDA    #$CB  ;too crowded: fall back to a crater and retry
       STA    TEMP10    ;CRATER DEFAULT
NEWB48
       LDA    HGRAP0-1,X  ;the destination slot must actually be empty...
       CMP    #PBLK
       BNE    NEWB58 ;ABORT -- ...otherwise give up entirely this frame
       LDA    HVERP0-2,X  ;the object below must not be too high up the screen...
       CMP    #$4E 
       BCS    NEWB58 ;ABORT -- ...or there is no room to fit this one in
       LDA    TEMP10 
       AND    #$7C  ;bits 6..2 of the descriptor = the graphic to use
       CMP    #$40  ;$40 and above means "use the terrain graphic instead"
       BCC    NEWB93
       LDA    PROGST 
       SBC    #$08   ;C=1 -- derive it from PROGST: $40 gives the planet, $28 the trench
       AND    #$68   ;40=PLN, 28=TRN
NEWB93 
       STA    HGRAP0-1,X  ;commit the object type
       LDA    #$56  ;surface objects always start at Y = $56 (just above the horizon)
       STA    HVERP0-1,X
       CPX    #$04  ;slot 4 = the landing zone or the man
       BEQ    NEWB53 ;LZ OR MAN
       LDY    #$04 
NEWB11
       JMP    NEWB10
NEWB53
       LDA    #AUDMAN-J  ;play the man-appears sound
       STA    CH1SHD 
       LDY    NEWAVE  ;on the easiest tier skip the wander setup entirely
       BEQ    NEWB11  ; EASY JUMP
       JMP    NEWB29
;
;
; ---- SPACE SPAWN -----------------------------------------------------------
; X is the empty slot BRAIN handed us.  HGRAP0-2,X is the object below it.
NEWB13
       LDA    HGRAP0-2,X  ;look at the object directly below this slot
       SBC    #$21  ;is it in the darter class ($21..$27)?
       CMP    #$07 
       BCS    NEWB74  ;no: normal space spawn
; A darter is spawned attached to the object below it, and inherits a Y just
; under that object rather than a random one.
;  DARTER
       TXA
       TAY
       DEX
       JSR    BRAN22  ;BRAN22 = swap this slot with the one below (shared with BRAIN)
       SBC    #$03  ;sit 3 scanlines below the parent
       STA    HVERP0-1,X
       BCC    NEWB16    ;ABORT -- would land off the bottom: abort
       LDA    #AUDLNH-J
       STA    CH1SHD 
       LDA    #$14  ;darter graphic
       STA    HGRAP0-1,X
       JMP    NEWB92
NEWB74
       LDA    TEMP10  ;crowding limit vs free-slot count, as above
       AND    #$03 
       CMP    TEMP4 
       BCS    NEWB20
; Not crowded enough for a real enemy: force a moon instead.  A moon may only
; appear if the object below it is small (class < $28), otherwise abort.
;  MOON FORCE STUFF
       LDY    SWAPT1-1,X  ;SWAPT1 maps the slot to the one it pairs with
       BEQ    NEWB21
       LDA.wy HGRAP0-1,Y
       AND    #$7F 
       CMP    #$28  ;the neighbour must be a small class
       BCS    NEWB21
; ABORT: leave the slot empty and return.  The script PC is NOT advanced, so
; the same spawn will be retried on a later frame.
NEWB16
;  ABORT
       LDA    #PBLK
       STA    HGRAP0-1,X
       RTS
NEWB21
       LDA    #$02  ;need at least 3 free slots for even a moon
       CMP    TEMP4 
       BCC    NEWB16  ;ABORT
       LDA    #$CB   ; MOON1 NOINC IQPNTR -- $CB = moon, and do not advance the VM program counter
       STA    TEMP10 
; ---- COMMON TAIL: choose the graphic ---------------------------------------
NEWB20
; DEFINE GRAPHIC
       LDA    TEMP10 
       AND    #$7C  ;bits 6..2 of the descriptor become the graphic byte
       CMP    #$40  ;class $40 is the ringed planet...
       BNE    NEWB71
       EOR    NEWTB8-1,X  ;RINGS -- ...whose rings variant comes from NEWTB8
NEWB71
       STA    HGRAP0-1,X  ;commit the object type
; ---- VERTICAL PLACEMENT ----------------------------------------------------
; The new object must fit in the vertical gap between the object above it
; (TEMP4 = the highest Y it may take) and the object below (TEMP5 = the lowest).
; The default is the midpoint; a random Y is used instead if it also fits.
; This is what keeps obj[1..4] sorted by Y for the display kernel.
;  VERTICAL
       LDA    #TOPSCN  ;default upper bound = top of screen
       CPX    #$04 
       BCS    NEWB24
       LDA    HGRAP0,X  ;otherwise: bottom of the object above, from its height in BRNTB6
       AND    #$7F 
       TAY
       LDA    BRNTB6,Y
       AND    #$3F  ;BRNTB6 low 6 bits = object height in scanlines
       EOR    #$FF 
       ADC    HVERP0+0,X   ;C=0 -- upper bound = neighbour Y minus neighbour height
NEWB24
       STA    TEMP4  ;MAX -- TEMP4 = MAX allowed Y
       LDA    #$00 
       CPX    #$02 
       BCC    NEWB25
       LDA    HVERP0-2,X  ;lower bound = the object below plus a small gap
       ADC    #$07   ;C=1
NEWB25
       STA    TEMP5  ;MIN -- TEMP5 = MIN allowed Y
       CMP    TEMP4 
       BCS    NEWB16  ;ABORT -- min > max: no room at all, abort
       ADC    TEMP4 
       ROR  ;midpoint of the range...
       STA    HVERP0-1,X   ;DEFAULT -- ...is the default Y
       LDY    RANDOM 
       LDA    NEWOB3,Y  ;RANDOM CODE -- Read a ROM byte at a random offset as a cheap extra random source.
       AND    #$0F 
       ADC    NEWTB1,X  ;NEWTB1 biases the random Y per slot
       CMP    TEMP5 
       BCS    NEWB26
       CMP    TEMP4 
       BCC    NEWB26
       STA    HVERP0-1,X  ;the random Y fits inside the range, so use it
; ---- PER-CLASS PLACEMENT ---------------------------------------------------
NEWB26
       LDA    TEMP10 
       CMP    #$92  ;$92 = the hyperspace warper: a fully scripted entrance
       BNE    NEWB27
; WARPER.  Sets up BOTH the warper (slot X) and the warp graphic in HGRAP1+3,
; giving them matching Z and a fixed approach so the pair animates together.
; WARPERS
       LDA    HVERP0-1,X
       CMP    HVERP0-2  ;must be above the object below it
       BCC    NEWB16  ;ABORT
       CMP    #TOPSCN-$10  ;and not too near the top of the screen
       BCS    NEWB16
       STA    HVERP1+3  ;put the warp effect in the shared P1+3 slot at the same Y
       LDA    #$08 
       STA    HHORP1+3 
       STA    ZPOSP0-1,X
       STA    ZPOSP0-1 
       LDA    #AUDJMP-J  ;play the hyperjump sound
       STA    CH1PTR 
       LDA    #$98 
       STA    HHORP0-1,X
       LDA    #$00 
       STA    ZDELP0-1,X
       STA    ZDELP0-1 
       LDA    #$05 
       STA    YDELP0-1,X
       STA    YDELP0-1 
       LDA    #$10 
       STA    HGRAP1+3  ;$10 = the warp graphic class
       LDA    #$0D 
       STA    XDELP0-1 
       LDA    RANDOM 
       AND    #$03 
       ORA    #$10 
       BNE    NEWB28  ;JMP -- leave a small random X drift in A for the shared tail
NEWB27
       CMP    #$A8  ;below $A8 = ordinary space enemies
       BCC    NEWB76
; MOONS.  Fixed distance band chosen from the throttle, X near the camera.
;   MOONS
;  MOON ZPOS
       LDY    #$28  ;far band
       LDA    IQWARP 
       ADC    #$1F    ;C=1 -- at low throttle use the near band instead
       BPL    NEWB69
       LDY    #$18  ;near band
NEWB69
       STY    ZPOSP0-1,X
;  MOON HPOS
       LDA    RANDOM  ;X = a random offset either side of the camera
       LSR
       ADC    #$10 
       ADC    CENTER 
       ROR
       JMP    NEWB31
; SPACE ENEMIES.  Optionally flip GAMEST bit 7 ("wander"), which makes the
; object drift aimlessly instead of attacking.  NEWTB5 gives the per-class
; wander probability and the easiest tier never wanders at all.
NEWB76
;  SPACE GUYS ONLY
;  WANDER STUFF
       LSR  ;descriptor bits 5..3 select the wander probability entry
       LSR
       LSR
       AND    #$07 
       TAY
       LDA    NEWAVE 
       BEQ    NEWB29  ;NO WANDER -- difficulty tier 0: never wander
       ASL    GAMEST  ;rotate the old wander flag out...
       BCS    NEWB91
       LDA    RANDOM 
       CMP    NEWTB5,Y  ;...roll a new one against NEWTB5...
NEWB91
       ROR    GAMEST  ;...and rotate it back into GAMEST bit 7
; Distance and X placement.  Y (0..3) is the JUMP QUALITY from GAMEST -- how
; accurately you arrived in this sector.  A bad jump drops enemies closer and
; more spread out.
NEWB29
;   ENTRY FROM LZ
; SHIP ZPOS
       LDA    GAMEST  ;jump quality 0..3
       AND    #$03 
       TAY         ;JMP QUALITY
NEWB10
;  ENTRY FROM PLANET GUYS
       LDA    NEWTB3,Y  ;NEWTB3[quality] = base distance
       STA    ZPOSP0-1,X
; SHIP HPOS
       LDA    RANDOM  ;random X spread, masked and biased per quality
       AND    NEWTB4,Y
       ADC    NEWT10,Y
       LSR
       BCC    NEWB32  ;mirror it to the other side of the camera half the time
       EOR    #$FF 
NEWB32
       ADC    CENTER  ;make it relative to the camera
NEWB31
       STA    HHORP0-1,X
       LDA    RANDOM  ;add a little random depth jitter
       AND    #$0F 
       ADC    ZPOSP0-1,X
       STA    ZPOSP0-1,X
       LDA    IQWARP  ;closing speed comes from the throttle...
       BPL    NEWB70
       CMP    #$F0 
       BCS    NEWB70
       LDA    #$10  ;...clamped to a minimum so nothing hangs motionless
NEWB70
       AND    #$1F 
       STA    ZDELP0-1,X  ;commit the closing speed
       LDA    #$00 
       STA    YDELP0-1,X
NEWB28
       STA    XDELP0-1,X  ;commit the horizontal drift
       LDA    TEMP10 
       CMP    #$CB  ;$CB was the fallback descriptor: retry next frame, so do not
;   advance the VM program counter.
       BEQ    NEWB92   ;NO INC IQPNTR
       INC    IQPNTR  ;normal case: consume this descriptor
; ---- FLIGHT PATH -----------------------------------------------------------
NEWB92
       LDA    RANDOM 
       LDY    PROGST 
       CPY    #$40  ;PROGST == $40 exactly means TRENCH
       BNE    NEWB44
       LDY    #$4C  ;in the trench everything flies down the same fixed lane
       STY    HHORP0-1,X
       BNE    NEWB43   ;JMP
NEWB44
       AND    #$09  ;otherwise pick a random path id, with the phase counter preset
       ORA    #$C0 
NEWB43
       STA    IQPATH-1,X  ;commit obj.path
NEWB75
       RTS
;
;
;
;
; GRATB3 -- per-class X nudge applied by GRAPH when computing the collision X.
; Signed bytes; see GRAP52.

GRATB3
       .byte $00,$02,$02,$FA,$FB,$FA,$FB,$FF
;
;
;
;===============================================================================
; B R A I N  --  PER-OBJECT AI, ONE OBJECT PER FRAME
;
; Called once per frame from the overscan chain.  It does three separate jobs
; that happen to share a routine:
;
;   1. SERVICE THE PENDING SWAP REQUEST left by CLOSE (labels BRAN19..BRAN17).
;      The display kernel can only draw obj[1..4] in increasing screen Y with
;      no overlap, so when CLOSE notices two objects have crossed, it files a
;      request in REQUST and BRAIN performs the actual exchange here.
;
;   2. DECIDE WHETHER TO FIRE an enemy photon (BRAN52..BRAN82).  Runs on one
;      frame in every four.
;
;   3. RUN THE AI FOR EXACTLY ONE OBJECT (BRAN70 onward).  Which object is
;      chosen by the low two bits of the frame counter, so each of the four
;      slots gets serviced every fourth frame.  This is why enemies in Solaris
;      steer in a slightly laggy, stepped way -- reproduce the 4-frame
;      round robin if you want the original feel.
;
; The AI itself is table dispatched: the object CLASS indexes BRNTB4 to pick
; one of a dozen behaviour handlers (BRAN11 = generic ship, BRAN15 = moon,
; BRAN31 = blockader, BRAN32 = planet/terrain, BRAN36 = photon, ...).
;
; The generic ship handler is the interesting one.  Its model is:
;   - obj.path (low nibble) selects a row in BRNTB1/BRNTB2/BRNTB3, which give
;     a target Z, a target Y and a target X respectively, plus per-axis speed
;     limits.  That triple IS the flight path.
;   - the high nibble of obj.path is a phase counter; when it overflows, the
;     path either advances (BRNT12) or is re-rolled (BRNT13).
;   - each axis then runs the DIVIDE -> PREHLP -> POSTHP pipeline (header
;     section 3) to slew the current velocity toward the target.
;
; Python sketch:
;
;   def brain(frame):
;       service_swap_request()
;       if frame % 16 == 3: maybe_fire_photon()
;       i = 1 + (frame & 3)
;       HANDLER[class_of(objs[i])](i)
;       resolve_vertical_order(i)
;===============================================================================
BRAIN
;  EVERY FRAME
       LDA    PROGST  ;Skip all AI while the chart or the hyperwarp screen is up.
       AND    #$30  ;CHART,HYPER
       BNE    BRAN99
; ---- 1. SWAP REQUEST SERVICE ----------------------------------------------
; REQUST was filled in by CLOSE.  Low 3 bits = the slot, bit 7 and bit 6 pick
; which of three exchange styles to perform.
;    EXCHANGE REQUEST
       BIT    PROGST  ;V = surface mode; surfaces never file swap requests.
       BVS    BRAN20  ;PLANET/TRN
       LDA    REQUST  ;nothing pending
       BEQ    BRAN20
       AND    #$07  ;low 3 bits = the slot index
       TAX
       BIT    REQUST  ;bit 7 -> the forced swap at BRAN17
       BMI    BRAN17
       BVS    BRAN19  ;bit 6 -> the graphic-aware swap at BRAN19
; Simple exchange: nudge this object up 2 scanlines and swap it with the one
; above, using the no-vertical-exchange variant so the nudge sticks.
;  SIMPLE EXCHANGE
       LDA    HVERP0-1,X
       SEC
       SBC    #$02 
       STA    HVERP0-1,X
       INX
       JSR    EXCHN1
BRAN99
       RTS
; Graphic-aware exchange.  If the object is currently off screen (bit 7 set)
; just push it below its neighbour and do a full swap.
BRAN19
       LDA    HGRAP0-1,X
       BPL    BRAN18
       LDA    HVERP0+0,X
       CLC
       ADC    #$03 
       STA    HVERP0-1,X
       INX
       JMP    EXCHNG
BRAN18
       AND    #$7F  ;strip the off-screen bit to get the real class
       TAY
       AND    #$78 
       CMP    #$38  ;explosions are never swapped -- let them play out in place
       BEQ    BRAN20   ;EXPLOSION
       LDA    ZOOMTB,Y  ;already double-size: too big to reorder safely
       BMI    BRAN20  ;SIZE=X2
       LDA    BRNTB6,Y  ;this object height...
       AND    #$3F 
       CLC
       ADC    HVERP1+2  ;...plus the P1+2 photon Y...
       CMP    HVERP0-1,X  ;...still below the object: it is too low to bother with
       BCS    BRAN10  ;TOO LOW
       LDA    HGRAP1+3 
       CMP    #PBLK  ;the shared P1+3 slot is in use, so leave well alone
       BNE    BRAN20
       LDA    YDELP0+1,X
       CMP    #$10 
       BCC    BRAN14
       LDA    #$1A  ;DOWN -- give the neighbour a downward push...
       STA    YDELP0+1,X  ;ALSO WRITES IN ZDEL P1+3
BRAN14
       LDY    #$00 
       LDA    #$01 
       STA    ZDELP0-1,X
       LDA    #$08    ;UP -- ...and this one an upward push, so they separate visually
       STA    YDELP0-1,X
       JSR    BRAN22      ;SWAP -- perform the exchange
; Forced swap: push the object down and exchange unconditionally.
BRAN17
       TXA
       TAY
       INX
       LDA    #$18  ;DOWN
       STA    YDELP0-1,X
       JMP    BRAN29   ;SWAP
BRAN10
       LDA    ZPOSP1+1  ;cosmetic tidy-up of the far photon after a crossing
       CMP    #$20 
       BCC    BRAN20
       LDA    #$80 
       STA    ZPOSP1+1   ;COSMETIC?
; ---- 2. PHASE-GATED WORK ---------------------------------------------------
BRAN20
;
;
       LDA    PROGST  ;Skip if the game is over ($80), paused/ended ($02), or dimmed.
       AND    #$83 
       BNE    BRAN99
;  ONE GUY PER FRAME SECTION
;
       LDA    ATRACT  ;Master phase clock: this whole block runs 1 frame in 16.
       AND    #$0F 
       BNE    BRAN52
       BIT    PROGST 
       BVS    BRAN54  ;TRN/PLN
       LDY    HVERP0+0  ;slot 1 has reached the bottom of the screen
       BNE    BRAN54
; ROTATE DOWN: the bottom object has fallen off, so shuffle every object down
; one slot and open a fresh empty slot at the top.
; ROTATE DOWN
       LDX    #$02 
       JSR    EXCHNG
       INX
       JSR    EXCHNG
       INX
       JSR    EXCHNG
       LDA    #$EF  ;$EF = above the top of the screen, so GRAPH will retire it
       STA    HVERP0+3 
       RTS
BRAN54
       JMP    BRAN70
BRAN52
       CMP    #$03  ;phase 3 of 16 is the enemy fire slot
       BNE    BRAN54
; ---- ENEMY PHOTON FIRE -----------------------------------------------------
; The nearest enemy fires at you if it is close enough (the range threshold
; BRNT15 tightens with difficulty), you are alive, and the front slot is not
; already an explosion.
;  PHOTON FIRE LOGIC
       LDA    HVERP1  ;MAN DIEING -- your ship Y is 0 while you are dying: no incoming fire then
       BEQ    BRAN63
       LDA    ZPOSP0  ;how far away the front object is
       CMP    #$50  ;too far to bother
       BCS    BRAN63
       LDY    NEWAVE 
       CMP    BRNT15,Y  ;BRNT15[difficulty] = the minimum range that will fire
       BCC    BRAN63
       LDY    HGRAP0  ;front object is off screen
       BMI    BRAN63
       STA    TEMP13
       BIT    PROGST 
       BVC    BRAN49
       LSR    TEMP13  ;halve the range on a surface (the view is compressed)
       LDA    BRNTB9,Y  ;TRN/PLAN -- BRNTB9 = the surface size/flags table
       TAY
       AND    #$1F 
       ADC    #$03    ;C=1 JUMP UP FIX -- firing offset above the shooter, from the object height
       STA    TEMP4 
       TYA
       LDY    #$15 
       AND    #$40  ;bit 6 of the flags = this class is allowed to shoot
       BNE    BRAN51
BRAN63
       JMP    BRAN64
BRAN49
       LDA    BRNTB6,Y  ;space version: BRNTB6 flags, bit 7 = allowed to shoot
       CMP    #$C0 
       AND    #$3F 
       STA    TEMP4 
       BCC    BRAN63
       LDA    HVERP0+0  ;and you must be in the vertical band it can reach
       SBC    #$30 
       CMP    #$28 
       BCS    BRAN63
       LDY    #$18  ;$18 = the space photon closing speed
BRAN51
       STY    TEMP12  ;TEMP12 = the photon closing speed for this shot
; Make room for the photon by swapping the front slots down, then build it in
; slot 1.
       LDX    #$03 
       LDY    #$04 
       BIT    HGRAP0+3  ;bit 6 of the type = this slot may be reused
       BVS    BRAN81
       BIT    HGRAP0+2
       BVC    BRAN64
       DEX
       DEY
; FIRE
BRAN81
       JSR    BRAN22   ;SWAP
       DEY
       DEX
       BNE    BRAN81
       LDA    #$37  ;$37 = the enemy photon graphic
       STA    HGRAP0 
       LDA    TEMP12
       STA    ZDELP0  ;closing speed chosen above
       LDX    #$00 
       STX    YDELP0 
       LDA    CENTER  ;aim: the horizontal offset from the camera to the shooter...
       SBC    HHORP0 
       BCS    BRAN83
       EOR    #$FF 
       INX
BRAN83
       LSR  ;...scaled down to a drift rate...
       LSR
       LSR
       LDY    #$0F 
BRAN65
       ADC    #$02  ;...and iterated until the drift covers the range in time
       CMP    TEMP13  ;ZPOSP0+0 
       BCS    BRAN66
       DEY
       BNE    BRAN65
BRAN66
       INY
       TYA
       LDY    NEWAVE 
       CMP    BRNT10,Y  ;BRNT10[difficulty] caps how sharply enemies can lead the shot
       BCC    BRAN82
       LDA    BRNT10,Y
BRAN82
       EOR    BRNT14,X  ;BRNT14 applies the sign (left or right of centre)
       STA    XDELP0 
       LDA    HVERP0+1  ;start the photon just above the shooter
       SEC
       SBC    TEMP4 
       ADC    #$03    ;C=1 ,ADD 4
       STA    HVERP0+0 
;
; LSOUND -- request a sound on channel 1, but only if the channel is idle
; (CH1PTR < 2 means nothing is playing).  Y = the AUDTAB offset to play.
; LSOUN2 is the entry that requests the enemy-shot sound specifically.
LSOUN2
;  ENTRY
       LDY    #AUDSHT-J
LSOUND
       LDA    CH1PTR 
       LSR
       BNE    LSOUN1
       STY    CH1PTR 
LSOUN1
       RTS
; ---- ROTATE UP -------------------------------------------------------------
; If the top object has run off the top ($F0 or above) shuffle everything up
; and open an empty slot at the bottom.
BRAN64
       LDA    #$03 
;  ROTATE STUFF
       LDY    HVERP0+3
       CPY    #$F0 
       BCC    BRAN70
       LDA    PAUTIM  ;do not rotate while an explosion is freezing the world
       BNE    BRAN70   ;FIX EXPLOS JMP UP BUG?
; ROTATE UP
       LDX    #$04 
       JSR    EXCHNG
       DEX
       JSR    EXCHNG
       DEX
       JSR    EXCHNG
       LDA    #$01 
       STA    HVERP0+0 
       RTS
; ---- 3. AI FOR ONE OBJECT --------------------------------------------------
; X = 1 + (frame & 3): each slot is serviced once every four frames.
BRAN70
       AND    #$03  ;pick this frame slot from the frame counter
       TAX
       INX
; Prepare the perspective divide inputs shared by every handler:
;   TEMP4 = zoomed Z (distance >> 2)
;   TEMP5 = |ZDEL| scaled, i.e. the closing speed magnitude
;   PNTR1 = the sign of ZDEL ($00 or $FF), used by DIVIDE as an EOR mask
;
;  IQ STUFF
;    SETUP FOR ZOOM
       LDY    #$FF 
       LDA    ZPOSP0-1,X
       LSR
       LSR
       STA    TEMP4  ;ZOOM Z VAL -- TEMP4 = distance, scaled for the divide table
       CMP    #$10  ;too close for perspective scaling to matter
       LDA    #$00  ;NO ZOOM
       BCS    BRAN40
       LDA    ZDELP0-1,X
       ASL
       ASL
       ASL
       ASL
       BCC    BRAN41
       LDY    #$00 
       EOR    #$F0 
BRAN41
       BPL    BRAN40
       LDA    #$70  ;clamp the closing speed used for scaling
BRAN40
       STA    TEMP5  ; ABS. ZDEL, ZOOM -- TEMP5 = |closing speed|
       STY    PNTR1  ; ZDEL SIGN, ZOOM -- PNTR1 = sign mask for DIVIDE
; Dispatch on the object CLASS.  BRNTB4 holds the low byte of each handler;
; surface mode uses the NEXT entry, which is why the index is bumped by 1.
;
       LDA    HGRAP0-1,X
       AND    #$78  ;class bits
       LSR
       LSR
       TAY
       BIT    PROGST  ;V = surface mode
       BVC    BRAN43
       INY   ;PLANET/TRN -- surface variants sit at odd indices in BRNTB4
BRAN43
       LDA    BRNTB4,Y  ;low byte of the handler...
       STA    PNTR4 
       LDA    #>BRAN32  ;...high byte is the page containing BRAN32
       STA    PNTR4+1
       LDA    SHIPST  ;ship is taking off or landing: freeze the scenery
       AND    #$30 
       BEQ    BRAN58
       LDA    HGRAP0-1,X  ;DOING TAKEOFF
       BPL    BRAN47
       LDA    #PBLK  ;blank the slot so it does not fight the takeoff animation
       STA    HGRAP0-1,X
BRAN58
       LDA    #$27  ;classes below $27 are visible enemies
       CMP    HGRAP0-1,X
       LDA    GAMEST 
       BPL    BRAN56
;   WANDER
       BCC    BRAN47   ;NOT VISIBLE -- wandering and not visible: keep wandering
       AND    #$7F  ;it became visible, so stop wandering and attack
       STA    GAMEST 
; Wandering / invisible objects get a pseudo-random path index instead of
; their real one, which is what makes them drift.
BRAN47
       TYA
       EOR    GAMTIM  ;mix in the game clock so the drift changes over time
       AND    #$03  ;RANDOM PATH
       BPL    BRAN55   ;JMP
BRAN56
       LDA    IQPATH-1,X  ;normal case: obj.path low nibble...
       AND    #$07 
       CLC
       ADC    BRNT11,Y  ;...plus BRNT11[class] = the first path row for this class
BRAN55 
       STA    TEMP13   ;PATH PNTR -- TEMP13 = the chosen path row index for the whole handler
       LDA    #$00 
       JMP.ind (PNTR4)  ;vectored call into the per-class handler
;
;
;
; ---- HANDLER: ENEMY PHOTON -------------------------------------------------
; Photons do not steer horizontally; they only track vertically toward you.
BRAN36
;  PHOTON TYPE
       STA    JOYRMV
       JMP    BRAN38
;
;
; ---- HANDLER: BLOCKADER ----------------------------------------------------
; Drifts sideways away from the camera, faster on higher difficulty.  Makes a
; sound when it reaches the camera plane.
BRAN31
;  BLOCK TYPE
       LDA    ZPOSP0-1,X  ;reached the camera plane
       BNE    BRAIN7
       JSR    LSOUN2
BRAIN7
       LDA    NEWAVE  ;drift rate rises with difficulty
       ADC    #$03    ;C=0
       LDY    HHORP0-1,X
       CPY    CENTER  ;drift away from whichever side of the camera it is on
       BCC    BRAN15
       EOR    #$FF 
;
;
; ---- HANDLER: MOONS AND OTHER SCENERY --------------------------------------
; Scenery does not chase you.  It just closes at a speed derived from the
; throttle and slides sideways under perspective.
BRAN15
;  MOON TYPE
       STA    JOYRMH
       LDA    IQWARP  ;throttle, treated as a signed approach rate
       CMP    #$80 
       ROR
       SEC
       SBC    #$02 
       TAY
       CPY    #$F7  ;the very top of the throttle range gets a special closing speed
       BCC    BRAN48
;  SPECIAL MOON ZDEL FIX
       LDA    BRNTB8-$F7,Y  ;BRNTB8 = the fixed closing speeds for maximum throttle
       STA    TEMP5 
       TYA
BRAN48
       JSR    ZHELP2  ;pack the desired closing speed
       LDA    ZDELP0-1,X
       JSR    POSTH1  ;slew toward it
       STA    ZDELP0-1,X
;
; Horizontal: pure perspective drift plus the camera motion this frame.
; XDEL MOON
       SEC
       LDA    HHORP0-1,X
       SBC    CENTER 
       JSR    DIVIDE  ;perspective drift from the offset to the camera
BRAN35
       CLC
       ADC    JOYRMH  ;plus how much YOU moved horizontally
       JSR    PREHL5   ;PACK -- pack it
       LDA    XDELP0-1,X
       JSR    POSTH1
       STA    XDELP0-1,X
;
; Vertical: converge on the vanishing point VCENT.
; YDEL MOON
BRAN38
       SEC
       LDA    HVERP0-1,X
       SBC    #VCENT  ;offset from the vertical vanishing point
       JSR    DIVIDE
       CLC
       ADC    JOYRMV  ;plus how much YOU moved vertically
       JSR    PREHL5  ;PACK
       LDA    YDELP0-1,X
       JSR    POSTH1
       BCC    BRAIN2  ;JMP
;
;
; ---- HANDLER: EMPTY SLOT ---------------------------------------------------
; Zero every velocity and fall into the swap logic, which will call NEWOBJ.
BRAN30
; PBLK TYPE
       STA    ZDELP0-1,X
       STA    XDELP0-1,X
BRAIN2
       STA    YDELP0-1,X
;
; ---- HANDLER: WARP GRAPHIC -------------------------------------------------
; Purely decorative; it is driven by SHPSRV, so skip straight to the swap
; logic.
BRAN42
; WARP GRA TYPE
       JMP    BRAN46
;
;
; ---- HANDLER: TRENCH TOWER -------------------------------------------------
; Clears the phase counter so a tower never re-rolls its path, then behaves
; like terrain.
BRN100
;  TRN TOWER
       LDA    IQPATH-1,X
       AND    #$E0 
       STA    IQPATH-1,X
;
; ---- HANDLER: PLANET / TERRAIN ---------------------------------------------
; Terrain closes at the throttle speed and, in the trench, steers toward a
; lane derived from its path byte.
BRAN32
; PLANET TYPE
       LDA    IQWARP  ;closing speed follows the throttle directly
       JSR    ZHELP1  ;SLOW AND PACK
       LDA    ZDELP0-1,X
       JSR    POSTH1
       STA    ZDELP0-1,X
       LDA    #$00 
       LDY    PROGST 
       CPY    #$40  ;PROGST == $40 exactly = trench
       BNE    BRAN35
;  TRENCH
       STA    TEMP10   ;A=0
       LDA    #$F9 
       SBC    IQWARP   ;C=1 -- maximum lateral speed falls as the throttle rises
       STA    TEMP7   ;MAX SPEED
       LDA    #$4C  ;default lane: centre of the trench
       BCC    BRAN89
       LDY    ZPOSP0-1,X
       CPY    #$54  ;close enough to matter: pick a lane from the path byte
       BCS    BRAN89
       LDA    IQPATH-1,X
       LSR
       LSR
       ADC    #$2B 
BRAN89
;  A=DEST
       JMP    BRAN21  ;A = the target X; join the shared steering tail
;
;
; ---- HANDLER: DARTER -------------------------------------------------------
; Below graphic $14 it is still warping in, so it does not steer yet.
BRAIN9
;  DARTER
       LDA    HGRAP0-1,X
       CMP    #$14 
       BCC    BRAN42   ;WARP IN
;
;
; ---- HANDLER: GENERIC ENEMY SHIP (the main one) ----------------------------
; Path bookkeeping, then three axes of steering.
BRAN11
;  SHIP TYPE
       LDA    PROGST  ;in the trench, ships behave as terrain instead
       CMP    #$40 
       BEQ    BRN100  ;TRENCH
; PATH PHASE.  Add $10 to the phase nibble every other frame; on overflow
; either advance to the next path row (BRNT12) or roll a brand new one
; (BRNT13).  BRNTB1 bit 0 chooses which.
;    PATH LOGIC
       STY    TEMP11
       LDY    TEMP13 
       LDA    ATRACT  ;re-sync all objects periodically so they do not drift apart
       AND    #$FC 
       CMP    #$F0 
       BEQ    BRAN73  ;RE-SYNC
       AND    #$04  ;only advance the phase every other frame
       BNE    BRAN72
BRAN73
       ORA    IQPATH-1,X
       CLC
       ADC    #$10  ;bump the phase nibble
       STA    IQPATH-1,X
       BCC    BRAN72  ;no overflow: nothing more to do
       LDA    BRNTB1,Y  ;BRNTB1 bit 0 = advance vs re-roll
       LSR
       LDY    TEMP11
       BCS    BRAN74
; Advance: step the path index by the amount in the high nibble of BRNT12.
;  INC PATH
       SEC
       LDA    BRNT12,Y
       AND    #$F0 
       ADC    IQPATH-1,X
       JMP    BRAN75
; Re-roll: BRNT13 is a random mask.  A negative mask means this object is done
; and should be removed instead.
BRAN74
;  NEW PATH
       LDA    BRNT13,Y   ;MASK
       BPL    BRAN78
       STA    HGRAP0-1,X   ;DARTER OFF -- negative mask = retire the object (used by the darter)
       JMP    BRN105   ; NEWOBJ?
BRAN78
       AND    RANDOM  ;random bits within the mask...
       ORA    BRNT12,Y  ;...ORed with the base path from BRNT12
       CPY    #$06    ;WARPER -- path row 6 is the hyperwarper
       BNE    BRAN75
       LDY    NEWAVE 
       SBC    BRNT16,Y   ;C=1 -- BRNT16[difficulty] biases how fast warpers act
BRAN75
       STA    IQPATH-1,X
; ---- Z (closing speed) -----------------------------------------------------
BRAN72
; ZDEL STUFF
       LDA    IQWARP  ;the throttle sets the baseline closing speed for everything
       CLC
       ADC    #$07 
       STA    TEMP10 
       LDY    TEMP13
       LDA    BRNTB1,Y  ;BRNTB1[path] = the target Z, low nibble = the Z speed limit
       TAY
       AND    #$0F 
       STA    TEMP7 
       TYA
       BMI    BRAN87
       LDY    NEWAVE 
       CMP    BRNT17,Y  ;BRNT17[difficulty] caps how fast enemies may close
       BCC    BRAN87
       LDA    BRNT17,Y
BRAN87
       SEC
       SBC    ZPOSP0-1,X  ;error = target Z minus current Z
       JSR    ZHELP  ;pack the desired closing speed
       SEC         ;DEFINE C=TYPE 2 -- C=1 selects the type 2 response curve
       LDA    ZDELP0-1,X
       JSR    POSTHP  ;two POSTHP calls in a row = type 2 (double) acceleration
       JSR    POSTHP   ;TWICE FOR TYPE 2 MOTION
       STA    ZDELP0-1,X
; Known bug workaround: an object that has wrapped past the camera from behind
; gets teleported to one side so it does not appear to fly through you.
;
; FROM BEHIND KLUDGE FIX
       AND    #$1F 
       CMP    #$10 
       BCS    BRAN12
       LDA    ZPOSP0-1,X
       CMP    #$F8  ;wrapped around past the camera
       BCC    BRAN12
       LDA    HHORP0-1,X
       CMP    #$50  ;move it to whichever side is further away
       LDA    #$A0 
       BCS    BRAN13
       LDA    #$00 
BRAN13
       STA    HHORP0-1,X
BRAN12
; ---- X ---------------------------------------------------------------------
;
;  XDEL STUFF
       SEC
       LDA    HHORP0-1,X  ;offset from the camera...
       SBC    CENTER 
       JSR    DIVIDE   ;ZOOM -- ...divided by distance to get the perspective drift
       CLC
       ADC    JOYRMH   ;JOYSTK -- plus your own motion, counted twice (the camera parallax is
;   deliberately exaggerated so enemies feel like they react to you)
       ADC    JOYRMH   ;ADD TWICE
       STA    TEMP10 
       LDY    TEMP13
       LDA    BRNTB2,Y  ;BRNTB2[path] = the target Y (fetched here, used below)
       STA    TEMP12
       LDA    BRNTB3,Y  ;BRNTB3[path] = the target X, low nibble = the X speed limit
       AND    #$0F 
       STA    TEMP7 
       CPY    #PH6-Q  ;path rows at PH6 and beyond are the horizontal warpers
       BCC    BRAIN1
       LDA    RANDOM   ;HWARPER -- warpers pick their side at random
       AND    #$20 
       BCS    BRAN69   ;JMP
BRAIN1
       LSR
       LDA    IQPATH-1,X  ;obj.path bit 3 mirrors the whole path left-right
       AND    #$08 
       BEQ    BRAN69
       LDA    #$FF     ;REFLECT
BRAN69
       EOR    BRNTB3,Y  ;apply the target X (and the mirror)
       BCS    BRAN62
       ADC    #$50  ;non-mirrored paths are relative to a fixed screen position...
       JMP    BRAN21
BRAN62
       ADC    CENTER  ;...mirrored ones are relative to the camera
; BRAN21 is the shared entry for "A = the target X", used by the terrain
; handler too.
BRAN21
       LDY    RTIMER  ;Bail out if the frame is nearly over -- this routine is long and
;   overrunning the timer would corrupt the display.  The object simply does
;   not steer this frame.
       CPY    #$0A 
       BCS    BRN101
       RTS       ;ABORT
BRN101
       SEC
       SBC    HHORP0-1,X  ;error = target X minus current X
       JSR    PREHLP  ;pack the desired horizontal speed
       LSR    TEMP12  ;DEFINE C -- BRNTB2 bit 0 selects the response curve for X
       LDA    XDELP0-1,X
       JSR    POSTHP
       STA    XDELP0-1,X
; ---- Y ---------------------------------------------------------------------
;
;  YDEL STUFF
       SEC
       LDA    HVERP0-1,X
       SBC    #VCENT  ;offset from the vertical vanishing point
       JSR    DIVIDE   ;ZOOM
       CLC
       ADC    JOYRMV
       ADC    JOYRMV  ;TWICE WHY? -- your own vertical motion, again counted twice
       STA    TEMP10 
       LDA    TEMP12
       ASL  ;the Y target is BRNTB2[path] shifted up one bit
       TAY
       AND    #$0F 
       STA    TEMP7 
       TYA
       SEC
       SBC    HVERP0-1,X
       JSR    PREHLP
       LDA    YDELP0-1,X
       LDY    PAUTIM  ;during an explosion pause, use the gentle response curve
       CPY    #$01   ;C=0=TYPE 1
       JSR    POSTHP
       STA    YDELP0-1,X
;
;
;-------------------------------------------------------------------------------
; SWAP LOGIC  --  keeps obj[1..4] sorted by screen Y with no vertical overlap.
;
; This exists ONLY because the display kernel reuses a single hardware player
; for all five P0-class objects.  It is nevertheless load-bearing gameplay:
; it is what causes enemies to visibly shuffle past each other, and it is the
; hook that calls NEWOBJ when a slot turns out to be empty.
;
; Three outcomes:
;   - slot is empty            -> ask NEWOBJ to fill it (BRAN50)
;   - slot overlaps a neighbour-> exchange them (BRAN22)
;   - nothing to do            -> return
;-------------------------------------------------------------------------------
BRAN46
;
;  SWAP LOGIC
       LDA    HGRAP0-1,X  ;is this slot empty?
       CMP    #PBLK
       BNE    BRAN23
; EMPTY SLOT.  Decide whether to spawn something here.
BRN105
; EMPTY
       LDY    HGRAP1+3  ;look at the shared P1+3 slot
       BPL    BRAN24
       CPY    #PBLK  ;P1+3 is busy, so a new object here would collide visually
       BNE    BRAN26
BRAN50
       JMP    NEWOBJ  ;THE SPAWN CALL.  X is still the empty slot index.
; P1+3 has run off the top: cascade every slot upward to close the gap.
BRAN26
;  OFF SCREEN
       LDA    HVERP1+3
       CMP    #TOPSCN
       BCC    BRAN98
BRAN16
       CPX    #$04 
       BEQ    BRAN85
       TXA
       TAY
       INX
       JSR    BRAN29
       JMP    BRAN16
; P1+3 is on screen.  Check that a new object would actually fit between it
; and this slot before deciding.
BRAN24
; ONSCREEN
       CPY    #$48   ;SATURN STUFF -- Saturn and the big moons are always allowed to spawn
       BCS    BRAN50
       LDA    BRNTB6,Y
       AND    #$3F 
       CLC
       ADC    HVERP0-2,X  ;NO LOAD P0+0 BUG -- Doug note: this reads HVERP0-2,X rather than HVERP0+0,X.  The
;   original comment flags it as a known bug that shipped.
       BCS    BRAN98  ;OOPS LOOK OUT! -- carry out of the add: overflowed the screen
       CMP    HVERP1+3
       BCS    BRAN98
       CPX    #$04 
       BCS    BRAN85
       LDA    HGRAP0,X
       AND    #$7F 
       TAY
       LDA    BRNTB6,Y
       AND    #$3F 
       ADC    HVERP1+3    ;C=0 
       CMP    HVERP0,X ;2PBLKS IN A ROW -- two empty slots in a row: safe to cascade
       BCC    BRAN85
       LDA    HGRAP0-2,X
       CMP    #PBLK
       BNE    BRAN98
       TXA
       TAY
       INX
       BCS    BRAN22  ;C=1,JMP SWAP
BRAN85
       LDA    #$80  ;mark the top of the chain so GRAPH retires it
       STA    YDELP0-1 
       TXA
       TAY
       LDX    #$00 
       BEQ    BRAN22  ;JMP SWAP
;
; OCCUPIED SLOT.  Decide whether it has crossed a neighbour and must be
; exchanged.  SWAPT2..SWAPT5 are per-slot Y thresholds that define the band
; each slot is allowed to occupy.
BRAN23
; FULL OBJ
;  VISUAL SWAP STUFF ??
       LDY    SWAPT5-1,X  ;SWAPT5[slot] = the slot it pairs with
       BIT    PROGST 
       BVC    BRAN59
;  PLANET/TRN
       LDA    ZPOSP0-1,X
       CMP    #$77  ;very distant surface objects never swap
       BCS    BRAN25
       LDA.wy HGRAP0-1,Y
       CMP    #PBLK
       BEQ    BRAN29
BRAN98
       RTS

; Space mode: compare this object Y against its allowed band.
BRAN59
       LDA    HVERP0-1,X
       CMP    SWAPT2-1,X  ;below the band: swap with the lower neighbour
       BCC    BRAN28
       CMP    SWAPT3-1,X  ;inside the band: nothing to do
       BCC    BRAN25
       CPX    #$01 
       BEQ    BRAN61
       LDA    HGRAP0-1,X    ;1LINE JITTER FIX -- Single-scanline jitter fix: recompute using the real object
;   height so an object exactly one line out does not oscillate.
       AND    #$7F 
       TAY
       LDA    BRNTB6,Y
       BPL    BRAN61
       AND    #$3F 
       ADC    #$01     ;C=1
       ADC    HVERP0-2,X
       CMP    HVERP0-1,X
       BCS    BRAN25   ;  END FIX
BRAN61
       LDY    SWAPT4-1,X  ;above the band: swap with the upper neighbour
BRAN28
       LDA.wy HGRAP0-1,Y  ;the swap partner must be empty...
       CMP    #PBLK
       BEQ    BRAN29
       AND    #$7F 
       STX    TEMP4 
       TAX
       LDA    SWAPT1-1,Y  ;...or at least not one of the special slots 1 and 4...
       BNE    BRAN25  ;Y NOT 1,4
       LDA    BRNTB6,X  ;...and small enough that swapping will not look wrong
       CMP    #$40    ;FIXES PHOTON OFF,ALSO
       BCS    BRAN25
       LDX    TEMP4 
;
; DO SWAP -- exchange every field of obj[X] with obj[Y], leaving obj[X] empty.
; Entry BRAN29 is the same thing.  This is the routine BRAIN, CLOSE and NEWOBJ
; all funnel into; in Python it is simply  objs[x], objs[y] = objs[y], objs[x]
; except that obj[X] is left as PBLK rather than receiving the old obj[Y].
BRAN29
;
BRAN22
;  DO SWAP
       LDA    HGRAP0-1,X
       STA.wy HGRAP0-1,Y
       LDA    #PBLK
       STA    HGRAP0-1,X
       LDA    ZDELP0-1,X
       STA.wy ZDELP0-1,Y
       LDA    XDELP0-1,X
       STA.wy XDELP0-1,Y
       LDA    YDELP0-1,X
       STA.wy YDELP0-1,Y
       LDA    IQPATH-1,X
       STA.wy IQPATH-1,Y
       LDA    HHORP0-1,X
       STA.wy HHORP0-1,Y
       LDA    ZPOSP0-1,X
       STA.wy ZPOSP0-1,Y
       LDA    HVERP0-1,X
       STA.wy HVERP0-1,Y
BRAN25
       RTS
;
;
;
;
;-------------------------------------------------------------------------------
; HYPSRV -- called every frame during HYPERWARP.
;
; Two jobs:
;   1. Cache ZOOMTB entries for the ship and the two photons so SHPSRV and the
;      kernel can scale them without repeating the lookup.
;   2. While the hyperwarp screen is up, pull the two photon "stars" down the
;      tunnel: subtract a zoom-derived amount from YDEL and decrement ZDEL,
;      which is what produces the streaking star effect.
; Falls through into GRAPH when the hyperwarp screen is NOT up.
;-------------------------------------------------------------------------------
HYPSRV
       LDX    HCOLP1+1  ;ship takeoff Z, cached for SHPSRV
       LDA    ZOOMTB,X
       STA    HOLDM0   ;FOR SHPSRV
       LDX    ZPOSP1 
       LDA    ZOOMTB,X
       STA    VECTP1  ;near photon zoom
       LDX    ZPOSP1+1 
       LDA    ZOOMTB,X
       STA    VECTP1+1  ;PHOTONS -- far photon zoom
;
       LDX    #$01 
       LDA    PROGST 
       AND    #$10  ;PROGST bit 4 = hyperwarp screen active
       BEQ    HYPSR1
HYPSR2
       LDY    ZDELP0,X
       LDA    ZOOMTB,Y
       LSR
       LSR
       LSR
       LSR
       AND    #$07 
       EOR    #$FF  ;negate so the following ADC subtracts
       SEC
       ADC    YDELP0,X
       BPL    HYPSR4
       LDA    #$00  ;clamp at zero rather than wrapping
HYPSR4
       STA    YDELP0,X
       DEY
       BEQ    HYPSR3
       STY    ZDELP0,X
HYPSR3
       DEX
       BPL    HYPSR2
       RTS
HYPSR1
;  FALL THRU
;
;
;
;===============================================================================
; G R A P H  --  ANIMATION FRAME SELECTION AND OFF-SCREEN CULLING
;
; Runs once per frame over all five slots (X = 4 down to 0).  For each object:
;
;   1. Decide whether it is still visible.  Not visible means ZPOS >= ZVIS, or
;      Y >= TOPSCN, or X outside 4..$9B.  Invisible objects are either shrunk
;      to their smallest graphic or retired to PBLK.
;   2. If visible, pick the ANIMATION FRAME.  The frame number is a function of
;      distance (ZPOS >> 2, clamped to $13) run through a per-class handler
;      chosen from GRATB6.  The handler writes the low 3 bits of the type byte.
;   3. Compute HHITP0, the X coordinate used for collision next frame.  This is
;      the object X plus a per-class nudge, because the visible sprite is not
;      centred on the logical X.
;   4. Track TARNUM, the slot the scanner locks onto: the nearest object of a
;      class below $40 (i.e. a real ship, not scenery).
;
; It also applies two small motion effects that logically belong to the AI but
; are cheaper to do here: a downward vector nudge in space (GRAPH1) and a path
; bit forced on in surface mode (GRAPH3).
;
; INPUTS   TEMP5 = the slot the caller wants left alone; TEMP6 = current best
;          scanner distance; X = 1 on entry from HYPSRV.
; OUTPUTS  HGRAP0-1,X updated animation frame or PBLK, HHITP0-1,X collision X,
;          TARNUM.
;
; NOTE the warning at GRAPH1: the V flag is set ONCE at the top of the loop and
; every handler relies on it still meaning "surface mode" when it runs.  In
; Python just pass a boolean.
;===============================================================================
GRAPH
;  ANIMATION HANDLER
;  X=1
       STX    TARNUM   ;DEFAULT -- default scanner target
       LDX    #$04 
GRAPH1
       BIT    PROGST  ;DEFINE V FOR PLN/TRN -- V = surface mode, and it must stay valid all the way down
;   WARNING DONT REDEFINE V FLAG
       CPX    TEMP5  ;leave the caller reserved slot alone
       BCS    GRAPH2
       TXA
       BEQ    GRAPH2
       BVS    GRAPH3
; Space only: nudge YDEL downward a notch so free-floating objects sink.
;  VECTOR DOWN STUFF
       LDA    YDELP0-1,X
       EOR    #$1F 
       CMP    YDELP0-1,X
       BCC    GRAPH2  ;JMP GRAPH2
       STA    YDELP0-1,X
       BCS    GRAPH2   ;JMP GRAPH2
; Surface only: force the two low path bits on, which pins terrain to its lane.
GRAPH3
;  PLN/TRN
       LDA    IQPATH-1,X
       ORA    #$03 
       STA    IQPATH-1,X
GRAPH2
       LDA    HGRAP0-1,X  ;empty slot: nothing to animate
       CMP    #PBLK
       BEQ    GRAPH4
       AND    #$7F  ;strip the off-screen bit
       LDY    ZPOSP0-1,X
       CMP    #$40  ;classes below $40 are ships, i.e. valid scanner targets
       BCS    GRAPH5
       CPY    TEMP6  ;is it nearer than the best so far?
       BCC    GRAPH5
       STY    TEMP6 
       STX    TARNUM  ;NEW TARNUM -- new scanner lock
GRAPH5
; VISIBILITY TEST.  Any failure jumps to GRAPH6.
;  OFFSCN CHECK
       CPY    #ZVIS  ;too far away
       BCS    GRAPH6
       LDY    HVERP0-1,X
       CPY    #TOPSCN  ;above the top of the screen
       BCS    GRAPH6
       LDY    HHORP0-1,X
       CPY    #$04    ;BIG MOONS FIX -- off the left edge (the extra margin is a big-moon fix)
       BCC    GRAPH6
       CPY    #$9C  ;off the right edge
       BCS    GRAPH6
; ON SCREEN: dispatch to the per-class animation handler.
;  ONSCREEN
       STA    HGRAP0-1,X
       AND    #$78  ;TEMP7 = the class bits, restored by the handler tail
       STA    TEMP7 
       LSR
       LSR
       TAY
       BVC    GRAPH7  ;surface variants sit at odd indices in GRATB6
       INY   ;PLN/TRN
GRAPH7
       LDA    GRATB6,Y  ;low byte of the handler...
       STA    PNTR4 
       LDA    GRATB7,Y  ;...and GRATB7 supplies the 9th address bit so the 24 handlers
;   can straddle a page boundary.  Pure PLUMBING.
       ASL
       LDA    #[>GRAP23]/2
       ROL
       STA    PNTR4+1
       LDA    ZPOSP0-1,X  ;distance drives the animation frame
       BVC    GRAPH8
       TAY  ;PLN/TRN
       LDA    SURTB2,Y  ;on a surface the object also sits on the horizon line SURTB2[z]
       STA    TEMP12
       TYA
       LSR
GRAPH8
       LSR
       CMP    #$13  ;20 animation steps maximum
       BCC    GRAPH9
       LDA    #$13 
GRAPH9
       TAY
       JMP.ind (PNTR4)  ;vectored call into the handler; Y = the frame index 0..$13
;
; OFF SCREEN.  Shrink to the smallest size; if that is still past POFF, or we
; are on a surface, retire the slot entirely.
GRAPH6
;  OFFSCREEN
       ORA    #$87  ;DEFAULT SMALL SIZE -- smallest size variant of this class
       CMP    #POFF
       BCC    GRAPH4
       BVS    GRAPH4
GRAP10
       LDA    #PBLK
GRAPH4  ;commit (PBLK if retired)
       STA    HGRAP0-1,X
       BVC    GRAP11
       LDY    ZPOSP0-1,X  ;surface objects still get parked on the horizon line...
       CPY    #ZVIS
       BCC    GRAP69
       LDY    #ZVIS-1
GRAP69
       LDA    SURTB2,Y  ;...so they reappear correctly when they come back into range
       STA    HVERP0-1,X
GRAP11
       JMP    GRAP12
;
;
; ---- HANDLER: SATURN RINGS -------------------------------------------------
; The rings are drawn in the shared P1+3 slot, so this handler copies the
; object position into P1+3 and turns itself off if it reached the top.
GRAP20
;  RINGS
       LDA    HGRAP1+3 
       AND    #$7F 
       CMP    #$48 
       BCC    GRAP40
       LDA    #$48 
       STA    HGRAP1+3 
       LDA    HHORP0-1,X
       STA    HHORP1+3 
       LDA    ZPOSP0-1,X
       STA    ZPOSP0-1 
       LDA    HVERP0-1,X
       SBC    #$01    ;C=1
       STA    HVERP1+3
       CMP    #TOPSCN-3
       BCS    GRAP10   ;TURN OFF
GRAP40
       JMP    GRAP36
;
;
; ---- HANDLER: PLANET PIRATE ------------------------------------------------
GRAP24
; PLNPIR
       LDA    TEMP4 
       JMP    GRAP70
;
; ---- HANDLER: BLOCKADER ----------------------------------------------------
GRAP26
;  BLOCK
       LDA    TEMP11
       JMP    GRAP65
;
; ---- HANDLER: SPACE FIGHTER AND FRIENDS ------------------------------------
; Animation phase comes from TEMP4/TEMP11/TEMP13, three free-running counters
; MOVER derives from the frame clock, so all objects of a class animate in
; step.  Near the camera the phase is used directly; past frame 9 it is
; reduced to a single bit so distant sprites do not flicker.
GRAP23
;  SPACE FIGHT, ETC
       LDA    TEMP4 
GRAP65
       CPY    #$09  ;ZOOM ADJ -- close up: full animation
       BCC    GRAP61
       AND    #$01  ;far away: two frames only
       CPY    #$0E  ;ZOOM ADJ
       JMP    GRAP60
;
; ---- HANDLER: THE MAN ------------------------------------------------------
; On the surface the man is decorative, but IN THE TRENCH he is the moving
; wall segment: this handler derives VWALL (the trench wall position) from his
; Y and pushes a matching wind velocity into YDELP0-1.
GRAP21
;  MAN
       LDA    PROGST 
       AND    #$FD 
       CMP    #$40 
       BNE    GRAP22
;  IN TRENCH
       LDA    ATRACT  ;update on alternate frames only
       LSR
       BCC    GRAP22
       LDA    PNTR3  ;VERT
       ADC    #$04  ;C=1
       AND    #$FE 
       CMP    #$56 
       BCS    GRAP22
       CMP    #$0C 
       BCC    GRAP22
       STA    VWALL  ;VWALL = the trench wall position for the kernel and for HITSRV
       LDA    GAMEST 
       LSR
       LDA    VWALL 
       BCS    GRAP54
       ADC    #$56 
       LSR
GRAP54
       STA    YDELP0-1  ;vertical wind pushing your ship toward the wall
       DEC    YDELP0-1  ;VWIND
;
;
; ---- HANDLER: TRENCH TOWER / PLANET FIGHTER --------------------------------
GRAP22
;  TRN TOWER
       STX    TEMP5 
GRAP71
;  PLN FIGHT
       LDA    TEMP13
GRAP70
       CPY    #$11 
GRAP60
       BCC    GRAP61
       LDA    #$00 
GRAP61
       CLC
       ADC    GRATB4,Y
       BIT    PROGST 
       BVC    GRAP44  ;SPACE GUYS
       LSR
       LSR
       LSR
       LSR
GRAP44
       JMP    GRAP42
;
;
; ---- HANDLER: PLANET PHOTON ------------------------------------------------
; WARNING in the original: this handler must stay inside page 8 because
; GRATB7 only supplies one extra address bit.  PLUMBING.
GRAP29
; WARNING: IN PAGE 8!
;  PLN PHOT
       LDA    HVERP0-1,X  ;clamp the photon to the terrain height
       CMP    TEMP12
       BCS    GRAP41
       STA    TEMP12
GRAP41
       LDA    ATRACT  ;alternate two frames every other frame
       LSR
       AND    #$01 
       ORA    GRATB2,Y
       JMP    GRAP42
;
;
; ---- HANDLER: SPACE PHOTON -------------------------------------------------
; When the animation index reaches zero the photon has arrived: start an
; explosion, freeze the world for $20 frames, and switch the graphic.
GRAP28
; WARINING: IN PAGE 9!
;  SPA PHOT
       TYA
       ORA    PAUTIM  ;not yet, and not during an existing pause
       BNE    GRAP41
       LDY    #EXPREG-EXPTAB  ;load the standard explosion script
       STY    EXPNTR 
       LDA    #$20 
       STA    PAUTIM  ;freeze the world
       LDA    #$3F  ;$3F = the explosion graphic
       BNE    GRAP96   ;JMP
;
;
; ---- HANDLER: DARTER / WARP GRAPHIC ----------------------------------------
GRAP27
; DAR/WRPGRA
       LDA    HGRAP0-1,X
       CMP    #$14  ;below $14 it is still the warp-in effect
       BCC    GRAP46
;  DARTER
       LDA    #AUDVAR-J  ;the darter has its own continuous sound
       STA    CH0SHD 
       LDA    ATRACT 
       LSR
       LSR
       AND    #$01 
       ORA    #$04 
       CPY    #$10 
       BCC    GRAP42
       ORA    #$02 
       BCS    GRAP42  ;JMP
;
;
; The warp-in effect: track the P1+3 slot until the two meet, then hand the
; slot over to the real object.
GRAP46
;  WARP GRA
       STX    TEMP5 
       LDY    HVERP1+3
       STY    HVERP0-1,X
       LDY    HHORP0-1,X
       CPY    HHORP1+3 
       BCS    GRAP43
       LDA    #PBLK
       STA    HGRAP1+3 
       LDA    #$00 
       STA    XDELP0-1,X
       LDA    #$18 
GRAP96
       BNE    GRAP43    ;JMP
;
;
; ---- HANDLER: MOONS --------------------------------------------------------
; Moons have twice the frame count of anything else, so the phase byte is used
; a nibble at a time depending on the slot.
GRAP30
;  MOONS
       LDA    GRATB1,Y
       CPX    #$01 
       BCS    GRAP47
       ADC    #$04    ;C=0
       LDY    #$A0 
       STY    ZPOSP0-1 
       BNE    GRAP66   ;JMP
GRAP47
       LSR
       LSR
       LSR
       LSR
GRAP66
       AND    #$0F 
       LDY    HGRAP0-1,X
       CPY    #$54  ;the second moon set starts at graphic $54
       BCC    GRAP67
       ADC    #$0B    ;C=1
GRAP67
       ADC    #$48   ;C=0 -- moon graphics start at $48
       BNE    GRAP43  ;JMP
;
;
; ---- HANDLER: EXPLOSIONS ---------------------------------------------------
; Explosions are SCRIPTED, not procedural.  EXPNTR is a program counter into
; EXPTAB and each entry is either
;    a byte >= $80  : a new frame.  Its low 3 bits are the sprite, and the
;                     rest encodes a vertical offset applied to the object
;                     (the explosion visibly rises as it expands).
;    a byte <  $80  : a timestamp -- hold the current frame until PAUTIM
;                     counts down to this value.
;    PBLK           : end of script, the object disappears.
; The four scripts are EXPPLN (on a planet), EXPTRN (trench), EXPREG (normal)
; and EXPFAR (a distant kill).
GRAP32
;  SPA EXPLOS
       STX    TEMP5 
GRAP33
;  PLN EXPLOS
       LDY    EXPNTR 
       LDA    EXPTAB,Y  ;fetch the next script byte
       BMI    GRAP48  ;bit 7 set = a new frame
       DEY
       CMP    PAUTIM  ;timestamp: hold until PAUTIM reaches it
       BEQ    GRAP49
       BNE    GRAP50  ;JMP
GRAP48
       CMP    #PBLK
       BEQ    GRAP51
       LSR
       LSR
       LSR
       SEC
       SBC    #$18  ;decode and apply the vertical rise
       CLC
       ADC    HVERP0-1,X
       STA    HVERP0-1,X
GRAP49
       INC    EXPNTR  ;advance the explosion script
GRAP50
       LDA    EXPTAB,Y
       AND    #$07  ;low 3 bits = the sprite index
       TAY
       ORA    #$38  ;class $38 = explosion
GRAP51
       STA    HGRAP0-1,X
       BIT    PROGST 
       BVS    GRAP52
       LDA    EXPOFF,Y  ;EXPOFF gives the matching horizontal offset per frame
       BVC    GRAP53  ;JMP
;
;
; ---- HANDLERS: LANDING ZONE, CRATER, PLANET KILLER -------------------------
; Static scenery: the frame is a straight function of distance via GRATB1.
GRAP34
;  LZ
GRAP35
;  CRATER
       STX    TEMP5 
GRAP36
;  PKILLER,ETC.
       LDA    GRATB1,Y
;
; Shared tail.  GRAP42 rebuilds the type byte from the class (TEMP7) plus the
; new frame, GRAP43 commits it, then the collision X is computed.
GRAP42
       AND    #$07  ;low 3 bits = the new animation frame
       ORA    TEMP7  ;reattach the class bits
GRAP43
       STA    HGRAP0-1,X  ;commit the object type
       BIT    PROGST 
       BVC    GRAP97
; Surface objects are pinned to the horizon line computed earlier.
;  PLN/TRN
       LDA    TEMP12
       STA    HVERP0-1,X
; COLLISION X.  The visible sprite is not centred on the logical X, so a
; per-class signed nudge is added.  GRATB3 covers classes $40 and up, BRNTB9
; the rest, and a set bit 7 in the flags means a fixed -4.
GRAP52
       LDY    HGRAP0-1,X
       CPY    #$40 
       LDA    GRATB3-$40,Y
       BCS    GRAP53
       LDA    BRNTB9,Y
GRAP55
       AND    #$80 
       BEQ    GRAP53
       LDA    #$FC 
GRAP53
       CLC
       ADC    HHORP0-1,X  ;nudge + object X
       CMP    #$A0  ;wrapped past the right edge, so clamp to 0
       BCC    GRAP56
       LDA    #$00 
GRAP56
       STA    HHITP0-1,X  ;HHITP0 is what HITSRV compares against next frame
GRAP12
       DEX  ;next slot, 4 down to 0
       BMI    GRAP68
       JMP    GRAPH1
GRAP68
       RTS

; Space objects reach here instead: the nudge comes from ZOOMTB (i.e. it
; scales with the sprite width at this distance).
GRAP97
       TAY
       TXA
       BEQ    GRAP68
       LDA    ZOOMTB,Y
       BVC    GRAP55    ;JMP
;
;
;
;
;
;
;
;
;===============================================================================
; C L O S E  --  VERTICAL OVERLAP RESOLUTION
;
; The companion to BRAIN swap logic.  BRAIN reorders objects; CLOSE detects the
; situations that need reordering and files a REQUST for BRAIN to act on next
; frame, while immediately fixing up any Y values that would make the display
; kernel misbehave this frame.
;
; The invariant it maintains, for slots 1..4 walking upward:
;
;     obj[i].y + height(obj[i]) <= obj[i+1].y
;
; If an object would overlap the one above it, its Y is pushed up to the
; boundary; if that pushes it off the top of the screen, the pair is marked for
; exchange.  PNTRP1 is left holding the highest slot still on screen, which the
; planet kernel uses as its object count.
;
; Entry points:
;   CLOSE   normal entry.  Branches to CLOS30 when V says we are on a surface.
;   CLOS30  the planet/trench loop, which is a separate simpler body.
;
; REQUST encoding, consumed by BRAIN next frame:
;   bits 2..0  the slot index
;   bit 6      graphic-aware exchange
;   bit 7      forced exchange
; Larger values win, so the most urgent request survives the frame.
;
; NOTE the reading order: the surface loop body (CLOS35/CLOS33) is listed FIRST
; in the source, before the CLOSE entry point itself at CLOSE.  Read from
; CLOSE downward, then come back up here.
;===============================================================================
;
; Empty-slot case: the boundary for the next object is just one line above.
CLOS35
;  PBLK
       LDA    HVERP0-1,X
       ADC    #$01    ;C=1
       JMP    CLOS36
;
; ---- SURFACE LOOP BODY (X = 1..4) -----------------------------------------
CLOS33
       LDA    ZPOSP0-1,X  ;how close this object is to the camera
       ADC    #$10   ;C=0
       CMP    #$12 
       BCS    CLOS44  ;still far away: nothing to check
       LDA    HGRAP0-1,X
       AND    #$78 
       LDY    #ATTSB1-W   ;5 IN A ROW? -- ATTSB1 is the spawn script to run when things stack up
       CMP    #$18  ;class $18 is the man
       BCC    CLOS42
       BNE    CLOS43    ;NOT MAN
       BIT    GAMEST 
       BVS    CLOS43    ; NOT ENEMY -- the man may not trigger the enemy-planet script
       LDY    #$5F        ;ABORT ENEMY PLANET
CLOS42
       CPY    IQPNTR  ;only ever raise the script priority, never lower it
       BCS    CLOS43
       STY    IQPNTR 
CLOS43
       LDA    #PBLK  ;too crowded: clear this slot
       STA    HGRAP0-1,X
CLOS44
       LDA    HGRAP0,X
       CMP    #PBLK  ;is the object above empty?
       BEQ    CLOS35
       AND    #$7F 
       TAY
       LDA    BRNTB9,Y  ;BRNTB9 low 5 bits = object height in surface mode
       AND    #$1F 
       ADC    HVERP0-1,X    ;C=0 -- bottom of this object...
       CMP    HVERP0+0,X  ;...must not reach the object above
       BCC    CLOS31  ;NO ERROR
CLOS36
       STA    HVERP0,X  ;it did: push the object above up to the boundary
       CPX    #$03 
       BNE    CLOS51
       LDA    ZPOSP0+3
       CMP    #ZVIS-1  ;the far photon is too near to be pushed, so leave it alone
       BCS    CLOS31
CLOS51
       LDA    #$FF 
       STA    ZDELP0,X  ;NO MOVE DOWN -- $FF stops it drifting down any further this frame
CLOS31
       LDA    HVERP0+0,X ;RESTORE
       CMP    PNTR3+1    ;FROM PLNSRV -- PNTR3+1 is the kernel object limit handed over by PLNSRV
       BCS    CLOS39
       STX    PNTRP1  ;PNTRP1 = the highest slot still within that limit
CLOS39
       INX
CLOS30
;  BEGIN PLANET/TRENCH
       LDA    BRNTB9,Y
       AND    #$20  ;flags bit 5 = this class must sit on an even scanline
       BEQ    CLOS32
       LSR    HVERP0-1,X  ;force the Y even...
       SEC
       ROL    HVERP0-1,X  ;...then odd, i.e. snap it to a 2-line grid
CLOS32 CPX    #$4
       BNE    CLOS33  ;loop until all four slots are done
CLOS40
       RTS
;
;
; ---- CLOSE: the real entry point ------------------------------------------
CLOSE
       LDX    #$00    ;OLD TAX -- X = 0, the scratch slot
       LDA    HVERP0+0 
       CMP    #$F3 
       BCC    CLOS77
       STX    HVERP0+0   ;FIX JUMP UP BUG -- Y wrapped past the top: the known jump-up bug, clamped to 0
CLOS77
       STX    REQUST  ;no swap requested yet this frame
       STX    PNTRP1  ;no on-screen slot found yet
       INX
       LDA    HGRAP0 
       AND    #$7F 
       TAY
       LDA    BRNTB6,Y  ;BRNTB6 = size and flags of the front object
       STA    TEMP4  ;TEMP4 carries the PREVIOUS object flags through the loop
       BNE    CLOS34  ;height 0 means the front slot is empty...
       STA    HVERP0+0  ;...so pin its Y to 0
CLOS34
       BIT    PROGST  ;V = surface mode
       BVS    CLOS30  ;PLN/TRENCH
;
; ---- P1+3 (the shared Saturn / big moon / warp slot) -----------------------
; Clamp it so it never overlaps the far photon, and switch a big moon off
; entirely if it would.
;
;  P1+3 CHECK
       LDA    HGRAP1+3
       AND    #$7F 
       TAY
       LDA    BRNTB6,Y
       AND    #$3F 
       STA    HOLDM0  ;FOR HITS -- HOLDM0 hands this height on to HITSRV
       CLC
       ADC    HVERP1+2
       CMP    HVERP1+3  ;would it overlap the far photon?
       BCC    CLOSE1
       STA    HVERP1+3  ;yes: pull it up to the boundary
       CPY    #$40  ;classes $40 and up are the big moons...
       BCC    CLOSE1
       LDA    #PBLK  ;MOON OFF -- ...which are switched off rather than squeezed
       STA    HGRAP1+3
CLOSE21
;
; ---- SPACE LOOP over slots 1..4 -------------------------------------------
;  P0 CHECK STUFF
;
CLOSE1
       LDA    HVERP0+0,X
       CMP    #TOPSCN
       BCS    CLOSE2  ;OFFSCRN -- already off the top: handle it in the tail loop instead
;  ON SCREEN
       LDA    HGRAP0,X
       AND    #$7F 
       TAY
       LDA    BRNTB6,Y  ;size and flags of this object
       TAY
       BEQ    CLOSE3  ;PBLK -- height 0 means the slot is empty
       AND    #$3F  ;just the height
       ADC    HVERP0-1,X   ;C=0 -- bottom edge of the previous object...
       CMP    HVERP0,X  ;...versus the top of this one
       BCC    CLOSE4   ;NO ERROR -- no overlap: nothing to do
       STA    HVERP0+0,X  ;overlap: push this object up to the boundary
       CMP    #TOPSCN
       BCS    CLOSE5   ;WENT OFFSCRN -- the push took it off the top of the screen
; REQUEST LOGIC.  Which exchange style is needed depends on the flag bits of
; THIS object (in Y) and of the PREVIOUS one (in TEMP4).
;  REQUEST LOGIC
       TYA  ;Y = this object flags
       BMI    CLOSE6  ;bit 7 set: this class extends downward
       BIT    TEMP4  ;bit 7 of the previous object flags
       BMI    CLOS11
       AND    #$40  ;bit 6: a plain graphic-aware exchange
       BNE    CLOSE7
       BEQ    CLOSE4    ;JMP
; This object is a normal top-anchored one.  Only file a request if it is
; actually on screen, otherwise let it drift away.
CLOSE6
; TOP =NORMAL
       LDA    HGRAP0,X   ;NO SWAP IF OFFSCRN -- off screen: do not bother swapping
       BMI    CLOSE4
       LDA    #$40 
       BIT    TEMP4 
       BMI    CLOSE8
       BVS    CLOSE4
CLOSE7
       LDA    #PBLK  ;clear the lower slot as part of the exchange
       STA    HGRAP0-1,X
       LDA    #$80  ;$80 = the forced-exchange request style
CLOSE8
       ORA    CLSTB1-1,X  ;CLSTB1 turns the slot index into the request payload
       CMP    REQUST  ;keep only the highest-priority request this frame
       BCC    CLOSE4
       STA    REQUST 
CLOSE4       
       STX    PNTRP1  ;PNTRP1 = the highest slot still on screen
CLOSE9
       STY    TEMP4  ;carry this object flags forward as the previous ones
       INX
       CPX    #$04 
       BCC    CLOSE1
       RTS
;
; Tail loop for objects that are already off the top: pull each one down onto
; its neighbour and file a low-priority exchange request.
CLOS10
       LDA    HVERP0+0,X
CLOSE2
       CMP    HVERP0-1,X  ;is it above its neighbour?
       BCS    CLOSE5
       LDA    HVERP0-1,X
       STA    HVERP0,X  ;no: snap it down onto the neighbour
       LDA    REQUST  ;only file a request if nothing more urgent is pending
       BNE    CLOSE5
       LDA    CLSTB1-1,X
       STA    REQUST 
CLOSE5
       INX
       CPX    #$04 
       BCC    CLOS10
       RTS
;
; A downward-growing object that is also moving downward is cleared outright
; rather than exchanged -- there is nowhere for it to go.
CLOS11
       LDA    YDELP0,X
       AND    #$10  ;YDEL bit 4 = moving down
       BEQ    CLOSE4
       LDA    #PBLK
       STA    HGRAP0,X
;
; Empty-slot fixup: leave a 2-line gap so the kernel does not glitch.
CLOSE3
       LDA    #$02 
       CLC
       ADC    HVERP0-1,X
       STA    HVERP0,X
       JMP    CLOSE9
;
;===============================================================================
; T A B L E S   F O R   B A N K   1
;===============================================================================
;
;
;
;
;
;  TABLES
;
;
;
;
;-------------------------------------------------------------------------------
; TYPTAB -- THE SPAWN SCRIPTS.  This is the PROGRAM that NEWOBJ interprets.
;
; W is EQUated to TYPTAB so that every jump target can be written as
; LABEL-W, i.e. an offset from the start of the script area.  That offset is
; exactly what IQPNTR holds.  Reading a script:
;
;   BLKTYP  .byte $CA,$CA,$D6,$D6            four blockaders, then
;           .byte LVS,$00, $AB,$AB, BRN,BLKTYP+6-W
;                                            set the loop counter from
;                                            NEWT11[0+difficulty], then spawn
;                                            two more and loop that many times
;   DONTYP  .byte $A1                        one more object, then
;           .byte $C8, ENB,SHIPST,$01        and flag the sector as cleared
;
; The scripts, in the order DORTB2 selects them when you enter a sector:
;
;   FRNTYP  a FRIENDLY planet -- nothing hostile, refuel here
;   TRNTYP  the TRENCH.  TRNTY1 is the in-trench script: it pokes PROGST=$40
;           and GAMEST=$15 with STO, spawns a long run of wall segments with
;           LVS/BRN, then ENBs PROGST bit 3 at the end to switch to the
;           planet-surface phase
;   BLKTYP  blockaders
;   FIGTYP  fighters
;   ENETYP  the ENEMY planet -- ends with INL (extra life) then BLOWT2
;   PIRTYP  pirates
;   PLNTYP  a mixed planet raid
;   MONTYP  the default "empty space" script: moons and scenery on a loop
;   COBTYP  the cobra ship
;
; Also here:
;   CRATYP  craters, the default surface filler.  GTO CRATYP loops forever
;   BLOWIT / BLOWT2  poke SHIPST to start the planet blowing up
;   HYPSUB  the cross-fire interrupt: three warpers then RET
;   ATTSUB  the attack interrupt fired by SMRHLP.  Blanks the last slot, then
;           spawns attackers on a difficulty-scaled loop, then RET
;
; IRQREQ (bank 3) is how SMARTS injects one of these subroutines: it pushes the
; current PC into IQSTAK and sets IQPNTR, i.e. a software interrupt into the VM.
;-------------------------------------------------------------------------------
TYPTAB
W EQU TYPTAB  ;EQUATE
       .byte $00
;   SPACE TYPE GUYS
BLKTYP 
       .byte $CA,$CA,$D6,$D6
       .byte LVS,$00,$AB,$AB,BRN,BLKTYP+6-W
DONTYP
       .byte $A1
       .byte $C8,ENB,SHIPST,$01
MONTYP
       .byte STO,IQREAP,$04
       .byte $CA,$D6,$CA,$D6,$C2,BRN,MONTYP+3-W
       .byte $C8,ENB,GAMEST,$20,GTO,MONTYP-W
COBTYP
       .byte LVS,$0A,$92,BRN,COBTYP+2-W,GTO,DONTYP-W
PIRTYP
       .byte $89,LVS,$05,RNW,$C0,PIRTY1-W,$89,BRN,PIRTYP+6-W
       .byte GTO,DONTYP-W
PIRTY1
       .byte STO,GAMEST,$00,$8B,$8B,$8B,GTO,DONTYP-W
PLNTYP
       .byte $A1,LVS,$0A
PLNTY1
       .byte RNW,$20,PIRTY1-W,RND,$E0,BRN,PLNTY1+3-W,GTO,DONTYP-W
FIGTYP
       .byte $81,LVS,$05
FIGTY1
       .byte RNW,$20,PIRTY1-W,RND,$F0,BRN,FIGTY1+3-W,GTO,DONTYP-W
;   PLANET TYPES

FRNTYP
       .byte $A7,$9B,$C3,$C3,EMP,PBLK-1,FRNTYP+1-W,$C0,$C3
FRNTY1
       .byte $C3,ENB,GAMEST,$20
CRATYP
       .byte ENB,SHIPST,$10,$C3,GTO,CRATYP-W
TRNTYP
       .byte ENB,GAMEST,$02,$A7,$AB,EMP,PBLK-1,TRNTYP+4-W
       .byte $A8,GTO,FRNTY1-W
TRNTY1
       .byte STO,PROGST,$40,STO,GAMEST,$15
       .byte LVS,$0F,$9F,$AB,EMP,PBLK-1,TRNTY1+9-W
       .byte BRN,TRNTY1+8-W,$AB,$AB,$AB,$AB,$AB
       .byte ENB,PROGST,$08,$C0
BLOWT2
       .byte ENB,SHIPST,$41
BLOWIT
       .byte ENB,SHIPST,$50,GTO,CRATYP+3-W
;
HYPSUB
       .byte $92,$92,$92,RET
;
;  ENETYP 2ND LAST IN TYPTAB
ENETYP
       .byte LVS,$0F,$9F,RND,$E8,EMP,PBLK-1,ENETYP+3-W
       .byte BRN,ENETYP+2-W,$C0,INL,GTO,BLOWT2-W
;
;  ATTSUB IS LAST IN TYPTAB
ATTSUB
       .byte STO,HGRAP0+3,PBLK
ATTSB1
       .byte $C3,LVS,$14,RND,$EC,BRN,ATTSB1+3-W
       .byte $C0,ENB,SHIPST,$01,RET
;
;
;
; CLSTB1  slot index -> REQUST payload.
; SWAPT1  slot -> the slot it pairs with for the moon-adjacency test.
; SWAPT2  slot -> the LOW Y bound of the band that slot may occupy.
; SWAPT3  slot -> the HIGH Y bound of that band.
; SWAPT4  slot -> the partner to swap with when it is above its band.
; (SWAPT5, near the end of the bank, is the partner when it is below.)
CLSTB1 .byte $01,$02,$03
;  SHARE 1
SWAPT1 .byte $00,$01,$04
;  SHARE 1
SWAPT2 .byte $00,$32,$53,$72
SWAPT3 .byte $50,$53,$72,$FF
SWAPT4 .byte $02,$03,$04,$04
;
;
; NEWTB1  per-slot bias added to the random spawn Y.
; NEWTB5  per-class wander probability, compared against RANDOM.
; NEWTB7  the descriptor pool RND draws from (indexed from $E0).
; NEWT11  5x5: [base][difficulty] -> how many objects LVS should spawn.
;         Reading down a column shows the wave getting bigger with difficulty.
; NEWTB3  jump quality -> base spawn distance.  A clean jump puts enemies far
;         away; a bad one drops them on top of you.
; NEWTB4  jump quality -> random X spread mask (paired with NEWT10 as a bias).
NEWTB1 .byte $78,$18,$38,$59,$76
NEWTB5 .byte $E0,$D0,$00,$00,$B0
NEWTB7
       .byte $A1,$81,$89,$CB,$A3,$8B,$83,$83
       .byte $8B,$83,$83,$C3,$8B,$83,$93,$93
       .byte $81,$81,$83,$8B
NEWT11 
       .byte $1E,$28,$37,$4B,$64
       .byte $00,$00,$01,$01,$02
       .byte $01,$02,$02,$03,$04
       .byte $00,$01,$01,$02,$04
       .byte $02,$04,$05,$05,$06
NEWTB3 .byte $84,$9E,$AE,$BE,$67
NEWTB4 .byte $3F,$3F,$1F,$1F,$7F
;
;
;
; EXPTAB -- the four explosion scripts.  See the explosion handler in GRAPH for
; the byte format.  EXPPLN = on a planet, EXPTRN = in the trench, EXPREG = the
; normal space kill, EXPFAR = a kill at long range.
EXPTAB
EXPPLN .byte $C5,$1C,$C4,$19,$C3,$16,$C2,$13
       .byte $C1,$10,$C0,$0D,PBLK
EXPTRN
       .byte $C3,$1E,$C5,$C5,PBLK
EXPREG
       .byte $C7,$CE,$CD,$C4,$1A,$CB,$16,$CA
       .byte $11,$D1,$0C,$D0,$07,PBLK
EXPFAR
       .byte $C7,$1E,$CE,$C6,$CD,$C5,$C4,$15
       .byte $CB,$12,PBLK
;
;
;
;
; BRNTB9 -- OBJECT SIZE AND FLAGS, SURFACE MODE.  Indexed by the low 7 bits of
; the type byte.  Low 5 bits = height in scanlines; bit 5 = must sit on an even
; scanline; bit 6 = may fire at you; bit 7 = the collision X needs the fixed
; -4 nudge.  BRNTB6 near the end of the bank is the space-mode twin.
BRNTB9
; BRNTB6 FOR PLANET
       .byte $52,$52,$52,$4F,$4F,$0F,$0C,$0A
       .byte $53,$13,$53,$51,$11,$51,$4E,$4B
       .byte $53,$53,$53,$51,$51,$51,$0E,$0B
       .byte $14,$14,$14,$11,$11,$11,$0E,$0B
       .byte $93,$91,$90,$8F,$0E,$0D,$0C,$0B
       .byte $13,$53,$13,$11,$51,$11,$4E,$0A
       .byte $10,$0F,$10,$0F,$0E,$0D,$0C,$0B
       .byte $B9,$B7,$B5,$B3,$11,$0F,$0F,$0F
       .byte $32,$30,$2E,$8D,$8C,$8B,$8B,$0A
;
;
; BRNT15  difficulty -> minimum range at which an enemy will shoot.
; BRNT16  difficulty -> warper timing bias.
; BRNT10  difficulty -> how far an enemy may lead its shot.
; BRNT17  difficulty -> maximum closing speed an enemy may use.
; All four get HARDER as the index rises, so they are the difficulty curve.
BRNT15 
       .byte $1C,$14,$0C,$08,$04
BRNT16 
       .byte $60,$40,$30,$20
;  SHARE 1
BRNT10
; PHOT VECTORS
       .byte $00,$03,$06,$08,$0C
BRNT17
;  MAX Z GUYS
       .byte $18,$20,$28,$30,$38
;
;
;-------------------------------------------------------------------------------
; THE FLIGHT PATH TABLES.  Q is EQUated to BRNTB1 so a path row can be named
; as PHn-Q, an offset.  A path index selects one entry from each of three
; parallel tables:
;
;   BRNTB1[p]   target Z.  Low nibble also doubles as the Z speed limit;
;               bit 0 chooses "advance the path" vs "re-roll the path" when the
;               phase counter overflows; bit 7 marks a path that ignores the
;               difficulty cap.
;   BRNTB2[p]   target Y (shifted left once when used) and, in bit 0, the
;               response curve for the X axis.
;   BRNTB3[p]   target X, low nibble also the X speed limit.
;
; The named groups PH1..PH7 are the path families:
;   PH1/PH2  the basic approach and retreat
;   PH3/PH4  weaving attack runs
;   PH5      slow scenery drift
;   PH7      the cobra
;   PH6      the horizontal warpers -- must be LAST, because BRAIN tests
;            CPY #PH6-Q to detect them
;
; BRNT11  class -> the first path row for that class
; BRNT12  class -> the base path value when re-rolling (high nibble is also the
;         step used when merely advancing)
; BRNT13  class -> the random mask ORed onto that base.  A NEGATIVE value here
;         means "retire the object instead of re-rolling", used by the darter.
;-------------------------------------------------------------------------------
BRNTB1
;  ZDELST
Q EQU BRNTB1  ;EQUATE
       .byte $01,$01,$01,$01
PH1    .byte $2E,$1A,$08,$13
PH2    .byte $F4,$F4,$F3,$F7
PH3    .byte $17,$26,$36,$FC,$3D
PH4    .byte $F2,$F2,$F3,$F7
PH5    .byte $20,$06,$06,$06,$07
PH7    .byte $24,$08,$18,$05
;  LAST IN TABLE
PH6    .byte $19,$0F,$09,$1A,$FF
;
BRNTB2 
; YDEST
       .byte $C4,$C4,$E4,$E4
       .byte $46,$3E,$3C,$38
       .byte $02,$02,$02,$02
       .byte $29,$39,$3B,$37,$3B
       .byte $01,$01,$01,$01
       .byte $0E,$2E,$1E,$0E,$0E
       .byte $2B,$55,$45,$55
       .byte $28,$38,$0A,$58,$48
;
BRNTB3
; XDEST
       .byte $74,$B4,$74,$B4
       .byte $DB,$1B,$18,$FC
       .byte $1D,$F9,$E4,$24
       .byte $1D,$FD,$FD,$28,$E8
       .byte $2E,$DE,$FF,$24
       .byte $C0,$2F,$CF,$FF,$0A
       .byte $DE,$19,$25,$ED
       .byte $1D,$ED,$FD,$0D,$FD
;
BRNT11 
       .byte PH1-Q,PH2-Q,PH3-Q,PH4-Q
       .byte PH5-Q,PH2-Q,PH6-Q,$00,PH7-Q
BRNT12
       .byte $80,$C0,$80,$40,$C0,$A0,$E0,$00,$70
BRNT13 
       .byte $08,$08,$09,$08,$E0,$0B,$0B,$00,$0B
;
;
;
;
; SURTB2 -- distance -> horizon Y.  Indexed by ZPOS 0..$77, gives the screen Y
; at which an object at that distance rests on the ground.  It is a hyperbola,
; flattening toward $56 at the horizon, and it IS the surface-mode perspective.
SURTB2 
       .byte $02,$05,$08,$0B,$0E,$10,$13,$15,$17,$19,$1B,$1D,$1F,$20,$22,$24
       .byte $25,$27,$28,$29,$2B,$2C,$2D,$2E,$2F,$30,$31,$32,$33,$34,$35,$36
       .byte $37,$38,$39,$39,$3A,$3B,$3C,$3C,$3D,$3E,$3E,$3F,$40,$40,$41,$41
       .byte $42,$42,$43,$43,$44,$44,$45,$45,$46,$46,$47,$47,$47,$48,$48,$49
       .byte $49,$49,$4A,$4A,$4B,$4B,$4B,$4C,$4C,$4C,$4D,$4D,$4D,$4D,$4E,$4E
       .byte $4E,$4F,$4F,$4F,$4F,$50,$50,$50,$50,$51,$51,$51,$51,$52,$52,$52
       .byte $52,$52,$53,$53,$53,$53,$53,$54,$54,$54,$54,$54,$55,$55,$55,$55
       .byte $55,$55,$56,$56,$56,$56,$56,$56
;
;
;
; GRATB6 -- class -> low byte of the animation handler in GRAPH.  Entries
; alternate space, surface, space, surface, which is why GRAPH bumps the index
; by one when V is set.  GRATB7 (up near the top of the bank) carries the 9th
; address bit for each entry.
GRATB6
       .byte <GRAP23,<GRAP71,<GRAP36,<GRAP24
       .byte <GRAP27,<GRAP71,<GRAP23,<GRAP21
       .byte <GRAP36,<GRAP34,<GRAP26,<GRAP22
       .byte <GRAP28,<GRAP29,<GRAP32,<GRAP33
       .byte <GRAP20,<GRAP35,<GRAP30,<GRAP35
       .byte <GRAP30,<GRAP35,<GRAP30,<GRAP35
;
;
;
; NEWT10  jump quality -> bias added to the random spawn X.
; GRATB1  distance -> animation frame for static scenery, packed two per byte.
; GRATB2  distance -> animation frame for planet photons.
; NEWTB8  the two Saturn-rings graphic variants.
; GRATB4  distance -> animation frame for ships (a coarser curve than GRATB1).
NEWT10 .byte $00,$60,$C0,$DF
;  SHARE 2
GRATB1 
       .byte $00,$00,$00,$00,$11,$11,$11,$22
       .byte $22,$32,$33,$43,$43,$54,$64,$75
       .byte $85,$96,$A6,$B7
GRATB2 
       .byte $02,$02,$02,$02,$02,$02,$02,$04
       .byte $04,$04,$04,$06,$06,$06,$06,$06
       .byte $06,$06,$06,$06
;
NEWTB8 
       .byte $14,$08
;  SHARE 2
GRATB4 .byte $00,$00,$00,$00,$00,$00,$00,$00
       .byte $00,$03,$33,$33,$33,$33,$35,$35
       .byte $35,$66,$66,$77
;
;
;
;
; BRNTB4 -- class -> low byte of the AI handler in BRAIN.  Same alternating
; space/surface layout as GRATB6.
BRNTB4 
       .byte <BRAN11,<BRAN11,<BRAN11,<BRAN11
       .byte <BRAIN9,<BRAN11,<BRAN11,<BRAN32
       .byte <BRAN11,<BRAN32,<BRAN31,<BRN100
       .byte <BRAN36,<BRAN36,<BRAN30,<BRAN30
       .byte <BRAN15,<BRAN32,<BRAN15,<BRAN42
       .byte <BRAN15,<BRAN42,<BRAN15,<BRAN42
       .byte <BRAN30,<BRAN30
;
;
; BRNTB7  |velocity| -> packed 5-bit speed code.  The forward half of the
;         packing used by PREHL3.
; BRNTB8  the fixed closing speeds used by scenery at maximum throttle.
; BRNT20  |delta| -> the clamped magnitude index used by PREHLP.
BRNTB7 
       .byte $00,$01,$02,$03,$04,$05,$06,$07
       .byte $08,$08,$08,$08,$09,$09,$09,$09
       .byte $0A,$0A,$0A,$0A,$0B,$0B,$0B,$0B
       .byte $0C,$0C,$0C,$0C,$0D,$0D,$0D,$0D
       .byte $0E,$0E,$0E,$0E,$0F,$0F,$0F,$0F
BRNTB8
       .byte $70,$70,$70,$60,$50,$50,$50
;
BRNT20 
       .byte $01,$02,$02,$04,$05,$06,$06,$08
       .byte $08,$0A,$0A,$0C,$0C,$12,$12,$12
;
;
;
; BRNTB6 -- OBJECT SIZE AND FLAGS, SPACE MODE.  The twin of BRNTB9.
; Low 6 bits = height in scanlines.  Bit 7 = extends downward / needs the
; special swap handling.  Bit 6 = is a solid target that may fire.
; Entry 0 is deliberately zero so that PBLK reads as "height 0", which is how
; CLOSE and BRAIN detect an empty slot without a compare.
BRNTB6
;  OBJ SIZE AND MISC TABLE
       .byte $D5,$D4,$D3,$D2,$D0,$90,$8D,$8B
       .byte $92,$90,$90,$CE,$CD,$CC,$CB,$CA
       .byte $91,$91,$91,$91,$90,$90,$90,$90
       .byte $D3,$D3,$D3,$D1,$D1,$CF,$8C,$8A
       .byte $D5,$D5,$D3,$D3,$D0,$CE,$CC,$8A
       .byte $12,$12,$12,$10,$10,$0E,$0C,$0A
       .byte $50,$4F,$50,$4F,$4E,$4D,$4C,$4B
       .byte $A5,$A1,$9D,$99,$95,$93,$92,$91
       .byte $17,$15,$13,$11,$10,$0F,$0D,$0C
       .byte $21,$1F,$1B,$17,$14,$13,$10,$0F
       .byte $0E,$0D,$0B,$0A
       .byte $21,$1F,$1B,$17,$14,$13,$10,$0F
       .byte $0E,$0D,$0B,$0A
;  SHARE 1    NULL FOR PBLK
;
;
; BRNTB5 -- packed speed code -> real magnitude.  This is the inverse of
; BRNTB7 and the final step of DIVIDE.  Note the curve: linear 0..8 then
; steps of 4, so slow speeds are finely controllable and fast ones are coarse.
BRNTB5 .byte $00,$01,$02,$03,$04,$05,$06,$07
       .byte $08,$0C,$10,$14,$18,$1C,$20,$24
;
;
;
;
;===============================================================================
; F I X E D - P O I N T   M A T H   H E L P E R S
; Full description in header section 3.  These four routines are the whole
; motion model; everything else just calls them.
;===============================================================================
;
;-------------------------------------------------------------------------------
; DIVIDE -- perspective divide.  A = signed screen offset from the centre of
; projection.  TEMP4 = zoomed distance, TEMP5 = |closing speed|, PNTR1 = the
; sign mask.  Returns the apparent drift, i.e. how fast this object appears to
; move sideways/vertically purely because it is approaching.
;
; Python:  return -sign * BRNTB5[divtab2[divtab1[|offset|, z], zdel]]
;          which is just  offset * closing_speed / distance
;-------------------------------------------------------------------------------
DIVIDE
       BPL    DIVID1  ;??? OR BCS MAYBE ??? -- negative input: negate, recurse, negate back
; NOTE: this stray line begins with an apostrophe, not a semicolon.  It is a
; comment in the assembler Doug used and is preserved verbatim.
' -VALUE
       EOR    #$FF 
       JSR    DIVID1
       EOR    #$FF 
       RTS
DIVID1
;  + VALUE
       ASL  ;move the high nibble into position for the table index
       BCC    DIVID3
       LDA    #$F0   ;FOR A>127 -- saturate for inputs above 127
DIVID3 
       AND    #$F0 
       ORA    TEMP4  ;Z VAL
       TAY  ;first pass: offset nibble | distance nibble
       LDA    DIVTB1,Y
       AND    #$0F 
       ORA    TEMP5  ;Z DEL
       TAY  ;second pass: partial quotient | closing-speed nibble
       LDA    DIVTB1,Y
       LSR
       LSR
       LSR
       LSR
       TAY
       LDA    BRNTB5,Y  ;UNPACK VALUE -- unpack the code into a real magnitude
       EOR    PNTR1   ; -ZOOM -- apply the sign the caller put in PNTR1
       RTS
;
;
;
;
;-------------------------------------------------------------------------------
; ZHELP / ZHELP1 / ZHELP2 -- prepare a desired CLOSING SPEED.
;
;   ZHELP   entry with A = the raw speed error.  Clamps |A| to TEMP7 (the
;           per-path Z speed limit), then adds the baseline in TEMP10.
;   ZHELP1  entry that only applies the AUTOMATIC SLOW-DOWN: an object that has
;           come closer than ZVIS is decelerated so it does not shoot past you.
;           Skipped while wandering or on a surface, where a different rule
;           applies, and skipped at very high throttle.
;   ZHELP2  entry that just PACKS: clamp to +-$0F/$F0 and reduce to the 5-bit
;           code in TEMP10.
;
; The sign trick used throughout: TEMP11 is set to $00 or $FF and used as an
; EOR mask, so the same code path handles both signs.  ROL TEMP11 then feeds
; the sign back into the carry for the following ADC.
;-------------------------------------------------------------------------------
ZHELP  
;  FOR Z ONLY
       LDY    #$00 
       STY    TEMP11  ;TEMP11 is the sign flag: $00 positive, $FF negative
       CMP    #$70  ;values $70 and up count as negative in this representation
       BCC    ZHELP3
       DEC    TEMP11
ZHELP3 
       EOR    TEMP11  ;make it positive
       CMP    TEMP7  ;clamp to the path speed limit
       BCC    ZHELP4
       LDA    TEMP7 
ZHELP4 
       EOR    TEMP11  ;restore the sign
       ROL    TEMP11  ;recover the carry from the sign flag
       ADC    TEMP10  ;add the caller baseline speed
; 
ZHELP1 
; SLOW DOWN
       LDY    ZPOSP0-1,X
       CPY    #ZVIS  ;already closer than the visibility cutoff?
       BCC    ZHELP2  ;still far away: no slow-down needed
       BIT    PROGST 
       BVS    ZHELP7   ;PLANET/TRENCH -- surfaces decelerate on a different schedule
       BIT    GAMEST 
       BMI    ZHELP7   ;WANDERING -- so do wandering objects
       CPY    #$D0 
       BCS    ZHELP2  ;past $D0 it is behind the camera, so leave it alone
       LDA    #$FE  ;$FE = decelerate by one notch
       BNE    ZHELP8  ;JMP
ZHELP7 
       LDA    ATRACT 
       LSR
       LSR
       AND    #$01 
       ORA    #$FE   ;SLOW DOWN
ZHELP8 
       LDY    IQWARP 
       CPY    #$F6  ;unless the throttle is already near maximum...
       BCS    ZHELP2
       SBC    #$01    ;GO A LITTLE FASTER  ,C=0 -- ...in which case accelerate slightly instead
;
ZHELP2 
;  PACK Z
       TAY
       BMI    ZHELP5
       CMP    #$10 
       BCC    ZHELP6
       LDA    #$0F  ;clamp positive speeds to $0F
       BCS    ZHELP6  ;JMP
ZHELP5 
       CMP    #$F0 
       BCS    ZHELP6
       LDA    #$F0  ;clamp negative speeds to $F0
ZHELP6 
       AND    #$1F  ;keep only the 5-bit code
       STA    TEMP10 
ZHEL99
       RTS
;
;
;
;
;-------------------------------------------------------------------------------
; PREHLP -- the X and Y equivalent of ZHELP.  A = the raw error, TEMP7 = the
; per-path speed limit, TEMP10 = the baseline.  Leaves the packed 5-bit code
; in TEMP10.
;
; PREHL5 is the pack-only entry.  It handles negatives by negating, packing the
; positive value through PREHL3, and then EOR $1F -- which is exactly the
; negative-code convention described in header section 3.
;-------------------------------------------------------------------------------
PREHLP 
; FOR X AND Y ONLY
       LDY    #$00 
       STY    TEMP11  ;TEMP11 is the sign flag: $00 positive, $FF negative
       CMP    #$80  ;values $80 and up count as negative
       BCC    PREHL1
       DEC    TEMP11
PREHL1 
       EOR    TEMP11  ;absolute value
       LSR  ;scale down by 4 -- X and Y are less sensitive than Z
       LSR
       CMP    TEMP7  ;clamp to the path speed limit
       BCC    PREHL2
       LDA    TEMP7 
PREHL2 
       TAY
       LDA    BRNT20,Y  ;BRNT20 maps magnitude to a code index
       EOR    TEMP11
       ROL    TEMP11 
       ADC    TEMP10 
PREHL5 
; PACK
       BPL    PREHL3  ;negative: pack the magnitude then flip to the negative encoding
       EOR    #$FF 
       JSR    PREHL3
       EOR    #$1F 
       STA    TEMP10 
       RTS
PREHL3 
       TAY
       CPY    #$28  ;codes above $27 saturate
       BCC    PREHL4
       LDY    #$27 
PREHL4 
       LDA    BRNTB7,Y  ;BRNTB7 does the actual magnitude -> code conversion
       STA    TEMP10  ;the packed result always comes back in TEMP10
       RTS
;
;
;
;-------------------------------------------------------------------------------
; POSTHP -- SLEW the current velocity toward the desired one.
;
;   A on entry  = the object CURRENT packed delta
;   TEMP10      = the DESIRED packed speed code (from PREHLP or ZHELP)
;   carry       = response curve.  C=0 is type 1: snap straight to the target.
;                 C=1 is type 2: move one notch, so acceleration is limited.
;                 BRAIN calls POSTHP twice for type 2 to get two notches.
;   returns A   = the new packed delta, with the accumulator bits preserved
;   POSTH1      = CLC then POSTHP, i.e. the type 1 entry.
;
; Python:
;   if not gradual: return (cur & 0xE0) | want
;   step = +1 or -1 toward want, clamped so it cannot overshoot
;-------------------------------------------------------------------------------
POSTH1 
       CLC  ;TYPE 1
POSTHP 
       STA    TEMP11  ;save the current packed delta
       AND    #$E0  ;keep the sub-pixel accumulator bits
       ORA    TEMP10  ;splice in the new speed code
       BCC    POSTH2  ;carry clear = type 1: take the new value as is
       CMP    TEMP11
       BEQ    POSTH2  ;already at the target: nothing to do
       EOR    TEMP11
       AND    #$10  ;which direction to step (the sign bit of the code)
       BEQ    POSTH4
       LDA    #$FE  ;$FE = step down by one notch
POSTH4 
       BCS    POSTH3
       EOR    #$FF  ;invert the step when going the other way
POSTH3 
       ADC    TEMP11  ;apply one notch to the current value
       SEC  ;C=1 tells the caller the value changed
       RTS
POSTH2 
       CLC  ;C=0 tells the caller nothing changed
       RTS
;
;
;
;-------------------------------------------------------------------------------
; EXCHNG -- swap EVERY field of obj[X-1] with obj[X-2].
; EXCHN1 is the same but leaves the Y coordinates alone, which the caller uses
; when it has already adjusted them by hand.
; In Python:  objs[i-1], objs[i-2] = objs[i-2], objs[i-1]
; (Doug typo in the original comment: EXCJAMGE.)
;-------------------------------------------------------------------------------
EXCHNG 
; EXCJAMGE PBK X-1 WITH X-2
       LDA    HVERP0-1,X
       LDY    HVERP0-2,X
       STA    HVERP0-2,X
       STY    HVERP0-1,X
EXCHN1
; NO VERT EXCHANGE
       LDA    ZDELP0-1,X
       LDY    ZDELP0-2,X
       STA    ZDELP0-2,X
       STY    ZDELP0-1,X
       LDA    HHORP0-1,X
       LDY    HHORP0-2,X
       STA    HHORP0-2,X
       STY    HHORP0-1,X
       LDA    ZPOSP0-1,X
       LDY    ZPOSP0-2,X
       STA    ZPOSP0-2,X
       STY    ZPOSP0-1,X
       LDA    YDELP0-1,X
       LDY    YDELP0-2,X
       STA    YDELP0-2,X
       STY    YDELP0-1,X
       LDA    XDELP0-1,X
       LDY    XDELP0-2,X
       STA    XDELP0-2,X
       STY    XDELP0-1,X
       LDA    HGRAP0-1,X
       LDY    HGRAP0-2,X
       STA    HGRAP0-2,X
       STY    HGRAP0-1,X
       LDA    IQPATH-1,X
       LDY    IQPATH-2,X
       STA    IQPATH-2,X
       STY    IQPATH-1,X
       RTS
;
;
;
;
;-------------------------------------------------------------------------------
; BANK 1 EXIT TRAMPOLINES.  PLUMBING -- see header section 8.
; Each STA STROBn swaps the ROM bank under the program counter, so the
; instruction that appears next in this listing is NOT what executes.  Note how
; small data tables (EXPOFF, SWAPT5, BRNT14) have been tucked into the gaps
; between trampolines to use up the otherwise wasted bytes.
; The trailing "DOUG N" and the two reset vectors are the cartridge footer.
;-------------------------------------------------------------------------------

;     BANK SELECT CODE
      ORG  $0FCF
      RORG BANK1+$0FCF
PON1
       STA    STROB4 ;JMP FFD2
       JSR    BRAIN
       STA    STROB3 ;JMP DFD8
      .byte $00,$00,$00
       JSR    HYPSRV
       STA    STROB2 ;JMP EFE1
EXPOFF 
       .byte $FF,$FC,$FD,$FA,$FA,$00,$00,$00
SWAPT5 .byte $01,$01,$02,$03
       JSR    CLOSE
       STA    STROB3 ;JMP DFF3
BRNT14 .byte $00,$1F
       .byte $00
       .byte "DOUG N"
       .word PON1
       .word PON1
;
;
; **********************
;  END INCLUDE BANK1.SRC
; **********************
;
;END

;
;
;===============================================================================
; B A N K   3  --  FRAME LOOP, STATUS DISPLAY, STAR CHART, PLAYER COLLISION
;
; This bank owns the outer structure of the game: reset, the per-frame MAIN
; loop, the overscan housekeeping (TIMSRV), the strategic layer (SMARTS and the
; star chart), what happens when something hits you (HITSRV), scoring and fuel.
; It also holds the two kernels that are common to every screen: the six-digit
; score readout and the scanner/fuel strip along the bottom.
;===============================================================================
; **********************************
;   VERSION 17.6  08-MAR-86
;COPYRIGHT (C) 1986, DOUGLAS NEUBAUER
; INCLUDE BANK3.SRC FOR UNIV.SRC
; **********************************
;
;
;*********
 seg bank3
 ORG $1000
 RORG BANK3    ; BEGIN BANK3
;*********
;
;
;
;-------------------------------------------------------------------------------
; SCRTAB -- the 6x8 pixel FONT, one glyph per 8 bytes, stored TOP ROW FIRST
; here (unlike the object sprites, which are stored bottom-first).  Only the
; low 6 bits of each byte are used, which is why the digits look narrow.
;
; Layout, in order:
;   +$00  digits 0 through 9
;   +$50  the four direction arrows: DOWN, LEFT, UP, RIGHT
;   +$70  an X (target lost) and a BLANK
;   +$80  the word SCANNER, five glyphs wide, drawn across the status strip
;   +$C0  the word JUMP, four glyphs
;   +$E0  the copyright line, six glyphs
;
; To extract in Python: SCRTAB[i*8 : i*8+8] is glyph i, MSB on the left.
;-------------------------------------------------------------------------------
SCRTAB
       .byte $00,$1E,$33,$33,$33,$33,$33,$1E
       .byte $00,$3F,$0C,$0C,$0C,$0C,$3C,$1C
       .byte $00,$3F,$30,$30,$1E,$03,$23,$3E
       .byte $00,$1E,$23,$03,$06,$03,$23,$1E
       .byte $00,$06,$06,$3F,$26,$16,$0E,$06
       .byte $00,$3E,$23,$03,$3E,$30,$30,$3F
       .byte $00,$1E,$33,$33,$3E,$30,$31,$1E
       .byte $00,$0C,$0C,$0C,$06,$03,$21,$3F
       .byte $00,$1E,$33,$33,$1E,$33,$33,$1E
       .byte $00,$1E,$23,$03,$1F,$33,$33,$1E
       .byte $00,$00,$00,$08,$1C,$3E,$00,$00 ;DOWN
       .byte $00,$00,$08,$18,$38,$18,$08,$00 ;LEFT
       .byte $00,$00,$00,$3E,$1C,$08,$00,$00 ;UP
       .byte $00,$00,$08,$0C,$0E,$0C,$08,$00 ;RIGHT
       .byte $00,$00,$66,$3C,$18,$3C,$66,$00 ;X
       .byte $00,$00,$00,$00,$00,$00,$00,$00 ;BLANK
;  SCANNER
       .byte $00,$FB,$0B,$0B,$FB,$C3,$C3,$FB
       .byte $00,$D9,$19,$19,$1F,$19,$19,$DF
       .byte $00,$65,$6D,$6D,$7D,$75,$75,$65
       .byte $00,$97,$B6,$B6,$F7,$D6,$D6,$97
       .byte $00,$B6,$36,$34,$BE,$32,$32,$BE
;  JUMP
       .byte $00,$78,$CC,$0C,$0C,$0C,$0C,$3E
       .byte $00,$79,$CD,$CD,$CD,$CD,$CD,$CD
       .byte $00,$8D,$8D,$AD,$AD,$FD,$DD,$8D
       .byte $00,$80,$83,$83,$F0,$9B,$9B,$F0
;  COPYRIGHT
       .byte $00,$00,$F7,$95,$87,$80,$90,$F0
       .byte $47,$41,$77,$55,$75,$00,$00,$00
       .byte $03,$00,$4B,$4A,$6B,$00,$08,$00
       .byte $80,$80,$AA,$AA,$BA,$22,$27,$02
       .byte $00,$00,$11,$11,$17,$15,$17,$00
       .byte $00,$00,$77,$55,$77,$54,$77,$00
;
;
; FUELT1 -- fuel gauge bar.  Index = FUEL >> 5, value = the playfield bit
; pattern for that many segments (progressively more bits cleared).
FUELT1
       .byte $7F,$7E,$7C,$78,$70,$60,$40,$00
;
;
; CHTAB8 / SMSKTB block.  SMSKTB itself is just the eight single-bit masks,
; but the bytes AFTER it are the STAR CHART ICONS, 8 bytes each, in the order:
;   X (cursor), GOOD (friendly), TRN (trench), BLK (blockader), FIGH (fighter),
;   BAD (enemy planet), PIRATE, PLN (planet), HOL (wormhole), COBRA, WALL.
; The icon index is what FINDV returns in TEMP6 and what CHTDRW packs into
; CHTBLK.  After the icons come the company-name glyphs and three small target
; graphics (moon/crater, man, landing zone) used by the scanner.
CHTAB8
; CHART GRAPHICS
       .byte $00,$00,$00,$00,$00,$00,$00 ;BLANK
; SHARE 1
LD107  .byte $00

SMSKTB
       .byte $01,$02,$04,$08,$10,$20,$40,$80
       .byte $00,$00,$66,$3C,$18,$3C,$66,$00 ;X
       .byte $00,$08,$2A,$1C,$7F,$1C,$2A,$08 ;GOOD
       .byte $00,$FF,$80,$BA,$AA,$BB,$80,$E0 ;TRN
       .byte $00,$18,$99,$C3,$E7,$C3,$99,$18 ;BLK
       .byte $00,$80,$40,$60,$72,$FF,$00,$80 ;FIGH
       .byte $00,$00,$E8,$98,$5A,$39,$1F,$00 ;BAD
       .byte $00,$00,$C3,$99,$FF,$99,$C3,$00 ;PIRATE
       .byte $00,$18,$3C,$FF,$18,$FF,$3C,$18 ;PLN
       .byte $00,$08,$1C,$08,$03,$E7,$B6,$9C ;HOL
       .byte $00,$1C,$26,$4E,$1C,$18,$18,$0E ;COBRA
       .byte $00,$08,$81,$00,$10,$00,$81,$10 ;WALL
; COMPANY NAME
       .byte $00,$F2,$D8,$D8,$D8,$D8,$D8,$F0
       .byte $00,$CD,$DD,$DD,$FD,$ED,$EC,$CC
       .byte $00,$EF,$8D,$CD,$8D,$ED,$00,$00
       .byte $00,$7A,$6A,$7B,$6A,$7B,$00,$00
       .byte $00,$BD,$B5,$B5,$B5,$B5,$00,$00
       .byte $00,$ED,$8F,$EF,$8D,$EF,$00,$00
; SOME TARG GRA
       .byte $18,$3C,$3C,$3C,$18 ;MOON/CRA
       .byte $24,$3C,$18,$7E,$18  ;MAN
       .byte $FF,$81,$81,$FF,$FF   ;LZ
;
;
;
       .byte $A0,$90
;
; XTABLE -- a second horizontal-position table like CRAZY, but for the scanner
; strip where the sprite is positioned within a narrower band.  PLUMBING.
XTABLE
       .byte $71,$61,$51,$41,$31,$21,$11,$01
       .byte $F1,$E1,$D1,$C1,$B1,$A1,$91,$72
       .byte $62,$52,$42,$32,$22,$12,$02,$F2
       .byte $E2,$D2,$C2,$B2,$A2,$92,$73,$63
       .byte $53,$43,$33,$23,$13,$03,$F3,$E3
       .byte $D3,$C3
;
;
;
;
;-------------------------------------------------------------------------------
; SCRKER -- THE SCORE KERNEL.
;
; WHAT IT DRAWS: six digits of score across the top of the screen, using both
; hardware players three-copies-wide with vertical delay, so six glyphs come
; out of two sprites.  PNTR1..PNTR6 each point at one digit glyph in SCRTAB;
; MESSRV or LDSCOR fills them in beforehand.
;
; Entry points:
;   SCRKER   normal: 8 scanlines, colours already set
;   SCRKR4   same but Y (the line count) supplied by the caller
;   SKRKR3   same but X (the glyph page) supplied too -- used for the title
;
; WAIT1L at the end is a general "burn one scanline" helper used all over the
; bank.
;
; For Python: draw score_string at the top in the game font.  Everything else
; here is beam timing.
;-------------------------------------------------------------------------------
SCRKER
; SETUP SCORE
;  DISPLAY PNTR 654321
       LDY    #$07 
SCRKR4
       LDX    #$F0 
SKRKR3
;  ENTRY
       STA    WSYNC
       STA    ADDEL
       STX    TEMP7 
       STX    TEMP5 
       LDA    #$10 
       STA    VBLANK   ;TURN OFF
       STX    PNTR3+1 
       STX    PNTR4+1
       STX    PNTR5+1
       STX    PNTR6+1
       STA    HDELP1
       STA    REFP0
       STA    REFP1
       LDA    #$00 
       STA    HPOSP0
       STA    HPOSP1
       STA    WSYNC
       STA    ADDEL
; NEXT LINE SETUP
       STA    GRAFP0
       STY    STAK1 
       LDA    #$03 
       STA    SIZPM0
       STA    SIZPM1
       STA    VDELP0
       STA    VDELP1
       STA    CLRDEL
;
SCRKR1
;  DISPLAY SCORE
       LDY    STAK1 
       LDA    (PNTR1),Y
       STA    STAK2 
       STA    WSYNC
       STA    ADDEL
       LDA    (PNTR2),Y
       TAX
       LDA    (PNTR6),Y
       STA    GRAFP0
       LDA    (PNTR5),Y
       STA    GRAFP1
       LDA    (PNTR4),Y
       STA    GRAFP0
       LDA    (PNTR3),Y
       LDY    STAK2 
       STA    GRAFP1
       STX    GRAFP0
       STY    GRAFP1
       STA    GRAFP0
       DEC    STAK1 
       BNE    SCRKR1
       LDA    #$00 
       STA    VDELP1
       STA    GRAFP0
       STA    GRAFP1
WAIT1L
; ENTRY
       STA    WSYNC
       STA    ADDEL
       RTS
;
;
;
;-------------------------------------------------------------------------------
; CHART -- THE STAR CHART KERNEL.
;
; WHAT IT DRAWS: the sector map.  CHTBLK holds 24 bytes = 48 cells, packed two
; 4-bit cells per byte; each nibble is an icon index into the CHTAB8 icon set,
; with 0 meaning empty.  The grid is 6 columns x 8 rows, drawn as playfield
; blocks with the two players carrying the icons.
;
; Below the grid it draws the word JUMP and the BCD countdown in JMPTIM, then
; falls through into SCANDS for the status strip.
;
; The cursor (your position) is CURSOR, 0..$2F.  SMRJOY moves it and calls
; CHTDRW / CHTERS to paint and erase icons in CHTBLK.
;
; Python: render a 6x8 grid of icons, highlight the cursor cell, show the jump
; timer.  None of the scanline juggling below matters.
;-------------------------------------------------------------------------------
CHART
       LDY    #$08 
       JSR    LDSCR4
       JSR    SCRKER
;  SETUP CHART
       STA    VDELP0
       LDA    #$17 
       STA    STAK1 
       LDA    HCOLP1 ;CHART COLOR
       ORA    #$0E 
       STA    COLPM0
       STA    COLPM1
       LDX    #$A0 
       STA    HPOSP0
       STA    HPOSM0
       STX    HDELM1
       LDY    #$C0 
       LDX    #$0A 
       STA    HPOSM1
       STA    HPOSP1
       STY    HDELM0
       EOR    #$22 
       STA    COLPF
CHAR98
       STA    WSYNC
       STA    ADDEL
       LDA    #$F1 
       STA    TEMP7,X
       LDY    #$9F 
       NOP
       NOP
       NOP
       NOP
       NOP
       DEX
       STA    CLRDEL
       BPL    CHAR98
;
CHART2
; DISPLAY CHART
; LINE 1 SETUP
       LDA    #$1F 
       STA    WSYNC
       STA    ADDEL
; LIN 2
       STA    GRFPF1
       STY    GRFPF2
       STA    GRAFM0
       STA    GRAFM1
       LDX    #$05 
CHAR82
       DEX
       BPL    CHAR82
       STX    GRFPF2
       LDY    STAK1 
       BMI    CHAR86
       LDX    #$0C 
       LDA    #$00 
       STA    GRFPF2
CHART5
       STA    WSYNC
       STA    ADDEL
;  LINES 3,4,5
       TYA
       AND    #$FE 
       EOR    #$0C 
       BEQ    CHAR85
       LDA    #$10 
CHAR85
       STA    GRFPF1
       LDA.wy CHTBLK,Y
       AND    #$F0 
       LSR
       STA    PNTR1-2,X
       DEX
       DEX
       LDA.wy CHTBLK,Y
       AND    #$0F 
       ASL
       ASL
       ASL
       STA    PNTR1-2,X
       DEY
       DEX
       DEX
       BNE    CHART5
;
       STY    STAK1 
       LDY    #$07 
CHART1
       LDA    (PNTR1),Y
       STA    WSYNC
       STA    ADDEL
       STA    STAK2 
       LDA    (PNTR6),Y
       STA    GRAFP0
       LDA    (PNTR3),Y
       STA    GRAFP1
       LDA    (PNTR4),Y
       TAX
       LDA    (PNTR5),Y
       NOP
       STA    GRAFP0
       NOP
       STX    GRAFP0
       LDX    STAK2 
       LDA    (PNTR2),Y
       STA    GRAFP1
       DEY
       STX    GRAFP1
       BPL    CHART1
       STA    WSYNC
       STA    ADDEL
; LINE 1
       LDA    #$10 
       STA    GRFPF1
; Y = FF
       BIT    STAK1 
       BPL    CHAR87
       LDY    #$9F 
CHAR87
       JMP    CHART2
CHAR86
; FINISH LINE 2
       LDA    HCOLP1 
       ADC    #$C8 
       TAX
       STA    WSYNC
       STA    ADDEL
; LINE 3, ALL DONE CHART
       LDA    #$00 
       STA    GRFPF1
       STA    GRFPF2
       STA    GRAFM0
       STA    GRAFM1
       LDY    #$02 
       LDA    #$A8  ;JUMP
       JSR    LDSCOR
       LDA    JMPTIM 
       AND    #$0F 
       ASL
       ASL
       ASL
       STA    PNTR1 
       LDA    JMPTIM 
       AND    #$F0 
       LSR
       STA    PNTR2 
       JSR    SCRKER
       LDY    #$08 
       JSR    LDSCR1  ; WAIT
;  FALL THRU TO SCANDS
;
;
;
;-------------------------------------------------------------------------------
; SCANDS -- THE SCANNER AND FUEL STRIP at the bottom of every play screen.
;
; WHAT IT DRAWS, top to bottom:
;   * RANGE readout: two digits derived from ZPOS of the object in TARNUM
;     (the scanner lock set by GRAPH).  SCNTB1 converts the distance into a
;     digit pair.
;   * DIRECTION arrows: one glyph showing whether the target is left, right or
;     dead ahead (from HHORP0 versus CENTER), and one showing up/down/centred
;     (from HVERP0).  The X glyph is used when there is no lock.
;   * TARGET ICON: which kind of thing is locked, from the class nibble via
;     SCNTB4 / SCNTB2 into the CHTAB8 icon set.
;   * LIVES: LIVTAB turns the remaining-ship count into a playfield pattern.
;   * FUEL BAR: FUELT1 for the bar itself, FUELT2..FUELT5 for the word FUEL.
;     Below $20 fuel it also queues the low-fuel warning sound and flashes.
;
; On the power-up screen (PROGST bit 7) it instead draws the title and
; copyright and skips the scanner entirely.
;
; Ends by jumping to MAIN2, i.e. the screen is finished and overscan begins.
;-------------------------------------------------------------------------------
SCANDS
       STA    WSYNC
       STA    ADDEL
; LINE 1
       LDA    #$00 
       STA    VDELP0
       STA    VDELM2
       STA    GRAFP0
       STA    GRAFP1
       STA    GRAFM2
       STA    SIZPM0
       STA    COLPF
; RANGE
       LDX    TARNUM  ;TARNUM = the slot GRAPH locked the scanner onto
       LDA    ZPOSP0-1,X  ;its distance
       CMP    #$40 
       BCC    SCAND8
       ADC    #$3F  ;ranges past $40 are compressed so they still fit two digits
       ROR
SCAND8
       TAY
       LSR
       AND    #$78 
       STA    PNTR5+0
       TYA
       AND    #$0F 
       TAY
       LDA    SCNTB1,Y  ;SCNTB1 turns the range into a pair of digit glyphs
       STA    PNTR5+1
       LDA    FUEL  ;fuel, scaled down to the width of the bar
       LSR
       LSR
       LSR
       STA    WSYNC
       STA    ADDEL
; LINE 2
       LDY    #$01 
       STY    PRIOR
       BIT    PROGST  ;PROGST bit 7 = power-up / game over...
       BPL    SCAN10  ;...so draw the title and copyright instead of the scanner
;  COPYRIGHT
       STY    COLBK
       LDA    #$C7 
       LDX    #$FF 
       TXS
       LDX    #$2C 
       JSR    LDSCOR
       LDY    #$08 
       JSR    SCRKR4
       LDA    #$68   ;TITLE
       LDX    #$2A 
       LDY    #$01 
       JSR    LDSCOR
       LDX    #>CHTAB8
       LDY    #$07 
       JSR    SKRKR3
       LDY    #$04  ;WAIT
       JMP    HORZ11
SCAN10
; HORIZ
       STA    STAK1    ;TEMPORARY REG
       SEC
       LDA    HHORP0-1,X  ;horizontal offset of the target...
       SBC    CENTER  ;...from the camera
       CLC
       ADC    #$28 
       CMP    #$50 
       BCC    SCAND1
       CMP    #$A8 
       LDA    #$50 
       BCC    SCAND1
       LDA    #$00 
SCAND1
       LSR  ;fold that into a 0..$14 arrow index
       TAY
       LDA    #$70-9 ;X -- dead ahead: the X glyph
       CPY    #$13 
       BEQ    SCAND5
       LDA    #$68-9 ;RT -- to the right: the right arrow
       BCS    SCAND5
       LDA    #$58-9 ;LT -- to the left: the left arrow
SCAND5
       STA    PNTR2 
       LDA    XTABLE,Y
       STA    HDELP0
       STA    WSYNC
       STA    ADDEL
;  LINE 3
;  HPOSP0
       AND    #$0F 
       TAY
       LDA    #>MASKTB
       STA    PNTR6+1
       LDA    #$B8 
       STA    COLPM1
       LDA    #$F2 
       STA    COLBK
       LDA    #$00 
       STA    GRAFM0
       LDA    #>SCRTAB
       STA    PNTR2+1
       STA    PNTR3+1 
SCAND6
       DEY
       BNE    SCAND6
       STA    HPOSP0
       LDA    HGRAP0-1,X
       AND    #$78 
       LSR
       LSR
       LSR
       TAY
       STA    WSYNC
       STA    ADDEL
;   LINE 4
       LDA    #$04 
       STA    SIZPM1
;  VERTICAL
       LDA    HVERP0-1,X  ;vertical offset of the target, folded the same way
       CLC
       ADC    #$48 
       LSR
       LSR
       LSR
       LSR
       STA    PNTR1   ;HOLD REG
       LDX    #$0E 
       STA    CLRDEL
       STA    HPOSP1  ; NUMBERS POSITION
       LDA    #$10 
       STA    HDELM2
       LDA    #$F0 
       STA    HDELP1
       STA    HPOSM2  ;CROSSHAIRS POSITION
       LDA    SCNTB4,Y  ;SCNTB4[class] = which icon this kind of target uses
       BIT    ONESHT  ;ONESHT bit 6 = you are damaged, so flicker the scanner colour
       BVC    SCAN11
       LDA    RANDOM 
       TAX
SCAN11
       STA    PNTR4 
       STX    COLPM0
       LDX    #$03 
       STA    WSYNC
       STA    ADDEL
       STX    GRAFM2
       STX    GRFPF1  ;DISP 1ST LINE SCANNER
       LDX    #$FF 
       STX    GRFPF2
       LDX    #$70-9  ;X
       LDA    PNTR1 
       CMP    #$08 
       BEQ    SCAND7
       LDX    #$60-9  ;UP
       BCS    SCAND7
       LDX    #$50-9  ;DWN
SCAND7
       STX    PNTR3 
       LDA    #<MASKTB+2
       SEC
       SBC    PNTR1 
       STA    PNTR6 
       LDA    SCNTB2,Y
       SEC
       SBC    PNTR1 
       STA    PNTR1 
       LDA    #>CHTAB8
       STA    PNTR1+1
       STA    CLRDEL
       LDY    #$0F 
       LDA    #$01    ;C=1
;
SCAND2
; DISPLAY SCANNER
       AND    (PNTR6),Y
       SBC    #$01 
       STA    WSYNC
       STA    ADDEL
       AND    (PNTR1),Y
       STA    GRAFP0
       LDA    TACTB1,Y
       STA    GRFPF2
       LDA    (PNTR2),Y  ; LEFT NO.
       LDX    TACTB2,Y
       BMI    SCAND3
       STA    GRAFP1
       LDA    PNTR4      ; SCANNER COLOR
       STA    COLBK
       STX    PRIOR
       LDA    (PNTR3),Y  ; RIGHT #
       STA    GRAFP1
SCAND4
       SEC
       LDX    #$F2   ;BAK COLOR
       LDA    #$01 
       STA    PRIOR
       STX    COLBK
       DEY
       BPL    SCAND2
       BMI    SCAN33 ;JMP
SCAND3
       STX    PRIOR
       LDA    PNTR5
       STA    PNTR2 
       LDA    PNTR5+1
       STA    PNTR3 
       JMP    SCAND4
SCAN33
;
;
       STA    WSYNC
       STA    ADDEL
; SETUP FUEL
       LDA    #$00 
       STA    GRAFP0
       NOP
       STX    COLPF   ;BAKCOL
       LDX    LIVES 
       LDA    LIVTAB,X
       STA    GRFPF0
       LDA    LIVTAB+1,X
       STA    GRFPF1
       LDA    #$34 
       STA    PRIOR
       LDA    STAK1   ;HOLDS FUEL
       LSR
       LSR
       TAY
       LDA    FUELT1,Y
       STA    GRFPF2
       LDY    STAK1 
       STA    HPOSP0
       STA    HPOSP1
       LDA    XTABLE-2,Y
       STA    HDELM2
       STA    WSYNC
       STA    ADDEL
       AND    #$0F 
       CLC
       ADC    #$07 
       TAX
DISP70
       DEX
       BPL    DISP70
       LDA    #$10 
       STA    HDELP1
       LDA    ATRACT 
       STA    HPOSM2
       STA    WSYNC
       STA    ADDEL
       LDX    #$F2   ;BAKCOL
       LDY    FUEL  ;fuel level
       CPY    #$01 
       BCC    DISP72
       CPY    #$20  ;below $20 is LOW FUEL...
       BCS    DISP71
       LDY    #$52 ;#AUDLOW-J
       STY    CH0SHD    ;LOW FUEL -- ...which queues the warning sound...
       AND    #$10  ;...and flashes the bar
       BNE    DISP72
DISP71
       LDX    #$1A 
DISP72
       LDY    #$04 
       NOP
       NOP
       NOP
       NOP
       STA    CLRDEL
;
DISP73
; DISPLAY FUEL
       LDA    #$8E 
       STA    WSYNC
       STA    ADDEL
       STA    COLPM0
       STA    COLPM1
       LDA    #$04 
       STA    SIZPM0
       STA    SIZPM1
       LDA    FUELT3,Y
       STA    GRAFP0
       STA    GRAFP1
       LDA    FUELT4,Y
       STA    GRAFP0
       LDA    FUELT2,Y
       STA    GRAFP1
       LDA    #$03 
       STA    SIZPM0
       STA    SIZPM1
       STX    COLPM0
       STX    COLPM1
       LDA    FUELT5,Y
       STA    GRAFP0
       STA    GRAFP1
       DEY
       BPL    DISP73
       JMP    MAIN2   ; SCREEN ALL DONE
;
;
;
FUELT2 .byte $EE,$88,$E8,$88,$E8
FUELT5 .byte $FF,$00,$EE,$CC
FUELT3 .byte $88,$88,$CC,$EE,$CC
FUELT4 .byte $8E,$8A,$EA,$8A,$EA
;
;
;  MASKTB BLOCK
;
; MASKTB block.  TACTB1 and TACTB2 are per-scanline playfield and priority
; patterns for the scanner strip; SCNTB4 and SCNTB2 map a target class to its
; icon and to the icon pointer.  The three tables deliberately overlap.
TACTB1 .byte $FF,$23,$03,$03,$03,$03,$03,$07
       .byte $FF,$07,$03,$03,$03,$03,$03,$23
MASKTB
SCNTB4 .byte $44,$44,$44,$B4,$B4,$55,$55,$87
       .byte $85,$85,$87,$87,$15
TACTB2 .byte $05,$05,$25,$05,$25,$05,$25,$05
       .byte $85,$05,$25,$05,$25,$05,$25,$05
;  END MASKTB BLOCK
;
;
SCNTB1 .byte $00,$08,$10,$18,$20,$20,$28,$28
       .byte $30,$30,$38,$38,$40,$40,$48,$48
;
SCNTB2 .byte $14,$44,$4C,$9F,$A4,$2C,$1C,$5B
       .byte $9A,$9A,$3C,$9A,$14
;
;
;
;
;
;-------------------------------------------------------------------------------
; LDSCOR -- load the six score-kernel glyph pointers.
;   A = the base glyph offset, X = the colour, Y = the number of scanlines to
;   wait afterwards.  It fills PNTR6, TEMP4, PNTR4, PNTR3, PNTR2, PNTR1 with
;   base, base+8, base+16 ... i.e. six consecutive glyphs.  Used to display a
;   fixed word (SCANNER, JUMP, the title) rather than the score.
; LDSCR1 is the plain "wait Y scanlines" tail.  PLUMBING.
;-------------------------------------------------------------------------------
LDSCR3 
; ENTRY FROM MESSRV
       LDY    #$01 
LDSCR4
; ENTRY FROM CHART
       LDX    #$48 
       LDA    #$78   ;SCANNER 
LDSCOR
; WORD TO SCORE KERNAL
; A=PNTR,X=COLOR,Y=WAIT
       STX    COLPM0
       STX    COLPM1
       CLC
       STA    PNTR6 
       ADC    #$08 
       STA    TEMP4 
       ADC    #$08 
       STA    PNTR4 
       ADC    #$08 
       STA    PNTR3 
       ADC    #$08 
       STA    PNTR2 
       ADC    #$08 
       STA    PNTR1 
LDSCR1
       STA    WSYNC
       STA    ADDEL
       DEY
       BNE    LDSCR1
       RTS
;
;
;
;
;
;
;-------------------------------------------------------------------------------
; MESSRV -- unpack the 3-byte BCD SCORE into the six glyph pointers for
; SCRKER.  Also does leading-zero blanking: MESSR2 walks the six pointers from
; the most significant end and replaces zeros with the blank glyph until it
; hits a non-zero digit.
;
; During attract mode (NEWATT >= $40 with the frame counter positive) it skips
; the score entirely and shows the SCANNER banner instead.
;
; Python:  digits = "%06d" % score; then lstrip the leading zeros.
;-------------------------------------------------------------------------------
MESSRV
       LDA    NEWATT 
       CMP    #$40  ;attract mode?
       BCC    MESSR1
       BIT    ATRACT  ;on alternate periods show the SCANNER banner, not the score
       BPL    LDSCR3
MESSR1
       LDA    #$1E 
       STA    COLPM0
       STA    COLPM1 ;SCORE COLOR
       LSR           ;A = 0F
       AND    SCORE  ;each BCD nibble is multiplied by 8 to become a glyph offset
       ASL
       ASL
       ASL
       STA    PNTR2 
       LDA    #$F0 
       AND    SCORE 
       LSR
       STA    PNTR3 
       LDA    SCORE+1
       AND    #$0F 
       ASL
       ASL
       ASL
       STA    PNTR4 
       LDA    SCORE+1 
       AND    #$F0 
       LSR
       STA    PNTR5
       LDA    SCORE+2 
       AND    #$0F 
       ASL
       ASL
       ASL
       STA    PNTR6 
       LDY    #$78    ;BLANK
       TYA
       LDX    PROGST 
       CPX    #$CE    ;PWR UP -- on the power-up screen the leading glyph is blanked differently
       BEQ    MESSR6
       LDA    #$00 
MESSR6
       STA    PNTR1 
;
       LDX    #$0A  ;six pointers, two bytes apart
MESSR2
       LDA    PNTR1,X  ;walk down from the most significant digit...
       BNE    MESSR3  ;...stopping at the first non-zero...
       STY    PNTR1,X  ;...blanking the zeros on the way
       DEX
       DEX
       BNE    MESSR2
MESSR3
       RTS
;
;
;
;
; CRAZY -- the horizontal position table.  Index = the pixel X you want,
; value = high nibble is the HMOVE fine adjustment and low nibble is the
; number of times to go round the delay loop before strobing RESPx.
; The table must not cross a page boundary or the timing breaks.
; PURE PLUMBING: in Python this whole mechanism is "x = pixel".
CRAZY
;  CANT CROSS PAGE BOUNDARY
       .byte $60,$71,$50,$61,$40,$51,$30,$41
       .byte $20,$31,$10,$21,$00,$11,$F0,$01
       .byte $E0,$F1,$D0,$E1,$C0,$D1,$B0,$C1
       .byte $A0,$B1,$90,$62,$73,$52,$63,$42
       .byte $53,$32,$43,$22,$33,$12,$23,$02
       .byte $13,$F2,$03,$E2,$F3,$D2,$E3,$C2
       .byte $D3,$B2,$C3,$A2,$B3,$92,$64,$75
       .byte $54,$65,$44,$55,$34,$45,$24,$35
       .byte $14,$25,$04,$15,$F4,$05,$E4,$F5
       .byte $D4,$E5,$C4,$D5,$B4,$C5,$A4,$B5
       .byte $94,$66,$77,$56,$67,$46,$57,$36
       .byte $47,$26,$37,$16,$27,$06,$17,$F6
       .byte $07,$E6,$F7,$D6,$E7,$C6,$D7,$B6
       .byte $C7,$A6,$B7,$96,$68,$79,$58,$69
       .byte $48,$59,$38,$49,$28,$39,$18,$29
       .byte $08,$19,$F8,$09,$E8,$F9,$D8,$E9
       .byte $C8,$D9,$B8,$C9,$A8,$B9,$98,$6A
       .byte $7B,$5A,$6B,$4A,$5B,$3A,$4B,$2A
       .byte $3B,$1A,$2B,$0A,$1B,$FA,$0B,$EA
       .byte $FB,$DA,$EB,$CA,$DB,$BA,$CB,$AA
;
;
;
;
; *** END KERNALS FOR BANK 3 *****
;
;
;
;
;===============================================================================
; I N I T  --  RESET AND RESTART
;
; Three nested entry points, from coldest to warmest:
;   INIT    power on.  Zeroes all of RAM and the TIA, sets PROGST = $CE (the
;           power-up / title state), 4 lives, the initial star chart.
;   INIT2   game reset or select.  Same but PROGST comes from Y.
;   INIT3   YOU DIED but the game is not over: refill fuel, clear damage,
;           recentre the camera, decrement LIVES.
;   INIT8   THE GAME IS OVER: PROGST = $CA.
;   INIT4   ship takeoff finished: rebuild the four object slots from INTAB1
;           (distances) and INTAB2 (X positions).
;   INIT5   the sector turned out to be empty: just reset the stack and the
;           sound shadows and go straight back to MAIN.
;
; Note INIT1 zeroes VSYNC,X for X = 0..$FF, which walks over the TIA registers
; AND all of zero page in one loop -- a classic 2600 clear-everything idiom.
;===============================================================================
;
;  INIT SECTION
INIT
       SEI
       CLD
       LDX    #$00   ;COLD START -- cold start: zero everything
       LDY    #$CE   ; GAME OVER -- PROGST value for the power-up screen
INIT2
;  WARM START: GAME RESET/SELECT
       LDA    #$00 
INIT1
       STA    VSYNC,X  ;zero TIA registers and all of RAM in one 256-byte sweep
       INX
       BNE    INIT1
       STY    PROGST 
       DEX    ;X=FF -- X = $FF...
       TXS  ;...becomes the stack pointer
;
       LDA    #$60 
       STA    JMPTIM  ;initial jump countdown (BCD)
       LDA    #$15 
       STA    CURSOR  ;initial chart cursor = your home sector
       LDA    #$04 
       STA    LIVES  ;you start with 4 spare ships
       LDY    #$07 
       JSR    DOOR24  ;SETUP CHART -- build the initial star chart from DORTB6
;
INIT3
;  ENTRY FROM MAN DIED
       LDY    #$FF 
       STY    FUEL  ;full fuel
       INY
       STY    ONESHT  ;Y=0 ,CLEAR DAMAGE -- clear the damage latches
       LDA    #$50 
       STA    CENTER  ;recentre the camera
       LDY    #$40    ;CRATERS -- craters are the default scenery graphic
       LDX    #VSHIP  ;your ship rest position
       DEC    LIVES  ;one life gone
       BNE    INIT6
       LDX    #$00 
INIT8
;  ENTRY FROM END GAME (DOOR)
       LDA    #$CA 
       STA    PROGST  ;PROGST value for game over
INIT6
       STX    HVERP1    ;REDUNDANT
       LDA    PROGST 
       AND    #$84  ;bit 7 or bit 2 set = the game is over or we are on a surface
       BEQ    INIT7   ;MAN DIED,GAME NOT OVER
;  RESET TO PLANET
       LDA    #CRATYP-W
       STA    IQPNTR  ;restart the crater script
       LDA    #$40 
       STA    GAMEST   ;YOUR PLANET -- GAMEST bit 6 = this is your own friendly planet
INIT4
; ENTRY FROM SHIP TAKEOFF
       STX    HVERP1  ;SHIP VERT
       LDA    #PBLK 
       STA    HGRAP1+3  ;clear the shared P1+3 slot
       LDX    #$03 
INIT10
       LDA    #$00 
       STA    XDELP0,X
       STA    ZDELP0,X  ;zero the horizontal and closing velocities
       LDA    INTAB1,X
       STA    ZPOSP0,X  ;INTAB1 = the four starting distances
       LDA    INTAB2,X
       STA    HHORP0,X  ;INTAB2 = the four starting X positions
       STY    HGRAP0,X  ;Y holds the graphic every slot starts as
       DEX
       BPL    INIT10
;
INIT7
;  MAN DIED GAME NOT OVER
       LDA    #$58 
       STA    PLINES  ;number of scanlines of planet surface
       LDA    #$80 
       STA    ZPOSP1  ;$80 = both photons off
       STA    ZPOSP1+1 
INIT5
;  ENTRY FROM SECTOR IS EMPTY
       LDX    #$FF 
       TXS              ;DEFINE STACK
       LDA    SHIPST 
       AND    #$10 
       ASL
       AND    SHIPST 
       STA    SHIPST    ;IF SHIPST=30 THEN =20 -- SHIPST $30 collapses to $20, i.e. jump-again becomes plain jump
       INX       ;X=0
       STX    VELOC  ;stop the ship drifting
       STX    CH0SHD 
       STX    CH1SHD 
;
;
;  END INIT SECTION
;
;
;===============================================================================
; M A I N  --  THE PER-FRAME LOOP.  Everything below is one NTSC frame.
;
; Structure:
;   MAIN    .. MAIN11   VSYNC, and position the starfield missile (M2) using
;                       the CRAZY table.  Then jump to MOVER in bank 4.
;   MAIN9               MOVER/GRAPH/CLOSE have run; convert the four HHITP0
;                       collision X values through CRAZY as well.
;   MAIN8               MESSRV builds the score digits.
;   HORZ15..HORIZ       position the ship, its photon, and the trench walls.
;   HORIZ5..HORIZ9      CHOOSE THE SCREEN: attract bars, star chart, hyperwarp,
;                       Saturn, or the normal space view.  Each calls SCRKER
;                       for the score and then vectors into its kernel.
;   MAIN2               overscan: reset the stack, start the overscan timer,
;                       pick the flame colour, recompute the difficulty tier.
;   TIMSRV              the housekeeping state machine (below).
;   then JOYSTK, AUDIO, SMARTS, BRAIN, and back to MAIN.
;
; The RTIMER / STIM64 accesses are the RIOT interval timer being used to pace
; the frame; the BPL spin loops wait for it.  PLUMBING.
;===============================================================================
MAIN
;
;  VBLANK SERVICE
;
       LDY    HHORM2  ;starfield X, which scrolls as you steer
       BIT    PROGST 
       BVC    MAIN11
       LDY    #$88     ;PLN/TRN  FIXED -- on a surface the starfield is fixed instead
MAIN11
       LDA    CRAZY,Y  ;CRAZY: turn a pixel X into coarse+fine positioning data
       LDY    RTIMER   ;FOR RANDOM
MAIN70
       LDX    RTIMER   ;TEMP  ***
       BPL    MAIN70  ;wait out the rest of the previous frame
       STA    WSYNC
       LDX    #$FF 
       STX    VSYNC
       STA    HDELM2
       AND    #$0F 
       LSR
       BCS    HORIZ1    ;DELAY
HORIZ1
       SEC
       NOP
       SBC    #$01 
       BPL    HORIZ1
       STA    HPOSM2
       STA    WSYNC
       STA    ADDEL
       JMP    EXIT3   ;TO MOVER -- hand off to MOVER in bank 4 (see header section 8)
;
; Back from MOVER/GRAPH/CLOSE.  Convert each object collision X into
; positioning data so the kernel can place the sprite.
MAIN9
       LDX    #$03 
HORIZ17
       LDY    HHITP0,X
       LDA    CRAZY,Y
       STA    HHITP0,X
       DEX
       BPL    HORIZ17
;
MAIN8
       JSR    MESSRV  ;build the score digits
;
HACKSEI
       NOP   ; TEMPORARY $78 ********* -- HACKSEI: a one-byte patch point the development system poked SEI
;   into.  In the shipped ROM it is a NOP.  PLUMBING.
;
;
;  END VBLANK SERVICE
;
;
       BIT    SHIPST  ;ship taking off: its X is driven by SHPSRV instead
       BMI    HORZ15
       LDY    HHORP1 
       LDA    CRAZY-$2D,Y
       STA    HHORP1 
HORZ15
       LDX    HOLDM2  ;HOLDM2 non-zero means the photon needs positioning too
       BEQ    HORZ14
       LDA    CRAZY-$2D,X
       STA    HHORP1+1 
HORZ14
       BIT    PROGST  ;V = surface mode
       BVC    HORZ16
       SEC     ;PLN/TRN
       LDA    #$A0 
       SBC    VWALL  ;the trench walls are positioned from VWALL
       TAX
       LDA    CRAZY+8,X
       STA    HOLDM0 
       LDY    VWALL 
       LDA    CRAZY-$0B,Y
       STA    HOLDM2 
HORZ16
       LDY    THGRP1  ;THGRP1 = which of the three ship graphics (level, bank L, bank R)
HORIZ
       LDX    $0285     ;TEMP ***
       BPL    HORIZ
       STA    WSYNC
       CLC
       LDA    HORTB1,Y
       ADC    RANDOM+1  ;HOLD CENTER -- RANDOM+1 doubles as the ship fine-position hold here
       TAX
       LDA    CRAZY,X
       STA    HDELM1
       AND    #$0F 
       LSR
       BCS    HORIZ4   ;DELAY
HORIZ4
       SEC
       NOP
       SBC    #$01 
       BPL    HORIZ4
       STA    HPOSM1
       STA    WSYNC     ;?? NEEDED ??
;
; ---- SCREEN SELECTION ------------------------------------------------------
;  SETUP FOR SCREEN
       LDX    #$00 
       LDA    PROGST 
       LSR  ;PROGST bit 0 = screen protect / attract dimming
       BCS    HORIZ5  ;SCREEN PROTECT
       AND    #$18  ;after the LSR these test PROGST bits 5 and 4, i.e. chart and
;   hyperwarp.  Neither set means the normal play view.
       BNE    HORIZ8
;  NORMAL
       LDA    LJOYT10,Y  ;LJOYT10 = the ship fine-position offset for this bank angle
       STA    RANDOM+1   ;HDELM1
       LDY    #<SATKRN  ;SATKRN draws Saturn on a planet approach...
       BIT    PROGST 
       BVS    HORIZ6   ;PLAN, DISP SATURN -- ...when V says we are in surface mode
       LDY    #<DIS170  ;DIS170 skips the shared P1+3 object...
       BIT    HGRAP1+3
       BMI    HORIZ7  ;NO P1+3
       LDY    #<DIS150  ;...DIS150 draws it
HORIZ6
       LDX    HHORP1+3 
HORIZ7
       STY    VECTP1
       LDA    CRAZY,X
       STA    STARS+1  ;TEMP HOLD HORIZ
       JSR    SCRKER  ;score kernel first
       JMP    EXIT2    ;DISPLY -- then the space display kernel in bank 2
HORIZ8
       AND    #$08  ;PROGST bit 4 = hyperwarp
       BEQ    HORIZ9
       JSR    SCRKER
       STA    HPOSM0
       STA    HPOSM2
       JMP    EXIT1  ;HWARP -- the hyperwarp tunnel kernel in bank 4
HORIZ9
       JSR    SCRKER
       JMP    CHART  ;otherwise the star chart
; SCREEN PROTECT: the game has been idle long enough that it paints slowly
; shifting colour bars instead of a picture, to avoid burning a CRT.
HORIZ5
       LDA    ATRACT   ;SCRN PROT.
       AND    #$C0 
       EOR    ATRACT+1 
       AND    #$C7 
       STA    COLBK
       LDY    #SCNSIZ+1
       JSR    WAIT1L
       STX    VBLANK
HORZ11
       JSR    LDSCR1
;  FALL THRU MAIN2
;
;
;
; ---- OVERSCAN --------------------------------------------------------------
MAIN2
;
;  OVERSCAN SERVICE
;
;
       STA    WSYNC
       LDA    #$20  ;FOR NOW***  ;28 (30 =#$24) LINES OVERSCAN -- start the overscan timer, ~28 scanlines
       STA    STIM64
       LDX    #$FF 
       STX    VBLANK
       TXS  ;reset the stack -- the kernels abuse it as a loop counter
       INX  ; X=0
       STX    THGRP1   ;FOR JOYSTK -- clear the ship bank angle ready for JOYSTK
       STX    HOLDM2   ;FOR PHOTON
       STX    COLBK
       LDA    ATRACT 
       AND    #$03 
       BEQ    MAIN88
       LDA    #$12 
MAIN88
       STA    HCOLP1     ;FLAME COLOR -- engine flame colour, alternating with the frame counter
       LDX    NEWLEV  ;DORT11[level] gives this level difficulty tier...
       LDA    DORT11,X
       AND    #$07 
       STA    NEWAVE  ;...as NEWAVE, 0..7.  It indexes most of the tuning tables.
;
;
;
HACKCLI
       NOP      ; TEMPOARY $58 *********** (sic) -- HACKCLI: the matching one-byte CLI patch point.  PLUMBING.
;
;
;
;
;-------------------------------------------------------------------------------
; TIMSRV -- OVERSCAN HOUSEKEEPING.  The state machine that owns everything
; that happens between frames:
;   * game reset switch                       -> restart
;   * the explosion pause timer PAUTIM        -> when it expires either you die
;                                                (INIT3) or play resumes
;   * ship takeoff / landing (SHIPST bit 7)   -> when the takeoff animation is
;                                                finished, rebuild the sector:
;                                                pick the new encounter script,
;                                                award or charge fuel, call DOOR
;   * SHIPST bit 0 = the sector is empty      -> score the cleared planet,
;                                                update the chart, move on
;   * the ATRACT frame counter                -> increment, and set the screen
;                                                protect bit when it wraps
; then calls HITSRV, JOYSTK+AUDIO (bank 2), SMARTS, and loops back to MAIN.
;-------------------------------------------------------------------------------
; TIMSRV
       LDA    ONESHT 
       LSR
       EOR    PORTB    ;GAME RESET -- PORTB bit 0 = the game reset switch
       LSR
       LDX    #NOCLER  ;X = NOCLER: restart without clearing the persistent variables
       BCS    TIMSR1
       LDY    #$4E  ;$4E = the PROGST value for a fresh game
       JMP    INIT2
TIMSR1
;
       LDA    PAUTIM  ;explosion pause running?
       BEQ    TIMSR4
       DEC    PAUTIM  ;count it down
       BNE    TIMSR4
       LDA    HVERP1  ;your ship Y is 0 only when you have been destroyed
       BNE    TIMSR4
       LDA    PROGST 
       ORA    #$02  ;set the "event just ended" latch...
       CMP    PROGST  ;...and if it was already set, you really died
       STA    PROGST 
       BNE    TIMS16
;  YOU DIED
       JMP    INIT3  ;YOU DIED: restart this life
TIMS16
       LDA    #$30 
       STA    PAUTIM  ;PAUSE A BIT LONGER -- otherwise hold the pause a little longer
TIMSR4
       LDA    SHIPST  ;SHIPST bit 7 = takeoff animation in progress
       BPL    TIMSR6
;  SHIP TAKEOFF
       LDY    HCOLP1+1 
       CPY    #$70  ;$70 means the takeoff animation has finished
       BNE    TIMSR9   ;NOT DONE
;  SHIP TAKEOFF DONE
       LDA    #$00 
       STA    IQSTAK 
       STA    PROGST   ;DEFAULT -- back to the default in-space state
       STA    GAMEST   ;DEFAULT
       LDA    #MONTYP-W  ;MONTYP = the default empty-space spawn script
       STA    IQPNTR   ;DEFAULT
       LDA    NEWATT 
       AND    #$F8  ;clear the pending-attack slot number
       STA    NEWATT 
       LDA    SHIPST 
       LDX    #$F2 
       CMP    #$B0  ;SHIPST $B0 = a wormhole jump, which skips the sector logic
       BEQ    TIMS18
       AND    #$10  ;bit 4 = we took off from a planet rather than hyperwarped
       BNE    TIMSR7  ;PLANET
       LDA    IQPATH-1  ;jump quality 0..3 comes from the path byte...
       AND    #$03    ;JMP QUAL I HOPE
       STA    GAMEST  ;...and is kept in GAMEST for the spawner to read
       EOR    #$FF 
       JSR    ADDFUL  ;a bad jump costs fuel
       JSR    DOOR  ;DOOR decides what is waiting in the sector we arrived at
TIMSR7
;  ENTRY FROM HITSRV
       LDX    #$E1  ;$E1 = the throttle value a new sector starts at
TIMS18
       STX    IQWARP 
       LDX    #VSHIP
       LDY    #PBLK
       JMP    INIT4
TIMSR6
       LSR
       BCC    TIMSR9  ;SHIPST bit 0 = this sector is now empty
;  SECTOR IS EMPTY
       AND    #$20  ;bit 5 = it was a planet or trench...
       BEQ    TIMS14
       LDY    #$01 
       LDA    #$08 
       JSR    ADDSC3 ;DESCTROY PLANET/TRN -- ...which is worth 8000 points
TIMS14
       LDA    NEWATT 
       AND    #$07 
       TAX
       LDA    LD107,X
       EOR    MAZRAM  ;clear this sector bit in the chart
       STA    MAZRAM 
       LDA    NEWATT 
       ASL
       ROL
       ROL
       EOR    NEWATT 
       AND    #$07 
       BEQ    TIMSR8
       LDA    NEWATT 
       AND    #$C0 
TIMSR8
       STA    NEWATT 
       JSR    DOOR2  ;recompute what the chart looks like now
       JMP    INIT5
TIMSR9
;
       LDA    PROGST 
       INC    ATRACT  ;advance the frame counter...
       BNE    TIMSR2
       INC    ATRACT+1  ;...and on a full 16-bit wrap turn on screen protect
       BNE    TIMSR2
       ORA    #$01 
       STA    PROGST 
TIMSR2
       AND    #$93  ;on the title, chart or attract screens the throttle is forced
       BEQ    TIMS17
;  IQWARP=0
       LDA    #$00 
       STA    IQWARP  ;...to zero so nothing moves
TIMS17
       JSR    HITSRV  ;did anything hit you
       JSR    EXIT5   ;JOY/AUDIO -- joystick and sound live in bank 2
       JSR    SMARTS  ;strategic AI and the star chart cursor
       JMP    MAIN
;
;
;
;
;    BANK3 SUBROUTINES
;
;
;
; INTAB1  the four starting object distances after a takeoff.
; INTAB2  the four starting object X positions.
; HITAB2  per-class MAXIMUM range at which your photon can hit something.
; LIVTAB  lives count -> playfield bit pattern for the ship icons.
; DORTB1  chart icon -> the PROGST value for that encounter.
; CHTAB1  the velocity values restored when you leave the star chart.
; DORT12  enemy-fleet speed per difficulty band.
INTAB1 .byte $05,$14,$27,$48
INTAB2 .byte $78,$28,$68,$3B
;
HITAB2
       .byte $1C,$2F,$2F,$38,$7F,$7F,$7F,$7F
;
LIVTAB .byte $80,$E0,$E0,$C0,$80
;  SHARE 2
SJOYT2
       .byte $00,$00,$80,$40
DORTB1
       .byte $48,$48,$00,$00,$48
;  SHARE 4
CHTAB1 .byte $00,$00,$00,$00,$00,$03,$00,$00
       .byte $00,$00,$03,$1A,$1A,$1A,$1A
; SHARE 2
DORT12
       .byte $00,$00,$09,$12,$1B
;
;
;
;===============================================================================
; S M A R T S  --  THE STRATEGIC LAYER
;
; Runs once per frame and owns everything above the dogfight:
;   * the JMPTIM countdown (BCD).  When it hits zero the enemy fleet moves,
;     GAMTIM advances, and if the fleet has reached a friendly planet, BLOWZ
;     destroys it.
;   * the NEGATIVE UNIVERSE effect (MAZSTA bit 7): random background flashes
;     and a noise burst.
;   * toggling the STAR CHART on and off with the fire button, saving and
;     restoring the object velocities across the switch (CHTAB1 / SMAR23).
;   * while the chart is up, SMRJOY handles cursor movement and the jump.
;   * SMRHLP is the enemy fleet AI: each fleet advances one step along a route
;     computed by FINDV, and may attack a friendly planet or ambush you.
;
; If none of that applies it falls through to BRAIN via EXIT4.
;===============================================================================
SMARTS
;  CHART BRAINS, ETC.
       LDY    PROGST  ;Y = PROGST, kept for the tests below
       LDA    SHIPST 
       ORA    PAUTIM  ;during a takeoff or an explosion pause...
       BEQ    SMART5
       TYA
       AND    #$DF  ;...force the chart bit off and go straight to BRAIN
       STA    PROGST 
SMART20
       JMP    EXIT4   ;DO BRAIN
SMART5
       TYA
       BNE    SMAR50  ;any non-zero PROGST means a special screen is up
       BIT    MAZSTA 
       BPL    SMAR50  ;MAZSTA bit 7 = negative universe
; NEGATIVE UNIVERSE
       LDX    #$42 
       LDA    RANDOM 
       CMP    #$0C            ;OR 08 -- occasional random noise burst and colour flash
       BCS    SMAR69
       LDA    #AUDEX6-J      ;NOISY
       STA    CH1PTR 
       LDX    #$8E 
SMAR69
       STX    COLBK
SMAR50
       TYA
       AND    #$83  ;only tick the strategic clock during normal play
       BNE    SMART1
       LDA    ATRACT 
       AND    #$1F  ;once every 32 frames
       BNE    SMAR11
       LDA    JMPTIM 
       SED  ;JMPTIM is BCD, so decimal mode is required for the countdown
       SEC
       SBC    #$01 
       CLD
       BNE    SMART3  ;not yet zero: just store it back
       INC    GAMTIM  ;the countdown expired: the enemy fleet advances
       LDA    NEWATT 
       BNE    SMAR55
       INC    GAMTIM  ;it advances twice as fast when no attack is pending
SMAR55
       CMP    #$40  ;NEWATT >= $40 means a friendly planet is already under attack
       BCC    SMART4
;  FALL THROUGH TO BLOWLZ ( NO BRAIN)
;
; BLOWZ -- a friendly planet has been destroyed.  Clear the attack flag, play
; the distress sound, swap in the destroy-planet spawn script, clear the
; sector from the chart, and set the negative-universe bit.
;
BLOWZ
       LDA    NEWATT 
       AND    #$3F   ;DEST PLN -- clear the attack-in-progress bits
       STA    NEWATT 
       LDA    #AUDHLP-J  ;the distress sound
       STA    CH1PTR 
       BIT    GAMEST  ;GAMEST bit 6 = you are standing on that planet...
       BVC    BLOWL1
       LDA    #BLOWIT-W  ;...so swap in the script that blows it up under you
       STA    IQPNTR   ;DEST PLAN
BLOWL1
; ENTRY FROM DOOR
       LDA    MAZRAM 
       AND    #$7F  ;clear the friendly-presence bit from the chart
       STA    MAZRAM 
       LDA    #$80   ;NEGATIVE UNIV. -- $80 = negative universe from here on
BLOWL3
; ENTRY FROM SMARTS
       ORA    MAZSTA 
       STA    MAZSTA 
       RTS
;
;
SMART4
       JSR    ADDFL2 ;-15 -- losing a planet costs 15 fuel
       LDA    #$50  ;25 SEC  (WAS #$60) -- reset the countdown to about 25 seconds
SMART3
       STA    JMPTIM 
SMAR21
       RTS

SMAR11
       CMP    JMPTIM  ;five ticks before the jump, run the enemy fleet AI
       BNE    SMART1
       CMP    #$05 
       BCS    SMART1
       JMP    SMRHLP
SMART1
       LDA    HGRAP1+3
       CMP    #$10         ;COBRA -- $10 in the shared slot is the cobra, which locks the chart out
SMAR30
       BEQ    SMART20
       LDA    GAMEST 
       AND    #$DF 
       CMP    GAMEST  ;GAMEST bit 5 is a one-shot: this reads and clears it
       STA    GAMEST ;ONESHOT GAMEST
       ROR
       LSR    ONESHT 
       AND    TRIG1  ;TRIG1 = the second fire button, which toggles the chart
       BMI    SMART9
       BCC    SMART9
       ASL    ONESHT 
SMAR22
;  ENTRY FROM SMRJOY
       LDA    PROGST 
       EOR    #$20  ;toggle PROGST bit 5 = the star chart
       STA    PROGST 
       AND    #$20 
       BEQ    SMAR24      ;EXIT CHART -- the bit went low, so we are LEAVING the chart
; SETUP CHART
       ASL               ;A = 40
       STA    ATRACT     ;HACK -- entering: park the frame counter (Doug calls it a hack)
; Leaving the chart: restore the 17 velocity bytes that CHTBLK was overlaying.
       BCC    BLOWL3     ;JMP
SMAR24
       LDX    #$10  ;leaving: restore the 17 velocity bytes CHTBLK was overlaying
SMAR23
       LDA    CHTAB1,X
       STA    XDELP0-1,X
       DEX
       BPL    SMAR23
       RTS

SMART9
       ASL
       ROL    ONESHT 
       LDA    #$20 
       TAY               ;SAVE
       BIT    PROGST     ;DEFINE V,Z
       BEQ    SMAR30     ;DO BRAIN
; FALL THRU TO SMRJOY
;
;
;-------------------------------------------------------------------------------
; SMRJOY -- STAR CHART INPUT.  Only runs while the chart is up.
;   * fire button      -> commit the jump: pick the abort script, set SHIPST to
;                         $20 (hyperwarp queued), recentre the camera and close
;                         the chart
;   * joystick         -> move CURSOR one cell, refusing moves blocked by a
;                         wall (NCHTB1 gives the wall bits) or off the grid
;   * every frame      -> blink the cursor by erasing and redrawing it
; EXPNTR is reused here as the auto-repeat delay for cursor movement.
;-------------------------------------------------------------------------------
SMRJOY
; IN CHART
       LDA    ATRACT  ;frame counter bit 7 gates whether a jump may be committed
       BPL    SMRJ43
       AND    #$BF 
       STA    ATRACT ;BIG HACK
       LDX    TRIG0  ;TRIG0 = the primary fire button
       BMI    SMRJ44
; JUMP
       LDX    #MONTYP-W       ;ABORT SPACE -- abort the space encounter...
       BVC    SMRJ40        ; V DEFINED ABOVE
       LDX    #CRATYP-W       ;ABORT PLANET/TRENCH -- ...or the surface one, whichever we are in
SMRJ40
       STX    IQPNTR  ;install the abort script
       STY    SHIPST        ;Y=$20 -- SHIPST $20 = hyperwarp queued
       ASL    ONESHT        ;NO SHOOT PHOTON -- swallow this press so it does not also fire a photon
       LSR    ONESHT 
       LDA    #$50 
       STA    CENTER  ;recentre the camera for the new sector
       BNE    SMAR22        ;JMP
SMRJ43
       LDY    #$01 
       STY    EXPNTR        ;JOYSTK WAIT -- reset the cursor auto-repeat delay
SMRJ44
       AND    #$07  ;which of the eight sector bits the cursor is over
       TAX
       LDA    MAZRAM 
       AND    SMSKTB,X  ;is anything actually there?
       BEQ    SMRJ22
       JSR    FINDV  ;FINDV works out what, and where
       LDY    TEMP6
       JSR    CHTERS  ;erase it...
       BNE    SMRJ60
       LDX    CURSOR 
       CPX    #$06 
       BEQ    SMRJ60
       BIT    RANDOM 
       BVS    SMRJ22
SMRJ60
       JSR    CHTDRW  ;...and redraw it.  Together these two make the icon blink.
SMRJ22
       DEC    EXPNTR  ;count down the cursor auto-repeat delay
       BPL    SMRJ99
       INC    EXPNTR ; EXPNTR = 0 ALWAYS?
       LDA    PORTA  ;PORTA = the joystick directions, active low
       LDX    #$03 
SMRJY1
       ASL
       BCC    SMRJY2
       DEX
       BPL    SMRJY1
SMRJ30
       LDA    ATRACT  ;cursor blink phase, from the frame counter
       AND    #$3F 
       LDY    #$00 
       CMP    #$21 
       BEQ    SMRJ31
       BCS    CHTRD2
SMRJ99
       LDY    #$02 
SMRJ31
       LDA    CURSOR 
       JSR    CHTERS      ;ERASE GUY, IF ANY (Y REG IS SAVED)
; FALL THRU TO CHTDRW
;
;
;
; CHTDRW -- draw icon Y at chart cell A.  Cells are packed two per byte, so
; the low bit of A selects the nibble.
; CHTERS -- erase the icon at chart cell A (mask off that nibble).  It returns
; A unchanged, which several callers rely on.
CHTDRW
; PUT OBJ ON CHART, A=POSIT, Y=GRAPHIC
       LSR
       TAX
       TYA
       BCC    CHTDR1
       ASL
       ASL
       ASL
       ASL
CHTDR1
       ORA    CHTBLK,X
       STA    CHTBLK,X
CHTRD2
       RTS
;
SMRJY2
       LDA    CURSOR 
       CLC
       ADC    SJOYT1,X
       CMP    #$30 
       BCS    SMRJ99 ;VERT
       TAY
       LDA    NCHTB1,Y
       AND    SJOYT2,X
       BNE    SMRJ99 ;HORIZ
       TYA
       LSR
       TAX
       LDA    CHTBLK,X
       BCC    SMRJY4
       LSR
       LSR
       LSR
       LSR
SMRJY4
       AND    #$0F 
       TAX
       CMP    #$0C 
       BCS    SMRJ99 ;HIT WALL
       TYA
       EOR    LSTCUR 
       BPL    SMRJY7
       ASL
       BNE    SMRJ30
SMRJY7
       LDA    CURSOR 
       STA    LSTCUR 
       ASL    LSTCUR 
       CPX    #$01 
       ROR    LSTCUR  ;SET BI
       STY    CURSOR 
       LDY    #$0F 
       STY    EXPNTR 
; FALL THRU TO CHTERS
;
CHTERS
; ERASE OBJ ON CHART, A=POSIT
       LSR
       TAX
       LDA    #$F0 
       BCC    CHTES1
       LDA    #$0F 
CHTES1
       AND    CHTBLK,X
       STA    CHTBLK,X
       TXA
       ROL            ;C STILL DEFINED ! (RESTORE A)
       RTS
;
;
;
;
;-------------------------------------------------------------------------------
; FINDV -- WHERE IS ENEMY FLEET X, AND WHAT IS IT?
;
; The chart is not stored as a map of contents; it is stored as eight ROUTES.
; Each fleet has a fixed starting cell (NCHTB5), a sign bitmap (NCHTB1) and a
; direction bitmap (NCHTB2), all indexed by [fleet][level].  FINDV replays that
; route JMPCNT[fleet] steps from the start and returns where the fleet is now.
;
; Returns  A = the chart cell, TEMP6 = the icon index, TEMP9 = the step count.
; FINDV6 is the "advance one more step" entry, used by SMRHLP to look ahead.
;
; The original warns that this is a BIG TIMING LOOP -- it is called from DOOR
; during vertical blank and can overrun.  Irrelevant to a Python port.
;
; NCHTB1 doubles as SJOYT3, the wall bitmap consulted by cursor movement, so
; the same data both routes the fleets and blocks your cursor.
;-------------------------------------------------------------------------------
FINDV1
       CLC
       LDX    #$00 
       BCC    FINDV2 ;JMP
FINDV
; X=INDEX (X NOT SAVED)
       TXA  ;fleet index...
       ASL
       ASL
       ASL
       ASL  ;...times 16...
       ORA    NEWLEV  ;...plus the level, indexes the per-level route tables
       TAY
       CPX    #$04 
       BCS    FINDV1
;   zero page comment insists MAZSTA follow JMPCNT
       CPX    #$02 
       LDA    FINTB2,X
       TAX
       LDA    JMPCNT,X  ;JMPCNT and MAZSTA are read as one two-byte array here.  This is
       BCC    FINDV8
       LSR
       LSR
       LSR
FINDV8
       AND    #$07  ;how many steps this fleet has taken so far, 0..7
       STA    TEMP9         ;FOR SMRHLP ONLY
       TAX
       LDA    NCHTB1,Y  ;TEMP7 = the sign bitmap for this route
       STA    TEMP7  ;SIGN
       LDA    NCHTB2,Y  ;TEMP4 = the direction bitmap for this route
       STA    TEMP4  ;DIR
       SEC
FINDV2
       LDA    NCHTB5,Y  ;NCHTB5 = the starting cell for this fleet on this level
       TAY
       AND    #$07 
       ADC    #$03 
       STA    TEMP6  ;GRAPHIC -- TEMP6 = which icon to draw for it
       TYA
       LSR
       LSR
       BPL    FINDV5  ;JMP
FINDV6
       LSR    TEMP7  ;one step: consume one sign bit...
       BCS    FINDV7
       ADC    #$08 
FINDV7
       ADC    #$F9 
       LSR    TEMP4  ;...and one direction bit, moving the cell accordingly
       BCS    FINDV5
       ADC    #$05 
FINDV5
       DEX
       BPL    FINDV6  ;repeat for as many steps as the fleet has taken
LDAF5  RTS
;
;
;
;
; FINTB2  maps a fleet index onto its JMPCNT byte (two fleets share one).
; SMHTB2  how much to advance a fleet, per jump-timer phase.
; NCHTB5  starting cell for each fleet on each level (8 fleets x 16 levels).
; DORTB3  the four wormhole destination cells.
; NCHTB1  route sign bits, and (as SJOYT3) the chart wall bitmap.
; NCHTB2  route direction bits.
; SJOYT1  joystick direction -> cursor cell delta.
FINTB2
       .byte $00,$01,$00
; SHARE 1
SMHTB2
       .byte $01,$01,$08,$08
;
;
NCHTB5
; INITIAL POSITIONS
       .byte $25,$64,$92,$00,$54,$54,$5D,$54,$8D,$B5,$5A,$0D,$34,$54,$3F,$9F
       .byte $22,$44,$6C,$54,$22,$0D,$35,$82,$1F,$85,$84,$00,$42,$82,$37,$6F
       .byte $00,$00,$27,$77,$61,$7D,$00,$2F,$31,$55,$00,$B5,$1A,$A5,$0C,$37
       .byte $00,$1A,$75,$7E,$82,$5F,$06,$1E,$AC,$17,$AF,$7A,$06,$37,$7F,$BE
       .byte $75,$9A,$37,$7A,$B5,$00,$3E,$3B,$0A,$62,$61,$6F,$00,$62,$8A,$5D
       .byte $9A,$09,$7C,$99,$29,$8A,$61,$62,$6A,$47,$07,$59,$B4,$B9,$53,$29
       .byte $62,$A4,$04,$04,$74,$04,$14,$5C,$BC,$25,$0C,$4C,$84,$09,$AD,$94
       .byte $50,$50,$98,$28,$A7,$38,$67,$A8,$40,$68,$38,$80,$50,$47,$00
;
; SHARE 1
DORTB3
; WORMHOLE DESTINATION
       .byte $00,$2A,$2F,$05
;
SJOYT3
; SHARE 2 BITS OF 1ST 48 BYTES OF NCHTB1
NCHTB1
; SIGNS
       .byte $B4,$26,$30,$00,$0F,$43,$95,$07,$1F,$0F,$07,$6A,$9C,$3C,$2A,$26
       .byte $11,$47,$B4,$3B,$38,$32,$2A,$53,$AA,$13,$0F,$00,$15,$5E,$A6,$33
       .byte $00,$00,$2A,$55,$AA,$0E,$00,$2A,$2A,$4D,$80,$27,$30,$2A,$33,$4E
       .byte $00,$38,$47,$2A,$1C,$0B,$2A,$55,$0F,$2A,$47,$71,$2A,$2A,$63,$55
;
NCHTB2
; DIRS
       .byte $38,$5F,$37,$00,$0E,$35,$2A,$55,$67,$17,$19,$2A,$65,$30,$2A,$26
       .byte $08,$40,$38,$57,$34,$38,$55,$50,$55,$52,$0E,$00,$78,$2F,$55,$2A
       .byte $00,$00,$2A,$55,$2A,$0F,$00,$2A,$55,$5C,$00,$2B,$2A,$2A,$4C,$55
       .byte $00,$0B,$4B,$55,$65,$20,$55,$2A,$0E,$2A,$26,$17,$55,$2A,$2A,$55
;
;
SJOYT1
       .byte $06,$FA,$01,$FF
;
;
;
;
;===============================================================================
; D O O R  --  WHAT IS IN THIS SECTOR?
;
; Called from TIMSRV the moment a hyperwarp finishes.  It asks FINDV for every
; fleet position, finds the one sitting on your cursor cell, and turns that
; into a game state:
;
;   DOOR4/DOOR8  found something.  Icon $0A is a WORMHOLE: set CURSOR to the
;                far end (DORTB3) and re-arm SHIPST for another jump.  Anything
;                else: PROGST comes from DORTB1 and the spawn script from
;                DORTB2, so this is the single place where "which enemy type
;                you meet" is decided.
;   DOOR50       icon 3 is FRIENDLY.  If CURSOR is 0 you have reached the end
;                of the star lanes and the game is won/over.
;   DOOR2        nothing there: the sector is empty.  DORTB9 lists the four
;                cells that start a NEW LEVEL; landing on one runs DOOR21.
;
; DOOR21 advances the level: reshuffle MAZRAM via SWAP, pick the next level
; from the big DORTB4 table, reload the chart if the level rolled over, and
; reset the jump timer.
;
; SWAP exchanges MAZRAM[0] with MAZRAM[level & 7], which is how the same eight
; bytes describe a different universe on every level.
;===============================================================================
DOOR21
; NEW LEVEL
       LDA    NEWATT 
       CMP    #$40  ;the fleet reached a friendly planet while you were jumping
       BCC    DOO438
       JSR    BLOWL1
DOO438
       JSR    SWAP   ;RESTORE
       LDA    DORTB8,Y  ;DORTB8[cell] = the cursor position the new level starts at
       STA    CURSOR 
       TYA
       ASL
       ASL
       ASL
       ASL  ;level index * 16...
       ORA    NEWLEV  ;...plus the current level
       LSR
       TAX
       LDA    DORTB4,X           ;THE BIG TABLE -- DORTB4 is the level progression table, packed two per byte
       BCC    DOOR37
       LSR
       LSR
       LSR
       LSR
DOOR37
       AND    #$0F 
       CMP    #$08 
       EOR    NEWLEV
       STA    NEWLEV  ;commit the new level number
       BCC    DOOR23  ;no carry means the level did not roll over
       LDY    #$0F 
DOOR24
;   ENTRY, LOAD MAZRAM (FROM INIT ONLY)
       LDX    #$07 
DOOR25
       LDA    DORTB6,Y  ;reload the eight chart bytes from DORTB6
       STA    MAZRAM,X
       DEY
       DEX
       BPL    DOOR25
DOOR23
       JSR    SWAP
       LDX    #$00 
       STX    NEWATT 
       LDY    NEWLEV
       LDA    GAMTIM
       SBC    DORT11,Y  ;DORT11[level] is the time budget for this level
       BCC    DOOR34
DOOR39
       SBC    #$04 
       BCC    DOOR35
       INX
       CPX    #$04 
       BCC    DOOR39
       LDA    MAZRAM  ;took too long: destroy a friendly planet
       AND    #$03 
       BEQ    DOOR35
       JSR    BLOWL1
DOOR35
       LDA    #$05  ;short countdown to the next fleet move
       STA    JMPTIM 
DOOR34
       LDA    DORT12,X  ;DORT12[band] sets how fast the fleets now advance
       STA    JMPCNT 
       BIT    MAZRAM  ;MAZRAM bit 7 = a friendly planet still exists
       BMI    DOOR36
       ORA    #$80 
DOOR36
       STA    MAZSTA 
       RTS

DOOR2
;  ENTRY FOR SECTOR IS EMPTY
       LDA    CURSOR 
       LDY    #$03 
DOOR20
       CMP    DORTB9,Y
       BEQ    DOOR21
       DEY
       BPL    DOOR20
       BMI    SWAP1      ;JMP
;
;
SWAP
       LDA    NEWLEV
       AND    #$07 
       TAX
       LDA    MAZRAM,X
       STA    TEMP4 
       LDA    MAZRAM 
       STA    MAZRAM,X
       LDA    TEMP4 
       STA    MAZRAM 
SWAP1
       LDX    CURSOR 
       STX    LSTCUR 
       RTS
;
DOOR
; JUST HYPERWARPED  (FROM TIMSRV)
       BIT    LSTCUR  ;LSTCUR bit 7 = you actually moved, so a jump really happened
       BPL    DOOR2          ;SECTOR EMPTY?!
       LDX    #$07 
DOOR3
       LDA    MAZRAM 
       AND    SMSKTB,X  ;is this sector bit occupied at all?
       BEQ    DOOR10
       STX    TEMP5 
       JSR    FINDV       ;BIG TIMING LOOP!!! WATCH OUT!! -- ask FINDV where that fleet is now
       LDX    TEMP5 
       CMP    CURSOR  ;does it sit on the cell you jumped to?
       BEQ    DOOR4
DOOR10
       DEX
       BPL    DOOR3
       BMI    SWAP1      ;SHOULDNT BE ABLE TO GET HERE, BAIL OUT!!!
DOOR4
; FOUND SOMETHING
       LDY    PNTR1  ;GRAPHIC -- Y = the icon FINDV returned (TEMP6 aliases PNTR1)
       CPY    #$0A  ;icon $0A = a WORMHOLE
       BNE    DOOR8
; WORMHOLE
       AND    #$03 
       TAY
       LDA    DORTB3,Y  ;DORTB3 gives the far end of the wormhole...
       STA    CURSOR 
       LDA    #$30 
       STA    SHIPST       ;JMP AGAIN -- ...and SHIPST $30 immediately queues another jump
       RTS

DOOR8
       LDA    DORTB1-3,Y  ;DORTB1[icon] = the PROGST value for this encounter
       STA    PROGST 
       LDA    DORTB2-3,Y  ;DORTB2[icon] = the spawn script.  THIS is where the game
;   decides what you are about to fight.
       STA    IQPNTR 
       CPY    #$03  ;icon 3 = a friendly planet
       BEQ    DOOR50      ;FRIENDLY
       INX               ;FIX FOR INDEX-1 -- record which fleet you ran into, in NEWATT
       TXA
DOOR60
; ENTRY FROM SMRHLP (SAVES A BYTE)
       ORA    NEWATT 
       STA    NEWATT 
DOOR5
       RTS

DOOR50
       LDA    CURSOR  ;STARS END?
       BNE    SMRHL4  ;cursor 0 = the end of the star lanes
; GAME OVER
       LDY    #$18    ;MAN -- the man is what you meet there
       STY    ONESHT  ;SET STARS END BIT -- mark the stars-end flag
       LDX    #VSHIP
       JMP    INIT8
;
;
;
;
;-------------------------------------------------------------------------------
; SMRHLP -- THE ENEMY FLEET AI, one fleet per jump-timer tick.
;
; Asks FINDV where the fleet is and FINDV6 where it is going next, then:
;   * if the next cell is YOUR cell, or the one you just left, it sets up a
;     CROSS FIRE ambush by injecting the HYPSUB script
;   * otherwise it advances the fleet on the chart and, if the destination is a
;     friendly planet, flags the attack in NEWATT and plays the distress sound
; SMRHL4 is also entered from DOOR when you arrive at a friendly planet.
;
; IRQREQ is the injection mechanism: it pushes the current VM program counter
; into IQSTAK and points IQPNTR at a new script -- a software interrupt into
; the NEWOBJ VM.  It refuses if the one-deep stack is already in use.
;-------------------------------------------------------------------------------
SMRHLP
; CHART THINK
       TAX
       EOR    NEWATT 
       CMP    #$40  ;already attacking a friendly planet: nothing more to do
       BCS    DOOR5       ;FRIENDLY ATTACK
       AND    #$07 
       BEQ    DOOR5
       LDA    MAZRAM 
       AND    LD107,X  ;is this fleet still alive on the chart?
       BEQ    IRQRQ1
       DEX                ;FIX INDEX
       JSR    FINDV  ;where the fleet is now...
       TAY                ;SAVE
       JSR    FINDV6      ;NEXT MOVE -- ...and where it moves to next
       LDX    TEMP9
       CPX    #$07  ;a fleet that has run its whole route stops
       BEQ    IRQRQ1       ;STOP
       STA    TEMP4 
       CMP    CURSOR  ;it is about to land on YOUR cell...
       BEQ    SMRHL1
       EOR    LSTCUR  ;...or the one you just left
       ASL
       BNE    SMRHL3
SMRHL1
; CROSS FIRE
       LDA    #HYPSUB-W  ;HYPSUB = spawn three warpers, i.e. a cross-fire ambush
       BNE    IRQREQ      ;JMP
SMRHL3
       LDA    PROGST 
       AND    #$20  ;PROGST bit 5: are we even looking at the chart?
       BEQ    SMRHL6      ;NOT IN THE CHART!!
       TYA
       JSR    CHTERS  ;erase the fleet from its old cell
SMRHL6
       LDY    JMPTIM 
       LDX    LDAF5,Y
       LDA    JMPCNT,X   ;JMPCNT OR MAZSTA
       CLC
       ADC    SMHTB2-1,Y   ;INC -- advance this fleet along its route
       STA    JMPCNT,X
       BIT    MAZRAM  ;MAZRAM bit 7 = a friendly planet exists
       BPL    IRQRQ1 ;NO FRIENDLY
       LDX    NEWLEV
       LDA    NCHTB5+$70,X  ;NCHTB5+$70 holds the friendly planet cell for each level
       LSR
       LSR
       CMP    TEMP4  ;is the fleet destination that planet?
       BNE    IRQRQ1
; HIT FRIENDLY
       TYA
       LSR
       ROR
       ROR
       JSR    DOOR60  ;record the attack in NEWATT
       LDA    #AUDHLP-J  ;the distress sound
       STA    CH1PTR 
       LDA    #$85           ;(WAS 99) -- give the player a longer countdown to respond
       STA    JMPTIM 
       BIT    GAMEST  ;GAMEST bit 6 = you are on that planet right now
       BVC    IRQRQ1
SMRHL4
; ENTRY FROM DOOR
       LDA    GAMEST 
       ORA    #$40  ;mark the planet as yours / under attack
       STA    GAMEST 
       LDA    NEWATT 
       BEQ    IRQRQ1
       ROL
       ROL
       ROL
       AND    #$03 
       JSR    DOOR60
       LDA    #ATTSUB-W  ;ATTSUB = the attack-wave spawn script
; FALL THRU TO IRQREQ
;
IRQREQ
; DEFINE A = IRQ ADDR
       LDY    IQSTAK  ;the VM stack is already in use: drop the request
       BNE    IRQRQ1
       LDY    IQPNTR  ;save the current VM program counter...
       DEY
       DEY
       STY    IQSTAK 
       STA    IQPNTR  ;...and vector the VM to the injected script
IRQRQ1
       RTS
;
;
; DORT11  level -> difficulty tier (the low 3 bits become NEWAVE) and the
;         level time budget.
; DORTB2  chart icon -> spawn script offset.  Read alongside DORTB1.
; DORTB9  the four chart cells that trigger a new level.
; DORTB8  the cursor position each new level starts at.
; DORTB6  the 16 initial MAZRAM bytes, two levels worth.
; DORTB4  the level progression table, packed two entries per byte.
; HITAB1  what your photon scores against each class, packed: the low 2 bits
;         pick the explosion sound from HITAB4, the rest is the BCD score.
; HITAB5  difficulty -> the GAMEST value set when you catch the man.
DORT11
       .byte $00,$00,$0B,$11,$F2,$09,$F4,$0A
       .byte $53,$5B,$2C,$F2,$41
LDD7E  .byte $F4,$F4,$F4
;
DORTB2
       .byte FRNTYP-W,TRNTYP-W,BLKTYP-W,FIGTYP-W
       .byte ENETYP-W,PIRTYP-W,PLNTYP-W,MONTYP-W,COBTYP-W
;
DORTB9
       .byte $18,$2D,$1D,$03
DORTB8
       .byte $23,$04,$12,$2C
;
DORTB6
; INITIAL MAZRAM VALUES
       .byte $F3,$FB,$FF,$FE,$FF,$EF,$FB,$FF
       .byte $FF,$FF,$FB,$FD,$EF,$FF,$7F,$FF
;
;

DORTB4
       .byte $11,$16,$3E,$21,$24,$43,$31,$71
       .byte $37,$73,$52,$43,$21,$75,$71,$16
       .byte $11,$31,$26,$13,$37,$20,$14,$43
       .byte $35,$43,$37,$72,$16,$27,$17,$51
;
HITAB1
       .byte $60,$66,$07,$12,$A0,$4F,$03,$00
       .byte $00,$00,$02,$02,$64,$62,$83,$00
       .byte $01,$0C,$03
HITAB4
       .byte $02,$98,$9F,$AF
HITAB5
       .byte $14,$14,$14,$1A,$1E
;
;
;
; ADDSCR -- add A to the score in BCD.  ADDSC3 adds into digit pair Y instead
; of the units, which is how the 8000-point planet bonus is applied.
; Python: score += value; the SED/CLD pair is just decimal mode.
ADDSCR
; A=VALUE
       LDY    #$00 
ADDSC3
; ENTRY FOR OTHER DIGITS
       SED
       CLC
ADDSC1
       ADC.wy SCORE,Y
       STA.wy SCORE,Y
       BCC    ADDSC2
       LDA    #$01 
       INY
       CPY    #$03 
       BCC    ADDSC1
ADDSC2
       CLD
       RTS
;
;
;
;
;
;===============================================================================
; H I T S R V  --  DID ANYTHING HIT YOU, AND DID YOU HIT ANYTHING?
;
; Runs once per frame during overscan.  It does NOT use the TIA collision
; latches for the main test (those are too coarse); instead it compares the
; precomputed HHITP0 collision X values from GRAPH against your ship and your
; two photons, and the object Y values against a vertical band.
;
; Structure:
;   HITSRV..HITSR1   set up the band.  On a surface the band comes from VWALL
;                    (so flying into the trench wall counts as a hit); in space
;                    it comes from your ship Y plus the P1+3 height in HOLDM0.
;   HITSR1           loop over the four object slots.  A slot is a candidate if
;                    its HHITP0 is negative (i.e. GRAPH says it overlaps) and
;                    it is not already an explosion.
;   HITSR5           work out WHAT it hit: your ship (Y index 0) or one of the
;                    photons (Y index 1 or 2).
;   HITSR7           IT HIT YOUR SHIP.  Branches by target class:
;                      the MAN     -> you catch him; sets the trench speed and
;                                     opens the door
;                      the LZ      -> land.  On your own planet you refuel and
;                                     repair; otherwise this is the trench
;                                     entrance
;                      a MOON      -> damage
;                      anything else at high closing speed -> you die
;                    Damage accumulates in ONESHT bits 4..6; the fourth hit
;                    destroys you.
;   HITSR8           YOUR PHOTON HIT IT.  Range-checks against HITAB2/HITAB3,
;                    scores it from HITAB1, plays the matching sound from
;                    HITAB4, starts the right explosion script, and freezes the
;                    world with PAUTIM.
;
; HITS25 is the "you are destroyed" entry: it turns your ship into an explosion
; at the camera and zeroes HVERP1, which is the flag TIMSRV reads to know you
; died.
;===============================================================================
HITSRV
       LDA    HVERP1  ;your ship Y is 0 only while you are already dead
       BEQ    HITS20
       LDA    SHIPST  ;no collisions during a takeoff
       BNE    HITS20
       LDX    FUEL  ;out of fuel means you are already blowing up
       BEQ    HITS52   ;NO FUEL BLOWUP
       LDA    PROGST 
       AND    #$B1  ;not during game over, screen protect or hyperwarp
       BNE    HITS20
       LDY    #$7F  ;space default: the whole screen width is the hit band
       BIT    PROGST  ;V = surface mode
       BVC    HITS14    ;A=0
;  PLAN/TRENCH
       LDY    VWALL  ;on a surface the TRENCH WALL position becomes the hit band...
       CPY    #$13  ;...and coming within $13 of it means you scraped the wall
       BCC    HITS43
       DEY
       DEY
       LDA    #$60 
HITS14
       STA    TEMP5  ;TEMP5 = the horizontal hit tolerance
       TYA
       LDY    HGRAP1+3
       BMI    HITSR3
       EOR    HOLDM0      ;FROM CLOSE!, NOT DEFINED FOR PLN/TRN -- HOLDM0 is the P1+3 object height that CLOSE left for us
       ORA    #$C0 
       SEC
       ADC    HVERP1+3  ;fold in the P1+3 Y so a big moon can also hit you
HITSR3
       STA    TEMP4  ;TEMP4 = the vertical hit threshold
;   coarse pre-filter for the scratch slot
       LDA    MIPL  ;MIPL is the TIA missile/player collision latch, used only as a
       STA    HHITP0 
       LDX    #$03 
HITSR1
       LDA    HHITP0,X  ;GRAPH left HHITP0 negative when the sprite overlaps your lane
       BPL    HITSR2
       LDA    HGRAP0,X  ;object is off screen
       BMI    HITSR2
       AND    #$78 
       CMP    #$38   ;EXPLOS -- class $38: explosions cannot hit you
       BEQ    HITSR2
       CLC
       ADC    TEMP5 
       STA    TEMP6  ;TEMP6 = which object class we are testing
       CMP    #$A0  ;$A0 is a crater, which is scenery and never hits
       BEQ    HITSR2  ;CRATER
       LDA    HVERP0+0,X
       CMP    TEMP4  ;is the object inside the vertical hit band?
       BCC    HITSR4  ;A HIT
HITSR2
       DEX
       BPL    HITSR1
HITS20
       RTS

HITS43
       TAX   ;A=0 -- HITS43: you touched the trench wall.  Toggle the crash state.
       LDA    GAMEST 
       EOR    #$01  ;GAMEST bit 0 flips: even means you got through the gap
       STA    GAMEST 
       LSR
       LDY    #$E8 
       STY    IQWARP  ;slam the throttle back
       BCS    HITS42   ;MADE IT THRU
HITS52
       JMP    HITS25  ;you did not get through: you are destroyed
HITSR4
       ADC    #$06     ;C=0 -- HITSR4: something is in range.  Work out WHAT it hit.
       STA    TEMP7 
       LDY    #$02 
HITSR5
       LDA.wy HVERP1,Y  ;compare against your ship (Y=0) then each photon (Y=1,2)
       CMP    TEMP7 
       BCS    HITSR6
       CPY    #$00 
       BEQ    HITSR7  ;Y=0 means it reached your ship
       LDA.wy ZPOSP1-1,Y  ;a photon only counts if it is switched on (bit 7 clear)
       BMI    HITSR6
       JMP    HITSR8
HITSR6
       DEY
       BPL    HITSR5
;  OOPS!
       RTS

; ---- IT HIT YOUR SHIP ------------------------------------------------------
HITSR7
;  HIT SHIP
       LDY    TEMP6  ;HITSR7: it hit YOUR SHIP.  TEMP6 says what class it was.
       CPY    #$10  ;class $10 = darter, which is lethal at any range
       BEQ    HITS45  ;DARTER
       LDA    ZPOSP0,X
       CMP    #$0C  ;anything else only counts at very close range
       BCS    HITSR9
       CPY    #$78  ;class $78 = THE MAN
       BNE    HITS10
; HITMAN
       LDA    #AUDCTH-J  ;the catch sound
       STA    CH1SHD 
       LDA    PROGST 
       AND    #$08  ;PROGST bit 3 clear means we are in the trench, so this is the
       BNE    HITS42
       LDY    NEWAVE  ;TRENCH
       LDA    HITAB5,Y  ;HITAB5[difficulty] sets the escape speed and opens the door
       STA    GAMEST    ;SPEED+OPEN DOOR
       LDY    #$FC 
       BNE    HITS77   ;JMP
HITS42
       LDA    #PBLK  ;anything else at this point simply vanishes
       STA    HGRAP0,X
       RTS

HITS10
       CPY    #$80  ;class $80 = THE LANDING ZONE
       BNE    HITS13
; LZ
       CMP    #$0D  ;only counts once you are practically on top of it
       BCS    HITSR9
       LDA    CENTER 
       SBC    HHORP0,X  ;how far off centre you are...
       CMP    #$04  ;...must be within 4 pixels or you just bump it
       BCS    HITS16
       BIT    GAMEST  ;GAMEST bit 6 = your own planet, so this is a refuel
       BVS    HITS41  ;YOUR PLANET
;  TRN ENTRANCE
       LDA    #TRNTY1-W  ;otherwise this is the TRENCH ENTRANCE: swap in TRNTY1 and
       STA    IQPNTR 
       JMP    TIMSR7
HITS41
       INC    FUEL  ;refuelling: one unit per frame while you sit on the pad
       BNE    HITS12
       DEC    FUEL  ;tank full, so undo the increment
       LDA    ONESHT 
       AND    #$8F  ;a full refuel also repairs all accumulated damage
       STA    ONESHT   ;FIX DAMAGE
       RTS

HITS12
       LDA    PROGST 
       ORA    #$02  ;set the event latch so TIMSRV lifts you off again
       STA    PROGST 
       LDA    #AUDFUL-J  ;the tank-full sound
       STA    CH1SHD 
       RTS

HITS16
       LDA    #AUDBMP-J  ;the bump sound (you missed the pad)
       LDY    #$04 
       STA    CH1PTR 
HITS77
       STY    IQWARP  ;and a hard throttle cut
HITSR9
       RTS

HITS13
       LDA    IQWARP 
       CMP    #$F0  ;at very high throttle nothing can touch you
       BCC    HITSR9     ;NO HITS AT HIGH SPEED
       LDA    HGRAP0,X
       CMP    #$40  ;class $40 and up are the moons, which are always fatal
HITS45
;  FROM DARTER BRANCH
       LDY    #AUDEX4-J  ;the moon-impact sound
       BCS    HITS26   ;HIT MOON
       LDA    RANDOM 
       AND    #$3F 
       CMP    ZPOSP0+1  ;the nearer the object, the more likely the hit is fatal
       BCS    HITS25   ;DIE
       LDA    NEWAVE  ;on the easiest difficulty tier a hit is only damage
       BEQ    HITS26 ;DAMAGE ONLY
       LDA    ONESHT 
; YOU ARE DESTROYED: replace your ship with an explosion at the camera.
       LSR
       AND    #$70  ;accumulate damage in ONESHT bits 4..6
       ORA    #$40 
       ORA    ONESHT 
       STA    ONESHT 
       AND    #$10  ;the fourth hit is fatal
       BEQ    HITS26 ;DAMAGE ONLY
HITS25
; ENTRY
       LDA    CENTER  ;HITS25: YOU ARE DESTROYED.  Put an explosion at the camera.
       STA    HHORP0,X
       LDA    #$0C 
; ---- YOUR PHOTON HIT IT ----------------------------------------------------
       STA    ZPOSP0,X
       LDA    #VSHIP+1
       STA    HVERP0+0,X
       LDY    #AUDEXP-J  ;the death explosion sound
       STY    CH1PTR 
       LDA    #$00 
       STA    HVERP1  ;ship Y = 0 is the flag TIMSRV reads to know you died
HITS26
       STY    CH0PTR 
       JSR    ADDFL2 ;-15 -- a death costs 15 fuel
       LDA    #$0E 
       STA    COLBK
       BNE    HITS15  ;JMP
HITSR8
;  HIT PHOTON
       STY    TEMP9  ;HITSR8: YOUR PHOTON HIT IT.  TEMP9 = which photon.
       LDY    TEMP6 
       CPY    #$10  ;class $10 = darter, always a hit
       BEQ    HITS51  ;DARTER
       LSR
       LSR
       CMP    #$08 
       BCC    HITS19
       LDA    #$07 
HITS19
       CPY    #$60  ;class $60 and below use the unhalved range...
       TAY
       LDA    ZPOSP0,X
       BCC    HITS21
       LSR   ;PLANET/TRENCH -- ...surfaces halve it, because the view is compressed
HITS21
       CMP    HITAB2,Y  ;HITAB2[class] = the maximum range this class can be hit at
       BCS    HITSR9
       CMP    HITAB3,Y  ;HITAB3[class] = the minimum range
       BCC    HITSR9
HITS51
       LDA    TEMP6
       LSR
       LSR
       LSR
       TAY
       CMP    #$0F  ;index $0F is the man, who cannot be shot
       BEQ    HITSR9   ;MAN
       CMP    #$10  ;index $10 is the landing zone...
       BNE    HITS18
       BIT    GAMEST  ;...which only counts on an ENEMY planet
       BVC    HITSR9   ;TRN ENTRANCE
;   LZ
       JSR    BLOWZ  ;shooting it destroys the planet
HITS18
       LDA    HITAB1,Y  ;HITAB1[class] packs the sound index and the BCD score
       PHA          ;   LOOK OUT !!
       AND    #$03 
       TAY
       LDA    HITAB4,Y  ;HITAB4 picks the explosion sound
       STA    CH1PTR    ;SOUND
       PLA          ; LOOK OUT
       LSR
       AND    #$7E  ;the rest of the byte, shifted, is the score value
       JSR    ADDSCR
       LDY    TEMP9
       LDA.wy ZPOSP1-1,Y
       CMP    #$18 
       LDA    #$80 
       STA.wy ZPOSP1-1,Y  ;switch off the photon that scored
       LDY    #EXPTRN-EXPTAB  ;pick the explosion script: trench...
       LDA    PROGST 
       EOR    #$40 
       BEQ    HITS23    ;TRNCH
       LDY    #EXPFAR-EXPTAB  ;...a distant kill...
       BCS    HITS22
HITS15
       LDY    #EXPREG-EXPTAB  ;...a normal kill...
HITS22
       BIT    PROGST 
       BVC    HITS23
;  PLANET/TRENCH
       LDY    #EXPPLN-EXPTAB  ;...or a planet surface kill
       LDA    IQPATH,X
       AND    #$03 
       EOR    #$03 
       BNE    HITS23
       STA    IQWARP    ;=0 VISUAL COSMETIC?
HITS23
       STY    EXPNTR 
; Cancel every OTHER explosion currently running, so only one plays at a time,
; then turn the object that was hit into the explosion.
       LDY    #$04 
HITS62
       LDA.wy HGRAP0-1,Y
       AND    #$78 
       CMP    #$38 
       BNE    HITS63
       LDA    #$E0 
       STA.wy HGRAP0-1,Y   ;TURN OFF EXPLOS
HITS63
       DEY
       BNE    HITS62
       LDA    #$20 
       STA    PAUTIM 
       LDA    #$3F 
       STA    HGRAP0,X
       STY    XDELP0,X     ;Y=0
       STY    YDELP0,X
       STY    ZDELP0,X
       RTS
;
;
;
; ADDFUL -- add signed A to FUEL, clamping at zero.  ADDFL2 is the common
; "lose 15 fuel" entry.  There is no upper clamp; refuelling relies on the
; caller noticing the wrap (see HITS41).
ADDFL2
; ENTRY -15
       LDA    #$F0 
ADDFUL
       SEC
       ADC    FUEL 
       BCS    ADDFL1
       LDA    #$00 
ADDFL1
       STA    FUEL 
       RTS
;
;
;
;
;
;
;-------------------------------------------------------------------------------
; BANK 3 EXIT TRAMPOLINES.  PLUMBING -- see header section 8.
; As in bank 1, small tables (LJOYT10, HORTB1, HITAB3) are wedged into the gaps
; between the bank-switch stubs.
;   LJOYT10  ship bank angle -> fine horizontal offset
;   HORTB1   ship bank angle -> coarse horizontal offset
;   HITAB3   per-class MINIMUM photon hit range (the twin of HITAB2)
;-------------------------------------------------------------------------------

;     BANK SELECT CODE
; ORG BANK3+$0FCC
EXIT5
       STA    STROB2   ;JMP EFCF
EXIT4
       STA    STROB1   ;JMP CFD2
EXIT3
       STA    STROB4   ;JMP FFD5
       JMP    INIT
       RTS

LJOYT10
       .byte $F0,$00,$00
HORTB1
       .byte $FD,$E1,$E6
HITAB3
       .byte $00,$00,$00,$08,$10,$1C,$1E,$20
       JMP    SCANDS
EXIT2
       STA    STROB2 ;JMP EFED
EXIT1
       STA    STROB4 ;JMP FFF0
       JMP    MAIN8
       JMP    MAIN9
       .byte "DOUG N"
       .word INIT
       .word INIT
;
;
;
; ************************
;  END INCLUDE BANK3.SRC
; ************************

;
;
;===============================================================================
; B A N K   2  --  THE SPACE DISPLAY KERNEL, YOUR SHIP, JOYSTICK, SOUND
;
; Two thirds of this bank is the kernel that draws the normal space view; the
; rest is JOYSTK (steering), SHPSRV (your ship graphic and photon firing) and
; AUDIO (the two-channel sound sequencer).
;
;-------------------------------------------------------------------------------
; HOW THE SPACE KERNEL WORKS (the summary; the per-fragment comments below
; only add what each piece contributes)
;
; It is a STATE MACHINE, not a loop.  Two chains run concurrently down the
; screen, one per hardware player:
;
;   the P1 chain  (VECTP1) draws, from the top down:
;                   the shared P1+3 object (Saturn rings / big moon / warp),
;                   your far photon (P1+2), your near photon (P1+1),
;                   and finally your ship (P1+0)
;   the P0 chain  (VECTP0) draws the four enemy/scenery objects, reusing the
;                   single P0 sprite for all of them -- which is exactly why
;                   BRAIN and CLOSE work so hard to keep them sorted by Y and
;                   non-overlapping.
;
; Each fragment ends in JMP (VECTPn), and each fragment stores the LOW BYTE of
; whichever fragment should run next.  So "what is on screen" is encoded in two
; zero page bytes.  The naming convention:
;
;   DISnn0  SETUP    -- latch the pointers for the next object
;   DISnn0  HPOS     -- position it horizontally (the CRAZY/delay-loop dance)
;   DISnn0  WAIT     -- burn scanlines until Y reaches the object top
;   DISnn0  DISPLAY  -- actually emit the sprite rows
;
; Per object the kernel needs three pointers, all pre-biased by the object Y so
; that (ptr),Y indexes straight into the sprite:
;   MOON1 / MISC1  the GRAPHIC   (from MTABL1 low, MTABL3 high)
;   MOON3 / MISC2  the COLOUR    (from MTABL2, one colour byte per scanline)
;   MOON2          the HMOVE DELTA (from MTABL4) -- a per-scanline horizontal
;                  nudge, which is how craters, rings and explosions get to be
;                  wider than the eight pixels a player normally gives you
;
; The STARFIELD is the third missile (M2): (STARS),Y fetches a bit pattern each
; scanline from STARTB, which JOYSTK scrolls as you steer.
;
; Y counts DOWN from TOPSCN to BOTSCN, i.e. Y is the screen row measured from
; the bottom.  A sprite ends when the fetched graphic byte is zero, which is
; why every sprite block starts with two $00 bytes.
;
; PYTHON PORT: ignore all of it.  Read MTABL1..MTABL4 to recover, for every
; object type, its sprite / colour ramp / width profile, then draw the object
; list normally.  The only behaviour worth reproducing is the vertical sort.
;-------------------------------------------------------------------------------
;  ******************************
;  VERSION 10.7  28-JUL-84
;COPYRIGHT (C) 1986, DOUGLAS NEUBAUER
;  BANK2.SRC FILE
;INCLUDE FOR UNIV.SRC, $E000 BANK
;  ******************************
;
;
;**********
; ORG BANK2   ; BEGIN BANK2
;**********
;
;
;
; WARNING: MUST BE ON PAGE BOUNDARY

       seg bank2
       ORG $2000
       RORG $F000
;
; --- SPACE KERNEL FRAGMENT: draw YOUR SHIP.  Emits ship rows from (MISC1),Y
;     with per-scanline colour from (MISC2),Y, and the starfield bit from
;     (STARS),Y into missile 2.  A zero graphic byte means the ship is done, at
;     which point the P1 chain switches to DIS130 for the photons.
DIS500
; DISPLAY SHIP
       LDA    (MISC1),Y
       STA    GRAFP1
       BEQ    DIS501
       LDA    (MISC2),Y
       STA    COLPM1
DIS502
; ENTRY FROM WAIT SHIP, 28 CY
       STX    HDELP0
       DEY
       LDA    (STARS),Y
       STA    GRAFM2
       ORA    #SCLR
       STA    COLPF
;
       LDA    (MISC1),Y
       TAX
       LDA    (MISC2),Y
       STA    COLPM1
       ASL
       STA    GRAFM1
       JMP.ind (VECTP0)
DIS501
       STA    GRAFM1
       DEY
       LDA    (MISC1),Y
       STA    GRAFP1
       STX    HDELP0
       LDA    #<DIS130
       STA    VECTP1
       LDA    (STARS),Y
       STA    GRAFM2
       ORA    #SCLR
       STA    COLPF
       LDX    #$00 
       NOP
       LDA    HCOLP1 
       STA    COLPM1
       JMP.ind (VECTP0)
;
; --- FRAGMENT: WAIT for the ship.  Burns scanlines until Y reaches the ship Y.
DIS780
; WAIT SHIP
       LDA    #<DIS500  ;=0
       STA    VECTP1
       STA    GRAFP1
       CPY    HVERP1 
       STA    HDELP1
       BCC    DIS502
       LDA    #<DIS780
       JMP    DIS910
;
;
;
; --- FRAGMENT: WAIT for the end of the picture.  The last thing the P1 chain
;     does; everything below the lowest object is drawn by this.
DIS580
; WAIT END OF SCREEN
       LDA    #$00 
       STA    GRAFP1
       DEY
       JMP    DIS912
;
;
;
; --- FRAGMENT: horizontally position the photon (DIS330) or the ship (DIS730).
;     Both hand off to DIS740, which burns the fine-position cycles.  PLUMBING.
DIS330
; HPOS PHOTON
       LDA    #<DIS370
       JMP    DIS740
;
;
DIS730
; HPOS SHIP
       LDA    #<DIS780
       JMP    DIS740
;
;
;
; --- FRAGMENT: draw a PHOTON.  The graphic is ANDed with (RANDOM),Y, which is
;     what makes the torpedo shimmer.  When the graphic runs out the chain
;     pops the next object from PNTRP1.
DIS130
; DISPLAY P1 PHOTON
       LDA    (MISC1),Y
       AND    (RANDOM),Y
       STA    GRAFP1
;
       DEY
DIS132
; ENTRY FROM WAIT PHOTON, 28 CY
       STX    HDELP0
       LDA    (STARS),Y
       STA    GRAFM2
       ORA    #SCLR
       STA    COLPF
;
       LDA    (MISC1),Y
       BNE    DIS131
       LDX    PNTRP1 
       STX    VECTP1 
       LDA    DIS500-1,X
       STA    PNTRP1 
       LDX    #$00 
       JMP.ind (VECTP0)
DIS131
       AND    (RANDOM),Y
       TAX
       LDA    #<DIS130
       STA    VECTP1
       JMP.ind (VECTP0)
;
;
;
; --- FRAGMENT: WAIT for a photon.
DIS370
; WAIT PHOTON
       LDA    #$00 
       STA    GRAFP1
       CPY    VERTP1
       DEY
       STA.w  $0021   ; original code used .byte to get this instr
       BCC    DIS132
       CPY    VERTP1
       BCS    DIS371
       LDA    #<DIS130
       STA    VECTP1
DIS371
       JMP    DIS912
;
;
       .byte <DIS700
;
; --- FRAGMENT: SETUP the near photon (P1+1) / far photon (P1+2).  Latches
;     VERTP1, MISC1 and the horizontal position for the fragments above.
DIS350
; SETUP P1+1
       LDA    #$00
       STA    GRAFP1
       LDA    HVERP1+1
       STA    VERTP1
       LDA    HGRAP1+1
       STA    MISC1
       LDA    HHORP1+1 
       JMP    DIS902
;
;
DIS300
; SETUP P1+2
       LDA    #$00 
       STA    GRAFP1
       LDA    HVERP1+2 
       STA    VERTP1
       LDA    HGRAP1+2 
       STA    MISC1
       LDA    HHORP1+2
       JMP    DIS902
;
;
       .byte <DIS580
;
; --- FRAGMENT: SETUP your ship (P1+0).  The last object in the P1 chain.
DIS700
; SETUP SHIP
       LDA    #$00 
       STA    GRAFP1
       LDA    HGRAP1 
       STA    MISC1
       STA    MISC2
; 
       LDA    HHORP1 
       STA    HDELP1
       AND    #$0F 
       STA    HOLDP1
       LDA    #<DIS730
       JMP    DIS900
;
;
;
; JOYTB1..JOYTB7 -- joystick response tables, indexed by the two vertical bits
; of PORTA.  JOYTB1/JOYTB2 scroll the starfield X, JOYTB3 scrolls the starfield
; pointer, JOYTB4/JOYTB5/JOYTB6 move the camera, JOYTB7 wraps it.
; They overlap on purpose (the ;SHARE 1 notes).
JOYTB6 .byte $9F
;  SHARE 1
JOYTB1 .byte $00,$08,$F8
;  SHARE 1
JOYTB2 .byte $00,$A0,$60
;  SHARE 1
JOYTB3
;  SHARE 4
JOYTB4 .byte $00
;  SHARE 1
JOYTB5 .byte $FF,$01
;  SHARE 1
;
;
; SATAB1 -- Saturn: 15 bytes of ring/body graphic followed by the same shape at
; a second size.  SATAB2 (further down) is its per-scanline HMOVE/size stream.
SATAB1
;  GRAPHIC
       .byte $00,$E0,$FC,$FF,$FF,$EF,$C7,$C7
       .byte $98,$07,$07,$01,$00,$00,$00
       .byte $00,$E0,$E0,$C0,$E0,$E0,$C0,$E0,$C0
       .byte $E6,$FE,$FC,$F8,$F0,$C0,$00,$00
;
;
;ORG BANK2+$10D  ;TEMPORARY? *********
;
; --- FRAGMENT: WAIT for the next P0 object.  DIS250 is the idle state of the
;     P0 chain: it counts Y down until the next object top is reached.
DIS250
; WAITP0
       STA    WSYNC
       STA    ADDEL
       STX    GRAFP1
;
       LDA    #<DIS200
       STA    VECTP0
       CPY    VERTP0
       BCC    DIS203
       DEY
       LDA    (STARS),Y
       STA    GRAFM2
       LDX    #$00 
       CPY    VERTP0
       BCC    DIS206
       LDA    #<DIS250
       JMP    DIS403
;
;
;
; --- FRAGMENT: DRAW a P0 object.  Three streams per scanline: (MOON1),Y the
;     graphic, (MOON3),Y the colour, (MOON2),Y the horizontal delta that makes
;     the object wider than eight pixels.
DIS200
; DISPLAY P0
       STA    WSYNC
       STA    ADDEL
       LDA    (MOON1),Y
       STA    GRAFP0
       STX    GRAFP1
       LDA    (MOON3),Y
       STA    COLPM0
;
       LDA    (MOON2),Y
       STA    HDELP0
DIS203
; ENTRY FROM DIS250  ,32
       DEY
       LDA    (STARS),Y
       STA    GRAFM2
;
       LDA    (MOON1),Y
       STA    GRAFP0
       BEQ    DIS201
       LDA    (MOON2),Y
       TAX   ;HDELP0
       LDA    (MOON3),Y
DIS206
       STA    WSYNC
       STA    ADDEL
       STA    COLPM0
       JMP.ind (VECTP1)
;
; --- FRAGMENT: this object is finished.  Pop the next slot off the P0 cursor
;     (which lives in the stack pointer) and latch its Y, or park at DIS250 if
;     all four are done.
DIS201
; ENTRY FROM DIS400, 56 CY WORST
       TSX   ;PNTRP0
       BEQ    DIS202  ;ALL DONE P0
       DEX
       TXS
DIS205
;  ENTRY FROM TOP O SCREEN
       LDA    HVERP0,X
       STA    VERTP0
       LDA    #<DIS400
DIS204
       STA    WSYNC
       STA    ADDEL
       STA    VECTP0
       JMP.ind (VECTP1)
DIS202
       STX    VERTP0  ;VPOS=0
       LDA    #<DIS250
       JMP    DIS204
;
;
;
; --- FRAGMENT: SETUP a P0 object, first line.  Reads HGRAP0/HHITP0 for the
;     slot, latches the collision X, and starts building the three pointers.
DIS400
;  SETUP P0, 1ST LINE
       STA    WSYNC
       STA    ADDEL
       STX    GRAFP1
       DEY
       LDA    (STARS),Y
       STA    GRAFM2
       ASL
       STA    MOON2+1  ;HOLD REG STAR GRAF.
;
       TSX
       LDA    MIPL
       STA    HHITP0+1,X  ;USES MOON2+0
       STA    HITCLR
       LDA    HHITP0,X
       STA    MOON2  ;HOLD
       LDA    HGRAP0,X
       BMI    DIS201  ;NO DISPLAY
       STA    MOON1   ;HOLD REG
       TAX
       SEC
       LDA    MTABL2,X
       SBC    VERTP0
       STA    MOON3
;
       LDX    #$00 
       LDA    #<DIS430
DIS403
       STA    WSYNC
       STA    ADDEL
       STA    VECTP0
       JMP.ind (VECTP1)
;
;
;
; --- FRAGMENT: horizontally position a P0 object.  The delay-loop dance that
;     turns the low nibble of the CRAZY value into a RESP0 strobe.  PLUMBING.
DIS430
; HPOSP0
       STA    WSYNC
       STA    ADDEL
       STX    GRAFP1
       LDA    MOON2  ;HOLD REG
       LDX    #<DIS460
       LSR
       BCS    DIS432  ;DELAY
DIS432
       SEC
       AND    #$07 
       BEQ    DIS433
       STX    VECTP0
       SBC    #$01 
       BEQ    DIS435
       LDX.w  MOON2+1 ;LDX ABS, STAR GRA - original code used DB $AE,MOON2+1,0
DIS431
       STX.w  GRAFM2 ;STX ABS -  original code used DB $8E,GRAFM2,0
       SBC    #$01 
       BNE    DIS431
       STA    HPOSP0
DIS434
       DEY
       STA    WSYNC
       STA    ADDEL
       LDX    MOON2
       JMP.ind (VECTP1)
DIS435
       NOP
DIS433
       STA    HPOSP0
       STX    VECTP0
       LDX    MOON2+1 
       STX    GRAFM2
       JMP    DIS434
;
;
;
; --- FRAGMENT: SETUP a P0 object, second line.  Finishes the three pointers
;     from MTABL1/MTABL3 (graphic), MTABL2 (colour) and MTABL4 (delta), each
;     pre-biased by the object Y, and picks the sprite width from SIZPM0.
DIS460
; SETUP P0, 2ND LINE
       STA    WSYNC
       STA    ADDEL
       STX    GRAFP1
       DEY
       LDA    (STARS),Y
       STA    GRAFM2
;
       LDX    MOON1  ;HOLD REG
       SEC
       LDA    MTABL1,X
       SBC    VERTP0
       STA    MOON1
       LDA    MTABL3,X
       STA    MOON3+1 
       SBC    #$00 
       STA    MOON1+1
       LDA    MTABL4,X
       LDX    #<DIS250   ;X=$0D ,IHOPE !!
       STX    VECTP0
       CMP    #<KDL8-1
       BCS    DIS461
       LDX    #$00 
DIS461
       STX    SIZPM0
       SBC    VERTP0
       STA    MOON2
       LDA    #>NULL
       SBC    #$00 
       STA    WSYNC
       STA    ADDEL
       STA    MOON2+1 
       JMP.ind (VECTP1)
;
;
;
; --- FRAGMENT: draw the shared P1+3 object (Saturn rings / big moon / warp).
;     It is the topmost thing in the P1 chain.
DIS100
;  DISPLAY P1+3
       LDA    (MISC1),Y
       STA    GRAFP1
       LDA    (MISC2),Y
       STA    COLPM1
DIS102
; ENTRY FROM WAIT P1+3, 27CY
       STX    HDELP0
       DEY
       LDA    (STARS),Y
       STA    GRAFM2
       ORA    #SCLR
       STA    COLPF
;
       LDA    (MISC1),Y
       TAX
       BEQ    DIS101  ;ALL DONE
       LDA    (MISC2),Y
       STA    COLPM1
       JMP.ind (VECTP0)
DIS101
       LDA    #<DIS170
       STA    VECTP1
       JMP.ind (VECTP0)
;
;
;
; --- FRAGMENT: WAIT for P1+3.  DIS170 is the variant used when there is no
;     P1+3 object at all, which simply moves straight on to the photons.
DIS150
;  WAIT P1+3
       LDA    #<DIS100
       STA    VECTP1
       LDA    #$00 
       STA    GRAFP1
       CPY    HVERP1+3 
       STA    HDELP1
       BCC    DIS102
       BEQ    DIS901
       LDA    #<DIS150
       JMP    DIS910
;
;
;
; --- FRAGMENT: pre-setup for the photons -- switch the pointers over to the
;     photon graphic page and the ship colour page.  Note the PAGE CROSS
;     warning: VECTP1+1 changes here, so the P1 chain moves to a different
;     page of fragments from this point down.  PLUMBING.
DIS170
; PRESETUP P1+2
       LDA    #$00 
       STA    GRAFP1
;
       LDA    HCOLP1+1 
       STA    COLPM1  ;PHOTON COLOR
       LDA    #>PHOGR1
       STA    MISC1+1
       LDA    #>DIS300
       STA    VECTP1+1   ;PAGE CROSS !!!!!
       LDA    #>YCL1  ;SHIP COLOR
       STA    MISC2+1
       LDA    #<DIS300
       JMP    DIS900
;
;
;
; --- FRAGMENT: shared entry points used by several of the above.  DIS910 is
;     the wait loop and DIS912 its test against BOTSCN; when Y reaches BOTSCN
;     the picture is finished and control leaves for bank 4.
DIS902
; ENTRY FROM PHOTON SETUP
       STA    HDELP1
       AND    #$0F 
       STA    HOLDP1
       LDA    #<DIS330
DIS900
;  MISC ENTRY
       DEY
       STX    HDELP0
       STA    VECTP1
DIS903
       LDA    (STARS),Y
       STA    GRAFM2
       ORA    #SCLR
       STA    COLPF
       LDX    #$00 
       JMP.ind (VECTP0)
;
DIS910
; WAIT ENTRY
       STA    CHTBLK 
DIS901
       DEY
DIS912
       CPY    BOTSCN 
       STX    HDELP0
       BNE    DIS903
; SCREEN DONE
       JMP    EXIT9   ;TO BANK 4
;
;
;
; SATKRN -- the Saturn kernel fragment.  Drawn only on a planet approach, above
; everything else, then it hands control to the normal P1 chain at DIS170.
; GAMEST bit 6 (your own planet) picks the friendly colour scheme.
SATKRN
; SATURN KERNAL
       LDX    #$00 
       STX    GRAFP1
       DEY
       CPY    #$8D   ;HVERP1+3
       BCC    SATK20
       STX    HDELP1
       JMP    DIS912
SATK20
; SETUP
       LDA    #<DIS170
       STA    VECTP1
       LDA    #$25 
       STA    SIZPM1
       STA    HPOSM0
       STA    HPOSP0
       STX    HDELP0
       LDA    #$F0 
       STA    HDELM0
       LDX    #$96 
       LDA    #$82 
       BIT    GAMEST 
       BVS    SATKR9
       LDX    #$26 
       LDA    #$22 
SATKR9
       STX    COLPM0
       STA    COLPM1
       LDX    #$20 
       JMP    SATKR1
;
;
;   GRAPHICS TABLES
;
;
;  STAR TABLE AND DELTAS
 ORG $22CF
 RORG BANK2+$2CF   ;TEMPORARY *********
SHPTB4 .byte $70,$00,$50
; SHARE 1
JOYTB7 .byte $00,<(STARTB+1)
;
;-------------------------------------------------------------------------------
; THE DELTA TABLES.  Each of these is a per-scanline horizontal nudge stream
; for one object shape, read through MTABL4.  They are what turns a single
; 8-pixel player into a wide object:
;
;   SATAB2         Saturn rings
;   NULL           16 zero bytes -- the "no delta" stream used by flat objects
;   RDL1           the rings variant
;   KDL8..KDL5     planet killer, four sizes
;   XDL8..XDL4     explosions, five sizes
;   CDLF..CDLA     craters, four sizes
;   STARTB         the STARFIELD bit pattern, which deliberately overlaps XDL4
;                  so the same bytes serve both purposes
;
; Python: read a delta stream as a shape outline -- entry n is how far row n is
; offset from row n-1.  Accumulate them to get a per-row X offset.
;-------------------------------------------------------------------------------
SATAB2 
; HDEL,SIZE,ETC
       .byte $00,$00,$E0,$E0,$F0,$02,$F2,$F2
       .byte $D7,$22,$F2,$F2,$92,$F2,$02,$02
       .byte $00,$F0,$00,$F0,$F0,$00,$F0,$00
       .byte $F0,$00,$00,$F0
;
; ORG BANK2+$2F0   ;TEMPOARY ********** (sic)
; NO DELTA
       .byte $00,$00,$00,$00,$00,$00,$00,$00
       .byte $00,$00,$00,$00,$00,$00,$00,$00
NULL
;
;   RINGS DELTA
       .byte $08,$09,$04,$06,$F4,$F9,$F8,$B8,$00,$02,$00,$09,$0C,$0E,$0C,$09
RDL1
; PLANET KILLER DELTA
       .byte $08,$18,$08,$08,$00,$F2,$00,$1D,$0E,$0C,$09,$FC
KDL8   .byte $0E,$1C,$F9,$08,$08,$08,$08,$0C,$0E,$0C,$15,$F6
KDL7   .byte $04,$11,$02,$00,$FD,$0E,$1C,$09,$08,$F8
KDL6   .byte $08,$18,$F8,$0E,$0C,$09,$08,$08,$18,$F8
KDL5
; EXPLOSION DELTA
       .byte $18,$D8,$48,$F8,$B8,$58,$98,$38
       .byte $68,$98,$C8,$58,$78,$98,$A8,$7A
       .byte $78,$A9,$98,$48,$18,$44,$A6,$34
       .byte $09,$08,$48
XDL8
       .byte $08,$0A,$08,$F1,$12,$D0,$29,$30
       .byte $A2,$30,$49,$CC,$CE,$7C,$E9,$CA
       .byte $18,$39,$18,$D8,$38,$08,$F8
XDL7
       .byte $0A,$18,$09,$F8,$E8,$28,$08,$F8
       .byte $08,$28,$B0,$42,$E0,$29,$1A,$F8
       .byte $09,$08,$10
XDL6
       .byte $02,$00,$19,$F8,$04,$16,$04,$09
       .byte $F4,$16,$04,$FD,$0E,$1C,$F9
XDL5
       .byte $08,$F8,$18,$F8,$18,$FA,$08,$19
;
STARTB
;
       .byte $F8,$0A,$08
XDL4
; CIRCLE DELTAS

       .byte $09,$04,$F6,$14,$09,$18,$08,$00
       .byte $F2,$00,$09,$0C,$0E,$0C,$09,$08
       .byte $18,$08,$08,$F0,$02,$F0,$1D,$0E
CDLF
       .byte $0C,$09,$1C,$FE,$0C,$19,$08,$08
       .byte $F8,$08,$0C,$0E,$0C,$05,$16,$04
       .byte $01,$F2,$00,$1D,$FE,$0C
CDLE
       .byte $09,$18,$F8,$18,$08,$0C,$FE,$0C
       .byte $09,$08,$08,$08,$18,$08,$08,$F8
       .byte $18,$F8
CDLC
       .byte $08,$18,$F8,$08,$18,$08,$08,$08
       .byte $08,$08,$FA,$08,$19,$F8
CDLA
;
;
; SPDVOL / SPDVL1 -- throttle (IQWARP) -> engine volume, for the two audio
; channels.  Indexed as SPDVOL-$D8,Y so the table starts at IQWARP = $D8.
SPDVOL
       .byte $D8,$D8,$D4,$D6,$D4,$C9,$B8
       .byte $A8,$98,$8A,$78,$61,$52,$40,$49
       .byte $30,$72,$60,$59,$4C,$3E,$3C,$29
       .byte $1A,$18,$19,$18,$18,$18,$18,$08
       .byte $0A,$08,$09,$08,$08,$08,$08,$08
       .byte $08
SPDVL1
       .byte $F8,$F0,$F2,$F0,$F9,$FA,$F8
       .byte $F9,$F8,$D0,$B2,$90,$79,$58,$34
       .byte $36,$34,$39,$34,$26,$24,$2D,$2E
       .byte $2C,$29,$28,$18,$18,$18,$18,$1A
       .byte $18,$19
;
;  END STAR TABLE
;
;  SHARE 7
;
; PHOTB3 -- minimum vertical spacing between your two photons, per zoom step.
; PHOTB1 -- your photon graphics, one block per zoom step.
PHOTB3 .byte $07,$07,$07,$07,$0B,$0A,$09,$08,$07
;
PHOTB1 
       .byte <PHOGR1+U,<PHOGR2+U,<PHOGR3+U,<PHOGR4+U
       .byte <PHOGR5+U,<PHOGR6+U,<PHOGR7+U,<PHOGR8+U
       .byte <BLANK+U
;
;
;
; PLANET KILLER
       .byte $00,$00,$08,$18,$3C,$7E,$FF,$08,$08,$FF,$7E,$3C,$18,$08
KGR8   .byte $00,$00,$08,$18,$1C,$3E,$7F,$08,$08,$7F,$3E,$1C,$18,$08
KGR7   .byte $00,$00,$08,$18,$3C,$7E,$08,$08,$7E,$3C,$18,$08
KGR6   .byte $00,$00,$08,$18,$1C,$3E,$08,$08,$3E,$1C,$18,$08
KGR5   .byte $00,$00,$18,$3C,$FF,$18,$FF,$3C,$18
KGR4   .byte $00,$00,$18,$7E,$18,$7E,$18
KGR3
       .byte $00,$00,$18
KGR1
       .byte $3C,$18
KGR2
;  RINGS
       .byte $00,$00,$0F,$3F,$FE,$F3,$E3,$C1
       .byte $0C,$18,$30,$30,$60,$7C,$F8,$E0
RGR8   .byte $00,$00,$0F,$3F,$7F,$73,$71,$06,$06,$0C,$18,$18,$3C,$38
RGR7   .byte $00,$00,$7C,$FE,$E6,$C2,$0C,$18,$18,$3C,$38
RGR6   .byte $00,$00,$3C,$7E,$76,$62,$06,$04,$0F,$0C
RGR5   .byte $00,$00,$0F,$1F,$12,$60,$40,$E0,$C0
RGR4   .byte $00,$00,$0E,$1E,$30,$20,$60,$60
RGR3   .byte $00,$00,$0C,$18,$38,$20
RGR2   .byte $00,$00,$08,$10,$20
RGR1
;
;  RING COL
CR
       .byte $68,$68,$68,$66,$66,$66,$66,$66
       .byte $66,$68,$68,$68,$68,$68
;
;  PLANET KILLER COL
CK
       .byte $00,$A4,$A6,$A8,$AA,$AC,$AE,$AE,$AC,$AA,$A8,$A6,$A4
;
;
;
; LINTB3 -- your ship graphic pointer, indexed by the takeoff animation step.
; LINTB5 (further down) is the matching colour pointer.
LINTB3
       .byte <SHP4+1,<SHP3+1,<SHP3+1,<SHP2+1
       .byte <SHP2+1,<SHP1+1,<SHP1+1,<SHP1+1
;
;
 ORG $2500
 RORG BANK2+$500    ;TEMPOARY ********** (sic)
;
; FIGHTER
       .byte $00,$00,$24,$66,$C3,$99,$99,$FF,$7E,$3C,$7E,$CF,$7E,$48
;
;-------------------------------------------------------------------------------
; THE SPACE SPRITE DATA.
;
; REMINDER on the storage convention (header section 7b): each block is stored
; BOTTOM ROW FIRST, so the byte at LABEL-1 is the TOP row and the two $00 bytes
; at the START of the block are the terminator the kernel tests for.  Walk
; BACKWARDS from LABEL-1 to extract a sprite top-to-bottom.
;
; The naming is <letter><GR><size>, where size 8 is nearest and 1 is furthest:
;   FGR*  Fighter          PGR*  Pirate           DGR*  Darter
;   HGR*  Hyperjumper      KGR*  Planet killer    BGR*  Blockader
;   EGR*  Enemy photon     XGR*  eXplosion        RGR*  Saturn rings
;   CGR*  Crater / moon    YGR1..3  YOUR SHIP (level, bank right, bank left)
;
; The matching colour ramps use CL instead of GR: YCL1 (your ship), CC1/CC2/CC4
; (moons and craters), and the CF/CP/CD/CK/CB/CE/CX/CR block indexed by MTABL2.
; A colour ramp is one TIA colour byte per scanline, so an object is shaded
; top-to-bottom by walking the ramp alongside the graphic.
;-------------------------------------------------------------------------------
FGR8
       .byte $00,$00,$3C,$7E,$DB,$99,$FF,$7E,$3C,$7E,$C3,$7E,$24
FGR7
       .byte $00,$00,$18,$3C,$7E,$FF,$7E,$3C,$7E,$F3,$7E,$12
FGR6
       .byte $00,$00,$24,$66,$42,$42,$7E,$3C,$6E,$3C,$28
FGR5   .byte $00,$00,$18,$3C,$7E,$3C,$76,$3C,$14
FGR4   .byte $00,$00,$28,$6C,$44,$7C,$38,$7C,$28
FGR3   .byte $00,$00,$10,$38,$38,$28
FGR2   .byte $00,$00,$10,$10
FGR1
; PIRATES
       .byte $00,$00,$C3,$81,$81,$A5,$FF,$BD,$99,$81,$C3
PGR8   .byte $00,$00,$63,$41,$55,$7F,$5D,$49,$63
PGR7   .byte $00,$00,$66,$42,$5A,$7E,$5A,$42,$66
PGR6   .byte $00,$00,$36,$22,$3E,$22,$36
PGR5   .byte $00,$00,$24,$3C,$3C,$24
PGR4   .byte $00,$00,$14,$14,$14
PGR3   .byte $00,$00,$18,$18
PGR2
       .byte $00,$00,$08
PGR1
;
;ORG BANK2+$584     ;TEMPOARY ********** (sic)
;  P1 PHOTONS
       .byte $00,$00,$10,$38,$7C,$7C,$7C,$38,$10
PHOGR1
       .byte $00,$00,$10,$38,$7C,$7C,$38,$10
PHOGR2
       .byte $00,$00,$18
PHOGR7
       .byte $3C,$3C,$3C,$18
PHOGR3
PHOGR4
       .byte $00,$00,$10,$38,$38,$10
PHOGR5
       .byte $00,$00
BLANK
       .byte $10
PHOGR8
       .byte $38,$10
PHOGR6
;
; FIGHTER COL
CF
       .byte $54,$56,$58,$5A,$5C,$58,$58,$5E,$5C,$5A,$58,$5E,$5E
;  PIRATE COL
CP
       .byte $1E,$1E,$18,$16,$14,$16,$18,$1E,$1E
       .byte $1A,$12,$12,$1A
;
;
;ORG BANK2+$5C1  ;TEMPOARY ********** (sic)
;  YOUR SHIP GRAPHIC
; NORMAL
       .byte $00,$00,$08,$0C,$0E,$1E,$0C,$04
       .byte $00,$04,$00,$F1,$7F,$3F,$1F,$1F
       .byte $0E,$0E,$04,$04
YGR1
; BANK RIGHT
       .byte $00,$00,$20,$30,$38,$78,$30,$10
       .byte $00,$1B,$00,$6F,$FE,$FC,$FC,$78
       .byte $38,$30,$10,$10
YGR2
; BANK LEFT
       .byte $00,$00,$10,$18,$1C,$3C,$18,$08
       .byte $00,$D8,$00,$E4,$7F,$3F,$3F,$1E
       .byte $1C,$0C,$08,$08
YGR3
;
;
 ORG $2600
 RORG BANK2+$600   
;
; BLOCKADER
       .byte $00,$00,$18,$3C,$81,$CB,$FF,$CB,$81,$3C,$18
BGR8
       .byte $00,$00,$18,$18,$20,$30,$38,$30,$20,$18,$18
BGR7
       .byte $00,$00,$18,$18,$04,$0C,$1C,$0C,$04,$18,$18
BGR6
       .byte $00,$00,$18,$40,$60,$70,$60,$40,$18
BGR5
       .byte $00,$00,$18,$02,$0E,$0E,$0E,$02,$18
BGR4
       .byte $00,$00,$10,$44,$7C,$44,$10
BGR3
       .byte $00,$00,$10
BGR1
       .byte $28,$10
BGR2
;
; JUMP GRAPHIC
       .byte $00,$00,$0C,$60,$06,$18,$C3,$0C,$60,$18
DGR8
; DARTER
       .byte $00,$00,$08,$1C,$3E,$1C,$08
DGR3   .byte $00,$00,$08,$1C,$08,$04
DGR2   .byte $00,$00,$0C,$08,$04
DGR1
; ENEMY BULLETS
       .byte $00,$00,$08,$08,$1C,$3E,$1C,$08,$08
EGR6    byte $00,$00,$36,$1C,$08,$1C,$36,$04
EGR5   .byte $00,$00,$08,$08,$1C,$08,$08
EGR4   .byte $00,$00,$14,$08,$14,$04
EGR3   .byte $00,$00,$08,$1C,$08
EGR2   .byte $00,$00,$08,$04
EGR1
;
       .byte $00,$00,$00,$00,$00,$00,$00,$00,$00,$00,$00,$00,$00,$00,$00,$00
       .byte $00,$00,$00,$00,$00,$00
;
;  ENEMY PHODON COLOR
CE
       .byte $9E,$8E,$7E,$6E,$7E,$8E,$9E,$00
;  DARTER COL
CD
       .byte $44,$48,$48,$00,$00,$42,$44,$48,$48,$46
       .byte $46,$48,$8A,$8C,$8C,$8E,$8E,$8A
; BLOCKADER COL
CB
       .byte $88,$CA,$C6,$CA,$88,$86,$CE,$CC
       .byte $CA,$CC,$CE,$86,$88
;
;
;
;       .byte $FF,$FF,$FF,$FF,$FF,$FF,$FF
 ORG $26C6
 RORG BANK2+$6C6   ;TEMPOARY ********** (sic)
; YOUR SHIP COLORS
       .byte $00,$00,$00
       .byte $00,$00,$00,$6D,$6B,$79,$76,$84
       .byte $84,$92,$A2,$A0
YCL1
       .byte $00,$00,$00,$00,$00,$00,$00,$00
       .byte $00,$00,$00,$6C,$6A,$79,$76,$84
       .byte $84,$92,$A2,$A0
;
       .byte $00,$00,$00,$00,$00,$00,$00,$00
       .byte $00,$00,$00,$6C,$6A,$79,$76,$84
       .byte $84,$92,$A2,$A0
;
;
 ORG $2700
 RORG BANK2+$700  ; TEMPOARY ********** (sic)
;
; HYPERJUMPER
       .byte $00,$00,$5A,$7E,$3C,$FF,$99,$99,$BD,$FF,$7E,$3C
HGR8
HGR7
HGR6
       .byte $00,$00,$24,$3C,$7E,$5A,$5A,$7E,$3C,$18
HGR5
HGR4
       .byte $00,$00,$28,$3C,$6C,$54,$7C,$38
HGR3
       .byte $00,$00,$10,$38,$38
HGR2
       .byte $00,$00,$10
HGR1
; EXPLOSION
       .byte $00,$00,$20,$08,$80,$20,$02,$20,$08,$84
       .byte $40,$01,$81,$81,$20,$04,$11,$40
       .byte $84,$02,$01,$02,$20,$04,$01,$80
       .byte $02,$40,$04,$40
XGR8
       .byte $00,$00,$08,$20,$82,$08,$20,$04,$08,$80
       .byte $15,$89,$80,$24,$50,$A0,$45,$40
       .byte $02,$48,$02,$49,$80,$A0,$02,$28
XGR7
       .byte $00,$00,$28,$10,$80,$04,$40,$84,$10,$05
       .byte $40,$84,$22,$80,$41,$84,$A0,$04
       .byte $08,$A0,$02,$50
XGR6
       .byte $00,$00,$14,$08,$20,$12,$44,$20,$12,$89
       .byte $04,$20,$08,$90,$02,$21,$08,$14
XGR5
       .byte $00,$00,$14,$28,$02,$44,$08,$2A,$54,$02
       .byte $48,$10,$24,$08
XGR4
       .byte $00,$00,$22,$7F,$7F,$7F,$FE,$FF,$FF,$7F,$3E,$38
XGR3
       .byte $00,$00,$30,$7C,$7C,$7C,$3C,$38
XGR2
       .byte $00,$00,$10,$38,$38,$10
XGR1
;
; HYPERJUMPER COL
CHCOL
       .byte $84,$84,$84,$88,$8A,$8E,$8C,$8A,$88,$86
       .byte $48,$4C,$48,$46,$42,$42,$42,$C4,$C6,$CA
       .byte $C8,$C6,$C6,$C4,$84,$84,$84,$44,$44,$48
       .byte $46,$44,$44,$42
;
;  EXPLOS COLOR
CX
       .byte $8E,$8E,$8E,$AA,$8E,$AA,$AA,$8E
       .byte $8E,$8E,$AA,$AA,$8E,$8E,$AA,$8E
       .byte $8E,$AA,$AA,$8E,$AA,$8E,$8E,$AA
       .byte $AA,$8E,$8E,$8E
       .byte $1E,$1E,$1E,$1E,$1E,$1E,$1E,$1E
       .byte $1E,$1E
;
;
SHPTB5
       .byte $08,$14,$1C,$0E,$2C
;
LINTB5 .byte $F5,$F5,$F5,$F4
       .byte $F4,$F2,$F2,$F2
;
;
;  APPROX. E800  ******
;
;   CIRCLES
       .byte $00,$00,$3C,$7E,$7E,$FF,$FF,$FF,$FF,$FF,$7E,$7E,$3C
CGR8   .byte $00,$00,$1C,$3E,$3E,$7F,$7F,$7F,$7F,$3E,$3E,$1C
CGR7   .byte $00,$00,$3C,$7E,$7E,$7E,$7E,$7E,$3C
CGR6   .byte $00,$00,$1C,$3E,$3E,$3E,$3E,$1C
CGR5   .byte $00,$00,$18,$3C,$3C,$3C,$18
CGR4   .byte $00,$00,$08,$1C,$1C,$08
CGR3   .byte $00,$00,$18,$18
CGR2   .byte $00,$00,$08
CGR1
       .byte $00
       .byte $00,$00,$18,$3C,$3E,$7E,$7E,$FE,$FE,$FE
       .byte $FF,$FF,$FF,$FF,$FF,$FF,$FF,$FF
       .byte $FE,$FE,$FE,$7E,$7E,$3E,$3C,$18
CGRF
       .byte $00,$00,$00
;
       .byte $00,$00,$08,$1C,$3C,$3E,$3E,$7E,$7E,$7E
       .byte $7F,$7F,$7F,$7F,$7F,$7F,$7E,$7E
       .byte $7E,$3E,$3E,$3C,$1C,$08
CGRE
       .byte $00,$00,$18,$38,$3C,$7C,$7C,$7C,$7E,$7E
       .byte $7E,$7E,$7E,$7E,$7C,$7C,$7C,$3C
       .byte $38,$18
CGRC
       .byte $00,$00,$18,$38,$3C,$3C,$7C,$7C,$7C,$7C
       .byte $7C,$7C,$3C,$3C,$38,$18
CGRA
;
; CIRCLE COLOR
CC2
       .byte $42,$44,$46,$48,$46,$44,$44,$46
       .byte $48,$46,$48,$48,$46,$46,$46,$48
       .byte $48,$46,$44,$42,$40,$42,$44,$44
CC1
       .byte $82,$82,$82,$82,$84,$84,$86,$86
       .byte $88,$88,$8A,$8A,$8C,$8C,$8E,$8E
       .byte $8E,$8C,$8A,$88,$86,$84,$82,$80
CC4
       .byte $A2,$A2,$A2,$A2,$A2,$A2,$A2,$A2
       .byte $A2,$A2,$A2,$A2
;
;
;
;
SATKR2
       LDA    (STARS),Y
       STA    GRAFM2
       ORA    #SCLR
       STA    COLPF
       LDA    XDL4-3,X  ;MOON
       STA    HDELP1
SATKR1
       STA    WSYNC
       STA    ADDEL
       LDA    SATAB1-1,X 
       STA    GRAFP0
       LDA    CGR1-1,X   ;MOON
       STA    GRAFP1
       LDA    SATAB2-1,X
       STA    GRAFM0
       STA    HDELP0
       AND    #$05 
       ORA    #$10 
       STA    SIZPM0
       DEY
       DEX
       BNE    SATKR2
       BIT    SHIPST 
       BPL    SATKR3
       STY    COLPM1    ;SHIP COLOUR
       LDA    #>DIS700    ;SHIP GO!
       STA    VECTP1+1 
       LDA    #<DIS700
       STA    VECTP1
SATKR3
       LDA    #$20 
       STA    SIZPM1
       JMP.ind (VECTP0)
;
;
;
;
;-------------------------------------------------------------------------------
; MTABL1..MTABL4 -- THE MASTER SPRITE INDEX.  All four are indexed by the
; object TYPE BYTE (HGRAP0-1,X), so together they are the whole sprite
; database:
;
;   MTABL1[type]  low byte of the GRAPHIC pointer
;   MTABL3[type]  high byte of the same (written with Z EQM so each row of the
;                 table names the sprite family it belongs to)
;   MTABL2[type]  the COLOUR RAMP pointer, one colour byte per scanline
;   MTABL4[type]  the HMOVE DELTA stream pointer, or 0 for a flat 8-pixel
;                 object
;
; The kernel subtracts the object screen Y from each pointer before use, so
; (ptr),Y lands on the right row without any per-row arithmetic.
;
; THIS IS THE TABLE TO PORT FIRST.  Walking it gives you, for every one of the
; ~128 type bytes, a sprite bitmap, a colour ramp and a width profile.
;-------------------------------------------------------------------------------
MTABL1

       .byte <FGR8+U,<FGR7+U,<FGR6+U,<FGR5+U,<FGR4+U,<FGR3+U,<FGR2+U,<FGR1+U
       .byte <PGR8+U,<PGR7+U,<PGR6+U,<PGR5+U,<PGR4+U,<PGR3+U,<PGR2+U,<PGR1+U
       .byte <DGR8+U,0,0,0,<DGR3+U,<DGR2+U,<DGR2+U,<DGR1+U
       .byte <HGR8+U,<HGR7+U,<HGR6+U,<HGR5+U,<HGR4+U,<HGR3+U,<HGR2+U,<HGR1+U
       .byte <KGR8+U,<KGR7+U,<KGR6+U,<KGR5+U,<KGR4+U,<KGR3+U,<KGR2+U,<KGR1+U
       .byte <BGR8+U,<BGR7+U,<BGR6+U,<BGR5+U,<BGR4+U,<BGR3+U,<BGR2+U,<BGR1+U
       .byte <EGR6+U,<EGR5+U,<EGR6+U,<EGR5+U,<EGR4+U,<EGR3+U,<EGR2+U,<EGR1+U
       .byte <XGR8+U,<XGR7+U,<XGR6+U,<XGR5+U,<XGR4+U,<XGR3+U,<XGR2+U,<XGR1+U
       .byte <RGR8+U,<RGR7+U,<RGR6+U,<RGR5+U,<RGR4+U,<RGR3+U,<RGR2+U,<RGR1+U
       .byte <CGRF+U,<CGRE+U,<CGRC+U,<CGRA+U,<CGR8+U,<CGR7+U,<CGR6+U,<CGR5+U
       .byte <CGR4+U,<CGR3+U,<CGR2+U,<CGR1+U
       .byte <CGRF+U,<CGRE+U,<CGRC+U,<CGRA+U,<CGR8+U,<CGR7+U,<CGR6+U,<CGR5+U
       .byte <CGR4+U,<CGR3+U,<CGR2+U,<CGR1+U
;
MTABL2
;  COLORS
; FIGHTER
Z EQM <CF
       .byte Z+$D,Z+$D,Z+$D,Z+$E,Z+$E,Z+$D,Z+$8,Z+$E
; PIRATE
Z EQM <CP
       .byte Z+$A,Z+$9,Z+$9,Z+$8,Z+$E,Z+$7,Z+$7,Z+$A
; DARTER
Z EQM <CD
       .byte Z+$13,0,0,0,Z+$B,Z+$5,Z+$5,Z+$6
; HJUMPER
Z EQM <CHCOL
       .byte Z+$B,Z+$19,Z+$23,Z+$A,Z+$18,Z+$F,Z+$C,Z+$7
; PKILLER
Z EQM <CK
       .byte Z+$E,Z+$E,Z+$D,Z+$D,Z+$C,Z+$B,Z+$A,Z+$9
; BLOCKADER
Z EQM <CB
       .byte Z+$E,Z+$E,Z+$E,Z+$D,Z+$D,Z+$6,Z+$5,Z+$E
; ENEMY PHOTON
Z EQM <CE
       .byte 0,0,Z+$8,Z+$9,Z+$8,Z+$9,Z+$8,Z+$9
; EXPLOSION
Z EQM <CX
       .byte Z+$1D,Z+$1B,Z+$19,Z+$17,Z+$1D,Z+$27,Z+$27,Z+$27
; RINGS
Z EQM <CR
       .byte Z+$0F,Z+$0F,Z+$0F,Z+$0F,Z+$0F,Z+$0F,Z+$0F,Z+$0F
;  MOON1 COLOR
Z EQM <CC1
       .byte Z+$19,Z+$18,Z+$16,Z+$14,Z+$14,Z+$11,Z+$10,Z+$0F
       .byte Z+$0D,Z+$0D,Z+$0D,Z+$0D
;  MOON2 COLOR
Z EQM <CC2
       .byte Z+$19,Z+$18,Z+$16,Z+$14,Z+$14,Z+$11,Z+$10,Z+$0F
       .byte Z+$0D,Z+$0D,Z+$0D,Z+$0D
;
;
;
;
;-------------------------------------------------------------------------------
; DISPLY -- entry to the space kernel from vertical blank.
;
; Sets up the shared state the fragments rely on, then starts the two chains:
;   * the starfield pointer and its X position
;   * the shared P1+3 object graphic and colour pointers, pre-biased by its Y
;     (with a special case: types $48 and up are big moons, which use a fixed
;     moon colour instead of their own ramp)
;   * PNTRP1 / the stack pointer as the two chain cursors
;   * Y = TOPSCN, i.e. start at the top of the picture
; and jumps into the P0 chain at DIS205.
;-------------------------------------------------------------------------------
DISPLY
;  ENTRY FROM VBLANK
       CLC
       SBC    STARS   ;A=0 -- CROSP1 = a star mask derived from the star pointer
       STA    CROSP1
       LDA    #$20   ;M=X4
       STA    SIZPM1
       LDA    #$80 
       STA    HDELM2
       LDA    RANDOM+1 
       STA    HDELM1
       LDA    #>DIS205
       STA    VECTP0+1  ;high byte of the P0 chain fragment page
       STA    RANDOM+1 
       LDA    STARS+1
       STA    HDELP1
       STA    WSYNC
       STA    ADDEL
       AND    #$0F 
       LDX    #>STARTB  ;the starfield pattern page
       STX    STARS+1
       LDX    #>DIS150
       STX    VECTP1+1  ;high byte of the P1 chain fragment page
       LSR
       BCS    DISPL2  ;DELAY
DISPL2
       BEQ    DISPL9
DISPL1
       SEC
       NOP
       SBC    #$01 
       BNE    DISPL1
       NOP
DISPL9
       STA    HPOSP1
;  2 SPARE CY
       STA    WSYNC
       STA    ADDEL
       LDX    HGRAP1+3  ;the shared P1+3 object type
       LDA    MTABL2,X  ;MTABL2 = its colour ramp pointer
       CPX    #$48  ;types $48 and up are the big moons...
       BCC    DISPL7
       LDA    #<CC4+$0D  ;MOON COLOR -- ...which use one fixed colour instead of a ramp
DISPL7
       SEC
       SBC    HVERP1+3  ;pre-bias the colour pointer by the object screen Y
       STA    MISC2
; C=1  I HOPE
       LDA    MTABL1,X  ;MTABL1 = its graphic pointer, pre-biased the same way
       SBC    HVERP1+3
       STA    MISC1
       LDA    MTABL3,X  ;MTABL3 = the high byte of that graphic pointer
       STA    MISC2+1 
       SBC    #$00 
       STA    MISC1+1
       LDX    PNTRP1 
       TXS   ;PNTRP0 -- the P0 chain cursor lives in the stack pointer
       LDA    #<DIS350
       STA    PNTRP1  ;the P1 chain starts with the far photon at DIS350
       LDY    #TOPSCN  ;start at the top of the picture and count Y downward
       JMP    DIS205
;
;
;
MTABL3
;  MOON1+1
Z EQM >FGR8
       .byte Z,Z,Z,Z,Z,Z,Z,Z
Z EQM >PGR8
       .byte Z,Z,Z,Z,Z,Z,Z,Z
Z EQM >DGR8
       .byte Z,0,0,0,Z,Z,Z,Z
Z EQM >HGR8
       .byte Z,Z,Z,Z,Z,Z,Z,Z
Z EQM >KGR8
       .byte Z,Z,Z,Z,Z,Z,Z,Z
Z EQM >BGR8
       .byte Z,Z,Z,Z,Z,Z,Z,Z
Z EQM >EGR6
       .byte 0,0,Z,Z,Z,Z,Z,Z
Z EQM >XGR8
       .byte Z,Z,Z,Z,Z,Z,Z,Z
Z EQM >RGR8
       .byte Z,Z,Z,Z,Z,Z,Z,Z
Z EQM >CGRF
       .byte Z,Z,Z,Z,Z,Z,Z,Z
       .byte Z,Z,Z,Z
       .byte Z,Z,Z,Z,Z,Z,Z,Z
       .byte Z,Z,Z,Z
;
;
;
;
MTABL4
; MOON2+0, HDEL
       .byte $00,$00,$00,$00,$00,$00,$00,$00
       .byte $00,$00,$00,$00,$00,$00,$00,$00
       .byte $00,$00,$00,$00,$00,$00,$00,$00
       .byte $00,$00,$00,$00,$00,$00,$00,$00
       .byte <KDL8+U,<KDL7+U,<KDL6+U,<KDL5+U,0,0,0,0
       .byte $00,$00,$00,$00,$00,$00,$00,$00
       .byte $00,$00,$00,$00,$00,$00,$00,$00
       .byte <XDL8+U,<XDL7+U,<XDL6+U,<XDL5+U,XDL4+U,0,0,0
       .byte <RDL1+U,<RDL1-1+U,<RDL1-3+U,<RDL1-4+U,0,0,0,0
       .byte <CDLF+U,<CDLE+U,<CDLC+U,<CDLA+U,0,0,0,0
       .byte $00,$00,$00,$00
       .byte <CDLF+U,<CDLE+U,<CDLC+U,<CDLA+U,0,0,0,0
       .byte $00,$00,$00,$00
;
;
;
;
;
;    END KERNALS BANK 2
;
;
;   SUBROUTINES
;
;
;
;
;===============================================================================
; J O Y S T K  --  READ THE STICK, STEER THE SHIP, SET THE THROTTLE
;
; Runs once per frame in overscan.  Three jobs:
;
; 1. THROTTLE (the speed block).  Held up/down changes IQWARP by one notch per
;    8 frames.  Special cases:
;      * pushing up past $D9 with SHIPST bit 5 set COMMITS A HYPERWARP: PROGST
;        bit 4 goes on, the two photons are repurposed as tunnel stars, and the
;        takeoff sound starts.
;      * SHIPST bit 4 instead means a planet takeoff.
;      * on a surface the throttle is clamped by JOYT13.
; 2. VERTICAL.  Scrolls the starfield (HHORM2 and the STARS pointer) and sets
;    JOYRMV, the amount every object drifts vertically this frame because YOU
;    moved.  BRAIN adds JOYRMV into each object dy.
; 3. HORIZONTAL.  VELOC is your signed lateral speed, clamped to $E0..$1F; it
;    accumulates into HPOSL (a sub-pixel accumulator) and then into CENTER,
;    the camera position, which is clamped to $2D..$74.  When the camera hits a
;    clamp the starfield scrolls instead, which is what makes the world feel
;    wider than the camera range.  THGRP1 records which way you are banking so
;    SHPSRV can pick the banked ship graphic, and JOYRMH is the horizontal twin
;    of JOYRMV.
;
; PORTA is active low, so $FF means the stick is centred.  In the NEGATIVE
; UNIVERSE (MAZSTA bit 7) the EOR #$FF is skipped, which inverts every control.
;===============================================================================
JOYSTK
       LDX    #$00 
       STX    JOYRMH
       STX    JOYRMV
       LDA    PORTA  ;PORTA = the joystick directions, active low
       CMP    #$FF  ;$FF means the stick is centred
       BEQ    JOYS68
       STX    ATRACT+1  ;any input resets the attract timer...
       LSR    PROGST  ;...and clears PROGST bit 0, the screen-protect flag
       ASL    PROGST 
JOYS68
       BIT    MAZSTA  ;NEGATIVE UNIVERSE: skip the inversion, so every control reverses
       BMI    JOYS35   ;NEGATIVE UNIVERSE
       EOR    #$FF 
JOYS35
       STA    TEMP12  ;TEMP12 keeps the raw direction bits for the horizontal section
       LSR
       LSR
       LSR
       LSR
       AND    #$03 
       TAY  ;Y = the two VERTICAL bits, 0..3
       LDA    PROGST 
       AND    #$B3  ;no throttle changes on the chart, in hyperwarp, or when dead
       BNE    JOYS49
       LDA    ATRACT 
       AND    #$07  ;the throttle only changes one notch every 8 frames
       BNE    JOYS77
;  SPEED STUFF
       LDX    IQWARP  ;IQWARP is signed; positive means we are not under thrust
       BPL    JOYS31
       LDA    SHIPST 
       AND    #$30  ;SHIPST bits 4 and 5 = a takeoff or hyperwarp is armed
       BEQ    JOYS40
       CPX    #$E0 
       BCS    JOYS31
       AND    #$10  ;bit 4 = a planet takeoff, which skips the tunnel setup
       BNE    JOYS41
       CPX    #$D9 
       BCS    JOYS31
       LDA    #$10  ;HWARP
       STA    PROGST  ;COMMIT THE HYPERWARP: PROGST bit 4
       LDA    #$28 
       STA    ZDELP0+1  ;the two photons are repurposed as the tunnel stars...
       LDA    #$30 
       STA    ZDELP0 
       LDA    #$4B 
       STA    YDELP0 
       LDA    #$49 
       STA    YDELP0+1  ;...with fixed speeds so they streak past you
       LDA    #AUDTAK-J
       STA    CH0PTR  ;the takeoff sound on both channels
JOYS41
       LDA    #AUDTAK-J
       STA    CH1PTR 
       LDA    #$05 
       STA    IQWARP   ;?? -- throttle resets for the jump
       LDA    #$00 
       STA    HCOLP1+1  ;SHIP TAKEOFF Z -- HCOLP1+1 becomes the takeoff animation clock
       LDA    #$80 
       ORA    SHIPST   ;SAVE TYPE OF TAKEOFF
       STA    SHIPST   ;SHIP TAKEOFF -- SHIPST bit 7 = the takeoff animation is now running
JOYS49
       RTS

JOYS40
       CPX    #$F1 
       BCC    JOYS32
       LDA    GAMEST   ;JOYSTK SPEED DELTA -- GAMEST bits 2..4 hold the per-level throttle step
       AND    #$1C 
       LSR
       LSR
       ADC    IQWARP   ;C=0
       BCS    JOYS31
       TAX
       CPX    #$F4 
       BCC    JOYS32
       CPX    #$FC 
       BCS    JOYS32
       BIT    PROGST  ;V = surface mode
       BVC    JOYS34
;  PLANET/TRENCH
       LDA    JOYT13,Y  ;on a surface JOYT13 clamps how fast you may go
       ASL
       BNE    JOYS32
JOYS34
       CPX    #$F9 
       BEQ    JOYS30
JOYS32
       INC    IQWARP  ;speed up one notch...
       BCC    JOYS30
       DEC    IQWARP  ;...undoing it if that would wrap
JOYS31
       DEC    IQWARP  ;slow down one notch
JOYS30
       JMP    JOYS24
JOYS77
;
;  VERTICAL
;   Y=VERT
       LSR  ;the vertical bit
       BCC    JOYS24
       LDA    HHORM2 
       CLC
       ADC    JOYTB1,Y  ;scroll the starfield X by JOYTB1...
       CMP    #$A0 
       BCC    JOYS20
;  C=1
       SBC    JOYTB2,Y  ;...wrapping through JOYTB2 at the screen edge
JOYS20
       STA    HHORM2 
;
;  STAR VERTICAL STUFF
       LDA    STARS 
       CLC
       ADC    JOYTB3,Y  ;and scroll the star PATTERN pointer as well
       CMP    #<[STARTB+2]
       BCC    JOYS21
       LDA    JOYTB7,Y  ;JOYTB7 wraps that pointer
JOYS21
       STA    STARS 
JOYS24
       LDA    JOYT11,Y
       STA    JOYRMV  ;JOYRMV = how much every object drifts vertically this frame
;
; HORIZONTAL
       LDX    #$01 
       STX    THGRP1
       LDY    VELOC  ;VELOC = your signed lateral speed
       BIT    TEMP12  ;TEMP12 bit 7 = pushing right, bit 6 = pushing left
       BPL    JOYST2
       BVS    JOYST4
; RIGHT
;  X=1
       CPY    #$1F  ;already at maximum right speed
       BEQ    JOYS11
JOYST3
       INY
       JMP    JOYS12
JOYST2
       BVC    JOYST4
; LEFT
       INX  ; X=2
       CPY    #$E0  ;already at maximum left speed
       BEQ    JOYST7
JOYST5
       DEY
JOYS12
       LDA    #$4E  ;flash the engine flame while thrusting sideways
       STA    HCOLP1 
       BNE    JOYST7  ;jmp
JOYST4
;  NULL
       DEX   ;X=0 -- NULL input: decay the speed back toward zero
       TYA
       BMI    JOYST3
       BNE    JOYST5
JOYST7
       STX    THGRP1  ;THGRP1 = the ship bank angle: 0 level, 1 right, 2 left
       STY    VELOC 
;
       LDX    #$01 
       TYA
       BPL    JOYST6
       INX
JOYST6
       ASL
       ASL
       ASL
       CLC
       ADC    HPOSL  ;accumulate the speed into the sub-pixel remainder...
       STA    HPOSL 
JOYS11
       LDA    JOYTB4-1,X
       ADC    CENTER  ;...and step the camera by the carry
       CMP    #$74  ;the camera is clamped to $2D..$74
       BCS    JOYST9
       CMP    #$2D 
       BCC    JOYST9
       STA    CENTER  ;in range: commit the new camera position
JOYST8
       RTS

JOYST9  ;at a clamp: scroll the STARFIELD instead, which is what makes
       CLC
       LDA    HHORM2 
       ADC    JOYTB5-1,X  ;the world feel wider than the camera range
       CMP    #$A0 
       BCC    JOYS10
       LDA    JOYTB6-1,X
JOYS10
       STA    HHORM2 
       LDA    THGRP1
       BEQ    JOYST8
       LDA    #$00 
       CPX    THGRP1  ;direction reversed, so kill the residual speed
       BNE    JOYS79
       LDA    JOYT14-1,X
JOYS79
       STA    VELOC 
       LDA    PROGST 
       CMP    #$40  ;in the trench the camera does not scroll at all
       BEQ    JOYST8    ;TRENCH
       LDA    JOYT12-1,X  ;JOYRMH = the horizontal twin of JOYRMV
       STA    JOYRMH
       RTS
;
;
;
;
;===============================================================================
; A U D T A B  --  THE SOUND SEQUENCES
;
; J is EQUated to AUDTAB so every sound is named as an offset (AUDEXP-J etc.),
; which is what CH0PTR / CH1PTR hold.
;
; BYTECODE FORMAT, one byte at a time:
;   $00        END of sequence.  The channel loads its SHADOW (CH0SHD/CH1SHD)
;              and plays that next, or falls silent.
;   $01..$04,
;   $06..$0F   set AUDC, the TIA WAVEFORM (noise, square, buzz, ...).  Every
;              sequence starts with one of these.
;   $05 nn     JUMP: continue at AUDTAB offset nn.  Used both to loop a sound
;              and to chain one sound into another.
;   $10        a REST: frequency 0, volume 0.
;   $11..$FF   a NOTE.  The whole byte goes to AUDF (frequency) and the high
;              nibble becomes AUDV (volume).  So the low nibble is pitch and
;              the high nibble is loudness, in one byte.
;
; The sequences: AUDEXP explosion, AUDRMP a long descending ramp, AUDPHN your
; photon, AUDLOW the low-fuel warble, AUDFUL tank full, AUDMAN the man appears,
; AUDTAK takeoff/hyperwarp, AUDEX2..AUDEX6 explosion variants (most of which
; end by jumping into AUDRMP or AUDTAK), AUDSHT the enemy shot, AUDLNH the
; darter launch, AUDVAR the darter drone, AUDCTH catching the man, AUDBMP a
; bump, AUDJMP the hyperjumper, AUDHLP the distress call.
;===============================================================================
AUDTAB
J EQU AUDTAB    ;EQUATE
       .byte $10,$00
AUDEXP
       .byte $0F,$88,$C6,$E9,$E7
AUDRMP
       .byte $08,$E4,$E5,$C6,$A7,$A8,$C9,$EA
       .byte $EB,$CC,$CC,$ED,$EE,$EE,$EF,$F0
       .byte $F0,$F1,$D1,$D2,$B2,$B3,$93,$94
       .byte $94,$75,$75,$56,$56,$57,$37,$38
       .byte $38,$39,$39,$39,$1A,$1A,$1A,$1B
       .byte $1B,$10,$00
AUDPHN
       .byte $08,$A2,$0F,$E6,$83,$C8,$84,$CA
       .byte $85,$89,$88,$89,$68,$6B,$6A,$6B
       .byte $4B,$4C,$4D,$4E,$4F,$31,$31,$32
       .byte $32,$2E,$2F,$11,$12,$13,$10,$00
AUDLOW
       .byte $04,$12,$12,$12,$12,$12,$12,$12
       .byte $38,$38,$38,$38,$38,$38,$38,$00
AUDFUL
       .byte $0F,$65,$42,$00
AUDMAN
       .byte $04,$27,$46,$68,$8A,$00
AUDTAK
       .byte $08,$20,$42,$64,$86,$C4,$E5,$E7
       .byte $C9,$CB,$AD,$E9,$EB,$ED,$CF,$D1
       .byte $D3,$F5,$F5,$F6,$F6,$F6,$D6,$D6
       .byte $D6,$B6,$B5,$94,$94,$73,$73,$73
       .byte $72,$52,$52,$52,$31,$31,$31,$11
       .byte $11,$11,$10,$00
AUDEX2
       .byte $03,$EE,$85,$66,$08,$05,AUDTAK-J+$12
AUDEX3
       .byte $10,$10,$08,$F0,$E1,$E4,$E3
       .byte $05,AUDRMP-J+6
AUDEX4
       .byte $0F,$E4,$C8,$AC,$08,$05,AUDRMP+$11-J
AUDEX5
       .byte $08,$E5,$E2,$E7,$E4,$FF,$05,AUDRMP-J+$21
AUDEX6
       .byte $08,$05,AUDTAK+5-J
AUDSHT
       .byte $08,$28,$66,$82,$05,AUDPHN-J+$A
AUDLNH .byte $08,$41,$8E,$A1,$8B,$00
AUDVAR .byte $04,$14,$13,$12,$11,$00
AUDCTH
       .byte $04,$2C,$2B,$2E,$69,$48,$27,$00
AUDBMP
       .byte $0F,$E8,$84,$CF,$8E,$6F,$6E,$4D
       .byte $4C,$4B,$2A,$29,$28,$27,$26,$10,$00
AUDJMP
       .byte $08,$21,$22,$43,$6C,$6A,$68,$87
       .byte $86,$85,$A3,$C1,$E4,$FF,$10,$00
AUDHLP
       .byte $04,$10,$51,$4F,$53,$00
;
;
;
SHPTB1
       .byte $8E,$8C,$8E,$8C,$8A,$88,$86,$84
       .byte $82,$80,$82,$80,$82,$80,$82,$80
;
SHPTB2
       .byte $8F,$8D,$8F,$8C,$8F,$8C,$8B,$8C
;
; SHPTB1 / SHPTB2 -- background colour ramps played during the hyperwarp and
; the takeoff animation.  SHPTB4 is the three-entry ramp used at the end.
       .byte $8A,$8D,$8A,$8C,$89,$8A,$88,$8A
       .byte $88,$8D,$88,$86,$84,$86,$84,$83
       .byte $84,$80,$82,$80,$82,$80,$83,$80
;
;
;
;
;===============================================================================
; S H P S R V  --  YOUR SHIP, AND FIRING
;
; Two modes:
;
;   NORMAL (SHPSR4).  Your ship sits at a fixed Y and its X follows CENTER
;   plus a small offset per bank angle (JOYTB8).  THGRP1 chooses one of the
;   three ship graphics via JOYTB9.
;
;   TAKEOFF / HYPERWARP (SHPSR1).  HCOLP1+1 is the animation clock, counting up
;   to $70.  The ship graphic and colour ramp are indexed from it via LINTB3
;   and LINTB5, the background cycles through SHPTB1/SHPTB2, and during a
;   hyperwarp the camera drifts randomly (SHPTB5 sets how much per difficulty
;   tier) which is what makes a jump inaccurate -- that inaccuracy becomes the
;   JUMP QUALITY the spawner reads out of GAMEST.
;
; It then falls straight through into PHOTON.
;===============================================================================
SHPSRV
;  SHIP GRAPHICS, ETC
       LDA    SHIPST 
       BMI    SHPSR1  ;SHIP TAKEOFF -- SHIPST bit 7 = the takeoff / hyperwarp animation is running
       CMP    #$20  ;$20 = hyperwarp queued but not yet started
       BNE    SHPSR4
;  HWARP SPEEDUP
       LDA    #$05 
       STA    TARNUM   ;HYP CURSOR -- the scanner shows the jump cursor during a warp
       LDY    #PBLK
       STY    IQREAP ;GRAPH
       LDX    #$FF 
       LDA    #$50 
       STA    PLINES  ;fixed surface height during the warp
       SBC    CENTER  ;how far the camera has drifted from centre...
       BCS    SHPS55
       LDX    #$01 
       EOR    #$FF 
SHPS55
       LSR
       CMP    #$04 
       BCC    SHPS56  ;...clamped to 0..3, which becomes the displayed JUMP QUALITY
       LDX    #$00 
       LDA    #$03 
SHPS56
       STA    IQPATH-1      ;DISPLAY JMP QUAL. -- IQPATH-1 is reused to carry the jump quality to the display
;
       LDA    ATRACT 
       LSR
       LSR
       LSR
       LDA    IQWARP  ;the throttle drives the tunnel colour
       ROL
       SBC    #$AE 
       CMP    #$31 
       BCS    SHPS21
       CMP    #$10 
       BCC    SHPSR6
       LDA    #$0F 
SHPSR6
       TAY
       LDA    SHPTB1,Y  ;SHPTB1 = the background colour ramp for the tunnel
       STA    COLBK
       LDY    NEWAVE  ;SHPTB5[difficulty] = how likely the camera is to drift
       LDA    RANDOM 
       CMP    SHPTB5,Y
       BCS    SHPS21
       TXA
       ADC    CENTER   ;C=0 -- drift the camera, which is what degrades the jump accuracy
       STA    CENTER 
SHPS21
       LDA    ATRACT 
       LSR
       LDA    #$50 
       BCC    SHPS20
SHPSR4
;  NORMAL SHIP
       LDA    CENTER  ;normal ship: X follows the camera
SHPS20 LDX    THGRP1
       STA    RANDOM+1 
       CLC
       ADC    JOYTB8,X  ;HOFFSET -- JOYTB8[bank] = the small horizontal offset per bank angle
       STA    HHORP1 
       LDA    JOYTB9,X  ;JOYTB9[bank] = which of the three ship graphics to draw
       JMP    SHPSR5
SHPSR1
       LDY    HCOLP1+1  ;Y = the takeoff animation clock
       BIT    PROGST 
       BVC    SHPSR3
;  PLANET/TRENCH
       LDA    #$02 
       STA    GCTLM1  ;FIX M1 GLITCHES -- a missile-glitch fix needed only on a surface
       CPY    #$13    ;$13 FOR TRENCH
       BCS    SHPSR3
       INC    HVERP1  ;PLANET TAKEOFF FIX -- planet takeoffs need one extra scanline of lift
SHPSR3
       LDA    RANDOM 
       AND    #$03 
       TAX
       LDA    SHPTB4,X  ;SHPTB4 = the late-takeoff colour flicker
       CPY    #$20 
       BCS    SHPSR7
       LDA    SHPTB2,Y  ;SHPTB2 = the main takeoff background ramp
SHPSR7
       STA    COLBK
       STA    ZDELP0-1  ;HOLD BAK COLOR
       LDA    #$4A 
       STA    HCOLP1 
       LDA    HOLDM0    ;FROM HYPSRV -- HOLDM0 is the zoom value HYPSRV cached for us...
       LSR
       LSR
       LSR
       LSR
       AND    #$07 
       CLC
       ADC    HVERP1  ;...and it is what lifts the ship up the screen
       STA    HVERP1 
       TYA
       LSR
       LSR
       TAX
       CMP    #$08 
       BCC    SHPSR2
       LDX    #$07 
SHPSR2
       INC    HCOLP1+1  ;advance the takeoff animation clock
       LDA    LINTB5,X  ;LINTB5[step] = the ship colour ramp for this step
       SEC
       SBC    HVERP1 
       STA    ATRACT+1    ;SHIP COLOR PNTR
       LDA    LINTB3,X  ;LINTB3[step] = the ship graphic for this step
SHPSR5
       SEC
       SBC    HVERP1  ;pre-bias by the ship Y so the kernel can index it directly
       STA    HGRAP1 
;   FALL THRU
;
;
;-------------------------------------------------------------------------------
; PHOTON -- FIRE AND ADVANCE YOUR TORPEDOES.
;
; You may have two shots in flight.  The near one is P1+1, the far one is P1+2.
; Firing loads the near slot; when the near shot gets far enough it is
; TRANSFERRED into the far slot (PHOT56), freeing the near slot for another.
;
; ONESHT bit 7 is the fire-button edge detector, so holding the button does not
; auto-fire.  ONESHT bit 2 alternates, so only every OTHER shot costs a unit of
; fuel.
;
; PHOTN1 then advances both shots: ZPOS increments (they recede), the vertical
; position rises by a zoom-derived amount that HYPSRV cached in VECTP1, and the
; graphic is picked from PHOTB1 by zoom step.  PHOTB3 enforces a minimum
; vertical gap between the two so they do not merge visually.
;-------------------------------------------------------------------------------
PHOTON
; FIRE PHOTON TORPEDO
       BIT    SHIPST  ;during a takeoff the ship RAM is in use, so no firing
       BPL    PHOT97
       RTS   ;USING SHIP RAM DURING TAKEOFF
PHOT55
       LDA    PAUTIM  ;already paused: just latch the request for later
       BNE    PHOTN5 ;WAIT
       LDA    ONESHT 
       ORA    #$02 
       STA    ONESHT 
       BNE    PHOTN5 ;JMP
PHOT97
       LDX    TRIG0  ;TRIG0 = the fire button
       BMI    PHOTN5
       LDY    #$00 
       STY    ATRACT+1  ;any press clears the attract timer
       BIT    ONESHT  ;ONESHT bit 7 = the button was released since the last shot
       BPL    PHOTN5
       LDA    PROGST 
       BMI    PHOT55   ;GAME OVER -- game over: the button means restart, not fire
       CPY    HVERP1         ;Y=0 -- you cannot fire while dead
       BEQ    PHOTN5
       AND    #$F8 
       CMP    PROGST 
       STA    PROGST 
       BNE    PHOTN5
       LDA    ZPOSP1  ;is the near photon free? (bit 7 set means off)
       BMI    PHOT44
       LDA    ZPOSP1+1  ;the far one is close enough to be pushed along instead
       CMP    #$31 
       BCS    PHOT56
       BCC    PHOTN8   ;JMP
PHOT44
;  LOAD PHOTON
       LDA    #AUDPHN-J  ;the firing sound
       STA    CH0PTR 
       STY    ZPOSP1    ;Y=0 -- switch the near photon on
       LDA    ONESHT 
       AND    #$7F      ;ONESHT
       EOR    #$04  ;ONESHT bit 2 alternates, so only every OTHER shot costs fuel
       STA    ONESHT 
       AND    #$04 
       BEQ    PHOT11
       LDY    FUEL 
       BEQ    PHOT11
       DEC    FUEL  ;one unit of fuel
PHOT11
       SEC
       ADC    CENTER  ;the shot starts at the camera X...
       STA    HOLDM2 
       LDA    #VSHIP+$09  ;...and just above the ship
       STA    HVERP1+1
       BNE    PHOTN8     ;JMP
PHOTN5
       ASL    ONESHT  ;remember the button state for the edge detector
       TXA
       ASL
       ROR    ONESHT 
       LDA    ZPOSP1 
       BMI    PHOTN8
       CMP    #$09 
       BCC    PHOTN8
       LDA    ZPOSP1+1 
       BPL    PHOTN8
PHOT56
;  TRANSFER
       LDA    ZPOSP1  ;TRANSFER: move the near shot into the far slot...
       STA    ZPOSP1+1 
       LDA    HVERP1+1 
       STA    HVERP1+2 
       LDA    HHORP1+1 
       STA    HHORP1+2
       LDA    #$80  ;TURN OFF
       STA    ZPOSP1  ;...and free the near slot for another
PHOTN8
;
       LDA    #$08 
       STA    HCOLP1+1 
       LDX    #$01 
PHOTN1
       LDY    ZPOSP1-1,X  ;bit 7 set means this photon is off
       BPL    PHOTN3
       LDA    HVERP1-1,X
       BNE    PHOT29
       LDA    #VSHIP  ;EXPLODED SHIP -- a destroyed ship still needs a muzzle position
PHOT29
       CLC
       ADC    #$06 
       STA    HVERP1,X
       LDY    #$08 
       BNE    PHOT27   ;JMP
PHOTN3
;  PHOTON ON
       LDA    VECTP1-1,X   ;HOLD ZOOMTB FROM HYPRSRV -- the ZOOMTB value HYPSRV cached for this photon...
       AND    #$70 
       LSR
       LSR
       LSR
       LSR
       ADC    HVERP1,X     ;C=0 -- ...raises the shot up the screen as it recedes
       STA    HVERP1,X
       INC    ZPOSP1-1,X  ;and it gets one step further away each frame
       TYA
       LSR
       LSR
       LDY    #$07 
       CMP    #$08 
       BCS    PHOT27
       LDY    #$0E  ;close shots get the bright colour
       STY    HCOLP1+1  ;PHOTON COLOR 
       TAY
PHOT27
       LDA    PHOTB1,Y  ;PHOTB1[zoom] = the photon graphic at this distance
       SEC
       SBC    HVERP1,X
       STA    HGRAP1,X
       INX
       CPX    #$03 
       BCC    PHOTN1
; VERT SPACING
       LDA    HVERP1+2  ;SIMPLIFY?
       SBC    PHOTB3,Y   ;C=1 -- PHOTB3 enforces a minimum gap between the two shots
       CMP    HVERP1+1
       BCS    PHOT28
       INC    HVERP1+2  ;too close: push the far one up one line
       DEC    HGRAP1+2   ;ADJ 
       LDA    HVERP1+1
       CMP    #$4D  ;past this Y the shot has reached maximum range...
       BIT    PROGST 
       BVC    PHOT83
;  PLN/TRN
       CMP    #$4B 
PHOT83
       BCC    PHOT28
       LDA    ZPOSP1 
       BMI    PHOT28
       LDA    #$80 
       STA    ZPOSP1+1  ;...so switch it off
PHOT28
       RTS
;
;
;
;
;
;===============================================================================
; A U D I O  --  THE TWO-CHANNEL SOUND SEQUENCER
;
; Services ONE channel per frame, alternating on the frame counter, so each
; channel updates at 30Hz.  X selects the channel (0 or 1) and indexes both
; the pointers (CH0PTR,X) and the TIA registers (AUDC0,X).
;
; Per channel:
;   fetch AUDTAB[ptr]; interpret it per the bytecode above; advance ptr.
;   On $00 (end of sequence) load the SHADOW register into the pointer and
;   clear the shadow -- that is the whole sound-priority scheme: a routine that
;   wants a sound NOW writes CHnPTR, one that wants it NEXT writes CHnSHD.
;
; AUDIO9 onward is the ENGINE, layered on top of channel 1 whenever nothing
; else is using it: pitch comes straight from IQWARP (the throttle) and volume
; from SPDVOL, plus a small boost while the stick is being moved.  During a
; hyperwarp the same engine is doubled onto channel 0 at a slightly different
; pitch, which is what gives the jump its beating sound.
;===============================================================================
AUDIO
       LDA    ATRACT 
       AND    #$01  ;alternate channels every frame, so each updates at 30Hz
       TAX
       LDY    CH0PTR,X  ;this channel program counter
       LDA    AUDTAB,Y  ;fetch the next byte of the sequence
       BNE    AUDIO2  ;non-zero: it is a command or a note
       LDA    PROGST 
       AND    #$81  ;during game over or screen protect, force silence
       BNE    AUDIO1
       LDY    CH0SHD,X  ;END of sequence: promote the SHADOW to the pointer...
       STY    CH0PTR,X
       STA    CH0SHD,X  ;...and clear the shadow
       RTS

AUDIO5
       CMP    #$05  ;$05 = the JUMP command
       BNE    AUDIO4
;  JUMP
       LDA    AUDTAB+1,Y  ;continue at the offset held in the next byte
       STA    CH0PTR,X
       RTS

AUDIO4
       STA    AUDC0,X  ;below $05 the byte is a WAVEFORM (AUDC)
       RTS

AUDIO2
       INC    CH0PTR,X  ;advance the sequence pointer
       CMP    #$10  ;below $10 it was a command, not a note
       BCC    AUDIO5
       BEQ    AUDIO3  ;exactly $10 is a REST
       STA    AUDF0,X  ;otherwise the whole byte is the FREQUENCY...
       LSR
       LSR
AUDIO1
       LSR
       LSR
AUDIO3
       STA    AUDV0,X  ;...and its high nibble is the VOLUME
       CPY    #AUDHLP-J  ;AUDHLP and later are held two frames per note, which is what
       BCC    AUDIO9
       LDA    ATRACT 
       AND    #$1E 
       BEQ    AUDIO9
       DEC    CH0PTR,X         ;REPEAT NOTE -- makes the distress call slower than everything else
AUDIO9
;    ENGINE AUDIO
       LDA    CH1PTR 
       CMP    #$02  ;is channel 1 already busy with a real sound?
       BCS    AUDIO6  ;CHANEL IN USE
       LDY    IQWARP  ;the throttle, treated as signed
       BPL    AUDIO6
       TYA
       CMP    #$F2 
       BCS    AUDIO7
       ADC    #$3A   ;3A=1D*2  C=0 -- scale it into the engine pitch range
       ROR
AUDIO7
       TAX
       STA    AUDF1  ;AUDF1 = the engine pitch
       LDA    SHIPST 
       CMP    #$20  ;during a hyperwarp the engine is doubled onto channel 0...
       BNE    AUDIO8
       LDA    CH0PTR 
       CMP    #$02 
       BCS    AUDIO8
       DEX  ;...one step detuned, which is what produces the beating
       STX    AUDF0  ;HWARP
       LDA    #$08 
       STA    AUDC0
       LDA    SPDVL1-$D8,Y  ;SPDVL1[throttle] = the channel 0 engine volume
       LSR
       LSR
       LSR
       LSR
       STA    AUDV0
AUDIO8
       LDA    #$08 
       STA    AUDC1
       LDA    SPDVOL-$D8,Y  ;SPDVOL[throttle] = the channel 1 engine volume
       LSR
       LSR
       LSR
       LSR
       LDY    #$F0 
       CPY    PORTA
       ADC    #$01   ;C=1=MOVE JOYSTK -- moving the stick adds one to the volume
       STA    AUDV1
AUDIO6
       RTS
;
;
;
; DIS740 -- the P1 horizontal positioning fragment.  HOLDP1 holds the fine
; remainder of the ship X and this burns the matching number of cycles before
; strobing RESP1.  PURE PLUMBING.
DIS740
;  HPOSP1
       STA    VECTP1
       LDA    #$00 
       STA    GRAFP1
       DEY
       LDA    HOLDP1
       LSR
       BCS    DIS742  ;DELAY
DIS742
       BEQ    DIS741   ;CY 39-40
       STX    HDELP0
       CMP    #$02 
       BCS    DIS743  ;CY 57-58
;  CY 48-49
       LDA    RANDOM  ;DUMMY
       STA    HPOSP1
       LDA    (STARS),Y
       JMP    DIS744
DIS743
       CPY    CROSP1 ;FIX STAR BUG
       BCC    DIS745
DIS745
       LDA    (STARS),Y
       STA    HPOSP1
DIS744
       STA    GRAFM2
       ORA    #SCLR
       STA    COLPF
       LDX    #$00 
       JMP.ind (VECTP0)
DIS741
       STA    HPOSP1
       STX    HDELP0
       LDA    (STARS),Y
       JMP    DIS744
;
;
;-------------------------------------------------------------------------------
; BANK 2 EXIT TRAMPOLINES.  PLUMBING -- see header section 8.
; PON2 is the entry point the other banks call to run JOYSTK and AUDIO.
; JOYTB8/JOYTB9 (ship offset and graphic per bank angle) and JOYT11..JOYT14
; (the joystick response constants) are wedged into the gaps.
;-------------------------------------------------------------------------------

;
;  BANK SELECT CODE
 ORG $2FCC
 RORG BANK2+$FCC

PON2
       STA    STROB1      ;JMP CFCF
       JSR    JOYSTK
       JSR    AUDIO
       STA    STROB3      ;JMP DFD8
JOYTB8 .byte $00,$02,$01
JOYTB9
       .byte <YGR1+2,<YGR2+2,<YGR3+2
;       .byte $D7,$EB,$FF
EXIT9
       STA    STROB4      ;JMP FFE1
       JSR    SHPSRV
       STA    STROB4      ;JMP FFE7
JOYT11 .byte $00,$06,$FA,$00
JOYT12 .byte $F9,$07
       JMP    DISPLY
JOYT13 .byte $00,$FF,$01,$00
JOYT14 .byte $1F,$E0
       .byte "DOUG N"
       .word PON2
       .word PON2

;
;
;===============================================================================
; B A N K   4  --  SURFACE AND HYPERWARP DISPLAY, MOVER, PLNSRV
;
; Three display kernels and one piece of core logic:
;
;   PLN*  the PLANET / TRENCH kernel.  Same vectored state-machine design as the
;         space kernel in bank 2 (see that bank header for the full
;         explanation) with three surface-specific additions:
;           * a HORIZON.  Objects do not float; they sit on the ground line,
;             which SURTB2 gives as a function of distance and which SURTB3 /
;             SURTB4 / SURTB5 draw as playfield.
;           * the STAR pattern is ANDed with CROSP1 so stars only appear in the
;             sky above the horizon.
;           * a background colour split: SKYCOL above, SURCOL / TRNCOL below.
;   TRN*  the same kernel specialised for the TRENCH: two moving walls whose
;         position is VWALL, drawn from SURTB5 and WALLTB.
;   HYP*  the HYPERWARP TUNNEL: your ship plus a starfield built from LINTB4,
;         with the two photons repurposed as streaking stars (HYPSRV drives
;         them).
;
;   MOVER is the real work: it integrates every object position from its packed
;   velocity, once per frame, and reseeds the PRNG.  It is the first thing the
;   frame loop calls.
;
;   PLNSRV / TRNSRV set up the surface parameters each frame: horizon height,
;   sky and ground colours, wall position, and the planet-explosion effects.
;
; PYTHON PORT: MOVER and PLNSRV matter; the kernels do not, beyond the sprite
; and colour data they index.
;===============================================================================
; ********************************
;   VERSION 11.2   31-JUL-84
;COPYRIGHT (C) 1986, DOUGLAS NEUBAUER
; INCLUDE BANK4.SRC FOR UNIV.SRC
; ********************************
;
;
;*********
       seg bank4
       ORG $3000
       RORG BANK4   ;BEGIN BANK4
;  ALWAYS F000
;*********
;
;
; WARNING: MUST BE ON PAGE BOUNDARY
;
; --- SURFACE KERNEL FRAGMENT: draw YOUR SHIP.  Same shape as the space
;     version, plus the sky/ground colour split (A holds SURCOL or 0) and the
;     star mask CROSP1 so stars stop at the horizon.
PLN500
; DISPLAY SHIP
       STA    COLBK
       LDA    (MISC1),Y
       STA    GRAFP1
       BEQ    PLN501
       LDA    (MISC2),Y
       STA    COLPM1
PLN502
       DEY
       LDA    (STARS),Y
       AND    CROSP1
       BEQ    PLN503
       LDA    (MISC1),Y
       TAX
       LDA    (MISC2),Y
       STA    COLPM1
       ASL
       STA    GRAFM1
       LDA    #SURCOL 
       JMP.ind (VECTP0)
PLN503
       LDA    (MISC1),Y
       TAX
       LDA    (MISC2),Y
       STA    COLPM1
       ASL
       STA    GRAFM1
       LDA    #$00 
       JMP.ind (VECTP0)
PLN501
       DEY
       LDA    (MISC1),Y
       STA    GRAFP1
       STY    GRAFM1
       LDA    #<PLN130  ;WARNING BIT 1 MUST =0
       STA    GRAFM1   ;KLUDGE HWARP STARS FIX !!!!!
       STA    VECTP1
       LDA    (STARS),Y
       AND    CROSP1
       BEQ    PLN504
       LDA    #SURCOL
PLN504
       LDX    HCOLP1 
       STX    COLPM1
       LDX    #$00 
       JMP.ind (VECTP0)
;
;
; --- FRAGMENT: WAIT for the ship.  HYP780 is the hyperwarp variant.
PLN780
; WAIT SHIP
       STA    COLBK
       LDA    #<PLN500  ;=0
       STA    VECTP1
       STA    GRAFP1
       CPY    HVERP1 
       STA    HDELP1
       BCC    PLN502
       LDX    #<PLN780
       JMP    PLN910
;
;
HYP780
;  WAIT HYPERSHIP
       STA    COLBK
       LDA    #<PLN500  ;=0
       STA    VECTP1
       CPY    HVERP1 
       STA    HDELP1
       BCC    PLN502
       BEQ    PLN581
       LDX    #<HYP780
       JMP    PLN910
;
;
;
; --- FRAGMENT: WAIT for the end of the picture.
PLN580
; WAIT END OF SCREEN
       STA    COLBK
       LDA    #$00 
       STA    GRAFP1
PLN581
       DEY
       JMP    PLN911
;
;
;
; --- FRAGMENT: horizontally position the photon / ship / hyperwarp ship.
PLN330
; HPOS PHOTON
       LDX    #<PLN370
       JMP    PLN740
;
;
PLN730
; HPOS SHIP
       LDX    #<PLN780
       JMP    PLN740
;
;
HYP730
;  HPOS HYPERSHIP
       LDX    #<HYP780
       JMP    PLN740
;
;
       .byte $00,$00
;  WARNING BIT 1 OF PLN130 MUST=0 FOR HWARP STARS FIX!!!
;
; --- FRAGMENT: draw a PHOTON on a surface.  As in space, the graphic is ANDed
;     with (RANDOM),Y to make it shimmer.
PLN130
; DISPLAY P1 PHOTON
       STA    COLBK
       LDA    (MISC1),Y
       AND    (RANDOM),Y
       STA    GRAFP1
;
       DEY
PLN132
; ENTRY FROM WAIT PHOTON, 27 CY
;
       LDA    (MISC1),Y
       BNE    PLN131
       LDX    PNTRP1 
       STX    VECTP1 
       LDA    PLN500-1,X
       STA    PNTRP1 
       LDX    #$00 
PLN134
       LDA    (STARS),Y
       AND    CROSP1
       BEQ    PLN133
       LDA    #SURCOL
PLN133
       JMP.ind (PNTR1)
PLN131
       AND    (RANDOM),Y
       TAX
       LDA    #<PLN130
       STA    VECTP1
       BNE    PLN134   ;JMP
;
;
;
; --- FRAGMENT: WAIT for a photon.
PLN370
; WAIT PHOTON
       STA    COLBK
       LDA    #$00 
       STA    GRAFP1
       CPY    VERTP1
       DEY
       STA    HDELP1
       BCC    PLN132
       CPY    VERTP1 
       BCS    PLN371
       LDA    #<PLN130
       STA    VECTP1
PLN371
       JMP    PLN912
;
;
       .byte <PLN700
;
; --- FRAGMENT: SETUP the photons and then the ship for the surface P1 chain.
PLN350
;SETUP P1+1
       STA    COLBK
       LDA    #$0
       STA    GRAFP1
       LDA    HVERP1+1 
       STA    VERTP1
       LDA    HGRAP1+1
       STA    MISC1
       LDA    HHORP1+1 
       JMP    PLN902
;
;
       .byte <PLN580
PLN700
; SETUP SHIP
       STA    COLBK
       LDA    #$0
       STA    GRAFP1
       LDA    HGRAP1 
       STA    MISC1
       STA    MISC2
; 
       LDA    HHORP1 
       STA    HDELP1
       AND    #$0F 
       STA    HOLDP1
       LDA    #<PLN730
       JMP    PLN900
;
;
;
;   P0 KERNALS
;
;
; --- FRAGMENT: the surface P0 chain -- wait, draw, advance, setup, position.
;     Structurally identical to the space P0 chain; the differences are the
;     background colour split and the horizon line.
PLN207
       STX    HDELP0
       STA    WSYNC
       STA    ADDEL
       STX    SIZPM0
       JMP.ind (VECTP1)
PLN250
;  WARNING: LOW PLN250 MUST BE <$10
; WAIT P0
       STA    WSYNC
       STA    ADDEL
       STA    COLBK
       STX    GRAFP1
;
       LDA    #$00 
       STA    COLPM0
       LDA    #<PLN200
       STA    VECTP0
       CPY    VERTP0 
       BCC    PLN203
       DEY
       CPY    VERTP0
       BCC    PLN206  ;MUST HAVE C=0
       BCS    PLN259  ;JMP
;
;
PLN200
; DISP P0
       STA    WSYNC
       STA    ADDEL
       STA    COLBK
       LDA    (MOON1),Y
       STA    GRAFP0
       STX    GRAFP1
       LDA    (MOON3),Y
       STA    COLPM0
PLN203
;  27 CY
       DEY
       LDA    (MOON1),Y
       STA    GRAFP0
       BEQ    PLN201
;
       LDA    (MOON3),Y
       TAX
       LSR
;
PLN206
;  ENTRY C=0!!
       LDA    (STARS),Y
       AND    CROSP1
       BEQ    PLN204
       LDA    #SURCOL
PLN204
       BCS    PLN207
PLN209
;  ENTRY
       STA    WSYNC
       STA    ADDEL
       STX    COLPM0
       JMP.ind (VECTP1)
PLN201
;  41 CY
       TSX
       BEQ    PLN202
       DEX
       TXS
       LDA    HVERP0,X
       STA    VERTP0
;
       LDX    #<PLN400
       JMP    PLN402
PLN202
       STX    PNTR3 
PLN259
       JMP    PLN462
;
;
PLN400
; SETUP P0, 1ST LINE
       STA    WSYNC
       STA    ADDEL
       STA    COLBK
       STX    GRAFP1
       TSX
       LDA    MIPL
       STA    HHITP0+1,X
       STA    HITCLR
       DEY
       LDA    HGRAP0,X
       BMI    PLN201
       STA    MOON1  ;HOLD
       LDA    HHITP0,X
       STA    HDELP0
       AND    #$0F 
       STA    MOON3  ;HOLD
       LDA    (MOON2),Y
       AND    CROSP1
       BEQ    PLN403
       LDA    #SURCOL
PLN403
       STA    MOON3+1
;
       LDX    #<PLN430
PLN402
;  ENTRY
       LDA    (STARS),Y
       AND    CROSP1
       BEQ    PLN401
       LDA    #SURCOL
PLN401
       STA    WSYNC
       STA    ADDEL
       STX    VECTP0
       JMP.ind (VECTP1)
;
;
PLN430
; HPOSP0
       STA    WSYNC
       STA    ADDEL
       STA    COLBK
       STX    GRAFP1
       LDX    #<PLN460
       LDA    MOON3
       LSR
       BCS    PLN431   ;DELAY
PLN431
       BEQ    PLN432
       STX    VECTP0
PLN433
       SEC
       NOP
       SBC    #$01 
       BNE    PLN433
       STA    HPOSP0
PLN434
       DEY
       STA    WSYNC
       STA    ADDEL
       LDA    MOON3+1   ;LINE LOOK AHEAD
       JMP.ind (VECTP1)
PLN432
       STA.w  HPOSP0     ;STA ABS HPOSP0 (ORIG = DB $8D,HPOS0,0)
       STX    VECTP0
       BEQ    PLN434   ;JMP
;
;
;
; --- FRAGMENT: PLN800 draws the MOUNTAIN RANGE / horizon from SURTB1 and the
;     playfield tables, which is what the surface has instead of a starfield.
PLN800
; PLOW UP PLANET
       STA    WSYNC
       STA    ADDEL
       STX    GRAFP1
       CPY    #$50 
       BCS    PLN804
       LDA    (RANDOM),Y
       CMP    YDELP0-1   ;PROB.
       ROL
       ROL
       STA    GRAFM0
PLN804
       DEY
       LDA    #$0E 
       STA    COLPM0
       LDA    HCOLP1 
       LDX    #$00 
       STX    SIZPM0
       STA    WSYNC
       STA    ADDEL
       STX    GRAFM0
       JMP.ind (VECTP1)
;
;
;
PLN460
; SETUP P0, 2ND LINE
       STA    WSYNC
       STA    ADDEL
       STA    COLBK
       STX    GRAFP1
       LDX    MOON1  ;HOLD
       LDA    PTABL4,X
       STA    SIZPM0
       SEC
       LDA    PTABL2,X
       SBC    VERTP0
       STA    MOON3
       LDA    PTABL1,X
       SBC    VERTP0 
       STA    MOON1
       LDA    PTABL3,X
       STA    MOON3+1 
       SBC    #$00 
       STA    MOON1+1
       DEY
PLN462
;  ENTRY
       LDX    #<PLN250
       LDA    (STARS),Y
       AND    CROSP1
       BEQ    PLN461
       LDA    #SURCOL
PLN461
       STX    HDELP0  ; X<$10
       STA    WSYNC
       STA    ADDEL
       STX    VECTP0
       JMP.ind (VECTP1)
;
;
;
;
; --- FRAGMENT: shared setup and wait entries for the surface chains, ending
;     at PLN912 which tests Y against BOTSCN.
PLN902
; ENTRY FROM PHOTON SETUP
       STA    HDELP1
       AND    #$0F 
       STA    HOLDP1
       LDA    #<PLN330
PLN900
;  MISC ENTRY
       DEY
       STA    VECTP1
PLN903
       LDA    (STARS),Y
       AND    CROSP1
       BEQ    PLN905
       LDA    #SURCOL
PLN905
       LDX    #$00 
       JMP.ind (VECTP0)
;
PLN910
; WAIT ENTRY
       DEY
       STX    VECTP1
PLN911
;  END SCREEN ENTRY
       CPY    #$06    ;BUG, WANT 4 FOR HYPER
       BNE    PLN912
       STA    GRAFM2  ;A=0 FOR TRENCH
PLN912
       CPY    #$00 
       BNE    PLN903
       JMP    EXIT8   ;TO SCANDS
;
;
;
; --- HYPERWARP KERNEL FRAGMENTS.  A much simpler chain: your ship plus the
;     two photons repurposed as streaking stars, over a colour-cycling
;     background.  HYPSRV in bank 1 drives the star motion each frame.
HYP250
; TOP HALF
       STX    YDELP0+3  ;TEMP
       LDX    WALLTB+1+8,Y   ;TRENCH FIX
       LDA    WALLTB+0+8,Y
       STA    GRFPF0,X
       DEY
       DEY
       LDX    YDELP0+3
HYP256
;  ENTRY FROM TOP O SCREEN
       LDA    LINTB4,X
       ASL
       STA    WSYNC
       STA    ADDEL
       STA    GRAFM1
       ROR
       CPX    YDELP0  ;VPOS2
       BCS    HYP251
       CPX    YDELP0+1 ;VPOS1
       BCS    HYP252
HYP251
       LDA    ZDELP0-1  ;DEFAULT
HYP252
       STA    COLBK
       INX
       TXA
       AND    #$03 
       BEQ    HYP250
       CPX    #$4D 
       BNE    HYP256
;  MIDDLE O SCREEN
       LDA    #$10 
       STA    HDELM2
       LDA    #$F0 
       STA    HDELM0
       LDX    #$00
;  Y=$4C    ,I HOPE.
;  FALL THRU TO HYP200
;
;
HYP200
; BOT HALF 
       STA    WSYNC
       STA    ADDEL
       STX    GRAFP1
       STA    GRAFM1
       LDA    ZDELP0-1  ;DEFAULT
       CPY    YDELP0    ;VPOS2
       BCS    HYP201
       CPY    YDELP0+1  ;VPOS1
       BCC    HYP201
       LDA    LINTB4,Y
HYP201
       STA    COLBK
       DEY
       LDX    WALLTB,Y
       LDA    WALLTB-1,Y
       STA    GRFPF0,X
       LDA    ZDELP0-1
       CPY    YDELP0    ;VPOS2
       BCS    HYP203
       CPY    YDELP0+1  ;VPOS1
       BCC    HYP203
       LDA    LINTB4,Y
HYP203
       LDX    #$00 
       STA    WSYNC
       STA    ADDEL
       STX    GRAFM1
       JMP.ind (VECTP1)
;
;
;
; --- TRENCH KERNEL FRAGMENTS.  The surface chain specialised for the trench:
;     two walls at VWALL drawn from SURTB5 and WALLTB, with the gap between
;     them being what you have to fly through.  TRNHLP sets the parameters.
TRN251
       LDA    #TRNCOL
       STA    COLPF
       LDA    #$8A 
       STA    GRAFM2
       STA    GRAFM0
       CPY    VWALL 
       DEY
       BCS    TRN254
       LDX    #$10 
       STX    HDELM2
       LDX    #$F0 
       STX    HDELM0
       LDX    #<TRN250
       BNE    TRN259   ;JMP
TRN254
       CPY    YDELP0-1  ;VWIND
       BCS    TRN252
       LDA    #SURCOL
TRN252
; ENTRY
       LDX    #<TRN255
       BNE    TRN259     ;JMP
;
;
TRN207
       STX    HDELP0
       STA    WSYNC
       STA    ADDEL
       LDX    SIZPM0     ;DUMMY, NO CRATERS
       JMP.ind (VECTP1)
;
TRN256
;  SETUP PF
       LDA    #$00 
       STA    COLBK
       STA    GRFPF2
       LDY    VWALL 
       LDX    WALLTB-7,Y
       BNE    TRN257
       STA    GRFPF1
TRN257
       LDA    WALLTB-8,Y
       STA    GRFPF0,X
       LDY    #$55   ;RESTORE
       LDA    #$00 
       BEQ    TRN252     ;JMP
;
;
TRN255
;  DOING WALL
       STA    WSYNC
       STA    ADDEL
       STX    GRAFP1
       JMP    TRN251
;
;
TRN200
; DISPL P0
       STA    WSYNC
       STA    ADDEL
       STA    COLBK
       LDA    (MOON1),Y
       STA    GRAFP0
       STX    GRAFP1
       LDA    (MOON3),Y
       STA    COLPM0
TRN203
;  27 CY
       DEY
       LDX    WALLTB-6,Y
       LDA    WALLTB-7,Y
       STA    GRFPF0,X
       LDA    (MOON1),Y
       STA    GRAFP0
       BEQ    TRN201
;
       LDA    (MOON3),Y
       TAX
       LSR
;
TRN206
;  ENTRY C=0!!
       LDA    #SURCOL
       BCS    TRN207
       STA    WSYNC
       STA    ADDEL
       STX    COLPM0
       JMP.ind (VECTP1)
TRN201
;  53 CY
       TSX
       BEQ    TRN202
       DEX
       TXS
       LDA    HVERP0,X
       STA    VERTP0
;
       LDX    #<TRN400
TRN402
; ENTRY
       LDA    #SURCOL
TRN259
;  ENTRY FROM WALL
       STA    WSYNC
       STA    ADDEL
       STX    PNTR1 
       JMP.ind (VECTP1)
TRN202
       STX    PNTR3 
TRN403
;  ENTRY
       LDX    #<TRN250
       BNE    TRN402  ;JMP
;
;
TRN250
;    WAIT P0
       STA    WSYNC
       STA    ADDEL
       STX    GRAFP1
       CPY    #$56       ;TOP OF TRENCH
       BEQ    TRN256
       STA    COLBK
       LDA    #<TRN200
       STA    VECTP0
       CPY    VERTP0
       BCC    TRN203
       DEY
       LDX    WALLTB-6,Y
       LDA    WALLTB-7,Y
       STA    GRFPF0,X
       LDX    #TRNCOL     ;M0 COLOR
       STX    COLPM0
       CPY    VERTP0
       BCC    TRN206  ;MUST HAVE C=0
       BCS    TRN403  ;JMP
;
;
TRN400
; SETUP P0, 1ST LINE
       STA    WSYNC
       STA    ADDEL
       STA    COLBK
       STX    GRAFP1
       LDA    #TRNCOL
       STA    COLPM0
       DEY
       LDX    WALLTB-6,Y
       LDA    WALLTB-7,Y
       BEQ    TRN401
       LDA    WALLTB-9,Y
TRN401
       STA    GRFPF0,X
       TSX
       LDA    MIPL
       STA    HHITP0+1,X
       STA    HITCLR
       LDA    HGRAP0,X
       BMI    TRN201
       STA    MOON1   ;HOLD
       LDA    HHITP0,X
       STA    HDELP0
       AND    #$0F 
       STA    MOON3  ;HOLD
       LDX    #<TRN430
       LDA    #SURCOL
       STA    WSYNC
       STA    ADDEL
       STX    VECTP0
       JMP.ind (VECTP1)
;
;
TRN430
; HPOSP0
       STA    WSYNC
       STA    ADDEL
       STA.w  COLBK    ;STA ABS COLBK (ORIG=DB $8D,COLBK,0)
       STX    GRAFP1
       LDX    #<TRN460
       LDA    MOON3
       LSR
       BCS    TRN431  ;DELAY
TRN431
       BEQ    TRN432
       DEY
TRN433
       SEC
       NOP
       SBC    #$01 
       BNE    TRN433
       STA    HPOSP0
TRN434
       LDA    #SURCOL
       STA    WSYNC
       STA    ADDEL
       STX    VECTP0
       JMP.ind (VECTP1)
TRN432
       STA    HPOSP0
       DEY
       JMP    TRN434
;
;
;
TRN460
; SETUP P0, 2ND LINE
       STA    WSYNC
       STA    ADDEL
       STA    COLBK
       STX    GRAFP1
       LDX    MOON1  ;HOLD
       LDA    PTABL4,X
       SEC
       BMI    TRN462   ;KEY
       STA    SIZPM0
       LDA    PTABL2,X
       SBC    VERTP0
       STA    MOON3
       LDA    PTABL1,X
       SBC    VERTP0 
       STA    MOON1
       LDA    PTABL3,X
       STA    MOON3+1
       SBC    #$00 
TRN463
;  52CY
       STA    MOON1+1
       DEY
       LDX    WALLTB-6,Y
       LDA    WALLTB-7,Y
       STA    GRFPF0,X
       STX    HDELP0  ;X=0,1,2
       LDA    #SURCOL
       LDX    #<TRN250  ;WARNING: NO WSYNC!!!!!
       STA    ADDEL
       STX    VECTP0
       JMP.ind (VECTP1)
;
TRN462
;  KEY
       LDA    #$20 
       STA    SIZPM0
       LDA    #<YPC1+7
       SBC    VERTP0
       STA    MOON3
       LDA    KEYTB1-$18,X
       SBC    VERTP0
       STA    MOON1
       LDA    #>YPL4
       STA    MOON3+1
       BNE    TRN463  ;JMP
;
;
;
; --- FRAGMENT: horizontal positioning for the surface P1 objects.  PLUMBING.
PLN740
; HPOSP1
       STA    COLBK
       LDA    #$00 
       STA    GRAFP1
       STX    VECTP1
       LDA    HOLDP1
       LSR
       BCS    PLN742   ;DELAY
PLN742
       BNE    PLN741
       STA    HPOSP1   ;CY 39-40
       DEY
       JMP    PLN746
PLN741
       DEY
       CMP    #$02 
       BCC    PLN743
       LDA    (STARS),Y
       NOP
       NOP
       NOP
       STA    HPOSP1  ;CY-57-58
PLN744
       AND    CROSP1
       BEQ    PLN745
       LDA    #SURCOL
PLN745
       LDX    #$00 
       JMP.ind (VECTP0)
PLN743
; CY 48-49
       STA.w  HPOSP1 ;STA ABS HPOSP1 (ORIG=DB $8D,HPOSP1,0)
PLN746
       LDA    (STARS),Y
       JMP    PLN744
;
;
;
;
;-------------------------------------------------------------------------------
; HYPER -- set up and run the HYPERWARP TUNNEL screen.
;
; WHAT IT DRAWS: your ship in the middle, a field of streaking stars, and a
; colour-cycling background.  The stars are the two photon slots, pulled down
; the screen by HYPSRV each frame; LINTB4 is the star bit pattern and CROSP1
; masks it.  ZDELP0-1 carries the background colour that SHPSRV computed.
;
; This screen is up while PROGST bit 4 is set, i.e. between committing a jump
; in JOYSTK and TIMSRV noticing the takeoff clock has reached $70.
;-------------------------------------------------------------------------------
HYPER
; SETUP HYPERSPACE
       LDA    ATRACT+1   ;SHIP COLOR
       STA    MISC2
       LDA    #>HYP730
       STA    VECTP1+1 
       LDA    #<HYP730
       STA    VECTP1
       LDA    #$70 
       STA    HDELM2
       LDA    #$50 
       STA    HDELM0
       STA    WSYNC
       STA    ADDEL
       LDA    #$00 
       STA    VDELM2
       STA    SIZPM1
       LDA    HCOLP1 
       STA    COLPM1
       LDA    #$30 
       STA    SIZPM0
       LDA    #$31 
       STA    PRIOR
       LDA    #<PLN580
       STA    PNTRP1 
       LDA    HHORP1 
       STA    HDELP1
       AND    #$0F 
       STA    HOLDP1
       LDA    #>SHP4
       STA    MISC1+1 
       STA    MISC2+1
       LDA    HGRAP1 
       STA    MISC1
       LDA    #>LINTB4
       STA    STARS+1
       LDA    #$10 
       STA    CROSP1
       STA    WSYNC
       STA    ADDEL
       LDA    #$02 
       STA    GRAFM2
       STA    GRAFM0
       LDA    #>HYP200
       STA    VECTP0+1
       LDA    #<HYP200
       STA    VECTP0
       LDA    #$10 
       STA    HDELM0
       LDA    #$F0 
       STA    HDELM2
       LDA    #<LINTB4  ;STAR PATTERN
       STA    STARS    ;DISP M1 STARS
       STA    HPOSM1
       LDA    #$80 
       STA    HDELM1
       LDA    ZDELP0-1
       STA    COLPF
       STA    COLPM0   ;A=COLOR
       LDX    #$00 
       LDY    #TOPSCN-$27  ;HOPEFULLY
       JMP    HYP256
;
;
;
; PLNTB4 / PLNTB2 / PLNTB1 / PLNTB3 / PLNTB5 / PLNTB6 -- per-scanline playfield
; patterns for the surface: the mountain silhouette, the ground texture and the
; trench walls.  Each is read a nibble at a time as the kernel walks down.
PLNTB4 .byte $F0,$F0,$B0,$90,$00,$00
;
;
;-------------------------------------------------------------------------------
; THE SURFACE SPRITE DATA.
;
; Same storage convention as bank 2 (header section 7b): stored BOTTOM ROW
; FIRST, so LABEL-1 is the TOP row and the leading $00 bytes terminate the
; object.  Naming is <letter>PL<size>, size 8 nearest:
;
;   RPL*  trench toweR     NPL*  miscellaneous     WPL*  the man (Walker)
;   PPL*  planet Pirate    CPL*  planet Craft      XPL*  eXplosion
;   FPL*  planet Fighter   LPL*  Landing zone      EPL*  Enemy photon
;   YPL*  Your ship on the surface   SHP1..SHP4  ship during takeoff
;   KEYTB1  the KEY graphic
;
; Colour ramps: NCL1/NCL2 (misc), RCL1 (tower), PCL1 (pirate), WCL1 (the man),
; XCL1 (explosion), CCL1 (craft), FCL1 (fighter), LCL1 (landing zone),
; ECL1 (photon), YPC1 and SHCL (your ship).
;-------------------------------------------------------------------------------
; PAGE 5 (MORE OR LESS)
;
; TRENCH TOWER
       .byte $00,$00,$24,$66,$FF,$18,$3C,$5E,$0F,$5E,$3C,$18
RPL8   .byte $00,$00,$24,$66,$FF,$18,$3C,$66,$DB,$66,$3C,$18
RPL7   .byte $00,$00,$24,$66,$FF,$18,$3C,$7A,$F8,$7A,$3C,$18
RPL6   .byte $00,$00,$24,$7E,$18,$3C,$0E,$0E,$3C,$18
RPL5   .byte $00,$00,$24,$7E,$18,$3C,$66,$66,$3C,$18
RPL4   .byte $00,$00,$24,$7E,$18,$3C,$70,$70,$3C,$18
RPL3   .byte $00,$00,$24,$3C,$18,$3C,$18
RPL2   .byte $00,$00,$18
RPL1
;  MISC GRAPHIC
       .byte $00,$00,$24,$66,$E7,$FF,$7E,$3C,$66,$42,$5A,$42
NPL8
NPL7
NPL6
       .byte $00,$00,$28,$6C,$FE,$7C,$38,$6C,$44,$54
NPL5
NPL4
NPL3
       .byte $00,$00,$10,$38,$38,$38,$28
NPL2
       .byte $00,$00,$10,$10
NPL1
;
;  MISC GRA COLORS
NCL1
       .byte $1A,$6A,$68,$66,$64,$8C,$8C,$8C,$8C,$1E
       .byte $1E,$4C,$4A,$48,$46,$8C,$8C,$1E,$1E,$8C
;
;
;ORG BANK4+$584   ;TEMPOARY *****
;
PLN198
;  P1 PHOTONS
       .byte $00,$00,$10,$38,$7C,$7C,$7C,$38,$10
       .byte $00,$00,$10,$38,$7C,$7C,$38,$10
       .byte $00,$00,$18
       .byte $3C,$3C,$3C,$18
       .byte $00,$00,$10,$38,$38,$10
       .byte $00,$00
       .byte $10
       .byte $38,$10
;
;  MISC GRA COLORS CONT.
NCL2
       .byte $1A,$8A,$88,$86,$84,$1E,$1E,$8C,$8C,$8C
;  TRN TWR COLOR
RCL1
       .byte $56,$58,$5A,$58,$5A,$5C,$5E,$5C,$5A,$58
;
PLNTB2 .byte $FF,$FF,$D7,$C3,$83,$81
;
;ORG BANK4+$5C1  ;TEMPOARY ********
;  YOUR SHIP GRAPHIC
; NORMAL
       .byte $00,$00,$08,$0C,$0E,$1E,$0C,$04
       .byte $00,$04,$00,$F1,$7F,$3F,$1F,$1F
       .byte $0E,$0E,$04,$04
; BANK RIGHT
       .byte $00,$00,$20,$30,$38,$78,$30,$10
       .byte $00,$1B,$00,$6F,$FE,$FC,$FC,$78
       .byte $38,$30,$10,$10
; BANK LEFT
       .byte $00,$00,$10,$18,$1C,$3C,$18,$08
       .byte $00,$D8,$00,$E4,$7F,$3F,$3F,$1E
       .byte $1C,$0C,$08,$08
 ORG $3600
 RORG BANK4+$600   ;TEMPOARY **********
;
;
;   MAN
       .byte $00,$00,$04,$04,$04,$2C,$38,$38,$08,$3C,$7E,$42,$5A
WPL8
       .byte $00,$00,$24,$24,$3C,$18,$08,$7E,$DB,$81,$18
WPL7
       .byte $00,$00,$20,$20,$20,$34,$1C,$5A,$42,$7E,$3C,$08,$18
WPL6
       .byte $00,$00,$08,$08,$28,$38,$10,$38,$7C,$54
WPL5
       .byte $00,$00,$28,$38,$10,$7C,$FE,$10
WPL4
       .byte $00,$00,$20,$20,$28,$38,$54,$7C,$38,$10
WPL3
       .byte $00,$00,$10,$10
WPL1
       .byte $10,$38,$10
WPL2
;
;  PLN PIRATE
       .byte $00,$00,$81,$C3,$66,$7E,$3C,$18,$18,$90,$F0,$60
PPL8
       .byte $00,$00,$81,$C3,$66,$7E,$3C,$18,$18,$3C,$3C,$18
PPL7
       .byte $00,$00,$81,$C3,$66,$7E,$3C,$18,$18,$09,$0F,$06
PPL6
       .byte $00,$00,$42,$66,$3C,$3C,$18,$50,$70,$20
PPL5
       .byte $00,$00,$42,$66,$3C,$3C,$18,$18,$3C,$18
PPL4
       .byte $00,$00,$42,$66,$3C,$3C,$18,$0A,$0E,$04
PPL3
       .byte $00,$00,$24,$3C,$18,$08,$04
PPL2
       .byte $00,$00,$18,$08
PPL1
;
;
;  PLN PIR COLORS
PCL1
       .byte $6A,$5A,$48,$46,$46,$46,$48,$4A,$4A,$4C
;  MAN COLORS
WCL1
       .byte $8A,$8A,$8A,$8A,$8A,$8A,$62,$18,$18,$18,$1C
       .byte $8A,$8A,$8A,$8A,$8A,$8A,$18,$18,$18,$62,$1C
       .byte $8A,$8A,$8A,$8A,$8A,$48,$18,$1C
       .byte $88,$88,$88,$46,$48
;
PLANT1 .byte $80,$8E,$80,$81
;
 ORG $36C6     
 RORG BANK4+$6C6    ;TEMPOARY  *******
; YOUR SHIP COLORS
       .byte $00,$00,$00
       .byte $00,$00,$00,$1D,$1B,$29,$26,$34
       .byte $34,$42,$42,$40
;
KEYTB1
       .byte <YPL4+U,<YPL4+U,<YPL4+U,<YPL3+U,<YPL3+U,<YPL3+U,<YPL2+U,<YPL1+U
;       .byte $DE,$DE,$DE,$E4,$E4,$E4,$E8,$EB
;
       .byte $00,$00,$00,$1C,$1A,$29,$26,$34
       .byte $34,$42,$42,$40
;
;
; SURTB1 -- the mountain-range profile, one byte per scanline.
SURTB1
       .byte $01,$02,$04,$08,$10,$20,$40
       .byte $80,$00,$00,$00,$1C,$1A,$29,$26,$34
       .byte $34,$42,$42,$40
;
;
 ORG $3700
 RORG BANK4+$700     ;TEMPOARY ********
;
; CRATER
       .byte $00,$00,$40,$88,$84,$82,$C6,$FE,$FC,$F8,$E0
CPL8   .byte $00,$00,$40,$90,$88,$CC,$F8,$F0,$C0
CPL7   .byte $00,$00,$30,$48,$F8,$F0,$C0
CPL6   .byte $00,$00,$3C,$42,$FF,$7E
CPL5   .byte $00,$00,$44,$FE,$7C
CPL4   .byte $00,$00,$6C,$3E
CPL3   .byte $00,$00,$68,$3C
CPL2   .byte $00,$00,$EF
CPL1
;
; EXPLOS GRAPHIC
       .byte $00,$00,$08,$04,$40,$02,$04,$10,$81,$02
       .byte $20,$04,$10,$40,$01,$04,$20,$08
XPL8
       .byte $00,$00,$10,$04,$20,$08,$02,$10,$04,$41
       .byte $04,$10,$04,$20,$04,$10
XPL7
       .byte $00,$00,$08,$04,$20,$0A,$18,$14,$4A,$10
       .byte $04,$24,$14,$28
XPL6
       .byte $00,$00,$08,$14,$08,$20,$14,$2A,$04,$10
       .byte $04,$10
XPL5
       .byte $00,$00,$08,$20,$42,$34,$98,$22,$44,$28
XPL4
       .byte $00,$00,$10,$44,$18,$28,$24,$10
XPL3
;
;
;  PLN FIGHTER
       .byte $00,$00,$81,$C3,$E7,$18,$3C,$18,$E7,$C3,$81
FPL8
FPL7
FPL6
       .byte $00,$00,$42,$66,$18,$18,$66,$42
FPL5
FPL4
FPL3
       .byte $00,$00,$24,$18,$24
FPL2
       .byte $00,$00,$18
FPL1
;
;
; EXPLOS COLOR
XCL1
       .byte $BC,$15,$1E,$F5,$BC,$15,$1E,$F5
       .byte $BC,$15,$1E,$F5,$BC,$15,$1E,$BC
;
       .byte $1E,$1E,$1E,$1E,$1E,$1E,$1E,$1E
;
; CRATER COLORS
CCL1
       .byte $C7,$60,$E7,$60,$07,$60,$27,$00,$47
       .byte $60,$60,$E7,$60,$27,$00,$47
       .byte $60,$60,$00,$00
;
;  FIGHTER COLOR
FCL1
       .byte $1A,$1A,$1A,$4E,$4E,$4E,$AC,$AC
       .byte $AC,$1A,$1A,$1A,$4E,$4E,$4E
;
;  KEY GRAPHIC
       .byte $00,$00,$05,$42,$A5,$BF,$A0,$40
YPL4
       .byte $00,$00,$0A,$24,$5E,$20
YPL3
       .byte $00,$00,$0C,$3C
YPL2
       .byte $00,$00,$18
YPL1
;  KEY COLOR
YPC1
       .byte $1C,$1C,$1C,$1C,$1C,$1C
;
;
;
;
; CHTAB7 -- background colour of the star chart, one per level.
; PTABL1 / PTABL2 / PTABL3 / PTABL4 -- the planet-surface texture and the
; planet-explosion animation tables.  PTABL4 is indexed as PTABL4-$E0,Y by the
; throttle during the blow-up sequence.
CHTAB7
;  CHART COLORS
       .byte $80,$30,$D6,$F0,$62,$B0,$06,$42
       .byte $50,$86,$70,$D0,$A0,$10,$A6,$00
;
PTABL1
;   CANT CROSS PAGE
; MOON1+0 GRAPHICS PNTR.
       .byte <FPL8+U,<FPL7+U,<FPL6+U,<FPL5+U,<FPL4+U,<FPL3+U,<FPL2+U,<FPL1+U
       .byte <PPL8+U,<PPL7+U,<PPL6+U,<PPL5+U,<PPL4+U,<PPL3+U,<PPL2+U,<PPL1+U
       .byte <NPL8+U,<NPL7+U,<NPL6+U,<NPL5+U,<NPL4+U,<NPL3+U,<NPL2+U,<NPL1+U
       .byte <WPL8+U,<WPL7+U,<WPL6+U,<WPL5+U,<WPL4+U,<WPL3+U,<WPL2+U,<WPL1+U
       .byte <LPL8+U,<LPL7+U,<LPL6+U,<LPL5+U,<LPL4+U,<LPL3+U,<LPL2+U,<LPL1+U
       .byte <RPL8+U,<RPL7+U,<RPL6+U,<RPL5+U,<RPL4+U,<RPL3+U,<RPL2+U,<RPL1+U
       .byte <EPL6+U,<EPL5+U,<EPL6+U,<EPL5+U,<EPL4+U,<EPL3+U,<EPL2+U,<EPL1+U
       .byte <XPL8+U,<XPL7+U,<XPL6+U,<XPL5+U,<XPL4+U,<XPL3+U,<XPL3+U,<XPL3+U
       .byte <CPL8+U,<CPL7+U,<CPL6+U,<CPL5+U,<CPL4+U,<CPL3+U,<CPL2+U,<CPL1+U
;
;
;
PTABL3 
       .byte $F7,$F7,$F7,$F7,$F7,$F7,$F7,$F7
       .byte $F6,$F6,$F6,$F6,$F6,$F6,$F6,$F6
       .byte $F5,$F5,$F5,$F5,$F5,$F5,$F5,$F5
       .byte $F6,$F6,$F6,$F6,$F6,$F6,$F6,$F6
       .byte $F8,$F8,$F8,$F8,$F8,$F8,$F8,$F8
       .byte $F5,$F5,$F5,$F5,$F5,$F5,$F5,$F5
       .byte $FC,$FC,$FC,$FC,$FC,$FC,$FC,$FC
       .byte $F7,$F7,$F7,$F7,$F7,$F7,$F7,$F7
       .byte $F7,$F7,$F7,$F7,$F7,$F7,$F7,$F7
;
;
;  LANDING ZONE
       .byte $00,$00,$FF,$81,$81,$81,$FF,$FF,$FF,$DB,$C3,$FF
LPL8   .byte $00,$00,$FE,$82,$82,$FE,$FE,$D6,$C6,$FE
LPL7   .byte $00,$00,$7E,$42,$42,$7E,$7E,$66,$7E
LPL6   .byte $00,$00,$7C,$44,$44,$7C,$6C,$7C
LPL5   .byte $00,$00,$FF,$81,$FF,$E7,$FF
LPL4   .byte $00,$00,$7E,$42,$7E,$7E
LPL3   .byte $00,$00,$3C,$24,$3C
LPL2   .byte $00,$00,$38,$38
LPL1
;
;
;
; LANDING COLORS
LCL1
       .byte $4C,$4A,$4A,$4A,$4E,$46,$48,$46,$46,$46
;
;
;
PTABL2
;  COLORS
; FIGHTER
;       .byte $D0,$D3,$D6,$CD,$D0,$D3,$CD,$D0
;       .byte $A0,$A0,$A0,$9F,$9F,$9F,$9E,$9C
;       .byte $7B,$85,$B2,$7A,$84,$B1,$82,$82
;       .byte $AB,$AB,$B6,$BE,$BE,$BE,$C3,$C3
;       .byte $D8,$D7,$D6,$D5,$D5,$D7,$D7,$D7
;       .byte $BC,$BC,$BC,$BC,$BC,$BC,$B7,$B6
;       .byte $00,$00,$ED,$EE,$ED,$EE,$ED,$EE
;       .byte $AB,$AB,$AB,$AB,$B3,$B3,$B3,$B3
;       .byte $BC,$C3,$BC,$C7,$C6,$C6,$C6,$C6
Z EQM <FCL1
       .byte Z+$A,Z+$D,Z+$10,Z+$7,Z+$A,Z+$D,Z+$7,Z+$A
; PLN PIR
Z EQM <PCL1
       .byte Z+$B,Z+$B,Z+$B,Z+$A,Z+$A,Z+$A,Z+$9,Z+$7
;  MISC GRAPHIC
Z EQM <NCL1
       .byte Z+$B,Z+$15,<NCL2+$B,Z+$A,Z+$14,<NCL2+$A,Z+$12,Z+$12
; MAN
Z EQM <WCL1
       .byte Z+$C,Z+$C,Z+$17,Z+$1F,Z+$1F,Z+$1F,Z+$24,Z+$24
; LAND ZONE
Z EQM <LCL1
       .byte Z+$B,Z+$A,Z+$9,Z+$8,Z+$8,Z+$A,Z+$A,Z+$A
; TRN TOWER
Z EQM <RCL1
       .byte Z+$B,Z+$B,Z+$B,Z+$B,Z+$B,Z+$B,Z+$6,Z+$5
; ENEMY PHOTON
Z EQM <ECL1
       .byte $00,$00,Z+$8,Z+$9,Z+$8,Z+$9,Z+$8,Z+$9
; EXPLOSION
Z EQM <XCL1
       .byte Z+$11,Z+$11,Z+$11,Z+$11,Z+$19,Z+$19,Z+$19,Z+$19
Z EQM <CCL1
       .byte Z+$A,Z+$11,Z+$A,Z+$15,Z+$14,Z+$14,Z+$14,Z+$14
;
;
PTABL4
;  SHARE WITH PLANET BLOWUP
;  CANT CROSS PAGE
       .byte $60,$60,$60,$20,$60,$20,$60,$20
       .byte $20,$60,$20,$20,$60,$20,$20,$20
       .byte $20,$60,$20,$20,$20,$20,$20,$60
       .byte $A0,$A0,$A0,$A0,$A0,$A0,$E0,$A0
       .byte $25,$25,$25,$25,$20,$20,$20,$20
       .byte $20,$20,$20,$20,$20,$20,$20,$20
       .byte $20,$20,$20,$20,$20,$20,$20,$20
       .byte $25,$25,$25,$25,$20,$20,$20,$20
       .byte $20,$20,$20,$25,$25,$25,$25,$20
;
;
;
; LINTB4 -- the hyperwarp star pattern, one byte per scanline.
LINTB4
;  CANT CROSS PAGE
       .byte $4E,$4F,$4E,$4E,$5E,$4E,$4E,$4E
       .byte $4F,$4E,$5C,$4E,$4D,$4E,$4C,$4D
       .byte $4C,$4C,$5D,$4C,$4C,$4C,$5C,$4D
       .byte $4A,$4C,$4A,$4D,$5A,$4A,$4A,$4A
       .byte $4A,$4A,$5A,$4A,$4B,$4A,$4A,$4A
       .byte $4A,$4B,$48,$4A,$48,$4A,$58,$4A
       .byte $48,$49,$48,$48,$58,$49,$48,$46
       .byte $58,$46,$48,$46,$56,$46,$47,$46
       .byte $54,$46,$45,$44,$54,$44,$44,$42
       .byte $42,$42,$42,$41,$40,$40,$40,$40
;
;
; HYPER SHIP GRAPHICS
       .byte $00,$00,$10,$18,$18,$38,$10,$00
       .byte $00,$00,$99,$FF,$7E,$3C,$3C,$18,$18,$18
SHP4
       .byte $00,$00,$18,$18,$18,$00
       .byte $00,$00,$5A,$7E,$3C,$18,$18,$18
SHP3
       .byte $00,$00,$18,$18,$18,$00
       .byte $00,$00,$24,$3C,$3C,$18
SHP2
       .byte $00,$00,$18,$18,$18,$00
       .byte $00,$00,$08
SHP1
; SHIP COLOR
       .byte $1E,$2C,$2A,$38,$36,$44,$42,$40
SHCL
;
;
;
;
; --- FRAGMENT: PLN140 / TRN140 -- the bottom-of-screen sections that draw the
;     ground texture (PTABL1..PTABL3) and, in the trench, the wall bases.
PLN140
; SETUP PLANET/TRENCH
       STA    WSYNC
       STA    ADDEL
       LDA    #$00 
       STA    GRAFM2
       STA    VDELM2
       STA    PRIOR
       STA    COLPF
       DEY
       LDA    PLINES 
       LSR
       LSR
       LSR
       AND    #$07 
       TAX
       LDA    SURTB1,X
       STA    CROSP1
       LDA    #<PLN350
       STA    PNTRP1 
       LDA    #>PLN198  ;TEMP, DEV.SYS.ONLY
       STA    MISC1+1
       LDA    #>PLN198+1
       STA    MISC2+1        ;  END TEMP
       LDX    IQPATH-1 
       STX    STARS 
       LDA    PROGST 
       AND    #$08 
       BEQ    TRN140
       STA    WSYNC
       STA    ADDEL
;  PLANET SETUP
       DEX
       DEX
       STX    MOON2
       LDA    XDELP0-1   ;MTNCOL
       STA    COLPF
       LDA    #>SURTB3
       STA    STARS+1
       STA    MOON2+1 
       LDA    #<PLN400
       STA    VECTP0
       LDA    #>PLN400
       STA    VECTP0+1
       LDA    #>PLN145
       STA    VECTP1+1 
       LDX    #<PLN145
PLN141
       STX    VECTP1
       LDA    ZDELP0-1   ;COLBK HOLD
       LDX    #$00 
       DEY
       JMP.ind (VECTP0)
PLN145
       LDX    #<PLN147
       JMP    PLN141
PLN147
       LDX    #<PLN100
       LDA    HCOLP1  ;PLANET COLOR
       LSR
       BIT    SHIPST 
       BVC    PLN141
;  BLOW PLANET
       BCS    PLN141
       LDA    ZDELP0-1
       STA    COLPF  ;TURN OFF MTNS
       LDA    #<PLN800
       STA    VECTP0
       LDA    RANDOM 
       STA    HPOSM0  ;FOR FUN
       AND    #$30 
       ADC    #$70 
       STA    HDELM0
       JMP    PLN141
;
;
TRN140
;  SETUP TRENCH
       STA    WSYNC
       STA    ADDEL
       LDA    #>SURTB5
       STA    STARS+1
       NOP
       NOP
       NOP
       NOP
       LDX    HOLDM0 
       LDA    HOLDM2 
       STA    HDELM2
       STX    HDELM0
       STA    WSYNC
       STA    ADDEL
       LDY    #$20 
       STY    SIZPM0
       AND    #$0F 
       LSR
       BCS    TRN144   ;DELAY
TRN144
       SEC
       NOP
       SBC    #$01 
       BPL    TRN144
       STA    HPOSM2
       STA    WSYNC
       STA    ADDEL
       JMP    TRN146   ;HUH?
;
;
;
; --- FRAGMENT: PLN100..PLN105 and TRN141..TRN146 -- the remaining surface
;     scanline blocks: the ground scroll, the landing-zone pad, and the
;     transition between the sky and ground colour regions.

PLN100
;  MOUNTAINS
       LDX    #$06 
PLN101
       LDA    PLNTB1-1,X
       STA    GRFPF0
       LDA    PLNTB2-1,X
       STA    GRFPF1
       LDA    PLNTB3-1,X
       STA    GRFPF2
       LDA    PLNTB4-1,X
       STA    GRFPF0
       LDA    PLNTB5-1,X
       DEY
       STA    GRFPF1
       LDA    PLNTB6-1,X
       STA    GRFPF2
       LDA    #$08 
       CPY    HVERP1 
       BEQ    PLN104
       LDA    #$00 
PLN104
       STA    GRAFP1
       DEX
       STA    WSYNC
       STA    ADDEL
       BNE    PLN101
; SETUP PLANET
;   X=0
       LDA    XDELP0-1 
       STA    COLBK
       STX    GRFPF0
       STX    GRFPF1
       STX    GRFPF2
       DEY
       LDA    #<PLN370
       BIT    SHIPST 
       BPL    PLN102
       LDA    #<PLN580
       STA    PNTRP1 
       CPY    HVERP1 
       BCC    PLN102
       BNE    PLN105
       LDX    #$08 
       BNE    PLN102   ;JMP
PLN105
       LDA    #>SHP4
       STA    MISC1+1 
       STA    MISC2+1
       LDA    ATRACT+1   ;SHIP COLOR 
       STA    MISC2
       LDA    #<HYP780
PLN102
       STA    VECTP1
       LDA    #>PLN370
       STA    VECTP1+1 
       LDA    #$00    ;COLBK
       JMP.ind (VECTP0)
;
;
TRN146
;  CONTINUE SETUP TRENCH
       TXA
       AND    #$0F 
       LSR
       BCS    TRN145   ;DELAY
TRN145
       SEC
       NOP
       SBC    #$01 
       BPL    TRN145
       STA    HPOSM0
       STA    WSYNC
       STA    ADDEL
       LDA    #>TRN400
       STA    VECTP0+1
       LDA    #>PLN370
       STA    VECTP1+1 
       LDA    #$FF 
       STA    GRFPF0
       STA    GRFPF1
       STA    GRFPF2
       LDA    #$00 
       STA    HDELM2
       STA    WSYNC
       STA    ADDEL
       LDA    #<PLN370
       BIT    SHIPST 
       BPL    TRN141
       LDA    #<PLN580
       STA    PNTRP1 
       LDA    #>SHP4
       STA    MISC1+1 
       STA    MISC2+1
       LDA    ATRACT+1 
       STA    MISC2    ;SHIP COLOR
       LDA    #<HYP780
TRN141
       STA    VECTP1
       LDA    #$31 
       STA    PRIOR
       LDY    #TRNTOP-6
       LDX    #$00 
       STX    HDELM0    ;X=0
       JMP    TRN400    ;ALL DONE TRN SETUP
;
;
;
;   WALLTB CANT CROSS PAGE
       .byte $00,$00,$00,$00,$00,$00
;
; WALLTB -- the trench wall profile, one byte per scanline.  Together with
; VWALL (which GRAPH derives from the man) this is the gap you have to fly
; through.
WALLTB
       .byte $00,$00,$10,$00
       .byte $10,$00,$30,$00,$30,$00,$70,$00
       .byte $70,$00,$00,$01,$00,$01,$80,$01
       .byte $80,$01,$C0,$01,$C0,$01,$E0,$01
       .byte $E0,$01,$F0,$01,$F0,$01,$F8,$01
       .byte $F8,$01,$FC,$01,$FC,$01,$FE,$01
       .byte $FE,$01,$00,$02,$00,$02,$01,$02
       .byte $01,$02,$03,$02,$03,$02,$07,$02
       .byte $07,$02,$0F,$02,$0F,$02,$1F,$02
       .byte $1F,$02,$3F,$02,$3F,$02,$7F,$02
;
       .byte $7F,$02,$FF,$02,$FF,$02,$FF,$02,$FF,$02
       .byte $7F,$02,$3F,$02,$1F,$02
;
       .byte $0F,$02,$07,$02,$03,$02,$01,$02
       .byte $FF,$01,$FE,$01,$FC,$01,$F8,$01
       .byte $F0,$01,$E0,$01,$C0,$01,$80,$01
       .byte $F0,$00,$70,$00,$30,$00,$10
;   SHARE 5
;
;
;-------------------------------------------------------------------------------
; MOVTB4..MOVTB7 -- THE MOTION TABLES.  All four are indexed by
; (packed delta AND $1F), i.e. by the 5-bit speed code:
;
;   MOVTB4[code]  what to ADD TO THE Z DELTA byte itself   (the accumulator)
;   MOVTB5[code]  what to ADD TO ZPOS                      (the whole steps)
;   MOVTB6[code]  what to ADD TO THE X or Y DELTA byte     (accumulator)
;   MOVTB7[code]  what to ADD TO the X or Y position       (whole steps)
;
; That pair-of-tables trick is how MOVER does fixed-point motion with no
; shifts and no unpacking: one lookup gives the fractional carry and one gives
; the integer step.  Z gets its own pair because it uses a different scale.
;
; Python equivalent for one axis:
;     obj.pos += velocity          # with velocity a float
; The tables exist only because the 6502 has no divide.
;-------------------------------------------------------------------------------
MOVTB5
       .byte $00,$00,$00,$00,$00,$00,$00,$00
       .byte $01,$01,$01,$01,$01,$01,$01,$01
       .byte $FE,$FE,$FE,$FE,$FE,$FE,$FE,$FE
       .byte $FF,$FF,$FF,$FF,$FF,$FF,$FF,$00
;
;
;
;
; TRNHLP -- shared setup for both surface kernels.  Stores the kernel object
; limit for CLOSE (PNTR3+1), sets the starfield pointer and the horizon
; scanline, and advances PLINES (how many scanlines of ground are drawn) by the
; throttle, so the ground appears to rush past faster at speed.
TRNHLP
       STX    PNTR3+1    ;FOR CLOSE
       STA    BOTSCN 
       LDA    #<STARTB-$71
       STA    STARS 
       LDA    #$3A 
       STA    HHORP1+3 
       LDA    IQWARP 
       CMP    #$80 
       ADC    PLINES 
       STA    PLINES 
       ASL
       RTS

;
; SURTB3 / SURTB4 / SURTB5 -- the ground and trench-wall playfield patterns.
; SURTB3 and SURTB4 are the planet surface at two detail levels; SURTB5 is the
; trench.  PLNSRV picks between them and stores the choice in IQPATH-1, which
; the kernel then uses as its pattern pointer.  The "CANT CROSS PAGE" warning
; is a timing constraint -- PLUMBING.
SURTB3
;  CANT CROSS PAGE
       .byte $FF,$FF,$FE,$FF,$FF,$FD,$FF,$FF
       .byte $FB,$FF,$FF,$F7,$FF,$FF,$EF,$FF
       .byte $DF,$FF,$FF,$BF,$FF,$7F,$FF,$FF
       .byte $FF,$FF,$FF,$FF,$FF,$FF,$FF,$FF
       .byte $FF,$FF,$FF,$FF,$FF,$FE,$FF,$FD
       .byte $FB,$F7,$FF,$EF,$DF,$BF,$7F,$FF
       .byte $FF,$FF,$FF,$FF,$FF,$FF,$FF,$FE
       .byte $FD,$F3,$EF,$DF,$3F,$FF,$FF,$FF
       .byte $FF,$FF,$FC,$F3,$CF,$3F,$FF,$FF
       .byte $FF,$FC,$F3,$8F,$7F,$FF,$FE,$E1
       .byte $1F,$FF,$FF
SURTB4
;  CANT CROSS PAGE
       .byte $FF,$FF,$FF,$FF,$FF,$FF,$FF,$FF
       .byte $FF,$FF,$FF,$FF,$FF,$FF,$FF,$FF
       .byte $FF,$FF,$FF,$FF,$FF,$FF,$FF,$FE
       .byte $FF,$FD,$FF,$FB,$FF,$F7,$FF,$EF
       .byte $DF,$FF,$BF,$FF,$7F,$FF,$FF,$FF
       .byte $FF,$FF,$FF,$FF,$FF,$FF,$FF,$FE
       .byte $FD,$FB,$F7,$EF,$DF,$BF,$7F,$FF
       .byte $FF,$FF,$FF,$FF,$FF,$FE,$F9,$F7
       .byte $CF,$3F,$FF,$FF,$FF,$FF,$FC,$E3
       .byte $9F,$7F,$FF,$FF,$FC,$C3,$3F,$FF
       .byte $FE,$E1,$1F,$FF
;
PLNTB3 .byte $DF,$8F,$0B,$01
;  SHARE 2
;
; ENEMY BULLETS
       .byte $00,$00,$08,$08,$1C,$3E,$1C,$08,$08
EPL6   .byte $00,$00,$36,$1C,$08,$1C,$36,$04
EPL5   .byte $00,$00,$08,$08,$1C,$08,$08
EPL4   .byte $00,$00,$14,$08,$14,$04
EPL3   .byte $00,$00,$08,$1C,$08
EPL2   .byte $00,$00,$08,$04
EPL1
;
;
;  ENEMY PHOTON COLOR
ECL1
       .byte $6E,$5E,$4E,$3E,$4E,$5E,$6E
;  SHARE 1
;
MOVTB4
       .byte $00,$20,$40,$60,$80,$A0,$C0,$E0
       .byte $00,$20,$40,$60,$80,$A0,$C0,$E0
       .byte $20,$40,$60,$80,$A0,$C0,$E0,$00
       .byte $20,$40,$60,$80,$A0,$C0,$E0,$00
;
PLNTB5 .byte $FF,$FF,$BB,$B1,$91,$10
;
;
SURTB5
;  CANT CROSS PAGE
       .byte $FF,$FF,$FE,$FF,$FD,$FF,$FF,$FF
       .byte $FB,$FF,$F7,$FF,$FF,$FF,$EF,$FF
       .byte $DF,$FF,$BF,$FF,$7F,$FF,$FF,$FE
       .byte $FF,$FD,$FF,$FB,$FF,$F7,$FF,$EF
       .byte $FF,$DF,$FF,$BF,$FE,$7F,$FD,$FF
       .byte $F3,$FF,$EF,$FF,$9F,$FF,$7F,$FE
       .byte $FF,$F9,$FF,$E7,$FF,$9F,$FE,$7F
       .byte $F1,$FF,$CF,$FF,$3F,$FE,$FF,$F1
       .byte $FF,$0F,$F0,$FF,$0F,$FF,$FF,$E0
       .byte $FC,$1F,$83,$FF,$7F,$C0,$E0,$3F
       .byte $FF,$FF
;   SHARE 2
;
PLNTB6 .byte $FF,$FF,$77,$67,$22,$20
;
MOVTB6
       .byte $00,$20,$40,$60,$80,$A0,$C0,$E0
       .byte $00,$80,$00,$80,$00,$00,$00,$00
       .byte $00,$00,$00,$80,$00,$80,$00,$80
       .byte $20,$40,$60,$80,$A0,$C0,$E0
;  SHARE 1
MOVTB7 .byte $00,$00,$00,$00,$00,$00,$00,$00
       .byte $01,$01,$02,$02,$03,$04,$05,$07
       .byte $F8,$FA,$FB,$FC,$FD,$FD,$FE,$FE
       .byte $FF,$FF,$FF,$FF,$FF,$FF,$FF
;  SHARE 1
;
; GRATB5 -- the animation phase source.  MOVER samples it twice per frame with
; different shifts of the frame counter to produce TEMP4, TEMP11 and TEMP13,
; the three phase values GRAPH hands to its animation handlers.  That is why
; all objects of a class animate in step.
GRATB5
      .byte $00,$01,$02,$11,$20,$21,$22,$11
;
;
;
;
;
;
;
;===============================================================================
; M O V E R  --  INTEGRATE EVERY OBJECT, ONCE PER FRAME
;
; The first thing the frame loop calls.  Three jobs:
;
; 1. FINISH VERTICAL BLANK: start the overscan timer, clear every TIA graphics
;    register, clear the collision latches.  PLUMBING.
;
; 2. RESEED THE PRNG.  Not an LFSR: it mixes the frame counter, the game clock,
;    the previous value, and a byte read straight out of ROM at $FE00,Y.  Any
;    reasonable PRNG substitutes in Python.
;
; 3. INTEGRATE.  For each of the five slots (X = 4 down to 0) and each of the
;    three axes, do:
;         code      = delta AND $1F
;         delta    += MOVTBn[code]        (the fractional accumulator)
;         position += MOVTBn+1[code]      (the whole-pixel step, plus carry)
;    with clamping: Z at $F1 (an object that reaches the camera is held rather
;    than wrapped) and Y at $F1 / $00 (so nothing wraps off the screen edges).
;
;    Surface mode takes the shorter MOVER3 path: no Z clamp, no P1+3 slot, and
;    a separate fix-up that keeps the planet photon on screen.
;
; If the star chart is up it goes to CHTSRV instead, which rebuilds the packed
; CHTBLK bitmap from CHTAB4.
;
; Python:
;     for o in objs[1:5]:
;         o.x += o.dx; o.y = clamp(o.y + o.dy); o.z = clamp(o.z + o.dz)
;===============================================================================
MOVER
; FINISH VBLANK STUFF
       LDA    #$2B    ;37 LINES #$30=40 VBLANK -- start the overscan timer, 37 lines of vertical blank
       STA    STIM64
       STA    RANDOM+1          ;DEFINE FOR HORIZ (IF IN CHART OR TAKEOFF)
       TYA
       INX  ;X=0
       STX    GRAFP0
       STX    GRAFM2
       STX    GRAFP1
       STX    GRAFP0
       STX    GRFPF0
       STX    GRFPF1
       STX    GRFPF2
       STX    GRAFM1
       STX    GCTLM1
       STX    BOTSCN  ;BOTSCN = where the picture ends
       STX    TEMP5    ;X=0 FOR VECT DOWN -- TEMP5 = the slot GRAPH should leave alone (none)
       STX    PNTR1   ; FOR TARNUM -- reset the scanner best-distance for GRAPH
       STA    HITCLR  ;clear the TIA collision latches for this frame
       INX   ;X=1
       STX    VDELM2
       STA    WSYNC
       STA    ADDEL
       STX    PRIOR
;  RNDNUM
       LDY    ATRACT 
       ADC    GAMTIM
       ADC    ATRACT 
       ADC    RANDOM 
       ADC    $FE00,Y   ;RANDOM CODE PAGE FE -- read a ROM byte at a frame-varying offset as extra entropy
       STA    RANDOM  ;the new PRNG value
       INC    RANDOM 
;  SETUP GRAPH
       TYA     ;ATRACT
       LSR
       TAX
       LSR
       LSR
       AND    #$07 
       TAY
       LDA    GRATB5,Y  ;GRATB5 sampled with one shift of the frame counter...
       STA    TEMP4 
       ASL
       ASL
       ASL
       ASL
       STA    TEMP13  ;...becomes the TEMP13 animation phase
       TXA
       AND    #$07 
       TAY
       LDA    GRATB5,Y  ;...and sampled with another shift becomes TEMP11
       STA    TEMP11
       LDA    #$56 
       STA    VWALL      ;DEFAULT -- VWALL default: no trench wall
       STA    CLRDEL        ;FOR STARS
       LDX    #$04 
       LDA    PROGST 
       AND    #$B3  ;on the chart, at game over or during a pause, skip the motion
       STX    VSYNC      ;OFF
       BNE    CHTSRV
; ---- X AXIS ----------------------------------------------------------------
MOVER1
;  HORIZ MOTION
       LDA    XDELP0-1,X
       AND    #$1F  ;the 5-bit speed code
       TAY
       CLC
       LDA    MOVTB6,Y  ;MOVTB6[code] = the fractional carry...
       ADC    XDELP0-1,X
       STA    XDELP0-1,X
       LDA    MOVTB7,Y  ;...and MOVTB7[code] = the whole-pixel step
       ADC    HHORP0-1,X
       STA    HHORP0-1,X
; ---- Z AXIS (uses its own table pair because the scale differs) ------------
; ZMOTION
       LDA    ZDELP0-1,X
       AND    #$1F 
       TAY
       CLC
       LDA    MOVTB4,Y  ;MOVTB4[code] = the Z fractional carry
       ADC    ZDELP0-1,X
       STA    ZDELP0-1,X
       LDA    MOVTB5,Y  ;MOVTB5[code] = the Z whole step
       ADC    ZPOSP0-1,X
       BIT    PROGST  ;V = surface mode, which skips the Z clamp
       BVS    MOVER3      ;PLN/TRN
       CMP    #$F1      ;Z=0 CHECK -- an object that reached the camera is HELD at $F1 rather than
       BCC    MOVER5      ;OK
       LDY    HGRAP0-1,X  ;wrapping, unless it is already off screen
       BPL    MOVER7     ;H,V OOPS!
MOVER5
;  VERT MOTION
       STA    ZPOSP0-1,X
; ---- Y AXIS ----------------------------------------------------------------
MOVER7
       LDA    YDELP0-1,X
       AND    #$1F 
       TAY
       CLC
       LDA    MOVTB6,Y
       ADC    YDELP0-1,X
       STA    YDELP0-1,X
       LDA    MOVTB7,Y
       ADC    HVERP0-1,X
       CMP    #$F1   ;MAX VERT CHECK -- clamp so nothing wraps off the top or the bottom
       BCC    MOVER2  ;OK
       LDA    #$00 
       LDY    HVERP0-1,X
       BPL    MOVER2
       LDA    #$F0 
MOVER2
       STA    HVERP0-1,X
       DEX  ;next slot, 4 down to 0
       BPL    MOVER1
MOVER4
       JMP    EXIT7    ;TO GRAPH
; Surface variant: no Z clamp, and the loop stops at slot 1 because P1+3 is not
; used on a surface.  The tail re-integrates the planet photon separately.
MOVER3
;  PLN/TRN
       STA    ZPOSP0-1,X
       DEX
       BNE    MOVER1  ;NO P1+3
;  PLANET PHOTON FIX
       LDA    YDELP0 
       AND    #$1F 
       TAY
       CLC
       LDA    MOVTB6,Y
       ADC    YDELP0 
       STA    YDELP0 
       LDA    MOVTB7,Y
       ADC    HVERP0+0 
       BPL    MOVE25
       TXA          ;X=0
MOVE25
       STA    HVERP0+0 
       JMP    EXIT7   ;TO GRAPH
;
;
;
; CHTSRV -- the star chart is up, so instead of moving objects, rebuild CHTBLK.
; CHTAB4 holds the sector-wall layout for each level, packed two bits per cell;
; this unpacks it into the 24-byte CHTBLK bitmap the chart kernel draws.
; MAZSTA bit 6 is the "chart needs redrawing" flag.
CHTSRV
; SETUP FOR CHART
       AND    #$20  ;PROGST bit 5 = chart
       BEQ    MOVER4 ;NOT CHART
       LDX    NEWLEV
       LDA    CHTAB7,X  ;CHTAB7[level] = the chart background colour
       STA    COLBK
       STA    HCOLP1 
       BIT    MAZSTA  ;bit 6 = the chart needs rebuilding
       BVC    CHTSR1
       LDA    MAZSTA 
       AND    #$BF 
       STA    MAZSTA 
       LDA    NEWLEV  ;three bytes of wall data per level
       ASL
       ADC    NEWLEV 
       ASL
       TAY
       LDX    #$17
       STX    PNTR1 
CHTSR2
       INC    PNTR1 
       BMI    CHTSR3
       LDA    #$FC 
       STA    PNTR1 
       LDA    CHTAB4,Y
       STA    PNTR1+1
       INY
CHTSR3
       LDA    #$00 
       ASL    PNTR1+1 
       BCC    CHTSR4
       LDA    #$C0 
CHTSR4
       ASL    PNTR1+1
       BCC    CHTSR5
       ORA    #$0C 
CHTSR5
       STA    CHTBLK,X
       DEX
       BPL    CHTSR2
CHTSR1
       JMP    EXIT6
;
;
;
CHTAB4
       .byte $CE,$90,$4C,$82,$5C,$67
       .byte $CD,$B6,$18,$E8,$2E,$23
       .byte $CB,$05,$56,$48,$0D,$A4
       .byte $8F,$16,$1E,$58,$38,$C0
       .byte $C1,$74,$1E,$0A,$BA,$C3
       .byte $02,$00,$52,$0A,$20,$84
       .byte $0B,$C0,$58,$32,$0F,$C1
       .byte $41,$A2,$0E,$19,$26,$03
       .byte $41,$26,$90,$58,$0E,$63
       .byte $C9,$24,$92,$49,$34,$04
       .byte $03,$E0,$A8,$AA,$2F,$84
       .byte $C7,$74,$80,$32,$6D,$C3
       .byte $41,$F0,$1E,$40,$0F,$A1
       .byte $01,$F4,$54,$51,$16,$C0
       .byte $C7,$D1,$16,$CF,$1F,$60
       .byte $09,$45,$92,$68,$9B,$06
;
;
;
;
;-------------------------------------------------------------------------------
; TRNSRV / PLNSRV -- per-frame SURFACE SETUP, called from the frame loop.
;
; PLNSRV first decides which surface we are on: PROGST bit 6 clear means we are
; in space and there is nothing to do; bit 3 selects planet (set) or trench
; (clear, so it branches to TRNSRV).
;
; Both then:
;   * pick the ground pattern (SURTB3/SURTB4 for a planet, SURTB5 for the
;     trench) and leave it in IQPATH-1 for the kernel
;   * call TRNHLP to set the horizon and advance the ground scroll
;   * choose the sky and ground colours.  PORTB bit 3 is the COLOUR/B-W switch,
;     and GAMEST bit 6 (your own planet) picks a friendlier sky.
;   * during a PLANET BLOW-UP (SHIPST bit 6) drive the flashing colours, the
;     rumble on channel 0 and the occasional explosion burst on channel 1
;
; YDELP0-1 is left holding the star probability and ZDELP0-1 the background
; colour, both of which the kernel reads.
;-------------------------------------------------------------------------------
TRNSRV
       STA    COLBK       ;A=0
       LDX    VWALL  ;VWALL is where the trench gap currently is
       DEX
       DEX    ;FIX CLOSE BUG -- the -2 is Doug fixing an off-by-one against CLOSE
       LDY    #<SURTB5+1  ;SURTB5 = the trench wall pattern
       LDA    #TRNTOP
       JSR    TRNHLP
       BMI    TRNSR2
       LDY    #<SURTB5
TRNSR2
       STY    IQPATH-1 
       LDA    CENTER  ;if the camera has drifted far from the trench centre...
       SBC    #$40 
       CMP    #$20 
       BCC    TRNSR3
       LDA    ZPOSP1+1 
       CMP    #$16  ;...and the far photon is close...
       BCC    TRNSR3
       LDA    #$80 
       STA    ZPOSP1+1  ;...switch the photon off (it would have hit a wall)
TRNSR3
       RTS
;
;
PLNSRV
       BIT    PROGST  ;V = surface mode; clear means we are in space
       BVC    PLNSR1
       LDA    PROGST 
       AND    #$08  ;PROGST bit 3: set = planet, clear = trench
       BEQ    TRNSRV
       LDY    #<SURTB4  ;SURTB4 / SURTB3 = the two planet ground patterns
       LDX    #$56    ;FOR CLOSE
       LDA    #MTNTOP
       JSR    TRNHLP
       BMI    PLNSR3
       LDY    #<SURTB3
PLNSR3
       STY    IQPATH-1  ;hand the chosen pattern to the kernel
       LDX    #$02 
       LDA    PORTB  ;PORTB bit 3 = the console COLOUR / BLACK-AND-WHITE switch
       AND    #$08 
       BEQ    PLNSR5   ;B/W
       LDX    #$00 
       LDA    #SKYCOL
       BIT    GAMEST  ;GAMEST bit 6 = your own planet, which gets the friendly sky
       BVS    PLNSR5
       LDA    #$50 
PLNSR5
       STX    XDELP0-1   ;MTNCOL -- mountain colour for the kernel
       LDX    ONESHT      ;STARS END?
       CPX    #$99  ;ONESHT $99 = the stars-end state, which recolours everything
       BNE    PLNSR9
       LDA    RANDOM 
       AND    #$76 
       ORA    #$40 
PLNSR9
       STA    COLBK  ;the sky colour
       STA    ZDELP0-1
       LDA    ATRACT 
       AND    #$03 
       TAY
       LDX    PLANT1,Y  ;PLANT1 cycles the planet colour on the frame counter
       LDA    #$C0 
       BIT    SHIPST  ;SHIPST bit 6 = this planet is blowing up
       BVC    PLNSR1
;  BLOWUP PLANET
       BMI    PLNSR2    ;TAKEOFF -- bit 7 = a takeoff is in progress, which wins
       LDY    IQWARP 
       BPL    PLNSR2
       LDA    ATRACT 
       LSR
       AND    #$02 
       ADC    #$40  ;flash between two colours as it goes
       TAX
       LDA    ATRACT 
       AND    #$07 
       BNE    PLNSR6
       LDA    PTABL4-$E0,Y  ;PTABL4[throttle] paces the explosion bursts
       ASL
       BPL    PLNSR6
       LDA    #AUDEX6-J  ;an occasional loud burst on channel 1
       STA    CH1PTR 
PLNSR6
       LDA    #AUDEXP-J  ;and a constant rumble queued on channel 0
       STA    CH0SHD   ;RUMBLE?
       TYA
       ASL
PLNSR2
       STX    HCOLP1   ;PLANET COLOR -- HCOLP1 = the planet colour the kernel will use
       STA    YDELP0-1  ;STAR PROB -- YDELP0-1 = the star probability for this frame
PLNSR1
       RTS
;
;
;
;
;
;-------------------------------------------------------------------------------
; BANK 4 EXIT TRAMPOLINES.  PLUMBING -- see header section 8.
; PON4 is the entry the other banks call to run MOVER.  As elsewhere, small
; tables (PLNTB1) are wedged into the gaps between the stubs, and the closing
; "DOUG N" plus the two reset vectors are the cartridge footer -- bank 4 is the
; one that is mapped in at power-on, so its vectors are the ones the 6502
; actually fetches.
;-------------------------------------------------------------------------------

;   BANK SELECT CODE
       .byte $FF
 ORG $3FD2
 RORG BANK4+$FD2
PON4
       STA    STROB3 ;JMP DFD5
       JMP    MOVER
EXIT7
       STA    STROB1 ;JMP DFDB
PLNTB1
       .byte $F0,$F0,$80,$80,$80,$00
       TYA
       BNE    PLN199
EXIT8
       STA    STROB3 ;JMP DFE7
       JSR    PLNSRV
       STA    STROB1 ;JMP DFF0
EXIT6
       STA    STROB3 ;JMP DFF0
       JMP    HYPER
PLN199
       JMP    PLN140
       .byte "DOUG N"
       .word PON4
       .word PON4
;
;
; **********************
;  END INCLUDE BANK4.SRC
; **********************
;
 END
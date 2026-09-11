"""The game's entire state: 128 bytes of zero page, addressed the way the ROM does.

Why a byte array instead of named attributes
--------------------------------------------
Solaris uses essentially all 128 bytes of the 2600's RAM, and it overlaps them
deliberately in ways the game logic *depends on*:

  * `STARS+1` and `NEWAVE` are the same byte ($C9).  The display kernel parks a
    horizontal position there; MAIN2 recomputes the difficulty tier over the top
    of it every frame, before anything reads it.
  * `HGRAP1+3` ($A4) is the byte the `-1,X` object loops reach when X = 0.  It is
    not a scratch pad -- it is the shared extra object slot (Saturn rings, a big
    moon, or the hyperwarp graphic), and MOVER integrating "slot 0" is exactly
    how that object moves.
  * `MAZSTA` must sit immediately after `JMPCNT` because FINDV indexes across
    the pair, and its low six bits ARE two fleets' step counters while its top
    two bits are the negative-universe and redraw flags.
  * `CHTBLK` overlays the per-object velocity arrays: on the star chart those 24
    bytes are the sector bitmap, everywhere else they are XDELP0/YDELP0/ZDELP0.
  * `HHITP0` holds a collision X from GRAPH for the first half of the frame, and
    then the display kernel overwrites it with TIA collision latches.
  * `IQREAP` doubles as the hyperwarp target number; `IQPATH-1` ($C3) carries the
    hyperwarp jump quality from SHPSRV to TIMSRV; `EXPNTR` doubles as the chart
    auto-repeat timer.

Un-aliasing all of that into separate attributes would be a rewrite, not a port,
and every one of those overlaps would become a subtle behaviour change.  So the
port keeps one 256-byte array and addresses it by the same constants the
assembly uses.  `m[HGRAP0 - 1 + x]` reads as `LDA HGRAP0-1,X`, which makes the
Python checkable line-by-line against the disassembly.

Screen coordinate note
----------------------
`HVERP0`/`HVERP1` count UP from the BOTTOM of the screen; `TOPSCN` ($99) is the
top.  Only the renderer flips that, at the very last moment.
"""

# --- zero page, from the `ORG $80` map at solaris_annotated.asm:440-558 ------
MAZRAM = 0x80   # 8 bytes: fleet-presence bits.  bit 7 of MAZRAM+0 also means
                # "a friendly planet still exists"
CURSOR = 0x88   # your cell on the chart, 0..$2F (6 wide x 8 tall)
JMPCNT = 0x89   # fleets 0 and 2 step counters (bits 0-2 and 3-5)
MAZSTA = 0x8A   # MUST FOLLOW JMPCNT.  fleets 1 and 3; bit 6 redraw, bit 7 negative universe
RANDOM = 0x8B   # 2 bytes of PRNG state
PROGST = 0x8D   # the game mode bits (see PROGST_* below)
HCOLP1 = 0x8E   # +0 ship/flame colour, +1 takeoff/hyperwarp animation clock
JMPTIM = 0x90   # BCD countdown to the next enemy fleet move
NEWLEV = 0x91   # current level 0..$0F
NOCLER = 0x91   # a warm start clears from here up
PNTR1 = 0x92    # PNTR1..PNTR6: six 16-bit scratch pointers, aliased below
PNTR2 = 0x94
PNTR3 = 0x96
PNTR4 = 0x98
PNTR5 = 0x9A
PNTR6 = 0x9C
ATRACT = 0x9E   # 2-byte free-running frame counter and master phase clock
ONESHT = 0xA0   # edge latches and the damage counter (see ONESHT_* below)

HGRAP1 = 0xA1   # object TYPE: +0 your ship, +1 near photon, +2 far photon,
                # +3 the shared extra slot (== the HGRAP0-1 "pad" byte)
HGRAP0 = 0xA5   # object TYPE for the four enemy/scenery slots
IQREAP = 0xA9   # spawn-VM loop counter; also the hyperwarp target number
HHORP1 = 0xAA   # object X for the player group
HHORP0 = 0xAE   # object X for the four enemy slots, 0..$9F
PLINES = 0xB2   # scanlines of planet surface currently drawn
HVERP1 = 0xB3   # object Y, player group.  HVERP1+0 == 0 means YOU ARE DEAD
HVERP0 = 0xB7   # object Y, enemy slots.  Bottom of screen is 0, Y counts UP
VWALL = 0xBB    # trench wall position (surface only), default $56
ZPOSP1 = 0xBC   # photon Z.  bit 7 set = that photon is switched off
ZPOSP0 = 0xBF   # object Z.  0 = at the camera, ZVIS = the far cutoff
IQPATH = 0xC4   # low nibble = flight path, high nibble = phase counter.
                # IQPATH-1 ($C3) carries the hyperwarp jump quality.

STARS = 0xC8    # starfield table pointer.  STARS+1 IS NEWAVE
NEWAVE = 0xC9   # difficulty tier 0..7, recomputed every frame in MAIN2
REQUST = 0xCA   # pending swap request from CLOSE, consumed by BRAIN
BOTSCN = 0xCB   # scanline at which the picture ends
HHORM2 = 0xCC   # starfield X (missile 2), scrolls as you steer
NEWATT = 0xCD   # attack state: low 3 bits the inbound fleet, bits 6/7 a
                # friendly planet is under attack
PAUTIM = 0xCE   # freeze timer; non-zero means an explosion is playing
CENTER = 0xCF   # THE CAMERA X, clamped $2D..$74 by JOYSTK
IQPNTR = 0xD0   # spawn-VM program counter (an offset into TYPTAB)
IQSTAK = 0xD1   # the VM's one-deep call stack; 0 means empty
IQWARP = 0xD2   # THROTTLE, signed.  $80..$FF is forward thrust, $FF fastest
SHIPST = 0xD3   # ship state machine (see SHIPST_* below)
HOLDM2 = 0xD4   # scratch: a pixel X for horizontal positioning
HOLDM0 = 0xD5   # scratch: a zoom byte handed from HYPSRV to SHPSRV
GAMTIM = 0xD6   # elapsed strategic time, paces the enemy fleets
LSTCUR = 0xD7   # previous chart cursor; bit 7 = the cell we left was occupied
GAMEST = 0xD8   # mission state bits (see GAMEST_* below)
LIVES = 0xD9
TARNUM = 0xDA   # the slot the scanner is locked onto
FUEL = 0xDB     # 0..$FF
SCORE = 0xDC    # 3 bytes of packed BCD, little-endian
CH0PTR = 0xDF   # sound channel program counters (offsets into AUDTAB)
CH1PTR = 0xE0
CH0SHD = 0xE1   # the queued follow-up sound per channel: the whole priority scheme
CH1SHD = 0xE2
EXPNTR = 0xE3   # explosion script pointer; doubles as the chart auto-repeat timer

CHTBLK = 0xE4   # 24 bytes: the packed chart bitmap, overlaying everything below
VECTP1 = 0xE4   # kernel: next P1 fragment
PNTRP1 = 0xE6   # kernel: saved fragment pointer / the planet kernel's object count
XDELP0 = 0xE8   # packed horizontal velocity, one per slot
YDELP0 = 0xED   # packed vertical velocity
ZDELP0 = 0xF2   # packed depth velocity == closing speed
VELOC = 0xF6    # your ship's lateral speed, signed, clamped $E0..$1F
HPOSL = 0xF7    # sub-pixel accumulator for the ship's lateral motion
HHITP0 = 0xF8   # collision X from GRAPH, then TIA collision latches from the kernel
STAK1 = 0xFC    # scratch that deliberately lives inside the 6502 stack page
STAK2 = 0xFD
STAK3 = 0xFE
STAK4 = 0xFF

# --- vertical-blank aliases (assembly lines 731-743) ------------------------
# The same bytes under the names the "thinking" half of the frame uses.
TEMP4 = PNTR5 + 0    # zoomed Z
TEMP5 = PNTR2 + 1    # |ZDEL|, or a min/max bound, or a hit tolerance
TEMP6 = PNTR1 + 0
TEMP7 = PNTR1 + 1    # the per-path SPEED LIMIT
TEMP9 = PNTR4 + 0
TEMP10 = PNTR4 + 1   # the PACKED RESULT of PREHLP/ZHELP
TEMP11 = PNTR2 + 0   # the sign flag, $00 or $FF, used as an EOR mask
TEMP12 = PNTR3 + 0
TEMP13 = PNTR3 + 1   # the path index / animation phase
JOYRMH = PNTR6 + 0   # this frame's world drift from your steering, horizontal
JOYRMV = PNTR6 + 1   # ... and vertical
THGRP1 = PNTR5 + 1   # ship graphic: 0 level, 1 banking right, 2 banking left

# --- display-kernel aliases (assembly lines 757-766) ------------------------
VECTP0 = PNTR1
HOLDP1 = PNTR2 + 0
CROSP1 = PNTR2 + 1
VERTP0 = PNTR3 + 0
VERTP1 = PNTR3 + 1
MISC1 = PNTR4
MOON2 = PNTR5
MOON1 = PNTR6
MOON3 = STAK1
MISC2 = STAK3

# --- game constants (assembly lines 689-706) --------------------------------
NUMCOL = 3 + 4
K = 8              # chart index of your home planet
U = 1
TOPSCN = 0x99      # the top scanline of the play area
SCNSIZ = TOPSCN + 39
MTNTOP = 0x62      # Y of the mountain horizon on a planet
TRNTOP = 0x62      # Y of the top of the trench walls
VSHIP = 0x1D       # your ship's resting Y; it never moves vertically in space
ZVIS = 0x78        # far visibility cutoff: ZPOS >= ZVIS is not drawn
PBLK = 0xE0        # THE EMPTY-SLOT SENTINEL ($60 class + $80 off-screen bit)
POFF = 0xA8        # past this, an off-screen object is retired entirely
SCLR = 0xF2        # star colour
VCENT = 0x53       # the vertical vanishing point objects converge on
SKYCOL = 0x70
SURCOL = 0x62
TRNCOL = 0x84

# --- PROGST bits (assembly header section 5) --------------------------------
PROGST_PROTECT = 0x01   # screen-protect / attract dimming
PROGST_FROZEN = 0x02    # "an event just ended": the world is frozen until fire
PROGST_PLANET = 0x08    # with bit 6 set: 0 = trench, 1 = planet
PROGST_HYPER = 0x10     # the hyperwarp tunnel screen is up
PROGST_CHART = 0x20     # the star chart is up
PROGST_SURFACE = 0x40   # on a planet or in the trench.  == $40 exactly is TRENCH
PROGST_OVER = 0x80      # game over / power-up / attract
PROGST_POWERUP = 0xCE   # the value INIT uses at power-up
PROGST_GAMEOVER = 0xCA
PROGST_NEWGAME = 0x4E   # the value TIMSRV uses when Game Reset restarts

# --- GAMEST bits ------------------------------------------------------------
GAMEST_DOOR = 0x01      # trench door: 1 = closed, hitting the wall kills you
GAMEST_QUALITY = 0x03   # hyperwarp jump quality 0..3, written by TIMSRV
GAMEST_THROTTLE = 0x1C  # (GAMEST & $1C) >> 2 is the throttle acceleration step
GAMEST_CHARTOK = 0x20   # one-shot: the wave script has finished, open the chart
GAMEST_FRIENDLY = 0x40  # this is YOUR planet
GAMEST_WANDER = 0x80    # newly spawned objects wander

# --- SHIPST bits ------------------------------------------------------------
SHIPST_EMPTY = 0x01     # this sector is now clear
SHIPST_FROMPLANET = 0x10
SHIPST_QUEUED = 0x20    # a hyperwarp is armed
SHIPST_JUMPAGAIN = 0x30 # a wormhole: jump straight back out again
SHIPST_BLOWUP = 0x40    # the planet is blowing up
SHIPST_TAKEOFF = 0x80   # the takeoff animation is running

# --- ONESHT bits ------------------------------------------------------------
ONESHT_CHART = 0x01     # star-chart toggle edge latch
ONESHT_RESTART = 0x02   # fire was pressed at game over
ONESHT_FUELALT = 0x04   # alternates, so only every OTHER shot costs fuel
ONESHT_DAMAGE = 0x70    # three hits accumulate here; the fourth is fatal
ONESHT_FIRE = 0x80      # fire-button release latch, so holding does not autofire

# --- object slot indices ----------------------------------------------------
# Almost every loop walks the object arrays as FIELD-1,X with X in 0..4:
#   X = 0        the SHARED EXTRA SLOT (HGRAP1+3): Saturn rings, a big moon or
#                the hyperwarp graphic.  It is the byte between the P1 and P0
#                groups, so the -1,X convention reaches it for free.
#   X = 1..4     the four enemy / scenery slots, kept sorted by screen Y
SLOT_SHARED = 0
SLOTS = (1, 2, 3, 4)

# Player group indices into HGRAP1 / HHORP1 / HVERP1.
P1_SHIP = 0
P1_PHOTON_NEAR = 1
P1_PHOTON_FAR = 2
P1_SHARED = 3


class Mem:
    """The 2600's RAM, plus the handful of TIA registers the game reads back.

    Indexing is by the assembly's own address constants, so ported routines read
    almost literally: `m[HGRAP0 - 1 + x]` is `LDA HGRAP0-1,X`.
    """

    __slots__ = ("ram",)

    def __init__(self):
        self.ram = bytearray(0x100)

    def __getitem__(self, addr):
        return self.ram[addr & 0xFF]

    def __setitem__(self, addr, value):
        self.ram[addr & 0xFF] = value & 0xFF

    def word(self, addr):
        """A little-endian 16-bit read, for the 2-byte counters."""
        return self.ram[addr & 0xFF] | (self.ram[(addr + 1) & 0xFF] << 8)

    def set_word(self, addr, value):
        self.ram[addr & 0xFF] = value & 0xFF
        self.ram[(addr + 1) & 0xFF] = (value >> 8) & 0xFF

    def clear_from(self, start):
        """`LDX #start / STA VSYNC,X / INX / BNE` -- the ROM's clear-everything
        idiom, which sweeps from `start` to $FF.  A cold start passes 0 (which
        also walks the TIA registers); a warm start passes NOCLER."""
        for a in range(start, 0x100):
            self.ram[a] = 0

    def inc(self, addr):
        """INC, returning the new value so callers can branch on zero."""
        v = (self.ram[addr & 0xFF] + 1) & 0xFF
        self.ram[addr & 0xFF] = v
        return v

    def dec(self, addr):
        v = (self.ram[addr & 0xFF] - 1) & 0xFF
        self.ram[addr & 0xFF] = v
        return v

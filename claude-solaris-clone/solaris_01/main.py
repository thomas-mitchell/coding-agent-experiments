"""Solaris (Atari 2600, 1986) -- run the clone.

    python main.py                 play
    python main.py --scale 2       a bigger window
    python main.py --mute          no sound
    python main.py --headless --frames 3600
    python main.py --headless --frames 300 --screenshot shot.png
"""

import argparse
import sys

from solaris import romdata as rom
from solaris.game import Game
from solaris.render.frame import HEIGHT, WIDTH
from solaris.tia import Sound, rgb

# A TIA pixel is about twice as wide as it is tall, so the picture is stretched
# 6:3 to land on the 4:3 frame the game had on a television.
PIXEL_W = 6
PIXEL_H = 3

CONTROLS = """\
  arrows / WASD   steer and throttle      space   fire
  tab             star chart              F1      game reset
  F3              colour / black-and-white
  escape          quit
"""


def parse_args(argv):
    p = argparse.ArgumentParser(description=__doc__,
                                formatter_class=argparse.RawDescriptionHelpFormatter)
    p.add_argument("--scale", type=int, default=1,
                   help="multiply the window size (default 1, i.e. 960x720)")
    p.add_argument("--mute", action="store_true", help="disable sound")
    p.add_argument("--headless", action="store_true",
                   help="run without a window, for testing")
    p.add_argument("--frames", type=int, default=0,
                   help="stop after this many frames")
    p.add_argument("--screenshot", metavar="PATH",
                   help="write the last frame as a PNG and exit")
    p.add_argument("--debug", action="store_true",
                   help="print the game state each second")
    return p.parse_args(argv)


def main(argv=None):
    args = parse_args(argv or sys.argv[1:])
    game = Game()
    if args.headless:
        return run_headless(game, args)
    return run_windowed(game, args)


def run_headless(game, args):
    frames = args.frames or 600
    for _ in range(frames):
        game.step()
    print(f"{frames} frames, no errors")
    if args.debug:
        print(state_line(game))
    if args.screenshot:
        save_png(game.frame, args.screenshot)
        print(f"wrote {args.screenshot}")
    return 0


def run_windowed(game, args):
    import pygame

    pygame.init()
    width = WIDTH * PIXEL_W * args.scale
    height = HEIGHT * PIXEL_H * args.scale
    screen = pygame.display.set_mode((width, height))
    pygame.display.set_caption("Solaris")
    clock = pygame.time.Clock()
    print(CONTROLS)

    sound = None
    if not args.mute:
        sound = attach_sound(pygame, game)

    surface = make_surface(pygame)

    running = True
    frames = 0
    while running:
        for event in pygame.event.get():
            if event.type == pygame.QUIT:
                running = False
            elif event.type == pygame.KEYDOWN and event.key == pygame.K_ESCAPE:
                running = False
        read_input(pygame, game.mach)

        game.step()
        blit(surface, game.frame)
        # scale first (nearest-neighbour, so the pixels stay hard edged), then
        # let the blit convert the 8-bit picture to the display's format
        screen.blit(pygame.transform.scale(surface, (width, height)), (0, 0))
        pygame.display.flip()
        if sound is not None:
            push_sound(pygame, sound, game.mach)

        frames += 1
        if args.debug and frames % 60 == 0:
            print(state_line(game))
        if args.frames and frames >= args.frames:
            running = False
        clock.tick(60)

    pygame.quit()
    return 0


def read_input(pygame, mach):
    keys = pygame.key.get_pressed()
    mach.set_joystick(
        up=keys[pygame.K_UP] or keys[pygame.K_w],
        down=keys[pygame.K_DOWN] or keys[pygame.K_s],
        left=keys[pygame.K_LEFT] or keys[pygame.K_a],
        right=keys[pygame.K_RIGHT] or keys[pygame.K_d],
    )
    mach.set_fire(keys[pygame.K_SPACE])
    mach.set_chart_button(keys[pygame.K_TAB])
    mach.set_reset_switch(keys[pygame.K_F1])
    # PORTB bit 3 is the colour / black-and-white switch, which the surface
    # kernel reads.  Hold F3 for black and white.
    if keys[pygame.K_F3]:
        mach.portb &= ~0x08
    else:
        mach.portb |= 0x08


# A TIA colour byte is hue<<4 | luminance<<1, so bit 0 is unused and there are
# only 128 distinct colours -- which fits an 8-bit indexed surface exactly.
# Writing the framebuffer straight into that surface's buffer is one memcpy
# instead of 30720 per-pixel writes.
INDEX_TABLE = bytes((c & 0xFE) >> 1 for c in range(256))


def make_surface(pygame):
    surface = pygame.Surface((WIDTH, HEIGHT), depth=8)
    surface.set_palette([((rgb(i * 2) >> 16) & 0xFF,
                          (rgb(i * 2) >> 8) & 0xFF,
                          rgb(i * 2) & 0xFF) for i in range(128)] + [(0, 0, 0)] * 128)
    return surface


def blit(surface, frame):
    surface.get_buffer().write(bytes(frame.px).translate(INDEX_TABLE))


def attach_sound(pygame, game):
    try:
        pygame.mixer.pre_init(frequency=31400, size=-16, channels=1, buffer=1024)
        pygame.mixer.init()
    except pygame.error:
        print("sound unavailable; continuing muted")
        return None
    game.mach.audio = Sound(sample_rate=31400)
    return game.mach.audio


def push_sound(pygame, sound, mach):
    import array
    samples = sound.render(31400 // 60)
    pcm = array.array("h", (int(max(-1.0, min(1.0, s)) * 20000) for s in samples))
    try:
        pygame.mixer.Sound(buffer=pcm.tobytes()).play()
    except pygame.error:
        pass


def state_line(game):
    from solaris import state as st
    m = game.mach.m
    objs = " ".join(f"{m[st.HGRAP0 + i]:02X}@{m[st.HHORP0 + i]:02X},"
                    f"{m[st.HVERP0 + i]:02X},z{m[st.ZPOSP0 + i]:02X}"
                    for i in range(4))
    return (f"f{game.mach.frame_count:6d} "
            f"PROGST {m[st.PROGST]:02X} GAMEST {m[st.GAMEST]:02X} "
            f"SHIPST {m[st.SHIPST]:02X} lives {m[st.LIVES]} "
            f"fuel {m[st.FUEL]:02X} warp {m[st.IQWARP]:02X} "
            f"centre {m[st.CENTER]:02X} lev {m[st.NEWLEV]} wave {m[st.NEWAVE]} "
            f"| {objs}")


def save_png(frame, path):
    """A minimal PNG writer, so a screenshot needs no extra dependency."""
    import struct
    import zlib

    raw = bytearray()
    for y in range(HEIGHT):
        raw.append(0)                       # filter type 0
        for _ in range(PIXEL_H):
            pass
        for x in range(WIDTH):
            colour = rgb(frame.px[y * WIDTH + x])
            pixel = bytes(((colour >> 16) & 0xFF, (colour >> 8) & 0xFF, colour & 0xFF))
            raw.extend(pixel * PIXEL_W)
    # repeat each row PIXEL_H times, rebuilding the filter bytes
    rows = []
    stride = 1 + WIDTH * PIXEL_W * 3
    for y in range(HEIGHT):
        row = bytes(raw[y * stride:(y + 1) * stride])
        rows.extend([row] * PIXEL_H)
    data = zlib.compress(b"".join(rows), 9)

    def chunk(tag, payload):
        return (struct.pack(">I", len(payload)) + tag + payload
                + struct.pack(">I", zlib.crc32(tag + payload) & 0xFFFFFFFF))

    header = struct.pack(">IIBBBBB", WIDTH * PIXEL_W, HEIGHT * PIXEL_H, 8, 2, 0, 0, 0)
    with open(path, "wb") as f:
        f.write(b"\x89PNG\r\n\x1a\n")
        f.write(chunk(b"IHDR", header))
        f.write(chunk(b"IDAT", data))
        f.write(chunk(b"IEND", b""))


if __name__ == "__main__":
    sys.exit(main())

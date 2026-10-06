"""Print generated ships as text, without opening a window.

    python -m ship.debug --seed 1        # draw one ship and list its rooms
    python -m ship.debug --sweep 100     # generate seeds 0..99 and report
"""

from __future__ import annotations

import argparse
from collections import Counter

from . import tiles as T
from .pipeline import GenerationError, generate_ship


def render_ascii(ship) -> str:
    rows = []
    for y in range(ship.height):
        row = [T.ASCII[ship.tiles[x, y]] for x in range(ship.width)]
        if y == ship.spawn[1]:
            row[ship.spawn[0]] = "@"
        rows.append("".join(row))
    return "\n".join(rows)


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--seed", type=int, default=0)
    parser.add_argument("--sweep", type=int, default=0, help="generate this many seeds and summarise")
    args = parser.parse_args()

    if args.sweep:
        attempts, failures = Counter(), []
        for seed in range(args.sweep):
            try:
                attempts[generate_ship(seed).attempts] += 1
            except GenerationError as e:
                failures.append(str(e))
        print(f"{args.sweep - len(failures)}/{args.sweep} ok; attempts histogram: {dict(sorted(attempts.items()))}")
        for f in failures:
            print("FAIL", f)
        return

    ship = generate_ship(args.seed)
    print(render_ascii(ship))
    print(f"\nseed {ship.seed}, {len(ship.rooms)} rooms, {ship.attempts} attempt(s)")
    for room in ship.rooms:
        links = sorted(ship.graph[room.id])
        print(f"  #{room.id:<3} {room.zone.value:<12} {room.type:<20} {room.rect.inner_w}x{room.rect.inner_h}  -> {links}")


if __name__ == "__main__":
    main()

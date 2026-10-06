# Ship roguelike skeleton

A roguelike set aboard a spaceship. Maps come from a **graph → floorplan → tilemap**
pipeline built to look *engineered* (compact, orthogonal, zoned, no wasted space),
not dungeon-like.

## Run

```
pip install -r requirements.txt
python main.py            # random ship
python main.py --seed 42  # reproducible ship
```

Controls: arrows / numpad / `hjklyubn` to move (8-way), `Tab` toggles room labels,
`R` generates a new ship, `Esc` quits. The status bar shows which room you're in.

Headless tools:

```
python -m ship.debug --seed 1      # ASCII map + room list and connections
python -m ship.debug --sweep 500   # generate many seeds, report validation retries
```

## Generation pipeline (`ship/pipeline.py`)

| Stage | Module | What it does |
|---|---|---|
| Archetype + deck shape | `stages/deck.py` | 11×5 grid of 8×8-tile structural modules; stepped bow taper, optional narrow stern; hull outline |
| Functional zones | `stages/zones.py` | Command (bow), Engineering (stern), Habitation/Science above the spine, Cargo below |
| Corridor network | `stages/corridors.py` | 3-wide spine bow→stern, cross corridors on module lines at zone boundaries (+ random extras) |
| Rectangular partitioning | `stages/partition.py` | BSP-subdivides every block completely; rooms share walls; splits prefer module lines |
| Assign rooms | `stages/assign.py` | Bridge at bow, Reactor at stern next to Main Engineering, Airlock on the hull, then per-zone room lists |
| Doors / graph | `stages/doors.py` | Corridor doors, spanning tree for interior rooms, extra loop doors; reactor only via engineering |
| Validation | `stages/validate.py` | Required rooms exist and every room is reachable from the airlock; otherwise regenerate |
| Templates/furnishing, vents, disaster | `stages/stubs.py` | Placeholders (no-ops) for the next steps |

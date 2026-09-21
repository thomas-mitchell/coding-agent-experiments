# Dynamic board layout

A pygame-ce sandbox for an Arkham-Horror-style board where **locations are cards**
connected by one-way or two-way roads, and the board arranges itself.

The game state is a directed graph. Where a card sits is derived, disposable state.
Gameplay code never says *"the Inn goes at (420, 275)"* — it says *"the Inn connects to
the Graveyard and the Market"*, and the layout decides the rest:

```python
board = BoardGraph()
board.add_location(hospital)
board.connect(hospital, church)
board.connect(hospital, town_square, two_way=True)

layout.update(board)
```

## Running it

```
pip install -r requirements.txt     # pygame-ce
python main.py                      # the sandbox
python main.py --script             # headless: play the whole deck, save board_final.png
python -m pytest                    # the tests
```

| key | |
|---|---|
| `A` | draw the next location card and place it |
| `Del` | remove the hovered or selected card |
| `C` then two clicks | connect two cards (hold `Shift` for a two-way road) |
| `X` then two clicks | close the road between two cards |
| `R` | full relayout from scratch — the churn the tiers exist to avoid |
| `Space` | replay the last animation |
| `1`–`4` | force the next insertion to a particular tier |
| `F` / `F1` | fit the board / debug overlay |
| drag, wheel | pan, zoom |

## How it places a card

Cards live in discrete slots on a square grid whose gutters are wide enough to route
roads through, so the board lines up like something that was printed rather than
simulated. Placing a card is a discrete search over free slots, scored by:

```
cost = edge_length + edge_crossing + edge_over_card
     + card_overlap + board_boundary + movement + region
```

`movement` is weighted far above everything else. The solver is not asked *"what is the
prettiest arrangement of this graph?"* but *"what is the least disruptive change that
accommodates this card?"* — mental-map preservation. A board the player has learned is
worth more than a tidy one.

It escalates only as far as it has to:

1. **free slot** — take a free slot near the card's connections, move nothing
2. **local shuffle** — nudge one or two neighbours aside, if that genuinely scores better
3. **expand board** — grow the grid, when there is no free slot at all
4. **full relayout** — hill-climb the whole board, still paying the movement cost

Playing the fifteen-card demo deck onto the five-card opening board reaches tier 1
fourteen times and moves **zero** existing cards. Press `R` to see what an unconstrained
relayout does instead: sixteen of twenty cards jump.

Connecting two cards that are already on the table moves nothing either. The road is
simply drawn long.

## How it draws a road

Placement and routing are separate problems. Once cards are in slots, the gutters form a
street network, and each connection is routed through it with A\* — turn penalties keep
runs straight, and a lane-reuse penalty keeps parallel roads apart. Corners are rounded,
roads are drawn *under* the cards, and one-way links get an arrowhead.

## The animation

The rearrangement is presentation, not something to conceal. A card is drawn, cards
already down slide apart, roads cross-fade, and the new card drops onto the board — each
stage inside the 300–600 ms band, never a visible solver.

## Layout

| | |
|---|---|
| `board/graph.py` | `Location`, `BoardGraph` — the game model, with no coordinates in it |
| `board/slots.py` | the invisible grid of card slots |
| `board/scoring.py` | the cost model |
| `board/layout.py` | `BoardLayout` — slot assignment and the four tiers |
| `board/routing.py` | orthogonal road routing |
| `board/animation.py` | tweens and stage sequencing |
| `board/render.py` | cards, roads, camera, debug overlay |
| `board/scenario.py` | the demo deck |

Locations may carry soft hints — `region="north"`, `layout_group="other_world"`,
`preferred_distance=2` — which nudge the solver without naming a coordinate.

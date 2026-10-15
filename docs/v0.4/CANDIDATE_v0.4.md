# v0.4, the candidate model: hands and head

*Written 2026-10-15 on the owner's word ("the split network is what makes sense to me. We have a mechanical side and a
strategy side"; "add this as the candidate v0.4 model to start with"). Not built; the full proposal it narrows is
[PROPOSAL_v0.4.md](PROPOSAL_v0.4.md) (its section 13). Decided first: the learning step by the library's GRU (B-237).*

## The shape

One network in two parts. **The hands** run every frame (40 a second): aim, keys, movement, rocket jumps. **The head**
runs every eighth frame (5 a second): where to go, what the enemy is probably doing, how the game stands, with a store
of the last three minutes. The head sends the hands a **plan** of 256 numbers, held for eight frames; the hands send the
head their state.

```
 791 inputs ─► encoder 256 + attention ─┐
 61 movement inputs ─► legs 256→256 ────┼─► HANDS: fast GRU (state 512) ─► keys, turn, pitch, fire, weapon ...
                                        │          ▲ plan 256 (every 8 frames)
 every 8th frame: encoder mean, fast state, store read, events ─► HEAD: slow GRU ─► target, way, value, win chance, guesses
                                                                        │ write every 0.8 s / read by attention
                                                                        ▼
                                                             STORE: 224 snapshots × 128 (3 minutes)
```

**His legs become part of the hands** (the owner: "the separate movement network should really be part of the main
fast network"). Today's movement network is small (86 thousand weights: 61 inputs → 256 → 256 → its choices, no memory).
It goes in whole as a branch of the hands, its answers into the hands' movement outputs where the switch hands them over
today: the merged network answers exactly as the two do now, and from then on one network trains both. Its branch learns
at a reduced rate at first: v0.2.1's lesson that graded his keys against it cost him the game (B-243).

## The sizes (weights)

| Part | Small | **Middle (proposed)** | Large |
|---|---|---|---|
| Hands: encoder, attention, legs branch, outputs | 0.66 M | 0.66 M | 0.66 M |
| Hands: fast GRU (input 512, state 512) | 1.57 M | 1.57 M | 1.57 M |
| **Hands total** | **2.2 M** | **2.2 M** | **2.2 M** |
| Head: input layer (1,056 →) | 512: 0.54 M | 768: 0.81 M | 1,024: 1.08 M |
| Head: slow GRU (state) | 768: 2.95 M | 1,024: 5.51 M | 1,536: 11.8 M |
| Head: plan, store, outputs | 0.5 M | 0.66 M | 0.9 M |
| **Head total** | **4.0 M** | **7.0 M** | **13.8 M** |
| **Total** (today 1.75 M) | **6.2 M** | **9.2 M** | **16.0 M** |

A variant for any column: the hands' GRU from 512 to 768 wide (1.57 → 2.95 M, an exact widening), if aim and rocket
jumps want the room.

**Training cost.** The head runs on one frame in eight, so its 7 M cost about what a 0.9 M part costs every frame: the
middle shape trains at close to today's cost per frame of play once the learning step is rebuilt (B-237). The window
doubles to 768 frames (96 of the head's steps); the card's memory at that length is measured before a run.

**On the server** (two slow cores; numbers to be measured on a private server at the 99th percentile). Two Bobbys with
their head ticks four frames apart: a frame carries both hands and one head.

| | Small | Middle | Large |
|---|---|---|---|
| Weights a frame, two Bobbys | 8.4 M | 11.4 M | 18.2 M |
| Their time a frame (estimate) | 2 to 4 ms | 2.5 to 5 ms | 4 to 8 ms |
| Two Bobbys within 25 ms, beside today's 7 ms | yes | yes | likely, tight |

The owner: one Bobby a server is fine, two ideal. The middle shape should carry two.

## The start, and the order

1. The learning step rebuilt and proven identical (B-237).
2. The legs merged into the hands, proven to answer as today.
3. **The head pre-trained on the pros' demos with its door shut** (below), so it costs him nothing yet.
4. The run: the hands start as v0.3's end exactly; the plan and the head's target start at zero and open only as far
   as they win games. Ten updates level against the control first.

## The pros' demos and the head

The head's questions are the ones the demos answer. As AlphaStar began from people's games before playing itself, the
head learns from 4,449 pro duels first, offline, while it cannot yet move him:

- **Where to go next**: the pro's next item or holding place, read in hindsight from where he went in the next seconds.
- **Who is winning**: the game's result is known for every frame of a demo: the win chance learnt from it.
- **Where the enemy is**: wherever the demo shows the other player, the truth for the guessing game; elsewhere, the
  next place he was seen.
- **What to remember**: minutes-long sequences teach the store what to write.

Then a small pull toward the pros' choices that fades during the run (the owner's rule: seeding is fine, what stays
must hold without it). Never the mouse: copying the pros' aim at full weight destroyed his (RESULTS 2026-10-04 21:12,
kept locally). The demo sets are rebuilt first with the mended converter (B-218, B-219) and v0.4's inputs.

## Also for v0.4 (backlog)

- **B-251**: the owner's ~5,000 public free-for-all games: calibrate his aim limits from many players.
- **B-252**: rocket jumps.
- **B-253**: the legs inside the hands (above).

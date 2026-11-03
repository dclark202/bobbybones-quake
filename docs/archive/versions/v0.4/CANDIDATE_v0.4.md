# v0.4, the candidate model: hands and head

*Written 2026-10-15 on the owner's word ("the split network is what makes sense to me. We have a mechanical side and a
strategy side"; "add this as the candidate v0.4 model to start with"). Not built; the full proposal it narrows is
[PROPOSAL_v0.4.md](PROPOSAL_v0.4.md) (its section 13). Decided first: the learning step by the library's GRU (B-237).*

**Before the head** (the owner, 2026-10-16 and 2026-10-17): one movement network ([UNIFIED_MOVEMENT.md](UNIFIED_MOVEMENT.md), B-259), and then its clean-up (step 6b there): the bridge's parts that no longer act once the legs switch is gone (the switch, the turn-down dial and residual, the turn correction, the fade, the solo self-driving, the key overrides) are removed from the network and the code, with the network proven to answer as before. Only then the head.

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

## The pros' demos and the head: how the seeding works

Supervised first, as AlphaStar began from people's games before it played itself: each pro game replayed through his own
senses, the head asked at every tick what the pro did next, and taught to answer, all before it is joined to him.
Reviewed with the owner later (2026-10-15).

1. **Through his eyes.** A demo has the recording pro's state every frame (place, speed, view, weapon, health, armor,
   ammunition, pickups, score, clock) and the enemy wherever the server sent him (often more than the pro could see).
   The converter (`sim/demo_dataset.py`) builds on the map, with his own sight and sound rules, exactly the 791 inputs
   he would have had. What the pro could not see is used only as an answer, never as an input.
2. **The hands, frozen, over the demo.** v0.3.x's network runs over the frames as it is: the encoder's summary and the
   fast memory's state are what the head gets in a game. The head ticks every eighth frame and writes its store as it
   will in play.
3. **The answers, in hindsight**, at every tick of the head:

   | The head's question | The answer from the demo |
   |---|---|
   | Where to go next | the next big item the pro took, or the holding place he went to and stayed at, within seconds |
   | Which way | which of the map's ways he took there |
   | Who is winning | the game's result, and the score's change over the next two minutes |
   | Where the enemy is | the enemy's true place wherever the demo has it; elsewhere, where he was next seen |
   | What the enemy is after | the next item the enemy took |

4. **Only the head learns.** About 46,000 minutes of pro play (the rocket jump extraction's count) are about 14 million
   ticks of the head, plenty for 7 M weights. It learns on three-minute stretches, so the store learns what is worth
   writing: a slot that answers "where is he?" a minute later is paid for.
5. **Checked on games it never saw** (some tournaments held out, and the two held-out maps): the next target better than
   simple rules (the nearest item, the pros' order table); the win chance true to its word (70% said, about 70% won);
   the enemy's place better than his last-seen inputs.
6. **Joined to him with every link at zero**: he plays as v0.3.x. In the run a small pull keeps the head near its
   pro-taught choices until the game's pay reaches it, and fades (the owner's rule: what stays must hold without it).
   Never the mouse: copying the pros' aim at full weight destroyed his (2026-10-04).

**What can go wrong**: pros play pros and he plays himself, so the win chance is off at first and the run corrects it;
pros take ways he cannot (a rocket jump to the red armor): such targets are masked until he can make them, or the pull
fades early (v14 lost Aerowalk to a rule that named what he could not reach); one point of view, so the enemy's own
choices are seen only in part. First: the demo sets rebuilt with the mended converter (B-218, B-219) and v0.4's inputs.
All of it offline, mostly on the processor, beside v0.3.1's training.

## The enemy as a target ("hunt"; the owner, 2026-10-15; B-256)

The classic Quake bots push when you are weak because their goal selector treats the enemy as a moving item: when his
estimated stack drops, the worth of walking to him passes the worth of the yellow armor. In v0.4 the head's "where to go
next" gets the enemy as one more target beside the items and the holding places: his believed place (the guessing game's
answer, refreshed as the head ticks), handed to the hands' way and legs as an item's place is today. Its worth is not a
rule: the head learns it from the pay by the game (`WIN_PAY`: a frag on a weak enemy when level late is worth a lot, at +8
little), and the pros' demos label it in pre-training where the pro went for the enemy rather than an item. It starts
closed (a zero row, opened out of "nothing" as the holding places were) and opens only as far as it wins games.

Why it may work now when it did not before: v0.2's enemy as a target was a narrow rule with a fitted start (level in 48
games, 45.9% in 128, left out); his pushing today is the same at every stack (12.6% of sightings, the pros 6.6%, pushing
when the enemy is weak). A learned worth, with the enemy's stack guessed and the game's score in the pay, is what the
classic bots hand-code.

## Also for v0.4 (backlog)

- **B-251**: the owner's ~5,000 public free-for-all games: calibrate his aim limits from many players.
- **B-252**: rocket jumps.
- **B-253**: the legs inside the hands (above).
- **B-256**: the enemy as a target of the head (above).

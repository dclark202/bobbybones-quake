# BobbyBones as he will be in v0.4.3

*2026-10-24, for the owner's review. Sizes are read from v0.4.1's end checkpoint (v0.4.2 has the same parts); the v0.4.3 additions
are being built today (branches `v043-head`, `v043-control`, `v043-rules`) and are marked* **NEW**.

## The picture

```
 his senses (868 inputs, every 25 ms: what he sees, hears, remembers; human delays and noise)
        │
        ├──────────────────────────────┐
        ▼                              ▼
 ┌──────────────┐               ┌───────────────────────────────┐
 │  THE HANDS    │◄── token ─────│  THE BRAIN (every 0.2 s)       │
 │  (every 25 ms)│   (69 numbers)│  its own GRU 256               │
 │               │               │  readouts: where he is, zones, │
 │  encoder      │               │  his stack, weapon, ahead 1/2/4s│
 │  attention    │               │  his target, when he appears,  │
 │  GRU 512      │◄── plan ──┐   │  the item race,                │
 │  13 outputs   │◄── bias ─┐│   │  NEW: "in control"             │
 └──────┬───────┘          ││   └──────────────┬────────────────┘
        │                  ││                  │ memory + all readouts
        │                  ││                  ▼
        │                  ││   ┌───────────────────────────────┐
        │                  │└───│  NEW: THE HEAD (every 0.2 s)   │
        │                  └────│  GRU 256: the plan             │
        │                       │  + stack, item timers, score,  │
        │                       │    clock, the hands' memory    │
        ▼                       └───────────────────────────────┘
 keys, mouse, fire, weapon, item/place target, way
        │
        ▼
 human limits (reaction 100 ms, flick speed, hand noise, 8 key changes/s) ─► the game (125 fps physics)
```

## The parts

| Part | What it does | Size | Ticks | Learns from |
|---|---|---|---|---|
| **Senses** (868 inputs) | everything as a person perceives it: sight with line of sight, sound, his own state, items, the map's places, the clock and score. The 76 rule-made columns (the old belief) are faded out of the hands in v0.4.2 | — | 25 ms | — |
| **The brain** (`belief`) | reads the senses into its own memory; keeps track of the unseen enemy | ~0.81 M (input 868→256, GRU 256) | 0.2 s | hindsight labels only (what really happened); never the pay |
| ↳ track readout | the enemy's place now, velocity, stack band, weapon in hand, his own weapons | 27 outputs (~73 k) | 0.2 s | hindsight |
| ↳ zones readout | which of 24 map zones he's in, his speed and heading | 28 outputs (~73 k) | 0.2 s | hindsight |
| ↳ ahead readout | where he'll be in 1, 2, 4 s; what he's going for (17 targets); when he'll appear; who wins the next item race | 42 outputs (~77 k) | 0.2 s | hindsight |
| ↳ **NEW: "in control"** | his share of the next two mega/red-armor spawns, 0 to 1 | a few outputs | 0.2 s | hindsight (who took them); never a pay |
| **The token** | the brain's answer (69 numbers: place, band, hand, zones, top-3 zones, speed, how long unseen) handed to the hands | — | 0.2 s | — |
| **The hands** | everything he does now | | 25 ms | the pay (PPO), through the values |
| ↳ encoder | 868 → 256 → 256 | ~0.29 M | | |
| ↳ attention | the inputs cut into 55 tokens by group (enemy, items, places, projectiles…) + the brain's token; 4 heads, width 96 | ~0.26 M | | |
| ↳ GRU memory | 512 | ~1.18 M | | |
| ↳ the merged legs | the old movement network, folded in (one driver since v0.3.5) | ~0.17 M | | |
| ↳ 13 outputs | forward/back, strafe, jump/crouch, turn, pitch, fire, weapon, walk, zoom, lift the mouse, **intention** (17 targets: items, holding places, "the enemy"), legs, way (3) | ~51 k | | |
| ↳ values | the fight value (~25 s horizon) and two long values (items and stack; ~2 min) | ~1.5 k | | |
| ↳ guessing questions | 8 small side-lessons (enemy place, appear, fight, items, near…) that shape the memory | ~23 k | | hindsight |
| **NEW: the head** | the plan: which item, hold, push, back off, deny a way. Reads the brain's memory and every readout (including "in control"), his stack, his item timers, score, clock, and the hands' memory (read only) | ~0.6 M (GRU 256) | 0.2 s | the pay, through the 2-minute value (a plan pays off 30–60 s later) |
| ↳ plan → hands | 64 numbers added into the hands' memory | starts at 0 | | |
| ↳ bias → intention | a nudge on the 17 intention choices | starts at 0 | | |
| **Total** | | ~3.0 M today, ~3.6 M with the head | | |

## What is hard-wired in v0.4.3, and its fate

| Hard-wired part | v0.4.3 | Later |
|---|---|---|
| The old rule belief (76 columns) in the hands and the simulator's readers | gone (v0.4.2) | — |
| The 76 rule columns inside the brain | still read by the brain | v0.4.6: faded out of the brain |
| The item rule (intention teacher, 10% floor) | **faded in the run** after the head shows it chooses well | — |
| The level pull (view eases to level out of sight) | **phased out in the run**: 0.95 → 1.0 | — |
| Blind-fire cost | waived where the brain believes the enemy **is** (v0.4.2) and, **NEW**, where it predicts he **will be** in 1–4 s | v0.4.4 on: costs and pays cross-faded into win chance |
| Shaping pays (items, stack, speed, damage, frag flats, watching, big-weapon order, shot price) | unchanged (mega 0.35) | v0.4.4 → v0.4.7: into pay by win chance only |
| His own item timers | kept (a person keeps them too) | kept |
| Fairness limits (physics, senses, aim, keys) | kept | always |

## "In control" and pay by win chance

They measure nearly the same thing from two sides:

- **"In control" (the brain's readout):** a prediction, from his senses, of who will own the next big items. It's learnt from the truth in hindsight, like the brain's other readouts, and never paid.
- **His win chance beyond score and clock:** the value network's view. What the value expects minus what the score and clock alone give is his "control" in pay terms.

As pay moves to win chance (v0.4.4 on), the value learns what wins, and the head plans to raise it. "In control" is the brain's own, explainable reading of the same state. So it feeds the head as an input now, can replace frag share as a check measure later (owner, 2026-10-24), and gives the play-test timelines a number people recognize.

## How v0.4.3 opens (one new thing at a time)

1. **Start** from v0.4.2's end with the head at zero: he plays exactly as v0.4.2's end.
   The "in control" readout's lesson and the head open slowly, check-tied.
2. When the head shows it chooses well: the item rule's floor fades to 0.
3. Then the level pull: 0.95 → 0.98 → 0.99 → 0.995 → 1.0, about 2 h a step.

The "will be" exemption opens after the head is fully in, before the item rule fades (one thing at a time).

**Pass:** level or better against v0.4.2's end, and the decision report's item and pressing rows moving toward the pros'
([RUN_v0.4.3.md](RUN_v0.4.3.md)).

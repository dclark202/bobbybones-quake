# v0.6.2 on one page: the strategy head opened, then the item rule faded, on win pay only

*2026-10-27 (owner): from v0.6.1's end (pay by win chance only). The plan of [RUN_v0.5.3.md](../v0.5.3/RUN_v0.5.3.md), renumbered:
two steps one after the other, the head first (with the item rule still guiding his target), then the rule faded with the head
open. Draft: the owner's decisions so far are below; the rest is settled after v0.6.1's play test.*

**Marks:** ✅ built and tested · ⏳ building · 🧪 to measure · ❓ owner's decision · ⏸ later

## Start

| | |
|---|---|
| Network | v0.6.1's end (`keep/policy_end_v061.pt` + optimizer) |
| Head | `sim/head2.py` (the strategy head: a slow GRU reading the brain, its readouts and his stack; a bias on his target choice, gated) |
| Head's start | **to revisit 10-28 after v0.6.1 has started (owner)**: fit the head to the pro demos with the gate shut, compared against how Bobby himself would have handled the same moments ❓ (below) |
| Mix | as v0.6.1 (65% whole games / 35% pro starts) ❓ |
| Control | **v0.6.1's end; every fourth check v0.6.0's end** ✅ (owner) |

## The head's start: the pro-demo fit (to revisit)

| Step | What |
|---|---|
| 1 | replay the pro demos through Bobby's own brain and hands (the simulator's inputs at each head tick, 0.2 s) |
| 2 | label each tick in hindsight with the pro's next target (the item taken or holding place reached, in his target list) |
| 3 | fit the head's correction only: Bobby's own choice + the head's bias = the pro's choice (where he already chooses as a pro, the head adds nothing; no double count of the item rule) |
| 4 | measure on held-out demos: Bobby's hands alone against hands + head, agreement with the pros; and where Bobby and the pros differ |
| Cost | the demo converter writes 311 of today's 868 inputs: ~1 day to update; label and fit scripts small; CPU at low priority |
| Then | the gate opens; the head goes on learning from win pay (the fit is only a start: the self-play equilibrium is unchanged) |

## Phase 1: the head opens / Phase 2: the item rule fades

| | |
|---|---|
| Phase 1 | the head's gate 0 → 1 (live `H2_GATE_CAP`), the item rule still on |
| Phase 2 | the item rule's weight 1 → 0 (live `INTENT_TEACH_W`), the head open |
| Gate | **keep going unless a collapse** ✅ (owner, as v0.6.1); flag < 40% won-lost, serious < 30% |
| Checkpoint | **saved when the head is open; training does not stop** ✅ (owner) |
| Play tests | **the owner plays both**: the head-open save and the rule-faded end ✅ |

## Watched (from v0.6.1's logs as the baseline)

| | |
|---|---|
| Targets | his target per map; agreement with the item rule (logged from v0.6.1) |
| Behaviour | camping and time at spawns, roaming, hunting (the v0.4.3/0.4.4 failures); the lightning-gun pull (82% in v0.4.4) |
| Pay | by lead and time left (logged from v0.6.1) |
| Brain | its readouts' accuracy (logged from v0.6.1): the head reads them |

## Later (reminder, not in this run)

Rocket jumps and the failed movement jumps (Aerowalk's red armor): the full-route copies are built and kept off.

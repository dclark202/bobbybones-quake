# Review: b1.2 to b1.4, the strategy head and the hand-over of his target choice

2026-11-03, read only (code at `8f2985c`). b1.4a had run three updates when this was written (09:39), so its own numbers are
three updates; the rest is b1.2a to b1.3a's data and the code.

**Marks:** **V** verified in the code (file:line) or the data (file named) · **G** a guess or an inference, not measured.

## The findings, ranked by what they cost in games

| # | Finding | Mark | Matters because |
|---|---|---|---|
| 1 | The head's memory is a ~30 s integrator ticking every 0.2 s, and its target scores read only that memory. The choice it is asked to make is mostly fast: about 70% of his target changes happen in fights, and the item rules time items to the second | V (structure), G (that this is the main cause of the 37%) | the head alone loses the mega on 9 maps of 10; the blend can only add what a slow chooser can see |
| 2 | Pays still tied to the target: the speed pay is paid only on an item's way (never on the hunt's), an abandoned trip gives its speed pay back, and every change costs 0.02 | V | any learner of the choice, the head included, is paid to prefer item runs to fights: the owner's "he needs to fight more" |
| 3 | The blend as built: the head's own scores have no trust region at a low mix, the ramp multiplies what it learnt early, at mix 0.5 it learns a correction (twice the change it wants) not a policy of its own, and the "frozen" half drifts with the trunk | V (code and algebra), V (drift, three updates), G (size) | b1.4a can reach a stable 0.5 that does not carry over to the head alone; b1.4b would relearn |
| 4 | The checks may favour the network under test by a few points: the same save against itself read 90-70 (56.3%), and every b1 run's first check read 53 to 62% against a start it had barely left (B-220, open since 10-11) | data V, cause G | every gate ("at least 50%", "under 45%") is read against this zero point |
| 5 | The head's credit horizon is about 1.2 s, not two minutes: its advantage uses the trainer's λ 0.98 | V | a target choice pays off over 4 to 8 s; beyond 1.2 s the credit rests on its value being right |
| 6 | Bug: with `--overlap` each update learns at the next rollout's mix (and gate), not the mix it played at | V | small in b1.4a (0.00625 a step), wrong for any larger live change |
| 7 | The head's PPO ratio is against the one-update-stale played policy (the hands use decoupled PPO), and its cap (e^30) does not bound the negative-advantage branch | V | wasted or lopsided steps; b1.2a's overflow path is only held by the 0.5 gradient clip |
| 8 | Smaller: the b1.3a card's per-map head-alone numbers are frag shares, not win rates; `INTENT_SEEK_W` is a dead dial; b1.3a slid against b1.2d's end; two lopsided maps in b1.2d; a tool default that plays both sides without contact freedom | V | the record and the plan |

## 1. Is the head's design sound, and why did an 87% copy play 37% alone?

**The goal is sound** (a learner owns the choice, starts from the rules' imprint, improves on pay). **The head as built is not fit
for the choice it is given.**

**What it is.** A GRU of 256 that ticks every 8 frames and holds its outputs in between; the target scores are `Linear(s)`, its
memory only (`sim/head2.py:144`, `:252-257`). Of its input layer's weight, 64% sits on the hands' memory, 18% on the brain's, 13%
on his own stack, timers and clock (V: b1.3a's end, `keep/policy_end_b13a.pt`).

**Its memory is slow and stayed slow (V, b1.3a's end):**

| | |
|---|---|
| time constant of the update gate from its bias, median | 153 ticks (31 s); 10th percentile 28 ticks (5.6 s) |
| units under 5 ticks (1 s) | 1 of 256; under 20 ticks (4 s): 10 |
| share of the target scores' weight on units slower than 20 s | 68% |
| change of the gate biases over 130 updates of copying | 0.08 on average, 0.12 at most (they start near 5: `chrono` 300, `head2.py:151-156`) |

The input-driven part of the gate was not measured on real inputs; its rows (norm about 0.86 over 256 inputs in [-1, 1]) suggest
typical shifts well under the bias (G).

**What the choice needs (V, `metrics.jsonl` of b1.3a, all seats, an update):** about 63,000 readings in contact, of which 24,000
(38%) change his target and 2,500 of those to the enemy; about 21 trips a player-minute, two thirds abandoned. That is about 15
changes a player-minute in fights against about 6 outside them (G: the two counters may not count the same seats).

**What the head alone did (V, `duel_gru_b1_3a/watch/h2h_headalone/*.json.log`):** the mega 31 to 41% of its spawns against the
opponent's 49 to 59% on every map but Lost World (37 against 37); bare 8 to 14% of the time against 3 to 7%; more lives a minute
(it dies more). A chooser that sees item timers and sightings through a 30 s average would do exactly this (G: not split out).

| Cause of 87% → 37% | Evidence | Weight |
|---|---|---|
| The slow head | above | the main one (G) |
| Distribution shift: the copy was taught only on states the hands chose into; its errors compound under an 8 s lock | KL 0.145 nats a reading; the head's first choice was the played one 75% of the time, the hands' 80% (`head2.copy`) | likely (G) |
| The 87% counts every reading; agreement on the readings that change the target, in and out of fights, was never measured (the card's "by map and situation" read was not built) | | unknown |
| Not the check | the head-alone games had a free contact for both sides (`set.SEAT_CONTACT_HE 1` in the json); the numpy path ticks after the frame and mixes where the head has a state, as the trainer does (`sim/test_suite.py:300-345`) | V |
| Not respawns | memory resets only at a game's end (`sim/duel_env.py:13161`); readings with no head state 0.08% (b1.4a updates 2-3) | V |

**What to do about it:** give the target scores the current frame (proposal P1), or split the choice: the head picks a plan over
seconds (an item class, a zone, hunt or hold) and the hands keep the re-decision in contact. Without one of these the head stays
behind the hands on the decisions that win fights and megas, at any mix.

## 2. Is b1.4a's blend correct as implemented?

**Correct (V):**
- The hands' target logits are cut from every loss that reads them (`sole_`, `sim/train_duel_rnn.py:4207-4212`; `h2pi_`, `pi_t`);
  the trunk gets nothing from the target choice; the item rule's label (`--intent-teach 9.13`) reaches nothing. The 17 rows are
  restored after each step (`H2_ROWS`).
- The head's own term sees the blend with the hands' part as a number (`:4677`); its value reads its memory and the hands' as a number.
- Each save is checked at the mix in its file (the `head2.mix` buffer; `test_suite.py` and `plugins/netpass.py:369-370` mix the same way).
- Respawns: see above. The head keeps its state through a death; only a game's end clears it.

**Problems:**

| | What | Mark | Fix |
|---|---|---|---|
| B1 | **Learnt at the next rollout's mix.** The mix is set back to the played one (`:4062-4063`), then `launch(update + 1)` (`:4101`) runs `pre_rollout`, which writes the next mix into `pol` (`:3258`); the learning step comes after. The gate (`:3257`), the brain token's gate (`:3251` / `:4066`) and the rule fade (`:3262` / `:4069`) have the same order: the ramps of v0.4.1, v0.4.2 and b1.1a were learnt one step ahead too. In b1.4a the head's ratio starts off by about 0.00625 × (head − hands), 0.1 logit on a reading | V code, G size | restore after the launch, or under `--overlap` set the buffers on `ACT` only |
| B2 | **No trust region on the head's own scores at a low mix.** The blend moves k times what the head's scores move, Adam (its own group) takes the k back out, and PPO clips the blend: the scores can move about 0.2/k logits an update before the clip binds (about 30 at k 0.006). The ramp is outside any trust region: each step adds Δk × (head − hands) to his choice, so what the head learnt at k 0.06 counts 8 times at 0.5. The tripwire (scores' length over 60; 17 at the start) is the only guard | V algebra (`:4677-4686`), G size | a KL or clip on the head's own distribution, or P1 (no blend) |
| B3 | **At 0.5 the head learns a correction, not a policy.** The best head output is 2L* − hands (L*: the best blend). Moved later to mix 1 it plays hands + 2Δ: every correction doubled. b1.4a's 0.5 does not prepare the head to play alone | V algebra | P1, or P2's mixture |
| B4 | **The frozen half drifts.** Only the 17 rows are held; the memory they read moves with every other lesson. With the head not yet acting (mix 0, b1.4a updates 1-3) his target choice already moved past the clip on 1.9%, 4.0%, 5.0% of readings (`head2.clip_share`): nothing steers that half | V data | check a save at mix 0 against b1.3a's end at mix 0; P1 makes the head own it |
| B5 | **The head's ratio is against the played policy**, one update stale under `--overlap` (the hands clip around the proximal pass, IS cap 2); `clamp(max=30.0)` (`:4679`) lets the ratio reach e^30 on the negative-advantage side. The gradient clip at 0.5 (`:5090`) stops an overflow, not a few frames steering a piece | V | the proximal pass for the head's term, IS cap 2, a second clip at 3 |
| B6 | **Credit horizon.** `head2_.gae(..., lam)` at the trainer's λ 0.98 (`:4528`): 1/(1 − γλ) ≈ 50 frames, 1.2 s, the same as the hands' (47). The two minutes enter only through its value | V | a λ of its own, 0.995 to 0.998 (5 to 11 s) |
| B7 | Entropy on the choice: only the head's, 0.005 × 0.1 on the blend, through k (`:4712`); a blend of two distributions in log space is sharper than either | V, low | |
| B8 | The hands' joint ratio still carries the intention's (blended, numbers only) on reading frames, so the head's movement within an update can clip the hands' other outputs there (one frame in 40) | V, low | leave the intention out of the hands' ratio under `--head2-sole` |

**The equilibrium as built:** half of his choice is the hands' drifting imprint, the other half the head's best answer to it on his
whole pay. The win part is 36% of the pay by size (V, `pay_terms.size_share`), so the remaining target-tied pays (finding 2) steer
the head toward item runs. In self-play both copies learn the same tilt, so it does not show as a loss in the checks.

## 3. What still shapes his target choice, and the order to take it out

| Term | Where | Size (b1.3a, a player-minute) | Mark |
|---|---|---|---|
| The lock, 8 s, with its releases (item taken or gone, "nothing", a contact) | `duel_env.py:2313`, `intend()` `:6943` | | V |
| `CONTACT_FREE` 1: every contact frees the choice, every reading in contact counts | `intend()` | 38% of contact readings change | V |
| `INTENT_SWITCH`: 0.02 a change, a constant, not live | `:458` | −0.37 (after deaths and damage, the largest cost) | V |
| **The speed pay on his way: only with an item target**; the enemy and holding places are left out | `:12955`, `:12983`, `:13000` | +0.32 (a third of the frag pay, 0.89) | V |
| The claw-back: an abandoned trip gives its speed pay back | `:12958` | −0.08 | V |
| The way pay itself: `intent_seek × INTENT_VALUE × item_reward`, and `--item-reward 0` | `:12956`, `train.cmd` | 0 (`item_seek −0.0`) | V: `INTENT_SEEK_W` is a dead dial; b1.4's step C changes nothing |
| `WEAPON_FREE`: a rocket, rail or lightning target he has with ammunition becomes "nothing" | `intend()` | | V |
| The item rule's label and its silencers (`RULE_CONTEST`, `RULE_HUNT`, `OPEN_SILENT`) | | reach nothing under `--head2-sole`; live only in the frozen imprint | V |
| `ITEM_FLAT` (in force MH 0.35, RA 0.30, YA 0.15; `train.cmd` says MH 0.30, `live.json` wins), `BIG_PICK_SEQ` | | pickup pay: the owner's to keep | V |

**The order I propose** (one at a time, each on the owner's go):

0. **No run:** take the way pay's dial and the rule label off the plan (both dead); fix B1 before any further ramp.
1. **The speed pay alike for every target** (the hunt's way included) and no claw-back of speed pay. Equilibrium: speed is paid
   the same whatever he chooses, both copies gain alike, so the choice is priced by fights, items and the win part only. Behaviour on
   the way: more hunting when nobody is in view. The largest tilt, and the one against fighting.
2. **`INTENT_SWITCH` to 0.** Outside contact the lock already limits changes; inside contact it is the price of re-deciding. Watch
   trips a minute and targets reached (b1.1a: freedom without a chooser became flicker).
3. **`WEAPON_FREE`'s coercion out**: the chooser learns not to fetch a weapon he has.
4. **The lock outside contact, 8 s → 0, last**, and only once the chooser has a fast path (finding 1); it defines when a choice
   counts at all.

## 4. Alternatives

Updates take about 4.5 minutes; a 200-game check about an hour on 8 efficiency cores.

| | What it changes | Cost | Equilibrium | Cheap test first |
|---|---|---|---|---|
| **P1, the exact hand-over** (recommended) | The head's target scores read its memory **and the hands' memory of the frame** (as a number); the hands' part starts as a copy of the hands' 17 target rows, its own part at zero. The head is then exactly the rules' imprint and plays alone (mix 1) from update 0, the only learner of the choice; the hands' rows go out of play. No blend, no shift, no doubling, no drifting half, no copy to relearn | about half a day: `head2.py` (the layer, numpy), `tools/head2_init.py`, export and plugin follow; a 12 h run | at the start exactly b1.3a's choices; then the best answer on his pay, with the slow memory as context | the identity check (0 actions differ, as `start.ps1` does today); 10 updates on a scratch copy reading the choice's step per update; 200 games against the start at update 20 |
| P2, a mixture in place of the blend | At each reading the head's draw with chance k, else the hands'; the head learns from its own draws (its own ratio) plus a fading KL to the frozen hands on every reading (DAgger on the states it visits) | about a day | as P1; the head is trained as itself at every k | the head-alone check at k 0.25 against the start |
| P3, a faster head | the update gates' start spread from 1 to 300 ticks (half under 10), a tick at each reading, or both | small; changes the head's outputs, so the copy is relearnt (the full run taught it in four updates) | unchanged | 20 updates of copy on a scratch copy, then 200 games of the head alone |
| P4, the head's own λ | 0.995 to 0.998 for its advantage (5 to 11 s) | one argument | unchanged; credit reaches choices whose pay comes seconds later | the head's value loss and advantage spread over 10 updates on a scratch copy |
| P5, the head's PPO as the hands' | around the proximal pass, IS cap 2, second clip at 3 | small | unchanged | `head2.clip_share` and its KL a step, 10 updates |
| P6, the overlap order (B1) | the buffers restored after the launch | tiny | unchanged | a counter: the learning step's mix equals the rollout's `h2m` |
| P7, the checks | (a) the zero point: the watcher's command with one save on both sides, 400 games at two seeds; (b) the head alone (mix 1) against the start every 40 updates of b1.4a; (c) a b1.4a save at mix 0 against b1.3a's end at mix 0; (d) b1.2d's end (the network on the servers) as a check opponent | games: the owner's word | | |

## 5. What looks wrong or unexplained in the results

1. **The checks' zero point (B-220).** b1.3a's `selfchk*.log` (the same `policy.pt` on both sides, 160 games): 40-24, 28-20, 22-26,
   together 90-70, 56.3% (z ≈ 1.6), not on the card. First checks of each run against a start it had barely left: b1.0a 61.9, b1.2a
   53.8, b1.2b 53.1, b1.2c 53.1, b1.2d 56.2, b1.3a 58.5%. Every check plays `--seed 100` (`tools/duel_eval.py:423`): the same game
   seeds each time, so near-identical networks replay near-identical games and share one draw of luck (G). If the edge is real, "level" is
   about 53 to 56%, and b1.3a's last checks (48 to 50%) read about 45%.
2. **The b1.3a card's per-map head-alone numbers are frag shares** (`head2head.py` prints won-lost and the frag share). The win
   rates ran from 20% (Blood Run, 4-16) to 50% (Campgrounds, 10-10); Lost World was 9-11 (45%), not 61%.
3. **b1.3a slid against b1.2d's end:** 58.5 → 44.0% from update 10 to 50 (z ≈ 2.9 as independent samples), then 48 to 50%;
   against b1.1, 52% at update 70 where b1.2d read 59.4% at 60 (z ≈ 1.4). b1.4a starts from b1.3a's end and is checked against it,
   not against b1.2d's end, the network on the servers.
4. **Lopsided maps** (pooled checks against each run's start; the seeds are shared, so these z's overstate): b1.2d Lost World 49-15
   (77%, z +3.3), Aerowalk 24-40 (38%, z −2.9); b1.3a Sinister 51-69 (42.5%). b1.2d's gain was mostly one map, its loss Aerowalk.
5. **Flicker in fights:** 38% of readings in contact change his target and one change in ten goes to the enemy; two trips in
   three are abandoned. The lock does not hold in contact (`CONTACT_FREE` 1); only the switch cost and the claw-back price it.
6. **b1.2a's runaway** (from its card, checked in its metrics): the bias's length 5, 55, 162, 317 at updates 20, 40, 60, 80, then
   NaN at 82. b1.4a's freeze removes the second learner; B2 is the remaining route to a large head score.
7. **Tools:** `tools/run/head2head.py` defaults `--contact-a` and `--contact-b` to "0" (both sides without contact freedom, which
   training has at 1). The head-alone run passed 1; the default is a trap. `train.cmd`'s `ITEM_FLAT` comment (MH 0.30) differs from
   `live.json` (MH 0.35), which is what plays.
8. **Pay pathologies:** none seen in b1.3a's ledger (frags +0.89, deaths −0.94, damage +1.61 / −1.40 a player-minute; the win
   part 36% of the pay by size, +0.04 net). b1.4a too young to read.

## For b1.4a while it runs (reads only, nothing changed)

- Watch `head2.copy.raw` (the tripwire, 17 now), `head2.clip_share` and the share of readings where the blend's choice differs from
  the hands' as the mix passes 0.1 to 0.3: B2 would show there first.
- The card's pass mark ("at least 50% at mix 0.5 for three checks") should be read against the checks' zero point (section 5, item 1).
- Before b1.4b: the head-alone check of the `Adone` save (P7 b) and the mix-0 drift check (P7 c) say whether the head is ready for
  more of the choice; P1 is the cleaner b1.4b if it is not.

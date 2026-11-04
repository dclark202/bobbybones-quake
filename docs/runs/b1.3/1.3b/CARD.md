# 1.3b: his target choice gets the strategy head's slow memory, one learner, from b1.2d's end

*2026-11-03 (owner), after the review of b1.2 to b1.4 ([docs/reviews/REVIEW_b1.2-b1.4.md](../../../reviews/REVIEW_b1.2-b1.4.md)): "I think I need to scrap what was done in B1.3. Please help me scope what to do in B1.3 instead"; then "OK you can start with the builds"; "I want to drop the B from our bot naming convention. So, this is just 1.3b, 1.4b,c". It replaces b1.3a's copy and b1.4a's blend: the head never copies and nothing is blended. The family: [README](../README.md). What comes after it: [1.4b](../../b1.4/1.4b/CARD.md) (1.4c merged into it).*

**Marks:** ✅ built and tested · ⏳ to build · 🧪 to measure · ❓ owner's decision

## In plain words

Today one small layer picks his target (an item, the enemy, a holding place) from his fast memory, the one that steps every frame. 1.3b gives that same layer a second input: the strategy head's slow memory (score, clock, item timers, the brain's guesses), and lets it be judged over a few seconds instead of about one. The part that reads the slow memory starts at zero, so on the first update he chooses exactly as b1.2d does (0 actions differ). There is one chooser all run: nothing to copy, nothing to blend, nothing to hand over.

## The owner's page

| | |
|---|---|
| Started from | **started 2026-11-03 16:31; stopped 11-04 at update 170 (owner: "strongest boy yet")**; planned to 08:00 (929 minutes) on the owner's word ("Commit and start"; without the last dry run's verdict: `-NoTrial`) · b1.2d's end with its optimizer (`data/sim_runs/duel_gru_b1_2d/keep/policy_end_b12d.pt`, the network on the public servers), the head added new (`tools/head2_init.py add --add 1 --chrono-lo 1 --gate 0 --ctrl-src belief`). b1.3a's and b1.4a's saves are not used |
| Run | `duel_gru_1_3b` |
| What | his target logits = the hands' 17 target rows on the fast memory h **plus** the head's target layer on the slow memory s (`--head2-add 1`). One set of logits, one lesson. The credit for the choice moves from his own advantage (about 1 s ahead) to the head's (λ 0.995, about 5 s, and its two-minute value) over updates 10 to 90 |
| How his target is chosen | scores = W_h·h + b + W_s·s; W_h and b are b1.2d's target rows, W_s starts at zero. Where the head has no state yet (a respawn to its first tick, 0.2 s) the rows alone |
| The hands' target rows | **learn**, as in b1.2d (not frozen) |
| The head | a GRU of 256 that ticks every 0.2 s on the brain, his stack, timers, clock and his fast memory; its memory speeds spread evenly in log from 1 to 300 ticks (median 4.5 s, 40% under 2 s; b1.3a's: median 31 s, 1 unit in 256 under 1 s); its plan into the hands stays shut (gate 0); its value on his whole pay at γ 0.9998 |
| The credit dial (live `H2_PG`) | 0 → 1 over updates 10 to 90 (owner, 11-03: "we should do it for 80 updates"): the target's gradient is (1 − c) × his own advantage's plus c × the head's. Both reach the rows, the fast memory, the head's layer and its GRU |
| The item rule's lesson | stays at b1.2d's weight; it **judges and teaches the hands' rows alone** (11-03, after the first dry run: when it read the sum, the head's correction made it push the rows harder and both parts grew, an arms race); [1.4b](../../b1.4/1.4b/CARD.md) fades it out |
| The two parts may oppose (owner, 11-03: "they should be allowed to oppose each other. The point of the new one is to correct. We just don't want the l1/2 norms blowing up") | an **L2 on both parts, one weight**: decoupled weight decay, AdamW's L2 (`--head2-l2 0.01`, live `H2_L2`): after each step the hands' 17 target rows and the head's target layer shrink by lr × 0.01, about 0.1% an update (an L2 in the loss went through Adam's scaling: the fourth dry run); owner: "Why not just add some l2 regularization"; "I don't see why you would use different weights for the two"): for one sum, training prefers the smallest split, so the parts cannot grow apart. No cap (owner, 11-03: "Just use L2"): a part over 40 is flagged in the watch log (`ramp_13b.py`) and `H2_L2` can be raised live (`--head2-norm-cap 30`: nothing below it). Both sizes, the sum and their cosine are in every update's record (`head2.hands`, `raw`, `sum`, `cos`, `l2`, `norm_cap`) |
| Lock (8 s), contact freedom, switch cost, weapon rule, speed pay on item trips | unchanged; 1.4b takes them out one at a time |
| Copy lesson, mix, blend | none |
| Combat, item and win pay | unchanged |
| Length | **until 08:00 on 11-04** (owner, 11-03: "let the run go until 8am tomorrow, however long that ends up being"): `-Minutes` set at the start to the minutes left to 08:00 (about 945 from 16:15, about 190 updates at 5 minutes) |
| League, checks | anchors: b1.2d's end, b1.1, v0.6.0's end. 200 games (20 a map) every 20 updates against b1.2d's end, every fourth against b1.1; read against the checks' zero point (below). The head blanked (its part out, the rows alone) against b1.2d's end at updates 100 and the end. The panel. Never stopped |
| Cores | the trainer on the 8 performance cores; checks, panel, ramp and logger on 8 efficiency cores (2-5, 10-13); 14-17 left for the owner |
| Kept | every save of the dial with its optimizer (`keep/policy_credit<update>_13b.pt`), the first save at c = 1, the end (`keep/policy_end_13b.pt`) |

## The schedule (a ramp on the update clock; the dial holds while a check says so)

| Updates | What changes | Gates |
|---|---|---|
| 0 to 10 | nothing: he plays and learns as b1.2d; the head's part of the scores starts at zero and learns (c = 0) | an extra first check at update 10 |
| 10 to 90 | c (live `H2_PG`) 0 → 1, +0.0125 an update | hold while a check reads under 50%; step back 10 updates if under 45% or two checks under 50% (each read against the zero point); a dip lasts 20 to 30 updates at most |
| 90 to the end (about 190, 08:00) | c = 1; it settles | checks every 20 updates (100, 120, 140, 160, 180) |

## Before the start

| Step | Where it stands |
|---|---|
| The fixes of the review (B1: each update learns at the mix and gates it played at; B5: the head's term clips around the learner before the update, weight capped at 2, a second clip at 3; `head2head.py` takes each save's own contact) | ✅ 11-03 (CPU smoke from b1.4a's end, 8 updates: the learnt mix the played one every update; the weight 0.99 to 1.00) |
| `sim/head2.py`: the add (`head2.add`, torch and numpy), the memory spread (`chrono_lo`) | ✅ unit test: a new head leaves the logits the same to the bit; torch and numpy agree (1.4e-6); no state, the rows alone; old saves load with add 0; the spread's median 22.7 ticks, 40% under 10 |
| The trainer: `--head2-add`, `--head2-lam`, `--head2-chrono-lo`, the credit split, the league's head with an add | ✅ CPU smoke, 10 updates from the start network with the dial 0 → 1: ALL PASSED (the credit followed the dial; λ 0.995; the head's own scores 0.003 → 0.21; the rows and the head's layer both learnt; no NaN; the save carries add 1; a 2-game check with it finished) |
| `tools/head2_init.py add --add 1 --chrono-lo 1`; the start against b1.2d's end | ✅ 0 actions differ (400 frames, 8 seats, the head's whole numpy path run); with the head's layer set at random: 1,107 differ (the path is live) |
| `make_files.py` (b1.2d's command with the head's arguments); settings check against b1.2d's | ✅ only the head's arguments and the run name differ |
| The checks, the plugin, the export (one numpy function, `np_mix_in`, for all three) | ✅ the plugin's forward pass against the checks' on the smoke's save (`tools/netpass_check.py`, 800 frames of Blood Run, resets, every gate and fade): every difference 0 (actions, logits, log-probs, memory); the head's part live in it (taken out: 103 of 3,200 choices differ). The export carries `head2.add` |
| A game on a private local server (image `qlbot:13b`: the public build plus the head's code; Bobby with the smoke's save against the game's Hardcore bot, Blood Run) | ✅ loads (`ready`), the plugin steps the head with its add (checked inside the container), frames median 7.0 to 7.4 ms (p99 9 to 10), the network 1.8 to 1.9 ms; won 13-2, the mega taken 21 times and the red armor 12 (nearly every spawn). The real inputs against the simulator's (`tools/input_check.py --real --npz`, brought up to date for the brain's pose and the movement branch, 11-03): alive; every difference is the opponent's (the game's bot holds the shotgun and plasma) or the tool's own round clock; none in what the head reads |
| The checks' zero point: b1.2d's end against itself, the watcher's settings, 200 games at seeds 100, 200, 300 | ✅ 11-03 (`data/sim_runs/zero_point_b12d/`): 105-95, 104-96, 98-102: **307-293, 51.2%** (z ≈ 0.6): the checks are fair; the bars stay at 50% (`-Zero 0.5`). No code treats the two sides apart (only their random streams differ; the seats are swapped). B-220's 56% was chance |
| The blanked check (a save played with its head's part out) | ✅ `tools/run/blank_head.py <save> <out>` (head2.add 0), then `head2head.py` against b1.2d's end; checked on the smoke's save (the same answers as a hand-made add-0 copy) |
| `ramp_13b.py` (c 0 → 1 over 10 to 90, the owner's 80 updates; hold under the bar, back 10 updates under 45% or two under the bar; the bars moved by the zero point, `--zero`; the kept saves) | ✅ on fake files: the dial's path, a hold, a lift, a step back and the kept saves as written |
| `start.ps1` (refuses on any settings difference, a dry run not passed, a run folder in use, a start that answers differently, a head path that is not live; then the trainer, the watcher, the ramp, the logger) | ✅ written; runs at the start |
| `dryrun_13b.py`: 10 updates on a scratch copy with the full command (no stall, no NaN, the credit to 1, the scores under 60, his step under 0.1, the head's clip share under 0.3) | **first run 11-03 13:01, ALL PASSED, but:** the head's part grew about 1 an update (0.07 → 9.3) and pointed against the hands' (cosine −0.41 on 9,272 frames of play, the sum 22.4 smaller than the hands' part 24.7, half the top choices overturned): the rule's arms race above. Fixed by the rule on the rows alone, the L2 and the cap |
| The soft cap's pull (CPU smoke, cap 15, weight 0.05) | ✅ the hands' part 19.2 → 13.1 in 10 updates, the cosine near 0 (−0.08 to +0.05) |
| The second dry run, L2 on the head's part only (`scratch_13b_dry2`) | stopped 11-03 at its first update on the owner's word (one weight for both parts instead) |
| The third dry run, L2 0.01 on both parts as first built (on the scores' level too, and reaching his memory) (`scratch_13b_dry3`) | **broke him; stopped at update 4:** the hands' part 22 → 7.3 → 4.0 → 1.8 (targets near random), his step 31 nats at update 1 and 6.6 at update 2 (normal 0.03): the penalty's gradient went through his shared memory |
| The fourth dry run: an L2 of 0.001 in the loss on both, centred, each part's own layer only (`scratch_13b_dry4`) | stopped at update 1: the hands' part 22 → 13.8 in one update (Adam sizes a steady pull's steps by the other gradients' noise, so a small λ still moves the rows fast) |
| **The fifth dry run: decoupled weight decay 0.01 on both target layers** (`scratch_13b_dry5`, 15:47 to 16:27) | **every check passed but one:** his step 0.031 to 0.041 (normal); the hands' part 21.6 to 22.7, never shrunk (the first dry run without any L2: 21.6 to 24.1); the head's part 0.06 → 2.9 (the first dry run: 9.3), the cosine −0.16 to 0 (the first: −0.41). **Failed:** "the head's part levels off": +0.19, +0.88, +0.44 over the last three updates, the +0.88 when this dry run's dial jumped 0.5 → 1 at once (the run's ramp moves 0.0125 an update). Before the dial: +0.06 to +0.36 an update |
| The owner's go and the length | ✅ 11-03 ("Commit and start"; until 08:00); **started 16:31** (`start.log`): settings check PASS, 0 actions differ, the random head layer 1,107 |

## Judged by

| Measure | Wanted |
|---|---|
| Win rate against b1.2d's end | level or better at the end, read against the zero point; no check under 45% |
| The head blanked | plays worse than with it (the head adds something) |
| The head's own scores' centred length (`head2.raw`) | bounded: flagged over 60 |
| The enemy's share of his targets | holds or rises |
| Items a minute, stack at fights, time at spawns | hold (floors from b1.2d's end) |
| No spawn camping, no holding a spot all game | the panel |
| Against b1.1 and v0.6.0's end | holds |
| The owner's play test | |

## The equilibrium

The choice is learnt on his whole pay as b1.2d's was; what changes is what it can see (the slow memory: score, clock, timers, the brain) and how far ahead it is credited (about 5 s plus the head's two-minute value, against about 1 s). In self-play both copies get the same context; the combat and item parts are zero-sum and the win part is the correction both gain from getting right, so the head is paid for choices that win: an item whose timing pays later, a fight when level or ahead, a retreat when behind. On the way: more choices that depend on the score and the clock. The pays still tied to the target (speed pay on item trips only, the switch cost, the claw-back) keep their tilt toward item runs until 1.4b.

## Red team

| Part | Hand-built or assumed | The measured alternative | Watch |
|---|---|---|---|
| The credit dial, 0 → 1 over 80 updates (the owner's) | chosen pace | the head's advantage from the start; the smoke's step sizes | the choice's step per update (`kl`), checks |
| λ 0.995 for the head's advantage | assumed | 0.98 (the hands'), 0.998 | the head's value loss, its advantage's spread |
| Memory speeds 1 to 300 ticks, even in log | assumed | b1.3a's (300, slow) | the blanked check; the share of the scores from s |
| The target's gradient reaches the fast memory with the head's advantage at c > 0 | a choice (as b1.2d's rows did with his own) | h as a number (b1.4a's freeze) | movement, aim and hits in the panel |
| The head's two-minute value is noisy | | | the head's value loss; checks |
| The two parts' sizes | L2 0.01 on both: an assumed strength (live); no cap | no L2 (the first dry run: a steady climb) | `head2.raw`, `hands`, `sum`, `cos`; `H2_L2` up if a part keeps climbing |
| The L2 on the hands' part pulls b1.2d's own scores (size about 24) from update 0: softer choices | at 0.001 about 5% of the main lesson's pull on them; relatively stronger once the rule fades (1.4b). At 0.01 on his memory it broke him (the third dry run) | | the hands' size, his step; `H2_L2` down in 1.4b if his choices go soft |
| An L2 also shrinks corrections that pay | the price of keeping the sizes down | a cap only | the blanked check: the head must still add something |
| The item rule's lesson on the rows | kept | out (1.4b) | |
| The checks' zero point and the seat question (B-220) | 50% assumed until measured | 🧪 three seeds | every gate |
| Pay pathologies (the ledger) | | | negative frags, sign flips, lopsided games |

## Changes on the fly

| Time | Change | Why |
|---|---|---|

## The result

**Stopped 2026-11-04 at update 170 on the owner's word** ("This is awesome, really strong results. I think we can stop him at u170. Absolutely save and log this guy right away strongest boy yet"). End = the save of update 170 (06:50): `keep/policy_end_13b.pt` with its optimizer (`keep/opt_end_13b.pt`), on the backup drive. (The stop tool was started six minutes after that save and waited for update 180's; it was cancelled and update 170's files kept by hand, checked byte for byte against `keep/policy_170.pt`; the trainer was stopped at update 178, before its next save.)

| Update | Credit | Against b1.2d's end | Against b1.1 |
|---|---|---|---|
| 10 | 0 | 120-80, 60.0% | |
| 30 | 0.25 | 139-61, 69.5% | |
| 50 | 0.5 | 154-46, 77.0% | |
| 70 | 0.75 | | 169-31, 84.5% |
| 90 | 1 | 177-23, 88.5% | |
| 110 | 1 | 178-22, 89.0% | |
| 130 | 1 | 168-32, 84.0% | |
| 150 | 1 | | 174-26, 87.0% |
| 170 | 1 | 🧪 playing | |

By map (pooled against b1.2d's end): 72% (Furious Heights, Toxicity) to 83% (Sinister); no weak map. The checks' zero point is 51.2%. The credit dial: no hold, no step-back; 1 at update 91.

| | Start | Update 170 |
|---|---|---|
| The hands' part of his target scores | 22.5 | 17.7 (the weight decay: the rows' weights 16.6 → 13.8, −17%) |
| The head's part | 0 | 8.5 (level from about update 100) |
| The sum | 22.4 | 18.5: his target choice somewhat softer than b1.2d's |
| Their cosine | 0 | −0.10 → −0.21 at update 50 → −0.15: mild opposition, stable |
| His step (kl) | 0.033 | 0.037 |
| Frags a match-minute | 1.61 (update 10) | 1.99 |
| The enemy's share of his targets | 7.8% (update 10) | 7 to 9%: not clearly up (the red armor up to 27%, the mega down 18% → 13%) |

The pay ledger (a player-minute, the end): frags +1.07, deaths −0.98, damage +1.76 / −1.48, speed +0.38, switch cost −0.28, claw-back −0.06, win part about 0: no negative frags, no sign flips, nothing lopsided.

**Not good:** the panel flagged camping near the red armor on Campgrounds (19 to 23% of the time from update 80 on, b1.2d's end 8%) and fewer rockets at mid range (0.23 to 0.27, b1.2d's end 0.37; the lightning gun up 0.50 → 0.63 of the time in hand with the enemy in view). **Not done:** the blanked-head check at update 100 (not wired into the watcher); it runs on the end save after update 170's check 🧪.

# 1.5a: the head contributes to his weapon choice, from 1.3b's end, before anything is faded

*2026-11-04 (owner): "his weapon usage is again converging on LG ... His rocket and rail aim are good, he just needs to use them more";
"ABSOLUTELY D, the head needs to inform the weapon choice"; then, on 1.4b's drift (lightning 0.56 → 0.60 of his time in games, big
weapons owned 1.78 → 1.67 as the item teacher faded, still falling after it ended; checks 52-56% against its start): "Before anything is
faded out, let us introduce having the head contribute to weapon choices. That way we can then fade it out concurrently (or in
succession) with the hard coded teacher, and other fades in 1.4b/c"; the plan: **not continue with 1.4c; start 1.5a from 1.3b's end;
build the head contributes to weapon choice portion; run overnight; then redo the fades as 1.6.** The runs start only on his command.
The family: [README](../README.md). The code: worktree `BobbyBones-15a`, branch `b15a` (built 11-04 for a start from 1.4c's end; the
changes for 1.3b's end are listed under "Before the start"); not started.*

## 1.5a in short

1.5a is **1.3b's run with the item teacher, the speed pay and the 8 s lock still on, plus one new thing: the head contributes to his
weapon choice.** Three small rule costs come out at update 0 as in 1.4b and 1.4c (owner, 11-04 evening: "they should come out at 0"):
the switch cost (a change of target), the weapon override (a weapon he holds may be chosen, for its ammunition) and the blind-fire
cost. The item teacher and the lock wait for 1.6 (owner: "1.6 is really then about dropping the item teacher and the handing over the lock").

"The head contributes to his weapon choice" is three pieces that work together:

| Piece | The problem today | What 1.5a does | What stays |
|---|---|---|---|
| **1. The head adds its scores to the weapon choice** (was "D") | his weapon is chosen by the hands alone, from the present frame: the same lightning gun at 200 units or 1,000. The strategy head (the slow planner that ticks every 0.2 s and already scores which item he goes for, since 1.3b) has no say in his weapon | the head gets a second output: one score per choice of the weapon key (keep the weapon, or switch to one of the nine), **added** to the hands' scores, as its target scores are added since 1.3b. One set of scores, one lesson. It starts at exactly zero, so the start plays as 1.3b's end to the bit. The head also reads 35 new numbers: the weapon in his hand and whether it can fire now, the enemy's weapon in view, what the enemy has been seen with since his last death, the rail and lightning hums he hears, whether the enemy is in view and his last known place. What it can learn: the rail out before the enemy appears at a far doorway, rockets ready for a close corner, the humming weapons away while travelling, an answer to the enemy's weapon, the next weapon before the last cell | the hands keep their own weapon scores, read every frame (the last-moment change: he jumped into close range) |
| **2. The weapon choice judged over seconds, not one second** (was "B") | a switch costs at once (0.4 s without a shot) and pays later; the weapon choice is judged by what happens in about the next 1.25 s, so "never switch" learns faster than "switch when" | the weapon choice's lesson moves to the head's clock: judged over about 5 s with the head's two-minute value, the way his target choice moved in 1.3b. A dial: 0 for the first 10 updates (the trial at 1.3b's credit), then 0 → 1 over updates 10 to 90 (owner, 11-04: "Make the ramp start at u10 and take 80 updates") | his aim, movement keys and trigger keep the hands' 1.25 s |
| **3. League opponents with weapon habits** (was "C") | his league is copies of himself, all on the lightning gun: nothing punishes the lightning gun at 900 units | 30% of the league opponents' lives (about 10% of his games) play with a habit, drawn each life: a third play the pros' weapon for the distance (rockets close, lightning in the middle, the rail far: 3,712 pro demos), a third lean on the rail, a third on rockets (a push of +2 on that weapon while they own it with ammunition). Never his own seat. Against a rail player at range the lightning gun loses; reading the enemy's weapon and the distance pays | the league's networks themselves |

Also in the league: 1.3b's end joins as the control; b1.2d's end (rockets 37% in hand) and v0.6.0's end (rail 26%) stay at their even
share (1.3b's draw; no matchmaking by difficulty until 1.6). Not in it: the game's weapon-switch timing (E2: measured and reported only).

**Why this order:** weapons and items are one loop: he picks up what he uses and uses what he owns. 1.4b showed that fading the item
teacher with the weapon habit unchanged lets ownership fall and the lightning gun rise. In 1.5a the teacher still keeps his rail and
rocket pickups up while the head learns to use them; 1.6 then fades the teacher once owning a rail is worth something to him.

## The schedule

| When | What |
|---|---|
| Tonight, 1.4b's end (about 20:15) | 1.4b ends by itself and is kept (`keep/policy_end_14b.pt`, backup). **1.4c is not started** (owner, 11-04) |
| On the owner's go | the code changes for a start from 1.3b's end (below), then the tests on the efficiency cores (no run trains then): the start answers as 1.3b's end to the bit; the trainer at a fixed seed with nothing new set = 1.3b's; a short CPU smoke with all three pieces on. About an hour |
| On the owner's command | merge `b15a` into `main`; `start.ps1`; 12 hours by default (about 140 updates of 5 minutes), overnight |
| Updates 10 to 90 | piece 2's dial 0 → 1 (+0.0125 an update, about 6.5 hours, at 1 about 7.5 hours in); pieces 1 and 3 from update 0 |
| Update 10 | the first check, 200 games against 1.3b's end: the trial (no dry run) |
| Every 20 updates | 200 games against 1.3b's end; every fourth against b1.2d's end; the panel. Every win rate reported; under 40% flagged at once; never held or stopped (rule 6) |
| Update 50 and the end | the same save with the head's weapon scores switched off, 200 games against 1.3b's end: does the head's part win games? |
| Every hour; 06:30 | the checks, his weapon in hand (rockets, lightning, rail), big weapons owned, the head's part, his frag share against each habit |
| After 1.5a | the report; **1.6: the fades redone from 1.5a's end**, one after the other, each on the owner's word from the reports (below) |

## 1.6 (to plan in its own session: [the 1.6a card](../../1.6/1.6a/CARD.md))

From 1.5a's end (owner, 11-04 evening: "1.6 is really then about dropping the item teacher and the handing over the lock. We'll review
that further in a different session"): the item teacher out, and the lock handed to the keep choice (1.4c's code, in branch `b14c`, under
`b15a`). Still to place: the speed pay and matchmaking by difficulty. Watched through each: big weapons owned, his weapon by distance, rail
and rockets in hand, the head's weapon part, the checks.

**Marks:** ✅ measured or decided · ⏳ to build · 🧪 to measure · ❓ owner's decision

## In plain words

His weapon does not depend on the distance. With the enemy in view he holds the lightning gun about two thirds of the time whether
the enemy is 200 units away or 1,000 (the gun reaches 768); the pros hold rockets close, the lightning gun in the middle and the rail
far. It is a choice he has stopped making, not a preference. The pay is weapon-blind, so the fix is not pay: it is who makes the
choice, on what clock, against which opponents, in a simulator that charges for a switch what the game charges.

Three pieces, all from update 0 (above: 1, 2, 3; in the sections below by their working letters: **D** the head adds its scores,
**B** the weapon choice judged on the head's clock, **C** the league's weapon habits; **A**, the game's switch timing, is out).

## The owner's page

| | |
|---|---|
| Started from | ✅ 1.3b's end with its optimizer (`data/sim_runs/duel_gru_1_3b/keep/policy_end_13b.pt`, update 170: "strongest boy yet", 93.5% against b1.2d's end), the head's weapon part added at zero (owner, 11-04: "Start 1.5a from 1.3b end"; 1.4c not continued) |
| Run | `duel_gru_1_5a` |
| Length | ❓ 12 hours by default (`--minutes 720`), overnight (owner: "Run overnight") |
| New, all from update 0 | the three pieces of "the head contributes to his weapon choice" ✅ (owner). A out: E2 measured and reported only (owner, 11-04) |
| Piece 2's dial | ✅ `H2_WPG` 0 → 1 over updates 10 to 90 (owner, 11-04: "Make the ramp start at u10 and take 80 updates"; `ramp_15a.py`, never held); saves kept at 10, 50, 90 and the end |
| The start | ✅ only on the owner's command (11-04) |
| Everything else as at 1.3b's end | ✅ the item teacher on (`INTENT_TEACH_W` 1), the speed pay (0.125), the 8 s lock (no keep choice); combat, item and win pay; `RAIL_FAR_PAY` 0.25: as 1.3b ended. Their fades: 1.6 |
| Out at update 0 | ✅ (owner, 11-04 evening) the switch cost (`INTENT_SWITCH=0`), the weapon override (`WEAPON_OWN=1`; the checks play each seat at its own), the blind-fire cost (`BLIND_FIRE_W=0`): the settings of 1.4b and 1.4c, identity-checked there |
| League | 1.3b's: anchors b1.2d's end, b1.1, v0.6.0's end (24% of the rollouts, even draw) plus 1.3b's end as the control; his last eight snapshots; piece 3's habit seats. No matchmaking by difficulty (1.6) |
| Checks | 200 games every 20 updates against 1.3b's end, every fourth against b1.2d's end (the servers' network), an extra one at update 10; his seat's weapon numbers alone (the checks pool both seats, B-239); the head's weapon scores switched off at updates 50 and the end. The panel. Never stopped (rule 6) |
| Cores | as 1.3b: the trainer on the 8 performance cores, everything beside it on 8 efficiency cores, 14-17 left for the owner |
| Kept | the saves at update 10, 50, 90 and the end, each with its optimizer |

## What the numbers say ✅

**His weapon with the enemy in view** (the panel, his own seat; pros: the panel's `PRO_FIGHT_HAND`):

| | rockets | lightning | rail | other |
|---|---|---|---|---|
| Pros | 41% | 32% | 14% | 12% |
| b1.0a u10 | 15% | 43% | 27% | 16% |
| b1.1a u180 | 21% | 46% | 14% | 19% |
| b1.2d u80 | 37% | 36% | 7% | 20% |
| 1.3b u10 → u170 | 28% → 24% | 50% → 62% | 8% → 2% | 14% → 12% |
| 1.4b u10 → u30 | 23% | 63% → 64% | 2% | 11% |

**By distance** (share of the big three; the checks, both seats; pros: `docs/pro_tables.json`, 3,712 demos):

| Enemy at | Pros RL / LG / RG | v0.6.0's end | 1.4b u30 |
|---|---|---|---|
| under 300 | 59 / 34 / 7 | 20 / 51 / 30 | 30 / 68 / 2 |
| 300 to 700 | 36 / 43 / 21 | 19 / 52 / 29 | 28 / 70 / 2 |
| over 700 | 21 / 17 / 62 | 20 / 49 / 31 | 28 / 70 / 2 |

**In training** (`metrics.jsonl`, time in hand in games and frags by weapon):

| | rockets | lightning | rail | lightning's frags |
|---|---|---|---|---|
| b1.2d, updates 11 to 80 | 36-38% | 38-40% | 4-5% | 48-52% |
| 1.3b u11 → u178 | 36% → 25% | 40% → 57% | 3% → 2% | 52% → 77% |
| 1.4b u4 → u47 | 24% → 24% | 58% → 58% | 2% → 2% | 76% → 79% |

- **Flat with distance in every run since at least v0.6.0.** v0.6.0 was varied but just as flat: a fixed mix, not a choice.
- **The rail slid in every run** (27% → 2% in view), through b1.2d's doubling of `RAIL_FAR_PAY`: a pay for one weapon did not hold it.
- **The lightning gun's rise was 1.3b**, while the head's credit took over his target choice; 1.4b has held it flat for 47 updates.
- **His aim with the rail and rockets holds**: rail hits 34-43% in 1.4b's training, rockets 47%.
- **Out of view** the pros travel on rockets (57% of travelling time; rail 12%, lightning 9%: both hum and give them away). His: 🧪 E1.

## Why: five causes, and what tells them apart

| | Cause | Decided by |
|---|---|---|
| H1 | **Fidelity**: the simulator waits for a reload before a switch starts (Quake 3's rule, `cool = max(cool, fire_cd + SWITCH)`; B-37, never measured in Quake Live). After a rail shot nothing else fires for 1.5 + 0.425 s, after a rocket 0.8 + 0.425 s, after the lightning gun 0.05 + 0.425 s. If the game lets a switch start during the reload, every rail-then-finish and rocket-then-lightning combination is dearer in training than in the game | E2 |
| H2 | **Credit**: the weapon key is a hands' output credited by the hands' advantage (λ 0.98, ~1.25 s). A switch costs at once (0.425 s without a shot) and pays later, so "never switch" learns faster than "switch when" | E3, E4 |
| H3 | **Self-play collapse**: his league is his own selves, none of which ever chose by distance, so nothing punishes the lightning gun at range | E4 |
| H4 | **Ownership**: he does not own the rail (Campgrounds' never taken, B-286) rather than not selecting it | E1 |
| H5 | **Aim by weapon**: if his rail sits further below the pros' than his lightning gun does, the best split for his hands leans to the lightning gun; then it is the aim calibration (the fairness limits stay; the owner's call) | E5 |

## The four parts

| Part | What | Taken from | Build |
|---|---|---|---|
| **A** (out of 1.5a) | **the game's weapon switch**: the simulator's switch rules set to the game's measured ones. E2 is measured and reported only (owner, 11-04); a later run if it finds a gap | the project's rule: the simulator first | not built |
| **B** | **the weapon key's credit on the head's clock**: the key stays the hands' (it reads the present frame: the rule of 11-03), its credit moves from the hands' advantage (λ 0.98, ~1.25 s) to the head's (λ 0.995, ~5 s, its two-minute value), a live dial as `H2_PG` was for the target. His aim, keys and fire keep the hands' credit | 1.3b (the target's credit moved the same way); AlphaStar's and Pluto's strategic choices credited on their own, slower clock | ✅ built: `--head2-wpg`, live `H2_WPG` (c): the main term keeps 1 - c of the key's gradient; the head's own clipped term (the head's advantage, its second clip, decoupled weights as the target's) gets c, on the frames his hand read the key; the record `weapon` (credit, frames, term, clip share, step) |
| **C** | **weapon habits in the league** (B-299's leaners, extended): 30% of the frozen league seats' lives (about 10% of his games), drawn per life (and for each seat's first life): a third "pro hand" (+2 × the pros' share of each owned weapon with ammunition: by the distance in 50-unit bands in view, `docs/pro_tables.json`; their travelling hand out of view, `sim/pro_hand.json`), a third rail leaners, a third rocket leaners (+2 on that weapon's score while owned with ammunition). Never his own seat. Matchmaking by difficulty sends more games to whichever beats him | AlphaStar's league, its human-data strategies (the statistic z) carried by opponents only | ✅ built: `--habit-p 0.3 --habit-push 2 --habit-kinds pro:1,rg:1,rl:1`, live `HABIT_P`, a random stream of its own; the record `habit` (league frames and his frags for and against, by habit) |
| **D** | **the head informs the weapon choice**: below | Pluto's action then target; AlphaStar's action-type head on the core's memory | ✅ built: `sim/head2.py` (`winp`, `wsc`, `wadd`, the inputs `wobs`), the trainer, the checks' numpy player, the plugin's forward pass, `tools/weapon_init.py` |

## Part D: the head informs the weapon choice

### Why the head, not more of the hands

A weapon is a plan for a fight, and the fight's shape is known before it starts: where the enemy will come from and how far, what he
holds, what he has, whether there is time to switch. The hands see the present frame and decide every tenth of a second; they are right
for the trigger and the last-moment change (he jumped into close range). The head carries the slow picture: the brain's enemy, where he
will appear in 1, 2 and 4 s, the item race, the score and clock. Today the head steers his target and only touches his weapon through
which item he goes for. The pros' weapon in hand changes with distance and with time since the enemy was seen; his does not with
either, which is the signature of a choice made on the frame alone with a 1.25 s credit.

### What it is

| | |
|---|---|
| The output | one new layer on the head's memory (`sim/head2.py`: the GRU of 256 that ticks every 0.2 s) giving 10 scores, one per choice of the weapon key (no press and the nine weapons) |
| How it acts | its scores are added to the hands' weapon-key scores, held from one tick to the next (two key readings), as its target scores are added to his target choice since 1.3b (`head2.add`). One set of scores, so the head and the hands never pull on two separate choices (b1.2a's blowup) |
| Its start | the layer at exactly zero: he plays as 1.3b's end, proven by `same` (0 actions differ, memory the same to the bit) |
| What the hands keep | their own rows, read every key reading on the present frame: distance now, the enemy in view, ammunition, reload. The rule of 11-03: a chooser reads what its choice depends on, at the rate it chooses |
| How it learns | one set of weapon-key scores (the hands' rows + the head's part, both with their gradient), one lesson: the main term at 1 - c and the head's own weapon term at c (part B's dial), the head's advantage (λ 0.995, ~5 s) and its two-minute value; decoupled weight decay at `H2_L2` (0.01) on both parts, the hands' ten weapon-key rows and the head's `wsc`, as on the target's two parts (the owner's one coefficient, 11-03; new for the hands' weapon rows: about 0.1% an update); no entropy bonus of its own (the weapon key's bonus stays, 0.5 of the coefficient) |
| Its inputs' layer | the 35 new inputs go through a layer of their own (`winp`, at zero) added to the head's input layer: 1.3b's weights untouched, the start the same to the bit |
| Its memory | the head's own; a tick's input is a number (no gradient into the brain or the hands through it), as today |

### What it reads: today's inputs and what is added

| | Today (`OBS_SEL`, the brain, the readouts) | Added for D (new columns at zero weight: no change at the start) |
|---|---|---|
| His own weapons | owned, ammunition | **the weapon in his hand** (`holding ...`, 9) and whether he can fire it now (reload or switch under way) |
| The enemy's weapons | only what the brain and the hands' memory carry implicitly | **`enemy holds ...`** (9, in view), **`enemy seen with ...`** (9, since his last death), **the hum heard** (rail, lightning: 2) |
| The enemy's place and future | the brain's readout now (27 + 28: place, zones, speed, direction) and ahead (where in 1, 2, 4 s, what he goes for, when he appears) | **the enemy noticed in view, seen or heard recently, and his last known place** (forward, left, up from him: exact in view, rough when heard; 5 inputs the hands have). Built in place of the two distances to the readouts' places: the head reads those places already and the distance is a function of them |
| Stacks, items, clock | health, armor, mega and red armor, the clock and score, item times, his target | |

### What it should learn (and what the pros do)

| Moment | The pros | What the head's part makes possible |
|---|---|---|
| The enemy expected far (over 700) | rail 62% | the rail out before he appears at a far doorway, not after the first glimpse |
| The enemy expected close (under 300) | rockets 59% | rockets ready for a corner or a stacked enemy coming in |
| Travelling, enemy unseen 5 to 15 s | rockets 63%, rail and lightning 12% (both hum within 500 units) | the humming weapons away: he is not heard standing still |
| The enemy holds the rail at range | (E6) | close in with rockets or break the line, not trade lightning at 900 units |
| Holding an angle (B-273) | the pros' holds (`sim/pro_holds/`) | target "this holding place" plus weapon "rail", both the head's: "stand here with the rail, looking where he appears". A reached hold is re-drawn at every reading (the keep choice does not decide there: checked 11-04), so it lasts while his target scores keep naming it; since 1.4b nothing charges him for standing still; the watch and pre-aim pays already pay for facing the spot at a sighting |
| Out of ammunition soon | | the next weapon chosen before the last cell, and its pickup as his target (the weapon override is out since 1.4b) |

### The open question: will it ever see a switch to learn from?

The head's part starts at zero and learns only from switches the hands make. If his odds of the rail at range are near zero (E3), it
has nothing to learn from: "a switch that starts at never is not found by trying" (the legs, 2026-10-10). Three things feed it in this
run: C's opponents make the lightning gun at range lose; B's longer credit lets a switch's payoff count; the key's own exploration bonus.
If E3 finds a dead end, the alternative ❓ is AlphaStar's start from human play: the new layer fitted, small, to the pros' choice for the
distance and the weapons owned (a fitted start: a full level check first, the 2026-10-11 rule), in place of zero.

### Builds ⏳

| | |
|---|---|
| `sim/head2.py` | ✅ `wsc` (10 scores on the state), `winp` (the 35 inputs `W_OBS`, the part `wobs` at the end of u), the buffer `wadd` (0 for a save without it), `pre()`, the held scores in `State`, `w` in `seq()`, numpy `np_wadd` / `np_tick`; a unit check: the part at zero leaves the head's state the same to the bit, the rollout's held scores = the learning pass's, numpy = torch |
| The trainer | ✅ the head's scores added to the weapon key's logits (rollout and learning passes, with their gradient); the key as played (`b_lpw`), its proximal log p and weight; B's dial; the part in its own optimizer group after the keep choice's (1.4c's optimizer loads into the groups before it); league files without it get it at zero (add 0); the L2; the records `weapon` and `habit` |
| `tools/weapon_init.py` | ✅ `add` (the part at zero, `wadd` 1, the optimizer copied) and `same` (0 actions differ, memory and head state the same to the bit; random scores reach the weapon key alone; at add 0 the same again) |
| The checks | ✅ `sim/test_suite.py` plays each seat's own part; `--head2-wadd 0` in `tools/duel_eval.py` and `ws_eval.py` (the blanked check, `blank_check.py`); `dump_eval.py` records his weapon key's chances (E3) |
| The plugin and the export | ✅ `plugins/netpass.py` adds the scores; `sim/export_duel.py` carries every `head2.` key already. Not yet tried on a server: before any play test or push (b1.2d stays on the servers) |
| Checked: a reached hold | **it is a forced re-decision** (11-04, `sim/duel_env.py`: `forced_` includes `intent_done`, which `note_holds` sets while he stands at the place): at a hold the keep choice never decides, his target is drawn again at every reading (once a second) and stays the hold only while the draw names it. "Rail at a holding place" therefore rests on the head's target scores naming the hold again and again, not on the keep choice. Changing it is a simulator change (a hold reached stays keepable): not in 1.5a; ❓ the owner's call for a later run |

### Measured by

| Measure | Wanted |
|---|---|
| The head's weapon part: its size, its step, how often its top weapon is the one he holds | grows, bounded |
| The blanked check (its weapon part at zero) at updates 50 and the end | the head's part wins games: it adds something |
| His weapon at a sighting, by the distance he expected (the brain's) and the distance it came at | the curve bends toward the pros' |
| Switches in the 2 s before a sighting, beside the pros' (E6) | up from about nothing |
| Rail or lightning in hand while travelling with the enemy unseen | toward the pros' 21% |
| Time at holding places with the rail, frags from there; the holds' share of his time | rail at holds up; no rise like 10-12's (places at 5% of readings were 22% of his time) |
| His weapon against the enemy's | answers the leaners as the pros answer each weapon |

## Before the start

**Step 0: measurements, no run changed.** Each is a side job: the owner decides whether it runs beside a run (CLAUDE.md rule 9). The
proposal for all: cores 14-17 (mask `0x3C000`), idle priority, no graphics card (`CUDA_VISIBLE_DEVICES=-1`), as the level check of 11-04
(80 games in 27 minutes there). They share nothing with the trainer (`0xC03C3`) or the watcher (`0x3C3C`), but take the cores left for
the owner's own play. E2 needs a game server, so a window with no training at all.

| | What | How | Length | Answers |
|---|---|---|---|---|
| E1 🧪 | **Owning against choosing** | the start network (1.3b's end) against itself, 100 games: time owning each big weapon; his weapon given what he owns, by distance, in and out of view; the first weapon after a spawn (pros: rockets 52%, lightning 28%, rail 20%); his seat alone | ~45 min | H4; out-of-view hand |
| E2 🧪 | **The game's weapon switch** | private server, `plugins/weaponlab.py`: a switch started during each weapon's reload (B-37); the switch time per pair; the lightning gun's reach and knockback | 1-2 h, between 1.4c's end and the start | H1, part A |
| E3 🧪 | **Does he ever try?** | his weapon key's odds of the rail with the enemy over 768 and the rail owned, of rockets under 300 with them owned | ~30 min | H2; D's start |
| E4 🧪 | **The decider: does the pros' choice win in the simulator?** | his network against itself, 200 games an arm, one seat's weapon key replaced by a rule: (a) the pros' likeliest weapon for the distance among those owned; (b) only "no lightning beyond 768"; (c) only "rockets under 300 if owned". A win is proof the simulator pays for switching; a loss is not proof it does not (his hands never trained with those weapons there) | ~1.2 h an arm | H1-H3 |
| E5 🧪 | **Aim by weapon against people and pros** | hits by weapon and distance: the checks; his public-server games (the game's per-weapon table, `player_stats`); people there; the pros' demos; which weapons people kill him with | 1-2 h, one core, logs only | H5; where people beat him |
| E6 🧪 | **The pros' targets** (B-299 step 1) | from the demos: switches a minute in view, switches before a sighting; their weapon against the enemy's and the distance; the same for people on the servers | 1-2 h, one core | the measures' references |

**The owner's choice (11-04): E1 and E3 on cores 14-17 (idle priority, no graphics card) when he says, E2 measured and reported only (A out
of 1.5a), E4, E5, E6 not now. Nothing scheduled ("just do the code build").** E1 and E3 would run on 1.3b's end (the start): `step0.py`, 100 ten-minute games
against itself, his weapon key's chances recorded (`dump_eval.py`'s `wkp`).

| Step | Where it stands |
|---|---|
| The code: worktree `BobbyBones-15a`, branch `b15a` (from `b14c`: 1.4b's and 1.4c's code is under it, each part unset = 1.3b's play, identity-checked then), built 11-04 during 1.4b (no change to either run); merged into `main` at the start (`b14c` first: its changes off in 1.5a's command) | ✅ built for a start from 1.4c's end; not committed |
| **The changes for a start from 1.3b's end** (owner, 11-04 evening: "Please start with the code build now") | ✅ built 17:45: the weapon part runs without the keep choice (the trainer and `weapon_init.py`; the optimizer saved by 1.5a itself, its weapon group after the head's, reloads on a restart); `make_files.py` from 1.3b's command with only `--head2-wpg 0` and the three habit flags added (`--head2-l2 0.01` is 1.3b's): the settings check PASS against 1.3b's command, and against 1.3b's end only its live dials differ (`CONTACT_FREE`, `LEVEL_PULL`, `RAIL_FAR_PAY`: carried in live.json and checked, as in 1.4b); `start.ps1` from 1.3b's end (1.3b's dials at their ends, its anchors plus `anchor_13b.pt`, the watcher's control 1.3b's end; not run: the start on the owner's final approval); `ramp_15a.py` and `blank_check.py` against 1.3b's end |
| The tests (`tests.py`, 11-04 18:24 to 18:59 after 1.4b's end, on cores the 1.4b watcher did not use; logs in `BobbyBones-15a/docs/runs/1.5/1.5a/tests/`) | ✅ **start**: 1.3b's end given the weapon scores answers as it to the bit (memory, head state, every action); random scores change the weapon key alone (406 of 3,200 draws, the rest 0); at add 0 the same again. **ident** (the trainer at a fixed seed, 2 updates, a league snapshot in every arm): it repeats itself to the bit; 1.5a's code with nothing new = the code under it, both updates; the scores at zero = 1.3b's play in update 1; habits at 0 = none; at 1 the league seats' weapon key differs from frame 0 while his seats stay the same until frame 19 (from there the simulators' shared random stream). **l2** (--head2-l2 50 against 0, 24 steps): the hands' weapon rows 0.8869, the head's weapon scores 0.8868, the hands' target rows 0.8867, the head's target scores 0.8865 (expected 0.886); the other rows 1.0000, the head's value 0.9998. **launch** (1.5a's own command made small, 3 updates): the three settings and the flags in, credit 0, the scores learning from update 1, habits at 0.3, the save carries `WEAPON_OWN=1`. **smoke** (all on, 317 short updates, --overlap): credit 1 every update, its step 0.001 to 0.018, the head's weapon scores 0.04 → 0.30 and its part's size 1.46 against the hands' ~20 (cosine about 0), the hands' weapon rows steady (10.88: the L2 small), habits' league frames by kind (pro 89k, rail 68k, rockets 86k), no NaN; the save and its snapshots carry the part; a one-map check and one with the weapon scores off finished. First tries: the worktree lacked the compiled simulator (`sim/qsim.dll`, git-ignored; copied, identical), and the start test and the habit check had faults of their own (fixed) |
| A dry run | none (owner, 11-04: small, identity-checked changes start directly; the first 10 updates and the check at update 10 are the trial) |
| The owner's command and the length | ❓ |

## Judged by

| Measure | Wanted |
|---|---|
| Win rate against 1.3b's end; against b1.2d's end | level or better: variety is not the goal, winning is |
| Weapon by distance, his seat alone, beside the pros' | the curve bends: rockets up under 300, rail up over 700, lightning beyond 768 toward zero |
| Rail and rockets in hand in view; frags by weapon | up from 2% and 23%; the pros' 14% and 41% are a reference, not a target |
| Switches a minute in view | toward the pros' (E6); no flicker |
| Part D's measures | above |
| Aim and hits by weapon | hold |
| The league table, the habit seats' rows | no network he loses ground to; the habit seats not beaten more easily than his selves |
| Speed, items, the mega and red armor first (1.5's standing watch) | hold |
| The owner's play test; people on the servers | does he change weapons in a fight; do people still kill him at range with the rail |

## The equilibrium

No part changes the pay; combat, item and win pay stay zero-sum and weapon-blind. **A** makes each weapon worth in training what it is
worth in the game. **B** changes how fast he can find the best answer, not what it is (λ trades bias for noise). **C** moves the best
answer from "best against himself" to "best against a mix that includes the pros' choice": against a rail player at range the lightning
gun loses, against a rocket player close it loses ground, so reading the enemy and the distance pays. **D** lets the choice be made
from what he knows before the fight, at the rate a plan changes: a held angle with the rail pays only if the enemy comes through it and
costs the item timing given up, and in self-play the other copy learns to come another way, so the weapon and the angle must follow what
he knows of the enemy, not the map. On the way: more switches before and in fights, short dips while his hands learn weapons at new
distances. In the long run he wins more because the weapon follows the fight.

## What AlphaStar and Pluto give, and where we differ

| Part | They | We take | Differs because |
|---|---|---|---|
| A varied league | AlphaStar: main agents, exploiters, PFSP; strategies kept varied by a statistic z drawn from human games | C: habit seats, one of them the pros' choice; PFSP on since 1.4b; the varied old anchors at a floor | one PC: no exploiters (parked, owner 11-03); z only on opponents: on his own seat z needs a pay for following it |
| The action type from the core | AlphaStar: the action type chosen from the core's memory, its arguments after it; Pluto: action, then target, 4 a second | D: the head's memory scores the weapon, the hands keep the frame-level part | the head adds, never replaces (b1.3a: a swap won 37%) |
| A choice credited on its own clock | both: strategic choices learn on their own, slower time scale | B | |
| Human data | AlphaStar: supervised start and a KL to it all through | D's alternative start only, if E3 finds a dead end; no standing KL | the owner's method: what stays must hold without it; the old weapon teacher made caricatures (B-198) |
| A guess of the opponent | Pluto: an output guessing the opponent | D reads the enemy's weapon; C gives a reason to | the enemy's weapon is an input, not a guess |

## Not in it

| | Why not |
|---|---|
| A pay for rail or rocket damage, a cost on the lightning gun | a single behaviour's pay; the rail's own pay was doubled in b1.2d and the rail fell anyway |
| A pay or count target for switches | PPO farms it (B-299) |
| Style lives for his own seat (`STYLE_P`, built, off since v0.3) | it pays the style's weapon and named it at every distance: caricatures (B-198) |
| Rail-only or rocket-only rounds | changed nothing in 2026-10-10's arm (B-210) |
| A standing pros' weapon teacher | the fallback only, faded, if this run does not bend the curve |
| The hunt among the brain's zones, the look point out | ❓ to a later run of the family |

## Red team

| Part | Hand-built or assumed | The measured alternative | Watch |
|---|---|---|---|
| Four parts at once | the owner's call (11-04) | one at a time | A and B cannot be told apart; C by the league table; D by its blanked check |
| E4's rule | the pros' choice played with his hands, which never trained with it there | E4 again after this run | a loss is not proof |
| The pros' table as reference and as the pro-hand seat | the pros' aim, not his | | win rate first |
| B's 5 s credit on a key read every 4 frames | assumed, from 1.3b | λ 0.99 for the weapon key | weapon flicker, empty-hand time, his step |
| D's scores held 0.2 s in a fast fight | assumed harmless: the hands' rows answer every reading | the head ticking faster | switches in close fights |
| D's start at zero | assumed: C and B make switches happen | the pros' choice as a fitted start (level check first) | E3; the head's weapon part's size by update 30 |
| The head now scores two choices from one memory and one value | AlphaStar's one value for all its heads | | the target choice's measures (1.3b's) hold |
| C's +2 and 30% | B-299's numbers, set by hand | a smaller share | the league table; the record `habit`: his frag share against each habit |
| C's pro hand by the simulator's distance in view, the pros' travelling hand out of view | the pros' table is by distance only, not by what they owned; renormalised over the weapons the seat owns | the pros' choice given ownership (E6) | |
| The L2 now on the hands' ten weapon-key rows too | the owner's one coefficient for both parts (11-03), extended to the weapon key; 0.01: about 0.1% an update | none on the rows | the rows' size in the record (`weapon.w.rows`) |
| The varied anchors' floor | assumed: PFSP starves what he beats | PFSP alone | their rows |
| `RAIL_FAR_PAY` 0.25 stays | a single behaviour's pay, still on | out after this run | ❓ |
| `LG_DEAF`, the hum (500 units) | from the game's sound files (10-22) | E2 can check the hum's reach | |
| Pay pathologies (the ledger) | no pay change | | negative frags, sign flips, lopsided games |

## What 1.4b showed (why the order changed, 11-04)

1.4b's item teacher faded out over updates 10 to 70 (done by update 85). In training his big weapons owned fell 1.78 (update 10) → 1.70
(update 90) → 1.67 (update 107), still falling after the fade ended; the lightning gun's share of his time in games rose 0.56 → 0.60; the
rail stayed at 0.02, rockets 0.23 to 0.26. The checks did not collapse (52.5 to 56.0% against its start; 90.5% against b1.2d's end at
update 70): a slow drift, not a crash, which the teacher's fade uncovered and will not undo by itself. Hence (owner): the weapon choice
first, with the teacher still on (1.5a); the fades after (1.6). 1.4c is not continued.

## E1 and E3 on 1.3b's end (the start), 11-04 18:30 to 19:15 ✅

100 ten-minute games against itself on the ten maps, his seats' frames every 4th (639k frames alive), cores 14-17
(`step0.py`; `BobbyBones-15a/data/sim_runs/scratch_15a_step0/out_13b_r2/step0.json`).

| E1: owning against choosing | rockets | lightning | rail |
|---|---|---|---|
| owned with ammunition (alive) | 80% | 69% | 28% (all three: 22%) |
| in hand, enemy in view / out of view | 24% / 24% | 61% / 57% | 2.2% / 1.7% |
| in hand in view by distance under 300 / 300-700 / over 700 (pros: rockets 59 / 36 / 21, lightning 34 / 43 / 17, rail 7 / 21 / 62) | 25 / 23 / 23% | 59 / 62 / 58% | 2.2 / 2.2 / 1.6% |
| in hand given he owns it, by distance | 29 / 28 / 28% | 82 / 84 / 82% | 7.3 / 6.8 / 5.6% |
| in hand owning all three, by distance | 9 / 8 / 8% | 80 / 84 / 80% | 0.4 / 0.7 / 0.6% |
| the first big weapon in hand after a spawn (949; pros: rockets 52%, lightning 28%, rail 20%) | 61% | 30% | 9% |

| E3: does he ever try (his chance of pressing the key at a reading, 10 readings a second) | readings | mean | over 5% | presses a second |
|---|---|---|---|---|
| the rail, enemy in view over 768, the rail owned and not in hand | 1,717 | 0.18% | 0.6% | 0.018 |
| the rail, 500 to 768 | 5,937 | 0.07% | 0.3% | 0.007 |
| rockets, enemy in view under 300, owned and not in hand | 23,380 | 0.36% | 1.3% | 0.036 |
| the lightning gun, over 768, owned and not in hand | 873 | 2.0% | 6.3% | 0.20 |

**What it says.** It is choosing, not owning (H4 is a small part): owning the rail he holds it 6-7% of the time in view and no more at range;
owning all three he holds the lightning gun 80-84% at every distance. His odds of reaching for the rail at range are close to never: about
one press in 55 seconds of that state, against one in 5 seconds for reaching for the lightning gun there. In a 1.5a update that is of the
order of two rail presses at range across all his seats (the state is 0.27% of his frames) and about a hundred for rockets close. The
head's weapon scores start at zero and learn from what he does: they also learn when the lightning gun at range loses (the habit
opponents), which moves weight away from it to every other choice, but the rail at range starts from very thin evidence. The fitted start
from the pros' choice (decision 3) is the alternative; a level check first. Watched in 1.5a: his chance of the rail at range and of rockets
close, update by update.

## The owner's decisions ❓

| | |
|---|---|
| 1 | Step 0: E1 and E3 on cores 14-17 (owner, 11-04), when he says (on 1.3b's end); E2 measured and reported only (A out). The tests and E1/E3: not scheduled ("just do the code build") |
| 2 | ✅ B's dial: 0 → 1 over updates 10 to 90 |
| 3 | D's start: zero (built) or the pros' choice as a fitted start, decided by E3 (a fitted start needs a level check first) |
| 4 | The length (12 h by default) and the start: on the owner's command |
| 5 | The hunt among zones and the look point: a later run of the family |
| 6 | A reached holding place stays a forced re-decision (checked 11-04): leave it, or make a reached hold keepable in a later run |

## Changes on the fly

| Time | Change | Why |
|---|---|---|

## The result

Not started.

# 1.4b: the hand-written pieces on his target choice out, with matchmaking by difficulty, 12 hours

*2026-11-03 (owner): the schedule of 1.3b and 1.4 ("Please sketch out the schedule for B1.3 and B1.4 under the proposed changes"); first one run of about 24 hours with five steps; then, the same evening: the item rule's lesson "is the meat of the run ... updates 10-70"; "I'm tempted to just remove speed pay all together" ("fade speed pay 70-90"); the switch cost "can just go"; the weapon rule: "He should be able to decide 'oh I need rocket ammo the most right now' and go get the ammo. He should not be rewarded in any way for pathological behavior that boils down to repeatedly picking up the same weapon"; "We can make the lock into a separate run 1.4c, it needs more working"; "this will start in the morning and should be given the standard 12 hours". The family's goal stands: "B1.4 - fade OLD rules out"; combat, item and win pay stay ("I view the win pay as the correction factor on top of those"). Starts only if [1.3b](../../b1.3/1.3b/CARD.md) passes. The lock: [1.4c](../1.4c/CARD.md). The family: [README](../README.md).*

**Marks:** ✅ built and tested · ⏳ to build · 🧪 to measure · ❓ owner's decision

## In plain words

The network does not change. What comes out are the hand-written pieces around his target choice: a rule it is taught to copy (the meat of the run), a cost on every change of target, a rule that turns some weapon choices into "nothing", and the pay for speed on the way to an item. His league opponents are drawn more often where he does worse against them. The 8 s lock stays (1.4c).

## The owner's page

| | |
|---|---|
| Started from | **2026-11-04 08:15** · 1.3b's end, update 170 (owner: "strongest boy yet"; 84 to 89% against b1.2d's end from update 90 on, 87% against b1.1), with its optimizer (`data/sim_runs/duel_gru_1_3b/keep/policy_end_13b.pt`) |
| Run | `duel_gru_1_4b` |
| Length | **12 hours** (`--minutes 720`; owner, 11-03: "the standard 12 hours"); about 145 updates at 5 minutes an update |
| How his target is chosen | as at 1.3b's end: one set of scores, the hands' rows plus the head's part, one lesson, the head's credit (`H2_PG` 1); the L2 on both parts stays |
| Combat, item and win pay | unchanged |
| League | anchors: 1.3b's end, b1.2d's end, b1.1, v0.6.0's end (24% of the rollouts), and his last eight snapshots; the draw by difficulty from update 0 (below) |
| Checks | 200 games every 20 updates against 1.3b's end, every fourth against b1.2d's end (the servers' network), and an extra one at update 10; read against the zero point (50%, b1.2d's measure: below). The head blanked at the end. The panel. Never stopped |
| Cores | as 1.3b: the trainer on the 8 performance cores, everything beside it on 8 efficiency cores, 14-17 left for the owner |
| Kept | the save at each step's end with its optimizer (`keep/policy_u10_14b.pt`, `_u70_`, `_u90_`), the end (`keep/policy_end_14b.pt`) |

## The schedule

| Updates | What | Dial | Where it stands |
|---|---|---|---|
| 0 | **the switch cost out** (0.02 a change of target → 0; today −0.30 a player-minute, paid by both copies alike) | `INTENT_SWITCH=0` in the command | ⏳ a setting in place of the constant (`duel_env.py:458`) |
| 0 | **the weapon override out**: a choice of a weapon he holds with a pickup's worth of ammunition is no longer turned into "nothing"; he may go for any weapon's ammunition when he judges it worth it. Kept: taking the weapon he chose ends the choice (a release, as for every item taken), so a taken weapon never stays his target pointing at its spawn (v0.4.4's camping) | `WEAPON_OWN=1` in the command (with `WEAPON_FREE=1` as today) | ⏳ |
| 0 to 10 | **matchmaking by difficulty** ([BACKLOG B-300](../../../BACKLOG.md); AlphaStar's prioritised fictitious self-play): each rollout's league opponent drawn by (1 − his frag share against it)², a floor of half the even share each, within the snapshots and within the anchors (the anchors' 24% kept). The checks' opponent (1.3b's end) keeps its even share: weighting it up when he loses to it would train him toward the gate | live `PFSP` 0 → 1 | ⏳ the trainer's draw, a running frag share per league file, the league table |
| 10 | an extra check | | |
| 10 to 70 | **the item rule's lesson out**, the meat of the run (owner: "updates 10-70"): his target is then learnt from pay alone | live `INTENT_TEACH_W` 1 → 0 (a factor on the rule's weight, its floor included) | ✅ live already |
| 70 to 90 | **the speed pay out** (today +0.35 a player-minute, less 0.06 given back from trips he abandons) | live `SPEED_PAY` 0.125 → 0 | ✅ live already |
| 90 to the end (about 145) | settles | | |

**Gates: none from update 21 (owner, 2026-11-04: "Don't hold the ramps just go forward with them").** The dials go forward on the clock; every check's win rate is reported, one under 40% flagged at once as a major problem; the owner decides to hold or stop. (Until update 21 the ramp held under 50% and stepped back under 45% or two checks under 50%; it never fired. The ramp restarted at 10:11 with `--free --resume`.)

**Not on this card:** the way pay (`INTENT_SEEK_W`) is already zero (`--item-reward 0`). With the speed pay out, the claw-back of abandoned trips has nothing left to give back. The dead rule code stays until its own bit-identical proof, apart from a run.

## Before the start

| Step | Where it stands |
|---|---|
| 1.3b passed its marks | ✅ 11-04: stopped at update 170 (owner: "strongest boy yet"); its last check 93.5% (187-13) against b1.2d's end |
| The code (worktree `b14b`, branch `b14b`) merged into `main` after 1.3b's trainer and watcher stop (its checks re-import the simulator) | ✅ 11-04 08:13 (1.3b's blanked-head check was still running: the new code with the settings unset is the same to the bit) |
| `INTENT_SWITCH` and `WEAPON_OWN` as settings, each identity-checked; `WEAPON_OWN` a `PLAY_VAR` and per seat in the checks (`--wown` / `--opp-wown` from each save's own settings; the panel carries it) | ✅ 11-03 (`ident.py`, Blood Run and Aerowalk, 3,000 frames: unset, and a seat array of 0, the same to the bit as before; `INTENT_SWITCH=0` the game the same and the pay up by exactly 0.02 a charged change, 377 and 510 of them; `WEAPON_OWN=1` none of the 83 and 54 held-weapon readings turned into "nothing": ALL PASSED) |
| A weapon or ammunition pickup pays nothing | ✅ (the big weapons' pay, `BIG_PICK_SEQ`, is once a life and never for a weapon he held; the way pay 0; `SPEED_PAY_RUN` pays 0 in games: the smoke's `speed_pay_run_per_player_min` 0.0) |
| How often 1.3b chooses a weapon he holds | ✅ about never: 0 of the opponent's 549 readings in the smoke's check (2 short games; random choices: 3 to 4%); the league keeps the learner's setting in training |
| Matchmaking: the draw, the running frag share per league file, live `PFSP`, the fixed share of the checks' opponent, the league table, off = today's draw | ✅ 11-03: `sim/league.py`, the trainer's `--pfsp`, `--pfsp-fixed`, `--league-table`; off makes exactly today's random calls. CPU smoke (`smoke.py`, 145 short updates, the dial at 1): every update recorded its opponent, frags and win part; the fixed anchor at 0.12 (the even share of two); the snapshots' chances 0.05 to 0.20 by the table; the table written (16 files); a save loads and a check with each seat's own `WEAPON_OWN` finishes: ALL PASSED. the table for the hourly line and reports: `tools/run/league_table.py --run <run> [--line]` |
| `make_files.py` (1.3b's command with these settings and `--minutes 720`), the settings check against 1.3b's; `ramp_14b.py`; `start.ps1` | ✅ 11-03: the settings check PASS (only the run name, the length, `--pfsp`, `--pfsp-fixed`, `WEAPON_OWN`, `INTENT_SWITCH` differ); `ramp_test.py` on fake files ALL PASSED (the dials on one clock, a hold, a step back of 10, the kept saves, nothing past the end); `start.ps1` written (runs at the start) |
| 10 updates on a scratch copy | dropped (owner, 11-04: "You do not need to do a dry run, that's just the first 10 updates of the run"); the first 10 updates and the check at update 10 are the trial |
| Do the pre-aim pays (`PREAIM_PAY` 0.05, `WATCH_PAY` 0.03) keep him facing the enemy when he backs off? (owner, 11-04) | ✅ measured 11-04 on 1.3b's update 170 against itself, 80 ten-minute games, the checks' settings, a recorder on every sighting (play unchanged): 4,632 sightings, 5.8 a minute. 35% come 1 to 3 s after the line closed (chases). A seat backing off (moving away at more than 150 u/s, the other not) is 17% of seats at a sighting; it faces away (over 90°) 49% of the time and loses 0.014 a sighting, **0.014 a player-minute** in all, against 0.13 for both pays and about 10 for win pay. The cost of backing off is the same after long gaps (10 s and more) as after 1 to 2 s. **Not the cause:** a 3 s minimum gap (`PREAIM_SHUT=3`) would take out a third of the pre-aim pay and a third of a cost that is 0.1% of his pay. The pays fire only at a fresh sighting, never while the enemy stays in view. Not changed in 1.4b; the pays go on 1.4c's fade list |
| The owner's go | ✅ 11-04 ("Just start it. From 1.3b u170 end"). The start's settings check against the save allows CONTACT_FREE, LEVEL_PULL and RAIL_FAR_PAY: 1.3b's live dials, carried in the copied live.json at the save's values (`live_check.py`) |

## Judged by

| Measure | Wanted |
|---|---|
| Win rate against 1.3b's end | level or better at update 70, 90 and the end (against the zero point) |
| Against b1.2d's end | better at the end |
| Items a minute, stack at fights, the mega and the red armor taken | hold after the item rule's lesson goes (the rule carried item timing) |
| **Speed**: his speed on trips (1.3b at update 37: 339, 52% of trip time over 320), air time, who takes the contested items first | hold after the speed pay goes (owner: "speed is the thing to watch"; flagged if they slide) |
| The enemy's share of his targets | up |
| Target changes a minute, targets reached, trips abandoned | no flicker without the switch cost |
| Time at weapon spawns, the same weapon taken again and again | no camping (the panel) |
| The two parts' sizes (`head2.hands`, `raw`) | bounded |
| The league table (frag share and win chance gained against each league network) | no network he loses ground to; the trend beside the checks |
| No spawn camping, no holding a spot all game | the panel |
| The owner's play test | |

## The equilibrium

1. **No switch cost.** Both copies paid it alike, so it shifted how often he re-decides, not who wins. Without it a change of target is priced only by what it leads to; outside contact the 8 s lock still limits changes. On the way: more re-decisions in fights.
2. **The weapon override out.** Fetching a weapon he holds pays nothing by itself (no pickup pay, no way pay, and from update 90 no speed pay): it is worth only the ammunition and keeping it from the enemy, both real and zero-sum. So he refills when ammunition decides fights and does not when it does not. Taking it ends the choice, so a camp needs a new choice every time and has nothing paying for it.
3. **Matchmaking by difficulty.** Practice goes where he does worst: less forgetting of old answers, toward a best answer to the league's strongest mix (AlphaStar's league). Against his own snapshots (about 50%) the draw stays near even; the anchors move most.
4. **The item rule's lesson out.** The choice is learnt from pay alone; an item is chosen when its pay (the table, the stack it gives in fights, the win part) beats a fight. The head's correction of the rule shrinks as the rule goes (its L2 pulls it back).
5. **The speed pay out.** Speed is then worth what it wins: arriving first, getting away, finding the enemy. Both copies gained it alike, so it tilted the choice toward item runs without changing who wins; the risk is that fast movement drifts down where races do not reward it.

## Red team

| Part | Hand-built or assumed | The measured alternative | Watch |
|---|---|---|---|
| Two removals at update 0 (switch cost, weapon override) beside the matchmaking | the owner's call: small tilts on one choice | one at a time | the update-10 check; target changes, weapon choices |
| The weapon override kept for old networks in the checks | assumed: 1.3b's end plays as it was trained | the one setting for both | 🧪 how often it fires |
| The league's frag share as the draw's "win rate" | a training slice (one opponent network an update, about 10 s of each game), not a whole game | games won-lost in the checks stay the gate | the table beside the checks |
| (1 − p)², the floor at half the even share | AlphaStar's "hard" weighting; the floor assumed | even draw (the dial at 0) | the shares by file |
| The checks' opponent at a fixed share | assumed: a gate trained against inflates | weighted like the rest | the checks against b1.2d's end (weighted) beside 1.3b's |
| 60 updates for the rule's lesson | the owner's pace | | items, the mega and red armor shares |
| The speed pay out | the owner's call | a speed pay the same for every target (distance covered over the last second) | speed on trips, air time, contested items |
| The L2 on the hands' part is relatively stronger once the rule is out | | `H2_L2` down if his choices go soft | the hands' size, his step |
| Pay pathologies (the ledger) | | | negative frags, sign flips, lopsided games |
| The checks' zero point | b1.2d's (51.2% on 600 games): the checks' machinery is the same for 1.3b's end | one more seed against 1.3b's end | every gate |

## Changes on the fly

| Time | Change | Why |
|---|---|---|

## The result

**Scrapped (owner, 2026-11-04 ~18:30: "stop everything with 1.4b I'm going to scrap it and try something else").** Stopped at update 113; its end kept as `keep/policy_end_14b.pt` with its optimizer (the save of update 110). Checks against 1.3b's end: update 10 52.5%, 30 56.0%, 50 54.5%, 90 53.5% (the update-110 check stopped before its result); against b1.2d's end at update 70: 90.5% (181-19). Speed held (339 at the start, 338 at update 106). The behaviour panel RED from update 60: roaming 22 to 24 map cells a minute (1.3b's end 28.5), the red armor held 34 to 39% on Blood Run and Campgrounds, camping near the red armor on Blood Run 18% at update 110 (control 6%), the lightning gun as his target on Campgrounds 21% (control 10%), rockets at mid range 0.18 (control 0.24).

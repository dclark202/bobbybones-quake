# 2.1b: the 8-second lock replaced by a learned keep choice, step by step, in one run

**Started from:** 2.0e's end (`data/sim_runs/duel_gru_2_0e/keep/policy_end_20e.pt` + `opt_end_20e.pt`; list 20e, 811 inputs; the head with
its 17 targets and 10 weapon scores; the 8-second lock), given the keep choice and its quiet layer at zero, both shares 0
(`tools/keep_init.py add --start zero --quiet 1`; `same`: "share 0: PASS", the start plays as 2.0e's end to the bit).

**The owner's go:** _(blank: his words, date, the length in updates and minutes)_

**Marks:** ✅ known or decided · ⏳ to build · 🧪 to measure · ❓ owner's decision

## The owner's page

| | |
|---|---|
| The goal | 2.0e's end with nothing new choosing his target, the lock handed over to a learned keep choice in two parts: fights and arrivals first (B), the quiet hold second (C), the lock's last share out (D). The plan: [PLAN_FROM_20E.md](../PLAN_FROM_20E.md); the family: [README.md](../README.md) |
| What it is not | No new chooser, no new options, no question loop, no weapon hand-over (2.2, 2.3). The map sense as head inputs is **not** in 2.1 (owner, 11-14: 2.2's first step); it learns silently here, nothing reads it |
| One run (owner, 11-14) | A → B → C → D in one run. **Each step opens only when the owner names it** in `data/sim_runs/duel_gru_2_1b/steps.json` (`{"B": <update>, "C": <update>, "D": <update>, "B_over": 20, "C_over": 30}`); `ramp_21b.py` opens its share over that many updates from the update named. Nothing opens on a schedule, holds or steps back on its own |
| Length | ✅ owner 11-14: start about 21:00, **stop at noon on 11-15** (`-Minutes 900`, 15 hours; `-Updates 200` only as a ceiling: at about 5 to 7 minutes an update the minutes end it first). The night is step A only; the owner reviews in the morning and decides on B (Sunday by day: his word) |
| Checks | every 20 updates, 200 games, against **2.0e's end** (the control); every fourth against **1.6a's end** (the long-term control). Every check reported; one under 40% flagged at once (MAJOR in `watch.log`) |
| The real judge | the owner's play test at B's end and at the end. The self-play checks reward the lightning equilibrium (1.7a: 63% in self-play, lightning only against him) |
| Kept | `keep/policy_end_21b.pt` + `opt_end_21b.pt`; marks with their optimizers at update 10 and at each step's start and end (`keep/policy_u<update>_21b.pt`) |

## The steps

| Step | What opens | What plays | Its measure (every update, `watch.log`) |
|---|---|---|---|
| A. Silent (from update 0) | the keep forks (keep against a new draw; `BRANCH_P` 0.2, `BRANCH_ZONE_P` 0.5, quiet moments read over 30 s); the stay value's lesson (`STAY_W` 1); the keep choice's silent lesson toward the stay value's sign (`KEEP_TEACH` 1, both layers); the map sense's silent lesson | 2.0e's end with the lock; nothing new plays | the stay value's held-out sign right (a mark the owner sets: to fill); its labels an update; the keep lesson's p against its target; the map sense's R2; the checks level |
| B. Fights and arrivals | `KEEP_G` 0 → 1 over `B_over` updates (the zone layer, `KEEP_ZONE=1`: in contact and at arrivals only) | five readings a second in a fight; an arrival can be kept; quiet = the lock | trips and reached unchanged; quiet re-decisions unchanged; the weapon in hand by range; megas and reds; **the owner's play test** |
| C. Quiet | `KEEPQ_G` 0 → 1 over `C_over` updates (the quiet layer: the stay value, the age, the change signals). It decides only where `KEEP_G`'s coin gave the keep choice the second: its real share is `KEEP_G` × `KEEPQ_G` | the lock's hold leaves his seats | quiet re-decisions a reading at or under the start's (flag over 1.25×); reached not down |
| D. The lock out | nothing more: both shares at 1 = the lock decides nowhere (recorded by the ramp) | all his own | the same guards |

## What goes in

| # | Change | Kind | When |
|---|---|---|---|
| 1 | The keep choice (1.7a's zone layer) and its quiet layer, at zero, shares 0 (`--keep-g 0 --keepq-g 0`) | exact (`same`) | the start |
| 2 | `KEEP_ZONE=1` (the keep choice by zone) and `KEEP_SIG=1` (the target's change signals) | simulator switches; at share 0 nothing plays differently | the start |
| 3 | The keep forks: `--branch 1 --branch-p 0 --branch-keep 1 --branch-zone-p 0.5 --branch-long 1 --branch-long-p 0 --branch-long-secs 30 --branch-win 320 --branch-hold 40 --branch-log 1 --branch-keep-long quiet`; live `BRANCH_P` 0.2 | lesson data (costs speed) | the start |
| 4 | The stay value (`--stay 1`, `sim/stay.py`), all run | silent lesson | the start |
| 5 | The keep choice's lesson toward the stay value's sign (`--keep-teach 1`), all run | silent lesson (rule 13: its own lessons, no copy of the lock) | the start |
| 6 | The map sense (`--map-sense 1 --map-sense-init <run>/keep/mapsense_start.pt`, from `data/sim_runs/space/mapsense_start.pt`) | silent lesson, nothing reads it | the start |
| 6b | **Damage taken costs 0.9 of the pay of damage dealt** (owner, 11-14; 2.0e: 1.0): `--dmg-taken-w 0.9`, live `DMG_TAKEN_W` 0.9; enemy damage only (`DMG_ENEMY_ONLY=1`: his own splash, falls and hazards stay at full cost) | the hands' pay table (the head is paid by the win chance only) | the start, at once |
| 7 | `KEEP_G` 0 → 1 | the share | B, on the owner's word |
| 8 | `KEEPQ_G` 0 → 1 | the share | C, on the owner's word |

**Left exactly as 2.0e's end played it:** AIM3 at its end values, the corrected knockback, the dodge inputs (`DODGE_G` 1), the damage
pay (0.005; no longer zero-sum: taken at 0.9, above), the far rail 0.1, `WIN_ADD` 0.33, the lock rule itself (`INTENT_HOLD` 8, `CONTACT_FREE` 1) where the shares do not reach, the
head and its credit, no firing cost, no weapon habits, no teacher.

## Decisions

1. ✅ One run, A to D (owner, 11-14).
2. ✅ The map sense into the head is 2.2's first step; in 2.1b it learns silently.
3. ✅ The keep choice starts at zero (`--start zero`, rule 13), not the lock made soft (owner 11-14: "fine").
4. ✅ B opens after the stay value's held-out sign is right 0.55 or more over 500 fight-and-arrival labels, then 200 games of the keep choice in contact against 2.0e's end (no learning) before B opens in training (owner 11-14: "fine").
5. ✅ Step A's first updates are the measurement of keep against a new draw on 2.0e's end (`tools/run/m1_report.py`); the check on 1.7a's update 90 on the graphics card later (owner 11-14: "fine"). ❓ If the stay value shows no skill: more forks an update; a deliberation cost (a hand-set price: his call); or stop after A.

## Red team: what is assumed, its alternative, what to watch

| Part | Assumed | What is known against it | Watch |
|---|---|---|---|
| The stay value can be learnt from forks | keep-or-redraw is simpler than ranking 17 targets | 2.1a: no skill after 9,104 forks (R2 about 0); `branch_test.py`: one moment's branches are too noisy | held-out sign right and labels every update (flag under 50 labels, sign at or under 0.5); M1 |
| The keep choice's lesson toward the stay value's sign | the sign is the right label | a noisy sign teaches noise; a zero start re-decides half the time where it decides | the lesson's p against its target (flag over 0.15 apart); quiet re-decisions once B opens |
| Step B is the part of 1.7a that won | five readings a second in contact | 1.7a's 63% was in self-play; the owner found it lightning only | the weapon readouts; the play test at B's end |
| The quiet hold needs no price | the stay value is the price | option-critic without a cost collapses (BOTS.md section 9); 1.7a drifted 0.03 → 0.125 | quiet re-decisions a reading every update (flag over 1.25× updates 1 to 5) |
| C's share | `KEEPQ_G` alone sets the quiet share | it is `KEEP_G` × `KEEPQ_G` (the simulator's coin) | the ramp flags C opened with `KEEP_G` under 1 |
| The judge scores a fork fairly | the win chance over the trip | fitted on v0.6.0's games; items in part by hand | the forks' outcomes beside the pay table's |
| The forks' cost | small | 2.1a ran about 7.8 minutes an update with forks | minutes an update from update 1 |
| The checks see what trains | the checks play the network as the trainer does | `sim/test_suite.py` Policy now plays the zone layer, the quiet layer and the stay value as the trainer's rollout (keep21_playtest: the server's pass = the checks' to the bit over 800 frames); `PANEL_SETS` gains `KEEP_ZONE=1,KEEP_SIG=1` (start.ps1). Left: a league file with the quiet layer plays it in the checks but the lock in training (none in the league at the start) | ✅ built 11-14 |
| A keepable hold becomes camping | | v0.4.3 | the panel's camping and spawn-camping measures at every check |
| Damage taken at 0.9 | an even trade now pays a little (+0.1 × 0.005 a point of damage) | the damage pay was made zero-sum on purpose (1.0) so trading is neutral and the win chance decides; under 1.0 self-play can drift toward trading health for damage (more pushes, less care for the stack) | the ledger's dealt and taken per minute, his health and armor at contact, the deaths per game, the checks against the control |
| Pay pathologies | | | negative frags, sign flips, lopsided games (the ledger, every update) |

## Research check (hard rule 14)

From [PLAN_FROM_20E.md](../PLAN_FROM_20E.md), "Research check":

1. **The game.** No mechanic changes. The change signals (an item's clock against his time to get there) rest on the respawn times (mega 35 s,
   red 25 s: MECHANICS.md, items), which the simulator has.
2. **What wins.** Control is owning the next mega and red (research README core 3): trips that finish (the quiet hold) and leaving a lost
   trip (the change signals). Holding an angle with the rail (DUEL_STRATEGY.md, positions) needs keepable arrivals.
3. **The player's view.** The change signals are what a player has: his own timers from pickups seen or heard, a sound, where he believes
   the enemy is. The map sense's features take the enemy's place from the brain's belief; only its label is the truth, in hindsight.
4. **In and out of control.** A keepable hold can become camping (v0.4.3): the panel's camping measures at every check. Out of control,
   breaking off a lost trip is the point of step C.
5. **Self-play equilibrium.** Two copies that finish trips contest the big items by timing, not by who stops flickering first. No league
   seat punishes a camper yet (2.0b's postmortem): named, not in 2.1.
6. **Bot precedent.** No system put an untrained chooser over trained hands; they taught it from predicted outcomes of each choice
   (BOTS.md sections 0, 13): the stay value. FTW's slow prior and FiGAR's "keep for k ticks" (sections 9, 13.2); option termination needs a
   cost or a reference: here the measured stay value.
7. **Rule 12.** No pro outcome is a target. The map sense's start may come from the pros' fit of the seeds (a measured fact of the maps).
8. **Not covered by the notes:** how long a strong player commits to a trip before giving it up.

## Before the go

| # | What | State |
|---|---|---|
| 1 | The decisions | ❓ 4, 5 |
| 2 | 2.0e's end and its optimizer | ⏳ (2.0e trains) |
| 3 | The run's files: `make_files.py`, `train.cmd`, `start_live.py`, `ramp_21b.py` (flags tested on made-up lines; a crashed flag or stall thread logged as MAJOR and started again), `start.ps1`, `smoke.py` | ✅ |
| 4 | The settings check against 2.0e's command: the card's differences only (`start.ps1` `$ALLOW`) | ✅ (with `train.cmd` of 720 minutes, 100 updates) |
| 5 | `live_accept` on a start file (from 2.0e's live.json mid-run) and the ramp's 52: PASS | ✅; again on the real file at the start |
| 6 | `smoke.py` (tag d, CPU, idle, cores 14-17): 19 of 19 PASS (`tests/smoke_d.log`); `live_test.py`: the new live names applied by update 4, both layers decide once open, `KEEPQ_G 1.5` and `KEEP_ZONE 2` refused: ALL PASSED (`tests/live_test.log`); `keep21_simtest.py`: off = 2.0e's simulator to the bit over 3,000 frames, duel = free-for-all, the zone split exact (`tests/simtest.log`); `keep21_playtest.py`: the server's pass = the checks' to the bit; `keep_init same` on 2.0e's update 10: share 0 PASS to the bit. The map sense recorded no samples in the smoke (its 200-frame horizon against short rollouts): **read its first records in the run** | ✅ |
| 7 | M1: keep against a new draw on 2.0e's end. Proposal: **step A's first updates are M1** (nothing new plays; the forks logged in `stay_forks.jsonl`, read with `tools/run/m1_report.py`); it gates C and D, not A. 1.7a's update 90 (the instrument's check) needs the graphics card: an hour after 2.0e ends, or after 2.1b, the owner's call | ❓ |
| 8 | The checks play the keep choice by zone and its quiet layer (`sim/test_suite.py`, `PANEL_SETS` with `KEEP_ZONE=1,KEEP_SIG=1`) | ✅ |
| 9 | For a play test: `export_duel.py` writes the quiet layer and the stay value; `netpass.py` plays them (= the checks to the bit, offline). Not tried on a server: the change signals there read state the plugin keeps (beliefs, sounds, the route); an image build and a local server before B's play test | ⏳ before B's play test |

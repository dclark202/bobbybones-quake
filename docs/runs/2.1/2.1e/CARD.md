# 2.1e: the head's slow half (DRAFT, 2026-11-15 evening; not approved, not started)

| | |
|---|---|
| Started from | 2.1d's end (to be kept as `keep/policy_end_21d.pt`), with the slow half added at zero (answers as 2.1d's end) |
| State | **draft.** The design is the owner's decision of 11-15 evening ("we should plan to do this anyway"); the schedule and the pass marks below wait for 2.1d's result. The build runs on branch `b21e` (an Opus 5.5 subagent, rule 16) |
| Length | to be asked before the start |

## The owner's page

**What it is.** The head gets a slower half. Today one memory does both jobs: every 0.2 s it asks "what should I be doing", and the plan
he is pulled toward is read out of that same fast memory, so the plan moves almost as fast as the question. In 2.1e a second, small
memory holds the plan. It thinks about once every 2 seconds and whenever a trip ends or he changes his mind; between those moments it
does not move. The owner's picture (11-15): "I'm going to go get mega" is the slow half; "every 200 ms I ask myself what else should I
be doing, knowing that I've already committed" is the fast half.

**What should change in his play.** Fewer goal changes that he takes back within 2 seconds (2.1c: 55 to 58% of his mid-trip changes),
more targets reached, and no loss against 2.1d's end with the lock out.

**What it is not.** No new choices, no new pay, no rule. The slow half only forecasts and steadies the goal he already chooses. Paying
the slow half for its own decisions is 2.2 (see "The fork" below).

## How the fast and slow sides talk

Four channels. Two exist today in a weaker form (2 and 3's source), two are new.

| # | Direction | What is said | When | New? |
|---|---|---|---|---|
| 1 | fast → slow | "this is what I see and want now": the head's state (256), the goal he holds (one of 17), how long he has held it, whether the held draw is on | at a slow tick only | new: today the plan reads the head's state at every refresh and has no memory of its own |
| 2 | slow → fast, **the pull** | "this is the plan": the slow half's odds over the 17 targets for the next 2 s (and 5 s), added to his goal scores as `PULL_G` x log(odds) | every 0.2 s, but the odds only change at a slow tick: the bar a new idea must clear is fixed in between | the pull is 2.1d's; its source moves from the fast plan to the slow half by a dial |
| 3 | slow → fast, **the read-back** | "this is what I committed to and why": the slow memory's state (128) as an input of the head | every 0.2 s | new; starts at zero weight behind a gate, opened after the pull's source has moved |
| 4 | fast → slow, **the interrupt** | "the trip ended" (reached, gone, respawned) or "I changed my mind mid-trip" (his fast choice beat the pull) | at once, off the slow clock | new for the second: without it the old plan would pull against his new goal for up to 2 s and push him to take the change back |

**A slow tick, step by step** (per seat):
1. The slow memory takes channel 1's inputs through one layer (to 128) and steps its own recurrent cell (128) once.
2. From the new state it writes the plan: odds over the 17 targets for each horizon (2 s, 5 s).
3. Until the next tick the state and the odds are frozen.

**Every 0.2 s in between**: the head scores the targets as today (hands' rows + head's scores), adds the pull from the frozen odds, and
picks by the held draw. If the pick differs from the goal he holds, that is a mid-trip change: he takes the new goal and channel 4
ticks the slow half so the plan follows him.

**When it ticks**: every 10 head ticks (2 s) since its last tick; at a trip's end (the moments the held numbers are rolled anew); at a
mid-trip change. At a death its state and odds go back to the start (even odds), as the plan's do today.

## What each side learns from

| Part | Learns from | Not from |
|---|---|---|
| The slow memory and its plan | the plan's lesson of 2.1c, unchanged: forecast his own fast odds (before the pull) averaged over the next 2 s and 5 s; through its own recurrent cell, over the ticks of a rollout; its own Adam | no pay, no pro, no rule, no copy of the old plan (rules 12, 13) |
| The read-back layer (channel 3) | the head's own learning (PPO, the head's pay as now), into that one layer only | the gradient does not go on into the slow memory: it stays a forecaster in this run |
| The head, the hands, the brain | as in 2.1d | |

## The fork for the owner (my recommendation first)

**A. 2.1e: the slow half forecasts and steadies (this card). 2.2: it is paid.** In this run the slow half is taught only by the forecast
lesson. That is enough for commitment, and it is one new thing. In 2.2, when there are orders to choose, the slow half gets its own
credit from the head's pay (a decision every 2 s, so the credit is spread over 6 decisions in 12 s, not 60) and becomes the part that
picks the play.

**B. Paid from the start.** FTW trains its slow core by the reward from the first step. It is the fuller form, but it is two new things
at once (a new memory and a new learner on the goal), and a paid slow half can take the goal over untrained (1.9a).

## The run (proposed; numbers wait for 2.1d's result)

| Stage | Updates | What is live | Mark to read before the next stage (reported; the owner decides, the ramp never holds) |
|---|---|---|---|
| 1. Silent | 1 to 20 | nothing new plays: `SLOW_MIX` 0, the read-back gate 0. **Three slow halves learn side by side, ticking at 1, 2 and 4 s** (owner, 11-15: the tick speed is decided on data), each forecasting beside the fast plan. At update 20 the owner picks one (live `SLOW_PICK`); only that one's plan and read-back ever play | its 2 s forecast error at or under the fast plan's (2.1c: 0.46 against 1.2 for the fast scores); its odds move less from tick to tick than the fast plan's; the replayed pull with its odds gives fewer mid-trip changes than with the fast plan's |
| 2. The pull's source moves | 20 to 50 | `SLOW_MIX` 0 → 1: the pull's log-odds = (1 - mix) x the fast plan's + mix x the slow half's | the share taken back within 2 s falls; targets reached not falling; the check against 2.1d's end |
| 3. The read-back opens | 50 to 80 | the read-back gate 0 → 1 | the same, and the head's sizes (rule 11) |
| 4. Hold | 80 to the end | everything open | the end checks; then 200 games with the slow half blanked (rule: proved used, not only harmless) |

Checks every 20 updates, 200 games, against 2.1d's end; every fourth against 2.0e's end. `PULL_G` and `HELD_G` stay where 2.1d ends.

## What is built (branch `b21e`; the list the build is checked against)

0. Three slow halves in the network (`head2.slow.0/1/2`, clocks 5, 10 and 20 head ticks; the clocks a setting `--slow-clocks`), each
   with its own state, lesson and readouts; a buffer `slow_pick` (live `SLOW_PICK`, 0 to 2) names the one whose odds enter the pull's
   mix and whose state the read-back reads. The other two stay silent to the run's end (their readouts go on).
1. `sim/head2.py`: the slow half inside the head (`head2.slow.*`: the input layer, the recurrent cell 128, the plan's layers to 2
   horizons x 17, the read-back layer at zero weights), a layout key, `add_slowhalf`, the torch and numpy passes (state per seat,
   tick, reset), buffers `slow_mix` and `slow_back` (the gate), so every reader of a network file plays it.
2. `sim/train_duel_rnn.py`: `--slow-half`, the state in the rollout (ticks on the clock, at a trip's end, at a mid-trip change; reset
   at a death), the stored states and tick marks, the lesson on the learner's copy with its own Adam (`slow_opt` in the checkpoint), the
   pull from the mixed log-odds as played (stored, as `b_pull`), the proof extended to it, rule 11's decay on the slow plan's last layer,
   live `SLOW_MIX` and `SLOW_BACK` with their ranges, the league's networks playing their own, the record `rec["slow"]`.
3. Readouts every update: both plans' forecast errors and top-1; how far each plan's odds move between refreshes; the replayed pull
   with each plan's odds; ticks a seat-minute by cause (clock, trip end, change of mind); sizes.
4. `sim/test_suite.py`, `plugins/netpass.py`, `plugins/duelbot.py`, `sim/export_duel.py`, the eval tools: the slow half's state and pass.
5. `tools/slow_init.py` (`add`, `widen-league --like`, `same`: the start answers as 2.1d's end, 0 actions differ).
6. `docs/runs/2.1/2.1e/`: `make_files.py`, `start_live.py`, `ramp_21e.py`, `start.ps1`, `restart.ps1`, `smoke.py`, `live_test.py`.

## Red team

| Hand-built or assumed | Why it is there | Its weakness, and the measured alternative |
|---|---|---|
| The 2-second clock | FTW's slow core ticks on a fixed period; 2 s is the horizon the pull already uses | a hand-set number. Too long: slow to re-plan after a fight; too short: it flickers like the fast plan. The interrupts (channel 4) cover the first; the tick-to-tick movement readout shows the second. The period is a setting, to be tried at 1 s and 4 s on the silent readouts before it plays |
| The interrupt at a change of mind | so the plan follows an override | it can make the slow half as fast as the fast half if he changes his mind constantly: then nothing is steadied. Read: ticks by cause; if "change of mind" dominates, the slow half is not slow |
| The slow half is taught only to forecast | rule 13: silent first; one new thing | a forecaster of a flickering chooser can only average the flicker; it does not decide. That is the limit of this run and the reason for the fork's 2.2 step |
| The mixed log-odds, a sum of learned parts | to move the pull's source slowly | rule 11: decay on both plans' last layers from the first update, each part's size recorded and flagged over 40 |
| The read-back | so his fast thinking knows the commitment | a new input of the head, live through a gate: it can destabilise the goal (2.0b). It opens last, alone, from zero weights |
| The same lesson as the fast plan | it is already measured | if both plans read alike on the silent readouts, the slow memory adds nothing over the fast plan and stage 2 is not worth running: said plainly at update 20 |

Pathology checks of the ledger as every card (negative frags, sign flips, lopsided games); the pull's proof extended to the slow half.

## Research check (rule 14)

1. **The game** (MECHANICS.md): none touched; no simulator value is used. The goal's choice only.
2. **What wins** (DUEL_STRATEGY.md "Principles distilled" 2, 3): control is owning the next big spawns and timing is "the map's clock made
   into plans": both need a goal held for 10 to 35 s. Works against none; a frozen plan would work against 6 ("steal when he commits":
   reacting to news), which is why the fast side can still override.
3. **The player's view**: the slow half reads only the head's state and his own goal: nothing a player does not have. No new input.
4. **In and out of control**: the same mechanism for both. Risk for the out-of-control player: a held plan to a big item he should
   abandon when the enemy arrives; the override and the interrupt are the guard. No new exploit seen (no pay changes).
5. **Self-play equilibrium**: no pay changes, so the equilibrium is the one of 2.1d; the change is how steadily each copy pursues it.
   The league's older networks (on the lock) punish a Bobby who dithers between goals.
6. **Bot precedent** (BOTS.md section 2 and idea 13.2): FTW's two-timescale memory, a slow core giving a prior for the fast one;
   base camping appeared only in agents with the temporal hierarchy. Differences: FTW trains the slow core by the reward and ties the
   two by a KL whose weight it evolved; here the slow half is a forecaster first (rule 13) and the tie is the pull, a live dial set by
   the checks. The notes' named risks: a strong tie freezes a bad prior; a prior that does not tick slower learns to flicker too. The
   Quake III bot (8.1) keeps one long-term goal: one persistent goal is enough for good item play.
7. **Rule 12**: no pro number is used anywhere.

## Before the go

- 2.1d's result, and the schedule and marks above fixed from it.
- The build's tests (identity at zero, the smoke, the live test, the proof) reported here.
- The owner's answer on the fork (A recommended) and on the length.

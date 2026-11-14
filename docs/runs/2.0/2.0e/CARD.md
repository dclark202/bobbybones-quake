# 2.0e: 1.6a's end cleaned up, on AIM3, with dodge inputs, in the corrected simulator

**Started from:** 1.6a's end (`data/sim_runs/duel_gru_1_6a/keep/policy_end_16a.pt` + `opt_end_16a.pt`; 980 inputs, the head with its
17 targets and 10 weapon scores, the 8-second lock, no keep choice, no combat order).

**The owner's go, 2026-11-14** ("80 updates, rail at 0.1 ..., weapons habits ... should be dropped entirely, hand lag is bullshit"; "Just start it when it's ready"). The owner, 11-14: "starting from 1.7a is not the move. 1.6a is much
better, despite what the win rate says. 1.7a literally only uses LG when I play against him"; "start from 1.6a; include aim3 config,
and other changes (damage pay, zero sum, dodge inputs) from 2.0d"; "The dead inputs must come out too"; "Ideally it should only be
60-80 updates and I can playtest tonight".

**Marks:** ✅ known or decided · ⏳ to build · 🧪 to measure · ❓ owner's decision

## The owner's page

| | |
|---|---|
| The goal | 1.6a's end on the cleaned inputs and AIM3, given inputs to dodge with, paid zero-sum for damage, trained in the corrected simulator. **Nothing strategic changes**: the head, its target and weapon scores and the 8-second lock stay exactly as 1.6a has them. The network 2.1 and 2.2 build on |
| What it is not | No keep choice, no order, no instruction, no new chooser, no head pay change, no strategy inputs moved. The lock goes only in 2.2, after its replacement is built and proven ([the plan](#the-rounds-after)) |
| Length | ✅ **80 updates** (owner, 11-14); the trainer stops itself (`--max-updates 80`). At 2.0d's measured 5.5 minutes an update: 7 h 20 |
| Checks | updates 10, 30, 50, 70 (the fourth also against 1.7a's update 90, a readout); 200 games; against **1.6a's end**, both seats under AIM3's end values and the corrected knockback. Every check reported; one under 40% flagged at once. Nothing holds or steps back on its own |
| The real judge | the owner's play test of the end, beside 1.6a. The checks' win rate is self-play and has misled before (1.7a: 63% over 1.6a, worse against him) |
| Read at every check | games by map; megas and reds head to head; both sides' hit rates by distance and by the target's crossing speed; the weapon in hand and in view by range, the rail owned (readouts only, rule 12); trips a player-minute and targets reached (the lock's measures: they must not move) |
| Kept | `keep/policy_end_20e.pt` + `opt_end_20e.pt`; marks at 10, 25, 35, 60 |

## What goes in (and in what order: one after the other)

| # | Change | Kind | When |
|---|---|---|---|
| 1 | **The input list 20e** (811 columns: list 18's cut plus the dodge group; the brain reads the first 691, the hands the first 803, a tail of 8). The dead columns cut and folded, the rule-made columns out, every input re-measured to its size on 1.6a's own play. 1.6a has no combat order, so the order's ten inputs (kept in 20d for 1.7a) are dead here and go | exact (`same`: the actions that differ counted, as 2.0d's 1 of 44,800) | the start |
| 2 | **The corrected knockback** (`KNOCK_QL=1 KNOCK_NOW=1`) | the game's physics, both seats | the start (a switch, not live) |
| 3 | **AIM3 at the 11-11 tuning**: `AIM3_W` 0 → 1, `AIM3_SIZE_A` 1 → 0.39, `AIM3_SIZE_B` 0 → 0.355, `AIM3_LEAD` 0 → 1, `AIM3_RELOAD` 1 → 0; `AIM3_FIX_TAU` 0.05 | aim | ramp, updates 0 to 25 |
| 4 | **The pay**: damage zero-sum, dealt and taken both 0.005 a point (`DMG_REWARD` 0.0055 → 0.005, `DMG_TAKEN_W` 0.8 → 1.0; owner 11-11); the far-rail pay 0.25 → 0.1 (owner 11-12, 11-14) | pay | ramp, updates 25 to 35 (in 2.0d a step at the start) |
| 5 | **The dodge inputs** (2.0d's seven: the enemy's aim past him sideways and up-down, his crossing and its change, damage taken short and long, the enemy's lightning on him), read by the hands as a token whose gate starts shut | new inputs (rule 13: silent, then open) | zero at the start; `DODGE_G` 0 → 1 over updates 35 to 60 |
| 6 | Hold | | 60 to 80 |
| 7 | **No weapon habits on league seats** (`HABIT_P` 0.3 → 0; owner 11-14: "dropped entirely") | league | the start |

**Left exactly as 1.6a has it:** the lock (`INTENT_HOLD` 8, `CONTACT_FREE` 1), the head and its credit, the head's weapon scores, the win part (`WIN_ADD`), the item table, no firing cost, no teacher, no speed pay.

**Not taken from 2.0d:** the keep choice's share (there is none), the pass-odds lesson and the order's parts (1.6a has none).

## Decisions (owner, 2026-11-14)

1. ✅ 80 updates.
2. ✅ The far-rail pay to 0.1 (with the pay ramp).
3. ✅ Weapon habits out.
4. ✅ No hand-lag aim term (`AIM3_HAND`): the other session's uncommitted diff was taken out of `sim/duel_env.py` before the build (kept as a
   patch outside the repo); the run uses the committed simulator.
5. ✅ By day: "Just start it when it's ready".
6. ❓ The play test: the plugins do not compute the dodge inputs and AIM3 has not been checked on a server ("Before the go" 9, 10).

## Red team: what is assumed, its alternative, what to watch

| Part | Assumed | The alternative, and what is known | Watch |
|---|---|---|---|
| AIM3 from 1.6a | it lands as it did elsewhere | 2.0c: 52.0 / 51.5% at updates 10 / 30 from 1.7a; 1.8a took it from b1.2d. Never tried from 1.6a | the checks at 10 and 30 |
| Three ramps in 60 updates, a hold of 20 | each can be told apart because they do not overlap | "opened slowly" would be 40 updates each; a check lands inside each ramp, not after a hold | the check after each ramp's end (30, 50, 70) |
| The knockback from update 0 | the game's value, both seats | not rampable (a switch). 2.0d had it among six start changes and lost 6 points by update 10; here it is the only non-exact start change, so update 10 measures it | the check at 10; the lightning's hit rate by distance |
| Zero-sum damage | serves "avoid damage as much as you deal it" | 2.0a / 2.0c showed lowering the damage pay costs games; this is a small change in size (0.0055 → 0.005) and a change in balance | the ledger: dealt and taken a player-minute cancel; frags a match-minute |
| Dodging pays in the simulator | the inputs help | AIM3.md section 3: the pros' lightning error is flat with crossing speed; only a reversal costs the shooter (pros x1.31, his AIM3 x1.14). His copies may not punish standing still enough | his hit rate against a crossing and a reversing target; at the end 200 games with the group blanked: no drop = it does not stay |
| The lock held | trips and reached stay at 1.6a's (about 24 a player-minute, 24%) | none: nothing touches it | both numbers every update |
| The checks reward the lightning | a win over 1.6a's end may be the same equilibrium again | a league seat that dodges like a person does not exist yet | the weapon readouts beside 1.6a's; the owner's play test |
| The surgery (cut, resize, new token) with no learning-rate-zero warm-up | the converter carries the optimizer's moments | a few updates at learning rate 0 (OpenAI Five) | the KL of updates 1 to 5 |
| 1.6a's optimizer file is the old form (no group names) | the trainer's resume chain takes it, as 1.7a's start did | a cold optimizer | `tests.py smoke` restarts from a save; `start.ps1` checks the optimizer line |
| Pay pathologies | | | negative frags, sign flips, lopsided games (the ledger) |

## Research check (hard rule 14)

1. **The game.** Knockback of the lightning, machine guns and shotgun (MECHANICS.md 1.2, 7.1): measured and fixed 11-13. AIM3's
   parameters are the pros' measured aim (MECHANICS.md 5.3; `docs/design/AIM3.md`). Still off the game and untouched: the hit cylinder
   against our box, players passing through each other, the shotgun's rings, the footstep rule (7.1).
2. **What wins.** Zero-sum damage serves "die less" (README core 1) and the out-of-control player's "damage at his pickups and
   leave" (core 4). The dodge inputs serve "the weaker aimer must make fights uneven" (core 8). Nothing here serves control
   (core 3) directly: that is 2.1 and 2.2.
3. **The player's view.** The dodge inputs are what a person perceives (the enemy's model pointing at him, with an error by distance;
   his own movement; the hits he feels). No truth input. The cut removes only dead or unread columns.
4. **In and out of control.** The pay change is symmetric; no pay for a place or an item changes; no new exploit.
5. **Self-play equilibrium.** Both seats harder to track lowers the lightning's worth in self-play toward its worth against people
   (`docs/design/LG_REAL_VS_SIM.md`: people hit him 43%, he hits them 29-39%). How far is not known (red team, dodging). The league is
   still only his copies (BOTS.md: GT Sophy; README core 9).
6. **Bot precedent.** OpenAI Five's surgery rules (BOTS.md section 3): the same surgery on the league's files; new inputs at zero
   behind a shut gate. AlphaStar: the control in every check.
7. **Rule 12.** No pro outcome is a target; AIM3's values are measured limits; hit rates and weapon shares are readouts.

## Before the go

| # | What | State |
|---|---|---|
| 1 | The decisions | ✅ (6 open: the play test) |
| 2 | List 20e (`sim/input_list_20e.json`, `docs/INPUTS_20e.csv`, `sim/duel_env_ffa20e.py`): 811 columns, the brain 691, the hands 803, the tail 8 | ✅ |
| 3 | A sample of 1.6a's end against itself under 2.0e's settings (40 games of 5 minutes, ten maps; `data/sim_runs/inputs20e/sample_obs.npy`) | ✅ |
| 4 | The converter takes 1.6a's file (`tools/inputs20d.py --list 20e`: any older width, no keep choice or order needed): every first layer's sums within 1e-13; `same` 1 of 44,800 actions differs with the brain's rounding off (7 as played), as 2.0d's start; the five anchors and 1.6a's end as a league file convert | ✅ |
| 5 | The run's files: `make_files.py`, `train.cmd`, `start_live.py`, `ramp_20e.py` (a crashed flag thread is logged as MAJOR and starts again), `start.ps1`, `smoke.py` | ✅ |
| 6 | The settings check against 1.6a's command (19 differences, all the card's) and 1.6a's end; `live_accept` on the start's file and the ramp's 62: PASS | ✅ |
| 7 | `smoke.py`: the trainer on the converted start, three small updates on the CPU, the dials at mid values | see [smoke.log](smoke.log) |
| 8 | The input health report on the converted start | 🧪 after the start (a readout; it does not gate the run) |
| 9 | For a play test: the dodge inputs computed in the plugin, the inputs recorded in a real game beside the simulator's | ⏳ |
| 10 | For a play test: AIM3 on the server, checked on a local server; the image rebuilt | 🧪 |

## The rounds after

| Round | What | The lock |
|---|---|---|
| 2.1 | The head he has grows in place: a silent **stay value** learned from forked moments (keep the target against redraw, judged over the whole trip), on every seat, playing nothing. Before it: the fork measured on 1.6a's and 1.7a's saves, no training | in |
| 2.2 | The lock out in two steps: five readings a second in contact and keepable arrivals (the quiet hold unchanged); then the quiet hold passes to the stay value, its share opened on a measure the owner sets | out only after the stay value holds at full share |

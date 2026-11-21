# 2.0c: the aim model AIM3 and the damage pay 0.002, zero-sum

*2026-11-10 night (owner): "Just start it when you have it, it can run until 9am tomorrow. Both changes at the same time ramp from u0 to
u40"; "Then we can start fresh on 2.1 with these changes established." The family: [README](../README.md). The aim:
[design/AIM3.md](../../../design/AIM3.md). The strategy layer's rebuild, which had this folder's name until tonight, is 2.1:
[../../2.1/DESIGN.md](../../2.1/DESIGN.md), [../../2.1/RUNDOWN.md](../../2.1/RUNDOWN.md).*

**Marks:** ✅ measured or built and tested · 🧪 measured during the run · ❓ the owner's to decide after it

**Started from:** 1.7a's update 90 (`data/sim_runs/duel_gru_1_7a/keep/policy_end_17a.pt` + `opt_end_17a.pt`, the same file as
`opt_u90_17a.pt`), widened to today's 1,053 inputs with zero weights: 2.0a's 994-input copy (1.7b's four timers), then 2.0b's 59 of the
map's table (`tools/b20b_init.py widen-league`). Nothing of 1.7b's, 1.7c's, 2.0a's or 2.0b's training; none of their parts on.

## The owner's page

| | |
|---|---|
| The two new things (owner: both at once) | **AIM3**: the sight error's slip and eccentricity terms against his eye instead of his crosshair (`AIM3_W` 0 → 1), and the base error by how big the enemy looks (`AIM3_SIZE_A` 1 → 0.39, `AIM3_SIZE_B` 0 → 0.355: the same 0.9 degrees at 500 units, less beyond, more nearer). **The damage pay**: `DMG_REWARD` 0.0055 → 0.002 a point, `DMG_TAKEN_W` 0.8 → 1.0 (zero-sum). All five live, straight lines over **updates 0 to 40** (`ramp_20c.py`); never held or stepped back |
| Why | he converged on the lightning because it is "the easiest to pay for, and it's the easiest to calibrate and tune" (owner), and his sight error was largest exactly where the rail needs it smallest (a held angle, a flick's start, a far target). This run establishes both corrections so that 2.1 starts on them. It does **not** teach the rail or rockets: nothing here puts him where those shots are the right ones |
| Stays | everything 1.7a's update 90 played: the judge's weight `WIN_ADD` 0.33, the flat frag and death, the item table, the keep choice at 0.975 and learning, the order shut, the habit seats, no firing cost, the delays 125 / 225 ms, every other aim number (`aim2_env.cmd`), every input and lesson of 1.7a's command. The three attention tokens update 90 never had (timers, space, targets) stay shut the whole run (`--gate-open 0`) |
| Length | **100 updates** (owner, 11-10 22:10, after the start: "Probably 80-100 updates is enough ... ramp at the first 40 then 40-60 to play from there. I want it to be done in the morning"): the ramp over updates 0 to 40, then 60 at the end values. The trainer was started with `--minutes 643` (to 09:00) seconds before that message and has no live cap, so it is stopped by hand right after the save of update 100 (the ramp keeps `keep/policy_u100_20c.pt` with its optimizer; the trainer's processes matched by their own command lines), on the owner's word above; the check of update 100 then finishes on the efficiency cores. If that stop does not happen the trainer ends itself at 09:00 |
| Checks | every 20 updates, 200 games, against 1.7a's update 90 (the control, and the start); every fourth against 1.6a's end; the extra one at update 10; Cypher's measures; the panel. **Both seats play under AIM3 at its end values** in every check (the aim he is being moved to; the control has never trained under it either) |
| What is read from it | (1) does he hold his level against update 90 through the ramp and after; (2) the ledger: damage dealt and taken a player-minute fall to about 0.67 and cancel; (3) 🧪 after the run, on its saves: the aim error tables of AIM3.md (the first 400 ms on a new target, the far lightning, the flicks' endpoints) and the held-angle probe, beside update 90's. Hit rates are readouts only (CLAUDE.md rule 12) |
| Expected | near 50% against update 90 through the ramp. The pay change alone took 2.0a to 40 to 46% against the same control over 98 updates (with the judge's weight raised as well and the damage pay at 0.001); here the judge's weight stays and the floor is twice as high. The aim change should help both seats alike in the checks. What should move: frags a match-minute down a little (fewer trades are worth taking), his first shots on a new target sooner. What may not move at all: the weapon in his hand |
| Not in this run | anything of 2.1 (instructions, the map sense, the appraisals, frozen moments, drills); the `better` and `max` levels (a play setting; `tools/aim2_levels.py` is not yet rewritten); any weapon work |

## Red team: what is hand-built or assumed, its measured alternative, the pathology checks

| Part | Hand-built or assumed | The alternative, and what was measured |
|---|---|---|
| The eye's lag 0.125 s, gain 1.0, fixation 0.10 s | read off binned medians of the pros' aim error (5,265 player-games): raised about 150 ms after a turn-round, no growth with crossing speed to 100 deg/s, settled 250 to 400 ms after he appears. The numbers are my reading of those curves, not a fit | a least-squares fit of the three to the curves; not done. They are fixed this run (not on the ramp) and live, so they can be moved without a restart |
| The size law 0.39 + 0.355 x half width | the pros' TOTAL aim error (eyes and hands, and how exact they choose to be up close) follows 0.55 + 0.5 x half width; I applied that shape to his SIGHT error and anchored it at 500 units, where his error already equals theirs | splitting sight from hand cannot be done from demos. The risk is closer than 400 units, where his sight error becomes larger than today (1.7 degrees at 200 units against 0.9): in the untrained readout his close lightning did not change (0.54 → 0.53 half bodies). 🧪 the first check and the aim tables after the run say whether training under it does |
| The damage pay 0.002, taken at 1.0 | the owner's number ("possibly to 0.002"); zero-sum so a trade of equal damage pays neither copy | 2.0a went to 0.001 with the judge's weight up to 0.6 and fell to 40-46%; here the judge stays at 0.33, so the total pay for a hit falls (a 100-damage hit: 0.55 + the judge's 0.33 to 0.54 before; 0.20 + the same after). Frags and deaths become about 1.8 times the damage's size. The ledger is logged every update |
| Both changes on one ramp (owner) | two new things at once: a fall cannot be pinned on one of them from this run alone | `tests.py ident` separates them at the first update (the pay dials change nothing before the first learning step; the aim dials change the inputs); if a check falls, the saves at the marks (10, 20, 40, ...) allow either to be re-run alone |
| The checks under AIM3's end values from update 10 | during the ramp he trains under a mix and is checked under the end | checking under the run's current mix would make every check a different test; checking under AIM2 would test him on the aim he is leaving |
| 40 updates for the ramp (owner) | the dip rule: a dip lasts 20 to 30 updates at most | reported at every check, never held |

**Pathologies watched from update 1** (the ramp's log, `watch/watch.log`, every FLAG and MAJOR line read): the trainer refusing `live.json`
or applying dials that were not written (MAJOR); damage dealt a player-minute over 1.0 from update 45 (MAJOR: the pay did not come down);
damage dealt and taken not cancelling; a check under 40% (MAJOR, told to the owner at once); frags a match-minute under 1.5 (passivity: with
less pay for damage the cheap answer is to avoid fights); the keep choice's quiet re-decisions over 0.08 (1.7a's slide began there); targets
reached 30% under the start; megas and reds head to head in each check (2.0b lost there); any firing cost above zero (MAJOR); a part of a
summed choice over 40 (rule 11). Negative frags and lopsided games: Cypher's measures of each check.

**Weaknesses, volunteered:**
- This run cannot show that AIM3 "works" for the rail: he barely fires it (5 shots an hour) and nothing here asks him to. A level result
  and smaller aim errors on new and far targets is the most it can show.
- Less damage pay with nothing else changed may make him passive rather than smarter. That is the first thing to look for.
- The keep choice keeps learning (as at update 90); 1.7a slid after update 90 with the order opening. The order is shut here, but the same
  network part is live.
- `tools/ffa_check.py` cannot run (its `testlab` map is missing); the group module's identity with AIM3 off was shown by a fixed-seed
  fingerprint instead.

## Built and tested before the start

| | State |
|---|---|
| AIM3 in `sim/duel_env.py`, `sim/duel_env_ffa.py`; off, and on with its start values: the simulator before, bit for bit (fixed-seed fingerprint, both modules) | ✅ AIM3.md section 6 |
| `train.cmd` made from 2.0a's (`make_files.py`); the settings check against 1.7a's command: only `--run`, `--minutes`, `--keep-g`, `--gate-open` and the seven AIM3 names differ | ✅ `start.ps1` runs it again and refuses on any other |
| The start answers as update 90: 2.0a's 994-input copy compared weight by weight; the 1,053-input start against it by `b20b_init same` (0 actions differ); its shut tokens are the order, timers, space, targets | ✅ `tests_start.log` |
| The trainer repeats itself at a fixed seed; the end pay dials change nothing before the first learning step and then are the dials' arithmetic in the ledger; the end aim dials change the first update's actions (6% of them); the gates are not opened | ✅ `tests_ident2.log`. The first pass (`tests_ident.log`) failed one line, and the line was wrong, not the pay: I expected damage taken to scale by 0.002/(0.8 x 0.0055) = 0.4545 and read 0.3854. With `DMG_ENEMY_ONLY=1` the taken weight is on an enemy's damage only; his own splash and falls cost the full price at either weight, so the ratio lies between 0.3636 and 0.4545 by how much of the sample's damage was his own. The check now says so. **So "zero-sum" holds between the two players; what he does to himself is still paid in full, now at 0.002 a point** |
| The real trainer applies the start's `live.json` before its first rollout; mid values of all five dials written after update 1 are applied, and are in the save's record of what the simulators played | ✅ `tests_live.log` |
| Ten updates with all end dials from update 0: no NaN, the ledger at the lower pay, dealt and taken cancelling within 15%, a restart with the optimizer, a one-map check | ✅ `tests_smoke.log` |
| `live_accept.py`: the trainer's own reader takes the start file and every file the ramp will write | in `start.ps1` |

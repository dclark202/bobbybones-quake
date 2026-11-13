# 1.9a: the head in charge, from 1.8a's end, with the spirit of 2.1 and every hand-built rule out

*2026-11-12 (owner): "I'm very skeptical that the plan outlined by 2.1 will actually work"; "the safest possible way to get the strategy head
into 1.8a ... he should know how to read the instructions 'verbs' from the head"; "The pay decisions stay: the head gets paid for its
decisions, by which ones were 'good' meaning they increased win chance"; "So let's start from 1.8 u190 then"; "Make it fit into 200 updates or
so, ALL of the hard coded bullshit has to come out and it can probably go most concurrently"; "the lock has to go before the head can make
decisions"; "Judge with items. As long as the head understands the value of items, we're good"; "the judge just pays the head"; "This is 1.9"
(2.1 is its own tree). Built on branch `b19`, made from `b21` (2.1's build, committed as it was) with 1.8a's last docs merged in.*

**RUNNING since 2026-11-12 18:20 (820 minutes, until 08:00; [RUNS.md](../../../RUNS.md) #48).** The owner's go (11-12): "you can start the run when it's ready and run it until 8am"; "Start around 6pm"; "just give me the
final schedule to review, ideally we get through everything" -> one night, 120 updates (below), the measurements from 18:00, the run until 08:00.**
Owner, 11-12, on the lock: "I don't want to ever see the lock again after we get it out"; on the far-rail pay: "Far rail pay should stay in,
0.1 just set it to there from the beginning".

| | |
|---|---|
| Started from | 1.8a's end: its save of update 190 (`data/sim_runs/duel_gru_1_8a/keep/policy_end_18a.pt` + `opt_end_18a.pt`) |
| Run folder | `data/sim_runs/duel_gru_1_9a` |
| Length | 120 updates in one night (18:00 the measurements, about 19:00 to 08:00 the run: 13 hours at 5.5 to 6.2 minutes an update is 125 to 140 updates; 120 leaves room) |
| Inputs | list 21: 852 (the brain 691, the hands 844: list 18 + the 48 instruction columns at zero weights, their token shut); the head: 1,052 numbers (+ the instruction part 91, the fight odds 2, the win value 1, all at zero weight at the start) |
| Control | every check against the start (1.8a's end); every fourth against 1.7a's update 90 |

## What it does, in one table

| | At the start (1.8a's end) | At the end of 1.9a |
|---|---|---|
| Who chooses | the old head's target scores + the hands' rows, at most once in 8 s (the lock) | **the head's instruction every 0.2 s**: a verb, a place, a point, a weapon (2.1's eight verbs and rows); the lock does not act on a seat under it |
| The weapon | the hands' key | **the head's**, binding while the instruction stands (the hands' key on those frames is not trained) |
| What the head asks itself | where the enemy is and will be; who takes the next mega and red; its own memory | the same, and **"will I win this fight"** (the fight odds, 1.7b's readout, learnt from update 0) and **"how do my chances stand beyond the score and the clock"** (his shadow win value, trained all through 1.8a); and **its own instruction fed back** (the one it is on, how long, and what changed since: the enemy in view, a sound, his believed place moving, an item's clock, a pain sound or the enemy's stack falling a band) |
| The head's pay | his whole pay, damage in it | **the judge's change in his win chance, with the next mega's and red armor's race in it**; never the pay table |
| The hands' pay | the table + the win part, the far-rail pay 0.25 | the same with the far-rail pay at 0.1 (owner); + the follow pay while it is open (12 to 108) |
| Hand-built in his choice | the lock, the old head's credit, the strategy inputs in the hands | none: the lock off his seats by update 48 (never again: owner), the strategy inputs out by 84, the follow pay out by 108 |

## Built (branch `b19`)

| Part | Where | Tested |
|---|---|---|
| 2.1's instruction in the simulator (verbs, rows, binding weapon, "none" never offered, the head re-decides every 0.2 s, the lock bypassed under an instruction) | `b21` as committed (`ba89e0b`) | `b21`'s own tests (`docs/runs/2.1/2.1a/tests_*.log`); `tools/run/test_21_parts.py`: **230 checks ALL PASSED** on `b19` (`unit.log`) |
| **The copy lesson**: the head's scorer is taught toward the rows of the target his old head chose at its last reading, and toward the weapon in his hand, on every kept reading, played or not (live `INS_COPY`; `--ins-copy`) | `sim/duel_env.py` (`ins_own_tg`), `sim/branch.py` (`copy_rows`, the worker's 14th field), `sim/head2.py` (`ins_loss` copy term), `sim/train_duel_rnn.py` | `tests_ident.log`, `tests_smoke*.log` |
| **The items' judge** for the head only: `chance_items` = the judge's mu + for the mega and the red armor K x w x [p x his stack gain - (1 - p) x the enemy's], the gains by the judge's own value of a stack, p = sigmoid((T_enemy - T_him) / tau), T = max(his route-field seconds to it, seconds until back), w = exp(-seconds until back / horizon); an item neither can reach counts nothing | `sim/win_judge.py`, `sim/duel_env.py` (`JUDGE_ITEMS`, `item_race`, `wh_raw` -> the head's `win_raw`) | `tests_judge.log`: **8 ALL PASSED** (K 0 = the judge to the bit; nearer never lowers his chance; the hands' win part and pay unchanged to the bit; the head's stream with K 0 = the hands' win part) |
| Its fit: tau on who really took each item next, the horizon on how games ended (held out by game); K = 1 (decided here, below) | `tools/run/fit_items.py`; the race recorded by `tools/run/ws_eval.py` with `WS_ITEMS=1` | dry run on two games: refuses for too little data, as it must |
| **The follow pay** (hands only, live `FOLLOW_PAY`, a second while the instruction's state is "doing") | `sim/duel_env.py` | `tests_judge.log` (on with nothing given = off to the bit); `tests_ident.log` |
| **The fight odds and the win value as the head's inputs** (owner, 11-12: "add fight odds and win chance"): the parts `fight` (2: the fight odds' two chances less a half) and `wv` (1: the shadow win value) of the head's input, at zero weight; the fight odds readout new (its last layer at zero), learnt from update 0 (`--fight-odds 1 --fight-warm 0`, `FIGHT_TRUTH=1`); the win value as 1.8a left it, still learning (`--win-value 1`). The checks' player reads both the same way (numpy) | `tools/b19_init.py`, `sim/head2.py` (`wv_t`, `np_wv`), `sim/train_duel_rnn.py`, `sim/test_suite.py` | `tests_start.log` (the start with both: 0 of 44,800 actions differ), `tests_ident.log`, `tests_smoke*.log` |
| Records every update: `ins.terms.copy` and `copy_agree`, `follow` (seat-seconds under an instruction, share doing, pay), `judge_items` (the head's stream, the judge's, the items' part) | `sim/train_duel_rnn.py` | `tests_smoke*.log` |
| The run's files | `make_files.py` (1.8a's command + the card's changes), `start_live.py`, `ramp_19a.py`, `start.ps1`, `stop_19a.ps1`, `night_prep.ps1` + `night_prep.vbs`, `tests.py` | settings check PASS against 1.8a's command; `live_accept` PASS on the start and all 182 files the ramp writes; `tests_start.log` **ALL PASSED** (0 of 44,800 actions differ, twice); `tests_live.log` **ALL PASSED** |

## The schedule (`ramp_19a.py`; updates from 1.8a's end = 0; straight lines; nothing holds or steps back on its own)

| Updates | Dial | From -> to | What |
|---|---|---|---|
| 0 (set at the start) | `H2_PG`, `INTENT_TEACH_W`, `SPEED_PAY`, `RAIL_FAR_PAY` | 1, ~0, ~0, 0.25 -> 0, 0, 0, **0.1** | the old head's credit closed; 1.8a's last two fades at their ends; the far-rail pay at 0.1 for the run (owner) |
| 0 to 12 | `INS_GATE` | -12 -> 0 | the instruction's token in the hands opens (the flat path learns from update 0) |
| 0 to 36, then 36 to 60 | `INS_COPY` | 1, then 1 -> 0 | the copy lesson: the scorer learns what he does now before it is played; faded once the head is paid on its own choices |
| 12 to 48 | `INS_G` | 0 -> 1 | the head's share of his seats: on = its instruction every 0.2 s, the weapon bound, **no lock**; from 48 none of his seats has the lock |
| 12 to 36, 90 to 108 | `FOLLOW_PAY` | 0 -> 0.01 -> 0 | the hands' pay a second for carrying an instruction out |
| 24 to 60 | `H2_INS_PG` | 0 -> 1 | the pay on the head's own choices: the items' judge's change in win chance |
| 60 to 84 | `SFADE` | 0 -> 1 | the strategy inputs out of the hands |
| 108 to 120 | | held | the end at 120 |

The lock (`INTENT_HOLD` 8) stays in the settings only for the seats not under the head (a falling share to 48) and for his opponents in the
league and the checks (trained with it); none of his own seats has it after 48, and no later design brings it back (owner, 11-12).

Every save is kept with its optimizer (every 10 updates), so a night's run stops at any save in the morning. Checks every 20 updates, 200 games;
the extra one at update 10. Both seats under AIM3's end values.

## The night (owner, 11-12: "Start around 6pm"; "run it until 8am")

| | |
|---|---|
| 18:00 | `night_prep.vbs start` (a scheduled task, no window): the settings check; then, at once on all cores, his own damage a second (FIN_RATE, 120 games of 1.8a's end) and the items' race (200 games of 1.8a's end, every second recorded); then the fit |
| about 19:00 | **only if both are made and the items' judge is ACCEPTED**: `start.ps1 -Minutes <until 08:00>`; its row in `docs/RUNS.md` at once |
| 08:00 | the trainer stops at its minutes (a save every 10 updates); the same script gives the watcher's check up to 45 minutes to finish and stops the watcher, the ramp and the self-play logger (nothing deleted; every process matched by its own command line) |
| If short of 120 | `night_prep.vbs resume` the next night (`start.ps1 -Resume`) finishes it, on the owner's word |

## Decided here (for the owner's review)

- **The race, as fitted on the night (11-12, 100 games of 1.8a's end, 118,787 race rows; `fit_items_v3.log`, `items_19a.json`)**:
  P(he takes it first) = 0.16 + 0.68 x sigmoid((the enemy's route seconds - his) / (1.04 + 0.57 x seconds until it is back)). Two fits were
  refused first and are kept (`items_19a_v1.json`, `_v2.json`): max(walk, back) made the long waits a coin (they went 34 / 60%); without
  the floor the curve could not be calibrated (far behind he still takes it a fifth of the time). Accepted: every bin within 0.07, the
  judge with the items better on held-out games (log loss -0.0014, 95% -0.0025 .. -0.0005), horizon 6 s, no axiom failure.
- **K = 1 for both items** in the head's judge: an item is worth to each player exactly the stack the judge itself says it brings, weighted by
  the race. Only tau (who gets there first) and the horizon are fitted. Fitting K to how games ended was too noisy (the smoke test's folds chose
  2.0 and 1.5 for the mega, 0 for the red armor); a free K is still fitted beside it as a readout.
- **The fit's acceptance**: at least 80 games and 2,000 race rows; the race calibrated (every bin of 200 rows or more within 0.07 of its p);
  the judge with the items no worse on held-out games than without (the difference's 95% interval reaches 0 or below); no axiom failure.
- **An item neither player can reach on the route field counts nothing** (Aerowalk's red armor needs a jump: its route time is "none" for
  every seat).
- **The old head's target credit is closed at the start** (`H2_PG` 0, as 2.1a): the instruction's rows do that job; the old head's value is
  left as it is and gets no credit.
- **No map sense, no brain questions, no quiet, no drills, no frozen moments** (the head made with `--ms 0 --bq 0 --quiet 0`; `BRANCH_P` 0 all
  run). The trainer's `--ins` needs `--appraise 1 --branch 1`: both exist, idle, and nothing is taught toward them.
- **"Win chance" is his shadow win value**: what he reads of his chances beyond what the score and the clock say (the head reads the score
  and the clock among its own inputs, so the two together are his chance). It is his own estimate from his memory (fair: no truth), trained
  through 1.8a. **Not wired into a game server** (the plugins do not know list 21 yet: no server plays 1.9a).
- **The schedule compressed from 200 to 120 updates** for one night (owner): the head's share opens over 36 updates (1.3b's credit opened over 80),
  the pay on its choices 12 updates after it begins playing.
- **The follow pay at 0.01 a second**: about 0.2 a player-minute if he carries an instruction out a third of the time, against 1.45 of damage
  dealt and 0.9 of frags (1.8a's ledger). It is not zero-sum: both players earn it.
- **FIN_RATE re-measured on 1.8a's end** (2.1a's table was measured on update 50).

## Red team

| Part | Assumed | The alternative, and what is known |
|---|---|---|
| The lightning | the head paid by the win chance with the items, and choosing the weapon, will not take him to the lightning the way 1.8a's damage-paid head did | **not addressed beyond that.** If the lightning wins more in his hands, the head will choose it. In 1.8a the lightning rose 43 -> 50% under AIM3 alone, before the head's credit. Watched: the weapon in hand by range, the head's weapon picks |
| The items' judge | the race (route-field seconds) and the judge's own stack values say what an item is worth | **its stream is noisy**: with random-hand bots the items' part moved frame to frame about six times as much as the judge itself (it is a potential, so it cancels over a game, but it adds noise to the head's lesson). The fitted tau from real games should smooth it; `judge_items` is read every update |
| The copy lesson | 60 updates of shadow teaching put the scorer near the old head's choices before it plays | its agreement is read every update (`copy_agree`); if it is low at 20, the head's share opens on a scorer that does not know what he does |
| The lock out with the head's share | a seat under the head re-decides every 0.2 s from update 20 | the flicker: the played seats' changes a second are flagged over 2.5 (2.1a's smoke: the orders stood 0.2 s, "continue" 3%, on an untaught scorer) |
| The binding weapon | the head's weapon is what he holds | never trained at full size. Weapon changes a player-minute flagged over 20 |
| The follow pay | a hand-built pay, small, for 160 updates | it pays carrying out, not winning; the hands' only; out at 180. The head may still learn "hold" away (a held rail angle was 6 to 9 points behind free play with his hands) |
| Seven dials overlapping | the owner's choice | a fall between 20 and 140 cannot be pinned to one dial; every save is kept |
| The fight odds | a new readout learns fast enough to be worth reading by the time the head plays (update 12 on) | it starts at "no idea" (0.5 each way) and the head reads it at zero weight: until it learns, it adds nothing. In 1.7b it never showed a gain on its own. Its skill is in the `fight` record every update |
| One night | the trainer stops at 08:00 at a save; if it is short of 120 the next night finishes it with `-Resume` | done many times; the ramp's clock is the lines of `metrics.jsonl` |

**Pathologies watched from update 1:** a refused or unapplied live.json (MAJOR); a check under 40% (MAJOR, told at once); any firing cost
(MAJOR); the old head's credit above 0 (MAJOR); megas and reds head to head 20% under the control's; frags a match-minute under 1.5; the
played seats' changes a second over 2.5; weapon changes over 20 a player-minute; one block of rows over 80% of the head's picks; the
lightning over 60% (reported). Negative frags and lopsided games: Cypher's measures of each check.

## Before the go

| # | What | State |
|---|---|---|
| 1 | Unit checks (`tools/run/test_21_parts.py`) on `b19` | ✅ 230 ALL PASSED |
| 2 | `tests.py start` (the start = 1.8a's end on real rows) | ✅ ALL PASSED |
| 3 | `tests.py judge` (the items' judge, the follow pay off and on) | ✅ ALL PASSED |
| 4 | `tests.py live` (the start's live.json and every ramp file applied, in the record) | ✅ ALL PASSED |
| 5 | `tests.py ident` (repeats to the bit; the copy lesson changes no play; the head's share and the follow pay reach the game) | ✅ 25 ALL PASSED. Read: with the head forced on every seat at update 1 (an untaught scorer) the weapon changed 194 times a player-minute (the copy lesson's reason: after 2 updates its best row is his old target 32% of the time); in his real games the items' part of the head's stream was 0.022 a frame against the judge's 0.014 |
| 6 | `tests.py smoke_plain` and `smoke` (14 small updates, every dial stepped; the wiring's KL; the copy lesson taught; a resume) | see `tests_smoke*.log` |
| 7 | FIN_RATE on 1.8a's end; the items' judge fitted and accepted | 18:00, `night_prep.ps1` (heavy: in the evening window) |
| 8 | The full-size trial | the run's own first ten updates and the check at update 10 (owner, 11-12) |
| 9 | The owner's go | ✅ 2026-11-12: "you can start the run when it's ready and run it until 8am"; "Start around 6pm": the measurements at 18:00, the run until 08:00 |

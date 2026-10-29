# v0.6.1b: the old hand-built belief out of the brain, overnight, from v0.6.1's end (DRAFT, not final)

*2026-10-29 (owner): "I'm not opposed to doing v0.6.3 B first (before v0.6.2), as a short overnight run"; "Write the card".
Group B of [v0.6.3](../v0.6.3/CARD.md), moved ahead of the strategy head so that the head ([v0.6.2](../v0.6.2/CARD.md))
learns once, on the brain it keeps. Starts after v0.6.1 ends, on the owner's go. Nothing is built.*

**Marks:** ✅ built and tested · ⏳ building · 🧪 to measure · ❓ owner's decision · ⏸ later

## What it does, in plain terms

The brain predicts where the enemy is (now and 1, 2, 4 s ahead), his stack, and who takes the next items, from Bobby's
senses. Among its inputs are 76 numbers that are the old **hand-written guess** of the same things:
- the believed place of the unseen enemy and the ways to and from it;
- the enemy-stack filter;
- the pre-fire spots;
- the emergence point.

They were faded out of the hands in v0.4.2, but the brain still reads them unfaded (`sim/rule_fade.py`: "The brain ...
keeps reading the unfaded inputs"). So the hand-built belief still reaches him through the brain. This run fades them out
of the brain too. The brain then has to find the enemy from what he saw and heard alone. The raw sensed facts stay: time
since seen or heard, where heard, damage, pickups and weapons seen.

## The owner's page

| | |
|---|---|
| Network | v0.6.1's end with its optimizer (`keep/policy_end_v061.pt`) |
| The one new thing | a dial g (`--brain-fade 1`, live `BRAIN_FADE`) on the same 76 columns as the hands' fade, on the brain's inputs: × (1 - g), from 0 to 1. At 0 the brain is exactly v0.6.1's |
| The fix with it | the game-end pay fix ([WINPAY_END.md](../v0.6.1/WINPAY_END.md)): a correction to the pay, in from the start. The first 10 updates read it alone |
| Pay | win chance only, as v0.6.1 (`WIN_W` 1, `FADE_V` 1, `WIN_GAIN` 0.33), v0.6.1's judge (`judge_v060_wpn.npz`) unchanged ❓ |
| Ramp | shut until the first save (~10 updates), then g +0.1 right after each save (every 10 updates, at least 25 min) to 1 at ~update 100, then held at 1 to the end. On the clock as v0.6.2's ramp ("keep going unless a collapse"); a hold or a step back is by hand, on the owner's word ❓ |
| Timing | ~4 min an update: g reaches 1 after ~7 h; `--minutes 780` (13 h) leaves ~5 h at 1 by morning. If the brain's scores have not come back by then: hold a few more hours, or start v0.6.2 anyway ❓ |
| Aim, mix, maps | as v0.6.1 (`!aim default`; 65% whole games / 35% the pros' mid-game starts; the ten maps) |
| League | v0.6.1's end and v0.6.0's end as anchors ❓ |
| Checks | every 10 updates, 160 games against v0.6.1's end, every fourth against the long-term control (v0.6.0's end); the behaviour panel. Under 40% flagged, under 30% posted. Never stopped |
| The brain's scores | from the metrics, against v0.6.1's last 20 updates: the place now and 1/2/4 s ahead, the stack band, who takes the next item, the "in control" readout. Expected: a dip while `g_b` rises, back during the hold |
| Run folder | `duel_gru_v0_6_1b` ❓ |
| Saved | `keep/policy_end_v061b.pt` with its optimizer: v0.6.2's start |
| Play test | not planned (overnight); the owner's call |

## Before the start

The code is on `main` in the working tree, uncommitted. It is inert unless a network carries `belief.fade` or the trainer gets
`--brain-fade 1`, so v0.6.1's running checks are unaffected.

| Step | Where it stands |
|---|---|
| **The brain's dial** ✅ | **In the trainer** (`sim/belief.py`): the brain's first layer reads the 76 columns' weights times (1 - g). For a linear layer this is the same sums as those inputs times (1 - g). `g` and the columns are plain attributes from the checkpoint's `belief["fade"]`, so the state dict is unchanged. **In the trainer's wiring** (`sim/train_duel_rnn.py`): `--brain-fade 1`; live `BRAIN_FADE` (0..1, read between rollouts); each rollout played and learnt at one g (`bfg` in the rollout's record); saved in every checkpoint; `brain_fade` in `metrics.jsonl`. Without `--brain-fade` a network's own g stays as it is, so v0.6.2 keeps 1 from v0.6.1b's end. **In the numpy copy** (`sim/btoken.py`, `numpy_brain`): the same weights for the checks, the self-play logger and the servers (`test_suite.Policy`, `plugins/netpass.py`, `sim/export_duel.py`, which carry `belief` as is) |
| **The people lesson** ✅ | `--brain-human` runs the same brain module (`belief_.seq(pol.belief, ...)`), so the demo frames are faded by the same g, nothing extra |
| **League opponents** ✅ | In training, every seat's brain is his current one (the rollout steps `net.belief` for all seats), so they read the same g. In the checks each network plays at its own file's g (v0.6.1's end: none) |
| **`BRAIN_READ`** | The simulator's readers (the legs' look point, hunt, contest, openings) read the brain's answer in every life, so they move with it. Intended; watched through the hunt and openings counters |
| **Identity** ✅ | `tools/run/brain_fade_check.py` on v0.6.0's end (2026-10-29, all passed): state dict keys unchanged; g 0 bit for bit as without the entry; g 0.3 the same as the inputs × 0.7 (1.0e-6); g 1 the faded columns change nothing and the others still count; numpy = torch at g 0.5 (1.07e-5, the same float noise as with no fade, 9.7e-6). `start.ps1` runs it again on v0.6.1's real end and refuses on a failure |
| **The trainer's smoke run** ⏳ | `docs/runs/v0.6.1b/smoke.py`, **after v0.6.1 ends**, ~20-25 min on the CPU: v0.6.1b's command made small, the dial stepped 0 → 0.5 → 1 by the ramp tool. It checks the metrics, the save's entry, the identity check on that save, and `test_suite.Policy` on it. Not run before then, so v0.6.1 is not slowed (owner, 2026-10-29) |
| **The ramp** ✅ | `tools/run/ramp_live.py` (as v0.6.1's level fade): `BRAIN_FADE` 0 → 1 by 0.1 right after each save, at least 25 min apart; the save before the first step kept as `keep/policy_prefade_v061b.pt`. On the clock, as v0.6.2's (owner: "keep going unless a collapse") ❓ |
| **Settings check** ✅ | `train.cmd` (made from v0.6.1's by the scratchpad's `make_cmd_v061b.py`) against v0.6.1's: PASS, only `--run`, `--minutes` (780) and `--brain-fade` differ. `aim2_env.cmd` copied unchanged (identical to v0.6.1's and v0.6.2's). `start.ps1` refuses otherwise |
| **The game-end fix** ✅ (merge ⏳) | `WIN_END` (branch `v062pay`, commit 129c1d2; off = v0.6.1's simulator to the bit, on = every game pays `scale x (result - start chance)` exactly: `tools/win_end_test.py`), merged into `main` right after v0.6.1 ends. Set in `train.cmd` (`set WIN_END=1`), allowed in the settings check (PASS: `--run`, `--minutes`, `--brain-fade`, `WIN_END`), and `$FIX_MARK = "WIN_END"` in `start.ps1`, which refuses until the merged code carries it (v0.6.1's session, 2026-10-29) |
| **Review fixes (v0.6.1's session, 2026-10-29)** ✅ | `start.ps1` did not parse (`"$JUDGE: ..."` reads as a drive): `${JUDGE}`; `tools/run/ramp_live.py` waited for the watcher's `keep/` copies and read `metrics.jsonl` before the run had one, so the smoke run's dial would never have moved: it now takes a save from `policy.pt` being rewritten (tested mid-run and on a fresh run); `smoke.py` read its last save from `keep/`, empty without a watcher: it now reads the trainer's `policy.pt` |
| **The servers** ⏸ | the numpy brain handles the entry; an image rebuild and an input recording (`OBSDUMP`) come before this network goes on any server. Not needed for the run |

If any of these is not done and checked by the evening, it does not start that night (the calibration rule).

## Start order (after v0.6.1 ends, on the owner's go)

1. The game-end fix in the code, with its own identity check; `$FIX_MARK` set in `start.ps1`.
2. `%USERPROFILE%\anaconda3\python.exe docs\runs\v0.6.1b\smoke.py`: must end ALL PASSED (~25 min).
3. `powershell -ExecutionPolicy Bypass -File docs\runs\v0.6.1b\start.ps1`. It runs the settings check, the judge's axioms, the
   identity check on v0.6.1's end and the live.json check (WIN_W 1, FADE_V 1), then starts the trainer, the watcher, the ramp and
   the self-play logger.

## The checklist

| | |
|---|---|
| Hand-built / assumed parts | the 76 columns, the hands' list (`rule_fade.FADE`) taken as is; the ramp's schedule (ten steps, on the clock); the hold of 10 updates; the people lesson faded alike |
| Weaknesses | The brain's predictions get worse while it relearns, and the hands lean on them, so the checks may dip in the middle. With only one night, the brain may not be fully back by morning. Fading the 76 out of the brain leaves the rule's numbers in the input files for nothing; a later version can drop them. The game-end fix and the fade are in one run: the fix's effect reads in the first 10 updates, the fade's after |
| Pay pathologies (ledger) | as v0.6.1: negative scores, sign flips, lopsided games in the self-play games |
| Watched | the brain's scores (above); time the enemy is found after being lost; hunt and openings counters; items a player-minute; the lightning gun's share |

## What changes for v0.6.2

- It starts from `keep/policy_end_v061b.pt`, not v0.6.1's end.
- Its checks are against v0.6.1b's end, every fourth against v0.6.0's.
- Its settings check takes v0.6.1b's `train.cmd` as the reference, and its identity check and `start.ps1` take the new
  start.
- The judge's refit uses the games of v0.6.1 and v0.6.1b together ❓.

Noted on v0.6.2's card; its files are changed only on the owner's go.

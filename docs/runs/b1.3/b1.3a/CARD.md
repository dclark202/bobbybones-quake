# b1.3a: the strategy head opens, as the only learner of his target choice

*2026-11-01 (owner): "B1.3 then becomes the opening of the strategy layer, WITH the fix to the learning so that this blowup doesn't occur again". Why: [b1.2a's card](../../b1.2/b1.2a/CARD.md). The family: [README](../README.md).*

**Marks:** ✅ built and tested · ⏳ to build · 🧪 to measure · ❓ owner's decision

## Decisions so far (owner, 11-01)

| Decided | |
|---|---|
| The order | b1.2c first (table, firing costs, contact freedom, jerk), to noon on 11-02; then this run: "the opening of the strategy layer, WITH the fix to the learning so that this blowup doesn't occur again" |
| b1.2a | scrapped: unusable, saved only. Not a start for anything |
| The hold rule | 40% holds a step; under 50% flagged (his number for the runs of 11-01; confirm here) |
| After this | `DMG_TAKEN_W` to 0.8 on enemy damage only is b1.4, if he still needs it. Rocket jumps and movement, Aerowalk's red armor with them, are later: "aerowalk will get fixed when we do movement later" |
| The head's pay | combat plus win (his choice for b1.2a, 10-31) |

| Agreed in the discussion; the owner is to confirm with this run's agent | |
|---|---|
| One learner | he accepted the blowup's diagnosis and asked for a real fix, not a patch; one learner is the proposal he wanted built in. The alternative: both learners, the head on his whole pay |
| The item rule stops teaching his target with it; item pay stops moving his target directly | consequences he has been told of |

| Open: the owner's, with this run's agent | |
|---|---|
| Length; the ramp's speed (proposal: five steps, 10 updates each); the tripwire's limit; floors and the enemy's share target, from b1.2c's end; which save, if a b1.2c stage harmed him | |

**The owner will hold this discussion with this run's agent: nothing here is scheduled, and no check or run starts unasked.**

## FOR THE NEXT SESSION: checks, then the run (owner, 11-01)

**Everything below waits for b1.2c to end (~11:57 on 11-02). Nothing starts beside it, and the run itself needs the owner's go and his length.** The run's files are written and have only had a syntax check at most; none has run. Rule 3 and the card's blowup section apply.

| # | Do | Passes when |
|---|---|---|
| 1 | b1.2c ended: `data/sim_runs/duel_gru_b1_2c/keep/policy_end_b12c.pt` and `opt_end_b12c.pt` there (a waiter of the session of 11-01 writes them; if not: `python tools/run/stop_run.py duel_gru_b1_2c b12c --now`). Read its card and checks. If b1.2c's stages harmed him, ask which stage's save to start from: `policy_table`, `policy_nofire`, `policy_contact` | it is judged usable by the owner |
| 2 | The head against itself: `python tools/run/head2head.py selfchk <any run> <a head save> 8 <same save> 8 --maps sinister,aerowalk,lostworld,furiousheights --games 16`, on a save with a head. On 11-01 b1.2a's update 80 read 19-29 on Blood Run 8-8, Hektik 8-8, Sinister 3-13, and a short instrumented test looked lopsided. Should be ~50%. Note `--contact-a/-b`. If it isn't, find out why in `tools/duel_eval.py` before trusting this run's checks | about 50%, by seats |
| 3 | `python docs/runs/b1.3/b1.3a/make_files.py <minutes>` (the owner's length), then `python tools/run/check_settings.py docs/runs/b1.3/b1.3a/train.cmd --ref docs/runs/b1.2/b1.2c/train.cmd "--allow=--run,--minutes,--head2,--head2-cap,--head2-ctrl-src,--head2-gate,--head2-open,--head2-start,--head2-pay,--head2-sole,H2_START"` | PASS |
| 4 | `%USERPROFILE%\anaconda3\python.exe docs\runs\b1.3\b1.3a\trial.py 40 > docs\runs\b1.3\b1.3a\trial.log`, CPU, ~1 h. It is the test of the fix: `sim/train_duel_rnn.py`'s `--head2-sole`, the cap, the skip, all unrun | ALL PASSED, and read the lengths it prints |
| 5 | Test `ramp_b13a.py` on a fake folder, as `docs/runs/b1.2/b1.2c/ramp_test.py` does; set `--bias-lim` from the trial's numbers (default 60) in `start.ps1` | steps and tripwire fire |
| 6 | The head with the fix on a private server (`tools/run/local_server.sh`): `sim/export_duel.py` is fixed for a head; the image needs b1.2c's `sim/` for `CONTACT_FREE` (`qlbot:playaim2` does not have it) | a game with no error |
| 7 | Report to the owner; on his go: `powershell -ExecutionPolicy Bypass -File docs\runs\b1.3\b1.3a\start.ps1`. Watch that it has really started or not (a rejected command ran on 11-01) | |

**Watch while it runs:** `TRIPWIRE` in `watch/watch.log`, and the trainer's exit, every time (a monitor without the exit line missed b1.2a's crash).

## THE BLOWUP: what it was, and what must be true before and during this run

**What happened in b1.2a (crashed 11-01 15:18, update 82):** the head and the hands both learned his target choice, on different pay. Their numbers are added, and each treated the other as fixed, so where they disagreed both pushed harder without limit. Bias length: 5, 55, 162, 317 at updates 20, 40, 60, 80. Its numbers went to NaN and the trainer died. **It looked healthy throughout:** checks of 54-56% and a "48%" bias share hid it, because the two sides were cancelling. A win rate cannot catch this; only the logits' size can.

**The correction, three parts, none optional:**

| | Part | Stands for |
|---|---|---|
| 1 | **One learner:** the hands' target outputs stop learning; only the head learns his target choice | the cause. Without it there is a tug of war |
| 2 | **A cap on the head's ratio** (`sim/train_duel_rnn.py:4610`), as on the hands', and a skip of any update with a non-finite gradient | a crash can't kill a night's run; neither is the fix |
| 3 | **A tripwire:** the trainer's `head2.bias`, and the hands' target logits' length, read at every update. Flagged in the chat at once if either passes a limit set from the trial | it is seen in hours, not found by a crash |

**Must pass before the start (`start.ps1` refuses otherwise) ⏳:**
- A test that the hands' target outputs do not change in an update, and that everything else in the hands still does.
- A trial from b1.2c's end through the whole gate, with the numbers read: the bias's length levels off, and the hands' target logits stay at their starting size. A trial that keeps climbing means no start.
- A fixed-seed identity at gate 0: the head shut answers as the network without it.

**Metrics not to trust alone:** `bias_share` (it reads 48% while both sides cancel) and win rate. Read the lengths, and the correlation of the two sides in games (`-0.99` in b1.2a; it should not be near -1).

## The owner's page

| | |
|---|---|
| Started from | b1.2c's end with its optimizer, given the head shut (`tools/head2_init.py add --gate 0`) |
| Run | `duel_gru_b1_3a` |
| The fix ⏳ | his target choice is the hands' fixed logits plus the head's bias, and **only the head learns it**. The hands' target outputs stop learning: no policy gradient, no entropy, no rule's label on them. The hands' other outputs learn as before |
| What it learns from | combat plus win pay, as b1.2a (`--head2-pay combat_win`) ❓ with the hands' prior fixed, item pay no longer moves his target directly |
| The item rule | stops teaching his target when the fix goes in, as it teaches only the hands. What it taught stays in the fixed preference |
| The ramp | shut for 10 updates, then `H2_GATE_CAP` up in steps ❓ to set from a trial: five steps, 10 updates each, ~4 h, is the proposal |
| Hold rule | goes on above 40%; a check under 50% flagged; 40% or less holds the next step ❓ |
| Length | ❓ the owner's, before the start |
| League, checks | b1.2c's end and v0.6.0's end as anchors; 160 games against the start; the panel. Never stopped |
| Kept | the head-open save, every step's save with its optimizer, the end |

## What went wrong in b1.2a, and why this fixes it

Two learners with different pay added to the same logit: each treats the other as fixed, so where they disagree each pushes harder, and softmax only sees the difference. At update 80: lightning +265 from the head, -257 from the hands, +8 in play; correlation -0.99. With one learner there is no opposing push. The rule's and the entropy's terms go with the hands' side, so nothing else pushes against the head.

## Judged by

| Measure | Wanted |
|---|---|
| The bias's length, and the hands' target logits (fixed) | bias's length bounded, steady after the opening; no NaN |
| Win rate against the start, v0.6.0's end | at least 50% |
| Enemy's share of his targets | clearly up; number set from b1.2c's end |
| Items a minute, stack at fights, time at spawns | floors set from b1.2c's end |
| A check with the head blanked | he is worse without it |
| The owner's play test | "he picks fights" |

## The equilibrium

The head plans for frags and winning on top of a fixed preference. In self-play its part is zero-sum: both copies gain from a plan that wins fights and games. Items count for it through what they add to winning and to fights, so it may leave some item runs when level or ahead, and go for an item when behind if that wins. The danger: it undervalues items, or holds a spot (v0.4.4).

## Red team

| | |
|---|---|
| Items may fall | the head has no item pay. Measured alternative: `--head2-pay all`, in which it learns the whole pay |
| Hands' logits drift | the target row is fixed, but its input, the hands' memory, keeps learning. Small from b1.1's size (~20), much larger at b1.2a's ±250, the reason b1.2a's saves are not used. Watched |
| Fixed preference | a hand-built-looking prior, inherited; a later step can fade it |
| A check tool with a head in the opponent seat | a short test of a head network against itself looked lopsided; a 64-game check runs. To settle before this run |
| Crash guards | a cap on the head's ratio (`sim/train_duel_rnn.py:4610`) as on the hands', and a skip of a non-finite update, go in beside the fix |
| Untested | the head as sole learner has not run. A trial of ten updates and a check before the start |
| Pay pathologies (ledger) | watched: negative scores, sign flips, lopsided games |

## Before the start

| Step | Where it stands |
|---|---|
| The fix, in the trainer and its identity | ⏳ the blowup's part 1 |
| The guards | ⏳ part 2 |
| The tripwire in the watcher | ⏳ part 3 |
| A trial through the whole gate, with the lengths read | ⏳ `start.ps1` refuses without it |
| The self-check's verdict | 🧪 |
| The server | the head in the plugin: the image runs it ✅ (b1.2a's update 50 against the game's bot); with the fix to retry ⏳ |
| The owner's go ❓ | |

## Changes on the fly

| Time | Change | Why |
|---|---|---|

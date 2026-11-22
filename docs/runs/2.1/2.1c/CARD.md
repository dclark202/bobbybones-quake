# 2.1c: the lock out by the held draw

**ENDED 2026-11-15 17:06 at update 50** (stopped at its save on the owner's word, to start 2.1d earlier; `keep/policy_end_21c.pt` + opt).
The trial's answer: **the held draw alone did not teach him to hold a goal, and he did not collapse.** At the constant share 0.25 (updates
33 to 50) his mid-trip changes on held trips stayed at 41 to 48 a seat-minute, 55 to 58% of them taken back within 2 seconds. Checks
against 2.0e's end: 104-96 = 52.0% (update 10, all lock), 96-104 = 48.0% (update 30; Sinister 4-16). Frags 2.0 to 2.1 a match-minute
throughout; targets reached 23% to 19%. The slow plan (shadow) predicts his next 2 seconds with an error of 0.46 against 1.2 for his
fast scores; the pull's readout: 28% fewer mid-trip changes at strength 1, 40% at 2 (replayed in the real simulator on the update-40
save: about 35% fewer at strength 1). The owner: more trips than on the lock is the point, not a fault. Next: [2.1d](../2.1d/CARD.md), the pull.

**Status at its start (2026-11-15): the owner's go given** ("Incorporate the other things you mentioned, and then start the run when it's ready. This is
2.1c"). A trial by day until about 19:00, then a review; what runs overnight is decided there.

## The owner's page

| | |
|---|---|
| Started from | **2.0e's end** (`duel_gru_2_0e/keep/policy_end_20e.pt` + `opt_end_20e.pt`). Nothing of 2.1b (no keep choice, no stay value, no frozen moments) |
| The one new thing | His goal stops being drawn again and again. The random numbers of his draw are rolled **once per trip** and held; five times a second his goal is the highest of his scores plus those numbers. It changes only when his own scores cross. With it, the head reads the goal he holds and how old it is, so his scores can learn to favour it (the learned comparison) |
| What goes out | The 8-second lock, by a share: a coin per trip puts the trip on the held draw (live `HELD_G`). At 1 the lock decides nothing |
| What is not in it | No keep choice, no judge, no timer, no margin we set |
| Pay | As 2.0e, with `--dmg-taken-w 0.9` (owner 11-14) |
| Length | **Until about 19:00** (owner 11-15: "I want this to run until about 7pm, and then we'll review and decide what to run overnight"). The trainer's time limit ends it; the update cap is set out of the way |
| The head's credit | `--head2-lam` 0.995 (about 5 s) → **0.998** (about 12 s), so a goal is credited over a trip. A setting, not new code; it makes the head's lesson noisier. Put to the owner and explained 11-15; he did not change it |
| In shadow | **The slow plan**: a second, slower opinion of where he is going, learning silently from update 0. Nothing reads it. The pull toward it is NOT built: it is the next step if the review says so |
| Control | 2.0e's end, in the league and in every check; every fourth check against 1.6a's end (the long-term control, as 2.1b) |

## The schedule (`ramp_21c.py`; never holds or steps back on its own)

| Updates | `HELD_G` | What plays | What it shows |
|---|---|---|---|
| 0 to 10 | 0 | The lock on every trip; the goal inputs in at zero weight; the longer credit on; the slow plan learning | The longer credit alone. Update 10's mark is the last all-lock save |
| 10 to 30 | 0 → 0.25 | A quarter of trips on the held draw by 30 | The first full-size reading of mid-trip changes |
| 30 to the end | 0.25 | Held there by design (owner 11-15) | Whether the mid-trip changes fall at a constant share; three quarters of trips stay on the lock, so a bad result does not sink the checks |

Checks every 20 updates, 200 games. Marks with their optimizers at 10, 30 and the end. Logged every update: the held draw's record
(share played, seat-frames on it, readings a second, new rolls and **changes mid-trip a seat-minute**), the slow plan's record, trips,
reached, the ledger. The first plan for this run (to share 1 by update 60, 100 updates) was replaced by this trial on the owner's word.

## The slow plan, in shadow (owner 11-15: "That seems like the most coherent approach so far")

The owner's words for it: "I think 'I'm going to go get mega' and then every 200ms I ask myself 'what else should I be doing' knowing that
I've already committed to getting mega. If something spikes and changes my mind then I change, otherwise I'm inclined to stick with the
goal I set for myself."

| Part | What | Plays? |
|---|---|---|
| The plan | A small layer read off the head's memory once a second and whenever he sets a goal, held between: his odds over the 17 targets for the next 2 seconds and the next 5 seconds | No. Nothing reads it; no gradient reaches the head or the hands (`sim/slowplan.py`, `--plan 1`) |
| Its lesson | His own fast choice averaged over the next 2 and 5 seconds. Not "which goal he held", which on a lock trip would teach it the lock (rule 13) | |
| Its skill, every update | How much better it predicts his next seconds than his fast scores of this moment do | |
| What the pull would have done | His held trips recounted with the plan added to his scores at three strengths: mid-trip changes a seat-minute at each | First order: the game is not replayed |
| What kind of changes | Of his mid-trip changes: the share he took back within 2 seconds (dithering), the share that followed news (the enemy seen, heard, a hit), the share that went against the plan | |

Why the pull is not in: the plan starts blank, so there is nothing to pull toward until it has learned; and the pull changes his target
scores, which must be wired identically into the rollout and every pass of the learner (1.7c's false collapse). It is built after the
review, if the numbers call for it. The limit of this form: it is a layer on the head's existing memory, not a slow memory of its own
(FTW's, BOTS.md section 2); the skill number says whether that is enough. Research: BOTS.md 13.2 (a slow learned prior the fast choice is
pulled toward) is this idea; the notes mark it compatible with rule 13 "if the prior is learned by the head itself, not an old network".

## What to expect at the start: he flickers on held trips, about four times the lock

Measured on 2.0e's end in the real simulator, share 0.5, 16 seats for a minute each (`tools/run/held_playtest.py`):

| Changes of goal a seat-minute | On the lock | On the held draw |
|---|---|---|
| Blood Run: all (at a trip's end / mid-trip) | 16.5 (12.0 / 4.5) | 65.6 (11.9 / **53.6**) |
| Aerowalk: all (at a trip's end / mid-trip) | 25.8 (16.7 / 9.1) | 92.5 (19.8 / **72.7**) |

I told you nothing would have to be learned for him to stop flickering. **That was wrong.** The resampling is gone, but his scores
cross about once a second on their own: under the lock they never had to be steady. So this run does not hand him a working commitment;
it hands him his own decisions and teaches them. What can bring the number down: each mid-trip change is now a decision that is credited
over the trip (the longer credit), and the goal inputs let his scores favour what he holds. Whether it does is what the run measures.
The ramp will flag "trips up 1.5x" as the share opens; that flag is expected, the question is whether `changes_min` falls after it.

## What was built

| Part | What | Where |
|---|---|---|
| The held draw in training | Per seat, one Gumbel number per target, rolled anew when his target ended (reached and not an arrival, gone, a spawn; on "nothing" once a second) together with the trip's coin. Under the coin: target = highest of scores + numbers at every keep reading. **The simulator is not changed**: it rides on 1.7a's keep column (always re-decide) | `sim/train_duel_rnn.py`: `--held`, `--held-g`, live `HELD_G` (range 0 to 1), the rollout's `if HELD:` blocks, the record `held` |
| What he learns from | On a held trip his target counts where it was a decision: a new roll applied, or a change mid-trip. A reading that kept the goal teaches nothing | the target's mask `b_live` |
| The learned comparison | The head's part **"goal"**: the target he holds (one of 17), its age (in twos of seconds, cut at 20 s), whether the trip is on the held draw. 19 numbers at the end of what the head's first layer reads, zero weights | `sim/head2.py`: `add_goal`, `goal_u`, `np_goal_u`, `np_kf_end`, the buffer `held_g`; `tools/held_init.py add / widen-league / same` |
| The checks' player | Plays the held draw and feeds the goal inputs exactly as the trainer does | `sim/test_suite.py` `Policy`; `tools/duel_eval.py`, `tools/run/dump_eval.py`, `tools/run/ws_eval.py` give it the trip-end column |
| The servers | The same in the plugin's forward pass; the export carries the share | `plugins/netpass.py` (`held_g`, `goal_on`, `kf_rows`), `plugins/duelbot.py` |
| The league | Each network plays at the share in its own file; anchors are widened the same way and play the lock (share 0); an anchor without a head is passed through | `tools/held_init.py widen-league` |
| The run's files | `make_files.py` (2.0e's command + `--held 1 --held-g 0`, `--head2-lam`, `--dmg-taken-w 0.9`), `train.cmd`, `start_live.py`, `ramp_21c.py`, `start.ps1`, `smoke.py`, `live_test.py` | this folder |

## Decisions taken while building

| # | Decision | Why |
|---|---|---|
| 1 | The simulator is untouched; the held draw is 1.7a's keep column with "always re-decide" | The lock rule's code stays as it is for the trips still on it |
| 2 | "Nothing" is not held: new numbers once a second | As today. The simulator turns a weapon he already owns into "nothing", and he would sit there |
| 3 | An arrival (the enemy hunted in view, a holding place stood at) is not a trip's end | So he can stay; 2.2's "hold a spot" needs it |
| 4 | The contact-free reading does not apply on a held trip | He already reads five times a second there |
| 5 | The age input is counted in twos of seconds | Measured: average 0.99, spread 1.04 (rule: a new input comes with its measured size). The one-hot columns are 0 or 1 by nature (averages 0.00 to 0.28) |
| 6 | The goal inputs open with the held draw, not as a separate step | They say nothing useful on a lock trip |
| 7 | The simulator takes the coin at his once-a-second reading | A trip's first second can still be on the other rule; by construction that only holds, never flickers |

## Tests (all on CPU, scratch folders, nothing deleted)

| Test | Result |
|---|---|
| The widened start answers as 2.0e's end (`held_init same`, real rows, random goals fed) | **0 of 44,800 actions differ** |
| Share 0 against 2.0e's end in the real simulator, 2,400 frames x 16 seats, two maps | **0 frames differ**, no coin in the column |
| The plugin's forward pass against the checks' player with the held draw at 0.5 (actions, keep column, whole memory) | **0 differences** over 2,400 frames, Blood Run and Aerowalk |
| The trainer, 3 updates at share 0.5 on the widened start (`smoke.py`) | ALL PASSED: exit 0, optimizer loaded (`head2.inp.weight` carried 938 → 957), held trips read 4.8 times a second, the head lists "goal 19" |
| `HELD_G` live (`live_test.py`): 0 at update 1, written to 0.5, played by the last update; 1.5 refused before the first rollout | ALL PASSED |
| `live_accept` on the start's file and all 62 files the ramp writes | PASS |
| `check_settings` against 2.0e's command and 2.0e's end | PASS; the differences are the card's (`--held`, `--held-g`, `--head2-lam`, `--dmg-taken-w`, run, length) |
| The ramp's flag thread on a smoke run's real metrics (40 s, a scratch folder) | No crash; the held line is logged every update; "the share played is none of the last written" fired, correctly (the live test had set 0.5 by hand) |
| The slow plan in shadow (built by an Opus agent, reviewed and rerun here): the smoke with `--plan 1` | ALL PASSED: both horizons have rows, the pull readout and the kinds of changes are recorded each update, the save carries the top-level entry `plan` with its Adam, a resume loads it ("from the checkpoint") |
| The slow plan cannot stop the run | Its four blocks in the rollout are wrapped: a failure prints one MAJOR PROBLEM line, turns the plan off for the rest of the run, and the run goes on (the ramp then flags "no plan record") |
| The live test again with the plan on | Failed once on a noisy threshold (share on the held draw 0.187 against a bar of 0.2 on a 96-frame sample), passed on the rerun (0.245). Read as noise in the test: the plan writes to no action, no held number and no random stream |
| `live_accept` on the new ramp (32 files), `check_settings` with `--plan` allowed | PASS, PASS |
| `start.ps1` | parses; run for the first time at the start (below) |

Known small thing: with the trainer's overlap on, the `held` record of an update can be the next rollout's (it is written when a rollout
ends). The ramp's check allows for it (it compares with the last four writes).

Not proven by a run: that the trainer with `--held 0` is bit-identical to before. Every new line is behind the switch except one buffer
in the head's file (`held_g`) and one per-seat list the simulators send; the trainer's small runs are not repeatable to the bit, so there
is no replay to show it. 2.1c itself runs with `--held 1`, where share 0 is covered by the tests above.

## Red team

| Assumed or hand-built | Weakness | Measured alternative / check |
|---|---|---|
| His scores become steady once changes are his own decisions | At the start they are not (table above). If they do not learn, he is b1.1a again: trips up, reached down | `changes_min`, trips, reached every update; the marks at 10 and 30 to go back to. The notes' next idea if it stalls: a learned slow prior the head's choice is pulled toward (BOTS.md 13.2) |
| A mid-trip change is taught like a fresh draw | Given held numbers, a change is not a draw from his probabilities; the lesson is approximate there | The target's KL and clip share as the share opens; the fallback is to teach only at new rolls |
| The longer credit (0.998) | The head's value was trained at 0.995; noisier advantages | Updates 0 to 10 show it alone: the head's value loss and advantage spread in the record |
| One roll per trip is enough exploration | Fewer independent draws on long trips | The target's entropy and each target's share by map |
| Goal inputs at zero weights behind no gate | They move the head's first layer as soon as held trips exist | 19 numbers, clamped, measured sizes; a blank test at the run's end (200 games with them zeroed) is owed by the inputs rule |
| League networks play the lock | He trains against opponents committed by a rule he is losing | The control check is against 2.0e's end on the lock; snapshots of this run carry their own share |
| Rule 11 | No new sum of two learned outputs: the target is still hands' rows + head's scores (decayed since 1.3b); sizes flagged over 40 by the ramp | |

Pathology check of the ledger: owed at the first updates of the run (no run yet).

## Research check (rule 14)

| # | Question | Answer |
|---|---|---|
| 1 | The game | No mechanic is touched; no simulator value changes (MECHANICS.md section 7 not involved) |
| 2 | What wins | Committing to an item and its timing is how control is kept and stolen (DUEL_STRATEGY.md "Principles distilled"; out of control: "steal when he commits"). Flicker works against all of it; "overcommitting throws games" (the trap note) is why the commitment must stay his to break |
| 3 | The player's view | The new inputs are his own goal and its age: things a player knows about himself. No truth input |
| 4 | In and out of control | No pay changes. A goal he can hold could become camping (v0.4.3); the panel's camping and spawn-camping measures stay in every check |
| 5 | Self-play equilibrium | Two copies that both flicker lose items to neither; the punishing opponent exists from update 0: 2.0e's end and the anchors, who commit by the lock |
| 6 | Bot precedent | BOTS.md section 0 names this failure ("a chooser re-deciding every 0.2 s flickers") and lists FTW's slow prior, a deliberation cost, FiGAR's learned repetition, the Quake III bot's one long-term goal. Section 8.4: hand-built bots solve it with hysteresis (a bonus for the running behaviour); the goal inputs are the learned form of that bonus. **Holding the draw's noise for a trip is not covered by the notes**: no listed system does it. Section 9: a deliberation cost "needs the owner" and is not used |
| 7 | Rule 12 | No pro number anywhere in it |

## Before the go

| | |
|---|---|
| ☑ | The owner's go, the length (to about 19:00), the schedule (held at 0.25), the slow plan in shadow |
| ☐ | The slow plan built and smoked (an Opus agent, on the owner's word: "Have an Opus 5.5 agent do the coding"), reviewed, its results under "Tests" |
| ☐ | `start.ps1 -Minutes <to 19:00> -Updates 100` (the update cap out of the way: the time limit ends the run) |
| ☐ | Its row in `docs/RUNS.md` at the start |
| ☐ | For a server play test afterwards: the image `qlbot` rebuilt (`sim/` and `plugins/` changed) |

Scratch folders left in place under `data/sim_runs/`: `scratch_21c_smoke`, `scratch_21c_smoke_b`, `scratch_21c_smoke_c`,
`scratch_21c_build`, `scratch_21c_play`, `scratch_21c_play2`, `scratch_21c_live_a`, `scratch_21c_live_b`.

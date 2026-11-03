# History: what was tried, what happened, what it taught

The short record of every model and experiment, so that nothing is tried twice by accident. The full write-ups are in
[archive/](archive/) (the per-version folders as they were, and the daily results log, [archive/RESULTS.md](archive/RESULTS.md)).
Newest first. A run's own card and report are in [runs/](runs/) from v0.6.0 on.

## Family tree: what each network started from

Every run gets a row here at its start, and a line in its series' table below (a stopped run, a side arm and a failed try too). To trace a network back, follow "Started from".

| Network | Started from | Run folder (`data/sim_runs/`) | Result, in a word |
|---|---|---|---|
| b1.3a | b1.2d's end (`keep/policy_end_b12d.pt`), its own optimizer, given the strategy head shut (`tools/head2_init.py add --gate 0`) | `duel_gru_b1_3a` | started 2026-11-02 20:22, 12 h: the head shut in play, learning to copy his target choice |
| b1.2d | b1.2c's save of update 250 (`keep/policy_nojerk_b12c.pt`), its own optimizer | `duel_gru_b1_2d` | 2026-11-02 13:33 to 19:41, ended at update 80 (owner), `keep/policy_end_b12d.pt` with its optimizer; **a success** (owner, after his play test); checks 56.2 / 57.5 / 51.2% against the start at updates 10 / 30 / 40, 59.4% against b1.1 at 60 |
| b1.2c | b1.1 widened to 980 inputs, the optimizer of b1.1a's update 170 (no head) | `duel_gru_b1_2c` | stopped 2026-11-02 12:52 at update 250 (owner); final check 55.6% against b1.1 (89-71) |
| b1.2b | b1.1, the optimizer of b1.1a's update 170 (no head) | `duel_gru_b1_2b` | 2026-11-01 16:12 to 17:40, update 20: stopped (owner) to give him the small items as inputs; 53.1% against b1.1 at update 10 |
| not approved | b1.1 | `duel_gru_b1_3a_UNAPPROVED_DO_NOT_USE` | a rejected command that ran, 11-01 15:44 to 16:08; not used |
| b1.2a | b1.1, the optimizer of b1.1a's update 170 (its own was not kept), the head added shut | `duel_gru_b1_2a` | **unusable:** crashed 2026-11-01 15:18 at update 82; the head and the hands fought over his target logits |
| **b1.1** | b1.1a's save of update 140 (`keep/policy_b1.1.pt`) | `duel_gru_b1_1a` | brain and pull out, lock 8 s; on the public servers since 2026-11-01 |
| b1.1a | b1.0a's end, its own optimizer | `duel_gru_b1_1a` | its lock fade left out of b1.1: its end at 1 s lost to b1.1 at 8 s 66-94 and to b1.0a's end at 8 s 68-92, each seat at its own lock; the 73.8% at update 170 was a shared lock's harm to b1.0a |
| **b1.0a** | v0.6.0's end, its own optimizer | `duel_gru_b1_0a` | success |
| v0.6.1e | v0.6.1's update 90, v0.6.1's end's optimizer | `duel_gru_v0_6_1e` | stopped early |
| v0.6.1d | v0.6.1's update 110, v0.6.1's end's optimizer | `duel_gru_v0_6_1d` | stopped; beat v0.6.0's end, fought less |
| v0.6.1c | v0.6.1's update 250, v0.6.1's end's optimizer | `duel_gru_v0_6_1c` | failed |
| v0.6.1b arm B | v0.6.1b's end | `arm_v061b_ent002` (`docs/runs/v0.6.1b/arms/`) | abandoned |
| v0.6.1b | v0.6.1's end | `duel_gru_v0_6_1b` | failed |
| v0.6.1 | v0.6.0's end | `duel_gru_v0_6_1` | level, weaker at the end |
| **v0.6.0** (the retrain; the first run's saves were lost on 10-28) | v0.4.2b's end | `duel_gru_v0_6_0` | good: on the servers to 2026-11-01 |
| v0.5.1 | v0.5.0's end | `duel_gru_v0_5_1` | failed |
| v0.5.0 | v0.4.2b's end | `duel_gru_v0_5_0` | failed |
| v0.4.4 | v0.4.3's update 80 | `duel_gru_v0_4_4` | scrapped |
| v0.4.3 | v0.4.2b's end (update 140) | `duel_gru_v0_4_3` | scrapped |
| **v0.4.2b** | v0.4.2's save 160, with the brain tuned offline (`brainppl/policy_brainppl.pt`) | `duel_gru_v0_4_2` | best of its day |
| v0.4.2 | v0.4.1's end; the first try is `duel_gru_v0_4_2_try1` | `duel_gru_v0_4_2` | good |
| v0.4.1 | v0.4.0b's end | `duel_gru_v0_4_1` | good |
| v0.4.0b | v0.4.0, a save with the brain's new outputs | `duel_gru_v0_4_0` | good |
| v0.4.0 | v0.3.10's end + a fresh brain | `duel_gru_v0_4_0` | good |

Older runs' starts are in their write-ups ([archive/](archive/)). The data loss of 2026-10-28 took the older run folders: v0.4.0 to v0.4.1 and v0.4.3 to v0.5.1 are gone (their folder names above are from the write-ups), and only `duel_gru_v0_4_2` survives of them.

## b1 (2026-10-31 →): win chance on top of the pay table

New names, bN.Nx, and the series to stick with (owner). The plan: [PLAN.md](PLAN.md), [design/B1_PLAN.md](design/B1_PLAN.md).

| Version | What | Result | Lesson |
|---|---|---|---|
| b1.3a (2026-11-02 20:22 →, 12 h) | from b1.2d's end: the strategy head in, shut in play all run, learning to copy his target choice (KL to the hands' choice on read frames, `--head2-copy`), its value on his whole pay; the hands train on as b1.2d. The first design (the head as the only learner, opened on pay) moves to b1.4 ([runs/b1.3/b1.3a/CARD.md](runs/b1.3/b1.3a/CARD.md)) | running; its trial stopped at update 102 on the owner's word (the copy reached the head only; agreement about 20%, the average choice, on 40 readings an update) | |
| b1.2d (2026-11-02 13:33 → 19:41, update 80; **a success**, owner) | from b1.2c's update 250: five pay changes faded together over updates 10 to 70 (the health and armor table by the point with the decay above 100 charged back, speed pay 0.25 → 0.125, damage taken 1.0 → 0.8, the stack lead 0.7 → 0, the long rail 0.12 → 0.25); the trainer on the 8 performance cores, the checks on 8 efficiency cores ([card](runs/b1.2/b1.2d/CARD.md)) | **a success** (owner's play test: "the goals are met. He was clearly engaging more in fights, and would quickly redirect to fight when he heard me nearby"; "the rocket fights are getting much better"). Against the start (b1.2c's update 250) 56.2 / 57.5 / 51.2% at updates 10 / 30 / 40; against b1.1 59.4% at 60, frag share 57.5% (b1.2c's end: 55.6%, 51.6%). The panel: the enemy as his target on Hektik 22% at the end against 10%; roaming on Blood Run 33 to 28 cells during the fade, 31 at update 70 | five pay changes at once, read by group: fine here; the small items count once priced by the point (a 5-health item among his targets on Aerowalk). On 8 check cores a check outlasts 10 updates: checks every 20 from now on |
| b1.2c (2026-11-01 evening → 11-02 12:52, update 250) | b1.2b's plan, with the 8 nearest small health and armor places as inputs; firing costs from update 60 ([card](runs/b1.2/b1.2c/CARD.md), [design/SMALL_ITEMS.md](design/SMALL_ITEMS.md)) | stopped at update 250 (owner) for b1.2d; final check 55.6% against b1.1 (89-71), frag share 51.6%. Reads the small items' inputs, barely acts on them (taken near his way 22% to 23%) | the prechecks found checks that would have failed all night: a change of inputs must go through the checks, panel and logger as the start script sets them |
| b1.1a (2026-10-31 21:11 → 11-01 07:27, update 180) | from b1.0a's end, the brain's old belief, the pull toward level and the target lock out, in one run ([runs/b1.1/b1.1a/CARD.md](runs/b1.1/b1.1a/CARD.md)) | brain and pull out at no cost seen: 60.6% against b1.0a's end at u130. Lock to 1 s: trips 12.6 to 20.0, targets reached 40% to 21%, the enemy's share unmoved, frags 1.56 to 1.41. **b1.1 = the save of update 140, before the lock's fade** (owner) | the lock alone doesn't make him fight: with no head to use it the freedom became flicker. A kept save must keep its optimizer (b1.1's own was lost) |
| b1.0a (2026-10-31 10:56 → 21:00) | from v0.6.0's end, win chance pay added on top of the unchanged table (`WIN_ADD`, live: 0 → 0.15 → 0.33, about a third of the total), `judge_v060_wpn`, `WIN_END`, no rescale; checks against v0.6.0's end only ([runs/b1.0/b1.0a/CARD.md](runs/b1.0/b1.0a/CARD.md)) | stopped at update 160 (owner: a success). Against v0.6.0's end 61.9 / 53.8 / 55.6 / 58.8 / 49.4 / 56.2 / 55.6 / 55.0% at updates 10 to 150 (a save every 20; `WIN_ADD` 0.33 from update 80). End: frags 1.61 a match-minute, rail in hand 0.14, entropy 1.84. The owner: "he's better than any of the v0.6.1x bots"; his biggest weakness, tunnel vision on items | adding win pay to the table kept what replacing the table lost; the rail's slide (0.22 to 0.14) remains unexplained |

## v0.6 (2026-10-27 → 10-31): the pro-measured aim

**How the line ended (owner, 2026-10-31):** mixed success, with many of its questions answered in the negative. v0.6.0 is the good result; the v0.6.1 tries did not
give a base to build on. Review: [runs/v0.6.1d/REVIEW_v0.6.1.md](runs/v0.6.1d/REVIEW_v0.6.1.md). v0.6.2a, v0.6.3 and v0.6.4 were never run; their cards stay as drafts for b1's later steps.

| Version | What | Result | Lesson |
|---|---|---|---|
| v0.6.1e (2026-10-31 08:22 → ~10:17, stopped by the owner at about update 30) | from v0.6.1's update 90, the table to half and win chance to half over 40 updates, then the pull and the brain's old belief together ([card](runs/v0.6.1e/CARD.md)) | 44.4% and 52.5% against its start at updates 10 and 20; replaced by b1 before its fades began | no conclusion: too short |
| v0.6.1d (2026-10-30 17:41 → 10-31 ~07:55, stopped by the owner at about update 219) | from v0.6.1's update 110, the old pay and win pay about equal in size, the pull and the brain's old belief faded together ([card](runs/v0.6.1d/CARD.md)) | against v0.6.0's end 59.4 / 67.5 / 60.0 / 50.0%; level with its start. But frags 1.75 → 1.32 a match-minute, rail in hand 0.22 → 0.09, panel flags for hunting and camping. `WIN_W` 0.8 kept only 20% of combat, not the half intended | the fades can be survived on a blend; he can win checks against v0.6.0 while fighting less, so win rate against old selves and skill measures tell different things, and it is unsettled which matters against people. Check what a dial setting really pays before running it |
| v0.6.1b arm B (2026-10-30, stopped at about update 17) | from v0.6.1b's end, the entropy bonus lower (`--ent-coef 0.002`) | abandoned for v0.6.1c; entropy flat at 1.987 | no conclusion: too short |
| v0.6.1c (2026-10-30, stopped at update 130) | from v0.6.1's update 250, the rescale, the pull and the brain's old belief together ([card](runs/v0.6.1c/CARD.md)) | 43.1% against v0.6.0's end and against its start; entropy rose with the rescale on | keeping the pay's size up did not stop the drift: it was not only a matter of pay size |
| v0.6.1b (2026-10-29 → 10-30, stopped at update 181) | from v0.6.1's end, the brain's old belief out, the refit judge, `WIN_END` ([card](runs/v0.6.1b/CARD.md)) | no-go: 43.8% against its start, 40.6% against v0.6.0's end; rail in hand 0.06, rocket 0.31; the league alone hid the slide | check against fixed networks; several changes at once cannot be told apart |
| v0.6.1 (2026-10-28 20:05 → 10-29 17:52, update 340) | the pay faded to win chance only (done update ~153), then the view's pull toward level faded out (`LEVEL_PULL` 0.95 → 1.0 from update 250, owner); the game-end pay fault found by an audit and left in (fixed for v0.6.1b: `WIN_END`) | level with v0.6.0's end on win chance only (50.0% over 800 games; 55.5% during the fade); the end lost to its own save before the level fade, 144-176 (45.0%), and played weaker in the owner's test; a slower game (frags 1.65 → 1.42 a match-minute), the rail out of his hands (in hand 0.21 → 0.13), items held with no item pay. Kept: `keep/policy_end_v061.pt` + `opt_end_v061.pt` (v0.6.1b's start) and `keep/policy_prelevel_v061.pt` (update 250, to return to; no optimizer), both backed up ([runs/v0.6.1/CARD.md](runs/v0.6.1/CARD.md)) | win chance alone held his level but did not lift it in 190 updates; nothing in the pay asks for the rail's use, and the pros' games price owning it near nothing too; one change at a time (the level fade and more win-only training cannot be told apart) |
| v0.6.1 (as started) | pay by win chance only, the chance from **the judge** (`sim/win_judge.py`): lead + stack edge in frags, the stack in a lasting and a decaying part, the owner's four axioms (frag good, death bad, damage dealt good, taken bad) in its shape; fitted on v0.6.0's 300 self-play games and frozen; the rocket launcher and the rail set to the lightning gun's worth by hand; no shaping; `WIN_GAIN` sized in the run | the fit: held-out log loss 0.378 (A, the hand-built formula: 0.392; B2, a hand-shaped fit: 0.380); the first form of B either saturated (capped) or paid a frag negative (free), and overtime labels had faked a 1.4 s fade (review of 2026-10-28); the dry run found the ramp's `WIN_GAIN` clip at 0.25 .. 4 (the judge's scale needs ~0.07) | a learned value with the axioms in its structure, not a hand formula; check a scale's assumptions when the thing it scales changes |
| v0.6.0 (retrain, 2026-10-28) | the same setup again after the data loss, the brain's people lesson from the pro demos only; ended at update 80 (owner) | crashed twice at the start: 9 of the recovered league networks were corrupt (weights 1e38 / NaN); the league cut to v0.4.2b's end. The checks had never run (a missing settings file in tools/run/panel.py), fixed at update 15. Against v0.4.2b's end: 52.5 / 59.4 / 55.0 / 56.2% at updates 20 / 40 / 60 / 80. On both public servers from 2026-10-28 ~01:05 UTC with the four `!aim` files; open-weights release v0.6.0 | check recovered files before using them (load them all); a watcher's threads must log their errors |
| v0.6.1 (first plan) | pay by win chance only: v0.5.1's fade again from v0.6.0's end, with potential shaping, a critic warm-up, the pay ledger | not started: the calibration showed the stack term could pay a frag *negative* (late, with a lead); the owner chose "B": fit his chance of winning directly on game results | red-team every hand-built part of a pay before the go; a stand-in (the next-frag model + a symmetric shortcut) is not the thing paid for |
| v0.6.0 | v0.5.0's setup (the loophole fixes) from v0.4.2b's end, with `!aim default` = the pros' mean measured knob by knob from 100 demos a map (aim2); 65% whole games / 35% pro starts, no movement practice | 170 updates overnight; 52-64% against v0.4.2b's end at the same aim (61.9% at update 130); rockets in hand too little against the pros (23% of the big three vs 38%), lightning gun too much | measuring the aim on the pros (not fitting by feel) gave a fair, strong default; the owner: "much more fair" |
| (2026-10-30) | leaderboard: **the rating by games won and lost, not frags** (owner: "it should just be win loss"), worked out again from every recorded game; a quit is the quitter's loss if behind after more than 5 minutes, else it does not count | Bobby 1,215 (he was 1,339), v0.1 and older have no recorded games and no rating; both servers rebuilt with it the same day (image `qlbot:pub-1a616d3`, branch `pub-perf`) | a person with one win starts above someone with a long record and a recent slump; the ± shows it |
| (2026-10-30) | leaderboard site: **a page for every player and for Bobby** (B-290): lifetime record, rating, maps with heat maps, weapons, playstyle, by version and aim; linked from the board and the game reports | live on the owner's go; the game reports' "Held" column found wrong (B-296) | the numbers come from the same public summaries as the reports; a page's address is a code from the anonymous key, and `!anonymous` removes it |
| (2026-10-29/30) | servers: **the frame budget** (branch `pub-perf`, images `qlbot:perf`, `qlbot:perf2`): the inputs, the network and the hearing check made faster, bit for bit the same numbers (all ten maps, on the PC and in the server image); both public servers moved to 1 vCPU / 1 GB boxes | the frame on the same host 15.5 -> 13.6 ms median, late frames 2.8% -> 1.4%; on 1 vCPU about 1% late, about 560 MB used; Bobby's work is single-threaded (a second core did nothing) | measure on the server (`DUEL_TIMING`, `DUEL_PROFILE`, a private sparring A/B); hosts have slow spells with no steal shown; on one core background jobs need the idle class (`chrt -i 0`), not `nice`. [guides/FRAME_BUDGET.md](guides/FRAME_BUDGET.md) |
| (2026-10-28) | servers: the viewmodel fix (`EARLY_BOBBY`: Bobby kicked and added again in the map hook, so a person's game loads his model) rolled back on both public servers (`EARLY_BOBBY=0`, every other setting the same, checked by a diff of the containers) | a play tester on EU after the first game: Bobby invisible (heard, not drawn), under the tester's own name on the scoreboard; the log shows the kick and re-add at that map change | the wrong player model is a known Quake Live bug (owner): live with it rather than work round it in the map hook. `tools/duel_server.sh` now defaults to `EARLY_BOBBY=0` with `PUBLIC=1` (still 1 on local servers) |
| (2026-10-28) | **data loss**: a repo cleanup deleted the whole local data folder (worktrees' `data` are links to it) | recovered: v0.4.2b's end + optimizer, its league, the server keys; lost: every v0.6.0 save (SSD), the people's brain pack (37 local sessions), the training nav files (rebuilt from the server's, 87-99% identical) | never delete near links into `data`; nightly backup to `T:`; see CLAUDE.md's hard rules |

## v0.5 (2026-10-26 → 27): failed

| Version | What | Result | Lesson |
|---|---|---|---|
| v0.5.1 | pay by win chance only (the win part crossed in, every other pay faded out, 25-min steps) | the checks fell from 47% to 37% by step 4; more passive (fewer frags); stopped. The owner: "v0.5 is a failure" | the win table makes a leader's frag worth little late and protects leads; the stack term is weak with a lead of 3+; damage underpaid against frags (0.42 of a frag vs 0.55) |
| v0.5.0 | from v0.4.2b's end: the loophole fixes (WEAPON_FREE, SPEED_LOS, GONE_BELIEF, TELEFRAG, JRUN_SPEED_BACK, SMALL_ZERO), `!aim default` as one speed error with caps tuned by the owner's play | never beat its start | an aim error tuned by feel and self-play calibration misled; measure the pros instead (→ aim2) |

## v0.4 (2026-10-22 → 26): the brain

| Version | What | Result | Lesson |
|---|---|---|---|
| v0.4.3 / v0.4.4 | the item rule faded, then the strategy head opened (69% against v0.4.3), generated mid-game starts | **scrapped: spawn camping** | a target choice left unguided (rule faded before any head) finds degenerate holds; a weapon target became a free "hold here"; open a head *before* fading the rule it replaces |
| v0.4.2 / v0.4.2b | the 76 rule-made inputs faded out of the hands (the brain reads them); the brain also taught on people's games | **the best network to date** (v0.4.2b's end: the start of v0.5.0 and v0.6.0); reads the owner far better (target 24% → 34%) | a first try dipped at fade 0 (42.5%) and was restarted with the fade from update 1 |
| v0.4.1 | the brain's answer into the hands as an attention token, opened slowly | passed its gate (85-75); the owner: "he actually is keeping track of me" | |
| v0.4.0 / v0.4.0b | the brain: a separate memory that tracks the enemy (place now and 1-4 s ahead, stack, target, item race), from his senses only; zones, speed and direction | the brain past the old hand-built belief everywhere, no gradient into the hands | the enemy picture and the hands need separate memories |

## v0.3 (2026-10-14 → 22): one movement network, pre-aim, watching

| Version | What | Result | Lesson |
|---|---|---|---|
| v0.3.11 | the knowledge pay (paid for tracking the enemy) | built; superseded by the brain | |
| v0.3.10 | pay for watching the right spot before a sighting; LG muffles hearing | beat v0.3.9 46-0-34 | the watching pay barely built the habit |
| v0.3.9 | pre-aiming pay | **65.2% against v0.3.8**, rail frags 3.9% → 9.5% | |
| v0.3.8 | every aim limit written out; QL's fire timing; senses fixed; drift inputs (off again: no effect) | | audits found the rail held back by a one-frame delay, senses leaking, his aim ~50 ms quicker than the pros |
| v0.3.7 | pro starts, auto-hop, missiles as points, the game's respawn and spawn points | 71.7% against v0.3.6 | |
| v0.3.6 | rocket aim, pre-fire, emergence point; speed work on the simulator | | |
| v0.3.2 → v0.3.5 | one movement network: the legs switch faded and removed | the switch fade failed (he learned round it); removing the output worked | don't fade a switch the policy can route around: remove it |
| v0.3.1 | the believed enemy stack, the hunt; legs learning; the game's physics | 63.8% against v0.3; public as v0.3.1 | |
| v0.3 | baseline with overtime | | the judge that sees the truth did not help |

## v0.2 (2026-10-11 → 13): attention

| Version | What | Result | Lesson |
|---|---|---|---|
| v0.2.2 | the fixed clock; a slow memory (left out) | | |
| v0.2.1 | stages B and C (places as targets, ways, whole games, the guessing game) | **fell to 25% in 20 updates**: the lesson grading his keys against the movement network | a new lesson must pass ten updates and a check against the control before a start |
| v0.2 | attention stage A, 143 inputs, ten maps, the two-minute value | 56.7% against v0.1 | the checks' noise: the same network against itself reads 48.8% (±10 points a map) |

## Before v0.2 (v0.1 = v15c and older)

The yard (`arena1`), movement teachers, the legs as a separate network, the first public server. Full notes in the git history
and `data/docs_old/` (local). Lessons that still hold are in CLAUDE.md's gotchas.

## Lessons that are now rules

- **Pay**: every pay change states its self-play equilibrium; anything paid for progress is paid on a running best; red-team the
  ledger (negative frags, sign flips, lopsided games) before a go.
- **Starts**: one new thing a run, opened slowly, tied to the checks; a new lesson passes ten updates and a check first.
- **Measure, don't guess**: the aim from the pros; calibrations are never skipped or approximated to meet a start time.
- **Settings**: every check and calibration is diffed by script against the run's command, live settings and checkpoint.
- **Data**: never delete near `data`; nightly backups to `T:`.

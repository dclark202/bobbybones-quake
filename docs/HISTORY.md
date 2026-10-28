# History: what was tried, what happened, what it taught

The short record of every model and experiment, so that nothing is tried twice by accident. The full write-ups are in
[archive/](archive/) (the per-version folders as they were, and the daily results log, [archive/RESULTS.md](archive/RESULTS.md)).
Newest first. A run's own card and report are in [runs/](runs/) from v0.6.0 on.

## v0.6 (2026-10-27 →): the pro-measured aim

| Version | What | Result | Lesson |
|---|---|---|---|
| v0.6.1 (planned) | pay by win chance only: v0.5.1's fade again from v0.6.0's end, with potential shaping, a critic warm-up, the pay ledger | not started: the calibration showed the stack term could pay a frag *negative* (late, with a lead); the owner chose "B": fit his chance of winning directly on game results | red-team every hand-built part of a pay before the go; a stand-in (the next-frag model + a symmetric shortcut) is not the thing paid for |
| v0.6.0 | v0.5.0's setup (the loophole fixes) from v0.4.2b's end, with `!aim default` = the pros' mean measured knob by knob from 100 demos a map (aim2); 65% whole games / 35% pro starts, no movement practice | 170 updates overnight; 52-64% against v0.4.2b's end at the same aim (61.9% at update 130); rockets in hand too little against the pros (23% of the big three vs 38%), lightning gun too much | measuring the aim on the pros (not fitting by feel) gave a fair, strong default; the owner: "much more fair" |
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

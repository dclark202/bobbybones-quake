# v0.2.1 audited: what is unsound, the fixes, the next run, and the questions for the owner

2026-10-13, 16:30, a fresh read of the code behind [REVIEW_v0.2.1.md](REVIEW_v0.2.1.md) (file and line numbers as there).
Written for the owner. Section 5 is the list of questions; every one has my recommendation beside it.

## 1. The verdict

- **The two collapses have two separate causes, and both are in how a lesson's gradient reaches the network, not in the
  ideas.** The movement-autopilot lesson pulls his aim output toward the route's turn on half of all frames (fast
  collapse). The guessing game moves the shared layers outside PPO's trust region: his step per update doubles on
  every output, uniformly (slow slide). Neither is a wiring bug in the labels; the labels are made correctly.
- **The checks are even.** Both networks act by sampling as in training, both have the same aim delays (100 / 200 ms)
  and the same simulator settings, the control's new tokens are shut as converted.
- **Training's own reading against the control is not a check and should not be read as one** (finding 3).
- The base of v0.2.1 (the holding places as targets, the new tokens shut) holds against the control at 20 updates.

## 2. Findings on the implementation

### F1. The guessing game moves the policy outside the trust region (the slow slide)

The eight questions' losses are summed unscaled (after 20 updates about 9.6, of which `near` alone 4.0, `strength`
1.5, `target` 1.4, `fight` 1.25) and multiplied by 0.2, and with `--aux-trunk 1.0` the whole of that gradient flows
into the encoder, the attention part and the GRU (l. 1150, 1183). PPO's clip limits only PPO's own step on the
outputs; a lesson on the shared layers changes every output with no such limit. The record shows exactly that:

| | step (`kl`) | clipped share | step per output (turn, pitch, keys, intention) |
|---|---|---|---|
| none of the new parts (F) | 0.022 | 0.21 | 0.0063, 0.0099, 0.0008, 0.0024 |
| guessing game only (A) | 0.045 | 0.34 | 0.0132, 0.0204, 0.0017, 0.0047 |
| the second start | 0.043 | 0.33 | 0.0124, 0.0192, 0.0015, 0.0044 |

Every output's step is doubled, by the same factor, whether the lesson has anything to say about it or not: the
shared layers are being moved by something other than PPO. Beside that, the gradient clip (l. 1300) takes PPO's and
the lesson's trunk gradients together at a norm of 0.5, so where the lesson's is large, PPO's share of the step
shrinks. The lesson learns well (the unseen enemy's place from 780 units of error to 335, the landmark right 49%)
while he plays worse: it is winning the shared layers.

**Fixes, cheapest first.** (a) `--aux-trunk 0.1` (test run P, running) or 0 (test run Q): the questions learn from
his memory without shaping it, or shape it a tenth as hard. (b) Scale each question's loss by its own starting
value (or by the log of its number of classes) so eight questions weigh as one, and lower the weight to 0.05. (c)
Keep only the questions the owner asked for: `place` and `near` (where the enemy is); `fight`, `first`, `strength`,
`target` are extras that cost the most. (d) Clip the lesson's trunk gradient on its own, to a fraction of PPO's
(more code; only if a to c do not hold). Any of these is tested the same way: 20 updates, the ten-map check.

### F2. The movement-autopilot lesson trains his aim output on the autopilot's frames (the fast collapse)

`LEGS_LABEL` gives the movement network's four choices on every frame it carried him (`duel_env.py` l. 3047). The
trainer's lesson (l. 1238 to 1247) puts a cross-entropy on his outputs 0 to 3 there: the three key outputs on the
frames his hand reads them, **the view's turn on every frame** (`lms_[3] = lm_`, l. 1241). The turn output is his aim.
On 52% of all frames (`labelled` 0.52 at update 10 of the first start) it is pulled toward the direction of a route;
the record shows the turn is where the lesson is furthest from him (its loss 2.35 of the lesson's 3.9; agreement 40%
against 87 to 93% on the keys). These output rows are the same ones that aim in a fight. His hits in view did not fall
in training's record because aim is measured where he fights; the checks fell because the whole movement-and-aim
policy had been moved. `--legs-teach-trunk 0` was worse (30%), which fits: with the shared layers held back the whole
pull lands on the output rows.

Beside that, the lesson labels frames on which his own outputs did not move him (PPO masks those outputs out there,
`head_masks` l. 520). A lesson on frames PPO does not train, on rows PPO trains elsewhere, is a second policy
written over the first.

**Fix.** Drop the lesson. The owner's own words make it needless: "the jumps don't need to be exact ... he should be
taught the general path". The withholding alone (`LEGS_KEEP=0.9`, lesson at 0) read 55% and is the weaning he wanted:
one stretch in ten he moves himself and PPO trains that. If the lesson is ever tried again: keys only (no turn label),
withheld frames only (where his outputs moved him and PPO trains them too), weight 0.01, and the ten-update test first.

### F3. Training's reading against the control is not a check

`vs_anchor_kill_share` (l. 941 to 943, 1482) is made of: one opponent network per update, the control in one update
in four; the league half of every worker's matches; kills in 9.6-second slices (384 frames) of two-minute rounds;
weapon drills included (17% of rounds, where a kill is aim only); groups of three in which two of three seats are his
(`even_kill`: the even seats of a group). It read 0.575 at the start when the check read 0.521, and fell six points
while the check fell thirteen. **Fix:** count it in one-against-one normal rounds and whole games only (`kind` in the
simulator's `even_kill`), and say in every report that it is a hint; the check loop is the judge. With the next run
one against one and without two-minute rounds most of the distortion goes by itself.

### F4. Three questions are labelled on a quarter of the frames only

`fight` and `first` need their whole window (288 frames) inside the rollout (384 frames): only frames 0 to 96 get a
label (l. 185, 190, 249), and the GRU state there is carried in from the previous rollout. Not a cause of anything,
but weak; if these questions stay, a window of 120 frames or a longer rollout.

### F5. The place question on a fresh memory

`place` is asked on every frame the enemy is alive and out of view, from the first frame of a life on (l. 165). Right
after a respawn he cannot know; the loss is least at the mean place, and the shared layers are pulled toward that
answer. Harmless, wasteful. Cheap fix: ask only once he has seen the enemy this life (the simulator's `seen_t`), or
not in a life's first two seconds.

### F6. What is sound

The labels' hindsight ends at a death or a round's end (`nc`, l. 160) and the "later" labels do not cross a round
(l. 286); the masks take the league's seats out (`wgt`); the gate opening is tiny at its start (a gate of -6 is a
weight of a quarter of a per cent) and alone cost nothing (50%); the item rule's silence reads the belief of the frame
before and alone cost nothing (52%); the checks' two seats are set up alike (sampled actions, the checkpoints' aim
delays 100 / 200 on both, the same switches, `TARGETS` with the control's places row "never").

### F7. Process

Four parts started together; the night's test runs were ten updates on four maps and a 46% was read as noise; test run
W (the three parts without the guessing game, together) was stopped at the owner's word before its first check, so
"the three are safe together" is not shown yet. The rule now in `CLAUDE.md` (ten or more updates and a check against
the control before any start) stands; add: one new part per start.

## 3. The fixes in one table

| # | Change | Where | Test before use |
|---|---|---|---|
| 1 | Guessing game: trunk share 0.1 or 0; losses scaled per question; `place` and `near` only; weight 0.05 | trainer flags; `train_duel_rnn.py` l. 1183 | P and Q tonight; then one run of the chosen form, 20 updates |
| 2 | Movement-autopilot lesson dropped; withholding kept at 0.9 | the run's command file (`--legs-teach 0`, `LEGS_LABEL` off, `LEGS_KEEP=0.9`) | already shown (K: 55%) |
| 3 | Training's control reading counted in 1v1 normal rounds and whole games only, and named a hint | `duel_env.py` l. 105; the report routine | none needed |
| 4 | `fight` and `first` windows 120 frames, or the two dropped | trainer flags | with 1 |
| 5 | `place` asked only after a sighting this life | `aux_labels`, l. 165 | with 1 |
| 6 | One new part per start, 20 updates and the ten-map check each | `CLAUDE.md` | — |

## 4. The next run as the owner asked for it

One against one only; whole games, mid-game starts and spawn starts; a slice of movement drill. What exists:

- **Built and tested in a staging copy (not in the repo yet):** the spawn openings as the item rule's label in a life's
  first ten seconds (`OPENINGS=1`, the pros' openings per spawn, the second pickup avoided when the enemy is believed
  within 500 units); mid-game starts and spawn starts from saved real moments of whole games (bit-for-bit restore);
  the round mix by shares. Identity with every switch off proven, the group module regenerated and checked. The
  patches go into the repo when no job imports `sim/` (after tonight's test runs) and get a 20-update test run.
- **Exists already:** whole games (`GAME_P`), one against one (`--group 2`), weapon drills (`--kind-p`), item runs and
  jump runs on every map (`ITEM_RUN_P`, `JUMP_RUN_P`: his movement practice until now), the courses on the test map.
- **Open in the build:** the bank of saved moments starts empty in every process (the first ten game-minutes have no
  mid-game starts); a ten-second spawn start has its value cut at the round's end; the avoid rule can fall back to
  the item it avoided (`OPEN_SILENT=1` makes the label silent there instead).

The run I would propose, settings in plain words (the long form goes on the run's one page for his go):

| | |
|---|---|
| Start network | v0.2.1's start (v0.2's end converted), not a slid save |
| Players | one against one, 5,040 duels |
| Rounds | whole ten-minute games 60%, mid-game starts 20%, spawn starts 10%, movement drill 10%; no two-minute rounds, no weapon drills |
| Openings | on, as the item rule's label in a life's first ten seconds, silent where nothing is left |
| Guessing game | the form P or Q proves tonight, `place` and `near` only; else off |
| Gate opening, item rule's silence | on (each harmless alone; together with the rest: the 20-update test shows it) |
| Autopilot lesson | off; withholding one stretch in ten |
| Judged by | the ten-map check against the control at every tenth update; two checks under 45% stop it |
| Before the start | the exact setting, 20 updates, the check; then his go |

## 5. Questions for the owner (with my recommendation)

1. **The guessing game: keep in a reduced form, keep as a probe only, or leave it out of the next run?**
   Recommendation: wait for P (a tenth of the pull) and Q (none) tonight. If P holds level: P's form with `place` and
   `near` only. If only Q holds: a probe (it then tells us what he knows, teaches nothing) or out. One part at a time
   means it could also wait for the run after.
2. **The movement-autopilot lesson: dropped for good, or retested later in the narrow form (keys only, withheld
   frames only)?** Recommendation: dropped; the withholding stays.
3. **The movement drill slice: which?** (a) item runs and jump runs on the duel maps as before (exists, ten per cent),
   (b) the courses on the test map (exists), (c) both, (d) something new (say what). Recommendation: (a), ten per cent,
   on all ten maps; (b) does not transfer to the maps.
4. **Weapon drills: gone entirely, or a small share?** Recommendation: gone; a whole game has every fight in it.
5. **Spawn starts as separate ten-second rounds, or the opening lesson inside whole games only?** Every respawn in a
   whole game already gets the opening label (the build's rollout: 100% of lives). A separate ten-second round adds
   reps of that moment but its value is cut at ten seconds. Recommendation: the label inside whole games and mid-game
   starts; spawn starts as a kind only if the reps are wanted, and then 30 to 60 seconds long, not ten.
6. **Where the avoid rule leaves no opening: silent label (`OPEN_SILENT=1`) or the normal rule?** Recommendation: silent.
7. **Mid-game starts in a process's first ten minutes:** accept that there are none (the bank fills as games run), or
   build a bank saved to disk and loaded at the start? Recommendation: accept for the test run; build the file if the
   run goes ahead.
8. **Styles.** Three lives in four are styled and the style's weapon decides his opening from any spawn, which the
   measurement found to be his largest difference from the pros. Lower `STYLE_P` (0.75 to 0.25), or let the opening
   override the style for the first ten seconds? Recommendation: the opening overrides for ten seconds; `STYLE_P`
   unchanged this run (one change at a time).
9. **The win-chance pay (`WIN_PAY`) in whole games: on or off?** Never run. Recommendation: off this run; its own test
   run later.
10. **Order of the parts to bring back, after the round mix and the openings:** guessing game (reduced), gate opening,
    item rule's silence, in that order? Recommendation: gate opening and the rule's silence in the first run (they are
    small, tested harmless alone, and the 20-update pretest covers them together); the guessing game by 1.
11. **The PC tonight.** Test runs P, E, Q end about 23:15. Apply the build, run the identity checks, and start the
    20-update pretest of the next run's exact setting overnight (ends about 02:00), results in the morning? Or stop at
    23:15 and run the pretest tomorrow on his word? Recommendation: overnight, test runs only; no real run starts
    without his word.
12. **Early stopping rule for the real run:** two checks under 45% against the control stops it (as now), or a trend
    rule (three checks falling in a row)? Recommendation: both.

## 6. Order of work

1. Tonight: P, E, Q (running). 2. 23:15: the build into the repo, identity and group checks, the training-reading fix
(F3), the `place` and window fixes (F4, F5) if the guessing game stays. 3. The pretest of the next run's exact setting,
20 updates, the check. 4. The run's one page for his go. 5. The run.

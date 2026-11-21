# 2.2a: the pilot (the outlook, the tracker, the map sense, trial trips: wired and measured)

**Status (2026-11-16 evening): the design agreed with the owner in the chat; the build is running (an Opus 5.5 subagent, branch `b21f`);
the owner reviews it when it is done. Not started; no go yet.** The suite's framework: [../DESIGN.md](../DESIGN.md).

## The owner's page

| | |
|---|---|
| Started from | **2.1d's end** (`duel_gru_2_1d/keep/policy_end_21d.pt` + `opt_end_21d.pt`, update 158: the lock out, the pull 2.0). Every new part is added at zero: he plays exactly as 2.1d's end at the start |
| What it is for | The pilot of 2.2. It brings in the part that values a play before he chooses it, and proves on today's 17 targets everything 2.2b needs to add attack plays. **A gain in games is not its purpose** (my odds of one: 20 to 25%) |
| What plays | Until the owner's mark: only **trial trips** (3% of his new goals). After the mark: the outlook's term on his goal scores |
| What does not change | His 17 targets, the pay (the head's whole pay, `--head2-pay all`), the pull, the held draw, the hands, the brain |
| Length | **one run, to 23:59 on Tuesday 11-17** (owner, 11-16: "start when it's ready and run until it's done"; "one run is what I'd prefer"; "I have no strong feelings at all when it should end, set the end time to 11:59pm on tuesday"). The three stages (about 140 updates) fit well inside it; the hold runs on to the end |
| Control | 2.1d's end in the league and in every check; every fourth check against 2.0e's end |

## The three jobs (owner, 11-16: no new memory; "neither needs to be a GRU")

| Job | What it is | Reads | Says | Learns from |
|---|---|---|---|---|
| **The chooser** | the head as it is | as now | his goal | his pay, as now |
| **The outlook** | plain layers on the head | the head's state; each play's own numbers; the map sense; the tracker | what committing to each play is worth: the pay until he lets go of it + the head's value of where that leaves him. Beside it, facts: he dies, I die, I take it, both stacks after | his own held trips, every reading; its own optimizer |
| **The tracker** | plain readouts on the brain | the brain's state; his own stack, timers, score, clock; what he dealt and saw | in control (four); a fight now: he dies first, I die first; I die / he dies within 5 and 10 s; contact within 2 and 5 s; **the enemy's stack as a range** (health and armor: low, middle, high) | what happened (the simulator's truth); its own optimizer |

**The split of hands and head (owner, 11-16):** by timescale, not by "the enemy in view". The hands own everything reactive, in view or
not (a pre-fire at a corner he just left). The head owns the planned shot at a place and a time.

**A fight's inputs, explicit (owner, 11-16)**, in his order of what decides a fight: (1) the stacks: his own exact, the enemy's as the
tracker's range; (2) the relative positions: the map sense for his place against where he believes the enemy; (3) the weapons, his and
the enemy's as the brain believes them. The damage he dealt and the pickups he saw are the evidence the tracker's range is made from.
These reach **the outlook first**; the chooser's own inputs are not widened until the outlook shows what they add (2.0b).

## What is in the run

| Part | State before the build | In this run |
|---|---|---|
| The outlook with 17 fixed outputs | built on `b21f` | silent; the yardstick |
| **The outlook that scores a play's description** | new | silent to the mark. The form that carries to 2.2b: a new play is valued from what it shares with plays he already makes. Three learn side by side (all inputs; without the map sense; without the tracker), so each group's worth is measured |
| The fact outputs | new | silent readouts |
| The tracker | in control exists; fight odds built in 1.7b, off; the rest new | silent; every output's skill reported |
| The map sense's lesson | exists; not in 2.1d's command | on again; its numbers go into the outlook only |
| The judge that sees items (`JUDGE_ITEMS`, built for 1.9a) | fitted on 1.9a's games | refitted on 2.1d's games; a silent second value of the head under the win-chance pay, and the outlook's labels under it: the evidence for the head's pay, decided before 2.2b |
| Trial trips | built, off | **0 → 3% of his new goals over updates 0 to 10**, on the 17 targets: a goal drawn evenly, not by his scores, so the outlook learns what the others are worth. They teach the outlook and are left out of the lesson of his own choice |
| The attack readouts | new | his time on the enemy target, and the outlook's value of it, by stack edge: does he already attack when he is ahead |

## The stages (my estimates; an update took about 5.3 minutes in 2.1d and will take somewhat more here)

| Stage | Updates | About | What is live | What the owner gets at its end |
|---|---|---|---|---|
| 1. Silent | 1 to 60 | 5.5 to 6.5 h | trial trips only | **the report for the mark**: each outlook's skill against the goal-blind yardstick (decisions and stays apart); what the map sense and the tracker each add; how far apart the 17 outlooks are; the share of his choices the term would change at 0.5, 1, 2, 4, 8; every tracker output's skill; the range of the enemy's stack against the old rule's estimate; the two pays side by side; the attack readouts |
| 2. Opens | 40 updates after the mark | 3.5 to 4.5 h | the outlook's dial 0 → the mark | he fights (frags and damage a minute); two checks against 2.1d's end; his changes of mind for no reason |
| 3. Hold | 40 updates | 3.5 to 4.5 h | open | two checks; then the end checks and 200 games with the outlook at 0 (about 40 minutes) |

- **Why 60 silent updates, not 30**: 2.1e's forecasters needed about 40 updates to level off, and the description outlook and the
  enemy's-stack range start from nothing with new inputs.
- **One run, and stage 2 starts by itself** (owner, 11-16 night: "the timing will probably be such that stage 2 starts in the middle
  of the night, so let's just give it a mechanism for starting on its own"). At update 60 the ramp decides once, by the rule below;
  its numbers are in `auto_mark.json` (the owner's to change); a mark written by hand (`watch/out_mark.json`) always wins, at any time.

| The rule at update 60 | Default | Why |
|---|---|---|
| **The gate**: an outlook may play only if its skill on trips it has not learnt from is above the goal-blind yardstick, on average over the last 10 updates, at decisions and at stays, and at decisions in at least 8 of those 10 updates | 10 updates; 8 of 10 | no number to tune on the skill's size: only "knowing the goal helps, steadily". If neither outlook passes, the dial stays shut, a MAJOR line says so, and the silent parts go on |
| **Which outlook**: the one that scores a description, unless the 17-output one is clearly better (the description's gain under 0.9 of it) | 0.9 | a near tie goes to the form 2.2b needs |
| **The label**: `seg` | fixed | no automatic choice among labels |
| **The strength**: the largest of 0.5, 1, 2, 4, 8 at which the term would change at most a tenth of his choices | 10% | a first opening that is clearly felt and far from taking his choice over (the pull at its present strength removes about 40% of his mid-trip changes) |
| **The opening**: 0 → that strength over 40 updates, then held. It never holds or steps back by itself; every check is reported, one under 40% flagged at once | 40 | as every ramp |
- If the silent report shows no skill above the yardstick, stages 2 and 3 are not run and that is the finding.
- Checks every 20 updates, 200 games. Every check reported; one under 40% flagged at once. The ramp never holds or steps back.

## Red team

| Hand-built or assumed | Its weakness, and the guard |
|---|---|
| "His trips are enough to learn what a play is worth" | the claim the suite rests on; 2.1a and 2.1b failed on noise. Readings in one trip share one outcome, so the true count is trips. Stage 1 measures it before anything plays |
| On the 17 targets the outlook mostly repeats what he already learns | so a pass says little about new plays and a miss is not final. The description outlook matching the 17-output one is the result that matters for 2.2b |
| The trial share, 3% | hand-set. Too small: the outlook knows only his favourites; too large: a part playing before it has learnt (1.9a). Live; the checks at updates 20 and 40 are read for its cost |
| The description of a play | chosen by us from the numbers that exist; recorded by the build. The three side-by-side outlooks show what each group adds |
| The map sense | its start came from a fit on the pros' games (a game fact: what a place is worth; rule 12 allows it) and his games correct it; on item targets it may add nothing (my odds 35%), its worth is expected on attack rows |
| The tracker reads the brain's state only | the state may not hold what an output needs (his stack is the likeliest). Then that fact becomes a lesson of the brain, a later step; the old rule's estimate is the yardstick |
| The items' judge | its item part moved about six times as much, frame to frame, as the judge itself in 1.9a's test: a noisy stream. Silent here; its value's skill is the reading |
| The outlook's term moves with his fast thinking | it could make him change his mind for no reason: "no news and back" is the guard as the dial opens |
| Four learned parts sum into his goal (hands, head, pull, outlook) | rule 11 on each, sizes flagged over 40, the proof extended |
| The automatic mark | its gate and its "a tenth of his choices" are hand-set, and nobody reads the silent report before it opens. Guards: the gate asks only for steady skill above the yardstick; the opening is slow (40 updates) with a check at its middle and end; the owner's hand-written mark overrides at any time; the save at update 60 is kept with its optimizer as the place to go back to |
| More learners and stored data in the trainer | the first two updates at full size are the trial (memory, the card) |

Ledger pathology checks (negative frags, sign flips, lopsided games) at the first updates, as every card.

## Research check (rule 14)

1. **The game**: no mechanic and no simulator value is touched. The enemy's stack uses the game's armor rule as the notes give it (README core 2).
2. **What wins**: principle 2 ("the stack decides most fights before they start"; order of needs: position, then weapon, then aim): the fight's inputs in that order. Principle 5 (estimate his stack from what he took and what you dealt): the tracker's range. Principle 6 (value a life by what follows): the outlook's label. Works against none.
3. **The player's view**: the tracker reads the brain's state and what he dealt, saw and heard; the truth is only its label. The range widens when he has heard nothing, as a player's does.
4. **In and out of control**: everything is silent but trial trips, which fall on both alike. Once the dial opens: an outlook learnt mostly in control may misjudge out of control; its skill is reported for both.
5. **Self-play equilibrium**: no pay changes; the equilibrium is 2.1d's until the dial opens. Then both copies choose goals by learnt consequences; an outlook that flatters one item would show as camping (the pickups' spread over the items is read).
6. **Bot precedent**: BOTS.md idea 1 (predict each order's outcome, open on a readiness mark; its risks are rows of the red team), idea 3 (new information as a readout first, not as inputs to the deciders: the tracker and the map sense enter through the outlook), idea 7 (probes as a readiness measure). The outlook's label is the standard value of a temporally extended action.
7. **Rule 12**: no pro outcome is a target. The map sense's start is a measured fact of places; nothing is pulled toward the pros.

## My odds (rule 15)

| | |
|---|---|
| The 17-output outlook shows skill above the yardstick | 60% |
| The description outlook matches it on the 17 targets | 70% |
| The map sense adds skill on today's targets | 35% |
| The tracker's range of the enemy's stack beats the old rule's estimate | 65% |
| Opened, a gain against 2.1d's end | 20 to 25% |
| The pilot leaves 2.2b with proven parts (the description outlook and trial trips both work) | 55% |

## Built and tested

Branch `b21f` (an Opus 5.5 subagent; commits `f94f230`, `def13dc`, `8b6192b`, `0e96864`, `7eba119`, the fix round `e5a3572`, the pass
odds `059a3f0`). Read against this card by a second Opus agent (the review found one blocker, fixed) and again after the fix round.

**Added after the first card (owner, 11-16): the odds he passes each place.** A tracker output: for each target that is a place, the
chance the enemy is at it within 1, 2 and 4 s (1.7's rule for "passes": within 192 units across, 128 up or down). One scorer for every
place, so it carries to 2.2b's cut-off places. Silent; it also goes into each play's description. The old combat-order lesson is not
switched on. 1.7a's readout reached an error of 0.080 against 0.186 for the base rate.

| Test | Result |
|---|---|
| The start against 2.1d's end (`play22 same`, recorded real play, 2 maps x 3 settings) | 0 of 576,000 actions differ |
| The trainer, everything new on and silent, against 2.1d's command on 2.1d's end, no overlap, two updates | actions, log-probabilities, values, pay, round ends, the head's value and log p: equal to the bit; the ledger equal |
| The same with the run's overlapped rollouts | update 1 equal to the bit; update 2 differs in 45,624 of 172,032 actions, **as 2.1d's own command does against itself** (44,488): the trainer does not repeat itself under overlap, with or without the new parts. An existing trait, found here |
| Unit tests (every new label, the quantiles' coverage 0.797 against 0.8, the automatic mark's rule on made-up histories, the guards, the end save) | ALL PASSED |
| The smoke with overlap (everything on, trial 0.1, the dial at 1 for each outlook, a league network playing its own, a resume) | ALL PASSED; the pull's proof 0.000008 to 0.000027 |
| The live test | the dials play as written; out-of-range values refused before the first rollout; every file the ramp can write accepted |
| A real check game with the description outlook playing (`check22`) | 0 blank descriptions; the held term equals the trainer's within 0.000001; the same game without the simulator's switch refuses to play |
| The checks' player against the plugin's pass on the export | 0 of 800 frames differ; the trainer's torch against the readers' numpy: at most one half-precision step (0.00024) |
| A fault put into the new parts on purpose (`fault_test`) | only the faulty part goes off, with a MAJOR line; the built outlook keeps learning |
| The settings check against 2.1d's command and save; the start scripts | PASS; 0 parser errors |
| The items' judge refitted on 100 new games of 2.1d's end (119,208 rows) | **accepted**: held-out log loss −0.00108 with the items (95% −0.00185 to −0.00027) |

**The blocker the review found (fixed):** the checks' games were set up without the switch that gives the description; from the
automatic mark on, every check would have judged a player fed blank descriptions, with no error. Now the switch travels with the
save, and a reader that cannot get the description refuses to play.

**What a trial trip is in the code:** at a new draw, with the trial share's chance, a goal is drawn evenly among the map's targets
(about one in 17 is the goal he would have picked anyway) and his dice are redrawn so that it wins. From then on it is an ordinary
trip: **he can leave it mid-trip** when something else scores higher. All its frames are left out of every lesson of his own choice.

**Decisions the build took** (the design was silent): the description of a target is the simulator's 19 numbers for it, the map
sense's 10 and the three pass odds; the situation is 56 numbers (his exact stack, his weapons, the enemy's as the brain believes them,
the tracker's 18 outputs, the map sense at his own place). Every new input is measured on all ten maps (47,840 readings), a constant
column gets spread 1, and each is clipped at 10 spreads. The description outlook's yardstick is its own goal-blind row, which knows
the situation: stricter than the built outlook's. If even strength 0.5 would change more than a tenth of his choices, the automatic
mark opens lower in proportion, not under 0.1. A league seat's description uses the learner's map sense and brain readout.

**Memory and time at full size (estimates; the first two updates are the test):** about 2.2 GB more RAM at the peak, 0.3 to 0.4 GB
more on the card; 12 to 15 s more a rollout (the map sense at every reading) and 5 to 10 s more a learning step.

**Not as specified, or open:**
- **No server can play the description outlook yet**: the plugin needs the maps' tables, which the server image does not hold, and
  the image must be rebuilt. No 2.2a network with that outlook playing goes on a server before this is fixed.
- The brain's "where he will be" numbers in a target's description are dead on this line (they exist only with the combat order): for 2.2b's build.
- The pass odds' split by in control uses his own in-control readout, not the truth.
- The trainer's non-repeatability under overlap: to be traced (the candidate: the next rollout draws from the global random stream while the update learns).

## Before a go

| | |
|---|---|
| ☐ | The build's report read against this card; its diff reviewed; the owner's review |
| ☐ | The tests: the start identical to 2.1d's end; everything silent identical in the trainer; the smoke; the live test; the proof; the server's pass; the settings check against 2.1d's command |
| ☐ | The items' judge refit accepted (or the run started without it, said plainly) |
| ☐ | `b21f` merged into main (the owner's yes), the start script, the row in `docs/RUNS.md` (#58) |
| ☑ | **The owner's go (11-16 night): "Start it when everything is ready"**; one run, to 23:59 on Tuesday 11-17; stage 2 by the automatic mark. Everything above this row must be met first; anything not as specified in the build goes to him before a start |

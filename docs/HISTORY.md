# History: ideas tried, what they taught

**Every training run (when, from what, how long, the checks, the outcome) is in [RUNS.md](RUNS.md): the source of truth.** This file
holds what a table row cannot: the design ideas that were tried and did not work or were abandoned, the measurements made without
training, the incidents, and the lessons that became rules. Read it before proposing anything, so nothing is tried twice by accident.
`#n` is a row of RUNS.md. Each run's full write-up is in its folder under [runs/](runs/) (card, report, postmortem); the long form of
this file as it stood on 2026-11-11 is [archive/HISTORY_2026-11-11.md](archive/HISTORY_2026-11-11.md), older write-ups and the daily
log ([archive/RESULTS.md](archive/RESULTS.md)) are in [archive/](archive/).

## Lessons that are now rules

- **Pay**: every pay change states its self-play equilibrium; anything paid for progress is paid on a running best; red-team the
  ledger (negative frags, sign flips, lopsided games) before a go.
- **Starts**: one new thing a run, opened slowly, tied to the checks; a new lesson passes ten updates and a check first.
- **A chooser reads what its choice depends on, at the rate it chooses** (owner, 2026-11-03, from AlphaStar and the b1.2 to b1.4
  review): no slow-only part for a fast decision. The head alone lost the mega on 9 maps of 10 through a 30 s memory.
- **Hand a choice from a rule to a learner on the learner's own states** (from AlphaStar): a lesson on the frames it plays, faded,
  never copy-then-swap (b1.3a: an 87% copy won 37% alone).
- **Open a head before fading the rule it replaces** (v0.4.3: the item rule faded with nothing in its place: he sat on a weapon's place, the lightning gun's. Older notes call this "spawn camping", meaning the item's place; players' spawn points are random and cannot be camped: owner, 2026-11-17).
- **Nothing makes him play a certain way; a behaviour is brought out only by making it pay** (owner, 2026-11-18, after 2.2b's
  practice trips: "Anything which forces him to use a specific method will not work ... dictating that he play a certain way makes
  him worse. Full stop. It doesn't work with PPO, it doesn't work at all"; "the way to get behavior to emerge is make it worthwhile
  ... it's not a time problem, it's a structure and incentive problem"). He had said it before 2.2b; the planning session built
  practice trips, a dealt weapon and options shut on the clock all the same. Out for good: practice trips, dealt plays, dealt
  weapons, forced destinations, a hand-set share. The behaviours he wants to see (spam, rail angles) are not put off: their pay
  goes in the next run.
- **Changes that work together open together, at a size meant to change his behaviour** (owner, 2026-11-18, when the planning
  session proposed opening the aggression lever, the spam pay and the rail pay 20 updates apart: "they all work together. They do
  not work in isolation ... 'one thing at a time' is stupid to adhere to blindly ... they have failed every time you try to shove
  them in sequentially because there's not enough meat to bite onto without the entire picture ... these small subtle changes
  absolutely will not work"). This replaces "one new thing a run" under **Starts** above. Seen in 2.2b: the near-miss pay alone,
  small, moved nothing (blind fire under 1 frame in 2,000 all run).
- **A pass mark is shown to be reachable on the card, before the go** (owner, 2026-11-18: "fix this in the planning phase"):
  2.2b's update-60 mark (practice trips as good as his own choices; 0.84 against 1.00 all run) could not pass, as 2.2a's could not.
- **The league table** (owner, 2026-11-03): frag share and win chance gained against each league network, in every report.
- **Measure, don't guess**: the aim from the pros' measured parameters; calibrations never skipped to meet a start time.
- **The pro demos measure; they never set his behaviour** (CLAUDE.md hard rule 12, 2026-11-10).
- **Settings**: every check and calibration is diffed by script against the run's command, live settings and checkpoint.
- **Data**: never delete near `data`; nightly backups to `T:`.

## Open problems (tried, not solved)

| Problem | Seen in | What is known |
|---|---|---|
| He fights with the lightning gun almost only (about 65% in hand) | every run since 1.3b (#35) | The lightning took his hand in 1.3b and 1.4b (in view 42 → 70%). Not moved by: the head's weapon scores (#37), the dial at play time, training under the pros' table (#43), the damage pay at 0.001 or 0.002 (#44, #46). Owner, 11-08: the cause is the incentive (damage paid too much; he does not value his life or position), not the weapon choice |
| He does not own the rail | b1.1 to b1.2a (#27-28) on | Rail owned 26 → 1% when the head learnt in the lightning equilibrium that it is worthless; rail pay nudges dropped (owner, 10-21: rail use belongs to strategy, holding an angle). Campgrounds 0% in every run since |
| The keep choice drifts into flicker | 1.7a, 1.7b (#40-41) | It wins games (63% at 1.7a u90) but quiet re-decisions rise on their own (0.03 → 0.125 a reading out of contact; trips 25 → 81 a player-minute). Hold it before adding anything on top |
| The strategy layer | 2.1 (designed, not built) | [runs/2.1/DESIGN.md](runs/2.1/DESIGN.md), [RUNDOWN.md](runs/2.1/RUNDOWN.md) |

## Ideas tried and dropped (newest first)

| Idea | Tried in | What happened | Why dropped / lesson |
|---|---|---|---|
| **Four fight options (go at him, cut him off, hold an angle, back off) scored by a fight network in one list beside the items, taught by practice trips** (dealt at random moments with a dealt weapon, half picked by the fight network itself; from update 60 the options in his list at a hand-set share while "the enemy" and the standing places were shut on the clock) | 2.2b (#60) | Level with the start for 60 updates, then worse: 86-114 against 2.1d's end at update 70, 59-101 against the start at update 90. Every option was worth less than his own choice at every update (go at him about −0.2, an angle −0.17, cut-off −0.1, back off −0.07), so the ranking learnt was "which disturbs him least": back off 11% of his decisions, cut-off 8% (the enemy passed the spot on 5% of trips), go at him 0.2%, an angle 0.1%; his own hunt 3.2 → 0.4%. The update-60 mark (practice as good as his own choices) could not pass. The pay split, the judge with items and the near-miss pay cost nothing and showed no gain; the near-miss pay alone moved nothing | **Forcing a play on him teaches that the play is bad** (owner: "Anything which forces him to use a specific method will not work"). A fight chosen at a random moment is a bad fight by the game's own rule. The fight decision is one question (is this fight worth taking now), not a pick among named plays. 2.2c: the fight network as one number on "the enemy"; pays on what he already does. [postmortem](runs/2.2/2.2b/POSTMORTEM.md) |
| **Switching a part's choice lesson off for a warm-up while the rest of it keeps training** (2.2b's first start: the item picker's choice lesson off for updates 1 to 10, its forecast learning the new pay through its shared memory) | 2.2b (#59) | Nothing held its outputs: its memory moved under the forecast's loss, its push on his weapon grew 3.1 → 5.5 with its weapon weights barely changed (the drift was in its memory), his weapon choice moved 4 to 23 times its normal speed (KL 0.06 to 0.35 at updates 5 to 10) and from update 8 he held the gauntlet, a third of the time from update 12; the update-10 check 0-200. The build's 4-update trial ended before the drift began (and read the fast weapon choice of a cold optimizer as the optimizer's) | **A part whose choice is not taught must be frozen whole (but for the layer that is learning), not left to drift under another loss. A trial must run past the point where a warm-up or a window ends.** Restart (#60): the item picker frozen but for its forecast's last layer through update 10, proven every update; its weapon push out over the same updates; alarms on the gauntlet and the weapon choice's speed |
| **A slow half of the head: a recurrent memory of its own beside the head (three, ticking at 1, 2 and 4 s, at a trip's end and at a change of mind), taught the fast plan's lesson (forecast his own goals 2 and 5 s ahead), its odds taking over the pull's source** (2.1e) | 2.1e (#57) | Silent to update 20, then the source moved to it. Its forecast reached the fast plan's and no better (0.67 against 0.67 at update 50); his changes of mind unchanged (no news and back within 2 s: 7% → 8%); checks level (51.5%, 52.5%). Stopped by the owner at update 50; the read-back not run | **A second forecaster of the same thing from the same inputs can only match the first: a new part needs a job the old one does not do.** Also: a count of re-decisions (trips, interrupts) is never a measure; ask whether he re-decides on noise or on a real signal (owner, 11-15 and 11-16). Next: an outlook per goal (2.1f) |
| **A stay value learned from forks: the same moment played twice (his held target vs a new draw from his own scores), the difference over 8 s (30 s in quiet) as its label; the keep choice taught toward its sign** (2.1b step A) | 2.1b (#53, #54) | 35 updates, about 8,000 forks (about 180 fights, 60 quiet, 1 arrival an update): the stay value's held-out sign 0.44-0.54 and its correlation about 0 from update 2 to 35; never above chance. The labels' size about 1.3-1.5 against a mean about 0.05; two branches drawing the SAME target differed by up to 1.09; 61-67% of the forks drew the held target (no signal). Nothing new played: the check at u10 49.5% vs 2.0e's end. The first start crashed at u10 (an anchor without the quiet layer, `ce70fc3`) | Stopped by the owner at u35, 11-15 10:49: "it's a failure". A label of two short futures from one fork is mostly the game's own chance: a single fork's difference is noise many times the effect. Before building on fork labels again, measure offline on logged forks that a signal exists (`stay_forks.jsonl` of `duel_gru_2_1b`); untried: the same dice in both branches, the draw without the held target |
| **The head in charge of every seat, its choice learning only from its played seats, its share opened by the clock** (1.9a, 2.1's instruction in small form) | 1.9a (#49) | The value and readouts learned silently, but the choice did not: it took his seats near uniform (entropy 3.29 -> 2.54 in 80 updates), re-chose every 0.2 s (4.8 changes a second), the bound weapon changed up to 107 times a minute; 51% at a quarter share (u30), 41.5% (u50), 15.5% vs 1.7a u90 (u70), 2.5% vs 1.8a end (u90). The items' race was 2-3x the judge's own part of the head's pay. The ramp's flag thread crashed at u16 | Learning silently must include the choosing (a lesson on shadow ticks, not a copy); a chooser's share opens on a measure the owner sets, not the clock alone; re-choosing every tick needs a learned commitment, never the lock; flag code tested on real played-seat metrics. [postmortem](runs/1.9/1.9a/POSTMORTEM.md) |
| **Space: per-target threat inputs against his belief, and a pay for the edge** ([design/SPACE.md](design/SPACE.md)) | 2.0b (#45) | 59 inputs moving with his belief every frame, fed to the head and the keep choice, made his target unstable (quiet re-decisions 0.05 → 0.11); he gave away the big items (megas 980 against 1713); fell to 27%. The edge pay never registered (0.2% of the pay's size). The brain's readout of the map's threat did learn (skill 0.66 → 0.77) | A place has no price in a game where nobody holds an angle: the punisher first (a holder seat in the league), a pay after. Proposal: [postmortem](runs/2.0/2.0b/POSTMORTEM.md) |
| **Damage pay down to a floor** (0.001 with the judge's weight up; 0.002 with AIM3) | 2.0a (#44), 2.0c (#46) | 2.0a: 40-46% against its start, the lightning unchanged; 2.0c: 35.5 / 39.5% at u50 / u90 | Lowering the damage pay alone does not change the weapon; it costs games. Owner (11-11): keep AIM3, do not drop the damage pay further |
| **Training under the pros' weapon table** (the table picks the weapon, the key copies it) | 1.7c (#42-43) | No gain in 60 updates against the same-table copy; the rail owned unchanged. Its false start (#42) was a trainer bug (PPO's reference pass lacked the key's mask) that looked like a slow collapse | Setting him to a pro outcome table is a metric made a goal (hard rule 12). When a check falls, check the trainer's own pieces (KL) before the design |
| **The weapon dial at play time** (no training, 11-07): a push on his weapon key; the table choosing (`!weapons pros`); the rail as a rule on his target | measured against 1.7a u90, 200 games each ([DIAL.md](runs/1.7/1.7c/DIAL.md)) | Push light 48.0%, strong 33.5%; the owner's draft table choosing 34.5%, the pros' table 29.0%; the rail target as a coin a frame 5.5%, a held trip 9.5%, near-and-armed 22.5% | Variety costs games against himself in proportion to the push; the weapon can be imposed exactly at play time, ownership (the rail, rocket ammunition) cannot. Kept as a play setting; `WDIAL_RAIL` off |
| **A rater of his options beside the chooser** (what committing to each goal is worth, learnt silently, then added to his scores once it beat a version not told the goal) | 2.2a (#58) | Never switched on: on his own choices, knowing the goal predicted the result no better (the gain 0.000, positive in 4 and 5 of 10 updates); at full strength it would have changed under 3% of his choices. The test was wrong: his own goal is already readable from his state, so no rater could pass it. On the 3% random goals knowing the goal did help (+0.02 to +0.05). The run trained nothing new for 90 updates and the monitor reported it as numbers | What an option is worth shows only on options he was sent on at random; a rater adds nothing on options the chooser already ranks. No stage hangs on an unproven test. The owner: no more judges of his options. 2.2b: the hands practise the fight options first; a fight network scores them beside the item picker |
| **The combat order** (a kind, a pointer over map candidates, a way; chase, cut off, spam, break off) | 1.7a (#40), 1.7b (#41) | Learnt away in 1.7a (2.1% → 0.02% of readings); never moved in 1.7b (the KL's sizing read one piece, found no orders, fell back to 1.0 and held them). The pros' fit at full rate cost games (32.0%) | An order the hands cannot carry out is judged and learnt away: AlphaStar kept a KL to the human policy through RL, not only as a start. Open one thing per round (order, pointer and fire push together could not be told apart). Hindsight labels must not read a place after a death |
| **The head's weapon scores added to the weapon key** | 1.5a (#37) | Won more (56.5% against 1.3b's end) but the weapon did not move toward the pros; switched off at u50 the result was 100-100. A prefit to the pros (1.5b) moved rockets 24 → 37% untrained; never run, the owner chose 1.6a | No proof the part wins games; weapon targets from the pros are out under rule 12 |
| **Handing the lock to a learned keep choice from 1.4b** | 1.4c (built, never run) | Not continued (owner): weapon choice first; redone as 1.7a's keep choice | |
| **The hand-written target pieces out at once** (switch cost, item rule lesson, speed pay) + PFSP matchmaking | 1.4b (#36) | 52.5-56.0% against 1.3b's end; more holding of the red armor once the rule went; scrapped by the owner at u113 | |
| **The head as a blend learning from pay alone, no anchor** | b1.4a (#34) | The head's scores ran away from the rules' choice at once (agreement 87 → 61% in eight updates) while it had almost no say; owner: "I don't trust it" | A learner opened on pay needs an anchor; b1.3 redesigned as 1.3b |
| **Copy-then-swap: the head copies his target choice, then takes over** | b1.3a (#33) | Copied 87%, but the head alone won 37.0% | Never copy-then-swap; hand over on the learner's own states |
| **The head opened on its own pay, sharing the target logits** | b1.2a (#28) | Head and hands fought over the same logits (lightning +265 / −257); crashed at u82, unusable | The origin of hard rule 11: a sum of two learned outputs is regularized |
| **L2 in the loss to hold the summed parts** | 1.3b dry runs | Through his shared memory it broke him (a step of 31 nats); on the rows alone it still shrank them under Adam | Decoupled weight decay after `opt.step()` held them (`H2_L2`) |
| **The target lock faded to 1 s with no head** | b1.1a (#27) | Trips 12.6 → 20.0, targets reached 40 → 21%, frags down; b1.1 kept as the save before the fade | Freedom without a head to use it becomes flicker. A kept save must keep its optimizer (b1.1's was lost) |
| **Pay by win chance only** (every other pay faded out) | v0.5.1 (#17), v0.6.1 line (#20-25) | v0.5.1 fell 47 → 37%, passive; v0.6.1 held level but did not lift in 190 updates, slower (frags 1.65 → 1.42), the rail out of his hands; v0.6.1b-e drifted (43%), fades together could not be told apart, a dial's real pay was not what was intended (`WIN_W` 0.8 kept 20% of combat) | Replaced by b1: win chance **added** on top of the pay table (#26, a success). Check against fixed networks, not the league alone; check what a dial setting really pays before running it |
| **A hand-built win table / stack term** | v0.6.1's first plan, v0.5.1 | The stack term could pay a frag negative late with a lead; the table made a leader's frag worth little and protected leads | Replaced by the fitted judge with the owner's axioms in its structure (`sim/win_judge.py`); red-team every hand-built part of a pay |
| **Aim tuned by feel and self-play** | v0.5.0 (#16) | Never beat its start | Measure the pros' parameters instead (aim2, then AIM3) |
| **Fading the item rule before a head existed** | v0.4.3, v0.4.4 (#14-15) | Camping on a weapon's place (he sat on the lightning gun; not players' spawn points, which are random): a weapon target became a free "hold here" | Open a head before fading the rule it replaces |
| **The hand-built enemy belief** (v0.2's rule belief) | v0.2 to v0.4.0 | A failed baseline (owner); retired once the learned brain passed it everywhere (v0.4.0) | The enemy picture and the hands need separate memories |
| **The knowledge pay** (paid for tracking the enemy) | v0.3.11 (built) | Superseded by the brain | |
| **Pay for watching the right spot before a sighting** | v0.3.10 | Won (46-0-34) but barely built the habit | |
| **Drift inputs** | v0.3.8 | No effect; off again | |
| **Rail pay nudges** | v0.3.x | Owner, 10-21: no more; rail use belongs to strategy (holding an angle) | |
| **Fading the legs switch** | v0.3.2-v0.3.5 | He learned round it; removing the output worked | Don't fade a switch the policy can route around: remove it |
| **The judge that sees the truth** (`--priv-value`), **the slow memory** (`--slow-mem`) | v0.3, v0.2.2 | No help; left out | |
| **The lesson grading his keys against the movement network** (`--legs-teach`) | v0.2.1 | Normal inside the league, 36% then 25% in the checks within 20 updates; four-update dry runs saw nothing | A new lesson passes ten updates and a check against the control first |
| **The enemy as a target by a narrow rule** | v0.2 (level check) | Level in 48 games, 45.9% in 128: left out | A fitted start passes a full level check, not a probe |
| **Teachers**: the weapon teacher, the movement teacher with free hands, the item rule naming unreachable items | v13-v15 | The weapon teacher kept to a run's end made him hold the style's weapon; the free-handed movement teacher (17 key changes a second against his 8) cost a map in an hour; the item rule with the pros' ways sent him over Aerowalk's circle jump (lost the map 12-88%) | A teacher must have the pupil's hands and name only what he can reach; teachers are being retired |
| **Imitating the pros' mouse or trigger** | before v0.2 | Destroys aim at full weight | Movement heads only (and now: measuring only, rule 12) |
| **The yard** (`arena1`), free-for-all as the main mode, the legs as a separate network | before v0.2 to v0.3 | Dropped for the ten duel maps, duel only (10-16, 10-23), one movement network | |

## Incidents and side work (not training)

| Date | What | Lesson |
|---|---|---|
| 2026-11-13 | **The small kicks measured and fixed** (weaponlab set 6, `data/weaponlab6`; [research/MECHANICS.md](research/MECHANICS.md) 7.1): a lightning tick pushes 50 u/s, a bullet 25, a heavy bullet 40, a pellet 25 (the cvars' 1.75 / 1 / 1 / 1), with no no-friction time; the simulator had 1.167 / 0.4 / 0.625 / 0.85 and 50 ms without friction. Fixed behind `KNOCK_QL=1` (`qsim_knockback_t`; off = bit-identical) | The old factors were fitted to the speed left after the hit frame's ground friction: measure a kick in the air, where nothing else acts on it. Then (set 7, open air): an instant hit moves its target in the hit frame, a rocket's a frame later; fixed behind `KNOCK_NOW=1`; both on, the simulator follows the game within 2.7 units over 14 frames. Set 6's lifted targets at 300 units had sat inside the map (check a lab spot in the simulator first) |
| 2026-11-13 | **The lightning, real games against the simulator** ([design/LG_REAL_VS_SIM.md](design/LG_REAL_VS_SIM.md)): 1.6a in 58 sessions against people and in 40 simulator games against itself. His own hit rate 33.8% real against 37.5% simulated, close at every distance; people hit him 43% at 200-600 units against his 29-39%; against the owner he lands 27% and 99 damage a minute (simulator about 250) | The simulator's lightning is not the gap: the opponent is. His copies are as easy to track as he is, so self-play overvalues the lightning against a person who dodges |
| 2026-11-11 | **The input audit** before 1.8 ([runs/1.8/1.8a/INPUT_AUDIT.md](runs/1.8/1.8a/INPUT_AUDIT.md)): 38,421 rows of his real inputs from two full-size updates on b1.2d's weights. Of 1,053 columns 239 never change in play, 76 are multiplied by zero in the hands (v0.4.2's fade; the brain reads them), and of the 814 live ones 291 arrive under 30% of their intended size (every input since v0.2 was appended as "mean 0, spread 1" and the statistics are frozen); the places, holds, small items and rocket aim (292 columns) carry about 1% of the hands' signal; the zoom's columns sit at the clip in 35 to 64% of rows | An input proved harmless at its start was never proved used. Inputs go by role (the brain: the truth; the head: strategy; the hands: carrying it out): reroute, fade in the old reader, remove. The clean-up comes before the redo ([design/INPUTS_CLEANUP.md](design/INPUTS_CLEANUP.md)); kept on the owner's word though unused today: the ways, the heavy machine gun, the gauntlet, the grenade arc |
| 2026-11-11 | **Where the lightning took his hand** (the 1.n runs' own records, the weapon in hand in training games at each run's end, rockets / rail / lightning): v0.6.0 16 / 22 / 45%, b1.0a 19 / 15 / 45%, b1.2d 37 / 5 / 38%, 1.3b 26 / 2 / 56%, 1.7a's update 90 19 / 1 / 67%. The rail went from b1.0a to b1.2c, before any head; the lightning rose inside 1.3b in step with the head's credit (40% at its update 10, 53% at 50) | The redo starts from b1.2d's end with AIM3 in the hands first ([runs/1.8/README.md](runs/1.8/README.md)). If the lightning climbs with the credit again, the aim was not the cause |
| 2026-11-11 | The trainer's own update number starts at 1 again after a restart (found by 1.8a's smoke test): a ramp that reads it would freeze its dials | A ramp's clock is the number of lines in `metrics.jsonl`, as the watcher counts |
| 2026-10-30 | Leaderboard by games won and lost, not frags (owner); a page per player and for Bobby (B-290) | A quit is the quitter's loss if behind after 5 minutes |
| 2026-10-29/30 | Servers' frame budget: inputs, network and hearing check made faster, bit-identical; 15.5 → 13.6 ms median; servers on 1 vCPU | Measure on the server; background jobs on one core need `chrt -i 0`. [guides/FRAME_BUDGET.md](guides/FRAME_BUDGET.md) |
| 2026-10-28 | The viewmodel fix (`EARLY_BOBBY`) rolled back on the public servers: Bobby invisible to a tester | The wrong player model is a known Quake Live bug: live with it |
| 2026-10-28 | **Data loss**: a cleanup deleted the whole data folder through links. Recovered v0.4.2b's end, its league, the server keys; lost every v0.6.0 save, the people's brain pack; 9 recovered league networks were corrupt | CLAUDE.md hard rule 1; load every recovered file before using it |
| 2026-10-11 | The checks' noise: the same network against itself 48.8% over 160 games, single maps 41-56% | Read a single map's number with ±10 points |

## Before v0.2 (v0.1 = v15c and older)

The yard (`arena1`), movement teachers, the legs as a separate network, the first public server. Full notes in the git history and
[archive/](archive/). Lessons that still hold are in CLAUDE.md's gotchas.

## The standing rules: where each came from (moved out of CLAUDE.md on 2026-11-17)

CLAUDE.md now holds each rule in a sentence or two. Its words, date and incident are here, as they stood in CLAUDE.md that day.

### The hard rules


1. **Never delete anything outside git's tracked files.** No `rm -rf`, `Remove-Item -Recurse`, `rmdir /s`, or
   `git worktree remove --force` on any folder. On 2026-10-28 a cleanup did that near links into `data/` and wiped the whole
   data folder (every run's checkpoints). A link (junction) is removed only with `cmd /c rmdir "<link>"` (no `/s`) after checking
   with `(Get-Item <path>).LinkType`, and the target is checked after. Any delete of data needs the owner's word for that exact
   delete and a backup first (`python tools/run/backup.py`). `tools/hooks/no_delete.py` (a hook in `.claude/settings.json`) asks
   him before any delete command runs.
2. **Do only what the owner asks.** A question is not a go. Ask before starting runs, servers, agents, or anything that
   changes something outside this session; before renaming or restarting fresh. Public servers only on his word.
   **Exception: a run he approved that crashes is fixed and restarted without asking** (owner, 2026-11-15: "Obviously this
   was meant to run overnight"; 2.1b sat dead 10 hours waiting for a go). Find the cause, fix it in the code, test the fix
   (a scratch smoke that exercises the failing path), move the dead folder aside (`<run>_crashN`, nothing deleted) or resume
   from the last save, restart with the same settings and the remaining length, add the crash and the restart to `RUNS.md`,
   and report it at once. A fix that changes the design, the pay or the settings still goes to him first.
3. **Settings check before every run, check and calibration, and before using its numbers:**
   `python tools/run/check_settings.py <train.cmd> --ref <reference.cmd>` (and `--ck <checkpoint>` for a run's own saves).
   Any difference not deliberately allowed = the data is not used. Never build a run tool from an older copy.
4. **Correctness over speed.** Never skip or approximate a calibration to meet a start time; say what is missing and when.
5. **Red-team before a go.** Every run card lists each hand-built or assumed part of the pay and design, its measured
   alternative, and the ledger's pathology check (negative frags, sign flips, lopsided games). Volunteer weaknesses unasked.
6. **Never stop a run** unless the owner says so. **Ramps never hold or step back on their own** (owner, 2026-11-04: "All you do
   is report, not hold. You report with urgency when things look bad and we decide together"). Every check's win rate is
   reported; one **under 40%** is flagged in the chat at once as a major problem. He decides hold or stop.
7. **No personal data** in the repo (Steam IDs, IPs, usernames, passwords); public-server details stay in `private/`.
8. **Git**: explicit `git add <files>`; never rebase; commits end with the Co-Authored-By line; push `main` at most 1-2
   times a day; one working tree (the repo) plus at most one worktree per active run, made without links into `data/`.
9. **The running run gets full priority** (owner, 2026-11-04: "The run that is going gets full priority. Period."). No side job
   (a smoke run, a dry run, a level check, a measurement, a server) is started on my own while a run trains: it goes to him first,
   naming its cores (by mask), its length, and what it shares with the run (the graphics card, the trainer's cores, the watcher's
   check cores). To stop a job's processes, match each one's own command line: Windows reuses process IDs.
10. **Build the approved design, never a simplified one** (owner, 2026-11-05: "I approve the design and that's what you build. You
   do not manage time, I manage that."). Every part of an approved design is built; an unspecified detail is decided from the
   design's intent and recorded; a real structural fork goes to him. No start times, schedules or time estimates drive what is
   built: when it is ready (built and tested), he decides.
11. **A decision made from the sum of two learned outputs is always regularized** (owner, 2026-11-05: "That sum just seems like a
   prime spot ... to get some opposite sign blowup"). Where a choice's logits are the hands' rows plus a head's scores (the target
   since 1.3b, the weapon key since 1.5a, the fire key and the order's pointer since 1.7), both parts get the decay (`H2_L2`: the
   decoupled weight decay in `sim/train_duel_rnn.py` after `opt.step()`) from the moment the sum is live, and each part's size
   is recorded and flagged over 40 by the run's ramp. A new sum is not built without both.
12. **The pro demos are for measuring things, never for setting Bobby's behaviour** (owner, 2026-11-10: "it's mistreating a
   metric as a goal"). What may be taken from them: measurable facts of the game and of human limits (what a place on a map is
   worth, reaction and notice times, the sight and hand errors and how they grow). What may NOT be made a target, a pay, a lesson,
   a pull or a pass mark: any outcome of a player's choices (a hit rate by weapon, how often a weapon is held or fired, how often
   they hold, spam or contest, where they stand); every attempt to set him to one collapsed him (the weapon teacher, the pros'
   weapon table of 1.7c, the pull of the head to the pros). Such numbers may be shown beside his as a labelled readout; a
   proposal never says "bring him to the pros' X%". Aim: each parameter is set from the pros' own measured value of that
   parameter (default = the average pro, better = p90, max = all off); what hit rate comes out is not tuned. Do not suggest
   otherwise again.
13. **A new part is never trained to copy a rule we do not want to keep; it learns silently, then is blended in** (owner,
   2026-11-12: "we do not train things to copy a rule that we do not want to replicate. We let them train silently first and then
   blend them in"). No copy lesson, teacher or imitation target that points a new head, choice or network at an old rule's or an old
   network's behaviour (b1.3a's copy lesson failed; 1.9a's first start had one and was restarted without it). "Silently" = it learns
   from its own lessons (its value, its readouts, its pay on its own played choices) while it plays nothing or a small share, and its
   share or gate then opens slowly. **Once a hand-built rule is out it never comes back** (the 8-second lock: "I don't want to ever see the
   lock again").
14. **Every decision is checked against the research notes** (owner, 2026-11-13: the issues "stem from a lack of understanding about
   how the game works"). Before proposing a design, a pay change or a run card, read the relevant parts of `docs/research/`
   (MECHANICS, DUEL_STRATEGY, PRO_INTERVIEWS, BOTS) and fill a **"Research check"** section answering the seven questions of
   `docs/research/README.md`, citing file and section; "not covered" is said plainly. A change that works against a principle there,
   or rests on a simulator value that the notes show is off the real game, says so up front. When a note proves wrong, fix it.

15. **When an approach has failed more than once, change the structure, not the variant** (owner, 2026-11-15: "we've hit a
   roadblock a bit and I think partially we're getting to be somewhat circular in our approaches. So rather than just offer some minor
   tweak, I really want you to think critically about whether a plan will work and don't be afraid to tear down other parts of how
   things are organized to get there"; "Stop thinking so linearly with what has been tried before ... just changing them slightly is
   not going to be the solution"). Name the assumption every failed attempt shared and propose removing it. Say plainly, with odds,
   whether a plan will work before it is built. "That is how it already is" is never a reason to keep a design: "I have no allegiance
   to anything specific design wise. I want the bot that does the things I ask ... when you get blinders thinking that we have to
   continue to do something a particular way because that's how it already is, it makes it a slog and I get frustrated." His part is
   guidance on what seems reasonable and expertise on Quake ("I'm trying to axiomatize my understanding of quake"); his plain-words
   description of how a player thinks is a design specification, to be mapped onto the mechanism (the lock's removal: six attempts
   shared "something decides when a new draw counts"; the step forward removed the re-draw, then built his "I'm going to go get mega ...
   every 200ms I ask myself what else should I be doing" as the slow plan and its pull, 2.1c and 2.1d). Never answer a design question
   with "run a test first" in place of an idea. The other hard rules still hold.

16. **In a Fable session, an Opus 5.5 subagent does the coding** (owner, 2026-11-15: "That is a standing order ... in a fable session
   always have an opus 5.5 subagent do the coding"). Every code change (the trainer, the simulator, tools, run scripts, plugins) is
   handed to a subagent started with the Opus model, with a full brief (the files, the exact change, the tests, what must not be
   touched: a live run's files, its processes); the session itself designs, reviews the diff, runs and monitors. Docs and run records
   (cards, `RUNS.md`, this file) are written by the session.
   **Fable mode (owner, 2026-11-16: Fable "really just for thinking through plans and interacting with me, and all of the mechanical
   simple stuff is handled by an Opus 5.5 subagent"; "the context blows up so quickly and you are overkill for monitoring").** A Fable
   session thinks, criticises, designs, decides with the owner and writes the briefs and the owner's pages (cards, designs). Everything
   mechanical goes to the `opus-worker` agent (`.claude/agents/opus-worker.md`, Opus 5.5): code, builds, tests, measurements and fits,
   reading a diff or many files (it brings back only what differs from the card), git, starting an approved run from its `start.ps1`,
   the run table and docs bookkeeping. **Run monitoring is a separate Opus 5.5 session**, started with a written brief when a run
   starts; it reports to the owner directly, and the Fable session reads its reports or the run's records only to plan. The Fable
   session still answers for the result: it checks the worker's key claims (the numbers a decision rests on) before it tells the owner.

17. **Advice on a run has one default form, and its homework is done unasked** (owner, 2026-11-17, after asking four times about
   2.2a: "This needs to be the default for when I ask for advice on runs. I do not want to have to repeat myself. The point of all the
   research and metrics is that you use them"). Before answering "how did it go" or "what next": read the run's records and checks
   (did it do what it was for, and from which update did it stop doing anything new); `docs/HISTORY.md` and `docs/RUNS.md` for every
   earlier attempt at the same aim, and the code for parts already built and switched off (nothing is called missing or proposed
   without looking); the research notes for the aim. The answer, in order: **the verdict** in plain sentences, own faults named;
   **what to keep and where to cut** (the save with the best record after the run stopped doing anything new, not the end by default);
   **what every failed attempt at this aim shared** (rule 15); **the next run as a list of concrete changes**, never "measure this
   first" in place of a change and never a small variant of what failed; the risks (what is unverified among them), the odds, his
   decisions. **Plain words**: no name coined for a part of the build without saying in the same sentence what it does; numbers as
   records and plain quantities. Nothing is started or edited while advising.


### The owner's goals


- **One goal: win games** (owner, 2026-10-24). Goals are set per generation: the current one is in `docs/PLAN.md` (2.x, from
  2026-11-08: pay the stack and the control, not the damage; then the strategy layer, 2.1). Every change is stated by the
  equilibrium it leads to in self-play and the behaviour it brings out on the way.
- **Names**: N.Nx (owner, 2026-11-03): N.N is a family of runs with a goal of its own, x = a, b, c the attempts (2.0a, 2.0b);
  folders `docs/runs/2.0/2.0a/` and `data/sim_runs/duel_gru_2_0a`. What ran as b1.0a to b1.4a and v0.x keeps its name and folders.
- **Design from AlphaStar and Pluto** (owner, 2026-11-03) for anything strategic (the head, target and plan choices, memory, the
  league, the value and pay, handing a choice from rules to a learner): name which part a proposal takes from them, where it differs
  and why (one PC, our data, fairness). Pluto: [docs/archive/versions/v0.3/PLUTO.md](archive/versions/v0.3/PLUTO.md). The rules
  taken so far: [docs/HISTORY.md](HISTORY.md) (lessons that are now rules).
- **One new thing per round**, shut at the start, opened slowly with the checks reported; two new things open one after the other.
- **Genuine learned behaviour** (movement, weapon choice, item control, positioning), not hand-coded rules or knob tuning; the
  hard-wired rules and teachers are retired over time. **Fair**: human physics (125 fps), human senses (sight with line of sight,
  sound; enemy projectiles only as seen or heard), mouse-like aim with human limits. Never miss on purpose to hit a number.
- Jumps: "he should be taught the general path, there's many ways to execute them": pay and labels are for the way.
- **The control in every run**: the last best network stays in the league (`--anchor-p`) and every checked save plays it head to
  head; a network is promoted only if it beats the control. Judge checks by games won and lost; say plainly what did not work.
- **Maps**: the ten duel maps all in training (Blood Run, Aerowalk, Lost World, Sinister, Furious Heights, Battleforged, Campgrounds,
  Hektik, Toxicity, Cure); House of Decay and Dismemberment held out, never trained. No maps with doors. Test map `testlab`. Real
  games against the game's Nightmare bot: before and after a run, never in the middle; never train against the game's bots.
- No powerups anywhere, a map's **duel** items in every mode (`plugins/powerups.py`). Servers are 1v1 only (since 2026-10-23).
- Never change the owner's Quake Live client settings or configs in the Steam `Quake Live` folder (copying the test map pk3 into
  its `baseq3` is allowed).
- **The public servers**: a utility kept apart from the repo, all their details in `private/`; never move them, or an address,
  account, server name, Discord or config value, into a tracked file. A network goes on them only on the owner's call (and only
  if it beats the control); never restart one while he is on it; rcon there only when needed.
- Log as much as possible from human-played rounds. Keep everything. Render videos after a run unasked (`sim/render_course.py`).
- The owner prefers concise answers and doable batches.


### Starting and watching a run


**No dry run for small changes** (owner, 2026-11-04): "that's just the first 10 updates of the run." A dry run is only for changes
we are not sure of (a new lesson, a new part of the network, a new pay whose step is unknown). Small, identity-checked changes start
the real run directly; its first 10 updates and the extra check at update 10 are the trial.

**The run itself is the validation** (owner, 2026-11-17 evening): "the run itself functions as the validation. This is how we do all of
the runs, for efficiency ... That's the only way this is possibly doable in a reasonable amount of time with my one computer." The story:
after 2.2b's failed start (#59) the planning session three times put a trial run in front of the restart (a 12-update scratch run, then
the real run as the trial, then neither). The pre-start checks are the quick ones that need no training (the start's identity, the unit,
live and guard tests, a one-step test of a new mechanism, alarms replayed on recorded data, the settings check, the dry run); the run's
own first updates, its alarms and the trainer's own proofs in `metrics.jsonl` are the trial.

1. The owner's go on the run's `CARD.md` (both parts filled in). **Ask him the length before starting**; 12 hours (`--minutes 720`)
   if he says the default.
2. `powershell -ExecutionPolicy Bypass -File docs\runs\<family>\<run>\start.ps1`: it runs the settings check and `live_accept`,
   refuses on any difference, checks the files are there and no trainer runs, then starts the trainer, the watcher and the
   self-play logger.
3. Its row in `docs/RUNS.md` at once (see Docs).
4. Monitoring from update 1, unasked: every FLAG and MAJOR line of `watch/watch.log`, `live_status.json` applied, dials played as
   written, a stall (no new line in `metrics.jsonl` for ten minutes). One line an hour; the 06:30 report after a night. Both carry
   the league table (frag share and win chance gained against each league network; [BACKLOG B-300](BACKLOG.md)) beside the checks.
   **Every report opens with the run's state in plain words** (owner, 2026-11-17: in 2.2a the part the run was for stayed switched
   off at update 60 and this reached him as a line of numbers; eight hours of training went on with nothing new playing: "a massive
   oversight"). One or two sentences on what is actually playing now and whether the run is on its card's plan. A decision that ends,
   skips or changes a stage is reported as **its consequence** (which stages are not happening, what he now plays, what the run can
   still show, what the owner could decide), not as its numbers, and stays at the top of every report until he answers. Every
   monitoring brief (`MONITOR.md` in the run's folder; 2.2b's is the pattern) carries this, names the run's point and the update at
   which it is decided, and uses no name of a part of the build without saying what the part does.
5. Cores (from b1.2d): the trainer alone on the 8 performance cores (`0xC03C3`); watcher, checks and logger on 8 efficiency cores
   (`0x3C3C`, `CHECK_BATCH=4`); 14-17 left for the owner. Checks every 20 updates, 200 games (`CHECK_EVERY=20`, `CHECK_GAMES=20`),
   against the control; every fourth against the long-term control.



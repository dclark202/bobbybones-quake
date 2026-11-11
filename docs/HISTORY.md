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
- **Open a head before fading the rule it replaces** (v0.4.3: the item rule faded with nothing in its place, spawn camping).
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
| **Space: per-target threat inputs against his belief, and a pay for the edge** ([design/SPACE.md](design/SPACE.md)) | 2.0b (#45) | 59 inputs moving with his belief every frame, fed to the head and the keep choice, made his target unstable (quiet re-decisions 0.05 → 0.11); he gave away the big items (megas 980 against 1713); fell to 27%. The edge pay never registered (0.2% of the pay's size). The brain's readout of the map's threat did learn (skill 0.66 → 0.77) | A place has no price in a game where nobody holds an angle: the punisher first (a holder seat in the league), a pay after. Proposal: [postmortem](runs/2.0/2.0b/POSTMORTEM.md) |
| **Damage pay down to a floor** (0.001 with the judge's weight up; 0.002 with AIM3) | 2.0a (#44), 2.0c (#46) | 2.0a: 40-46% against its start, the lightning unchanged; 2.0c: 35.5 / 39.5% at u50 / u90 | Lowering the damage pay alone does not change the weapon; it costs games. Owner (11-11): keep AIM3, do not drop the damage pay further |
| **Training under the pros' weapon table** (the table picks the weapon, the key copies it) | 1.7c (#42-43) | No gain in 60 updates against the same-table copy; the rail owned unchanged. Its false start (#42) was a trainer bug (PPO's reference pass lacked the key's mask) that looked like a slow collapse | Setting him to a pro outcome table is a metric made a goal (hard rule 12). When a check falls, check the trainer's own pieces (KL) before the design |
| **The weapon dial at play time** (no training, 11-07): a push on his weapon key; the table choosing (`!weapons pros`); the rail as a rule on his target | measured against 1.7a u90, 200 games each ([DIAL.md](runs/1.7/1.7c/DIAL.md)) | Push light 48.0%, strong 33.5%; the owner's draft table choosing 34.5%, the pros' table 29.0%; the rail target as a coin a frame 5.5%, a held trip 9.5%, near-and-armed 22.5% | Variety costs games against himself in proportion to the push; the weapon can be imposed exactly at play time, ownership (the rail, rocket ammunition) cannot. Kept as a play setting; `WDIAL_RAIL` off |
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
| **Fading the item rule before a head existed** | v0.4.3, v0.4.4 (#14-15) | Spawn camping: a weapon target became a free "hold here" | Open a head before fading the rule it replaces |
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

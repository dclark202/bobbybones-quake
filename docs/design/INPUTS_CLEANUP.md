# The input clean-up: a proposal (2026-11-11)

*Owner: "I'd rather kill the dead inputs and fix the small input problem before trying 1.8 at all ... fix the inputs + tune aim3; redo
from 1.2d on; then get to 2.1"; "We've had inputs creep up slowly from 500 to now over 1000, with a huge change in model architecture ...
The inputs need to be refreshed to account for that ... to reduce latency when running the live bot ... make sure that when we add new
stuff it actually is getting used correctly." The measurements: [runs/1.8/1.8a/INPUT_AUDIT.md](../runs/1.8/1.8a/INPUT_AUDIT.md).
**A proposal for review. Nothing is built.***

**The owner's answer (11-11):** "do not cut the ways, hmg, gauntlet, grenade arc, grenades will be in soon enough. We also need to let him use
multiple ways to get to a point. Even though he's not using those weapons they are still part of the game that need to be in his networks.
I'm very skeptical about removing pre-fire and emergence, that seems like it should stay part of it. The rest of this I agree with."
**So: the ways (7), the heavy machine gun and the gauntlet (about 14), the grenade arc (6), the pre-fire (39) and the emergence (8) STAY.**
Section B is withdrawn; A loses its weapon row; the list ends near 840 columns, not 750. What that changes is under "After the owner's answer" at the end.

## What is wrong, in three lines

1. **A quarter of the list is dead**: 239 of 1,053 columns never change in play, and 76 more are multiplied by zero in the hands.
2. **A third of the rest is mis-sized**: every input since v0.2 was appended as "spread 1" whatever its real spread, and the statistics
   are frozen. 291 live columns reach him under 30% of the intended size; a few old ones sit at the ±10 clip.
3. **Nothing checks either**: a new input is proved harmless at the start (0 actions differ) and never proved used afterwards.

## The changes

### A. Cut what is exactly dead (no change in what he does)

Removed from the simulator's list, from every network's first layer, and from the attention tokens. A constant column's effect is a
fixed number: it is folded into the layer's bias (the flat encoder, the brain's input layer) or into the token's mark (attention), so the
network answers the same to the action.

| Cut | Columns | Why it is dead |
|---|---|---|
| more enemies | 24 | free-for-all only; duel is the mode (owner, 10-16) |
| movement goal | 7 | movement rounds and courses: no longer trained |
| style | 4 | `STYLE_P=0` since v0.3 |
| his legs | 2 | the legs switch was retired in v0.3.x |
| v038 drift | 4 | `DRIFT_IN=0` |
| crouched (his, the enemy's) | 2 | nobody crouches |
| walls and sight outside his field of view | 19 | always −1 by the fairness rule |
| hazards: deadly drops | 16 | none on these maps |
| enemy projectiles: slots 5 and 6, and the dead flags of 2 to 4 | 32 | never filled |
| flags that are always 1 ("exists", "slot holds a place") | about 34 | constant on all ten maps |
| b17 order, b20b space, b20b targets | 69 | never opened; 2.0b's design failed; 2.1 defines its own |

**About 213 columns.** Two attention tokens go with them ("others", "drift").

### B. WITHDRAWN (owner, 11-11: these stay): cut what is live in the simulator but no network uses

| Cut | Columns | State today | Recommendation |
|---|---|---|---|
| v036 pre-fire | 39 | zero in the hands since v0.4.2's fade; 0.3% of the brain's signal | **cut for both.** The hands get pre-fire back through 2.1's "spam" instruction, with inputs designed for it |
| v036 emergence | 8 | zero in the hands; 0.2% of the brain's signal | **cut for both** |
| b3 ways | 7 | constant today (`WAYS` off) | **cut**; the movement work brings its own when it comes |
| grenade arc | 6 | he holds grenades 0.1% of the time; 0.00% of the signal | **cut** |
| the "enemy is believed here" flags of the places | 16 | zero in the hands; part of the rule-made belief | with decision D2 |

**About 60 to 76 columns.** These are not exact: each cut is proved by 200 games against the uncut network (level = within the checks'
noise).

### C. Fix the sizes (no change in what he does at the start)

- **Re-measure every remaining input's average and spread** on today's play and rescale the first layers so he answers the same
  (`sim/renorm_policy.py`, extended to the attention tokens, the brain's input layer and the head's). After it, the places, the holds,
  the small items, the rocket aim and the yellows' timers arrive at full size, and the zoom, the jump thumb and "holding plasma" stop
  hitting the clip.
- **The optimizer's kept moments for those layers are rescaled with the weights** (or those layers' moments start fresh): otherwise the
  first updates take wrong-sized steps on exactly the inputs that were fixed. To build and test.

### D. Decide what the brain and the head read

| # | Question | Today | Options | Recommendation |
|---|---|---|---|---|
| D1 | The brain's list | the first 868 columns, by position | (a) the cleaned list, by name; (b) a list chosen for it | (a) now: same information, about 200 fewer columns; its list becomes explicit so that a new input is given to the brain on purpose, not by where it sits |
| D2 | The rule-made belief (the enemy's believed place, the stack by rule: 26 columns + the 16 flags) | the brain reads it: 11% of its input signal; the hands do not | (a) keep for the brain; (b) fade it from the brain in a run of its own; (c) cut now | **(a) for the clean-up, (b) as its own step in 2.n.** Cutting it now would change the part everything else stands on, in the same step as everything else |
| D3 | The head's own columns | 81: health, armor, weapons owned, ammunition, nearest mega and red, clock, score, last takes, his target, the order's ten | add: the weapon in his hand (9), the enemy in view (1), the yellows' timers (4); drop the order's ten | **yes, at the head's birth** in the redo, so it is never retrofitted |
| D4 | The hands read every column twice (flat, and as tokens) | both paths since v0.2 | keep both; or flat only for the small groups | keep both now; it is the one architecture question here and belongs to 2.1 |

### E. Judge the large, quiet groups after the fix, not before

| Group | Columns | Share of the hands' signal today | Note |
|---|---|---|---|
| v02 places (the eight nearest of the pros' places) | 96 → 72 after A and B | 0.4% | arrive at 16% of full size |
| b2 holds (the holding places) | 64 → 54 | 0.4% | 16% |
| b12 small items (eight places) | 112 → 105 | 0.2% | 33% |
| v036 rocket aim | 20 | 0.06% | 12% |
| v02 position, game, items | 26 | 0.1% | 22 to 28% |

Whether these are badly designed or only too small to be heard cannot be told today. **Recommendation:** fix their size, train, then
measure each by games with the group blanked (F3). What is still unused then is cut or rebuilt; the places and holds are in any case
what 2.1's map sense replaces.

### F. Rules so it does not creep back

1. **A new input comes with its measured average and spread** (a sample of real play), never "0 and 1". The converters refuse otherwise.
2. **An input health report before every run and at every check** (the audit as a tool, `tools/run/input_health.py`): constant columns,
   size outside 0.5 to 2, more than 1% of rows at the clip, each group's share of the signal at each reader. A FLAG in the watch log.
3. **A new group is proved used, not only harmless**: at a run's end, 200 games with the group blanked against the same network with it.
   No drop = it is not used = it does not stay.
4. **A budget**: the list's length is on every card; an addition names what it reads that nothing else gives.
5. **One list, by name**: each network (hands, brain, head) has its own list of names in the checkpoint; nothing reads "the first N".

### G. Latency

The network is 1.8 to 1.9 ms of a 7 ms frame on a local server; the rest is building the inputs and the game. **Not measured by group.**
The cuts that save real work are those whose inputs are traced or searched each frame: the pre-fire and emergence (47), the dead hazard
and wall rays (35), the projectile slots, the order and the map's table. **First step of the build: time the building of each group** in
the plugin, before and after.

## What comes out

| | Today | After A | After A and B |
|---|---|---|---|
| The simulator's list (b1.2d's 980 of today's 1,053) | 1,053 | about 826 | about 750 to 765 |
| Read by the hands | about 740 live | the same, all at full size | the same |
| Attention tokens | 67 | 61 | 58 |

## How it is done, in order

1. **Measure**: the plugin's time by group; the input health tool (F2) from the audit's scripts.
2. **The new list** in `sim/duel_env.py` behind one switch, today's simulator frozen as `duel_env_1053.py` for every older network
   (the servers' network keeps playing on it).
3. **The converter** (`sim/reshape_policy.py` by name, with the folding of A and the rescale of C) for b1.2d's end and the league's files.
4. **Proofs**: A and C: the converted b1.2d on the new list against the old one on the old list at fixed seeds, 0 actions differ.
   B: 200 games level. The plugin's inputs against the simulator's in a real game (`tools/input_check.py --real`).
5. **AIM3's open points** (below), on the cleaned network.
6. **The redo from b1.2d** (1.8a's card, with the new start), then 2.1.

## AIM3: what "tune" covers

| Point | State | Proposed |
|---|---|---|
| The eye's lag, gain and fixation time | read off the pros' curves by eye | a least-squares fit to those curves |
| The rocket lead | his rockets point 0.17 of a full lead behind a crossing enemy; the pros 0.02 | measure whether the lead inputs (6) and the rocket aim inputs (20, at 12% size today) carry his own delay; fix the input, not the aim |
| The slow weapons' random reload delay | unmeasured | measure against the pros' refire times |
| `better` and `max` | defined; not in `tools/aim2_levels.py` | add |

## Decisions for the owner

| # | Decision | My recommendation |
|---|---|---|
| 1 | A: cut the exactly dead columns (about 227) | yes |
| 2 | B: cut pre-fire and emergence for the brain too, the ways, the grenade arc | yes, each proved level by 200 games |
| 3 | C: re-measure and rescale, with the optimizer's moments | yes; it is the change that matters most |
| 4 | D2: the rule-made belief stays for the brain through the clean-up | yes; its own step later |
| 5 | D3: the head gets the weapon in hand, the enemy in view, the yellows' timers at its birth | yes |
| 6 | E: the places, holds and small items stay until measured at full size | yes; cutting them now would be a guess |
| 7 | The free-for-all inputs go for good | yes (duel is the mode); the group module stays for two players |
| 8 | The servers | the network on them keeps today's list (the frozen simulator); the new list goes out with the first network trained on it |
| 9 | F: the five rules, into CLAUDE.md | yes |

## Weaknesses

- The audit ranks by weights and real values, not by games with a group removed: a group that matters in rare moments could be
  under-rated. That is why E waits and B is checked by games.
- Rescaling changes how he learns from the first update on. It is the point of doing it, and it means the redo will not retrace 1.3b
  to 1.7a even with the same schedule.
- A frozen copy of the simulator is one more thing to keep working (v8, v11, v12, v13, v14, v15f, v02 and 20a exist already).
- None of this by itself gives weapon variety or strategy. It removes a reason they could not be learnt.

## After the owner's answer (11-11)

| Kept | What follows from keeping it |
|---|---|
| The heavy machine gun, the gauntlet (about 14), the ways (7) | they are constant today, so their size cannot be measured: they get **design statistics** (the range they will have when on), and the health report lists them as "kept, off" so they are not flagged. Rule F1 becomes: measured where live, by design where off, never "0 and 1" by default |
| The grenade arc (6) | live only with the launcher in hand (0.1% of his time): its statistics are measured on those frames alone (the drills hold the launcher) |
| The ways | keeping the columns does not make him use more than one way: `WAYS` is off and his way output's rows sit at 0, −20, −20 since v0.2.1 (B-301). ❓ where the ways open: a stage of the redo, or with 2.1 |
| Pre-fire (39) and emergence (8) | **today they are multiplied by zero in the hands** (v0.4.2's fade at 1.0); only the brain reads them, at 0.5% of its signal. Keeping the columns changes nothing for the hands unless the fade is lifted for these 47. The hands' old weights on them are still there (80 to 95% of an ordinary column's), from before v0.4.2, so lifting it at once would bring back three-week-old habits: it has to be a live dial opened slowly, with its own check. ❓ lift the fade for these 47 as a stage of the redo (my recommendation: after the head's credit, before the keep choice), or leave them brain-only until 2.1's "spam" |
| Latency | the pre-fire and emergence are among the inputs that cost real work each frame; with them kept the saving is smaller. Measured first, as before |

Unchanged: A's other cuts, C (the re-measure), D, E, F, the order of the work. The decisions' table: 2 is withdrawn; two new ones above.

## Final, as decided (owner, 11-11)

"The brain makes predictions for what it believes is the truth. The head decides based on that what strategy to execute. And the hands
execute the strategy. In the past, ALL inputs went to the hands because it was the only thing that existed. So we rerouted them to the brain
and then turned them off in the hands. So they can just be removed from the hands now ... they're just dead weight. This similarly applies
to the other changes." On the brain's own-key, wall and floor inputs: "those inputs for the brain are fine, they constitute the 'Truth about
the game'". On the strategy inputs in the hands: "that fade and remove makes sense. Once we get the head back in, those inputs can go from
the hands. Put that at the end of this 1.8 run." The ways: kept as columns; "giving him multiple ways is something we will work on later".

| # | Change | Exact? |
|---|---|---|
| 1 | The about 213 constant columns out of every network (A, without the heavy machine gun and the gauntlet) | yes |
| 2 | The 76 columns already rerouted to the brain out of the hands (pre-fire 39, emergence 8, the rule-made belief 8, the places' belief flags 16, the stack by rule 5); they stay in the brain's list | yes |
| 3 | The yellows' timers (4) never go to the hands: the head's only | yes (the hands' weights on them are zero) |
| 4 | Every remaining input re-measured and the first layers rescaled, the optimizer's moments with them; the kept-but-off inputs (the ways, the heavy machine gun, the gauntlet) by design, the grenade arc on the frames he holds the launcher | yes at the start |
| 5 | Each network reads its own list by name: the brain its senses (unchanged in content, its constants out); the head the belief and the game's state; the hands the rest | yes |
| 6 | The head at its birth: + the weapon in his hand (9), the enemy in view (1), the yellows' timers (4), the mega's and red's timers (4); − the order's ten | at zero effect |
| 7 | **At the end of the 1.8 run:** the strategy inputs fade out of the hands (the clock and score 8, the mega's and red's timers and who has them, when he last took each item 12, the game's 3) over 40 updates, held 20, then removed from the hands' list | no: a stage with its own checks |
| 8 | The five rules (F) into CLAUDE.md | |

The lists: the simulator about 840 columns; the hands about 760, about 730 after 7; the brain about 726; the head about 89 of its own beside
the belief and the hands' memory. Kept in the hands for now: the places, the holds, the small items (where his targets are), judged at
full size after the run (E).

## State and what a new session picks up (2026-11-11 afternoon)

**Nothing of the clean-up is built.** Decided and recorded above; the owner starts the next session for it. In order:

1. Time the building of each input group in the plugin (the latency baseline); make the audit a tool (`tools/run/input_health.py`, from
   `docs/runs/1.8/1.8a/audit_obs.py` and the audit's two inline analyses: constants, size, clip, each group's share at each reader).
2. The new list in `sim/duel_env.py` behind one switch; today's simulator frozen as a copy for every older network; `tools/make_ffa_env.py`'s
   anchors; `docs/INPUTS.csv` and a frozen `docs/INPUTS_1053.csv`.
3. The converter (by name; constants folded into the bias or the token's mark; the rescale with the optimizer's moments; each network's own
   list in the checkpoint) for b1.2d's end, its optimizer and 1.3b's three anchors.
4. Proofs: 0 actions differ against the unconverted network at fixed seeds; the plugin's inputs against the simulator's in a real game.
5. AIM3's open points on the cleaned network.
6. 1.8a's start and tests again on the cleaned start, the last stage built ([runs/1.8/1.8a/CARD.md](../runs/1.8/1.8a/CARD.md)); the owner's go.

1.8a's schedule as agreed (owner: "keep the head at 80. The rest looks fine"): AIM3 over updates 0 to 30; the head's credit 50 to 130; the
restart at 150; the item teacher and the speed pay out 160 to 190; the keep choice 210 to 250; the strategy inputs out of the hands 270 to
310; the end at 330 (about 29 hours at 5.3 minutes an update).

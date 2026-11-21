# 1.7a: the combat order, as specced: the lock overhauled, the head's order (a kind, a candidate by a pointer, the way), the brain's pass odds, the fire push, from 1.6a's end

*2026-11-05 (owner): "Stop thinking in terms of sub runs, it's all 1.7"; "You build it as it was originally specced. There is no 'make
it simpler so it's ready' ... build 1.7 CORRECTLY as one branch." One run carries [the combat order](../README.md) whole: the 8 s lock
replaced by a learnt choice to keep or re-decide five times a second (an arrival keepable); at each reading the head's order: **a kind**
(the target as chosen, cut off, spam, break off), **a candidate by a pointer** over every kind's candidates, **the way**; the brain's
lesson of the odds he passes each candidate; the hands reading the order's point; his weapon reading the order; the head's push on the
fire key on its own clock; the start fitted to the pros. 2026-11-04 night (owner): "that decision happens every 0.2s, which makes him
feel alive." Starts from [1.6a](../../1.6/1.6a/CARD.md)'s end. **Built 11-05 on one branch, `b17` (worktree `BobbyBones-17b`; the
build, part by part: [BUILD.md](../BUILD.md)); every test passed; the start level-checked (47% at full share: the rarer start).**
**Ready (11-05 evening). The owner starts it in a new session:** `powershell -ExecutionPolicy Bypass -File docs\runs\1.7\1.7a\start.ps1
-Until "2026-11-06 21:00"` (owner: "run it until 9pm tomorrow (friday 11/6)"). The run starts only on the owner's command.*

**Started from:** 1.6a's end (`data/sim_runs/duel_gru_1_6a/keep/policy_end_16a.pt`, update 80) with its optimizer.

**Marks:** ✅ known or decided · ⏳ to build · 🧪 to measure · ❓ owner's decision

## In short

| Updates | What | Dial |
|---|---|---|
| 0 | 1.6a's end given the keep choice (share 0) and the whole order (share 0, adds 0, its token shut, the pros' fit with the new kinds 4.5 times rarer as its start: the owner's "rarer start"), the fire push (add 0), the pass readout: it plays as 1.6a's end (`keep_init.py`, `order_init.py` `same`); the league's files given the order's inputs at zero | `--keep-g 0 --cmb-g 0 --padd 0 --fadd 0 --head2-fpg 0`, `COMBAT=1`, `order_init.py --kind-shift 1.5` |
| 0 to the end | **the brain's pass lesson** (its own layers; nothing else moves by it) | `--pass-odds 0.3 --pass-warm 0` |
| 0 to 10 | as 1.6a's end: the trial, a check at update 10 | |
| 10 to 90 | **the lock handed to the keep choice**, +0.0125 an update ✅ (owner: 80 updates) | live `KEEP_G` 0 → 1 |
| 90 to 170 | **the order and the fire push opened together** ✅ (owner, 11-05): the order asked at a share, its pointer's scores on his targets and his way, its token for the hands; the head's push on the trigger, half the trigger's credit on the head's clock (owner: "Ok that seems fair") | live `CMB_G` 0 → 1, `PADD` 0 → 0.3, `ORD_GATE` −12 → 0 (shut before); `FADD` 0 → 1, `H2_FPG` 0 → 0.5 |
| 170 to the end | every dial held at its end value (`PADD` 0.3, `H2_FPG` 0.5, the rest 1) | |
| Length | ✅ until 21:00 on Friday 11-06 (owner, 11-05 evening): `start.ps1 -Until "2026-11-06 21:00"` works out the minutes | `--minutes` |

## The combat order as built (11-05) ✅ (part by part: [BUILD.md](../BUILD.md))

| | |
|---|---|
| The map's numbers | `tools/order_maps.py` -> `sim/order_maps/<map>.npz`, the ten maps: sight between every two places, doorways and corridors, teleporters, the spam points (doorways, exits, the pros' blind-shot spots) with their lines of fire, the ways out, the holds' lanes, the seconds of way between every two places |
| The order | at each reading of his target that counts (five a second in the keep choice's seconds), with the share `CMB_G`: **a kind** (the target as chosen, cut off, spam, break off; κ = W s + U ctx + b, a kind with no valid candidate shut), then **a candidate** by AlphaStar's pointer, one scorer for every candidate, g(s, x) = v·tanh(A s + B x + c), over 3 cut-off places (the brain's 1, 2, 4 s ahead), 8 spam points, 8 ways out; the same scorer on the 17 targets and his 3 ways, added (x `PADD`) to the head's target and way scores. Head-only (S5); learnt in the head's own clipped term with the target and the keep choice (λ 0.995), no entropy bonus, no pay of its own |
| Each candidate's numbers | 34: kind, his and the enemy's seconds of way, height, range, its place in his facing, seen from the brain's places ahead and from him, doorway, corridor and width, teleporter, item up or due, holding place, the pros' blind shots there by weapon, **the brain's odds he passes it in 1, 2, 4 s**, valid; the situation (14) for the kind |
| Its start | **fitted to the pros, the new kinds 4.5 times rarer** (owner, 11-05: "the rarer start is good"; the fit as is 32% in its level check, this 47%) (`tools/order_pros.py`: 120,000 moments of 600 duels on the ten maps, labelled in hindsight: spam, break off, item, hold, cut off, chase; the kind's U, b and the pointer's B, c, v by maximum likelihood, the weights on his state zero) |
| Cut off | his way to the chosen place ahead, followed as the look-ahead moves, his legs looking there; arrived (keepable) within 300 units or with the enemy in view; given up without the brain's answer |
| Spam | his way to the place with a line of fire to the chosen point nearest him, his legs looking at the point; arrived there or with the point in sight within 1,500 units |
| Break off | his way to the chosen way out (out of the brain's predicted sight; a health or armor item up or due), his legs on the brain's place 1 s ahead; arrived where the predicted places do not see him; ended at an item |
| The brain's lesson | the odds the enemy passes each candidate within 1, 2, 4 s, on the brain's state (no gradient into the brain), graded in hindsight (`sim/passodds.py`) |
| What the hands see | 10 new inputs: the order's kind, the point to watch or shoot (its direction, pitch, distance, height), whether to shoot it; an attention token of their own, left out while shut (the start to the bit) and opened with the order (`ORD_GATE`) |
| His weapon | the head's weapon part and its own inputs read the order's (at zero to begin with) |
| The fire push | the head's two scores on the fire key (`fsc`, live `FADD`), its credit on the head's clock (`H2_FPG`: a lob pays 1 to 3 s after it leaves) |
| The checks and the servers | the checks' player and the plugins play all of it (the plugin's forward pass the checks' to the bit: `plugin_parity.py`) |
| Records | `cmb`: share, adds, the token's gate, readings asked, p(an order), drawn and p by kind; the simulators' chosen, frames, arrivals and damage by kind; the pass lesson (loss, Brier against its base rate); the order's weights; `fire` |

## How his target is chosen and kept

| | Today | At share 1 |
|---|---|---|
| Which target | one choice of 17 (nothing, the items, the weapons, the enemy, the holding places): the hands' rows plus the head's scores, learnt by the head's own lesson only (`H2_PG` 1, since 1.3b) | the same |
| When a new draw counts | at a reading (once a second, staggered; at once after a spawn and when a contact begins) only if his target is "nothing", reached, gone, 8 s old (really 9), or he is in contact (the enemy seen or heard in the last 2 s, `CONTACT_FREE` 1); a holding place may be left for an item. Everything else is held: the blinders | **the keep choice**: at each reading, keep or re-decide; only a re-decision draws the target (it may come out the same, and then its age runs on) |
| Readings | once a second | **at the head's tick, five a second** ✅ |
| How long a target lasts | the lock's 8 s, or until a release | the run of keeps: no duration is chosen |

**The keep choice** (`sim/head2.py`, `head2.keep`, built in 1.4c): one layer of the strategy head giving the logit of re-deciding,
z = w_s·s + w_h·h + w_age·age + w_c·contact + w_lp·lp_held + w_a·arrived + w_t·since_arrival + b, P(re-decide) = σ(z).

| Input | What | Learns through it | At its start |
|---|---|---|---|
| s | the head's memory (its GRU of 256; reads the brain, the readouts, his stack, item timers, score and clock, the hands' memory) | yes: the gradient goes on into the head's GRU and its input layer | 0 |
| h | the hands' memory (512) | no: a number | 0 |
| age | seconds since his target changed (/ 10, at most 20 s); 0 in contact | | the soft lock (below) |
| contact | the enemy seen or heard in the last 2 s | | the soft lock |
| lp_held | the held target's log-probability under the present scores (from 1.7b: the held order's) | | 0 |
| arrived, seconds since arrival ⏳ | he stands at his holding place, or the enemy he hunts is in view (from 1.7b: any arrival); for how long | | 90% a second; 0 |

- **Learnt** in the head's own clipped term only: at a reading it decided, his log-probability is that of keep or re-decide, plus the
  target's where one was drawn; the head's advantage (λ 0.995, about 5 s) and its two-minute value; no entropy bonus; no pay of its own.
  Only readings it decided teach it (its own seats): at share 0 it learns nothing.
- **At its start the head decides nothing:** the weights on s, h and lp_held are zero, so it is the lock made soft on the age and contact
  alone. It becomes the head's decision as those weights grow (the record's split, below).
- **The hand-over:** with chance g the keep choice owns a stretch of readings, otherwise the lock rule; each league network at the share
  in its own file, a network without the choice with the lock.

## Changes to 1.4c's build ✅ (built 11-05, branch `b17a`; tests below)

| | Why | What |
|---|---|---|
| **1. Readings at the head's tick** ✅ (owner) | a reading once a second keeps a sound or a hit from out of view waiting up to a second; the head already ticks every 0.2 s | the keep choice reads on the frame after each head tick (all seats, every 8 frames), with the state that tick made (1.4c's code reads the state before the tick). The hand-over in whole seconds: at each of a seat's lock-rule readings (once a second, staggered, as today) a coin with chance g gives the next second to the keep choice (its five readings) or to the lock rule (its one). At share 0 every reading is today's: identity to the bit |
| **2. Its start re-fitted for five readings a second** | 1.4c's start is a chance per reading once a second | the same chance per second: per reading 1 − (1 − σ(0.75 × (age − 8.5)))^(1/5): 0.07% at 1 s, 1.4% at 5 s, 5.5% at 7 s, 16% at 9 s, 38% at 11.5 s; in contact 37% (90% a second). A logistic fitted to it (`keep_init.py add`), checked by `same` at share 1 against these numbers |
| **3. An arrival stays keepable, with its own clock** ✅ (owner: "This is the right path") | "reached" means ended for an item (taken) but arrived for the enemy (in view: `note_hunt`, `sim/duel_env.py:8188`) and a holding place (stood at: `note_holds`, `:8557`); both stay "reached" until his target changes, so every later reading is forced to draw again: "fight him" and "hold this angle" could never be kept | "reached" split in two: **ended** (taken, gone, "nothing", a spawn: a forced re-decision) and **arrived** (the enemy in view, a holding place stood at: the keep choice decides), built as a general kind for 1.7b's arrivals (a cut-off point, a spam spot). Two more numbers for the keep choice (arrived; the seconds since arrival; KEEP_F 3 → 7 with the optional two): without them the age, counted from the choice, would end a hold soon after he gets there; with them how long he holds an angle is learnt. Their start: an arrival re-decided about 90% a second (37% a reading), as today's forced draw once a second. The lock rule keeps its forced readings: share 0 the same to the bit |
| **4. The optimizer's groups** | the trainer's resume chain (`sim/train_duel_rnn.py` 2600-2683) takes a save with [the head's, the weapon part's] groups for 1.4c's [head, keep]; a parameter's shape differs and **the whole network's optimizer starts cold**, said in one log line (`optimizer: opt.pt does not fit ...`); every later resume would meet the same (its branch expects head, keep, weapon) | a branch for a save with the head and the weapon part gaining the keep choice; one order on every later resume, told apart by the saved groups' sizes (the keep choice 2 tensors, the weapon part 4); on `--resume` with an `opt.pt` a load that fails stops the trainer (a flag allows a cold start on purpose); `start.ps1` checks the line. A smoke that restarts from a save |
| **5. The record** | to see whether the decision becomes the head's | the keep layer's pull from the memories (s, h) against the age, contact and arrival numbers, per update; re-decisions a second, in and out of contact; the blinders (1.4c's counters); holds: how long, what they bring |
| Optional ✅ (owner, 11-05: yes) | a sound reaches the keep choice only through the memories (a trainable path through the head's GRU, which reads the hands' memory) | two numbers of its own, a sound heard and a hit taken with the enemy out of view, each exp(−seconds / 2) (1 just now), at zero weight (identity kept) |
| **As built** | | the simulator's keep column is d + 2c + 4r (the draw, the hand-over's coin, a keep reading on the frame after the head's tick), −1 the lock rule; `intent_arr` and `arr_t` (arrivals), `khit_t` (hit unseen), `kown` (the keep choice's second), `stats["keep2"]` (its seconds and readings); `keep_feat()` 7 columns. A forced reading of the keep choice that draws the same target starts it anew (the lock rule keeps its "reached", as before). The layout's `keep` is 2 (1.4c's 1, three numbers, is refused). The start (`keep_init.py add`, 1.5a's end): out of contact z = 0.68 × age − 7.66 a reading, a target held 7.76 s against 1.4c's 7.80 s (the survival curves within 0.013); in contact and at an arrival 0.369 a reading (90% a second). The record: `keep.pull` (its logit's parts: the head's state, the hands' memory, its own numbers), `keep.arrived`, `keep.sim2` |

## What 1.4c showed ✅

Its level check (the start at share 1, once a second, against 1.4b's save of update 30): 112-88 (56.0%). It re-decided at 54% of
readings (the lock rule frees 60%), 90% in contact, and kept his target after a sound out of contact 92% of the time: the blinders are there
at the start, for the run to learn away. It does not carry over (no weapon part then, readings once a second, no arrivals): 1.7a's start
gets its own level check.

## Before the start ✅ (11-05 evening)

| | |
|---|---|
| The code ✅ | one branch, `b17` (1.7a's keep choice its first commit), merged into `main` after 1.6a ended; `duel_env_ffa.py` regenerated; `docs/INPUTS.csv` 990 rows |
| The simulator ✅ | `ident.py` ALL PASSED (20 checks): the order off and never asked = 1.6a's simulator to the bit; asked: every kind chosen, followed, arriving; the group module the duel module's to the bit, the order off and on (Blood Run, 1,500 frames) |
| The start ✅ | `keep_init.py same`, `order_init.py same`: 0 of 3,200 actions differ at share 0; the attention part without the shut token to the bit (torch and numpy) |
| The trainer ✅ | `tests.py ident` ALL PASSED: 1.7's code with the inputs widened = 1.6a's code up to the rounding of the wider first layer (both updates: no action differs, log p within 0.00013); everything at zero and COMBAT on = that, to the bit; the optimizer's moments carried over the widened inputs. `tests.py smoke` ALL PASSED: every part open from update 0, 80 small updates: the records, the pass odds learning (Brier 0.162 → 0.101, base 0.151), the order's weights on his state growing from zero, the fire push growing, a restart from a save with its optimizer, a one-map check |
| The plugins ✅ | `plugin_parity.py`: the plugin's forward pass the checks' to the bit with every part open; a real server not tried |
| The fit to the pros ✅ | 120,000 moments of 600 duels, ten maps: held-out log loss of the kind 0.442 (the kinds' shares alone 0.477), of the candidate 1.227 (even 2.580); after two label fixes (the pros' belief from sight and sound, 20 s; no break off, cut off or chase across a death or a teleporter) |
| The level checks ✅ | 200 games against 1.6a's end each ([BUILD.md](../BUILD.md) part 9): the keep choice alone 57.5%; with the order at full share, the fit as is 32.0%, **the rarer start 47.0% (passes: the start used)**; the pointer's scores on his targets: at full weight 30.5% (61-139: fails); at 0.3 53.5% (107-93: passes) |
| The ramp ✅ | `ramp_17a.py` (`ramp_test.py` ALL PASSED): the owner's schedule; a part of a sum over 40 flagged |
| Run files ✅ | `make_files.py`; `start.ps1` (the rarer start; `-Until`; refuses without a length, with any firing cost, if the start does not answer as 1.6a's end, or if the optimizer does not load); the settings check passes against 1.6a's command and its end; 1.6a's dials at their ends |
| No dry run | (owner, 11-04) the first 10 updates and the check at update 10 are the trial |

## The checks

200 games every 20 updates against 1.6a's end, every fourth against b1.2d's end; an extra one at update 10 and ❓ one at update 20 (ten
updates into the hand-over); each seat at its own share. 1.5a's weapon measures in each; the head's weapon scores switched off at the end.
Every win rate reported; under 40% flagged at once; never held or stopped (rule 6). Saves kept with their optimizer at updates 10
(share 0), 50 (share 0.5), 90 (share 1) and the end.

## Watched and judged by

| Measure | Wanted |
|---|---|
| Win rate against 1.6a's end; against b1.2d's end | level or better (the zero point: about 50%) |
| **The keep choice's pull from the head's memory** against the age, contact and arrival | grows: the decision becomes the head's |
| **Feels alive**: the time from a sound, a sight or a hit from out of view to a change of target; the blinders | down |
| No flicker (b1.1a's sign: trips 12.6 → 20 a minute, targets reached 40% → 21%): trips a minute, targets reached and abandoned, re-decisions a second | no slide |
| Contacts on an item plan (1.6a's baseline) | down where fighting pays |
| Hunts held past the first sight; their frags | up |
| Holds: how long, the rail there, frags from there; the holding places' share of his time; spawn camping | holds that pay; no rise like 10-12's (places at 5% of readings were 22% of his time) |
| Big weapons owned, his weapon by distance; speed; the mega and red armor first | hold |

## The equilibrium

Nothing pays for the target itself (since 1.6a): a plan is priced only by what it leads to. In self-play the keep choice's best answer is
to hold a plan while it still pays (an item race, an escape, a fight he is winning, an angle the enemy will come through) and to drop it
when what he senses changes the best plan (a sound, a hit from out of view, the enemy's believed place, a timer). Both copies learn the
same; the combat and item parts are zero-sum, and the win part pays the copy that reacts better. On the way: shorter holds around sounds
and the enemy, long ones on item timing and at angles that pay, less churn in fights.

## Red team

| Part | Hand-built or assumed | The measured alternative | Watch |
|---|---|---|---|
| Keeping split from choosing | assumed (AlphaStar's "no new order"; option-critic's termination) | the lock 8 → 0 (b1.1a: 41% head to head, no head, speed pay on) | trips, targets reached |
| Five readings a second | the owner's call; the head's tick | once a second (1.4c) | re-decisions a second, flicker |
| The start re-fitted from 1.4c's per-second chances | assumed: the same hazard a second | 1.4c's start as it was (five times the re-decisions) | the level check |
| The age, contact and arrival inputs | hand-made numbers it may lean on for good ("re-decide at 8.5 s" learnt) | the memories alone | the pull's split |
| The hands' memory a number to this choice | a choice of safety (a new output's gradient into the shared memory can cost aim) | with its gradient | aim and hits |
| Forced re-decisions where the target ended | hand-built: "ended" | everything learnt | time on a gone target |
| An arrival keepable | the owner's call | forced, as today | time at places against what they bring |
| No entropy bonus, no price on re-deciding | assumed | a price, sized against the entropy bonus | re-decisions a second |
| The keep choice's frames in the head's term (five a second against the target's one) | assumed harmless: most keeps are near-certain, small gradient | a weight per part | the target's measures (1.3b's) hold |
| The candidates (3 cut-off horizons, the 8 spam points nearest the brain's places, the 8 best ways out by seconds of way) | hand-built lists, learnt among by the pointer | a learnt point over the map (AlphaStar's spatial head) | each kind's frames, arrivals and damage |
| The candidates' numbers (34) and the situation's (14) | hand-made features the pointer may lean on for good | the head's state alone (A s, from zero) | the pointer's weights on his state against on the numbers (`cmb.w`) |
| The pros' labels (part 9's thresholds) and the places ahead stood in for by the last seen speed | hand-set in hindsight | the brain run on demos; other thresholds | the fit's held-out likelihood; the level check; p by kind against the pros' shares |
| A label whose kind has no valid candidate left out of the fit | the network cannot choose it there | counted as the target as chosen | the count in `order_fit.json` |
| "Passes" within 192 across, 128 up | hand-set | other radii | the pass lesson's Brier against its base rate |
| The order made at the keep reading before that frame's outputs (the candidates one frame old) | the simulators make them after the tick's frame | a frame later | nothing to watch: the trainer and the learning step read the same |
| The shut token left out of the attention entirely | so the start answers to the bit | e^-30 (older kinds) | none |
| The order and the fire push opened together after the keep choice (u90 to 170; the owner's) | the owner's call, 11-05 | together | the checks from u90 |
| The way's third level inert without `WAYS` (one way to each target) | the owner's call: the ways next round (B-301) | `WAYS=1` | the way's adds choose nothing until then |
| The rarer start: the new kinds 4.5 times rarer than the pros' fit | measured: the fit as is 32%, this 47% at full share | the fit as is | p by kind (`cmb.p`) climbing where orders pay |
| The pros' labels after the two fixes (sight and sound; no break off across a death) | measured: 23% → 5% of spam labels without a candidate; break off 7.7% → 3.5% of moments | the first labels | the level check |
| `PADD` held at 0.3 from update 170 (a fixed dial, live-settable; the pointer's scores themselves keep learning) | measured (at full weight 30.5% (61-139: fails); at 0.3 53.5% (107-93: passes)) | 1 | his target choice's two parts (`cmb.sums.targets`): the add against the hands' |
| A sum of two outputs regularized (rule 11): `H2_L2` 0.01 on both parts of the fire key and of the pointer's adds | the owner's rule | none | each part's size; a flag over 40 |
| The trigger's credit only halfway (`H2_FPG` 0.5) | the owner's call | all the way | hits and accuracy by weapon |
| Pay pathologies (the ledger) | | | negative frags, sign flips, lopsided games |

## The owner's decisions

| | | |
|---|---|---|
| 1 | ✅ the hand-over over 80 updates | owner, 11-04 night |
| 2 | ✅ readings at the head's rate, five a second | owner, 11-04 night |
| 3 | ✅ an arrival keepable, with its own clock | owner, 11-04 night |
| 4 | ✅ the length: until 21:00 on Friday 11-06 ("run it until 9pm tomorrow (friday 11/6)") | owner, 11-05 evening |
| 5 | ✅ the sound and hit numbers in (owner, 11-05); update 20 is a regular check (every 20), no extra one | owner, 11-05 |
| 6 | ✅ checks: "Run whatever checks you need, you don't need to ask me"; 1.6a's leftover processes stopped | owner, 11-05 evening |
| 6b | ✅ the schedule: the lock first (10 to 90), then the order and the fire push together (90 to 170); the trigger's credit halfway | owner, 11-05 evening |
| 6c | ✅ the ways (`WAYS`): "We can leave the routes for the next round" (B-301) | owner, 11-05 evening |
| 6d | ✅ the rarer start: "yes, the rarer start is good" | owner, 11-05 evening |
| 6e | ✅ a decision from a sum of two learned outputs is regularized (CLAUDE.md rule 11) | owner, 11-05 evening |
| 6f | ✅ `PADD`'s end value (0 to it over updates 90 to 170, then held): the highest of 1 and 0.3 that passes the level check, else 0: **0.3** | owner, 11-05 evening ("OK just give me the results") |
| 7 | ✅ the start: "Go ahead and start it" | owner, 11-05 18:00 |

## The result

**A false start, 18:01 to 19:23 (update 14; kept aside as `data/sim_runs/duel_gru_1_7a_false_start` and its log).** The trainer refused
every live.json: `start.ps1` and the ramp wrote the order's gate as −30, and the trainer's reader took any number below 0 as an error and
refused the whole file. It then trained on its command's start values: the item teacher (weight 0.1 to 1.0), the speed pay (0.75 a
player-minute), the jerk, weapon-switch and fire-toggle costs (−0.39, −0.10, −0.07 a player-minute), no win pay, damage taken 1.0, the
long rail 0.12, and the keep choice's dial at 0 whatever the ramp wrote. The ramp flagged the costs every update from 18:10; nobody read it
until 19:20. Its check at update 10 read about level with 1.6a's end on the maps played. Stopped on the owner's word ("Restart it and fix
it. Whatever cause this to happen this way needs to isolated and mdae to not happen again").

**Why nothing caught it:** `start.ps1` compared the file's values with 1.6a's end but never asked the trainer whether it accepts it; the
ramp's test ran on fake files; `tests.py ident` set the dials by argument and `smoke` opened them all (to values of 0 or more); the trainer
printed REFUSED and went on; the ramp's flag was a line in a log.

**The fix (11-05 19:23 to 19:42):**

| | |
|---|---|
| The trainer | `LIVE_RANGE` (a live name that may be below 0: `ORD_GATE` −30 .. 0; every other 0 .. inf); a file refused before the first rollout stops it (exit 3, "NOT TRAINING"); every read written to `<run>/live_status.json` |
| Before a start | `tools/run/live_accept.py`: the start's file and every one the ramp will write (172, clocks 0 to 171) read with the trainer's own reader; in `start.ps1`, which then waits for the trainer's "applied" before it starts anything beside it |
| While it runs | the ramp: a refusal, a dial not played as written (within the 3 updates the overlap takes), and any firing cost logged as MAJOR PROBLEM; `tools/run/watch.py` logs a refusal for every run |
| Tests | `tests.py live` (the real trainer, small, on the CPU): the start's file applied, no cost, speed pay or teacher in the books, a dial written after update 1 played by update 4; a gate of −31 stops the trainer before any update: ALL PASSED. `ramp_test.py` with the new flags: ALL PASSED. `live_accept.py` on the old trainer code refuses the false start's file; on the new, accepts it |
| Rules | CLAUDE.md (gotchas): every live name its range and a test on the real trainer; monitoring reads every FLAG and MAJOR line from update 1 |

**Restarted 2026-11-05 19:42 from 1.6a's end**, until 21:00 on 11-06 (1,518 minutes): settings checks PASS, no firing cost, LIVE ACCEPT
PASS, the start the same as 1.6a's end to the bit, live.json applied before the first rollout (19:42:33); update 1: no jerk, switch or toggle
cost, no speed pay, the item teacher at 0, the win part in the books.

**Ended on the owner's word 2026-11-06 19:15 at update 246** (**1.7a's result is the save of update 90** (owner, 11-06: "save that as 1.7a; update 90. That has JUST the choice redesign"): the keep choice alone at 0.975, the order never asked, 63.0% against 1.6a's end; `keep/policy_end_17a.pt` + `opt_end_17a.pt`; the last save, update 240, kept as `keep/policy_u240_17a.pt`): level with 1.6a's end (49.5% at update 210) after 63-64% at updates 90 to 130; the keep choice won games but flickered (trips 25 -> 81 a player-minute, reached 24% -> 8%); the order was learnt away (2.1% -> 0.02% of readings); [postmortem](POSTMORTEM.md).

**Local play test (11-06 evening)** of the update-90 save on image `qlbot:17a` (the public build `pub-4464445` + 1.7, built from `main`). Its first start failed: `sim/passodds.py` imported torch at the top, the servers have no torch, and the bot stopped on every frame (`plugin_parity.py` ran on this PC, which has torch). Fixed: torch only inside the functions that need it; checked in the image without torch (`import passodds, netpass`), the trainer's side unchanged (the module's loss at the prior: 0.105).

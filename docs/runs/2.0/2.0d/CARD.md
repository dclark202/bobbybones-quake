# 2.0d: 1.7a's update 90 cleaned up, on AIM3, with dodge inputs, in the corrected simulator

**Started from:** 1.7a's update 90 (`data/sim_runs/duel_gru_1_7a/keep/policy_u90_17a.pt` + `opt_u90_17a.pt`; byte-identical to
`policy_end_17a.pt` / `opt_end_17a.pt`, checked 2026-11-13 by SHA-256).

**Built 2026-11-13, not started** (the state of each part: "Before the go" below). The owner, on the first draft: "starting from 1.7a u90; a
short run with aim3 mechanics and *something* to help him understand how to dodge better ... three purposes: get him onto aim3, add
inputs for helping to dodge, remove dead inputs"; then "Dodging inputs are good"; then "Focus on the easy stuff first, aim3 config,
remove dead inputs, changes to pay amounts. The flow of strategy inputs out of the hands to the head can be saved for 2.1. I would like
a run of about 80-100 updates that does the work to get 1.7a 'cleaned up' and onto the correct aim3 config, and trains in the corrected
simulator." On the second draft (which had left the dodge inputs out): "The point was to put the dodge inputs in. DO IT", and on the
fade of the head's weapon part: "Makes no damn sense" (the fade is out: item 9 below).

**Marks:** ✅ known or decided · ⏳ to build · 🧪 to measure · ❓ owner's decision

## The owner's page

| | |
|---|---|
| The goal | 1.7a's update 90, with the structural decisions made since it was trained applied, on AIM3, **given inputs to dodge with**, trained in the corrected simulator. The network 2.1 builds on |
| Length | **90 updates** (owner, 11-13): one night at about 7 minutes an update; `stop_at_90.ps1` once update 90's save is kept |
| Checks | every 20 updates, 200 games, against 1.7a's update 90; every fourth against 1.8a's end; the extra one at update 10. **Both seats under AIM3's end values and `KNOCK_QL=1`** (the corrected simulator for both: the control is judged in the same game). Every check reported; one under 40% flagged at once |
| Read at every check | games won by map; megas and reds head to head; **both sides' hit rates by distance and by the target's crossing speed** (the lightning comparison's measure: the dodge inputs' effect shows here), the same table from the real games beside it; the lightning in hand and in view by range, the rail owned (readouts, rule 12); the keep choice's trips, targets reached and quiet re-decisions (1.7a's flicker); the head's and the hands' parts of the target sum and of the weapon key (rule 11); frags a match-minute; the input health report, the dodge group's share at the hands |
| Kept file | `keep/policy_end_20d.pt` + `opt_end_20d.pt`; marks kept at 10, 30, 60, 90 |

## The rule for what goes in (owner, 11-13)

"2.0d is an overnight run to clean up the network by removing dead inputs, and make the structural fixes for aim/dodging and simulator.
That's it." It gets him ready for 2.1, whose goal is the head making the weapon decisions, with map sense and a detailed breakdown of
the action. So: **the head (its target, keep choice, weapon part, pay, inputs) is left exactly as update 90 has it**; 2.0d fixes what
the head's choices will be judged by in 2.1: the inputs it reads by name, how well each weapon really lands (aim, knockback, dodging),
and a league and pay that do not push a weapon on him.

## The simulator correction (done 11-13) ✅

[MECHANICS.md section 7.1](../../../research/MECHANICS.md) flagged the small kicks. Measured on a local lab server
(`plugins/weaponlab.py` set 6, `data/weaponlab6`), then fixed behind `KNOCK_QL=1` (off = the simulator before, bit-identical over
4,000 frames with 32 players):

| One hit, horizontal push | Game, in the air | Simulator before | `KNOCK_QL=1` |
|---|---|---|---|
| Lightning tick | 47.5 u/s (50 at the aim's 18 degrees) | 33.3 | **47.5** |
| Machine gun bullet | 23.8 | 9.5 | **23.8** |
| Heavy machine gun bullet | 38.0 | 23.8 | **38.0** |
| Shotgun, full shot | 357 (500 at 44 degrees) | 303 | 340 (95 of 100 damage landed) |
| Rocket, rail | 428, 340 | 428, 340 | unchanged |

On the ground, the game takes 15 u/s a frame by friction from the hit frame on; the old factors had been fitted to that leftover
speed, and then gave no friction for 50 ms. Now the kick is the game's and friction starts at once. The hit frame's order (the game
moves the target in the hit frame, the simulator a frame later) and the long stream in open air are being fixed by the other session
(`KNOCK_NOW`, owner 11-13); 2.0d runs with whatever of it is built and tested by the go.

**What it changes in play:** a lightning stream pushes a target 1.4 times harder (about 1,000 u/s of push a second at full contact in
the air), and machine-gun fire 2.5 times. Both players are moved more by small hits, so tracking a pushed target is a little harder,
and being on the receiving end of the lightning is a bit more disruptive.

## What goes in

| # | Change | Kind | When |
|---|---|---|---|
| 1 | **The input list 20d** (821 columns: list 18's cut, with **the order's ten inputs kept** (owner, 11-13) and the dodge group): the dead columns cut and folded, the 72 rule-made columns out (pre-fire, emergence, rule belief, place flags, stack by rule), every input re-measured to its size on 1.7a's own play, each network its own list by name | exact (`tools/inputs20d.py same`: 0 actions differ) | the start |
| 2 | **1.7a's combat order not asked** (its kind, pointer, fire push), as at update 90 (`CMB_G`, `PADD`, `FADD` 0, its parts kept in the file); **the brain's pass-odds lesson out** (`--pass-odds 0`). `COMBAT=1` stays: the order's ten inputs carry his target's look point | exact | the start |
| 3 | The keep choice's share to 1 (the lock's last 2.5% out: rule 13) | not exact (2.5% of his seconds) | the start |
| 4 | **The corrected knockback** (`KNOCK_QL=1`, and `KNOCK_NOW` if built) | the game's physics | the start (a switch, not live) |
| 5 | **Pay amounts**: damage 0.005 zero-sum (0.0055 dealt / 0.8 taken → 0.005 / 1.0; owner 11-11); the far-rail pay 0.25 → 0.1 (owner 11-12) | pay | the start, as a step (as 1.8a did) |
| 6 | **No weapon habits in the league** (`HABIT_P` 0.3 → 0; scrapped in 1.8a) | league | the start |
| 7 | **AIM3 at the 11-11 tuning**: `AIM3_W` 0 → 1, `AIM3_SIZE_A` 1 → 0.39, `AIM3_SIZE_B` 0 → 0.355, `AIM3_LEAD` 0 → 1, `AIM3_RELOAD` 1 → 0; `AIM3_FIX_TAU` 0.05 from the start | aim | ramp, updates 0 to 30 |
| 8 | ~~The head paid by the win chance only~~: **moved to 2.1** (11-13). 2.0d does not touch the strategy layer; the head's pay is part of 2.1's change to the head | | |
| 9 | **The dodge inputs** (below), read by the hands, as a token whose gate starts shut (rule 13: they learn silently, then open) | new inputs | in at zero at the start; the gate opens over updates 30 to 60 |

**Kept as update 90 has it:** the head's target choice and its credit (`H2_PG` 1, `H2_L2` on both parts of the sum), **the head's part
of the weapon key** (1.5a's weapon scores, `wadd` 1, learning, with `H2_L2` on both parts and their sizes flagged over 40), the keep
choice (learning), no firing cost, no item teacher, no speed pay, the switch cost out, the win part `WIN_ADD` 0.33, the item table,
every delay. The 10 "order" inputs of the hands (the look point of his chosen target; owner, 11-13: "keep them").

**Why the head's weapon part stays (the second draft faded it out over updates 40 to 70; removed 11-13).** The fade copied 1.8a, which
had dropped it because switched off it read 100-100. But 2.1's goal is the head choosing the weapon, and 2.1a's own card says "nothing it
replaces is taken away before it is shown to carry the weight". Taking out the head's only weapon route one run before 2.1 gives it the
weapon works against that. It stays as it is; 2.1 decides what happens to it beside the instruction's binding weapon (`INS_BIND`).

**Saved for 2.1** (owner): the strategy inputs out of the hands to the head (`SFADE`), the head's new columns at its birth, the
instruction.

## The dodge inputs (item 9) ✅ built and measured 11-13

What he has today for being shot at: the enemy's facing (yaw only, sin/cos, columns 216-217, "turned toward him"), the enemy firing
now (235), damage taken this frame and where it came from (220-222). Nothing says **where the enemy's aim sits on him**, **how fast he
is crossing the enemy's line of fire**, or **whether he is being tracked**. The group "b20d dodge" (`sim/duel_env.py`, `DODGE_IN`,
`_dodge`; the full list's last 7 columns, 1,101 to 1,107):

| Input | What a person perceives | Scale |
|---|---|---|
| The enemy's aim passes him, sideways | the enemy's facing (yaw, pitch) at the same old sighting as his other enemy inputs, with SENSE_MINOR's drifting facing error (15 degrees, 0.5 s), none while a lightning or rail beam of the enemy's is drawn this frame; the miss at his distance; +-3 when the enemy is turned away; only while the enemy is in view | units / 100, -3 .. 3 |
| The enemy's aim passes him, up or down | the same, the aim's height against his body's middle | units / 100, -3 .. 3 |
| His crossing of the enemy's line of fire | his velocity less the enemy's as he reads it, around the enemy's believed place; while the enemy is in view or was within 5 s | degrees a second / 100, -3 .. 3 |
| The crossing's change | the crossing less the crossing 0.25 s ago: a reversal reads twice the crossing | the same |
| Damage taken, short | a sum fading with 0.5 s | points / 50, at most 2 |
| Damage taken, long | a sum fading with 2 s | points / 200, at most 2 |
| The enemy's lightning on him | the share of the enemy's lightning ticks he perceived (the enemy in view, or the tick hit him) that hit him, both counts fading with 1 s | 0 .. 1 |

"Around the enemy" is one sign for the aim and the crossing (+ = counter-clockwise from above, to the enemy's left): "his aim on my +
side and I cross +" is moving into it. The sight error's noise has a random stream of its own: the game is not changed by the switch.

**Proved (11-13):** off = the simulator before to the bit (1.7a's command, `KNOCK_QL=1 KNOCK_NOW=1`, Campgrounds and Blood Run, 3,000
frames, 32 players: every old input, reward, round end and state); on = the same game (states, rewards, ends, every old input), only
the seven columns added; `duel_env_ffa` regenerated and identical to `duel_env` at two players, off and on; the readings on
hand-placed players (14 cases: the aim's miss sideways and up-down, turned away, out of view, crossing, running together, straight
away, a reversal, the fading sums, the lightning share): all as computed by hand.

**The list:** `sim/input_list_20d.json` / `docs/INPUTS_20d.csv` (`input_list.py extend`): list 18 with the group in the hands' part
(811 columns; the brain the first 691, the hands' encoder the first 803, the tail 8). `sim/duel_env_ffa20d.py` gives it (the trainer's
`--env`). The check tools give an older network its first n columns when the rest are newer groups: "b20d dodge" added to that list
(`tools/duel_eval.py`, `tools/run/dump_eval.py`, `tools/run/ws_eval.py`), or every check of 1.7a u90 would have refused. A check plays
a save trained with the switch with it on (`tools/run/panel.py`, as `SPACE_IN`).

**Their statistics** ✅ ([dodge_stats.json](dodge_stats.json); the converter's numbers for the new columns): 1.7a u90 against itself,
40 games of 5 minutes on the ten maps, under 1.7a's command, the checks' play switches, AIM3's end values and the corrected knockback;
969,000 rows of living seats (the enemy in view 17% of them):

| Input | Mean | Spread | Not zero | Half of the non-zero under / 9 in 10 under |
|---|---|---|---|---|
| aim sideways | -0.000 | 0.484 | 14.5% | 0.60 / 2.66 (1.3% at the turned-away cap) |
| aim up-down | -0.010 | 0.355 | 13.5% | 0.43 / 1.66 |
| crossing | -0.012 | 0.471 | 64.8% | 0.22 / 0.79 (22 / 79 degrees a second) |
| crossing change | +0.000 | 0.494 | 64.9% | 0.15 / 0.81 |
| damage taken, short | 0.051 | 0.160 | 19.7% | 0.16 / 0.65 |
| damage taken, long | 0.048 | 0.092 | 56.3% | 0.04 / 0.24 |
| the enemy's lightning on him | 0.094 | 0.213 | 22.5% | 0.41 / 0.78 |

With the enemy in view, his aim passes within 30 units of him sideways 45% of the time. The plugins do not compute them: no 2.0d network on a server before they do. At the end: 200
games with the group blanked; no drop = it does not stay.

## The schedule (updates; every dial live and straight; nothing holds or steps back on its own)

| Updates | Dial | From → to | What | Mark kept |
|---|---|---|---|---|
| 0 | | | items 1-6 at the start, the dodge columns in at zero weights behind a shut gate; the start answers as update 90 under the old simulator (`same`) | start |
| 0 to 30 | `AIM3_W`, `AIM3_SIZE_A/B`, `AIM3_LEAD`, `AIM3_RELOAD` | as item 7 | AIM3 in | 10, 30 |
| 30 to 60 | `DODGE_G` (live, 0 → 1): the dodge columns times it in the simulator; the trainer sets the dodge token's gate to log(`DODGE_G`) (left out at 0) | shut → open | the dodge inputs in | 60 |
| 60 to 90 | | held | the end | 90 = the end |

No restart.

## ❓ Decisions for the owner

1. ✅ **The length**: 90 updates (owner, 11-13).
2. *(was the head's pay; moved to 2.1)*
3. ✅ **Keep them** (owner, 11-13). **The hands' 10 "order" inputs** (the look point of his chosen target). List 18 cut them as dead, and in 1.8a (no combat order)
   they were. **In 1.7a they are not dead:** with `COMBAT=1` they carry his target's look point, and update 90 reads them a little
   (their weights about 8% of an ordinary input's). That is the head's target passed to the hands, which is the by-role way. Keep
   them (my recommendation, exact) or cut them (not exact).
4. ✅ **Learning, flagged** (owner, 11-13; `ramp_20d.py` flags trips over 70, reached under 9%, quiet re-decisions over 0.08). **The keep choice: learning, or frozen?** 1.7a's flicker grew while it trained on (trips 58 → 81 a player-minute after update 90).
   My recommendation: learning, with its three numbers flagged at each check (trips over 70, reached under 9%, quiet re-decisions over
   0.08).
5. **Does dodging pay in the simulator? Calibrated 11-13 (AIM3.md section 3, the correction).** The earlier "the pros' error doubles
   with crossing speed" was a filter's artifact: over every view the pros' lightning error is flat with crossing speed (1.03 / 1.02 /
   1.02 half bodies to 100 deg/s), his grows about as theirs within each distance band, and the hit share is flat for both (pros 44-49%,
   him 46-52%). **No crossing-speed limit.** What does pay against a person is the **reversal**: 75-150 ms after the target changes
   direction the pros' lightning error is x1.31 (hit share 46% → 35%), his under AIM3 x1.14 (53% → 47%). The eye's lag was fitted to
   the rail; the lightning's extra is the hand's. ❓ A hand-lag term after a reversal, fitted to the pros' lightning curve (rule 12), built
   behind a switch, measured untrained, ramped with AIM3; or nothing (the inputs go in; the blank test at the end says whether he used
   them).

## Red team: what is hand-built or assumed, its measured alternative, the pathology checks

| Part | Assumed | The alternative, and what is known | Watch |
|---|---|---|---|
| 2.0c's fall (update 90 + AIM3 + damage 0.002: 35.5 / 39.5% at 50 / 90) | blamed on the damage pay | AIM3 itself costs him under 1.7a's head | the checks at 10 and 30, before the dodge gate opens |
| Several changes at the start (the cut, the kick, the pay step, no habits, the keep share) | each small or exact | one at a time over more updates | the check at 10; if it falls, the start's level check takes them one by one |
| The damage pay as a step at the start | 1.8a did it so | a ramp | the ledger: damage dealt and taken a player-minute cancel |
| The corrected kick from update 0 | the game's value, both seats | a ramp (not possible: a switch) | the lightning's hit rate by distance, both sides |
| The dodge inputs' perception (the enemy's aim from his model's facing, its error by distance) | a person reads where a visible enemy is pointing, exactly while a beam is drawn | the enemy's view angles exact (truth: not fair) | the inputs' statistics against their design; the blank test at the end |
| Dodging pays little against his copies (decision 5) | the inputs help anyway | the tracking limit fitted to the pros | his hit rate by the target's crossing speed beside the pros' and the real games' |
| The conversion of a network with a head | ⏳ `inputs18.py` refuses one today | 1.8a added its head after the cut | `same`: 0 actions differ, twice |
| The head's weapon part kept, learning | it carries little (1.8a: off read 100-100) and does no harm | faded (the second draft; out) | its size against the hands' (rule 11, flagged over 40); the weapon by range, switches a minute |
| No learning-rate-zero warm-up after the surgery ([BOTS.md](../../../research/BOTS.md), OpenAI Five) | the converter carries the optimizer's moments, rescaled | a few updates at learning rate 0 | the KL of updates 1 to 5 |
| Pay pathologies (the ledger) | | | negative frags, sign flips, lopsided games |

## Research check (hard rule 14; `docs/research/README.md`)

1. **The game.** The change touches the knockback of the lightning, the machine guns and the shotgun (MECHANICS.md 1.2, 7.1): now
   measured and fixed (above). AIM3's parameters are the pros' measured aim (AIM3.md; MECHANICS.md 5.3). Still off the game and
   untouched here: the hit cylinder against our box, players passing through each other, the shotgun's fixed rings, the
   footstep rule, fall-damage modifiers (MECHANICS.md 7.1). The box makes every weapon a little easier to hit with, which also makes
   dodging pay a little less than in the game.
2. **What wins.** Zero-sum damage serves "avoid damage as much as you deal it" (DUEL_STRATEGY.md, principle 15): taking a hit now
   costs what dealing one pays, and dodging is how a hit is not taken. The head and its pay are untouched (2.1). The pros' advice to a player out-aimed is movement and position
   (DUEL_STRATEGY.md, the CS-trained friend): the dodge inputs serve that.
3. **The player's view.** The dodge inputs are what a person perceives: the enemy's model pointing at him (with an error by distance,
   exact only while a beam shows it), his own movement, the hits he feels. No truth input. The cut removes only columns that are dead
   or that nothing reads.
4. **In and out of control.** The pay changes are symmetric. Zero-sum damage makes the out-of-control player's "damage at his
   pickups and leave" (principle 6) pay the same as the controller's damage: no new exploit. No pay for places or items changes.
5. **Self-play equilibrium.** Under AIM3 the far rail lands more (his far sight back) and his close lightning a little less (AIM3.md
   section 9); the corrected kick pushes a lightning target harder; dodge inputs let both seats move to be hard to hit, which lowers
   the lightning's worth in self-play toward its worth against people (LG_REAL_VS_SIM.md: people hit him at 43%, he hits them at
   29-39%). How far it moves depends on decision 5: with the simulator's tracking as it is, a fast crossing costs the shooter little.
   The league still holds only his own copies (BOTS.md: GT Sophy's lesson).
6. **Bot precedent.** OpenAI Five's surgery rules (BOTS.md section 3): the same surgery on the league's snapshots (the converter does
   the league's files too); new inputs at zero behind a shut gate. AlphaStar: the control in the checks.
7. **Rule 12.** No pro outcome is a target. AIM3's parameters and the tracking limit (if chosen) are the pros' measured limits; the hit
   rates by crossing speed and the lightning and rail numbers are readouts only.

## Before the go

| # | What | State |
|---|---|---|
| 1 | The decisions above | ✅ 1, 3, 4, 5 (owner, 11-13; 5: "Just keep aim3 as it is": no hand lag) |
| 2 | `KNOCK_QL` built and tested (weaponlab set 6 replayed; off = bit-identical) | ✅ 2026-11-13 |
| 3 | `KNOCK_NOW` (the hit frame's order) and the long stream in open air | ✅ 2026-11-13 (8eb42c5) |
| 4 | The dodge inputs in `sim/duel_env.py` behind `DODGE_IN` (off = bit-identical), `duel_env_ffa` regenerated and checked, `INPUTS_20d.csv` | ✅ 2026-11-13 |
| 4b | Their measured statistics | ✅ 2026-11-13 ([dodge_stats.json](dodge_stats.json)) |
| 4c | The live gate `DODGE_G` (`sim/duel_env.py`: a live and play name, 0 .. 1, the columns times it; off and at 1 bit-identical, at 0.5 exactly half: 1,500 frames, 32 players) and the token "dodge" (`sim/attn.py` DROP_SHUT; the trainer sets its gate to log(`DODGE_G`), logged as `dodge_gate` each update) | ✅ `tests.py ident` (DODGE_G 1 changes update 1's actions; the metrics' gate) and `live` (0.5 written mid-run: columns 0.5, token log 0.5). The live test found a trainer bug: `ls_apply` (live_settings.env) set the simulator's globals on the list's wrapper module (`duel_env_ffa18/20d/21`), which hid the live `DODGE_G` from the trainer and never reached the simulators' own code; fixed (set on the group module), the tests re-run ALL PASSED |
| 5 | `tools/inputs20d.py` (list 20d: 821 columns, the order's ten kept; the head's columns rescaled with the rest, its two cut "exists" folded; the optimizer's moments; the anchors with `--league`), its sample `data/sim_runs/inputs20d/sample_obs.npy` (47,992 rows of 1.7a u90 against itself under 2.0d's settings) | ✅ `tests.py start` ALL PASSED: every first layer's sums within 2e-13 on the sample; `same` 1 of 44,800 actions differs with the brain's rounding off (19 as played: the brain's half-precision inputs on two grids, as 1.8a's); all six anchors convert (within 2e-13) |
| 6 | The run's files (`make_files.py`, `train.cmd`, `start.ps1`, `ramp_20d.py`, `start_live.py`, `stop_at_90.ps1`, `tests.py`); the settings check against 1.7a's command and update 90 (PASS with the card's allowed names); `live_accept` on the start's file and the ramp's 62 (PASS) | ✅; the ramp's flag thread read the smoke run's 10 updates (dodge gate, keep choice, ledger, flags) with no error |
| 7 | Tests (`tests_*.log`, `tests_*2.log` after the fix): start, ident, smoke, live ALL PASSED; the full-size trial: the run's own first updates (the owner, 11-13: "we'll start it shortly") | ✅ |
| 8 | The input health report on the converted start ([input_health_start.log](input_health_start.log)): sizes median 1.00 (12.4% under 0.5: projectiles and grenade arc, columns left with their old statistics by the converter's rule); 20 FLAGs, all small or constant groups also flagged on list 18; the dodge group 0% (zero weights, as built); the order's ten 0.003% of the hands' signal (a small part, as decision 3 said) | ✅ |
| 9 | The owner's go and the length | |

# 2.0d: 1.7a's update 90 cleaned up, on AIM3, in the corrected simulator

**Started from:** 1.7a's update 90 (`data/sim_runs/duel_gru_1_7a/keep/policy_end_17a.pt` + `opt_end_17a.pt`).

**Not built, not started.** A schedule for the owner's review (2026-11-13). The owner: "Focus on the easy stuff first, aim3 config,
remove dead inputs, changes to pay amounts. The flow of strategy inputs out of the hands to the head can be saved for 2.1. I would
like a run of about 80-100 updates that does the work to get 1.7a 'cleaned up' and onto the correct aim3 config, and trains in the
corrected simulator." Earlier: "Dodging inputs are good" (not in this run: see below).

**Marks:** ✅ known or decided · ⏳ to build · 🧪 to measure · ❓ owner's decision

## The owner's page

| | |
|---|---|
| The goal | 1.7a's update 90, with the structural decisions made since it was trained applied, on AIM3, trained in the corrected simulator. The network 2.1 builds on |
| Length | **90 updates** (❓ the owner's 80 to 100): one night at about 7 minutes an update |
| Checks | every 20 updates, 200 games, against 1.7a's update 90; every fourth against 1.8a's end; the extra one at update 10. **Both seats under AIM3's end values and `KNOCK_QL=1`** (the corrected simulator for both: the control is judged in the same game). Every check reported; one under 40% flagged at once |
| Read at every check | games won by map; megas and reds head to head; the lightning in hand and in view by range, the rail owned (readouts, rule 12); both sides' hit rates by distance (the lightning comparison's measure); the keep choice's trips, targets reached and quiet re-decisions (1.7a's flicker); the head's and the hands' parts of the target sum (rule 11); frags a match-minute; the input health report |
| Kept file | `keep/policy_end_20d.pt` + `opt_end_20d.pt`; marks kept at 10, 30, 50, 70, 90 |

## The simulator correction (done today) ✅

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
speed, and then gave no friction for 50 ms. Now the kick is the game's and friction starts at once. One known difference stays: the game
moves the target in the hit frame, the simulator a frame later (every weapon, as before).

**What it changes in play:** a lightning stream pushes a target 1.4 times harder (about 1,000 u/s of push a second at full contact in
the air), and machine-gun fire 2.5 times. Both players are moved more by small hits, so tracking a pushed target is a little harder,
and being on the receiving end of the lightning is a bit more disruptive.

## What goes in

| # | Change | Kind | When |
|---|---|---|---|
| 1 | **The cleaned input list 18**: the dead columns cut and folded, the 72 rule-made columns out (pre-fire, emergence, rule belief, place flags, stack by rule), every input re-measured to its size, each network its own list by name, the yellows' timers the head's only | exact (`same`: 0 actions differ) | the start |
| 2 | **1.7a's combat order removed** (its kind, pointer, fire push; the brain's pass odds): never asked at update 90 (`CMB_G`, `PADD`, `FADD` 0) | exact | the start |
| 3 | The keep choice's share to 1 (the lock's last 2.5% out: rule 13) | not exact (2.5% of his seconds) | the start |
| 4 | **The corrected knockback** (`KNOCK_QL=1`) | the game's physics | the start (a switch, not live) |
| 5 | **Pay amounts**: damage 0.005 zero-sum (0.0055 dealt / 0.8 taken → 0.005 / 1.0; owner 11-11); the far-rail pay 0.25 → 0.1 (owner 11-12) | pay | the start, as a step (as 1.8a did) |
| 6 | **No weapon habits in the league** (`HABIT_P` 0.3 → 0; scrapped in 1.8a) | league | the start |
| 7 | **AIM3 at the 11-11 tuning**: `AIM3_W` 0 → 1, `AIM3_SIZE_A` 1 → 0.39, `AIM3_SIZE_B` 0 → 0.355, `AIM3_LEAD` 0 → 1, `AIM3_RELOAD` 1 → 0; `AIM3_FIX_TAU` 0.05 from the start | aim | ramp, updates 0 to 30 |
| 8 | **The head paid by the win chance only** (`--head2-pay win`; owner 11-11: "the head is paid by the win-chance pay only"); the hands keep the table and their win part (owner 11-12) | the head's value and credit | ❓ the start, or a restart at 40 (below) |
| 9 | **The head's part on the weapon key out** (1.5a's weapon scores, `wadd`; scrapped in 1.8a: switched off it read 100-100) | not exact: fade | updates 40 to 70, then held ⏳ (a live dial for `wadd`, as `PADD`) |

**Kept as update 90 has it:** the head's target choice and its credit (`H2_PG` 1, `H2_L2` on both parts of the sum), the keep choice
(learning), no firing cost, no item teacher, no speed pay, the switch cost out, the win part `WIN_ADD` 0.33, the item table, every
delay. The 10 "order" inputs of the hands (the look point of his chosen target; ❓ below).

**Saved for 2.1** (owner): the strategy inputs out of the hands to the head (`SFADE`), the head's new columns at its birth, the
instruction. **Not in this run:** the dodge inputs. They need building, their statistics measured, and a blank test at the end. In
the corrected simulator dodging also pays more (small hits now move a target as in the game), so they are a clean next step:
2.0e, or 2.1's first stage.

## The schedule (updates; every dial live and straight; nothing holds or steps back on its own)

| Updates | Dial | From → to | What | Mark kept |
|---|---|---|---|---|
| 0 | | | items 1-6 at the start; the start answers as update 90 under the old simulator (`same`) | start |
| 0 to 30 | `AIM3_W`, `AIM3_SIZE_A/B`, `AIM3_LEAD`, `AIM3_RELOAD` | as item 7 | AIM3 in | 10, 30 |
| 30 to 40 | | held | AIM3, the kick and the pay read at their end values | |
| 40 | ❓ restart at the save of update 40 with `--head2-pay win` (item 8) | | the head's value and credit to the win chance | 50 |
| 40 to 70 | `WADD` (⏳) | 1 → 0 | the head's weapon-key part out | 70 |
| 70 to 90 | | held | the end | 90 = the end |

If item 8 goes in at the start instead, there is no restart and the schedule is otherwise the same.

## ❓ Decisions for the owner

1. **The length**: 90 (as above), or anywhere in 80 to 100.
2. **The head's pay to win-only (item 8): at the start, or at a restart at update 40?** `--head2-pay` is not a live switch. At the
   start it is one more change in the first ten updates. At 40 it comes after AIM3 settles and is read on its own, at the cost of a
   planned restart (stop right after the save, `--fade-start`, as 1.8a's restart at 150). My recommendation is 40.
3. **The hands' 10 "order" inputs** (the look point of his chosen target). List 18 cut them as dead, and in 1.8a (no combat order)
   they were. **In 1.7a they are not dead:** with `COMBAT=1` they carry his target's look point, and update 90 reads them a little
   (their weights about 8% of an ordinary input's). That is the head's target passed to the hands, which is the by-role way. Keep
   them (my recommendation, exact) or cut them (not exact).
4. **The keep choice: learning, or frozen?** 1.7a's flicker grew while it trained on (trips 58 → 81 a player-minute after update 90).
   Frozen keeps that out of a run whose job is aim and clean-up. Learning lets it adapt to AIM3 and the new kick. My recommendation:
   learning, with its three numbers flagged at each check (trips over 70, reached under 9%, quiet re-decisions over 0.08).

## Red team: what is hand-built or assumed, its measured alternative, the pathology checks

| Part | Assumed | The alternative, and what is known | Watch |
|---|---|---|---|
| 2.0c's fall (update 90 + AIM3 + damage 0.002: 35.5 / 39.5% at 50 / 90) | blamed on the damage pay | AIM3 itself costs him under 1.7a's head | the checks at 10 and 30, before anything else opens |
| Several changes at the start (the cut, the kick, the pay step, no habits, the keep share) | each small or exact | one at a time over more updates | the check at 10; if it falls, the start's level check takes them one by one |
| The damage pay as a step at the start | 1.8a did it so | a ramp | the ledger: damage dealt and taken a player-minute cancel |
| The corrected kick from update 0 | the game's value, both seats | a ramp (not possible: a switch) | the lightning's hit rate by distance, both sides |
| The kick's frame order (the game moves the target in the hit frame, the simulator a frame later) | small, every weapon alike | a change to the step's order (large, risky) | none |
| The conversion of a network with a head | ⏳ `inputs18.py` refuses one today | 1.8a added its head after the cut | `same`: 0 actions differ, twice |
| The head's pay at 40, by a restart | the value relearns its target | at the start | the head's value loss, its credit, the checks at 50 and 70 |
| `WADD` faded over 30 updates | the weapon key's other part takes over | cut at once (1.8a's off test read 100-100) | the weapon by range, switches a minute |
| No learning-rate-zero warm-up after the surgery ([BOTS.md](../../../research/BOTS.md), OpenAI Five) | the converter carries the optimizer's moments, rescaled | a few updates at learning rate 0 | the KL of updates 1 to 5 |
| Pay pathologies (the ledger) | | | negative frags, sign flips, lopsided games |

## Research check (hard rule 14; `docs/research/README.md`)

1. **The game.** The change touches the knockback of the lightning, the machine guns and the shotgun (MECHANICS.md 1.2, 7.1): now
   measured and fixed (above). AIM3's parameters are the pros' measured aim (AIM3.md; MECHANICS.md 5.3). Still off the game and
   untouched here: the hit cylinder against our box, players passing through each other, the shotgun's fixed rings, the
   footstep rule, fall-damage modifiers (MECHANICS.md 7.1). None is changed by this run; the box makes every weapon a little easier to
   hit with, the lightning included.
2. **What wins.** Zero-sum damage serves "avoid damage as much as you deal it" (DUEL_STRATEGY.md, principle 15): taking a hit now
   costs what dealing one pays. The head paid by win chance alone serves "die less" and "the stack decides" (README core 1-2)
   rather than damage. Nothing here works against a principle; the far-rail pay at 0.1 is a small shaping pay (rule: kept by the
   owner).
3. **The player's view.** No input is added. The cut removes only columns that are dead or that nothing reads; what a person
   perceives is unchanged.
4. **In and out of control.** The pay changes are symmetric. Zero-sum damage makes the out-of-control player's "damage at his
   pickups and leave" (principle 6) pay the same as the controller's damage: no new exploit. No pay for places or items changes.
5. **Self-play equilibrium.** Under AIM3 the far rail lands more (his far sight back) and his close lightning a little less (AIM3.md
   section 9); the corrected kick pushes a lightning target harder. Both move the equilibrium slightly away from the lightning at
   range. The league still holds only his own copies (BOTS.md: GT Sophy's lesson: self-play alone leaves him unready for people
   who move differently). This run does not fix that; the dodge inputs and a varied league are the levers after it.
6. **Bot precedent.** OpenAI Five's surgery rules (BOTS.md section 3): the same surgery on the league's snapshots (the converter does
   the league's files too) and a learning-rate-zero warm-up (not planned: red team). AlphaStar: the control in the checks.
7. **Rule 12.** No pro outcome is a target. AIM3's parameters are the pros' measured limits; the lightning and rail numbers are
   readouts only.

## Before the go

| # | What | State |
|---|---|---|
| 1 | The decisions above | ❓ |
| 2 | `KNOCK_QL` built and tested (weaponlab set 6 replayed; off = bit-identical) | ✅ 2026-11-13 |
| 3 | `tools/inputs18.py` for a network that has the head and the keep choice, and the combat order's removal; `same` on update 90 twice; the league's files the same way | ⏳ |
| 4 | A live `WADD` (the head's weapon-key add), with its range and a `tests.py live` test | ⏳ |
| 5 | The run's files (`make_files.py`, `train.cmd`, `start.ps1`, `ramp_20d.py`, `start_live.py`, `stop_20d.ps1`, `tests.py`); the settings check against 1.7a's command; `live_accept` on every file the ramp writes; the ramp's flag thread tested on a real record (1.9a's crash) | ⏳ |
| 6 | Tests: start (`same`), ident (everything at update 90's values = 1.7a's trainer), live, smoke; a two-update trial at full size | ⏳ |
| 7 | The input health report on the converted start | ⏳ |
| 8 | The owner's go and the length | |

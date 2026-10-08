# BobbyBones: results log

What we tried, what we measured, and what it means, **including what did not work**. Newest first. Each
entry names the backlog items it settles or raises ([BACKLOG.md](BACKLOG.md), `B-nn`); the plan is in
[PLAN.md](PLAN.md); log formats are in [LOGS.md](LOGS.md). Numbers are from local runs; raw data lives in
the git-ignored `data/` folder (paths given so results can be re-checked).

## 2026-10-08 13:15 — The aim audit, aim ability as one knob, the Nightmare stand-in, honest item state (owner: "human good, not bot good"; "on par or slightly above me, 10% over or so ... a knob")

**Aim in real games** (free-for-all logs; people 19 minutes alive, thin; `scratchpad/aim_logs.py`):

| | People | Bobby v10 | Bobby v8 |
|---|---|---|---|
| First shot after an enemy appears (median) | 0.50 s | 0.20 s | 0.20 s |
| Crosshair on him after (median) | 0.50 s | 0.30 s | 0.25 s |
| Firing, share of the time an enemy is in view | 24% | 53% | 62% |
| Crosshair within 3 deg / 10 deg while in view | 15 / 45% | 40 / 75% | 47 / 78% |
| Aim error while firing (median, third quartile) | 5.4, 13.3 deg | 3.1, 5.6 | 2.5, 5.1 |

He is "bot good" in four ways: he notices and shoots at once, he keeps the trigger down, he is locked on whoever is in
view, and being hit hardly shakes him (reflex room: he kept 78% of his tracking under fire, the owner 51%). His single
shots are below the owner's (first rail shot 60 to 70% against 88%, rockets that hurt 36 to 47% against 83%), and last
night's cut (perception 1.2 deg, slow) cost those ten points each while hardly touching the tracking; three seeds a
setting showed the perception settings alone cannot change that shape.
**The knob** (`AIM_LEVEL` 1 to 5 in `sim/duel_env.py`, 3 by default; each level 1.25 times the errors and delays of the
next; `AIM_PRESET=v12|v10` for old networks): level 3 = perception 0.6 deg quick (as before the cut), tracking delay
100 ms (75), flinch 0.25 deg a point up to 6 deg fading over 0.5 s (0.12, 3, 0.3), up to 200 ms more before an enemy who
turns up off the crosshair unexpected is noticed (`SURPRISE_MS`, new; in the simulator, the group generator and both
plugins). Reflex room, v12's weights before adapting, three seeds:

| | Owner | Level 2 | Level 3 | Level 4 |
|---|---|---|---|---|
| Tracking: time on target | 40.1% | 41.9% | 44.8% | 54.1% |
| Lightning damage a second | 57.7 | 62.2 | 65.8 | 77.9 |
| On a jumping target after | 350 ms | 347 | 348 | 314 |
| First rail shot | 87.5% | 60.7% | 68.4% | 79.5% |
| Rockets that hurt | 83.3% | 36.3% | 38.0% | 36.1% |
| Under fire: time on target / lightning damage | 20.4% / 35.7 | 24.5% / 36.7 | 27.9% / 42.2 | 34.1% / 50.5 |
| Under fire: first rail shot | 62.5% | 16.5% | 35.0% | 46.3% |

Level 3 is the owner plus 12% on tracking and level with him on reaction; under fire still above him; rail and rockets
are a matter of practice, not of limits (to come back as rooms in training). Open (the owner's call, a reward): a cost per shot.
**Nightmare stand-in** (`PERSONAS[8]`, `tools/duel_eval.py`; checks only): the scripted item runner with the weapons
the game's bot was logged to fire and little jumping. First calibration (32 five-minute games, each network under the
limits it trained with), score a game: v11 2.4 : 9.5 on arena1 (real, per 10 min: about 6 : 25), v10 7.4 : 9.8 (real 22 : 28):
the ratios match without tuning (0.25 against 0.26; 0.76 against 0.79). On the duel maps it has nothing valid to be set
against yet (the entry below).
**Honest item state** (`ITEM_BELIEF`, off by default; B-125): the item rule and the inputs about his chosen item go by
what he knows. Test (an obeying pupil, 2,400 frames): of the goal-frames with the item truly gone he still thinks it
there in 13 to 16% (taken out of earshot, place not seen since); never the other way round. The two-player simulator is
unchanged with it on or off.
**The pros' positions** (`tools/pro_positions.py`, `sim/pro_positions/`): in the scorecard. v12 on Blood Run at 5.5 h
(general lives, small sample): overlap 0.54; 83% of his time on the ground that holds 90% of theirs.

## 2026-10-08 13:00 — A fault in the real-game control, found and fixed: on a busy PC the bot's commands were dropped (and the duel-map Nightmare numbers were wrong)

Found while setting the Nightmare stand-in against the real scores. In the sparring games on Blood Run and Aerowalk
(four each, last night) Bobby **stood still 37 to 39% of his time alive**, a movement key down in 76 to 88% of it, in
spells of up to 45 s at a few places; his view was *exactly* unchanged in 52% of the frames. On arena1: 12% standing,
no spell over a second. In the simulator the same network stands 10 to 11% and next to never for 3 s; in the
free-for-all games on the public server there is no such spell either.
**Cause** (`DUEL_AIMDUMP`, a frame-by-frame record of what became of his mouse output): in the frozen frames the game had
run no new command for him. His input rode on the game AI's own command, which the engine issues once per server
loop: one frame late always, and not at all in the extra game frames a server runs to catch up when it falls behind. In
those frames the game replayed his last command. The sparring games ran beside a training that held every core (two
containers at once for the duel maps), so the servers were behind half of the time.
**Fix** (`minqlx/botctl.c`, `hooks.c`): a bot under full control is commanded by us once per game frame, right after the
plugins have set that frame's input (`Botctl_BeforeFrame`); the game AI's command for him is not run. Same game, same
load, after the fix: one command every 25 ms in 6,992 of 6,999 frames, standing 11% (no spell over 3 s), mean speed 238
(140 to 194 before), score 1-5 with more damage dealt than taken (694 : 566). It also takes the hidden frame of delay
out of his aim on every server.
**What this changes in earlier entries:** every Nightmare score on Blood Run and Aerowalk measured beside a training (all of
v11's; v12's so far none) is void, and v11's arena1 scores (measured the same way, a quarter of the frames unchanged) are
too low by an unknown amount. v10's final 22-28 was measured after its training had ended. The audit's line that he
scores next to nothing on the duel maps rested on these numbers. Rule from now on: real-server checks run only when no
training is running, or are read with the share of unchanged frames beside them.

## 2026-10-08 — Audit of the model, the training pipeline, the plans and the results (owner's request)

Checked in the code and the logs, not from memory. **Verified:**

1. **The learning rate has been a tenth of its setting since v8.** `--lr-minutes 1440` (v8 on) decays it to a tenth over
   the *cumulative* minutes of the lineage, which stood at 2,163 when it was introduced: every update of v8 to v12 (about
   40 hours: the intention, the map reader, items, the stack pay, the styles) ran at 2.5e-5, not 2.5e-4. Seeds (large
   supervised gradients) still moved him within an hour; reward-only changes did not, and "a reward alone does nothing"
   (v9, v11) was measured under this handicap. No measure of the policy's step (KL, clip fraction) is logged.
2. **Credit reaches half a second.** The advantage estimate uses lambda 0.95 at 40 decisions a second: about 20 frames;
   everything later rests on the value estimate. A walk to a weapon is 3 to 10 s, the fight it decides later still.
3. **Trading damage pays both sides.** +0.005 a point dealt, -0.0025 a point taken (`--dmg-taken-w 0.5`, set to stop
   two players avoiding each other on Blood Run): an even exchange at v12's 347 damage a minute pays each about +0.9 a
   minute, the size of the whole stack pay. Fighting is subsidized; fetching competes with it.
4. **One respawn in five is put in front of an enemy** (`close_p` floor 0.2: 300 to 700 units away, in line of sight,
   facing him), the opposite of "a weapon first": with machine-gun spawns that life starts in a fight he should avoid.
5. **The intention is the item rule.** Its teacher has weight 2.0 and never fades; the goal he names is the rule's by
   imitation (loss 0.01 to 0.03), so the rule's quality is his item play. In v12 30% of his trips arrive.
6. **A fairness gap:** the intention inputs "chosen item is up / comes back in" give the true state of whichever item he
   names, seen or not (the item rule uses it too). The other item inputs are honest (up only while seen; mega and red
   by what he took or heard). The owner turned item timers off for people.
7. **The checks are thin and uncontrolled.** Nightmare on a duel map is one five-minute game (v10 0-10 and 0-0, v11 1-4 and
   0-6: he scores next to nothing there, at 137 to 187 units a second where the pros average 285 to 300); the training
   numbers pool four maps and all round kinds; no run had a control arm and each changed five to ten things.
8. Smaller: teacher fades count from the start of the process (a restart resets them); a run does not pin the simulator
   module it was started with; the first pro-route tables took the step most often taken, which for armors includes
   waiting for them (armor pickups fell on all three maps in the pupil test; rebuilt from the pros' fastest trips).

**Sound, keep:** the inputs' honesty and the human limits, the intention with the way's next step, keys-only teachers,
the move to the duel maps (pros have the enemy in view 10 to 15% of the time; he was raised in an arena at 40 to 50%), the
pro tables and the scorecard beside them. Not a bug: the public server and the benchmark do have the walking graphs and
map-reader tables for all four maps.
**Proposed** (BACKLOG B-123 to B-130): a side-by-side test of the learning rate before v13 (two half-size arms from v12's
weights, three hours), with the policy step logged; close spawns off; the intention inputs by what he knows; per-map
numbers and a fixed set of opponents in the simulator with many games; then, each with its own control arm, a longer
credit horizon and even damage trading; a goal model learned from the pros' next pickups in place of the two-line item
rule; positions against the pros' on the duel maps; no further aim cuts until the game's own accuracy counts say so.

## 2026-10-08 — Pre-work for `duel_gru_v13`, the seeding experiment (owner: "do the pre-work now"; nothing started)

Built while v12 trains, every switch off by default, the two-player simulator unchanged with them off:

- **Seeds** (`sim/duel_env.py`): `PRO_WEAPON` (the weapon teacher names the pros' first choice for the distance among the
  big weapons he owns, per map from `sim/pro_seed.json`; within 10 points of it is left alone), `PRO_ITEMS` (the item rule
  in the pros' order: bare, the nearest big weapon, rockets when within 1.5 s of the nearest; armed, the nearest of yellow
  armor, red armor and mega he can still use), `SPAWN_TEACH` (the keys-only walking teacher also with an enemy in view
  while he has no big weapon). The **yellow armors are intentions** now (up to two a map): 491 inputs, the intention
  output 6 -> 8; `sim/reshape_policy.py` can grow the last head. `sim/duel_env_v12.py` / `duel_env_ffa_v12.py` are the
  frozen 487-input simulator of v12 (`ENVMOD=duel_env_ffa_v12 REFLEX_ENV=duel_env_v12` for its checks).
- **Tests**: a pupil who obeys the teacher's keys with a fixed view on Blood Run picks up 2.5 weapons and 2.1 armors a
  player-minute and is bare 74% of the time (random play: 0.1 weapons, 99%); the item rule names a weapon in every bare
  frame and armor or mega in every armed one; a two-minute trainer run on the three duel maps with all seeds on from a
  v12 checkpoint carried to the new shape ran clean (he already names the yellow armors in a third of his intentions).
- **Measuring** (`tools/stack_probe.py`): the scorecard per map beside the pros' numbers, with machine-gun spawns. First
  look at v12 (2.5 h in, general lives, small samples): Blood Run time bare 64% (pros 6%), first weapon after 21 s (2.3),
  150 or more 40% (62%), the pros' weapon for the distance in 37% of the frames; arena1 time bare 94%.
- **People's positions** (`tools/position_overlap.py`): 7 sessions, 27 minutes of people alive on arena1 so far (thin).
  v12 against them: overlap 0.48; 74% of his time is in the cells that hold 90% of people's, 53% of theirs in his.
- **The style split recounted by time in hand** (enemy in view, owning all three; `docs/pro_styles_in_hand.json`): rockets
  42 / 40%, lightning 34 / 36%, rail 24 / 24% (Blood Run / Aerowalk). The rail is held a quarter of the time by everybody;
  it is the most-held weapon in 9-10% of games (rockets 51-57%, lightning 34-39%). The earlier "1%" counted firing frames.
- Launcher and weight carry-over are written (`start_v13.py`, `prep_v13.py` in the scratchpad), not run.
- **The pros' ways** (`PRO_ROUTES`, `tools/pro_routes.py` -> `sim/pro_routes/<map>.npz`; off by default): 4,000 to 10,000
  trips an item and map; a pro step on a quarter to two thirds of each map; 230 places on Aerowalk from which the walking
  graph has no way to the red armor now have one. **What did not work: they do not pass the test set for them.** A pupil
  who obeys the teacher's keys (fixed view, walking; three seeds, 120 to 144 lives a setting), shortest ways against the
  pros': first weapon after 5.9 / 6.2 s on Blood Run, 12.0 / 12.5 s on Aerowalk, 25.5 / 25.0 s on Lost World; weapons
  picked up 5 to 19% fewer with the pros' ways on every map. (The first tables, the step most often taken, looked better
  on Aerowalk in one small sample and halved the armor pickups: trips to an armor include waiting for it; the tables are
  now built from the pros' fastest trips.) Reading: for a walker the shortest way cannot be beaten; what the pros' ways
  could add (speed with their movement, safer ground, looking like a player) this test does not measure. Not in v13
  unless the owner wants them in as they are; to be tried as a single change with a control arm.

## 2026-10-08 07:31 — `duel_gru_v12`: playing styles and a machine-gun spawn in every life (owner's idea; until 14:00) (B-120, B-116)

From v11's final weights (4,338 min) carried to 487 inputs. Every life is general or has a preferred weapon (rockets,
rail, lightning; a quarter each): the item rule sends him for it first, the weapon teacher names it at every distance
(weight 1.0 fading over 240 min), damage with it pays half as much again, and half a frag a minute inside its band with
it in hand. Every life starts with the machine gun only (`ARENA_SETS=mg`, `--loadout-p 0,1,0,0`, no random stacks).
Keys-only walking teacher 0.5 fading over 180 min; stack pay 1.0 / 1.0 / 0.5 / 1.0; fire button 2.9 clicks a second
(owner: "up the clicks to 3"); the rest as v11. Brief hourly lines, the full check at the end (owner).

| | Time bare | Big weapons held | Weapons picked up a player-minute | His weapon in hand (rockets / rail / lightning lives) | Big weapons held, general / preferred lives | Fire, frags a match-minute |
|---|---|---|---|---|---|---|
| 07:50 (update 10) | 80% | 0.24 | 1.88 | - | - | 25%, 3.7 |
| 08:35 | 70% | 0.37 | 1.94 | 10 / 17 / 22% | 0.24 / 0.36-0.48 | 23%, 3.6 |
| 09:35 | 61% | 0.47 | 2.19 | 26 / 30 / 45% | 0.25 / 0.47-0.69 | 22%, 3.6 |
| 10:35 (walking teacher at zero) | 58% | 0.51 | 2.31 | 33 / 34 / 52% | 0.26 / 0.52-0.76 | 22%, 3.6 |
| 11:05 | 56% | 0.54 | 2.37 | 37 / 36 / 54% | 0.25 / 0.55-0.79 | 22%, 3.7 |
| 12:05 (both teachers at zero) | 54% | 0.56 | 2.45 | 41 / 40 / 58% | 0.27 / 0.57-0.80 | 22%, 3.8 |
| 13:00 | 54% | 0.57 | 2.49 | 43 / 40 / 59% | 0.26 / 0.57-0.82 | 21%, 3.9 |

## 2026-10-08 — Tables from the pro demos, to seed the teachers with (owner: "weapon preference, style, intention can and should be tuned on the pro demos")

`tools/pro_tables.py` -> `docs/pro_tables.json`, from the light sets of `sim/demo_dataset.py --lite` (new: only the facts
counted, ten minutes a map on three cores): **3,266 1v1 demos, 505 hours of play** on Blood Run (1,066), Aerowalk (978) and
Lost World (1,222; no railgun on that map). No player names in the sets, so "per demo" is one game of one player.

| | Blood Run | Aerowalk | Lost World | All |
|---|---|---|---|---|
| Fired, owning all three: rockets / lightning / rail under 300 units | 63 / 32 / 6% | 48 / 44 / 8% | - | 54 / 39 / 7% |
| ... at 400-600 | 32 / 54 / 14% | 31 / 49 / 19% | - | 31 / 52 / 17% |
| ... at 700-800 | 20 / 40 / 40% | 23 / 29 / 48% | - | 22 / 35 / 44% |
| ... beyond 900 | 12 / 3 / 84% | 16 / 3 / 81% | - | 14 / 3 / 83% |
| Distance of his fights, quartiles: rockets | 233 / 363 / 537 | 232 / 352 / 522 | 228 / 355 / 550 | 230 / 356 / 537 |
| ... lightning | 318 / 474 / 597 | 253 / 392 / 554 | 362 / 542 / 664 | 305 / 478 / 617 |
| ... rail | 501 / 680 / 875 | 398 / 591 / 766 | - | 439 / 629 / 815 |
| Games leaning (over half the firing) to rockets / lightning / rail / none | 25 / 26 / 1 / 49% | 17 / 31 / 1 / 51% | - | 21 / 28 / 1 / 50% |
| Fight distance in those games (median) | 453 / 464 / 516 | 394 / 400 / 426 | - | 429 / 431 / 480 |
| A big weapon in this share of lives; after (median, third quartile) | 84%; 2.3, 5.2 s | 89%; 1.8, 3.7 s | 72%; 4.9, 10.7 s | 82%; 2.7, 5.3 s |
| The first one: rockets / lightning / rail | 50 / 28 / 22% | 51 / 19 / 30% | 55 / 45 / - | 52 / 28 / 20% |
| Time alive without a big weapon | 6% | 7% | 11% | 8% (Bobby v11: 57%) |
| Next pickup with no big weapon: a weapon / yellow / red / mega | 69 / 22 / 5 / 4% | 86 / 8 / 2 / 4% | 56 / 30 / 7 / 8% | 73 / 18 / 4 / 5% |
| Next pickup once armed: a weapon / yellow / red / mega | 20 / 38 / 24 / 17% | 36 / 20 / 24 / 20% | 10 / 45 / 28 / 18% | 23 / 33 / 25 / 19% |
| Health plus armor: under 100 / 150 or more | 15 / 61% | 28 / 42% | 15 / 62% | 19 / 56% |
| Enemy in view, firing: no big weapon / three | 9, 16% / 14, 36% | 10, 17% / 15, 43% | 10, 13% / 15, 32% (two) | 10, 15% / 15, 40% |
| Closing speed with rockets / lightning / rail in hand (units/s, + = closes) | -34 / +7 / +40 | -31 / +13 / +38 | -14 / +7 / - | -26 / +9 / +39 |

What holds on every map: rockets close and lightning in the middle, the rail from about 750; half of the games lean to
rockets or lightning and almost none to the rail; the fight distance barely follows the leaning; a weapon within about
3 s of a spawn, rockets first in half of the lives; bare, he fetches a weapon and avoids the fight; armed, he takes armor
(the yellow most of all, which is not among Bobby's intentions); with rockets he gives ground, with the rail he closes.
Our settings against it: the weapon rule (rockets 60-300, lightning to 700, rail from 500) is too short for rockets and
too early for the rail; the item rule puts mega and red before a weapon; the style bands are narrower than the pros'.

## 2026-10-07 20:35 — `duel_gru_v11`: a pay for keeping a stack, fewer fire clicks, softer hitscan aim, a weapon teacher, items in fights (owner's list, approved; until 06:30)

From v10's weights (3,817 min). Four maps, groups 2,3,2,4,2, 10,080 players, 64 minibatches, GPU 10.5 GB. Changes, as in
[PLAN.md](PLAN.md):

1. **Stack pay** (frags a minute, every frame of a normal game): health above 100 and armor up to +0.5; rockets, lightning,
   rail up to +0.5; none of the three: 0 at the spawn, -0.25 after 5 s, to -1.0 after 20 s; health plus armor under 70: to -0.5 at zero.
2. **Fire button**: a change at most every 200 ms (2.5 clicks a second; was five).
3. **Hitscan aim one click down**: perception error 1.2 deg (0.6), lingering 0.5 s (0.15), plus 0.012 deg per deg/s of the
   enemy's motion across the view (at most 3). Reaction unchanged.
4. **Weapon teacher** on the weapon key, weight 1.0 fading to nothing over six hours (a seed; after that results decide):
   rockets 60 to 300 units, lightning to 700, rail from 500; lightning in hand up to 700 or rail in hand from 300 is left alone.
5. **Rocket drills** 15%, seven in ten with the machine gun too.
6. **Item runs** 20% without the walking teacher; half become a fight after 20 s (stacked against fresh spawns).
7. **Intention** held 8 s, released when the item is taken; three workers in five play 1v1.

The first updates are a start-up artifact (every seat begins the first round with its drawn weapons at once: big weapons
held 2.34, bare 8%); the steady state is reached after about ten updates. Hourly, from the training log and, at the odd
hours, the measured check (`chk11_HH05.txt`):

| | v10 end | 21:40 (1 h) | 23:40 (3 h) | 03:45 (narrowed teacher, 2 h) | 05:45 (teachers at zero, 1.5 h) |
|---|---|---|---|---|---|
| Stack: above 100 (0 to 1), big weapons held, time bare, time under 70 | - | 0.16, 0.54, 59%, 28% | 0.15, 0.54, 60%, 28% | 0.18, 0.62, 56%, 24% | 0.17, 0.61, 57%, 25% |
| Weapon rule agreement (teacher weight) | 0.61 | 0.85 (0.82) | 0.91 (0.49) | 0.90 (0) | 0.87 (0) |
| Frag share rockets / rail / lightning / machine gun | 4 / 17 / 20 / 52% | 13 / 9 / 13 / 63% | 16 / 6 / 12 / 66% | 20 / 9 / 15 / 57% | 18 / 12 / 15 / 54% |
| Hit rate rail / lightning / machine gun / rockets | 57 / 45 / 50 / 38% | 44 / 43 / 42 / 53% | 41 / 43 / 42 / 54% | 36 / 40 / 39 / 55% | 39 / 38 / 40 / 52% |
| Pickups a player-minute: mega, red, weapons | 0.34, 0.35, 1.84 | 0.26, 0.28, 1.40 | 0.27, 0.30, 1.44 | 0.34, 0.38, 1.59 | 0.35, 0.39, 1.64 |
| Collect-then-fight: kills by the stacked : by the fresh | - | 130 : 120 | 1329 : 1268 (last 8 updates) | 778 : 667 | 1042 : 914 |
| Item-run arrivals a player-minute | 4 | 3.8 | 4.1 | 4.4 | 4.5 |
| Nightmare arena1 / Blood Run / Aerowalk (at 20 min) | 22-28 / 0-10 / 0-0 | 8-22 / 0-7 / 0-6 | 6-22 / 0-4 / 0-7 | 7-29 / 0-7 / 0-6 | 4-25 / 1-4 / 0-6 |
| arena1 fight check: mega, red a player-minute | 0.01, 0.02 | 0.04, 0.01 | 0.08, 0.02 | 0.12, 0.03 | 0.12, 0.04 |
| Solo test arena1: mega / red / RL / RG / LG | 69 / 97 / 100 / 100 / 100% | 75 / 94 / 97 / 100 / 100% | 69 / 94 / 100 / 100 / 100% | 75 / 94 / 100 / 100 / 100% | 75 / 94 / 100 / 100 / 100% |
| Reflex room: aim error, time on target, lightning damage a second, first rail shot | 3.0 deg, 58%, 83, 74% | 4.6 deg, 52%, 76, 55% | 4.4 deg, 51%, 74, 48% | 3.5 deg, 47%, 69, 64% | 3.7 deg, 48%, 70, 49% |

At one hour: the aim limits bite as measured beforehand (rail and machine gun hit rates down 13 and 8 points); rockets
went from 4% to 13% of frags and hit more; he follows the weapon table. Nightmare on arena1 fell from 22-28 to 8-22 twenty
minutes in (softer aim, fewer clicks, not yet adapted). The stack numbers have not moved yet. The stacked side of the
collect-then-fight rounds does not win more than the fresh side (130 : 120): a stack is not yet worth anything to him.

At three hours nothing about the stack has moved (bare 60%, big weapons 0.54, the stacked side of the collect-then-fight
rounds no better than the fresh one), and Nightmare on arena1 has not come back (6-22). Rockets 16% of frags.

**00:39, the hour-four fallback applied** (pre-approved). At four hours: time bare 58% (hour one 60%), health and armor above
100 0.152 (0.152), big weapons held 0.56 (0.54); fight check mega 0.08, red 0.02 a player-minute. All three conditions
held, so the run was restarted from the 00:37 checkpoint (kept as `policy_before_fallback.pt`, 4,058 min) with the four
stack sizes doubled (1.0, 1.0, 0.5, 1.0) and the walking teacher inside normal games (`STACK_TEACH=1`, `--teach 1.0`
fading over 180 min); the weapon teacher continues at 0.33 over its remaining 115 min. First updates: 20% of the frames
of normal games carry the teacher's labels, teacher loss 3.2. Unchanged at four hours otherwise: rockets 17% of frags,
weapon rule agreement 0.91.

**01:47, what did not work: the fallback as first applied.** In one hour the stack numbers moved for the first time (time bare
58% -> 48%, big weapons held 0.56 -> 0.84, above 100 0.15 -> 0.24; arena1 fight check mega 0.26, red 0.21 a player-minute,
from 0.08 and 0.02) and he all but stopped fighting: fire on 7% of the frames (31%), 1.1 frags a match-minute (4.8), enemy
in view 23% of the time (49%), machine-gun hits 29% (42%), 0.25 frags a minute against the scripted players (1.28), more
suicides than frags, Nightmare on arena1 2-31. Fire fell to 14% within three updates, too fast for a reward: the teacher
did it. It labelled the view as well as the keys (the turn head, his mouse) on nearly half of all frames of normal games, at
weight 1.0 with a loss of 3. Restarted from `policy_before_fallback.pt` (the damaged weights kept as `policy_fallback1.pt`)
with the teacher narrowed: keys only (no label for the view; the trainer now masks each head by its own label), only after
1.5 s without seeing or hearing an enemy, weight 0.5 fading over 150 min. Stack sizes stay doubled. If fire and frags fall
again, the run goes back to the settings of 20:35.

03:45, two hours of the narrowed teacher (weight now 0.1): he still fights (fire 25% of frames, 3.4 frags a match-minute against 4.8
before), pickups are up a quarter (mega 0.34, red 0.38, weapons 1.59 a player-minute), the stacked side of the
collect-then-fight rounds wins a little more often (1.17 : 1, was 1.12 : 1), rockets 20% of frags. In the arena1 fight check
mega 0.12 and red 0.03 a player-minute: small. Nightmare on arena1 7-29.

**06:29, the end** (4,338 min; `policy_end_v11.pt`). Last eight updates: rockets 18% of frags (v10 4%) with both teachers at
zero for over two hours, weapon rule agreement 0.83 and slowly falling, fire 28% of frames, 4.3 frags a match-minute, time
bare 57%, big weapons held 0.61, pickups mega 0.34 red 0.41 weapons 1.64 a player-minute, stacked side 1.18 : 1.
**Worked:** rockets and weapon choice by distance, and they hold without the teacher; the fire-click limit; the aim limits
bite as measured (3.7 deg, 48% on target, first rail shot 49%). **Did not work:** the stack pay alone (nothing in four
hours); the first fallback (above); the narrowed teacher moved pickups by a quarter and time bare by two points; in the
arena1 fight check he takes 0.12 megas and 0.04 red armors a player-minute and almost never the rocket launcher (0.01;
rail 0.53), so his rockets come from the spawns and drills that hand him one. **Nightmare on arena1 4-25 (v10: 22-28)**:
softer aim, fewer clicks, and still the machine gun 78% of the time there. The item problem is not solved.

Built for the fallback (off, `STACK_TEACH`): the walking teacher inside normal games, while bare or under 70 with nobody
in view, toward what the item rule names. Test on arena1 with machine-gun spawns, 12 player-minutes, random aim: a pupil
who obeys the labels takes 12 weapons and 9 red armors and is bare 67% of the time; one who ignores them 2, 0 and 91%.

## 2026-10-07 20:00 — The owner's game against v10 on the public server (arena1, 10 minutes, him and two Bobbys), and a reward for keeping a stack

Score 61 : 10 : 10 (damage 8,594 : 2,835 : 2,701). Session `20261008-005506_arena1_ffa`; `tools/player_card.py --games`:

| | Owner | v10 (two bots) |
|---|---|---|
| Mega, red armor taken (share of spawns) | 12, 15 (70%, 54%) | 0, 0 |
| Big weapons picked up a minute | 6.5 | 0.8 |
| First big weapon after a spawn | 4.3 s | 8.1 s, in one life of nine |
| Weapon in hand | rockets 42%, rail 40%, MG 9%, lightning 8% | MG 97% |
| Shots fired | lightning 44%, rockets 24%, rail 16%, MG 14% | MG 98% |
| The game's own accuracy | lightning 43%, rockets 50%, MG 27% | MG 23%, lightning 25% |
| Aim error while firing | 4.9 deg | 3.1 deg |

What did not work: v10 learned to walk to an item alone and takes none in a game against a person. With MG spawns he
fights every life with the machine gun.

The owner's read: "good players know to maintain stack; bad players spawn and immediately start fighting ... he isn't
picking it up through self play, so we have to enforce it." Built (off by default, `STACK_PAY`, `STACK_WPN`, `STACK_BARE`,
`STACK_LOW` in `sim/duel_env.py`): a pay per second of a normal game for health above 100 and armor, and for the big
weapons he holds; a cost per second with none of the three, and with health and armor together under 50. Checked against
its own counts in groups of 2 and 4; the two-player simulator is unchanged with it off. New metric `stack`.
Owner's changes at 20:20: the bare cost grows with the time without a big weapon, the low cost starts at 70 (one rail shot) in
proportion to the shortfall; checked frame by frame. The fire button changes at most every 200 ms (2.5 clicks a second,
measured 2.25 when asked every frame; it was five). Public server: a game started with F3 was thrown back to warmup in the
same instant (the bots-only abort ran before the start was marked as the people's), so "Game on" showed while everybody
kept every weapon; no abort in the 30 s after a ready-up start now.
Also fixed: the player card gave a seat's events to whoever held it first (a bot in warmup, then the owner).

## 2026-10-07 — Public server: new name, `!map` limited to the trained maps (owner)

The server list name is now "doppz's bot arena | duel & FFA | chicago" (`tools/push_bobby.sh`; takes effect at the next `push_bobby.sh` restart, or live with rcon `set sv_hostname`). `!map` and `!maps` list only `testlab, arena1, bloodrun, aerowalk, lostworld, campgrounds, sinister, furiousheights` (the maps he has seen in training; `duelbot.MAPS` is shared with ffabot, `botmode.DUEL_MAPS` keeps a copy; `lockout` and the other pool maps are no longer pickable). Not yet tested on a server.

## 2026-10-07 13:28 — `duel_gru_v10`: he is shown the walk (the runner's keys as a fading teacher in item runs), item runs at 30% of the time (owner: "do it, items 1 and 2, start it now as v10")

**Why.** v9 ended at 13:27 (3,483 minutes, `duel_gru_v9/policy_end_v9.pt`). Its last 17 hours changed a great deal around him (a seeded intention, a claw-back, a scripted item runner, a scattering machine gun, smaller maps, item runs) and the item numbers did not move: alone on arena1 with the intention fixed he takes the item in 0 to 22% of 30-second rounds (09:15, 11:05, 13:05), and in item runs 0.10 to 0.17 targets a player-minute for three hours. He chooses the right item and cannot walk to it. The owner: "not showing anything new and starting to look like a waste of compute".

**What is new.**
- **The walking teacher** (`_run_teach` in `sim/duel_env.py`): in item runs every frame carries the keys the scripted runner would press from where he stands toward the target he was given (forward, strafe, jump, turn). The trainer's old teacher loss imitates them on the four movement heads (`--teach 0.5 --teach-minutes 180`: half weight, fading to nothing by 16:28). The same kind of seed as the intention head's. Measured before the launch, every seat pressing exactly the labelled keys: **7.8 targets a player-minute on arena1, 6.0 on Blood Run, 3.6 on Aerowalk (groups of 3), 3.2 on Lost World (groups of 4)** against his 0.15.
- **Item runs 30% of the playing time** (`ITEM_RUN_P=0.30`, was 0.10).
- Everything else as v9 at its end: its weights and league, arena1 / Aerowalk / Blood Run / Lost World, 10,080 players, the item runner in a quarter of the fight rounds, the scattering machine gun, the claw-back only on a trip given up, the item rule at weight 2, rocket drills 15%. Until 19:00.

**Stop rule (agreed with the owner).** Targets taken a player-minute in item runs: above 1.0 at the 15:05 check, it runs to 19:00; still under 0.5 at 17:05, the run is stopped early. To watch as well: the turn labels touch the head he aims with, in frames without an enemy; imitating the mouse at full weight broke his aim on 2026-10-04, so the hit rates are read every hour.

**Rule for the fade (agreed with the owner at 15:50, who had asked whether the teacher should stay longer).** The teacher fades to zero at 16:28 as planned, so that the 17:05 check says whether he keeps the walk by himself. If that check shows under 1.5 targets a player-minute in item runs, or the mega and the red armor no better than 41% and 53% in the solo test, the run is restarted at once with the teacher at a constant weight of 0.15 for the rest of it (`start_v10_keep.py`); otherwise it runs unaided to 19:00.

First four updates: teacher loss 4.36 -> 3.57, targets 0.05 -> 0.24 a player-minute, 36,600 steps a second, 10.5 GB.

| Time | Minutes | Item runs: targets a player-minute, teacher weight and loss | Solo test on arena1: mega / red / RL / RG / LG | Hits rail / LG / MG / rockets | Intentions mega / red, reached | vs Nightmare: arena1 10 min, Blood Run 5, Aerowalk 5 |
|---|---|---|---|---|---|---|
| 13:05 (v9's last) | 3457 | 0.15, none | 16 / 0 / 3 / 16 / 22 % | 61 / 47 / 51 / 36% | 31 / 49 %, 2.8% | 18-28, 1-10, 2-0 |
| 13:35 | 3490 | 0.24, 0.48, 3.57 | - | 57 / - / 49 / - (first rollouts) | - | - |
| 14:12 | 3527 | **2.05** (0.41 at 13:40, 0.80 at 13:47, 1.20 at 13:55, 1.58 at 14:04), 0.38, 2.56 | - (odd hours) | 59 / 46 / 51 / 36% (unchanged: the turn labels have not touched his aim) | 27 / 45 %, 8.9% (item runs count in it) | - . Void deaths 0.42 a player-minute (0.12 in v9): he now jumps the gaps and misses some |
| 15:05 (1 h 37; teacher weight 0.27) | 3572 | 2.3 to 2.9 (levelling near 2.5), 0.19 at 15:20, 2.0 | **41 / 53 / 94 / 100 / 100 %** (v9: 16 / 0 / 3 / 16 / 22); the weapons in about the walking graph's own time (4.1 to 4.3 s for a way of 3.0 to 3.2), the mega and red in 12 to 15 s for a way of 4 to 5; left to choose, alone, he takes the red armor in 38% of the rounds (0% in v9) | 59 / 46 / 51 / 37% | 27 / 45 %, 10 to 13% | arena1 **15-28** (damage 4290 : 2299; machine gun in hand 58%, rail 22%, lightning 9%: it was 82 / 5 / 3 in v9). Blood Run **1-9** (1149 : 925; lightning 14%), Aerowalk **1-9** (1431 : 1264; lightning 23%). In fights on arena1 from a normal spawn: mega 0.06, **red armor 0.01 a player-minute: the first one ever taken** (lying 99%). Void deaths 0.31, falling. Reflex 3.4 deg, rockets that hurt 44% |
| 16:08 (teacher weight 0.06, zero at 16:28) | 3643 | 2.7 to 3.4 (still rising as the teacher goes), 0.06, 2.0 | - (odd hours) | 57 / 45 / 49 / 38% | 25 / 44 %, 13 to 15% | - . Rockets 4% of his frags (1 to 2% in v9). Mega 0.26, red 0.34 a player-minute in training. Void deaths 0.29 to 0.43 |
| 17:05 (**the teacher at zero since 16:28**) | 3692 | **3.7 to 4.4** (mean of the last five 4.1; 3.4 when the teacher ended): he kept the walk and went on improving | **75 / 88 / 100 / 100 / 100 %** (15:05: 41 / 53 / 94 / 100 / 100); mega in 11.4 s for a way of 3.5, red in 9.6 for 5.5, the weapons in 3.0 to 6.9 for 2.8 to 4.4; alone and free he takes the red armor in 78% of the rounds (38%) | 57 / 46 / 50 / 36% | - , 15 to 17% | arena1 **13-27** (3909 : 2521; machine gun 80%, rail 9%), Blood Run **1-7** (975 : 943), Aerowalk **0-10** (1154 : 982). In fights on arena1 from a normal spawn: mega 0.03, red armor 0.02 a player-minute (2 in 96 minutes). In training mega 0.34, red 0.31 (lying 64%, 68% of the time; 71%, 80% at 15:05). Void deaths 0.24. Reflex 3.0 deg, rockets that hurt 41%. **The rule: both conditions clear (4.1 against 1.5; 75% and 88% against 41% and 53%), so it runs unaided to 19:00** |
| 19:00 final (3817 min) | 3817 | about 4 (3.8 to 4.5 in the last hour) | arena1 **69 / 97 / 100 / 100 / 100 %**; Blood Run 100 / 28 / 100 / 100 / 100; Aerowalk 100 / 25 (the walking graph has no way to it from most spawns) / 72 / 100 / 97 | 55 / 45 / 49 / 38% | - , 15.5% | arena1 **22-28** (damage 4478 : 2231, twice Nightmare's; machine gun in hand 76%), Blood Run **0-10** (1352 : 998), Aerowalk **0-0** (the two met 2% of the time). In fights on arena1 from a normal spawn: mega 0.01, red 0.02 a player-minute. Reflex 3.0 deg, rockets that hurt 36% |

**v10 in short.** *Worked*: the walk. Shown a scripted walker's keys in solo item runs for three hours, at a weight that faded to nothing, he went from 0.15 to about 4 targets a player-minute and went on improving after the teacher had gone; alone on arena1 he now takes what he is told to in 69 to 100% of 30-second rounds (0 to 22% in the morning), the weapons in close to the walking graph's own time, and of his own choice the red armor in four rounds of five. His aim did not move. *Did not move*: the games. Against Nightmare he deals twice the damage on arena1 and loses 22-28; on Blood Run and Aerowalk he scores nothing in five minutes. During fights he still leaves the mega and the red armor lying (0.01 and 0.02 a player-minute from a normal spawn), and he does not fire rockets (nine launchers picked up in the three 17:05 games, none fired). The red armor on Blood Run (28%) and on Aerowalk (25%) is also a matter of the way there (93% of it covered on Blood Run; no graph route on Aerowalk). The owner had it put on the public server at 19:03 to play it. Next: `duel_gru_v11` (docs/PLAN.md), for exactly these two things.

## 2026-10-06 evening — the public server: free-for-all rules, ready-up games, joining fixed (owner's requests while playing v8 with friends)

The public server ("BobbyBones the learning quake bot") runs the final v8 in free-for-all with three Bobbys on `arena1`, all 62 nav files and the map pool (`!map <name>`). Fixed and changed tonight, each tested on a local server first (`docs/COMMANDS.md`, `docs/HOSTING.md`):
- **Joining**: a friend of the owner was dropped on every join, on arena1 and on bloodrun alike ("connected" then "disconnected" within seconds, no kick). Two causes, both the pure server's pak list: first `lockout.pk3` was mounted although it is not in the Workshop item (19:48), then the server's own mounted copies of `arena1.pk3` and `testlab.pk3` sat next to the Workshop ones (20:34). The public server now loads the two maps from the Workshop item alone, so its pak list is exactly what a joining client downloads; local servers keep the mounts. The owner never saw it because both files are in his own `baseq3`.
- **Free-for-all rules** (owner): no quad (where a map puts the quad in the mega's place in free-for-all, campgrounds, the mega comes back, as in 1v1 and in training), no spawn timers on the armors and the mega, weapons back in 2 s (1v1 keeps 5 s), eight client slots with six seats in the game (the seventh and eighth spectate), `!bots 0` to `4`.
- **Real games**: warmup gives everybody every weapon, so there was no way to play a machine-gun-spawn game. `!match` was first made to start one (`allready`), which found that the server's ready percentage of 2 (set long ago to make warmup permanent) stops any start; then replaced at the owner's call: **a real 10-minute game starts when more than half of the people in the game press F3**; the Bobbys never ready up and are not counted; the game's own score table at the end, then warmup again (`sv_warmupReadyPercentage 1` in `server/lab.cfg`, the F3 count in `plugins/ffabot.py`).
- **Map switch**: `!map arena1` from bloodrun loaded arena1 and the free-for-all plugin pulled the server straight back to bloodrun (its wanted map was set only when it loaded); fixed in `plugins/botmode.py`. A map outside the plugin's old five-map list (sinister) made it reload the map every 10 s; the whole pool counts now.
- The 62 maps' nav graphs are on the server; the v8 network plays sinister and bloodrun with its routes (the owner played both).

## 2026-10-06 evening — `duel_gru_v9`: the map reader, seven maps, item respawn sounds, spawn points, random stacks, near-item spawns, claw-back (B-104, B-100; owner's plan, docs/PLAN.md "Next round")

Built after the owner stopped v8 at 17:49 ("we've gotten everything we can from this iteration"). From `duel_gru_v8` at update 150 (2486 min, `policy_end_v8.pt`), carried over by name (`reshape_policy.py --also` for the HMG columns from v7): 419 -> 483 inputs (459 with two players), 417 kept, 12 from v7, 54 new at zero, the two learned-cell inputs gone.

- **The map reader (B-104)**: `tools/map_raster.py` draws every map on the simulator's own 64-unit, two-layer cell grid (24 channels: walkable floor, height, solid, hazard, pads and landings, teleporters, spawns, every item kind) and computes the facts (travel time to mega / red / RL / RG / LG, openness, height above the floor, distance to the nearest hazard and spawn point). `sim/map_reader.py` is a ~60k-weight conv trained on the 62 maps of `docs/MAPS.md` plus arena1 (5 held out: almostlost, cure, hektik, toxicity, silence) to predict the facts, flipped and turned at random; its 16 numbers per cell and layer are written as `data/maps/cells_<map>.npy` and are now plain inputs (his cell and the enemy's last known: 32), in place of the table learned per map in v8. Nav graphs for all 62 maps built in 20 minutes (`sim/build_nav.py`, system Python). Three maps with lifts (delirium, terminus, theedge) are reader-only: the simulator has no movers.
- **New inputs**: item respawn sounds (mega, red, a weapon, a small health or armor came back within earshot: 4; `note_respawn` in the plugin too), the four nearest spawn points (12), the other two enemies' weapons in hand (6, group block), the heavy machine gun back everywhere it was (29 of the 62 maps have one).
- **Spawns**: a quarter with a random stack (health 100-200, armor 0-150) so the worth of armor is learned in fights; a quarter within 2 s of the mega or the red armor so he tastes the stack (`--stack-p 0.25 --near-item-p 0.25`); weapon sets only from the map's own weapons (`--loadout-p 0.25,0.75,0,0` on the duel maps, the arena sets on arena1).
- **Claw-back**: what a trip toward the chosen item has paid is taken back when he switches away or dies before taking it. v8 farmed the approach (below).
- **Maps for play**: arena1, aerowalk, bloodrun, lostworld, furiousheights, campgrounds, sinister (owner's pick), one per worker in turn; groups of 2, 3 and 4 everywhere; 21 workers.
- **Also**: the route grid is built in seconds and cached (`RouteField._grid`; the game-server plugin caches it in its data folder); the plugin applies the fire-finger rule (the button changes state at most every 100 ms), which is why the lightning gun stuttered on the server (the simulator held it 300 ms median); the v8 simulator is frozen as `sim/duel_env_v8.py` / `duel_env_ffa_v8.py` for the v8 network (the public server runs it); `sim/render_replay.py` renders a video from a server session log (the Nightmare game below).

Launched 18:32 (until 07:00 on the 7th): 21 workers, 8372 players, 1.41 M weights, 34,000 steps a second, graphics memory 15.9 of 16.4 GB. First update: with a quarter of the spawns next to the big items, mega 0.17 and red armor 0.32 per player-minute already (the taste of the stack by design); intentions lightning 65%, mega 22%.

**Stopped 19:21 at update 27** so the owner could play v8 on his machine (save of update 20 kept as `policy_stop_1921_update20.pt`). **Relaunched 20:42 on his go, to run until 16:00 on the 7th** (his call at 20:45; the 07:00 end is followed by a resume until 16:00), with these changes agreed in between:
- 180 matches a worker (memory down a tenth, 14.3 GB), rocket drills in a tenth of the rounds and rockets in 6 of the 28 arena spawn sets (v8's rockets were poor: 57% of them hurt the target against 83% for the owner).
- **The intention head seeded** by a simple item rule, like the game bot's own item table (mega when below 100 health and it is up or about to be, red when below 50 armor, else the nearest big weapon he lacks): imitated at weight 0.5 fading to zero over four hours, no reward attached (`--intent-teach 0.5`; owner: "seeding is fine here"). In the smoke test the intention shares moved to mega 33%, red 32% within minutes.
- **Aim limits tuned up** (owner, after the reflex comparison below): perception noise 1.0 -> 0.6 degrees (`PERCEPT_SIGMA`), hand noise 0.14 -> 0.10 (`MOTOR_NOISE`). The reaction (200 ms) and tracking (75 ms) caps stay: the final v8 measured against the owner's reflex card was at par on reaction (200 ms both), slower in tracking lag (122 against 102 ms) and turn reaction (275 against 212) with the cap at 75 ms, so the lag is the policy's and not the cap's; wider on a strafing target (3.5 against 2.5 degrees), more time on target (60% against 40%), worse first-shot flicks (68% against 88%) and rockets (57% against 83%). The frozen v8 simulator keeps the old values.
- The nightly loop checks every hour at :05 through to 15:05 (videos every three hours).
- **Graphics memory 15.8 -> 8.4 GB** (owner at 20:50: "kind of high"). Fewer players did not lower it (15.8 GB with 8372 players and with 7560 alike). A cap on the process (`GPU_MEM_FRACTION=0.80`) then crashed the run out of memory at its third update (21:06, ten minutes lost, resumed from the 20:56 save), and the error gave the cause away: it asked for 4.68 GiB in one piece, the size of the whole input buffer (384 steps x 6776 players x 483 inputs). The trainer made each rollout's buffers while the last rollout's were still held, so two of them were alive at once. They are now let go first (`train_duel_rnn.py`). Relaunched 21:07 with 162 matches a worker (6776 players, 33,000 steps a second): peak 8.4 GB over the first six updates, the cap left in place as a guard. Earlier runs could have had about 60% more players in the same memory.

| Time | Minutes | Fights: frags per group-min, in view, speed | Hit rail / LG / MG / rockets | Mega, red armor per player-min (lying) | Intentions: none / mega / red / RL / RG / LG, trips a min, reached | Void deaths | Half of his time in (cells) | vs Nightmare on arena1, 10 min |
|---|---|---|---|---|---|---|---|---|
| 18:35 (start) | 2486 | 12.0 (first sample) | 54% / 50% / - / 12% | 0.17, 0.32 | 2 / 22 / 2 / 5 / 3 / 65 %, 17, 1.5% | - | - | - |
| 21:15 (8 min after the last relaunch; no 21:05 check: the hourly loop was started after 19:05 and slept for its first slot until the next evening, replaced by `nightly_v9b.sh`) | 2536 | 8.0 | 53% / 44% / 47% / 25% | 0.14, 0.15 (lying 77%, 84% of the time) | 9 / 26 / 44 / 2 / 1 / 18 %, 10.5, 1.3% (abandoned 75%) | 0.013 | - | - |
| 22:05 | 2581 | 13.4, 46%, 261 | 58% / 42% / 45% / 37% | 0.12, 0.13 in training (lying 79%, 85%); in the arena1 probe without near-item spawns: mega 0.06, red 0 | 0 / 30 / 49 / 15 / 3 / 3 %, 11.6, 1.7% (abandoned 73%) | 0.019 | 523 (18%) | **6-31** (damage 3279 : 2050; machine gun in hand 88% of the time) |
| 23:05 | 2642 | 11.2, 42%, 253 | 57% / 45% / 46% / 40% | 0.16, 0.21 in training (lying 88%, 86%); arena1 probe: mega 0.02, red 0 | 1 / 27 / 40 / 12 / 3 / 17 %, 10.0, 1.6% (abandoned 72%) | 0.023 | 553 (20%) | **10-33** (damage 3787 : 2806; machine gun 72%, rail 14%) |
| 00:05 | 2703 | 11.7, 42%, 245 | 59% / 44% / 46% / 43% | 0.15, 0.15 in training (lying 77%, 82%); arena1 probe: mega 0.04, red 0 | 0 / 28 / 53 / 15 / 3 / 1 %, 10.4, 1.8% (abandoned 64%, died 36%) | 0.038 | 592 (21%) | **17-32** (damage 4341 : 2688; machine gun 71%, rail 15%) |
| 01:05 (the intention seed reaches zero at 01:07) | 2765 | 13.3, 46%, 262 | 59% / 44% / 47% / 43% | 0.16, 0.17 in training (lying 77%, 82%); arena1 probe: mega 0.04, red 0 | 0 / 31 / 50 / 15 / 3 / 1 %, 9.8, 2.1% (abandoned 67%) | 0.028 | 586 (21%) | **21-30** (damage 4410 : 2439; machine gun 71%, rail 11%, lightning 7%) |
| 02:05 (first hour without the seed) | 2820 | 13.8, 49%, 268 | 62% / 46% / 47% / 41% | 0.17, 0.16 in training (lying 79%, 79%); arena1 probe: **mega 0.14** (lying 78%), red 0 | 0 / 17 / 61 / 20 / 2 / 1 %, 9.5, 2.0% (abandoned 65%) | 0.045 | 624 (22%) | **22-36** (damage 4520 : 3196; machine gun 77%, rail 8%) |
| 03:05 | 2881 | 13.5, 46%, 249 | 61% / 46% / 48% / 45% | 0.15, 0.17 in training (lying 76%, 80%); arena1 probe: mega 0.10 (lying 85%), red 0 | 0 / 5 / 64 / 30 / 1 / 1 %, 9.0, 2.8% (abandoned 54%, died 46%) | 0.042 | 622 (22%) | **15-35** (damage 4272 : 2972; machine gun 79%, rail 7%) |
| 04:05 | 2942 | 15.4, 53%, 281 | 58% / 46% / 49% / 41% | 0.17, 0.19 in training (lying 75%, 80%); arena1 probe: mega back to 0.04 (lying 94%), red 0 | 0 / 3 / 51 / 45 / 1 / 1 %, 10.1, 2.8% (abandoned 51%, died 49%) | 0.048 | 602 (21%) | **12-41** (damage 4052 : 3533; machine gun 84%, rail 0%): the second hour down |
| 05:05 | 3003 | 14.2, 50%, 266 | 61% / 48% / 50% / 42% | 0.22, 0.25 in training (lying 80%, 82%); arena1 probe: mega 0.03 (lying 96%), red 0 | 0 / 2 / 27 / 70 / 0 / 0 %, 8.8, 2.7% (abandoned 54%, died 46%) | 0.033 | 583 (21%) | **11-34** (damage 3784 : 2961; machine gun 77%, rail 9%): the third hour down, a trend since the seed ran out at 01:07 (peak 21-30 at 01:05) |
| 06:05 | 3064 | 14, -, - | 60% / 48% / 50% / 43% | arena1 probe: red 0 | 0 / 1 / 7 / **92** / 0 / 0 %, 6.2, 4.1% (abandoned 37%, died 62%) | - | - | **21-30** (damage 4242 : 2704; machine gun 72%, lightning 11%): the "trend" of the three hours before was the noise of one game an hour |
| 07:05 (30 min into the constant seed and the claw-back change; before the runner) | 3107 | 12.4, 45%, 237 | 64% / 49% / 54% / 41% | 0.17, 0.22 in training (lying 74%, 80%); arena1 probe: mega 0.06, red 0 | 0 / 29 / 50 / 17 / 4 / 1 %, 10.9, 2.1% (abandoned 69%) | 0.049 | 541 (19%) | arena1 **18-29** (damage 3747 : 2665; machine gun 70%, rail 12%). Duel maps, 5 min, the game's spawn: Aerowalk **0-10**, Blood Run **1-12**, Lost World **0-13**, Campgrounds **1-5**; machine gun 58 to 87% of the time. (Furious Heights and Sinister: no game, the script reprinted Aerowalk's line; fixed) |
| 08:24 (five minutes after the last relaunch: runner, scatter, four maps, 10,080 players; the first rollouts of a launch are short rounds) | 3185 | 10.6 | 61% / 52% / 48% / 28% | 0.16, 0.15 in training (lying 80%, 76%) | 10 / 27 / 45 / 16 / 1 / 1 %, 9.0, 1.9% (abandoned 57%, died 43%) | 0.099 | - | - (measured check at the odd hours). Against the runner: 3.9 frags a minute, 3.5 deaths |
| 09:05 (47 min of runner, scatter, four maps) | 3225 | 10.8, 40%, 228 | 63% / 49% / 52% / 39% | 0.22, 0.25 in training (lying 83%, 82%); arena1 probe: mega 0.07, red 0 | 0 / 31 / 51 / 15 / 3 / 2 %, 9.6, 2.6% (abandoned 57%, died 43%) | 0.099 | 605 (21%) | arena1 **20-26** (damage 4225 : 2359; machine gun 77%, rail 12%), the closest yet. Blood Run **0-9** (899 : 805), Aerowalk **0-9** (910 : 983), machine gun 70%. Against the runner 2.2 frags : 1.5 deaths a minute. Reflex: 2.9 deg, rockets that hurt 35% |
| 10:33 (seven minutes after the relaunch with item runs; weapons could not be picked up in them from 10:07 to 10:25, an old rule of the movement rounds, fixed) | 3311 | 9.4 | 60% / 52% / 48% / 28% (first rollouts of a launch) | 0.14, 0.15 in training | 12 / 29 / 51 / 3 / 3 / 2 %, 7.4, 2.5% (abandoned 53%, died 47%) | 0.104 | - | - . **Item runs: 0.05 targets taken a player-minute** (the starting point; a player who knew the ways would take about ten). Against the runner 3.6 : 3.1 |
| 11:05 (40 min of item runs) | 3340 | 12.6, 46%, 248 | 60% / 47% / 51% / 35% | 0.15, 0.19 in training; arena1 probe: mega 0.08, red 0 | 0 / 32 / 46 / 15 / 4 / 3 %, 7.6, 2.4% (abandoned 61%, died 39%) | 0.115 | 580 (20%) | arena1 **13-34** (3801 : 3023; machine gun 84%). Blood Run **2-9** (1035 : 909), Aerowalk **1-2** (304 : 413; the two met 4% of the time; shotgun 75%). **Item runs: 0.11 to 0.23 targets a player-minute** (0.03 at the start). Solo test on arena1: mega 12%, red 0%, RL 0%, RG 12%, LG 22% of the rounds (09:15: 4 / 0 / 0 / 4 / 21). Runner 2.4 : 1.9. Reflex: 3.3 deg, rockets that hurt 32% |
| 12:10 (1 h 45 of item runs) | 3408 | 7.4 | 61% / 47% / 51% / 36% | 0.18, 0.18 in training | 0 / 32 / 47 / 14 / 4 / 4 %, 7.4, 2.4% (abandoned 60%, died 40%) | 0.118 (lava damage 7.4 a player-minute, 3.3 at 07:05) | - | - . **Item runs flat: 0.10 to 0.17 targets a player-minute** for the last hour and a half. Runner 2.5 : 2.1 |
| 13:05 (the last v9 check, 2 h 40 of item runs) | 3457 | - | - | arena1 probe: mega 0.04, red 0 | 0 / 31 / 49 / 14 / 3 / 3 %, 7.7, 2.8% (abandoned 56%, died 44%) | - | - | arena1 **18-28** (4077 : 2584; machine gun 82%). Blood Run **1-10** (924 : 1031). Aerowalk **2-0** (487 : 83; rail in hand 95%; the two met 4% of the time): his first win over Nightmare with the game's spawn. Item runs 0.10 to 0.17 targets a player-minute, flat for three hours. Solo test on arena1: mega 16%, red 0%, RL 3%, RG 16%, LG 22%. Reflex: 3.4 deg, rockets that hurt 42% |

**The night in short (owner's review, 06:15).** Against Nightmare 6-31, 10-33, 17-32, 21-30, 22-36, 15-35, 12-41, 11-34, 21-30: level with or a little above v8's 18-30 at best, and one ten-minute game an hour swings by ten frags either way. Rockets: 25% -> 43% hits in training with the drills, but **he does not fight with them**: 2% of his frags all night, never in his hand against Nightmare, absent from the weapon-by-distance table (machine gun 60 to 70% at every range; v8's rail and lightning shares fell because most spawns are machine-gun spawns now). Aim limits tuned up: no visible gain yet (3.0 to 3.7 degrees on a strafing target against v8's 3.5 and the owner's 2.5). Graphics memory 15.8 -> 8 GB. **Items: did not work again.** The red armor was never taken from a normal spawn on arena1 in nine hours, the mega 0.02 to 0.14 per player-minute. **What did not work, and why:** while the item rule was imitated (until 01:07) he chose mega and red four times in five and still reached 2% of them; once it had faded his choices went to the rocket launcher, 15% -> 92% in five hours. The claw-back took a trip's pay back when he died on the way; with a third to two thirds of the trips ending in death the long ones lost money and the short, safe one to the launcher won. So the claw-back as built pushed him away from the big items.

**06:35 — two changes, the owner's call, on the current weights** (`policy_stop_<time>.pt` kept): the claw-back only when he gives a trip up, not when he dies on it (`CLAW_ON_DEATH = False`); the item rule imitated for good and four times as strongly (`--intent-teach 2.0`, no fading; the owner: "fine with cranking up the intention head quite a bit to demonstrate him actually going for mega and red"). Runs until 16:00. Relaunched 06:36 (a first relaunch at 06:25 died on a typo in the launch line: 12 minutes lost), with rocket drills at 15% of the rounds. Three updates later his choices were back from rockets 94% to mega 26%, red 49%.

**06:20 — the duel maps, measured for the first time** (owner: "how is the gameplay on the other duel maps?"; the training numbers are not split by map). 1v1 against himself, 4 minutes x 8 games a map (`tools/heatmap.py --map`), mega / red armor per player-minute: Blood Run 0.17 / 0, Aerowalk 0.28 / 0.89, Lost World 0.08 / 0.38, Furious Heights 0 / 0.89, Campgrounds 0.80 / 0.31, Sinister 0.42 / 0. So he does take the red armor on four of the six: arena1's is the exception. Fights are rare there: about one death a player-minute (seven on arena1 with three players), the enemy in sight 5% of the time in the Blood Run and Campgrounds videos, 26% on Aerowalk. **Against Nightmare on Blood Run with the game's own spawn, 5 minutes: 0-9** (damage 1027 : 849). He took 4 weapons, Nightmare 16; the mega 0 against 7, the red armor 0 against 2, the yellow 1 against 13; he held the machine gun 85% of the game and never the rocket launcher, which he picked up twice. The older Blood Run benchmarks handed both players every weapon at spawn (`give_loadout` on every respawn): a scored duel on a duel map now keeps the game's spawn, as its chat line always said. The hourly check plays the six duel maps against Nightmare from 07:05 on, five minutes each, two games side by side (`tools/hourly_arena1.sh`, `BENCH_NAME` / `BENCH_DATA` in `tools/bench_arena.sh`).

**07:45 — the item runner and a scattering machine gun** (owner: "we gotta get him to go for items, mg all game is garbage"; "lower his mg accuracy, add the runners too and see if it helps"; B-102, parked until now in favour of pure self-play):
- **Why**: every copy of him skips the items, so skipping costs nothing in self-play; Nightmare turns up stacked every minute and wins on frags while he wins on damage.
- **The runner** (`script 3`, `_runner_keys` in `sim/duel_env.py`): a hand-written opponent in a quarter of the fight rounds (`RUNNER_P=0.25`), one seat of the group. He goes for what the item rule names (the same rule the intention head imitates: the mega when hurt, the red armor when bare, else the nearest big weapon he lacks) along the walking graph, jumps the ledges and the long edges, and fights like the all-round scripted fighter when someone is in view, still moving along his way. The game's spawn, real pickups, no reward, not imitated. `tools/runner_check.py` (the runner against a player who stands still, 2 minutes x 12 games): red armor per runner-minute arena1 1.4, Aerowalk 1.0, Lost World 0.75, Blood Run 0.2, and more on Furious Heights, Campgrounds and Sinister (the count there also catches other armor jumps: read it as "often"); a big weapon in hand 58 to 72% of the time. **So the red armor on arena1 can be reached on foot**: his not taking it is not the map. Frags against the runner and by him are counted in the trainer's `vs_bot` numbers.
- **The machine gun** had no scatter in the simulator: at 50% hits it was a laser at any range, the weapon behind 55% of his frags. Bullets now leave inside a cone of 1.4 degrees (`MG_SPREAD`; the Quake 3 source's value, heavy machine gun too). **Not measured on a Quake Live server yet** (to do with `plugins/weaponlab.py`); if the real one scatters less, he will be undervaluing it at range.
- On the current weights, from the next checkpoint save, until 16:00. Relaunched 07:38. In the first updates he trades about evenly with the runner: 3.6 frags a minute against 3.3 deaths.

**08:00 — the smaller maps only, and the measured check every other hour** (owner). The duel maps are too big for a player who does not go for items: he meets an enemy about once a minute there against seven times on arena1, and scored 2 frags in 20 minutes against Nightmare across four of them (07:05 row). Floor area from the walking graphs (64-unit cells): Aerowalk 568, Blood Run 761, Lost World 829, Campgrounds 1037, arena1 1050, Furious Heights 1157, Sinister 1172. Training goes on on **arena1, Aerowalk, Blood Run and Lost World**; Campgrounds, Furious Heights and Sinister are out until he seeks. Cutting maps into pieces was considered and not done (a fenced round teaches staying put and leaves the big items outside the fence); more close spawns is the next lever if the duel maps stay quiet. The measured part of the hourly check (Nightmare on arena1, Blood Run and Aerowalk; the reflex test; the heat map; a 30-second arena1 video) runs at the odd hours; the even hours print the training numbers. The owner confirms that the machine gun and the heavy machine gun scatter in the game and that the shotgun fires a fixed pattern (B-107b: measure both). Relaunched 07:52 on the four maps.

**08:18 — a larger batch** (owner: "you're under-utilizing my GPU"; I had said it would not speed training up, the simulator on the CPU being the limit, and he decided for it): 240 matches a worker and 64 minibatches, 10,080 players an update (6,776 before). Measured over the first three updates: graphics memory 11.4 GB at the peak (cap 13.1), 36,700 steps a second (34,200 before: a little more, the per-step overhead of a worker is shared by more players), an update every 105 seconds. The owner's rule from here: no further changes before 16:00 unless something goes badly wrong.

**09:15 — alone on the map, he does not go and get what he intends** (`tools/solo_item_check.py`; the owner's idea of solo runs, tested first). The 08:17 weights, one learner a game with nobody to see or fight, machine gun at spawn, 30-second rounds, the intention forced to one item for the whole round (48 rounds each). Share of rounds in which he took it, with the walking graph's time from his spawn:

| Intention | arena1 | Aerowalk | Blood Run |
|---|---|---|---|
| mega | 4% (way 3.6 s) | 17% (3.0 s) | 8% (3.7 s) |
| red armor | 0% (5.1 s) | 23% (only from the spawns next to it) | 0% (6.6 s) |
| rocket launcher | 0% (4.5 s) | 19% (2.5 s) | 0% (5.5 s) |
| railgun | 4% (3.3 s) | 25% (2.4 s) | 17% (4.9 s) |
| lightning gun | 21% (3.2 s) | 29% (3.4 s) | 10% (5.1 s) |

When he does take it, it takes him 10 to 27 seconds for a way of 3: he comes across it. He runs the whole time (310 to 380 units a second) and gets 35 to 87% of the way at his nearest. Left to choose, alone, he picks the red armor about 80% of the time and takes it in 0% of the rounds on arena1 and Blood Run. **So the missing piece is the skill, not the will or the time**: he has the time to the item and the direction of the next step of the way among his inputs (`_intent`) and has not learned to follow them; the way reward, the pickup reward and the seed all act on the choice and on a walk he cannot do. This also explains v7 and v8. (Found on the way: on Aerowalk the walking graph has no way to the red armor from most spawns.)

**10:08 — item runs** (owner: "some small % of solo runs on the maps to learn where the things are and actually see the benefit of picking them up. That mirrors how people learn maps. Worth adding to this current experiment despite my order"; the run extended to 19:00). A tenth of the playing time (`ITEM_RUN_P=0.10`) he is alone on the map for 60 seconds, from a spawn point with the game's spawn. His target is given to him as his intention (one of the big items lying there, drawn at random; the next one as soon as he has it, another if somebody takes it first) so that what his inputs say and what pays agree. Pay: the usual way and pickup rewards, plus 0.2 for every second of the way gained, minus 0.2 for every second that passes, plus 0.5 on taking it; nothing is clawed back and the intention head is not trained on those frames. Built on the movement-round code (`_item_run_start`, `_run_pick`, `RUN_LEN`, `RUN_SCALE`, `RUN_ARRIVE` in `sim/duel_env.py`): all seats of a group run at once, each alone (nobody is seen or heard). Checked with random keys in groups of 2, 3 and 4: 8 to 12% of the time in runs, no enemy ever in view, the intention always the target. The trainer's `move` numbers (arrivals a minute, speed) now count item runs, and the odd-hour check repeats the solo test on arena1: **the pass mark is that table going from about 10% to over 80%**. Not yet in: the second half of the owner's idea, seeing the benefit (collect for 20 seconds, then an opponent with a plain spawn appears); to be added once the walk works, so that the two can be told apart.

## 2026-10-06 12:16 — `duel_gru_v8`: an explicit intention, a learned map, 97 fewer inputs (owner: "try a model change"; until 19:00) (B-100, B-101, B-103)

**Ended 17:49 at update 150 (2486 min; `policy_end_v8.pt`), stopped by the owner 70 minutes early.** Against Nightmare, 10 minutes on arena1, across the day: 2-27, 6-27, 15-27, 3-25 and at the end **18-30 (damage 4051 : 2658)** — the first run to trade frags with it; the morning's v7 was 2-21 to 4-28. Fights 9 to 10 a minute, an enemy in view a third of the time, firing 27%, no hiding; void deaths 0.40 -> 0.09 per player-minute; rail 52%, lightning 42% hits. **Items: did not work.** The mega 0.02 to 0.03 per player-minute and the red armor never, in training and in play; he takes weapons (0.6 per player-minute) and the small healths on his way. The intention numbers show why: the mega was *chosen* a quarter of the time, reached on 1.7% of trips, abandoned on 74% — the way reward paid for the approach and nothing was taken back when he turned away, so he farmed the approach (fixed in v9 by the claw-back). Intention share at the end: lightning 60%, mega 25%, red 2%. Reflex test against the benchmark: more time on the strafing target (60% against 48%) but a wider error (3.5 against 2.0 degrees) and slower to catch a turn (275 against 170 ms); rockets poor (57% hurt against 95%). Trigger: he holds the lightning gun 300 ms median, 2% of presses under 100 ms — the stutter the owner saw on the server was the plugin passing frame-by-frame requests to the game without the fire-finger rule (fixed). The owner played it: "quite good, feels human-like, not botty; a bit too reliant on the railgun; doesn't pick up items yet." Heat map: the whole upper floor, the red island never — which the owner reads as holding the high ground, sound play on this map. (The first final check at 17:49 ran its video and reflex parts on an already-changed simulator and was discarded; the numbers above are from the frozen v8 simulator.)

Why: `duel_gru_v7` took the mega 0.02 times per player-minute and the red armor never, all morning, through three
sizes of pickup reward. He had the map knowledge as inputs (routes, timers, his stack) and did not act on it. The
diagnosis (owner agreed): nothing he trains against needs a stack, the red armor sits past the void he has learned
to avoid, and the travel reward of 11:35 (0.0025 a frame) was smaller than the exploration bonus. The two-player
checkpoint-mates still fight at 125/0.

From `duel_gru_v7` at update 40 of the restart (`policy_end_v7_update40.pt`, 2160 min), carried over by name with
`sim/reshape_policy.py` (360 inputs kept with their weights, 112 retired, 15 new at zero; `policy_start_from_v7.pt`).

- **The intention head** (one more action, 6 choices): nothing, the mega, the red armor, rockets, rail, lightning.
  Read once a second per player (staggered; at once after a spawn), held in between; the trainer masks the head's loss
  to the frames it was read on. Changing it costs 0.02. Inputs back to him (13): the chosen way's seconds and next step,
  the chosen item up / coming back in, which intention, seconds since chosen. So "follow the arrow" is easy and
  "which arrow" is the decision, and the decision is logged: share of time per intention, trips chosen / reached /
  abandoned / ended by death, seconds to reach. The plugin and the videos show it.
- **Rewards (owner's sizes):** pickup 0.75 per 100 points of health or armor (a full mega or red armor 0.75 against 1 for
  a frag, "never more than a frag"), a weapon he lacked 0.19; **an enemy's mega or red costs the others half of what he
  gained** (-0.375 for a full one); the chosen way pays 1.0 per second of it gained (0.025 a frame, five times the
  exploration bonus), while the item is up or comes back before he can be there, fading to a quarter over six hours
  (`--intent-seek 1.0 --intent-seek-minutes 360`). The old nearest-item travel reward is off.
- **A learned map (2 inputs, a table of 4096 x 16 learned numbers):** the 64-unit cell he stands in and the cell the enemy
  was last known in (two height layers), looked up in a table the network learns ("what this place is like"). Starts
  at random with zero weights into the encoder, so nothing changes until training uses it. Exported with the policy;
  the plugin and the numpy policies read it.
- **Retired (112, owner: keep the network near 500 and the server cheap):** everything that is always zero on `arena1`:
  yellow and green armor, shotgun, grenade launcher, plasma gun, heavy machine gun (as items, held, owned, ammo, in the
  enemy's hands, in memory, as shot sounds), grenades and plasma in flight, the third health, the ammo boxes, the map
  name, the 60 s clock, the directions of the five routes (seconds stay; the chosen route has its direction). 472 -> 375
  inputs (357 with two players); 1.45 M weights; graphics memory 9.8 of 16.4 GB. They come back with the duel maps
  (B-101), by the same tool.
- **Not done, kept as an option (B-102):** a scripted "runner" in the league that takes the mega and red and fights with a
  stack, so that not stacking costs something in self-play. The owner wants pure self-play for now.
- **New measurements:** `tools/heatmap.py` (where he spends his time on the map, top view, with items and deaths; how
  many cells hold half of his time) and in the training numbers the share of time the mega and the red armor lie
  there untaken (`mega_lying`, `red_armor_lying`: both should go down). Videos can be rendered larger (`--width 640`).
- First update (thin sample, 2 min): intentions uniform (a sixth each), 58 changes per player-minute, 0.3% of trips
  reached; mega 0.078 per player-minute, lying 99% of the time.

| Time | Minutes | Fights: frags per group-min, in view, speed | Hit rail / LG / MG / rockets | Mega, red armor per player-min (lying) | Intentions: none / mega / red / RL / RG / LG, trips a min, reached | Void deaths | Half of his time in (cells) | vs Nightmare on arena1, 10 min |
|---|---|---|---|---|---|---|---|---|
| 12:18 (start) | 2163 | 4.1, -, - | - | 0.078 (99%), 0.003 (100%) | 17 / 17 / 17 / 17 / 17 / 17 %, 58, 0.3% | 0.15 | 328 of 32 x 32 (v7 at 12:09; 12% of the cells visited) | - |
| 12:46 (update 33) | 2192 | 9.0, 32%, 242 u/s (firing 25%) | 49% / 39% / 42% / 24% | 0.026 (95%), 0 (100%) | 15 / 23 / 5 / 20 / 8 / 30 %, 36, 0.4% | 0.12 | - | 2-5 in a 2 min server test (damage 628 / 415) |
| 12:52 | 2200 | stopped at update 40 for the six changes below (`policy_before_six_changes_update40.pt`) | | | | | | |
| 14:05 | 2235 (restarted 12:58 with the six changes) | 8.7, 31%, 230 u/s (firing 25%) | 49% / 40% / 42% / 27% | 0.024 (96%), 0.002 (100%) | 6 / 27 / 7 / 18 / 4 / 39 %, 14, 1.1% | 0.12 | 350 (12%) | 2-27 (damage 2249 / 2135, held MG 80%) |

**12:52 — six changes at once, then no more (owner: "prohibit me from making more changes unless the data really looks bad"; the run ends 19:00 and is reviewed then):**
1. **The way is worth the item:** the travel reward is the pickup value (0.75 for mega or red, 0.19 for a weapon) spread along the way as it is gained, so a trip never pays more than the item; the 1.0 per second of 12:16 (a red trip was worth five frags) is gone, and so is the fade.
2. **Shotgun, grenade launcher and plasma gun back** in every input they had (44 inputs: items, held, owned, ammo, in the enemy's hands, memory, shot sound, grenades and plasma in flight): 375 -> 419 (401 with two players). He must know the game's main weapons for the maps to come; the heavy machine gun stays out. Their weights came from `duel_gru_v7` by name (`reshape_policy.py --also`).
3. **Horizon 12 -> 25 s** (`--gamma 0.999`): item cycles are 25 and 35 s.
4. **Training sequences 256 -> 384 frames (6.4 -> 9.6 s)**, 48 minibatches: the gradient for remembering a timer or where the enemy went only flows within a sequence.
5. **A choice holds 3 s** unless the item was taken or he died ("nothing" can be left at any read): 36 changes a minute and 0.4% of trips completed at 12:46.
6. **Learning rate over cumulative training time** (`--lr-minutes 1440`: a tenth after 24 h in all), not reset to full at every restart (six restarts today, six jolts).
Plugin fix on the way: the server had crashed on the table lookup (`P.files` on a dict); retested 2-5 in 2 min.

**13:30 — free-for-all plugin built (B-105, owner's request, not on the public server yet):** `plugins/ffabot.py`, up to four Bobbys and people in six seats. Test with three Bobbys on `arena1`: no errors over 9,000 frames, each at 257 to 277 u/s, an enemy in sight 33 to 41% of the time, firing 18%, 13 kills in the first 90 s, intentions spread over mega / rockets / lightning (red armor 9% for one of them). Test server on port 27971 for the owner to try.

**14:30 — the owner played v8 (2225 min) on the local free-for-all server:** "quite good: he doesn't pick up items yet but the play is good; a bit too reliant on the railgun; definitely feels human-like, not botty". Three Bobbys among themselves hold the rail 70 to 90% of the time (rail hits 49% in the simulator against 40% for lightning). Pushed to the public server at 14:28: free-for-all with three Bobbys on `arena1` by default, `!map testlab` for the 1v1 rooms.

**16:30 — the trigger, measured (`tools/fire_holds.py`, 72 player-minutes of self-play):** he holds the lightning gun down 250 ms median, 527 ms mean, 2% of presses under 100 ms, 1.6 presses a second with an enemy in view; rail 150 ms median; machine gun 250 ms. So the fire spam the owner saw on the server is not in the network's behaviour: it is on the plugin or server side (bot sub-steps, the attack button per server frame) — to find before the next deploy.

**16:30 — what four Bobbys cost per server frame (measured on the training PC):** building the inputs for 6 seats 1.55 ms (2.28 ms with the dense view), one network pass for 4 Bobbys 0.57 ms (0.76 ms). The rented server (2 cloud vCPUs) is about 2.5 times slower and the game itself keeps one core busy: about 8 to 10 ms of a 25 ms frame today. Budget set with the owner: 15 ms. Inputs that are numbers he already knows cost nothing; ray casts (68 per seat now) and network size are what cost.

**What "really bad" means, agreed in advance:** fights per group-minute under 5 or firing under 15% (he avoids fights for the items); void deaths above 0.4 per player-minute; the run stalls (no update for 10 min); or by 19:00 intention trips reached still under 2% with mega under 0.05 per player-minute. Anything else waits for the 19:00 review.

## 2026-10-06 07:00 — `duel_gru_v7`: pickup reward, routes to the items, groups of 2, 3 and 4 (owner's plan after the night)

**Ended 12:09 at update 40 of the 11:35 restart (2160 min; `policy_end_v7_update40.pt`). Did not work for items:** mega 0.02 per player-minute and red armor 0 the whole morning, through pickup rewards of 0.3, 0.6 and 1.5 and a travel reward; he out-damaged Nightmare every hour and lost 2-21, 3-32, 3-26, 4-28 on stack. What did improve: void deaths 0.40 -> 0.16 per player-minute, firing 18 -> 23% of the time, no hiding, rail hits 40 -> 47%. Replaced by `duel_gru_v8` (above).

From the `duel_gru_v5` network again (1888 min; `policy_start_405_inputs.pt`), not from the passive morning one.
- **Players:** a third of the workers each with groups of 2, 3 and 4, all against all (`--group 2,3,4`; about the same
  number of players per worker). In a group, someone else's frag costs you nothing, so hiding loses ground.
- **Pickup reward:** 0.3 per 100 points of health or armor gained (a full mega or red armor 0.3 against 1 for a frag),
  0.03 for a weapon. To be faded out once items are fought over.
- **Damage taken weighs half of damage dealt** (`--dmg-taken-w 0.5`); frag +1 and death -1 unchanged.
- **Spawn:** machine gun and gauntlet only in three spawns of four, one of the seven weapon sets otherwise.
- **Route inputs (20):** seconds of travel along the floor and the next step of the way to the mega, the red armor,
  rockets, rail and lightning (`RouteField` over `data/maps/nav_arena1_sim.json`, built by `sim/build_nav.py` with
  the system Python: the Anaconda scipy is broken, so the lookup is plain numpy). 387 inputs with two players, 405
  with the group block. The walking map did not find the jump pad to the tower: the way to the mega goes round by
  the stairs (about 10 s).
- **Benchmark:** ten minutes against Nightmare on `arena1` each hour.
- First update: enemy in view 39%, firing 20% of the time, void deaths 0.40 per player-minute.

**07:29 — the mouse pad and better hearing (owner; network widened 405 -> 414 inputs, one new action; checkpoint before: `policy_before_pad_and_hearing.pt`)**
- **Mouse pad:** his view is turned by a mouse on a pad 240 degrees wide. At the edge he cannot turn further that way: the
  mouse is lifted and set back in the middle, 125 ms without any view movement. He can also lift it himself (new action).
  Inputs: where the hand is on the pad, mouse in the air. Why: he stood and spun on the spot to look around, which no
  person can do. Set from the owner's sessions: longest one-way turn 219 degrees (99 in 100 under 170), pauses inside
  long turns 125 ms. Check: asking for a constant 8 degrees a frame for 5 s gives 1189 degrees where it gave 1600, with
  the mouse in the air 22% of the time.
- **Hearing:** the nearest enemy heard within 1000 units (running steps, jumps and landings, shots; no line of sight
  needed): just heard, fading, direction against his view (about 10 degrees rough), above or below, loudness, coming or
  going. 7 inputs. Before, a sound gave a rough position for a few kinds of event only. A sound is heard on 29% of
  frames with three players moving at random.
- Both are mirrored in the game-server plugin.

**07:56 — the hum of the railgun and the lightning gun (owner: holding one gives your position away, it is part of the game's balance)**: an enemy holding either is heard within 500 units even when he stands still and does not fire, and the hum tells which of the two it is (2 more inputs, 416 in all). He knows which weapon he holds himself, so whether to carry a humming weapon is left to him.

**What went wrong, 07:30 to 07:56:** after the widening to 414 inputs the run stood still at its second update for 26 minutes: the graphics memory was full (15.9 of 16.4 GB) and training crawled. Nothing was lost but the time. Restarted with smaller training batches (`--minibatches 36`, 240 groups per worker): 14.3 GB, 49,000 steps a second where it had 59,000.

**08:29 — five gaps from an audit of the inputs (owner: add 1 to 5), 416 -> 472 inputs; checkpoint before: `policy_before_audit_inputs.pt`**
1. **The walk key is back** (it was switched off on 2026-10-05 when it did nothing): walking is silent, and now that steps are heard that is half of the hearing. It sits on the little finger with crouch. Its output was noise after training without it, so it was reset to "almost always off".
2. **Hazards in sight:** in 8 directions at 96 and 224 units, is the floor lava, is it a drop that kills (32 inputs, only inside the field of view). A deadly drop used to read like any ledge. Checked: at the edge of the void the drop is flagged ahead, in front of the pit the lava, on open floor nothing.
3. **The enemy's last known speed and heading**, kept for 5 s after he leaves the view (3).
4. **Where the nearest jump pad lands** (3), and the pad is now in the routes: mega from the south-west floor 2.3 s, it was 9.8 s round by the stairs (B-98 done).
5. **His own two nearest projectiles** in flight (18).
- Training batches `--minibatches 40`; 45,000 steps a second, an update every 49 s, checked over 13 updates. Graphics memory 15.5 of 16.4 GB: there is little room left for more inputs at this number of players.

**08:50 — a denser picture of the view, built behind a switch, not in the run (B-99, item 6):** 9 x 5 distances across his view where the standard picture has 5 x 3 (`DENSE_VIEW=1`; off by default, and with it off the simulator is unchanged). Cost measured: a simulator step for 510 players takes 29.9 ms with it against 20.2 ms without (+48%, measured while the run was using the processor), 517 inputs against 472, and the graphics memory has no room for it at the present number of players. Whether it helps is not measured: that needs two training runs side by side, which the graphics card cannot hold while `duel_gru_v7` trains.

**10:25 — less flinch, more for items (owner: Nightmare ruins him on items):** flinch 0.2 -> 0.12 deg per point of damage (at most 3): under fire his first rail shot had fallen to 30% where the player's was 63%. Pickup reward doubled, 0.3 -> 0.6 per 100 points of health or armor (a full mega or red armor 0.6 against 1 for a frag). A weapon he did not have counts as 25 points (0.15); one he has already counts as nothing, so standing on a weapon's spot earns nothing (before, every pickup of a weapon paid a little, which could be farmed every 5 s). Checkpoint before: `policy_before_more_item_reward.pt`.

**11:35 — items, harder (owner: beat him over the head with it):** forty minutes of the doubled pickup reward moved nothing (mega 0.016 per player-minute, red armor none). Now (checkpoint before: `policy_before_item_seek.pt`):
- pickup reward 0.6 -> 1.5 per 100 points: a full mega or red armor is worth more than a frag, a 25 health 0.375, a weapon he lacks 0.375;
- **going for an item pays on the way** (`ITEM_SEEK=0.1`): 0.1 per second of travel gained toward the nearest big item that is lying there and that he can use (mega below 200 health, red armor below 200 armor, a weapon he does not have), by the route along the floor. Moving away costs the same. Jumps in the figure (item taken, death, teleporter, the flight from a jump pad) pay nothing.
Both are rewards for a single behaviour, against the method chosen on 2026-10-05; the owner's call, to be faded out once items are fought over.

| Time | Minutes | Fights: frags per group-min, in view, speed | Hit rail / LG / MG / rockets | Mega, red armor per player-min (lay) | First weapon after | Void deaths per player-min | vs Nightmare on arena1, 10 min |
|---|---|---|---|---|---|---|---|
| 07:04 (start) | 1889 | 2.3, 39%, 269 u/s | 40% / 37% / 42% / 47% | 0.088 (2.5 s), 0.001 | 2.3 s | 0.40 | - |
| 08:05 | 1920 (stood still 07:30 to 07:56; pad, hearing and hum in) | 5.2, 28%, 227 u/s | 37% / 33% / 36% / 13% | 0.017 (36 s), 0.003 (36 s) | 14.3 s | 0.38 | 2-21 (damage 2004 / 1827, held MG 91%) |
| 09:05 | 1980 (audit inputs and walk key since 08:29) | 5.1, 25%, 212 u/s | 39% / 33% / 36% / 25% | 0.024 (242 s), 0.01 (259 s) | 16.6 s | 0.28 | 3-32 (damage 2785 / 2971, held MG 72%, rail 16%) |
| 10:05 | 2038 | 4.8, 24%, 183 u/s | 41% / 37% / 34% / 27% | 0.017 (495 s), 0.002 (709 s) | 17.9 s | 0.20 | 3-26 (damage 2679 / 2425, held MG 82%, rail 9%) |
| 11:05 | 2097 (less flinch, pickup reward 0.6 since 10:27) | 6.4, 25%, 210 u/s | 47% / 39% / 39% / 30% | 0.016 (236 s), 0 | 13.7 s | 0.17 | 4-28 (damage 2950 / 2260, held MG 77%, LG 7%, rail 6%) |
| 12:05 | 2155 (pickup 1.5, travel reward since 11:35) | 7.7, 31%, 235 u/s | 47% / 41% / 42% / 33% | 0.028 (166 s), 0.002 (194 s) | 9.0 s | 0.16 | 3-23 (run at 12:10 from the same checkpoint; damage 2367 / 1848, held MG 88%; the 12:05 attempt did not start) |
| 15:05 | 2315 | 9.7, 33%, 245 u/s (firing 26%) | 50% / 41% / 42% / 20% | 0.026 (96%), 0.001 (100%) | 5 / 28 / 4 / 12 / 2 / 49 %, 13, 1.4% | 0.11 | 378 (14%) | 6-27 (damage 2878 / 2555, held MG 73%, rail 17%) |
| 16:05 | 2377 | 9.7, 33%, 241 u/s (firing 27%) | 52% / 41% / 43% / 27% | 0.030 (96%), 0.001 (100%) | 5 / 26 / 3 / 5 / 1 / 60 %, 12, 1.7% | 0.09 | 391 (14%) | **15-27** (damage 3724 / 2189, held MG 70%, rail 12%, LG 9%) |
| 17:49 (end) | 2486 | 8.9, 31%, 221 u/s (firing 27%) | 52% / 41% / 43% / 27% | 0.031 (96%), 0 (100%) | 8 / 25 / 2 / 5 / 1 / 60 %, 11, 1.4% | 0.09 | 409 (15%) | **18-30** (damage 4051 / 2658, held MG 73%, rail 9%, LG 7%) |
| 17:05 | 2441 | 10.1, 33%, 240 u/s (firing 28%) | 52% / 42% / 43% / 30% | 0.025 (97%), 0.001 (100%) | 5 / 24 / 2 / 3 / 1 / 66 %, 11, 1.9% | 0.09 | 403 (15%) | 3-25 (damage 2623 / 1926, held MG 84%, rail 7%) |

## 2026-10-05 21:03 — `duel_gru_v6`: `arena1` with items, the limits from the reflex test, memory inputs (until 07:00) (B-87, B-90, B-92 to B-94)

From `duel_gru_v5` at 1888 min, widened 348 -> 385 inputs (`policy_start_385_inputs.pt`); a new run name because the
map, the spawn and the meaning of the limits changed.

- **Training:** only self-play on `arena1` (the whole map), two players, 180 s rounds, against the league of past
  versions. Spawn: machine gun and gauntlet, normal health; weapons, mega health and red armor are picked up.
  Lava 20 damage a second, the void kills. Simulator `duel_env_ffa` with two players per group.
- **Reward:** unchanged (frag +1, death -1, damage 0.005 dealt minus taken); **no reward for pickups**
  (`--item-reward 0`; the trainer's default of 0.3 never mattered before because the fighting room had no items).
- **Limits:** tracking delay 75 ms with focus bursts, error on the seen direction 1.0 deg, flinch 0.2 deg per
  point of damage, hand limits as before.
- **New inputs (19):** mega and red armor known taken and how long ago; what the enemy is known to have (mega, red
  armor, weapons seen in his hands); time since his own respawn and since the enemy's last known death; his own
  focus. The game-server plugin feeds the same.
- **Measured each hour** (`tools/hourly_arena1.sh`): the training numbers with the map ones (mega and red armor a
  minute and how long they lay, seconds to the first weapon of a life, deaths in the void, lava damage), five
  minutes against Nightmare on `arena1`, and the reflex test against the benchmark.

| Time | Minutes | Fights: frags a min, in view, speed | Hit rail / LG / MG / rockets | Mega, red armor per player-min (lay) | First weapon after | Void deaths per player-min | vs Nightmare on arena1, 5 min |
|---|---|---|---|---|---|---|---|
| 21:06 (start) | 1889 | 0.4, 26%, 267 u/s | 62% / 46% / 44% / - | 0.105 (2.6 s), 0 | 2.8 s | 0.46 | - |
| 22:05 | 1947 | 1.7, 10%, 233 u/s | 50% / 42% / 43% / - | 0.03 (389 s), 0 | 25.6 s | 0.22 | **1-14** (damage 1101 / 1331, held MG 87%, rail 3%) |
| 23:05 | 2008 (spawn weapon sets since 22:23) | 2.5, 9%, 234 u/s | 44% / 44% / 41% / 43% | 0.01 (428 s), 0.001 | 17 s | 0.13 | 0-13 (damage 912 / 1146, held MG 84%) |
| 00:05 | 2068 | 3.6, 11%, 242 u/s | 48% / 42% / 40% / 27% | 0.03 (782 s), 0.002 | 14.7 s | 0.13 | 0-13 (damage 1009 / 993; Nightmare took the red armor 9 times and the mega 5 times and averaged 136 health + 95 armor, Bobby 99 + 0; 3 of his 13 deaths were falls into the void) |
| 01:05 | 2129 | 1.7, 5%, 223 u/s | 40% / 47% / 51% / - | 0.01 (885 s), 0 | 23.6 s | 0.08 | **9-13** (damage 2036 / 1238, held rail 40%, MG 51%) |
| 02:05 | 2186 | 2.3, 7%, 230 u/s | 44% / 51% / - / - | 0.01 (1141 s), 0.001 | 23.1 s | 0.06 | 0-16 (damage 948 / 1173, held MG 89%: he fetched no weapon this game; one five-minute game swings a lot) |
| 03:05 | 2246 | 2.9, 8%, 229 u/s | 52% / 42% / 41% / 58% | 0.02 (1510 s), 0 | 13.5 s | 0.08 | 1-11 (damage 1163 / 953, held MG 71%, rail 21%) |
| 04:05 | 2306 | 1.1, 11%, 241 u/s | 47% / 36% / 42% / 12% | 0.04 (1547 s), 0.001 | 2.9 s | 0.02 | 6-16 (damage 1952 / 1482, held MG 70%, rail 18%) |
| 05:05 | 2369 | 1.2, 4%, 219 u/s | 49% / 39% / 42% / 20% | 0.007 (1715 s), 0.001 | 33.5 s | 0.04 | 0-18 (damage 929 / 1552, speed 119 u/s, held MG 86%) |
| 06:05 | 2428 | 1.6, 4%, 217 u/s | 51% / 41% / 45% / - | 0.01 (1262 s), 0.001 | 20.6 s | 0.05 | 5-16 (damage 1697 / 1403, speed 172 u/s, held MG 81%) |
| 07:00 (end) | 2476 | 1.3, 4%, 208 u/s | 52% / 40% / 39% / 30% | 0.006 (1596 s), 0 | 24.7 s | 0.04 | 4-26 in ten minutes (damage 2738 / 2146, held MG 88%) |

**Result of the night (did not work):** ten hours made him worse at fighting on the map. He learned the map's
dangers (void deaths 0.46 -> 0.04 per player-minute, lava damage 25 -> 1) and to fight with rail and lightning when
he has them, but the two copies drifted apart: the enemy in view 26% -> 4% of the time, firing 14% -> 3%, key
changes asked 6.6 -> 1.3 a second. The mega lay 25 minutes between pickups and the red armor was taken a handful
of times in all. Against Nightmare: 1, 0, 0, 9, 0, 1, 6, 0, 5 frags in five minutes and 4-26 in ten at the end,
although he usually dealt as much damage as he took: Nightmare carried 136 health and 95 armor on average (red
armor nine times in one game), he 99 and none. Why: with a death costing what a frag earns and damage taken
costing what damage dealt earns, staying away is a safe answer on a map with room to hide, and since neither copy
took the armor, neither ever met a stacked opponent to learn its worth from. The aim limits held: on the reflex
test he ended at 60% of the time on a strafing target (benchmark 48%), first rail shot 82% (95%), on a new target
after 350 ms (280 ms).

**22:23 — spawn weapons (owner)**: after an hour the two rarely met (in view 10%) and fought almost only with the machine gun (79% of kills; a weapon picked up once in two minutes). Now each player draws his own set at every spawn: machine gun and gauntlet always, plus one of the eight combinations of rail, lightning and rockets with equal weight (none included). Checkpoint before it: `policy_before_weapon_sets.pt`. The map has no ammo boxes: ammo comes only with the weapons lying there (back 5 s after being taken). The Nightmare benchmark stays the real game's duel spawn.

Start: as expected much weaker than in the fighting room (he has never had to find a weapon, cross a map or avoid
a drop): 0.4 frags a minute against 15, the enemy in view 26% of the time, a death in the void every two
minutes per player. Machine gun 44% under the new limits (78% under the old).

## 2026-10-05 21:45 — the benchmark redone from a run where the player moves as he aims; `arena1` (B-91 to B-94)

The owner: telling players to stand still is wrong, good players aim by moving. He ran the test again moving
normally; that run alone is the benchmark now, at 20% better than him (`docs/reflex_benchmark.json`).

**What went wrong before**: tracking lag was measured from how the view turns against how the direction to the
target changes. A player who strafes with the target hardly turns his view, so that number was meaningless (it
gave 192 ms, then 0 ms). It is now the slope of the gap between crosshair and target against how fast the target
itself crosses the view, which holds however the gap is closed. On that measure he and Bobby were about level in
timing all along; **the 150 ms tracking delay set two hours earlier was based on the bad number and is withdrawn**
(75 ms stays). Where Bobby is ahead is precision, not speed.

| Measure | Player (last run) | Benchmark (20% better) | Bobby (`duel_gru_v5`, new limits, untrained for them) |
|---|---|---|---|
| Strafing target: share of time on it | 40% | 48% | 62% |
| Strafing target: lightning damage a second | 58 | 69 | 86 |
| Strafing target: crosshair trails it by | 102 ms | 82 ms | 132 ms |
| Strafing target: catches a turn after | 212 ms | 170 ms | 228 ms |
| Jumping target: a third of the way there after | 200 ms | 160 ms | 197 ms |
| Jumping target: on it after | 350 ms | 280 ms | 309 ms |
| Jumping target: first shot hits | 88% | 95% | 73% |
| Rockets: share that hurt the target | 83% | 95% | 19% |
| Under fire: time on the strafing target | 20% (-49%) | 25% | 41% (-35%) |
| Under fire: lightning damage a second | 36 (-38%) | 43 | 65 (-24%) |
| Under fire: first rail shot hits | 63% (-29%) | 75% | 49% (-33%) |
| Under fire: on a new target after | 550 ms (+57%) | 440 ms | 309 ms (+0%) |

- **Limits set from it**: error on the seen direction 0.5 -> 1.0 deg; flinch 0.06 -> 0.2 deg per point of damage (at
  most 4); tracking delay stays 75 ms with focus bursts (50 ms sharp for 2 s, then 100 ms). Being shot at cost the
  player about half his tracking and a third of his rail hits: the flinch is sized to that.
- **Still off**: his lightning tracking is above the benchmark (62% against 48%) and his rail and rockets below it.
  Four 20-second samples per room are noisy (one sweep gave more time on target with more error), and the network
  has not trained under these limits, so the next step is to train, then measure with more repeats, then adjust.
- The reflex test no longer asks players to stand still; Bobby is measured moving freely too. Aim error is the
  median now (the mean was thrown by moments of looking away).
- Map `train-arena` renamed `arena1` (an `arena2` for closer fights is planned).

## 2026-10-05 21:00 — aim under fire and focus in bursts: built, measured on Bobby, waiting for the player's run (B-93, B-94)

- **Reflex test**: in track, flick and rocket the target now shoots back with the machine gun for the second 20
  seconds; `tools/reflex_report.py` measures each half and prints what being shot at costs, per aim type.
- **Before the change Bobby lost nothing under fire** (old limits: aim error 1.08 deg under fire against 1.27 calm,
  first rail shot 77% against 79%): a hit only pushed him.
- **Flinch (B-94)**: a hit throws his read of the enemy's direction off by 0.06 deg per point of damage (at most
  2.5), fading over 0.3 s. **Focus (B-93)**: 2 s of sharp tracking (delay 50 ms shorter), then 25 ms longer than the
  set delay until focus is back (a quarter of a second per second out of contact). First values, to be set from
  players.
- Bobby (`duel_gru_v5`, untrained for any of this) with a 150 ms delay, focus and flinch: view behind a strafing
  target by 168 ms over 40 s (benchmark 163); under machine-gun fire time to get on a new target 291 -> 328 ms
  (+13%), first rail shot 71% -> 67%, tracking about unchanged (machine-gun hits are 5 damage each: 0.3 deg).

## 2026-10-05 20:10 — first player measured in the reflex test; benchmark set; maps renamed and the arena rebuilt (B-91, B-92, B-87)

**The owner ran `!reflex` twice** (averages; Bobby = `duel_gru_v5` at 1888 min in the same rooms in the simulator,
standing still, with the limits he trained under):

| Measure | Player | Bobby | Benchmark (15% better than the player) |
|---|---|---|---|
| Strafing target: view runs behind by | 192 ms | 76 ms | 163 ms |
| Strafing target: follows a turn after | 150 ms | 75 ms | 128 ms |
| Strafing target: share of time on it | 43% | 79% | 50% |
| Strafing target: aim error | 4.1 deg | 1.1 deg | 3.5 deg |
| Strafing target: lightning damage a second | 64 | 102 | 73 |
| Jumping target: view starts moving after | 238 ms | 125 ms | 202 ms |
| Jumping target: on it after | 463 ms | 172 ms | 393 ms |
| Jumping target: first shot hits | 85% | 78% | - |
| Slow target: hand jitter | 0.71 deg a frame | 0.98 | - |
| Rockets: share that hurt the target, damage a rocket | 91%, 60 | fires none | - |

- He reacted about twice as fast as the player everywhere; his hand shake was already at the player's level. So
  the day's shake nudges were aimed at the wrong thing: the gap is reaction and tracking.
- Caveats: one player, two runs; he was moving in the slow-target room (285 u/s), so that row is not a clean
  steadiness reading.
- **Benchmark** (owner: 10 to 20% better than him until more players are measured): `docs/reflex_benchmark.json`;
  `tools/reflex_report.py` prints it as a column.
- **Limits changed to reach it**: tracking delay 75 -> 150 ms (`--react-ms 150`), view inertia 0.5 -> 0.75
  (`MOUSE_SMOOTH`). The current network measured under them, untrained for them: view behind by 155 ms
  (benchmark 163), view starts moving after 200 ms (202), follows a turn after 150 ms (128), on a new target
  after 281 ms (393: still too fast; more inertia, 0.85, did not change it because he simply asks for faster
  turns, so that needs a limit on how fast the hand speeds up), time on the strafing target 30% (50%; expected to
  recover with training). To be re-measured after the next run.
- **Keys** (the server now counts changes over every command a client sends, 125 a second): the player made 4 to 7
  movement-key changes a second in the movement courses, 7 to 19 in the busiest second. Bobby's hand allows 10 in a
  burst and 4 a second sustained, and he makes about 5: his budget is not looser than a person's.

**Maps**: `bobbylab` is now `testlab`, `bobbyyard` is `train-arena` (code, docs and files; older entries below keep
the old names). The arena after the owner's play test: a closed room in the south-east, a long wall on the west
side, the south wall open to a drop that kills, the red armor on an island in it (walkway round, or a circle jump
of 256 units: in the simulator a plain running jump falls short and a circle jump lands), a lava pit under the
catwalk (20 damage a second), a mound in the south-west corner, game textures and coloured light. Lava and the
drop are in the simulator (`hurt` in `rooms.json`); the group simulator still matches the two-player one.
Server commands `!reflex`, `!movement`, `!duel`. What went wrong on the way: the arena rebuild dropped the
course list from the test lab's data (`!movement` reported no courses) and the first version showed a lava
stripe on the cliff and sky where walls should be; all fixed the same evening.

## 2026-10-05 15:45 — built for tonight, not in training: groups of up to six, and the yard with items (B-86, B-87)

Owner's idea for after the 19:00 review: several bots at once, all against all, so there is more to dodge and
react to; and move them to the room with items. Built beside the running simulator so the run is not touched.
- `sim/duel_env_ffa.py` (written from `duel_env.py` by `tools/make_ffa_env.py`): groups of G players. Each one
  sees, hears and can hit every other; rockets splash on all; a shot on a line with two players hits the nearer.
  The enemy inputs describe the enemy he attends to: the noticed one nearest his crosshair (the current one
  preferred a little), else the one seen or heard last. 18 new inputs at the end (348 -> 366): two more enemies
  in view (there, where, direction, whether he faces this player), how many are in view, how many players.
  Reward as before: +1 a frag, -1 a death, damage dealt minus damage taken, whoever it is.
- Check (`tools/ffa_check.py`): with two players it is **identical to `duel_env` over 3000 frames** (same seed
  and actions; inputs, rewards and round ends compared; 50 frags and 19,700 damage in both). With 4 and 6 players
  in the environment box and in the yard it runs and fights (6 in the box: 145 frags in 75 s of 8 groups).
- The yard with items (`--map bobbyyard`, `ARENA_ROOMS=yard`): pickups work (weapons, red armor, mega), items
  come back on their timers and reset each round. Weapon sets by `ARENA_SETS` (`mg` = machine gun and gauntlet
  only, the duel spawn); `ARENA_STACK=0` turns the random health and armor off.
- A one-minute training test with four players in the yard (the v5 network widened): runs at the usual speed per
  player, he fights and picks weapons up (about one a minute per player).
- The league in a group: every second member of half the groups is played by a past version.
- Not done yet: the play-test server, the videos and the Nightmare benchmark still use the two-player simulator
  (B-88).

## 2026-10-05 09:26 — `duel_gru_v5`: arena fights only, with finger and sight limits (until 16:00)

Owner's change of course: become good at combat first, in the two boxes, and see what emerges; limit his actions
until the right kind of play appears. From `duel_gru_v4` at 1363 min (`policy_after_night.pt`); a new run name
because the meaning of the inputs changed (`duel_env_v4.py` is the frozen copy for older checkpoints).

- **Training:** only arena self-play on the test map, aim box and environment box half each; 60 s rounds; two
  random weapons (the same for both) in half the rounds, the full set in the other half; 125 health, no items;
  himself and up to eight older selves as opponents. Reward: frag +-1, damage dealt minus damage taken at equal
  weight, the small costs. Exploration bonus halved (0.005). No walk key, no demos, no courses, no Blood Run.
- **Finger limits (new):** one hand, five fingers. Ring = strafe left; middle = forward and back (no direct
  reversal); index = strafe right and the weapon keys; thumb = jump; little finger = crouch. A finger cannot act
  again for 150 ms (thumb 100 ms); the hand has 5 key actions a second (burst 3). Before the limit he asked for
  35-45 key changes a second; with it 5.2 are made and 93% of his requests are refused (start of the run).
- **Sight limits (new):** wall, floor and ceiling distances only inside a 100 x 75 degree view around where he
  looks; rockets seen in view or heard within 400 units; no waypoint compass on courses. Looking 60 degrees up
  he sees no walls and no floor (checked).
- Effect on the unadapted network in the environment box (60 s, simulator): no limits 2.4-3.5 frags per
  player-minute; sight limits alone 1.4-1.6; both 1.0-2.4.
- **Server:** `!arena box|env [minutes]` (COMMANDS.md); the same mode against Nightmare is the benchmark
  (`tools/bench_arena.sh`). First benchmark, 1368 min (before adapting), environment box, 5 min: **13-23**, damage
  1611 / 2360, speed 198 u/s, Nightmare in view 41% of the time, shotgun held 71% (Nightmare held it 78%).
  Two bugs found and fixed on the way: placing the game's bot froze it; a match start took the weapons away.
- Training speed 76k steps/s.

| Time | Train min | Key changes asked / made per s | Refused | Aim error in view | Standing | Looking up or down | vs Nightmare (env box, 5 min) |
|---|---|---|---|---|---|---|---|
| 09:33 | 1369 | about 70 / 5.2 | 93% | 12.0 deg | 12.5% | 1.9% | 13-23 |
| 10:15 | 1409 | - / 5.4 | 92.5% | 6.9 deg | 14.7% | 1.6% | - |
| 11:30 | 1483 | - / 5.5 | 92.7% | 5.4 deg | 12.5% | 0.7% | **28-15** (damage 3424 / 1642, speed 211 u/s, in view 32%, held LG 40% / HMG 39%) |
| 12:35 | 1543 (no HMG, aim nudged, env box only since 12:15) | - / 5.2 | 94.6% | 7.4 deg | 18% | 0.6% | 26-15 (damage 3133 / 1626, speed 191 u/s, in view 36%, held rail 70%) |
| 13:35 | 1575 (slower left hand since 13:13) | 17.6 / 4.6 | 95% | 6.1 deg | 27% | 0.4% | 32-10 (damage 3894 / 1126, speed 207 u/s, in view 35%, held rail 84%); rail 81%, MG 73%, LG 51%; rail 70% of kills; moving enemy takes 75 damage/s against 97 standing |
| 14:35 | 1640 (enemy movement read 200 ms late from 14:40) | 14.4 / 5.1 | 93% | 4.8 deg | 14.5% | 0.1% | 23-11 (damage 2856 / 1127, speed 166 u/s, in view 32%, held rail 82%); rail 85%, MG 75%, LG 52% before the nudge; rail 70% of kills |
| 15:40 | 1697 (rocket weapon sets, drawn per player, since 15:18) | 14.2 / 5.1 | 93% | 5.5 deg | 12% | 2.8% | **29-9** (damage 3534 / 1035, speed 205 u/s, in view 32%, held rail 83%); self-play: rail 78%, MG 69%, LG 55%, rockets 21%; kills rail 53%, LG 27%, MG 19%, rockets 1%; speed 254 u/s |
| 16:40 | 1754 | 13.0 / 5.2 | 92% | 4.7 deg | 9% | 3.2% | 7-2 only (damage 932 / 225, in view 10%: the two hardly met in this one, not comparable); self-play: rail 82%, MG 74%, LG 57%, rockets 41%; kills rail 56%, LG 25%, MG 18%, rockets under 1%; speed 267 u/s. **PC crashed about 16:50; restarted 16:54 from the 16:46 save (1766 min), about 5 minutes lost** |
| 17:40 | 1804 | 11.6 / 5.1 | 91% | 4.5 deg | 14% | 1.0% | 26-12 (damage 3250 / 1310, speed 210 u/s, in view 33%, held rail 85%); self-play: rail 82%, MG 78%, LG 60%; speed 248 u/s. Weapon use (`tools/weapon_use.py`, 3 min): damage rail 52%, LG 30%, MG 18%, **rockets under 0.5%**; rockets held 2% of the time he owns them (rail 96%, LG 52%). So he does not open with rockets and finish with something else: he hardly fires them, and the hit rates for rockets come from very few shots |
| 19:00 (end) | 1888 (more shake from 17:58, direction read with a 0.5 deg error from 18:18) | 9.3 / 4.9 | 90% | 4.6 deg | 14.5% | 1.2% | **25-11** (damage 3106 / 1221, speed 236 u/s, in view 31%, held rail 88%); self-play: rail 73%, MG 74%, LG 63%; speed 249 u/s; damage by weapon rail 52%, LG 28%, MG 19%, rockets under 0.5%; dodging: an enemy moving over 200 u/s takes 80 damage a second of fire, a standing one 67 (no gain from moving in this sample) |

**18:18 — coarser read of the crosshair against the enemy (owner)**: a slowly drifting error on the direction to an enemy in view, 0.5 degrees (one standard deviation) drifting over 150 ms, carried by every input that gives that direction (position, angles, the fine readings, the crosshair-on-him flag); `PERCEPT_SIGMA` (checkpoint before it: `policy_before_percept.pt`). The hand shake of 17:58 did not lower the hit rates in its first 20 minutes (rail 80%, machine gun 82%): a player is about 3.5 degrees wide at 500 units, so shake of hundredths of a degree does not move shots off him. First update after this change: rail 80% -> 73%, aim error 5.1 -> 5.3 degrees (one update, thin).

**17:58 — hand shake raised again (owner: aim still too good, one more nudge)**: the share of the view movement 0.10 -> 0.14, the constant shake 0.03 -> 0.05 degrees a frame (checkpoint before it: `policy_before_shake2.pt`). Before: rail 82%, machine gun 78%, lightning 60%, aim error 4.5 degrees; rockets under 0.5% of damage because the machine gun out-damages them at that accuracy.

**15:18 — weapon sets changed (owner's idea)**: each player draws his own set, a quarter each: rockets / rockets + lightning / rockets + rail / all three (machine gun and gauntlet always), so most fights are uneven and half his spawns have no rail (`ARENA_SETS`; checkpoint before it: `policy_before_rocketsets.pt`). Shotgun, plasma and grenades get no practice in this run. After 20 minutes: rail's share of kills 70% -> 53%, lightning 14% -> 27%, rockets still 1% of kills at 21% hits.

**10:10 — fight inputs added (owner: must have), network widened 311 -> 340 inputs at a checkpoint** (new inputs
get zero weights, so nothing learned is lost; `sim/widen_obs.py`; the 311-input checkpoint is kept as
`policy_311_inputs.pt`):
- enemy shots he saw or heard: firing now, time since the last shot (two scalings), which weapon it was (every
  weapon has its own sound), time until that weapon can fire again, seen or only heard: 14 inputs;
- the line of the enemy's last bullet, rail or lightning shot while it is on screen (nearest point, fading over
  a second): 4;
- the enemy in view: crouched, in the air: 2;
- his own hand: keys in effect, key budget, which fingers are free: 9 (so he can tell whether a press took).
Checked in the simulator: a rail seen gives "firing", weapon rail, 1.5 s counting down, a trail; a rail heard
from behind gives the weapon and no trail. On the server the enemy's shots are read from his ammo dropping.
Already present before: enemy weapon in hand while in view, the two nearest incoming projectiles, hit feedback.
Still not there: the enemy's health and armor (not knowable in the game either), more than two projectiles.

Found while reading the trainer: the damage part of the reward is 0.001 per point, not 0.004 (it fades with an
old curriculum setting that has long reached its floor). Kills at +-1 dominate; left as it is for this run.

**10:27 — right hand and zoom added (owner), damage reward 0.005; network widened to 343 inputs and a ninth
action head (zoom) at a checkpoint** (`policy_340_inputs.pt` kept):
- right hand: fire on the index finger (cannot change again for 75 ms: at most 6.7 clicks a second), zoom on
  the middle finger (150 ms);
- zoom, held: the view shrinks to 40% (100 x 75 -> 40 x 30 degrees, so the sight limits become tunnel vision),
  the same hand movement turns the view 40% as far (finer aim, 40% of the hand shake floor, top turn speed
  480 deg/s). The new head starts "off" 99% of the time; inputs: zoomed, fire finger free, zoom finger free.
- checked: ring walls seen 5 -> 1 of 16 when zoomed; an enemy 30 degrees off centre is seen unzoomed and not
  zoomed; the fastest turn covers 289 degrees in 10 frames unzoomed and 116 zoomed; a fire button asked to flip
  every frame changes 13.3 times a second.
- The damage reward is set outright to 0.005 per point from here (`--dmg-reward`).
Numbers at the restart (61 min of arena training): aim error 6.6 deg, rail 64%, LG 42%, MG 57%, HMG 56%;
frags by weapon HMG 64-66%, LG 13%, shotgun 11-13%; 61-67% of kills against his older selves; keys refused 92.5%.

**10:44 — tighter limits, random stacks, pain sounds (owner); network widened to 348 inputs** (`policy_343_inputs.pt` kept):
- crouch: the little finger rests 500 ms after acting (at most one crouch a second; measured 1.05); fire: 100 ms
  (at most five clicks a second; measured 4.0);
- arena rounds start both players on the same random health and armor, each one of 25, 50, ... 200 (checked);
- the enemy's health is not an input and never was; he has the damage of each of his own hits (the number a
  player sees) and the running total for this enemy life. New: the enemy's pain sound when hit within earshot,
  one of four by his health (under 25 / 50 / 75 / above), 5 inputs; checked against his true health.
Numbers at this restart (77 min of arena training): aim error 6.7 deg; 75% of kills against older selves;
standing 12%; zoomed 1.7%; keys refused 92.6%; HMG 67% of kills.

**10:50 — the yard: a small two-level duel arena on the test map** (owner: closer to the duel maps, for his
feedback; not in training). 1792 x 1536: open middle with pillars and low cover, a tunnel under the north
balcony, a low strip under the east balcony, balconies 192 up joined at the corner, a tower with a catwalk,
stairs, a ramp, a jump pad onto the tower, a teleporter from the tunnel to the far corner. Checked in the
simulator: stairs and ramp walk up to the balcony, the pad lands on the tower and catwalk, the teleporter and
all twelve spawn spots work. Server: `!arena yard`.

**11:30 — first win against Nightmare**: 28-15 in five minutes in the environment box (13-23 two hours of
training earlier). In training: hit rates rail 79%, MG 79-81%, HMG 79%, LG 50-66%; HMG 69-80% of kills, LG 12-21%;
zoomed 1.2-1.6%; crouched 6-7%; keys refused 92.7% (unchanged). To watch: the HMG has replaced the shotgun as
the one weapon, and tracking hit rates are back above the owner's card.

**12:08 and 12:15 — no HMG, aim limits nudged down, environment box only (owner)** (`policy_before_nohmg.pt` kept):
- the heavy machine gun is out of the test map's loadouts and aim rooms (most duel maps do not have one);
- aim limits: tracking delay 50 -> 75 ms, hand noise 0.08 -> 0.10 of the view movement plus 0.02 -> 0.03 degrees
  a frame; just before the change hit rates were rail 84%, MG 84%, HMG 82%, LG 51%, aim error 3.7 degrees;
- arena rounds only in the environment box (LG and HMG ruling an empty box is no surprise).
Five minutes after: kills by weapon LG 41%, rail 35%, MG 12%, shotgun 10%; rail 72%, MG 67%, LG 54%; enemy in
view 42% (70% with the open box in the mix); aim error 7.7 degrees; standing still 22%.

**12:50 — `bobbyyard`: the yard as its own small duel map with items** (owner; for his feedback, not in training).
Mega health on the tower (where the jump pad lands), red armor in the tunnel's west end, railgun on the north
balcony's east end, rocket launcher on the open ground south-east, lightning gun under the east balcony, two
25-health and two shards. Its own map file so that the test map and the running training are untouched
(`maps/bobbyyard/`; `tools/make_lab_map.py` writes both). On it nobody is handed weapons: the game's duel
spawn. Checked: loads in the simulator and on the server; in three minutes against Nightmare both bots picked
items up (Nightmare the red armor ten times and the mega six).

**12:30 — does moving protect him?** (`tools/dodge_check.py`, two minutes of self-play in the environment box):
damage per second of firing at an enemy in view is 87 when he stands, 70 when he moves slowly, 71 above 200
u/s: moving costs the shooter about 18%. He moves sideways at 156 u/s with the enemy in view and changes
direction 0.3 times a second.

**13:13 — the left hand slowed down (owner: 40 key decisions a second is far too many; bursts yes, but not for long)**
(`policy_before_keyrate.pt` kept):
- the left hand decides ten times a second: keys and weapon choice are read from the network every fourth frame
  (staggered by player) and held in between; the mouse and the fire button stay at 40 a second;
- stamina: a burst of up to 10 key actions, refilled at 4 a second (was burst 3, 5 a second). Random mashing gets
  13.5 actions into the first second and 4.0 a second after that (measured);
- exploration bonus per action: none on the movement keys and the fire button, a quarter on the mouse, half on
  the weapon choice, full on zoom (so that zoom still gets tried). Owner asked about removing it altogether:
  kept small where a choice could otherwise freeze before it has been explored.
- Fight videos now show the keys his fingers pressed, not every request (they had shown the requests).
Before: he asked for about 40 key changes a second. Right after: 17.6 asked, 4.6 made.
The trainer was found dead at 13:10 (stopped without an error message some time after 12:50; memory was not
short); restarted from the 12:43 checkpoint, about 25 minutes of training lost.

**14:40 — aim down one more notch (owner: getting quite good)** (`policy_before_velreact.pt` kept): how the enemy
is moving is now known 200 ms late (where he is: still 75 ms). A person follows steady movement closely and
needs about that long to pick up a reversal; it also makes a change of direction worth something to the one
being shot at. This is the single extra nudge the owner allowed for the day.

After 46 minutes of arena-only training: aim error in view 12 -> 6.9 degrees, hit rates rail 34 -> 69%, LG
24 -> 42%, MG 26 -> 59%, HMG 21 -> 51%; frags by weapon HMG 43%, LG 21%, shotgun 20% (72% at the start).

## 2026-10-05 08:50 — does a bigger network help? (imitation test on the pro demos) and the new mix's smoke test

**Size test** (`sim/bc_size_test.py`): the same kind of network at three sizes, imitation only, 160 Blood Run
demos (25 hours) for 8 minutes each, scored on 30 demos (4.6 hours) it never saw.

| Layers x memory | Weights | Steps in 8 min | Held-out loss | Movement keys right | Turn within one bin |
|---|---|---|---|---|---|
| 256 x 512 (current) | 1.4 M | 21,651 | 3.38 | 78.6% | 74.0% |
| 512 x 1024 | 5.2 M | 20,645 | 3.81 | 75.3% | 72.4% |
| 512 x 2048 | 16.3 M | 8,718 | 3.89 | 74.8% | 71.6% |

The current size predicts unseen pro play best; both bigger ones are worse on every head. Limits of the test:
equal time, not equal steps (the largest got 40% of the steps); 25 hours of data, where a bigger network
overfits sooner; no tuning per size; it measures copying pros, not learning by self-play. Reading: nothing here
says the network is too small. The current size stays.

**Smoke test of the next mix** (9 minutes from the night's checkpoint; arena 26%, run-and-gun 21%, aim 21%,
Blood Run duels 16%, courses 16%; damage taken at equal weight; walk key off; no demos): runs at the expected
speed. Arena: 6 -> 9.5 frags per player-minute, enemy in view 64% -> 70%, speed 245 -> 199 u/s (he stands and
shoots in the boxes: to watch). Run-and-gun: damage 834 -> 1744 a minute, speed with a target about 280 u/s,
not rising yet. Aim error in view 16 -> 10 degrees. Walk 0%.

Also after the PC crashed at about 08:10: nothing was training; checkpoints and code intact; the size test and
one video were redone; play-test server restarted. All demos are downloaded (Blood Run 1293, Aerowalk 1012,
Lost World 1411; only Blood Run converted).

## 2026-10-04 21:12 — overnight run: combat, movement rooms, pro demos (`duel_gru_v4` from 775 min, until 07:00)

Owner's plan: three parts of equal weight, Blood Run only for the real map. What was built, checked and started:

- **Shotgun check.** Real game 100 / 61 / 26 damage at 100 / 300 / 600 units (four shots each, stored
  measurements), the same as the simulator. The habit is not a simulator error.
- **Combat (half of the playing time).** Self-play duels on Blood Run. Spawn: 50% machine gun and gauntlet only
  (the real duel spawn), 30% one or two random weapons from the map, 20% every weapon on the map; never a
  shotgun at spawn (checked on 512 spawns: 49% / 29% / 23%, shotgun 0%). Item reward doubled (0.6 per 100 points).
- **Movement rooms (half of the playing time).** Thirteen courses with equal time (speed, circle, twohop, ramps,
  slalom, turns, narrow, pillars, rocket, bends, pads, drops, climb), the items room (a pickup pays 0.5; mega and
  red armor on their timers; two-minute rounds), 10% of this half in aim rooms. `dodge` is not in the simulator.
  Checked with a scripted runner: every course starts and measures progress; the straight line through `drops`
  kills (1 health); jump pads and the teleporter work; items give their reward and respawn after 35 s / 25 s.
- **Pro demos.** 367 Blood Run demos converted (`sim/demo_dataset.py`, 95% of frames kept); the inferred keys
  reproduce the recorded next-frame velocity to a median of 2.3 u/s (23 u/s without keys). Newly downloaded
  demos are converted every 45 minutes and join in.
- **What did not work: equal weight for the demos.** Smoke tests, 8 minutes each from the same checkpoint:

| Demo loss | Pro keys predicted | Hit rate RL / RG / LG at the end | Aim error in view | Crouch / walk |
|---|---|---|---|---|
| none (control: new spawn rule only) | - | 0.58 / 0.74 / 0.69 | 9.9 deg | 25% / 39% |
| weight 1.0, all heads (the "equal weight" setting) | 36% -> 61% | 0.10 / 0.13 / 0.13 | 18.2 deg | 5% / 1% |
| weight 0.2, keys + turn at a quarter | 33% -> 54% | 0.27 / 0.68 / 0.55 | 19.0 deg | 7% / 4% |
| weight 0.2, keys only | 34% -> 52% | 0.41 / 0.71 / 0.60 | 19.0 deg | 8% / 6% |

  At full weight on every head his aim collapsed within minutes: the demo inputs lack the enemy's health, sounds
  and hit feedback, so copying the pros' mouse and trigger from them is wrong. With the movement keys (and a
  little of the turn) at weight 0.2 the hit rates hold, walking and crouching all but disappear, and the error
  to the target while it is in view doubles: he moves at speed now and has to learn to aim while doing it. The
  run uses that setting. Whether the aim error comes back down is the thing to watch tonight.
- A first launch at 21:06 used the old settings by mistake (the new command file had not been written); it was
  stopped after five minutes and the checkpoint restored from `policy_before_night.pt`.
- Speed: 58k steps/s with the demo batches (63k without).

### Hourly reports of the night

| Time | Train min | Speed straight | Pro keys right | Aim error in view | Crouch / walk | Shotgun frag share | Nightmare, 10 min (all weapons in hand) | Speed in duels (simulator) |
|---|---|---|---|---|---|---|---|---|
| 21:12 | 775 | 361 | 39% | 8 deg | 25% / 35% | 84% | (19:00: 6-21, 116 u/s live) | 106 u/s (17:00) |
| 22:15 | 836 | 796 | 74% | 13-20 deg | 10% / 12% | 6% | 0-11, 330 / 1232 damage, 87 u/s, in view 4%, shotgun held 76% | 136 u/s, above 330 u/s 3% of the time, in view 8% |
| 23:15 | 893 | 707 (finishes 8 of 13 courses; not circle, twohop, pillars, rocket) | 77% | 16 deg | 12% / 39% | 4% | 1-24, 1405 / 2973 damage, 140 u/s, in view 11%, shotgun held 81% | 184 u/s, above 330 u/s 6%, in view 6% |
| 00:15 | 955 | 777 (first finishes on circle) | 79% | 12 deg | 21% / 33% | 11% | 1-18, 975 / 2155 damage, 135 u/s, in view 9%, shotgun held 80% | 168 u/s, above 330 u/s 6%, in view 12% |
| 01:15 | 1016 | 814 | 80% | 18 deg | 16% / 25% | 7% | 0-21, 870 / 2485 damage, 113 u/s, in view 10%, shotgun held 79% | 133 u/s, above 330 u/s 4%, in view 12% |
| 02:15 | 1074 | 827 (circle now finished 1.3 times a minute) | 80% | 18 deg | 26% / 35% | 14% | 0-21, 586 / 2699 damage, 132 u/s, in view 12%, shotgun held 61% | 143 u/s, above 330 u/s 6%, in view 9% |
| 03:15 | 1135 | 857 (first finishes on twohop) | 82% | 21 deg | 31% / 43% | 4% | 0-24, 1340 / 3006 damage, 140 u/s, in view 13%, shotgun held 69% | 140 u/s, above 330 u/s 5%, in view 9% |
| 04:15 | 1196 | 818 (circle 3.4 finishes a minute) | 80% | 25 deg | 29% / 42% | 12% | 1-18, 1210 / 2447 damage, 167 u/s, in view 10%, shotgun held 65% | 127 u/s, above 330 u/s 4%, in view 19% |
| 05:15 | 1254 | 868 | 81% | 14 deg | 38% / 43% | 12% | 0-22, 1335 / 2906 damage, 161 u/s, in view 11%, shotgun held 62% | 138 u/s, above 330 u/s 6%, in view 25% |
| 06:15 | 1314 | 914 | 82% | 16 deg | 33% / 44% | 14% | 0-25, 965 / 3241 damage, 156 u/s, in view 13%, shotgun held 60% | 128 u/s, above 330 u/s 5%, in view 23% |

| 07:00 (final) | 1361 | 966 | 82% | 15 deg | 31% / 45% | 5% | 0-24, 1390 / 3366 damage, 165 u/s, in view 13%, shotgun held 60% | 132 u/s, above 330 u/s 5%, in view 28% |

### Result of the night (1361 min, `suite/lab_1363`, checkpoint `policy_after_night.pt`)

- **Courses: clearly better, several past the owner.** Speed straight 19.1 s at 971 u/s (owner 28.1 s, 718);
  ramps 14.8 s (19.7 s); narrow 13.5 s (14.4 s); circle 8.0 s (13.6 s); drops 7.5 s (11.3 s). Slower than him on
  slalom (24.2 s against 19.3 s), bends (26.8 s against 15.4 s), turns, climb. Never finished: twohop, pillars,
  rocket. Items room: 3.3-4.4 megas per two minutes of 4 possible, red armor never.
- **Duels: no better.** Nightmare 0-24 at the end and never more than one frag in ten minutes all night
  (6-21 before the run). Speed in Blood Run duels about 130 u/s throughout; walk 45%, crouch 31% of frames.
- **Aim: much worse in the aim rooms.** Hit rate walk / jump / environment, before -> after: LG 87 / 90 / 69 ->
  32 / 30 / 24; MG 88 / 84 / 73 -> 52 / 51 / 42; HMG 87 / 85 / 75 -> 40 / 41 / 19; plasma 55 / 53 / 51 ->
  24 / 23 / 19; rail 90 / 88 / 85 -> 72 / 68 / 50; rockets 61 / 41 / 60 -> 43 / 31 / 32. He now keeps the
  target in view about 87% of the time (30-45% before), so damage per second is about the same; the
  precision is what went. With 5% of the time in aim rooms and a demo loss on the turn, nothing held it.
- **What did not work:** equal thirds did not produce movement in fights; the demo loss on movement keys changed
  his keys for an hour and self-play undid it; nine hours without progress in duels.
- **Why (reading, not proven):** damage taken costs double what damage dealt pays, so avoiding each other is
  rational in self-play; demos show pro situations, not his; courses teach speed with nothing to shoot.

01:50: run-and-gun round built in the simulator (B-81), **not switched on** (`--lab-gun`, off by default): the
runner has a weapon on the speed, slalom, ramps or turns course, a target keeps appearing 500-900 units ahead
beside the path, and damage pays in proportion to his speed. First measurement with tonight's checkpoint (1016
min, lightning gun): on the speed straight he runs 735 u/s alone and 295 u/s with a target in view (in view
99% of the time, 1397 damage a minute); turns 401 -> 294 u/s. He slows to walking pace to shoot: this round
measures exactly the habit it is meant to train away.

22:20: the speed is in the courses only. In Blood Run duels in the simulator he still moves at 136 u/s and the
two players see each other 8% of the time: self-play duels have become avoiding each other. Given every weapon
he still takes the shotgun (76%). Left running as planned; this is the finding to act on in the morning
(candidates: B-81 run-and-gun, the double weight on damage taken, movement rounds on Blood Run itself).

## 2026-10-04 20:15 — Lost World replaces Campgrounds; older pro demos

- Lost World: map file taken from the server's game data, route graph built by the simulator (1272 spots, 7126
  walk links, 11762 air links, 29 teleporter links), loads in the duel simulator (weapons on the map: RL, LG, SG,
  GL, PG; one teleporter, two jump pads). It takes the third map slot of the inputs (was Campgrounds). Atlas
  built from the graph only so far.
- Demo site totals for Blood Run duels: 1309 (1071 in the 2009-2014 format `.dm_73`, which the parser reads;
  236 `.dm_91`). The 1071 older ones are downloading; Aerowalk and Lost World follow in the same queue
  (`data/fetch_more.cmd`).

## 2026-10-04 20:05 — test map: seven more rooms, rocket ledges lowered (owner)

- New: `move bends`, `move pads` (jump pads and a teleporter: the map builder now writes trigger and item
  entities), `move drops`, `move climb`, `move dodge` (Bobby's body is a rocket turret that leads its target),
  `peek` (rail duel through gaps; the opponent stands still and shoots back; nobody dies), `items` (mega health
  and red armor on their real timers in a ring corridor).
- Rocket ledges about 30% lower: steps of 160, 224, 280 and 448 (was 224, 320, 400, 640).
- Checked in the simulator: floors along every path; a player holding forward takes the first pad onto the
  ledge, is teleported, takes the second pad over the wall and reaches the end; the climb works with hops.
  Not yet seen in the game itself: the turret, the peek duel and the items room are new server code.
- Spawn weapons are now limited to the weapons that lie on the map (simulator and server).

## 2026-10-04 19:45 — test map: owner's review of the new movement rooms

- `turns` was an empty room: its corridor walls were dropped by the map compiler (footprints wound the wrong way).
  Rebuilt as plain rectangles with short walls across the two sharp corners (mitred corners gave the bot
  navigation compiler more planes than it accepts); checked in the simulator: walls on both sides, sealed.
- `twohop`: every platform has a dark pad (start of the run) and a line (first jump); a fall puts you back on the pad.
- `pillars`: 18 pillars instead of 36. `rocket`: a fourth ledge, 640 high (needs a double rocket jump).
- The game's bot in `!spar` and the fight room is Nightmare again (`SKILL=4` gives Hardcore).
- `tools/build_lab_map.sh` builds the map in one step.

## 2026-10-04 19:40 — map atlases built (B-75, first version)

- `tools/build_atlas.py` -> `maps/atlas/<map>.json` and `.png` (see ATLAS.md). Blood Run: 26 areas, 10 big items,
  224 pro demos, 81,084 trips, 2.8 routes per (area, item); in 140 of 240 pairs pros use two or more routes.
  Aerowalk: 20 areas, 148 demos, 45,885 trips. Campgrounds: built from the graph only (its six demos are not parsed).
- Pro play adds routes the route graph does not have (Blood Run: 47-odd per map, for example a 0.6 s way to the
  red armor the graph takes 7.6 s for), which also shows where the route graph is missing jumps.
- Pros on Blood Run spend most time around mega health (12%), the grenade launcher (9%), red armor (7%).
- Also today: `!nosg` on the play-test server (spawn with every weapon except the shotgun).
- Not done: nothing reads the atlas yet; areas are clusters, not rooms; arrival is not pickup.

## 2026-10-04 16:55 and 17:32 — `duel_gru_v4`: self-play only, less aim, no shotgun at spawn (owner)

- 16:55 (650 min): scripted fighters removed from duel rounds (`--bot-p 0`): duels are Bobby against himself and
  his older snapshots. The game's bots are for benchmarking only and are never trained against.
- 17:32 (686 min): playing time recut to self-play duels 50%, lab movement courses 30%, stock-map movement 10%,
  aim rooms 10% (about 7% stock, 3% lab). To break the shotgun habit nobody spawns with a shotgun in duel
  rounds any more (`NO_SG_SPAWN=1`, and it is out of the same-single-weapon rounds): as in the real game it has
  to be picked up. Checkpoints kept: `policy_before_selfplay.pt`, `policy_before_mix3.pt`.
- Hourly benchmark against Nightmare (Blood Run, five minutes, every weapon in hand):

| Training min | Score (Bobby-Nightmare) | Damage dealt / taken | Mean speed | Enemy in view | Weapon held |
|---|---|---|---|---|---|
| 686 (before this change) | 1-10 | 1320 / 1278 | 95 u/s | 10% | shotgun 86% |
| 704 (22 min after) | 7-5 | 1355 / 872 | 120 u/s | 12% | shotgun 87% |
| 775 (final, ten minutes) | 6-21 (5-10 at five minutes) | 2625 / 2814 | 116 u/s | 12% | shotgun 87% |

The 7-5 was a lucky five minutes: over ten minutes the final checkpoint lost 6-21. Benchmarks need ten minutes or more.

### `duel_gru_v4` final (775 min, 19:00)
- Training (self-play only for the last two hours): frag share LG 32%, HMG 16%, rail 14%, SG 10%, MG 10%, RL 9%,
  PG 8%; hit rates LG 72%, rail 84%, RL 56%; 7.4 switches a minute; blind fire 0.0%; crouch 29% and walk 39% of
  frames (rose all afternoon); enemy in view 9% of the time.
- Courses in training: speed 679 u/s, ramps 549, slalom 406. Lab card (`suite/lab_0775`): speed straight mean
  704 u/s (owner 718), ramps 581 (owner 605), slalom 405 (owner 550). Untrained courses (circle, twohop, turns,
  narrow, pillars, rocket): none finished.
- Lab aim rooms: hit rates at or above the owner's (LG 87 / 90 / 70% against 51 / 89 / 55; rail 90 / 88 / 85
  against 70 / 100 / 57; rockets below: 61 / 41 / 60 against 89 / 83 / 88), but damage per second is mostly
  lower than his because he has the target in view only 20-45% of the time with the tracking weapons: he looks
  away between bursts.
- What did not work: with every weapon in hand at spawn he still holds the shotgun 87% of the time and walks
  (116 u/s) on a real server; movement speed from the courses does not carry into fights; he loses clearly to
  Nightmare.

## 2026-10-04 16:30-17:10 — `duel_gru_v4` on a real server (plugin update, B-57)

- The plugin now plays networks trained under the newer rules (311 inputs: clock, score, sounds, hit feedback,
  crouch, walk, noticing delay, flick cap, hand noise, reload delay). No frame errors in 15 minutes of sparring.
- **Bug found and fixed: weapon switches were cancelled live.** The plugin sent the new weapon number for one
  frame; the game needs it held for the whole switch (0.4 s) and otherwise falls back. The chosen weapon is now
  remembered, as in the simulator. This bug was present in every earlier play test.
- Live rounds now match training: clock, score and memory start over every two minutes.
- Sparring opponent changed from Nightmare (skill 5, which cheats) to Hardcore (skill 4), owner's decision.
- Spar at 629 min, Blood Run, all weapons: 2-8 in five minutes against Hardcore. Shotgun in hand 84-100% of the
  time, mean speed 130 u/s, enemy in view 14% of the time, damage dealt 1505 against 977 taken.
- **Not a transfer problem:** the same network in the simulator under the same conditions (Blood Run, all weapons,
  two-minute rounds, scripted all-round fighter) holds the shotgun 100% of the time at a mean speed of 106 u/s,
  and wins there (32 frags, 5750 damage dealt against 2452 taken). With every weapon in hand he has learned
  "walk slowly with the shotgun". What did not work: random loadouts and the round recut have not broken the
  shotgun habit in full-loadout fights, and course speed (500 u/s) does not carry into fights.

## At a glance

| Worked | Did not work |
|---

## 2026-10-04 (15:27): `duel_gru_v4` recut (owner's mix), heavier damage penalty, teacher removed

Resumed from `policy_before_recut.pt` (561 min) until 19:00.
- Playing time: stock maps 67% (12 of 18 workers) = normal duels 44%, movement 11%, aim 11%; lab map 33% =
  courses (speed, slalom, ramps) 22%, lab aim rooms 11%. The owner's shares (40 / 10 / 10 / 20 / 10) summed to
  90 and were scaled up.
- Normal duels: 40% one or two random weapons per player, 20% real duel spawn, 20% every weapon, 20% the same
  single weapon for both (the old single-weapon rounds, now inside normal duels).
- Damage taken, from any source (opponent, own splash, falls), now weighs twice as much as damage dealt.
- The movement teacher is off (owner: its settings were too different to help further). It lifted fast-air in
  item runs from 8% to 32-34% in its 80 minutes.
- Lab aim rooms: the subject starts having already noticed the target, like a person after the countdown.

Before the recut (25 minutes with the courses): speed straight 482 u/s average, ramps 435, slalom 329 (361 / 361 /
306 at the start); crouch 19% and walk 30% of the time.

**Server tick rate checked:** Quake Live locks `sv_fps` at 40 (setting 125 on the command line is ignored;
frames measured at 25.0 ms). A "better" server can only come from hardware and network, not from a higher tick.

---

## 2026-10-04 (15:01): `duel_gru_v4` restarted with lab movement courses

Starts B-68. The run was stopped right after a checkpoint (`policy_before_courses.pt`, 536 min) and resumed
until 19:00 with the test map as a fourth training map: 4 of 18 workers (22% of playing time) run the speed,
slalom and ramps courses, rewarded by progress along the course. On the other three maps the time split is
45% normal, 18% aim, 12% single weapon, 25% movement. The lab aim rooms are not in training yet.

Before the restart (48 minutes of the new rules): frags by weapon LG 22%, shotgun 24%, rail 16%, plasma 10%,
HMG 10%; switches 8.6 per minute; movement rounds 355 u/s with 34% fast-air; ahead of every scripted style
except the tracker (1.8 frags to 1.9 deaths per minute); crouches 16% and walks 27% of the time, which is more
than expected and worth watching; fall damage 11 points per player-minute.

LG aim rooms on the lab map now keep the target inside lightning gun range (zone 256-670 units from the subject).

---

## 2026-10-04 (14:30): owner's test-chamber card, lab rooms in the simulator, `duel_gru_v4` started

Settles B-57 (simulator half), B-34. Raises B-67, B-68.

**Owner's card** (`data/duellive/suite/human_20261004-183837.json`, lab map, 15 s aim rooms):

| Weapon | Walking target | Jumping target | Environment box |
|---|---|---|---|
| LG | 51% | 89% | 55% |
| Rail | 70% | 100% | 57% |
| Shotgun (pellets) | 42% | 57% | 44% |
| Machine gun | 58% | 80% | 54% |
| HMG | 51% | 63% | 49% |
| Plasma | 46% | 59% | 47% |

Crosshair about 4 degrees off a walking target, on target 54-56% with LG. A jumping target is much easier than a
walking one. Movement: speed straight 718 u/s average and 854 top (20,300 units in 28 s), ramps 605, slalom 550;
the old gaps course was not finishable (4 falls). The owner rates his aim "decent, not great": Bobby may sit a
bit above these numbers, not far above.

**Did not work on the lab map:** a placement spot inside the raised platform (invisible Nightmare bot, respawn
inside solid); removing weapons without removing the one in hand (rocket launcher in movement rooms); targets
warped back at walls; trick-jump stations (dropped: unclear what they test); the 480-unit gap (not clearable
while strafe jumping).

**Lab map now:** aim box, environment box, nine movement courses (speed, circle-jump gaps, two-hop gaps, ramps,
slalom, turns, narrow path, pillars, rocket jumps), one fight against the game's Nightmare bot.

**Lab rooms in the simulator** (`sim/duel_env.py` lab mode, `sim/test_suite.py --lab`): the rooms are read from
`maps/bobbylab/rooms.json`, so courses added to the map need no code. Checked with scripted players: course
progress, falls and checkpoints, finish; target zones and jumping.

**First lab card for Bobby** (`duel_gru_v4` at 501 min, 13 minutes into the new rules;
`data/sim_runs/duel_gru_v4/suite/lab_0501.md`): aim rooms 2-9% hit rate with the crosshair 16-26 degrees off;
speed straight 395 u/s average, 501 top; turns 10,650 of 11,900 units; slalom stuck at the walls; circle,
two-hop, narrow and pillars: 9-24 falls, no progress past the first obstacles; rocket course: first ledge only.
- Why aim is so low there while it is 40-70% in his training rounds: at the start of a room he turns away
  before the new 200 ms noticing delay has passed (0 to 72 degrees off in 8 frames), the target then leaves his
  view, and he takes seconds to find it again. The map is also new to him. The human starts each room already
  looking at the target after a countdown. Not a scoring bug: his error at frame 0 is 0 degrees.
- LG reaches 768 units and half of the aim box's target zone is beyond that from the subject's start.

**`duel_gru_v4`** started 14:08 (widened from v3; outputs identical before training). First launch stalled: 6.4 s
sequences filled the GPU memory; restarted with 24 minibatches. 56-61k steps per second. At 14 minutes: frags
spread over weapons (LG 24%, shotgun 20%, rail 15%), movement rounds 335 u/s with 32% fast-air (8% before),
beats the rusher, jumper and spammer styles, loses to the sniper, dodger and allround.

---

## 2026-10-04 (afternoon): `duel_gru_v3` final, second human play test, changes approved for the next run

Settles B-38, B-43/B-44 (built), raises B-57 to B-60.

**Final card, 489 minutes** (`data/sim_runs/duel_gru_v3/suite/card_0487.md`, endless ammo in aim rooms):
LG 82% and rail 94% on a fast-strafing target at mid range, shotgun pellets 70%; shotgun held 94-99% at every
range; movement 283 u/s; solo 0.88 megas and 0.35 red armors per minute; scripted fighters: 4.3 frags to 1.2
deaths per minute against allround, 3.0 to 2.4 against the sniper, 3.6 to 2.2 against the tracker.
First live minutes against Nightmare: 2-2 with even damage (yesterday's version: 0-10).

**Owner's play test** (sessions `data/duellive/sessions/20261004-17*_human`): much better, still easy to beat.
- Hitscan aim is superhuman: turns onto the player instantly, never misses, tracks with the shotgun like nobody can.
- Taps the LG trigger instead of holding it; fires on the exact frame a reload ends.
- Always has the shotgun out; could not be coaxed onto other weapons.
- Does not pick up items or move fast; stands in odd spots; takes every fight he sees, even from a bad position;
  works his way around a wall toward the player instead of finding a better position.

**What did not work in v3:** one-sided damage reward (dealt only) made every sighting worth fighting; a 25 ms
reaction with no hand limits gave inhuman aim; all-weapon spawns let him settle on one weapon.

**Approved for the next run (built in `sim/duel_env.py`, not trained yet):**
- Aim limits: 200 ms before a newly visible enemy is noticed, 50 ms tracking delay, flick cap 1200 deg/s, hand
  noise proportional to view speed, 0-120 ms random delay after the reload of slow weapons, a cost per change
  of the fire button. Weapon fire is heard by the enemy (B-47).
- Weapons: 60% of normal rounds with 1-2 random weapons per player (drawn independently), 20% real duel spawn
  (machine gun + gauntlet), 20% all weapons. Half of normal rounds against the eight scripted styles.
- Fights: damage reward is now dealt minus taken. Horizon 0.998, memory across deaths, 311 inputs (B-47, B-48).
- Movement: strafe-jump teacher, long drills, 35% of playing time (B-43).

**Test map** `bobbylab` built (B-33/B-34 follow-up): aim box, environment box, speed straight, and 3D copies
(8-unit blocks) of four trick spots. Compiled with q3map2; bots need the `.aas` (mbspc `-forcesidesvisible`).
Lab rooms run on the server (41 rooms, about 29 minutes); the simulator side of the lab rooms is still to do (B-57).

**Repo:** the first approach (Nightmare layer, coach, cluster) moved to `legacy/`.

---

## 2026-10-04 (09:10): built for the next run: movement teacher and opponent styles

Builds B-43, B-44 (owner: "2 and 3, different types of opponent behavior, good or bad, and movement drills
for building and maintaining speed").

- **Movement teacher.** In movement rounds the three-map movement policy (`multimap_v1`, which strafe-jumps)
  is asked what it would do from the same spot, and its (sampled) keys and turn are offered as labels; the
  trainer adds an imitation loss that fades out (`--teach 0.5 --teach-minutes 240`). Check: players that
  simply follow the labels in the duel simulator move at 390 u/s with 41% fast-air (Bobby alone: 302 u/s, 8%).
  A fresh network with the loss reached 311 u/s and 26% fast-air in 75 seconds of training.
- **Movement drills.** Goals 3-20 s away (were 1.5-12), 40 s rounds so several goals chain, and the arrival
  bonus grows with arrival speed. Default time share of movement rounds 35% (was 15%).
- **Opponent styles** for the scripted fighter, half of normal rounds: allround, sniper (rail, keeps
  700-1200 units), rusher (rockets at the feet, always closing), tracker (LG at 250-550), dodger (fast
  direction changes, backs off when hurt), and deliberately bad ones: stander, jumper (straight line,
  always jumping), spammer (fires blind, random weapons). Results per style are logged (`vs_persona`), and the
  test suite and the live rooms have one ladder room per style (`!room ladder sniper`).
- **Did not work:** building the teacher with its own simulator world corrupted memory (worlds share buffers
  sized by player count); it now reuses the duel world. Importing torch inside a worker crashed numpy; the
  teacher loads plain numpy weights.

---

## 2026-10-04 (08:30): pickups measured, spawn ammo raised, and why he holds the shotgun

Settles B-38 (owner: spawn with normal pickup ammo) and most of B-14.

**Pickups measured on a real server** (`plugins/itemlab.py`, `data/itemlab/`, three maps, first pickup from empty):

| Item | Gives |
|---|---|
| Weapons | RL 10, RG 10, LG 100, SG 10, GL 10, PG 50 |
| Ammo boxes | rockets 5, slugs 5, lightning 50, shells 5, grenades 5, cells 50, bullets 50 |
| Health | 5 / 25 / 50 / mega 100 |
| Armor | shard 5 / 25 / 50 / 100 |

The simulator had weapon pickups RL 5, RG 5, GL 5 and ammo boxes lightning 60, shells 10: corrected. Spawn
loadout is now one pickup's worth per weapon (was RL 10, RG 5, LG 60, GL 5). Still unmeasured: ammo caps,
a weapon picked up when already owned, damage through armor, HMG (not on these maps).

**Shotgun: not a bug.** After the ammo change and a random spawn weapon he still selected the shotgun
98-100% of the time in normal rounds. Forcing each weapon in the weapon-choice room (Blood Run, fast target):

| Forced weapon | Close: kills/min | Mid: kills/min | Far: kills/min |
|---|---|---|---|
| his own choice (shotgun) | 17.5 | 13.7 | 2.2 |
| shotgun | 19.9 | 13.6 | 2.7 |
| LG | 18.4 | 13.8 | 2.8 |
| rail | 16.4 | 12.2 | 1.9 |
| rockets | 14.2 | 8.9 | 1.6 |
| plasma | 20.7 | 13.5 | 2.6 |

Every weapon gives him about the same kills per minute, because his time per kill (about 4 s) is mostly
finding and turning onto the target, not the weapon. With a switch costing time and reward, staying on one
weapon is rational. The simulator's shotgun matches the real one (100 / 61 / 26 damage at 100 / 300 / 600
units measured, same in the simulator). Weapon choice will only matter against opponents that punish it;
that is a job for stronger opponents and the human play test, not for a reward on weapon use.

---

## 2026-10-04 (morning): crash at 00:40, test-suite card at 231 minutes, costs raised

Raises B-39. Settles nothing yet (run resumed until 12:00).

- The PC blue-screened at 00:40 (bugcheck 0x1E; the earlier one on 10-01 was 0xD1), 231 minutes into
  `duel_gru_v3`. The checkpoint from 00:40 survived (`policy_0231_crash.pt`); about six hours of training
  time were lost. Resumed at 07:35.
- Test suite card at 231 minutes (`data/sim_runs/duel_gru_v3/suite/card_0230.md`, three maps):
  - Aim at 350-650 units: LG 50-56% hit rate on every target type, rail 62-65%, rockets 46-51% (direct or
    splash). Close range: LG 73%, rail 79%. Far (800-1200): 11-16%, he loses sight of the target
    (in view 12-16% of the time).
  - Weapon choice: shotgun 87-98% at every distance.
  - Movement: 10.8 arrivals per minute, 302 u/s, 8% fast-air.
  - Solo: 0.29 megas and 0.39 red armors per minute; fire held 42% of the time with nobody there;
    448 switches per minute.
  - Scripted fighter: 3.0 frags to 1.4 deaths per minute.
- **Did not work:** the 0.002 switch cost and 0.0005 blind-fire cost. Both were about ten times smaller than
  the entropy bonus PPO pays for keeping those choices random, so with no enemy around he switched and fired
  at random (solo room: 448 switches per minute). Raised to 0.02 per switch and 0.003 per frame of blind
  fire. Nine minutes after the restart: switches 191 -> 9.6 per minute, blind fire 22% -> 8.5%.
- Still open: shotgun preference (B-38).

---

## 2026-10-03 (23:15): `duel_gru_v3` at 149 minutes, two simulator defects fixed mid-run

Raises B-37, B-38. The run was stopped and resumed from its checkpoint twice (about 10 minutes lost);
`policy_before_switchfix.pt` is the checkpoint from before the fixes.

At 149 minutes: crosshair error in view 8.7 degrees (38 at the start), on target 66% of the time in view,
LG 28% and rail 29% hit rate, 2.4 frags to 1.3 deaths per minute against the scripted fighter, 70% kill share
against older snapshots, movement rounds 293 u/s. But: shotgun held 88-95% of the time at every range and
84% of frags, and switches back up to 144 per minute.

Defects found:
1. **Switching during a reload was free.** In the game a weapon change only starts once the reload from the
   last shot is over; the simulator let the 0.425 s switch run inside the reload, so flicking weapons after a
   shotgun or rail shot cost nothing. Fixed: the switch now waits for the reload (`fire_cd`). Not yet
   measured on the real server for the firing case (B-37); it follows the Quake 3 rule.
2. **The round mix was a share of round starts, not of playing time.** Normal rounds last about 100 s and the
   others 10-15 s, so about 86% of playing time was normal rounds and aim rounds got about 6%, not 25%.
   Fixed: `kind_p` is now the share of time.

Not changed (decision for the owner, B-38): the spawn loadout gives 10 shells but only 60 cells and 5 slugs,
so the shotgun carries the most damage per spawn (about 1000 potential against 360 for LG). The shotgun
preference may be a rational answer to those arbitrary amounts. Real pickup amounts are still unmeasured (B-14).

---

## 2026-10-03 (night): test suite v1 and live rooms

Settles B-32, B-33; B-34 built. Raises B-35, B-36.

- `sim/test_suite.py`: fixed rooms and seeds for any checkpoint (aim per weapon against still / slow / fast /
  jumping targets and at three distances, weapon choice by range, movement, solo, scripted-fighter ladder).
  First card: `duel_gru_v3` at 5 minutes of training (near-random; the baseline to improve on).
- The same rooms run on the play-test server with a person as the subject (`!room ...`, `!room suite`).
  Dry run with a Nightmare bot standing in as the subject: LG 76% on a still target and 30% on a fast strafe,
  rail 14% of slugs on a still target, rockets 90% still / 62% fast (direct or splash).
- Bugs found and fixed in the dry run: target damage was dropped on the frame it was healed; healing a dead
  target left it stuck; aborting the match with two bots looped (warmup is now only held for a human).
- New hook function `minqlx.set_view()` turns a player's view (used to face the subject toward the target).
- `duel_gru_v3` at 31 minutes: 133k steps/s; switches 28 per minute (387 at the start); movement rounds
  271 u/s with 10.7% fast-air and 6.8 arrivals per minute; crosshair error in view 27 degrees (38 at start);
  megas 0.34 and red armors 0.51 per player-minute. Watch item: he holds the shotgun 87-97% of the time in
  normal rounds (it forgives bad aim).

---

## 2026-10-03 (night): first human play test, and what changed for `duel_gru_v3`

Settles B-08. Raises B-28 to B-34.

**Play test** (owner vs `duel_gru_v2`, 28 minutes, three maps; `data/duellive/sessions/*_human`): owner 54,
Bobby 14.

| Owner's note | Measured in the session logs | Cause in training |
|---|---|---|
| Switches weapons constantly | 33-75 switches per minute (normal loadout) | Switch cost was a guessed 0.1 s |
| Spams, runs dry, then does not shoot | Fire held 74-80% of frames with the enemy in view, 38-42% with nobody in view | Endless ammo in drills, endless machine gun |
| Odd weapon priority | Under 300 units: rail 50-56%, rockets 13-25% | 75% single-weapon rounds |
| Cannot track a slow strafe | Median crosshair error 6 degrees while in view; within 3 degrees 20-25% of frames | 150 ms delay, coarse smoothed turns |
| Jumps constantly, no speed | Jump key 30% of frames (owner 7%); above 330 u/s 5% (owner 37-46%) | Nothing rewards speed; nobody punishes jumping |
| Low ground, odd spots, stuck at a teleporter | Below the owner ~50% of the time | 15 s rounds |
| Rarely picks up health or armor | Big items: owner ~75, Bobby 14 | Tiny item bonus, short rounds |

His crosshair was within 3 degrees more often than the owner's (20-25% vs 5-18%): aim is undersold by the
spam, as the owner noted. Play-test bugs seen: a real match could start and the map then rotated out of the
pool; session folders could carry the wrong map label.

**Weapon switch time measured** (`plugins/weaponlab.py` set 3, `data/weaponlab4/`): from the switch command
to the first shot is 17 frames = 0.425 s for every pair tested (the held weapon changes after 10 frames).
The simulator had 0.1 s.

**Changes in the simulator for `duel_gru_v3`** (`sim/duel_env.py`, 171 inputs):
- Switch time 0.425 s and a 0.002 cost per switch; ammo finite in every round; 0.0005 per frame for holding
  fire when no enemy was seen for over a second; item bonus 0.3 per 100 points; reaction delay 25 ms.
- Aim: turn steps down to 0.03 degrees per frame, lighter smoothing for commands up to 1 degree, and the
  pull toward level only applies when no enemy is in view (a pure cost was not tried: 0.99 collapsed before).
- Round kinds: 45% normal (all weapons at spawn), 25% aim rounds against a scripted strafing target
  (LG-weighted), 15% one-weapon rounds, 15% movement rounds (run to mega / red / yellow armor).
- 20% of normal rounds are against a scripted fighter (turns onto the enemy, rockets close / LG mid / rail far).
- Scripted players are not trained on and not counted in the accuracy numbers.
- New metrics: accuracy and crosshair error while the enemy is in view, switches per minute, blind fire,
  weapon held by distance, movement-round speed and arrivals, results against the scripted fighter.
- Smoke run (7 minutes): 134k steps per second; switches, blind fire and crosshair error falling, movement
  arrivals and speed rising. Results of the full run go in the next entry.

---|---|
| Simulator physics match the real game; learned movement transfers (time ratio 1.01) | Settings search (coach) on top of Nightmare: 6% win rate vs control 69% |
| Strafe jumping emerged from reward alone (human physics) | Our own routing/movement on top of Nightmare: 0/108 |
| Nine weapons measured on a real server and reproduced | Recorded nav graphs (17% junk nodes) |
| Rail flicks and three-weapon use after the aim-input fix and drills | 25 ms bot physics (learned a ground-strafing exploit) |
| A simulator-trained duel policy runs on the real server | Self-play before the aim-input fix: rockets only |
| | `duel_gru_v2` vs Nightmare: 0-10; LG tracking stuck at 4-5%; weapon choice random |

---

## 2026-10-03 (evening): first GRU self-play run with memory (`duel_gru_v2`) and first live duel

Settles B-106, B-108. Raises B-01 to B-07.

**Training** (`data/sim_runs/duel_gru_v2/`, 272 minutes, 2.48 billion steps, ~152k steps/s, three maps,
RL/RG/LG/MG, 75% single-weapon drill rounds, 150 ms reaction delay, simulator `sim/duel_env_v2.py`):

| | 102 min | 219 min | 272 min (end) |
|---|---|---|---|
| Rail hit rate | 8-9% | 20% | 17-20% |
| Rocket hit rate | 4% | 6-7% | 8-10% |
| LG hit rate | 4% | 5% | 4-5% |
| Frags by weapon (RL / RG / LG) | 26 / 41 / 33% | 22 / 48 / 30% | 21 / 46 / 33% |
| Enemy visible | 6% | 8% | 7% |
| Megas / red armors per player-minute | 0.13 / 0.16 | 0.27 / 0.20 | 0.24 / 0.15 |
| Suicides per match-minute | 0.1-0.2 | 0.06-0.07 | 0.05-0.06 |
| Kill share vs older snapshots | 55-71% | 56-63% | 49-57% |
| Fast-air share (strafe jumping) | ~2% | 2% | 2% |

- Worked: rail flicks learned on their own; all three main weapons score frags; fewer suicides.
- Did not work: LG tracking never moved; no strafe jumping; item control low; improvement against its own
  past versions had nearly stopped by the end.

**Live port** (`plugins/duelbot.py`, `sim/export_duel.py`, `tools/duel_server.sh`): the policy's inputs are
rebuilt on the real server by the simulator's own `observe()` (positions, health, weapons, ammo, the
opponent's rockets, item states), the network runs in numpy, and Bobby is driven with human physics.
- A server crash was found and fixed: with human physics the bot flag was dropped for good, and the server
  crashed ("netchan queue is not properly initialized") as soon as a second player joined. The flag is now
  restored after every game frame (`Botctl_AfterFrame`).
- New hook function `minqlx.missiles()` lists projectiles in flight.

**Live vs Nightmare, Blood Run** (`data/duellive/duel_live_test2.jsonl`, `data/duellive/spar/`):

| Setting | Minutes | Frags Bobby - Nightmare | Damage dealt / taken |
|---|---|---|---|
| Normal loadout | 5 | 0 - 10 | 560 / 1162 |
| LG-only drill | 2 | 2 - 6 (cumulative with ~1 min normal) | 750 / 638 |

- All 560 damage in the normal loadout was rail hits (7 x 80). LG and rockets did nothing.
- He holds each of the four weapons about 25% of the time, the machine gun included: weapon choice was
  never learned, because in 75% of training rounds there was only one weapon (B-04).
- He holds fire about half the time with the enemy on screen 6-20% of the time (B-05).
- In LG-only rounds he out-damaged Nightmare, so the simulator's aim does carry over; the normal-loadout
  loss is mostly weapon choice.
- Not measured yet: a human opponent (first play-test session planned the same evening, B-08).

**Read on the 150 ms reaction delay** (B-03): fair for reacting to something new, but it is applied to all
enemy information, including smooth tracking, where people predict and show almost no lag. At strafing speed
the target moves ~48 units in 150 ms, more than a body width. Plan: curriculum from 50 ms to 125 ms.

---

## 2026-10-03 (afternoon): aiming fixed, weapon drills, all nine weapons measured and simulated

**Why self-play only ever used rockets** (`duel_v1`, `duel_v2`, first GRU run: 98-100% of frags):
1. A structural defect in the inputs: the 150 ms reaction delay was applied to the whole "angle from crosshair to
   enemy" reading, so the player saw the effect of its own mouse movement 6 frames late. Fixed: only the
   opponent's state (position, velocity, visible or not) is delayed; the player's own view is current.
2. No direct reading of the reticle-to-enemy distance. Added: coarse (+-15 deg) and fine (+-2 deg) offsets on both
   axes, a "crosshair is on the enemy" flag, and the target's apparent size.
3. Nothing forced practice with rail/LG. Added: weapon drill rounds (both players have exactly one weapon).
Result (`duel_gru_v2`, 75% drill rounds over RL/RG/LG, 19 minutes in): rail hit rate 0.3% -> 12%, LG 0.2% -> 9%,
frags by weapon rockets 47% / LG 31% / rail 22%, 5.3 frags per match-minute.
Also learned the hard way: weakening the view's pull toward level from 5% to 1% per frame made the pitch drift to
floor/sky again and players stopped seeing each other (3% visible); reverted.

**Remaining weapons measured on a real server** (`plugins/weaponlab.py`, WEAPONLAB_SET=2, `data/weaponlab3/`):

| Weapon | Real Quake Live | Simulator |
|---|---|---|
| Machine gun (starting weapon) | 5 per 100 ms, 10 u/s knockback per hit | same |
| Heavy machine gun | 8 per 75 ms, 25 u/s per hit | same |
| Shotgun | 100 at 100 units, 60 at 300, 25 at 600; knockback 415 / 254 / 106 | 20 pellets x 5, gaussian spread 3 deg (expected 100 / 61 / 23) |
| Plasma | 20 per hit every 100 ms, 2000 u/s (first hit frame 9 at 400 units, 17 at 800), 110 u/s knockback; splash 16 / 16 / 10 / 3 at 0 / 10 / 20 / 30 units; at own feet 7-9 damage, 95 u/s lift | same timing; splash 16 / 16 / 10 / 3; own feet 8, 98 u/s |
| Grenades | 100 direct at 150 units (frame 9, 542 u/s knockback), 2.5 s fuse, own feet 44 damage / 277 u/s lift | direct 100, frame 9, 544; own feet 53 / 650 (NOT matched: bounce before the fuse) |
| Gauntlet | 50 per ~425 ms, hits at 40 units, not at 70; 219 u/s | same |

Model changes from these: plasma moves on the frame it appears (rockets and grenades do not); grenades get Quake's
loft (+0.2 on the forward z); splash knockback = 5 u/s x splash damage x 1.07 on others, x 1.3 on yourself (fits
rockets 450 / 549 and plasma 80 / 95); refire timer rounding fixed (machine guns were firing 20% slow).
Bug found by a smoke test: a projectile at rest (grenade on the floor) counted as a direct hit on the opponent
anywhere (zero-length segment in the hit test). Fixed in `sim/duel_env.py`; the frozen `duel_env_v2.py` used by
the running job only has it for exactly axis-parallel or zero-length shots.

## 2026-10-03 (afternoon): weapons checked against real Quake Live

Method: `plugins/weaponlab.py` puts two fully controlled bots on a 1,408-unit flat stretch of Campgrounds and
fires controlled setups (4 repetitions; the first of each is discarded as a setup glitch), logging health and
velocity every frame. `sim/validate_weapons.py` replays the identical setup in the duel simulator.
Data: `data/weaponlab/`, `data/weaponlab2/`. Real damage includes ~1 point of health decay (tests start at 200 hp).

| Test | Real: damage / hit frame / knockback (horizontal, vertical) | Simulator after fixes |
|---|---|---|
| Rocket at the body, 400 units | 100 / 17 / 449, -24 | 100 / 17 / 449, -25 |
| Rocket at the body, 800 units | 101 / 33 / 450, -12 | 100 / 33 / 450, -12 |
| Rocket at own feet (rocket jump) | 42-43 self damage, 549 u/s up | 42, 550 |
| Rocket at the floor 0 / 20 / 40 / 60 / 80 / 100 / 120 / 140 units in front | 85 / 81 / 64 / 46 / 38 / 23 / 8 / 0 | 84 / 78 / 63 / 47 / 37 / 23 / 10 / 0 |
| ...same, knockback (h, v) at 20 / 60 / 100 | (167, 391) / (196, 138) / (104, 49) | (181, 382) / (208, 145) / (116, 54) |
| Railgun, 1000 units | 80 / frame 2 / 340, 0 | 80 / 2 / 340, -7 |
| Lightning gun | 6 per 50 ms (120/s), 35 u/s per tick, hits at 700, misses at 800+ | same (range 768) |

What the real game does (now in `sim/duel_env.py`):
- A shot leaves one frame (25 ms) after the fire command; a rocket does not move on the frame it appears.
- Rocket speed 1000 u/s. Direct hit 100 damage. Splash: 84 damage and "100 points" of knockback, both falling
  off linearly to zero at 120 units; the falloff sits ~20 units closer to the target than the plain
  distance-to-hitbox (calibrated constant).
- Knockback = 5 u/s per point, times 0.9 on other players (direct hit: 450 u/s), times 1.1 on yourself (rocket
  at your feet: 550 u/s up); splash pushes upward (Quake 3's +24 on the direction). Own splash damage is halved.
- Railgun 80 damage, knockback factor 0.85 (340 u/s). Lightning gun 6 damage per 50 ms, range 768, ~35 u/s per tick.

Wrong in the first-pass simulator (and so in the `duel_v1` run): no firing delay, rockets moved on the spawn
frame, splash knockback mostly sideways instead of up, one knockback factor (1.1) for everything, splash ~20
units too short, LG knockback too weak. `duel_v1` should be retrained on the corrected simulator.

Not yet measured: weapon switch time, damage through armor, shotgun/grenades/plasma/MG/HMG, air targets.

## 2026-10-03: duel simulator, first self-play run (`duel_v1`)

Setup: `sim/duel_env.py` (2 players per match, RL/RG/LG with infinite ammo, QL damage/splash/knockback,
half self-damage, 125 hp, no items), 150 ms reaction delay on everything a player knows about the opponent,
110° field of view + hearing within 800 units. One policy plays both sides. 117 min, 284 million steps,
3,072 players on Blood Run. Curriculum: respawn near the opponent (100% → 20% over 60 min), short rounds
(15 s → 120 s).

Problems fixed on the way (short runs): view pitch drifted to ±89° so players never saw each other (fix: the
view eases back toward level); players learned to hide because being seen = being shot (fix: reward damage
dealt, not penalize damage taken, as curriculum shaping); players drifted apart with no respawns (fix: short
rounds that restart both players near each other).

Results (eval at normal spawns, 90 s x 64 matches, `sim/eval_duel.py`):

| | Self-play | vs random policy | vs standing dummy |
|---|---|---|---|
| Kills per match-minute | 0.61 | 0.73 (0 deaths) | 0.54 |
| Rocket hit rate (direct + splash) | 21% | 9% | 14% |
| Rail / LG hit rate | ~0 (unused) | ~0 | ~0 |
| Sideways speed with a rocket incoming vs otherwise | 201 vs 128 u/s | 179 vs 103 | — |
| Shots fired just after losing sight (prefire) | 7% | 4% | 1% |
| Rocket jumps per player-minute | 0.18 | 0.07 | 0.03 |
| Fast airborne (strafe jumping) share | 3.7% | 2.3% | 1.5% |

Training curve: rocket hit rate 7% → 28% while players spawned close, ~20% at normal spawns; suicides fell to
~0.1 per match-minute.

What it means:
- It learned to aim and lead rockets (splash-heavy), to dodge sideways under fire, some prefire and occasional
  rocket jumps. It beats a random policy without dying.
- It is weak at finding the opponent (0.54 kills/min against a dummy that never moves): no memory, no map
  knowledge in its inputs.
- It never learned rail or LG (coarse turn steps can't aim them; rockets always available) and doesn't strafe
  jump in fights (trained from scratch, not from the movement policy).
- Weapons/damage in the simulator are not yet checked against the real game, and no live duel test yet.

## 2026-10-03 (morning): simulator-built nav graphs, one policy on three maps, live on all three

**Nav graphs built by the simulator** (`sim/build_nav.py`, ~10 s per map): standing spots found by dropping
a player box on a 48-unit grid; walk links and run/jump/drop/jump-pad/teleport links all verified by
simulated movement (human physics).

| Map | Spots | Walk / jump-drop / teleport links | Spots that can reach the goal items |
|---|---|---|---|
| Blood Run | 1,185 | 6,857 / 11,633 / 49 | 97% |
| Aerowalk | 906 | 5,259 / 7,871 / 174 | 65% (platforms over the void; some need jumps a standing start can't make) |
| Campgrounds | 1,643 | 9,950 / 15,120 / 0 | 92% |

Blood Run route estimates are 13% longer than the recorded graph's (no rocket-jump shortcuts, standing starts).

**One movement policy, three maps** (`multimap_v1`, started from the Blood Run policy, 90 min, 4 workers per map,
simulator nav graphs): success 74% → 96% (Blood Run 99.7%, Campgrounds 97%, Aerowalk 94%), trip time vs a
perfect runner 0.86 → 0.83 (faster than the single-map policy). No falls on any map.

**Live (real QL server, human physics, `plugins/movetest.py`, 3 servers in parallel):**

| Map | Live arrived | Simulator success | Live / simulator time |
|---|---|---|---|
| Blood Run | 72/72 | 100% | 1.01 (p10 0.95, p90 1.10) |
| Campgrounds | ~26/30 | 82% | 1.07 |
| Aerowalk | 28/42 (67%) | 82% | 1.05 (p90 1.35) |

- Aerowalk live failures (14/42) were all 20 s timeouts, no deaths. 7 of those trips also fail in the
  simulator (mostly to the Red Armor, which the simulator-built graph can't reach from a standing start: needs
  a running jump or rocket jump). The other 7 fail only live (stuck/wandering): a real but smaller transfer gap
  (~17% of Aerowalk trips). Aerowalk has no hurt triggers; falling into the void ends a trip in both.
- A test server once loaded the map but ran no game frames until restarted (no players yet). Same symptom as
  the public server's "hang" on 2026-10-02. Workaround: restart; to investigate (QL idle behaviour?).

## 2026-10-03: learned strafe jumping transfers to real Quake Live

**Result.** A movement policy trained only in the simulator (`sim/`) completes item-to-item trips on a
real Quake Live server as fast as it does in the simulator.

| Live test, Blood Run, 1 run per trip | Human physics (8/8/9 ms) | Bot physics (25 ms) |
|---|---|---|
| Trips arrived | 73/73 | 72/72 |
| Live time / simulator time (median) | **1.01** (p10 0.97, p90 1.13) | 1.09 |
| Faster than Nightmare's real median trip | 24/24 | 24/24 |
| Median top speed | 534 u/s | 507 u/s |

Examples (live vs Nightmare's real median): MH→LG 1.45 s vs 8.7 s, MH→RG 2.3 s vs 7.0 s, SG→RA 1.25 s vs 2.5 s.
Nightmare's numbers come from training-server trips and include its detours, so the true gap is smaller.

- How: `plugins/movetest.py` drives Bobby with the exported policy (`sim/export_policy.py`), using the same
  observation code as training (simulator compiled into the server image for wall/floor rays).
  Comparison: `sim/compare_live.py`. Data: `data/movetest/`.
- Human physics on the server: the C hook (`minqlx/botctl.c`, `set_bot_substeps`) splits each 25 ms
  command into 8/8/9 ms moves and clears the bot flag so the game moves each one (Q3/QL move bots once per
  frame otherwise). Live velocities match the simulator's human physics (p90 error 1.3 u/s vs 13.8 for
  25 ms physics).
- Harness bugs found on the way: the plugin kept commanding the old view after teleporters (the game turns
  the view; fixed by reading `view_angles` every frame); numpy booleans broke the JSON log.

## 2026-10-03: overnight training, human physics: strafe jumping emerged

- Run `bloodrun_human_v1`: 10 h, 1.93 billion steps, PPO, 3,072 players, human (125 fps) physics.
- Nothing about strafe jumping is coded. Reward = time saved toward the goal item.
- Signature in the policy: forward + strafe, view held 8-15° off the velocity, sides alternating, short
  jump taps on landing; speed grows while airborne (e.g. 380 → 530 u/s in one hop sequence).
- Eval vs 1-hour run: chained hops above 330 u/s 0 → 804, fast airborne time 17% → 47%, vmax 510 → 855.
- Learning curve: trip time vs a perfect runner 0.97 → 0.90 by hour 2, then ~1%/h, 0.86 at hour 10.
  Plateau on this setup.

## 2026-10-02/03: frame-rate exploit found by the first policy (and ruled out)

- The first policy (`bloodrun_v1`, 1 h, 25 ms physics) learned **ground strafing** at 370-385 u/s without
  jumping: forward + strafe with the view ~40° off the velocity, so acceleration beats friction each frame.
- It only works with 25 ms physics frames (bots at 40 Hz). A 125 fps human gets a sliver of it.
- Owner decision: train with human physics only (`substeps=(8,8,9)`), so Bobby can't use bot-only physics.

## 2026-10-02/03: simulator fidelity

- Simulator = ioquake3 Pmove + collision (vendored in `sim/q3/`) with Quake Live's settings (jump 275,
  auto-hop; chain jump off), real map files (IBSP 47), jump pads and teleporters. ~740k player steps/s per core.
- Checked against ~20,000 recorded frames of two Nightmare bots on a real QL server (`sim/validate.py`):
  one-step error 0 units (p95), velocity 0.6 u/s (= recording rounding); 0.5 s open-loop replays within
  0.5 units for 90%; 2 s within 8.4 units for 90%.
- `pmove_ChainJump 1` does **not** mean "+110 within 500 ms": real jumps 200 ms apart got 275.
- The engine's `lastUsercmd` is stale for bots; `minqlx.ran_usercmd` (new) returns the command a think
  actually ran. Recordings now log exact inputs (`inputs_<map>.txt`), also for humans (last command of the
  frame).

## 2026-10-03: recorded nav graphs are partly junk

- 389 of 2,320 points in Blood Run's recorded graph (17%) are outside the playable map (a whole phantom
  corridor north of the map, from old recordings); 196 more are mid-air jump points.
- Spawning players there caused all "falls off the map" (17% of training trips) and many stalls.
- Filtering with the map's own data (leaf cluster = -1 outside the map; floor under spawn points):
  success 82% → 100%, falls 17% → 0%. Speed unchanged (0.866 of run-speed time).

## 2026-10-02: settings search (coach) on Nightmare + fair aim: no needle moved

- Since 09:30, 572 matches: Bobby (old aim) 6% win rate vs control (plain Nightmare) 69%.
- The coach (cross-entropy method over ~14 settings) found nothing real: most generations had ~3 matches
  per candidate (best-of-N luck); with 5 trainers per candidate the best had a 6% win rate at n >= 10.
- Root causes: the old accuracy tuner deliberately loosened LG aim up to 3x when Bobby hit > 40% (removed);
  weapon choice used rockets very little (120 rockets vs ~12,900 LG cells across trainers).
- After the aim fix, 4 aerowalk test matches were all wins (20-4, 11-8, 8-4, 7-3). Too small to call.
- Nightly settings-search runs paused in favor of learning (this log's newer entries).

## Earlier (2026-10-01/02, see git history and CLAUDE.md)

- Item-route-first design lost 108/108 vs Nightmare. Split test: our movement and our decisions lost
  badly; Nightmare movement + our fair aim was the best of our variants but still far below control.

## Data sources

- Demos: 380 recent (.dm_91, 2024-2026) duel demos from demos.quakelive.ru: Blood Run 226, Aerowalk 148,
  Campgrounds 6 (`tools/fetch_demos.py`, `data/demos/`). Older eras (dm_73, 2009-2013) and
  quakehistory.com (292 curated 2012-13 POV duels; robots.txt blocks its download folder) not used yet.

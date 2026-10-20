# Tonight's report: what we found today and what goes into v0.3.8

*Written 2026-10-20 for the owner's go on v0.3.8. v0.3.7 trained from Mon 17:53 to Tue 14:08 (save 380, optimizer kept). Every
measurement below was made on the spare cores while it trained, or after it stopped. The one-page sheet is
[RUN_v0.3.8.md](RUN_v0.3.8.md); the numbers here are the full tables behind it. "Pros": the archive's pro duel demos (up to 2,626
demos on the same maps); "the owner": his play-test sessions. A check is 160 ten-minute duels on ten maps, seats swapped, aim
level 3 (the same network against itself reads 48.8%; a check moves 3 to 4 points by chance).*

## 0. Where v0.3.7 ended

| Update | 10–60 | 80–140 | 160–240 | 260–380 |
|---|---|---|---|---|
| Against v0.3.6's end (previous best) | 62.5 (u40) | 67.0, 68.7 | 70.5, 71.2, 71.8 | 69.9, **71.7 (end of day, 137–19)** |
| Against v0.3.1's end (control) | 62.7, 72.2 | 75.2, 76.8 | 77.0, 81.1 | 80.0, 78.1, **77.5 (146–9)** |

- Flat at about 70% against v0.3.6 since update 200. Part of the margin is the old networks playing v0.3.7's rules (duel
  movement, the jump read, the respawn delay, missiles as points, the zoom fix), which they never trained on.
- Movement, enemy unseen: speed 319–326 (v0.3.6 314–316); take-offs 31 near, 39–42 far a minute (25 / 31). In view: 0.6–0.8
  take-offs a minute, speed ~293 (no jumping in fights, as before).
- Frags 2.1–2.4 a match-minute (2.0–2.2). Mega and red armor 1.8–1.9 a minute. Weapon pay by order: about 1.3 first, 0.7
  second, 0.35 third big weapon a player-minute.
- Rail: rail starts' first shot within 10 s 39% → 44–54%, far hits in rail starts ~13% → 20% (after the two nudges of the night);
  rail in hand in games 6–7%, unmoved. The two nudges: long-rail pay 0.12 → 0.25 (did nothing: he takes too few long shots to
  earn it) and rail starts facing within 15°, 30 s long.
- Frags dipped to 1.8 around update 176 and came back: every simulator's games began together at the 00:15 restart and ended
  together 60 updates later. Each mid-run restart causes one such wave.

## 1. Rail: why his clicks land late

The measurements (save 220, 96 games on Blood Run, Sinister, Campgrounds, Aerowalk; pros 51,202 rails; the owner 284):

| | Bobby | Pros | The owner |
|---|---|---|---|
| Rail shots a minute with the enemy in view | 0.34 | 2.2 | – |
| Share past 750 units | 3% | 43% | median 557 u |
| Rail hit rate | 32% | 45% | 36% (62% last night, 34 rails) |
| Error growing at the shot (>15°/s): share, hits | 46%, 21% | 37%, 39% | 31%, 35% |
| — the enemy outruns his tracking | **31.5%, 19%** | 21.9%, 46% | 17.6%, 38% |
| — his own overshoot | 7.8%, 24% | 11.6%, 28.5% | 9.9%, 36% |
| View speed through the shot (4 frames before) | 0.56: he **stops to click** | 1.32: keeps turning | 1.37 |
| Finisher: switch to rail and fire on a wounded, retreating enemy | 1.3% | 21.4% | 23% |

- Held at the same target speed the pros' outrun shots still hit 44–47%, his 17–26%: not only his shorter range.
- The hand model is not the cause: on his overshoots the hand carries the view 0.6° after he stops.
- **The structural part:** every shot waited one frame after the press, in the simulator and on the servers alike; Quake Live
  fires on the press frame. The crosshair was on the enemy at 39.6% of his presses and 33.6% of his shots. And the server fires
  a driven bot's shot 8 ms into the frame, along the last yaw plus 0.32 of the frame's turn (`minqlx/botctl.c`); the simulator
  used the whole turn (9% of rails flipped, both ways). The "stop and click" habit is probably his answer to that hold: with
  the shot traced on the next frame's view, braking kept the view on target. Fixed (section 3): rail hits 35 → 56% on Blood Run,
  46 → 50% on Sinister, before any training.

## 2. The senses: what he knew that a person doesn't (the input audit)

Every input group was read in the code. Unfair ones, worst first, with what the pros show and the cost of each fix (his side
only, the network not retrained, frag share against v0.3.6's end; noise ±0.04; off 0.550):

| Sense | Before | Now (the switch) | Pros vs Bobby | Cost |
|---|---|---|---|---|
| Footsteps | an enemy running within 800 u "heard" every frame, in the air too; the error drawn fresh each frame, so averaged to ~13 units | a footstep every 0.55 s on the ground above 150 u/s, jumps; one 10° / ±30% error a sound (`HEAR_FIX`) | pros: 1.8 steps a second at 250–400 u/s, 0.02 in the air; facing a hidden running enemy 44–48% (Bobby 53 / 44%, with the fix 50 / 35%) | **0.477: ~7 points** |
| Hearing | loudness = exact distance; exact closing speed | no closing speed, distance ±30%, the hum's error drifting | turning to a sound: pros end 7° off, Bobby 20° | (in the above) |
| Sounds from cut-off parts of the map | heard by distance alone | the server sends a player's sounds only while he is in your potentially visible set (`HEAR_QL`) | section 2b | – |
| Projectiles | exact, undelayed, exact fuse | noticed after 100 ms in sight, read 100 ms late, fuse only if seen since launch (`PROJ_FIX`) | pros dodge an out-of-view rocket from 0.05 s, +50 u/s by 0.35 s; Bobby does not dodge at all | 0.565: none |
| Enemy velocity | exact, 200 ms late (also in his leads, rocket floor aim, believed place) | read 200 ms late with a drifting 20% error, under 30 u/s as still (`VEL_FIX`) | no effect on his tracking (section 4) | 0.556: none |
| Distance to a seen enemy | exact | a drifting 15% error (`RANGE_FIX`) | no effect on his rockets | 0.565: none |
| Facing, crouch, weapon; dropped weapon time; MG/SG lines; item timers | this frame's truth; exact; visible; a perfect stopwatch | his reaction delay, facing ±15°; only if the death was seen; rail and lightning only; ±0.75 s when only heard (`SENSE_MINOR`) | – | – |
| All four big ones together | | | | 0.523 |

The pattern: the leaks were real in his inputs, but apart from hearing he had not learned to use them.

### 2b. Sounds from cut-off parts of the map (`HEAR_QL`)

Quake Live does not muffle sound through walls; the server only sends an entity's sound events to clients whose potentially
visible set contains it, so a player in a part of the map cut off by the void is not heard however close. Checked against the
pro demos (a demo holds exactly what the server sent its player; 232 first-person demos, 12 maps, 5.1 M frames):

| What | Result |
|---|---|
| The enemy's own sounds (steps ~131k, jumps and falls ~42k, fire ~93k, pain ~11k, pickups ~12k, deaths, weapon changes) | **0** arrived while his entity was absent from the snapshot |
| The same as separate event entities (~160k) | 0.06% absent (the 300 ms such an entity lives) |
| Sounds at another place (teleport in / out, wall hits, rail trails, explosions, item respawns) | sent by the PVS of their own place: teleports 99.3–99.5% in our PVS |
| Sent to everyone | death messages; map ambience; on newer servers an item-pickup notice (event 83; whether the client plays a sound for it is unknown: the client is closed) |
| Our PVS test against the server's, enemy present (2.78 M frames) | **98.99%** agree (97.6% Lost World to 99.8% Hektik and Battleforged; the misses grow with distance and are partly the 9-point box) |
| Our PVS in short gaps (enemy absent < 0.5 s) | says not sent on 88% (the rest mostly from interpolating his place) |
| A line-of-sight rule instead | wrong: with the enemy sent he is in clear sight on only 31% of frames |
| Distance | the server sends to ~2,200 u; audibility is the client's: in Quake 3's open sound code a sound fades to nothing at ~1,330 u (26% at 1,000, 10% at 1,200: an assumption for Quake Live). The simulator's ranges (1,000 steps, 1,200 events) cut at a quarter to a tenth of full volume: no change |

**Verdict: `HEAR_QL=1` is right for v0.3.8, no parameter change.** It silences about 1% of the sounds the game would send.
(Spectator demos of the newer protocol were left out: their server sends both players nearly always, without the PVS; Bobby
is a player.)

## 3. Fire timing as Quake Live does it (`FIRE_QL`, every weapon)

| Weapon | Before | Now | Proof |
|---|---|---|---|
| Rail, lightning, machine guns, shotgun, gauntlet | one frame after the press; the next frame's full turn | the press frame; the server's angle (last yaw + 0.32 of the turn, final pitch); the enemy where he stood at the frame's start | 300 of 300 crossing shots agree with the server's rule (233 before) |
| Rockets | final yaw | the server's angle, velocity cut to whole units | within 0.05° |
| Grenades, plasma | a frame late, from 14 units ahead, ~46 ms behind the game | the game's muzzle (5 units ahead), velocity cut, 50 ms of flight in the launch frame | the game's 29 measured grenades within 0.43 units |
| Shotgun | pellets drawn at random | the game's fixed pattern | 100 / 60 / 25 damage at 100 / 300 / 600 units, as in the game |

Effect, save 220 against itself, before training: rail 35.4 → 55.8% (Blood Run), 45.6 → 49.6% (Sinister); lightning +2 to +4;
machine gun +2 to +6; rockets ±3 (noise). Open: a person with ping is slightly further in the past than the frame's start; the
machine gun's spread width is not measured in the game.

## 4. Aim: his timing against the pros', and the reaction-delay options

| | Pros | Bobby (save 220, today's 100 ms) |
|---|---|---|
| Strafe reversal: view turns back (608 events) | 0.10 s | 0.05 s |
| Tracking: delay behind the enemy, how fully he follows | 100 ms, 0.88 (0.75 slow targets) | 50 ms, 0.98 |
| The same with no velocity input at all | – | 50 ms, 0.94 |

His whole loop runs ~50 ms ahead of the pros', from his place and crosshair inputs with the 100 ms delay, not from the velocity
input. The sweep, every sense fix on (the network not retrained at the new delay; training will raise every number again):

| Setting | Reversal turn-back / half peak | Follow at 100 ms | Lightning | Rail | Rockets that hit | Rockets near (200–500) |
|---|---|---|---|---|---|---|
| **Pros** | 0.10 / 0.175 s | 0.88 | 31% | 42% | ~28% | 33% |
| 100 ms | 0.05 / 0.15 | 0.92 | 47% | 44% | 55% | 62% |
| 125 ms | 0.075 / 0.15 | 0.91 | 44% | 42% | 54% | 57% |
| 150 ms | 0.075 / 0.125 | 0.885 | 39% | 33% | 53% | 57% |
| 175 ms | 0.075 / 0.175 | 0.875 | 34% | 29% | 52% | 54% |
| **125 ms, everything on** (fire timing, mouse filter 4 Hz) | 0.05 / 0.15 | 0.95 | 41% | **42%** | 53% | 55% |
| **150 ms, everything on** | 0.075 / 0.15 | 0.93 | 38% | 35% | 52% | 56% |
| 150 ms, everything on, filter 3.5 Hz | 0.075 / 0.15 | 0.93 | 38% | 36% | 54% | 53% |
| **175 ms, everything on** | 0.075 / 0.15 | **0.887** | **33.5%** | 33% | 52% | 56% |

| Option | Lightning vs pros | Rail vs pros | Follow vs pros |
|---|---|---|---|
| 125 ms | +10 points | level | +0.07 |
| 150 ms | +7 | −7 | +0.05 |
| 175 ms | +2.5 | −9 | level |

- One delay cannot match both: lightning (continuous tracking) wants ~175, rail (flick, settle, click) wants ~125. A
  per-weapon delay is not a human limit (the eyes do not change with the weapon); if rail stays low after training, look at
  the rail's own chain (the filter on the last correction before a shot, the 200 ms acquire delay), not the delay.
- The rockets: the "52–55% against ~28%" is mostly the mix of distances (the pros' 28% includes long and blind rockets; he
  fires more of his close). By distance, rockets that hurt:

  | Distance | Pros | v0.3.5's end (before the rocket aim helper) | v0.3.6's end | Save 220 |
  |---|---|---|---|---|
  | under 250 u | 72% | 75% | 80% | 78% |
  | 250–500 | 45% | 49% | 57% | 48% |
  | 500–750 | 23% | 16% | 23% | 31% (59 rockets) |
  | 750–1,100 | 12.5% | 8% | 6% | few |

  Within each band he is near the pros; the helper's exact aim point added ~8 points at 250–500 in v0.3.6. A perceived (noised,
  delayed) aim point for it is a later item, not urgent.
- The mouse filter makes him follow more fully (it smooths his small corrections), so each delay sits a little higher with it.
  3.5 Hz changes nothing measurable against 4 Hz (the owner chose 4 Hz).

## 5. The "wave" and aiming with the body (the owner's play-test note)

Lightning fire, enemy in view, 150–700 units (Bobby 2,828 s; pros 337 demos; the owner 110 s; v0.3.6 on the real server 192 s):

| | Bobby | Pros | The owner | v0.3.6 on the server |
|---|---|---|---|---|
| Mouse acceleration rms | 4,845°/s² | 2,455 | 1,360–1,435 | 4,459–4,797 |
| Turn reversals a second | 8.2 | 4.6 | 3.5–3.9 | 8.1–8.8 |
| View power above 4 Hz (the target's own: 3–8%) | 53% | 29% | 14–17% | 48–52% |
| Body's share of the tracking | −0.02 | 0.02 | −0.06 | 0.05 |
| Strafe changes a second while firing | 1.0 | 1.59 | 1.65 | 1.0 |
| Follows the enemy's strafe reversal (median) | 0.40 s | 0.25 s | 0.20 s | – |

- The wave is his hand: his turn command is near white noise (84% of its power above 4 Hz, a sign change 12.8 times a second),
  and small commands passed almost unsmoothed. The fix (`HAND_BAND`): a low-pass on the view's turn whose cutoff rises with
  its speed (4 Hz + 0.5 Hz per °/frame); sized offline on his own commands: 4,600 → 2,613°/s², 8.3 → 4.8 reversals, 43 → 27%
  above 4 Hz (pros 2,455, 4.6, 29%); a small correction 25 ms later, a fast flick 9% slower.
- Nobody strafes to aim: the mouse does all the tracking for pros, the owner and Bobby. What people do is reverse their strafe
  more often. Strafing against the enemy's motion is the dodge: the enemy's lightning on him 43% (55% with it, 62% still), rail
  28 / 42 / 59%. A dodge drill (the enemy firing at him; practice, no pay) is proposed for v0.3.9.

## 6. The duel preset (`DUEL_QL`)

The servers run Quake Live's duel factory; the simulator had free-for-all's numbers:

| Setting | Free-for-all | Duel | Simulator before | Now |
|---|---|---|---|---|
| Shortest time between jumps | 100 ms | 50 ms | 100 | 50 (49 refused, 50 jumps) |
| Wading speed | 0.8 | 0.75 | 0.8 | 0.75 (293 u/s in the pool) |
| Pickup reach in height | ~66 (219 of 7,767 pickups at 56+) | ~51 (4,656 duel pickups: 99.9% within 50.4, none at 56) | 56 | 51 |
| Crouch step jump | on | off | never modelled | – |

## 7. The new input: target drift (`DRIFT_IN`)

How fast the enemy slides across his crosshair (yaw, pitch, a smoothed pair), from the perceived angles only: zero unseen, on a
first sighting or a teleport. Sized from the pros' tracking: 50 ms later than the angles; no extra noise (the sight error's
wander already gives ~13°/s raw, 4–7 smoothed, as rough as the pros' rate error). A v0.3.7 save widened to it answers exactly
as before (0 of 5,376 choices differ).

## 8. The code and the dry run

- Branch `v038`, frozen at `0a14b6f` (worktree `ql-bot-v038s`): the weapon pay by order, the zoom fix, the far-rail price (held,
  off), the drift input, fire timing, the five sense switches, the mouse filter, the duel preset, and the merge of the two
  branches (one fix found by the checks: the distance error with the drift input read as a new sighting). With every switch off
  the simulator is identical to v0.3.7's; every switch's unit check passes with all on; the servers compute the same inputs
  (99.7–100%).
- Dry run from save 380, every switch, 150 ms, 12 updates: exit 0; step 0.029–0.032 an update (v0.3.7 0.028–0.030), the largest
  single output 0.013 (as v0.3.7's dry run); frags back from 0.58 to 1.67 a match-minute; speed unseen 318–332.
- Its check: against v0.3.1's end 72.4% (139–18); against v0.3.7's end 41.9% (50–99): the check tool gave v0.3.7's end its own
  100 ms against his 150, after 12 updates at the new limits. In training every seat shares his delay.

## 9. Not resolved, or for later

- The rocket aim helper's exact aim point (a few points at 250–500): a perceived aim point later.
- Rail below the pros at 150–175 ms: re-measure after a few hours of v0.3.8; then the rail's own chain.
- The reversal turn-back stays 25 ms early from 150 on: he seems to anticipate reversals.
- v0.3.9: the finisher (pro starts at the moment the enemy is wounded and pulling away), the dodge drill, reaction by situation
  (a surprise slower than a tracked reversal), ledge grabs, rockets at step corners, grenade splash close in; the rocket-jump
  specialist tomorrow.

## Files

Scratch folders of the measurements: `railmeasure`, `railcause`, `inputaudit`, `aimbody`, `v038hitscan`, `v038senses`, `v038duel`,
`v038merge`, `v038drift`, `pvscheck`; the watcher and checks: `v037w`, `v038w`.

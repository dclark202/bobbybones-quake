# v0.3.8 on one page: what changes from v0.3.7

*Working document, started 2026-10-20 07:50, filled in as today's measurements report. Folder `duel_gru_v0_3_8`. Starts on the
owner's go after the ~19:30 play test (about 21:00 Tue), from v0.3.7's save nearest 16:00 (optimizer kept); runs to **16:00 Wed**.
Code: branch `v038` (frozen at `0a14b6f`, worktree `ql-bot-v038s`). Status: **running since 17:10 Tue** (owner's go), from v0.3.7's save 380,
optimizer kept, 125 ms, to 16:00 Wed; the owner (2026-10-20 ~10:15): all the sense, aim and fire-timing fixes go into v0.3.8,
limits at or slightly better than the pros'. 16:00–19:30: v0.3.8's dry run (10 updates, step per output, a check against the control)
on the card; the rocket-jump specialist moves to tomorrow. Timeline (owner, ~12:40): v0.3.7 stops at save 400 (~15:15), its
end-of-day check; the dry run at 15:30 with a provisional 150 ms; the start after the full aim sweep (~17:45), to 16:00 Wed.*

**Marks:** ✅ built and proven identical with its switch off · 🧪 measured or tested today · ❓ owner's decision · ⏸ not in v0.3.8

## Where v0.3.7 ended (from its checks)

| | v0.3.6's end | v0.3.7 (update 220, 06:20 Tue) |
|---|---|---|
| Against v0.3.6's end (previous best) | – | 62.5% (u40) → 71.2% (u200) |
| Against v0.3.1's end (control) | 55.0% | 62.7% (u10) → 81.1% (u220) |
| Speed, enemy unseen | 314–316 | 319–324 |
| Take-offs a minute, enemy unseen near / far / in view | 25 / 31 / 0.7 | 31 / 39 / 0.6–0.8 |
| Frags a match-minute | 2.0–2.2 | 2.3–2.4 |
| Rail in hand / rail frags | 6% / 4% | 6–7% / 4–5% |
| Rail starts: first shot within 10 s; far hits | – | 39% → 44–54%; 12–14% → 20% |

Caveat: the old networks play under v0.3.7's new rules (duel movement, jump read, respawn, missiles, zoom), which they never
trained on; part of the margin is that. (Filled at the stop: the end-of-day check, 80 + 80 games.)

## 1. Rail: why his clicks land late (measured today)

| Finding | Him | Pros | The owner | State |
|---|---|---|---|---|
| Rail shots a minute, enemy in view | 0.34 | 2.2 | – | 🧪 |
| Share of rails past 750 units | 3% | 43% | median 557 u | 🧪 |
| Rail hit rate | 31% | 46% | 62% | 🧪 |
| Fired while the aim error grows (>15°/s): share, hits | 40.5%, 22% | 36.5%, 39% | – | 🧪 |
| Fired more than 2 target half-widths off (hits 0% for him) | 56% | 47% | – | 🧪 |
| Fired on the first frame of a turn | 19.5% | 9% | 3% | 🧪 |
| Finisher: switch to rail and fire on a wounded, retreating enemy | 1.3% | 21.4% | 23% | 🧪 |
| Cause: the enemy outruns his tracking (share of rails, hits) | 31.5%, 19% | 21.9%, 46% | 17.6%, 38% | 🧪 the main gap |
| Cause: his own overshoot (share, hits) | 7.8%, 24% | 11.6%, 28.5% | 9.9%, 36% | 🧪 fewer than pros: not the hand |
| Outrun shots held level by target speed: hits | 17–26% | 44–47% | – | 🧪 not only his shorter range |
| View speed through the shot (median, 4 frames before) | 0.56: he **stops to click** | 1.32: they **keep turning through it** | 1.37 | 🧪 the habit |
| The enemy on his crosshair: at his decision / at the press / at the shot | 50% / 46% / 20% | – | – | 🧪 the latency chain (his read is 4 frames old, plus the 1-frame hold) |

## 2. Simulator and server fixes

| Change | Switch | State |
|---|---|---|
| Shots waited one frame after the press (simulator and servers alike); Quake Live fires on the press frame. The hold is 25 ms a person doesn't have: crosshair on the enemy at the press 39.6%, at today's shot 33.6%: **about 6 points of rail hits** | `FIRE_QL=1` | ✅ 0151bab (identical off): press to shot 0 frames for every weapon, on the simulator and the servers |
| Shot direction as the server fires it (yaw + 0.32 of the turn, final pitch); rockets too | `FIRE_QL=1` | ✅ 300 of 300 rails at crossing targets agree with the server's rule (233 of 300 before); rocket direction within 0.05° |
| Grenade and plasma launch: muzzle, speed, the game's 50 ms of flight in the launch frame (fitted on 29 grenades measured in the game) | `FIRE_QL=1` | ✅ within 0.05 units of the game's model |
| Shotgun: the game's is fixed (100 / 60 / 25 damage at 100 / 300 / 600 units, every time); the simulator drew pellets at random | `FIRE_QL=1` | ✅ the same three numbers |
| Server shot direction: the server runs Bobby's frame in 3 steps and fires in the first (8 ms in): yaw = last yaw + 0.32 of the turn, final pitch, the enemy where he stood at the frame's start (`minqlx/botctl.c`). The simulator uses the whole turn: ~9% of rails flip, 4–5% each way. Rockets too (they leave on the final yaw in the simulator) | `HITSCAN_QL` | 🧪 being built: the simulator matches the server |
| Hand model (mouse smoothing): not the cause; he overshoots less than pros (7.8% vs 11.6% of rails) | – | no change |
| Duel preset leftovers (the servers run the duel factory; the simulator had free-for-all's): shortest time between jumps 100 → 50 ms; wading speed 0.8 → 0.75; pickup reach in height 56 → 51 units (4,656 duel pickups on the play-test and public servers: 99.9% within 50.4, none at 56; free-for-all's reach is ~66: 219 of 7,767 at 56 or more); crouch step jump: off in duel, never in the simulator. All library settings already (no rebuild) | `DUEL_QL=1` | 🧪 being built (owner, ~13:00: "might as well get them right") |
| Zoom as a person sees it: sight error ×0.4 zoomed, fine-aim threshold in hand degrees | `ZOOM_PERCEPT=1` | ✅ in v0.3.7 since save 50 |

## 3. Senses: inputs that give him more than a person knows (audit 2026-10-20)

| Input | Today | As a person perceives it | Pro measurement | State |
|---|---|---|---|---|
| Footsteps ("heard" rule) | any enemy <800 u moving >250 u/s heard every frame, in the air too, through walls; fresh error each frame averages to ~13 u | a footstep every 0.55 s on the ground above 150 u/s (pros' demos: 1.8/s at 250–400 u/s, 2.35/s above 400, 0.02/s in the air), jumps; one 10° error a sound | 1,379 pro demos | 🧪 `HEAR_FIX` tried |
| Hearing block | exact distance (loudness), exact closing speed, fresh 10° error each frame (~1.5° averaged) | distance ±30%, no closing speed, the hum's error drifting (1 s) | as above | 🧪 `HEAR_FIX` tried |
| Sounds from cut-off parts of the map | every event by distance only | `HEAR_QL=1`: the server sends a player's sounds only when he is in your potentially visible set (the map's precomputed visibility; Quake Live does not muffle sound through walls: the "void" between map sections is what cuts it) | 232 pro demos: 0 enemy sounds arrived while he was outside the snapshot; our visibility test agrees with the server's on 98.99% of frames; a line-of-sight rule would cut 2/3 of what the game sends | ✅ on, no change (report section 2b) |
| **`HEAR_FIX=1` built** (with `HEAR_QL=1`) | | footsteps every 0.55 s above 150 u/s on the ground, none in the air; 10° and ±30% one draw a sound; no closing speed; hum error drifting 1 s | unit check: every footstep 22 frames apart, 0 heard placements without a sound; servers' inputs match 99.7–100% | ✅ bef5e8b (identical off); also fixes a stale wall-hearing cache on the servers |
| **Hearing result** | facing the hidden enemy within 20°: 53% / 44% running (near / far), 50% / 33% in the air; turning to a sound: 67% turn, end 19.7° off | with the fix: 50% / 35% running, 41% / 27% in the air | pros: 44–48% running, 38–41% in the air; 70% turn, end 6.9° off | 🧪 cost: none with both sides fixed (0.549 vs 0.550); **with only his side fixed 0.477 vs 0.55: about 7 points** (32 games each, untrained): he was using the leak; training should win it back |
| Enemy velocity (and the leads, rocket floor aim, believed place) | true velocity 200 ms late, no noise | perceived: angle rate across (drift input), size change along; delay, noise, threshold | strafe-reversal latency | 🧪 |
| Distance to a seen enemy | exact | error proportional to distance | rocket miss along vs across the line | 🧪 |
| Projectiles | exact, no reaction delay, exact fuse and closest pass; yet he does not dodge rockets launched out of view (speed away flat, then −120 u/s by 0.8 s) | noticed after 100 ms in sight, read 100 ms late (earliest response ~200 ms), fuse only if seen since launch | pros (12,259 rockets launched out of view): dodge starts 0.05 s, half by 0.225 s, +50 u/s at 0.35 s | 🧪 `PROJ_FIX` tried; per-seat cost check ~10:30 |
| Strafe reversal | his view's turn crosses zero 0.05 s after the enemy reverses; the same with the velocity fix | – | pros 0.10 s (3,833 events; his 89, more queued) | 🧪 he reacts ~50 ms sooner than pros, **not from the velocity input** |
| Steady tracking (lightning range, view rate vs the enemy's bearing rate) | follows at 0.98–1.02 at every speed; wobble 39–52°/s | – | pros follow slow motion at 0.74–0.84, fast at 0.92; wobble 41–53°/s | 🧪 his following is perfect, a person's lags; wobble the same |
| Tracking loop (view rate against the enemy's bearing rate, best-fitting delay) | 50 ms late, follows at 0.98; the same with the velocity fix; with no velocity at all 50 ms, 0.94 | – | pros 100 ms late, follow at 0.88 (0.75 slow) | 🧪 his whole loop is ~50 ms quicker: the reaction delay sets it, not the velocity input; react 150 ms should match |
| Strafe reversal, 608 events | his view crosses zero at 0.05 s, half-peak 0.15 s | – | pros 0.10 / 0.175 s | 🧪 confirmed |
| Rockets near a grounded enemy (within 120 u, 200–500 / 500–1,000 u) | 53% / 25%; with a range fix 46% / 7%; with no velocity 60% | – | pros 33% / 20% (they aim at the floor in front) | 🧪 not velocity, not range; suspect the rocket aim helper's exact solves (damage per rocket and v0.3.5 vs v0.3.6 queued) |
| Drift input sizes (from the tracking) | – | delay ~50 ms; slow slides read ~25% slow (0.75 under 50°/s, 0.92 at 150); threshold 2°/s; no extra noise needed | – | 🧪 firming up |
| **Built** (branch `v038-senses`, identical with all off; the servers' inputs match 99.8–99.9%) | | `VEL_FIX=1` (200 ms, Weber 0.2, under 30 u/s = 0) · `RANGE_FIX=1` (15%) · `PROJ_FIX=1` (100 + 100 ms) · `SENSE_MINOR=1` (facing ±15°, reaction-delayed state, drop time only to the dead and the killer, MG/SG/HMG no trails, item clock ±0.75 s when only heard) | unit checks pass | ✅ c2b02af, cadf1a1, d2efb00; sizes may change with the aim sweep |
| **Cost of each fix, his side only** (frag share against v0.3.6's end, untrained, 2 maps × 16 games, noise ±0.04) | off 0.550 | hearing 0.477 · projectiles 0.565 · velocity 0.556 · distance 0.565 · all four 0.523 | – | 🧪 only hearing costs him (~7 points); training should win it back |
| Enemy facing, crouch, weapon | this frame's truth | his reaction delay; facing coarse | – | 🧪 |
| Item timers | a perfect stopwatch | ±0.5–1 s when only heard | pros' item arrival spread | 🧪 |
| Dropped weapon time left | exact, even unseen | only if the death was seen or heard | – | 🧪 |
| Machine gun / shotgun lines | visible like the rail | rail and lightning only | – | 🧪 |

## 4. New inputs

| Change | Switch | State |
|---|---|---|
| Target drift: how fast the enemy slides across his crosshair (yaw, pitch, and a smoothed pair: 4 inputs, 864 → 868), from what he perceives; delay, noise, threshold as settings to be sized from pro play (`DRIFT_DELAY`, `DRIFT_SIGMA`, `DRIFT_WEBER`, `DRIFT_MIN`) | `DRIFT_IN=1` | ✅ (6df64eb: identical off; a v0.3.7 save widened answers the same, 0 of 5,376 choices differ); sizes 🧪; ❓ |
| The new input's attention gate opens slowly from the run's start (the run must pass its own start minute as `--gate-start`, or it opens at once) | | note for the run file |

## 5. Run composition and pay

| Change | v0.3.7 | v0.3.8 | State |
|---|---|---|---|
| Weapon pay by order (1st/2nd/3rd of RL/LG/RG a life) | 0.10/0.06/0.05 since save 50 | 0.10/0.06/0.05 | ✅ keep (owner) |
| Long-range rail pay | 0.25 since 22:57 (lever 1; did nothing) | 0.12 | ✅ back (owner: "safer") |
| Rail starts: facing, length | within 15°, 30 s since save 110 (lever 3) | within 15°, 30 s | ✅ |
| Rail starts share | 10% | 15% (the 5 points from whole games: 70 → 65%; pro starts, item and jump runs unchanged) | ✅ from whole games (owner); watched, and back to 10% once it has done its part |
| Jump key read | 50% of frames | every frame | ✅ (owner) |
| League | v0.3.4, v0.3.5, v0.3.6 ends, 8% each | v0.3.5, v0.3.6, v0.3.7 ends, 8% each (v0.3.7: 70% against v0.3.6) | ✅ |
| Checks | alternate v0.3.6's end and v0.3.1's | alternate v0.3.7's end (previous best) and v0.3.1's; the old networks play under the new rules: margins lower at first | ✅ (owner) |
| Reaction delay (how old his view of the enemy is when he decides; not a person's whole reaction, which includes the hand) | 100 ms | **options table from the sweep, each setting against the pros' numbers** (reversal turn-back, tracking delay and follow, lightning, rail, rockets); pick at or slightly better than the pros | ✅ **125 ms, everything on** (owner, 17:00: "I know it's better than the pros, that's fine") |
| League opponents' delay in training | – | the same as his: the trainer gives every seat of a simulator one delay (`env.react_frames`), the league's too (corrected 15:50: I said earlier they kept 100 ms; that is true only of the checks) | ✅ nothing to decide |
| Delay of the old network in the checks (the check tool takes each network's own: v0.3.7's end 100 ms) | – | give both seats his delay (`--opp-react-ms`), so "against the previous best" compares skill under the same limits; or keep each its own | ✅ the same delay as his (owner) |
| Mouse filter | – | 4 Hz (owner, ~13:20: "Let's just do 4Hz"; the 3.5 Hz numbers shown for reference) | ✅ (owner) |
| All the sense fixes, fire timing, drift input, mouse filter | – | all in | ✅ (owner: "All in") |
| Far-rail fixed price | held | | ⏸ (it would invite low-chance shots) |

## 5b. Reaction delay: the options (save 220 with every sense fix on; untrained at the new delay)

| Setting | Strafe reversal: turn back / half peak | Tracking delay, follow at 100 ms | Lightning hits | Rail hits | Rockets that hit | Rockets near (200–500 u) |
|---|---|---|---|---|---|---|
| **Pros** | 0.10 / 0.175 s | 100 ms, 0.88 | 31% | 42% | ~28% | 33% |
| 100 ms (today) | 0.05 / 0.15 s | 50 ms, 0.92 | 47% | 44% | 55% | 62% |
| 125 ms | 0.075 / 0.15 s | 50 ms, 0.91 | 44% | 42% | 54% | 57% |
| 150 ms | 0.075 / 0.125 s | 50 ms, 0.885 | 39% | 33% | 53% | 57% |
| 175 ms | 0.075 / 0.175 s | 50 ms, 0.875 | 34% | 29% | 52% | 54% |
| **125 ms, everything on** (fire timing + mouse filter 4 Hz) | 0.05 / 0.15 s | 50 ms, 0.95 | 41% | **42%** | 53% | 55% |
| **150 ms, everything on** | 0.075 / 0.15 s | 50 ms, 0.93 | 38% | 35% | 52% | 56% |
| 150 ms, everything on, filter 3.5 Hz (reference) | 0.075 / 0.15 s | 50 ms, 0.93 | 38% | 36% | 54% | 53% |
| **175 ms, everything on** | 0.075 / 0.15 s | 50 ms, **0.887** | **33.5%** | 33% | 52% | 56% |

Everything on: 383–455 reversal events a setting, ~600 rail shots (±2 points). With the mouse filter on he follows more fully (it smooths his small corrections), so each delay sits a little further above the pros' follow than without it. 3.5 Hz changes nothing measurable against 4 Hz.

| Option | Lightning vs pros | Rail vs pros | Follow vs pros | In short |
|---|---|---|---|---|
| 125 ms | +10 points | level | +0.07 | clearly better than pros at tracking; rail at their level |
| 150 ms | +7 | −7 | +0.05 | in between |
| 175 ms | +2.5 | −9 | level | matches the pros' tracking; rail below |

- Lightning comes to the pros with the delay (175: within 3 points); rail falls below them from 150 (samples ~600 shots, ±2 points).
- The rocket gap is mostly the mix of distances: by distance band he is near the pros (250–500 u: 48% hurt vs 45%); the rocket aim helper's exact aim point added ~8 points there in v0.3.6. A perceived aim point later, not urgent.
- These numbers are before training at the new delay: training raises them again, so a pick that matches the pros now ends a little better than them.
- ❓ the owner's pick. My lean: **150 ms** (tracking and lightning near the pros, rail recoverable in training; 175 costs rail more).

## 6. Aiming with the body (the owner's play test, 2026-10-19: "he still 'waves' the lg around … people usually aim with small hand movements and by strafing")

| Change | Switch | State |
|---|---|---|
| Measure: how much of his tracking is the mouse vs his own strafing; mirror strafing; the "wave" (mouse jerk and reversals); his speed while firing; whether mirror-strafing also dodges (the enemy's hits on him). Bobby vs pros vs the owner | – | 🧪 today (results by 18:30) |
| Already pointing that way: pros' mouse follows a strafing enemy at 0.74–0.92 of his angle change, Bobby's at 1.0 | – | 🧪 measured |
| **The wave is real**, lightning fire 150–700 u (Bobby 2,828 s; the owner 110 s; v0.3.6 on the real server): mouse acceleration rms Bobby 4,845°/s², the owner 1,360–1,435; turn reversals 8.2/s vs 3.5–3.9/s; share of view-turn power above 4 Hz 53% vs 14–17% (the target itself 3–6%). v0.3.6 on the server: 4,797, 8.1/s, 52%: not a simulator artefact | – | 🧪 pros parsing; where it comes from (his commands vs the hand model) next |
| Mirror strafing: neither Bobby (0.00) nor the owner (−0.05 to +0.01) strafes to cancel the angle; both leave all the tracking to the mouse | – | 🧪 pros to settle what humans do |
| Body while firing: Bobby 283 u/s, 1.0 strafe changes a second, still 7% of the time; the owner 228 u/s, 1.65/s, still 15–20% | – | 🧪 the owner reverses his strafe more |
| The dodge: the enemy's lightning on him: strafing against the enemy's motion 43%, with it 55%, still 62% (rail 28 / 42 / 59%); the owner's sessions the same way | – | 🧪 moving against the enemy is the dodge |
| Expected to help in v0.3.8 without a new rule: the slower reaction and perceived velocity make a perfect mouse harder, so the body's share should pay more; the drift input tells him how fast the enemy slides, which is what matching a strafe needs | (the aim changes) | re-measure after a few hours of v0.3.8 |
| **Verdict:** the wave is his hand. His turn command is near white noise (84% of its power above 4 Hz, a sign change 12.8 times a second) and small turns pass almost unsmoothed. Pros: mouse acceleration 2,455°/s², 4.6 reversals/s, 29% above 4 Hz (Bobby 4,845, 8.2/s, 53%; the owner 1,400, 3.7/s, 15%) | – | 🧪 measured (337 pro demos) |
| **Strafe-aiming does not hold:** nobody (pros 0.02, the owner −0.06, Bobby −0.02) cancels the enemy's motion with his own; the mouse does all of it. What people do: reverse their strafe more (pros 1.59/s, the owner 1.65/s, Bobby 1.0/s) and follow an enemy's reversal sooner (pros 0.25 s, Bobby 0.40 s) | – | 🧪 that is dodging, not aiming |
| **Human hand bandwidth:** a low-pass on the view's turn whose cutoff rises with its speed (4 Hz + 0.5 Hz per °/frame: small corrections smoothed, flicks let through), every weapon. Sized offline on his own lightning commands: acceleration 4,600 → 2,613°/s², reversals 8.3 → 4.8/s, above 4 Hz 43 → 27% (pros 2,455, 4.6, 29%). Cost: a small correction 25 ms later (50% at 50 ms, 90% at 100 ms); a fast flick 60% done in 8 frames vs 66% | `HAND_BAND=1` (`HB_FC=4`, `HB_BETA=0.5`) | ✅ f3e5fd4 (identical off; the servers' filter matches to 2e-6) ❓ |
| Dodge practice: rounds where the enemy fires lightning or rail at him (a drill, no pay); moving against the enemy's strafe is worth 12 points of lightning and 14 of rail on him in the simulator | (to build) | ⏸ v0.3.9 |
| Lightning-fight starts | – | ⏸ dropped: strafe-aiming is not what humans do |

## 7. Later revisions (proposed, not in v0.3.8)

| Change | Why | State |
|---|---|---|
| Rocket-jump specialist trained alone, then used as a teacher (B-272) | rocket-jump runs had under 1 rocket in 200 tries | ⏸ tomorrow (owner) |
| The finisher: pro starts at the moment an enemy is wounded and pulling away, rail in reach | he switches and fires 1.3% vs the pros' 21% | ⏸ v0.3.9 |
| Ledge grabs a few frames early as the game does; rockets at a step's corner (18–74 damage in the game, 0 in the simulator); grenade splash close in about 12 points too strong | the stairs and splash audit (591 cases) | ⏸ v0.3.9 |
| Reaction by situation: a surprise (enemy appears) slower than a tracked reversal | today's sweep uses one delay for both | ⏸ after the sweep |
| Strategy layer (v0.4) | when the checks against the previous best flatten for two days (they flattened at ~70% vs v0.3.6 since update 200) | ⏸ |

## 8. Today's tests (results filled in)

| Test | Result |
|---|---|
| Rail cause: tracking vs overshoot vs fire timing | |
| Server substep mismatch: hits flipped | |
| Senses: pro limits and each fix on/off against v0.3.6's end | |
| Drift input: identical with it off; conversion changes no choice | ✅ 0 of 5,376 choices differ |
| Aim sweep: reaction 100 / 125 / 150 / 175 ms with the sense fixes on (pro numbers to match) | **100 ms** (307 reversals): reversal crossing 0.05 s (pros 0.10), tracking 50 ms late at 0.96 (pros 100 ms, 0.88); lightning 47% (pros 31%); rail 44% (pros 42%); rocket hit share 55% (pros ~28%); rockets near the enemy 62% (pros 33%). **150 ms** (439 reversals): crossing 0.075 s, tracking follow 0.885 at 100 ms (pros 0.88), lightning 39%, rail **33%** (pros 42%), rocket hit share 53%, rockets near 57%. **125 ms** (361 reversals): crossing 0.075 s, follow 0.907 at 100 ms, lightning 44%, rail 42%, rocket hit share 54%, rockets near 57%. Without the fire-timing fix in any: the final arm (every switch, 150 ms provisional, filter 4 and 3.5 Hz) adds it (it lifted rail 4–20 points). 175: ~14:45 |
| Aiming with the body (section 6) | |
| Fire timing: hits by weapon, off → on (save 220 against itself, 32 games a map) | rail 35.4 → **55.8%** (Blood Run), 45.6 → 49.6% (Sinister); lightning +2 to +4; machine gun +2 to +6; rockets ±3 (noise); plasma 26 → 27% |
| Merged code (2215887): all off identical to 6df64eb; two-player check with all twelve switches on; v0.3.6 ident; every unit check with everything on (3 checks read off by the random stream or the wall hearing on the test map, none a merge bug); 3-minute trainer with all on | ✅ one fix found (the distance error with the drift input read as a new sighting) |
| v0.3.8 dry run (from save 380, every switch, 150 ms provisional, 12 updates, 14:20–15:05) | ✅ exit 0; step 0.029–0.032 an update (v0.3.7: 0.028–0.030); the largest single output 0.013 (as v0.3.7's dry run); frags back from 0.58 to 1.67 a match-minute by update 12 (the restart and the new limits); speed unseen 318–332 (v0.3.7 320–326); in view 294–308 |
| Its check: against v0.3.7's end and against v0.3.1's (160 games each, v0.3.8's rules) | against v0.3.1's **72.4%** (139–18); against v0.3.7's end **41.9%** (50–99): v0.3.7's end plays at its own 100 ms against his 150 after only 12 updates, the size the delay and the hearing cost was expected to be (hearing alone ~7 points). The checks against the previous best should give both seats the same delay (❓ below) |
| End-of-day check of v0.3.7 (save 380, v0.3.7's rules) | ✅ against v0.3.6's end **71.7%** (137–19; every map above 58%); against v0.3.1's **77.5%** (146–9). v0.3.7's end joins the league |

## Files

Measurements: the scratchpad folders `railmeasure`, `railcause`, `inputaudit`, `v038drift`. Code: branch `v038`.

# Tonight's report: v0.3.6's day, the tests, and what changes in v0.3.7

*Written for the play test of 2026-10-19 ~19:30. **v0.3.7 is already training (since 17:53); you play v0.3.6's end while it trains.** v0.3.6 trained from Sun 21:50 to Mon 15:46 (260 updates; stopped at the save,
optimizer kept). The play-test server runs that save: "BobbyBones v0.3.6", UDP 27971. The one-page sheet of v0.3.7 is
[RUN_v0.3.7.md](RUN_v0.3.7.md).*

## 0. Where v0.3.6 ended

Checks: 160 ten-minute duels on ten maps, seats swapped, aim level 3 (the same network against itself reads 48.8%; a check
moves 3 to 4 points by chance).

| Update | 20-60 | 80-120 | 140-180 | 200-250 |
|---|---|---|---|---|
| Against v0.3.1's end | 48.8, 53.3, 53.5 | 52.5, 52.2, 51.8 | 53.9, 54.9, 54.4 | 55.0, **57.0**, 55.0 |
| Against v0.3.4's end (the public server's network) | 47.2, 47.4, 49.3 | 51.2, 48.8, 50.1 | 51.2, 48.3, 51.8 | **53.8**, 53.3, 52.8 |

- He passed the public network around update 180 and held 53 to 54% for the last four checks; still rising at the stop.
- Movement with the enemy unseen: 23 take-offs a minute near, 30 far (v0.3.5: 12 / 17); speed 314 to 315 (v0.3.5 ~300). Solo runs 341.
- With the enemy in view: 0.4 take-offs a minute (you: good, jumping in fights makes you easy to hit), speed 291.
- Frags 2.0 to 2.2 a match-minute, mega and red armor 2.0 a minute. Jump runs made 35% (now weighted to the hard ones).
- Rail past 900 units: 8 shots in 659 minutes. Rail starts in v0.3.7 are for this.
- Sparring against the game's Nightmare bot on the server tonight: **won 11 to 4**, speed 315, but only 3 rockets fired
  (lightning and plasma 90% of the time; Nightmare used the shotgun only).
- Blood Run and Sinister were his weakest maps (45 to 48%); the dig found no stuck spots (he is stuck less than v0.3.4),
  but rocket fights on Sinister and the first mega on Blood Run; both maps were back at 51 to 58% in the last checks.

## 1. Bug fixes in the simulator

### Auto-hop (measured in the game tonight, flat test map, 4 s of strafe jumping from 320)

What the game does:
- The server switch `pmove_AutoHop` is 1 in both factories. Whether a held jump jumps again on landing is each player's own
  `cg_autoHop`. With 1, a held jump re-jumps on every landing; with 0, one jump, then he runs.
- The servers give Bobby `cg_autoHop 1` (`BOBBY_AUTOHOP=1`); your client has 1 too.
- Holding jump costs speed (the game counts the jump key in the move, wish speed x0.82): **holding is the worst way to hop.**

| How the jump is pressed | Speed after 4 s (the game) |
|---|---|
| Held through every landing | 327 |
| Pressed 1 frame before landing | **596** |
| 2 / 3 frames before | 589 / 582 |
| On the landing frame | 544 |
| 1 / 2 / 3 frames late | 455 / 405 / 373 |

- The pressed rows are the same with auto-hop on or off; only the held row differs (off: one hop, then 327 on the ground).
- **The simulator reproduces every case exactly** (22 flat cases, 0.00 units a frame off) with auto-hop on, and with it off
  matches the off cases exactly. Nothing was wrong; v0.3.7 keeps it on (`AUTO_HOP=1`, now written into the network and given
  to his bot on the servers, so training and the servers can never disagree).
- **What was wrong is the reading of his jump:** his keys are read one frame in four, so after a landing his press could be
  up to 3 frames late (455 to 373 instead of 544 to 596). v0.3.6 was measured: 0 of 2,894 landings with jump held through (he
  never holds), 46% with no jump after the landing, 30% re-pressed late. v0.3.7 reads the jump key every frame
  (`JUMP_EVERY`; the other keys and the finger limit as before). A scripted hopper pressing 1 frame late: 456 -> 598.
  v0.3.6 asked every frame presses jump 44 times a minute instead of 24 and runs 6% slower at first, so it starts on 25% of
  frames and is raised live (50%, then 100%) as he adapts.

### The duel servers' movement differs from free-for-all (found tonight)

All lab measurements so far were made in free-for-all. The duel factory (the play-test and sparring servers):

| Setting | Free-for-all | Duel | Simulator |
|---|---|---|---|
| Speed from the forward key alone (`pmove_BunnyHop`) | yes | **no** (held forward: 500 -> 320) | yes (`QL_FWD=1`) |
| Shortest time between jumps (`pmove_JumpTimeDeltaMin`) | 100 ms | 50 ms | 100 |
| Crouch step jump | on | off | not modelled |
| Wading speed in water | 0.8 | 0.75 | 0.8 |
| Item height (pickup reach) | 35 | 15 | measured on ffa |

- **v0.3.7 sets `QL_FWD=0`** (duel): the simulator then matches the duel measurements 1,362 of 1,372 (1,202 with v0.3.6's
  setting). Strafe jumping is unchanged; forward-only hops stop gaining speed, as in a real duel. ✅ in (your yes).
- The other four: small, fixed in the next days.

### Stairs, ledges and splash on steps (591 cases, the game against the simulator)

- Overall 4,126 of 4,190 measures within 5%; the game repeated itself exactly in every double take.
- **Blood Run's stairs-to-yellow jump**: the game falls short too (peak 535.4 against the lip at 536.1 from the pros' take-off
  at any speed 320 to 500); arriving in the air makes it in both. The simulator was right.
- **Ledge grabs (40 to 56 high)**: the game steps up onto the ledge while he is still rising; the simulator only once he
  falls (5 frames later, 16 to 23 units lower at the top). Both end on the ledge. Fix later.
- **Missiles were a small box, now a point** (`MISSILE_POINT`, in v0.3.7, your yes): rocket blasts on stairs at the game's
  point 214 of 216 (was 0; 50 more than 3 units early); worst 10% of blasts 9.8 -> 3.8 units off; damage the same as the
  game 197 -> 214 of 251; grenades come to rest 67 -> 12 units from the game's spot.
- Left for later: 5 rockets at a step corner do 18 to 74 in the game and 0 in the simulator; grenade splash about 12 points
  too strong close in.

### Other fixes in v0.3.7 (your yes)
- **Respawn** after 2.1 s, as the game (was instant; 19,809 pro respawns: earliest 2.1, median 2.125).
- **Spawn points**: the maps' start points used too (Furious Heights: 7% of pro respawns).

### Not in v0.3.7
- Hearing through the map's visibility data (`HEAR_QL`): built, waits for a measurement in the game.
- Rockets leave a frame late on the servers (a plugin bug, B-268): fixed before he plays on a server again.
- The game's settings dump: everything else matches (damage, reload, splash, projectile speeds, gravity, jump, overtime);
  knockback of lightning and shotgun to be traced.

## 2. Setting changes (speed: the same training, faster)

| Change | Before | After |
|---|---|---|
| Simulator (identical numbers) | 59-62 ms a frame | 47-53 ms (-12 to -21%) |
| Learning step without its waits on the card (`--learn-nosync`) | 124 s | 109 s |
| Learning while the next games play (`--overlap`, decoupled PPO) | 232 s an update | **~159 s (-32%)**, same step size (kl 0.026) |
| 180 learning pieces instead of 360 | | faster (137 s) but **learns less** per update (kl 0.017): not used |
| Fused optimizer | | no gain: not used |

About 45% more updates in a day. v0.3.7 runs with `--overlap 1 --learn-nosync 1`.

## 3. Run composition (set by you tonight)

| Round kind | v0.3.6 | v0.3.7 |
|---|---|---|
| Whole games | 70% | 70% |
| Mid-game starts (his own games) | 10% | 0% |
| Pro starts (5,000 real moments a map from 1,400 pro duels) | – | 10% |
| Rail range starts (15 s, pro rail spots) | – | **10%** (the rocket jumps' 5% moved here) |
| Rocket-jump runs | – | 0% (needs a teacher first: B-272) |
| Item runs | 10% | 5% |
| Jump runs | 10% | 5% |
| League | v0.3.1's end, 25% of games | **the last 3 best: v0.3.4, v0.3.5, v0.3.6's ends, 8% each** |

Checks: alternate the previous best (v0.3.6's end) and v0.3.1's end (control); end of day 80 + 80 games; a day's end joins
the league only at 50% or more against the previous best.

## 4. Training and pay changes

| Change | State |
|---|---|
| Chain-hop pay `HOP_CHAIN=0.005`: each hop that keeps speed (within 15) pays more, x1 to x3; a loss, 150 ms on the ground or the enemy in view ends the chain; nothing in view. A good hopper unseen earns 0.4-0.75 a minute, under a frag | ❓ |
| Jump read on 25% of frames between the hand's readings, raised live to 50% and 100% | ✅ |
| `QL_FWD=0` (duel movement) | ✅ |
| Pay kept from v0.3.6: damage taken 0.75, speed pay 0.25 / 0.4, long-range rail 0.12, blind rockets free | ✅ |
| Item pay (0.35 / 0.35 / 0.18) kept | ✅ |
| Rail nudges if stalled at about update 80 (my call, flagged) | ✅ |
| Run length: started 17:53 Mon (your go), to 16:00 Tue (the default stop from now on), play test 19:30 Tue | ✅ |

## 5. Anything else of note

- The public server's setup is out of the GitHub repo (kept privately); `main` pushed.
- A rented card with more memory for v0.4 is on the backlog (B-271), only if learning stays the larger part.
- The week: one version a day, v0.4 when the checks against the previous best flatten for two days.

## 6. Test results

| Test | Result |
|---|---|
| Stop at a save, kept, server built | ✅ 15:46 save 260; server up, his inputs in the real game match the simulator's |
| Stairs, ledges, splash, auto-hop in the game | ✅ above (591 cases, 4,126/4,190 within 5%) |
| Settings dump | ✅ duel factory differences found (section 1) |
| Learner arms | ✅ overlap + nosync: -32% an update, same learning |
| All new code with its switches off | ✅ identical to v0.3.6 (worker messages, 3 maps; two-player check; v0.3.6's start check) |
| Full dry run of v0.3.7, 15 updates, step per output | ✅ step 0.028-0.032 a update, the largest single output 0.013; frags back from 0.6 to 2.0 a match-minute (restart warm-up plus the 2.1 s respawn); speed unseen 307-311 (v0.3.6 314: the duel movement), take-offs unseen 34-35 a minute (23-30), in view about 1; rail starts from update 7: first shot within 10 s in 26%, hits 55% near, 15% mid, 0 far yet; rocket-jump runs: under 1 rocket in 200 tries, so taken out |
| Its check against v0.3.6's end | not run separately: the run started at 17:53 and its own checks against v0.3.6's end begin at update 10 (about 18:45) |

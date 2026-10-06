# BobbyBones: results log

What we tried, what we measured, and what it means, **including what did not work**. Newest first. Each
entry names the backlog items it settles or raises ([BACKLOG.md](BACKLOG.md), `B-nn`); the plan is in
[PLAN.md](PLAN.md); log formats are in [LOGS.md](LOGS.md). Numbers are from local runs; raw data lives in
the git-ignored `data/` folder (paths given so results can be re-checked).

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

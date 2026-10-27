# AIM2: the new human aim model (proposal for the run after v0.5.1, 2026-10-27)

Branch `aim2` (from v0.5.1's code, 120c086; worktree `ql-bot-aim2`), the play build `play-aim2` (from `play-v05`; worktree
`ql-bot-playaim2`). The reference for the limits as they are today: [`docs/v0.5.1/AIM_LIMITS.md`](../v0.5.1/AIM_LIMITS.md)
(cited as AIM_LIMITS 2.x). Everything here is a switch, off by default: with every switch off the simulator is v0.5.1's to
the bit (section 7).

**Status of the numbers (FINAL, 2026-10-27 18:20).** The `!aim` table (section 9) is fitted on a fixed-seed random sample of
the POOLED pro demos (100 a map, 1,000 drawn, 968 read: 626 tournament, 374 archive; the tournament set's old map versions in
the `_...` subfolders included; the list is `aim2cal/pros_pooled.npz.list.txt` in the session scratchpad), against the pros'
per-demo DISTRIBUTIONS: default at the pros' median, worse near their 10th percentile (25-50% below their mean), better near
their 90th. The simulator's side: self-play of v0.5.1's last save (trained under the OLD model: the immediate effect, not the
adapted one), five maps x four 5-minute games a level; the 80-game suite with v0.4.2b's end (section 4.3).

---

## 1. What changes, in one table

| | Today (v0.5.1) | AIM2 |
|---|---|---|
| Error for a moving target | `PERCEPT_SPEED` x the world bearing's rate (deg/s), capped by the weapon in hand (rail 0.001, LG 1.5, the rest 1.5): a flat +1.5 deg whenever the target moves, however well he follows it | **retinal slip** (the target's angular rate minus his view's, as of his read delay) and **eccentricity** (the angle from his crosshair to the target, as of the delay); no weapon in the formula |
| What the sight error reaches | the perceived enemy place itself: his map memory, belief, places, tokens, the lead's geometry | **only the aim**: the crosshair-to-target angles, the on-target flag, the burst-to-enemy closeness and the final angles of the lead and rocket aim inputs; the world picture gets the delay, the distance error and the velocity error only |
| Focus (the first 2 s of a sighting) | the read delay 2 frames shorter (100 -> 50 ms), 1 frame longer after | the delay stays (100 ms, +25 ms after); the base sight error x 0.75 while focus lasts |
| Flinch | an instant kick of the error (`add` x N(0,1)) plus a sustained `add` on its sigma | the sustained part only (it builds within the error's 0.15 s memory and fades over `FLINCH_TAU`); values live |
| Zoom | x 0.4 on the base error only | x 0.4 on every term (base, flinch, slip, eccentricity) |
| View inertia | `MOUSE_SMOOTH` 0.75 / 0.2 before the 4 Hz hand band | unchanged by default; `AIM2_SMOOTH_K` (live) can scale it down (section 5) |

---

## 2. The switches (all PLAY_VARS; the numbers live in `live.json`)

`sim/duel_env.py` (and the generated `duel_env_ffa.py`; `tools/make_ffa_env.py` updated for the one changed anchor):

| Switch | Default | What it does | Code |
|---|---|---|---|
| `AIM2` | 0 | the slip + eccentricity terms replace the old speed term; zoom on every term | `observe()`, `_aim2_note()`, `_aim2_err()` |
| `AIM2_W` (live) | 1 | blend: old speed term x (1 - W) + new terms x W; the zoom's reach on the non-base terms by W. **W = 0 is the old error exactly** | `observe()` |
| `AIM2_C_SLIP`, `AIM2_S0`, `AIM2_CAP_SLIP` (live) | 0.02 deg per deg/s, 15 deg/s, 2.0 deg | error + min(C x max(0, slip - S0), CAP) | `_aim2_err()` |
| `AIM2_C_ECC`, `AIM2_E0`, `AIM2_CAP_ECC` (live) | 0.04 deg per deg, 2 deg, 2.0 deg | error + min(C x max(0, ecc - E0), CAP) | `_aim2_err()` |
| `AIM2_SPLIT` | 0 | the world picture apart from the aim error | `observe()`, `_raim()`, `_v14()` |
| `AIM2_SPLIT_W` (live) | 1 | the world picture keeps (1 - W) of the sight error (**0 = today exactly**) | `observe()` |
| `AIM2_FOCUS` | 0 | focus lowers the sight error instead of the delay | `observe()` |
| `AIM2_FOCUS_GAIN` (live) | 0 frames | the delay cut while focus lasts (2 = today's) | `observe()` |
| `AIM2_FOCUS_SIG` (live) | 0.75 | the base sight error x this while focus lasts (1 = today) | `observe()` |
| `AIM2_FLINCH` | 0 | a hit grows the sustained flinch only, no instantaneous kick | `step()`, `note_hit()` |
| `FLINCH_PER_DMG`, `FLINCH_MAX`, `FLINCH_TAU` | the aim level's (0.25, 6, 0.5) | now also PLAY_VARS and live (they were environment-only: a server got the level's values) | `live_values()` |
| `AIM2_SMOOTH_K` (live) | 1 | `MOUSE_SMOOTH` / `_FINE` x K for policy players (0 = no inertia; the hand band alone) | `step()`, the plugin's `drive()` |
| `MOTOR_NOISE`, `MOTOR_BASE` | the level's | now PLAY_VARS (a checkpoint and policy.npz carry them) | |

**How the slip and the eccentricity are read.** Every `observe()` (the plugins call it every frame too) keeps one row a
player in `a2_hist`: his view (yaw, elevation) and the true bearing from his eye to the enemy's acquired place (`self.known`
+ 4 units, as `opp_hist` keeps it) with the acquired flag. `_aim2_err()` reads the row of his read delay (the same frame of
the past as the place he reads: `pick` with focus, `react_frames` or the seat's delay without) and the one before it:
slip = |(bearing change - view change) per frame| / 25 ms, the yaw part x cos(elevation); eccentricity = the angle between
his view and the bearing on that row. Both 0 unless the enemy was acquired on both rows (on the first frame of a sighting the
eccentricity counts, the slip does not). Scripted players get no error. `aim2_clear()` empties the history (the plugin calls
it where it clears `opp_hist`). The terms are added to the sigma of the existing AR(1) error (`PERCEPT_TAU` 0.15 s), as the
old speed term was: the error is a slowly wandering offset, not a fresh draw each frame.

**Who reads `known` under `AIM2_SPLIT` (every consumer in `observe()`).**

| Consumer | Gets | Note |
|---|---|---|
| `rel` (the enemy's place relative to him, `opp_feat`) | world | a place, not an angle to aim by |
| sin/cos of the angle to the enemy, the coarse and fine crosshair-to-enemy readings (yaw, pitch) | **aim** | |
| `on_target` (`_seg_box` along his view) | **aim** | |
| apparent size | world (its distance) | |
| `_intent` (the intention's reading of the enemy) | world | |
| `_v14`: the lead of a rocket / plasma ball | world for the meeting point (place, flight time, floor); **+ the aim's angular offset** on the final yaw, pitch and floor angles | the offset = the angle between the aim's and the world's place, so at `AIM2_SPLIT_W = 0` it is 0 |
| `_v15` (jumps, projectiles' arcs, the grenade arc) | world | |
| `_v02` (the believed place, the places, every token of the attention part) | world | |
| `_raim`: backstop distance vs the enemy's | world | |
| `_raim`: how close a rocket fired now would burst to the enemy | **aim** | |
| `_raim`: the floor aim point | world geometry, **+ the aim's offset** on its four angle inputs | the wall by it: world |
| `_drift` (off in the run, `DRIFT_IN=0`) | world place, aim angles | |
| the velocity inputs | `VEL_FIX` as before | never had the sight error |

The brain (v0.4.x) reads the same input vector; its place inputs are the world columns above.

---

## 3. The pros: targets per weapon style

**Populations.** (a) The pooled sample (the fit's reference): 968 demos, 100 drawn a map from the archive
(`<demo root>\demos\<map>`) and the tournament set (`T:\quake-demos\trance\by_map\<map>` and its `_...` subfolders, 25 ms
snapshots only) together, seed 20261027 + the map's index. (b) The whole tournament set: 5,702 of its 6,624 demos read (the
rest 8 / 32 ms snapshots or unreadable). (c) The archive: 1,385 demos, 150 a map. All read with `tools/demodump` and
`tools/pro_yardsticks.py`'s functions; the measures are `tools/aim2_measure.py` (its docstring says how each is read: a shot is
a step down of the ammunition, a hit a step of the player's own hit counter on that frame or the next, a rocket's or plasma
ball's hit the counter step due when it lands). The old map versions' collision is not the current map's: their line-of-sight
test (who is "in view", the sightings) is approximate; their hits, distances, slip and eccentricity are not affected. The
archive's pros hit 2-15% more than the tournament's (tournament opponents dodge better). The table below is (b) / (c); section
4 uses (a).

Every number is a hit share in percent (from the first pass: 1,280 tournament / 1,385 archive demos; the whole sets agree within a point).

| Measure | LG (tracking) | MG (tracking + spread) | Rail (flick) | Shotgun (close flick) | Rockets (prediction) | Plasma (prediction + tracking) |
|---|---|---|---|---|---|---|
| all shots with the enemy's place known | 31.5 / 35.3 (650k / 679k) | 31.6 / 31.9 (48k / 34k) | 34.6 / 39.6 (26k / 35k) | 77.9 / 76.3 (1.3k / 2.3k) | 35.8 / 34.8 (90k / 103k) | 12.8 / 12.0 (66k / 44k) |
| under 250 u | 42.4 / 46.7 | 45.8 / 46.5 | 44.1 / 51.4 | 74.9 / 75.4 | 72.8 / 74.1 | 27.4 / 29.8 |
| 250-500 | 34.7 / 38.8 | 38.9 / 40.0 | 37.8 / 44.3 | 83.8 / 79.8 | 43.9 / 45.9 | 15.9 / 16.4 |
| 500-750 | 29.4 / 32.1 | 32.1 / 32.9 | 36.1 / 40.6 | 73.8 / 74.7 | 23.4 / 24.2 | 9.1 / 9.6 |
| 750-1100 | 10.7 / 11.3 | 24.9 / 24.6 | 32.2 / 37.0 | 62.3 / 64.4 | 13.5 / 11.8 | 6.0 / 5.6 |
| 0.1-0.2 s after the target's strafe reversal (distance-matched, % of steady) | 64 / 68 | 73 / 71 | 50 / 52 | 87 / 92 | 99 / 103 | 93 / 89 |
| 0.2-0.35 s after a reversal | 92 / 91 | 87 / 92 | 80 / 82 | 98 / 98 | 105 / 104 | 96 / 95 |
| slip 50+ deg/s vs under 25 (distance-matched) | 90 / 90 | 77 / 73 | 88 / 94 | 98 / 92 | 105 / 105 | 87 / 90 |
| after damage in the last 0.5 s (distance-matched, % of calm) | 118 / 117 | 122 / 124 | 106 / 99 | 105 / 108 | 114 / 112 | 111 / 108 |
| after 30+ damage | 113 / 112 | 113 / 110 | 102 / 95 | 100 / 103 | 107 / 104 | 108 / 102 |
| first shot after a sighting, by the angle off then: 0-5 / 5-15 / 15-30 / 30-60 deg, hit % | 35 / 27 / 28 / 30 | | 50 / 47 / 45 / 43 (archive 56 / 52 / 50 / 45) | 95 / 88 / 90 / 89 | 38 / 50 / 54 / 48 | |
| ... its time, median s | 0.1 / 0.2 / 0.3 / 0.4 | | 0.3 / 0.3 / 0.4 / 0.6 | 0.3 / 0.3 / 0.4 / 0.4 | 0.2 / 0.2 / 0.3 / 0.4 | |
| miss along the target's motion, median (+ = led too far) | | | | | -42 / -46 u | -36 / -35 u |
| miss \|along\| / across, median | | | | | 78 / 63 u (archive 87 / 70) | 53 / 35 u (58 / 40) |
| direct hits % (rockets: within 60 u) | | | | | 11.4 / 10.1 | 10.3 / 9.5 |

What the pros' numbers say about the mechanisms:
- **No post-damage dip** in any style (distance-matched, the share after a hit is 95-124% of the calm share): a pro's aim is
  not measurably thrown off by being hit (the confound: a player who is being hit is in a mutual fight with a target that
  is shooting, not dodging; the simulator has the same confound, so the ratios are compared like for like). The flinch
  should be small.
- **A clear reversal dip** for the hitscan styles: LG and MG at 64-73% of their steady rate 0.1-0.2 s after the target
  reverses, back to ~90% by 0.2-0.35 s; the rail at 50% (a rail fired just after a dodge misses half as often again). The
  dip's timing fits a read delay of about 100-150 ms. Rockets and plasma show none (splash and leading the feet absorb it).
- **Slip costs tracking modestly** (LG 90%, MG 75%, plasma 87-90% at slip over 50 deg/s), the rail little, rockets nothing.
- **The rail flick**: the first shot's hit rate falls slowly with the angle (50 -> 43% from 0-5 to 30-60 deg) while its time
  doubles (0.3 -> 0.6 s): pros trade time for accuracy on wide flicks.
- **Rockets under-lead** (the projectile passes behind the target by ~40 u median) and miss across by ~65 u: rockets are
  aimed at the floor near the feet, the splash forgives.

## 4. The simulator beside the pros

### 4.1 The pros' spread, and where each level lands

`python tools/aim2_measure.py dist <pros> <sims...>`: each measure per pro demo (demos with enough shots of the weapon: LG and MG
200, rail, rockets and plasma 30, shotgun 10; a sighting measure 5 sightings), its percentiles, and each simulator run's value
with its percentile among the demos (pN). `dm` = hits against the pooled pros' rate at the same distances (100 = their mean);
`rev` = the hit share 0.1-0.2 s after the target's strafe reversal against the steady share (both distance-matched); `dmg` =
after damage in the last 0.5 s against calm; `flick_hit` / `flick_time` = the first shot of that weapon after a sighting: hit %,
median seconds. Columns: the old model (v0.5.1's save; v0.4.2b's end at its level 4 in the suite), then AIM2 worse, default
(v0.5.1's save and v0.4.2b's end in the suite), better.

| style | measure | pro demos | p10 | p25 | p50 | p75 | p90 | sim_v051_old.npz | suite80_old.npz | sim_lv_worse4.npz | sim_sw_g1.npz | suite80_new.npz | sim_lv_better4.npz |
|---|---|---|---|---|---|---|---|---|---|---|---|---|---|
| lg | dm | 884 | 77 | 87 | 100 | 114 | 127 | 114 (p75) | 141 (p96) | 70 (p5) | 112 (p72) | 116 (p76) | 141 (p96) |
| lg | rev | 588 | 43 | 53 | 66 | 82 | 100 | 80 (p72) | 83 (p77) | 78 (p68) | 84 (p78) | 85 (p79) | 86 (p81) |
| lg | dmg | 856 | 86 | 98 | 114 | 138 | 168 | 102 (p32) | 103 (p32) | 182 (p93) | 126 (p64) | 148 (p81) | 123 (p59) |
| lg | flick_hit | 869 | 11 | 20 | 30 | 41 | 50 | 28 (p45) | 35 (p63) | 19 (p21) | 33 (p63) | 25 (p40) | 32 (p54) |
| lg | flick_time | 869 | 0.10 | 0.17 | 0.24 | 0.30 | 0.35 | 0.28 (p67) | 0.23 (p43) | 0.46 (p98) | 0.33 (p84) | 0.32 (p83) | 0.25 (p52) |
| mg | dmg | 12 | 98 | 100 | 129 | 151 | 187 | 106 (p42) | 100 (p25) | 239 (p100) | 128 (p42) | 139 (p58) | 93 (p8) |
| rg | dm | 308 | 73 | 82 | 97 | 116 | 127 | 127 (p90) | 125 (p87) | 48 (p0) | 90 (p36) | 93 (p41) | 115 (p74) |
| rg | rev | 26 | 9 | 28 | 57 | 78 | 105 | 87 (p81) | 68 (p65) | 56 (p46) | 128 (p96) | 100 (p88) | 140 (p100) |
| rg | dmg | 201 | 53 | 83 | 111 | 147 | 187 | 82 (p24) | 81 (p24) | 122 (p59) | 108 (p47) | 137 (p70) | 104 (p44) |
| rg | flick_hit | 725 | 30 | 40 | 50 | 60 | 69 | 63 (p80) | 71 (p91) | 28 (p8) | 49 (p45) | 44 (p37) | 53 (p55) |
| rg | flick_time | 725 | 0.27 | 0.30 | 0.32 | 0.36 | 0.44 | 0.38 (p76) | 0.32 (p47) | 0.52 (p96) | 0.38 (p76) | 0.43 (p89) | 0.32 (p48) |
| sg | dm | 28 | 75 | 82 | 94 | 114 | 119 | - | - | - | - | - | - |
| sg | dmg | 30 | 74 | 83 | 105 | 126 | 156 | - | - | - | - | - | - |
| sg | flick_hit | 13 | 81 | 83 | 100 | 100 | 100 | - | - | - | - | - | - |
| sg | flick_time | 13 | 0.28 | 0.30 | 0.30 | 0.35 | 0.44 | - | - | - | - | - | - |
| rl | dm | 920 | 77 | 88 | 100 | 114 | 125 | 98 (p47) | 96 (p42) | 81 (p13) | 97 (p44) | 91 (p30) | 103 (p54) |
| rl | rev | 327 | 39 | 70 | 95 | 132 | 166 | 105 (p57) | 109 (p60) | 106 (p57) | 92 (p48) | 121 (p70) | 86 (p42) |
| rl | dmg | 818 | 69 | 91 | 114 | 140 | 174 | 92 (p26) | 91 (p25) | 108 (p42) | 87 (p22) | 97 (p31) | 106 (p40) |
| rl | flick_hit | 929 | 30 | 39 | 50 | 60 | 69 | 55 (p65) | 44 (p38) | 36 (p19) | 42 (p33) | 45 (p40) | 60 (p77) |
| rl | flick_time | 929 | 0.17 | 0.23 | 0.28 | 0.33 | 0.40 | 0.40 (p90) | 0.40 (p89) | 0.60 (p99) | 0.50 (p98) | 0.43 (p94) | 0.40 (p90) |
| pg | dm | 396 | 42 | 68 | 95 | 124 | 153 | 134 (p81) | 141 (p85) | 88 (p40) | 112 (p66) | 119 (p71) | 129 (p78) |
| pg | rev | 179 | 0 | 41 | 85 | 126 | 220 | 86 (p51) | 90 (p53) | 57 (p32) | 49 (p27) | 77 (p46) | 56 (p32) |
| pg | dmg | 310 | 19 | 62 | 98 | 149 | 231 | 81 (p39) | 106 (p54) | 103 (p53) | 97 (p50) | 108 (p55) | 98 (p50) |

The pros' spread of the main measure by source (distance-matched to each set's own mean): the tournament set lg p10/p50/p90 78/100/124 (4493 demos); mg p10/p50/p90 76/89/106 (10 demos); rg p10/p50/p90 71/96/122 (755 demos); sg p10/p50/p90 81/102/119 (55 demos); rl p10/p50/p90 78/100/124 (5057 demos); pg p10/p50/p90 48/96/149 (2278 demos) (the archive's file of the first pass kept no demo numbers).

**Where the final levels land (dm, pro percentile):**

| Style | worse | default | better | target |
|---|---|---|---|---|
| LG (tracking) | 70 (p5) | 112-116 (p72-76) | 141 (p96) | p10 / p50 / p90 |
| rail (flick) | 48 (p0); first shot 28% (p8) | 90-93 (p36-41); first shot 44-49% (p37-45) | 115 (p74); first shot 53% (p55) | |
| rockets (prediction) | 81 (p13) | 91-97 (p30-44) | 103 (p54) | |
| plasma (prediction + tracking) | 88 (p40) | 112-119 (p66-71) | 129 (p78) | |
| MG (tracking + spread) | 63 (66 of the mean) | 95-96 | 83-94 | |

Default sits inside the pros' middle half for every style (LG and plasma at its upper edge, the rail at its lower); worse is
at or below the pros' 10th percentile for the hitscan styles and 12-19% below their mean for the projectiles; better is above
the top decile for LG, near the 75th percentile for the rail and plasma, the median for rockets.

**What did not match, and why (the mechanism responsible):**
- *LG high and the rail low at the same setting.* LG's hit share moves with the read delay (75 ms: +25 points) and hardly with
  the slip term (0.02 -> 0.04: no measurable change) or the base error (0.45 -> 0.64: none); the rail moves with the eccentricity
  term, the base error and the delay. His LG excess is at close range (0-250 u: 53-54% against the pros' 44%), where neither
  term is large. Not fixed here; the next lever is the self-play setting (his opponent is himself) rather than a weapon cap.
- *The reversal dip is shallower than the pros'* (LG 84% of steady against their median 66%; rail similar): the delay (100 ms)
  and the hand chain should make a dip, and self-play opponents reverse in patterns his own network knows. To check against
  people's sessions before adding a mechanism (a longer read delay on a change of direction would be the one).
- *Projectiles barely respond to perception* (worse's plasma 88% of the mean): their lead comes from the velocity read and the
  splash forgives; worse needed the velocity read worsened too (300 ms, +-45%), better improved (150 ms, +-10%).
- *His first rocket after a sighting is slow* (0.40-0.50 s against the pros' median 0.28 s, p90-98) at every level: a habit of
  the network (he fires rockets once settled), not a limit.
- *The flinch*: see section 6; at the final values his post-damage ratio is inside the pros' spread for every style.

### 4.2 Per weapon style: pro targets, the old model, AIM2

**lightning (tracking)**. Mechanism: the read delay (100 ms; focus no longer cuts it) and the slip term: the error grows when his view does not follow the target, most right after a reversal; the base error x focus.

| measure | pros, pooled sample (968) | pros, tournament (all 5,702) | pros, archive (1,385) | old model, v0.5.1 save | old model, v0.5.0 end | AIM2 default, v0.5.1 save | AIM2 default, v0.4.2b end (80-game suite) | old level 4, v0.4.2b end (suite) | AIM2 worse (final) | AIM2 better (final) |
|---|---|---|---|---|---|---|---|---|---|---|
| hit share against the pros at his distances (100 = the pooled pros) | 100 (467363) | 96 (2844152) | 106 (679201) | 114 (23019) | 115 (24348) | 112 (9870) | 116 (50449) | 141 (62062) | 70 (11844) | 141 (9118) |
| all | 33.1 (467363) | 31.6 (2844152) | 35.3 (679201) | 42.4 (23019) | 42.6 (24348) | 41.5 (9870) | 42.3 (50449) | 50.7 (62062) | 27.5 (11844) | 51.7 (9118) |
| dist 0-250 | 43.7 (61617) | 42.7 (358258) | 46.7 (88962) | 58.8 (7704) | 59.0 (8650) | 53.4 (3639) | 54.1 (15578) | 65.1 (18093) | 35.8 (5900) | 64.1 (2823) |
| dist 250-500 | 36.9 (178788) | 35.0 (1055608) | 38.8 (271022) | 40.3 (10703) | 39.7 (10763) | 41.1 (4141) | 43.9 (23287) | 52.3 (28266) | 22.1 (4565) | 54.7 (4184) |
| dist 500-750 | 30.2 (191425) | 29.4 (1201467) | 32.1 (273162) | 24.0 (3707) | 24.7 (3913) | 26.1 (1664) | 27.7 (9339) | 38.4 (12335) | 11.0 (1104) | 33.4 (1752) |
| dist 750-1100 | 11.0 (34690) | 10.8 (225018) | 11.3 (44680) | 3.1 (812) | 4.5 (938) | 4.4 (408) | 4.9 (2020) | 6.6 (3040) | 2.7 (258) | 7.7 (313) |
| 0.1-0.2 s after a reversal, distance-matched, % of steady | 67.0 (63972) | 66.6 (386691) | 67.8 (92073) | 80.5 (1550) | 82.3 (1544) | 84.0 (710) | 84.9 (3537) | 83.4 (4160) | 78.2 (890) | 86.4 (574) |
| slip 50+ deg/s, distance-matched, % of slip under 25 | 89.5 (180015) | 89.9 (1055876) | 89.7 (266504) | 76.6 (14305) | 74.7 (15585) | 66.0 (5907) | 67.5 (29996) | 73.5 (34270) | 68.7 (8869) | 73.1 (4545) |
| after damage (any in 0.5 s), distance-matched, % of calm | 117.8 (215095) | 118.9 (1282441) | 116.5 (314243) | 102.4 (11352) | 102.6 (11912) | 125.8 (3945) | 148.2 (29409) | 102.6 (29101) | 181.8 (3912) | 122.6 (4283) |
| flick 0-5 deg: first-shot time med | 0.1 (3217) | 0.1 (19777) | 0.1 (4858) | 0.2 (47) | 0.2 (41) | 0.2 (21) | 0.2 (82) | 0.1 (135) | 0.4 (17) | 0.2 (16) |
| flick 0-5 deg: first-shot hit % | 34.2 (3217) | 34.5 (19777) | 35.4 (4858) | 34.0 (47) | 43.9 (41) | 33.3 (21) | 32.9 (82) | 39.3 (135) | 17.6 (17) | 50.0 (16) |
| flick 5-15 deg: first-shot time med | 0.2 (4420) | 0.2 (26943) | 0.2 (6489) | 0.2 (131) | 0.2 (173) | 0.3 (69) | 0.2 (372) | 0.2 (509) | 0.4 (62) | 0.2 (77) |
| flick 5-15 deg: first-shot hit % | 28.8 (4420) | 27.8 (26943) | 31.7 (6489) | 32.8 (131) | 31.2 (173) | 33.3 (69) | 26.6 (372) | 38.1 (509) | 12.9 (62) | 37.7 (77) |
| flick 15-30 deg: first-shot time med | 0.3 (2242) | 0.3 (13148) | 0.3 (3112) | 0.3 (164) | 0.3 (173) | 0.4 (56) | 0.3 (330) | 0.2 (437) | 0.5 (60) | 0.2 (76) |
| flick 15-30 deg: first-shot hit % | 28.9 (2242) | 27.7 (13148) | 30.6 (3112) | 29.3 (164) | 28.3 (173) | 33.9 (56) | 24.8 (330) | 33.0 (437) | 16.7 (60) | 25.0 (76) |
| flick 30-60 deg: first-shot time med | 0.4 (1464) | 0.4 (9134) | 0.4 (2049) | 0.4 (218) | 0.4 (249) | 0.4 (102) | 0.4 (475) | 0.3 (602) | 0.6 (91) | 0.3 (102) |
| flick 30-60 deg: first-shot hit % | 30.9 (1464) | 28.3 (9134) | 30.6 (2049) | 22.9 (218) | 26.5 (249) | 33.3 (102) | 23.8 (475) | 32.7 (602) | 24.2 (91) | 30.4 (102) |

**machine gun (tracking + spread)**. Mechanism: as the lightning gun (the same eyes); the spread is the game's.

| measure | pros, pooled sample (968) | pros, tournament (all 5,702) | pros, archive (1,385) | old model, v0.5.1 save | old model, v0.5.0 end | AIM2 default, v0.5.1 save | AIM2 default, v0.4.2b end (80-game suite) | old level 4, v0.4.2b end (suite) | AIM2 worse (final) | AIM2 better (final) |
|---|---|---|---|---|---|---|---|---|---|---|
| hit share against the pros at his distances (100 = the pooled pros) | 100 (32350) | 97 (223939) | 99 (33761) | 98 (1008) | 95 (1121) | 95 (293) | 96 (2983) | 112 (1942) | 52 (218) | 109 (508) |
| all | 32.3 (32350) | 32.0 (223939) | 31.9 (33761) | 39.6 (1008) | 37.8 (1121) | 37.5 (293) | 37.5 (2983) | 43.5 (1942) | 20.2 (218) | 42.3 (508) |
| dist 0-250 | 46.8 (3794) | 46.1 (28872) | 46.5 (3768) | 55.2 (404) | 57.1 (429) | 54.8 (115) | 51.2 (976) | 63.7 (611) | 34.2 (73) | 63.3 (147) |
| dist 250-500 | 39.3 (7375) | 38.9 (53690) | 40.0 (7178) | 37.7 (366) | 30.9 (395) | 29.3 (92) | 40.1 (1138) | 43.1 (775) | 19.4 (62) | 36.1 (191) |
| dist 500-750 | 33.7 (8718) | 31.8 (63083) | 32.9 (9529) | 17.5 (171) | 26.1 (188) | 28.6 (56) | 23.1 (549) | 29.0 (331) | 12.1 (58) | 34.8 (135) |
| dist 750-1100 | 24.7 (9045) | 24.1 (61670) | 24.6 (9922) | 7.8 (51) | 8.5 (94) | 16.7 (24) | 13.3 (249) | 14.3 (182) | 0.0 (21) | 18.2 (33) |
| 0.1-0.2 s after a reversal, distance-matched, % of steady | 74.6 (3084) | 71.0 (21771) | 70.6 (3307) | 93.9 (79) | 61.8 (75) | 84.6 (29) | 87.6 (279) | 92.7 (180) | 109.4 (27) | 124.3 (42) |
| slip 50+ deg/s, distance-matched, % of slip under 25 | 72.6 (8876) | 77.2 (64354) | 73.4 (8935) | 95.3 (636) | 78.3 (689) | - | 74.0 (1823) | 86.1 (1129) | - | 61.6 (162) |
| after damage (any in 0.5 s), distance-matched, % of calm | 120.2 (11275) | 119.2 (82545) | 124.1 (12358) | 105.9 (506) | 109.4 (557) | 128.1 (84) | 139.0 (1630) | 99.6 (1029) | 239.3 (47) | 92.9 (222) |

**rail (flicking)**. Mechanism: the eccentricity term (a far-off target is placed worse until the crosshair arrives) + the hand chain's settle (inertia, 4 Hz band) + the base error; the notice and surprise delays set the time.

| measure | pros, pooled sample (968) | pros, tournament (all 5,702) | pros, archive (1,385) | old model, v0.5.1 save | old model, v0.5.0 end | AIM2 default, v0.5.1 save | AIM2 default, v0.4.2b end (80-game suite) | old level 4, v0.4.2b end (suite) | AIM2 worse (final) | AIM2 better (final) |
|---|---|---|---|---|---|---|---|---|---|---|
| hit share against the pros at his distances (100 = the pooled pros) | 100 (22209) | 95 (127147) | 106 (35331) | 127 (713) | 115 (768) | 90 (495) | 93 (1074) | 125 (1241) | 48 (844) | 115 (371) |
| first shot after a sighting, angle-matched (100 = pros) | 100 (9497) | 97 (53803) | 104 (15732) | 132 (324) | 134 (325) | 103 (191) | 93 (488) | 148 (540) | 59 (241) | 111 (175) |
| all | 37.5 (22209) | 35.9 (127147) | 39.6 (35331) | 54.0 (713) | 49.0 (768) | 38.4 (495) | 39.3 (1074) | 52.5 (1241) | 21.0 (844) | 48.5 (371) |
| dist 0-250 | 49.1 (605) | 47.6 (4210) | 51.4 (803) | 64.6 (198) | 61.9 (223) | 45.8 (144) | 56.8 (292) | 64.0 (325) | 30.1 (346) | 72.0 (107) |
| dist 250-500 | 41.2 (3485) | 39.8 (20049) | 44.3 (5370) | 53.3 (306) | 47.8 (337) | 40.9 (208) | 40.0 (475) | 55.9 (487) | 16.1 (335) | 46.8 (124) |
| dist 500-750 | 38.4 (7586) | 36.9 (44767) | 40.6 (12481) | 46.3 (162) | 42.0 (138) | 27.8 (115) | 23.4 (222) | 49.5 (303) | 10.3 (126) | 34.3 (99) |
| dist 750-1100 | 35.4 (8189) | 33.7 (46836) | 37.0 (12821) | 45.2 (42) | 31.0 (58) | 28.0 (25) | 24.6 (57) | 25.3 (87) | 18.2 (33) | 28.9 (38) |
| 0.1-0.2 s after a reversal, distance-matched, % of steady | 54.2 (2467) | 51.7 (14418) | 52.4 (4027) | 87.2 (46) | 86.9 (52) | 125.7 (35) | 100.5 (70) | 68.0 (77) | 51.1 (74) | 139.8 (20) |
| slip 50+ deg/s, distance-matched, % of slip under 25 | 92.7 (8425) | 91.3 (51429) | 94.3 (14135) | 107.6 (307) | 90.9 (252) | 105.9 (191) | 84.3 (439) | 95.0 (524) | 106.2 (247) | - |
| after damage (any in 0.5 s), distance-matched, % of calm | 106.4 (4658) | 103.4 (26630) | 99.4 (7492) | 81.7 (253) | 82.3 (268) | 108.3 (157) | 136.7 (551) | 81.4 (317) | 121.7 (180) | 103.8 (111) |
| flick 0-5 deg: first-shot time med | 0.3 (3997) | 0.3 (22116) | 0.3 (7008) | 0.2 (36) | 0.2 (27) | 0.2 (17) | 0.3 (45) | 0.2 (54) | 0.4 (27) | 0.2 (20) |
| flick 0-5 deg: first-shot hit % | 53.1 (3997) | 50.5 (22116) | 55.6 (7008) | 75.0 (36) | 74.1 (27) | 70.6 (17) | 60.0 (45) | 70.4 (54) | 48.1 (27) | 60.0 (20) |
| flick 5-15 deg: first-shot time med | 0.3 (3680) | 0.3 (20115) | 0.3 (6040) | 0.3 (99) | 0.3 (100) | 0.3 (64) | 0.3 (145) | 0.2 (175) | 0.4 (86) | 0.2 (51) |
| flick 5-15 deg: first-shot hit % | 49.6 (3680) | 49.0 (20115) | 51.8 (6040) | 60.6 (99) | 66.0 (100) | 46.9 (64) | 45.5 (145) | 69.7 (175) | 27.9 (86) | 54.9 (51) |
| flick 15-30 deg: first-shot time med | 0.4 (1150) | 0.5 (6646) | 0.5 (1655) | 0.4 (70) | 0.4 (79) | 0.4 (52) | 0.4 (136) | 0.3 (121) | 0.5 (44) | 0.3 (37) |
| flick 15-30 deg: first-shot hit % | 46.5 (1150) | 44.9 (6646) | 49.8 (1655) | 61.4 (70) | 69.6 (79) | 42.3 (52) | 40.4 (136) | 74.4 (121) | 18.2 (44) | 62.2 (37) |
| flick 30-60 deg: first-shot time med | 0.6 (670) | 0.6 (4926) | 0.6 (1029) | 0.5 (119) | 0.5 (119) | 0.5 (58) | 0.6 (162) | 0.5 (190) | 0.6 (84) | 0.4 (67) |
| flick 30-60 deg: first-shot hit % | 45.7 (670) | 43.0 (4926) | 44.7 (1029) | 62.2 (119) | 55.5 (119) | 51.7 (58) | 42.6 (162) | 70.0 (190) | 27.4 (84) | 44.8 (67) |

**shotgun (close flick)**. Mechanism: as the rail at close range (eccentricity + hand); the pellets are the game's.

| measure | pros, pooled sample (968) | pros, tournament (all 5,702) | pros, archive (1,385) | old model, v0.5.1 save | old model, v0.5.0 end | AIM2 default, v0.5.1 save | AIM2 default, v0.4.2b end (80-game suite) | old level 4, v0.4.2b end (suite) | AIM2 worse (final) | AIM2 better (final) |
|---|---|---|---|---|---|---|---|---|---|---|
| hit share against the pros at his distances (100 = the pooled pros) | 100 (1401) | 102 (8559) | 99 (2249) | 61 (36) | 110 (12) | 132 (1) | 80 (15) | 79 (18) | 28 (10) | 0 (5) |
| first shot after a sighting, angle-matched (100 = pros) | 100 (491) | 101 (3181) | 100 (798) | 96 (7) | 112 (6) | - | 98 (7) | 112 (5) | 120 (1) | - |
| all | 76.8 (1411) | 78.1 (8596) | 76.3 (2262) | 39.0 (41) | 83.3 (12) | 100.0 (1) | 30.0 (30) | 39.3 (28) | 13.3 (15) | 0.0 (5) |
| dist 0-250 | 75.9 (386) | 77.3 (2481) | 75.4 (613) | 60.0 (5) | 100.0 (1) | 100.0 (1) | 50.0 (4) | 75.0 (4) | 0.0 (3) | - |
| dist 250-500 | 78.9 (658) | 81.8 (3862) | 79.8 (1045) | 88.9 (9) | 100.0 (5) | - | 66.7 (6) | 83.3 (6) | 100.0 (2) | - |
| dist 500-750 | 77.8 (284) | 76.2 (1732) | 74.7 (442) | 33.3 (9) | 75.0 (4) | - | 50.0 (2) | 28.6 (7) | - | - |
| dist 750-1100 | 65.8 (73) | 62.4 (484) | 64.4 (149) | 15.4 (13) | 50.0 (2) | - | 66.7 (3) | 100.0 (1) | 0.0 (5) | 0.0 (5) |
| 0.1-0.2 s after a reversal, distance-matched, % of steady | 92.4 (173) | 86.3 (921) | 91.6 (304) | - | - | - | - | - | - | - |
| slip 50+ deg/s, distance-matched, % of slip under 25 | 94.7 (724) | 94.5 (6376) | 92.2 (1140) | - | - | - | - | - | - | - |
| after damage (any in 0.5 s), distance-matched, % of calm | 109.9 (468) | 106.7 (2901) | 107.8 (715) | - | - | - | - | - | - | - |
| flick 0-5 deg: first-shot time med | 0.2 (57) | 0.3 (386) | 0.2 (105) | - | 0.2 (1) | - | - | - | - | - |
| flick 0-5 deg: first-shot hit % | 94.7 (57) | 92.0 (386) | 93.3 (105) | - | 100.0 (1) | - | - | - | - | - |
| flick 5-15 deg: first-shot time med | 0.3 (190) | 0.3 (1143) | 0.3 (310) | 0.6 (3) | 0.2 (2) | - | 0.3 (2) | 0.3 (2) | - | - |
| flick 5-15 deg: first-shot hit % | 92.6 (190) | 91.8 (1143) | 92.9 (310) | 66.7 (3) | 100.0 (2) | - | 100.0 (2) | 100.0 (2) | - | - |
| flick 15-30 deg: first-shot time med | 0.3 (148) | 0.3 (920) | 0.3 (230) | 0.5 (2) | 0.4 (1) | - | 0.3 (2) | 0.4 (2) | - | - |
| flick 15-30 deg: first-shot hit % | 89.2 (148) | 90.9 (920) | 89.1 (230) | 100.0 (2) | 100.0 (1) | - | 100.0 (2) | 100.0 (2) | - | - |
| flick 30-60 deg: first-shot time med | 0.4 (96) | 0.4 (732) | 0.4 (153) | 0.4 (2) | 0.8 (2) | - | 0.7 (3) | 0.3 (1) | 0.8 (1) | - |
| flick 30-60 deg: first-shot hit % | 83.3 (96) | 87.8 (732) | 85.0 (153) | 100.0 (2) | 100.0 (2) | - | 66.7 (3) | 100.0 (1) | 100.0 (1) | - |

**rockets (prediction)**. Mechanism: the velocity read (VEL_FIX: 200 ms old, +-20%) and the read delay feed the lead; the sight error only on the final angle (AIM2_SPLIT); splash forgives.

| measure | pros, pooled sample (968) | pros, tournament (all 5,702) | pros, archive (1,385) | old model, v0.5.1 save | old model, v0.5.0 end | AIM2 default, v0.5.1 save | AIM2 default, v0.4.2b end (80-game suite) | old level 4, v0.4.2b end (suite) | AIM2 worse (final) | AIM2 better (final) |
|---|---|---|---|---|---|---|---|---|---|---|
| hit share against the pros at his distances (100 = the pooled pros) | 100 (74563) | 100 (450031) | 102 (102961) | 98 (503) | 98 (608) | 97 (261) | 91 (1383) | 96 (1007) | 81 (296) | 103 (299) |
| all | 34.6 (74563) | 35.2 (450031) | 34.8 (102961) | 46.7 (503) | 49.0 (608) | 49.8 (261) | 42.0 (1383) | 45.7 (1007) | 42.6 (296) | 49.5 (299) |
| dist 0-250 | 72.8 (9979) | 72.5 (61568) | 74.1 (14018) | 68.1 (163) | 67.0 (224) | 68.1 (113) | 67.3 (428) | 64.8 (318) | 59.1 (137) | 69.6 (102) |
| dist 250-500 | 44.3 (25671) | 44.2 (157823) | 45.9 (34680) | 49.3 (215) | 49.8 (251) | 49.5 (95) | 42.1 (580) | 46.8 (462) | 42.7 (103) | 54.0 (126) |
| dist 500-750 | 23.6 (22277) | 23.6 (138171) | 24.2 (29469) | 16.9 (89) | 18.7 (107) | 12.1 (33) | 16.6 (247) | 24.3 (144) | 0.0 (38) | 14.3 (49) |
| dist 750-1100 | 13.0 (13024) | 13.4 (76565) | 11.8 (17932) | 7.4 (27) | 12.0 (25) | 14.3 (14) | 8.0 (100) | 4.8 (62) | 6.2 (16) | 9.5 (21) |
| 0.1-0.2 s after a reversal, distance-matched, % of steady | 100.1 (6221) | 100.2 (38035) | 103.0 (8371) | 101.5 (47) | 87.4 (45) | 102.3 (17) | 121.0 (118) | 108.8 (79) | 105.9 (18) | 85.9 (17) |
| slip 50+ deg/s, distance-matched, % of slip under 25 | 103.3 (41589) | 103.2 (248901) | 104.5 (56983) | 45.7 (46) | 75.6 (239) | - | 108.0 (587) | 109.4 (410) | - | - |
| after damage (any in 0.5 s), distance-matched, % of calm | 114.4 (14706) | 112.3 (90107) | 112.4 (19700) | 93.2 (216) | 110.2 (258) | 88.5 (106) | 96.5 (782) | 91.0 (406) | 108.9 (68) | 104.6 (130) |
| flick 0-5 deg: first-shot time med | 0.2 (2315) | 0.2 (14255) | 0.2 (3101) | 0.4 (4) | 0.4 (9) | 0.6 (4) | 0.3 (21) | 0.2 (19) | 0.4 (2) | 0.4 (4) |
| flick 0-5 deg: first-shot hit % | 37.4 (2315) | 36.2 (14255) | 40.5 (3101) | 25.0 (4) | 44.4 (9) | 50.0 (4) | 42.9 (21) | 42.1 (19) | 0.0 (2) | 75.0 (4) |
| flick 5-15 deg: first-shot time med | 0.2 (6168) | 0.2 (38057) | 0.2 (8227) | 0.3 (33) | 0.3 (36) | 0.3 (17) | 0.3 (105) | 0.3 (63) | 0.6 (18) | 0.3 (22) |
| flick 5-15 deg: first-shot hit % | 48.3 (6168) | 48.9 (38057) | 52.9 (8227) | 60.6 (33) | 44.4 (36) | 58.8 (17) | 50.5 (105) | 50.8 (63) | 27.8 (18) | 63.6 (22) |
| flick 15-30 deg: first-shot time med | 0.3 (4005) | 0.3 (24339) | 0.3 (5245) | 0.4 (38) | 0.4 (56) | 0.4 (20) | 0.4 (121) | 0.4 (80) | 0.7 (21) | 0.4 (23) |
| flick 15-30 deg: first-shot hit % | 53.4 (4005) | 52.4 (24339) | 56.3 (5245) | 55.3 (38) | 51.8 (56) | 45.0 (20) | 39.7 (121) | 38.8 (80) | 47.6 (21) | 56.5 (23) |
| flick 30-60 deg: first-shot time med | 0.4 (2988) | 0.4 (18780) | 0.4 (3653) | 0.5 (77) | 0.5 (88) | 0.5 (40) | 0.5 (194) | 0.5 (130) | 0.7 (34) | 0.4 (42) |
| flick 30-60 deg: first-shot hit % | 51.0 (2988) | 49.4 (18780) | 53.1 (3653) | 54.5 (77) | 61.4 (88) | 32.5 (40) | 45.9 (194) | 44.6 (130) | 35.3 (34) | 59.5 (42) |
| miss along med (moving) | -45.7 (56654) | -44.6 (342140) | -46.4 (78565) | -46.4 (422) | -36.7 (513) | -47.6 (220) | -41.2 (1167) | -45.1 (788) | -51.8 (244) | -34.2 (248) |
| miss |along| med | 83.9 (56654) | 80.7 (342140) | 86.6 (78565) | 55.6 (422) | 49.7 (513) | 53.3 (220) | 58.2 (1167) | 55.4 (788) | 59.1 (244) | 49.8 (248) |
| miss across med | 67.1 (56654) | 64.9 (342140) | 69.5 (78565) | 38.6 (422) | 37.1 (513) | 33.7 (220) | 40.8 (1167) | 38.3 (788) | 36.5 (244) | 35.7 (248) |
| direct % | 10.1 (74563) | 10.5 (450031) | 10.1 (102961) | 23.7 (489) | 20.6 (592) | 20.8 (259) | 18.6 (1356) | 21.7 (976) | 19.4 (288) | 23.4 (295) |

**plasma (prediction + tracking)**. Mechanism: both: the lead from the velocity read, then the slip term while he holds the stream on a moving target.

| measure | pros, pooled sample (968) | pros, tournament (all 5,702) | pros, archive (1,385) | old model, v0.5.1 save | old model, v0.5.0 end | AIM2 default, v0.5.1 save | AIM2 default, v0.4.2b end (80-game suite) | old level 4, v0.4.2b end (suite) | AIM2 worse (final) | AIM2 better (final) |
|---|---|---|---|---|---|---|---|---|---|---|
| hit share against the pros at his distances (100 = the pooled pros) | 100 (38741) | 101 (261456) | 104 (44452) | 134 (3959) | 125 (4951) | 112 (1531) | 119 (3901) | 141 (5532) | 88 (2551) | 129 (2128) |
| all | 12.5 (38741) | 13.0 (261456) | 12.0 (44452) | 24.0 (3959) | 21.8 (4951) | 20.2 (1531) | 21.4 (3901) | 25.6 (5532) | 17.4 (2551) | 23.0 (2128) |
| dist 0-250 | 28.4 (5259) | 28.5 (38598) | 29.8 (5562) | 38.7 (1221) | 40.1 (1517) | 33.0 (540) | 35.0 (1241) | 41.5 (1804) | 26.6 (1064) | 36.9 (680) |
| dist 250-500 | 15.9 (11770) | 15.7 (80435) | 16.4 (11321) | 22.0 (1825) | 18.9 (2007) | 17.2 (571) | 19.3 (1693) | 22.8 (2412) | 13.0 (1050) | 20.4 (945) |
| dist 500-750 | 9.4 (10139) | 9.0 (68829) | 9.6 (10867) | 11.0 (621) | 7.5 (970) | 9.1 (264) | 9.2 (695) | 10.8 (931) | 6.8 (281) | 13.4 (305) |
| dist 750-1100 | 5.1 (8450) | 6.0 (58461) | 5.6 (11507) | 2.6 (235) | 4.7 (404) | 6.3 (95) | 5.0 (199) | 4.2 (287) | 3.3 (90) | 3.4 (147) |
| 0.1-0.2 s after a reversal, distance-matched, % of steady | 91.2 (4072) | 89.1 (28195) | 89.3 (4360) | 85.9 (240) | 106.7 (289) | 49.0 (87) | 76.9 (268) | 90.2 (436) | 56.7 (167) | 56.3 (116) |
| slip 50+ deg/s, distance-matched, % of slip under 25 | 85.0 (13761) | 86.4 (95051) | 90.3 (14392) | 94.4 (2655) | 102.5 (3186) | 82.6 (961) | 77.4 (2518) | 101.6 (3448) | 87.3 (1839) | 82.7 (1291) |
| after damage (any in 0.5 s), distance-matched, % of calm | 111.4 (12664) | 108.3 (87551) | 107.7 (13538) | 80.9 (1924) | 98.1 (2284) | 97.2 (579) | 108.1 (2061) | 105.8 (2650) | 103.4 (811) | 97.6 (1041) |
| miss along med (moving) | -35.3 (28922) | -34.9 (195689) | -34.8 (33507) | -36.0 (3161) | -36.1 (3944) | -38.5 (1258) | -38.3 (3200) | -36.0 (4445) | -46.4 (2100) | -37.8 (1694) |
| miss |along| med | 55.2 (28922) | 52.5 (195689) | 57.6 (33507) | 41.7 (3161) | 44.1 (3944) | 45.1 (1258) | 46.3 (3200) | 41.4 (4445) | 53.4 (2100) | 43.2 (1694) |
| miss across med | 37.2 (28922) | 35.4 (195689) | 40.3 (33507) | 27.1 (3161) | 28.1 (3944) | 27.1 (1258) | 28.0 (3200) | 24.5 (4445) | 30.0 (2100) | 26.1 (1694) |
| direct % | 10.0 (38737) | 10.5 (261456) | 9.5 (44447) | 18.6 (3959) | 17.6 (4951) | 16.0 (1531) | 16.7 (3901) | 20.9 (5532) | 12.8 (2551) | 19.1 (2128) |

### 4.3 The 80-game suite (the owner's, 2026-10-27)

v0.4.2b's end with its OLD level-4 aim (`aim_settings(4)` as the code had it before branch aim2: sight error 0.48, no speed
term (level 4 had none), surprise 160 ms, flinch 0.2 / 4.8 / 0.5 with the kick, hand noise 0.08 / 0.04, its checkpoint's delays
100 / 160 ms, focus as before) in one seat, the same network under AIM2 default (the final values) in the other; 8 ten-minute
games a map on the ten maps, seats swapped half and half; the process runs v0.5.1's `.cmd` (v0.5.0's fixes, the input
switches); each side's aim its own (`env.seat_aim`, `tools/duel_eval.py --aim-he / --aim-opp`).

**All maps: 80 games.** Old level 4 vs AIM2 default: W-L-D 70-10-0 (old's games), frag share old 0.692, mean score 17.1 - 7.2

| weapon | old: hit % | old: % of pros | old: shots | AIM2: hit % | AIM2: % of pros | AIM2: shots |
|---|---|---|---|---|---|---|
| lg | 50.7 | 141 | 62062 | 42.3 | 116 | 50449 |
| rg | 52.5 | 125 | 1241 | 39.3 | 93 | 1074 |
| rl | 45.7 | 96 | 1007 | 42.0 | 91 | 1383 |
| pg | 25.6 | 141 | 5532 | 21.4 | 119 | 3901 |
| mg | 43.5 | 112 | 1942 | 37.5 | 96 | 2983 |
| sg | 39.3 | 65 | 28 | 30.0 | 57 | 30 |

| map | games | old W-L-D | old frag share |
|---|---|---|---|
| aerowalk | 8 | 8-0-0 | 0.667 |
| battleforged | 8 | 7-1-0 | 0.684 |
| bloodrun | 8 | 8-0-0 | 0.706 |
| campgrounds | 8 | 6-2-0 | 0.634 |
| cure | 8 | 5-3-0 | 0.630 |
| furiousheights | 8 | 7-1-0 | 0.703 |
| hektik | 8 | 8-0-0 | 0.813 |
| lostworld | 8 | 6-2-0 | 0.643 |
| sinister | 8 | 8-0-0 | 0.709 |
| toxicity | 8 | 7-1-0 | 0.662 |

Level 4 is far above the pros (LG and plasma +41%, the rail +25%) and is this network's trained condition; AIM2 default is near
the pros' median and untrained for it: the 70-10 is the immediate cost of the new aim for a network that never trained under
it, not what a network trained under AIM2 would do.

## 5. The hand chain (item 5): does it double-filter?

`tools/aim2_hand_chain.py` (pure arithmetic of `step()`'s lines, no noise):

| Command | Today (inertia 0.75 / 0.2 + 4 Hz band) | No inertia (`AIM2_SMOOTH_K=0`, band only) | Inertia, no band | Half inertia (K = 0.5) |
|---|---|---|---|---|
| a held turn rate (2 / 8 / 15 / 30 deg a frame): frames to 90% of it | 10 / 9 / 9 / 9 | 4 / 3 / 3 / 2 | 9 / 9 / 9 / 9 | |
| a 10 deg flick, the fastest plan: 90% / settled within 1 deg / overshoot | 100 / 100 ms / 0 | 50 / 50 ms / 0.7 deg | 50 / 50 ms / 1.0 deg | 50 / 50 ms / 0 |
| a 40 deg flick (settled within 2 deg) | 75 / 125 ms / 4.2 deg | 50 / 50 ms / 1.9 deg | 75 / 100 ms / 2.0 deg | 75 / 75 ms / 1.0 deg |
| an 80 deg flick (within 4 deg) | 100 / 125 ms / 1.3 deg | 100 / 100 ms / 0 | 100 / 100 ms / 0 | 100 / 100 ms / 0.3 deg |

(The fastest plan: every "a command for k frames, then another for k2 frames, then nothing" from his discrete turn commands is
tried; the flick cap is 30 deg a frame. With the inertia a plan has to brake: the fastest 40 deg plan is 60 deg/frame x2 then
-30 x3.)

- **Was `HAND_BAND` fitted with `MOUSE_SMOOTH` upstream? Yes.** Commit f3e5fd4 (2026-10-20, v0.3.8): "the view's velocity (hb)
  follows the hand's (mv, after its smoothing and the flick cap)"; sized offline on save 220's recorded commands while firing
  lightning so that the view's yaw acceleration (4,600 -> 2,613 deg/s2), reversals (8.3 -> 4.8 a second) and power above
  4 Hz (0.43 -> 0.27) matched the pros' (2,455, 4.6, 0.29). So the two filters are in series by design: the band was sized on
  top of the inertia, and the pair, not the band alone, is what matched the pros' spectrum.
- **It does slow him.** A held turn command reaches 90% of its rate in 9-10 frames (225-250 ms) through the chain, 2-4 frames
  with the band alone; the inertia (0.75 a frame) is almost all of it. For a flick his best command plan (a burst and a brake)
  settles a 10 deg flick in 100 ms (50 without the inertia), 40 deg in 125 ms (50), 80 deg in 125 ms (100). The pros' first
  rail shot after a sighting comes 0.3 s (0-15 deg) to 0.6 s (30-60 deg) after it: the chain is not what limits his flick
  time; it limits how quickly he can change a tracking rate (a reversal), which is where the pros' LG and rail dip.
- **Proposal (not in the table; needs retraining):** `AIM2_SMOOTH_K=0` with the band refitted (`HB_FC` lower, e.g. 2.5-3 Hz) on
  a network's own commands so that the pros' view spectrum is matched by one filter, not two. Changing it changes his hands:
  a network trained with the inertia over-steers without it. Leave `AIM2_SMOOTH_K=1` for the next run; measure the spectrum
  with the new perception first (his tracking commands will change when the flat speed error goes).

## 6. The flinch (item 4)

- **The code (verified, `step()` and `note_hit()`):** on a hit, `add = min(FLINCH_MAX, FLINCH_PER_DMG x dmg)`; the sustained
  `flinch += add` (capped at `FLINCH_MAX`, fading over `FLINCH_TAU`, added to the error's sigma), and the error itself jumps
  by `add x N(0,1)` per axis. **The reviewer's "double application" is half right**: the stationary variance of the AR(1) is
  sigma^2, so the kick does not double the variance, it only makes it arrive at once instead of over the error's 0.15 s
  memory (and repeated lightning hits add a little: about +1.8 deg rms under steady LG fire at 20 hits/s with 1.5 deg each).
  `AIM2_FLINCH=1` keeps the sustained part only.
- **The values were environment-only**: `FLINCH_*` were read through `_aim()` but were neither PLAY_VARS nor live, so a server
  played the aim level's values whatever a run set. Now both.
- **The pros show no dip** (section 3). The trigger on the server is fixed already (`play-v05` 31d2825: only the opponent's
  hits, as the simulator).

**The calibration** (the hit share in the 0.5 s after taking damage, distance-matched, % of his calm share; the same
confounds on both sides, so compared like for like):

| | Pros (tournament / archive) | Today (kick + 0.25 / 6 / 0.5) | AIM2, sustained only, 0.25 / 6 / 0.5 | AIM2, 0.05 / 1.5 / 0.3 (`sw_g1`) |
|---|---|---|---|---|
| rail, any damage / 30+ | 106 / 102 (99 / 95) | 82 / 71 | 87 / 78 | 108 / 107 |
| lightning | 118 / 113 (117 / 112) | 102 / 110 | 121 / 131 | 126 / 140 |
| plasma | 111 / 108 (108 / 102) | 81 / 81 | 106 / 108 | 97 / 97 |
| rockets | 114 / 107 (112 / 104) | 93 / 96 | 85 / 86 | 88 / 84 |

Today's flinch costs his rail a fifth of its hits after a hit (the pros lose nothing). **Fitted: `AIM2_FLINCH=1`,
`FLINCH_PER_DMG 0.05`, `FLINCH_MAX 1.5`, `FLINCH_TAU 0.3`** (a rail hit: 1.5 deg fading over 0.3 s; steady LG fire: about
1.5 deg). The rockets stay below the pros at every setting: his own splash counts as "damage taken" (he fires rockets close),
not the flinch. Sample: a few hundred shots after damage a weapon in the simulator; noisy (+-10).

## 7. The identity proofs

`tools/aim2_ident.py`: a fixed-seed replay of v0.5.1's simulator (the run's `.cmd` settings and `live.json`, the run's 100 /
200 ms delays) with random actions for every output, 12 matches x 2 players, 2,000 frames on Blood Run and Aerowalk, each side
in its own process, compared to the bit (every input, every pay, round ends, kills, every counter, the final view):

| Check | Result |
|---|---|
| `duel_env_ffa` (the run's module): v0.5.1's code against `aim2` with every switch off | IDENTICAL (both maps; 1,743 / 1,471 player-frames with the enemy acquired, 12,115 / 15,289 zoomed, 463 / 257 damage) |
| `duel_env`: the same | IDENTICAL |
| `duel_env_ffa`: `aim2` off against `aim2` with every switch ON at the blend's start (`AIM2=1 AIM2_W=0 AIM2_SPLIT=1 AIM2_SPLIT_W=0 AIM2_FOCUS=1 AIM2_FOCUS_GAIN=2 AIM2_FOCUS_SIG=1 AIM2_SMOOTH_K=1`) | IDENTICAL: a run can start with the switches on and open them by the live numbers |
| sanity: off against `AIM2=1 AIM2_SPLIT=1 AIM2_FOCUS=1 AIM2_FLINCH=1` | DIFFERS (inputs from frame 606, pay, view, kills), as it must |

The second commit on the branch (c6c4af3) changes the code's DEFAULTS only (item 7: `REACT_FRAMES` 4, the trainer's
`--react-ms` 100, `test_suite`'s fallback 100, `PERCEPT_SPEED` 0.075 x the level's factor, `PERCEPT_SPEED_MAX` 1.5, the rail
cap 0.001): a tool run without the run's environment now plays as `!aim default` does. Under the run's own environment (which
sets every one of them) nothing changes.
Re-checked after that commit: `duel_env_ffa`, v0.5.1's code against `aim2` (c6c4af3 and later) with every switch off, both
maps: IDENTICAL.

## 8. The server (play build `play-aim2`)

- `plugins/duelbot.py`: the plugin never calls `step()`; everything AIM2 needs is kept in `observe()` (`a2_hist`, the focus,
  the flinch's decay), which it calls every frame. Added: `env.aim2_clear()` where it clears `opp_hist` (a new life),
  `AIM2_SMOOTH_K` in `drive()` (as in `step()`), and `DUEL_AIM2DUMP=1` (a row a frame of what the new terms read and what they
  are made of). The flinch's trigger was already the opponent's hits only (31d2825).
- **Checked on a private sparring server** (container `qlpaim2`, image `qlbot:playaim2`, Bobby on `!aim default` against the
  game's bot on Blood Run, 92 s, 3,200 frames, 600 with the enemy acquired, flinch up to 3.8 deg): `tools/aim2_srvcheck.py`
  worked the slip, eccentricity and error out again from the same frames' raw values by the simulator's rule: **3,104 frames
  compared, the slip within 0.0008 deg/s (float32), the eccentricity and the error exact; no frame off.** The container is
  stopped (not removed).

## 9. The `!aim` table under AIM2 (FINAL, 2026-10-27)

Written by `tools/aim2_levels.py` (its `TABLE`); the play build's files are `data/duellive_playaim2/policy_*.npz` (v0.4.2b's
end). Where each level lands among the pros: section 4.1.

| Setting | worse | **default** | better | max |
|---|---|---|---|---|
| Tracking delay `react_ms` | 150 | **100** | 100 | 25 |
| Notice delay `acquire_ms` | 300 | **200** | 150 | 25 |
| `SURPRISE_MS` | 300 | **200** | 150 | 0 |
| Sight error `PERCEPT_SIGMA` (deg; `PERCEPT_TAU` 0.15 s) | 1.0 | **0.6** | 0.35 | 0 |
| Focus: base error x `AIM2_FOCUS_SIG` / delay cut `AIM2_FOCUS_GAIN` (frames) | 0.85 / 0 | **0.75 / 0** | 0.7 / 1 | - |
| Slip: `AIM2_C_SLIP` (deg per deg/s) / `AIM2_S0` (deg/s) / `AIM2_CAP_SLIP` (deg) | 0.07 / 0 / 4 | **0.035 / 10 / 2.5** | 0.02 / 15 / 1.5 | 0 |
| Eccentricity: `AIM2_C_ECC` (deg per deg) / `AIM2_E0` (deg) / `AIM2_CAP_ECC` (deg) | 0.035 / 2 / 2 | **0.02 / 2 / 1** | 0.005 / 3 / 0.3 | 0 |
| Flinch `FLINCH_PER_DMG` / `_MAX` / `_TAU` (sustained only) | 0.15 / 4 / 0.4 | **0.05 / 1.5 / 0.3** | 0.02 / 0.75 / 0.25 | 0 |
| Hand noise `MOTOR_NOISE` / `MOTOR_BASE` | 0.15 / 0.075 | **0.10 / 0.05** | 0.075 / 0.0375 | 0.10 / 0.05 (as trained) |
| Enemy velocity read `VEL_DELAY_MS` / `VEL_WEBER` / `VEL_MIN` | 300 / 0.45 / 30 | **200 / 0.2 / 30** | 150 / 0.1 / 30 | 25 / 0 / 0 |
| Distance read `RANGE_WEBER` | 0.25 | **0.15** | 0.15 | 0 |
| Projectiles `PROJ_NOTICE_MS` / `PROJ_READ_MS` | 100 / 100 | **100 / 100** | 100 / 100 | 25 / 25 |
| Enemy facing `SM_FACE_DEG` | 15 | **15** | 15 | 0 |
| The old speed term `PERCEPT_SPEED` (and its caps) | 0 | **0** | 0 | 0 |
| Switches `AIM2`, `AIM2_SPLIT`, `AIM2_FOCUS`, `AIM2_FLINCH`; `AIM2_W`, `AIM2_SPLIT_W` | 1; 1, 1 | **1; 1, 1** | 1; 1, 1 | 1; 1, 1 |
| `AIM_LEVEL` | 3 | **3** | 3 | 40 |
| Everything else (inertia, flick cap, 4 Hz band, pad, fingers, fire hold, reload jitter, field of view, hearing) | as trained | as trained | as trained | as trained |

Beside today's table (AIM_LIMITS 1.1): the delays are today's at worse and default; better keeps 100 ms and gets back one frame
of focus (75 ms for the first 2 s of a sighting) instead of today's 75 ms throughout (75 ms throughout put his LG at 144% of the
pros' mean); the sight error 1.0 / 0.6 / 0.3 -> 1.0 / 0.6 / 0.35; the old speed term (0.075 deg per deg/s, caps 1.5 / rail 0.001
at default) is gone, replaced by the slip and eccentricity rows; the flinch was 0.25 / 6 / 0.5 with a kick at every level; the
velocity read now differs by level (the projectiles' lever); max keeps the hand as trained (today's `AIM_LEVEL` 40 took the
hand noise to ~0 as well; changed on `play-v05` too, section 12).

## 10. How each level should feel against the current limits

Against the current limits (AIM_LIMITS 1.1), situation by situation. The network in the play build is v0.4.2b's end, trained
under the old limits: it plays the new ones untrained, so it shows the immediate feel, not the adapted one.

| Situation | Today (default) | AIM2 default | What you should notice |
|---|---|---|---|
| **LG on a smooth, steady strafe** | +1.5 deg error whenever you move (the cap binds from 20 deg/s), however well he follows you: about 2.1 deg per axis | if he is following you, the slip is small: 0.6 deg (0.45 in his first 2 s of focus) | steadier, more dangerous LG against a predictable strafe; the "always 2 degrees off" wobble is gone |
| **LG / MG at your strafe reversal** | the same 2.1 deg; his read is only 50 ms late in the first 2 s (focus) | his view keeps going for his 100 ms delay while you reverse: the slip jumps to about twice your angular speed (e.g. 70 deg/s at 35 deg/s strafes): +2.1 deg (0.035 x (70 - 10)) for ~0.15-0.25 s | reversals (A-D timing) shake him off, as they shake a pro (pros keep 64-68% of their LG hits 0.1-0.2 s after a reversal); jittery, unpredictable strafes beat him more than wide steady ones |
| **His own strafing while he fires** | his own movement turns the world bearing: counted as target speed | only what his eyes see slip: if he turns with you, no cost | he can strafe and track at once; a careless strafe (view not following) costs him |
| **Pre-aimed rail (you appear on his crosshair)** | 0.6 deg, no speed term (the rail cap 0.001), delay 50 ms with focus | 0.45-0.6 deg, no eccentricity term within 2 deg; delay 100 ms | about as deadly as now; a little slower to the click (no 50 ms focus delay) |
| **Wide rail flick (you appear 30-60 deg off)** | the same 0.6 deg however far he flicks | +0.02 deg per degree off as of his delay (cap 1 deg): his first read of your place is off by up to 1 deg more, shrinking as the crosshair arrives (the error's memory is 0.15 s) | snap-and-click from far off misses more; a flick that takes 100-200 ms to settle still hits (pros: 43-45% first-shot hits at 30-60 deg, 0.6 s); today's rail (62% at 30-60 deg in self-play) was far above the pros |
| **Rockets / plasma (lead)** | the lead solved from a place carrying the full sight error + the flat 1.5 deg speed term; plus VEL_FIX's 200 ms, +-20% velocity | the meeting point from a place without the sight error, the error only on the final angle; the speed term gone; VEL_FIX as before | about the same rockets (the splash forgives), somewhat better plasma lead on steady movers; a change of direction inside 200 ms still fools his lead (the velocity read) |
| **After being hit** | an instant kick of up to 6 deg (a rail hit or a rocket), +1.5 deg for each LG cell, fading over 0.5 s (about 7 deg under steady LG fire) | no kick; the sustained part only, much smaller (0.05/dmg, max 1.5, 0.3 s; section 6) | hitting him first no longer wins a trade by itself: he keeps shooting back about as well (the pros show no dip at all) |
| **Zoomed (rail at range)** | x0.4 on the base error only (flinch and speed term unscaled) | x0.4 on everything | his zoomed rail on a moving target is clearly sharper than today |
| **Long fights** | focus: 50 ms delay for 2 s, then 125 ms | delay 100 ms throughout (125 after 2 s); focus makes him steadier (error x0.75), not faster | his first 2 s are no longer superhumanly quick; burst accuracy, not burst reaction |

**worse** (the pros' 10th percentile or below: LG 70% of their mean, the rail 48%, rockets 81%, plasma 88%): sight error 1.0,
slip 0.07 from the first deg/s (cap 4), eccentricity 0.035 (cap 2), delays 150 / 300 ms, flinch 0.15 / 4 / 0.4, hand noise
0.15, and a poor read of your velocity (300 ms old, +-45%) and distance (+-25%). Feel: a decent player, not a pro: loses you
at every reversal and on any fast crossing, slow and loose on wide flicks (first rail after a sighting at 0.5 s, 28% hits),
clearly put off by being hit, rockets and plasma led to where you were going a third of a second ago.

**better** (around the pros' top decile: LG above it at 141%, the rail at their 75th percentile, 115%; plasma 129%, rockets
103%): sight error 0.35, slip 0.02 from 15 deg/s (cap 1.5), eccentricity 0.005 from 3 deg (cap 0.3), delays 100 / 150 with one
frame of focus (75 ms for the first 2 s of a sighting), flinch 0.02 / 0.75 / 0.25, hand noise 0.075, a sharp velocity read
(150 ms, +-10%). Feel: the first exchange of a fight is very sharp (the focus frame), reversals still cost him for a moment,
wide flicks land (first rail 0.32 s, 53% hits: the pros' median time), his LG is very hard to strafe out of.

**max**: every perception and reaction limit the server can switch off is off: no sight error, no slip or eccentricity term,
no flinch, delays one frame (25 ms), the enemy's velocity and distance exact and one frame old, projectiles noticed at once.
The hand stays as trained (inertia, 4 Hz band, hand noise 0.10 / 0.05, flick cap, pad, fingers, fire hold, reload jitter),
and so do the field of view, line of sight and hearing. Feel: what his hands can do with perfect eyes: tracking limited only
by how fast his hand changes direction (the inertia and band), flicks by the hand chain (~100-125 ms to settle), and still
human on the fingers. Today's `max` took the hand noise to ~0 as well (AIM_LEVEL 40 scales it); under AIM2 and on `play-v05`
the hand noise stays as trained.

## 11. A run with it (from v0.5.1's end)

One new thing (the aim model) per the owner's rule of 2026-10-24: start directly from v0.5.1's end (its optimizer kept), the
switches ON from the first update at the blend's start (proved identical to today, section 7), then opened slowly by the live
numbers, tied to the checks.

| Step | Live settings (`live.json`) | Opens over | Check before the next step |
|---|---|---|---|
| start | `.cmd`: `AIM2=1 AIM2_SPLIT=1 AIM2_FOCUS=1 AIM2_FLINCH=1`; live `AIM2_W=0 AIM2_SPLIT_W=0 AIM2_FOCUS_GAIN=2 AIM2_FOCUS_SIG=1` (= today exactly), the default's other numbers set | | none (identical) |
| 1 the world picture | `AIM2_SPLIT_W` 0 -> 1 | 10-20 updates | the control, the brain's place error (his belief steadier, not worse) |
| 2 focus | `AIM2_FOCUS_GAIN` 2 -> 1 -> 0 (frames), `AIM2_FOCUS_SIG` 1 -> 0.75 | 20 updates | the control; first-shot times after a sighting |
| 3 the error model | `AIM2_W` 0 -> 1 in steps of 0.1-0.2 (the old speed term fades, slip + eccentricity rise; the zoom's reach on all terms with it) | 30-60 updates | the control at every step (hold under 50%, back under 45% or two checks under 50%); hit rates by weapon against the pros' table (`tools/aim2_measure.py vs`) |
| 4 the flinch | `FLINCH_PER_DMG` / `_MAX` / `_TAU` from 0.25 / 6 / 0.5 to the default's | 10 updates | the post-damage ratio against the pros' |

Equilibrium (the owner's standing rule: every change states the self-play equilibrium it leads to): under the old model a
target's speed cost the shooter a flat error whatever he did, so moving fast paid by itself and following well paid nothing
extra. Under AIM2 the shooter's error depends on how well his view follows the target, so tracking pays, and the dodger's
best answer is the change the shooter cannot follow within his delay: reversals and unpredictable timing, as people and pros
dodge. In self-play this should push both sides toward tighter tracking and more varied strafing; the rail moves from "free"
(no speed term) to "pre-aim pays, wide snap-flicks cost", which favours holding angles (B-273, the owner's "rail via
strategy"). The fight is decided more by position and reaction than by a flat penalty, which is what wins games against people.
The behaviour on the way: while `AIM2_W` opens, his LG on smooth strafes gets better before he learns to track reversals (his
LG share may rise for a while); his wide rail flicks get worse at once (fewer far rail frags in the first hours).

What to watch: hit rates by weapon and distance against the pros (`vs`: 100 = the tournament pros), the reversal dip
(should approach 64-68% for LG), the rail's first shot by angle, frags by weapon, and the control.

## 12. The play builds

**`play-aim2` (the owner's feel test of AIM2).** Branch `play-aim2` from `play-v05`'s head 31d2825 (so with eb58acb's win
value in the mind view and the flinch from the opponent's damage only), worktree `ql-bot-playaim2`, image `qlbot:playaim2`
(`docker build -f Dockerfile.reuse --build-arg QL_FROM=qlbot:play05 -t qlbot:playaim2 .`). Data folder
`data/duellive_playaim2`: v0.4.2b's end (`duel_gru_v0_4_2/keep/policy_end_v042.pt`, no win-value head: the mind view shows
none) exported by `sim/export_duel.py --env duel_env_ffa --legs move_v17_look --version "v0.4.2" --round-secs 600`, then
`tools/aim2_levels.py` writes `policy_worse/default/better/max.npz` and `policy.npz` = default; `!aim worse|default|better|max`
switches between them as on `play-v05`. To start it (port 27976, unlisted, the mind log on), from `ql-bot-playaim2` in Git Bash:

    NAME=qlplayaim2 DATA=data/duellive_playaim2 IMAGE=qlbot:playaim2 PORT=27976 bash tools/duel_server.sh - bloodrun duel_env_ffa

(`tools/duel_server.sh` removes a container of the same name first; `qlplayaim2` is a new name, the test container `qlpaim2`
is kept stopped.) The mind viewer: `python tools/mind_view.py --data data/duellive_playaim2 --port 8765`.

**`play-v05` `!aim max` (the current, old model).** `data/duellive_play05/policy_max.npz` rewritten (the old one kept as
`policy_max_level40.npz`; scratchpad `play05/aim05_max.py`): every perception and reaction limit the server can set is off
(`AIM_LEVEL` 40, delays 25 / 25 ms, `SURPRISE_MS` 0, `PERCEPT_SPEED` 0, `FLINCH_PER_DMG` 0, `VEL_DELAY_MS` 25 with
`VEL_WEBER` 0 and `VEL_MIN` 0, `RANGE_WEBER` 0, `PROJ_NOTICE_MS` / `PROJ_READ_MS` 25, `SM_FACE_DEG` 0; the switches stay on so
the inputs keep their layout) and the hand noise as trained (0.10 / 0.05; level 40 had taken it to ~0). Worse, default and
better are unchanged. A running `play-v05` server picks it up at the next `!aim max`. Focus cannot be switched off from the
server (a constant); with a 25 ms delay it changes nothing (the delay is never under one frame).

## 13. The run command for v0.6.0 (from v0.4.2b's end, v0.5.0's fixes + AIM2 default, branch `aim2`)

The trainer of branch `aim2` (a40097e and later) ran v0.5.1's command with this block on v0.4.2b's end (a scratch run
`aim2_dry`, 4 workers, 24 matches): 11 updates, kl 0.04, a clean exit; the live names below are accepted by its `live.json`.
In the `.cmd` (replace the old aim lines: `set AIM_LEVEL=3` stays, `set PERCEPT_SPEED_MAX=1.5` goes, and `live.json` must not set
`PERCEPT_SPEED`, `PERCEPT_SPEED_MAX_RG` or `_LG`):

    rem ---- AIM2 default (docs/v0.5.2/AIM_MODEL.md section 9)
    set AIM_LEVEL=3
    set PERCEPT_SPEED=0
    set AIM2=1
    set AIM2_SPLIT=1
    set AIM2_FOCUS=1
    set AIM2_FLINCH=1
    set PERCEPT_SIGMA=0.6
    set PERCEPT_TAU=0.15
    set SURPRISE_MS=200
    set MOTOR_NOISE=0.10
    set MOTOR_BASE=0.05
    set AIM2_W=1
    set AIM2_SPLIT_W=1
    set AIM2_FOCUS_GAIN=0
    set AIM2_FOCUS_SIG=0.75
    set AIM2_C_SLIP=0.035
    set AIM2_S0=10
    set AIM2_CAP_SLIP=2.5
    set AIM2_C_ECC=0.02
    set AIM2_E0=2
    set AIM2_CAP_ECC=1
    set FLINCH_PER_DMG=0.05
    set FLINCH_MAX=1.5
    set FLINCH_TAU=0.3

and the trainer flags `--react-ms 100 --acquire-ms 200` (v0.4.2b was trained at 100 / 160 and `AIM_LEVEL` 4). The velocity,
distance, projectile and facing reads stay v0.5.1's (`VEL_FIX=1 VEL_DELAY_MS=200 VEL_WEBER=0.2 VEL_TAU=0.3 VEL_MIN=30`,
`RANGE_FIX=1 RANGE_WEBER=0.15 RANGE_TAU=0.5`, `PROJ_FIX=1` 100 / 100, `SENSE_MINOR=1`), as do `HAND_BAND=1 HB_FC=4.0 HB_BETA=0.5`
and `ZOOM_PERCEPT=1`. To open the new aim slowly instead (section 11), start with the same block and `live.json`
`{"AIM2_W": 0, "AIM2_SPLIT_W": 0, "AIM2_FOCUS_GAIN": 2, "AIM2_FOCUS_SIG": 1, "FLINCH_PER_DMG": 0.2, "FLINCH_MAX": 4.8,
"FLINCH_TAU": 0.5}` plus `PERCEPT_SIGMA 0.48` in the `.cmd` (level 4, v0.4.2b's own; with `AIM2_FLINCH=0` for the kick), which
is v0.4.2b's training aim exactly (proved for the blend's start, section 7), and move the live numbers to the block's;
`PERCEPT_SIGMA` and `AIM2_FLINCH` are not live (change them at a safe restart).
A checkpoint carries every one of these (PLAY_VARS) and `sim/export_duel.py` writes them into `policy.npz`; the plugins set
them before loading the simulator (`play-aim2`'s plugin keeps the new state, section 8).

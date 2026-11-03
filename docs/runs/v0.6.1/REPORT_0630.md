# 06:30 report, Thu 10-29: v0.6.1 overnight

**v0.6.1** (`duel_gru_v0_6_1`): pay by win chance only, the chance from the frozen judge (`judge_v060_wpn.npz`), from v0.6.0's
end. Started 20:05, now at update 157. No stall, no crash, no restart. The fade finished at 05:55 (step 12): since update ~153 he
is paid by his chance of winning only. Nothing was changed overnight.

## In short

- **The fade went through without a dip.** Against v0.6.0's end he held 55.5% over the seven checks on the win pay (622-498),
  the same as before it (55.3%, 177-143). The last three, at `WIN_W` 0.9 to 1: 60.0%, 58.1%, 52.5%.
- **He plays a slower game.** Frags a match-minute 1.65 → 1.56 (v0.6.0's end: 1.75); a whole game 15 frags against v0.6.0's 18.
  The last panel (update 150) flags roaming: 20 map cells a minute against 27.
- **The pay's size halved** (8.3 → 4.2 a player-minute: the other pays faded and nothing replaced them), so the entropy bonus
  now weighs twice as much. Entropy rose 1.80 → 1.92 in the last 10 updates. The one thing to watch today.
- **Win chance only has had 4 updates.** The run's real test is today's checks from update 160 on.

## Run

| | |
|---|---|
| Updates | 1 → 157 in 598 min, one every 4.0 min (2.0 to 4.3); 16,950 steps a second (11,650 at update 1) |
| Stalls, crashes | none: no gap over 4.3 min, trainer, watcher, ramp and self-play logger all up all night |
| KL, clip | 0.031, 0.33 throughout (0 during the critic's warm-up, updates 31-43, as designed) |
| Settings check (`--ck` on the run's save) | one difference, `NO_SWITCH=1` in the checkpoint, not in the command. **It is the checker's gap, not the run's**: the trainer writes `NO_SWITCH=1` into every save from `--no-switch 1` (in the command), and v0.6.0's own saves show the same difference against v0.6.0's command. The numbers are used |

## Ramp

| Time | Step | `WIN_W` | `FADE_V` |
|---|---|---|---|
| 22:00 | `WIN_GAIN` = **0.33** (combat 4.49 / the win part 13.7 a player-minute at a gain of 1, updates 21-30) | | |
| 22:01 | 1 + critic warm-up (over at update 43, 22:46) | 0.1 | 0 |
| 23:23, 00:03, 00:42 | 2, 3, 4 | 0.2 → 0.4 | 0 |
| 01:20, 01:58, 02:37, 03:17, 03:56 | 5 → 9 | 0.5 → 0.9 | 0.125 → 0.625 |
| 04:36 | 10 | 1.0 | 0.75 |
| 05:15, 05:55 | 11, **12: done** | 1.0 | 0.875, **1.0** |

A step every 37 to 40 min, on the clock, whatever the checks said (your word).

## Checks (160 games, ten maps, both seats at `!aim default`; one check of 160 moves ±8 points by chance)

**Against v0.6.0's end** (games won-lost; no draws, so the win rate is of decided games):

| Update | 10 | 30 | 50 | 70 | 90 | 100 | 120 | 130 | 140 |
|---|---|---|---|---|---|---|---|---|---|
| `WIN_W` at the save | 0 | 0 | 0.1 | 0.3 | 0.5 | 0.6 | 0.8 | 0.9 | 1.0 |
| Won-lost | 95-65 | 82-78 | 92-68 | 79-81 | 95-65 | 83-77 | 96-64 | 93-67 | 84-76 |
| Win rate | 59.4% | 51.2% | 57.5% | 49.4% | 59.4% | 51.9% | **60.0%** | 58.1% | 52.5% |
| Frag share | 51.8% | 49.4% | 53.4% | 50.1% | 53.3% | 52.8% | 55.7% | 55.3% | 52.0% |

Updates 40, 60, 80, 110 and 150 were checked against v0.4.2b's end instead, or skipped while a check was still playing.

**Per map, on the win pay (updates 50-140):** Aerowalk 69-43, Toxicity 68-44, Lost World 67-45, Cure 66-46, Blood Run 63-49,
Battleforged 62-50, Hektik 60-52, Campgrounds 59-53, Sinister 54-58, Furious Heights 54-58. Aerowalk is the clearest gain
(34-14 in the last three checks, 14-2 at update 130). Sinister and Furious Heights are level: Furious Heights swung 5-11, 13-3,
7-9, 5-11 between checks, which is noise at 16 games.

**Against v0.4.2b's end:** 108-52 (67.5%) at update 60, 93-67 (58.1%) at update 110; update 150 is playing. v0.6.0's end
read 56.2% there.

## Behaviour panel

- **Green:** updates 10, 40-90, 110, 140.
- **Red:**
  - hunting the scripted watcher, 0.23 frags a minute against 0.32 (updates 20, 30, 120, 130): the same flag as all of v0.6.0's night;
  - the red armor's share of the pickups, 0.43 against 0.51 (100, 130);
  - camping on Aerowalk near the yellow armor, 23-24% of his time against 12% (120, 130), where he wins most;
  - rockets at mid range, 0.10 against 0.15 (130);
  - **roaming, 20.1 cells a minute against 27.1 (150), the first save on win chance only.**

## Pay

| | Update 30 (before) | 90 (`WIN_W` 0.5) | 130 (1.0) | 157 (win only) |
|---|---|---|---|---|
| The win part's share of the pay | 0 | 26% | 65% | **100%** |
| Damage dealt + taken | 34% | 19% | 5% | 0 |
| Frags + deaths | 18% | 10% | 3% | 0 |
| Item pickups, order, stack | 24% | 23% | 14% | 0 |
| Pay size a player-minute | 8.19 | 7.46 | 5.45 | **4.22** |

- The win part's size at a gain of 1 stayed at 12.5 to 13.4 all night (29 at update 1, the start-up transient the ramp skips),
  so the gain of 0.33 held its sizing: the win part paid about what the fight's pay paid before it.
- **Pathology check:** a frag or damage of the wrong sign is impossible by construction (the judge's axioms). In the self-play
  games: no negative score at updates 80 and 120 (2 at update 40 from suicides; v0.6.0 had 4 in 60 games); no lopsided games
  (largest margin 12 to 13 frags against v0.6.0's 16, median 4 to 5.5); no draws. The full ledger (`tools/pay_ledger.py`)
  needs a run of recorded games, and I started nothing tonight.

## Weapons, accuracy, items (training averages)

| | Before (1-30) | Win pay (44-90) | 91-130 | 131-157 | v0.6.0's end |
|---|---|---|---|---|---|
| Rockets in hand | 0.163 | 0.167 | 0.170 | 0.170 | 0.160 |
| Rail in hand | 0.209 | 0.205 | 0.196 | **0.195** (0.182 at 157) | 0.217 |
| Lightning gun in hand | 0.448 | 0.444 | 0.445 | 0.438 | 0.450 |
| Plasma in hand | 0.113 | 0.121 | 0.129 | **0.136** | 0.106 |
| Hit rate RL / RG / LG | .49 / .34 / .37 | .49 / .34 / .37 | .49 / .34 / .37 | .49 / .34 / .37 | .49 / .35 / .37 |
| Mega / red armor a player-minute | 0.81 / 0.94 | 0.79 / 0.94 | 0.80 / 0.94 | 0.80 / 0.94 | 0.73 / 0.93 |
| Weapons a player-minute | 3.66 | 3.58 | 3.51 | 3.49 | 3.68 |
| Frags a match-minute | 1.65 | 1.65 | 1.58 | **1.56** | 1.75 |

- **Items held up with no item pay**: megas and red armors are where they were. The judge's worth of a stack carries them.
- Accuracy is flat on every weapon.
- A little more plasma and rockets, less rail.

**Rail:** in hand 0.21 → 0.18-0.20, shots 2.0 → 1.8 a minute, frag share 18% → 15%. Hit rate near 0.39-0.41 (flat), mid
0.21-0.29, far 0.09-0.31 (too few shots to read). The hand-set worth of owning the rail (= the lightning gun's) pays taking it,
not holding it, and holding it fell a little.

## Self-play games (the judge's next training data)

Updates 40 and 80: 50 whole games each, done. Update 120: 40 of 50 (Cure playing). Update 160 comes next.

## What did not work

- **No win-rate gain from the win pay so far**: 55.5% on it against 55.3% before it. Holding level was the bar for the fade.
  Beating v0.6.0's end is still to come.
- **Rail use fell** a little despite the hand-set worth.
- **The watcher flag is still there**, as through all of v0.6.0.

## Weaknesses seen

- **A slower, more holding game**: fewer frags (−11% against v0.6.0's end), less roaming at update 150, more camping on
  Aerowalk. Under win-chance pay, a held lead is worth keeping, so this may be the right equilibrium against himself. It is also
  the shape a person could exploit by pressing him. Today's checks and your play test will tell.
- **Half the pay, the same entropy bonus**: the policy's push toward randomness now weighs twice as much against what he is paid.
  Entropy 1.80 → 1.92 since the fade ended. If it keeps rising, his play spreads out for no gain.
- **Win chance only for 4 updates**: nothing yet says how he does when it is the only pay.

## Options for your review (none acted on)

1. **Leave it running to 20:05** on win chance only and judge it on the checks from update 160 on. This was the plan.
2. **If entropy keeps rising** (over ~2.0 by noon): `WIN_GAIN` 0.33 → ~0.66 in `live.json` brings the pay back to its
   pre-fade size. This is a live change at a save; the alternative is a lower `--ent-coef`, which needs a restart.
3. **Fix `check_settings.py`** so it reads `--no-switch 1` as `NO_SWITCH=1`. Then the `--ck` check passes cleanly.
4. **v0.6.2's judge**: refit on v0.6.1's own self-play games (updates 40 to 160+). As the card says, the hand-set rocket and
   rail worth would come out unless you keep it. With rail use falling, that is worth a look.
5. **Your play test tonight**: watch whether he holds and waits when ahead. That is where the slower game shows, and where a
   person could press him.

# `duel_gru_v13`: mid-run report (2026-10-09, data to 05:20, eight hours in)

The run of [MANIFEST_v13.md](MANIFEST_v13.md), started 2026-10-08 21:26, still training (it ends itself at 16:00).
Numbers are the mean of ten updates; the duels are 48 ten-minute games a map against the Nightmare stand-in, played
every eighteen minutes from the latest save. "Start" is the starting network under v13's own settings.

## In short

- **It is going well, on every one of the owner's priorities. Nothing has collapsed. My recommendation: let it run.**
- **Items and weapons**: time without a big weapon 37% -> 17%, big weapons held 0.87 -> 1.35, red armor taken 0.21 ->
  0.58 a player-minute, the machine gun's share of his frags 23% -> 7%.
- **Against the stand-in he now wins on both duel maps**: Aerowalk 71% of the frags and 48 games of 48 (start 52%, 27),
  Blood Run 58% and 31 of 48 (start 30%, none). He takes Blood Run's red armor on 26% of its spawns (start 0%).
- **The first four hours looked worse than they were**: under the walking and weapon teachers he fell below the starting
  network in these duels; from the hour they were gone everything rose.
- **Not going the way he asked**: rockets are slipping since the weapon teacher ended (34% of his frags -> 22%, lightning
  49%), and there is no strafe jumping (he is faster, 265 -> 290, but by walking: fast in the air 9% of the time).

## Where the run stands

| | |
|---|---|
| Updates, time | 255 updates, 473 minutes; 987 million frames (6,850 hours of play); 34,600 frames a second (v12: 32,200) |
| Teachers | walking and weapon teachers faded to zero at 01:26 (four hours in); the item rule stays on the intention |
| Health | no errors, no stop sign at any check; policy step 0.008, 9% of samples clipped |
| The PC | one trainer uses 27% of the CPU; the duel checks run on spare cores at low priority |

## Self-play, hour by hour

| | start | 1 h | 2 h | 3 h | 4 h | 5 h | 6 h | 7 h | now |
|---|---|---|---|---|---|---|---|---|---|
| Time bare | 37% | 32% | 29% | 27% | 24% | 19% | 18% | 18% | 17% |
| Big weapons held | 0.87 | 0.96 | 0.99 | 1.02 | 1.09 | 1.24 | 1.30 | 1.34 | 1.35 |
| Stack of 150 or more | 14% | 17% | 18% | 18% | 20% | 21% | 23% | 23% | 24% |
| Weapons picked up a player-minute | 2.43 | 2.44 | 2.52 | 2.56 | 2.77 | 3.29 | 3.50 | 3.66 | 3.72 |
| Mega a player-minute | 0.50 | 0.53 | 0.55 | 0.56 | 0.60 | 0.65 | 0.68 | 0.69 | 0.69 |
| Red armor a player-minute | 0.21 | 0.24 | 0.26 | 0.29 | 0.33 | 0.42 | 0.50 | 0.56 | 0.58 |
| Other armor a player-minute | 1.57 | 1.68 | 1.81 | 1.85 | 1.96 | 2.18 | 2.28 | 2.38 | 2.40 |
| Trips to his chosen item that arrive | 36% | 38% | 39% | 41% | 44% | 48% | 50% | 51% | 51% |
| Frags by rockets | 25% | 29% | 31% | 31% | **34%** | 30% | 26% | 24% | 22% |
| ... lightning | 34% | 34% | 35% | 35% | 34% | 43% | 48% | 49% | 49% |
| ... rail | 18% | 18% | 19% | 20% | 20% | 19% | 20% | 20% | 23% |
| ... machine gun | 23% | 19% | 15% | 14% | 12% | 8% | 6% | 7% | 7% |
| Frags a match-minute | 2.66 | 2.46 | 2.50 | 2.48 | 2.56 | 2.90 | 2.94 | 3.03 | 3.09 |
| On target, enemy in view | 31% | 30% | 31% | 31% | 31% | 32% | 32% | 33% | 33% |
| Against the scripted runner: frags, deaths a minute | 0.59, 2.04 | 0.64, 1.88 | 0.72, 1.91 | 0.81, 1.82 | 0.92, 1.81 | 1.17, 1.75 | 1.25, 1.65 | 1.29, 1.65 | |
| Share of frags against his older selves | 44% | 45% | 50% | 52% | 54% | 60% | 57% | 55% | 56% |
| Speed on his way | 265 | 263 | 265 | 265 | 271 | 282 | 285 | 288 | 290 |
| Fast in the air | 21% | 24% | 26% | 26% | 25% | 15% | 11% | 10% | 9% |
| Key actions a second: made, asked (8 allowed) | 6.7, 8.1 | 7.0, 9.1 | 7.4, 10.0 | 7.5, 10.2 | 7.4, 9.4 | 6.6, 7.4 | 6.1, 6.5 | 5.8, 5.8 | 5.6, 5.6 |
| Walking teacher's weight | 0.48 | 0.40 | 0.27 | 0.15 | 0.02 | 0 | 0 | 0 | 0 |

Also at 05:20: races for a big item (15% of his rounds) end with a learner taking it in 48% of them (17% at the
start); a trip takes 5.9 s (7.9) and 30% are dropped (40%); his armor soaks 82 damage a player-minute (37); hit rates
rockets 46%, rail 45% (38%), lightning 42% (38%), machine gun 37%. Lives without a preferred weapon, the weak spot of v12,
hold 1.29 big weapons (0.65) and make 0.99 frags a death (0.76). By map: time bare 18% on Blood Run, 15% on Aerowalk, 19%
on Lost World; Lost World has the fewest frags (0.78 a player-minute against 1.32 and 1.80).

For scale: v12 ended at 54% of the time bare, 0.57 big weapons held, 45% of his frags by machine gun, speed 257 (on four
maps and under its own settings; the "start" column is the like-for-like baseline).

## Against the Nightmare stand-in (the duel curve)

| Check | Blood Run: share of frags (95%) | kills a game | won / lost | Aerowalk: share of frags | kills a game | won / lost |
|---|---|---|---|---|---|---|
| start | 30% (27-32) | 8.0 : 19.0 | 0 / 47 | 52% (50-55) | 21.6 : 19.5 | 27 / 16 |
| update 10 (22:06) | 18% (16-20) | 3.0 : 13.8 | 0 / 48 | 41% (38-43) | 13.1 : 19.2 | 4 / 43 |
| update 50 (23:20) | 23% (19-26) | 3.0 : 10.2 | 0 / 48 | 45% (43-48) | 13.3 : 16.0 | 10 / 38 |
| update 100 (00:54) | 25% (22-29) | 3.0 : 9.1 | 1 / 45 | 46% (44-49) | 13.7 : 15.8 | 12 / 35 |
| update 120 (01:30, teachers gone) | 28% (25-31) | 3.4 : 8.8 | 3 / 44 | 49% (46-51) | 13.8 : 14.6 | 19 / 28 |
| update 150 (02:25) | 38% (34-42) | 5.2 : 8.3 | 5 / 41 | 62% (59-65) | 18.8 : 11.7 | 40 / 7 |
| update 180 (03:20) | 47% (43-50) | 6.1 : 7.0 | 17 / 29 | 66% (63-68) | 20.1 : 10.6 | 46 / 2 |
| update 210 (04:15) | 56% (52-59) | 7.9 : 6.3 | 34 / 10 | 68% (66-71) | 19.8 : 9.2 | 47 / 1 |
| update 240 (05:11) | **58% (55-62)** | 8.6 : 6.1 | **31 / 12** | **71% (69-73)** | 21.0 : 8.6 | **48 / 0** |

| At the last check (start) | Blood Run | Aerowalk |
|---|---|---|
| Time bare | 6% (33%) | 5% (24%) |
| Stack of 150 or more: he, the stand-in | 59%, 43% (10%, 44%) | 46%, 15% (12%, 15%) |
| Mega, red armor: his share of their spawns | 45%, 26% (29%, 0%) | 64%, 5% (31%, 9%) |
| Yellow armor a minute | 2.8 (0.39) | 2.0 (0.12) |
| Damage a kill costs: his kills, the stand-in's | 291, 475 (340, 173) | 179, 407 (205, 193) |
| His frags by rockets / lightning / rail / machine gun | 30 / 35 / 31 / 4% (21 / 41 / 22 / 16) | 11 / 52 / 37 / 1% (21 / 37 / 30 / 12) |
| Hit rate: rockets, lightning, rail | 49, 41, 41% (44, 38, 34) | 50, 48, 51% (55, 45, 46) |

**Why it dipped, why it rose.** Under the teachers he stopped hunting the stand-in: his speed toward it when he was
the stronger one fell from +108 to +57 units a second on Blood Run and from +63 to +14 on Aerowalk, he saw it a third
less, and fired half as many lightning and machine-gun shots, while already holding a stack three times as often. The
stand-in, left alone, stacked and killed him at leisure. Once the teachers were gone the stack turned into kills: he is
the stronger one in 64% of their meetings on Blood Run (12% at the start), and a kill on him costs 475 damage (173). He
still closes in less than the starting network did (+55 on Blood Run, +17 on Aerowalk when strong): he wins on stack and
aim, not on chasing.

**arena1** (not trained in this run): 37 to 40% of the frags throughout (start 38%), 9 to 14 games won of 48 (none at the
start, because he no longer falls: 2 to 3 own deaths a game against 14.7). He takes its red armor never (29% at the start)
and its mega on 19% of spawns (30%), and moves at 226 to 240 there (287): he is forgetting the yard while not unlearning
to fight on it.

## The new things, one by one

| | What the run shows |
|---|---|
| Dropped weapons | 1.07 fall a player-minute; two thirds are taken, steady from the first hour; 44% of those are new to the taker (65% at the start, when fewer had weapons) |
| The ground at his feet | on arena1 the falls went from 14.7 to 2.4 a game at the first save, before training could have taught it: he sees the edge now. The price: he stays off the island with the red armor |
| Teachers held back from the shared layers | on target stayed at 30 to 33% from the first update (v12 lost four points at its start and never got them back) |
| The hand at 8 | under the walking teacher he made 7.4 to 7.5 actions a second and asked for 10; without it he makes 5.6 and asks for 5.6: nothing refused, no spam |
| Pay for knowing where the enemy is | the measure has barely moved (0.37 -> 0.39): it has not changed how he looks so far |
| Pay for pace | 0.02 a player-minute: he is almost never above running speed on his way, so it pays next to nothing and has not brought jumping |
| Speed | 265 for four hours (the walking teacher's own pace), 290 now; fast in the air fell from 21-26% under the jump label to 9% |
| Closing in, self-play | unchanged: -4 when weak, +47 in between, +63 when strong |
| Races for a big item | a learner takes it in 48% of them (17% at the start; v12: 15 to 18%) |

## What is not going the way he asked

1. **Rockets.** "If anything he should be using more rockets as time goes on": they rose to 34% of his frags under the
   weapon teacher and have slipped to 22% since it ended; in the Aerowalk duels 11% (lightning 52%, rail 37%). At close
   range he holds lightning 35%, rockets 27%, rail 21% (the pros' first choice there is rockets). His weapon key agrees
   with the pros' weapon for the distance 82% of the time (90% at the start). Likely reasons, to be tested, not changed
   mid-run: his own splash is charged at full price since v13 (damage taken at full price), and lightning pays steadily
   at a 42% hit rate. Options for the next run: keep a light weapon teacher on instead of fading it to zero; charge his
   own splash less; pay rocket damage a little more in rocket lives.
2. **Strafe jumping.** None. The jump key lived only as long as its teacher; the pace pay is too small to matter at
   0.02 a player-minute. He needs to be shown air strafing (keys and turn together, from the pro demos) or given rounds
   whose point is speed. Not in this run.
3. **arena1** is not trained and drifts (above). If people are to play him there, some of the training has to stay there
   (B-162, the owner's call).
4. **Looking around.** The pay for knowing where the enemy is has not moved its own measure.
5. **Lost World** has no duel check (the stand-in hardly moves there) and the fewest frags in training.

## Where it is still going

Still rising at 05:20: Blood Run against the stand-in (two points an hour now, eight an hour at 03:00), red armor and
weapons picked up, frags (3.09), hit rates. Flat for three hours: time bare (17 to 18%), trips that arrive (51%), the share
of frags against his older selves (55 to 57%). Aerowalk is at its ceiling (48 of 48). The run is past its steep part and
not yet flat.

## Definitions of success (MANIFEST, section 8) and where each stands

| | v12 | v13 at 05:20 |
|---|---|---|
| Share of the frags against the stand-in: arena1, Blood Run, Aerowalk | 35%, 25%, 47% | 37%, **58%**, **71%** |
| His share of the red armor's spawns there | 19%, 0%, 9% | 0%, **26%**, 5% |
| His share of the mega's spawns | 21%, 24%, 21% | 19%, **45%**, **64%** |
| Races for a big item taken by a learner | 15 to 18% | **48%** |
| Time bare; the machine gun's share of his frags | 54%; 45% | **17%; 7%** |
| Fast in the air; speed on his way | 9%; 257 | 9%; 290 (no strafe jumping) |
| Real Nightmare games, ten minutes | 14-27, 7-18, 6-13 | to be played at the end, on a free PC |

## What to look out for today

- **Saturation**: if Blood Run's duel share, the red armor and the frags stop rising for three hours, he has what this
  setup can give and the run should stop before 16:00.
- **Rockets** falling further (under 15% in self-play would be a third of their peak).
- **Collecting without fighting**: stack rising while frags or the duels fall. Not the case now.
- The usual stop signs: weapon pickups or big weapons held down by 30%, the machine gun's share up 15 points, firing
  under 8% of frames, frags under 1.2 a match-minute, the policy's step over 0.05.

## Recommendation

**Let it run.** It is still improving on the things asked for and nothing is degrading that training on these maps can
fix. At its end: 100 duels a map against the stand-in, the scorecard, the reflex room, videos, and real Nightmare games
on a free PC, then the full report with what to try next. The two things this run will not deliver, rockets and strafe
jumping, need a decision for the next one.

## Heat maps and videos

From the save of update 240 (05:02): where he spends his time on the three duel maps and arena1, and a first-person duel
against himself on Blood Run and on Aerowalk (`videos/duel_gru_v13_*/`, not in the repository).

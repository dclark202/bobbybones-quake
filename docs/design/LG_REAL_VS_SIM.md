# The lightning: real games against the simulator (1.6a, 2026-11-13)

The owner (11-13): "the LG numbers in practice don't hold up to the real game". A measurement, no training. The question: is the
simulator's lightning more generous than Quake Live's, so that training in it overvalues the lightning?

## What was compared

| | Real games | The simulator |
|---|---|---|
| Network | 1.6a's end on the public servers (`policy: duel_gru_1_6a`) | the same file, `keep/policy_end_16a.pt` |
| Games | 58 sessions against people, 11-05 to 11-09 (US and Amsterdam; 5 of them the owner's, 46 minutes): the session archive. Last night's are not in it: the daily pull has been off since 11-09 | 40 ten-minute games, 1.6a against itself, ten maps, the settings of 1.6a's own checks (`check_settings` against its update-50 check: only the per-seat copies of the same settings differ) |
| Aim | each session's `!aim` level, from its events | default (AIM_LEVEL 3, the pros' mean; delays 125 / 225 ms) |
| Shots | the lightning ammo's drops frame to frame, the lightning held | the simulator's own `lg_shots` |
| Hits | the session's hit events with the lightning (from health and armor drops) | the simulator's own `lg_hits` |
| Distance | between the two players, at the shot and at the hit | between the two players at the shot |
| Tools | `tools/run/lg_real.py` -> [lg_real_16a.json](lg_real_16a.json) | `tools/run/lg_sim.py` (duel_eval unchanged, the step wrapped) -> [lg_sim_16a.json](lg_sim_16a.json) |

## Result

**His own lightning is about the same in both.** At the default aim the simulator gives him 37.5% against 33.8% in real games.
By distance the two are close everywhere except over 800 units:

| Bobby's lightning, default aim | Hit rate | Shots a minute | Damage a minute | Lightning in hand (of the time) |
|---|---|---|---|---|
| Simulator (against himself, 808 seat-minutes) | **37.5%** | 112 | about 250 | 58% |
| Real, against people (304 minutes) | **33.8%** | 100 | 210 | 61% |
| Real, against the owner (29 minutes) | **26.9%** | 61 | 99 | 72% |

| Hit rate by distance (units) | 0-200 | 200-400 | 400-600 | 600-800 | 800+ |
|---|---|---|---|---|---|
| Simulator, Bobby | 49.5% | 43.1% | 29.1% | 18.8% | 0.4% |
| Real, Bobby against people | 49.0% | 39.1% | 28.6% | 22.4% | 7.9% |
| Real, Bobby against the owner (few shots) | 33% | 33% | 24% | 14% | 5% |
| **Real, people against Bobby** | 42.4% | **43.2%** | **43.0%** | **39.1%** | 6.3% |

What it says:

1. **The simulator does not hand him a better lightning than the game does.** His hit rate, shots a minute and time with it in hand
   are within a few points. The physics, the hit test and the aim limits are not the gap.
2. **The gap is the opponent.** In the simulator he shoots at himself. In the game, people hit him with the lightning far better than he
   hits them: 43% at 200 to 600 units against his 29 to 39%. Against the owner he lands 27% and does 99 damage a minute, two fifths of
   what the simulator gives him. People move to be hard to hit; his copies don't, and he does not move to be hard to hit either.
   Self-play trains him against an opponent who is as easy to track as he is, so the lightning pays more in training than against a
   person who dodges.
3. Over 800 units: the game records hits that the simulator, with a range of 768, can't give. That's small (2-3% of his shots) and is
   probably distance measured between origins at a slightly different moment. It isn't a lever.

## What this means for the plan

- AIM3 limits **his** aim. It does nothing about how easy **he** is to hit, or how easy his copies are. That is the lever this
  measurement points at: movement under fire (dodging the lightning), and an opponent in training who dodges like a person.
- Rule 12 allows measuring it from the pros: how much a player's movement under fire lowers the hit rate against them, by distance.
  It doesn't allow making a pro's movement a target.
- Proposed (the owner decides):
  - (a) a readout at every check: **his hit rate against his opponent, and his opponent's against him**, by distance, beside the
    real-game table above;
  - (b) the same comparison on the owner's games of last night, once the session pull runs again;
  - (c) measure how hard a pro is to hit with the lightning (the hit rate against them, by distance and by their speed across the
    line of fire), as a number for the simulator's opponents, not for his behaviour.

## Limits

- 1.6a only. The owner's own games are 5 sessions (46 minutes), a small sample.
- Real hits come from health and armor drops a frame, so two hits in one frame count as one: damage a hit averages 6.2 against 6. The
  real hit rate may be a point low.
- The people choose when to fight him; the simulator's opponent is the same network every game.

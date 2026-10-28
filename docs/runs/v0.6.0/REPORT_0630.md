# 06:30 report, Wed 10-28: v0.6.0 overnight, and v0.6.1's calibration

**v0.6.0** (`duel_gru_v0_6_0`): v0.5.0's setup from v0.4.2b's end, at the new pro-measured `!aim default`. Started 19:42,
now at update 155. No stall, no restart. The guard has been off since 21:01 (your call: never stop the run).

## Recommendation: GO for v0.6.1 at ~07:00

v0.6.0 beats its start at the same aim (62% at update 130), and nothing collapsed. Two settings change from the plan:
- **`WIN_GAIN` is 3.85, not 1.75.**
- **The shaping weight is raised with it, to about 2.2.**

Both are under "Calibration" below.

## Checks against v0.4.2b's end (160 games, both seats at the new default)

| Update | 10 | 30 | 50 | 70 | 90 | 110 | 130 |
|---|---|---|---|---|---|---|---|
| Won-lost | 94-66 | 86-74 | 82-78 | 102-58 | 102-58 | 75-85 | 99-61 |
| Win rate | 58.8% | 53.8% | 51.2% | **63.7%** | **63.7%** | 46.9% | **61.9%** |

The checks skip a save while the previous check is still playing, so only every 20 updates is checked. The 46.9% at update
110 was one low check between two above 60%.

## Behaviour panel

- **Green:** updates 10, 40, 60, 80, 140.
- **Red, every time the same flag:** hunting the scripted watcher. 0.21-0.24 frags a minute against the control's 0.31,
  at updates 20, 30, 70, 90, 100, 110, 130, 150. He beats the real opponent but is slower against a still target that holds a
  spot.
- **Red once each:**
  - rockets at mid range, 0.11 against 0.15 (updates 50, 110);
  - "passive", 0.12 frags a seat-minute in self-play against 0.20 (update 120).

## Weapons, accuracy, items (training, update 1 → 155)

**Weapon in hand (share of time):**

| | Rockets | Rail | Lightning gun | Plasma |
|---|---|---|---|---|
| Bobby, update 150 | 0.18 | 0.18 | 0.43 | 0.14 |
| Bobby, of the three big weapons | 23% | 23% | 54% | |
| Pros, of the three big weapons (3,712 demos) | 38% | 21% | 41% | |

Too little rockets and too much lightning gun against the pros. This was the same at the start (rockets 0.19).

**Hit rate:**

| | Rockets | Rail | Lightning gun | Plasma |
|---|---|---|---|---|
| Update 1 | 0.46 | 0.35 | 0.37 | 0.22 |
| Peak | 0.51 (update 81) | | | |
| Update 155 | 0.47 | 0.32 | 0.35 | 0.19 |

Flat, a little down.

**Items a player-minute:**

| | Mega | Red armor | Armors | Weapons |
|---|---|---|---|---|
| Update 1 | 1.41 | 0.97 | 2.78 | 5.06 |
| Update 155 | 0.78 | 0.98 | 2.20 | 3.53 |

Megas settled at about 0.8 by update 20. The red armor held.

**Frags a match-minute:** 1.34 at update 1, a peak of 1.89 at update 21, then 1.57. Fewer fights than the peak, which matches
the one "passive" flag.

## Calibration for v0.6.1 (on the save of update 130; started 05:02)

| Part | Result |
|---|---|
| (a) `WIN_GAIN` | **3.85**, from updates 117-136: combat 4.42 a player-minute, the win part 1.15; steady, 10-90% 3.75-3.94. v0.5.1 had 1.75. |
| (b) Pay by term, his seats, last 20 updates | damage 35%, frags 18%, item pickups 17%, way and speed 11%, the hands' costs 10%, the stack 4%, item order 3%, watching/pre-aim 2%, rail 0.1%. Everything but frags and damage fades to 0 by step 12. |
| Self-play games, logged once a second | 6 of 10 maps done, the last 4 running; done ~06:45 |
| (c) The stack refit and K, (d) close-game baselines, his win sense | come after the games; added to this report before 07:00 |

**Why the gain doubled.** The win part a player-minute fell from 1.70 at update 10 to 1.13. His games moved his chance of
winning less per minute: fewer frags, and more games decided early. To keep the total pay at today's size, the win part needs
3.85. This doesn't change what he learns in the end; it sets the size of the pay against the flat pay still in place during
the fade.

**The shaping weight has to follow the gain.**
- The ledger's K = 1 kept a 100-damage hit at 0.53 of a frag at a gain of 1.75.
- The win part grows with the gain, but the shaping doesn't. At 3.85 with K = 1, a hit would drop to about 0.47 of a frag.
- K x 3.85 / 1.75 ≈ **2.2** keeps 0.53. 2.5 gives the flat pay's 0.55.
- The refit (c) gives the exact number from his own games. I'd use its value, or 2.2 if it isn't in by 07:00.
- Either way the shaping stays neutral: it leaves the self-play equilibrium unchanged.

## What starts at ~07:00 on your go

- v0.6.0 stops right after its next save. Its end is kept as `keep/policy_end_v060.pt` with its optimizer.
- v0.6.1 starts from it:
  - code: branch `v061`;
  - mix: 65 / 35;
  - aim: the new default;
  - `RAMP_GAIN` 3.85;
  - `RAMP_K` 2.2 (or the refit's value);
  - step 1 with the 10-update critic warm-up, then a step every 10 updates and at least 25 min, whatever the checks say.
- Checks against v0.6.0's end. Under 40% I flag it to you, under 30% I post it here. Never stopped.
- Every check logs:
  - weapons, items and accuracy;
  - agreement with the item rule;
  - pay by lead and time left;
  - the brain's readouts.
- The fade is done around 17:00. Your play test is ~19:00. The run continues to Thursday noon.

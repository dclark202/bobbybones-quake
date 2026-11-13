# 1.9a: postmortem (2026-11-13)

**Run**: `duel_gru_1_9a` ([RUNS.md](../../../RUNS.md) #49), from 1.8a's end (u190). It ran from 2026-11-12 19:35 to 2026-11-13 07:14
(11 h 39) and reached update 95. **The owner stopped it** at 07:14 ("Just stop it now and write a postmortem"). `finish_19a` (the 08:00
resume) was cancelled before it ran. The trainer, the ramp and the logger were stopped by command line; the watcher was left to finish
its check. The end kept is the update-90 save (`keep/policy_end_19a.pt` + `opt_end_19a.pt`, copies of `policy_u90_19a.pt`). It is not
a network to use. **1.8a's end stays the best network.** The card: [CARD.md](CARD.md).

## What happened

| Check | Against | Head's share | Record | Win rate | Frag share |
|---|---|---|---|---|---|
| u10 | 1.8a end | 0 | 96-104 | 48.0% | 51.3% |
| u30 | 1.8a end | 0.27 | 102-98 | 51.0% | 52.7% |
| u50 | 1.8a end | 0.63 | 83-117 | 41.5% | 44.4% |
| u70 | 1.7a u90 (long-term) | 0.97 | **31-169** | **15.5%** | 28.6% |
| u90 (8 of 10 maps) | 1.8a end | 1.0 | **4-156** | **2.5%** | about 17% |

For scale, 1.8a against 1.7a u90 was 40.5% (its u150). The checks play the head at the save's own share (`head2.ins_g` is in the
checkpoint), so they measured what the head did.

While the head played no seat (u0-12), nothing changed (48%). With the head on a quarter of the seats, the cost did not show (51% at
u30). From a share of about 0.6 it fell, and at full share it collapsed: every map lost at u90, 0 to 1 win in 20 games on each.

| Training readout | u11 | u31 | u51 | u71 | u95 |
|---|---|---|---|---|---|
| head's share (`INS_G`) | 0 | 0.27 | 0.60 | 0.93 | 1.0 |
| the head's choice: entropy (uniform over ~26 offered = 3.26) | 3.29 | 3.28 | 3.24 | 3.07 | 2.54 |
| order changes a second on played seats (one tick = 0.2 s) | - | 4.81 | 4.78 | 4.70 | 4.18 |
| bound weapon changes a minute (flag over 20) | 6.8 | 107 | 103 | 60 | 39 |
| the bound weapon not the hands' own pick | - | 53% | 44% | 32% | 27% |
| hands carrying the order out (`follow.doing`) | - | 9.2% | 9.6% | 7.3% | 6.6% |
| the pay term on the head's choice | - | 0.0003 | -0.001 | 0.0005 | 0.0002 |
| gradient into the scorer / the head's target lesson | - | 0.018 / 0.69 | 0.038 / 0.44 | 0.076 / 0.61 | 0.033 / 0.10 |
| the head's pay: items part / judge part | 0.0045 / 0.0058 | 0.0063 / 0.0032 | 0.0068 / 0.0020 | 0.0069 / 0.0026 | 0.0063 / 0.0035 |
| frags a match-minute (alarm under 1.5) | 1.88 | 1.59 | 1.09 | 1.33 | 1.08 |
| new weapons picked up a player-minute | 2.1 | 1.2 | 0.94 | 0.92 | 1.1 |

Behaviour panel (RED at u20 and at every panel from u50): he aimed for the red armor far more than the control (Blood Run 39-45% against
17%, Campgrounds 51% against 23%), camped near it (Campgrounds 20-27% against 8%), took fewer megas (share 0.45 at u90 against 0.97),
and hunted less (0.27 frags a minute against the watcher, control 0.38). Lightning owned fell from 73% (u10) to 48% (u70).

## Why

1. **The head's choice took over his seats untrained.** Rule 13's "learn silently" covered the head's value, the fight odds (AUC
   0.87-0.88, they learned well) and the win value. **It did not cover the choosing.** The only lesson on the scorer was the pay on
   its own played choices (`H2_INS_PG`), so it learned nothing until it played, and then very slowly. Its pay term was about 0.001,
   against gradients 10-20 times larger from the head's target lesson. Over 80 updates its entropy went only from 3.29 to 2.54. In
   effect, a near-uniform sampler over ~26 orders ran his seats from u48 on. The ramp opened the share by the clock (u12-72), not by
   any measure of whether the scorer was ready.
2. **Re-deciding every 0.2 s from a near-uniform sampler is a random walk.** 2.1's "every 0.2 s, no lock" assumes a sharp scorer that
   keeps its choice by choosing it again. With a flat one, the order changed on 95% of ticks (it stood 0.21 s). The binding weapon then
   forced up to 107 weapon changes a minute, half against the hands' own pick. The hands could not carry anything out (6-10% "doing"),
   frags fell to about 1.1 a match-minute, and the binding weapon took the lightning out of his hand.
3. **The head's pay was mostly the items' race, and the race term was noisy.** From u31 the items part of the head's win-chance stream
   was 2-3 times the judge's own part. The race fit was refused twice and accepted on the third form, with a 0.16 floor. A noisy items
   signal paid on choices that were nearly random gives a weak gradient pointing at the item orders. The red-armor fixation and
   camping fit that, while the mega was lost because nothing carried it out. This is a likely contributor, not a proven one.
4. **The alarms went silent, and I did not cover the gap.** The ramp's flag thread crashed at update 16 (21:36), on the first played
   picks: `ins.picks` is a count, and the flag code read it as a dict (`ramp_stderr.log`). From then on no FLAG or MAJOR line was
   written: not the weapon-change flag, not "under 40%" at u70, not passivity. The watcher's own check lines carry no MAJOR mark. My
   own monitor lapsed after the u30 check (00:10), so u50 (41.5%) and u70 (15.5%) were not reported until the owner asked at 07:07.
5. **Red team.** The smoke tests had already shown 145 bound-weapon changes a minute on an untaught scorer. I listed it as a
   watch-from-u12 flag instead of a blocker. At u31 I reported that the scorer was still uniform and asked whether to hold the share,
   but with no answer overnight the clock kept opening it (rule 6), and I did not report again until 07:07.

## What worked

- The silent phase was clean: the hands were untouched while the head learned silently (48% / 51% at u10 / u30). The fight-odds
  readout learned well (skill 0.36-0.38, AUC 0.87-0.88).
- Every dial played as written: no refused live.json, no stall, KL steady at 0.030-0.032. The start, stop and keep tooling worked.
- The u30 save is a valid result for "the head on a quarter of the seats does not cost games" (51% against 1.8a's end). It does not
  show that the head helps.

## Lessons (proposed as rules; the owner decides)

- **Learning silently must include the choosing.** A new chooser does not take seats until its choice has learned something, from
  lessons that need no played seats. Two options that keep rule 13 (no copy of an old rule):
  - its own value's advantage over the offered rows on every shadow tick (its value is paid by the judge, so this is its own
    lesson, not a copy);
  - or the pay on shadow choices, scored by the judge's change in win chance over the tick that followed.
- **Open a chooser's share on a measure, not on the clock alone.** For example: entropy under a set mark, order changes under 1 a
  second, and the bound weapon under 20 a minute on the seats it already plays. With rule 6 (ramps never hold on their own) this means
  the owner sets the mark at the go, and the ramp reports when it is crossed. It never holds by itself.
- **No re-decision every tick without commitment from the chooser itself.** It can be a learned keep choice (as 1.7a's), or the
  choice re-read as "keep or change" with its own value. It must not be the lock: the lock never returns (rule 13). Only a sharp
  scorer can re-choose every 0.2 s.
- **The items' race is not paid to the head until its noise is under the judge's own part.** Measure that on recorded games first.
- **Monitoring:** a crashed flag thread must stop the ramp loudly, or be restarted and logged. Every flag code is tested on a real
  `metrics.jsonl` line from a smoke run with played seats. The watcher's check line carries the MAJOR mark itself. My own monitor
  runs to the run's end, chained, with no gap.

# v0.3 mid-run report (Thursday 2026-10-15, 06:15)

*Run `duel_gru_v0_3`, started 20:17 Wednesday ([RUN_v0.3.md](RUN_v0.3.md)). Time limit 18:00 today.*

**In short:** a clean night, and a real lead over v0.2. He rose from level to a peak of 57.5% at update 70, then
fell for two checks to 52.1%. The noon rule needs the last three checks rising, so as things stand the run stops at noon.
The best network so far is the save of update 70, and every checked save is kept.

## The night

101 updates in ten hours, about 6 minutes each. No stall, no crash and no error. The trainer is alive (last update 06:13).
He has played about 11,000 steps a second since midnight, faster than the 9,000 at the start.

## Against v0.2 (160 ten-minute games on ten maps each; level 50%, V's bar 53.5%, one check moves about ±3 by chance)

| Update | 0 | 10 | 20 | 30 | 40 | 50 | 60 | 70 | 80 | 90 |
|---|---|---|---|---|---|---|---|---|---|---|
| % against v0.2 | 51.0 | 50.8 | 52.5 | 52.6 | **55.0** | 54.3 | **56.2** | **57.5** | 54.3 | 52.1 |

- **Trend:** a steady climb for six hours, from level to 57.5%. V's best check was 53.9%.
  The last two checks fell back, and 52.1 is inside the noise of 54 to 55. The mean of updates 40 to 90 is 54.9%.
- **By map:** Blood Run is his weak map all night (43 to 55%, mostly under level). Toxicity, Cure and Furious Heights are
  his best (55 to 68%).
- **His legs** (the movement network driving him) rose from 51% of his time at the start to 63%.

## Weapon watch (styles are off; time in hand, and against test run V)

| | Rockets | Rail | Lightning | Plasma | Grenades |
|---|---|---|---|---|---|
| V (pretest) | 18% | 18% | 48% | | |
| v0.3 update 10 | 34% | 14% | 37% | 1% | 0 |
| v0.3 update 100 | 22% | 13% | 43% | 12% | 0 |

No collapse: the alarm is a weapon under half of V's share, and none came near it. Rockets fell from 34% to 22% in the
first two hours and then held, above V's level. Plasma grew from nothing to 12%. Grenades and the shotgun are unused, as
in every earlier run. Frags: lightning 55%, rockets 16%, rail 15%, plasma 12%.

## Stop rules and noon

- The two falls in a row (57.5, 54.3, 52.1) are one short of the automatic stop rule, which needs three. The update-100
  check (due about 06:30) decides it. If it reads under 52.1%, the run stops there by itself.
- **Noon:** to go on to 18:00, the last three checks must rise beyond about 2 points. They are falling, so unless
  updates 100 to 110 climb back sharply, **the run stops at noon** (about update 160 at most).
- **Which save to evaluate:** the update-70 save reads best (57.5%), but one check is ±3. Before the 18:00 evaluation,
  I'd check the top two or three saves (60, 70 and the last) again against v0.2 with more games, then evaluate the winner.
  That takes about an hour.

## What to watch

- Whether the fall is noise or a real slide. A slide after a peak looks like his league of recent selves pulling
  him into a style that beats them but not v0.2.
- Blood Run, the public server's map, is his weakest.
- Rail time in hand is slowly falling (18% to 13%).

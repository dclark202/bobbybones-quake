# b1.1a: 06:30 report, 2026-11-01 (`duel_gru_b1_1a`, update 165)

All three fades finished on schedule, with no crash and no hold. No check has read a save with the lock changed yet.

| Save | Dials at that save | Against | Record | Win rate | Frag share |
|---|---|---|---|---|---|
| u10 | none | b1.0a's end | 90-70 | 56.2% | 52.9% |
| u30 | brain ~0.2 | b1.0a's end | 91-69 | 56.9% | 54.2% |
| u50 | brain ~0.5 | b1.0a's end | 85-75 | 53.1% | 51.1% |
| u70 | brain ~0.8 | v0.6.0's end | 92-68 | 57.5% | 53.4% |
| u90 | brain 1 | b1.0a's end | 83-77 | 51.9% | 51.0% |
| u110 | brain 1, pull ~0.97 | b1.0a's end | 80-80 | 50.0% | 51.7% |
| u130 | brain 1, pull 1 | b1.0a's end | 97-63 | 60.6% | 54.7% |

| 10-update means | u30 | u80 | u120 | u140 | u150 | u160 | u165 |
|---|---|---|---|---|---|---|---|
| Lock | 8 s | 8 s | 8 s | 8 → 4 s | 4 → 2 s | 2 → 1 s | 1 s |
| Trips a player-minute | 12.6 | 12.7 | 12.6 | 12.4 | 13.7 | 16.4 | 17.9 |
| Targets reached | 0.40 | 0.40 | 0.40 | 0.40 | 0.34 | 0.27 | 0.24 |
| The enemy's target share | 1.3% | 1.6% | 1.2% | 1.1% | 1.0% | 1.0% | 1.1% |
| Frags a match-minute | 1.56 | 1.65 | 1.56 | 1.51 | 1.49 | 1.44 | 1.45 |
| Aim error, enemy in view | 13.6 | 13.7 | 13.9 | 14.2 | 14.1 | 14.2 | 14.2 |
| On target, enemy in view | 0.230 | 0.233 | 0.229 | 0.226 | 0.224 | 0.217 | 0.215 |

Rail in hand 0.13 at u20, 0.07 from u140; rocket 0.20 to 0.27. The panel was green from u70 to u160.

## Read

- **The brain:** no clear cost: 53 to 57%, then a low of 50% and a high of 60.6% after it.
- **The pull:** win rate held, but aim error rose about 0.4 degrees over its stretch and frags fell. Those moves started before the lock.
- **The lock:** the flicker the card warned of. Trips up 40%, targets reached down 40%, and the enemy's share has not moved. On these numbers, freeing the choice has not by itself made him fight more. It may settle, or the head may use it; about 20 minutes at 1 s is too soon to call it.
- **The rail:** in hand down about half overnight, with rockets up, the shift seen in the v0.6.1 runs. Unexplained.

## For b1.2a's start

`policy_nopull_b11a.pt` (u140, brain and pull out, lock 8 s) is the save nearest the 60.6% check. **Its own optimizer was not kept:** the ramp copied only the policy, against the owner's standing rule, and `opt.pt` has been overwritten since. Nearest kept: `keep/opt_170_b11a.pt`, 30 updates later, with the lock at 1 s. `ramp_live.py` and `ramp_head.py` now keep the optimizer with every save they keep.

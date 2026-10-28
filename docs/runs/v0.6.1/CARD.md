# v0.6.1: pay by win chance only, the chance from the judge (frozen), from v0.6.0's end

*2026-10-28 (owner): "Build judge. Freeze now, train later." The judge is his chance of winning learned from how his own games
ended, with the owner's four axioms in its shape: "frag good, death bad, deal damage good, take damage bad". It replaces the
hand-built formula (A) and the hand-shaped fit (B2); the earlier design with the stack term and the shaping
([WINPAY_v0.6.1.md](WINPAY_v0.6.1.md)) is superseded. The way there: [B_FIT.md](B_FIT.md) and the review of 2026-10-28.*

**Marks:** ✅ built and tested · ⏳ building · 🧪 to measure · ❓ owner's decision

## The owner's page

| | |
|---|---|
| Network | v0.6.0's end with its optimizer (`keep/policy_end_v060.pt`, kept by `start.ps1`) |
| Pay | the change in his chance of winning (the judge's) x `WIN_GAIN`; the game's last frame pays the result. Faded in by the ramp; every other pay faded out (`FADE_V`); no shaping |
| The judge | `sim/win_judge.py`: lead + stack edge in frags over the frags still to come; each player's worth a small network of his stack in two parts (owner, 2026-10-28: the decay above 100): the lasting part (health up to 100 + armor up to 100, armor counted up to twice the health) and the decaying part (health and armor above 100), his big weapons owned and the time left; a fresh respawn (125 health) is lasting 100 + decaying 25, the anchor a kill resets to. Fitted on v0.6.0's 300 self-play games (`tools/run/fit_b.py`), **frozen** for this run (`WIN_JUDGE`) ✅ code, 🧪 the fit |
| Axioms (by construction) | frag good, death bad (a kill always gains at least a quarter frag of value); damage dealt good, taken bad (a player's worth only rises with his own stack). Checked on 247,104 state changes ✅ |
| Overtime | its own short game: the period's clock (as the simulator's pay reads it); the regulation rows of games that went to overtime are not fitted |
| Ramp | `tools/run/ramp.py`, on the clock (RAMP_ALWAYS): `WIN_GAIN` sized from the run's own counters (updates 21 to 30, the judge's win part against the combat pay); step 1 with the critic's 10-update warm-up; then a step every 10 updates and 25 min: `WIN_W` 0.1 a step to 1, `FADE_V` from step 5 to 1 at step 12 ✅ |
| Code | `main` with branch `v061j` merged (WIN_JUDGE; off = v0.6.0's simulator to the bit) ✅ |
| Aim, mix, maps | as v0.6.0 (`!aim default`; 65% whole games / 35% the pros' mid-game starts; the ten maps) |
| League | v0.4.2b's end and v0.6.0's end as anchors, then his own new snapshots (none of the recovered files) |
| Checks | every 10 updates, 160 games against v0.6.0's end (every fourth against v0.4.2b's end); the behaviour panel. Under 40% flagged, under 30% posted. Never stopped automatically |
| Logged | self-play games of every 40th save (the judge's training data for v0.6.2) |
| Length | 24 hours (`--minutes 1440`; owner, 2026-10-28: start around 21:00, "let it run for 24 hours"). The fade: `WIN_GAIN` sized at updates 21-30 (~2 h), step 1 with the warm-up (~40 min), a step every 10 updates; win chance only from about update 150 (~10 h) |

## The checklist

| | |
|---|---|
| Settings check | `train.cmd` against v0.6.0's `train.cmd`: only `--run`, `--minutes`, `WIN_JUDGE` differ ✅ (`start.ps1` refuses otherwise) |
| Identity | WIN_JUDGE off = v0.6.0's simulator to the bit: inputs, pay, round ends, events, counters; Blood Run and Aerowalk, the blend off and on (`tools/judge_ident.py ident`) ✅ |
| Parity | WIN_JUDGE on: the simulator's chance = the judge's on its own state every frame (0 difference), the win part zero-sum and = scale x the change (`tools/judge_ident.py judge`) ✅ |
| Acceptance of the fit | held-out log loss no worse than B2's interval and better than A; no axiom failure; the value table sensible (hits rise with damage, mega > red armor at low health); drift between saves within the intervals 🧪 |
| Hand-built / assumed parts | the shape "lead + stack edge in frags" (needed to prove the frag axiom); the armor rule (armor counts up to twice the health) and the split at 100 into lasting and decaying; a dead player counts as his respawn at once; the floor below a respawn (at most 0.5 frag for a low lasting part, 0.1 for the decaying part, 0.05 a weapon: together 0.75, which keeps a kill worth at least 0.25 frag); the ramp's schedule |
| Weaknesses | weapons he rarely takes cannot show their worth (the rail: only exploration breaks the loop; refit per version); ammunition, weapon in hand, position and item timers are not in the judge (they pay only through what they lead to); self-play data only; with a 0.999 discount the judge is his goal over ~25 s |
| Pay pathologies (ledger) | a frag or damage dealt of the wrong sign: impossible by construction, checked on the grid ✅; late with a big lead the pay goes quiet (decided games) |
| Test on last night's 60 games | the judge (two parts) 0.4361 held-out log loss, one part 0.4365, B2 0.4360, the free network 0.4394, A 0.4796; axioms hold; the decaying part priced low (a mega at 100+50 +2.3 points at 5:00 level against a red armor's +8.9; wide intervals on 60 games) ✅ |

## Start (after v0.6.0 ends, on the owner's go)

1. `python tools/run/fit_b.py duel_gru_v0_6_0 --boot 30 --out data/sim_runs/judge/judge_v060.npz --json data/sim_runs/judge/judge_v060.json`: the report to the owner.
2. Merge `v061j` into `main`.
3. `powershell -ExecutionPolicy Bypass -File docs\runs\v0.6.1\start.ps1`

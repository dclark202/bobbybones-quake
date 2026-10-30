# v0.6.1: pay by win chance only, the chance from the judge (frozen), from v0.6.0's end

*2026-10-28 (owner): "Build judge. Freeze now, train later." The judge is his chance of winning learned from how his own games
ended, with the owner's four axioms in its shape: "frag good, death bad, deal damage good, take damage bad". It replaces the
hand-built formula (A) and the hand-shaped fit (B2); the earlier design with the stack term and the shaping
([WINPAY_v0.6.1.md](WINPAY_v0.6.1.md)) is superseded. The way there: [B_FIT.md](B_FIT.md) and the review of 2026-10-29.*

> **What follows this run (owner, 2026-10-29), for the session running it:**
> - **v0.6.1 finishes as planned (~18:00).** Nothing about it changes.
> - **Then [v0.6.1b](../v0.6.1b/CARD.md) runs overnight from v0.6.1's end:** the old hand-built belief faded out of the brain
>   (live `BRAIN_FADE`), with the game-end pay fix. **[v0.6.2](../v0.6.2/CARD.md) starts tomorrow morning from v0.6.1b's end,
>   not tonight.**
> - **The game-end pay fix** ([WINPAY_END.md](WINPAY_END.md)) is this session's to land, in `sim/duel_env.py` (then
>   `duel_env_ffa.py` regenerated). Once it is in and checked, set `$FIX_MARK` in
>   [v0.6.1b/start.ps1](../v0.6.1b/start.ps1) to a string the fix's code carries. The start refuses until then. If the fix
>   is a switch, it also goes in v0.6.1b's `train.cmd` and the settings check's allowed list.
> - **Already built for v0.6.1b** (another session, uncommitted on `main`): the brain's dial in `sim/belief.py`,
>   `sim/btoken.py` and `sim/train_duel_rnn.py`. It is inert unless a network carries `belief.fade` or the trainer gets
>   `--brain-fade 1`, so this run and its checks are unaffected. Also built: `tools/run/brain_fade_check.py` (passed on v0.6.0's
>   end), and v0.6.1b's `train.cmd` (settings check against this run's: PASS), `start.ps1` and `smoke.py`.
> - **The order after this run ends:**
>   1. the fix;
>   2. `smoke.py` (~25 min, CPU);
>   3. v0.6.1b's `start.ps1`, on the owner's go.
>
>   `start.ps1` keeps this run's end as `keep/policy_end_v061.pt` itself.
> - **The level fade:** `fade_level.ps1` had not run as of 2026-10-29 afternoon (no log line, no `LEVEL_PULL` in live.json). The
>   owner says it is handled in this run. v0.6.1b takes over whatever `LEVEL_PULL` this run's live.json ends with.

**Marks:** ✅ built and tested · ⏳ building · 🧪 to measure · ❓ owner's decision

## The owner's page

| | |
|---|---|
| Network | v0.6.0's end with its optimizer (`keep/policy_end_v060.pt`, kept by `start.ps1`) |
| Pay | the change in his chance of winning (the judge's) x `WIN_GAIN`; the game's last frame pays the result. Faded in by the ramp; every other pay faded out (`FADE_V`); no shaping |
| The judge | `sim/win_judge.py`: lead + stack edge in frags over the frags still to come; each player's worth a small network of his stack in two parts (owner, 2026-10-28: the decay above 100): the lasting part (health up to 100 + armor up to 100, armor counted up to twice the health) and the decaying part (health and armor above 100), his big weapons owned and the time left; a fresh respawn (125 health) is lasting 100 + decaying 25, the anchor a kill resets to. Fitted on v0.6.0's 300 self-play games (saves 40 to 80; `tools/run/fit_b.py` -> `data/sim_runs/judge/judge_v060.npz`, report beside it), **frozen** for this run. Then by hand (owner, 2026-10-28: "set rl and rg taken ... in line with LG"): owning the rocket launcher or the rail worth the lightning gun's 0.26 frag (fitted: 0.08, 0.07) -> `judge_v060_wpn.npz`, the file `WIN_JUDGE` names ✅ |
| The fit (300 games, 42 to overtime) | held-out log loss: the judge 0.3781, one part 0.3785, the free network 0.3789, B2 0.3798, A 0.3920 (worse than the judge, 95% +0.003 .. +0.025), the pro table 0.4049; axioms hold; level 5:00: a 100-damage hit +12.6 points, a frag of a 20-hp enemy +7.6 (+9.2 with the weapons edit), a mega +9.9, a red armor +9.0, the LG +2.8; per save (60 games each) a hit +6 to +22, no trend; the weapons edit costs +0.0006 of log loss on all games ✅ |
| Axioms (by construction) | frag good, death bad (a kill always gains at least a quarter frag of value); damage dealt good, taken bad (a player's worth only rises with his own stack). Checked on 247,104 state changes ✅ |
| Overtime | its own short game: the period's clock (as the simulator's pay reads it); the regulation rows of games that went to overtime are not fitted |
| Ramp | `tools/run/ramp.py`, on the clock (RAMP_ALWAYS): `WIN_GAIN` sized from the run's own counters (updates 21 to 30, the judge's win part against the combat pay); step 1 with the critic's 10-update warm-up; then a step every 10 updates and 25 min: `WIN_W` 0.1 a step to 1, `FADE_V` from step 5 to 1 at step 12 ✅ |
| Code | `main` with branch `v061j` merged (WIN_JUDGE; off = v0.6.0's simulator to the bit) ✅ |
| Aim, mix, maps | as v0.6.0 (`!aim default`; 65% whole games / 35% the pros' mid-game starts; the ten maps) |
| League | v0.4.2b's end and v0.6.0's end as anchors, then his own new snapshots (none of the recovered files) |
| Checks | every 10 updates, 160 games against v0.6.0's end (every fourth against v0.4.2b's end); the behaviour panel. Under 40% flagged, under 30% posted. Never stopped automatically |
| Logged | self-play games of every 40th save (the judge's training data for v0.6.2) |
| Length | 24 hours (`--minutes 1440`; owner, 2026-10-28: start around 21:00, "let it run for 24 hours"). The fade: `WIN_GAIN` sized at updates 21-30 (~2 h), step 1 with the warm-up (~40 min), a step every 10 updates; win chance only from about update 150 (~10 h) |

## How it ended (2026-10-29)

| | |
|---|---|
| End | stopped by hand right after the save of update 340 (17:52; owner: "run goes until 6pm"), `keep/policy_end_v061.pt` + `opt_end_v061.pt`; v0.6.1b's start |
| Checks against v0.6.0's end | during the win pay's fade (updates 50-140) 622-498, 55.5%; win chance only (160-230) 400-400, 50.0%; during and after the level fade (250-320) 51.2 to 56.9% a check |
| The level fade (owner, 2026-10-29) | `LEVEL_PULL` 0.95 -> 1.0, 0.01 right after each save from 12:14 (update 250) to 14:39 (`tools/run/ramp_live.py`); the checks played each save at its own pull |
| The end against the save before the level fade (update 250, `keep/policy_prelevel_v061.pt`) | 160 games at each pull for both seats (`tools/run/compare_level.py`): at 1.0 68-92, **42.5%**; at 0.95 76-84, 47.5%; pooled 144-176, 45.0% (±5.5 points). The last 90 updates (the level fade and more win-only training together: not told apart) likely cost him a little, most without the pull |
| Kept | the save before the level fade as `keep/policy_prelevel_v061.pt` (= `keep/policy_250.pt`, no pull in its settings; its optimizer was not kept, only the end's), backed up to T:, the copies checked identical (sha256, first 16: `policy_end_v061.pt` 636c4ceaeabfeb93, `opt_end_v061.pt` 06f7901d80e9320e, `policy_prelevel_v061.pt` 58f7db344e01209c) (owner: "save the weights for the pre pull fade model so we can return if needed") |
| The owner's decision | "The pull needs to go"; v0.6.1b starts from v0.6.1's end (no pull) as planned: "I'm going to continue with the planned next iterations because I think they all work together to create something better at the end" |
| Behaviour over the run | a slower game (frags a match-minute 1.65 -> 1.42); the rail out of his hands (in hand 0.21 -> 0.13, shots 2.0 -> 1.0 a minute; accuracy flat); items held (megas 0.80, red armors 0.95 a player-minute) with no item pay; entropy 1.82 -> 1.91 |
| Play tests | 12:00 (save 240): Hektik 31-4 to the owner at `!aim better`; 19:30 (the end): Aerowalk 14-2 to the owner at `!aim better` (forfeit at 6.9 min); the owner: the end played weaker than the noon save, as the comparison found |

## The checklist

| | |
|---|---|
| Settings check | `train.cmd` against v0.6.0's `train.cmd`: only `--run`, `--minutes`, `WIN_JUDGE` differ ✅ (`start.ps1` refuses otherwise) |
| Identity | WIN_JUDGE off = v0.6.0's simulator to the bit: inputs, pay, round ends, events, counters; Blood Run and Aerowalk, the blend off and on (`tools/judge_ident.py ident`) ✅ |
| Parity | WIN_JUDGE on: the simulator's chance = the judge's on its own state every frame (0 difference), the win part zero-sum and = scale x the change (`tools/judge_ident.py judge`) ✅ |
| Acceptance of the fit | held-out log loss no worse than B2's interval and better than A; no axiom failure; the value table sensible (hits rise with damage, mega > red armor at low health); drift between saves within the intervals 🧪 |
| Hand-built / assumed parts | the shape "lead + stack edge in frags" (needed to prove the frag axiom); the armor rule (armor counts up to twice the health) and the split at 100 into lasting and decaying; a dead player counts as his respawn at once; the floor below a respawn (at most 0.5 frag for a low lasting part, 0.1 for the decaying part, 0.05 a weapon: together 0.75, which keeps a kill worth at least 0.25 frag); the ramp's schedule; **the rocket launcher's and the rail's worth set by hand to the lightning gun's** (his games priced them near 0: it pays taking them, not using them well; removed at v0.6.2's refit unless the owner says otherwise) |
| Weaknesses | weapons he rarely takes cannot show their worth (the rail: only exploration breaks the loop; refit per version); ammunition, weapon in hand, position and item timers are not in the judge (they pay only through what they lead to); self-play data only; with a 0.999 discount the judge is his goal over ~25 s |
| Pay pathologies (ledger) | a frag or damage dealt of the wrong sign: impossible by construction, checked on the grid ✅; late with a big lead the pay goes quiet (decided games). **Found 2026-10-29 (an audit), left in this run (owner): a game pays the judge's chance on its last frame, not its result** (at 0 s the judge's spread is 0.14 frags and the stacks still count): on this run's 250 self-play games 4.8% were off by more than 0.1, 0.14 of pay a game on average against 3.19 for a whole game, the worst 6.2 (a won game paid as a loss); it pulls a little toward stacking in a game's last seconds. Fixed for v0.6.2 (`WIN_END`) |
| Test on last night's 60 games | the judge (two parts) 0.4361 held-out log loss, one part 0.4365, B2 0.4360, the free network 0.4394, A 0.4796; axioms hold; the decaying part priced low (a mega at 100+50 +2.3 points at 5:00 level against a red armor's +8.9; wide intervals on 60 games) ✅ |

## Start (after v0.6.0 ends, on the owner's go)

1. `python tools/run/fit_b.py duel_gru_v0_6_0 --boot 30 --out data/sim_runs/judge/judge_v060.npz --json data/sim_runs/judge/judge_v060.json`: the report to the owner.
2. Merge `v061j` into `main`.
3. `powershell -ExecutionPolicy Bypass -File docs\runs\v0.6.1\start.ps1`

# v0.6.0 on one page: v0.5.0's setup from v0.4.2b's end, with Bobby's aim limits measured from the pros

*2026-10-27 (owner): "v0.5 is a failure, we move to v0.6". v0.5.0 and v0.5.1 never beat their start (v0.4.2b's end) in any
check; their aim limits of 2026-10-26 (one speed error, capped by the weapon in hand) are dropped. v0.6.0 = v0.5.0 (the
loophole fixes, etc.) with the new aim; ~6 h; then v0.6.1 = pay by win chance from its end.*

**Marks:** ✅ built and tested · ⏳ building · 🧪 to measure · ❓ owner's decision · ⏸ later

## Start

| | |
|---|---|
| Network | v0.4.2b's end (`duel_gru_v0_4_2/keep/policy_end_v042.pt` + optimizer) ✅ |
| Code | branch `aim2` (v0.5.1's code + the aim2 switches; the win-pay switches off) ✅ |
| Loophole fixes (v0.5.0's) | WEAPON_FREE, SPEED_LOS, GONE_BELIEF, TELEFRAG, JRUN_SPEED_BACK, SMALL_ZERO, damage taken weighed 1.0 ✅ |
| Aim | `!aim default` = the pros' mean, measured knob by knob from 100 demos a map ⏳ (being measured) |
| Pay | v0.5.0's: flat frag, damage and item pay (mega 0.35, red 0.30, yellow 0.15), speed pay 0.25; win chance recorded only |
| Mix | 65% whole games / 35% the pros' mid-game starts; no movement practice (owner) |
| Length | ~6 h (`--minutes 420`) |
| Run | `duel_gru_v0_6_0`; command `scratch/run_duel_gru_v0_6_0.cmd` (scratchpad v060/make_cmd_v060.py), folder made by prep_v060.py ✅ |
| Before the start | the owner's play test of v0.4.2b's end at the new `!aim default` (local server) ❓ |

## The aim knobs (fitted on the weapon whose style isolates them)

| Knob | Style | Measured on |
|---|---|---|
| Notice delay, surprise delay | flick | enemy appears → first aim movement |
| Tracking delay, focus, slip error | tracking | LG: error by crossing speed, around reversals |
| Eccentricity error | flick | rail: error at the shot by flick angle |
| Velocity read, distance read | prediction | rockets: lead error along / across, by distance |
| Sight error, hand noise, flinch | shared | still targets; after taking damage |
| Hand smoothing | — | as trained (a change needs retraining) |

Levels: `default` = pro mean, `better` ≈ p90, `worse` ≈ p25, `max` = limits off (hands as trained). Plasma, MG and SG are checks.

## Open

| | |
|---|---|
| Opening | the new aim all at once (the run's purpose is to adapt to it) or eased in from v0.4.2b's old aim over ~2 h ❓ |
| Checks | every 20 updates against v0.4.2b's end, each seat at its own aim (new) or both at the new default ❓; the behaviour panel |
| Stop | only a collapse ❓ |

## Logged for v0.6.1

| | |
|---|---|
| Recorded, not paid | the win part's size (the win pay's gain), pay by term (the ledger), what win pay would have paid, his own win sense |
| In the last 2 h | the v0.6.1 calibration from v0.6.0's play: gain, ledger, stack-term refit, close-game baselines |

## Then

v0.6.1 (branch `v061`, `docs/v0.6.1/WINPAY_v0.6.1.md` there): v0.5.1's win-chance fade (25-min steps) from v0.6.0's end, with the potential shaping
and the critic warm-up.

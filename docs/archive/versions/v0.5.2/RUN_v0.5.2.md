# v0.5.2 on one page: the new human aim model, calibrated to the pros by weapon style

*2026-10-27 (owner): v0.5.1 finishes the fade to pay by win chance; then this run replaces the aim limits of 2026-10-26 (one
error by the target's speed across the world, capped by the weapon in hand: rail 0.001°, everything else 1.5°) with a model
of the eyes and hands that does not know the weapon. The owner: "I'm not convinced our approach yesterday to aim smoothing was
the right one"; "LG is tracking, rail is flicking, rockets are predictions. Plasma is a hybrid of predicting and tracking, SG is
a close range flick, mg/hmg is tracking with spread"; "when in doubt, calibrate based on the pros. Their measures should be the
benchmark for `default`". The limits as they are: [AIM_LIMITS.md](../v0.5.1/AIM_LIMITS.md); the model and its calibration:
`AIM_MODEL.md` in this folder (being written). Then [v0.5.3](../v0.5.3/RUN_v0.5.3.md): the strategy head.*

**Marks:** ✅ built and tested · ⏳ building · 🧪 to measure · ❓ owner's decision · ⏸ later

## Start

| | |
|---|---|
| Network | v0.5.1's end (`keep/policy_end_v051.pt` + optimizer), on pay by win chance only ⏳ (v0.5.1's fade ends ~03:00-04:00 Wed) |
| Code | branch `aim2` (from v051): the new model as switches, all off = v0.5.1's simulator bit for bit (`tools/aim2_ident.py`) ✅ |
| Pay | win chance only, unchanged (v0.5.1's end state) |
| Mix | as v0.5.1: 67% whole games / 33% the pros' mid-game starts, no movement practice |
| When | Wed ~noon (after ~8 h of win-chance pay alone) through Thu morning ❓ |

## The new model (one new thing, opened in two phases)

| Part | Now (v0.5.1) | v0.5.2 | Mostly governs |
|---|---|---|---|
| Fast-target error | by the target's speed across the world, cap by weapon (rail 0.001°, else 1.5°) | **retinal slip**: the target's motion against his own view's, as of his delay; **eccentricity**: the angle off his crosshair. No weapon in it | slip: tracking (LG, MG, plasma); eccentricity: flicks (rail, SG) |
| Where the error goes | his whole picture of the enemy (map memory, the brain, the rocket floor point) | the crosshair-to-target angles and the lead's last offset only; his map memory gets the delay and the judged range and speed | predictions (RL, plasma) and the brain |
| Focus | cuts his tracking delay 100 → 50 ms for 2 s of sight | keeps the delay; sharpens his sight instead | reversals in tracking |
| Flinch | 0.25°/damage, up to 6°, 0.5 s; impulse and sustained together | recalibrated to the pros' dip in the half second after a hit; sustained only | every weapon |
| Zoom | shrinks the base sight error only | shrinks every part of it | zoomed MG, LG, rail |
| Hand smoothing | view inertia 0.75 ahead of the 4 Hz hand filter | 🧪 measured: is it filtered twice? A change there is his hands (retraining): its own later step if so | flicks |

## Calibration (the pros are `default`)

| | |
|---|---|
| Data | the tournament demos 2010-2016 (6,624 duels, ~1,029 h, `T:\quake-demos\trance\by_map`) and the pro sets ⏳ |
| By style | LG and MG: accuracy by the target's speed and around strafe reversals; rail and SG: flick time and accuracy by flick angle; RL: hit and splash by distance and target speed, the lead's miss along and across the motion; plasma: both; every weapon: the dip after taking damage ⏳ |
| Levels | `default` = the pros' average per style; `worse` 25-50% below a pro; `better` ~25% above or the top of the pros' spread; `max` = every perception and reaction limit the server can turn off, the hands as trained (owner) ⏳ |
| Owner's check | play test of v0.4.2b's end under the new levels (the play build `play-aim2`, the mind view with his win chance) ❓ |

## Opening

| Phase | What | How |
|---|---|---|
| A | the world picture apart from the aim error; the code defaults = `!aim default` | at once at the start (it changes what his memory and the brain see, not how well he aims); 10-20 updates |
| B | old error model → new: the weapon caps out; slip, eccentricity, focus as sharpness, the new flinch, zoom in | a blend of the two in ~5 steps of 40-50 min, each panel-gated like v0.5.1's fade |
| Before the start | the 10-update dry run on a scratch copy + a check + the panel (standing rule); the server's inputs against the simulator's with the new model on | ⏳ |

## Checks and panel

| | |
|---|---|
| Control | v0.4.2b's end, fixed; each seat on its own aim settings from its checkpoint (new at this boundary: numbers not comparable with earlier checks) |
| Reference | v0.5.1's end |
| Panel | v0.5.1's, plus aim by style beside the pros: hit rates by weapon, rail flick times, LG around reversals, the rocket lead's miss |
| Stop | only a collapse (owner: a check under 15% or two in a row under 25%); a dip while he relearns his aim is expected |

## After

| | |
|---|---|
| v0.5.3 | the strategy head, then the item rule's fade ([RUN_v0.5.3.md](../v0.5.3/RUN_v0.5.3.md)) |
| Public servers | if v0.5.2 beats the control: one deploy with the v0.5.x network, the new `!aim` levels, the flinch fix (the opponent's hits only) and Bobby added at a map's load ❓ |

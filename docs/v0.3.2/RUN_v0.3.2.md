# v0.3.2 and v0.3.3 on one page

*Written 2026-10-18 after the runs, from the run folders and [../v0.4/MOVEMENT_STATUS.md](../v0.4/MOVEMENT_STATUS.md). The
plan they serve: one movement network ([../v0.4/UNIFIED_MOVEMENT.md](../v0.4/UNIFIED_MOVEMENT.md), B-259). Folders
`duel_gru_v0_3_2`, `duel_gru_v0_3_3`. Status: **both over**; neither went on a server.*

## v0.3.2: step 1, the turn correction (Fri 2026-10-16 20:56 to Sat 07:25, 140 updates)

**What changed from v0.3.1:** while his legs drive, his own network adds to the legs' left-right turn (`LEGS_TURN_ADD`,
up to ±15° a frame, opened from zero). The look-aware legs (`LEGS_LOOK`, `move_v17_look`) were built for it but did not
learn to look in their own training, so v0.3.1's legs were kept, with the look inputs at zero. Pay, rounds and aim level 3
as in v0.3.1. The control: v0.3.1's end.

**Checks against v0.3.1's end** (160 ten-minute games, ten maps): 49.0, 49.7, 49.8, 50.3, 50.6, 49.9, 50.1, 49.8, 48.8, 46.6,
51.1%: level.

**What it showed:** given the turn, he leaned on his legs **more** (63% of game time against 54%) and gave the correction
back (used on 3.8% of legs frames at the end, about 10% when its opening ended; 3.7° on average). Walking stayed at 0%. Step
1 alone does not end the "moving mode". Its update-140 save (`keep/policy_switch.pt`) is where v0.3.3 and v0.3.4 began.

## v0.3.3: steps 2 and 3 (Sat 07:27, stopped after 5 updates)

Key overrides (`LEGS_KEYS_ADD`: he takes back one control at a time) and the legs' layer into his memory (`--legs-feat`),
from v0.3.2's update 140. Stopped after five updates for v0.3.4, which took step 3 and the blend instead; the key overrides
were never used again (they leave in step 6b). No check was made. Nothing to read from it.

## Next

v0.3.4: [../v0.3.4/RUN_v0.3.4.md](../v0.3.4/RUN_v0.3.4.md).

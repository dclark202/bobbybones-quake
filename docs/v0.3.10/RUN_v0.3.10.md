# v0.3.10 on one page: what changes from v0.3.9

*Approved by the owner, 2026-10-22. **Schedule (owner, ~09:20):** v0.3.9 ends at noon ("It's a success, and we'll build ON IT"); v0.3.10 starts at noon from v0.3.9's noon save (optimizer kept, staggered starts) and runs 6–8 hours to see whether the look-back pay helps; meanwhile v0.3.11 (the knowledge pay) is built; if the look-back pay helps, v0.3.11 starts overnight from v0.3.10, watched; if v0.3.11 flops, back to v0.3.10 in the morning. Code: branch `v0310` (`9bb8f8a`).**16:00 Fri 2026-10-23** (owner, 2026-10-22); the LG cost watched for the first ~5 hours with the owner before it runs overnight.*

**Marks:** ✅ built and proven identical with its switch off · ⏳ to build · 🧪 measured · ❓ owner's decision · ⏸ not in v0.3.10

## Where v0.3.9 stands (update 194, 07:47 Thu)

| | v0.3.9 |
|---|---|
| Against v0.3.8's end (aim 4; v0.3.8 at its 125 ms) | 64.5% (u10) → 71.9% (u140, u180) |
| Same, both at 100/160 ms (u160) | 65.2% (124–31) |
| Against v0.3.1's end | 89.1% (u40) → 92.7% (u160), 160–0 |
| Pre-aim at a fresh sighting: within 15°; q | 16% → 21%; 0.32 → 0.38 (pros 58%; 0.68) |
| Rail: frags; shots a minute | 3.9% → 9.7%; 0.45 → 0.93 (hit rate near 48% → 57%) |
| Jump presses a minute; speed unseen | 57 → 43; 335 → 329 (jump cost off since 07:22, presses flat) |
| Weapon in hand travelling, enemy unseen: LG / RL | 55% / 21% (pros 14% / 59%); humming weapon ~60% at every band (pros 28% → 9%) |

## 1. The lightning gun out of contact (the owner, 2026-10-22: "small noise pay for LG ... monitor over the first few hours and adjust if needed")

| Change | Detail | State |
|---|---|---|
| ~~LG noise cost~~ (`LG_QUIET_COST=0`: **left out**, the owner: "it's a bandaid, not a principled approach"; the knowledge pay of v0.3.11 is to teach it) — as built: | While his lightning gun is in hand, he is alive, and **by his own senses** the enemy is away: not in view for 3 s or more and nothing of him heard in the last 2 s. Ramps with the quiet time: 0 at 3 s → full at 10 s; full = 0.004 a second (0.24 a minute; a frag is 1). Games and pro starts only (not jump practice). At today's 55% LG carrying out of contact: about 0.08–0.12 a minute. Escape: switch to rockets or rail while it is quiet (switching takes time: not at contact) | ✅ |
| Equilibrium | rockets or rail carried between fights, the LG brought out when a close fight is heard or expected; the enemy's sounds become worth more. Goals: weapon use, counterplay | – |
| **His own LG muffles his hearing** (`LG_DEAF=1`, a PLAY_VAR: the plugins too) | From the game's sound files (scratchpad `lghum/REPORT.md`): with the LG out (not firing) footsteps heard to 700 u (now 800), the enemy's LG hum not heard, +8° direction and +0.1 distance error on muffled footsteps; firing the LG: footsteps 500, other sounds 1,000. Small and realistic; the pros showed no measurable muffling | ✅ |
| Watched, first ~5 hours with the owner | LG / RL share travelling unseen (target direction: pros 14% / 59%); weapon switches in the 2 s before contact (late switches); checks against v0.3.9's end. Proposed adjustments (live, on the owner's yes): cost ×2 if LG carrying has not moved; halved if the check drops or late switches climb | ❓ |

## 2. Watching the opening: back pay (the owner: "back pay for 'having been looking in the right direction prior to enemy seen'. This is the first step into resurrecting the 'pay for knowing where the enemy is'")

| Change | Detail | State |
|---|---|---|
| **Look-back pay** (`WATCH_PAY=0.03`, live) | At each fresh sighting (the same event as the pre-aim pay: line of sight opens after 1 s+ closed, both alive, no respawn or teleport in the last 1 s; games and pro starts), look back over the previous **1.5 s**: for each frame he was alive and the enemy hidden, how close his view was to the spot the enemy came out at (the enemy's chest at the sighting, seen from where he stood then): w = 1 at 0°, falling to 0 at 45°. His score = the average over the window, later frames weighted more (weights rising linearly from 0.5 to 1). Zero-sum like the pre-aim pay: the better watcher of the two gets 0.03 × (the difference), the other loses as much. Paid once at the sighting; the learning carries it back to the turns that earned it | ✅ |
| Why zero-sum | self-play stays balanced: watching an opening pays only if the enemy watched his worse, and the enemy learns to come from openings that are not watched (counterplay) | – |
| Fairness | the pay reads the truth (where the enemy came out); his inputs stay what he perceives | – |
| Size | at ~10 sightings a minute, at most ~0.3 a minute, typically far less: smaller than the pre-aim pay (0.05) | ❓ |
| Counter | the look-back score by weapon, in metrics and on the watcher's line, beside the pre-aim numbers | ✅ |

## 3. Recommended beside them

| Change | Why | State |
|---|---|---|
| **Fair checks**: every old network in the checks plays at aim 4's delays (100/160 ms), like him (the owner, 2026-10-22: "we should do it by promoting the old networks to the level 4 aim"; replaces the rule of 2026-10-20) | the overnight checks gave v0.3.9 a reaction-time edge: 71.9% at unequal delays, 65.2% equal | ✅ decided |
| Everything else as v0.3.9 | pre-aim pay 0.05, aim 4, hop and chain pays off, no jump cost, rail streak off, staggered starts, the safe restart | – |
| Not yet: the enemy-tracking lesson (`strength` and the guessing game into his memory) | one step at a time: the look-back pay first, then the tracking lesson in v0.3.11 if it helps | ⏸ |
| Not yet: a mix of aim levels | still waiting for pre-aiming to settle | ⏸ |
| Front/back hearing: not needed (the owner: "Quake live has doppler sound, you can hear coming/going") | – | ✖ dropped |

## 4. Before the start

Build both pays and LG_DEAF on `v0310` with every switch off identical to v0.3.9; unit checks of both pays (constructed angles,
zero-sum); the plugins' LG_DEAF; the new lessons' gate: a check at update 10 against v0.3.9's end.

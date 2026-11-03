# v0.3.10 on one page: what changes from v0.3.9

*Agreed with the owner, 2026-10-22 morning. Folder `duel_gru_v0_3_10`, from v0.3.9's last save (v0.3.9 stopped early, ~09:40:
"It's a success, and we'll build ON IT"), optimizer kept, staggered starts. Code: branch `v0310` (`9bb8f8a`, worktree `ql-bot-v0310`).*

**Plan for the day (the owner, ~09:20):** v0.3.10 runs **6–8 hours** to see whether the look-back pay helps; v0.3.11 (the knowledge
pay, [RUN_v0.3.11.md](../v0.3.11/RUN_v0.3.11.md)) is built meanwhile; **this evening** the owner decides: if the look-back pay is
helping, v0.3.11 starts overnight from v0.3.10, watched (its gate and any automatic fallback reviewed with the owner tonight); if not,
v0.3.10 goes on. If v0.3.11 flops: back to v0.3.10 in the morning.

**Marks:** ✅ built and proven identical with its switch off · 🧪 measured · ❓ owner's decision · ✖ left out · ⏸ later

## Where v0.3.9 ended (update ~225, 09:25 Thu)

| | v0.3.9 |
|---|---|
| Against v0.3.8's end, both at aim 4's delays (u160) | **65.2%** (124–31) |
| Against v0.3.8's end, v0.3.8 at its 125 ms | 64.5% (u10) → 71.9% (u140–180) |
| Against v0.3.1's end | 89% (u40) → 92.7% (u160–200), 160–0 |
| Pre-aim at a fresh sighting: within 15°; score q | 16% → 20%; 0.32 → 0.37 (pros 58%; 0.68) |
| Rail: share of frags; shots a minute; hit rate near | 3.9% → 9.5%; 0.45 → 0.98; 48% → 59% |
| Jump presses a minute; speed unseen | 57 → 43; 335 → 330 (jump cost off since 07:22, presses flat after) |
| Weapon in hand travelling, enemy unseen: LG / RL | 55% / 21% (pros 14% / 59%) |

## 1. Watching the opening: the look-back pay (the owner: "back pay for 'having been looking in the right direction prior to enemy seen'. This is the first step into resurrecting the 'pay for knowing where the enemy is'")

| Change | Detail | State |
|---|---|---|
| **Look-back pay** (`WATCH_PAY=0.03`, live) | At each fresh sighting (the pre-aim pay's event: the line of sight opens after 1 s+ closed, both alive, no respawn or teleport in the last 1 s; games and pro starts), look back over the previous **1.5 s**: for each frame he was alive and the enemy hidden, how close his view was to the spot the enemy came out at (the enemy's chest at the sighting, seen from where he stood then): 1 at 0°, falling to 0 at 45°; the average over the window, later frames weighted more (0.5 → 1). Zero-sum: the better watcher of the two gets 0.03 × (the difference), the other loses as much. Paid once at the sighting | ✅ |
| Equilibrium | watching an opening pays only if the enemy watched his worse; the enemy learns to come out of openings that aren't watched (counterplay) | – |
| Fairness | the pay reads the truth (where the enemy came out); his inputs stay what he perceives | – |
| Size | ~10 sightings a minute: at most ~0.3 a minute, typically far less (the pre-aim pay is 0.05 a sighting) | – |
| Counter | the look-back score by weapon on every save line, beside the pre-aim numbers | ✅ |

## 2. The lightning gun

| Change | Detail | State |
|---|---|---|
| **His own LG muffles his hearing** (`LG_DEAF=1`, a PLAY_VAR: the plugins too) | Only what the game's sound engine supports (scratchpad `lghum/REPORT.md`): with the LG out (not firing) enemy footsteps heard within 700 u (was 800), the enemy's LG hum not heard, +8° direction and +0.1 distance error on muffled footsteps; firing the LG: footsteps within 500 u, other sounds within 1,000 u. Rail left out (the owner: "until we see overuse of rail emerge") | ✅ |
| LG noise cost | **left out** (the owner: "it's a bandaid, not a principled approach"); built behind `LG_QUIET_COST` (0 in the run). The knowledge pay of v0.3.11 is to teach the quiet weapon between fights | ✖ |
| Measured | LG / RL / RG in hand out of contact (pros 14% / 59% / 13%) on every save line | ✅ |

## 3. Checks (fair: every old network plays at aim 4's 100/160 ms, like him; the owner: "promoting the old networks to the level 4 aim")

| When | Against |
|---|---|
| Update 10 (the look-back pay's gate) | v0.3.9's end |
| Every 20 from update 20 | v0.3.9's end and **the control, v0.3.6's end** (the public server's network) in turn; v0.3.1 retired at 92.7% (the owner) |

## 4. How "helping" will be read this evening

There is no copy of v0.3.10 without the look-back pay (one run at a time), so the evidence is: the look-back score rising; pre-aim
climbing faster than in v0.3.9 (+0.05 in q over its first 170 updates); the fair checks against v0.3.9's end above 50%. Strong
evidence, not proof.

## 5. Everything else as v0.3.9

Pre-aim pay 0.05; aim 4 in training; hop and chain-hop pays off, no jump cost; rail streak pay off (the other rail pays kept);
staggered starts; the safe restart (each use on the owner's yes); jump practice as of 2026-10-21; shares 70 / 20 / 10; hearing level B;
item pay 0.30 / 0.30 / 0.15. Front/back hearing: not needed (the owner: "Quake live has doppler sound"). Later: a mix of aim levels.

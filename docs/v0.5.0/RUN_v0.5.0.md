# v0.5.0 on one page: back to v0.4.2b, the loopholes closed, one aim setting

*2026-10-26 (owner): v0.4.3 and v0.4.4 are scrapped ("too many dead ends and weird behavior I don't want to carry forward"). On a
local server v0.4.4 looped one item and the weapon beside it (Hektik: 7 megas, 31 lightning-gun pickups in 4.9 minutes) and never
went for the player; v0.4.2b's end does not. The simulator does it too (the same save in self-play: lightning gun as target 82%,
47% of the time within 300 u of its spawn). The checks had not seen it: they played each save against the previous one and
counted intentions over every kind of round. v0.5.0 is one phase: v0.4.2b's end, every loophole found closed, `!aim default`,
the owner's mix; at least 6 hours, maybe overnight. Then [v0.5.1](../v0.5.1/RUN_v0.5.1.md): pay by win chance only; then [v0.5.2](../v0.5.2/RUN_v0.5.2.md): the head, then the item rule's fade.*

**Marks:** ✅ built and tested · ⏳ building · 🧪 to measure · ❓ owner's decision · ⏸ later

## Start

| | |
|---|---|
| Network | v0.4.2b's end (`duel_gru_v0_4_2/keep/policy_end_v042.pt` + optimizer): the old belief faded out (1.0), the brain taught on people's games (share 0.35). Also the fixed control of every check |
| Code | branch `v050` (v0.4.4's code + the fixes below; every newer switch off: generated starts, item floor, targeted item runs; **no strategy head**: it is attached shut at v0.5.1's start). The command: `scratch/run_duel_gru_v0_5_0.cmd`, made from v0.4.2b's own by `make_cmd.py` (scratchpad v050), every change listed in its head |
| Before the start | the dry run: the exact command on a scratch folder for 10 updates, then the update-10 check against v0.4.2b's end and the behaviour panel (the standing new-setup rule) ⏳; the panel's proof (v0.4.1's end green, v0.4.4's u221 red) ⏳ |
| Not carried over | generated mid-game starts; the item floor and targeted item runs; the equal big-weapon pickup pay (owner: it did nothing); rocket-jump runs (none in this phase) |
| Run | `duel_gru_v0_5_0`; ≥ 6 h (owner), overnight if it keeps improving; end kept as `keep/policy_end_v050.pt` + optimizer |

## Mix and practice

| | |
|---|---|
| Mix of all training | **60% whole ten-minute games / 30% the pros' mid-game starts / 10% movement** (item runs and jump runs) |
| Jump practice focus | Campgrounds' bridge-to-rail (b2r, with the pros' run-ups, 108 makes) and Aerowalk's red armor jump, at most 4× the others |
| Shadow readouts | the win value and "in control": recorded, no effect on play |
| The item rule | **on** (his guide to which item; faded in v0.5.1 after the head is open) |

## The fixes (each a switch; off is v0.4.4's simulator bit for bit)

| Fix | What | Equilibrium / why | State |
|---|---|---|---|
| `WEAPON_FREE` | taking the weapon he chose ends the choice; a weapon he holds with a pickup's worth of ammunition is no target | a weapon spawn is no longer a free "hold here" order; going for a weapon he lacks or that is low stays | ✅ built, off = identical; 🧪 test on v0.4.4's u211 (does the camping stop) |
| `SPEED_LOS` | the speed pay only while the enemy is out of his line of sight (was: out of his view cone) | no pay for facing away from the enemy. The speed pay itself fades out before v0.5.1's head opens (it bribes the choice of target) | ⏳ built, testing |
| `--dmg-taken-w 1.0` | damage taken costs as much as damage dealt pays (was 0.75) | damage zero-sum: only out-damaging the enemy pays (an even trade paid both 0.14) | trainer setting |
| `GONE_BELIEF` | a held choice let go early only when he *knows* its item is gone (was: the truth) | no free probe of item clocks out of his sight; simulator and plugin alike | ⏳ built, testing |
| `TELEFRAG` | a teleport onto the other player kills him, as in the game | standing on a teleporter exit is no longer safe | ⏳ built, testing |
| `JRUN_SPEED_BACK` | a failed jump-practice try gives back its speed pay too | practice pays making the jump, not the run-up | ⏳ built, testing |
| `SMALL_ZERO` | the knowledge pay and the big weapons' pay by order zero-sum | no pay both sides collect | ⏳ built, testing |
| Weapon re-pick ammo | measured in the game (private server, a live duel on Blood Run, 100 cases): a weapon pickup always adds a full weapon load (lightning +100, rockets and rail +10) up to the cap (150 / 25 / 25), taken even at full; an ammo box +50 / +5, not taken at the cap; weapons back in 5 s, boxes in 40 s | the simulator already matches on every point (owner: "Whatever it is in quake live is correct") | ✅ no change |
| Grenade, plasma, blind rocket fire free | left as is (owner) | – | – |

## One aim setting (`!aim`) ✅ (owner, 2026-10-26)

| `!aim` | Tracking / notice delay | Sight error | Hand noise | Fast-target | Rail cap | LG cap | Use |
|---|---|---|---|---|---|---|---|
| `worse` | 150 / 300 ms | 1° | 0.15 | 0.125 | 5° | 15° | an easier opponent |
| **`default`** | **100 / 200 ms** (level 3) | **0.6°** | **0.10** | **0.075** | **3°** | **10°** | **always trained on; the servers' default** |
| `better` | 75 / 150 ms | 0.3° | 0.075 | 0.05 | 2° | 5° | a harder opponent |
| `max` | 25 / 25 ms | 0 | 0 | 0 | 0 | 0 | every human limit off |

*Table of 2026-10-26 evening (owner: "I want the worse and better to really stand out"). The cap by weapon (rail / lightning,
`PERCEPT_SPEED_MAX_RG` / `_LG`, live; other weapons 5° at default) came after the review: one cap of 5° moved both together
(lightning 37.4%, rail 38.2%). Calibration, v0.4.2b's end against itself, 8 maps x 8 games: rail 3° / LG 5°: 37.3 / 43.8;
3 / 8: 34.3 / 41.9; 3 / 12: 34.0 / 45.0; 2.5 / 10: 34.5 / 44.6 (the pros 32.7 / 43.5). In the run from update 30 (a restart
at the save, optimizer kept, code `v050aim` 33804d3), ramped 4/6.5 -> 3/8 -> 3/10 (18:34 to 19:24). Not in the table and
scaled with it in the play files: MOTOR_BASE with the hand noise, SURPRISE_MS with the delays, the other weapons' cap with
the rail's; the flinch stays the default's. Local play build: worktree `ql-bot-v042aim` (v0.4.2b's end, port 27975).*

| Calibration (v0.4.2b's end against itself, 8 maps x 8 games) | lightning | rail | rockets |
|---|---|---|---|
| the pros (4,166 demos; a rocket's hit with splash) | 32.7% | 43.5% | 31.2% (72% under 250 u, 45% to 500) |
| level 4, no limit (how v0.4.x trained) | 50.8% | 58.8% | 49.2% |
| level 3, no limit | 49.8% | 58.4% | 48.3% |
| level 3, 0.075, cap 3° | 40.0% | 43.0% | 51.4% |
| **level 3, 0.075, cap 5° (default; owner: "split the difference")** | **37.4%** | **38.2%** | **52.4%** |
| level 3, 0.1, cap 8° | 33.3% | 35.5% | 53.6% |

The limit moves lightning and rail together; the pros' rail-lightning gap is wider than the simulator's (a rail-only lever is a
later item). His lightning reads high partly because he fights in the open more than the pros (owner). Rockets read high
overall because he fires them close. `!aim 1..5` and the separate calibration are replaced; the plugin change ships with the
first deploy (owner's call); `better` and `worse` are measured before it.

| Ramp (owner: "ramp it in but don't hold back on checks") | PERCEPT_SPEED 0 → 0.025 → 0.05 → 0.075, one step every 30 minutes by time (`ramp_aim50.py`); level 3's delays and the cap 5° from the start |
|---|---|

## Checks (every 20 updates, 160 ten-minute games) and the behaviour panel

| | |
|---|---|
| Control | **v0.4.2b's end, fixed**, both seats at `!aim default`; every 4th check v0.3.10's end |
| Games | (owner, 2026-10-26 evening: "not concerned with the win rate ... it's more about how it feels to play against him") overnight he trains on; stopped only on a collapse: a check under 15% or two in a row under 25% (scratchpad v050/guard_v050.py) |
| Targets | his held target per map, whole games only, the frames it is read: red at ~2× v0.4.2b's share for any one target |
| Camping | time within 300 u of each item and weapon spawn per map; weapon pickups a minute and re-picks of an owned weapon: red at ~2× v0.4.2b's |
| Roaming | map cells a minute (256-unit), median speed: red at −15% |
| Hunting | against the scripted watcher (a player holding a spot): frags a minute, time to the first sighting, share in view: red at −25% |
| Weapons | in hand per map against the pros; hit rates against the pros' averages |
| Items | mega, red and yellow armor shares: red at −15% |
| Pay | each pay term a minute; any shaping term growing toward the frag pay flagged |
| Health | kl, entropy per output, aim error, stalls, saves |
| Proof first | the panel on today's saves: v0.4.2b's end green, v0.4.4's u211 red ⏳ |
| Owner | a local game at the end (the self-play checks cannot see what a person sees); the server-vs-simulator input check before any play build |

## Numbers so far (simulator; the behaviour study of 2026-10-26)

| | v0.4.1 end | v0.4.2b end | v0.4.4 u211 |
|---|---|---|---|
| target lightning gun (self-play, held) | 9% | 8% | 82% (Blood Run) |
| time within 300 u of the lightning gun's spawn (Blood Run) | | | 47% |
| frags a minute against the watcher | 0.45 | 0.44 | 🧪 |
| mega / red armor share against the watcher | 0.89 / 0.54 | 0.86 / 0.46 | 🧪 |
| 🧪 v0.4.2b against v0.4.1 (160 games, with and without the aim fix) | running | | |

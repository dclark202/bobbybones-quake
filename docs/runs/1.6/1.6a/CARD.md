# 1.6a: the item teacher and the speed pay out, from 1.5a's end

*2026-11-04 evening (owner): "Before anything is faded out, let us introduce having the head contribute to weapon choices. That way we can
then fade it out concurrently (or in succession) with the hard coded teacher, and other fades in 1.4b/c." The plan, agreed in the review
of 11-04 night (owner): "The first 40 updates can take the teacher and speed pay out. That's easy"; then, on the order of 1.6 and 1.7:
"1.6 could be turned into a very short run to just do the first 40 updates part that we planned. 1.7 then becomes an expansion of the
lock + decision choice"; "1.6 is 80 updates, fade is the first 40 then a hold after that. 1.6 is settled and it can easily be run once 1.5
is done." The lock's hand-over moved to [1.7](../../1.7/README.md). Starts from [1.5a](../../1.5/1.5a/CARD.md)'s end, if it passes. The
family: [README](../README.md). **Running since 2026-11-05 07:22.***

**Marks:** ✅ known or decided · ⏳ to build · 🧪 to measure · ❓ owner's decision

## In short

| Updates | What | Dial |
|---|---|---|
| 0 | 1.5a's end with its optimizer: nothing new in the network | |
| 0 to 40 | **the item teacher and the speed pay out, together** ✅ (owner) | live `INTENT_TEACH_W` 1 → 0 (the lesson's weight 0.1 → 0: below); live `SPEED_PAY` 0.125 → 0 (its take-back on a trip given up goes with it) |
| 10 | the extra check (the trial: no dry run) | |
| 40 to 80 | **held** ✅ (owner): both at 0; the watch for 1.4b's slow drift (big weapons owned kept falling 20 updates after its fade ended) | |
| Length | ✅ 80 updates (owner): about 7 hours at 1.5a's 5.0 minutes an update (`--minutes` about 420, the run ends at the first save from update 80) | |
| League | ✅ (owner, 11-05) as in 1.5a: no matchmaking by difficulty (no `--pfsp`), the habit seats kept (`HABIT_P` 0.3) | |
| 0 on, for good | **no cost for firing at all** ✅ (owner, 11-04 night: "there should be no cost for firing AT ALL ... Make sure it's out fully in 1.6 and leave it that way"): every firing cost at zero at its source, and the start refuses any that is not (below) | |

Already out since 1.5a's update 0: the switch cost, the weapon override, the blind-fire cost. From update 40 nothing pays for his target
itself: the speed pay was the last pay tied to it.

## No cost for firing ✅

Every firing cost is already zero in 1.5a (checked 11-04 night in its command, its live settings and its pay record: the shot cost 0.0
a player-minute). 1.6a makes it so at the source and keeps it so:

| Cost | In the simulator | In 1.5a | In 1.6a and after |
|---|---|---|---|
| The shot's price (ammunition scarce) | `SHOT_COST` × `SHOT_W` × the map's scarcity × `COST_FIRE_W` | `SHOT_COST` 0.10 × live `COST_FIRE_W` 0 = 0 | `SHOT_COST=0` in the command |
| A far rail shot's price | `RG_FAR_PRICE` × `COST_FIRE_W` | 0 | 0 |
| Pressing and releasing fire | `FIRE_TOGGLE_COST` (0.003) × `COST_FIRE_W` | × 0 = 0 | `COST_FIRE_W` 0, checked |
| A weapon switch | `SWITCH_COST` (0.02) × `COST_FIRE_W` | × 0 = 0 | `COST_FIRE_W` 0, checked |
| Fire with no enemy seen or heard | `BLIND_FIRE_COST` (0.003) × `BLIND_FIRE_W` | `BLIND_FIRE_W=0` | 0 |
| A blind rocket the rule calls "nonsense" | `BLIND_RL_DMG` (6 points by default) | `BLIND_RL_DMG=0` | 0 |

**Kept so:** `start.ps1` refuses a start with any of them above zero (the command and `live.json`), the ramp never touches them, and the
checks read the record's firing terms (`shot_cost_per_player_min` and the ledger's terms by kind) at zero every update. What remains is
the game's own: ammunition runs out, splash hurts him, a reload and a switch take their time.

## Why these two, and why first

| | |
|---|---|
| The item teacher is weak | its weight is at its floor: `--intent-teach 9.13` faded long ago to `--intent-teach-floor 0.1`; `INTENT_TEACH_W` is a factor on it. It teaches the hands' target rows only (the teachers judge the hands' part alone, `pi_t`; 0.05 into the shared layers). His targets that name the rule's item (`intent_rule_agree`, recorded whatever the weight): 1.3b u10 → u178, teacher on throughout, 74% → 48%; 1.4b's fade u10 → u113, 49% → 45%. The rail as his target: 1.3b 3.1% → 1.4%, teacher on. 1.4b's drift looks like 1.3b's trend carrying on, not the fade |
| 1.4b's drift had other changes in it | matchmaking by difficulty (u0 to 10), the switch cost, the weapon override and the blind-fire cost out (u0), the speed pay out (u70 to 90, when ownership "kept falling after the fade"). 1.5a has the three u0 removals with the teacher on: its end, not 1.4b's 1.78, is the baseline for big weapons owned |
| **The speed pay prices re-deciding** | a trip given up gives its speed pay back (`sim/duel_env.py:13017`; games with nobody seen for 1.5 s): −0.07 to −0.08 a player-minute in 1.4b, about a fifth of the speed pay, out of contact only. Out before 1.7 hands his target to a learnt choice, so that nothing pays for keeping a plan |
| The speed pay out cost no speed (1.4b) | trip speed 340 at u70 → 336 to 338 after u90; 50 to 52% of trip time over 320 |
| No new code | both dials are live already (1.4b's ramp ran them); the run can start as soon as 1.5a is done, while 1.7's code is built |

## What 1.6a leaves open for 1.7

1.7 overhauls the lock and makes fighting the head's plan: chase, cut off, hold an angle, spam a chokepoint, items by a way chosen for
where the enemy is expected ([the 1.7 card](../../1.7/README.md)). 1.6a adds no cost, rule or lesson on a hold, a wait or a shot at an
unseen enemy, and every shot is free with every weapon (above): spam is judged only by what it leads to. The pre-aim and watch pays stay
on (`PREAIM_PAY` 0.05, `WATCH_PAY` 0.03).

**Recorded in 1.6a as 1.7's baseline:**

| | |
|---|---|
| Hunts | the enemy's share of his targets, how long a hunt lasts and how it ends (sight, given up, re-decided), the frags after a hunt |
| Holds | his time at holding places, how long he stays, the rail in hand there, frags from there |
| Shots at an unseen enemy, by weapon | grenades, plasma, rockets, lightning, rail: how often, where (a doorway, a teleporter exit, the pros' places), their damage |
| **Contacts on an item plan** (owner, 11-04: "I can still tell that I am disrupting some sort of plan he has to get items") | the share of contacts in which his target stays an item, and the damage and frags each side makes in them |

## Before the start ⏳

| | |
|---|---|
| 1.5a's end and its report | ✅ the owner's call (decision 2): start from it |
| Run files | from 1.5a's command (`docs/runs/1.5/1.5a/make_files.py`): the run name `duel_gru_1_6a`, the length, `SHOT_COST=0`, no `--pfsp`; `start.ps1` refusing any firing cost above zero; the settings check against 1.5a's command and its end (`python tools/run/check_settings.py`); `start.ps1` from 1.5a's end: its anchors, 1.5a's end as the control and an anchor, 1.3b's end an anchor |
| The ramp | 1.4b's `ramp_14b.py` as the model, `--free` (never held: CLAUDE.md rule 6): `INTENT_TEACH_W` 1 → 0 and `SPEED_PAY` 0.125 → 0 over updates 0 to 40; its test on fake files (`ramp_test.py`) |
| The records above | some exist (his targets' shares, `intent.share`; blind fire by weapon, `v14.blind_fire`; blind rockets by kind); the rest (a hunt's length and end, time and frags at holds, blind shots' places and damage, contacts on an item plan) added to the panel or the checks' JSON ⏳ 🧪: records only, play unchanged |
| No dry run | (owner, 11-04) the first 10 updates and the check at update 10 are the trial |
| **Built 11-05 morning** (owner: "start the code build and then tell me when the run is ready") | ✅ `make_files.py` (1.5a's command: run name, `--minutes 600` as a cap with `--max-updates 80`, `--head2-wpg 1` at 1.5a's end value, `SHOT_COST=0`; the settings check against 1.5a's command passes with those five differences only); ✅ `ramp_16a.py` (both dials 0 to 40, marks 10, 40, 80, the blanked check at 80 against 1.5a's end; logs big weapons owned and flags 0.05 under the first five updates; flags any firing cost) and `ramp_test.py` on fake files (all passed, `ramp_test.log`); ✅ `start.ps1` (refuses any firing cost above zero in the command or `live.json`, 1.5a's dials not at their ends, a settings difference, a running trainer). The 1.7 baseline records (hunts, holds, blind shots' places, contacts on an item plan) not built (owner, 11-05: "Proceed without the 1.7 monitoring") |
| Found 11-05 | **1.5a's big weapons owned slid with the teacher on**: 1.3b's end 1.80 → 1.5a 1.79 (u11-20) → 1.71 (u41-50) → 1.70 to u130 → 1.67 (u131). So 1.4b's drift came with the three u0 removals or the weapon part, not the item fade alone. 1.6a's baseline is 1.70 |

## The checks

200 games every 20 updates against 1.5a's end, every fourth against b1.2d's end, an extra one at update 10. 1.5a's measures in each: his
weapon by distance (his seat alone), his chance of the rail at range and of rockets close (`dump_eval.py`'s `wkp`), the habit seats' rows
in the league table; the head's weapon scores switched off at the end (1.5a's `blank_check.py`). Every win rate reported; under 40%
flagged at once; never held or stopped (rule 6). Saves kept with their optimizer at update 40 and the end.

## Watched and judged by

| Measure | Wanted |
|---|---|
| Win rate against 1.5a's end; against b1.2d's end | level or better (the zero point: the same network against itself, about 50%) |
| **Big weapons owned**, update by update, through the fade and the hold | holds at 1.5a's end; no slide in updates 40 to 80 (1.4b's drift) |
| His weapon in hand by distance, rail and rockets in hand; the head's weapon scores | hold or keep bending toward the pros' (1.5a's measures) |
| Speed on trips, air time (owner: "speed is the thing to watch") | hold through the speed pay's fade |
| The mega and red armor taken first, stack at fights, targets reached | hold |
| 1.7's baseline (above) | recorded |

## The equilibrium

The item lesson goes: his target choice is then learnt from what each choice leads to, by the hands' rows and the head's scores together.
The speed pay goes: fast movement is paid only by what it wins (it held in 1.4b), and keeping or dropping a trip costs nothing of itself.
The combat, item and win parts stay; in self-play the items he takes are those that win games against a copy that also takes them.

## Red team

| Part | Hand-built or assumed | The measured alternative | Watch |
|---|---|---|---|
| The teacher and the speed pay out together over 40 updates | the owner's call (1.4b took them 60 and 20 updates, apart) | one at a time | big weapons owned, speed |
| A hold of 40 updates | the owner's call | longer | 1.4b's drift lasted 20 or more updates after its fade |
| `RAIL_FAR_PAY` 0.25 still on | a single behaviour's pay | out, later | rail in hand |
| No firing cost | the owner's rule | a price on ammunition (`SHOT_COST`; the firing costs went out in b1.2) | ammunition run out in fights; shots a minute |
| Pay pathologies (the ledger) | | | negative frags, sign flips, lopsided games |

## The owner's decisions

| | | |
|---|---|---|
| 1 | ✅ 80 updates: the teacher and the speed pay out over 0 to 40, held to 80; the lock to 1.7 | owner, 11-04 night |
| 1b | ✅ no cost for firing at all, at its source, refused at the start, and left that way | owner, 11-04 night |
| 2 | ✅ start from 1.5a's end (its weapon goal not met: the 06:30 report of 11-05); "The goal is to get this part done so that 1.7 can start from it. 1.7 is the real meat" | owner, 11-05 07:20 |
| 3 | ✅ no matchmaking by difficulty in 1.6a: the league draws as in 1.5a (no `--pfsp`) | owner, 11-05 morning |
| 4 | ✅ the speed pay in item runs kept (`SPEED_PAY_RUN` 0.4): "it's not relevant to this run" | owner, 11-05 |
| 5 | ✅ `RAIL_FAR_PAY` 0.25 kept | owner, 11-05 |
| 6 | ✅ started 2026-11-05 07:22: "Start 1.6a now"; the 1.7 baseline records not built ("we'll get that involved when we have it") | owner, 11-05 |

## The result

Started 2026-11-05 07:22 from 1.5a's end (update 133) with its optimizer; every start check passed (`start.log`). **Ended 2026-11-05
14:25 at update 80** as set (exit 0, no stall, no restart). End kept: `keep/policy_end_16a.pt` and `opt_end_16a.pt` (the same bytes as
`policy_u80_16a.pt`, `opt_u80_16a.pt`); saves with their optimizer at updates 10, 40, 80. **The goal is met: both parts out, games held;
the one cost is a slow slide in item control.** 1.7 starts from its end.

| Check (200 games, ten maps) | Record | Win rate | Frag share |
|---|---|---|---|
| u10 against the start (1.5a's end) | 102-98 | 51.0% | 50.1% |
| u30 against the start (teacher at 0.25) | 91-109 | 45.5% | 47.9% |
| u50 against the start (both at 0 from u40) | 101-99 | 50.5% | 50.3% |
| u70 against b1.2d's end (reference) | 188-12 | 94.0% | 73.5% (1.5a at u70: 88.0%) |
| u80, the head's weapon scores off, against 1.5a's end | 79-81 on 8 of 10 maps (running) | | |

No check against the start after u50 (the watcher's every fourth went to the reference at u70; the run ends before u90).

| Measure | Start | End | |
|---|---|---|---|
| Big weapons owned | 1.70 (1.5a's end) | 1.62 | slid from u44 (1.67) to u67 (1.63), flat 1.62 from u71; the ramp flagged it from u71 (its own baseline read 1.678, update 1's transient) |
| Mega + red armor a minute | 1.92 (u10) | 1.84 (u80) | |
| Trip speed; share over 320 | 337-339; 0.50-0.53 | 339; 0.51 | held through the speed pay's fade |
| Weapon in hand in games | rockets 0.22, lightning 0.58, rail 0.02 (u10) | rockets 0.22, lightning 0.61, rail 0.01 | no move toward the pros' (rockets 0.41, rail 0.14) |
| Behaviour panel | | GREEN at every reading (u10 to u80) | |
| Firing cost | 0 | 0 every update | |

Read: the item teacher and the speed pay are gone with no loss of games against the start and a better margin over b1.2d's end than
1.5a's. Speed did not need its pay. Item control slid about 5% (1.70 → 1.62 big weapons owned, 1.92 → 1.84 mega and red a minute)
and had flattened by the end; nothing in the run replaces the teacher's pull, so 1.7 should watch both from its first update.

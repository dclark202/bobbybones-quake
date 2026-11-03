# b1.4a: free choice in contact, exchanges that pay a little, the item rule out

**Out of date (owner, 11-01): contact freedom moved to b1.2b, the rule's end to b1.3a's fix. Only stage 2, the damage weight, is left here. See the [family page](../README.md).**

*2026-11-01 (owner): "Fight more", "Tunnel vision less", "Begin to fade out hard coded rules for items". On the damage weight: "He should net a bit from chip damage, I like the idea of damage taken being slightly less than damage given"; "We can go to 0.8". Moved here from b1.3 when that became the pay table and the costs. Rocket jumps and movement are left for later. The family: [README](../README.md). The diagnosis behind it: [TARGET_LOCK.md](../../../design/TARGET_LOCK.md).*

**Marks:** ✅ built and tested · ⏳ to build · 🧪 to measure · ❓ owner's decision

## The owner's page

| | |
|---|---|
| Started from | b1.3a's end with its optimizer (`duel_gru_b1_3a/keep/policy_end_b13a.pt`, `opt_end_b13a.pt`) |
| Run | `duel_gru_b1_4a` |
| Stage 1: free choice in contact | the lock does not apply while the enemy is in contact (noticed or heard in the last ~2 s), with a reading at once on first contact. The item rule is silent in contact. Opened by a live dial, the chance a contact is free. Out of contact the 8 s lock stands. Code written, one bug's fix ready ⏳ |
| Stage 2: exchanges pay a little | `DMG_TAKEN_W` 1 → 0.9 → 0.8 (owner), on enemy damage only (owner): his own splash, falls and hazards stay at full cost. Live dial ✅; enemy damage only: code written ⏳ |
| Stage 3: the item rule out | `INTENT_TEACH_W` 1 → 0.75 → 0.5 → 0.25 → 0, everywhere. Live dial ✅ |
| Stays | b1.3a's table and its costs gone, `WIN_ADD` 0.33, the head on combat plus win pay, the fairness limits, `!aim default`, 65% games / 35% pro starts |
| Hold rule | as b1.2a: goes on above 40%; a check under 50% flagged in the chat; 40% or less holds the next step (owner, 11-01) |
| Length | `--minutes 1440` (24 h) ❓ to confirm at the start |
| League, checks | the start and v0.6.0's end as anchors; 160 games, about every 20 updates, against the start, each seat at its own contact dial; every fourth against v0.6.0's end; the panel. Never stopped |
| Kept | with its optimizer: the save before each step, the saves at the stages' ends, and `keep/policy_end_b14a.pt` |

## The schedule

Hours from the start, at ~4.6 minutes an update. A step comes right after a save, every 20 updates (owner). A hold adds to it.

| Update | Hours | What | Save kept |
|---|---|---|---|
| 0 to 10 | 0 to 0:45 | nothing changes | `policy_start_b14a.pt` |
| 10 / 30 / 50 / 70 | 0:45 / 2:20 / 3:50 / 5:20 | **contact** 25% / 50% / 75% / 100%, the rule silent with it | one before each step |
| 70 to 90 | 5:20 to 6:55 | held; read | `policy_contact_b14a.pt` at 90 |
| 90 / 110 | 6:55 / 8:25 | **`DMG_TAKEN_W`** 0.9 / 0.8 | one before each step |
| 110 to 130 | 8:25 to 10:00 | held; read; possible play test | `policy_fight_b14a.pt` at 130 |
| 130 / 150 / 170 / 190 | 10:00 / 11:30 / 13:00 / 14:35 | **`INTENT_TEACH_W`** 0.75 / 0.5 / 0.25 / 0 | one before each step |
| 190 to ~313 | 14:35 to 24:00 | settles; play test | the end |

From ~08:00 on 11-02, after a look at b1.3a's end and the owner's go.

## Judged by

| Measure | Now | Wanted |
|---|---|---|
| Win rate against the start, against v0.6.0's end | | at least 50% |
| Enemy's share of his targets | 1.8% (u49 of b1.2a, gate 0.4); 1.2% before the head | clearly up; number set from b1.3a's end ⏳ |
| Off by 30+ degrees, the owner in sight under 800 u | 25-30% (the owner: 15-18%), b1.0a's games | near a person's |
| Closing speed, same frames | -17 to -34 u/s | about 0 or better |
| Closing after a sighting; fires within 1 s (`tools/bobby_yardsticks.py`) | from b1.3a's end 🧪 | pros: +5 u/s, 79% |
| Chip damage: exchanges with no death | 5.1 to 5.3 a minute; stack taken 107-139 by him, 154-181 by the owner, b1.0a's games (`play_read.py`) ⏳ | stack taken by him up |
| Stack at the start of a fight | 139-160 against the owner's 198-254 | does not fall |
| Items a minute, time at spawns | | floors set from b1.3a's end ⏳ |
| Rule agreement, trips a minute, targets reached | 72%, 12.5, 40% | read through stage 3 |
| The owner's play tests | "tunnel vision" | "he picks fights" |

## The equilibrium

**Stage 1:** both players re-decide at contact, so a commitment holds only while nobody is about, and the better answer to the enemy's presence wins. **Stage 2:** at 0.8 a point dealt pays 0.0055 and a point taken from the enemy costs 0.0044, so an even exchange pays both a little (per 100 damage each: +0.11). With b1.3a's costs gone and today's volume, that takes an even exchange from about -0.08 to about +0.23 a player-minute. Chip damage nets a bit, and frags, deaths and win pay still decide the game. **Stage 3:** targets are chosen by the head and the hands' pay, so items are taken when they matter. Expected on the way: more fights and shorter item trips; then fewer pickups. The danger is trading when low, which frags and the win part price.

## Red team

| | |
|---|---|
| 0.8 is a guess at the size | +0.23 a minute is still under speed pay's +0.75, and more if he fights more. It may not be enough, or it may pay trades that lose games. The dial is live, and a change is for the owner's word |
| It reverses a fix, more gently | v0.5.0 raised 0.75 to 1.0 because even trades paid both. That is now the aim, at a smaller size. Win rate against v0.6.0's end is the guard |
| Self-play may mislead | both copies trade happily, while a person punishes trades (21-0 and 12-0 came largely from stack). Only play tests can catch this |
| Stack | more fights from behind may lose more games. Stage 3 may lower stack further |
| It may not fix the looking | stage 1 starts only once he has noticed. No pay rewards looking; b1.3a's jerk fade removes a cost on it, and that this is enough is untested |
| Item rule, spawn camping | v0.4.4's camping came with the rule's fade. Some loopholes are fixed since. The panel flags it. Its real pull is unknown: weight 0.1, agreement 72% |
| What stage 3 does not remove | `ITEM_RATE`, `BIG_PICK_SEQ`, `ITEM_BELIEF`, the pros' tables, `RULE_WALK`'s ways. Openings' labels: to confirm they scale with the dial |
| Flicker in contact | he re-samples every second in contact. It only moves his way input and target, but the reviewer suspects it disturbs the hands (aim error is the read) |
| Contact steps | 20 updates a step (owner), one check at each value. b1.1a's harm took about 40 updates to show, so a cost may appear one step late |
| A young start | b1.3a's last change has ~3 h behind it at this run's start. Its slow costs may read as this run's |
| Hold at 40% (owner) | below b1.1a's failure (41-42%), which it would have passed: a slow loss goes through, flagged only. The stage saves are the way back |
| Target switch cost | `INTENT_SWITCH` 0.02 (-0.23 a minute) still taxes re-deciding. Left in: its size against a hit is small. Measured alternative: free in contact |
| Hand-built / assumed | the ~2 s contact window, what counts as contact, every schedule, the 0.8, the rule's silence in contact, the head's pay |
| Pay pathologies (ledger) | watched in self-play games: mutual chip with few frags, negative scores, sign flips, lopsided games, value drift |
| Rocket jumps, movement jumps | important, not in this run (owner) |

## Before the start

| Step | Where it stands |
|---|---|
| Contact in the simulator, per seat in the checks | written in the worktree `BobbyBones-b13`; the identity test found the rule speaking on a contact's first reading, the fix is ready, not applied ⏳ |
| Enemy damage only | written; to pass the identity test ⏳ |
| Contact on a server | it must reach the plugin (`env_vars`); tried on a private server ⏳ |
| The measures | chip damage in `play_read.py` written; floors and the enemy's share from b1.3a's end ⏳ |
| Command, ramp, start script, smoke | written for the earlier plan; to redo from b1.3a's ⏳ |
| The owner's go ❓ | ~08:00 on 11-02 |

## Changes on the fly

| Time | Change | Why |
|---|---|---|

# b1.1a: the brain's old belief, the pull toward level and the target lock out, from b1.0a's end

*2026-10-31 (owner): "fade those two, get him 'ready for strategy'"; the brain "can take 4-5" hours; "Why not try to do the lock fade overnight? Put it after the level fade. 2 hours each. Then we can tell in the morning before starting if it should be addressed after. Just make sure to save the checkpoints in between the three fades." The family: [README](../README.md).*

**Marks:** ✅ built and tested · ⏳ to build · 🧪 to measure · ❓ owner's decision

## The owner's page

| | |
|---|---|
| Started from | b1.0a's end with its own optimizer (`keep/policy_end_b10a.pt`, `opt_end_b10a.pt`) ⏳ |
| Run | `duel_gru_b1_1a` |
| Pay | as b1.0a's end: the table unchanged, `WIN_ADD` 0.33, live |
| The rest | as b1.0a: item rule on, no head, 65% games, 35% pro starts, `!aim default` |
| Hold rule | the ramp goes on above 40%; any check under 50% is flagged in the chat; a check of 40% or less against the start holds the next step |
| Length | `--minutes 855`, to about noon on 11-01 from a ~21:45 start (~225 updates); the owner may cut it short |
| League | b1.0a's end and v0.6.0's end as anchors, then his own snapshots |
| Checks | 160 games, about every 20 updates in practice, against b1.0a's end; every fourth against v0.6.0's end; the panel. Never stopped |
| Logged | self-play games of every 40th save |

## The schedule (one run, written for a ~21:15 start; add the real start's delay, ~30 min; ~3.8 min an update, a step right after a save)

| Time | Update | What | Save kept before it |
|---|---|---|---|
| 21:15 to ~21:55 | 0 to 10 | shut | `keep/policy_start_b11a.pt` |
| ~21:55 to ~02:20 | 10 to 80 | **the brain:** `BRAIN_FADE` 0 → 1, seven steps, ~4.5 h | `keep/policy_prebrain_b11a.pt` |
| to ~03:00 | to 90 | held | |
| ~03:00 to ~04:50 | 90 to 120 | **the pull:** `LEVEL_PULL` 0.95 → 1, three steps, ~2 h | `keep/policy_nobrain_b11a.pt` |
| to ~05:30 | to 130 | held | |
| ~05:30 to ~07:25 | 130 to 160 | **the lock:** `INTENT_HOLD` 8 → 4 → 2 → 1 s, three steps, ~2 h | `keep/policy_nopull_b11a.pt` |
| ~07:25 to the end | 160 on | settle | at the end `keep/policy_end_b11a.pt` + `opt_end_b11a.pt`, the state with all three out |

So b1.2 can start from any of them: the morning's checks say which fade, if any, to go back before.

**Stopped at 08:00 to 09:00 for b1.2, the lock has only ~1 to 1.5 h and ~3 checks to settle.** To noon: ~4.5 h.

## Judged by

| In the stretch | Read |
|---|---|
| Each fade's own | win rate against b1.0a's end (at least 50% in the last checks), every fourth against v0.6.0's end |
| The brain | the brain's scores; tracking in the mind log |
| The pull | aim error and on-target share with the enemy in view, rail in hand |
| The lock | target changes a minute, the enemy's share of his targets (1.2% now), items a minute, time on a target |
| All | frags a match-minute (1.60 now), the panel, the owner's play test |

Not entropy: most of what moves it is zoom and the mouse with nobody to aim at (`tools/run/entropy_heads.py`, 10-31).

## The equilibrium

The pay doesn't change, so neither does its fixed point: win more games, collect the table. The brain must carry the enemy's place from its own memory. The view must find level by itself. **The lock:** he may change his mind each second, so a target is held only if it keeps being the best thing to do. Expected behaviour: he can leave an item run when a fight starts, but also risks flicking between targets and arriving nowhere, since the item rule still teaches items at each reading and the price of a switch (`INTENT_SWITCH`) stays. In self-play, a free choice favours the best answer to what the enemy is doing right now.

## Red team

| | |
|---|---|
| The lock has no record | never faded. v0.6.3's draft expected flicker. Two hours is fast for that, and the owner's call. Without a head to steer it, the item rule fills the freed readings, so it may raise item-chasing and not lower it. That's what the morning's reading is for |
| Checks can't separate seats' locks | 🧪 `INTENT_HOLD` is one number for the whole process, so both seats of a check and the league's older selves get the same lock. A check at 1 s plays b1.0a's end at 1 s too, a lock it never trained with. So the checks may flatter him, or hide a cost. A per-seat lock is more to build |
| The servers | a save's lock must reach the plugin through `env_vars`, and its play tests must use it. To verify on a private server before a play test |
| The brain's record | v0.6.1b's checks fell 54 → 44 during its fade, on win-only pay; its scores held |
| The pull's record | v0.6.1's end lost 144-176 to its save before the fade, confounded with more win-only pay; probably minor |
| Together | v0.6.1d took out the brain and the pull on a blend, held level with its start, and played better than its numbers |
| Three fades, short holds | a slow cost from one can show up in the next stretch; the holds are ~40 min. Reading them apart is approximate |
| Settling | short if stopped at 08:00 to 09:00. A slide after that wouldn't show |
| b1.0a's end is young | ~4.5 h at full win pay |
| Hold at 40% | a slow loss down to 41% goes through all three, flagged only. The saves are there to go back to |
| Tunnel vision | win pay prices items up more than frags (a red armor x4, a frag x2.2, level at 5 min): unmeasured as a cause, not changed here |
| Hand-built / assumed | the schedule, the hold rule, the lock's steps, its floor of 1 s, which columns count as the old belief (`sim/rule_fade.py`) |
| Pay pathologies (ledger) | none new. Watched: negative scores, sign flips, lopsided games |
| Rocket jumps, movement jumps | important, not in this run |

## Before the start

| Step | Where it stands |
|---|---|
| `INTENT_HOLD` a live dial ✅ | in `LIVE_VARS`, range checked; `ident.py`: at 8 s the same as HEAD to the bit, set live or not; at 1 s target changes x3 on random actions; the panel plays a save at its own lock |
| The ramp ✅ | `ramp_b11.py`: the brain, the pull, the lock, the three saves kept; `start.ps1` refuses without the lock fade |
| Settings check ✅ | against b1.0a's command: only `--run`, `--minutes`, `--brain-fade` |
| Smoke run | `smoke.py`, on the new plan; `start.ps1` refuses without ALL PASSED and the lock's check |
| b1.0a's end | kept at its next save after the owner's word; `handover.py` not used |
| The owner's go ✅ | 2026-10-31: "Just build it yourself and start it when it's ready. I agree on the plan that we have (what is in the card)" |

## Changes on the fly

| Time | Change | Why |
|---|---|---|

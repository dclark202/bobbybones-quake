# 1.4c: the target lock out, by a learned choice to keep or re-decide, from 1.4b's end

*2026-11-03 (owner): split out of 1.4b ("We can make the lock into a separate run 1.4c, it needs more working"). 2026-11-04 (owner): "The main thing here is that we need to fade the item lock out, so that he does not get blinders after deciding on an item"; on the plan below: "Yes, I agree with this. Write it into a 1.4c card, and have it ready to go tonight. My intention is to run 1.4b til this evening and 1.4c overnight". The blind-fire cost goes out at the start (owner, 11-04: "make sure its out in 1.4c"). The family: [README](../README.md); the lock's history: [design/TARGET_LOCK.md](../../../design/TARGET_LOCK.md).*

**Marks:** ✅ built and tested · ⏳ to build · 🧪 to measure · ❓ owner's decision

## In plain words

Today a target holds for 8 seconds (really 9: the lock's off-by-one) whatever happens, unless the item is taken, is gone by what he knows, or he has seen the enemy in the last 2 s. A sound, a hit from out of view, the enemy's pickup heard, an item coming due: none of these free it. Those are the blinders. Taking the lock off without anything in its place (b1.1a) made his targets flicker, because every free reading draws all 17 targets again: the lock was the only thing that turned that draw into a plan he keeps.

1.4c gives him what AlphaStar and Pluto have and we lack: **"no new order" as its own choice, separate from which target**. At each reading he chooses to keep his target or to re-decide; only a re-decision draws the target. The lock rule hands its readings to this choice a share at a time (g, 0 → 1); at the end the lock is out of his play.

## The owner's page

| | |
|---|---|
| Started from | 1.4b's end with its optimizer (`data/sim_runs/duel_gru_1_4b/keep/policy_end_14b.pt`), if 1.4b passes; the keep choice added to it (`tools/keep_init.py add`) |
| Run | `duel_gru_1_4c` |
| Length | ❓ **12 hours** by default (`--minutes 720`, about 145 updates), overnight (owner: "1.4c overnight") |
| The one new thing | **keep or re-decide** at each reading, handed the lock's readings by the share g (live `KEEP_G`) 0 → 1 over updates 10 to 90 |
| Also at update 0 | the blind-fire cost out (`BLIND_FIRE_W=0`; it was −0.0014 a player-minute in 1.3b) |
| How his target is chosen | as at 1.4b's end: the hands' rows plus the head's part, the head's credit (`H2_PG` 1), the L2 on both parts; the item rule's lesson, the switch cost and the speed pay are out (1.4b) |
| Combat, item and win pay | unchanged |
| League | 1.4b's, with 1.4b's end as an anchor: 1.4b's end, 1.3b's end, b1.2d's end, b1.1, v0.6.0's end, and his last eight snapshots; matchmaking by difficulty on (`PFSP` 1), the checks' opponent (1.4b's end) at a fixed share. Networks without the keep choice play with their lock (g 0 for their seats) |
| Checks | 200 games every 20 updates against 1.4b's end, every fourth against b1.2d's end (the servers' network), and an extra one at update 10; each seat at its own g and lock; read against the zero point (51.2%). The panel. Never stopped |
| Cores | as 1.4b: the trainer on the 8 performance cores, everything beside it on 8 efficiency cores, 14-17 left for the owner |
| Kept | the saves at update 10, 50 (g 0.5), 90 (g 1) and the end, each with its optimizer (`keep/policy_u10_14c.pt`, `_u50_`, `_u90_`, `keep/policy_end_14c.pt`) |
| Not in it | the pre-aim and watch pays (they stay; a candidate for 1.4d), readings at the head's 0.2 s tick (a later step), option A (a hold length chosen with the target) |

## The keep choice

| | |
|---|---|
| What | at each reading of his target, a choice of two. **Keep**: the target stays and the 17-way draw doesn't count. **Re-decide**: the target is drawn as today (it may come out the same) |
| Forced re-decision | only where the target has ended: taken, gone by his belief, "nothing", a reading at once after a spawn or a weapon taken. A contact still gives a reading at once: a chance to re-decide, not a release |
| Rate | today's readings: once a second, staggered, and at once on a contact |
| What it reads | the head's slow memory (with its gradient, as the head's target layer), the hands' fast memory (a number: no gradient into it from this choice), and three numbers: the target's age out of contact, contact (the enemy seen in the last 2 s), the held target's log-probability under the present scores (option-critic's termination: re-decide when the held plan is worth less than the others) |
| Its start | the lock made soft: out of contact the chance to re-decide is σ(0.75 × (age − 8.5 s)) (0.4% at 1 s, 1.6% at 3 s, 25% at 7 s, 59% at 9 s, 90% at 11.5 s); in contact 90%. The weights on the two memories and on the log-probability start at zero |
| Credit | the head's advantage (λ 0.995, about 5 s) and its two-minute value, as 1.3b's target: the keep choice's log-probability joins the target's in the head's term; none goes to the hands' term (`H2_PG` 1) |
| Entropy bonus | none on this choice (a bonus pulls it toward 50%: a re-decision every 2 s) |
| Pay | none of its own. After 1.4b nothing pays for the target itself (no way pay, no speed pay, no claw-back, no switch cost): re-deciding costs only what it leads to |
| The hand-over | at each reading that is not forced, with chance g the keep choice decides; otherwise the lock rule (locked → keep; run out or in contact → re-decide). g 0 plays as 1.4b's end: the coin and the keep draw have a random stream of their own. AlphaStar's hand-over on the learner's own states (the review's P2 mixture), not copy-then-swap |
| Per seat | each network plays at the g in its own file (`head2.keep_g`); a network without the choice plays with the lock |

## The schedule

| Updates | What | Dial | Gates |
|---|---|---|---|
| 0 | the blind-fire cost out | `BLIND_FIRE_W=0` in the command | |
| 0 to 10 | g = 0: he plays as 1.4b's end minus the blind-fire cost; the keep choice learns nothing yet | | an extra check at update 10 |
| 10 to 90 | g 0 → 1, +0.0125 an update (1.3b's credit pace) | live `KEEP_G` | reported, never held or stepped back (owner, 11-04: "Don't hold the ramps just go forward with them"; CLAUDE.md rule 6; `ramp_14c.py --free`): every check's win rate in the chat, one under 40% at once as a major problem; the owner decides hold or stop |
| 90 to the end (about 145) | g = 1: the lock is out of his play; settles | | a check every 20 updates |

## Before the start

| Step | Where it stands |
|---|---|
| The code: worktree `BobbyBones-14b`, branch `b14c` (from `main` at 6f4dabb), merged into `main` after 1.4b's trainer and watcher stop (its checks re-import the simulator) | ✅ built 11-04; ⏳ the merge |
| The simulator: the keep column (−1 the rule, 0 keep, 1 re-decide) beside the actions, the forced re-decisions, `keep_live`, `keep_feat()`, the counters (`stats["keep"]`, 16: who decided, re-decisions, and the blinders: held readings out of contact whose draw differs from the held target, after a sound in the last second and in quiet), `BLIND_FIRE_W`; `duel_env_ffa.py` regenerated | ✅ 11-04 (`ident.py`, Blood Run and Aerowalk, 3,000 frames, 1.4b's settings: unset and a keep column of −1 the same to the bit as HEAD, counters too; `BLIND_FIRE_W=0` the game the same and the pay up by exactly 0.003 a billed frame, 11,740 and 9,228 of them; keep everywhere: no change of target at a reading his choice decided (5 and 5 resets to "nothing" by deaths); re-decide everywhere: every decided reading counted, changes of target 805 → 1,790 and 1,158 → 1,837; a random column: decided readings = the counter: ALL PASSED) |
| `sim/head2.py`: the keep layer (torch and numpy), `head2.keep_g`; old saves load with no keep (share 0) | ✅ |
| The trainer: the draw and the coin (their own random stream), the keep column to the simulators, the masks, the keep choice's log-probability in the played, proximal and learning passes (with the target in the head's term; out of the hands' term at `H2_PG` 1), live `KEEP_G`, each league network at the share in its file, the keep choice in its own optimizer group (1.4b's optimizer loads into the groups before it), the record `keep` in every update | ✅ (the smoke below) |
| The checks, the panel, the logger: each seat at its own share (`sim/test_suite.py`'s numpy path; `tools/duel_eval.py`, `tools/run/dump_eval.py`, `ws_eval.py` send the keep column; the checks' JSON carries `stats["keep"]`) | ✅ |
| `tools/keep_init.py add` (the soft lock as the start); `same`: share 0 → 0 actions differ against the source; share 1 → the keep column back, its re-decisions by age and contact as the start says | ✅ 11-04 on 1.4b's latest save: 0 actions differ, memory the same to the bit; at share 1 re-decided 0.7% at 0-2 s, 7% at 4-6 s, 58% at 8-10 s, 98% at 14-16 s, 89% in contact: ALL PASSED |
| `ramp_14c.py` on fake files (`ramp_test.py`): `KEEP_G` on the clock, a hold, a lift, a step back of 10, the kept saves (10, 50, 90), nothing past the end, the other dials untouched, the flicker and keep-step flags | ✅ 11-04: ALL PASSED |
| A CPU smoke (`smoke.py`): 1.4b's update 10 given the keep choice with its optimizer, share 1, short updates; a league snapshot with its own keep choice at 0.5; a check of the save (keep on) against one without | ✅ 11-04 (started beside 1.4b without the owner's word, on the check cores at low priority: CLAUDE.md rule 9 since): 107 short updates, every one with its keep record at share 1, 32 to 89 decided readings each, its step under 0.014, its weights on the memories off zero (0.11, 0.13), the soft lock's own weights barely moved, no NaN; the save carries share 1; a check against a network without it finished, his keep choice deciding there: ALL PASSED. 1.4b's optimizer loaded, the keep choice in a group of its own |
| 🧪 The blinders before: on a 1.4b save, play unchanged, how often a locked reading's draw differs from the held target, by what happened in the last second; the target's spread at free readings (entropy, the draw not the top choice) | ⏳ |
| 🧪 A full level check of the start at g = 1 (200 games): the standing rule for a fitted start. Against 1.4b's save of update 30, during 1.4b on efficiency cores 14-17 (`0x3C000`, idle priority: not the trainer's `0xC03C3` nor the watcher's `0x3C3C`, no graphics card), owner 11-04: "if you can run the level check on the remaining E cores just do that in the meantime" | ⏳ running since 11:12 (`level.log`, `level/summary.json`) |
| A dry run | **none** (owner, 11-04: "We don't need a dry run, because this is a small change, it's just the first 10 updates of the actual run"): the first 10 updates and the check at update 10 are the trial |
| `make_files.py` (1.4b's command with these settings), the settings check against 1.4b's; `start.ps1` | ✅ 11-04: the settings check PASS (only the run name, the length, `--pfsp-fixed anchor_14b.pt`, `--keep-g 0` and `BLIND_FIRE_W=0` differ); against a 1.4b save only its live dials differ (`CONTACT_FREE`, `LEVEL_PULL`, `RAIL_FAR_PAY`: carried in live.json, `live_check.py`). `start.ps1` refuses unless 1.4b's dials are at their ends, both settings checks pass, the level check passed (it logs whether it was of 1.4b's end itself, by its sha256, or of an earlier save), and the start answers as 1.4b's end (`keep_init.py same`); the ramp runs `--free` (CLAUDE.md rule 6). `tonight.ps1` (on the owner's go): at 1.4b's end keeps it, stops its watcher, ramp and logger after its last check, merges `b14c`, waits for the level check, starts |
| The plugin and the export know the keep choice | ⏳ after the start, before any play test or server push (b1.2d stays on the servers) |
| The owner's go and the length | ❓ |

## Judged by

| Measure | Wanted |
|---|---|
| Win rate against 1.4b's end | level or better at updates 50, 90 and the end (against the zero point) |
| Against b1.2d's end | better at the end |
| **The blinders**: locked readings whose draw differs from the held target, after a sound or a hit from out of view; the time from such a moment to a change of target | down from 1.4b's end |
| **No flicker** (b1.1a's sign: trips 12.6 → 20 a minute, targets reached 40% → 21%): trips a minute, targets reached, abandoned, the average hold, re-decisions a reading in and out of contact | no slide from 1.4b's end (at update 11: 20.1 trips a minute, 24.9% reached, 63.7% abandoned) |
| The mega and the red armor taken first, stack at fights | hold |
| **Speed** (1.4b's watch): speed on trips, air time | hold |
| The holding places' share of his time (the lock's guard on places goes with it) | no rise like 10-12's (places at 5% of readings were 22% of his time) |
| The keep choice's size and step | bounded; its step per update small |
| The league table | no network he loses ground to |
| No spawn camping, no holding a spot all game | the panel |
| The owner's play test | does he turn when he hears you |

## The equilibrium

After 1.4b nothing pays for the target itself: it is a plan, priced only by what it leads to. In self-play the keep choice's best answer is to hold a plan while it still pays (an item race, an escape) and to re-decide when what he senses changes the best plan (a sound, a hit from out of view, the enemy's believed place, a timer). Both copies learn the same; the combat and item parts are zero-sum, and the win part pays the copy that reacts better. On the way: shorter holds around sounds and the enemy, long ones on item timing, and less churn in fights (today 36% of contact readings change his target). In the long run he wins more because his plan follows what he knows.

## Red team

| Part | Hand-built or assumed | The measured alternative | Watch |
|---|---|---|---|
| Keeping split from choosing the target | assumed, from AlphaStar's no-op and Pluto's orders | C, the lock 8 → 0 (b1.1a: 41% head to head, but with speed pay on item trips, the claw-back and no head) | trips, targets reached |
| Readings once a second | today's | the head's 0.2 s tick (Pluto: 4 a second) | the time from a sound to a change of target |
| Forced re-decision where the target ended | hand-built: "the target ended" | everything learned | time on a gone target |
| No entropy bonus, no price on re-deciding | assumed; the owner took out the switch cost (option-critic's deliberation cost) | a price on re-deciding, sized against the entropy bonus | re-decisions a minute |
| The start: the lock made soft (slope 0.75 a second, 90% in contact) | assumed: near the lock, with some early re-decisions to learn from | a flat 1 in 8 a reading; the hard lock (nothing to learn from) | the level check at g = 1; the early re-decisions' share |
| The hands' memory a number to this choice | a choice of safety: a new output's gradient into the shared memory can cost aim (2026-10-08's teacher) | with its gradient, as the target rows | aim and hits in the panel |
| Each seat at its own g; old networks keep the lock | assumed: each plays as trained | one g for all | the league table |
| The blind-fire cost out at update 0 | the owner's order | | the update-10 check |
| Pay pathologies (the ledger) | | | negative frags, sign flips, lopsided games |
| The checks' zero point | b1.2d's (51.2% on 600 games) | | every gate |

## Changes on the fly

| Time | Change | Why |
|---|---|---|

## The result

Not started.

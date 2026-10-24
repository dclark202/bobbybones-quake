# v0.4.0 on one page: the brain, trained beside the hands (pretraining)

*2026-10-22 night: **running** since 20:07 (branch `v040`, `5f49cad`; every test passed: the hands bit-identical to v0.3.10, no gradient into them, no measurable extra time), runs to about noon Fri. Then v0.4.1 connects the
brain to the hands ([RUN_v0.4.1.md](RUN_v0.4.1.md)); v0.4.2 fades the old belief out
([RUN_v0.4.2.md](RUN_v0.4.2.md)); v0.4.3 adds the strategy head ([RUN_v0.4.3.md](RUN_v0.4.3.md)). Design: [BELIEF_LOOP.md](BELIEF_LOOP.md).*

**Marks:** ✅ built and tested · ⏳ building · 🧪 to measure · ❓ owner's decision · ⏸ later

## Why: what v0.3.x settled (the owner, 2026-10-22)

> "close out v0.3.x as saying definitively that these two need to be separate networks, and start on v0.4 now as the brain."

| Try | The enemy picture lived in | What happened |
|---|---|---|
| The guessing game (v0.2.1, 2026-10-12) | his play memory | learnt to answer; cost aim when it shaped his memory hard; no gain in play |
| v0.3.11 first start (10% into his memory, pay 0.002, 30-min opening) | his play memory | the readout learnt fast (10 s+ unseen 935 → 478 u) but games against v0.3.10's end 80-80, 74-86, 77-83 (~48%); the drift check put the extra change in his goal choices out of view |
| v0.3.11b (5%, pay 0.001 then 0, 3-h opening) | his play memory | gate 80-80; stopped after 2 h for this |

Twice the shared memory cost his play: the picture gets its own memory.

## The two parts

| Part | What | Clock | Learns from | State |
|---|---|---|---|---|
| **The hands** | v0.3.10's end, exactly: aim, movement, weapons, goal choice. Trains on v0.3.10's settings (pre-aim pay, look-back pay, `LG_DEAF`, everything else) | every frame (40 Hz) | the game, as v0.3.10 | – |
| **The brain** (new) | its own input layer on his senses → a GRU of 256 → the readout (the enemy's place ± spread, velocity, stack band, weapon in hand, weapons owned) | every 0.2 s (5 Hz, the future strategy head's clock), from an 8-frame summary (mean + max) so a one-frame sound or glimpse is never lost | the lesson only: its guesses graded against the truth. **No pay, no cost** | ⏳ |
| The link | **none in v0.4.0**: nothing reads the brain; no gradient between the two | – | – | – |

So v0.4.0 is two things at once: more training of v0.3.10 (the hands), and the brain's pretraining before they connect.
Size: about 0.7 M weights more (input layer, GRU, readout); a few % more time an update (target).

## Tests before the start

| Test | Pass |
|---|---|
| Identity | the hands' actions bit-identical to v0.3.10's end on a fixed replay, with the brain added |
| Isolation | after a step of the lesson alone, every hands weight's gradient is exactly zero |
| A one-frame event | changes the brain's tick input (the max summary) |
| A CPU trial of a few updates | runs; the brain's errors fall |
| A short GPU trial | update time and the card's memory |

## Measures (the watcher, every update)

| What | Notes |
|---|---|
| The brain's position error by time unseen (in view, 0–2, 2–5, 5–10, 10 s+, since the enemy's respawn) | against its own trend and the pros' trackers (last known 229 u, +1 s velocity 204 u, the pros' pattern 143 u) |
| Stack band right, weapon in hand right, weapons owned right | – |
| The hands: step per update, aim, hit rates, pre-aim, look-back | should read as v0.3.10 |
| Checks against v0.3.10's end: **record, win rate, frag share** (whole ten-minute games, overtime) | the hands are v0.3.10 training on: ~50% expected |

## Found during the run

| When | What |
|---|---|
| 20:30 | **The velocity part's flat ~13.8 nats is not a bug** (debugger, branch `v040-veldbg`, `8cf1201`: a regression test only). Truth columns, mapping, fp16 store and gradient all check out. The enemy's velocity is near-unpredictable past ~0.4 s (the exact truth 0.4 s old is no better than the prior), he is in view ~15% of frames, and even perfect use of his late, noisy perceived velocity only reaches ~13.0 in view. The real limit is the output's shape: the enemy almost always moves ~340 u/s in an unknown direction, which a Gaussian centred on zero can't express; a speed + direction readout scores 13.40 unseen vs 13.9. ❓ for v0.4.1's new outputs (owner's word) |

## Ready to connect? (the test at ~11:00 Fri, before v0.4.1)

The brain's answers will replace the old rule-made belief (in v0.4.2), so it must beat that rule everywhere, not on average:

| Test | Pass |
|---|---|
| Position error 0–2 s unseen | at or under the old rule's ~142 u (pre-aim needs it) |
| 2–5 s and 10 s+ | clearly under the old rule (~500 / ~780 u), heading toward the pros' 229 / 143 u |
| The enemy's stack | the right band more often than the old filter (68%), a smaller error (the filter: 40 points off) |
| Levelled off | errors flat over the last ~3 h (still falling fast: train longer, the hands lose nothing) |
| Every map | no map where it is worse than the old rule |
| Honest | its spread matches its real error |
| **Zones (v0.4.0b)**: better than the point at long gaps | top-1 and top-2 zone right at 5–10 s and 10 s+ clearly above the zone of its own point estimate, the zone he was last seen in, and the map's commonest zone |
| Zones: honest | its odds calibrated: of the times it says ~60%, right ~60% (within ~5 points over the bins) |
| Zones: split beliefs | where the point is far off (> 600 u), the true zone still in its top two clearly more often than the point's zone gets it |
| Zones: levelled off, every map | flat over the last ~2 h; no map where it is below the baselines |

## Settings and files

| | |
|---|---|
| Start | v0.3.10's end (`duel_gru_v0_3_10/keep/policy_end_v0310.pt`) + a fresh brain (`tools/belief_init.py add`) |
| League | anchors v0.3.8, v0.3.9, v0.3.10 ends + v0.3.10's last 8 snapshots |
| Run | `duel_gru_v0_4_0`, run file `ql-bot-v040/scratch/run_duel_gru_v0_4_0.cmd`, watcher `scratchpad/v040w` |
| Flags | `--belief 256 --belief-every 8 --track 0.3 --info-pay 0`; `TRACK_TRUTH=1` |
| Ends | about noon Fri (the owner) |

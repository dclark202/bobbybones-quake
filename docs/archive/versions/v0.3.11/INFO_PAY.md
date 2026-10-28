# v0.3.11: pay for knowing where the enemy is (design, calibration, build)

*Built 2026-10-22 on branch `v0311` (from `v0310`, 9bb8f8a). Everything is behind switches, all off by default: with them off
the simulator's worker messages are identical to 9bb8f8a's and the trainer is unchanged. Nothing has been run on the card.*

The owner, 2026-10-22: "Have Bobby keep a running estimate of position, stack, ownership of weapons, direction, speed, etc of
the enemy in memory, with some estimate of uncertainty. Every few ticks he gets paid proportional to how accurate this is,
perhaps weighted by uncertainty as well. The pay can be zero sum."

## 1. What is built

| Part | What it is | Switch (off by default) |
|---|---|---|
| **The truth** (simulator) | 16 more columns of `info["aux"]`: the enemy's horizontal velocity in his frame, the six weapons the enemy owns, `trk_on` (a duel's game, both alive and in play), seconds since the enemy was last in view, his hand-built belief (`v02_bel`, ok, age) in his frame, EN_STACK's stack. Labels only: never inputs, nothing in the simulator reads them | `TRACK_TRUTH=1` (a training switch, not a PLAY_VAR: the plugins never see it) |
| **The belief readout** (network) | `sim/track.py`: from what his outputs read (his memory, 512) a layer of 256 and a last layer of 27 that starts at zero: the enemy's place (forward, left, up from him) with two spreads (across, up-down), his velocity with a spread, his stack band (4), weapon in hand (9), weapons owned (6 chances). A prediction, not an action: it feeds nothing | layers come with `--track` or `--info-pay`, or with a network that has them |
| **The lesson** (trainer) | the readout's negative log-likelihood of the truth on every learner frame of a duel's game with both alive; `--track-trunk` of its gradient reaches his memory and the layers below (as `--aux-trunk`); weight rising from 0 over `--track-warm` minutes | `--track W` |
| **The pay** (trainer) | every `--info-every` frames (20 = 0.5 s), every seat's readout scored against the truth (a floored log-likelihood, section 3); pay = k (his score - the enemy's score of him), added to the reward of that frame; nothing unless both seats are on (`trk_on`) | `--info-pay k`, starting `--info-delay` minutes after the lesson began and rising over `--info-warm`; live in `live.json` as `INFO_PAY` |
| **Counters** | `metrics.jsonl` "track": by time unseen (in view, 0-2 s, 2-5, 5-10, 10 s+, not seen since his spawn): the readout's median place error beside his belief inputs', share where the readout is nearer, its spread, NLL by part, band / weapon / owned called right, mean score; the pay per player-minute (absolute and net), its share decided while neither sees the other, the sum over all pairs (zero-sum check); the lesson's losses by part | with the readout on |
| **Conversion** | `tools/track_init.py widen <in.pt> <out.pt>` adds the layers (last layer zero) and the layout; `strip`; `show`. League files and the control need nothing: the trainer reads every seat with the learner's own readout | — |

Where it is computed: in the trainer, during the rollout (the readout's numbers never reach the simulator). The readout is
the learner's network on every seat's own memory: the league's and the control's seats are read by the same reader as his,
so a pair is always judged by one judge, and a league network needs no readout of its own. The pay is added to the reward
before the advantages (GAE carries it back to the turns, steps and sounds that earned it).

## 2. Calibration (the evidence)

**Sources.** (a) The pros: 1,043 duels for which the archive holds both players' own recordings (Blood Run 330, Aerowalk 300,
Lost World 361, Campgrounds 24, Cure 14, Hektik 8, Toxicity 5, Battleforged 1; Sinister and Furious Heights have none),
10,300 player-minutes, both players' true places, velocities, health, armor and weapons every 0.1 s
(`tools/counterplay_pros.py`'s pairing). Sight as the simulator's (55 degree cone, a clear line, 4,000 units). Hearing is an
approximation with the simulator's ranges: running footsteps (on the floor, faster than 250) within 800 units, a shot or a
take-off within 1,200 (straight line, walls ignored). (b) Bobby: v0.3.9's save 210 against itself in the simulator (sections
below). Scripts and raw output: the scratchpad `v0311/cal/`.

### 2.1 How far an unseen opponent goes (pros, all maps pooled; tau = seconds since last seen or heard)

| tau (s) | 0-0.5 | 0.5-1 | 1-2 | 2-3 | 3-5 | 5-7.5 | 7.5-10 | 10-15 | 15+ |
|---|---|---|---|---|---|---|---|---|---|
| share of both-alive time | 22% | 11% | 10% | 6% | 7% | 4% | 1.5% | 1% | 0.5% |
| displacement across, median (units) | 65 | 239 | 355 | 437 | 518 | 604 | 663 | 718 | 735 |
| ... 90th percentile | 173 | 405 | 689 | 900 | 1067 | 1195 | 1255 | 1315 | 1357 |
| rms per axis = sd(tau) | 122 | 235 | 339 | 415 | 478 | 540 | 574 | 605 | 620 |

By sight alone the opponent is in view 14% of the time and unknown 76% (by sight and hearing: known 37%, unknown 63%, most
of it within 2 s of a sound). The spread levels off at about 620 units an axis after 10 s: the size of a duel map.

### 2.2 How well simple trackers place him (median error, units, while unknown)

| Tracker | sight + hearing | sight only |
|---|---|---|
| Last known place | 229 | 515 |
| Last known + velocity for 1 s (his belief inputs' rule) | 204 | 544 |
| The pros' own flow (cell of 192 u + heading + tau, fitted on half the games, judged on the other half) | **143** | **425** |
| Blind (the map's mean place) | 585 | 569 |

By tau (sight + hearing): last known 69 / 253 / 379 / 472 / 558 / 650 / 709 / 765 units at 0-0.5 / 0.5-1 / 1-2 / 2-3 / 3-5 /
5-7.5 / 7.5-10 / 10-15 s; the flow 70 / 110 / 195 / 324 / 421 / 522 / 606 / 671. Knowing the map's flow is worth 25 to 45%
over "where he was" from 0.5 to 7.5 s; past 10 s little beats the blind guess. A good readout should reach the flow tracker.

### 2.3 Stack and weapons while unseen (pros; nats a scoring that the last known state is worth over the prior)

| Part | Prior's score | "As when last known" (persistence table) | Worth (nats) | How it fades |
|---|---|---|---|---|
| Stack band (4) | -1.29 | -0.34 | 0.95 | 1.20 at 0-0.5 s, 0.64 at 3-5 s, 0.49 at 10-15 s |
| Weapon in hand (8) | -1.37 | -0.58 | 0.79 | 1.19, then 0.37 from 3 s on |
| Each weapon owned | -0.47 to -0.69 | -0.04 to -0.06 | 0.42 to 0.65 | barely: owned weapons change rarely |

Stack and weapons are visible in the demos only from each player's own recording (paired games): an unseen opponent's band is
the same as when last known 75% of the time at 3-5 s; owned weapons almost always.

### 2.4 Bobby today (v0.3.9 save 210 against itself, simulator)

Four maps (Blood Run, Aerowalk, Lost World, Hektik), eight ten-minute games each, CPU, the v0.3.9 run's settings, every 0.5 s
with both alive (69,000 rows). tau = seconds since the simulator's senses last gave him the enemy (noticed in view or heard).

| tau (s) | 0-0.5 | 0.5-1 | 1-2 | 2-3 | 3-5 | 5-7.5 | 7.5-10 | 10-15 | all unknown |
|---|---|---|---|---|---|---|---|---|---|
| share of both-alive time | 10% | 6% | 8% | 8% | 11% | 9% | 5% | 6% | 67% |
| **his belief inputs (v02_bel)**, median error | 89 | 164 | 289 | 368 | 539 | 648 | 727 | 752 | **410** |
| his memory's guess (the guessing game's `place`, trunk 0) | 418 | 448 | 494 | 586 | 646 | 681 | 698 | 731 | 577 |
| last known place (same rows) | 68 | 228 | 383 | 510 | 600 | 678 | 742 | 753 | 477 |
| the pros, last known (sight + hearing; 2.2) | 69 | 253 | 379 | 472 | 558 | 650 | 709 | 765 | |
| the pros' flow tracker (2.2) | 70 | 110 | 195 | 324 | 421 | 522 | 606 | 671 | |

- **The bar**: his hand-built belief is 410 units off while unknown (2026-10-14: 445), about as good as "last known" by the
  pros' clock; a readout that reaches the pros' flow would be 20 to 35% better from 1 to 7.5 s. His memory's guess today
  (577) is worse than his own inputs everywhere under 7.5 s: the readout must first learn to read the inputs he has.
- Not seen or heard since the enemy's spawn: 15.5% of the time (belief 928 u, memory 775).
- He is in view 16% of the time (pros 14%); the enemy stays unknown for longer stretches than with the pros (by the pros'
  generous hearing they are mostly within 2 s of a sound; he 3 to 10 s), so the place part has more to earn in the sim.
- Within the simulator's own games the flow tracker gains less over "last known" (440 against 477) than with the pros
  (143 against 229): his routes are less regular, or 69,000 rows are too few for the table (the pros had 2.3 million).
- EN_STACK's stack belief: 47 points off on average while the enemy is unknown, 32 in view.

## 3. The scoring rule and its weights

- **Place**: a Gaussian (mean, spread across, spread up-down) mixed with a uniform over a 4,000 x 4,000 x 1,000 box (5% of the
  mass): log p of the true place. Spreads squashed into 40-4,000 units across, 30-1,500 up-down. Best possible -13.9 (exact,
  at the floor), blind about -21.6, the worst -26.5 (the floor: one wild miss costs at most about 5 nats more than a blind
  guess). Proper: on average a belief scores best by giving its true mean and spread (unit-checked). The lesson uses the
  plain log-likelihood (no floor), so far misses still teach.
- **Velocity**: a Gaussian across the floor (spread 30-1,000 u/s) mixed with a uniform over a disk of 900 u/s.
- **Categories**: log of (0.98 p + 0.02 / K) for the band and the weapon in hand; each owned weapon as a coin the same way.
- **Weights** (`--track-parts`, the lesson and the pay alike): place 1, velocity 0.25, band 0.5, weapon in hand 0.25, owned
  0.25 (six coins together). From 2.2-2.3: a good tracker beats a poor one by about 1 nat a scoring on the place while unknown
  (the flow against "where he was"), up to 6-8 nats when one sees the other and is not seen; the band is worth up to 1 nat,
  the weapon 0.8, owned weapons are known to both nearly always (their weight is kept low so that six coins do not outweigh
  the place).
- **Cadence**: every 0.5 s (20 frames), the pre-aim pay's scale of events; the pros' tau table shows nothing moves much faster.

## 4. The pay's size k

- **The noise of the pay** (both seats tracking equally, with the same simple tracker: last known + velocity, sd(tau) from
  2.1, exact in view): the place scores of two players of one game differ by 1.96 nats a scoring on average (pros; Bobby's
  self-play 2.12), 235 to 254 nats a minute; 85 to 95% of it while neither sees the other, the rest one-sided sightings
  (3.7 nats each with the pros, 6.1 with Bobby: he is seen without seeing more often). With equal skill this is zero on
  average: noise in his rewards, not a signal.
- **The signal** (a better tracker against a poorer one): the flow tracker against "last known" is +1.05 nats a scoring on
  the place while unknown (pros, 2.2); unknown 63% of the time: about 0.66 nats a scoring, 80 nats a player-minute. The
  stack band and the weapon add at most 0.5 x 0.95 + 0.25 x 0.8 = 0.7 nats a scoring.
- **k = 0.002** (`--info-pay 0.002`): the signal is worth about 0.16 a player-minute (the pre-aim pay's scale, 0.1 to 0.3),
  the noise about 0.5 |pay| a player-minute (zero mean; a frag is 1, the items pay about 5 a player-minute). In the CPU
  smoke (section 6) the |pay| at k = 0.002 rose from 0.01 to 0.46 a player-minute as the readout learnt.
  Live: `{"INFO_PAY": 0.001}` in `<run>/live.json` halves it from the next rollout.
- The pay begins `--info-delay` minutes after the lesson's start (default 60) and rises over `--info-warm` (default 60):
  until the readout has learnt something its differences are mostly noise.

## 5. The equilibrium (the standing rule) and the five goals

**Self-play equilibrium.** Zero-sum and symmetric: the same network on both seats earns nothing on average, whatever it does;
the pay moves only the difference between the two. One reader (the learner's readout) judges both seats, so neither can
earn by having a better judge, only by having a better picture in its memory or by being harder to picture. A deviation pays
when it (a) gathers information the other side does not (looking at the openings and ways he comes by, listening, reading
the item timings: the items call the enemy), or (b) gives less away (fewer sounds near the enemy: footsteps within 800 units,
take-offs and shots within 1,200; ways the enemy's memory cannot foretell; not being seen without seeing; a weapon change or
a pickup out of sight). The equilibrium is a player who watches and listens and moves in ways that are hard to read: the
pros' habits. In view both know almost everything: the difference there is about zero.

**Risks and what to watch.** Quiet costs speed: walking near the enemy is quieter (the speed goal pulls the other way; the
signal, about 0.16 a minute, is below the speed pay and the items): watch his speed unseen and jump presses a minute. Hiding
gains nothing by itself (both pictures get worse) unless he still hears the enemy, which is an ambush, a pro's play: watch
standing over 3 s. The share decided while neither sees the other (`hidden_share`; 0.45 to 0.99 in the smoke) says which
it is paying for. It does not pay for frags or damage: the fight stays the fight's. The pay's gradient never reaches the
readout (its lesson is supervised alone), so the readout cannot learn to flatter its own seat.

**The five goals.** Counterplay +: knowing where the enemy is and not being known is its core. Positioning +: watching the
openings (beside the look-back pay), ways that are hard to read. Weapon use: neutral to +: changing and picking up weapons
unseen hides them (the hand and owned parts, small weights). Speed / movement: a small pull toward quiet near the enemy
(watched). Beating people: through the first two.

**Fairness.** The pay reads the truth; his inputs stay what he perceives; the readout is never an input. Nothing changes in
the plugins: the readout, TRACK_TRUTH and the pay are the trainer's alone and the export leaves them behind.

## 6. Tests (2026-10-22; CPU only, cores 14 and 15, low priority)

| Test | Result |
|---|---|
| Worker messages with every switch off against 9bb8f8a (the run file's settings, random actions, 400 frames x 48 players): Aerowalk, Cure, Blood Run | IDENTICAL |
| `TRACK_TRUTH=1` against off (Aerowalk) | every message identical except `info["aux"]`, whose old 24 columns are identical; the 16 new columns sane (games on 63% of rows, velocities to 540 u/s, owned weapons, unseen seconds, belief, stack) |
| Trainer with the flags off against 9bb8f8a's trainer (seeded, `--overlap 0`, CPU, from v0.3.9 save 210), three updates | every update line identical but its timing; the saved weights identical to the bit |
| Unit checks of `sim/track.py` (scratchpad `v0311/unit_track.py`) | 18 of 18: the true spread and mean score best; the true chances beat even and overconfident ones (band, weapon, owned); velocity; the floors (a wild miss -26.5, a sure wrong band -5.3); the best place score -13.98; zero-sum over every pair; nothing when a seat is off; nothing between equal readouts; the module made without a draw of the random stream; the prior spreads exact; the lesson learns a place (error 10 u) |
| Conversion: `tools/track_init.py widen` of v0.3.9 save 210 | every old tensor and entry bit-identical, only `track.*` and `track` new; `test_suite.Policy` of both on the same inputs and draws (60 frames x 64 players): actions identical, memories identical (difference 0.0) |
| The checks' tools with the converted file | `sim/export_duel.py`: the same npz, key for key and bit for bit; `tools/duel_eval.py` (two games of one minute, the same seed): the same results |
| Trainer smoke ON (CPU, 2 workers x 8 matches, 64 steps, 4 pieces, `--overlap 1 --learn-nosync 1`, the run's settings; `--track 0.3 --track-trunk 0.1 --info-pay 0.002`, no delay) from the converted save, with an optimizer saved without the readout | 46 updates; the optimizer loaded (the readout's group added after); the pay summed to exactly 0 over all pairs in every rollout; mean |pay| 0.11 (updates 1-10) to 0.25 (37-46) a player-minute; the readout learnt: hand loss 1.85 to 1.33, band 1.37 to 1.13, owned 3.90 to 3.43, median place error in view 245 to 167 u, 0-2 s unseen 522 to 382 u; velocity did not move in that time |
| Resume of that run (an optimizer saved with the readout's group), `--track-lr-scale 5`, 39 updates | loaded whole; band 1.01, hand 0.98, owned 1.90 over the last ten updates; |pay| 0.46; the pairs' sum 0 throughout |
| The readout kept, lesson and pay off (the converted network, TRACK_TRUTH unset), 11 updates | runs; the readout's weights unchanged to the bit |

## 7. What is left before a 10-update gate arm

1. Convert the start network (v0.3.10's save at the arm's start) with `tools/track_init.py widen`; nothing else in the run
   folder changes (the league and the control are read by the learner's readout; `opt.pt` loads into the old groups).
2. The run file: `set TRACK_TRUTH=1` and `--track 0.3 --track-trunk 0.1 --track-warm 30 --track-lr-scale 5 --info-pay 0.002
   --info-delay 30 --info-warm 30` (proposed; the owner's go). For a gate at update 10 (about an hour) the pay is fully on
   only near its end: arm A (the lesson alone, `--info-pay 0`) and arm B (the pay from the start, `--info-delay 0 --info-warm
   10`) would tell the two apart, as the rule of 2026-10-13 asks of a new lesson.
3. On the card, not measured (the card was v0.3.10's): the update's time and memory (the readout is 0.14 M weights; the truth
   adds 16 float16 columns a frame on the host, about 0.12 GB at 10,080 players), and the step per output in the first
   updates (`--kl-heads`): the lesson reaches his memory at 0.1 of its gradient.
4. Live: INFO_PAY is a live name of `live.json` (as DMG_TAKEN_W), not of `live_settings.env`.
5. To read at the gate: `track.rollout.by.<band>.err_med` against `bel_med` (the readout must come under his belief inputs,
   410 u while unknown) and `nearer`; `pay.abs_per_player_min`, `pay.hidden_share`, `pay.pairs_sum` (must be 0); the
   lesson's losses (`track.loss`); and the usual check against the control.

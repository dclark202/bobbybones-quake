# v0.4.2's first try: the dip at fade 0 (2026-10-24), for review

## Context

BobbyBones is a Quake Live duel bot: a recurrent network (GRU 512, attention over input groups, 868 inputs, ~3 million
weights) trained by PPO self-play in a simulator, against a league of his own snapshots plus fixed older networks
("anchors"). Checks: every 20 updates, 160 ten-minute games (16 on each of ten maps, seats swapped between halves, aim
level 4, whole games with overtime) of the saved network against the previous best; a single map moves about ±10 points
by chance, a whole check about ±4.

The v0.4.x line:
- **v0.4.0/0.4.0b, the brain**: a part of the network that learns, from his senses only, to predict the enemy's place now and
  1, 2, 4 s ahead, his stack, and who takes the next items (labels in hindsight).
- **v0.4.1, the token**: the brain's answer fed into the rest of the network (the "hands"). It ran to update 320 and ended
  2026-10-24 07:12. Its checks against v0.4.0b's end read 64 to 71% from update 150 on, and 159-1 against v0.3.6. Its end
  save, `duel_gru_v0_4_1/keep/policy_end_v041.pt`, is kept with its optimizer state.
- **v0.4.2, the fade** (`RUN_v0.4.2.md`): 76 input columns made by hand-written rules (a rule's belief of where the enemy
  is, his stack, pre-fire places, the emergence point) multiplied by (1 − g) in the hands only (the brain still reads
  them). With `BRAIN_READ=1`, the simulator's readers of that belief (the legs' look point, the hunt target, the item-contest
  and hunt-silence rules, the doorway watching) use the brain's answer for a life drawn with chance g. With `BLIND_BRAIN=1`,
  pre-fire where the brain expects the enemy is free for those lives. **At g = 0 all of this is off.** The build was tested
  bit-identical to v0.4.1 in the simulator at g = 0.
- Also in v0.4.2: `PAY_SPLIT`, `WIN_SHADOW` (record only; a fixed-seed replay is bit-identical with them off and on).

## The first try (`duel_gru_v0_4_2_try1`, 07:14 to 10:04)

**The start:**
- Resumed from v0.4.1's end save (policy and optimizer), with the same league snapshots and anchors, plus v0.4.1's end
  added as an anchor.
- The fade was held shut for 60 minutes (`--rule-fade-delay 60`), then planned to open 0 → 1 over 250 minutes, capped by
  a live `FADE_CAP` (0.1 at the start), which a guard script raises only while checks pass.

**The run's settings against v0.4.1's** (checked by diffing the run files and the trainer's own "in force" printout):
- The run file differs only in `BRAIN_READ=1`, `BLIND_BRAIN=1`, `PAY_SPLIT=1`, `WIN_SHADOW=1` and the `--rule-fade*` flags.
- The live settings differ only in the **mega health flat pay, 0.30 → 0.35 from update 6** (the owner's change), and the
  fade's own two settings. The red armor stays at 0.30 and the yellow at 0.15.
- The code is v0.4.1's branch plus the fade commit, a route-copy commit (all off), and the win-chance tracker merge.

**The fade's actual level:**
- g = 0 for updates 1 to 18, then 0.001, 0.017, 0.033 and 0.049 for updates 19 to 22.
- The guard set the cap to 0 at update 23, after the update-10 check.
- A few lives drawn on the brain before then kept reading it until about update 38: 0.1 to 1.4% of reads, 0.04% at
  update 47.

**The checks against v0.4.1's end:**

| Save | g in its training | Record | Win rate | Frag share |
|---|---|---|---|---|
| update 10 | 0 throughout | 68-92 | 42.5% | 49.1% |
| update 30 | 0, except 0.001 to 0.05 at updates 19 to 22 | 68-92 | 42.5% | 47.6% |

Per map, update 10: Blood Run 5-11 (46%), Aerowalk 3-13 (45%), Lost World 8-8 (52%), Sinister 5-11 (46%), Furious Heights
5-11 (44%), Battleforged 9-7 (53%), Campgrounds 7-9 (50%), Hektik 9-7 (49%), Toxicity 8-8 (51%), Cure 9-7 (56%).

Per map, update 30: Blood Run 6-10 (46%), Aerowalk 6-10 (46%), Lost World 8-8 (46%), Sinister 6-10 (43%), Furious Heights
9-7 (51%), Battleforged 8-8 (52%), Campgrounds 6-10 (50%), Hektik 8-8 (45%), Toxicity 3-13 (43%), Cure 8-8 (54%).

Note: the games went 42.5% while the frag share stayed near level (48 to 49%).

**The training numbers** (no sign of trouble):

| Measure | v0.4.1's last updates | the first try's updates 10 to 47 |
|---|---|---|
| Step size (KL) | 0.031 | 0.030 to 0.031 |
| Aim error (visible) | 12.1 to 12.4° | 12.2 to 12.8° |
| Hit rate: rail / rocket / lightning | 0.60 / 0.53 to 0.55 / 0.53 to 0.54 | 0.58 to 0.62 / 0.50 to 0.57 / 0.52 to 0.55 |
| Pickups a minute: mega / red armor | 0.87 to 0.94 / 1.05 to 1.11 | 0.81 to 1.14 / 1.01 to 1.16 |
| Frags a match-minute | 2.39 to 2.59 | 2.0 to 2.5 (still rising from fresh games at update 10) |
| Kill share against the anchors | not measured | 0.47 at update 10, then 0.55 to 0.57 |
| Kill share against his snapshots | 0.49 to 0.55 | 0.48 to 0.55 |
| Entropy | 1.69 to 1.72 | 1.64 to 1.82 |

## What was checked

1. **The check path is fair.** v0.4.1's end against itself, through the same check (code, settings, driver), read 84-76
   (52.5%), frag share 48.7%. Per map: Blood Run 8-8, Aerowalk 7-9, Lost World 11-5, Sinister 5-11, Furious Heights 10-6,
   Battleforged 7-9, Campgrounds 11-5, Hektik 9-7, Toxicity 10-6, Cure 6-10.
2. **A code review of the checks** (tools/duel_eval.py, sim/test_suite.py, sim/rule_fade.py, against v0.4.1's branch)
   found no seat asymmetry:
   - The fade at g = 0 returns the inputs unchanged.
   - Both seats' brain token gate is 1.0, and both brains are stepped alike.
   - `BRAIN_READ` is not on in the checks; the checkpoint's settings are not applied by the check tool.
   - The reaction and aim delays are the same for both seats (100/150 ms).
   - The same input list is used for both seats.
   - The seat swap and the scoring credit the right seat.
   - The opponent file is byte-equal to v0.4.1's end.
   - The five check settings first added for v0.4.2 (`RL_AIM`, `PREFIRE`, `EMERGE_IN`, `HOP_QUIET_HEARD`, `RJ_CLEARED`) are
     input switches with no per-seat flag, and both networks trained with them on.
3. **The weights moved normally.** The relative change per group from v0.4.1's end to the first try's update 30 is the
   same as over 30 of v0.4.1's own updates (GRU 0.091 vs 0.091, policy 0.053 vs 0.053, attention 0.062 vs 0.064). The
   input statistics are identical.
4. **The simulator at g = 0:** `PAY_SPLIT` and `WIN_SHADOW` are record only. Every `BRAIN_READ` reader returns the rule's
   answer when no life is on the brain. The brain's draws use their own random stream.

## Open questions for the reviewer

- What in the first ten updates could make the network lose 7 points of games against its own starting point, with
  normal training numbers and a fair check?
- The one training change is the mega pay, +0.05 from update 6, in 4 to 24 updates. Can a pay change that small move
  games this much this fast? Note that the games fell while the frag share stayed near level.
- The league: v0.4.1's end was added as a fifth anchor (v0.3.8, v0.3.9, v0.3.10, v0.4.0b, v0.4.1). Does adding the
  starting network as an anchor change what he learns early (training against an exact copy of himself)?
- Something in a resume? Same optimizer state, the same learning rate (1e-4 in the metrics); the entropy and other schedules were not checked.
- A strong end save? v0.4.1 never played its own end save head to head, so the end could be a lucky high point.
  The owner considers going back into v0.4.1 not useful; the restart below tests v0.4.2 directly.

## What happened next

- 10:04: the first try was stopped (kept, nothing deleted).
- 10:34: restarted from v0.4.1's end with mega 0.35 from update 1 and the fade opening from the first update (capped at
  0.1). The first check is at update 10 with g = 0.1, its result about 12:40.

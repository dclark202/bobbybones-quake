## 2026-10-16 08:45 — Rocket jump runs built (B-252), all off by default; a scripted player clears 104 of the 174 pros' links in the corrected simulator (75% of the pros' rocket jumps); off = v0.3.1's simulator by fixed runs

Built in a helper's branch for the v0.3.1 restart (old run name `duel_gru_v0_3_1`); no training was run. Meant with `RL_QL=1`
and the physics switches (`QL_FLOAT`, `QL_FWD`, `QL_LAND`, `QL_JUMP`, with `QL_MOVE`): v0.3's rockets jump 60 units too low
(RESULTS 2026-10-15 21:25).

**What was built** (`sim/duel_env.py`, `sim/rocket_jumps.py`, `sim/train_duel_rnn.py`'s counters, `tools/rj_check.py`,
`sim/rj_clear.json`):
- **Rocket jump runs** (`RJ_RUN_P`, a share of the playing time from the same draw as the item runs and the jump runs). He
  starts 30 to 90 units of way (`RJ_BACK`) before the take-off of one of the pros' links in `docs/pro_rocket_jumps.json`
  (those whose take-off and landing are on the walking map; `RJ_CLEARED=1`: only those a scripted player clears). He holds
  the rocket launcher (10 rockets) and the machine gun, with the pros' median health and armor at that take-off. His
  target is the landing: his way's inputs lead there through the link. The five jump inputs show it as a jump ahead that
  needs no speed. **No new inputs** (773 / 797, as main).
- **Pay**: `RJ_ARRIVE` (default 0.5, the item and jump runs' arrival) once, when he comes down within 110 units of the
  landing from a flight of 8 frames or more that passed the take-off. Nothing for the way, for speed or for a near miss.
  A try ends without pay when he touches the floor elsewhere after the take-off, dies, or runs out of time (the way's
  seconds plus 2.5). The self-damage costs what it costs in games (damage taken, about 0.16 a rocket at v0.3.1's weights).
- **Silent teachers**: his legs (`LEGS`), the movement teacher and the walking teacher give nothing in these runs, so his
  own keys, view and trigger move him there (`_legs_who`, `_move_teach`, the walking keys).
- `RJ_LOOK_P`: the share of tries that start with his view already down at the pros' look-down.
- `RJ_OPEN` (`"map:1,3"` or `"map:all"`, a PLAY_VAR): his ways in games take the open links while he holds the launcher
  with a rocket and has `RJ_OPEN_HP` (150) or more health and armor. A link costs its flight plus `RJ_OPEN_COST`
  (1 s). It changes only his way's inputs and pay; the item rule and the scripted players keep theirs. Not to be opened
  until the runs show he makes them.
- `RL_QL` is now a PLAY_VAR: a checkpoint keeps it, so the checks play the rockets it was trained with.
- Counters (`v15.rj_*` in `metrics.jsonl`): the share of frames, tries, the share that arrived, rockets a try, and per map
  and link.

**Proofs.**
- Fixed-seed runs (`ident16.py`, 400 frames, 24 or 36 players), main at 78a8576 against the branch, with every new switch
  off: 12 of 12 identical. The sets were v0.3's, v0.3.1's, and v0.3.1's plus the restart's jump runs and physics
  (`JUMPS`, `JUMP_ALL`, `JUMP_RUN_P`, `RL_QL`, `QL_FLOAT`, `QL_FWD`, `QL_LAND`, `QL_JUMP`, `QL_MOVE`, `GL_QL`), each on
  Blood Run and Aerowalk, `duel_env` and `duel_env_ffa`.
- `tools/make_ffa_env.py`, then `tools/ffa_check.py`: two players identical to `duel_env` over 3000 frames.
- With the switches on: forced runs on Blood Run, Aerowalk and the free-for-all module ran without errors. With random
  actions, 0 arrivals.

**Can the pros' links be cleared in the simulator?** (`tools/rj_check.py clear`, all switches above on, no finger or aim
limits, the view held.) A scripted player tries plain executions until one clears the link: standing at the take-off,
running at it from 150 back, or arriving in the air at 350, 450 or 550 u/s; looking down 55, 70 or 88; fire on the jump
frame or one after; forward held or no key; aimed at the landing, then 10 degrees either side. A link clears when the
first landing is within 110 units of the pros' landing.

| map | links | on the walking map | cleared (their numbers) | pros' jumps on cleared links |
|---|---|---|---|---|
| Blood Run | 21 | 15 | 9 (2, 3, 6, 7, 10, 14, 15, 20, 21) | 67% |
| Aerowalk | 13 | 12 | 9 (1, 2, 3, 4, 6, 9, 10, 12, 13) | 91% |
| Lost World | 19 | 18 | 14 | 84% |
| Sinister | 13 | 12 | 10 | 86% |
| Furious Heights | 5 | 5 | 2 (1, 5) | 50% |
| Battleforged | 17 | 16 | 3 (1, 12, 14) | 24% |
| Campgrounds | 20 | 20 | 9 | 28% |
| Hektik | 12 | 11 | 9 | 77% |
| Toxicity | 13 | 11 | 7 | 24% |
| Cure | 16 | 16 | 9 | 50% |
| House of Decay (held out) | 16 | 16 | 8 | 60% |
| Dismemberment (held out) | 22 | 22 | 15 | 62% |
| **all** | **187** | **174** | **104** | **13,426 of 17,839 (75%)** |

- What the clearing executions were: 52 standing, 43 running in, 9 arriving in the air.
- The run's own rule pays these executions: 468 of 480 tries driven by them were paid, on six maps.
- The 70 links not cleared are mostly the long, high ones with look-down near 88 (Blood Run 4, 8, 11, 13). They need air
  control or a curved way that the straight script does not try. It is not shown that the simulator cannot do them.
- `RJ_CLEARED=1` keeps the runs to the 104 cleared links (`sim/rj_clear.json`). A first run of the same check, by
  mistake under his own hand limits and with a jump asked for only one frame, cleared 77.

**His hands (`tools/rj_check.py hand`, AIM_LEVEL 3, KEY_RATE 8; no aim limit changed).**
- With the strongest look-down (20 degrees a frame asked; view inertia 0.75; the view eases back toward level by 5% a
  frame when nobody is in view), he looks down to 50 in 5 frames, 70 in 7 and 88 in 8 (0.2 s). He holds it by pushing on
  (all the way down, the view stops at 89).
- The strongest command overshoots by 10 to 25 degrees, so 50 to 60 needs braking.
- Jump and click: the jump is read only on his left hand's frame, one in four (0 to 3 frames of wait). The click is read
  on any frame (fire finger free after 7 frames). Asked 0, 1, 2, 3 or 4 frames after the jump, the rocket left exactly
  then in 78 of 80 tries (twice 2 for 3, at 50), at every look-down from 50 to 88.
- So the pros' timing (shot on the jump frame up to 4 after) is within his limits. The shot on the jump frame needs him
  to time the press to his hand's read frame. His inputs show his keys' state, not that phase, so he must learn it from
  memory. One frame later needs only a reaction to his own take-off; in the game that rises 264 against 319 on the jump
  frame.

**The pay's equilibrium.** These runs are movement practice, alone on the map: not part of the zero-sum game, so there is
no opponent to play against and the best play is the plain optimum. A try is worth `RJ_ARRIVE` x p minus about 0.16 a
rocket (self-damage at v0.3.1's damage weights).
- At 0.5 a rocket pays once he arrives on about a third of them.
- At 1.0 it pays from about one in six. 1.0 is about what one successful jump run pays in all (way, arrival, speed).
- Not trying earns 0. He might learn to hold the trigger in these runs before he finds an arrival: the counters
  `rj_shots` and `rj_over` show it. `RJ_LOOK_P` makes the first arrivals likelier.
- Goals served: speed and movement (the first), positioning (high ground, items sooner), weapon use (the launcher as a
  tool).

**What did not work, or was not done:**
- No training: the runs have never been learnt from.
- 70 links not cleared by the script.
- The pros' entry speed at take-off is not in the data.
- The legs network (`move_v15n`) was trained in the old physics, and nothing here checks it under the new.
- `RJ_OPEN` is built, but it must not be opened before the runs show arrivals.

**What to try next:**
1. The ten-update test below on a scratch copy before the restart.
2. Air-control and curved executions in `rj_check` for the 70 links not cleared.
3. Read per-link arrivals after a few hours. Open `RJ_OPEN` for the links he arrives on in half of his tries.

**The ten-update test** (CLAUDE.md, 2026-10-13: a new lesson passes ten updates and a check against the control before a
start).
- Two arms on a scratch copy of the restart's start: the restart's `.cmd` with the physics alone, and the same with
  `RJ_RUN_P=0.02 RJ_LOOK_P=0.5 RJ_ARRIVE=1.0 RJ_CLEARED=1` (`RJ_BACK` default).
- Ten updates each. Read the step per output (`--kl-heads`), `v15.rj_tries`, `rj_over`, `rj_shots` and the per-map
  `rjs`.
- Then 4 maps of 16 games each against the control. The rocket arm must not fall below the physics arm.

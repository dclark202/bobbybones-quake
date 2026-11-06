# 1.8a: movement: the jumps he cannot make, the ways, rocket jumps

*2026-11-05 evening (owner): "we need to revisit movement: rocket jumping and the strafe jumps/circle jumps he currently cannot make
(aerowalk red, b2r, etc.)"; "I agree about 1.8 being movement focused. Please start a card for those items, I'll have another agent work
on it." The family's page: [README.md](../README.md). **A card started, not a design:** what is there today, the steps proposed, what to
measure first, the red team and the owner's open decisions. Nothing built, nothing run; the run starts only on the owner's command.*

**Started from:** ❓ 1.7a's end (to fill in at the start).

**Marks:** ✅ known or decided · ⏳ to build · 🧪 to measure · ❓ owner's decision

## For the agent who builds it

- Read [CLAUDE.md](../../../../CLAUDE.md)'s hard rules first. While 1.7a trains (until 21:00 on 11-06), **rule 9**: no side job (a
  measurement, a replay, a level check) starts without the owner's word, with its cores by mask, its length and what it shares with the
  run named. The trainer has the performance cores (`0xC03C3`); the watcher, the ramp and the self-play logger are on `0x3C3C`; 14 to 17
  (`0x3C000`) are the owner's.
- **Rule 10:** the design the owner approves is built whole. A real structural fork goes to him; an unspecified detail is decided from
  the design's intent and recorded here.
- **Rule 11:** a choice that is the sum of two learnt outputs (the way: the hands' rows plus the pointer's scores, `PADD`) is decayed
  (`H2_L2`) from the moment it is live; each part's size flagged over 40.
- Build on a branch of its own (`b18`) in a worktree without links into `data/` (rule 8); nothing in `sim/` of the main checkout changes
  while 1.7a trains (its checks re-import the simulator).
- Read [docs/HISTORY.md](../../../HISTORY.md) on v14 (Aerowalk's red armor), v15 (the jump runs), v0.3.6 and v0.3.7 (the rocket-jump
  runs: 1 rocket in 200 tries) and v0.4.0b (zones and Aerowalk's red-armor rocket jump) before proposing anything.

## What is there today ✅ (as 1.7a runs: `docs/runs/1.7/1.7a/train.cmd`)

| | |
|---|---|
| The jump lists | `sim/pro_gaps/<map>.json` (from the pros' demos, `tools/pro_gaps.py`; an entry's `"use"` is the owner's), drawn by `tools/draw_gaps.py`; the jumps his ways take in games: `JUMP_OPEN` (per map, by number); left out: `JUMP_SKIP=aerowalk:16`; `JUMPS=1`, `JUMP_ALL=1` (tries at jumps on no item's way too) |
| Jump practice | `JUMP_RUN_P=0` in 1.7a (jump runs off); the counters by map (`v15.runs_by_map`); `tools/jump_check.py` (him alone in jump runs) |
| The walker | `RULE_WALK` (2026-10-10): the rules and item runs count a walker's ways only, so a jump he cannot make is never named |
| The ways | `WAYS` off; `sim/ways.py`, `sim/pro_ways_legs/<map>.json` (of 2026-10-12, to re-measure: `tools/ways_check.py`); the way output's rows at bias 0, −20, −20 since v0.2.1 (always "the shortest"); the pointer's scores on each way built in 1.7, inert without the switch (B-301) |
| Rocket jumps | the runs built behind switches (B-252), off in 1.7a (`RJ_RUN_P` unset: 0); set in 1.7a: `RJ_ONLY=aerowalk:1`, `RJ_CLEARED=1` (only the rocket jumps a scripted player clears: `sim/rj_clear.json`, 77 of the pros' 174), `RJ_LOOK_P=0.5`, `RJ_TEACH=1` with its weight at 0 (live `RJ_TEACH_W`); the simulator's rocket jump set close to the game's by `RL_QL` and `QL_FLOAT` (RESULTS 2026-10-15 21:25); the specialist teacher of B-272 not built |
| The view's pull toward level | **already gone**: live `LEVEL_PULL` 1.0 in 1.7a (B-275: 1.0 = no pull). Not the cause of 1.7's rocket-jump numbers; v0.3.7's 1 rocket in 200 tries was under the old pull |
| Hop | `AUTO_HOP=1` in training (a held jump re-jumps on landing); the plugins give it only with `BOBBY_AUTOHOP=1` (B-269: whether the servers set it is unknown) |
| The movement network | `move_v17_look`, an input only (`LEGS_IN`) and its look point; the legs' switch retired (B-259) |

## The steps (proposed; ❓ the owner's at the card's review)

| Step | What | Done when |
|---|---|---|
| **1. Can each jump be made?** 🧪 (no training) | The list of the jumps the owner means, by map and number in `sim/pro_gaps` (Aerowalk's red armor; ❓ "b2r" and the rest: the owner names them; B-284's spots: Blood Run's stairs to the yellow armor, Toxicity's blocks, behind the teleporters). For each: the pros' take-off and way replayed in the simulator **under his hand limits** (`KEY_RATE` 8, his turn and flick limits, 125 fps): made or not, and the margin. Then him alone in jump runs on them (`jump_check.py`): his rate today. B-269 settled (held jump with auto-hop on and off, flat ground, stairs, ledges: the game against the simulator). The rocket jump re-checked against the game (rise, distance, self-damage, knockback) | a table: each jump, made by the pros' inputs under his hands (yes, no, the margin), his rate alone today, the game against the simulator. **A jump that cannot be made with his hands goes to the owner** (a fairness limit, or the simulator, or the jump left out) |
| **2. The ways, with the pros' jumps** | B-301 whole: the ways' tables re-measured; the pros' second and third ways with their jumps among his ways; the way output opened from "the shortest" by the pointer (`PADD` on the way, decayed: rule 11); jump practice at a share (`JUMP_RUN_P`) on the jumps of step 1 that can be made; a level check of the start (the 2026-10-11 rule) | the head takes a jump way where it pays; nothing names a jump |
| **3. Rocket jumps** | rocket-jump practice (`RJ_RUN_P`) on the cleared list, its start from the pros' 174 (B-272's specialist, or a fit of his own outputs to the scripted jumper's: ❓ the owner's, a teacher being one of the hard-wired parts to retire); the rocket-jump ways among the ways of step 2, priced by the health they cost | a rocket jump taken in games where it pays (Aerowalk's red armor first) |
| ❓ Weapon combos | the owner: "for later, possibly 1.8". Measured first (the pros' rocket hit or near miss followed within 0.6 s by the lightning gun, the rail or the shotgun, by map and range; his own; knockback and the flight after a hit, simulator against game); if a gap: two perceived inputs (the enemy in the air; the time since his splash hit, both read late as a person sees them) and a start for the weapon key fitted to the pros at those moments; no pay of its own | |

## Measured and judged by

| Measure | Wanted |
|---|---|
| Win rate against 1.7a's end; against b1.2d's end (the long-term control) | level or better at each step; under 40% flagged at once (rule 6) |
| Each named jump: tries, made, deaths and lava or falls on it, in practice and in games | made where it pays; Aerowalk's red armor taken over the jump |
| His ways: the share of each way, the jump ways' share, the trips' seconds, his predictability (B-217, B-190) | jump ways used where they win the race |
| Rocket jumps: tries, made, health spent, the item or place reached first | up where they pay; no rocket jumps that lose the stack fight |
| Aerowalk by itself (a map's number read per map: the 2026-10-10 lesson) | never the v14 fall |
| Speed, standing still, stuck at B-284's spots | hold; the stuck spots down |
| Big weapons owned, the mega and red armor first, frag share | hold |

## Red team (to complete when designed)

| Part | Hand-built or assumed | The measured alternative | Watch |
|---|---|---|---|
| The pros' jumps as the list | the pros' data | every jump the simulator finds possible (`JUMP_ALL`) | jumps the pros do not use |
| His hand limits on hard jumps | the fairness limits (owner) | none: a jump only a machine makes | a jump made with less margin than the pros |
| A teacher for rocket jumps (B-272) | a hard-wired part (owner, 10-23: retire them by fading) | practice and pay alone (1 in 200 tries made: B-272) | his rate once its weight fades |
| Jump practice's share | hand-set | a share by how often he fails each jump (the jump flow rule: open in games at 50% success, back at 25%) | ❓ a per-jump gate against rule 6's "never hold on its own" |
| The ways' choice opened by the pointer | 1.7's pattern | a soft rule | the way's share by update; the level check |
| The simulator's jump physics | measured once (10-15, 10-16) | measured again in step 1 | a jump made in the simulator, failed on the server |
| Pay pathologies (the ledger) | | | negative frags, sign flips, lopsided games |

## The owner's decisions

| | | |
|---|---|---|
| 1 | ✅ 1.8 is movement: rocket jumping and the strafe and circle jumps he cannot make | owner, 11-05 evening |
| 2 | ✅ item pay by effective stack (B-297) out: "we have a simpler implementation that works well enough" | owner, 11-05 evening |
| 3 | ❓ the jumps by name: Aerowalk's red armor; "b2r" and the rest | |
| 4 | ❓ the ways (B-301) in 1.8 (proposed: step 2) | |
| 5 | ❓ the steps as one run opened part after part, or a run a step | |
| 6 | ❓ a rocket-jump teacher (B-272) or practice and pay alone | |
| 7 | ❓ weapon combos in 1.8 or later | |
| 8 | ❓ cores and a time for step 1's measuring while 1.7a trains (rule 9) | |
| 9 | ❓ the length, the start: on his command | |

## The result

Not started: a card (11-05 evening); another agent plans and builds it.

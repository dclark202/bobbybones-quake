# 1.8: movement: the jumps he cannot make, the ways, rocket jumps

**The goal (owner, 2026-11-05 evening):** "we need to revisit movement: rocket jumping and the strafe jumps/circle jumps he currently
cannot make (aerowalk red, b2r, etc.)"; "I agree about 1.8 being movement focused." Weapon combos (a rocket to put him in the air, the
lightning gun to finish) are "for later, possibly 1.8". Item pay by effective stack (B-297) is out (owner, 11-05: "we have a simpler
implementation that works well enough").

**Starts from:** 1.7a's end (❓ the owner's call when 1.7a ends: its end, or its best save). **Nothing built, nothing run.** The owner has
another agent plan and build it; the run starts only on his command.

**Marks:** ✅ known or decided · ⏳ to build · 🧪 to measure · ❓ owner's decision

## Why these three belong together

A hard jump is worth something only as a way somewhere: a shorter way to the red armor, a way the enemy does not watch, a way out. In
1.7 the head chooses the target and the order, but his way to it is always the walker's shortest (B-301: the way output's rows sit at
bias 0, −20, −20 since v0.2.1). So a jump he learns in practice is never taken in a game unless a rule names it, and a rule naming a jump
he cannot make is what cost v14 Aerowalk (12% to 88% against v13 within 17 minutes, 2026-10-10: the item rule sent him to the red armor
over a circle jump). 1.8 lets the head choose the way, the pros' jump ways among them, and teaches the jumps so the choice is real.

## The steps (one new thing a round: the owner's rule of 10-24)

| Step | What | Why in this place |
|---|---|---|
| 1. Measured, no training 🧪 | Can each named jump be made **in the simulator, with his hands** (125 fps, `KEY_RATE` 8 actions a second, his turn limits)? Replay the pros' take-offs; `tools/jump_check.py`, `tools/label_check.py`. Settle B-269 (a held jump re-jumps: `AUTO_HOP=1` in training; on the servers only with `BOBBY_AUTOHOP=1`). Re-check the rocket jump against the game (`RL_QL`, `QL_FLOAT`: rise, self-damage, knockback; RESULTS 2026-10-15 21:25). | If a jump cannot be made in the simulator with his hands, no run finds it; if the simulator's physics is not the game's, he learns a jump that fails on the server |
| 2. The ways, with the pros' jumps in them | B-301: his item trips and the order's ways choose among the shortest and the pros' second and third ways (`WAYS=1`, `sim/ways.py`; the pointer's scores on each way, built in 1.7, inert without the switch), the ways' tables re-measured with today's legs and walking map (`tools/ways_check.py`), jump practice at a share | Nobody names a jump: the head takes a jump way only where it pays. The jumps a walker cannot make stay out of every rule (`RULE_WALK`, 2026-10-10) |
| 3. Rocket jumps | Practice runs on the pros' rocket jumps (174 in the demos, 77 cleared by the scripted rocket jumper: `sim/rj_clear.json`), the start from those; then the rocket-jump ways in the ways' choice | Last: a rocket jump costs health, so it is a way the head has to price, which needs step 2 |
| ❓ Weapon combos | A rocket to put the enemy in the air, then the lightning gun or the rail: measured in the pros' demos and in his games first; if a gap, two perceived inputs (the enemy in the air; the time since his splash hit) and a start for the weapon key fitted to the pros at those moments; no pay of its own | The owner: "for later, possibly 1.8". Step 1's physics check (knockback, flight after a hit) is the combo's too |

## The attempts

| Attempt | Started from | What | State | Result |
|---|---|---|---|---|
| [1.8a](1.8a/CARD.md) | ❓ 1.7a's end | ❓ to plan: steps 1 to 3 as one run opened one part after another, or one run a step | card started 11-05 evening; nothing built | |

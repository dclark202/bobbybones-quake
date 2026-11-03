# Teaching the hard jumps (proposal, 2026-10-29; not built, nothing started; the run: [v0.6.4](../runs/v0.6.4/CARD.md))

The three targets: rocket jumps (B-212, B-252, B-272), two-hop strafe jumps such as Campgrounds' bridge to rail
(`pro_gaps` id 9, "b2r"), Aerowalk's red armor circle jump (id 1). For after v0.6.2. End state: one movement
network, his own legs branch. The teacher networks are scaffolding and are removed at the end.

## Why the old practice stalled

The problem is exploration, not reward. On-policy PPO from his own policy never finds the sequence, so there is no
success to learn from:

| Jump | His record | Makeable in the simulator? |
|---|---|---|
| Rocket jumps | Fired in under 1 of 200 tries, 0.1-0.3% made (v0.3.7). On Aerowalk's red armor 0 rockets in about 420 tries: the view's pull toward level took his pitch from 70° to 54° | Yes: a scripted player clears 104 of 174 links, and `RJ_COPY`'s pupil 80% |
| b2r | 0 of about 2,700 practice tries; the movement teacher's pupil 0% | Yes: the pros' inferred keys land it 84 of 89 times |
| Aerowalk red armor | 2%, then 13-16% with the pros' run-ups. Half his tries never jump; the rest take off at about 340 u/s against the 425 needed | Yes: `ROUTE_COPY`'s two-hop route 62-66% |

Copying the scripted routes as labels (`RJ_COPY`, `ROUTE_COPY`) works, but it is the hard-wired path you don't
want. Grading his whole network against a teacher (`--legs-teach`) cost 51% → 36%.

## The proposal: specialist teachers, then distill into the legs branch

### Step 1: a library of makes, made by search

For each target jump, collect thousands of successful runs in the simulator, under his hands (finger and mouse limits,
aim2). Seed the search, then let a random search over key and mouse sequences (cross-entropy) widen it:

- **b2r:** the pros' run-up states (`sim/pro_jump_starts/campgrounds.npz`) and their inferred keys.
- **Aerowalk red armor:** the pros' run-ups and the two-hop route.
- **Rocket jumps:** the pros' 5,039 rocket jumps in `docs/pro_rocket_jumps.json` and the 104 cleared links.

The search keeps only runs that land, and keeps them varied: different run-ups, take-off places and timing. This
matches your rule that the path, not one exact key sequence, is what's taught. These runs are data, not labels for him.

### Step 2: three small teacher networks, one per family

The families are the rocket jump, the multi-hop strafe and the circle jump. Each is trained in `movement_env` with
`train_move.py`, pay = arrive + time only, as today. Two changes break the exploration wall:

- **Start from the end and move back.** The first tries start mid-air on a successful run, close to landing. As the
  teacher succeeds from there (say ≥70%), its start moves back along the run: the take-off, then the run-up, then 2-3 s
  before it. Every stage pays only for landing, so the pay stays honest. Search terms: reverse curriculum, backplay,
  Go-Explore.
- **Start by imitating the library, then let it go.** The teachers begin with a copy loss on the library, faded to
  zero over the run, so the end result is what RL keeps.

**Pass test (`tools/label_check.py`, his hands):** at least 60% made from varied run-ups. The rocket jumps must also
pass on the game's own physics (`plugins/rjlab.py` on a private server).

### Step 3: distill into his legs branch, off-line, before any run

The legs branch is a separate block in his network (61 → 256 → 256 → 17), so it can be refitted on its own without
moving the shared layers. It does not drive him: since v0.3.5 (`--no-switch 1`) his own outputs always drive.
The branch reaches them two ways:

- **`--legs-gate`:** its choice is added to his movement outputs (forward, sideways, jump, turn, walk, zoom), weighted by
  a gate read from his memory.
- **`--legs-feat`:** its hidden layer goes into his memory.

The teachers take the branch's own 61 inputs and give the same 17 outputs, so the step is a plain copy. The teachers
start as copies of his current branch. **Pitch and fire are not in this channel**, and a rocket jump needs both (look
down, fire, jump). For the rocket-jump teacher, the gate is widened to pitch and fire: new outputs at zero, the same
mechanism, and his gate decides whether to listen.

How it is fitted:

- **What it is fitted to:** a mix of (a) frames from his own games with his current branch's answers, so it keeps
  what it does, and (b) frames at the target jumps with the teachers' answers.
- **Cycles (DAgger):** the refitted branch plays the jump runs; the teacher labels the frames it reaches; repeat.
- **Pass tests:**
  - In games he plays as before: same-answer check, then 160 games against his unchanged self, about 50%.
  - The jump runs pass alone, with no teacher.

This is how your earlier rule is kept: the teacher never touches the shared layers.

### Step 4: one run, practice back in, the teachers gone

The trainer starts from the refitted network:

- **Practice back in:** jump runs and rocket-jump runs, shut at the start, then opened slowly to a few percent of all
  training and tied to the checks.
- **Pay:** only for landing in practice; win chance in games.
- **Routes:** the three jumps go into his routes (`JUMP_OPEN`; the rocket-jump links) only once practice is at least 50%
  (the jump-flow rule), and come back out if it falls under 25%.
- **No teacher is in the run.** Whether he uses a jump in a game is left to the win-chance pay and the strategy head.

## What must change first

1. **The view's pull toward level (B-275) blocks the rocket jump.** People look down at their feet freely. The pull is
   a hand-built rule and is not one of the fairness limits. The owner fades it in v0.6.1 (2026-10-29), so it is at 1.0
   by v0.6.4. The rocket-jump teacher trains at 1.0 (the teacher has the pupil's hands).
2. **His routes have no way to Aerowalk's red armor** (B-114 and related). The jump links have to be in the routes
   before the head can choose it.
3. **Check the game's own physics on all three jumps.** Running rocket jumps were 30/30 after the `QL_*` fixes, but b2r
   and the circle jump have not been checked against the real game.

## Red team

**Hand-built or assumed parts, and what was measured instead:**

| Part | What was measured |
|---|---|
| Which jumps are taught (your B-204 list) | The pros' frequencies in `pro_gaps` |
| The library's seeds: inferred keys, scripted routes | Gone after step 2: the copy loss fades to zero and the teacher keeps only what lands under RL |
| The step-back threshold, the pass bars (60%, 50% / 25%) | None. Pass bars are choices |
| The DAgger mix between his games and the jumps | Tuned on the same-answer check |

**What the equilibrium may bring out:**

| Risk | What holds it |
|---|---|
| Rocket jumps cost health, so he may rocket-jump in fights or too often | The win-chance pay prices it. Watch the panel for rocket jumps per game and the health lost to them |
| A jump under fire, against your "no jumping in fights" | Watch jump tries with the enemy in view |
| Losing what the branch already does in games | The same-answer check and the 160 games of step 3 |
| The lasting risk: the jump is learned in practice and never used in games | Then the head doesn't value it, a strategy question and not movement. The check: how often he takes the jump with the item up |

**Ledger checks, as always:** negative frags, sign flips, lopsided games.

**The alternative without teachers:** start from the end and move back, inside the main run. It is cheaper to build,
but every practice update moves the whole network, which already cost aim once. The teachers keep the risky learning
outside his network until it is proven.

## Order and cost

- **Steps 1 and 2:** the simulator only; can run beside v0.6.2 on idle cores at low priority. Each needs your go.
- **Step 3:** hours.
- **Step 4:** one round with one new thing (the practice and the refitted branch count as one: the branch is checked
  equal before the start).

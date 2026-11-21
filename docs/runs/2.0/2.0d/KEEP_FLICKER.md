# The keep choice's flicker: the problem, where it stands in 2.0d, and what 2.1 plans for it

Written 2026-11-13 (owner: "Write the summary of this problem, with context and what is planned for 'fixing it' in 2.1. I will have another
agent review"), while 2.0d trains (RUNS.md #50). Sources are linked; numbers are quoted from them, not re-measured unless said.

## 1. What the keep choice is

Since 1.7a, Bobby's strategy head picks a **target** (one of 17: nothing, the items, the weapons, the enemy, the holding places). The
**keep choice** decides how long he stays on it. Five times a second, at the head's tick, it gives the probability of **re-deciding**
(drawing a new target) against keeping the one he has. It replaced the hand-built **8-second lock** (a target lasted 8 s unless a
release fired), which the owner has ruled out for good (CLAUDE.md rule 13: "Once a hand-built rule is out it never comes back").

Its form ([1.7a's card](../../1.7/1.7a/CARD.md), "The keep choice"; built in 1.4c): one layer of the head,
P(re-decide) = σ(w_s·s + w_h·h + w_age·age + w_c·contact + w_lp·lp_held + w_a·arrived + w_t·since_arrival + b). The inputs:

- s: the head's memory, the only part that learns through the head;
- h: the hands' memory;
- age: seconds on the target;
- contact: the enemy seen or heard in the last 2 s;
- lp_held: the held target's log-probability under the present scores;
- arrived, and the seconds since arrival.

It learns in the head's own policy term: the head's advantage (λ 0.995, about 5 s), no entropy bonus and no pay of its own. It started as
the lock made soft on age and contact, and became the head's decision as the weights on s grew.

## 2. The problem: it drifts into flicker

**Flicker** here means changing target so often that he rarely reaches one. Three measures, logged every update (`ramp_20d.py`):

| Measure | What it counts |
|---|---|
| Trips a player-minute | changes to a *different* target (`sim/duel_env.py`, the trip counter) |
| Targets reached | the share of targets reached before being left |
| Quiet re-decisions a reading | re-decisions with no contact and nothing heard: the ones that cannot be a reaction to the fight |

**In 1.7a** ([postmortem](../../1.7/1.7a/POSTMORTEM.md), "The keep choice"):

| Update | Trips a player-minute | Reached | Quiet re-decisions a reading | Games (against 1.6a's end) |
|---|---|---|---|---|
| 10 (the lock) | 23.9 | 24% | | |
| 50 | 35.6 | 17% | 0.042 | 53.5% |
| 90 | 58.3 | 11% | 0.054 | **63.0%** |
| 130 | 61.1 | 10% | 0.054 | 63–64% |
| 170 | 68.3 | 10% | 0.088 | |
| 240 | 80.8 | 8% | 0.125 | falling |

- **What worked:** the choice became the head's own (its pull from the head's memory rose 0.2 → 3.4), and games rose with it, to 63%.
  Keeping a target through a fight and leaving it when the fight changes is worth games.
- **What did not:** by update 240 he took a new target every 0.75 s and left 92% of them before reaching them. Re-deciding in contact
  (0.96 a reading) is the choice's job. **Re-deciding out of contact with nothing heard rose 0.030 → 0.125 a reading** (14% → 49% a
  second): drift, not a reaction to anything. It did not cost games until update 130; after that, the slide in games and the quiet
  re-decisions grew together.
- **1.7b drifted the same way** ([HISTORY.md](../../../HISTORY.md), "The keep choice drifts into flicker").
- **The same pattern without a head:** b1.1a faded the lock to 1 s with no learned chooser (trips 12.6 → 20, reached 40% → 21%, frags
  down). The lesson in HISTORY: "Freedom without a head to use it becomes flicker."

**Why it may drift** (hypotheses, not measured):
1. Nothing in its lesson prices a re-decision. There is no entropy bonus and no cost, and the advantage is noisy over about 5 s, so a
   small preference for re-deciding is never pushed back. (A switching cost would be a hand-set price: the owner removed the switch cost
   in 1.4b.)
2. Its main input, s, also carries the target scores. As the head's memory grows sharper and moves faster, a fresh draw looks better
   more often. The pull from s grew 1.4 → 3.4 between updates 90 and 240, alongside the flicker.
3. The lesson only sees readings the keep choice itself decided, so the cost of leaving a target is credited over a short horizon,
   while the cost of never arriving is long.

**1.7c froze it** (`--keep-freeze 1`: it plays at its share but learns nothing; [1.7c's card](../../1.7/1.7c/CARD.md)). 1.7c was a test
of the pros' weapon table and was stopped at update 62 with no gain (a false start before it was a PPO mask bug), so freezing was never
judged on its own. The weakness its card names: "frozen,
it cannot adapt to the new fights either."

## 3. Where it stands in 2.0d

2.0d starts from **1.7a's update 90**, the point where the games peaked and the flicker had already begun. The owner chose to keep the
choice **learning, flagged** (11-13); the alternative was frozen. The share went 0.975 → 1 at the start (the lock's last 2.5% out).
`ramp_20d.py` flags trips over 70, reached under 9%, quiet re-decisions over 0.08. **Its flags report; nothing stops or holds the run**
(CLAUDE.md rule 6).

The first eleven updates (`data/sim_runs/duel_gru_2_0d/watch/watch.log`, local):

| Update | 1 | 2 | 3 | 4 | 5 | 6 | 7 | 8 | 11 |
|---|---|---|---|---|---|---|---|---|---|
| Trips a player-minute | 66.4 | 61.2 | 60.2 | 63.0 | 63.8 | 60.8 | 65.1 | 67.9 | 65.5 |
| Reached | 12.4% | 10.4% | 9.3% | 9.5% | 10.4% | 9.7% | 9.6% | 8.8% | 8.9% |
| Quiet re-decisions a reading | 0.017 | 0.039 | 0.051 | 0.052 | 0.044 | 0.038 | 0.045 | 0.046 | |

- The start sits at 1.7a's update-90 level (58 trips, 11%), so the 9% "reached" line was crossed at updates 8 and 11 without a trend.
- The quiet re-decisions (0.04–0.05) are below their 0.08 line and at 1.7a's update-90 value (0.054).
- **What 2.0d can tell:** whether the drift resumes while AIM3, the corrected knockback and the dodge inputs come in. In 1.7a it took
  until about update 130–170 (40–80 updates past update 90) to grow clearly. 2.0d is 90 updates long, so it covers about the stretch
  where 1.7a's drift became visible.
- **The owner's thought (11-13):** "perhaps it makes sense to train with this decision frozen? we'll have to see how it goes." Freezing
  is not live: it needs a restart at a save (every 10 updates) with `--keep-freeze 1`, the optimizer kept and `--fade-start` passed.
  Nothing is changed unless the owner decides.

## 4. What 2.1 plans for it

From the current plan ([2.1a's card](../../2.1/2.1a/CARD.md), rewritten 11-13; [2.1's DESIGN](../../2.1/DESIGN.md);
[1.9a's postmortem](../../1.9/1.9a/POSTMORTEM.md); [PLAN_FROM_17A](../../2.1/PLAN_FROM_17A.md)):

| Round | What happens to the keep choice | Status |
|---|---|---|
| **2.1a** (the head learns to choose an instruction, silently) | **Untouched.** "Every game seat is chosen as 2.0d's end chooses (its head's target, the keep choice, its weapon part), all still learning"; the keep choice's three flags carried over | sketch for the owner's review |
| **2.2** (the head takes seats: its instruction replaces the target on game seats) | "**commitment by the chooser itself** (every 0.2 s, no timer; a learned slow prior if its orders do not stand)" | named, not designed |
| DESIGN.md (the full 2.1 design) | the keep choice becomes "stay or take the new instruction", read only from the **change signals** (about 6 inputs: the enemy came into view, a sound, the belief's shift since he committed, an item's clock crossing the time to get there), paid by the game's pay | designed, not built |

**What is NOT planned any more:**
- **The 1-second redraw.** 2.1a's earlier build (from 1.8a, never started; [INSTRUCTION.md](../../2.1/INSTRUCTION.md), "2.1a") redrew
  a standing instruction one second after its last draw (`head2.ins_redo`), or at once on done, failed or a wake. That is a hand-set
  timer; PLAN_FROM_17A put it to the owner (open question 5: "commitment under the instruction"), and the rewritten card drops it for
  2.2's "no timer".
- **The lock.** It never returns (rule 13).

**1.9a's lesson** (its postmortem): "No re-decision every tick without commitment from the chooser itself. It can be a learned keep
choice (as 1.7a's), or the choice re-read as 'keep or change' with its own value. It must not be the lock ... Only a sharp scorer can
re-choose every 0.2 s." In 1.9a the head, re-choosing every tick without commitment, took the seats nearly uniformly and flipped the
bound weapon up to 107 times a minute; the checks fell to 2.5%.

**So the fix as planned has two parts, neither built:**
1. **Inputs that make a quiet re-decision unjustifiable:** the change signals only (DESIGN.md). Out of contact, with nothing new, the
   keep choice would have nothing to react to, which addresses the quiet re-decisions directly, unlike today's s, which carries the
   whole head memory.
2. **Commitment owned by the chooser** (2.2): its own value of keeping against changing, or a learned slow prior, rather than a timer.

## 5. Open questions for the review

1. **Is the drift a property of the inputs (s) or of the lesson (no price on re-deciding)?** The DESIGN fix changes the inputs only. If
   the lesson is the cause, a change-signals-only keep choice may still drift, more slowly. A measurement that could tell: 1.7a's
   update-130 or -240 save with s's weight zeroed (the change signals approximated by contact, age, arrived), quiet re-decisions over
   200 games. The 1.7a postmortem proposed a related level check (the update-130 save with `PADD` 0 against 0.3); it was never run.
2. **Does the flicker cost games before it is extreme?** 1.7a held 63% to update 130 with 61 trips and 10% reached. If the cost only
   comes past roughly 0.08 quiet re-decisions, the flag line is the right alarm. If the cost is gradual, 2.0d's start already pays some.
3. **Frozen or learning through 2.1a?** 2.1a keeps it learning on game seats while the instruction learns silently. A frozen keep choice
   gives 2.1a a fixed baseline to compare against (its checks are against 2.0d's end) but cannot adapt to AIM3 or the dodge inputs.
   This is the owner's decision; 2.0d's numbers by its end should inform it.
4. **Is "trips" the right measure?** It counts changes to a different target, so a re-decision that redraws the same target counts as a
   keep. The quiet re-decisions count the decision itself and look like the cleaner signal of drift.
5. **The interaction with 2.2's chooser.** If 2.2's instruction chooser owns its own commitment, the keep choice's role shrinks to
   "stay or take the new instruction". Does 2.2 then still need the keep choice at all, or does the chooser's "keep" option replace it?
   DESIGN.md keeps both; the 2.2 line says "commitment by the chooser itself". These should be reconciled before 2.2 is designed.

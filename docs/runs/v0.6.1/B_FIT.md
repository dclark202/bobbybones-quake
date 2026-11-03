# B: fitting Bobby's chance of winning — the problem and a proposed approach

*2026-10-28, for review. Code: [tools/run/fit_b.py](../../../tools/run/fit_b.py). Data: the self-play games v0.6.0 logs while it
trains ([tools/run/selfplay_loop.py](../../../tools/run/selfplay_loop.py)).*

## 1. What B is for

v0.6.1 pays Bobby by his chance of winning only. Every frame his pay is the change in that chance:

    pay(t) = WIN_GAIN x ( P(state at t) - P(state at t-1) ),   and at the game's end P = the result (1 won, 0 lost, 0.5 level)

`P` is a formula that reads the state of the game and says how likely he is to win from there. **B** is that formula fitted
directly on how his own games ended (the owner's choice of 2026-10-28, over the hand-built formula used so far).

One property matters for everything below. Over a whole game the pay adds up to `result - P(start)`, whatever `P` is
(the sum telescopes). So **P does not change what Bobby is being asked to do (win)**, apart from a small effect of the
discount (gamma 0.999 a frame). What P changes is *when* he is told a move was good: a correct P pays a hit or a mega on the
frame it happens; a wrong P pays it wrongly then and takes it back later, which makes learning slower and noisier. A P that
says a frag *lowers* his chance would tell him, on that frame, that killing was a mistake.

## 2. The data

Self-play games of v0.6.0's saves 40, 60, 80, 100 and 120: 6 games a map on the ten maps, so 60 games a save and 300 in all
(owner, 2026-10-28). The aim is v0.6.0's own on both seats. One row a second per game: the score, both players' health and
armor, which big weapons each owns (rocket launcher, lightning gun, railgun), who is dead, the time left.
Label: the game's final result for seat 0.

- **A game is one outcome.** Its ~600 rows are not independent, so every interval is by whole games resampled.
- Overtime rows are left out of the fit (overtime is a short game of its own).
- Seats are swapped in every second game, and both seats are the same network, so the fit is symmetric by construction.

## 3. The formula as designed (this morning) and what went wrong

    P(win) = Phi( (d + mu) / s )
      d   his lead in frags
      s   = sqrt(v x time_left + v0)                         how many frags can still swing (a random walk)
      mu  = c x tanh(u) x (1 - exp(-time_left / tau))        what his stack and weapons are worth, in frags
      u   = a x tanh(stack_diff / 300) + bRL dRL + bLG dLG + bRG dRG
      stack_diff = (his health + armor) - (the enemy's); a dead player counts as his respawn (125, no weapons)
      dX  = he owns X minus the enemy owns X (-1, 0 or 1)

The design capped **c at 0.5**, so the stack and weapons are never worth more than half a frag. The reason: a frag adds 1 to
`d`, and `mu` can then move by at most 1, so a frag can never lower his chance.

**Test on last night's 60 surviving games** (save ~130 of the lost run, fitted with 5 folds by game):

| formula | held-out log loss (lower is better) |
|---|---|
| the pro table by score and time only (no stacks) | 0.559 |
| the simulator's current formula (pro table + the 10-26 stack term) | 0.538 |
| B, c capped at 0.5 | 0.485 |
| B, c free (up to 3) | 0.477 |
| a small free network, no structure | 0.481 |

B predicts results clearly better than what the simulator has now. But both versions of B misbehave:

**(a) Capped: the cap is always hit, and the fit turns into a step.** The data wants the stack worth more than half a frag,
so the fit pushes c to 0.5 and makes `a` huge (108) so that `tanh` saturates. Then *any* stack advantage, however small, is
worth exactly half a frag:

| event (level score, 5:00 left) | capped B: change in his chance, points |
|---|---|
| 100-damage hit | +3.3 |
| mega | +3.3 |
| red armor | +3.3 |
| rail taken | +3.3 |

A 10-damage hit would also be worth about +3.3. As a pay that is wrong: it would teach him that the first point of damage is
worth everything and the rest nothing.

**(b) Free: sensible values mid-game, nonsense at the very end.** With c free the fit finds c 2.7 (a big stack edge is worth up
to ~2.7 frags) and sensible weights (`a` 2.5; the rail and the rocket launcher about 0). Mid-game the values look right (5:00
left, level: a 100-damage hit +9.8, a mega +11.1, a frag from full +14.3). But `tau` comes out at 1.4 s, so the stack's worth
does not shrink until the last second or two. With 10 s left, killing a 1-hp enemy (who then respawns at 125) *lowers* his
chance by up to 23 points. The check found **800 states** (of 5,508 on the test grid) where a frag lowers his chance, all in
the last seconds (the worst five all at 10 s left; how far back the violations reach was not yet tabulated). There are few
rows there to fit on, so the formula's shape decides, and that shape is wrong there.

## 4. Proposed approach

Keep B's shape, let c be free, and **add the rule "a frag never lowers his chance, a death never raises it" as a constraint of
the fit itself**, not as a cap on one number.

1. On a grid of states (lead -8..+8; time left 600 s down to 1 s; both stacks from 1 to 200; weapon sets), for every frag
   (before: the enemy alive at his stack; after: lead +1, the enemy at his respawn's 125 with no weapons) require
   P(after) >= P(before) + a small margin. The same for a death from his side (by symmetry it is the same constraint).
2. Fit by maximum likelihood plus a large penalty on any violation: lambda x sum( max(0, P_before - P_after + margin)^2 ).
   After the fit, check with zero tolerance on a finer grid than the one penalised; any violation = not used.
3. Optionally give the time factor a floor that is sensible on its face: the stack edge cannot outlast the time it takes to
   turn it into a frag (e.g. `tau` >= 10 s). The constraint in step 1 should make this unnecessary; to be checked.
4. Report as `fit_b.py` does now: held-out log loss against the current formula and the free network; the value table
   (hit, frags, death, mega, red armor, rail, rocket launcher) at several leads and times, with 95% intervals by games
   resampled; drift between the five saves; the violation check.

**Acceptance (before it goes into the simulator):**
- no violation on the fine grid;
- held-out log loss no worse than "B, c free" by more than its own 95% interval, and better than the current formula;
- a 100-damage hit, a mega and a red armor get *different* values, rising with the size of the stack change;
- the values for a frag and a death have the right sign everywhere, and their size shrinks with a big lead late;
- the five saves agree within their intervals (no strong drift during the run).

### Alternatives considered

| | for | against |
|---|---|---|
| **Keep the 0.5 cap** (as designed) | safe by construction | saturates (above): a wrong pay for hits and items |
| **c free, no constraint** | fits best | pays a frag negative late in the game |
| **Constrained fit (proposed)** | fits nearly as well as free, right sign everywhere | the constraint holds on a grid only: needs the fine-grid check |
| **A free network** (no formula) | no shape to get wrong | no guarantee of sign or smoothness; harder to read and check; the simulator would need to run it every frame |
| **Shape that cannot violate** (e.g. the stack worth at most one frag, through the chance of the next frag) | guaranteed without a grid | it is close to the current formula, which predicts worse (0.538) and paid a frag negative in the 10-27 calibration |

## 5. What goes into the simulator afterwards

The simulator's current win pay has the old shape (a pro table by score and time, plus the old stack term). B's shape is
different, so the simulator needs B as a new option behind a switch (off = today's simulator, proven identical in fixed-seed
runs), reading B's fitted numbers from a file. Two follow-ups:
- **The separate shaping** (`WIN_SHAPE_K`, designed to pay hits and items on the frame they happen) is probably not needed
  with B: B already reads the stacks, so a hit changes P on its frame. Proposal: `WIN_SHAPE_K` 0 with B.
- **`WIN_GAIN`** (the size of the win pay against the current pay) is measured on v0.6.0's end after the run, with B.

## 6. Known limits (for the reviewer)

- Health and armor are added up. Armor absorbs two thirds of damage, so 100 armor is worth more than 100 health. The fit
  cannot tell a mega from a red armor of the same size. A refinement: effective health = health + min(armor, 2 x health).
- Weapons owned only; ammunition and the weapon in hand are not in it.
- The data is Bobby against himself. As a pay in self-play that is what matters; against people the chance would differ.
- 300 games: precise enough for the slope of the score and the main stack weight (about +-7%), weaker on rare states
  (big leads late, the rail).
- The saves cover updates 40 to 120 of one run; the network changes in between. The per-save drift check is there for that.

## 7. Questions for the reviewer

1. Is a constraint on a grid of states the right way to enforce the frag/death sign, or is there a shape that guarantees it
   without losing the fit?
2. Is the telescoping argument (section 1) right for this pay, given the discount of 0.999 a frame and the overtime rule (the
   last frame of each overtime period pays the period's result)?
3. Should the stack use effective health (armor absorbs two thirds) instead of health + armor?
4. Is the separate shaping really redundant with B?
5. Anything in the data (one row a second, self-play, 300 games from five saves) that makes this fit unreliable?

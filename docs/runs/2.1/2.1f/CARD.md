# 2.1f: an outlook for each goal (DRAFT, 2026-11-16; for the owner's design review; not approved, not built)

| | |
|---|---|
| Started from | **2.1d's end** (`duel_gru_2_1d/keep/policy_end_21d.pt`, update 158), so it is a clean comparison with 2.1e: both branch from the same network |
| State | **draft for discussion.** Possibly tonight's run, beside 2.1e's result |
| Length | to be asked |

## The owner's page

**The idea (owner, 11-16).** 2.1e's slow half "just provides a slow (and currently worse) approximation of what the pull already does".
What is wanted is a part that thinks ahead: "he's thinking in the hypothetical future (8 s ahead) and pulling towards what will have the
best outlook in the forward time window ... 'If I take this fight will it...'".

**What it is.** For each goal he can choose, the head learns an **outlook**: if I commit to this goal from here, how do the next seconds
go. The pull says "this is what I am committed to"; the outlook says "this is what is worth committing to". The outlook is added to his
choice by a dial that starts at zero.

**How it differs from what failed.** 2.1a and 2.1b asked the same question and learnt nothing: they froze a moment, played it two ways and
compared, about 8,000 comparisons in all, each one noise many times the effect. Since 2.1c he commits to a goal and holds it for a trip,
so **every trip he plays is an example**: from this situation, committed to this goal, this is what followed. That is hundreds of
thousands of examples an update, no forks.

**What it is not.** No new goals, no new opponents, no change of pay. "Take this fight or not" is not one of his 17 goals today (fighting
is the hands'); that question comes when break off and engage are rows in 2.2, judged by this same outlook.

## What happens every 0.2 s (with the outlook open)

1. The head scores the 17 goals: the hands' rows + the head's scores, as now.
2. The pull is added: `PULL_G` x log(the plan's odds), as in 2.1d.
3. **New: the outlook is added**: `OUT_G` x (the outlook of each goal less their average here, in units of its usual spread), so it only
   moves goals against each other and the dial means the same whatever the label's size.
4. The held draw picks and holds, as now.

## What the outlook learns from

| | |
|---|---|
| The examples | his own held trips: at the reading where he took a goal, the situation (the head's state) and the goal; nothing is forced, nothing is forked |
| The label | what followed that reading. **Four outlooks learn side by side, one plays** (live `OUT_PICK`): `ret` = the head's own return, the quantity its value already learns (the whole pay, credit about 12 s); `all8` = the whole pay over the next 8 s; `win8` = the win-chance part only over 8 s; `win5` = the same over 5 s. A death cuts the window |
| What is taught | only the outlook of the goal he was on (the other 16 get no label from that trip) |
| What the four are for | the window (the owner's 8 s against the head's 12 s) and the pay (whole against win chance only) are both open questions; each is read silently on its skill before anything plays. The win-chance ones are evidence for the owner's open question on the head's pay, at no risk |
| The yardstick | beside each outlook, the same label predicted **without knowing the goal**. The outlook's skill above that is what knowing the goal adds: if it adds nothing, choosing among these goals cannot be learnt this way |
| What it never learns from | a pro's choice, a rule, a table (rules 12, 13) |

## The run (proposed)

| Stage | Updates | What is live | Read before the next (reported; the owner decides; the ramp never holds) |
|---|---|---|---|
| 1. Silent | 1 to 30 | nothing new plays; both outlooks learn | **skill on trips it has not learnt from**: does a higher predicted outlook go with a better result, per goal and across goals; how far apart the goals' outlooks are in one situation (if they barely differ, choosing among the 17 has little to gain and the value is in 2.2's new plays); which outlook, (a) or (b), predicts better |
| 2. Opens | 30 to 70 | `OUT_G` 0 → its mark (set from stage 1: the size at which it moves about as many choices as the pull at 0.5) | he fights (frags, damage a minute); the checks against 2.1d's end; the kinds of his changes of mind (the new readout) |
| 3. Hold | 70 to the end | open | the end checks; 200 games with the outlook at 0 |

## What would be built (an Opus 5.5 subagent; branch `b21f`)

1. The outlook inside the head (`head2.out.*`): from the head's state, 17 numbers for each of the two outlooks; last layer at zero.
2. Its lesson on the learner's copy from the rollout's held trips, its own Adam; rule 11's decay; sizes recorded.
3. The term in the target choice, as played and as learnt (stored, and in the proof), live `OUT_G` (and which outlook plays).
4. Readouts: held-out skill, the spread between goals, the share of his choices that are the outlook's top, how often each goal gets a label.
5. Every reader of a network file (the checks' player, the server's pass, the export), the init tool with `same`, the run's files.
6. The new readouts of his changes of mind (branch `b22r`) come with it.

## Trial trips (built, off by default)

A dial (`OUT_TRIAL`, 0 at the start) that on a small share of his new draws gives him a goal picked evenly among those open to him, held
to the trip's end. It is the guard against an outlook that only knows his favourites, and the way 2.2 would open a new play. Such a trip
teaches the outlook; it is left out of the lesson that shapes his own choice, since he did not choose it. Not opened without the owner's word.

## Red team

| Hand-built or assumed | Its weakness, and the guard |
|---|---|
| "Trips are enough data" | the claim this whole card rests on. Stage 1 measures it before anything plays; if there is no held-out skill at update 30, stage 2 is not opened and that is the finding |
| It only knows the goals he chooses | a goal he rarely takes in a kind of situation has a poor outlook there, and he chooses goals where they are good, so the examples flatter them. Guards: the term is only the difference between goals; a count per goal and situation; if needed, a small share of trial trips on a goal he would not have taken (the mechanism 2.2 needs anyway) |
| It can feed on itself | he chooses by the outlook, which is taught by his choices. The pull has the same loop and held; the dial opens slowly and every sum is decayed (rule 11) |
| The label's window | the head's own return (about 12 s) is the pay's choice, not a measured one. A fixed 8 s window is the alternative; both can be read silently |
| A sum of four learned parts now picks his goal (hands, head, pull, outlook) | rule 11 on each; each part's size flagged over 40; the proof extended |
| The mark for `OUT_G` | hand-set from a readout; opened slowly and reported |
| Choosing among 17 item goals may not be where games are won | then the outlook shows little here and its worth is as the way 2.2's plays are judged. Said plainly at update 30 |

Ledger pathology checks as every card.

## Research check (rule 14)

1. **The game** (MECHANICS.md): none touched; no simulator value used.
2. **What wins** (DUEL_STRATEGY.md principles 1 to 4, PRO_INTERVIEWS.md 4.2): "fight when your stack and position give you the edge", timing as "the map's clock made into plans": both are judgements of a choice by what follows. Works against none.
3. **The player's view**: the outlook reads only the head's state, which holds what he perceives and remembers. No new input.
4. **In and out of control**: the same part for both. Risk: an outlook learnt mostly in control may misjudge the out-of-control situations; read the skill by stack difference.
5. **Self-play equilibrium**: no pay change. Both copies choose goals by learnt consequences; an outlook that flatters one item would show as camping (guarded).
6. **Bot precedent** (BOTS.md idea 1: "teach the head on every tick by predicting each order's outcome, and open its seats on a readiness mark"; its named risks: "orders the hands never carry out get no data", values "reflect the hands' current habits"). Also IntelAct (3.1: acting by predicting future measurements for each action). Differences: examples from held trips, not forced orders; opened by a dial on a measured skill.
7. **Rule 12**: no pro number used.

## My odds (rule 15)

The silent outlook shows real skill at ranking goals: about 65%. Opened, it shows a gain against 2.1d's end in one night: 30 to 35%.
Whatever the night shows, it is the part 2.2's plays would be judged by.

## Before a go

- The owner's review of this design; the label's window; which outlook plays if both show skill.
- The build's tests (identity at zero, the smoke, the live test, the proof, the server's pass).
- The length.

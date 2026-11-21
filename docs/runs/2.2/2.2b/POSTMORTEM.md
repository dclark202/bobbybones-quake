# 2.2b: postmortem

Written 2026-11-18 by the planning session, from the monitoring session's night report, the run's own records
(`data/sim_runs/duel_gru_2_2b/metrics.jsonl`, `watch/`), the trainer's code, [the card](CARD.md), `HISTORY.md` and `RUNS.md` (#59, #60).
The run: restarted 11-17 20:37 from 2.2a's update 90, stopped by the owner 11-18 07:05 at update 99.

> **What followed (11-18):** the owner's reading under "What every failed attempt shared" stands. The sections "The next run", "The
> fallback", "Risks and odds" and "Your decisions" below are the planning session's first proposal and are superseded by
> [2.2c's card](../2.2c/CARD.md) (started 11-18 12:34 from 2.2a's update 90). The owner asked for no more odds; those below are kept
> only as the record.

## The verdict

**The run failed at its aim, and from update 60 it made him worse.** Up to update 60 he played level with his start. From update 60
the four fight options went into his list and his own "go after the enemy" and "go to a standing place" were taken out. What came in
was backing off and walking to a spot where the enemy was predicted to pass; going at him and holding an angle never came in. He
fought less and lost to his start.

| Check | Against | Games won-lost |
|---|---|---|
| Update 10 | the start | 99-101 |
| Update 30 | the start | 116-84 |
| Update 50 | the start | 93-107 |
| Update 70 | 2.1d's end | 86-114 (the start scored 125-75 against it) |
| Update 90 | the start | 59-101 after 8 of 10 maps |

The first three are level with the start: together 308-292, and one check moves about 7 points by chance. I do not read a fall
between updates 30 and 50. The fall is stage 2.

**What worked:** the restart's fix (gauntlet in hand 0.2 to 0.5% all night; the frozen item picker never moved; its weapon push gone
by update 9). The new pay arrangement (each network paid for its own job, the judge that reads the items, the near-miss pay) cost
nothing in 60 updates. It also showed no gain.

## What happened in stage 2

Share of his decisions, from the trainer's log:

| Where he heads | Update 60 | Update 99 |
|---|---|---|
| "The enemy" (the item picker's own option) | 3.2% | 0.4% |
| The eight standing places (the item picker's) | 14.4% | 1.9% |
| Back off (new) | 0 | 11.0% |
| Cut him off (new) | 0 | 7.8% |
| Go at him (new) | 0 | 0.2% |
| Hold an angle (new) | 0 | 0.1% |

Over the same updates: frags fell from 1.85 to 1.55 a match-minute, and the enemy was in his view 17.1% of the time, then 15.4%.

So the swap was: his hunting and his standing places out, backing off and cut-off walks in. And the cut-off walk mostly leads nowhere:
on practice trips through update 60 the enemy passed the chosen spot on 4,048 of 86,476 trips (5%). For the angle it was 1,561 of
39,962 (4%). Nearly a fifth of his decisions went to trips that avoid the enemy or wait where he does not come.

## Why the fight network rated the options this way

1. **Every option was worth less than his own choice, at every update.** The fight network's own measure of a practice trip (its
   result against what it expected from his own play) was below zero for all four options from update 5 to update 99: go at him about
   −0.2, hold an angle about −0.17, cut him off about −0.1, back off about −0.07. The ranking it learnt (back off first, cut-off
   second) is the ranking of which option disturbs him least. Back off is close to an item trip; go at him is the largest change.
2. **A practice trip was dealt at a random moment.** The game's rule is that a fight taken at a random moment is a bad fight; a
   fight is good when it is chosen for the state (stack, place, weapon). A network that only sees "go at him" at random moments learns
   its average, which is bad. It was meant to learn *when*; with about 500 to 800 such trips an update it did not.
3. **A practice trip was dealt a random weapon, held by a strong push** (the card's "a weapon he owns, each equally likely"; no
   gauntlet, but the machine gun counts). Going at him with a weapon drawn by lot loses the damage trade. Backing off with one costs
   nothing. This weighed on exactly the options the run was for. **My design.**
4. **Half the practice was picked by the fight network itself, and it fed on its own ranking.** At update 60 it picked back off
   3,281 times, cut-off 937, go at him 18, the angle 11. Go at him and the angle got 10% of the practice each, not the 19% planned.
5. **The total share of the fight options was set by hand** to what "the enemy" and the places held (about 18%). So the options got
   18% of his decisions whatever they were worth, split by the ranking above. **My design**, named on the card as the one hand-set number.

## My faults

- **The update-60 test could not pass.** "On practice trips he deals at least as much damage for the damage he takes as on his own
  choices": a trip forced on a trained player at a random moment is worse than his own choice almost by definition (0.84 against 1.00
  all run). This is 2.2a's fault again (a test never shown to pass for a part that works). It did not hold the run, but it was the
  run's only yardstick.
- **"The enemy" was shut on the clock while its replacement was at 0.2%.** `HISTORY.md` has the rule: open a head before fading the
  rule it replaces. The card's plan opened and shut them over the same updates whatever the numbers said.
- **The random weapon** (3 above) and **the hand-set share** (5 above).
- **An alarm that could not fire.** The restart's alarm on how fast his weapon choice moves read a figure the restart itself switched
  off; it showed 0 all night. The gauntlet alarm covered for it.
- **Nothing logged when he chose a fight option** (ahead, behind, after a frag), though the card asked for it. Whether the fight
  network told states apart at all is not known.

## Not verified

- **Which of the three changes of stage 2 cost the games**: losing the hunt, losing the standing places, or the trips away. They
  opened together (accepted on the card).
- **That a check plays the fight options exactly as training does.** By the code it does (the check reads the fight network and the
  save's own share), and training's own figures fell over the same updates. It was never compared directly. One measurement settles
  this and the point above: update 90's save with the fight options switched off in the check (which restores "the enemy" and the
  places), 200 games against the start. If that is level, the weights are fine and the loss is the list.

## Where to cut

**Keep update 60** (`keep/policy_u60.pt` with `keep/opt_u60.pt`): the last save before stage 2, with its optimizer, level with the
start by the three checks. It holds the relearnt pay split, the hands' new inputs and 60 updates of practice. Update 30 has the best
single record (116-84) but no optimizer, and 58% is inside chance of level. The end (update 90, `keep/policy_end_22b.pt`) is kept by
rule and not used.

Honest about update 60: it is not shown to be better than 2.2a's update 90. If the next design drops the practice trips, starting
again from 2.2a's update 90 is as good and simpler.

## What every failed attempt shared

**The owner's reading (2026-11-18), which he had given before the run and which the planning session built against:** "Anything
which forces him to use a specific method will not work ... dictating that he play a certain way makes him worse. Full stop."
"The way to get behavior to emerge is make it worthwhile ... it's a structure and incentive problem." The practice trips, the dealt
weapon, the options shut on the clock and the hand-set share were all forcing. The fallback further down is withdrawn for the same
reason, and nothing of 2.2b is used: the next run starts from 2.2a's update 90, the file 2.2b started from (owner, 11-18).

1.7a (the combat order), 1.9a (the head in charge), 2.2a (the rater), 2.2b (the fight network): each time the fight plays were **new
places to walk to, added beside the items, whose worth was to be learnt by sending him there**, and each time they were measured
against his own trained choice and lost.

The assumption to remove: **that deciding a fight means picking one of several named plays.** By the owner's three lines the
decision is one question, asked all the time: *is this fight worth taking now?* He already has the play ("the enemy": he goes after
him, the hands know how, he chose it 3% of the time and it was part of a network that won). What he lacks is a better answer to
*when*.

This breaks design principle 5 as written ("a new part plays a little from the start"): here the part's own picks starved the
options it ranked low. It follows principle 1 (build what the player does) and principle 2 (do not force a job into a part).

## The next run: concrete changes

1. **"The enemy" and the standing places stay in his list**, scored by the item picker as before. Nothing that works is shut.
2. **The fight network scores one thing: "the enemy".** Its number is added beside the item picker's score for that option (rule 12:
   beside, never instead). It starts at zero, so he plays exactly as the start.
3. **No practice trips, no dealt weapon, no hand-set share.** The fight network learns from his own trips after the enemy, which he
   already makes and the hands already carry out. Its pay stays its own (damage dealt and taken, frags, deaths, the chance of winning),
   and it keeps reading what a fight decision needs (the odds of a fight, both stacks, the weapons).
4. **Back off is not a place.** Leaving a fight is "the enemy" scoring low so that an item wins; health and armor are already items.
5. **Cut-off and the angle wait.** Before either is built again, the rule that picks the spot is fixed on logged games, without
   training: today the enemy passes the spot on 5% of trips. They return as *where the hunt points* (at him, or where he will be), not
   as options of their own. The angle belongs with firing at a spot he cannot see (2.2c's design).
6. **Kept from 2.2b:** the pay split, the judge that reads the items, the near-miss pay, the background predictions.
7. **Logged from update 1:** how often he heads for the enemy when ahead, level and behind on stack, and just after a frag; how fast
   the hands' weapon choice moves (the missing alarm).
8. **The pass mark is one that can be met:** checks level with the start or better; and he goes after the enemy more when ahead than
   when behind, by more than at the start.

**The fallback, if you want the four options tried once more:** practice dealt evenly with his own weapon, "the enemy" never shut, no
hand-set share. I do not recommend it: sixty updates of all four options below his own choice is a clear answer about them as built.

## Risks and odds

- **The fight network may only repeat the item picker's score for the enemy** (2.1e's lesson: a second forecaster of the same thing
  from the same inputs matches the first). What is different here is its pay and its inputs. If its number stays near zero, that is
  the answer.
- A sum of two learned scores on one option: both regularized, both sizes logged (rule 13).
- Odds: checks stay level, about 75%. He visibly hunts more when ahead and less when behind, about 45%. He beats the start by a
  clear margin, about 25%.

## Your decisions

1. The next run as above, or the fallback.
2. Start from 2.2b's update 60 or from 2.2a's update 90.
3. Whether to run the one measurement under "Not verified" first (200 games, no training).
4. The name (2.2c is taken on paper by firing at a spot he cannot see).

# 2.2d: the parts of 2.2c we want, without the pays that failed; a starting point for 2.3

**Approved by the owner, 2026-11-18**: "keep the pay split, rail pickup, far [rail], and aggression [lever]. drop the long sighting pay
and near miss pay and contest pay"; the rail forecast: "Ok it's out then. Let it go for a max of 80 updates, I'll read how it goes in
the morning and then we'll regroup". Written after 2.2c was stopped by the owner at update 71 (RUNS.md #61: checks 77-123, 91-109,
85-115 against the start).

## The owner's page

| | |
|---|---|
| Started from | 2.2a's update 90 (the file 2.2b and 2.2c started from). Nothing of 2.2b's or 2.2c's training is used |
| The aim | A clean overnight run of the parts already decided, to give a save to build 2.3 on. **Update 60's save is the default going forward** if the checks hold |
| What is new against 2.2c | Nothing is added to his play or his pay. Three pays are taken out. Two log lines and one alarm fix |
| How it is judged | Games won and lost against the start. Nothing else is a pass mark |
| Length | At most 80 updates, and it stops at 08:00 on 11-19 whichever comes first (owner, 11-18) |

## What plays (every part as built for 2.2c, its code unchanged)

| Kept | Detail |
|---|---|
| **The aggression lever** | The fight network puts out one number, added to the item picker's own score for "the enemy". Zero through update 10, on in full from update 11; the hands are shown it (its gate opens over updates 10 to 20). Both scores carry the decay; its size is logged and flagged over 40 (rule 13) |
| **Each network paid for its own job** | The item picker: items and the chance of winning. The fight network: damage dealt less taken, frags, deaths, the chance of winning. The hands as before, plus the far-rail pay |
| **The judge that reads the items and stacks** | The chance of winning comes from it, as refitted on the start's games for 2.2b and 2.2c; scaled to at least each network's flat pay, re-measured in the build now that three pays are out (rule 14) |
| **The rail pickup pay** | 0.15, once a life, when he takes the rail while not holding one. In 2.2c the rail owned in the checks went from 13% to 23% of his time alive |
| **The far-rail pay** | 0.5 for a rail hit in 2.2c's band, to the hands and the item picker. In 2.2c it collected almost nothing and cost nothing |
| **The hands' new inputs** | The yellow armors' timers and where the brain expects the enemy in 1, 2 and 4 seconds (the input list of 2.2c) |
| **The weapon choice is the hands' own** | The item picker's push on his weapon goes out over updates 0 to 10; its weapon scores are never trained. 2.2b did the same and its update-10 check was 99-101, so this is not what hurt 2.2c's start |
| **The warm-up** | The item picker frozen but for its forecast's last layer through update 10 |
| **Firing costs nothing** | As now |

| Dropped (owner, 11-18) | Why |
|---|---|
| **The contest pay** (at the pickup, by the second, the steal, the charge for a free pickup) | "contest pay isn't working drop it." The enemy's big pickups under pressure stayed at 28 to 31% for 60 updates; it was the largest new pay in the ten updates before 2.2c's 77-123 |
| **The pay at a long sighting with the rail in hand** (0.10) | It fired 1 to 5 times an update |
| **The near-miss pay** | His shells near an item nobody took rose 45% in 2.2c: it paid shots that pressured nobody |

**Not in this run, for 2.3:** the forecast of what the rail would deal (owner: "it's out"), and the rail opponent in his league.

## What is added (logging and one fix only; none of it reaches his play or his pay)

1. **The contest and near-miss counters stay as logging, with their pay at exactly zero.** The build shows the pay is zero on every
   term (at the pickup, by the second, the steal, the free-pickup charge, the near miss), not small.
2. **A log line: what a rail would have dealt against what he dealt, by distance.** For each frame the enemy is in his sight: did his
   crosshair cross the enemy in the next 1.5 s (a rail would have hit: 80 points, one shot a 1.5 s), against the damage he did deal
   in those 1.5 s, summed by distance band (under 500, 500 to 768, 768 to 1,200, over 1,200 units), and by whether he owned the rail.
3. **A log line: at each of the enemy's big pickups with no pressure, did he have a clear line to the item**, and from how far.
4. **The weapon-choice-speed alarm fixed.** In 2.2c it could not read the hands' figure from update 21 on and printed a major problem
   every update. The build finds why and shows it reading on a trial that runs past the update where it broke, or says it could not.
5. **A check at update 60**, against the start and against 2.1d's end, since that save is to be the default.

## The schedule (everything opens on the clock, every number reported)

| Updates | What plays | What learns |
|---|---|---|
| 0 | Identical to 2.2a's update 90 (proven before the start: no action differs on fixed-seed replays) | |
| 0 to 10 | The rail pickup pay and the far-rail pay at full size. The lever at zero. The item picker frozen; its push on his weapon going out | The hands; the forecasts of the item picker and the fight network |
| 11 to the end | The lever on in full; the item picker learns; the hands shown the lever (gate opening over 10 to 20) | Everything |
| 10, 30, 50, 60, 70 | Checks, 200 games, against the start; update 60 also against 2.1d's end | |
| 60 | The save kept with its optimizer: the default going forward | |
| 80, or 08:00 on 11-19 | It stops after a save; the end kept with its optimizer, and checked | |

Saves kept at updates 10, 20, 40, 60, 80 and the end.

**The one pass mark: checks level with the start or better.** Known reachable: the start scores level with itself, and 2.2b held it
through 60 updates under the same pay split. A check under 40% is flagged at once as a major problem.

## Red team: what is set by hand or assumed

| Part | Whose | The risk | Its measured alternative or guard |
|---|---|---|---|
| The far-rail pay at 0.5 and the pickup pay at 0.15 | The owner's | **2.2c's fall at update 10 came from the contest pay or the rail pays; the records cannot separate them.** If it was the rail pays, this run falls the same way and update 60 is not a good default | The check at update 10 answers it. Both pays are live dials |
| The lever | Kept on the owner's word | In 2.2c it grew (about 1.0, larger when ahead) and he headed for the enemy 9% of the time ahead against 2% behind, but no check improved. It may be doing nothing for the result | Its size, and how often he hunts ahead, level and behind, reported every update |
| The pay with three terms out | Mine to check | The win-chance scale or the split was measured with the contest pay in | The scales re-measured in the build on the start's games |
| The counters with the pay at zero | Mine | A leftover term pays or charges something | The build's proof that each term is exactly zero; the pay terms printed every update |
| The rail log line | Mine | It assumes he would aim the same with the rail in hand, and counts a hit whenever the crosshair crosses him | It is a measurement, never a pay or a target; read with that fault in mind |
| Self-play | Assumed | His copies both close at once; nothing in this run punishes open ground | Not addressed here. It is the question for 2.3 |

**The pay's pathology check.** Negative frags: untouched. Sign flips: none; the rail pickup pay is paid once a life and cannot be
farmed by dropping it; the far-rail pay is zero-sum (the one hit is charged). Lopsided games: the stronger player collects more
far-rail pay, as with damage. Nothing is paid for a shot that hits nothing.

**The equilibrium in self-play.** With the contest and near-miss pays out, his pay is damage, frags, items and the chance of winning,
plus two small rail pays. He is led to walk to the rail and own it; whether he then holds it depends on whether it deals more than
the lightning or the rockets in the games his copies play, where both close at once. If it does not, he will own it and not use it,
as in 2.2c. That is expected here and is what the new log line measures.

## Research check (docs/research/README.md's seven questions)

1. **The game**: nothing of the game changes. The rail's 80 points and 1.5 s between shots in the log line are MECHANICS.md's weapon table.
2. **What wins**: the lever serves "take the uneven fights" (DUEL_STRATEGY 1.4, 1.6); the rail "is the comeback weapon" and "almost a mega or a red" (1.5, 1.3). Dropping the contest pay leaves "making his pickup cost him" (1.3) unserved again: 74% of the enemy's big pickups were free at the start and about 70% through 2.2c.
3. **The player's view**: no input changes against 2.2c. The log lines read the simulator's truth and are never shown to him.
4. **In and out of control**: nothing new for either side; the lever reads the stacks, the score and the clock.
5. **Self-play equilibrium**: above. No league opponent holds a long line, so nothing teaches the rail's worth or the cost of open ground.
6. **Bot precedent**: nothing strategic is taken from AlphaStar or Pluto here; the run removes parts. The rail opponent (AlphaStar's exploiters, BOTS.md) is put off to 2.3.
7. **Rule 10**: no pro outcome is a target. The rail log line compares his own play with his own possible play.

## Which principles (docs/design/PRINCIPLES.md)

Follows 6 (every part off = identical at the start, on its own live dial) and 8 (each decider paid for its own job). It tests 2
again in its smaller form (the lever). It breaks none.

## Not verified (the build settles each before a start)

- That the contest and near-miss counters can run with every pay term exactly zero.
- Why the weapon-choice-speed alarm lost the hands' figure at update 21.
- The win-chance scales with three pays out.

## For the owner

Decided 11-18: the list above; the forecast out; at most 80 updates, stopping at 08:00. Proposed by the planning session and built
unless he says no: the counters as logging, the two log lines, the alarm fix, the check at update 60.

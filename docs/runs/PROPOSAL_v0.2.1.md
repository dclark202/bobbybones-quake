# v0.2.1: the proposal (2026-10-12, for the owner's review this afternoon; not a manifest yet)

The owner, 06:40: "write me the proposed changes for v0.2.1 including attention B and C and any other things youve
learned from this run. Do not promote the live server yet, well review together this afternoon". v0.2
(`duel_gru_v0_2`) trains until 11:00 ("you can stop earlier if it seems fully baked"); its report follows its end.
**The name**: v0.2.1 is the run after v0.2, from v0.2's end. The write-up that carried the name on 2026-10-11
(`MANIFEST_v15e.md`) was never run; its content went into v0.2. Nothing here is started or pushed: the public server
stays on v0.1.

## 1. What v0.2 taught

| # | Finding | The numbers |
|---|---|---|
| 1 | Stage A works as a part and does not by itself change how he plays | the door lets 38% of his memory's input through; 57.9% against v0.1 at eight hours, all of it on the four maps v0.1 never played games on (67%; the six maps both know 52%); the scorecard beside the pros 47%, as at the start |
| 2 | **His choice of weapon follows the draw of his "style" far more than the situation** | three lives in four have a drawn weapon (rockets, rail, lightning, a quarter each) and damage with it pays half as much again. In a rockets life rockets are in his hand 48% of the time, in his other lives about one time in seven. By distance his hand hardly changes: rockets 27% close and 22% far, lightning 31% at every distance, the rail 22% close. Nothing in v0.2 touched the draw, so his weapon mix stood still |
| 3 | **With rockets he is the weaker player** | frags per death in a rockets life 0.82, a rail life 0.75, a lightning life 1.17, a general life 0.90. In a rockets life they are in his hand 48% of the time. His lightning hits more than a pro's (cells hit 43% against 32%) even after the first aim step, so every trial of his own says: lightning |
| 4 | **On his own feet he does not strafe jump at all** | on the frames his legs carry him his own view turn is the legs' choice 6% of the time (ceiling 71%; sideways key 45% against 91%). He is on his own feet half of every game, at 280 units a second; on his legs 322 |
| 5 | With no item due he has no target | 8% of his time overall, 28 to 32% on Aerowalk, where his legs carry him 19% of a game (Furious Heights 69%) |
| 6 | The aim step did what it was sized for and no more | first hit at 20 to 40 degrees off 0.56 to 0.61 s (the pros 0.76); his weapon mix did not move |
| 7 | The hop-gain pay is too small to matter by itself | 0.18 a player-minute; time at 400 or more 10.1% to 9.0% |
| 8 | The two-minute value estimate did no harm and may have helped his stack | it adds a third to his credit; back at the mega within 2 s 48% to 53%; against v0.1 he holds 150 or more 53% of the time (v0.1 in the same games 43%) |
| 9 | Held-out maps are a sound check | House of Decay 77 to 75%, Dismemberment 58 to 60% while the trained maps rose |
| 10 | The checks' noise | the same network against itself: 48.8%, single maps 41 to 56%. A check is read by its mean and by map group, never by one map |
| 11 | From the builds: his legs cannot stop (over a ledge at 370); the pros' other ways are mostly drops, jumps and rocket jumps the walking map lacks; a frag paid by the game must be paid per frame | [../design/V02_STAGE_B.md](../design/V02_STAGE_B.md), [../design/V02_STAGE_C.md](../design/V02_STAGE_C.md) |

Findings 2 and 3 are new and change what I would do about rockets. The first aim step, the rocket prices and the
places could not have moved his weapon use: the draw of lives decides it, and inside a life his own results favour
lightning.

## 2. What v0.2.1 would be

From v0.2's end. Everything below is built and tested in a copy unless marked; with every switch off the merged
simulator and trainer are bit for bit today's (the merge: 791 inputs, 13 outputs).

| # | Change | For which of the seven points | State | The risk |
|---|---|---|---|---|
| 1 | **His own movement taught by his legs** (stage C part 1): on the stretches he chooses his legs, his own keys and turn are pulled toward what they did; one stretch in ten is withheld (he asked for his legs and moves himself) so that what he can do alone is measured from the first hour | speed (the half of the game he is on his own feet) | built; needs its weight and warm-up from a dry run | a new teacher: at full weight it triples his step in a first update and moves his pitch. Held back to a share of the shared layers and warmed up over an hour |
| 2 | **A target that is never "nothing": places** (stage B part 2): eight holding places a map from the pros, his to choose like an item; where the item rule names nothing the lesson is silent | speed (his legs always have somewhere to go); position; somewhere to go when he refuses a fight | built; the place choice opened at 5% of his readings by a bias, not a rule | a new choice at the start has cost him twice (the enemy as a target). A full level check of 128 games before the start; in a probe "the nearest place" read level and took his idle time from 14.6% to 1.9% |
| 3 | **Things he is asked to foretell** (stage B part 1): where the unseen enemy is, where he next appears, how the next fight ends, when the big items return. Not paid | crosshair placement; the fights he takes weak; item timings | built | small: it only shapes what his memory keeps (the weight 0.1 could not be told from chance in his step) |
| 4 | **Legs that arrive and stand** (stage C part 2, the standing half) | holding a place without going over the ledge | the code is built; the network needs about an hour of the card and then the pupil test of today's legs on the ten maps | the short trial cost plain speed (361 to 336): it goes in only if the trained network passes the test, else places are held on his own feet as in the probe |
| 5 | **The draw of his lives toward rockets** (owner's decision 1): rockets 40% of lives, lightning 15%, rail 10%, general 35% (today 25 / 25 / 25 / 25); the extra pay for the life's weapon as it is | rockets: more of his time is practice with the weapon he is weakest with | a small change to build (a weighted draw; the servers draw the same) | his strength falls at first, because a rockets life is worth 0.82 frags a death and a lightning life 1.17: checks are read by life as well as in all |
| 6 | **The second aim step** (owner's decision 2): the aim level from 1.5 to 0.75, about half way to the pros' flick curve, with the acquire delay honoured by the checks (B-226) | rockets and the rail against lightning: the edge his lightning has over a pro's shrinks | the setting exists; B-226 is an hour's work | strength against v0.1 is not affected (both play at the run's level); against people he is a little less sharp |
| 7 | **The pros' weapon in hand with nobody in view, as a small standing pull** (owner's decision 3; approved in general as "the pros' choices as a standing pull"): travelling and holding, the label is the pros' share by how long the enemy is unseen (rockets up, the humming weapons down); only on frames with nobody in view, only his weapon key | rockets in hand when a fight begins; the quiet weapon the owner asked for | to build (a table from the demos' pull, a loss like the weapon teacher's); a day with its dry run | a teacher kept to a run's end makes him hold a weapon by rote; kept small and to unseen frames it cannot touch his choice in a fight |

**Held, with the reason:**

- Several ways (B part 3): built, but a small lever until the walking map has the pros' drops and jumps: a second way
  differs from the shortest from 9 to 24% of his starts. It waits for the jumps (B-204) and for rocket jumps.
- Whole games and the pay by the game (B part 4): built, but a ten-minute game is 4.8 hours of a run, the checks and
  the servers do not know a game's clock yet, and two decisions are the owner's (4 and 5 below). Next after this.
- Legs that run and look (C part 2, the looking half): the short trial did not learn it. The legs' training is
  judged at thirty minutes; if looking moves, it joins a later run.
- The enemy as a target: not opened. It lost twice from a fitted start; it wants the belief to tell him the enemy
  is weak, which part 3 of this run trains.

## 3. What I expect, and what would prove it wrong

| Point | Expect in a night | It did not work if |
|---|---|---|
| Speed | his own turn agrees with his legs' 6% to over 40%; in withheld stretches at 400 or more some of the time; time at 400 or more over a game 9% to 12% or more; idle time under 3% | his own turn's agreement stays under 20%, or the time at 400 or more does not move |
| Rockets | rockets in hand with the enemy in view 19% to about 28% by the draw alone (40% of lives at 48%, the rest at 14%); frags per death in a rockets life up from 0.82 | the share rises only by the draw and a rockets life stays at 0.82 |
| Low ground | no change expected from this run by itself; the places give him high spots to choose | (measured, not judged) |
| Weak fights | commits with a stack under 60 from 5% down; closing speed when weak down from +24 | both unmoved, as in v0.2 |
| Item timings | held at 48 to 53% | below 45% |
| Aggression that pays | no change expected | (measured) |
| Spam | rockets in hand while holding from 15% up; blind rockets may follow | (measured) |
| Strength | level with v0.2's end at the first check; ahead of it after a night on the general lives | under 45% at two checks |

Honest limit: nothing in this run pays for height, for refusing a fight, or for a rocket fired at a doorway. If the
low ground and the fights he takes are still where they are after it, they need a decision of their own (the pay for
height the owner held back with "token first"; whole games).

## 4. Before a start (after 11:00, with the card free)

| Step | Time |
|---|---|
| v0.2's end: the report, the scorecard, real games against the game's Nightmare bot on the quiet PC, the owner's game | his afternoon |
| The merge into the repo (`apply_all.py`), the converters for v0.2's end, the control and the league | under an hour |
| Dry runs of ten minutes each on the card: the size (47 tokens need more pieces an update), the legs' lesson at three settings, the foretelling | an hour and a half |
| The legs trained for standing (decision at thirty minutes), then the pupil test on ten maps | one to two hours |
| The level check for the place choice: 128 games against v0.2's end | forty minutes |
| How the attention part comes to look at the new place tokens: a schedule in the trainer that opens their gate over the first hour (to build; today the gate starts shut and nothing opens it) | an hour |
| Changes 5 and 6 if the owner says yes (the weighted draw; B-226) | an hour |
| Change 7 if the owner says yes | a day: it would join the run after, or delay this one |
| The plugins for a v0.2.1 network (places as targets on a server) | before any server use, not before the run |

Without change 7 a start tonight is realistic; the manifest follows the owner's answers.

## 5. For the owner to decide

1. **The draw of his lives** (change 5): rockets 40%, lightning 15%, rail 10%, general 35%? Or another mix, or no
   styled lives at all (every life general, his weapon by the situation alone)? I would take the mix above: the styled
   lives were his idea and they do make him practise a weapon; the fault is the even split.
2. **The second aim step** (change 6): to level 0.75 now, or hold it one more run? I would take it now: finding 3
   says his lightning's edge is what his own trials keep choosing.
3. **The pull of the pros' weapon in hand with nobody in view** (change 7): build it, and for this run or the next? I
   would build it for the next run and not hold this one for it.
4. **The table a frag is paid by in whole games** (held part): the pros' as counted, or for equal players?
5. **Whole games begun in their middle** at a run's start, so that they fill within hours?
6. **Who chooses where his legs look** (held part): his belief of the enemy by rule, or an output of his own?
7. **The control**: v0.2's end becomes the control and the league's anchor if it holds its lead over v0.1 to the end;
   v0.1 stays in the league beside it.

## 6. The run in outline

As v0.2 (ten maps, 30 simulators, rollouts of 384, the same pay) with: `TARGETS=1`, `LEGS_LABEL=1`, `LEGS_KEEP=0.9`,
`--aux 0.1`, `--legs-teach` with its warm-up, and by the owner's answers the weighted draw, `AIM_LEVEL=0.75`,
`LEGS_STAND=1`. A night. Checks from every save against v0.2's end with the seats swapped, read by map group and by
the kind of life; the stand-in with the two held-out maps in a slot of its own, so that it no longer delays the next
check by an hour; the scorecard beside the pros twice in the night. With every 30-minute line: his own turn's
agreement with his legs, his speed in withheld stretches, his time with a place as target, rockets in hand, frags
per death by the kind of life.

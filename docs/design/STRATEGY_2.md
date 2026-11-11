# 2.0c: the strategy layer that asks, answers and commits (a design for the owner's review, 2026-11-10)

*Owner, 11-10: "The point of the head is exactly to run the cost/benefit analysis of these different actions which are all possibly
valid, and then send an instruction to the hand to carry out until that action is either changed or confirmed 200 ms later"; "'this
is a rail spot' means nothing if his action is 'go get yellow'"; "The idea of a hierarchy for choices failed in 1.7. To me, that
means we didn't give him the right additional context of information to make those choices. This is a rectification of those
failures"; "this is a large change, and a completely expanded way of asking and answering questions, which are fed recursively back
into the strategy layer"; "the maps need to be wringed for info to feed into the model; seed info pulled from the maps and pro demos,
but also learned and reinforced through self play." Nothing here is built. Start: 1.7a's update 90.*

## What was wrong before, in one table

| Attempt | What the head had | Why it failed |
|---|---|---|
| 1.7a's order ([postmortem](../runs/1.7/1.7a/POSTMORTEM.md)) | four kinds of order, a pointer, a fit to the pros as the start | judged before the hands could carry an order out; nothing kept a rare order tried; and **nothing told the head when an order pays**: it had no number for "this is a place to hold" or "he will come through that door" |
| 2.0b ([postmortem](../runs/2.0/2.0b/POSTMORTEM.md)) | 59 numbers about the place, from a fixed table | information with no action to use it on: his choices were still "go to item X"; and the numbers moved every frame into the keep choice |

The two failures are one: 1.7 gave him the actions without the knowledge, 2.0b the knowledge without the actions. 2.0c is both, built
as one thing.

## The loop, every 0.2 s

1. **The brain** says what it believes: where the enemy is (odds over places), his stack and weapon, where and when he will next
   come into view. Its job, unchanged.
2. **The map sense** (new, learned) turns his own place and those odds into what the map means right now: how good it is to stay
   here with each weapon, how good each place he could go is, which opening to watch.
3. **The appraisals** (new, learned): for every action he could take now, a forecast of what it would bring. These are the explicit
   questions, each with a learned answer.
4. **The head** reads all of it, with its own last answers and how long it has been on its current action, and gives the list
   of intentions (how much each action is worth now) and the one instruction for the hands.
5. **The keep choice** decides whether to stay on the instruction or take the new one.
6. **The hands** carry the instruction out until it changes.

Step 4's output goes back in at step 4 of the next tick. That is the recursion: he sees what he thought 0.2 s ago, what he
committed to and when, and what has changed since.

## The actions (what the head can send the hands)

An instruction is a verb, a place, a point to look or shoot at, and a weapon.

| Verb | Meaning | The place and point come from |
|---|---|---|
| go | move to an item or place, do not linger | the items, as today |
| contest | be on an item's ground before it comes back, and hold it | the mega, the red, the yellows, with their clocks |
| hold | stand here, watch that opening, wait for the shot | the map's holding places and the openings that look onto the enemy's likely ways |
| spam | from here, put rockets, grenades or plasma on that point | corridors and doorways the enemy must pass |
| push | close with the enemy and fight | his believed place |
| cut off | be where he is going before he is | the brain's forecast of his way |
| break off | leave the fight for cover and the nearest thing worth having | the fallback of his place |

The weapon is part of the instruction: "hold here with the rail" and "hold here with the lightning" are two candidates with two
appraisals. Nothing sets his weapon by a table; he chooses the instruction whose forecast is best.

Each tick a short list of candidates per verb is drawn from the map (the best few by the map sense under his present belief), so the
head weighs about 20 to 30 concrete instructions, not every place on the map.

## The questions (the appraisals)

Two kinds, all learned, all scored against what really happened.

**About the situation** (several exist today as lessons the head barely uses):

| Question | State |
|---|---|
| Where is he, what is his stack and weapon | the brain (exists) |
| Who wins this fight if it goes on | the fight odds (exists, 1.7b) |
| Who takes the next mega, the next red | "in control" (exists); **the yellows are new** |
| Will he pass this point in the next seconds | the pass odds (exists, 1.7a: Brier 0.080 against 0.186) |
| Where will he come into view, and when | the emergence point (exists as an input) |
| What is this place worth with him there | **the map sense (new)** |
| What is the game worth now: the lead and the clock | the judge's value (exists) |

**About each candidate action** ("should I do X"; new): if I commit to this instruction for the next few seconds, what do I expect?

| Forecast | Truth it is scored against |
|---|---|
| damage I deal, damage I take | the next seconds of the game, while the instruction was held |
| chance he dies, chance I die | the same |
| the item gained or lost | who took it |
| the change in the chance of winning | the judge at the end of the horizon |

One network answers for every candidate: it reads the situation, the map sense at the candidate's place and point, and the
candidate itself (verb, weapon, distances, clocks). Because the answer comes from what the candidate *is*, a rarely chosen
instruction still gets a sensible forecast from the map and from the pros' games. That is what 1.7a's order never had: there a rare
order had nothing to stand on but its own few tries.

## The map sense

The value of standing at P when the enemy is at X, by weapon. It starts from seeds and is corrected by play.

| | |
|---|---|
| Seeds from the map | sight between the two places, distance, the number of ways into view of P and how fast he reaches them ("easily challenged"), the time to cover and the exits ("no fallback"), height, the items near |
| Seeds from the pros' games | how long they stay at P with the enemy at X, what they hold, where they look, what the stay brought them |
| The learned part | a small network over the seeds, shared by every map, and a correction per place of each map that starts at zero |
| Its lesson | what happened in the seconds after he stood there (damage both ways, a frag, a death), in his games and, kept all run, the pros' |
| Held to the seeds | the corrections decay toward zero, so his games adjust the map and cannot erase it |
| Read under the belief | averaged over the brain's odds of where the enemy is: steady when the belief is steady, moving when it truly moves |

## Committing, and changing his mind

- The head's inputs include the instruction he is on, how long, and **its forecast when he took it against its forecast now**. Staying
  is the default because a hold that is still good still reads good.
- What should move him is given as numbers of its own: the enemy came into view, a sound, how far the belief has moved since he
  committed, an item's clock crossing the time it takes to get there, the forecast of his instruction falling under another's.
- The keep choice (1.7a's part that worked: 50% to 63%) stays as the gate. It reads those change signals. It does not read the
  per-candidate numbers, which is what made the target unstable in 2.0b.
- Nothing prices a change of mind (owner, 11-04). Commitment has to come from the forecasts being right.

## How it learns

| Part | Learns from | Paid? |
|---|---|---|
| The brain | its lessons against the truth, as today | never |
| The map sense | outcomes after standing at P with him at X; the pros' games | never |
| The appraisals | outcomes while an instruction was held; the pros' games with their instructions inferred (a still player with the rail on a doorway is a hold; fire at a point with nobody in view is a spam; arriving on an item before it comes back is a contest) | never |
| The head's choice | the game's pay, through its own value; and a pull toward the pros' choice in the same situation, **kept all run** (AlphaStar; 1.7a used it only as the start) | yes |
| The keep choice | the game's pay | yes |
| The hands | the game's pay, with the instruction as an input | yes |

The pay is the game's: frags and deaths, the items, the judge, damage at 0.002 and zero-sum (owner, 11-10). A hold that lands 80 for
15 taken pays; a brawl pays nothing. A pay from the map sense's own value (its change from one moment to the next) can be added later;
it is not needed for the design to stand.

Rule 11: the choice's scores are the head's own plus the appraisals' part; both carry the decay and their sizes are recorded.

## The order things open in (1.7a's lesson: the hands first)

| Gate | Opens | The test that must pass first |
|---|---|---|
| 0 | the map sense and the appraisals learn; nothing reads them | their skill on recorded games and the pros' (below) |
| 1 | the hands read the instruction, in **drills**: practice rounds where the instruction is given (drawn from the pros' situations) and the hands are paid by what happens | each verb carried out: a hold waits and takes the shot, a spam fires at the point, a contest is on the ground in time |
| 2 | the head reads the questions, with today's choices | no fall against the control; the quiet re-decisions flat |
| 3 | the head's instructions go to the hands in games, from the pros' rate, with the pull to the pros kept | the forecasts of chosen instructions match what they brought |

Whether gates 0 to 3 are one run or several is the owner's call when each test is read; the design is one thing and is built whole.

## Tests before any training

1. **The seeds** (started 11-10): the plots of every map, "how good is each place with him at X", by weapon, for the owner to judge
   (his examples: Lost World's top middle, Blood Run's bottom T, the contested megas); and whether the seeds forecast the pros' and his
   games on a held-out half.
2. **The pros' instructions**: how often they hold, spam, contest, cut off, break off; what each brought; with which weapon.
3. **The appraisals** fitted on recorded games: their skill against the base rate, per verb.
4. **What self-play does to the map sense**: fit the corrections on 1.7a's games and plot where they leave the seeds.
5. **Steadiness**: how much the head's inputs move from tick to tick on recorded games, against 2.0b's.
6. The head fitted to the pros: its agreement on held-out games. Then the identity at the start, and ten updates with a check; a
   dry run under the control is not started.

## Weaknesses, said now

- **His own games teach that places do not matter**, because nobody in them holds. The pros' games in the lessons and the pull to the
  pros' choices are the defence; test 4 measures it. If it is not enough, opponents that hold (the league's exploiters) are next.
- **Inferring the pros' instructions is a rule** of mine and will be wrong sometimes; it is checked by reading samples with the owner.
- **The hands may not learn a verb in drills** (the rail under his aim limits is the likely one). Then that is the finding, and it is
  fixed before the head is asked to choose it.
- **It is large.** More parts than any run before; each has its own test so a failure can be pinned to one.
- A forecast for an action never tried is a guess from the seeds. The pull to the pros keeps such actions tried; without it they
  die as 1.7a's order did.

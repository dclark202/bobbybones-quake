# 2.1: the strategy layer that asks, forecasts, chooses and commits; the map as a rule he can adjust

*Written on 2026-11-10 as "2.0c"; that name went to the run of AIM3 and the damage pay ([../2.0/2.0c/CARD.md](../2.0/2.0c/CARD.md)) on the owner's word that night ("Then we can start fresh on 2.1 with these changes established"). Where the text below says 2.0c it means this design.*

**A draft for the owner's review (2026-11-10). Nothing trains; no go is asked yet.** The design in full:
[design/STRATEGY_2.md](../../design/STRATEGY_2.md). Why: [2.0b's postmortem](../2.0/2.0b/POSTMORTEM.md), [1.7a's](../1.7/1.7a/POSTMORTEM.md).

| | |
|---|---|
| Started from | 2.0c's result (1.7a's update 90 trained under AIM3 and the damage pay 0.002), once it is read |
| Kept from 2.0a | damage zero-sum (taken priced as dealt). Dropped: its 0.001 and the judge's weight up |
| Branch | `b20b` today; a branch `b20c` when the build starts |

## The owner's words (11-10)

- "It decides between a suite of questions, recurrently, with instructions that feed to hand for execution. The brain supplies the
  belief about the true state of the game, which is a fairness rule."
- "The hands get paid through doing damage/frags/winning, the head gets paid by 'making the statistically correct choice at the given
  situation' by sampling a frozen state and picking say the top 5 choices and a handful of others."
- "Regions/specific spots of the map are easily exploited or naturally safe to hold. Before we just willed that he would pick up on
  that naturally, but I don't believe the network really has the capacity to know that for all maps in its weights. So it has to be a
  rule for the map he's playing on that he can adjust by self play, but always with a slight pull to the 'average pro player'."
- "'This is a rail spot' means nothing if his action is 'go get yellow'."
- "The point is to do this correctly, not to rush through it."

## What changes, in one table

| | Today (1.7a's update 90) | 2.0c |
|---|---|---|
| What the head chooses | one of 17 targets (items, holding places, the enemy), and keep or re-decide | an **instruction**: a verb (go, contest, hold, spam, push, cut off, break off), a place, a point to watch or shoot, a weapon |
| What the head knows of the map | nothing of its own; the hands' inputs | the **map sense**: the worth of his place and of each candidate's place against where the brain believes the enemy, by weapon |
| What the head knows of its options | its own learned scores | a **forecast for every candidate** (the appraisals): damage both ways, who dies, the item, the chance of winning |
| What it remembers of its own thinking | its memory | its last answers, the instruction it is on and since when, that instruction's forecast then and now, and what has changed since |
| How the head learns | the game's pay on the one choice it made | **the frozen moment**: the same moment played out under several instructions, and the head taught toward the ones that came out best |
| How the hands learn | the game's pay | the same, with the instruction as an input; each verb practised in drills first |
| Damage pay | 0.0055 a point, taken at 0.8 | 0.002 a point, taken at 1.0 (zero-sum) |
| The weapon | the hands' key plus the head's scores | part of the instruction; no table sets it |

## The parts

| Part | What it is | Learns from | State |
|---|---|---|---|
| Brain | the belief: where the enemy is, his stack and weapon, where he comes into view | its lessons against the truth | exists |
| Fight odds, in control, pass odds, the judge's value | questions about the situation | hindsight | exist (the yellows' "who takes it" is new) |
| **Map sense** | a table a map: the worth of standing at P with the enemy at X, by weapon. Seeds from the map (sight each way by range, ways into view, cover and exits, height) and from the pros (what a stay there brought them); a shared small network over the seeds; a correction a place that starts at zero | what a stay brought, in his games and the pros'; **the corrections decay toward the pros' fit all run** | version 1 fitted and tested; version 2 building |
| **Appraisals** | one network that forecasts any candidate instruction from the situation, the map sense at its place, and what it is | the frozen moments (every option's true outcome); the pros' games with their instructions inferred | to build |
| **Head** | reads all of the above and its own last tick; gives the intentions and the instruction | the frozen moments and a share of the game's pay (no pull to the pros: rule 12) | exists; its inputs, its choice and its lesson are rebuilt |
| Keep choice | stay or take the new instruction | the game's pay | exists; gets the change signals, not the per-candidate numbers |
| Hands | carry the instruction out | the game's pay; drills | exist; the instruction's token is 1.7's |
| **Freeze and branch** | save a moment, restore it once a candidate, hold the candidate a few seconds, play on, compare | — | the save and restore of a moment exist in the simulator (`_moment_take`, `_moment_set`); the branching round and its lessons to build |

## The frozen moment (the head's lesson)

1. In a share of training time a game's moment is saved: both players, rockets in the air, items, clocks, what each knows, and both
   networks' memories.
2. The candidates: the head's five best and three drawn from the rest (so the unlikely ones are seen).
3. Each is restored from the same moment and is his first choice for one second (test 4: a rigid four-second hold loses whatever the target), then he plays on, re-deciding as he does in a game; a free-play branch is the reference.
4. What each branch brought is recorded: damage both ways, deaths, items, and the value at the end.
5. Two lessons: the appraisals learn every branch's outcome; the head's choice is moved toward the candidates the appraisals rate best (test 4: a single moment's branches are too noisy to rank its options directly; the appraisals average over thousands of moments).

The hands play every branch and are paid as always. The head is not paid for its choice by the game any more; it is taught by the
comparison. A single branch of a fight is close to a coin toss: the lessons average over many moments, and how many are needed is
measured before any run (below).

## The questions, explicitly

Every question has a learned answer, a truth it is scored against, and a reader. Nothing about the enemy is answered from the truth
in play: the answers come from the brain's belief and his own senses; the truth is only the lesson's label, known in hindsight.

**A. About the situation** (asked every 0.2 s, whatever he is doing)

| # | The question | The answer's form | Scored against | Exists? |
|---|---|---|---|---|
| S1 | Where is the enemy now? | odds over the map's zones, and a point | his true place | yes (the brain) |
| S2 | What is his stack, and what is in his hand? | four bands; a weapon | the truth | yes (the brain) |
| S3 | Where will he be in 1, 2 and 4 s? | a point each | his true place then | yes (the brain) |
| S4 | Where does he next come into my view, and when? | an opening; seconds | the next sighting | as a rule-made input today; becomes a lesson |
| S5 | Will he pass this point within 3 s? (asked of each corridor candidate) | a chance | whether he did | yes (the pass odds, 1.7a) |
| S6 | If this fight goes on, who dies first? | two chances | the fight's end | yes (the fight odds, 1.7b) |
| S7 | Who takes the next mega? the next red? each yellow? | a chance each | who took it | mega and red yes ("in control"); the yellows new |
| S8 | What is my place worth with him where I believe him: staying with rockets, with the rail, with the lightning, or passing through? | damage dealt and taken in the next 5 s, each of the four | what a stay there brought | **new (the map sense)** |
| S9 | What is my chance of winning the game from here? | a chance | the game's result | yes (the judge's value) |

**B. About each thing he could do** (asked of every candidate instruction, 20 to 30 a tick: "should I do X?")

"If I commit to this instruction for the next 4 s and then play on for 4 more:"

| # | The question | The answer's form | Scored against |
|---|---|---|---|
| A1 | how much damage do I deal? | points | the branch or the game, while it was held |
| A2 | how much do I take? | points | the same |
| A3 | does he die? | a chance | the same |
| A4 | do I die? | a chance | the same |
| A5 | do I get the item it is about (or lose the one I leave)? | a chance | who took it |
| A6 | how does my chance of winning change? | S9 at the end less S9 now | the judge's value 8 s on |

One network answers A1 to A6 for any candidate. It reads S1 to S9, the candidate (its verb, its weapon, S8 at its place, the way
there, the clocks it depends on) and what he is doing now. The examples of your message map onto it as:

| Your words | The candidate it is asked of |
|---|---|
| "should I take this fight" | push (and S6) against break off |
| "should I contest the next mega / red / yellow" | contest, one candidate an item (and S7) |
| "should I spam this corridor" | spam, one candidate a corridor (and S5) |
| "stand here and wait for a rail shot" | hold at P watching O with the rail (and S4, S8) |
| "move through this room but look at this door" | go, with a point to watch (S4) |

**C. The head's output: the list of intentions**

For every candidate, how much better it is than what he is doing now (from A6 and its own judgment), and the one instruction it sends.
Both go back into the head 0.2 s later with: the instruction he is on, how long, A1 to A6 as they read when he took it and as they
read now, and the change signals (he came into view; a sound; how far S1 has moved since he committed; a clock in S7 crossing the
time to get there).

## The verbs are a toolkit, not a quota (owner, 2026-11-10; CLAUDE.md hard rule 12)

"The point of the actions is to give him access to the toolkit of common techniques. He can then chose to use them when he sees fit,
or perhaps even learn new ways to use weapons that nobody has ever thought of ... we are not prescribing that he must use them with %
frequency. That is never going to work. We put him in the situation where he learns to use them."

| | What it means in the build |
|---|---|
| The verbs (go, contest, hold, spam, push, cut off, break off) | exist so that he CAN do each: the hands are drilled in situations where the verb can pay, and the head may choose it |
| How often he uses one, and with which weapon | his own, from what wins. No share, rate, weapon mix or hit rate of the pros is a target, a pay, a lesson, a pull or a pass mark anywhere in this run |
| The pros' demos | measure things: what a place is worth (the map sense's start), the aim parameters (aim3), the situations a drill starts from (a place, a weapon in hand, an enemy on his way: a starting state, not a label for what to do there) |
| The tables of what the pros do by weapon in this card | readouts, shown beside his; nothing is tuned to them |
| Still open for the review | the appraisals' third data source in "How each is trained" (the pros' games with their instruction inferred by a rule of mine) teaches the forecasts from what pros chose to do. It is a forecast of outcomes, not a pull on his choice, but the instruction labels are my inference of a player's choice: to be decided whether it stays, or the forecasts learn from his own play and the frozen moments only |

## Knowing an item is up is not going for it (owner, 2026-11-10)

"He should *know* it, but not always act on it to be present at the exact time, that decision should be able to be selected, learned
and trained." "Item X is up, but I'm going to do this instead": most people do not stand on the mega the moment it spawns.

| Part | What it means in the build |
|---|---|
| He knows | The items' clocks and "up" as he knows them (his own pickups, what he saw or heard) stay inputs of the head, whatever he is doing; S7 (who takes it next) is asked every tick |
| He may leave it | An up item is one candidate ("contest X") beside the others; nothing in the head's lesson prefers it. For every big item that is up or due, each OTHER candidate is also asked **A7: if I do this instead, does the enemy take X before I can?** (a chance; scored against who took it), so "hold here first, the mega after" is rated with the mega's risk in it |
| What must not force it | No rule, teacher or lesson names an up item as the target (the item rule and item teacher stay off). The pickup pay in the hands' table pays the pickup whenever it happens, not for being first to the frame |
| The weak point | **Found 11-10: the judge cannot see items at all** (test 5d), so a branch's end scored by it reads every delay of a pickup as a loss. The branch's end must be scored by something that knows the item is up and who is nearer: his own learned value, or the judge with an item term ([RUNDOWN.md](RUNDOWN.md), decision 1) |
| The measure | How long a big item stands up before it is taken, and what the taker did in that time: the pros beside him. Needs the items' clocks in the demo sets (the same addition the contest inference needs) |

## How each is trained

| Part | The lesson | The data |
|---|---|---|
| S1 to S7, S9 | as today: each against its own truth | his games |
| S8, the map sense | regression on what the next 5 s brought (dealt, taken), by the weapon in hand; the per-place corrections decay toward the pros' fit | his games; the pros' games all run (the fit to them is the seed) |
| A1 to A6, the appraisals | regression and chance against what the instruction brought | **the frozen moments** (every sampled candidate has its true outcome from the same moment); his games (the instruction he held); the pros' games (their instruction inferred by rule) |
| The head's choice | toward the candidates that came out best in the frozen moment (its five best and three others played out); a share of the game's pay on its choice. No pull to the pros (CLAUDE.md rule 12) | the frozen moments; the pros' games |
| The keep choice | the game's pay | his games |
| The hands | the game's pay, with the instruction as an input | his games; the drills |

## Teaching the hands a verb

Putting them in the situation often enough is most of it, but three things have to be true or the practice teaches nothing:

1. **The situation is one where the verb can pay.** A drill begins from a pros' moment of that verb (his place, the weapon in his
   hand, the enemy on his way), with the instruction given, and is paid by what happens: the game's own pay, nothing invented.
2. **The hands can read the instruction before they are judged on it.** Its token opens first (1.7a judged the order while the hands
   read it at a hundred-thousandth of its weight).
3. **The simulator lets the verb pay at all.** A scripted player who does the verb perfectly (waits, fires the frame the enemy
   shows) is run first. If even he loses the exchange with the rail under the aim limits, no practice fixes it: the limit is the finding.

**A readout, not a target (rule 12):** what the pros do with each weapon beside what he does today (1.7a's update 90, the next 5 s with the enemy near; `tools/run/pro_verbs.py`):

| | The pros | He |
|---|---|---|
| Waiting unseen (a hold): share of the time near the enemy | 8.0% | 5.4% |
| ... the weapon in hand then: rockets / rail / lightning | 60 / 21 / 8% | 16 / 1 / 75% |
| ... what it brings (deals less takes): rockets / rail / lightning | +8.8 / +7.9 / +2.0 | −7.2 / −3.2 / −0.5 |
| In a fight, the weapon in hand: rockets / rail / lightning | 37 / 23 / 32% | 20 / 1 / 71% |
| ... what it brings: rockets / rail / lightning | +23.7 / +11.6 / +12.4 | −3.3 / −18.1 / +5.8 |
| Trigger time with nobody in view: rockets / rail / grenades | 71 / 77 / 93% | not recorded |

The pros carry rockets or the rail while the enemy is unseen and go to the lightning when the fight is on. He carries the lightning
everywhere, and in his hands rockets and the rail lose. (The pros' numbers are from the recording player's side, who is more often
the winner: the levels flatter them; the order of the weapons is the finding.)

## New inputs

| To | What | How many (first count) |
|---|---|---|
| The head, about here | the map sense at his place by weapon (rockets, rail, lightning) and for passing through; the best opening to watch | about 8 |
| The head, a candidate | its verb, weapon, the map sense at its place, the way there, the clocks it depends on, its forecast (6 numbers) | about 16 a candidate, 20 to 30 candidates |
| The head, about itself | last tick's intentions; the instruction it is on, for how long; its forecast then and now; the change signals (the enemy came into view, a sound, the belief's shift since it committed, an item's clock) | about 40 |
| The hands | the instruction (1.7's token: verb, place, point) and its weapon; the map sense at his place | 10 (exist) + about 5 |
| The keep choice | the change signals only | about 6 |

Everything about the enemy comes from the brain's belief, never the truth (the fairness rule). The truth is used only to score lessons.

## Pay and learning

| | Paid by the game | Taught |
|---|---|---|
| Hands | frags and deaths, the items, the judge, damage 0.002 zero-sum | drills for each verb |
| Keep choice | the same | |
| Head | a share, on its choice | the frozen moments (his own play, scored by the game) |
| Map sense, appraisals, brain | no | outcomes; the pros' games |

Rule 11: the head's scores and the appraisals' part of the choice both carry the decay and are recorded.

## Before any training: the tests

| # | Test | State |
|---|---|---|
| 1 | The seeds forecast the pros' and his games on a held-out half | **version 1** (2-second slices in view): AUC of "hit for 20 or more" 0.775 on the pros (2.0b's number 0.734; no map 0.729), 0.872 on his games (0.862); it rated the rail worst everywhere. **Version 2** (`tools/run/seed_calib2.py`: the next 5 s of every moment with the enemy near, in view or not; taken and dealt): the rail and rockets now read as the weapons for distance and for the rooms behind (pictures `docs/design/space/seed2_*.png`). R2 on the pros' other half: takes 0.098, deals 0.139, deals less takes 0.042 (no map: 0.066, 0.090, 0.021). **On his games the exchange is not forecast at all (−0.04)**: the pros' map of who wins the exchange does not hold in his games |
| 2 | The pros' demos give the damage they deal | **done**: the hit counter is in `sets_lite2` (1,255 games); it checks out (the pros' lightning lands 32% of its cells, the rail about 45% of its shots). Damage = hits by a nominal damage a weapon; rockets' splash is the weak point. **What it shows**: standing still, the pros get +10.5 (rockets) and +9.8 (rail) in 5 s against +5.9 with the lightning, and take 28 against 44. **In his hands it is the other way round**: rockets −3.8, rail −9.4, lightning +1.5 (1.7a's update 90). So today the lightning is right for him: his hands cannot yet make the burst weapons pay |
| 3 | A moment can be saved and restored | **yes**, in the simulator today (mid-game starts use it); the networks' memories are the trainer's to save |
| 4 | Branching gives a signal: the same moment under each of today's 16 targets and in free play, repeated | **done** (`tools/run/branch_test.py`, `branch_hook.py`; 1.7a's update 90 against itself, 120 frozen moments on eight maps, 54 branches each, outcomes over 8 s). **It works**: one match's moment copied into the others with both networks' memories; free play from the copy reads −0.09 ± 0.05 of pay against the opponent (level). **A target forced for 4 s loses whatever it is** (−0.27 to −0.66; his own −0.33): a rigid hold takes away his re-deciding in a fight, so a branch forces the first choice for 1 s and then plays on. **The signal**: the first choice is 9 to 12% of one branch's outcome; about 10 branches a target make the order half signal. **His own target is among the best three in 30 to 38% of moments (chance 18%)**: better than chance, far from the best. **The cost**: 8 s of 54 branches is 17,000 match-frames, about 35 s of one core in the checks' code. **What it means for the design**: one moment cannot rank its options (too noisy); many moments with few branches each teach the appraisals, which average the noise, and the head is taught toward the appraisals' order |
| 5 | The pros' instructions inferred by rule: how often they hold, spam, contest; samples read with the owner | **first part done** (`tools/run/pro_verbs.py`: hold, move unseen, fight, spam; the table under "Teaching the hands a verb"). The contest needs the items' clocks, which the lite sets do not hold; the samples are not yet read with the owner |
| 5b | The held-angle probe: can a hold pay under his aim limits? | **done 11-10, corrected** (`tools/run/hold_test.py`, `hold_hook.py`). The first reading (a first shot 650 ms after the enemy is in view) was my script turning slowly and is withdrawn (owner: "650ms doesn't look right"). Measured: the simulator lets him notice at 200 ms; the pros' held shot leaves at 275 ms (the fast end 200). With HIS OWN aim, made to stand at a pros' holding place with the rail, pre-aimed on the enemy's path (292 frozen moments, 8 s): dealt less taken −9.4 ± 2.2 (handed back 1.5 s after contact: −6.4 ± 1.7) against free play −3.2 ± 1.3; his first shot at 425 ms, 47% hit. Under AIM3's default: −9.2 (−3.7), free −1.0; 375 ms, 43%. **The hold does not pay yet with his present hands under either model; the limits allow it.** The hold drills wait until he has trained under AIM3 |
| 5c | The aim parameters from the pros (rule 12: parameters, not hit rates) | **done 11-10**: [AIM3.md](../../design/AIM3.md). The pros' aim error is about one half body width at every distance; a still view sees a crosser no worse than a following one; the error is raised about 150 ms after a turn-round and 250 to 400 ms after he appears; a flick's endpoint error is about 7% of its travel. AIM3 built (off = bit-identical), default / better / max proposed |
| 5d | Does the judge's value move with an item up and untaken? | **no, by its code** (`sim/win_judge.py`: the score, the time, both stacks, three weapons). A branch scored by it cannot value leaving an item for now: RUNDOWN.md decision 1 |
| 6 | The appraisals' skill per verb on recorded games and on the branches | after 4 and 5 |
| 7 | What his own games do to the map sense's corrections | after seeds version 2 |
| 8 | Drills: each verb carried out by the hands | after the instruction's build |
| 9 | Identity at the start; ten updates and a check; under the control = no start | last |

## The order things open in

| Gate | Opens | Passes when |
|---|---|---|
| 0 | the map sense and the appraisals learn; the frozen moments run; nothing reads them | tests 1, 4, 6 |
| 1 | the damage pay to 0.002, zero-sum | no fall against the control; megas and reds head to head |
| 2 | the hands read the instruction in drills | test 8, verb by verb |
| 3 | the head reads the map sense, the appraisals and itself, with today's choices | no fall; quiet re-decisions flat |
| 4 | the head's instructions go to the hands in games, opened slowly from none (no rate is prescribed: he chooses) | the forecasts of what he chose match what it brought |

Whether these are one run or several is decided as each gate's test is read.

## Guards, from update 1

Megas and reds head to head in each check; the keep choice's quiet re-decisions over 0.08; frags a match-minute under 1.5; the sizes
of every part of a summed choice.

## Weaknesses

- **The branches are played against himself.** They say what is right against his own play; nobody there holds an angle yet. The pull
  to the pros in the map sense and in the head is the defence, and holders appear as soon as he learns to hold.
- **A branch is noisy.** If test 4 shows the options cannot be told apart at a cost we can pay, the head's lesson falls back to the
  appraisals' averaged forecasts.
- **The pros' damage dealt is counted by hits, not points**, and their instructions are inferred by a rule of mine.
- **The hands may fail a verb** (the rail under his aim limits is the likely one). It is then fixed before the head may choose it.
- **It is the largest change so far**: five new parts. Each has its own test and its own gate so a failure can be pinned.
- The explicit orders of 1.7 (the kinds and the pointer) are rebuilt as the instruction; the pointer on his targets (`PADD`), suspected
  in 1.7a's slide, is not carried over.

## Decided (owner, 2026-11-10)

| | Decision |
|---|---|
| The two changes from test 4 | accepted: the head is taught toward the appraisals' order; a branch forces the first choice for a second, then he plays on |
| The verbs | the seven, "for now" |
| The head's pay | **his own play**: the frozen moments (each branch is him playing on, scored by the game's pay and the judge) and a share of the game's pay on its choice. **No pull to the pros on the head's choice**: "every time we've tried to pull him towards pros he's gone to shit afterwards". The pros' games still teach the forecasts (what an instruction brought): information, not a pull on his choice |
| The map sense | starts from the pros' fit; the slight pull back to it stays for now ("a static feature of the map averaged from existing games"); he is "open to removing the map pull, and just using it as a starting point": the pull is a live number, and 0 is allowed |
| The damage pay | 0.002, zero-sum, in at the start |
| The perfect-hold probe | "yes just do it": `tools/run/hold_test.py` |

Where the rest of this card still says "the pull to the pros" for the head, this table replaces it. The guard for it: the head's
choices by verb in every check; one verb taking nearly all of them is reported at once.

## Decisions for the owner (as asked on 11-10; answered above)

1. The seven verbs: is the list right, and is anything missing (for example "bait", or "time an item" as its own verb)?
2. The head no longer paid by the game, only taught by the frozen moments and the pull to the pros: confirm, or keep a small share of the game's pay on it.
3. The pull to the pros in the head's choice, all run: its strength is set from test 5; confirm the idea.
4. The damage pay at 0.002 zero-sum as gate 1 of this run, or as a short run of its own first.

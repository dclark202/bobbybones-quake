# v0.2.1: the manifest (2026-10-12, rewritten in the evening around the owner's four goals; started 2026-10-12 20:31 on his go; changes during the run in section 9)

**The run on one page: [RUN_v0.2.1.md](RUN_v0.2.1.md).** This file is the long write-up behind it.

**The names.** v0.1 is `duel_gru_v15c`. v0.2 (`duel_gru_v0_2`) ended on 2026-10-12 at 08:43
([REPORT_v0.2.md](../v0.2/REPORT_v0.2.md)) and is the network on the public server since 15:15. **v0.2.1** (`duel_gru_v0_2_1`)
is this run: from v0.2's end, one night. The proposal it grew from is [PROPOSAL_v0.2.1.md](PROPOSAL_v0.2.1.md); the
thinking behind goal 1 is [../v0.2.1/ENEMY_MODEL.md](ENEMY_MODEL.md).

**Words.**
- **The movement autopilot**: the separate small network that runs and strafe-jumps him to a target when he switches it
  on (in the code and the older documents: "his legs", `LEGS`).
- **The guessing game**: questions he is asked every frame about what he cannot see, corrected afterwards by what was
  true. Nothing is paid for it (the trainer's `--aux`).
- **The item rule**: the hand-written rule that teaches his choice of what to go for next (the nearest item he can use).
- **First half, second half**: the night's two parts (in the scripts and the older documents: leg 1, leg 2).

**The owner** (2026-10-12, evening): "I think that guessing game is the real move here, together with attention B and
C. Can you update the manifest doc for how to train with these main things? know where the enemy is/how to predict his
location/how to act accordingly (strategic); maintain speed (mechanical); use rockets effectively (mechanical) +
downtune lg aim; good positioning (strategic -- in line with the first bullet) maintain high ground, etc. I think we
should push the guess as part of attention B+C it makes sense to ship those together since it's the whole package.
Without one part it's not as effective".

## 0. The four goals: what trains each, and how we will know

| # | The goal | What trains it in this run | When | Where he is today, and the pros | Not in this run |
|---|---|---|---|---|---|
| 1 | **Know where the enemy is, predict him, act on it** | **The guessing game, pushed**: eight questions (four until today) at twice the weight, which with the new questions is about eight times the pull on his shared layers. **The item rule silent in a contest**: where he believes the enemy nearer to the item it names, the rule says nothing and what he does is his own to find. **Places as targets**: somewhere to go that is not an item (wait, cut off, hold). The attention part opened to the places and the ways | from the start, all night | his guess of an unseen enemy's place is 640 units off (a blind guess: 800). He comes to an item the enemy is nearer to 61% of the time, the pros 28%; with 50 of stack less than the enemy 37%, the pros 10%. Fights with a stack under 60: 5.0%, the pros 1.2%. Hiding the unseen enemy from his choice of what to do next costs him nothing (51.0% against himself) | his answers wired straight into his choices (the next run: it can start from this run's end at no loss); opponents that hunt and ambush; games paid by the game |
| 2 | **Maintain speed** | **The movement autopilot's lesson**: on the stretches he hands to it, his own keys and mouse are pulled toward what it did; one stretch in ten he must run himself, so what he can do alone is measured | from the start, all night | at 400 or more 8.6% of a game, the pros 17.5%. His own mouse turn agrees with the autopilot's 6% of the time (ceiling 71%). Where he runs himself he is at 400 or more 2% of the time, carried 22% | an autopilot that looks where the enemy will come from; second and third ways |
| 3 | **Use rockets** (lightning aim down: put off) | **Four of his lives in ten are rocket lives** (lightning 15%, rail 10%, general 35%). **The pros' weapon in hand** while nobody is in view. **His aim is left as it is in this run** (the owner: "we need roughly lg down but rail up. can put this off for now"; a tracking limit is measured for later: pretest 18) | second half | rockets in hand with the enemy in view 22%, the pros 39.5%. Rockets a minute 2.7, the pros 10.8. Frags a death in a rocket life 0.82 (in a lightning life 1.17). Lightning 39.7% of cells, the pros 31.6%; rail 40.0%, the pros 42.7% | the aim change; rocket jumps |
| 4 | **Position: high ground** | **Places as targets**: the eight places a map where the pros hold. The guessing game (goal 1: a position is good against where the enemy is). **A hit from above pays more, one from below less** (small: about 3% of his pay) | places from the start; the height pay in the second half | higher than the enemy in view 16.6% of the time, the pros 26%. No target at all 8% of a game (Aerowalk 28 to 32%) | |

**Goal 1, plainly.** By the morning he should KNOW more: that is measured, his answers against the truth. ACTING on it
is what the silent rule and the places make room for; nothing in this run forces it. His answers and his choices are
read off the same 512 numbers, so what he knows is within his choice's reach, and until tonight the item rule outvoted
it on every frame. The direct wire from his answers to his choices is the next run's step.

**What would count as worked** (the checks through the night, the scorecard at the end):

| Goal | Worked | Did not |
|---|---|---|
| 1, knowing | his guess of the unseen enemy's place under 450 units off; the landmark he is nearest to named right clearly more often than "where I last saw him" | no better than at the start |
| 1, acting | he comes less often to an item the enemy is nearer to (61% toward 50%); the blindfold on his choice begins to cost him (51% toward 47%) | both unmoved: then the direct wire is what is missing |
| 2 | his own turn agrees with the autopilot's over 40%; at 400 or more over a game 12% or more | agreement under 20%, or the time at 400 or more unmoved |
| 3 | rockets in hand with the enemy in view over 33%; frags a death in a rocket life toward 1.0 | rocket lives still his weakest by the same margin |
| 4 | higher than the enemy in view over 20%; time with no target under 3% | unmoved, or the mega and the low items fall |
| all | 45% or more of the frags against the control (v0.2's end); hits in view within two points of the start | under 40% at two checks: the run stops itself |

## 1. The package, and the night's two halves

**One package, as the owner asked: the guessing game with stages B and C, started together.** What of B and C is in:

| Part | In this run | Why not, if not |
|---|---|---|
| The guessing game (C), widened and at twice the weight | yes, from the start | |
| The attention part opened to its new tokens: places, holding places, ways (B) | yes, from the start | |
| Places as targets (B) | yes, from the start | |
| The movement autopilot's lesson (C) | yes, from the start | |
| The draw of his lives, the pros' weapon in hand (C) | yes, second half | |
| The aim step (the proposal's) | no | the owner, 2026-10-12 evening: lightning down but rail up is wanted, and no setting measured gives both |
| Second and third ways (B) | no | a small lever until the walking map has the pros' drops and jumps: a second way differs from the shortest on 9 to 24% of his starts |
| Whole ten-minute games, paid by the game (B) | no | they need games that begin in their middle (the owner: yes, build it); a ten-minute game from its start is 4.8 hours of a run |
| An autopilot that looks, an autopilot that stands (C) | no | looking was not learnt in two trainings; standing made him 2 to 6% slower (Aerowalk 17%) |

**The two halves.**

| Half | Length | Running | Goes on if |
|---|---|---|---|
| First | half of the time to the end (nine hours with the end at 15:00) | goals 1 and 2 and the places of goal 4: three lessons and one new choice. No pay changes, no opponent changes | its two last checks are not under 45% against the control and his hits in view are within two points of the start |
| Second | the rest | everything of the first half goes on; added: rocket lives, the pros' weapon in hand, the height pay | (the end of the night) |

Why not everything at the start: the second half changes which lives he lives and what a hit pays, and it lowers his
strength by design (four lives in ten become rocket lives, where he makes 0.82 frags a death). Started together with
three new lessons, a fall could not be traced to its cause, and the check that protects his aim would have no level to
stand on. If the first half does not pass, it runs on to the end and the second half waits for the next night.

## 2. What goes in, change by change

Everything is in the repo, every switch off by default; with all off the simulator and the trainer are v0.2's bit for
bit (16 of 16 fixed runs at the merge; again for each switch added since).

| Half | Goal | Change | The switches | Its setting, and where it comes from |
|---|---|---|---|---|
| 1 | 1 | The guessing game: eight questions, not paid | `--aux 0.2 --aux-warm 60 --aux-heads place,appear,fight,items,target,strength,first,near` (the second half: `--aux-warm 0`, it is a new start of the trainer) | section 2a; the weight rises from nothing over the first hour. At 0.3 with no warm-up his aim held but the first updates moved him three times the usual (pretest 17): the run is gentler than the test in both |
| 1 | 1 | The item rule silent where he believes the enemy nearer to the item it names, by two seconds of way or more | `RULE_CONTEST=2` | 4 to 9% of the rule's item frames; no pay, no new lesson (pretest 13); the owner's decision 17: on |
| 1 | 1, 4 | Places as targets: eight holding places a map from the pros, his to choose like an item | `TARGETS=1 TARGETS_FREE=2`; the start made by `tools/targets_init.py open --from-nothing 0.3` | opened only out of the readings he would have chosen "nothing" at; a place is left for an item at any reading: level against the control in 160 games (pretest 7) |
| 1 | 1, 4 | The attention part opened to the new tokens over the first hour | `--gate-open 60 --gate-from -6` | as built |
| 1 | 2 | The movement autopilot's lesson; one stretch in ten withheld | `LEGS_LABEL=1 LEGS_KEEP=0.9`, `--legs-teach 0.05 --legs-teach-trunk 0.25 --legs-teach-warm 60` | with the weight rising from nothing his step stays 0.03 to 0.07 (0.32 with no warm-up): pretest 6 |
| 1 | | The two-minute value estimate at full from the start | `--long-gamma 0.9998 --long-ramp 0` | v0.2's end state |
| 2 | 3 | The draw of his lives | `STYLE_MIX=rockets:0.40,lightning:0.15,rail:0.10` (general 35%) | by the draw alone rockets in hand with the enemy in view 21.9% to 33.4% (pretest 10); the owner's decision 3 |
| 2 | 3 | The pros' weapon in hand with nobody in view | `HAND_TEACH=1`, `--hand-teach 0.1 --hand-teach-trunk 0.05 --hand-teach-warm 60` | a mild step and a small lever (pretest 11) |
| 2 | 4 | A hit from above worth more, one from below less | `HIGH_PAY=0.25` (at 128 units of height, in proportion below that) | about 3% of his pay moves by height as he plays today (pretest 9); the owner's decision 6 |

Unchanged from v0.2: the ten maps, 10,080 players (30 simulator processes of 168 matches), the rounds, the pay and the
prices (the speed pay with them), the scripted opponents, his aim (level 1.5, delays 100 / 200 ms).

### 2a. The guessing game's eight questions

Every frame, for an enemy he may not see; corrected afterwards by what was true in the simulator. The truth is a label
only, never an input: a player learns the same from watching both sides of a demo.

| # | The question | The answer's form | In it since |
|---|---|---|---|
| 1 | Where is he? | one point | v0.2.1 as first written |
| 2 | Which landmark is he nearest to, now and three seconds on? | odds over the map's fifteen landmarks (the mega, the armors, the three big weapons, the eight holding places: what his own choice is made among) | tonight |
| 3 | Where does he next come into view? | two angles | first |
| 4 | What is he going for? | odds over the same list his own choice is made from; the truth is the other seat's own choice | tonight |
| 5 | How strong is he, and what does he hold? | his stack in four bands; the weapon in his hand | tonight |
| 6 | Who takes the mega next, and the red armor? | I, he, nobody within seven seconds | tonight |
| 7 | How does the next fight end? | a frag, fragged, neither; the damage | first |
| 8 | When are the mega and the red armor back? | seconds | first |

Question 2 is the cure for the single point's flaw (it cannot say "at the red armor or at the mega" and lands between
the two). Questions 4 to 6 are what a pro asks before he chooses: go elsewhere, get there first, or wait for him. The
new answers start from nothing, so their pull on his shared layers rises by itself as they are learnt.

## 3. The control, the league, the checks

- **The control** is v0.2's end (`policy_control.pt`: it answers as `policy_end_v0_2.pt` in 15,360 of 15,360 choices).
  It is also a standing opponent in the league, v0.1 the other (`--anchor-p 0.25`); beside them his last eight selves.
- **From the newest save whenever the check loop is free** (a save every ten updates, about 65 minutes; a check about
  every hour and a half): 16 games a map against the control on the ten maps, the seats swapped in every second
  process, read by kind of life; his speed profile; at the start, the change of halves and the end also the stand-in on
  the two held-out maps and three trained ones.
- **With every update**: his answers in the guessing game against the truth, the share of frames the item rule was
  silent, his hits in view, his step by output.
- **The change of halves**: when the first half's time is up, if its two last checks are not under 45% against the
  control and his hits in view are within two points of the start. Else the first half runs on to the end. The second
  half is a restart of the trainer from the first half's last save with its settings added; its warm-ups count from its
  own start.
- **Reports**: a line at each check through the night, check-in reports at 06:30 (with the change of halves) and at
  noon (the owner's word), the summary at the end with the scorecard beside the pros and the regulars, the contest
  measures of goal 1 and the blindfold.
- **It stops by itself** on a stall (no update for twelve minutes) that a restart from the last save does not cure, or
  under 40% against the control at two checks in a row.
- **Nothing is promoted.** After the run: real games against the game's Nightmare bot on the quiet PC, and a video.

## 4. The PC

- **The eight performance cores only**, for the trainer, its simulators and the checks (affinity `0xC03C3`; RESULTS
  2026-10-12 13:00). The checks run at low priority in the trainer's gaps (60% of an update is the learning step, which
  leaves most of the cores idle); a job that does not end in 75 minutes is stopped and tried again. The efficiency
  cores stay unused: even a job pinned alone to one died 3 times in 20 on the afternoon of 2026-10-12 (0 in 1,300
  simulator-minutes on the performance cores).
- **One numpy thread a process** (`OPENBLAS_NUM_THREADS=1`): with a thread a core every process reserved 0.6 GB of work
  space it never touched, and a trainer with its 30 simulators filled the PC's 67 GB limit twice on 2026-10-12.
- **Speed**: about 10,000 steps a second (v0.2: 14,500): an update every 6.5 minutes, of which 60% is the learning step
  on the card (1,080 pieces of 384 frames, fed by one processor thread) and 40% the simulators. A night of 14 hours is
  about 500 million steps (v0.2: 564 million in 10.8 hours).
- **The card**: 13.2 of 16 GB with an update cut in 360 pieces. The owner's game client and the run do not fit on it
  together: no playing on this PC while it trains.
- The owner's, not tonight's: the board's BIOS update (the processor runs its pre-launch microcode), a larger page file.

## 5. Pretests

In the rows written before the evening "his legs" is the movement autopilot and "leg" a half of the night.

| # | Pretest | Result |
|---|---|---|
| 1 | Legs trained to look and stand together | standing learnt (arrives 91%), looking not (17.8% against 16.6%), plain speed down 3%: stopped |
| 2 | Legs trained to stand only (`move_v16b`, 40 minutes), then the ten-map test of today's legs | passes (items a minute +2.4% over `move_v15n`, no map more than 5% under; Campgrounds on the line); Blood Run's upper ledge held 91% of the time against 76%, the lower one no better. But its pupil is slower: 2 to 6% on most maps, 17% on Aerowalk, and told to stand it brakes all the way to the place (at 400 or more 22% of the way against 35%). Out |
| 3 | v0.2's end checks | [REPORT_v0.2.md](../v0.2/REPORT_v0.2.md) |
| 4 | The merge: with everything off, bit for bit | 16 of 16 fixed runs |
| 5 | Size and speed on the card | section 4 |
| 6 | The legs' lesson with its warm-up | his step 0.03, 0.07, 0.04, 0.04 over four updates while the weight rose to a third; his own turn's agreement with his legs' 7, 11, 24, 29%; sideways key 48 to 57%; in withheld stretches his turn 6 to 17%; on target 28.0 to 28.3% |
| 7 | Level check of the opened place choice against the control | evenly at 5% of all his readings: 44.7% in 128 games (42-7-79), a fail: a place holds like an item, 5% of readings was 19% of his time and came out of the armors' time. Out of his "nothing" only: 48.0% in 128. The same and left for an item at any reading (`TARGETS_FREE=2`): **50.9% in 160 games (86-9-65)**, the mega 43.6% of its spawns against the control's 44.6% |
| 8 | The aim step (not in this run: decision 18) | v0.2's end, seven settings, three maps, 36 games each against himself: the level from 1.5 to 0.5 at 100 / 200 ms moves lightning 39.7 to 37.8% (the pros 31.6), rail 40 (no trend), first hits unchanged (0.28 to 0.30 s at 0 to 5 degrees off; the pros 0.32), 1.4 points against the stand-in. The tracking delay at 125 ms: lightning 33.4% but rail 40.0 to 33.4%, his opening fire at wide angles under the pros', 3 points against the stand-in; with the acquire delay at 250 ms his first hit is slower than the pros' (0.41 s). On his server by the game's own table his lightning already reads about the people's (v0.1: 29.7%; the people 31.7%) and his rail ten points under theirs. Delays are whole frames of 25 ms |
| 9 | The size of the height pay | v0.2's end against itself, the same games at four sizes: 14% of his damage is dealt from above, 11% from below; 0.25 moves 3.1% of his pay between the two players (0.1: 1.25%, would drown in the entropy bonus; 0.5: 6.25%, a rule and not a nudge) |
| 10 | The weighted draw of lives at the start | by the draw alone rockets in hand with the enemy in view 21.9% to 33.4%, rockets' share of his frags 17% to 28%. The second half's baseline, frags a death under the mix: rockets life 0.83, general 0.91, rail 0.80, lightning 1.18 |
| 11 | The weapon-in-hand pull and the second half's first step on the card | dry run of 13:50, two updates: 13.1 GB; his step 0.043 then 0.026, of it his weapon key 0.009 then 0.0003 at the full weight; 6.3 then 1.5 weapon changes a minute; lives drawn 36 / 41 / 9 / 14%. Where the lesson speaks his hand is already the pros' while travelling (rockets 62% against 60%) and differs only while holding a place (30% against 73%; 2% of his time) |
| 12 | The people scale with v0.1's first day | v0.1: 32% of 185 frags against four people, rating 1269 (v14's end 1251); in real games 14% of 119 |
| 13 | The guessing game at three times the weight (four questions) with the silent rule: dry run of 16:37, four updates beside the same at the plain weight | his step 0.064, 0.064, 0.051, 0.050 (at the plain weight 0.032, 0.074, 0.043, 0.045); on target 28.1, 26.7, 28.2, 29.4% (28.0, 26.8, 27.8, 28.3%); the unseen enemy's place off by 633 then 484 units (640 then 548); where he next appears off by 52 then 43 degrees (50 then 46); the rule silent on 4.4, 6.8, 8.9, 8.4% of its item frames. Learns faster at no cost seen |
| 14 | The blindfold: v0.2's end against itself with what it knows of an unseen enemy hidden | from all his outputs: 14.9% of the frags (64 games: 3 won, 60 lost). From his choice of what to do next only: **51.0%** (160 games: 79-7-74): the choice does not use it. The method's own control, the items' state hidden from that choice: 44.8% (160 games: 55-9-96): what the choice does use, the method sees |
| 15 | Contest sense beside the pros (999 pro games, 192 of his) | who takes a contested mega or red armor: the same (the race). Who comes when the enemy is the nearer: the pros 28%, he 61% (at the mega 30% and 71%). When 50 of stack behind in a contest: the pros 26%, he 55%; the enemy clearly nearer too: 10% and 37% |
| 16 | The four new questions as code | with them off the simulator and the trainer are the same bit for bit (4 fixed runs, 203 arrays each); their labels equal a plain loop's on hand-made and recorded cases; a network with the new layers resumes, and the checks' tools load and play it exactly as without them |
| 17 | The eight questions at three times the weight with the silent rule on the card (dry run of 19:20) | his step 0.199, 0.167, 0.115, 0.091 (the four questions at that weight: 0.064, 0.064, 0.051, 0.050): the first updates three times the usual, falling; on target 28.1, 26.2, 28.0, 28.7%: his aim held; the unseen enemy's place off by 630 then 491 units; the landmark he is nearest to named right 18 then 28% of the time (three seconds on: 17 then 24%); the weapon he holds 53 then 70%; what he is going for 40 then 43%; the rule silent on 4.4 to 8.9% of its item frames; 13.0 GB on the card and 10,000 to 10,500 steps a second, as without. The run takes 0.2 with an hour's warm-up (the warm-up checked in a small trainer: the weight rises as set) |
| 18 | A limit on tracking a fast-crossing enemy (`PERCEPT_SPEED`: his error in judging where the enemy is grows with how fast the enemy's direction moves) at aim level 0.5 | v0.2's end against itself, 36 games a setting: at 0.012 lightning 37.8% to 35.3%, rail 37.1% to 37.0%, first hits as they were, 78.9% against the stand-in (76.6%); at 0.025 lightning 31.6% (the pros' 31.6%) but rail 32.6%, first hits 0.29 / 0.35 / 0.44 / 0.76 s (the pros 0.32 / 0.44 / 0.55 / 0.76), 70.0% against the stand-in. It lowers lightning alone at the small value; it does not raise rail. Not in this run (decision 18) |

## 6. What could go wrong

- **A lesson costs his aim** (it has before, and it did not come back). Three lessons run at once in the first half.
  The autopilot's reaches a quarter into the shared layers and rises over an hour; the new questions start from nothing;
  hits in view are in every line; the second half does not start on a fall of two points.
- **The guessing game takes room from playing**: its pull on the shared layers grows as the new answers are learnt,
  past what four updates of a dry run show. Watched with every update (his step by output, hits in view); the cure is a
  restart from the last save at a lower weight.
- **The silent rule costs pickups** in the moments it is silent: that is the point of it and it is counted (the mega
  and the red armor by spawn in every check). Off again by a restart if the big items fall.
- **A new choice costs him at the start** (twice before). Places are in as their level check of 160 games passed them.
- **The second half dips by design**: more of his lives are rocket lives, where he is the weaker player. Its checks are
  read by kind of life; the measure is the rocket life itself.
- **A process dies** (the processor's efficiency cores). The trainer is kept off them; a stall is seen within twelve
  minutes and the run restarts from its last save.
- **The PC's memory limit.** The free commit is read beside the run; one numpy thread a process.
- **The plugins know none of the new parts**: no real game with a v0.2.1 network until they do (B-233).

## 7. The public server

v0.2 is on it since 2026-10-12 15:15 (the owner's word; RESULTS 2026-10-12 15:15). Nothing is pushed by this run. The
plugin batch of 2026-10-12 09:59 is live (results and map vote, 5 s weapons, F3 in 1v1, the owner's mark, QLStats
lookup).

## 8. The owner's decisions

His answers of 2026-10-12 (his decision document, section 4), and what is open for the evening. The run starts on his
word.

| # | The question | His answer | So |
|---|---|---|---|
| 1 | Two halves, one run with everything, or two half-size runs | "your call" | two halves |
| 2 | May the second half start by itself when the first passes its gate | "yes" | it may |
| 3 | The draw of his lives in the second half | "your call" | rockets 40%, lightning 15%, rail 10%, general 35% |
| 4 | The aim step | "yes" | superseded by decision 18: his aim is left as it is |
| 5 | The pros' weapon in hand with nobody in view | "yes, all" | in the second half, all lives |
| 6 | A hit from above worth more | "yes, but this seems somewhat dangerous. I'm open to trying it" | in the second half at the small size (`HIGH_PAY=0.25`, about 3% of his pay); the mega and the low items watched |
| 7 | An autopilot that stands at a place | "your call" | out of this run (slower: pretest 2) |
| 8 | v0.2's end as the control, v0.1 in the league | "yes" | so |
| 9 | v0.2 on the public server | "we've already moved 0.2 up" | on it since 15:15 |
| 10 | Games that begin in their middle; the table a frag is paid by | "yes games can and should start mid way with a different variety of states (up/down/tied/stacked/not/etc.)" | to build for the run after; the table explained to him, his answer open |
| 11 | The QLStats lookup on for everyone | "yes" | it is on |
| 12 | Which player id is his | "tbd"; then (20:05) "I'm on it now playing on campgrounds you can verify my account id" | found by the server's own owner mark on his frag lines; the people reports keep him apart |
| 13 | Start and end | "let's discuss this later, likely I will review everything and we'll start the run around 9pm" | no start before his go; the end is decision 19 |
| 14 | Where the autopilot looks while it carries him | "explain more" | explained; not in this run |
| 15 | The BIOS update or the performance cores | "just use the performance cores" | so |
| 16 | The guessing game with stages B and C as one package, pushed | "I think we should push the guess as part of attention B+C ... it's the whole package" | eight questions at twice the weight, rising over the first hour (pretest 17) |
| 17 | The item rule silent in a contest (`RULE_CONTEST=2`) | "yes, it will and should affect item pickups but that's moot if he loses to every human. He should avoid an item that is being actively watched in a way that require him to approach from an inferior position. period." | on, from the start |
| 18 | Lightning down: the aim level alone (small), or with the tracking limit of pretest 18 | "we need roughly lg down but rail up. can put this off for now, but it's something to come back to."; "Leave aim untouched tonight is fine." | no aim change in this run; B-228 |
| 19 | The end: 07:00 or 11:00 | "you can go until 3pm tomorrow if need be, I would like a check in report at 6:30 am and noon." | the end at 15:00 on 2026-10-13 (nine hours a half); check-in reports at 06:30 and 12:00 |
| 20 | The go | "TBD likely around 9pm I would still like to play him first"; then (20:27, after the PC's restart) "Ok ready to go now. Before you start the run check the pickup logic in the sim to make sure it's not buggy ... Then start the run." | started 20:31 |

## 9. Changes during the run

- **2026-10-12 20:31: started** (`duel_gru_v0_2_1`), as sections 0 to 2 say: the first half for 554 minutes (to about
  05:45), the end at 15:00 on 2026-10-13. The owner: "Quick checks on the hour, nothing too detailed needed on my
  end, just a run health. 6:30 midway report and another at noon, with a planned end of 3pm; metric evals afterwards
  for validation. It can be stopped early or altered if you think something has gone wrong and can be fixed easily.
  Anything more substantial just stop the run and flag for me."
- **Before the start, the pickup reach** (the owner had seen him walk to an item and pass it without taking it): in
  7,767 pickups recorded on the public server the game takes an item within 36 units on each horizontal axis and at
  any height of a jump; the simulator's reach (a circle of 36, a height of 56) lies inside that everywhere. Not the
  cause, nothing changed (RESULTS 2026-10-12 20:35; B-241).
- **His feedback from watching v0.2 that evening**, for the runs after: rail should be 50 to 60% against people
  (B-228); with nobody in view he should look where the enemy must come from ("let's see what happens tonight, but
  keep this in mind": B-242); a pickup should be confirmed by its sound, "otherwise if he wants it he has to go back
  to it" (B-241).
- **2026-10-12 23:30: stopped by the watcher's rule.** Against the control 52% at the start, 36% at update 10, 25%
  at update 20, on every map; his aim unchanged, his stack and his deaths worse.
- **The night's arms** (ten updates each from the run's start network, then four maps against the control): none of
  the new parts 51%, the gate's opening alone 50%, the guessing game alone 46%, the item rule's silence alone 52%,
  the movement network's lesson alone 36%, the same lesson held out of the shared layers 30%, the withholding
  without the lesson 55%. The lesson of section 1 (his own keys and turn taught by the movement network) is the
  cause and is out of v0.2.1 (RESULTS 2026-10-13 07:00; B-243).
- **2026-10-13 06:43: started again** on the owner's word ("You can restart the run now ... You can use the computer
  until 7pm, if you want to spend the whole time for the first half + early stopping, that's fine, we'll do the
  second half overnight"): the same start network, `--legs-teach 0`, everything else as sections 0 to 2 say; the
  first half only, to 19:00; no second half by itself. His words for the day: "give me a mid run report at noon and
  4, same hourly check ins, flag anything weird. Run the evals when it finishes, and after it's done make a
  recommendation on the second half". The first start's files: `first_start_1012` in the run's folder.

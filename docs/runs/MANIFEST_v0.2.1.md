# v0.2.1: the manifest (2026-10-12; not started: it starts on the owner's go; changes during the run in section 9)

**The names.** v0.1 is the network on the public server (`duel_gru_v15c`). v0.2 (`duel_gru_v0_2`) ended on 2026-10-12 at
08:43 ([REPORT_v0.2.md](REPORT_v0.2.md)). **v0.2.1** (`duel_gru_v0_2_1`) is this run: from v0.2's end, one night in two
legs. The proposal it grew from is [PROPOSAL_v0.2.1.md](PROPOSAL_v0.2.1.md); the owner's answers are in his decision
document of the day (section 8 here keeps them).

**The owner** (2026-10-12): "you can create all the new things you need. When v0.2 training is done run the metrics
eval, then run any tests needed before v0.2.1 summarize the results and present them to me with the proposed training
manifest. I will review then"; "So probably good to nudge him toward high ground ... I'm open to changing anything
about the training runs. So please think for awhile about this about how to most efficiently use the next run. Pro data
and player data from the server can be used to calibrate his ability as well"; "Do not promote the live server yet".

## 0. What it is judged by

v0.2 is level with v0.1 on the six maps both know and ahead on the four new to games, and plays as v0.1 did (scorecard
48% beside the pros). This run is to change how he plays. Each leg has its own measures:

| Leg | The measure | v0.2's end | The pros | Your regulars |
|---|---|---|---|---|
| 1 | his own view turn agrees with his legs' (on the frames they carry him) | 6% | ceiling 71% | |
| 1 | at 400 or more in the stretches withheld from his legs | 2% (carried: 22%) | | |
| 1 | time at 400 or more over a game | 8.6% | 17.5% | 17% |
| 1 | time with no target | 8% (Aerowalk 28 to 32%) | | |
| 1 | what he foretells: the unseen enemy's place, off by | 640 units (a blind guess: 800) | | |
| 2 | rockets in hand with the enemy in view | 22% | 39.5% | 44% |
| 2 | rockets a minute | 2.7 | 10.8 | 11 |
| 2 | frags per death in a rockets life | 0.82 (lightning life 1.17) | | |
| 2 | higher than the enemy in view | 16.6% | 26% | 40% |
| 2 | lightning: cells that hit | 43% | 32% | 32% |
| 2 | weapon changes a minute | 2.5 | 12.7 | |
| both | frag share against the control (v0.2's end), ten maps, seats swapped | 50% | | |
| both | hits in view (his aim must not pay for a lesson) | on target 28% | | |

Beside these: the stand-in on the two held-out maps (House of Decay, Dismemberment), the scorecard beside the pros and
the owner's regulars at the end, and his place among the people who play him (each by a permanent random id).

## 1. The shape: two legs, and why

| Leg | Length | Adds | Goes on if |
|---|---|---|---|
| 1. Movement and targets | half of the time to 07:00 | his own movement taught by his legs; the things he foretells; places as targets | its two last checks are not under 45% against the control and his hits in view are within two points of the start |
| 2. Weapons and height | the rest | the draw of his lives toward rockets; the second aim step; the pros' weapon in hand with nobody in view; a hit from above worth more | (the end of the night) |

- **Attribution.** Leg 1 is two lessons and at most one new choice; leg 2 changes which weapon his lives favour and what
  a hit pays. Started together, a fall in strength could come from any of seven changes.
- **v0.2 had learnt what it would in about five hours** (54.8% against v0.1 at 3.5 hours, 56 to 58% from then on).
  Fourteen hours on one set of changes would mostly be waiting.
- **The surest first.** His legs already show what the movement should be: that lesson has a known target, and in four
  dry-run updates his own turn went from 7% to 29% agreement with theirs with his aim where it was.
- Set aside: two half-size runs side by side (each learns at half the rate, and their results still have to be put
  together in a third run); everything at once (a night sooner if every change is good, a night lost if one is not).

## 2. What goes in, change by change

Everything is in the repo since the merge of 2026-10-12 (commit `ccdf9be`), every switch off by default; with all off
the simulator and the trainer are v0.2's bit for bit in 16 of 16 fixed runs.

| Leg | Change | The switches | Its setting, and where it comes from |
|---|---|---|---|
| 1 | His own movement taught by his legs: on the stretches he chooses his legs, his own keys and turn are pulled toward what they did; one stretch in ten is withheld (he asked for his legs and moves himself) | `LEGS_LABEL=1 LEGS_KEEP=0.9`, `--legs-teach 0.05 --legs-teach-trunk 0.25 --legs-teach-warm 60` | the dry run of 13:23 (section 5): with the weight rising from nothing his step stays 0.03 to 0.07 (0.32 with no warm-up) and a third of the tested weight already takes |
| 1 | The things he foretells (not paid): where the unseen enemy is, where he next appears, how the next fight ends, when the big items return | `--aux 0.1` | as built; its share of his step could not be told from chance |
| 1 | The attention part opened to the new tokens over the first hour | `--gate-open 60 --gate-from -6` | as built |
| 1 | The two-minute value estimate at full from the start (it was ramped in during v0.2) | `--long-gamma 0.9998 --long-ramp 0` | v0.2's end state |
| 1 | Places as targets: eight holding places a map from the pros, his to choose like an item | `TARGETS=1 TARGETS_FREE=2`; the start made by `tools/targets_init.py open --from-nothing 0.3` | opened only out of the readings he would have chosen "nothing" at (three in ten of them; every item's share exactly what it was), and a place is left for an item at any reading: level against the control in 160 games (pretest 7) |
| (out) | Legs that arrive and stand (`LEGS_STAND=1`, `move_v16b`) | not set: his legs stay `move_v15n` | the network passes the ten-map test but its pupil is slower (pretest 2): recommended out; the owner's decision 7 |
| 2 | The draw of his lives | `STYLE_MIX=rockets:0.40,lightning:0.15,rail:0.10` (general 35%) | the owner's decision 3 |
| 2 | The second aim step | **section 5, pretest 8** | from the pros' flick curve and the regulars' accuracy |
| 2 | The pros' weapon in hand with nobody in view | `HAND_TEACH=1`, `--hand-teach 0.1 --hand-teach-trunk 0.05 --hand-teach-warm 60` | a mild first step and no flicker, but a small lever (pretest 11) |
| 2 | A hit from above worth more, one from below less | `HIGH_PAY=0.25` (at 128 units of height, in proportion below that) | about 3% of his pay moves by height as he plays today (pretest 9) |

Unchanged from v0.2: the ten maps, 10,080 players (30 simulator processes of 168 matches), the rounds, the pay and the
prices, the scripted opponents, the first aim step (level 1.5, delays 100 / 200 ms) through leg 1.

**Held** (the reasons in the proposal): whole ten-minute games and the pay by the game (they want games that begin in
their middle); several ways; legs that run and look (not learnt in two trainings); the enemy as a target.

## 3. The control, the league, the checks

- **The control** is v0.2's end (`policy_control.pt`: it answers as `policy_end_v0_2.pt` in 15,360 of 15,360 choices).
  It is also a standing opponent in the league, v0.1 the other (`--anchor-p 0.25`); beside them his last eight selves.
- **From the newest save whenever the check loop is free** (a save every ten updates, about 65 minutes; a check about
  every hour and a half): 16 games a map against the control on the ten maps, the seats swapped in every second
  process, read by kind of life; his speed profile; at the start, the change of legs and the end also the stand-in on
  the two held-out maps and three trained ones.
- **The change of legs**: when leg 1's time is up, if its two last checks are not under 45% against the control and
  his hits in view are within two points of the start. Else leg 1 runs on to 07:00. Leg 2 is a restart of the trainer
  from leg 1's last save with leg 2's settings; its warm-ups count from its own start.
- **Reports**: a line at each check through the night, a short report at the change of legs, the summary at 07:00 with
  the scorecard beside the pros and the regulars.
- **It stops by itself** on a stall (no update for ten minutes) that a restart from the last save does not cure, or
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
  on the card (1,080 pieces of 384 frames, fed by one processor thread) and 40% the simulators. The efficiency cores
  would add about 15% and would carry the checks. A night of 14 hours is about 500 million steps (v0.2: 564 million in 10.8 hours).
- **The card**: 13.2 of 16 GB with an update cut in 360 pieces.
- The owner's, not tonight's: the board's BIOS update (the processor runs its pre-launch microcode), a larger page file.

## 5. Pretests

| # | Pretest | Result |
|---|---|---|
| 1 | Legs trained to look and stand together | standing learnt (arrives 91%), looking not (17.8% against 16.6%), plain speed down 3%: stopped |
| 2 | Legs trained to stand only (`move_v16b`, 40 minutes), then the ten-map test of today's legs | passes (items a minute +2.4% over `move_v15n`, no map more than 5% under; Campgrounds on the line); Blood Run's upper ledge held 91% of the time against 76%, the lower one no better. But its pupil is slower: 2 to 6% on most maps, 17% on Aerowalk, and told to stand it brakes all the way to the place (at 400 or more 22% of the way against 35%). Recommended out |
| 3 | v0.2's end checks | [REPORT_v0.2.md](REPORT_v0.2.md) |
| 4 | The merge: with everything off, bit for bit | 16 of 16 fixed runs |
| 5 | Size and speed on the card | section 4 |
| 6 | The legs' lesson with its warm-up | his step 0.03, 0.07, 0.04, 0.04 over four updates while the weight rose to a third; his own turn's agreement with his legs' 7, 11, 24, 29%; sideways key 48 to 57%; in withheld stretches his turn 6 to 17%; on target 28.0 to 28.3% |
| 7 | Level check of the opened place choice against the control | evenly at 5% of all his readings: 44.7% in 128 games (42-7-79), a fail: a place holds like an item, 5% of readings was 19% of his time and came out of the armors' time. Out of his "nothing" only: 48.0% in 128. The same and left for an item at any reading (`TARGETS_FREE=2`): **50.9% in 160 games (86-9-65)**, the mega 43.6% of its spawns against the control's 44.6% |
| 8 | The second aim step | **pending** |
| 9 | The size of the height pay | v0.2's end against itself, the same games at four sizes: 14% of his damage is dealt from above, 11% from below; 0.25 moves 3.1% of his pay between the two players (0.1: 1.25%, would drown in the entropy bonus; 0.5: 6.25%, a rule and not a nudge) |
| 10 | The weighted draw of lives at the start | **pending** |
| 11 | The weapon-in-hand pull and leg 2's first step on the card | dry run of 13:50, two updates: 13.1 GB; his step 0.043 then 0.026, of it his weapon key 0.009 then 0.0003 at the full weight; 6.3 then 1.5 weapon changes a minute; lives drawn 36 / 41 / 9 / 14%. Where the lesson speaks his hand is already the pros' while travelling (rockets 62% against 60%) and differs only while holding a place (30% against 73%; 2% of his time) |
| 12 | The people scale with v0.1's first day | v0.1: 32% of 185 frags against four people, rating 1269 (v14's end 1251); in real games 14% of 119 |

## 6. What could go wrong

- **A lesson costs his aim** (it has before, and it did not come back). The legs' lesson reaches a quarter into the
  shared layers and rises over an hour; hits in view are in every line; leg 2 does not start on a fall of two points.
- **A new choice costs him at the start** (twice before). Places go in only on a level check of 128 games or more.
- **Leg 2 dips by design**: more of his lives are rocket lives, where he is the weaker player (0.82 frags a death).
  Its checks are read by kind of life; the measure is the rockets life itself.
- **The aim step changes what wins.** Both seats of every check play at the run's level.
- **A process dies** (the processor's efficiency cores). The trainer is kept off them; a stall is seen within ten
  minutes and the run restarts from its last save.
- **The PC's memory limit.** The free commit is read beside the run; one numpy thread a process.
- **The plugins know none of the new parts**: no real game with a v0.2.1 network until they do (B-233).

## 7. The public server

v0.1 stays (the owner: "Do not promote the live server yet"). Nothing is pushed by this run. The plugin batch of
2026-10-12 09:59 is live (results and map vote, 5 s weapons, F3 in 1v1, the owner's mark, QLStats lookup).

## 8. The owner's decisions

(filled from his decision document when he has answered; the run does not start before)

## 9. Changes during the run

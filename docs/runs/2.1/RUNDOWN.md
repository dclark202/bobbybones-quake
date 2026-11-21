# 2.1 (the strategy layer; called 2.0c until 11-10 night) as it stands (for the owner's review, 2026-11-11)

Nothing trains, nothing is committed, no server has any of it. The full design is [DESIGN.md](DESIGN.md) and
[../../design/STRATEGY_2.md](../../design/STRATEGY_2.md); the aim is [../../design/AIM3.md](../../design/AIM3.md).
Starts from **1.8's end** (owner, 11-11: 2.0c dropped; AIM3 kept, the damage pay not lowered; the 1.n series redone from b1.2d's end under AIM3: [../1.8/1.8a/CARD.md](../1.8/1.8a/CARD.md)). Where this page says "the damage pay 0.002" or "from 2.0c", that is superseded.

## 1. In from the start

| | What | State |
|---|---|---|
| **AIM3** | the sight error against his eye, not his crosshair (a held angle and a flick's start no longer get the largest error); the base error by how big the enemy looks (far targets); default = the average pro's parameters, better = p90, max = off | **built** as switches, off = bit-identical; parameters measured on 5,265 pro player-games; table in AIM3.md section 4; not yet in `tools/aim2_levels.py`, no training under it |
| **Damage pay 0.002, zero-sum** (from 0.0055 dealt, 0.8 x taken) | the burst weapons' damage and the lightning's are paid alike and a trade of equal damage pays nothing | a setting of the run's command (`DMG_REWARD`, `DMG_TAKEN_W=1`); nothing to build; its effect on the first updates is unmeasured |

## 2. The design in six lines

Every 0.2 s: the **brain** says where the enemy is (his senses only) -> the **map sense** says what his place is worth with the enemy
there, by weapon -> the **appraisals** forecast what each of 20 to 30 candidate instructions would bring -> the **head** reads all
of it and its own last tick and picks an instruction (a verb, a place, a point, a weapon) -> the **keep choice** holds or drops it
-> the **hands** carry it out. The hands are paid by the game; the head by his own play (the frozen moments and a share of the
game's pay). The verbs are a toolkit he may use, never a quota.

## 3. Built

| Piece | What it is | Where |
|---|---|---|
| The design and the explicit questions (S1-S9, A1-A7), how each is trained, the gates | written | DESIGN.md, STRATEGY_2.md |
| Map sense seeds | what a place brings in the next 5 s with the enemy near, by weapon, fitted on the pros, tested on held-out games and on his | `tools/run/seed_calib2.py`, `data/sim_runs/space/seed_v2.joblib`, pictures in `docs/design/space/` |
| The pros' damage dealt | the hit counter in the demo sets | `sim/demo_dataset.py --lite2` |
| Freeze-and-branch | a moment copied into many matches with both networks' memories, a first choice forced, the outcomes recorded | `tools/run/branch_hook.py`, `branch_test.py`; two inert hooks in `sim/duel_env.py` (`force_intent`) and `tools/duel_eval.py` (`BRANCH_HOOK`) |
| The held-angle probe | a seat made to stand and hold with a weapon at the pros' holding places, pre-aimed, his own aim or a script | `tools/run/hold_hook.py`, `hold_test.py` |
| The aim measures | the pros' and his games in the same columns; the aim error and how it grows | `sim/demo_dataset.py --lite3` (4,222 demos), `tools/run/aim_rec.py`, `aim_rec_hook.py`, `pro_aim.py`, `pro_knobs.py` |
| AIM3 | section 1 | `sim/duel_env.py`, `sim/duel_env_ffa.py` (regenerated) |
| Rule 12 | the demos measure things, never set his behaviour | CLAUDE.md |

## 4. Not built (all of the network and the trainer)

| Piece | Depends on |
|---|---|
| The instruction in the simulator: the seven verbs, their places, points and weapons; what "done" and "failed" mean for each | the review of the verbs' definitions |
| The map sense as a part of the network (learned, started from the seeds) | decision 4 below (the pull) |
| The appraisals network (A1-A7 for any candidate) | decisions 2 and 3 below |
| The head's new inputs, its own last tick fed back, its lesson | the appraisals |
| Frozen-moment rounds in the trainer (a share of the rollout that restores a moment and plays branches) | the appraisals |
| The drills: each verb from a starting state where it can pay | the instruction; AIM3 trained in |
| The yellows in "who takes it next"; the items' clocks in the demo sets | - |
| The run's files (command, ramp, start script, settings check, identity, ten updates and a check) | everything above |
| `tools/aim2_levels.py` with AIM3's columns; the plugins' check with AIM3 on | the table's approval |

## 5. Where it departs from what was specced, and why

| Specced (owner) | As built or as now proposed | Why |
|---|---|---|
| The head is paid for "the statistically correct choice" by playing out the top 5 and a handful of others from a frozen state | many moments with a few branches each teach the appraisals; the head is taught toward the appraisals' order (accepted 11-10) | one moment's branches cannot rank its options: the first choice is 9 to 12% of a branch's outcome (120 moments, 54 branches each) |
| A branch holds its option | the first choice is forced for one second, then he plays on (accepted 11-10) | a rigid 4 s hold loses whatever the option, his own included |
| The map as "a rule ... with a slight pull to the average pro" | starts from the pros' fit; the pull is a live number that may be 0 (owner 11-10: open to "just using it as a starting point") | the seeds forecast the exchange weakly on the pros (R2 0.04) and not at all on his games |
| A pull of the head's choice to the pros | **removed** (owner 11-10, rule 12) | every pull to the pros collapsed him |
| The hold drills built next | **held back** | the probe: a standing hold with the rail is 6 points behind free play over 8 s with his present hands, under AIM2 and AIM3 alike; he first has to train under AIM3 |
| The probe's first result ("first shot 650 ms") | **withdrawn**: that was my script turning slowly. Measured: the simulator lets him notice at 200 ms; the pros' held shot leaves at 275 ms (fast end 200) | owner: "650ms doesn't look right" |

## 6. Findings that change the design

1. **The judge cannot see items.** The win-chance judge reads the score, the time, both stacks and the three big weapons, nothing
   about an item being up or who is nearer. A6 ("how does my chance of winning change") scored by it makes "the mega is up but I do
   this first" read as a loss in every 8-second branch. To be changed: decision 1.
2. **A hold does not pay yet, and that is about his hands, not his limits.** The limits allow the shot (notice at 200 ms). With
   his own aim, standing and pre-aimed, his first rail shot leaves at 375 to 425 ms and hits 43 to 47%.
3. **What still tilts him to the lightning after 1.7a** (the audit; every direct cost on firing, clicking, switching, turning
   sharply, firing blind and standing still is already 0):
   - damage paid as it lands at 0.0055 with damage taken at 0.8 (2.0c: 0.002, zero-sum);
   - the sight error that was largest on a still crosshair and a flick's start (AIM3);
   - the fixed-angle base error, too large for a far target (AIM3's size law);
   - the reload's random extra delay on slow weapons only (unmeasured: AIM3.md section 5);
   - nothing tells him where to fire with nobody in view (the pros: two thirds of their rockets; he: 9%): the "spam" instruction;
   - his tracking of a fast or turning enemy is tighter than the pros' aim error (1.01 against 1.81 half bodies at 50 to 100
     degrees a second), so the lightning is worth more to him than to a person. Not changed (owner: tracking stays).
4. **His rockets point behind a crossing enemy** (-0.17 of the full lead; the pros 0.02): he does not make up his own delay. The
   rocket lead inputs are the place to look (AIM3.md section 5); not yet measured.
5. **Rule 12 reaches one part of the design**: the appraisals' third data source was the pros' games with their instruction
   inferred by a rule of mine (a player's choice, by my inference). Decision 2.

## 7. Decisions for the review

| # | The decision | My recommendation |
|---|---|---|
| 1 | What scores a branch's end, since the judge cannot see items: (a) his own learned value, which reads the items' clocks; (b) the judge with an item term added (who holds the next mega and red: S7); (c) longer branches | (a) for the head's lesson, with the judge kept for the pay: it is the only one that sees what he knows, and it costs nothing to build. Its risk: it is his own estimate, so a bias of his is taught back to him; the branches' real outcomes (A1 to A5) stay beside it |
| 2 | Do the appraisals learn from the pros' games at all | no: his own play and the frozen moments only (rule 12). The pros' games stay as starting states for drills |
| 3 | The share of the game's pay on the head's choice beside the frozen moments | start at today's (the head is paid as in 1.7a) and let the frozen moments' lesson open beside it; nothing is taken away at the start |
| 4 | The map sense's pull to the pros' fit | start with it small and live; take it to 0 if his own games' corrections are stable (test 7) |
| 5 | AIM3's table (AIM3.md section 4): the size law (it makes his sight error larger than today closer than 400 units), better at p90, the eye's gain at 1 | as written; the one number to watch is his close lightning |
| 6 | His tracking of fast and turning enemies is tighter than a person's: leave it, or lower the eye's gain / lengthen its lag so tracking carries a human's error too | leave it for 2.0c (one new thing); raise it again after he has trained under AIM3 |
| 7 | Is AIM3 with the damage change one run of its own before the head's rebuild, or the first gate of 2.0c | a run of its own, short: it is the one part that is built, it changes what his hands can do, and the drills and the frozen moments both need hands that have trained under it. Rule "one new thing per round" says the same |
| 8 | "p90" as the spread between player-games with the chance of a game's own shot count taken out (rail 61%), or the raw 90th percentile of games (70%) | the first; it is the one that says what a p90 player is, not what a lucky game is |

## 8. The order I would build in (no dates: when each is built and tested, you decide)

1. AIM3's table into the levels tool and the plugins' check; the run card for "AIM3 + damage 0.002" from 1.7a's update 90, with the
   aim error tables and the held-angle probe as its measures (not hit rates).
2. The instruction in the simulator (the verbs), with a scripted seat proving each can be carried out and what "done" means.
3. The map sense and the appraisals as parts of the network, learning with nothing reading them; the frozen-moment rounds.
4. The drills, verb by verb, on hands that have trained under AIM3; the probe repeated.
5. The head's new inputs and its lesson; then its instructions to the hands in games, opened from none.

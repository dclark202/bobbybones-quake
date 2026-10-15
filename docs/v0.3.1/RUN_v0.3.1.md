# v0.3.1 on one page (the training manifest)

*Written 2026-10-15 13:20 on the owner's word: "rocket jumping, improved rocket aim, merging movement network ... I would
like to train tonight". A fine-tuning of his mechanics after v0.3 ("it's a fine tuning of his weapon usage. An experiment
post major model version"), not a full new model. The plans in full: [PROPOSAL_v0.3.1.md](PROPOSAL_v0.3.1.md).
Status: **not started; the owner's go after his play test.** Folder: `duel_gru_v0_3_1`.*

## What can be ready tonight, and what cannot

| Part | Tonight? | Why |
|---|---|---|
| **Rocket drills** | **yes** | the trainer's one-weapon round exists (`--drill-p`, `--drill-weapons rl`): a setting, no new code |
| **Rocket jump runs** | **only if two checks pass by 22:00** | the simulator's rocket jump must first match the game's (a measuring plugin, built this afternoon, run after the play test), and the runs are new code (built this afternoon in a staging copy, applied after 18:00) |
| **His legs inside the network** | **no: the next start** | the network, the trainer's loss, the checks' tools, the export and both plugins all change, and it must be proven to play exactly as before: one to two days |

## What he trains on (tonight)

Whole games, mid-game starts and movement practice as in v0.3, and beside them:

| Session | Share | What it is |
|---|---|---|
| Rocket drills | 10% | short rounds on the ten maps, both players with the rocket launcher only (15 rockets), against his league: aim, splash, the enemy in the air |
| Rocket jump runs (if ready) | 2% | from a pro's take-off spot to its landing, with the launcher and about 220 health and armor; a ladder of starts (in the air looking down; on the floor looking down; a normal stance); a nudge on the look-down and the shot's moment toward the pros' that fades |

Unchanged from v0.3: the human limits, sight and sound only, the pay (no pay for a near miss), the ten maps, no powerups,
overtime, no styles.

## What it starts from, and the control

v0.3's best save by its evaluation (the owner picks it at 19:00). **The control is that same save** (the last best
network): it stays in his league (a quarter of his games) and every check plays it. v0.2 is checked once at the end.

## How it is judged and stopped

- Every tenth update: 160 ten-minute whole games against the control on ten maps (level 50%, one check moves about ±3).
- **His rockets** at every check, in whole games only: rockets a minute, damage a rocket, direct hits, the share of
  frags, time in hand. The drills are kept only if these rise and the check holds.
- **Rocket jumps** (if in): arrivals per link in the runs; rocket jumps a game in whole games beside the pros' table.
- **Stops by itself**: under 47% at update 10, two checks under 45%, or three falling. The weapon watch as in v0.3.
- A line an hour at night, a mid-run report at 07:00. Promoted only on the owner's word and only if it beats the control.

## Before the start (tonight)

1. 18:00 v0.3 ends; its evaluation; 19:00 to 20:00 the owner's play test.
2. 20:00 the rocket jump check: the game's and the simulator's jumps side by side (pass: rise and distance within 5%,
   damage exact). A difference that cannot be fixed by 22:00 leaves the runs out.
3. The rocket jump runs applied and proven to change nothing with them off; two updates of a dry run read for the
   drills' and the runs' real shares of his time.
4. The owner's go. Start about 22:00 to 22:30; to noon Friday, or longer on his word.

## The legs inside the network (the next start)

Today the movement network is apart: when his switch is on, it computes his keys and turn in the simulator, and the
trainer gives his own movement outputs no credit on those frames, so nothing ever improves it from games. Unified: it
becomes a branch of his network on the card, its 61 inputs passed with his others; on a frame his switch is on, his
movement outputs are the branch's (the same four choices it makes today: forward, strafe, jump, turn). Then the
ordinary training credits the branch for what wins games, and it is one network. Stages: (a) the branch frozen, the
network proven to play exactly as today; (b) the branch learns, at a quarter of the rate; (c) links that start at zero
from his memory and the head's plan into the branch, so his movement can know the enemy. Each stage ten updates and a
check against the control.

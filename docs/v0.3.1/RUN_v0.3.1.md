# v0.3.1 on one page (the training manifest)

*Written 2026-10-15 13:20 on the owner's word: "rocket jumping, improved rocket aim, merging movement network ... I would
like to train tonight". A fine-tuning of his mechanics after v0.3 ("it's a fine tuning of his weapon usage. An experiment
post major model version"), not a full new model. The plans in full: [PROPOSAL_v0.3.1.md](PROPOSAL_v0.3.1.md); the manifest with what is still to build: [MANIFEST_v0.3.1.md](MANIFEST_v0.3.1.md).
Status: **build everything first, then train; no start time set** (the owner, 2026-10-15 17:25). Earlier: **a draft, to be reviewed with the owner after v0.3 ends** (13:30: "merging the movement network needs to be part of it. Let's just review this once the training v0.3 is done. We'll decide how much/what to build for v0.3.1"); nothing is built before. Folder: `duel_gru_v0_3_1`.*

## Build everything first, then train (the owner, 2026-10-15)

"for v0.3.1 we'll build everything first, then resume training. No time set for starting yet." One start, from v0.3's
18:00 stop point, once every part is built and proven alone (ten updates and a check against the control). What is
built and what is not: [MANIFEST_v0.3.1.md](MANIFEST_v0.3.1.md), section 6. The order: the faster learning step
(B-237); his legs inside the network (B-253); the rocket jump check against the game, then the rocket jump runs if it
passes (B-252); the rail's surprise delay from the rail test and the pros' demos (B-255); the rocket drills checked.

## What he trains on

Whole games, mid-game starts and movement practice as in v0.3, and beside them:

| Session | Share | What it is |
|---|---|---|
| Rocket drills | 10% | short rounds on the ten maps, both players with the rocket launcher only (15 rockets), against his league: aim, splash, the enemy in the air |
| Rocket jump runs (if the check against the game passes) | 2% | from a pro's take-off spot to its landing, with the launcher and about 220 health and armor; a ladder of starts (in the air looking down; on the floor looking down; a normal stance); a nudge on the look-down and the shot's moment toward the pros' that fades |

**His aim at level 3** (the owner, 2026-10-15: "Set it to 3 going forward"; v0.2 and v0.3 trained at 1.5, which cost the rail most: B-255). **The surprise delay with the rail** (the owner, 2026-10-15) set from the pros' demos: how soon after an enemy appears they fire the rail, by how far off the crosshair he was; his own curve is matched to theirs at level 3 before the start. The plan (the owner, 2026-10-15): build v0.3.1 tonight, then train on for a while to see what happens.

Unchanged from v0.3: sight and sound only, sight and sound only, the pay (no pay for a near miss), the ten maps, no powerups,
overtime, no styles.

## What it starts from, and the control

v0.3's last save, where it stops at 18:00 (the owner: "We'll pick up v0.3.1 from the 6pm stop point"). **The control is v0.3's best save by its evaluation tonight** (the last best
network): it stays in his league (a quarter of his games) and every check plays it. v0.2 is checked once at the end.

## How it is judged and stopped

- Every tenth update: 160 ten-minute whole games against the control on ten maps (level 50%, one check moves about ±3).
- **His rockets** at every check, in whole games only: rockets a minute, damage a rocket, direct hits, the share of
  frags, time in hand. The drills are kept only if these rise and the check holds.
- **Rocket jumps** (if in): arrivals per link in the runs; rocket jumps a game in whole games beside the pros' table.
- **Stops by itself**: under 47% at update 10, two checks under 45%, or three falling. The weapon watch as in v0.3.
- A line an hour at night, a mid-run report at 07:00. Promoted only on the owner's word and only if it beats the control.

## Before the start (no time set)

1. 18:00 v0.3 ends; its evaluation; the owner's play test.
2. Every part built in its order and proven alone.
3. The `.cmd` written; two updates of a dry run read for the sessions' shares.
4. The owner's go and the start time.

## The legs inside the network

Today the movement network is apart: when his switch is on, it computes his keys and turn in the simulator, and the
trainer gives his own movement outputs no credit on those frames, so nothing ever improves it from games. Unified: it
becomes a branch of his network on the card, its 61 inputs passed with his others; on a frame his switch is on, his
movement outputs are the branch's (the same four choices it makes today: forward, strafe, jump, turn). Then the
ordinary training credits the branch for what wins games, and it is one network. Stages: (a) the branch frozen, the
network proven to play exactly as today; (b) the branch learns, at a quarter of the rate; (c) links that start at zero
from his memory and the head's plan into the branch, so his movement can know the enemy. Each stage ten updates and a
check against the control.

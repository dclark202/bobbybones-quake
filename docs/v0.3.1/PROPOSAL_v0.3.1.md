# v0.3.1: the mechanical side

*Written 2026-10-15 on the owner's word: "before v0.4 starts (perhaps concurrently with pretraining the strategy layer) we
should work on rocket jumping and merging the two movement networks into one ... along with better rocket/projectile
aim". v0.3.x is the hands: aim, movement, the weapons, with a little strategy. v0.4 bolts the strategy layer (the head)
onto its end ([../v0.4/CANDIDATE_v0.4.md](../v0.4/CANDIDATE_v0.4.md)). Not built; it starts from the network the owner
picks after v0.3's evaluation and play test.*

## The priorities

| # | What | Why | Done when |
|---|---|---|---|
| 0 | **The learning step rebuilt** (B-237): his memory by the library's GRU, not frame by frame in Python | every run after it about twice as fast; moved here from v0.4 because all of v0.3.1 gains from it | the same loss and gradients as today on a saved update, to rounding |
| 1 | **His legs inside the network** (B-253): the movement network as a branch of the main network, then learning from games, then seeing the enemy and his memory | two networks cannot learn from each other; his legs know nothing of the enemy and never learn from games | each step level or better against the control |
| 2 | **Rocket jumps** (B-252): the game's rocket jump measured and the simulator checked against it; the pros' and the free-for-all players' rocket jumps found in the demos; rocket jump runs with a ladder of starts and a fading nudge on the look-down and the timing; the links in each map's walking graph | he never rocket jumps; some routes, items and escapes need it | he reaches the landings in the runs, then uses them in games where they pay |
| 3 | **Better rocket and projectile aim** (B-254) | rockets are the owner's second priority; his rockets hit less and he fires far fewer than the pros | his damage per rocket and plasma shot moves toward the pros' |

## Rocket and projectile aim (item 3), the first steps

- **Measure first**, his and the pros' and the free-for-all players' (B-251): rockets a minute, direct hits, splash damage
  per rocket, shots at the enemy's feet or the floor beside him, plasma hits, by distance and by whether the enemy is in
  the air.
- **What he is told.** He has six inputs for a rocket's and a plasma ball's lead (since v14). Check they give what a
  player aims at: the floor under the enemy's predicted place for splash, the time the rocket takes, an enemy in the air.
- **His limits.** The reaction, flick and hand limits from the free-for-all games (B-251) apply to projectile aim too.
- **Not proposed without the owner**: rocket drills (the rule of 2026-10-13 is whole games and mid-game starts only) and
  any pay for a near miss (a reward for a single behaviour).

## Beside it: the head's pre-training

The strategy layer of v0.4 learns from the pros' demos offline while v0.3.1 trains (the candidate, "The pros' demos and
the head"): the demo sets rebuilt with the mended converter first (B-218, B-219). It shares the PC's one graphics card
with the trainer: it runs on the processor, in the trainer's gaps, or on rented time.

## The order

0 first (a day). 1 and the measurements of 2 and 3 next; 2's runs after 1 (they train the legs branch). Each part
alone: ten updates and a check against the control before it joins the run, as every new part since 2026-10-13.

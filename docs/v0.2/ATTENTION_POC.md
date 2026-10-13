# Attention over the scene: a proof of concept (scope, not started)

Owner's question (2026-10-07): would attention make sense for this model, in place of the "memory"; and: scope a local
experiment, the worry being whether several bots can run it at once on the hardware we have, if it works at all.

## What is proposed, and what is not

- **Not** attention over time in place of the GRU. The GRU carries its state at a fixed cost per frame; attention would
  need about 1,400 stored frames to span one mega cycle at 40 frames a second. The long things he must remember (item
  timers, the clock, where the enemy was last seen) are inputs already.
- **Yes** to attention over the things in the scene, feeding the GRU. Today every enemy, item, projectile, sound and
  spawn point has a fixed slot in a flat vector of 483 numbers ("the other two enemies", "the four nearest spawn
  points", "the ways to five big items"). As tokens, any number of them in any order can be read, on any map and in any
  group size. This is the shape of OpenAI Five and AlphaStar: attention over units, a recurrent core for memory.
- It does **not** address the open problem of v9 (he chooses the right item and does not walk to it: an incentive
  problem, not one of perception). It is groundwork for many maps and for groups of four to six.

## The model

    self features (about 120: own state, walls, clock, fingers)  ----------------------------.
    tokens, each = [kind one-hot, relative position (3), relative velocity (3), a few facts]   \
      enemies (up to 5), items (the 16 nearest + the big ones), projectiles (8), sounds (4),    >-- concat -> GRU 512 -> the same heads
      spawn points (4), route goals (5), the map reader's cell for self and for each enemy     /
    token MLP (-> 64) -> one cross-attention layer, the self vector as the only query, 4 heads -'

One query (himself) reading about 40 tokens costs in proportion to the number of tokens, not its square. A second variant
for the A/B: one self-attention layer among the tokens first (they can then relate to each other: "the rocket that is
flying at the enemy who stands on the mega").

## Step 0: can four bots run it at once? (half a day, no training, no GPU)

Answer the hardware question before building anything. A numpy forward pass with random weights, timed for 1 to 4 bots:
- on the PC and on the rented server (2 slow cores, about 2.5 times slower), the same way the current network was timed
  (2026-10-06: inputs for six seats 1.55 ms, the network for four Bobbys 0.57 ms on the PC; budget 15 ms of the 25 ms frame);
- estimate beforehand: about 1 million multiply-adds a bot a frame for the attention part against about 1.5 million for
  the GRU with 483 inputs, so roughly +70%: near 1 ms for four bots on the PC, 2.5 ms on the server.
- **Pass**: four bots under 4 ms on the server for the cross-attention variant. If the self-attention variant does not
  pass, it is dropped here.

**Measured 2026-10-07 09:00** (`tools/attention_timing.py`, random weights, numpy, one thread; milliseconds a frame for all bots together, median and 99th percentile in brackets). The rented server, 2 cores, nobody playing:

| Bots | Today's network | Cross-attention | With a self-attention layer |
|---|---|---|---|
| 1 | 0.15 (0.40) | 1.18 (3.45) | 1.51 (3.89) |
| 2 | 1.02 (3.32) | 2.22 (6.50) | 2.64 (6.90) |
| 4 | 0.98 (3.34) | 2.29 (6.41) | 3.12 (7.45) |
| 6 | 1.20 (3.51) | 2.64 (6.84) | 3.78 (9.76) |

The PC, with the training run on every core (so the tails are the training's, not the network's): four bots 0.51 / 1.77 / 2.55 ms, six bots 0.78 / 2.07 / 3.45 ms.

- **Both variants pass** (four bots under 4 ms on the server at the median): 2.3 ms and 3.1 ms against today's 1.0 ms. With the inputs (about 4 ms for six seats on the server) a frame stays inside the 15 ms budget, the 99th percentile included.
- The cost is about **1.3 ms more whatever the number of bots**: it is the overhead of many small array operations in numpy, not arithmetic (one bot costs 1.2 ms where the estimate from multiply-adds said 0.3). So it can be cut if needed (one head, fewer reshapes, a fused token layer), and more bots are nearly free.
- Not measured: building the tokens. They are made of numbers the flat inputs compute already, so the input time should hardly move.

## Step 1: the tokens (one day)

`observe_entities()` in `sim/duel_env.py` beside `observe()`: the self vector, a token array `[players, K, F]`, a mask and
the kinds. Everything in it is computed for the flat inputs already; the human limits stay where they are (what is not
seen or heard is not a token). The flat inputs stay too: both arms run on one simulator. The trainer stores the tokens in
the rollout (about 640 numbers a step against 483) and the play plugin builds them from the same function.

## Step 2: does it work at all? (one night)

Training both arms from nothing would take days to say anything (the current weights carry some 55 hours). Instead:
1. **Distill**: the attention model learns to copy the current flat network on that network's own games (same heads,
   cross-entropy to its action probabilities, value regression). This shows in a few hours whether the tokens carry what
   the flat inputs do. *Pass*: agreement on the keys, the fire button and the weapon above 95%, turn within one bin 90%.
2. **Continue with self-play** from the distilled weights for the rest of the night, the flat network continuing beside
   it as the control, each on half the workers.
3. **Read**: at equal samples, frags against the same frozen opponent (the v8 end checkpoint) and the hit rates: the
   attention arm at least level. Then the two probes that are the reason for doing this at all:
   - **group size**: trained in groups of 2 to 4, played in groups of 6;
   - **a map never trained on**: played on one of the held-out maps of the map reader.
   *Pass*: level in the fights and clearly ahead in at least one probe.

## Step 3: on the real server (half a day, only if step 2 passes)

Export to numpy, the plugin builds the tokens, three Bobbys on the private server, frame times logged. *Pass*: no frame
over the budget in a ten-minute game.

## Cost, risks, timing

- About three working days and two nights of the PC; nothing touches the running experiment before step 2.
- The weights cannot be carried over by input name as from v8 to v9: distillation is the bridge, and it copies the flat
  network's habits, good and bad.
- A token set is another place for the simulator and the real game to disagree: the plugin must build tokens with the
  simulator's own function, as it does for the flat inputs.
- When: after Goal 1 on arena1 is in sight, or as a side experiment on idle nights. Not during v9.

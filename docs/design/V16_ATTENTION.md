# v16: attention (the proposed model, as it stands after 2026-10-11)

A proposal for the owner's review. Nothing of it is built. Second version: rewritten on the evening of 2026-10-11 after
the day's measurements (the pros' yardsticks and Bobby beside them, the event record tried on the demos, the fight
target tried in the simulator, the model timed on the rented server). The first pass of the run:
[../runs/MANIFEST_v16.md](../runs/MANIFEST_v16.md). The event record's test: [v16_event_record.md](v16_event_record.md).
The earlier scope note: [ATTENTION_POC.md](ATTENTION_POC.md).

**What it is judged by** (the owner, 2026-10-11): "Game awareness primarily. Also how much his movement begins to blend
together the two styles fighting/moving we have now." What he wants to see: "Rocket/plasma/grenade spam used
appropriately"; "Playing aggressive/defensive depending on score/being in control/etc. (in control = knows item times
and has stack to contest them when they become available)"; "Setting traps/using weapon combos for frags (rocket to
disrupt movement, then LG on the midair enemy)". After playing v15c: "their main failure point is that their routes are
predictable"; "he has no counterplay"; "he doesn't know how to push an advantage"; "enemy position + uncertainty";
"a 'strength of position' token ... which then influences what weapon they are likely to chose" ("Absolutely it
should" hold the weapon that suits the spot). Whole ten-minute games with pay for the result: "Yes". Three bots a
server would do; four fit.

## 1. What the day's measurements say he lacks

Bobby (v15c's end, 1,440 minutes against himself) beside the pros (4,085 demos), `tools/bobby_yardsticks.py` and
`tools/pro_yardsticks.py`:

| | The pros | Bobby |
|---|---|---|
| Rockets a minute; the share fired with no enemy in view | 10.8; 50% | 2.1; 0.3% |
| Grenades a minute | 2.2 | 0.03 |
| A rocket, then rail or lightning within 1.5 s, per ten minutes | 3.6 | 0.05 |
| In hand with the enemy in view: lightning, rockets | 29%, 40% | 42%, 19% |
| The distance he fights at (median) | 508 | 327 |
| Closing on a sighting when weak (under 60) / stacked | -12 / +12 | +33 / +34 |
| Stacked: closing just after a frag / otherwise | +37 / +5 | +34 / +32 |
| Higher than the enemy in view; time in the lowest third of the map | 26%; 28% | 17.5%; 40% |
| Trips between two items on the commonest way; on a way of their own | 40%; 36% | 52%; 19% |
| Back at the mega within 2 s of its return | 47% | 49% |
| Time in his eight most-used places (one game) | 24.5% | 25.0% |

He already has what a memory gives (item timing, where his time goes). He lacks what comes from knowing the enemy's
state and the map's places: he behaves the same whatever the enemy has, never fires at a place, fights low and close,
and takes one way. Two tests of the day say the same:

- **The event record on the demos** ([v16_event_record.md](v16_event_record.md)): a record of events foretells the next
  item better (73% against 67% with no memory) and where a just-lost enemy is (125 units off against 315 in the first
  second), nothing about the fight, and no more than a recurrent memory overall.
- **The enemy as a target** (`FIGHT_TARGET`, built and tried): a way to the fight did not help. By a broad rule it cost
  him his items (health and armor 154 down to 126) and his duels (39% against himself without it); by a narrow rule
  (strong and armed, the enemy spawned under 10 s ago and was seen within 4 s) it was level. What is missing is knowing
  when the enemy is weak.

So this version differs from the first in three things: the separate list of events is out of the first build (its two
useful parts move into the enemy token and the item tokens); the first stage already carries the new information (the
enemy as believed, places, his position); and the outputs for a place as a target and for a choice of way come in the
second stage, not the third.

## 2. The model

Attention is added beside what he has, not in place of it. Today's path stays whole, so on its first frame v16 is the
network it starts from, weight for weight.

```
                          today's path (kept, carried over)
 577 flat inputs ----------> Linear 256, tanh -> Linear 256, tanh -------------+
 + about 200 new numbers                                                      (+)---> GRU 512 ---> 12 outputs
                                                                               |       (kept)      (kept; more in
 TOKENS (cut out of the same input vector inside the network)                  |                    stage B)
  each: Linear(its numbers -> 96) + a learned vector for its kind              |
  block 1: self-attention among all tokens (4 heads of 24, feed-forward 192)   |
  block 2: the same, computed for the two rows that are read ------------------+
           (himself, the summary) -> Linear(192 -> 256), starts at ZERO
```

| Part | Size | Starts as |
|---|---|---|
| One layer a kind of token, `Linear(F_kind, 96)`, and a kind vector | about 25,000 weights | random, small |
| Attention block, twice: 4 heads, feed-forward 96 -> 192 -> 96, layer norm before each part | about 75,000 each | random |
| The adapter into the GRU's input, `Linear(192, 256)` | 49,000 | **zero**: the network is the old one until training moves it |
| Today's encoder, GRU, outputs | 1.44 M | carried over |
| The belief output and the second value output (stage B) | under 30,000 | zero |
| His legs as a part of the network (stage C) | 86,000 | carried over from `move_v15n` |

About 1.7 M weights. The second block is computed only for the two rows that are read: that is exact (the last block's
rows do not depend on each other) and saves most of its cost. An adapter that starts at zero, not a distillation: a
copy is loose (2026-10-10: a network that agreed with the movement network on nearly every frame could not strafe
jump), and a control he equals on the first day makes every later check readable.

### The tokens (54 in a duel)

A token is a view: its numbers are cut out of the flat input vector inside the network. Everything is under the same
limits as today: what he does not see or hear is not shown. The walls, floor and hazards around him stay in the flat
path. Bold: new information, about 200 numbers in all.

| Kind | How many | Numbers | What it holds |
|---|---|---|---|
| Himself | 1 | about 60 | health, armor, weapon in hand, weapons owned, ammunition, speed, his hands, his legs' switch |
| The game | 1 | about 16 | both frag counts and their difference, the round's clock, the item clocks, **the time left in the game**, **how loud he has been in the last seconds**, **his health and armor less what he believes the enemy has** |
| His position | 1 | about 12 | **new**: his height against where he believes the enemy is; how much of the ways around he overlooks from here and from how many he can be seen; his ways out; how long he has stood here; and from the pros' fights at this place (`sim/pro_places/<map>_cells.json`): **which weapon they hold here** and **how those fights went** |
| The enemy as seen | 1 (up to 5 in groups) | about 70 | only while in view: where, how fast, facing, weapon, what he fired, the damage he took |
| The enemy as believed | 1 | about 24 | always: **where he was last seen or heard and how long ago, how he was moving, how far he can have got since**; his strength as far as it can be known: **seconds since he spawned** (the game announces every frag), **the weapons seen on him this life, the damage dealt to him this life, the big items he may have taken since** |
| Projectile | 6 | 15 | where, how fast, its kind, a grenade's fuse, when and how close it passes |
| Item | 12 | about 18 | where, the way to it in seconds, up or not as he believes, when it returns as he believes, his target or not, **when he last took it himself** |
| Place | 8 | about 14 | **new**: the nearest of the map's places (`sim/pro_places/<map>.json`: where the pros' shots land when nobody is in view; exits, doorways, item spots): where, in view or not, **whether a rocket, a plasma ball or a grenade from here reaches it and the view that does it**, **whether the enemy can be there by now**, **whether he was heard there** |
| His way | 3 x 6 | about 6 | the next waypoints of up to three ways to his target (stage B: the choice among them), the jump ahead |
| Sound | 4 | about 10 | the last sounds heard: where from, what, how long ago |
| Summary | 1 | none | a learned token that gathers an overview |

No separate list of events in the first build. If a later stage wants one, the test says how: eight slots for frequent
events and eight for rare ones (sixteen of the last reach back only 19 seconds), no "fired" events, "hurt" once a
burst.

### Outputs

Stage A: the twelve he has. Stage B adds, all inside the fairness rules (he still moves the mouse and pulls the trigger):

- **A target**, read twice a second: an item, a place, where he believes the enemy is, or "hold here". It does two
  things. It says where his way leads (his legs take it as any way: the fight becomes reachable at speed). And it
  chooses what his aiming aids (a rocket's lead, a grenade's arc: inputs he already has) are computed for: today always
  the enemy, then also a doorway or an exit.
- **A way**: one of up to three ways to that target (the walker's shortest and the pros' other ways), chosen when the
  target changes.
- **A belief** (an output that is not an action): where the enemy is now, as a spread over the map's places. In the
  simulator it learns from the true answer, which he is never shown; what it says is fed back to him in the place
  tokens. This is "enemy position + uncertainty", learnt. The pros' demos can start it: the enemy's place while unseen
  is in them on 64% of the samples.

## 3. What it costs on the server

Timed on the rented server (two cores) inside the game's image on 2026-10-11 with nobody playing, random weights, one
thread (`tools/attention_timing_v16.py`; milliseconds a frame for all bots together, the median and the 99th percentile):

| Bots | Today's network | v16 as above (width 96, 58 tokens) | Width 64 |
|---|---|---|---|
| 1 | 0.23 (0.44) | 4.24 (4.93) | 3.86 (4.51) |
| 3 | 1.43 (2.09) | 6.83 (7.59) | 6.00 (7.11) |
| 4 | 1.09 (1.69) | 6.99 (8.44) | 6.04 (6.56) |

Building the inputs takes about 4 ms more; the budget for all bots is 15 ms of a 25 ms frame. Four bots fit. About
4 ms of the cost is the overhead of many small operations, not arithmetic, and can be cut. In training the attention
layers need several times the memory a sequence, so minibatches get smaller: about three to four times slower an update
is my estimate; a dry run measures it.

## 4. Blending the two ways of moving (stage C)

Today the switch replaces his movement outputs by his legs' on a frame; nothing is learnt about his own keys on those
frames, or about his legs ever. Three steps, each checked against the one before:

1. **His legs learn.** Their network becomes a part of his (the same weights at the start) and the game's pay reaches
   it through the frames it moved him: keeping speed without running into a rocket, and more speed for each jump.
2. **His legs see what he sees**: the GRU's state enters their second layer through an adapter that starts at zero.
3. **The switch becomes a share**: the movement outputs are a mix of both, the share set ten times a second. When one
   set of weights does both, the share stops mattering. The measure: how far apart his own movement outputs and his
   legs' are on the same frames.

In the day's probes it made no difference to a fight whether he got there on his legs or on his own feet.

## 5. The owner's wishes, part by part

| He wants to see | In the model | In his rounds and pay | The number, Bobby today -> the pros |
|---|---|---|---|
| Spam used appropriately | place tokens; the target as a place; the belief | a rocket with no enemy in view is free at the pros' places (built 2026-10-11); the lobber as an opponent | blind rockets a minute 0.004 -> 4.5; grenades a minute 0.03 -> 2.2 |
| Pushing an advantage, backing off when weak | the enemy as believed with his strength; the advantage number; the target as the enemy | whole games with pay for the result; nothing paid for the push itself | closing when stacked, just after a frag against otherwise: +34 / +32 -> +37 / +5; when weak +33 -> -12 |
| Aggressive or defensive by score and time | the game token (score, time left) | whole ten-minute games with pay for the result; rounds that begin ahead or behind late | closing behind after 7:00 against ahead: +45 / +56 -> +36 / +7 |
| Traps and combinations | the enemy as seen (in the air), his own projectiles, the target | a room where a rocket throws the enemy up | a rocket then rail or lightning: 0.05 -> 3.6 per ten minutes |
| Strong positions, high ground, the weapon for the spot | the position token | optional: a hit from above paid more (`HIGH_PAY`, built, never used) | higher than the enemy in view 17.5% -> 26%; lowest third 40% -> 28%; rockets in hand in view 19% -> 40% |
| Routes that cannot be foretold | the way output | the watcher on his commonest way | trips on the commonest way 52% -> 40% |
| Quiet movement | how loud he has been (the game token) | none yet | to be measured for the pros first |

Attention gives him the means. The reason comes from the rounds: without whole games nothing makes the score matter,
and a cheaper rocket alone has not made him fire one.

## 6. The pro demos

| Use | State |
|---|---|
| Yardsticks: spam, combinations, behaviour by score and time, item timing, predictability, an aggression index | done for the six maps (`docs/pro_yardsticks.json`); Bobby through the same (`docs/bobby_yardsticks_<tag>.json`) |
| The places, and the strength of a position by cell with the weapon held there | done for the six maps (`sim/pro_places/`) |
| The four other maps; the pros' ways as routes; walking; when they spam; combinations by hits | being pulled (2026-10-11 evening) |
| The belief: where the unseen enemy is | possible (64% of the samples have it); needs the converter's corpse fault fixed (B-219) and the tokens built |
| The pros' choices by situation as a fading teacher on his target | later, on the owner's word, after the gap in the index is seen |
| Exact frags, landing points, both scores | after the parser is fixed (B-218): "do this right not rush it" |
| Never | their mouse and trigger (it destroyed his aim on 2026-10-04) |

## 7. Order

- **Stage 0, done**: the timing on the server.
- **Stage A**: the tokens with the new information (the enemy as believed, places, his position), the adapter from
  zero. Rounds and pay as the network he starts from. It must do no harm, and cut out it must be missed.
- **Stage B**: the target (item, place, enemy, hold), the choice of way, the belief, the time left and the noise,
  whole games with pay for the result.
- **Stage C**: his legs as a learning part of him and the switch as a share; a list of events if the numbers ask for it.

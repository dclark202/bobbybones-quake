# v16: attention (the proposed model, and what the pro demos can do for it)

A proposal for the owner's review (2026-10-11). Nothing here is built. The earlier scope note is
[ATTENTION_POC.md](ATTENTION_POC.md) (2026-10-07: timings on the rented server); the first pass of the run is
[../runs/MANIFEST_v16.md](../runs/MANIFEST_v16.md).

**What it is judged by** (the owner, 2026-10-11): "Game awareness primarily. Also how much his movement begins to blend
together the two styles fighting/moving we have now." What he wants to see: "Rocket/plasma/grenade spam used
appropriately"; "Playing aggressive/defensive depending on score/being in control/etc. (in control = knows item times
and has stack to contest them when they become available)"; "Setting traps/using weapon combos for frags (rocket to
disrupt movement, then LG on the midair enemy since they cannot dodge as easily)". Whole ten-minute games with pay for
the result: "Yes". Training speed: "completely neutral ... I just want him to learn, and be able to fit 4 bots on the
server that I am paying for."

## 1. Today's model, and what it cannot do

    576 inputs -> Linear 256, tanh -> Linear 256, tanh -> GRU 512 -> 12 outputs (75 choices) + a value     1.44 M weights
    his legs: 61 inputs -> Linear 256, tanh -> Linear 256, tanh -> 4 outputs (17 choices)                  frozen, switched in

- Every thing has a fixed slot: "the nearest projectile", "the second nearest", "the red armor". What he learns about
  one slot he does not know about another, and a relation between two things (the enemy is near the red armor, the red
  armor is back in five seconds, I have 40 health) has to be learnt slot pair by slot pair.
- His memory is the GRU's state: good for the last seconds, poor for "he took the mega 28 seconds ago".
- He can aim only at an enemy: the inputs that help him aim (the lead of a rocket, a grenade's arc) are computed for
  where he believes the enemy is. A doorway, an exit, an item spot cannot be a target.
- Nothing says how the game stands as a whole: rounds are two minutes and a frag pays the same at any score.
- His two ways of moving are two networks with a hard switch.

## 2. The proposed model

Attention is added beside what he has, not in place of it. The path of today's network stays whole, so on its first
frame v16 is the network it starts from, weight for weight.

```
                         today's path (kept, carried over)
 576 flat inputs ─────────> Linear 256, tanh -> Linear 256, tanh ──────────────┐
                                                                               (+)──> GRU 512 ──> outputs
 THINGS (up to 64 tokens)        2 blocks of self-attention                     │      (kept)      (kept; new ones
  1 himself   1 the game         width 96, 4 heads, feed-forward 192            │                   in stage C)
  enemies (1; up to 5 in groups) each token: Linear(its numbers -> 96)          │
  6 projectiles                   + a learned vector for its kind               │
  12 items    8 places           tokens that are not there are masked           │
  6 on his way (waypoints, jump)                                                │
  6 sounds    16 events ─────────────────────> read-out: himself's row (96)     │
                                               + one query over all rows (96) ──┘
                                               -> Linear 192 -> 256, starts at ZERO
```

| Part | Size | Starts as |
|---|---|---|
| Token layers, one a kind (9 kinds): `Linear(F_kind, 96)` and a kind vector | about 25,000 weights | random, small |
| Self-attention block, twice: 4 heads of 24, feed-forward 96 -> 192 -> 96, layer norm before each part | about 75,000 each | random |
| Read-out: his own row, and one learned query attending over all rows | 192 numbers | random |
| Adapter into the GRU's input: `Linear(192, 256)` added to today's encoder output | 49,000 | **zero**: the network is the old one until training moves it |
| Today's encoder, GRU and outputs | 1.44 M | carried over |
| A second value output: the chance to win this game (stage B) | 513 | zero |
| His legs as a part of the network (stage C, section 4) | 0.1 M | carried over from `move_v15n` |

About 1.7 M weights in all. Why an adapter that starts at zero and not a distillation into a new network: a copy is
loose (the lesson of 2026-10-10: a network that agreed with the movement network on nearly every frame could not strafe
jump), and a control that he equals on day one makes every later check readable.

### The things

A token is a view: its numbers are cut out of the flat input vector inside the network, and only the new ones (places,
events, the time left, the noise he made: about 230 numbers beside today's 576) are added to that vector. All of it is
under the same limits: what he does not see or hear is not a token. The flat inputs stay while the tokens prove themselves; then the groups the tokens carry are thinned out of the
flat path (dropped at random in training) so that he has to read the tokens.

| Kind | How many | What a token holds | Today |
|---|---|---|---|
| Himself | 1 | health, armor, weapon in hand, ammunition, speed, his hands, his legs' switch | "self", "weapons", "own hands", "his movement", "his legs" |
| The game | 1 | his frags, the enemy's, the difference, **the time left in the game**, the item clocks, **how loud he has been in the last seconds** | "clock and score"; the two in bold are new |
| Enemy | 1 (5 in groups) | where, how fast, facing, weapon, in view or how long ago, what he last fired, the damage he took, the map reader's numbers for his place | "enemy", "enemy shots", "enemy pain", "memory", "more enemies" |
| Projectile | 6 | where, how fast, its kind, a grenade's fuse, when and how close it passes | "projectiles" |
| Item | 12 | where, the way to it in seconds, up or not as he believes, when it is back as he believes, his intention or not | "items", "more items", "routes", "intention" |
| Place | 8 | **new**: the nearest exits, doorways and item spots of the map: where, in view or not, whether a rocket, a plasma ball or a grenade from here reaches it and the view that does it | the lobber's exit list (`_trick_points`) has them per map |
| His way | 6 | the next waypoints to his target, the jump ahead: what his legs' network is shown | "jump ahead"; the legs' own inputs |
| His position | 1 | **new** (the owner, 2026-10-11: "a 'strength of position' token ... which then influences what weapon they are likely to chose"): his height against where he believes the enemy is, how much of the ways around he overlooks from here and from how many he can be seen, his ways out, how long he has stood here | "who stands higher" is counted (B-160) but he is not shown it |
| Sound | 6 | the last sounds heard: where from, what, how long ago | "sounds", "hearing" |
| Event | 16 | **new**: a short record with times: the enemy last seen (where, with what, how strong), an item he heard taken, an item he took, damage dealt and taken, a frag, a death, **his own loud moments** (a rail or lightning shot, a jump, running where the enemy could hear) | partly "memory" (the last of each only) |

Events are few and sparse: sixteen cover about a minute of a duel. This is not attention over 1,400 past frames (ruled
out in the note of 2026-10-07): the GRU keeps the last seconds, the event record keeps what happened and when.

### Outputs

Stage A and B: the twelve he has. Stage C adds two, and both stay inside the fairness rules (he still has to move the
mouse and press the trigger):

- **A target**: one of the enemy and place tokens, or none, read twice a second. It does not aim for him. It chooses
  what the aiming inputs he already has (a rocket's lead, a grenade's arc) are computed for. Today that is always the
  enemy. With a place as the target he can put grenades into a doorway and plasma at an exit he heard the enemy near.
- **His intention as a choice among the item tokens** in place of the fixed list of eight.
- **A way**: one of up to three ways to his target (the walker's shortest and the pros' other ways, which the atlas
  has), chosen when his target changes; his legs take that way. Today there is one way to a target and his legs take
  it every time: his routes are predictable by construction (the owner's playtest of 2026-10-11: "I find them in the
  same 2 or 3 spots").

## 3. What it costs on the server

The rented server has two cores; four Bobbys must fit in a frame of 25 ms, of which 15 ms are the budget for all of
them together. Measured there on 2026-10-07 with random weights (median for four bots): today's network 1.0 ms, one
attention layer with one query over 40 tokens 2.3 ms, with a self-attention layer among the tokens 3.1 ms; building the
inputs takes about 4 ms. The model above is larger (two blocks, 64 tokens): my estimate is 5 to 7 ms for four bots.
**Before anything is trained** it is timed with random weights on the PC and, on the owner's word, on the server.
Pass: four bots under 8 ms at the median and 12 ms at the 99th percentile. If it fails: one block, width 64, or 48
tokens, in that order.

## 4. Blending the two ways of moving (stage C)

Today the switch replaces his movement outputs by his legs' on a frame, and nothing is learnt about his own keys on
those frames or about his legs ever. The blend in three steps, each a check against the step before:

1. **His legs learn.** Their network becomes a part of his (the same weights at the start) and the game's pay reaches
   it through the frames it moved him. It can then learn what it never knew: to keep speed and not run into a rocket.
2. **His legs see what he sees.** The GRU's state enters the legs' second layer through an adapter that starts at zero.
3. **The switch becomes a share.** In place of "his keys or the legs'", the movement outputs are a mix of both with a
   share he sets ten times a second, and the share's two ends are today's two modes. If one set of weights comes to do
   both, the share stops mattering: that is the blend. The measure: how far apart his own movement outputs and his
   legs' are on the same frames, fighting and travelling. Today they are two different players.

## 5. The owner's three wishes, part by part

| He wants to see | In the model | In his rounds and pay | Measured by |
|---|---|---|---|
| Spam used appropriately | place tokens, the target output, events ("heard at the teleporter") | the blind-fire rule as it is (a rocket with no enemy in view is judged by where it lands); the lobber as an opponent who does it to him | shots with no enemy in view by weapon: how many a minute, the share that land within a splash radius of where the enemy is, damage from them; beside the pros' |
| Aggressive or defensive by score, control and time | the game token (score, time left), item tokens with his beliefs, the event record, the second value output | **whole ten-minute games with pay for the result** in a share of his rounds (stage B); rounds that begin behind or ahead with a few minutes left | by game state (ahead, level, behind; early, late): how fast he closes on the enemy, fights he starts, time near the items about to return; the share of the big items he is at within two seconds of their return ("in control") |
| Traps and combinations | the enemy token (in the air, his speed), projectile tokens for his own rockets, the target output | a room where the enemy is thrown up by a rocket (as the one-weapon rounds were built); nothing paid for the combination itself | frags within 1.5 seconds of his own rocket's knock, by the second weapon; frags by a grenade or plasma fired with no enemy in view |

| Routes and positions that cannot be foretold; high ground (the playtest of 2026-10-11) | the position token, the way output | an opponent that waits on his commonest way (the watcher does this already); a hit from above worth more (`HIGH_PAY`, built and never used) if the owner says so | the share of his time in his eight most-used places and in the lowest third of the map, the share of his trips on the commonest way, his height against the enemy in view; beside the pros' |

Attention gives him the means. The reason comes from the rounds: without whole games nothing makes the score matter,
and without the weapon rounds nothing makes a grenade worth firing.

## 6. The pro demos

What we have: 3,712 duels, 34,238 minutes, on the six maps. A demo is one player's view: what he saw is there (the
enemy only while the server sent him, about when he was in view; never the enemy's health), what he pressed is
inferred, and the score and the game clock are in the file but not read out by `sim/demo_dataset.py` yet.

| Use | What | Risk |
|---|---|---|
| **1. Yardsticks** (first, cheap) | the same numbers as section 5's last column, for the pros: spam by weapon and where it lands, combinations a game, behaviour by score and time left, arriving at items on their return, walking. As the speed profile did for movement: it says how far he is and from what | none; needs the score and clock read out of the demos |
| **2. The places** | where the pros' shots with no enemy in view land, map by map: the list the place tokens are drawn from | none: data for his inputs, not a lesson |
| **3. Teaching the event record to remember** | on demo sequences turned into tokens, the attention part alone learns to foretell what the demo shows later: where and when the enemy comes into view next, which item the player takes next and when, damage in the next two seconds. No output of his is trained on it | low: his aim and keys are not touched. The demo sets must be made again with tokens |
| **4. The pros' choices as a starting lean** | which item they go for and whether they close or hold, given score, time and what they have: a teacher on the intention (later the target) output that fades, as the item rule is today, but from the pros and by situation | medium: a teacher kept too long is copied blindly (v14's lesson); fading and the control guard it |
| **Not** | their mouse and trigger (it destroyed his aim on 2026-10-04); anything about the enemy while unseen (it is not in a demo) | |

## 7. Order

Stage A: the things, as an adapter that starts at zero; timing first. Stage B: events, the noise he makes, the time
left, whole games with pay for the result, the yardsticks from the demos. Stage C: the target output, the intention
among the items, his legs blended. Each stage starts from the best network of the one before and is checked against it.

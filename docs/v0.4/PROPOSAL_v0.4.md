# v0.4: the architecture after v0.3, Pluto's way (a proposal, 2026-10-14 night)

*Written on the owner's word while v0.3 trains ("I would like to implement a type of 'memory' for the bot, modeled
after the pluto starcraft AI bot ... propose architecture changes for the next model iteration ... the five goals are
what matter here, the bot ultimately has to win matches"). Nothing here is built or started. v0.3 (`duel_gru_v0_3`,
[../v0.3/RUN_v0.3.md](../v0.3/RUN_v0.3.md)) runs to Thursday; this is the plan for the model after it, named v0.4 here
until the owner names it. What is known of Pluto: [../v0.3/PLUTO.md](../v0.3/PLUTO.md).*

## 0. One page: the eight changes, what each is for, and whose call it is

| # | Change | Goal it serves | Cost | Call |
|---|---|---|---|---|
| 1 | **The learning step rebuilt** (B-237): his memory stepped over whole sequences by the library's own routine, not frame by frame in Python | all of them: about a third more updates a night | a day's work, proven identical | mine; first, because everything below costs time |
| 2 | **A bigger network, about 13 M weights** (today 1.75 M; the owner's ceiling 20 M): memory 1536 wide fed by 768, encoder 768, tokens 192 wide, three attention blocks; widened *exactly* from v0.3's end, so nothing learnt is lost | all | an update 1.5 to 2.5 times longer, or about 3,000 duels an update instead of 5,040; **one Bobby on the public server** instead of two | **the owner's**: the size (13 M or the 19 M shape) and longer updates or fewer duels (section 3) |
| 3 | **A long memory, Pluto's way**: his state written every 0.8 s into a store of 224 slots (3 minutes), read by attention every key frame, fed into his memory through a door that starts shut | 4 counterplay, 3 positioning, the enemy in his head | 10 to 15% of an update; 0.4 GB | mine, as its own test arm |
| 4 | **His memory asks the inputs**: the attention part's second block takes its question from his memory, not from the inputs alone (Pluto: every attention query comes from the memory) | the enemy in his head | tiny | mine |
| 5 | **A learned win chance** in bands, paired across both seats, with a twin that sees the truth in training only (Pluto's judge, built for the game's result, not the 25-second value that failed today) | 4, 5 | one output; a cheap test on v0.3's whole games before any run | mine for the output; the pay is 6 |
| 6 | **The pay leans on winning**: every frame pays the change in his chance of winning (`WIN_PAY`, built in stage B, never run); the flat frag and death pay gone in games; item and stack pay and the item rule faded to a standing prior | 4 counterplay, 2 weapons | no time; a real change of what he is paid for | **the owner's** (section 6) |
| 7 | **The strategic choices decided in order**: his target first, then his way, then the switch to his legs, then his weapon, each seeing the one before (Pluto decides the action, then its target) | 3, 2 | tiny | mine |
| 8 | **Damage taken at 0.2 of damage dealt and no flat death cost** (the owner's thought tonight) | 2, 4 | none | its own test arm; my recommendation is 6 instead of a flat removal (section 7) |

Not in this package, said plainly: nothing here teaches strafe jumping on his own feet (goal 1 is movement; his legs
stay as they are; the candidate is the judge of pro-like travelling, [../v0.2/V16_TRAINING.md](../v0.2/V16_TRAINING.md)
proposal 5, which is its own proposal). Rockets in hand are watched in v0.3 with the styles gone; if they fall, that is
a pay question for section 6, not an architecture one.

**The order** (the standing rule: one part per start, ten updates and the check against the control before any run):
1 → 2 → the offline test of 5 → 3 with 4 → 5 → 6 and 8 as separate arms → 7 → v0.4 is the arms that held, one run.

## 1. What v0.3 will not fix, and why

v0.3 is the right baseline (whole games, the real clock, the openings, no styles: everything that tested level or
better). The faults below are structural and the night's test runs (V, H, S, B) left every one of them where it was.

| Fault | The measure | Where it comes from |
|---|---|---|
| **He always closes in and fights to a death** | closing speed ahead / even / weak 53 / 56 / 52 u/s (the pros 7 / -3 / 17); an even fight ends with someone dead 53% (33%); when ahead he dies 2.5 times as often as a pro ([../v0.2.2/NIGHT_1013.md](../v0.2.2/NIGHT_1013.md) 0.2) | nothing pays breaking off; his opponents are copies of himself who also close; the item rule names the next item whatever his standing; his memory reaches 10 to 30 s, so "I am ahead and he is weak" is rebuilt from the inputs each time |
| **Item control does not follow his standing** | mega and red taken when ahead / weak .55 / .47 (the pros .64 / .35); he comes to an item the enemy is nearer to 61% of the time (28%) ([../v0.2.1/ENEMY_MODEL.md](../v0.2.1/ENEMY_MODEL.md) 3) | the same; and a frag is paid +1 at 0:0 and at +8 with a minute left |
| **Where the enemy is does not reach his choices** | the blindfold on his intention costs him nothing: 51.0% against himself with everything about an unseen enemy hidden from that choice (the same hidden from aim: 14.9%) | his intention's teacher never looks at the enemy; his memory's own guess of the unseen enemy is worse than the rule-made belief inputs (683 units against 445) |
| **His memory is taught over ten seconds** | the learning window is 384 frames; what he did 20 s ago moves his choices a little, nothing older than 100 s (`tools/memory_reach.py`; B-248) | a loss can only change how he wrote his memory inside the window; 768 frames do not fit the card |
| **The pay horizon is 25 seconds** | `--gamma 0.999`: a reward 25 s ahead counts 37%, a minute ahead 9%; the long count (0.9998) is for items and stack only | holding a lead, denying an item, a position for the next fight are nearly worthless to him |
| **The second memory of test S did not help** | level at update 10, two under at 20, 21% slower; the owner's play test: "fought worse" | four faults, named ([../v0.3/RUN_v0.3.md](../v0.3/RUN_v0.3.md)): it fed every output, aim and keys too; its training pulled on the rest of the network; it learnt at the full rate on a weak signal; the guessing game did not reach it |
| **The judge that sees the truth did nothing** | the 25-second value explained the returns no better with the truth (0.906 against 0.910) | the noise is in the next seconds (hits, misses); the truth decides games, not seconds; the judge was asked the wrong question |

What Pluto does about each: a memory over minutes that is read, not decayed; a judge of the *game* with privileged
inputs in training; a pay that is the game's result; no teachers. And it is 150 times bigger.

## 2. The shape, in one picture

```
inputs (791) ──► tokens (48) ──► block 1: tokens look at tokens
                                 block 2: asked by [the summary token ; his memory of the frame before]   (change 4)
                                              │
            encoder (512) ◄──────────────────┘ (added, through the door, as today)
                 │
                 ├──► + the store's read  (asked by his memory of the frame before; 4 heads over 224 slots; door at zero)   (change 3)
                 ▼
            his memory: GRU 1024                                                                         (change 2)
                 │
   ┌─────────────┼──────────────────────┬──────────────────┬────────────────────┬──────────────────────┐
 policy (13;   value, 25 s     value, 2 min (2)      win chance in bands     the guessing game     [training only]
 the strategic                                        paired across seats     (place, near)         the twin win head
 four in order)                                       (change 5)                                    that sees the truth;
 (change 7)                                                                                         the enemy's target
                 │
            every 0.8 s: write a slot = f(memory, the encoder's mean since the last write, the tick's events) ──► the store
```

With every door at zero and the new rows at zero the network answers exactly as v0.3's end: every change is a part that
can be given to a network without changing it, and opened only by what wins games. That is the rule that let stage A
in without cost and that test S kept (its door opened to 5% in 25 updates); the rest of S's faults are avoided below.

## 3. The size (change 2)

Today's network, counted from v0.3's checkpoint: 1.75 M weights (his memory 1.18 M, the encoder 0.27, the attention
part 0.25, the outputs 0.05). The owner tonight: first "5-10m params is probably fine", then "one estimate is that we
could go up to 20m weights, I'd keep it maybe less than that but 6.5m might still be too small"; one Bobby on the
public server if that is the price. Pluto is 315 M; the shapes below are a twentieth to a fifteenth of it.

**Three shapes, counted** (his memory is three gates of (input + width + 2) × width; the rest is small beside it):

| Shape | Memory | Encoder | Tokens, blocks | Store, judge, outputs | Total | Memory's work against today |
|---|---|---|---|---|---|---|
| today | 512 fed by 256: 1.18 M | 256: 0.27 M | 96 wide, 2: 0.25 M | 0.05 M | **1.75 M** | 1× |
| the small one | 1024 fed by 512: 4.7 M | 512: 0.67 M | 128 wide, 3: 0.6 M | 0.5 M | **6.5 M** | 4× |
| **proposed** | **1536 fed by 768: 10.6 M** | 768: 1.2 M | 192 wide, 3: 1.1 M | 0.8 M | **13.7 M** | 9× |
| the ceiling | 2048 fed by 768: 17.3 M | 768: 1.2 M | 192 wide, 3: 1.1 M | 0.8 M | **20.4 M** | 15× |

**The shape proposed: about 13.7 M.** Under the owner's ceiling with room left for the store and the judge; the memory
is three times as wide as today's and nine times the work; the tokens twice as wide. The 20 M shape spends nearly
everything on the memory's own recurrence (17 of 20 M) for 1.6 times the cost of the proposed one and a third more
width; I would go there only if arm S shows the 13.7 M network still learning faster than today's at its tenth check,
and then by the same exact widening again.

**Widened exactly.** New units of the memory start with their gates and their outgoing rows at zero, new encoder units
the same: the wide network gives v0.3's end's answers to the last digit on fixed inputs (the proof as
`sim/add_attention.py --same` gives it). The tool is a hidden-width widening beside `sim/reshape_policy.py`, which
widens inputs only. So nothing of 60 hours of learning is spent; the check against the control at every tenth update
judges what the room buys.

**What it costs, and why the estimate is wide.** The card (16 GB) holds 13 GB today at 5,040 duels × 384 frames in
360 pieces, and what fills it is the attention part's graph over whole sequences, not the memory. The memory's own
work at 13.7 M is nine times today's: in the rollout a multiplication of [10,080 seats × 768] by [768 × 4,608] a
frame, about 2 to 3 ms on the card, a second or two over 384 frames; in the learning step, today stepped frame by
frame in Python where the time is the stepping and not the size, so the size costs little there until change 1 moves
it to the library's routine, where it is about 30 to 60 s of a 408 s update. The attention part at 192 wide needs
twice the activations: the pieces go from 360 to about 480 or the part runs at half precision (it does already). My
estimate: **an update 1.5 to 2.5 times longer at the same players, or the same time at about 3,000 duels**; measured
in arm S, with the card's memory and the time a step. Change 1 claws a third back first. **The owner's choice**: longer
updates (fewer a night; whole games take 63 updates to reach their first end today) or fewer duels an update. I
recommend fewer duels: 3,000 duels are 6,000 seats; v0.2 learnt at 5,040 matches with groups of three and four in
them, and one against one has no groups.

**On the server.** 13.7 M weights in plain numpy are about 55 MB read a frame a bot, 3 to 6 ms a bot at one thread:
one Bobby fits the 25 ms a frame with room, two probably, four do not. The public server's two Bobbys become one, on
the owner's word and not before a network of this size has been played on a private server
(`tools/attention_timing_v16.py`'s way of measuring, at the 99th percentile). The rented server (two slow cores, 2.5
times slower than the PC) would carry one.

**The earlier size test said bigger was worse** (RESULTS 2026-10-05: the same kind of network at three sizes copying
the pros' Blood Run demos for eight minutes each; 5.2 M worse than 1.4 M on every output, 16.3 M worse again with 40%
of the steps). It does not decide this:
equal time, not equal steps; 25 hours of demos, where a bigger network overfits sooner; copying, not self-play; no
memory to fill. Size alone was never tested in self-play here. Pluto's lesson is size with memory and a judge together,
which is this package; the exact widening makes the test free at its start.

## 4. The long memory (change 3), in detail

**Not a second GRU.** Test S's slow memory decayed: a GRU holds a mix of everything and forgets by a rate. Pluto's store
keeps each moment as it was and the read is a lookup: "when did I last see him, and where" is one slot, not a trace.

- **The write.** Every 32 frames (0.8 s) a slot of 128 numbers: tanh of a layer over [his memory after the frame, the
  mean of the encoder's output since the last write, the tick's events as a short hand-made list: enemy seen, heard,
  hurt him, hurt by him, an item taken and which]. The events ground the slot before the layer has learnt anything.
  224 slots are 3.0 minutes, the owner's window ("2 to 3 minutes"; Pluto 4.3). The variant he leaned to on
  2026-10-14: every 24 frames (0.6 s) × 320 slots, the same 3.2 minutes at a third more cost.
- **The read.** On the key frames (every fourth, as his hands are read) a question from his memory of the frame before
  (Pluto: "the attention queries come from h_{t-1}, not from x_t"), four heads over the slots, each slot's age as a
  feature beside it; the answer through a door at zero into his memory's *input*. Pluto adds it into the gates; at one
  cell the input is the same thing and keeps the numpy twin (`plugins/netpass.py`) simple. Between key frames the
  answer is held.
- **The training.** The slots written inside the rollout are under the gradient; the slots before it are stored
  numbers, as `sim/slowmem.py`'s ring keeps them (stale by minutes at a learning rate of 1e-4: acceptable, measured
  harmless in S). The read learns over every slot; the write's layer is shared by every slot, so what it learns to
  write in the window it writes everywhere. Its lessons are the guessing game (where the unseen enemy is, the landmark
  he is nearest to) and the win chance, both routed to it: the questions a pro asks of his memory. The part learns at a
  quarter of the trunk's rate.
- **S's four faults, each answered.** It fed every output, aim and keys too → the read enters his memory's input and
  reaches aim only through the memory, and the door opens by what wins games. Its training pulled on the rest →
  its lessons (the guessing game) stay at `--aux-trunk 0` for the trunk and full for the store (AUDIT F1). Full rate on
  a weak signal → a quarter of the rate. The guessing game did not reach it → it is its first lesson.
- **Where it lives.** `sim/store.py` beside `sim/attn.py` (torch for the trainer, the same sums in numpy for
  `sim/test_suite.py` and both plugins); the per-seat state array grows by 224 × 128 numbers at half precision (57 KB);
  the plugins already keep the events the write needs (`note_take`, `hear`, `seen2`). On the server the read is 224 ×
  128 a key frame a bot: nothing beside today's 7 ms.
- **The gate before a run.** The memory's guess of the unseen enemy must beat the belief inputs at 10 and at 30 s
  unseen (today it is nearer 21% of the time); level against the control at updates 10 and 20; and the blindfold on his
  intention must begin to cost him (today 51.0%; a cost is the first sign that the enemy has reached his choices).

## 5. The judge (change 5), in detail

Pluto's training network has several value outputs, a win output in 53 bands paired across both players, and a guess of
the opponent; all are cut from the released network. Bobby today has a value at 25 s and two at two minutes, and a
hand-made table (`sim/win_chance.json`, 257 pro games) for the pay by the game that was never switched on.

- **The output.** From his memory and the newest slot: the game's result in 21 bands (the margin at 10:00 from −10 and
  beyond to +10 and beyond, a draw the middle band); his chance of winning is the bands summed. Trained by the results
  of whole games: v0.3 produces them from its update 63 on, so the lesson has data from the first hour of v0.4's test
  arms.
- **Paired.** Both seats are the same network at the same frame in self-play, so seat A's margin m is seat B's −m: one
  loss ties the two, Pluto's paired head. It halves the noise and makes the chance honest (the two seats' chances sum
  to one).
- **The twin that sees the truth.** A second copy of the output, fed 55 more numbers that only the simulator knows (the
  enemy's place, stack, weapon and target, the items' timers; the patch of 2026-10-14 in the scratchpad), training only,
  the same target. Its use is a lower-variance baseline for the win pay's advantage, which is the one place a judge
  earns its keep: today's test asked it about the next 25 seconds, where the truth decides nothing; the game's result
  is what it decides. **Tested offline first, on v0.3's saved whole games** (frames and results from a check), the
  processor only: both outputs fitted on frames, scored on held-out games. If the twin explains the result no better,
  it stays out and the plain output carries the pay.
- **The start.** The output's layer is fitted to the hand table on score and clock, the rest zero: `WIN_PAY` on day one
  pays the table and drifts to the learned chance as the games come in. His chance is also a number to show on the
  server (Pluto draws a graph of it; the owner may like it in the chat).

## 6. The pay (change 6): the owner's decisions, each with its evidence

The pay is the owner's. These are the four decisions, with what the evidence says about each, and each is its own arm
(ten updates, the check against the control, and the counterplay table, the aggression index and deaths by standing
read beside the frag share: a pay that costs two points of frag share and moves closing-when-weak toward the pros is a
win for goal 4 and is reported as one).

1. **`WIN_PAY=1` with the learned chance.** Every frame pays the change in his chance of winning; the leader is paid
   to hold, the one behind to risk; the two seats sum to zero; a game's pays sum to its result, so nothing can be
   pumped. One rule gives "defend a lead late", "take risks when behind", "a frag at +8 is worth little", "a death at
   +8 with 30 s left costs about nothing", with no behaviour paid for. Evidence: the counterplay table; B-216 (a
   visitor's point on offense or defense by the score); Pluto's pay is the result and nothing else.
2. **The flat frag (+1) and death (−1) gone in games.** They are gone with `WIN_PAY` already (`duel_env.py`: the pay
   by the game replaces them in whole games); damage dealt and taken stay at a lower weight, because aim needs a
   signal within seconds.
3. **Item and stack pay faded over the run to a third** (today 5.5 of the 6.1 he earns a player-minute), **the item
   rule faded from 2.0 to 0.2** as a standing prior. Evidence: run B silenced 77% of the rule's frames and his items did
   not move (mega .806 / .808 a player-minute, red .968 / .952): the rule is not what holds his item control, so a fade
   costs little; and a rule at full weight to the end of every run is the template the owner wants gone (B-240).
   Pluto has no teachers; we keep a prior, because 60 hours of item timing are worth keeping.
4. **`--gamma` stays at 0.999** for the short value; the win pay is the difference of a function of the state, so it
   needs no long discount to carry (stage B's argument). Nothing else of the pay changes: no pay for any yardstick.

## 7. The owner's thought on the death penalty (change 8)

*"Should we remove the reward penalty for death? I've read that damage taken should be < 0.2 × damage given in reward
and the penalty for death should be eliminated to make a more aggressive bot."*

- **Where the advice comes from.** Setups where the agent turns passive: hides, will not engage, trades nothing.
- **His fault is the opposite, measured.** He commits to fights at 12.6% of sightings (the pros 6.6%); with a stack
  under 60 at 4 to 5% (1.2%); he closes in at 50 to 65 u/s whatever his standing; an even fight ends with him dead 27%
  (15%); ahead, he dies 2.5 times as often as a pro; he walks to an item the enemy is nearer to 61% of the time (28%).
  He is not timid; he is indiscriminate. A flat removal of the death's cost makes that worse by construction.
- **What a death costs him today** (`sim/duel_env.py` lines 6918 to 6984 and v0.3's command): the flat −1 (already
  not paid in whole games under `WIN_PAY`); the stack pay he held (`STACK_PAY=1.0`); the trip's pay on the way
  (`--item-loss 0.5`); and damage taken at `--dmg-taken-w 1.0` (v0.3 halved it from 2.0) × 0.005 a point. The flat −1
  is one cost of three; dropping it alone changes less than it seems.
- **Recommendation.** Not a flat removal: make the death's cost the game's (change 6). A death at +8 with 30 s left
  costs about nothing, a death at 0:0 costs a lot, a death against a fresh spawn when stacked costs more than one when
  weak: that is a pro's aggression (fearless when it pays, careful when it does not), from one rule. **Damage taken at
  0.2 is cheap and goes in as its own arm** (`--dmg-taken-w 0.2`, ten updates, the check, the aggression index and deaths
  by standing). My expectation, written down so it can be wrong: more damage traded, more deaths when weak, no gain in
  frag share. The pros' dodging is what a low weight on damage taken would unlearn: after a hit of 50 or more they break
  the line of sight within 2 s four times in five.

## 8. The smaller changes (4 and 7)

- **His memory asks the inputs** (4). Today the attention part's questions are made from the inputs alone: it cannot
  look for what his memory wants ("where is the door he came through last time"). The second block's question becomes
  [the summary token; his memory of the frame before, through a layer at zero]. Identity-checked; the plugins carry
  the memory already.
- **The strategic choices in order** (7). Today the thirteen outputs are sampled independently on the same frame: his
  way does not know the target he just chose, his legs' switch does not know the way, his weapon knows neither. Pluto
  decides the action, then its argument, then its target, each conditioned on the last. Here: the intention's sampled
  choice (through a small embedding) is added before the way, the legs and the weapon outputs; the way's before the
  legs'. Exact in numpy; `head_masks` unchanged; the layers at zero.

## 9. The learning step (change 1)

B-237 as written: his memory stepped over whole sequences by the library's routine (sequences cut at round ends by
`b_done`), the attention part's activations at half precision or recomputed, fewer and larger pieces. Identity: the
same loss to 1e-5 on a saved rollout. Expected: the learning step from 245 s toward 120 s of a 408 s update, about a
third more updates a night. First, because changes 2 and 3 cost time and this pays for them.

## 10. What v0.3's end must be read for before the decisions (Thursday, 19:00)

1. **The counterplay table** at v0.3's end against v0.2 (`tools/counterplay.py`): if whole games and the real clock
   alone moved closing-by-standing and deaths-when-ahead, change 6 is a smaller lever; if not (the night's runs say
   not), it is the lever.
2. **Rockets in hand** with the styles gone (the weapon watch at every check): a fall decides whether the pay needs a
   weapon prior (section 6 has none).
3. **`tools/memory_reach.py`** on v0.3's end: his memory's reach after a night of whole games, the baseline the store
   must beat.
4. **The frames and results of whole games** from the checks, kept for the offline test of the judge (section 5).

## 11. The order, and the test of each part

The standing rules hold: one part per start; ten updates and the check against the control (160 games, ten maps, a
check's noise about three points) before anything goes into a run; the control is v0.3's end.

| Step | What | The gate |
|---|---|---|
| 1 | B-237, the learning step | identical loss on a saved rollout; the update's time |
| 2 | Arm S: the exact widening to about 13.7 M | identical answers at the start; level at updates 10 and 20; the update's time and the card's memory measured; the owner's choice of updates or duels made on the numbers; the 20 M shape only if S is still climbing at its tenth check |
| 3 | The judge offline on v0.3's whole games | the twin beats the plain output on held-out games, or stays out |
| 4 | Arm M: the store and the memory's question (3, 4), door shut at the start, the guessing game routed to the store | the memory's guess beats the belief inputs at 10 and 30 s; level against the control; the blindfold begins to cost |
| 5 | Arm J: the win chance (5), no pay | its calibration on held-out games beats the table |
| 6 | Arm W: the pay (6) in the owner's form; arm P: damage taken 0.2 (8) | the counterplay table and the aggression index move toward the pros; the frag share read beside them |
| 7 | Arm D: the choices in order (7) | level or better |
| 8 | **v0.4**: the arms that held, one run from v0.3's end, the control v0.3 | beats the control; the owner's play test |

Each arm is an hour of the card at today's size (ten updates) plus the check; two or three a night. The whole package
is about a week of evenings beside the day's runs, with the owner's three decisions (the size's cost, the pay, the death
cost) taken as the numbers come in.

## 12. The five goals, honestly

| Goal | What this package does for it | What it does not |
|---|---|---|
| 1. Speed and movement | nothing direct | his legs stay; the judge of pro-like travelling is its own proposal |
| 2. Weapon use | a pay that leans on winning prices the weapon that wins fights; the weapon choice sees the target | no pay for rockets (the owner's rule); the styles' fall is v0.3's to show |
| 3. Positioning | a memory over minutes; places as targets with the enemy in his head | high ground still unpaid (`HIGH_PAY` off) |
| 4. Counterplay | the centre: memory, judge, pay by the game | his opponents are still himself (exploiters dropped on the owner's word) |
| 5. Beat people | the judge's chance shown on the server; later, an opening chosen per person by his record against them (Pluto's bandit) | the play test is the only proof |

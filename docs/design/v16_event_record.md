# v16: the event record, tried on the pro demos

A feasibility test (2026-10-11) of row 3 of section 6 of [V16_ATTENTION.md](V16_ATTENTION.md): "teaching the event record
to remember, by predicting what a demo shows next. None of his outputs is trained on it." Nothing of Bobby's was
trained or changed. Tools: [demo_events.py](../../tools/demo_events.py) (demos -> events and samples) and
[event_pretrain.py](../../tools/event_pretrain.py) (the models and the comparison).

## The answer

- **Against nothing remembered: yes, on two things.** A record of events foretells which big item the player takes next
  (67% right with no memory, 71 to 73% with the record) and when (40% -> 44%), and where the unseen enemy is now (444
  units off -> 382; in his first second out of view 315 -> 125). On the three fight targets (hurt within 2 s, dead
  within 5 s, when the enemy is next in view) memory of any kind adds nothing that could be told from noise.
- **Against a GRU: equal as specified, ahead on items once the list is changed.** The last 16 events foretell what a
  GRU of 256 foretells, within the spread between two GRU runs. With the record split by how often a kind comes (the
  last 8 of the frequent kinds, the last 8 of the rare ones) it is ahead of the GRU on the item targets (which: loss
  0.711 -> 0.658; when: 40.7% -> 43.6% right) and equal on the rest, with half the weights and four passes over the
  data against the GRU's 24 to 48.
- **On maps never trained on the record holds up better** than the GRU on the bucket targets (next item 48% right
  against 40%; when the enemy is next in view 1.740 against 1.79, the trivial guess being 1.779). No model learned
  place there.
- **The list as designed is too short in time.** Pros produce 51 events a minute: sixteen reach back 19 seconds at the
  median, not "about a minute". When a pro is on his way back to the mega, his own last pickup of it is still among
  the last 16 events 16% of the time.
- **Not shown:** that the record adds to a GRU when it is fed into one (v16's arrangement). That model had four passes
  and was still falling steeply when its time was up.
- Every model was still improving when stopped (40 minutes of training in all, one seed each). Differences under
  about 2% of a loss are not findings.

## What was built

| Step | Command | Time |
|---|---|---|
| Events and samples from the sets | `python tools/demo_events.py --out <scratch>/data --procs 2` | 45 s |
| What is in them | `python tools/demo_events.py --stats <scratch>/data` | 20 s |
| Is his last pickup of an item still in the record | `python tools/demo_events.py --reach <scratch>/data` | 40 s |
| One demo's events as a table | `python tools/demo_events.py --show 100 --map bloodrun` | |
| A model: `mlp`, `gru`, `events` or `both` (Anaconda Python, graphics card) | `python tools/event_pretrain.py --data <scratch>/data --model events --minutes N` | as given |
| The record split by rate | `... --model events --record split --tag events_split` | |
| The trained record read with parts hidden | `... --model events [--record split --tag events_split] --load --ablate` | 1 min |
| The tables below | `python tools/event_pretrain.py --report` | |

Samples (1.7 GB) are in a scratch folder, not in the repo. Weights and results are in `data/sim_runs/event_pretrain/`:
`events.pt` (the last 16, as specified), `events_split.pt` (8 + 8, the better one), `mlp.pt`, `gru.pt`, `gru_short.pt`,
`both.pt`, with `results_<name>.json` and `ablate_<name>.json`. A weights file carries the input names, the event kinds
and facts, and the input statistics.

**Source.** The full sets (311 inputs) exist for Blood Run only, and no list in `docs/INPUTS*.csv` has 311 inputs (the
oldest in git has 366, a day younger than the sets). The samples are made from `sets_lite/` (all ten maps, 32 named
columns a frame, written by the `lite` branch of `sim/demo_dataset.py`). Checked against Blood Run's full sets: place
and yaw equal to the last digit; health and armor equal inputs 4 and 5 times 200; the nine "owns" flags equal inputs 80
to 88; velocity from place differences is 12 units a second off the recorded one at the median (339 is the median
speed). The targets were checked against a brute-force count on one demo (600 rows, 599 equal for each target).

## The data

| Map | Demos | Hours | Chains | Deaths seen | Rows | Sixteen events reach back (median) | Eight rare events reach back |
|---|---|---|---|---|---|---|---|
| Aerowalk | 978 | 144.3 | 2,770 | 9,984 | 2,604,380 | 15 s | 39 s |
| Blood Run | 1,061 | 151.1 | 2,694 | 5,617 | 2,725,591 | 22 s | 57 s |
| Lost World | 1,216 | 188.5 | 3,805 | 6,262 | 3,399,431 | 22 s | 60 s |
| Battleforged | 149 | 21.5 | 1,014 | 138 | 388,416 | 21 s | 68 s |
| Furious Heights | 149 | 21.2 | 1,175 | 60 | 383,547 | 20 s | 62 s |
| Sinister | 146 | 20.3 | 920 | 47 | 366,976 | 23 s | 68 s |
| Cure (never trained on) | 129 | 17.3 | 476 | 295 | 312,347 | 21 s | 56 s |
| Hektik (never trained on) | 144 | 19.9 | 1,058 | 612 | 359,533 | 14 s | 47 s |
| Toxicity (never trained on) | 87 | 12.4 | 375 | 503 | 223,335 | 15 s | 46 s |
| Campgrounds (never trained on) | 5 | 0.8 | 7 | 43 | 13,681 | 22 s | 57 s |

4,064 demos, 597 hours, 10,777,237 rows (one every 8 frames: five a second), 1,823,232 events. Training: 9,079,542
rows. Held out: 788,799 rows of the six training maps (by pair of players, so that both recordings of one game are on
one side; one pair in ten, 8% of the rows) and all 908,896 rows of the four maps the project holds out.

**How frames hang together.** A stretch is what the sets call one (frames 25 ms apart). Stretches are joined over a
hole of a few lost frames into a life, and lives over a death into a chain (the next stretch starts as a fresh spawn:
125 health, no armor, machine gun and gauntlet). The record and the clock run on over a chain. Anything else ends it,
and a target that would reach over such an end is left out, not counted as "no". Warm-up is dropped. Half the rows of
the three big maps are in chains longer than nine minutes; on the 150-demo maps it is two to three minutes, and there
most deaths fall into the cuts (see "What the demos cannot teach").

**The now vector** (47 numbers): place, velocity, health, armor, weapon in hand, weapons owned, enemy in view or not,
the enemy's place from him, his velocity and weapon while in view, seconds since the enemy was last in view, his own
view direction, firing. Beside it a learned vector for the map.

**Events** (kind, a weapon or none, a place, a time, four facts):

| Event | A minute | Facts |
|---|---|---|
| fired (his own rocket, rail or lightning; at most one every 1.5 s a weapon) | 14.5 | his health and armor, enemy in view or not |
| enemy in (came into view after half a second or more out of it) | 9.2 | his health and armor, the distance, how long since the sighting before |
| enemy out (where he was last, what he held) | 9.0 | the enemy's velocity, how long he had been in view |
| hurt (at most one a second, with all the damage since the one before) | 8.6 | health and armor after, the damage, enemy in view or not |
| took a weapon he did not own | 2.2 | health and armor |
| took a 25 or 50 health | 2.0 | health and armor after, the gain |
| took yellow armor | 1.6 | the same |
| took red armor | 1.1 | the same |
| took mega | 0.9 | the same |
| took green armor | 0.5 | the same |
| spawned / died | 0.8 / 0.7 | health and armor |
| all | 50.9 | |

Pickups are read from the jumps in health, armor and weapons and set at the item's spot (`plugins/duel_items.json`);
0.1% have no item near (5.7% in the five Campgrounds demos). "Enemy out" enters the record half a second after the loss (a shorter loss is no event); until
then the same facts stand in the record as a running entry, so that nothing is known later than a player knows it.

**Targets**, all from what the demo shows after the row:

| Target | Asked on | What it says |
|---|---|---|
| Enemy next in view: when | 86% of rows (he is out of view) | under 1 s 17%, 1-2 s 12%, 2-4 s 18%, 4-8 s 21%, 8-16 s 19%, over 16 s or never in this life 13% |
| ... and where | when within 16 s | his place then, as an offset from where the player is now (map axes) |
| Next big pickup: which | 72% (one comes within 16 s) | mega 20%, red armor 26%, yellow armor 31%, a weapon 24% |
| ... and when | 95% | under 1 s 10%, 1-2 s 9%, 2-4 s 15%, 4-8 s 21%, 8-16 s 22%, over 16 s or never 24% |
| Hurt within 2 s | 99% | yes 28% |
| Dies within 5 s | 97% | yes 5.5% |
| Where the enemy is now (added) | 64% of the rows where he is out of view | an offset from the player; only where the server sent the enemy all the same |

## The comparison

| Model | Weights | Passes over the training rows | Minutes |
|---|---|---|---|
| Nothing remembered: the now vector through three layers of 320 | 233,736 | 13 | 3.5 |
| GRU 256, trained through 6.4 s (32 rows; the reach of his training today) | 310,920 | 24 | 3.5 |
| GRU 256, trained through 51 s (256 rows) | 310,920 | 48 | 6.0 |
| Record, the last 16 events: two attention blocks of width 96, 4 heads, read out at the now token | 166,600 | 4 | 7.5 |
| Record, 8 frequent + 8 rare: the same model | 166,600 | 4 | 7.5 |
| Record (8 + 8) into the GRU through an adapter that starts at zero | 487,496 | 4 | 8.1 |

The GRU steps over the now vectors of a chain five times a second (his steps 40 times) with its state carried from the
chain's first row. The budget was 40 minutes of training in all; the last three ran while another training run shared
the graphics card, hence the few passes.

**Demos held out, on the six training maps** (788,799 rows). Loss: lower is better.

| Target | Trivial | Nothing remembered | GRU 6.4 s | GRU 51 s | Record, last 16 | Record, 8 + 8 | Record into GRU |
|---|---|---|---|---|---|---|---|
| Enemy next in view, when: loss / right bucket | 1.773 / 21.3% | 1.685 / 27.3% | 1.675 / 27.7% | 1.680 / 27.6% | 1.680 / 27.4% | 1.679 / 27.7% | 1.682 / 27.4% |
| Next pickup, which: loss / right | 1.371 / 32.2% | 0.787 / 67.3% | 0.718 / 70.6% | 0.711 / 71.0% | 0.691 / 71.3% | **0.658 / 73.2%** | 0.704 / 71.0% |
| Next pickup, when: loss / right bucket | 1.726 / 23.6% | 1.383 / 39.8% | 1.388 / 40.3% | 1.387 / 40.7% | 1.377 / 40.7% | **1.325 / 43.6%** | 1.406 / 39.8% |
| Hurt within 2 s: loss / AUC | 0.587 / 0.500 | 0.4645 / 0.784 | 0.4654 / 0.786 | 0.4683 / 0.783 | 0.4658 / 0.785 | 0.4654 / 0.785 | 0.4713 / 0.780 |
| Dies within 5 s: loss / AUC | 0.195 / 0.500 | 0.1382 / 0.881 | 0.1368 / 0.885 | 0.1378 / 0.882 | 0.1365 / 0.886 | 0.1356 / 0.888 | 0.1378 / 0.883 |
| Enemy next in view, where: mean error in units | 735 (where last seen) | 522 | 509 | 516 | 510 | 509 | 510 |
| Enemy now, out of view: mean error in units | 590 (where last seen) | 444 | 375 | 384 | 383 | 382 | 378 |

Trivial: always the commonest bucket, the base rate, "he is where he was last seen". A third GRU run (51 s, another
seed, 20 passes) gave 1.682, 0.731, 1.419, 0.472, 0.1385, 512 and 384 down the rows: with the two GRU columns that is
the spread between runs of one model.

Where the enemy is now, by how long he has been out of view (mean error in units):

| Out of view for | Rows | Where last seen | Nothing remembered | GRU 6.4 s | GRU 51 s | Record, last 16 | Record, 8 + 8 |
|---|---|---|---|---|---|---|---|
| under 1 s | 89,685 | 137 | 315 | 160 | 167 | 125 | 124 |
| 1-4 s | 122,039 | 487 | 439 | 354 | 361 | 361 | 360 |
| 4-16 s | 153,515 | 799 | 479 | 451 | 460 | 476 | 475 |
| over 16 s or never seen | 72,464 | 880 | 539 | 518 | 533 | 543 | 540 |

**Maps never trained on** (Cure, Hektik, Toxicity, Campgrounds: 908,896 rows):

| Target | Trivial | Nothing remembered | GRU 6.4 s | GRU 51 s | Record, last 16 | Record, 8 + 8 | Record into GRU |
|---|---|---|---|---|---|---|---|
| Enemy next in view, when: loss / right bucket | 1.779 / 20.9% | 2.101 / 21.4% | 1.786 / 23.0% | 1.792 / 24.0% | 1.740 / 25.7% | 1.740 / 26.4% | 1.791 / 24.2% |
| Next pickup, which: loss / right | 1.388 / 24.7% | 1.973 / 37.7% | 1.432 / 40.2% | 1.529 / 40.1% | 1.187 / 47.6% | 1.196 / 49.3% | 1.237 / 47.7% |
| Next pickup, when: loss / right bucket | 1.734 / 21.9% | 2.219 / 22.3% | 1.924 / 24.5% | 1.867 / 25.7% | 1.813 / 27.9% | 1.837 / 29.9% | 1.764 / 27.7% |
| Hurt within 2 s: loss / AUC | 0.598 / 0.500 | 0.711 / 0.627 | 0.552 / 0.675 | 0.584 / 0.667 | 0.551 / 0.681 | 0.544 / 0.685 | 0.568 / 0.670 |
| Dies within 5 s: loss / AUC | 0.174 / 0.500 | 0.186 / 0.700 | 0.137 / 0.834 | 0.137 / 0.841 | 0.139 / 0.858 | 0.127 / 0.872 | 0.137 / 0.836 |
| Enemy next in view, where: mean error in units | 688 (where last seen) | 1021 | 669 | 684 | 698 | 694 | 673 |
| Enemy now, out of view: mean error in units | 556 (where last seen) | 899 | 548 | 588 | 559 | 541 | 561 |

These models know a map only by having seen its coordinates (there is no map geometry in their inputs), so on a new
map the place targets are no better than "where he was last seen", and the bucket losses are near or above the trivial
guess (the record's stay under it on all but the pickup's time). What carries over is the order: the record first.

## What carries it

The trained record read with parts hidden (demos held out; a part is masked, the model is not trained again). The
rows under a bold line are of that model:

| The record read with | Next pickup: which | when | Hurt | Dies | Enemy now (units) | Next in view: when |
|---|---|---|---|---|---|---|
| **Last 16**, whole | 0.691 | 1.377 | 0.4658 | 0.1365 | 383 | 1.680 |
| only the last 8 / 4 / 2 / 1 events | 0.741 / 0.806 / 0.878 / 0.948 | 1.402 / 1.446 / 1.504 / 1.563 | 0.467 / 0.471 / 0.480 / 0.494 | 0.138 / 0.141 / 0.146 / 0.150 | 385 / 391 / 405 / 433 | 1.684 / 1.690 / 1.702 / 1.716 |
| **8 + 8**, whole | 0.658 | 1.325 | 0.4654 | 0.1356 | 382 | 1.679 |
| only the 8 frequent | 0.947 | 1.520 | 0.474 | 0.141 | 391 | 1.697 |
| only the 8 rare | 0.735 | 1.383 | 0.504 | 0.142 | 494 | 1.720 |
| events of the last 5 s | 0.835 | 1.491 | 0.477 | 0.141 | 396 | 1.700 |
| events of the last 10 s | 0.765 | 1.444 | 0.471 | 0.138 | 387 | 1.689 |
| events of the last 20 s | 0.700 | 1.394 | 0.467 | 0.137 | 383 | 1.683 |
| events of the last 40 s | 0.661 | 1.333 | 0.466 | 0.136 | 382 | 1.680 |
| without "took mega" | 0.789 | 1.377 | 0.467 | 0.136 | 383 | 1.683 |
| without "took red armor" | 0.760 | 1.374 | 0.468 | 0.136 | 385 | 1.685 |
| without "took yellow armor" | 0.711 | 1.380 | 0.466 | 0.136 | 383 | 1.681 |
| without "enemy out" | 0.674 | 1.336 | 0.476 | 0.138 | 469 | 1.704 |
| without "enemy in" | 0.663 | 1.334 | 0.471 | 0.136 | 384 | 1.681 |
| without "fired" | 0.666 | 1.333 | 0.467 | 0.136 | 386 | 1.681 |
| without "hurt" | 0.660 | 1.327 | 0.469 | 0.136 | 383 | 1.680 |
| without green armor, health, weapon, died or spawned (each) | 0.658 to 0.662 | 1.326 to 1.331 | 0.466 | 0.136 to 0.137 | 382 to 383 | 1.679 to 1.680 |

- The fight targets and the enemy's place live in the last five to ten seconds. The item targets keep gaining out to
  forty seconds: between "the last 20 s" and "the last 40 s" lies as much as between the GRU and the 8 + 8 record.
  That is the item clocks (25 s for an armor, 35 s for the mega).
- When a pro is on his way to an item (it is his next pickup, within 16 s), his own last pickup of it was 50 s ago for
  the mega, 40 s for the red armor, 30 s for a yellow one. It is still among the last 16 events 16%, 31% and 48% of
  the time; among the last 8 rare events 78%, 84% and 89%.

## What it means for the design

1. **An event record is a workable memory.** With half the weights and no state to carry it foretells what a GRU does,
   and what it knows can be printed and switched off part by part (the table above cost a minute).
2. **Its gain is the items, and only with the list organised by rate.** That is the design's own example ("he took the
   mega 28 seconds ago"), and it is the one place where the record beat the GRU here.
3. **The GRU is not as forgetful as section 1 of the design says**, at least in this setting: trained through only 6.4
   seconds, with its state carried, it did as well as trained through 51. On the enemy's place after four seconds and
   more out of view it was the best model (451 units against 476 for the record and 479 for no memory): it keeps
   something the events as listed do not hold.
4. **For the fight, the present is enough** in these data: hurt, dying and the next sighting are foretold as well from
   the now vector alone.
5. **Whether the record adds to a GRU when fed into it was not answered.** It needs about 20 more minutes of training
   for that one model (it was at 9.51 on the held-out demos and falling 0.12 a pass; the 8 + 8 record alone ended at 9.41).

## What should change in the event list

1. **Slots by rate, not "the last 16".** Eight for the frequent kinds, eight for the rare ones (measured above). The
   rare eight then reach back 53 s at the median.
2. **Keep mega, red and yellow armor pickups; the rest of the rare kinds earned nothing here.** Green armor, the 25 and
   50 healths, weapon pickups, died and spawned changed no target by more than 0.006. They could give their slots to
   what the sets could not supply (an item heard taken, a frag, damage dealt).
3. **One event a sighting, not two.** "Enemy out" carries the enemy (382 -> 469 units without it); "enemy in" adds
   little. Merged (where he came in, where he was lost, how long, with what) they free a fifth of the frequent slots.
4. **"Fired" out of the record.** It is the commonest event (14.5 a minute, 28% of all) and adds least. "How loud he
   has been" is a number for the game token, as the design already has it. If it stays, it should carry where he
   aimed: a shot at nothing in view says where he thinks the enemy is, which may be what the GRU kept and the record
   did not (not tested).
5. **"Hurt" once a burst**, not once a second: its events add 0.004 to their own target.
6. **The item clocks may belong in the item tokens.** "When I last took it" per big item is three numbers that never
   fall out of a list. The design's item tokens already hold "when it is back as he believes"; the pickups in the
   record then only repeat it.

## What the demos cannot teach, and what the sets lack

- **The enemy while unseen is mostly in the demos**, against the "Not" row of the design's table: the server sent him
  on 64% of the rows where he was out of view (49% on Blood Run and Lost World, 80% on Aerowalk, 98% and more on
  Battleforged, Furious Heights and Sinister). "Where is he now" can be taught from demos (the added target above),
  with the caution that it is known more often when he is near.
- Not in a demo at all: the enemy's health and armor.
- Not in the sets, to be read from the raw demos if wanted: sounds, items the enemy took, damage dealt, frags, the
  score and the clock (the last two are being read out separately), the enemy's death (a dead enemy's body may count
  as "in view" here).
- **The sets hold no time stamps.** A lost frame cuts a stretch, and stretches under two seconds are dropped. On
  Battleforged, Furious Heights and Sinister that hides nearly every death (47 to 138 seen in about 150 demos each,
  against 5 to 10 a demo on the big maps), so "dies within 5 s" rests on Aerowalk, Blood Run and Lost World. With the
  frame's server time and the reason a stretch ended written into the sets, chains would be whole games.
- A demo is one player's view of one game: nothing here says what he would have done with other knowledge.

## Unsure of

- One seed and a few minutes a model; all were still improving. The GRU had 24 to 48 passes, the record 4.
- Why the server sent the unseen enemy nearly always on three maps and half the time on two I did not look into (the
  three are also the ones full of holes: another kind of recording, perhaps).
- The GRU here is not his: five steps a second, a state carried through whole chains, supervised targets.
- A respawn is taken as 2 s and a hole as 75 ms. A death is "the next stretch starts as a fresh spawn".
- "Fired" is the firing state, not shots (a rail counts once per 1.5 s).
- The split of the demos is by the words of the file names (to keep both views of a game together); a game recorded
  under two unlike names could sit on both sides.
- Whether the attention weights trained here help v16 at all is open: v16's blocks will see other tokens too.

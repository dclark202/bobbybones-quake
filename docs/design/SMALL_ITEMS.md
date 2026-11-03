# Small items as inputs, and b1.2c's decisions

*2026-11-01. The run: [b1.2c's card](../runs/b1.2/b1.2c/CARD.md). The plan it follows: [b1.2b's card](../runs/b1.2/b1.2b/CARD.md).*

## The goal

Owner, stopping b1.2b at update 20: "He needs to know where they are", "And what they are"; "he does not need to be forced to time shards and 25hp bubbles like the mega and red. But he DOES need to pick them up"; "the shards and 5hp bubbles should be 'grouped' ... just group that as 'one thing'".

Before this he had the two nearest 25/50 healths and the two nearest bubbles or shards, lumped together, as a straight line, with no way to walk. Green armor had no input of its own.

## The design

| Decision | What | Why, or the alternative |
|---|---|---|
| Places | one 25 health, 50 health or green armor, or a group of bubbles or of shards (same kind within 200 units) | the owner's grouping; the ten maps hold 7 to 12 places |
| Slots | the 8 places nearest by his way, nearest first, one attention token each | more slots cost memory; a far place can drop out until he is nearer |
| Numbers | 14 a slot, 112 in all: filled (1), what it is (5), where (3), seconds of his way (1), next step of the way (2), something there by his senses (1), what it would give him now (1) | |
| Clocks | none | the owner: these need not be timed |
| Knowledge | seen, heard taken or taken by him, by `ITEM_BELIEF`'s rule; not the truth | fairness |
| Brain | reads only its original 868 inputs | its lesson from human games has only those |
| Opening | new encoder columns at zero; tokens shut, gate -12 to 0 over two hours | |

## What is widened

A network's input size is fixed, so new inputs need new connections. `tools/items_init.py` takes a network from 868 to 980 inputs: 112 zero columns in the encoder, 8 attention tokens and their first layer, gate shut. Memory, action outputs and brain do not change.

- b1.1's widened copy is the copy that learns.
- The controls (b1.1, v0.6.0's end) are widened only to play in the same simulator. `items_init.py same` proves each gives the same actions as its original.

## Is it useful: the baseline

b1.1 widened, in self-play on Blood Run, Aerowalk and Cure, about 175 player-minutes. A chance is a place that is there, within 1 s of his way, and would give him points.

| Item | Chances | Taken |
|---|---|---|
| Green armor | 390 | 31% |
| Bubbles | 400 | 25% |
| 25 health | 461 | 20% |
| Shards | 828 | 18% |
| 50 health | 24 | 0% |

About 12 chances a player-minute, 2.7 taken. Some misses are right (in a fight), and b1.1 was not paid under the new table: this is the room to improve and the measure to read, not a forecast. Inputs give him the knowledge, not proof that he uses it.

**If pickups don't rise with the gate open, raise the small items' pay first:** a shard pays 0.01 and a bubble 0.0125, against 0.25 for a full mega.

## Alternatives not taken

| Alternative | Why not now |
|---|---|
| All places in fixed slots | lets his memory follow an item, but these are not to be timed, and it costs more memory |
| Small items as targets he can choose | a more direct pull, but a new output; it belongs with b1.3's strategy layer |
| One "best nearby item" input | a hand-built rule, of the kind being retired |

## The run's decisions (owner, 2026-11-01)

| Decision | What |
|---|---|
| Length | to 18:00 on 11-02 by default; "I may end it early" |
| Saves | one after each stage, with its optimizer: `policy_table_`, `policy_nofire_`, `policy_contact_`, `policy_nojerk_b12c.pt`; the save before each step too |
| Order | as he set for b1.2b: table, firing costs, contact freedom, jerk. Contact has a record of losing games, so it comes after the costs settle; jerk is the likeliest to shake his aim, so it is last |
| First stage | firing costs from update 60, not b1.2b's 30: at 30 the items would have about 20 minutes fully open, and their effect would mix with the firing change |
| Cost of that | an early end comes before more of the later stages: jerk begins about 15 hours in |
| Page file | raised by the owner to 40 GB: commit limit 103.4 GB, from 85.4 |

## Faults found in the prechecks (fixed before the start)

| Fault | Effect if run | Fix |
|---|---|---|
| The controls had 868 inputs and `docs/INPUTS.csv` lists 980: `tools/duel_eval.py` refuses them | every check fails and is written as 0-0; the ramp reads 0% and holds at its first step all night | `start.ps1` uses widened copies (`keep/control_*.pt`) and refuses to start if either answers differently |
| `SM_ITEMS` was not in `panel.settings()`, used by the checks, panel and self-play logger | those games give him zeros for the new inputs: a different player from the one training | taken from the save's `env_vars` |
| The last stage had no named save | no way back to its end by name | `ramp_b12c.py` keeps `policy_nojerk_b12c.pt` two saves after the last step |
| Commit memory: about 81 GB used with a four-map check, limit 85.4; a job about 1.0 GB | ten jobs at once could run Windows out and kill the run | the page file above; a temporary cap on the jobs was removed again |

**Lesson:** the dry run tested the trainer, not the watcher's own commands. A change of inputs must be run through the checks, panel and logger exactly as `start.ps1` sets them.

## Not done

A real server: `SM_ITEMS` and the plugins are not yet tried on one (the card's red team). Needed before a play test.

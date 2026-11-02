# b1.2c: b1.2b's plan, with every small health and armor item as an input

*2026-11-01 (owner, stopping b1.2b at update 20): "He needs to know where they are", "And what they are"; "This needs to go in the current run actually ... build the CORRECT way for him to get the positions and state of the hp and armors/shards. I'll review it around 7 and then we'll restart it overnight." The family: [README](../README.md). The plan otherwise: [b1.2b's card](../b1.2b/CARD.md).*

**Marks:** ✅ built and tested · ⏳ to build · 🧪 to measure · ❓ owner's decision

| | |
|---|---|
| Started from | **b1.1** (`duel_gru_b1_1a/keep/policy_b1.1.pt`) widened, with `opt_b1.1.pt`. Run `duel_gru_b1_2c` |

## What was wrong

He had only the two nearest 25/50 healths and the two nearest bubbles or shards, lumped together: a straight line, not told apart, no way to walk. Green armor had no input of its own. b1.2b paid for all of them.

## The design

(Owner, 11-01: "he does not need to be forced to time shards and 25hp bubbles like the mega and red. But he DOES need to pick them up"; "the shards and 5hp bubbles should be 'grouped' ... just group that as 'one thing'".)

**The 8 small places nearest him by his way, nearest first, one attention token each, 14 numbers each, 112 inputs.** A place is one 25 health, 50 health or green armor, or **a group of bubbles or of shards** (the same kind within 200 units). With groups the ten maps hold 7 to 12 places, so the 8 nearest cover most of a map.

| Numbers | What | How he knows it |
|---|---|---|
| 1 | the slot has a place | the map |
| 5 | **what it is:** bubbles, 25 health, 50 health, shards, green armor | the map |
| 3 | **where it is** from him, turned to his facing | the map, as a player knows it, also out of sight |
| 1 | the seconds of **his way** to it | the map |
| 2 | **the next step** of that way | the map |
| 1 | **something there** | his senses: seen, heard taken, or taken by him. Not the truth |
| 1 | **what it would give him now**: for a group, what is left of it, up to his cap (a 25 health at 100 health gives 0; bubbles fill to 200) | his own stack, and what he knows is there |

**No clocks** on these: the big items keep theirs. The state is by the same rule as the big items (`ITEM_BELIEF`): wrong on 8-9% of random-play readings, as it should be.

**How it reaches him:** new tokens only, shut at the start, opening from gate -12 to 0 over two hours; the encoder's new columns start at zero. **The brain reads only its original 868 inputs**, because its lesson from human games has only those.

**Picking them up:** this gives him the knowledge, and the table the reason. Nothing makes him detour. If small pickups (`pick_by`) don't rise, raise their pay first.

## Choices to confirm ❓

| | Built | Alternative |
|---|---|---|
| Slots | the nearest 8 | fewer or more: about 0.13 GB of commit a slot |
| Group radius | 200 units (the clusters are the same from 200 to 320) | |
| Opening | gate over 2 h with the table | a number in `make_files.py` |
| Run name | b1.2c, the next attempt | |
| Length | to 18:00 on 11-02 (owner, 11-01: "until 6pm tomorrow by default, I may end it early"): `make_files.py <minutes>` at the start | |

## The schedule

Hours from the start, at about the update time below. As b1.2b's, with the gate added.

| Update | Hours at 4.6 min | What |
|---|---|---|
| 0 | 0 | **the table** in force; **the tokens** begin to open, to 2:00 |
| 60 | 4:36 | save `policy_table_b12c.pt`; **firing costs** 0.8, 0.6, 0.4, 0.2, 0 at updates 60 to 100 (owner, 11-01: from 60, not b1.2b's 30, so the items are read alone first) |
| 120 | 9:12 | save `policy_nofire_b12c.pt`; **contact** 25, 50, 75, 100% at updates 120 to 180 |
| 200 | 15:20 | save `policy_contact_b12c.pt`; **jerk** 0.8 to 0 at updates 200 to 240, to 18:24 |
| 260 | 19:56 | save `policy_nojerk_b12c.pt` |
| to the end | to 18:00 on 11-02 | settles; the run ends itself, or the owner ends it. Every stage's save has its optimizer |

## Red team

| | |
|---|---|
| Time and card | measured at full size, 11-01: an update 4.2 min against b1.2b's 4.1; a frame of the simulator +8%; the card 9.1 GB peak, 12.2 held of 16. No real cost |
| **Commit memory** | **the one real cost.** The trainer holds 46 GB of private memory, and a check of four maps beside it left 1.0 GB of commit free (limit then 82 GB, now 85.4), with 10 GB of memory free. A job of a check, panel or logger commits about 1.0 GB (measured 11-01). The owner raised the page file to 40 GB on 11-01: limit 103.4 GB, about 15 GB free with all ten jobs at once (estimated) |
| Two new things at the start | the table and the tokens, against the owner's rule of one at a time. The tokens are shut and open slowly, the table is at once (owner) |
| More to look at | attention spent on 8 more tokens may cost him elsewhere: the gate's opening is where that shows. Win rate, aim at each step of the gate |
| Tunnel vision | he may now see more to fetch. The fighting measures are the guard |
| Slots reorder | a slot is the nearest, second nearest...: the order shifts as he moves. What it is and where it is come in the numbers, but his memory can't follow a slot. He has no way to recall where a far item is, except by having been told it when it was near |
| A server | `SM_ITEMS` and the plugins: `sim/` must reach the image (`qlbot:playaim2` does not have it), and the belief runs in `observe()`, which the plugin calls. To try on a private server before a play test ⏳ |
| Hand-built / assumed | the 14 numbers, 8 slots, 200 units, the look every 0.4 s, 2 h |
| Pay pathologies | none new from this: inputs only |

## Before the start

| Step | Where it stands |
|---|---|
| The inputs | `sim/duel_env.py` (`SM_ITEMS`, `_sm`, `_sm_update`), `duel_env_ffa.py`, `docs/INPUTS.csv` (980), `sim/attn.py` ✅ |
| Off is today's | `items_check.log`: first 868 inputs, pay, ends the same to the bit as git HEAD, new inputs zeros; on: the game the same; a table to read by eye ✅ |
| The network | `tools/items_init.py`: b1.1 widened answers as b1.1, 0 actions differ ✅ |
| The optimizer | the trainer carries it over (`--opt-small-items`), seen in the dry run: encoder and marks carried, the new layer fresh ✅ |
| Ramp | `ramp_test.log` ✅ |
| A full-size dry run on the card | 4 updates, no error, kl and clip as before; a check beside it ran; `data/sim_runs/scratch_b12c_full` ✅ |
| The checks | prechecks of 11-01 found two faults, both fixed: the controls were b1.1 and v0.6.0 of 868 inputs, which `tools/duel_eval.py` refuses (now the widened copies, `keep/control_*.pt`, proved to answer alike), and the checks, panel and logger played him with `SM_ITEMS` off (now the save's own, `tools/run/panel.py`) ✅ |
| Baseline for the measure | b1.1 widened in self-play, three maps, about 175 player-minutes: with a small place within 1 s of his way that would give him points, he takes it 18% (shards), 20% (25 health), 25% (bubbles), 31% (green), 0 of 24 (50 health) of the time: about 12 such passes a minute, 2.7 taken |
| Commit memory | page file 40 GB, limit 103.4 GB ✅ |
| The owner's review and go ✅ | 11-01: to 18:00 on 11-02, firing costs from update 60, "then start" |

Then: `python docs/runs/b1.2/b1.2c/make_files.py <minutes>`, `powershell -ExecutionPolicy Bypass -File docs\runs\b1.2\b1.2c\start.ps1`

## Changes on the fly

| Time | Change | Why |
|---|---|---|

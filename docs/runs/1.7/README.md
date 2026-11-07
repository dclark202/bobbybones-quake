# 1.7: the combat order: fighting as the head's plan, every 0.2 s, the lock overhauled

*2026-11-04 night (owner): "What I'd like to see in 1.7 is a much better way of fighting, derived from the lock being completely
overhauled. It should permit him to: chase an enemy; decide to cut the enemy off X seconds into the future; decide to hold an angle for a
rail shot; decide to spam a corridor or chokepoint; or be one of the 'go get X item' choices with it's own pathing based on where he
expects the enemy to be. And that decision happens every 0.2s, which makes him feel alive. He's getting much better but I can still tell
that I am disrupting some sort of plan he has to get items. His item timing and control is overall decent. We need to use the head to
build an equally strong sense of how to fight. The offense side." On spam: "it could be any weapon really. grenades are good when there's
a height difference, plasma is for certain corridors and tp exists, rockets can work too even lg. The point is that the head should be
able to tell him 'you gotta spam here to stop the enemy'." Earlier the same night: "Using the look ahead for where he will be, Bobby
needs to be able to decide what the right path for how to attack is. So this requires the brain and head to interact for the decision";
"I absolutely need them to be in the model." On the design below: "This otherwise largely looks right to me, except break off needs to
be part of it too. Part of offensive is knowing how to stop, it's still important"; "this is exactly the right idea and we should get to
it soon." Starts from [1.6a](../1.6/1.6a/CARD.md)'s end. **When:** after 1.5 ("I expect 1.5 will take more tinkering so it may take a
few days to get back to this") and 1.6. **The design, agreed in principle (owner, 11-04 night); its details to plan; nothing built,
nothing run.***

**Marks:** ✅ known or decided · ⏳ to build · 🧪 to measure · ❓ owner's decision

## The problem in plain words

His plan today is one of 17 targets, held 8 s. Seven are items, and his item timing and control are decent. The fight has two crude
entries: "the enemy" (go where the brain believes he is now; it ends at the first sight) and eight holding places (a place to stand,
not chosen for what it sees). In a contact the lock lets go, but the next draw mostly names an item again: the owner can feel the item
plan he breaks into. **There is no plan for a fight: his hands fight the present frame.** The enemy is 7 to 8% of his choices (1.3b,
1.4b), the holding places about 5%; the grenade launcher is in his hand 0.1% of the time, the rail 2%.

## The order: what replaces his target

At every head tick (0.2 s, five a second) he keeps his order or gives a new one: **a kind, then what it points at, then the way**.

| Kind | What it points at | The way | What the hands are told | It pays when |
|---|---|---|---|---|
| **Go get an item** (today's items) | which item | one of up to three, chosen for **where he expects the enemy along each**: around him, or through him | the way; where the enemy is expected | the item is worth it and safe enough |
| **Chase** (today's "the enemy") | the enemy where the brain believes he is now, followed as the belief moves | to him | the way; his believed place | he is near and weaker |
| **Cut off** | the place the look-ahead puts him in **X = 1, 2 or 4 s** from now, followed as the look-ahead moves | to that place | the way; that place | he gets there first: the first hit |
| **Hold an angle** | a holding place and **the lane it watches**: the look-ahead's places in its sight | to the place | the way; **the point to watch** | the enemy comes through the lane: the first shot, the rail at range |
| **Spam** | **a point on his predicted path**: a doorway, a corridor, a teleporter exit, the pros' blind-shot spots | to a spot with a line of fire | **the point to shoot**; the head's push on the fire key | damage before the fight, or the enemy held back |
| **Break off** ✅ (owner: "Part of offensive is knowing how to stop") | **a way out of the fight**: a place out of the enemy's predicted sight, a health or armor item, a teleporter, a door he can put between them | **away from where the look-ahead puts him**, out of his lines of fire | the way; where the enemy is expected (to keep him behind) | he is behind in stack or losing the fight: he lives, the enemy gets no frag, and he comes back stronger |

**His weapon follows the order** (the head's weapon scores of 1.5a, reading the order and its point): grenades over a height difference,
plasma in a corridor or at a teleporter exit, rockets at a corner, the rail for a long lane, the lightning gun close.

## How they decide together: the brain predicts, the head chooses, the hands do

| | Its part | Taught by |
|---|---|---|
| **The brain** | where the enemy is and will be: his place now and in 1, 2 and 4 s (`sim/ahead.py`), the odds over the zones now (`sim/track_z.py`), what he goes for, when he next appears, the item race. **New (S3): for each candidate point, the odds that he passes there within 1, 2 and 4 s** | the truth, in hindsight; never pay: its answer stays honest and can be checked against people's games (the owner's concern, 10-24) |
| **The map** | numbers for each candidate, worked out, not learnt: his seconds of way there, the enemy's from his believed place, the height difference, the range, a line of sight or of fire, a teleporter exit, the corridor's width, how the pros used the spot (which weapons, how often) | the map |
| **The head** | the order: a score for each kind, then for each candidate of the kind from its own state and the candidate's numbers (AlphaStar's pointer: **one scorer for every candidate, so it works on every map**, the held-out maps too), then for each way; the keep or re-decide; the push on the weapon and fire keys | pay, on its own clock (λ 0.995, its two-minute value) |
| **The hands** | move, aim and shoot, every frame, reading the order, the way and the point to watch or shoot | pay, on their clock |

The brain's answer reaches the head as numbers (no gradient back): the head's choices change what happens and the brain is re-taught on
the new play. Nothing aims for him; every number comes from his own senses (the fairness rules).

## The candidates: where an order can point

| | From | Already in the repo |
|---|---|---|
| Items | the map's items | ✅ |
| The enemy now | the brain's place now | ✅ |
| Cut-off points | the look-ahead's places at 1, 2 and 4 s, each with its spread and his own time there | ✅ the places; ⏳ the times |
| Holds and their lanes | the pros' holding places (8 a map, `sim/pro_holds/<map>.json`: their share, the pros' weapons there, how they fared), each with the lanes it sees | ✅ the places; ⏳ what each sees (traced on the map) |
| Spam points | the doorways between zones, the teleporter exits, the corridors, the pros' blind-shot spots of every weapon (`sim/pro_places/<map>_rl.json`, `_gl`, `_pg`; `PREFIRE` already ranks them by the enemy's believed way) | ✅ the pros' spots; ⏳ the doorways, exits, corridors and their numbers |
| Ways out (break off) | places out of the lines of fire from where the look-ahead puts him, health and armor items, teleporter entrances, doorways to put between them; each with his seconds of way there and the enemy's | ✅ the items, teleporters; ⏳ the rest, from the same sight tables as the holds |

## Every 0.2 s, without flicker

- **The keep choice** (1.7a) at every tick: keep the order or re-decide. Taking the lock off with nothing in its place flickered (b1.1a:
  trips 12.6 → 20 a minute, 41% head to head); here keeping is a choice of its own, learnt by pay, and its start is near today's lock.
- **Forced** only where the order ended (the item taken or gone, the enemy dead, a spawn). An arrival (at the hold, at the spam spot,
  the enemy in sight) is the keep choice's: he waits, or moves on.
- **What an order points at is a reference:** chase and cut-off follow the moving belief and look-ahead with no new order; an item, a
  hold and a spam point stay put.

## "You gotta spam here": the hands' side

- **The point to watch or shoot** as a few inputs of the hands (its direction from his view, its distance, its height), beside the way.
- **The head's push on the fire key (S6):** the head's scores added to the fire key, held from tick to tick, as its scores are added to
  his target (1.3b) and his weapon key (1.5a), at zero at the start, credited on the head's clock: a lob pays 1 to 3 s after it leaves,
  beyond the hands' 1.25 s.
- **The weapon:** the head's weapon scores read the order and the point.

## The pay

No pay for any order. Combat, item and win pay as today (the b1 rule: the table stays): an offense order pays by the damage and frags it
brings and the games it wins; a break off by the damage and the frag it denies. **No cost for firing at all** ✅ (owner, 11-04 night:
"there should be no cost for firing AT ALL"): every firing cost is zero since 1.5a, fixed at its source and refused at the start from
1.6a on ([the 1.6a card](../1.6/1.6a/CARD.md)), so a spam is judged only by what it leads to. A risk to watch: an item's pay is direct
and sure, a fight's is not; if the head's value keeps preferring items while fights would win games, that is the owner's call on the table
later, not part of 1.7.

## Will he try them? The start (S4)

The new plays start near never, and a choice that starts at never is not found by trying (the legs, 2026-10-10; the rail at range in
1.5a's E3). **Recommended: a start fitted to the pros**, AlphaStar's start from people: the 3,712 duel demos have both players' places
and shots, so each moment can be labelled in hindsight (the pro's next seconds: toward an item; toward where the enemy was; toward where
the enemy went later, a cut-off; standing at a hold facing a lane; shots at an unseen enemy, a spam), and the head's kind and pointer
scores fitted to them, small; a full level check first (the 2026-10-11 rule); then pay alone, no standing pull.

## The steps (one new thing per round)

| Attempt | What | Its start |
|---|---|---|
| [1.7a](1.7a/CARD.md) | **the lock overhauled**: the keep choice at the head's tick, arrivals with their own clock, on today's 17 targets; `KEEP_G` 0 → 1 over 80 updates | at share 0, 1.6a's end to the bit |
| 1.7b | **the order reshaped**: today's 17 written as kinds and pointers (items, chase, holds: a softmax split by kind is the same choice exactly), the ways and holds scored with the look-ahead, the point to watch to the hands, the brain's lesson per candidate (first with no gradient into the brain) | 1.7a's end to the bit; the new scores from zero |
| 1.7c | **cut off** opened | the pros' fit, a level check |
| 1.7d | **spam** opened: the spam points, the head's push on the fire key | the pros' fit, a level check |
| 1.7e | **break off** opened: the ways out | the pros' fit (the demos show when they leave a fight and where to), a level check |

**Superseded (owner, 11-05):** "Stop thinking in terms of sub runs, it's all 1.7"; "build 1.7 CORRECTLY as one branch": every step
above is in one run, 1.7a, opened by its dials ([BUILD.md](BUILD.md): how each part is built; [1.7a/CARD.md](1.7a/CARD.md): the schedule).

## AlphaStar and Pluto

| | AlphaStar | Pluto | 1.7 |
|---|---|---|---|
| The decision | the action type, then its arguments, each from a head reading what was chosen before it: units by a pointer, a point over the map | an action, then its target, four a second | a kind, then a candidate by a pointer, then the way, five a second |
| Kinds of order | StarCraft's commands: move, attack (a unit or a point), hold position; a retreat is a move away | Brood War's | item, chase, cut off, hold, spam, break off |
| Keeping an order | the game keeps it; "no new order" is a choice | the game keeps it | the keep choice |
| The opponent | in its memory; no separate prediction | a guess of the opponent (training only) | the brain's look-ahead and its odds per candidate, a lesson of its own |
| A start from people | supervised on human games, then a pull toward them | none | fitted to the pros, no standing pull |

## The equilibrium

Each play pays only where the brain predicts well enough: a cut-off if he gets there first, a hold if the enemy comes through the lane,
a spam if he must pass the point, an item if it is worth more than the fight it avoids, a break off if the fight is lost and the way out
is not watched. In self-play the other copy learns paths harder to
predict (the ways), to check angles it expects watched and to avoid shelled doorways, so the brain must predict a mixed enemy and the head
must choose among odds: toward the pros' mix of plays. Ahead in stack or time, fighting pays; behind, the items and breaking off. In the
long run he wins more because he picks his fights and how to enter them, as he picks his items now.

## Measured and judged by

| Measure | Wanted |
|---|---|
| Win rate against 1.6a's end; against b1.2d's end | level or better at each step, better at the end |
| **The offense**: each kind's share, its damage and frags a minute, who hits first, his frag share | up; every kind used where it pays |
| **Feels alive**: the time from a sound, a sight or a hit to a change of order; orders a minute | short; no flicker (trips, targets reached) |
| **Contacts on an item plan** (the owner's) | down where fighting pays (1.6a's baseline) |
| Holds: first shots from there, the rail there; spam: damage by weapon at a point, the enemy's arrival held back | up |
| Break off: deaths in the 5 s after one, frags denied, the stack he comes back with; fights he stays in while losing | deaths after a break off down; fewer lost fights fought to the end |
| Items: the mega and red armor first, stack at fights | hold |
| The brain against the truth and people's games | holds |
| The owner's play test | "does it still feel like I am breaking into an item plan?" |

## Red team (to complete per attempt)

| Part | Hand-built or assumed | The measured alternative | Watch |
|---|---|---|---|
| Five kinds, named by the owner | the owner's call | the arguments alone, kinds implicit | the kinds' shares |
| The candidates' numbers | chosen by hand | the brain's own state only | which numbers the scorer leans on |
| The holds are the pros' 8 a map | the pros' data | every point that sees the lane | rail frags from elsewhere |
| The spam points | doorways, exits, corridors, the pros' spots | the pros' spots alone | spam damage |
| The pros' fit as the start | AlphaStar's | a soft rule; zero | the level check; the kinds' shares by 40 updates |
| The head's push on the fire key | the 1.3b and 1.5a pattern | the fire key's credit moved instead | blind shots and their damage |
| The brain taught only by the truth | honest beats useful | the head's lesson into the brain | the look-ahead's error |
| The head's size (a GRU of 256) | enough for the order | 512 | its value's error, its choices' spread |
| Camping at holds and spam spots | the keep choice decides | a limit | time at a place against its frags |
| Pay pathologies (the ledger) | | | negative frags, sign flips, lopsided games |

## Decided ✅

| | |
|---|---|
| The six plays: items by a way chosen for the enemy, chase, cut off X s ahead, hold an angle, spam with any weapon, break off | owner, 11-04 night |
| Decisions every 0.2 s (the head's tick) | owner, 11-04 night |
| 1.6 the short removals run; 1.7 the lock and the fight | owner, 11-04 night |
| The lock overhauled first (1.7a), the order on top of it | 11-04 night |
| Nothing prices a hold, a wait or a shot at an unseen enemy; no cost for firing at all (since 1.5a, fixed from 1.6a) | owner, 11-04 night |
| The structural decisions below as recommended: "largely looks right ... exactly the right idea" | owner, 11-04 night; their details when planned |

## The structural decisions (agreed in principle, owner 11-04 night: "largely looks right"; S9 changed by him)

| | Decision | Recommended | The alternatives |
|---|---|---|---|
| S1 | The order's shape | **a kind, then a candidate, then the way**, replacing the 17 targets (written as kinds and pointers, the same choice exactly at the start) | more fixed targets added to the 17 |
| S2 | How an order points | **a pointer**: one scorer over candidates described by numbers: every map, the held-out maps, no per-map slots | fixed slots per map, as H1 to H8 today |
| S3 | The brain's new lesson | **the odds he passes each candidate within 1, 2, 4 s**, graded in hindsight | the zones ahead (a map-wide grid); none (the look-ahead's places only) |
| S4 | The new plays' start | **fitted to the pros** (labelled demos), a level check first | a soft hand rule; zero and exploration |
| S5 | Who scores the order | **the hands' rows stay on today's 17 choices** (the fast part, the start the same), **the new kinds and pointers are the head's alone** | the head alone everywhere (b1.3a's swap: 37%); the hands everywhere |
| S6 | "Spam here" | **the head's scores added to the fire key** (the 1.3b and 1.5a pattern) | the fire key's credit moved to the head's clock while spamming; both |
| S7 | The pay | **unchanged; no cost for firing at all** ✅ (owner) | a pay per kind (single-behaviour pays: no) |
| S8 | The steps | **one at a time** (above); ❓ the order of cut off, spam and break off | 1.7b to 1.7e in one run, in succession |
| S9 | Break off | ✅ **a kind in 1.7** (owner: "Part of offensive is knowing how to stop, it's still important") | later |
| S10 | The head's size | **as it is**, widened if its value or its choices stall | wider now |

## The attempts

| Attempt | Started from | What | State | Result |
|---|---|---|---|---|
| [1.7a](1.7a/CARD.md) | 1.6a's end (update 80) with its optimizer | the whole combat order in one run (owner, 11-05): the keep choice at the head's tick; the order (a kind, a candidate by a pointer, the way) fitted to the pros, the new kinds 4.5 times rarer at the start; the brain's pass odds; the hands reading the order's point; the fire push with half the trigger's credit; the ways (`WAYS`) next round | **Ended on the owner's word 2026-11-06 19:15 at update 246** (end: the save of update 240, `keep/policy_end_17a.pt` + `opt_end_17a.pt`): level with 1.6a's end (49.5% at update 210) after 63-64% at updates 90 to 130; the keep choice won games but flickered (trips 25 -> 81 a player-minute, reached 24% -> 8%); the order was learnt away (2.1% -> 0.02% of readings); [postmortem](1.7a/POSTMORTEM.md); started 2026-11-05 19:42 after a false start at 18:01 (its live.json refused by the trainer for 14 updates: [card](1.7a/CARD.md#the-result)). Level checks of its start against 1.6a's end: the keep choice alone 57.5%, the whole start 53.5% (`PADD` 0.3) | |

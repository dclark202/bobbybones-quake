# 1.7c: the weapon plan (a draft, to refine while 1.7b runs)

*2026-11-06 evening (owner): "we'll hold it out for 1.7c. I think we need to revisit his weapon usage and really get it to a more equal state,
he just uses LG constantly and it's not very enjoyable to play against imo. More rockets would be great, and rails too ... while it's going
why don't you have a good think about how we can follow up with 1.7c to get better weapon usage." Starts from ❓ 1.7b's end (or its best
save). **A draft: nothing decided, nothing built, nothing run.** Sources: [Cypher set against Bobby](../../../design/CYPHER.md) (B-303,
B-305), [1.5a's card](../../1.5/1.5a/CARD.md) (the weapon causes H1 to H5, the prefit 1.5b), [1.7b](../1.7b/CARD.md).*

**Marks:** ✅ known or decided · ⏳ to build · 🧪 to measure · ❓ owner's decision

## What is known

| | Bobby (1.7a's update 90, 80 self-play games) | The pros | |
|---|---|---|---|
| In hand with the enemy in view: rockets / lightning / rail | 20 / 67 / 0.9% | 41 / 32 / 14% | |
| ... by distance (under 300 / 300 to 700 / over 700), lightning | 67 / 71 / 69% | 34 / 43 / 17% | flat: a habit, not a choice |
| **Out of view (travelling)**: rockets / lightning / rail | **19 / 66 / 1%** | **57 / 9 / 12%** | the lightning gun and the rail hum and give a player away |
| **At a new sighting** (after 1 s out of view), lightning | **69%** (67 / 70 / 69% at under 300 / 300 to 700 / over 700) | | he meets the enemy with what he travels with, at any distance |
| Hits (B-303): lightning close / mid / 500 to 750; rockets; rail | 47 / 38 / 22%; 49% (direct 20%); 40 shots in 36 games | 44 / 37 / 31%; 36% (10.5%); 37% | his rockets above the pros' (but see the red team), the lightning gun level |
| The game's switch during a reload (B-302) | the simulator's rule is the game's (within two frames) | | not a cause |
| 1.5a: the head's scores added to the weapon key | the rail at range one press in 55 s of that situation; no move toward the pros | | the press is too rare a choice to be tried |
| 1.5b: the head's weapon part prefitted to the pros (push 2.5, never run) | rockets in view 24 -> 37%, lightning 61 -> 50%, 56.5% against 1.3b's end untrained; still flat by distance | | the fit helps; the form keeps it flat |
| Weapon habits in the league (1.5a on) | he scores 53 to 55% against habit seats and plain ones alike | | the habits do not punish the lightning gun |
| The trade bonus (B-306) | 0.37 a player-minute, the lightning gun's steady stream earned it best | | zero-sum from 1.7b: its effect on his weapon measured there |

**The diagnosis.** His weapon in a fight is the weapon he travels with, and he travels with the lightning gun. The pros travel on rockets and
change by the distance of the fight they expect. Cypher: "everything you do in Quake you try to predict and do up front". A weapon is a plan
made before the sighting, not a reaction after it; Bobby's choice is a key press on the present frame, and the press that would change a
plan (the rail at range, rockets before a corner) is almost never tried.

## Experiments of 2026-11-07 (owner: "I'll let you run experiments now ... I just want more fighting and varied weapons")

**Does he fight less than before? No.** From the watcher's checks (both sides, ten maps): frags a player per ten-minute game
v0.6.0 9.3, b1.2a 6.6, b1.2d 7.7, 1.3b's end 9.6, 1.6a 11.3, 1.7a's u10 11.6, 1.7b's u90 10.4; the enemy in view 15 to 18% of
the time throughout. **What changed is the weapon** (in hand with the enemy in view, rockets / rail / lightning):

| | v0.6.0 | b1.1a's end | b1.2a | b1.2d | 1.3b start → end | 1.4b | 1.6a | 1.7a u10 | 1.7b u90 |
|---|---|---|---|---|---|---|---|---|---|
| in hand in view | 18 / 26 / 43% | 29 / 14 / 35% | 27 / 8 / 46% | 39 / 6 / 39% | 36 / 5 / 42 → 30 / 4 / 51% | 24 / 2 / 63% | 21 / 1 / 66% | 24 / 1 / 65% | 19 / 1 / 70% |

The rail went over b1.1 to b1.2a (unexplained then, HISTORY b1.0a); the lightning gun took over in 1.3b's run and 1.4b.

**A push on his weapon key at play time, no training** ([exp/wpush.py](exp/wpush.py): 1.7a's u90 pushed against itself plain,
200 games, the u90 check's own settings read back and compared; `sim/test_suite.py` WeaponPush, `tools/duel_eval.py --wpush`).
"share": every press of the three raised by p x the pros' share (the 1.5a habit seats' form); "ratio": a press of weapon j gets
p x (log s_j - log s_held), the pros' shares (in view by distance, out of view their travelling hand).

| arm | record (win rate) | rockets / rail / lightning in hand in view | ... out of view | rockets' share of his frags | kills a player per 10 min, pushed / plain |
|---|---|---|---|---|---|
| plain (the other side, every arm) | | 18 to 21 / 1 / 69 to 72% | 18 to 20 / 1 / 64 to 67% | 10% | |
| share 2 | 111-89 (55.5%) | 21 / 1 / 70% | 22 / 1 / 65% | | 11.9 / 10.7 |
| share 4 | 96-104 (48.0%) | 25 / 1 / 67% | 26 / 1 / 61% | | 10.8 / 11.0 |
| ratio 0.5 | 98-102 (49.0%) | 22 / 1 / 69% | 21 / 1 / 64% | | 11.2 / 11.0 |
| ratio 1 | 100-100 (50.0%) | 24 / 1 / 67% | 24 / 1 / 60% | 14% | 11.0 / 11.2 |
| **ratio 3** | **85-115 (42.5%)** | **35 / 1 / 55%** | **38 / 1 / 47%** | **24%** | **9.8 / 11.8** |
| the pros | | 41 / 14 / 32% | 57 / 12 / 9% | | |

**Why a push moves him so little** ([exp/wkey_diag.py](exp/wkey_diag.py), 6 games of 5 min on Blood Run): at a reading of his
weapon key with the lightning gun in hand out of view he gives "press the lightning gun" (a no-op) 0.67, "keep" 0.29, "press
rockets" 0.003; with rockets in hand he presses back to the lightning gun 6 to 8% of readings. A press of another weapon is a
rare event, and a push multiplies a rare event: ratio 1 (+1.8 on rockets from the lightning gun) took it to 0.0096.

**What it says.** Up to ratio 1 the mix moves little and costs nothing (49 to 55%); at ratio 3 the mix comes halfway to the pros'
and he loses 42.5%: his hands fight worse with rockets than with the lightning gun as they are. So the lightning gun is the best
weapon *for today's hands*, which never practise rocket fights (b1.2d's hands did: 39% rockets, "the rocket fights are getting
much better", owner). The rail is two problems: owned with ammunition 33% of his time on Aerowalk and held about 1%, and never
owned on Campgrounds (0%; B-286); even ratio 3 left it at 1% (the push for it is large only in view beyond about 700 units,
where he rarely is with it). Cypher's measures under ratio 3 (`wpush/r3/cypher.jsonl`): the pushed side out-stacked dies 55% (plain 53%),
deals 327 a minute (plain 336); his items as before.

**The weapon dial for play against people** (owner, 11-07: "Build the dial for play against people and I'll play test it when it's ready. Then afterwards we'll consider 1.7c"): [DIAL.md](DIAL.md). `!weapons light`: 48.0% against himself, rockets in view 27%; `!weapons strong`: 33.5%, rockets in view 41%; the rail does not move. On the local server for his play test.

## The proposal (rough)

**The weapon plan: the head holds the weapon he should have in hand**, five times a second, and he follows it unless his hands override.

| Part | What | From |
|---|---|---|
| 1. The plan | at each head tick, a choice over the weapons he owns with ammunition: the weapon to hold; held to the next tick. The simulator switches to it when it differs from the one in hand (the game's switch time; not mid-shot of a weapon whose reload is running: the game's own rule); his hands' weapon key overrides it for the last-moment change (he jumped into close range) | AlphaStar's action type chosen first; the order's form (1.7a, 1.7b) |
| 2. What it reads | what it needs, at the rate it chooses (the rule of 11-03): the brain's look-ahead (where and when the enemy next appears, the distance and height of that place), the order (its kind and point: spam a doorway, cut him off, break off), his weapons and ammunition, the enemy's weapon seen and the hums heard, the fight odds (1.7b) | the owner's 1.7 spec: "his weapon follows the order: grenades over a height difference, plasma in a corridor or at a teleporter exit, rockets at a corner, the rail for a long lane, the lightning gun close" |
| 3. Its start | fitted to the pros: their weapon in hand by the same situation, in view (by distance, height) **and out of view** (the travel weapon, by where and when the next sighting comes): labelled from the demos as the order's fit was (`tools/order_pros.py`'s way) | 1.5b's prefit (56.5% untrained) |
| 4. A KL to that fit through the run | sized from the first updates as 1.7b's ORD_KL | AlphaStar; 1.7a's postmortem |
| 5. Credit on the head's clock | the plan judged over about 5 s (the head's two-minute value), as the weapon key's since 1.5a (`H2_WPG`) | 1.5a, B |
| 6. Opened as 1.7b's order | the plan at the fit's rate with the head frozen while the hands learn to fight with the weapon it gives them, then learnt | 1.7a's postmortem cause 1 |

**The equilibrium.** Zero-sum combat pay (1.7b): a weapon is worth only what it wins. The pros' KL keeps rockets and the rail in his hands
while the value learns where they win. Cypher says a stand-and-trade lightning fight between equals goes to the bigger stack, while rockets
from a corridor or a held angle win fights for the defender. With the weapon planned ahead of the sighting, the copy that meets the enemy
with rockets at a corner, or the rail on a long lane, wins those fights. **Watched:** the travel hand (19 / 66 / 1% now) toward the pros'
(57 / 9 / 12%); the hand by sighting distance no longer flat; frags by weapon; rail owned (Campgrounds' rail never taken, B-286); the checks.

## Open questions ❓ and things to measure first 🧪

| | |
|---|---|
| 🧪 | the pros' hand by the situation the plan reads (the labels of part 3): in view by distance and height, out of view by the next sighting's distance and time; how often they switch at a sighting |
| 🧪 | whether 1.7b's zero-sum damage alone moves his weapon (its checks' hand numbers) |
| 🧪 | **fairness, before he uses more rockets**: his rocket hits (49%, direct 20%) are above the pros' (36%, 10.5%) in self-play, where the target is another Bobby who may dodge less than a person; measure his rockets against the people on the public servers (their logs) and the stand-in before the plan makes him fire more of them (the aim's limits stay; never miss on purpose) |
| ❓ | the plan's default: follow the plan unless the hands press (recommended: the press is the rare choice today) or a sum with the hands' weapon key (1.5a's form; rule 11's regularization) |
| ❓ | "hold an angle" as an order kind (the owner's 1.7 spec: "decide to hold an angle for a rail shot"; 1.7a has holding places as targets only): in 1.7c with the plan, or after |
| ❓ | weapon combos (a rocket to lift him, the lightning gun or the rail to finish; the 1.8 card's "possibly"): from the plan's inputs (the enemy in the air), or later |

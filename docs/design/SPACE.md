# Space: whose ground it is, as a number he can read (a design for 2.0b)

*2026-11-09 (owner, after 2.0a and more pro demos): "they have this very well-defined sense of 'space' that they control, that the enemy
controls, and that is contested. For instance, there are view lines where one person may control and the other will not dare to just ambush
through without a plan"; "one person is controlling a weapon to deny the other person the ability to break in"; "some more detailed way of
estimating his 'control' of an area of the map, which is also part of his sense of 'should I take this fight'"; "He needs to be punished for
his bad decisions. He permits the other him to give up too much, basically he has no sense for the 'personal space' bubble that pros
naturally perceive, and will overextend into situations where his chance of winning the fight plummets." A first draft: nothing here is
built, measured or decided. The run: [2.0b](../runs/2.0/2.0b/CARD.md).*

**Marks:** ✅ measured or already built · 🧪 to measure before a go · ⏳ to build · ❓ owner's decision

## 1. What three runs say

| Run | What changed | What he did with it |
|---|---|---|
| 1.7b | information: the fight odds as a brain readout (Brier 0.12 against 0.21); the damage pay zero-sum | the order's kinds never moved |
| 1.7c | the weapon forced to the pros' table in training | no gain; stopped at update 62 |
| 2.0a | incentive: damage by the point down 5.5 times, the judge's stack pay up | lightning 0.64, dies out-stacked 0.549 (the start 0.552, the pros 0.299), 42% against its start |

Each changed one of three things that only work together:

1. **He cannot see space.** No input says "that corridor is his". The fight odds of 1.7b are about a fight that is already on, where he
   stands; nothing says what a fight would be worth *over there*, which is the question when a target is chosen.
2. **Nobody punishes him for ignoring it.** A sight line is dangerous only if somebody holds it. His copy holds nothing, so walking through
   is right against it, and a copy that walks into his own ground is not made to pay either.
3. **The pay has no place in it.** The judge prices lead, clock, stacks and weapons owned; two players at 150/100 each are worth the same
   wherever they stand.

## 2. The instrument: the exchange model X

One small model, fitted once on recorded games and frozen, as the judge is. It answers: **with me here and him there, with these weapons
and these stacks, who comes out ahead in the next 5 seconds?**

| | |
|---|---|
| Reads | both places (distance, height difference, line of sight between them, each one's nearest way out of the other's sight), the weapon each holds and the big three each owns, both effective stacks; a small learned part per pair of zones for what is particular to a map (`sim/zones/<map>.json`, at most 24 zones a map ✅) |
| Says | P(he dies first within 5 s), P(the enemy dies first), and the expected change in each one's stack: the same window and the same truth as 1.7b's fight odds (`FIGHT_H` 5 s ✅), now as a function of where |
| Fitted on | the pros' games (3,712 demos ✅; a pass that keeps the 5 s after each moment with both in play ⏳: `tools/pro_moments.py` keeps moments, not what follows) and his own (the frame records of `tools/run/cypher_measure.py sim` ✅: both places, stacks, weapons, damage, kills every frame) |
| The pros' aim is not his | the rail's worth along a long line is the pros' rail. The weapon part is fitted on his games and the place part on both, or his hit rates by weapon and distance go in as a known input 🧪 (decided by held-out error) |
| Judged by | Brier against the base rate and **against the same model without the places** on held-out games and on the two held-out maps: what the places add is the measure of whether "space" is in the data at all |

**The map, from X.** For a state of the game, X over every zone he could be in against where the enemy is gives each zone one of three
names: his (he comes out ahead there), the enemy's, contested. The weapon is in it by construction: a rail makes the long lines his who
holds it, rockets the corners. That is where "controlling a weapon to deny" gets a value, and where the rail gets a job without any weapon
rule. **The bubble** is the same thing seen from his seat: the zones round him where his number is still good, and the edge where it falls.

**Fair.** The pay and the measures may use the true places. He never does: his inputs are X against where *the brain believes* the enemy is
(its place readout over the zones ✅) with the stack and weapon he believes (`EN_STACK` ✅; the weapon 🧪). X itself is map knowledge, as the
pros' places are: a pro knows which spot beats which.

## 3. The owner's examples (to fill in: his words, then what X must say; an example X gets wrong is a fault in X, found before a run)

| | The situation (owner) | What a pro does | What X must read | X on the pros' games / on his 🧪 |
|---|---|---|---|---|
| 1 | **Lost World, the middle area's top level** (owner, 11-09): contested; one or both hold the lightning gun, one comes out of the two tunnels (in line with the bridges to the rockets) | does not run out of the tunnel into the open | the open middle is contested or the holder's; the tunnel mouths are the edge: the number of the one who steps out falls at the step | |
| 2 | **Blood Run, the bottom T near the mega**: one player on each leg of the T, the legs at right angles; rockets or the lightning gun | holds his leg; does not step into the crossing | each leg is its holder's; the crossing is the enemy's for whoever enters it | |
| 3 | **He overextends**: in either place, "just running right out into the open letting the enemy get a free easy shot" | stops at the corner; "a skillful chip, or tactical spam or something. NOT just running right through it" | his number falls along his own path before the fight; the entries are counted and how they end | |
| 4 | **His copy is let off**: "the other one NOT punishing him by either running away or not acting on it" | takes the free shot | an enemy stood in *his* ground in his sight: did he deal damage within the window, did the enemy leave alive | |
| 5 | **The bubble's reach**: "usually it extends to sightlines, so corridors and turns are the 'end point'" (and Cypher's points: corridors with a way out) | | the edge of his ground lies at corners and turns: X changes most across a break in the line of sight, not with distance | |
| 6 | **Contested by nature**: the rocket spawn on Lost World, the mega on Blood Run, the mega on Battleforged, the lightning gun on Hektik: "too many sightlines converging on them, or can be attacked from a place that is totally safe otherwise. Usually a weapon or item is there and the reason it is there is because the area cannot be easily held down" | takes the item and leaves; does not stand there | these zones are nobody's: whoever stands in them is behind against most of the zones that see them. **A test of X with no game state at all: these four must come out as the least holdable zones of their maps** | |
| 7 … | more from the owner's demos as he finds them | | | |

## 3b. Measured 2026-11-09 (part A's first passes; the pros: 150 demos a map, 1,157 to 1,256 games; Bobby: 1.7a's update 90, 80 games)

| Pass | What | Result |
|---|---|---|
| 1 ✅ | X by zones (`tools/run/space_fit.py`): who dies first in a decided fight, right on held-out games | the stacks and weapons alone: the pros 82.8%, Bobby 88.2%; with distance, height and sight 82.9 / 88.5%; with a part by zone 82.9 / 88.2%. **A room-sized place adds nothing to who wins, in the pros' games either.** It says only whether a fight happens. This definition is dropped |
| 2 ✅ | who held and who pushed when the two come into sight | at level stacks no difference in either (the pros 11.9 against 11.7% dead first, Bobby 15.1 against 17.2%); the differences over all stacks are the stack's (the weak hold, the strong push). He pushes at 64% of sight onsets, the pros at 47% |
| 3 ✅ | **a score a place** (`tools/run/space_score.py`; owner: "a score per place on the map of how 'bad' that is to just hang out in"): from the map alone, B = the seconds he is in sight before he can walk out of it, an enemy anywhere (pictures: `docs/design/space/<map>.png`) | the worst zones: Lost World's rockets first and its top middle second (the owner's examples); Blood Run's bottom floor by the mega third and fourth; Battleforged's mega fourth; Hektik's lightning gun not in the first six. Damage taken a minute with the enemy near rises with B (the pros 368 to 513, Bobby 268 to 439). **But the pros stand in the worst fifth as much as he does (15.3 against 15.4% of standing time)**: a place is not bad by itself |
| 4 ✅ | **the same against the enemy where he is**: the seconds to the nearest place *that enemy* does not see (`cov8[his point, my point]`) | damage taken a minute, by seconds from cover (under 0.5 / 0.5 to 1 / 1 to 2 / over 2): the pros 1011 / 1468 / 1724 / 1853, Bobby 612 / 1400 / 2054 / 2113. Of his time in the enemy's sight he is over 1 s from cover in **28.8%, the pros in 23.5%**; under 0.5 s in 27.5% against the pros' 35.6%. The measure that sets them apart is this one: **the pair of places, not the place** |

| 5 ✅ | **against where the enemy can be** within 1.5 s of walking: the share of that ground that sees him (`see8`) | with him **not in the enemy's sight now**, hit for 20 or more in the next 2 s, by that share (none / under 25% / 25 to 50 / 50 to 75 / over 75): the pros 9 / 19 / 28 / 35 / 39%, Bobby 4 / 13 / 24 / 37 / 39%. **The score says what is coming before anybody is in view**, and it needs only a place for the enemy, not a sight of him. Of all his time near the enemy he is in the worst band 12.4%, the pros 9.5%, and is hit there 63% against their 45% |
| 6 ✅ | the weapon in the enemy's hand and the distance, in his sight: damage taken a minute (under 400 / 400 to 768 / 768 to 1500 units) | the pros: rockets 2081 / 721 / 236, lightning 2699 / 2292 / 593, **rail 1501 / 1763 / 1900**. The rail's line does not shorten with distance; the others' do: "a weapon held to deny" as a table. In Bobby's games the rail is in the enemy's hand for 3 minutes of 1,281 |

| 7 ✅ | **the threat in damage** (`space_score.py edge`): the share of the enemy's reach that sees him, by the length of the line, times the weapon table (the pros' damage a second in sight for all nine weapons: `data/sim_runs/space/weapon_threat.json`, measured on half the demos, tested on the other half) | hit for 20 or more in the next 2 s by the threat on him (under 2 / 2 to 5 / 5 to 10 / 10 to 20 / over 20 damage a second): the pros 11 / 23 / 27 / 40 / 60%, Bobby 4 / 14 / 23 / 34 / 63%. **He spends 18.3% of his time near the enemy under a threat over 20; the pros 8.3%.** The clearest gap between them so far |
| 8 ✅ | **the edge** (what he puts on where the enemy is, less what the enemy puts on where he is) and **the map's cover** (the share of the map's points he covers better than the enemy by 2 damage a second, less the enemy's share); Bobby's games (the pros' demos hold no enemy stack or frags a frame) | the edge from under −10 to over 10: dealt less taken in the next 2 s −7.6 / −1.9 / −0.4 / +1.1 / +6.7. The map's cover from under −0.3 to over 0.3: frags less deaths in the next 30 s −0.50 / −0.26 / −0.02 / +0.22 / +0.40. **Beside the stack it adds little in his games** (the next 30 s explained: the stack ratio 0.286, with the cover 0.293): in his world the stack decides and the ground does not yet |

Cautions: the pros' enemy is known only while the server sends him and his damage dealt is an estimate; "near" is within 1,500 units; the
cover time ignores jumps; the weapon in a hand goes with the stack. Next passes ⏳: the cover weighted by what a place holds (the items and
their clocks) instead of every point alike; 2.0a's end beside update 90; the pros' cover from the enemy's last known place.

**How he reads it (owner, 11-09: "in real time he needs to use his belief about the enemy to judge the score of where he wants to go, or
where he hangs out or chooses to stay").** The table is a pair of places; his belief is a spread of places for the enemy (the brain's place
readout, now and 1, 2, 4 s ahead ✅). The score of a place for him is the table's mean over that spread, exactly as pass 5 takes the mean
over the enemy's reach: a sure belief gives pass 4's sharp edge at the corner, an unsure one a wider, softer bubble. Read for where he
stands (the hands), for each target and the way to it (the head), and for the enemy's exposure on the path he is expected to take (hold an
angle, spam). Cypher's "not to lose" is the low side of the same number: the long quiet stretches are both players keeping it low.

## 4. The four uses, in order (one new thing a round; two in a run open one after the other)

**Redirected 2026-11-09 (owner: "a live readout, per place, and on the aggregate ... And then pay zero sum by 'control' of different areas,
using the real map state"; "let's redirect 2.0b to go in this direction").** The instrument below is no longer X by zones (dropped: 3b,
pass 1) but the table of 3b's passes 4 to 8. 2.0b is: the readout (the cover of each zone, the aggregate, the threat on him), then the
inputs against his belief (B below), then a small zero-sum pay for the cover of the item ground: [the card](../runs/2.0/2.0b/CARD.md).
The holders (C) are held in reserve; D follows. The table below is the first draft, kept as written.

| | Use | What it is | New for him? |
|---|---|---|---|
| **A** | **The measurement** (no run) | fit X; read the examples of part 3 on it; then, on the pros' games and on his (1.7a's u90, 2.0a's end): time in his own, contested and the enemy's zones by stack ratio; entries into the enemy's zones while out-stacked and how they end; how often an enemy who enters his zones leaves alive | nothing: it decides whether B to D are built on this definition. **If it does not set the pros apart from him, the definition is wrong and nothing below is built on it** |
| **B** | **He reads it** | inputs for the hands (X where he stands; the direction of the nearest zone where it is better) and, for the head, X at every target it chooses among (the chooser reads what its choice needs, at its rate: the AlphaStar rule of 11-03). Opened from zero weight through a gate | a new input group; no new output, no new sum of learned outputs (rule 11: X is frozen and enters as inputs) |
| **C** | **Seats that punish** | a share of the league's lives are *holders*: his own copy with its own hands and aim, whose target is set by X instead of its head: the zone that covers the learner's believed way with the best number, held until he comes or the item it guards is gone. And the reverse lesson is already in the pay: an enemy who dies in his zone is a frag. AlphaStar's exploiters are the model (a seat whose job is to find the main agent's hole); ours is built from X because a learned exploiter costs a second trainer on one PC | opponents only; nothing in him is scripted |
| **D** | **The pay knows where** | the judge looks 5 s ahead through X: the potential is the judge on the stacks X expects, not on the stacks now. Stepping into a held line costs at the step, not at the death 5 s later. Still a potential: zero-sum, cannot be pumped, does not change the best play (PLAN_2's 2.0c, with X as its positional part) | a pay change: its own round |

After these: the break off and the order again (1.7b's parts) and drills that start in a losing fight (leaving a lightning gun is a skill
he has never practised: starts drawn from the pros' moments where the weaker player got away ⏳).

**Why B before D.** A potential moves credit to the frame of the decision, but his critic already explains most of the pay (EV 0.88): what he
lacks at that frame is not the blame, it is another thing to do that he can tell apart. B gives the head a different number on each target;
C makes the wrong one cost a frag in the game itself. D is then the pay agreeing with both.

## 5. The equilibrium (the standing rule)

Self-play with B and C: the player with the stack and the weapon holds the zones that cover the next spawn, because an entry there is a frag
for him; the other stays outside the edge, takes what lies outside it (the yellows, a weapon), chips from a zone that has a way out, and
comes in when the number says so (the holder left, the stack changed, a second way in). Fights happen at edges and many end with nobody
dead. On the way: fewer deaths on entering held ground, the leader's share of the next spawns up, fights nobody finishes up, frags a
match-minute down at first. It wins more in the long run if X is right about where fights are won, which part A measures first; if X is
wrong he learns to respect lines that do not matter, and the control (1.7a's u90, which respects nothing) beats him: the checks say so.

## 6. Red team

| Part | Hand-built or assumed | The measured alternative | Watch |
|---|---|---|---|
| X's features (distance, sight, ways out) | chosen by hand | the per-pair learned part alone, where the data carry it; held-out maps say which generalises | Brier with and without each group |
| "Space" is in his own games | probably not: his copy holds nothing, so on his games the places may add nothing to the stacks | the pros' games carry it; the two fits are reported apart | what the places add, pros against him |
| The pros' aim and weapons in X | see part 2 | his hit rates as an input | X's rail lines on his games: predicted against what happened |
| The enemy in the pros' demos | sent only while near or in view; his stack worked out, not read (`est` 1) | none: fights need sight; the stack's error is the judge rows' error | rows by `est` |
| A readout learnt and not used (1.7b) | B alone may repeat it | C in the same run, after B is open | the head's choices by X at the target chosen |
| The holders | a scripted target on a learned body: a hand-built opponent, and he may learn *the holder*, not the game | holders are a share of lives, the league and the control stay; PFSP (✅ built, off since 1.4b) sets the share by how he does against them | win rate by kind of seat; the control |
| Passivity | both copies respect each other's edge and nobody comes | the flat frag, the items' points, the holders leave when the item is gone | frags a match-minute under 1.5; nobody-dead fights over 75% |
| Camping | he holds a zone and gives up the rest | nothing pays the zone itself (B-280's pathology is a pay; B is an input) | items taken, by kind |
| The 5 s window | assumed from 1.7b | 3 and 8 s fitted beside it in part A | the examples of part 3 by window |
| The servers | the plugins never call `step()`: X's inputs must be kept there too | recorded on a private server beside the simulator's before any deploy | `OBSDUMP` |
| Pay pathologies (D only) | | | negative frags, sign flips, lopsided games |

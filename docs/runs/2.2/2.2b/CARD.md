# 2.2b: a fight network beside the item picker

**Status (2026-11-17): built, reviewed and started on the owner's go ("Have a subagent build it and validate it. Then start it when it's ready"). The build's record: [BUILD.md](BUILD.md). The first start failed (the gauntlet; RUNS #59); restarted with three changes: "The restart (11-17 evening)" below (RUNS #60).**

## The owner's page

| | |
|---|---|
| Started from | **2.2a's save of update 90** (`data/sim_runs/duel_gru_2_2a/keep/policy_90.pt`): the best record after 2.2a stopped doing anything new, 125-75 (62.5%) against 2.1d's end. A 200-game check moves about ±7 points: the best pick, not a proven one. Its optimizer was not kept (the nearest: updates 60 and 100), so the run starts with a warm-up |
| The aim | When to be aggressive, when to collect, and how to fight become decisions with their own network, their own pay and the information a fight decision needs |
| The owner's words | "Choosing whether to fight or not and how is literally the core of the game, so it makes sense it should be its own dedicated network." "We do not necessarily need the fight network to take over, we just need it to inform when to be aggressive and when to be passive/collect items. It should not act as a lock, but it should allow him to be aggressive when it pays off." "'Fight while going to this item' is a total possibility" |
| The two ideas | (1) **The item picker scores the items; a new fight network scores four fight options; both go into one list** and the highest score is where he goes. No switch between "item mode" and "fight mode". (2) **The hands practise the fight options before the fight network's scores count**: in 1.7a they were judged while the hands could not carry them out, and his choice of them fell from 2% to 0.02% |
| What comes out | The part that rated his options in 2.2a (all four versions) and its on/off test. "The enemy" and "the places" as options of the item picker (shut in both of its halves: the hands' scores and its own). The item picker's push on his weapon |
| What stays from 2.2a | The background predictions: the enemy's health and armor as a range, the odds of a fight, either player dying within 5 and 10 s, contact within 2 and 5 s, who is in control, where the enemy will be in 1, 2 and 4 s |
| Also in this run, on the owner's word | **A small pay for a near miss with a projectile** (change 13). "He's actually *too* timid currently, with projectiles specifically. The thing about good quake players is that they 'seem to be everywhere' because they're constantly shooting out projectiles to keep you penned into a specific spot. He doesn't have that at all currently. We should start him back in that direction ASAP" |
| Not in this run | Firing at a spot he cannot see (2.2c; its design is in [../DESIGN.md](../DESIGN.md)) |
| Control | 2.2a's update 90 in the league and in every check; every fourth check against 2.1d's end |
| Length | **A 24-hour limit, started when it is built and tested** (owner, 11-17: "We will start it when it's ready, set the deadline for 24hrs but it likely will not go that long ... I'll review in the morning and decide on a stop point") |

## The structure after this run

| Part | Its question | Reads | Gives | Paid by |
|---|---|---|---|---|
| **The belief** (as now) | What is true about the enemy? | What he sees and hears | Predictions: where the enemy is and will be, his stack, the odds of a fight | Being right |
| **The item picker** (the decider we have, narrowed) | Which item is worth going for? | The belief, his stack, the item timers, score, clock | A score for every item (**all items stay**: big items, weapons, yellow armor, health) and for "nothing" | **Items and the change in his chance of winning. No damage, no frags** |
| **The fight network** (new) | How much is a fight worth now, and which kind? | Below | A score for each of four fight options; a nudge on the weapon; its eagerness, told to the hands | **Damage dealt and taken, far rails, frags and deaths, and the change in his chance of winning. No item pay** |
| **The hands** (as now) | How do I do it this instant? | Everything he senses, where he is headed, how eager the fight network is | Aim, trigger, dodging, the weapon in hand; he always drives himself: nothing else moves him | All of his pay, as now |
| **The way's suggestion** (a part of his own network, as now) | | The place he is headed for and the point to look at | Suggests the keys that walk the way there. **It does not move him**: since v0.3.5 his own network always drives (corrected 11-17: an earlier version of this card called it a separate walker) | Learns with the rest |

**One list, no switch.** Every 0.2 s each item has a score from the item picker and each fight option has a score from the fight
network. He heads for whichever is highest. A mega three seconds out can outscore a chase; a weak enemy nearby can outscore a far
yellow armor. Aggression is the fight network's scores being high, not a mode he is put in.

**Fighting on the way to an item is the default.** Whatever he is headed for, the hands shoot and dodge when they see the enemy, and
they are told how eager the fight network is, so they can press a fight on the way or slip past it. Nothing holds him to a spot.

## The fight network

**Its four fight options** (each is a place on the map he heads for, as an item is):

| Option | What going there means | Where it comes from |
|---|---|---|
| At him | Chase, or stay on him | Where he believes the enemy is (today's "enemy" option) |
| Where he will be | Cut him off | The place he is most likely to pass in 2 or 4 seconds (the prediction trained in 2.2a) |
| An angle on his path | Hold: stand where you see the spot he must pass, and watch it | Of the map's standing places, one that sees that spot and that he reaches first |
| Away | Break off | A way out, or a health or armor item he can reach unseen |

**What it reads:**
- the belief's memory and every prediction made from it;
- his own stack, weapons and ammunition, the item timers, the score and the clock;
- **the item picker's scores for every item and its memory**: what the item plan wants, how badly, and why;
- the hands' memory (how the fight of the last seconds has gone);
- for each fight option: how long the way there is for him and for the enemy, and what the spot sees;
- where he is headed now and for how long.

It has no memory of its own to start with: it reads three. Nothing it reads is changed by its learning.

**How a destination is held.** As since 2.1c, for the whole list: each option gets a score every tick; a set of dice is rolled once
when he sets off and kept until that trip ends; the highest total wins. A rival needs real news to overtake. No timer, no lock. The
item picker's slow plan (2.1d) keeps steadying the items; the fight network sees where he is headed and for how long.

**The weapon to bring.** A score for each weapon, **added to the hands' own weapon scores**. Sized for when he has nobody to shoot
at; in a fight the hands' own scores are far larger and decide.

**It never touches the trigger.** That is 2.2c.

## The restart (11-17 evening)

**What failed.** The first start (RUNS #59, 17:56 to 19:56) was stopped by the owner after 18 updates. From update 8 he held the gauntlet
more and more (under 1% of his time in games through update 7, then 14%, 25%, and a third of the time from update 12), and the check at
update 10 lost 0-200 to the start. The agreed cause: for its first 10 updates the item picker's choice lesson was switched off while the
rest of it kept learning to forecast its new pay. Nothing held what it put out: its memory drifted, its push on his weapon grew (its size
3.1 → 5.5) and his weapon choice moved 4 to 23 times faster than normal (KL 0.06 to 0.35 against 0.015) until he walked around with the
gauntlet. That start's folder is kept as `data/sim_runs/duel_gru_2_2b_failed_1117`; nothing from it is used.

**The three changes (the owner's decisions; everything else of this card unchanged):**

1. **The item picker is frozen for its first 10 updates**, except the last layer of its forecast (the one layer that reads its memory and
   says what the next seconds are worth): that layer relearns the new pay; nothing else of it moves at all (its memory, its scores for the
   items, its slow plan, its weapon scores, the tracker stored inside it). Its choice lesson stays off in that window. From update 11 it
   learns as designed. The trainer proves it every update: the largest difference of every frozen weight from the start must be exactly 0.
2. **The item picker's push on his weapon leaves at the start.** It fades 1 → 0 over updates 0 to 10 (in the first plan: 60 to 100) and
   is 0 for the rest of the run; its weapon scores never learn in this run. The fight network's weapon nudge still comes in over 60 to 100
   as planned: between update 10 and update 60 his weapon is the hands' choice alone.
3. **Two alarms**, each a MAJOR line in `watch/watch.log` every update from update 1: the gauntlet in his hand more than 5% of the time,
   and his weapon choice moving faster than 0.045 (three times its normal speed). Replayed over the failed start, they would have fired at
   update 5 (the speed) and update 9 (the gauntlet).

**The stage table, corrected:** in stage 1 (updates 0 to 60) the item picker's weapon push leaves over updates 0 to 10; stage 2 (60 to
100) no longer has it (the fight options enter his list; "the enemy" and "the places" leave the item picker; the fight network's weapon
nudge opens).

## The changes

| # | Change | Detail |
|---|---|---|
| 1 | **The rater of options is removed** | Its networks, lessons, random goals and on/off test. An update should fall from about 6.6 minutes back toward 2.1d's 5.3 |
| 2 | **The fight network is added** | As above. Until update 60 its scores are not in his list; it picks half of the practice trips |
| 3 | **The fight options are switched on in the simulator** | Built in 1.7, off since. Cut-off moves to the prediction that works (the 1.7 version used one that is dead on this line). The angle with a look point is new. Break off as fixed in 1.7b |
| 4 | **The hands are told where he is headed and how eager the fight network is** | New inputs: the kind of spot, where it and its look point are, how long he has been headed there, the fight network's four scores. Added with their measured average and spread, starting with no effect, opened over updates 0 to 20 |
| 5 | **Practice** | At a new decision, with a set chance, he is sent on one of the four fight options that is possible at that moment, with a weapon he owns (each equally likely). **Half of these are dealt at random** (each option equally likely), so every option keeps being tried; **the other half are picked by the fight network itself** from its own four scores, which start equal. That half is what keeps its scores honest before update 60: there is no tie to starting amounts. **The destination is kept** until the spot, contact, or 4 seconds; he still drives himself the whole way. Practice only, never a choice of his own. The chance: 0 → 12% over updates 0 to 20, held to 60, then 5% to the end. A practice trip counts as the fight network's own exploration, so its scores learn from every one and no fight option can fall to nothing in training |
| 6 | **Both players get practice** | Each also learns what it costs to be cut off, to walk into a held angle, to chase someone who leaves |
| 7 | **Fight starts** | A fifth of all rounds start just after a frag: one player with the stack and weapons of a real moment, the other fresh. Taken from the rounds that start at a pro game's moment (35% → 15%); whole games stay at 65% |
| 8 | **The pay is split** | The item picker: items and the change in his chance of winning. The fight network: damage, far rails, frags, deaths, and the change in his chance of winning. The hands: unchanged. For its first 10 updates the item picker only relearns its forecast under the new pay; its scores are not taught until then |
| 8b | **The chance of winning is read by the judge that sees the items and stacks** | For every part paid by it (the hands, the item picker, the fight network): one judge everywhere. Refitted on 100 new games of the start and accepted by its test before a start; the ledger's check (negative frags, sign flips) is run with it as the pay. In 2.2a this judge only fed a side forecast while the pay kept the older one; that is ended here (owner, 11-16 and 11-17) |
| 9 | **The chance of winning is scaled up for both** | For the item picker and for the fight network, the win-chance part is scaled to **at least the size of their flat pay** (items for one; damage and frags for the other), measured on the start's games, logged every update, flagged if it falls below. The fight network keeps two forecasts, one for damage and frags, one for the chance of winning, each brought to the same size before they are added. It is also what makes the two networks' scores comparable in one list: the chance of winning is their common currency |
| 10 | **The fight options enter his list, slowly** | Updates 60 to 100: the share of his decisions at which the fight options are in the list goes 0 → 1. Over the same updates "the enemy" and "the places" are shut in both halves of the item picker, while the fight network's weapon nudge opens (the item picker's weapon push: gone by update 10 since the restart). **One number is set by hand here**: the four fight options' total share at update 60 starts at what "the enemy" and "the places" hold together at that moment (they are what leaves the list), so his play does not jump. How that total is split among the four comes from what the fight network has learnt by then |
| 11 | **It opens whatever the numbers say; they are reported, not obeyed** | A ramp never holds on its own. At update 60 the report says in plain words whether the hands carry the fight options out and how much practice each has had. If not enough, it is flagged at once and you decide |
| 12 | **Reports in plain words** | Every report opens with what is playing now and whether the run is on this card's plan |

**Change 13: the near-miss pay (owner, 11-17).**

| | |
|---|---|
| What is paid | A rocket, grenade or plasma ball that deals no damage but bursts near the enemy pays a little, **more the closer it was**: the full amount at the edge of its splash, falling in a straight line to nothing at the outer distance. Whether he saw the enemy or not |
| Why | A shot that hits 1 time in 10 is a weak lesson: nine misses teach nothing. This gives a signal on most shots. He was also trained for many generations with a cost on firing "at nonsense" (off since 1.4c); the habit was never unlearnt |
| How much | Far below a hit: the best near miss pays about what 5 points of damage pay. A live dial, 0 → full over updates 0 to 20 |
| The outer distance | About 300 units from the enemy (roughly a second of running). Set by me; a live dial |
| Zero-sum | The enemy is charged what the shooter is paid. Without this, two copies could stand apart and lob near misses at each other for profit; with it, the one being shelled has his own reason to move, which is what being penned in is |
| A cap | At most one full near miss a second for each player, so a stream of plasma cannot farm it |
| Who learns from it | The hands (they fire) and the fight network (with its damage part). Not the item picker |
| What it is kept out of | His own "damage dealt" inputs and counters: they stay true damage. No cost on firing anywhere (the standing word) |
| What is watched | Damage a minute, and projectiles fired a minute in view and out of view, hits and near misses beside them. **Readouts only**: no firing rate or hit rate is a target (rule 12), and a low hit rate is not a fault |

## Regularization

| Where | What | Why |
|---|---|---|
| **The fight network's scores before update 60: no tie; it plays a little from the start** | Half of the practice trips are picked by the fight network itself (change 5). A score that climbs too high gets picked more, shows its results and comes back down | The first design tied its shares to starting amounts (6%, 10%, near zero). The owner did not trust the amounts (11-17), and the tie would have held down the two new options, cut-off and back off, that the run is for |
| The fight network's last layer | Decay; the spread of its scores logged, flagged over 40 | The kept dice have a fixed size: if the scores grow large the dice stop mattering, if they shrink he picks at random |
| The fight network's first layer | Decay | It reads over a thousand numbers from three memories that keep changing as those networks learn; 2.0b fell apart on fast-moving inputs into a decider |
| The one list (two networks' scores side by side) | Decay on both, both sizes logged and flagged over 40; the common win-chance scale of change 9 | Two learners with different pay in one choice |
| The weapon: the hands' scores plus the fight network's | Decay on both, sizes logged, flagged over 40 (rule 11) | A sum of two learned outputs |
| The items: the hands' scores plus the item picker's plus the plan's boost | As since 1.3b and 2.1d | Unchanged |
| The hands' new inputs | Opened over 20 updates; their weights' size logged, flagged over 40 | New inputs into a trained network |
| No bonus for spreading his choice over the fight options | Left out on purpose | That bonus spreads a choice over new options whatever they pay; the 5% practice floor does the exploring |

## The stages

| Stage | Updates | What plays | What to look at |
|---|---|---|---|
| 1. Practice | 0 to 60 | His choices as now; practice up to 12 in 100 decisions. **(The restart) Updates 0 to 10: the item picker frozen but for its forecast's last layer; its weapon push 1 → 0**. The fight network learns and picks half of the practice trips; its scores are not yet in his list | On practice trips: does he get there or meet the enemy; damage dealt against damage taken on each kind; does he fire when the enemy walks into a held angle; which weapon he ends up holding. Frags and damage a minute; projectiles fired a minute, in view and out, with hits and near misses. Three checks |
| 2. The fight options enter his list | 60 to 100 | Their share 0 → 1; the enemy and the places leave the item picker (its weapon push left over updates 0 to 10: the restart); the fight network's weapon nudge opens | How often he heads for each fight option and when (ahead, behind, just after a frag, an item due); the weapon out of fights; the checks |
| 3. Hold | 100 to the end | The full structure; practice 5 in 100 | The checks; a play test |

**The hands carry a fight option out** means, over ten updates: on at least half of the practice trips he reaches the spot or meets the
enemy; and on them he deals at least as much damage for the damage he takes as on his own choices. Practice comes at random
moments, so the comparison is fair (in 1.7a it was not). If the hands overrule a kind every time (most likely "away", with the enemy
in view and damage to be had), that is reported as it is: nothing is added to hold him.

## What it passes on

- Checks at least level with the start.
- At the end, without practice, he heads for a fight option in more than 10 of 100 decisions, and differently when ahead and when behind.
- In a play test: he cuts you off, holds an angle on you, leaves a fight he is losing, and has the rail out when he waits.

## Red team: what is set by hand or assumed

| Part | Set by | The risk | The measured alternative |
|---|---|---|---|
| The pay split | The owner | The item picker's forecast must be relearnt | Its warm-up; both networks' forecast errors logged every update |
| Frags and deaths to the fight network only | Me (the owner named damage and far rails) | The item picker feels a death only through the chance of winning | None; say if you want deaths in the item picker's pay |
| Two networks' scores in one list | The design | If their scales drift apart, one side always wins the list | The common win-chance scale; both sizes logged; the share of decisions each side wins, every update |
| The practice chance (12%, then 5%) | Me | Too high: sent to chase while weak 1 decision in 8. Too low: each fight option is seen about 3 times in 100 decisions, which may be too thin by update 60 | 2.2a ran random goals at 3% with no fall in the checks; the update-60 report says how much practice each has had |
| Keeping a practice destination up to 4 s | Me; approved | The one thing that resembles the lock. Never touches his own choices; the hands can still take over | None |
| Where each fight option is | A rule from the predictions and the map's tables | A bad rule teaches a bad play | Logged per kind: how often the enemy did pass the spot |
| The fight options' total share at update 60 | From what "the enemy" and "the places" hold then | Too high or too low a start for options that behave differently from those two | The check at update 70; it is learnt from there on |
| Everything of stage 2 opens together | Left so (owner: "oh well") | If a check falls in updates 60 to 100, the cause cannot be pinned on one of: the fight options, the options shut in the item picker, the weapon hand-over | None |
| No memory in the fight network | Me | It may not follow a fight's course from what it reads | Its forecast error; a memory is added if it lags |
| Fight starts at 20% of rounds | Me | Fewer starts from pro games' moments | None |
| The near-miss pay: its size, its outer distance, its cap | Me, on the owner's word for the pay itself | He comes to like near misses for their own sake and aims beside the enemy; or the charge on the enemy makes him over-fear shells that cannot hurt him | A hit pays about twenty times a near miss; damage a minute must not fall as projectiles a minute rise; both are live dials |
| He walks to a fight option when it is his destination | Assumed: he does for an item and for the hunted enemy, by the same way inputs | If not, stage 1 has to teach the walking as well, and may be too short | The build's first test: arrival and contact on dealt practice trips, per option |

**The ledger's check:** the win chance now comes from the judge that reads the items (change 8b). Beyond that no pay amount changes except the win-chance scale (change 9) and the near-miss pay (change 13, zero-sum, so it adds nothing to the two players' total); which network learns from which part changes.
The scaled win part is checked for sign flips and negative frags on the start's games before a start. Lopsided games are expected in
the fight starts, by design.

**What I think is weakest:** the fight options have to win more than walking to the next item does. If they do not, their scores stay
low, and that is a true answer about them.

## The equilibrium in self-play

Two copies who can both cut off, hold and break off: the player ahead goes for fights at places the other must pass; the player
behind leaves fights he is losing and waits at an angle on the item the other must take. Running blindly at a held angle starts to
cost: the price a position has lacked in every run so far. The item picker, no longer paid for damage, scores items for the stack and
the win, not for the fights near them. With the chance of winning scaled up for both, each is pulled toward what wins the game over
what pays at once. The near-miss pay, charged to the one shelled: each fires projectiles where the other is about to be, and each
keeps out of where they land. Neither gains from it on average; what it changes is that shots at a place get fired at all and that
being shelled moves a player, until true chip damage carries both by itself.

## From AlphaStar

One scorer per kind of option, their scores compared in one choice. AlphaStar's tie to a starting behaviour was considered for the
fight network and dropped (see Regularization). Different from AlphaStar: a fight option is worked out from the predictions by a rule, not pointed at by a
network, because 1.7a's pointer added a moving part to every choice; and nothing is tied to human play (rule 12).

## Research check

1. **The game**: movement, sight and the weapon in hand; no damage or item rule is touched. The fight starts use the measured spawn rule (DUEL_STRATEGY 1.7).
2. **What wins**: principle 1 (the stack decides most fights before they start: go at him and cut off when ahead, away when behind); 6 (out of control: damage at his pickups and leave); 7 ("weapon by range and stack"); 12 (a position needs a way out); 15 (avoid damage as much as you deal it). "Don't chase away from the timing" is why the items and the fight options are compared in one list, with the item timers read by both.
3. **The player's view**: every spot comes from his belief, never the truth. "What do I want, what does he want, what is the best counter" (1.12).
4. **In and out of control**: going at him and cutting off are the controller's; the angle and away are the out-of-control core (1.5). The exploit to watch: camping on an item's place under the name of holding an angle.
5. **Self-play**: "strategic moves only pay if the opponent punishes their absence" (5.3): the reason both players get practice.
6. **Bot precedent**: "no system put an untrained strategy layer over trained hands" (BOTS section 0); a value per pay part (BOTS 13.5): the pay split and the fight network's two forecasts; "one high-variance pay part can stop the value from being learned" (OpenAI Five): the win-chance scale; pivotal-moment scenarios with fixed shares (13.6); our own 1.7a postmortem ("open the hands' token before the order's share").
7. **Rule 12**: no pro outcome is a target. 1.7's fit of the plays to the pros is not used. The near-miss pay names no firing rate, hit rate or place of the pros.
8. **The near-miss pay**: "spam is one of the primary sources of damage"; rockets and grenades at doorways, corners and item spots; projectiles "also throw off the opponent's aim" (DUEL_STRATEGY 1.10); principle 13 ("spam is damage"). The owner, 11-17: chip and zoning damage from low-success shots is how most damage is done; "most people hit maybe 1 in 10 grenades, that doesn't mean they're useless." The splash sizes are read from MECHANICS in the build.

## Odds

- The hands learn to carry the fight options out: about 65%.
- He then heads for them often enough to see in a play test: about 50%.
- The checks stay level with the start: about 65% (the pay split, the win-chance scale and stage 2 are all new).

## Open, said plainly

- A server cannot play this network until the fight options, the predictions and the fight network are in the game image.
- From 2.2a, unexplained, to be traced in the build before a start: the trainer's consistency check that failed once at update 153, and whether it shows at update 90.

## Built and tested (2026-11-17; the full record is [BUILD.md](BUILD.md))

Built by an Opus 5.5 worker on branch `b22b`, reviewed by the planning session, sent back for one fix round, merged.

| Test | Result |
|---|---|
| The start against 2.2a's update 90, every new dial at zero | 0 of 1,075,200 actions differ |
| The simulator with every new switch off | Identical on fixed-seed replays |
| Does he go to each fight option when it is dealt (the start network, four maps) | Reached the place or met the enemy: go at him 0.78, cut him off 0.91, hold an angle 0.91, back off 0.945 |
| An angle practice trip | 408 of 579 arrived and held about 2 s each; on 55% of those the enemy came into view while he held |
| The judge that reads the items, refitted on 100 new games of the start | Accepted (held-out gain, all folds); it is the pay for every part. The guard refuses any new run without it |
| The win-chance part against each decider's flat pay | 2.1 to 7.0 times larger: no scaling was needed |
| Frags with no win-chance gain (7 of 454) | Traced: frags in games already decided, a frag and a suicide in one frame, a frag bought with a big loss of his own stack. The judge behaving as it should; no fault |
| The command's values against the values that play | All 53 names equal; the start refuses otherwise |
| Four updates at full size, the carried optimizer | No part off, no non-finite number; the choices move calmly (weapon KL 0.002 to 0.012); the graphics card 14.2 of 16 GB |
| Unit, live-file and guard tests; the small run through every stage with a restart | All passed |

**Different from this card, as built:**

- **The start carries 2.2a's update-100 optimizer**, not a cold one: cold, the weapon choice moved twenty times faster than usual in the second update.
- **An update takes about 6.0 minutes** (2.2a: 6.6; 2.1d: 5.4). Update 60 comes about 6 hours in, update 100 about 10 hours in.
- **Practice is 7.6 in 100 decisions, not 12.** Each of the four kinds is attempted equally often, but go at him, cut him off and the angle can only be dealt with the enemy out of sight, so about half of those attempts deal nothing. Of the trips dealt, back off is 42% and the other three about 19% each. (The first build dealt back off ten times as often as each other kind; that was sent back.)
- **The weapon nudge learns only from practice trips**, where the weapon was dealt at random. On his own choices the weapon is the hands' pick, and learning the nudge from that would copy the hands.
- **Cut-off chooses among 16 places a map** (eight standing places and eight choke points), the one the prediction says he is most likely to pass.
- **The hands' old input "headed for the enemy" is on for all four fight options**, back off included. The new inputs that say which option he is on open over updates 0 to 20.
- The part that read the map for the rater left with it.
- No server can play this network: the export refuses it.


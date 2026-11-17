# 2.2: he values a play before he chooses it (the suite's framework; owner, 2026-11-16 evening: "this plan for 2.2 makes sense"; 2.2a first; no run carded yet)

> **Superseded in part on 2026-11-17.** 2.2a failed at its purpose: the part that rated his options (the outlook) never switched on and
> is not rebuilt (owner: "every 'judge' has sucked"). The suite now runs on a different structure, decided in the chat of 11-17: an
> **item picker** (items only) under a **fight network** (fight or not, and how), with the hands practising the plays first. The current
> design is [2.2b's card](2.2b/CARD.md); 2.2c is the section "2.2c: firing at a spot he cannot see" below. The three-jobs table, the
> steps table and the odds on this page are kept as the record of 11-16.

Blends [2.1f's card](../2.1/2.1f/CARD.md) (the outlook) and [the 2.2 proposal](README.md) (new plays on trial trips) into one suite
(owner, 11-16: 2.1 is done, the lock is out; 2.1f moves here; start from 2.1d's end). The critical review behind the 2.2 proposal is
[REVIEW_2026-11-16.md](REVIEW_2026-11-16.md). Where this page differs from those two, the difference is marked **changed**.

## The goal (the owner's)

His choices grow from "go to one of 17 targets" to the plays of a duel: spam a spot, hold for a rail, attack by chasing or cutting
off (where and when), break off. The head ends up directing weapon use away from a fight (what to bring, when to fire at a place);
the hands own everything reactive, in view or not. Running answers to "am I in control" and "will I win this fight" feed the head.

## Where it starts

2.1d's end (update 158). Every 0.2 s the head scores 17 targets (nothing, the items, **the enemy**, a holding place): the hands' rows
+ the head's scores + the pull. The held draw keeps a goal for a trip. No lock.

## Three jobs, three learners (the owner's "several small networks", made concrete)

| Job | The question | What it is | Learns from | State today |
|---|---|---|---|---|
| **The tracker** | what is true, and how will things go as I am playing: am I in control, will I win this fight, where is he | the brain's readouts | hindsight (what happened), its own optimizer, no pay | in control: on, read by the head. Fight odds: built in 1.7b, **not on** in 2.1d's line. Win chance: learning in shadow |
| **The outlook** | what follows **if I commit to this play** | one value per play (and a few facts beside it) | his own held trips: the pay until he lets go of the play + the head's value of where that leaves him | built on branch `b21f`, never run |
| **The chooser** | which play, now | the head as it is: scores, the pull, the held draw | his pay (PPO), as now | 2.1d |

The tracker says how it is going; the outlook says what each choice would change; the chooser decides. The loop the owner asked for:
tracker → the chooser's inputs; the chooser's goal → what the outlook is asked about; the outlook → the chooser's scores.

**Decided (owner, 11-16 evening): three jobs, no new memory.** "The outlook needs no memory, and the tracker is basically a build
on to the brain ... those questions are really answered better by the brain." The outlook is plain layers on the head's state (the
head's memory already is the situation as he remembers it; a memory on a memory is 2.1e again). The tracker is a set of readouts on
the brain, whose job is "what it believes is the truth" and whose memory already holds what happened. Each has a lesson and an
optimizer of its own. A first idea of the same evening (each a recurrent memory of 128, "512 in all") was dropped: nothing measured
says the head is short of capacity; a part is widened when a readout shows it is too small. If one tracker output reads poorly from
the brain's state (his stack is the likeliest), the first fix is to make that fact a lesson of the brain.

**"The slow memory looks ahead": what 2.1f really is.** It is not 2.1e's slow half (that is dropped). It is a readout on the head's
own memory: for each play, "the pay from now until I let go of it, plus my value of where I stand then". That is the worth of a
commitment, however long it lasts (2 s for an item, 10 s for a cover): a fixed 8 s window mixes in his next decisions, so the window
labels learn beside it as readouts only. **Changed:** the open question of "commitment trials" (a lock on some trips, for measuring)
is not needed with this label, and is dropped.

## Why the outlook matters more in 2.2 than its card says

On today's 17 targets it tells him little he is not already learning (the card's own odds: 20 to 25% for a gain). Its real job:

1. **It is how a new play gets in.** A new row has no trained score, and the pull holds it about 9 points down. A bias cannot open it.
   But the outlook can learn a new play's worth quickly and honestly from a small share of trial trips, and its term then gives the
   row a real score. Silent on trial trips, then blended in by its dial: rule 13 as written.
2. **It answers the owner's questions in words**: beside the value it predicts a few facts for each play (**changed**, a small
   addition): he dies, I die, I take the item, my stack and his after. "If I take this fight" becomes a number he can read, and a
   label far less noisy than pay (the noise is what sank 2.1a and 2.1b).
3. **It makes the head's pay question measurable** (damage in the head's pay or not): the value under each pay learns side by side.

## The order: what the head tells the hands (changed: one contract, not one per play)

Every play the owner named is the same four things: **a place to be, a point to look at, a weapon to bring, fire at the point or
not**, and what ends it.

| Play | Place | Point | Weapon | Fire at the point | Ends |
|---|---|---|---|---|---|
| Go to an item (today) | the item | free | free | no | reached, gone |
| Chase | where the brain puts him now | him | the head's | no (the hands fight on sight) | contact, lost |
| Cut off | where the brain expects him in 1, 2, 4 s | his way in | the head's | no | contact, forecast gone |
| Break off | a way out | free | free | no | out of contact |
| Spam a spot / deny an item | a spot with a line | the item, his path | rockets, grenades | **yes** | the item's clock, contact |
| Hold for a rail | a spot with a line | the approach | the rail | no (the hands fire when he appears) | the item's clock, contact |

- The head never presses a key. It sets the goal; the hands carry it out and are shown the point. With the enemy in view the hands'
  own fight wins out, as now. The weapon stays a sum (decided 11-14), regularized (rule 11).
- The hands learn the three skills once, for any place and point (go to a place that is not an item; look at a point with nobody in
  view; fire at it), on trial trips with their success measured per skill. 1.7a's "he goes to the spot and does not fire" is this gap.
- The shared assumption of the failed attempts (1.7a, 1.7b, 1.9a, 2.1a): a play was offered before the hands could do it, before
  anything could say what it was worth, and re-drawn five times a second. 2.1 fixed the last; the outlook and this contract are the
  other two.

## The steps (one new thing each; each ends on its measure, reported; nothing holds on its own)

| Run | The one new thing | Why here | Read at its end |
|---|---|---|---|
| **2.2a** | The pilot: the outlook (17 outputs, and the form that scores a play's description), the tracker, the map sense, the judge with items, all silent; trial trips on the 17 targets; then the outlook's dial on the owner's mark | the instruments, before anything hangs on them | [its card](2.2a/CARD.md) |
| **2.2b** | **Attack: where and when.** The enemy target split into go to him now, and cut him off 1, 2, 4 s ahead (the brain's forecast). Trial trips → the outlook → its dial | the owner's priority ("I really want to see the attacking come to light"); movement only, the hands nearly have it (the hunt); the stack, the map sense and the weapons are what the outlook reads for it | scripted version first (the written rule); he fights; "I die / he dies" against what happened; the rows blanked at the end |
| **2.2c** | **Attack with the weapon to bring, and break off** | the weapon is two descriptions scored by the same outlook; break off is the other half of "should I take this fight" | as 2.2b; never fighting is the exploit to watch |
| **2.2d** | The hands' planned shot: look at a point, fire at it, on trial trips | needed by every play below | each skill's rate on trial trips, against a pass mark |
| **2.2e** | **Cover a point**: a spot, a point, a weapon, fire or hold. Items at their time first | the plays his copies make pay (they take the mega 0.8 s after its spawn) | camping and "fires with the enemy in view" above all |
| 2.3 | Opponents who walk into angles | a hold away from items does not pay in his world (a perfect one loses, −20.4) | [2.3](../2.3/README.md) |

**Before 2.2b: the head's pay is decided** (damage in it or the win chance alone) from 2.2a's side-by-side values. A head paid for
damage would choose fights for damage once attack is a choice. The judge that sees items exists (`JUDGE_ITEMS`, built and accepted for
1.9a, refitted in 2.2a); the line "the judge cannot see items" in the proposal and the review of 11-16 was wrong.

**Changed from the 2.2 proposal:** attack comes first (cover needs hand skills nobody has shown; attack needs none new). Hold and spam
are one play, told apart by the weapon and the fire flag.

## 2.2a

The pilot: its card is [2.2a/CARD.md](2.2a/CARD.md) (what is in it, the stages, the red team, the odds).

## Notes for 2.2c, from the owner's play test of 2.1d's end (11-16 evening; not designed in detail)

- **"Holding a rail angle isn't enough, but it's a start. It should also include 'have rail out and look for a shot'"** (owner). In the
  order's four parts: no fixed place, the point where he is expected, the rail in hand, fire on sight. It is the lead case of "attack
  with the weapon to bring", not only a hold.
- **My reading of why he does not use the rail (to be measured, not assumed).** The owner's: "he prefers to have weapons out that get
  him paid" (the hands are paid by the damage; the lightning pays steadily, the rail in lumps). Beside it: his opponents are his copies,
  who hold the rail almost never, so his hands get almost no rail practice, his rail on a moving target is probably weak, and holding
  fire until the target slows is then the right choice for him (a missed rail costs 1.5 s). A loop: not held, so not learnt, so not
  worth holding. Every attempt to move his weapon from outside failed (1.5a's weapon scores: no gain; 1.7c's table: collapse; rule 12).
- **Trial weapons**: on a small share of trips he carries a weapon he would not have chosen. The hands get the practice and the
  outlook learns what the weapon is worth from each place (the map sense already has a rail reading for every pair of places). The
  same mechanism as trial trips, on the order's weapon part.
- **The jumping and the rail are probably one cause**: nobody in his world rails him, so a jump in a fight (the easiest rail target)
  costs him nothing. Once the rail is used against him, jumping in view is priced by itself. Until then: a readout (jumps with the
  enemy in view against travelling), no cost added.
- **Before 2.2c, on recorded games (no training)**: his rail's hit rate by how fast the target moves, in self-play and in the owner's
  play test; how often he fires with the enemy in view, by the enemy's speed and by his weapon. Not a pro target: facts about his hands.
- **A fixed play test after each run** (the same maps, the score, the owner's three ratings: fight decisions, positioning, weapon use),
  to see the slow improvement he asked for.

## 2.2c: firing at a spot he cannot see (blind fire; the owner, 2026-11-17: "I think that's the right way in")

The run after 2.2b. It needs 2.2b's result first: he has to be standing at a spot and looking at a point before a trigger can be
taught there (1.7a's push on the trigger did nothing for that reason). The weapon to bring and break off, which this page gave to
2.2c on 11-16, moved into 2.2b.

**What blind fire is for (owner):** "blind fire is structurally about two things: area or weapon denial or chip damage. Both are low
success but add up largely over time and make a player much stronger. They are not going to get encouraged by damage pay." "Blind fire
works because it makes the opponent 'do something else'. That's the opportunity cost. If I get denied a route to mega and the enemy
takes it even though I otherwise would have been able to, the enemy needs to 'get paid' for that."

**So the pay is for what the enemy has to do in response, not for the damage.** As a bare idea it has two holes; the design closes both.

| Hole | Why | How it is closed |
|---|---|---|
| The enemy changes his mind constantly anyway | A copy of Bobby drops goals for many reasons; paid per "he gave it up", he fires anywhere and collects | Only a shot on the enemy's actual way counts, and only the response beyond his usual rate is paid (rows 1 and 2) |
| A copy that does not fear the shots never yields | Then there is nothing to pay | The enemy is charged what the shooter is paid, and the splash hurts him as it always did (row 3) |

**The design:**

| # | Part | Detail |
|---|---|---|
| 1 | Which shots count | A shot fired with the enemy out of view that lands **ahead of him on his way to the item he is going for**, shortly before he gets there. The simulator knows his goal and his way (a pay may use the truth, as a lesson's label does). The research's own rule: far rockets pay only as prediction at a place he must go (an item at its time, a door) |
| 2 | What is paid: the response | One of: he arrives later than his way's time; he gives the item up; **the shooter takes the item he was going for** (the owner's case: the denied route to the mega). The usual rate of each without a shot is subtracted, so firing at nothing averages to zero |
| 3 | Zero-sum | The denied player is charged what the shooter is paid. Each side pays for the other's denials, which gives the enemy his own reason not to be deniable and keeps two copies from farming it together |
| 4 | A near miss pays a little | **Moved into 2.2b on the owner's word (11-17, "ASAP")**: every projectile that bursts near the enemy, seen or not, pays a little by how close, charged to the enemy ([2.2b's card](2.2b/CARD.md), change 13). Here it is already running. Chip damage pays as damage |
| 5 | A cap | Per item spawn, so one item cannot be farmed |
| 6 | Who is paid | The fight network (it gets a sixth play, "spam", and a score on the trigger that is **added to the hands' own trigger score** while he is on a hold or spam play; both parts regularized and their sizes logged, rule 11) and the hands (they press the key) |
| 7 | Weapon denial | The same pay: his goal is the rail, the shots land on its approach |
| 8 | How it is taught | As 2.2b's plays: dealt as practice first, to both players, then the fight network's own choice of it opens |

**The equilibrium in self-play:** the shooter is paid only when the enemy yields; the enemy yields only when the shells cost him more
than the item is worth to him. So it settles at shelling the items at their times, and the enemy timing his entry between shells or
going for another item. An enemy who never yields takes the chip damage instead, which pays the shooter as damage.

**Never**: the pros' blind-shot places or their blind-fire rate as a target (rule 12; the old `BLIND_PLACES` switch did this and is not
used). No cost on firing (the owner's standing word).

**Where it can still fail:** it stands on the same prediction as 2.2b's cut-off (where he will be in 2 to 4 seconds). If that is not
good enough for a shell to threaten him, he never yields and nothing is paid. My odds that blind fire becomes a visible habit: 35 to 40%.

**Research check (short; the card's will be full):** DUEL_STRATEGY 1.10 ("spam is one of the primary sources of damage"; rockets and
grenades at doorways, items and his predicted path), 1.5 point 3 ("deal damage at his pickups, then leave"; "make his stack worth less
than it reads"), principle 5 ("an item taken under fire is worth less") and 13. Section 5.4: "item timings are the predictable
arrivals ... spam at the item pays by itself" if his arrival is predictable.

## Decided in the chat of 11-16 (owner)

- The three jobs with no new memory; the outlook scores a play's description; the tracker and the map sense enter through the outlook, not the chooser's inputs.
- Attack first (2.2b, 2.2c), then the planned shot and cover.
- The order is four parts (a place, a point, a weapon, fire at the point or not); the hands do all firing.
- **The split of hands and head is by timescale**: the hands own everything reactive, in view or not; the head owns the planned shot at a place and a time.
- A fight's inputs are explicit: his stack exact, the enemy's as the tracker's range (health and armor), the map sense, the weapons.
- Trial trips as the way the outlook learns the goals he does not favour, and the way a new play enters; 3% in 2.2a.

## Open for the owner

1. The head's pay (damage in it, or the win chance with items alone): before 2.2b, from 2.2a's readouts.
2. A drill pay for the hands' planned shot on trial trips (a pay for carrying out, not for a behaviour in games): at 2.2d.
3. 2.2a's length, and one session or two.

## Weak points

- The outlook knows only what he does; a play he never takes is unknown. The trial share is the guard, and too large a share is 1.9a.
- The head is paid for damage: an attack row can be chosen for damage, not for the game (the lightning habit).
- His world is his copies. What they do not punish, he will not learn; cover's gain can fade as they stop coming on time.
- Four learned parts sum into one choice (hands, head, pull, outlook): rule 11 on each, each size flagged.
- The plan (the pull's source) must widen with every new row and forecast it.
- A servers' plugin must set each play's clock and end.

## My odds (rule 15)

| | |
|---|---|
| The outlook shows skill above the yardstick on the 17 targets | 60% (a miss there is not final: those targets differ little) |
| ... on attack against break off | 75% |
| The attack rows survive on their own with the checks level | 50% |
| A visible gain against the control from 2.2a + 2.2b | 30 to 35% |
| The hands reach a usable rate on the point skills | 55% |
| A cover row survives on its own | 35% |
| By the suite's end the owner sees deliberate plays in a play test | about 50% |

## Research check (rule 14)

1. **The game**: no mechanic touched in 2.2a and 2.2b. 2.2d rests on item times (mega 35 s, red 25 s: MECHANICS, matches the sim) and on far rockets, which "pay only as prediction at a place he must go" (README core 7).
2. **What wins**: principle 2 (the stack decides a fight before it starts: the "will I win" readout and attack / break off), 4 (out of control: damage him at his known pickup times and leave: cover), 6 (value a life by what follows a death: the outlook's label). Works against none; a cover that turns into waiting works against 3 ("paying it outright invites spawn camping").
3. **The player's view**: tracker and outlook read only the brain's and head's states. No truth input.
4. **In and out of control**: attack serves the stacked player, break off and cover the other. The exploit to watch: never fighting (break off always), camping (cover always).
5. **Self-play equilibrium**: two copies that both value fights by stack fight less evenly matched fights; right per principle 2, and it can read as passive. Copies answer a known cover by not coming on time (correct: "stay unpredictable"). Nobody punishes a bad place: 2.3.
6. **Bot precedent**: BOTS.md idea 1 (predict each order's outcome, open on readiness; its named risks are the weak points above), idea 3 (new information as a readout first: the tracker), idea 10 (the order as a long-term goal the hands serve); FTW for the pull. The outlook's label is the standard value of a temporally extended action. Not AlphaStar's pointer over a fitted start (1.7a's, which failed).
7. **Rule 12**: no pro number anywhere.

# 2.2c: he contests the items from afar, and the fight network becomes an aggression lever

**Approved by the owner, 2026-11-18: "Yes to all. Build it and then start it when it's ready."** Written after
[2.2b's postmortem](../2.2b/POSTMORTEM.md) and the chat of 11-18. It replaces the older "2.2c: firing at a spot he cannot see" in
[../DESIGN.md](../DESIGN.md) (its pay for the enemy's response is used here; its "spam play" and its dealt practice are not).

## The owner's page

| | |
|---|---|
| Started from | 2.2a's update 90 (the file 2.2b started from). Nothing of 2.2b's training is used |
| The aim | He stops letting the enemy pick the items up for free: he pressures them from a distance with rockets, grenades, plasma and the rail. And he picks his fights by the state: the fight network turns his aggression up or down |
| What is new | Two things, opened together because they work as one: **the contest pay** and **the aggression lever** |
| What is out | Practice trips, dealt plays, a dealt weapon, the four fight options, anything shut in his list, any share set by hand (owner, 11-18: nothing makes him play a certain way) |
| How it is judged | Games won and lost against the start. Beside it, read and reported, never a pass mark: how many of the enemy's big pickups were under pressure, shells fired at items out of view, how often he hunts when ahead and when behind |
| Length | 100 updates (owner, 11-18) |

## Why this, in the owner's words

"He doesn't pressure the items at all. He just lets the opponent pick them up." "He's understacked and a safe distance from red. Don't
just let the opponent pick it up. Fire rockets targeted to where the opponent is/is going or where the item will spawn. Spam it with
grenades or plasma. Do literally anything but let the opponent just pick it up and cede the item. He needs to contest them in ways that
don't require getting directly in the fight." "The way to get behavior to emerge is make it worthwhile."

What 2.2b's records add: with the near-miss pay on and firing free, he fired with the enemy out of view on under 1 frame in 2,000,
and the near-miss pay was 0.2% of his pay's size. A pay that small, on something he almost never does, taught nothing. The pre-aim pay
is the model of one that worked: it pays at an event that already happens (every fresh sighting), it is graded, and the other player is
charged.

## Change 1: the contest pay

**The event already happens**: the enemy picks up a mega, a red armor or a yellow armor (thousands of times an update), or the rail,
the rocket launcher or the lightning gun.

**At that moment the simulator looks back 4 seconds** and grades how much pressure the other player put on that pickup, from 0 to 1.
That share of the item's own pay is taken from the picker and given to the one who pressured. An item taken under fire is worth less,
and the difference goes to him.

| Rung | What counts in those 4 seconds | Up to |
|---|---|---|
| 1. Set on it | In the last second he has a clear line to the item or to the enemy, his crosshair within 60 degrees of it (graded, 1 at dead on, as the pre-aim pay), and in his hand a weapon that does damage at that range by the game's own numbers (the lightning gun nothing past 768; the gauntlet nothing) | 0.25 |
| 2. Shells there on time | Each of his rockets, grenades or plasma balls that bursts near the item's place or near the enemy, graded by how close (1 inside the splash, falling to 0 at 300 units, the near-miss pay's own rule), fired in view or out of it | 0.5 |
| 3. Damage at the pickup | The damage he dealt the enemy in the 4 seconds, 100 points = 0.5. The damage itself is paid as damage as always | 0.5 |
| The total | Rungs added, at most 1 | 1 |
| **Without getting in the fight** | The damage he took from the enemy in the same 4 seconds is taken off, 100 points = 0.5; never below 0 | |
| 4. The steal | The enemy was headed for the item with under 4 seconds of way left, he pressured it (a rung 2 or 3 event), and **he** then picks it up within 10 seconds: he is paid the top share (80% of the item's pay) on top of the item's own pay, and the enemy is charged it | 1 |

| | |
|---|---|
| Size | Full pressure moves **80% of the item's flat pay** (owner, 11-18: "He still needs to get positive reward for picking up the item. Always. But the pressure on it should start to bite. Cap it at 80%"). The picker always keeps at least 20%. The item pays: mega 0.35, red 0.30, yellow 0.15 (a frag is 1.0), so full pressure on a mega moves 0.28. The weapons: 80% of 0.10. One live dial on the share (`CONTEST_W`, 0.8, never above 1). **As built (found in the build, 11-18):** health and armor are paid by the point, not by these flats (a mega taken at 150 health pays 0.10), so the share is taken of the smaller of the flat and what that pickup actually paid; otherwise a pickup at a high stack would pay the picker less than nothing, against the owner's "always". Measured on the start's games the contest pay is 1.9% of his pay's size |
| **A free pickup costs him a little** (owner, 11-18: "A small amount but he needs to learn to not let that happen. Letting the enemy gain stack is never good") | When the enemy takes one of these items with no pressure at all, he pays the picker **10% of the item's pay** (a mega: 0.035). With some pressure the charge shrinks in step and turns into his gain: from −10% at none to +80% at full. Its size is mine; a live dial (`CEDE_W`, 0.1) |
| Zero-sum | The picker is charged what the other is paid. Two copies cannot farm it together |
| A cap | One contest pay for each spawn of an item, so one item cannot be milked |
| Who is paid | The hands (they aim and fire) and the item picker (it chooses where he stands, and the charge lands on the picker's item pay). Not the fight network |
| The near-miss pay | Stays as built in 2.2b, at its 2.2b size, from update 0 |
| "He gave it up" | Not paid on its own (owner, 11-18: "leave out for now"). His copies change goal 20 to 34 times a minute for many reasons, so a pay per "gave up" would be collected by firing anywhere. The steal (rung 4) and a pickup under pressure are counted at the item, where nothing is ambiguous |

**Kept off the item: paid by the second** (owner, 11-18: "We can add a pay here"; approved as written).

| | |
|---|---|
| When it runs | A mega, red or yellow is up, and the enemy could have it soon: he is nearer to it than Bobby (by seconds of way) and under 6 seconds of way from it |
| What is paid | Each second it stays up while Bobby has pressure on it, 16% of the item's pay moves from the enemy to Bobby (5 seconds of delay moves the full 80%), times the pressure |
| Pressure here | His shells bursting near the item or near the enemy in the last 4 seconds: full weight (graded by how close, as rung 2). A clear line to the item with his crosshair on it and a weapon in hand that reaches: quarter weight (the rail angle held on an item) |
| The cap | 80% of the item's pay for each spawn, **shared** with the pay at the pickup and the steal. A pickup always pays the picker at least 20% |
| The enemy's choices | Go in and take the damage, or leave: beyond 6 seconds of way the charge stops |
| Its known fault | His copies dither near items for their own reasons, so some of it is paid for delays the shells did not cause. Accepted (owner's yes) |

**The free-pickup charge is always charged**, also when he took another big item in the same seconds (owner, 11-18: "anything that
allows the enemy to gain stack should be penalized. It might be the 'correct play' but it's still a best of all bad scenarios
situation"). It does not make taking the other item wrong: 0.30 for the red against 0.035 for the mega let go.

## Change 1b: the rail, a chain of three pays (owner, 11-18: "Pay him to pickup and own the rail. Pay him to have it out when the enemy is suspected far away and in possible sightlines"; approved as written)

| Link | The event | The pay | To |
|---|---|---|---|
| Picking it up | He takes the rail while he does not hold one; once a life | 0.15 (a yellow armor's pay; "a rail is almost a mega or a red", DUEL_STRATEGY) | The item picker |
| Having it out on a long line | A fresh sighting (the pre-aim pay's own event) from beyond 768 units, where the lightning gun does nothing: the pre-aim grade of his crosshair, counted only with the rail in his hand, less the enemy's the same | 0.10 a sighting, zero-sum (twice the pre-aim pay; that pay stays as it is beside it) | The hands and the item picker |
| Hitting with it | The far-rail pay, 2.2b's band (500 to 800 units) | 0.5 (2.2b's was 0.1) | The hands and the item picker |

Each on its own live dial. Not built: a pay for the right weapon at every range (it needs a table of each weapon's worth by range,
which would be a number invented by the planning session).

**What he needs to see to do it** (the build checks each, and adds what is missing as an input that starts at zero, with its measured
average and spread): his belief of when each contestable item is up (the yellow armors' timers are today read by no network's first
layer); where the brain expects the enemy in 1, 2 and 4 seconds (the brain's answer already reaches the hands). No order, no mode: inputs only.

## Change 2: the fight network becomes an aggression lever

| | |
|---|---|
| What it puts out | **One number.** It is added to the item picker's own score for "the enemy", which stays in his list as it is. High: he goes after him. Low: an item wins, which is stacking up. Beside it, its two forecasts of its own pay, as in 2.2b |
| What is removed from 2.2b's fight network | The four fight options, their bias, the weapon nudge, the practice deal, the shut mask |
| What it reads | As built: the belief's memory, the predictions (who is in control, the odds of a fight, deaths soon, the enemy's stack as a range), his stack, weapons, ammunition, the item timers, the score and the clock, the item picker's scores, where he is headed. The four options' place numbers go out with the options |
| The hands | Are shown the number as an input (the token built in 2.2b, its gate opened over updates 10 to 20). They are told how eager he is; they are not told what to do |
| Its pay | Its own: damage dealt less damage taken, frags, deaths, and the change in his chance of winning from the judge that reads the items and stacks, scaled to at least the size of its flat pay (rule 14). No item pay, no contest pay |
| How it learns | From every decision he makes (each one is a choice between the enemy and the items), by his own play. Nothing is dealt |
| The start | Its last layer starts at zero: he plays exactly as 2.2a's update 90, proven on fixed-seed replays |
| Rule 13 | The enemy's total is now a sum of two learned scores: both get the decay from update 0, the lever's size is logged every update and flagged over 40 |

## Kept from 2.2b's pay (owner, 11-18: "there are good things from 2.2b we have to keep, relating to pay movement")

Only 2.2b's code and settings are kept, none of its training.

| Kept | Detail |
|---|---|
| **Each network paid for its own job** | The item picker: items, the chance of winning, and now the contest pay. The fight network: damage dealt less damage taken, frags, deaths, the chance of winning. The hands: as before, plus the contest pay and the far-rail pay. It cost nothing in 2.2b's first 60 updates |
| **Frags and deaths go to the fight network only** | The item picker feels a death through the chance of winning (owner, 11-18: "this is fine") |
| **The judge that reads the items and stacks** | The chance of winning comes from it, refitted on the start's games and accepted before the start (rule 14) |
| **The win-chance pay at least the size of each network's flat pay** | It was 42% of his pay's size in 2.2b |
| **The near-miss pay** | As built (zero-sum, at most one full near miss a second), at its 2.2b size, from update 0 |
| **The weapon choice is the hands' own** | The item picker's push on his weapon goes out over updates 0 to 10 and its weapon scores are never trained (owner, 11-18: "first 10 updates get rid of the item picker's push and let the hands do all the work") |
| **The warm-up of 2.2b's restart** | The item picker frozen but for its forecast's last layer through update 10, while its forecast relearns the new pay (in the restart it never moved) |
| **Firing costs nothing** | As now: `COST_FIRE_W=0`, `BLIND_FIRE_W=0` |

| Moved | Detail |
|---|---|
| **The far-rail pay goes to the hands, and to the item picker** (owner, 11-18: "Give the hands the far rail pay"; the item picker added with change 1b) | In 2.2b it went to the fight network, which acted on it through its weapon nudge. The nudge is out, and the hands pick the weapon and fire. **Its size 0.5** (owner, 11-18: "something crazy like 0.5? Just to see what happens"; 2.2b's was 0.1), its band as in 2.2b's command (500 to 800 units); a live dial, so it can come down in the run. This replaces the owner's word of 10-21 (rail pay nudges dropped) |

| Dropped | |
|---|---|
| The fight network's weapon nudge; the four options and their bias; the practice deal and its weapon push; the shut mask | |

## The schedule (100 updates; everything opens on the clock, every number reported)

| Updates | What plays | What learns |
|---|---|---|
| 0 | Identical to 2.2a's update 90 (proven before the start) | |
| 0 to 10 | **The contest pay (at the pickup, by the second, the steal, the free-pickup charge) and the rail's three pays at full size from update 0.** The lever at zero. The item picker's choices frozen; its push on his weapon fading out, gone by update 10: the hands do all the work | The hands, under the contest pay and the far-rail pay. The forecasts of the item picker and the fight network, under their new pays |
| 10 | Check against the start | |
| 10 to 100 | **The lever on, the item picker's choices taught again, the hands shown the lever (its gate opening over 10 to 20).** Nothing else changes for the rest of the run | Everything |
| 30, 50, 70, 90 | Checks, 200 games, against the start; every fourth against the long-term control | |

The warm-up to update 10 is not a slow opening of the new parts: a network whose pay has changed cannot be taught choices until its
forecast of that pay has relearnt (2.2b's first start lost 0-200 on this), and the contest pay is on in full meanwhile.

**The one pass mark: checks level with the start or better.** It is known to be reachable (the start scores level with itself;
2.2b's first 60 updates held it under the same pay split). Everything else is reported and is not a pass mark, because none of it can
be shown beforehand to pass (owner, 11-18). A check under 40% is flagged at once as a major problem.

**Reported every update from update 1**: the enemy's big pickups under pressure (share, and the average pressure), steals, shells
bursting within 300 units of an item about to come up or just taken, fired in view and out of view, by weapon; the contest pay's size
in his pay; the lever's size and its average when he is ahead, level and behind on stack and just after a frag; how often he heads for
the enemy in each of those four; frags and damage a match-minute; the gauntlet and weapon-choice-speed alarms (the second fixed to
read the hands' own figure).

## Red team: what is set by hand or assumed

| Part | Whose | The risk | Its measured alternative or guard |
|---|---|---|---|
| The size (80% of the item's flat pay) | The owner's cap | Too small again: the item flats are 2 to 6% of his pay's size, the chance of winning 42%. Or he gives up his own items to shell the enemy's | The contest pay's share of his pay reported from update 1; his own pickups a minute beside it. It cannot be raised past the whole item pay without breaking "a pickup always pays" |
| The charge for a free pickup (10%) | The owner's, its size mine | He is charged for pickups he had no way to reach (just spawned, across the map), and answers by hanging around the enemy's items and neglecting his own | Small by design; his own pickups a minute; how far he was from the item at each free pickup, reported; the live dial `CEDE_W` |
| The 4-second window, the 300 units, the rungs' weights | Mine | A window too short misses grenades thrown early ("grenades 2 to 3 s before mega" fits; a lob from far may not) | Counted from update 1: shells that burst at an item up to 8 s before a pickup and earned nothing |
| Rung 1 (set on it, no shot) | Mine, from the pre-aim pay | He learns to stare at items and never fires | Rung 1 is a quarter; shells and damage are worth twice as much; fired shells reported beside it |
| The charge on the picker | Mine | He stops taking big items at all when the enemy is near, and both copies stand off | His own big pickups a minute and the checks; the win-chance pay still pays the stack |
| "Damage taken is taken off" | Mine, from "contest without getting in the fight" | He never contests at close range even when stacked | The lever and the damage pay cover the close fight; this pay is only for the far one |
| The far-rail pay to the hands, at 0.5 | The owner's | He stops playing the game to stand far away with the rail. And still: in 2.2b he held the rail 0.3% of the time and fired it about 60 times an update, so even a large pay starts from few samples; rung 1 of the contest pay (a weapon that reaches, on a line to the item) is what is meant to lead him to it. What 0.5 is in frags for one far hit is stated in `BUILD.md` | The rail in hand, rail shots and far hits a minute, reported from update 1; the size is a live dial (`RAIL_FAR_PAY`) |
| The lever only repeats the item picker's score for the enemy | Assumed not | 2.1e: a second forecaster of the same thing from the same inputs matches the first | Its pay and inputs differ; its size is reported; if it stays near zero that is the answer, and it has cost nothing |
| The hands can find the shot from their inputs | Not verified | No pay can teach a shot at something he cannot locate | The build's input check above, before the start |
| Self-play | Assumed | His copies yield to shells the same way he fires them; a person may not | Play test after the run |

**The pay's pathology check.** Negative frags: untouched. Sign flips: the contest pay is zero-sum and capped at 80% of the item's pay, so a
pickup always pays the picker at least 20% of it. Lopsided games: the weaker player collects more contest pay, the stronger loses
some item pay; that is the intended direction (the out-of-control player's play). Farming: paid only at a real pickup, once per spawn.
Aiming beside the enemy for near misses: a hit pays far more than a near miss, as in 2.2b.

**The equilibrium in self-play.** The shooter is paid when the enemy takes an item under his fire or loses it to him. The picker
answers by coming at another moment or by another way, by taking another item, or by clearing the shooter out first (the lever's
side). So it settles at shelling the big items at their times from safe places, entries timed between shells, and fights started
where the stack allows. An enemy who walks through takes the damage.

## Read against the goals and the research (the planning session, 11-18, on the owner's word)

**Where it fits.**

| The owner's line or the notes | What in this card serves it |
|---|---|
| Three things decide a fight: stack, positioning, weapons | The contest pay is about the enemy's stack (an item under fire is worth less to him). The far-rail pay and rung 1 are about the weapon for the range. Being charged for a far rail hit teaches the other one where not to walk: positioning |
| Take high-confidence fights, leave the coin flips | The lever, reading both stacks, the weapons and the fight odds. The contest pay takes off the damage he took, so walking into the item and trading pays little ("a small LG hit on a healthy opponent on his way to red is a poor trade", DUEL_STRATEGY 1.4) |
| To win you have to play to not lose | Shelling from safety is damage without return damage ("deal damage as the opponent picks up items, then leave without taking damage", 1.5; "defensive damage", the defender who backs off as he shoots) |
| Chip and zoning damage as a milestone | Rungs 1 and 2 pay the shot at the place and the time, hit or not |
| Ahead: run the clock. Behind: don't gamble | The lever reads the score and the clock |

**Three gaps found in this reading, each closed on the owner's yes (11-18).**

1. **Nobody was paid to own the rail** (the item picker decides whether he walks to it; he owned it 1% of the time). Closed by
   change 1b: the pickup pay, the long-line pay, and the far-rail pay to the item picker as well as the hands.
2. **The charge for a free pickup falls on "take the other item" too.** The planning session proposed an exemption; the owner kept
   the charge, and the planning session agrees: the trade still pays well, the charge only ranks "take the other and shell his" higher.
3. **The best denial paid nothing directly.** Closed by the pay by the second (change 1).

**Weaknesses that stay.**

- **His world is his copies.** They will learn to respect shells and long lines because they are charged for it. A person is not
  charged. The play test after the run is the only check of that (the notes' self-play warning, README core 9).
- **Every pay here is still a pay for an action, not for winning.** They are meant as the way in: once he does these things, the
  damage and the chance of winning should carry them, and these pays can come down on their dials. If the behaviour disappears when
  a pay is turned down, it was never worth anything to him.
- **The far-rail pay at 0.5 pays aim at range.** The notes also say "rail whoring makes you predictable" and "rail spots need a
  safe position and an exit" (1.5, 1.9). Nothing here teaches the exit; the damage he takes while standing there does.
- **Plasma**: its splash is one of the listed differences between the simulator and the real game, so a habit of plasma at items
  may not carry over to a server.

## Research check

1. **The game**: splash radii, projectile speeds, grenade timing and item respawns (MECHANICS, core numbers "match" per the notes' section 7). Plasma's splash offset is listed as off the real game: plasma's rung-2 pay rests on a simulator difference until measured.
2. **What wins**: DUEL_STRATEGY 1.3 ("Denying = ... making its pickup cost him"; "grenades 2 to 3 s before mega"; damage "voids" an item), 1.5 point 3 ("deal damage at his pickups, then leave"; "spam the item and its approaches"; "rail him at the mega from cover"), 1.10 ("spam is one of the primary sources of damage"), 1.11 ("weapon control is control"); PRO_INTERVIEWS strenx ("you just check and you spam"; "with rail and the opponent without it, you have position everywhere"). Works against none; pushed too far it works against 1.6 ("never give up the position for a frag that may not come"): his own pickups are watched.
3. **The player's view**: he times the items from heard and seen pickups (his belief), and places the enemy by sound and last sight (the brain). The pay reads the truth; his inputs do not.
4. **In and out of control**: the out-of-control player's main tool (1.5); the in-control player's "spamming the entries to your area" (1.6). The exploits to watch: hovering at the enemy's items; never taking a contested item.
5. **Self-play equilibrium**: above. "Prediction and counter-prediction" (1.12): the picker's answer is to be less predictable. No league opponent punishes over-shelling; ammunition and missed items do.
6. **Bot precedent**: BOTS.md has no system with a pay for denial; the nearest is its warning that one high-variance pay part can stop the value from being learnt (OpenAI Five). This pay is frequent and capped. Not AlphaStar's or Pluto's: nothing strategic is taken from them here; the lever is a learnt bias on one option of an existing choice, not a new chooser.
7. **Rule 10**: no pro outcome is a target. The grenade timing and the places are not set; only the game's own ranges and the simulator's truth of who took what.

## Not verified (the build settles each before a start)

- That the simulator's "seconds of way to a place" can be asked for the enemy and an item at every frame cheaply enough (rung 4).
- Which contestable items' timers the hands read today.
- The size of one full contest pay against one rocket hit's damage pay (to be stated in `BUILD.md`).

## For the owner

Decided 11-18: the far-rail pay to the hands; frags and deaths to the fight network only; the item picker's weapon push out over
the first 10 updates.

The length: 100 updates (owner, 11-18).

Also decided 11-18: full pressure moves 80% of the item's pay and a pickup always pays; a free pickup costs him a little; "he
gave it up" left out for now; the contest pay goes to the hands and the item picker; the hands are shown the lever; the far-rail pay
at 0.5.

And: the rail chain (0.15 for the pickup, 0.10 at a far sighting with the rail out, 0.5 for a far hit, the last two also to the
item picker); the free-pickup charge always, at 10% of the item's pay; the pay by the second (16% a second, the enemy within 6
seconds of the item). **The go: "Yes to all. Build it and then start it when it's ready."**

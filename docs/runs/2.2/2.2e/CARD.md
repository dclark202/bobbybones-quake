# 2.2e: 2.2d without the rail pickup pay, on a new aim level (aim4), with a rail drill

**Approved by the owner, 2026-11-19**: aim4 ("yep. make that the aim4 default. build it and start it when it's ready"); the rail
pickup pay out, the lever kept as in 2.2d ("1. yes 2. yes 3. yes"); the far-rail pay ("I think we should drop the far rail pay down
to .2 - enough to encourage the behavior but not enough to completely turn him into a rail only player"); the drill ("him in a long
room, spawned at different distances to the enemy 500--1500 units. Enemy moves fastly and randomly with jumps. He has only the rail
no mg or gauntlet can move but has no other incentive in this space other than to just shoot at the enemy. he gets paid for shots
that land", "this is distinct from rule 11 and I'm specifically asking you to do it", "fine use the duel maps"); the length ("we'll
plan to run it overnight til 8am").

Written after 2.2d failed its pass mark (RUNS.md #62: checks against the start 98-102, 72-128, 92-108, 86-114, 78-122, 81-119).

## The owner's page

| | |
|---|---|
| Started from | 2.2a's update 90 (the file 2.2b, 2.2c and 2.2d started from). Nothing of 2.2b's, 2.2c's or 2.2d's training is used |
| The aim | The same parts as 2.2d without what made it fall, on an aim level that makes the mid-range rail easier, with practice for the far rail he has never learnt |
| What is new against 2.2d | Aim4 for every seat. The rail pickup pay out. The far-rail pay 0.5 to 0.2. A rail drill on 10% of training. More checks, two alarms, a monitoring session |
| How it is judged | Games won and lost against the start, both seats on aim4. Nothing else is a pass mark |
| Length | It stops after a save at 08:00 on 11-20 (owner, 11-19) |

## Why 2.2d fell (the reading this card rests on)

- Its record tracked his share of the red armor (33 to 38% in the losing checks; the start's 39 to 43%) and the maps where he
  collected the rail (aerowalk, sinister, bloodrun: 32 to 37% of games won; rail owned 21 to 72% of his time there). He owned the rail
  23% of his time and held it 0.5%.
- The lever did not cause it: with the lever zeroed, update 80 went 87-113 and update 60 went 85-115 against the start (the run's own
  81-119 and 86-114); head to head, lever on against lever zeroed, 97-103 and 83-117. It changed his target in 42 of 14,400 decisions.
- So the rail pickup pay is the best-matching cause: it sent him to an item he then did not use, at the red armor's cost.

## Aim4 default (one config for every weapon; docs/design/AIM_ROOM_2026-11-19.md)

Aim3's "better" level with the sight error in proportion to how big the enemy looks.

| Setting | Aim3 default (2.2d) | Aim4 default |
|---|---|---|
| Reaction delay | 125 ms | 100 ms |
| Time to pick up a new target | 225 ms | 175 ms |
| Enemy velocity age (`VEL_DELAY_MS`) | 200 ms | 175 ms |
| Velocity error / range error (`VEL_WEBER`, `RANGE_WEBER`) | 0.20 / 0.19 | 0.15 / 0.17 |
| Base sight error (`PERCEPT_SIGMA`) | 0.9 | 0.64 |
| Sight error: constant part / part by apparent size (`AIM3_SIZE_A`, `AIM3_SIZE_B`) | 0.39 / 0.355 | 0 / 0.49 |
| Slip on a moving target: rate / cap (`AIM2_C_SLIP`, `AIM2_CAP_SLIP`) | 0.023 / 2.1 | 0.007 / 1.1 |
| Off-centre error (`AIM2_C_ECC`) | 0.06 | 0.01 |
| Sight error while his focus lasts (`AIM2_FOCUS_SIG`) | 1.0 | 0.7 |
| Eye lag (`AIM3_PURSUIT_TAU`) | 0.125 s | 0.10 s |
| Flinch when hit (`FLINCH_PER_DMG`, `FLINCH_MAX`) | 0.012, 0.7 | 0, 0 |
| Hand noise: moving / base (`MOTOR_NOISE`, `MOTOR_BASE`) | 0.10 / 0.05 | 0.08 / 0.038 |
| Everything else (the hand's turn steps, its carried view speed, its bandwidth, the rocket lead) | | unchanged |

What the aim room measured on 2.2a's update 90 (a fast strafing target, 11-19): the reaction delay is the only setting that moves
his hit rate, and it moves the lightning gun with the rail. Aim3 "better": rail 30% to 38% at about 470 units, 20% to 24% at about
910; lightning gun 41% to 49% at about 300; rockets 37% to 40%. At a 75 ms delay the lightning gun reached 54 to 59%, which the
owner ruled out. The proportional sight error changed nothing measurable on this network; it is kept on the code's reading (aim3's
far sight error is a slow offset of up to one half body) and equals "better" at 300 units. No setting moved the far rail: his error
at about 910 units stayed near 1.9 half bodies under every variant.

## The rail drill (the owner's, 11-19)

| | |
|---|---|
| Share | 10% of training frames from update 0 through update 40, fading evenly to zero by update 60. Checks are whole games only |
| Where | Long sight lines on the ten duel maps (the aim room's spots), not a separate room: his network has no tables for another map. At 1,500 units only narrow lanes exist (Campgrounds, Furious Heights) |
| A stretch | 30 seconds in three placements of 10 seconds. At each placement he and the target are put on a line at a distance drawn evenly from 500 to 1,500 units, his view a random 0 to 45 degrees off the target |
| Him | Only the rail, ammo that does not run out; no machine gun, no gauntlet, no items. Free to move and jump; nothing pays or charges him for it. Aim4 |
| The target | Scripted, never fires. Runs at full speed across his line, changing direction at random: every 0.3 to 1.2 s in half the stretches, every 0.15 to 0.5 s in the other half. Jumps at random (the aim room's share). Its health is restored after each hit |
| The pay | Only for a rail shot that lands: the hands' damage pay for it and the far-rail pay (0.2), exactly as in a game. No frag, item, win-chance or death term |
| Who learns | Only the hands. The item picker, the fight network and the brain's forecasts take nothing from drill frames. The hands are told it is a drill as they are told a game's kind |

## What plays, against 2.2d

| Kept as in 2.2d | |
|---|---|
| Each network paid for its own job; the win-chance judge that reads the items and stacks | Re-measured on the start's games under aim4 (rule 14) |
| The aggression lever | Zero through update 10, on in full from 11; the hands shown it over 10 to 20; decay and size logged (rule 13) |
| The item picker frozen through update 10; its push on his weapon out over 0 to 10 | |
| The hands' inputs; firing costs nothing; the contest counters as logging; the two log lines; the weapon-speed alarm | |

| Changed | |
|---|---|
| Aim | Aim4 default for him, his league opponents and the control |
| The rail pickup pay | 0.15 to 0 |
| The far-rail pay | 0.5 to 0.2, its band unchanged (500 to 800 units, then level) |
| The rail drill | New, above |
| Checks | Updates 10, 20, 30, then every 10, and the end; 200 games against the start, both seats aim4; update 60 also against 2.1d's end |
| Alarms | His red armor share 5 points or more under the start's in a check; his time holding an empty weapon over 1.5% |
| Monitoring | A separate session from update 1 (2.2d had none) |
| After the end | The aim room on the end save: rail, lightning gun and rockets. The lightning gun over 53% at about 300 units is flagged to the owner |

## The schedule (everything opens on the clock, every number reported)

| Updates | What plays | What learns |
|---|---|---|
| 0 | 2.2a's update 90 under aim4. With aim4's values set back to aim3's and the drill at zero: identical to it (proven before the start) | |
| 0 to 10 | Far-rail pay 0.2. The drill at 10%. The lever at zero. The item picker frozen; its weapon push going out | The hands; the forecasts of the item picker and the fight network |
| 11 to 40 | The lever on; the item picker learns; the drill at 10% | Everything |
| 41 to 60 | The drill fading to zero | Everything |
| 61 to the end | Whole games only | Everything |
| 08:00 on 11-20 | It stops after a save; the end kept with its optimizer, checked, and put through the aim room | |

Saves kept every 10 updates and the end.

**The one pass mark: checks level with the start or better.** A check under 40% is flagged at once as a major problem.

## Red team: what is set by hand or assumed

| Part | Whose | The risk | Its measured alternative or guard |
|---|---|---|---|
| Aim4's values | The owner's choice of aim3 "better"; the proportional part mine | The lightning gun gains as much as the rail, so the rail may be no more worth holding than before. After training the lightning gun may rise past what the room showed on an untrained network | The room on the end save. The delays are command settings, not live dials: they cannot be changed in the run |
| The proportional sight error | Mine | It measured no effect; it rests on reading the code | Equal to "better" at 300 units, smaller beyond; the room measures this exact combination before the start |
| The drill's share, length, placements, fade | The share the owner's (10 or 15%); the rest mine | He learns the script's movement, not aiming at a player. He hits in the drill and still does not hold the rail in games. October's rail starts (10 to 15%, both seats with the rail from a mid-game moment) were dropped as doing nothing | Random direction changes; games are 90%. Every update: drill hit rate by distance, and in games the rail's time in hand, shots and hit rate by distance |
| Only the hands learn from the drill | Mine | The brain shares layers with the hands, so "nothing but the hands" may not be separable; the hands' own estimate of what is coming may mix a drill's pay with a game's | The build shows which parameters get a gradient from drill frames, and that the hands can tell a drill from a game. If either cannot be done cleanly it goes to the owner before a start |
| The far-rail pay at 0.2 | The owner's | Too small to matter outside the drill: at 0.5 it collected almost nothing in 2.2c and 2.2d | A live dial |
| The rail pickup pay as 2.2d's cause | Mine | 2.2d's fall began when the item picker started to learn (update 11); the pickup pay is the best match, not a proof. If it was the item picker's learning itself, this run falls the same way | Checks at 10, 20 and 30; the red armor alarm |
| The win-chance judge | Fitted under aim3 | Under aim4 fights end differently, so its numbers may be off | Re-measured on the start's games under aim4 and accepted, or reported |
| The start is not level with 2.2a's update 90 as it played | Aim4 changes his play from the first frame | The first check compares two networks that were both trained on aim3 | Both seats play aim4 in every check; the start against itself under aim4 is level by construction |
| Self-play | Assumed | His copies both close at once; nothing punishes open ground | Not addressed here |

**The pay's pathology check.** Negative frags: untouched. Sign flips: none. The drill pays only a landed shot and charges nothing;
he cannot enter or stay in a drill by his own choice (its share is on the clock), so it cannot be farmed from a game. In games the
far-rail pay is zero-sum as before (the one hit is charged). Lopsided games: the stronger player collects more far-rail pay, as with
damage. Nothing is paid for a shot that hits nothing.

**The equilibrium in self-play.** In games his pay is damage, frags, items and the chance of winning, plus a small far-rail pay;
nothing pays him to own the rail. He holds it only if it deals more than the lightning gun or the rockets where his copies fight.
The drill adds no term to a game: it can only change how well his hands aim the rail. If his copies still both close to lightning
gun range, he will aim the rail better and still not carry it.

## Research check (docs/research/README.md's seven questions)

1. **The game**: nothing of the game changes. The rail's 80 points and 1.5 s between shots: MECHANICS.md's weapon table.
2. **What wins**: the rail "is the comeback weapon" and "almost a mega or a red" (DUEL_STRATEGY 1.5, 1.3); the lever serves "take the uneven fights" (1.4, 1.6). The red armor share that 2.2d lost is stack control (1.3). "Making his pickup cost him" stays unserved.
3. **The player's view**: no input is added. Aim4 changes how late and how exactly he sees the enemy, every limit still a person's (aim3's "better" level is set from the pros' measured values; AIM3.md section 4).
4. **In and out of control**: nothing new for either side.
5. **Self-play equilibrium**: above. No league opponent holds a long line; the drill's target is not a player.
6. **Bot precedent**: a drill on a share of training is nearer to a curriculum than to anything in AlphaStar or Pluto; nothing strategic is taken from them here.
7. **Rule 10**: no pro outcome is a target, a pay or a pass mark. Aim4's values are human limits (allowed). The pros' hit rates in the room's tables are a marker for reading it, never a mark he must reach. The drill pays his own landed shots.

## Which principles (docs/design/PRINCIPLES.md)

Follows 6 (each part off = identical, on its own dial) and 8 (each decider paid for its own job). The drill departs from "a new
behaviour is brought out only by making it pay" by the owner's own word, for a hand skill only.

## Not verified (the build settles each before a start)

- That drill frames reach only the hands' learning, and that the hands can be told a drill from a game.
- That the aim room's target script can run inside the trainer's simulator, off = identical.
- The win-chance judge under aim4.
- "Better" with the proportional sight error in the room, and the lightning gun at 200 units under it.

## Decided from the design's intent (rule 7)

Three placements of 10 seconds in a 30-second stretch; his view 0 to 45 degrees off the target; the target's health restored after
each hit; the fade from update 41 to 60; the alarms' thresholds; checks every 10 updates after 30.

# Stage B of the attention model: the build's specification (2026-10-11 night; being built in copies while v0.2 trains)

The owner, 2026-10-11: "Build everything for attention A first, then build the rest (B and C) once the run has started
and you have downtime." Stage A is training as v0.2 ([../v0.2/MANIFEST_v0.2.md](../v0.2/MANIFEST_v0.2.md)). This page
says what stage B is in the simulator and the trainer, part by part, so that each part can be built and checked on its
own and merged after the run. Nothing here changes the running simulator: every part is behind a switch that is off by
default, and with all of them off fixed runs must be bit for bit what they are today. His answers that it rests on are
in V16_APPROACH.md ("The owner's answers").

## Part 1. Things he is asked to foretell (not paid)

Why: they shape what his memory keeps and what the attention part reads; nothing pays him for them. Owner: fights taken
and refused "as a measure and as something he is asked to foretell"; crosshair placement "very important".

| What | The label | Where it comes from |
|---|---|---|
| Where the unseen enemy is | his true place in his own frame (forward, left, up), on frames the enemy is alive and out of view | the simulator's state at that frame |
| Where the enemy next appears | the direction (sideways and up-down angle from his view as it stands) of the enemy at the next frame he comes into view, if that is within 5 s | hindsight inside a rollout |
| How the next fight ends | within 10 s of a frame with the enemy in view: his frag, the enemy's frag, or neither; and the damage dealt less the damage taken in the next 5 s | hindsight inside a rollout |
| When the big items return | seconds until the mega and the red armor are back, as they truly are (he is shown only what he believes) | the simulator's state |

- Simulator: `info["aux"]`, one array a step with, per player: the enemy's true place in his frame, alive and in-view
  flags, the true seconds to the mega and the red armor, the damage dealt and taken this frame, a frag made, a frag
  taken. Always written (cheap), read only by the trainer.
- Trainer: `--aux <weight>` (0 = off). Small output layers on his memory for the four labels; the hindsight labels are
  made from the rollout's stored frames; losses: squared error on places and seconds (scaled), cross-entropy on the
  fight's end. The size of each loss and how well he foretells (the error in units; the share of fights called right)
  are written with every update. With `--aux 0` the trainer is as it was.
- Never an input: what he foretells is not fed back to him in this stage.

## Part 2. A target that is never "nothing", and places as targets

Why: with no item due he has no target, his legs cannot carry him and he stands on his own feet at 270 units a second,
13 to 23% of his time, in the places the owner found him waiting. Owner: "Yes".

- Switch `TARGETS=1`. The intention keeps its nine choices and gains eight: "place 1" to "place 8", the map's holding
  places: the eight cells of `sim/pro_places/<map>_cells.json` where the pros hold longest and fare best (a list a map,
  made once by a tool and kept as `sim/pro_holds/<map>.json`; a map without one has no place choices).
- A place as a target: his way leads to it (the route field's nearest point), it is reached when he stands within 96
  units, and it stays his target while he holds it. No pay of its own.
- "Nothing" stays a choice but the item rule's lesson no longer names it: where the rule names no item the lesson is
  silent, so that what he does then is his own.
- The enemy as a target (the ninth choice) stays as built and is still not seeded.
- His legs: a place is a way like an item's. The inputs "his target" and "his way" show a place as they show an item.
- New inputs, at the end: for each of the eight holding places, where it is in his frame, the way to it in seconds, and
  how the pros fare there (already in the place tokens of stage A for the firing places; these are the holding ones).

## Part 3. Several ways to a target

Why: there is one way to each item, the shortest, and his legs take it every time; the owner's "main failure point is
that their routes are predictable". Owner: "Yes".

- Switch `WAYS=1`. For each pair of route goals the pros' ways are in `sim/pro_ways/<map>.json` (up to three a pair,
  with points every 128 units). A second route field is built a map from each goal's alternative ways: the shortest way
  that follows the pros' second and third ways where they exist.
- A new output, the way (three choices: the shortest, the second, the third), read with the intention. His legs and his
  own way inputs follow the way he chose. Where a pair has fewer ways the other choices are the shortest.
- Measured, not paid: the share of his trips on the commonest way (57% today, the pros 43%).

**Built 2026-10-12 night** (patch scripts with their checks, in a copy; not on the card). With `WAYS` off fixed runs
are bit for bit; every set of ways arrives from every point of every map; flipping the way at every reading earns no
more trip pay than keeping it. **The lever is small as built**:

| | Ten maps |
|---|---|
| The pros' ways that are not the shortest | about 380 |
| ... that need a drop or a jump the walking map lacks / are rocket jumps / cost over 1.5 times the shortest | 147 / 74 / 28 |
| ... that his legs make when tried (5 of 6 tries) | 134 of 176 tried: 130 second ways, 4 third ways |
| Starts from which the second way differs from the shortest | 9 to 24% by map |

Blood Run's and Aerowalk's mega have no second way at all. Where there is one his legs really take another path (Blood
Run's red armor: 39% of the path's points over 128 units from the shortest run; Aerowalk's yellow armor 73%). A new
finding on the way: his legs do not make every link of the walking map (a drop onto a ledge on Blood Run sent him
round for good), so a way counts only after his legs have made it (`sim/pro_ways_legs/<map>.json`, made again when his
legs or the walking map change). What limits the choice is the walking map and his legs, not the choosing: the pros'
other ways are mostly jumps and drops. It joins the jumps (B-204) and rocket jumps, which the owner asked to be
reminded of after this run.

## Part 4. Whole games, and a frag paid by what it does to the game

Why: only a whole game makes the score and the time left mean anything. Owner: whole games "Yes"; a frag paid by what
it moves his chance of winning "yes"; late-game rounds from drawn states "yes, up to 25%".

- Switch `GAME_P=<share>`: that share of the games' groups play whole ten-minute games (clock and score running, no
  restart at two minutes). Switch `LATE_P=<share>`: rounds of three minutes that begin at 7:00 of such a game with a drawn
  score (ahead or behind by one to three, or level) and the stacks that go with it.
- The pay in those games, switch `WIN_PAY=1`: a frag for him or of him pays the change in his chance of winning the
  game, by the score difference and the time left, times a scale that makes a frag at 0:0 with ten minutes left worth
  what a frag is worth today. The table comes from the pros' games (the mended parser gives both scores at every
  moment): `sim/win_chance.json`, made by a tool. The flat pay for a frag is not paid there.
- The game token gets the true time left in the game and the score difference (they are inputs already in rounds).
- Checks: the same network in whole games against two-minute rounds (does anything break when a game runs ten minutes:
  items, clocks, memory resets); what a game pays in all against today.

**Built 2026-10-12 night** (patch scripts with their checks, in a copy; not on the card). With the switches off fixed
runs are bit for bit; a whole game ends once at its 24,000th frame with clock, score and items right on every frame;
late rounds are drawn as specified. What the build changed in the specification, and what is the owner's to decide:

- **The pay is per frame, not per frag.** The chance of winning moves with the clock too: paid at frags alone, falling
  one behind early and levelling late would pay 1.4 for an unchanged chance. So every frame pays the change, a frag's
  frame carries the step, and between frags the leader gets a trickle (one ahead for a whole game: about 3.1 of the
  4.1 a won game pays in all). The two players' pays sum to zero on every frame and a game's sum is exactly the
  scale times the change in chance. An enemy's death by his own hand pays him.
- **The table** is from 300 demos read tonight (257 games; the whole archive is 33 minutes at one process). One frag
  ahead with ten minutes left is 62%, at 3:00 66%, at 1:00 73%, at 0:30 81%; three ahead at 3:00 89%. The frag that
  breaks a level score with 30 seconds left pays 2.5 times an opening frag; a frag when five ahead with a minute left
  pays nothing.
- **For the owner**: the pros' pairings are uneven, so in their games a lead also says who is the better player; between
  equal players one ahead at 10:00 is 58%, not 62%, and the late level-breaking frag is worth 4 opening frags, not 2.5.
  His own games are between near-equals. The table can be the pros' as it is, the same model for equal players, or
  counted from his own league games (a collector for those is not built).
- **Whole games fill slowly.** A ten-minute game is 4.8 hours of a run at today's speed and a late round 1.4 hours; a
  restart of the trainer loses every game in progress. Starting some matches in the middle of a game at a run's start
  would cure it and is not built.
- Whole games are duels only (17 of v0.2's 30 simulators); a network trained on them needs the game's clock and score
  on a server and in the checks, which neither has yet.

## Part 5. The pros' choices as a small standing pull

Owner: "yes". After part 2. A table from the demos: by situation (his stack band, the enemy's time alive, the items
due), the share of the pros' next targets (an item, a place). A small constant weight on the distance between his
choice of target and that table, in place of the item rule's lesson where the table has enough lives. Not built before
parts 1 to 4 have run.

## The order of merging and the first run

Each part arrives as a patch script against the simulator and the trainer as they stand in v0.2, with its own checks
(fixed runs unchanged with its switch off; its numbers with the switch on). After v0.2 ends: part 1 first (it changes
no behaviour), then 2, then 4, then 3; a ten-minute dry run after each; the run after v0.2 takes what has passed.
Stage C (his legs as a part of the one network that can run and look; the judge) is specified when v0.2's numbers on
his legs are in.

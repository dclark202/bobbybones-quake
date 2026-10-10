# After v14: the scope of what comes next

Written 2026-10-09 while `duel_gru_v14` trains, at the owner's request ("Scope out changes after the v14 run has been set
up"). Nothing here is built or decided. Sources: his notes after his games against v13
([RESULTS.md](RESULTS.md) 2026-10-09 20:05), [BACKLOG.md](BACKLOG.md) B-188 to B-192.

## Where he is

The owner, 2026-10-09: "currently we have a bot that 'plays quake'. It could beat probably 20% of the people that
regularly play on the FFA server ... someone who actually knows how to play the game will win every time." What a
player who knows the game does to him, in the records of that day:

| What | The record |
|---|---|
| Holds the red armor and the mega; Bobby keeps taking fights from behind (B-188) | Blood Run 0 to 24: the owner had 242 health plus armor at his frags, Bobby's lives lasted 18 s |
| Grenades and plasma, at teleporter exits and from above (B-189) | 6 of 24 and 10 of 23 frags in two games; Bobby held neither for a frame |
| Reads his routes (B-190) | he wanted Blood Run's red armor 16% of his time and took it twice |
| Stays above and out of sight, picks the fights | a friend's free-for-all: 23 to 5 head to head, seen 6 to 11% of the time |
| Moves faster | over 400 units a second 20% of the time, Bobby 3% |
| An empty weapon in hand (B-192) | 3% to 15% of his time in ten-minute games |

v14 is aimed at the fifth row and at rockets. The rest is this note.

## What v14 decides

- He strafe jumps and fires rockets: the next step is decisions (parts B and A below), in that order of the owner's
  interest ("this is the next step, and really where it gets interesting").
- He does not strafe jump: movement stays first; of this note only part A's scripted opponents and B-192 would go
  beside it.

## A. Opponents that punish what he does

His copies never do to him what people do: they hold no map, fire no grenades or plasma, wait at no exit. Two ways to
put such opponents into his games, the cheap one first.

**A1. Scripted tricks** (days, no new training method). The simulator has scripted opponents with styles and the
Nightmare stand-in. New styles, each a few dozen lines:

- the holder: takes the red armor and the mega on their clocks and comes for him after a frag (B-188);
- the spammer: grenades or plasma into the exit of a teleporter, a door or a stair he is heading for, and down from
  above (B-189); needs the stand-in to fire arcs, which the lead inputs' arithmetic already has;
- the watcher: stands where his usual way to an item can be seen and waits (B-190).

Mixed into 10 to 20% of his games. What it costs: the time to write and check them; the danger is that he learns the
script and not the idea, which is why they are only the start.

**A2. Trained exploiters** (the league training of AlphaStar, small). An exploiter is a copy of his network that plays
only against the frozen current Bobby and is paid only for beating him, under the same human limits. It keeps what he
can already do and looks for whatever beats him most cheaply; nobody has to think of the trick. Then its snapshots go
into his own league (20 to 30% of his games), he trains, and a new exploiter is made against the new him.

- What the trainer needs: an opponent pool given from outside (it has a league of its own snapshots), one side that
  does not learn, and the mix of pools per game. A few days.
- What it costs to run: the GPU carries one full run. An exploiter at a quarter of the size for three or four hours
  between or beside his runs.
- The danger: an exploiter finds the cheapest thing, and that can be a flaw of the simulator and not of his play. Every
  exploit is looked at (a video) before it is fed back; the ones that are flaws get fixed in the simulator.
- The measure it gives for free: how long a fresh exploiter needs to reach 70% of the frags against him. A number for
  "how readable is he" that should rise from run to run.

## B. A head that decides (B-191)

Today: the last output, the intention, picks one of eight (nothing, the mega, the red armor, two yellow armors, three
weapons) once a second; the inputs then show the way there, and progress along it is paid. Everything else, 40 times a
second, is one recurrent network that is trained on windows of under ten seconds. So he has a goal for the next item
and reflexes, and nothing between: no "stay away while he has 240", no "he is on my way", no "not this way again".

**B1. More decisions on the head he has** (the smallest step, no new architecture). The intention gets three more
choices beside the items: hunt (the way to where the enemy was last seen or is likely to be), stay away (the way that
keeps distance and cover), hold (a place: the pros' positions are in `sim/pro_positions`). The mechanism is the one of
the item ways. One more input block and three outputs: the kind of widening done for v13 and v14.

**B2. A second, slower network** (the model expansion). It runs once or twice a second and reads a summary of the
game, not the frame: the item clocks as he believes them, both players' health, armor, weapons and ammo, where he is
and where the enemy was last seen and how long ago (as map cells), the score and the clock, what the last fights cost.
Its memory covers minutes: at one or two steps a second a window of 256 steps is two to four minutes, where the fast
network's is six to ten seconds. It outputs the decision of B1; the fast network carries it out, as it carries out the
intention now.

**B3. Attention over things** in place of fixed input slots: one small vector per item (kind, clock, distance, the way's
length), per enemy (last place, time since, what he holds), per missile and dropped weapon in view, pooled by attention.
It serves both networks, takes any number of players and items, and is where "this exit is being spammed" can be read
(missiles near a place on his way).

**How it would be trained.**

1. Offline first, no risk: from the pros' demos (150 or more a map, already converted), can the summary of B2 predict a
   pro's next goal? If it cannot, the summary lacks something, and we know before a single training run.
2. The slow network starts from that predictor, then learns by self-play on the game's own pay, counted over its
   one-second steps, with the fast network held still at first (a new teacher moved the whole network in its first
   updates twice; the same care here).
3. Then both together, with the exploiters of A2 in the league: decisions only get better against opponents that
   punish bad ones.

**What it costs.** The attention block runs 40 times a second for about 10,000 players in training: 30 to 40 things, 64
numbers each, one or two layers, or the trainer slows down more than the third it can afford. The server computes the
network in numpy; attention is a few matrix products more. B1 is a run's preparation like v14's. B2 and B3 are two to
three weeks of building and checking before a first run, and the first run will likely play worse than the one before
it for a while.

## C. Small things that can go beside either

- B-192: the empty weapon. The weapon teacher's label when the weapon in hand is empty; some rounds of ten minutes or
  with lean ammo.
- B-190's measures: how often a trip repeats the last way, what he does when the enemy was last seen on it.
- Maps: Toxicity (he died by the map 9 times in one game there) and Cure into training once v14 has shown what the
  held-out maps give.

## A proposal for the order (the owner's to change)

| Run | If v14 gives strafe jumping and rockets | If it does not |
|---|---|---|
| v15 | B1 (hunt, stay away, hold), A1 (the three scripted styles), B-192; beside it, offline: B2's predictor on the pros' demos | movement again, with A1 and B-192 beside it |
| v16 | B2 and B3 (the slow network, attention), A2 (exploiters) | B1 |

Decisions he would have to make before v15: which of A1's styles; whether hunt, stay away and hold are the right three
decisions; how much of his time goes to scripted opponents; whether a run that plays worse for a while (v16) is
acceptable before the reviewer's visit.

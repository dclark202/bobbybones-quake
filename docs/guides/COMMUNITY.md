# BobbyBones: play him, and help set his limits

BobbyBones is a Quake Live bot that is learning the game from scratch. Nobody told him how to aim, dodge or pick
a weapon: a neural network plays millions of fights against copies of itself in a simulator of the game, and
what works stays. He is not the game's bot with new settings, and he never trains against the game's bots.

He plays under human limits on purpose:

- **Human physics.** The same 125 fps movement you get.
- **Human eyes.** He sees only what is in his field of view with a clear line, hears roughly what you would hear,
  and gets no readout of your health.
- **Human hands.** One finger per key with time between presses, a hand that tires, no more than five clicks a
  second, a mouse with reaction time and shake.

The open question is **how good those hands and eyes should be**, and that is where you come in. Until now his
limits were guesses. On the first measurement against a real player he kept his lightning gun on a strafing target 62% of the
time where the player managed 40%, and being shot at cost the player half of that while it cost him a third. We would rather set him from what players can actually do than keep guessing.

## Where he is

- Fights in a small arena look like Quake: he strafes, uses cover, switches weapons, and beats the game's
  Nightmare bot there about 25 to 11 in five minutes.
- He barely uses rockets, does not time items yet, and knows one small map. Map knowledge is the next thing he
  has to learn.
- The long-term goal is a fair opponent on the real duel maps, and later one that can adapt to a new player's
  level.

## How to join

1. Nothing to install: the two custom maps download by themselves when you join (Steam Workshop item
   [3814411166](https://steamcommunity.com/sharedfiles/filedetails/?id=3814411166)).
2. Start Quake Live and connect: `connect <server address>` in the console.
3. One player is measured at a time. If someone is already playing, watch and wait for your turn.

The server stays in warmup: no clock, no score, play as long as you like.

## What to do there

Type these in chat.

| Command | Where | What happens | Time |
|---|---|---|---|
| `!reflex` | test lab | The aim test, below | 3.5 min |
| `!movement` | test lab | Every movement course in a row, timed, with a table at the end | 6 min |
| `!duel` | test lab | Five minutes against him in a small room, full weapons | 5 min |
| `!map arena1` then `!duel` | arena | Five minutes against him on his training map: you spawn with the machine gun and fight over the mega health, the red armor and the weapons | 5 min |
| `!map testlab` | anywhere | Back to the test lab | |
| `!note <text>` | anywhere | Tell us something: "he never looks up", "aim feels unfair at range", "stuck in the corner" | |
| `!room off` | test lab | Stops a test that is running | |

### The aim test (`!reflex`): the one we need most

Four short rooms. Aim and move exactly as you normally would: good players aim with their feet as much as with the mouse, and that is what we want to measure. In three of the rooms the target shoots back for the second 20 seconds (you cannot die), so we can see what being shot at costs your aim.

| Room | Weapon | The target | What we learn |
|---|---|---|---|
| slow | lightning gun | walks slowly from side to side | how steady you hold on an easy target |
| track | lightning gun | strafes and turns round without warning | how far your crosshair runs behind, and how soon you follow a turn |
| flick | railgun | jumps to a new place every few seconds | how fast you react, how fast you get there, whether the first shot hits |
| rocket | rockets | strafes and turns round without warning | how you lead a moving target |

Run it two or three times; the first run is always a warm-up.

### The training arena

A small two-level map built for him: a tunnel, a closed room, balconies and a catwalk, a jump pad, a teleporter,
a lava pit, and a drop on the south side that kills. The red armor stands on an island over that drop: there is
a safe walkway round to it, and a circle jump straight across that saves time.

## What we need, and why

| What | Why |
|---|---|
| **Aim test runs from players of every level** | His reaction time, tracking and flick speed are set from these. Right now the benchmark is one player; we want the middle of many, and the range from new players to very good ones. |
| **Movement course times** | A human bar for movement, so we can tell whether his strafe jumping is good or just looks good. |
| **Duels, and what you notice** | Numbers do not show what feels wrong. A note that says what he did and when is worth more than a score. |
| **Honest verdicts on fairness** | If he hits shots a person could not, or sees things a person could not, we want to know. That is a bug, not a feature. |

## What is recorded

- Every frame of your session on the server: positions, where you look, which keys and buttons are down, health,
  weapon; and every hit, pickup and test result.
- Aim test results are filed under an anonymous id: a scrambled code made on the server, so your second visit
  matches your first without your name or Steam ID being stored with the results.
- The data is used to set his limits and to judge him. Results may be published as numbers ("median player:
  190 ms") without names.

## Everything is open

Code, the simulator, the maps, every result including what did not work:
<https://github.com/dclark202/bobbybones-quake>. The log of experiments is `docs/RESULTS.md`; what the network
is given as input is listed in `docs/INPUTS.csv`.

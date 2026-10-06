# Play-test routine

Two parts: play Bobby (about 20 minutes), then run the test chamber on yourself (about 20 minutes). Everything is
logged per frame; your notes are what the numbers cannot show. Log formats: [LOGS.md](LOGS.md).

## Before you start

```bash
bash tools/duel_server.sh <run> bloodrun <env module>     # e.g. duel_gru_v3 bloodrun duel_env_v3
```
- Connect to port 27970 (`connect 127.0.0.1:27970` in the console). No password.
- The server stays in warmup: no clock, no score, endless play. Both players spawn with every weapon and one
  pickup's worth of ammo (this is not true to the game; items and weapons still respawn normally).
- Chat commands: [COMMANDS.md](COMMANDS.md). To watch him against a Nightmare bot: `!spar`.

## Part 1: play him (about 20 minutes)

| Step | Time | What to do | What to watch for |
|---|---|---|---|
| 1 | 5 min | Blood Run, play to win | Baseline. How does it feel? Fair? |
| 2 | 1 min each | Passive checks: stand still in the open; strafe slowly at mid range; break line of sight around a corner; stand on high ground and let him come | Does he find you, track you, follow you, take a bad fight from below? |
| 3 | 2 min | Keep your distance (rail, LG at range) | Does he close the gap, switch weapon, or keep shooting the shotgun? |
| 4 | 2 min | Rush him with rockets | Does he back off, dodge, fight back? |
| 5 | 2 min | Ignore him and run the big items (mega, red, yellow) | Does he contest them, time them, or wander? |
| 6 | 3 min each | `!map aerowalk`, `!map campgrounds`, play to win | Does he know these maps as well as Blood Run? |

Notes: type `!note <tag> <text>` whenever something stands out. The note is stamped with both positions,
health, his weapon and whether he could see you. Tags (first word): `aim`, `move`, `weapon`, `items`,
`position`, `stuck`, `unfair`, `weird`, `good`.

Questions to answer at the end (as notes or in chat):
1. Did his aim feel fair, too strong, or too weak? At which range?
2. What is the single dumbest thing he does?
3. What would a decent player punish first?
4. Anything that looked like a bug (stuck, not shooting, spinning)?

## Part 2: the test chamber (about 20 minutes)

Bobby's body becomes the scripted target or opponent and **you** are measured, with the same metrics the
simulator uses for him. This gives the human bar for each room. All commands: [COMMANDS.md](COMMANDS.md).

1. `!map testlab` (the test map: an aim box, an environment box with pillars and cover, and four movement courses).
2. `!room suite`: 31 rooms, back to back. `!room off` stops it at any time.

| Rooms | What happens | What to do |
|---|---|---|
| 21 aim rooms, 25 s each in the aim box and 45 s in the environment box | Seven weapons (no grenade launcher), three rooms each: target walking at random, target walking and jumping, target in the environment box. Endless ammo; the target never shoots or dies | Hit it as much as you can |
| 9 movement courses, up to 30 s each | Speed straight, circle-jump gaps, two-hop gaps, ramps and stairs, slalom, turns, narrow path, pillars, rocket jumps. Gauntlet only (rocket launcher in the rocket course). A course ends when you reach the far end | Get as far as you can, as fast as you can |
| 1 fight, 60 s | In the environment box against the game's Nightmare bot, every weapon in hand | Play to win |

Each room counts down 5 s and prints your result in chat. Single rooms for repeats: `!rooms` lists them.
Repeating a room averages your results; two or three runs of the suite give a steadier baseline.


Your card is saved to `data/duellive/suite/human_<time>.json`; the session with every frame and note is in
`data/duellive/sessions/`. The stock maps have their own, older set of rooms (see COMMANDS.md).

## The aim reflex test (about three minutes)

A short test of hands and eyes only, for setting Bobby's aim limits against real players. `!map testlab`, then
`!reflex`. Stand where you are put; nothing shoots back; two or three runs give a steadier result.

| Room | Weapon | Target | What it measures |
|---|---|---|---|
| slow, 20 s | lightning gun | walks slowly from side to side | steadiness: aim error, hand jitter (a standing target would be hit every time) |
| track, 40 s | lightning gun | strafes, turns at random moments | how far the view runs behind, how soon a turn is followed, aim error |
| flick, 45 s | railgun | jumps to a new place every 2 to 3 s | time until the view starts to move, time until it is on the target, turn speed, first-shot hits |
| rocket, 30 s | rockets | strafes, turns at random moments | damage a rocket, how far ahead of the target the aim is |

```bash
python tools/reflex_report.py --bobby <run>      # everyone who ran it on this server, side by side with Bobby in the simulator
```
Players are listed by an anonymous id (a salted hash made on the server; no names or Steam IDs are stored with
the results). Times come from 25 ms frames: single values are no finer than that, medians over many events are.

## Running the test suite on Bobby (simulator)

```bash
python sim/test_suite.py --run <run>                                   # all rooms, three maps (about 25 minutes)
python sim/test_suite.py --run <run> --quick                           # one map, short rooms (a few minutes)
python sim/test_suite.py --run <run> --policy <checkpoint.pt>          # a specific checkpoint
python sim/test_suite.py --run <run> --compare <earlier card.json>     # shows the change per metric
python sim/test_suite.py --run duel_gru_v3 --env duel_env_v3           # an older run needs its own simulator module
```
The card is printed and saved to `data/sim_runs/<run>/suite/card_<minutes>.md` and `.json`. Room names and
metrics are the same as on the play-test server, so the two cards can be read side by side.

Differences to keep in mind when comparing: Bobby's numbers are simulator numbers; live targets have endless
health (kills = damage / 125); your hits are derived from damage and ammo used.

## After the session

Tell Claude you are done. It reads the session and the card, compares your card with Bobby's, and updates
RESULTS.md and the backlog before the next training run.

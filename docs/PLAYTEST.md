# Play-test routine

Two parts: play Bobby (about 20 minutes), then run the test rooms on yourself (about 25 minutes). Everything is
logged per frame; your notes are what the numbers cannot show. Log formats: [LOGS.md](LOGS.md).

## Before you start

```bash
bash tools/duel_server.sh <run> bloodrun <env module>     # e.g. duel_gru_v3 bloodrun duel_env_v3
```
- Connect to port 27970. In the console first: `password <value>` (the `DUEL_PASSWORD` line in `data/owner.env`).
- The server stays in warmup: no clock, no score, endless play. Both players spawn with every weapon and one
  pickup's worth of ammo (this is not true to the game; items and weapons still respawn normally).
- Chat commands: `!note <text>`, `!drill <weapon|off>`, `!map <bloodrun|aerowalk|campgrounds>`, `!room ...`, `!rooms`.

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

## Part 2: test rooms on yourself (about 25 minutes)

Bobby's body becomes the scripted target or opponent and **you** are measured, with the same metrics the
simulator uses for him. This gives the "decent human" bar for each room.

- `!room suite` runs the standard set: 12 aim rooms (LG, rail, rockets against a still and a fast target at mid
  range, and the fast target at close and far range), 3 weapon-choice rooms, movement, solo, and 4 ladder
  opponents (allround, sniper, rusher, tracker). About 25 minutes. `!room off` stops it at any time.
- Each room counts down 5 s, then runs 40-120 s and prints your result in chat.
- Aim and weapon-choice rooms move you to a new spot every 10 s, roughly facing the target, with fresh ammo.
  The target never dies and never shoots. Just shoot it as well as you can.
- Weapon-choice rooms: you have every weapon. Use whatever you think is right for the distance.
- Movement room: the screen names an item ("Go to: Mega Health"). Get there as fast as you can; the next goal
  follows. Weapons are taken away.
- Solo room: two minutes alone. Collect what you would collect in a real game. Do not shoot Bobby (he stands still).
- Ladder rooms: a two-minute fight against a scripted opponent of one style. Play to win.

Single rooms, for repeats or weapons outside the suite:
```
!room aim <lg|rg|rl|pg|sg|hmg|mg> <still|slow|fast|jump> [close|mid|far]
!room choice <close|mid|far>
!room move        !room solo
!room ladder [allround|sniper|rusher|tracker|dodger|stander|jumper|spammer]
```
Repeating a room averages your results. Running the suite two or three times gives a steadier baseline.

Your card is saved to `data/duellive/suite/human_<time>.json`; the session with every frame and note is in
`data/duellive/sessions/`.

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

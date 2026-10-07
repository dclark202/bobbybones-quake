# BobbyBones: plan

Long-term goal: a Quake Live bot that **learns** to play (movement, aim, tactics) and beats people fairly:
human physics, human-like limits, knowledge only from sight and sound. The current target is Goal 1 below: one
small arena, played like a person would play it. Judge by how the play looks (videos, play tests), the
Nightmare score, and numbers for items and movement on that map.

## How the docs fit together (keep them in sync)

| File | Holds | Updated when |
|---|---|---|
| [PLAN.md](PLAN.md) (this) | Approach, where we are, what is being worked on now, owner decisions | The approach, status or "Now" list changes |
| [BACKLOG.md](BACKLOG.md) | Every open, planned and finished work item, with an ID (`B-nn`) and priority | An item is added, started, finished or dropped |
| [RESULTS.md](RESULTS.md) | Dated log of what was tried and what happened, including what did **not** work | Every training run, live test or measurement |
| [PLAYTEST.md](PLAYTEST.md) | The play-test routine and how to run the test suite | The routine or the rooms change |
| [COMMANDS.md](COMMANDS.md) | Every server chat command | A command is added or changed |
| [HOSTING.md](HOSTING.md) | How to rent and start a public server | The hosting setup changes |
| [INPUTS.csv](INPUTS.csv) | Every input of the network in order, with meaning and scale (written by `tools/list_inputs.py`, checked against the simulator's count) | Inputs are added or changed |
| [LOGS.md](LOGS.md) | Schema of the recorded data (play-test sessions, training metrics, weapon lab) | A log format changes |

Rules: a result entry names the backlog items it settles (`B-nn`); a backlog item marked done links to the
result that showed it; the "Now" list below only contains backlog IDs. One change = all three touched in the
same commit.

## Approach

1. **Learn in a fast simulator, verify in the real game.** The simulator (`sim/`) runs the same physics
   thousands of times faster than real time. Every learned skill gets a live check before it is trusted.
2. **Learn from people.** Pro duel demos and the owner's play-test sessions teach what good players do
   (imitation). Self-play reinforcement learning then improves on it.
3. **Measure against people.** A fixed test chamber scores Bobby and human players in the same rooms; play tests
   and (soon) a public server give the human side. Nightmare is a milestone, not the gate.

## Status (2026-10-05)

| Stage | What | Status |
|---|---|---|
| 1 | Movement simulator (Q3 Pmove + collision, QL settings, jump pads, teleporters) | done, validated |
| 1 | Movement policy: strafe jumping emerged, transfers live (time ratio 1.01) | done |
| 2 | Simulator-built nav graphs, one movement policy on three maps | done (live 67-100% of trips) |
| 3 | Duel simulator: nine weapons, items and pickups, switch time measured on a real server; sounds, clock, crouch, walk, fall damage; human aim limits | done; unmeasured values listed in B-14, B-37, B-53 |
| 3 | Self-play with memory (GRU, league, scripted opponent styles) | `duel_gru_v3` done (489 min); `duel_gru_v4` done (775 min, self-play only since 650 min) |
| 3 | Play-test server: plays a trained network, session logs, notes, test rooms with a human as the subject | done, including networks trained under the newer rules |
| 3 | Test suite: fixed rooms and scorecards, in the simulator and on the server; test map `testlab` | done (aim rooms, nine movement courses, Nightmare fight); first human card recorded |
| 3 | Human limits: five-finger left hand, right-hand click limits, sight only in the field of view, aim limits | done (`duel_gru_v5`, B-83 to B-85) |
| 3 | A network that beats Nightmare | in the environment box: yes, 23-11 to 32-10 in five minutes (`duel_gru_v5`). On Blood Run: not yet (`duel_gru_v4` 6-21 in ten minutes) |
| 3 | Goal 1: the yard with items, map knowledge, up to four players | simulator and map built (B-86, B-87); the owner reviews the map first |
| 4 | Pro demos | 3,700 downloaded for three maps, Blood Run converted; a night of movement imitation made courses faster, duels no better (RESULTS 2026-10-04 21:12) |
| 5 | Public servers and community play tests | scoped (HOSTING.md); waits for a decent Bobby and the plugin update |
| 6 | Opponent profiles, player reports | later |

## Goal 1 (owner, 2026-10-05)

The first target is smaller than "a duel bot on the popular duel maps":
1. Plays human-like Quake (no key spam, steady aim, looks where it matters).
2. In one small arena: the yard (map `arena1`, chosen by the owner 2026-10-05; he reviews the map before it
   goes into training).
3. Shows knowledge of that map and moves efficiently on it.
4. One against one, or all against all up to four players, whichever brings out the behaviour better.
5. Beats Nightmare there (done: 23-11 to 32-10 in five minutes, RESULTS 2026-10-05).

The duel maps (Blood Run, Aerowalk, Lost World) are folded back in once he meets these consistently. The
owner's favourite mode is free-for-all with three or four players. Map knowledge is the hard part: it is
deciding, not reacting, and it is also what makes the game fun and the goal interesting (owner).

How each point is measured: 1 by the videos and the key numbers (asked against made); 3 by the share of mega
and red armor spawns he takes and how soon, whether he is on his way before they appear, speed between fights,
use of the jump pad and teleporter, and whether he fetches a weapon after a machine-gun spawn (B-89); 5 by five
minutes against Nightmare at each checkpoint.

## Now

`duel_gru_v9` trains from 2026-10-06 20:42 until 16:00 on the 7th (owner's call) on seven maps with the map reader
(see "Next round" below; RESULTS 2026-10-06 evening): intention head seeded by a simple item rule, rocket drills,
perception noise 0.6 degrees and hand noise 0.10 (tuned up after the reflex comparison with the owner). v8 ended
17:49: 18-30 against Nightmare at the end, human-like play by the owner's account, items still untouched (the
approach-farming found and fixed). The public server runs v8 in free-for-all with three Bobbys: no quad, no item
timers, weapons back in 2 s, a real game when more than half of the people ready up. The morning's `duel_gru_v7` did
not take items at any pickup reward; the night's `duel_gru_v6` hid.

Open: B-102 (a stacking runner in the league, if the intention collapses to "nothing"), fading the item rewards out
once items are fought over, B-92 (more players for the benchmark), B-95 (key budget), B-99 items 6 to 8, `arena2`.

## Next round: `duel_gru_v9` (scope agreed 2026-10-06 afternoon; built after the 19:00 review)

1. **Map reader (B-104)**: nav graphs for the 62 maps of `docs/MAPS.md`; per map a raster and computed labels (travel times, line of sight, item distances, surroundings, pro positions); a ~50k-weight conv trained on all 62; its 16 numbers per cell written as the per-map cell table that fills the two existing cell inputs. Frozen in training at first. Held-out check on unseen maps.
2. **New inputs** (419 -> ~448): item respawn sounds (4), spawn points (12), the other two enemies' weapons (4), HMG back (9). Dense view only as a reduced-scale A/B alongside.
3. **Maps for play**: arena1 + aerowalk, bloodrun, lostworld, furiousheights, campgrounds, sinister (owner's pick); the other 55 are reader training and held-out tests.
4. **Groups**: 2, 3 and 4 on every map (owner 2026-10-06).
5. **Spawns**: the game's (MG + gauntlet, no armor) in 3 of 4, a weapon set otherwise, drawn only from the weapons that lie on that map; a quarter of spawns with a random stack (health 100 to 200, armor 0 to 150) so the value of armor is learned in fights (owner agreed 2026-10-06).
6. **Rewards**: as v8 12:52, with a **claw-back**: what a trip toward the chosen item has paid is taken back if he switches away or dies before taking it (v8 farmed the approach: mega chosen 26% of the time, reached on 1.7% of trips, abandoned 74%); halve the pickup and way rewards once mega + red exceed 0.3 per player-minute on arena1. **Near-item spawns**: a quarter of training spawns within about 2 s of the mega or the red armor, so he tastes the stack and learns its worth from the fights (owner agreed 2026-10-06). Later: the intention head imitated from pro demos (which big item a pro is heading for).
7. **Limits**: reaction and tracking caps unchanged; perception noise 1.0 -> 0.6 degrees and hand noise 0.14 -> 0.10 (owner, 2026-10-06 evening, after v8 measured wider than him on a strafing target with the same reaction). The LG trigger artefact on the server fixed. 384-step sequences, gamma 0.999, lr over 24 h. Intention head seeded by a simple item rule for the first four hours (owner: "seeding is fine here"); rocket drills in a tenth of the rounds.
8. **Start** from v8's last checkpoint by name (`reshape_policy`).
9. **Hourly**: the usual table per map, Nightmare on arena1 and bloodrun, heat maps, one held-out-map probe a night.
10. **Public server** stays on v8 until v9 beats it against Nightmare and the owner has played it.

## Owner decisions

- Maps: Blood Run (ZTN), Aerowalk, Campgrounds only, until told otherwise.
- Human physics only (125 fps); no bot-only frame-rate tricks.
- Human-like reaction and aim limits; never miss on purpose; no wallhacks. Since 2026-10-04: 200 ms to notice
  an enemy who comes into view, 50 ms tracking delay, flick speed cap, hand noise that grows with turn speed,
  a random delay after slow-weapon reloads. His aim may sit a bit above a decent human's, not far above.
- Aim should be smooth like a mouse but allow flicks.
- Rounds and spawn weapons are not true to the game yet (short rounds, random or full loadouts); accepted for
  now to coax out behavior, flagged as B-56.
- Spawning with the full weapon set is fine while learning to aim; items must be picked up. Ammo as a scarce
  resource comes later ("getting him to not suck first").
- Weapons were validated against the real game before training was trusted; keep doing that for new mechanics.
- Pro demos: Blood Run and Aerowalk first; fetch more only if needed.
- Sharing (2026-10-04): post to the Quake community once Bobby is decent (after the next run), with a video,
  a public server for playing him and one for the test chamber, a how-to-help page and a results page
  (B-61 to B-65). This replaces the earlier rule "no public server until he beats Nightmare".
- Log as much as possible from human-played rounds.
- Long-term focus (2026-10-04): smooth, efficient movement that keeps speed, and good choices of position and
  weapon, not just good aim (BACKLOG B-42 to B-46).
- The test chamber is the yardstick (2026-10-04): the owner, a novice friend and later the public run the same
  rooms; Bobby's aim limits are tuned against those cards. New rooms are tried by the owner before they go into
  training.
- Map knowledge should not live only in the network's weights: an atlas per map with several learned routes per
  item, seeded from pro play (B-72, B-75), then a value map (B-73).
- Pro demos come after self-play has gone as far as it can; first use is routes and positions.
- Third map is Lost World, not Campgrounds (2026-10-04): more played, and it has elements he has not seen.
- The game's bots are a benchmark only (Nightmare, ten minutes per checkpoint); he trains against himself.
- Spawn weapons are only those that lie on the map.
- Goal 1 (2026-10-05): the yard, human-like play, map knowledge, one against one or up to four players,
  beating Nightmare there. The duel maps wait until he meets it consistently.
- Method (2026-10-05): limit what he can do until the right play appears; do not reward single behaviors (speed,
  dodging). Changing the reward is the owner's call.
- No personal data in the repo.

## How to run (short)

```bash
sim\build.bat                                              # Windows: build sim\qsim.dll (MSVC)
python sim/train_duel_rnn.py --run <name> --minutes 600    # self-play with memory (GPU if available)
python sim/test_suite.py --run <name> [--compare card.json]   # standard test rooms, one scorecard
bash tools/duel_server.sh <run> bloodrun <env module>      # private play-test server, port 27970
SPAR=1 bash tools/duel_server.sh <run> bloodrun <env module>   # same policy against a Nightmare bot, no port
python sim/validate_weapons.py                             # simulator weapons vs real-server measurements
python sim/train_move.py / eval_move.py / export_policy.py # movement-only policies (stage 1-2)
```
In the play-test server chat: `!note <text>`, `!drill rl|rg|lg|off`, `!map <name>`.
Maps are extracted from the game's pak into `data/maps/` (never committed). `data/` is git-ignored.

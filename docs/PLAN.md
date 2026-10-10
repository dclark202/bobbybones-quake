# BobbyBones: plan

Long-term goal: a Quake Live bot that **learns** to play (movement, aim, tactics) and beats people fairly: human
physics, human-like limits, knowledge only from sight and sound. The target since 2026-10-09 (owner): human-like play
on the game's own duel maps, one against one and all against all with up to six players. Trained on Blood Run,
Aerowalk, Lost World, Sinister, Furious Heights and Battleforged; Campgrounds, Hektik, Toxicity and Cure are held out
for checks. Judged by how the play looks (videos, play tests), by duels against the last best network and against the
Nightmare stand-in, by real games against the game's Nightmare bot on a free PC, and by what people do to him on the
public server.

What lives where in `docs/`, and the routine that keeps it so: [README.md](README.md). The plan as it stood until
2026-10-10 (the status table of 2026-10-08, Goal 1 and the yard, v11 to v13 as proposed and as done, the suite after
the audit, the seeding plan): [archive/PLAN_2026-10-10.md](archive/PLAN_2026-10-10.md).

## Approach

1. **Learn in a fast simulator, verify in the real game.** The simulator (`sim/`) runs the same physics
   thousands of times faster than real time. Every learned skill gets a live check before it is trusted.
2. **Learn from people.** Pro duel demos and the owner's play-test sessions teach what good players do
   (imitation). Self-play reinforcement learning then improves on it.
3. **Measure against people.** A fixed test chamber scores Bobby and human players in the same rooms; play tests
   and (soon) a public server give the human side. Nightmare is a milestone, not the gate.

## Status (2026-10-10)

| What | Where it stands |
|---|---|
| On the public server | `duel_gru_v13` ([runs/REPORT_v13.md](runs/REPORT_v13.md)): free-for-all, two Bobbys, the ten duel maps in the vote, a leaderboard since 2026-10-09. Against people so far: 19 frags made, 130 taken (three players) |
| In training | `duel_gru_v14`, third start, 2026-10-10 08:06 to 19:00 at the latest ([runs/MANIFEST_v14.md](runs/MANIFEST_v14.md)). The second start lost to v13 head to head (36% of the frags) and was stopped ([runs/MIDRUN_v14.md](runs/MIDRUN_v14.md)) |
| The checks of a run | every save plays the last best network head to head (the owner's standing rule, 2026-10-10) and 32 ten-minute duels a map against the Nightmare stand-in; real games against the game's Nightmare bot before and after a run; play tests |
| The simulator | movement, nine weapons, items, sounds, the human limits on hands, eyes and aim; set right against the game's maps on 2026-10-09 (twelve mismatches). Its targets are easier to hit with a rail than people are (B-199) |
| Items and weapons (v13) | time without a big weapon 18%, red armor 0.63 a player-minute; 70% of the frags against the stand-in on the six maps; the game's Nightmare bot beaten on Blood Run (14-4, 11-6, 10-3) and Lost World (8-5, 6-4, 9-5) |
| Strafe jumping and speed | not there: he moves at 290 units a second, fast in the air a tenth of the time. A strafe-jumping teacher gave half of the lesson in item runs and little of it in his games (B-200, B-201) |
| Rockets | v13 fights with the rail at every distance (rockets 17% of his frags). Taught the pros' table and playing styles he used rockets (39%) and lost to v13 (B-198, B-199) |
| Plasma, grenades, shotgun | never in his hand (B-189) |
| Game awareness | not begun: he does not hunt, runs the same ways, walks into fire at a teleporter's exit, cannot play from behind (B-188 to B-191). Scope: [design/SCOPE_v15.md](design/SCOPE_v15.md) |
| Aim | one knob (`AIM_LEVEL`, 3 = the owner's reflex card plus about a tenth). On a real server his rail hits 35% of its shots, three people's 32% |
| Pro demos | 3,700 duel demos of five of the maps, as tables: the weapon by distance, the order of items, positions, where they jump |

## Now

**The third start of `duel_gru_v14` is training** since 2026-10-10 08:06 (owner's go at 07:46; RESULTS 08:15; the list in
[MANIFEST_v14.md](runs/MANIFEST_v14.md), section 0), to 19:00 at the latest, with a mid-run report around noon: from v13 again, v13
kept in the league and played first in every check (under 45% of the frags against it twice in a row: stop), weapons
as v13 had them, the strafe-jumping teacher switched on after two clean checks. The second start is kept as
`duel_gru_v14_try2`. The first 80 minutes lost Aerowalk to v13 12% to 88% (the item rule named a red armor only a jump
reaches; fixed at 09:32, level since); the teacher is on since 10:57 with grenade and plasma shots free. Mid-run report:
[runs/MIDRUN_v14c.md](runs/MIDRUN_v14c.md).

**`duel_gru_v15` is being prepared** on the branch `v15` (owner, 10:38: "Start on anything you can with preparing for v15
now while v14 is running ... Ideally I would like v15 to start tonight"): jump runs on the pros' jumps with a teacher
trained on them, grenades and plasma (lives that begin with them, one-weapon rounds, the lobber, the watcher and the
holder among his opponents). What is built and what is not: [runs/MANIFEST_v15.md](runs/MANIFEST_v15.md). It starts on
his go.

**The owner's priority list for the next models (2026-10-10)**: (1) strafe jumping and keeping speed; (2) rockets; (3)
plasma and grenades, the shotgun to a lesser extent; (4) "game awareness": not through a teleporter the enemy watches,
not always the same path, which "needs more model build out" and is "arguably the most important long term" but comes
when the first two or three are there. "Any plan going forward needs to address those, together with any weird
behavior that is showing up mid run/in duels."

**Mid-run of the second start, 2026-10-10 07:00 ([MIDRUN_v14.md](runs/MIDRUN_v14.md))**: as a duelist v14 is weaker than v13: head to head 36% of the
frags on the six maps and 41 games won of 192; against the stand-in 70% -> 58%. Two causes in the run's setup: the weapon
in his hand (he holds what the weapon teacher names, in a styled life at every distance; v13 holds the rail at every
distance and that wins in the simulator) and a league of his own last eight snapshots, without the control (B-197).
Rockets make 35% of his frags; shotgun, grenades and plasma 0.0% in hand; strafe jumping is half-learned in item runs
and hardly there in his games. The owner's answer the same morning: try again, from v13 and with v13 kept in
the league (the third start, above).

The backlog items in work or next, by the owner's list ([BACKLOG.md](BACKLOG.md)):

- The run in progress: B-197, B-195.
- 1, strafe jumping and keeping speed: B-204 (the items behind a jump), B-200, B-201.
- 2, rockets: B-198, B-199.
- 3, plasma, grenades, the shotgun: B-189, B-169.
- 4, game awareness: B-191 (scoped for him on 2026-10-10: [design/SCOPE_v15.md](design/SCOPE_v15.md), part 3), B-190, B-188, B-202.
- Odd behaviour seen in runs and duels: B-192, B-194, B-196.

## Owner decisions

- No powerups, ever (2026-10-09): "FFA maps on the public server, testing, etc. SHOULD NEVER HAVE QUAD ... Make sure it (and protection) are always off, and do not train bobby to do anything with it"; the invisibility on Battleforged too.
- The items of a duel are the only ones (2026-10-09): "use the 'duel weapon locations' for all of the maps ... Even for the public FFA matches and training FFA matches ... Those should be the 'only ones that exist' in our world". On Campgrounds in free-for-all that means the mega where the game puts the quad.
- The simulator has to match the game's maps (2026-10-09): "Fix all 12" of the audit's mismatches, shots through bars and grates among them ("windows or holes in the floor that can be shot through. Make sure those are accurate").
- The duel check: 32 games a map are enough ("Doesn't matter to me"); the stand-in has to be shown to play on a map before a number from it is trusted.
- Maps (2026-10-09): v14 trains on Blood Run, Aerowalk, Lost World, Campgrounds, Sinister and Furious Heights; Cure, Toxicity, Hektik and Battleforged later. arena1 is dropped entirely ("just focusing on the in game duel maps"): no training and no checks on it from v14 on; the maps he has never seen, for checks, are Battleforged and Hektik (owner, 2026-10-09: "Held out maps: battleforged, hektik"); they stay out of training while they serve as that.
- Strafe jumping (2026-10-09): "absolutely crucial to the game, he needs to learn it asap". A teacher that strafe-jumps may name keys and view in movement rounds on the duel maps; a pay for speed from 320 to 480, flat above, aggressive at first.
- Shots with no enemy in view (2026-10-09): firing rockets, plasma and grenades at where he thinks the enemy is, or is about to be, is how they are used and is not penalized; "firing them at nonsense (or not rocket jumping) should be discouraged"; a small allowance for pre-firing a beam. Rockets keep a very low shot price; plasma and grenades have none.
- Lead reading (2026-10-09): he is given where a rocket has to be aimed to meet a moving enemy ("a major part of the game").
- Shotgun, plasma, grenades (2026-10-09): not a priority and no lives that start with them; the weapon teacher is neutral while he holds one; watched.
- Maps (2026-10-07): training on arena1, Aerowalk, Blood Run and Lost World; Campgrounds, Furious Heights and Sinister come back once he goes for items. The public server offers the eight he has trained on.
- Seeding is fine (2026-10-06, 2026-10-07): a simple rule or a scripted player may show him a behavior at a weight that fades (the intention, the walk, next the weapon choice); what stays must hold without it.
- Scripted opponents of our own (the item runner) may be in the league; the game's bots stay a benchmark only.
- One batch of changes, then wait: no changes to a running experiment unless the data is clearly bad; the assistant is to push back.
- Logs from the public server only while a person plays; pulled to the PC daily and then removed from the server; no names.
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
- (2026-10-08) Training moves to the three duel maps; the yard is the check map ("people like the actual maps in the
  game"). Rail lives stay ("pros absolutely do play rail").
- (2026-10-08) Seeding his behavior with fading teachers and tables from the pro demos is fine ("we apparently need to be
  more explicit with seeding him with patterns for play"); the pros' ways as a walking teacher stay out until they beat
  the shortest ways in a test.
- (2026-10-08) Reward and setup calls for v13: a price per shot by weapon and map ("ammo is a scarce resource ... a learned
  behavior to be spam happy or need to conserve"); damage soaked by armor at a third; rounds that start as a race for a big
  item; damage taken at full price; credit horizon 0.98; the key budget at 5 a second ("monitor it as we progress"); no
  rocket drills; no spawns beside the mega or red; jumping encouraged again, informed by the pros ("jumping is how you
  strafe jump which IS a goal").
- (2026-10-08) Aim stays at level 3 of the knob; tuning the levels up and down waits for more people's data.
- (2026-10-08) During a run: brief hourly lines; the full metrics, video, heat map and summary at its end. No changes
  mid-run unless the data is clearly bad.
- (2026-10-08) All docs, the README included, are kept current.
- (2026-10-08 19:30) v13 with the teachers' losses held back from the shared layers (`--teach-trunk 0.05`): "yes".
- (2026-10-08, after his two games against v12) "He plays like a human ... a pretty bad novice who knows how to aim better
  than they know how to play quake. That's fine." Top priority: game sense for items, position, control and weapons; "the
  absolute worst thing we could see in training now is for the item pickups and weapon use to collapse again. If anything
  he should be using more rockets as time goes on." Strafe jumping: a priority, "but that might be a bit ambitious still".
- (2026-10-08) Into v13 on his word: dropped weapons (the start waited for them), the ground at his feet in every
  direction ("not a fairness problem"), the hand at 8 key actions a second ("they need to be deliberate"), pay for knowing
  where the enemy is, pay for pace, a walking teacher of keys only. Not now: a cost for aiming upward.
- (2026-10-08) A run may go to 16:00 the next day; stop it early if something has gone wrong or he has stopped learning. A
  mid-run report when he wakes (07:00), the full report at the end with recommendations for what to try next, hourly
  check-ins, the PC at about 80 to 85%.
- (2026-10-08) Before a run starts he reviews a full report of the last network, a full manifest of the next run and the
  state of the public server, and gives the go himself.
- (2026-10-10) The control in every run: the last best network stays in the league and every checked save plays it head
  to head ("this should be standard going forward, continue to check against the last best version + new iterations").
- (2026-10-10) For the next run he is "inclined to fold in" three things, scoped in [design/SCOPE_v15.md](design/SCOPE_v15.md):
  jump training (a gap course and the named jumps of the real maps; the teacher may train on Campgrounds' and Toxicity's
  jumps), grenades and plasma (the free shots go back in with the teacher's restart of v14's third start), and attention
  for strategy. Also to learn in time: stairs with jump held, and a jump at a ledge that hooks onto it.
- (2026-10-10 10:38) v15 is jumps and grenades and plasma ("Definite yes to jumps and plasma/grenades"), with the shares of
  his rounds as proposed ("I agree with all of those changes": [runs/MANIFEST_v15.md](runs/MANIFEST_v15.md), section 1);
  attention "I really want, but it seems there needs to be more build out": the run after.
- (2026-10-10) The priority list for the next models: strafe jumping and keeping speed; rockets; plasma and grenades
  (the shotgun less); then game awareness. Every plan addresses these and any odd behaviour seen in a run or in duels.

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

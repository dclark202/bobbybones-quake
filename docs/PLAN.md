# BobbyBones: plan

Long-term goal: a Quake Live bot that **learns** to play (movement, aim, tactics) and beats people fairly: human
physics, human-like limits, knowledge only from sight and sound. The target since 2026-10-09 (owner): human-like play
on the game's own duel maps, one against one and all against all with up to six players. Trained on Blood Run,
Aerowalk, Lost World, Sinister, Furious Heights and Battleforged, with movement-only practice on Campgrounds, Hektik,
Toxicity and Cure; the owner wants the ten in training and less played maps held out (2026-10-11; House of Decay is
prepared). Judged by how near his play comes to the pros' measures, verified by the owner's play and by what people do
to him on the public server; by duels against the last best network; the Nightmare stand-in and the game's Nightmare
bot are the floor.

What lives where in `docs/`, and the routine that keeps it so: [README.md](README.md). The plan as it stood until
2026-10-11: [archive/PLAN_2026-10-11.md](archive/PLAN_2026-10-11.md); until 2026-10-10 (the status table of 2026-10-08, Goal 1 and the yard, v11 to v13 as proposed and as done, the suite after
the audit, the seeding plan): [archive/PLAN_2026-10-10.md](archive/PLAN_2026-10-10.md).

## Approach

1. **Learn in a fast simulator, verify in the real game.** The simulator (`sim/`) runs the same physics
   thousands of times faster than real time. Every learned skill gets a live check before it is trusted.
2. **Learn from people.** Pro duel demos and the owner's play-test sessions teach what good players do
   (imitation). Self-play reinforcement learning then improves on it.
3. **Measure against people.** A fixed test chamber scores Bobby and human players in the same rooms; play tests
   and (soon) a public server give the human side. Nightmare is a milestone, not the gate.

## Status (2026-10-11)

| What | Where it stands |
|---|---|
| On the public server | **v0.2** (`duel_gru_v0_2`'s end) since 2026-10-12 15:15 (the owner: "yes send him to the public server"): free-for-all, two Bobbys, the ten duel maps in the vote, a leaderboard with a QLStats lookup. Before it v0.1 (`duel_gru_v15c`'s end) from 2026-10-11 13:01; the owner after playing v0.1: "much better than v14 was"; "strong LG, very strong"; "their main failure point is that their routes are predictable"; "he doesn't know how to push an advantage" |
| The last run | **v0.2** ended 2026-10-12 08:43: level with v0.1 on the six maps both have played games on (48.7%), ahead on the four new to games (59, 58, 59, 75%), his play where it was (scorecard 48% beside the pros). [runs/REPORT_v0.2.md](runs/REPORT_v0.2.md) |
| The next run | **v0.2.1** (`duel_gru_v0_2_1`), prepared, waits for the owner's go (about 21:00 on 2026-10-12): from v0.2's end to 15:00 the next day, in two halves, written around the owner's four goals of that evening (know where the enemy is and act on it; keep speed; rockets; position and high ground). First half: the guessing game at eight questions and twice the weight, the item rule silent where he believes the enemy nearer to its item, places as targets, his own movement taught by his movement network. Second half, on top: more rocket lives, the pros' weapon in hand, a hit from above worth more. His aim is left as it is (the owner: lightning down but rail up, later). On the eight performance cores only (B-238). [runs/MANIFEST_v0.2.1.md](runs/MANIFEST_v0.2.1.md) |
| After it | **The enemy in his head, the next steps** (the owner, 2026-10-12: "pushing him hard to prioritize knowing where the enemy is and how that should inform what he does next"): his answers in the guessing game wired to his choices, opponents that hunt and ambush, games that begin in their middle: B-240 |
| The checks of a run | every save plays the last best network head to head, seats swapped in half of the games since 2026-10-11 (B-220), and the Nightmare stand-in; his speed profile in games; at a run's end the measures beside the pros' (`tools/convergence.py`) and real games against the game's Nightmare bot on a free PC; play tests |
| How near he is to the pros | v15c's end: 48% on fourteen measures (position 65%, speed 82%, weapons 17%, aggression 3%, control 95%); v14's end 39%: the log of 2026-10-11 19:00, [design/V16_APPROACH.md](design/V16_APPROACH.md) |
| Strafe jumping and speed | he strafe jumps on his legs (a second, movement-only network he switches to: v15b). In games: 9.4% of his travelling time at 400 or more, hops 332, 389, 384 (the pros 17.5%; 366, 421, 422). His legs alone reach 356, 405, 410: the limit is how they are used (they carry him 46% of his game time and his chains fall after the second hop) |
| Rockets | 2.1 a minute against the pros' 10.8; none with no enemy in view (the pros: half); in hand 20% of his time. The three changes the owner allowed (half the shot's price, free at the pros' places, half the cost of a wasted one) changed nothing in 165 minutes of training; a seed that presses fire by rule is level in games but its rockets do not hit (B-210) |
| Plasma, grenades | in hand 1.7% and 0.9% of his time (v15c); grenades 0.03 a minute against the pros' 2.2 |
| Game awareness | measured beside the pros: he closes on the enemy at the same speed whatever the enemy's state, takes the commonest way 57% of the time (the pros 43%), stands low. The enemy as a target is built and lost its first trial (B-221). The attention model is designed: [design/V16_ATTENTION.md](design/V16_ATTENTION.md), [runs/MANIFEST_v16.md](runs/MANIFEST_v16.md), [design/V16_TRAINING.md](design/V16_TRAINING.md) |
| Against the game's Nightmare bot, real games | v15c's end 50 frags to 22, v15b's end 54 to 11 (six ten-minute games each on Blood Run, Aerowalk, Lost World) |
| The simulator | movement, nine weapons, items, sounds, the human limits on hands, eyes and aim; set right against the game's maps on 2026-10-09. Its targets are easier to hit with a rail than people are (B-199) |
| Aim | one knob (`AIM_LEVEL`, 3 = the owner's reflex card plus about a tenth). On a real server his rail hits 35% of its shots, three people's 32% |
| Pro demos | 4,449 duel demos of the ten maps: the weapon by distance, the order of items, positions, jumps; since 2026-10-11 the measures of play (`docs/pro_yardsticks.json`), the places their blind shots land (`sim/pro_places/`), their ways as routes (`sim/pro_ways/`). where they look, their holds, their hands, their movement in a fight. The parser and the converter were mended on 2026-10-11 (B-218, B-219); the stored sets are still to be rebuilt |

## Now

The owner's priority list (2026-10-10): (1) strafe jumping and keeping speed; (2) rockets; (3) plasma and grenades, the
shotgun less; (4) game awareness. Since 2026-10-11 the next model is the attention model (v16), judged by "game
awareness primarily. Also how much his movement begins to blend together the two styles fighting/moving"; progress is
read as how near he comes to the pros' measures, verified by the owner's play and, less, by the Nightmare bot.

The backlog items in work or next ([BACKLOG.md](BACKLOG.md)):

- 1, speed: B-211 (his legs in games), B-213 (the real game with legs: three measurements open), B-204.
- 2, rockets: B-210.
- 3, plasma, grenades: B-189.
- 4, game awareness: B-217 (predictable routes), B-216 (offense or defense by the score), B-221 (the enemy as a target), B-191.
- The run in training: B-223 (v0.2).
- The demos and the checks: B-218, B-219, B-220, B-225, B-226.
- His aim, where he looks, the fights he takes: B-228, B-229, B-230, B-231.
- The simulator and the maps: B-224, B-227.
- Odd behaviour seen in runs and duels: B-214, B-215, B-192.

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
- (2026-10-10 noon) v14 ends on its best save; v15 after "the next few hours auditing the new things", with a full
  manifest, "later today or this evening". For projectiles he must "see all projectiles that he should be able to ...
  within his field of vision", not "by wallhacks", "distinguish projectiles and understand their splash damage, timer
  (grenades)", and be "*slightly* encouraged to use plasma and grenades. It should be ~5-10% max". The lobber's timing
  and the grenade measurement are in v15. Rockets: "try parallel arms ... if nothing is obviously working we'll delay
  it". Hektik's, Cure's and Toxicity's jumps are to be listed too ("it might contaminate the purity of the held out map,
  but it's important that he understands how to move around these maps efficiently").
- (2026-10-10 15:38) v15 starts from v14's end; no teacher's labels on Toxicity nor in Lost World's item runs; movement-only
  practice on the four other maps at 7.6% of his time, watched; the one-weapon rounds with grenades and plasma "should be
  temporary just to introduce him to these weapons, monitor and turn them down once he starts to understand them"; the
  36 jumps without tries are built before the start ("Build first"); run length to be asked when the rest is settled.
  Enemy projectiles: "he should only know what's in view or what he can hear. He's allowed to \"suspect\" rockets, but
  that maybe is learned behavior instead": the old rule that showed anything within 400 units is gone for good.
- (2026-10-10 15:28) v14's end goes on the public server with the bots' names and voices.
- (2026-10-10) The priority list for the next models: strafe jumping and keeping speed; rockets; plasma and grenades
  (the shotgun less); then game awareness. Every plan addresses these and any odd behaviour seen in a run or in duels.
- (2026-10-11) v15c's end with his legs goes on the public server ("Push 15c to the live server so I can play against
  him"). Three bots a server are enough if the next model costs more ("if we need to drop to 3 bots max per server that
  is also fine").
- (2026-10-11) The next model is the attention model: "I believe attention will be the secret sauce if we can get it
  right". Judged by "game awareness primarily. Also how much his movement begins to blend together the two styles
  fighting/moving we have now". Whole ten-minute games with pay for the result: "Yes". Training speed: "completely
  neutral". The position token holds the weapon that suits the spot ("Absolutely it should"); places and their strength
  come from the pros' demos. The parser and the converter are mended first: "We should do this right not rush it".
- (2026-10-11) Progress is read as convergence on the pros ("position, speed bursts, combos, aggressive play"), from his
  games against himself, the Nightmare bot as a floor: "targets to aim for as a result of training, to be verified by me
  playing against him and to a lesser extent his performance against nightmare". The pros' numbers lean toward winners:
  "we want to emulate the best behavior anyway".
- (2026-10-11) Maps: the ten duel maps he knows are "the most popular in the game, if we can get those in training (maybe
  hold out dm6 just because there was so little data for it) and use some others for hold out that are less popular
  that's fine".
- (2026-10-11) Rockets: "we can be more forgiving with him for how he uses rockets, reduce the cost slightly"; the three
  changes (half the shot's price, free at the pros' places, half the cost of a wasted one) "but test them first".
- (2026-10-11) Movement stays first: "He needs to maintain speed, and build it more effectively, AND we should be
  thinking about how the two networks will mesh into one over time"; tuned for "more speed per jump, maintaining speed
  for longer".
- (2026-10-11 evening) **Names**: "The v15c bot that exists on the server is now: v0.1. We're building v0.2 currently, any
  exploration phases will get a further index e.g., v0.2.1, etc."; "v1.0 starts when he can beat me." v0.2 is the run
  proposed for the night (ten maps, the rocket changes, the enemy as a target) with stage A of the attention model:
  [runs/MANIFEST_v0.2.md](runs/MANIFEST_v0.2.md); the part that is ready is v0.2.1.
- (2026-10-11 evening) His answers to the day's questions ([design/V16_APPROACH.md](design/V16_APPROACH.md)): Campgrounds in
  training, House of Decay held out, Toxicity stays on the public server's list; the enemy as a target and the rocket
  changes in; a value estimate that counts two minutes ahead with the first attention stage; his aim "overtuned ...
  let's slowly tune it down, using pros as a goal"; "pay him a tiny amount" for speed gained from hop to hop, "but the
  key is getting him to use them and maintain speed"; fights taken and refused as a measure ("his choice of picking fight
  is terrible currently"); the noise he makes with footsteps and stairs ("you make sound on stairs even when walking");
  the gauntlet "ideally he should, but i won't hold up the run for it"; promotion by the control and the scorecard "within
  an amount of noise"; later: a frag paid by what it moves his chance of winning, late-game rounds "up to 25%", the pros'
  choices as a small standing pull, high ground "token first"; the exploiter left out ("Isn't HE the exploiter? He should
  be?").

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

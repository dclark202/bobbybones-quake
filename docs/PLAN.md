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

## Status (2026-10-07 evening)

| What | Where it stands |
|---|---|
| Simulator: movement, nine weapons, items, sounds, human limits on hands, eyes and aim | done and checked against the real game; machine guns scatter since today (value not yet measured on a server, B-107b) |
| Movement: strafe jumping learned from reward alone, transfers to the real game | done |
| Self-play training with memory, a league of his older selves | running; 10,080 players a batch, 37,000 steps a second, 8 to 11 GB of graphics memory |
| Play on a real server: 1v1 and free-for-all with up to four Bobbys | done; public server up (v8), logs pulled to the PC daily |
| Aim against the owner's reflex card | reaction equal (200 ms); error on a strafing target 3.0 to 3.4 degrees against his 2.5; rockets that hurt 41% against 83% |
| **Walking to an item he has chosen** | **learned today in v10**: alone on arena1 he takes what he is told to in 75 to 100% of 30-second rounds (0 to 22% this morning), and kept it without the teacher |
| Taking the mega and the red armor during a fight | not yet: 0.03 and 0.02 a player-minute from a normal spawn on arena1; Nightmare and people take them every time they come back |
| Using rockets | not yet: he picks the launcher up and does not fire it (4% of his frags) |
| Beating Nightmare with the game's own spawn | not yet: arena1 13-27 to 21-30 in ten minutes (he deals more damage and loses on frags: the stack); Blood Run and Aerowalk 0 to 2 frags in five minutes |
| Maps in training | arena1, Aerowalk, Blood Run, Lost World (the bigger three are out until he seeks items) |
| Pro demos | 3,700 downloaded; a night of movement imitation made courses faster, duels no better; not in use |
| Attention over the scene in place of fixed input slots | scoped, the cost on the rented server measured and fine (`ATTENTION_POC.md`, B-109); waits |
| Opponent profiles, player reports | later |

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

**`duel_gru_v10` ran 2026-10-07 13:28 to 19:00** from v9's end: in item runs (30% of the time, alone on the map, the target given as his intention) he was shown the keys a scripted walker would press, and the help faded to nothing by 16:28. Targets taken a player-minute in those runs went from 0.15 to 4.5 and kept rising after the teacher was gone; the solo test on arena1 went from 16 / 0 / 3 / 16 / 22% (mega / red / RL / RG / LG) to 75 / 88 / 100 / 100 / 100%. His aim did not change. Against Nightmare and for items taken during fights nothing has moved yet (RESULTS 2026-10-07 13:28).

How it got there (RESULTS 2026-10-06 evening to 2026-10-07): v9 added a seeded intention, a claw-back, a scripted item runner in the league (B-102), a scattering machine gun and smaller maps, and none of it moved the item numbers; a test of him alone with a fixed goal (`tools/solo_item_check.py`) then showed that he chose the right item and could not walk to it. v8 (18-30 against Nightmare, "feels human" by the owner) is what the public server plays.

Next: the proposal below, for the owner's sign-off. Open besides it: B-107b (measure the machine guns' scatter and the shotgun pattern), B-92 (more players for the reflex benchmark), B-95 (key budget), B-109 (attention), Aerowalk's walking graph (no way to the red armor from most spawns), `arena2`.

## Plan: seeding his behavior from the pro demos (owner, 2026-10-08; proposal, nothing running)

**Why:** three runs say the same thing. A reward alone moved nothing in 17 hours (v9) and 4 hours (v11); a pattern shown by a
fading teacher was learned within three hours each time and kept (the walk in v10, the weapon table in v11).
**Rules for every seed:** a table fitted from play, not frames imitated; a teacher only on the movement keys, the weapon
key or the intention, never on the view or the trigger (v11, 00:39); it fades to zero; it counts as learned only if the
number holds two hours after the fade. Source: `docs/pro_tables.json` (3,266 demos, 505 hours, three maps).

| Seed | From the demos | Teacher | Number that must move (pros) |
|---|---|---|---|
| S1 weapon by distance | which weapon is fired at which distance, per map, owning all three | the weapon key: the pros' first choice in each 100-unit bin among what he owns; where the first two are within 10 points either is left alone | agreement with the table; rockets' share under 400 units (54%) |
| S2 item order | what is picked up next, bare or armed | the intention: a weapon first when bare (rockets when two are about as near), then armor: yellow, red or mega, whichever is up and nearest; **yellow armor becomes an intention** (the output grows from 6 to 7) | time without a big weapon (8%); health plus armor at 150 or more (56% of the time) |
| S3 spawn routine | a big weapon 2.7 s after the spawn (median), in 82% of lives | the keys-only walking teacher from the spawn to the first weapon, also with an enemy in view (the view stays his) | first weapon after (2.7 s; third quartile 5.3 s) |
| S4 style mix and bands | the split of a game and the distance of the fights per weapon | style lives: general, rockets, lightning and rail (owner: "pros absolutely do play rail, keep it"; none on Lost World, which has no railgun); bands from the quartiles (rockets 230-540, lightning 305-620, rail 440-815) | his weapon in hand in a style life |
| S5 the pros' ways | positions along the way from each spawn to each weapon and between the items (the atlas, `maps/atlas/<map>.json`, already holds routes seeded from the demos) | the walking teacher follows the atlas route on the three duel maps, the shortest way elsewhere | arrivals a player-minute; time to the first weapon |
| S6 a pro column | time bare, first weapon, stack, firing by weapons owned | none: a column in the hourly check beside Bobby's | - |

Not seeded: backing off when hurt (weak in the demos), the enemy's health (not in a demo), where he looks, when he fires.
**Limits:** the demos are 1v1 with duel item timing on three maps; arena1 has none (and no yellow armor), and the habits of
a three- or four-player game come from the owner's server logs, which are thin still.
(Correction, same day: the "1% of games lean to the rail" above counted firing frames, and a rail fires once in 1.5 s
where the lightning gun fires every frame. By that count the rail is undercounted; the style split is to be recounted by
time in hand and by shots.)

### The experiment (owner, 2026-10-08: "use the three duel maps as the train and it gets validated on arena1; ideally we move him off arena1")

**Train:** Blood Run, Aerowalk and Lost World only, a third each; no arena1 frames at all. From v12's final weights, seeds S1
to S4 as teachers fading over four hours, S6 as a column. Groups of 2, 3 and 4 as now; machine-gun spawns; overnight length.
**Validate, three layers, the bars written down before the run:**

1. *On the training maps, two hours after the teachers are gone* (the seed was learned, not just followed): time without
   a big weapon at most 25% (pros 8%, now about 70% with machine-gun spawns); first weapon within 6 s at the median (pros
   2.7); 150 or more health plus armor at least 30% of the time (pros 56%); agreement with the pros' weapon table at
   least 70%; fire and frags not under the v12 floor (he still fights). Nightmare on all three, against v12's scores.
2. *On arena1, which the run never sees* (does it carry over?): the same numbers there, each within one and a half times
   its training-map value, and Nightmare on arena1 not below v12's. Honest limit: every network so far was trained on
   arena1, so this shows whether seeding on the duel maps improves arena1 without practice there, not play on a map he
   has never seen. For that, one game map he has never trained on is added to the check (sinister, which people have
   already played on the server; a walking graph has to be built for it).
3. *Positioning against people on arena1:* the logged frames of people playing the bots on arena1 are pooled into a map of
   where they stand (cells of 32 units, and the same by weapon in hand); Bobby's map comes from the fight check. One
   number: the share of his time spent where people spend theirs (overlap of the two maps), plus the distance to the
   enemy and the mega and red taken per spawn (people 25% and 17%; the owner 70% and 54%). v12 is measured first as the
   baseline; the bar is "better than v12". Thin data: about three hours of people in all, part of it on arena1.
4. *The owner plays him* on a duel map and on arena1; a card of each game.

### How the pro data goes into v13 (owner, 2026-10-08: "it should reinforce the work we've started with v12"; pro routes in)

v12 set up the frame with hand-made rules: style lives, a weapon rule, an item rule, a walking teacher on the shortest
way. v13 keeps the frame and puts what the pros do behind each rule; the rewards do not change.

| v12 (hand-made) | v13 (from 505 hours of pro play) | Built |
|---|---|---|
| Weapon rule: rockets 60-300, lightning to 700, rail from 500 | the pros' first choice per 100 units, per map (`PRO_WEAPON`) | yes |
| Item rule: mega, then red, then a weapon; no yellow armor | a weapon first when bare, then the nearest armor or mega; yellow armors as goals (`PRO_ITEMS`) | yes |
| Walking teacher only when no enemy is about | also from the spawn to the first weapon with an enemy in view (`SPAWN_TEACH`) | yes |
| Walking teacher along the shortest way | **along the pros' way**: for each goal, the step the pros took from each place on their trips that ended in picking it up (their positions are in the light demo sets), laid on the walking graph; where fewer than 20 pro trips passed, the shortest way | to build (S5, `PRO_ROUTES`) |
| Style bands and a pay for the distance | no pay for distance; the style still names the weapon to fetch and hold, the pros' table the weapon for the distance in general lives | yes |
| Four styles, a quarter each | the same, rail included; no rail life on Lost World | yes |

Teachers: the weapon key 1.0, the movement keys 0.5, the intention 2.0, fading to nothing over four hours; then at least
four hours without them. Start: v12's final weights carried to 491 inputs. Maps: Blood Run, Aerowalk, Lost World.
**Styles on the public server now:** the plugin draws one of the map's styles for each bot life at random (and logs it).
**Choosing the style himself (v14):** at each spawn his own value estimate is asked once per style and the style is drawn
in proportion (the trainer does it for the players that spawned, the plugin the same way); only after v13 has shown that
all four styles are played and differ.

**Order of work (approved by the owner 2026-10-08 10:10; to be put before him again when v12 ends at 14:00):**
1. 14:00: v12 ends; full metrics, video, heat map, summary, and v12's scorecard per map (`tools/stack_probe.py`) as the baseline.
2. The gate: v12's gains held without the teachers (below).
3. Build the pros' ways (`PRO_ROUTES`) and test them: a pupil who obeys them reaches the first weapon at least as fast as on the shortest ways.
4. The owner plays v12; random styles per bot life on the server if he wants that deployed.
5. v13 starts on his go, overnight.
6. Validation in the three layers above (the training maps against the pros, arena1 held out, people's positions on arena1).

**Risks:** the spawn routine labels about a third of the frames, nearer to the teacher that broke his fighting in v11 (this
one never touches the view): fire and frags are watched in the first hour and the teacher is cut back if they fall. The
pros' ways are 1v1 ways; the fallback to the shortest way and the fade leave him free in a larger game.

**When (owner, 2026-10-08): a separate experiment after v12, not folded into it.** v12 is the crude version (hand-set
rules); its end decides what v13 is. Gate at v12's end: two hours after the teachers are gone, time bare has not gone back
above about 65%, his weapon in hand in a style life has not halved, and he still fights. *Passes:* v13 is the pro seeds as
scoped here. *Fails* (the gains go with the teacher): the problem is keeping, not the tables; v13 first gets a longer
fade or a small standing teacher, and the pro tables come after.
What v12 has shown by its second hour, and what it means for the seeds: (1) only style lives fetch (big weapons held
0.47-0.69 against 0.25 in general lives, which do not move): the **item order** seed, a weapon first for every bare
life, matters most; (2) the fight distance does not separate by style, and hardly does among the pros: the band pay
(`STYLE_BAND`) is dropped for the pros' **weapon-by-distance** table (the weapon for the distance, not the distance for
the weapon); (3) the first weapon comes after 8 s against the pros' 2.7: the **spawn routine**; (4) the style states
themselves stay as in v12, rail included. Baseline: v12's final numbers split by map, so that on the three duel maps
the only change in v13 is the seeds.

**After it:** if layers 1 and 2 pass, the public server's default map becomes a duel map and arena1 stays as a check only.
Then the pros' ways (S5), the style chosen by himself, and free-for-all habits from the server logs.

## Proposed: `duel_gru_v12`: playing styles and machine-gun spawns (owner's idea of 2026-10-08; built, waiting for his go)

Every life he is in one of four states, given to him as four inputs (487 inputs now): **general**, or a preferred weapon
(**rockets, rail, lightning**), a quarter each (`STYLE_P` 0.75). With a preferred weapon: the item rule sends him for it
first; the weapon teacher names it at every distance once he has it (general keeps the distance table); damage with it
pays half as much again (`STYLE_DMG`); and half a frag a minute while the enemy is in view inside its band with it in
hand (`STYLE_BAND`; rockets 60 to 300, lightning 150 to 700, rail from 500). Together with: a machine-gun spawn in every
life (`ARENA_SETS=mg`, `--loadout-p 0,1,0,0`, no random stacks), the keys-only walking teacher at 0.5 fading over three
hours, stack pay at the doubled sizes, from v11's final weights (carried over by `sim/reshape_policy.py`).
**Choosing the state himself** is the step after: once he has played all four, his own value estimate at the spawn can
pick (no new output needed), or a new output is added. `sim/duel_env_v11.py` / `duel_env_ffa_v11.py` are the frozen
483-input simulator for v10 and v11 (the public server: export with `--env duel_env_ffa_v11` from now on).

## Done: `duel_gru_v11` (2026-10-07 20:35 to 2026-10-08 06:29; results in RESULTS.md)

**Outcome:** rockets 4% -> 18% of frags and weapon choice by distance, both kept without the teacher; aim and fire clicks
limited as intended; the stack is not solved (time bare 60% -> 57%) and Nightmare on arena1 fell to 4-25. **Proposed next
(for the owner):** every training spawn a machine-gun spawn, as on the server (today four in ten spawns hand him weapons, so
his rockets and his wins come from lives where he never had to fetch anything), with the keys-only teacher from the start
at a moderate weight; Nightmare and the fight check run the same way. Aim stays one click down until that is measured.

v10 taught him the walk: alone on arena1 he now takes what he is told to in 75 to 100% of 30-second rounds (v9: 0 to 22%), and kept it after the teacher was gone. Two things are still missing, and v11 takes one lever set for each.

**A. He does not go for the mega and the red armor while a fight is on** (from a normal spawn on arena1 in fights: mega 0.03, red 0.02 a player-minute; Nightmare takes them every time they come back).
1. **Collect, then fight** (`COLLECT_FIGHT_P=0.5`): half of the item runs turn into a fight after 20 seconds; half of the seats, drawn at random, are put back to a plain spawn and the others keep what they gathered. He meets from both sides a fight decided by what was collected. Item runs 20% of the time, no walking teacher.
2. **The intention holds** for 8 seconds, not 3, and is released at once when the item is gone (`INTENT_HOLD=8`): a trip is no longer dropped by the dice a second later.
3. **More 1v1**: three workers in five play groups of two (`--group 2,3,2,4,2`), so that on arena1 a life more often outlasts a trip (in groups of three it lasts 8 seconds).

**B. He does not use rockets** (nine launchers picked up in three games against Nightmare, none fired; 4% of his frags, all from the rocket-only drills), although at his accuracy they pay more a second than the machine gun (about 40 against 25).
4. **The weapon rule as a teacher on the weapon key** (`--weapon-teach 1.0`, fading over six hours): rockets from 100 to 450 units, lightning to 700, the rail beyond 600, else the machine gun, among what he holds with ammo. The same kind of seed as for the intention and the walk. He agrees with it 60 to 70% of the time today (mostly when the machine gun is all he has).
5. **Mixed drills** (`DRILL_MIX_P=0.7`): in most rocket drills both players also hold the machine gun, half the time in hand, so the choice is practised and not only the aim.

**C. His hitscan aim is too good in real play** (the owner and a friend: "a hard hitter" with the machine gun). From the player cards (`tools/player_card.py`): crosshair within 3 degrees of an enemy in view 56% of the time (people 23%, Nightmare 27%); 2.1 degrees off while firing (people 3.2); 74% of his damage with the machine gun (people 7%). The reflex room had said he was a little worse than the owner: the room flatters people. And while the machine gun is that good, rockets have no reason to be used.
6. **A slower, larger error on where he sees the enemy, growing with how fast the enemy crosses his view** (`PERCEPT_SIGMA` 0.6 -> 1.2 degrees, `PERCEPT_TAU` 0.15 -> 0.5 s, `PERCEPT_SPEED` 0.012 degrees per degree a second, at most 3): one click down. Not the reaction time (200 ms and 75 ms stay). A second click is measured and ready (1.6 / 0.6 / 0.02).

**Owner, 2026-10-07 20:40: lightning and rail overlap.** Rockets 60 to 300; the rail is the choice from 500 on and the lightning gun up to 700; with the lightning gun in hand up to 700, or the rail in hand from 300 on, the teacher says nothing (`W_RULE_RG` 500, `W_RULE_RG_OK` 300).

**The weapon rule's distances come from people's play and are kept up to date**: the card is recomputed from every new game; when people's weapon-by-distance table and the rule's distances (rockets 60 to 300 units, lightning to 700, the rail beyond) drift apart, the rule is changed and the change recorded.

Unchanged: v10's weights and league, arena1 / Aerowalk / Blood Run / Lost World, 10,080 players, the item runner in a quarter of the fight rounds, the item rule on the intention at weight 2, rocket drills 15%, the scattering machine gun.

**Read after the first night**: rockets' share of his frags (4%) and of his shots at close range (0%), the launcher in hand against Nightmare (0%); mega and red from a normal spawn in fights on arena1 (0.03, 0.02); in collect-then-fight rounds, kills by the stacked side against kills by the plain side (if the stack does not win there, nothing will teach its worth); the Nightmare scores (arena1 13-27, Blood Run 1-7, Aerowalk 0-10); the solo test must stay above 75%.

**Risks**: five changes at once, in two groups that touch different heads (the intention and movement; the weapon key), so their effects can still be told apart by their own numbers. The weapon teacher could make him hold rockets where he should not (point-blank is excluded by the rule; the fade leaves the last word to the fights).


**E. Pay for keeping a stack (owner, 2026-10-07 20:10, after his 61 : 10 : 10 game).** In frags a minute at full value:
health above 100 and armor 0.5 (`STACK_PAY`), the three big weapons 0.5 (`STACK_WPN`, a third each), a cost of 0.25
while he holds none of them (`STACK_BARE`) and 0.25 while health and armor together are under 50 (`STACK_LOW`). Normal
games only, not item runs or drills. Watch for hiding: the share of time with the enemy in view and frags a minute must
not fall. Owner, 20:20: the cost for holding none grows with the time gone without (nothing at the spawn, 0.25 after 5 s, up to 1.0 after 20 s); the low cost starts at 70 health plus armor (one rail shot) and grows to 0.5 at zero (`STACK_LOW` 0.5). **F. Fire button:** a change at most every 200 ms, 2.5 clicks a second (was five; owner: he taps the lightning gun, nobody does). **Applied 2026-10-08 00:39** (all three held; see RESULTS). **Fallback at hour four (owner: "good"), applied once at a checkpoint if all three hold against hour one:** the share of time without a big weapon has not fallen by a quarter, health and armor above 100 have not risen by a quarter, mega and red in the arena1 fight check are still near zero. Then: the four stack sizes doubled, and the walking teacher inside normal games (bare or under 70, no enemy in view: the keys to the nearest thing he lacks, that item as his goal, fading over three hours; to be built and tested, off, during the first hours). The weapon rule is a seed, not a rule (owner: "learnable"): it fades to nothing over six hours and only results decide after that. Not built: a cost for starting a fight with fewer than two weapons (it would also punish shooting back).

## Owner decisions

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

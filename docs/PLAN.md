# BobbyBones: plan

Long-term goal: a Quake Live bot that **learns** to play (movement, aim, tactics) and beats people fairly:
human physics, human-like limits, knowledge only from sight and sound. The current target (owner, 2026-10-08):
human-like play on the three duel maps, Blood Run, Aerowalk and Lost World, one against one and all against all with
up to four to six players: he uses the weapons, picks up the items and plays the map as a good player would; item
control, weapon choice and positioning are the key. The yard (`arena1`, Goal 1 below) is the map he is checked on and,
from v13, no longer trains on. Judge by how the play looks (videos, play tests), by duels with error bars against the
Nightmare stand-in, by real games against Nightmare on a free PC, and by the numbers for items and movement per map.

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
| [../README.md](../README.md) | The public page: the goal, the fairness rules, how it works, what he can do, what is in progress and planned (no dated status: owner, 2026-10-08) | The goal, a fairness rule or what he can do changes |
| [REPORT_v12.md](REPORT_v12.md) | The full report of the network on the public server | (a report per network the owner reviews) |
| [MANIFEST_v13.md](MANIFEST_v13.md) | The next run in full: what is in its rounds, what it is paid for and shown, what changed | Before a run starts, for the owner's approval |

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

## Status (2026-10-08 evening)

| What | Where it stands |
|---|---|
| Simulator: movement, nine weapons, items, sounds, human limits on hands, eyes and aim | done and checked against the real game. Corrected on 2026-10-08: no universal ammo packs (the real game has none), round lengths (they ended at 0.68 of their length), the pay for the way to an item (it could be farmed). Open: machine-gun scatter not measured on a server (B-107b) |
| The learning loop | reviewed on 2026-10-08 by three readers and with tests: reward, flags, labels, masks and the PPO arithmetic are right. Fixed around it: the input statistics (the direction to the mega and to the red armor reached him at 3 to 6% of size), the left hand's outputs credited on frames they are not read on, the first round of every restart |
| Play on a real server | 1v1 and free-for-all with up to four Bobbys. The plugins were set against the simulator on 2026-10-08: the 1v1 plugin had never had the map's walking graph, and on the public server every Bobby moved on another Bobby's keys; both fixed, with nine smaller gaps. The routine check is `tools/input_check.py` |
| Aim | one knob (`AIM_LEVEL`; 3 = the owner's reflex card plus about a tenth, the only level trained). Reflex room: on a strafing target 45% of the time (owner 40%), first rail shot 32% (88%), a rocket 35 damage (54) |
| Weapons | v12 (playing styles, machine-gun spawn): time without a big weapon 74% -> 54%, his style's weapon in hand 41 to 61%, the machine gun's share of his frags 73% -> 45%; kept after the teachers were gone |
| Items, alone | told to fetch an item he gets it in 84 to 100% of tries, but for the red armor on Blood Run (3%: the last step is a gap jump) and on Aerowalk (28%: the walking graph has no way to it) |
| **Items with an enemy about** | **the open problem.** In duels against the stand-in he takes 19% of the red armor's spawns on arena1 (the stand-in 36%) and 1% on Blood Run; in real games Nightmare takes the mega and the armors two to five times as often as he does. His own value estimate puts 100 armor at zero. v13 answers with armor that soaks damage at a third of the price, rounds that start as a race for a big item, and the repaired pay for the way |
| Movement | he walks (270 to 290 units a second) and jumps in 1 to 2% of frames; the pros are in the air for 35% of their moving time, at 380 to 400. The walking teacher had been labelling "no jump"; from v13 it labels jumps where the pros jump, the jump head gets an exploration bonus and the hand 5 key actions a second |
| The walking layer (teacher, scripted runner, the "next step" inputs) | the teacher's own pupil reaches every item in 86 to 100% of tries on the three duel maps (Aerowalk's red armor: no way). To be rebuilt so that jump and drop links are taken the way they were made (B-140) |
| Nightmare, real games of ten minutes (v12, every plugin fix) | arena1 14-27, Blood Run 7-18, Aerowalk 6-13: he deals more damage on all three and loses on the stack |
| Nightmare stand-in in the simulator | `tools/duel_eval.py`, 100 ten-minute duels a map with error bars; matches the real scores on arena1; not usable on Lost World (the scripted runner hardly moves there, B-141) |
| Maps in training | up to v12: arena1, Aerowalk, Blood Run, Lost World. From v13: the three duel maps; arena1 held out |
| Pro demos | 3,266 1v1 demos (505 hours) of the three duel maps, as tables: weapon by distance, item order, positions, where they jump. The pros' ways as a walking teacher were tried and left out (slightly worse than the shortest ways) |
| Public server | v12 with playing styles and the fixed plugins since 2026-10-08 16:50; three Bobbys on arena1 |
| Attention over the scene; opponent profiles; player reports | scoped (`ATTENTION_POC.md`, B-109) / later |

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

**Next run: `duel_gru_v13`**, to start on the owner's approval of [MANIFEST_v13.md](MANIFEST_v13.md) (he reviews it with
[REPORT_v12.md](REPORT_v12.md) on 2026-10-08 19:00) and run overnight. Its starting network is ready (fresh input
statistics, B-145). One open point from the dry runs: the first updates (B-154).

Open besides it, in this order: B-140 (the walking layer rebuilt properly, with keys a hand can press), B-154 (teachers
and the shared layers), B-149 (the last 0.7 frame of shot timing), B-141 (the scripted runner on Lost World), B-153 (a
spinning helper thread on the game servers), B-148 (smaller gaps of the free-for-all plugin), B-150 (trainer
housekeeping), B-107b, B-92, B-109.

How it got here: RESULTS 2026-10-06 to 2026-10-08 (v9 to v12, the audit, the wiring review).

## Proposed: `duel_gru_v13` (the owner's approvals of 2026-10-08; the exact settings go into RESULTS when it starts)

From `duel_gru_v12b`'s weights (491 inputs), on Blood Run, Aerowalk and Lost World, groups of 2, 3 and 4, full size,
learning rate 1e-4 (the two arms of 2026-10-08 showed no difference between 2.5e-5 and 1e-4 over two hours).

| Group | What | Switch or flag |
|---|---|---|
| Seeds from the pros, fading over four hours | weapon by distance; item order (a weapon first when bare, then the nearest armor or the mega); the spawn routine; yellow armors as goals; jumps where the pros jump | `PRO_WEAPON`, `PRO_ITEMS`, `SPAWN_TEACH`, `PRO_JUMP`, `--teach 0.5`, `--weapon-teach 1.0` |
| Rewards | damage taken at full price, but what armor soaks at a third; a price per shot by weapon, map, place and belt; the way to an item paid on new ground only; no pay for a style's distance | `--dmg-taken-w 1.0`, `ARMOR_COST=0.33`, `SHOT_COST=0.10`, `STYLE_BAND=0` |
| Rounds | 15% start as a race for a big item; no rocket drills; no spawns beside the mega or the red armor; rounds of 80 to 160 s; the game's spawn (machine gun) | `CONTEST_P=0.15`, `--kind-p 1,0,0,0`, `--near-item-p 0` |
| Honest knowledge and limits | items by what he saw or heard; aim level 3; no ammo packs; 5 key actions a second | `ITEM_BELIEF=1`, `AIM_LEVEL=3`, `AMMO_PACKS=0`, `KEY_RATE=5` |
| Learning | credit horizon 0.98; the hand's outputs credited on the frames they are read on; an exploration bonus on the jump head; fresh input statistics | `--lam 0.98`, `--ent-heads 0,0,0.25,...`, `sim/renorm_policy.py` |

What decides whether it worked, against v12 on the same checks: his share of the red armor's and the mega's spawns in
duels against the stand-in (arena1 19%, Blood Run 1% now) and in real games; the share of race rounds in which somebody
takes the item (15 to 18% now); time in the air and speed on the way (2%, 270 to 290 now); the real Nightmare scores
(14-27, 7-18, 6-13 now); time bare and weapons as in v12 or better. Watched in the first hour: the policy's step with
the teachers on (a restart at half the rate if the KL stays above 0.05), fire and frags (a teacher must not stop him
fighting, as on 2026-10-08 00:39), falls.

## The suite after the audit (owner, 2026-10-08 11:15: agrees with the five problems and the four gaps; "scope how to implement them", "recommend a suite of total changes, and whether now or after the current run")

**Timing: after v12 ends (14:00).** Nothing of the suite can run sooner (it has to be built, which happens meanwhile), and
v12's final weights are the baseline for the new checks. (Its last hours as a test of keeping are weaker than first said:
at a tenth of the learning rate things also fade ten times slower.)

**The checks (built first; every later change is judged on them):**
- *Nightmare in the simulator.* Quake Live's bot code is closed; what can be ported is the Quake 3 bot it descends from
  (botlib and the game-side AI in the ioquake3 source, with the game's own bot files and .aas maps): days of work and
  still a cousin. Now: a stand-in, our scripted item runner given Nightmare's measured play from 692 minutes of logs
  (weapon by distance, damage a minute, aim error, item shares, speed), accepted only if it reproduces the real scores
  we have (v10 22-28 on arena1, v11 4-25; near nothing on the duel maps). For checks only, never a training opponent.
  100 ten-minute duels a map (about ten minutes of computing for all maps); old networks play through an input adapter.
  It is also the test for hiding: a player who avoids fights scores no frags against it.
- The real Nightmare stays the reference: three ten-minute games a map at the end of each run, side by side.
- Frozen v10 and v12 as opponents; numbers per map from the trainer; the policy's step (KL, clip fraction) logged.
- The pros' positions per duel map (all, bare or armed, enemy in view or not) and his overlap with them in the scorecard.

**The four gaps:**
- *Item control: a goal model from the pros.* For every frame of a pro's life the label is what he picked up next within
  15 s (or "engage" when his next act is the fight, or nothing); inputs that exist on any map (health, armor, weapons,
  seconds to each item along the floor, seconds since he last took each, enemy seen and how far, seconds alive). A
  small network, trained on two maps and tested on the third to prove that it carries over; the two-line rule's hit
  rate on the same data is the bar to beat. In training it replaces the item rule as the intention's teacher (numpy in
  the workers), and that teacher fades once the learning rate is right. Half a day.
- *Stacked and nothing to do.* "Engage" is one more intention: the way to where the enemy was last seen or heard (ways
  between any two nodes are tabled once per map); waiting at an item about to return is already a label of the goal
  model. The intention grows from 8 to 9. A day with the goal model.
- *Positioning.* Measured first (above). Then a mild pull: a potential on the pros' share of time per cell in his
  situation, paid only on moving between cells (it cannot be farmed by standing), sized at a tenth of a frag from a dead
  corner to a favorite spot; on the maps with pro data only.
- *Aim* (it may go up). The cut hit the wrong shots: in the reflex room his tracking is still above the owner's (48% on
  target against 40%) and his first rail shot far below (49% against 88%); in the one real game counted his machine gun
  and lightning hit less than the owner's. A sweep of the three perception settings in the room against the owner's
  whole profile (a smaller, quicker error and a larger share that grows with the target's speed), then per weapon
  against the game's own accuracy counts from people's games as they come in.

**Order:**
| When | What runs | What it tells |
|---|---|---|
| now to 14:00 | v12 to its end; the checks and the switches for the five fixes are built | - |
| 14:00 | v12's full check; v10, v11 and v12 on the new checks; the aim setting chosen from the sweep | the baseline |
| 14:30 to 19:00 (owner: "until 7pm") | two half-size arms from v12's weights (`duel_gru_v12a`, `duel_gru_v12b`), with the aim at level 3, close spawns off and items by what he knows; only the learning rate differs (a tenth as in v8 to v12, against 1e-4 constant) | how much the learning rate matters; the winner's weights and rate go on |
| tonight, after the owner's review at 19:00 (owner: "v13 can run in one go") | v13, one full-size run on the three duel maps from the winning arm: the pro seeds (weapon table, item order, spawn routine, yellow armors), even damage trading, credit horizon 0.98, the price per shot by weapon and map (`SHOT_COST` 0.10, owner: "ammo is a scarce resource"), and, if he agrees, without the ammo packs the real game does not have (`AMMO_PACKS=0`, B-135) | the seeds against v12, on the stand-in duels and the scorecard per map |
| tomorrow night | v14: the goal model with "engage", the pull to the pros' positions | item control and positioning |
The pros' ways stay out until tried alone with a control (they did not pass their test). Each run starts only on the owner's go.

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

## Done: `duel_gru_v12`: playing styles and machine-gun spawns (2026-10-08 07:31 to 14:00; results in RESULTS.md)

**Outcome.** In the simulator the styles took: time without a big weapon 74% -> 54%, his style's weapon in hand 4-10% ->
41-61%, the machine gun's share of his frags 73% -> 45%, and all of it held for two and a half hours after both teachers
were gone (the gate for v13 passes). Against the real Nightmare: 6-24 on arena1, 0-11 on Aerowalk and 0-9 on Blood Run,
and then the reason for much of it: **the 1v1 plugin had never given him the map's walking graph**, so in every real 1v1
game he did not know the way to any item (RESULTS 2026-10-08 14:55). With it: 13-33 on arena1, the red armor taken
twice, and 16 of his 33 deaths falls into the void on the way to it; 1-19 on Blood Run. Nightmare still takes the armor
and the mega many times over (18 yellow armors to his 5 on Blood Run). **Item control decides the games against
Nightmare, not aim or weapons**; what stops him is different on each map (the table in RESULTS).

What was set up:


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

# `duel_gru_v12`: full report (2026-10-08)

The network on the public server since 2026-10-08 16:50. Everything here is from [RESULTS.md](RESULTS.md) (entries of
2026-10-08), set in one place for the owner's review before `duel_gru_v13` ([MANIFEST_v13.md](MANIFEST_v13.md)).

## In short

- **Better**: weapons. He fetches them and uses them (time without a big weapon 74% -> 54%; the machine gun's share of
  his frags 73% -> 45%), and it lasted after the teachers were gone.
- **Even with Nightmare on damage, behind on score**: 14-27, 7-18, 6-13 in fair ten-minute games; he deals more damage
  on all three maps and loses on armor and health.
- **Not solved**: taking the big items when an enemy is about; jumping (he walks); the lives without a preferred weapon.
- **Found while checking it**: faults around the learning loop that held every network back (the wiring review), now fixed.

## What it is

| | |
|---|---|
| From | `duel_gru_v11`'s final weights (4,338 min of training in the lineage), carried to 487 inputs |
| Trained | 2026-10-08 07:31 to 14:00: 388 minutes, 194 updates, 751 million player-frames (about 5,200 hours of play) |
| Network | 487 inputs -> 256 -> 256 -> memory of 512 (GRU) -> 11 outputs (forward, strafe, jump or crouch, turn, pitch, fire, weapon, walk, zoom, lift, intention) |
| Maps, groups | arena1, Aerowalk, Blood Run, Lost World; groups of 2, 3, 2, 4, 2 (10,080 players at once) |
| New in v12 | a **playing style** per life (general, rockets, rail, lightning; a quarter each) as four inputs; **every life starts with the machine gun only**; fire button 2.9 clicks a second |
| Teachers | keys-only walking teacher (0.5, gone after 180 min), weapon teacher (1.0, gone after 240 min), the item rule on the intention (2.0, constant) |
| Rewards | frag +1, death -1, damage 0.005 a point dealt and half of that taken, items 0.75, pay for a stack, pay on the way to the chosen item, damage with the style's weapon +50%, half a frag a minute inside the style's distance |
| Learning rate | 2.5e-5 (a tenth of the nominal one: the decay counted the whole lineage's minutes, found in the audit) |
| File | `data/sim_runs/duel_gru_v12/policy_end_v12.pt`; inputs in `docs/INPUTS_v12.csv`; simulator module `duel_env_ffa_v12` |

## Training, start to end

| | Time bare | Big weapons held | Weapons picked up a player-minute | His weapon in hand (rockets / rail / lightning lives) | Big weapons held, general / preferred lives | Fire, frags a match-minute |
|---|---|---|---|---|---|---|
| 07:50 (update 10) | 80% | 0.24 | 1.88 | - | - | 25%, 3.7 |
| 08:35 | 70% | 0.37 | 1.94 | 10 / 17 / 22% | 0.24 / 0.36-0.48 | 23%, 3.6 |
| 09:35 | 61% | 0.47 | 2.19 | 26 / 30 / 45% | 0.25 / 0.47-0.69 | 22%, 3.6 |
| 10:35 (walking teacher at zero) | 58% | 0.51 | 2.31 | 33 / 34 / 52% | 0.26 / 0.52-0.76 | 22%, 3.6 |
| 12:05 (both teachers at zero) | 54% | 0.56 | 2.45 | 41 / 40 / 58% | 0.27 / 0.57-0.80 | 22%, 3.8 |
| 14:00 (end) | 54% | 0.57 | 2.53 | 42 / 40 / 60% | 0.28 / 0.55-0.81 | 21%, 4.0 |

Both teachers were at zero from 12:05 on and every number kept rising: what they showed him stayed.

## How he plays at the end (training's own numbers, all four maps)

| | |
|---|---|
| Frags by weapon | machine gun 46%, lightning 23%, rockets 16%, rail 15% (v11: machine gun 73%) |
| Hit rate | rockets 44%, rail 38%, lightning 38%, machine gun 37% |
| Weapon in hand in a fight | machine gun 59 to 65% at every distance; rockets 8 to 12%, rail 12 to 15%, lightning 11 to 16% |
| By style | lightning lives: his weapon in hand 60%, 1.05 frags a death; rail 40%, 0.77; rockets 42%, 0.72; **general 0.28 big weapons, 0.65 frags a death** (the weakest, and it did not move) |
| Pickups a player-minute | weapons 2.54, mega 0.37, red armor 0.32, other armor 0.74, health 0.64 |
| Chosen item | red armor 34%, rockets 23%, mega 16%, lightning 16%, rail 11%; 6.8 trips a player-minute, **30% reached, 50% dropped** |
| Movement | 257 units a second on his way, fast in the air 9% of the time; **the jump key in 1 to 2% of frames** |
| Left hand | asks for 6.6 key actions a second, makes 3.8 (the budget was 4) |
| Against the league's older versions | 52% of the frags |
| Against our scripted item runner | 1.22 frags a minute against 2.33 deaths: he loses 1 : 2 |
| On arena1 | the mega lies untaken 62% of the time, the red armor 70%; 0.25 falls into the void a player-minute |

## Against Nightmare, real games

Ten minutes a map, three games side by side, the game's own spawn. (Found at 19:27: the PC was not free. An idle local
game server held 7 to 8 of its 20 threads all day, RESULTS 2026-10-08 19:30; the games are to be repeated.) The first two columns are before the
plugin faults were fixed (see the last section): **every real Nightmare score before 2026-10-08 16:51 understated him**.

| Map | 14:01, before any fix | 14:37, walking graph and timers | **16:51, all fixes** | Damage dealt / taken | Red, mega, yellow armor: he / Nightmare | Damage lost a life: he / Nightmare |
|---|---|---|---|---|---|---|
| arena1 | 6-24 | 13-33 | **14-27** | 3,271 / 2,175 | 3 / 8, 1 / 4, - | 133 / 243 |
| Blood Run | 0-9 (5 min) | 1-19 | **7-18** | 2,870 / 2,285 | 0 / 2, 3 / 9, 6 / 16 | 153 / 417 |
| Aerowalk | 0-11 (5 min) | (not valid) | **6-13** | 2,943 / 1,890 | 2 / 1, 4 / 9, 2 / 11 | 181 / 497 |

He deals more damage than Nightmare on all three maps and takes as many weapons (27 to 36 on Blood Run, 40 to 35 on
Aerowalk). The frags are lost on the stack: Nightmare absorbs two to three times as much damage a life. On arena1 10 of
his 28 deaths are falls into the void on the way to the red armor.

## Against the Nightmare stand-in (simulator, 100 ten-minute duels a map)

`tools/duel_eval.py`; the stand-in is our scripted item runner with Nightmare's aim, for checks only.

| Map | Score | His share of the frags (95%) | Won / drawn / lost | Time bare: he / it | Stack of 150 or more: he / it | Mega, red: his share of the spawns (its share) | Own deaths a game |
|---|---|---|---|---|---|---|---|
| arena1 | -0.9 : 17.4 | 35% (34-37) | 0 / 0 / 100 | 47% / 24% | 5% / 17% | 21% (2%), 19% (34%) | 13.2 |
| Blood Run | 4.8 : 18.6 | 25% (24-27) | 0 / 0 / 100 | 36% / 11% | 8% / 49% | 24% (64%), 0% (48%) | 1.7 |
| Aerowalk | 17.4 : 20.1 | 47% (45-49) | 37 / 3 / 60 | 28% / 20% | 11% / 17% | 21% (65%), 9% (6%) | 0.8 |

These are with playing styles drawn and today's simulator (`docs/eval_v12_nightmare_styles.json`): the baseline v13 is
measured against. The first set of 14:00 (`docs/eval_v12_nightmare.json`: 42%, 34%, 47% of the frags) played general
lives only and against a weaker stand-in: its walker has since learned to take jump pads and teleporters, which made it
much stronger on Blood Run (its share of the red armor 22% -> 48%). Lost World is not usable: the stand-in hardly moves
there (B-141).

## The big items, map by map

| Map | Red armor alone, told to fetch it | His share of its spawns in duels (the stand-in's) | What stops him |
|---|---|---|---|
| arena1 | 100% in 6.6 s | 19% (34%) | it stands on an island over the void: 10 to 16 falls a game; with an enemy about half of his trips are dropped |
| Blood Run | **3%** (every other item 100%) | 0% (48%) | the last step is a jump over a 190 to 240 unit gap: he covers 96% of the way and falls |
| Aerowalk | 28% | 9% (6%) | the walking graph has no way to it (the pros jump there) |
| Lost World | 94% | 5% | in normal rounds he does not go |

Why he drops it with an enemy about, from the code: damage taken cost half of what damage dealt paid; damage his armor
soaks was charged like health lost (his own value estimate puts 100 armor at zero); in self-play nobody takes the big
items either, so the race for one hardly ever happened; and a quarter of his training lives started within two seconds
of the mega or the red armor, which the real game does not have.

## Aim (reflex room; the owner's run beside it)

| | He | Owner |
|---|---|---|
| On a strafing target | 45% of the time | 40% |
| Lightning, damage a second | 68.5 | 57.7 |
| On a jumping target after | 431 ms | 350 ms |
| First rail shot hits | 32% | 88% |
| A rocket does | 35 damage | 54 |
| On target while under fire | 35% | 20% |

Tracking is about a good player's; the first rail shot and the rockets are well below.

## On the public server

Since 16:50 with every plugin fix: free-for-all, three Bobbys on arena1, `!map` for the trained maps. Every public game
before it was played by Bobbys moving on each other's keys (10 to 11 key changes a second, 179 to 192 units a second);
with the fix 1.4 to 1.9 forward-key changes a second at 287 to 316. Nobody has played on the new build yet.

## What did not work

- **Item control with an enemy about**: the open problem (tables above).
- **Jumping**: gone. The walking teacher of v10 to v12 labelled "no jump" on every frame that was not a gap or a step.
- **General lives** did not improve (0.29 -> 0.27 big weapons): the styles carried all of the gain.
- **The machine gun** is still in his hand 59 to 65% of the time in a fight.
- **Trips**: half are dropped; the pay for the way could be collected without arriving (fixed for v13).
- **The scripted runner beats him 2 : 1**, and he has not adapted to it in three runs.
- **Lost World**: time bare 66%, first weapon after 27 s.
- **The learning rate** sat at a tenth of its nominal value through v8 to v12. Two arms after v12 (2.5e-5 against 1e-4,
  two hours each) showed no difference, so the rate was not what held him back.

## Faults found while checking v12 (all fixed; RESULTS 2026-10-08 13:00, 14:55, 16:00)

| Where | Fault | Effect |
|---|---|---|
| 1v1 plugin | never given the map's walking graph or the item timers | in every real 1v1 game the inputs for the items' ways and times were zero |
| Free-for-all plugin | the finger rules ran once per Bobby on everybody's keys | on the public server every Bobby moved on another's keys |
| Real-game control | on a busy PC the bot's commands were dropped | the duel-map Nightmare numbers were wrong |
| Input statistics | frozen, and carrying a giant test map of v4 and v5 | the direction to the mega and the red armor reached the network at 3 to 6% of size |
| Pay for the way to an item | paid for ground gained again and again | collectable without arriving |
| Left hand's outputs | read one frame in four, credited on all four | three quarters of the credit was noise |
| Rounds | the length was redrawn every frame | rounds ended at 0.68 of their length |
| Simulator | ammo packs the real game does not have | ammunition was never short |
| Walking teacher | labelled "no jump"; took pads and teleporters off their plates | he unlearned jumping; the teacher's own pupil missed items |
| Groups of three and four | all damage pay and the frag went to one attacker a victim a frame | 0.7 to 0.8% of the damage pay and 1.0 to 1.4% of the frags went to the wrong player |

## Verdict

The best network so far, and the first whose weapon habits held without a teacher. It is the base of v13 by way of
`duel_gru_v12b` (v12 plus two hours at a learning rate of 1e-4, no measurable difference).

# `duel_gru_v13`: training manifest (proposed 2026-10-08; **not started**, waits for the owner's approval)

What the run is made of: the network it starts from, what is in its rounds, what it is paid for, what it is shown,
and what has changed since `duel_gru_v12` ([REPORT_v12.md](REPORT_v12.md)). The exact command is at the end.

## 1. Start, size, length

| | |
|---|---|
| Starts from | `duel_gru_v12b` (v12 plus two hours at a learning rate of 1e-4), 491 inputs, with its last eight league snapshots; 4,834 minutes of training in the lineage |
| Input statistics | measured afresh on v13's own rounds (`sim/renorm_policy.py`): 133 of 491 inputs rewritten, his play unchanged to 8e-8 |
| Network | 491 inputs -> 256 -> 256 -> memory of 512 (GRU) -> 11 outputs; unchanged |
| Size | 21 simulator processes, 10,080 players at once, 384 frames (9.6 s) an update, an update about every two minutes |
| Length | overnight, from the owner's go to 07:00 (nine to ten hours: about 290 updates, 8,000 hours of play) |
| Maps | **Blood Run, Aerowalk, Lost World**, a third of the players each. arena1 is not trained on: it is the check map |
| Groups | duels 62% of the players, three players 19%, four players 19%, all against all |

## 2. What is in the rounds

Every round is a game on a real map with the game's own start: **125 health, no armor, the machine gun with 100
bullets, a spawn point away from the enemies, every item in place**. No drills, no spawns beside an item, no random
stacks. Rounds last 80 to 160 seconds with respawns inside; his memory and score start over with each round.

| Kind of round | Share of his playing time | What happens |
|---|---|---|
| **Normal game** | about 76% | self-play in the group; frags, deaths, damage, items |
| ... of which a **race for a big item** | 15% of the normal rounds | the mega, the red armor or a yellow armor is gone and back in 4 to 8 s; everybody knows it and starts about that far from it by the walking graph. No extra pay: the situation, dealt often (in self-play the race hardly ever happened) |
| ... of which **against the scripted item runner** | 25% of the normal rounds | one seat is our scripted player that collects the stack and then fights: the learner meets an enemy who turns up with armor |
| **Item run, alone** | about 11% | alone on the map for up to 60 s with a target given as his intention (a big item that is there, the next one when he has it); paid for the way gained and for taking it |
| **The fight after a run** | about 13% | half of the item runs turn into a fight after 20 s: half of the seats are put back to a plain spawn, the others keep what they gathered. He meets, from both sides, a fight decided by what was collected |

(Shares counted in the simulator set up as the trainer sets it, ten minutes on each map; RESULTS 2026-10-08 18:45.)

**Who is in the other seats.** In half of the matches every seat is the current network. In the other half the odd
seats are played by one of his last eight earlier versions (a new one every 20 minutes). The game's bots are never in
training.

**His style, life by life.** Three lives in four have a preferred weapon (rockets, rail, lightning, a quarter each;
no rail lives on Lost World, which has no railgun), given to him as four inputs; one in four is general. In a preferred
life the item rule sends him for that weapon first, the weapon teacher names it at every distance, and damage with it
pays half as much again.

## 3. What he is paid for

| | Value | Since |
|---|---|---|
| Frag / death | +1 / -1 | always |
| Damage dealt | +0.005 a point (a rail hit 0.40) | always |
| Damage taken, health | -0.005 a point | **v13** (was half of that) |
| Damage taken, soaked by armor | a third of that | **v13** (was charged like health) |
| A shot fired | a tenth of what its hit would pay, times how scarce that ammo is for him (the map, the way to more, his belt; 0.25 to 3): a rocket about 0.05, a rail slug 0.04, a lightning cell 0.003 | **v13** |
| Picking up | 0.75 per 100 points of health or armor (mega and red armor 0.75, yellow 0.375), a weapon he did not have 0.19 | v9 |
| The enemy takes the mega or the red armor | half of its pickup, off | v9 |
| The way to the item he chose | worth its pickup (0.75 for the mega or the red armor, 0.375 for a yellow armor, 0.19 for a weapon), paid in parts **on new ground only** | fixed for v13 (it could be collected again and again) |
| Keeping a stack | a frag a minute at full value for health over 100 and armor, another for the three big weapons; half a frag a minute off while he holds none (growing with the time), a frag a minute off under 70 health and armor | v11 |
| Damage with his style's weapon | +50% | v12 |
| Fighting at his style's distance | off (was half a frag a minute) | **v13** |
| Changing his intention | -0.02 | v8 |
| Exploration bonus | turn, pitch, weapon, zoom, lift, intention as before; **the jump key 0.25** (was none) | **v13** |

## 4. What he is shown (teachers; they only ever name keys, never where he looks or when he fires)

| Teacher | Weight | What it names | From the pros |
|---|---|---|---|
| Walking teacher (keys) | 0.5, fading to zero over 4 hours | the keys along the shortest way to the item the item rule names: in item runs; in normal games while he has no big weapon or is under 70, and no enemy is in view; **new: also with an enemy in view while he has no big weapon** (`SPAWN_TEACH`) | the pros have a weapon 2.7 s after a spawn |
| ... its jump label | (same) | **new: the jump key down where the pros are in the air for more than half of their moving time** and he is on his way at speed; feet down before a jump, a drop, a pad or a teleporter; no label elsewhere (until now: "no jump" everywhere) | `tools/pro_jumps.py`, 3,266 demos |
| Weapon teacher | 1.0, fading over 4 hours | the weapon for the distance among those he owns; in a preferred life, that weapon | **new: the pros' first choice by distance** (`PRO_WEAPON`), not hand-set distances |
| Item rule (on the intention) | 2.0, constant | what to go for | **new: the pros' order** (`PRO_ITEMS`): with no big weapon the nearest one (rockets when nearly as near); armed, the nearest of yellow armor, red armor and mega that he can use; else a weapon he lacks. **The yellow armors are goals now** (the pros take them most of all) |

The gate as for v12: after the teachers are at zero (four hours in) the numbers must hold or rise.

## 5. His limits (unchanged unless marked)

| | |
|---|---|
| Physics, senses | 125 fps human physics; sight in a 110-degree field with line of sight, sound within 800 units, pain sounds |
| Aim | level 3 of the one knob (the owner's reflex card plus about a tenth); reaction 100 ms, 200 ms to pick up a new target |
| Item knowledge | **new in training since v12b: what he saw or heard** (`ITEM_BELIEF`), not the true state |
| Left hand | five fingers; decisions ten times a second; **5 key actions a second** when tired (was 4) |
| Right hand | fire and zoom at no more than 2.9 clicks a second |
| Ammunition | **new: no ammo packs** (the real maps have none): weapons and their boxes only |

## 6. What has changed since v12

**Settings (the owner's calls of 2026-10-08).**

| | v12 | v13 | Why |
|---|---|---|---|
| Maps | arena1 and the three duel maps | the three duel maps | "people like the actual maps in the game"; arena1 becomes the held-out check |
| Rocket drills | 15% of the time | none | "they seem to have done their part" |
| Spawns beside the mega or red | a quarter of the lives | none | the real game has none; it stood in for learning to go there |
| Race rounds | none | 15% of normal rounds | "go pick up the red armor": the contested pickup was almost never practised |
| Damage taken | half price | full price, armor-soaked at a third | an even trade was profit, and armor earned nothing |
| Shots | free | a price by weapon, map, place and belt | "ammo is a scarce resource ... spam happy or need to conserve" |
| Ammo packs | everywhere | none | the real game does not spawn them |
| Pay for the style's distance | half a frag a minute | off | paid for standing at a distance, not for winning there |
| Item rule, weapon rule | hand-set | the pros' order and the pros' weapon by distance | "be more explicit with seeding him with patterns for play" |
| Yellow armors | not goals | goals | the pros take them most of all |
| Jump key | teacher said "no jump"; no exploration bonus | teacher names jumps where the pros jump; bonus 0.25 | "incentivise him to jump again, but informed by pro play" |
| Key budget | 4 a second | 5 a second | he asked for 6.8 and got 3.8; people sustain about 7 |
| Learning rate | 2.5e-5 | 1e-4 | the nominal rate; the two arms showed no harm |
| Credit horizon (lambda) | 0.95 | 0.98 | item trips take 5 to 10 s |
| Teachers and the shared layers | full weight | **5% (proposed, section 7)** | a teacher with new labels broke his aim on its way in |

**Faults fixed in the code since v12 (the wiring review; all in the simulator or trainer v13 runs on).**

| | Before | Now |
|---|---|---|
| Input statistics | frozen with a giant test map in them: the direction to the mega and the red armor at 3 to 6% of size, to pads and teleporters at 4 to 8%, the second and third enemy at 3 to 13% | measured afresh |
| Pay for the way | on ground gained again and again | on new ground only; dropping a trip takes its pay back |
| Left-hand outputs | read one frame in four, credited on all four | credited on the frames they are read on |
| Round length | redrawn every frame: rounds ended at 0.68 of their length (54 to 109 s) | drawn once: 80 to 160 s |
| First round after a restart | every weapon at the spawn | the game's spawn |
| Walking teacher and scripted runner | cut across jump pads and teleporters; Aerowalk's graph had links nobody can walk | enter at the plate or entrance; Aerowalk's graph pruned. The teacher's own pupil reaches 86 to 100% of every item on the three maps (Aerowalk's red armor: no way in the graph) |
| Damage and frag credit in groups of three and four | all to the last attacker of the frame | per attacker; the frag to the hit that killed (it moved 0.7 to 0.8% of the damage pay and 1.0 to 1.4% of the frags) |
| Styles, drills | style drawn in one of two spawn paths; drills started far apart | every new life; drills close |

## 7. The first minutes (dry runs of these exact settings at half size, on scratch copies)

The network moves very far in its first updates: the policy's step is 1.07, 0.48, 0.11, 0.05 and 0.027 from the twelfth
update on (the arm restarted at 0.018). **The cause is the item teacher on its new labels** (the pros' order, with the
yellow armors, at weight 2.0), which reaches the mouse outputs through the layers all outputs share: without it the
step is 0.008, with the old item rule 0.014 to 0.020. It is not the fresh input statistics and not the new rewards.

A softer start (a warm-up from a tenth of the rate, or the old rate of 2.5e-5; 17 updates each) **ends in the same
place**: fewer frags, less firing, worse aim. What does change it is **holding the teachers' losses back from the
shared layers** (`--teach-trunk`, new: the output layer still learns the labels in full, the layers all outputs share
get 5% of the teachers' pull). After 8 updates at 1e-4:

| | No learning | As planned | **Teachers at 5% into the shared layers** | At 0% |
|---|---|---|---|---|
| The policy's step: update 1, update 8 | 0 | 1.07, 0.033 | 0.23, 0.013 | 0.030, 0.020 |
| ... of it the turn output, update 1 | | 0.41 | 0.056 | 0.015 |
| Frags a match-minute | 2.9 to 3.1 | 2.2 | **2.9** | 2.6 |
| Firing, with an enemy in view | 67 to 68% | 54 to 55% | **68%** | 66% |
| Aim error in view, on target | 13.3 to 13.9, 31% | 15.0 to 15.5, 26 to 27% | **13.5, 31%** | 13.4, 31% |
| Time bare | 40% | 36% | **35%** | 33% |
| Fast in the air; speed on his way | 8 to 11%; 273 to 291 | 23 to 25%; 263 to 270 | **22%; 273** | 17%; 286 |
| Key actions a second: asked, made | 5.0, 4.0 | 10.5, 4.7 | 9.5, 4.7 | 7.9, 4.7 |
| The teachers' losses left: keys, intention | | 1.2, 0.3 | 2.0, 0.6 | 3.5, 1.0 |

So the drop in aim and fighting at a teacher's start is **damage, not his new behavior**: with the shared layers
protected the taught habits arrive just the same (time bare, the jump key) and what he knew stays. v12 carries the same
mark: on target fell from 37% to 33% in its first two updates under its teachers and was 32% at its end.

**Proposed for v13, the one change to the list the owner approved: `--teach-trunk 0.05`.** It is a setting of the
learning, not a reward. The caution: it rests on eight updates at half size; the labels are learned more slowly (the
keys' loss 2.0 against 1.2), and if they stall the first hour will show it (time bare and the teachers' losses in the
hourly lines). Without it v13 starts as in the "as planned" column.

What the first half hour will look like either way: **the jump key comes alive and the left hand is full** (he asks
for twice what it can do, as in v12's teacher phase: the walking teacher's own keys use a hand's whole budget). The stop
signs: firing under 8% of frames or frags under 1.2 a match-minute (the pattern of the teacher that stopped him fighting
on 2026-10-08 00:39). Details: RESULTS 2026-10-08 18:45.

## 8. What is watched, and what decides

**First hour** (brief lines): the policy's step, firing and frags (a teacher must not stop him fighting), falls, key
requests against keys made at 5 a second, time in the air, the race rounds taken, the price of a shot, damage soaked.
A stop and restart only if the data is clearly bad.

**At the end**, against v12 on the same checks:

| | v12 now |
|---|---|
| His share of the red armor's and the mega's spawns against the stand-in | arena1 19% and 21%, Blood Run 0% and 24%, Aerowalk 9% and 21% |
| Share of the frags against the stand-in | 35%, 25%, 47% |
| Race rounds in which a learner takes the item within ten seconds | 15 to 18% |
| In the air, speed on his way | 2%, 257 to 290 |
| Real Nightmare games, ten minutes | 14-27, 7-18, 6-13 |
| Time bare; machine gun's share of his frags | 54%; 45% (must not get worse) |

## 9. The command (as `launch_v13.py` writes it)

```
ARENA_ROOMS=yard ARENA_SETS=mg ARENA_STACK=0 RUNNER_P=0.25 ITEM_RUN_P=0.20 COLLECT_FIGHT_P=0.5 DRILL_MIX_P=0.7
INTENT_HOLD=8 STACK_PAY=1.0 STACK_WPN=1.0 STACK_BARE=0.5 STACK_LOW=1.0 STACK_TEACH=1 STYLE_P=0.75 STYLE_DMG=0.5
STYLE_BAND=0 PRO_WEAPON=1 PRO_ITEMS=1 SPAWN_TEACH=1 ITEM_BELIEF=1 SHOT_COST=0.10 AMMO_PACKS=0 ARMOR_COST=0.33
CONTEST_P=0.15 AIM_LEVEL=3 KEY_RATE=5 PRO_JUMP=1 GPU_MEM_FRACTION=0.80

python sim/train_duel_rnn.py --env duel_env_ffa --group 2,3,2,4,2 --map bloodrun,aerowalk,lostworld --workers 21
  --matches 240 --steps 384 --run duel_gru_v13 --resume --minutes <to 07:00> --gamma 0.999 --react-ms 100
  --acquire-ms 200 --kind-p 1,0,0,0 --drill-weapons rl --lab-p 0,0,1 --arena-len 180 --bot-p 0 --teacher none
  --teach 0.5 --teach-minutes 240 --weapon-teach 1.0 --weapon-teach-minutes 240 --minibatches 64 --lr 1e-4
  --lr-minutes 1440 --lr-end 1.0 --lam 0.98 --close-floor 0 --loadout-p 0,1,0,0 --close-minutes 1 --intent-teach 2.0
  --intent-teach-minutes 1000000 --dmg-taken-w 1.0 --ent-coef 0.005 --ent-heads 0,0,0.25,0.25,0.25,0,0.5,0,1,1,0.1
  --dmg-reward 0.005 --item-reward 0.75 --item-loss 0.5 --intent-seek 1.0 --intent-seek-minutes 0 --stack-p 0
  --near-item-p 0 --teach-trunk 0.05 --kl-heads 10 --fade-start 4834.27
```

`--teach-trunk 0.05` is the proposal of section 7 (left out, the list is as approved); `--kl-heads 10` measures the step
per output every tenth update; `--fade-start` keeps the teachers' fade across a resume.

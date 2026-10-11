# `duel_gru_v15b`: the legs run, the manifest (2026-10-10 night)

**Which run is which.** v14's end (the save of 10:57 on 2026-10-10) is on the public server and is the control of every
check here. v15's first start (`duel_gru_v15`, 17:10 to 18:54) was stopped: [MANIFEST_v15.md](MANIFEST_v15.md), section 0.
**v15b is the run of this document**: from v14's end, the movement fix alone. `duel_gru_v15tW` is a scratch arm beside
it (v15's rounds without the teacher's lesson, half size), not a run. The day's log: [2026-10-10](../results/2026-10-10.md).

## 0. The owner's decisions (2026-10-10 evening)

| When | Decision |
|---|---|
| 20:50 | "So your recommendation is 'build movement/fighting as a switch' and let him decide when to use it? I like it. Let's build it and try it. The computer is yours to manage experiments with until 7am. I would like a report at 7 please." |
| 20:50 | "It might not make [sense] to make both the weapon changes and movement changes in one go. If you want to run them in parallel or push the weapon changes to tomorrow that is also fine. Write out the training manifest for the movement fix, build the necessary framework, and then start it." |
| 20:50 | v14's end stays on the public server: "a 'public beta version' starting point" |
| 20:55 | "most people have the setting turned on where if you run out of ammo it moves you to a different weapon. Give him that setting and use the weapon swaps from quake live. Fold that into whatever you run tonight" |
| standing | the last best network in the league and first in every check; his priorities: strafe jumping and keeping speed; rockets, plasma and grenades; then game awareness |

Changes during the run are written here.

## 1. The one change: the movement network is his legs

Taught as a side lesson, strafe jumping never reached him (v14 three times, v15's first start, a trial at two strengths:
the log of 2026-10-10 20:45). A network copies the movement network only loosely, and a loose copy does not strafe jump.
So it is no longer copied. It is a part of him that he switches on.

| | |
|---|---|
| **The switch** | one more output, the twelfth: his own movement, or his legs. Read ten times a second (as his keys are), held between |
| **What his legs take** | while the switch is on and he has a target: his movement keys (forward, strafe, jump), his view's turn left and right, and walk and zoom are let go. The choices are the movement network's (`move_v15n`: trained under his finger limits and with his mouse; its pupil's hops 356, 405, 410, the pros' 366, 421, 422), made from its own 61 inputs, and they pass through his hand's limits as his own keys do |
| **What stays his** | the switch itself on every reading, his view up and down, the trigger, the weapon key, his intention (which item) |
| **The target** | the item of his intention; in an item run or a jump run the run's item (in a jump run the landing first, as the movement network was trained) |
| **No way, no legs** | with no intention, on a map the movement network has no walking map of, or before the landing of one of the 19 jumps its own pupil fails at, the switch does nothing and he moves himself |
| **Two new inputs** (576) | the switch as it stands; that his legs carried him on the last frame |
| **Training** | the switch counts on the frames it was read. The outputs his legs take count only on the frames he moved himself: nothing is learnt about his own keys from frames he did not press them |
| **Pay** | nothing new. The pay for speed (0.3) and for items is what it was: his legs earn it or they do not |

Switch: `LEGS=1`, `LEGS_EVERY=4`; the network by the trainer's `--teacher move_v15n` (no label loss: `--teach 0`,
`RUN_TEACHER=0`), in checks by `LEGS_NET`.

**Where the switch starts.** A new output that starts at "never" is not found by trying: a tenth of a second on his legs
gains nothing, strafe jumping pays only when it is kept up. So its weights are placed by a fit to the plain rule of the
evening's test (legs while he has a target and no enemy has been in view for 1.5 seconds), from 261,000 frames of v14's
end playing itself with that rule (`tools/legs_init.py`). The fitted output gives the rule's answer on 94% of the frames
(legs with 0.95 where the rule says so, 0.10 where it does not, 0.02 with an enemy in view). No label and no pay says
so afterwards: from the first update the switch is his. The control and the league's older selves have the output at
"never".

## 2. What else is in, and what waits

| | v15b | Why |
|---|---|---|
| The game's weapon change on an empty weapon | on (`AUTO_SWITCH=1`): the trigger on an empty weapon brings up the highest weapon in the game's order that has ammunition (heavy machine gun, plasma, rail, lightning, rockets, grenades, shotgun, machine gun, gauntlet), after the empty click's half second and the change itself | the owner, 20:55. The control plays under it too in the checks. The half second is Quake 3's source; not measured in Quake Live yet |
| Jump runs on the pros' jumps | 10% of his time (v15's: tries at 137 of 144 jumps) | movement |
| Movement-only practice on Campgrounds, Hektik, Toxicity, Cure | 7.7% of his time | movement (owner, 13:08) |
| Enemy projectiles as a player sees them; grenades as measured | on (`PROJ_SEE=1`, `GL_QL=1`) | the owner's standing decision on what he may know; the control plays under it too |
| The teacher's lesson (labels on his keys and view) | **off** | it is what failed |
| One-weapon rounds, lives that begin with a weapon in hand, the lobber, the watcher, the holder | **off** (v14's rounds: games, a quarter of them against the item runner) | the weapon changes wait (owner: "push the weapon changes to tomorrow that is also fine") |
| Shot prices | every shot at its full price, no blind-fire rule (v14's third start) | the same |
| Everything else | as v14's third start: the six maps, the league of his last eight selves, v13 and v14's end as standing opponents in a quarter of the rollouts, the item rule at 2.0, aim and hand limits, the pay for speed 0.3 | |

His time: item runs 20%, jump runs 10%, games 70% (of all his players 7.7% are on the four movement-only maps).

## 3. What was checked before the start

| Check | Result |
|---|---|
| The simulator with the new switches off | identical in fixed runs of 600 frames to the simulator before the change (Aerowalk, two players; Blood Run, groups of three); two players in the group module identical to the duel module over 3,000 frames |
| The start network (fitted switch) against the control, 16 ten-minute duels a map | Blood Run 51%, Aerowalk 46%, Lost World 54%, Sinister 51%, Furious Heights 46%, Battleforged 46%; games 48 won, 3 drawn, 45 lost. His legs carried him 21 to 62% of his time; his time at 400 or more 3.7 to 13.0% (the control: 1.6 to 2.5%) |
| The same with the fit as it came (softer, read four times a second) | 49, 42, 40, 49, 54, 45%: games 39, 5, 52. Hence the firmer fit and ten readings a second |
| A dry run of ten minutes at half size | six updates. The policy's step 0.010 an update (v14's teacher start: 0.17), the switch's own 0.0004 to 0.0007. His legs carried him 44 to 52% of his time (26 to 34% in games: Aerowalk 9 to 13%, Furious Heights 49 to 54%), 0.5 to 1.3% of that with an enemy in view. In his runs 6.8 to 7.7 items a minute (v14's end alone: 5.8), 28% of the time fast in the air (11%), speed on his legs 324, on his own 293. The game changed his weapon 0.14 times a player-minute. (It ran with v15's shot prices; the run has v14's) |

## 4. Start, league, checks, what it is judged by

- From v14's end (lineage minute 5839), widened to 576 inputs and twelve outputs. 24 simulators of 210 games on the six
  maps and four movement-only ones: 10,920 players. To 07:00 of 2026-10-11 (the owner: the computer until 7).
- The check loop, from every save it finds free: against the control on the six maps (24 ten-minute duels a map), his
  speed profile in games (`tools/speed_profile.py`), then the stand-in on the ten maps (16 a map).
- **Judged by** (the owner's first priority): in games, his time at 400 or more and the speed from hop to hop, beside the
  pros' (17.5%; 366, 421, 422; 70% of hops gain) and the control's (1 to 2%; hops lose speed); and his duels against the
  control map by map. The trainer's own numbers: the share of his time on his legs, in games and by map, how often with
  an enemy in view, his speed on his legs and on his own, items a minute and jumps over in his runs.
- **Stopped early** (the owner left it to me): if after two hours he does not beat his own start against the control
  over the six maps, if a map falls ten points under its start value at two checks in a row, or if the switch goes to
  "never" or "always".

## 5. Known, not right yet

- **The real game cannot play it yet.** The plugins do not run his legs, and `sim/export_duel.py` does not pack the
  movement network. Until both are built (and his inputs recorded in a real game beside the simulator's) v15b lives in
  the simulator only: no Nightmare games, nothing for the public server.
- The game's weapon change is the client's, not the server's: on a server the plugin has to do it for him. The empty
  click's half second is from Quake 3's source and not measured in Quake Live.
- The movement network's pupil still takes lava in Lost World's item runs (58 points a minute) and slime on Toxicity
  (142): he has to learn where not to trust his legs.
- The legs know nothing of enemies or sound: quiet movement (walking) is his own only.
- Rocket jumps, the plasma climb, the seven jumps without tries: not in this run (B-209, B-212).

## 6. The run as started

```
ARENA_ROOMS=yard ARENA_SETS=mg ARENA_STACK=0 RUNNER_P=0.25 ITEM_RUN_P=0.20 COLLECT_FIGHT_P=0.5 DRILL_MIX_P=0.7
INTENT_HOLD=8 STACK_PAY=1.0 STACK_WPN=1.0 STACK_BARE=0.5 STACK_LOW=1.0 STACK_TEACH=1 STYLE_P=0.75 STYLE_DMG=0.5
STYLE_BAND=0 PRO_WEAPON=1 PRO_ITEMS=1 SPAWN_TEACH=1 ITEM_BELIEF=1 SHOT_COST=0.10 AMMO_PACKS=0 ARMOR_COST=0.33
CONTEST_P=0.15 AIM_LEVEL=3 PRO_JUMP=1 KEY_RATE=8 GROUND_SENSE=1 KNOW_PAY=0.5 PACE_PAY=0 TEACH_KEYS_ONLY=1 DROPS=1
SHOT_MASK=1 LAVA=1 WALK_FIX=1 QL_MOVE=1 ITEM_DROP=1 SOLIDS=1 PRO_WAYS=1 NEAREST=1 SPEED_PAY=0.3 SPEED_PAY_RUN=0.3
RUN_TEACHER=0 STACK_KEYS=0 TEACH_FREE=0 BLIND_RULE=0 HIGH_PAY=0 RULE_WALK=1 JUMPS=1 JUMP_ALL=1 JUMP_RUN_P=0.10
PROJ_SEE=1 GL_QL=1 LEGS=1 LEGS_EVERY=4 AUTO_SWITCH=1
LEGS_NET=data/sim_runs/move_v15n/policy.npz

sim\train_duel_rnn.py --env duel_env_ffa --group 2,3,2,4,2 --map
    bloodrun,aerowalk,lostworld,sinister,furiousheights,battleforged --workers 24 --matches 210 --steps 384 --run
    duel_gru_v15b --resume --minutes <minutes> --gamma 0.999 --react-ms 100 --acquire-ms 200 --kind-p 1,0,0,0
    --drill-weapons rl --lab-p 0,0,1 --arena-len 180 --bot-p 0 --teacher move_v15n --teach 0 --teach-minutes 100000
    --teach-warm 0 --weapon-teach 0 --weapon-teach-minutes 1000000 --minibatches 70 --lr 1e-4 --lr-minutes 1440
    --lr-end 1.0 --lam 0.98 --close-floor 0 --loadout-p 0,1,0,0 --close-minutes 1 --intent-teach 2.0
    --intent-teach-minutes 1000000 --dmg-taken-w 1.0 --ent-coef 0.005 --ent-heads
    0,0,0.25,0.25,0.25,0,0.5,0,1,1,0.1,0.1 --dmg-reward 0.005 --item-reward 0.75 --item-loss 0.5 --intent-seek 1.0
    --intent-seek-minutes 0 --stack-p 0 --near-item-p 0 --kl-heads 10 --teach-trunk 0.05 --teach-trunk-move 1.0
    --anchor-p 0.25 --move-maps campgrounds,hektik,toxicity,cure --move-matches 105 --fade-start <the lineage's
    minute at the start>
```

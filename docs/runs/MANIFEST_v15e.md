# `duel_gru_v15e`: the manifest for the night of 2026-10-11 (for the owner's go; not started)

**Which run is which.** v15c's end is on the public server since 13:01 and is the control here. v15f was the afternoon's
trial of the enemy as a target (stopped), v15r the afternoon's trial of the rocket changes. **v15e is the run proposed
for tonight**: today's network, not attention. The attention model ([../design/V16_ATTENTION.md](../design/V16_ATTENTION.md),
[MANIFEST_v16.md](MANIFEST_v16.md)) is built over the next two days ("We should do this right not rush it").
The day's log: [2026-10-11](../results/2026-10-11.md).

## 0. The owner's decisions it rests on (2026-10-11)

| | |
|---|---|
| Rockets | "we can be more forgiving with him for how he uses rockets, reduce the cost slightly"; "Yes to the three rocket changes, but test them first before 7 and include in the report" |
| The fight as a target | "'fight' is a target ... Build this first" |
| Maps | "the 10 we have I think are the most popular in the game, if we can get those in training (maybe hold out dm6 just because there was so little data for it) and use some others for hold out that are less popular that's fine" |
| The night | "plan to train overnight" |

Changes during the run are written here.

## 1. What changes from v15c

| # | | v15c | v15e | Switch | Tried today |
|---|---|---|---|---|---|
| 1 | **Games on all ten maps** | games on six; movement only on Campgrounds, Hektik, Toxicity, Cure | games, item runs and jump runs on all ten; thirty simulators, three a map, 10,080 players as before | `--map` (ten), `--group 2,3,2,4,2,2,3` | no. He has never fought on the four: on the public server he died in Toxicity's slime |
| 2 | **A rocket shot at half its price** | full price | half | `SHOT_W=rl:0.5,gl:0,pg:0` | `duel_gru_v15r`, full size, 165 minutes from v15c's end: his rocket use did not change (in hand 21.2% in the first half hour and 21.3% in the last; 0.003 blind rockets a player-minute throughout; 2.4 rockets a minute against himself, v15c 2.1). No harm: its end against v15c's end with the seats swapped is level: 69 games won, 7 drawn, 68 lost (48.9% of the frags) |
| 3 | **A blind rocket free at the pros' places** | free as a rocket jump, near where he believes the enemy is, or on the enemy's likely way | also within 150 units of one of the 24 places a map where the pros' blind shots land (the six maps; the four others when their lists are made) | `BLIND_PLACES=150` | the same trial |
| 4 | **A wasted blind rocket costs half** | 6 points of damage | 3 | `BLIND_RL_DMG=3` | the same trial |
| 5 | **The enemy as a target, from the narrow rule** (a choice: section 4) | none | a ninth intention; its start fitted to: strong and armed, the enemy spawned under 10 s ago and was seen within 4 | `FIGHT_TARGET=1` | by the broad rule it lost (39% against v15c's end; it cost him his items); by this narrow one it was level in probes (21 games won, 1 drawn, 26 lost; the same network on both sides: 17, 6, 25) and the enemy was his target 8% of his time |
| 6 | **Where it starts** | v15b's end | the rocket trial's end (`duel_gru_v15r`: v15c's end after 165 more minutes with the rocket changes, level with v15c's end), with the enemy as a target fitted on top if it is in | | |

Unchanged: his legs with two readings to switch off, the pay for speed (0.5 in games), the weapon rounds (lives that
begin with a weapon in hand, one-weapon rounds, the lobber, the watcher, the holder), jump runs and item runs, the
game's weapon change on an empty weapon, the item rule, aim and hand limits, the league of his last eight selves with
v15b's and v15c's ends as standing opponents in a quarter of the rollouts.

## 2. What it is judged by

The owner's priorities, each with its number from today (`tools/bobby_yardsticks.py`, v15c's end beside the pros):

| | v15c's end | The pros |
|---|---|---|
| Speed kept: his time at 400 or more while travelling; hops 1 to 3 | 9.4%; 332, 389, 384 | 17.5%; 366, 421, 422 |
| Rockets a minute; fired with no enemy in view | 2.1; 0.3% | 10.8; 50% |
| Closing when stacked: the enemy just fragged / otherwise | +34 / +32 | +37 / +5 |
| On the four maps new to games: against the stand-in | Campgrounds 71%, Hektik 59%, Toxicity 79%, Cure 70% | |
| His own deaths a game on Toxicity (slime) | to be measured at the start | |
| Against the control, map by map, seats swapped in half of the games | level is 50% | |

## 3. Start, league, checks, stopping

- Full size, to 07:00 of 2026-10-12. The start is kept as `policy_start_v15e.pt`.
- The check loop, from every save it finds free: against v15c's end on the ten maps, his speed profile in games, and
  every third time the stand-in on the ten maps and on House of Decay (a map he never sees in training: section 4).
  In the morning: the yardsticks beside the pros', and real games against the game's Nightmare bot on the quiet PC.
- Stopped: under 45% against the control at two checks in a row (level is 50% with the seats swapped), or a map ten
  points under at two checks.
  The wake-ups watch for a stall (no update for ten minutes).

## 4. For the owner to decide

1. **The fight target in or out** (row 5). My recommendation: in, from the narrow rule. It did not lose, it is the
   behaviour asked for, and he is free to drop it as he dropped the broad one. It will not by itself make him read the
   enemy's state: that is v16.
2. **Campgrounds in training or held out.** The archive has only 6 demos of it in today's format but 212 usable ones
   from 2010 on in the older format, so the demo count is no reason to keep it out. My recommendation: in.
3. **The held-out map: House of Decay** (236 usable demos, no doors, prepared and checked today; it has lava, no red
   armor and no rail). Dismemberment is the only other candidate with demos (142, 50 of them recent); it needs your
   word, and two faults in its walking map mended first.
4. **The rocket changes in or out**, on the trial's numbers (row 2).

## 5. Known, not right yet

- The duel check was not even between its seats: the same network on both gave the first-named side 47% of the frags
  (55 games to 83 of 144). The cause is not found (B-220); this run's checks seat him on the odd seats in every second
  process (`tools/duel_eval.py --swap`), so level is 50% here and 47% in every number from before.
- In real games he holds plasma 18 to 40% of the time on Blood Run, in the simulator 3% (B-213): not explained.
- The four maps new to games have no list of the pros' places yet (being pulled): row 3 does nothing there until then.
- Three things change at once again (maps, rockets, the fight target); the yardsticks separate them in the morning.
- A seed for rockets with nobody in view was probed and is not in this run: a rule that presses fire is level in games
  (20 games won, 6 drawn, 22 lost against 17, 6, 25 without) but its rockets do not hit; the view has to be turned to
  where the enemy comes out as well (the log of 2026-10-11 19:00).
- Nothing in this run is new for his speed, the owner's first priority. Measured today (the log of 19:00): carried by
  his legs he is as fast as the pros (at 400 or more 20% of that time; past 500 after six seconds), and the time at
  speed is lost where he has no target and stands on his own feet, around fights, and in stretches of under a second.
  More readings to end a stretch change nothing. The fix is in the next model: a target that is never "nothing"
  and his legs as a trainable part ([MANIFEST_v16.md](MANIFEST_v16.md)).

## 6. The run as it would be started

```
ARENA_ROOMS=yard ARENA_SETS=mg ARENA_STACK=0 RUNNER_P=0.30 ITEM_RUN_P=0.20 COLLECT_FIGHT_P=0.5 DRILL_MIX_P=0.7 INTENT_HOLD=8 STACK_PAY=1.0 STACK_WPN=1.0 STACK_BARE=0.5 STACK_LOW=1.0 STACK_TEACH=1 STYLE_P=0.75 STYLE_DMG=0.5 STYLE_BAND=0 PRO_WEAPON=1 PRO_ITEMS=1 SPAWN_TEACH=1 ITEM_BELIEF=1 SHOT_COST=0.10 AMMO_PACKS=0 ARMOR_COST=0.33 CONTEST_P=0.15 AIM_LEVEL=3 PRO_JUMP=1 KEY_RATE=8 GROUND_SENSE=1 KNOW_PAY=0.5 PACE_PAY=0 TEACH_KEYS_ONLY=1 DROPS=1 SHOT_MASK=1 LAVA=1 WALK_FIX=1 QL_MOVE=1 ITEM_DROP=1 SOLIDS=1 PRO_WAYS=1 NEAREST=1 SPEED_PAY=0.5 SPEED_PAY_RUN=0.3 RUN_TEACHER=0 STACK_KEYS=0 TEACH_FREE=0 BLIND_RULE=1 HIGH_PAY=0 RULE_WALK=1 JUMPS=1 JUMP_ALL=1 JUMP_RUN_P=0.10 PROJ_SEE=1 GL_QL=1 LEGS=1 LEGS_EVERY=4 AUTO_SWITCH=1 LEGS_OFF=2 SHOT_W=rl:0.5,gl:0,pg:0 START_GUN_P=0.10 START_GUN_W=rl:0.5,pg:0.25,gl:0.25 TRICKS=1 TRICK_P=lobber:0.267,watcher:0.2,holder:0.2 BLIND_PLACES=150 BLIND_RL_DMG=3 FIGHT_TARGET=1
sim\train_duel_rnn.py --env duel_env_ffa --group 2,3,2,4,2,2,3 --map bloodrun,aerowalk,lostworld,sinister,furiousheights,battleforged,campgrounds,hektik,toxicity,cure --workers 30 --matches 168 --steps 384 --run duel_gru_v15e --resume --minutes <minutes> --gamma 0.999 --react-ms 100 --acquire-ms 200 --kind-p 0.829,0,0.171,0 --drill-weapons rl,rl,rl,rl,pg,pg,gl,gl,sg --lab-p 0,0,1 --arena-len 180 --bot-p 0 --teacher move_v15n --teach 0 --teach-minutes 100000 --teach-warm 0 --weapon-teach 0 --weapon-teach-minutes 1000000 --minibatches 80 --lr 1e-4 --lr-minutes 1440 --lr-end 1.0 --lam 0.98 --close-floor 0 --loadout-p 0,1,0,0 --close-minutes 1 --intent-teach 2.0 --intent-teach-minutes 1000000 --dmg-taken-w 1.0 --ent-coef 0.005 --ent-heads 0,0,0.25,0.25,0.25,0,0.5,0,1,1,0.1,0.1 --dmg-reward 0.005 --item-reward 0.75 --item-loss 0.5 --intent-seek 1.0 --intent-seek-minutes 0 --stack-p 0 --near-item-p 0 --kl-heads 10 --teach-trunk 0.05 --teach-trunk-move 1.0 --anchor-p 0.25 --fade-start <the lineage's minute at the start>
```

# `duel_gru_v15c`: the manifest (2026-10-11, to noon)

**Which run is which.** v14's end is on the public server (the owner, about 07:12: "hold off on the public server promotion just
yet"). v15b is the legs run of the night ([REPORT_v15b.md](../legacy/REPORT_v15b.md)); its end is the network this run starts from
and the control of its checks. **v15c is the run of this document**: v15b's end with the weapon work and two changes to
how his legs are used, from the morning of 2026-10-11 to noon. The day's log: [2026-10-11](../results/2026-10-11.md).

## 0. The owner's decisions (2026-10-11 morning)

| When | Decision |
|---|---|
| about 07:05 | "We can continue training with another [...] round check in at noon. What do you recommend putting all in it?" |
| about 07:15 | "Things I would like to see in the next run - maintaining speed longer - making better decisions on when to go fast - weapon usage. Can you continue that until noon." |
| about 07:15 | "Build out the necessary infra to get him to fight in simulator and real game with the legs. Then benchmark him [...] make sure we have all the needed build out to do the same nightmare bot evals we've been doing with this latest version" |
| about 07:25 | "Pay for speed in games - yes. Two readings - yes." The two movement modes "are fine for now but long term they in theory should blend into one 'movement' knowledge basis in the weights" |
| about 07:30 | his scores against the Nightmare bot and against v14 in a short report now and another at noon; after the noon report the work on an attention layer begins |

Changes during the run are written here.

## 1. What changes from v15b

| # | | v15b | v15c | Switch | For |
|---|---|---|---|---|---|
| 1 | **Switching his legs off** | one reading of "my own movement" ends a stretch | two readings in a row (0.2 seconds) | `LEGS_OFF=2` | keeping speed longer: 62 to 73% of his stretches ended on a single "no" with no enemy in view and most lasted under a second |
| 2 | **The pay for speed in games** | 0.3 | 0.5 (in his runs it stays 0.3) | `SPEED_PAY=0.5` | when to go fast: seven hours at 0.3 did not move his time at speed (8 to 9% of his travelling) |
| 3 | **Lives that begin with a weapon in hand** | none | 10% of his lives in games: rockets half, plasma and grenades a quarter each | `START_GUN_P=0.10`, `START_GUN_W` | weapon usage (rockets option A of 2026-10-10) |
| 4 | **One-weapon rounds** | none | about 5% of his time: 15 seconds, both with the same weapon: rockets 4 in 9, plasma 2, grenades 2, shotgun 1 | `--kind-p 0.829,0,0.171,0`, `--drill-weapons` | the same; to be turned down "once he starts to understand them" |
| 5 | **Scripted opponents** | the item runner in 25% of his games | in 30%: the runner, the lobber (plasma, grenades at exits), the watcher (rail from a post), the holder | `TRICKS=1`, `TRICK_P`, `RUNNER_P=0.30` | the same |
| 6 | **Shot prices** | every shot at its full price | plasma and grenade shots free; a rocket with no enemy in view is judged by where it lands | `SHOT_W=gl:0,pg:0`, `BLIND_RULE=1` | the same |
| 7 | **The control** | v14's end | v15b's end in every check; v14's end and v15b's end as standing opponents in a quarter of the rollouts; v14's end once more at the end | `--anchor-p 0.25` | the standing rule |

Unchanged: his legs and their network (`move_v15n`), the switch read ten times a second, the game's weapon change on an
empty weapon, jump runs (10%), item runs (20%), movement-only practice on four maps, projectile sight, the item rule,
aim and hand limits. Rows 3 to 6 are v15's first start as it was at its stop; they ran 44 minutes as a side arm without
the teacher's lesson: his runs held and he stood at 47 to 48% against v14's end.

## 2. What was checked before the start

| Check | Result |
|---|---|
| Two readings to switch off, on v15b's end against v14's end (24 ten-minute duels a map, no training) | Blood Run 52%, Aerowalk 52%, Lost World 44%, Sinister 60%, Furious Heights 66%, Battleforged 54%: games 95 won, 5 drawn, 44 lost (with one reading, the check of 434 minutes: 89, 7, 48). His time at 400 or more 11.7% of all his time (10.4%) |
| The group module after the change | two players identical to the duel module over 3,000 frames; with `LEGS_OFF=1` nothing changes |
| A dry run | none: no new teacher and no new input; the first updates of the run are read instead (the start is kept as `policy_start_v15c.pt`) |

## 3. Checks, what it is judged by, stopping

- The check loop, from every save it finds free: against v15b's end on the six maps (24 ten-minute duels a map), his
  speed profile in games, every third time the stand-in on the ten maps. At noon: the end against v14's end, and real
  games against the game's Nightmare bot once the server side is built (B-213) and the PC is quiet.
- **Judged by**: (1) keeping speed: his time at 400 or more while travelling and the speed at hops 1 to 3, the length of
  his stretches on his legs; (2) rockets, plasma and grenades: time in hand in games, frags and hits by weapon; and his
  duels against v15b's end map by map.
- **Stopped early**: under 45% against v15b's end at two checks in a row, or a map ten points under at two checks.

## 4. Known, not right yet

- The server side for his legs is being built beside this run (B-213); until it is tested no real game.
- One-weapon rounds and lives that begin with a weapon change what a "game" is for part of his time: the weapon shares
  of the trainer's metrics are for games only.
- Three things change at once (rows 1, 2, and 3 to 6): the speed profile reads the first two, the weapon numbers the
  third; a fall in his duels cannot be laid at one of them without a further test.

## 5. The run as started

```
ARENA_ROOMS=yard ARENA_SETS=mg ARENA_STACK=0 RUNNER_P=0.30 ITEM_RUN_P=0.20 COLLECT_FIGHT_P=0.5 DRILL_MIX_P=0.7
INTENT_HOLD=8 STACK_PAY=1.0 STACK_WPN=1.0 STACK_BARE=0.5 STACK_LOW=1.0 STACK_TEACH=1 STYLE_P=0.75 STYLE_DMG=0.5
STYLE_BAND=0 PRO_WEAPON=1 PRO_ITEMS=1 SPAWN_TEACH=1 ITEM_BELIEF=1 SHOT_COST=0.10 AMMO_PACKS=0 ARMOR_COST=0.33
CONTEST_P=0.15 AIM_LEVEL=3 PRO_JUMP=1 KEY_RATE=8 GROUND_SENSE=1 KNOW_PAY=0.5 PACE_PAY=0 TEACH_KEYS_ONLY=1 DROPS=1
SHOT_MASK=1 LAVA=1 WALK_FIX=1 QL_MOVE=1 ITEM_DROP=1 SOLIDS=1 PRO_WAYS=1 NEAREST=1 SPEED_PAY=0.5 SPEED_PAY_RUN=0.3
RUN_TEACHER=0 STACK_KEYS=0 TEACH_FREE=0 BLIND_RULE=1 HIGH_PAY=0 RULE_WALK=1 JUMPS=1 JUMP_ALL=1 JUMP_RUN_P=0.10
PROJ_SEE=1 GL_QL=1 LEGS=1 LEGS_EVERY=4 AUTO_SWITCH=1 LEGS_OFF=2 SHOT_W=gl:0,pg:0 START_GUN_P=0.10
START_GUN_W=rl:0.5,pg:0.25,gl:0.25 TRICKS=1 TRICK_P=lobber:0.267,watcher:0.2,holder:0.2
LEGS_NET=data/sim_runs/move_v15n/policy.npz

sim\train_duel_rnn.py --env duel_env_ffa --group 2,3,2,4,2 --map
    bloodrun,aerowalk,lostworld,sinister,furiousheights,battleforged --workers 24 --matches 210 --steps 384 --run
    duel_gru_v15c --resume --minutes <minutes> --gamma 0.999 --react-ms 100 --acquire-ms 200 --kind-p
    0.829,0,0.171,0 --drill-weapons rl,rl,rl,rl,pg,pg,gl,gl,sg --lab-p 0,0,1 --arena-len 180 --bot-p 0 --teacher
    move_v15n --teach 0 --teach-minutes 100000 --teach-warm 0 --weapon-teach 0 --weapon-teach-minutes 1000000
    --minibatches 80 --lr 1e-4 --lr-minutes 1440 --lr-end 1.0 --lam 0.98 --close-floor 0 --loadout-p 0,1,0,0
    --close-minutes 1 --intent-teach 2.0 --intent-teach-minutes 1000000 --dmg-taken-w 1.0 --ent-coef 0.005
    --ent-heads 0,0,0.25,0.25,0.25,0,0.5,0,1,1,0.1,0.1 --dmg-reward 0.005 --item-reward 0.75 --item-loss 0.5
    --intent-seek 1.0 --intent-seek-minutes 0 --stack-p 0 --near-item-p 0 --kl-heads 10 --teach-trunk 0.05
    --teach-trunk-move 1.0 --anchor-p 0.25 --move-maps campgrounds,hektik,toxicity,cure --move-matches 105
    --fade-start <the lineage's minute at the start>
```

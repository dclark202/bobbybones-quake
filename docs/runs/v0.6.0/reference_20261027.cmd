rem v0.6.0 as it ran on 2026-10-27 night (the reference for tools/run/check_settings.py; not to be run)
exit /b 1
@echo off
rem ==== v0.5.0 (owner, 2026-10-26; docs/v0.5.0/RUN_v0.5.0.md): from v0.4.2b's end, v0.4.3 and v0.4.4 scrapped. Made from v0.4.2b's
rem own command (run_duel_gru_v0_4_2_r4.cmd) by scratchpad v050/make_cmd.py, every change listed there:
rem  code ql-bot-v050 (branch v050: the loophole fixes); WEAPON_FREE SPEED_LOS GONE_BELIEF TELEFRAG JRUN_SPEED_BACK SMALL_ZERO on;
rem  !aim default: AIM_LEVEL 3, --acquire-ms 225 (100 tracking as before), PERCEPT_SPEED live in live.json (target 0.075),
rem  PERCEPT_SPEED_MAX 5; --dmg-taken-w 1.0; mix of all training 60% whole games / 30% the pros' mid-game starts / 10% jump runs;
rem  jump focus aerowalk:1;campgrounds:9 at 4x (the pros' b2r run-ups, PRO_JSTART_P 0.5 as before); the brain's people lesson at
rem  0.35 from the start; the shadow win value added (no effect on play), the 'in control' shadow as before; no strategy head.
rem ==== v0.6.0 (owner, 2026-10-27): v0.5.0's setup from v0.4.2b's end with the aim2 calibration; code ql-bot-aim2 (branch
rem  aim2); no movement practice (JUMP_RUN_P 0, jump focus off: 67% whole games / 33% the pros' mid-game starts); ~6 h
rem  (--minutes 420). The aim2 values: scratch\aim2_env.cmd. Made by scratchpad v060/make_cmd_v060.py.
cd /d C:\Users\dacla\ql-bot-aim2
set GPU_MEM_FRACTION=0.90
if "%LEARN%"=="" set LEARN=--overlap 1 --learn-nosync 1
set LEGS_NET=C:\Users\dacla\ql-bot\data\sim_runs\move_v17_look\policy.npz
set OPENBLAS_NUM_THREADS=1
set EN_STACK=1
set HUNT=1
set LEGS_IN=1
set LEGS_LOOK=1
set LEGS_TURN_ADD=1
set WALK_NO_JUMP=1
set HOP_QUIET=1
set HOP_QUIET_HEARD=1
set HOP_QUIET_NEAR=300
set AWARE_LOG=1
set QL_FLOAT=1
set QL_FWD=0
set QL_LAND=1
set QL_JUMP=1
set RL_QL=1
set STACK_DIFF=0.7
set ITEM_FLAT=MH:0.30,RA:0.30,YA:0.15
set BIG_ONCE=1
set BIG_PICK=0.10
set STACK_BARE_MAX=1
set PYTHONFAULTHANDLER=1
set ARENA_ROOMS=yard
set ARENA_SETS=mg
set ARENA_STACK=0
set RUNNER_P=0.30
set ITEM_RUN_P=0
set COLLECT_FIGHT_P=0
set OVERTIME=1
set DRILL_MIX_P=0.7
set INTENT_HOLD=8
set STACK_PAY=0
set STACK_WPN=0
set STACK_BARE=0.25
set STACK_LOW=0
set STACK_TEACH=1
set STYLE_P=0
set STYLE_DMG=0.5
set STYLE_BAND=0
set PRO_WEAPON=1
set PRO_ITEMS=1
set SPAWN_TEACH=1
set ITEM_BELIEF=1
set SHOT_COST=0.10
set AMMO_PACKS=0
set ARMOR_COST=1
set CONTEST_P=0.10
rem v0.3.9 (owner, 2026-10-21: aim 4 "feels fun to play against and did not seem overbearing")
set AIM_LEVEL=3
set PRO_JUMP=1
set KEY_RATE=8
set GROUND_SENSE=1
set KNOW_PAY=0.25
set PACE_PAY=0
set TEACH_KEYS_ONLY=1
set DROPS=1
set SHOT_MASK=1
set LAVA=1
set WALK_FIX=1
set QL_MOVE=1
set ITEM_DROP=1
set SOLIDS=1
set PRO_WAYS=1
set NEAREST=1
set SPEED_PAY=0.25
set SPEED_PAY_RUN=0.4
set RUN_TEACHER=0
set STACK_KEYS=0
set TEACH_FREE=0
set BLIND_RULE=1
set HIGH_PAY=0
set RULE_WALK=1
set JUMPS=1
set JUMP_ALL=1
set JUMP_RUN_P=0
set PROJ_SEE=1
set GL_QL=1
set LEGS=1
set LEGS_EVERY=4
set AUTO_SWITCH=1
set LEGS_OFF=2
rem shot prices (owner, 2026-10-21): the rail at 0.2 of what it was, the shotgun at 0.5
set SHOT_W=rl:0.5,gl:0,pg:0,rg:0.2,sg:0.5
set START_GUN_P=0
set START_GUN_W=rl:0.5,pg:0.25,gl:0.25
set TRICKS=1
set TRICK_P=lobber:0.267,watcher:0.2,holder:0.2
set BLIND_PLACES=150
set BLIND_RL_DMG=0
rem v0.3.9 (owner, 2026-10-21: "He should use jumping to get placed quickly. Period."): the hop pay was 2.1 a player-minute
rem in v0.3.8 (0.9 in v0.3.7, 0.4 in v0.3.6), take-offs 38/min, no more speed: each new chain re-earned the 320->480 gain.
rem Off, the chain-hop pay off; jumping pays only through SPEED_PAY (speed over new ground on his way); a small cost for a
rem take-off with nobody in view in games and item runs, so a hop that buys no speed is a loss (live)
set HOP_PAY=0
rem v0.3.10: the jump cost off (live 0 in v0.3.9 since 2026-10-22 07:22)
set JUMP_COST=0
set TARGETS=1
set LEGS_KEEP=0.9
set OPENINGS=1
set OPEN_SILENT=1
set GAME_P=0.65
set MID_START_P=0
set TARGETS_FREE=2
set RULE_CONTEST=2
set RULE_HUNT=50
rem v0.3.6 (owner's go 2026-10-18): rocket aim, pre-fire (rl/gl/pg), emergence point; long-range rail pay; jump runs weighted
rem to his misses, half begun 3-5 s back at 300 u/s; 70/10/10/10; NO rocket-jump runs (RJ_RUN_P unset = 0). Hot reload: <run>\live.json.
set RL_AIM=1
set PREFIRE=1
set EMERGE_IN=1
set RAIL_FAR_PAY=0.12
rem rail (owner, 2026-10-21): the long-rail pay ramps from 500 to 800 units, then level; a flat 0.05 for every rail hit after the first until a miss
set RAIL_FAR_LO=500
set RAIL_FAR_HI=800
rem v0.3.9: the rail streak pay removed (owner, 2026-10-21); the other rail pays kept
set RAIL_STREAK_PAY=0
set RAIL_STREAK_CAP=1
set JUMP_WEIGHT=1
set JUMP_FAR_P=0.5
rem v0.3.7 (2026-10-19): the owner's shares 70/10/10/5/5 (games, pro starts, rail starts, item runs, jump runs; no rocket-jump runs), the jump read on a share of
rem frames, auto-hop as the servers run it, the chain-hop pay, missiles as points, the game's respawn delay and spawn points,
rem QL_FWD=0 (the duel factory's pmove_BunnyHop 0, measured 2026-10-19)
set PRO_START_P=0.35
set RAIL_START_P=0
set RAIL_START_LEN=30
set RAIL_START_YAW=15
set JUMP_EVERY=1
set AUTO_HOP=1
set HOP_CHAIN=0
set MISSILE_POINT=1
set RESPAWN_QL=1
set SPAWN_QL=1
rem (2026-10-19 ~21:00, the owner: "I would like this in the tonight run") restarted at a save from ql-bot-v037s (12e1b7c):
rem the big three paid a life by order 0.10/0.06/0.05 (BIG_PICK_SEQ takes the place of BIG_PICK/BIG_ONCE); JUMP_EVERY also in live.json
set BIG_PICK_SEQ=0.10,0.06,0.05
rem the zoom as a person sees it (the owner: "put these fixes in as well, on a safe save"): sight error x0.4 zoomed, the
rem fine-aim threshold in hand degrees (a PLAY_VAR: the checkpoint, checks and plugins carry it). RG_FAR_PRICE stays unset (held)
set ZOOM_PERCEPT=1
rem ---- v0.3.8 (2026-10-20): every limit written out (a default is not stored in the checkpoint) ----
rem shares 65 / 10 / 15 / 5 / 5 (whole games, pro starts, rail starts, item runs, jump runs); jump key every frame; long rail pay 0.12
rem fire timing as Quake Live (every weapon), the drift input, the senses as a person has them, the mouse low-pass, the duel preset
set FIRE_QL=1
rem 2026-10-21 (owner: option B): drift inputs off (zeros: the A/B of save 270 read 51.8% on, 51.6% off)
set DRIFT_IN=0
rem the stuck spots as tries in advanced movement (owner, 2026-10-21); no rocket jumps yet
set STUCK_STARTS=1
set DRIFT_DELAY=50
set DRIFT_SIGMA=0
set DRIFT_WEBER=0.10
set DRIFT_MIN=2
set DRIFT_TAU=0.15
set DRIFT_SMOOTH=0.1
set HEAR_FIX=1
set HEAR_QL=1
rem hearing level B (owner, 2026-10-21: "I honestly don't mind him being 'a bit superhuman'"): the void rule kept, the
rem placing of a sound loosened: 3 deg, 10% of the distance, 15 u in height, a footstep every 0.3 s (was 10 / 0.3 / 40 / 0.55)
set HF_STEP_DT=0.3
set HF_STEP_SPEED=150
set HF_DIR=3
set HF_LOUD=0.1
set HF_HUM_TAU=1
set HF_UP=15
set VEL_FIX=1
set VEL_DELAY_MS=200
set VEL_WEBER=0.2
set VEL_TAU=0.3
set VEL_MIN=30
set RANGE_FIX=1
set RANGE_WEBER=0.15
set RANGE_TAU=0.5
set PROJ_FIX=1
set PROJ_NOTICE_MS=100
set PROJ_READ_MS=100
set SENSE_MINOR=1
set SM_FACE_DEG=15
set SM_FACE_TAU=0.5
set SM_ITEM_SD=0.75
set HAND_BAND=1
set HB_FC=4.0
set HB_BETA=0.5
set DUEL_QL=1
set DQ_JUMP_MS=50
set DQ_WADE=0.75
set DQ_PICK_Z=51
rem (2026-10-20 00:15, rail lever 3, the owner's standing OK of 2026-10-19 for a stall at ~u80): restarted at save 110; rail starts
rem facing within 15 degrees (was 45) and 30 s long (was 15); RAIL_FAR_PAY 0.25 by live.json (lever 1, 22:57)
rem (2026-10-19, the owner) training on 16 of the 20 cores (C3FFF): four E cores (14-17) left for Windows, Quake Live and a play-test server
rem (the trainer pinned to the P cores was slower in a dry run: learning 133 s against 126 unpinned)
rem 2026-10-20 safe restart at save 70 (owner): the jumps he makes >=50% in jump runs (>=30 tries, v0.3.7+v0.3.8 counters) open in games;
rem jump runs skip the ones he makes >=80% and pay 0.5 for getting over the gap; item pay 0.35/0.35/0.18 -> 0.30/0.30/0.15 (more action)
rem 2026-10-21 midday (owner: "if a jump is failing in games remove that route from the games and put it back in the trainer"):
rem closed in games (under ~45% in 40 measured games): Lost World 9, Hektik 4 and 7, Sinister 4, 24 and 25, Blood Run 14 (82 open)
set JUMP_OPEN=bloodrun:1,3,5,7,8,9,11,13,26;aerowalk:3,5,10,18,20,21;lostworld:1,2,3,6,7,10,11,12,14,15,16,17,18,21,22,23,24;sinister:1,2,7,10,13,14,18,19,20,22,27;furiousheights:5,7,8,11,14,16,18,21,22,23,24,26,28;battleforged:1,5,6;campgrounds:1,3,15;hektik:1,2,3,5,9,10,12,13,14;toxicity:1,2,3,4,8;cure:1,5,7,9,13,14
rem closed jumps stay in practice whatever his rate there; a jump run's target only after the jump (Blood Run id 2 loop);
rem varied starts (speed, line, view; around the pros' run-ups)
set JUMP_KEEP_CLOSED=1
set JUMP_PAST_PICK=1
set JUMP_VARY=1
rem gentler weighting (owner: "more practice with the ones he fails, but capped ... so he actually still gets to practice
rem each one"): weight = max(0.3, 1 - success), at most 3.3x between the worst and the best; no one jump above 25 percent
set JUMP_W_FLOOR=0.3
set JUMP_W_CAP=0.25
rem 2026-10-21 afternoon (code 53a6056): jump-run start spots inside solid left out or moved (Aerowalk 4 stood still
rem on every try); a jump made from his own take-off counts as made (floor touch at the landing after a flight from
rem 60 percent of the gap away, not from below)
set JUMP_SOLID_FIX=1
rem 2026-10-21 evening (the jump videos): a make must leave the floor on the take-off's side at its height (=1 counted
rem hops onto the landing from beyond it and walks round); fast jumps (pros' take-off 420 u/s or more) start their near
rem tries 1.2-2.5 s back, moving (room for two hops); no start on a take-off's lip; far starts for every jump; the
rem pros' run-ups to Aerowalk's red armor from up to 2 s before their take-off (their hops included)
set JUMP_OVER_ANY=3
set JUMP_RUNUP=420
set PRO_JSTART_MAXLEAD=80
set JUMP_W_DROP=0.8
set JUMP_OVER_PAY=0.5
rem 2026-10-20 ~22:00 safe restart (owner: "give him more a fighting chance with it ... he should get it tonight"): half the tries at
rem Aerowalk's red armor jump begin in a pro's own run-up 0.2-1 s before the take-off; that jump 10x the practice weight
set PRO_JSTART_P=0.5
rem 2026-10-21 ~07:00 safe restart (owner: "I don't think the rail starts are doing anything so let's drop them, give 5% each to
rem jumps, full games and pro starts"; then "Do we still need the movement rounds? I think not ... 70 full games 20 pro starts 10 jumps"):
rem shares 70 / 20 / 10 (games, pro starts, jump runs); no rail starts, no item runs
set JUMP_FOCUS=
set JUMP_FOCUS_W=4
rem v0.3.9 (owner, 2026-10-21 night: "preaiming. that's it"): a zero-sum pay at each fresh sighting for the crosshair nearer the
rem enemy than his on you; staggered first games (no restart wave); Aerowalk 16 out of practice ("nonsensical");
rem a jump's landing must be reached (JUMP_OVER_ANY=3: Sinister 29's run-off drop)
set PREAIM_PAY=0.05
set STAGGER_START=1
set JUMP_SKIP=aerowalk:16
rem v0.3.10 (owner, 2026-10-22: "small noise pay for LG ... monitor over the first few hours and adjust if needed"): a cost of
rem 0.004 a second for the LG in hand while by his own senses the enemy is away (not in view 3 s+, nothing heard 2 s), ramped
rem 3 s -> 10 s, games and pro starts (live); his own LG muffles footsteps (700 u; firing 500, other sounds 1000) and the
rem enemy's LG hum (a PLAY_VAR); the look-back pay ("back pay for having been looking in the right direction prior to enemy
rem seen"): zero-sum at each fresh sighting, the last 1.5 s of his view against the spot the enemy came out at (live)
rem the LG noise cost left out (owner, 2026-10-22: "it's a bandaid, not a principled approach")
set LG_QUIET_COST=0
set LG_DEAF=1
set WATCH_PAY=0.03
rem v0.3.11 (owner, 2026-10-22: "Have Bobby keep a running estimate of position, stack, ownership of weapons, direction, speed,
rem etc of the enemy in memory, with some estimate of uncertainty ... paid proportional to how accurate this is ... zero sum"):
rem the truth columns for his readout of the enemy (labels only, never inputs)
set TRACK_TRUTH=1
rem v0.3.11b (the owner, 2026-10-22 ~17:05): the second start from v0.3.10's end with v0.3.11's trained readout, a slow opening;
rem the lesson's weight, its share into his memory and the pay are live.json names (TRACK_W, TRACK_TRUNK, INFO_PAY)
rem v0.4.0 stage A (the owner, 2026-10-22 evening: the enemy tracking must not share the policy's memory, "these two need
rem to be separate networks"; v0.4 starts now as "the brain"): from v0.3.10's end (tools/belief_init.py add, optimizer kept);
rem a belief memory of its own (sim/belief.py: 256, a tick every 8 frames on the mean and max of the frames since the last)
rem tracks the enemy and v0.3.11's readout reads it; the lesson reaches the belief and the readout only (no gradient into
rem the policy, checked every update: track.iso); the knowledge pay off; TRACK_TRUTH=1 kept (labels only)
rem v0.4.0b (2026-10-23, branch v040z): the restart at a save with the brain's new outputs; the hands' training unchanged.
rem The readout's second part (sim/track_z.py; tools/belief_init.py add-zones on the save): odds over the map's zones (owner:
rem "let's replace the 10+s range with the distribution over locations"), the enemy's speed and way over 0.2 s (owner: "speed+
rem direction separately makes sense"); lesson only, rising over 60 min (live.json TRACK_Z_W: a factor, 0 pauses); the old
rem velocity part out of the lesson (vel:0; still counted beside the new). TRACK_Z=1: their truth (labels only).
set TRACK_Z=1
rem Rocket jump practice for Aerowalk's red armor only (owner, 2026-10-23), out of the jump runs' share (RJ_FROM_JUMP): the
rem 10% of advanced movement stays 10%. RJ_RUN_P starts at 0 and is opened by live_settings.env (0 -> ~0.025 over ~3 h)
set RJ_ONLY=aerowalk:1
set RJ_CLEARED=1
set RJ_LOOK_P=0.5
rem the look-down of half the tries at 70 degrees (sim/rj_clear.json's clearing execution), not the pros' 47: 47 does not
rem clear it in the run's physics even standing at the take-off (2026-10-23: from the practice's 8 start spots, 5 cleared at 70 with a stop)
set RJ_LOOK_CLEAR=1
set RJ_FROM_JUMP=1
rem v0.4.1 (docs/v0.4.0/RUN_v0.4.1.md; branch v041): the brain's answer as one more token of the hands' attention (sim/btoken.py:
rem the place +- spread AND the zone odds always, speed and direction, stack band, weapon in hand, weapons owned, the time since he
rem last noticed the enemy; kept in map coordinates and turned to his pose every frame), behind a gate that is exactly shut (the
rem token is not there) for the first hour, then opens 0 -> 1 over 4 h (live.json: BTOK_GATE_CAP 0 closes it at once, a value caps
rem it; BTOK_GATE_OPEN 0 holds it, more minutes slow it; BELIEF_LR the brain's rate, 2.5 = half of v0.4.0's 5). The readout ahead
rem (sim/ahead.py: the enemy in 1, 2, 4 s, what he goes for, when he appears; lesson only, rising over 60 min, live AHEAD_W).
rem The track_z lesson already rose in v0.4.0b: --track-z-warm 0. BTOK_START: the minute the hour counts from = the save's minutes
rem at the first start; the SAME number on every resume (set BTOK_START=... before calling this file)
rem the item race's truth for the readout ahead (labels only): TRACK_RACE=1
set TRACK_RACE=1
rem The rocket-jump moment lesson (owner, 2026-10-23): labels only at the start; RJ_TEACH_W in live.json turns it on after the
rem gate's 10%% check; RJ_LOOK_FREE=1 (live_settings.env, the level pull off in rocket-jump tries only) goes on with it. 68 deg:
rem the pitch from which a scripted try clears the link (62: 2 of 8 starts)
set RJ_TEACH=1
set RJ_TEACH_PITCH=68
rem ---- v0.4.2a (docs/v0.4.0/RUN_v0.4.2a.md; branch v042a): the old hand-built belief faded out of the hands. The 76 rule-made
rem input columns (sim/rule_fade.py, chosen by name) times (1 - g) after the input scaling in the hands only (the brain reads them
rem unfaded); g kept with each rollout. BRAIN_READ=1: the simulator's readers of the old belief (the legs' look point, the hunt's
rem target, RULE_CONTEST, RULE_HUNT by the brain's stack band, the openings) take the brain's answer for a life drawn with chance g.
rem BLIND_BRAIN=1 (the owner's word, 2026-10-23): BLIND_RULE's pre-fire exemption and the blind rockets' test on the same draw.
set BRAIN_READ=1
set BLIND_BRAIN=1
rem (owner, 2026-10-24) the win-chance pay tracked, not paid: PAY_SPLIT (the pay by term) and WIN_SHADOW (what WIN_PAY would pay), record only
rem (branch winpay 33575d9 merged; bit-identical off and on, tools/winpay_ident.py)
set PAY_SPLIT=1
set WIN_SHADOW=1
rem ---- r3 (2026-10-24): the route copy (labels; the lesson at weight 0, opened by live.json's RJ_COPY_W) and the shadow
rem 'in control' (hindsight labels only: tools/control_ident.py, off and on identical to the bit)
rem (owner, 2026-10-24 ~19:30: "let's keep the aerowalk route out for now ... nervous about including this type of thing overnight"): no ROUTE_COPY
set CONTROL_TRUTH=1
rem v0.5.0's loophole fixes (sim/duel_env.py, each documented there; RESULTS 2026-10-26)
set WEAPON_FREE=1
set SPEED_LOS=1
set GONE_BELIEF=1
set TELEFRAG=1
set JRUN_SPEED_BACK=1
set SMALL_ZERO=1
rem !aim default's fast-target cap (PERCEPT_SPEED itself is live: live.json)
rem the aim2 model at !aim default (the calibration of 2026-10-27; the old speed term and its caps off)
call C:\Users\dacla\ql-bot-aim2\scratch\aim2_env.cmd
if "%WV_START%"=="" set WV_START=-1
if "%CTL_START%"=="" set CTL_START=-1
rem v0.4.2b (owner, 2026-10-24 night): the brain taught on people's games beside self-play (branch brainppl 4b1d881): the start
rem save = save 160 with the offline-tuned brain (data\sim_runs\brainppl\policy_brainppl.pt; KL 0.002 on the hands), the people's share of the
rem brain's lesson rising 0 -> 0.35 over 90 min (live BRAIN_HUMAN_W), sessions 0.7 / demos 0.3 of it. BH_START: -1 = this process's start;
rem on a later resume set BH_START to the first start's minute (in the log) so the opening does not begin again
if "%BH_START%"=="" set BH_START=-1
if "%RF_START%"=="" set RF_START=18411.038983547685
rem (RF_START: v0.4.1's end save, keep/policy_end_v041.pt, update 320)
if "%RF_START%"=="" (echo set RF_START to the save's minutes ^(the first start^) & exit /b 1)
start "" /b /wait /affinity C3FFF C:\Users\dacla\anaconda3\python.exe sim\train_duel_rnn.py --env duel_env_ffa --group 2 --map bloodrun,aerowalk,lostworld,sinister,furiousheights,battleforged,campgrounds,hektik,toxicity,cure --workers 30 --matches 168 --steps 384 --run duel_gru_v0_6_0 --resume --minutes 790 --gamma 0.999 --react-ms 125 --acquire-ms 225 --kind-p 1,0,0,0 --drill-weapons rl,rl,rl,rl,pg,pg,gl,gl,sg --lab-p 0,0,1 --arena-len 180 --bot-p 0 --teacher move_v17_look --teach 0 --teach-minutes 100000 --teach-warm 0 --weapon-teach 0 --weapon-teach-minutes 1000000 --minibatches 360 --lr 1e-4 --lr-minutes 1440 --lr-end 1.0 --lam 0.98 --close-floor 0 --loadout-p 0,1,0,0 --close-minutes 1 --intent-teach 9.13 --intent-teach-minutes 1643 --dmg-taken-w 1.0 --ent-coef 0.005 --ent-heads 0,0,0.25,0.25,0.25,0,0.5,0,1,1,0.1,0.1,0,0 --dmg-reward 0.0055 --item-reward 0 --item-loss 0.5 --intent-seek 1.0 --intent-seek-minutes 0 --stack-p 0 --near-item-p 0 --kl-heads 10 --teach-trunk 0.05 --teach-trunk-move 1.0 --anchor-p 0.24 --fade-start 7214.898282571636 --long-gamma 0.9998 --long-ramp 0 --obs-half --fast-gru 1 --legs-learn 1.0 --legs-ent 0 --intent-teach-floor 0.1 --aux 0.2 --aux-trunk 0 --gate-open 480 --gate-from -12 --gate-start 14397.514 --aux-heads place,near --aux-warm 0 --aux-tail --aux-fresh 5 --aux-unseen --aux-measure --turn-add-open 120 --turn-add-start 9685.137113598985 --turn-add-to 4.68 --legs-feat 1 --legs-door-lr-scale 0.25 --legs-gate 1 --legs-residual 0 --no-switch 1 --solo-self-drive 1 --belief 256 --belief-every 8 --track 0.3 --track-warm 0 --track-lr-scale 5 --belief-lr-scale 2.5 --info-pay 0 --track-parts pos:1,vel:0,band:0.5,hand:0.25,own:0.25 --track-z zone:0.5,spd:0.25,dir:0.25 --track-z-warm 0 --btoken 1 --btoken-delay 60 --btoken-open 240 --btoken-start 17278.807862214246 --ahead default --ahead-warm 60 --ahead-start 17278.807862214246 --rj-teach 0 --rj-teach-warm 120 --rj-teach-trunk 0.05 --rule-fade 1 --rule-fade-delay 0 --rule-fade-open 250 --rule-fade-start %RF_START% --control 1 --control-lr 1e-3 --control-warm 60 --control-start %CTL_START% --control-every 5 --control-hid 64 --control-src belief,both --win-value 1 --win-value-lr 1e-3 --win-value-warm 60 --win-value-start %WV_START% --brain-human C:\Users\dacla\ql-bot\data\sim_runs\brainppl\pack_ppl,C:\Users\dacla\ql-bot\data\sim_runs\brainppl\pack_demo --brain-human-mix 0.7,0.3 --brain-human-w 0.35 --brain-human-open 0 --brain-human-start -1 --brain-human-lanes 1 %LEARN% >> data\sim_runs\duel_gru_v0_6_0.log 2>&1
echo exit %ERRORLEVEL% >> data\sim_runs\duel_gru_v0_6_0.log

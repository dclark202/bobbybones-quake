# 2.1: the simulator's side of the head's choice: the candidates, the pick, the force, the drills

*2026-11-11, branch `b21`, worktree `BobbyBones-21`. Written while 1.8a trained: **nothing here has run in a simulator** (the
worktree has no data folder). What ran: the compile checks, `tools/make_ffa_env.py` (its guard passed), `tools/list_inputs.py`
(the list is unchanged: 1,092 columns, the 39 of "b21 instruction" as before), and an import of the group module that printed the
constants below. The instruction itself: [INSTRUCTION.md](INSTRUCTION.md). The trainer's side: [TRAINER_PARTS.md](TRAINER_PARTS.md).
Details the design left open are marked **(decided here)** for the owner's review (CLAUDE.md rule 10).*

All of it is behind `INSTR` (a play switch). With `INSTR=0`, or with `INSTR=1` and nothing called, the simulator is what it was:
no draw from the simulator's random stream, nothing kept that anything reads. `instr_feat()` and `instr_state()` are reads.

## The interface (`sim/duel_env.py`, the same in the generated `sim/duel_env_ffa.py`)

| Name | What |
|---|---|
| `INS_C = 32`, `INS_F = 32`, `INS_FEAT`, `NW = 9` | the candidates a seat, the numbers a candidate, their names, the weapons |
| `INS_ROW0`, `INS_ROW_VERB`, `INS_NONE_ROW` | where each verb's rows begin; each row's verb; the row "none" |
| `env.instr_feat() -> (X [n, 32, 32] float32, ok [n, 32] bool, wok [n, 9] bool)` | the candidates of this tick, whether each can be chosen, the weapons he owns with ammunition (the gauntlet always). Keeps the rows for the pick |
| `env.instr_pick(c [n], w [n], who [n] = all)` | gives each seat in `who` row `c` and weapon `w` through `instr_in()`. `c = -1`, the row "none" or a row that is not valid: no instruction. A weapon he does not own with ammunition: none asked for |
| `env.force_instr` [n, 2] int (row, weapon), `-1` = not forced | a forced seat takes the forced row and weapon inside `instr_pick()` whatever is passed, in `who` or not. Not part of a moment (`MOMENT_STATIC`): a copy cannot move a force |
| `env.ins_cur` [n] | the row he is on (`-1`: none, or an instruction given without a row) |
| `env.ins_w` [n] | the weapon asked for (`-1`: none) |
| `env.instr_state() -> [n, 6] float32` | the change signals, below |
| `env.ins_drill` [n] bool | the seat is in a drill: its instruction is the script's |

**The order at a head tick** (every 8 frames): `instr_feat()`, the head chooses, `instr_pick(c, w, who)`, then `step()`. The target
and the way follow from the next frame's `intend()`.

## The rows

| Rows | Verb | The place | The point | `when` | Valid when |
|---|---|---|---|---|---|
| 0 to 6 | go | the item (mega, red, rockets, rail, lightning, yellow, second yellow: the instance his way finds first) | none | none | the map has it |
| 7 to 10 | contest | the mega, the red, the yellows | where the brain expects the enemy in a second | none | the map has it |
| 11 to 18 | hold | the map's holding places | its best opening: of the map's doorways and corridors its place sees, the one nearest where the brain expects him in a second (no belief: nearest the place) **(decided here)** | his seconds of walking to it from his believed place | the map has the place |
| 19 to 22 | spam | the place to fire from nearest him by his way | the four spam points nearest where the brain expects him | the same | he believes a place, a place to fire from is reachable, and he owns rockets, grenades or plasma with ammunition **(decided here)** |
| 23 | push | where he believes him | the same | none | he believes a place |
| 24 to 26 | cut off | the brain's place for him 1, 2, 4 s ahead | where he believes him now | 1, 2, 4 | the brain gives its forecast |
| 27 to 29 | break off | the three ways out (and health and armor items up or due) the brain's places do not see, whose way favours him most | where the brain expects him in a second | none | there is one |
| 30 | none | | | | he is alive |
| 31 | spare | | | | never |

A row means the same thing at every tick. The spam point and the way out he is on stay in their row (and the spam's place to fire
from is kept), so "the row I am on" holds from tick to tick while the others are re-ranked **(decided here)**. A hold's opening may
change with the belief without that being another instruction (`instr_in()`'s rule changed: only a spam's point is fixed).

## The numbers of a candidate (`INS_FEAT`)

Every one from his own place and stack, the item belief's books, the brain's places and the map's own numbers. An invalid row
carries its verb alone.

| Columns | Name | What | Scale |
|---|---|---|---|
| 0 to 7 | `v_none`, `v_go`, ... `v_out` | the row's verb | 0 or 1 |
| 8 | `valid` | it can be chosen now | 0 or 1 |
| 9 | `on_now` | it is the instruction he is under (the row "none": he is under none) | 0 or 1 |
| 10, 11 | `t_me`, `t_en` | seconds of walking to the place: his; the enemy's from his believed place (2 with no belief) | / 10, at most 2 |
| 12 | `lead` | the enemy's seconds less his (each capped at 20) | / 10, −2 to 2 |
| 13 | `height` | the place's height from him | / 200, −3 to 3 |
| 14 | `range` | its distance from his eye | / 1000, at most 3 |
| 15, 16 | `fwd`, `left` | forward and left of his facing | / 1000, −3 to 3 |
| 17 to 19 | `sees_1`, `sees_2`, `sees_4` | the place sees where the brain expects the enemy in 1, 2, 4 s (the belief without the forecast) | 0 or 1 |
| 20 | `seen_me` | the place sees where he stands | 0 or 1 |
| 21, 22 | `item_up`, `item_back` | an item's row: there by what he knows; seconds until it is back | 0 or 1; / 30, at most 2 |
| 23 to 26 | `door`, `corridor`, `width`, `tele` | a spam point's or a way out's map numbers | 0 or 1; width / 1000 |
| 27 to 29 | `pt_given`, `pt_range`, `pt_line` | the point: there is one; its distance; the place sees it | 0 or 1; / 1000, at most 3 |
| 30, 31 | `when_ok`, `when` | the enemy's seconds to the point: known; the seconds | 0 or 1; / 4, at most 2 |

**Left out on purpose (decided here):** 1.7's `pro_rl`, `pro_gl`, `pro_pg` (how often the pros spammed a point with each weapon)
and `pro_hold` (how often they held a place). They are what players chose to do; the map sense is where the pros' measured outcomes
come in (rule 12). His own stack is not repeated here: the head has it among its own columns. The brain's pass odds are not written
in (1.8a has no pass odds; the trainer may add them).

## The change signals (`instr_state()`)

| Column | What | Scale |
|---|---|---|
| 0 to 2 | doing, done, failed (INSTRUCTION.md's table) | 0 or 1 |
| 3 | how long he has been on it | seconds / 10, at most 2 |
| 4 | how far his belief of the enemy's place has moved since it was given (2 when a belief came or went) | units / 1000, at most 2 |
| 5 | an item's instruction: the item is there, or back within his way to it, by what he knows | 0 or 1 |

Zeros for a seat under none.

## The drills

`DRILL_INS_P` (live, 0 to 1, default 0 = nothing changes): the chance that a game's start (a match whose clock went back: a new
round, a mid-game or pro start, in rounds of the ordinary kind) is followed by a drill for one network seat of the match.

| | |
|---|---|
| When it begins | at the first head tick at which a verb can be given to the seat; it waits 20 s at most, then there is no drill **(decided here)** |
| What is given | a verb drawn over the verbs that have a valid row (`DRILL_INS_VERBS`, live, "hold:2,spam:2,go:1"; unset: all alike), a valid row of it, and a weapon he owns with ammunition (a spam: rockets, grenades or plasma). From the drills' own random stream |
| How long | `INS_DRILL_SECS` (live, default 8) or until he dies; the row is given again at every head tick, so a place that follows the belief moves with it |
| Held by | `force_instr`: whatever the head picks in that time, the seat takes the script's |
| After | the force is lifted and he is under none until the head gives one |
| Pay | the game's alone. Nothing is paid for a state, and no pro's choice says what to do: a pro start is only where the game begins (rule 12) |
| For the trainer | `env.ins_drill` [n]: the seat's instruction is not the head's own choice and must not be learnt as one |

A drill's flags and the force are the seat's, not a moment's: a frozen-moment copy into a match does not start, move or end a drill
(the copied match's clock is copied with it, so the copy is not read as a start).

**Decided here:** a drill follows a game's start rather than being a round kind of its own. The design asks for "a situation where
the verb can pay"; with pro starts at 35% of games the start is often such a moment, and a valid candidate row is the test that
the verb can be given there. Whether that is enough is what the probes and the first drills' ledger will say.

## What a game server's plugin must call (it never calls `step()`)

Every frame, after `intend()` and the order's calls it makes today: `env._ins_step()` (the clocks and the state). At every head
tick: `env.instr_feat()`, the head's choice, `env.instr_pick(c, w)`. `env.visible`, `env.seen_t`, `env.intent_done` and the item
belief's books must be kept as the plugin keeps them for the target and the keep choice; `_ins_step` reads them. No drills on a
server (`DRILL_INS_P` unset). None of this is in the plugins yet.

## Not verified (needs the simulator, after 1.8a)

`python docs/runs/2.1/tests_instr.py` now has six cases; all are unrun.

| | |
|---|---|
| 1, 2, 4 | off and "on with nothing called" equal the simulator of `c99cc02` to the bit; the two-player module against the group module |
| 5 | `instr_feat()` at every tick with nothing picked changes nothing; shapes, ranges, invalid rows; a picked row lands; a force holds and lifts; `instr_state()` in range |
| 6 | with `DRILL_INS_P=1`: drills begin, hold a valid row for no longer than the window, and end under none |
| Not covered by a test | the time `instr_feat()` adds to a tick at full size; the candidates on each of the ten maps (a map without `sim/order_maps/<map>.npz` has only the row "none"); whether a hold's opening as chosen here is one a person would watch (pictures for the owner); how often each row is valid in real games (the test prints it for one map) |


## Second pass (owner, 2026-11-11: pieces 1, 2, 3, 4 and 6 go into the build; this opponent's habits later)

Written the same day by a second pass over `sim/duel_env.py`; **nothing of it has run in a simulator** (the generator, the input
lister and the list extension ran, and the module imported with its own asserts). Where the sections above say 32 rows, 32 numbers
or 39 inputs, the numbers below replace them; rows 0 to 31 and `INS_NONE_ROW = 30` are where they were.

### Two findings asked for

**1. The respawn rule depends on where the fragger stands: a spawn can be forced to an extent.** `_spawn(i, avoid)` puts a killed
player at a random one of the half of the map's spawn points FARTHEST (straight distance, over the median) from `avoid`, and a death
in a game calls it with the enemy's place at the moment the wait ends (`RESPAWN_QL=1`: 2.1 s after the death; 1.8a has it and
`SPAWN_QL=1`). So where he stands 2.1 s after his frag decides which half the enemy comes back in; within that half the point is
uniform. The code's own note: of the rules tried on 14,937 respawns of the pros this one fits best (86.9% inside the far half from
the enemy; Quake 3's rule, the far half from the DEATH place, 70.2%; uniform 50%). The game's exact rule is not known to be this
one; it is the best measured fit. Nothing was changed.

**2. Walking: the key works in 1.8a, and it may NOT be silent under the hearing 1.8a trains with.** The walk key is action column 7:
`walk = (a[:, 7] == 1) & (not self.no_walk)`, key strength `WALK = 64` instead of 127; 1.8a's command has no `--no-walk`, so his
hands can walk today (they do not: 0.0% of frames in the audit). Hearing under `HEAR_FIX=1` (1.8a) is by events: a footstep while
on the ground faster than `HF_STEP_SPEED = 150` units a second and not crouched; a jump; nothing for a landing here. The footstep
rule reads the SPEED, not the walk key. By the game's own arithmetic a key of 64 gives 320 x 64 / 127 = 161 units a second, which
is over 150: **if the simulator's walking speed is 161, walking makes footsteps and only crouching is silent.** The comment at
`WALK` ("silent: under the footstep speed") was written for the old rule (heard over 250). Not measured (it needs a minute of the
simulator: walk on flat ground and read the speed and `hf_ev`); nothing was changed. If it is so, the fix is one line the owner
should decide (in the game a walking player makes no footstep whatever his speed: the walk key itself silences them).

### What was built

| Name | What |
|---|---|
| `INS_VERBS` (9) | + `"check"` (`INS_CHECK = 8`): go where he can see the place the brain expects the enemy at, to find out. Doing: on his way; done: his eye has a clear line to that place, or the enemy is noticed in view; never failed by itself |
| `INS_C = 41`, `INS_F = 37` | rows 32 to 34 check (the brain's places 1, 2, 4 s ahead: the walking point nearest him by his way that has a line to it; the point: that place); rows 35 to 37 "spush" (verb push: rush a spawn point); rows 38 to 40 "sspam" (verb spam: from the nearest point by his way that sees the spawn point within 1,500 units, on that spawn point; `when`: what is left of the enemy's wait). `INS_BLOCKS`, `INS_ROW0` (`"check"`, `"spush"`, `"sspam"`), `INS_ROW_VERB` say so; `INS_BLOCK_VERB` maps the two spawn blocks to their verbs |
| The spawn rows | valid for `INS_SPAWN_SECS` (5; env var) after the enemy's death (he knows a death: the game tells every player; the mark is `RESPAWN_QL`'s wait, so without `RESPAWN_QL` there are none): the `SPAWN_K = 3` points of the far half from where he stands NOW that are nearest him by his way. The row he is on keeps its spawn point while the window lasts |
| `env.ins_cspawn` [n, INS_C] int | the spawn point (`env.spawns`' number) a row is about; -1 for every other row and for an invalid one. `env.ins_spk` [n]: the spawn point of the instruction he is under |
| `INS_FEAT` | the verb one-hot is 9 wide (every later column one further); + `spawn_row` (the row is about a spawn point) and three columns the simulator leaves at ZERO for the trainer to fill from the brain: `unsure`, `known`, `spawn_odds`. `INS_FILL = {"unsure": 34, "known": 35, "spawn_odds": 36}` |
| `SPAWN_MAX = 32`, `env.spawns` [S, 3] | a padding size for the brain's answer over spawn points; the map's spawn points (the twelve maps have 6 to 14) |
| `KNOWN_TRUTH=1` | `info["aux"]` columns `en_knows` (the enemy has him noticed in view, or the enemy's picture of him is at most `KNOWN_T` = 3 s old and within `KNOWN_R` = 300 units of where he is: the enemy's last known place of him or the place the enemy's readers believe him at) and `en_heard` (the enemy heard him, not seen, within the last second). The present truth, a label only |
| `SPAWN_TRUTH=1` | `en_spawn` (on the frame the enemy is back after a death: the spawn point's number; else -1; needs `RESPAWN_QL`) and `en_dead_t` (seconds since the enemy last died, at most 99) |
| quiet | `instr_in(..., who=None, quiet=None)`, `instr_pick(c, w, who=None, q=None)` (`q` [n] 0 or 1; none: 0), kept in `env.ins_q` [n]; `env.force_quiet` [n] int (-1: not forced; read inside `instr_pick`; not part of a moment). Asking quiet or not is the same instruction (its clock goes on). One more input of the hands, the last of `b21 instruction`: "quiet asked". `N_INS = 41`; the full list 1,094; list 21: 845 columns, the hands the first 837 |
| the drills | `DRILL_INS_QUIET` (0..1, default 0.25; live like the other three): a drill of go, hold, cut off or check asks quiet with that chance (through `force_quiet`, lifted with the drill). `DRILL_INS_VERBS` accepts `check` |
| `env.ins_noise` [n] | seconds since he last made a footstep or a jump (`HEAR_FIX`'s events), for the readouts; `env.ins_dead_t`, `env.ins_heard_t` the clocks the rows and labels read (`_ins_clock()`, every frame when `INSTR`, `KNOWN_TRUTH` or `SPAWN_TRUTH` is on) |
| `env.last_spawn` [n] | the spawn point he last started from |

**Decided here:**
- The check's place is simply the nearest point by his way with a line to the expected place; "not exposed from more than one side"
  is not read (it is what the map sense is for).
- "Most likely by what a player can know" = the far half from where he stands now, all alike; of those, the three nearest by his
  way (the ones he can act on). The brain's learned odds go into `spawn_odds` by the trainer.
- A death of the enemy by his own hand or the lava opens the spawn rows too (the game announces every death).
- One switch for the two "knows" labels, another for the two spawn labels.
- `en_heard` is read from the last frame's senses (he was placed by a sound and not seen): a frame late.
- A hold's or check's quiet is asked by the drill's script with a chance; nothing in the simulator rewards or enforces it.
- `force_quiet` does not by itself put a seat under a force: it only sets the field of a seat being given an instruction.

**A plugin must also call** `env._ins_clock()` every frame before `env._ins_step()` (the spawn rows' and the labels' clocks), and
pass the head's quiet choice as `instr_pick(c, w, who, q)`.

**Not verified:** case 7 of `tests_instr.py` (the labels on = the game to the bit; `en_knows` only with the enemy's sight or a fresh
picture within reach; `en_spawn` where he stands; check rows only with a belief; spawn rows only in their seconds and about a real
spawn point; quiet kept, forced, carried by a moment and the force not), and cases 1 to 6 again on the grown list. Not covered by
any test: the walking speed and whether it is heard (finding 2); whether the far half as he stands now is the half at the wait's
end often enough to be worth acting on; the time the check rows add (a [seats, walking points] pass a tick). A force (a drill's,
a frozen moment's, `force_quiet`) is never released by a timer other than the drill's own: the giver lifts it.

## Third pass (owner, 2026-11-11 night: the lightning gun "is for cleanup"; the finish time, the wake, the pattern's moments)

The owner's pattern: "land a disruption rocket or perhaps multiple; oh the enemy is weak (i heard them scream e.g.); let me switch
to lg and finish them off". What the simulator now gives for it; all of it from his senses and his belief, never the truth.

### What was built

| Part | Where | What |
|---|---|---|
| The table `FIN_RATE` | `sim/duel_env.py` (top, after the weapon table) | 9 weapons x 3 distance bands (under 400, 400 to 768, over 768 units): **his own** damage a second of trigger held, misses and splash in it. An environment string (27 numbers), a play variable (the checkpoint's and the export's `env_vars` carry it) and a live name. `FIN_RATE_DEFAULT` is a **placeholder by design, not measured**; `tools/run/fin_rate.py measure` makes the real one from his recorded games |
| His belief of the enemy's stack | `_fin_belief()` | a life on the brain with an answer: the brain's stack band odds times the bands' middles (37.5, 100, 162.5, 250) and the spread of those odds; any other seat: the stack belief of `EN_STACK` (what he dealt, heard and saw) and its spread; neither: no belief. The distance: to the enemy in his view, else to where he believes him, else the middle band |
| The finish time | `_fin()` | per weapon: seconds to finish him = the believed stack / his rate in that band; the cautious one = the believed stack plus its spread; seconds of fire he has = ammunition x refire time. As inputs: a finish time / 5, at most 2 (2 too: a weapon he cannot use, a rate of 0, no belief); seconds of fire / 10, at most 2 (the gauntlet: 2) |
| For the head and the appraisals | `INS_FEAT`'s last 27 (`INS_FIN0` = 37; `INS_F` = 64) | the three numbers of every weapon in every valid candidate row (the same in a seat's rows): the rows' scorer, the weapon's scorer and the appraisals read them |
| For the hands | the group `b21 instruction`'s last 7 (`N_FIN`; `N_INS` = 48) | the weapon asked for (3; zeros under no instruction or none asked); the weapon in his hand (3) and "he has a belief of the stack" (1): **live for every living seat with `INSTR` on, under an instruction or not** (what lets the hands learn to let go of the trigger) |
| The wake | `_ins_clock()`, `instr_state()` (now 8 numbers, `INS_SIG`) | a pain sound of the enemy heard (not twice within 0.5 s: the game's own limit), or his believed stack fallen by `INS_WAKE_DROP` (25: one band of the pain sound's four) since the last wake or since the instruction was given: for the 8 frames after it `instr_state()`'s seventh number is 1, so exactly one reading of the head sees it. Its eighth number: how far the believed stack has fallen since the instruction was given (/ 100, at most 2) |
| The pattern's moments | `instr_pattern()` -> 0, 1, 2 | 1: within 1 s of a chunk hit of his on the living enemy (40 points or more in one frame, booked by `note_dealt`: needs `EN_STACK=1`) or of a pain sound heard, the enemy alive and within 1,500 units by his belief or in view; 2: a fight's start with both stacks high (the enemy in view for under 1 s after 2 s or more out of it, his own stack and his believed stack of the enemy both 150 or more) |
| The head's pay label | `HEAD_PAY_TRUTH=1` -> the aux column `win_raw` | this frame's change in his chance of winning as the win judge reads it (the win part at a gain of 1, a game's end in it). A label: never an input, never paid, the game unchanged. No entry of the pay table is in it |

Sizes: the full list **1,101** columns (1,053 + 48); list 21 **852** (the brain the first 691, the hands the first 844, the tail 8).

### Decided here, for the owner's review

- **The brain's stack answer is four bands**, so a finish time from it moves in coarse steps (a believed stack of about 40, 100, 160
  or 250, blended by the odds). It is the brain's belief as the design asks. The measured alternative: a finer stack readout of the
  brain (a number and a spread), filled into the rows by the trainer as "known" and "unsure" are.
- **A rate of 0 means "never"** (the lightning gun past its reach of 768 units, a cell he never fired in): the finish time reads 2.
- **The wake's drop is 25** (one pain band), counted from the most he has believed since the last wake. Under his own lightning
  gun that is a wake about every half second of hits: in a fight the head re-decides often, as a seat under no instruction does
  at every tick.
- **A wake ends a keep as "done" and "failed" do** (the head draws anew at that reading and may draw the same again): the owner
  approved "he is made to look". The keep choice also reads the wake through the head's inputs.
- **A chunk hit is 40 points in one frame** (a rocket, a rail, a grenade, a close shotgun; never the lightning gun's 6 or the
  machine gun's 5). **"High" is 150** (above a fresh spawn's 125).
- **In the measuring tool the damage is booked in the band of the distance when it lands**, the trigger time in the band at the
  shot (a rocket's flight is under a second).
- **The gauntlet's rate cannot be measured** by ammunition; it keeps the placeholder.

### Tested (2026-11-11 night, CPU, cores 14 to 17, below-normal priority; 1.8a training throughout)

`docs/runs/2.1/tests_instr.py --map bloodrun --frames 2000`, the maps read from a scratch copy: see TRAINER_PARTS.md, "The fifth
build", for the results. Two things the earlier cases needed and did not have, fixed: the simulator is now made with the walking
map (`nav=`: without it there is no way and no candidate row but "none"), and `--cmd <train.cmd>` plays every case under a run's
own simulator settings (the default settings give him no belief of the enemy's place, so check, push and cut rows never open).
`tools/ffa_check.py` plays on the test map and there is **no `testlab.bsp`** in the repo's `data/maps`: case 4b compares the
two-player module and the generated group module on Blood Run instead.

### A plugin must also

set nothing new: the finish time and the wake are made by `observe()`, `_ins_clock()` and `instr_state()`, which it already calls;
`note_dealt()` (it calls it for every hit) books the chunk hits. The table reaches it in the export's `env_vars` (`FIN_RATE`).

## Fourth pass (2026-11-12, for 2.1a: [2.1a/CARD.md](2.1a/CARD.md))

| Part | Where | State |
|---|---|---|
| **The binding weapon** (`INS_BIND=1`, a play variable; the owner: "I think that makes sense"). While a seat is under an instruction that names a weapon he owns with ammunition (the gauntlet: owned), the weapon key's action is that weapon's, set after his own draw and before the finger limits (the hand reads it at its own rate; the game's switch time stays). `ins_bind_act()` is the one definition; `env.instr_bind()`; `env.ins_bind_a` the action set this frame (-1: his own stood); `stats["ins_bind"]` = his hand's readings alive, of them bound, of them not his own pick, weapon changes | `sim/duel_env.py` (regenerated `duel_env_ffa.py`) | `tests_instr.py` case 9: on with nothing given = off to the bit; the action set is the definition's; a seat bound for 2 s holds the weapon (10,595 seat-frames bound, the asked weapon in hand on 93%) |
| **No switch cost on a change of target the instruction made** (it is the head's decision; the hands are not charged for it). With no instruction: as before | `sim/duel_env.py` (`intent_ins`, `sw_chg`) | case 2 of the suite (on with nothing given = off) |
| **`INTENT_SWITCH` and `WEAPON_OWN` are live names** (read only in `intend()` and in the pay): range 0 to 0.1; 0 or 1 | `LIVE_VARS`, `live_values` | unit checks; `2.1a/tests.py live`, `ramp_test.py` |
| `live_now()` gives a table (`FIN_RATE`) as a list: two simulators' answers compare. **A fault of the third pass found by the first real trainer start**: the trainer's "the simulators disagree" check raised on the array | `sim/duel_env.py` | `2.1a/tests.py old` |
| The tools read the data under `QLBOT_ROOT` when it is set (a worktree has none): the trainer, the checks' player, the recorder, the probes, the export | 38 places, `os.environ.get("QLBOT_ROOT") or ROOT` | unset: as before |

**Decided here:** the binding goes through the finger limits (a weapon key press ten times a second at most, as his own); it binds for as
long as the instruction stands; a weapon he does not own, or has no ammunition for, never binds (his own choice stands, as with "none").

# 2.2c: the build's record

Written by the build (an Opus 5.5 worker, 2026-11-18) for the planning session. The card is [CARD.md](CARD.md) (the specification); this
file is what was built, how it was tested, and where the build decided what the card left open. Branch `b22c` (from `main` at `76a6a66`),
not merged, not pushed. The run has not started: the planning session starts it with `start.ps1` after reading this.

## Read first

1. **The item's pay that the contest pay moves is never more than what the pickup paid the picker.** The card and the brief give the
   item pays as the command's `ITEM_FLAT` (mega 0.35, red 0.30, yellow 0.15). The simulator has not paid those flats for health and
   armor since b1.2d: they are paid by the point (`ITEM_PT_LO` 0.004 a point up to 100, `ITEM_PT_HI` 0.002 above, the decay charged
   back), so a mega taken at 150 health pays 0.10, a red armor from 0 pays 0.40. Built: the contest's base is the smaller of the flat
   (0.10 for a weapon) and what this pickup paid him (the by-the-second pay: what it would pay the enemy now). That keeps the owner's
   "he still needs to get positive reward for picking up the item. Always" and the 20% floor; the card's 80% is then 80% of that. **A
   real fork for the planning session**: taking the flat as the base whatever the pickup paid would let a pickup at a high stack pay
   the picker less than nothing.
2. **At the start most of the enemy's big pickups are free**: on the start's games (the start playing itself, ten maps, 1.2 million seat
   frames) 465 of 1,789 (26%) were under any pressure, the mean pressure 0.059; 1,324 were free, his mean distance from the item then
   1,085 units (603 under 1,000, 661 from 1,000 to 2,000, 60 over 2,000). So from update 0 the free-pickup charge is paid on three
   pickups in four: small (a mega's 0.035), but steady. And **376 steals** against his own 1,789 big pickups: the steal's mark counts
   any damage to the enemy in the window (rung 3), so a fight near an item the enemy was heading for marks it; each steal pays 80% of
   the flat. Reported every update; the card's sizes, not changed.
3. **The rail chain starts from almost nothing**: of 720 fresh sightings beyond 768 units on the start's games, he had the rail in his
   hand at 4. The long-line pay was 0.007% of his pay's size, the far-rail pay 0.004%, the rail's pickup pay 0.26%.
4. **The contest pay at the start is 1.9% of his pay's size** (the pickup's 1.72%, by the second 0.19%), beside the item pays (red
   3.7%, yellow 2.3%, mega 2.0%) and the win part (59.7%). The card's red team foresaw it ("too small again"). Measured, not changed.
5. The trial's numbers, the minutes an update and the first update's arrival: "The full-size trials" below.

## What was built, by the card's sections

| # | Part | Where | As built |
|---|---|---|---|
| A | The contest pay | `sim/duel_env.py` `CONTEST=1` (`_cb_init`, `_cb_begin`, `_cb_burst`, `_cb_ways`, `_cb_frame`, `_cb_press`, `_cb_pick`); terms `contest`, `contest_sec` | At an enemy's pickup of a contested item (the map's route goals of MH, RA, YA, YA2, RL, RG, LG), the other player's pressure from his rings of the last 4 s (rung 1: the last second; rung 2: his bursts; rung 3: damage dealt; less damage taken), the transfer `base x (CONTEST_W x p - CEDE_W x (1 - p))`, the steal, the pay by the second, the cap per spawn and the picker's floor. Live `CONTEST_W` (0.8, 0 .. 1), `CEDE_W` (0.1, 0 .. 0.5) |
| B | The rail chain | `sim/duel_env.py` `RAIL_CHAIN=1` (`_rc_pick`, `_rc_line`); terms `rail_pick`, `rail_line` | The rail taken while he holds none: `RAIL_PICK_PAY` (0.15), once a life, zero-sum. The long line: at the pre-aim pay's fresh sighting beyond 768 units, `RAIL_LINE_PAY` (0.10) x (his pre-aim grade with the rail in hand, else 0, less the enemy's the same), zero-sum; `PREAIM_PAY` beside it unchanged. `RAIL_FAR_PAY` 0.1 -> 0.5, band 500 to 800 as 2.2b's. Each live with a range |
| C | The aggression lever | `sim/fightnet.py` (`VERSION_LEVER`: `layout_lever`, `raw_lever`, `LeverNet`, `np_forward_lever`, `lever_add`, `lever_vec`, `NpFight.reading_lever`); `sim/train_duel_rnn.py --lever 1 --lev-g --lev-from`; `tools/lever22_init.py` | One number x live `LEV_G` (0 .. 1), rounded to half precision, added to the item picker's score of "the enemy" after the pull, before the draw; held from his keep readings (five a second); its two forecasts as 2.2b's. Out of play: the four options and their bias, the weapon nudge, practice and its weapon push, the shut mask (`--lever` refuses `--fgt-g`, `--fgt-w`, `--practice-p` above 0; live `FGT_G`, `FGT_W`, `PRACTICE_P`, `FGT_BIAS` are ignored with a line). Its inputs: brain 256, the tracker 18, the item picker's obs columns 69, the item picker's target log-probabilities 17, the head 256, the hands 512, where he is headed 18 (his target, the seconds on it) = 1,146 (2.2b's 1,230 less the options' 80 numbers and the fight option he is on). PPO on every target decision of his (a new draw or a change mid-trip), its own pay (the fight group: damage dealt less taken, frags, deaths; the win part x `--win-scale-fight`), its own Adam (1e-4); decay `H2_L2` on its first and last layers from update 0; its size every update (mean and largest |lever|), flagged over 40. The hands shown it through 2.2b's token (the first of the four score columns: what the lever adds; the other three 0). The checks' player plays it as the trainer (`sim/test_suite.py`: proven, below); `tools/duel_eval.py`, `tools/run/ws_eval.py`, `tools/run/dump_eval.py` and `tools/run/panel.py` know it |
| D | Kept from 2.2b | below, "The nine kept" | |
| E | The inputs | `sim/duel_env.py` `AHEAD_IN=1` (`_ahi`, group "b22c ahead", 13 columns); list 22c (`tools/inputs22c.py list`, `sim/input_list_22c.json`, `docs/INPUTS_22c.csv`, `sim/duel_env_ffa22c.py`); `tools/inputs22c.py convert`, `stats` | Below, "The inputs" |
| F | Logging from update 1 | the trainer's `fight` block (`fg_record_lever`); the simulator's counters `stats["contest"]` (24 numbers), `stats["contest_burst"]` (by weapon, in and out of view, near an item up, coming in 4 s, taken in the last 4 s), `stats["rail_chain"]`; `ramp_22c.py` writes it all into `watch/watch.log` in plain lines every update | Below, "Reported every update" |
| G | The run's files | `train.cmd` (`make_files.py`), `start.ps1`, `start_live.py`, `start_values.py`, `accept_22c.py`, `ramp_22c.py`, `alarms_22c.py`, `league_22c.py`, `play22c.py`, `win_scale.py`, `win_scale_22c.json`, `MONITOR.md`, `tests.py`, `ident_sim.py`, `ffa_check22c.py`, `check_lever.py`, `check_eval.py`, `smoke.py` | Checks at updates 10, 30, 50, 70, 90 (the watcher: the first at 10, then every 20), 200 games against the start (2.2a's update 90), every fourth against 2.1d's end, as 2.2b's |

## The contest pay as built (the numbers)

| | |
|---|---|
| Contested items | The route goals of the map labelled MH, RA, YA, YA2, RL, RG, LG (a map's other copies of a weapon too). Blood Run: MH, RA, RL, RG, LG, YA, YA2 |
| The item's pay (the base) | `min(flat, what this pickup paid him)`; flat = `ITEM_FLAT` (MH 0.35, RA 0.30, YA 0.15; YA2 as YA), 0.10 for a weapon (`CONTEST_WPN`, the first of `BIG_PICK_SEQ`). By the second: `min(flat, what the item would pay the enemy now)` (the same table by the point) |
| Rung 1 (up to 0.25) | 0.25 x the largest, over the last second (40 frames), of: the enemy in his view (the simulator's own sight) or the item on a clear line from his eye (a trace to the item's place + 16 units up), x his crosshair's grade (1 dead on, 0 at 60 degrees, the pre-aim pay's), x a weapon in hand that reaches that far (the lightning gun 768, the shotgun 1,500 (MECHANICS: the game's range), the machine guns and the rail 8,192, rockets, grenades and plasma always, the gauntlet never). The item's trace is made only while the item is up and the enemy within 6 s of way of it |
| Rung 2 (up to 0.5) | Each of his bursts in the window that dealt the enemy no damage: 0.25 x f x min(1, its splash / a rocket's) (a rocket or a grenade 0.25 x f, a plasma ball 0.045 x f), f the near-miss rule's grade (1 inside its splash radius, straight to 0 at `NEAR_OUT` 300) of the burst against the item's place or the enemy's box at the burst, the larger; summed, at most 0.5. Two near rockets fill it; so do about fourteen near plasma balls |
| Rung 3 (up to 0.5) | Damage he dealt the enemy in the window, 100 points = 0.5 |
| Taken off | Damage he took from the enemy in the window, 100 points = 0.5; p never below 0 |
| The transfer | `base x (CONTEST_W x p - CEDE_W x (1 - p))` from the picker to him (negative: from him to the picker). No pressure: he pays 10%. Full: he is paid 80% |
| The steal | A mark when the enemy's target (his intention) is the item, under 4 s of way, the item up, and he has a rung 2 or rung 3 event in the window; within 10 s of the last mark he picks it up: `CONTEST_W x flat` from the enemy to him, inside the spawn's cap; the mark consumed |
| By the second (MH, RA, YA) | The item up; the enemy nearer than he and under 6 s of way: each frame `CONTEST_W / 5 x base x pressure x 0.025 s` from the enemy to him, pressure `min(1, 2 x rung 2 now + 0.25 x his crosshair on the item now with a weapon that reaches)` |
| One cap a spawn | At most `0.8 x flat` moves to the others in all (by the second, the pickup, the steal); the picker is never charged more than `0.8 x` what his pickup paid him (by the second and at the pickup together). The free-pickup charge is a move to the picker and has no cap |
| Seconds of way | The route's table (`R.T`, the seconds the item seek and the routes' inputs read) at his node + his distance to it at 320 a second, every frame (no measurable cost: 12.3 s against 13.7 s for an 800-frame replay with everything on) |
| Where | Games and normal rounds of two policy seats; no runs, no rooms, no test map, no scripted seat |
| Pay a frame | Into the frame's pay and `r_long` (the items' part, as the item pays), zero-sum; booked as its own terms |

**What one full contest pay is worth** (the card's "not verified"): a mega taken under full pressure moves 0.28 when the mega paid the
picker at least 0.35; a direct rocket (100 points) pays its shooter 0.50 for the damage dealt (`DMG_REWARD` 0.005), so a full contest of
a mega is 0.56 of a direct rocket hit; a red armor's 0.24 is 0.48; a yellow's 0.12 is 0.24; a weapon's 0.08 is 0.16. The free-pickup
charge on a mega (0.035) is 7% of a direct rocket hit.

**What one far rail hit pays at 0.5**: the far-rail pay rises from 0 at 500 units to 0.5 at 800 and beyond, on top of the rail's 80
points of damage (0.40): a hit beyond 800 pays the shooter 0.90, nine tenths of a frag (a frag is 1.0), half a frag of it the far-rail
pay alone; the victim is charged 0.5 + 0.36 (the damage taken at `DMG_TAKEN_W` 0.9).

## The nine kept from 2.2b (the brief's D)

| # | Kept | Where | Value |
|---|---|---|---|
| 1 | The pay split by network | `sim/fight22.py`, `FIGHT_SPLIT=22c` (the command) | The item picker: the item terms, `contest`, `contest_sec`, `rail_pick`, `rail_line`, `rail` (the far rail), with the win part. The fight network (the lever): `dmg_dealt`, `dmg_taken`, `frag`, `death`, `deaths_other`, `high` (0), with the win part. The hands: every term (as ever) |
| 2 | Frags and deaths to the fight network only | the same | not in the item picker's group |
| 3 | The judge with the items, refitted on the start's games and accepted | `JUDGE_PAY=1`, `JUDGE_ITEMS=docs\runs\2.2\2.2b\items_22b.json` | 2.2b's refit: 100 games of 2.2a's update 90 against itself, the same start; accepted. The judge's guard passes the command |
| 4 | The win-chance pay at least each network's flat pay | `--win-scale-items 1 --win-scale-fight 1` (`win_scale_22c.json`) | Measured on the start's games with 2.2c's pay: the item picker's flat part is 0.215 of the win part's size, the fight network's 0.395: both scales 1. The trainer reports the ratio every update and the ramp flags it under 1 |
| 5 | The near-miss pay as built, 2.2b's size, from update 0 | `NEAR_MISS=1`, `NEAR_PAY=5` (command and live), `NEAR_OUT` 300 | to the hands only (2.2c's split) |
| 6 | The weapon choice the hands' own | `--head2-wpg 0`, live `H2_WPG` 0 (never written); `H2_WADD` written 1 -> 0 over clocks 0 to 7 (`ramp_22c.py`) | 0 plays by update 10 |
| 7 | The item picker frozen but for its forecast's last layer through update 10, proven every update | `--h2-freeze 1 --h2-choice-warm 10 --h2-wsc-freeze 1` | The proof's line every update (`alarms_22c.py`), MAJOR if a held weight moved |
| 8 | Firing costs nothing | `COST_FIRE_W=0`, `BLIND_FIRE_W=0`, `SHOT_COST=0`, `BLIND_RL_DMG=0` | `start.ps1` and `make_files.py` refuse otherwise |
| 9 | The gauntlet alarm; the weapon-choice-speed alarm FIXED | `alarms_22c.py` | The gauntlet in hand (`v14.in_hand.g`) over 5%: MAJOR. The speed: 2.2b read `weapon.kl`, the item picker's credit term on the weapon key, which `H2_WPG` 0 switches off (0 all night). Now `kl_heads[6]`, the hands' own weapon key's KL, over three times its normal: 0.0126 (its median over 2.2a's 156 updates 0.0042; over 2.2b's 99 updates 0.0033, its largest 0.0047). On 2.2b's metrics: it reads 0.0005 at update 1 to 0.0047, never over |

## The inputs (the brief's E)

What the hands read today, checked by name in list 22b:

| Item | His belief of when it is up | Read by the hands' first layer |
|---|---|---|
| Mega, red armor | "memory: known to be taken", "how long ago" (columns 272 to 275) | yes (brain and hands) |
| Rocket launcher, rail, lightning gun | "items: nearest ...: seen up / seen gone", "v02 items: since he took ..." (522 to 526) | yes (brain and hands) |
| **The yellow armors** | "b17b timers: (second) yellow armor: known to be taken / how long ago" | **no: in list 22b's tail, read by no first layer; the item picker's columns do not include them either** |
| **Where the brain expects the enemy in 1, 2, 4 s** | the brain's readout ahead (`net.ahead`) | **no: the brain's token carries its place now (and zones, speed, direction), not the places ahead; they were sent to the simulator only for the old combat order** |

Added (list 22c: 22b with 17 more columns in the hands' part, read by their encoder only, no new attention token; the brain's 691
unchanged): the yellows' four timers moved from the tail into the hands' part (their statistics carried: they were measured with the
list), and the group "b22c ahead" (`AHEAD_IN=1`): for 1, 2 and 4 s, where the brain's readout ahead puts the enemy from his eye now
(forward, left, up in his yaw, distance; thousands of units) and that there is an answer, 13 columns. The trainer sends the places with
the brain's answer (`AHEAD_IN` turns `BA_SEND` on); the checks' player and tools do the same. Each column at zero weight; the ahead
columns' mean and spread measured on the start's play (`play22c.py sample`: the start playing itself on the ten maps, 1,500 frames x 32
seats a map, every fourth frame's living seats; numbers in `start_dryrun.log`). **The list's length: 844 inputs (the brain the first
691, the hands' encoder the first 840, a tail of 4: the guessing lesson's marks).** `AHEAD_IN` is a play switch (saved with the network;
`tools/run/panel.py` sets it for a check of such a save).

## Reported every update (the card's list, the brief's F)

The trainer's `fight` block and the ramp's lines in `watch/watch.log`: the enemy's big pickups (MH, RA, YA) and the share under
pressure with the mean pressure and each rung's mean; the enemy's weapon pickups under pressure; steals; free pickups and his distance
from the item at each (mean and three bins); the pay to and from him at pickups and by the second, the frames paid by the second, how
often the cap bit; his own big pickups a seat-minute; his rockets, grenades and plasma bursting within 300 units of an item that is up,
coming in 4 s or taken in the last 4 s, in view and out of view, by weapon; bursts near an item nobody then took within 8 s; bursts 4 to 8 s
before the enemy took it (paid nothing); the rail in hand, rail shots and far hits (500 units and more) a seat-minute, the far-rail pay
got and lost, the rail's pickup pays, fresh sightings beyond 768 and those with the rail in hand, the long line's pay; every new pay term's
sum, size and share of his pay's size (beside the near miss, the win part, damage, the item pays); the lever's share as played, its size
(mean and largest |lever|) and its average and how often he is headed for the enemy when he is ahead (his effective stack more than 25
over the enemy's true one), level (within 25), behind (under -25), and in the 5 s after his frag; frags and damage a seat-minute; the
projectiles a seat-minute in and out of view; the lever's lesson (decisions, its share as played, advantage on the enemy and on an item,
forecast errors, the clipped share, its KL, sizes, decay, the win scale); the two alarms and the freeze's proof.

## Tests

Every test below was run in the build; none is claimed that was not. The official runs under the Anaconda Python the trainer uses.

| Test | What | Result |
|---|---|---|
| The simulator off = bit-identical (`ident_sim.py`) | Fixed-seed replays of the tree before the build against the new, 2.2b's settings, every new switch off, the same random actions | **IDENTICAL** (inputs by name, pay, round ends, targets, stacks, places): Blood Run 800 frames and 1,200 frames, Hektik 1,200 frames, 16 seats each; the 1,128 old columns equal, the 13 new ones 0 |
| The generated module (`ffa_check22c.py`; `tools/make_ffa_env.py` regenerated after every edit) | `duel_env_ffa` against `duel_env` at two players WITH 2.2c's switches on, Blood Run with its ways, 1,500 frames x 48 seats | **IDENTICAL**: inputs, pay, round ends, the pay by term, the contest counters (19 enemy big pickups, 7 under pressure, 6 steals, 6,827 frames paid by the second) |
| The pays on constructed cases (`tests.py unit`, the simulator's own code) | free pickup; full, partial and rung-1 pressure; damage taken off; the cap per spawn; the picker's 20% floor with the by-the-second charge before it; the steal and its 10 s; by the second at 5.9 s and 6.1 s, when he is the nearer, its cap and its floor; the rail's pickup once a life; the long line (rail in hand beyond 768, within 768, no rail, both with the rail); zero-sum to the last digit in each | **33 of 33 PASS**: free pickup +0.035 / -0.035; full pressure 0.28 (the picker keeps 0.07 = 20%); pressure 0.25: 0.04375; taken off: back to the free charge; the cap: 0.03 more; the floor: 0.03 more (0.08 = 80% of a 0.10 pickup); the steal +0.315 (0.28 and the free charge), none after 10.025 s; by the second 0.0004 a frame at 5.9 s, 0 at 6.1 s, 0 when nearer, capped, floored; the rail 0.15 / 0 / 0.15 after a new life; the long line 0.08, 0, 0, 0.03; every sum exactly 0 |
| A whole run with every switch on (`tests.py unit`) | 8 matches x 3,000 frames, random actions | The four new terms zero-sum in every match of every frame (largest sum exactly 0); paid (contest 0.70, by the second 0.43, the rail's pickup 2.4); the pay split's parts (2.2c's groups) sum to the frame's pay (largest difference 1.2e-7) |
| The lever, numpy against torch (`tests.py unit`) | 64 rows, a last layer made non-zero; its add's half rounding; its vector; its inputs' names | Largest difference 2.0e-7; the add equal to the bit; only "the enemy"; no option's numbers |
| The checks play the lever as the trainer (`check_lever.py`) | A save whose lever learnt (the CPU smoke's, |lever| up to 0.0076, share 1), Blood Run 600 frames x 16 seats through the checks' player | (a) 1,184 readings: the Policy's lever against the trainer's torch network on the same inputs, largest difference 2.8e-9; (b) replayed at share 1 and 0: the target logits as drawn differ only in "the enemy", by exactly the add (difference 0); (c) the hands' inputs equal the add (0). **ALL PASSED** |
| The check tool (`check_eval.py`: `tools/duel_eval.py` as the watcher runs it) | 2 games on Blood Run against 2.2a's update 90: the smoke's lever save; 2.2b's last save (the four options) | Both ran to the end (0-2 and 0-2: two short games, not a measure); older checkpoints keep working |
| `tests.py live` | Every new live name refused out of its range and accepted at its ends, by the trainer's own reader | **25 of 25 PASS** (`LEV_G` 0..1, `CONTEST_W` 0..1, `CEDE_W` 0..0.5, `RAIL_PICK_PAY`, `RAIL_LINE_PAY`, `RAIL_FAR_PAY` 0..1) |
| `accept_22c.py` (`tools/run/live_accept.py`) | The start's live file and the ramp's every clock; each new live name at both ends of its range | **ALL ACCEPTED** (13 files) |
| `start_values.py` | The command's start values against the start's live file, name by name | **PASS**, 55 names |
| `check_settings` | Against 2.2b's command; against 2.2a's update 90 | 17 differences, every one deliberate ("Every difference"): **PASS** with `start.ps1`'s allow list; against the start file `DESC_OX` and `RAIL_FAR_PAY`, allowed |
| The start answers as 2.2a's update 90 (`play22c.py ident`, inside `start.ps1 -DryRun`) | 2.2a's update 90 plays Blood Run and Toxicity (1,200 frames x 32 seats), its places ahead sent so the new columns are real; both networks replay; the new one also at the lever's share 1 | **0 of 1,075,200 actions differ, at share 0 and at share 1; 0 keep columns**; the largest logit difference 0.000136, memory 8.4e-5; the new columns real in the recording (largest 1.93). The ahead columns' statistics from 117,774 rows (none constant; "there is an answer" 0.99). The whole dry run (`start.ps1 -Minutes 1440 -Updates 100 -DryRun`, into `data/sim_runs/scratch_22c_dryrun`): **passed** (both settings checks, start values 55 names, live accept, the start's pipeline, ident, the league: 9 anchors, the control, 8 snapshots, all list 22c) |
| The CPU smoke (`smoke.py`, 2 simulators x 8 matches, 5 updates, the stages five times faster, `--lev-from 2`, 2.2a's update-100 optimizer carried, then a resume for one update) | The whole trainer path with the lever | **PASSED**: the lever played at share 0 on updates 1 and 2, 1 from update 3; its size grew from 0 (0.0027, 0.0039, 0.0038 mean, largest 0.0063); a snapshot with its own lever joined the league (update 5) and the resume reloaded it; the freeze's proof `held_max` 0 every update; the pull's proof 1e-5; the contest counters, the rail, the pay terms in every block; no non-finite number, no flag but "frags under 1.5" (tiny sample) |
| `python tools/docs_check.py` | | 3 problems, all from before this build (three links to `docs/runs/2.1/2.1a/TESTS.md`, not in `main`); none in the files touched |

## The full-size trials

At the run's own size (30 simulators x 168 matches, 360 pieces, the graphics card; `smoke.py` with `SMOKE_FULL=1`), from the dry run's
start file with 2.2a's update-100 optimizer carried, the league of two converted anchors and the control, the start's live file. For the
technical side only: nothing about behaviour is read from them and nothing was tuned on them.

| Trial | What | Update 1 | Update 2 |
|---|---|---|---|
| 1 (`scratch_22c_smoke_full1`) | Two updates from the run's clock 0 | KL 0.0033, clip 0.026; the target's KL 0.00004, the hands' weapon key's 0.0004; the lever played at 0, its size 0; the freeze's proof `held_max` 0 (on); the pull's proof 0.00044; 100,748 decisions in the lever's lesson | KL 0.0040, clip 0.036; target 0.00007, weapon key 0.0005; the same: lever 0, freeze held exactly, the pull's proof 0.00048 |
| 2 (`scratch_22c_smoke_full_clock9`) | Two updates from the run's clock 9 (`SMOKE_CLOCK=9`: the trainer counts 9 updates done, as on a resume), live at clock 9's dials (`H2_WADD` 0, the gate -26.7): **past the switch at update 10** | Run update 10: KL 0.0034; freeze ON, `held_max` 0; the lever played at 0 | Run update 11: **the freeze off (the item picker learns: the target's KL 0.00021), the lever played at share 1 and learnt** (its mean -0.046, largest 0.33, the clipped share 0.0003); the pull's proof 0.0023 (under the 0.003 flag bar); KL 0.0044, clip 0.041 |

In both: every pay term paid and in the ledger (the contest pay 1.6 to 2.0% of his pay's size, by the second 0.2 to 0.3%, the rail's pickup
0.1 to 0.4%, the near miss 0.2 to 0.5%, the win part 60 to 73%); the win part 2.7 to 7.1 times each network's flat pay (no flag); no non-
finite number; no MAJOR line in the ramp's replay of trial 1's metrics (`ramp_22c.py --once`: every line written, the lever, contest, shells,
rail and pay-term lines read as intended; the only FLAG the generic "frags a match-minute under 1.5"). The gauntlet in hand 0.5 to 1.1%.

**Time**: each trial's start to its second update's line 13.2 to 13.3 minutes (the trainer's start-up and two updates); the rollout 208 to 232 s,
the learning 214 to 357 s (they overlap; as 2.2b's: about 6 minutes an update in steady state, the first update's learning the longer).
The first update's own time was not stamped; from the second's line and the update's parts it came about 8 to 9 minutes after
the start-up (the start-up's league loading included: over the six-minute rule of thumb, which is about an update's own time; the card
was not full). The card's memory at most **14.4 GB of 16** (a sample every 20 s over
trial 1), the PC's free memory at least 13.6 GB, commit at most 77 GB.

## Decided in the build (the card left it open; decided from its intent)

| Detail | Decided | Why |
|---|---|---|
| The item's pay the contest pay moves | `min(flat, what the pickup paid the picker)` (by the second: what it would pay the enemy now); flat 0.10 for a weapon | "A pickup always pays" and "the picker keeps 20%": health and armor are paid by the point, the flats are only a ceiling (Read first, 1) |
| The cap and the share | The cap 0.8 of the flat a spawn and the picker's 20% floor are fixed (`CB_CAP`); `CONTEST_W` is the share full pressure moves (the card's "never above 1"): above 0.8 the cap binds first | The card's cap is the owner's ("Cap it at 80%"); the dial sets how fast pressure bites |
| Rung 2 per shell | 0.25 x f x min(1, splash / a rocket's): a rocket or grenade near enough fills half the rung, two fill it; a plasma ball 0.045 x f | The card gives the rung's ceiling only; two good shells in 4 s is the notes' "grenades 2 to 3 s before mega"; plasma's small splash counts small |
| A burst that hurt the enemy | Counts in rung 3 (its damage) only, not rung 2 | As the near-miss pay: no double count |
| f for rung 2 | The larger of the burst against the item's place and against the enemy's box at the burst; graded to `NEAR_OUT` (live, 300) | The card ("near the item's place or near the enemy", "the near-miss pay's own rule") |
| Rung 1's "clear line to the item" | A trace from his eye to the item's place + 16 units up, made only while the item is up and the enemy within 6 s of way of it; to the enemy: the simulator's own sight (`visible`) | Rung 1 at a pickup needs the enemy near the item anyway; it saves the traces |
| "A weapon that reaches" | The lightning gun 768, the shotgun 1,500 (the game's range, MECHANICS; the simulator's own is 8,192), the hitscan guns 8,192, rockets, grenades and plasma always, the gauntlet never | The card ("by the game's own numbers") |
| Seconds of way | The route's table every frame (`_cb_ways`) | Cheap (no measurable cost); the same seconds his routes' inputs read |
| The by-the-second pressure | `min(1, 2 x rung 2 now + 0.25 x his crosshair on the item now with a weapon that reaches)` | The card: shells "full weight", the crosshair "a quarter"; rung 2's 0.5 maps to full |
| The steal | "Headed for": the enemy's target (his intention) is the item and under 4 s of way, the item up; "pressured": a rung 2 or rung 3 event of his in the window at that moment; "within 10 s": of the last such moment; pays `CONTEST_W x flat` inside the spawn's cap, once | The card's rung 4 |
| A spawn | From the item coming up to its pickup; a new round starts the books again | The card ("one contest pay for each spawn") |
| Where it counts | Games and normal rounds of two policy seats; not in runs, rooms, the test map, nor with a scripted seat | As the pre-aim pay's games |
| The free-pickup charge when he is dead | Charged (the owner: "always") | The card |
| Into `r_long` | The contest pay and the rail's pickup pay (as the item pays); the long line not (as the pre-aim pay) | The long values' items part |
| The rail's pickup pay | Zero-sum (the enemy loses as much, as every item's pay, `SMALL_ZERO`); once a life (reset at his next life, `_fresh`); only when he holds no rail; not in runs; the hands count it as every term | The card names the item picker; the hands count every term (as in 2.2b) |
| The long line's distance | Between the two players' places at the fresh sighting, over 768 | The card ("from beyond 768 units") |
| The lever's start on the clock | `--lev-from 10` in the trainer (its own count, the same as the item picker's freeze): the rollouts of updates 1 to 10 play the lever at share 0, update 11's on at `LEV_G` (1 from the start's live file) | Exact (a ramp's write plays 2 to 3 updates late); the lever and the item picker's choices start together |
| The hands' token's gate | Written -30 to clock 8, then to 0 at clock 17 (plays about updates 10 to 20) | The card ("opened over updates 10 to 20"), the write's lag as 2.2b's restart treated `H2_WADD` |
| The lever's lesson | Every target decision of his seats (a new draw, or a change mid-trip) while on the held draw and alive; the ratio around the probability as played (his target logits as played less the lever's add, plus the share x the lever now); the advantage from its own pay by GAE on the ticks, its two parts brought to spread 1 and added (2.2b's) | The card ("from every decision he makes ... by his own play") |
| Its size (rule 13) | The mean and the largest |lever| at his readings, and the mean on a sample of the lesson's rows; flagged over 40 | One number added to one score: its own size is its length |
| What the hands are shown | What the lever adds (share x lever, clipped to 5), in the first of 2.2b's four score columns; the other three 0; their design statistics kept (the columns were constant at the start) | The card ("the token built in 2.2b"); no new columns |
| League seats | A league file with a lever of its own plays it at its own saved share; a 2.2a file (none) plays 0 | As 2.2b's league seats with a fight network |
| The lever's inputs' norm | 2.2b's measured norm of the same inputs on the same keep readings, taken by name (`lever22_init.py`) | They are the same numbers |
| The judge with the items | 2.2b's accepted refit (`items_22b.json`), not refitted again | Its 100 games are of the same start (2.2a's update 90) |
| The new inputs' place | Read by the hands' encoder only, no new attention token (the encoder's columns at zero weight) | The brief: "inputs that start at zero weight"; a new token would need a gate of its own and a schedule the card does not give |
| The tracker's pass odds | Keep learning on the readings' rows as in 2.2b, though nothing reads them in play now (the options are out) | Changes nothing else; reported in the fight block |
| Saves kept | At 10, 20, every 20, and the end (with optimizers) | The card's stages are at 10 and 20 |
| The speed alarm's bar | Three times the hands' weapon-key KL's normal (0.0042, 2.2a's median): 0.0126 | 2.2b's rule ("three times its normal") on the right figure |

## Every difference of the command from 2.2b's

`python tools/run/check_settings.py docs/runs/2.2/2.2c/train.cmd --ref docs/runs/2.2/2.2b/train.cmd`, without an allow list: 17 names, every
one deliberate (with `start.ps1`'s allow list: PASS). `--minutes` is the cap given to `start.ps1` (the run ends at `--max-updates 100`).

| Name | 2.2c | 2.2b | Why |
|---|---|---|---|
| `--run` | duel_gru_2_2c | duel_gru_2_2b | the run |
| `--minutes`, `--max-updates` | 1440, 100 | 1440, 1000 | the owner's length (100 updates); minutes a cap |
| `--env` | duel_env_ffa22c | duel_env_ffa22b | list 22c (E) |
| `--lever`, `--lev-g`, `--lev-from` | 1, 1, 10 | unset | the lever (C); its share 1, played 0 on updates 1 to 10 |
| `CONTEST`, `CONTEST_W`, `CEDE_W` | 1, 0.8, 0.1 | unset | the contest pay (A) |
| `RAIL_CHAIN`, `RAIL_PICK_PAY`, `RAIL_LINE_PAY` | 1, 0.15, 0.10 | unset | the rail chain (B) |
| `RAIL_FAR_PAY` | 0.5 | 0.1 | the owner's 0.5 (B) |
| `AHEAD_IN` | 1 | unset | the brain's places ahead as inputs (E) |
| `FIGHT_SPLIT` | 22c | unset (22b) | the pay split's groups (D1) |
| `NEAR_PAY` | 5 | unset (live 0 -> 5 over 0 to 20) | 2.2b's size from update 0 (D5) |
| `--win-scale-items`, `--win-scale-fight` | 1, 1 | 1, 1 | measured again (the same values) |

Against the start file's settings (`--ck` 2.2a's update 90): `DESC_OX` (the rater's, out since 2.2b) and `RAIL_FAR_PAY` (0.1 -> 0.5),
both allowed in `start.ps1`.

## Not done, or open

1. **The fork of "Read first" 1** (the contest's base is what the pickup paid, at most the flat): for the planning session.
2. **What works against the run's aim, seen in the build** (none changed: the card's sizes are the owner's): three enemy big pickups in
   four are free at the start, so the free-pickup charge starts as a steady small cost on him; the steal is frequent at the start (376
   against 1,789 of his own big pickups) because any damage he dealt the enemy while the enemy was heading for the item marks it, and
   it pays 80% of the flat each time; the rail chain's long line has almost nothing to pay on (the rail in hand at 4 of 720 far
   sightings); the contest pay is 1.9% of his pay's size at the start, under each big item's own pay.
3. **No server can play a 2.2c network**: `sim/export_duel.py` and the plugins know neither the lever nor list 22c (as 2.2b's: the
   export refuses a fight network); the `qlbot` image is not rebuilt.
4. **The item picker does not read the yellows' timers either** (nor did it in 2.2b): only the hands' encoder reads them now. Not asked.
5. **The tracker's pass odds still learn** on the readings' rows, while nothing in play reads them (the options are out): left as 2.2b
   built it.
6. `docs/runs/2.2/2.2c/train.cmd` is the dry run's (`--minutes 1440 --max-updates 100`); `start.ps1` writes it again from its
   `-Minutes -Updates`.
7. Not merged, not pushed; no row in `docs/RUNS.md` (the run has not started). Scratch folders left in place (nothing deleted):
   `data/sim_runs/scratch_22c_smoke_a`, `scratch_22c_build` (the ledger's ten games and the checks' short games),
   `scratch_22c_dryrun` (the dry run's start and league; its log `start_dryrun.log` beside this file, not committed, as 2.2b's), `scratch_22c_smoke_full1` and `scratch_22c_smoke_full_clock9` (the full-size trials).

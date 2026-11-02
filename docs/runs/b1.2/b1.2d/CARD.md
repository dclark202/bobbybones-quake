# b1.2d: the pay table set by the point, the speed pay down, damage taken 0.8, the stack lead out, the long rail up

*2026-11-02 (owner): "I think generally we should trend the speed pay down and spread it out over the small items. But I want to be very careful that combat still wins out in his decisions"; "we have this table as a baseline, and win chance pay does the 'correction' to it"; "I think the rail pay can go up"; "Let's put it in a card for B1.2d to experiment with after this run ends. I think we should nail this down before going to 1.3". The family: [README](../README.md). Why: b1.2c's read (below).*

**Marks:** ✅ built and tested · ⏳ to build · 🧪 to measure · ❓ owner's decision

## The owner's page

| | |
|---|---|
| Started from | **b1.2c's save of update 250** (`duel_gru_b1_2c/keep/policy_nojerk_b12c.pt`, with its optimizer), the first save after its jerk fade ended (owner, 11-02); b1.2c's end values kept |
| Started by | the owner, in another session (`start.ps1`), after the core test below |
| Run | `duel_gru_b1_2d` |
| Goal | the pay table as the baseline, win chance pay as the correction to it; combat wins his decisions |
| Stays | damage dealt, frags, deaths, `WIN_ADD` 0.33, the target-switch cost (0.02; owner, 11-02: "Stack lead only"), fairness limits, `!aim default`, b1.2c's end values of the firing costs, contact and jerk |
| Length | **12 hours** (`--minutes 720`; owner, 11-02: "I will likely cancel it early and start B1.3 tonight, but i'd rather it go long than have to restart it") |
| Kept | each save of the fade with its optimizer, and the first save with it done |

## Why

b1.2c gave him every small health and armor item as an input. He reads them (their encoder weights grew from 0 to about a fifth of a typical input's) but barely acts on them: the share of small items taken when within 1 s of his way went from 22% to 23% (update 160 against b1.1; bubbles 25% to 35%, 25 health 20% to 14%). Small items pay about 0.04 a player-minute in all, against frags 0.70 and speed pay 0.68: too little to change a decision. And the table priced a point above 100, which decays 1 a second, like a lasting one, with decay charged nothing.

## The table

Health and armor priced by the point, the same rate for both (armor takes 2/3 of each hit while it lasts, so his life is about health plus armor). Points are priced by where they land:

| Rule | Value |
|---|---|
| Points that bring health or armor up to 100 | **0.004 a point** |
| Points above 100 | **0.002 a point** |
| Decay above 100 | **charged 0.002 a point**, only on points that were paid above 100: not the spawn's 125, not what damage took first (found in the build: otherwise every respawn cost 0.05 never paid) |
| Flat item pay (`ITEM_FLAT` on mega, red, yellow) | **out**: the per-point rule prices them |
| Zero-sum | kept: the enemy loses what he gains, decay included |

**Low, mid, high** are the one stat the item adds to (health for health items, armor for armor items) when he picks it up: **low** = the pickup stays at or under 100, **mid** = it straddles 100, **high** = it lands wholly above 100.

| Item | Low | Mid | High | Today |
|---|---|---|---|---|
| Red armor (+100, to 200) | 0 armor: **0.40** | 50 armor: **0.30** | 100 armor: **0.20** | 0.20 |
| Mega (+100, to 200) | (always over 100) | 60 health: **0.28** | 100 health: **0.20** | 0.25 |
| Yellow armor (+50, to 200) | 0 to 50 armor: **0.20** | 75 armor: **0.15** | 100 armor: **0.10** | 0.10 |
| Green armor (+25, to 200) | 0 to 75 armor: **0.10** | 90 armor: **0.07** | 100 armor: **0.05** | 0.05 |
| 50 health (to 100 only) | 50 health or less: **0.20** | 80 health: **0.08** | 100 or more: nothing | 0.125 |
| 25 health (to 100 only) | 75 health or less: **0.10** | 90 health: **0.04** | 100 or more: nothing | 0.0625 |
| Bubble or shard (+5, to 200) | under 95: **0.02** | 98: **0.014** | 100 or more: **0.01** | 0.01 to 0.0125 |

At high, the points are paid when taken and charged back as they decay, unless damage uses them first.

## The other pays

| Term | Now | b1.2d |
|---|---|---|
| Speed pay (`SPEED_PAY`) | 0.25 (0.68 a player-minute) | **0.125** (about 0.34) |
| Long rail (`RAIL_FAR_PAY`, 500 to 800 units) | 0.12 a hit | **0.25** |
| Damage taken (`DMG_TAKEN_W`, live), on the enemy's damage only (`DMG_ENEMY_ONLY=1`: his own splash, falls and hazards at full cost) | 1.0 | **0.8** (owner, 11-02; was b1.4a's plan) |
| Stack lead (`STACK_DIFF`, live) | 0.7 | **0**: the win part's judge already counts the stack edge (lasting and decaying parts); it paid for holding stack above 100, against the table's decay rule |
| Everything else | | unchanged |

## Combat wins

By size (`pay_terms`' size share: both sides of zero-sum terms counted; the watch line's "combat N× items and movement", which counts every item, weapon-order, stack and speed term):

| | Combat (damage dealt and taken, frags, deaths) | Items, weapons, stack, speed | Ratio |
|---|---|---|---|
| b1.2c, updates 173 to 182 | 4.44 a player-minute | 2.33 (health and armor 1.03, weapon order 0.24, stack lead 0.37, speed 0.69) | **1.9×** |
| b1.2d (estimated) | 4.13 (damage taken 1.55 → 1.24) | 1.78 (health and armor about 1.2, weapon order 0.24, stack lead 0, speed 0.34) | **about 2.3×** 🧪 |

(Corrected 11-02: the first estimate left out the weapon-order and stack-lead pays.)

**The rules for this and every later change:** no single pickup above 40% of a kill (a kill pays about 1.0 with its damage; the most is red armor at 0 armor, 0.40), and combat at least twice items and movement together, by size.

## The equilibrium

Both get back to 100 first: it pays twice what topping up does, so the small items count when hurt and pace counts less. Stack above 100 pays only if a fight uses it before it decays, so a mega or a red armor is taken when a fight is near or to deny it (zero-sum doubles denial). Farming a group of bubbles or shards above 100 nets nothing: the refill is charged back by the decay. Win pay corrects the rest: what actually wins games (contesting the mega when level, skipping a top-up to finish a kill). A far rail hit pays about 0.8 with its damage, so holding long angles is worth more.

## The schedule

**All five fade together in a straight line from b1.2c's values, over updates 10 to 70** (owner, 11-02: "all go at the start, fade over 40 updates from where they are now. All five changes"; then "fade starts at u10 and takes 60 updates"); `ramp_b12d.py --start 10 --over 60` writes them after each update. A check of 40% or less against the start holds the fade where it is. b1.2c's own end values (firing costs 0, contact freedom 100%, jerk 0) are kept as they are (owner: "the values we faded to are KEPT now").

| Dial | Updates 0 to 10 | 25 | 40 | 55 | 70 on |
|---|---|---|---|---|---|
| The table (`ITEM_PT_MIX`: the old rates → the table by the point, decay charge with it) | 0 | 0.25 | 0.5 | 0.75 | **1** |
| `SPEED_PAY` | 0.25 | 0.219 | 0.188 | 0.156 | **0.125** |
| `DMG_TAKEN_W` | 1.0 | 0.95 | 0.9 | 0.85 | **0.8** |
| `STACK_DIFF` | 0.7 | 0.525 | 0.35 | 0.175 | **0** |
| `RAIL_FAR_PAY` | 0.12 | 0.153 | 0.185 | 0.218 | **0.25** |

Saves kept with their optimizers: `policy_start_b12d.pt`, every save of the fade (`policy_fade10_b12d.pt` to `policy_fade60_b12d.pt`), `policy_faded_b12d.pt` (update 70). Then it settles to the end: 12 hours in all, about 170 updates at 4.2 minutes.

b1.2c's final check (its update 250 against b1.1, 160 games) runs beside b1.2d's start on the check cores (`final_check_b12c.py`, started once by `start.ps1`), into b1.2c's own `watch.log`.

**Against the owner's one-change rule:** five changes at once. Read by group in the checks and counters, not one at a time; the fade's saves are the way back.

Checks: against the start (b1.2c's end), every fourth against b1.1; the league keeps b1.1, v0.6.0's end and b1.2c's end as anchors.

## The cores

Owner, 2026-11-02: "Use the 8 P cores for training ONLY", "Leave 4 E cores free for my ordinary computer use", "Use 8 of the E cores for the checks", "up to half can be used for testing during the run if it's deemed necessary". The efficiency-core crash of October is fixed (owner).

| Use | Logical cores | Mask | Where it is set |
|---|---|---|---|
| The trainer and its 30 simulators, nothing else | 0, 1, 6, 7, 8, 9, 18, 19 (performance) | `0xC03C3` | `train.cmd` (`start /affinity C03C3`) |
| The watcher (every check and panel job inherits it), the ramp, the self-play logger | 2-5, 10-13 (efficiency) | `0x3C3C` | `start.ps1` |
| Of those, for a test during the run when needed | 10-13 (the checks keep 2-5) | `0x3C00` | by hand |
| The owner's own use | 14-17 (efficiency) | `0x3C000` | nothing of ours |

The checks sized to 8 cores: 4 maps at a time, 2 processes each (`CHECK_BATCH=4`, was 5); the panel 2 jobs at once, 1 while a check plays (`PANEL_PAR=2`, `PANEL_PAR_BUSY=1`); the self-play logger 1 map at a time. b1.2c ran the trainer on 16 cores (`0xC3FFF`) and every check on the 8 performance cores beside it.

**Before the run (owner: "before doing the full run, have it run a short test to make sure the CPU cores are being used effectively"; "they start once 1.2c is done"):** `cpu_test.py`, about 30 minutes, nothing else of ours running: b1.2d's own command on a scratch copy of b1.2c's end, and a check batch beside it as the watcher plays one. Passes when an update takes at most 10% more than b1.2c's 4.2 minutes, the trainer stays on the performance cores, the checks on their 8 cores, nothing of ours on the owner's four, and the batch finishes. If the update is slower: two of the test cores to the trainer (the 2026-10-19 measure: pinned to the performance cores, learning 133 s against 126 unpinned).

## Judged by

| Measure | b1.2c's end | Wanted |
|---|---|---|
| Win rate against b1.2c's end, against b1.1 | | at least 50% |
| Small items taken when within 1 s of his way (the scratchpad's pass-by measure, three maps) | 23% at update 160 | up |
| Pickups by item (`pick_by`) | | small items up |
| Stack at the start of a fight | | up |
| Mega and red armor | 0.80 and 0.94 a minute | hold |
| Pay by group (`pay_terms`) | combat 1.8× items and movement | combat at least 2× |
| Speed on his way, cells roamed | | hold |
| Rail far shots a minute, far hit rate | 5 far shots in 785 minutes, 0.20 | up |
| The owner's play test | "tunnel vision" | picks up what's near; still fights |

## Red team

| Risk | Measured alternative | Watch |
|---|---|---|
| Halving speed pay may cost strafe jumping and pace | 0.18 instead of 0.125 | speed on his way, cells |
| Red armor at 0 armor doubles, toward tunnel vision | red armor capped at 0.30 | armor share, targets, the panel's camping test |
| Mega worth less held idle | its above-100 points at 0.003 | mega share; v0.4.4's spawn camping |
| Small items may still not move: 0.02 under 100 is small | none safe above 100: more than the decay charge makes a farm | the pass-by measure; if flat, it is b1.3's job, not more pay |
| Far rail shots are rare | long-range starts | far shots a minute |
| Rail pay against "no more rail pay nudges" (owner, 2026-10-21) | | the owner's word of 2026-11-02 stands |
| Decay charge zero-sum: the enemy is paid for his decay | not zero-sum | the ledger |
| Hand-built / assumed | the line at 100, 0.004 and 0.002, 0.125, 0.25, the 40% and 2× rules | |
| Pay pathologies (ledger) | | negative scores, sign flips, lopsided games; a pump from damage or splash against refills |

## Before the start

| Step | Where it stands |
|---|---|
| The table in `sim/duel_env.py` (`ITEM_PT_LO`, `ITEM_PT_HI`, `ITEM_DECAY`, all live; in `ITEM_RATE`'s place when on), `duel_env_ffa.py` regenerated | ✅ |
| `SPEED_PAY`, `RAIL_FAR_PAY` | live already ✅ |
| Counters: `item_pt` (points to 100, over, decayed), `sm_pass` (small places near his way: passes, share taken) in `metrics.jsonl`; the watch line's "combat N× items and movement" and "small taken near" | ✅ |
| `pay_check.log`: all off = b1.2c's simulator to the bit (git HEAD); the split at one rate = the old rate to the bit; on: the game the same, the pay's change zero-sum in every frame, decay never above what was paid above 100 | ✅ ALL PASSED |
| `tools/ffa_check.py` | ❌ cannot run: its test map `maps/sim.bsp` is missing (not this change); `pay_check` runs on the group module instead |
| `make_files.py` → `train.cmd`; settings check against b1.2c's: only `--run`, `--minutes`, `ITEM_PT_*`, `SM_PASS` differ | ✅ |
| `ITEM_PT_MIX` (live): the fade from the old rates; at 0 with enemy-only damage at weight 1 it pays as b1.2c to the bit (`pay_check.log`) | ✅ |
| `ramp_b12d.py`: the five dials in one 40-update line; `ramp_test.log` (also with a hold) | ✅ ALL PASSED |
| `start.ps1`: refuses on a trainer running, b1.2c's dials not at their ends, a failed settings check or log; controls b1.2c's end and b1.1 widened | ✅ parsed; a check job with b1.2d's settings against b1.1 widened played |
| A dry run on the card | not done (owner: "just start it after c") |
| The cores: `train.cmd` on `C03C3`, `start.ps1` on `0x3C3C` with the checks sized; `cpu_test.py` written | ✅ built; the test runs once b1.2c is done 🧪 |
| Length | 12 hours, written (`make_files.py 720`) ✅ |
| The fade from update 10 over 60 updates; `ramp_test.log` (also with a hold) | ✅ ALL PASSED |
| b1.2c stopped at its update 250 save, kept with its optimizer as `policy_nojerk_b12c.pt` (owner, 11-02) | ⏳ about 12:51 |
| The core test (`cpu_test.py`) | 🧪 after b1.2c stops; results below |
| The start | the owner, in another session |

## The core test's results

*(filled in when it has run)*

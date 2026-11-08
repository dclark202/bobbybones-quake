# 1.7c: the weapons, under the pros' table

*Started from 1.7a's result, its save of update 90 (`keep/policy_end_17a.pt`), with its optimizer. Owner, 2026-11-07 evening: "ok let's do
it then. start it when it's ready, 12 hrs is fine, or you can run it until noon tomorrow"; "It should be a focused train session to get the
weapon goals"; "the pros table is the only one to consider"; "I honestly don't care if his win rate against himself plummets". The design
and its reasons: [TRAIN_UNDER_TABLE.md](TRAIN_UNDER_TABLE.md); the dial it runs on and its checks: [DIAL.md](DIAL.md).*

**Started from:** 1.7a's update 90 (`data/sim_runs/duel_gru_1_7a/keep/policy_end_17a.pt` + `opt_end_17a.pt`), widened to today's 994 inputs
with zero weights on 1.7b's four timer inputs (`tools/b17b_init.py widen-league`; it answers as update 90: `same`, 0 actions differ). Nothing
of 1.7b's training.

## The owner's page

| | |
|---|---|
| The one new thing | **the pros' weapon table chooses the weapon in hand of every network seat** (his, the league's eight snapshots, the anchors): `sim/weapon_dial.py choose()` sets the weapon key's action in place of the network's, exactly as `!weapons pros` does on a server and `--wpush-form replace` in the checks. In view by the distance to the enemy in 50-unit bins, out of view their travelling hand (`docs/pro_tables.json`, `sim/pro_hand.json`; by band, rockets / rail / lightning: close 60 / 7 / 33%, medium 35 / 22 / 43%, long 19 / 74 / 8%, out of view 72 / 16 / 12%). Fire, aim, movement, items and targets stay his |
| The weapon key | no policy gradient and no entropy bonus on the frames the table set it; it **copies the table** instead (cross-entropy 0.1 on the frames the key was read, from the shared layers detached: the key's own layer learns it alone; standing, never faded). At the end his own key is a fitted prior for the table, so that the choice can later be handed back with a standing leash and the dial can come off the servers |
| Frozen | the keep choice at the save's share (0.975) and learning nothing (`--keep-freeze 1`: it drifted into flicker in 1.7a after update 130 and in 1.7b); the order shut as at update 90 (`CMB_G`, `PADD`, `FADD`, `H2_FPG` 0, `ORD_GATE` -30); the habit seats off (`HABIT_P` 0: the table replaces them); the head's weapon credit off (`H2_WPG` 0: the key is not his) |
| Opening | live `WRULE_P` 0 -> 1 over updates 0 to 20 (`ramp_17c.py`): the share of lives under the table; reported, never held or stepped back (rule 6) |
| Pay | **unchanged from update 90**: 0.0055 a damage point, a frag 1, `WIN_ADD` 0.33, `DMG_TAKEN_W` 0.8, `ITEM_FLAT` MH 0.35 / RA 0.30 / YA 0.15, no cost for firing. The start's live.json is the save's own record (`start_live.py`), not 1.7a's end file |
| Length | the owner's: until noon 11-08 (`-Minutes` at the start; about 4.5 min an update) |
| Checks | every 20 updates: his save **under the table** against update 90 **plain** (200 games: the yardstick; the start reads 29.0%) and against update 90 **under the table** (100 games: the same hands and table, what the training added; the start reads 50% by construction); b1.2d's end plain every fourth; Cypher's measures of every check; **the rail owned by map** (wanted: over 60% on the rail maps by update 80, Campgrounds over 30%); the panel |
| Expected | against plain update 90 he starts at 29% and should climb as the hands learn rockets and the rail; he may end under 50% there (acceptable, the owner). What should appear: rocket prediction and splash, rail timing at range, dodging rockets, positions where the table's weapon is the better one, the rail taken because it is finally worth something. Cypher's three numbers can move here for a structural reason (escaping a lost fight is possible against rockets, not against lightning at 768 units); they are measured, not assumed |
| Not in this run | spam at doorways and holding rail angles: watched on the panel (rockets fired out of view and their hits, damage from unseen), not forced; the next layer if they do not appear (a fire prior out of view from the demos; the pros' holding places). The rail's ownership by a play-time rule: measured and rejected ([DIAL.md](DIAL.md)) |

## Red team

| Part | Hand-built or assumed | The measured alternative | Watch |
|---|---|---|---|
| The table | the pros' pooled hand (3,712 demos, all maps): what they hold, not why | per map (`pro_tables.json` has a table a map); by the stack (B-304) | a map where his mix under the pooled table loses badly where the pros' per-map table differs |
| The weapon choice as a rule | a hard-wired part on a choice the owner wants learnt (10-23: retire hard-wired parts by fading) | part 3 of the plan hands it back with a standing KL; the copy loss here is its fitted start | the copy loss falling and the agreement rising (the ramp logs both each update) |
| No PG on the key | assumed: a trained key drifts back to lightning (every run so far) | a KL instead of a mask (part 3) | nothing here: the key is not played while the rule is on |
| The keep choice frozen | its drift seen twice; frozen, it cannot adapt to the new fights either | let it learn with a flag | trips a player-minute and targets reached against the start (flagged at 1.5x / 0.7x) |
| Fairness: his rockets | 48 to 51% hits against a copy (the pros 36%) | against people (the play test's `player_stats`), the stand-in | before any public server |
| The rail he does not own | nothing here makes him take it; this run tests whether the head learns its value | a price on the rail pickup in the item table if the head has not moved it by update 40: the owner's call | rail owned by map at every check |
| The fire key with the rail | his rail press rate was near zero when he chose it | 1.7a's fire-push machinery (`FADD`) as the fallback | rail shots a minute with the rail in hand (the panel) |
| Pay pathologies | the ledger as every run | | negative frags, sign flips, lopsided games |

## The checklist

| | |
|---|---|
| built | `--wrule`, `--wrule-imit`, `--keep-freeze`, live `WRULE_P` in the trainer; `wrule` in the checkpoint; the watcher's checks under the table and the second control (`CTRL_TABLE`); the rail owned in the checks' stats (`weapons_owned`); the panel's player under the table; `ramp_17c.py`, `make_files.py`, `start_live.py`, `start.ps1`, `tests.py` |
| tests | `tests.py start` (the widened start answers as update 90), `ident` (the rule at share 0 = the trainer before it, to the bit; under the table the actions differ, every seat under it), `live` (WRULE_P written mid-run is played), `smoke` (10 small updates under the table: the copy loss falls, the save carries `wrule`, a restart loads the optimizer, a one-map check under the table finishes): their logs beside this card |
| level check of the start | 1.7a's update 90 under the pros' table against itself plain, 200 games: 58-142 (29.0%) ([DIAL.md](DIAL.md)) |
| start | `start.ps1 -Minutes <until noon>` from the main checkout after `b17c` is merged (the settings check against 1.7a's command: only `--run`, `--minutes`, `--keep-g`, `--wrule`, `--wrule-imit`, `--keep-freeze`, `--habit-p`, `--head2-wpg` differ). **Started 11-07 19:47 (970 min): a false start.** Two defects in the wiring, not in the design: (1) the watcher told the table control from the plain one by file path, and they are the same file, so the update-10 check played the control under the table and was filed as plain (fixed 22:43, by a flag); (2) **PPO's reference log-probability pass (`LP_PX`, the overlap-KL, step-KL and legs-guide passes) did not get the weapon key's mask the learner's has**, so the ratio was inflated on every frame under the table: the KL estimate went negative from update 25 (1.7a's +0.028 all run), the checks fell 29.0 (start) -> 28.5 (u30) -> 22.5 (u50) -> 23.5% (u70) against plain u90 and 46.5 -> 38 -> 41 -> 37% against u90 under the table, the rail owned unchanged, Cypher's numbers worse. Found 01:45 (the negative KL), fixed and re-tested (ident, smoke: the KL positive); not stopped by me (rule 6); **stopped on the owner's word 11-08 07:05 at update 111** ("Yes, stop it now and then start the right one"); its folder `duel_gru_1_7c_false1`. **Started again 11-08 07:09 with the fixed trainer, 720 minutes** (`false_start.ps1`). Lesson: a new per-head mask must reach every `head_masks` call; a negative `kl` in the metrics is a ratio defect and the ramp now has no eye on it: watch it by hand |

---

*The earlier draft of this card (2026-11-06 evening: the head holds the weapon, fitted to the pros, a KL opened as 1.7b's order) follows as
written; it is part 3 of the plan now.*

## What is known (the draft of 11-06)

| | Bobby (1.7a's update 90, 80 self-play games) | The pros | |
|---|---|---|---|
| In hand with the enemy in view: rockets / lightning / rail | 20 / 67 / 0.9% | 41 / 32 / 14% | |
| ... by distance (under 300 / 300 to 700 / over 700), lightning | 67 / 71 / 69% | 34 / 43 / 17% | flat: a habit, not a choice |
| **Out of view (travelling)**: rockets / lightning / rail | **19 / 66 / 1%** | **57 / 9 / 12%** | the lightning gun and the rail hum and give a player away |
| **At a new sighting** (after 1 s out of view), lightning | **69%** (67 / 70 / 69% at under 300 / 300 to 700 / over 700) | | he meets the enemy with what he travels with, at any distance |
| Hits (B-303): lightning close / mid / 500 to 750; rockets; rail | 47 / 38 / 22%; 49% (direct 20%); 40 shots in 36 games | 44 / 37 / 31%; 36% (10.5%); 37% | his rockets above the pros' (but see the red team), the lightning gun level |
| The game's switch during a reload (B-302) | the simulator's rule is the game's (within two frames) | | not a cause |
| 1.5a: the head's scores added to the weapon key | the rail at range one press in 55 s of that situation; no move toward the pros | | the press is too rare a choice to be tried |
| 1.5b: the head's weapon part prefitted to the pros (push 2.5, never run) | rockets in view 24 -> 37%, lightning 61 -> 50%, 56.5% against 1.3b's end untrained; still flat by distance | | the fit helps; the form keeps it flat |
| Weapon habits in the league (1.5a on) | he scores 53 to 55% against habit seats and plain ones alike | | the habits do not punish the lightning gun |
| The trade bonus (B-306) | 0.37 a player-minute, the lightning gun's steady stream earned it best | | zero-sum from 1.7b: its effect on his weapon measured there |

**The diagnosis.** His weapon in a fight is the weapon he travels with, and he travels with the lightning gun. The pros travel on rockets and
change by the distance of the fight they expect. Cypher: "everything you do in Quake you try to predict and do up front". A weapon is a plan
made before the sighting, not a reaction after it; Bobby's choice is a key press on the present frame, and the press that would change a
plan (the rail at range, rockets before a corner) is almost never tried.

## Experiments of 2026-11-07 (owner: "I'll let you run experiments now ... I just want more fighting and varied weapons")

**Does he fight less than before? No.** From the watcher's checks (both sides, ten maps): frags a player per ten-minute game
v0.6.0 9.3, b1.2a 6.6, b1.2d 7.7, 1.3b's end 9.6, 1.6a 11.3, 1.7a's u10 11.6, 1.7b's u90 10.4; the enemy in view 15 to 18% of
the time throughout. **What changed is the weapon** (in hand with the enemy in view, rockets / rail / lightning):

| | v0.6.0 | b1.1a's end | b1.2a | b1.2d | 1.3b start → end | 1.4b | 1.6a | 1.7a u10 | 1.7b u90 |
|---|---|---|---|---|---|---|---|---|---|
| in hand in view | 18 / 26 / 43% | 29 / 14 / 35% | 27 / 8 / 46% | 39 / 6 / 39% | 36 / 5 / 42 → 30 / 4 / 51% | 24 / 2 / 63% | 21 / 1 / 66% | 24 / 1 / 65% | 19 / 1 / 70% |

The rail went over b1.1 to b1.2a (unexplained then, HISTORY b1.0a); the lightning gun took over in 1.3b's run and 1.4b.

**A push on his weapon key at play time, no training** ([exp/wpush.py](exp/wpush.py): 1.7a's u90 pushed against itself plain,
200 games, the u90 check's own settings read back and compared; `sim/test_suite.py` WeaponPush, `tools/duel_eval.py --wpush`).
"share": every press of the three raised by p x the pros' share (the 1.5a habit seats' form); "ratio": a press of weapon j gets
p x (log s_j - log s_held), the pros' shares (in view by distance, out of view their travelling hand).

| arm | record (win rate) | rockets / rail / lightning in hand in view | ... out of view | rockets' share of his frags | kills a player per 10 min, pushed / plain |
|---|---|---|---|---|---|
| plain (the other side, every arm) | | 18 to 21 / 1 / 69 to 72% | 18 to 20 / 1 / 64 to 67% | 10% | |
| share 2 | 111-89 (55.5%) | 21 / 1 / 70% | 22 / 1 / 65% | | 11.9 / 10.7 |
| share 4 | 96-104 (48.0%) | 25 / 1 / 67% | 26 / 1 / 61% | | 10.8 / 11.0 |
| ratio 0.5 | 98-102 (49.0%) | 22 / 1 / 69% | 21 / 1 / 64% | | 11.2 / 11.0 |
| ratio 1 | 100-100 (50.0%) | 24 / 1 / 67% | 24 / 1 / 60% | 14% | 11.0 / 11.2 |
| **ratio 3** | **85-115 (42.5%)** | **35 / 1 / 55%** | **38 / 1 / 47%** | **24%** | **9.8 / 11.8** |
| the pros | | 41 / 14 / 32% | 57 / 12 / 9% | | |

**Why a push moves him so little** ([exp/wkey_diag.py](exp/wkey_diag.py), 6 games of 5 min on Blood Run): at a reading of his
weapon key with the lightning gun in hand out of view he gives "press the lightning gun" (a no-op) 0.67, "keep" 0.29, "press
rockets" 0.003; with rockets in hand he presses back to the lightning gun 6 to 8% of readings. A press of another weapon is a
rare event, and a push multiplies a rare event: ratio 1 (+1.8 on rockets from the lightning gun) took it to 0.0096.

**What it says.** Up to ratio 1 the mix moves little and costs nothing (49 to 55%); at ratio 3 the mix comes halfway to the pros'
and he loses 42.5%: his hands fight worse with rockets than with the lightning gun as they are. So the lightning gun is the best
weapon *for today's hands*, which never practise rocket fights (b1.2d's hands did: 39% rockets, "the rocket fights are getting
much better", owner). The rail is two problems: owned with ammunition 33% of his time on Aerowalk and held about 1%, and never
owned on Campgrounds (0%; B-286); even ratio 3 left it at 1% (the push for it is large only in view beyond about 700 units,
where he rarely is with it). Cypher's measures under ratio 3 (`wpush/r3/cypher.jsonl`): the pushed side out-stacked dies 55% (plain 53%),
deals 327 a minute (plain 336); his items as before.

**The weapon dial for play against people** (owner, 11-07: "Build the dial for play against people and I'll play test it when it's ready. Then afterwards we'll consider 1.7c"): [DIAL.md](DIAL.md). `!weapons light`: 48.0% against himself, rockets in view 27%; `!weapons strong`: 33.5%, rockets in view 41%; the rail does not move. On the local server for his play test.

## The proposal (rough)

**The weapon plan: the head holds the weapon he should have in hand**, five times a second, and he follows it unless his hands override.

| Part | What | From |
|---|---|---|
| 1. The plan | at each head tick, a choice over the weapons he owns with ammunition: the weapon to hold; held to the next tick. The simulator switches to it when it differs from the one in hand (the game's switch time; not mid-shot of a weapon whose reload is running: the game's own rule); his hands' weapon key overrides it for the last-moment change (he jumped into close range) | AlphaStar's action type chosen first; the order's form (1.7a, 1.7b) |
| 2. What it reads | what it needs, at the rate it chooses (the rule of 11-03): the brain's look-ahead (where and when the enemy next appears, the distance and height of that place), the order (its kind and point: spam a doorway, cut him off, break off), his weapons and ammunition, the enemy's weapon seen and the hums heard, the fight odds (1.7b) | the owner's 1.7 spec: "his weapon follows the order: grenades over a height difference, plasma in a corridor or at a teleporter exit, rockets at a corner, the rail for a long lane, the lightning gun close" |
| 3. Its start | fitted to the pros: their weapon in hand by the same situation, in view (by distance, height) **and out of view** (the travel weapon, by where and when the next sighting comes): labelled from the demos as the order's fit was (`tools/order_pros.py`'s way) | 1.5b's prefit (56.5% untrained) |
| 4. A KL to that fit through the run | sized from the first updates as 1.7b's ORD_KL | AlphaStar; 1.7a's postmortem |
| 5. Credit on the head's clock | the plan judged over about 5 s (the head's two-minute value), as the weapon key's since 1.5a (`H2_WPG`) | 1.5a, B |
| 6. Opened as 1.7b's order | the plan at the fit's rate with the head frozen while the hands learn to fight with the weapon it gives them, then learnt | 1.7a's postmortem cause 1 |

**The equilibrium.** Zero-sum combat pay (1.7b): a weapon is worth only what it wins. The pros' KL keeps rockets and the rail in his hands
while the value learns where they win. Cypher says a stand-and-trade lightning fight between equals goes to the bigger stack, while rockets
from a corridor or a held angle win fights for the defender. With the weapon planned ahead of the sighting, the copy that meets the enemy
with rockets at a corner, or the rail on a long lane, wins those fights. **Watched:** the travel hand (19 / 66 / 1% now) toward the pros'
(57 / 9 / 12%); the hand by sighting distance no longer flat; frags by weapon; rail owned (Campgrounds' rail never taken, B-286); the checks.

## Open questions ❓ and things to measure first 🧪

| | |
|---|---|
| 🧪 | the pros' hand by the situation the plan reads (the labels of part 3): in view by distance and height, out of view by the next sighting's distance and time; how often they switch at a sighting |
| 🧪 | whether 1.7b's zero-sum damage alone moves his weapon (its checks' hand numbers) |
| 🧪 | **fairness, before he uses more rockets**: his rocket hits (49%, direct 20%) are above the pros' (36%, 10.5%) in self-play, where the target is another Bobby who may dodge less than a person; measure his rockets against the people on the public servers (their logs) and the stand-in before the plan makes him fire more of them (the aim's limits stay; never miss on purpose) |
| ❓ | the plan's default: follow the plan unless the hands press (recommended: the press is the rare choice today) or a sum with the hands' weapon key (1.5a's form; rule 11's regularization) |
| ❓ | "hold an angle" as an order kind (the owner's 1.7 spec: "decide to hold an angle for a rail shot"; 1.7a has holding places as targets only): in 1.7c with the plan, or after |
| ❓ | weapon combos (a rocket to lift him, the lightning gun or the rail to finish; the 1.8 card's "possibly"): from the plan's inputs (the enemy in the air), or later |

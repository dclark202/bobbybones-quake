# 2.2b: the build's record

Written by the build (an Opus 5.5 worker, 2026-11-17) for the planning session. The card is [CARD.md](CARD.md); this file is the record of
what was built, how it was tested, and where the build departs from the card. Branch `b22b` (from `b293e76`), not merged.

## Not done, or open (read first)

1. **The optimizer at the start: a decision for the planning session.** Cold (the card), the second update's weapon KL is 0.30 (2.2a's:
   0.015) even at a tenth of the rate; with 2.2a's update-100 optimizer carried it is 0.002. `start.ps1 -Opt <file>` carries one. I
   recommend `-Opt data\sim_runs\duel_gru_2_2a\keep\opt_u100.pt` ("The full-size trial").
2. **`--lr-warm` did nothing as the card's command had it** (it counts from `--fade-start`, 7214). Fixed with a new `--lr-warm-start`
   (the trainer); worth a line in CLAUDE.md's gotchas (not mine to write).
3. **An update takes 7.3 to 7.6 minutes**, not toward 2.1d's 5.3 (2.2a: 6.6).
4. **Two meanings shift under the fight options** (not rules acting on him): his input "his intention is the enemy" is 1 on all four
   options, back off included; the `--ahead` readout's target class 8 means "on a fight option". See "The audit's points".
5. **The ramp's inherited flag "the win part is over 0.6 of the pay's size"** fires on nearly every update with the judge with the items
   as the pay (0.59 to 0.79 in the measurements; 2.2a's first update: 0.60). The monitor reports every FLAG; the planning session may want
   to tell the monitor it is expected, or move the line.
6. Pay groups that are my reading of the card: `high` (0 here) with the fight network's; `drops` and `item_seek` the hands' only;
   `item_decay` and `stack_keep` the item picker's ("The ledger").
7. The few frag frames whose win part is at or below 0 (7 of 454, the same count under both judges) were not traced frame by frame;
   lopsided finished games were not measured (only games under way).
8. `tools/run/make_train_cmd.py` could not make 2.2b's command (its form needs the old `cd /d ...ql-bot` line); `make_files.py` (2.2a's
   pattern) makes it from 2.2a's command as it ran, with the guard inside.
9. The league seats get no weapon nudge; the fight network's weapon scores learn from practice trips' dealt weapons only.
10. An angle practice trip ends on arrival and never holds; the map sense left with the rater.
11. No server can play a 2.2b network (the export refuses it; the plugins do not know the fight options); the `qlbot` image is not rebuilt.
12. The test map's `testlab.bsp` is missing in `data/maps`: the generated module's check ran on Blood Run.
13. `check_settings.py` applies the guard to the command alone (it reads no live file); the trainer reads the run's `live.json` too.
14. Not merged, not pushed; branch `b22b`. No row in `docs/RUNS.md` for 2.2b (it has not started). Scratch folders left in place
    (nothing deleted): `data/sim_runs/scratch_22b_*` (the start's pieces, smokes, trials, the dry run), `scratch_22b_items` (the 100
    refit games).

## What was built, by the card's changes

| # | Change | Where | As built |
|---|---|---|---|
| 1 | The rater of options removed | `sim/train_duel_rnn.py` (no `--outlook`, `--out22`, `--map-sense`); `tools/fight22_init.py layout` | The start file has none of its parts (`head2.out.*`, `dsc.*`, `vw.*`, `out_g`, `out_pick`, `out_src`; the layout keys outlook, desc22, vw). The tracker and its pass odds stay and keep learning with their own Adam (`trk22_opt`). A 2.2a league file is loaded with the rater's parts left out. The map sense was read only by the rater: it goes too |
| 2 | The fight network | `sim/fightnet.py`; the trainer's `--fight22` | 1,230 inputs (the brain 256, the tracker 18, his inputs 69, the items 17, the head 256, the hands 512, the options' numbers 80, where he is headed 22), two hidden layers of 256, 4 scores, 10 weapon scores, 2 forecasts (damage and frags; the win part). Its own Adam (1e-4), its own random stream. Decay (`H2_L2`) on its first and last layers. A copy plays; league snapshots keep theirs (`SNAP_FN`) |
| 3 | The fight options in the simulator | `sim/duel_env.py` (`FIGHT=1`) on 1.7's combat order's points | Him: the enemy's believed place. Cut off: 8 holding places and 8 choke points of the map's tables, valid if he gets there before the enemy; the trainer picks the one the tracker's pass odds favour most (max of the 2 s and 4 s odds). The angle: a place that sees the candidate, reached first, 150 to 1,500 units away, the quickest. Away: the best way out (1.7b's break-off, `OUT_LIVE` 1.5 s counted from the trip's start). The order rides on the keep column (`FG_ASK` 2048, `FG_KIND` 4096 x kind, `FG_CAND` 65536 x candidate) |
| 4 | The hands' new inputs | group "b22b fight" (20 columns), list 22b, `sim/duel_env_ffa22b.py`; token `fight22` | The kind, the spot and its look point, the time headed there, the four scores (`FG_IN_G`). Their statistics measured on the start's play (`tools/fight22_init.py norm`, 71,760 readings); the four score columns are constant at the start (the scores start equal) and keep their design statistics. The token's gate is live `FGT_GATE`: -30 shut, -12 after the first update, 0 at update 20 |
| 5 | Practice | the trainer | Dealt at a new decision with chance `PRACTICE_P`; him, cut and angle only with the enemy out of view; half dealt evenly, half from the fight network's own softmax; a random weapon he owns (no gauntlet). Held to the spot, a sighting, 4 s or death. The probability of what was played is the mixture (practice x (half even + half its own) + the rest x his list) |
| 6 | Both players practise | the trainer | The league seats are dealt practice too (counted apart: `league_dealt`) |
| 7 | Fight starts | `sim/duel_env.py` `FIGHT_START_P` 0.20, `PRO_START_P` 0.35 → 0.15 | A pro start's moment, then one seat (evenly drawn) keeps it and gets the frag, the other is fresh at a spawn by the measured rule; the judge's base read again |
| 8 | The pay split | `sim/fight22.py`; `--head2-pay items_win` | See the ledger below. The item picker's choice lessons are off for its first 10 updates (`--h2-choice-warm 10`); its forecast learns from the first |
| 8b | The judge with the items is the paid win chance | `sim/duel_env.py` `JUDGE_PAY=1`; `items_22b.json` | One judge everywhere (the hands, the item picker, the fight network). Refitted: see "The judge with the items" |
| 9 | The win scales | `--win-scale-items`, `--win-scale-fight` | Measured on the start's games: see "The win scales" |
| 10 | The fight options enter his list | the trainer (`FGT_G`, `FGT_W`, `H2_WADD`, `FGT_BIAS`) | One list: the 17 item targets with "the enemy" (8) and the places (9 to 16) shut, then the four fight scores masked by validity, drawn with the kept dice. A coin per trip with chance `FGT_G` says whether the four are in the list. The weapon: the fight network's nudge (x `FGT_W`) added to the hands' weapon scores while the item picker's push fades (`H2_WADD` 1 → 0) |
| 11 | Reported, not obeyed | `ramp_22b.py` | At update 60 the plain-words line per option; the one number `FGT_BIAS` decided once (the mean of the trainer's `bias_to_set` over updates 51 to 60) |
| 12 | Plain words | `ramp_22b.py` | The ramp's lines open with what plays |
| 13 | The near-miss pay | `sim/duel_env.py` `NEAR_MISS=1`, live `NEAR_PAY` (0 → 5 over updates 0 to 20), `NEAR_OUT` 300 | A rocket, grenade or plasma ball that hurts nobody: the shooter is paid `NEAR_PAY` points of damage's pay x f, f = 1 at the splash's edge falling to 0 at `NEAR_OUT`; the enemy is charged the same (zero-sum); at most one full near miss a second a player (a budget); kept out of `dealt` and his damage inputs |

The metrics' `fight` block (change 12's readouts): practice trips by option and how they ended, damage on them against his own choices,
the share of his decisions each destination wins, how often each side wins the list, the bias, seat frames by option, near misses,
projectiles fired in and out of view, the weapon out of fights by destination, sizes (flag over 40), its lesson (forecast errors, the
win scale and the ratio of flat pay to the win part), the tracker's pass odds, non-finite counts.

## The ledger: every pay term and who counts it

Measured on the start's own games (`legs_test.py --pay`: the start file playing itself on all ten maps, 16 matches x 4,000 frames a map,
practice 0, 2.2b's command with its `aim2_env.cmd`, the start's `live.json` with the near-miss pay at its full 5, the pay as the
trainer's workers set it: `--item-reward 0`, `--item-loss 0.5`, `--intent-seek 1`, `DMG_REWARD` 0.005, `DMG_TAKEN_W` 0.9). 1,209,840 seat
frames of whole games. Sums over both seats, so a zero-sum term sums to 0: "size" is the sum of its absolute values. The groups are
`sim/fight22.py`'s, by the term's name; **the hands count every term, as ever**.

| term | group | counted by | sum | size | minus | plus | share of all pay's size |
|---|---|---|---|---|---|---|---|
| win_part | win | the item picker x k_items, the fight network x k_fight (+ the hands) | 0.0000 | 5079.5484 | -2539.7742 | 2539.7742 | 0.5875 |
| dmg_dealt | fight | the fight network (+ the hands) | 743.7897 | 743.7897 | 0.0000 | 743.7897 | 0.0860 |
| dmg_taken | fight | the fight network (+ the hands) | -725.5391 | 725.5391 | -725.5391 | 0.0000 | 0.0839 |
| death | fight | the fight network (+ the hands) | -477.0000 | 477.0000 | -477.0000 | 0.0000 | 0.0552 |
| frag | fight | the fight network (+ the hands) | 454.0000 | 454.0000 | 0.0000 | 454.0000 | 0.0525 |
| item_RA | items | the item picker (+ the hands) | 0.0000 | 343.4929 | -171.7464 | 171.7464 | 0.0397 |
| item_YA | items | the item picker (+ the hands) | 0.0000 | 219.3527 | -109.6763 | 109.6763 | 0.0254 |
| item_MH | items | the item picker (+ the hands) | 0.0000 | 190.3928 | -95.1964 | 95.1964 | 0.0220 |
| big_order | items | the item picker (+ the hands) | 0.0000 | 172.6000 | -86.3000 | 86.3000 | 0.0200 |
| item_flat_other | items | the item picker (+ the hands) | 0.0000 | 74.2910 | -37.1455 | 37.1455 | 0.0086 |
| item_decay | items | the item picker (+ the hands) | 0.0000 | 46.6308 | -23.3154 | 23.3154 | 0.0054 |
| preaim | other | the hands only | -0.0000 | 45.2080 | -22.6040 | 22.6040 | 0.0052 |
| near_miss | fight | the fight network (+ the hands) | 0.0000 | 30.4869 | -15.2435 | 15.2435 | 0.0035 |
| watch | other | the hands only | 0.0000 | 18.4947 | -9.2473 | 9.2473 | 0.0021 |
| know | other | the hands only | 0.0000 | 11.7372 | -5.8686 | 5.8686 | 0.0014 |
| stack_keep | items | the item picker (+ the hands) | -6.7900 | 6.7900 | -6.7900 | 0.0000 | 0.0008 |
| drops | other | the hands only | -0.0000 | 5.9000 | -2.9500 | 2.9500 | 0.0007 |
| rail | fight | the fight network (+ the hands) | 0.0000 | 0.2375 | -0.1188 | 0.1188 | 0.0000 |

The terms at 0 in these games, by group (the switches that would pay them are off or at 0): items `item_points`, `items_other`,
`item_loss`, `stack_diff` (`STACK_DIFF` 0); fight `high` (`HIGH_PAY` 0), `deaths_other`; win `win_pay` (`WIN_W` 0: the win part is
`win_part`); the hands only `item_seek`, `jerk`, `weapon_switch`, `hop`, `blind_fire`, `move_round`, `course`, `fire_toggle`, `shot_price`,
`blind_rocket`, `style`, `way`, `way_claw`, `speed`, `speed_run`, `intent_switch`, `runs`, `lg_quiet`, `edge`, `cover`.

Where the split departs from the coordinator's list: **`high`** (the high ground's pay, 0 here) is grouped with the fight network's;
**`item_decay`, `stack_keep`** go with the items (the item picker's); **`drops`** (an item dropped by a death) and **`item_seek`**
(the way to the chosen item, 0 here) are the hands' only. Each of these is my reading of the card ("items" / "damage, far rails, frags,
deaths, near misses"); the planning session may move any of them by name in `sim/fight22.py`.

**The pathology check** (the same games, the judge with the items as the pay): of 454 frags, the frag term was above 0 for all (0 at or
below 0); the fragger's whole frame pay was at or below 0 on 2 (0.4%); the win part was at or below 0 on 7 frag frames (1.5%), **the
same count under both judges**, so not the items' doing; the victim's whole pay was at or above 0 on 1. The cause of these few frames was
not traced frame by frame (not done). No negative frags, no sign flip of the items judge against the item-blind one. Lopsided games:
the games under way when the 100 s of each map ended (160 games) had a mean score gap of 2.7 frags, 3 at 10 or more (fight starts give a
one-frag lead by design); these are not finished games, so this reads the start of games only.

## The judge with the items (correction A)

**Wired as the paid win chance**: `JUDGE_PAY=1` (`sim/duel_env.py`): the win part paid in whole games is `(WIN_W x WIN_GAIN + WIN_ADD) x
wh_raw`, the judge with the items' change this frame, in place of `wb_raw` (the item-blind judge's). It needs `JUDGE_ITEMS` and `WIN_JUDGE`
(asserted at import). Off: the pay as before, bit for bit (the identity replays). The hands, the item picker and the fight network all
learn from this one win part (each times its own scale). The readouts that read `wh_raw` (the head's pay truth, 1.9a on) were already this judge.

**Refit** (`tools/run/fit_items.py`, the same procedure as 2.2a's `items_22a.json`): 100 new games of 2.2a's update 90 against itself
(`data/sim_runs/scratch_22b_items/selfplay/items22b_u90`), the race part on 117,301 rows (log loss 0.6528 against a coin's 0.6931; its
bins on the diagonal within 0.04), held out by game on 55,200 rows: log loss 0.36708 for the item-blind judge, 0.36560 with the items,
a difference of -0.00149 (95%: -0.00236 to -0.00070); every fold chose the 6 s horizon; K mega 1, K red 1. **ACCEPTED**
(`docs/runs/2.2/2.2b/items_22b.json`, its log `fit_items_22b.log`). 2.2a's fit for comparison: -0.00108 (95%: -0.00185 to -0.00027) on
50,400 rows.

**The pay's difference from 2.2a's judge** (the same games as the ledger: the win part per frame, `WIN_ADD` 0.33 x the change, both
judges on the same frames, 1,209,840 seat frames of whole games): the item-blind judge (what 2.2a paid) mean 0.0000, spread 0.0360; the
judge with the items mean 0.0000, spread 0.0340 (0.94 of it). Both are zero-sum, so the mean is 0 by construction; the judge with the
items moves the pay per frame about 6% less.

## The win scales (change 9)

`k = max(1, the flat part's size / the win part's size)` on the ledger's games: the item picker's flat part (items) is 0.206 of the win
part's size, the fight network's (damage, frags, deaths, far rails, near misses at 5) 0.436: **both scales are 1** (the win part is
already the larger by 4.8 and 2.3 times). Written to `win_scale_22b.json`; `start.ps1` passes it to `make_files.py`. The trainer logs the
same ratio every update from its own rollout (`fight.lesson.win_scale`) and flags a scale under the flat part's size: in the three
full-size trials (2 updates each, 725,760 frames an update) the flat part was 0.16 to 0.21 (items) and 0.14 to 0.38 (fight) of the win
part, so 1 holds at the start's settings and with every dial open.

## The guard (correction B)

`sim/judge_guard.py` `check(env, live, root)`: a command whose win-chance pay is on (`WIN_ADD` or `WIN_W` above 0, in the command or in the
run's `live.json`) **or set up** (`WIN_JUDGE` named: a live file may switch the pay on later, as 2.2a's did) must have `JUDGE_PAY=1`, a
`WIN_JUDGE` that exists, and a `JUDGE_ITEMS` whose file says `"accepted": true` (`tools/run/fit_items.py`). Otherwise:

| Where | Behaviour on refusal |
|---|---|
| `sim/train_duel_rnn.py` | Right after its arguments are read (its environment and the run folder's `live.json`): prints `REFUSED (the judge's guard): ...` with the reason and the fix, exit code 2, before any simulator or network is made. `--old-judge-replay 1` lets an older command run (a replay or an evaluation) and prints that it did |
| `tools/run/check_settings.py` | Runs on every command it reads (the command's own environment; it does not read a live file, so it leans on `WIN_JUDGE` counting as "set up"): `REFUSED the judge's guard: ...` and exit 1, whatever the settings' comparison says; a passing command prints `judge's guard: the win-chance pay reads the judge with the items (...)` |
| `tools/run/make_train_cmd.py` | `REFUSED, train.cmd not written` (exit 1): nothing is written |
| `docs/runs/2.2/2.2b/make_files.py` | Asserts the guard on the command it writes |

Tests (`tests.py guard`: all passed): `check()` refuses a command without `JUDGE_PAY`, one whose fit says `"accepted": false`, one whose
fit file does not exist, and a command without the win pay whose live file switches `WIN_ADD` on; it passes the judge with an accepted
fit and a command with no win pay; `check_settings.py` refuses 2.2a's command (exit 1) and passes 2.2b's on the guard; `make_train_cmd.py`
refuses an old-style command and leaves `train.cmd` byte for byte as it was; the trainer refuses at its start (exit 2) and goes past the
guard with `--old-judge-replay 1`. The checks' players and `duel_eval` do not pay and are not touched.

## The audit's points (correction C)

**His legs.** 2.2b runs with `--no-switch 1`: his own network walks; nothing else moves him. The legs test (`legs_test.py`: the start
network playing itself, practice dealt at 12%, the simulator's own fight options; 4 maps x 4,000 frames x 32 seats) reached the spot or met
the enemy on dealt practice trips:

| Option | Blood Run | Aerowalk | Toxicity | Campgrounds |
|---|---|---|---|---|
| Go at him | 0.586 | 0.816 | 0.724 | 0.573 |
| Cut him off | 0.826 | 0.967 | 0.855 | 0.855 |
| Hold an angle | 0.818 | 0.933 | 0.873 | 0.907 |
| Back off | 0.922 | 0.925 | 0.920 | 0.893 |

In the full-size trial with every dial open (one update, all ten maps): him 0.81, cut 0.96, angle 0.95, away 0.98.

**The command's start values are the live file's** where the trainer takes one (`start_values.py`: 53 names, all equal; `start.ps1`
refuses otherwise). Where the trainer takes none: `H2_PG` and `H2_MIX` start from the trainer's own factor (1 and 0, equal to the live
file's); the rater's `OUT_*` names are gone with it. Three names 2.2a's command left unset (`CONTACT_FREE`, `COST_FIRE_W`, `COST_JERK_W`:
1, 1, 1 by default had its live file been refused) are now set to the live values (1, 0, 0).

**Every setting of 2.2b's command** against 2.2a's: the table at the end ("Every setting"). 440 names; 35 play differently from 2.2a's
last values; 19 differ only as written (2.2a's live file had them at 2.2b's value).

**The new module is made the project's way.** `sim/duel_env_ffa22b.py` is 20e's wrapper with the list's name changed (made by `sed` from
`duel_env_ffa20e.py`; `sim/input_list.py extend('22b', '20e', ('b22b fight',))` wrote `sim/input_list_22b.json` and `docs/INPUTS_22b.csv`).
20e is not a frozen simulator: it is a thin wrapper that runs today's `duel_env_ffa.py` with list 20e's columns. Proof that nothing of the
game changed with the switches off: fixed-seed replays of the tree before 2.2b's changes (HEAD at the start) against the new tree, the same
actions: **identical** (inputs, pay, done flags) on Blood Run (800 frames) and on Blood Run and Hektik (1,200 frames, 16 seats); the 1,108
old columns equal and the 20 new ones 0. With `FIGHT=1` and `NEAR_MISS=1` at `NEAR_PAY` 0 and no fight order given: the old inputs and the
pay identical. The generated module was regenerated by `tools/make_ffa_env.py` after every edit; `tools/ffa_check.py`'s check on Blood Run
(the test map's `testlab.bsp` is missing in `data/maps`): observations, pay and done equal over 1,500 frames x 48 seats.

**The inert settings.** None of these changes the pay, a live lesson, an input a network reads, or his seats in 2.2b:

| Setting | Value | What it does | Inert? | Cost |
|---|---|---|---|---|
| `PRO_ITEMS` | 1 | The pros' item order replaces the item rule's (`intent_rule`) | Yes: the rule only labels the item lesson (off: `--intent-teach 0`, `INTENT_TEACH_W` 0) and the runner (never plays) | The rule runs every frame for every seat |
| `PRO_WEAPON` | 1 | The weapon teacher's label from the pros' table | Yes: the weapon teacher is off (`--weapon-teach 0`) | Small |
| `STACK_TEACH`, `SPAWN_TEACH` | 1, 1 | The walking teacher's labels toward the item rule's pick | Yes: the teacher is off (`--teach 0`) | Its locate and way steps for the seats it labels, every frame |
| `RULE_HUNT`, `RULE_CONTEST` | 50, 2 | Blank the item rule's label where hunting or contesting is reasonable | Yes: they change a label nobody learns from | A goal loop and two locates every frame |
| `TARGETS_FREE` | 2 | Lets a held place be dropped for an item | Yes: needs his target at a place (9 to 16), shut under `FIGHT` | One vector step |
| `PREFIRE`, `EMERGE_IN` | 1, 1 | 39 + 8 old input columns (pre-fire, emergence) | Yes: cut from the lists since list 18; no pay or lesson reads them | **Real**: traces and a way search every frame for columns nobody reads |
| `BLIND_PLACES` | 150 | Marks a blind rocket near a pro place as free | Yes: the blind-rocket cost is 0 (`BLIND_RL_DMG` 0) | Small |
| `TRICK_P` and the scripted opponents | lobber .267, watcher .2, holder .2 | The scripted runner's persona | Yes: plain rounds never come (whole games 0.65 + moments 0.35 = 1), `--bot-p 0`, runners 0 | None a frame |
| `--ahead default` | | The brain's readout of the enemy's next place and his target | A lesson on a readout (not pay, not his actions); **its meaning shifts**: see below | Its loss |

What still names "the enemy" or "the places": none of the rules above writes or reads target 8 or 9 to 16 for his seats. Two meanings
shift under `FIGHT`, reported for the planning session to judge (neither is a rule acting on him):
- **His input "his intention is the enemy"** (column 495 of list 22b, read by the brain and the hands) is `intent == 8`. A fight order
  sets his target to 8 whatever its kind, so this input is 1 on all four options (back off included), not only when he hunts. The new
  20 columns say which kind; their token opens over updates 0 to 20. Until then a practice "back off" shows the hands "headed for the enemy".
- **The `--ahead` readout's "target" class** learns the enemy's target; class 8 now means "the enemy is on one of the four fight options",
  and the places' classes (9 to 16) no longer occur.

## Tests

Every test below was run in the build; none is claimed that was not.

| Test | What | Result |
|---|---|---|
| The simulator off = bit-identical (`ident_sim.py`) | Fixed-seed replays, the tree before 2.2b against the new, the same actions, every switch off | **Identical**: Blood Run 800 frames; Blood Run and Hektik 1,200 frames x 16 seats; the 1,108 old columns equal, the 20 new 0. `FIGHT=1`, `NEAR_MISS=1` at `NEAR_PAY` 0, no order: old inputs and pay identical |
| The generated module (`tools/ffa_check.py`'s check) | `duel_env_ffa.py` against `duel_env.py` at two players | Equal (observations, pay, done) over 1,500 frames x 48 seats on Blood Run (`testlab.bsp` is missing in `data/maps`, so not on the test map) |
| The legs test (`legs_test.py`) | His own network walks each option (the table above) | Every option reached or met on 57% to 97% of dealt trips by map (the lowest: going at him on Blood Run and Campgrounds) |
| The start answers as 2.2a's update 90 (`ident.py`, run inside `start.ps1 -DryRun`) | 2.2a's update 90 plays Blood Run and Toxicity (1,200 frames x 32 seats, `FIGHT=1`), every frame recorded; both networks replay it from the same seeds | **0 of 1,075,200 actions differ, 0 keep columns differ**; the largest logit difference 0.00014, memory 0.00008 |
| The numpy reader as the trainer's torch (`tests.py unit`) | The fight network's scores and the one list's masks, numpy (`fightnet.np_forward`, the checks' player) against torch | Equal ("the one list: numpy as torch") |
| `tests.py unit` | The mixture's probability (three cases); the one list's masks; the one number's bias; the pay split's parts sum to the frame's pay (largest difference 1.5e-8 over 600 frames); near misses paid in a run; a fight start (11 made, each: one seat fresh with the machine gun and the gauntlet, one frag added); the near miss graded (f 0.556 at 200 units), zero-sum, capped, nothing for a burst that hurt; the win scale's arithmetic | **ALL PASSED** |
| `tests.py live` | Every new live name refused out of its range and accepted at its ends, by the trainer's own reader (`PRACTICE_P` 0 to 0.3, `FGT_BIAS` -30 to 30, `H2_WADD` 0 to 1, `FGT_GATE` -30 to 0, `NEAR_PAY` 0 to 10, `NEAR_OUT` 151 to 600, `FGT_G` 0 to 1, `FGT_W` 0 to 5) | **ALL PASSED** |
| `tests.py guard` | The judge's guard (above) | **ALL PASSED** |
| `live_accept` (`accept_22b.py`, in `start.ps1`) | The start's `live.json` and every file the ramp may write, `FGT_BIAS` at -30, 0, 30, under 2.2b's command's environment | **PASS** x 3 |
| `check_settings` | Against 2.2a's command (47 names allowed, listed in `start.ps1`: every one a change of the card or a start value made equal to the live value) and against 2.2a's update 90 (`DESC_OX` allowed: the rater's) | **PASS**, both |
| `start_values.py` | The command's start values against the start's `live.json`, name by name | **PASS**, 53 names |
| `start.ps1 -DryRun` | Every check and every file of the start, into `data/sim_runs/scratch_22b_dryrun`, the trainer not started | **Passed**: the command, both settings checks, the live file, start values, live accept, convert, layout, norm, `ident.py`, the league (9 anchors, 8 snapshots, the control). Its start file equals the trials' (weights identical, the norm to 1e-13) |
| The CPU smoke (`smoke.py`, `_c` and again `_d` after the last trainer changes) | 2.2b's command made small (2 simulators x 8 matches), 10 updates with the stages ten times faster, then a resume for one more update | **PASSED**: practice 0 → 0.12, the token -30 → -12 → 0, the near pay; the one number decided once at update 6 (-4.68) and the plain-words report (all four options "THE HANDS CARRY IT OUT" on this tiny sample); the list and the weapon hand-over over updates 6 to 10; the resume reloads the optimizer and **2 of 5 league files with their own fight network**; the pull's proof 1e-5 to 0.002 including the list's frames; no non-finite number |
| The full-size trials | Below | Passed, with the optimizer finding |
| A check on a save (`tools/duel_eval.py`) | A full-size trial's save (dials open) against 2.2a's update 90, Blood Run, 4 games of 2 minutes, the watcher's own arguments | Ran to the end (it found and I fixed a bug in my own change to `duel_eval.py`, `dump_eval.py`, `ws_eval.py`: a variable named as the seat clock) |

## The full-size trial

Three trials at the run's own size (30 simulators x 168 matches, 360 pieces, the graphics card; `smoke.py` with `SMOKE_FULL=1`, 2 updates
each, from the start file, the league of two converted anchors and the control):

| Trial | Dials | Optimizer | Update 1: KL, clip, the target's KL, the weapon's KL | Update 2: the same | Minutes an update (1, 2) |
|---|---|---|---|---|---|
| 1 | all open (practice 0.12, near pay 5, token open, FGT_G 1, FGT_W 1, H2_WADD 0) | cold, full rate 1e-4 (the warm-up did not work then: below) | 0.246, 0.40, 0.221, 0.883 | 0.063, 0.28, 0.044, 0.373 | 9.3, 7.3 |
| 2 | the start's (shut) | cold, the warm-up (1.1e-5, 1.6e-5) | 0.014, 0.09, 0.011, 0.044 | **0.050, 0.15, 0.046, 0.296** | 9.2, 7.3 |
| 3 | the start's (shut) | **2.2a's update 100 optimizer carried** (`keep/opt_u100.pt`), the same warm-up | 0.0036, 0.03, 0.0004, 0.0018 | **0.0043, 0.04, 0.0006, 0.0023** | 9.7, 7.6 |

2.2a for comparison (warm optimizer, full rate): KL 0.027 to 0.030, the weapon's 0.015, the target's 0.004. In every trial: no part
turned off, no non-finite number, no flag; the pull's proof (`pull.first_err`) 0.0002 to 0.0006 at the start's dials (0.0031 at update 2
with every dial open); the fight network's sizes (scores 0.10 to 0.13, weapon 0.16 to 0.17, first layer 9.3 to 9.5, last 0.10 to 0.17) and
the one list's (the item side 23, the hands' weapon rows 12 to 13) all far under 40. Practice in trial 1: him 904 dealt, 0.81 reached or met;
cut 792, 0.96; angle 785, 0.95; away 9,013, 0.98 (away is valid nearly always, the others only with the enemy out of view); the fight side won
the list at 34% of decisions (scores still near equal, no bias set).

**Memory** (a monitor every 20 s over trials 1 and 2 and the start of 3; before: 18.3 GB of RAM in use, commit 32.9 GB, the card 1.4 GB):
the card's memory at most 14.1 GB of 16; RAM in use at most 50.3 GB (17.7 GB free at the least); commit at most 81.2 of 111 GB.

**Minutes an update**: 7.3 to 7.6 after the first (2.2a: 6.6; the card hoped for nearer 2.1d's 5.3 with the rater out). The rollout
200 to 240 s, the learning 214 s (its first update 355 s). The fight network's lesson takes about 1 s, the tracker's pass odds about 1.3 s;
the rest is the item picker's and the hands' learning as in 2.2a.

**The optimizer at the start.** The card starts cold with a warm-up because no optimizer was kept at update 90. Measured: cold, even at a
tenth of the rate, the second update's weapon KL is 0.30, 20 times 2.2a's (likely the cold Adam: its first steps are about the rate's
size for every weight whatever its gradient; not traced further). With 2.2a's update-100 optimizer carried (its
moments are the gradient's scale, 10 updates on; the trainer carries them over to the widened first layer and starts the new token's
fresh), the KL is at 2.2a's level. `start.ps1 -Opt <file>` carries one; without `-Opt` it starts cold as the card says. **For the planning
session to decide** (my recommendation: `-Opt data\sim_runs\duel_gru_2_2a\keep\opt_u100.pt`).

## 2.2a's consistency failure at update 153 (traced)

The pull's proof (`pull.first_err`: the largest difference, at the learner's first pass, between the log-probability of the played
target as played and as the learner computes it) over 2.2a's 156 updates: median 0.00092, 90th percentile 0.0031, 16 updates above
0.003, one above 0.01: update 153, 0.0186. At update 90 it was 0.00214. The worst frame of update 153 was frame 93 of its piece: not a
reading, no reset, no new draw, no change of target; the target "the enemy"; -3.454 as played against -3.435 recomputed; the 99.9th
percentile of that update 0.00046; one frame of 10,752 over 0.01. Nothing points at wiring: it reads as rounding drift between the
rollout's frame-by-frame memory and the learner's whole-sequence pass under large scores (the hands' about 14.5, the pull 9.2) and
the overlap. 2.2b carries the same machinery: the smoke's and the trials' values are in "Tests". The ramp flags a value over 0.003 and
calls one over 0.01 MAJOR.

## Decisions taken in the build (unspecified details, decided from the card's intent)

| Detail | Decided | Why |
|---|---|---|
| Which cut-off place | Among the 16 candidates he reaches before the enemy, the one the tracker's pass odds favour most (the larger of its 2 s and 4 s odds) | The card: "cut-off moves to the prediction that works"; the tracker's pass odds learn without the outlook (the rater's own score of them left with it) |
| When him, cut and angle are dealt in practice | Only with the enemy out of view (away whenever valid) | A trip toward an enemy in view ends at once by contact; practice is for reaching the spot. Away is therefore dealt far more often (trial 1: 9,013 against 785 to 904) |
| A practice trip's end | The spot, a new sighting after he was out of view, 4 s, or death; on its frames his own target choice is not read (`b_live` 0: no lesson of his target head on a pick he did not make); the fight network learns from it as its own exploration | The card ("until the spot, contact, or 4 seconds"). Consequence: **an angle trip ends on arrival and never holds there**; holding is then his own choice |
| The weapon on a practice trip | Even among the weapons he owns, no gauntlet | The card ("a weapon he owns, each equally likely") |
| What the fight network's weapon scores learn from | The practice trips' dealt weapons only (their advantage) | On his own and list trips the weapon is the hands' pick; teaching the nudge from it would copy the hands (rule 13) |
| The league seats | Dealt practice (change 6) and their snapshot's own fight network when it has one; **no weapon nudge** | The nudge is the learner's dial (`FGT_W`); a league file's own is not replayed |
| "The enemy" and the places shut | On the trips whose list has the four (the coin at `FGT_G`); open on the others | So the item picker's choices fade out with `FGT_G`, as the card's 60 to 100 ramp says, not all at once |
| The one number (`FGT_BIAS`) | The mean of the trainer's `bias_to_set` over updates 51 to 60 (the bias at which the four's share equals what "the enemy" and the places hold), written once | The card's change 10 |
| The fight network's forecasts | GAE on its ticks (the head's gamma and lambda to the tick's power), two forecasts (damage and frags; the win part x `--win-scale-fight`), each part's advantage brought to spread 1, then added | The card ("each brought to the same size before they are added") |
| The win scales | `max(1, sum of the flat part's sizes / the win part's)` over the start's games | The card's "at least the size of their flat pay"; both measured at 1 |
| The warm-up | `--lr-warm 60` minutes from a new `--lr-warm-start 26519` (2.2b's start in the lineage's minutes): about 9 updates from a tenth to the full rate | **`--lr-warm` counts from `--fade-start`, which 2.2b keeps at 2.2a's 7214: alone it would have done nothing** (found in trial 1, where the rate was 1e-4 from the first update). A gotcha for CLAUDE.md, not mine to write |
| `--fade-start 7214` | As 2.2a ran it | Every fade it drives ended long ago |
| The league | 2.2a's 9 anchors, its own last 8 snapshots up to update 90 (minute 26,519), the control (2.2a's update 90) as `anchor_22a90.pt`, all converted to list 22b (`league_22b.py`) | The league as it stood at the start's save |
| The controls | The checks against 2.2a's update 90 (the start, `keep/control_22a90.pt`); every fourth against 2.1d's end (`keep/control_21d.pt`) | The card; 2.1d's end is the long-term control as in 2.2a |
| A resume | The league files with a fight network (2.2b's own snapshots) play with it after a restart (`SNAP_FN` reloaded from their files) | Found in the build: a resume had them play the item picker alone |
| The near miss | Counted per burst of a rocket, grenade or plasma ball that damaged nobody; graded from the splash radius (rockets 120, grenades 150, plasma 20) to `NEAR_OUT`; the budget refills one full near miss a second | The card's change 13; splash sizes from the simulator (MECHANICS) |
| A fight start | The survivor keeps the moment's place, stack and weapons and gets the frag; the other gets the spawn's health, no armor, the machine gun (100 rounds) and the gauntlet at a spawn by the measured rule | The card's change 7 |
| The plugins and the export | Refuse a 2.2b network (`sim/export_duel.py`: REFUSED) | The card ("a server cannot play this network until ...") |

## Every setting

Made by `settings_table.py` (2.2b's `train.cmd` with `aim2_env.cmd`, the start's `live.json` as `start.ps1` makes it, 2.2a's command, 2.2a's last `live.json`). "Plays" is the live file's value where it sets the name (marked "(live)"), else the command's. "Differs": **yes** = plays differently from 2.2a's last values; "written only" = the command's text differs but 2.2a's live file already played 2.2b's value. A name both commands leave unset is not listed (the simulator's default plays in both).

| | name | 2.2b's command | plays in 2.2b | 2.2a's command | played in 2.2a (its last live.json) | differs |
|---|---|---|---|---|---|---|
| set | AIM2 | 1 | 1 | 1 | 1 |  |
| set | AIM2_CAP_ECC | 2.8 | 2.8 | 2.8 | 2.8 |  |
| set | AIM2_CAP_SLIP | 2.1 | 2.1 | 2.1 | 2.1 |  |
| set | AIM2_C_ECC | 0.06 | 0.06 | 0.06 | 0.06 |  |
| set | AIM2_C_SLIP | 0.023 | 0.023 | 0.023 | 0.023 |  |
| set | AIM2_E0 | 0 | 0 | 0 | 0 |  |
| set | AIM2_FLINCH | 1 | 1 | 1 | 1 |  |
| set | AIM2_FOCUS | 1 | 1 | 1 | 1 |  |
| set | AIM2_FOCUS_GAIN | 0 | 0 | 0 | 0 |  |
| set | AIM2_FOCUS_SIG | 1.0 | 1.0 | 1.0 | 1.0 |  |
| set | AIM2_S0 | 5 | 5 | 5 | 5 |  |
| set | AIM2_SPLIT | 1 | 1 | 1 | 1 |  |
| set | AIM2_SPLIT_W | 1 | 1 | 1 | 1 |  |
| set | AIM2_W | 1 | 1 | 1 | 1 |  |
| set | AIM3 | 1 | 1 | 1 | 1 |  |
| set | AIM3_FIX_TAU | 0.05 | 0.05 (live) | 0.05 | 0.05 (live) |  |
| set | AIM3_LEAD | 1 | 1.0 (live) | 0 | 1.0 (live) | written only |
| set | AIM3_PURSUIT_GAIN | 1.0 | 1.0 (live) | 1.0 | 1.0 (live) |  |
| set | AIM3_PURSUIT_TAU | 0.125 | 0.125 (live) | 0.125 | 0.125 (live) |  |
| set | AIM3_RELOAD | 0 | 0.0 (live) | 1 | 0.0 (live) | written only |
| set | AIM3_SIZE_A | 0.39 | 0.39 (live) | 1 | 0.39 (live) | written only |
| set | AIM3_SIZE_B | 0.355 | 0.355 (live) | 0 | 0.355 (live) | written only |
| set | AIM3_W | 1 | 1.0 (live) | 0 | 1.0 (live) | written only |
| set | AIM_LEVEL | 3 | 3 | 3 | 3 |  |
| set | AMMO_PACKS | 0 | 0 | 0 | 0 |  |
| set | ARENA_ROOMS | yard | yard | yard | yard |  |
| set | ARENA_SETS | mg | mg | mg | mg |  |
| set | ARENA_STACK | 0 | 0 | 0 | 0 |  |
| set | ARMOR_COST | 1 | 1 | 1 | 1 |  |
| set | AUTO_HOP | 1 | 1 | 1 | 1 |  |
| set | AUTO_SWITCH | 1 | 1 | 1 | 1 |  |
| set | AWARE_LOG | 1 | 1 | 1 | 1 |  |
| set | BIG_ONCE | 1 | 1 | 1 | 1 |  |
| set | BIG_PICK | 0.10 | 0.10 | 0.10 | 0.10 |  |
| set | BIG_PICK_SEQ | 0.10,0.06,0.05 | 0.10,0.06,0.05 | 0.10,0.06,0.05 | 0.10,0.06,0.05 |  |
| set | BLIND_BRAIN | 1 | 1 | 1 | 1 |  |
| set | BLIND_FIRE_W | 0 | 0 | 0 | 0 |  |
| set | BLIND_PLACES | 150 | 150 | 150 | 150 |  |
| set | BLIND_RL_DMG | 0 | 0 | 0 | 0 |  |
| set | BLIND_RULE | 1 | 1 | 1 | 1 |  |
| set | BRAIN_READ | 1 | 1 | 1 | 1 |  |
| set | COLLECT_FIGHT_P | 0 | 0 | 0 | 0 |  |
| set | CONTACT_FREE | 1.0 | 1.0 (live) | (unset) | 1.0 (live) | written only |
| set | CONTEST_P | 0.10 | 0.10 | 0.10 | 0.10 |  |
| set | CONTROL_TRUTH | 1 | 1 | 1 | 1 |  |
| set | COST_FIRE_W | 0 | 0.0 (live) | (unset) | 0.0 (live) | written only |
| set | COST_JERK_W | 0 | 0.0 (live) | (unset) | 0.0 (live) | written only |
| set | DESC_OX | (unset) | (unset) | 1 | 1 | **yes** |
| set | DMG_ENEMY_ONLY | 1 | 1 | 1 | 1 |  |
| set | DODGE_G | 1.0 | 1.0 (live) | 0 | 1.0 (live) | written only |
| set | DODGE_IN | 1 | 1 | 1 | 1 |  |
| set | DQ_JUMP_MS | 50 | 50 | 50 | 50 |  |
| set | DQ_PICK_Z | 51 | 51 | 51 | 51 |  |
| set | DQ_WADE | 0.75 | 0.75 | 0.75 | 0.75 |  |
| set | DRIFT_DELAY | 50 | 50 | 50 | 50 |  |
| set | DRIFT_IN | 0 | 0 | 0 | 0 |  |
| set | DRIFT_MIN | 2 | 2 | 2 | 2 |  |
| set | DRIFT_SIGMA | 0 | 0 | 0 | 0 |  |
| set | DRIFT_SMOOTH | 0.1 | 0.1 | 0.1 | 0.1 |  |
| set | DRIFT_TAU | 0.15 | 0.15 | 0.15 | 0.15 |  |
| set | DRIFT_WEBER | 0.10 | 0.10 | 0.10 | 0.10 |  |
| set | DRILL_MIX_P | 0.7 | 0.7 | 0.7 | 0.7 |  |
| set | DROPS | 1 | 1 | 1 | 1 |  |
| set | DUEL_QL | 1 | 1 | 1 | 1 |  |
| set | EMERGE_IN | 1 | 1 | 1 | 1 |  |
| set | EN_STACK | 1 | 1 | 1 | 1 |  |
| set | FIGHT | 1 | 1 | (unset) | (unset) | **yes** |
| set | FIGHT_START_P | 0.20 | 0.20 | (unset) | (unset) | **yes** |
| set | FIGHT_TRUTH | 1 | 1 | 1 | 1 |  |
| set | FIRE_QL | 1 | 1 | 1 | 1 |  |
| set | FLINCH_MAX | 0.7 | 0.7 | 0.7 | 0.7 |  |
| set | FLINCH_PER_DMG | 0.012 | 0.012 | 0.012 | 0.012 |  |
| set | FLINCH_TAU | 0.3 | 0.3 | 0.3 | 0.3 |  |
| set | GAME_P | 0.65 | 0.65 | 0.65 | 0.65 |  |
| set | GL_QL | 1 | 1 | 1 | 1 |  |
| set | GONE_BELIEF | 1 | 1 | 1 | 1 |  |
| set | GPU_MEM_FRACTION | 0.90 | 0.90 | 0.90 | 0.90 |  |
| set | GROUND_SENSE | 1 | 1 | 1 | 1 |  |
| set | HAND_BAND | 1 | 1 | 1 | 1 |  |
| set | HB_BETA | 0.5 | 0.5 | 0.5 | 0.5 |  |
| set | HB_FC | 4.0 | 4.0 | 4.0 | 4.0 |  |
| set | HEAR_FIX | 1 | 1 | 1 | 1 |  |
| set | HEAR_QL | 1 | 1 | 1 | 1 |  |
| set | HF_DIR | 3 | 3 | 3 | 3 |  |
| set | HF_HUM_TAU | 1 | 1 | 1 | 1 |  |
| set | HF_LOUD | 0.1 | 0.1 | 0.1 | 0.1 |  |
| set | HF_STEP_DT | 0.3 | 0.3 | 0.3 | 0.3 |  |
| set | HF_STEP_SPEED | 150 | 150 | 150 | 150 |  |
| set | HF_UP | 15 | 15 | 15 | 15 |  |
| set | HIGH_PAY | 0 | 0 | 0 | 0 |  |
| set | HOP_CHAIN | 0 | 0 | 0 | 0 |  |
| set | HOP_PAY | 0 | 0 | 0 | 0 |  |
| set | HOP_QUIET | 1 | 1 | 1 | 1 |  |
| set | HOP_QUIET_HEARD | 1 | 1 | 1 | 1 |  |
| set | HOP_QUIET_NEAR | 300 | 300 | 300 | 300 |  |
| set | HUNT | 1 | 1 | 1 | 1 |  |
| set | INTENT_HOLD | 8 | 8.0 (live) | 8 | 8.0 (live) |  |
| set | INTENT_SWITCH | 0 | 0 | 0 | 0 |  |
| set | ITEM_BELIEF | 1 | 1 | 1 | 1 |  |
| set | ITEM_DECAY | 0.002 | 0.002 (live) | 0.002 | 0.002 (live) |  |
| set | ITEM_DROP | 1 | 1 | 1 | 1 |  |
| set | ITEM_FLAT | MH:0.35,RA:0.30,YA:0.15 | MH:0.35,RA:0.30,YA:0.15 (live) | MH:0.30,RA:0.30,YA:0.15 | MH:0.35,RA:0.30,YA:0.15 (live) | written only |
| set | ITEM_PT_HI | 0.002 | 0.002 (live) | 0.002 | 0.002 (live) |  |
| set | ITEM_PT_LO | 0.004 | 0.004 (live) | 0.004 | 0.004 (live) |  |
| set | ITEM_RATE_AR | 0.002 | 0.002 (live) | 0.002 | 0.002 (live) |  |
| set | ITEM_RATE_HP | 0.0025 | 0.0025 (live) | 0.0025 | 0.0025 (live) |  |
| set | ITEM_RUN_P | 0 | 0 | 0 | 0 |  |
| set | JRUN_SPEED_BACK | 1 | 1 | 1 | 1 |  |
| set | JUDGE_ITEMS | docs\runs\2.2\2.2b\items_22b.json | docs\runs\2.2\2.2b\items_22b.json | docs\runs\2.2\2.2a\items_22a.json | docs\runs\2.2\2.2a\items_22a.json | **yes** |
| set | JUDGE_PAY | 1 | 1 | (unset) | (unset) | **yes** |
| set | JUMPS | 1 | 1 | 1 | 1 |  |
| set | JUMP_ALL | 1 | 1 | 1 | 1 |  |
| set | JUMP_COST | 0 | 0 | 0 | 0 |  |
| set | JUMP_EVERY | 1 | 1 | 1 | 1 |  |
| set | JUMP_FAR_P | 0.5 | 0.5 | 0.5 | 0.5 |  |
| set | JUMP_FOCUS |  |  |  |  |  |
| set | JUMP_FOCUS_W | 4 | 4 | 4 | 4 |  |
| set | JUMP_KEEP_CLOSED | 1 | 1 | 1 | 1 |  |
| set | JUMP_OPEN | bloodrun:1,3,5,7,8,9,11,13,26;aerowalk:3,5,10,18,20,21;lostworld:1,2,3,6,7,10,11,12,14,15,16,17,18,21,22,23,24;sinister:1,2,7,10,13,14,18,19,20,22,27;furiousheights:5,7,8,11,14,16,18,21,22,23,24,26,28;battleforged:1,5,6;campgrounds:1,3,15;hektik:1,2,3,5,9,10,12,13,14;toxicity:1,2,3,4,8;cure:1,5,7,9,13,14 | bloodrun:1,3,5,7,8,9,11,13,26;aerowalk:3,5,10,18,20,21;lostworld:1,2,3,6,7,10,11,12,14,15,16,17,18,21,22,23,24;sinister:1,2,7,10,13,14,18,19,20,22,27;furiousheights:5,7,8,11,14,16,18,21,22,23,24,26,28;battleforged:1,5,6;campgrounds:1,3,15;hektik:1,2,3,5,9,10,12,13,14;toxicity:1,2,3,4,8;cure:1,5,7,9,13,14 | bloodrun:1,3,5,7,8,9,11,13,26;aerowalk:3,5,10,18,20,21;lostworld:1,2,3,6,7,10,11,12,14,15,16,17,18,21,22,23,24;sinister:1,2,7,10,13,14,18,19,20,22,27;furiousheights:5,7,8,11,14,16,18,21,22,23,24,26,28;battleforged:1,5,6;campgrounds:1,3,15;hektik:1,2,3,5,9,10,12,13,14;toxicity:1,2,3,4,8;cure:1,5,7,9,13,14 | bloodrun:1,3,5,7,8,9,11,13,26;aerowalk:3,5,10,18,20,21;lostworld:1,2,3,6,7,10,11,12,14,15,16,17,18,21,22,23,24;sinister:1,2,7,10,13,14,18,19,20,22,27;furiousheights:5,7,8,11,14,16,18,21,22,23,24,26,28;battleforged:1,5,6;campgrounds:1,3,15;hektik:1,2,3,5,9,10,12,13,14;toxicity:1,2,3,4,8;cure:1,5,7,9,13,14 |  |
| set | JUMP_OVER_ANY | 3 | 3 | 3 | 3 |  |
| set | JUMP_OVER_PAY | 0.5 | 0.5 | 0.5 | 0.5 |  |
| set | JUMP_PAST_PICK | 1 | 1 | 1 | 1 |  |
| set | JUMP_RUNUP | 420 | 420 | 420 | 420 |  |
| set | JUMP_RUN_P | 0 | 0 | 0 | 0 |  |
| set | JUMP_SKIP | aerowalk:16 | aerowalk:16 | aerowalk:16 | aerowalk:16 |  |
| set | JUMP_SOLID_FIX | 1 | 1 | 1 | 1 |  |
| set | JUMP_VARY | 1 | 1 | 1 | 1 |  |
| set | JUMP_WEIGHT | 1 | 1 | 1 | 1 |  |
| set | JUMP_W_CAP | 0.25 | 0.25 | 0.25 | 0.25 |  |
| set | JUMP_W_DROP | 0.8 | 0.8 | 0.8 | 0.8 |  |
| set | JUMP_W_FLOOR | 0.3 | 0.3 | 0.3 | 0.3 |  |
| set | KEY_RATE | 8 | 8 | 8 | 8 |  |
| set | KNOCK_NOW | 1 | 1 | 1 | 1 |  |
| set | KNOCK_QL | 1 | 1 | 1 | 1 |  |
| set | KNOW_PAY | 0.25 | 0.25 | 0.25 | 0.25 |  |
| set | LAVA | 1 | 1 | 1 | 1 |  |
| set | LEGS | 1 | 1 | 1 | 1 |  |
| set | LEGS_EVERY | 4 | 4 | 4 | 4 |  |
| set | LEGS_IN | 1 | 1 | 1 | 1 |  |
| set | LEGS_KEEP | 0.9 | 0.9 | 0.9 | 0.9 |  |
| set | LEGS_LOOK | 1 | 1 | 1 | 1 |  |
| set | LEGS_NET | data\sim_runs\move_v17_look\policy.npz | data\sim_runs\move_v17_look\policy.npz | data\sim_runs\move_v17_look\policy.npz | data\sim_runs\move_v17_look\policy.npz |  |
| set | LEGS_OFF | 2 | 2 | 2 | 2 |  |
| set | LEGS_TURN_ADD | 1 | 1 | 1 | 1 |  |
| set | LEVEL_PULL | 1.0 | 1.0 (live) | (unset) | 1.0 (live) | written only |
| set | LG_DEAF | 1 | 1 | 1 | 1 |  |
| set | LG_QUIET_COST | 0 | 0 | 0 | 0 |  |
| set | MID_START_P | 0 | 0 | 0 | 0 |  |
| set | MISSILE_POINT | 1 | 1 | 1 | 1 |  |
| set | MOTOR_BASE | 0.05 | 0.05 | 0.05 | 0.05 |  |
| set | MOTOR_NOISE | 0.10 | 0.10 | 0.10 | 0.10 |  |
| set | NEAREST | 1 | 1 | 1 | 1 |  |
| set | NEAR_MISS | 1 | 1 | (unset) | (unset) | **yes** |
| set | OPENBLAS_NUM_THREADS | 1 | 1 | 1 | 1 |  |
| set | OPENINGS | 1 | 1 | 1 | 1 |  |
| set | OPEN_SILENT | 1 | 1 | 1 | 1 |  |
| set | OUT_LIVE | 1.5 | 1.5 | (unset) | (unset) | **yes** |
| set | OVERTIME | 1 | 1 | 1 | 1 |  |
| set | PACE_PAY | 0 | 0 | 0 | 0 |  |
| set | PAY_SPLIT | 1 | 1 | 1 | 1 |  |
| set | PERCEPT_SIGMA | 0.9 | 0.9 | 0.9 | 0.9 |  |
| set | PERCEPT_SPEED | 0 | 0 | 0 | 0 |  |
| set | PERCEPT_SPEED_MAX |  |  |  |  |  |
| set | PERCEPT_TAU | 0.15 | 0.15 | 0.15 | 0.15 |  |
| set | PREAIM_PAY | 0.05 | 0.05 | 0.05 | 0.05 |  |
| set | PREFIRE | 1 | 1 | 1 | 1 |  |
| set | PROJ_FIX | 1 | 1 | 1 | 1 |  |
| set | PROJ_NOTICE_MS | 100 | 100 | 100 | 100 |  |
| set | PROJ_READ_MS | 100 | 100 | 100 | 100 |  |
| set | PROJ_SEE | 1 | 1 | 1 | 1 |  |
| set | PRO_ITEMS | 1 | 1 | 1 | 1 |  |
| set | PRO_JSTART_MAXLEAD | 80 | 80 | 80 | 80 |  |
| set | PRO_JSTART_P | 0.5 | 0.5 | 0.5 | 0.5 |  |
| set | PRO_JUMP | 1 | 1 | 1 | 1 |  |
| set | PRO_START_P | 0.15 | 0.15 | 0.35 | 0.35 | **yes** |
| set | PRO_WAYS | 1 | 1 | 1 | 1 |  |
| set | PRO_WEAPON | 1 | 1 | 1 | 1 |  |
| set | PYTHONFAULTHANDLER | 1 | 1 | 1 | 1 |  |
| set | QL_FLOAT | 1 | 1 | 1 | 1 |  |
| set | QL_FWD | 0 | 0 | 0 | 0 |  |
| set | QL_JUMP | 1 | 1 | 1 | 1 |  |
| set | QL_LAND | 1 | 1 | 1 | 1 |  |
| set | QL_MOVE | 1 | 1 | 1 | 1 |  |
| set | RAIL_FAR_HI | 800 | 800 | 800 | 800 |  |
| set | RAIL_FAR_LO | 500 | 500 | 500 | 500 |  |
| set | RAIL_FAR_PAY | 0.1 | 0.1 (live) | 0.12 | 0.1 (live) | written only |
| set | RAIL_START_LEN | 30 | 30 | 30 | 30 |  |
| set | RAIL_START_P | 0 | 0 | 0 | 0 |  |
| set | RAIL_START_YAW | 15 | 15 | 15 | 15 |  |
| set | RAIL_STREAK_CAP | 1 | 1 | 1 | 1 |  |
| set | RAIL_STREAK_PAY | 0 | 0 | 0 | 0 |  |
| set | RANGE_FIX | 1 | 1 | 1 | 1 |  |
| set | RANGE_TAU | 0.5 | 0.5 | 0.5 | 0.5 |  |
| set | RANGE_WEBER | 0.19 | 0.19 | 0.19 | 0.19 |  |
| set | RESPAWN_QL | 1 | 1 | 1 | 1 |  |
| set | RJ_CLEARED | 1 | 1 | 1 | 1 |  |
| set | RJ_FROM_JUMP | 1 | 1 | 1 | 1 |  |
| set | RJ_LOOK_CLEAR | 1 | 1 | 1 | 1 |  |
| set | RJ_LOOK_P | 0.5 | 0.5 | 0.5 | 0.5 |  |
| set | RJ_ONLY | aerowalk:1 | aerowalk:1 | aerowalk:1 | aerowalk:1 |  |
| set | RJ_TEACH | 1 | 1 | 1 | 1 |  |
| set | RJ_TEACH_PITCH | 68 | 68 | 68 | 68 |  |
| set | RL_AIM | 1 | 1 | 1 | 1 |  |
| set | RL_QL | 1 | 1 | 1 | 1 |  |
| set | RULE_CONTEST | 2 | 2 | 2 | 2 |  |
| set | RULE_HUNT | 50 | 50 | 50 | 50 |  |
| set | RULE_WALK | 1 | 1 | 1 | 1 |  |
| set | RUNNER_P | 0.30 | 0.30 | 0.30 | 0.30 |  |
| set | RUN_TEACHER | 0 | 0 | 0 | 0 |  |
| set | SENSE_MINOR | 1 | 1 | 1 | 1 |  |
| set | SHOT_COST | 0 | 0 | 0 | 0 |  |
| set | SHOT_MASK | 1 | 1 | 1 | 1 |  |
| set | SHOT_W | rl:0.5,gl:0,pg:0,rg:0.2,sg:0.5 | rl:0.5,gl:0,pg:0,rg:0.2,sg:0.5 | rl:0.5,gl:0,pg:0,rg:0.2,sg:0.5 | rl:0.5,gl:0,pg:0,rg:0.2,sg:0.5 |  |
| set | SMALL_ZERO | 1 | 1 | 1 | 1 |  |
| set | SM_FACE_DEG | 15 | 15 | 15 | 15 |  |
| set | SM_FACE_TAU | 0.5 | 0.5 | 0.5 | 0.5 |  |
| set | SM_ITEMS | 1 | 1 | 1 | 1 |  |
| set | SM_ITEM_SD | 0.75 | 0.75 | 0.75 | 0.75 |  |
| set | SM_PASS | 1 | 1 | 1 | 1 |  |
| set | SOLIDS | 1 | 1 | 1 | 1 |  |
| set | SPAWN_QL | 1 | 1 | 1 | 1 |  |
| set | SPAWN_TEACH | 1 | 1 | 1 | 1 |  |
| set | SPEED_LOS | 1 | 1 | 1 | 1 |  |
| set | SPEED_PAY | 0 | 0.0 (live) | 0.25 | 0.0 (live) | written only |
| set | SPEED_PAY_RUN | 0.4 | 0.4 | 0.4 | 0.4 |  |
| set | STACK_BARE | 0.25 | 0.25 | 0.25 | 0.25 |  |
| set | STACK_BARE_MAX | 1 | 1 | 1 | 1 |  |
| set | STACK_DIFF | 0 | 0.0 (live) | 0.7 | 0.0 (live) | written only |
| set | STACK_KEYS | 0 | 0 | 0 | 0 |  |
| set | STACK_LOW | 0 | 0 | 0 | 0 |  |
| set | STACK_PAY | 0 | 0 | 0 | 0 |  |
| set | STACK_TEACH | 1 | 1 | 1 | 1 |  |
| set | STACK_WPN | 0 | 0 | 0 | 0 |  |
| set | STAGGER_START | 1 | 1 | 1 | 1 |  |
| set | START_GUN_P | 0 | 0 | 0 | 0 |  |
| set | START_GUN_W | rl:0.5,pg:0.25,gl:0.25 | rl:0.5,pg:0.25,gl:0.25 | rl:0.5,pg:0.25,gl:0.25 | rl:0.5,pg:0.25,gl:0.25 |  |
| set | STUCK_STARTS | 1 | 1 | 1 | 1 |  |
| set | STYLE_BAND | 0 | 0 | 0 | 0 |  |
| set | STYLE_DMG | 0.5 | 0.5 | 0.5 | 0.5 |  |
| set | STYLE_P | 0 | 0 | 0 | 0 |  |
| set | SURPRISE_MS | 0 | 0 | 0 | 0 |  |
| set | TARGETS | 1 | 1 | 1 | 1 |  |
| set | TARGETS_FREE | 2 | 2 | 2 | 2 |  |
| set | TEACH_FREE | 0 | 0 | 0 | 0 |  |
| set | TEACH_KEYS_ONLY | 1 | 1 | 1 | 1 |  |
| set | TELEFRAG | 1 | 1 | 1 | 1 |  |
| set | TRACK_RACE | 1 | 1 | 1 | 1 |  |
| set | TRACK_TRUTH | 1 | 1 | 1 | 1 |  |
| set | TRACK_Z | 1 | 1 | 1 | 1 |  |
| set | TRICKS | 1 | 1 | 1 | 1 |  |
| set | TRICK_P | lobber:0.267,watcher:0.2,holder:0.2 | lobber:0.267,watcher:0.2,holder:0.2 | lobber:0.267,watcher:0.2,holder:0.2 | lobber:0.267,watcher:0.2,holder:0.2 |  |
| set | VEL_DELAY_MS | 200 | 200 | 200 | 200 |  |
| set | VEL_FIX | 1 | 1 | 1 | 1 |  |
| set | VEL_MIN | 30 | 30 | 30 | 30 |  |
| set | VEL_TAU | 0.3 | 0.3 | 0.3 | 0.3 |  |
| set | VEL_WEBER | 0.2 | 0.2 | 0.2 | 0.2 |  |
| set | WALK_FIX | 1 | 1 | 1 | 1 |  |
| set | WALK_NO_JUMP | 1 | 1 | 1 | 1 |  |
| set | WATCH_PAY | 0.03 | 0.03 | 0.03 | 0.03 |  |
| set | WEAPON_FREE | 1 | 1 | 1 | 1 |  |
| set | WEAPON_OWN | 1 | 1 | 1 | 1 |  |
| set | WIN_ADD | 0.33 | 0.33 (live) | (unset) | 0.33 (live) | written only |
| set | WIN_END | 1 | 1 | 1 | 1 |  |
| set | WIN_JUDGE | data\sim_runs\judge\judge_v060_wpn.npz | data\sim_runs\judge\judge_v060_wpn.npz | data\sim_runs\judge\judge_v060_wpn.npz | data\sim_runs\judge\judge_v060_wpn.npz |  |
| set | WIN_SHADOW | 1 | 1 | 1 | 1 |  |
| set | ZOOM_PERCEPT | 1 | 1 | 1 | 1 |  |
| arg | --acquire-ms | 225 | 225 | 225 | 225 |  |
| arg | --ahead | default | default | default | default |  |
| arg | --ahead-start | 17278.807862214246 | 17278.807862214246 | 17278.807862214246 | 17278.807862214246 |  |
| arg | --ahead-warm | 60 | 60 | 60 | 60 |  |
| arg | --anchor-p | 0.24 | 0.24 | 0.24 | 0.24 |  |
| arg | --arena-len | 180 | 180 | 180 | 180 |  |
| arg | --aux | 0.2 | 0.2 | 0.2 | 0.2 |  |
| arg | --aux-fresh | 5 | 5 | 5 | 5 |  |
| arg | --aux-heads | place,near | place,near | place,near | place,near |  |
| arg | --aux-measure |  |  |  |  |  |
| arg | --aux-tail |  |  |  |  |  |
| arg | --aux-trunk | 0 | 0 | 0 | 0 |  |
| arg | --aux-unseen |  |  |  |  |  |
| arg | --aux-warm | 0 | 0 | 0 | 0 |  |
| arg | --belief | 256 | 256 | 256 | 256 |  |
| arg | --belief-every | 8 | 8 | 8 | 8 |  |
| arg | --belief-lr-scale | 2.5 | 2.5 | 2.5 | 2.5 |  |
| arg | --bot-p | 0 | 0 | 0 | 0 |  |
| arg | --brain-fade | 0 | 1.0 (live) | 0 | 1.0 (live) |  |
| arg | --brain-human | data\sim_runs\brainppl\pack_demo | data\sim_runs\brainppl\pack_demo | data\sim_runs\brainppl\pack_demo | data\sim_runs\brainppl\pack_demo |  |
| arg | --brain-human-lanes | 1 | 1 | 1 | 1 |  |
| arg | --brain-human-mix | 1.0 | 1.0 | 1.0 | 1.0 |  |
| arg | --brain-human-open | 0 | 0 | 0 | 0 |  |
| arg | --brain-human-start | -1 | -1 | -1 | -1 |  |
| arg | --brain-human-w | 0.35 | 0.35 | 0.35 | 0.35 |  |
| arg | --btoken | 1 | 1 | 1 | 1 |  |
| arg | --btoken-delay | 60 | 60 | 60 | 60 |  |
| arg | --btoken-open | 240 | 240 | 240 | 240 |  |
| arg | --btoken-start | 17278.807862214246 | 17278.807862214246 | 17278.807862214246 | 17278.807862214246 |  |
| arg | --close-floor | 0 | 0 | 0 | 0 |  |
| arg | --close-minutes | 1 | 1 | 1 | 1 |  |
| arg | --control | 1 | 1 | 1 | 1 |  |
| arg | --control-every | 5 | 5 | 5 | 5 |  |
| arg | --control-hid | 64 | 64 | 64 | 64 |  |
| arg | --control-lr | 1e-3 | 1e-3 | 1e-3 | 1e-3 |  |
| arg | --control-src | belief,both | belief,both | belief,both | belief,both |  |
| arg | --control-start | %CTL_START% | %CTL_START% | %CTL_START% | %CTL_START% |  |
| arg | --control-warm | 60 | 60 | 60 | 60 |  |
| arg | --dmg-reward | 0.005 | 0.005 (live) | 0.0055 | 0.005 (live) | written only |
| arg | --dmg-taken-w | 0.9 | 0.9 (live) | 0.9 | 0.9 (live) |  |
| arg | --drill-weapons | rl,rl,rl,rl,pg,pg,gl,gl,sg | rl,rl,rl,rl,pg,pg,gl,gl,sg | rl,rl,rl,rl,pg,pg,gl,gl,sg | rl,rl,rl,rl,pg,pg,gl,gl,sg |  |
| arg | --ent-coef | 0.005 | 0.005 | 0.005 | 0.005 |  |
| arg | --ent-heads | 0,0,0.25,0.25,0.25,0,0.5,0,1,1,0.1,0.1,0,0 | 0,0,0.25,0.25,0.25,0,0.5,0,1,1,0.1,0.1,0,0 | 0,0,0.25,0.25,0.25,0,0.5,0,1,1,0.1,0.1,0,0 | 0,0,0.25,0.25,0.25,0,0.5,0,1,1,0.1,0.1,0,0 |  |
| arg | --env | duel_env_ffa22b | duel_env_ffa22b | duel_env_ffa20e | duel_env_ffa20e | **yes** |
| arg | --fade-start | 7214.898282571636 | 7214.898282571636 | 7214.898282571636 | 7214.898282571636 |  |
| arg | --fast-gru | 1 | 1 | 1 | 1 |  |
| arg | --fgt-g | 0 | 0.0 (live) | (unset) | (unset) | **yes** |
| arg | --fgt-gate | -30 | -30.0 (live) | (unset) | (unset) | **yes** |
| arg | --fgt-w | 0 | 0.0 (live) | (unset) | (unset) | **yes** |
| arg | --fight22 | 1 | 1 | (unset) | (unset) | **yes** |
| arg | --fight22-lr | 1e-4 | 1e-4 | (unset) | (unset) | **yes** |
| arg | --gamma | 0.999 | 0.999 | 0.999 | 0.999 |  |
| arg | --gate-from | -12 | -12 | -12 | -12 |  |
| arg | --gate-open | 0 | 0 | 0 | 0 |  |
| arg | --gate-start | 21009.47 | 21009.47 | 21009.47 | 21009.47 |  |
| arg | --group | 2 | 2 | 2 | 2 |  |
| arg | --h2-choice-warm | 10 | 10 | (unset) | (unset) | **yes** |
| arg | --h2-wadd | 1 | 1.0 (live) | (unset) | (unset) | **yes** |
| arg | --habit-kinds | pro:1,rg:1,rl:1 | pro:1,rg:1,rl:1 | pro:1,rg:1,rl:1 | pro:1,rg:1,rl:1 |  |
| arg | --habit-p | 0 | 0.0 (live) | 0 | 0.0 (live) |  |
| arg | --habit-push | 2 | 2 | 2 | 2 |  |
| arg | --head2 | 1 | 1 | 1 | 1 |  |
| arg | --head2-add | 1 | 1 | 1 | 1 |  |
| arg | --head2-cap | 0 | 0.0 (live) | 0 | 0.0 (live) |  |
| arg | --head2-chrono-lo | 1 | 1 | 1 | 1 |  |
| arg | --head2-ctrl-src | belief | belief | belief | belief |  |
| arg | --head2-gate | 0 | 0 | 0 | 0 |  |
| arg | --head2-l2 | 0.01 | 0.01 | 0.01 | 0.01 |  |
| arg | --head2-lam | 0.998 | 0.998 | 0.998 | 0.998 |  |
| arg | --head2-open | 0 | 0.0 (live) | 0 | 0.0 (live) |  |
| arg | --head2-pay | items_win | items_win | all | all | **yes** |
| arg | --head2-pg | 1 | 1 | 1 | 1 |  |
| arg | --head2-start | %H2_START% | %H2_START% | %H2_START% | %H2_START% |  |
| arg | --head2-wpg | 1 | 1.0 (live) | 1 | 1.0 (live) |  |
| arg | --held | 1 | 1 | 1 | 1 |  |
| arg | --held-g | 1 | 1.0 (live) | 0 | 1.0 (live) | written only |
| arg | --info-pay | 0 | 0 | 0 | 0 |  |
| arg | --intent-seek | 1.0 | 1.0 | 1.0 | 1.0 |  |
| arg | --intent-seek-minutes | 0 | 0 | 0 | 0 |  |
| arg | --intent-teach | 0 | 0.0 (live) | 9.13 | 0.0 (live) | written only |
| arg | --intent-teach-floor | 0.1 | 0.1 | 0.1 | 0.1 |  |
| arg | --intent-teach-minutes | 1643 | 1643 | 1643 | 1643 |  |
| arg | --item-loss | 0.5 | 0.5 | 0.5 | 0.5 |  |
| arg | --item-reward | 0 | 0 | 0 | 0 |  |
| arg | --kind-p | 1,0,0,0 | 1,0,0,0 | 1,0,0,0 | 1,0,0,0 |  |
| arg | --kl-heads | 10 | 10 | 10 | 10 |  |
| arg | --lab-p | 0,0,1 | 0,0,1 | 0,0,1 | 0,0,1 |  |
| arg | --lam | 0.98 | 0.98 | 0.98 | 0.98 |  |
| arg | --legs-door-lr-scale | 0.25 | 0.25 | 0.25 | 0.25 |  |
| arg | --legs-ent | 0 | 0 | 0 | 0 |  |
| arg | --legs-feat | 1 | 1 | 1 | 1 |  |
| arg | --legs-gate | 1 | 1 | 1 | 1 |  |
| arg | --legs-learn | 1.0 | 1.0 | 1.0 | 1.0 |  |
| arg | --legs-residual | 0 | 0 | 0 | 0 |  |
| arg | --loadout-p | 0,1,0,0 | 0,1,0,0 | 0,1,0,0 | 0,1,0,0 |  |
| arg | --long-gamma | 0.9998 | 0.9998 | 0.9998 | 0.9998 |  |
| arg | --long-ramp | 0 | 0 | 0 | 0 |  |
| arg | --lr | 1e-4 | 1e-4 | 1e-4 | 1e-4 |  |
| arg | --lr-end | 1.0 | 1.0 | 1.0 | 1.0 |  |
| arg | --lr-minutes | 1440 | 1440 | 1440 | 1440 |  |
| arg | --lr-warm | 60 | 60 | (unset) | (unset) | **yes** |
| arg | --lr-warm-start | 26519 | 26519 | (unset) | (unset) | **yes** |
| arg | --map | bloodrun,aerowalk,lostworld,sinister,furiousheights,battleforged,campgrounds,hektik,toxicity,cure | bloodrun,aerowalk,lostworld,sinister,furiousheights,battleforged,campgrounds,hektik,toxicity,cure | bloodrun,aerowalk,lostworld,sinister,furiousheights,battleforged,campgrounds,hektik,toxicity,cure | bloodrun,aerowalk,lostworld,sinister,furiousheights,battleforged,campgrounds,hektik,toxicity,cure |  |
| arg | --map-sense | (unset) | (unset) | 1 | 1 | **yes** |
| arg | --map-sense-init | (unset) | (unset) | data\sim_runs\space\mapsense_start.pt | data\sim_runs\space\mapsense_start.pt | **yes** |
| arg | --matches | 168 | 168 | 168 | 168 |  |
| arg | --max-updates | 1000 | 1000 | 1000 | 1000 |  |
| arg | --minibatches | 360 | 360 | 360 | 360 |  |
| arg | --minutes | 1440 | 1440 | 1663 | 1663 | **yes** |
| arg | --near-item-p | 0 | 0 | 0 | 0 |  |
| arg | --no-switch | 1 | 1 | 1 | 1 |  |
| arg | --opt-small-items | 1 | 1 | 1 | 1 |  |
| arg | --out-kinds | (unset) | (unset) | seg,ret,all8,win8,win5,segw,winit8 | seg,ret,all8,win8,win5,segw,winit8 | **yes** |
| arg | --out22 | (unset) | (unset) | 1 | 1 | **yes** |
| arg | --outlook | (unset) | (unset) | 1 | 1 | **yes** |
| arg | --plan | 1 | 1 | 1 | 1 |  |
| arg | --practice-p | 0 | 0.0 (live) | (unset) | (unset) | **yes** |
| arg | --pull | 1 | 1 | 1 | 1 |  |
| arg | --pull-g | 2 | 2.0 (live) | 0 | 2.0 (live) | written only |
| arg | --pull-h | 0 | 0 | 0 | 0 |  |
| arg | --react-ms | 125 | 125 | 125 | 125 |  |
| arg | --resume |  |  |  |  |  |
| arg | --rj-teach | 0 | 0.0 (live) | 0 | 0.0 (live) |  |
| arg | --rj-teach-trunk | 0.05 | 0.05 | 0.05 | 0.05 |  |
| arg | --rj-teach-warm | 120 | 120 | 120 | 120 |  |
| arg | --rule-fade | 1 | 1 | 1 | 1 |  |
| arg | --rule-fade-delay | 0 | 0 | 0 | 0 |  |
| arg | --rule-fade-open | 250 | 250 | 250 | 250 |  |
| arg | --rule-fade-start | %RF_START% | %RF_START% | %RF_START% | %RF_START% |  |
| arg | --run | duel_gru_2_2b | duel_gru_2_2b | duel_gru_2_2a | duel_gru_2_2a | **yes** |
| arg | --solo-self-drive | 1 | 1 | 1 | 1 |  |
| arg | --stack-p | 0 | 0 | 0 | 0 |  |
| arg | --steps | 384 | 384 | 384 | 384 |  |
| arg | --teach | 0 | 0 | 0 | 0 |  |
| arg | --teach-minutes | 100000 | 100000 | 100000 | 100000 |  |
| arg | --teach-trunk | 0.05 | 0.05 | 0.05 | 0.05 |  |
| arg | --teach-trunk-move | 1.0 | 1.0 | 1.0 | 1.0 |  |
| arg | --teach-warm | 0 | 0 | 0 | 0 |  |
| arg | --teacher | move_v17_look | move_v17_look | move_v17_look | move_v17_look |  |
| arg | --track | 0.3 | 0.3 | 0.3 | 0.3 |  |
| arg | --track-lr-scale | 5 | 5 | 5 | 5 |  |
| arg | --track-parts | pos:1,vel:0,band:0.5,hand:0.25,own:0.25 | pos:1,vel:0,band:0.5,hand:0.25,own:0.25 | pos:1,vel:0,band:0.5,hand:0.25,own:0.25 | pos:1,vel:0,band:0.5,hand:0.25,own:0.25 |  |
| arg | --track-warm | 0 | 0 | 0 | 0 |  |
| arg | --track-z | zone:0.5,spd:0.25,dir:0.25 | zone:0.5,spd:0.25,dir:0.25 | zone:0.5,spd:0.25,dir:0.25 | zone:0.5,spd:0.25,dir:0.25 |  |
| arg | --track-z-warm | 0 | 0 | 0 | 0 |  |
| arg | --turn-add-open | 120 | 120 | 120 | 120 |  |
| arg | --turn-add-start | 9685.137113598985 | 9685.137113598985 | 9685.137113598985 | 9685.137113598985 |  |
| arg | --turn-add-to | 4.68 | 4.68 | 4.68 | 4.68 |  |
| arg | --weapon-teach | 0 | 0 | 0 | 0 |  |
| arg | --weapon-teach-minutes | 1000000 | 1000000 | 1000000 | 1000000 |  |
| arg | --win-scale-fight | 1 | 1 | (unset) | (unset) | **yes** |
| arg | --win-scale-items | 1 | 1 | (unset) | (unset) | **yes** |
| arg | --win-value | 1 | 1 | 1 | 1 |  |
| arg | --win-value-lr | 1e-3 | 1e-3 | 1e-3 | 1e-3 |  |
| arg | --win-value-start | %WV_START% | %WV_START% | %WV_START% | %WV_START% |  |
| arg | --win-value-warm | 60 | 60 | 60 | 60 |  |
| arg | --workers | 30 | 30 | 30 | 30 |  |
| live | BTOK_GATE_CAP |  | 1.0 |  | 1.0 |  |
| live | FADE_CAP |  | 1.0 |  | 1.0 |  |
| live | FADE_V |  | 0.0 |  | 0.0 |  |
| live | H2_COPY |  | 0.0 |  | 0.0 |  |
| live | H2_MIX |  | 0.0 |  | 0.0 |  |
| live | H2_PG |  | 1.0 |  | 1.0 |  |
| live | ITEM_PT_MIX |  | 1.0 |  | 1.0 |  |
| live | NEAR_OUT |  | 300.0 |  | (not in the file) | **yes** |
| live | NEAR_PAY |  | 0.0 |  | (not in the file) | **yes** |
| live | OUT_G |  | (not in the file) |  | 0.0 | **yes** |
| live | OUT_PICK |  | (not in the file) |  | 0 | **yes** |
| live | OUT_SRC |  | (not in the file) |  | 0 | **yes** |
| live | OUT_TRIAL |  | (not in the file) |  | 0.03 | **yes** |
| live | VALUE_WARM |  | 0 |  | 0 |  |
| live | WIN_GAIN |  | 1.0 |  | 1.0 |  |
| live | WIN_SHAPE_K |  | 0.0 |  | 0.0 |  |
| live | WIN_W |  | 0.0 |  | 0.0 |  |

440 names; 35 play differently from 2.2a's last values; 19 differ only as written (2.2a's live file had them at 2.2b's value)

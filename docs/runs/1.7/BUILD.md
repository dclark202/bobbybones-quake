# 1.7: the build of the combat order, as specced

The approved design is [README.md](README.md) (owner, 11-04 night: "largely looks right ... exactly the right idea"; 11-05: "You build
it as it was originally specced"; "it's all 1.7"; CLAUDE.md rule 10). This page is how each part of it is built in the code, on the one
branch `b17` (worktree `BobbyBones-17b`; 1.7a's keep choice is its first commit). Nothing of the design is left out or replaced by a
simpler stand-in. Where the design leaves a detail open it is decided here from its intent and marked **(detail)**; a real fork is
marked ❓ and goes to the owner.

**Marks:** ✅ built and tested · 🔨 built, its test running · ⏳ to build · ❓ owner's decision

**State (11-05 evening): every part built and tested; the start level-checked; the owner's decisions taken (below). The run starts on
his command in a new session ([1.7a/CARD.md](1.7a/CARD.md): how).**

## The parts

| # | Part (README) | Where | State |
|---|---|---|---|
| 1 | The keep choice at the head's tick, an arrival keepable (1.7a) | `sim/duel_env.py`, `sim/head2.py`, trainer, `tools/keep_init.py` | ✅ (commit 69c0c49: every test passed) |
| 2 | The map's numbers: sight between places, doorways, corridors, teleporters, the pros' spots, holds' lanes, ways out, the seconds of way | `tools/order_maps.py` -> `sim/order_maps/<map>.npz` (the ten maps; House of Decay and Dismemberment have no map files here) | ✅ |
| 3 | The candidates of every kind, their numbers, their points (S1, S2; the candidates table) | `sim/duel_env.py` (`COMBAT`: `order_feat`, `_cmb_points`, `_cmb_arrive`) | ✅ (`ident.py`: 20 checks; COMBAT on with the order never asked = 1.6a's simulator to the bit; asked: every kind chosen, followed, arriving; the group module the duel module's to the bit with it off and on) |
| 4 | The order: a kind, then a candidate by a pointer, then the way (S1, S2, S5) | `sim/head2.py` (`ok_*`, `op_*`, `order_scores`), trainer (drawn at the keep reading, learnt in the head's own term) | ✅ (numpy and torch the same; the trainer's identity and smoke tests) |
| 5 | The brain's new lesson: the odds he passes each candidate within 1, 2, 4 s (S3) | `sim/passodds.py`, trainer (`--pass-odds`, live `PASS_W`) | ✅ (the smoke: its Brier 0.162 -> 0.101 against a base rate of 0.151 in 80 small updates) |
| 6 | The hands read the point to watch or shoot and the order's kind | inputs `b17 order` (10), attention token `order` (left out while shut), `tools/order_init.py` | ✅ (the start answers as 1.6a's end: 0 of 3,200 actions differ; the attention part to the bit) |
| 7 | His weapon follows the order (the head's weapon part and its own inputs read the order's) | `sim/head2.py` (`W_OBS`, `OBS_SEL`), `tools/order_init.py` (`inp`, `winp` widened at zero) | ✅ |
| 8 | The head's push on the fire key, credited on the head's clock (S6) | `sim/head2.py` (`fsc`), trainer (`--head2-fpg`, live `H2_FPG`) | ✅ (the smoke: its scores off zero and growing) |
| 9 | The start fitted to the pros (S4) | `tools/order_pros.py` (label, fit) -> `docs/runs/1.7/1.7a/order_fit.json` | ✅ (120,000 moments of 600 duels; the start used: the fit with the new kinds 4.5 times rarer, the owner's "rarer start": level check 47%) |
| 10 | The checks' player, the check tools, the plugin and the export | `sim/test_suite.py`, `tools/duel_eval.py`, `ws_eval.py`, `dump_eval.py`, `plugins/netpass.py`, `plugins/duelbot.py`, `sim/export_duel.py` | ✅ (the plugin's forward pass the checks' to the bit with every part open: `plugin_parity.py`); a real server not tried (a server needs the owner's word) |
| 11 | The run's files, the ramp, the tests, the level check | `docs/runs/1.7/1.7a/` | ✅ the ramp (its test), the command (settings check against 1.6a's command and its end: only the named differences), the trainer's tests (`tests.py start`, `ident`, `smoke`: ALL PASSED), the level checks (the card) |

## 2. The map's numbers (offline, per map)

`tools/order_maps.py <map>` (the simulator's own collision, `qsim.lines`) writes `sim/order_maps/<map>.npz`:

| Table | What |
|---|---|
| `vis` | line of sight between every two points of the walking map at eye height (both standing): a bit matrix, points x points |
| `doors` | the doorways: the walking map's links that join two zones (`sim/zones/<map>.json`), gathered by zone pair and by place (detail: links within 192 units of each other are one doorway); its point, its two zones, the way through it, its width (traces across it at eye height), a corridor flag (detail: under 192 units wide) |
| `teles` | the teleporters' entrances and exits (the map's triggers) |
| `spam` | the spam points: the doorways, the corridors, the teleporter exits and the pros' blind-shot spots (`sim/pro_places/<map>_rl/_gl/_pg.json`, with where they fired from and their shares by weapon); for each, the points of the walking map with a line of fire to it within 1,500 units |
| `outs` | the ways out: the zones' middles, the doorways, the holding places, the health and armor items, the teleporter entrances |
| `hold_node` | each holding place's point (its lane: that row of `vis`) |
| `walk_t` | the seconds of way between every two points, on the walking map a DuelEnv with 1.6a's settings makes |

## 3. The candidates, their numbers, their points (the simulator, `COMBAT=1`)

At each keep reading (the frame after the head's tick), for every seat:

| Kind | Candidates | Its point to go to | Its point to watch or shoot | Arrived (keepable) | Ended (forced) |
|---|---|---|---|---|---|
| the target as chosen | today's 17 (nothing, the items, the enemy, the holding places): the hands' rows and the head's scores (S5) | as today (the hunt's way for the enemy) | the enemy: where he believes him; a holding place: the first of the brain's places 1, 2, 4 s ahead in its lane; an item: the brain's place 1 s ahead | as today; a holding place stood at, the enemy in view | as today |
| cut off | the brain's places 1, 2 and 4 s ahead (3) | that place, followed as the look-ahead moves | the same | within 300 units, or the enemy in view | no answer ahead (given up) |
| spam | of the spam points, the 8 nearest the brain's places ahead (detail: by the least distance to any of them) | the point with a line of fire to it nearest him by his way | the spam point | at the place to fire from, or the point in sight within 1,500 units | none left in range |
| break off | of the ways out, the 8 that the brain's places ahead do not see and that favour him most (detail: the enemy's seconds of way minus his; an item only up or due within his way) | the way out | the brain's place 1 s ahead (to keep him behind) | the place reached and out of the predicted sight | an item taken |

**Each candidate's numbers** (`order_feat`, 34 a candidate; the same for every kind, so one scorer reads them all): its kind (one-hot);
his seconds of way to it; the enemy's from where he believes him; the height from him; the range; its place in his facing; whether it
sees the brain's places 1, 2 and 4 s ahead, and is seen from his place (`vis`); doorway, corridor and its width, teleporter exit or
entrance, item (up, back in), holding place; the pros' use of it (their blind shots there by weapon, their holds there); the brain's
odds that he passes it within 1, 2, 4 s (part 5, written in by the trainer); valid. **The ways** (the third level): for his target's
three ways (`WAYS`), the way's seconds, the least distance of its next 30 points to the brain's places ahead, the share of them those
places see. **The situation** (14, for the kind): in contact, seen how long ago, his health and armor, the enemy's as he believes them,
whether there are places ahead and a belief, the range and height of the place 1 s ahead, his weapon (rockets, lightning, rail, other).

**The column** (`env.step`'s last): d + 2c + 4r as 1.7a, + 8 kind (0 the target as chosen, 1 cut off, 2 spam, 3 break off) + 32
candidate (0 to 7) + 256 q (the order asked). An order counts where his reading counts (the keep choice or a forced reading), on the keep
reading's frame.

**The hands' new inputs** (group `b17 order`, 10, a token kind `order` in the attention part): the kind (cut off, spam, break off:
one-hot), whether the point is one to shoot (spam), the point's direction from his crosshair (sine, cosine), its pitch, its distance, its
height, valid. Zero weights at the start. The token, while its gate is shut (-30), is left out of the attention altogether
(`sim/attn.py DROP_SHUT`, detail): the sums are exactly those of the network without it, so the start answers as 1.6a's end to the bit;
older kinds' shut tokens (the small items' in the league's b1.1 and v0.6.0 files) keep the e^-30 weight they were trained with.

## 4. The order (the head, `sim/head2.py`; the trainer)

- **The kind**: κ = W s + U ctx + b over (the target as chosen, cut off, spam, break off), a kind with no valid candidate masked. W starts
  at zero; U and b the pros' fit.
- **The candidate**: a pointer, one scorer for every candidate (AlphaStar's): g(s, x) = v · tanh(A s + B x + c), softmax over the kind's
  valid candidates. A starts at zero; B, c, v the pros' fit.
- **The way**: the same scorer on each of his target's three ways, added (x `PADD`) to the way output's scores.
- **The 17 targets**: the same scorer on each target's numbers, added (x `PADD`) to the head's target scores (S5: the hands' rows stay).
- Made at the keep reading **before that frame's outputs** (detail: the candidates are the simulators' after the tick's frame; the adds
  then play from the reading's frame on, as the learning step reads them: segment j's adds from reading j); drawn on the keep choice's
  stream; asked with the share `CMB_G` (live); learnt in the head's own clipped term with the target and the keep choice (λ 0.995, its
  two-minute value); no entropy bonus; no pay of its own (the b1 table, unchanged, no cost for firing). Everything starts at zero effect.

## 5. The brain's new lesson (S3)

`sim/passodds.py`: on the brain's state at the tick (a number: no gradient into the brain) and a candidate's place in his facing at the
tick, the odds that the enemy passes within 192 units across and 128 up (detail) of it within 1, 2 and 4 s. Graded in hindsight on the
rollout's truth, left out past the rollout's end, a death or a frag. Its answers go into the candidates' numbers. A lesson from update 0
(`--pass-odds 0.3 --pass-warm 0`: the weight of 1.6a's tracking lesson, `--track 0.3`; its own layers at the readouts' rate).

## 6. The hands' side

`tools/order_init.py add`: the inputs of `b17 order` appended (zero weights; statistics mean 0, spread 1), the attention token kind `order`
added with its gate shut (as `tools/targets_init.py`'s `widen_attn`; the layout's other entries, the brain's token among them, kept);
`order_init.py widen-league` gives every league file the same inputs, token and head inputs at zero (start.ps1 converts the anchors).
The optimizer's state carries over the widened inputs (1.6a's `--opt-small-items 1`: the encoder's columns, the token's marks and first
layer, and now the head's input layers `inp` and `winp`). The gate opens by the live dial `ORD_GATE` (detail: shut until the order opens,
then from -12 to 0 with it; never lowered; 1.6a's long-finished `--gate-open` line leaves it alone).

## 7. His weapon follows the order

The head's weapon part (1.5a) reads the order's inputs (`W_OBS` + `b17 order`; `winp` widened at zero) and the head's own inputs read
them (`OBS_SEL` + `b17 order`; `inp` widened at zero).

## 8. The fire push and its credit (S6)

`fsc(s)`: two scores held from tick to tick, `fadd` x them on the fire key's (live `FADD`). Its credit as 1.5a's weapon key: a share
`H2_FPG` (live) of the fire key's gradient in the head's own term (a lob pays 1 to 3 s after it leaves), the rest in the hands'.

## 9. The start fitted to the pros (S4)

`tools/order_pros.py label` (one process a map): the duel demos (`T:\quake-demos`, `tools/demodump`, read by `tools/pro_moments.py`: the
followed player exact, the enemy's entity, his stack worked out, the items' states), a moment every 0.5 s where pro_moments takes one and
the demo follows the same player alive for 4 s after it. The simulator (1.6a's settings, `COMBAT=1`) is put at each moment as its pro
starts are; his belief of the enemy is where he last saw or heard him in this stretch (his sight cone and a clear line; the enemy's shots,
pain sounds and pickups within the simulator's `EAR_RANGE`), known for the simulator's own `V02_KNOWN` (20 s); the brain's
places ahead are stood in for by that place moved on by the enemy's last seen speed for (seconds since + horizon), stopped at the first
wall (detail: the brain is not run on demos); the brain's odds are its start's, 0.1. The candidates and their numbers are the simulator's
own `order_feat`. **The labels** (detail, the first that holds): spam (a blind rocket, grenade or plasma shot of his in the next 0.5 s
landing 150 units or more away: the spam candidate nearest its landing within 300), break off (the enemy in view within 1 s; 3 s later no
clear line, 300 units further apart, no item taken: the way out nearest where he is then within 400; none of break off, cut off and chase
across a death of the enemy or a teleporter step in the window: a won fight's respawn far away is no break off), item (a target item taken within
4 s), hold (out of view, within 150 units of a holding place for 2 s), cut off (out of view, his belief known, 250 units moved in 2 s,
where he is then within 400 of where the enemy is 1, 2 or 4 s after the moment and 200 nearer to that than to the believed place: cut off
at that horizon), chase (the same move, 200 nearer the believed place), otherwise the target as chosen with no target named. 60 demos a
map, 12,000 moments a map kept.

`tools/order_pros.py fit`: the kind's U, b and the pointer's B, c, v by maximum likelihood with an L2 chosen on a held-out tenth of the
demos; W and A stay zero. A label whose kind has no valid candidate at that moment (the network cannot choose it there) is left out of the
kind's term (counted). Written into the start by `tools/order_init.py add --fit`. Then a full level check (the 2026-10-11 rule:
`level.py --cmb`, the fitted start at full share against 1.6a's end).

**What the fit came to (11-05):** on the held-out demos the kind's log loss 0.442 against 0.477 for the kinds' shares alone, the
candidate's 1.227 against 2.580 for an even choice; the kinds' predicted shares 87.7 / 3.6 / 4.7 / 4.1% (the target as chosen, cut off,
spam, break off) against 88.6 / 3.6 / 4.1 / 3.7% seen. Two fixes on the way: the pros' belief at first counted only sightings within 10 s
(23% of the spam labels had no candidate: 5% after), and break off counted a won fight's respawn far away (break off 7.7% of the pros'
moments before, 3.5% after).

**The level checks (200 games against 1.6a's end, each seat at its own share):**

| The start at full share | Result |
|---|---|
| the keep choice alone | **57.5%** (115-85): passes |
| the keep choice and the order, the order's token opened at once (its first layer untrained) | 12.0% (24-176): a wrong check, the run opens the token from -12 over updates 90 to 170 |
| the same, the token shut, the first fit (its labels before the two fixes) | 15.5% (31-169) |
| the same, the corrected fit | 32.0% (64-136): fails |
| the same, the new kinds 4.5 times rarer (`order_init.py add --kind-shift 1.5`) | **47.0%** (94-106): passes; **the start used** (owner, 11-05) |
| that start with the pointer's scores on his targets and way at full weight (`PADD` 1) / at 0.3 | at full weight 30.5% (61-139: fails); at 0.3 53.5% (107-93: passes) |

Why the order costs games at the start: neither the head nor the hands know it yet (the kind reads its context alone, his state's weights
at zero; the hands' order inputs at zero: on a spam order he goes to the spot and does not fire). The rarer start keeps the pros' shape
(which kind when, which candidate) at a quarter of the rate; the head raises it where orders win games.

## 10. The checks and the servers

The checks' numpy player (`test_suite.Policy`) holds the order's numbers after the head's state, reads the candidates the check tools
give it at its keep readings (`env.order_feat()`), writes the brain's odds in, draws the kind and candidate into the keep column, adds
the pointer's scores to the targets and the way, plays the fire push; the check tools pass the brain's places ahead to the simulator.
The plugins (`plugins/netpass.py`, `duelbot.py`) do the same, and run what only `step()` keeps (`_cmb_points` after `intend`,
`_cmb_arrive` with the hunt's arrivals); the export writes the pass readout. `plugin_parity.py`: the plugin's forward pass equals the
checks' to the bit with every part open. A real server: not tried (the owner's word first).

## 11. The run

One run, 1.7a, from 1.6a's end with its optimizer, everything at zero effect at the start (`start.ps1`: keep_init add and same, order_init
add --fit and same against 1.6a's end, the league converted, the settings checks). The owner's schedule (11-05 evening; `ramp_17a.py`): the keep choice (`KEEP_G`)
over updates 10 to 90; then the order (`CMB_G` 0 -> 1, `PADD` 0 -> 0.3, `ORD_GATE` -12 -> 0) and the fire push (`FADD` 0 -> 1, `H2_FPG` 0 -> 0.5:
half the trigger's credit on the head's clock, half kept by the hands) together over updates 90 to 170; the brain's lesson from update 0.
Until 21:00 on Friday 11-06 (`start.ps1 -Until "2026-11-06 21:00"`). The ways (`WAYS`): the next round.

## Decisions taken here from the design's intent (detail)

| | |
|---|---|
| Candidates a kind | cut off 3 (the horizons), spam 8, break off 8; the 17 targets; 3 ways |
| Doorway, corridor | links within 192 units one doorway; a corridor under 192 units wide |
| "Passes" (the brain's lesson) | within 192 units across, 128 up |
| The kind's context numbers | so the pros' start can be fitted without his head's state on demos (part 9); W on the state starts at zero |
| The pros' places ahead | the believed place moved on by the last seen speed (the brain is not run on demos) |
| The pros' labels | part 9's thresholds |
| When the order is made | at the keep reading, before that frame's outputs (the candidates are the previous frame's, after the tick) |
| The shut token | left out of the attention while at -30 (the start to the bit); opened by `ORD_GATE` from -12 |
| The pass lesson's weight | 0.3, 1.6a's tracking lesson's; from update 0 |
| A sum of two outputs (owner's rule, CLAUDE.md 11) | the fire key (the hands' rows + the head's push) and the pointer's scores on the targets and the way get `H2_L2`'s decay on both parts from the moment they are live; each part's size recorded (`cmb.sums`), the ramp flags one over 40 |
| The pros' belief on demos | sight and sound, 20 s (the simulator's own) |

## The owner's decisions (11-05 evening)

| | |
|---|---|
| 1 | The schedule: the lock first (`KEEP_G` 10 to 90), then the order and the fire push together (90 to 170) |
| 2 | The trigger's credit only halfway in this run (`H2_FPG` 0.5): "Ok that seems fair" |
| 3 | Every decision made from a sum of two learned outputs is regularized (CLAUDE.md rule 11) |
| 4 | The rarer start: "yes, the rarer start is good" |
| 5 | The length: "run it until 9pm tomorrow (friday 11/6)" |
| 6 | The ways (`WAYS`, the order's third level): "We can leave the routes for the next round" ([BACKLOG](../../BACKLOG.md) B-301: the ways' tables measured again with today's legs, his way choice opened from "the shortest", a level check). Built behind the switch; inert in 1.7a |
| 7 | `PADD`'s end value (0 to it over updates 90 to 170, then held; a fixed dial): the highest of 1 and 0.3 that passes the level check, else 0: **0.3** |
| 8 | Checks: "Run whatever checks you need, you don't need to ask me"; 1.6a's leftover processes stopped (owner) |

# 1.7c: the weapons, under the table (the plan, 2026-11-07 evening)

*Owner, 11-07 evening, after the push dial's play test ("didnt do fucking anything"): "I honestly don't care if his win rate against
himself plummets, playing against him is not enjoyable because he just only ever shoots LG." ... "go ahead and build what you think is
the right normalization for him in human play. It should address the cypher issues as well as my repeatedly stated problems with how he
plays. And also plan for me what additional training is needed to get him more towards that in practice ... another, focused, run to get
the weapons on track would be fine. I do not want to just keep running aimlessly though. We need to have a plan that is different from
what we've done so far, because it is clearly not working."*

**Started from:** 1.7a's update 90 (`keep/policy_end_17a.pt` + `opt_end_17a.pt`: the keep choice alone). Nothing of 1.7b.

## Why every run so far came out the same

Seven runs (v0.6, 1.3b, 1.4b, 1.5a, 1.6a, 1.7a, 1.7b) with different pay tables, teachers and heads all converged on the lightning gun
(in hand in view 67 to 73%; the pros 32%). Three causes, none of them a pay weight:

1. **The opponent is his own copy.** At equal aim the lightning gun is the best duel weapon inside 768 units: his lightning hits are
   level with the pros' (47 / 38 / 22% by range against 44 / 37 / 31%) and his rockets are *above* theirs (49% against 36%), and he still
   prefers lightning. Zoning a corridor with rockets has no value against a copy that learns to avoid it; a rail held at an angle has
   none against a copy that never has to come through it. In self-play, lightning *is* the right answer.
2. **Damage pay per point** (0.0055 a point since b1.2d) pays the steady weapon over the lumpy one at the same expected damage.
3. **The press is rare.** The weapon key is read one frame in four and is "keep" nearly always; a press of the rail at range happens
   in 0.1 to 0.2% of readings. PPO cannot explore what it never does, and every faded lesson (1.5b's prefit: rockets 24 → 37%, then
   back to 20% in training) returns to cause 1's equilibrium.

So: **a damage pay weighted by weapon** (the owner's question: pay lightning damage less) would move the mix by an amount we could
only find by more runs, and cause 1 would still pull toward lightning; **weaker lightning in the simulator** makes the simulator lie
(his lightning is already level with the pros'); **a bonus for rare events** (rocket hits, rail shots) fades back like every faded
lesson. None of them is a different plan. The different plan: **take the weapon choice away from the learner and give it to the
pros' table, in play and in training, and let him learn to fight with the weapon in his hand.** AlphaStar never let the policy drift
from the human prior (the standing KL to the human policy, the z statistic): this is that, in the plainest form that can be built today.

## Part 1 (built, 11-07 evening): the replace form of the dial, for play against people

[sim/weapon_dial.py](../../../../sim/weapon_dial.py) `choose()`: the owner's table *chooses* his weapon among rockets, the rail and the
lightning gun that he owns with ammunition, by his situation (the enemy noticed in view and the distance to where he last knew him; out
of view: travelling or zoning); the key's action is set to it in place of the network's (a press until it is in hand, then keep). The
choice is held: drawn again only when the situation's row changes and the weapon has been held 1.5 s (no flapping at a band's edge), at
once when the row gives the weapon in hand nothing (lightning at long range), or when it is no longer owned with ammunition. Where the
row allows none of the three he owns (a spawn's machine gun; lightning alone at long range) the network's own key stands. Fire, aim and
movement stay his. The same function runs in the checks (`tools/duel_eval.py --wpush 1 --wpush-form replace`) and on the servers
(`!weapons pros`; `WEAPONS=pros` in `tools/run/local_server.sh`); [exp/dial_parity.py](exp/dial_parity.py) proves the two paths choose
alike every frame, every press is of an owned weapon, every other output is drawn exactly as with the dial off (its own random stream).

| The owner's table | rockets | rail | lightning gun |
|---|---|---|---|
| in view, close (under 300 units) | 50% | | 50% |
| in view, medium (300 to 700) | 70% | | 30% |
| in view, long (700 and over) | 30% | 70% (where he has it) | |
| out of view (travelling, zoning) | 70% | 15% | 15% |

**Its check** (1.7a's update 90 under the table against the same save plain, 200 ten-minute games on ten maps, the u90 check's own
settings, with Cypher's measures; the tables in [DIAL.md](DIAL.md)): **69-131 (34.5%)**, frag share 44%; in hand in view rockets 53 /
rail 2 / lightning 40% (plain 18 / 1 / 74%; the pros 41 / 14 / 32%); frags by rockets 41% (plain 12%); kills 8.8 against 11.4 a player
a game. He holds what the table chose on 98 to 99% of frames (a switch in a median of one frame). Cypher's numbers do not improve
(out-stacked he dies 52% / escapes 45%, weaker side hits first 18%: worse than plain, rockets land later than lightning): the table
changes the weapon, not the fight; training under it is where they can move. **The rail stays at 2 to 3% because he does not own it**,
and on the long maps he lacks rockets with ammunition or the rail on 40% of his long-range frames in view, where the dial stands
aside and lightning stays: the items side is a limit the dial cannot move (below, the red team).

**Why this is the right normalization for human play:** against a person none of cause 1 holds (a person does come through the
corridor, does hold the angle), so the pros' mix is the right prior there; the table is deterministic where the push was a nudge; and
nothing of the network changes, so what he learnt about items, position and the keep choice is untouched. **Its limits:** his rail
timing and rocket prediction are the hands' as trained (rockets in hand 20% of the time, the rail 1%); he does not go and take the
rail (Campgrounds: never); and it is a hand-built rule on a choice the owner wants learnt (the way out is part 3).

## Part 2: 1.7c, the focused run: train under the table

**The one new thing:** his weapon is the table's on every seat of the league (his own, the snapshots, the anchor): `choose()` in the
trainer's rollout in place of the networks' weapon key, exactly as the checks and the servers run it (one function). The weapon key's
output gets no policy gradient and no entropy bonus (its mask zero in `head_masks`); instead it learns to **copy the table's choice**
(a cross-entropy to the dial's action on the frames the key is read, weight 0.1, standing): at the run's end the network's own key is a
fitted prior for the table, so that part 3 can hand the choice back with a standing KL and the dial can come off the servers.

| | 1.7c |
|---|---|
| Start | 1.7a's update 90 with its optimizer; the keep choice at its u90 setting with its output's loss masked (it drifted into flicker in 1.7a after update 130 and in 1.7b: it does not train further here); the order shut (`CMB_G`, `PADD`, `FADD` 0), the habit seats off (`HABIT_P` 0: the table replaces them) |
| The rule | `--wrule 1`: `weapon_dial.choose()` on every network seat in the rollout, after the draw (where `habit_push` adds today, `wkey_add`), a state per seat and the dial's own stream; `--wrule-imit 0.1`: the weapon head copies the dial's action (cross-entropy on key frames), no PG, no entropy on it; the checkpoint carries `wrule` so that every check plays him under the table (`duel_eval --wpush 1 --wpush-form replace`) |
| Opening | the share of lives under the table (live `WRULE_P`) 0 → 1 over updates 0 to 20 (the convention: shut at the start, opened with the checks reported; rule 6: the ramp only reports); the league's seats at the same share |
| Pay | **unchanged**: 0.0055 a damage point, a frag 1, `WIN_ADD` 0.33, `ITEM_FLAT` MH 0.30 / RA 0.30 / YA 0.15; no cost for firing. No weapon-weighted damage pay: with the choice the table's, a weapon weight on the pay has no target left to move |
| Length | 80 updates (about 6 h at 4.5 min an update), the owner's call (rule: ask him for the length); checks every 20 updates, 200 games |
| Checks | (a) against 1.7a's u90 **plain** (the yardstick: is the whole network, hands under the table, as strong as before?) and (b) against 1.7a's u90 **under the table** (the same hands and the same table: what the training added), both every 20 updates; the long-term control b1.2d's end plain every fourth; Cypher's measures (`tools/run/cypher_measure.py`) at updates 40 and 80; the panel: weapon in hand by situation, shots and hits a minute by weapon held, rail shots a minute with the rail in hand, rockets fired out of view (zoning), **the rail owned by map** (the one number the play-time rules could not move: the run's test of whether the head learns the rail's value) |

**The equilibrium it leads to.** Both copies carry the pros' mix, so the weapon is no longer a variable that self-play can collapse.
What remains to learn is how to fight with the weapon in hand: rocket prediction and splash on a dodging target, the rail's timing at
long range, dodging rockets and leaving rail lines, positions where the table hands him the better weapon (medium range with rockets,
long range with the rail). Against a copy that fires rockets, escaping a lost fight becomes possible where it was not against lightning
at 768 units: **Cypher's three numbers (an out-stacked Bobby dies 56% / escapes 38%, the pros 30 / 64%; the weaker side hits first 22%,
the pros 47%; fights with nobody dead 38 to 49%, the pros 64 to 71%) are downstream of the lightning equilibrium**, and this run is the
first in which they can move for a structural reason rather than a pay. They are measured, not assumed; if they do not move by update 80
the fight decision gets its own round (the break-off as a hard rule at play time is the next lever, not built here).

**What it will cost.** Against the plain u90 he will start where part 1's check puts him (the push at the pros' rocket share cost 16.5
points) and should climb as the hands learn the weapons; against himself the end may still be under 50% against plain u90: the owner has
said that is acceptable ("I honestly don't care if his win rate against himself plummets"). The number that matters is the play test.

### Red team

| Part | Hand-built or assumed | The measured alternative | Watch |
|---|---|---|---|
| The table | the owner's draft (the pros hold lightning most at medium range: 34 / 43 / 17% close / medium / long) | the pros' table by distance (`docs/pro_tables.json`), one line of code | if his medium-range fights die with rockets in hand against lightning, the table's medium row is the suspect, not the hands |
| The weapon choice as a rule | a hard-wired part on a choice the owner wants learnt | part 3 hands it back with a standing KL; the copy loss here is its fitted start | the copy loss's accuracy by update (should pass 90% on key frames) |
| No PG on the weapon key | assumed: a trained key would drift back to lightning (it did in every run) | a KL to the table instead of a mask (part 3) | nothing here: the key is not played while the rule is on |
| Fairness: his rockets | his rocket hits in self-play (49%, direct 20%) are above the pros' (36%, 10.5%), the target another Bobby | his rockets against people (the play test's `player_stats`), against the stand-in | if his rockets against people are over the pros', the aim limits per weapon style (aim2) are re-measured before any public server |
| The rail he does not own | **a play-time rule cannot fix it** (measured 11-07 evening, [DIAL.md](DIAL.md): sent for the rail from anywhere he dies, 9.5% against u90 plain; sent only when it is near and he is armed, ownership moves 33 → 35%). He owns the rail a third of the time on the rail maps and never on Campgrounds because in the lightning equilibrium the head learnt it is worthless (b1.1 to b1.2a: 26 → 1%). **This run is where that changes:** under the table the rail is used at range, so the head's target, trained with the win pay, has a reason to route by it. Rail owned by map is a measured target of the run (wanted: over 60% on the rail maps by update 80, Campgrounds over 30%) | if the head has not moved it by update 40: a price on the rail pickup in the item table (`ITEM_FLAT` prices health and armor only today): a hand rule in training, the owner's call | rail owned by map; rail in hand in view at long range; long-range frames with neither rockets nor the rail (the panel) |
| The fire key with the rail | the hands fired the rail in 0.1 to 0.2% of readings when they chose it | measured in part 1's check (rail shots a minute held) | a rail held and not fired is a fire-key problem for this run's gradient to fix; if it does not move by update 40, a fire push on the rail (1.7a's `FADD` machinery) is the fallback |
| Pay pathologies | the ledger as every run | | negative frags, sign flips, lopsided games |

### What has to be built (a day's work, measurable: it is one function already written, wired into the rollout and the loss)

1. `sim/train_duel_rnn.py`: `--wrule`, `--wrule-imit`, live `WRULE_P`; the state per seat; the mask and the copy loss; `wrule` in the
   checkpoint; the dial's stream its own (the play's draws untouched, as `HB_RNG`).
2. `tools/run/watch.py` and `panel.py`: a save with `wrule` is checked under the table (`--wpush 1 --wpush-form replace`), against both
   controls; the panel's weapon rows by situation and the rail's shots held.
3. `tests.py`: an identity check (`--wrule 0` = today's trainer, fixed seeds), the live file accepted (`WRULE_P` in `LIVE_RANGE`), ten
   updates on a scratch copy with the loss read per output (the copy loss must not move the shared layers: `--teach-trunk`'s pattern).
4. The card, the ramp, `start.ps1`, the settings check against 1.7a's reference.

## Part 3 (after 1.7c, not now): the choice handed back with a standing prior

The weapon key plays again with a KL to the table (or to the pros' table) that is **never faded** (AlphaStar's rule, the lesson of 1.7b's
`ORD_KL`: size it against the advantage gradient on a scratch copy before the start, and log the size every update). Then, and only
then, the head may learn to depart from the table where it wins: a rail taken because he is out-stacked at range, lightning kept at
medium range because the enemy is in the open. If the prior is sized right his mix stays near the pros' and the departures are the
strategy; if it is sized wrong he goes back to lightning, and the dial stays on the servers.

## Movement (1.8), the owner's other round

The owner wants Aerowalk's red armor, b2r and the rocket jumps ("at least one more training round with the advanced movement"). The
plan that is different from what was done before is already written: [design/TRICK_JUMPS.md](../../../design/TRICK_JUMPS.md) and the
[1.8a card](../../1.8/1.8a/CARD.md). What was done before was practice plus pay (b2r: 0 of about 2,700 tries; rocket jumps fired in
under 1 of 200 tries): exploration never found a success to learn from. What is different:

1. **Step 1, no training (can run beside 1.7c on the efficiency cores, on the owner's word with its mask):** each named jump replayed
   under his hand limits from the pros' inputs: made or not, and the margin. A jump his hands cannot make goes to the owner (a limit, the
   simulator, or the jump left out). This is a table, not a run, and it decides everything after it.
2. **A library of makes by search**, under his hands (the pros' run-ups seeded, a cross-entropy search over keys and mouse), kept varied
   (the owner's rule: the path, not one key sequence).
3. **Specialist teachers per family** (rocket jump, two-hop strafe, circle jump), trained backwards from the landing (the reverse
   curriculum: start near the landing, move the start back as it succeeds), imitation of the library faded to zero; the pass test with his
   hands (`tools/label_check.py`, 60% made from varied run-ups; the rocket jump on the game's physics too).
4. **Distilled into his legs branch off-line** (a separate block, 61 → 256 → 256 → 17, refitted alone), then one run with the ways carrying
   the jumps (B-301) and the pointer opening the way's choice: the head takes a jump way where it pays, nothing names a jump.

Order: 1.7c first (6 h), the movement step 1 measured beside it, the movement run from 1.7c's end. The weapons run does not touch the
legs branch and the movement run does not touch the weapon rule, so the two compose.

# Cypher's way of winning, set against Bobby

*2026-11-06 (owner): "do attempt to distill as much of his knowledge of the game towards our approach, not just for 1.7, but for the
entire bot as a whole"; "I want to try the weapon work again." The source: a video interview in which Cypher (the Quake Live champion) talks
about how he wins duels, the transcript read on 2026-11-06 (not kept in the repo). Bobby as he stands: 1.6a plus the keep choice, i.e. 1.7a's
result, its save of update 90 ([POSTMORTEM](../runs/1.7/1.7a/POSTMORTEM.md)). The items are in the [backlog](../BACKLOG.md) as B-302 to B-311; the checks ran the same day (below); the next run planned from it:
[1.7b](../runs/1.7/1.7b/CARD.md).*

**Marks:** ✅ known or decided · ⏳ to build · 🧪 to measure · ❓ owner's decision

## In short

Cypher wins on **stack math and timing**; Bobby fights on **aim and the present frame**. Three gaps found in the code line up with what he says:

| | The gap | Where it is |
|---|---|---|
| 1 | **The pay pays damage more than kills**: a kill on a 200/200 enemy pays about 2.2 frags of damage before the frag's 1, and a trade nobody wins pays both players. His criticism of the strong aimer who takes fights for damage, not kills, is in the pay | `--dmg-reward 0.0055`, live `DMG_TAKEN_W` 0.8 (b1.2d) |
| 2 | **The yellow armors have no timer anywhere**, and the brain's item race and the "in control" readouts count the mega and the red armor only. His advice on ZTN (our Blood Run) is to rotate the armors and time a yellow with the red | `docs/INPUTS.csv` (`memory`), `sim/ahead.py` (`race`), `sim/control.py` |
| 3 | **His weapon is a rare key press that the learner almost never tries**: the lightning gun two thirds of the time at every distance, the rail at range about one press in 55 s of that situation | the weapon key (hands) plus the head's weapon scores (1.5a) |

## His points

1. **Stack math decides fights, not aim.** Count your stack and the enemy's; fight with 30 to 50% more, avoid otherwise. Between aimers of
   similar level the bigger stack wins: 35% lightning with the stack beats 45% without it. A machine-gun chip before the fight (the enemy at
   −50) changes the math. Who will win is known before the fight starts.
2. **Timing when out of control is the most important skill.** Know every spawn; know where the player in control can overextend and where you
   will be faster than him in the next 5 seconds.
3. **Rotations, not fixation.** Not only the red armor and the mega: rotate the armors. He times one yellow and rotates the red with it.
4. **Out of control, try not to lose.** Skip the item that is about to spawn where the enemy will be; stay in corridors with a way out; do
   damage while backing off (the player who holds a spot hits more than the one who pushes into it); never give away a frag; wait for the
   impatient opponent to leave an item to come for you, and take what he leaves.
5. **Where and when, not how.** Everything is predicted and done ahead, about 10 seconds ahead; living in the moment means being lost for
   the next moves.
6. **Read the opponent.** His habits, learnt by heart; his items tell you his stack (a player who takes nothing is an easy target); his
   behaviour tells you the timings (a hurried rocket jump means the item spawns now); sound always.
7. **Good spots**: shortcuts to every item when in control; places where every way the enemy can arrive has an answer (down to the
   teleporter if he comes from above, rockets if he comes through the teleporter, away if he goes for the yellow).
8. **The map seen from above**, himself a point on it.
9. **The strong aimer's trap**: fights taken for damage and accuracy instead of kills; fights taken against a 200/200 because the aim feels
   better; pushing when he should wait and waiting when he should push.
10. **How he practises**: weaker opponents train the strong side (aim, not losing frags), the best ones the weak side (hard situations);
    one improves when punished; a small change can turn a player around.

## Bobby against each point

Numbers: 1.7a's updates 86 to 90 (training) and its panel at update 90; the pros' from the panel and `docs/pro_tables.json` (3,712 demos).

| His point | Bobby today | The gap |
|---|---|---|
| 1. Stack math | ✅ inputs: his health and armor, the enemy's stack as he believes it (`EN_STACK`), the pain sound's band; the brain's stack band reaches the head (`trk`); the win judge prices the stack edge (`sim/win_judge.py`) | 🧪 never measured whether he takes fights by the stack ratio; "break off", the head's way to decline a fight, was learnt away in 1.7a |
| 1, 9. Damage against kills | damage dealt 0.0055 a point, taken 0.0044 (0.8 of it); a frag 1 | ❌ the pay is positive-sum in trades and large beside the frag (below) |
| 2, 3. Timing, rotations | ✅ mega and red armor: "known to be taken" (he took it or heard it) and "how long ago" against its timer; the brain's race for both; "in control" = his share of their next spawns | ❌ no yellow armor timer (only "comes back in" while a yellow is his chosen target); race and "in control" leave the yellows out; the head reads only his own pickups' clocks (`v02 items`), the heard ones only through the brain |
| 4. Out of control | ✅ the keep choice redirects him on a sound or a hit (63% against 1.6a's end); the holding places; the brain's pass odds (Brier 0.080 against 0.186) | 🧪 nothing measures his deaths or damage while behind in stack; break off is gone |
| 5. Where and when | ✅ the brain's look-ahead (1, 2, 4 s), the pass odds | the order (cut off, spam) died of the causes in the postmortem, not for lack of a picture |
| 6. Reading the opponent | ✅ the brain, taught on people's games too; weapon habits on 30% of the league's lives | habits are weapons only, and over whole runs he scores the same against habit seats (53 to 55% of the frags) as against plain ones: the +2 push changes little |
| 7. Good spots | ✅ the pros' holding places and places as inputs; 1.7a's "ways out" candidates | no number per place for its exits |
| 10. Getting punished | ✅ matchmaking by difficulty (AlphaStar's PFSP, B-300) is built | ❌ off since 1.4b |

### His weapon, in numbers

| | rockets | lightning | rail |
|---|---|---|---|
| In hand with the enemy in view: Bobby (panel, u90) | 20% | 67% | 0.9% |
| ... the pros | 41% | 32% | 14% |
| His frags by weapon (u86 to 90) | 11% | 85% | 0.4% |
| Lightning in hand by distance, close / mid / far (u86 to 90) | | 67 / 71 / 69% | |
| The pros by distance (under 300 / 300 to 700 / over 700, share of the big three) | 59 / 36 / 21% | 34 / 43 / 17% | 7 / 21 / 62% |
| His hits (u86 to 90) | 52% | 39% | 43% |
| Damage a second at those hits | (splash counted in the hits: not comparable) | 6 × 20 × 0.39 ≈ **46** | 80 × 0.43 / 1.5 ≈ **23** |

A choice he has stopped making, flat by distance since at least v0.6.0 ([1.5a's card](../runs/1.5/1.5a/CARD.md)). 1.5a's head weapon scores did
not move it; the prefit to the pros (1.5b, never run) moved rockets 24 → 37% in view and won 56.5% against 1.3b's end untrained, **but stayed
flat by distance too**: the way the choice is made, not only its start, holds it flat. Two fidelity checks were never done: whether the game
lets a switch start during a reload (the simulator does not: `cool = max(cool, fire_cd + SWITCH)`, so a rail shot then the lightning gun is
1.5 + 0.425 = 1.9 s; B-37), and his hits by weapon against the pros' (1.5a's E5).

## The red-team: the damage pay

| | |
|---|---|
| What it pays | 0.0055 a point dealt, 0.0044 a point taken from the enemy (`DMG_TAKEN_W` 0.8, live since b1.2d), a frag +1, a death −1; win pay on top (`WIN_ADD` 0.33). 100 damage = 0.55 of a frag |
| Beside the frag | a kill on a fresh spawn (125 health) pays 0.69 of damage first; on a 200/200 (about 400 damage, the armor counted) about 2.2 |
| In self-play | a trade of 100 for 100 pays **both** players +0.11; frags, deaths, items and win pay are zero-sum, so this is the one part of the combat pay that does not depend on beating the enemy |
| Its equilibrium | both copies seek damage trades; the weapon with the steadiest damage in contact, the lightning gun (46 a second against the rail's 23), earns it best whether or not the fight is won; the rail's burst and the chip before a fight are worth only their points. Cypher's strong-aimer trap |
| Why it is 0.8 | b1.2d (owner, 11-02) lowered it from 1.0 to get him fighting, and it worked ("clearly engaging more in fights"). The keep choice and the win pay now carry part of that |
| The alternative | 1.0: zero-sum, damage worth only what it does to the fight's result through the frags and the win pay. Risk: a more passive game (v0.5.1, v0.6.1d) |
| 🧪 First | the pay ledger (`PAY_SPLIT`'s `dmg_dealt`, `dmg_taken`): the positive-sum part a game against the frags' and the win pay's size |

## The checks (2026-11-06, the owner: "Go ahead and start the checks for anything")

1.7a's update 90 in 80 self-play games on the ten maps with every frame recorded (`tools/run/cypher_measure.py sim`: `tools/duel_eval.py`'s
play with the checks' settings, the settings check against 1.7a's command, live file and save: the same but for one path written two
ways); the pros from their 1-second rows (`data/sim_runs/judge/pro_rows`) and their moments (`sim/pro_moments`). Records:
`data/sim_runs/duel_gru_1_7a/cypher/` (`stack_u90.txt`, `items_u90.txt`, `aim/`).

**Fights by the stack ratio** (effective stacks: health plus the armor it can use; a fight: damage either way, gaps of 2 s or less, 40 or
more in all; each fight seen from both sides; Bobby read once a second, as the pros' rows are; the enemy's stack in a demo is worked out,
so the pros' numbers are rougher):

| His stack / the enemy's | Bobby: wins / loses / nobody dies | The pros: wins / loses / nobody dies |
|---|---|---|
| under 0.67 | 6.0 / **56.0** / **37.9%** | 6.3 / **29.9** / **63.9%** |
| 0.67 to 0.9 | 13.9 / 40.1 / 46.0% | 10.7 / 19.1 / 70.2% |
| 0.9 to 1.1 | 25.6 / 25.8 / 48.6% | 14.5 / 14.9 / 70.6% |
| 1.1 to 1.5 | 39.9 / 14.4 / 45.7% | 19.2 / 10.7 / 70.0% |
| over 1.5 | 56.1 / 6.0 / 37.9% | 29.9 / 6.2 / 63.9% |
| the bigger stack (over 1.1) wins of the fights someone died in | 84.5% (frame by frame: 86.9%) | 77.5% |
| the weaker side (under 0.9) hits first | 22.2% of its fights | 46.9% |

**What it says.** Cypher's stack math holds in both: the bigger stack wins most fights that end in a death. The difference is the rest:
the pros' fights mostly end with nobody dead (64 to 71%), his with a death; and **out-stacked, he dies in more than half his fights where
the pros get away from two in three**. Behind, the pros also hit first twice as often as he does: chip damage from a spot they can leave.

| Measure | Bobby (u90) | The pros | |
|---|---|---|---|
| The trade bonus (B-306) | 339 damage a player-minute: 0.37 a player-minute of pay for trades, about a third of his frags' (1.16 a player-minute) | | zero-sum in 1.7b (owner) |
| The mega after its spawn | taken within 1 s 57%, a median 0.8 s; there 5% of the time | there 7% of the moments | timed |
| The red armor | within 1 s 46%, a median 1.2 s; there 17% | 11% | |
| The yellows | within 1 s 16%, a median 6.3 s; there 29%; taken by the player behind in stack 53% | 15% | partly by choice: a yellow does little for a full stack |
| His weapon with the enemy in view (opening / in contact / backing off) | lightning 62 to 67 / 72 to 77 / 68 to 73%; rockets 20 to 27 / 16 to 20 / 20%; the rail 1% in every phase and distance | | |
| His hits (B-303) | lightning 47 / 38 / 22% (under 250 / 250 to 500 / 500 to 750); rockets 49% (direct 20%); the rail 40 shots in 36 games | 44 / 37 / 31%; rockets 36% (direct 10.5%); the rail 37% | his rockets stronger than the pros', his lightning level |
| Lightning when he took 30+ damage in the last 0.5 s | 56% (206% of his calm rate) | 37% (113%) | both copies stand and trade |
| The game's switch during a reload (B-302) | the simulator: rail then lightning 1.925 s | the game: 1.975 s (every pair within two frames) | no gap |
| Starts with a player 100+ ahead (B-310) | | 45% of the pros' start moments | already there |

## The proposals

One new thing a round (the owner's rule of 10-24); each measured first where it can be. Where each takes from AlphaStar or Pluto is named.

| B | What | His point | From | First |
|---|---|---|---|---|
| **The weapon round** | | | | |
| B-302 ✅ no gap (the game waits for the reload too) | **The game's weapon switch during a reload** (`plugins/weaponlab.py`, a private server): if the game allows it, the combos he describes (the chip then the lightning gun, the rail then the lightning gun, a rocket then the finish) are dearer in training than in the game | 1, 4 | the simulator first | a private container while no one plays the local server; no training needed |
| B-303 ✅ his rockets above the pros', lightning level | **His hits by weapon and distance against the pros'** (1.5a's E5): if his rail sits further below the pros' than his lightning gun, the lightning gun is right for his hands and the question is the aim calibration | 9 | aim2: measure the pros | logs only, one core |
| B-304 ✅ out-stacked he dies twice as often | **The stack table**: fights started and won by the stack ratio, 1.7a's u90 against the pros (`tools/pro_moments.py` rebuilds the other player's stack in the demos); his weapon by the fight's phase (opening at range, in contact, backing off) | 1, 4 | | the efficiency cores (`0x3C3C`) |
| B-305 ⏳ | **The weapon as a held choice at the head's tick**: the weapon to hold (owned, with ammunition), read five times a second and held, credited on the head's clock; the simulator presses the key when it differs from the one in hand; the hands keep their own scores for the last-moment change (the sum regularized: rule 11). Today the rail at range is a press the learner tries about once in 55 s of that situation; a held choice is tried at its own rate. Started from the pros' hand by distance and situation (1.5b's fit), with **a KL to that fit kept through the run** as a live dial | 1, 5 | AlphaStar: the action type chosen first and the KL to the human policy through the whole of its learning (the 1.7a lesson); the target intention's own form | the design to the owner; then the build, a level check of its start |
| B-306 ✅ in 1.7b (owner) | **The damage pay zero-sum**: `DMG_TAKEN_W` 0.8 → 1.0, slowly | 1, 9 | the pay's equilibrium (the owner's rule) | B-304 and the ledger above |
| (B-300) | **Matchmaking by difficulty back on**: built, one dial | 10 | AlphaStar's PFSP | |
| **The rest of the bot** | | | | |
| B-307 ✅ the yellows' in 1.7b (owner) | **Every armor's timer as he can know it**: for each yellow (and the red and the mega, already there for the hands) known taken (he took it, heard it taken, saw its place empty), the seconds until it is back, with a person's counting error; into the hands and the head; the yellows into the brain's race and the "in control" readouts | 2, 3 | AlphaStar sees only what is in view and keeps the rest in memory; these are what a player keeps in his head, as the mega's and the red's inputs since v6 | 🧪 his armor pickups' order and arrival against the spawn, against the pros', Blood Run and Aerowalk first |
| B-308 ⏳ 1.7b | **Break off again, the 1.7a way fixed**: the hands' token open before the head may ask for it, a KL to the pros' fit, alone in its round | 4 | AlphaStar's KL; the postmortem's causes 1 and 2 | checked by his deaths a minute while behind in stack and the contested spawns skipped (B-304's measure) |
| B-309 ⏳ | **Route and timing habits in the league**: the weapon-habit push on the target scores of frozen league seats (a red-armor camper, a mega timer, a hunter, an item-leaver), drawn per life. Does the brain read the habit within a game, and does he take what the item-leaver leaves? | 4, 6 | AlphaStar's league, its strategies carried by opponents | small: the habit code of 1.5a |
| B-310 dropped (already there) | **Practice from behind**: the mid-game starts weighted toward his being out of control (the enemy 100 or more ahead in stack, the timings his) | 10 | | their share in today's starts first |
| B-311 ⏳ | **Ways out as map numbers**: for each place, its exits and the seconds to break the enemy's line of sight, for the head's candidates | 4, 7 | the map's numbers of 1.7's pointer | later |

## The order proposed ❓

1. The three measurements B-302 to B-304 and the ledger: no training (the efficiency cores 2 to 5 and 10 to 13; the game-server check in a
   second container, only while nobody plays the local one).
2. **The weapon round: B-305** (one new thing). B-306 and B-307 each a round of their own after it, as the measurements say.
3. B-308, then B-309 and B-310.

Where this sits against 1.8 (movement: the jumps, the ways, rocket jumps) is the owner's call.

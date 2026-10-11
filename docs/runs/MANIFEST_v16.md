# v16: the manifest, a first pass (2026-10-11; for the owner's review, nothing is built or started)

**Which run is which.** v14's end is on the public server. v15b is the legs run of the night
([REPORT_v15b.md](REPORT_v15b.md)); v15c is its continuation to noon with the weapon work
([MANIFEST_v15c.md](MANIFEST_v15c.md)). **v16 is the next model**: the network v16 starts from (v15b's end or v15c's,
the owner's choice after the noon report) with attention added. The model in full:
[../design/V16_ATTENTION.md](../design/V16_ATTENTION.md).

## 0. The owner's decisions so far (2026-10-11)

| | |
|---|---|
| What v16 is judged by | "Game awareness primarily. Also how much his movement begins to blend together the two styles fighting/moving we have now." |
| What he wants to see | spam with rockets, plasma and grenades used appropriately; aggressive or defensive by score and control ("in control = knows item times and has stack to contest them when they become available"); traps and weapon combinations ("rocket to disrupt movement, then LG on the midair enemy") |
| Whole ten-minute games with pay for the result | "Yes" |
| Training speed | "completely neutral"; four bots must fit on the rented server |
| Still his to decide | section 6 |

## 1. Three stages, each from the best network of the one before

| Stage | What is new | Length | It passes if |
|---|---|---|---|
| **0. Timing** (no training) | the model with random weights, timed for four bots on the PC and, on the owner's word, on the rented server | half a day | four bots under 8 ms a frame at the median, 12 ms at the 99th percentile (today's network: 1.0 ms; the budget for all of them: 15 ms) |
| **A. The things** | tokens for himself, the game, enemies, projectiles, items, places, his way, sounds; two attention blocks; an adapter into the GRU that starts at zero. Rounds and pay as the network he starts from had them | a day to build, a night to train | he is level with his start in the first check (he is the same network), not under it after the night, and with the adapter cut out he plays worse than with it: he uses it |
| **B. The game as a whole** | the event record; two new inputs (the time left in the game, how loud he has been); whole ten-minute games with pay for the result; rounds that begin ahead or behind late in a game; the yardsticks from the pros' demos | two days to build, two nights | section 3's numbers move toward the pros' and he beats stage A's end |
| **C. Targets and one way of moving** | the target output (the enemy or a place); his intention as a choice among the item tokens; his legs as a learning part of him, then the switch as a share | three days to build, two nights | spam and combination numbers move; his own movement outputs and his legs' come closer on the same frames; he beats stage B's end |

Stage A changes nothing he is paid for or shown: it only has to do no harm and be used. The wishes are stages B and C.

## 2. His rounds (stage B on; stage A keeps what he has)

| | Share of his playing time | Why |
|---|---|---|
| Games of two minutes, as now | 35% | fights, items, the league: what made him |
| **Whole games of ten minutes**, clock and score running, **the result paid at the end** | 25% | the only place where the score and the time left mean anything |
| **Late-game rounds**: three minutes, begun at 7:00 with a drawn score state (ahead by one to three, level, behind by one to three) and the stacks that go with it | 10% | ten minutes hold few late moments; these are where offense or defense is decided |
| Item runs, jump runs (as v15b), on the six maps and the four movement-only ones | 22% (15 and 7) | movement; less than now because his legs carry it |
| Weapon rounds: one-weapon rounds, lives that begin with a weapon, and (stage C) the knock-up room | 8% | "temporary just to introduce him to these weapons": turned down when the numbers of section 3 hold without them |

Opponents: his last eight selves; the last best network and the one before in a quarter of the rollouts (the standing
rule); the scripted lobber, watcher, holder and runner in 30% of his two-minute games.

## 3. What he is paid, and what he is measured by

Pay, new in stage B (everything else as now):

| | Proposal | Note |
|---|---|---|
| **The result of a whole game** | paid once at its end: a win worth about three frags, a loss costing the same, a draw nothing, scaled by the margin up to three frags (a 1:0 and a 10:2 are not the same game) | a starting proposal. What a ten-minute game pays him today in frags, damage and items is measured first, and the size is set against it: large enough to matter late, small enough that he does not stop fighting early. **A reward: the owner's to set** |
| The same frag pay in whole games | kept | without it the first eight minutes teach nothing |
| A second value output | his chance to win the game from here | not pay: it lets the first value output keep its meaning in two-minute rounds |
| Nothing for spam, combinations, walking, control | none | they are measured, not paid; a pay for a single behaviour only on the owner's word |

Measured at every check, beside the pros' numbers where the demos give them (section 5):

| Wish | Number |
|---|---|
| Game awareness | the share of mega and red armor returns he is at within two seconds, by himself and against the control; his believed item times against the true ones |
| Offense or defense | by state (ahead, level, behind; before and after 7:00): speed toward the enemy, fights he starts a minute, deaths a minute, his share of the big items |
| Control | the time he holds more than the enemy (health plus armor, big weapons) and what he does with it |
| Spam | shots with no enemy in view a minute by weapon; the share landing within a splash radius of the enemy's true place; damage and frags from them |
| Combinations and traps | frags within 1.5 seconds of his own rocket's knock, by the second weapon; frags by grenades and plasma fired at a place |
| Noise | the share of his travelling he walks while the enemy is within earshot and has not seen him; rail and lightning shots with no enemy in view |
| The blend | how far his own movement outputs are from his legs' on the same frames (stage C); his speed profile travelling and fighting |
| Still a duelist | against the control map by map, the stand-in on ten maps, real games against the game's Nightmare bot before and after |

## 4. Start, league, checks, stopping

- From the network the owner names after the noon report of 2026-10-11, at the settings it was trained with; the same
  size of run (24 simulators of 210 games, four movement-only ones) unless the card says otherwise. A token is cut out of
  the flat inputs inside the network, so the rollout stores only the new numbers on top (places, events, the two new
  inputs: about 230 beside 576, some 40% more). The stored inputs fill most of the card today: they go to half
  precision, or the run to about three quarters of its players. A dry run decides.
- The control in every check is the network he starts from; the adapter starts at zero, so the first check must be level.
- Stopped: under 45% against the control at two checks in a row, or a map ten points under at two checks.
- Before the real server: the plugins build the tokens with the simulator's own function, a recorded game beside the
  simulator's inputs, four Bobbys timed on a private server.

## 5. The pro demos in this run

1. **Stage B, first**: the score and the game clock read out of the demos (`sim/demo_dataset.py` leaves them out
   today); the yardstick numbers of section 3 for the pros, map by map (as `tools/speed_profile.py` did for speed).
2. **Stage B**: the places the pros fire at with no enemy in view, clustered a map: the list of place tokens.
3. **Stage B, to be tried on a side arm first**: the attention part and the event record learn on demo sequences to
   foretell what comes next in the demo (the enemy's next appearance, the next item taken, damage in two seconds).
   None of his outputs is trained on it.
4. **Stage C, on the owner's word**: the pros' choices by situation (which item, close or hold) as a fading teacher on
   his intention.
Never their mouse or trigger.

## 6. For the owner to decide

1. Which network v16 starts from: v15b's end or v15c's (the noon report).
2. The size of the pay for a game's result (section 3) and the shares of section 2.
3. Whether the late-game rounds may begin from drawn states, or only whole games count.
4. The pros' choices as a teacher (section 5, point 4): yes, no, or after the yardsticks are seen.
5. Timing on the rented server (stage 0): it runs a script there for a minute with nobody playing.
6. What trains meanwhile: nothing, or the network of point 1 continuing as it is while stage A is built.

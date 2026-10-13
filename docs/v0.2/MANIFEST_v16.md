# v16: the manifest, a first pass (2026-10-11; for the owner's review, nothing is built or started)

**Which run is which.** v14's end is on the public server. v15b is the legs run of the night
([REPORT_v15b.md](../legacy/REPORT_v15b.md)); v15c is its continuation to noon with the weapon work
([MANIFEST_v15c.md](../v0.1/MANIFEST_v15c.md)). **v16 is the next model**: the network v16 starts from (v15b's end or v15c's,
the owner's choice after the noon report) with attention added. The model in full:
[../v0.2/V16_ATTENTION.md](V16_ATTENTION.md).

## 0. The owner's decisions so far (2026-10-11)

| | |
|---|---|
| What v16 is judged by | "Game awareness primarily. Also how much his movement begins to blend together the two styles fighting/moving we have now." |
| What he wants to see | spam with rockets, plasma and grenades used appropriately; aggressive or defensive by score and control ("in control = knows item times and has stack to contest them when they become available"); traps and weapon combinations ("rocket to disrupt movement, then LG on the midair enemy") |
| Whole ten-minute games with pay for the result | "Yes" |
| Training speed | "completely neutral"; four bots must fit on the rented server |
| After playing v15c on the public server (13:20) | "much better than v14 was": plasma "a little but it was really good", "strong LG, very strong", "some rocket usage, could use more". "Biggest criticism: their paths are still predictable. I find them in the same 2 or 3 spots usually. And typically they're kind of 'weird' spots, like maintaining a low ground position, or stuck on the stairs in the yellow room" of Blood Run. "Leaning towards installing in them some amount of preference for high ground. Perhaps this should be a 'strength of position' token in attention, which then influences what weapon they are likely to chose." Movement: "more speed per jump, maintaining speed for longer; rather than just 'average speed'" |
| Still his to decide | section 6 |

## 1. Three stages, each from the best network of the one before

| Stage | What is new | Length | It passes if |
|---|---|---|---|
| **0. Timing** (done 2026-10-11) | the model with random weights, timed inside the game's image on the rented server with nobody playing (`tools/attention_timing_v16.py`) | done | four bots 7.0 ms a frame at the median, 8.4 at the 99th percentile (today's network 1.1); the bar was 8 and 12; building the inputs takes about 4 more of the 15 ms budget |
| **A. The tokens, with the new information** | tokens for himself, the game, his position (with the pros' weapon and strength for the spot), the enemy as seen, **the enemy as believed with his strength**, projectiles, items, **places**, his way, sounds; two attention blocks; an adapter into the GRU that starts at zero. No list of events. Rounds and pay as the network he starts from had them | two days to build, a night to train | level with his start in the first check (he is the same network), not under it after the night, and with the adapter cut out he plays worse: he uses it |
| **B. Targets, ways, the game as a whole** | the target output (an item, a place, the enemy's believed place, hold); the choice among up to three ways; the belief output; the time left and the noise he makes; whole ten-minute games with pay for the result; rounds that begin ahead or behind late in a game | three days to build, two nights | the numbers of section 3 move toward the pros' (first: blind rockets, the commonest way's share, closing by the enemy's state) and he beats stage A's end |
| **C. One way of moving** | his legs as a learning part of him, then seeing what he sees, then the switch as a share; a list of events (eight frequent, eight rare) if the numbers ask for it; the room for combinations | three days to build, two nights | his own movement outputs and his legs' come closer on the same frames; more speed for each jump in games; he beats stage B's end |

Second version (2026-10-11 evening), after the day's measurements: the list of events is out of the first build (on the pros' demos it foretold the next item and a just-lost enemy better and nothing else: [../v0.2/v16_event_record.md](v16_event_record.md)); the first stage carries the new information; a place as a target and the choice of way move to the second stage, because spam and routes are where he is furthest from the pros.

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
| Predictable or not | the share of his time in his eight most-used places and in the lowest third of the map; the share of his trips on the commonest way between two items; time standing; his height against the enemy in view |
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
7. High ground: the position token alone (he is shown it and learns what it is worth), or also a hit from above paid more (`HIGH_PAY`, built on 2026-10-09 and never used in a run).
8. Speed for each jump: a pay for speed gained from one hop to the next (approved in principle on 2026-10-10; the rule is shown first), or only his legs learning from the game's pay (stage C).
9. Several ways to a target (the way output of stage C): brought forward to stage B, since predictable routes are his main fault today?
10. His pay, his rounds and his opponents ([../v0.2/V16_TRAINING.md](V16_TRAINING.md), written on his question of
    2026-10-11): the second value estimate brought forward to stage A; an exploiter in his league and its share of the
    simulators; a frag paid by what it moves his chance of winning the game; the pros' choices as a standing prior
    (point 4 above); promotion by the scorecard beside the control.
11. A target that is never "nothing" (measured 2026-10-11, the log of 19:00): with no item due he has no target, his legs
    cannot carry him, and he stands on his own feet at 270 units a second, 13 to 23% of his time; it is also where the
    owner found him waiting in odd places. Proposed for stage B: with no item due the target is a place worth holding
    (from the pros' cells and holds), and his legs take him there.

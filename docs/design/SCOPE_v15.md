# v15: the scope (jumps, grenades and plasma, decisions)

Written 2026-10-10 for the owner, who is "inclined to fold them into the next run": what each of the three would change
in the simulator, the maps and tools, the network, the trainer, the checks and the servers. Nothing here is built
unless it says so. It replaces the note of 2026-10-09 (in the git history), whose parts on scripted opponents and on a
head that decides are carried over. His priority list ([PLAN.md](../PLAN.md)): strafe jumping and keeping speed;
rockets; plasma and grenades; then game awareness. Backlog: B-204, B-200, B-201 (jumps); B-189, B-202 (grenades and
plasma, opponents); B-191, B-190, B-188 (decisions).

## 1. Jumps: a gap course and the named jumps of the real maps

**What is there.** The test map has graded movement courses already (`tools/make_lab_map.py`: circle-jump gaps,
two-hop gaps, ramps and stairs, pillars, pads, drops, a climb) and a tool that copies a region of a real map into it. A
strafe-jumping teacher (`move_v14d`, a movement-only network) that reaches 359 units a second on Blood Run. The pros'
ways in the walking graph. Measured on 2026-10-10: Aerowalk's red armor is taken from 325 units away at 470 to 480
units a second, Blood Run's long gap from 420 units at 510; a walker's jump carries about 170.

**What is missing.** The walking graph is built by running and jumping from a standing start, so a gap that needs
speed is not a link in it: the teacher has no way across and labels nothing there, and the item rule either sends him
where he cannot go (Aerowalk's red armor until `RULE_WALK`) or never sends him.

| | Change |
|---|---|
| The list | `tools/pro_gaps.py`: every airborne link the pros take that a walker cannot, or that saves a second or more: take-off zone, landing zone, the speed they have, how often. Per map, as a table the owner strikes from and adds to. His list is the start: the bridge to the rail and the pillars on Campgrounds, the red armors of Aerowalk and Blood Run, the stairs to the yellow armor on Blood Run, the upper floor of Furious Heights, the red armor to the health bubbles on Sinister, the two boxes from the red armor to the mega on Toxicity. Campgrounds has ten demos: its jumps are set by hand from his names |
| The walking graph | `sim/build_nav.py`: a pass for speed links (a run-up, then a jump at 400 to 550 units a second), each with the speed it needs. The route field keeps three times a link: a walker's, a jumper's, the pros' |
| The test map | the named jumps copied in beside the graded gaps, each as a course with a start, a landing and a time. Two more kinds from the owner (2026-10-10): stairs taken with jump held, and a jump at a ledge that hooks onto it. Both are measured in the game first (`plugins/movetest.py`) and set beside the simulator (`QL_MOVE` has the game's step height; the rest is not checked) |
| The teacher | `sim/train_move.py`: goals across speed links, on the six maps, Campgrounds, Toxicity (owner, 2026-10-10: yes) and the test map's courses; lava priced so that Lost World's fault goes; Aerowalk's missing ways mended. A night on the processors. Its check per jump: does a player pressing only its labels arrive |
| Bobby's rounds | item runs that begin one step before a jump (a share of the item runs), with the teacher's labels; the teacher's labels by its best choice and not a sample if the pupil test says so (B-201) |
| Bobby's inputs | for the step ahead on his way: that it needs speed, the speed it needs, how far the take-off is, the gap's length and height: five inputs |
| The item rule | names an item behind a jump again when his own arrival rate there passes a mark in the pre-run check, map by map (`RULE_WALK` by item) |
| Checks | per jump: the teacher's pupil, Bobby alone, Bobby in a game; the same jumps on the real server as a card the owner can run too. Kept from v14: speed on his way in games, time fast in the air |

Held-out maps: with their jumps in the teacher's training, Campgrounds and Toxicity stay out of Bobby's duel training
and remain checks of his play there, no longer of his movement.

Risk: the simulator against the game at edges, stairs and ledges (measure first); a teacher with new labels moves the
whole network (a dry run as long as its weight takes to rise, the control in every check).

## 2. Grenades and plasma

**Why they are 0.0% of his time in every run.** Nobody uses them on him and he on nobody. Shots with no enemy in
view are priced, so firing into an exit is punished. He sees enemy grenades and plasma in view (36 inputs) and can lead
a plasma ball (six inputs), and has nothing for a grenade's arc. He never holds one long enough to find out.

| | Change |
|---|---|
| Prices | grenade and plasma shots free and the rule for fire with no enemy in view (`SHOT_W=gl:0,pg:0`, `BLIND_RULE=1`): back in v14's third start with the teacher's restart (owner, 2026-10-10: yes) |
| Opponents | the three scripted players into the simulator (built in a copy and measured, B-202): the lobber fires plasma and grenades into the far end of a teleporter or jump pad on his way, the watcher holds a post with the rail, the holder keeps the mega and the red armor. A share of the rounds that have the scripted item runner today. The lobber's timing first: its grenades and plasma make 2 to 17% of its frags |
| Rounds | one-weapon rounds with the grenade launcher and with the plasma gun (the trainer has them: `--kind-p`, `--drill-weapons`), a few per cent of the rounds, against the watcher on its post and the runner on its ways; some lives of normal games that begin with one of the two in hand. Skill before choice; no teacher on the weapon key in games (v14's second start) |
| Inputs | a grenade's arc: where one fired now comes down and where it is when it goes off, as the six lead inputs do for rockets and plasma: six inputs |
| The simulator | grenades measured again on a real server (`plugins/weaponlab.py`): bounce, fuse, speed, the push at one's own feet (650 units a second in the simulator, 277 measured: B-19) |
| The yardstick | `tools/pro_tables.py`: when the pros fire grenades and plasma: enemy in view or not, distance, height, at a teleporter's exit or a pad's landing. A table to set his use beside; a teacher only if the rounds above do not bring it |
| Checks | time in hand, shots and frags by both weapons, frags on an enemy not in view, damage he takes from them (does he still walk into an exit under fire: B-189) |

The shotgun "to a lesser extent": it comes with the one-weapon rounds; nothing else is planned for it.

Risk: the simulator's grenade is not the game's; one-weapon rounds teach habits of their own (keep them few).

## 3. Decisions: what "attention for strategy" is made of

Today he has a goal for the next item, chosen once a second from eight, and reflexes 40 times a second with a memory
of under ten seconds. Nothing between: no "he is on my way", no "not this way again", no "stay away while he has 240".

| Piece | What it is | Change | Fits the next run |
|---|---|---|---|
| A. More decisions on the head he has | hunt (the way to where the enemy was last seen or is likely to be), stay away (the way that keeps distance and cover), hold (a place: the pros' positions are in `sim/pro_positions`) beside the eight items | three more choices on the intention output, about twelve inputs (the three ways), pay as for the item ways; some rounds of ten minutes, or decisions have nothing to pay for | yes |
| B. A predictor from the pros, offline | can a summary of the game (item clocks as he believes them, both stacks, where the enemy was last seen and how long ago, score, clock) predict a pro's next goal in 3,700 demos | a tool and a small network on the processors, no training run | yes, beside it |
| C. A second, slower network | runs once or twice a second on that summary, remembers minutes, makes the decision of A; the fast network carries it out | a second network in the trainer, the plugins and the export; it starts from B with the fast network held still | no: two to three weeks before a first run |
| D. Attention over things | each item, enemy, missile and exit as a small vector instead of a fixed slot, pooled by attention: "missiles near the exit on my way", "the enemy was last seen on this way", any map, any number of players | `observe_entities()` beside the flat inputs; the network changes shape, so the weights are carried over by copying the old network's play (distillation) and not by input name. Timed on the rented server: four bots 2.3 ms a frame against 1.0 ms now, inside the budget | no: with C |

C and D are where "strategy" would live, and they are a different network: the first run with them will likely play
worse than the one before it for a while. A and B cost a run's preparation and say whether the summary carries what
a decision needs before C is built.

## What folding all three into v15 comes to

| | In v15 | Not in v15 |
|---|---|---|
| Jumps | all of part 1 | |
| Grenades and plasma | all of part 2 | |
| Decisions | A (hunt, stay away, hold) and B (the offline predictor) | C and D (the slow network, attention): v16 |
| The network | one widening: about 23 inputs (509 -> about 532) and three choices on the intention output | a new architecture |
| Before the run | the list of jumps for the owner; the game measured (stairs, ledge, grenades); the walking graphs rebuilt; the teacher trained and checked jump by jump; the scripted opponents in the simulator; the widening with its fixed-run checks; the manifest | |
| Work | about a week of building and measuring before the start, most of it in part 1 | |
| Kept from v14's third start | the control in the league and first in every check, per map; the item rule naming only what he can reach; weapons untaught | |

**For the owner to decide**: whether v15 waits for all of it or starts with parts 1 and 2 while A is built (my
advice: parts 1 and 2 first, A in the run after: three new things in one run cannot be told apart when something
moves, which is v14's lesson); the share of rounds for the scripted opponents and the one-weapon rounds; which jumps
of the list; whether ten-minute rounds come in with A.

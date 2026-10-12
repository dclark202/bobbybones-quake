# v0.2: the manifest (2026-10-11 evening; for the owner's go; nothing is started)

**The names** (the owner, 2026-10-11): "The v15c bot that exists on the server is now: v0.1. We're building v0.2
currently, any exploration phases will get a further index e.g., v0.2.1, etc." and "v1.0 starts when he can beat me."

| Name | What it is | Its folder |
|---|---|---|
| **v0.1** | the network on the public server since 2026-10-11 13:01; the control | `duel_gru_v15c` (`policy_end_v15c.pt`) |
| **v0.2.1** | the run that is ready tonight: today's network, games on all ten maps, the rocket changes, the enemy as a target. It was written up as `duel_gru_v15e` ([MANIFEST_v15e.md](MANIFEST_v15e.md)) | `duel_gru_v0_2_1` |
| **v0.2** | v0.2.1's content with stage A of the attention model, the two-minute value estimate, and the owner's answers of this evening | `duel_gru_v0_2` |
| v0.2.2, ... | further trials on the way | |
| **v1.0** | the first network that beats the owner | |

The owner: "Add stage A from attention to your proposed v15e for tonight and call it v0.2. Don't start it just yet --
give me a full training manifest for it first along with what if anything you still need to build." This is that
manifest. **Stage A is designed and timed, not built** (section 5): built with care it is about a day's work, so the
honest choice for tonight is in section 6.

## 0. The owner's answers it rests on (2026-10-11 evening, his words)

| | |
|---|---|
| Attention | "I'm tempted to just start v16 now, why not?"; the list of events out of the first build: "yes" |
| A second value estimate that counts about two minutes ahead, with the first stage | "yes" |
| Maps | Campgrounds "in"; House of Decay "held out"; Toxicity stays on the public server's list ("no" to taking it off) |
| The enemy as a target, by the narrow rule | "in" |
| The three rocket changes | "in" |
| A seed for rockets with nobody in view | not answered; probed in four forms and not in this run (no form gave rockets that hit) |
| His aim | "it seems his aim is overtuned at possibly the reason why he has become so reliant on lg/rail rather than rockets. let's slowly tune it down, using pros as a goal"; his lightning against people: "measure first, I think he just sucks at doding" |
| Speed gained from hop to hop | "I don't think they're quite there yet, pay him a tiny amount for it. but the key is getting him to use them and maintain speed" |
| Fights taken and refused as a measure and something to foretell | "yes. his choice of picking fight is terrible currently" |
| The noise he makes | "yes, make sure it involves footsteps and stairs as well (you make sound on stairs even when walking)" |
| The gauntlet | "ideally he should, but i won't hold up the run for it" |
| Promotion by the control and the scorecard | "yes within an amount of noise" |
| Later stages | a frag paid by what it moves his chance of winning: "yes"; late-game rounds from drawn states: "yes, up to 25%"; the pros' choices as a small standing pull: "yes"; high ground: "token first"; several ways to a target and a target that is never "nothing": "Yes"; rounds from real moments: "Hold this for v16"; the judge of pro-like movement: "Yes, eventually. Don't build it now but remind me of it after tonight's run"; the exploiter: "leave it out ... Isn't HE the exploiter? He should be?" |

## 1. What v0.2 changes from v0.1

| # | | v0.1 | v0.2 | State |
|---|---|---|---|---|
| 1 | Games on all ten maps (Campgrounds in) | games on six, movement only on four | thirty simulators, three a map, 10,080 players | ready (dry run passed 18:38: 22,800 frames a second, 12.8 GB of the card's 16) |
| 2 | The three rocket changes (`SHOT_W=rl:0.5`, `BLIND_PLACES=150`, `BLIND_RL_DMG=3`) | off | on | ready. Tried for 165 minutes: harmless, no change in his rocket use |
| 3 | The enemy as a target, seeded by the narrow rule (`FIGHT_TARGET=1`) | none | a ninth intention | ready (the fit agrees with the rule on 93.3% of the frames; he takes it 4% of his time at the start) |
| 4 | **Attention, stage A: he is shown more** (section 2) | a flat list of 577 inputs | the inputs cut into tokens, about 230 new numbers, two attention blocks, a door into his memory that starts closed | **not built** (section 5) |
| 5 | **A value estimate that counts two minutes ahead** | one estimate, 25 s (`--gamma 0.999`) | a second one at 0.9998 for the pay of items and stack; fights stay on the short one. His target and way are credited by both, his hands mostly by the short one | **not built** |
| 6 | A tiny pay for speed gained from hop to hop | none | proposed rule, his to confirm: at a take-off while travelling with nobody in view, 0.001 for each unit of speed above the best take-off of this chain so far, between 320 and 480. A whole chain from 320 to 480 pays 0.16 (a pickup of a big item pays 0.75). Paid on the chain's best so far, so losing speed and regaining it pays nothing | **not built** (two hours) |
| 7 | His aim tuned down slowly, the pros' flick curve as the goal | `AIM_LEVEL=3` | step one of several: the delay before he notices an enemy who appears off his crosshair and his hand noise raised until his first hit at 10 to 40 degrees off is a third of the way to the pros' (today 0.38 and 0.58 s; the pros 0.53 and 0.78). Both sides of every check play under the same limits | **to calibrate** (three ten-minute replays; an hour) |
| 8 | Held-out check | the stand-in on ten maps | also on House of Decay; the control with seats swapped | ready |

Unchanged: his legs (two readings to switch off), the pay for speed in games (0.5), the weapon rounds, item runs and
jump runs, the item rule, the game's weapon change on an empty weapon, the league of his last eight selves with the
older networks as standing opponents in a quarter of the rollouts.

Not in v0.2 (stages B and C, as answered): the target that is never "nothing", several ways, whole games and the pay by
the chance of winning, late-game rounds, the standing pull to the pros' choices, legs that run and look, the judge.

## 2. Stage A in full

**The model.** His 577 inputs and the new ones are cut into tokens inside the network. Each kind of token has its own
first layer to 96 numbers; two attention blocks (4 heads, feed-forward 96 to 192 to 96); two rows are read out (a
summary token and his own) and go through `Linear(192, 256)` into the input of his memory, added to what today's
encoder gives. That last layer starts at zero: at its first update the network is v0.2.1's end exactly. About 1.7 million
weights (today 1.44). On the rented server four bots take 7.0 ms a frame (8.4 at the 99th percentile; today 1.1).

| Token | How many | From today's inputs | New in stage A |
|---|---|---|---|
| Himself | 1 | health, armor, weapons, ammunition, speed, his hands, his legs' switch | |
| The game | 1 | frag counts, the round's clock, item clocks | the time left; how loud he has been in the last 3 s (shots, jumps, landings, running steps; stairs: see below) |
| His position | 1 | the map reader's numbers for his cell | his height against where he believes the enemy is; how the pros fare in this cell and with which weapon (`sim/pro_places/<map>_cells.json`); how many of the map's places he has in sight |
| The enemy as seen | 1 (5 in groups) | where, how fast, facing, weapon, what he fired, damage taken | |
| **The enemy as believed** | 1 | where he was last seen and how long ago | where last heard and how long ago; how he was moving; how far he can have got since (seconds of way); his strength as far as it can be known: the damage dealt to him this life, the armor and mega he was heard or seen taking, how long he has lived |
| Projectile | 6 | all of it | |
| Item | 12 | where, the way to it, up or not as he believes, his target or not | when he last took it himself |
| **Place** | 8 | | the nearest of the map's 24 places where the pros' shots land: where, in sight or not, how far from where he believes the enemy is, how often the pros meet the enemy there |
| His way | 3 x 6 | the next waypoints, the jump ahead | |
| Sound | 4 | the last sounds heard: where, what, how long ago | |
| Summary | 1 | | a learned token |

Campgrounds has no places yet (its demos are being fetched tonight on the owner's yes): its place tokens are empty until
its list is made.

**Sounds on stairs** (the owner: "you make sound on stairs even when walking"). The simulator makes a walking player
silent everywhere. To be measured in the game first (a walking player on stairs, heard or not, at what distance), then
built into the simulator's sounds and his own loudness. It does not hold up the first night.

## 3. Rounds, pay, opponents

As v0.2.1: games of two minutes, the weapon rounds, item runs and jump runs on all ten
maps, the scripted lobber, watcher, holder and runner, his last eight selves, v0.1 and the network before it as standing
opponents. The pay is today's, with rows 5 and 6 of section 1. Whole games and the pay by the chance of winning come
with stage B.

## 4. Start, league, checks, stopping, promotion

- It starts from v0.2.1's end if that is at least level with v0.1 ("within an amount of noise": two points of the frag
  share over 240 games), else from v0.1. The attention parts are added by a converter; the first check must be level.
- Full size on the card as far as it fits: the stored inputs grow by about 40%, so they go to half precision or the run
  to about three quarters of its players. A ten-minute dry run decides and shows his step per output before the start.
- Speed: three to four times slower a step than today. A stage needs a night.
- Checks from every save: against v0.1 on the ten maps with the seats swapped; his speed profile; every third time the
  stand-in on the ten maps and on House of Decay. At its end: the scorecard beside the pros (five groups), his commits by
  situation, his flick curve, where he looks before the enemy appears; real games against the game's Nightmare bot on a
  quiet PC.
- Does the door open: the size of the last layer's weights and the share of his memory's input that comes through it
  are written with every update.
- Stopped: under 45% against v0.1 at two checks in a row, or ten points under on a map at two checks; a stall is watched
  for.
- Promoted to the public server as v0.2: it beats v0.1 and falls back in no group of the scorecard by more than three
  points, and the owner has played it.

## 5. What is still to build for v0.2

| | Work | Hours | Needs |
|---|---|---|---|
| a | The token layout over today's 577 inputs, by input name, with a check that every input has a place | 1 | |
| b | The new inputs in the simulator behind a switch (with it off the simulator is unchanged in fixed runs): the enemy as believed, eight places, his position, the time left, his loudness; the group module regenerated; today's simulator frozen as a copy | 5 | the places in sight are traced a few times a second, not every frame; the cost is measured |
| c | The network with attention in the trainer; a converter that adds it to an existing network with the door closed (outputs equal on a batch); the same forward pass in plain numbers for the checks (the timing prototype has it) | 4 | |
| d | The second value estimate: the pay split in two in the simulator's reward, two outputs, two advantages | 3 | |
| e | The hop-gain pay (row 6) | 2 | the owner's word on the rule |
| f | The aim step (row 7): three replays to set it | 1 | |
| g | Dry run, the card's memory, the first level check | 1 | |
| h | For the real server (not needed to train): the plugins and the export build the tokens with the simulator's own function; four Bobbys timed on a private server | 4 | before v0.2 is promoted |

Rows a to g: about 17 hours of work and waiting on checks. With two helpers on rows b and d in staging copies it is
ready for a start tomorrow (2026-10-12) in the evening. Ready today: rows 1, 2, 3 and 8 of section 1, which are v0.2.1.

## 6. Tonight

| Choice | What happens | For and against |
|---|---|---|
| **A (recommended): v0.2.1 now, v0.2 tomorrow evening** | v0.2.1 starts on the owner's go and runs to tomorrow evening, or until v0.2 is ready. Stage A is built beside it in staging copies (the repo's simulator is not touched while a run trains). v0.2 starts from v0.2.1's end | the card is not idle; he plays games on Campgrounds, Hektik, Toxicity and Cure for the first time, which the public server needs; the attention build is not rushed ("do this right not rush it") |
| B: wait for v0.2 | nothing trains tonight; the whole PC builds stage A; v0.2 starts when it has passed its dry run, tomorrow afternoon at the earliest | a few hours sooner for v0.2; a night of training lost, and v0.2 then carries the ten maps and attention at once |
| C: a cut-down stage A tonight (attention over today's inputs only, no new information, no second value estimate) | buildable in about four hours, a start near midnight | it tests only whether the door opens. The afternoon's reading was that the gain is in the new information, not in attention itself; and it is the rushed build the owner warned against |

## 7. What could go wrong

- The door stays closed: he ignores the tokens. Seen in the first night's numbers; the answer is a short lesson that
  makes him foretell from the tokens (where the unseen enemy is), which is stage B's belief brought forward.
- The second value estimate makes the pay for items louder than the pay for fights (it sums over two minutes). The dry
  run reads his step per output; the two are scaled to today's balance at the start.
- The aim step costs him his duels against older selves' habits, not against the control (both play under the same
  limits). Watched by his weapon choice: the owner expects rockets to gain as lightning and rail lose their edge.
- The card: three to four times the work a step and 40% more stored inputs. If it does not fit at full size the run is
  three quarters of its players.

## 8. The public server

v0.1 stays on it, Toxicity stays in its map list (the owner's "no"). Nothing is pushed by this run. At the next push
with new code v0.1 needs `--env duel_env_ffa_v15` (the frozen 576-input simulator).

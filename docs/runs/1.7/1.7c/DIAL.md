# The weapon dial for play against people (2026-11-07)

*Owner, 11-07: "What I want to see is him use rockets both in close and medium range, and for zoning. Use LG at close range, and
rail at long range. He's not learning it training, but perhaps there's a way to nudge toward that for play against people?" ...
"Build the dial for play against people and I'll play test it when it's ready. Then afterwards we'll consider 1.7c."*

**What it is.** A push on his weapon key at play time, no training ([sim/weapon_dial.py](../../../../sim/weapon_dial.py)): a press
of rockets, the rail or the lightning gun (owned with ammunition) gets p x (log t_j - log t_held), t = the owner's table for the
situation he perceives (the enemy noticed in view, the distance to where he last knew him). Keep and the other weapons are untouched.
A hand-built rule, not learned; the network is 1.7a's update 90 unchanged.

| The owner's table (the draft he left as it was) | rockets | rail | lightning gun |
|---|---|---|---|
| in view, close (under 300 units) | 50% | | 50% |
| in view, medium (300 to 700) | 70% | | 30% |
| in view, long (700 and over) | 30% | 70% (where he has it) | |
| out of view (travelling, zoning) | 70% | 15% | 15% |

**On the servers.** `!weapons off|light|strong` in the 1v1 plugin (plugins/duelbot.py; the push in plugins/netpass.py `step()`),
beside `!aim`: the player in the duel or the server's owner; at once; back to the default (`DUEL_WEAPONS`, else off) on a new map
and when the person in the duel leaves; every change in the session's events (`event: weapons`) and the default in `meta.json`.
`tools/run/local_server.sh` takes `WEAPONS=<level>` for the default.

## Checks

| | result |
|---|---|
| The plugin's push = the checks' ([exp/dial_parity.py](exp/dial_parity.py)) | ALL PASSED: at off, light and strong the network's logits the same in both, the plugin draws from them + the push and nothing else (largest difference 1e-6), the checks' push the same as the plugin's (0) |
| In the image (`qlbot:17a-dial`, built from `main` + the dial; numpy 2.5.4, no torch) | `import weapon_dial, netpass`: ok |
| `!weapons` on the server (rcon as the owner) | strong at the start (`WEAPONS=strong`), light, strong: each logged and announced |
| A real game against Nightmare (skill 5, Blood Run, strong, 10 min, a private server) | won 21-5; with rockets owned in hand rockets 34%, the lightning gun 57%; frags rockets 5, the lightning gun 16; rockets 24 shots, 18 hits (splash counts), 1,107 damage. Nightmare dodges little: not a measure of fairness |

**In the simulator** (1.7a's update 90 with the dial against itself without, 200 ten-minute games on ten maps, the u90 check's own
settings read back and compared: [exp/wpush.py](exp/wpush.py) `--form dial`; the earlier pushes toward the pros' hand beside them):

| | record (win rate) | rockets / rail / lightning in hand in view | ... out of view | rockets' share of his frags | kills a player per 10 min, pushed / plain |
|---|---|---|---|---|---|
| off (the plain side) | | 18 to 20 / 1 / 70 to 73% | 18 to 20 / 1 / 65 to 68% | 10% | |
| **light (p 2)** | **96-104 (48.0%)** | **27 / 1 / 63%** | **27 / 1 / 57%** | **15%** | 10.9 / 11.3 |
| **strong (p 4)** | **67-133 (33.5%)** | **41 / 1 / 49%** | **43 / 1 / 41%** | **18%** | 9.2 / 11.9 |
| (the pros' hand, ratio 1; ratio 3) | 50.0%; 42.5% | 24 / 1 / 67%; 35 / 1 / 55% | 24 / 1 / 60%; 38 / 1 / 47% | 12%; 16% | |
| the pros | | 41 / 14 / 32% | 57 / 12 / 9% | | |

**What it says.** Light is nearly free against himself (48%: within the checks' noise) and moves rockets 20 -> 27%. Strong puts
rockets in his hand as often as the pros in view (41%) and costs 16.5 points against himself: his hands fight worse with rockets
than with the lightning gun (as the pushes toward the pros' hand showed). What it costs against people is what the play test
measures. **The rail does not move** (1% at every setting): he rarely owns it with the enemy at long range (Aerowalk: owned a third
of his time; Campgrounds: never taken), and a push on the key cannot make him go and take it. **Zoning**: the dial puts rockets in
his hand out of view (43% on strong); whether he fires them at a doorway is his own (no cost for firing; 1.7a's order learnt its
spam away).

## Weaknesses (red team)

- A hand-built rule on a learned choice; the learned way is 1.7c's plan (the head holds the weapon, fitted to the pros, a KL through
  the run), to consider after the play test.
- **Fairness, before it goes public**: his rocket hits in self-play (50%, direct 20%) are above the pros' (36%, 10.5%), where the
  target is another Bobby. The play test's logs (`player_stats`: shots, hits, damage by weapon) give his rockets against a person.
- The table is the owner's, not the pros' (the pros hold the lightning gun most at medium range: 34 / 43 / 17% close / medium / long).
- The image is `main` (1.7b's code, its switches off unless the export sets them) + the dial, not the public build `pub-4464445` + the
  dial: the export of update 90 is the one played on 11-06 (its env_vars the same to the key; the settings check's three differences,
  CONTACT_FREE, LEVEL_PULL and RAIL_FAR_PAY, are 1.7a's live dials, as then).

## The local play test

Server `qlduel_17a-dial` on port 27970 (`connect 127.0.0.1:27970`), image `qlbot:17a-dial`, 1.7a's update 90, aim default, the dial
**strong** at every map's start (`WEAPONS=strong`); `!weapons off` / `light` to compare. Data: `data/duellive_17a-dial`; the mind
viewer http://localhost:8765/ and the games site http://localhost:8766/history/.

**The owner's verdict (2026-11-07 evening): "didnt do fucking anything".** One game on Blood Run, about 3.5 minutes (19:31 to 19:34,
then a map change to Sinister), the dial on strong (`meta.json`). Bobby held the lightning gun 53% of the game, rockets 26%,
the machine gun 13%, the shotgun under 1% (the whole game, whether or not he owned rockets). That is still a lightning-gun player:
a push on a key press he almost never makes cannot change how he plays. The server and the mind log were stopped on his word; the
dial stays in the code, off by default, and is not on the public servers.

## The replace form, `!weapons pros` (2026-11-07 evening; branch `wdial`)

*Owner: "go ahead and build what you think is the right normalization for him in human play."* The table **chooses** his weapon
instead of nudging a press ([sim/weapon_dial.py](../../../../sim/weapon_dial.py) `choose()`; the design and the training plan behind
it: [TRAIN_UNDER_TABLE.md](TRAIN_UNDER_TABLE.md)): among rockets, the rail and the lightning gun that he owns with ammunition, one is
drawn from the table's row for his situation and the weapon key's action is set to it (a press until it is in hand, then keep). Held
1.5 s across a band's edge; drawn again at once when the row gives the weapon in hand nothing; where the row allows none of the three
he owns, the network's key stands. Fire, aim and movement are his. `!weapons pros` on a server (`WEAPONS=pros` in
`tools/run/local_server.sh`); in the checks `--wpush 1 --wpush-form replace`; `WDIAL_LOG=<file>` writes one line a player a frame
(seat, row, held, pick, action, distance, in view) for a diagnosis.

| Check | Result |
|---|---|
| [exp/dial_parity.py](exp/dial_parity.py), the plugin's path against the checks' | ALL PASSED: the same weapon key action in both every frame (200 frames x 8 players); every press of a weapon owned with ammunition; where the row allows none the network's key stands and every other output is exactly the dial-off draw (the dial has its own random stream) |
| Does he hold what the table chose? (`WDIAL_LOG`, Blood Run 2 games; Aerowalk and Campgrounds 2 games) | held = chosen on 98 to 99% of the frames the dial is active; a switch lands in a median of 1 frame (mean 1.8, p90 4), 94% of the choices realised. **In view at long range with the dial active: rockets 79 / rail 17 / lightning 4%** (Aerowalk, Campgrounds) |
| When does it stand aside? | the row allows none of the three he owns on 14 to 16% of all frames (a spawn's machine gun), and on **40% of the long-range frames in view on Aerowalk and Campgrounds**: no rockets with ammunition and no rail. That, not the dial, is the lightning gun he still shows at range (the check's bands: lightning in hand at over 700 units 50%, all maps) |

**In the simulator** (1.7a's update 90 under the table against the same save plain, 200 ten-minute games on ten maps, the u90 check's own
settings; `wpush.py --form replace --cy`; [exp/wsum.py](exp/wsum.py)):

| | record (win rate) | frag share | rockets / rail / lightning in hand in view | ... out of view | frags by rockets / lightning | kills a player per 10 min, table / plain |
|---|---|---|---|---|---|---|
| **pros (the replace form)** | **69-131 (34.5%)** | 44.0% | **53 / 2 / 40%** | 53 / 3 / 33% | **41 / 57%** | 8.8 / 11.4 |
| strong (the push, p 4) | 67-133 (33.5%) | 43.4% | 41 / 1 / 49% | 43 / 1 / 41% | 18 / 77% | 9.2 / 11.9 |
| plain (the other side) | | | 18 / 1 / 74% | 19 / 1 / 68% | 12 / 84% | |
| the pros | | | 41 / 14 / 32% | 57 / 12 / 9% | | |

Maps: Toxicity 10-10, Blood Run 9-11, Campgrounds 8-12, Cure 8-12, Lost World 7-13, Hektik 7-13, Sinister 6-14, Aerowalk 5-15,
Furious Heights 5-15, Battleforged 4-16. His hits under the table: rockets 48%, lightning 36%, the rail 22% (0.2 shots a minute: too
rarely owned to judge his trigger with it). Lives a minute 2.50 against 1.93 (he dies more); the mega 41% against 49%; damage from
unseen 16 against 23 a minute (he fires less blind).

| Cypher's measures (`cypher_measure.py check`, 6,875 fights) | him under the table | the plain side | the pros |
|---|---|---|---|
| out-stacked: dies / escapes | 51.7 / 45.2% | 45.4 / 48.3% | 29.9 / 63.9% |
| the weaker side hits first | 17.9% | 34.5% | 46.9% |
| the bigger stack wins the fight | 79.7% | 89.9% | 77.5% |

**What it says.** The replace form does what the push could not: the weapon in his hand is the table's (rockets 53% in view, the pros'
41%; frags by rockets 41% against 12%), and it costs what the push at "strong" cost (34.5% against himself; the owner: acceptable).
His hands fight worse with rockets against a copy that has lightning: 8.8 kills to 11.4, dies more, and as the weaker side he hits
first half as often (rockets land later than lightning). **None of Cypher's numbers improves before training**: the table changes the
weapon, not the fight decision; whether they move is what the run under the table ([TRAIN_UNDER_TABLE.md](TRAIN_UNDER_TABLE.md))
measures. **The rail stays out of his hand (2 to 3%) because he does not own it**, and at long range he lacks rockets with
ammunition or the rail 40% of the time on the long maps: the items side (the rail and rocket ammunition as things worth taking) is a
limit the dial cannot move and the run's panel must report. His rockets' hits (48%) are above the pros' (36%) against a copy; against
people they are measured in the play test's `player_stats` before any public server.

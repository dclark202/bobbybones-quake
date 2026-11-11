# 2.0b: what was measured before the build (2026-11-09)

*The card's nine measurements ([CARD.md](CARD.md)); the method and the earlier passes: [design/SPACE.md](../../../design/SPACE.md) part 3b.
Data: the pros, 150 demos a map on nine maps (1,256 games; the weapon table from half, the tests on the other half); Bobby, 80 recorded
self-play games each of 1.7a's update 90 (`duel_gru_1_7a/cypher/u90`) and of 2.0a's end (`duel_gru_2_0a/cypher/end`, recorded 11-09 on
the efficiency cores; the settings check: 124 settings, one differs only in spelling (`LEGS_NET`'s `%ROOT%`), one save-only pay value
(`RAIL_FAR_PAY` 0.25 in the save, 0.12 in the command: no part of play)). Tools: `tools/run/space_score.py` (`score`, `test`, `edge`,
`zones`, `state`, `draw`), `tools/run/space_fit.py`; the item and pro-cover scripts are in the session's scratchpad and move into
`space_score.py` with the build ⏳.*

## The gap the run is aimed at

| With the enemy within 1,500 units | The pros | 1.7a's update 90 | 2.0a's end |
|---|---|---|---|
| Time under a threat over 20 damage a second | **8.0%** | **18.0%** | **18.4%** |
| Hit for 20 or more in the next 2 s, by the threat on him (under 2 / 2-5 / 5-10 / 10-20 / over 20) | 11 / 22 / 27 / 40 / 60% | 4 / 14 / 22 / 34 / 64% | 4 / 14 / 22 / 34 / 63% |
| Time with the edge under −10 | 4.1% | 7.4% | 8.0% |
| In the enemy's sight: over 1 s from cover | 23.5% | 28.8% | 25.6% |
| Not in his sight, over 75% of his reach sees him: hit in the next 2 s | 39% | 39% | 42% |
| Dealt less taken in the next 2 s, the edge from under −10 to over 10 | (no damage dealt in the demo sets) | −7.6 … +6.7 | −9.2 … +8.1 |

## The nine measurements

| | Measurement | Result | What it means for the card |
|---|---|---|---|
| 1 ✅ | the cover of the big items' ground and who takes the next item | 5 s before a pickup, who covers the item's place names the taker in 65% (where it says anything: 61% of pickups); who is nearer 61%; who has the stack 55%. Beside the other two it adds little (log loss 0.6452 → 0.6424) | the item cover is real but mostly "who is nearer" |
| 2 ✅ | 2.0a's end beside update 90 | on every space measure the same within a point (the table above). In self-play it takes the mega slower: within 1 s of the spawn 44% against 57%, median 1.3 s against 0.8 s; the red 41% against 46%. Who takes by the stack is unchanged (the mega: ahead 47%, behind 31 to 32%) | **2.0a's pay did not teach him to cede the big items by the stack; his timing of them slipped by half a second.** The start stands; the mega and red timing joins the check measures |
| 3 ✅ | the pay's size | **the edge**: mean 4.1 damage a second in size with the enemy near (89% of the time), the 95th percentile 17.9. At 0.0005 a damage-second: 0.11 a player-minute (a tenth of the frags'), a full minute at +20 pays 0.6 of a frag. **The item cover**: mean size 0.19; at a frag a full minute of all of it, 0.19 a player-minute | both fit the card's two rules |
| 4 ⏳ | belief against truth | not measured: the records do not hold the brain's readout | a recorder change, with the build; part 2 does not open before it is read |
| 5 ✅ | the pros' cover of the item ground by their own stack | the pros from under 75 to over 250 of stack: +0.017 to +0.050; update 90: −0.009 to +0.058; 2.0a's end: −0.021 to +0.065 | **the pros' leader does not hold more of the item ground than his.** A pay for the item cover has no measured ground; the edge has |
| 6 ✅ | teleporters | they were left out (29 to 188 links a map); now in as one-way links for the reach and the way to cover. The threat's test moved by under half a point | done |
| 7 ⏳ | the two held-out maps | not done: no `data/maps/nav_houseofdecay_sim.json` or `nav_dismemberment_sim.json` | find how their walking maps are kept, or build them |
| 8 ✅ | the cost | nearest point and the threat both ways for 10,000 players: 7 ms; with the cover of 24 zones from zone tables: 15 ms. Read every frame that is about 5% of a rollout by my estimate (not timed in the trainer); at the head's rate far less. The tables: 1.3 to 4.9 MB a map | no obstacle; timed properly in the build's smoke test |
| 9 ✅ | pictures of a state | `space_score.py state`: Blood Run, the enemy at the mega with lightning: the threat is the T of corridors round him and stops at each corner (`docs/design/space/state_bloodrun_z15_w2.png`) | the owner's eye on more states |

## Passes that came back empty (kept so they are not tried again)

| Pass | Result |
|---|---|
| Who wins a decided fight, by room-sized zones | the stacks and weapons alone: the pros 82.8% right, Bobby 88.2%; the places add nothing in either |
| Who held and who pushed at a sight onset | no difference at level stacks in either; over all stacks it is the stack (the weak hold, the strong push) |
| A score of a place by the map alone | it tracks damage taken, but the pros stand in the worst fifth as much as he does (15.3 against 15.4% of standing time) |
| The map's cover beside the stack, his games | frags less deaths in the next 30 s explained: the stack 0.286 (2.0a's end 0.325), with the cover 0.293 (0.331) |

## The weapon table (the pros, damage a second on a player in sight; `data/sim_runs/space/weapon_threat.json`)

| Weapon in the enemy's hand | under 400 units | 400 to 768 | over 768 |
|---|---|---|---|
| rockets | 35.0 | 12.2 | 4.0 |
| rail | 25.4 | 29.5 | 32.8 |
| lightning | 45.7 | 39.0 | 9.8 |
| plasma | 43.0 | 20.2 | 10.0 |
| machine gun | 7.5 | 7.2 | 7.1 |
| shotgun (16 minutes of it) | 38.4 | 15.5 | 27.2 |
| grenades (12 minutes) | 17.9 | 4.8 | 2.4 |

Cautions: the weapon in a hand goes with the stack and the moment (a rail is in hand when a line is being held); the pros' enemy is known
only while the server sends him; in Bobby's games the enemy holds the rail for 3 minutes of 1,281, so his own table has no rail row.

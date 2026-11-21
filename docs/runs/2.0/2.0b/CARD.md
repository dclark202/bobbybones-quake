# 2.0b: the ground he covers and the ground that covers him: read, seen, then paid

*2026-11-09 (owner): "a score per place relative to where the enemy is; and in real time he needs to use his belief about the enemy to judge
the score of where he wants to go, or where he hangs out or chooses to stay"; "This is exactly the 'bubble' I'm talking about, the good
places to hold, vs the places he believes he will get punished for walking into willy nilly"; "play to not lose ... he needs to be expanding
what he believes to be his control of the area and reducing the opponents. That probably should get a live readout, per place, and on the
aggregate? And then pay zero sum by 'control' of different areas, using the real map state. this trains the brain and the head to learn to
control certain areas more than others"; "let's redirect 2.0b to go in this direction". The design and what was measured:
[design/SPACE.md](../../../design/SPACE.md) (part 3b); the family: [README](../README.md); before it: [2.0a's report](../2.0a/REPORT.md).
**Rewritten 2026-11-09; the owner's go the same evening ("ok looks good. continue the build and start it when it's ready"; the length: "sure 16:00 is fine"). The build and what was decided in it: [BUILD.md](BUILD.md); the measurements: [MEASURED.md](MEASURED.md).***

**Marks:** ✅ measured or already built · 🧪 to measure before the go · ⏳ to build · ❓ owner's decision

**Started from:** 2.0a's end (`data/sim_runs/duel_gru_2_0a/keep/policy_end_20a.pt` with its optimizer; owner, 11-09: "2.0a end is fine"),
with **1.7a's update 90 as the control** in every check (the last best; 2.0a's end is 42% against it). 🧪 measurement 2 below may speak
against it.

## The owner's page

| | |
|---|---|
| The instrument ✅ | **the table of a map** (`tools/run/space_score.py`, `data/maps/space_<map>.npz`): for every pair of walking points, how much of the ground a player can be on within 1.5 s of the one sees the other, by the length of the sight line; times **the weapon table** (the pros' damage a second in sight, nine weapons, three lengths: `data/sim_runs/space/weapon_threat.json`). From it, for any two places and two weapons: **the threat** on a place (damage a second), **the edge** (what he puts on the enemy's place less what the enemy puts on his), **the cover** of a place (which of the two threatens it more) |
| What was measured ✅ | hit for 20 or more in the next 2 s rises with the threat from 11 to 60% (the pros) and 4 to 63% (Bobby). **He is under a threat over 20 damage a second 18.3% of his time near the enemy; the pros 8.3%.** The edge runs his next 2 s from −7.6 to +6.7 damage; the map's cover his next 30 s from −0.50 to +0.40 frags less deaths. In his games the cover adds little beside the stack (0.286 → 0.293 explained) |
| Part 1, from update 0: **the readout** | a lesson for the brain, its own layers, nothing else moved by it: from his senses, **the cover of each zone** (his, the enemy's, by how much: at most 24 a map), **the aggregate** (his share of the map's item ground less the enemy's) and **the threat on him**. The truth is the table read at the true places and weapons, every frame: exact, no hindsight |
| Part 2, opened after part 1 has learnt: **he reads it** | inputs, from zero weight through a gate: for the hands, the threat where he stands, the edge, the direction of the nearest place with less threat; for the head, the threat at each target it chooses among and along the way to it, and his cover of it. **Always against the brain's belief of the enemy's place** (its place readout, now and 1, 2, 4 s ahead: a spread of places, the table's mean over it), never the truth |
| Part 3, opened last and slowly: **the control pay** | zero-sum, from the true state: a frame pays `CONTROL_PAY` × (his cover of the map's item ground less the enemy's), the enemy the same with the sign turned. Places count by what they hold (the big items by their clocks, the weapons), not by area. Live dial from 0 ❓ decision 3, sized 🧪 by the rule: **the whole map's item ground held for a full minute pays less than one frag**, and its size in the ledger stays under a quarter of the frags' |
| Stays | 2.0a's end pay (damage at the floor 0.001 zero-sum, `WIN_ADD` 0.6, the flat frag and death, the item table); the keep choice learning (flagged at 0.08); the order shut; the habit seats; no firing cost; the fairness limits; `!aim default`. **The weapon untouched**: read as an outcome (the weapon table gives the rail a job on long lines; nothing pays the rail) |
| Length | ✅ to 16:00 on 11-10 (owner, 11-09: the three parts need about 100 updates to open and the pay three checks after) |
| Checks | every 20 updates, 200 games against 1.7a's update 90; every fourth against 1.6a's end; the extra check at update 10; of every check Cypher's measures and **the space measures** (below); the ledger every update |
| Expected | the readout learnt well inside 30 updates (its truth is exact). With the inputs open: less time under a heavy threat, targets chosen where the threat is low, more standing near cover. With the pay: the leader's cover of the item ground up, the weaker player outside it and taking what lies outside. Win rate against update 90 from 42% toward and over 50% |
| Not in this run | the holder seats (SPACE.md part C: kept in reserve: with the pay the game itself is no longer the only thing that punishes); the judge looking ahead through the table (part D); break off and the order; drills that start in a losing fight; any weapon work |

## Risk by the lead and the clock (owner, 2026-11-09, later)

"the place weightings + time left in game should encourage safe play when up, proportional to time left, fed by the brain, head and win
chance pay. Up 1 with 1 minute left, the goal is to keep that lead, down 3 with 2 minutes left, you might have to take some bigger risks to
get the chip damage needed to get an in on a fight"; "stack determines who wins a fight. people tend to have similar damage per second, so
stack and positioning determine a fight, and positioning is what we're trying to fix here. Chip damage evens out the stack, and can have
affect on positioning (bigger stack = more control can be exerted)."

What the measurements say to it: the stack alone names the winner of a decided fight 83% of the time among the pros and 88% for him; the
place does not add to *who wins*, it sets *the damage exchanged before and around it* (the threat, the edge). So the chain is place →
damage → stack → fight, and the place's worth is the damage it is expected to cost or bring, priced as any damage is. **The judge already
prices damage by the lead and the clock** (2.0a's card: a frag when 3 behind with 2:00 left 0.82, when 3 ahead 0.33; a chip on a stacked
enemy more than on a spawn). ❓ Decision 9: part 3's pay as the judge reading the edge (the damage the next 2 s are expected to bring,
priced by the judge at the lead and the clock: safe when ahead late, risk when behind, with no rule for either) instead of a flat pay for
covered ground. The head already reads the lead and the clock; with part 2 it reads the threat beside them.

## Why this, after 2.0a

1.7b gave him a number without a reason and 2.0a a reason without a number. Here the number comes first and is exact (part 1), he gets to
use it (part 2), and only then is anything paid for it (part 3). Three parts open one after the other, each read on its own measure before
the next (the rule for more than one new thing).

## The equilibrium (the standing rule)

Zero-sum in every part of the pay. Two copies each want the ground round the next spawns covered by themselves: the one with the stack and
the weapon for the lines holds it, because an entry under his threat costs the enterer damage he can now see coming; the other stays where
the threat on him is low, takes what lies outside (the yellows, a weapon), chips from places with cover close, and comes in when the cover
changes (the holder leaves for an item, a second way in, a weapon that out-ranges his). Fights happen at edges. On the way: fewer frags a
match-minute at first, more fights nobody finishes, less time under threat. It wins more in the long run if covering the item ground wins
games: true of the pros by the owner's eye and by Cypher's account; **not yet shown in numbers** (in his own games the cover adds little
beside the stack). If it is false he learns to hold ground that does not matter and the control, which holds nothing, beats him: the checks
say so.

## Still to measure before the go

**Measured 2026-11-09: [MEASURED.md](MEASURED.md).** Done: 1, 2, 3, 5, 6, 8, 9. Open: 4 (belief against truth: with the build) and 7 (the
held-out maps' walking maps). What they changed: the start stands (2.0a's end is level with update 90 on every space measure; its mega
timing slipped from 0.8 to 1.3 s); the pay is the edge first (decisions 9 to 11), the item cover has no measured ground in the pros' play.

| | Measurement | Why | Needs |
|---|---|---|---|
| 1 🧪 | **the cover weighted by what a place holds**: the item ground (the points that see or reach each big item and weapon, weighted by its clock), and whether holding it beforehand says who takes the next mega, red and yellow | it is the pay's own quantity; a pay on raw area would pay corridors | his records ✅ |
| 2 🧪 | **2.0a's end beside update 90** on every measure of SPACE.md 3b, and who takes a contested big item by the stack ratio | 2.0a's end took fewer megas and reds: if its pay taught that, the start changes | 80 recorded games of 2.0a's end: a side job, about 36 minutes on the efficiency cores (`0x3C3C`), nothing else running |
| 3 🧪 | **the pay's size**: the cover's spread a player-minute at his present play, and the dial that keeps a full minute of the whole item ground under one frag | decision 3; rule 5 | measurement 1 |
| 4 🧪 | **belief against truth**: the threat on him read from the brain's place readout against the threat from the true place, frame by frame | part 2 is only as good as his belief; an unsure belief must give a soft bubble, not a wrong sharp one | the brain's readout written into the records ⏳ |
| 5 🧪 | **the pros' cover** from the enemy's last known place: when ahead, do they hold more of the item ground than he does | the claim the pay rests on | the demo sets ✅ |
| 6 🧪 | **the table's ways**: cover and reach use walking and air links only; teleporters and jump pads are left out | Blood Run and Lost World have teleporters: a wrong reach there is a wrong bubble | the walking map's other links |
| 7 🧪 | **the two held-out maps** (House of Decay, Dismemberment): tables built, the score's test on them | nothing in the table is fitted to a map; the weapon table is the pros' | minutes |
| 8 🧪 | **what a frame costs**: the lookups for 10,000 players an update | the trainer's update time must hold | a timing on a scratch copy |
| 9 🧪 | **the owner's eye**: pictures of the threat for states he names (the enemy at a place with a weapon) | "a sharp score say around a corner is exactly what I have in mind" | `space_score.py state` ✅ |

## Judged by (every check)

| Measure | Update 90 ✅ | The pros ✅ | Alarm |
|---|---|---|---|
| Win rate against 1.7a's update 90 | (2.0a's end: 42%) | | under 40%: flagged at once (rule 6) |
| Time near the enemy under a threat over 20 damage a second | 18.3% | 8.3% | |
| Time with the edge under −10 | 7.4% | 4.1% | |
| In the enemy's sight: over 1 s from cover / under 0.5 s | 28.8 / 27.5% | 23.5 / 35.6% | |
| Not in sight, over 75% of the enemy's reach sees him | 12.4% of his time | 9.5% | |
| The readout: error against its base rate (cover a zone, the aggregate, the threat) | | | not under the base rate by update 30: part 2 does not open |
| The head's targets: the threat at the one chosen against the others on offer | 🧪 | | level through part 2: the inputs are not used (1.7b's failure) |
| The leader's cover of the item ground; who takes the next big item | 🧪 | 🧪 | |
| Dies when out-stacked | 0.549 | 0.299 | |
| Mega / red / yellow taken | (2.0a's end: 1231 / 1451 / 2520) | | megas and reds falling further |
| Frags a match-minute | 2.2 | | under 1.5 (passivity) |
| The ledger: the control pay's size beside the frags' | | | over a quarter; a sign flip; negative frags; lopsided games |
| His weapon in hand (lightning / rockets / rail) | 0.64 / 0.19 / 0.01 | | read, not steered |

## Red team

| Part | Hand-built or assumed | The measured alternative | Watch |
|---|---|---|---|
| The table | the reach (1.5 s of walking), the three lengths of a line, cover by walking time: chosen, not fitted | 1 and 2.5 s beside it; the links of measurement 6 | the score's test (SPACE.md 3b pass 7) at each |
| The weapon table | the pros' damage a second: their aim, not his; the weapon in a hand goes with the stack | his own table from his games (lightning at mid range 18 against the pros' 38 a second) ❓: the pros' teaches him the rail's line before he can hold it himself; his own is what he faces in self-play | the threat's calibration on his games, by weapon |
| The control pay | **shaping**: in his games the cover adds little beside the stack, so this pays what we believe matters before the game shows it. B-280 ruled a control pay out once (camping) | the judge fitted with the cover in it (part D): the weight would come from who wins, and on his own games it would come out near nothing | the ledger's size; items taken; frags a match-minute; the control |
| Level pay or a potential | a potential (paying the change) cannot be farmed and does not change the best play; **the point here is to change it**, so the pay is on the level, zero-sum | the potential as the cautious arm ❓ | standing time in covered ground with nothing to guard |
| Places by what they hold | the item ground's weights (which items, how the clock counts) are a choice | measurement 1 picks the weighting that says who takes the next item | the cover of ground with no item |
| The inputs read his belief | a wrong belief gives a wrong bubble; the brain's place readout was never used this way | measurement 4 | the threat from belief against the truth, in every check |
| A readout learnt and not used | 1.7b | the gate's opening tied to the head's-targets measure | above |
| The pay knows the truth | by design; the readout is how he gets to know | none needed | the readout's error |
| The servers | the plugins never call `step()`: the table, the weapon table and the belief's spread must be kept there too; the tables are files a map (🧪 size) | recorded on a private server beside the simulator's before any deploy | `OBSDUMP` |
| No new sum of learned outputs (rule 11) | the table is frozen and enters as inputs and labels; the readout is a lesson | | |
| Pay pathologies | | | negative frags, sign flips, lopsided games |

## The steps

| | Step | Done when |
|---|---|---|
| 1 | measurements 1 to 9; a page to the owner | he says go on, change, or stop |
| 2 | ⏳ the table in the simulator (`sim/space.py`: load, the threat, the edge, the cover; off = today's simulator in fixed runs); the truth columns (`SPACE_TRUTH`) | an identity check off; the truth columns against `space_score.py` on recorded games |
| 3 | ⏳ part 1: the readout's layers and lesson in the trainer | ten updates on a scratch copy: the lesson falls, nothing else moves (the step by output) |
| 4 | ⏳ part 2: the inputs (the widening: the start answers as before), the gate live with its range (`LIVE_RANGE`) | `tests.py start`, `ident`, `live`, `smoke` |
| 5 | ⏳ part 3: the pay in the simulator, `CONTROL_PAY` live with its range, its term in the ledger | the ledger is the dial's arithmetic; zero-sum to the bit between the two seats |
| 6 | a new part of the network and a new pay: **ten updates on a scratch copy and a check against the control** before the start | the check not under the start's level |
| 7 | the card finished on the measured numbers, the settings check, the owner's go | |

## The checklist

| | |
|---|---|
| built | [BUILD.md](BUILD.md): the table and the lookup (`sim/space.py`), the truth columns, the inputs and the pay (`sim/duel_env.py`), the readout (`sim/spaceread.py`, the trainer's `--space-read`), the converter (`tools/b20b_init.py`), the run's files. **Not built:** belief against truth (measurement 4), the space measures of a check's own games, the plugins |
| tests (logs beside this card) | `tests_env.py` 18 checks; `tests.py start` (the start answers as 2.0a's end), `ident` 22 checks (a fixed seed repeats itself; the pay and the open inputs' gate each change nothing before the first learning step, to the bit), `live` 8 (the start's file applied; dials written after update 1 applied by update 4; the save carries the gate), `smoke` 16 (ten small updates with everything open, a restart, a check with the save's own inputs and gate) |
| found by the tests | the two new tokens' first layer was drawn at random (opening the inputs changed 10% of the actions at once): now at zero; the tokens' own gate counted from a minute long past (open at once): `--gate-start` is the run's start minute; the optimizer's carry-over knew one new token: now two; the checks' settings did not carry `SPACE_IN` and `SPACE_GATE` (a check would have played him without the inputs): `tools/run/panel.py` reads them from the save |
| the dry run (`dry.py`, `dry_train.log`) | the run's own command at full size, **everything open from update 0** (the worst case): ten updates in 58 minutes (5.7 an update, 2.0a's pace; the card at 8.4 GB of 16). The step 0.029 on every update (2.0a's own); frags a match-minute 1.3 → 2.2; the readout above its base rate from update 2, at update 10: the threat on him 0.76, what he puts 0.74, the map's cover 0.69, the zones 0.57 (1 = perfect); the edge pay 0.7% of the pay's size; under a threat over 20 in 17% of the frames (the measurement read 18%) |
| the dry run's check against the control (`dry_check.log`) | **74-126 = 37.0%** of 200 games against 1.7a's update 90 (2.0a's end read 42% against it; a check's noise about 3.5 points; the line set before it ran: not under 35%). Under 40%, so flagged to the owner at once. Worst maps: Furious Heights 4-16, Blood Run 5-15, Aerowalk 5-15. The arm is the worst case (everything open at once); the run's own checks at updates 10 and 30, before anything but the readout is open, are the baseline |
| start | **`start.ps1` 2026-11-09 21:09**, 1126 minutes (to 16:00 on 11-10; owner: "start it when it's ready", "sure 16:00 is fine"); the settings check against 2.0a's command: only `--run`, `--minutes`, `--space-read`, `--gate-start` and the five set lines differ; `tests_env.py` in the start; the start answers as 2.0a's end; `live_accept.py`: the start's file and the ramp's 102 accepted; the trainer applied `live.json` before its first rollout; `start.log` beside this card. (A first try at 21:07 did not parse: a quoting mistake in a log line; nothing had run) |

## The end

**stopped 2026-11-10 07:21 at update 107 on the owner's word** (the end kept: update 100, `keep/policy_end_20b.pt`): 40.5, 35.0, 40.5% against the control at updates 10, 30, 50, then 30.0% at 70 and 27.0% at 90 as the inputs opened fully; he lost the big items head to head (megas 980 against 1713 at update 90); the pay by the place was never tested (0.2% of the pay's size when the fall came); the readout learnt (skill 0.66 to 0.77) ([postmortem](POSTMORTEM.md)).

## The owner's decisions

| | Decision | Recommended |
|---|---|---|
| 1 | The start | ✅ 2.0a's end (owner); looked at again after measurement 2 |
| 2 | The readout's places | ✅ the map's zones (at most 24) and the aggregate; the threat on him and what he puts on the enemy beside them (owner, 11-09: "looks good" to the recommendations) |
| 3 | The pay's end size | ✅ `EDGE_PAY` 0.0005 a damage-second (measurement 3: a tenth of the frags' size; a full minute at an edge of +20 pays 0.6 of a frag); `COVER_PAY` 0 |
| 4 | On the level or as a potential | ✅ on the level, zero-sum |
| 5 | The weapon table | ✅ the pros' (it is what a held line can do); looked at again if his own play makes it false |
| 6 | The gates | ✅ on the clock (rule 6: no hold): `SPACE_GATE` over updates 30 to 60, `EDGE_PAY` over 60 to 100; a readout not above its base rate at update 30 is a MAJOR line, not a hold. The two new attention tokens open by the trainer's own gate over the first 120 minutes |
| 7 | The holder seats | ✅ not in this run |
| 8 | Length | ✅ to 16:00 on 11-10 |
| 9 | Part 3's pay: flat by the place, or the judge reading the edge | ✅ **flat by the place first** (owner, 11-09: "I'm a bit skeptical of the judge just because it hasn't worked perfectly in the past, maybe we start with a pay per place and then transition to the win chance variant if it shows that it works"); the judge's variant after, if the flat one works |
| 10 | **Which flat quantity** ✅ (a) alone, (b) built at 0 | (a) **the edge**: a second pays `EDGE_PAY` × (the damage a second he puts on where the enemy is less what the enemy puts on where he is). Zero-sum by construction; it is the measured gap (he is under a heavy threat 18.0% of his time near the enemy, the pros 8.0%) and it runs his next 2 s from −7.6 to +6.7 damage. Sized ✅: at 0.0005 a damage-second its size is 0.11 a player-minute (a tenth of the frags'), a full minute at an edge of +20 pays 0.6 of a frag. (b) **the item ground's cover** (the card's first form): it says who takes the next big item (65% against 61% for who is nearer), sized ✅ 0.19 a player-minute at a frag a full minute, but the pros' leader does not hold more of it than his (+0.050 against +0.058). **Recommended: (a) alone first; (b) as a second dial at zero, opened only if the leader's cover does not rise by itself** |
| 11 | The edge pays the weapon that suits the distance ✅ kept | by the pros' table a rail in hand over 768 units puts 33 a second on a place, lightning 10: the edge pay is the first pay that prices the weapon by range, through the pros' numbers. The owner's rule is "the weapon untouched: read as an outcome". Recommended: keep it (it is the place's score "informing strategy and weapons", his words), read his weapon by distance in every check, and say so on the card; the alternative is the edge with both players' weapons set equal (position only) |

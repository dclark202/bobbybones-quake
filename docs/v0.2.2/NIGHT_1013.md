# The night of 2026-10-13: the test runs, their results, and the exploiter proposal

*A skeleton written 2026-10-13 17:50, to be filled in the morning when every run is done (the owner: "create a summary once they
are all done"; he hands it to the next session and decides on it). Every number comes from `scratchpad\gate_test\diag.log`
("arm X update N against the control, ten maps: 0.xxx") and `diag3.jsonl`; the records from `data\sim_runs\duel_gru_v0_2_1_dg<X>\metrics.jsonl`.
Background: [../v0.2.1/AUDIT_v0.2.1.md](../v0.2.1/AUDIT_v0.2.1.md) (what went wrong in v0.2.1), [RUN_v0.2.2.md](RUN_v0.2.2.md) (the next run).*

## 0. The report of 2026-10-14 16:00 (for the owner's go on v0.2.2)

Runs: all from v0.2.1's start network (v0.2's end converted), one against one, checked against the control (v0.2's end) in 160
ten-minute games on ten maps. A check's noise is about three points. **V** is v0.2.2's exact setting (whole games 75%, mid-game
starts 25%, the openings, no pull from the guessing game); **S** is V plus the revised guessing game and the slow memory (started
11:46 today, still training).

### 0.1 The numbers against the control

| Run | What it tests | U10 | U20 | U30 | Fixed clock |
|---|---|---|---|---|---|
| E | the 1v1 baseline, none of the new parts | 49.8 | 51.5 | | |
| P | guessing game, a tenth of its pull | 50.3 | 47.6 | | |
| Q | guessing game, no pull | 50.8 | 50.7 | | |
| **V** | **v0.2.2's setting** | **53.6** | **53.9** | **53.0** | **53.5** (U30) |
| H | every league match against the control (an exploiter) | 52.8 | 50.1 | | |
| B | V + the item rule silent under a fresh belief (`RULE_BLIND=10`) | 51.9 | 51.1 | | |
| **S** | **V + revised guessing game + slow memory** | **53.2** | **51.8** | | (born under it) |
| start | v0.2.1's start network | | | | 49.9 |

The fixed clock (B-249) moved nothing that matters: the start network reads level (49.9) and V30 53.5 against 53.0 before.

### 0.2 Counterplay, his biggest weakness (the owner, 2026-10-13)

His side of games against the control, four maps of 16; the pros from 1,043 duels of both players' own demos. "Ahead" = 50 or more
stack above the enemy and a big weapon; "weak" = 50 or more below or no big weapon.

| | pros | v0.2 | V30 | H20 | S10 | S20 |
|---|---|---|---|---|---|---|
| closing speed toward the enemy, ahead / even / weak (u/s) | 7 / -3 / 17 | 53 / 56 / 52 | 54 / 59 / 62 | 57 / 64 / 66 | 48 / 46 / 54 | 44 / 39 / 54 |
| a fight ends with the enemy dead: ahead / even / weak | .32 / .18 / .05 | .44 / .26 / .08 | .45 / .27 / .08 | .41 / .23 / .08 | .43 / .26 / .09 | .42 / .27 / .07 |
| a fight ends with him dead: ahead / even / weak | .03 / .15 / .31 | .08 / .27 / .38 | .07 / .22 / .38 | .08 / .25 / .42 | .06 / .25 / .39 | .08 / .20 / .38 |
| mega + red share: ahead / even / weak | .64 / .57 / .35 | .55 / .57 / .47 | .53 / .55 / .44 | .57 / .53 / .45 | .53 / .55 / .41 | .53 / .51 / .40 |

What the table says, plainly:
- **He always closes in** (50 to 65 u/s whatever his standing); the pros hold or close slowly, and close only a little faster when weak (to trade or reach an item).
- **He fights to a death far more**: an even fight ends in a death 53% of the time for him, 33% for the pros. When ahead he dies 2.5 times as often as a pro.
- **His item control barely follows his standing**: the pros take 64% of the mega and red when ahead and 35% when weak; he takes 55% and 47%. A pro ahead locks the map; he does not.
- **Who starts fights is not the gap**: both start about half, ahead or weak.
- **None of the night's runs moved it**: V (v0.2.2's setting), H (two hours of learning only the control) and S have the same shape as v0.2.
- **One hint, in S only**: his closing speed when ahead or even fell from V30's 54 / 59 to 48 / 46 at update 10 and 44 / 39 at update 20
  (weak unchanged at 54). Toward the pros' shape, but 64 games a measure and no noise figure for it yet: a hint, not a finding.
  Watch it at S30 and S40.

Why it persists: nothing in training pays for breaking off. His opponents are copies of himself who also always close, so
disengaging is never rewarded; the item rule's lesson (weight 2 to the run's end) names the next item whatever his standing; and
his memory reaches 10 to 30 s, so "I am ahead, he is weak and hiding" is rebuilt from inputs each time rather than remembered.

What in v0.2.2 aims at it: the whole games (a lead is worth something only over a whole game; two-minute rounds made every fight
cheap) and the openings; the guessing game with no pull (his belief of the unseen enemy); the item rule loosened. What is
missing: an opponent who punishes chasing (exploiters were tried: H found no hole), and pay for the state of the game (the win-chance
pay, `WIN_PAY`, built in stage B and never run). The slow memory is the part aimed at "remember what he does": too early to read.

### 0.3 The memory

**Today (v0.2, V):** a memory of 512 that ticks every frame, taught over a window of 9.6 s; what he did 20 s ago still moves his
choices a little, nothing older than about 100 s (tools/memory_reach.py). Over a ten-minute game he cannot remember the enemy's habits.

**The slow memory (built today, `sim/slowmem.py`, `--slow-mem 1`):** a second memory of 256 that ticks once every 1.2 s, fed a
squeezed copy of the fast memory and the mean of what he saw since its last tick; taught over 6.4 minutes (a ring of 320 ticks per
player kept on the host, 5.1 GB). His outputs read the fast memory plus the slow one through a door that starts shut, so he starts
exactly as he was and opens it only if it wins him games. The option the owner leans to (12:05): a tick every 0.6 s, taught over
3.2 minutes, at the same cost (`--slow-every 24`).

**What doubling the fast window would cost instead:** 768 steps (19.2 s) did not fit on the card (out of memory before its first
update); 384 steps peaked at 13.0 GB. The slow memory is the only way to minutes on this card.

**S so far:** an update takes 6.9 minutes against V's 5.7: **21% slower** (the estimate was 5 to 12%), so a 30-hour run gets about 260 updates instead of 315; card 13.0 GB; the door's share of his outputs .003 at update 1,
.047 at update 25 (opening slowly, as a new part with a shut door should); against the control 53.2 at update 10 (V 53.6) and 51.8 at update 20 (V 53.9): level at 10, two points under at 20, inside a check's
noise. **It does not hurt; whether it helps is not knowable today** (updates 30 and 40 in the 19:00 addendum).

**Now or v0.3?**
- For now: cannot hurt at the start (door shut); the owner's goal of counterplay needs memory of the enemy over minutes; a later restart with it means another conversion and another start.
- Against: 21% fewer updates in the same hours; no proof today that he uses it to play better (a check is three points of noise and the door is still mostly shut); the ring empties on every restart (about 40 updates to fill: a crash costs more); it is one more part in a run whose own parts (whole games, openings) are new.

### 0.4 The item rule (B against V)

B silenced the item rule wherever he believed he knew where the enemy was (fresh within 10 s): 77% of the rule's frames in his own
play. Against V (updates 11 to 20): items unchanged (mega .806 / .808 a player-minute, red .968 / .952), armor soaked 124.5 / 124.9,
the openings followed more (.78 / .73) and the targets reached more (.60 / .54); against the control 51.9 / 51.1 against V's 53.6 / 53.9.
Silencing three quarters of the lesson changed nothing he does with items: the rule is not what holds his item control.
**Recommendation:** v0.2.2 takes the loosening as the owner asked, in the mild form already in V (silent where nothing is left,
`RULE_CONTEST`), and B's `RULE_BLIND` waits: it lost two to three points, inside the noise but on both checks, for no gain on items.

### 0.5 The guessing game revised

The audit's two flaws fixed: every question is now labelled over its whole window, also on the last frames of a stretch (before,
many frames had no label), and nothing is asked in the first 5 s of a life before he has seen or heard the enemy (he cannot know).
`near` is asked only while the enemy is unseen, as `place` already was. A new measure sets his memory's guess beside his belief inputs. With no pull on his playing layers (V's setting). In S: his
memory's guess of the unseen enemy's place is 683 units off against the belief inputs' 445; the memory is nearer only 21% of
the time. **The guessing game teaches nothing yet that his belief inputs do not already say**; with no pull it costs nothing.

### 0.6 Exploiters: dropped

H trained only against the control for 20 updates: 52.8 then 50.1 (E 49.8 / 51.5). No hole found, and no counterplay learned (the
table above). Dropped on the owner's word (08:44).

### 0.7 The clock fixes, plainly

The checks used to reset his game clock, the score and his memory every two minutes, even for networks trained on whole games: they
were judged playing ten two-minute games instead of one ten-minute one. Fixed (B-249): a network trained on whole games plays a whole
game in the checks; the plugins on a server read the real game's clock and score the same way. Re-baselines: start 49.9, V30 53.5.

### 0.8 v0.2.2, part by part against the five goals

| Goal | V against E (records, updates 11 to 20) | Part of v0.2.2 | Still missing |
|---|---|---|---|
| 1. Speed and movement | speed 326 / 330 u/s, hops 13.9 / 14.0 a minute: unchanged | none new | the hop pay (`HOP_PAY`) is off; nothing new for strafe jumping |
| 2. Weapon use | rockets in hand 18% against 25% (LG 48% against 40%); hits unchanged (RL .45 / .44, RG .40 / .42, LG .38 / .39) | whole games | the rocket share fell: watch it in the play test |
| 3. Positioning | targets reached .52 / .52; openings followed 73% (start 21 to 27%), first big item 2.6 to 4.4 s (pros 1.9 to 2.3) | the openings, mid-game starts | holding places beyond the openings |
| 4. Counterplay | unchanged (0.2) | whole games; the guessing game; the slow memory (S) | an opponent who punishes chasing; pay for the game's state |
| 5. Beat people | 53.5% against v0.2 (fixed clock) | the whole run | the play test tonight |

**Recommendation: v0.2.2 go**, with V's setting (whole games, mid-game starts, openings, no pull from the guessing game, the item
rule loosened in V's form). The slow memory: the 19:00 addendum gives the call after S's checks at 30 and 40; on today's numbers it is level and
21% slower, and the owner's choice of a tick of 0.6 s is untried.

### 0.9 Open decisions for the owner

1. v0.2.2: go or not, and with or without the slow memory (the 19:00 addendum adds S's later checks).
2. The plugins at overtime: in a level duel the game's two-minute overtime periods are shown to him as the game's last two minutes
   again, period after period; the other way is to hold the clock at the end. The built default is the first; say if you want "hold".
3. The plugins' clock check on a private server: tonight at 19:00 as planned.

## 1. The runs, in order

All from v0.2.1's start network (v0.2's end converted), one against one, checked against the control (v0.2's end) in 160 ten-minute
games on ten maps at every tenth update. Level is 50%; the same network against itself reads about 49%; a check's noise is about
three points on the mean. For comparison, earlier today: none of the new parts with groups (F) 51.7% and 52.3%; the guessing game
alone at full pull (A) 43.9% and 41.8%.

| Run | What it tests | Update 10 | Update 20 | Update 30 | Notes |
|---|---|---|---|---|---|
| P | the guessing game (eight questions) with a tenth of its pull on his playing layers (`--aux-trunk 0.1`) | 50.3% | 47.6% | | step per update 0.021 to 0.022 throughout, the base's (full pull: 0.047) |
| E | none of the new parts: the 1v1 baseline | 49.8% | 51.5% | | |
| Q | the guessing game with no pull on his playing layers (`--aux-trunk 0`): a probe | 50.8% | 50.7% | | |
| V | **the pretest of v0.2.2's exact setting** (whole games 75% / mid-game starts 25% of the games' time, item and jump runs 10%, no weapon drills, the openings silent where nothing is left, no autopilot lesson, the guessing game as `place` and `near` at the pull chosen from P, E, Q) | 53.6% | 53.9% | 53.0% (53.5% under the fixed clock) | 30 updates: whole games reach 4:48 |
| H | **how exploitable is v0.2**: none of the new parts, every league match against the control (`--anchor-p 1.0`) | 52.8% | 50.1% | | 60% or more = the control can be played around in two hours of learning |
| B | v0.2.2's setting with the item rule silent under a fresh belief of the enemy (`RULE_BLIND=10`) | 51.9% | 51.1% | | judged against V |

The choice tonight made for v0.2.2's guessing game (by the rule in the runbook: P within three points of E → a tenth of the pull; else
Q within three → no pull; else out): **AUX_TRUNK = 0** (P was 3.9 points under E at update 20; Q within one point).

### The plan reviewed (2026-10-13 18:05, on the owner's word)

The night's build was rehearsed on a throwaway copy of the repo's three files before the evening's runs end: the four patches
apply, the six fixed sets are identical bit for bit with every new switch off, and a short run with V's and B's switches on goes
through. What a reader of the table must keep in mind:

- **Times** (each run's last check is 45 minutes after its last update): P about 18:30, E 20:50, Q 23:10, the build 23:10 to 23:35,
  V about 02:45, H 05:05, B 07:25.
- **Who is compared with whom.** P and Q against E (same rounds, one part apart). H against E (one setting apart). B against V at
  updates 10 and 20 (one switch apart). V against E is *not* one part apart: the rounds, the openings, the gate, the rule's silence
  in a contest and the guessing game all differ, so a low V says "not ready" and not which part; a level V is what the pretest asks.
- **One check is 160 games, about three points of noise.** The choice of the guessing game's form rests on single checks at update
  20; a P or Q within three points of E on either side is "no harm seen", no more. B against V likewise: read the records
  (items a minute, armor, the intention shares) beside the two numbers.
- **B is a large change, not a nudge**: under random play `RULE_BLIND=10` silenced 44% of the item rule's frames (the frames with a
  label fell from 43% to 26% of all). If his item numbers fall in B, a shorter memory (3 to 5 s) is the next thing to try, not the end of the idea.
- **V's whole games reach 4:48 of ten minutes** in 30 updates and the bank of saved moments starts empty: the pretest reads the first
  half of a game and few mid-game starts.
- **H's 60% line** is a judgment, not a measured threshold; E's number the same night is the real comparison.

### The owner's decisions since the plan was written (2026-10-13 evening to 2026-10-14 morning)

- The five goals weigh every change: speed and movement, weapon use, positioning, counterplay, beating people.
- The guessing game is opt-in: pull on his playing layers only if a test is level with the baseline (P was not; v0.2.2 takes it with no pull). The owner doubts the tests judged it fairly ("knowing the enemy location is exactly the way to play this game"): it is revised (the audit's two flaws fixed, asked only while the enemy is unseen, judged against his belief inputs).
- The item rule must be loosened in v0.2.2; its form from run B.
- Exploiters are dropped ("I honestly don't think exploiters are going to work at this point"; run H found no hole).
- A counterplay measure was built (tools/counterplay.py, the pros' side tools/counterplay_pros.py); the owner calls the pros-against-v0.2 table "arguably his biggest weakness": the report addresses it.
- The checks' two-minute reset of his clock, score and memory is fixed before v0.2.2's checks; the frozen "time left" input of two-minute networks in checks is repaired too (a new baseline follows); the plugins get the same clock.
- His memory: the learning window is 9.6 s and his memory reaches 10 to 30 s (tools/memory_reach.py). The owner: "make the easy updates now with v0.2.2, then expand the memory to minutes and that becomes v0.3", then (2026-10-14 09:00) build the longer memory now and test whether it belongs in v0.2.2: report at 16:00 with pros and cons, an addendum at 19:00 if the memory test runs long.
- Weapon use is measured at every check (aim stability).
- The evening of 2026-10-14 (the owner, 11:58: "Do that exact plan"): the report at 16:00; at 19:00 an addendum, and the slow-memory
  test run (arm S) stops right after its update-40 save; the game server image is rebuilt with the day's code and the plugins' clock
  checked on a private server (not the public one); v0.2.2's pretest network (V, update 30) and S's update-40 save exported; the owner
  plays them about 19:30, then decides overnight: resume S (its six minutes of stored past start empty again) or start a new
  training session with the slow memory in.

## 2. What the records say (fill in)

- **V, the openings:** share of his lives with an opening's label (`openings.with_opening`), his agreement with the label
  (`openings.agree`; the start network: 21% on Blood Run, 27% on Aerowalk), seconds to the first big pickup (`openings.first_big_s`;
  the start: 4.8 s Blood Run, 3.2 s Aerowalk; the pros: 2.3, 1.9), the share of games' time in mid-game starts (`moments.time_share.mid`)
  and moments saved; `rule_contest`; `vs_anchor_kill_share` (now counted in 1v1 normal rounds and whole games only).
- **H, the exploiter:** what changed against the start network: `v14.in_hand` (the weapon in hand), `fire_in_view`, the intention
  shares (`intent` / `place` fields), `armor_soaked_per_player_min`, the lives' kinds in the check's json (`h2h_dgH_20_<map>.json`).
- **B, the silent rule:** `rule_blind` (the share of the rule's frames silenced), intention shares, items a minute, armor soaked, against V's.

## 3. The exploiter proposal (dropped on the owner's word, 2026-10-14 08:44; kept as written)

**Why.** His opponents in training are copies of himself (the last eight saves and the control). Nobody in the league plays around
him, so countering is never rewarded; an experienced player is exactly the opponent the league lacks. Run H measures how far a learner
gets against the control in two hours when that is all it does.

**What.** Exploiters in the league: a copy of him trained against him alone (`--anchor-p 1.0` against the frozen network, twenty
updates), saved as an anchor (`snapshots/anchor_exploit_<n>.pt`), so that a share of his league matches are against something that
has learnt him. The trainer already draws anchors in a share of the league matches (`--anchor-p`); the exploiter files only need to
be there. Two or three exploiters, refreshed against the current network every few hours of a run (the refresh costs the card: a
pause of the run, or a smaller exploiter trainer beside it).

**Cheapest first step.** Run H's end network *is* an exploiter of the control. If H reads well above 50%, v0.2.2 can start with it as
a second anchor beside the control, at no further cost; the mid-run refresh is the follow-up.

**What it is not.** No new pay, no new input: the opponents change, nothing else.

## 4. Recommendation (the morning's frame; the report is section 0)

The owner (2026-10-13 evening): one report once B is done, giving the best guess at what goes into the next full run (one against
one: whole games and some mid-game starts), part by part against his four goals, for his decision in the morning:

1. keeping speed and moving well through the map;
2. the right weapon for the moment;
3. good positions;
4. counterplay: pressing when stacked against a weak enemy, no fights when weak, taking or keeping away from items.

For each goal: what the night's records show (speed and hops, `v14.in_hand` and hits by weapon, `v14.height` and the places,
kills and deaths by stack in the checks' lives), which part of v0.2.2 serves it, and what is still missing.

- v0.2.2: go / not yet, and why (V against E; the openings' numbers).
- The guessing game: the form chosen, and what P, E, Q say about the diagnosis of B-246.
- The item rule (B against V): into v0.2.2, into v0.2.3, or dropped.
- The exploiter (H): into v0.2.2 as an anchor, or not.

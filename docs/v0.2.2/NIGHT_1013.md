# The night of 2026-10-13: the test runs, their results, and the exploiter proposal

*A skeleton written 2026-10-13 17:50, to be filled in the morning when every run is done (the owner: "create a summary once they
are all done"; he hands it to the next session and decides on it). Every number comes from `scratchpad\gate_test\diag.log`
("arm X update N against the control, ten maps: 0.xxx") and `diag3.jsonl`; the records from `data\sim_runs\duel_gru_v0_2_1_dg<X>\metrics.jsonl`.
Background: [../v0.2.1/AUDIT_v0.2.1.md](../v0.2.1/AUDIT_v0.2.1.md) (what went wrong in v0.2.1), [RUN_v0.2.2.md](RUN_v0.2.2.md) (the next run).*

## 1. The runs, in order

All from v0.2.1's start network (v0.2's end converted), one against one, checked against the control (v0.2's end) in 160 ten-minute
games on ten maps at every tenth update. Level is 50%; the same network against itself reads about 49%; a check's noise is about
three points on the mean. For comparison, earlier today: none of the new parts with groups (F) 51.7% and 52.3%; the guessing game
alone at full pull (A) 43.9% and 41.8%.

| Run | What it tests | Update 10 | Update 20 | Update 30 | Notes |
|---|---|---|---|---|---|
| P | the guessing game (eight questions) with a tenth of its pull on his playing layers (`--aux-trunk 0.1`) | 50.3% | 47.6% | | step per update 0.021 to 0.022 throughout, the base's (full pull: 0.047) |
| E | none of the new parts: the 1v1 baseline | | | | |
| Q | the guessing game with no pull on his playing layers (`--aux-trunk 0`): a probe | | | | |
| V | **the pretest of v0.2.2's exact setting** (whole games 75% / mid-game starts 25% of the games' time, item and jump runs 10%, no weapon drills, the openings silent where nothing is left, no autopilot lesson, the guessing game as `place` and `near` at the pull chosen from P, E, Q) | | | | 30 updates: whole games reach 4:48 |
| H | **how exploitable is v0.2**: none of the new parts, every league match against the control (`--anchor-p 1.0`) | | | | 60% or more = the control can be played around in two hours of learning |
| B | v0.2.2's setting with the item rule silent under a fresh belief of the enemy (`RULE_BLIND=10`) | | | | judged against V |

The choice tonight made for v0.2.2's guessing game (by the rule in the runbook: P within three points of E → a tenth of the pull; else
Q within three → no pull; else out): **AUX_TRUNK = ___**.

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

## 2. What the records say (fill in)

- **V, the openings:** share of his lives with an opening's label (`openings.with_opening`), his agreement with the label
  (`openings.agree`; the start network: 21% on Blood Run, 27% on Aerowalk), seconds to the first big pickup (`openings.first_big_s`;
  the start: 4.8 s Blood Run, 3.2 s Aerowalk; the pros: 2.3, 1.9), the share of games' time in mid-game starts (`moments.time_share.mid`)
  and moments saved; `rule_contest`; `vs_anchor_kill_share` (now counted in 1v1 normal rounds and whole games only).
- **H, the exploiter:** what changed against the start network: `v14.in_hand` (the weapon in hand), `fire_in_view`, the intention
  shares (`intent` / `place` fields), `armor_soaked_per_player_min`, the lives' kinds in the check's json (`h2h_dgH_20_<map>.json`).
- **B, the silent rule:** `rule_blind` (the share of the rule's frames silenced), intention shares, items a minute, armor soaked, against V's.

## 3. The exploiter proposal (for the owner's decision)

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

## 4. Recommendation (fill in the morning)

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

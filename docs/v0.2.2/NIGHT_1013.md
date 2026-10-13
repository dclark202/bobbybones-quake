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
| P | the guessing game (eight questions) with a tenth of its pull on his playing layers (`--aux-trunk 0.1`) | 50.3% | | | step per update 0.022, the base's (full pull: 0.047) |
| E | none of the new parts: the 1v1 baseline | | | | |
| Q | the guessing game with no pull on his playing layers (`--aux-trunk 0`): a probe | | | | |
| V | **the pretest of v0.2.2's exact setting** (whole games 75% / mid-game starts 25% of the games' time, item and jump runs 10%, no weapon drills, the openings silent where nothing is left, no autopilot lesson, the guessing game as `place` and `near` at the pull chosen from P, E, Q) | | | | 30 updates: whole games reach 4:48 |
| H | **how exploitable is v0.2**: none of the new parts, every league match against the control (`--anchor-p 1.0`) | | | | 60% or more = the control can be played around in two hours of learning |
| B | v0.2.2's setting with the item rule silent under a fresh belief of the enemy (`RULE_BLIND=10`) | | | | judged against V |

The choice tonight made for v0.2.2's guessing game (by the rule in the runbook: P within three points of E → a tenth of the pull; else
Q within three → no pull; else out): **AUX_TRUNK = ___**.

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

- v0.2.2: go / not yet, and why (V against E; the openings' numbers).
- The guessing game: the form chosen, and what P, E, Q say about the diagnosis of B-246.
- The item rule (B against V): into v0.2.2, into v0.2.3, or dropped.
- The exploiter (H): into v0.2.2 as an anchor, or not.

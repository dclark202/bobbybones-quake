# 1.7b: the build

The approved design is [CARD.md](CARD.md) (owner, 2026-11-06 evening: decisions 1 to 9 taken; "let's start 1.7b now"; "Just keep 1.7b as
we agreed"). Branch `b17b` in the main checkout (from `main` at b0c7ef5, which has 1.7a's code). Nothing of the card is left out or
replaced by a simpler stand-in (CLAUDE.md rule 10); a detail the card leaves open is decided here from its intent and marked
**(detail)**; a real fork goes to the owner. The run starts on the owner's go ("let's start 1.7b now") once every test below passes.

**State (2026-11-06, 21:47): every part built and tested (below); ready to start on the owner's go (given: "let's start 1.7b now").**

**Marks:** ✅ built and tested · 🔨 built, its test running · ⏳ to build · ❓ owner's decision

## The parts

| # | Part (card) | Where | State |
|---|---|---|---|
| 1 | The yellow armors' timers: 4 inputs (each yellow: known taken, the seconds since against 25 s), from the item belief every player already keeps (`bel_t`, ITEM_BELIEF: taken by him, heard taken, seen empty); the head reads them and the heard mega and red armor timers (`memory`) | `sim/duel_env.py` (`N_YT`, `_yt`), `tools/make_ffa_env.py` (regenerated), `tools/list_inputs.py` -> `docs/INPUTS.csv` (994), `sim/attn.py` (token kind `timers`, in `DROP_SHUT`), the start tool | ✅ (`ident.py`: the game the same to the bit as 1.7a's code, the 4 inputs in [0, 2], known 27 to 33% of the time) |
| 2 | The fight odds: the brain's readout of how the fight now ends (the enemy dies first, he dies first), labelled in hindsight by the simulator (`FIGHT_TRUTH`), a lesson only; the head reads its two chances | `sim/duel_env.py` (`FIGHT_TRUTH`, `FIGHT_H` 5 s, `FIGHT_PRE` 1 s, `_fight_step`), `sim/fightodds.py`, the trainer (`--fight-odds`, live `FIGHT_W`), `sim/head2.py` (part `fight`, `fight_t`, `np_fight`), `sim/test_suite.py`, `plugins/netpass.py`, `sim/export_duel.py` | ✅ (`ident.py`: labels only, the game the same to the bit; `tests.py ident`: the lesson on moves nothing to the bit; `smoke`: see below) |
| 3 | Break off reached by living through it: 1.5 s with neither seeing the other and no damage either way | `sim/duel_env.py` (`OUT_LIVE`, the quiet clock `out_qt`, `_cmb_arrive`), `plugins/duelbot.py` (the clock, as for `khit_t`) | ✅ (`ident.py`: off, the same to the bit; on, break off reached 21 -> 648 and 37 -> 596 times on the two maps, the other kinds' arrivals as before) |
| 4 | The order's two dials: `H2_OPG` (the order's share of the head's term) and `ORD_KL` (a KL to the frozen start's order) | the trainer (`--head2-opg`, `--ord-kl`; live `H2_OPG`, `ORD_KL`), `sim/head2.py` (`order_scores_fixed`, `order_kl`) | ✅ (`tests.py live`: the dials applied and played; `smoke`: see below) |
| 5 | The start: 1.7a's update 90 given parts 1 and 2 at zero effect and the frozen order copy; plays as update 90 to the bit | `tools/b17b_init.py` (`add`, `widen-league`, `same`) | ✅ `same`: 0 actions differ, at the files' own shares and at the keep choice's and the order's share 1 with random keep numbers and candidates (300 frames x 8 seats) |
| 6 | Cypher's measures in every check | `tools/duel_eval.py` (`CY_REC`, off by default), `tools/run/cypher_measure.py` (`summarize`, mode `check`), `tools/run/watch.py` (`CHECK_CYPHER=1`: a line in watch.log and `watch/cypher.jsonl` a check) | ✅ (a one-map check with `CY_REC` wrote its summaries and read back) |
| 7 | The run's files: command, ramp, start script, tests, settings check against 1.7a's command | `docs/runs/1.7/1.7b/` (`make_files.py`, `train.cmd`, `ramp_17b.py`, `start.ps1`, `tests.py`, `ident.py`) | ✅ the settings check: only the named differences; `tests.py start`, `ident`, `live` ALL PASSED; `smoke`: below |
| 8 | The servers' latency with parts 1 and 2 (before any deploy, not before the start) | a private server, `DUEL_TIMING` | ⏳ |

## Details decided from the design's intent

| Part | Detail | Why |
|---|---|---|
| 1 | the yellows' timers read the item belief every player already keeps (`bel_t`, ITEM_BELIEF): taken by him, heard taken (`SENSE_MINOR`'s error), or seen empty (counted as taken half its time ago); the plugins feed the same books through `observe()` | the mega's and the red armor's "memory" timers are kept by pickups only; `bel_t` is the belief the chosen item's "comes back in" has used since 2026-10-08, kept on the servers already: no new state, no new cost a frame |
| 1 | the timers' attention token stays shut all run (left out: `DROP_SHUT`); the hands read the four through the encoder (`enc.0`, zero weights at the start), the head through its own inputs | opening a token whose first layer is random moves the attention sums at once (the order's token needed a gate and its own dial); the encoder reads every input, so nothing is lost |
| 1 | the head's new inputs: the heard mega and red timers (`memory`: 4) and the yellows' (4), at the end of its obs part | the card: "the head's inputs also take the four memory timers (heard, not only his own)" |
| 2 | the fight label: a frame with both alive in a duel's game and damage either way between the two within 1 s after it (a fight on); its result the first death within 5 s (the enemy first: win; he first: lose; one frame: both; neither: both 0, he got away); a round end inside the window: no label | B-304's fights (damage either way, a death within the fight or soon after); 5 s: most of his fights are over in 2 s (B-304: median 1.7 to 2.3 s), the brain's look-ahead reaches 4 s |
| 2 | the readout reads the brain's state and his hands' memory ("both": the brain knows the enemy, the hands' memory his own stack), kept every brain tick in a ring; its own Adam (sim/control.py's pattern: nothing of it reaches the policy) | Cypher: who wins comes from both stacks; the "in control" readout's "both" read more than the brain alone (the probe of 2026-10-24) |
| 2 | the head's part "fight": the two chances minus 0.5, between ctrl and obs | as the ctrl part reads "in control" |
| 3 | break off reached when for 1.5 s **he has not seen the enemy** and no damage has gone either way (the card said "neither has seen the other") | he cannot know whether the enemy sees him; the arrival is one of the keep choice's inputs, so it must come from his own senses (the fairness rule) |
| 3 | a way out that is an item still ends the order when he gets there (taken) | an item taken is gone as a target; as 1.7a |
| 4 | `H2_OPG`: the order's log-probability in the head's own term scaled in its gradient, not its value (`c lo + (1 - c) lo.detach()`): the ratio as it is, the order's layers still at 0 | "the head frozen on the order" while it is asked at the start's rate |
| 4 | the KL: from the reference (the start's order layers with the head's state at zero) to the head's, over the kinds and within each new kind over its candidates weighted by the reference's chance of that kind (forward KL: a kind the pros use cannot go to zero); on the readings the order is asked at; its two pulls on the kinds' logits (the KL's per unit weight, the head's term's) recorded every update for the sizing | AlphaStar's KL to the human policy; the card's "its size from the first updates" |
| 5 | the order's reference checked equal to 1.7a's save of update 10 (before the order was ever asked) | the reference is the pros' fit of 1.7a's start, as the card says |

## The tests (2026-11-06 evening, on the CPU, no run training)

| Test | Result |
|---|---|
| `tools/b17b_init.py same` (`tests.py start`) | ALL PASSED: 0 actions differ against 1.7a's update 90, at the files' own shares and at share 1 with random keep numbers and candidates |
| seeded games, the start against update 90 (Blood Run, `tools/duel_eval.py`) | the whole result the same to the last number |
| `ident.py` (the simulator, 1.7a's code at HEAD against today's, Blood Run and Aerowalk) | ALL PASSED |
| `tests.py ident` (the trainer, a fixed seed, two updates) | ALL PASSED: the start with the fight odds' lesson on, the labels and the new break off = without them, to the bit; the optimizer's state loaded and carried over the widened inputs; the order opened changes play |
| `tests.py live` | ALL PASSED: the start's live.json applied; H2_OPG, ORD_KL, FIGHT_W written after update 1 played |
| `tests.py smoke` | ALL PASSED (442 small updates, every dial open): the fight odds labelled every update, Brier 0.25 -> 0.10 against the best constant's 0.21; the order's KL recorded (divergence 0.0015 to 0.002, both pulls); every kind followed; break off reached by living 259 times, cut off 48, spam 278; no NaN; the save carries the readout, the reference, the head's part; a restart loads the optimizer; a one-map check of the save against update 90 finishes |

## Found on the way

- **The checks' player and the servers' forward pass read the order's validity flags as the legs' way flags** (`sim/test_suite.py` and
  `plugins/netpass.py`, since 1.7's build, 11-05): at an order reading `ok_` (the legs' "a way" flags, read by the legs gate later in the
  same frame) was overwritten by the order's "a valid candidate" flags. Only a network with the order asked is touched: 1.7a's checks from
  update 90 on played the learner's legs gate on the order's flags one frame in eight (the control, 1.6a's end, has no order); the
  public servers' networks have no order. Fixed (`okc_`). Whether it moved 1.7a's later checks: one check of a later save with the fixed
  player would tell (not run: the owner's call).
- **The check tools refused a network with fewer inputs than the list** once the timers were in (`fit_list` trimmed only the order's group):
  every check of 1.7b against 1.7a's update 90 would have failed. Fixed in `tools/duel_eval.py`, `tools/run/dump_eval.py`, `ws_eval.py`.
- **The trainer counts input positions from the end** in three places (the brain's 868 inputs, the guessing game's belief columns, a fresh
  encoder's random stream) and `sim/head_data.py` in one: each now subtracts the timers too.

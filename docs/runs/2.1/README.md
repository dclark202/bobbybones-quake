# 2.1: he commits on his own (the lock out), learns what a spot is worth (map sense), and the "should I do X?" method is proven

**The family's design (owner, 2026-11-14). No run is carded yet.** The round order was agreed on 11-14 ("Ok this is good"):
2.0e (aim, dodge, cleaned inputs) → **2.1** → [2.2](../2.2/README.md) (new decisions, the question loop) → [2.3](../2.3/README.md) (the head
sets the weapon). The plain-words explanation, the red team and the Research check are in [PLAN_FROM_20E.md](PLAN_FROM_20E.md).

Superseded, kept as they were: [DESIGN.md](DESIGN.md) (the full 11-10 design: still the reference for the questions S1-S9 / A1-A6, the
verbs and the frozen moment), [PLAN_FROM_17A.md](PLAN_FROM_17A.md), [2.1a](2.1a/CARD.md) (the instruction as a separate chooser; RUNS.md #51).

**2.1c (2026-11-15): the lock out by the held draw.** 2.1b's stay value never learned from its forks (RUNS.md #54). 2.1c drops the
keep choice and the judge: his draw's random numbers are rolled once per trip and held, so his goal changes only when his own scores cross,
and the head reads the goal he holds. Built and tested, waiting for the owner's go: [2.1c/CARD.md](2.1c/CARD.md).

**2.1d (2026-11-15, ended 11-16 at update 158): the pull. The lock is out and he holds his level** (52.0% against 2.1c's end, 55.0% against 2.0e's end; 31.5% with the pull at 0). The slow plan moved inside the head and its 2-second odds, times a strength, added to his goal
scores; the held share to 1.0 by update 110 (the lock out). [2.1d/CARD.md](2.1d/CARD.md), RUNS.md #56.

**Decided (owner, 2026-11-15 evening): the head gets a slow half, whatever 2.1d's result.** "We're basically expanding the current head with
a slower half, to handle long term planning ... I think we should plan to do this anyway, since it sounds like it makes the goals of 2.n
more achievable as well. And there's precedent for it with other bots." The form agreed in the chat: a recurrent memory of its own (about
128) beside the head, ticking every 2 seconds and at a trip's end, its state fixed between ticks; it reads the head's state, the goal he
holds and its age, and the brain's picture; the plan's odds are read from it (so the pull's bar is fixed between ticks); the head reads it
back as an input at zero weight. It learns silently by the plan's own lesson (his fast odds ahead), then the pull's source is blended from
today's plan to it (rule 13); rule 11 on the sum from the start. From DeepMind's Capture the Flag agent (FTW: a slow core as a prior for the
fast one; `docs/research/BOTS.md` 13.2). Why for 2.2: the plan and pull work on any choice list (more choices = more near-ties), a long play
(hold an angle until an item spawns) needs a holder, the slow inputs (map sense, item timings, control) enter there, a decision every 2 s
gets cleaner credit, a new choice can be forecast silently before it is played. Open: the tick length (hand-set), the plan's output widens
with 2.2's choices, whether the trainer's older `--slow-mem` part can be reused. Not designed in detail, not built: its card (with the
research check) comes after 2.1d's result.

**The family is closed (owner, 2026-11-16 evening): 2.1 met its goal, the lock is out (2.1d). The outlook of 2.1f runs as 2.2a:
[../2.2/DESIGN.md](../2.2/DESIGN.md).**

**2.1e (2026-11-16, stopped at update 50): the slow half as built is a slow duplicate of the pull; harmless, no gain** ([card](2.1e/CARD.md), RUNS.md #57). **Next: [2.1f](2.1f/CARD.md), an outlook for each goal** (owner, 11-16: "the more principled design. It adds a genuine new signal, the hypothetical future value"), built on branch `b21f`; see [2.1f/HANDOFF.md](2.1f/HANDOFF.md). 2.2 and 2.3 were rewritten the same day from how 2.1 ended ([2.2](../2.2/README.md), [2.3](../2.3/README.md)).

## The goal

2.0e's end, with nothing new choosing his goal, brought to where 2.2 can add decisions: he keeps or drops a goal by a learned part (no
8-second lock), he can stay at a place he reached, a map sense learns from his games, and one question of the "should I do X?" kind
(keep my goal or change it) is taught from frozen moments and shown to work.

## Decided (owner, 11-14)

| # | Decision |
|---|---|
| 1 | Starts from **2.0e's end** (1.6a's line), if it passes the owner's play test |
| 2 | **Nothing new chooses.** The target stays the sum of the hands' rows and the head's scores (1.3b), 17 targets. The instruction's separate chooser (1.9a, 2.1a) is not used |
| 3 | **The lock comes out only after its replacement is in and shown to hold**, in two parts: fights and arrivals first, the quiet hold second |
| 4 | The replacement is the **keep choice that exists** (1.7a's), with what 1.7a lacked: a **stay value** taught from frozen moments over the whole trip, running to the run's end, and a quiet reading that sees only what can justify a change |
| 5 | **Measured before trained** (M1 to M3 below); M1 gates steps C and D |
| 6 | No new options, no question loop, no weapon hand-over: those are 2.2 and 2.3 |
| 7 | One step opens after the other; each ends on its measure, reported; nothing holds or steps back on its own; a mark with its optimizer at each step's end |

**Answered 11-14 (afternoon):** 1. the owner asked for a recommendation ("fitting has proven to be a shit move"): built as a ZERO start
learning silently toward the stay value's sign (the fitted start kept as an option; 2.1b/BUILD.md decision 1). 3. **one run**, A to D (it
may run on Sunday by day). 4. **2.2's first step**. 2. open until M1's numbers are in.

## Open for the owner (asked 11-14; my recommendation first)

1. The keep choice **starts as the lock made soft** (`tools/keep_init.py`: a fitted start, share 0 identical). Allowed, or out under rule 13?
2. If M1 shows no usable signal: **(c) stop after step B** and keep the quiet hold on the lock; first try (a) more forks an update; (b) a
   deliberation cost only on the owner's word (a hand-set price).
3. **Two runs**: A + B, the owner's play test, then C + D. Or one.
4. The map sense as head inputs: **2.2's first step**, or 2.1's step D. It learns silently in 2.1 either way.

## The steps

| Step | What opens | What plays | Its measure |
|---|---|---|---|
| A. Silent | frozen moments (keep against a new draw), the stay value's lesson, the map sense's lesson | 2.0e's end, the lock | the stay value's sign right on held-out moments above a mark the owner sets; map sense skill; checks level |
| B. Fights and arrivals | the keep choice's share 0 → 1 **in contact and at arrivals only** | five readings a second in a fight; an arrival can be kept; quiet = the lock | trips and reached out of contact unchanged; weapon in hand by range; megas and reds; **the owner's play test** |
| C. Quiet | quiet readings pass from the lock rule to the keep choice's quiet reading (the stay value + the change signals), share 0 → 1 | the lock's hold leaves his seats | quiet re-decisions a reading at or under step B's; reached not down |
| D. The lock out | the lock's last share out; (decision 4) the map sense's inputs to the head, gate shut → open | all his own | the same guards; the map inputs' health report; 200 games with them blanked |

## Where the code is

| Part | Built | Files |
|---|---|---|
| The lock rule | yes | `sim/duel_env.py` `intend()` (the line `may = (self.intent == 0) \| self.intent_done \| (self.intent_t >= INTENT_HOLD) \| ...`), `INTENT_HOLD`, `CONTACT_FREE` |
| The keep choice: its layer, start, share | yes (1.4c, 1.7a) | `sim/head2.py` `has_keep`, `keep_x`, `keep_logit`, `np_keep_logit`; `tools/keep_init.py add / same`; the trainer's `--keep-g` (live `KEEP_G`), `--keep-freeze`, `keep_group`, the record `keep` (`KEEP_ACC`, `sim2.redecide_quiet`) |
| Arrived against ended, the keep choice's seven numbers | yes (1.7a) | `sim/duel_env.py` `intent_arr`, `arr_t`, `kown`, `keep_feat()`, `note_hunt`, `note_holds`, `stats["keep2"]` |
| Frozen moments | yes; ran in 2.1a | `sim/branch.py`; `sim/duel_env.py` `_moment_take`, `_moment_set`; the trainer's `--branch`, `--branch-p` (live `BRANCH_P`), `--branch-hold`, `--branch-win`, `--branch-quiet-p`, `--branch-long*` |
| The forecast of a target's outcome | yes; learnt nothing in 2.1a (9,104 moments, about 240 an update) | `sim/appraise.py` (outputs dealt, taken, he_dies, i_die, item, dv, dv_long); `--appraise` |
| The frozen moment as a measurement | yes, for 1.7a's update 90 and targets x repeats | `tools/run/branch_test.py`, `branch_hook.py`, `branch_record.py` |
| Map sense | yes; a lesson only | `sim/mapsense.py`; `--map-sense`, `--map-sense-init`, `--map-sense-pull`; `tools/run/mapsense_init.py`, `seed_calib.py`, `seed_calib2.py`; `data/sim_runs/space/mapsense_start.pt`, `data/maps/space_<map>.npz` |
| The change signals | yes, inside the instruction's code | `sim/duel_env.py` `INS_SIG`, `INS_SIG_WAKE`, `_ins_step` (behind `INSTR=1`) |
| The run tools on 1.6a's line | yes (2.0e) | `docs/runs/2.0/2.0e/` (`make_files.py`, `start.ps1`, `ramp_20e.py`, `start_live.py`, `smoke.py`); `tools/inputs20d.py --list 20e`; list 20e |

## To build

**Built 11-14 for 2.1b (branch `b21b`): 1 to 6 and 8; 7 not built** (owner: the map sense into the head is 2.2's first step). What was
built, the decisions taken while building and the tests: [2.1b/BUILD.md](2.1b/BUILD.md).

| # | What | Where | Notes |
|---|---|---|---|
| 1 | The keep choice on 2.0e's end at share 0 | `tools/keep_init.py add` on a network of list 20e; `same` | to verify: it was written for the full-width networks; the optimizer gains the `keep` group (2.0e's saves carry group names or not: check the trainer's resume chain) |
| 2 | **A switch that limits the keep choice to contact and arrivals** (quiet readings stay with the lock rule) | `sim/duel_env.py` `intend()`, where the coin `kown` gives a second to the keep choice; then `tools/make_ffa_env.py`, `tools/ffa_check.py` | off = bit-identical; live, with its `LIVE_RANGE` and a `tests.py live` case |
| 3 | The frozen moment **keep against a new draw**: the same moment with the held target forced and with a draw forced, at quiet moments, in contact and at arrivals | `sim/branch.py` `plan()` (which moments, `prefer`), the trainer's branch code | the window must cover a trip: `--branch-long` (30 s) for quiet moments |
| 4 | **The stay value**: "keeping beats a new draw by this much", from the forks | `sim/appraise.py` asked of the held target and of the head's own draw; or a two-way head of its own | M1 decides which; its skill is recorded every update |
| 5 | **The keep choice's quiet reading**: in quiet it reads the stay value, the change signals and the age only (not the head's whole memory), and is taught toward the stay value's sign all run | `sim/head2.py` (a second small layer beside `keep`, rule 11 if it is summed with anything), the trainer's keep term | the change signals taken out from behind `INSTR` |
| 6 | The ramp and its flags: quiet re-decisions, trips, reached, the stay value's skill, forks an update; a crashed flag thread logged and restarted | from `docs/runs/2.0/2.0e/ramp_20e.py` | flags tested on real lines of a smoke run |
| 7 | (decision 4) The map sense as head inputs: at his place (8 numbers) and at each target's place, measured statistics, zero weights, a shut gate | `sim/head2.py` `PARTS`, `layout`, `feats`; the trainer; `tools/` a widening tool with `same` | 2.0b's lesson: slow gate, a blank test at the end |
| 8 | The server side for a play test of each step | `plugins/duelbot.py`, `plugins/netpass.py`, `sim/export_duel.py` | the keep choice played on servers in 1.7a's time; list 20e, the dodge inputs and AIM3 on a server are open from 2.0e |

## Before any training (measurements, no run)

| # | What | Tool | Decides |
|---|---|---|---|
| M1 | Keep against a new draw on 2.0e's end and on 1.7a's update 90: how often a new draw wins, by how much, by quiet / contact / arrival and by age; how many moments tell the sign | `tools/run/branch_test.py` adapted (it forces targets on 1.7a's update 90 today) | whether steps C and D can be built; forks an update needed. 1.7a's quiet re-decisions must show as losing: if not, the instrument is wrong |
| M2 | 2.0e's end with the keep choice's fitted start in contact and at arrivals only, against 2.0e's end, 200 games, no learning | `tools/duel_eval.py` after builds 1 and 2 | what step B is worth untrained; whether it moves the weapon in hand |
| M3 | The map sense's skill on 2.0e's recorded games; its start file re-fitted | `tools/run/mapsense_init.py`, `seed_calib2.py` | its start |

## Guards from update 1 (reported; the owner decides)

Quiet re-decisions a reading; trips a player-minute; targets reached; frags a match-minute; megas and reds head to head; the panel's
camping and spawn-camping measures (a keepable hold can become camping: v0.4.3); the weapon in hand by range (a readout); every check
against 2.0e's end, one under 40% flagged at once.

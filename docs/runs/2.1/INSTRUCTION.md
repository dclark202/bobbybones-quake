# 2.1: the instruction (what the head sends the hands), as built on branch `b21`

*2026-11-11. Built while 1.8a trains, in the worktree `BobbyBones-21`; nothing of it has run. The design: [DESIGN.md](DESIGN.md),
[../../design/STRATEGY_2.md](../../design/STRATEGY_2.md). Where the design left a detail open it is decided here from the design's
intent and marked **(decided here)** for the owner's review (CLAUDE.md rule 10).*

## The instruction

Five fields, set by the head every 0.2 s (in drills: by the drill), held by the keep choice:

| Field | What | Comes from |
|---|---|---|
| verb | go, contest, hold, spam, push, cut off, break off, check; or none | the head's choice |
| quiet | 0 or 1: asked to be quiet (second pass; nothing forces the walk key or pays for it) | the head's choice |
| place | where to be | an item, a holding place, the brain's believed or forecast place of the enemy, a fallback |
| point | what to watch or shoot | an opening or a point on the enemy's believed way; none for go and break off |
| weapon | what to have in hand | one he owns with ammunition (others cannot be chosen) |
| when | seconds until the enemy is expected at the point; none if unknown **(decided here)** | the brain's forecast (1, 2, 4 s ahead; the pass odds) |

Everything about the enemy in it is the brain's belief, never the truth. `when` is added because a rocket on a point is only worth
firing if it arrives as he does: the hands need the two times side by side.

## The verbs: what each means, when it is "being done", done, and failed **(decided here)**

The state is one of: on the way, doing, done, failed. It is read by the hands (as inputs), by the head and the keep choice (as change
signals), by the appraisals (as what the instruction brought) and by the drills (when a drill ends). Nothing is paid for a state.

| Verb | Place, point | Doing | Done | Failed |
|---|---|---|---|---|
| go | an item or a place; no point | never (it is a passage) | he is within the pickup reach of the place (36 units each way), or took the item | the item was taken by the enemy first |
| contest | a big item's ground; the point = the way the enemy is believed to come | on the ground (within 96 units) before the item is back | he took it | the enemy took it |
| hold | a holding place; an opening | within 48 units of the place with the weapon in hand | never by itself: it lasts until the head changes it | pushed off: more than 128 units from the place after having been in place |
| spam | where he fires from (may be where he stands); a point on the enemy's way | in place, the weapon in hand, the point within reach of the weapon | never by itself | the weapon has no ammunition |
| push | the enemy's believed place; the point = the same | the enemy noticed in view | the enemy died | never by itself |
| cut off | the brain's forecast of his place 1, 2 or 4 s ahead; the point = where he is believed to come from | within 96 units of the place | the enemy was noticed in view after he arrived | 2 s past the forecast's time with no sighting |
| break off | a fallback: the nearest cover with something worth having | never (it is a passage) | 1 s out of the enemy's sight and more than 400 units from his believed place | never by itself |
| check | where he can see the place the brain expects the enemy at; that place | on his way | his eye has a clear line to that place, or the enemy is noticed in view | never by itself |

His death ends any instruction. A candidate whose weapon he does not own, or has no ammunition for, cannot be chosen.

## What the hands are given (a new group, `b21 instruction`)

Appended at the end of the simulator's list; off (`INSTR=0`) the simulator is bit-identical and the columns read zero. Each comes with
its statistics by design until a sample of drills measures them (CLAUDE.md "Inputs").

| Columns | What | Scale |
|---|---|---|
| 9 | the verb, one of eight, or none | 0 or 1 |
| 3 | its state: doing, done, failed | 0 or 1 |
| 1 | how long he has been on it | seconds / 10, capped at 2 |
| 5 | the place: from him, turned to his facing (forward, left, up); the seconds of walking there; a place is given | units / 1000 in ±2; units / 200 in ±3; seconds / 10; 0 or 1 |
| 5 | the point: sideways and up from his crosshair; its distance; it is inside his field of view; his eye has a clear line to it | degrees / 180, / 90; units / 1000; 0 or 1 |
| 9 | the weapon asked for | 0 or 1 |
| 1 | it is the one in his hand | 0 or 1 |
| 7 | **the firing solution on the point** for the weapon asked for: there is one (rockets, plasma, a grenade within reach); the flight time; where to aim, sideways and up (the grenade's arc in it); the enemy's time is known; that time, counted down; the flight time less it (0 = it lands as he arrives) | 0 or 1; seconds / 2; degrees / 180, / 90; 0 or 1; seconds / 4; seconds / 2 in ±1 |
| 1 | quiet asked (second pass) | 0 or 1 |
| 3 | **the finish time of the weapon asked for** (third pass): seconds to finish the enemy with it (his believed stack over his own measured damage a second with that weapon at that distance), the cautious seconds (the believed stack plus its spread), the seconds of fire he has with it | seconds / 5 capped at 2 (2: he cannot use it, a rate of 0, no belief); seconds / 10 capped at 2 |
| 3 | **the same for the weapon in his hand**: live for every living seat, under an instruction or not | the same |
| 1 | he has a belief of the enemy's stack; live for every living seat | 0 or 1 |

48 columns (41 before the third pass). The firing solution is what the lead, the rocket aim and the grenade arc inputs give on an enemy he sees (each of the
three needs him noticed in view or seen within 3 s: read in the code, 2026-11-11); this gives it on a point with nobody in view.
The way to the place itself still comes through his target and the "intention" inputs he follows today (11% of the hands' signal).

**The way in:** the 39 columns are in the hands' list (list 21) at zero weights, and one attention token "instr", shut. So there are
two ways in, as for every other input (the flat encoder, the token): the encoder's opens by learning from the first drill; the
token's by the trainer's gate line. The input health report reads both at each reader. *(This corrects what I said on 11-11, "one
named path": the flat path cannot be shut for one group, and it is the one that needs no gate.)*

## The scripted seats (does the simulator let the verb pay at all?)

For each verb a script that carries it out as well as the limits allow, under the same aim model, senses and delays as he has; run
from frozen moments against 1.8's end, 8 s each, beside free play from the same moment (the held-angle probe's method). A verb whose
perfect script loses to free play cannot be learnt by drills: that is then the finding, and it is fixed first.

## As built (2026-11-11, branch `b21`, worktree `BobbyBones-21`; nothing run but the generators and compile checks)

| Part | Where | State |
|---|---|---|
| The instruction in the simulator: `INSTR` (a play switch), `instr_in()` (the giver's call, every head tick), the state every frame (`_ins_step`), the 39 inputs (`_ins`), his target and the way and look points taken from it (`intend`, `_bel_src`), a new life ends it, a frozen moment carries it | `sim/duel_env.py`; `sim/duel_env_ffa.py` regenerated (`tools/make_ffa_env.py`, its guard passed) | written; **not run** |
| The full list: 1,092 columns (1,053 + 39 at the end; every older column where it was) | `docs/INPUTS.csv` (`tools/list_inputs.py`) | generated |
| List 21 = list 18 + the 39 in the hands' part: 843 columns, the brain the first 691, the hands the first 835, the tail 8 | `sim/input_list.py extend`, `sim/input_list_21.json`, `docs/INPUTS_21.csv`, `sim/duel_env_ffa21.py`; list 18's module now accepts a full list that grew at its end | generated |
| A network of list 18 brought to list 21 at zero effect; the new columns' statistics by design, then measured from a drill's rows | `tools/inputs21.py convert / stats / same` | written; **not run** |
| The attention token "instr", last, left out while shut | `sim/attn.py` | written |
| The export and the plugin's forward pass on a cleaned list (the file carries each column's place in the full list; the second fade group; the weapon dial on the full row) | `sim/export_duel.py`, `plugins/netpass.py` | written; **not run**; `tools/netpass_check.py` is its proof |
| The spam probe: rockets, grenades, plasma on a point with nobody in view, beside free play from the same moment; the seat under the instruction | `tools/run/spam_hook.py`, `tools/run/verb_test.py` (runs the hold probe on any save too) | written; **not run** |
| The three goals as readouts of recorded games; the recorder keeps his trigger | `tools/run/goal_readout.py`, `tools/run/cypher_measure.py` | written; **not run** |
| The map sense, the appraisals, the frozen-moment rounds in the trainer | [TRAINER_PARTS.md](TRAINER_PARTS.md) | see there |

**Decided here, for the owner's review** (beside the table of verbs above):
- A place that is a point of the map (push, cut off, break off, spam's place to fire from) goes to his way as the enemy's believed
  place does: the way leads to the route goal nearest it, as 1.7's order did. A way to any point of the map is not built.
- "Failed" for an item is by what he knows (the item belief's books say it was taken after the instruction was given, and not by
  him), never the truth.
- Rockets and plasma get a firing solution with no check of the line (the "clear line" input says that); a grenade's bounces are not
  solved: the low arc to the point, or none.
- The scripted spam probe stands still while it fires. A spam on the move is the hands' to learn.

**Second pass (owner, 2026-11-11: "1, 2, 3 are a definite include", the spawn points after a frag, quiet):** the verb "check", the
spawn rows for five seconds after the enemy's death, the quiet field and its input, and the truth labels for "does the enemy know
where I am" and "where does he respawn" are in the simulator: [SIM_PARTS.md](SIM_PARTS.md), "Second pass", with two findings (the
respawn rule can be forced; walking may not be silent under today's hearing). The full list was 1,094 columns, list 21 845.

**Third pass (owner, 2026-11-11 night: the lightning gun "is for cleanup"; "we need to have a way to estimate whether the lg ammo
owned is (on average) enough to cover the expected remaining stack"):** the finish time (his own measured damage a second by weapon
and distance against his belief of the enemy's stack) for the head, the appraisals and the hands; the wake (a pain sound heard or
the believed stack fallen by a band makes the head draw anew at its next reading); the pattern's moments for the frozen moments
(branches that differ only in the weapon); and the head's pay label (the win chance alone): [SIM_PARTS.md](SIM_PARTS.md), "Third
pass", and [TRAINER_PARTS.md](TRAINER_PARTS.md), "The fifth build". The full list is **1,101** columns, list 21 is **852** (the
brain the first 691, the hands the first 844, the tail 8).

**Not built:**
- The plugins do not give or step an instruction (`instr_in`, `_ins_step` on a server): needed when a head gives instructions (2.1b).
- The scripted seats for go, contest, push, cut off, break off: the network does the first three today; the probes built are the
  two his goals name (hold, spam).
- The drills (rounds that start from a moment and give the instruction by script) and the head's choice of an instruction.
- The items' clocks in the demo sets.

## The tests, in the order to run them once 1.8a has ended (each needs the owner's go; none trains)

Merge `b21` into the repo's tree first (`data/` is there), or run from the worktree with `QLBOT_ROOT` set to the repo for the maps.

| # | Command | Passes when | Cost |
|---|---|---|---|
| 1 | `python docs/runs/2.1/tests_instr.py` | ALL PASSED: off = the simulator of `c99cc02` to the bit; on with no instruction = off; under instructions the columns are live, in range, zero for a seat under none; a moment carries it; `tools/ffa_check.py` | one core, a few minutes |
| 2 | `python tools/run/input_health.py <1.8a's end> <sample>`; `python tools/inputs21.py convert <1.8a's end> <out>`; `python tools/inputs21.py same <1.8a's end> <out> --sample <obs.npy>` | 0 actions differ | one core, minutes |
| 3 | `python sim/export_duel.py ...` on 1.8a's end, then `tools/netpass_check.py --env duel_env_ffa18` | the plugin's pass = the checks' pass (difference 0) | one core, minutes |
| 4 | `python tools/run/cypher_measure.py sim --run duel_gru_1_8a --policy <end> --out <dir>`, then `python tools/run/goal_readout.py <dir> --side -1` | the baseline of the three goals for 1.8's end | 80 games on the check cores |
| 5 | `python tools/run/verb_test.py run --hook hold_hook --run duel_gru_1_8a --policy <end> --tag h18`, then `read` | the hold against free play with hands trained under AIM3 (before: 6 behind) | 8 jobs on the check cores |
| 6 | `python tools/run/verb_test.py run --hook spam_hook --run duel_gru_1_8a --policy <end> --tag s18`, then `read` | whether a perfect spam pays at all: rockets, grenades, plasma, oracle and fair | 8 jobs on the check cores |
| 7 | the trainer parts' tests | [TRAINER_PARTS.md](TRAINER_PARTS.md) | there |

Before 4 to 6: `tools/run/cypher_measure.py check` for the same run and save (CLAUDE.md rule 3).

## 2.1a (2026-11-12)

The weapon field is **binding** (`INS_BIND=1`: the owner, 11-12): while the instruction stands and names a weapon he owns with ammunition,
that is the weapon in his hand; "none" leaves it to the hands. A standing instruction is drawn anew **one second** after its last draw, or
at once when it is done, has failed or a wake came (`head2.ins_redo`, `ins_end`); the 8-second lock does not act on a seat under an
instruction. A change of target made by an instruction is not charged the switch cost. The run: [2.1a/CARD.md](2.1a/CARD.md).

# v0.2.1: what was new, what happened, and what to review

Written 2026-10-13 for a reviewer who has not seen the project. The owner's request: "a full review from a new pair of
eyes". Everything named here is in the repo at the commit that adds this file; line numbers are of that commit.
Background in one page: [RUN_v0.2.1.md](RUN_v0.2.1.md). The run in full: [MANIFEST_v0.2.1.md](MANIFEST_v0.2.1.md).
The designs: [V02_STAGE_B.md](V02_STAGE_B.md), [V02_STAGE_C.md](V02_STAGE_C.md), [ENEMY_MODEL.md](ENEMY_MODEL.md),
[PROPOSAL_v0.2.1.md](PROPOSAL_v0.2.1.md). The log: [results/2026-10-13.md](../results/2026-10-13.md) and the day before.

## 1. The short of it

v0.2.1 is the run after v0.2 (`duel_gru_v0_2`), started from v0.2's end. v0.2's end is also **the control**: every
checked save plays it head to head and a network is promoted only if it beats it. The run was started twice and stopped
twice, because he lost level against the control from the first updates:

| | start | update 10 | update 20 | update 30 |
|---|---|---|---|---|
| First start (all new parts on) | 52.1% | 36.0% | 25.2% | stopped |
| Second start (the movement-autopilot lesson off) | 52.1% | 47.8% | 41.1% | 39.1%, stopped |

(Share of frags against the control, 160 ten-minute games: ten maps of 16, seats swapped. The same network against
itself read 48.8% in such a check, single maps 41 to 56%: about three points of noise on the mean, ten on a map.)

Test runs since then say which parts cost him (section 4). Two are found: **the movement-autopilot lesson** (fast) and
**the guessing game** (slower). Neither is understood: why they cost him is the first thing to review.

## 2. What he is, as far as the new parts need it

- A recurrent policy (PPO, GRU 512) trained by self-play in a simulator of Quake Live (`sim/duel_env.py`; the group
  module `sim/duel_env_ffa.py` is generated from it). Trainer: `sim/train_duel_rnn.py`.
- 791 inputs, cut into tokens for an attention part before the GRU (`sim/attn.py`); thirteen outputs ("heads"):
  movement keys, view turn, fire, weapon, ..., **the intention** (which item or place he goes for, read every few
  frames), **the movement-autopilot switch** and his way.
- **The movement autopilot** ("his legs", `LEGS=1`): a separate movement network (`move_v15n`) that takes over his
  keys and view turn while his switch is on and he has a target. He decides when; it carries him.
- **Teachers**: supervised losses on some outputs beside PPO. The one that matters here is **the item rule**
  (`--intent-teach 2.0`): a label on the intention output from a hand-written rule (nearest useful item and so on).
- The league: he plays his own last eight snapshots, and one update in four the control (`--anchor-p 0.25`).
- Training rounds were two minutes from a fresh start, in groups of two, three and four players
  (`--group 2,3,2,4,2,2,3`), with 17% weapon drills and 20% / 10% item and jump runs. 10,080 players, 384 frames a
  rollout, an update about every 5.7 minutes.

## 3. The new parts

The run's command file is not in the repo (it is in the run's folder); its settings are in the manifest's sections 2
and 9. Each part below: what it is, why it was wanted, where it is, how it was set.

### 3.1 The guessing game (`--aux`)

- **What.** A supervised lesson on the GRU's output: eight small linear layers that foretell things he cannot see,
  from his memory. The truth is the simulator's (`info["aux"]`, labels only, never inputs, never paid). The eight
  questions: `place` (where the unseen enemy is), `appear` (the angle he next appears at), `fight` (how the fight
  ends, its damage), `items` (seconds to the mega and the red armor), `target` (the enemy's intention), `strength`
  (his stack in four bands, his weapon), `first` (who takes the mega and the red armor next), `near` (the landmark
  the enemy is nearest to, now and 120 frames on).
- **Why.** The owner: "we should be pushing him hard to prioritize knowing where the enemy is". The thought was that
  a memory that must foretell the enemy carries what position play needs.
- **Where.** `sim/train_duel_rnn.py`: labels by hindsight in `aux_labels` (l. 122), `aux_guess` (l. 198), `aux_near`
  (l. 253); the layers at l. 653; the loss at l. 1147 to 1183; the gradient clip at l. 1300. The truth:
  `duel_env.py` `aux()` (l. 5529), columns `AUX_COLS` (l. 1078).
- **Settings.** `--aux 0.2 --aux-heads place,appear,fight,items,target,strength,first,near --aux-warm 60`
  (weight from 0 to 0.2 over the first hour), `--aux-trunk 1.0` (the default: the whole gradient reaches the shared
  layers). New layers start at zero.
- **What the record shows.** He learns the questions (the unseen enemy's place from 780 units of error to 335; the
  landmark right 39%, then 49%). With the lesson on, his step an update (`kl`) is about 0.043 and the clipped share
  0.33; without it 0.022 and 0.21.
- **Worth a reviewer's eye** (mine, unproven): the eight losses are added unscaled. At the start they sum to about
  17, after 20 updates to about 9.6 (`near` alone 4.0, `target` 1.4, `strength` 1.5, `fight` 1.3), times 0.2. The
  policy's and the lesson's gradients into the shared layers are clipped **together** to a norm of 0.5 (l. 1300), so
  a large lesson gradient takes the step away from PPO. Whether that is what happens was not measured.

### 3.2 The gate opening (`--gate-open`)

- **What.** v0.2.1's network has nine new tokens in the attention part (the holding places and his ways). They come
  with a "gate": a number added to the attention scores for a token, -30 in a converted network (nothing looks at
  it, so the network answers as before). `--gate-open 60 --gate-from -6` raises the gate from -6 to 0 over the first
  hour; the league's files keep theirs shut.
- **Where.** `sim/attn.py` (l. 33, 102 to 142); trainer l. 797 to 824. Conversion: `tools/targets_init.py`,
  `tools/ways_init.py`; `sim/add_attention.py --same` proves a converted network answers as before.
- **Evidence.** Alone, ten updates, four maps: 50%. A save of the first start played with its gate shut again was no
  better (22% against 25%).

### 3.3 The movement-autopilot lesson (`--legs-teach`) and the withholding (`LEGS_KEEP`)

- **What.** Two things that were built as one. `LEGS_KEEP=0.9`: in one in ten of the stretches where he switched the
  autopilot on, it is withheld and his own outputs move him, in his own seats only. `LEGS_LABEL=1` with
  `--legs-teach 0.05 --legs-teach-trunk 0.25 --legs-teach-warm 60`: on the frames the autopilot carried him (and the
  withheld ones) his own key and view-turn outputs get the autopilot's choice as a label.
- **Why.** So that his own movement comes to be as good as the autopilot's and he depends on it less.
- **Where.** `duel_env.py` l. 633 to 652 (the switches), l. 2989 to 3028 (labels and the draw); trainer l. 1005
  (the weight), l. 1236 to 1262 (the loss).
- **Evidence.** The lesson alone: 36% after ten updates; with its gradient held out of the shared layers
  (`--legs-teach-trunk 0`): 30%. The withholding alone, lesson at weight 0: 55%. So it is the lesson on his own
  outputs, shared layers or not. Its step read normal (0.04) and his hits in view read normal while it happened.
- **Worth a reviewer's eye.** On the frames the autopilot carries him his own key and turn outputs are not what
  moves him, and the trainer credits an output only on the frames it was read (`head_masks`). What exactly a
  cross-entropy on those outputs at those frames does to the frames where he does move himself (fights, mostly) is
  the open question. In the checks the share of time on the autopilot rose (0.50 to 0.63) as he slid.

### 3.4 The item rule's silence (`RULE_CONTEST=2`)

- **What.** The item rule's label is silent where he believes the enemy nearer to the item it names by two seconds
  of way or more. No new label, only fewer.
- **Where.** `duel_env.py` l. 753 to 761, l. 3685 to 3699, l. 5615.
- **Evidence.** Alone, ten updates, four maps: 52%.

### 3.5 In the base of every test run (not "new parts" in the tables)

- **Holding places as targets** (`TARGETS=1`, `TARGETS_FREE=2`): intentions 9 to 16 are a map's holding places
  (`sim/pro_holds/<map>.json`); opened out of "nothing" at a share of 0.3 (`tools/targets_init.py open
  --from-nothing`). The checks set the same switches for both sides.
- With none of the four parts above, 20 updates: 51.7% and 52.3%. The base holds.

## 4. The test runs

Each is a scratch copy of the run's folder from its start network, the run's command file with parts taken out, the
save played against the control. "Night" runs: ten updates, four maps (Blood Run, Campgrounds, Lost World,
Battleforged), 64 games. "Day" runs: twenty updates, ten maps, 160 games at updates 10 and 20.

| Test run | Parts on | Result |
|---|---|---|
| F (night) | none | 51% |
| G (night) | gate opening | 50% |
| R (night) | item rule's silence | 52% |
| K (night) | withholding, lesson at 0 | 55% |
| L (night) | autopilot lesson (with withholding) | **36%** |
| T (night) | the same, held out of the shared layers | **30%** |
| A (night) | guessing game | 46% |
| F (day) | none | 51.7%, 52.3% |
| A (day) | guessing game | **43.9%, 41.8%** |
| W (day) | gate opening, withholding, item rule's silence (the second start without the guessing game) | running; see the log |

Also measured:
- The slid save (second start, update 30) in **two-minute games**: 39.3%, the start network 51.2%. So the loss does
  not come from the checks' games being longer than training's rounds.
- Training's own reading against the control (`vs_anchor_kill_share`, one update in four, groups and drills
  included) starts about five points above the checks and fell from 0.575 to 0.515 in the second start while the
  checks fell from 52 to 39. It under-reads a slide and is sparse; it was not a warning.

## 5. What went wrong in the process

- The dry runs before the first start were four updates and read the step per output; they saw nothing. The rule
  since: a new lesson gets ten or more updates and a check against the control before a start.
- The night's test runs were ten updates on four maps. On that evidence the second start kept the guessing game
  (46%: read as noise). It was not noise.
- Four new parts were started together.

## 6. Questions for the reviewer

1. **The guessing game.** Is the loss wired soundly (l. 1147 to 1183, the labels' functions, the masks, the windows
   cut to the rollout: `frames [200, 288, 200]`)? Is the scale the problem (section 3.1), or the joint clip, or
   that the GRU's memory is asked to hold things that crowd out what play needs? What is the smallest change worth
   a test: a lower weight, `--aux-trunk` below 1, a clip of its own, losses normed per question, fewer questions,
   a layer of its own between the GRU and the questions?
2. **The autopilot lesson.** Why does a small cross-entropy on his own keys and turn cost 16 to 22 points in ten
   updates while every training number reads normal? Is there a fault in which frames get the label
   (`legs_lab`, `legs_wh`, the trainer's `head_masks` and `dc`)? Is the idea sound at all?
3. **Why do the checks and training disagree?** What in training hides a 13-point loss (section 4)?
4. **The checks themselves** (`tools/duel_eval.py --opp policy:<file>`): is anything in how the two networks are set
   up uneven (per-seat settings from each checkpoint, the gate, `TARGETS`, the autopilot's network)?
5. **Anything else in the new code** that looks wrong: the conversion tools, the attention gate, the labels' hindsight
   (does any label leak across a round's end or a death?), the item rule's silence.
6. **The plan for the next run** ([../BACKLOG.md](../BACKLOG.md) B-244, B-245; [../design/openings/README.md](../design/openings/README.md),
   [../design/openings/BOBBY_v0.2.md](../design/openings/BOBBY_v0.2.md)): whole ten-minute games, mid-game starts
   and spawn starts from saved moments, one against one only, spawn openings as the item rule's label in a life's
   first ten seconds. Its code is built in a staging copy and is not in the repo yet.

## 7. Ground rules the review should know

- Fair play: human senses and hand limits; nothing he could not know may be an input (labels may).
- The owner decides rewards and teachers; no reward for a single behaviour without asking.
- A change is judged against the control in the checks, not by training's numbers.
- More in `CLAUDE.md` ("Hard-won gotchas") and [../PLAN.md](../PLAN.md).

# The belief loop: one picture of the enemy, used by the hands and by the head

*Design note, 2026-10-22 afternoon (while v0.3.11 trains). The owner: "the fast mechanical network and the strategy network
need to share the same representation of the enemy, but act on it in different ways." Run cards (names, the owner, 2026-10-22 night): [RUN_v0.4.0.md](RUN_v0.4.0.md) (the brain in its own memory, pretrained beside v0.3.10's hands), [RUN_v0.4.1.md](RUN_v0.4.1.md) (the brain connected to the hands), [RUN_v0.4.2.md](RUN_v0.4.2.md) (the old belief faded out), [RUN_v0.4.3.md](RUN_v0.4.3.md) (the strategy head). Since this note: the picture lives in a separate brain memory (GRU 256, every 0.2 s), not in his play memory; read the parts below with that.*

## Where we are

- v0.3.11 ([RUN_v0.3.11.md](../v0.3.11/RUN_v0.3.11.md)) builds the picture: a readout (512 → 256 → 27) from his memory says
  where the enemy is (with a spread), his velocity, stack band, weapon in hand and weapons owned. A lesson grades it against the
  truth (10% into his memory) and a zero-sum knowledge pay rewards the side that knows more.
- First hour: the readout beats his hand-built belief from 5 s unseen on (10 s+: 657 u against 793 u; since the enemy's
  respawn: 712 against 968). The step per update, his aim and his hit rates are unchanged.
- Nothing yet **acts** on the readout's answers directly: whatever he uses, he uses through the memory they are read from.

## The idea: a filter, made explicit

Tracking an unseen opponent is a recurrent loop, the one every tracker (a Kalman filter, a person) runs:

| Step | A person | Bobby today | Bobby after v0.4.0 / v0.4.1 |
|---|---|---|---|
| **Predict** | "he was going toward mega; 2 s later he's about there" | implicit in the GRU | the readout also says where the enemy will be in 1, 2 and 4 s, and what he is going for |
| **Update** | a sound, a glimpse, a pickup heard | the senses into the GRU | the same |
| **Use** | aim where he will appear; decide to contest or skip | the policy reads the GRU | the policy *and* a small slow head read the readout's answers as an input |

So yes, "recurrent" is the right word, twice over: the belief is carried forward and corrected every frame, and the
answers feed back into the next frame's decisions. Two things keep the loop honest:

- The answers fed back are built **only from his own senses** (the readout reads his memory; the memory reads his inputs).
  The truth only grades; it never enters.
- The answers are fed back **without a gradient** (stop-gradient): the readout is trained to be right, never to be "useful"
  to the policy at the cost of being right.

## Three parts, in order

### 1. Predict ahead (v0.4.0)

New readout outputs, graded and paid exactly as v0.3.11's (a proper score: confidently right best, confidently wrong worst):

| Output | Truth (known once the future has played out in the rollout) |
|---|---|
| Enemy place in 1, 2 and 4 s, each with a spread | his position then, in the frame of now |
| What he is going for | the next of: mega, red, yellow, a big weapon, a holding place, "me" (he comes into view first), within 10 s; else "none" |
| When he will come into view | the seconds until the line of sight opens (bands: <1, 1–3, 3–6, >6 s, not within 10 s) |

- **Grading delay:** a prediction is graded when its truth arrives (up to 10 s later); the pay is credited at the frame it was
  made. The trainer has whole 384-frame windows (9.6 s), so a prediction made in a window's last seconds is graded in the next
  one, or left out (both are fine; left out is simpler).
- **Zero-sum pay:** the same rule as now: k × (his score − the enemy's score). The equilibrium: hide your intentions (vary
  your route, do not telegraph the item you go for) and read the other's. That is the owner's "game awareness" item
  (not through a teleporter the enemy watches, not always the same path).
- **Calibration from the pros' demos** before the start: how predictable a pro is 1, 2, 4 s ahead (the spread to grade
  against), and how often "what he goes for" is guessable from the pattern alone.

### 2. The picture as an input both sides read (v0.4.1)

- The readout's answers (now and ahead, about 60 numbers) become **one more attention token**, `belief`, read by the fast
  network from the next frame on. Its gate starts shut (`--gate-open`, as for every new token since v0.2.1), so the start is
  exact; the door opens over hours.
- What the fast network should do with it: pre-aim at the predicted appearance (the pre-aim pay already pays this), turn
  toward the likely opening (the look-back pay), keep the quiet weapon out while the enemy is predicted far.

### 3. A small slow head (v0.4.1): the simpler path to the strategy layer

v0.4's candidate head ([ARCHITECTURE.md](../v0.4/ARCHITECTURE.md) section 3) is about 7 M weights: a slow GRU of 1024, a store of
three minutes of memories (224 slots), a plan of 256 into the fast GRU. Most of that size is there to **work out** the enemy and
the game from raw memory. With the belief readout doing that, the head can start small and grow only when a measure says it
needs to.

| | v0.4 candidate (2026-10-17) | The small head (proposed) |
|---|---|---|
| Reads | encoder mean over 8 frames, the fast state, a 3-min store | the belief token (now and ahead), his own stack, item timers, the score and clock, the fast state (no gradient) |
| Memory | slow GRU 1024 | slow GRU 256 |
| Store of the past | 224 slots, 4-head attention | none (added later only if it forgets item timings or patterns beyond its memory) |
| Ticks | every 8 frames (0.2 s) | every 8 frames |
| Acts by | a plan (256) into the fast GRU + target and way logits | a plan (64) into the fast GRU + a bias on the intention head's logits (both start at zero: exact start) |
| Learns from | PPO on the intention head's choices, its own value at the long horizon | the same; its value on the existing long-horizon output (γ 0.9998) |
| Size | ~7 M (head) + 2.1 M (hands) | ~0.6 M (head) + 2.1 M (hands) |
| On a server | 3 ms a tick at one thread | well under 1 ms |

How it grows into v0.4 if needed: widen the slow GRU, add the store, add the target and way heads. Each step is one
switch and a measured reason (below).

## How we measure whether the picture is used: the decision report

A check plays games with the truth at hand, so it can ask whether his choices follow the situation. Same games as the
checks (whole ten-minute games, overtime, aim 4), plus the pros' demos where both players' recordings exist.

| Decision | Measured as | Good play |
|---|---|---|
| Fight or avoid | when the enemy comes into view: does he close in or back off, by the stack gap (his − the enemy's, in bands) | closes when ahead, backs off when behind; the slope of closing against the gap |
| Items against the enemy | each mega and red taken or gone for: the enemy's distance and whether the enemy was also going for it | takes it when the enemy is far; contests only when strong |
| Timing | arrival at mega/red relative to its spawn (early, on time, late, missed) | on time, more so when the enemy is weak |
| Deaths while weak | deaths with his stack < 100 against an enemy > 150 | fewer |
| After losing sight | his path in the next 5 s: toward the enemy's believed place, or away, by the stack gap | toward when strong, away when weak |
| Belief used | the same rows split by the readout's own belief of the gap (what he thinks), beside the truth | his choices follow his belief more than chance |

Read: v0.3.10's save 70 (before), v0.3.11 every few hours (while he learns), the pros (the target). If the rows move
toward the pros' with v0.3.11 alone, the small head can wait; if they stay flat, that is the head's job.

## What could go wrong, and the guard

| Risk | Guard |
|---|---|
| The prediction lesson shakes the shared layers (the guessing game of 2026-10-12) | the same small share into memory (10%), a warm-up, the step per update and aim watched from update 1 |
| Paying for prediction makes him predictable to himself and odd to others | zero-sum: being predictable costs him exactly what the enemy gains |
| The slow head learns to ignore the belief | the belief token is its main input and the head is small; the decision report shows it |
| Two new parts at once hide which one helped | one step a version: prediction alone (v0.4.0), then the token and the head (v0.4.1, in arms), each ten updates and a check against the control before its start |

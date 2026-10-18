# Bobby's movement: the problem, the fix, the progress

*2026-10-17 morning. Plan in full: [UNIFIED_MOVEMENT.md](UNIFIED_MOVEMENT.md). Backlog: B-259 (one movement network),
B-260 (v0.3.2's bridge).*

**Since then (2026-10-18):** v0.3.3 was stopped after five updates; v0.3.4 blended the legs into him (to 57.5% against
v0.3.1's end), its switch fade failed; **v0.3.5 trains with the switch removed** since Sunday 06:55. Below is the state of
Saturday morning; the steps' state now is in [UNIFIED_MOVEMENT.md](UNIFIED_MOVEMENT.md), the runs in
[../v0.3.4/RUN_v0.3.4.md](../v0.3.4/RUN_v0.3.4.md) and [../v0.3.5/RUN_v0.3.5.md](../v0.3.5/RUN_v0.3.5.md).

## The problem: two drivers

Bobby is two networks sharing one body.

- **His own network** (the hands) aims, shoots, picks targets and fights.
- **His legs** are a small movement network trained separately to strafe jump along a route. Since v0.3.1 they sit inside
  him as a branch.
- **A switch** (one of his outputs) decides who drives. While the legs drive, they own his forward/back and strafe keys,
  jump and crouch, his **left-right mouse turn**, walk and zoom.

The legs know nothing about the enemy. That causes three things:

1. **"Moving mode" tunnel vision** (the owner's play test, 2026-10-16: "nothing gets him to stop and look around"). While
   the legs drive he literally cannot turn to look. They drive 54–63% of his game time.
2. **He never walks and makes no effort to be quiet.** The legs own the walk button and were trained only for speed.
3. **He leaves moving mode only when he sees you, not when he hears you.** The legs drive on only 1.7% of the frames
   with the enemy in view.

Merging the two is the top goal (the owner, 2026-10-16: "the two movement networks are a major problem for how he is
now"), ahead of v0.4's strategy layer, which needs one movement network to send its plan to.

## The fix: one movement network, in small steps

Rules for every step:
- Each is behind a switch.
- Each starts **exactly** where the last left off: the network plays the same on its first frame, proved by replays.
- Each must hold in a ten-update test against the control before it stays in.
- No step grades his keys against the legs. The two times that was done, it cost him the game.

| Step | Change | What it gives him | Status |
|---|---|---|---|
| 1 | Look-aware legs (`LEGS_LOOK`), and a **turn correction** (`LEGS_TURN_ADD`): his own network adds up to ±15° a frame to the legs' turn | He can glance while the legs run | **v0.3.2, ran 20:56 → 07:25.** The look-aware legs did not learn to look in training, so v0.3.1's own legs were kept, with the look inputs at zero |
| 2 | **Key overrides** (`LEGS_KEYS_ADD`): he can take back forward/back, strafe, jump, walk or zoom, one control at a time | He can walk quietly or sidestep while the legs drive | v0.3.3: stopped after five updates, never used |
| 3 | **The legs' knowledge into his memory** (`--legs-feat`): the legs' 256-number layer feeds his memory through a door that starts shut | His own network learns what the legs know about strafe jumping | in v0.3.4 and v0.3.5 |
| 4 | **The legs as a guide** (`--legs-guide`): when he drives himself, his choice leans toward the legs' by a learned weight that starts at 0 | His own movement and the legs' converge, and we can measure by how much | in v0.3.4 and v0.3.5 as the blend (part A) |
| 5 | **Retire the switch:** it fades out once the two agree | One set of keys and one turn | the fade failed in v0.3.4; the switch removed in v0.3.5 |
| 6 | **Clean-up:** the legs are a layer of his network at the full learning rate | One movement network; v0.4's head goes on top | the legs part at the full rate in v0.3.5 (from 2026-10-18 09:17) |

## Progress

**v0.3.2 (step 1), 140 updates:** level with v0.3.1. Checks against v0.3.1's end went 49.0, 49.7, 49.8, 50.3, 50.6,
49.9, 50.1, 49.8, 48.8, 46.6, 51.1%.

| | v0.3.1's end | v0.3.2 (last 10 updates) |
|---|---|---|
| Turn correction used, share of legs frames | none | 3.8% (it had reached about 10% when its opening ended) |
| Its size | | 3.7° |
| Legs' share of game time | 54% | **63%** |
| Legs speed, hop chains | 342, 12.8/min | 343, 13.5/min |
| Walking | 0% | 0% |

What it showed:
- Given only the turn, he chose to lean on his legs **more**, and he is giving the correction back.
- The legs did not learn to look in their own training (17.8% of the time facing the point, against 16.1% for legs that
  cannot see it).
- So step 1 alone does not end moving mode. Steps 2 and 3, which hand his own network the keys and the legs' knowledge,
  are the real start of the merge.

**v0.3.3 (steps 2 + 3)** started 07:27 and was stopped after five updates for v0.3.4.

**What we watch at every step:**
- legs' share of game time
- the turn correction's use and the key overrides' use
- the walking share
- legs speed and hop chains, and his own speed when he drives himself
- the door's share of his memory's input
- the switch-off agreement (from step 4)
- the checks by map
- the owner's play tests

**Open (the owner's):** whether look-aware legs are worth a redesigned training task (a reward for keeping the view on
the point).

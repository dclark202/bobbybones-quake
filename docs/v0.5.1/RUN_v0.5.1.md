# v0.5.1 on one page: pay by win chance only

*2026-10-26 night (owner: "a lot of his current behavior is pathological. he does what gives him reward, and ends up not
fighting when he should be and doing weird things"). From v0.5.0's end, before the strategy head (now
[v0.5.3](../v0.5.3/RUN_v0.5.3.md), after the new aim model of [v0.5.2](../v0.5.2/RUN_v0.5.2.md)): the head optimises whatever he is paid, so it opens on the pay that only rewards winning.
Two overlapping fades: the fight's pay becomes the change in his chance of winning, then everything else in a game fades out.
At the end a game pays him only for his chance of winning. The full proposal and its review:
[PROPOSAL_v0.5.1_winpay.md](PROPOSAL_v0.5.1_winpay.md).*

**Marks:** ✅ built and tested · ⏳ building · 🧪 to measure · ❓ owner's decision · ⏸ later

## Start

| | |
|---|---|
| Network | v0.5.0's end (`duel_gru_v0_5_0/keep/policy_end_v050.pt` + optimizer) |
| Code | branch `v051` (1cb3009, 1b02dd6, 120c086: v0.5.0's code + the pay blends below; everything off = v0.5.0 bit for bit in fixed runs of both modules; a game's win part sums to its result; at full fade a game frame pays only the win part; the CPU smoke test of the command passed) ✅ |
| Aim | `!aim default`: level 3 delays (100 / 200 ms), sight 0.6°, hand 0.10, fast-target 0.075 capped at 1.5° (rail 1.0°) |
| Mix | **67% whole games / 33% the pros' mid-game starts; no movement practice at all** (owner: "He isn't getting any better at any of the jumps specifically. So let's just remove them"): `JUMP_RUN_P` 0, the jump focus off. Every frame he plays is a game paid by win chance |
| Speed pay | already 0 (faded out at v0.5.0's end, 04:00-06:05) |
| Before the go | the first 10 updates are the dry run (as v0.5.0's: the pay is v0.5.0's at step 0), then a check against the control and the behaviour panel; the start is one script (`start_v051.ps1`: v0.5.0 stopped after its next save and kept as its end, the folder made, the trainer, watcher, guard and ramp started) ✅ |
| Run | `duel_gru_v0_5_1`, Tue 07:00 to Wed noon (owner) |

## What is paid now in a game (v0.5.0, per player-minute)

| Pay | Now | At v0.5.1's end |
|---|---|---|
| Frag / death | +0.42 / -0.43 | replaced by the win chance |
| Damage dealt / taken | +0.80 / -0.86 | replaced by the win chance |
| Speed | +0.50 (gone by the start) | 0 |
| View jerk, target switch, shot price, weapon switch, fire toggle | -0.23, -0.13, -0.13, -0.09, -0.03 | 0 |
| Items (zero-sum) | about +0.05 | 0 |
| A dozen small terms (stack, big weapons in order, knowledge, watching the spot, far rail, height, pre-aim, blind fire, drops, way claw) | 0 to 0.03 each | 0 |

## The pay at the end

| Part | What it is | State |
|---|---|---|
| Win chance | each frame: the change in his chance of winning, from `sim/win_chance.json` (the pros' 257 games: score lead and time left); the overtime and buzzer frames read 0 s left | ✅ |
| Stack in the win chance | a zero-sum term: the chance the next frag is his (from both stacks and big weapons), times what a frag is worth at this score and clock, times the chance a frag still comes before the end; 0 at the end. Fitted from 1,040 pro games recorded by both players: held out, the win chance's log loss 0.3959 -> 0.3848, better in every time band; a dead player counts as his respawn stack | ✅ |
| `WIN_GAIN` | scales the win part to keep his pay the size it is now: set by the ramp before step 1 from the run's own counters (the combat pay's size over the win part's, the first 10 updates), within 1 to 4 | 🧪 |
| The long value | the win part also feeds his ~2-minute value (it learned items and stack before; they fade): `WIN_LONG` | ✅ |

**Equilibrium:** each frame pays the change of one function of the game, so a game's pay sums to its result whatever happened on
the way: zero-sum, nothing can be pumped, the self-play optimum is to win. The stack term changes when he is paid, never how much a
game is worth.

## The schedule: a step every 10 updates (about 45 minutes, never under 40), each cleared by the behaviour panel

| Step | About (Tue) | Fight pay → win chance (`WIN_W`) | Everything else (`FADE_V`) |
|---|---|---|---|
| start | 07:00 | 0 (v0.5.0's pay) | 0 |
| 1-4 | 07:45 → 10:00 | 0.1 → 0.4 | 0 |
| 5 | 10:45 | 0.5 | 0.125 |
| 6-9 | 11:30 → 13:45 | 0.6 → 0.9 | 0.25 → 0.625 |
| 10 | 14:30 | **1.0** | 0.75 |
| 11-12 | 15:15 → 16:00 | 1.0 | 0.875 → **1.0** |
| after | evening, overnight | win chance only; the owner's play test in the evening; trains to Wed noon | |

- The stack term goes in at the start if its fit is ready, else before step 5 (before any item pay fades).
- A red panel holds the ramp; the same red twice steps it back one step. The ramp script steps by updates, not the clock.

## Watched (the behaviour panel every 10 updates during the fades; v0.4.2b's end as the fixed control)

| | |
|---|---|
| Weapons | **in hand against the pros** (owner: "the biggest thing to watch for"); weapon switches a minute (they rise as the switch cost goes) |
| Items | mega and red armor share; time near spawns; targets per map |
| Fighting | passive (self-play frags a minute), hunting the spot-holder, roaming |
| Hands | view acceleration, reversals a second, fast wobble against the pros (`HAND_BAND` is the limit now, not the jerk cost) |
| Checks | 160 games every 20 updates against v0.4.2b's end: reported, not a gate. The collapse guard stays: a check under 15%, or two in a row under 25%, stops the run |

## Not yet

| | |
|---|---|
| Movement practice | removed for v0.5.1 (owner); revisited once the strategy layer and the rest are done. The panel tracks his tries and successes at Aerowalk's red-armor jump and Campgrounds' b2r in games meanwhile |
| The item rule | a lesson for which item to go for (not a pay): stays on; faded with the head in v0.5.3 |
| A learned win chance | later: a correction learned from his own games on top of the pros' fit, only if it predicts held-out games better ⏸ |

## Risks

| | |
|---|---|
| Credit for items | taking a mega pays through the stack term and the frags it leads to; item control may sag: the panel's mega and red share gate the ramp |
| The signal's shape | most of it at frags; a dip is expected (bounded dips: 20-30 updates) |
| Switching free | the finger limits bound it; switches a minute are watched |

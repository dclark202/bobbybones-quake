# b1.3a: the strategy head in, shut, learning to copy his target choice

*2026-11-02 evening (owner): "we bring it in in b1.3 to learn how to copy the rules that exist, and then once we know it can, we remove those rules and let the head train"; "B1.3 - fade head IN. It starts overnight and is ready sometime tomorrow. B1.4 - fade OLD rules out"; "Plan for that B1.3 to run for about 12 hours". The family: [README](../README.md). Replaces the design of 11-01 (the head as the only learner, opened on pay; why it was needed: [b1.2a's card](../../b1.2/b1.2a/CARD.md)), which never ran: that design moves to b1.4.*

**Marks:** ✅ built and tested · ⏳ to build · 🧪 to measure · ❓ owner's decision

## The owner's page

| | |
|---|---|
| Started from | **b1.2d's end** (`keep/policy_end_b12d.pt`, its save of update 80) with its optimizer, given the head shut (`tools/head2_init.py add --gate 0`) |
| Started by | `start.ps1 -Minutes 720 -NoTrial` on the owner's go, **2026-11-02 20:22** (owner: "stop the trial you are running. Let's just start B1.3 and see how it goes"); both identities passed (0 actions differ); ends about 08:30 on 11-03 |
| Run | `duel_gru_b1_3a` |
| What | the strategy head is in, **shut in play all run** (gate 0: he plays as b1.2d's network does). It learns one thing: **to copy his target choice**. At every reading of his target, the head's own choice (its target layer, without the gate) is taught to match the hands' choice (their distribution, as a number), by KL (`--head2-copy 1`). It has no pay-driven lesson (`--head2-pg 0`). Its value learns his whole pay on two minutes (`--head2-pay all`: combat, items, win; owner 11-02: "I'm fine leaving combat, item and win pay in him"), ready for b1.4 |
| The hands | train on exactly as b1.2d: the same pay, the same rules (the item rule's label included). b1.3a is also more b1.2d training |
| No blowup possible | the head does not act (gate 0) and has no pay-driven lesson; the copy's gradient reaches the head only (checked by the trainer at its first piece: it stops otherwise) |
| Length | **12 hours** (`--minutes 720`; owner, 11-02) |
| League, checks | b1.2d's end, b1.1 and v0.6.0's end as anchors; 200 games (20 a map) every 20 updates against the start, every fourth against b1.1; the panel. Never stopped |
| Cores | as b1.2d: the trainer on the 8 performance cores, the checks, panel and logger on 8 efficiency cores, 4 left for the owner |
| Kept | every save the trainer keeps; the end as `keep/policy_end_b13a.pt` with its optimizer |

## Judged by (the copy is ready for b1.4 when)

| Measure | Wanted | Where |
|---|---|---|
| The head's first choice = the hands' first choice, on read frames | 90% or more (proposal ❓), on every map; also in fights, at low stack, when bare | `metrics.jsonl` `head2.copy.agree` (by map and situation: 🧪 a read of the end save, to build) |
| The copy's KL | falling, then flat | `head2.copy.kl` |
| **The head plays alone** (his target from the head's choice, the hands' target outputs left out) against b1.2d's end, 200 games | about level (45% or more ❓) | **74-126, 37.0%** (below; 11-03) |
| Play | as b1.2d: checks about 50% against the start | the watcher |
| The head's value | its loss falls | `head2.v_loss` |

## Red team

| | |
|---|---|
| The copy reads the hands' memory | the head's inputs include the hands' fast memory (as numbers), so copying them is easy and fast: the head may learn a read-out of the hands rather than the situation. Fine for b1.4 (the head keeps reading it), and it is why the "plays alone" check matters. Alternative: hide the hands from it (`--head2-off hands`); left out (owner's choice, 11-02: in) |
| A copy of a moving target | the hands keep learning, so the head copies b1.2d's network as it drifts. The copy at the end is of the end |
| After a respawn | the head has no state until its next tick (up to 8 frames), and his target is read at once after a spawn. The copy skips those frames; **b1.4 must handle them** (the hands' choice, or a tick at the reset) ⏳ |
| Untested here | the copy lesson is new code (`--head2-copy`, 11-02); the trial was stopped before its verdict (above) |
| The head is a slow memory | it ticks every 0.2 s and its memory starts tuned to 0.2 to 60 s (most units near 30 s: `chrono` 300), made for a two-minute strategy; copying a choice that changes moment to moment needs fast units. If agreement is still near the average-choice level (20 to 30%) after about 3 hours, the head needs a fix and a restart (b1.3b): a faster start for its memory, or the hands' choice read more directly |
| Pay pathologies (ledger) | unchanged from b1.2d; watched as always |

## The equilibrium

Unchanged from b1.2d: the head does not act. The table is the baseline, win pay the correction.

## Before the start

| Step | Where it stands |
|---|---|
| `--head2-copy` in the trainer (the KL on read frames with a head state; its counters `head2.copy`; the one-time check that its gradient reaches the head only) | ✅ written, compiles; applied after b1.2d's trainer exits |
| `make_files.py`: b1.2d's command with the head's arguments (gate 0, cap 0, open 0, `--head2-pay all --head2-pg 0 --head2-copy 1`) | ✅ |
| `start.ps1`: `-Minutes 720`; the settings check allows only `--run`, `--minutes` and the head's arguments; refuses without `trial_copy.log` ALL PASSED; the identity (head shut, and its whole path at gate 1, answer as the save); no ramp | ✅ written, not run |
| The trial (`trial_copy.py`, `trial_copy.log`): 40 min on the CPU, cores 16 and 17 | **stopped at update 102 on the owner's word** (20:20): the copy's gradient reached the head only (`head2.target`; at the first piece the head's GRU had none because the target layer starts at zero), gate 0 throughout, no NaN; KL 2.26 → about 1.45 and flat, agreement about 20% and flat: the average choice, not the situational one. The trial has about 40 readings an update against the run's about 30,000, so it could not settle whether the copy gets good |
| The owner's go | given 11-02 evening ("Let's do that"; the start: "Ok go", 20:20) |

**Watch while it runs:** the trainer's exit, every time; `head2.copy` each hour.

## Changes on the fly

| Time | Change | Why |
|---|---|---|

## The result (2026-11-03)

Ended 07:17 at update 130 (owner), `keep/policy_end_b13a.pt` with its optimizer. The copy: agreement 86.8% (KL 0.145), flat from update 50. Play with the hands choosing about level with b1.2d's end (58.5 / 52.5 / 44.0 / 48.0 / 49.5% at updates 10 / 30 / 50 / 90 / 110; 52% against b1.1 at 70); the panel green.

**The head alone** (`head2head.py --mix-a 1`, its choice in place of the hands', against b1.2d's end, 200 games, [headalone.log](headalone.log)): **74-126, 37.0%**, frag share 43.5%; by map won-lost from 4-16 (20%, Blood Run) to 10-10 (Campgrounds), Lost World 9-11 (the frag shares 33% to 61%; corrected 11-03: the per-map numbers were frag shares). Under the 45% bar: the head copies the hands where the hands' choices led, and alone it meets places it never saw. The owner: "he was always going to suck with a hard swap ... The only reasonable way to do this is to blend the two in together": b1.4a.

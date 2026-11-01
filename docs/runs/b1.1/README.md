# b1.1: ready for strategy

**b1.1 is `duel_gru_b1_1a/keep/policy_b1.1.pt` + `opt_b1.1.pt`** (owner, 2026-11-01; also on `T:`): b1.1a's save of update 140, the brain's old belief and the pull out, lock 8 s. The lock's fade moved to b1.2.

**The goal:** the hand-built rules that stand in the head's way gone, at no loss of strength, with the win pay and the pay table in place: the brain's old belief (`BRAIN_FADE`, the 76 rule-made input columns), the view's pull toward level (`LEVEL_PULL`) and the target lock (`INTENT_HOLD`, 8 s).

**Passes when:** at least level with b1.0a's end in the last checks, aim, rail, frags and the brain's scores hold, and the owner's play test.

## The attempts

| Attempt | Started from | What | State | Result |
|---|---|---|---|---|
| [b1.1a](b1.1a/CARD.md) | b1.0a's end, its own optimizer | the brain, the pull, the lock, in one run, a save kept between them | 2026-10-31 21:11 to 11-01 07:27, update 180 | brain and pull out: 60.6% against b1.0a's end (u130). Lock out: flicker, b1.1 taken from before it |

## Next, depending on b1.1a

| If | Then |
|---|---|
| all three hold | b1.2 from its end |
| the lock costs him, or his targets flicker | b1.2 from `policy_nopull_b11a.pt` (lock back at 8 s); the lock is looked at again after the head |
| the pull costs him | b1.1b from `policy_nobrain_b11a.pt` |
| the brain costs him | b1.1b from `policy_prebrain_b11a.pt` |

# b1.3: the strategy layer opens

**The goal, as changed 2026-11-02 evening (owner):** "we bring it in in b1.3 to learn how to copy the rules that exist, and then once we know it can, we remove those rules and let the head train" (b1.4). The head is shut in play and learns to copy his target choice; the rules fade out in b1.4.

**The first goal (owner, 2026-11-01):** the strategy head open, with the fix to its learning, so that he chooses what to do by the game's state: above all, he fights more. "My general biggest gripe is he needs to fight more. I have to pick the fights with him, which is not good."

**Passes when:** at least level with its start and v0.6.0's end; the head's and the hands' target logits do not run away; the enemy's share of his targets clearly up; items and stack hold; no spawn camping; the head adds something (a check with it blanked); the owner's play test.

## The attempts

| Attempt | Started from | What | State | Result |
|---|---|---|---|---|
| [b1.3a](b1.3a/CARD.md) | b1.2d's end | the head in, shut in play, learning to copy his target choice (the copy design, owner 11-02 evening; the sole-learner design moves to b1.4) | ended 11-03 07:17 at update 130 (owner); the copy 86.8%; play about level with b1.2d's end; **the head alone 74-126, 37.0%** against b1.2d's end ([headalone.log](b1.3a/headalone.log)) | the copy holds while the hands choose; a hard swap to the head fails: b1.4a blends the two |

# b1.3: the strategy layer opens

**Redone 2026-11-03 (owner: "I think I need to scrap what was done in B1.3"):** b1.3a's copy (and b1.4a's blend on top of it) is scrapped. [1.3b](1.3b/CARD.md) starts again from b1.2d's end: his target choice keeps its one chooser, which also reads the strategy head's slow memory (at zero at the start) and is credited by the head's longer view. Why: [the review](../../reviews/REVIEW_b1.2-b1.4.md).

**The goal, as changed 2026-11-02 evening (owner):** "we bring it in in b1.3 to learn how to copy the rules that exist, and then once we know it can, we remove those rules and let the head train" (b1.4). The head is shut in play and learns to copy his target choice; the rules fade out in b1.4.

**The first goal (owner, 2026-11-01):** the strategy head open, with the fix to its learning, so that he chooses what to do by the game's state: above all, he fights more. "My general biggest gripe is he needs to fight more. I have to pick the fights with him, which is not good."

**Passes when:** at least level with its start and v0.6.0's end; the head's and the hands' target logits do not run away; the enemy's share of his targets clearly up; items and stack hold; no spawn camping; the head adds something (a check with it blanked); the owner's play test.

## The attempts

| Attempt | Started from | What | State | Result |
|---|---|---|---|---|
| [b1.3a](b1.3a/CARD.md) | b1.2d's end | the head in, shut in play, learning to copy his target choice (the copy design, owner 11-02 evening; the sole-learner design moves to b1.4) | ended 11-03 07:17 at update 130 (owner); the copy 86.8%; play about level with b1.2d's end; **the head alone 74-126, 37.0%** against b1.2d's end ([headalone.log](b1.3a/headalone.log)) | the copy holds while the hands choose; a hard swap to the head fails: b1.4a blends the two |
| [1.3b](1.3b/CARD.md) | b1.2d's end | the head's own scores added to the hands' (one chooser, its slow-memory part at zero at the start), the credit moved to the head's advantage over updates 10 to 90; the head's memory speeds spread; no copy, no blend | started 11-03 16:31, to 08:00 on 11-04 | |

# b1.4: the old rules fade out, the head decides

**The goal (owner, 2026-11-02 evening):** "B1.3 - fade head IN ... B1.4 - fade OLD rules out"; "we bring it in in b1.3 to learn how to copy the rules that exist, and then once we know it can, we remove those rules and let the head train". Combat, item and win pay stay ("I view the win pay as the correction factor on top of those"). Most of the rule removal goes here, the rest in b1.5 at most (owner: "Your proposed schedule here is too timid").

**Starts from (2026-11-03):** [1.3b](../b1.3/1.3b/CARD.md)'s end, if it passes. (Before: b1.3a's end, whose head had learnt to copy his target choice; scrapped with b1.4a.) The plan of 11-02 below is history; the current steps are on [1.4b](1.4b/CARD.md).

## The plan (proposal of 11-02 evening; exact numbers set on the card)

| Order | Fade | Dial | Updates |
|---|---|---|---|
| at the start, no change in play | the dead rule code out, proven bit-identical: the item rule's silencers (`RULE_CONTEST`, `RULE_HUNT`, `OPEN_SILENT`), the openings' label, the weight-0 teachers (`PRO_WEAPON`, `PRO_ITEMS`, `STACK_TEACH`, `SPAWN_TEACH`, `--teach`, `--weapon-teach`), `--intent-teach`, `SHOT_COST` (already 0 through `COST_FIRE_W`) | | 0 |
| A | his target choice moves from the hands' (the rules' imprint) to the head's: a cross-fade 0 → 1; the hands' target outputs frozen from the start (one learner: b1.2a's blowup); the head learns from his whole pay as it takes over | `H2_MIX` (new) | 10 to 50 |
| B | the target lock out of fights | `INTENT_HOLD` 8 s → 0 | 50 to 80 |
| C | the way pay out (the pay for progress toward his chosen target) | `INTENT_SEEK` (new live dial) 1 → 0 | 80 to 110 |

Holds: a check at 40% or less holds the fade in progress, under 50% flagged.

**b1.5 (owner: "at most"):** the hunt as the head's choice among the brain's zones (new outputs), the movement network's look point out of his inputs.

**Moved out (11-02):** the damage weight (`DMG_TAKEN_W` 0.8 on enemy damage only) went into b1.2d. Item pay by effective stack (B-297) and knowing every health and armor item (B-298) wait for a later step.

## The attempts

| Attempt | Started from | What | State | Result |
|---|---|---|---|---|
| [1.4c](1.4c/CARD.md) | 1.4b's end | (owner, 11-04) the target lock out by a learned choice to keep or re-decide (AlphaStar's no-op), handed the lock rule's readings by a share 0 → 1 over updates 10 to 90; the blind-fire cost out | built 11-04 (branch `b14c`); **not continued** (owner, 11-04 evening: the weapon choice first, 1.5a from 1.3b's end; the lock's hand-over redone in 1.6) | not started |
| [1.4b](1.4b/CARD.md) | 1.3b's end | (owner, 11-03 evening) 12 h: the switch cost out and a weapon he holds choosable from the start; matchmaking by difficulty over updates 0 to 10; the item rule's lesson out over 10 to 70; the speed pay out over 70 to 90 (the lock moved to 1.4c) | **scrapped** 11-04 evening at update 113 (owner) | |
| [b1.4a](b1.4a/CARD.md) | b1.3a's end | replanned 11-03 after the head-alone test (37%): the head blended in to half (mix 0 → 0.5 over updates 10 to 90), learning from pay the whole time; the copy lesson off; the rules' imprint frozen; the lock and the way pay stay; 12 h | **stopped 11-03 11:12 at update 21** (owner) | 43.5% at update 10 (mix 0); the head's scores 16 → 29, agreement 87% → 61%: b1.3 to be redesigned |

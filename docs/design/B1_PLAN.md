# b1: win chance as one signal among the pays, then the rules out

*2026-10-31 (owner): new names, b1.n.x. Win chance pay is "purely an additional signal"; combat skills "and likely item incentives" stay
as hard rules. The owner sets the order of the later steps; the order below is a proposal.*

**Replaces v0.6.x's goal of pay by win chance only.** Each step has one new thing, shut at its start and opened slowly.

## The steps

| Run | One new thing | Start | Passes when (beside the owner's play test) |
|---|---|---|---|
| **b1.0a** | win pay added, every other weight fixed ([card](../runs/b1.0/b1.0a/CARD.md)) | v0.6.0's end | the gates below |
| **b1.1a** | the pull toward level and the brain's old belief out, together (`LEVEL_PULL` 0.95 → 1, `BRAIN_FADE` 0 → 1; owner, 2026-10-31) | b1.0's end | at least level with b1.0's end; the brain's scores, rail in hand and aim hold; no fall in the gates |
| **b1.2a** | the strategy head in, item rule on (`H2_GATE_CAP` 0 → 1) | b1.1's end | at least level; targets and roaming hold; the head adds something (blanked-head check) |
| **Later** | the item rule's label out (`INTENT_TEACH_W` 1 → 0) | b1.2's end | at least level; no spawn camping (v0.4.4's failure); items hold |

**2026-11-01 (owner):** b1.2's goal changed from the head to every item priced and the costs out ([family](../runs/b1.2/README.md)). Small items as inputs and b1.2c's decisions: [SMALL_ITEMS.md](SMALL_ITEMS.md).

bN is the series, bN.N a family of runs with a specific goal, bN.Nx an attempt at it (a, b, c, ...). A failed attempt gets the next letter (b1.1b), not a new number. If b1.1a fails, b1.1b and b1.1c isolate its two fades: no run has tested either alone.

**After that, not yet ordered:** the target lock (`INTENT_HOLD`, `TARGETS_FREE`, `WEAPON_FREE`), the pros' tables as inputs, the movement
mechanics (rocket jumps, trick jumps: v0.6.4's card, still the plan).

## The gates for b1.0, measured on v0.6.0

| | v0.6.0 u80 | v0.6.1d u219 (win-heavy) | b1.0's floor |
|---|---|---|---|
| Frags a match-minute | 1.75 | 1.32 | 1.6 |
| Rail in hand | 0.22 | 0.09 | 0.18 |
| Entropy | 1.76 | 1.87 | 1.82 |
| Against v0.6.0's end | | 50 to 67.5% | mean of the last four checks at least 52% |
| Against v0.6.1d's end | | | at least 50% |

The floors are proposals, set by hand from these two runs.

## What else this has to settle

| Point | Why it matters | Decision |
|---|---|---|
| The dials can't add | `paid = (1-v) other + (1-w) combat + w G win`: raising w always cuts combat | new live dial `WIN_ADD`: `+ A x win`, nothing else moves |
| What a frag is worth | a frag now pays 1 plus its win value, never near 0 (table in the card). On win-only pay a frag in a decided game paid about 0, so fights there taught nothing: a likely part of the skill loss, not yet proven | additive pay fixes this by construction |
| Double counting | the judge prices frags, damage, stack and weapons, so those are paid twice. Intended: it raises what matters when the game is close | watch for over-trading late, and for armor hoarding |
| Where the win incentive comes from | at a discount of about 25 s, the game-end pay reaches the hands only in the last 25 s. The hands' reason to win is the judge's pricing, by score and clock. The head (two minutes) sees more | the head will matter for real game sense; say so in its card |
| The head learns from all pay | its value uses the whole frame's pay, so with item flats on it also chases item flats, and only about a third of its pay is win | check at b1.2; the flats may have to come down there |
| "Item rules" is two things | the rule's **label** on his target, and the item **pay** (`ITEM_FLAT`, `BIG_PICK_SEQ`) | the later step removes the label only; the pay stays |
| The other hand-built pays | `RAIL_FAR_PAY`, `WATCH_PAY`, `PREAIM_PAY`, `KNOW_PAY`, speed, shot prices all stay | an owner's list, after the item rule |
| Length itself | v0.6.0's retrain ran only 80 updates and its first run 170; no flat-pay run has gone longer. A slide in b1.0 could be run length, not pay | if b1.0a slides, the next arm is v0.6.0 flat for 12 h, before any change to the pay |
| The judge drifts | each refit fits games of a bot already drifting (v0.6.1's judge came from win-only play) | frozen for all of b1; a refit is its own step, with an A/B |
| Check noise and the ramps | ±4 points on 160 games. "Hold under 50%" stalls half the time on a network truly at 50% | hold on a mean of two checks under 47%; back a step on two under 45%. Owner's call: this softens the standing rule |
| One yardstick | each v0.6.1x run was checked against its own start | v0.6.0's end at every check, all through b1, plus each run's start |

## Sessions (if each step passes)

At about 4 min an update, 12 h is about 180 updates. A ramp of about 4 h leaves about 8 h to settle.

| Day | Run | Then |
|---|---|---|
| Sat 10-31 | **b1.0a** running from 10:56, to ~9:00 on 11-01 by default; play test this evening; ended early, **b1.1a** overnight (owner's call) | |
| Sun 11-01 | 06:30 report, play test, **b1.1a** | |
| Mon 11-02 | report, play test, the head's smoke and identity checks, **b1.2a** | |
| Tue 11-03 | report, play test, the item rule's fade if b1.2a holds | |
| Wed 11-04 | report, play test, b1's first candidate for the servers | owner's call |

Any retry pushes the rest back a day. Docs on the first go: CLAUDE.md's names and goals, `docs/PLAN.md`, `docs/HISTORY.md`.

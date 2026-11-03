# The target lock: where it stands, why it is being faded, what replaces it

*Written 2026-11-01 for an independent review, while b1.2a runs. Code references are to the working tree of that day. "From the code" means read, not run. The run itself is not to be stopped or changed by the review.*

**In short:** the lock (`INTENT_HOLD`) keeps a chosen target for a set time. The owner wants it gone. The one time it was faded, without a replacement, targets flickered and he lost head-to-head games. **b1.2a now fades it again with no direct replacement.** The strategy head is the hoped-for replacement, but nothing shows it can hold a choice, and its design does not force it to.

## What the lock is

Every player has a **target** (the "intention", the eleventh action output): nothing, an item, a weapon, the enemy, or a holding place (17 choices). It is read once a second (`INTENT_EVERY` = 40 frames of 25 ms, staggered by player), and at once after a spawn.

The target sets the way shown in his inputs and the speed pay for covering it. There is no pay for the way itself: `--item-reward 0` makes its worth zero (corrected 11-01, after the review). **It does not move his body:** the hands still choose keys and aim, and can fight while locked on an item. So the lock binds where his way and way pay point, not what his hands do.

The rule is in `intend()`, `sim/duel_env.py:6729`. At a reading, a new choice counts only if one of these holds:

| Condition | Meaning |
|---|---|
| `intent == 0` | the current target is "nothing" |
| `intent_done` | the item was taken; or, for the enemy, he is in view |
| `intent_t >= INTENT_HOLD` | the lock has run out |
| `intent_gone` | the item is gone and won't be back in time, judged by what he knows (`GONE_BELIEF`); or the enemy has no way to him |

Holding places have their own exception (`TARGETS_FREE=2`): one can be left at any reading, but only for an item.

Readings that fail this test are not "live" (`intent_live`). The hands' lesson on this output, the item rule's label and the head's bias lesson all count only live readings (the head's per `sim/head2.py:39`). **So a longer lock also means fewer readings to learn from.**

## History

| When | What | Result |
|---|---|---|
| 10-06, v8 | 3 s lock added with the target | |
| By 10-08 | 8 s in training | the setting did not reach servers until 10-08: they ran 3 s, training ran 8 s |
| 10-12 | `TARGETS_FREE=2` | a holding place locked for 8 s cost him the mega: places at 5% of readings were 22% of his time |
| 10-26, v0.5.0 | `GONE_BELIEF` | the early release was a free way to probe item clocks out of sight |
| 10-29, v0.6.3 draft | lock listed for removal, flicker expected | never run |
| 10-31, b1.1a | fade to 1 s over ~2 h, no head | below |
| 11-01, b1.2a | fade to 0 s, after the head opens | running |

I found no record of why the lock was lengthened to 8 s beyond a code comment ("v11: longer, with a release when the item is gone"). The original reason it was thought necessary should be treated as unknown.

## Why fade it

**The owner's reasons:**
- "My general biggest gripe is he needs to fight more. I have to pick the fights with him" (10-31). This is b1.2's goal.
- All hand-built rules are to go in time, leaving the fairness limits. The lock is a rule making a decision for him (10-23).
- "The lock should go entirely, but step it in a way that we can trace when something goes wrong" (11-01).

**The design reasons:**
- While locked he can't re-target when the situation changes, for example when a fight starts or the enemy is heard.
- The head can only influence his target at live readings. At 8 s it is largely unable to react, which limits what strategy can do.
- In self-play, a free choice favours the best answer to what the enemy is doing now.

**Against these reasons:** the enemy's share of his targets did not move at all when the lock came down in b1.1a (1.2% to 1.1%). **Nothing yet shows the lock is what stops him fighting.** The hands can already fight while locked, and the speed pay, item pay and item rule all still point at items.

## What happened when it was faded (b1.1a, no head)

The fade went 8 → 4 → 2 → 1 s over about 2 hours, with about 1 hour at the end.

| | Lock 8 s (u120) | Lock 1 s (u180) |
|---|---|---|
| Trips a player-minute | 12.6 | 20.0 |
| Targets reached | 40% | 21% |
| Enemy's share of targets | 1.2% | 1.2% |
| Frags a match-minute | 1.56 | 1.41 |
| Aim error, enemy in view (degrees) | 13.9 | 14.4 |

Fair head-to-heads, each seat at its own lock, 160 games, about ±4 points:
- b1.1a's end (1 s) against b1.1 (8 s): 66-94, 41.2%, frag share 44.7%.
- b1.1a's end (1 s) against b1.0a's end (8 s): 68-92, 42.5%, frag share 46.2%.

The run's own check of 73.8% at u170 played both seats at one short lock, which harmed the opponent. It is not evidence of strength.

**Limits of this evidence:** one fast fade, little time to adapt, no head. It doesn't show that a slower fade or a head would fail.

## What we have to replace it

There is no direct replacement. These are the parts that could supply commitment:

| Part | What it does | How far it replaces the lock |
|---|---|---|
| **The strategy head** (`sim/head2.py`), gate opening now | a slow GRU, ticking every 0.2 s, adds a bias to the target logits and a plan to the hands' memory. It reads the brain, the "in control" readout, stack, timers, score, clock and his current target | **The intended replacement, but unproven.** Its pay is combat plus win pay, not item pay. Nothing rewards it for holding a choice as such, and a logit bias does not guarantee a held choice under sampling. Its size against the hands' item pay and the rule is unmeasured. In the smoke run its bias was 12% of his target choice |
| **Giving up a trip** (`sim/duel_env.py:12679`) | changing target before arrival takes back the speed pay earned on that trip | **A small price** (-0.07 a player-minute, u35), already live in b1.1a, which still flickered. It only covers items: the way to a place or the enemy pays nothing |
| **`INTENT_SWITCH`** | 0.02 for changing target | small, and refunded on leaving a holding place |
| **The hands' memory and inputs** | he sees his target and its age (`intent_t`, input column 12) | could learn to hold; b1.1a's hour doesn't show it did |
| **The reading rate** | one reading a second | a floor of about 1 s, not commitment |

The item rule is not a replacement. It teaches items at live readings, except where `RULE_CONTEST` and `RULE_HUNT` silence it. Its weight is at its floor of 0.1 (`--intent-teach 9.13` has faded out; corrected 11-01, after the review), so more readings may mean more of its pull toward items, which works against the goal of fighting more.

## The current plan (b1.2a)

Started 11-01 09:08 from b1.1, 24 hours. Full card: [CARD.md](../runs/b1.2/b1.2a/CARD.md).

1. Head gate 0 → 1, +0.1 every 10 updates. At 09:55 it stood at 0.1 (u10).
2. Head-open save at about u110.
3. Lock 8 → 6 → 4 → 3 → 2 → 1 → 0 s, a step every 20 updates (~76 min at 3.8 min an update; updates are so far nearer 4.5 min). The save and optimizer before each step are kept.
4. About 10 hours to settle at 0 s.

Hold rule: a check at 40% or less against the start holds the next step; under 50% is flagged. The ramp has no way back, only the kept saves.

## Issues found while writing this

**1. The lock runs one second longer than its setting after a change (from the code; not run).** `intent_t` is zeroed on the frame a target changes, then gains 25 ms a frame. At the next reading, 40 frames later, it stands at 0.975 s. So a setting of H whole seconds frees the choice at H + 1 seconds:

| Setting | 8 | 6 | 4 | 3 | 2 | 1 | 0 |
|---|---|---|---|---|---|---|---|
| Earliest new choice after a change | 9 s | 7 s | 5 s | 4 s | 3 s | 2 s | 1 s |

So **"lock 1 s" in b1.1a was really about 2 s, and b1.2a's last step goes to a value never run.** Every number labelled "1 s" above should be read this way. Keeping the same target is not a change, so `intent_t` runs on and later readings are free.

**2. At 0 s, other protections stop mattering (from the code).** With `intent_t >= 0` always true, every reading is live. `TARGETS_FREE=2`'s protection (a place not dropped for "nothing" or another place) and `GONE_BELIEF` no longer do anything. The 10-12 reason for protecting places returns with no guard. `WEAPON_FREE` still works, since it acts on the choice itself.

**3. Flicker may be partly sampling, not decisions (a hypothesis, untested).** If the target is sampled at each reading, a spread-out distribution produces changes at every free reading even when no decision changes. The lock hid that. The intention output's entropy weight is small (`--ent-coef 0.005` × 0.1), but the rule's labels and the distribution's actual spread were not looked at. I did not confirm how the checks pick actions.

**4. Training's league shares one lock (from the card; not traced in the trainer).** `INTENT_HOLD` is one number per training process, so older selves in the league play at the current lock, which they did not train with. Only the checks play each seat at its own (`hold_seat`). This may flatter his league results during the fade.

**5. The two stages overlap in what they measure.** The head has about 7 hours open at an 8 s lock, where it rarely gets a live reading, then the lock falls under it. It may learn a policy for a world about to change. The opposite order was not tried.

**6. The start optimizer is from u170,** with the lock already at 1 s, on a network from u140. Its effect is not measured.

## Alternatives not built

- **A learned hold:** a separate output deciding when to re-choose, with the lock's job moved into the network. This addresses the sampling issue directly.
- **Stickiness on the logits:** a bonus for keeping the current target, faded slowly. A hand-built rule, but softer than a lock.
- **Keep a short floor:** stop at 2 or 3 s if 0 s costs games. The owner wants it gone entirely, so this would be his call.
- **A higher switch price,** sized against the entropy bonus.
- **Changing the pull toward items first:** lower item pay or fade the rule, since the evidence so far says the lock is not what holds down fighting.

## Questions for the review

1. Is the off-by-one in issue 1 right, and does it change how the b1.1a result or the steps should be read?
2. Is the head, as designed and paid, able to hold a choice at all? Could its bias outweigh the hands' item pay and the rule?
3. Is removing the lock likely to help him fight more, given the enemy's share didn't move in b1.1a? What would test this directly?
4. Is flicker mostly sampling, and how would we measure it? For example, the target's probability spread at readings and how many changes follow no change in the situation.
5. Is the order right: head first and then the lock, rather than together or the rule first?
6. Is the ~76-minute step long enough, given that b1.1a's fall took about 40 updates to show? Should a check at 40% do more than hold the next step?
7. What should we read at each step to tell a temporary dip from real harm?
8. Is there anything this document gets wrong? It was written from the code and records, by the session that started the run.

## Where to look

| | |
|---|---|
| The lock | `sim/duel_env.py`: `intend()` at line 6715, way pay and take-back at lines 12665-12692, notes at lines 343-378 and 459 |
| The head | `sim/head2.py` (header); `--head2*` in `sim/train_duel_rnn.py` |
| The fade | `docs/runs/b1.2/b1.2a/ramp_b12.py`, `tools/run/ramp_live.py`, `tools/run/ramp_head.py` |
| b1.1a's evidence | `docs/runs/b1.1/b1.1a/CARD.md`, `REPORT_0630.md`, `tools/run/head2head.py` |
| The run | `docs/runs/b1.2/b1.2a/CARD.md`, `train.cmd`; `data/sim_runs/duel_gru_b1_2a/` (read only) |
| The earlier draft | `docs/runs/v0.6.3/CARD.md` |

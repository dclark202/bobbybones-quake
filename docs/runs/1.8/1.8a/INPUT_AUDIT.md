# The input audit before 1.8a (2026-11-11)

*Owner: "audit ALL of his current inputs ... look for 'dead' inputs that have no effect on him anymore, things that were residuals that were
removed in previous runs, or that are actively hurting his ability ... blindspots ... for the mechanical and the brain/head networks."
Nothing was changed. The network audited is 1.8a's start (b1.2d's end's weights, 1,053 inputs).*

## How it was measured

| Measure | What it is | Tool, data |
|---|---|---|
| Constant in play | a column that never changes in 38,421 rows of raw inputs sampled from two full-size training updates (all ten maps, his seats and the league's, 1.8a's phase-1 settings) | `audit_obs.py` → `data/sim_runs/scratch_18a_obs/obs.npy` |
| Scale | the spread of a column after the network's frozen normalizer (1.0 = as designed; 0.2 = it arrives at a fifth of the intended size); the share of rows at the ±10 clip | the same sample against the checkpoint's `obs_mean`, `obs_var` |
| Share of the signal | of everything that varies at the first layer of a reader (the hands' encoder; the brain's input layer), the part that comes from a group: weights × real inputs. Faded columns count zero for the hands | the same sample, the start's weights |
| Blanked | a group's columns replaced by their average in the hands: how many of his action choices change on 400 frames × 8 seats of drawn inputs | `audit_ablate.py`. It only separates "nothing" from "something" (his memory amplifies any change): exactly 0 = truly dead |

Not measured: games with a group removed. A group can matter in rare moments that none of these weigh.

## Who reads what

| Network | Reads | Size |
|---|---|---|
| **Hands** (the mechanical network) | all 1,053 columns twice: flat through the encoder, and cut into 67 attention tokens of 24 kinds; plus the brain's answer as a token, the movement network's 64 features (the legs' branch), and the head's plan (shut) | encoder 336k weights, attention 270k, memory 1.18M |
| **Brain** (belief) | the first 868 columns, unfaded (so not the small items, the order, the timers, the map's table), every 0.2 s | 814k |
| **Its readouts** | the brain's state: the enemy's place, stack, weapon, zone, 1 / 2 / 4 s ahead, who takes the mega and red next, in control | 290k |
| **Head** (strategy) | the brain's state (256), its readouts (27 + 28 + 42 + 4), the hands' memory (512), and 81 input columns of its own: his health and armor, weapons owned and ammunition, the nearest mega and red, the clock and score, when he last took each item, his target as chosen, the order's ten | 677k |
| **Keep choice** | the head's state, the hands' memory, 7 numbers of its own (the target's age, contact, arrival, sound, hit, the held target's log p) | small |

## The 1,053 columns, by state

| State | Columns | What |
|---|---|---|
| Live and read | about 740 | |
| **Constant in play** | **239** | below |
| **Faded out of the hands** (v0.4.2's rule fade at 1.0; the brain still reads them) | **76** | the rule-made belief of the enemy's place (7), the height above him (1), the places' "the enemy is believed here" (16), the enemy's stack by rule (5), all of the pre-fire inputs (39), all of the emergence inputs (8) |

**The 239 constant columns:**

| Why constant | Columns | Groups |
|---|---|---|
| Parts that are off in duels or retired | 69 | more enemies (24: free-for-all), movement goal (7: courses), his legs (2), b3 ways (7), drift (4), style (4), the heavy machine gun and the gauntlet (about 14 across weapons, items, enemy), crouched (2), the hearing's "coming or going" (1), others |
| Newer parts never opened | 69 | b17 order (10), b20b space (8), b20b targets (51) |
| Outside his field of view (reads −1 always) | 19 | walls: 11 of the 16 rays (67.5° to 292.5°); sight: 5 long distances, 3 ceilings |
| Slots that are never filled | 32 | enemy projectiles: all of slots 5 and 6, the type flags and fuses of slots 2 to 4 |
| Nothing of the kind on these maps | 16 | hazards: every "deadly drop" |
| Always 1 ("exists", "slot holds a place") | about 34 | items, places, holds, small items |

They cost no skill: a column that never changes moves no weight and no decision. They cost a little compute, and three whole attention
tokens are constants ("others", "ways", "drift").

## By group

`n` columns; `const` constant; `scale` the median spread after the normalizer; `hands`, `brain` the group's share of the signal at that
reader's first layer.

| Group | n | const | scale | hands | brain | Note |
|---|---|---|---|---|---|---|
| enemy | 35 | 3 | 0.90 | 13.1% | 15.8% | the largest for both |
| intention | 16 | 0 | 1.05 | 11.0% | 0.5% | his chosen target |
| items | 54 | 11 | 1.13 | 7.6% | 13.5% | |
| self | 13 | 1 | 1.08 | 7.1% | 2.5% | |
| weapons | 27 | 6 | 1.01 | 6.5% | 0.3% | "holding plasma" hits the clip 10% of rows |
| map reader | 32 | 0 | 1.08 | 4.2% | 1.9% | |
| own hands | 14 | 0 | 0.98 | 3.9% | 5.6% | **over-scaled**: "zoom finger free" at the clip 64% of rows, "zoomed in" 35%, the jump thumb 9 to 12% |
| sounds | 24 | 0 | 1.19 | 3.7% | 3.9% | |
| place | 29 | 0 | 0.98 | 3.5% | 4.4% | |
| more items | 24 | 4 | 0.97 | 2.7% | 1.3% | |
| sight | 28 | 8 | 0.59 | 2.7% | 0.4% | |
| routes | 7 | 0 | 1.00 | 2.4% | 2.8% | |
| hazards | 32 | 16 | 0.39 | 2.4% | 0.4% | lava only |
| projectiles | 90 | 32 | 0.01 | 2.1% | 0.2% | an enemy projectile is in his inputs 0.9% of rows |
| hearing | 9 | 1 | 0.65 | 1.3% | 6.4% | |
| walls | 16 | 11 | 0.00 | 1.0% | 0.3% | five rays live |
| lead | 6 | 0 | 1.31 | 1.0% | 0.2% | rockets' and plasma's meeting point: live 5% of rows |
| floor | 8 | 0 | 1.06 | 0.9% | 0.2% | |
| memory | 18 | 1 | 0.36 | 0.8% | 0.4% | the mega's and red's timers |
| enemy shots | 18 | 2 | 0.54 | 0.7% | 1.3% | |
| clock and score | 8 | 0 | 1.00 | 0.7% | 0.1% | |
| hits | 4 | 0 | 0.40 | 0.7% | 0.7% | |
| jump ahead | 5 | 0 | 0.29 | 0.6% | 0.0% | |
| **v02 places** | **96** | 8 | **0.16** | **0.4%** | 1.0% | the eight nearest of the pros' places |
| **b2 holds** | **64** | 10 | **0.16** | **0.4%** | 3.8% | the holding places |
| his movement | 4 | 0 | 0.76 | 0.4% | 0.1% | |
| enemy pain | 5 | 0 | 0.77 | 0.4% | 0.9% | |
| dropped weapon | 8 | 0 | 0.45 | 0.3% | 0.0% | |
| v02 believed | 21 | 0 | 0.30 | 0.3% | **6.8%** | 7 faded; the rule-made belief |
| **b12 small items** | **112** | 7 | **0.33** | **0.2%** | not read | "reads them, barely acts on them" (b1.2c) |
| v031 enemy stack | 6 | 0 | 0.83 | 0.1% | **4.1%** | 5 faded; the rule-made stack |
| **v036 rocket aim** | **20** | 0 | **0.12** | **0.06%** | 0.1% | the backstop and floor point for rockets |
| v02 position | 10 | 0 | 0.23 | 0.04% | 0.1% | |
| v02 items | 13 | 1 | 0.22 | 0.03% | 0.1% | when he last took each item |
| v02 game | 3 | 0 | 0.28 | 0.01% | 0.0% | |
| grenade arc | 6 | 0 | 0.03 | 0.00% | 0.0% | he holds grenades 0.1% of the time |
| v036 prefire | 39 | 0 | 0.24 | **0 (faded)** | 0.3% | |
| v036 emergence | 8 | 0 | 0.50 | **0 (faded)** | 0.2% | |
| b17b timers | 4 | 0 | 0.39 | 0 (weights zero) | not read | the yellows' timers: live in the inputs, unread |
| more enemies, movement goal, style, his legs, b3 ways, v038 drift, b17 order, b20b space, b20b targets | 137 | 137 | — | 0 | 0 | constant |

## What stands out

1. **Everything added since v0.2 arrives too small.** The converters give a new column the statistics "mean 0, spread 1" whatever its
   real spread, and the trainer keeps the statistics frozen. Of the 814 live columns, 291 arrive under 0.3 of the intended size and 84
   under 0.1. The places (96), the holds (64), the small items (112) and the rocket aim (20) are 292 columns that together carry about 1%
   of the hands' signal. That is the likeliest reason "he reads the small items and barely acts on them", and the same would happen to
   every input 2.1 adds. `sim/renorm_policy.py` re-measures the statistics and rescales the weights so that he answers exactly as before.
2. **A few old columns are too large.** The zoom's two columns sit at the ±10 clip in 35 to 64% of rows (their statistics were frozen
   when he almost never zoomed), the jump thumb's in about 10%, "holding plasma" in 10%. Each is a jolt of ten units into the encoder on
   an ordinary event. The same re-measure fixes them.
3. **The hands cannot see where to pre-fire.** All 47 pre-fire and emergence columns are faded to zero in the hands since v0.4.2; what
   is left is the brain's answer as one token. He fires 9% of his rockets with nobody in view, the pros two thirds. 2.1's "spam"
   instruction is the planned answer; the audit says the hands have nothing else to go on.
4. **The brain leans on the hand-built belief.** The rule-made belief of the enemy's place and the rule-made stack filter are 11% of what
   varies at the brain's input. The hands were faded off them; the brain was not. It may be largely re-reading a rule the owner called a
   failed baseline.
5. **The head does not know which weapon is in his hand** except through the hands' memory: its own columns have what he owns and his
   ammunition, not what he holds (that was in 1.5a's weapon part, scrapped). It also has the mega's and red's place but no timer of the
   yellows and nothing of the small items. In the two heads that trained (1.3b, 1.7a) the strongest columns were the brain's "in control"
   readout and his own health and armor.
6. **He never crouches and never walks.** Both keys exist and are used 0.0% of frames; "crouched" is constant for him and for the enemy.
   Not an input fault: nothing has ever made quiet movement or a lower hitbox pay.
7. **The yellows' timers will open by themselves.** Their token is left out while shut, but the encoder reads the four columns from zero
   weight; in 2.0c they grew to 15% of an ordinary column's weight in 100 updates. The owner approved them in 1.7b ("can't hurt").
8. **Enemy projectiles: six slots, two used.** A projectile is in his inputs in under 1% of rows (he only gets what he sees or hears).

## Suggested, for the owner's call

| # | Change | Why | Cost and risk | When |
|---|---|---|---|---|
| 1 | **Re-measure the input statistics once, at 1.8a's start** (`renorm_policy.py`: output unchanged) | items 1 and 2: 291 columns under-sized, a handful over-sized; every later run inherits it | he answers the same at the start (proved by the same-answers check), but he learns differently afterwards: the under-sized inputs get their say faster, and Adam's kept moments for the encoder no longer fit. One more new thing in the first updates, beside AIM3. To test first: ten updates and a level check | ❓ at 1.8a's start, or as its own short run before it, or left for 2.1 |
| 2 | Leave the 239 constant columns in place for 1.8a | they cost no skill; cutting them changes every tool, the plugins and the servers' export | none | a clean-up when 2.1 rebuilds the head's inputs and the plugins anyway |
| 3 | Give the head "what he holds" and the yellows' timers as columns of its own | item 5; both exist as inputs | new head inputs at zero weight: small | with 2.1's head inputs |
| 4 | Decide what the brain should read of the rule-made belief | item 4; the standing aim is to retire hand-built rules | fading it from the brain is a real change to the part everything else leans on: its own test | 2.n, not 1.8a |
| 5 | Pre-fire for the hands | item 3 | — | 2.1's "spam" instruction; nothing in 1.8a |
| 6 | Enemy projectile slots 6 → 3; the outside-of-view rays out | bloat only | with the clean-up of 2 | later |

**For 1.8a itself, my recommendation:** only item 1 is worth deciding now, because it changes how well everything after it learns.
Nothing in the audit says an input is actively harming him beyond the over-sized columns of item 2.

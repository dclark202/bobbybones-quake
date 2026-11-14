# 2.3: the head sets the weapon, as part of the decision

**The family's design (owner, 2026-11-14). No run is carded; nothing here is built beyond what is listed as built.** After
[2.2](../2.2/README.md) (the new decisions as rows of his goal choice, each with a forecast).

## The goal

The weapon becomes part of what the head decides: "hold this angle **with the rail**" is one decision. The hands carry it out. Today the
weapon key is the hands' own scores plus the head's weapon scores added on top (1.5a), and the hands can always outvote the head.

## Decided (owner, 11-14)

| # | Decision | From |
|---|---|---|
| 1 | Starts from **2.2's end**: the head has decisions that give it a reason to want a weapon | 1.9a handed the weapon over to a chooser with no reason: it changed up to 107 times a minute, half against the hands' own pick |
| 2 | The weapon is chosen **with the goal, at the moments the goal is chosen or kept** (the keep choice's readings), not on a clock of its own. What holds the goal holds the weapon | the same commitment, one place |
| 3 | **Built out of what he has**: the head's weapon scores that are already added to the weapon key grow; the hands' part shrinks; then the head's choice binds. No new chooser | 1.5a's part won games (56.5% against 1.3b's end) |
| 4 | Both parts of the sum stay regularized, their sizes recorded and flagged over 40, from the first update | rule 11 |
| 5 | **No table, no pro target, no weapon share as a pass mark.** Which weapon he holds is his own, from what wins. Weapon shares are readouts | rule 12; 1.7c |
| 6 | No cost for firing, switching or holding a weapon | owner 11-04 |
| 7 | The hands keep everything about using the weapon: aim, when to press, the switch's timing inside a fight | inputs and jobs by role |

## The steps

| Step | What opens | What plays | Its measure |
|---|---|---|---|
| A. Silent | the weapon's forecast: frozen moments where only the weapon differs; the head's weapon scores taught toward the forecasts' best for the goal he is on | as 2.2's end | the forecast ranks weapons better than chance on held-out moments; the head's weapon scores agree with it more often |
| B. The head's part grows | the credit for the weapon key moves to the head; the hands' rows are decayed toward zero | the sum, more and more the head's | weapon changes a minute (flag over 20); the bound weapon against the hands' own pick; hit rates by weapon and range; checks |
| C. Binding | the head's weapon binds for the goal's length, its share opened on a measure | the head's weapon; the hands switch only where the goal leaves it free (out of ammunition, the weapon not owned) | the same; the rail owned and in hand at range (readouts); the owner's play test |

## Where the code is

| Part | Built | Files |
|---|---|---|
| The head's weapon scores added to the weapon key; its credit | yes (1.5a; in every network since) | `sim/head2.py` `add_weapon`, `has_weapon`, `wsc`, `wadd`, `np_wadd`, `np_wadd_on`; the trainer's `--head2-wpg` (live `H2_WPG`), `wpn_group` |
| A binding weapon in the simulator | yes (2.1's build) | `sim/duel_env.py` `INS_BIND`; `sim/head2.py` `bound_mask`; the trainer's `--ins-bind` |
| Weapon scores given the chosen row | yes, for the instruction's scorer | `sim/head2.py` `ins_wscores`, `ins_wq_logp`, `ins_joint_logp` |
| Frozen moments where only the weapon differs | yes (2.1's build; never opened: 2.1a stopped before update 75) | the trainer's `--branch-wpn-p` (live `BRANCH_WPN_P`); `sim/branch.py` |
| The forecast with a weapon in the candidate | yes; no skill yet | `sim/appraise.py` (`N_WEAPON` 10: nine weapons and "none") |
| The weapon dial at play time, the pros' table | yes: **not used** (rule 12; 1.7c) | `docs/runs/1.7/1.7c/DIAL.md` |
| Weapon habits on league seats | yes: **out since 2.0e** (owner 11-14) | `--habit-p` |

## To build

| # | What | Notes |
|---|---|---|
| 1 | The weapon chosen **at the goal's readings** and held with it (the keep choice's "keep" keeps the weapon) | joins the weapon scores to `intend()`'s readings; today the weapon key is read every frame by the hands |
| 2 | The weapon scores **given the goal** for target rows (reuse `ins_wscores` on the rows of 2.2) | at zero weights first; `same` |
| 3 | The hands' share of the weapon key decayed on a dial (live), recorded each update | rule 11's sizes; not a fade of a rule: both parts are learned |
| 4 | The binding share (live), what stays free for the hands (no ammunition, weapon not owned, the switch's timing) | from `INS_BIND`, `bound_mask` |
| 5 | The readouts and flags: weapon changes a minute, bound against the hands' pick, hit rate and damage by weapon and range before and after | 1.9a's flag (over 20 a minute) was only a watch item there: here a guard from update 1 |
| 6 | The server side | `plugins/duelbot.py`, `plugins/netpass.py`, `sim/export_duel.py` |

## Weaknesses to carry into the card

- **The lightning.** He fights with it almost only (HISTORY.md, open problems); self-play overvalues it because his copies are easy to
  track (`docs/design/LG_REAL_VS_SIM.md`). A head that learns the weapon in that equilibrium learns the lightning again (b1.1 to b1.2a: the
  head learnt the rail is worthless). 2.0e's dodge inputs and 2.2's decisions (a held angle, fire at a corridor) are what should give
  other weapons a worth; if the readouts at 2.2's end still show lightning only, say so before starting 2.3.
- The weapon-only frozen moments were never run.
- A bound weapon the hands disagree with costs aim (1.9a: "half against the hands' own pick").
- Research check (rule 14) owed on the card: MECHANICS.md (weapons by range, switch time), README core 7 ("burst breaks a big stack,
  streams finish; the lightning does nothing beyond 768"), PRO_INTERVIEWS.md.

## After 2.3 (parked, in the order last discussed)

| | |
|---|---|
| The head's own pay | the head paid by the win chance only (standing word, 11-11), with the judge re-fitted on the new play |
| Opponents | league seats that play what his copies do not (a holder, a dodger); small exploiters (AlphaStar, GT Sophy) |
| Information | what he does to learn where the enemy is (a "check" decision; the verb exists in `INS_VERBS`) |
| This opponent | adapting in a game and across games to one opponent (owner 11-11: after the strategy layer works) |

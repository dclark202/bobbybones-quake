# b1.4a: the head blended in beside the rules, learning the whole time

*2026-11-02 evening (owner): "B1.3 - fade head IN. It starts overnight and is ready sometime tomorrow. B1.4 - fade OLD rules out"; "we bring it in in b1.3 to learn how to copy the rules that exist, and then once we know it can, we remove those rules and let the head train"; "I'm fine leaving combat, item and win pay in him. I view the win pay as the correction factor on top of those". 2026-11-03 morning, after the head-alone test (b1.3a's head choosing alone: 74-126, 37%): "he was always going to suck with a hard swap ... The only reasonable way to do this is to blend the two in together"; "we need to show that it can be stable with both before trying to fade the hard coded rules out"; "H2 copy has to go ... The point of the copy was the pretrain it. That's done now. MIX fades to 0.5, HEAD learns the whole time. For B1.4a, fade the HEAD in over 80 updates, 10--90. Let it run for 12 hours, I will review this evening for the 8s lock." The family: [README](../README.md). The earlier plan on this card (the head to mix 1, then the lock and the way pay out, with the copy lesson fading behind) was replaced on 11-03; its trial (`trial_b14a.log`, ALL PASSED) tested that plan's code.*

**Marks:** ✅ built and tested · ⏳ to build · 🧪 to measure · ❓ owner's decision

## The owner's page

| | |
|---|---|
| Started from | **started 2026-11-03 09:18, 12 h** · **b1.3a's end** with its optimizer (`keep/policy_end_b13a.pt`): the head shut in play (mix 0), its copy of the rules' choice at 87% agreement |
| Run | `duel_gru_b1_4a` |
| What | his target choice becomes a blend: the head's share rises 0 → 0.5 and the rules' share falls 1 → 0.5 with it. The head learns from his whole pay the whole time. Nothing is removed: the goal is to show the two are stable together before the rules fade out |
| How his target is chosen | the target scores are (1 - mix) x the hands' scores (the rules' imprint) + mix x the head's own scores (`H2_MIX`, a buffer in the network). Where the head has no state yet (respawn to its first tick) the hands' choice stands; counted (`head2.copy.no_state`; 0 in the trial) |
| The hands' target outputs | **frozen** (`--head2-sole 1`): the rules' imprint stays exactly as b1.3a left it; no gradient, entropy or rule label reaches it. One learner on the choice (b1.2a's blowup). The rest of the hands (movement, aim, weapon) learns as usual |
| The head | learns from his whole pay from update 0 (`--head2-pg 1`, `--head2-pay all`); its pull on the choice grows with the mix |
| The copy lesson (`H2_COPY`) | **off from the start** (0): it was b1.3a's pretraining, done |
| The 8 s target lock (`INTENT_HOLD`) | **stays at 8 s**; the owner reviews it this evening ❓ |
| The way pay (`INTENT_SEEK_W`) | stays (1) |
| Combat, item, win pay | unchanged |
| Length | **12 hours** (`--minutes 720`) |
| League, checks | b1.3a's end, b1.2d's end, b1.1 and v0.6.0's end as anchors; 200 games (20 a map) every 20 updates against the start (b1.3a's end at mix 0), every fourth against b1.1; each save checked at its own mix; the panel. Never stopped |
| Cores | the trainer on the 8 performance cores; the checks, panel, ramp and logger on 8 efficiency cores; 4 left for the owner |
| Kept | every save during the fade with its optimizer (`keep/policy_fade<update>_b14a.pt`), the first save at mix 0.5 (`policy_Adone_b14a.pt`), the end (`policy_end_b14a.pt`) |

## The schedule (`ramp_b14a.py`, on one clock of updates that stops while a hold is on)

| Updates | `H2_MIX` (head's share) | Rules' share | `H2_COPY` | Head learns | Lock | Way pay |
|---|---|---|---|---|---|---|
| 0 to 10 | 0 | 1 | 0 | yes (no pull on play yet) | 8 s | 1 |
| 10 to 90 | 0 → 0.5, a straight line (+0.00625 an update) | 1 → 0.5 | 0 | yes | 8 s | 1 |
| 90 to the end (about 160) | 0.5 | 0.5 | 0 | yes | 8 s | 1 |

The mix at each check: update 20: 0.06 · 40: 0.19 · 60: 0.31 · 80: 0.44 · 100 on: 0.5.

**No hold (owner, 11-03: "Do not stop the fade, just let it go over the 80 updates. If it goes badly just respond here and we will review"):** the mix runs 10 to 90 whatever the checks read; a check under 50% is flagged in the chat for the owner to review.

**Tripwire (flagged in the chat at once; the run never stopped):** the head's own target scores' centred length over 60 (`--raw-lim`; the copy's end about 20), a non-finite number, a skipped piece.

**How fast the head learns as it fades in:** the pay's push on the head's scores is scaled by the mix (a sixteenth of full at 0.06, half at 0.5), but Adam sizes each step by the gradient's own recent size and the head has its own group, so its steps are about the same size at any mix. What changes is what it learns from: at a low mix it nudges a choice the rules still make; only near 0.5 do its own choices shape the games. Its memory (GRU) also learns from its own value, which the mix does not scale.

## Before the start

| Step | Where it stands |
|---|---|
| The mix in the network, the trainer, the checks, the plugin, the export | ✅ built and tested (`mix_unit.py`; the trial of 11-02) |
| `make_files.py` (b1.3a's command with `--head2-pg 1 --head2-mix 0 --head2-sole 1`), settings check against b1.3a's | ✅ PASS (unchanged by the new schedule) |
| `ramp_b14a.py` for this schedule: `H2_MIX` 0 → 0.5 over 10 to 90 only, no hold; the copy, lock and way pay dials out of it | ✅ built 11-03; tested on fake files at a tenth scale (the mix line, the kept saves) |
| `start.ps1`: `H2_COPY=0` in live.json (was 1); its log line | ✅ |
| A trial | skipped on the owner's word ("you do not need to do a 10 update dry run, just start the run"; `-NoTrial`) |
| The owner's go | ✅ 11-03 morning; **started 09:18** (`start.log`) |

## Judged by

| Measure | Wanted |
|---|---|
| Win rate against the start (b1.3a's end) | at least 50% at mix 0.5 for three checks in a row: the sign that the two are stable together and b1.4b can fade the rules out |
| Against b1.1 and v0.6.0's end | holds |
| The head's own scores' length | bounded, no runaway |
| How often the blend's choice differs from the rules' alone | rises with the mix (the head has a say); reported |
| The enemy's share of his targets | up ("he needs to fight more") |
| Items a minute, stack at fights, time at spawns | hold (floors from b1.3a's end) |
| No spawn camping (v0.4.4), no holding a spot all game | the panel |
| The owner's play test | |

## The equilibrium

The head plans for his whole pay: combat, the item table and the win correction; in self-play the combat and item parts are zero-sum and the win part is the correction both copies gain from getting right. Half his choice stays the rules' frozen imprint, so his play cannot drift far from b1.3a's while the head learns: a blend that settles where the head adds what the rules miss (more fights when level or ahead, items when behind or the enemy is far). The risk is a head that undervalues the items' timing, which only the rules carried.

## Red team

| | |
|---|---|
| The head alone was 37% | the blend at 0.5 had never been measured; the fade runs anyway and a check under 50% is flagged for review |
| The checks lag | a check takes about an hour: its number is for a mix 10 to 15 updates older than the run's |
| The optimizer's memory | the head's Adam state comes from the copy lesson; its first steps on pay are sized by that history for about an update |
| Frozen rules | their labels are still computed and reach nothing (the cost of the rule code stays until b1.4b removes it) |
| The lock reviewed this evening | a change mid-run is a second new thing in the run: at a save, with the optimizer kept, and only after the fade has finished |
| Pay pathologies (ledger) | negative frags, sign flips, lopsided games: watched |

## Changes on the fly

| Time | Change | Why |
|---|---|---|

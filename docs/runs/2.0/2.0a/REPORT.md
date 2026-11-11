# 2.0a: report (2026-11-09 07:35)

**Run**: `duel_gru_2_0a`, from 1.7a's update 90 (1.7a's result), 2026-11-08 21:29 to 06:56, 565 minutes, 98 updates, no stall, no
MAJOR line. The dials went as written (`live_applied.json` at update 73: `DMG_REWARD` 0.001, `DMG_TAKEN_W` 1.0, `WIN_ADD` 0.6).
The end is kept as `keep/policy_end_20a.pt` with its optimizer. The card: [CARD.md](CARD.md).

## Checks (200 games each, Cypher's measures, PERCEPT_SPEED 0)

| Update | Against | Record | Win rate | Frag share | Worst maps |
|---|---|---|---|---|---|
| 10 | 1.7a's update 90 (the start) | 100-100 | 50.0% | 50.3% | level everywhere |
| 30 | the start | 82-118 | 41.0% | 47.4% | Hektik 4-16, Cure 8-12 |
| 50 | the start | 100-100 | 50.0% | 48.9% | Sinister 5-15, Toxicity 6-14 |
| 70 | 1.6a's end (the long-term control) | 108-92 | 54.0% | 50.9% | Hektik 6-14 |
| 90 | the start | 84-116 | **42.0%** | 45.5% | Cure 6-14 (33% frags), Aerowalk 6-14, Lost World 9-11 |

Update 90 is the first check wholly under the new pay (the fade ended at 70). None under 40%. 1.7a's u90 read 63% against 1.6a's
end; 2.0a's u70 reads 54%: the same loss seen from the other side.

## The ledger (pay a player-minute)

| Update | dmg dealt | dmg taken | frag | death | win part (size share) | items | total |
|---|---|---|---|---|---|---|---|
| 10 (dials at 1.7a's) | 1.86 | -1.58 | 1.04 | -1.10 | 0.09 (0.42) | ~0 | 0.30 |
| 50 (mid-fade) | 0.83 | -0.80 | 1.08 | -0.88 | 0.13 (0.51) | 0.08 | 0.41 |
| 90 | 0.35 | -0.36 | 1.21 | -1.16 | 0.09 (0.60) | 0.03 | 0.11 |
| 98 | 0.34 | -0.35 | 1.13 | -1.11 | 0.03 (0.60) | -0.02 | -0.02 |

The swap did what it was built to do: damage pay down 5.5 times to the floor, zero-sum (dealt = taken), the judge's part 60% of
the pay's size. The trade bonus is gone (an even trade pays 0).

## What he did with it

| Measure (the update 90 check: he / the start / the pros) | | |
|---|---|---|
| dies when outstacked | 0.549 / 0.552 / 0.299 | **unchanged** |
| escapes when outstacked | 0.410 / 0.395 / 0.639 | unchanged |
| the weaker hits first | 0.220 / 0.230 / 0.469 | unchanged |
| the bigger stack wins | 0.855 / 0.884 / 0.775 | down a little (he loses more as the stronger) |
| fights where he is the outstacked one | 2187 / 1704 | **he carries less stack** |
| mega / red / yellow taken (200 games) | 1231 / 1451 / 2520 vs 1364 / 1781 / 2263 | **fewer megas and reds, more yellows** |
| lightning / rockets / rail in hand in games | 0.64 / 0.19 / 0.01 (update 1: 0.43 / 0.24 / 0.03) | **lightning unchanged, the whole run** |
| frags a match-minute | 2.2 (update 1: 1.2) | no passivity |
| keep choice | share 0.975, re-decides 0.47, quiet 0.036, kl 0.002 | quiet, learning |
| damage a minute (Cypher) | 332 vs 340 | about the same |

## Reading

1. **Removing the damage pay did not move the weapon, the committing to losing fights, or his stack-carrying, in 98 updates.** The
   lightning is 64% of his time in hand from update 10 to 98 under a pay that gives it nothing special. So the LG-only play is not
   held up by the damage pay alone: it is a habit of the policy (1.5a to 1.7a trained under the damage pay for 500+ updates), or
   the lightning is simply the best weapon under his aim limits at the ranges he fights. Either way the incentive swap by itself
   is not the lever; a run from this end tells more only if something else changes too.
2. **The measured prediction held**: the card said the weak side's losing fight is priced about as today under 2.0a (1.17 vs 1.23) and
   that only a death priced above the frag changes it. The Cypher rows confirm it: dies-when-outstacked 0.549 against 0.552.
3. **He lost 8 points against the start and took fewer megas and reds.** With the damage pay gone, most of his per-frame signal is the
   ±1 frag/death flats plus a zero-sum judge; the item table's 0.35/0.30 is unchanged but now competes with a thinner hands' pay.
   One check of 200 is worth about 3.5 points of noise, so 42% is a real loss, small.
4. **Variance**: the judge's part at 0.60 of the pay size tripped the ramp's FLAG on 15 updates (0.600 to 0.606): at the threshold, not over
   it in any meaningful way. The kl 0.029 and clip 0.30 at the end are 1.7a's normal.

## What I propose for 2.0b (his call)

The owner's problem ("blindly committing to fights he knows he will lose") is a death-pricing problem, measured so before the go
and confirmed tonight. Two parts, one new thing each, in order:

- **2.0b: the death costs more than the frag pays.** `DEATH_W` as a live dial (new code: the flat is hard-coded ±1.0 in `duel_env.py`),
  from 1.0 to 1.5 over updates 10 to 70, from 2.0a's end (or 1.7a's u90: 2.0a's end is 42% against it). Margin for the weak side's
  fight-to-death against chip-and-leave: 1.17 -> 1.67 (the card's table). Risk: negative-sum pay = passivity; the alarm stays at
  frags a match-minute under 1.5, reported every update. A death priced by the stack given up (2.0b') is the better form but needs
  the judge's weights believed; the flat is one knob and it is measurable in a night.
- **The judge's refit as a daytime measurement** (2.0c's prerequisite): fit on 1.7a/2.0a self-play with the pros' rows, read its prices
  table and weapon values before any run uses it. The last refit (10-29) priced owning the rail below nothing.

Not proposed: a second run of 2.0a's dials alone (reading 1), the weapon dial (owner: leave it).

## State

The trainer ended on its clock at 06:56. The watcher (29228), the ramp (43720) and the self-play logger (40088) are still up, idle,
on the efficiency cores; they stop on the owner's word. Nothing committed.

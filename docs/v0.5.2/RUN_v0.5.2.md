# v0.5.2 on one page: the strategy head opened, then the item rule faded, behaviour-gated

*2026-10-26 (owner; renumbered that night: v0.5.1 is now the win-chance pay, [RUN_v0.5.1.md](../v0.5.1/RUN_v0.5.1.md), and this run comes after it, from v0.5.1's end, on win-chance pay alone): first planned from v0.5.0's end ([RUN_v0.5.0.md](../v0.5.0/RUN_v0.5.0.md)) after its ≥ 6 h on `!aim default` with the
loopholes closed. Two steps, one after the other: the head opens while the item rule still guides his target (v0.4.3 faded the
rule before any head existed, so for a whole version nothing guided the choice, and the spawn camping began), then the rule fades
with the head taking over. Each step is stepped by the checks AND the behaviour panel; a red holds or steps back by itself.*

**Marks:** ✅ built and tested · ⏳ building · 🧪 to measure · ❓ owner's decision · ⏸ later

## Start

| | |
|---|---|
| Network | v0.5.0's end (`keep/policy_end_v050.pt` + optimizer) |
| Code | v0.5.0's (`v050`), every v0.5.0 fix on; `!aim default`; the mix 60 / 30 / 10 |
| Control | v0.4.2b's end (fixed, as in v0.5.0) and v0.5.0's end; every 4th check v0.4.1's end (owner: "Use v0.4.1 as the ref. v0.3.10 can be out") |
| Before the head opens | the speed pay phased out at v0.5.0's end (owner): live SPEED_PAY 0.25 -> 0 in steps of 0.05 every 25 min from 04:00 Tue (scratchpad v050/ramp_speed50.py; the jump runs' own speed pay kept); equilibrium: speed is worth only what it wins |

## Schedule (owner, 2026-10-26)

| When | What |
|---|---|
| Mon 21:00 | look at v0.5.0 (likely: let it run overnight) |
| Tue 04:00-06:05 | the speed pay phased out (v0.5.0's end) |
| Tue 06:30 | the report on v0.5.0 |
| Tue 07:00-08:00 | v0.5.1 starts: the head attached shut, trains shut ~20 updates and a check, then opens (phase 2) |
| Tue afternoon | play test after phase 2; then phase 3 (the item rule fades) |
| Wed noon | v0.5.1 ends (or earlier, the owner's call) |

## Phase 2: the strategy head

| | |
|---|---|
| What | the head's gate cap 0 → 1 (live `H2_GATE_CAP`), the item rule still on |
| Steps | +0.1 every 25 min while the checks pass (games 50%+) AND the behaviour panel is green; hold at 45-50% or one red; back to the last passing value under 45%, two checks under 50%, or a red twice |
| Watched closely | his targets per map (the head pushed the lightning gun to 82% in v0.4.4), time at each weapon spawn, roaming, hunting the watcher |
| Ends | the cap at 1.0 with two passing checks at full |

## Phase 3: the item rule faded (after phase 2's play test)

| | |
|---|---|
| What | the item rule's weight 1.0 → 0 (live `INTENT_TEACH_W`), the head open |
| Steps | −0.1 every 25 min on the same gates; a red target or camping limit steps the rule back up |
| Ends | the rule at 0 with two passing checks; then the owner's play test |

## After

| | |
|---|---|
| Then | pay by win chance (v0.4.5's plan, renumbered), on the owner's go |
| Owner | a local game after phase 2 and after phase 3 |

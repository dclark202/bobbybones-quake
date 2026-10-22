# v0.3.9 on one page: what changes from v0.3.8

*Decided 2026-10-21 night with the owner ("Start it up when you're ready and let it go til 4pm tomorrow"). Folder
`duel_gru_v0_3_9`, from v0.3.8's end (save 506, optimizer kept); runs to **16:00 Thu 2026-10-22**. Code: branch `v039` (worktree
`ql-bot-v039`). v0.3.8 ended early at save 506 (the owner: "a wash for trial and error of rail. This is the right direction to go").
Status: **building** (the start waits for every change below to pass its tests).*

**Marks:** ✅ built and proven identical with its switch off · ⏳ building, tests pending · 🧪 measured · ❓ owner's decision during the run · ⏸ not in v0.3.9

## Where v0.3.8 ended

| | v0.3.8 |
|---|---|
| Against v0.3.7's end (previous best), aim 3 | 54.0% (u326) → 52.4–52.5% (u366–486) |
| Against v0.3.1's end (control), aim 3 | 80.8% (u346) → 82–83% (u386–466) |
| Rail: in hand / share of frags | 5–8% / 4–6%: unchanged by the shot price cut, the long-rail pay and the streak bonus |
| Pre-aim at a fresh sighting: median error; within 15° (real games) | v0.3.8 40°; 26% (140 sightings). Older Bobbys 30°; 30%. The owner 23°; 35%. Pros 12°; 58% (4,638) |
| Jump presses a minute, enemy out of sight (real games) | v0.3.8 61; older Bobbys 30; the owner 33; pros ~24 (from their motion) |
| Hop pay a player-minute (training) | v0.3.6 0.4 → v0.3.7 0.9 → v0.3.8 2.1, take-offs 22 → 28 → 38 a minute, speed unchanged (~330) |

## 1. Pre-aiming (the owner: "preaiming. that's it")

| Change | Detail | State |
|---|---|---|
| Pre-aim pay (`PREAIM_PAY=0.05`) | At each **fresh sighting**: the line of sight between the two opens after at least 1 s closed (whichever way they face); both alive; neither respawned in the last 1 s; in games and pro starts only. Each crosshair's error at that very frame (before any reaction) scores q = 1 at 0°, falling straight to 0 at 60°. The better-placed player is paid 0.05 × (the difference), the other loses as much (zero-sum). About 10 sightings a minute: at most ~0.25 of a frag a minute. The pay reads the truth; his inputs stay what he perceives | ⏳ |
| Equilibrium | crosshair on the likely sight lines when contact is near, and not walking into a held angle; avoiding sightings earns nothing. Goals: weapon use, counterplay | – |
| Pre-aim counters | error, share within 15°, q, by weapon, in every update's metrics and on the watcher's line; the yardsticks above | ⏳ |

## 2. Jumping (the owner: "He should use jumping to get placed quickly. Period.")

| Change | Detail | State |
|---|---|---|
| Hop pay off (`HOP_PAY` 0.003 → 0) | It paid speed gained from hop to hop above the chain's best; a chain ended after 0.4 s on the floor, under 250 u/s or with the enemy in view, and its best was forgotten, so every new chain re-earned the 320→480 gain: a loop (2.1 a player-minute in v0.3.8, more than his frags) | ⏳ |
| Chain-hop pay off (`HOP_CHAIN` 0.005 → 0) | It paid each hop that kept speed over 320: a pay for the count of hops | ⏳ |
| What pays for jumping now | Only the speed pay (`SPEED_PAY`, unchanged): new ground on the way to his chosen target, by its speed (nothing at 320, full at 480); per stretch of ground, so detours and zigzags earn nothing; a trip given up gives it back | – |
| Jump cost (`JUMP_COST=0.004`, new) | Each take-off with no enemy in view, in games and item runs (not in jump practice): a hop that buys speed earns ~20× that back through the speed pay; one that doesn't is a small loss. At 38 take-offs a minute: ~0.15 a minute | ⏳ |
| Equilibrium | he jumps when it makes the way faster, otherwise not; nothing changes in fights (the cost is only with nobody in view). Goal: speed and movement | – |
| Watched | speed with the enemy unseen and take-offs a minute; the cost up if he still spams, down if his speed falls (live, on the owner's yes) | ❓ |

## 3. Other changes

| Change | Detail | State |
|---|---|---|
| Aim 4 | training at aim 4 (100 ms reaction, 160 ms acquire; v0.3.8: aim 3, 125/200); checks at aim 4, one bridge check at aim 3 | ⏳ |
| Staggered starts (`STAGGER_START=1`) | each match's first game begins at a random point of its clock: no restart wave | ⏳ |
| Safe restart (live settings) | changed settings reach the games as they start; no running game is cut off; each use on the owner's yes | ⏳ |
| Jump practice: landing reach (`JUMP_OVER_ANY=3`) | a make must reach within 64 u of the landing's distance along the jump's line (Sinister 29's lucky drop) | ⏳ |
| Jump practice: Aerowalk 16 out (`JUMP_SKIP=aerowalk:16`) | the owner: "nonsensical" | ⏳ |
| Rail streak pay removed (`RAIL_STREAK_PAY=0`) | the long-rail pay and the shot prices kept | – |
| Rail shot price | if he fires the rail too freely: rg 0.2 → 0.5 by the safe restart (approved in advance by the owner) | ❓ |

Unchanged from v0.3.8's end: shares 70 whole games / 20 pro starts / 10 advanced movement; hearing level B; item pay
0.30/0.30/0.15; the speed pay; the jump practice of 2026-10-21 (no starts inside walls, his own take-off counted from the take-off's
side, two-hop run-ups for fast jumps, the Aerowalk red armor's 2 s pro run-ups, Toxicity 7 out).

## 4. Checks

| When | Against | Aim |
|---|---|---|
| Update 10 (the new pays' gate) | v0.3.8's end | 4 |
| Every 20 from update 20 | v0.3.8's end and v0.3.1's end in turn | 4 |
| Update 100 | v0.3.8's end (the bridge to the old checks) | 3 |

## 5. Not in v0.3.9

| Item | Why | State |
|---|---|---|
| Jumps in and out of games by success (thresholds) | needs in-game per-jump counters | ⏸ |
| A mix of aim levels (3/4/5) | one change at a time beside pre-aiming; reminder after v0.3.9 | ⏸ |
| Toxicity 7 and Furious Heights 20 starts by hand | not built | ⏸ |
| The rocket-jump specialist (B-272) | after v0.3.9 | ⏸ |
| Holding an angle and waiting (B-273) | v0.4's strategy layer | ⏸ |
| v0.3.10 option A: watching the right opening (the owner, 2026-10-21: "if the enemy is hidden but is watching the right area that goes to him as pay"; shaped: credited back from the next sighting, the last 1-2 s of view on the spot where the enemy came out) | a denser lesson than the sighting pay; pays the opening, not the wall he is behind; most when contact is near | ⏸ v0.3.10 |
| v0.3.10 option B: keeping track of the enemy (the owner: predict the enemy's place and stack, scored by correctness over time; never shown to him as pay, he learns to keep a better record) | partly there: the guessing game (`--aux`) asks `place` and `near` at weight 0.2 but with `--aux-trunk 0`, so it does not shape his memory; `strength` (his stack) is not asked; `EN_STACK` is a hand-built belief. To try: `strength` added and the lesson let into the shared layers (`--aux-trunk`), with the 2026-10-12 caution (eight questions pulled ~5x as hard) | ⏸ v0.3.10 |

## Files

Run file `ql-bot-v039\scratch\run_duel_gru_v0_3_9.cmd` (from the scratchpad's `v039\mkrun_v039.py`); the watcher
`scratchpad\v039w\watch.py`; the pre-aim and effort measurements `scratchpad\preaim\REPORT.md`.

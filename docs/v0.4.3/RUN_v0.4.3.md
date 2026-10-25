# v0.4.3 on one page: the strategy head (DRAFT)

*2026-10-22: **proposed**, after v0.4.1 works (names, the owner, 2026-10-22 night: v0.4.0 the brain's pretraining, v0.4.1 the brain
connected, v0.4.2 "the blending out of the old belief network while inserting the brain network", with what was called v0.4.1
before: the strategy head). Before it: [RUN_v0.4.2.md](../v0.4.2/RUN_v0.4.2.md) (the old belief faded out) (numbers, the owner, 2026-10-23: "Can we just make these separate numbers: v0.4.2a -> v0.4.2; v0.4.2b -> v0.4.3"; what was v0.4.3 and on is v0.4.4 and on). Design: [BELIEF_LOOP.md](../v0.4.0/BELIEF_LOOP.md).*

*2026-10-23 evening: the old belief's fade is v0.4.2, [RUN_v0.4.2.md](../v0.4.2/RUN_v0.4.2.md) (built and tested on the CPU; start Sat on the owner's go). This card, the head, is v0.4.3: build Sat-Sun, start Sun afternoon if v0.4.2 passes. The goal of v0.4.x (owner, 2026-10-23): **pay by win chance** as the only game pay ("there is no tuning, you just pay for the win it figures out the rest"); the brain and the head are what make it possible; the shaping pays are scaffolds, recalibrated if badly off and then faded (below).*

**2026-10-25 13:30: RE-PLANNED (owner): weapon variety first, then the head, then pay by win chance.** He never takes
Campgrounds' rail (every version since v0.4.1) and leans on the rail on Hektik since v0.4.2 (RESULTS 2026-10-25 13:30, B-286);
the owner: "course correct now before adding more complications and further solidifying the behavior". The item rule's fade
is done (INTENT_TEACH_W 0 since 12:25, update 60). The head stays shut; update 70 is kept with its optimizer as the fallback before
it (`data/fallbacks/v043_u70_prehead`). The schedule below replaces the plan of 10-24 evening.

| When (approx.) | What | How |
|---|---|---|
| from u72-73 | the three big weapons pay alike | BIG_PICK_SEQ 0.10,0.10,0.10 (was 0.10,0.06,0.05), live; fades out in v0.4.4's cross-fade |
| 13:20 -> 16:00 | the pros' mid-game starts 22% -> 50% of the games' time | GAME_P / PRO_START_P live: 0.70/0.30, 14:15 0.60/0.40, 15:10 0.55/0.45, 16:00 0.50/0.50 (scratchpad v043w/ramp_starts.py; holds under 45%) |
| when ready (restart at a save if not live) | targeted practice runs to the items he never takes (Campgrounds' rail by its pad, Hektik's lightning, by measured pickups per map) | item runs 10% of the playing time beside the jump runs' 10%: the mix 40% whole games / 40% mid-game starts / 20% practice (branch `starts`) |
| every save | pickups and weapon held per map, in the simulator against v0.4.2's end | scratchpad v043w/weapon_watch.py (weapon_watch.jsonl) |
| tonight (owner's review) | the head opens overnight if Campgrounds' rail is clearly above 0 and the checks are 50% or better against v0.4.2's end; then practice back to 10%, whole games 50%, starts 40% | RAMP=head as planned; trains through Monday |
| tonight, if the rail has not moved | plan B (agreed): a temporary low-weight teacher for the neglected weapons only, faded | |
| Mon | the "will be" exemption, the level pull phased out | as before |
| Tue | v0.4.4: pay by win chance (with mid-game starts from people's games, moments before pickups) | the owner's go |

**2026-10-25 07:35: STARTED** (`duel_gru_v0_4_3`, code `v043b` 98c54b8, worktree `ql-bot-v043`; from v0.4.2b's end, update 140). Changed from the plan of 10-24 evening: v0.4.2 became v0.4.2b overnight (the brain taught on people's games: [../v0.4.2/BRAIN_HUMANS_v0.4.2b.md](../v0.4.2/BRAIN_HUMANS_v0.4.2b.md)), and its people's lesson stays on (share 0.35); the owner's order is the **item rule's fade first**, then the head (attached shut at the start, H2_GATE_CAP 0, its control slot on the brain + memory readout); v0.4.2c (pusher opponents) dropped by the owner. Guard as v0.4.2's (scratchpad v043w/live_ramp.py: RAMP=rule now, RAMP=head next). Checks against v0.4.2's end: u10 86-74 (53.8%), u30 76-84 (47.5%, frag share 49.8%). Running beside: the shadow win value, the "in control" readouts.

**2026-10-24 ~19:45: THE PLAN (owner: "Good, let's plan on that")**

1. **Tonight:** v0.4.2 restarted once at a save with the **"in control" shadow** in (no effect on play; the Aerowalk route copy
   left out: the owner, "I'm just nervous about including this type of thing overnight when I can't watch it"); it runs overnight.
2. **Sun morning, after the owner reads the 06:30 report:** v0.4.2 ends at a save (kept as `keep/policy_end_v042.pt` + optimizer)
   and **v0.4.3 starts** from it directly (one new thing: shut at the start, opened slowly, tied to the checks).
3. **Then the schedule below, through most of Monday.** Each step opens only after the one before is fully in and passing.

| When (approx.; a held step moves the rest later) | What opens | How |
|---|---|---|
| Sun ~08:00 | **v0.4.3 starts; the head** (shut) | the head's gate from update 1, capped at 0.1 for the first two checks (u10, u30), then +0.05 every 25 min on passing checks (live `H2_GATE_CAP`) |
| from the start, all the time | **two shadows** (no effect on play; proven bit-identical on and off) | the **"in control" readouts** (brain alone, brain + hands' memory) and the **shadow win value** (what pay by win chance would be worth; learns only, never paid: the critic v0.4.4's cross-fade starts from) |
| Sun ~09:00-14:00, beside the run (CPU) | **the 256/512 brain test** | can the brain learn "in control" as its own lesson at 256 without its other answers getting worse, or does it need 512? Decides how "in control" reaches the head (below) |
| Sun ~16:00 | the head fully in | two checks at full head |
| Sun ~17:45 | **the "will be" blind-fire exemption** | no out-of-view shot cost where the brain predicts the enemy will be in 1-4 s; a chance per life 0 -> 1 over ~2-3 h (live `BLIND_AHEAD_P`) |
| Sun 19:30 | play test | v0.4.3 with the head, the mind view |
| Sun ~21:00 -> overnight | **the item rule fades** | live `INTENT_TEACH_W` 1.0 -> 0 (its 10% floor included), -0.1 every 25 min on passing checks |
| Mon 06:30 | report | does the head choose items well without the rule |
| Mon ~07:00 -> ~16:00 | **the level pull ends** | live `LEVEL_PULL` 0.95 -> 0.98 -> 0.99 -> 0.995 -> 1.0, ~2 h a step |
| by the brain test | **"in control" into the head** | 256 fine: a brain lesson, opened on its own after the "will be" exemption, into the head's slot; 256 too small: with the brain widened to 512, a round of its own (v0.4.4 on) |

The guard on every step: a check under 50% holds; under 45% (frag share under 48.5%) or two checks under 50% rolls that step
back. Not in v0.4.3 (recommended, the owner's call): the pay clean-up (big-weapon order, shot price, watching / pre-aim to 0)
goes with v0.4.4's cross-fade. Code: branch `v043` (the head, the rules' switches, the "in control" readouts, the shadow win value,
the overtime fix; all shut = v0.4.2), worktree `ql-bot-v043`.

*2026-10-24 12:15 (owner): scope: the head (with the brain's outputs and the "in control" readout as its inputs); the "will be" blind-fire exemption **kept in**; then in the run, one after the other: the item rule's floor faded, the level pull phased out. Building today on the CPU in parallel (branches `v043-head`, `v043-control`, `v043-rules`); "in control" tested offline on v0.4.2's saves (a probe on his frozen state). Start Sunday from v0.4.2's end on the owner's go.*

The whole network as it will be: [ARCHITECTURE_v0.4.3.md](ARCHITECTURE_v0.4.3.md). The owner, 2026-10-24: "It's crucial we get 'in control' into the brain network"; it and pay by win chance are "going to be closely related".

**Marks:** ✅ built and tested · ⏳ building · 🧪 to measure · ❓ owner's decision · ⏸ later

## The two versions, each started and checked on its own (one change at a time)

| Step | What | Pass before the next |
|---|---|---|
| **v0.4.2: the old belief out** ([RUN_v0.4.2.md](../v0.4.2/RUN_v0.4.2.md)) | the cross-fade: the old rule-made inputs (the extrapolated belief, ~20, and the stack filter, 6) times (1 − g) as a gate g opens over hours; **the raw sensed facts stay** (where and when he last saw or heard the enemy: the owner, 2026-10-22, "yes that seems right to me"); the brain's new outputs from v0.4.1 (zones, where he will be in 1/2/4 s, what he is going for, when he appears, the item race) join the `belief` token once they pass their own readiness test; the old rule's readers inside the simulator (the legs' look point, the hunt's target) move to the brain | games ≥ level against v0.4.1's end; the decision report's reading rows moving |
| **v0.4.3: the strategy head** (this card) | below | the decision report's item rows moving |

## The strategy head

| Part | Detail | State |
|---|---|---|
| **The brain's new outputs, read by the head** (owner, 2026-10-23: "The hands handle what to do *now*, the predictions drive strategy") | where the enemy will be in 1/2/4 s, what he is going for, when he appears, the item race: inputs of the head, not the hands' token; each joins after its readiness bar | ❓ |
| **"In control" (B-280; the owner, 2026-10-23: "It's a very common way of talking about quake and would resonate well with anyone looking deeper into his structure")** | a brain readout 0..1: his share of the next two mega/red-armor spawns, labelled after the fact (who took them; like the brain's other readouts, learnt from the truth, read from his senses only, never a pay); read by the head; beside it, control from the value: his win chance beyond what the score and clock give. Shown in the decision report (does he fight when in control, back off when not) and as a timeline in play-test reports (the shadow win value is the value's side, above) | ✅ shadow readouts built; 🧪 the 256/512 test decides the way into the head |
| **The small slow head** | reads the brain (its memory and its answers), his own stack, item timers, score and clock, the hands' memory (no gradient); a GRU of 256 ticking every 0.2 s with the brain; acts by a plan (64) into the hands' memory and a bias on the intention head's choice, both starting at zero (an exact start, proven by a test) | ❓ |
| Size | ~0.6 M weights (v0.4's earlier candidate head: ~7 M); grows only on a measured need | – |
| On a server | well under 1 ms a tick; the head added to the plugins' forward pass | ❓ |
| The head's horizon | a goal choice pays off 30–60 s later: the head learns from the two-minute value output (γ 0.9998), not the main ~25 s one, or it undervalues timing plays | ❓ |
| The blind-fire exemption on "will be" (owner, 2026-10-23: "it probably should be 'will be'") | v0.4.2 waives the out-of-view shot cost where the brain believes the enemy *is*; v0.4.3 extends it to where the brain predicts he *will be* in 1–4 s (the ahead outputs), with its equilibrium stated: still a cost waived, never a pay | ✅ built; opens after the head (kept in: owner, 2026-10-24) |
| A start from the pros (only if needed) | the pros' next goal by situation (mega when the enemy is far, back off when weak) as a light prior on the head's bias, fading like the item rule; added only if the head is slow to find these by winning. The owner is wary of copying the pros' choices (HAND_TEACH): measure first | ⏸ |

## Rule-made strategy the head takes over (the owner, 2026-10-22: "Is there any other parts of him like this that might need revisiting?")

*Timing (the owner, 2026-10-22): "those should be included eventually, that's probably at least v0.4.1 probably later" (said when the head was called v0.4.1): with the head at the earliest, more likely a later v0.4.x once it has shown it chooses well.*

| Part | Now | With the head |
|---|---|---|
| The item rule (the intention teacher, never under 10%) | a hand rule nudges which item he goes for, forever | its floor faded to zero as the decision report shows the head choosing well |
| The hunt (`HUNT`) | a rule sends his way toward where he believes the enemy (reads the readout from v0.4.0) | whether to hunt is the head's choice |
| Item pays (pickups, the big-item order, item loss) | hand-shaped values of items whatever the situation | lowered step by step as the head learns their value from winning (the item-pay review of 2026-10-17 belongs here) |
| The view's pull toward level (B-275) | with no enemy in view his pitch eases back to level (0.95 a frame): a crutch of 2026-10-03 that stops him holding a look up or down out of sight | phased out regardless of the drift measure (owner, 2026-10-23: "I think it's done its part"; "Let's just plan to phase it out regardless"): measured (RESULTS 2026-10-23 15:30), then a live factor 0.95 -> 0.98 -> 0.99 -> 0.995 -> 1.0, about 2 h a step, the control checks as usual, the plugins in the same batch |
| Item timers (his own pickups) | rule-kept clocks: fair, a person keeps them too | kept; the enemy's side ("when is mega back after he took it") into the readout only if the report shows timing mistakes |

## What it should do

| Situation | The head's bias |
|---|---|
| Strong, the enemy weak and predicted near | toward "the enemy" as his target |
| Weak, the enemy strong | toward the items the enemy is not going for, away from his predicted path |
| The enemy going for mega, he is strong | contest it; weak: take the red armor across the map |
| An item about to spawn, the enemy far | be there on time |

## Targets: the decision report (the owner, 2026-10-22: "whatever we start doing in v0.4.x needs to target these findings")

| Row (v0.3.10's end against v0.3.9's end, 80 whole games, `data/decision/v0310_end.txt`) | Baseline |
|---|---|
| Presses in when far behind (gap < −75) / dies within 10 s | 36% / 61% |
| Presses in when far ahead (gap > 75) / the enemy dies within 10 s | 61% / 60% |
| Closing against the gap (slope, u/s per 100 points) | 30.9 (v0.3.9: 26.7) |
| Mega and red respawns: waiting / on time / late / **the enemy took it** / unused | 19 / 8 / 26 / **42** / 5% |
| ... when the enemy is weak (< 100) | 20 / 9 / 30 / 35 / 6% (hardly different) |
| Enemy within 600 u at his pickups: when he is weak / strong | 32% / 26% (he does not avoid contests when weak) |
| Lost contests a game | 4.2 |
| Deaths while weak (his stack < 100, the enemy's > 150) a game / share of his deaths | 4.4 / 38% |
| After losing sight: toward the enemy when ahead / away when behind | 40% / 42% |

What v0.4.3 must move (the head chooses):

| Row | Target |
|---|---|
| Mega and red respawns: waiting (19%; the pros 12%) | down toward the pros. **Not** "the enemy took it" (42%): the pros' is 42% too (`data/decision/pros.txt`, 2026-10-23: in a duel each takes about half) |
| Enemy near his pickups when he is weak (32%) | down: when weak, take the item the enemy is not going for |
| Lost contests (4.2 a game) | down |
| Presses in when far behind (36%; the pros 24%), deaths while weak (4.4 a game; the pros 3.3) | down toward the pros |
| After losing sight, the gap slope (17.3; the pros 21.2) | up toward the pros |
| Closing against the gap (30.9) | steeper: press when ahead, back off when behind |

v0.4.3 passes when these move toward the pros' (the same report on the pros' demos, to be filled in).

## Measure: the decision report

Fight or back off by the stack gap; items against the enemy's distance; timing; deaths while weak; where he goes after losing
sight; split by what he believes as well as by the truth. v0.4.3 passes when these move toward the pros' (`tools/decision_report.py`).

## Play tests aimed at it

The owner stays weak, or stacked, on purpose: does he press or back off; does he contest the item the owner goes for. The quick
human check of "he changes his intention by the enemy's state" that no single number holds.

## Growing the head (the owner, 2026-10-22: "slowly build out the size of the head to incorporate new pathologies that appear in practice")

Each pathology seen in play tests or the people review becomes a **measured row** in the decision report first; the head grows
(or gets a new intention) only to move that row, and the row says whether it worked.

## Toward pay by win chance (v0.4.4 on; the owner, 2026-10-23)

| Step | What | When |
|---|---|---|
| Measure (now, CPU; branch `winpay`) | his own win table beside the pros'; the pay ledger (each pay's share); each shaping pay's alignment with winning 30–120 s later; value readiness (does his value predict the result; does it rise at a mega by the mega's worth); a shadow win-chance counter | 2026-10-23 → |
| Recalibrate | a shaping pay far from its measured worth set to it (a bridge before its fade, not an end) | before its fade |
| Frag pay → win chance (`WIN_PAY`, built) | a cross-fade of the flat ±1 into the change of his win chance, check-tied; the head's long value rewired to include it | v0.4.4 |
| Scaffolds faded | one or two a version: items, the item rule's floor, speed/hop, watching/pre-aim, stack difference, damage last | v0.4.4 on |
| Stays | the fairness limits (aim, senses, his own item timers); movement practice's own pays (no score there) | – |

## Then (v0.4.4 and on, each on a measured need)

| Step | When |
|---|---|
| More intentions: contest, wait at an item, stack up, ambush the predicted opening (opened out of the choices they stand in for, never by a bias over all) | the head's bias cannot express the choice the report wants |
| A wider slow memory | the head's value or the report stalls |
| A store of the last minutes | he forgets the enemy's habits or item timings beyond a minute |
| Rail angles held on purpose (B-273) | through a holding place chosen by the head |

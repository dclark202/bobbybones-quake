# 2.2c: the brief for the monitoring session (an Opus 5.5 session; written 2026-11-18 by the build, for the planning session to hand over)

You monitor run **2.2c** (`data/sim_runs/duel_gru_2_2c`) until the owner stops it or its 100 updates end it, and report to the owner in your
chat. You monitor and report only. Read `CLAUDE.md` first (its hard rules bind you; "How we work" is how the owner wants a run described),
then the card, [CARD.md](CARD.md), whole. The build's record is [BUILD.md](BUILD.md).

## The first rule: say what is happening, in plain words

**Every report opens with one or two plain sentences a Quake player understands who has not read the card: what is actually playing
now, and whether the run is on the card's plan.** Then the numbers.

- **When something ends, skips or changes a stage, report what it means for the run**: what he is now playing, what the rest of the run
  can and cannot still show, and what the owner could decide. Keep that statement at the top of every report until he answers it.
- **No name of a part of the build without saying in the same sentence what it does.** Say "the contest pay (when the enemy picks up a
  big item, the shells and damage he put on it in the 4 seconds before move part of the item's pay to him)", "the aggression lever (one
  number the fight network adds to his score for going after the enemy)". Never a dial's code name alone.
- Numbers as records and plain quantities: "112-88 against the start", "31 of 80 enemy megas and armors taken under fire".
- A count of how often he re-decides is never a measure and is never flagged. A low hit rate is never a fault: shells at an item that
  hit nobody are what the contest pay is there to bring.

## What the run is (the card in short)

He starts from 2.2a's update 90 (2.2b's start; nothing of 2.2b's training). Two new things, together:

- **The contest pay**: when the enemy picks up a mega, a red or yellow armor, the rocket launcher, the rail or the lightning gun, the
  simulator looks back 4 seconds at what Bobby did to that pickup (his crosshair set on it with a weapon that reaches, his rockets,
  grenades and plasma bursting near the item or the enemy, damage he dealt), less the damage he took; that pressure (0 to 1) moves up to
  80% of the item's pay from the picker to him. A pickup with no pressure at all costs him 10% of the item's pay. While a big item is
  up and the enemy is nearer to it and within 6 s, Bobby's shells on it move pay from the enemy each second. Taking an item the enemy
  was about to take, after pressuring it, pays a steal. At most 80% of an item's pay moves per spawn; the picker always keeps 20%.
- **The rail chain**: a pay for picking up the rail (0.15, once a life), for having it out at a fresh sighting beyond 768 units (0.10),
  and the far-rail hit pay at 0.5 (2.2b: 0.1). A far hit now pays half a frag on top of its damage.
- **The aggression lever**: the fight network now gives ONE number, added to the item picker's own score for "the enemy". No fight
  options, no practice trips, no weapon nudge, nothing shut. It learns from every target decision he makes, with its own pay (damage
  dealt less taken, frags, deaths, the chance of winning).
- **Kept from 2.2b's restart**: each network paid for its own job; the item picker frozen (but its forecast) through update 10; its push
  on his weapon gone by update 10 (the hands choose the weapon alone); firing free; the near-miss pay at 2.2b's size; the gauntlet alarm
  and the weapon-speed alarm (the second now reads the hands' own figure).

| Updates | What plays | The point |
|---|---|---|
| 0 to 10 | The contest pay, the rail chain and the near-miss pay at full size from update 0. The lever at 0 (the trainer plays it at 0 on these updates by its own count). The item picker frozen (its forecast learns); its weapon push fades 1 → 0, played 0 by update 10 | The hands learn under the new pay; the forecasts learn the new pay |
| 10 | Check against the start | |
| 11 to 100 | The lever on (share 1); the item picker's choices taught again; the hands shown the lever (its attention gate written open over updates 8 to 17, so it plays over about 10 to 20). Nothing else changes | Does he contest the items and pick his fights |
| 30, 50, 70, 90 | Checks, 200 games, against the start; every fourth against 2.1d's end | |

**The one pass mark: checks level with the start or better.** Everything else is reported, never a pass mark. A check under 40% is a
major problem, said at once. Nothing holds or steps back on its own: **a bad number is yours to shout about**; nothing else will.

**As built (read [BUILD.md](BUILD.md)):** the minutes an update, the ledger of the pay at the start (each new pay's share of his pay), and
the start's own numbers for the contest pay (how many of the enemy's big pickups are under pressure at the start) are in BUILD.md: compare
with them.

## Never

Stop, restart, hold or change the run, its processes or its files (`live.json`, the ramp, any dial). Start any job on the PC while it
trains. Delete anything. Push. If the trainer **crashes**: CLAUDE.md rule 2's exception applies to the planning session, not to you;
report it to the owner at once with the traceback and the last save. If the ramp, the watcher or the logger dies, report it at once.

## What to watch (under `data/sim_runs/duel_gru_2_2c/`)

`metrics.jsonl` (a line an update; the block `fight` is this run's: `played` (the lever's share as played), `lever` (its size and its
average by his state), `play` (frags and damage a seat-minute, how often he is headed for the enemy), `contest`, `rail`, `pay_terms`,
`projectiles`, `lesson`, `flags`); `watch/watch.log` (**every FLAG and MAJOR line from update 1**: the ramp writes every number of the
fight block there in plain lines); `watch/*stderr.log`; `live_status.json`.

## What to report

1. **At once**: any MAJOR line, above all: **the gauntlet in his hand over 5% of the time**; **his weapon choice moving over three times
   its normal speed** (the hands' weapon-key KL over 0.0126; its normal 0.0042); a frozen part of the item picker that moved; **the lever
   played at a share other than 0 before update 11**; each check (200 games against the start, 2.2a's update 90; every fourth against
   2.1d's end): games won and lost, **one under 40% is a major problem, said with urgency**; a stall (no new line for 15 minutes); a non-
   finite count; a refused settings file; RAM free under 5 GB or commit over 95 GB; the card's held memory over 15 GB; the lever's size or
   the item picker's target scores over 40 (rule 13: a FLAG line); the win-chance pay smaller than either network's flat pay (a FLAG line).
2. **One line an hour**, after the plain-words opening: the update and the minutes an update; frags and damage a seat-minute; the enemy's
   big pickups and the share under pressure (and the average pressure), steals, free pickups and how far he was then; his shells within
   300 units of an item, in view and out of view, by weapon; the contest pay's and the rail chain's share of his pay; the rail in hand,
   rail shots and far hits a minute; from update 11, the lever's size and its average when he is ahead, level and behind on stack and
   after a frag, and how often he heads for the enemy in each; any FLAG since the last line.
3. **What would work against the run's aim, flagged when seen** (the card's red team): his own big pickups a minute falling (he gives up
   his items to shell the enemy's); the share of free pickups far from the item staying high (charged for what he cannot reach: the
   free-pickup charge is a live dial, `CEDE_W`, the owner's to set); shells near items rising while damage a minute falls (shelling for
   pay, not for the game); the rail in hand rising while frags and checks fall (standing far away with the rail; the far-rail pay is a
   live dial, `RAIL_FAR_PAY`); the lever staying at 0 (that is an answer: it has cost nothing); sitting on an item's place (say "camping
   on an item"; there is no spawn camping in duel).
4. **Through updates 11 to 30**: the lever opens and the item picker's choices are taught again at the same time: a fall in a check there
   cannot be laid on one of them; say so, do not guess a cause.
5. **At 06:30**: the night's report, in the same form.
6. **At the end**: the trainer's exit, the kept files (`keep/policy_u<N>.pt` at 10, 20, every 20, and `policy_end_22c.pt` with their
   optimizers), the last checks. End checks and a play-test server are owed, not yours to run.

## Mechanics

Pace yourself (a wake-up every 20 to 30 minutes, and at updates 10 and 11, at 06:30, at the end) without the owner prompting you; nothing
you schedule may open a console window. Updates are counted by the lines of `metrics.jsonl`. You may add a section "The run" to the card
and finish the run's row of `docs/RUNS.md` at the end, then `python tools/docs_check.py` and a commit with explicit `git add` of those two
files; no other edits, no push.

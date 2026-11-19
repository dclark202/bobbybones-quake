# 2.2d: the brief for the monitoring session (an Opus 5.5 session; written 2026-11-18 by the build, for the planning session to hand over)

You monitor run **2.2d** (`data/sim_runs/duel_gru_2_2d`) until its 80 updates end it, 08:00 on 11-19 comes, or the owner stops it, and report to
the owner in your chat. You monitor and report only. Read `CLAUDE.md` first (its hard rules bind you; "How we work" is how the owner wants a run
described), then the card, [CARD.md](CARD.md), whole. The build's record is [BUILD.md](BUILD.md).

## The first rule: say what is happening, in plain words

**Every report opens with one or two plain sentences a Quake player understands who has not read the card: what is actually playing
now, and whether the run is on the card's plan.** Then the numbers.

- **When something ends, skips or changes a stage, report what it means for the run**: what he is now playing, what the rest of the run
  can and cannot still show, and what the owner could decide. Keep that statement at the top of every report until he answers it.
- **No name of a part of the build without saying in the same sentence what it does.** Say "the aggression lever (one number the fight
  network adds to his score for going after the enemy)", "the rail pickup pay (0.15 when he takes the rail while holding none, once a
  life)". Never a dial's code name alone.
- Numbers as records and plain quantities: "112-88 against the start", "31 of 80 enemy megas and armors taken under fire".
- A count of how often he re-decides is never a measure and is never flagged. A low hit rate is never a fault.

## What the run is (the card in short)

He starts from 2.2a's update 90 (the same start as 2.2b and 2.2c; nothing of their training). It is 2.2c with three pays taken out:

- **Out (owner, 11-18)**: the contest pay (pay moved between the players at the enemy's pickups by the pressure Bobby put on them), the
  pay at a long sighting with the rail in hand, and the near-miss pay (pay for a rocket or grenade that burst near the enemy and hurt
  nobody). **Each is exactly zero.** The contest pay's and the near miss's counters still run: they are measurements now, nobody is paid
  by them.
- **Kept**: the aggression lever (one number the fight network adds to the item picker's score for "the enemy"; 0 through update 10,
  on from 11; the hands shown it over 10 to 20); each network paid for its own job (the item picker: items and the chance of winning; the
  fight network: damage dealt less taken, frags, deaths, the chance of winning); the rail pickup pay (0.15, once a life, when he takes
  the rail while not holding one); the far-rail pay (0.5 for a rail hit from 500 to 800 units and beyond); the hands' inputs of 2.2c;
  the weapon choice the hands' own (the item picker's push on it gone by update 10); the item picker frozen but its forecast through
  update 10; firing free.
- **New, logging only**: two lines in `watch/watch.log` every update (below), and the weapon-choice-speed alarm reading every update
  (in 2.2c it could not from update 21: the figure was measured every 10th update only; fixed in the command).

| Updates | What plays | The point |
|---|---|---|
| 0 to 10 | Identical to 2.2a's update 90 at the start. The rail pickup pay and the far-rail pay at full size. The lever at 0. The item picker frozen (its forecast learns); its weapon push fades 1 to 0, played 0 by update 10 | The hands; the forecasts |
| 10 | Check against the start. **This answers the card's open question**: 2.2c's fall to 77-123 at update 10 came from the contest pay or the rail pays; if 2.2d falls the same way, it was the rail pays | |
| 11 to the end | The lever on in full; the item picker learns; the hands shown the lever (its gate written open over clocks 8 to 17, played over about 10 to 20) | Everything |
| 30, 50, 60, 70 | Checks, 200 games, against the start; **at 60 also against 2.1d's end** (the long-term control). Update 60's save is to be the default going forward if the checks hold | |
| 80, or 08:00 | The trainer stops after a save; the end kept with its optimizer (`keep/policy_end_22d.pt`, `opt_end_22d.pt`) and checked against the start | |

Saves kept with their optimizers at 10, 20, 40, 60, 80 and the end.

**The checks queue** (`tools/run/watch.py`, CHECK_AT): one check at a time, none skipped. A check takes about 65 minutes, about ten
updates, so from 50 on they fall behind the run: the update-60 check against the start plays from about update 60 to 70, the one against
2.1d's end from about 70 to 80, the update-70 check after that, and the end's last (after the trainer has stopped, near 08:00 or after).
Report each as it comes, with its update number; say plainly when the run has ended and checks are still playing.

**The one pass mark: checks level with the start or better.** Everything else is reported, never a pass mark. A check under 40% is a
major problem, said at once. Nothing holds or steps back on its own: **a bad number is yours to shout about**; nothing else will.

## Never

Stop, restart, hold or change the run, its processes or its files (`live.json`, the ramp, any dial). Start any job on the PC while it
trains. Delete anything. Push. If the trainer **crashes**: CLAUDE.md rule 2's exception applies to the planning session, not to you;
report it to the owner at once with the traceback and the last save. If the ramp, the watcher or the logger dies, report it at once.

## What to watch (under `data/sim_runs/duel_gru_2_2d/`)

`metrics.jsonl` (a line an update; the block `fight` is this run's: `played` (the lever's share as played), `lever` (its size and its
average by his state), `play` (frags and damage a seat-minute, how often he is headed for the enemy), `contest` (counters only),
`rail`, `pay_terms`, `projectiles`, `rail_would`, `free_see`, `lesson`, `flags`); `kl_heads` (the weapon alarm's figure: index 6);
`watch/watch.log` (**every FLAG and MAJOR line from update 1**: the ramp writes every number of the fight block there in plain lines);
`watch/*stderr.log`; `live_status.json`.

The two new lines, every update:
- **"what a rail would have dealt against what he dealt"**: from each moment the enemy comes into his sight, a 1.5 s window (the rail's
  reload): one possible rail hit of 80 if his crosshair crossed the enemy's body with a clear line at any frame of it, against the damage
  he actually dealt in it with whatever he held; by the distance at the window's start (under 500, 500 to 768, 768 to 1,200, over 1,200
  units) and whether he owned the rail then. It is a measurement that assumes he would aim the same with the rail in hand, never a pay or
  a target. Read: in the far bands, is the possible rail damage well above what he deals, and does it change when he owns the rail.
- **"at the enemy's free big pickups his line to the item"**: at each mega or armor the enemy took with no pressure from him, whether he
  had a clear line from his eye to the item, and how far he was (dead seats counted apart). Read: are free pickups ones he could see.

## What to report

1. **At once**: any MAJOR line, above all: **a dropped pay that paid anything** ("A DROPPED PAY PAID SOMETHING": the contest pay, the
   long line or the near miss not exactly 0); **the gauntlet in his hand over 5% of the time**; **his weapon choice moving over three
   times its normal speed** (the hands' weapon-key KL over 0.0126; its normal 0.0042); **the weapon alarm without its figure** ("no
   kl_heads": the fix failed); a frozen part of the item picker that moved; **the lever played at a share other than 0 before update 11**;
   each check (200 games; at 10, 30, 50, 60, 70 and the end against the start, at 60 also against 2.1d's end): games won and lost, **one
   under 40% is a major problem, said with urgency**; a stall (no new line for 15 minutes); a non-finite count; a refused settings file;
   RAM free under 5 GB or commit over 95 GB; the card's held memory over 15 GB; the lever's size or the item picker's target scores over
   40 (rule 13: a FLAG line); the win-chance pay smaller than either network's flat pay (a FLAG line).
2. **One line an hour**, after the plain-words opening: the update and the minutes an update; frags and damage a seat-minute; the rail in
   hand, rail shots and far hits a minute, the rail pickup pays; the rail line by distance (possible rail damage against damage dealt, the
   rail owned or not); the enemy's free big pickups he had a line to; the contest counters (the enemy's big pickups and the share under
   pressure: a measurement now); from update 11, the lever's size and its average when he is ahead, level and behind on stack and after a
   frag, and how often he heads for the enemy in each; any FLAG since the last line.
3. **What would work against the run's aim, flagged when seen** (the card's red team): **a fall at the update-10 check like 2.2c's**
   (77-123): with the contest pay out, that points at the rail pays (both live dials: `RAIL_PICK_PAY`, `RAIL_FAR_PAY`, the owner's to set);
   the rail in hand rising while frags and checks fall (standing far away with the rail); the lever staying at 0 (that is an answer: it
   has cost nothing); sitting on an item's place (say "camping on an item"; there is no spawn camping in duel).
4. **Through updates 11 to 30**: the lever opens and the item picker's choices are taught again at the same time: a fall in a check there
   cannot be laid on one of them; say so, do not guess a cause.
5. **At 06:30**: the night's report, in the same form, with update 60's checks if they have come (the default save going forward).
6. **At the end**: the trainer's exit (80 updates or the 08:00 time cap), the kept files (`keep/policy_u<N>.pt` at 10, 20, 40, 60, 80 and
   `policy_end_22d.pt` with their optimizers), the checks still playing in the queue and when they should land.

## Mechanics

Pace yourself (a wake-up every 20 to 30 minutes, and at updates 10 and 11, at 06:30, at the end) without the owner prompting you; nothing
you schedule may open a console window. Updates are counted by the lines of `metrics.jsonl`. You may add a section "The run" to the card
and finish the run's row of `docs/RUNS.md` at the end, then `python tools/docs_check.py` and a commit with explicit `git add` of those two
files; no other edits, no push.

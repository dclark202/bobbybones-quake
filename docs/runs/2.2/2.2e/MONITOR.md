# 2.2e: the brief for the monitoring session (an Opus 5.5 session; written 2026-11-19 by the build, for the planning session to hand over)

You monitor run **2.2e** (`data/sim_runs/duel_gru_2_2e`) from update 1 until it stops at 08:00 on 11-20 (or the owner stops it), and report to
the owner in your chat. You monitor and report only. Read `CLAUDE.md` first (its hard rules bind you; "How we work" is how the owner wants a run
described; **never edit CLAUDE.md**), then the card, [CARD.md](CARD.md), whole. The build's record is [BUILD.md](BUILD.md).

## The first rule: say what is happening, in plain words

**Every report opens with one or two plain sentences a Quake player understands who has not read the card: what is actually playing
now, and whether the run is on the card's plan.** Then the numbers.

- **When something ends, skips or changes a stage, report what it means for the run**: what he is now playing, what the rest of the run
  can and cannot still show, and what the owner could decide. Keep that statement at the top of every report until he answers it.
- **No name of a part of the build without saying in the same sentence what it does.** Say "the rail drill (30-second stretches on a long
  sight line of a duel map, the rail his only weapon, a scripted target that runs and jumps and never fires; he is paid only for rails that
  land)", "the aggression lever (one number the fight network adds to his score for going after the enemy)". Never a dial's code name alone.
- Numbers as records and plain quantities: "112-88 against the start", "a rail hit rate of 21% at 750 to 1,000 units in the drill".
- A count of how often he re-decides is never a measure and is never flagged. A low hit rate is never a fault.

## What the run is (the card in short)

He starts from 2.2a's update 90 (the file 2.2b, 2.2c and 2.2d started from; nothing of their training). It is 2.2d with:

- **Aim4 for every seat** (him, his league, both seats of every check): the aim settings of aim3's "better" level (a 100 ms reaction delay,
  175 ms to pick up a new target, smaller sight and hand errors, no flinch) with the sight error in proportion to how big the enemy looks.
  The checks play both seats at aim4 (the start too), so a check compares two networks under the same aim.
- **The rail pickup pay out** (2.2d paid 0.15 when he took the rail while holding none; now exactly 0, a MAJOR line if it pays).
- **The far-rail pay 0.2** (2.2d 0.5): paid for a rail hit from 500 units, in full from 800.
- **The rail drill, new**: 10% of the playing time from update 0 to update 40, then fading evenly to none by update 60 (written by the ramp; a
  written value plays one or two updates later). In a drill he stands on a long sight line of the map he is on (500 to 1,500 units from the
  target; three placements of 10 seconds each), holds only the rail (no machine gun, no gauntlet, no other weapon, ammunition that never runs
  out, no items), and the target is a script that runs across his line, changes direction at random (every 0.3 to 1.2 s in half the
  stretches, 0.15 to 0.5 s in the other half), jumps at random, never fires, and gets its health back after every hit. **He is paid only
  for a rail that lands** (the hands' damage pay, 0.4 for the 80 points, and the far-rail pay); every other pay term on his drill frames is
  exactly 0 (a MAJOR line if not). **Only the hands learn from drill frames**: the item picker, the fight network (the lever), the brain's
  forecasts and the hands' own forecasts take nothing from them (proven in the build), and the hands are told it is a drill by a learned
  vector of their own (its size is in the drill line). Checks never play a drill.
- **Kept from 2.2d**: the lever (0 through update 10, on from 11; the hands shown it over 10 to 20), each network paid for its own job, the
  win-chance judge with the items (re-measured under aim4: both win scales still 1), the item picker frozen through update 10 and its push on
  his weapon gone by then, firing free, the contest pay, the long line and the near miss at 0 (their counters run).

| Updates | What plays | What learns |
|---|---|---|
| 0 | 2.2a's update 90 under aim4 (with aim3's values it is 2.2a's update 90 to the bit: proven) | |
| 0 to 10 | The drill at 10%. The lever at 0. The item picker frozen; its weapon push going out. Far rail 0.2 | The hands; the forecasts |
| 11 to 40 | The lever on; the item picker learns; the drill at 10% | Everything |
| 41 to 60 | The drill fading to none (written 0.10 at 40, 0.05 at 50, 0 at 60) | Everything |
| 61 to the end | Whole games only | Everything |
| 08:00 on 11-20 | The trainer stops at the first update's end after its minutes, after its save; the end kept with its optimizer (`keep/policy_end_22e.pt`, `opt_end_22e.pt`) | |

Saves kept with their optimizers every 10 updates and at the end.

**The checks** (`tools/run/watch.py`, in a queue, one at a time, none skipped): 200 games against the start (2.2a's update 90) at updates 10,
20, 30, then every 10, and the end; at 60 also against 2.1d's end (the long-term control). Both seats at aim4. A check takes about an hour,
about as long as ten updates, so the queue keeps roughly level with the run until the extra check at 60, then runs about a check behind; the
end check plays after the trainer has stopped. Report each as it comes, with its update number.

**Two alarms on every check** (FLAG lines in `watch/watch.log`, from the watcher; also shown by the ramp beside the check): his red armor share
5 points or more under the start's in that check (2.2d's losing checks had 33 to 38% against the start's 39 to 43%); his time holding an empty
weapon over 1.5%.

**The one pass mark: checks level with the start or better.** Everything else is reported, never a pass mark. **A check under 40% is a
major problem, flagged at once.** Nothing holds or steps back on its own: a bad number is yours to shout about; nothing else will.

## Never

Stop, restart, hold or change the run, its processes or its files (`live.json`, the ramp, any dial). Start any job on the PC while it
trains. Delete anything. Push. Edit `CLAUDE.md`. If the trainer **crashes**: CLAUDE.md rule 2's exception applies to the planning session,
not to you; report it to the owner at once with the traceback and the last save. If the ramp, the watcher or the logger dies, report it at once.

## What to watch (under `data/sim_runs/duel_gru_2_2e/`)

`metrics.jsonl` (a line an update; `rdrill` is the drill's block, `rail` the rail in games, `fight` the lever's and 2.2d's lines); `kl_heads`
(the weapon alarm's figure: index 6); `watch/watch.log` (**every FLAG and MAJOR line from update 1**: the ramp writes every number in plain
lines there); `watch/*stderr.log`; `live_status.json`.

The two new lines, every update:
- **"rail drill"**: the share written; the share of his learner frames that were drills (expect about 0.10 to update 40, then falling); his
  minutes in drills; his rail shots in the drill, the hit rate, and the share fired with the crosshair off the target's body on the frame
  before (fired in the swing); the same by the true distance at the shot (under 500, 500-750, 750-1,000, 1,000-1,250, 1,250 and more);
  the placements by line band; the pay on his drill frames (the damage pay and the far-rail pay, and every other term's size, which must be 0);
  the drill vector's size and gradient. Read: does the drill's far hit rate rise over updates 1 to 40.
- **"rail in games"**: the rail's share of his time alive in games (by the enemy's distance), rail shots a seat-minute, the hit rate under
  500 / 500-800 / beyond. Read: does what the drill teaches show in games (hit rate at range, the rail held), or not.

## What to report

1. **At once**: any MAJOR line, above all: **the drill paid a term other than the rail's damage and the far rail**; **a dropped pay that
   paid anything** (the contest pay, the long line, the near miss, the rail pickup); **the gauntlet in his hand over 5%**; **his weapon choice
   moving over three times its normal speed**; a frozen part of the item picker that moved; **the lever played at a share other than 0 before
   update 11**; no drill record while its share is above 0; each check: games won and lost, **one under 40% is a major problem, said with
   urgency**, and **each of the two alarms** (red armor, empty weapon) when it fires; a stall (no new line for 15 minutes); a non-finite count;
   a refused settings file; RAM free under 5 GB; the card's held memory over 15 GB; the lever's size or the item picker's target scores over
   40 (rule 13); the win-chance pay smaller than either network's flat pay.
2. **One line an hour**, after the plain-words opening: the update and the minutes an update; frags and damage a seat-minute; the drill
   (share played, hit rate by distance, off-body share); the rail in games (in hand, shots a minute, hit rate by distance); the far-rail pay
   got; the red armor share in the last check; from update 11, the lever's size and its average when he is ahead, level and behind; any FLAG
   since the last line.
3. **What would work against the run's aim, flagged when seen** (the card's red team): the drill's hit rate rising while the rail in games
   does not move (he learns the script, not the rail at range); the rail in hand rising while frags and checks fall (standing far with the
   rail); **a fall at the checks from update 10 to 30 with the red armor alarm**: 2.2d's fall began when the item picker started to learn;
   if 2.2e falls the same way without the rail pickup pay, it was not that pay; say so, do not guess further; sitting on an item's place
   (say "camping on an item"; there is no spawn camping in duel).
4. **Through updates 11 to 30**: the lever opens and the item picker learns at the same time while the drill runs: a fall there cannot be laid
   on one of them; say so.
5. **At 06:30**: the night's report, in the same form, with every check so far.
6. **At the end (08:00)**: the trainer's exit line and its last update; the kept files (`keep/policy_u<N>.pt` every 10 and `policy_end_22e.pt`
   with their optimizers); the end check in the queue and when it should land; then **the aim room on the end save** (below).

## After the end: the aim room on the end save

Only after the trainer has stopped (no job while it trains). As the build measured the start (BUILD.md, "Aim room"): 2.2e's end save under
the aim4 default, the strafing target, Campgrounds, 8 matches x 5 minutes a condition, the rail from 500 and 1,000 units, the lightning gun
from 400 and 200, rockets from 400:

    python tools/run/aim_room.py play --tag end22e --add --target strafe --games 8 --minutes 5 --maps campgrounds --aim aim4 --policy data/sim_runs/duel_gru_2_2e/keep/policy_end_22e.pt --weapon rg --dist 500,1000 --jobs 6 --seed 95000
    python tools/run/aim_room.py play --tag end22e --add --target strafe --games 8 --minutes 5 --maps campgrounds --aim aim4 --policy data/sim_runs/duel_gru_2_2e/keep/policy_end_22e.pt --weapon lg --dist 200,400 --jobs 6 --seed 96000
    python tools/run/aim_room.py play --tag end22e --add --target strafe --games 8 --minutes 5 --maps campgrounds --aim aim4 --policy data/sim_runs/duel_gru_2_2e/keep/policy_end_22e.pt --weapon rl --dist 400 --jobs 3 --seed 97000
    python tools/run/aim_room.py report --tag end22e

(run hidden; each about 5 minutes). Report the hit rates beside the start's (BUILD.md's table) and **flag to the owner the lightning gun over
53% at about 300 units** (the start from 400 lands at about 300; the owner ruled out a lightning gun at 54 to 59%).

## Mechanics

Pace yourself (a wake-up every 20 to 30 minutes, and at updates 10, 11, 40, 60, at 06:30, at the end) without the owner prompting you; nothing
you schedule may open a console window. Updates are counted by the lines of `metrics.jsonl`. You may add a section "The run" to the card and
finish the run's row of `docs/RUNS.md` at the end, then `python tools/docs_check.py` and a commit with explicit `git add` of those two files;
no other edits, no push.

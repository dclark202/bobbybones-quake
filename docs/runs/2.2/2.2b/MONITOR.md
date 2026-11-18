# 2.2b: the brief for the monitoring session (an Opus 5.5 session; written 2026-11-17 by the planning session)

You monitor run **2.2b** (`data/sim_runs/duel_gru_2_2b`) until the owner stops it or its 24-hour limit ends it, and report to the owner
in your chat. You monitor and report only. Read `CLAUDE.md` first (its hard rules bind you; rule 17 is how the owner wants a run
described), then the card, [CARD.md](CARD.md), whole. The build's record is [BUILD.md](BUILD.md).

## The first rule: say what is happening, in plain words

**Every report opens with one or two plain sentences a Quake player understands who has not read the card: what is actually playing
now, and whether the run is on the card's plan.** Then the numbers.

- The owner lost eight hours of 2.2a because the one decision the run was for (a part kept switched off at update 60) reached him as a
  line of numbers. **When something ends, skips or changes a stage, report what it means for the run**: which stages are not
  happening, what he is now playing, what the rest of the run can and cannot still show, and what the owner could decide. Keep that
  statement at the top of every report until he answers it.
- **No name of a part of the build without saying in the same sentence what it does.** Say "the four fight options (go at him, cut
  him off, hold an angle, back off)", "the network that scores them", "the share of his decisions at which they are in his list".
  Never a dial's code name alone.
- Numbers as records and plain quantities: "112-88 against the start", "he reached the place on 6 of 10 practice trips", "off by 22
  armor points". Not skill scores.
- A count of how often he re-decides or changes his mind is never a measure and is never flagged. A low hit rate with projectiles is
  not a fault: low-odds shots are what the near-miss pay is there to bring back.

## What the run is (the card in short)

He starts from 2.2a's update 90. A new network scores four fight options; the item picker scores the items; both sit in one list and
he heads for the highest. The schedule:

| Updates | What plays | The point |
|---|---|---|
| 0 to 10 (the restart) | The item picker is frozen except the last layer of its forecast (the trainer proves it every update: a plain line in `watch/watch.log`, MAJOR if a frozen weight moved); its push on his weapon fades 1 → 0 and stays 0 for the run; its weapon scores never learn | His weapon is the hands' alone from update 10 until the fight network's nudge opens at 60 |
| 0 to 20 | His choices as before. Practice trips (he is sent on a fight option with a random weapon) rise to 12 in 100 decisions; half dealt at random, half picked by the new network. The small pay for a projectile that bursts near the enemy opens. The hands start to be told where he is headed | The hands begin to practise |
| 20 to 60 | The same, held | Do the hands carry the fight options out |
| **60** | **The ramp writes a plain-words line** in `watch/watch.log`: whether the hands carry each option out, how much practice each has had | **The run's first decision point. Report it at once and in full, as its meaning** |
| 60 to 100 | The fight options enter his own list (their share 0 → 1). "The enemy" and "the places" leave the item picker; the fight network's weapon nudge opens (the item picker's weapon push left by update 10: the restart). Practice 5 in 100 | Does he use them himself |
| 100 on | The full structure | Checks; the owner's play test |

Nothing in this run holds or steps back on its own: the stages open on the clock whatever the numbers say. **So a bad number is yours
to shout about**; nothing else will.

**As built (read [BUILD.md](BUILD.md)'s first section):** an update takes about 6 minutes, so update 60 comes about 6 hours in and update
100 about 10 hours in. Practice trips are about 7.6 in 100 decisions; of the trips dealt, back off is about 42% and the other three
about 19% each (if back off climbs well above that, say so: he is being sent running away too often). The one FLAG about the pay's
size now fires when the win-chance part is **smaller** than a decider's flat pay; it should not fire. The start carried 2.2a's
update-100 optimizer.

**The restart (11-17 evening; the card's "The restart").** The first start failed (the gauntlet in hand a third of the time from update 12,
0-200 at update 10); its folder is `duel_gru_2_2b_failed_1117`. The run you monitor keeps the name 2.2b and the folder
`data/sim_runs/duel_gru_2_2b`. As built for the restart: the item picker frozen but for its forecast's last layer through update 10
(`metrics.jsonl` block `h2_freeze`: `held_max` must be exactly 0 through update 10, and `weapon_max` exactly 0 for the whole run; the ramp's
line "the item picker FROZEN ..." every update); its weapon push `H2_WADD` 1 → 0 over updates 0 to 10 as the ramp writes it (the value
actually played lags the written one by about 2 to 3 updates, so 0 first plays at about update 12 or 13: read `fight.played.h2_wadd`).

## Never

Stop, restart, hold or change the run, its processes or its files (`live.json`, the ramp, any dial). Start any job on the PC while it
trains. Delete anything. Push. If the trainer **crashes**: CLAUDE.md rule 2's exception applies to the planning session, not to you;
report it to the owner at once with the traceback and the last save. If the ramp, the watcher or the logger dies, report it at once.

## What to watch (under `data/sim_runs/duel_gru_2_2b/`)

`metrics.jsonl` (a line an update; the block `fight` is this run's: practice trips by option and how they ended, damage on them, the
share of his decisions each destination wins, how often each network's side wins the list, forecast errors, the win-chance scale,
sizes, near misses, projectiles fired, parts off, non-finite counts); `watch/watch.log` (**every FLAG and MAJOR line from update 1**);
`watch/*stderr.log`; `live_status.json`.

## What to report

1. **At once**: any MAJOR line, above all the restart's two alarms: **the gauntlet in his hand over 5% of the time** (`v14.in_hand.g`
   over 0.05) and **his weapon choice moving over three times its normal speed** (`weapon.kl` over 0.045), and a frozen part of the item
   picker that moved; each check (every 20 updates, 200 games against the start, 2.2a's update 90; every fourth against
   2.1d's end): games won and lost, **one under 40% is a major problem, said with urgency**; a stall (no new line for 15 minutes); a
   part turned off, a non-finite count, a refused settings file; RAM free under 5 GB or commit over 95 GB; the card's held memory
   over 15 GB; any size over 40; the win-chance scale under 1 for either network.
2. **One line an hour**, after the plain-words opening: the update and the minutes an update; frags and damage a minute; projectiles
   fired a minute in view and out of view, with hits and near misses; practice trips per option and how many reached the place or met
   the enemy; from update 60, how often he heads for each fight option himself and how often each network's side wins the list; any
   FLAG since the last line.
3. **At update 60, in full and as its meaning**: for each of the four options, do the hands carry it out (reached the place or met
   the enemy on at least half of the practice trips; damage dealt for damage taken no worse than on his own choices), and how much
   practice it has had. If an option fails, say what that means: it enters his list from update 60 anyway and will likely be learnt
   away as in 1.7a; the owner can lengthen practice or stop.
4. **Through updates 60 to 100**: whether a fall in a check can be told apart (it cannot: the fight options, the options shut in the
   item picker and the weapon hand-over open together; say so, do not guess a cause).
5. **Damage a minute against projectiles a minute**: if projectiles rise and damage a minute falls, he may be aiming beside the
   enemy for the near-miss pay: flag it.
6. **Camping**: if he stands at an angle for long stretches with nobody coming, or sits on an item's place, flag it (there is no such
   thing as spawn camping; do not use the phrase).
7. **At 06:30**: the night's report, in the same form.
8. **At the end**: the trainer's exit, the kept files, the last checks. End checks and a play-test server are owed, not yours to run.

## Mechanics

Pace yourself (a wake-up every 20 to 30 minutes, and at update 60, at update 100, at 06:30, at the end) without the owner prompting
you; nothing you schedule may open a console window. Updates are counted by the lines of `metrics.jsonl`. You may add a section "The
run" to the card and finish the run's row of `docs/RUNS.md` at the end, then `python tools/docs_check.py` and a commit with explicit
`git add` of those two files; no other edits, no push.

# 2.1b, step A: morning report (11-15, 06:05)

## What happened

The run trained 9 updates (20:28 to 21:21) and then crashed. It has not trained since.

- **The cause** was a bug in the build. On update 10 the trainer drew an old league network (2.0e's end and older) as the opponent for the first time. Those files have no quiet layer, and the trainer refused to load them.
- **The fix** (commit `ce70fc3`): such a file now gets the quiet layer at zero and plays the lock in quiet moments, as the design said. A short test drew an old network in every round from update 2 to update 6 with no error.
- **The restart is waiting for your go.** It would rename the dead folder to `duel_gru_2_1b_crash1` (nothing deleted) and start again from 2.0e's end with the same settings.

**So there is no step A to judge yet.** These are the 9 updates' first signs.

## The first signs (9 updates)

- **Speed:** about 5.5 minutes an update, with the copied moments included. 80 updates take about 7.5 hours, and 60 updates take about 5.5 hours.
- **The copied moments:** about 220 a minute-long update, almost all in fights (1,586) or quiet (390); arrivals are rare (4).
- **Wasted copies:** in 61% of fight moments and 67% of quiet moments, the "new pick" drew the same target he already held, so those copies taught nothing.
- **The stay-or-switch judge:** it picked the better side 47–58% of the time on moments it hadn't trained on, around 50% on average. That is no skill yet, which is expected this early.
- **The size of the signal:**
  - Over all moments, keeping and switching come out almost the same on average, and a single moment varies hugely.
  - To tell the average apart from zero would take about 10,000 copied moments in fights, about 45 updates.
  - The judge can still learn which *situations* favour keeping before that. One early hint: in fights where he has held his target 5–8 seconds, keeping did better (31 moments, not yet reliable).
- **The keep choice's own lesson:** it sits at 50/50, as it should while the judge knows nothing.
- **Damage taken at 0.9:** too early to read. No check was played, since the first is at update 10.
- **Map sense:** learning; no reading worth giving yet.
- **Warnings raised:**
  - A low frag rate at updates 1–2, the same start-up dip as 2.0e.
  - "Win part over 0.6 of the pay" at update 1.
  - The judge's "no skill" warning every update.
  - Quiet re-decisions up a little at update 8. The lock decides everything there, so this is ordinary variation.

## Verdict

**B cannot open this morning: step A never ran.**

From the signal size above, the judge needs about 45–80 updates of copied moments before it can be trusted, so update 80 is a sensible point to judge it. Going by what you described yesterday, B and C each still get 60 updates:

- **Restart at about 07:00:** update 80 comes at about 14:30, B at about 20:00, C at about 01:30 Monday. The noon and 7pm play tests move to the evening and to Monday.
- **To keep a play test today:** judge A earlier, at about update 50 (about 11:45). That is risky, because the judge may not have skill by then.

Before restarting I'll also want your go on the change below.

**Suggested small change:** draw the "new pick" only among targets other than the held one. Today 61–67% of copies are wasted because the new pick is his current target, so this would roughly double the useful moments an update. The design chose to draw from his own scores (decision 3 in [BUILD.md](BUILD.md)), so this is your call.

## Needs your go

1. **The restart**, now that the crash is fixed.
2. **Whether to exclude the held target from the new pick** (see the suggested change above).
3. **The game-server image rebuild and a local server check** before B's play test: cores 14–17 at idle, about 20–30 minutes. Bobby with the new keep choice has never run on a real server.

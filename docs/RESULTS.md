# BobbyBones: results log (index)

What we tried, what we measured, and what it means, **including what did not work**. Newest first. Each
entry names the backlog items it settles or raises ([BACKLOG.md](BACKLOG.md), `B-nn`); the plan is in
[PLAN.md](PLAN.md); log formats are in [LOGS.md](guides/LOGS.md). Numbers are from local runs; raw data lives in
the git-ignored `data/` folder (paths given so results can be re-checked).

The log itself is one file a day in [results/](results/): each entry there is a dated section, newest first. This
page lists every entry. A new entry goes at the top of today's file and gets a line here.

## [2026-10-16](results/2026-10-16.md)

- 08:45 — Rocket jump runs built (B-252), all off by default; a scripted player clears 104 of the 174 pros' links in the corrected simulator (75% of the pros' rocket jumps); off = v0.3.1's simulator by fixed runs
- 06:30 — v0.3.1's night: from level to 60% against v0.3's end (110 games to 45), no collapse; he wins the fights he gets, he does not seek more
- 01:25 — Quake Live's movement measured case by case (B-258): four differences from the simulator found and fixed behind switches (all off); with them every measured case is within 5%. Bobby has never auto-hopped on the servers

## [2026-10-15](results/2026-10-15.md)

- 21:25 — The rocket jump check (B-252): as of v0.3 the simulator's rocket jumps are wrong (the blast comes 3 frames late, damage is off by up to 10, jumps are 60 units too low); two switches, both off by default, bring it within 5% and 1 point
- 21:40 — B-253 stage (b) built: his legs branch can learn from games (`--legs-learn`), off = stage (a) exactly
- 21:15 — v0.3.1's belief of the enemy's stack (B-257) and the hunt (B-256) built behind switches, off = today's simulator; the belief's error is a quarter of a fixed guess's
- 20:53 — v0.3.1 started: v0.3 resumed from its 18:00 stop with the owner's pay table and the faster learning step
- 16:50 — How soon the pros fire the rail after an enemy appears: Bobby is not slower at first, he fires less often later (B-255)
- 12:45 — The pros' rocket jumps found in 5,039 demos: on every map, 1 to 11 a game, with the links they repeat (B-252)
- 06:15 — v0.3's night: from level to 57.5% against v0.2 at update 70, then two falls to 52.1%; no stall, no weapon collapse

## [2026-10-14](results/2026-10-14.md)

- 22:30 — The architecture for the model after v0.3 proposed, Pluto's way: a store of his past read by attention, a judge of the game's result, the pay leaning on winning, a network of about 13.7 M weights; the owner's two thoughts answered
- 20:15 — The owner's play test: V30 better than v0.2, S40 fought worse; the judge that sees the truth did not help and is left out; v0.3, the new baseline, started 20:17
- 16:00 — v0.2.2's setting (V) holds 53.5% against v0.2 under the fixed clock; the slow memory (S) is level at update 10 and two points under at 20, 21% slower an update; counterplay unchanged in every run

## [2026-10-13](results/2026-10-13.md)

- 07:00 — v0.2.1's first start fell to 25% against the control in 20 updates and was stopped (23:30); seven arms in the night: the lesson that makes his own keys copy the movement network is the cause, alone and with the shared layers held out; started again at 06:43 without it, first half only, to 19:00

## [2026-10-12](results/2026-10-12.md)

- 20:35 — v0.2.1 started (20:31, the owner's go); before it, the game's reach for a pickup measured in 7,767 recorded pickups: the simulator's reach lies inside it, so it is not why he passes items; the owner's notes from watching v0.2
- 20:00 — v0.2.1 rewritten around the owner's four goals: the guessing game gets four more questions (eight in all); his choice of what to do next does not use where the enemy is (the blindfold, with its control); eight questions at three times the weight move him three times as hard at first and his aim holds; a tracking limit lowers lightning and leaves rail; his aim stays as it is
- 16:00 — The second aim step: the aim level is a weak lever, the tracking delay is the strong one and takes the rail with it; no setting gives all three; leg 2 takes the small step
- 15:15 — v0.2 is on the public server (the owner: "yes send him to the public server"); his answers to v0.2.1's questions; the run waits for his go at about 21:00
- 15:00 — v0.2.1's pretests on the card: both legs fit and run on the eight performance cores; the legs' lesson takes at once and leaves his aim alone; the place choice as first opened cost him the big items; 60% of an update is the learning step, not the simulators; an efficiency core is not safe even for a job pinned alone
- 13:00 — Python jobs on the PC began to die at random at 11:12: not our code but the processor's efficiency cores (a thread pushed off one in mid-work now and then resumes a few instructions early); stages B and C merged; everything of ours now runs on the eight performance cores
- 09:45 — The server batch of the owner's remarks: a game's own end with the map vote, weapons back in 5 s, the owner marked, people tied to their sessions, F3 in 1v1 found and fixed, the Discord line, the QLStats lookup; proven on a private server, not on the public one yet
- 06:55 — "Awaiting snapshot" again on the public server: the seat guard of 2026-10-10 read a field the header has wrong
- 05:00 — v0.2 at seven hours: 56.7% against v0.1, all of the gain on the four maps v0.1 never played games on; his way of playing has not moved (scorecard 47%); stages B and C all built and merged in a copy

## [2026-10-11](results/2026-10-11.md)

- 23:40 — v0.2 plays on a real server (private, both plugins: its 143 inputs and the attention part); stage B parts 1 and 2 and stage C part 1 built in copies; the checks' noise measured (the same network against itself: 48.8%)
- 22:00 — v0.2 built and started (21:49): attention stage A with 143 new inputs, the two-minute value estimate, the hop-gain pay, the first aim step, ten maps; the enemy as a target left out after a proper level check (45.9% in 128 games); Dismemberment in place of Delirium as the second held-out map
- 19:10 — Fights taken and refused, and the flick curve, from the pros' demos with v15c's end beside them: he stays in twice as many fights as the pros and the same in every situation; up to 40 degrees off target his first hit comes sooner than a pro's, and the enemy appears within 20 degrees of his view 28% of the time (the pros 65%)
- 19:00 — The afternoon before v16: the pros' measures and how near he is to them (48% of the way on fourteen measures), the enemy as a target (lost by a broad rule, level by a narrow one), the three rocket changes tried (no change in his rocket use), the server's timing for the attention model (passes), a held-out map, the duel check made even between its seats
- 13:40 — `duel_gru_v15c` (v15b's end with the weapon work, two readings to switch his legs off, speed pay 0.5): level with v15b, no gain in speed kept or in rockets; the real game plays his legs (B-213) and both beat the game's Nightmare bot; v15c on the public server
- 12:50 — The public server's data: a fuller daily pull (raw logs, seven days on the server, an index, a second copy)
- 07:00 — `duel_gru_v15b` after its night: he strafe jumps on his legs (9.2% of his travelling time at 400 or more; v14's end 1.3%, the pros 17.5%) and his duels rose to 56% against v14's end; his time at speed did not rise in training

The log of 2026-10-02 to 2026-10-10 (the first approach and the numbered models v1 to v15b, before v0.1) is kept
locally, out of the repo.

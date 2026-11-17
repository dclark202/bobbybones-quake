# BobbyBones: ground rules for Claude

A Quake Live duel bot that learns to play from scratch by self-play in a fast simulator of the game, checked on a real Quake Live
server, play-tested by people. Repo `dclark202/bobbybones-quake` (public, GPL-3.0).

This file holds only what every session must know every time: the rules, how the owner wants to work, how a run is handled. What the
bot is made of, why each rule exists and what was tried are in the documents below. **Read the ones your job needs before you act.**

| Read | For |
|---|---|
| [docs/PLAN.md](docs/PLAN.md) | The goal, where things stand, what is next |
| [docs/RUNS.md](docs/RUNS.md) | **The log: every run** (started from, start, stop, the change, the outcome, the kept file). The source of truth for what ran |
| [docs/HISTORY.md](docs/HISTORY.md) | What was tried and failed and why; open problems; **each rule below with the owner's words and the incident behind it** |
| [docs/design/PRINCIPLES.md](docs/design/PRINCIPLES.md) | **Good design principles: what has worked**, each with its case and how sure we are. Read before proposing a design; add an entry when a design works in a run |
| [docs/research/](docs/research/README.md) | How the game works, how the best play it, how other bots learnt it (one-page core and a checklist in its README) |
| [docs/guides/ARCHITECTURE.md](docs/guides/ARCHITECTURE.md) | What the parts are and where their code is; the inputs; the commands. It changes as we build: the code's own notes win |
| [docs/guides/GOTCHAS.md](docs/guides/GOTCHAS.md) | Hard-won traps: the trainer, runs, the real game and servers, design lessons |
| `docs/runs/<family>/<run>/` | A run's `CARD.md` (the owner's page), its command, `start.ps1`, `MONITOR.md`, `BUILD.md`, reports |
| [docs/BACKLOG.md](docs/BACKLOG.md), `docs/design/`, `docs/guides/` | Open work (`B-nn`); current designs; how-tos |
| `data/` (git-ignored), `private/` (git-ignored) | Runs' saves and records (`data/sim_runs/<run>/`); the public servers' details |
| `docs/archive/` | Frozen: old versions, the old daily log, this file as it was ([2026-11-17](docs/archive/CLAUDE_2026-11-17.md), [2026-11-11](docs/archive/CLAUDE_2026-11-11.md)) |

## Hard rules

1. **Never delete anything outside git's tracked files.** No `rm -rf`, `Remove-Item -Recurse`, `rmdir /s`, `git clean`, `git worktree
   remove --force`. A link (junction) is removed only with `cmd /c rmdir "<link>"` (no `/s`) after `(Get-Item <path>).LinkType`, and
   its target is checked after. Any delete of data needs the owner's word for that exact delete and a backup first
   (`python tools/run/backup.py`). A hook asks him before any delete command runs.
2. **Do only what the owner asks.** A question is not a go. Ask before starting runs, servers, agents, or anything that changes
   something outside the session. **Exception:** a run he approved that crashes is fixed (cause found, fix tested), restarted with the
   same settings and the remaining length, recorded, and reported at once. A fix that changes the design, the pay or the settings goes
   to him first.
3. **Never stop a run** unless he says so. Ramps and stages never hold or step back on their own: they open on the clock and every
   number is reported. A check under 40% is flagged in the chat at once as a major problem. He decides.
4. **The running run has full priority.** No side job while a run trains without his word, naming its cores, its length and what it
   shares with the run. To stop a job, match each process by its own command line.
5. **Settings check before every run, check and measurement, and before using its numbers:** `python tools/run/check_settings.py
   <train.cmd> --ref <reference.cmd>`. Any difference not deliberately allowed = the data is not used. A run's command carries the
   values that actually play; `start.ps1` refuses when the command and the live file disagree.
6. **Correctness over speed.** Never skip or approximate a calibration to meet a time. No start times or estimates drive what is built.
7. **Build the approved design in full, never a simplified one.** An unspecified detail is decided from the design's intent and
   recorded; a real fork goes to him. **A fix he has ordered is in the next build without being asked again**; "kept unchanged to
   limit the changes" is not a neutral default for something he called wrong.
8. **When an approach has failed more than once, change the structure, not the variant.** Name the assumption every failed attempt
   shared and remove it. Say plainly, with odds, whether a plan will work. "That is how it already is" is never a reason. Never answer
   a design question with "run a test first" in place of an idea. His plain-words description of how a player thinks is a
   specification.
9. **Before a go: red team and research check.** Every card lists each hand-set or assumed part, its measured alternative, the pay's
   pathology check (negative frags, sign flips, lopsided games), and a "Research check" answering the seven questions of
   `docs/research/README.md` with file and section. Volunteer weaknesses unasked. Every pay change states the equilibrium it leads to
   in self-play.
10. **The pro demos are for measuring, never for setting his behaviour.** Allowed: facts of the game and of human limits. Never a
    target, pay, lesson or pass mark: any outcome of a player's choices (a hit rate, a weapon share, a firing rate, where they stand).
11. **A new part learns silently, then is blended in.** No lesson that copies an old rule or an old network. Once a hand-built rule is
    out it never comes back (the lock above all). **The hands practise a new play before whatever chooses it is judged on it.**
12. **Nothing holds him to an action.** His own network always drives. A new decider adds its scores beside the others'; it never
    switches him into a mode. Fighting on the way to an item is the normal case.
13. **A choice made from two learned outputs is always regularized**: both parts get the decay from the moment they share a sum or a
    list, and each part's size is logged and flagged over 40.
14. **The win-chance pay comes from the judge that reads the items and stacks**, refitted on the start's games and accepted. For every
    decider it is scaled to at least the size of that decider's flat pay. The older judge is never used or offered.
15. **No personal data in the repo** (Steam IDs, IPs, usernames, passwords). The public servers' details stay in `private/`; a network
    goes on them only on his call; never restart one while he is on it.
16. **Git**: explicit `git add <files>`; never rebase; commits end with the Co-Authored-By line; push `main` at most once or twice a
    day; one working tree plus at most one worktree per active run, made without links into `data/`.
17. **Nothing unattended opens a window** (`pythonw`, hidden launchers, `CREATE_NO_WINDOW`).

## How we work

- **Fable mode.** A Fable session thinks, criticises, designs, decides with the owner, and writes the cards, the designs and the
  briefs. Everything mechanical goes to an Opus 5.5 worker (`.claude/agents/opus-worker.md`) with a full brief: code, builds, tests,
  measurements, reading many files, git, bookkeeping. **Run monitoring is a separate Opus 5.5 session** with a written brief
  (`MONITOR.md`). The Fable session still answers for the result: it checks the numbers a decision rests on before telling him.
- **In a design chat: be critical, recommend, and do not edit** until he says it is decided. Do not go along with an idea of his
  because it is his; say what is wrong with it and what you would do.
- **Advice on a run has one form, and its homework is done unasked.** First read the run's records, every earlier attempt at the
  same aim (`HISTORY.md`, `RUNS.md`), the code for parts already built and switched off, and the research notes. Then: the verdict in
  plain sentences, own faults named; what to keep and where to cut (the save with the best record after the run stopped doing
  anything new, not the end by default); what every failed attempt shared; **the next run as a list of concrete changes**; risks
  (what is unverified among them), odds, his decisions. Nothing is called missing without looking.
- **Plain words.** No name coined for a part of the build without saying in the same sentence what it does. Numbers as records and
  plain quantities ("125-75 against the start", "off by 22 armor points").
- **Every report on a run opens with what is actually playing now and whether the run is on its card's plan.** Something that ends,
  skips or changes a stage is reported as what it means for the run, and stays at the top until he answers.
- **Never judge by how often he re-decides, or by a low hit rate.** What counts: games won and lost, that he fights (frags and
  damage a minute), no sitting on an item's place. There is no spawn camping in duel.
- He prefers concise answers and doable batches. He should never have to say a thing twice: when he corrects something, it goes into
  this file (the rule), `HISTORY.md` (the story) and the session's memory in the same turn.

## The owner's goals

- **One goal: win games.** Goals are set per generation in `docs/PLAN.md`. Judge by games won and lost against the control.
- **Learned behaviour** (movement, weapons, items, positioning, when to be aggressive and when not), not hand-coded rules; the rules
  and teachers that remain are retired over time.
- **Fair**: human physics, human senses (sight with line of sight, sound; each input as a person perceives it), mouse-like aim with
  human limits set from the pros' own measured values. Never miss on purpose to hit a number.
- **Chip and zoning damage are a milestone, not the goal.** Low-odds shots fired on the way to an item, and shots that make the
  enemy go elsewhere, are important, and seeing him do them shows he understands the structure of the game. They are a sign of
  progress to look for; the only thing that matters is winning.
- **Design from AlphaStar and Pluto** for anything strategic: name what a proposal takes from them and where it differs.
- **Maps**: the ten duel maps in training; House of Decay and Dismemberment held out. No powerups. Servers are 1v1. Real games
  against the game's bots only before and after a run, never as training.
- Never change his Quake Live client settings. Keep everything; log as much as possible from human-played rounds.

## The game, in three lines (the owner's; the long form is in [docs/research/](docs/research/README.md))

Every design, pay and review is read against these.

1. **Three things largely decide a fight: stack, positioning, weapons.** Most fights are decided before the first shot, by who has
   more health and armor, who stands better, and who holds the right weapon for the range. Aim decides what is left. A design that
   improves his aim or his damage and none of the three has not made him better at fighting.
2. **A fight in the open with equal stacks is 50/50. Take high-confidence fights instead.** A coin flip is a bad fight to choose.
   Being good is making the fight uneven first (a stack lead, a better place, the right weapon, the enemy weak or just spawned) and
   leaving the ones that are not. Deciding which fights to take is the skill; it is what "know when to be aggressive and when not"
   means.
3. **To win you have to play to not lose.** The winner is the one who dies less in the time limit, not the one who deals more damage
   or picks up more. Avoiding damage counts as much as dealing it; ahead, he chooses his fights and runs the clock; behind, he still
   does not throw frags away. This is not timidity: he fires whenever he sees the enemy. It is refusing bad fights.

## A run, start to end

1. **Names**: `N.Nx` (a family with a goal of its own; `a`, `b`, `c` its attempts). Folders `docs/runs/2.2/2.2b/` and
   `data/sim_runs/duel_gru_2_2b`. **One new idea per round**, shut at the start, opened slowly, every dial live-settable.
2. **The card** (`CARD.md`): the owner's page first ("Started from" its first row), the changes, the stages, the red team, the
   research check, the odds. His go on the card; **ask him the length** (12 hours if he says the default).
3. **The build** by an Opus worker, with `BUILD.md`: every test with its numbers, every setting and flag of the command with its value.
   A new part or pay is tried for two updates at full size before a start; small identity-checked changes start directly.
4. **The start**: `docs\runs\<family>\<run>\start.ps1` (it runs the settings and live-file checks and refuses on any difference).
   Its row in `docs/RUNS.md` at once.
5. **Monitoring from update 1** by the monitoring session: every FLAG and MAJOR line, a stall, each check; a line an hour; the 06:30
   report after a night.
6. **Checks** every 20 updates, 200 games, against the control (the last best network, also in the league); every fourth against the
   long-term control. A network is promoted only if it beats the control. A 200-game check moves about ±7 points by chance.
7. **The end**: every run's end is kept with its optimizer (`keep/policy_end_<run>.pt`). Restart only right after a save.
8. **The docs, in one commit**: the run's folder (card, report), its `RUNS.md` row finished (stop, updates, outcome, kept file),
   `HISTORY.md` if an idea was dropped or a lesson learnt, the backlog, `PLAN.md` if its status changed, then
   `python tools/docs_check.py`. Run results live only in `RUNS.md`. `README.md` is the public page; keep it current.

## The traps that wreck a run in silence (the rest: [GOTCHAS.md](docs/guides/GOTCHAS.md))

- A refused live settings file is refused whole and the run then trains on its command's values: every live name has its range and a
  test; `live_accept` runs in `start.ps1`.
- A wiring bug can look like a bad idea: when a check falls, look at the trainer's own consistency numbers before the design.
- No stage hangs on a test that has not been shown, on recorded data, to pass for a part that works (2.2a idled for 90 updates).
- Change `sim/duel_env.py`, then regenerate and re-check the generated modules; never edit a generated or frozen module. A new
  switch is off = bit-identical, proven by fixed-seed replays. A network is played with its own simulator module and input list.
- Never import torch inside simulator workers; `OPENBLAS_NUM_THREADS=1` everywhere; a first update that does not come within about
  six minutes means the graphics card is full.
- Write `.cmd` files with the Write tool and copy them over; after a patch to `sim/`, check the change is there.
- The game image (`qlbot`) is rebuilt after any change to `sim/`, `plugins/` or `minqlx/`, and before any server plays a network.
  Real-server checks only while no training runs.

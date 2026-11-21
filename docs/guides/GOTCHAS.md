# Hard-won gotchas (moved out of CLAUDE.md on 2026-11-17)

Read the part for the job in hand: before starting or restarting a run, before a server, before a design. The few that can wreck a
run in silence are also in CLAUDE.md.


**Runs and the trainer**
- **A refused live.json is refused whole, and the run then trains on its command's start values** (1.7a's false start): every
- **The command carries the values that play** (2.2a's audit, 2026-11-17: its command still said `--held-g 0`, `--pull-g 0`,
  `--intent-teach 9.13`, `STACK_DIFF=0.7`, `RAIL_FAR_PAY=0.12` while the live file played the lock out, the teacher off, 0 and 0.1: one
  refused live file would have brought the lock and the item rule's teacher back in silence). A new run's command has, for every name
  with a live dial, the value that actually plays as its start value; `start.ps1` refuses when the command and the start's live file
  disagree. The build's record lists every setting and flag of the command with its value and whether it differs from the run before:
  the session reads that table before a start and the owner can ask for it.
- **The win-chance pay comes from the judge that reads the items and stacks, always** (owner, 2026-11-16 and 11-17: "you must use the
  right one here. This is called cutting corners"). Two judges sit in the code and the older, item-blind one was every run's inherited
  default; 2.2a switched the right one on for a side forecast only. From 2.2b the settings check and the trainer refuse a new run whose
  win-chance pay is not from it (an explicit replay flag for old runs). It is refitted on the start's games and accepted before a
  start. It is never offered as a choice and "the judge cannot see items" is never written as a caveat again.
- **A fix the owner has ordered is in the next build without being asked again.** "Kept unchanged to limit the changes" is not a
  neutral default for something he has called wrong; one change at a time is about new parts, not about leaving known faults in.
  live name that may be negative is in `LIVE_RANGE`; a refusal before the first rollout stops the trainer; `live_accept.py` in
  `start.ps1` reads the start's file and every one the ramp will write; every new live name gets its range and a `tests.py live` test.
- A wiring bug can look like a bad idea: 1.7c's false start (PPO's reference pass without the weapon key's mask) read as a slow
  collapse. When a check falls, look at the KL and the trainer's own pieces before the design.
- `--lr-warm` counts from `--fade-start`, not from the run's start: on a line whose `--fade-start` is far in the past it does
  nothing and the first update runs at the full rate (found in 2.2b's build). Give `--lr-warm-start <the start's minute>`.
- **Switching a part's lesson off while the rest of it trains leaves its outputs unheld** (2.2b's first start: the item picker's choice
  lesson off for 10 updates, its memory moving under its forecast's loss; he ended up holding the gauntlet, 0-200 at update 10). Freeze
  the whole part but the layer that learns (gradient None before the step: a zero gradient with Adam's moments still moves it), prove it
  every update, and let any trial run past the update where a warm-up or window ends.
- A start without its own optimizer: carry the nearest kept one (2.2b: 2.2a's update 100 for a start at update 90). Cold, even at
  a tenth of the rate, the weapon choice moved twenty times faster than usual in the second update.
- Restart only right after a save (every 10 updates), keep a copy; pass `--fade-start <minute>` on every resume.
- `--obs-half` is retired (owner, 2026-11-15: "There's no reason to keep it"): the rollout's stored inputs at half precision made the
  learner's recomputed log-probabilities differ from the played ones (up to 0.08 to 0.12 at the worst frame at full size, 2.1d's proof);
  the flag is retired and refused; a new run's command built from an older one strips it. Since 2026-11-15 (2.1d's restart at update 30)
  the trainer always rounds the rollout's inputs to half precision at their source, so play and learning read the same values and the
  stored inputs are float16 (full precision cost 12.6 GB a buffer and nearly exhausted the PC's memory). Every other reader now rounds
  the same way, bit for bit, for every network (branch `bhalf`, to be merged after 2.1d ends): the checks' player (`test_suite.Policy.norm`),
  the plugins' pass (`netpass.norm`; `movetest`), the tools that normalise on their own, the brain's lessons (`sim/obs_half.py`: torch's
  `.half()` of a double rounds twice, so the torch paths round once in double precision). **The `qlbot` image must be rebuilt before any
  server plays a network** (the export is unchanged: `policy.npz` keeps the mean and variance, the plugin rounds).
- Write `.cmd` run files with the Write tool to the scratchpad and copy them over (Git Bash heredocs mangle backslashes; writing
  over an existing `.cmd` in a chain once failed silently and the old settings ran). After a patch to `sim/`, check the change is
  there (a write once failed with Errno 22 and left the file as it was).
- A scratch test must import the repo's `sim/`, not a staging copy. Two tools that import a module being edited mix versions.
- GPU memory: long sequences and many players fill the 16 GB card (`--minibatches`, `ATTN_AMP`); a first update that does not come
  within about six minutes means the card is full. After every widening, check `metrics.jsonl` keeps growing.
- `OPENBLAS_NUM_THREADS=1` in every `.cmd` and pool (else each worker commits 0.7 GB; Windows ran out of commit with 36 GB free).
  `CUDA_VISIBLE_DEVICES=-1` (not `""`) hides the card on Windows; a CPU trainer needs `OMP_NUM_THREADS=1`.
- Where an update's time goes: 40% rollout, 60% the learning step (Python steps the GRU per piece: time goes with the number of
  pieces, B-237). More simulator cores help the rollout only.
- `SetPriorityClass` via ctypes needs `restype`/`argtypes` on 64-bit Python; `subprocess` `creationflags=0x4000` works.
- The PC's load as Windows reports it reads far above the share of processor time: size side jobs by the load. The PC has
  blue-screened under load: runs save every 10 updates. Keep `PYTHONFAULTHANDLER=1` and the exit codes.
- A background shell is capped at two hours; chain waiters or launch detached.
- `tools/list_inputs.py` writes `docs/INPUTS.csv` whatever its arguments.
- An identity check after a new output: random actions for the old outputs only, or the random stream shifts.

**Design lessons (each cost a run)**
- The checks' noise: the same network against itself reads 48.8% over 160 games, single maps 41 to 56%. Read maps one by one too
  (v14 lost Aerowalk 24 points while the mean did not move). The control belongs in the checks from the first hour: "53% against
  his old selves" says nothing.
- A new lesson must pass ten updates and a check against the control before a start; a fitted start for a new choice must pass a
  full level check, not a probe.
- A teacher must have the pupil's hands and must not name what he cannot reach (v14: the item rule sent him over Aerowalk's circle
  jump; `RULE_WALK=1`). A teacher with new labels moves the whole network at once (`--teach-trunk`, `--teach-warm`).
- A new choice opened by a bias costs what it displaces: open it out of the one it stands in for (`targets_init.py open
  --from-nothing`); the entropy bonus spreads his choice over new equal choices whatever they pay, and drowns small shaping costs.
- Anything paid per frame for progress is paid on a running best, or a setback and its recovery is a pump.
- Whatever is paid by the damage must not be added to `dealt` (his feedback inputs are made of it).
- **A test that decides whether a stage opens can idle a whole run** (2.2a: the switch-on test of the part that rated his options
  could not have passed even for a perfect one, because on his own choices the goal is already known from his state; the stage never
  opened and 90 updates trained nothing new). No stage hangs on a test that has not been shown, on recorded data, to pass for a part
  that works and fail for one that does not. Stages open on the clock (rule 6) and the numbers are reported with urgency.
- **What an option is worth cannot be learnt from his own choices**: he only ever takes the one he prefers. Only options he was sent
  on at random show it (2.2a: knowing the goal helped on the 3% random trips and nowhere else). Every "judge" of his options so far
  failed (1.9a's scorer, 2.2a's rater); the owner does not want another. New options are taught to the hands by practice first.
- **An order the hands have not practised is judged worthless and learnt away** (1.7a: 2% → 0.02%; the same shape in 1.9a and 2.2a).
  Whatever changes who chooses comes after the hands can carry the choice out.
- **Nothing holds him to an action** (owner, 2026-11-17: "What I DO NOT WANT to happen is to have any type of blinders like we had
  with previous leg networks where they would force him into an action"). A new decider adds its scores to one list beside the
  others'; it never switches him into a mode. Fighting on the way to an item is the normal case and how most damage is done.
- **Low-odds shots are part of the game** (owner, 2026-11-17: chip and zoning damage; "most people hit maybe 1 in 10 grenades, that
  doesn't mean they're useless"). A low hit rate is never a fault in a check, a pay or a readout, and never a reason against a shot.
- **There is no spawn camping in duel** (players' spawn points are random; owner, 2026-11-17). The old notes' "spawn camping" means
  sitting on an item's place (v0.4.3 sat on the lightning gun). Say "camping on an item".

**The real game and servers**
- The plugins call `observe()` but never `step()`: anything only `step()` updates is stale on a server unless the plugin sets it.
  After any input change, record the inputs in a real game (`OBSDUMP=1` with `tools/bench_arena.sh`) and set them beside the
  simulator's. Rebuild `qlbot` after any change to `sim/`, `plugins/` or `minqlx/`.
- Real-server checks only while no training runs. Before one: `docker ps`, `docker stats --no-stream`; stop servers nobody uses
  (`docker stop`, not `rm`).
- An rcon client that leaves while the server prints (a map load) can freeze the server: `tools/rcon.py` leaves only in a quiet
  moment; a map change gets `--wait 30`.
- Quake Live locks `sv_fps` at 40. The client uses UDP 27960, servers 27970. An idle server runs no frames until someone joins.
  minqlx has no damage event (hits from health drops); warmup emits no kill stats. Aborting a warmup countdown in a loop hangs the
  server. A chat line must not have a percent sign before a letter.
- A pure server's pak list must be exactly a client's (pak00, bin, the Workshop item), or players drop silently. `sv_pure` is
  write-protected; `sv_warmupReadyPercentage` and `sv_maxclients` are latched. The server's stdout lags through `tee`.
- Plugin changes can be tried without an image build: mount `plugins/` over `/ql/minqlx-plugins` and `tools/` over `/tools`.
- The game's pickup reach (7,767 pickups): 36 units each horizontal axis, any jump height; the simulator's (`dxy < 36`,
  `dz < 56`) lies inside it.
- Docker on Windows: LF line endings (`.gitattributes`).
- After merging a branch, push plainly: `git pull --rebase` on a merge commit replays the branch. Fetch and look first.

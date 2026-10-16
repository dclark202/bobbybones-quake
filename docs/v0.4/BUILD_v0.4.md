# v0.4 build spec: the head (written 2026-10-16 16:30 for the night's build)

The design is [CANDIDATE_v0.4.md](CANDIDATE_v0.4.md) (hands and head) and [PROPOSAL_v0.4.md](PROPOSAL_v0.4.md) section 13.
This page fixes the **interfaces**, so that four lanes can be built at once. A lane that needs to change an interface
says so in its report rather than changing it quietly.

## 0. Rules for every lane

- **Base:** branch `v0.4` (from b50983a: main 2521b01 plus the server queue). One worktree and one branch per lane:
  `v04-core`, `v04-sim`, `v04-pre`, `v04-serve`. Commit on your own branch; never push; never merge into main.
- **Data:** each worktree gets a junction `data` → `C:\Users\dacla\ql-bot\data`. Read from it only; write your scratch
  under your worktree's `scratch/`, which is git-ignored.
- **The running training must stay undisturbed.** `duel_gru_v0_3_1b` trains from `C:\Users\dacla\ql-bot-v031c` on the
  card until 19:00, and again from about 21:00.
  - CPU only: `CUDA_VISIBLE_DEVICES=-1`.
  - Every Python process: `OPENBLAS_NUM_THREADS=1`, `OMP_NUM_THREADS=1`, `PYTHONFAULTHANDLER=1`, affinity `0xC03C3`
    (`cmd //c start "" //b //wait //affinity C03C3 ...`, or the scratchpad's `es/pinrun.py`), low priority.
  - At most **two** processes per lane at a time, and nothing that runs more than about 20 minutes.
- **Do not touch:**
  - `C:\Users\dacla\ql-bot-v031c`, `ql-bot-v031b`, `ql-bot-arms`
  - `data/sim_runs/duel_gru_v0_3_1b` (except to read a `keep/policy_*.pt`)
  - the `qlbot` docker image, any server, the public server
  - the owner's Quake Live folder
  - `C:\Users\dacla\ql-bot` itself (it is the owner's checkout: work in your worktree)
- **Off = today, proven.**
  - Every simulator change sits behind a switch that is off by default. With it off, `ident16.py` (scratchpad) is
    IDENTICAL for `duel_env` and `duel_env_ffa` on Blood Run and Aerowalk with the v0.3.1 switches.
  - `tools/ffa_check.py` passes.
  - Change `duel_env.py`, then regenerate `duel_env_ffa.py` with `tools/make_ffa_env.py`; never edit the generated
    file.
- **Style:** match the code around you (comments in the owner's plain words, the switch documented where the others
  are). Commits end with `Co-Authored-By: Claude Opus 5.5 <noreply@anthropic.com>`. Write commit messages to a file and
  use `git commit -F`.
- No personal data in the repo: no Steam IDs, addresses or Windows usernames.

## 1. The part: `sim/head.py` (lane core owns it; the others build against this API)

The layout dict, kept in a checkpoint as `ck["head"]` and in `policy.npz` as JSON text under `head`:

```python
layout(every=8, size=1024, inp=768, fast=512, enc=256, ev=32, plan=256,
       slots=224, write_every=4, slot=128, read=256, read_heads=4, ring=96,
       n_target=17, n_way=3, win_bands=5, chrono=96)
```

**A tick** happens on frame t when `(g + 1) % every == 0`, where g is the global frame count (as `sim/slowmem.py`).

- **The tick's input:** `u = [h_fast after frame t (512) ; mean of e over the tick's frames (256) ; store read (256) ;
  events of the tick (32)]`, 1056 numbers.
- **The slow step:** `p = tanh(inp(u))` (768), then `s = GRUCell(768 → 1024)(p, s)`. The `chrono` start is as in
  slowmem.
- **The plan:** `plan = tanh(plan_out(s))` (256), held until the next tick.
  - **It reaches the hands through a new layer `head.plan_in`, Linear 256 → 256, initialised at zero, added to the fast
    GRU's input:** `x_fast = e + plan_in(plan)`. The GRU's own shape is unchanged.
  - With `plan_in` at zero the network is v0.3.1 exactly.
- **The store:**
  - Every `write_every` ticks (0.8 s) one slot is written: `slot = write([s ; mean e ; events])` → 128.
  - It is a ring of `slots` = 224 slots (3 min), and each slot keeps its age in ticks.
- **The read** (on every tick, before the slow step, using the slow state of the tick before):
  - 4-head attention.
  - The query comes from `s`. The keys and values come from `[slot ; age features (8)]`.
  - Output 256. A store with no slots reads zeros.
- **The outputs, all from `s`:**

| Name | Shape | Init | Use |
|---|---|---|---|
| `target` | 17 | zero | added to the hands' intention logits on the tick frames and held for the tick |
| `way` | 3 | zero | added to the hands' way logits, the same way |
| `v_short` | 1 | normal | value, γ per frame 0.999 (≈ 25 s), the same returns as the hands' value |
| `v_long` | 1 | normal | value of `r_long` at γ 0.9998 (2 min) |
| `win` | 5 | zero | bands of the final score margin: ≤ −5, −4..−1, 0, 1..4, ≥ 5 (whole games and mid-game starts only) |
| `aux.*` | as today's `--aux-heads` | zero | the guessing questions, asked of the head |

- **Reset:** the trainer's `done` clears `s`, the plan, the running mean and the store, as it clears the fast memory.
- **Exact start:** `plan_in` = 0 and `target` / `way` = 0 means a converted network answers exactly as before. Prove
  it with fixed-seed replays.
- **API, torch:**

```python
make_module(lay, seed=None)
class State                     # (n, lay, dev), reset(d), peek()
live(mod, st, e, h_after)       # -> (plan_for_next_frames, target_add, way_add)
seq(mod, lay, e, hs, dn, st0)   # learning step: everything over a rollout
Ring                            # the ring of inputs before the rollout, as slowmem's
```

  Because the plan feeds the fast GRU, the learning step runs the fast GRU in **8-frame segments**: one fused call per
  segment, with a head tick between segments (48 segments for 384 steps).

- **API, numpy** (lane serve writes it, in the same file, numpy only at the top level):

```python
np_state_width(lay)
np_tick(W, lay, e, h_after, hf, events)   # -> (plan, target_add, way_add, hf2)
```

  The whole state is one array per seat: `[s | plan | acc e | n | frames | store slots × (slot + 1 age) | write
  count]`.

## 2. The trainer (lane core)

- The switch is `--head <layout json or "default">`. Without it the trainer is today's: proven by an identical
  first-update loss on a fixed seed.
- **Conversion:** `tools/head_init.py <in.pt> <out.pt>` adds the part (zeros where it must be). `--same a b` proves that
  the two answer alike on recorded inputs.
- **Loss masks:**
  - `target` and `way` count on tick frames only (`intent_live` for the head).
  - `win` counts on ticks of whole games with a known result.
  - Head values: on ticks only.
- **The head's learning rate** is `--head-lr-scale` (default 0.25), in its own optimiser group.
- **Opponents:** the league's files without a head get one with `plan_in` = 0 (as `load_net` does for the slow memory).
- **Write per update:** `head` in `metrics.jsonl`, with the plan's size, the norm of `plan_in`, the share of the target
  from the head, the win head's loss and calibration, and the read's attention entropy.

## 3. The simulator (lane sim)

- **Events:** `env.head_events()` → `[n, 32]` float32. These are counts and flags since the last call (the trainer calls
  it on ticks):
  - damage dealt, damage taken (/100)
  - he fragged, he died
  - enemy seen (frames share), enemy heard (any sound)
  - his pickups by class: MH, RA, YA, RL, RG, LG, health or ammo (7)
  - pickups he heard or saw the enemy make, by the same classes (7)
  - item respawn sounds heard: MH, RA, YA, weapon (4)
  - the enemy's pain sound heard
  - his weapon changed
  - he jumped (take-offs), he landed from a fall
  - padding to 32

  Only what he could perceive, as the inputs. It must be fed by what the plugins can also call: the existing `note_*`
  hooks plus a new `note_event` if needed. A plugin never calls `step()`.
- **Labels** in `info["aux"]` (new columns, never inputs): the final score margin band of the whole game at its end,
  written back to every tick of that game. Whole games and mid-game starts only. The trainer needs the band per tick
  of a finished game, which arrives only at the game's end: keep the rollout's ticks and fill them in when the game
  ends, or mask the ones whose game has not ended. Choose one and say which.
- **The switch:** `HEAD_EVENTS=1` (a `PLAY_VAR`). Off means no events computed and the simulator unchanged.

## 4. Pretraining (lane pre)

- `sim/head_data.py`: sequences for the head from
  1. the pro demos (`sim/demo_dataset.py` output; the demos are in the folder named in `data/demo_root.txt`)
  2. the public server's session logs (`T:\quake-sessions\public\*.tar.gz`, `frames.csv`: both players every frame;
     [docs/guides/LOGS.md](../guides/LOGS.md))
  3. the new input logs (`inputs_*.npz` in a session folder: `t, frame, obs[797], h[512], acts[13]`; none exist yet,
     so a synthetic one is enough for the test)
- **Labels:**
  - target: the next item or holding place the player reached
  - the enemy's place 3, 10 and 30 s ahead (masked where unknown)
  - the final score margin band
- `sim/pretrain_head.py`: the hands are frozen (a v0.3.1 checkpoint run in eval mode to give `e` and `h`); the head is
  trained on those labels, CPU-runnable at a small size.
- Read before relying on the demos: CLAUDE.md "Pro demos", and the record that imitating mouse or trigger destroyed aim
  (only the head is trained here, so the hands are safe by construction).

### 4.1 How to build the data and run the pretraining (lane pre, 2026-10-16)

Everything on the CPU (`CUDA_VISIBLE_DEVICES=-1`, the section 0 rules); the Anaconda Python; `data/` read only (the
route caches go to `scratch/route_cache`, `ROUTE_CACHE`).

```bash
python sim/head_data.py spec --ck <policy.pt> --out scratch/spec.json       # the hands' simulator module and switches, once
python sim/head_data.py demos --map bloodrun --limit 3 --spec scratch/spec.json --out scratch/head_data   # DEMODUMP=<demodump.exe>
python sim/head_data.py sessions --archives T:/quake-sessions/public/<s>.tar.gz ... --seat both --spec scratch/spec.json --out scratch/head_data
python sim/head_data.py inputs --session <a session folder with inputs_*.npz> --spec scratch/spec.json --out scratch/head_data
python sim/head_data.py synth --session <an unpacked session> --into <folder> --ck <policy.pt> --spec scratch/spec.json   # a test log
python sim/head_data.py show scratch/head_data/*.npz                        # shapes and label rates
python sim/head_data.py count                                               # demos and 1v1 sessions per map
python sim/pretrain_head.py --ck <policy.pt> --data scratch/head_data --small --steps 300 [--head-module scratch/standin]
```

- **Inputs.** The converted sets of `sim/demo_dataset.py` (`<demo root>/sets`) hold the 311 inputs of 2026-10-04 and are
  not usable: `head_data.py` builds the 797 inputs again with the checkpoint's own module (`duel_env_ffa`, two seats) and
  switches, fed as the 1v1 plugin feeds it (`plugins/duelbot.py` `frame()`), the player whose sequence it is in seat 0.
  The plugin's input logs (`inputs_*.npz`) are taken as they are. Not rebuilt exactly (the file's top lists it all): his
  intention input is the item rule's choice (`--intent rule`; the hands' own choice would need the network in the
  builder), his way is 0, no legs network; in demos the enemy's health, what the recorder dealt, the enemy only while the
  server sent him; in sessions the ammunition of SG / GL / PG / MG and the item timers (only pickups are logged).
- **Labels per tick** (a tick on every 8th frame he is alive): target (the next item of the intention list he picked up, or
  holding place he stood at for 1 s, within 60 s and before his next death; never across a cut to another followed player),
  the enemy's landmark 3, 10, 30 s on (as the aux question `near`; unknown where a demo did not send him), the final margin
  band (whole games with a known end: a demo's intermission with the followed player's own score agreeing, a session's
  real game from `player_stats`). Beside them the baselines: the item rule at the tick, the landmark of v0.2's believed
  place. Events: the 32 columns of section 3, counted by the builder until `env.head_events()` lands.
- **Speed.** About 5 to 7 ms a frame on a busy PC: a ten-minute demo or session seat in 2 to 5 minutes. All 5,039 demos of
  the twelve maps are about 200 hours of one core; run them map by map in jobs under 20 minutes.
- **Pretraining.** The hands' `e` and `h` are worked out once per shard and cached (`--cache`); plan_in stays at zero, so the
  head is unrolled over its ticks only (`head.ticks`, asked of lane core; a stand-in that follows section 1 is in the
  lane's scratch). The hands are hashed before and after (bit-identical, asserted). The enemy lesson's layer (`pre.en`) is
  the pretraining's own.

**Data counts** (2026-10-16). Demos in the archive (`T:/quake-demos/demos`): Aerowalk 1,012, Blood Run 1,293, Lost World
1,411, Campgrounds 226, Battleforged 150, Furious Heights 150, Sinister 150, Hektik 146, House of Decay 142, Dismemberment
142, Cure 130, Toxicity 87 (hza 6,192 and trinity 22 are no map of ours). Of Blood Run's, 1,066 of 1,293 converted in
`sim/demo_dataset.py`'s run; the rest were too short or broken. 1v1 sessions with a person in the public archive (sessions,
real games of 5 min or more, minutes of frames): Blood Run 16 / 12 / 162, Sinister 11 / 6 / 136, Furious Heights 8 / 5 /
114, Hektik 9 / 3 / 84, Aerowalk 37 / 1 / 72, Toxicity 7 / 2 / 41, Cure 6 / 2 / 40, Campgrounds 5 / 3 / 37, Lost World 5 / 1
/ 27, Battleforged 1 / 1 / 11: about 720 minutes, 36 games with a result, each usable twice (Bobby's seat and the
person's). The free-for-all sessions are not used. No input logs exist yet.

**The proof** (3 Blood Run demos, 2 sessions x 2 seats, 1 synthetic input log; 24,619 ticks; head at `--small`; 300 steps,
20 % of every shard held out at its end): label rates target 0.82, enemy at 10 s 0.73 (demos 0.32 to 0.45, sessions 0.85 to
0.98), win 0.70, belief 0.88. Losses (first 25 steps -> last 25): target 2.51 -> 0.67, enemy 2.63 -> 1.89, win 1.41 -> 0.12.
Held out: target 22 % (item rule 10.5 %, most common label 11 %), enemy at 10 s 11.3 % against the belief's 10.9 %, at
30 s 13.0 % against 13.2 %: on this little data the head overfits (82 % target on its training ticks) and the gate is not
met; the win head's 74 % held out is the same games' later minutes (the band is one number a game), not a skill. The hands
were bit-identical before and after, plan_in still zero; the hands here agree with `test_suite.Policy` to 7e-6.

## 5. Serving (lane serve)

- The numpy head in `sim/head.py`: `np_tick` must match torch's `live` to 1e-5 on random inputs.
- `sim/export_duel.py` writes `head` (layout) and `head.*` weights.
- `plugins/netpass.py`: `step()` carries the head's state in the seat's state array, ticks it every 8 frames, adds
  `target` / `way` and feeds the plan.
- `plugins/duelbot.py`: the events for the tick, from the same hooks as the simulator. The 1v1 plugin is primary; the
  free-for-all plugin may break (owner, 2026-10-16), but say so.
- `sim/test_suite.py` / `tools/duel_eval.py`' `Policy`: the same numpy path, so the checks can play a v0.4 network.

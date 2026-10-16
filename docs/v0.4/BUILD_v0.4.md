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

### 3a. As built (lane sim, 2026-10-16)

**The columns**, `duel_env.HEAD_EVENT_COLS` (also `N_HEAD_EVENTS = 32` and `HEAD_COL`, name → column), and the hook that
feeds each one. step() calls the same hooks, so a plugin that calls them gets what training gets.

| # | Name | What | Fed by |
|---|---|---|---|
| 0 | `dmg_dealt` | damage he dealt to other players, points / 100 | `note_combat(dealt, taken, frag, died)` |
| 1 | `dmg_taken` | damage he took from anything (enemies, his own splash, lava, falls) / 100 | `note_combat` |
| 2 | `frag` | frags he made of another player | `note_combat` |
| 3 | `died` | his deaths of anything | `note_combat` |
| 4 | `en_seen` | share of the tick's frames with an enemy *noticed* in view (reaction and acquire delay, as the inputs: `acquired`, in a group `acq2`) | `note_frame()` |
| 5 | `en_heard` | flag: any enemy sound heard | `hear()`, `_hear()`, `note_frame()` (the senses' running steps: `seen_t` at 0 with nobody noticed; a fresh pain sound) |
| 6–12 | `took_mh`, `took_ra`, `took_ya`, `took_rl`, `took_rg`, `took_lg`, `took_small` | his pickups by class; `small` = everything else (health, shards, green armor, ammunition, the other weapons) | `note_take(i, it)` |
| 13–19 | `en_took_*` | pickups of others he saw (noticed in view) or heard (within `HEAR_EVT`), same classes; never in movement rounds or solo rooms | `note_take(i, it)` |
| 20–23 | `resp_mh`, `resp_ra`, `resp_ya`, `resp_wp` | item returns heard (within `HEAR_EVT`) | `note_respawn(k, who)` |
| 24 | `en_pain` | the enemy's pain sounds heard (`pain_t` set to 0 on the frame) | `note_frame()` |
| 25 | `weapon_change` | the weapon in his hand changed (not across a spawn or a teleport) | `note_frame()` |
| 26 | `takeoff` | left the ground going up (over 100 u/s: a jump, a jump pad) | `note_frame()` |
| 27 | `fall_land` | landed `HEAD_FALL_DROP` (64) units or more below where he left the ground | `note_frame()` |
| 28–31 | `pad_28` … `pad_31` | zeros | |

- `head_events()` returns the counts since the last call (`en_seen` divided by the frames counted) and starts again;
  zeros with the switch off. `note_event(i, name, value)` adds to any column by name, for anything a plugin knows that no
  other hook brings.
- **The plugin's side (lane serve):** once a frame call `note_combat` with the game's counts of the frame (damage dealt
  to the opponent, damage taken, frags, deaths; arrays of `env.n`), and `note_frame()` **after** `senses()`, the pain
  sound (`pain_t`) and `env.weapon[0]` are set and the state is filled. `hear()`, `_hear()`, `note_take()` and
  `note_respawn()` are already called by `duelbot.py` and count by themselves. Then `head_events()` on the head's tick.
- **A round's end:** a player whose round ended (`done`) starts his count again at the start of the next step; the frame
  that ended it is still in the count, so a tick on that frame sees it. A plugin has no rounds: nothing to do.
- **Off:** nothing of it is created or computed (the names are in `MOMENT_STATIC`, so a mid-game start never copies
  them), no random number is drawn: the simulator is today's, proven below.

**The win label**, two more columns at the end of `AUX_COLS`, only with `HEAD_EVENTS=1` (read them by name:
`AUX_COLS.index("win_game")`):

- `win_game`: the number of the whole game (`game` kind 1) or mid-game start (kind 3) **the frame just played belongs
  to**: `info["aux"]` of the step that played frame t (the trainer's `obs_t` → `act_t` → `step`) carries the game of
  frame t. A running number of this simulator from 0, the same for all seats of the game (float32, exact below 2^24); key
  it by (worker, player) and number. -1: no labelled game (a normal round, an item run, a jump run, a late round, a spawn
  start).
- `win_band`: on the frame that ends such a game (the step whose `done` is set for it; overtime played out): the band of
  his final margin, his frags less the best of the others' (a mid-game start's saved score included): 0 for ≤ −5,
  1 for −4..−1, 2 level, 3 for 1..4, 4 for ≥ 5 (`WIN_BAND_EDGES`). -1 on every other frame.

**The trainer's side (lane core). Choice: fill in, with the true band where the game ended in the rollout and the
head's own forecast otherwise. A game whose end has not come is never masked.** A game is 24,000 frames, about 63
updates of 384 steps. Masking the unfinished games would label only the last 9.6 s of each game, where the score already
tells the result. Keeping the ticks until the end costs too much memory: 3,000 ticks × 1,024 slow-state numbers a
player-game, which is tens of GB for 10,000 players. So the band is learnt as a value is, with γ = 1: the forecast at a
tick should equal the forecast at a later tick of the same game.

1. On every head tick k (frame t_k) of the rollout keep `gid[p, k] = aux[t_k, p, win_game]`.
2. For every player p and game g ≥ 0 in the rollout: if a frame of the rollout has `win_game == g` and `win_band >= 0`,
   that frame ended g: the target of every tick of g is `one_hot(win_band)` (the **true** label; its loss is the one
   counted for calibration).
3. Otherwise g goes on past the rollout. The target of its ticks is `softmax(win_logits)` at **the last tick of g in the
   rollout**, detached (from `seq`'s own outputs in the learning step, or from the collection pass). That last tick
   itself is masked.
4. Ticks with `gid == -1` are masked. Loss: cross-entropy of `win` to the target, over the ticks not masked.
   Optionally weight the true-label ticks up. Report the loss and the calibration from the true-label ticks only.
5. The game's frames before its first tick in the rollout (the rollout starts mid-game) need nothing: their ticks
   were in the rollout before.

**Proofs (2026-10-16, CPU, the v0.3.1 switches).**

- `ident16.py`: base e9aed8c against this branch is IDENTICAL for `duel_env` and `duel_env_ffa` (group 3) on Blood
  Run and Aerowalk, with the switch off and with `HEAD_EVENTS=1`. `tools/ffa_check.py` passes, off and on.
- Events: random play with weapons handed out, `head_events()` on every frame. On Aerowalk (4,000 frames, 24 players)
  the sums match the simulator's own books:
  - pickups 198 = the stats' 198 (mega 8, red 9)
  - frags 19, deaths 38
  - damage dealt and taken equal to `info["aux"]`
  - `en_seen` equals the frames noticed
  - every column moved, and the padding never did.
  `duel_env_ffa` on Blood Run gives the same.
- The win label: games brought to their end with set scores, 7,748 of them on Aerowalk (2,703 whole games, 5,045
  mid-game starts). All give the right band for both seats: ±5 and more, ±1..4, overtime decided by a frag, and level
  after the last overtime period. No band appears on any other frame, and the game's number changes on the frame after
  its end.

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

## 5. Serving (lane serve)

- The numpy head in `sim/head.py`: `np_tick` must match torch's `live` to 1e-5 on random inputs.
- `sim/export_duel.py` writes `head` (layout) and `head.*` weights.
- `plugins/netpass.py`: `step()` carries the head's state in the seat's state array, ticks it every 8 frames, adds
  `target` / `way` and feeds the plan.
- `plugins/duelbot.py`: the events for the tick, from the same hooks as the simulator. The 1v1 plugin is primary; the
  free-for-all plugin may break (owner, 2026-10-16), but say so.
- `sim/test_suite.py` / `tools/duel_eval.py`' `Policy`: the same numpy path, so the checks can play a v0.4 network.

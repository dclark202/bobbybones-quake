# The server's frame budget

Quake Live runs 40 frames a second: 25 ms a frame. The duel plugin (`plugins/duelbot.py`) does all of Bobby's work inside
the game's frame, on the game's own thread: the inputs (`env.observe()`), the network (`netpass.step`), his hands
(`drive`, the finger limits) and the bookkeeping. A frame that takes longer than 25 ms is late, and players feel it as
lag. The work is single-threaded: a second core does nothing for it (measured 2026-10-29, the same numbers pinned to one
core), so a 1 vCPU server serves as well as a 2 vCPU one of the same speed.

## Measuring it

- **On a server:** `DUEL_TIMING=1` (`TIMING=1` for `tools/duel_server.sh`) writes `timing.txt` in the data folder, one
  line a minute of play: the frame's median, p90, p99 and max, the share over 15 and 25 ms, and of it the inputs and the
  network. Lines appear only while someone plays (an empty server runs no frames). The first minute after a map load has
  one frame of 0.4 to 1 s: the load, in every build.
- **Without a person:** a private sparring container (`SPAR=1`: Bobby against Nightmare, no port opened, unlisted) with
  `TIMING=1`. A/B two builds on the same host, alternating (old, new, old, new): the hosts' speed drifts over the evening.
- **Where the time goes:** `DUEL_PROFILE=2400` writes a cProfile of the plugin every 2,400 frames (`profile_<k>_tottime.txt`,
  `_cumulative.txt`). It slows the frame; read the shares, not the times.
- **Offline:** the simulator's `observe()` and the network on the PC, with the public network file, two seats played by
  the network on a fixed seed: the scratch scripts `record.py` (records inputs, actions, memory and the legs' inputs a
  frame), `compare.py` (bit for bit) and `bench_net.py` (the network at one seat). The PC is about 3 times faster per core
  than a Vultr High Frequency vCPU.

## The rule for a speedup

Bobby must play exactly as trained. Every change is checked **bit for bit**: the same inputs, actions, memory and legs'
inputs on all ten maps (1,500 frames each, fixed seed), on the PC and inside the server image (its Python and numpy
versions). A speedup that changes a number, however small, is a simulator change and goes through training instead.
`duel_env_ffa.py` is regenerated from `duel_env.py` (`tools/make_ffa_env.py`, whose anchors match exact lines).

## Done (branch `pub-perf`)

| Commit | Change | Effect |
|---|---|---|
| 29bbc4b | `observe()`: the item inputs for all 13 blocks in one pass (one distance table, one sight cone, one trace call: `rays_md`, the same trace ray by ray); the lava and slime spots of both radii in one trace and one contents call; no projectile block when none is in sight; the old projectile block that `PROJ_SEE` replaces no longer built | |
| 29bbc4b | `np.clip` through numpy's own clip ufunc for float arrays (`_clip`: np.clip's three Python layers end in that call); `rot()` without `np.stack`; fixed tables made once (one-hot tables, ray angles, the splash radii, the route items' respawn times) | inputs 7.6 -> 5.8 ms on the server (-24%) |
| 29bbc4b | the network: the layer norm's means as numpy's `_mean` makes them without its wrappers (`attn._mean_last`), the tokens' column lists, the input scale and the draw's tables made once per network | -2% on the server (-8% on the PC) |
| 8bf5184 | the hearing check (`HEAR_QL`: `hear` -> `_hear_ok` -> `pvs.Vis.clusters`): the BSP descent point by point in plain Python floats (the same float64 sums in the same order; `leaves_np` is the reference) and a memo of recent points | it was 9% of a frame on 1 vCPU; 80 -> 9 us a player's box |

Live: `qlbot:perf` (29bbc4b) on both public servers from 2026-10-29/30, `qlbot:perf2` (8bf5184: `qlbot:perf` with the new
`sim/pvs.py` copied in, a thin layer built on each server) from 2026-10-30 01:37 UTC. The code is on `pub-perf`, not yet on `main`.

The frame on the same Vultr host and hour (private sparring, old against new): median 15.5 -> 13.6 ms, late frames
2.8% -> 1.4%. In people's games on the new build: 12.6-13.5 ms, 0.5-1.4% late. On 1 vCPU / 1 GB: 12.5-15.7 ms, about 1% late.

Tried and left out: Python's garbage collector frozen after load (`gc.freeze()`: 203 collections in 3,000 frames down to 2;
its effect on late frames could not be measured on a busy PC: to measure on a server); computing only Bobby's seat in the
inputs (the work is per numpy call, not per seat: about 5%, the traces only).

## Where more time could come from

From the 1-vCPU profile of 2026-10-30 (before 8bf5184), as shares of the plugin's frame:

| Part | Share | What it is | Idea |
|---|---|---|---|
| `observe()` | ~43% | about 3,000 small numpy calls on two rows | more batching as above: `_v02` (its places and items), `_pref`, `_emerge`, `_extra`'s sight rays, `locate` (11 calls a frame), the 54 remaining `np.stack` calls, 220 `astype` calls |
| the network | ~11% | matrix work mostly; the attention part's two blocks, `btoken`, the legs' branch | little left without changing the numbers |
| `legs_prep` | ~6% | the movement network's inputs (`_move_labels`, `movement_env.observe`) | once a frame already (`legs_reuse`); batch its calls |
| `drive` + `limit_keys` | ~6% | his hands: the finger limits, the mouse | vectorised already; small gains |
| `hear` | ~9% | the hearing check | done in 8bf5184 |
| `log_frame`, `senses`, `sync_world`, `intent_release`, the frame's own lines | ~10% | the game's state into the simulator, the logs | the logs' writing on a background thread (the inputs log already is) |

Larger changes, each its own piece of work: Bobby's work on a second thread one frame behind (`docs/BACKLOG.md` B-292: needs a
second core and a simulator check of the extra 25 ms); the hot parts of `observe()` in C beside `sim/sim_api.c` (a new library
build and the same bit-for-bit check).

## Running on 1 vCPU / 1 GB

Since 2026-10-30 both public servers run on Vultr High Frequency 1 vCPU / 1 GB boxes (details in `private/`). What that needs:
background jobs at Linux's idle scheduling class (`chrt -i 0`: a `nice 19` job still cost late frames on one core), the
services a game server does not need switched off, no image build on the box (it may not fit in 1 GB: the image is built
elsewhere and copied in), and the session pull every 6 hours (32 GB disks). Memory: about 560 MB of 955 used in play; the
largest container peak seen was 433 MB.

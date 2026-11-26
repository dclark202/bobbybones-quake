# knecht-q3-bot — the DoomWarriors Quake 3 port of BobbyBones

A fork of [BobbyBones](https://github.com/dclark202/bobbybones-quake), the Quake Live duel bot that was trained from scratch by reinforcement learning. BobbyBones plays Quake Live through a server plugin; **this project ports the same approach to Quake 3**: the clan runs the [Quake3e](https://github.com/doomwarriors-clan/Quake3e) engine (`dwc` branch) with the [OSP](https://github.com/doomwarriors-clan/osp) game mod, and the goal is a bot that learns our duel and TDM maps by playing against our own clan botfiles — with human-like senses only (field of view, line of sight, no wall hacks).

## Status (2026-11-26)

| Milestone | State |
|---|---|
| **Phase 0 — spike:** prove an external process can drive a bot client slot in Quake3e + OSP **per frame** (usercmds incl. substeps, game-state read-back, lifecycle edges like kicks / map rotation / sidecar death) | **DONE** — scenario suite T1–T10, final matrix **12/12 green** on the merged engine (2026-11-20); see `spike/` + `docs/spike/SPIKE_ENGINE.md` |
| Engine-side `botctl` control channel (Unix socket, **off by default**, `botctl_enable 0`) | **merged** into [doomwarriors-clan/Quake3e](https://github.com/doomwarriors-clan/Quake3e) `dwc` (PR #13), shipped in release `dwc-2026.11.20` |
| **Training PoC:** PPO on live dedicated duel servers against clan botfiles | **IN PROGRESS** — multi-day runs run6 + run7 completed/paused (~5.8 M steps so far); current focus: a **learning-signal telemetry fix** (see "Training findings" below). Canonical training stack lives in the private Forgejo `homelab` repo (`rl/`, run7 v2.3 + README recipe); this repo's `phase3-poc` branch is being synced from it |
| TDM 2v2 env (8 clan TDM maps) | built + smoke-verified, idle until the duel learning signal matures |
| Sim parity (port the upstream `sim/` approach to Quake 3) | not started — next after the training PoC |
| Live deploy on production servers | **open clan decision** — only after a trained net proves itself; the engine channel stays off by default until then |

## Training findings (2026-11-26)

- **run6 (duel vs skill-5 clan botfiles, ~4 M steps, multi-env PPO v2):** flat — K/D stuck at ~0.04 across six 200-rollout buckets, no skill trend; more wall-time alone did not help. Decision: change the learning setup, not the budget.
- **run7 v2.3 (launched 2026-11-26):** 3 parallel duel envs (Sarge / Doom / Daemia at skill 2 — opponent curriculum), frag-dominant reward v3 (kill +10 / death −3 / intermission outcome ±20/5), multi-env PPO learner (`ppo3`/`train3`), policy initialized from run6, fresh value head. Infrastructure ran green (watchdog, per-env fault isolation, ~150–190 steps/s).
- **Telemetry finding (early review after 622 games):** the per-game log recorded **0 frags / 0 wins**, while the server's own `games.log` showed real kills — and a naturally finished duel confirmed the engine scoreboard also saw almost none (17 RL-bot kills in ~209 games vs skill 2; ~390 damage dealt per game without closing kills). Root causes found: the duel servers' **map feeder force-cuts games** (`nextmap`/watchdog `force map` every ~150 s — those games write no `Exit:`/`score:` lines, so outcome detection and score read-back operate on garbage boundaries), and the env's kill detection relies on a snapshot alive→dead edge that does not fire reliably under those conditions. **Consequence: the +10 kill reward was almost never delivered — the run optimized damage/survival shaping but was never reinforced for finishing kills.**
- **Ground-truth reconciliation harness built** (`rl/harness_kill.py` + `rl/harness_server.sh`): a dedicated duel server with **natural game endings** (fraglimit/timelimit, no map feeder) plus an independent shadow view of the snapshot stream; per-game PASS/FAIL checks reconcile env counters against `Kill:` lines in `osp/games.log`. Fix of the env accounting + adoption of natural-end server configs for the training runs is the current work item.
- **Next steps:** 100-game validation run with a working kill/outcome signal → curriculum gate decision (skill 2 → 3 at sustained game K/D ≥ 0.5) → re-evaluate run6's "flat" verdict under clean telemetry. Network architecture (GRU policy + PPO, 1.89 M params) is unchanged so far; checkpoints remain usable as `--load` starting points.

## How it fits together

```
training process (Python, consumer GPU)
   │  observations (game-state snapshots)        usercmds every frame (+ substeps)
   ▼                                             ▲
botctl Unix-socket channel  ────────  Quake3e dedicated server (dwc build, USE_BOTCTL=1)
   ▲                                  + OSP QVM + clan botfiles
   └─ rcon: swaps the opponent bot at episode boundaries
```

The bot occupies a **regular client slot** (it shows up in `status`, joins teams, scores like a player) but is driven frame-by-frame from outside the engine — no scripting embedded in the engine, no changes to the game QVM. The spike proved the whole channel incl. its failure modes; the training PoC reuses the exact same protocol.

## What lives where in this repo

- `spike/` — Phase 0 client side: `botctl.py` (stdlib protocol client), `sidecar.py` (scenario brains T1–T10), `run_spike.sh` (spike driver), `rcon_probe.py`
- `docs/spike/` — spike design (V1/V2), measurement methodology, the full 12/12 results matrix, and the archived engine issue/PR text (`QUAKE3E_ISSUE.md`)
- `phase3-poc` (branch, merge pending) — the RL training stack: duel / duel-v2 / duel7 environments on the botctl channel, PPO (`ppo2`/`ppo3`), policy nets (`net2`), training loops (`train2`/`train3`), smoke + recovery + rotation tests, server start/stop scripts. Being refreshed from the canonical Forgejo `homelab` `rl/` tree (run7 v2.3 + ground-truth harness) before its merge
- everything else (`sim/`, `tools/`, `plugins/`, `minqlx/`, `server/`, …) — the original BobbyBones Quake Live project, kept untouched as design reference

## Relationship to upstream

Upstream BobbyBones keeps moving fast, for **Quake Live**. We treat its code as a reference, keep all clan work **purely additive** (new directories only, no edits to upstream files), and pull upstream improvements in as periodic **upstream-sync merge PRs** into `main` — next one planned after the `phase3-poc` merge, and always refreshed before the sim-parity phase starts. QL-specific parts (minqlx plugin, QL maps and physics, QL sim tuning) are never ported blindly: each is evaluated against Quake 3 mechanics when its phase begins.

## Related clan repos

- [Quake3e](https://github.com/doomwarriors-clan/Quake3e) (`dwc`) — the engine incl. the `botctl` half of this project
- [osp](https://github.com/doomwarriors-clan/osp) — the game mod on our servers (needs no botctl changes)
- [dwc-bots](https://github.com/doomwarriors-clan/dwc-bots) — the clan botfiles used as training opponents
- [q3-servers](https://github.com/doomwarriors-clan/q3-servers) — production server configs (a later live integration would touch this)

## License

Upstream code in this repository is covered by the [GPL-3.0](LICENSE) license (`LICENSE`); `WEIGHTS_LICENSE.md` covers upstream's published Quake Live model weights. The engine-side `botctl` code lives in the Quake3e fork under its GPL terms.

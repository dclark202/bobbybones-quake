# knecht-q3-bot — the DoomWarriors Quake 3 port of BobbyBones

A fork of [BobbyBones](https://github.com/dclark202/bobbybones-quake), the Quake Live duel bot that was trained from scratch by reinforcement learning. BobbyBones plays Quake Live through a server plugin; **this project ports the same approach to Quake 3**: the clan runs the [Quake3e](https://github.com/doomwarriors-clan/Quake3e) engine (`dwc` branch) with the [OSP](https://github.com/doomwarriors-clan/osp) game mod, and the goal is a bot that learns our duel and TDM maps by playing against our own clan botfiles — with human-like senses only (field of view, line of sight, no wall hacks).

## Status (2026-11-22)

| Milestone | State |
|---|---|
| **Phase 0 — spike:** prove an external process can drive a bot client slot in Quake3e + OSP **per frame** (usercmds incl. substeps, game-state read-back, lifecycle edges like kicks / map rotation / sidecar death) | **DONE** — scenario suite T1–T10, final matrix **12/12 green** on the merged engine (2026-11-20); see `spike/` + `docs/spike/SPIKE_ENGINE.md` |
| Engine-side `botctl` control channel (Unix socket, **off by default**, `botctl_enable 0`) | **merged** into [doomwarriors-clan/Quake3e](https://github.com/doomwarriors-clan/Quake3e) `dwc` (PR #13), shipped in release `dwc-2026.11.20` |
| **Training PoC:** PPO on the live dedicated server against skill-5 clan botfiles | **IN PROGRESS** — the stack is in branch `phase3-poc` (merge PR planned 2026-11-24); a multi-day training run is active; how to run it: `phase3-poc/README.md` |
| TDM 2v2 env (8 clan TDM maps) | built + smoke-verified, idle until the duel learning signal matures |
| Sim parity (port the upstream `sim/` approach to Quake 3) | not started — next after the training PoC |
| Live deploy on production servers | **open clan decision** — only after a trained net proves itself; the engine channel stays off by default until then |

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
- `phase3-poc/` (branch, merge pending) — the RL training stack: duel / duel-v2 / TDM-2v2 environments on the botctl channel, PPO (`ppo2.py`), policy nets (`net2.py`), training loop (`train2.py`), smoke + recovery + rotation tests, server start/stop scripts
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

# Phase 0 — Spike Engine: external per-frame control of Quake3e bot client slots

**Status: T1–T6 PASS (2026-11-15) — GO for Phase 1.** See `QUAKE3E_ISSUE.md`
for the PR text.

## Objective

Prove that an **external process** (no embedded scripting, no QVM changes) can
drive a bot client slot in a Quake3e (`dwc`) + OSP dedicated server **per-frame**:
own the slot like a human player, submit usercmds every frame (incl. substeps),
and read game state back — on a TDM server, with the stock game QVM.

This is the first gate of the RL-bot port (`knecht-q3-bot` / BobbyBones): if
per-frame external driving doesn't work, the port needs a different architecture.

## Design

- **Engine patch** (Quake3e branch `botctl-spike`, off `dwc` tip `8fa5549e`;
  6 files, `botctl_enable 0` = stock no-op):
  - `code/server/botctl.c` — UDS listener thread on
    `/tmp/q3e-botctl-<port>.sock`, binary protocol (PING/ADD/REMOVE/TEXT/CMD/
    SNAP/LIST), per-client staged usercmd queue, snapshot serializer.
  - `SV_RunFrame` hooks: `Botctl_Frame()` BEFORE `GAME_RUN_FRAME` (replay
    staged cmds, K/frame spread evenly = substeps) + `Botctl_Snapshot()` AFTER
    (dump reflects the frame that just ran).
  - `SV_MapRestart_f`: managed clients reconnect as regular players
    (`Botctl_IsManaged`; the NA_BOT-based `isBot` would be rejected by
    `BotAISetupClient` when `bot_enable 0`).
  - Per-frame reliable-command ACK + `lastPacketTime` refresh for the
    packetless managed clients (mirrors `SV_BotGetConsoleMessage` for engine
    bots; without it: "Server command overflow" drop in ~1 min, `sv_timeout`
    after 200 s).
- **Protocol**: snapshot = `u32 time, u32 restart_id, u16 np, u16 ne` +
  player blobs (132 B: client, origin[3], health, armor, weapon, weaponstate,
  team, score, viewangles[3], delta_angles[3], pm_type, ammo[16]) + entity
  blobs (52 B: items/missiles/etc.).
- **Sidecar** (this repo, branch `spike-q3e-botctl`, `spike/`): stdlib-Python
  `botctl.py` (protocol client) + `sidecar.py` (T1–T6 brains) + `run_spike.sh`
  (driver: FIFO stdin, fresh home, TDM cvars, port 28133, TERM→KILL cleanup).

## Test matrix & results

Test instance: knecht, port 28133, fresh home `~/.q3a_spike`, `bot_memory 0`,
stock OSP **dwc.4** QVM (`dfb1c02a`), TDM `q3dm7` (`g_gametype 3`), 20 fps.

| # | Test | Result | Measured |
|---|------|--------|----------|
| T1 | slot lifecycle (add/list/connect/join/remove/freed/readd) | **PASS** | `list=True connect=True joined=True team=red remove=1 freed=True readd=0`, `SERVER_EXIT=0` |
| T2 | scripted movement (first-1.0 s clean run) | **PASS** | 300.6 u/s, dir_dot 1.000, 300.7 u |
| T3 | substep replay 1 vs 4 cmds/frame | **PASS** | 309.3 vs 301.9 u/s, ratio 0.98 |
| T4 | world state + firing | **PASS** | 53 items visible; nearest item (244 u) picked up (vanishes); MG ammo 50→37 **and** `WEAPON_FIRING=3` observed (drifting-phase sampling) |
| T5 | TDM warmup → match start | **PASS** | red+blue join + `say ready`; match started ~15 s after last join (in-place `map_restart`); both bots **alive after the restart** |
| T6 | 10-min random-action soak + clean SIGTERM | **PASS** | 600 s/600 s, 9,978 snapshots, dead_time 0 s, `SERVER_EXIT=0` |

All runs: engine alive at scenario end, `SERVER_EXIT=0`.

## Key findings (things we learned the hard way)

1. **This OSP build's numbering is not vanilla**: no blaster —
   `0=NONE 1=GAUNTLET 2=MACHINEGUN …` (11–13 MISSIONPACK-only), `MAX_WEAPONS=16`,
   `WEAPON_FIRING=3`. A gauntlet (1) "fires" only on a physical trace hit.
   TDM spawn: MG (2) + 50 ammo + 125 hp (excess 25 counts down 1/s to 100 —
   stock Q3 rule, NOT damage).
2. **Firing observation**: fixed-period sampling phase-locks onto READY frames
   (always reads state 0 even while firing) → use ammo decrement (robust) or
   drifting-phase sampling. `PMF_RESPAWNED` blocks the first shot until a
   delivered buttons=0 cmd ran pmove (release ~1 s, then attack).
3. **Snapshot timing**: dumps must be built AFTER the game frame; `map_restart`
   does NOT reset engine time — `sv.restartedServerId` is the reliable
   "(re)start happened" signal.
4. **Packetless clients need ACK upkeep** (reliable commands + lastPacketTime)
   or the engine drops them (~1 min / 200 s).
5. **TDM warmup resets when a team goes empty** — test bots must stay in their
   teams until the match actually starts; expiry = in-place `OSP_MapRestart`.
6. JIT "compiled to N bytes" is **not** a QVM fingerprint (prod and clean both
   825,400).

## Go / No-Go

**GO.** An external process can drive a client slot per-frame on the production
engine+QVM with stock behavior: full run speed, substeps, state reads (incl.
items + ammo + firing), team/warmup/match flow, and multi-minute stability.
No engine-side limitations surfaced that would block the port.

## Next (Phase 1: sim parity)

- Rebuild BobbyBones `libqsim` from Quake3e sources (Q3A/OSP settings,
  sv_fps 40 → substep 3), parity audit vs the real server (their
  `tools/phys_compare.py` / `sim/validate.py`), nav data for the 8 TDM maps.
- Open the `Quake3e` issue (see `QUAKE3E_ISSUE.md`), push `botctl-spike`,
  PR base `dwc`.
- Before Phase 3 (training): vLLM TP=2 → single GPU (user action) per the GPU
  compromise.

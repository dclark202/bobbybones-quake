# Paste-ready: `doomwarriors-clan/Quake3e` issue (open BEFORE the first push of `botctl-spike`)

Title:

```
botctl: external per-frame control of bot client slots (Unix socket) for the RL bot port
```

Body:

```markdown
## Why

We are porting the BobbyBones RL bot (see `doomwarriors-clan/knecht-q3-bot`) to
Quake3e (`dwc`) + OSP for the TDM servers. The live-server side of that port
needs the engine to let an **external process** (a Python "sidecar")

1. own a client slot like a bot would (no QVM bot state, normal
   team assignment / warmup / scoring — the client is played *from outside*),
2. submit usercmds **every frame** (including several per frame / substeps),
3. read the game state back (players: origin/viewangles/health/armor/weapon/
   ammo, plus interesting entities: items, missiles, ...) —

without embedded scripting in the engine itself. Goals: keep the engine clean
(the sidecar is a separate, unlinked process — nothing but the engine's own
GPLv2+ sources is linked into the binary), keep ops simple (one Unix socket,
one cvar), and keep everything **off by default** so a stock build behaves
exactly as today.

This issue is for the Phase-0 "spike engine" step: prove that an external
process can drive a bot client slot per-frame on a TDM server, end to end.

## What the patch does

Branch `botctl-spike` (off `dwc` tip `8fa5549e`; original commit + two
review-rework commits), 7 files:

- `code/server/botctl.c` (new, ~1500 lines): a listener thread on the Unix
  socket `fs_homepath/botctl-<net_port>.sock` (chmod 0600; the
  `botctl_sockpath` cvar overrides) speaking a small binary protocol
  (PING / ADD / REMOVE / TEXT / CMD / SNAP / LIST). `ADD` creates a real
  client slot (NA_BOT netchan, `isBot=qfalse` in the game connect, so the
  game module treats the client as a regular player). Staged usercmds are
  queued per client; `Botctl_Frame()` (called from `SV_RunFrame`) replays
  them **before** `GAME_RUN_FRAME`, spreading K cmds per frame evenly over
  the frame (substeps). A state dump requested via `SNAP` is built by
  `Botctl_Snapshot()` **after** `GAME_RUN_FRAME`, so it reflects the frame
  that just ran: header `u32 time, u32 restart_id` (sv.restartedServerId —
  changes on every map (re)start), player blobs incl. `ammo[MAX_WEAPONS]`,
  and the interesting entities.
- `code/server/sv_main.c`: the two call sites around the game frame.
- `code/server/sv_init.c`: `Botctl_Init()` (registers the `botctl_enable`
  cvar, default **0**) and `Botctl_Shutdown()`.
- `code/server/server.h`: declarations.
- `code/server/sv_ccmds.c`: `SV_MapRestart_f` reconnects botctl-managed
  clients as regular players (`Botctl_IsManaged()`). Without this the
  stock NA_BOT-based `isBot` flag makes the game run `BotAISetupClient`,
  which rejects the client when `bot_enable` is 0 — i.e. every in-place
  `map_restart` (warmup expiry, round rotation) would silently drop the
  external bots.
- `Makefile`: `USE_BOTCTL` gate (default **0**): only `USE_BOTCTL=1` (and
  never on mingw/Windows builds) adds `-DUSE_BOTCTL`, `botctl.o` and
  `-lpthread` to the dedicated target.

Packetless-client mechanics (the part that needs a second look in review):
botctl slots exchange no network packets, so nothing would ever acknowledge
their server→client reliable commands — the 64-slot buffer overflows in
~1 minute on the 1/s `tinfo` team broadcast alone ("Server command
overflow" drop), and `sv_timeout` (200 s default) is the second killer.
`Botctl_Frame()` therefore acks their reliable commands and refreshes
`lastPacketTime` each frame — exactly what `SV_BotGetConsoleMessage`
already does for the engine's own bots. The sidecar consumes state via the
UDS channel, so discarding the client-protocol stream is correct.

## Rules compliance

- **Off/stock by default**: `botctl_enable 0` (default) → the whole code
  path is a no-op (early returns; the socket is only bound when enabled).
- **Gated at compile time**: `USE_BOTCTL = 0` (Makefile default) → no
  `botctl.o`, no `-lpthread`, no `-DUSE_BOTCTL`; the `server.h` hooks only
  exist for `USE_BOTCTL && DEDICATED` and are no-op macros otherwise. The
  default-build binaries were byte-compared against the parent commit:
  identical (see SPIKE_ENGINE.md).
- **Dedicated server only**; clients stay stock (no protocol/cgame/ui
  changes).
- **No syscall-enum changes** (nothing appended/inserted in `gameImport_t`).
- **No new compiler warnings**: built with
  `make BUILD_CLIENT=0 BUILD_SERVER=1 USE_MV=1 release` — zero new warnings
  (only the pre-existing `sv_client.c:402`).

## Verification (Phase-0 test matrix)

Dedicated test instance (knecht, port **28133**, fresh home, `bot_memory 0`,
stock OSP **dwc.4** QVM, TDM `q3dm7`, `g_gametype 3`), driven by the
stdlib-Python sidecar from `knecht-q3-bot` (branch `spike-q3e-botctl`):

| Test | What it proves | Result |
|---|---|---|
| T1 | slot lifecycle: add / list / connect / team join / remove / slot freed / re-add | PASS |
| T2 | scripted movement: first-second clean run 300.6 u/s, direction dot 1.000 | PASS |
| T3 | substep replay: 1 vs 4 cmds/frame → 309.3 vs 301.9 u/s (ratio 0.98) | PASS |
| T4 | world state: 53 items visible, nearest item picked up (vanishes), MG fire proven (ammo 50→37 + `WEAPON_FIRING` seen) | PASS |
| T5 | TDM warmup → match start (in-place `map_restart`), both teams stay in, bots **alive after the restart** | PASS |
| T6 | 10-minute random-action soak (walk/jump/fire, deaths handled), clean SIGTERM | PASS (600 s/600 s, 9,978 snapshots, dead_time 0 s, `SERVER_EXIT=0`) |

Also verified: engine survives the whole run (`SERVER_EXIT=0`), the
reconnect fix keeps managed clients through `map_restart`, and a 600 s
run stays connected (the reliable-ack / `lastPacketTime` refresh).

## Proposed flow

1. This issue (you open it).
2. I push `botctl-spike` and open a PR against `dwc` (single commit;
   throwaway head branch as per repo rule).
3. After merge: normal `dwc-YYYY.MM.DD` release flow when/IF we want it in
   the release binaries. Until then it can live on `dwc` dormant
   (`botctl_enable 0`) — it costs nothing at rest. No production
   deployment is part of this; the q3-servers flow comes with the actual
   bot deploy (apply = Micha).

Out of scope here: the NN/sidecar itself (lives in `knecht-q3-bot`), any
game-module (QVM) changes, and training infrastructure.
```

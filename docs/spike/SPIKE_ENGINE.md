# Phase 0 — Spike Engine: external per-frame control of Quake3e bot client slots

**Status: V2 rework done (Quake3e PR #13, issue #12); full green spike run
T1–T9 on the V2 engine (2026-11-16) — GO for Phase 1.** See `QUAKE3E_ISSUE.md`
for the issue/PR text.

## Objective

Prove that an **external process** (no embedded scripting, no QVM changes) can
drive a bot client slot in a Quake3e (`dwc`) + OSP dedicated server **per-frame**:
own the slot like a human player, submit usercmds every frame (incl. substeps),
read game state back — on a TDM server, with the stock game QVM. And prove the
lifecycle edges the review asked about: admin kicks, botlib bots taking a freed
slot, map rotation, server restart, sidecar death.

This is the first gate of the RL-bot port (`knecht-q3-bot` / BobbyBones): if
per-frame external driving doesn't work, the port needs a different architecture.

## Design (V2 = review rework, branch `botctl-spike`)

- **Engine patch** (Quake3e, off `dwc` tip `8fa5549e`; commit stack
  `7d3932ce` (v1) → `21a35999` (build gating) → `a7dae3fc` (review fixes)
  → `ef9820ab`/`dbed1dd8`/`054019ce` (review round 2); 6 files):
  - **Gating**: Makefile `USE_BOTCTL = 0` by default; only a non-mingw
    dedicated build with `USE_BOTCTL=1` compiles `-DUSE_BOTCTL`, links
    `ded/botctl.o` and `-lpthread`. `server.h` declares the hooks only under
    `#if defined(USE_BOTCTL) && defined(DEDICATED)` — every other config
    (client builds, mingw) gets no-op macros, so stock builds can neither
    mis-declare nor mis-link the channel. `USE_BOTCTL=0` objects are
    **byte-identical** to the parent commit (verified against `8fa5549e`).
  - `code/server/botctl.c` — UDS listener thread, default socket
    `fs_homepath/botctl-<net_port>.sock` (chmod 0600, `botctl_sockpath`
    overrides), binary protocol (PING/ADD/REMOVE/TEXT/CMD/SNAP/LIST),
    per-client staged usercmd queue, listener log queue drained on the
    server thread, request-sequence generation (no stale replies after a
    timeout), `SO_RCVTIMEO`/`SO_SNDTIMEO` so `pthread_join` can't hang.
  - `SV_RunFrame` hooks: `Botctl_Frame()` BEFORE `GAME_RUN_FRAME` (replay
    staged cmds, K/frame spread evenly = substeps) + `Botctl_Snapshot()` AFTER
    (dump reflects the frame that just ran).
  - `SV_MapRestart_f`: managed clients reconnect as regular players
    (`Botctl_IsManaged` → `isBot=qfalse`, then `SV_ClientEnterWorld` — the
    packetless clients have no gamestate handshake). TDM `map` rotations run
    `SV_SpawnServer(killBots=qfalse)`, so managed slots **survive** rotation.
  - `Botctl_ClientDropped()` hooked into `SV_DropClient` + `SV_BotFreeClient`:
    whenever the engine drops a managed client (kick, timeout, `killBots`,
    inactivity), the management state is cleared — no phantom auto-ACK /
    injected usercmds for the next occupant of the slot.
  - `Botctl_Shutdown` (called by `SV_Shutdown`): listener down, socket
    unlinked, managed clients dropped, enable state reset → the 12 h
    `SV_Restart` cycle (`SV_Shutdown` + `map`) re-arms the channel.
  - Per-frame reliable-command ACK + `lastPacketTime` refresh for the
    packetless managed clients (mirrors `SV_BotGetConsoleMessage` for engine
    bots; without it: "Server command overflow" drop in ~1 min, `sv_timeout`
    after 200 s).
  - Reply-send semantics (review round 2): every reply send checks its
    result; a failure (`SO_SNDTIMEO` timeout or gone socket — the peer
    stopped consuming) closes the connection instead of continuing with
    silently dropped replies on a stream that can no longer be framed
    correctly. A failed send then uses the SAME path as a sidecar crash
    (`s_sidecar_lost` → managed clients dropped). Covered by T9.
- **Protocol**: snapshot = `u32 time, u32 restart_id, u16 np, u16 ne` +
  player blobs (132 B: client, origin[3], health, armor, weapon, weaponstate,
  team, score, viewangles[3], delta_angles[3], pm_type, ammo[16]) + entity
  blobs (52 B, taken live from `sv.num_entities` after the game frame).
- **Sidecar** (this repo, branch `spike-q3e-botctl`, `spike/`): stdlib-Python
  `botctl.py` (protocol client) + `sidecar.py` (T1–T9 brains) + `run_spike.sh`
  (driver: FIFO stdin, fresh home, TDM cvars, port 28133, TERM→KILL cleanup).

## Test matrix & results

Test instance: knecht, port 28133, fresh home `~/.q3a_spike`, V2 spike engine
(`quake3e.ded.x64` md5 `c06bc7c6…`, `USE_BOTCTL=1`, review-round-2 fixes),
stock OSP **dwc.4** QVM, TDM `q3dm7` (`g_gametype 3`), 20 fps, 30 s warmup.

| # | Test | Result | Measured (final4 run 2026-11-16, all 11 scenarios in one session) |
|---|------|--------|----------------------------------------------------------------------|
| T1 | slot lifecycle (add/list/connect/join/remove/freed/readd) | **PASS** | `list=True connect=True joined=True team=red remove=1 freed=True readd=0` |
| T2 | scripted movement — best straight window over a 4-direction sweep | **PASS** | window 0.40 s: **321.6 u/s**, dot 1.000, travel 128 u, yaw 270 (spawn probe 282 u/s, spawns=1) |
| T3 | substep replay 1 vs 4 cmds/frame | **PASS** | sub1 **321.9 u/s** (dot 1.000, yaw 90) vs sub4 **322.1 u/s** (dot 1.000, yaw 270), **ratio 1.00** |
| T4 | world state + firing (up to 6 fresh-spawn pickup tries, stuck-aware) | **PASS** | items 53 visible; try 2: dist 285 u, item vanished under the bot (graze sweep); MG ammo 50→37 + FIRING state seen (health 124→110 = spawn DoT, not a criterion) |
| T5 | TDM warmup → match start | **PASS** | red+blue join + `say ready`, match started after 15.3 s, alive after the in-place `map_restart` |
| T5b | real map rotation (`rcon map ospdm6`) | **PASS** | restart_id 5027→7019, managed slots [0, 1] intact, both alive + drivable (distinctive viewangle test) |
| T5c | `killserver` → `map q3dm7` restart cycle | **PASS** | socket gone + `Server Shutdown` in the rcon answer, socket recreated, LIST empty, re-ADD on slot 0 + team join |
| T6 | 10-min random-action soak + clean SIGTERM | **PASS** | 600 s/600 s, 10,002 snapshots, 0.0 s dead-time (this run's random walks stayed out of the pit; channel alive + drivable throughout) |
| T7 | `clientkick <slot>` → `addbot dwcbot1 5 red` reuses the slot | **PASS** | kicked slot 0 → botctl LIST clears engine-side → addbot takes the same slot → LIST stays empty |
| T8 | sidecar crash → engine drops + keeps listening | **PASS** | `list_empty=True player_gone=True readd_after_reconnect=True` |
| T9 | stalled reader (review round 2): unanswered SNAP flood → send must fail → engine closes the connection | **PASS** | 132 unanswered SNAP requests flooded → engine closed the connection (no dropped-reply stream), dropped managed clients (`bot control connection lost`), rcon `status` still answered, LIST empty, re-ADD after reconnect |

All 11 scenarios PASS in the final4 run; engine alive at every scenario end,
`SERVER_EXIT=0`.

### Measurement notes (how the gates became trustworthy)

- **Spawn probe + reroll** (`spawn_drivable`): q3dm7 team spawns are random
  per ADD, and some face a wall/corridor. The sidecar probes 0.35 s of
  full-speed walking in the four cardinal yaws — that **average is a
  close-wall detector**: from standing an unobstructed bot covers ~90 u by
  0.35 s (260–300 u/s), a wall at 120 u truncates the average to ~230 →
  REMOVE+re-ADD rerolls the spawn (up to 4 tries, then a best-effort fresh
  ADD). Do NOT lengthen the probe: at 0.5 s the four-direction turnaround
  momentum dominates the average — 2026-11-16 measured the same 293 u/s on
  every spawn regardless of geometry, making a 300 gate unpassable. And no
  "pre-hold" along the chosen yaw: the probe already walks the bot ~90 u into
  the corridor; a further hold just pins it early against the far wall.
- **T2/T3 scoring** (`hold_and_measure` + `sweep_straight`): each hold scores
  the best **STRAIGHT** ~0.5 s window (direction dot ≥ 0.95), not a
  fixed-window average (measures spawn geometry) and not the fastest window
  regardless of direction (measures wall-following — a sub4 run once clocked
  301.9 u/s at dot 0.559 rounding a corner). The measurement **sweeps all
  four cardinal yaws (2 s each) on the same spawn** and takes the best window;
  only a spawn whose whole sweep misses the gate is rerolled. Why: the spawn
  probe walks the bot ~100 u into the corridor it just measured, so a
  borderline spawn (wall ~175 u ahead, probe 283 u/s) leaves the hold one
  short truncated window (once 254.6 u/s over 0.30 s) — sweeping finds the
  direction that is actually open, without any world-geometry knowledge.
  Gates: rate ≥ 260 u/s AND dot ≥ 0.99; T3 also requires the sub1/sub4 ratio
  ≥ 0.85 (substeps must not distort achieved speed).
- **Sidecar pacing**: plain `sleep(1/hz)` + cmd + snap overshoots the 50 ms
  engine frame budget (scheduler + UDS latency) → the staged queue empties →
  `Botctl_RunClient` injects its idle cmd (the bot stands a beat). That skewed
  early T3 sub1 peaks to 267–272 u/s. All movement loops pace against absolute
  deadlines; T3 stages at 24/96 Hz (the queue absorbs the surplus, the 4×
  factor between sub1/sub4 is preserved).
- **T4 pickup** re-ADDs the bot per attempt (up to 6): a re-ADD rerolls a
  fresh team spawn, and the candidate is the top item ranked from that fresh
  position over ALL dumped items (2-D distance + 1.5×|dz| height penalty; no
  radius filter — after a failed walk the bot sits where no item is nearby,
  and a filter would end the loop at tries=1). `brain_toward` has stuck
  handling (< 24 u progress in 2 s → alternating back-up/sidestep, give up
  after 5 events) and a **z guard**: abort when the bot is > 80 u below the
  item (the q3dm7 red base drops ~450 u into a pit that a walking bot cannot
  climb out of — earlier runs judged every later candidate from the pit), and
  "reached" requires |dz| ≤ 40 (2-D above an item on another level is not a
  pickup). After "reached" a 3 s **graze sweep** (turn while walking) crosses
  the spot from all directions — reached=True without the item vanishing once
  happened at dz +148 (item on a platform overhead). Some q3dm7 spawns simply
  cannot walk to their nearest item. Item vanishing under the bot is the
  pickup signal; a health rise is NOT required (may be armor; DoT near the
  q3dm7 red spawn lowers health regardless).
- **T7 uses `addbot dwcbot1 5 red`**: the dwc botfiles define only a `skill 5`
  personality block; skill 4 makes botlib load the default personality and
  abort — visible only in the rcon answer (the rcon redirect swallows that
  output), which the sidecar logs on failure.
- **RCON log expectations**: the rcon redirect (`Com_BeginRedirect`) swallows
  the executed command's console output — `Server Shutdown (killserver)` and
  the `map` output land in the **rcon answer**, never in the server log. So
  T5c asserts the shutdown line from the rcon answer, and the T5b log check
  is negative-only (no wrongful `management cleared` line).

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
   "(re)start happened" signal. Snapshots include ALL `CS_ACTIVE` clients —
   botlib bots (from `addbot`) show up too; `LIST` only ever lists botctl
   clients (T7 proves botctl never hijacks a botlib bot).
4. **Packetless clients need ACK upkeep** (reliable commands + lastPacketTime)
   or the engine drops them (~1 min / 200 s).
5. **TDM warmup resets when a team goes empty** — test bots must stay in their
   teams until the match actually starts; expiry = in-place `OSP_MapRestart`.
6. JIT "compiled to N bytes" is **not** a QVM fingerprint (prod and clean both
   825,400).
7. **RCON wire format**: connectionless packets need the **four-byte** 0xff
   marker — `SV_PacketEvent` tests `*(int32_t*)msg->data == -1`, a two-byte
   marker is silently dropped; replies are `NET_OutOfBandPrint` (prepends the
   same four bytes): `\xff\xff\xff\xffprint\n<text>`. Cvar name is
   `rconPassword`; rate limit 10/s.
8. **`killserver` is rcon-able even though `SV_Frame` blocks**: after
   shutdown `Sys_Sleep(-1)` loops on `NET_Sleep`, which still dispatches UDP
   packets into `SV_PacketEvent` (`NET_Event → Com_RunAndTimeServerPacket`),
   and `SV_Shutdown` keeps `ip_socket` open — an rcon `map` wakes the server.
9. **TDM `map` does NOT kill bots** (`SV_SpawnServer(killBots=qfalse)`): botlib
   and managed clients reconnect through `SV_MapRestart_f`. The engine's 12 h
   `SV_Restart` is the shutdown/reinit path (T5c).
10. **A failed reply send IS a broken connection** (n4cer review round 2): with
    `SO_SNDTIMEO` set, `send()` can time out on a peer that stopped reading —
    continuing then drops replies on a half-sent frame, desyncing the stream
    and hanging a request/response sidecar. The handler closes the connection
    and reuses the sidecar-crash drop path. T9 reproduces it permanently: ~130
    unanswered ~3 kB SNAP dumps (~400 kB) fill the UDS buffers, the engine's
    send hits the 500 ms timeout → close + managed clients dropped.

## Go / No-Go

**GO.** An external process can drive a client slot per-frame on the production
engine+QVM with stock behavior: full run speed, substeps, state reads (incl.
items + ammo + firing), team/warmup/match flow, map rotation survival,
kick/addbot/restart/sidecar-death/stalled-reader lifecycle edges, and
multi-minute stability.
No engine-side limitations surfaced that would block the port.

## Next (Phase 1: sim parity)

- Rebuild BobbyBones `libqsim` from Quake3e sources (Q3A/OSP settings,
  sv_fps 40 → substep 3), parity audit vs the real server (their
  `tools/phys_compare.py` / `sim/validate.py`), nav data for the 8 TDM maps.
- Land PR #13 (base `dwc` or a feature branch — pending Micha's call, see the
  PR reply).
- Before Phase 3 (training): vLLM TP=2 → single GPU (user action) per the GPU
  compromise.

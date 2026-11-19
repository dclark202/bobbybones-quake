#!/usr/bin/env python3
"""
sidecar.py -- the spike "brain": drives one bot slot in a Quake3e + OSP
server through the botctl Unix socket and runs the T1-T10 spike scenarios.

Usage:
  python3 sidecar.py --port 28133 --scenario t2 --botname SpikeBot [--team red]
                     [--hz 100] [--seconds 10] [--verbose]

Scenarios (each prints a PASS/FAIL line and exits 0/1):
  t1  slot lifecycle: add -> appears in LIST + SNAP (spawns, gets a team in
      TDM) -> remove -> slot freed. (scoreboard/kick covered via server log)
  t2  scripted movement: hold forward along all four cardinal yaws (2 s
      each); the best STRAIGHT ~0.5 s window must hit run speed (~320 u/s).
      Only a spawn whose whole four-direction sweep misses is rerolled.
  t3  substeps: two runs (1 cmd/frame vs 4 cmds/frame, same total input
      time), each sweeping the four yaws; the best straight-window rates
      must match (physics is substep-driven).
  t4  world state: verify items are present in the entity dump; walk into
      a reachable item (up to 6 fresh-spawn tries, stuck-aware brain_toward)
      and verify it vanishes under the bot; firing via MG ammo decrement.
  t5  warmup: bot must be ready-able via TEXT "ready"; the driver checks
      the server log for the match-start line (see run_spike.sh).
  t5b real map rotation (rcon map ospdm6; TDM killBots=qfalse): managed
      clients must SURVIVE via the SV_SpawnServer reconnect path (V2:
      isBot=qfalse + SV_ClientEnterWorld), LIST intact, drivable on the
      new map.
  t5c killserver -> map (the SV_Shutdown + "map" cycle of the 12 h
      SV_Restart): socket must go down with the shutdown, come back after
      the restart (enable-flag re-arm), LIST empty, re-ADD works.
  t6  soak: random-walk + occasional fire for N seconds (default 600);
      PASS = no engine crash (socket alive) the whole time.
  t7  admin kick (rcon clientkick <slot>) followed by a stock bot joining
      that slot (rcon addbot dwcbot1 5 red -- the dwc botfiles define only a
      skill-5 block): management state must clear on its own (LIST empty,
      stays empty), and the addbot bot must land on the same slot.
  t8  sidecar crash: closing the connection without REMOVE must make the
      engine drop its managed clients and keep listening (fresh connection
      sees LIST empty, old player gone, can ADD again).
  t9  stalled reader (review round 2): flood SNAP requests without reading
      any reply until the engine's SO_SNDTIMEO send fails -- the engine must
      CLOSE the connection (never continue with dropped replies), drop its
      managed clients, stay responsive (rcon), and accept a fresh
      connection + ADD (LIST empty).
  t10 close-during-reply / SIGPIPE (review round 3): send a SNAP request
      and close the connection ~10 ms later, while the reply is in flight.
      Without MSG_NOSIGNAL/SO_NOSIGPIPE the engine's send() raises SIGPIPE
      and the WHOLE server dies (exit 141). PASS = after 10 such tries the
      engine still answers rcon status and keeps the socket listening.

Stdlib only. Talks to the engine socket <fs_homepath>/botctl-<port>.sock
(see botctl.sockpath_for_port; the spike runs use ~/.q3a_spike).
"""

import argparse
import math
import os
import random
import signal
import socket
import struct
import sys
import time

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from botctl import (
    Botctl, Snapshot, sockpath_for_port,
    BUTTON_ATTACK,
    OP_SNAP, _send_frame,     # raw send for the T9 stalled-reader flood
    WP_MACHINEGUN,          # this OSP build's spawn weapon (no blaster; 1=GAUNTLET)
    WEAPON_FIRING,          # ==3 in this build (NOT 1)
    PM_NORMAL, PM_DEAD,
    TEAM_RED, TEAM_BLUE,
)

TEAM_NAMES = {0: "none", 1: "red", 2: "blue", 3: "spec"}   # OSP team_t order


# ------------------------------------------------------------------ helpers
def log(msg: str, verbose_only: bool = False, verbose: bool = False):
    if verbose_only and not verbose:
        return
    print(f"[{time.strftime('%H:%M:%S')}] {msg}", flush=True)


def rcon(args, command: str, timeout: float = 3.0) -> str:
    """One RCON command over UDP. q3e handles rcon CONNECTIONLESS: the
    marker is FOUR 0xff bytes (SV_PacketEvent tests *(int32_t*)msg->data
    == -1; a 2-byte marker is silently dropped), then 'rcon <pass> <cmd>\\0'.
    Replies come back the same way: NET_OutOfBandPrint also prepends four
    0xff bytes, so a reply packet is '\\xff\\xff\\xff\\xffprint\\n<text>'
    (sv_main.c SVC_RemoteCommand + SV_FlushRedirect). Keep rcon calls per
    scenario few: SVC_RateLimitAddress rate-limits them."""
    import socket as _socket
    s = _socket.socket(_socket.AF_INET, _socket.SOCK_DGRAM)
    s.settimeout(timeout)
    s.bind(("127.0.0.1", 0))
    payload = (b"\xff\xff\xff\xffrcon " + args.rconpass.encode()
               + b" " + command.encode() + b"\x00")
    s.sendto(payload, (args.rconhost, args.port))
    chunks = []
    try:
        while True:
            data, _ = s.recvfrom(4096)
            body = data.lstrip(b"\xff")          # the marker is 4x 0xff
            if body.startswith(b"print"):
                chunks.append(body[len(b"print"):].decode(errors="replace").lstrip("\n"))
            else:
                break
    except _socket.timeout:
        pass
    s.close()
    return "".join(chunks)


def wait_for_connect(bc: Botctl, slot: int, timeout: float) -> bool:
    """Wait until the bot has a live playerState (connected, any team)."""
    t0 = time.time()
    while time.time() - t0 < timeout:
        snap = bc.snap()
        if snap.player(slot) is not None:
            return True
        time.sleep(0.2)
    return False


def join_team(bc: Botctl, slot: int, team: str, timeout: float = 15.0) -> bool:
    """Join a team the human way: TEXT 'team red|blue' (OSP SetTeam).
    The userinfo 'team' key is only honored for SVF_BOT clients."""
    r = bc.text(slot, f"team {team}")
    log(f"TEXT 'team {team}' as client {slot} -> {r}")
    want = TEAM_RED if team.lower() in ("red", "r") else TEAM_BLUE
    t0 = time.time()
    while time.time() - t0 < timeout:
        p = bc.snap().player(slot)
        if p and p["team"] == want:
            return r == 1
        time.sleep(0.2)
    return False


def wait_for_alive(bc: Botctl, slot: int, timeout: float) -> bool:
    t0 = time.time()
    while time.time() - t0 < timeout:
        snap = bc.snap()
        p = snap.player(slot)
        if p and p["health"] > 0:
            return True
        time.sleep(0.2)
    return False


def dist2d(a, b) -> float:
    return math.hypot(a[0] - b[0], a[1] - b[1])


def norm2d(x, y):
    n = math.hypot(x, y)
    if n < 1e-6:
        return 0.0, 0.0
    return x / n, y / n


def fwd_right_from_yaw(yaw_deg: float):
    """World-space unit vectors for Q3 yaw (0 = +x, 90 = +y)."""
    r = math.radians(yaw_deg)
    return (math.cos(r), math.sin(r)), (-math.sin(r), math.cos(r))


def choose_clear_yaw(bc: Botctl, slot: int, hz: float, verbose: bool = False):
    """Spawn facing on q3dm7 is random -- a full-speed hold may walk straight
    into a wall (spawn luck, not a channel bug; this bit us on 2026-11-16:
    rate 49-165 u/s on 1 s averages even along the probed best yaw). Probe
    0.35 s of forward walking in the four cardinal world-yaw directions and
    return the clearest one; spawn_drivable() gates on the rate. The 0.35 s
    AVERAGE is a close-wall detector: from standing, an unobstructed bot
    covers ~90 u by 0.35 s (~260-300 u/s); a wall at 120 u truncates the
    average to ~230 -> reroll. (Do NOT lengthen the probe: at 0.5 s the
    four-direction turnaround momentum dominates -- 2026-11-16 measured
    293 u/s on EVERY spawn regardless of geometry, making any gate ~300
    unpassable.)"""
    best_yaw, best_rate = 0.0, -1.0
    for yaw in (0.0, 90.0, 180.0, 270.0):
        p0 = bc.snap().player(slot)
        if not p0:
            continue
        start = p0["origin"]
        t0 = time.time()
        t_next = t0
        while time.time() - t0 < 0.35:
            bc.cmd(slot, 127, 0, 0, 0, WP_MACHINEGUN, 0.0, yaw)
            # absolute-deadline pacing: plain sleep(1/hz) overshoots
            # (scheduler + UDS latency) and starves the engine queue -> an
            # idle cmd frame (bot stands a beat). 2026-11-16 T3: sub1 peaks
            # landed at 267-272 u/s this way, ratio skewed to 0.83-0.84.
            t_next += 1.0 / hz
            if t_next > time.time():
                time.sleep(t_next - time.time())
        p1 = bc.snap().player(slot)
        if not p1:
            continue
        d = math.hypot(p1["origin"][0] - start[0], p1["origin"][1] - start[1])
        rate = d / max(time.time() - t0, 1e-6)
        log(f"probe yaw {yaw:.0f}: {d:.0f}u ({rate:.0f}u/s)", verbose_only=True, verbose=verbose)
        if rate > best_rate:
            best_rate, best_yaw = rate, yaw
        time.sleep(0.2)
    return best_yaw, best_rate


def hold_and_measure(bc: Botctl, slot: int, yaw: float, hz: float,
                     hold: float = 2.0, win: float = 0.5):
    """Hold fwd=127 along `yaw` for `hold` s, sampling the origin at hz, and
    return the best (rate, dir_dot, distance, window_len) over windows of
    ~win seconds that are STRAIGHT (direction dot >= 0.95): the claim to
    prove is "there is a full-rate straight run along the commanded yaw".
    A fixed-window average measures the spawn geometry (a wall 130-165 u
    ahead truncates it); a curving window measures wall-following, not the
    channel (2026-11-16 sub4: rate 301.9 with dot 0.559 -- the bot rounded a
    corner at speed). If no straight window exists, the overall fastest
    window is returned so the FAIL detail shows what actually happened."""
    samples = []
    t0 = time.time()
    t_next = t0
    while time.time() - t0 < hold:
        bc.cmd(slot, 127, 0, 0, 0, WP_MACHINEGUN, 0.0, yaw)
        p = bc.snap().player(slot)
        if p:
            samples.append((time.time() - t0, p["origin"][0], p["origin"][1]))
        t_next += 1.0 / hz
        if t_next > time.time():          # deadline pacing, see choose_clear_yaw
            time.sleep(t_next - time.time())
    fx, fy = fwd_right_from_yaw(yaw)[0]
    best = (0.0, 0.0, 0.0, 0.0)           # fastest overall (fallback detail)
    best_straight = (0.0, 0.0, 0.0, 0.0)
    for i in range(len(samples)):
        ti, xi, yi = samples[i]
        for j in range(i + 1, len(samples)):
            tj, xj, yj = samples[j]
            dt = tj - ti
            if dt < win * 0.5 or dt > win * 2.0:
                continue
            dx, dy = xj - xi, yj - yi
            d = math.hypot(dx, dy)
            rate = d / dt
            if rate > best[0]:
                best = (rate, (dx * fx + dy * fy) / max(d, 1e-6), d, dt)
            dot = (dx * fx + dy * fy) / max(d, 1e-6)
            if dot >= 0.95 and rate > best_straight[0]:
                best_straight = (rate, dot, d, dt)
    return best_straight if best_straight[0] > 0 else best


def sweep_straight(bc: Botctl, slot: int, yaw0: float, hz: float,
                   hold: float = 2.0, win: float = 0.5, min_rate: float = 260.0):
    """hold_and_measure along the spawn probe's yaw first, then the other
    three cardinal yaws; return ((rate, dot, dist, dt, yaw), passed) for the
    best STRAIGHT window found, stopping early once the gate is met. This
    removes the probe-vs-hold mismatch: the probe walks the bot ~100 u INTO
    the corridor it just measured, so a borderline spawn (wall ~175 u, probe
    average 283) leaves the hold only a short truncated straight window
    (2026-11-16 T2: 254.6 u/s over 0.30 s). Scoring all four directions on
    the same spawn keeps the spawn random (a boxed spawn still has open
    directions) and needs no world-geometry knowledge. Turnaround transients
    are excluded by the straight (dot) filter itself."""
    yaws = [yaw0] + [y for y in (0.0, 90.0, 180.0, 270.0) if y != yaw0]
    best = (0.0, 0.0, 0.0, 0.0, yaw0)
    for y in yaws:
        r, d, di, dt = hold_and_measure(bc, slot, y, hz, hold, win)
        if r > best[0]:
            best = (r, d, di, dt, y)
        if best[0] >= min_rate and best[1] >= 0.99:
            return best, True
    return best, False


def spawn_drivable(bc: Botctl, args, suffix: str, verbose: bool = False,
                   gate: float = 260.0, max_spawns: int = 4):
    """ADD + connect + team join + probe; returns (slot, yaw, probe_rate).
    If every cardinal probe stays below `gate` u/s (0.35 s average -> see
    choose_clear_yaw) the spawn is boxed in: REMOVE + re-ADD rerolls the team
    spawn point (random pick) and probes again, up to max_spawns tries. If all
    tries stay boxed, one final fresh ADD is returned best-effort (never a
    REMOVED slot -- a hold on a removed client measures 0.0 and looks like an
    engine bug; that is exactly what the 2026-11-16 gate-300 experiment
    produced). Slot -1 only when ADD/connect/join itself failed. No pre-hold:
    the probe already walks the bot ~90 u toward the corridor; an extra hold
    along the chosen yaw just presses the bot into the far wall early
    (2026-11-16: straight window 0.0 u/s on a gate-passing spawn)."""
    slot, yaw, rate = -1, 0.0, -1.0
    for attempt in range(1, max_spawns + 1):
        slot = bc.add(args.botname + suffix, args.team)
        if slot < 0:
            return -1, 0.0, -1.0
        if not wait_for_connect(bc, slot, 20.0) or not join_team(bc, slot, args.team or "red"):
            bc.remove(slot)
            time.sleep(0.5)
            continue
        time.sleep(1.0)  # spawn settle (knockback + DoT)
        yaw, rate = choose_clear_yaw(bc, slot, 20.0, verbose=verbose)
        if rate >= gate:
            return slot, yaw, rate
        log(f"spawn {attempt} boxed in (best probe {rate:.0f}u/s) -> reroll")
        bc.remove(slot)
        time.sleep(1.0)
    # best-effort fresh spawn so the caller always gets a live slot
    slot = bc.add(args.botname + suffix, args.team)
    if slot >= 0 and (wait_for_connect(bc, slot, 20.0) and join_team(bc, slot, args.team or "red")):
        time.sleep(1.0)
        return slot, yaw, rate
    return -1, 0.0, -1.0


def result(name: str, ok: bool, detail: str = "") -> int:
    print(f"RESULT {name}: {'PASS' if ok else 'FAIL'} {detail}", flush=True)
    return 0 if ok else 1


# ------------------------------------------------------------------ brains
def brain_hold(bc: Botctl, slot: int, dur: float, hz: float,
               fwd=127, right=0, up=0, buttons=0, weapon=WP_MACHINEGUN,
               yaw_step=0.0, verbose=False):
    """Hold a fixed movement input at hz Hz for dur seconds. Returns
    (start_origin, end_origin, end_yaw)."""
    snap = bc.snap()
    p0 = snap.player(slot)
    start = p0["origin"]
    yaw = p0["viewangles"][1]
    n = int(dur * hz)
    dt = 1.0 / hz
    for i in range(n):
        bc.cmd(slot, fwd, right, up, buttons, weapon, 0.0, yaw)
        yaw += yaw_step
        time.sleep(dt)
    snap = bc.snap()
    p1 = snap.player(slot)
    return start, p1["origin"], p1["viewangles"][1]


def brain_toward(bc: Botctl, slot: int, target_xy, hz: float, max_time: float,
                 yaw_step=0.0, verbose=False, target_z=None):
    """Steer toward a 2-D point (optional z for the sanity checks). Returns
    (reached: bool, start, end).
    Stuck handling (2026-11-16 T4): if less than 24 u of 2-D progress in 2 s
    of walking, alternate back-up (odd events) / sidestep (even) for 0.8 s;
    give up after 5 stuck events (railing/ledge -- some q3dm7 items are not
    walk-reachable from a random spawn at all).
    Z guard (2026-11-16 T4: the bot walked off the red-base ledge ~450 u down
    into the pit and every later candidate was judged from there): give up on
    this candidate as soon as the bot is > 80 u BELOW the target z -- a
    walking bot cannot climb that back out. 'reached' also requires |dz| <= 40
    (standing 2-D above an item on a lower/upper level is not a pickup)."""
    snap = bc.snap()
    p0 = snap.player(slot)
    start = p0["origin"]
    yaw = p0["viewangles"][1]
    t0 = time.time()
    last = start
    t_next = t0
    stuck = 0
    anchor_t, anchor_pos = t0, start
    unstick_until = 0.0
    while time.time() - t0 < max_time:
        snap = bc.snap()
        p = snap.player(slot)
        if not p:
            time.sleep(0.05)
            continue
        ox, oy, oz = p["origin"]
        yaw = p["viewangles"][1]
        now = time.time()
        if target_z is not None and oz < target_z - 80.0:
            log(f"brain_toward: bot at z {oz:.0f}, target z {target_z:.0f} "
                f"-> fell off, abort")
            return False, start, last
        if unstick_until > now:
            # alternate: back up, then sidestep around the obstacle
            if stuck % 2 == 1:
                bc.cmd(slot, -127, 0, 0, 0, WP_MACHINEGUN, 0.0, yaw)
            else:
                side = 127 if (stuck // 2) % 2 == 1 else -127
                bc.cmd(slot, 30, side, 0, 0, WP_MACHINEGUN, 0.0, yaw)
        else:
            fx, fy = norm2d(target_xy[0] - ox, target_xy[1] - oy)
            # project the world target direction onto the view's fwd/right
            (fdx, fdy), (rdx, rdy) = fwd_right_from_yaw(yaw)
            fwd = fx * fdx + fy * fdy
            right = fx * rdx + fy * rdy
            fwd_i = int(max(-127, min(127, round(fwd * 127))))
            right_i = int(max(-127, min(127, round(right * 127))))
            bc.cmd(slot, fwd_i, right_i, 0, 0, WP_MACHINEGUN, 0.0, yaw + yaw_step)
            if now - anchor_t >= 2.0:
                if dist2d((ox, oy), anchor_pos) < 24.0:
                    stuck += 1
                    log(f"brain_toward stuck event {stuck} at ({ox:.0f},{oy:.0f}) "
                        f"-> {'back up' if stuck % 2 == 1 else 'sidestep'}")
                    if stuck >= 5:
                        return False, start, last
                    unstick_until = now + 0.8
                anchor_t, anchor_pos = now, (ox, oy)
        last = p["origin"]
        if dist2d((ox, oy), target_xy) < 24.0 and (target_z is None
                                                   or abs(oz - target_z) <= 40.0):
            return True, start, last
        t_next += 1.0 / hz
        if t_next > time.time():          # deadline pacing, see choose_clear_yaw
            time.sleep(t_next - time.time())
    return False, start, last


# ---------------------------------------------------------------- scenarios
def wait_in_team(bc: Botctl, slot: int, timeout: float) -> bool:
    t0 = time.time()
    while time.time() - t0 < timeout:
        p = bc.snap().player(slot)
        if p and p["team"] in (TEAM_RED, TEAM_BLUE):
            return True
        time.sleep(0.2)
    return False


def t1(bc: Botctl, args) -> int:
    name = f"T1 {args.botname}"
    slot = bc.add(args.botname, args.team)
    if slot < 0:
        return result(name, False, "ADD failed (no free slot?)")
    log(f"added as client {slot}")
    time.sleep(1.0)

    lst = bc.list()
    in_list = any(n == slot for n, _, _ in lst)

    connected = wait_for_connect(bc, slot, 20.0)
    # join like a human (the 'team' userinfo key is bot-only in OSP)
    joined = join_team(bc, slot, args.team or "red") if args.team \
        else wait_in_team(bc, slot, 15.0)
    snap = bc.snap()
    p = snap.player(slot)
    team_ok = bool(p and p["team"] in (TEAM_RED, TEAM_BLUE))

    # remove must free the slot
    rm = bc.remove(slot)
    time.sleep(0.5)
    slot_free = True
    try:
        snap2 = bc.snap()
        if snap2.player(slot) is not None:
            slot_free = False
    except Exception:
        pass
    # a re-add should now work (same or another slot)
    slot2 = bc.add(args.botname + "2", args.team)
    ok = in_list and connected and joined and team_ok and rm == 1 and slot_free and slot2 >= 0
    if slot2 >= 0:
        bc.remove(slot2)
    detail = (f"list={in_list} connect={connected} joined={joined} team="
              f"{TEAM_NAMES.get(p['team'] if p else -1, '?')} remove={rm} "
              f"freed={slot_free} readd={slot2}")
    return result(name, ok, detail)


def drive_best_window(bc: Botctl, args, hz: float, suffix: str = "",
                      verbose: bool = False, max_spawns: int = 3):
    """T2/T3 core: spawn (spawn_drivable without rerolls -- the sweep covers
    all four directions anyway), sweep_straight over the four cardinal yaws,
    and only if the WHOLE sweep misses the gate reroll the spawn (up to
    max_spawns). Returns (slot, (rate, dot, dist, dt, yaw), probe, spawns);
    slot is still live on a pass (caller removes)."""
    slot = -1
    probe = -1.0
    best = (0.0, 0.0, 0.0, 0.0, 0.0)
    used = 0
    for s in range(max_spawns):
        sl, yaw, pr = spawn_drivable(bc, args, suffix, verbose=verbose,
                                    gate=-1.0, max_spawns=1)
        if sl < 0:
            continue
        used = s + 1
        probe = max(probe, pr)
        best, passed = sweep_straight(bc, sl, yaw, hz)
        if passed:
            return sl, best, probe, used
        log(f"spawn {used}: no straight window >= 260 u/s in any yaw -> reroll")
        bc.remove(sl)
        time.sleep(1.0)
    return -1, best, probe, used


def t2(bc: Botctl, args) -> int:
    """T2: scripted movement. drive_best_window: hold fwd=127 along every
    cardinal yaw (2 s each), hold_and_measure scores the best straight ~0.5 s
    window -- the channel must produce straight run-speed movement (~320 u/s)
    no matter where the random team spawn faces; only a spawn whose whole
    four-direction sweep misses the gate is rerolled (re-ADD)."""
    name = "T2 movement"
    slot, (rate, dot, dist, dt, yaw), probe, used = drive_best_window(bc, args, args.hz)
    if slot >= 0:
        bc.remove(slot)
    ok = rate >= 260.0 and dot >= 0.99
    return result(name, ok,
                  f"best window {dt:.2f}s: rate={rate:.1f}u/s dir_dot={dot:.3f} "
                  f"travel={dist:.1f}u yaw={yaw:.0f} (spawn probe {probe:.0f}u/s, "
                  f"spawns={used})")


def t3(bc: Botctl, args) -> int:
    """T3: substeps. Stage 1 vs 4 identical fwd cmds per engine frame (sidecar
    at 24 vs 96 Hz); drive_best_window sweeps the four cardinal yaws per spawn
    and the best straight window of each run is compared. Multi-cmd replay
    that drops or clumps inputs shows up as a rate spread; both must reach
    full run speed along some commanded direction."""
    name = "T3 substeps"

    def run(substeps: int):
        # stage at 24 Hz * substeps (slightly over the 20 fps engine): with a
        # plain 20 Hz cadence every scheduler/UDS overshoot starves the staged
        # queue -> Botctl_RunClient injects its idle cmd for that frame (bot
        # stands a beat) -- that skewed sub1 peaks to 267-272 u/s on
        # 2026-11-16. The queue absorbs the surplus (identical cmds, no
        # physics difference); the 4x factor between stages is preserved.
        slot, (rate, dot, dist, dt, yaw), probe, used = drive_best_window(
            bc, args, 24.0 * substeps, verbose=args.verbose)
        if slot >= 0:
            bc.remove(slot)
        time.sleep(2.0)  # let the slot free + world settle between runs
        return rate, dot, dt, yaw, used

    rate1, dot1, dt1, yaw1, used1 = run(1)
    rate4, dot4, dt4, yaw4, used4 = run(4)
    ratio = min(rate1, rate4) / max(rate1, rate4) if max(rate1, rate4) > 0 else 0.0
    ok = (rate1 >= 260.0 and rate4 >= 260.0
          and dot1 >= 0.99 and dot4 >= 0.99
          and 0.85 <= ratio <= 1.2)
    detail = (f"best straight rate(sub1)={rate1:.1f}u/s dot={dot1:.3f} "
              f"yaw={yaw1:.0f} spawns={used1} | "
              f"rate(sub4)={rate4:.1f}u/s dot={dot4:.3f} yaw={yaw4:.0f} "
              f"spawns={used4} | ratio={ratio:.2f}")
    return result(name, ok, detail)


def t4(bc: Botctl, args) -> int:
    name = "T4 world state"
    slot = bc.add(args.botname, args.team)
    if slot < 0:
        return result(name, False, "ADD failed")
    if not wait_for_connect(bc, slot, 20.0):
        bc.remove(slot)
        return result(name, False, "no connect")
    if not join_team(bc, slot, args.team or "red"):
        bc.remove(slot)
        return result(name, False, "no team join")
    time.sleep(1.0)

    # 1) items must be visible in the entity dump
    snap = bc.snap()
    items0 = snap.items()
    log(f"items visible at start: {len(items0)}", verbose_only=True, verbose=args.verbose)
    if not items0:
        bc.remove(slot)
        return result(name, False, "no ET_ITEM entities in dump")

    # 2) walk into an item and watch it vanish under the bot. The nearest
    #    item is not always walk-reachable from a random spawn (ledge/railing/
    #    pit around the q3dm7 red base, 2026-11-16 runs), so EVERY attempt
    #    re-ADDs the bot (a re-ADD rerolls a fresh team spawn), ranks the
    #    items from that fresh position (2-D distance + 1.5x |dz| penalty,
    #    no radius filter -- filters emptied the list after a failed walk and
    #    ended the loop at tries=1), walks to the top candidate with
    #    brain_toward (stuck handling + z guard: abort when the bot is > 80 u
    #    below the item -- a walking bot cannot climb the red-base pit back
    #    out), then does a short GRAZE SWEEP over the spot: "within 24 u in
    #    XY" alone does not touch the item (railings, items a level up/down --
    #    attempts once logged reached=True at dz +148). Pickup (not a health
    #    rise) is the signal: the item may be armor, and DoT near the q3dm7
    #    red spawn can lower health regardless.
    p = snap.player(slot)
    if not p:
        bc.remove(slot)
        return result(name, False, "no player after item dump")
    h0 = p["health"]
    reached = pickup_ok = False
    target = None
    d0 = -1.0
    tries = 0
    tried = set()
    for attempt in range(6):
        bc.remove(slot)
        time.sleep(0.5)
        slot = bc.add(args.botname, args.team)
        if slot < 0 or not wait_for_connect(bc, slot, 20.0) \
                or not join_team(bc, slot, args.team or "red"):
            continue
        time.sleep(1.0)  # spawn settle (knockback + DoT)
        snap = bc.snap()
        p = snap.player(slot)
        if not p:
            continue
        po = p["origin"]
        tries = attempt + 1
        cand = list(snap.items())
        cand.sort(key=lambda e: dist2d(po[:2], e["origin"][:2])
                  + 1.5 * abs(e["origin"][2] - po[2]))
        if not cand:
            continue
        nearest = cand[0]
        for e in cand:  # prefer a candidate not already tried from a prior spawn
            key = (round(e["origin"][0]), round(e["origin"][1]))
            if key not in tried:
                nearest = e
                break
        tried.add((round(nearest["origin"][0]), round(nearest["origin"][1])))
        target = nearest
        d0 = dist2d(po[:2], nearest["origin"][:2])
        log(f"T4 attempt {tries}: fresh spawn, target "
            f"({nearest['origin'][0]:.0f},{nearest['origin'][1]:.0f}) "
            f"dist {d0:.0f}u dz {nearest['origin'][2] - po[2]:+.0f}u")
        reached, start, end = brain_toward(bc, slot,
                                           (nearest["origin"][0], nearest["origin"][1]),
                                           args.hz, 30.0, verbose=args.verbose,
                                           target_z=nearest["origin"][2])
        snap = bc.snap()
        still_there = any(dist2d(e["origin"][:2], nearest["origin"][:2]) < 8.0
                          and abs(e["origin"][2] - nearest["origin"][2]) < 24.0
                          for e in snap.items())
        if not still_there:
            # picked up during the walk itself (checked IMMEDIATELY: items
            # respawn after ~20-30 s, a later re-check could see the respawn)
            log(f"T4 attempt {tries}: reached={reached} item_gone=True (during walk)")
            pickup_ok = True
            break
        if reached:
            # graze sweep: turn while walking forward -> the bot radiates
            # across the item spot from all directions
            g0 = time.time()
            t_next = g0
            while time.time() - g0 < 3.0:
                p = bc.snap().player(slot)
                if not p:
                    break
                bc.cmd(slot, 127, 0, 0, 0, WP_MACHINEGUN, 0.0,
                       p["viewangles"][1] + (time.time() - g0) * 120.0)
                t_next += 1.0 / args.hz
                if t_next > time.time():
                    time.sleep(t_next - time.time())
            snap = bc.snap()
            still_there = any(dist2d(e["origin"][:2], nearest["origin"][:2]) < 8.0
                              and abs(e["origin"][2] - nearest["origin"][2]) < 24.0
                              for e in snap.items())
        log(f"T4 attempt {tries}: reached={reached} item_gone={not still_there}")
        if not still_there:
            pickup_ok = True
            break

    snap = bc.snap()
    p1 = snap.player(slot)
    h1 = p1["health"] if p1 else 0
    still_there = target is not None and any(
        dist2d(e["origin"][:2], target["origin"][:2]) < 8.0
        and abs(e["origin"][2] - target["origin"][2]) < 24.0 for e in snap.items())

    # 3) firing: the spawn weapon is the hitscan MACHINEGUN (this OSP build
    #    has no blaster; slot 1 is the GAUNTLET, which only fires on a
    #    physical hit). Fire the MG for ~1.5 s with DRIFTING-phase sampling
    #    (fixed-period sampling phase-locks onto READY frames and never sees
    #    FIRING) and prove the fire pipeline via:
    #      (a) MG ammo decrementing  -- robust, monotonic, always visible
    #      (b) WEAPON_FIRING(3) observed in at least one snapshot
    #    A hitscan gun spawns no ET_MISSILE, so there is no missile check.
    p_fire = bc.snap().player(slot)
    saw_firing_state = False
    ammo0 = ammo1 = None
    if p_fire and p_fire["health"] > 0:
        w = WP_MACHINEGUN
        ammo0 = p_fire["ammo"][w]
        t0 = time.time()
        jit = 0.0
        while time.time() - t0 < 1.5:
            yaw = p_fire["viewangles"][1]
            bc.cmd(slot, 0, 0, 0, BUTTON_ATTACK, w, 0.0, yaw)
            time.sleep(0.05 + jit)
            jit = (jit + 0.013) % 0.09        # drift the sample phase
            snap = bc.snap()
            p_fire = snap.player(slot)
            if not p_fire or p_fire["health"] <= 0:
                break
            if p_fire["weaponstate"] == WEAPON_FIRING:
                saw_firing_state = True
        ammo1 = p_fire["ammo"][w] if p_fire else None
    fired = saw_firing_state or (
        ammo0 is not None and ammo1 is not None and ammo1 < ammo0)
    missiles_seen = len(bc.snap().missiles())

    bc.remove(slot)
    # pickup verdict was computed in the walk loop (item vanished under the
    # bot on one of the attempts); h0->h1 stays in the detail only -- the
    # item may be armor, and DoT near the q3dm7 red spawn lowers health
    # regardless. reached is a detail too: the claim is "the guided walk made
    # the item vanish under the bot" -- a stuck abort can still cross the
    # item on the way (2026-11-16: dist 285, stuck abort, item_gone True).
    ok = pickup_ok and fired
    detail = (f"items0={len(items0)} tries={tries} dist={d0:.0f} "
              f"reached={reached} health {h0}->{h1} item_gone={not still_there} "
              f"fire_ok={fired} (MG ammo {ammo0}->{ammo1} "
              f"firing_state_seen={saw_firing_state}) missiles_now={missiles_seen}")
    return result(name, ok, detail)


def t5(bc: Botctl, args) -> int:
    """TDM warmup with two human-like slots (red + blue): both must be able
    to send TEXT "ready". The match then starts when the warmup expires
    (match_carespawn -> in-place map_restart); the driver (run_spike.sh)
    confirms it via the SECOND "InitGame:" line in the server log.
    (A TDM match needs >=1 player per team, hence two bots.)"""
    name = "T5 warmup ready"
    red = bc.add(args.botname + "-red", "red")
    blue = bc.add(args.botname + "-blue", "blue")
    if red < 0 or blue < 0:
        if red >= 0:
            bc.remove(red)
        if blue >= 0:
            bc.remove(blue)
        return result(name, False, f"ADD failed (red={red} blue={blue})")

    ok_spawn = wait_for_connect(bc, red, 20.0) and \
        wait_for_connect(bc, blue, 20.0)
    if not ok_spawn:
        bc.remove(red)
        bc.remove(blue)
        return result(name, False, "no connect for both")

    # both must join their teams the human way
    j_red = join_team(bc, red, "red")
    j_blue = join_team(bc, blue, "blue")
    time.sleep(1.0)
    r_red = bc.text(red, "ready")
    r_blue = bc.text(blue, "ready")
    log(f"TEXT 'ready' -> red={r_red} blue={r_blue}")

    # give the game a moment to react, then confirm both are still alive
    # and in their teams
    time.sleep(3.0)
    snap = bc.snap()
    pr, pb = snap.player(red), snap.player(blue)
    alive = bool(pr and pb and pr["health"] > 0 and pb["health"] > 0
                 and pr["team"] == TEAM_RED and pb["team"] == TEAM_BLUE)

    # IMPORTANT: both bots must STAY in their teams for the whole warmup --
    # OSP TDM resets the warmup to "waiting for players" the moment a team
    # goes empty (g_main.c), so removing them now would prevent the match
    # from ever starting. The expiry does an in-place OSP_MapRestart
    # (g_main.c -> "map_restart 0"), which re-runs G_Init (second
    # "InitGame:" line in the server log) but does NOT reset engine time --
    # the observable signal is sv.restartedServerId, exposed as
    # snap.restart_id (it also changes on full map changes).
    t0 = time.time()
    base_id = snap.restart_id
    started = 0
    waited = 0.0
    alive_after = False
    while time.time() - t0 < 45.0:
        time.sleep(0.5)
        waited = time.time() - t0
        snap = bc.snap()
        if snap.restart_id != base_id:
            started = 1
            time.sleep(0.5)   # let the game reconnect the clients
            snap = bc.snap()
            pr, pb = snap.player(red), snap.player(blue)
            alive_after = bool(pr and pb and pr["team"] == TEAM_RED
                               and pb["team"] == TEAM_BLUE)
            break
    bc.remove(red)
    bc.remove(blue)
    ok = (j_red and j_blue and r_red == 1 and r_blue == 1
          and alive and started and alive_after)
    return result(name, ok,
                  f"join_red={j_red} join_blue={j_blue} "
                  f"text_red={r_red} text_blue={r_blue} alive_in_teams={alive} "
                  f"match_started={started} alive_after_restart={alive_after} "
                  f"(waited {waited:.1f}s)")


def t6(bc: Botctl, args) -> int:
    name = "T6 soak"
    slot = bc.add(args.botname, args.team)
    if slot < 0:
        return result(name, False, "ADD failed")
    if not wait_for_connect(bc, slot, 20.0):
        bc.remove(slot)
        return result(name, False, "no connect")
    if not join_team(bc, slot, args.team or "red"):
        bc.remove(slot)
        return result(name, False, "no team join")
    time.sleep(1.0)

    dur = args.seconds if args.seconds > 0 else 600
    t0 = time.time()
    dead_waited = 0.0
    last_snap_ok = 0
    snaps = 0
    alive = True
    while time.time() - t0 < dur:
        try:
            snap = bc.snap()
        except Exception as e:
            alive = False
            log(f"SNAP failed: {e}")
            break
        p = snap.player(slot)
        if not p:
            alive = False
            break
        snaps += 1
        last_snap_ok = time.time()
        if p["pm_type"] == PM_DEAD:
            # idle while dead (the idle-cmd path keeps P_Think running)
            time.sleep(0.5)
            dead_waited += 0.5
            continue
        # random walk with occasional jump + fire
        r = random.random()
        if r < 0.8:
            yaw = p["viewangles"][1] + random.uniform(-90, 90)
            bc.cmd(slot, random.choice([0, 60, 127, -60]),
                   random.choice([-127, -60, 0, 60, 127]), 0,
                   random.choice([0, BUTTON_ATTACK]), WP_MACHINEGUN, 0.0, yaw)
        elif r < 0.9:
            yaw = p["viewangles"][1]
            bc.cmd(slot, 127, 0, 127, 0, WP_MACHINEGUN, 0.0, yaw)  # jump
        else:
            time.sleep(0.1)
        time.sleep(1.0 / args.hz)

    elapsed = time.time() - t0
    bc.remove(slot)
    ok = alive and elapsed >= dur * 0.95
    return result(name, ok,
                  f"ran={elapsed:.0f}s/{dur}s snaps={snaps} dead_time={dead_waited:.1f}s")


def wait_list_empty(bc: Botctl, timeout: float) -> bool:
    """Poll LIST until no managed client is left (engine-side drop must
    clear the management state via Botctl_ClientDropped)."""
    t0 = time.time()
    while time.time() - t0 < timeout:
        if not bc.list():
            return True
        time.sleep(0.2)
    return False


def t5b(bc: Botctl, args) -> int:
    """T5b: a REAL map rotation (rcon 'map ospdm6'). In TDM, SV_Map_f passes
    killBots=qfalse, so SV_SpawnServer reaches the reconnect loop with every
    NA_BOT client still connected:
      - V1 reconnected managed clients through the engine-bot path
        (isBot=qtrue): dropped (no botlib skill/character, or
        BotConnectfailed with bot_enable 0).
      - V2: Botctl_IsManaged -> isBot=qfalse + SV_ClientEnterWorld, so the
        managed clients SURVIVE the rotation with their slots and management
        intact, and stay drivable on the new map.
    Proof: restart_id changes, LIST still holds both client numbers, both
    have a live player state on the new map, and a fresh usercmd visibly
    changes their viewangles (input pipeline alive, wall-independent).
    Contrast with t7: the kick path DROPS a managed client and management
    clears."""
    name = "T5b map rotation"
    red = bc.add(args.botname + "-red", "red")
    blue = bc.add(args.botname + "-blue", "blue")
    if red < 0 or blue < 0:
        if red >= 0:
            bc.remove(red)
        if blue >= 0:
            bc.remove(blue)
        return result(name, False, f"ADD failed (red={red} blue={blue})")
    if not (wait_for_connect(bc, red, 20.0) and wait_for_connect(bc, blue, 20.0)):
        bc.remove(red); bc.remove(blue)
        return result(name, False, "no connect before rotation")
    if not (join_team(bc, red, "red") and join_team(bc, blue, "blue")):
        bc.remove(red); bc.remove(blue)
        return result(name, False, "no team join before rotation")

    base_id = bc.snap().restart_id

    r_out = rcon(args, "map ospdm6")
    log(f"RCON 'map ospdm6' -> {r_out.strip()[:60]!r}")

    # wait for the new level (restart_id changes; snaps empty during loading)
    rid = 0
    t0 = time.time()
    while time.time() - t0 < 30.0:
        time.sleep(0.5)
        try:
            rid = bc.snap().restart_id
        except Exception:
            continue
        if rid and rid != base_id:
            break
    if not rid or rid == base_id:
        bc.remove(red); bc.remove(blue)
        return result(name, False, "map rotation never happened (restart_id unchanged)")

    time.sleep(2.0)  # let the reconnect + first frames settle

    # management must be INTACT: both slots still managed, same client nums
    slots = {c[0] for c in bc.list()}   # botctl list() -> tuples (client, name, team)
    still_managed = red in slots and blue in slots

    # both must have a live player state on the new map
    pr = pb = None
    t0 = time.time()
    while time.time() - t0 < 20.0 and not (pr and pb):
        snap = bc.snap()
        pr, pb = snap.player(red), snap.player(blue)
        if not (pr and pb):
            time.sleep(0.5)
    alive = bool(pr and pb and pr["health"] > 0 and pb["health"] > 0)

    # input pipeline check: command a distinctive viewangle, verify it lands
    # (viewangles apply even against a wall, so this is not spawn-luck)
    ctrl_ok = False
    if alive:
        want_yaw = (pr["viewangles"][1] + 123.0) % 360.0
        t0 = time.time()
        while time.time() - t0 < 2.0 and not ctrl_ok:
            bc.cmd(red, 0, 0, 0, 0, WP_MACHINEGUN, 30.0, want_yaw)
            time.sleep(0.1)
            p = bc.snap().player(red)
            if p:
                dy = abs((p["viewangles"][1] - want_yaw + 180.0) % 360.0 - 180.0)
                dp = abs(p["viewangles"][0] - 30.0)
                ctrl_ok = dy < 5.0 and dp < 5.0

    bc.remove(red); bc.remove(blue)

    ok = still_managed and alive and ctrl_ok
    return result(name, ok,
                  f"restart_id {base_id}->{rid} managed_intact={still_managed} "
                  f"(slots {sorted(slots)}) alive={alive} input_ok={ctrl_ok}")


def t5c(bc: Botctl, args) -> int:
    """T5c: killserver -> map (the exact SV_Shutdown + "map" cycle that the
    12 h SV_Restart performs). Botctl_Shutdown must stop + unlink the socket
    AND reset the enable flag, and Botctl_Frame must re-arm the channel after
    the restart (v1 bug: a static 'was_enabled' stayed true, so the socket
    never came back). Proof: socket disappears on killserver, the engine
    recreates it after 'map q3dm7', a FRESH connection sees LIST empty and
    can ADD again."""
    name = "T5c killserver restart"
    slot = bc.add(args.botname, args.team or "red")
    if slot < 0:
        return result(name, False, "ADD failed")
    if not wait_for_connect(bc, slot, 20.0):
        bc.remove(slot)
        return result(name, False, "no connect")

    path = bc.sockpath
    r_out = rcon(args, "killserver")
    log(f"RCON 'killserver' -> {r_out.strip()[:80]!r}")
    # NOTE: the rcon redirect swallows the server's console output while the
    # command runs (common.c Com_Printf -> rd_buffer only), so the shutdown
    # line shows up HERE, not in the server log.
    shutdown_seen = "Server Shutdown (killserver)" in r_out
    time.sleep(1.5)                       # SV_Shutdown + Botctl_Shutdown teardown
    sock_gone = not os.path.exists(path)

    try:
        bc.close()                        # the engine closed our connection
    except Exception:
        pass

    rcon(args, "map q3dm7")               # same Cbuf text SV_Restart adds

    # the channel must re-arm: Botctl_Frame sees botctl_enable 1 as a fresh
    # on-edge (s_enabled was reset) and recreates listener + socket
    t0 = time.time()
    while time.time() - t0 < 40.0 and not os.path.exists(path):
        time.sleep(0.5)
    if not os.path.exists(path):
        return result(name, False, "socket never recreated after restart")
    time.sleep(1.0)                       # let map load + first frames run

    try:
        bc2 = Botctl(path)
        bc2.ping()
    except Exception as e:
        return result(name, False, f"reconnect after restart failed: {e}")

    try:
        list_empty = not bc2.list()
        n = bc2.add(args.botname + "-after", args.team or "red")
        readd = n >= 0 and wait_for_connect(bc2, n, 20.0)
        joined = readd and join_team(bc2, n, args.team or "red")
        if readd:
            bc2.remove(n)
    finally:
        bc2.close()

    ok = sock_gone and shutdown_seen and list_empty and readd and joined
    return result(name, ok,
                  f"socket_gone={sock_gone} shutdown_line={shutdown_seen} "
                  f"socket_recreated=True "
                  f"list_empty={list_empty} readd_slot={n if readd else '-'} "
                  f"connect+team={joined}")


def t7(bc: Botctl, args) -> int:
    """T7 (as requested in the PR review): admin kick of a managed client
    (rcon 'clientkick <slot>'), then a STOCK bot joins that slot
    (rcon 'addbot dwcbot1 5 red'). The drop goes through SV_DropClient, which
    is NOT a botctl path: without the Botctl_ClientDropped hook the slot
    would keep a phantom 'managed' flag (auto-ACK + injected usercmds for
    the next occupant). Proof: LIST empties on its own, the addbot bot
    lands on the same slot (engine really freed it), and LIST stays empty
    (botctl does not hijack the botlib bot). run_spike.sh deploys
    bot_enable 1 + the dwc botfiles for this scenario."""
    name = "T7 clientkick -> addbot"
    slot = bc.add(args.botname, args.team or "red")
    if slot < 0:
        return result(name, False, "ADD failed")
    if not wait_for_connect(bc, slot, 20.0):
        bc.remove(slot)
        return result(name, False, "no connect")
    if not join_team(bc, slot, args.team or "red"):
        bc.remove(slot)
        return result(name, False, "no team join")

    r_out = rcon(args, f"clientkick {slot}")   # clientkick takes the 0-based slot
    log(f"RCON 'clientkick {slot}' -> {r_out.strip()[:60]!r}")

    cleared = wait_list_empty(bc, 5.0)

    # OSP usage: addbot <botname> [skill 1-5] [team] [msec delay] [altname]
    # (g_bot.c Svcmd_AddBot_f). Skill 5 on purpose: the dwc botfiles are
    # production-tuned and define ONLY a "skill 5" personality block
    # (botfiles/bots/dwcbot1_c.c) -- skill 4 makes botlib fall back to the
    # default personality and abort ("couldn't find skill 4 in
    # bots/dwcbot1_c.c", verified 2026-11-16 via the rcon answer).
    r_out = rcon(args, "addbot dwcbot1 5 red")
    # every G_AddBot failure text ("Bot not defined", "All player slots in
    # use", "BotConnectfailed") is printed INSIDE the rcon redirect -> it
    # only shows up here, never in the server log. Log it.
    log(f"RCON 'addbot dwcbot1 5 red' -> {r_out.strip()[:400]!r}")
    occupied = False
    t0 = time.time()
    # bot_memory 0 -> the addbot path COMPILES the dwcbot1 character files
    # on the server thread before the client slot is taken; allow plenty of
    # time before judging the slot reused (warmup countdown runs in
    # parallel, g_warmup 30).
    while time.time() - t0 < 45.0 and not occupied:
        occupied = bc.snap().player(slot) is not None
        if not occupied:
            time.sleep(0.5)
    if occupied:
        time.sleep(2.0)          # let the bot finish connect + team join
    else:
        # name dump: snapshots carry no names, rcon 'status' does
        st = rcon(args, "status", timeout=4.0)
        log(f"RCON 'status' -> {st.strip()[:400]!r}")
    still_cleared = not bc.list()

    ok = cleared and occupied and still_cleared
    return result(name, ok,
                  f"kicked slot={slot} list_cleared={cleared} "
                  f"addbot_took_same_slot={occupied} botctl_list_still_empty={still_cleared}")


def t8(bc: Botctl, args) -> int:
    """T8: the sidecar dies. Closing the connection without REMOVE (crash
    simulation) must make the engine drop the clients it drove ('bot control
    connection lost' in Botctl_Frame) and keep listening: a FRESH connection
    sees LIST empty, no player state for the old slot, and can ADD again."""
    name = "T8 sidecar lost"
    slot = bc.add(args.botname, args.team or "red")
    if slot < 0:
        return result(name, False, "ADD failed")
    if not wait_for_connect(bc, slot, 20.0):
        bc.remove(slot)
        return result(name, False, "no connect")
    if not join_team(bc, slot, args.team or "red"):
        bc.remove(slot)
        return result(name, False, "no team join")

    path = bc.sockpath
    bc.close()                      # simulate the crash (EOF, no REMOVE sent)
    log("connection closed without REMOVE (simulated crash)")
    time.sleep(1.5)                 # Botctl_Frame notices within a frame

    try:
        bc2 = Botctl(path)          # engine must still be listening
        bc2.ping()
    except Exception as e:
        return result(name, False, f"engine stopped listening: {e}")

    try:
        lst_empty = not bc2.list()
        gone = bc2.snap().player(slot) is None
        n = bc2.add(args.botname + "-after", args.team or "red")
        readd = n >= 0 and wait_for_connect(bc2, n, 20.0)
        if readd:
            bc2.remove(n)
    finally:
        bc2.close()

    ok = lst_empty and gone and readd
    return result(name, ok,
                  f"old_slot={slot} list_empty={lst_empty} player_gone={gone} "
                  f"readd_after_reconnect={readd}")


def t9(bc: Botctl, args) -> int:
    """T9 (review round 2, 2026-11-16): stalled reader. The sidecar stops
    reading its socket and keeps firing SNAP requests. Each engine reply send
    carries the 500 ms SO_SNDTIMEO; once the kernel buffers fill, bc_send_msg
    must FAIL -- and the handler must then treat the connection as broken and
    CLOSE it, instead of continuing with silently dropped replies (a partial
    frame would desync the stream; a request/response sidecar would wait
    forever for the missing reply). Expected engine behaviour after the close:
    it drops the clients it drove (same path as the T8 crash, 'bot control
    connection lost'), keeps serving UDP (rcon status answers), and a FRESH
    connection sees LIST empty and can ADD again."""
    name = "T9 stalled reader"
    slot = bc.add(args.botname, args.team or "red")
    if slot < 0:
        return result(name, False, "ADD failed")
    if not wait_for_connect(bc, slot, 20.0):
        bc.remove(slot)
        return result(name, False, "no connect")
    if not join_team(bc, slot, args.team or "red"):
        bc.remove(slot)
        return result(name, False, "no team join")
    time.sleep(1.0)

    # flood SNAP requests, never read a reply: each dump is ~3 kB on q3dm7,
    # so a few dozen unanswered ones fill the UDS buffer and the engine's
    # next send() hits SO_SNDTIMEO -> bc_sendall -1 -> bc_send_msg -1 ->
    # conn_broke -> handler break + close.
    path = bc.sockpath
    sent = 0
    closed = False
    t0 = time.time()
    while time.time() - t0 < 25.0:
        try:
            _send_frame(bc.sock, OP_SNAP, b"")
            sent += 1
        except OSError as e:
            log(f"T9: send failed after {sent} requests: {e}")
            closed = True             # engine already closed the socket
            break
        if sent % 25 == 0:            # peek: did the engine close the connection?
            try:
                data = bc.sock.recv(1, socket.MSG_PEEK)
            except OSError:
                data = b""
            if data == b"":           # EOF
                closed = True
                break
        time.sleep(0.02)
    if not closed:
        try:                          # final check after the flood window
            bc.sock.settimeout(3.0)
            closed = bc.sock.recv(1) == b""
        except OSError:
            closed = True
    try:
        bc.close()
    except Exception:
        pass
    if not closed:
        return result(name, False,
                      f"engine kept the broken stream open ({sent} SNAP requests, "
                      "no close -- dropped replies would desync the sidecar)")

    log(f"T9: engine closed the connection after {sent} unanswered SNAP requests")
    time.sleep(2.0)                   # Botctl_Frame drops the orphaned clients

    # the server must still be fully responsive on UDP (point 8's symptom was
    # a stalled handler; here the whole connection is gone -- rcon must work)
    resp = rcon(args, "status", timeout=5.0)
    rcon_ok = bool(resp.strip())

    try:
        bc2 = Botctl(path)
        bc2.ping()
    except Exception as e:
        return result(name, False, f"engine stopped listening: {e}")
    try:
        lst_empty = not bc2.list()
        gone = bc2.snap().player(slot) is None
        n = bc2.add(args.botname + "-after", args.team or "red")
        readd = n >= 0 and wait_for_connect(bc2, n, 20.0)
        if readd:
            bc2.remove(n)
    finally:
        bc2.close()

    ok = rcon_ok and lst_empty and gone and readd
    return result(name, ok,
                  f"requests_flooded={sent} engine_closed_conn=True "
                  f"rcon_answered={rcon_ok} list_empty={lst_empty} "
                  f"player_gone={gone} readd_after_reconnect={readd}")


def t10(bc: Botctl, args) -> int:
    """T10 (review round 3, 2026-11-19): close-during-reply = SIGPIPE
    repro. The engine serves one UDS connection at a time, so the close
    must land on THIS connection: send a SNAP request (the handler then
    waits up to a frame in Botctl_WaitSnapshot), close ~10 ms later — the
    close lands while the request is in flight. Before the fix the
    reply's send() raised SIGPIPE (nothing ignored it) and the default
    action terminated the whole server (exit 141) before -1/EPIPE was
    visible. After the fix (MSG_NOSIGNAL on Linux / SO_NOSIGPIPE on
    BSD/macOS) the send fails with EPIPE, takes the normal
    connection-lost path, and the engine must stay up: rcon status
    answers and a fresh connection works, on every try."""
    name = "T10 close-during-reply (SIGPIPE)"
    if not rcon(args, "status", timeout=5.0).strip():
        return result(name, False, "rcon status already failing before the test")
    path = bc.sockpath
    for i in range(10):
        _send_frame(bc.sock, OP_SNAP, b"")     # reply is now in flight
        time.sleep(0.01)                       # close lands while it waits
        try:
            bc.close()
        except Exception:
            pass
        if not rcon(args, "status", timeout=5.0).strip():
            return result(name, False,
                          f"server dead after try {i + 1} (rcon silent — SIGPIPE kill?)")
        try:
            bc = Botctl(path)
            bc.ping()
        except Exception as e:
            return result(name, False,
                          f"engine stopped listening after try {i + 1}: {e}")
        time.sleep(0.5)                        # Botctl_Frame drop path between tries
    try:
        bc.close()
    except Exception:
        pass
    return result(name, True,
                  "10/10 close-during-reply tries survived: rcon answered, "
                  "engine kept listening (EPIPE path, no SIGPIPE kill)")


SCENARIOS = {
    "t1": t1, "t2": t2, "t3": t3, "t4": t4, "t5": t5, "t5b": t5b,
    "t5c": t5c, "t6": t6, "t7": t7, "t8": t8, "t9": t9, "t10": t10,
}


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--port", type=int, default=28133)
    ap.add_argument("--sockpath", default=None,
                    help="explicit socket path (default derived from port)")
    ap.add_argument("--scenario", choices=sorted(SCENARIOS), default="t1")
    ap.add_argument("--botname", default="SpikeBot")
    ap.add_argument("--team", default="", help="red/blue, or empty for auto")
    ap.add_argument("--hz", type=float, default=100.0)
    ap.add_argument("--seconds", type=float, default=10.0)
    ap.add_argument("--rconhost", default="127.0.0.1")
    ap.add_argument("--rconpass", default="testrcon123",
                    help="rcon password of the spike server")
    ap.add_argument("--verbose", action="store_true")
    args = ap.parse_args()

    path = args.sockpath or sockpath_for_port(args.port)
    if not os.path.exists(path):
        print(f"RESULT {args.scenario}: FAIL socket not found: {path}", flush=True)
        return 1

    bc = Botctl(path)
    try:
        ping = bc.ping()
        log(f"connected to {path} (ping={ping})")
    except Exception as e:
        print(f"RESULT {args.scenario}: FAIL connect/ping: {e}", flush=True)
        return 1

    try:
        return SCENARIOS[args.scenario](bc, args)
    finally:
        bc.close()


if __name__ == "__main__":
    sys.exit(main())

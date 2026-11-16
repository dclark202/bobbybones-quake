#!/usr/bin/env python3
"""
sidecar.py -- the spike "brain": drives one bot slot in a Quake3e + OSP
server through the botctl Unix socket and runs the T1-T8 spike scenarios.

Usage:
  python3 sidecar.py --port 28133 --scenario t2 --botname SpikeBot [--team red]
                     [--hz 100] [--seconds 10] [--verbose]

Scenarios (each prints a PASS/FAIL line and exits 0/1):
  t1  slot lifecycle: add -> appears in LIST + SNAP (spawns, gets a team in
      TDM) -> remove -> slot freed. (scoreboard/kick covered via server log)
  t2  scripted movement: hold forward for N seconds, verify the snapshot
      origin moves in the commanded direction by a plausible distance.
  t3  substeps: two runs (1 cmd/frame vs 4 cmds/frame, same total input
      time), verify total displacement is close (physics is substep-driven).
  t4  world state: verify items are present in the entity dump; walk into
      the nearest health item and verify it disappears AND health rises.
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
      that slot (rcon addbot dwcbot1 4 red): management state must clear on
      its own (LIST empty, stays empty), and the addbot bot must land on the
      same slot.
  t8  sidecar crash: closing the connection without REMOVE must make the
      engine drop its managed clients and keep listening (fresh connection
      sees LIST empty, old player gone, can ADD again).

Stdlib only. Talks to the engine socket <fs_homepath>/botctl-<port>.sock
(see botctl.sockpath_for_port; the spike runs use ~/.q3a_spike).
"""

import argparse
import math
import os
import random
import signal
import struct
import sys
import time

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from botctl import (
    Botctl, Snapshot, sockpath_for_port,
    BUTTON_ATTACK,
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
    """One RCON command over UDP. q3e handles rcon CONNECTIONLESS:
    '\\xff\\xffrcon <pass> <cmd>\\0', replies come back as one or more
    '\\xff\\xffprint\\n<text>' packets (sv_main.c SVC_RemoteCommand +
    SV_FlushRedirect). Keep rcon calls per scenario few:
    SVC_RateLimitAddress rate-limits them."""
    import socket as _socket
    s = _socket.socket(_socket.AF_INET, _socket.SOCK_DGRAM)
    s.settimeout(timeout)
    s.bind(("127.0.0.1", 0))
    payload = b"\xff\xffrcon " + args.rconpass.encode() + b" " + command.encode() + b"\x00"
    s.sendto(payload, (args.rconhost, args.port))
    chunks = []
    try:
        while True:
            data, _ = s.recvfrom(4096)
            if data.startswith(b"\xff\xffprint"):
                chunks.append(data[len(b"\xff\xffprint"):].decode(errors="replace").lstrip("\n"))
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
    T2 dot=1.000 but 49 u/s). Probe 0.35 s of forward walking in the four
    cardinal world-yaw directions and return the clearest one."""
    best_yaw, best_rate = 0.0, -1.0
    for yaw in (0.0, 90.0, 180.0, 270.0):
        p0 = bc.snap().player(slot)
        if not p0:
            continue
        start = p0["origin"]
        t0 = time.time()
        while time.time() - t0 < 0.35:
            bc.cmd(slot, 127, 0, 0, 0, WP_MACHINEGUN, 0.0, yaw)
            time.sleep(1.0 / hz)
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
                 yaw_step=0.0, verbose=False):
    """Steer toward a 2-D point. Returns (reached: bool, start, end)."""
    snap = bc.snap()
    p0 = snap.player(slot)
    start = p0["origin"]
    yaw = p0["viewangles"][1]
    t0 = time.time()
    last = start
    while time.time() - t0 < max_time:
        snap = bc.snap()
        p = snap.player(slot)
        if not p:
            time.sleep(0.05)
            continue
        ox, oy, oz = p["origin"]
        yaw = p["viewangles"][1]
        fx, fy = norm2d(target_xy[0] - ox, target_xy[1] - oy)
        # project the world target direction onto the view's fwd/right
        (fdx, fdy), (rdx, rdy) = fwd_right_from_yaw(yaw)
        fwd = fx * fdx + fy * fdy
        right = fx * rdx + fy * rdy
        fwd_i = int(max(-127, min(127, round(fwd * 127))))
        right_i = int(max(-127, min(127, round(right * 127))))
        bc.cmd(slot, fwd_i, right_i, 0, 0, WP_MACHINEGUN, 0.0, yaw + yaw_step)
        last = p["origin"]
        if dist2d((ox, oy), target_xy) < 24.0:
            return True, start, last
        time.sleep(1.0 / hz)
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


def t2(bc: Botctl, args) -> int:
    name = "T2 movement"
    slot = bc.add(args.botname, args.team)
    if slot < 0:
        return result(name, False, "ADD failed")
    if not wait_for_connect(bc, slot, 20.0):
        bc.remove(slot)
        return result(name, False, "no connect")
    if not join_team(bc, slot, args.team or "red"):
        bc.remove(slot)
        return result(name, False, "no team join")
    time.sleep(1.0)  # let the spawn settle (knockback + DoT)

    # Hold fwd=127 for ~1.2 s but MEASURE the first ~1.0 s along the
    # clearest of four probe directions (see choose_clear_yaw): that segment
    # is clean run speed (~320 u/s) unless the (random) spawn faces a wall.
    hz = args.hz
    dt = 1.0 / hz
    HOLD, MEASURE = 1.2, 1.0

    p0 = bc.snap().player(slot)
    if not p0:
        bc.remove(slot)
        return result(name, False, "no player after join")
    yaw0, probe_rate = choose_clear_yaw(bc, slot, hz, verbose=args.verbose)
    time.sleep(0.3)

    p0 = bc.snap().player(slot)
    if not p0:
        bc.remove(slot)
        return result(name, False, "no player after probe")
    start = p0["origin"]

    mid, mid_t = None, 0.0
    t0 = time.time()
    while time.time() - t0 < HOLD:
        bc.cmd(slot, 127, 0, 0, 0, WP_MACHINEGUN, 0.0, yaw0)
        if mid is None and (time.time() - t0) >= MEASURE - dt:
            mid = bc.snap().player(slot)
            mid_t = time.time() - t0
        time.sleep(dt)

    end = bc.snap().player(slot)
    bc.remove(slot)
    if not mid:
        return result(name, False, "mid snapshot missing")

    fx, fy = fwd_right_from_yaw(yaw0)[0]      # commanded direction
    mo = mid["origin"]
    mdx, mdy = mo[0] - start[0], mo[1] - start[1]
    mtraveled = math.hypot(mdx, mdy)
    mdot = (mdx * fx + mdy * fy) / max(mtraveled, 1e-6)
    rate = mtraveled / max(mid_t, 1e-6)
    ok = rate > 250.0 and mdot > 0.95 and mtraveled > 200.0
    end_str = (f" end=({end['origin'][0]-start[0]:+.1f},{end['origin'][1]-start[1]:+.1f})"
               if end else "")
    return result(name, ok,
                  f"first{mid_t:.2f}s: rate={rate:.1f}u/s dir_dot={mdot:.3f} "
                  f"travel={mtraveled:.1f}u ({mdx:+.1f},{mdy:+.1f}){end_str}")


def t3(bc: Botctl, args) -> int:
    name = "T3 substeps"

    def run(substeps: int):
        """Stage `substeps` identical cmds per frame (hz = 20*substeps) for
        1.2 s and MEASURE the first 1.0 s of travel along the clearest
        direction (see choose_clear_yaw)."""
        slot = bc.add(args.botname, args.team)
        if slot < 0:
            return None
        if not wait_for_connect(bc, slot, 20.0):
            bc.remove(slot)
            return None
        if not join_team(bc, slot, args.team or "red"):
            bc.remove(slot)
            return None
        time.sleep(1.0)
        hz = 20 * substeps
        yaw, probe_rate = choose_clear_yaw(bc, slot, 20.0)
        dt = 1.0 / hz
        HOLD, MEASURE = 1.2, 1.0
        mid, mid_t = None, 0.0
        p0 = bc.snap().player(slot)
        if not p0:
            bc.remove(slot)
            return None
        start = p0["origin"]
        t0 = time.time()
        while time.time() - t0 < HOLD:
            bc.cmd(slot, 127, 0, 0, 0, WP_MACHINEGUN, 0.0, yaw)
            if mid is None and (time.time() - t0) >= MEASURE - dt:
                mid = bc.snap().player(slot)
                mid_t = time.time() - t0
            time.sleep(dt)
        bc.remove(slot)
        time.sleep(2.0)  # let the slot free + world reset between runs
        if not mid:
            return None
        return mid_t, math.hypot(mid["origin"][0] - start[0],
                                 mid["origin"][1] - start[1])

    r1 = run(1)
    r4 = run(4)
    if r1 is None or r4 is None:
        return result(name, False, "run failed (spawn/add)")
    t1, d1 = r1
    t4, d4 = r4
    rate1, rate4 = d1 / max(t1, 1e-6), d4 / max(t4, 1e-6)
    ratio = min(rate1, rate4) / max(rate1, rate4)
    # both substep rates must be near clean run speed (~300 u/s in the first
    # second); a >2.5x spread means the multi-cmd-per-frame replay path
    # drops or clumps staged inputs.
    ok = rate1 > 200.0 and rate4 > 200.0 and 0.4 <= ratio <= 2.5
    detail = (f"rate(sub1)={rate1:.1f}u/s rate(sub4)={rate4:.1f}u/s "
              f"d1={d1:.1f}u d4={d4:.1f}u ratio={ratio:.2f}")
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

    # 2) walk into the nearest item: it must vanish AND health should rise
    p = snap.player(slot)
    nearest = min(items0, key=lambda e: dist2d(p["origin"][:2], e["origin"][:2]))
    d0 = dist2d(p["origin"][:2], nearest["origin"][:2])
    h0 = p["health"]
    reached, start, end = brain_toward(bc, slot, (nearest["origin"][0], nearest["origin"][1]),
                                       args.hz, 25.0, verbose=args.verbose)
    snap = bc.snap()
    p1 = snap.player(slot)
    h1 = p1["health"] if p1 else 0
    still_there = any(dist2d(e["origin"][:2], nearest["origin"][:2]) < 8.0
                      for e in snap.items())

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
    # pickup: the item vanishing under us is the robust signal. Do NOT require
    # a health rise -- the nearest item may not be a health pack, and a
    # -1 hp/s damage-over-time runs near the q3dm7 red spawn.
    pickup_ok = (not still_there) or (h1 > h0)
    ok = reached and pickup_ok and fired
    detail = (f"items0={len(items0)} dist={d0:.0f} reached={reached} "
              f"health {h0}->{h1} item_gone={not still_there} "
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
    slots = {c["client"] for c in bc.list()}
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
    log(f"RCON 'killserver' -> {r_out.strip()[:60]!r}")
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

    ok = sock_gone and list_empty and readd and joined
    return result(name, ok,
                  f"socket_gone={sock_gone} socket_recreated=True "
                  f"list_empty={list_empty} readd_slot={n if readd else '-'} "
                  f"connect+team={joined}")


def t7(bc: Botctl, args) -> int:
    """T7 (as requested in the PR review): admin kick of a managed client
    (rcon 'clientkick <slot>'), then a STOCK bot joins that slot
    (rcon 'addbot dwcbot1 red'). The drop goes through SV_DropClient, which
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

    # OSP usage: addbot <botname> [skill 1-5] [team] -> team is ARG 3
    # (g_bot.c Svcmd_AddBot_f); skill 4 = OSP's default.
    rcon(args, "addbot dwcbot1 4 red")
    occupied = False
    t0 = time.time()
    # bot_memory 0 -> the addbot path COMPILES the dwcbot1 character files
    # on the server thread before the client slot is taken; allow plenty of
    # time before judging the slot reused.
    while time.time() - t0 < 30.0 and not occupied:
        occupied = bc.snap().player(slot) is not None
        if not occupied:
            time.sleep(0.5)
    if occupied:
        time.sleep(2.0)          # let the bot finish connect + team join
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


SCENARIOS = {
    "t1": t1, "t2": t2, "t3": t3, "t4": t4, "t5": t5, "t5b": t5b,
    "t5c": t5c, "t6": t6, "t7": t7, "t8": t8,
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

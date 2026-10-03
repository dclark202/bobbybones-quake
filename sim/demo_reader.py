"""Read demos extracted by tools/demodump (out.bin + out.json).

    d = load("data/demos_parsed/x.bin")      # dict of numpy arrays, one row per snapshot
    d["time"], d["origin"], d["velocity"], d["angles"], d["weapon"], d["health"], d["armor"], ...
    d["players"][i]  -> (k, 19) other player entities in snapshot i
    d["missiles"][i] -> (k, 12), d["items"][i] -> (k, 6), d["events"][i] -> (k, 9)

Player-state layout (PS_N = 103 floats) as written by demodump.cpp.
"""
import json
import os

import numpy as np

HDR = 6
PS_N = 103
PL_N, MI_N, IT_N, EV_N = 19, 12, 6, 9
# offsets inside the player-state block
PS = dict(clientNum=0, commandTime=1, origin=2, velocity=5, angles=8, delta_angles=11, pm_type=14, pm_flags=15,
          pm_time=16, groundEntityNum=17, weapon=18, weaponstate=19, weaponTime=20, viewheight=21, eFlags=22,
          movementDir=23, gravity=24, speed=25, stats=26, persistant=42, ammo=58, powerups=74, events=90,
          eventParms=92, eventSequence=94, externalEvent=95, externalEventParm=96, damageEvent=97, damageYaw=98,
          damagePitch=99, damageCount=100, generic1=101, jumppad_ent=102)
ENTITYNUM_NONE = 1023


def load(bin_path):
    raw = np.fromfile(bin_path, dtype=np.float32)
    meta = json.load(open(os.path.splitext(bin_path)[0] + ".json", encoding="utf-8", errors="replace"))
    assert meta.get("ps_n", PS_N) == PS_N
    ps, times, players, missiles, items, events = [], [], [], [], [], []
    i = 0
    n = len(raw)
    while i + HDR + PS_N <= n:
        assert raw[i] == 1, "bad record marker at {}".format(i)
        t, npl, nmi, nit, nev = (int(v) for v in raw[i + 1:i + 6])
        i += HDR
        ps.append(raw[i:i + PS_N])
        i += PS_N
        players.append(raw[i:i + npl * PL_N].reshape(npl, PL_N))
        i += npl * PL_N
        missiles.append(raw[i:i + nmi * MI_N].reshape(nmi, MI_N))
        i += nmi * MI_N
        items.append(raw[i:i + nit * IT_N].reshape(nit, IT_N))
        i += nit * IT_N
        events.append(raw[i:i + nev * EV_N].reshape(nev, EV_N))
        i += nev * EV_N
        times.append(t)
    ps = np.array(ps, np.float32).reshape(-1, PS_N)
    out = dict(meta=meta, time=np.array(times, np.int64), ps=ps, players=players, missiles=missiles, items=items,
               events=events)
    for k in ("origin", "velocity", "angles"):
        out[k] = ps[:, PS[k]:PS[k] + 3]
    for k in ("clientNum", "weapon", "weaponstate", "groundEntityNum", "pm_type", "pm_flags", "eFlags"):
        out[k] = ps[:, PS[k]].astype(np.int64)
    out["stats"] = ps[:, PS["stats"]:PS["stats"] + 16]
    out["ammo"] = ps[:, PS["ammo"]:PS["ammo"] + 16]
    return out


def server_info(meta, key):
    """a value from config string 0 / 1 of the first gamestate (e.g. 'mapname')"""
    for gs in meta["gamestates"]:
        for cs in ("cs0", "cs1"):
            parts = gs["cs"].get(cs, "").split("\\")
            for a, b in zip(parts[1::2], parts[2::2]):
                if a == key:
                    return b
    return None

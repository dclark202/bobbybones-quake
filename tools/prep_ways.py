"""Make a server's map tables before it takes players.

The simulator keeps two tables per map beside the walking map, or in $ROUTE_CACHE where that folder cannot be written
(a server: /maps is read-only, the tables go to its data folder): the nearest point of the walking map for every grid
cell, and since v0.2 the seconds of way between any two points (duel_env's RouteField.ways, read by the last 143
inputs). Both are worked out at a map's first load if their file is not there or was made under other switches: up to
ten seconds a map, and a game server stands still for as long. tools/duel_server.sh therefore runs this in the image
before the server starts, with the same data folder and the same switches the plugin will set (those of policy.npz):

    docker run --rm --entrypoint python3 -v <data folder>:/tmp/practice -v <repo>/data/maps:/maps:ro qlbot /tools/prep_ways.py bloodrun aerowalk ...

A table that is already there (in /maps, copied with the walking map, or in the data folder from an earlier start) is
only read. A map without a walking map or a map file is skipped. One map per process: the simulator's worlds share
their buffers.
"""
import glob
import importlib
import json
import os
import subprocess
import sys
import time
import zipfile

D = os.environ.get("PREP_DATA", "/tmp/practice")
MAPS_DIR = os.environ.get("PREP_MAPS_DIR", "/maps")


def bsp_of(mapname):
    """the map file, taken from the game's own pak (as the plugins do)"""
    bsp = "/tmp/maps/{}.bsp".format(mapname)
    if os.path.exists(bsp) and os.path.getsize(bsp) > 1000:
        return bsp
    os.makedirs("/tmp/maps", exist_ok=True)
    for pak in ["/ql/baseq3/pak00.pk3", "/ql/baseq3/{}.pk3".format(mapname), "/ql/maps-data/{0}/{0}.pk3".format(mapname)] + sorted(
            glob.glob("/ql/steamapps/workshop/content/282440/*/{}.pk3".format(mapname))):
        try:
            data = zipfile.ZipFile(pak).read("maps/{}.bsp".format(mapname))
        except (KeyError, OSError):
            continue
        with open(bsp, "wb") as f:
            f.write(data)
        return bsp
    return None


def one(mapname):
    import numpy as np
    P = np.load(os.path.join(D, "policy.npz"))
    ev = json.loads(str(P["env_vars"])) if "env_vars" in P.files else {}
    os.environ.update({k: str(v) for k, v in ev.items()})
    if "legs" in P.files:
        os.environ["LEGS_NET"] = os.path.join(D, str(P["legs"]))
    os.environ["ROUTE_CACHE"] = D
    nav = os.path.join(MAPS_DIR, "nav_{}_sim.json".format(mapname))
    if not os.path.exists(nav):
        print("{}: no walking map, nothing to make".format(mapname), flush=True)
        return
    bsp = bsp_of(mapname)
    if bsp is None:
        print("{}: no map file, skipped".format(mapname), flush=True)
        return
    sys.path.insert(0, "/sim")
    E = importlib.import_module(str(P["env"]))
    before = set(os.listdir(D))
    t0 = time.time()
    env = E.DuelEnv(bsp, n_matches=1, seed=1, nav=nav, **(dict(group=2) if "ffa" in str(P["env"]) else {}))
    new = sorted(f for f in set(os.listdir(D)) - before if f.startswith("nav_"))
    ways = getattr(env, "v02_ways", None)
    print("{}: {:.1f} s; {}{}".format(mapname, time.time() - t0, "made " + ", ".join(new) if new else "its tables were there",
                                      "" if ways is None else "; ways between {} points, {} places of the pros, {} cells with numbers".format(
                                          len(ways), len(env.v02_pp), 0 if env.v02_cell is None else len(env.v02_cell[4]) - 1)), flush=True)


if __name__ == "__main__":
    if len(sys.argv) == 3 and sys.argv[1] == "--one":
        one(sys.argv[2])
        sys.exit(0)
    if not os.path.exists(os.path.join(D, "policy.npz")):
        print("map tables: no policy.npz in the data folder, nothing made")
        sys.exit(0)
    seen = []
    for m in sys.argv[1:]:
        m = m.lower()
        if m in seen:
            continue
        seen.append(m)
        r = subprocess.run([sys.executable, os.path.abspath(__file__), "--one", m])
        if r.returncode:
            print("{}: not made (the server makes it at the map's first load)".format(m), flush=True)

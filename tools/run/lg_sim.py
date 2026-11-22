"""(tools/run/lg_sim.py; docs/design/LG_REAL_VS_SIM.md; LGCMP_OUT=<folder> python tools/run/lg_sim.py <duel_eval args>) 1.6a's lightning in the simulator, counted as lg_real.py counts it from the servers' sessions: shots and hits (the simulator's own
lg_shots / lg_hits, policy seats), by the distance between the two players, minutes, the lightning in hand while alive. Runs
tools/duel_eval.py unchanged (its own settings from the checkpoint), with DuelEnv.step wrapped in every worker (spawn re-imports this
file as __mp_main__, so the wrap is at the top level). Each worker writes its totals to LGCMP_OUT/<pid>.json every 400 steps."""
import json, os, sys
ROOT = r"C:\Users\dacla\Documents\gh\BobbyBones"
sys.path.insert(0, os.path.join(ROOT, "sim"))
sys.path.insert(0, os.path.join(ROOT, "tools"))
import numpy as np
import importlib

OUT = os.environ["LGCMP_OUT"]
E = None                    # the env module, wrapped when duel_eval imports it (after it has set the checkpoint's settings)
BINS = [0, 200, 400, 600, 800, 10000]
LGI = 2
_orig = None
T = {"steps": 0, "seat_min": 0.0, "lg_seat_min": 0.0, "shots": 0.0, "hits": 0.0,
     "shots_b": [0.0] * 5, "hits_b": [0.0] * 5}


def _b(d):
    for i in range(5):
        if d < BINS[i + 1]:
            return i
    return 4


def _sum(self, k):
    v = self.stats.get(k, 0)
    return float(np.sum(v))


def step(self, a):
    s0, h0 = _sum(self, "lg_shots"), _sum(self, "lg_hits")
    out = _orig(self, a)
    ds, dh = _sum(self, "lg_shots") - s0, _sum(self, "lg_hits") - h0
    if self.n == 2:
        if ds or dh:
            b = _b(float(np.linalg.norm(self.state[0, :3] - self.state[1, :3])))
            T["shots_b"][b] += ds; T["hits_b"][b] += dh
        T["shots"] += ds; T["hits"] += dh
        pol = np.asarray(self.script) == 0
        alive = np.asarray(self.hp) > 0
        T["seat_min"] += float(pol.sum()) * E.DT / 60.0
        T["lg_seat_min"] += float((pol & alive & (np.asarray(self.weapon) == LGI)).sum()) * E.DT / 60.0
    T["steps"] += 1
    if T["steps"] % 400 == 0:
        json.dump(T, open(os.path.join(OUT, "{}.json".format(os.getpid())), "w"))
    return out


_imp = importlib.import_module


def _import(name, *a, **k):
    global E, _orig
    m = _imp(name, *a, **k)
    if name.startswith("duel_env") and hasattr(m, "DuelEnv") and _orig is None:
        E, _orig = m, m.DuelEnv.step
        assert m.WEAPONS.index("lg") == LGI
        m.DuelEnv.step = step
    return m


importlib.import_module = _import

if __name__ == "__main__":
    import duel_eval
    sys.argv = ["duel_eval.py"] + sys.argv[1:]
    duel_eval.main()

"""v0.6.1's pay ledger: what typical events pay him under (a) v0.5.0's flat pay, (b) the full win pay (WIN_W 1, FADE_V 1, WIN_GAIN G,
WIN_STACK 1), (c) (b) + the shaping WIN_SHAPE_K = k. The win part and the shaping are worked out by the simulator's own
functions (_win_p, _wb_chance, _wb_pnext, _wsh_psi of sim/duel_env.py in the v061 worktree) on a stand-in state, so the
numbers are the code's. Every amount is his (the first seat's); the win part and the shaping are zero-sum (the enemy gets
minus it), and so is the flat pay here (damage dealt 0.0055 a point = the enemy's taken; ITEM_FLAT takes the same from the enemy).
    python tools/winpay_ledger.py [--gain 1.75] [--k 0,1,2,3,4] [--json out.json] [--md out.md]   (v0.6.1: docs/v0.6.1/WINPAY_v0.6.1.md)
"""
import argparse
import json
import os
import sys

import numpy as np

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, os.path.join(ROOT, "sim"))
os.environ.setdefault("OPENBLAS_NUM_THREADS", "1")
import duel_env as E  # noqa: E402

DMG, MH, RA, FRAG = 0.0055, 0.35, 0.30, 1.0                # v0.5.0's flat pay (--dmg-reward 0.0055, taken weight 1; ITEM_FLAT MH 0.35 RA 0.30)
GAMMA = 0.999


class S:
    """a stand-in for one duel (two seats) with the simulator's functions bound to it"""
    def __init__(self, tab):
        self.frags_r = np.zeros(2)
        self.hp = np.array([100.0, 100.0])
        self.armor = np.array([50.0, 50.0])
        self.rsp_wait = np.zeros(2, np.int64)
        self.has = np.zeros((2, 16), bool)
        self.has[:, [E.RL, E.LG]] = True                     # (both own the rocket launcher and the lightning gun; nobody the rail)
        self.wb_tab = tab

    def _others_arr(self):
        return np.array([[1], [0]])

    _win_p = E.DuelEnv._win_p
    _wb_chance = E.DuelEnv._wb_chance
    _wb_pnext = E.DuelEnv._wb_pnext
    _wsh_psi = E.DuelEnv._wsh_psi

    def copy(self):
        o = S(self.wb_tab)
        o.frags_r, o.hp, o.armor, o.rsp_wait, o.has = self.frags_r.copy(), self.hp.copy(), self.armor.copy(), self.rsp_wait.copy(), self.has.copy()
        return o

    def W(self, left, stack=True):
        E.WIN_STACK = stack
        return float(self._wb_chance(0, left)[0])

    def psi(self, left):
        return float(self._wsh_psi(0, left)[0])


def table():
    f_ = os.path.join(ROOT, "sim", "win_chance.json")
    wc_ = json.load(open(f_, encoding="utf-8"))
    p_ = np.array(wc_["p"], np.float64)
    left_ = np.array(wc_["left_s"], np.float64)
    D_ = int(np.array(wc_["diffs"])[-1])
    return (p_, float(left_[1]), D_), 1.0 / (float(p_[-1, D_ + 1]) - 0.5)


def kill(s, v):
    """seat v dies: his respawn's stack (the simulator's rule), the killer scores"""
    s.frags_r[1 - v] += 1
    s.hp[v], s.armor[v] = 0.0, 0.0
    s.rsp_wait[v] = 10
    s.has[v] = False


def events():
    """(name, flat pay, before-state builder, the change, seconds left)"""
    L = []

    def base(lead=0, me=(100.0, 50.0), him=(100.0, 50.0)):
        def b(tab):
            s = S(tab)
            s.frags_r[:] = (max(lead, 0), max(-lead, 0))
            s.hp[:], s.armor[:] = (me[0], him[0]), (me[1], him[1])
            return s
        return b

    def hit(d, v=1):
        def f(s):
            take_ = min(s.armor[v], d * 2 / 3)               # (Quake's armor: two thirds into the armor)
            s.armor[v] -= take_
            s.hp[v] -= d - take_
        return f

    L.append(("100-damage rail hit, level, 5:00 left", DMG * 100, base(), hit(100), 300.0))
    L.append(("50 damage of LG, level, 5:00 left", DMG * 50, base(), hit(50), 300.0))
    L.append(("100-damage hit, level, 9:50 left", DMG * 100, base(), hit(100), 590.0))
    L.append(("100-damage hit, 3 up, 1:00 left", DMG * 100, base(3), hit(100), 60.0))
    L.append(("100-damage hit, 3 down, 1:00 left", DMG * 100, base(-3), hit(100), 60.0))

    def mega(s):
        s.hp[0] = min(200.0, s.hp[0] + 100.0)
    L.append(("mega health, level, 5:00 left (100+50 -> 200+50)", MH, base(), mega, 300.0))

    def red(s):
        s.armor[0] = min(200.0, s.armor[0] + 100.0)
    L.append(("red armor, level, 5:00 left (100+50 -> 100+150)", RA, base(), red, 300.0))

    def rlnew(s):
        s.has[0, E.RL] = True
    def base_norl(tab):
        s = base()(tab)
        s.has[:, E.RL] = False
        return s
    L.append(("rocket launcher taken (he had none, nor the enemy), level, 5:00", 0.10, base_norl, rlnew, 300.0))

    def frag(s):
        kill(s, 1)
    L.append(("frag, level, 9:50 left (him 100+50, the enemy at 20)", FRAG, base(0, him=(20.0, 0.0)), frag, 590.0))
    L.append(("frag, level, 5:00 left (him 100+50, the enemy at 20)", FRAG, base(0, him=(20.0, 0.0)), frag, 300.0))
    L.append(("frag, 3 up, 1:00 left (the enemy at 20)", FRAG, base(3, him=(20.0, 0.0)), frag, 60.0))
    L.append(("frag, 3 down, 1:00 left (the enemy at 20)", FRAG, base(-3, him=(20.0, 0.0)), frag, 60.0))

    def death(s):
        kill(s, 0)
    L.append(("death, 3 up, 1:00 left (he at 20)", -FRAG, base(3, me=(20.0, 0.0)), death, 60.0))
    L.append(("death, level, 5:00 left (he at 20)", -FRAG, base(0, me=(20.0, 0.0)), death, 300.0))

    def rj(s):
        s.hp[0] -= 50.0 * 1 / 3
        s.armor[0] -= 50.0 * 2 / 3                           # (his own splash, 50 after SELF_FACTOR; armor takes two thirds)
    L.append(("rocket jump, 50 self damage, level, 5:00 left", -DMG * 50, base(), rj, 300.0))
    return L


def trade(tab, scale, G, ks, left=300.0):
    """an even trade at 5:00: from both at 100+50, level: he takes 130 (to 20) and frags; then he is taken to 20 and fragged"""
    s0 = S(tab)
    s0.frags_r[:] = (0, 0)
    out = dict(flat=DMG * (130 - 130) + FRAG - FRAG + DMG * (130 - 130))
    seq = []
    s = s0.copy()
    seq.append(s.copy())
    s.hp[1], s.armor[1] = 20.0, 0.0                          # his 130 into the enemy
    seq.append(s.copy())
    kill(s, 1)
    seq.append(s.copy())
    s.hp[1], s.armor[1], s.rsp_wait[1] = 125.0, 0.0, 0       # (the respawn: no change by the rule)
    seq.append(s.copy())
    s.hp[0], s.armor[0] = 20.0, 0.0                          # the enemy's 130 into him
    seq.append(s.copy())
    kill(s, 0)
    seq.append(s.copy())
    w_ = [x.W(left) for x in seq]
    p_ = [x.psi(left) for x in seq]
    out["win"] = G * scale * (w_[-1] - w_[0])
    for k in ks:
        out["k{}".format(k)] = out["win"] + k * sum(GAMMA * p_[i + 1] - p_[i] for i in range(len(p_) - 1))
    return out


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--gain", type=float, default=1.75)
    ap.add_argument("--k", default="0,1,2,3,4")
    ap.add_argument("--json", default="")
    ap.add_argument("--md", default="")
    a = ap.parse_args()
    ks = [float(x) for x in a.k.split(",")]
    tab, scale = table()
    E.WIN_SHAPE_TAU = 32.5
    rows = []
    for name, flat, mk, ch, left in events():
        s = mk(tab)
        t = s.copy()
        ch(t)
        wt = G_ = a.gain * scale
        win_tab = G_ * (t.W(left, stack=False) - s.W(left, stack=False))
        win = G_ * (t.W(left) - s.W(left))
        dpsi = GAMMA * t.psi(left) - s.psi(left)
        r = dict(event=name, flat=round(flat, 3), win_table_only=round(win_tab, 3), win_stack=round(win, 3), dpsi=round(dpsi, 4))
        for k in ks:
            r["k{:g}".format(k)] = round(win + k * dpsi, 3)
        rows.append(r)
    tr = trade(tab, scale, a.gain, ks)
    rows.append(dict(event="even trade at 5:00 (each takes 130 and frags once), net", flat=round(tr["flat"], 3), win_table_only=0.0,
                     win_stack=round(tr["win"], 3), dpsi=None, **{"k{:g}".format(k): round(tr["k{}".format(k)], 3) for k in ks}))
    hdr = ["event", "flat (v0.5.0)", "win, table only", "win + stack term (G {:g})".format(a.gain), "dPSI"] + ["+ shaping k={:g}".format(k) for k in ks]
    lines = ["| " + " | ".join(hdr) + " |", "|" + "---|" * len(hdr)]
    for r in rows:
        lines.append("| " + " | ".join([r["event"], str(r["flat"]), str(r["win_table_only"]), str(r["win_stack"]),
                                         "" if r["dpsi"] is None else str(r["dpsi"])] + [str(r["k{:g}".format(k)]) for k in ks]) + " |")
    md = "\n".join(lines)
    print("WIN_SCALE {:.4f}, WIN_GAIN {:g}: a frag at 0:0 with ten minutes left = {:.3f} (table only)".format(scale, a.gain, a.gain))
    print(md)
    if a.json:
        json.dump(dict(gain=a.gain, ks=ks, scale=scale, rows=rows), open(a.json, "w"), indent=1)
    if a.md:
        open(a.md, "w").write(md + "\n")


if __name__ == "__main__":
    main()

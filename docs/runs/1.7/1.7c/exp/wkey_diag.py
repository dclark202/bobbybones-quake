"""1.7c, why the weapon push moves his hand so little: his weapon key at the frames it is read (env.key_dec), 1.7a's update-90 save
against itself, in the u90 check's settings (wpush.py's), on one or two maps. For his seats (the even ones; no swap): by the
weapon in hand (rockets, rail, lightning) and in view or not, the mean chance of "keep" and of each press, how often a press of
another weapon comes, and what changed his weapon: his key, or something else (an empty weapon: AUTO_SWITCH; a death).

    python docs/runs/1.7/1.7c/exp/wkey_diag.py [--push 1 --form ratio] [--maps bloodrun] [--games 4] [--minutes 5] [--affinity 0xC03C3]
"""
import argparse
import csv
import json
import os
import sys

import numpy as np

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
import wpush as WP                                            # noqa: E402  (ROOT, U90, hold_args, the settings)

ROOT = WP.ROOT
sys.path.insert(0, os.path.join(ROOT, "sim"))
sys.path.insert(0, os.path.join(ROOT, "tools"))
sys.path.insert(0, os.path.join(ROOT, "tools", "run"))


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--push", type=float, default=0.0)
    ap.add_argument("--form", default="ratio")
    ap.add_argument("--maps", default="bloodrun")
    ap.add_argument("--games", type=int, default=4)
    ap.add_argument("--minutes", type=float, default=5.0)
    ap.add_argument("--affinity", default="")
    a = ap.parse_args()
    if a.affinity:
        import ctypes
        from ctypes import wintypes
        k32 = ctypes.WinDLL("kernel32", use_last_error=True)
        k32.GetCurrentProcess.restype = wintypes.HANDLE
        k32.SetProcessAffinityMask.argtypes = [wintypes.HANDLE, ctypes.c_size_t]
        k32.SetProcessAffinityMask.restype = wintypes.BOOL
        assert k32.SetProcessAffinityMask(k32.GetCurrentProcess(), int(a.affinity, 16))
    os.environ["OPENBLAS_NUM_THREADS"] = "1"
    os.environ["PANEL_RUN"] = "duel_gru_1_7a"
    ref_ = json.load(open(os.path.join(WP.SR, "duel_gru_1_7a", "watch", "chk_90_prev_bloodrun.json")))["set"]
    envvars = {k: str(v) for k, v in ref_.items()}           # (the u90 check's, its SEAT_ values included: both sides the same save)
    os.environ.update(envvars)                               # (before any simulator module is imported: its switches are read then)
    import test_suite as T
    import duel_eval as DE
    names = [(r["group"], r["input"]) for r in csv.DictReader(open(os.path.join(ROOT, "docs", "INPUTS.csv"), encoding="utf-8"))]
    pol = T.Policy(WP.U90, seed=1)
    opp = T.Policy(WP.U90, seed=2)
    old = DE.fit_list(names, len(pol.mean))
    idx = np.array([names.index(x) for x in old])
    if a.push:
        pol.wpush = T.WeaponPush(a.push, old, a.form)
    ix = {n_[1]: i_ for i_, n_ in enumerate(old)}
    HOLD = [ix["holding " + w] for w in ("rocket launcher", "railgun", "lightning gun")]
    INV = ix["noticed in view"]
    OWN = [ix["owns " + w] for w in ("rocket launcher", "railgun", "lightning gun")]
    AMMO = [ix["ammo: " + w] for w in ("rocket launcher", "railgun", "lightning gun")]
    o_ = np.concatenate([[0], np.cumsum(pol.dims)]).astype(int)
    W0, W1 = int(o_[6]), int(o_[7])
    REC = dict(cur=None, rows=[])
    orig_act = T.Policy.act

    def act(self, obs, h, *x, **k):
        out, h2 = orig_act(self, obs, h, *x, **k)
        if self is pol:
            lg_ = self.last_logits[:, W0:W1].astype(np.float64).copy()
            if getattr(self, "wpush", None) is not None:
                lg_[:, 1:4] += self.wpush(obs)
            p_ = np.exp(lg_ - lg_.max(1, keepdims=True))
            p_ /= p_.sum(1, keepdims=True)
            hd_ = obs[:, HOLD] > 0.5
            REC["cur"] = dict(p=p_, want=out[:, 6].copy(), hold=np.where(hd_.any(1), hd_.argmax(1), 3), inv=obs[:, INV] > 0.5,
                              own=(obs[:, OWN] > 0.5) & (obs[:, AMMO] > 0.0))
        return out, h2
    T.Policy.act = act
    tot = {}
    for mp in a.maps.split(","):
        E = __import__("duel_env_ffa")
        orig_step = E.DuelEnv.step

        def step(self, acts, *x, **k):
            w0_ = self.weapon.copy()
            hp0_ = self.hp.copy()
            r = orig_step(self, acts, *x, **k)
            c_ = REC["cur"]
            if c_ is not None and len(c_["want"]) * 2 == self.n:
                ev_ = np.arange(0, self.n, 2)
                REC["rows"].append(dict(c_, dec=self.key_dec[ev_].copy(), w0=w0_[ev_], w1=self.weapon[ev_].copy(), alive=(hp0_[ev_] > 0) & (self.hp[ev_] > 0)))
                REC["cur"] = None
            return r
        E.DuelEnv.step = step
        job = ("duel_env_ffa", envvars, mp, a.games, a.minutes, 100, pol, idx, "policy", opp, idx,
               (600.0, 600.0, False), False, (125, 225, 125, 225))
        DE.play(job)
        E.DuelEnv.step = orig_step
    R = REC["rows"]
    print("frames recorded", len(R), "seats", len(R[0]["want"]) if R else 0, "| push", a.push, a.form if a.push else "")
    E = __import__("duel_env_ffa")
    WN = list(E.WEAPONS)
    big = [E.RL, E.RG, E.LG]
    P = np.concatenate([r["p"] for r in R])
    want = np.concatenate([r["want"] for r in R])
    hold = np.concatenate([r["hold"] for r in R])
    inv = np.concatenate([r["inv"] for r in R])
    dec = np.concatenate([r["dec"] for r in R])
    w0 = np.concatenate([r["w0"] for r in R])
    w1 = np.concatenate([r["w1"] for r in R])
    al = np.concatenate([r["alive"] for r in R])
    own = np.concatenate([r["own"] for r in R])
    print("owned with ammunition while alive: rockets / rail / lightning", np.round(own[al].mean(0), 3))
    print("frames alive", int(al.sum()), "| key read on", round(float(dec[al].mean()), 3), "of them")
    for hn, hj in (("rockets", 0), ("rail", 1), ("lightning", 2)):
        for vn, vm in (("out of view", ~inv), ("in view", inv)):
            m = al & dec & (hold == hj) & vm
            if m.sum() < 50:
                continue
            pm = P[m].mean(0)
            sw_key = (w1 != w0) & m & (want > 0) & (want - 1 == w1)
            print("  holding {:9s} {:11s}: read frames {:6d} | p keep {:.3f} | p press rl {:.4f} rg {:.4f} lg {:.4f} (own weapon key {:.3f}) | others {:.4f} | "
                  "switched by the key {:.4f} a read".format(hn, vn, int(m.sum()), pm[0], pm[1 + E.RL], pm[1 + E.RG], pm[1 + E.LG], pm[1 + big[hj]],
                                                             1.0 - pm[0] - pm[1 + E.RL] - pm[1 + E.RG] - pm[1 + E.LG], sw_key.sum() / m.sum()))
    ch = al & (w1 != w0)
    by_key = ch & (want > 0) & (want - 1 == w1) & dec
    print("weapon changes alive", int(ch.sum()), "| by his key on a read frame", int(by_key.sum()), "| other", int((ch & ~by_key).sum()))
    keyless = ch & ~by_key
    if keyless.any():
        pr = {}
        for x0, x1 in zip(w0[keyless], w1[keyless]):
            pr["{}->{}".format(WN[x0], WN[x1])] = pr.get("{}->{}".format(WN[x0], WN[x1]), 0) + 1
        print("  the other changes:", dict(sorted(pr.items(), key=lambda kv: -kv[1])[:10]))
    pr = {}
    for x0, x1 in zip(w0[by_key], w1[by_key]):
        pr["{}->{}".format(WN[x0], WN[x1])] = pr.get("{}->{}".format(WN[x0], WN[x1]), 0) + 1
    print("  his key's changes:", dict(sorted(pr.items(), key=lambda kv: -kv[1])[:12]))
    sec = al.sum() * 0.025
    print("  changes a minute alive: by key {:.1f}, other {:.1f}".format(by_key.sum() / sec * 60, (ch & ~by_key).sum() / sec * 60))


if __name__ == "__main__":
    main()

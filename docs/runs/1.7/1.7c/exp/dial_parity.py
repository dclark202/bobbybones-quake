"""The weapon dial on the servers against the checks' (owner, 2026-11-07: "Build the dial for play against people"): 1.7a's update-90
save exported as the servers load it (sim/export_duel.py), driven through the plugins' forward pass (plugins/netpass.py step(), the
dial at P["_wdial"] as plugins/duelbot.py sets it) and the checks' (sim/test_suite.py Policy, WeaponPush form "dial", as the simulator
measurements of light and strong ran), on the same inputs: random about the network's input means, with the dial's own columns made
real (one weapon in hand, owned weapons with ammunition, the enemy in view or not, his last known place at every distance).
Checks, at off, light and strong: the network's logits the same in both every frame; what the plugin draws from = the network's
logits + sim/weapon_dial.py push on the presses of rockets, rail and the lightning gun and nothing else; off = the network's own.

    python docs/runs/1.7/1.7c/exp/dial_parity.py <the export of 1.7a's update 90, policy_trained.npz>"""
import os
import sys

import numpy as np

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.dirname(os.path.dirname(HERE)))))
sys.path.insert(0, os.path.join(ROOT, "sim"))
sys.path.insert(0, os.path.join(ROOT, "plugins"))
import netpass as NP  # noqa: E402
import test_suite as T  # noqa: E402
import weapon_dial as WD  # noqa: E402

OK = [True]
U90 = os.path.join(ROOT, "data", "sim_runs", "duel_gru_1_7a", "keep", "policy_90.pt")


def check(name, c):
    OK[0] = OK[0] and bool(c)
    print(("PASS " if c else "FAIL ") + name, flush=True)


def main():
    npz = sys.argv[1]
    P, Aa = NP.load(npz)
    pol = T.Policy(U90, seed=7)
    o_ = np.concatenate([[0], np.cumsum(pol.dims)]).astype(int)
    W0 = int(o_[6])
    seen = {}
    orig_draw = NP.draw

    def draw(P_, logits, rng):
        seen["l"] = np.array(logits, copy=True)
        return orig_draw(P_, logits, rng)
    NP.draw = draw
    B, F = 8, 200
    rng = np.random.default_rng(3)
    for lv, p in WD.LEVELS.items():
        pol.wpush = T.WeaponPush(p, [], "dial") if p else None
        h_t, h_n = pol.zeros(B), np.zeros((B, NP.width(P)), np.float32)
        pose = np.zeros((B, 4), np.float32)
        zmap = np.zeros(B, np.int64)
        nrng = np.random.default_rng(9)
        dl = dw = dother = 0.0
        npush = 0
        rows = np.zeros(4, int)
        for t in range(F):
            raw = rng.normal(pol.mean, np.sqrt(pol.var) + 1e-3, size=(B, len(pol.mean))).astype(np.float32)
            raw[:, list(WD.HOLD)] = 0.0
            raw[np.arange(B), np.array(WD.HOLD)[rng.integers(0, 3, B)]] = 1.0
            raw[:, list(WD.OWN)] = (rng.random((B, 3)) < 0.7)
            raw[:, list(WD.AMMO)] = rng.uniform(0.0, 1.0, (B, 3)) * (rng.random((B, 3)) < 0.9)
            raw[:, WD.INVIEW] = rng.random(B) < 0.5
            raw[:, list(WD.POS)] = rng.normal(0, 1, (B, 3)) * rng.uniform(0.05, 0.6, (B, 1))
            pose[:, :3] += rng.normal(0, 10, (B, 3)).astype(np.float32)
            pose[:, 3] = rng.uniform(-180, 180, B)
            kf = np.stack([rng.uniform(0, 16, B), (rng.random(B) < 0.3), rng.integers(0, pol.dims[10], B), np.zeros(B), np.zeros(B),
                           np.full(B, 20.0), np.full(B, 20.0)], 1).astype(np.float32)
            xl = rng.normal(0, 1, (B, pol.legsP[0].shape[1])).astype(np.float32) if pol.needs_xl else None
            kw = {"xl": xl} if xl is not None else {}
            P["_wdial"] = p                                  # (plugins/duelbot.py act(): self.WDIAL_LEVELS[self.wdial])
            at, h_t = pol.act(raw, h_t, pose=pose, zmap=zmap, kf=kf, **kw)
            an, h_n = NP.step(P, Aa, raw, h_n, nrng, pose=pose, zmap=zmap, kf=kf, **kw)
            dl = max(dl, float(np.abs(pol.last_logits - P["_logits"]).max()))
            want = np.array(P["_logits"], np.float64, copy=True)
            add = WD.push(raw, p)
            want[:, W0 + 1:W0 + 4] += add
            if p:
                ts_ = T.WeaponPush(p, [], "dial")(raw)        # (the checks' add, as Policy.act makes it)
                dw = max(dw, float(np.abs(ts_ - add).max()))
            d_ = np.abs(seen["l"] - want)
            dother = max(dother, float(d_.max()))
            npush += int((np.abs(add) > 0).any(1).sum())
            rows += np.bincount(WD.situation(raw), minlength=4)
        check("{} (p {:g}): the network's logits the same in both (largest difference {:.3g})".format(lv, p, dl), dl < 1e-3)
        check("{}: the plugin draws from the network's logits + the dial's push, nothing else (largest difference {:.3g})".format(lv, dother),
              dother < 1e-5)
        if p:
            check("{}: the checks' push the same as the plugin's (largest difference {:.3g}); pushed rows {} of {}; rows by situation {}".format(
                lv, dw, npush, B * F, rows.tolist()), dw < 1e-6 and npush > 0)
        else:
            check("off: nothing pushed ({} rows)".format(npush), npush == 0)
    print("ALL PASSED" if OK[0] else "FAILED")
    return 0 if OK[0] else 1


if __name__ == "__main__":
    sys.exit(main())

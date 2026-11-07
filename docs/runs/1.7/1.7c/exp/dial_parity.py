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

os.environ["WDIAL_RAIL"] = "1"                               # the target rule on for its checks (off by default in play: weapon_dial.TARGET_ON)
HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.dirname(os.path.dirname(HERE)))))
sys.path.insert(0, os.path.join(ROOT, "sim"))
sys.path.insert(0, os.path.join(ROOT, "plugins"))
import netpass as NP  # noqa: E402
import test_suite as T  # noqa: E402
import weapon_dial as WD  # noqa: E402

OK = [True]
U90 = os.environ.get("U90") or os.path.join(ROOT, "data", "sim_runs", "duel_gru_1_7a", "keep", "policy_90.pt")   # (U90=<path>: from a worktree without data/)


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
    # the replace form ("pros", 11-07 evening): both paths seeded alike draw alike, so the weapon key's action must be the same in
    # both every frame; every press is of one of the three he owns with ammunition; where he owns none of them the network's own
    # key stands (the same as a run with the dial off on the same numbers); he presses when the row forbids the weapon in hand
    NP.draw = orig_draw
    pol_r, pol_0 = T.Policy(U90, seed=11), T.Policy(U90, seed=11)
    pol_r.wpush = T.WeaponPush(1.0, [], "replace")
    pol_r.wrng = np.random.default_rng(77)                   # the dial's own stream, the same in both paths
    P["_wdial"], P["_wdial_mode"], P["_wdial_state"], P["_wdial_rng"] = 0.0, "replace", {}, np.random.default_rng(77)
    h_r, h_0, h_n = pol_r.zeros(B), pol_0.zeros(B), np.zeros((B, NP.width(P)), np.float32)
    nrng = np.random.default_rng(11)
    pol_r.krng, pol_0.krng = np.random.default_rng(5), np.random.default_rng(5)   # (the keep choice's own stream, alike in both)
    rng = np.random.default_rng(3)
    pose, zmap = np.zeros((B, 4), np.float32), np.zeros(B, np.int64)
    same_tn = same_none = True
    bad_press = presses = forced = none_rows = 0
    tgt_same = True
    tgt_n = tgt_bad = tgt_could = 0
    prev = None
    for t in range(F):
        raw = rng.normal(pol_r.mean, np.sqrt(pol_r.var) + 1e-3, size=(B, len(pol_r.mean))).astype(np.float32)
        raw[:, list(WD.HOLD)] = 0.0
        raw[np.arange(B), np.array(WD.HOLD)[rng.integers(0, 3, B)]] = 1.0
        raw[:, list(WD.OWN)] = (rng.random((B, 3)) < 0.6)
        raw[:, list(WD.AMMO)] = rng.uniform(0.0, 1.0, (B, 3)) * (rng.random((B, 3)) < 0.9)
        raw[:, WD.INVIEW] = rng.random(B) < 0.5
        raw[:, list(WD.POS)] = rng.normal(0, 1, (B, 3)) * rng.uniform(0.05, 0.6, (B, 1))
        raw[:, WD.HEALTH] = rng.uniform(0.0, 1.0, B)          # (the target rule's columns made real)
        raw[:, WD.DEAD] = rng.random(B) < 0.1
        for it_ in (WD.ITEM_RL, WD.ITEM_RG):
            raw[:, it_["exists"]] = rng.random(B) < 0.8
            raw[:, it_["gone"]] = rng.random(B) < 0.1
            raw[:, list(it_["pos"])] = rng.normal(0, 1, (B, 3)) * rng.uniform(0.1, 1.0, (B, 1))
        pose[:, :3] += rng.normal(0, 10, (B, 3)).astype(np.float32)
        pose[:, 3] = rng.uniform(-180, 180, B)
        kf = np.stack([rng.uniform(0, 16, B), (rng.random(B) < 0.3), rng.integers(0, pol_r.dims[10], B), np.zeros(B), np.zeros(B),
                       np.full(B, 20.0), np.full(B, 20.0)], 1).astype(np.float32)
        xl = rng.normal(0, 1, (B, pol_r.legsP[0].shape[1])).astype(np.float32) if pol_r.needs_xl else None
        kw = {"xl": xl} if xl is not None else {}
        ar, h_r = pol_r.act(raw, h_r, pose=pose, zmap=zmap, kf=kf, **kw)
        a0, h_0 = pol_0.act(raw, h_0, pose=pose, zmap=zmap, kf=kf, **kw)
        an, h_n = NP.step(P, Aa, raw, h_n, nrng, pose=pose, zmap=zmap, kf=kf, **kw)
        own_ = (raw[:, list(WD.OWN)] > 0.5) & (raw[:, list(WD.AMMO)] > 0.0)
        row_ = WD.situation(raw)
        any_ = ((WD.TABLE[row_] >= WD.FLOOR) & own_).any(1)   # the row allows one of the three he owns
        same_tn = same_tn and bool((ar[:, 6] == an[:, 6]).all())
        tgt_same = tgt_same and bool((ar[:, 10] == an[:, 10]).all())
        spoke_ = ar[:, 10] != a0[:, 10]                        # the target rule spoke (the intention differs from the dial-off draw)
        could_ = (raw[:, WD.INVIEW] < 0.5) & (raw[:, WD.DEAD] < 0.5) & (raw[:, WD.HEALTH] >= WD.HEALTH_FLOOR) & own_[:, 0] & (
            ~own_[:, 1] & (raw[:, WD.ITEM_RG["exists"]] > 0.5) & (raw[:, WD.ITEM_RG["gone"]] < 0.5))   # (a trip begun near may go on from far)
        tgt_n += int(spoke_.sum())
        tgt_could += int(could_.sum())
        tgt_bad += int((spoke_ & ~could_).sum()) + int((spoke_ & (ar[:, 10] != WD.INTENT_RG)).sum())
        same_none = same_none and bool((ar[~any_, 6] == a0[~any_, 6]).all()) and bool((ar[:, :6] == a0[:, :6]).all()) \
            and bool((ar[:, 7:10] == a0[:, 7:10]).all()) and bool((ar[:, 11:] == a0[:, 11:]).all())   # every other output as with the dial off
        none_rows += int((~any_).sum())
        pr_ = any_ & (ar[:, 6] > 0)
        presses += int(pr_.sum())
        bad_press += int((pr_ & ~own_[np.arange(B), np.clip(ar[:, 6] - 1, 0, 2)]).sum())
        hd_ = np.array(WD.HOLD)[None, :] == np.array(WD.HOLD)[raw[:, list(WD.HOLD)].argmax(1)][:, None]
        forbid_ = any_ & (WD.TABLE[row_][hd_] < WD.FLOOR)   # the weapon in hand gets nothing in this row (and the row allows another he owns)
        forced += int((forbid_ & (ar[:, 6] == 0)).sum())
    check("pros: the weapon key's action the same in the checks' path and the plugin's every frame ({} frames x {} players)".format(F, B), same_tn)
    check("pros: where the row allows none of the three he owns the network's own key stands ({} rows), and every other output is "
          "exactly the dial-off draw".format(none_rows), same_none and none_rows > 0)
    check("pros: every press is of a weapon he owns with ammunition ({} presses, {} not owned)".format(presses, bad_press), presses > 0 and bad_press == 0)
    check("pros: the weapon in hand forbidden by the row is never kept ({} kept)".format(forced), forced == 0)
    check("pros: the target rule's intention the same in both paths every frame", tgt_same)
    check("pros: the target rule spoke on {} rows of {} where it may (random inputs: a trip rarely outlives a frame), {} where it may not or "
          "with another target".format(tgt_n, tgt_could, tgt_bad), tgt_bad == 0 and tgt_n > 0)
    print("ALL PASSED" if OK[0] else "FAILED")
    return 0 if OK[0] else 1


if __name__ == "__main__":
    sys.exit(main())

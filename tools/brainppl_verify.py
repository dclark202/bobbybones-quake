"""(brainppl) the replay of a simulator game against the simulator's own record: the inputs and the brain's lesson labels.

    python tools/brainppl_verify.py <sim shard> <replayed shard of the same match's session> [--seat 0]

The simulator's record is the truth (sim/brain_data.py sim, its first match written as a session with --write-sessions);
the replay (sim/brain_data.py session) rebuilds Bobby's inputs and the labels from what a session log holds. Reported: the
share of input columns that agree, the label columns' agreement, and the lessons' labels (track, track_z, ahead incl. the race)
made by the trainer's own code from each, on the frames both have.
"""
import argparse
import json
import os
import sys

import numpy as np

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(HERE)
sys.path.insert(0, os.path.join(ROOT, "sim"))


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("sim")
    ap.add_argument("rep")
    ap.add_argument("--seat", type=int, default=0)
    ap.add_argument("--json", default=None)
    a = ap.parse_args()
    import torch
    import ahead as ahead_
    import brain_data as BD
    zs, zr = np.load(a.sim), np.load(a.rep)
    cols = json.loads(str(zs["meta"]))["cols"]
    C = {k: i for i, k in enumerate(cols)}
    s = a.seat
    sobs, sdone, saux = zs["obs"][:, s].astype(np.float32), zs["done"][:, s], zs["aux"][:, s]
    rows = zr["row"]
    robs, rdone, raux = zr["obs"][:, 0].astype(np.float32), zr["done"][:, 0], zr["aux"][:, 0]
    fs = rows + 1                                            # (session row r: the state after step r = the simulator's frame r + 1)
    ok = fs < len(sobs)
    fs = fs[ok]
    n = len(fs)
    rep = {}
    # the inputs
    A, B = sobs[fs], robs[:n]
    sd = np.maximum(sobs.std(0), 1e-3)
    close = (np.abs(A - B) <= np.maximum(0.01, 0.02 * sd))
    rep["inputs"] = dict(frames=int(n), cols_95=round(float((close.mean(0) >= 0.95).mean()), 4), cells_close=round(float(close.mean()), 4),
                         mean_abs_err_over_sd=round(float((np.abs(A - B) / sd).mean()), 4))
    # the label columns, frame by frame
    lab = {}
    for k in BD.TRACK_COLS + BD.TRZ_COLS + ("en_in_view", "trk_on", "mega_s", "red_s", "race_me_mh", "race_en_mh", "race_me_ra", "race_en_ra", "x", "y", "z", "yaw"):
        x, y = saux[fs, C[k]], raux[:n, C[k]]
        tol = 1.0 if k in ("x", "y", "z", "en_fwd", "en_left", "en_up") else 0.5 if k.startswith(("en_v", "en_spd", "en_mv")) else 0.05
        if k == "yaw":
            dd = np.abs((x - y + 180) % 360 - 180)
        else:
            dd = np.abs(x - y)
        on_ = (saux[fs, C["trk_on"]] > 0.5)                  # (the frames the lessons are taught on)
        lab[k] = dict(all=round(float((dd <= tol).mean()), 4), trk_on=round(float((dd <= tol)[on_].mean()), 4) if on_.any() else None)
    rep["label_cols_agree"] = lab
    # the target: the simulator's own (the enemy network's intention) against the person's proxy (next big pickup in 15 s)
    ts_, tp_ = saux[fs, C["en_target_sim"]].astype(int), raux[:n, C["en_target"]].astype(int)
    tps_ = saux[fs, C["en_target_ppl"]].astype(int)
    m_ = tp_ >= 0
    rep["target"] = dict(proxy_frames=round(float(m_.mean()), 4), proxy_replay_vs_sim_proxy=round(float((tp_[m_] == tps_[m_]).mean()), 4) if m_.any() else None,
                         proxy_vs_intention=round(float((tp_[m_] == ts_[m_]).mean()), 4) if m_.any() else None)
    # the trainer's labels from each, on the replay's frames (a stream of his living frames: the simulator's rows taken at fs)
    K = 8
    T = (n // K) * K
    def labels(aux_, done_):
        x = torch.from_numpy(np.ascontiguousarray(aux_[:T + 1, None, :][..., [C[c] for c in ahead_.COLS + ahead_.COLS_RACE]])).float()
        d = torch.from_numpy(np.ascontiguousarray(done_[:T, None].astype(np.float32)))
        return ahead_.labels(x, d, tuple(ahead_.COLS + ahead_.COLS_RACE), K, 17, race=True)
    sd_ = np.zeros(n, bool)                                  # (the simulator's done, carried to the frames kept: a death between two kept frames)
    cs_ = np.concatenate([[0], np.cumsum(sdone.astype(np.int64))])
    sd_[:-1] = (cs_[fs[1:]] - cs_[fs[:-1]]) > 0
    sa_ = saux[np.concatenate([fs, fs[-1:]])].copy()
    sa_[:, C["en_target"]] = sa_[:, C["en_target_ppl"]]      # (the same target question on both sides)
    ys, yr = labels(sa_, sd_), labels(raux[:n + 1], rdone[:n])
    names = ("fut", "fut_m", "target", "target_m", "appear", "appear_m", "lead", "lead_m", "there", "there_m")
    lb = {}
    for nm, u, v in zip(names, ys, yr):
        u, v = u.float(), v.float()
        if nm == "fut":
            m2 = (ys[1] > 0.5) & (yr[1] > 0.5)
            e = (u - v).norm(dim=-1)[m2] * 1000.0
            lb[nm] = dict(median_units=round(float(e.median()), 2) if len(e) else None, within_5u=round(float((e < 5).float().mean()), 4) if len(e) else None)
        elif nm.endswith("_m"):
            lb[nm] = round(float((u == v).float().mean()), 4)
        elif nm == "lead":
            m2 = (ys[7] > 0.5) & (yr[7] > 0.5)
            lb[nm] = round(float(((u - v).abs() <= 0.05)[m2].float().mean()), 4) if m2.any() else None
        else:
            mk = {"target": 3, "appear": 5, "there": 9}[nm]
            m2 = (ys[mk] > 0.5) & (yr[mk] > 0.5)
            lb[nm] = round(float((u == v)[m2].float().mean()), 4) if m2.any() else None
    rep["ahead_labels"] = lb
    trk_s, trk_r = saux[fs, C["trk_on"]] > 0.5, raux[:n, C["trk_on"]] > 0.5
    rep["trk_on"] = dict(sim=round(float(trk_s.mean()), 4), replay=round(float(trk_r.mean()), 4), agree=round(float((trk_s == trk_r).mean()), 4))
    rep["done"] = dict(sim=int(sd_.sum()), replay=int(rdone[:n].sum()))
    print(json.dumps(rep, indent=1))
    if a.json:
        json.dump(rep, open(a.json, "w"), indent=1)


if __name__ == "__main__":
    main()

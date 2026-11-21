"""2.2c (docs/runs/2.2/2.2c/CARD.md change 1, "What he needs to see"; CLAUDE.md "Inputs"): a network of list 22b brought to list 22c, with nothing
of it in effect, so that it answers as before.

List 22c (sim/input_list_22c.json, made here by `list`): list 22b with two changes to the hands' part, read by their encoder only (no new
attention token):
  * the yellow armors' timers (group "b17b timers": known to be taken, how long ago; the second yellow the same): in list 22b they sat in the
    tail, read by no network's first layer; now at the end of the hands' part
  * the brain's places ahead (group "b22c ahead", the simulator's AHEAD_IN: where its readout ahead expects the enemy in 1, 2 and 4 s from his
    eye, and that there is an answer), after them
The tail keeps the guessing lesson's four marks. The brain reads its 691 as before.

    python tools/inputs22c.py list
        writes sim/input_list_22c.json and docs/INPUTS_22c.csv
    python tools/inputs22c.py convert <list22b.pt> <out.pt>
        the hands' encoder: the 17 columns at zero weights after its 823; every column number of the file moved by NAME (the head's obs_cols, the
        fight network's, the attention's kinds, the rule fade's, the brain token's seen_col; a column list it does not know: refused); the timers'
        statistics carried (they were measured with the list), the ahead columns' by design until `stats` measures them
    python tools/inputs22c.py stats <list22c.pt> <rows.npz> <out.pt>
        the ahead columns' mean and spread from real rows (docs/runs/2.2/2.2c/sample22c.py: the start playing with AHEAD_IN on); refused unless
        every weight on them is still zero; a column constant in the sample keeps its design statistics
The optimizer needs no file of its own: the trainer's --opt-small-items carries enc.0.weight over (its end-appended columns: the first 803 are
list 20e's, as 2.2a's optimizer has them)."""
import argparse
import csv
import json
import os
import sys

import numpy as np

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, os.path.join(ROOT, "sim"))
OLD, NEW = "22b", "22c"
TIMERS, AHEAD = "b17b timers", "b22c ahead"
NUM, FLAG = (0.0, 0.1), (0.1, 0.09)                          # (mean, variance) by design, as tools/inputs21.py's


def make_list():
    import input_list as IL
    B = json.load(open(IL.path(OLD), encoding="utf-8"))
    R = IL.full_rows()
    nh = int(B["n_hands"])
    tail = B["names"][nh:]
    tim = [x for x in tail if x[0] == TIMERS]
    marks = [x for x in tail if x[0] != TIMERS]
    assert len(tim) == 4 and len(marks) == 4, (len(tim), len(marks))
    ah = [[r["group"], r["input"]] for r in R if r["group"] == AHEAD]
    assert len(ah) == 13, len(ah)
    names = B["names"][:nh] + tim + ah + marks
    L = dict(version=NEW, base=OLD, full=len(R), n_brain=int(B["n_brain"]), n_hands=nh + len(tim) + len(ah), names=names, cut=B["cut"],
             added=[TIMERS + " (moved from the tail into the hands' part)", AHEAD],
             note="brain = the first n_brain; the hands' encoder = the first n_hands; the tail is read by no first layer")
    json.dump(L, open(IL.path(NEW), "w", encoding="utf-8"), indent=0)
    full = {(r["group"], r["input"]): r for r in R}
    with open(os.path.join(ROOT, "docs", "INPUTS_{}.csv".format(NEW)), "w", encoding="utf-8", newline="") as f:
        w = csv.writer(f, lineterminator=chr(10))
        w.writerow(["index", "group", "input", "meaning", "scale", "added in", "read by"])
        for j, (g, n) in enumerate(L["names"]):
            r = full[(g, n)]
            who = "brain, hands" if j < L["n_brain"] else ("hands" if j < L["n_hands"] else "none (the guessing lesson's marks)")
            w.writerow([j, g, n, r["meaning"], r["scale"], r["added in"], who])
    print("list {}: {} inputs; the brain the first {}, the hands the first {} (the yellows' timers 4 and the brain's places ahead 13 added to "
          "the hands' part), the tail {}".format(NEW, len(names), L["n_brain"], L["n_hands"], len(names) - L["n_hands"]))


def lists():
    import input_list as IL
    return IL.load(OLD), IL.load(NEW)


def new_cols(Ln, group=AHEAD):
    return [j for j, (g, _) in enumerate(Ln["names"]) if g == group]


def convert(a):
    import torch
    Lo, Ln = lists()
    ck = torch.load(a.inp, weights_only=False, map_location="cpu")
    I = ck.get("inputs") or {}
    assert str(I.get("list", -1)) == OLD and [tuple(x) for x in ck["input_names"]] == [tuple(x) for x in Lo["names"]], "not a network of list " + OLD
    sd = ck["model"]
    nh0, n0, nh1, n1 = int(Lo["n_hands"]), int(Lo["n"]), int(Ln["n_hands"]), int(Ln["n"])
    assert n1 == n0 + 13 and nh1 == nh0 + 17 and Ln["n_brain"] == Lo["n_brain"]
    assert [tuple(x) for x in Ln["names"][:nh0]] == [tuple(x) for x in Lo["names"][:nh0]]
    pos_new = {tuple(x): j for j, x in enumerate(Ln["names"])}
    mp = {i: pos_new[tuple(x)] for i, x in enumerate(Lo["names"])}            # (an old column's number in the new list, by name)
    sh = lambda c: mp[int(c)]   # noqa: E731
    # ---- the hands' encoder: the 17 columns at zero weights after its 823
    W = sd["enc.0.weight"]
    assert tuple(W.shape)[1] == nh0, (tuple(W.shape), nh0)
    sd["enc.0.weight"] = torch.cat([W, torch.zeros(W.shape[0], nh1 - nh0, dtype=W.dtype)], 1)
    rows = {(r["group"], r["input"]): r for r in csv.DictReader(open(os.path.join(ROOT, "docs", "INPUTS.csv"), encoding="utf-8"))}
    ahc = new_cols(Ln)
    for key, col in (("obs_mean", 0), ("obs_var", 1)):
        v = np.asarray(ck[key], np.float64)
        assert len(v) == n0
        out = np.zeros(n1, np.float64)
        for i_, j_ in mp.items():
            out[j_] = v[i_]                                  # (the timers' too: measured with the list)
        for j_ in ahc:
            out[j_] = (FLAG if rows[tuple(Ln["names"][j_])]["scale"].strip() == "0 or 1" else NUM)[col]
        ck[key] = out.astype(np.asarray(ck[key]).dtype)
    if "obs_count" in ck and np.ndim(ck["obs_count"]) == 1 and len(ck["obs_count"]) == n0:
        oc_ = np.asarray(ck["obs_count"])
        out = np.zeros(n1, oc_.dtype)
        for i_, j_ in mp.items():
            out[j_] = oc_[i_]
        ck["obs_count"] = out
    ck["obs_dim"] = n1
    moved = []
    # ---- the attention part: every kind's column numbers by name (no new token: the encoder reads the new columns)
    lay = dict(ck["attn"])
    assert int(lay["obs_dim"]) == n0 and lay.get("gated")
    lay["kinds"] = [dict(k, idx=[[(c if int(c) < 0 else sh(c)) for c in row] for row in k["idx"]]) for k in lay["kinds"]]
    lay["obs_dim"] = n1
    ck["attn"] = lay
    moved.append("the attention's {} kinds".format(len(lay["kinds"])))
    if ck.get("rule_fade") is not None:
        rf = dict(ck["rule_fade"])
        rf["cols"] = [sh(c) for c in rf["cols"]]
        if rf.get("more") and rf["more"].get("cols"):
            rf["more"] = dict(rf["more"], cols=[sh(c) for c in rf["more"]["cols"]])
        ck["rule_fade"] = rf
        moved.append("the rule fade's {}".format(len(rf["cols"])))
    if ck.get("head2") is not None:
        h2 = dict(ck["head2"])
        for key in ("obs_cols", "wobs_cols"):
            if h2.get(key) is not None:
                h2[key] = [sh(c) for c in h2[key]]
                moved.append("the head's {} ({})".format(key, len(h2[key])))
        for k2, v2 in list(h2.items()):                      # (the head's parts' own column lists: the tracker's obs_cols, ...)
            if isinstance(v2, dict):
                v2 = dict(v2)
                for k3, v3 in list(v2.items()):
                    if k3.endswith("obs_cols") and isinstance(v3, (list, tuple)):
                        v2[k3] = [sh(c) for c in v3]
                        moved.append("the head's {}['{}'] ({})".format(k2, k3, len(v3)))
                h2[k2] = v2
        ck["head2"] = h2
    if ck.get("fight22") is not None:
        F = dict(ck["fight22"])
        L = dict(F["layout"])
        L["obs_cols"] = [sh(c) for c in L["obs_cols"]]
        F["layout"] = L
        ck["fight22"] = F
        moved.append("the fight network's obs_cols ({})".format(len(L["obs_cols"])))
    if ck.get("btoken") is not None and "seen_col" in ck["btoken"]:
        ck["btoken"] = dict(ck["btoken"], seen_col=sh(ck["btoken"]["seen_col"]))
        moved.append("the brain token's seen_col")
    for key in ("belief", "track", "track_z", "ahead", "control", "fightodds", "spaceread", "passodds"):
        d = ck.get(key)
        if isinstance(d, dict):
            for k2, v2 in d.items():
                nums_ = isinstance(v2, (int, np.integer)) or (isinstance(v2, (list, tuple, np.ndarray)) and len(v2) > 0
                                                               and all(isinstance(x_, (int, np.integer)) for x_ in np.asarray(v2, object).ravel()))
                if (k2.endswith("cols") or k2.endswith("_col")) and nums_:
                    raise SystemExit("{}['{}'] holds column numbers this converter does not move: add it".format(key, k2))
    ck["inputs"] = dict(I, list=NEW, n=n1, n_brain=int(Ln["n_brain"]), n_hands=nh1, full=int(Ln["full"]), design_stats=[ahc[0], ahc[-1] + 1],
                        ahead=[ahc[0], ahc[-1] + 1], timers=[nh0, nh0 + 4])
    ck["input_names"] = [list(x) for x in Ln["names"]]
    ck["env_module"] = "duel_env_ffa{}".format(NEW)
    torch.save(ck, a.out)
    print("wrote {}: list {} ({} inputs; the brain the first {}, the hands the first {}, the tail {}); 17 hands' columns at zero weights (the "
          "yellows' timers, their statistics carried; the brain's places ahead, design statistics); moved by name: {}".format(
              a.out, NEW, n1, Ln["n_brain"], nh1, n1 - nh1, "; ".join(moved)))


def stats(a):
    import torch
    _, Ln = lists()
    ck = torch.load(a.inp, weights_only=False, map_location="cpu")
    assert str((ck.get("inputs") or {}).get("list", -1)) == NEW, "not a network of list " + NEW
    nh0 = int(Ln["n_hands"]) - 17
    zc = list(range(nh0, int(Ln["n_hands"])))
    assert not ck["model"]["enc.0.weight"][:, zc].any(), "a weight on the 17 columns is no longer zero: the statistics stay"
    cols = new_cols(Ln)
    z = np.load(a.rows)
    X = np.asarray(z["ahead"], np.float64)
    assert X.shape[1] == len(cols), (X.shape, len(cols))
    m, v = X.mean(0), X.var(0)
    keep = v <= 1e-6
    mean, var = np.asarray(ck["obs_mean"], np.float64).copy(), np.asarray(ck["obs_var"], np.float64).copy()
    mean[cols] = np.where(keep, mean[cols], m)
    var[cols] = np.where(keep, var[cols], v)
    ck["obs_mean"], ck["obs_var"] = mean.astype(np.asarray(ck["obs_mean"]).dtype), var.astype(np.asarray(ck["obs_var"]).dtype)
    ck["inputs"] = dict(ck["inputs"], design_stats=None, ahead_measured=dict(rows=int(len(X)), file=os.path.basename(a.rows),
                                                                             design_kept=[Ln["names"][cols[i]][1] for i in np.nonzero(keep)[0]]))
    torch.save(ck, a.out)
    print("wrote {}: the brain's places ahead: {} columns' statistics from {} rows ({} constant, their design kept)".format(a.out, len(cols), len(X), int(keep.sum())))
    for j_, c_ in enumerate(cols):
        print("  {:<48s} mean {:+.4f} sd {:.4f}".format(Ln["names"][c_][1], float(mean[c_]), float(np.sqrt(var[c_]))))


def main():
    ap = argparse.ArgumentParser()
    sp = ap.add_subparsers(dest="cmd", required=True)
    sp.add_parser("list")
    p = sp.add_parser("convert")
    p.add_argument("inp")
    p.add_argument("out")
    p = sp.add_parser("stats")
    p.add_argument("inp")
    p.add_argument("rows")
    p.add_argument("out")
    a = ap.parse_args()
    if a.cmd == "list":
        make_list()
    else:
        {"convert": convert, "stats": stats}[a.cmd](a)


if __name__ == "__main__":
    main()

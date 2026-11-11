"""The cleaned input list (owner, 2026-11-11; docs/design/INPUTS_CLEANUP.md): which of the simulator's inputs a network is given, by NAME.

The simulator (sim/duel_env_ffa.py) keeps building its full list (docs/INPUTS.csv, 1,053 columns). A list here is a selection of those by
(group, input), in three parts, in this order:
    brain   the columns the brain reads (and the hands too): the first n_brain
    hands   the columns only the hands read (the small items): up to n_hands. The hands' encoder reads the first n_hands, the brain the
            first n_brain
    tail    kept in the list, read by no network's first layer: the 76 rule-made columns that were faded out of the hands (v0.4.2) and of
            the brain (b1.1) (the trainer's guessing lesson reads five of them as marks; the pre-fire and emergence stay on the owner's
            word), and the yellow armors' timers (the strategy head's own columns only)
What is not in a list is cut: dead by construction (a part that is off for good, a ray outside his field of view, a hazard the maps do not
have, a flag that is always 1 on the ten maps, the order / space / targets inputs that were never opened). A column that only never
changed in self-play (the enemy crouched, a gauntlet in his hand, a fifth projectile in view) is NOT cut: a person can cause it.

    python sim/input_list.py build 18 <a sample of raw inputs: obs.npy, 1,053 wide>     writes sim/input_list_18.json and docs/INPUTS_18.csv
    python sim/input_list.py show 18

sim/duel_env_ffa18.py is the simulator that gives this list; tools/inputs18.py converts a network to it."""
import csv
import json
import os
import sys

import numpy as np

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
FULL_CSV = os.path.join(ROOT, "docs", "INPUTS.csv")
CUT_GROUPS = {"more enemies": "free-for-all only", "movement goal": "movement rounds and courses only", "style": "STYLE_P=0 since v0.3",
              "his legs": "the legs switch was retired", "v038 drift": "DRIFT_IN=0", "b17 order": "never opened (2.1 defines its own)",
              "b20b space": "never opened (2.0b)", "b20b targets": "never opened (2.0b)"}
TAIL_GROUPS = ("b17b timers",)                              # the strategy head's only


def full_rows():
    return list(csv.DictReader(open(FULL_CSV, encoding="utf-8")))


def path(version):
    return os.path.join(os.path.dirname(os.path.abspath(__file__)), "input_list_{}.json".format(version))


def load(version):
    """-> dict(version, names [[group, input], ...] in the list's order, src [the simulator's column of each], n_brain, n_hands, n,
    cut {"group|input": why})"""
    L = json.load(open(path(version), encoding="utf-8"))
    full = {(r["group"], r["input"]): i for i, r in enumerate(full_rows())}
    L["src"] = [full[(g, n)] for g, n in L["names"]]
    L["n"] = len(L["names"])
    return L


def build(version, sample, faded, n_brain_old=868):
    """the list from the rules above; faded: the simulator's columns of the rule fade (a checkpoint's rule_fade["cols"])"""
    R = full_rows()
    X = np.load(sample, mmap_mode="r")
    assert X.shape[1] == len(R), (X.shape, len(R))
    lo, hi = np.asarray(X.min(0)), np.asarray(X.max(0))
    cut = {}
    for i, r in enumerate(R):
        g, n = r["group"], r["input"]
        const = lo[i] == hi[i]
        if g in CUT_GROUPS:
            cut[i] = CUT_GROUPS[g]
        elif const and g in ("walls", "sight") and lo[i] == -1.0:
            cut[i] = "outside his field of view (always -1)"
        elif const and g == "hazards" and "deadly drop" in n:
            cut[i] = "no deadly drop on the ten maps"
        elif const and lo[i] == 1.0 and "heavy machine gun" not in n and (
                n.endswith(": exists") or n.endswith("slot holds a place") or (g == "b12 small items" and n.endswith(": there"))):
            cut[i] = "always 1 on the ten maps"
    fd = set(int(c) for c in faded)
    assert not (fd & set(cut)), "a faded column is cut"
    tail = [i for i in range(len(R)) if i in fd] + [i for i, r in enumerate(R) if r["group"] in TAIL_GROUPS]
    ts = set(tail)
    brain = [i for i in range(n_brain_old) if i not in cut and i not in ts]
    hands = [i for i in range(n_brain_old, len(R)) if i not in cut and i not in ts]
    order = brain + hands + tail
    assert len(set(order)) == len(order) and len(order) + len(cut) == len(R)
    L = dict(version=version, full=len(R), n_brain=len(brain), n_hands=len(brain) + len(hands),
             names=[[R[i]["group"], R[i]["input"]] for i in order],
             cut={"{}|{}".format(R[i]["group"], R[i]["input"]): w for i, w in sorted(cut.items())},
             note="brain = the first n_brain; the hands' encoder = the first n_hands; the tail is read by no first layer")
    json.dump(L, open(path(version), "w", encoding="utf-8"), indent=0)
    with open(os.path.join(ROOT, "docs", "INPUTS_{}.csv".format(version)), "w", encoding="utf-8", newline="") as f:
        w = csv.writer(f, lineterminator="\n")
        w.writerow(["index", "group", "input", "meaning", "scale", "added in", "read by"])
        for j, i in enumerate(order):
            who = "brain, hands" if j < len(brain) else ("hands" if j < len(brain) + len(hands) else
                                                         ("head" if R[i]["group"] in TAIL_GROUPS else "none (kept)"))
            w.writerow([j, R[i]["group"], R[i]["input"], R[i]["meaning"], R[i]["scale"], R[i]["added in"], who])
    return L


def show(version):
    import collections
    L = load(version)
    print("list {}: {} of the simulator's {} columns; the brain reads the first {}, the hands' encoder the first {}, the tail {}".format(
        L["version"], L["n"], L["full"], L["n_brain"], L["n_hands"], L["n"] - L["n_hands"]))
    c = collections.Counter(L["cut"].values())
    print("cut {}: {}".format(len(L["cut"]), dict(c)))


if __name__ == "__main__":
    if sys.argv[1] == "build":
        import torch
        ck = torch.load(os.path.join(ROOT, "data", "sim_runs", "duel_gru_b1_2d", "keep", "policy_end_b12d.pt"), map_location="cpu", weights_only=False)
        build(int(sys.argv[2]), sys.argv[3], ck["rule_fade"]["cols"])
    show(int(sys.argv[2]))

"""2.2b (docs/runs/2.2/2.2b/CARD.md): the start network made from 2.2a's update 90, its list already brought to 22b (tools/inputs21.py convert
--old 20e --new 22b --group "b22b fight" --token fight22: the hands' new columns at zero weights, the token shut).

    python tools/fight22_init.py layout <list22b.pt> <out.pt>
        THE RATER OF OPTIONS OUT (change 1): the head's outlook (head2.out.*, out_g, out_pick), the desc outlooks (head2.dsc.*), the second value
        (head2.vw.*) and the dial out_src taken out of the model and the head's layout; the checkpoint's "out_opt", "out_stats" dropped, its
        "out22" kept only for the tracker's Adam ("trk22_opt"). The tracker (head2.trk.*: its readouts and pass odds) stays. Nothing of what was
        taken out ever played (out_g 0 at update 90): he answers as before. THE FIGHT NETWORK added (sim/fightnet.py): its layout (its inputs'
        parts; the pass scorer's norm, taken from desc22's measured norm of the 19 order numbers), its weights (the last layer at zero), no norm
        yet. -> out.pt (then: the sample of its inputs, docs/runs/2.2/2.2b/legs_test.py --sample)
    python tools/fight22_init.py norm <layout.pt> <out.pt> --samples <a.npz,b.npz,...>
        the fight network's inputs' norm MEASURED on the samples (each column's mean and spread over the keep readings of the start's play, with
        practice trips; a column whose spread is under NEAR_CONST: spread 1, listed); the hands' 20 new columns' statistics measured on the same
        samples' rows (refused unless every weight on them is still zero; a constant column keeps its design statistics, listed)
"""
import argparse
import os
import sys

import numpy as np

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, os.path.join(ROOT, "sim"))
NEAR_CONST = 1e-3
GROUP = "b22b fight"
DROP_KEYS = ("head2.out.", "head2.dsc.", "head2.vw.")
DROP_BUFS = ("head2.out_g", "head2.out_pick", "head2.out_src")


def layout_cmd(a):
    import torch
    import fightnet as FN
    import duel_env as E
    import desc22 as D
    ck = torch.load(a.inp, weights_only=False, map_location="cpu")
    assert str((ck.get("inputs") or {}).get("list")) == "22b", "not a network of list 22b (tools/inputs21.py convert --old 20e --new 22b first)"
    assert ck.get("fight22") is None, "the network has a fight network already"
    sd = ck["model"]
    L2 = dict(ck["head2"])
    assert L2.get("trk22") and L2.get("desc22"), "2.2a's network expected (the tracker and the desc outlooks inside its head)"
    assert float(sd["head2.out_g"]) == 0.0, "the outlook's term plays in this file (out_g {}): it is not 2.2a's update 90".format(float(sd["head2.out_g"]))
    gone = [k_ for k_ in sd if k_.startswith(DROP_KEYS) or k_ in DROP_BUFS]
    for k_ in gone:
        del sd[k_]
    DL = L2["desc22"]
    pn = dict(mean=list(DL["norm"]["tgt_mean"][:D.N_ORDER]), sd=list(DL["norm"]["tgt_sd"][:D.N_ORDER]), idx=list(DL["tgt_idx"]))
    assert [list(E.CMB_FEAT)[i_] for i_ in pn["idx"]] == list(D.TGT_COLS), "desc22's order columns are not the simulator's"
    for k_ in ("outlook", "desc22", "vw"):
        L2.pop(k_, None)
    ck["head2"] = L2
    o22 = ck.pop("out22", None) or {}
    ck["trk22_opt"] = o22.get("trk_opt")
    for k_ in ("out_opt", "out_stats"):
        ck.pop(k_, None)
    TL = L2["trk22"]
    FL = FN.layout(brain=int(TL["bel"]), trk=18, obs_cols=L2["obs_cols"], obs_names=[str(x_) for x_ in L2.get("obs_names", L2["obs_cols"])],
                   n_target=int(L2["n_target"]), head=int(L2["size"]), hands=int(ck["hidden"]), cmb_feat=E.CMB_FEAT, pass_norm=pn)
    mod = FN.make_module(FL)
    ck["fight22"] = dict(layout=FL, model={k_: v_.detach().clone() for k_, v_ in mod.state_dict().items()}, opt=None, applied_bias=None,
                         note="tools/fight22_init.py layout: no norm yet")
    torch.save(ck, a.out)
    print("wrote {}: taken out {} weights of the rater of options ({}); the head's layout without outlook, desc22, vw; the tracker kept (its Adam "
          "as trk22_opt: {}); the fight network added: {} inputs ({}), {} -> {} -> {} outputs, the last layer at zero, no norm yet".format(
              a.out, len(gone), sorted(set(k_.split(".")[1] for k_ in gone)), ck["trk22_opt"] is not None, FL["width"],
              ", ".join("{} {}".format(k_, w_) for k_, w_ in FL["parts"]), FL["hid"], FL["hid"], FL["n_out"]))


def norm_cmd(a):
    import torch
    import input_list as IL
    ck = torch.load(a.inp, weights_only=False, map_location="cpu")
    F = ck.get("fight22")
    assert F is not None and F["layout"].get("norm") is None, "a network from `layout` expected (a fight network with no norm)"
    X, R = [], []
    for f_ in a.samples.split(","):
        z_ = np.load(f_)
        X.append(z_["fx"])
        R.append(z_["rows"])
    X, R = np.concatenate(X).astype(np.float64), np.concatenate(R).astype(np.float64)
    L = F["layout"]
    assert X.shape[1] == L["width"], (X.shape, L["width"])
    mu, sd = X.mean(0), X.std(0)
    const = sd < NEAR_CONST
    sd = np.where(const, 1.0, sd)
    import fightnet as FN
    nm = FN.names(L)
    L = dict(L, norm=dict(mean=[float(x_) for x_ in mu], sd=[float(x_) for x_ in sd], measured=dict(rows=int(len(X)), files=a.samples.split(",")),
                          const=[nm[i_] for i_ in np.nonzero(const)[0]]))
    F = dict(F, layout=L, note="tools/fight22_init.py norm: measured on {} keep readings".format(len(X)))
    ck["fight22"] = F
    Ln = IL.load("22b")
    cols = [j_ for j_, (g_, _) in enumerate(Ln["names"]) if g_ == GROUP]
    assert R.shape[1] == len(cols), (R.shape, len(cols))
    sd_ = ck["model"]
    ki_ = [i_ for i_, k_ in enumerate(ck["attn"]["kinds"]) if k_["name"] == "fight22"][0]
    assert not sd_["enc.0.weight"][:, cols].any() and not sd_["attn.emb.{}.weight".format(ki_)].any(), "a weight on the new columns is no longer zero"
    m_, v_ = R.mean(0), R.var(0)
    keep_ = v_ <= 1e-6
    mean, var = np.asarray(ck["obs_mean"], np.float64).copy(), np.asarray(ck["obs_var"], np.float64).copy()
    mean[cols] = np.where(keep_, mean[cols], m_)
    var[cols] = np.where(keep_, var[cols], v_)
    ck["obs_mean"], ck["obs_var"] = mean.astype(np.asarray(ck["obs_mean"]).dtype), var.astype(np.asarray(ck["obs_var"]).dtype)
    ck["inputs"] = dict(ck["inputs"], design_stats=None, measured=dict(rows=int(len(R)), files=a.samples.split(","),
                                                                        design_kept=[Ln["names"][cols[i_]][1] for i_ in np.nonzero(keep_)[0]]))
    torch.save(ck, a.out)
    print("wrote {}: the fight network's {} inputs' norm measured on {} keep readings ({} constant, spread 1: {}); the hands' {} new columns' "
          "statistics measured on {} rows ({} constant, their design kept: {})".format(
              a.out, L["width"], len(X), int(const.sum()), [nm[i_] for i_ in np.nonzero(const)[0]][:12], len(cols), len(R), int(keep_.sum()),
              [Ln["names"][cols[i_]][1] for i_ in np.nonzero(keep_)[0]]))
    for j_, c_ in enumerate(cols):
        print("  {:<40s} mean {:+.4f} sd {:.4f}".format(Ln["names"][c_][1], float(mean[c_]), float(np.sqrt(var[c_]))))


def main():
    ap = argparse.ArgumentParser()
    sp = ap.add_subparsers(dest="cmd", required=True)
    p = sp.add_parser("layout")
    p.add_argument("inp")
    p.add_argument("out")
    p = sp.add_parser("norm")
    p.add_argument("inp")
    p.add_argument("out")
    p.add_argument("--samples", required=True)
    a = ap.parse_args()
    {"layout": layout_cmd, "norm": norm_cmd}[a.cmd](a)


if __name__ == "__main__":
    main()

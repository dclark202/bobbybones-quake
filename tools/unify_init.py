"""One movement network, steps 3 and 4 (sim/legs_unify.py): give a network the trainer's --legs-feat / --legs-guide parts at
zero, and prove that it answers as before (or that the numpy side answers as torch with the parts woken).

    python tools/unify_init.py widen <in.pt> <out.pt> [--feat] [--guide]
    python tools/unify_init.py wake <in.pt> <out.pt> [--scale 0.05]       (a test copy: the parts at random)
    python tools/unify_init.py same <a.pt> <b.pt> [--frames 2000] [--players 32] [--npz <b's policy.npz>]

widen keeps everything of the network and adds legs_door (zeros), legs_guide (zeros) and the layout ("legs_unify");
the network must have its legs' branch inside (LEGS_IN). The trainer does the same for a network without the parts
(the control, older league files): a converted file is for the checks' tools and for a run that starts from it.

same plays both networks on the same random inputs (his inputs and the branch's: about one row in eight with no way,
all zeros), with resets (each seat's memory cleared with a chance of 1% a frame) and the same draws:
  - torch: a forward written here from the trainer's sums (encoder, attention part, the legs' door into the fast GRU's
    input only, his memory, the outputs, the guide), for a and for b, each on its own memory;
  - numpy: sim/test_suite.py's Policy for a and b (b's parts forced on even at zero, so the path is the one a woken
    network takes), and plugins/netpass.py's step() for b if --npz (an export of b by sim/export_duel.py);
  - b in torch against b in numpy, on numpy's memory each frame (teacher-forced): the largest difference of the memory
    and of the logits.
The networks of 2026-10-16 have no head, slow memory or ordered outputs: the torch forward here asserts that.
"""
import os
import sys

import numpy as np

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(HERE)
sys.path.insert(0, os.path.join(ROOT, "sim"))
sys.path.insert(0, os.path.join(ROOT, "plugins"))


def _layout(ck, feat, guide):
    import importlib
    import legs_unify as LU_
    import movement_env as M_
    E_ = importlib.import_module(ck.get("env_module") or "duel_env")
    return LU_.layout(ck["action_dims"], E_.TURN, M_.TURN_BINS, feat, guide)


def widen(src, dst, feat=True, guide=True):
    import torch
    ck = torch.load(src, weights_only=False, map_location="cpu")
    sd = ck["model"]
    assert "legs.0.weight" in sd, "the network has no legs' branch inside (LEGS_IN)"
    old = ck.get("legs_unify") or {}
    lay = _layout(ck, feat or old.get("feat", 0), guide or old.get("guide", 0))
    if lay["feat"] and "legs_door.weight" not in sd:
        sd["legs_door.weight"] = torch.zeros(lay["enc"], lay["hid"])
        sd["legs_door.bias"] = torch.zeros(lay["enc"])
    if lay["guide"] and "legs_guide" not in sd:
        sd["legs_guide"] = torch.zeros(len(lay["outs"]))
    ck["legs_unify"] = lay
    torch.save(ck, dst)
    print("{} -> {}: feat {}, guide {} (at zero)".format(os.path.basename(src), os.path.basename(dst), lay["feat"], lay["guide"]))


def wake(src, dst, scale=0.05, seed=3):
    import torch
    ck = torch.load(src, weights_only=False, map_location="cpu")
    sd = ck["model"]
    g = torch.Generator().manual_seed(seed)
    if "legs_door.weight" in sd:
        sd["legs_door.weight"] = torch.randn(sd["legs_door.weight"].shape, generator=g) * scale
        sd["legs_door.bias"] = torch.randn(sd["legs_door.bias"].shape, generator=g) * scale
    if "legs_guide" in sd:
        sd["legs_guide"] = torch.rand(sd["legs_guide"].shape, generator=g) + 0.25
    torch.save(ck, dst)
    print("{} -> {}: the parts woken (scale {})".format(os.path.basename(src), os.path.basename(dst), scale))


class TorchNet:
    """the trainer's sums for a network without head, slow memory or ordered outputs, in torch on the CPU"""

    def __init__(self, path):
        import torch
        import torch.nn as nn
        import legs_unify as LU_
        ck = torch.load(path, weights_only=False, map_location="cpu")
        assert not ck.get("head") and not ck.get("slow") and not ck.get("ordered") and not ck.get("cells"), "not for this network's parts"
        sd = ck["model"]
        self.mean, self.var = np.asarray(ck["obs_mean"]), np.asarray(ck["obs_var"])
        H = sd["gru.weight_hh"].shape[1]
        self.enc = nn.Sequential(nn.Linear(sd["enc.0.weight"].shape[1], 256), nn.Tanh(), nn.Linear(256, 256), nn.Tanh())
        self.enc.load_state_dict({k[4:]: v for k, v in sd.items() if k.startswith("enc.")})
        self.attn = None
        if ck.get("attn") is not None:
            import attn as attn_
            self.attn = attn_.make_module(ck["attn"], 256)
            self.attn.load_state_dict({k[5:]: v for k, v in sd.items() if k.startswith("attn.")}, strict=False)
        self.gru = nn.GRUCell(256, H)
        self.gru.load_state_dict({k[4:]: v for k, v in sd.items() if k.startswith("gru.")})
        self.pi = nn.Linear(H, sd["pi.weight"].shape[0])
        self.pi.load_state_dict({"weight": sd["pi.weight"], "bias": sd["pi.bias"]})
        self.legs = nn.Sequential(nn.Linear(sd["legs.0.weight"].shape[1], 256), nn.Tanh(), nn.Linear(256, 256), nn.Tanh(), nn.Linear(256, 17))
        self.legs.load_state_dict({k[5:]: v for k, v in sd.items() if k.startswith("legs.")})
        self.uni = LU_.as_layout(ck.get("legs_unify"))
        self.door = self.gw = self.gm = None
        if self.uni and self.uni["feat"]:
            self.door = nn.Linear(self.uni["hid"], self.uni["enc"])
            self.door.load_state_dict({"weight": sd["legs_door.weight"], "bias": sd["legs_door.bias"]})
        if self.uni and self.uni["guide"]:
            self.gw = sd["legs_guide"].float()
            self.gm = LU_.GuideMaps(self.uni, "cpu")
        self.dims = [int(d) for d in ck["action_dims"]]

    def step(self, obs, h, xl):
        """-> (logits, the new memory) as numpy"""
        import torch
        import legs_unify as LU_
        with torch.no_grad():
            x = torch.from_numpy(np.clip((obs - self.mean) / np.sqrt(self.var + 1e-8), -10, 10).astype(np.float32))
            e = self.enc(x)
            if self.attn is not None:
                e = e + self.attn(x)
            xlt = torch.from_numpy(np.asarray(xl, np.float32))
            h2, lgl = LU_.t_branch(self.legs, xlt)
            ok = LU_.t_way(xlt)
            self.parts = [None, None]
            if self.door is not None:
                self.parts[0] = (self.door(h2) * ok[:, None]).numpy()
                e = e + self.door(h2) * ok[:, None]
            hn = self.gru(e, torch.from_numpy(h))
            lg = self.pi(hn)
            if self.gm is not None:
                self.parts[1] = self.gm.add(self.gw, lgl, ok).numpy()
                lg = lg + self.gm.add(self.gw, lgl, ok)
            return lg.numpy(), hn.numpy()


def _np_logits(pol, h_new, xl):
    """the numpy side's logits from its new memory: the outputs' layer and the guide (sim/legs_unify.py's numpy sums)"""
    import legs_unify as LU_
    lg = h_new @ pol.wp.T + pol.bp
    if pol.uniG is not None:
        ok = LU_.np_way(xl)
        lg = lg + LU_.np_guide_add(pol.uni, pol.uniG, LU_.np_branch(pol.legsP, xl)[1], ok, sum(pol.dims))
    return lg


def _pdiff(la, lb, dims):
    """the largest difference of the chances of two sets of logits, output by output"""
    o = np.concatenate([[0], np.cumsum(dims)]).astype(int)
    m = 0.0
    for j in range(len(dims)):
        pa, pb = (np.exp(l_[:, o[j]:o[j + 1]] - l_[:, o[j]:o[j + 1]].max(1, keepdims=True)) for l_ in (la, lb))
        m = max(m, float(np.abs(pa / pa.sum(1, keepdims=True) - pb / pb.sum(1, keepdims=True)).max()))
    return m


def same(a, b, frames=2000, players=32, npz=None):
    import test_suite as T_
    pa, pb = T_.Policy(a, seed=5), T_.Policy(b, seed=5)
    if pb.uni is not None:                                   # (the woken path even with the parts at zero)
        import torch
        sd = torch.load(b, weights_only=False, map_location="cpu")["model"]
        if pb.uni.get("feat"):
            pb.uniD = (sd["legs_door.weight"].numpy(), sd["legs_door.bias"].numpy())
        if pb.uni.get("guide"):
            pb.uniG = sd["legs_guide"].numpy().astype(np.float32)
    ta, tb = TorchNet(a), TorchNet(b)
    NP = None
    if npz:
        import netpass as N_
        NP = N_.load(npz)
        if NP[0].get("_uni") is None and pb.uni is not None:         # (forced as above)
            import legs_unify as LU_
            NP[0]["_uni"] = (LU_.as_layout(NP[0]["legs_unify"]), pb.uniD, pb.uniG, LU_)
    n_in, n_l = len(pa.mean), pa.legsP[0].shape[1]
    rng = np.random.default_rng(1)
    ha, hb, hta, htb = pa.zeros(players), pb.zeros(players), pa.zeros(players), pb.zeros(players)
    hn = pb.zeros(players)
    w = dict(part_door=0.0, part_guide=0.0, part_guide_p=0.0, tb_np_p=0.0, np_mem=0.0, np_acts=0, t_mem=0.0, t_logit=0.0, tb_np_mem=0.0, tb_np_logit=0.0, npass_mem=0.0, npass_acts=0, ways=0)
    for f_ in range(frames):
        obs = (rng.standard_normal((players, n_in)) * 2.0).astype(np.float32)
        xl = rng.standard_normal((players, n_l)).astype(np.float32)
        xl[rng.random(players) < 0.125] = 0.0                # (rows with no way: zeros, as legs_prep() gives them)
        w["ways"] += int((np.abs(xl).max(1) > 0).sum())
        r_ = rng.random(players) < 0.01                      # resets
        for m_ in (ha, hb, hta, htb, hn):
            m_[r_] = 0.0
        hb_in = hb.copy()
        pa.rng, pb.rng = np.random.default_rng(1000 + f_), np.random.default_rng(1000 + f_)
        aa, ha = pa.act(obs, ha, xl=xl)
        ab, hb = pb.act(obs, hb, xl=xl)
        w["np_mem"] = max(w["np_mem"], float(np.abs(ha - hb).max()))
        w["np_acts"] += int((aa != ab).sum())
        la, hta = ta.step(obs, hta, xl)
        lb, htb = tb.step(obs, htb, xl)
        w["t_mem"] = max(w["t_mem"], float(np.abs(hta - htb).max()))
        w["t_logit"] = max(w["t_logit"], float(np.abs(la - lb).max()))
        lt_, ht_ = tb.step(obs, hb_in, xl)                   # b in torch on numpy's memory (teacher-forced)
        import legs_unify as LU_                             # ... and the parts alone: torch's against sim/legs_unify.py's numpy sums
        ok_ = LU_.np_way(xl)
        h2_, lgl_ = LU_.np_branch(pb.legsP, xl)
        if tb.parts[0] is not None:
            w["part_door"] = max(w["part_door"], float(np.abs(tb.parts[0] - LU_.np_door(pb.uniD[0], pb.uniD[1], h2_, ok_)).max()))
        if tb.parts[1] is not None:
            gn_ = LU_.np_guide_add(pb.uni, pb.uniG, lgl_, ok_, sum(pb.dims))
            w["part_guide"] = max(w["part_guide"], float(np.abs(tb.parts[1] - gn_).max()))
            l0_ = hb @ pb.wp.T + pb.bp                       # (as chances: his own logits with either guide added)
            w["part_guide_p"] = max(w["part_guide_p"], _pdiff(l0_ + tb.parts[1], l0_ + gn_, pb.dims))
        w["tb_np_mem"] = max(w["tb_np_mem"], float(np.abs(ht_ - hb).max()))
        w["tb_np_logit"] = max(w["tb_np_logit"], float(np.abs(lt_ - _np_logits(pb, hb, xl)).max()))
        w["tb_np_p"] = max(w["tb_np_p"], _pdiff(lt_, _np_logits(pb, hb, xl), pb.dims))
        if NP is not None:
            import netpass as N_
            an_, hn = N_.step(NP[0], NP[1], obs, hn, np.random.default_rng(1000 + f_), xl=xl)
            w["npass_mem"] = max(w["npass_mem"], float(np.abs(hn - hb).max()))
            w["npass_acts"] += int((an_ != ab).sum())
    w["choices"] = frames * players * aa.shape[1]
    print("{} and {}: {} frames x {} seats, {} with a way; {}".format(os.path.basename(a), os.path.basename(b), frames, players, w["ways"],
                                                                       ", ".join("{} {:.3g}".format(k_, v_) for k_, v_ in w.items() if k_ != "ways")))
    return w


if __name__ == "__main__":
    args = sys.argv[1:]

    def opt(name, default):
        return type(default)(args[args.index(name) + 1]) if name in args else default
    if args[0] == "widen":
        widen(args[1], args[2], "--feat" in args, "--guide" in args)
    elif args[0] == "wake":
        wake(args[1], args[2], opt("--scale", 0.05))
    elif args[0] == "same":
        w_ = same(args[1], args[2], opt("--frames", 2000), opt("--players", 32), opt("--npz", ""))
        ok_ = w_["np_mem"] == 0 and w_["np_acts"] == 0 and w_["t_mem"] == 0 and w_["t_logit"] == 0
        print("exact" if ok_ else "not exact", "| torch against numpy (b): memory {:.2e}, logits {:.2e}, chances {:.2e}; the parts: door {:.2e}, "
              "guide {:.2e} (as chances {:.2e})".format(w_["tb_np_mem"], w_["tb_np_logit"], w_["tb_np_p"], w_["part_door"], w_["part_guide"],
                                                       w_["part_guide_p"]))
        sys.exit(0 if ok_ else 1)
    else:
        sys.exit(__doc__)

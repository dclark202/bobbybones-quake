"""One movement network, steps 3 and 4 (sim/legs_unify.py): give a network the trainer's --legs-feat / --legs-guide parts at
zero, and prove that it answers as before (or that the numpy side answers as torch with the parts woken).

    python tools/unify_init.py widen <in.pt> <out.pt> [--feat] [--guide] [--keys]   (--keys: LEGS_KEYS_ADD's five, shut)
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


def _layout(ck, feat, guide, gate=0, residual=0):
    import importlib
    import legs_unify as LU_
    import movement_env as M_
    E_ = importlib.import_module(ck.get("env_module") or "duel_env")
    return LU_.layout(ck["action_dims"], E_.TURN, M_.TURN_BINS, feat, guide, gate=gate, residual=residual,
                      mem=int(ck["model"]["gru.weight_hh"].shape[1]))


def add_keys(ck):
    """(LEGS_KEYS_ADD, step 2) his five choices "my legs' / mine" on his legs added shut at the end of his outputs: weights
    0, the bias of "my legs'" at KA_SHUT over "mine" (as the trainer's load_net gives a network without them)"""
    import importlib
    import torch
    os.environ["LEGS_KEYS_ADD"] = "1"
    E_ = importlib.import_module(ck.get("env_module") or "duel_env")
    sd = ck["model"]
    dims = [int(d) for d in ck["action_dims"]]
    k_ = 2 * len(E_.KA_COLS)
    assert sd["pi.weight"].shape[0] == sum(dims), (sd["pi.weight"].shape, dims)
    b_ = torch.zeros(k_, dtype=sd["pi.bias"].dtype)
    b_[0::2] = float(E_.KA_SHUT)
    sd["pi.weight"] = torch.cat([sd["pi.weight"], sd["pi.weight"].new_zeros(k_, sd["pi.weight"].shape[1])], 0)
    sd["pi.bias"] = torch.cat([sd["pi.bias"], b_], 0)
    ck["action_dims"] = tuple(dims) + (2,) * len(E_.KA_COLS)
    ck["env_vars"] = dict(ck.get("env_vars") or {}, LEGS_KEYS_ADD="1")


def widen(src, dst, feat=True, guide=True, keys=False, gate=False, residual=False):
    import torch
    ck = torch.load(src, weights_only=False, map_location="cpu")
    sd = ck["model"]
    assert "legs.0.weight" in sd, "the network has no legs' branch inside (LEGS_IN)"
    if keys:
        add_keys(ck)
        sd = ck["model"]
    old = ck.get("legs_unify") or {}
    lay = _layout(ck, feat or old.get("feat", 0), guide or old.get("guide", 0), gate or old.get("gate", 0), residual or old.get("residual", 0))
    if lay["feat"] and "legs_door.weight" not in sd:
        sd["legs_door.weight"] = torch.zeros(lay["enc"], lay["hid"])
        sd["legs_door.bias"] = torch.zeros(lay["enc"])
    if lay["guide"] and "legs_guide" not in sd:
        sd["legs_guide"] = torch.zeros(len(lay["outs"]))
    H = int(sd["gru.weight_hh"].shape[1])
    for n_, o_, i_, on_ in (("legs_gate", len(lay["outs"]), H, lay["gate"]), ("legs_motor", lay["motor"], lay["hid"], lay["gate"]),
                            ("legs_res_a", len(lay["bdims"]), H, lay["residual"]), ("legs_res", int(sum(lay["bdims"])), H, lay["residual"])):
        if on_ and n_ + ".weight" not in sd:                 # (v0.3.4 A, B) at zero
            sd[n_ + ".weight"] = torch.zeros(o_, i_)
            sd[n_ + ".bias"] = torch.zeros(o_)
    ck["legs_unify"] = lay
    torch.save(ck, dst)
    print("{} -> {}: feat {}, guide {}, gate {}, residual {} (at zero){}; {} outputs".format(
        os.path.basename(src), os.path.basename(dst), lay["feat"], lay["guide"], lay["gate"], lay["residual"],
        ", keys shut" if keys else "", len(ck["action_dims"])))


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
    for n_ in ("legs_gate", "legs_motor", "legs_res_a", "legs_res"):
        if n_ + ".weight" in sd:
            sd[n_ + ".weight"] = torch.randn(sd[n_ + ".weight"].shape, generator=g) * scale
            sd[n_ + ".bias"] = torch.randn(sd[n_ + ".bias"].shape, generator=g) * scale
    if "legs_res_a.bias" in sd:                              # (a well inside (0, 1))
        sd["legs_res_a.bias"] = torch.rand(sd["legs_res_a.bias"].shape, generator=g) * 0.6 + 0.2
    if "--fade" in sys.argv:
        ck["switch_fade"] = float(sys.argv[sys.argv.index("--fade") + 1])
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
        self.door = self.gw = self.gm = self.gate = self.res = None
        self.fade = float(ck.get("switch_fade", 0.0))
        if self.uni and self.uni["feat"]:
            self.door = nn.Linear(self.uni["hid"], self.uni["enc"])
            self.door.load_state_dict({"weight": sd["legs_door.weight"], "bias": sd["legs_door.bias"]})
        if self.uni and (self.uni["guide"] or self.uni.get("gate")):
            self.gw = sd["legs_guide"].float() if self.uni["guide"] else None
            self.gm = LU_.GuideMaps(self.uni, "cpu")

        def lin(n_):
            l_ = nn.Linear(sd[n_ + ".weight"].shape[1], sd[n_ + ".weight"].shape[0])
            l_.load_state_dict({"weight": sd[n_ + ".weight"], "bias": sd[n_ + ".bias"]})
            return l_
        if self.uni and self.uni.get("gate"):
            self.gate = (lin("legs_gate"), lin("legs_motor"))
        if self.uni and self.uni.get("residual"):
            self.res = (lin("legs_res_a"), lin("legs_res"))
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
            if self.gw is not None:
                self.parts[1] = self.gm.add(self.gw, lgl, ok).numpy()
                lg = lg + self.gm.add(self.gw, lgl, ok)
            if self.gate is not None:                        # (v0.3.4 A)
                ga_ = self.gm.add(self.gate[0](hn), lgl, ok) + self.gm.place(self.gate[1](h2) * ok[:, None])
                self.parts.append(ga_.numpy())
                lg = lg + ga_
            if self.fade:
                lg = lg.clone()
                lg[:, int(sum(self.dims[:11])) + 1] -= self.fade
            self.legs_lg = (LU_.t_residual(self.res[0], self.res[1], lgl, hn) if self.res is not None else lgl).numpy()
            return lg.numpy(), hn.numpy()


def _np_logits(pol, h_new, xl):
    """the numpy side's logits from its new memory: the outputs' layer and the guide (sim/legs_unify.py's numpy sums)"""
    import legs_unify as LU_
    lg = h_new @ pol.wp.T + pol.bp
    ok = LU_.np_way(xl)
    h2, lgl = LU_.np_branch(pol.legsP, xl)
    if pol.uniG is not None:
        lg = lg + LU_.np_guide_add(pol.uni, pol.uniG, lgl, ok, sum(pol.dims))
    if pol.uniT is not None:
        lg = lg + LU_.np_gate_add(pol.uni, *pol.uniT, h_new, h2, lgl, ok, sum(pol.dims))
    if pol.fade:
        lg = lg.copy()
        lg[:, int(sum(pol.dims[:11])) + 1] -= pol.fade
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
        if pb.uni.get("gate"):
            pb.uniT = tuple(sd[k_].numpy() for k_ in ("legs_gate.weight", "legs_gate.bias", "legs_motor.weight", "legs_motor.bias"))
        if pb.uni.get("residual"):
            pb.uniR = tuple(sd[k_].numpy() for k_ in ("legs_res_a.weight", "legs_res_a.bias", "legs_res.weight", "legs_res.bias"))
    ta, tb = TorchNet(a), TorchNet(b)
    NP = None
    if npz:
        import netpass as N_
        NP = N_.load(npz)
        if NP[0].get("_uni") is None and pb.uni is not None:         # (forced as above)
            import legs_unify as LU_
            NP[0]["_uni"] = (LU_.as_layout(NP[0]["legs_unify"]), pb.uniD, pb.uniG, LU_, pb.uniT)
            if pb.uniR is not None:
                NP[0]["_res"] = (pb.uniR, LU_)
    n_in, n_l = len(pa.mean), pa.legsP[0].shape[1]
    rng = np.random.default_rng(1)
    ha, hb, hta, htb = pa.zeros(players), pb.zeros(players), pa.zeros(players), pb.zeros(players)
    hn = pb.zeros(players)
    w = dict(legs_ab=0.0, legs_tn=0.0, legs_np_pass=0.0, part_gate=0.0, b_extra_not0=0, part_door=0.0, part_guide=0.0, part_guide_p=0.0, tb_np_p=0.0, np_mem=0.0, np_acts=0, t_mem=0.0, t_logit=0.0, tb_np_mem=0.0, tb_np_logit=0.0, npass_mem=0.0, npass_acts=0, ways=0)
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
        w["legs_ab"] = max(w["legs_ab"], float(np.abs(pa.legs_logits(xl) - pb.legs_logits(xl, zo=hb)).max()))   # (the legs' logits his legs draw from)
        k_ = min(aa.shape[1], ab.shape[1])                   # (b may have more outputs: LEGS_KEYS_ADD's five, compared as "my legs'")
        w["np_mem"] = max(w["np_mem"], float(np.abs(ha - hb).max()))
        w["np_acts"] += int((aa[:, :k_] != ab[:, :k_]).sum())
        w["b_extra_not0"] += int((ab[:, k_:] != 0).sum())
        la, hta = ta.step(obs, hta, xl)
        lb, htb = tb.step(obs, htb, xl)
        w["t_mem"] = max(w["t_mem"], float(np.abs(hta - htb).max()))
        w["t_logit"] = max(w["t_logit"], float(np.abs(la - lb[:, :la.shape[1]]).max()))
        lt_, ht_ = tb.step(obs, hb_in, xl)                   # b in torch on numpy's memory (teacher-forced)
        w["legs_tn"] = max(w["legs_tn"], float(np.abs(tb.legs_lg - pb.legs_logits(xl, zo=ht_)).max()))
        if len(tb.parts) > 2:
            import legs_unify as LU_
            h2g_, lgg_ = LU_.np_branch(pb.legsP, xl)
            w["part_gate"] = max(w["part_gate"], float(np.abs(tb.parts[2] - LU_.np_gate_add(pb.uni, *pb.uniT, ht_, h2g_, lgg_, LU_.np_way(xl), sum(pb.dims))).max()))
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
            w["legs_np_pass"] = max(w["legs_np_pass"], float(np.abs(N_.legs_logits(NP[0], xl, zo=hn) - pb.legs_logits(xl, zo=hb)).max()))
    w["choices"] = frames * players * min(aa.shape[1], ab.shape[1])
    print("{} and {}: {} frames x {} seats, {} with a way; {}".format(os.path.basename(a), os.path.basename(b), frames, players, w["ways"],
                                                                       ", ".join("{} {:.3g}".format(k_, v_) for k_, v_ in w.items() if k_ != "ways")))
    return w


if __name__ == "__main__":
    args = sys.argv[1:]

    def opt(name, default):
        return type(default)(args[args.index(name) + 1]) if name in args else default
    if args[0] == "widen":
        widen(args[1], args[2], "--feat" in args, "--guide" in args, "--keys" in args, "--gate" in args, "--residual" in args)
    elif args[0] == "wake":
        wake(args[1], args[2], opt("--scale", 0.05))
    elif args[0] == "same":
        w_ = same(args[1], args[2], opt("--frames", 2000), opt("--players", 32), opt("--npz", ""))
        ok_ = w_["np_mem"] == 0 and w_["np_acts"] == 0 and w_["t_mem"] == 0 and w_["t_logit"] == 0 and w_["b_extra_not0"] == 0 and w_["legs_ab"] == 0
        print("exact" if ok_ else "not exact", "| torch against numpy (b): memory {:.2e}, logits {:.2e}, chances {:.2e}; the parts: door {:.2e}, "
              "guide {:.2e} (as chances {:.2e})".format(w_["tb_np_mem"], w_["tb_np_logit"], w_["tb_np_p"], w_["part_door"], w_["part_guide"],
                                                       w_["part_guide_p"]))
        sys.exit(0 if ok_ else 1)
    else:
        sys.exit(__doc__)

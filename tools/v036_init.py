"""v0.3.6 (docs/v0.4/ROCKETS_v0.3.6.md): a network of v0.3.5's shape made a network of the simulator with RL_AIM and PREFIRE
(sim/duel_env.py), the new parts closed: it answers as before.

    python tools/v036_init.py widen <in.pt> <out.pt>                 (a new file)
    python tools/v036_init.py league <file.pt> [<file.pt> ...]       (in place: the control, the league's files)
    python tools/v036_init.py same <old.pt> <new.pt>                 the two answer alike (numpy, random inputs; exit 1 if not)
    python tools/v036_init.py opt <old.pt> <old opt.pt> <new.pt> <new opt.pt> [--fill median|zero]
                                                                     the optimizer's state of old.pt laid out for new.pt (below)
    python tools/v036_init.py prep --from <v0.3.5's save .pt> --league <v0.3.5's snapshots folder> [--run duel_gru_v0_3_6]
                              [--cmd-template <.cmd> --cmd-out <.cmd> --until "2026-10-19 12:00" --setup-min 10]

widen / league: the 67 new inputs (N_RAIM 20, the group "v036 rocket aim"; N_PREF 39, "v036 prefire"; N_EMG 8, "v036 emergence"; at
the end of the group module's 864) get zero weight in the old encoder and mean 0, spread 1 in the input statistics; the attention part gets their
tokens (the kinds "rocket" and "emerge", one token each, and "prefire", a token a place: tools/targets_init.py's widen_attn, a first layer and
marks as sim/attn.py starts them) with their gate shut (attn.GATE_SHUT): nothing looks at them, and the encoder does not read
them: every output is what it was. The older tokens keep their weights, marks and gates (v0.3.5's are open). Nothing else is
touched (the legs' branch, its door and gate, the outputs, the value heads, env_vars). A file already of the new shape is
left as it is. `same` proves it: a few hundred random inputs (the new columns random too) through test_suite.Policy's numpy
sums of both networks for a few frames, the same draws: the largest difference of their memories, and the choices that differ.

prep: the run's folder data/sim_runs/<run>: policy.pt (the save widened), keep/policy_start.pt (the same), keep/policy_v035_end.pt
(the save as it was), snapshots/ (the league's last eight snap_*.pt by the minute in their names and every anchor_*.pt,
widened); a `same` of the save against policy.pt. With --cmd-template: the run's .cmd with {MINUTES} (from now, less
--setup-min, to --until) and {GATE_START} (the save's minutes: the trainer's --gate-start, so that the new tokens' gate opens
on a line from the run's first minute) filled in. Refuses to write into a run folder that has a policy.pt (--force).
prep also writes the run's opt.pt from the save's optimizer state (--opt <file>; default: the save's opt file beside it,
opt.pt beside policy.pt or opt_<x>.pt beside policy_<x>.pt; --no-opt: none, the trainer starts its optimizer cold).

opt: the trainer's Adam state (opt.pt: its "state" is keyed by a parameter's place in the optimizer's list) laid out for the
widened network. The list is rebuilt as the trainer builds it (train_duel_rnn.py: group 0 = the network's parameters in their
order less legs.*, head.* with --head, the legs' door and guide (UNI_PFX) with --legs-feat and the like; then the head's
group, the door's group, the legs' group, those that are there) from the checkpoint's own weights in their order (a
module's parameters before its buffers and children, as torch lists both; the attention part's gate is a buffer; the
widened file's attn.emb.<i>, which widen_attn writes at the file's end, at the old file's place for them: module_order).
The trainer refuses an opt.pt whose moments do not have their parameters' shapes (a cold start then). Which of
those groups there are is found from the old file: the one layout whose group sizes are the file's and whose every saved
moment has its parameter's shape (else it refuses). A parameter is followed by name, the attention part's by its token kind
(widen_attn renumbers attn.emb.<i> and inserts the new kinds' rows into attn.mark); a widened tensor (enc.0.weight: new
columns at the end) keeps its old moments in the old part and gets for the new part exp_avg 0 and exp_avg_sq the median of
the old part's (--fill median, the default: a new column's first steps are then small, not the 3 to 6 times the rate that
zero moments and an old step count give) or 0 (--fill zero); a brand-new parameter (a new kind's first layer) gets no state
(Adam starts it as new). Every group keeps its settings (lr, lr_scale: the trainer's resume puts this run's rates back).
Run it with the Anaconda Python; V036_ENV: the simulator module (default duel_env_ffa, the run's)."""
import os
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(HERE)
SIM = os.path.join(ROOT, "sim")
MODULE = os.environ.get("V036_ENV") or "duel_env_ffa"
INPUTS = os.path.join(ROOT, "docs", "INPUTS.csv")
NEW_KINDS = ["rocket", "emerge", "prefire"]


def _env():
    os.environ["CUDA_VISIBLE_DEVICES"] = "-1"
    for k_ in ("OPENBLAS_NUM_THREADS", "MKL_NUM_THREADS", "OMP_NUM_THREADS"):
        os.environ.setdefault(k_, "1")
    for p_ in (SIM, HERE):
        if p_ not in sys.path:
            sys.path.insert(0, p_)
    import importlib
    return importlib.import_module(MODULE)


def widen(ck, E):
    """the checkpoint (in place) with the simulator's inputs and the new tokens shut; returns (inputs added, kinds added)"""
    import numpy as np
    import torch
    import targets_init as TI
    sd = ck["model"]
    old_n = int(sd["enc.0.weight"].shape[1])
    extra = E.OBS_DIM - old_n
    assert extra in (0, E.N_RAIM + E.N_PREF + E.N_EMG), "the network has {} inputs, the simulator {} (this converter adds the {} of N_RAIM, N_PREF and N_EMG only)".format(
        old_n, E.OBS_DIM, E.N_RAIM + E.N_PREF + E.N_EMG)
    if extra == 0:
        assert ck.get("attn") is None or ck["attn"]["obs_dim"] == E.OBS_DIM
        return 0, []
    W = sd["enc.0.weight"]
    sd["enc.0.weight"] = torch.cat([W, torch.zeros(W.shape[0], extra, dtype=W.dtype)], 1)
    ck["obs_mean"] = np.concatenate([np.asarray(ck["obs_mean"], np.float64), np.zeros(extra)]).astype(np.asarray(ck["obs_mean"]).dtype)
    ck["obs_var"] = np.concatenate([np.asarray(ck["obs_var"], np.float64), np.ones(extra)]).astype(np.asarray(ck["obs_var"]).dtype)
    ck["obs_dim"] = E.OBS_DIM
    fresh = []
    if ck.get("attn") is not None:
        assert ck["attn"]["obs_dim"] == old_n, (ck["attn"]["obs_dim"], old_n)
        fresh = TI.widen_attn(ck, INPUTS)
        assert ck["attn"]["obs_dim"] == E.OBS_DIM and fresh == NEW_KINDS, (ck["attn"]["obs_dim"], fresh)
    ck["v036_init"] = dict(inputs_added=int(extra), tokens_added=fresh, gate="shut ({})".format(-30.0))
    return extra, fresh


def say(what, f, ck, extra, fresh):
    at = ck.get("attn")
    shut = 0
    if at is not None:
        shut = int((ck["model"]["attn.gate"] < 0).sum())
    print("{}: {} ({} inputs, {} new; attention tokens {}{}; tokens with the gate shut: {})".format(
        what, f, int(ck["model"]["enc.0.weight"].shape[1]), extra, at["tokens"] - 1 if at else 0,
        ", new: " + ", ".join(fresh) if fresh else "", shut), flush=True)


def main_widen(src, dst):
    E = _env()
    import torch
    torch.set_num_threads(1)
    ck = torch.load(src, weights_only=False, map_location="cpu")
    r = widen(ck, E)
    torch.save(ck, dst)
    say("widened", dst, ck, *r)


def main_league(files):
    E = _env()
    import torch
    torch.set_num_threads(1)
    for f in files:
        ck = torch.load(f, weights_only=False, map_location="cpu")
        r = widen(ck, E)
        if r[0]:
            torch.save(ck, f)
        say("league" if r[0] else "left as it is", f, ck, *r)


def main_same(a, b, players=64, frames=6):
    """test_suite.Policy's numpy sums of both networks on the same random inputs and draws: memories and choices"""
    E = _env()
    import numpy as np
    import test_suite as T_
    pa, pb = T_.Policy(a, seed=5), T_.Policy(b, seed=5)
    n = max(len(pa.mean), len(pb.mean))
    rng = np.random.default_rng(1)
    mean = np.zeros(n)
    sd_ = np.ones(n)
    mean[:len(pb.mean)], sd_[:len(pb.var)] = pb.mean, np.sqrt(pb.var + 1e-8)
    ha, hb = pa.zeros(players), pb.zeros(players)
    nxl = int(pb.legsP[0].shape[1]) if pb.legsP is not None else 0
    worst, acts, tot = 0.0, 0, 0
    for f_ in range(frames):
        pa.rng, pb.rng = np.random.default_rng(1000 + f_), np.random.default_rng(1000 + f_)
        obs = (mean + sd_ * rng.standard_normal((players, n)) * 1.5).astype(np.float32)   # (the new columns random as well)
        xl = rng.standard_normal((players, nxl)).astype(np.float32) if nxl else None
        aa, ha = pa.act(obs, ha, xl=xl if pa.needs_xl else None)
        ab, hb = pb.act(obs, hb, xl=xl if pb.needs_xl else None)
        k = min(aa.shape[1], ab.shape[1])
        acts += int((aa[:, :k] != ab[:, :k]).sum())
        tot += aa[:, :k].size
        worst = max(worst, float(np.abs(ha - hb).max()))
    att = "attention part {} / {}".format("on" if pa.attP is not None else "off (door shut)", "on" if pb.attP is not None else "off (door shut)")
    print("{} and {}: {}; {} random observations x {} frames: largest difference of their memories {:.2e}, choices that differ {} of {}".format(
        os.path.basename(a), os.path.basename(b), att, players, frames, worst, acts, tot), flush=True)
    return worst < 1e-4 and acts == 0


UNI_PFX = ("legs_door.", "legs_guide", "legs_gate.", "legs_motor.", "legs_res_a.", "legs_res.")   # (train_duel_rnn.py's UNI_PFX)


def module_order(sd, template=None):
    """the weights' names in the network's own order (a module's parameters, then its children's, as torch lists them).
    A file the trainer saved has it; a widened one (widen_attn) has the attn.emb.<i> keys at its end: their place is that
    of the template's (the file it was widened from) attn.emb block, by number"""
    if template is None:
        return list(sd)
    emb_ = sorted((k for k in sd if k.startswith("attn.emb.")), key=lambda k: int(k.split(".")[2]))
    out, done = [], False
    for k in template:
        if k.startswith("attn.emb."):
            if not done:
                out += emb_
                done = True
        elif k in sd:
            out.append(k)
    rest_ = [k for k in sd if k not in set(out)]
    assert not rest_, "weights the template does not place: {}".format(rest_[:5])
    return out


def opt_layouts(ck, order=None):
    """the optimizer lists the trainer may build for this checkpoint: {(head, uni, legs): [[names of a group], ...]}
    (order: the weights' names in the module's order, module_order; default: the file's)"""
    sd = ck["model"]
    buf = {"attn.gate"} if (ck.get("attn") or {}).get("gated") else set()
    ks = [k for k in (order or sd) if k not in buf]
    out = {}
    for head in (False, True):
        for uni in (False, True):
            for legs in (False, True):
                g0 = [k for k in ks if not k.startswith("legs.") and not (head and k.startswith("head.")) and not (uni and k.startswith(UNI_PFX))]
                gs = [g0]
                if head:
                    gs.append([k for k in ks if k.startswith("head.")])
                if uni:
                    gs.append([k for k in ks if k.startswith(UNI_PFX)])
                if legs:
                    gs.append([k for k in ks if k.startswith("legs.")])
                out[(head, uni, legs)] = gs
    return out


def opt_find(ck, opt):
    """the layout of opt (a torch Adam state_dict) among opt_layouts(ck): (key, groups of names); refuses if not one"""
    sd = ck["model"]
    sizes = [len(g["params"]) for g in opt["param_groups"]]
    hits = []
    for key, gs in opt_layouts(ck).items():
        if [len(g) for g in gs] != sizes:
            continue
        ok = True
        for g_names, g in zip(gs, opt["param_groups"]):
            for n_, i_ in zip(g_names, g["params"]):
                st_ = opt["state"].get(i_)
                if st_ is not None and tuple(st_["exp_avg"].shape) != tuple(sd[n_].shape):
                    ok = False
        if ok:
            hits.append((key, gs))
    keys_ = {tuple(tuple(g) for g in gs) for _, gs in hits}
    assert len(keys_) == 1, "the optimizer's groups ({}) fit {} layouts of the network".format(sizes, len(keys_))
    return hits[0]


def opt_convert(old_ck, old_opt, new_ck, fill="median"):
    """old_opt (the trainer's Adam state_dict for old_ck's network) for new_ck's network (widen() of it); -> (state_dict, report)"""
    import numpy as np
    import torch
    key, old_gs = opt_find(old_ck, old_opt)
    new_gs = opt_layouts(new_ck, order=module_order(new_ck["model"], list(old_ck["model"])))[key]
    osd, nsd = old_ck["model"], new_ck["model"]
    kinds_o = [k["name"] for k in (old_ck.get("attn") or {}).get("kinds", [])]
    kinds_n = [k["name"] for k in (new_ck.get("attn") or {}).get("kinds", [])]
    rows_o, r = {}, 0
    for k in (old_ck.get("attn") or {}).get("kinds", []):
        rows_o[k["name"]] = (r, len(k["idx"]))
        r += len(k["idx"])
    mark_rows = []                                           # attn.mark: per new row its old row (-1: a new kind's)
    for k in (new_ck.get("attn") or {}).get("kinds", []):
        if k["name"] in rows_o:
            r0, n_ = rows_o[k["name"]]
            assert n_ == len(k["idx"])
            mark_rows += list(range(r0, r0 + n_))
        else:
            mark_rows += [-1] * len(k["idx"])
    if kinds_n:
        mark_rows.append(r)                                  # (the summary token, last)
    st_old = {}                                              # old name -> its saved moments
    for g_names, g in zip(old_gs, old_opt["param_groups"]):
        for n_, i_ in zip(g_names, g["params"]):
            if i_ in old_opt["state"]:
                st_old[n_] = old_opt["state"][i_]
    rep_ = dict(copied=0, widened=[], new=[], no_state=0, layout=dict(zip(("head", "uni", "legs"), key)))
    state, groups, idx = {}, [], 0

    def filled(old_t, new_shape, sl, sq):
        z_ = torch.zeros(new_shape, dtype=old_t.dtype)
        if sq and fill == "median":
            z_ += float(old_t.float().median())
        z_[sl] = old_t
        return z_
    for g_names, g in zip(new_gs, old_opt["param_groups"]):
        g2 = {k_: v_ for k_, v_ in g.items() if k_ != "params"}
        g2["params"] = list(range(idx, idx + len(g_names)))
        groups.append(g2)
        for n_ in g_names:
            shape = tuple(nsd[n_].shape)
            src = n_
            if n_.startswith("attn.emb.") and kinds_n:
                kn_ = kinds_n[int(n_.split(".")[2])]
                src = "attn.emb.{}.weight".format(kinds_o.index(kn_)) if kn_ in kinds_o else None
            s_ = st_old.get(src) if src is not None else None
            if src is None or (src not in osd):
                rep_["new"].append(n_)
            elif s_ is None:
                rep_["no_state"] += 1
            elif tuple(s_["exp_avg"].shape) == shape and n_ != "attn.mark":
                state[idx] = {k_: (v_.clone() if torch.is_tensor(v_) else v_) for k_, v_ in s_.items()}
                rep_["copied"] += 1
            elif n_ == "attn.mark":
                rows_ = torch.tensor([max(0, x_) for x_ in mark_rows])
                keep_ = torch.tensor([x_ >= 0 for x_ in mark_rows])
                d_ = {}
                for k_, v_ in s_.items():
                    if k_ in ("exp_avg", "exp_avg_sq"):
                        t_ = v_[rows_].clone()
                        t_[~keep_] = float(v_.float().median()) if (k_ == "exp_avg_sq" and fill == "median") else 0.0
                        d_[k_] = t_
                    else:
                        d_[k_] = v_.clone() if torch.is_tensor(v_) else v_
                assert tuple(d_["exp_avg"].shape) == shape
                state[idx] = d_
                rep_["widened"].append("{} {} -> {} ({} new rows)".format(n_, tuple(s_["exp_avg"].shape), shape, int((~keep_).sum())))
            else:
                os_ = tuple(s_["exp_avg"].shape)
                assert len(os_) == len(shape) and all(a_ <= b_ for a_, b_ in zip(os_, shape)) and os_[:-1] == shape[:-1], \
                    "{}: {} -> {} is not a widening at the end".format(n_, os_, shape)
                sl = tuple(slice(0, a_) for a_ in os_)
                state[idx] = {k_: (filled(v_, shape, sl, k_ == "exp_avg_sq") if k_ in ("exp_avg", "exp_avg_sq")
                                   else (v_.clone() if torch.is_tensor(v_) else v_)) for k_, v_ in s_.items()}
                rep_["widened"].append("{} {} -> {}".format(n_, os_, shape))
            idx += 1
    names_ =[n_ for g_ in new_gs for n_ in g_]
    for i_, s_ in state.items():
        assert tuple(s_["exp_avg"].shape) == tuple(nsd[names_[i_]].shape) == tuple(s_["exp_avg_sq"].shape), names_[i_]
    rep_["sizes"] = [len(g_) for g_ in new_gs]
    return dict(state=state, param_groups=groups), rep_


def main_opt(old, old_opt, new, new_opt, fill="median"):
    import torch
    torch.set_num_threads(1)
    o_ck = torch.load(old, weights_only=False, map_location="cpu")
    n_ck = torch.load(new, weights_only=False, map_location="cpu")
    o_opt = torch.load(old_opt, weights_only=False, map_location="cpu")
    sd, r = opt_convert(o_ck, o_opt, n_ck, fill=fill)
    torch.save(sd, new_opt + ".tmp")
    os.replace(new_opt + ".tmp", new_opt)
    print("optimizer: {} -> {}: groups {} -> {} (layout {}), moments copied {}, widened {}, new parameters (no state) {}, "
          "parameters without a saved state (never stepped) {}; fill {}".format(
              os.path.basename(old_opt), new_opt, [len(g["params"]) for g in o_opt["param_groups"]], r["sizes"], r["layout"],
              r["copied"], r["widened"], r["new"], r["no_state"], fill), flush=True)
    return r


def opt_beside(f):
    """the optimizer file saved beside a policy file: opt.pt beside policy.pt, opt_<x>.pt beside policy_<x>.pt"""
    d_, b_ = os.path.split(f)
    c_ = os.path.join(d_, "opt.pt" if b_ == "policy.pt" else b_.replace("policy", "opt", 1))
    return c_ if c_ != f and os.path.exists(c_) else None


def main_prep(argv):
    import argparse
    import datetime
    import glob
    import re
    import shutil
    ap = argparse.ArgumentParser()
    ap.add_argument("--from", dest="src", required=True)
    ap.add_argument("--league", required=True)
    ap.add_argument("--run", default="duel_gru_v0_3_6")
    ap.add_argument("--force", action="store_true")
    ap.add_argument("--cmd-template", action="append", default=[])
    ap.add_argument("--cmd-out", action="append", default=[])
    ap.add_argument("--until", default="2026-10-19 12:00")
    ap.add_argument("--setup-min", type=float, default=10.0)
    ap.add_argument("--opt", default="")
    ap.add_argument("--no-opt", action="store_true")
    ap.add_argument("--fill", default="median", choices=("median", "zero"))
    a = ap.parse_args(argv)
    E = _env()
    import torch
    torch.set_num_threads(1)
    out = os.path.join(ROOT, "data", "sim_runs", a.run)
    assert os.path.abspath(a.src) != os.path.abspath(os.path.join(out, "policy.pt"))
    assert a.force or not os.path.exists(os.path.join(out, "policy.pt")), "{} has a policy.pt already (--force)".format(out)
    os.makedirs(os.path.join(out, "keep"), exist_ok=True)
    os.makedirs(os.path.join(out, "snapshots"), exist_ok=True)
    shutil.copy(a.src, os.path.join(out, "keep", "policy_v035_end.pt"))          # (the save as it was; the source is only read)
    ck = torch.load(a.src, weights_only=False, map_location="cpu")
    r = widen(ck, E)
    assert r[0] == E.N_RAIM + E.N_PREF + E.N_EMG, "the save is not of v0.3.5's shape ({} inputs added)".format(r[0])
    torch.save(ck, os.path.join(out, "policy.pt"))
    shutil.copy(os.path.join(out, "policy.pt"), os.path.join(out, "keep", "policy_start.pt"))
    say("start", os.path.join(out, "policy.pt"), ck, *r)
    opt_src = None if a.no_opt else (a.opt or opt_beside(a.src))
    if opt_src:                                              # the save's optimizer state, laid out for the widened network
        shutil.copy(opt_src, os.path.join(out, "keep", "opt_v035_end.pt"))
        main_opt(a.src, opt_src, os.path.join(out, "policy.pt"), os.path.join(out, "opt.pt"), fill=a.fill)
        shutil.copy(os.path.join(out, "opt.pt"), os.path.join(out, "keep", "opt_start.pt"))
    else:
        print("optimizer: {}: the trainer starts it cold".format("--no-opt" if a.no_opt else "no opt file beside " + a.src), flush=True)
    minutes0 = float(ck.get("minutes", 0.0))

    def num(f_):
        return int((re.findall(r"\d+", os.path.basename(f_)) or ["0"])[0])
    snaps = sorted(glob.glob(os.path.join(a.league, "snap_*.pt")), key=lambda f_: (num(f_), f_))[-8:]
    anchors = sorted(glob.glob(os.path.join(a.league, "anchor_*.pt")))
    assert snaps and anchors, "no snapshots or no anchor in {}".format(a.league)
    for f_ in snaps + anchors:
        dst = os.path.join(out, "snapshots", os.path.basename(f_))
        c_ = torch.load(f_, weights_only=False, map_location="cpu")
        rr = widen(c_, E)
        torch.save(c_, dst)
        say("league", dst, c_, *rr)
    ok = main_same(a.src, os.path.join(out, "policy.pt"))
    assert ok, "the widened start does not answer as the save"
    assert len(a.cmd_template) == len(a.cmd_out)
    for tp_, op_ in zip(a.cmd_template, a.cmd_out):
        mins = int((datetime.datetime.strptime(a.until, "%Y-%m-%d %H:%M") - datetime.datetime.now()).total_seconds() / 60.0 - a.setup_min)
        assert mins > 30, "--until is {} minutes away".format(mins)
        t_ = open(tp_, encoding="utf-8").read()
        assert "{MINUTES}" in t_ and "{GATE_START}" in t_
        t_ = t_.replace("{MINUTES}", str(mins)).replace("{GATE_START}", repr(minutes0))
        open(op_, "w", encoding="utf-8", newline=chr(13) + chr(10)).write(t_)
        print("wrote {} (--minutes {}: to {}; --gate-start {})".format(op_, mins, a.until, minutes0))
    print("ready:", out)


if __name__ == "__main__":
    args = sys.argv[1:]
    if not args:
        sys.exit(__doc__)
    if args[0] == "widen":
        main_widen(args[1], args[2])
    elif args[0] == "league":
        main_league(args[1:])
    elif args[0] == "same":
        sys.exit(0 if main_same(args[1], args[2]) else 1)
    elif args[0] == "opt":
        fl_ = args[args.index("--fill") + 1] if "--fill" in args else "median"
        main_opt(args[1], args[2], args[3], args[4], fill=fl_)
    elif args[0] == "prep":
        main_prep(args[1:])
    else:
        sys.exit(__doc__)

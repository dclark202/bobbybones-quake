"""v0.3.6 (docs/v0.4/ROCKETS_v0.3.6.md): a network of v0.3.5's shape made a network of the simulator with RL_AIM and PREFIRE
(sim/duel_env.py), the new parts closed: it answers as before.

    python tools/v036_init.py widen <in.pt> <out.pt>                 (a new file)
    python tools/v036_init.py league <file.pt> [<file.pt> ...]       (in place: the control, the league's files)
    python tools/v036_init.py same <old.pt> <new.pt>                 the two answer alike (numpy, random inputs; exit 1 if not)
    python tools/v036_init.py prep --from <v0.3.5's save .pt> --league <v0.3.5's snapshots folder> [--run duel_gru_v0_3_6]
                              [--cmd-template <.cmd> --cmd-out <.cmd> --until "2026-10-19 12:00" --setup-min 10]

widen / league: the 59 new inputs (N_RAIM 20, the group "v036 rocket aim"; N_PREF 39, "v036 prefire", at the end of the group
module's 856) get zero weight in the old encoder and mean 0, spread 1 in the input statistics; the attention part gets their
tokens (the kinds "rocket", one token, and "prefire", a token a place: tools/targets_init.py's widen_attn, a first layer and
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
Run it with the Anaconda Python; V036_ENV: the simulator module (default duel_env_ffa, the run's)."""
import os
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(HERE)
SIM = os.path.join(ROOT, "sim")
MODULE = os.environ.get("V036_ENV") or "duel_env_ffa"
INPUTS = os.path.join(ROOT, "docs", "INPUTS.csv")
NEW_KINDS = ["rocket", "prefire"]


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
    assert extra in (0, E.N_RAIM + E.N_PREF), "the network has {} inputs, the simulator {} (this converter adds the {} of N_RAIM and N_PREF only)".format(
        old_n, E.OBS_DIM, E.N_RAIM + E.N_PREF)
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
    assert r[0] == E.N_RAIM + E.N_PREF, "the save is not of v0.3.5's shape ({} inputs added)".format(r[0])
    torch.save(ck, os.path.join(out, "policy.pt"))
    shutil.copy(os.path.join(out, "policy.pt"), os.path.join(out, "keep", "policy_start.pt"))
    say("start", os.path.join(out, "policy.pt"), ck, *r)
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
    elif args[0] == "prep":
        main_prep(args[1:])
    else:
        sys.exit(__doc__)

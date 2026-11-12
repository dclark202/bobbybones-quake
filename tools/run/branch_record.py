"""2.1: frozen-moment branches recorded from a save WITHOUT training it, for tools/run/prune_inputs.py (owner, 2026-11-11: "before doing
any of the training we should run this appraisal and prune my ideas"). It runs the trainer itself on a scratch copy of the save, so the
moments, the forced first choices (instructions, the weapon-only ones of the owner's pattern under the binding weapon among them), the
outcomes and the win-chance dV are exactly the lesson's own (sim/branch.py; the trainer's --branch-dump writes each rollout's rows as the
appraisals would read them), with every learning rate at 0: the network that plays is the save, from the first rollout to the last.
The head's own share stays 0 (the branches' first choices are forced; play after the hold is his own, under no instruction).

    <anaconda python> tools/run/branch_record.py --policy <a save of list 21 with the head's part> --opt <its optimizer file>
        --league <a folder of league files of list 21> --mapsense <mapsense_start.pt> --name <scratch_21a_...> --out <dump folder>
        [--updates 6] [--branch-p 0.5] [--wpn-p 0.3] [--workers 16] [--matches 168] [--device cpu|cuda] [--fin <fin_rate json>]
    --name: a NEW scratch run folder under data/sim_runs (refused if it is there, or if the name does not begin with "scratch_").
A measurement: say its cores and whether it takes the graphics card before running it beside a run (CLAUDE.md rule 9). The settings are
the run's own command (docs/runs/2.1/2.1a/make_files.py, from 1.8a's current one): check_settings before using its numbers (rule 3)."""
import argparse
import glob
import importlib.util
import json
import os
import shutil
import sys
import time

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(os.path.dirname(HERE))
DROOT = os.environ.get("QLBOT_ROOT") or ROOT
RUN21 = os.path.join(ROOT, "docs", "runs", "2.1", "2.1a")
FROZEN = (("--lr", "0"), ("--control-lr", "0"), ("--win-value-lr", "0"), ("--head2-l2", "0"))     # nothing that plays learns
LIVE = dict(DRILL_INS_P=0.0, DRILL_INS_RATE=0.0, INS_G=0.0, H2_INS_PG=0.0, BRANCH_LONG_P=0.0, INS_LONG_W=0.0, MAP_SENSE_W=0.0, APPRAISE_W=0.0, KNOWN_W=0.0, SPAWN_W=0.0, INS_TEACH=0.0)


def plan_cmd(t, name, a, out):
    """the run's command -> the recorder's: frozen, its own name, cores and length, the dump"""
    import re
    ln = t.split("\n")
    ci = [i for i, x in enumerate(ln) if "train_duel_rnn.py" in x and not x.startswith("rem")]
    assert len(ci) == 1
    c = ln[ci[0]]
    for f_, v_ in FROZEN + (("--workers", str(a.workers)), ("--matches", str(a.matches)), ("--branch-wpn-p", "0")):
        assert len(re.findall(r" {} \S+ ".format(re.escape(f_)), c)) == 1, f_
        c = re.sub(r" {} \S+ ".format(re.escape(f_)), " {} {} ".format(f_, v_), c)
    assert c.count(" %LEARN% >> ") == 1
    c = c.replace(" %LEARN% >> ", " --snapshot-min 100000 --max-updates {} --branch-dump {} %LEARN% >> ".format(a.updates, out))
    ln[ci[0]] = c
    return "\n".join(x if x.startswith("rem") else x.replace("duel_gru_2_1a", name) for x in ln)


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--policy", required=True)
    ap.add_argument("--opt", required=True)
    ap.add_argument("--league", required=True)
    ap.add_argument("--mapsense", required=True)
    ap.add_argument("--name", required=True)
    ap.add_argument("--out", required=True)
    ap.add_argument("--updates", type=int, default=6)
    ap.add_argument("--branch-p", type=float, default=0.5)
    ap.add_argument("--wpn-p", type=float, default=0.3)
    ap.add_argument("--workers", type=int, default=16)
    ap.add_argument("--matches", type=int, default=168)
    ap.add_argument("--device", default="cpu", choices=("cpu", "cuda"))
    ap.add_argument("--fin", default="")
    ap.add_argument("--limit-min", type=float, default=600.0)
    a = ap.parse_args()
    assert a.name.startswith("scratch_"), "--name: a scratch run folder (scratch_...)"
    spec = importlib.util.spec_from_file_location("tests21a", os.path.join(RUN21, "tests.py"))
    T = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(T)
    D = T.new_dir(a.name)
    os.makedirs(a.out, exist_ok=True)
    assert not glob.glob(os.path.join(a.out, "br_*.npz")), "--out has dumps already: a new folder"
    shutil.copy2(a.policy, os.path.join(D, "policy.pt"))
    shutil.copy2(a.opt, os.path.join(D, "opt.pt"))
    for f in sorted(glob.glob(os.path.join(a.league, "anchor_*.pt"))):
        if not f.endswith("_list21.pt") or not os.path.exists(f.replace("_list21.pt", ".pt")):
            shutil.copy2(f, os.path.join(D, "snapshots", os.path.basename(f).replace("_list21.pt", ".pt")))
    shutil.copy2(a.mapsense, os.path.join(D, "keep", "mapsense_start.pt"))
    shutil.copy2(os.path.join(T.R18, "live_settings.env"), os.path.join(D, "live_settings.env"))
    T.live21(D, dict(LIVE, BRANCH_P=float(a.branch_p), BRANCH_WPN_P=float(a.wpn_p), INS_GATE=-30.0))
    full = T.cmd21(D, fin=a.fin, small_branches=False)
    t = plan_cmd(open(full, encoding="ascii").read().replace("\r\n", "\n"), a.name, a, a.out)
    BS = "\\"
    for x, y in (("set ROOT=%~dp0.." + BS + ".." + BS + ".." + BS + "..", "set ROOT={}\nset QLBOT_ROOT={}{}".format(
                    DROOT, DROOT, "\nset CUDA_VISIBLE_DEVICES=-1\nset OMP_NUM_THREADS=1" if a.device == "cpu" else "")),
                 ("cd /d %ROOT%", "cd /d " + ROOT), (">> data" + BS + "sim_runs" + BS, ">> %ROOT%" + BS + "data" + BS + "sim_runs" + BS)):
        assert t.count(x) >= 1, x
        t = t.replace(x, y)
    cmd = os.path.join(D, "record.cmd")
    open(cmd, "w", encoding="ascii", newline="").write(t.replace("\n", "\r\n"))
    shutil.copy2(os.path.join(os.path.dirname(T.CMD18), "aim2_env.cmd"), os.path.join(D, "aim2_env.cmd"))
    json.dump(dict(policy=a.policy, name=a.name, updates=a.updates, branch_p=a.branch_p, wpn_p=a.wpn_p, workers=a.workers, matches=a.matches, device=a.device,
                   frozen=dict(FROZEN), live=LIVE, time=time.strftime("%Y-%m-%d %H:%M")), open(os.path.join(a.out, "record.json"), "w"), indent=1)
    log = T.trainer(cmd, a.name, a.limit_min)
    fs = sorted(glob.glob(os.path.join(a.out, "br_*.npz")))
    import numpy as np
    n = sum(int(np.load(f)["Y"].shape[0]) for f in fs)
    print("{} dumps, {} branch rows in {}{}".format(len(fs), n, a.out, "" if log else " (THE TRAINER STILL RUNS OR DIED: see data/sim_runs/{}.log)".format(a.name)))
    return 0 if fs and log else 1


if __name__ == "__main__":
    sys.exit(main())

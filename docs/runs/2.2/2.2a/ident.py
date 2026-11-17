"""2.2a's identity test (the brief's test 2): the trainer with every new part on and silent against the same save without them. Two arms of the
smoke's small CPU trainer at a fixed seed (--seed 7, 2 updates, --dump-acts; no overlap, no own snapshots; the same two 2.1d anchors):
  X  2.1d's own command (docs/runs/2.1/2.1d/train.cmd) on 2.1d's end, 2.1d's live.json (none of the outlook's names)
  Y  2.2a's command (--outlook, --out22, --map-sense, DESC_OX=1, FIGHT_TRUTH=1, JUDGE_ITEMS=items_22a.json) on the start file (out22_init add)
     with the built outlook's, desc's and the tracker's last layers made NON-ZERO (smoke.nonzero: they learn and answer, but must not play),
     OUT_G 0, OUT_TRIAL 0, OUT_SRC 1
PASS: both updates' actions, log-probabilities (the hands' and the head's target), the hands' and the head's values, the pay, the round ends:
equal to the bit; the ledger (rec pay_terms) equal. SMOKE_OVERLAP=1: both arms with --overlap 1 --learn-nosync 1, as train.cmd has them (the review).
SAME_ARM=x: the second arm is X again (does the trainer repeat itself at this seed and setting?)
    set QLBOT_ROOT=...; <anaconda python> docs/runs/2.2/2.2a/ident.py <2.1d's end> <its opt> <the start file> <anchor a> <anchor b>"""
import json
import os
import subprocess
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
CODE = os.path.dirname(os.path.dirname(os.path.dirname(os.path.dirname(HERE))))
DATA = os.environ.get("QLBOT_ROOT") or ""
NOWIN = getattr(subprocess, "CREATE_NO_WINDOW", 0)
TAG = os.environ.get("TEST_TAG", "")


def arm(name, start, opt, a1, a2, extra_env):
    run = "scratch_22a_ident" + TAG + "_" + name
    D = os.path.join(DATA, "data", "sim_runs", run)
    env = dict(os.environ, TEST_TAG=TAG + "_ident_" + name, SMOKE_UPDATES="2", SMOKE_LEAGUE="0", SMOKE_OUT_G="0", SMOKE_TRIAL="0",
               SMOKE_EXTRA="--seed 7 --dump-acts " + os.path.join(DATA, "data", "sim_runs", "scratch_22a_smoke" + TAG + "_ident_" + name, "acts"), **extra_env)
    r = subprocess.run([sys.executable, os.path.join(HERE, "smoke.py"), start, opt, a1, a2], env=env, capture_output=True, text=True, creationflags=NOWIN)
    print("arm {}: {}".format(name, r.stdout.strip()[-600:]), flush=True)
    return os.path.join(DATA, "data", "sim_runs", "scratch_22a_smoke" + TAG + "_ident_" + name)


def main():
    import torch
    s21, o21, s22, a1, a2 = sys.argv[1:6]
    DX = arm("x", s21, o21, a1, a2, dict(SMOKE_CMD=os.path.join(CODE, "docs", "runs", "2.1", "2.1d", "train.cmd"), SMOKE_NO_OUT="1", SMOKE_NONZERO="0"))
    if os.environ.get("SAME_ARM") == "x":
        DY = arm("x2", s21, o21, a1, a2, dict(SMOKE_CMD=os.path.join(CODE, "docs", "runs", "2.1", "2.1d", "train.cmd"), SMOKE_NO_OUT="1", SMOKE_NONZERO="0"))
    else:
        DY = arm("y", s22, o21, a1, a2, dict(SMOKE_SRC="1", SMOKE_NONZERO="1"))
    ok = True
    for u in (1, 2):
        px, py = os.path.join(DX, "acts_{}.pt".format(u)), os.path.join(DY, "acts_{}.pt".format(u))
        if not (os.path.exists(px) and os.path.exists(py)):
            print("FAIL  update {}: a dump is missing ({}, {})".format(u, os.path.exists(px), os.path.exists(py)))
            ok = False
            continue
        X, Y = torch.load(px), torch.load(py)
        for k_ in ("act", "logp", "val", "rew", "done", "vh", "lpi"):
            if k_ not in X and k_ not in Y:
                continue
            eq_ = k_ in X and k_ in Y and X[k_].shape == Y[k_].shape and bool(torch.equal(X[k_], Y[k_]))
            nd_ = int((X[k_] != Y[k_]).sum()) if (k_ in X and k_ in Y and X[k_].shape == Y[k_].shape) else -1
            ok = ok and eq_
            print("{}  update {}: {} equal to the bit ({} numbers; {} differ)".format("PASS" if eq_ else "FAIL", u, k_, X[k_].numel() if k_ in X else 0, nd_))
    MX = [json.loads(x) for x in open(os.path.join(DX, "metrics.jsonl"))]
    MY = [json.loads(x) for x in open(os.path.join(DY, "metrics.jsonl"))]
    for u, (mx, my) in enumerate(zip(MX, MY)):
        eq_ = json.dumps(mx.get("pay_terms"), sort_keys=True) == json.dumps(my.get("pay_terms"), sort_keys=True)
        ok = ok and eq_
        print("{}  update {}: the ledger (pay_terms) equal: {}".format("PASS" if eq_ else "FAIL", u + 1, eq_))
    print("Y's silent parts learnt (the outlook's loss {}, the tracker's {}, the map sense's frames {})".format(
        (MY[-1].get("outlook") or {}).get("loss"), ((MY[-1].get("out22") or {}).get("tracker") or {}).get("loss"), (MY[-1].get("map_sense") or {}).get("frames")))
    print("ALL PASSED" if ok else "FAILED")
    return 0 if ok else 1


if __name__ == "__main__":
    sys.exit(main())

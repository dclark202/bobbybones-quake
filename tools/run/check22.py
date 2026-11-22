"""2.2a, the review's blocker: a network whose desc term plays, in the watcher's own check game (tools/duel_eval.py with tools/run/panel.py's
settings() of that network, as tools/run/watch.py runs it), against a control.
  a. panel.settings() of the file passes DESC_OX=1 on from its env_vars
  b. the check game plays (a few short games on one map): the description the checks' player read is not blank (the target "nothing" valid on
     every seat, the map sense's numbers not all zero) and the held desc term it played equals the trainer's torch sums (sim/desc22.py inputs and
     term on the head's torch module, from the same raw inputs and head states): the largest difference within one half-precision step
  c. the same game with DESC_OX taken out of the settings: the game refuses (a RuntimeError naming the missing map numbers), never zeros
    QLBOT_ROOT=<the checkout with data> python tools/run/check22.py --policy <a file whose desc term plays> --ctrl <a control> --work <new folder>"""
import argparse
import glob
import os
import subprocess
import sys

import numpy as np

ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
NOWIN = getattr(subprocess, "CREATE_NO_WINDOW", 0)


def run(a, sets, tag):
    d = os.path.join(a.work, tag)
    os.makedirs(d)
    js = os.path.join(d, "eval.json")
    cmd = [sys.executable, os.path.join(ROOT, "tools", "duel_eval.py"), "--run", "check22", "--policy", a.policy, "--opp", "policy:" + a.ctrl,
           "--opp-inputs", os.path.join(ROOT, "docs", "INPUTS.csv"), "--map", a.map, "--games", "2", "--minutes", str(a.minutes), "--procs", "1",
           "--swap", "--json", js, "--react-ms", "125", "--acquire-ms", "225", "--opp-react-ms", "125", "--opp-acquire-ms", "225", "--round", "600",
           "--opp-round", "600"]
    cmd += [x for s_ in sets for x in ("--set", s_)]
    env = dict(os.environ, OPENBLAS_NUM_THREADS="1", CUDA_VISIBLE_DEVICES="-1", DESC22_TRACE=os.path.join(d, "trace"))
    env.pop("DESC_OX", None)
    r = subprocess.run(cmd, cwd=os.environ.get("QLBOT_ROOT") or ROOT, env=env, capture_output=True, text=True, creationflags=NOWIN)
    open(js + ".log", "w").write(r.stdout + "\n" + r.stderr)
    return r, d


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--policy", required=True)
    ap.add_argument("--ctrl", required=True)
    ap.add_argument("--work", required=True)
    ap.add_argument("--map", default="campgrounds")
    ap.add_argument("--minutes", type=float, default=1.0)
    a = ap.parse_args()
    if os.path.exists(a.work):
        raise SystemExit(a.work + " is there: not run (nothing deleted)")
    os.makedirs(a.work)
    sys.path.insert(0, os.path.join(ROOT, "tools", "run"))
    sys.path.insert(0, os.path.join(ROOT, "sim"))
    os.environ.setdefault("PANEL_RUN", "check22")
    import panel as P
    sets = P.settings(0.0, a.policy)
    ok_a = "DESC_OX=1" in sets
    print("a. panel.settings() of the file: DESC_OX {}: {}".format("passed on" if ok_a else "MISSING", "PASS" if ok_a else "FAIL"), flush=True)
    r, d = run(a, sets, "with")
    tr_ = sorted(glob.glob(os.path.join(d, "trace_*.npz")))
    ok_b = r.returncode == 0 and bool(tr_)
    worst, n_, blank, msz = 0.0, 0, 0, 0.0
    if ok_b:
        import torch
        import head2 as H2
        import desc22 as D
        ck = torch.load(a.policy, weights_only=False, map_location="cpu")
        hm = H2.make_module(ck["head2"])
        hm.load_state_dict({k_[len("head2."):]: v_ for k_, v_ in ck["model"].items() if k_.startswith("head2.")})
        DL = ck["head2"]["desc22"]
        mi_ = [i_ for i_, n2_ in enumerate(DL["tgt"]) if n2_.startswith("map sense")]
        for p_ in tr_:
            z = np.load(p_)
            for i_ in range(20):
                if "term_{}".format(i_) not in z.files:
                    break
                si_, tg_ = D.inputs(DL, torch.from_numpy(z["sit_{}".format(i_)]), torch.from_numpy(z["tgt_{}".format(i_)]))
                tm_ = D.term(hm.dsc, DL, torch.from_numpy(z["h_{}".format(i_)][:, :int(ck["head2"]["size"])]), si_, tg_, float(z["g_{}".format(i_)]),
                             int(z["pick_{}".format(i_)])).numpy()
                worst = max(worst, float(np.abs(tm_ - z["term_{}".format(i_)]).max()))
                blank += int((z["valid_{}".format(i_)][:, 0] < 0.5).sum())
                msz = max(msz, float(np.abs(z["tgt_{}".format(i_)][..., mi_]).max()))
                n_ += 1
        ok_b = n_ > 0 and blank == 0 and msz > 0 and worst <= 2e-3
    print("b. the check game with desc's term (exit {}): {} readings traced; blank descriptions {}; the map sense's largest number {:.3f}; the held "
          "term against the trainer's torch sums: largest difference {:.2e}: {}".format(r.returncode, n_, blank, msz, worst, "PASS" if ok_b else "FAIL"),
          flush=True)
    if r.returncode != 0:
        print(r.stderr[-2000:])
    r2, d2 = run(a, [s_ for s_ in sets if not s_.startswith("DESC_OX=")], "without")
    msg_ = "without the order's map numbers" in (r2.stdout + r2.stderr) or "blank description" in (r2.stdout + r2.stderr)
    ok_c = r2.returncode != 0 and msg_
    print("c. the same game without DESC_OX: exit {}, the refusal named: {}: {}".format(r2.returncode, msg_, "PASS" if ok_c else "FAIL"), flush=True)
    ok = ok_a and ok_b and ok_c
    print("ALL PASSED" if ok else "FAILED", flush=True)
    return 0 if ok else 1


if __name__ == "__main__":
    sys.exit(main())

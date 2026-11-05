"""1.4c's two measurements before the start (CARD.md, "Before the start"), on the checks' machinery (tools/run/head2head.py: each seat its own
settings and lock, ten maps, seats swapped):
  level <1.4b's end.pt> [--games 20]
      the fitted start (tools/keep_init.py add, made here from that file as start.ps1 makes it) at share 1 (head2.keep_g 1: the keep choice
      decides every reading not forced) against the network it came from (the lock rule): 200 games. The standing rule for a fitted start: a
      full level check before a run. The summary keeps the source's sha256 (start.ps1 refuses a level check of another file).
      LEVEL PASS: a win rate of 45% or more (the step-back bar; flagged under 50%)
  blinders <save.pt> [--games 8]
      a save against itself (the lock rule both sides), play unchanged: the blinders before. Of the readings the lock held out of contact,
      how often the drawn target differed from the held one, after a sound (the enemy heard in the last second) and in quiet; how often a
      reading after a sound changed the target
Both write <out>/summary.json and print the keep counters (duel_env.intend's stats["keep"], both seats together).
    %USERPROFILE%\\anaconda3\\python.exe docs\\runs\\b1.4\\1.4c\\level.py level <1.4b's end.pt> --out docs\\runs\\b1.4\\1.4c\\level"""
import argparse
import glob
import json
import os
import subprocess
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.dirname(HERE))))


def keep_read(kp):
    q = lambda x, y: round(x / max(1.0, y), 4)
    return dict(rule_readings=int(kp[0]), rule_held=q(kp[1], kp[0]), rule_held_draw_differs=q(kp[2], kp[1]),
                his_readings=int(kp[3]), his_redecide=q(kp[4], kp[3]), his_changed=q(kp[5], kp[3]), his_kept_draw_differs=q(kp[6], kp[3] - kp[4]),
                his_redecide_contact=q(kp[8], kp[7]), forced=int(kp[9]),
                held_after_sound=int(kp[10]), held_after_sound_draw_differs=q(kp[11], kp[10]),
                held_quiet=int(kp[12]), held_quiet_draw_differs=q(kp[13], kp[12]),
                after_sound=int(kp[15]), after_sound_changed=q(kp[14], kp[15]))


def run(label, run_, a_, b_, games, out):
    cmd = [sys.executable, os.path.join(ROOT, "tools", "run", "head2head.py"), label, run_, a_, "8", b_, "8", "--out", out, "--games", str(games)]
    print(" ".join(cmd), flush=True)
    subprocess.check_call(cmd, cwd=ROOT)
    W = L = 0
    kp = [0.0] * 16
    for js in glob.glob(os.path.join(out, "*.json")):
        if os.path.basename(js) == "summary.json":
            continue
        v = list(json.load(open(js))["maps"].values())[0]
        W, L = W + v["won"], L + v["lost"]
        k_ = (v.get("st_raw") or {}).get("keep")
        if k_ and len(k_) == 16:
            kp = [x + y for x, y in zip(kp, k_)]
    return W, L, kp


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("mode", choices=("level", "blinders"))
    ap.add_argument("a")
    ap.add_argument("b", nargs="?", default="")
    ap.add_argument("--games", type=int, default=0)
    ap.add_argument("--out", required=True)
    ap.add_argument("--run", default="duel_gru_1_4c")
    a = ap.parse_args()
    os.makedirs(a.out, exist_ok=True)
    if a.mode == "level":
        import hashlib
        import torch
        st_ = os.path.join(a.out, "start.pt")
        subprocess.check_call([sys.executable, os.path.join(ROOT, "tools", "keep_init.py"), "add", a.a, st_], cwd=ROOT,
                              env=dict(os.environ, CUDA_VISIBLE_DEVICES="-1"))
        ck = torch.load(st_, map_location="cpu", weights_only=False)
        assert (ck.get("head2") or {}).get("keep") and "head2.keep.weight" in ck["model"], "the start has no keep choice"
        ck["model"]["head2.keep_g"] = torch.tensor(1.0)
        g1 = os.path.join(a.out, "start_g1.pt")
        torch.save(ck, g1)
        W, L, kp = run("level_g1", a.run, g1, a.a, a.games or 20, a.out)
        wr = W / max(1, W + L)
        res = dict(won=W, lost=L, win_rate=round(wr, 4), keep=keep_read(kp), start=st_, ref=a.a,
                   from_sha=hashlib.sha256(open(a.a, "rb").read()).hexdigest())
        json.dump(res, open(os.path.join(a.out, "summary.json"), "w"), indent=1)
        print(json.dumps(res, indent=1))
        print("LEVEL {}: the start at share 1 against {}: {}-{} = {:.1%}{}".format("PASS" if wr >= 0.45 else "FAIL", os.path.basename(a.a), W, L, wr,
                                                                               " (flag: under 50%)" if wr < 0.5 else ""))
        return 0 if wr >= 0.45 else 1
    W, L, kp = run("blinders", a.run, a.a, a.a, a.games or 8, a.out)
    res = dict(won=W, lost=L, keep=keep_read(kp), save=a.a)
    json.dump(res, open(os.path.join(a.out, "summary.json"), "w"), indent=1)
    print(json.dumps(res, indent=1))
    return 0


if __name__ == "__main__":
    sys.exit(main())

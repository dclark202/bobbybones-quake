"""1.7a's level check of the start (CARD.md, "Before the start"; the standing rule: a fitted start for a new choice passes a full level
check before a run), on the checks' machinery (tools/run/head2head.py: each seat its own settings and lock, ten maps, seats swapped):
  level <1.6a's end.pt> [--games 20]
      the fitted start (tools/keep_init.py add, made here from that file as start.ps1 makes it: re-fitted for five readings a second,
      arrivals keepable) at share 1 (head2.keep_g 1: the keep choice decides every second, the lock rule none) against the network it
      came from (the lock rule): 200 games. The summary keeps the source's sha256.
      LEVEL PASS: a win rate of 45% or more (flagged under 50%)
It writes <out>/summary.json and the keep counters (duel_env.intend's stats["keep"] and ["keep2"], both seats together). It runs from this
checkout (1.7a's code) with full paths, on the cores it is started on (the owner's).
    python docs\\runs\\1.7\\1.7a\\level.py level <1.6a's end.pt> --out <dir>"""
import argparse
import glob
import hashlib
import json
import os
import subprocess
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.dirname(HERE))))


def keep_read(kp, k2):
    q = lambda x, y: round(x / max(1.0, y), 4)
    return dict(rule_readings=int(kp[0]), rule_held=q(kp[1], kp[0]), forced=int(kp[9]),
                held_after_sound=int(kp[10]), held_after_sound_draw_differs=q(kp[11], kp[10]),
                held_quiet=int(kp[12]), held_quiet_draw_differs=q(kp[13], kp[12]),
                after_sound=int(kp[15]), after_sound_changed=q(kp[14], kp[15]),
                keep_seconds=round(k2[0] * 0.025, 1), keep_readings_a_second=q(k2[1], k2[0] * 0.025), keep_forced=q(k2[2], k2[1]),
                keep_decided=int(k2[3]), redecide=q(k2[4], k2[3]), changed=q(k2[5], k2[3]), arrived=int(k2[6]), redecide_arrived=q(k2[7], k2[6]),
                contact=int(k2[8]), redecide_contact=q(k2[9], k2[8]), heard=int(k2[10]), redecide_heard=q(k2[11], k2[10]),
                quiet=int(k2[12]), redecide_quiet=q(k2[13], k2[12]))


def run(label, run_, a_, b_, games, out):
    cmd = [sys.executable, os.path.join(ROOT, "tools", "run", "head2head.py"), label, run_, a_, "8", b_, "8", "--out", out, "--games", str(games)]
    print(" ".join(cmd), flush=True)
    subprocess.check_call(cmd, cwd=ROOT)
    W = L = 0
    kp, k2 = [0.0] * 16, [0.0] * 14
    for js in glob.glob(os.path.join(out, "*.json")):
        if os.path.basename(js) == "summary.json":
            continue
        v = list(json.load(open(js))["maps"].values())[0]
        W, L = W + v["won"], L + v["lost"]
        st_ = v.get("st_raw") or {}
        if st_.get("keep") and len(st_["keep"]) == 16:
            kp = [x + y for x, y in zip(kp, st_["keep"])]
        if st_.get("keep2") and len(st_["keep2"]) == 14:
            k2 = [x + y for x, y in zip(k2, st_["keep2"])]
    return W, L, kp, k2


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("mode", choices=("level",))
    ap.add_argument("a")
    ap.add_argument("--games", type=int, default=20)
    ap.add_argument("--out", required=True)
    ap.add_argument("--run", default="duel_gru_1_7a")
    a = ap.parse_args()
    os.makedirs(a.out, exist_ok=True)
    import torch
    st_ = os.path.join(a.out, "start.pt")
    subprocess.check_call([sys.executable, os.path.join(ROOT, "tools", "keep_init.py"), "add", a.a, st_], cwd=ROOT,
                          env=dict(os.environ, CUDA_VISIBLE_DEVICES="-1"))
    ck = torch.load(st_, map_location="cpu", weights_only=False)
    assert int((ck.get("head2") or {}).get("keep") or 0) == 2 and "head2.keep.weight" in ck["model"], "the start has no keep choice of 1.7a's"
    ck["model"]["head2.keep_g"] = torch.tensor(1.0)
    g1 = os.path.join(a.out, "start_g1.pt")
    torch.save(ck, g1)
    W, L, kp, k2 = run("level_g1", a.run, g1, a.a, a.games, a.out)
    wr = W / max(1, W + L)
    res = dict(won=W, lost=L, win_rate=round(wr, 4), keep=keep_read(kp, k2), start=st_, ref=a.a,
               from_sha=hashlib.sha256(open(a.a, "rb").read()).hexdigest())
    json.dump(res, open(os.path.join(a.out, "summary.json"), "w"), indent=1)
    print(json.dumps(res, indent=1))
    print("LEVEL {}: the start at share 1 against {}: {}-{} = {:.1%}{}".format("PASS" if wr >= 0.45 else "FAIL", os.path.basename(a.a), W, L, wr,
                                                                           " (flag: under 50%)" if wr < 0.5 else ""))
    return 0 if wr >= 0.45 else 1


if __name__ == "__main__":
    sys.exit(main())

"""1.7c's first experiment (owner, 2026-11-07: "I'll let you run experiments now ... I just want more fighting and varied weapons"):
does a weapon mix nearer the pros' cost him games with today's hands? No training: 1.7a's update-90 save (the result of 1.7a) with a
fixed push on his weapon key toward the pros' weapon in hand (sim/test_suite.py WeaponPush: in view by distance, out of view their
travelling hand) plays the same save unpushed, in the watcher's own check (ten maps, CHECK_GAMES ten-minute games a map, seats
swapped, both at 125 / 225 ms, each at its own lock, contact and WEAPON_OWN). The settings are the u90 check's own (its JSON's "set",
read back and compared with tools/run/panel.settings for this save: any difference refuses); the only difference is --wpush.
Run it under `start /affinity <mask>` (its games inherit the mask).

    python docs/runs/1.7/1.7c/exp/wpush.py --push 2 --out data/sim_runs/duel_gru_1_7a/wpush/p2 [--games 20] [--batch 4] [--maps a,b]
"""
import argparse
import json
import os
import subprocess
import sys
import time

ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))))
sys.path.insert(0, os.path.join(ROOT, "tools", "run"))
PY = os.environ.get("BB_PY") or r"C:\Users\dacla\anaconda3\python.exe"
SR = os.path.join(ROOT, "data", "sim_runs")
U90 = os.path.join(SR, "duel_gru_1_7a", "keep", "policy_90.pt")
MAPS = ["bloodrun", "aerowalk", "lostworld", "sinister", "furiousheights", "battleforged", "campgrounds", "hektik", "toxicity", "cure"]


def hold_args(pol, ctrl):
    """tools/run/watch.py hold_args (each side at its own lock, contact, WEAPON_OWN)"""
    import torch
    out = []
    for name, cname, wname, p_ in (("--hold", "--contact", "--wown", pol), ("--opp-hold", "--opp-contact", "--opp-wown", ctrl)):
        ev_ = torch.load(p_, map_location="cpu", weights_only=False).get("env_vars") or {}
        v_ = ev_.get("INTENT_HOLD")
        if v_ not in (None, ""):
            out += [name, str(v_)]
        out += [cname, str(ev_.get("CONTACT_FREE") or 0)]
        out += [wname, "1" if str(ev_.get("WEAPON_OWN") or "0") not in ("0", "", "0.0") else "0"]
    return out


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--policy", default=U90)
    ap.add_argument("--opp", default=U90)
    ap.add_argument("--push", type=float, required=True)
    ap.add_argument("--opp-push", type=float, default=0.0)
    ap.add_argument("--form", default="share", help="share or ratio (sim/test_suite.py WeaponPush)")
    ap.add_argument("--games", type=int, default=20)
    ap.add_argument("--minutes", type=float, default=10.0)
    ap.add_argument("--batch", type=int, default=4)
    ap.add_argument("--maps", default=",".join(MAPS))
    ap.add_argument("--out", required=True)
    ap.add_argument("--cy", action="store_true", help="Cypher's measures of the games (CY_REC) into <out>/cy")
    ap.add_argument("--affinity", default="", help="a processor mask in hex (0x3C3C: efficiency cores 2-5, 10-13; 0xC03C3: the performance cores); "
                    "its games inherit it")
    a = ap.parse_args()
    if a.affinity:
        import ctypes
        from ctypes import wintypes
        k32 = ctypes.WinDLL("kernel32", use_last_error=True)
        k32.GetCurrentProcess.restype = wintypes.HANDLE
        k32.SetProcessAffinityMask.argtypes = [wintypes.HANDLE, ctypes.c_size_t]
        k32.SetProcessAffinityMask.restype = wintypes.BOOL
        assert k32.SetProcessAffinityMask(k32.GetCurrentProcess(), int(a.affinity, 16)), "affinity not set: {}".format(ctypes.get_last_error())
        print("processor mask {}".format(a.affinity), flush=True)
    out = os.path.join(ROOT, a.out) if not os.path.isabs(a.out) else a.out
    os.makedirs(out, exist_ok=True)
    os.environ["PANEL_RUN"] = "duel_gru_1_7a"                    # (panel.live_caps: 1.7a's live.json)
    import panel as P
    ref_ = json.load(open(os.path.join(SR, "duel_gru_1_7a", "watch", "chk_90_prev_bloodrun.json")))["set"]
    seat_ = {k: v for k, v in ref_.items() if k.startswith("SEAT_")}      # (written by duel_eval from --hold / --contact / --wown: hold_args below)
    ref_ = {k: v for k, v in ref_.items() if not k.startswith("SEAT_")}
    sets = ["{}={}".format(k, v) for k, v in ref_.items()]
    mine = dict(x.split("=", 1) for x in P.settings(0.0, a.policy))
    ha_ = hold_args(a.policy, a.opp)
    hd_ = dict(zip(ha_[0::2], ha_[1::2]))
    am_ = {"--hold": "SEAT_HOLD_HE", "--opp-hold": "SEAT_HOLD_OPP", "--contact": "SEAT_CONTACT_HE", "--opp-contact": "SEAT_CONTACT_OPP",
           "--wown": "SEAT_WOWN_HE", "--opp-wown": "SEAT_WOWN_OPP"}
    mine.update({am_[k]: v for k, v in hd_.items()})
    ref_all = dict(ref_, **seat_)
    diff = sorted(set(mine) ^ set(ref_all)) + sorted(k for k in set(mine) & set(ref_all) if str(mine[k]) != str(ref_all[k]))
    if diff:
        print("REFUSED: the settings differ from 1.7a's u90 check:", {k: (mine.get(k), ref_all.get(k)) for k in diff}, flush=True)
        sys.exit(1)
    print("settings: 1.7a's u90 check's own ({} switches), checked against panel.settings for this save: identical".format(len(sets)), flush=True)
    env = dict(os.environ, OPENBLAS_NUM_THREADS="1", PYTHONFAULTHANDLER="1", CUDA_VISIBLE_DEVICES="-1")
    if a.cy:
        env["CY_REC"] = os.path.join(out, "cy")
    maps = a.maps.split(",")
    t0 = time.time()
    for w in range(0, len(maps), a.batch):
        jobs = []
        for mp in maps[w:w + a.batch]:
            js = os.path.join(out, "chk_{}.json".format(mp))
            cmd = [PY, "tools/duel_eval.py", "--run", "wpush_{}_{:g}".format(a.form, a.push), "--policy", a.policy, "--opp", "policy:" + a.opp, "--opp-inputs",
                   os.path.join(ROOT, "docs", "INPUTS.csv"), "--map", mp, "--games", str(a.games), "--minutes", str(a.minutes), "--procs", "2", "--swap",
                   "--json", js, "--react-ms", "125", "--acquire-ms", "225", "--opp-react-ms", "125", "--opp-acquire-ms", "225",
                   "--round", "600", "--opp-round", "600", "--wpush", str(a.push), "--opp-wpush", str(a.opp_push), "--wpush-form", a.form]
            cmd += [x for s_ in sets for x in ("--set", s_)]
            cmd += ha_
            jobs.append((mp, js, subprocess.Popen(cmd, cwd=ROOT, env=env, creationflags=0x4000 | 0x08000000, stdout=open(js + ".log", "w"),
                                                  stderr=subprocess.STDOUT)))
        for mp, js, p in jobs:
            p.wait()
            try:
                v = json.load(open(js))["maps"][mp]
                print("{} {}-{} share {:.1%} | {:.0f} min".format(mp, v["won"], v["lost"], v["frag_share"], (time.time() - t0) / 60), flush=True)
            except Exception as e:                           # noqa: BLE001
                print("{} ERROR {}".format(mp, repr(e)[:200]), flush=True)
    print("done in {:.0f} min".format((time.time() - t0) / 60), flush=True)


if __name__ == "__main__":
    main()

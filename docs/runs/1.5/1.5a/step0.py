"""1.5a's step 0, E1 and E3 (owner, 2026-11-04: "E1 + E3 only", overnight on cores 14-17; CARD.md "Before the start"). No run changed.

  E1  owning against choosing: a save against itself in whole ten-minute games on the ten maps (dump_eval with the panel's play settings,
      his seat's frames every 4th dumped): the time he owns each big weapon (with ammunition), the weapon he holds given what he owns, by
      the distance to the enemy (the simulator's, in view) and out of view; the first big weapon he holds after a spawn
  E3  does he ever try: his weapon key's chances on the same frames (the logits as he played them, dump_eval's wkp): of the rail with
      the enemy in view over 768 units, the rail owned and not in hand; of rockets under 300 with rockets owned and not in hand

    python docs/runs/1.5/1.5a/step0.py run <save.pt> <out dir> [--games 10] [--par 4] [--label duel_gru_1_4c]
    python docs/runs/1.5/1.5a/step0.py report <out dir>          (writes <out dir>/step0.json and prints the tables)
Run under the caller's cores (overnight.ps1: 14-17, idle priority) with CUDA_VISIBLE_DEVICES=-1."""
import argparse
import csv
import glob
import json
import os
import subprocess
import sys
import time

import numpy as np

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.dirname(HERE))))
PY = os.environ.get("BB_PY") or sys.executable
MAPS = ("bloodrun", "aerowalk", "lostworld", "sinister", "furiousheights", "battleforged", "campgrounds", "hektik", "toxicity", "cure")
BIG = ("rl", "rg", "lg")
NAMES = {"rl": "rocket launcher", "rg": "railgun", "lg": "lightning gun"}
BANDS = ((0, 300), (300, 700), (700, 1e9))


def say(s):
    print(time.strftime("%H:%M:%S ") + s, flush=True)


def run(a):
    os.environ.setdefault("PANEL_RUN", a.label)
    sys.path.insert(0, os.path.join(ROOT, "tools", "run"))
    import panel as P_
    os.makedirs(a.out, exist_ok=True)
    try:
        ps = float(json.load(open(os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(a.save))), "live.json"))).get("PERCEPT_SPEED") or 0.0)
    except Exception:                                        # noqa: BLE001
        ps = 0.0
    sets = P_.settings(ps, a.save)
    env = dict(os.environ, DUMP_OUT=os.path.join(a.out, "dumps"), OPENBLAS_NUM_THREADS="1", PYTHONFAULTHANDLER="1", CUDA_VISIBLE_DEVICES="-1",
               PANEL_CODE=ROOT)
    J = []
    for mp in MAPS:
        js = os.path.join(a.out, "eval_{}.json".format(mp))
        if os.path.exists(js):
            continue
        cmd = [PY, os.path.join(ROOT, "tools", "run", "dump_eval.py"), "--run", a.label, "--policy", a.save, "--map", mp, "--games", str(a.games),
               "--minutes", "10", "--procs", "1", "--json", js, "--round", "600", "--seed", "1500", "--react-ms", "125", "--acquire-ms", "225",
               "--opp", "policy:" + a.save, "--opp-inputs", os.path.join(ROOT, "docs", "INPUTS.csv"), "--opp-round", "600",
               "--opp-react-ms", "125", "--opp-acquire-ms", "225"]
        cmd += [x for s_ in sets for x in ("--set", s_)]
        J.append((cmd, js))
    say("E1/E3: {} against itself, {} maps x {} ten-minute games, {} at once (PERCEPT_SPEED {})".format(a.save, len(J), a.games, a.par, ps))
    live = []
    while J or live:
        while J and len(live) < a.par:
            cmd, js = J.pop(0)
            live.append((subprocess.Popen(cmd, cwd=ROOT, env=env, stdout=open(js + ".log", "w"), stderr=subprocess.STDOUT), js))
        time.sleep(10)
        for p_, js in list(live):
            if p_.poll() is not None:
                live.remove((p_, js))
                say("{} done (exit {})".format(os.path.basename(js), p_.returncode))
    report(a)


def report(a):
    ic = {r["input"]: int(r["index"]) for r in csv.DictReader(open(os.path.join(ROOT, "docs", "INPUTS.csv"), encoding="utf-8"))}
    c = dict(dead=ic["dead"], hold=[ic["holding " + NAMES[w]] for w in BIG], own=[ic["owns " + NAMES[w]] for w in BIG],
             ammo=[ic["ammo: " + NAMES[w]] for w in BIG], hold_all=[ic[k] for k in sorted(ic) if k.startswith("holding ")])
    F = sorted(glob.glob(os.path.join(a.out, "dumps", "dump_*.npz")))
    assert F, "no dumps in " + os.path.join(a.out, "dumps")
    O, PO, EN, VIS, SEAT, WK, FI = [], [], [], [], [], [], []
    for i_, f in enumerate(F):
        z = np.load(f)
        O.append(z["obs"])
        PO.append(z["pos"])
        EN.append(z["en"])
        VIS.append(z["vis"])
        SEAT.append(z["seat"])
        WK.append(z["wkp"].astype(np.float64) if "wkp" in z.files else np.full((len(z["obs"]), 10), np.nan))
        FI.append(np.full(len(z["obs"]), i_))
    O, PO, EN, VIS, SEAT, WK, FI = (np.concatenate(x) for x in (O, PO, EN, VIS, SEAT, WK, FI))
    alive = O[:, c["dead"]] < 0.5
    own = (O[:, c["own"]] > 0.5) & (O[:, c["ammo"]] > 0.0)                   # [n, 3] rockets, rail, lightning with ammunition
    hold = O[:, c["hold"]] > 0.5
    d = np.sqrt(((PO - EN) ** 2).sum(1))
    out = dict(frames=int(alive.sum()), files=len(F))
    out["E1_owning"] = {w: round(float(own[alive, i].mean()), 4) for i, w in enumerate(BIG)}
    out["E1_owning_all_three"] = round(float(own[alive].all(1).mean()), 4)
    hold_tab = {}
    for k_, m_ in (("in view", alive & VIS), ("out of view", alive & ~VIS)):
        hold_tab[k_] = {w: round(float(hold[m_, i].mean()), 4) for i, w in enumerate(BIG)}
    out["E1_in_hand"] = hold_tab
    by = {}
    for lo, hi in BANDS:                                     # in view: his weapon by distance, all, and given he owns all three
        m_ = alive & VIS & (d >= lo) & (d < hi)
        m3_ = m_ & own.all(1)
        key = "{}-{}".format(lo, int(hi) if hi < 1e8 else "")
        by[key] = dict(frames=int(m_.sum()), hand={w: round(float(hold[m_, i].mean()), 4) for i, w in enumerate(BIG)},
                       owns_all_frames=int(m3_.sum()),
                       hand_owning_all={w: round(float(hold[m3_, i].mean()), 4) for i, w in enumerate(BIG)} if m3_.any() else None,
                       given_owned={w: round(float(hold[m_ & own[:, i], i].mean()), 4) if (m_ & own[:, i]).any() else None for i, w in enumerate(BIG)})
    out["E1_in_view_by_distance"] = by
    first = {w: 0 for w in BIG}                              # the first big weapon in hand after a spawn (his seats, frames in order per file)
    for f_ in np.unique(FI):
        for s_ in np.unique(SEAT[FI == f_]):
            m_ = (FI == f_) & (SEAT == s_)
            dd_, hh_ = ~alive[m_], hold[m_]
            armed = None
            for t in range(len(dd_)):
                if dd_[t]:
                    armed = False
                elif armed is False and hh_[t].any():
                    first[BIG[int(np.argmax(hh_[t]))]] += 1
                    armed = True
    tot = max(1, sum(first.values()))
    out["E1_first_big_after_spawn"] = {w: round(first[w] / tot, 4) for w in BIG}
    out["E1_first_big_after_spawn_n"] = int(tot)
    ok_ = ~np.isnan(WK[:, 0])
    e3 = {}
    for name, w_i, key_i, cond in (("rail, enemy in view over 768, rail owned not in hand", 1, 2, (d > 768)),
                                   ("rail, enemy in view 500-768, rail owned not in hand", 1, 2, (d > 500) & (d <= 768)),
                                   ("rockets, enemy in view under 300, rockets owned not in hand", 0, 1, (d < 300)),
                                   ("lightning, enemy in view over 768, lightning owned not in hand", 2, 3, (d > 768))):
        m_ = ok_ & alive & VIS & cond & own[:, w_i] & ~hold[:, w_i]
        p_ = WK[m_, key_i]
        e3[name] = dict(frames=int(m_.sum()), p_mean=round(float(p_.mean()), 5) if m_.any() else None,
                        p_median=round(float(np.median(p_)), 5) if m_.any() else None,
                        share_over_5pct=round(float((p_ > 0.05).mean()), 4) if m_.any() else None,
                        per_second=round(float(p_.mean()) * 10.0, 4) if m_.any() else None)   # (the key is read 10 times a second)
    out["E3_weapon_key"] = e3
    out["E3_note"] = ("p: his chance of pressing that weapon's key at a reading of the key (read every 4th frame: 10 a second); "
                      "per_second: the expected presses a second in that state")
    json.dump(out, open(os.path.join(a.out, "step0.json"), "w"), indent=1)
    print(json.dumps(out, indent=1))


def main():
    ap = argparse.ArgumentParser()
    sp = ap.add_subparsers(dest="cmd", required=True)
    p = sp.add_parser("run")
    p.add_argument("save")
    p.add_argument("out")
    p.add_argument("--games", type=int, default=10)
    p.add_argument("--par", type=int, default=4)
    p.add_argument("--label", default="duel_gru_1_4c")
    p = sp.add_parser("report")
    p.add_argument("out")
    a = ap.parse_args()
    run(a) if a.cmd == "run" else report(a)


if __name__ == "__main__":
    main()

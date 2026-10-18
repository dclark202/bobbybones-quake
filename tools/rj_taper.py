"""v0.3.6's rocket jump runs, for the taper (docs/v0.4/ROCKETS_v0.3.6.md item 6; the owner, 2026-10-17: 10% of his time for
this run's first stretch, then, when his clears stop rising, the jumps he clears opened on his ways in games (RJ_OPEN) and the
runs down to about 2%, later 0). Reads only: the run's metrics.jsonl (the trainer's v15.rj_* per update) and, for the
numbers of the links, each map's list as the simulator keeps it.

    python tools/rj_taper.py --run duel_gru_v0_3_6 [--window 10] [--flat 0.02] [--checks 3]
                             [--min-share 0.5] [--min-tries 40] [--last 30] [--cmd <the run's .cmd>] [--maps a,b,...]

  - the curve: the share of the tries that arrived, per window of --window updates (a check), and whether the last --checks
    windows are flat (none above the best before them by more than --flat): "stop rising" is that;
  - per map and link over the last --last updates: tries, arrivals, the share; and its number in the map's list of
    docs/pro_rocket_jumps.json (the RJ_OPEN numbers). The links' order in the metrics is the simulator's (the cleared links
    that are on its walking map: RJ_CLEARED); to name them the simulator is built once a map with the run's switches
    (--cmd: its `set` lines; one match, no game is played; a second or two a map);
  - the RJ_OPEN line for the links with --min-tries or more tries and an arrival share of --min-share or more.
The change itself is a restart's (after a checkpoint save): RJ_RUN_P and RJ_OPEN are read by the simulators when they start."""
import argparse
import json
import os
import subprocess
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(HERE)


def ids_of(mapname, cmd):
    """the numbers (in docs/pro_rocket_jumps.json) of the map's rocket jumps in the order the simulator counts them"""
    env = dict(os.environ)
    if cmd:
        for l_ in open(cmd, encoding="utf-8"):
            l_ = l_.strip()
            if l_.lower().startswith("set ") and "=" in l_:
                k_, v_ = l_[4:].split("=", 1)
                env[k_] = v_
    env.update(RJ_RUN_P=env.get("RJ_RUN_P") if float(env.get("RJ_RUN_P") or 0) > 0 else "0.1", CUDA_VISIBLE_DEVICES="-1", OPENBLAS_NUM_THREADS="1")
    code = ("import os,sys,json;sys.path.insert(0,{!r});import duel_env as E;m={!r};"
            "e=E.DuelEnv(os.path.join({!r},m+'.bsp'),n_matches=1,seed=0,nav=os.path.join({!r},'nav_'+m+'_sim.json'));"
            "print(json.dumps([int(r['id']) for r in e.rjs]))").format(os.path.join(ROOT, "sim"), mapname, os.path.join(ROOT, "data", "maps"),
                                                                       os.path.join(ROOT, "data", "maps"))
    out = subprocess.run([sys.executable, "-c", code], env=env, capture_output=True, text=True)
    if out.returncode != 0:
        return None
    return json.loads(out.stdout.strip().splitlines()[-1])


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--run", required=True)
    ap.add_argument("--window", type=int, default=10)
    ap.add_argument("--flat", type=float, default=0.02)
    ap.add_argument("--checks", type=int, default=3)
    ap.add_argument("--min-share", type=float, default=0.5)
    ap.add_argument("--min-tries", type=int, default=40)
    ap.add_argument("--last", type=int, default=30)
    ap.add_argument("--cmd", default="")
    ap.add_argument("--maps", default="")
    ap.add_argument("--metrics", default="", help="another metrics.jsonl than the run's")
    ap.add_argument("--no-ids", action="store_true", help="do not build the simulator for the links' numbers")
    a = ap.parse_args()
    rows = []
    for l_ in open(a.metrics or os.path.join(ROOT, "data", "sim_runs", a.run, "metrics.jsonl"), encoding="utf-8"):
        try:
            d = json.loads(l_)
        except ValueError:
            continue
        v = d.get("v15") or {}
        rows.append((int(d.get("update", len(rows) + 1)), float(d.get("minutes", 0.0)), int(v.get("rj_tries", 0)),
                     float(v.get("rj_over", 0.0)), float(v.get("rj_run_frames", 0.0)), v.get("rjs") or {}))
    rows = [r for r in rows if r[2] > 0]
    if not rows:
        sys.exit("no rocket jump tries in the metrics yet")
    print("updates with tries: {} (update {} to {}); share of his frames in the runs (last): {:.3f}".format(len(rows), rows[0][0], rows[-1][0], rows[-1][4]))
    win = []
    for i in range(0, len(rows), a.window):
        w_ = rows[i:i + a.window]
        t_ = sum(r[2] for r in w_)
        o_ = sum(r[2] * r[3] for r in w_)
        win.append((w_[0][0], w_[-1][0], t_, o_ / max(1.0, t_)))
    print("the curve (arrived / tries, a window of {} updates):".format(a.window))
    for u0, u1, t_, s_ in win:
        print("  updates {:>5d}-{:<5d} tries {:>7d} arrived {:.3f}".format(u0, u1, t_, s_))
    full = [w_ for w_ in win if w_[1] - w_[0] + 1 >= a.window]
    if len(full) > a.checks:
        best_before = max(w_[3] for w_ in full[:-a.checks])
        flat = all(w_[3] <= best_before + a.flat for w_ in full[-a.checks:])
        print("the last {} full windows {} (best before them {:.3f}, flat within {:+.3f})".format(
            a.checks, "are FLAT: the clears have stopped rising" if flat else "still rise", best_before, a.flat))
    else:
        print("fewer than {} full windows: no plateau can be read yet".format(a.checks + 1))
    last = rows[-a.last:]
    per = {}
    for r in last:
        for m_, lk in r[5].items():
            acc = per.setdefault(m_, {})
            for j_, (t_, s_) in enumerate(lk):
                c_ = acc.setdefault(j_, [0.0, 0.0])
                c_[0] += t_
                c_[1] += t_ * s_
    maps = [m_ for m_ in (a.maps.split(",") if a.maps else sorted(per)) if m_]
    opens = []
    for m_ in maps:
        ids = None if a.no_ids else ids_of(m_, a.cmd)
        got = []
        print("{} (the last {} updates):".format(m_, len(last)))
        for j_, (t_, o_) in sorted(per.get(m_, {}).items()):
            nm_ = ids[j_] if ids is not None and j_ < len(ids) else None
            ok_ = t_ >= a.min_tries and o_ / max(1.0, t_) >= a.min_share
            print("  link {:>2d} (number {}): tries {:>6.0f} arrived {:>6.0f} share {:.2f}{}".format(
                j_, nm_ if nm_ is not None else "?", t_, o_, o_ / max(1.0, t_), "  OPEN" if ok_ else ""))
            if ok_ and nm_ is not None:
                got.append(nm_)
        if got:
            opens.append("{}:{}".format(m_, ",".join(str(x_) for x_ in sorted(got))))
    print("RJ_OPEN={}".format(";".join(opens)) if opens else "nothing to open (at --min-tries {} and --min-share {})".format(a.min_tries, a.min_share))


if __name__ == "__main__":
    main()

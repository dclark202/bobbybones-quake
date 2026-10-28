"""(B data, 2026-10-28: v0.6.0's own aim on both seats: !aim default 125 / 225 ms and the aim2 block of panel_v061r.py;
the calibration window's games of 10-28 05:02 ran at 100 / 200 ms with RANGE_WEBER 0.15) winsense: play a checkpoint against a fixed opponent with the run's check settings (as the watcher's checks: ten maps, seats
swapped, !aim default 100 / 200 ms, whole games, the run's live PERCEPT_SPEED and caps) and log his shadow win value once a
second (ws_eval.py, built from the run's tools/duel_eval.py by make_ws_eval.py).
    python run_ws.py --policy <ckpt.pt> --tag <name> [--opp <ckpt.pt>] [--games 8] [--par 2] [--procs 2] [--maps a,b] [--minutes 10]
Rows go to out/<tag>/rows_<map>.json; then: python score_ws.py <tag> [<tag> ...]"""
import argparse, json, os, subprocess, sys, time
ROOT_ = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))   # (the repo root: tools/run/ is two down)

HERE = os.path.dirname(os.path.abspath(__file__))
SP = os.path.dirname(HERE)
sys.path.insert(0, HERE)
os.environ.setdefault("PANEL_RUN", "duel_gru_v0_6_0")
import panel as P                                       # (read only: its settings(), the checks' switches; PANEL_SETS: v0.6.0's aim switches)

PY = (os.environ.get("BB_PY") or r"C:\Users\dacla\anaconda3\python.exe")
CODE = os.environ.get("PANEL_CODE") or ROOT_
SR = os.path.join(ROOT_, "data", "sim_runs")
CTRL42 = os.path.join(SR, "duel_gru_v0_4_2", "keep", "policy_end_v042.pt")
MAPS = ["bloodrun", "aerowalk", "lostworld", "sinister", "furiousheights", "battleforged", "campgrounds", "hektik", "toxicity", "cure"]


def live_ps(run):
    try:
        return float(json.load(open(os.path.join(SR, run, "live.json"))).get("PERCEPT_SPEED") or 0.0)
    except Exception:                                        # noqa: BLE001
        return 0.0


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--policy", required=True)
    ap.add_argument("--tag", required=True)
    ap.add_argument("--opp", default="self", help="a checkpoint, or self: the policy against itself (the fits want self-play)")
    ap.add_argument("--games", type=int, default=8, help="games a map")
    ap.add_argument("--procs", type=int, default=2, help="processes a map (even: seats swapped in every second)")
    ap.add_argument("--par", type=int, default=2, help="maps at once")
    ap.add_argument("--maps", default=",".join(MAPS))
    ap.add_argument("--minutes", type=float, default=10.0)
    ap.add_argument("--ps", type=float, default=None, help="PERCEPT_SPEED (default: the run's live.json now)")
    ap.add_argument("--run", default="duel_gru_v0_6_0")
    ap.add_argument("--seed", type=int, default=700)
    a = ap.parse_args()
    if a.opp == "self":
        a.opp = a.policy
    ps = live_ps(a.run) if a.ps is None else a.ps
    sets = P.settings(ps)
    out = os.path.join(SR, a.run, "selfplay", a.tag)
    os.makedirs(out, exist_ok=True)
    json.dump(dict(policy=a.policy, opp=a.opp, sets=sets, games=a.games, maps=a.maps, minutes=a.minutes, started=time.strftime("%Y-%m-%d %H:%M")),
              open(os.path.join(out, "meta.json"), "w"), indent=1)
    env = dict(os.environ, OPENBLAS_NUM_THREADS="1", PYTHONFAULTHANDLER="1", CUDA_VISIBLE_DEVICES="-1", OMP_NUM_THREADS="1")
    todo = [m for m in a.maps.split(",") if not os.path.exists(os.path.join(out, "rows_{}.json".format(m)))]
    run_ = []
    while todo or run_:
        while todo and len(run_) < a.par:
            mp = todo.pop(0)
            js = os.path.join(out, "eval_{}.json".format(mp))
            cmd = [PY, os.path.join(HERE, "ws_eval.py"), "--run", a.run, "--policy", a.policy, "--opp", "policy:" + a.opp, "--opp-inputs",
                   os.path.join(CODE, "docs", "INPUTS.csv"), "--map", mp, "--games", str(a.games), "--minutes", str(a.minutes), "--procs", str(a.procs),
                   "--swap", "--json", js, "--react-ms", "125", "--acquire-ms", "225", "--opp-react-ms", "125", "--opp-acquire-ms", "225",
                   "--round", "600", "--opp-round", "600", "--seed", str(a.seed), "--ws-out", out]
            cmd += [x for s_ in sets for x in ("--set", s_)]
            print(time.strftime("%H:%M:%S"), "start", mp, flush=True)
            run_.append((mp, subprocess.Popen(cmd, cwd=CODE, env=env, creationflags=0x40 | 0x08000000, stdout=open(js + ".log", "w"),
                                              stderr=subprocess.STDOUT)))
        time.sleep(5)
        for x in list(run_):
            if x[1].poll() is not None:
                print(time.strftime("%H:%M:%S"), "done", x[0], "exit", x[1].returncode, flush=True)
                run_.remove(x)
    print(time.strftime("%H:%M:%S"), "all done", flush=True)


if __name__ == "__main__":
    main()

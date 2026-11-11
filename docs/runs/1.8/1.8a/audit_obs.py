"""The input audit's sample (owner, 2026-11-11: "audit ALL of his current inputs"): phase 1's command at FULL size for 2 updates on a scratch
copy of 1.8a's start (data/sim_runs/scratch_18a_obs), with the trainer's --obs-dump: 0.5% of the rows of raw inputs of both updates
(about 38,000 rows, all ten maps, the league's seats and his own), written to data/sim_runs/scratch_18a_obs/obs.npy. Nothing of a real
run is touched. No trainer may be running.
    %USERPROFILE%\\anaconda3\\python.exe docs\\runs\\1.8\\1.8a\\audit_obs.py"""
import os
import re
import shutil
import subprocess
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
import tests as T                                             # noqa: E402

RUN = "scratch_18a_obs" + T.TAG


def main():
    D = T.lay_out(RUN)
    subprocess.check_call([T.PY, os.path.join(HERE, "make_files.py"), "1700", "1"], stdout=subprocess.DEVNULL)
    t = open(T.CMD, encoding="ascii").read().replace("\r\n", "\n")
    out = os.path.join(D, "obs.npy")
    for a, b in (("set ROOT=%~dp0.." + T.BS + ".." + T.BS + ".." + T.BS + "..", "set ROOT={}".format(T.ROOT)),
                 ("%LEARN% >> ", "%LEARN% --max-updates 2 --obs-dump {} --obs-dump-from 1 --obs-dump-to 2 >> ".format(out))):
        assert t.count(a) == 1, a
        t = t.replace(a, b)
    t = re.sub(r"--run duel_gru_\S+ ", "--run {} ".format(RUN), t)
    t = re.sub(r"data\\sim_runs\\duel_gru_[0-9a-z_]+\.log", lambda m_: "data" + T.BS + "sim_runs" + T.BS + RUN + ".log", t)
    assert not any(("duel_gru_1_" in x or "duel_gru_2_" in x) for x in t.split("\n") if not x.startswith("rem"))
    c_ = os.path.join(D, "obs.cmd")
    open(c_, "w", encoding="ascii", newline="").write(t.replace("\n", "\r\n"))
    shutil.copy2(os.path.join(HERE, "aim2_env.cmd"), os.path.join(D, "aim2_env.cmd"))
    log = T.trainer(c_, RUN, 40)
    print("exit ok" if log and log.rstrip().splitlines()[-1].strip() == "exit 0" else "FAILED", "|", [x for x in (log or "").splitlines() if "rows of raw inputs" in x])
    return 0 if os.path.exists(out) else 1


if __name__ == "__main__":
    sys.exit(main())

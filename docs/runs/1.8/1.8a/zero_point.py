"""1.8a's zero point against the point it is re-reaching (docs/runs/1.8/1.8a/CARD.md): the START (b1.2d's end with the head and the keep
choice at zero effect: it plays as b1.2d's end) against 1.7a's update 90, exactly as the watcher will play the run's fourth checks: 200 games
(20 a map, seats swapped), both seats under AIM3's end values, COMBAT on for 1.7a's order inputs (start.ps1's PANEL_SETS, read from it).
The start against b1.2d's end needs no games: the two answer alike to the action (tests.py start), and b1.2d's end against itself read
51.2% in 600 games (1.3b's card). A scratch run folder (data/sim_runs/scratch_18a_zero), nothing of a real run touched, CPU only; run it on
the efficiency cores:  cmd /c start "" /b /wait /affinity 3C3C %USERPROFILE%\\anaconda3\\python.exe docs\\runs\\1.8\\1.8a\\zero_point.py"""
import json
import os
import re
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.dirname(HERE))))
sys.path.insert(0, HERE)
sys.path.insert(0, os.path.join(ROOT, "tools", "run"))
RUN = "scratch_18a_zero" + os.environ.get("TEST_TAG", "")


def main():
    import tests as T
    D = T.lay_out(RUN)
    ps1 = open(os.path.join(HERE, "start.ps1"), encoding="utf-8").read()
    sets = re.findall(r'^\$env:PANEL_SETS = "([^"]+)"', ps1, re.M)
    assert len(sets) == 1 and "AIM3_W=1" in sets[0] and "COMBAT=1" in sets[0], sets
    os.environ.update(PANEL_SETS=sets[0], PANEL_RUN=RUN, PANEL_CTRL=T.C17, CTRL_PREV=T.C17, CTRL_PREV_LABEL="1.7a's update 90", CHECK_GAMES="20",
                      CHECK_BATCH="4", CHECK_RULE="0", CHECK_CYPHER="0")
    sys.argv = [sys.argv[0], RUN]
    import watch as W
    W.games(os.path.join(D, "policy.pt"), 0, T.C17, "1.7a's update 90 (the zero point: the start plays as b1.2d's end)", W.live_ps())
    r = [json.loads(x) for x in open(os.path.join(D, "watch", "checks_prev.jsonl"))][-1]
    print("ZERO POINT: the start against 1.7a's update 90: {}-{} = {:.1%}, frag share {:.1%}".format(r["won"], r["lost"], r["won"] / max(1, r["won"] + r["lost"]), r["mean"]))
    return 0


if __name__ == "__main__":
    sys.exit(main())

"""2.2e: the watcher's two new settings tested on made-up check results (tools/run/watch.py CHECK_DELAYS, CHECK_ALARMS): duel_eval is not run; a
stand-in writes each map's result file. Three cases: no alarm (his red share 0.40, the opponent's 0.42; empty 0.5 %), the red armor alarm (0.33
against 0.40), the empty weapon alarm (2 %). Each check's delays in the command line it would run (100 / 175 for both seats). Scratch folder
data/sim_runs/scratch_22e_watchtest (nothing deleted).
    QLBOT_ROOT=<checkout> python docs/runs/2.2/2.2e/watch_test.py"""
import json
import os
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.normpath(os.path.join(HERE, "..", "..", "..", ".."))
RUN = "scratch_22e_watchtest"
os.environ.update(CHECK_DELAYS="100,175", CHECK_ALARMS="1", QLBOT_ROOT=os.environ.get("QLBOT_ROOT") or ROOT, CHECK_BATCH="10")
sys.argv = ["watch.py", RUN]
sys.path.insert(0, os.path.join(ROOT, "tools", "run"))
import watch as W  # noqa: E402

CASES = {"none": (0.40, 0.42, 0.005), "red": (0.33, 0.40, 0.005), "empty": (0.41, 0.40, 0.02)}
CMDS = []


class FakeP:
    def __init__(self, cmd, **kw):
        CMDS.append(cmd)
        js = cmd[cmd.index("--json") + 1]
        mp = cmd[cmd.index("--map") + 1]
        he_r, op_r, em = CASE[0]
        row = dict(frag_share=0.5, won=10, lost=10, he=dict(hit_rate={}, shots_per_min={}, red_share=he_r, empty_in_hand=em),
                   opponent=dict(red_share=op_r))
        json.dump({"maps": {mp: row}}, open(js, "w"))

    def wait(self):
        return 0


CASE = [None]
W.subprocess.Popen = FakeP
W.P.settings = lambda ps, pol=None: []
W.hold_args = lambda pol, ctrl, table=False: []
ok = True
for k_, v_ in CASES.items():
    CASE[0] = v_
    n0 = len(CMDS)
    W.games("pol.pt", {"none": 10, "red": 20, "empty": 30}[k_], W.CTRL_PREV, "the control", 0.0)
    rec = [json.loads(x) for x in open(os.path.join(W.WD, "checks_prev.jsonl"))][-1]
    dl_ = {(c[c.index("--react-ms") + 1], c[c.index("--acquire-ms") + 1], c[c.index("--opp-react-ms") + 1], c[c.index("--opp-acquire-ms") + 1]) for c in CMDS[n0:]}
    want_ = {"none": 0, "red": 1, "empty": 1}[k_]
    good_ = len(rec.get("alarms", [])) == want_ and dl_ == {("100", "175", "100", "175")}
    ok &= good_
    print("{}: alarms {} | delays {} | {}".format(k_, rec.get("alarms"), dl_, "PASS" if good_ else "FAIL"))
print("watch.log:")
print("".join(open(os.path.join(W.WD, "watch.log")).readlines()[-9:]))
print("WATCH TEST " + ("PASS" if ok else "FAIL"))
sys.exit(0 if ok else 1)

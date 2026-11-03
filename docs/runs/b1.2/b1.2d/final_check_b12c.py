"""b1.2c's final check (owner, 2026-11-02: "run the final check of u250 when b1.2d starts"): its save of update 250 against b1.1 (widened), 160 ten-minute games on ten maps, seats swapped, exactly as b1.2c's
watcher plays a check (tools/run/watch.py games(), its settings from the save), into b1.2c's own watch/checks_prev.jsonl and watch.log. Started by b1.2d's start.ps1 on the check cores beside b1.2d.
    python docs/runs/b1.2/b1.2d/final_check_b12c.py"""
import os
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.dirname(HERE))))
K0 = os.path.join(ROOT, "data", "sim_runs", "duel_gru_b1_2c", "keep")
POL = os.path.join(K0, "policy_250.pt")
CTRL = os.path.join(K0, "control_b11.pt")
assert os.path.exists(POL) and os.path.exists(CTRL), (POL, CTRL)
os.environ.update(CTRL_PREV=CTRL, CTRL_PREV_LABEL="the start (b1.1)", PANEL_RUN="duel_gru_b1_2c")
sys.argv = [os.path.join(ROOT, "tools", "run", "watch.py"), "duel_gru_b1_2c"]
sys.path.insert(0, os.path.join(ROOT, "tools", "run"))
import watch as W                                            # (b1.2c's watcher's own code: its folder, its live.json, its labels)
W.say("final check of b1.2c's update 250 (started with b1.2d; CHECK_BATCH {})".format(W.CHECK_BATCH))
W.games(POL, 250, CTRL, "the start (b1.1)", W.live_ps())
W.say("final check of b1.2c done")

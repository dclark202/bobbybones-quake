"""b1.2c's dry run at full size, on the card, with nothing else running: its train.cmd for --minutes 25 into data/sim_runs/scratch_b12c_full, from b1.1 widened with its optimizer, anchors widened. For: does the optimizer load, does the card hold it, what an update costs, and the new tokens' first updates. It does not start a run.
    %USERPROFILE%\\anaconda3\\python.exe docs\\runs\\b1.2\\b1.2c\\dry_full.py"""
import json, os, re, shutil, subprocess, sys, time
HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.dirname(HERE))))
PY = sys.executable
SR = os.path.join(ROOT, "data", "sim_runs")
R0 = os.path.join(SR, "duel_gru_b1_1a", "keep")
RUN = "scratch_b12c_full"
D = os.path.join(SR, RUN)
BS = "\\"
MINS = sys.argv[1] if len(sys.argv) > 1 else "25"


def say(s):
    print(time.strftime("%H:%M:%S ") + s, flush=True)


assert not os.path.exists(D), D + " is there"
for s_ in ("snapshots", "keep", "watch"):
    os.makedirs(os.path.join(D, s_))
env = dict(os.environ, OPENBLAS_NUM_THREADS="1", PYTHONFAULTHANDLER="1")
II = os.path.join(ROOT, "tools", "items_init.py")
subprocess.check_call([PY, II, "widen", os.path.join(R0, "policy_b1.1.pt"), os.path.join(D, "policy.pt")], cwd=ROOT, env=env)
subprocess.check_call([PY, II, "widen", os.path.join(R0, "policy_b1.1.pt"), os.path.join(D, "snapshots", "anchor_b11.pt")], cwd=ROOT, env=env)
subprocess.check_call([PY, II, "widen", os.path.join(SR, "duel_gru_v0_6_0", "keep", "policy_end_v060.pt"), os.path.join(D, "snapshots", "anchor_v060_end.pt")], cwd=ROOT, env=env)
shutil.copy2(os.path.join(R0, "opt_b1.1.pt"), os.path.join(D, "opt.pt"))
shutil.copy2(os.path.join(SR, "duel_gru_b1_1a", "live_settings.env"), os.path.join(D, "live_settings.env"))
lv = json.load(open(os.path.join(SR, "duel_gru_b1_1a", "live.json"), encoding="utf-8"))
lv.update(INTENT_TEACH_W=1.0, VALUE_WARM=0, BRAIN_FADE=1.0, LEVEL_PULL=1.0, INTENT_HOLD=8.0, ITEM_RATE_HP=0.0025, ITEM_RATE_AR=0.002, COST_FIRE_W=1.0, COST_JERK_W=1.0, CONTACT_FREE=0.0)
json.dump(lv, open(os.path.join(D, "live.json"), "w", encoding="utf-8"))
t = open(os.path.join(HERE, "train.cmd"), encoding="ascii").read().replace("\r\n", "\n")
t = re.sub(r"--minutes \d+ --gamma", "--minutes {} --gamma".format(MINS), t)
for a, b in [("set ROOT=%~dp0.." + BS + ".." + BS + ".." + BS + "..", "set ROOT={}".format(ROOT)), ("call %~dp0aim2_env.cmd", "call " + os.path.join(HERE, "aim2_env.cmd")),
             ("--run duel_gru_b1_2c ", "--run " + RUN + " "), ("data" + BS + "sim_runs" + BS + "duel_gru_b1_2c.log", "data" + BS + "sim_runs" + BS + RUN + ".log")]:
    assert t.count(a) >= 1, a
    t = t.replace(a, b)
cmd = os.path.join(D, "dry.cmd")
open(cmd, "w", encoding="ascii", newline="").write(t.replace("\n", "\r\n"))
say("the dry trainer starts, {} minutes".format(MINS))
sys.exit(subprocess.call(["cmd.exe", "/c", cmd], cwd=ROOT, env=env))

"""2.0b's train.cmd (owner, 2026-11-09: "continue the build and start it when it's ready"; docs/runs/2.0/2.0b/CARD.md): 2.0a's command, every
setting as 2.0a ran, with --run duel_gru_2_0b, the length (--minutes as given), and 2.0b's own:
  set SPACE_TRUTH=1           the table's truth columns (the readout's lesson)
  set SPACE_IN=1              the inputs "b20b space" and "b20b targets" (59; in from zero weight), times the live SPACE_GATE
  set SPACE_GATE=0            the inputs' gate at the start (live; ramp_20b.py opens it)
  set EDGE_PAY=0              the pay by the place at the start (live; the ramp opens it); set, so that the simulators load the table
  set COVER_PAY=0             the item ground's pay: built, at 0 the whole run
  --space-read 1              the brain's readout "space" (its own layers and Adam; live SPACE_W)
  --gate-start <minute>       the minute 2.0a's end stands at: the two new tokens' attention gate opens from -12 to 0 over the command's 120
                              minutes counted from the run's start (2.0a's command has an older minute there, long past: the tokens would be open at once)
Nothing else changes in the command. The pay at the start is 2.0a's end's (live.json: DMG_REWARD 0.001, DMG_TAKEN_W 1.0, WIN_ADD 0.6). The
start network is 2.0a's end given 2.0b's parts with nothing of them in effect (tools/b20b_init.py add; start.ps1), with its optimizer.
    python docs/runs/2.0/2.0b/make_files.py <minutes>"""
import os
import re
import shutil
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
SRC = os.path.normpath(os.path.join(HERE, "..", "2.0a"))
t = open(os.path.join(SRC, "train.cmd"), encoding="ascii").read().replace("\r\n", "\n")
OLD = "--head2-fpg 0 --pass-odds 0.3 --pass-warm 0"
START = os.path.join(HERE, "..", "..", "..", "..", "data", "sim_runs", "duel_gru_2_0a", "keep", "policy_end_20a.pt")


def start_minute():
    """the minute 2.0a's end stands at (its save's own count): the new tokens' gate opens from there (--gate-start), not from the run's
    old --fade-start, which would open them at once"""
    import torch
    return float(torch.load(START, map_location="cpu", weights_only=False)["minutes"])


GS = "{:.2f}".format(start_minute())
NEW = "--head2-fpg 0 --space-read 1 --pass-odds 0.3 --pass-warm 0"
SETS = ("SPACE_TRUTH=1", "SPACE_IN=1", "SPACE_GATE=0", "EDGE_PAY=0", "COVER_PAY=0")


def sub(a, b):
    global t
    assert t.count(a) == 1, (a, t.count(a))
    t = t.replace(a, b)


MIN = sys.argv[1]
assert int(MIN) > 0
lines = t.split("\n")
cl_ = [i for i, x in enumerate(lines) if "train_duel_rnn.py" in x and not x.startswith("rem")]
assert len(cl_) == 1
c = lines[cl_[0]]
assert c.count(OLD) == 1 and len(re.findall(r"--minutes \d+ --gamma ", c)) == 1 and "--space-read" not in c
assert "--gate-from -12 " in c and "--gate-open 120 " in c and len(re.findall(r"--gate-start [0-9.]+ ", c)) == 1
c = re.sub(r"--gate-start [0-9.]+ ", "--gate-start " + GS + " ", c)
c = c.replace(OLD, NEW)
c = re.sub(r"--minutes \d+ --gamma ", "--minutes {} --gamma ".format(MIN), c)
lines[cl_[0]] = c
t = "\n".join(x if x.startswith("rem") else x.replace("duel_gru_2_0a", "duel_gru_2_0b") for x in lines)   # (the history lines stay as written)
sub("rem the repo root: this file lives in docs\\runs\\2.0\\2.0a\\",
    "rem ==== 2.0b (owner, 2026-11-09: \"continue the build and start it when it's ready\"; docs/runs/2.0/2.0b/CARD.md): the map's table "
    "(sim/space.py). Three parts opened one after the other by ramp_20b.py: the brain's readout 'space' from update 0 (--space-read 1, "
    "SPACE_TRUTH=1); the inputs against his belief (SPACE_IN=1, live SPACE_GATE 0 -> 1 over updates 30 to 60); the pay by the place (live "
    "EDGE_PAY 0 -> 0.0005 a damage-second over updates 60 to 100; COVER_PAY built, at 0). Everything else as 2.0a's end. From 2.0a's end "
    "(tools/b20b_init.py add) with its optimizer. 2.0a's command with: run duel_gru_2_0b; --minutes; --space-read 1; set " + ", ".join(SETS) +
    ". Made by make_files.py.\n"
    "rem the repo root: this file lives in docs\\runs\\2.0\\2.0b\\")
sub("\nset COMBAT=1\n", "\nset COMBAT=1\n" + "".join("set {}\n".format(s_) for s_ in SETS))
t = t.replace("docs\\runs\\2.0\\2.0a\\", "docs\\runs\\2.0\\2.0b\\")
cl_ = [x for x in t.split("\n") if "train_duel_rnn.py" in x and not x.startswith("rem")]
assert len(cl_) == 1 and "/affinity C03C3 " in cl_[0] and "--minutes {} --gamma ".format(MIN) in cl_[0]
assert "--pfsp" not in cl_[0] and "--opt-cold-ok" not in cl_[0] and "--max-updates" not in cl_[0] and "--wrule" not in cl_[0] and "--keep-freeze" not in cl_[0]
assert NEW + " " in cl_[0] and "--run duel_gru_2_0b " in cl_[0] and "--habit-p 0.3 " in cl_[0] and "--head2-wpg 1 " in cl_[0] and "--keep-g 0.975 " in cl_[0]
assert "--head2-l2 0.01" in cl_[0] and "--track 0.3 " in cl_[0] and "--dmg-reward 0.0055 " in cl_[0] and "--dmg-taken-w 1.0 " in cl_[0]
assert "--opt-small-items 1 " in cl_[0] and "--gamma 0.999 " in cl_[0]
for s_ in ("SHOT_COST=0", "BLIND_FIRE_W=0", "BLIND_RL_DMG=0", "WEAPON_OWN=1", "INTENT_SWITCH=0", "COMBAT=1", "BRAIN_READ=1", "ITEM_BELIEF=1",
           "WIN_JUDGE=%ROOT%\\data\\sim_runs\\judge\\judge_v060_wpn.npz", "WIN_SHADOW=1", "WIN_END=1", "PAY_SPLIT=1", "DMG_ENEMY_ONLY=1") + SETS:
    assert t.count("\nset {}\n".format(s_)) == 1, s_
assert "2_0a" not in "\n".join(x for x in t.split("\n") if not x.startswith("rem")) and "2.0a" not in "\n".join(x for x in t.split("\n") if not x.startswith("rem"))
open(os.path.join(HERE, "train.cmd"), "w", encoding="ascii", newline="").write(t.replace("\n", "\r\n"))
shutil.copy2(os.path.join(SRC, "aim2_env.cmd"), os.path.join(HERE, "aim2_env.cmd"))
print("written")

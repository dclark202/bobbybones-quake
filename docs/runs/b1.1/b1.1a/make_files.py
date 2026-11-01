"""b1.1a's train.cmd (owner, 2026-10-31), made from b1.0a's: --run duel_gru_b1_1a (and its log), --minutes 885, --brain-fade 1 (the brain's gate moves; live BRAIN_FADE).
    python docs/runs/b1.1/b1.1a/make_files.py"""
import os
import shutil

HERE = os.path.dirname(os.path.abspath(__file__))
SRC = os.path.join(HERE, "..", "..", "b1.0", "b1.0a")
t = open(os.path.join(SRC, "train.cmd"), encoding="ascii").read().replace("\r\n", "\n")


def sub(a, b):
    global t
    assert t.count(a) == 1, (a, t.count(a))
    t = t.replace(a, b)


t = t.replace("duel_gru_b1_0a", "duel_gru_b1_1a")
sub("--run duel_gru_b1_1a --resume --minutes 1320 --gamma", "--run duel_gru_b1_1a --brain-fade 1 --resume --minutes 885 --gamma")
sub("set ROOT=%~dp0..\\..\\..\n", "set ROOT=%~dp0..\\..\\..\\..\n")
sub("rem the repo root: this file lives in docs\\runs\\b1.0a\\",
    "rem ==== b1.1a (owner, 2026-10-31; docs/runs/b1.1/b1.1a/CARD.md): from b1.0a's end, the brain's old belief, the pull toward level and the target lock faded out (live BRAIN_FADE, LEVEL_PULL, INTENT_HOLD:\n"
    "rem  ramp_b11.py). b1.0a's command with: run duel_gru_b1_1a; --minutes 885; --brain-fade 1. Made by make_files.py.\n"
    "rem the repo root: this file lives in docs\\runs\\b1.1\\b1.1a\\")
open(os.path.join(HERE, "train.cmd"), "w", encoding="ascii", newline="").write(t.replace("\n", "\r\n"))
shutil.copy2(os.path.join(SRC, "aim2_env.cmd"), os.path.join(HERE, "aim2_env.cmd"))
print("written")

"""b1.0a's train.cmd (owner, 2026-10-31), made from v0.6.0's: --run duel_gru_b1_0a (and its log), --minutes 1320, the readouts' warm-ups over (WV_START,
CTL_START at v0.6.0's start minute, as v0.6.1), the judge (WIN_JUDGE) and the game-end fix (WIN_END). WIN_ADD itself is live (ramp_win.py).
    python docs/runs/b1.0a/make_files.py"""
import os
import shutil

HERE = os.path.dirname(os.path.abspath(__file__))
SRC = os.path.join(HERE, "..", "v0.6.0")
t = open(os.path.join(SRC, "train.cmd"), encoding="ascii").read().replace("\r\n", "\n")


def sub(a, b):
    global t
    assert t.count(a) == 1, (a, t.count(a))
    t = t.replace(a, b)


t = t.replace("duel_gru_v0_6_0", "duel_gru_b1_0a")
sub("--minutes 510 --gamma", "--minutes 1320 --gamma")
sub("C:\\Users\\dacla\\anaconda3\\python.exe", "%USERPROFILE%\\anaconda3\\python.exe")
sub("rem the repo root: this file lives in docs\\runs\\v0.6.0\\",
    "rem ==== b1.0a (owner, 2026-10-31; docs/runs/b1.0a/CARD.md): from v0.6.0's end, win chance pay added on top of the table (live WIN_ADD, ramp_win.py), the table\n"
    "rem  unchanged. v0.6.0's command with: run duel_gru_b1_0a; --minutes 1320; WV_START, CTL_START at v0.6.0's start minute; WIN_JUDGE; WIN_END. Made by make_files.py.\n"
    "rem the repo root: this file lives in docs\\runs\\b1.0a\\")
sub('if "%WV_START%"=="" set WV_START=-1', 'if "%WV_START%"=="" set WV_START=19593.9')
sub('if "%CTL_START%"=="" set CTL_START=-1', 'if "%CTL_START%"=="" set CTL_START=19593.9')
sub('if "%RF_START%"=="" set RF_START=18411.038983547685',
    "rem the judge, frozen, fitted on v0.6.0's own games, the rocket launcher and the rail at the lightning gun's worth by hand; a game's result paid on its last frame\n"
    "set WIN_JUDGE=%ROOT%\\data\\sim_runs\\judge\\judge_v060_wpn.npz\n"
    "set WIN_END=1\n"
    'if "%RF_START%"=="" set RF_START=18411.038983547685')
open(os.path.join(HERE, "train.cmd"), "w", encoding="ascii", newline="").write(t.replace("\n", "\r\n"))
shutil.copy2(os.path.join(SRC, "aim2_env.cmd"), os.path.join(HERE, "aim2_env.cmd"))
print("written")

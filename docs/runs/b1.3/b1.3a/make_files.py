"""b1.3a's train.cmd (owner, 2026-11-01), from b1.2c's: --run duel_gru_b1_3a; --minutes as given; the head, shut, on combat plus win pay, as the only learner of his target (--head2-sole 1). The table and the dials come from b1.2c's end in live.json (start.ps1).
    python docs/runs/b1.3/b1.3a/make_files.py <minutes>"""
import os
import shutil
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
t = open(os.path.join(HERE, "..", "..", "b1.2", "b1.2c", "train.cmd"), encoding="ascii").read().replace("\r\n", "\n")


def sub(a, b):
    global t
    assert t.count(a) == 1, (a, t.count(a))
    t = t.replace(a, b)


MIN = sys.argv[1]
t = t.replace("duel_gru_b1_2c", "duel_gru_b1_3a")
sub("--minutes 990 --gamma", "--minutes {} --gamma".format(MIN))
sub(" %LEARN% >> ", " --head2 1 --head2-ctrl-src belief --head2-open 1 --head2-cap 0 --head2-gate 0 --head2-start %H2_START% --head2-pay combat_win --head2-sole 1 %LEARN% >> ")
sub('if "%RF_START%"=="" set RF_START=18411.038983547685', 'if "%H2_START%"=="" set H2_START=-1\nif "%RF_START%"=="" set RF_START=18411.038983547685')
sub("rem the repo root: this file lives in docs\\runs\\b1.2\\b1.2c\\",
    "rem ==== b1.3a (owner, 2026-11-01; docs/runs/b1.3/b1.3a/CARD.md): the strategy head opens, the only learner of his target. b1.2c's command with: run duel_gru_b1_3a; --minutes; the head's arguments with --head2-sole 1. Made by make_files.py.\n"
    "rem the repo root: this file lives in docs\\runs\\b1.3\\b1.3a\\")
open(os.path.join(HERE, "train.cmd"), "w", encoding="ascii", newline="").write(t.replace("\n", "\r\n"))
shutil.copy2(os.path.join(HERE, "..", "..", "b1.2", "b1.2c", "aim2_env.cmd"), os.path.join(HERE, "aim2_env.cmd"))
print("written")

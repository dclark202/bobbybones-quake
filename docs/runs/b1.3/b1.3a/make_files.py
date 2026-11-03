"""b1.3a's train.cmd (owner, 2026-11-01; rebuilt on b1.2d's command 2026-11-02, owner: "prepare this"): b1.2d's command with --run duel_gru_b1_3a; --minutes as given;
the head, shut in play all run, learning to copy his target choice (--head2-copy 1; owner 2026-11-02: "we bring it in in b1.3 to learn how to copy the rules that exist"), its value on his whole pay; no pay-driven lesson for it (--head2-pg 0). b1.2d's pay table and its faded dials come from b1.2d's end in live.json (start.ps1).
The trainer on the 8 performance cores (0xC03C3), as b1.2d.
    python docs/runs/b1.3/b1.3a/make_files.py <minutes>"""
import os
import re
import shutil
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
SRC = os.path.join(HERE, "..", "..", "b1.2", "b1.2d")
t = open(os.path.join(SRC, "train.cmd"), encoding="ascii").read().replace("\r\n", "\n")


def sub(a, b):
    global t
    assert t.count(a) == 1, (a, t.count(a))
    t = t.replace(a, b)


MIN = sys.argv[1]
t = t.replace("duel_gru_b1_2d", "duel_gru_b1_3a")
assert len(re.findall(r"--minutes \d+ --gamma ", t)) == 1
t = re.sub(r"--minutes \d+ --gamma ", "--minutes {} --gamma ".format(MIN), t)
sub(" %LEARN% >> ", " --head2 1 --head2-ctrl-src belief --head2-open 0 --head2-cap 0 --head2-gate 0 --head2-start %H2_START% --head2-pay all --head2-pg 0 --head2-copy 1 %LEARN% >> ")
sub('if "%RF_START%"=="" set RF_START=18411.038983547685', 'if "%H2_START%"=="" set H2_START=-1\nif "%RF_START%"=="" set RF_START=18411.038983547685')
sub("rem the repo root: this file lives in docs\\runs\\b1.2\\b1.2d\\",
    "rem ==== b1.3a (owner, 2026-11-01; docs/runs/b1.3/b1.3a/CARD.md): the strategy head in, shut, learning to copy his target choice (the rules as he plays them). b1.2d's command with: run duel_gru_b1_3a; --minutes; the head's arguments with --head2-copy 1, --head2-pg 0, --head2-pay all. Made by make_files.py.\n"
    "rem the repo root: this file lives in docs\\runs\\b1.3\\b1.3a\\")
assert "/affinity C03C3 " in t and "--minutes {} --gamma ".format(MIN) in t
open(os.path.join(HERE, "train.cmd"), "w", encoding="ascii", newline="").write(t.replace("\n", "\r\n"))
shutil.copy2(os.path.join(SRC, "aim2_env.cmd"), os.path.join(HERE, "aim2_env.cmd"))
print("written")

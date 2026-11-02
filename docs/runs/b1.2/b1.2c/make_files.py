"""b1.2c's train.cmd (owner, 2026-11-01), from b1.2b's: --run duel_gru_b1_2c; --minutes as given; SM_ITEMS=1; the new tokens' gate opens from -12 over 120 minutes from the start. Then ramp_b12b.py's steps, from the same file.
    python docs/runs/b1.2/b1.2c/make_files.py <minutes> [gate start, the minutes of the network: default b1.1's]"""
import os
import shutil
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
t = open(os.path.join(HERE, "..", "b1.2b", "train.cmd"), encoding="ascii").read().replace("\r\n", "\n")


def sub(a, b):
    global t
    assert t.count(a) == 1, (a, t.count(a))
    t = t.replace(a, b)


MIN = sys.argv[1]
G0 = sys.argv[2] if len(sys.argv) > 2 else "21009.47"
t = t.replace("duel_gru_b1_2b", "duel_gru_b1_2c")
sub("--minutes 1185 --gamma", "--minutes {} --gamma".format(MIN))
sub("--gate-open 480", "--gate-open 120")
sub(" %LEARN% >> ", " --opt-small-items 1 %LEARN% >> ")
sub("--gate-start 14397.514", "--gate-start {}".format(G0))
sub("set ITEM_RATE_AR=0.002\n", "set ITEM_RATE_AR=0.002\nrem (b1.2c) every small health and armor item as an input: what it is, where, the way, its state by what he knows\nset SM_ITEMS=1\n")
sub("rem the repo root: this file lives in docs\\runs\\b1.2\\b1.2b\\",
    "rem ==== b1.2c (owner, 2026-11-01; docs/runs/b1.2/b1.2c/CARD.md): b1.2b's plan, with every small health and armor item as an input, from the start. b1.2b's command with: run duel_gru_b1_2c; --minutes; SM_ITEMS=1; --gate-open 120 from the start. Made by make_files.py.\n"
    "rem the repo root: this file lives in docs\\runs\\b1.2\\b1.2c\\")
open(os.path.join(HERE, "train.cmd"), "w", encoding="ascii", newline="").write(t.replace("\n", "\r\n"))
shutil.copy2(os.path.join(HERE, "..", "b1.2b", "aim2_env.cmd"), os.path.join(HERE, "aim2_env.cmd"))
print("written")

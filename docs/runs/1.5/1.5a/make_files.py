"""1.5a's train.cmd (owner, 2026-11-04 evening; docs/runs/1.5/1.5a/CARD.md): 1.3b's command, every rule and teacher as 1.3b had them, with
--run duel_gru_1_5a, --minutes as given, and only the head's say in his weapon choice added: the weapon key's credit on the head's clock
(--head2-wpg 0 at the start; live H2_WPG opened by ramp_15a.py over updates 10 to 90) and the league seats' weapon habits on 30% of their
lives (--habit-p 0.3, live HABIT_P; +2; a third each the pros' hand, rail, rockets). Out at update 0 (owner, 11-04 evening): the switch cost
(INTENT_SWITCH=0), the weapon override (WEAPON_OWN=1), the blind-fire cost (BLIND_FIRE_W=0), as 1.4b and 1.4c had them. The head's weapon scores come with the start network
(tools/weapon_init.py add on 1.3b's end: at zero, wadd 1). The L2 (--head2-l2 0.01) is 1.3b's and now reaches the weapon key's two parts
too. The trainer on the 8 performance cores (0xC03C3), as 1.3b.
    python docs/runs/1.5/1.5a/make_files.py <minutes>"""
import os
import re
import shutil
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
SRC = os.path.join(HERE, "..", "..", "b1.3", "1.3b")
t = open(os.path.join(SRC, "train.cmd"), encoding="ascii").read().replace("\r\n", "\n")


def sub(a, b):
    global t
    assert t.count(a) == 1, (a, t.count(a))
    t = t.replace(a, b)


MIN = sys.argv[1]
t = t.replace("duel_gru_1_3b", "duel_gru_1_5a")
assert len(re.findall(r"--minutes \d+ --gamma ", t)) == 1
t = re.sub(r"--minutes \d+ --gamma ", "--minutes {} --gamma ".format(MIN), t)
sub(" --head2-l2 0.01 %LEARN% >> ", " --head2-l2 0.01 --head2-wpg 0 --habit-p 0.3 --habit-push 2 --habit-kinds pro:1,rg:1,rl:1 %LEARN% >> ")
sub("set WEAPON_FREE=1\n", "set WEAPON_FREE=1\n"                                    # (owner, 11-04 evening: "they should come out at 0")
    "rem (1.5a, owner 2026-11-04: out at update 0, as 1.4b and 1.4c had them) a weapon he holds may be chosen; taking the one he chose still ends the choice\n"
    "set WEAPON_OWN=1\n"
    "rem (1.5a) no cost for a change of target\n"
    "set INTENT_SWITCH=0\n"
    "rem (1.5a) no blind-fire cost\n"
    "set BLIND_FIRE_W=0\n")
sub("rem the repo root: this file lives in docs\\runs\\b1.3\\1.3b\\",
    "rem ==== 1.5a (owner, 2026-11-04 evening; docs/runs/1.5/1.5a/CARD.md): the head contributes to his weapon choice, from 1.3b's end, "
    "nothing faded. 1.3b's command with: run duel_gru_1_5a; --minutes; --head2-wpg 0 (live H2_WPG, ramp_15a.py: 0 -> 1 over updates 10 "
    "to 90); --habit-p 0.3 --habit-push 2 --habit-kinds pro:1,rg:1,rl:1 (live HABIT_P). The start: 1.3b's end given the head's weapon part "
    "(tools/weapon_init.py add). Made by make_files.py.\n"
    "rem the repo root: this file lives in docs\\runs\\1.5\\1.5a\\")
cl_ = [x for x in t.split("\n") if "train_duel_rnn.py" in x and not x.startswith("rem")]
assert len(cl_) == 1 and "/affinity C03C3 " in cl_[0] and "--minutes {} --gamma ".format(MIN) in cl_[0]
assert "--pfsp" not in cl_[0] and "--keep-g" not in cl_[0] and "--head2-l2 0.01" in cl_[0]
assert all(t.count("\nset {}\n".format(s_)) == 1 for s_ in ("WEAPON_OWN=1", "INTENT_SWITCH=0", "BLIND_FIRE_W=0"))
open(os.path.join(HERE, "train.cmd"), "w", encoding="ascii", newline="").write(t.replace("\n", "\r\n"))
shutil.copy2(os.path.join(SRC, "aim2_env.cmd"), os.path.join(HERE, "aim2_env.cmd"))
print("written")

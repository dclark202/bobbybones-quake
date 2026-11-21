"""1.7b's train.cmd (owner, 2026-11-06 evening: "let's start 1.7b now"; "Just keep 1.7b as we agreed"; docs/runs/1.7/1.7b/CARD.md): 1.7a's
command, every setting as 1.7a ran, with --run duel_gru_1_7b, the length (owner, 11-06 evening: about 150 updates, "That's fine":
--max-updates 150, and --minutes as given, a cap above it), and:
  --keep-g 1                  the keep choice at full share from the start (1.7a's ramp had it at 1 by update 90)
  --fight-odds 1 --fight-warm 0   the brain's fight odds lesson from update 0 (sim/fightodds.py; its own Adam)
  --head2-opg 0 --ord-kl 0     the order's share of the head's term and its KL at 0 at the start (live H2_OPG, ORD_KL: ramp_17b.py)
  FIGHT_TRUTH=1               the fight odds' labels in the simulators
  OUT_LIVE=1.5                break off reached by living through it (1.5 s without seeing the enemy and no damage either way)
The order's share, its token, the pointer's adds, the fire push stay at zero as 1.7a's start (--cmb-g 0 --padd 0 --fadd 0 --head2-fpg 0;
live CMB_G and ORD_GATE opened by ramp_17b.py; PADD, FADD, H2_FPG held at 0: the card's "out"). The damage pay's taken weight: live
DMG_TAKEN_W 0.8 -> 1.0 by ramp_17b.py. The start network is 1.7a's update 90 given 1.7b's parts at zero effect (tools/b17b_init.py add).
--opt-small-items 1 carries the optimizer's state over the widened inputs (the encoder's columns, the timers' token's marks and first
layer); the head's inp by the file's head2_inp_map. No cost for firing at all (SHOT_COST=0, as 1.7a). The trainer on the 8 performance
cores (0xC03C3), as 1.7a.
    python docs/runs/1.7/1.7b/make_files.py <minutes>"""
import os
import re
import shutil
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
SRC = os.path.join(HERE, "..", "1.7a")
t = open(os.path.join(SRC, "train.cmd"), encoding="ascii").read().replace("\r\n", "\n")
OLD = "--keep-g 0 --cmb-g 0 --padd 0 --fadd 0 --head2-fpg 0 --pass-odds 0.3 --pass-warm 0"
NEW = "--keep-g 1 --cmb-g 0 --padd 0 --fadd 0 --head2-fpg 0 --pass-odds 0.3 --pass-warm 0 --fight-odds 1 --fight-warm 0 --head2-opg 0 --ord-kl 0"


def sub(a, b):
    global t
    assert t.count(a) == 1, (a, t.count(a))
    t = t.replace(a, b)


MIN = sys.argv[1]
assert int(MIN) > 0
MAXU = 150                                                   # (owner, 11-06 evening: "about 150 updates (about 14 h)": "That's fine")
lines = t.split("\n")
cl_ = [i for i, x in enumerate(lines) if "train_duel_rnn.py" in x and not x.startswith("rem")]
assert len(cl_) == 1
c = lines[cl_[0]]
assert c.count(OLD) == 1 and len(re.findall(r"--minutes \d+ --gamma ", c)) == 1
c = c.replace(OLD, NEW)
c = re.sub(r"--minutes \d+ --gamma ", "--minutes {} --max-updates {} --gamma ".format(MIN, MAXU), c)
lines[cl_[0]] = c
t = "\n".join(x if x.startswith("rem") else x.replace("duel_gru_1_7a", "duel_gru_1_7b") for x in lines)   # (the history lines stay as written)
sub("set COMBAT=1\n", "set COMBAT=1\n"
    "rem (1.7b, docs/runs/1.7/1.7b/CARD.md) the fight odds' labels (sim/duel_env.py FIGHT_TRUTH) and break off reached by living through it\n"
    "set FIGHT_TRUTH=1\n"
    "set OUT_LIVE=1.5\n")
sub("rem the repo root: this file lives in docs\\runs\\1.7\\1.7a\\",
    "rem ==== 1.7b (owner, 2026-11-06 evening: \"let's start 1.7b now\"; docs/runs/1.7/1.7b/CARD.md): the combat order again, rebuilt around "
    "Cypher's fight decision: the brain's fight odds (the head reads them), break off reached by living through it, the hands before the "
    "head (the order asked at the start's rates with the head's order frozen, then learnt), a KL to the pros' order through the run; the "
    "damage pay zero-sum and the yellow armors' timers first; the pointer's adds and the fire push out. From 1.7a's update 90 with its "
    "optimizer, given 1.7b's parts at zero effect (tools/b17b_init.py add). 1.7a's command with: run duel_gru_1_7b; --minutes (the "
    "owner's length); " + NEW + " (live CMB_G, ORD_GATE, H2_OPG, ORD_KL, DMG_TAKEN_W: ramp_17b.py); FIGHT_TRUTH=1, OUT_LIVE=1.5. Made by "
    "make_files.py.\n"
    "rem the repo root: this file lives in docs\\runs\\1.7\\1.7b\\")
t = t.replace("docs\\runs\\1.7\\1.7a\\", "docs\\runs\\1.7\\1.7b\\")
cl_ = [x for x in t.split("\n") if "train_duel_rnn.py" in x and not x.startswith("rem")]
assert len(cl_) == 1 and "/affinity C03C3 " in cl_[0] and "--minutes {} --max-updates {} --gamma ".format(MIN, MAXU) in cl_[0]
assert "--pfsp" not in cl_[0] and "--opt-cold-ok" not in cl_[0]
assert NEW + " " in cl_[0] and "--opt-small-items 1 " in cl_[0] and "--run duel_gru_1_7b " in cl_[0]
assert "--habit-p 0.3" in cl_[0] and "--head2-l2 0.01" in cl_[0] and "--head2-wpg 1 " in cl_[0] and "--track 0.3 " in cl_[0]
for s_ in ("SHOT_COST=0", "BLIND_FIRE_W=0", "BLIND_RL_DMG=0", "WEAPON_OWN=1", "INTENT_SWITCH=0", "COMBAT=1", "BRAIN_READ=1", "FIGHT_TRUTH=1",
           "OUT_LIVE=1.5", "ITEM_BELIEF=1"):
    assert t.count("\nset {}\n".format(s_)) == 1, s_
assert "1.7a" not in "\n".join(x for x in t.split("\n") if not x.startswith("rem"))
open(os.path.join(HERE, "train.cmd"), "w", encoding="ascii", newline="").write(t.replace("\n", "\r\n"))
shutil.copy2(os.path.join(SRC, "aim2_env.cmd"), os.path.join(HERE, "aim2_env.cmd"))
print("written")

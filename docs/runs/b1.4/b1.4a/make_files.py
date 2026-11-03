"""b1.3a's train.cmd (owner, 2026-11-01), from b1.2a's: --run duel_gru_b1_3a; the head open from the start; DMG_ENEMY_ONLY=1. CONTACT_FREE and DMG_TAKEN_W start at their shut values in live.json (start.ps1).
    python docs/runs/b1.3/b1.3a/make_files.py"""
import os
import shutil

HERE = os.path.dirname(os.path.abspath(__file__))
t = open(os.path.join(HERE, "..", "..", "b1.2", "b1.2a", "train.cmd"), encoding="ascii").read().replace("\r\n", "\n")


def sub(a, b):
    global t
    assert t.count(a) == 1, (a, t.count(a))
    t = t.replace(a, b)


t = t.replace("duel_gru_b1_2a", "duel_gru_b1_3a")
sub("--head2-cap 0 --head2-gate 0 ", "--head2-cap 1 --head2-gate 1 ")
sub("set GONE_BELIEF=1\n", "set GONE_BELIEF=1\nrem (b1.3a) DMG_TAKEN_W on an enemy's damage only; his own splash, falls and hazards at full cost\nset DMG_ENEMY_ONLY=1\n")
sub("rem the repo root: this file lives in docs\\runs\\b1.2\\b1.2a\\",
    "rem ==== b1.3a (owner, 2026-11-01; docs/runs/b1.3/b1.3a/CARD.md): free target choice in contact, damage taken to 0.65 on an enemy's damage, the item rule out, by live dials (ramp_b13.py). b1.2a's command with: run duel_gru_b1_3a;\n"
    "rem  the head open from the start; DMG_ENEMY_ONLY=1. Made by make_files.py.\n"
    "rem the repo root: this file lives in docs\\runs\\b1.3\\b1.3a\\")
open(os.path.join(HERE, "train.cmd"), "w", encoding="ascii", newline="").write(t.replace("\n", "\r\n"))
shutil.copy2(os.path.join(HERE, "..", "..", "b1.2", "b1.2a", "aim2_env.cmd"), os.path.join(HERE, "aim2_env.cmd"))
print("written")

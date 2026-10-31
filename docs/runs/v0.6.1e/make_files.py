"""v0.6.1e's files (owner, 2026-10-31: from v0.6.1's save of update 90, the original pay table to half and win chance to half over the first 40 updates,
then the pull and the brain faded together, 12 h), made from v0.6.1d's. train.cmd: --run duel_gru_v0_6_1e (and its log), --minutes 720.
start.ps1, smoke.py: the names, live.json at the start WIN_W 0.5, FADE_V 0.125, WIN_GAIN 0.33, the settings check against d's command. ramp_fades.py is written by hand.
    python docs/runs/v0.6.1e/make_files.py"""
import os
import shutil

HERE = os.path.dirname(os.path.abspath(__file__))
SRC = os.path.join(HERE, "..", "v0.6.1d")
BS = "\\"


def read(name):
    return open(os.path.join(SRC, name), encoding="ascii").read().replace("\r\n", "\n")


def sub(t, a, b):
    assert t.count(a) == 1, (a, t.count(a))
    return t.replace(a, b)


def names(t):
    return t.replace("duel_gru_v0_6_1d", "duel_gru_v0_6_1e").replace("v061d", "v061e").replace("v0.6.1d", "v0.6.1e")


# train.cmd
t = names(read("train.cmd"))
t = sub(t, "--minutes 915 --gamma", "--minutes 720 --gamma")
t = t.replace("the blend held (live.json:", "the pay to half and half over 40 updates, ramp_fades.py (live.json at the start WIN_W 0.5, FADE_V 0.125, WIN_GAIN 0.33; was:")
open(os.path.join(HERE, "train.cmd"), "w", encoding="ascii", newline="").write(t.replace("\n", "\r\n"))

# start.ps1
t = read("start.ps1")
t = sub(t, 'Join-Path $ROOT "docs' + BS + 'runs' + BS + 'v0.6.1c' + BS + 'train.cmd"', 'Join-Path $ROOT "docs' + BS + 'runs' + BS + 'v0.6.1D_REF' + BS + 'train.cmd"')
t = sub(t, '"--allow=--run,--minutes,--adv-pay-ref"', '"--allow=--run,--minutes"')
HEAD = ("# v0.6.1e's start (owner, 2026-10-31; docs/runs/v0.6.1e/CARD.md): v0.6.1's save of update 90, the pay to half the table and half win chance over\n"
        "# 40 updates (WIN_W 0.5, FADE_V 0.125 -> 0.5, WIN_GAIN 0.33 -> 0.87), the rescale at 10, then the pull and the brain's old belief\n"
        "# faded out together. Refuses unless: no trainer runs; the code and the judge are there; the settings check passes against v0.6.1d's\n"
        "# command (only --run, --minutes differ); smoke.log ends ALL PASSED; the run folder is new. Nothing stops the run.\n"
        "# Usage (PowerShell):  powershell -ExecutionPolicy Bypass -File docs" + BS + "runs" + BS + "v0.6.1e" + BS + "start.ps1\n")
t = HEAD + t[t.index("$ErrorActionPreference"):]
t = names(t).replace("v0.6.1D_REF", "v0.6.1d")
t = sub(t, "d.update(WIN_W=0.8, FADE_V=0.5, WIN_GAIN=0.35,", "d.update(WIN_W=0.5, FADE_V=0.125, WIN_GAIN=0.33,")
t = t.replace("policy_110.pt", "policy_90.pt").replace("anchor_v061_u110", "anchor_v061_u90").replace("save of update 110 (the start)", "save of update 90 (the start)")
open(os.path.join(HERE, "start.ps1"), "w", encoding="ascii", newline="").write(t)

# smoke.py
t = names(read("smoke.py"))
t = sub(t, "W, V, G = 0.8, 0.5, 0.35", "W, V, G = 0.5, 0.5, 0.87")
t = sub(t, "lv.update(WIN_W=W, FADE_V=V, WIN_GAIN=G,", "lv.update(WIN_W=W, FADE_V=0.125, WIN_GAIN=0.33,")
t = sub(t, '"--min-s", "0", "--sleep", "5"', '"--pay-steps", "5", "--pay-every", "1", "--poll", "5", "--min-s", "0", "--sleep", "5"')
t = t.replace("policy_110.pt", "policy_90.pt").replace("anchor_v061_u110", "anchor_v061_u90").replace("save of update 110", "save of update 90")
t = sub(t, "scratch_v061d_smoke", "scratch_v061e_smoke") if "scratch_v061d_smoke" in t else t
t = sub(t, '("--minutes 915 --gamma", "--minutes 12 --gamma")', '("--minutes 720 --gamma", "--minutes 12 --gamma")')
t = sub(t, "'WIN_W': 0.8", "'WIN_W': 0.5")
t = sub(t, "'WIN_GAIN': 0.35", "'WIN_GAIN': 0.87")
open(os.path.join(HERE, "smoke.py"), "w", encoding="ascii", newline="").write(t)

shutil.copy2(os.path.join(SRC, "aim2_env.cmd"), os.path.join(HERE, "aim2_env.cmd"))
print("written")

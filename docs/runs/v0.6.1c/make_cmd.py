"""v0.6.1c's command (owner, 2026-10-30: from v0.6.1's save of update 250; the pull toward level and the old belief in the brain
faded out together over the first ~5-6 h; 12 h; the advantages rescaled to keep the entropy down), made from v0.6.1b's own
command. Every change: --run duel_gru_v0_6_1c (and its log); the advantages' rescaling --adv-pay-ref 8.5 (v0.6.0's pay size a
player-minute in games, 8.4-8.8) --adv-pay-tau 5 --adv-pay-max 4 --adv-pay-warm 30 (opened over 30 min; owner: "Open the rescaling faster"). Kept from v0.6.1b:
--brain-fade 1 (live BRAIN_FADE, from 0), WIN_END=1, WIN_JUDGE judge_v061_wpn.npz, --minutes 720.
    python docs/runs/v0.6.1c/make_cmd.py [out]   (default: docs/runs/v0.6.1c/train.cmd)"""
import os
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
src = open(os.path.join(HERE, "..", "v0.6.1b", "train.cmd"), encoding="ascii").read().replace("\r\n", "\n")
out = sys.argv[1] if len(sys.argv) > 1 else os.path.join(HERE, "train.cmd")
BS = "\\"


def sub(t, a, b):
    assert t.count(a) == 1, (a, t.count(a))
    return t.replace(a, b)


REM = ("rem ==== v0.6.1c (owner, 2026-10-30; docs/runs/v0.6.1c/CARD.md): back to v0.6.1's save of update 250 (the win pay faded in, the\n"
       "rem  pull toward level still on), v0.6.1b's command with: run duel_gru_v0_6_1c; the advantages rescaled (--adv-pay-ref 8.5: the\n"
       "rem  pay's pull on his choices against the entropy bonus kept as with v0.6.0's pay; opened over 30 min; live ADV_PAY_REF). Live: LEVEL_PULL\n"
       "rem  0.95 -> 1 and BRAIN_FADE 0 -> 1 together, a step right after each save (tools/run/ramp_live.py --also). Made by make_cmd.py.\n")
t = src
t = sub(t, "rem the repo root: this file lives in docs" + BS + "runs" + BS + "v0.6.1b" + BS + "\n",
        REM + "rem the repo root: this file lives in docs" + BS + "runs" + BS + "v0.6.1c" + BS + "\n")
t = sub(t, "--run duel_gru_v0_6_1b ", "--run duel_gru_v0_6_1c ")
LOG_B = "data" + BS + "sim_runs" + BS + "duel_gru_v0_6_1b.log"
LOG_C = "data" + BS + "sim_runs" + BS + "duel_gru_v0_6_1c.log"
t = sub(t, " %LEARN% >> " + LOG_B + " 2>&1",
        " --adv-pay-ref 8.5 --adv-pay-tau 5 --adv-pay-max 4 --adv-pay-warm 30 %LEARN% >> " + LOG_C + " 2>&1")
t = sub(t, "echo exit %ERRORLEVEL% >> " + LOG_B, "echo exit %ERRORLEVEL% >> " + LOG_C)
open(out, "w", encoding="ascii", newline="").write(t.replace("\n", "\r\n"))
print("written", out)

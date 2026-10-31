"""v0.6.1d's files (owner, 2026-10-30: the blend held, "ideally the PAY for the original item rules and the win chance should be
roughly equal"), made from v0.6.1c's. train.cmd: --run duel_gru_v0_6_1d (and its log), --adv-pay-ref 10. start.ps1: the start is
v0.6.1's save of update 110; live.json holds WIN_W 0.8, FADE_V 0.5, WIN_GAIN 0.35, LEVEL_PULL 0.95, BRAIN_FADE 0; ramp_fades.py fades the pull and the brain together; the checks
against that save and v0.6.0's end; the settings check against v0.6.1c's command; refuses until smoke.log ends ALL PASSED.
    python docs/runs/v0.6.1d/make_files.py"""
import os
import shutil

HERE = os.path.dirname(os.path.abspath(__file__))
SRC = os.path.join(HERE, "..", "v0.6.1c")
BS = "\\"


def read(name):
    return open(os.path.join(SRC, name), encoding="ascii").read().replace("\r\n", "\n")


def sub(t, a, b):
    assert t.count(a) == 1, (a, t.count(a))
    return t.replace(a, b)


# train.cmd
t = read("train.cmd")
REM = ("rem ==== v0.6.1d (owner, 2026-10-30; docs/runs/v0.6.1d/CARD.md): from v0.6.1's save of update 110, the blend held (live.json: WIN_W 0.8,\n"
       "rem  FADE_V 0.5, WIN_GAIN 0.35), the old pay and the win pay about equal, the pull and the brain's old belief faded together live (ramp_fades.py). v0.6.1c's command\n"
       "rem  with: run duel_gru_v0_6_1d; --adv-pay-ref 10. Made by make_files.py.\n")
t = sub(t, "rem the repo root: this file lives in docs" + BS + "runs" + BS + "v0.6.1c" + BS + "\n",
        REM + "rem the repo root: this file lives in docs" + BS + "runs" + BS + "v0.6.1d" + BS + "\n")
t = sub(t, "--run duel_gru_v0_6_1c ", "--run duel_gru_v0_6_1d ")
t = sub(t, "--minutes 720 --gamma", "--minutes 915 --gamma")  # (owner: until 9am 10-31, from a start ~17:45)
t = sub(t, "--adv-pay-ref 8.5 ", "--adv-pay-ref 10 ")
LOG_C = "data" + BS + "sim_runs" + BS + "duel_gru_v0_6_1c.log"
LOG_D = "data" + BS + "sim_runs" + BS + "duel_gru_v0_6_1d.log"
t = sub(t, " >> " + LOG_C + " 2>&1", " >> " + LOG_D + " 2>&1")
t = sub(t, "echo exit %ERRORLEVEL% >> " + LOG_C, "echo exit %ERRORLEVEL% >> " + LOG_D)
open(os.path.join(HERE, "train.cmd"), "w", encoding="ascii", newline="").write(t.replace("\n", "\r\n"))

# start.ps1
t = read("start.ps1")
HEAD = ("# v0.6.1d's start (owner, 2026-10-30; docs/runs/v0.6.1d/CARD.md): v0.6.1's save of update 110, the blend held with the old pay and the\n"
        "# win pay about equal (WIN_W 0.8, FADE_V 0.5, WIN_GAIN 0.35), the rescale at 10, the pull and the brain's old belief faded out together. Refuses\n"
        "# unless: no trainer runs; the code and the judge are there; the settings check passes against v0.6.1c's command (only --run and\n"
        "# --adv-pay-ref differ); smoke.log ends ALL PASSED; the run folder is new. Then: backs up, makes duel_gru_v0_6_1d, starts the trainer,\n"
        "# the watcher (every 10 updates against the start, every fourth against v0.6.0's end), the fades and the self-play logger. Nothing stops\n"
        "# the run.   Usage (PowerShell):  powershell -ExecutionPolicy Bypass -File docs" + BS + "runs" + BS + "v0.6.1d" + BS + "start.ps1\n")
t = HEAD + t[t.index("$ErrorActionPreference"):]
t = sub(t, 'Join-Path $K1 "policy_prelevel_v061.pt"', 'Join-Path $K1 "policy_110.pt"')
t = sub(t, '$RUN = "duel_gru_v0_6_1c"', '$RUN = "duel_gru_v0_6_1d"')
t = sub(t, '"docs' + BS + 'runs' + BS + 'v0.6.1b' + BS + 'train.cmd"', '"docs' + BS + 'runs' + BS + 'v0.6.1c' + BS + 'train.cmd"')
t = sub(t, '"--allow=--run,--adv-pay-ref,--adv-pay-tau,--adv-pay-max,--adv-pay-warm"', '"--allow=--run,--minutes,--adv-pay-ref"')
t = sub(t, 'keep' + BS + 'policy_start_v061c.pt', 'keep' + BS + 'policy_start_v061d.pt')
t = sub(t, 'snapshots' + BS + 'anchor_v061_u250.pt', 'snapshots' + BS + 'anchor_v061_u110.pt')
t = sub(t, "d.update(LEVEL_PULL=0.95, BRAIN_FADE=0.0, VALUE_WARM=0)",
        "d.update(WIN_W=0.8, FADE_V=0.5, WIN_GAIN=0.35, ADV_PAY_REF=10.0, LEVEL_PULL=0.95, BRAIN_FADE=0.0, VALUE_WARM=0)")
t = sub(t, "v0.6.1's save of update 250 (the start)", "v0.6.1's save of update 110 (the start)")
t = sub(t, '(Join-Path $ROOT "tools' + BS + 'run' + BS + 'ramp_live.py"), $RUN, "BRAIN_FADE", "0", "1", "0.125", "--also", "LEVEL_PULL:0.95:1.0:0.00625", "--keep-as", "policy_prefade_v061c.pt"',
        '(Join-Path $HERE "ramp_fades.py"), $RUN')
i = t.index('Log ("watcher "')
t = t[:i] + 'Log ("watcher " + $w.Id + " | fades " + $r.Id + " (the pull 0.95 -> 1 and the brain 0 -> 1 together, eight steps, after saves, 25 min apart) | self-play logger " + $s.Id + " | no guard (owner: never stop the run)")\n'
open(os.path.join(HERE, "start.ps1"), "w", encoding="ascii", newline="").write(t)

shutil.copy2(os.path.join(SRC, "aim2_env.cmd"), os.path.join(HERE, "aim2_env.cmd"))
print("written train.cmd, start.ps1, aim2_env.cmd")

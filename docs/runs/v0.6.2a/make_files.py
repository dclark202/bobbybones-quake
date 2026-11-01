"""v0.6.2a's files (owner, 2026-10-30: the strategy head, from v0.6.1c's end, no pro-demo fit, the judge kept), made from v0.6.2's.
train.cmd: --run duel_gru_v0_6_2a (and its log) and the rescale --adv-pay-ref 10 --adv-pay-tau 5 --adv-pay-max 4 --adv-pay-warm 0
(he is already at a factor of ~3: no opening); --minutes 720 (owner, 2026-10-30: 12 h by default, asked before the start; the head in only, the item rule's fade moved to v0.6.3). start.ps1 and smoke.py: every pointer from v0.6.1b to v0.6.1c, the settings check
against v0.6.1c's command, ADV_PAY_REF 10 in live.json, start.ps1 refuses until smoke.log ends ALL PASSED, smoke.py checks the rescale.
    python docs/runs/v0.6.2a/make_files.py"""
import os
import shutil

HERE = os.path.dirname(os.path.abspath(__file__))
SRC = os.path.join(HERE, "..", "..", "archive", "versions", "v0.6.2")
BS = "\\"


def read(name):
    return open(os.path.join(SRC, name), encoding="ascii").read().replace("\r\n", "\n")


def sub(t, a, b):
    assert t.count(a) == 1, (a, t.count(a))
    return t.replace(a, b)


def names(t):
    for a, b in [("duel_gru_v0_6_1b", "duel_gru_v0_6_1c"), ("v061b", "v061c"), ("v0.6.1b", "v0.6.1c"), ("duel_gru_v0_6_2", "duel_gru_v0_6_2a"),
                 ("runs" + BS + "v0.6.2", "runs" + BS + "v0.6.2a"), ("runs" + BS + BS + "v0.6.2", "runs" + BS + BS + "v0.6.2a"), ("runs/v0.6.2", "runs/v0.6.2a"),
                 ("policy_start_v062", "policy_start_v062a"), ("scratch_v062b_smoke", "scratch_v062a_smoke"), ("v0.6.2's", "v0.6.2a's")]:
        t = t.replace(a, b)
    return t


# train.cmd
t = names(read("train.cmd"))
LOG = "data" + BS + "sim_runs" + BS + "duel_gru_v0_6_2a.log"
t = sub(t, "--resume --minutes 1440 ", "--resume --minutes 720 ")
t = sub(t, " %LEARN% >> " + LOG + " 2>&1", " --adv-pay-ref 10 --adv-pay-tau 5 --adv-pay-max 4 --adv-pay-warm 0 %LEARN% >> " + LOG + " 2>&1")
open(os.path.join(HERE, "train.cmd"), "w", encoding="ascii", newline="").write(t.replace("\n", "\r\n"))

# start.ps1
t = names(read("start.ps1"))
t = sub(t, "\"--allow=--run,--minutes,--head2,", "\"--allow=--run,--minutes,--adv-pay-ref,--adv-pay-warm,--head2,")
t = sub(t, "d.update(H2_GATE_CAP=0.0,", "d.update(ADV_PAY_REF=10.0, H2_GATE_CAP=0.0,")
t = sub(t, "if (-not (Select-String -Path (Join-Path $ROOT \"sim" + BS + "duel_env_ffa.py\")",
        "$sm = Join-Path $HERE \"smoke.log\"\n"
        "if (-not (Test-Path $sm) -or -not ((Get-Content $sm -Tail 1) -like \"*ALL PASSED*\")) { Log \"the smoke run has not passed (smoke.log): not started\"; exit 1 }\n"
        "if (-not (Select-String -Path (Join-Path $ROOT \"sim" + BS + "duel_env_ffa.py\")")
t = sub(t, "the strategy head replaces the item rule, from", "the strategy head faded in only (the item rule stays on: its fade is v0.6.3's), from")
t = sub(t, "the head-open save kept, then the item rule 0.1 a step to 0; on the clock)", "the head-open save kept, done there: RAMP_HEAD_ONLY; on the clock)")
t = sub(t, "$r = Start-Process -FilePath $PY -ArgumentList (Join-Path $ROOT \"tools" + BS + "run" + BS + "ramp_head.py\")", "$env:RAMP_HEAD_ONLY = \"1\"\n$r = Start-Process -FilePath $PY -ArgumentList (Join-Path $ROOT \"tools" + BS + "run" + BS + "ramp_head.py\")")
t = sub(t, "(shut 10 updates, then the gate, the head-open save, the item rule; on the clock)", "(shut 10 updates, then the gate, the head-open save, done; the item rule stays on; on the clock)")
open(os.path.join(HERE, "start.ps1"), "w", encoding="ascii", newline="").write(t)

# smoke.py
t = names(read("smoke.py"))
t = sub(t, '("--minutes 1440 ", "--minutes 12 ")', '("--minutes 720 ", "--minutes 12 ")')
t = sub(t, "    import torch\n",
        "    ap_ = [m.get(\"adv_pay\") for m in M]\n"
        "    say(\"adv_pay first {} last {}\".format(ap_[0], ap_[-1]))\n"
        "    check(\"adv_pay in every update\", None not in ap_)\n"
        "    if None not in ap_:\n"
        "        check(\"the factor above 1 from the first update (no opening: {})\".format(ap_[0][\"k\"]), ap_[0][\"k\"] > 1.0)\n"
        "        check(\"the target 10 throughout\", all(x[\"ref\"] == 10.0 for x in ap_))\n"
        "    import torch\n")
open(os.path.join(HERE, "smoke.py"), "w", encoding="ascii", newline="").write(t)

shutil.copy2(os.path.join(SRC, "aim2_env.cmd"), os.path.join(HERE, "aim2_env.cmd"))
print("written train.cmd, start.ps1, smoke.py, aim2_env.cmd")

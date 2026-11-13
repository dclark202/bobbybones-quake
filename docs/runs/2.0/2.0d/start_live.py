"""2.0d's live.json at the start: 2.0a's start file made anew by 2.0a's own start_live.py (the live values 1.7a's update 90 PLAYED, from
the save's record: DMG_REWARD 0.0055, DMG_TAKEN_W 0.8, WIN_ADD 0.33, KEEP_G 0.975, the order shut, no firing cost), with 2.0d's changes:
  the start's steps   DMG_REWARD 0.005, DMG_TAKEN_W 1.0 (zero-sum: item 5), RAIL_FAR_PAY 0.1 (owner, 11-12), KEEP_G 1 (item 3), HABIT_P 0 (item 6)
  the dials' starts   AIM3_W 0, AIM3_SIZE_A 1, AIM3_SIZE_B 0, AIM3_LEAD 0, AIM3_RELOAD 1 (AIM2 to the bit), DODGE_G 0 (the dodge columns zeros)
  fixed               the eye's lag 0.125, its gain 1.0, the fixation time 0.05 (AIM3.md section 9)
ramp_20d.py moves the six dials.
    python docs/runs/2.0/2.0d/start_live.py <the save (policy_u90_17a.pt)> <1.7a's live.json> <out live.json>"""
import json
import os
import subprocess
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
STEPS = dict(DMG_REWARD=0.005, DMG_TAKEN_W=1.0, RAIL_FAR_PAY=0.1, KEEP_G=1.0, HABIT_P=0.0)
NEW = dict(AIM3_W=0.0, AIM3_SIZE_A=1.0, AIM3_SIZE_B=0.0, AIM3_LEAD=0.0, AIM3_RELOAD=1.0, DODGE_G=0.0,
           AIM3_PURSUIT_TAU=0.125, AIM3_PURSUIT_GAIN=1.0, AIM3_FIX_TAU=0.05)


def main():
    out = sys.argv[3]
    r = subprocess.run([sys.executable, os.path.join(HERE, "..", "2.0a", "start_live.py"), sys.argv[1], sys.argv[2], out], capture_output=True, text=True,
                       creationflags=getattr(subprocess, "CREATE_NO_WINDOW", 0))
    print(r.stdout + r.stderr[-2000:])
    assert r.returncode == 0, "2.0a's start_live.py failed"
    d = json.load(open(out, encoding="utf-8"))
    for k_, v_ in (("DMG_REWARD", 0.0055), ("DMG_TAKEN_W", 0.8), ("WIN_ADD", 0.33), ("KEEP_G", 0.975), ("COST_FIRE_W", 0.0), ("ORD_GATE", -30.0),
                   ("RAIL_FAR_PAY", 0.25), ("CMB_G", 0.0), ("PADD", 0.0), ("FADD", 0.0)):
        assert float(d[k_]) == v_, (k_, d.get(k_), v_)
    assert float(d.get("HABIT_P", 0.3)) == 0.3, d.get("HABIT_P")
    assert not any(k_ in d for k_ in NEW) and not any(k_ in d for k_ in ("SPACE_GATE", "EDGE_PAY", "COVER_PAY", "SPACE_W", "WRULE_P", "INS_G", "INS_GATE"))
    was = {k_: d.get(k_) for k_ in STEPS}
    d.update(STEPS)
    d.update(NEW)
    print("2.0d's steps at the start: {} (were {}); the dials' start values: {}".format(json.dumps(STEPS), json.dumps(was), json.dumps(NEW)))
    json.dump(d, open(out, "w", encoding="utf-8"), indent=1)
    print("written: " + out)


if __name__ == "__main__":
    main()

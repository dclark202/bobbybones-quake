"""2.0c's live.json at the start: 2.0a's start file made anew by 2.0a's own start_live.py (the live values 1.7a's update 90 PLAYED, from
the save's record: DMG_REWARD 0.0055, DMG_TAKEN_W 0.8, WIN_ADD 0.33, KEEP_G 0.975, the order shut, no firing cost), with 2.0c's dials at
their start: AIM3_W 0, AIM3_SIZE_A 1, AIM3_SIZE_B 0 (AIM2 to the bit) and the eye's three fixed numbers. ramp_20c.py moves the five dials.
    python docs/runs/2.0/2.0c/start_live.py <the save (policy_end_17a.pt)> <1.7a's live.json> <out live.json>"""
import json
import os
import subprocess
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
NEW = dict(AIM3_W=0.0, AIM3_SIZE_A=1.0, AIM3_SIZE_B=0.0, AIM3_PURSUIT_TAU=0.125, AIM3_PURSUIT_GAIN=1.0, AIM3_FIX_TAU=0.10)


def main():
    out = sys.argv[3]
    r = subprocess.run([sys.executable, os.path.join(HERE, "..", "2.0a", "start_live.py"), sys.argv[1], sys.argv[2], out], capture_output=True, text=True)
    print(r.stdout + r.stderr[-2000:])
    assert r.returncode == 0, "2.0a's start_live.py failed"
    d = json.load(open(out, encoding="utf-8"))
    for k_, v_ in (("DMG_REWARD", 0.0055), ("DMG_TAKEN_W", 0.8), ("WIN_ADD", 0.33), ("KEEP_G", 0.975), ("COST_FIRE_W", 0.0), ("ORD_GATE", -30.0)):
        assert float(d[k_]) == v_, (k_, d[k_], v_)
    assert not any(k_ in d for k_ in NEW) and not any(k_ in d for k_ in ("SPACE_GATE", "EDGE_PAY", "COVER_PAY", "SPACE_W", "WRULE_P"))
    d.update(NEW)
    print("2.0c's start values: " + json.dumps(NEW))
    json.dump(d, open(out, "w", encoding="utf-8"), indent=1)
    print("written: " + out)


if __name__ == "__main__":
    main()

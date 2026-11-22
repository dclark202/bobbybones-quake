"""2.1a's live.json at the start (the blend, owner 11-13): 2.0d's start file made anew by 2.0d's own start_live.py (the live values 1.7a's
update 90 PLAYED, from the save's record, with 2.0d's steps: damage 0.005 zero-sum, far rail 0.1, keep share 1, no habits; the dials'
starts: AIM3 as AIM2 to the bit, DODGE_G 0), with 2.1a's own names at their start values (the instruction's dials shut, the lessons
nothing plays from at 1). ramp_21a.py moves the dials.
    python docs/runs/2.1/2.1a/start_live.py <the save (policy_u90_17a.pt)> <1.7a's live.json> <out live.json>"""
import json
import os
import subprocess
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
NEW = dict(DRILL_INS_P=0.0, DRILL_INS_RATE=0.0, BRANCH_P=0.0, INS_GATE=-30.0, INS_G=0.0, BRANCH_WPN_P=0.0, BRANCH_LONG_P=0.0, INS_LONG_W=0.0, H2_INS_PG=0.0,
           MAP_SENSE_W=1.0, APPRAISE_W=1.0, KNOWN_W=1.0, SPAWN_W=1.0, INS_TEACH=1.0, INS_TEMP=0.05, INS_ENT=0.0)
FROM_20D = dict(DMG_REWARD=0.005, DMG_TAKEN_W=1.0, RAIL_FAR_PAY=0.1, KEEP_G=1.0, HABIT_P=0.0, WIN_ADD=0.33, AIM3_W=0.0, AIM3_SIZE_A=1.0, AIM3_SIZE_B=0.0,
                AIM3_LEAD=0.0, AIM3_RELOAD=1.0, DODGE_G=0.0, AIM3_FIX_TAU=0.05, COST_FIRE_W=0.0, CMB_G=0.0, PADD=0.0, FADD=0.0, ORD_GATE=-30.0)


def main():
    out = sys.argv[3]
    r = subprocess.run([sys.executable, os.path.join(HERE, "..", "..", "2.0", "2.0d", "start_live.py"), sys.argv[1], sys.argv[2], out],
                       capture_output=True, text=True, creationflags=getattr(subprocess, "CREATE_NO_WINDOW", 0))
    print(r.stdout + r.stderr[-2000:])
    assert r.returncode == 0, "2.0d's start_live.py failed"
    d = json.load(open(out, encoding="utf-8"))
    off = {k_: (d.get(k_), v_) for k_, v_ in FROM_20D.items() if k_ not in d or abs(float(d[k_]) - v_) > 1e-9}
    assert not off, "2.0d's start values are not what the card says: {}".format(off)
    assert not any(k_ in d for k_ in NEW), "2.0d's start file has a name of 2.1a's already: {}".format([k_ for k_ in NEW if k_ in d])
    d.update(NEW)
    print("2.1a's own names at the start: " + json.dumps(NEW))
    json.dump(d, open(out, "w", encoding="utf-8"), indent=1)
    print("written: " + out)


if __name__ == "__main__":
    main()

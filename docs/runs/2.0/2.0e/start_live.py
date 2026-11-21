"""2.0e's live.json at the start: 1.6a's last live.json (the values its end played: DMG_TAKEN_W 0.8, WIN_ADD 0.33, RAIL_FAR_PAY 0.25,
INTENT_HOLD 8, CONTACT_FREE 1, the item teacher and the speed pay out, no firing cost), with:
  the step            HABIT_P 0 (owner, 11-14: the weapon habits dropped entirely)
  the dials' starts   DMG_REWARD 0.0055 (the command's value, in the file so the ramp can move it), AIM3_W 0, AIM3_SIZE_A 1, AIM3_SIZE_B 0,
                      AIM3_LEAD 0, AIM3_RELOAD 1 (AIM2 to the bit), DODGE_G 0 (the dodge columns zeros)
  fixed               the eye's lag 0.125, its gain 1.0, the fixation time 0.05 (AIM3.md section 9)
ramp_20e.py moves the dials: AIM3 over updates 0 to 25; DMG_REWARD 0.005, DMG_TAKEN_W 1.0, RAIL_FAR_PAY 0.1 over 25 to 35; DODGE_G over 35 to 60.
    python docs/runs/2.0/2.0e/start_live.py <1.6a's live.json> <out live.json>"""
import json
import sys

STEPS = dict(HABIT_P=0.0)
NEW = dict(DMG_REWARD=0.0055, AIM3_W=0.0, AIM3_SIZE_A=1.0, AIM3_SIZE_B=0.0, AIM3_LEAD=0.0, AIM3_RELOAD=1.0, DODGE_G=0.0,
           AIM3_PURSUIT_TAU=0.125, AIM3_PURSUIT_GAIN=1.0, AIM3_FIX_TAU=0.05)


def main():
    d = json.load(open(sys.argv[1], encoding="utf-8"))
    for k_, v_ in (("DMG_TAKEN_W", 0.8), ("WIN_ADD", 0.33), ("RAIL_FAR_PAY", 0.25), ("INTENT_HOLD", 8.0), ("CONTACT_FREE", 1.0), ("COST_FIRE_W", 0.0),
                   ("SPEED_PAY", 0.0), ("INTENT_TEACH_W", 0.0), ("HABIT_P", 0.3), ("H2_PG", 1.0), ("H2_WPG", 1.0), ("ITEM_PT_MIX", 1.0), ("STACK_DIFF", 0.0)):
        assert float(d[k_]) == v_, (k_, d.get(k_), v_)
    assert d["ITEM_FLAT"] == "MH:0.35,RA:0.30,YA:0.15", d["ITEM_FLAT"]
    assert not any(k_ in d for k_ in NEW) and not any(k_ in d for k_ in ("KEEP_G", "CMB_G", "PADD", "FADD", "ORD_GATE", "INS_G", "INS_GATE", "WRULE_P"))
    was = {k_: d.get(k_) for k_ in STEPS}
    d.update(STEPS)
    d.update(NEW)
    print("2.0e's step at the start: {} (was {}); the dials' start values: {}".format(json.dumps(STEPS), json.dumps(was), json.dumps(NEW)))
    json.dump(d, open(sys.argv[2], "w", encoding="utf-8"), indent=1)
    print("written: " + sys.argv[2])


if __name__ == "__main__":
    main()

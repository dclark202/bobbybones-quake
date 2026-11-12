"""2.1a's live.json at the start: what 1.8a's save of update 50 PLAYED (the record in the save itself: its "live", the simulators' and the
trainer's names), written under the names 1.8a's live.json carries, with 2.1a's own names at their start values. ramp_21a.py moves the
dials. Refuses if the save's record is not "b1.2d under AIM3" (AIM3 at its end values, the old head's credit 0, the item teacher 1, the
speed pay 0.125, the keep choice and the strategy fade at 0).
    python docs/runs/2.1/2.1a/start_live.py <1.8a's policy_u50_18a.pt> <1.8a's live.json (for its names)> <out live.json>"""
import json
import sys

# 2.1a's own names at the start (the ramp's "before" values; the lessons nothing plays from at 1 from update 0)
NEW = dict(DRILL_INS_P=0.0, DRILL_INS_RATE=0.0, BRANCH_P=0.0, INS_GATE=-30.0, INS_G=0.0, BRANCH_WPN_P=0.0, BRANCH_LONG_P=0.0, INS_LONG_W=0.0, H2_INS_PG=0.0,
           INTENT_SWITCH=0.02, WEAPON_OWN=0.0,
           MAP_SENSE_W=1.0, APPRAISE_W=1.0, KNOWN_W=1.0, SPAWN_W=1.0, INS_TEACH=1.0, INS_TEMP=0.05, INS_ENT=0.0)
# what update 50 must have played (the card: "b1.2d under AIM3", before the head's credit)
WANT = dict(AIM3_W=1.0, AIM3_SIZE_A=0.39, AIM3_SIZE_B=0.355, AIM3_LEAD=1.0, AIM3_RELOAD=0.0, AIM3_FIX_TAU=0.05, H2_PG=0.0, INTENT_TEACH_W=1.0, SPEED_PAY=0.125,
            KEEP_G=0.0, SFADE=0.0, DMG_REWARD=0.005, DMG_TAKEN_W=1.0, WIN_ADD=0.33, INTENT_HOLD=8.0, COST_FIRE_W=0.0, H2_WPG=0.0, HABIT_P=0.0)


def main():
    import torch
    ck = torch.load(sys.argv[1], map_location="cpu", weights_only=False)
    names = json.load(open(sys.argv[2], encoding="utf-8"))
    rec = {}
    for part in ("sim", "trainer"):
        rec.update((ck.get("live") or {}).get(part) or {})
    assert rec, "the save has no record of what it played"
    d = {}
    for k_, now_ in names.items():
        v_ = rec.get(k_)
        assert v_ is not None, "{}: in 1.8a's live.json, not in the save's record".format(k_)
        d[k_] = v_ if isinstance(now_, str) else float(v_)
    off = {k_: (d.get(k_), v_) for k_, v_ in WANT.items() if k_ not in d or abs(float(d[k_]) - v_) > 1e-9}
    assert not off, "the save did not play 'b1.2d under AIM3': {}".format(off)
    ev = ck.get("env_vars") or {}
    assert str(ev.get("WEAPON_OWN", "0")) in ("0", "0.0") and float(ev.get("INTENT_HOLD", 8.0)) == 8.0, "the save's play variables: {}".format(
        {k_: ev.get(k_) for k_ in ("WEAPON_OWN", "INTENT_HOLD")})
    assert not any(k_ in d for k_ in NEW), "1.8a's live.json has a name of 2.1a's already"
    d.update(NEW)
    print("2.1a's start: as update 50 played ({} names), and its own: {}".format(len(names), json.dumps(NEW)))
    json.dump(d, open(sys.argv[3], "w", encoding="utf-8"), indent=1)
    print("written: " + sys.argv[3])


if __name__ == "__main__":
    main()

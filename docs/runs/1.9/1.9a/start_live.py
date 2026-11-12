"""1.9a's live.json at the start: what 1.8a's end (its save of update 190) PLAYED (the record in the save itself: its "live", the
simulators' and the trainer's names), written under the names 1.8a's live.json carries, with 1.8a's last two fades at their ends (the item
rule's lesson and the speed pay: 0; the save of update 190 was taken a step before they reached it), the old head's credit closed, and 1.9a's
own names at their start values. ramp_19a.py moves the dials. Refuses if the save's record is not 1.8a's end.
    python docs/runs/1.9/1.9a/start_live.py <1.8a's policy_end_18a.pt> <1.8a's live.json (for its names)> <out live.json>"""
import json
import sys

# 1.9a's own names at the start (the ramp's "before" values)
NEW = dict(INS_GATE=-30.0, INS_G=0.0, H2_INS_PG=0.0, INS_COPY=1.0, FOLLOW_PAY=0.0, INTENT_SWITCH=0.0, WEAPON_OWN=1.0,
           DRILL_INS_P=0.0, DRILL_INS_RATE=0.0, BRANCH_P=0.0, BRANCH_WPN_P=0.0, APPRAISE_W=0.0, INS_TEACH=0.0, INS_TEMP=0.05, INS_ENT=0.0)
# set at the start (decided here, the card): the old head's target credit closed (the instruction's rows do its job); 1.8a's last fades at their ends
SET = dict(H2_PG=0.0, INTENT_TEACH_W=0.0, SPEED_PAY=0.0, RAIL_FAR_PAY=0.1)    # (owner, 11-12: the far-rail pay stays, at 0.1 from the start)
# what update 190 must have played (1.8a's end: AIM3 at its end values, the head's credit full, the keep choice and the strategy fade shut)
WANT = dict(AIM3_W=1.0, AIM3_SIZE_A=0.39, AIM3_SIZE_B=0.355, AIM3_LEAD=1.0, AIM3_RELOAD=0.0, AIM3_FIX_TAU=0.05, H2_PG=1.0,
            KEEP_G=0.0, SFADE=0.0, DMG_REWARD=0.005, DMG_TAKEN_W=1.0, WIN_ADD=0.33, INTENT_HOLD=8.0, COST_FIRE_W=0.0, H2_WPG=0.0, HABIT_P=0.0,
            RAIL_FAR_PAY=0.25)
NEAR_END = dict(INTENT_TEACH_W=0.1, SPEED_PAY=0.0125)        # (the fades u160 -> 190: within one step of their end)


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
    off.update({k_: (d.get(k_), "<= {}".format(v_)) for k_, v_ in NEAR_END.items() if k_ not in d or float(d[k_]) > v_ + 1e-9})
    assert not off, "the save did not play 1.8a's end: {}".format(off)
    ev = ck.get("env_vars") or {}
    assert str(ev.get("WEAPON_OWN", "0")) in ("1", "1.0") and float(ev.get("INTENT_HOLD", 8.0)) == 8.0, "the save's play variables: {}".format(
        {k_: ev.get(k_) for k_ in ("WEAPON_OWN", "INTENT_HOLD")})
    for k_, v_ in SET.items():
        assert k_ in d, k_
        d[k_] = v_
    for k_, v_ in NEW.items():
        if k_ in d:
            assert abs(float(d[k_]) - v_) < 1e-9 or k_ in ("INTENT_SWITCH", "WEAPON_OWN"), "1.8a's live.json has {} at {}".format(k_, d[k_])
        d[k_] = v_
    print("1.9a's start: as update 190 played ({} names); set {}; its own {}".format(len(names), json.dumps(SET), json.dumps(NEW)))
    json.dump(d, open(sys.argv[3], "w", encoding="utf-8"), indent=1)
    print("written: " + sys.argv[3])


if __name__ == "__main__":
    main()

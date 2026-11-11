"""2.0b's live.json at the start: 2.0a's last live.json (the dials its end played: checked against the trainer's own record of the file it
applied, live_applied.json) with 2.0b's start values, every part of 2.0b shut: SPACE_GATE 0, EDGE_PAY 0, COVER_PAY 0; SPACE_W 1 (the
readout's lesson on from update 0). ramp_20b.py moves SPACE_GATE and EDGE_PAY from there.
    python docs/runs/2.0/2.0b/start_live.py <2.0a's live.json> <2.0a's live_applied.json> <out live.json>"""
import json
import sys

NEW = dict(SPACE_GATE=0.0, EDGE_PAY=0.0, COVER_PAY=0.0, SPACE_W=1.0)


def main():
    d = json.load(open(sys.argv[1], encoding="utf-8"))
    ap = (json.load(open(sys.argv[2], encoding="utf-8")).get("file") or {})
    dif = {k_: (d.get(k_), ap.get(k_)) for k_ in sorted(set(d) | set(ap)) if str(d.get(k_)) != str(ap.get(k_))}
    assert not dif, "2.0a's live.json is not the file its trainer last applied: {}".format(dif)
    for k_, v_ in (("DMG_REWARD", 0.001), ("DMG_TAKEN_W", 1.0), ("WIN_ADD", 0.6), ("KEEP_G", 0.975), ("CMB_G", 0.0), ("PADD", 0.0), ("FADD", 0.0),
                   ("H2_FPG", 0.0), ("ORD_GATE", -30.0), ("COST_FIRE_W", 0.0), ("HABIT_P", 0.3), ("H2_WPG", 1.0), ("SPEED_PAY", 0.0),
                   ("ITEM_PT_MIX", 1.0), ("STACK_DIFF", 0.0)):
        assert float(d[k_]) == v_, (k_, d[k_], v_)
    assert d["ITEM_FLAT"] == "MH:0.35,RA:0.30,YA:0.15", d["ITEM_FLAT"]
    assert not any(k_ in d for k_ in NEW) and "WRULE_P" not in d
    print("2.0a's end played: " + json.dumps({k_: d[k_] for k_ in sorted(d)}))
    d.update(NEW)
    print("2.0b's start values: " + json.dumps(NEW))
    json.dump(d, open(sys.argv[3], "w", encoding="utf-8"), indent=1)
    print("written: " + sys.argv[3])


if __name__ == "__main__":
    main()

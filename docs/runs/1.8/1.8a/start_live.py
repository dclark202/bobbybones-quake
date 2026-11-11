"""1.8a's live.json at the start: b1.2d's own live file (checked against the record in its end save: what b1.2d's end PLAYED), with the
names the strategy head, the keep choice and AIM3 need at their start values, and the damage pay at 0.005 and zero-sum (owner, 2026-11-11: "Change the
damage pay to 0.005 at the start"; "damage should be zero sum from the start": DMG_TAKEN_W 0.8 -> 1.0). ramp_18a.py moves AIM3_W, AIM3_SIZE_A, AIM3_SIZE_B, H2_PG, INTENT_TEACH_W, SPEED_PAY and KEEP_G.
    python docs/runs/1.8/1.8a/start_live.py <b1.2d's end (policy_end_b12d.pt)> <b1.2d's live.json> <out live.json>"""
import json
import sys

HEAD = dict(H2_GATE_CAP=0.0, H2_GATE_OPEN=0.0, H2_PG=0.0, H2_MIX=0.0, H2_COPY=0.0, H2_WPG=0.0, HABIT_P=0.0, KEEP_G=0.0, SFADE=0.0)
AIM = dict(AIM3_W=0.0, AIM3_SIZE_A=1.0, AIM3_SIZE_B=0.0, AIM3_PURSUIT_TAU=0.125, AIM3_PURSUIT_GAIN=1.0, AIM3_FIX_TAU=0.05, AIM3_LEAD=0.0, AIM3_RELOAD=1.0)
PAY = dict(DMG_REWARD=0.005, DMG_TAKEN_W=1.0)                 # (owner, 11-11: 0.005, and "damage should be zero sum from the start": b1.2d's 0.8 -> 1.0)
WANT = dict(WIN_ADD=0.33, DMG_TAKEN_W=0.8, INTENT_TEACH_W=1.0, SPEED_PAY=0.125, COST_FIRE_W=0.0, COST_JERK_W=0.0, STACK_DIFF=0.0, RAIL_FAR_PAY=0.25,
            INTENT_HOLD=8.0, ITEM_PT_MIX=1.0, ITEM_FLAT="MH:0.35,RA:0.30,YA:0.15")


def main():
    import torch
    ck = torch.load(sys.argv[1], map_location="cpu", weights_only=False)
    d = json.load(open(sys.argv[2], encoding="utf-8"))
    rec = {}
    for part in ("sim", "trainer"):
        rec.update((ck.get("live") or {}).get(part) or {})
    off = {k_: (d.get(k_), rec[k_]) for k_ in rec if k_ in d and rec[k_] is not None and not isinstance(d[k_], str) and abs(float(d[k_]) - float(rec[k_])) > 1e-9}
    assert not off, "b1.2d's live.json is not what its end save played: {}".format(off)
    for k_, v_ in WANT.items():
        assert d.get(k_) == v_, (k_, d.get(k_), v_)
    assert not any(k_ in d for k_ in list(HEAD) + list(AIM) + ["DMG_REWARD"]), "b1.2d's live.json has a name of 1.8a's already"
    d.update(HEAD)
    d.update(AIM)
    d.update(PAY)
    print("1.8a's start values: " + json.dumps(dict(HEAD, **AIM, **PAY)))
    json.dump(d, open(sys.argv[3], "w", encoding="utf-8"), indent=1)
    print("written: " + sys.argv[3])


if __name__ == "__main__":
    main()

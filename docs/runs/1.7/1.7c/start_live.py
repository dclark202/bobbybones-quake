"""1.7c's live.json at the start: the live values 1.7a's update 90 PLAYED (the save carries them: its "live" record, the simulators' and the
trainer's), with 1.7c's changes: HABIT_P 0 (the habit seats off), H2_WPG 0 (the head's weapon credit off), WRULE_P 0 (the table's share at
the start; ramp_17c.py opens it), KEEP_G 0.975 (as the save). Everything else, the pay above all, exactly as the save played it. Prints what
differs from the save and from 1.7a's last live.json (its end, update 246: the order open there), so the start is read, not assumed.
    python docs/runs/1.7/1.7c/start_live.py <the save (policy_end_17a.pt)> <1.7a's live.json> <out live.json>"""
import json
import sys

import torch

CHANGE = dict(HABIT_P=0.0, H2_WPG=0.0, WRULE_P=0.0, KEEP_G=0.975)


def main():
    ck = torch.load(sys.argv[1], map_location="cpu", weights_only=False)
    lv = ck.get("live") or {}
    sim_, tr_ = lv.get("sim") or {}, lv.get("trainer") or {}
    d = {}
    for k_, v_ in sim_.items():                              # the simulators' values are kept as strings in the record; numbers back as numbers
        if v_ is None:
            continue
        try:
            d[k_] = float(v_) if not isinstance(v_, str) or v_.replace(".", "", 1).replace("-", "", 1).isdigit() else v_
        except ValueError:
            d[k_] = v_
    d.update({k_: v_ for k_, v_ in tr_.items() if v_ is not None})
    for k_ in ("DMG_REWARD", "FADE_OPEN", "BTOK_GATE_OPEN", "H2_GATE_OPEN", "H2_GATE_CAP", "BELIEF_LR", "TRACK_W", "TRACK_TRUNK", "TRACK_Z_W",
               "AHEAD_W", "BRAIN_HUMAN_W", "INFO_PAY", "ITEM_FLOOR", "ITEM_FLOOR_W", "H2_PG", "H2_MIX"):
        d.pop(k_, None)                                      # (the command's own, or a record only: not live names the file carries)
    old = json.load(open(sys.argv[2], encoding="utf-8"))
    d = {k_: v_ for k_, v_ in d.items() if k_ in old or k_ in CHANGE}     # only names 1.7a's file carried (the trainer's reader knows them)
    for k_ in old:
        if k_ not in d:
            d[k_] = old[k_]
            print("from 1.7a's last live.json (not in the save's record): {} = {}".format(k_, old[k_]))
    before = dict(d)
    d.update(CHANGE)
    print("the save (1.7a's update 90) played: " + json.dumps({k_: before.get(k_) for k_ in sorted(before)}))
    print("1.7c changes: " + json.dumps({k_: (before.get(k_), v_) for k_, v_ in CHANGE.items() if before.get(k_) != v_}))
    print("differs from 1.7a's last live.json (update 246): " + json.dumps({k_: (old.get(k_), d.get(k_)) for k_ in sorted(set(old) | set(d))
                                                                            if str(old.get(k_)) != str(d.get(k_))}))
    for k_, v_ in (("CMB_G", 0.0), ("PADD", 0.0), ("FADD", 0.0), ("H2_FPG", 0.0), ("ORD_GATE", -30.0), ("COST_FIRE_W", 0.0), ("WRULE_P", 0.0),
                   ("HABIT_P", 0.0), ("KEEP_G", 0.975), ("DMG_TAKEN_W", 0.8), ("WIN_ADD", 0.33)):
        assert float(d[k_]) == v_, (k_, d[k_], v_)
    assert d["ITEM_FLAT"] == "MH:0.35,RA:0.30,YA:0.15", d["ITEM_FLAT"]
    json.dump(d, open(sys.argv[3], "w", encoding="utf-8"), indent=1)
    print("written: " + sys.argv[3])


if __name__ == "__main__":
    main()

"""2.2c's live.json at the start (made as 2.2b's: docs/runs/2.2/2.2b/start_live.py): 2.2a's last live.json (the values 2.2a played last: the pull
PULL_G 2 and the held share HELD_G 1 as they are, AIM3 at its values, the damage pay 0.005, DMG_TAKEN_W 0.9, DODGE_G 1, the win part WIN_ADD
0.33, no item rule, no firing cost), without the rater's dials (OUT_G, OUT_PICK, OUT_TRIAL, OUT_SRC), with 2.2c's dials at their start:
  the ramp's at clock 0 (ramp_22c.py: FGT_GATE -30, H2_WADD 1); NEAR_OUT 300; and never written by the ramp:
  NEAR_PAY 5 (the near-miss pay at 2.2b's size from update 0), H2_WPG 0 (2.2b's restart: the weapon key the hands' own), LEV_G 1 (the lever's
  share; the trainer plays it at 0 to update 10 by its own count, --lev-from 10), CONTEST_W 0.8, CEDE_W 0.1 (the contest pay), RAIL_PICK_PAY 0.15,
  RAIL_LINE_PAY 0.10, RAIL_FAR_PAY 0.5 (the rail chain; 2.2a played the far rail at 0.1)
Refuses (exit 1) when 2.2a's file is not at the values 2.2a ran with or already has a 2.2b or 2.2c name.
    python docs/runs/2.2/2.2c/start_live.py <2.2a's live.json> <out live.json> [--any]
--any (the smoke and the live test only): only the values that must always hold are asserted (the lock, no firing cost, no habits, no item rule)."""
import json
import os
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
import ramp_22c as R  # noqa: E402

NEW = dict(R.sched(0.0), NEAR_OUT=300.0, NEAR_PAY=5.0, H2_WPG=0.0, LEV_G=1.0, CONTEST_W=0.8, CEDE_W=0.1, RAIL_PICK_PAY=0.15, RAIL_LINE_PAY=0.10)
FAR_RAIL = 0.5
GONE = ("OUT_G", "OUT_PICK", "OUT_TRIAL", "OUT_SRC")
RAN_22A = (("DMG_TAKEN_W", 0.9), ("DMG_REWARD", 0.005), ("RAIL_FAR_PAY", 0.1), ("WIN_ADD", 0.33), ("INTENT_HOLD", 8.0), ("CONTACT_FREE", 1.0),
           ("COST_FIRE_W", 0.0), ("SPEED_PAY", 0.0), ("INTENT_TEACH_W", 0.0), ("HABIT_P", 0.0), ("H2_PG", 1.0), ("H2_WPG", 1.0), ("ITEM_PT_MIX", 1.0),
           ("STACK_DIFF", 0.0), ("AIM3_W", 1.0), ("AIM3_SIZE_A", 0.39), ("AIM3_SIZE_B", 0.355), ("AIM3_LEAD", 1.0), ("AIM3_RELOAD", 0.0),
           ("AIM3_PURSUIT_TAU", 0.125), ("AIM3_PURSUIT_GAIN", 1.0), ("AIM3_FIX_TAU", 0.05), ("DODGE_G", 1.0), ("HELD_G", 1.0), ("PULL_G", 2.0),
           ("LEVEL_PULL", 1.0), ("WIN_W", 0.0))
ALWAYS = (("INTENT_HOLD", 8.0), ("COST_FIRE_W", 0.0), ("HABIT_P", 0.0), ("INTENT_TEACH_W", 0.0))


def main():
    args = [x for x in sys.argv[1:] if not x.startswith("--")]
    any_ = "--any" in sys.argv[1:]
    d = json.load(open(args[0], encoding="utf-8"))
    for k_, v_ in (ALWAYS if any_ else RAN_22A):
        if k_ not in d or abs(float(d[k_]) - v_) > 1e-6:
            raise SystemExit("2.2a's live.json has {} = {}, not {}: not made".format(k_, d.get(k_), v_))
    if not any_ and d.get("ITEM_FLAT") != "MH:0.35,RA:0.30,YA:0.15":
        raise SystemExit("2.2a's live.json has ITEM_FLAT {}: not made".format(d.get("ITEM_FLAT")))
    old_ = [k_ for k_ in list(NEW) + ["FGT_BIAS", "FGT_G", "FGT_W", "PRACTICE_P"] if k_ in d and k_ not in ("H2_WPG",)]
    if old_:
        raise SystemExit("2.2a's live.json already has {}: not made".format(old_))
    for k_ in GONE:
        d.pop(k_, None)
    d.update(NEW)
    d["RAIL_FAR_PAY"] = FAR_RAIL
    print("2.2c's names at the start: {}; RAIL_FAR_PAY {}; taken out: {}; every other value as 2.2a's {} ({} names)".format(
        json.dumps(NEW), FAR_RAIL, GONE, "file (not checked: --any)" if any_ else "file", len(d)))
    json.dump(d, open(args[1], "w", encoding="utf-8"), indent=1)
    print("written: " + args[1])


if __name__ == "__main__":
    main()

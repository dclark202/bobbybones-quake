"""2.1b's live.json at the start: 2.0e's last live.json (the values its end played: AIM3 at its 11-11 end values, the zero-sum damage pay
0.005, the far rail 0.1, DODGE_G 1, the lock INTENT_HOLD 8 with CONTACT_FREE 1, no weapon habits, no firing cost), with the new names:
  KEEP_G 0          the keep choice's share (its zone layer: contact and arrivals): shut, the lock decides everywhere      (ramp_21b.py, step B)
  KEEPQ_G 0         its quiet layer's share of the quiet readings: shut                                                   (ramp_21b.py, step C)
  KEEP_TEACH 1      the keep choice's silent lesson toward the stay value's sign, all run
  STAY_W 1          the stay value's lesson from the keep forks, all run
  BRANCH_P 0.2      the share of each simulator's self-play matches that are fork destinations
  BRANCH_ZONE_P 0.5 the share of the keep forks' moments taken in contact or at an arrival (the rest quiet, read over 30 s)
  DMG_TAKEN_W 0.9  changed from 2.0e's 1.0 (owner 11-14: damage taken costs 0.9 of the pay of damage dealt)
Every other value as 2.0e's end played it. Refuses (exit 1) when 2.0e's file is not at its end values or already has a new name.
    python docs/runs/2.1/2.1b/start_live.py <2.0e's live.json> <out live.json> [--any]
--any (the smoke only, on a file of 2.0e mid-run): the end values are not asserted."""
import json
import sys

NEW = dict(KEEP_G=0.0, KEEPQ_G=0.0, KEEP_TEACH=1.0, STAY_W=1.0, BRANCH_P=0.2, BRANCH_ZONE_P=0.5)
CHANGED = dict(DMG_TAKEN_W=0.9)   # (owner 11-14: damage taken costs 0.9 of the pay of damage dealt; 2.0e ended at 1.0)
END_20E = (("DMG_TAKEN_W", 1.0), ("DMG_REWARD", 0.005), ("RAIL_FAR_PAY", 0.1), ("WIN_ADD", 0.33), ("INTENT_HOLD", 8.0), ("CONTACT_FREE", 1.0),
           ("COST_FIRE_W", 0.0), ("SPEED_PAY", 0.0), ("INTENT_TEACH_W", 0.0), ("HABIT_P", 0.0), ("H2_PG", 1.0), ("H2_WPG", 1.0), ("ITEM_PT_MIX", 1.0),
           ("STACK_DIFF", 0.0), ("AIM3_W", 1.0), ("AIM3_SIZE_A", 0.39), ("AIM3_SIZE_B", 0.355), ("AIM3_LEAD", 1.0), ("AIM3_RELOAD", 0.0),
           ("AIM3_PURSUIT_TAU", 0.125), ("AIM3_PURSUIT_GAIN", 1.0), ("AIM3_FIX_TAU", 0.05), ("DODGE_G", 1.0))
ALWAYS = (("INTENT_HOLD", 8.0), ("COST_FIRE_W", 0.0), ("HABIT_P", 0.0))     # (also on a mid-run file: the lock in, no firing cost, no habits)


def main():
    args = [x for x in sys.argv[1:] if not x.startswith("--")]
    any_ = "--any" in sys.argv[1:]
    d = json.load(open(args[0], encoding="utf-8"))
    for k_, v_ in (ALWAYS if any_ else END_20E):
        if k_ not in d or abs(float(d[k_]) - v_) > 1e-6:
            raise SystemExit("2.0e's live.json has {} = {}, not {}: not made".format(k_, d.get(k_), v_))
    if d.get("ITEM_FLAT") != "MH:0.35,RA:0.30,YA:0.15":
        raise SystemExit("2.0e's live.json has ITEM_FLAT {}: not made".format(d.get("ITEM_FLAT")))
    old_ = [k_ for k_ in list(NEW) + ["CMB_G", "PADD", "FADD", "ORD_GATE", "INS_G", "INS_GATE", "WRULE_P"] if k_ in d]
    if old_:
        raise SystemExit("2.0e's live.json already has {}: not made".format(old_))
    d.update(NEW)
    d.update(CHANGED)
    print("2.1b's new names at the start: {}; changed: {}; every other value as 2.0e's {} ({} names)".format(
        json.dumps(NEW), json.dumps(CHANGED), "file (not checked at its end values: --any)" if any_ else "end", len(d)))
    json.dump(d, open(args[1], "w", encoding="utf-8"), indent=1)
    print("written: " + args[1])


if __name__ == "__main__":
    main()

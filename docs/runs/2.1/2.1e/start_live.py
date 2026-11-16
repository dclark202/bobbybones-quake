"""2.1e's live.json at the start: 2.1d's last live.json (the values 2.1d played last: its pull PULL_G and held share HELD_G as they are, AIM3
at 2.0e's end values, the damage pay 0.005, DMG_TAKEN_W 0.9, the far rail 0.1, DODGE_G 1, the lock INTENT_HOLD 8 with CONTACT_FREE 1, no
weapon habits, no firing cost, no item rule), with:
  SLOW_MIX 0        the pull's source: the fast plan alone (2.1d's pull to the bit)          (ramp_21e.py opens it 0 -> 1 over updates 20 to 50)
  SLOW_BACK 0       the read-back's gate: shut                                                (ramp_21e.py opens it 0 -> 1 over updates 50 to 80)
  SLOW_PICK 1       the half that plays: the 2-second one (the owner sets it by hand at update 20; the ramp never writes it)
Every other value as 2.1d's file has it; PULL_G and HELD_G are taken as found (the ramp never writes them: "PULL_G and HELD_G stay where 2.1d
ends", the card). Refuses (exit 1) when 2.1d's file is not at the values 2.1d ran with or already has a new name.
    python docs/runs/2.1/2.1e/start_live.py <2.1d's live.json> <out live.json> [--any]
--any (the smoke and the live test only): the values are not asserted, but the ones that must hold always (the lock, no firing cost, no
habits, no item rule's lesson: the pull refuses it)."""
import json
import sys

NEW = dict(SLOW_MIX=0.0, SLOW_BACK=0.0, SLOW_PICK=1)
RAN_21D = (("DMG_TAKEN_W", 0.9), ("DMG_REWARD", 0.005), ("RAIL_FAR_PAY", 0.1), ("WIN_ADD", 0.33), ("INTENT_HOLD", 8.0), ("CONTACT_FREE", 1.0),
           ("COST_FIRE_W", 0.0), ("SPEED_PAY", 0.0), ("INTENT_TEACH_W", 0.0), ("HABIT_P", 0.0), ("H2_PG", 1.0), ("H2_WPG", 1.0), ("ITEM_PT_MIX", 1.0),
           ("STACK_DIFF", 0.0), ("AIM3_W", 1.0), ("AIM3_SIZE_A", 0.39), ("AIM3_SIZE_B", 0.355), ("AIM3_LEAD", 1.0), ("AIM3_RELOAD", 0.0),
           ("AIM3_PURSUIT_TAU", 0.125), ("AIM3_PURSUIT_GAIN", 1.0), ("AIM3_FIX_TAU", 0.05), ("DODGE_G", 1.0))
ALWAYS = (("INTENT_HOLD", 8.0), ("COST_FIRE_W", 0.0), ("HABIT_P", 0.0), ("INTENT_TEACH_W", 0.0))   # (the pull refuses the item rule's lesson)


def main():
    args = [x for x in sys.argv[1:] if not x.startswith("--")]
    any_ = "--any" in sys.argv[1:]
    d = json.load(open(args[0], encoding="utf-8"))
    for k_, v_ in (ALWAYS if any_ else RAN_21D):
        if k_ not in d or abs(float(d[k_]) - v_) > 1e-6:
            raise SystemExit("2.1d's live.json has {} = {}, not {}: not made".format(k_, d.get(k_), v_))
    if not any_ and d.get("ITEM_FLAT") != "MH:0.35,RA:0.30,YA:0.15":
        raise SystemExit("2.1d's live.json has ITEM_FLAT {}: not made".format(d.get("ITEM_FLAT")))
    for k_, hi_ in (("HELD_G", 1.0), ("PULL_G", 5.0)):
        if k_ not in d or not 0.0 <= float(d[k_]) <= hi_:
            raise SystemExit("2.1d's live.json has no {} in 0 .. {} ({}): not made".format(k_, hi_, d.get(k_)))
    old_ = [k_ for k_ in list(NEW) + ["CMB_G", "PADD", "FADD", "ORD_GATE", "INS_G", "INS_GATE", "WRULE_P", "KEEP_G", "KEEPQ_G", "KEEP_TEACH", "STAY_W",
                                      "BRANCH_P", "BRANCH_ZONE_P"] if k_ in d]
    if old_:
        raise SystemExit("2.1d's live.json already has {}: not made".format(old_))
    if float(d.get("ITEM_FLOOR_W", 0.0)) != 0.0:
        raise SystemExit("2.1d's live.json has ITEM_FLOOR_W {} (the floor on his item odds): not made (not in 2.1d's play)".format(d.get("ITEM_FLOOR_W")))
    d.update(NEW)
    print("2.1e's new names at the start: {}; PULL_G ({}) and HELD_G ({}) as 2.1d's file has them; every other value as 2.1d's {} ({} names)".format(
        json.dumps(NEW), d["PULL_G"], d["HELD_G"], "file (not checked: --any)" if any_ else "file", len(d)))
    json.dump(d, open(args[1], "w", encoding="utf-8"), indent=1)
    print("written: " + args[1])


if __name__ == "__main__":
    main()

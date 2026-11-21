"""2.2b's restart (11-17 evening): the two alarms and the freeze's proof line, read from one metrics.jsonl line. ramp_22b.py writes them into
watch/watch.log every update from update 1; run alone it replays a metrics.jsonl (the failed start's, for the proof that they would have fired):

    python docs/runs/2.2/2.2b/alarms_22b.py <metrics.jsonl>

  (a) the gauntlet in hand (v14.in_hand.g) over GAUNTLET_MAX (0.05): MAJOR
  (b) the weapon choice's speed (weapon.kl) over KL_MAX (0.045, three times its normal 0.015): MAJOR
  (c) the freeze's proof (h2_freeze, written by the trainer with --h2-freeze / --h2-wsc-freeze): a plain line every update; MAJOR if a held
      parameter of the item picker moved (its largest difference to the start not exactly 0) or the block is missing or failed
"""
import json
import sys

GAUNTLET_MAX = 0.05
KL_MAX = 0.045


def _dig(d, ks):
    for k_ in ks:
        if not isinstance(d, dict):
            return None
        d = d.get(k_)
    return d


def lines(m_, u_, freeze_expected=True):
    """the alarm and proof lines of one update's metrics (u_: the update, = its line number) -> [str]"""
    out = []
    g_ = _dig(m_, ("v14", "in_hand", "g"))
    kl_ = _dig(m_, ("weapon", "kl"))
    if isinstance(g_, (int, float)) and g_ > GAUNTLET_MAX:
        out.append("MAJOR PROBLEM update {}: THE GAUNTLET IS IN HIS HAND {:.1%} of the time in games (over {:.0%}; the failed start held it a "
                   "third of the time)".format(u_, g_, GAUNTLET_MAX))
    if isinstance(kl_, (int, float)) and kl_ > KL_MAX:
        out.append("MAJOR PROBLEM update {}: HIS WEAPON CHOICE MOVES FAST: weapon KL {:.4f} (over {}, three times its normal 0.015; the failed "
                   "start's ran 0.06 to 0.35 before the gauntlet)".format(u_, kl_, KL_MAX))
    hz_ = m_.get("h2_freeze")
    if hz_ is None:
        if freeze_expected:
            out.append("MAJOR PROBLEM update {}: no freeze proof in the metrics (the trainer runs without --h2-freeze / --h2-wsc-freeze?)".format(u_))
        return out
    if hz_.get("record_error"):
        out.append("MAJOR PROBLEM update {}: the freeze proof failed: {}".format(u_, hz_["record_error"]))
        return out
    fc_ = hz_.get("forecast_moved") or {}
    ou_ = hz_.get("outputs_vs_start") or {}
    out.append("update {}: the item picker {} (run update {}, window {}): held parameters {} largest difference to the start {:g} "
               "(its weapon scores {:g}){}; its forecast's last layer moved {:g}; its other parameters moved {:g}; on a fixed batch its goal "
               "scores differ from the start's by {:g}, its weapon scores by {:g}".format(
                   u_, "FROZEN except its forecast's last layer" if hz_.get("on") else "learns (its weapon scores frozen)" if hz_.get("weapon_frozen")
                   else "learns", hz_.get("run_update"), hz_.get("window"), hz_.get("held_n"), float(hz_.get("held_max") or 0.0),
                   float(hz_.get("weapon_max") or 0.0), " (put back: {})".format(hz_.get("moved")) if hz_.get("restored") else "",
                   max([float(v_) for v_ in fc_.values()] or [0.0]), float(hz_.get("free_max") or 0.0), float(ou_.get("target", -1.0)),
                   float(ou_.get("wsc", -1.0))))
    if float(hz_.get("held_max") or 0.0) != 0.0 or hz_.get("moved"):
        out.append("MAJOR PROBLEM update {}: A FROZEN PART OF THE ITEM PICKER MOVED: largest difference {:g} on {} (put back to the start's "
                   "values: {})".format(u_, float(hz_.get("held_max") or 0.0), hz_.get("moved"), bool(hz_.get("restored"))))
    return out


def main():
    p_ = sys.argv[1]
    L_ = [json.loads(x_) for x_ in open(p_, encoding="utf-8") if x_.strip()]
    for u_, m_ in enumerate(L_, 1):
        for l_ in lines(m_, u_, freeze_expected=False):
            print(l_)
        print("update {}: weapon.kl {} gauntlet in hand {}".format(u_, _dig(m_, ("weapon", "kl")), _dig(m_, ("v14", "in_hand", "g"))))


if __name__ == "__main__":
    main()

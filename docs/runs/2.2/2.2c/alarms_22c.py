"""2.2c (from 2.2b's restart, kept: the card "Kept from 2.2b's pay"): the two alarms and the freeze's proof line, read from one metrics.jsonl line.
ramp_22c.py writes them into watch/watch.log every update from update 1; run alone it replays a metrics.jsonl:

    python docs/runs/2.2/2.2c/alarms_22c.py <metrics.jsonl>

THE FIX (the brief, 11-18): 2.2b's speed alarm read weapon.kl, the item picker's credit term on the weapon key, switched off with H2_WPG 0: it
showed 0 all night. It now reads the hands' own: kl_heads[6] (the weapon key's KL of the hands' policy step, HAND_HEAD 6), over KL_MAX = three
times its normal (KL_NORMAL 0.0042: its median over 2.2a's 156 updates; 2.2b's 99: 0.0033, its largest 0.0047).

  (a) the gauntlet in hand (v14.in_hand.g) over GAUNTLET_MAX (0.05): MAJOR
  (b) the weapon choice's speed (kl_heads[6], the hands' own weapon key) over KL_MAX (0.0126, three times its normal 0.0042): MAJOR
  (c) the freeze's proof (h2_freeze, written by the trainer with --h2-freeze / --h2-wsc-freeze): a plain line every update; MAJOR if a held
      parameter of the item picker moved (its largest difference to the start not exactly 0) or the block is missing or failed
"""
import json
import sys

GAUNTLET_MAX = 0.05
KL_NORMAL = 0.0042
KL_MAX = 3 * KL_NORMAL
HAND_HEAD = 6


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
    kh_ = m_.get("kl_heads")
    kl_ = kh_[HAND_HEAD] if isinstance(kh_, list) and len(kh_) > HAND_HEAD else None
    if kl_ is None:
        out.append("MAJOR PROBLEM update {}: no kl_heads in the metrics: the weapon-choice-speed alarm cannot read the hands' weapon key".format(u_))
    if isinstance(g_, (int, float)) and g_ > GAUNTLET_MAX:
        out.append("MAJOR PROBLEM update {}: THE GAUNTLET IS IN HIS HAND {:.1%} of the time in games (over {:.0%}; the failed start held it a "
                   "third of the time)".format(u_, g_, GAUNTLET_MAX))
    if isinstance(kl_, (int, float)) and kl_ > KL_MAX:
        out.append("MAJOR PROBLEM update {}: HIS WEAPON CHOICE MOVES FAST: the hands' weapon-key KL {:.4f} (over {:.4f}, three times its normal "
                   "{}; 2.2b's failed start: the gauntlet followed)".format(u_, kl_, KL_MAX, KL_NORMAL))
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
        kh_ = m_.get("kl_heads") or []
        print("update {}: the hands' weapon-key KL {} gauntlet in hand {}".format(u_, kh_[HAND_HEAD] if len(kh_) > HAND_HEAD else None, _dig(m_, ("v14", "in_hand", "g"))))


if __name__ == "__main__":
    main()

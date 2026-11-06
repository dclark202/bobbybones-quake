"""Will the trainer accept this live.json, and every one its ramp will write? (1.7a's false start, 2026-11-05)

1.7a's ramp wrote the order's gate as -30 into live.json; the trainer refuses any negative number, a refused file is refused
whole, and the run trained 14 updates on its command's start values (the item teacher, the speed pay, the costs back on, no
win pay) in place of 1.6a's end dials. Nothing checked the file against the trainer itself. This tool reads the file with
the trainer's own reader (sim/train_duel_rnn.py live_read, its LIVE_RANGE), and with --ramp the same file with the ramp's
dials at every clock from 0 to the ramp's end, as the ramp would write them. Exit 1 on any refusal.
    python tools/run/live_accept.py <live.json> [--env duel_env_ffa] [--ramp docs/runs/<v>/<run>/ramp_<x>.py]
The ramp module must have DIALS ((name, from, to, value there, at the end, before), ...) and dial_at(clock, lo, hi, v0, v1, pre)."""
import argparse
import importlib
import importlib.util
import json
import os
import sys
import tempfile

ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
sys.path.insert(0, os.path.join(ROOT, "sim"))


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("live")
    ap.add_argument("--env", default="duel_env_ffa")
    ap.add_argument("--ramp", default="")
    a = ap.parse_args()
    import train_duel_rnn as T
    E_ = importlib.import_module(a.env)
    start = {k_: os.environ.get(k_) for k_ in getattr(E_, "LIVE_VARS", ())}
    base = json.load(open(a.live, encoding="utf-8"))
    tstart = {k_: 0.0 for k_ in ("DMG_TAKEN_W", "DMG_REWARD")}

    def read(d):
        fd_, p_ = tempfile.mkstemp(suffix=".json")
        with os.fdopen(fd_, "w", encoding="utf-8") as f_:
            json.dump(d, f_)
        try:
            return T.live_read(p_, E_, start, tstart)[2]
        finally:
            os.unlink(p_)

    bad = []
    why_ = read(base)
    print("the file {}: {}".format(a.live, "accepted" if why_ is None else "REFUSED: " + why_))
    if why_ is not None:
        bad.append(("file", why_))
    if a.ramp:
        spec_ = importlib.util.spec_from_file_location("ramp_", a.ramp)
        R = importlib.util.module_from_spec(spec_)
        spec_.loader.exec_module(R)
        end_ = max(d_[2] for d_ in R.DIALS)
        n_ = 0
        for clock_ in range(0, int(end_) + 2):
            d_ = dict(base)
            for nm_, lo, hi, v0, v1, pre in R.DIALS:
                d_[nm_] = round(R.dial_at(float(clock_), lo, hi, v0, v1, pre), 6)
            w_ = read(d_)
            n_ += 1
            if w_ is not None:
                bad.append((clock_, w_))
        print("the ramp {}: {} files (clocks 0 to {}), {}".format(os.path.basename(a.ramp), n_, int(end_) + 1,
              "all accepted" if not [b_ for b_ in bad if b_[0] != "file"] else "REFUSED at clocks {}".format(
                  sorted({b_[0] for b_ in bad if b_[0] != "file"})[:10])))
    for c_, w_ in bad[:5]:
        print("  refused ({}): {}".format(c_, w_))
    print("LIVE ACCEPT: PASS" if not bad else "LIVE ACCEPT: FAIL")
    sys.exit(1 if bad else 0)


if __name__ == "__main__":
    main()

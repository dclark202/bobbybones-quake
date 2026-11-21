"""2.2b's BUILD.md table of every setting (the coordinator's audit of 11-17): every environment setting and trainer argument of 2.2b's command
(train.cmd with aim2_env.cmd, as tools/run/check_settings.py reads them), its value in the command, the value that plays (the start's live.json
where it sets the name: the simulator's live names and the trainer's live factors), 2.2a's command's value, and whether 2.2b's differs from 2.2a's
as it was written or as it played (2.2a's last live.json). Markdown on stdout.
    python docs/runs/2.2/2.2b/settings_table.py <2.2b train.cmd> <2.2b's start live.json> <2.2a train.cmd> <2.2a's last live.json>"""
import json
import os
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.normpath(os.path.join(HERE, "..", "..", "..", ".."))
sys.path.insert(0, os.path.join(ROOT, "tools", "run"))
sys.path.insert(0, HERE)
import check_settings as CS  # noqa: E402
import start_values as SV  # noqa: E402

ARG_LIVE = {a_: k_ for k_, (a_, how_) in SV.TRAINER.items() if a_}


def fmt(x):
    return "" if x is None else str(x).replace("|", "\\|").replace(ROOT, "%ROOT%")


def main():
    c_b, l_b, c_a, l_a = sys.argv[1:5]
    eb, ab = CS.read_cmd(c_b)
    ea, aa = CS.read_cmd(c_a)
    lb = json.load(open(l_b, encoding="utf-8"))
    la = json.load(open(l_a, encoding="utf-8"))
    rows = []
    for kind_, B, A in (("set", eb, ea), ("arg", ab, aa)):
        for n_ in sorted(set(B) | set(A)):
            vb, va = B.get(n_), A.get(n_)
            ln_ = n_ if kind_ == "set" else ARG_LIVE.get(n_)
            pb = lb.get(ln_) if ln_ and ln_ in lb else vb
            pa = la.get(ln_) if ln_ and ln_ in la else va
            wr_ = not CS.same(vb, va) if (vb is not None and va is not None) else (vb != va)
            try:
                pl_ = abs(float(pb) - float(pa)) > 1e-9
            except (TypeError, ValueError):
                pl_ = fmt(pb) != fmt(pa)
            rows.append((kind_, n_, fmt(vb if vb is not None else "(unset)"), fmt(pb if pb is not None else "(unset)") + (" (live)" if ln_ in lb else ""),
                         fmt(va if va is not None else "(unset)"), fmt(pa if pa is not None else "(unset)") + (" (live)" if ln_ in la else ""),
                         "**yes**" if pl_ else ("written only" if wr_ else "")))
    for k_ in sorted(set(lb) | set(la)):                      # (live names the command does not name: the trainer's own factors)
        if not any(r_[1] == k_ for r_ in rows) and not any(ARG_LIVE.get(r_[1]) == k_ for r_ in rows):
            pl_ = fmt(lb.get(k_)) != fmt(la.get(k_))
            rows.append(("live", k_, "", fmt(lb.get(k_, "(not in the file)")), "", fmt(la.get(k_, "(not in the file)")), "**yes**" if pl_ else ""))
    print("| | name | 2.2b's command | plays in 2.2b | 2.2a's command | played in 2.2a (its last live.json) | differs |")
    print("|---|---|---|---|---|---|---|")
    for r_ in rows:
        print("| " + " | ".join(r_) + " |")
    n_ = sum(1 for r_ in rows if r_[6] == "**yes**")
    print("\n{} names; {} play differently from 2.2a's last values; {} differ only as written (2.2a's live file had them at 2.2b's value)".format(
        len(rows), n_, sum(1 for r_ in rows if r_[6] == "written only")))


if __name__ == "__main__":
    main()

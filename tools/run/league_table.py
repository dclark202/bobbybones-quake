"""(1.4b, B-300; owner 2026-11-03: the league table in every hourly line and report) print the league table: by league file, the training
slices against it, his frags for and against and his frag share, the decayed share the draw uses, the win chance gained (the judge's unit: a
frag at 0:0 with ten minutes left is 1) a slice. --run keeps a run's own snapshots and the anchors; --line prints one line for the hourly report.
    python tools/run/league_table.py [--run duel_gru_1_4b] [--line] [--table data/sim_runs/league_table.json]"""
import argparse
import json
import os
import sys

ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
sys.path.insert(0, os.path.join(ROOT, "sim"))
import league  # noqa: E402


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--table", default=os.path.join(ROOT, "data", "sim_runs", "league_table.json"))
    ap.add_argument("--run", default="")
    ap.add_argument("--line", action="store_true")
    a = ap.parse_args()
    L = league.League(a.table, a.run)
    rows = []
    for n, e in L.tab.items():
        if a.run and "/" in n and not n.startswith(a.run + "/"):
            continue
        if a.run and a.run not in e.get("runs", []):
            continue
        f_, g_ = e["frags_for"], e["frags_against"]
        rows.append((n, e["slices"], f_, g_, f_ / max(1, f_ + g_), L.p(n), e["win_gained"] / max(1, e["slices"])))
    rows.sort(key=lambda r: (not r[0].startswith("anchor_"), r[0]))
    if a.line:
        an_ = [r for r in rows if r[0].startswith("anchor_")]
        sn_ = [r for r in rows if not r[0].startswith("anchor_")]
        f_, g_ = sum(r[2] for r in sn_), sum(r[3] for r in sn_)
        print("league: " + " | ".join("{} {:.0%} ({}-{}, win {:+.2f})".format(r[0].replace("anchor_", "").replace(".pt", ""), r[4], r[2], r[3], r[6]) for r in an_)
              + " | snapshots {:.0%} ({}-{}, {} files)".format(f_ / max(1, f_ + g_), f_, g_, len(sn_)))
        return
    print("{:42s} {:>6s} {:>6s} {:>6s} {:>7s} {:>7s} {:>9s}".format("file", "slices", "for", "agst", "share", "draw p", "win/slc"))
    for r in rows:
        print("{:42s} {:6d} {:6d} {:6d} {:7.1%} {:7.1%} {:+9.3f}".format(*r))


if __name__ == "__main__":
    main()

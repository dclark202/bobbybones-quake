"""v0.4.0 brain: the readout's zones and its speed and direction, read from a run's metrics.jsonl (the trainer's track block,
--track-z): the zones' readiness numbers by time unseen, summed over the last N updates.

    python tools/zones_report.py <run> [--last 20] [--maps]

By time unseen (in view, 0-2 s, 2-5 s, 5-10 s, 10 s+, since the enemy's spawn): the zone right first and in the first two;
three bars: the zone of the readout's own place, the zone he last saw the enemy in, the map's commonest zone so far; the
zones' nll beside the map prior's; the calibration's mean gap; on frames where the place is 600 units or more off, the first
two zones right against the place's zone. Then the calibration table (every zone's odds in ten bins against how often it was
the zone), by map (--maps), and the speed and direction against the old velocity part.
"""
import argparse
import json
import os

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
BINS = ("in_view", "0-2s", "2-5s", "5-10s", "10s+", "unseen_since_spawn")


def wavg(rows, key, wkey):
    n = sum(r.get(wkey, 0) for r in rows if key in r)
    return (sum(r[key] * r.get(wkey, 0) for r in rows if key in r) / n) if n else float("nan"), n


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("run")
    ap.add_argument("--last", type=int, default=20)
    ap.add_argument("--maps", action="store_true")
    a = ap.parse_args()
    recs = []
    for line in open(os.path.join(ROOT, "data", "sim_runs", a.run, "metrics.jsonl"), encoding="utf-8"):
        try:
            r = json.loads(line)
        except ValueError:
            continue
        z = (((r.get("track") or {}).get("rollout") or {}).get("z"))
        if z:
            recs.append((r.get("update"), r.get("track", {}), z))
    recs = recs[-a.last:]
    if not recs:
        raise SystemExit("no track.rollout.z in {} (a run with --track-z and TRACK_Z=1)".format(a.run))
    print("{}: updates {} .. {} ({} records)".format(a.run, recs[0][0], recs[-1][0], len(recs)))
    ls = [t.get("z_loss") for _, t, _ in recs if t.get("z_loss")]
    if ls:
        print("lesson (first, last): " + "  ".join("{} {:.3f} -> {:.3f}".format(k, ls[0][k], ls[-1][k]) for k in ls[0]))
    print("{:20s} {:>7s} {:>6s} {:>6s} | {:>6s} {:>6s} {:>6s} | {:>6s} {:>6s} | {:>5s} | {:>6s} {:>6s} {:>6s}".format(
        "zones by time unseen", "frames", "top1", "top2", "point", "seen", "prior", "nll", "pr.nll", "gap", "far n", "f.top2", "f.pt"))
    for b in BINS:
        rows = [z[b] for _, _, z in recs if b in z and "zone_frames" in z[b]]
        if not rows:
            continue
        g = lambda k, w="zone_frames": wavg(rows, k, w)[0]
        fn = sum(r.get("far_frames", 0) for r in rows)
        print("{:20s} {:7d} {:6.3f} {:6.3f} | {:6.3f} {:6.3f} {:6.3f} | {:6.3f} {:6.3f} | {:5.3f} | {:6d} {:6.3f} {:6.3f}".format(
            b, sum(r["zone_frames"] for r in rows), g("zone_top1"), g("zone_top2"), g("point_zone"), g("seen_zone", "seen_frames"), g("prior_top1"),
            g("zone_nll"), g("prior_nll"), g("calib_gap"), fn, g("far_top2", "far_frames"), g("far_point_zone", "far_frames")))
    print("  (point: the zone of the readout's own place; seen: the zone he last saw the enemy in, where he has seen him this life;"
          " prior: the map's commonest; far: the place 600 u or more off)")
    n = [0] * 10
    p = [0.0] * 10
    h = [0.0] * 10
    for _, _, z in recs:
        c = z.get("calib")
        if c:
            for i in range(10):
                n[i] += c["n"][i]
                p[i] += c["p"][i] * c["n"][i]
                h[i] += c["hit"][i] * c["n"][i]
    print("calibration (the zones' odds in ten bins -> how often it was the zone): " + "  ".join(
        "{:.2f}->{:.2f} ({})".format(p[i] / n[i], h[i] / n[i], n[i]) for i in range(10) if n[i]))
    print("  mean gap {:.4f}".format(sum(abs(p[i] - h[i]) for i in range(10)) / max(1, sum(n))))
    print("{:20s} {:>7s} {:>7s} {:>7s} {:>7s} {:>8s} {:>8s} {:>8s}".format("speed, direction", "spd err", "spd nll", "dir err", "dir nll",
                                                                             "polar", "old vel", "old win"))
    for b in BINS:
        rows = [z[b] for _, _, z in recs if b in z]
        if not rows:
            continue
        g = lambda k, w="frames": wavg(rows, k, w)[0]
        print("{:20s} {:7.1f} {:7.3f} {:7.1f} {:7.3f} {:8.3f} {:8.3f} {:8.3f}".format(b, g("spd_err_med"), g("spd_nll"), g("dir_err_med", "dir_frames"),
                                                                                    g("dir_nll", "dir_frames"), g("polar_nll"), g("vel_old_nll"), g("vel_old_nll_win")))
    print("  (errors: medians averaged over updates, units a second and degrees; polar: the new parts as one density over the "
          "velocity (nats, per (u/s)^2) against the old velocity part's on its own truth and on the 0.2 s mean)")
    if a.maps:
        maps = sorted({m for _, _, z in recs for m in z.get("by_map", {})})
        print("{:15s} {:>7s} {:>6s} {:>6s} {:>6s} {:>6s} {:>6s} {:>6s} {:>6s}".format("by map", "frames", "top1", "top2", "point", "seen", "prior", "nll", "pr.nll"))
        for m in maps:
            rows = [z["by_map"][m] for _, _, z in recs if m in z.get("by_map", {})]
            g = lambda k: wavg(rows, k, "frames")[0]
            print("{:15s} {:7d} {:6.3f} {:6.3f} {:6.3f} {:6.3f} {:6.3f} {:6.3f} {:6.3f}".format(
                m, sum(r["frames"] for r in rows), g("top1"), g("top2"), g("point_zone"), g("seen_zone"), g("prior_top1"), g("nll"), g("prior_nll")))


if __name__ == "__main__":
    main()

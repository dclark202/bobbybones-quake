"""Hourly report line(s) for an arena run: the last few lines of the training log, compact."""
import re
import sys

run = sys.argv[1] if len(sys.argv) > 1 else "duel_gru_v5"
ls = [l for l in open("data/sim_runs/{}.log".format(run), encoding="utf-8", errors="replace") if l.startswith("update=")]
st = max(i for i, l in enumerate(ls) if l.startswith("update=1 "))
ls = ls[st:]
for l in ls[:: max(1, len(ls) // 5)][-5:] + [ls[-1]]:
    g = lambda k: (re.search(k + r"=([^ ]+)", l) or [0, ""])[1]
    d = lambda k: (re.search(k + r"=(\{[^}]*\})", l) or [0, ""])[1]
    print("upd", g("update"), "min", g("minutes"), "sps", g("sps"), "aim_err", g("aim_err_visible"), "on_target", g("on_target_visible"),
          "jerk", g("jerk"), "switches/min", g("switches_per_min"), "fire", g("fire"), "entropy", g("entropy"), "vs_snapshots", g("vs_snapshot_kill_share"))
    print("   arena", d("arena"))
    print("   keys", d("keys"), "| hit", d("hit_rate"))
    print("   frags", d("frag_share"))
    if d("yard"):
        print("   map", d("yard"), "| pickups", d("pickups_per_player_min"))

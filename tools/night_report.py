"""One compact report from the last line of a training log plus the benchmark and duel-speed lines of an hourly
check (the output file of the check is given as the argument, or a log file alone)."""
import re
import sys

text = open(sys.argv[1], encoding="utf-8", errors="replace").read().splitlines()
ups = [l for l in text if l.startswith("update=")]
for l in text:
    if l.startswith("BENCH") or "speed mean" in l or re.match(r"^\d\d:\d\d$", l) or re.match(r"^\d+$", l):
        print(l[:300])
if ups:
    l = ups[-1]
    g = lambda k: (re.search(k + r"=([^ ]+)", l) or [0, ""])[1]
    c = lambda k: (re.search(r"'%s': \{'speed': (\d+), 'finishes_per_min': ([0-9.]+)" % k, l) or [0, "", ""])
    print("upd", g("update"), "min", g("minutes"), "sps", g("sps"), "hit rl/rg/lg",
          re.search(r"hit_rate=\{'rl': ([0-9.]+), 'rg': ([0-9.]+), 'lg': ([0-9.]+)", l).groups(), "aim_err", g("aim_err_visible"),
          "on_target", g("on_target_visible"), "crouch", g("crouch"), "walk", g("walk"), "air_fast", g("air_fast"),
          "frags/min", g("frags_per_match_min"), "keys", re.search(r"keys_right': ([0-9.]+)", l).group(1))
    print("  courses (speed, finishes/min)", {k: (c(k)[1], c(k)[2]) for k in
          ("speed", "circle", "twohop", "ramps", "slalom", "turns", "narrow", "pillars", "rocket", "bends", "pads", "drops", "climb")})
    print("  items", re.search(r"items_room=\{[^}]*\}", l).group(0)[11:], "frag_share", re.search(r"frag_share=\{[^}]*\}", l).group(0)[11:])

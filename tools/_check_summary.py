"""compact summary of one tools/hourly_arena1.sh output (used for the overnight reports)"""
import re, sys
t = open(sys.argv[1], encoding="utf-8", errors="replace").read()
u = [l for l in t.splitlines() if l.startswith("upd")][-1]
g = lambda k, s=t: (re.findall(k + r"'?:? ?=?([-0-9.]+)", s) or ["?"])[-1]
ar = [l for l in t.splitlines() if l.startswith("ARENA")]
print("min", re.search(r"min ([0-9.]+)", u).group(1), "| frags/min", g("frags_per_min"), "in_view", g("in_view"), "speed", g("'speed'"),
      "fire", re.search(r"fire ([0-9.]+)", u).group(1), "| hit rl", g("'rl'", t[t.rfind("hit {"):]), "rg", g("'rg'", t[t.rfind("hit {"):]),
      "lg", g("'lg'", t[t.rfind("hit {"):]), "mg", g("'mg'", t[t.rfind("hit {"):]))
print("mega/min", g("mega_per_player_min"), "lay", g("mega_lay_s"), "| red/min", g("red_armor_per_player_min"), "lay", g("red_armor_lay_s"),
      "| first weapon", g("first_weapon_s"), "| void", g("void_deaths_per_player_min"), "lava", g("lava_dmg_per_player_min"), "| keys asked", g("asked_per_s"))
print("frags", t[t.rfind("frags {"):].splitlines()[0][:110])
print(ar[-1][:230] if ar else "no Nightmare line")
for k in ("share of time on it", "lightning damage", "on it after", "first shot"):
    for l in [l for l in t.splitlines() if k in l][:2]:
        print("  ", l[:50].strip(), "|", " ".join(l[50:].split()))
f = [l for l in t.splitlines() if l.startswith("fight")]
print(f[-1][:200] if f else "", "| python procs", t.strip().splitlines()[-2] if "exited" in t.strip().splitlines()[-1] else t.strip().splitlines()[-1])

"""(1.4b, 2026-11-04; 1.4c's start.ps1 as 1.4b's) the start save's live dials that are not in the command (CONTACT_FREE, LEVEL_PULL, RAIL_FAR_PAY: set by
live.json in 1.3b) must be in the run's copied live.json at the save's own values: the settings check against the save allows them only so.
    python live_check.py <save.pt> <live.json>"""
import json
import sys

import torch

ev = torch.load(sys.argv[1], map_location="cpu", weights_only=False).get("env_vars") or {}
d = json.load(open(sys.argv[2], encoding="utf-8"))
bad = {k: (ev.get(k), d.get(k)) for k in ("CONTACT_FREE", "LEVEL_PULL", "RAIL_FAR_PAY")
       if ev.get(k) is None or d.get(k) is None or abs(float(ev[k]) - float(d[k])) > 1e-9}
print("live.json carries the save's live dials" if not bad else "live.json differs from the save (save, live.json): " + str(bad))
sys.exit(1 if bad else 0)

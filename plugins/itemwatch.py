"""itemwatch: every ITEMWATCH_SECS seconds (default 10) the item entities of the running game are written down
(entity number, class, place, there or not, milliseconds until back): to check what another plugin did to the items
(plugins/powerups.py: no powerups, the items of a duel in every mode) and that items it put there come back after they
are taken. Load beside the playing plugins: QLX_PLUGINS="botctl, botmode, ffabot, itemwatch".
Writes /tmp/practice/itemwatch.jsonl."""
import json
import os
import time

import minqlx

D = "/tmp/practice"
SECS = float(os.environ.get("ITEMWATCH_SECS", "10"))


class itemwatch(minqlx.Plugin):
    def __init__(self):
        self.add_hook("frame", self.on_frame)
        self.next = 0.0

    def on_frame(self):
        now = time.time()
        if now < self.next:
            return
        self.next = now + SECS
        try:
            t_ms, items = minqlx.item_states()
            row = dict(t=round(now, 1), map=(minqlx.get_cvar("mapname") or "").lower(), factory=minqlx.get_cvar("g_factory"),
                       state=self.game.state if self.game is not None else None, level_ms=int(t_ms),
                       powerup_switch=minqlx.get_cvar("g_spawnItemPowerup"),
                       items=[[int(n), c, round(float(x), 1), round(float(y), 1), round(float(z), 1), int(bool(up)), int(b - t_ms)]
                              for n, c, x, y, z, up, b in items])
            with open(os.path.join(D, "itemwatch.jsonl"), "a") as f:
                f.write(json.dumps(row) + "\n")
        except Exception:                                    # noqa: BLE001
            pass

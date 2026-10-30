"""Offline check of the game history's server side (no game server): plugins/ladder.py's !anonymous, its duels line with
the game's start, its welcome and end lines; tools/board_merge.py's anonymous list and history; the chat rules.
    python tools/history_check.py      (exit 0: all passed)"""
import json
import os
import re
import shutil
import sys
import tempfile
import time
import types

HERE = os.path.dirname(os.path.abspath(__file__))
TMP = tempfile.mkdtemp(prefix="history_check_")
os.environ["LADDER_DIR"] = TMP
os.environ["LADDER_SRV"] = "us"
os.environ.pop("QLSTATS", None)

fake = types.ModuleType("minqlx")


class _Plugin:
    _loaded_plugins = {}

    def __init__(self):
        pass

    def add_hook(self, *a, **k):
        pass

    def add_command(self, *a, **k):
        pass

    def players(self):
        return []


fake.Plugin, fake.RET_STOP_ALL, fake.RET_USAGE = _Plugin, 2, 1
fake.console_print = lambda *a: None
fake.get_cvar = lambda name: {"mapname": "campgrounds", "timelimit": "10"}.get(name, "")
fake.thread = lambda f: f
fake.next_frame = lambda f: f
fake.delay = lambda t: (lambda f: f)
sys.modules["minqlx"] = fake
sys.path.insert(0, os.path.join(HERE, "..", "plugins"))
sys.path.insert(0, HERE)
import ladder as L                                           # noqa: E402
import ratings as R                                          # noqa: E402
import board_merge as BM                                     # noqa: E402

fails = []


def check(ok, what):
    print(("ok   " if ok else "FAIL ") + what)
    if not ok:
        fails.append(what)


class Who:
    def __init__(self, sid, name="tester"):
        self.steam_id, self.clean_name, self.name, self.id = sid, name, name, 3
        self.told = []

    def tell(self, s):
        self.told.append(s)


lad = L.ladder()
lad.is_owner = lambda p: False
L.is_bot = lambda p: False
person = Who(1000000000000001)                               # (a made-up id)
key = lad.key(person)

# !anonymous, !anonymous off
lad.cmd_anonymous(person, ["!anonymous"], None)
pj = json.load(open(os.path.join(TMP, "private.json")))
check(pj["keys"][key]["on"] == 1, "!anonymous writes the key as anonymous")
check(str(person.steam_id) not in open(os.path.join(TMP, "private.json")).read(), "private.json holds no Steam id")
time.sleep(0.2)
lad.cmd_anonymous(person, ["!anonymous", "off"], None)
check(json.load(open(os.path.join(TMP, "private.json")))["keys"][key]["on"] == 0, "!anonymous off undoes it")
lad.cmd_anonymous(person, ["!private"], None)
check(json.load(open(os.path.join(TMP, "private.json")))["keys"][key]["on"] == 1, "!private (alias) works")

# the newest word counts across servers
eu = tempfile.mkdtemp(prefix="history_check_eu_")
json.dump(dict(keys={key: dict(on=0, t=time.time() + 5), "other": dict(on=1, t=1.0)}), open(os.path.join(eu, "private.json"), "w"))
pk = BM.private_keys([("us", TMP), ("eu", eu)])
check(key not in pk and "other" in pk, "the newest word of a person counts on both servers")

# the duels line carries the game's start; the id
lad.bot_plugin = lambda: types.SimpleNamespace(P={"run": "duel_gru_v0_4_1"}, aim_level=lambda: 4)
t_end = time.time()
lad.note_duel(key, 0, 10.0, 7, 12, False, "game", net="duel_gru_v0_4_1", t0=t_end - 600.0)
d = json.loads(open(os.path.join(TMP, "duels.jsonl")).read().splitlines()[-1])
check(abs(d["t0"] - (t_end - 600.0)) < 0.02 and d["srv"] == "us", "duels line: t0 and srv")
gid = R.game_id(d, "us")
check(re.match(r"^us-\d{8}-\d{6}-campgrounds$", gid) is not None, "game id " + gid)
d2 = dict(d)
d2.pop("t0")
check(abs(R.game_t0(d2) - R.game_t0(d)) < 1.0, "an old line (no t0) gives the start from its end and minutes")

# the end line and the welcome
lad.report_t = time.time()
check(lad.report_lines() == [lad.REPORT_LINE], "the report line after a recorded game")
lad.report_t = time.time() - 60
check(lad.report_lines() == [], "no report line long after a game")
lad.board = {"players": {}}
lad.record_line = lambda: ""
wl = lad.welcome_lines(person)
check(lad.HISTORY_LINE in wl, "the welcome names the history and !anonymous")
for s_ in (lad.REPORT_LINE, lad.HISTORY_LINE, lad.PAGE_LINE) + tuple(person.told):
    check(not re.search(r"%[A-Za-z]", s_) and '"' not in s_ and ";" not in s_, "chat rules: " + re.sub(r"\^\d", "", s_)[:70])
check(all(len(re.sub(r"\^\d", "", x)) < 120 for x in (lad.REPORT_LINE, lad.HISTORY_LINE) + tuple(person.told)),
      "every line short enough for one chat line")

# the history: ratings after and their change, a private person anonymous
frags = [dict(t=t_end - 500 + i, map="campgrounds", killer=key if i % 3 else R.BOT + "duel_gru_v0_4_1",
              victim=R.BOT + "duel_gru_v0_4_1" if i % 3 else key) for i in range(30)]
rows = BM.game_history(frags, [d], {key: "tester"}, {key}, now=time.time())
check(len(rows) == 1 and rows[0]["name"] is None and rows[0]["id"] == gid, "history row: anonymous, its id")
check(rows[0]["dr"][0] == rows[0]["r"][0] - 1500 and rows[0]["dr"][0] > 0, "history row: change over the game from 1500")
rows = BM.game_history(frags, [d], {key: "tester"}, set(), now=time.time())
check(rows[0]["name"] == "tester", "history row: named when not anonymous")
check(rows[0]["who"] == R.page_id(key) and key not in R.page_id(key), "history row: the person's page, not the key")
check(BM.game_history(frags, [d], {key: "tester"}, {key}, now=time.time())[0]["who"] is None, "history row: no page after !anonymous")
check(not BM.game_history(frags, [d], {}, set(), now=time.time() + 181 * 86400), "a game older than 180 days leaves the history")

shutil.rmtree(TMP, ignore_errors=True)
shutil.rmtree(eu, ignore_errors=True)
print("{} failed".format(len(fails)) if fails else "all passed")
sys.exit(1 if fails else 0)

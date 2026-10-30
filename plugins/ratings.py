"""The leaderboard's arithmetic and its file. Not a plugin: plugins/ladder.py keeps it on a server, tools/elo.py reads it
on the PC.

What counts: every frag between a person and BobbyBones, either way, in a live game (owner, 2026-10-26: "ladder should be
actual games only"; until then warmup frags counted too: rated() below; the frag lines still record warmup frags). Frags
between two people, between two Bobbys, by the game's own bots, and deaths by one's own hand or the map are not counted.

Each counted frag is a game won by the one who made it. Ratings are Glicko-1 (Glickman 1999), updated at every frag: a
number, and how unsure it is (RD). A difference of d points means the higher one makes 1 / (1 + 10^(-d/400)) of the
frags between the two: 100 points is 64%, 200 is 76%, 400 is 91%. Frags come in streaks (a stack, a spawn, a held
position), so one frag counts as a quarter of a game (W): a new player's first frag moves him about 70 points, not 175,
and it takes about 200 frags, not 50, until the table is as sure of him as it gets. The unsure one moves more: a new
network of Bobby starts at the last one's number with RD 150, so that it is Bobby's number that moves when he has got
better or worse, not the people's.

Every person meets only Bobby here, so a person's number says how he does against Bobby, and Bobby's says how he does
against the people who come.

One board for several servers (owner, 2026-10-23: the US and EU servers share one board). Each server only appends to its
own frags.jsonl and duels.jsonl (a line carries "srv": the server's name). tools/board_merge.py, run every few minutes on
one server, reads every server's files, takes each frag once (a frag is its time, killer and victim: the history the
servers started from is in every copy) and works the table out again from all frags in time order: board.json, which
it gives to every server with "upto", how far into each server's own files it read. A server's plugin plays on that
board plus its own lines after "upto" (read_tail, replay); it never writes board.json. The functions for both are here.
"""
import hashlib
import json
import math
import os
import re
import time

Q = math.log(10.0) / 400.0
R0, RD0 = 1500.0, 350.0          # where everybody starts, and how unsure
RD_MIN = 50.0                    # never surer than this (people get better, and so does he)
W = 0.25                         # a frag is this much of a game: frags come in streaks
RD_NEW_NET = 150.0               # a new network of Bobby: the last one's number, this unsure
C_DAY = 35.0                     # away for a while: RD grows to sqrt(RD^2 + C_DAY^2 * days)
MIN_FRAGS = 20                   # frags with Bobby (made and taken) before a person has a rank
BOT = "bobby:"                   # Bobby's keys: bobby:<the network's run>


def g(rd):
    return 1.0 / math.sqrt(1.0 + 3.0 * Q * Q * rd * rd / (math.pi * math.pi))


def expect(r, r_j, rd_j):
    """the share of the frags the one rated r is expected to make against the one rated r_j"""
    return 1.0 / (1.0 + 10.0 ** (-g(rd_j) * (r - r_j) / 400.0))


def update(r, rd, r_j, rd_j, s):
    """one game against (r_j, rd_j) with result s (1 won, 0 lost): the new number and RD"""
    e, gj = expect(r, r_j, rd_j), g(rd_j)
    v = 1.0 / (1.0 / (rd * rd) + W * Q * Q * gj * gj * e * (1.0 - e))
    return r + W * Q * v * gj * (s - e), max(RD_MIN, math.sqrt(v))


def label(run):
    """duel_gru_v13 -> v13"""
    return str(run).replace("duel_gru_", "")


class Table:
    def __init__(self, path=None):
        self.path = path
        self.players = {}        # key -> dict(name, r, rd, won, lost, t, since, bot)
        self.dirty = False
        if path and os.path.exists(path):
            try:
                self.players = json.load(open(path, encoding="utf-8"))["players"]
            except Exception:                                # noqa: BLE001 - a broken file is set aside, not written over
                os.replace(path, path + ".broken-{}".format(int(time.time())))

    def save(self):
        if not self.path or not self.dirty:
            return
        tmp = self.path + ".tmp"
        with open(tmp, "w", encoding="utf-8") as f:
            json.dump(dict(schema=1, saved=round(time.time(), 1), players=self.players), f, indent=1, ensure_ascii=False)
        os.replace(tmp, self.path)
        self.dirty = False

    def entry(self, key, name, now=None):
        """a player's row, made at his first frag; a new network of Bobby takes over the last one's number"""
        now = time.time() if now is None else now
        e = self.players.get(key)
        if e is None:
            r, rd = R0, RD0
            if key.startswith(BOT):
                last = max((p for k, p in self.players.items() if k.startswith(BOT)), key=lambda p: p["t"], default=None)
                if last is not None:
                    r, rd = last["r"], max(last["rd"], RD_NEW_NET)
            e = self.players[key] = dict(name=name, r=r, rd=rd, won=0, lost=0, t=now, since=now, bot=key.startswith(BOT))
        else:
            e["name"] = name
            days = max(0.0, (now - e["t"]) / 86400.0)
            e["rd"] = min(RD0, math.sqrt(e["rd"] ** 2 + C_DAY * C_DAY * days))
        return e

    def frag(self, killer, killer_name, victim, victim_name, now=None):
        """one counted frag; returns the two rows after it"""
        now = time.time() if now is None else now
        a, b = self.entry(killer, killer_name, now), self.entry(victim, victim_name, now)
        (ra, rda), (rb, rdb) = update(a["r"], a["rd"], b["r"], b["rd"], 1.0), update(b["r"], b["rd"], a["r"], a["rd"], 0.0)
        a.update(r=ra, rd=rda, won=a["won"] + 1, t=now)
        b.update(r=rb, rd=rdb, lost=b["lost"] + 1, t=now)
        self.dirty = True
        return a, b

    def board(self, bobby=None):
        """the ranked rows, best first: people with MIN_FRAGS frags or more, and Bobby's current network (key `bobby`;
        his earlier networks keep their rows in the file and are not ranked)"""
        rows = [(k, p) for k, p in self.players.items()
                if (k == bobby) or (not k.startswith(BOT) and p["won"] + p["lost"] >= MIN_FRAGS)]
        return sorted(rows, key=lambda kp: -kp[1]["r"])

    def rank(self, key, bobby=None):
        """(rank, of how many) on the board, or (None, of how many) for somebody not ranked yet"""
        rows = self.board(bobby)
        for n, (k, p) in enumerate(rows, 1):
            if k == key:
                return n, len(rows)
        return None, len(rows)

    def earlier(self, bobby):
        """Bobby's networks before the current one, newest first"""
        return sorted(((k, p) for k, p in self.players.items() if k.startswith(BOT) and k != bobby), key=lambda kp: -kp[1]["t"])


# ---------------------------------------------------------------------- the shared board (several servers, one table)
BOARD_SCHEMA = 1


def version_of(net):
    """the docs' version name of a run (as sim/export_duel.py: duel_gru_v0_3_1b -> v0.3.1, duel_gru_v15c -> v0.1)"""
    m = re.match(r"duel_gru_v(\d+(?:_\d+)+)[a-z]?$", str(net))
    return "v" + m.group(1).replace("_", ".") if m else "v0.1" if net == "duel_gru_v15c" else str(net)


FORFEIT_WIN_MIN = 5.0                                  # minutes (owner, 2026-10-24)


def duel_result(d):
    """a duels.jsonl line as Bobby's result: 0 won, 1 lost, 2 drawn; None for a line that does not count (a timed duel or
    a forfeit: the record is of full games, owner 2026-10-16). A forfeit after more than FORFEIT_WIN_MIN minutes with Bobby
    ahead is his win (owner, 2026-10-24: "if someone quits a duel and they are behind they are forfeiting ... treat it as a win")"""
    try:
        if d.get("kind") != "game":
            return None
        p_, b_ = d["score"]
        if d.get("forfeit"):
            if not (b_ > p_ and float(d.get("minutes") or 0.0) > FORFEIT_WIN_MIN):
                return None
        return 0 if b_ > p_ else 1 if b_ < p_ else 2
    except (KeyError, TypeError, ValueError):
        return None


def game_t0(d):
    """a duels.jsonl line's game start (unix time): its "t0" (from 2026-10-25), else its end less the minutes played"""
    try:
        if d.get("t0"):
            return float(d["t0"])
        return float(d["t"]) - 60.0 * float(d.get("minutes") or 0.0)
    except (TypeError, ValueError):
        return 0.0


def page_id(key):
    """a person's page on the site: a code worked out from the anonymous key, so a new name keeps the page and the key
    itself does not leave"""
    return hashlib.sha256(("bobbybones-page:" + str(key)).encode("utf-8")).hexdigest()[:12]


def game_id(d, srv):
    """a finished game's id on the site (owner, 2026-10-25: "each game gets a unique id ... so it can be tracked"):
    <server>-<UTC start yyyymmdd-hhmmss>-<map>, e.g. us-20261025-143207-campgrounds. Worked out from the line alone, the
    same on every machine; one server plays one game at a time, so two games never share it."""
    return "{}-{}-{}".format(srv or "x", time.strftime("%Y%m%d-%H%M%S", time.gmtime(int(game_t0(d)))),
                             re.sub(r"[^a-z0-9]", "", str(d.get("map") or "map").lower()) or "map")


def read_tail(path, offset=0):
    """the complete lines of a jsonl file from a byte offset on: (parsed lines, the offset after the last complete line).
    A last line still being written (no newline yet) is left for the next read; a line that does not parse is skipped.
    An offset past the file's end (the file was replaced) reads nothing."""
    out = []
    try:
        with open(path, "rb") as f:
            f.seek(0, 2)
            size = f.tell()
            if offset > size:
                return out, offset
            f.seek(offset)
            data = f.read()
    except OSError:
        return out, offset
    end = data.rfind(b"\n") + 1
    for raw in data[:end].splitlines():
        try:
            d = json.loads(raw.decode("utf-8"))
        except (ValueError, UnicodeDecodeError):
            continue
        if isinstance(d, dict):
            out.append(d)
    return out, offset + end


def rated(f):
    """a frag line that moves the ratings: one in a live game (owner, 2026-10-26: "ladder should be actual games only")"""
    return (f.get("state") or "in_progress") == "in_progress"


def replay(table, frags, names=None):
    """apply frag lines (in their order) to a table: the same arithmetic as the live plugin. names: key -> name (the rows'
    names otherwise stay as they are; a new row is named by its key until a name is known)"""
    names = names or {}
    for f in frags:
        if not rated(f):
            continue
        try:
            k, v, t = f["killer"], f["victim"], float(f["t"])
        except (KeyError, TypeError, ValueError):
            continue
        nk = names.get(k) or table.players.get(k, {}).get("name") or k
        nv = names.get(v) or table.players.get(v, {}).get("name") or v
        a, b = table.frag(k, nk, v, nv, t)
        if f.get("owner"):
            (b if a.get("bot") else a)["owner"] = True
    return table


def load_board(path):
    """a board.json written by tools/board_merge.py, or None (missing, broken or of another schema)"""
    try:
        with open(path, encoding="utf-8") as f:
            b = json.load(f)
        if isinstance(b, dict) and b.get("schema") == BOARD_SCHEMA and isinstance(b.get("players"), dict):
            return b
    except Exception:                                        # noqa: BLE001 - a broken file is no board: the last one stays
        pass
    return None

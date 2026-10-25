"""board_merge.py: one leaderboard from several servers' files (owner, 2026-10-23: the US and EU servers share one board).

    python3 tools/board_merge.py --server us=<folder> --server eu=<folder> --out board.json
        [--history us] [--prev board.json] [--merged <folder>]

Each <folder> holds a server's frags.jsonl, duels.jsonl and ratings.json as plugins/ladder.py writes them (a copy is fine).
Every frag is taken once: a frag is its time, killer and victim, so the history that every server started from (the same
lines in every copy) counts once. A line's server is its "srv"; a line without one is the --history server's when it is
in more than one copy (the common history: the old Chicago server), else the server whose file it is in. The table is
worked out again from nothing, all frags in time order (plugins/ratings.py: replay), so the result does not depend on
when or how often this runs. Names: the name on the newest row for a key among the servers' ratings.json and the last
board (frag lines carry keys only).

board.json (plugins/ratings.py BOARD_SCHEMA): {schema, saved, n_frags, n_duels, upto: {server: {frags, duels}} (the byte
offset of the last complete line read in each server's files: a server plays on the board plus its own lines after it),
players (as ratings.json), duels: {"all" | version: [Bobby won, lost, drawn]} (full games, no forfeits), people: {key:
{frags: {server: [made, taken]}, duels: {server: [won, lost, drawn]}}} (the person's side), bobby: Bobby's current key}.
Keys are anonymous (plugins/ladder.py key()); no Steam id is in any of these files.

Safety: a board with fewer frags than --prev is not written (a copy that went missing or short must not shrink the
board); exit 2 then. --merged writes the merged frags.jsonl and duels.jsonl (every line once, "srv" filled in, time
order) for the PC's tools. Writes are atomic (a temporary file, then a rename).
"""
import argparse
import collections
import json
import os
import sys
import time

HERE = os.path.dirname(os.path.abspath(__file__))
for p_ in (HERE, os.path.join(os.path.dirname(HERE), "plugins")):      # (a copy beside ratings.py, or the repo's tools/)
    if os.path.exists(os.path.join(p_, "ratings.py")):
        sys.path.insert(0, p_)
        break
import ratings as R  # noqa: E402


def write_atomic(path, text):
    tmp = "{}.tmp{}".format(path, os.getpid())
    with open(tmp, "w", encoding="utf-8", newline="\n") as f:
        f.write(text)
    os.replace(tmp, path)


def gather(servers, name, ident, history):
    """every line of <name> in the servers' folders, once: [(line with srv, ...)], {server: offset read}"""
    seen = collections.OrderedDict()
    upto = {}
    dup = 0
    for srv, folder in servers:
        lines, end = R.read_tail(os.path.join(folder, name), 0)
        upto[srv] = end
        for d in lines:
            try:
                k = ident(d)
            except (KeyError, TypeError, ValueError):
                continue
            if k in seen:
                seen[k][1].append(srv)
                dup += 1
            else:
                seen[k] = (d, [srv])
    out = []
    for d, where in seen.values():
        d = dict(d)
        if not d.get("srv"):
            d["srv"] = history if (len(where) > 1 and history in where) else where[0]
        out.append(d)
    out.sort(key=lambda d: float(d.get("t") or 0.0))          # (stable: lines of the same time keep their order)
    return out, upto, dup


def merge(servers, history, prev=None):
    frags, up_f, dup_f = gather(servers, "frags.jsonl", lambda d: (round(float(d["t"]), 2), d["killer"], d["victim"]), history)
    duels, up_d, dup_d = gather(servers, "duels.jsonl", lambda d: (round(float(d["t"]), 2), d["key"], d.get("map")), history)
    # names: the newest row per key among the servers' tables and the last board
    best = {}
    sources = [(prev or {}).get("players") or {}]
    for srv, folder in servers:
        try:
            sources.append(json.load(open(os.path.join(folder, "ratings.json"), encoding="utf-8"))["players"])
        except Exception:                                    # noqa: BLE001 - no table there: the other sources name them
            pass
    for rows in sources:
        for k, p in rows.items():
            if isinstance(p, dict) and p.get("name") and (k not in best or float(p.get("t") or 0) >= best[k][0]):
                best[k] = (float(p.get("t") or 0), p["name"])
    names = {k: v[1] for k, v in best.items()}
    table = R.replay(R.Table(), frags, names)
    rec = {"all": [0, 0, 0]}
    people = collections.defaultdict(lambda: dict(frags={}, duels={}))
    for f in frags:
        bot_killed = str(f["killer"]).startswith(R.BOT)
        person = f["victim"] if bot_killed else f["killer"]
        c = people[person]["frags"].setdefault(f["srv"], [0, 0])
        c[1 if bot_killed else 0] += 1
    for d in duels:
        k_ = R.duel_result(d)
        if k_ is None:
            continue
        for v_ in ("all", R.version_of(d.get("net", ""))):
            rec.setdefault(v_, [0, 0, 0])[k_] += 1
        c = people[d["key"]]["duels"].setdefault(d["srv"], [0, 0, 0])
        c[{0: 1, 1: 0, 2: 2}[k_]] += 1                       # (the person's side: Bobby's loss is his win)
    nets = [f.get("net") for f in frags if f.get("net")]
    board = dict(schema=R.BOARD_SCHEMA, saved=round(time.time(), 1), n_frags=len(frags), n_duels=len(duels),
                 upto={srv: dict(frags=up_f[srv], duels=up_d[srv]) for srv, _ in servers},
                 servers=[srv for srv, _ in servers], bobby=(R.BOT + nets[-1]) if nets else None,
                 players=table.players, duels=rec, people=dict(people), private=sorted(private_keys(servers)),
                 dups=dict(frags=dup_f, duels=dup_d))
    return board, frags, duels, names


def private_keys(servers):
    """the people who said !anonymous (plugins/ladder.py: private.json in each server's folder, {"keys": {key: {"on", "t"}}}):
    the newest word of each person on any server counts ("!anonymous off" on one server undoes it on both)"""
    last = {}
    for srv, folder in servers:
        try:
            rows = json.load(open(os.path.join(folder, "private.json"), encoding="utf-8")).get("keys") or {}
        except Exception:                                    # noqa: BLE001 - none there yet
            continue
        for k, v in rows.items():
            if isinstance(v, dict) and (k not in last or float(v.get("t") or 0) >= last[k][0]):
                last[k] = (float(v.get("t") or 0), bool(v.get("on")))
    return {k for k, (t, on) in last.items() if on}


HISTORY_DAYS = 180                                           # (owner, 2026-10-25) the site's game history goes back this far


def game_history(frags, duels, names, private, now=None, days=HISTORY_DAYS):
    """the game history: every real game (kind "game") of the last `days` days, newest first, with both ratings after it
    and their change over the game (the frags inside it, worked out in time order from all frags as the board is).
    A row: id (ratings.game_id), srv, t0, len (seconds), map, score [person, Bobby], forfeit, ot, aim, ver, name (the
    person's name on the board; None for a person who said !anonymous, or with no name known), r [person, Bobby] after,
    dr [person, Bobby] change. No key leaves: the page needs none."""
    now = time.time() if now is None else now
    games = [d for d in duels if d.get("kind") == "game" and now - float(d.get("t") or 0) < days * 86400.0]
    marks = []
    for i, d in enumerate(games):
        marks.append((R.game_t0(d) - 0.01, 0, i))
        marks.append((float(d["t"]) + 1.0, 1, i))           # (a frag in the game's last frame is written just after it)
    marks.sort()
    table, fi, snap = R.Table(), 0, {}
    ft = [float(f.get("t") or 0) for f in frags]

    def r_of(key):
        p = table.players.get(key)
        if p is not None:
            return p["r"]
        if key.startswith(R.BOT):                            # (a new network starts at the last one's number: Table.entry)
            last = max((q for k, q in table.players.items() if k.startswith(R.BOT)), key=lambda q: q["t"], default=None)
            return last["r"] if last is not None else R.R0
        return R.R0

    for t, kind, i in marks:
        while fi < len(frags) and ft[fi] <= t:
            R.replay(table, [frags[fi]], names)
            fi += 1
        d = games[i]
        keys = (d.get("key"), R.BOT + str(d.get("net") or ""))
        snap.setdefault(i, [None, None])[kind] = [r_of(keys[0]), r_of(keys[1])]
    rows = []
    for i, d in enumerate(games):
        a, b = snap[i]
        t0 = R.game_t0(d)
        nm = names.get(d.get("key"))
        if d.get("key") in private or not nm or nm == d.get("key"):
            nm = None
        mins = float(d.get("minutes") or 0.0)               # (the game's own clock: a server that falls behind is slower than wall time)
        rows.append(dict(id=R.game_id(d, d.get("srv")), srv=d.get("srv"), t0=int(t0), len=int(round(60.0 * mins)),
                         map=d.get("map"), score=[int(x) for x in d.get("score", [0, 0])], forfeit=int(bool(d.get("forfeit"))),
                         ot=int(mins > 10.03), aim=str(d.get("aim") or ""), ver=R.version_of(d.get("net", "")),
                         name=nm, r=[int(round(b[0])), int(round(b[1]))], dr=[int(round(b[0] - a[0])), int(round(b[1] - a[1]))]))
    rows.sort(key=lambda x: -x["t0"])
    return rows


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--server", action="append", required=True, help="name=folder (name: a-z0-9, up to 8)")
    ap.add_argument("--history", default=None, help="the server the shared history is counted for (default: the first)")
    ap.add_argument("--prev", default=None)
    ap.add_argument("--out", required=True)
    ap.add_argument("--merged", default=None)
    ap.add_argument("--history-out", default=None, help="the game history (history.json for tools/board_page.py)")
    a = ap.parse_args()
    servers = [tuple(s.split("=", 1)) for s in a.server]
    history = a.history or servers[0][0]
    prev = R.load_board(a.prev) if a.prev else None
    board, frags, duels, names = merge(servers, history, prev)
    if prev is not None and (board["n_frags"] < int(prev.get("n_frags") or 0) or board["n_duels"] < int(prev.get("n_duels") or 0)):
        print("NOT WRITTEN: {} frags and {} duels, the last board had {} and {} (a copy missing or short?)".format(
            board["n_frags"], board["n_duels"], prev.get("n_frags"), prev.get("n_duels")))
        sys.exit(2)
    write_atomic(a.out, json.dumps(board, indent=1, ensure_ascii=False))
    if a.merged:
        os.makedirs(a.merged, exist_ok=True)
        write_atomic(os.path.join(a.merged, "frags.jsonl"), "".join(json.dumps(f) + "\n" for f in frags))
        write_atomic(os.path.join(a.merged, "duels.jsonl"), "".join(json.dumps(d) + "\n" for d in duels))
    if a.history_out:
        rows = game_history(frags, duels, names, set(board["private"]))
        write_atomic(a.history_out, json.dumps(dict(schema=1, saved=board["saved"], games=rows), separators=(",", ":"), ensure_ascii=False))
    by = collections.Counter(f["srv"] for f in frags)
    print("board: {} frags ({}), {} duels, {} rows; Bobby {}; taken once: {} frags and {} duels in more than one copy; {} anonymous".format(
        len(frags), ", ".join("{} {}".format(k, v) for k, v in sorted(by.items())), len(duels), len(board["players"]),
        "{:.0f}".format(board["players"][board["bobby"]]["r"]) if board["bobby"] in board["players"] else "-",
        board["dups"]["frags"], board["dups"]["duels"], len(board["private"])))


if __name__ == "__main__":
    main()

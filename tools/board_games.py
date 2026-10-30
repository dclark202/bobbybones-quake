"""board_games.py: the leaderboard site's game history and game reports (owner, 2026-10-25). Called by tools/board_page.py.

    history/index.html, history/page-<n>.html   the history: 50 games a page, newest first, the last 180 days
                                                 (tools/board_merge.py --history-out: older games are not in it, so
                                                 they leave the site at the next publish)
    games/<id>.html                              a game's report: the game's data inline, drawn by assets/report.js; a
                                                 game without its summary (tools/game_summary.py) gets the header only
    maps/<map>.json                              a map's floor (the walking graph's nodes, data/maps/nav_<map>_sim.json)
                                                 and its big items (plugins/duel_items.json), in units of 8
    players/<page id>.html                       a person's page: everything against Bobby (ratings.page_id; none after !anonymous)
    players/bobby.html                           Bobby's own page: his strengths and weaknesses now, his opponents
    assets/site.css, site.js, report.js          (tools/board_site/)

Names: the history's (the board's last name for a person); a person who said !anonymous, or one with no name known, is
"Anonymous". Nothing else about a person leaves: no key, no Steam id, no address.
"""
import collections
import html
import json
import os
import shutil
import sys
import time

HERE = os.path.dirname(os.path.abspath(__file__))
for p_ in (HERE, os.path.join(os.path.dirname(HERE), "plugins")):
    if os.path.exists(os.path.join(p_, "ratings.py")):
        sys.path.insert(0, p_)
        break
import ratings as R  # noqa: E402

SITE = os.path.join(HERE, "board_site")
PER_PAGE = 50
Q = 8
FONTS = ('<link rel="preconnect" href="https://fonts.googleapis.com">'
         '<link rel="stylesheet" href="https://fonts.googleapis.com/css2?family=Chakra+Petch:wght@500;700'
         '&family=IBM+Plex+Sans:wght@400;500;600&family=IBM+Plex+Mono:wght@400;500&display=swap">')
MAPS = {"bloodrun": "Blood Run", "aerowalk": "Aerowalk", "lostworld": "Lost World", "sinister": "Sinister",
        "furiousheights": "Furious Heights", "battleforged": "Battleforged", "campgrounds": "Campgrounds", "hektik": "Hektik",
        "toxicity": "Toxicity", "cure": "Cure", "houseofdecay": "House of Decay", "dismemberment": "Dismemberment"}
SERVERS = {"us": "US", "eu": "EU"}
BIG = {"item_health_mega": "MH", "item_armor_body": "RA", "item_armor_combat": "YA", "weapon_rocketlauncher": "RL",
       "weapon_railgun": "RG", "weapon_lightning": "LG"}
e = html.escape


def map_name(m):
    return MAPS.get(m, str(m).title())


def mmss(s):
    s = max(0, int(s))
    return "{}:{:02d}".format(s // 60, s % 60)


def utc(t):
    return time.strftime("%Y-%m-%d %H:%M", time.gmtime(t))


def when(t):
    """the time in UTC, shown in the viewer's own time by assets/site.js"""
    return '<time datetime="{}" data-t="{}">{} UTC</time>'.format(time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime(t)), int(t), utc(t))


def num(n):
    return "{:,}".format(int(n))


def signed(n):
    n = int(n)
    return "+{}".format(n) if n > 0 else "−{}".format(-n) if n < 0 else "±0"


def pname(row):
    return row.get("name") or "Anonymous"


def result(row):
    """(the result tag, its class): Bobby's side; a quit shows when it came"""
    p, b = row["score"]
    cls = "bw" if b > p else "dr" if b == p else ""
    if row.get("forfeit"):
        return "quit at {}".format(mmss(row["len"])), cls
    txt = "Bobby won" if b > p else "Bobby lost" if b < p else "Draw"
    return txt + (" · overtime" if row.get("ot") else ""), cls


def ratings(row, sep=" · "):
    return ('<span class="p">{} {} ({})</span>{}<span class="b">BobbyBones {} ({})</span>'.format(
        e(pname(row)), num(row["r"][0]), signed(row["dr"][0]), sep, num(row["r"][1]), signed(row["dr"][1])))


def nav(active, up):
    """the tabs: the leaderboard (the site's front page) and the game history; up = the way to the site's root"""
    tabs = [("board", "Leaderboard", up + "index.html" if up else "index.html"), ("history", "Game history", up + "history/index.html")]
    return '<nav class="tabs" aria-label="Site"><span class="site">BobbyBones</span>' + "".join(
        '<a href="{}"{}>{}</a>'.format(h, ' aria-current="page"' if k == active else "", t) for k, t, h in tabs) + "</nav>"


# the tab's icon: Bones' portrait from the game (default skin, 32 px; owner, 2026-10-27), inline so every page has it
ICON = '<link rel="icon" type="image/png" href="data:image/png;base64,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">'


def page(title, body, up, scripts=(), description=""):
    return ("<!doctype html>\n<html lang=\"en\"><head><meta charset=\"utf-8\">"
            '<meta name="viewport" content="width=device-width,initial-scale=1">'
            "<title>{}</title><meta name=\"description\" content=\"{}\">" + ICON + "{}"
            '<link rel="stylesheet" href="{}assets/site.css"></head>\n<body><div class="wrap">\n{}\n</div>\n{}</body></html>\n').format(
        e(title), e(description), FONTS, up, body, "".join('<script src="{}assets/{}"></script>'.format(up, s) for s in scripts))


# ---------------------------------------------------------------------- the history list
def history_pages(rows, have):
    """{file name: html} for the history; have: the ids with a summary"""
    n = max(1, -(-len(rows) // PER_PAGE))
    name = lambda i: "index.html" if i == 1 else "page-{}.html".format(i)
    out = {}
    for i in range(1, n + 1):
        part = rows[(i - 1) * PER_PAGE:i * PER_PAGE]
        body = [nav("history", "../"), "<section><h1>Game history</h1>",
                '<p class="sub">Every full game against BobbyBones on the US and EU servers, newest first, the last 180 days. '
                "Click a game to open its report.</p>"]
        body.append('<div class="tbl"><table id="hist"><thead><tr><th>Date</th><th>Players (rating after the game, change)</th>'
                    '<th>Score</th><th>Map</th><th class="n">Length</th><th class="n">Aim</th><th>Bobby</th><th>Server</th>'
                    '<th><span class="vh">Open</span></th></tr></thead><tbody>')
        if not part:
            body.append('<tr><td colspan="9">No games yet.</td></tr>')
        for r in part:
            tag, cls = result(r)
            href = "../games/{}.html".format(e(r["id"], quote=True))
            body.append(('<tr data-href="{h}"><td><a class="row" href="{h}" tabindex="-1">{w}</a></td><td><a class="row" href="{h}">'
                         '<span class="pl p">{pn}</span> <span class="r">{pr} ({pd})</span> vs <span class="b">BobbyBones</span> '
                         '<span class="r">{br} ({bd})</span></a></td><td><b>{p}–{b}</b> <span class="tag {c}">{tag}</span></td>'
                         '<td>{m}</td><td class="n">{ln}</td><td class="n">{aim}</td><td>{v}</td><td>{s}</td>'
                         '<td class="go" aria-hidden="true">›</td></tr>').format(
                h=href, w=when(r["t0"]), pn=e(pname(r)), pr=num(r["r"][0]), pd=signed(r["dr"][0]), br=num(r["r"][1]),
                bd=signed(r["dr"][1]), p=r["score"][0], b=r["score"][1], c=cls, tag=e(tag), m=e(map_name(r["map"])),
                ln=mmss(r["len"]), aim=e(r.get("aim") or "–"), v=e(r.get("ver") or ""),
                s=e(SERVERS.get(r.get("srv"), str(r.get("srv") or "").upper()))))
        body.append("</tbody></table></div>")
        pg = ['<div class="pager">']
        pg.append('<a href="{}">‹ Newer</a>'.format(name(i - 1)) if i > 1 else '<span class="off">‹ Newer</span>')
        pg.append("<span>Page {} of {} · {} games</span>".format(i, n, len(rows)))
        pg.append('<a href="{}">Older ›</a>'.format(name(i + 1)) if i < n else '<span class="off">Older ›</span>')
        pg.append("</div>")
        body.append("".join(pg) + "</section>")
        body.append('<div class="notes"><p>Times are shown in your own time zone (UTC without scripts). The rating is the '
                    "leaderboard&rsquo;s (Glicko-1, one update per frag), after the game, with its change over the game&rsquo;s "
                    "frags. A quit is a game the player left or stopped before its end.</p>"
                    "<p>Players are named as on the leaderboard. Type <b>!anonymous</b> in the game to show as Anonymous here "
                    "(past games too; <b>!anonymous off</b> to undo it). Games appear here 10 to 15 minutes after they end.</p></div>")
        out[name(i)] = page("BobbyBones Game History" + ("" if i == 1 else " ({})".format(i)), "\n".join(body), "../", ("site.js",),
                            "Every full game against BobbyBones on its Quake Live duel servers")
    return out


# ---------------------------------------------------------------------- a game's report
def game_page(row, g, pages=()):
    """the report of one game: row = its history row, g = its summary (tools/game_summary.py) or None, pages = the people
    with a page of their own"""
    tag, cls = result(row)
    pn = pname(row)
    pn_html = '<a class="plink" href="../players/{}.html">{}</a>'.format(row["who"], e(pn)) if row.get("who") in pages else e(pn)
    data = dict(id=row["id"], map=row["map"], len=row["len"], pname=pn)
    if g:
        for k in ("q", "pos", "frags", "items", "win", "stats", "mind"):
            if k in g:
                data[k] = g[k]
    js = json.dumps(data, separators=(",", ":"), ensure_ascii=True).replace("</", "<\\/")
    srv = SERVERS.get(row.get("srv"), str(row.get("srv") or "").upper())
    b = [nav("history", "../"), '<header class="score">',
         '<div class="eyebrow">Duel · {} · {} · {}</div>'.format(e(map_name(row["map"])), mmss(row["len"]), when(row["t0"])),
         '<div class="line"><div class="side p"><span class="name">{}</span><span class="n">{}</span></div><span class="dash">–</span>'
         '<div class="side b"><span class="n">{}</span><span class="name">{}</span></div></div>'.format(
             pn_html, row["score"][0], row["score"][1], '<a class="plink" href="../players/bobby.html">BobbyBones</a>' if pages else "BobbyBones"),
         '<div class="facts"><span class="tag {}" style="margin:0">{}</span><span>Bobby {} · aim level {}</span><span>{} server</span>'
         '<span id="dmgline"></span></div>'.format(cls, e(tag), e(row.get("ver") or ""), e(row.get("aim") or "–"), e(srv)),
         '<div class="facts"><span>Leaderboard after this game: {}</span></div>'.format(ratings(row)),
         '<div class="facts"><span>Game {}</span><span><a href="../history/index.html">All games</a></span></div></header>'.format(e(row["id"]))]
    if not g:
        b.append('<section><h2>No detailed record</h2><p class="note">This game has its result and ratings only: it was played '
                 "before the servers kept a record of every game, or its record was no longer on the server.</p></section>")
    else:
        b.append('<section><h2>How the game went</h2><p class="sub">Bobby&rsquo;s chance of winning from the score and clock alone '
                 "(a table made from pro duels), with every frag on the timeline.</p>"
                 '<div class="chart"><svg id="win" viewBox="0 0 960 230" width="100%" role="img" aria-label="Win chance over the game"></svg></div></section>')
        bel = bool(g.get("mind") and g["mind"].get("bel"))
        b.append('<div class="two"><section><h2>Where it was fought</h2><p class="sub">Time spent across the map (sampled twice a '
                 "second), frags marked where the victim died.</p>"
                 '<div class="tog" role="group" aria-label="Whose positions"><button id="t-both" aria-pressed="true">Both</button>'
                 '<button id="t-p" aria-pressed="false">{}</button><button id="t-b" aria-pressed="false">BobbyBones</button>{}</div>'
                 '<canvas id="heat" width="900" height="900" role="img" aria-label="Where both players were over the map"></canvas>'
                 '<div class="legend"><span><i class="key" style="background:var(--player)"></i>{}</span><span><i class="key" '
                 'style="background:var(--bobby)"></i>BobbyBones</span><span>× a death · ◆ an item</span></div>'
                 '<p class="sub" id="heatnote"></p></section>'.format(
                     e(pn), '<button id="t-bel" aria-pressed="false">Where Bobby thought {} was</button>'.format(e(pn)) if bel else "", e(pn)))
        b.append('<section><h2>Item control</h2><p class="sub">Who took each big item.</p><div class="tbl"><table id="items"><thead><tr>'
                 "<th>Item</th><th>{}</th><th>Bobby</th><th>Share</th></tr></thead><tbody></tbody></table></div>"
                 '<h2>Frag feed</h2><div class="feed" id="feed"></div></section></div>'.format(e(pn)))
        b.append('<section><h2>Weapons</h2><p class="sub">Shots, accuracy and kills by weapon, and how much of the game each was held '
                 "(the game&rsquo;s own end-of-game table).</p><div class=\"tbl\"><table id=\"weap\"><thead><tr><th>Weapon</th>"
                 "<th>{0} acc.</th><th>Kills</th><th>Held</th><th>Bobby acc.</th><th>Kills</th><th>Held</th></tr></thead><tbody></tbody>"
                 "</table></div></section>".format(e(pn)))
        if g.get("mind"):
            b.append('<section><h2>What Bobby was thinking</h2><p class="sub">From Bobby&rsquo;s mind log, recorded five times a second '
                     "next to where the player really was.</p><div class=\"mind\" id=\"mindstats\"></div><div class=\"two\">"
                     '<div class="mblock"><h3>Tracking the player out of sight</h3><p class="sub">How far off his picture of the player '
                     "was, by how long since he last saw him, against simply remembering the last sighting. Shorter is better.</p>"
                     '<div id="trackbars" class="bars"></div></div><div class="mblock"><h3>Predicting where the player goes</h3>'
                     '<p class="sub">His guess of the player&rsquo;s place 1, 2 and 4 s ahead, against assuming the player stays where '
                     "Bobby believes he is now.</p><div class=\"tbl\"><table id=\"ahead\"><thead><tr><th>Ahead</th><th>Bobby&rsquo;s guess</th>"
                     "<th>&ldquo;Stays put&rdquo;</th><th>Gain</th></tr></thead><tbody></tbody></table></div></div></div>"
                     '<div class="two"><div class="mblock"><h3>Reading the player&rsquo;s next item</h3><p class="sub">When the '
                     "player&rsquo;s next take within 15 s was this item, how often Bobby&rsquo;s top guess named it.</p>"
                     '<div id="recall" class="bars"></div></div><div class="mblock"><h3>His most common wrong reads</h3>'
                     '<p class="sub">Bobby expected the first, the player went for the second (moments, five a second).</p>'
                     '<div class="tbl"><table id="misses"><thead><tr><th>Bobby expected</th><th>Player went for</th><th>Moments</th>'
                     "</tr></thead><tbody></tbody></table></div></div></div><div class=\"mblock\"><h3>His error over the game</h3>"
                     '<p class="sub">Distance between where Bobby believed the player was and where he really was, every 5 s while '
                     'the player was out of sight.</p><div class="chart"><svg id="errline" viewBox="0 0 960 170" width="100%" '
                     'role="img" aria-label="Belief error over the game"></svg></div></div></section>')
    b.append('<script id="game" type="application/json">{}</script>'.format(js))
    title = "{} vs BobbyBones, {} – BobbyBones Game".format(pn, map_name(row["map"]))
    return page(title, "\n".join(b), "../", ("site.js", "report.js"),
                "{} {}–{} BobbyBones on {}, {} UTC".format(pn, row["score"][0], row["score"][1], map_name(row["map"]), utc(row["t0"])))


# ---------------------------------------------------------------------- maps
def map_file(mp, maps_dir, items):
    """the floor of a map (its walking graph's nodes, each once at 8 units) and its big items; None without the graph"""
    p = os.path.join(maps_dir or "", "nav_{}_sim.json".format(mp))
    try:
        with open(p, encoding="utf-8") as f:
            nodes = json.load(f)["nodes"]
    except Exception:                                        # noqa: BLE001 - no graph here: the heat map uses the players' places
        return None
    seen, flat = set(), []
    for n in nodes:
        k = (int(round(n[0] / Q)), int(round(n[1] / Q)))
        if k not in seen:
            seen.add(k)
            flat += [k[0], k[1]]
    its = [[BIG[i[0]], int(round(i[1] / Q)), int(round(i[2] / Q))] for i in (items or {}).get(mp, []) if i[0] in BIG]
    return dict(q=Q, floor=flat, items=its)


# ---------------------------------------------------------------------- a person's page
WEAPONS = {"rocket": "Rocket", "lightning": "Lightning", "railgun": "Rail", "shotgun": "Shotgun", "plasma": "Plasma", "grenade": "Grenade",
           "machinegun": "Machine gun", "gauntlet": "Gauntlet", "hmg": "Heavy MG", "bfg": "BFG", "chaingun": "Chaingun", "nailgun": "Nailgun"}
HEAT_BIN = 4                                                 # (a heat map's cell: 4 of the summaries' units of 8, 32 game units)
MIN_GAMES_STYLE = 3                                          # games with a record before a person gets tags or counts as "typical"
MIN_FIELD = 5                                                # people behind "the typical player" before it is shown


def light(row, g):
    """what a person's page needs of a game's summary, kept apart from the summary (the board's server has 1 GB)"""
    s = (g or {}).get("stats", {}).get("p")
    if not s:
        return None
    its = [[0, 0], [0, 0], [0, 0]]
    for it in g.get("items") or []:
        its[it[1]][it[2]] += 1
    win = g.get("win") or []
    m = g.get("mind") or {}
    track = [t for t in m.get("track") or [] if t.get("brain") is not None and t.get("last") is not None]
    share = sum(t["share"] for t in track)
    return dict(sec=row["len"], w=s.get("w") or {}, dealt=s.get("dealt", 0), taken=s.get("taken", 0), items=its,
                dist=[f[5] for f in g.get("frags") or [] if f[1] == 0 and f[5] > 0],
                chance=[100 - w[1] / 10.0 for w in win], b=(g.get("stats") or {}).get("b") or {},
                frags=[(min(9, int(f[0] // 60)), f[1], f[5]) for f in g.get("frags") or [] if f[7] != -1],
                mind=dict(brain=sum(t["share"] * t["brain"] for t in track) / share, last=sum(t["share"] * t["last"] for t in track) / share,
                          top1=(m.get("target") or {}).get("top1", 0.0), sightings=m.get("sightings", 0), surprises=m.get("surprises", 0),
                          track=track, ahead=m.get("ahead") or [], truth=(m.get("target") or {}).get("by_truth") or {}) if share else None)


def outcome(row):
    """the person's result as the record counts it (ratings.duel_result): w, l, d, or q for a game that does not count"""
    p, b = row["score"]
    if row.get("forfeit") and not (b > p and row["len"] / 60.0 > R.FORFEIT_WIN_MIN):
        return "q"
    return "w" if p > b else "l" if p < b else "d"


def wl(c):
    return "{}–{}".format(c["w"], c["l"]) + ("–{}".format(c["d"]) if c["d"] else "")


def tally(rows):
    c = dict(g=len(rows), w=0, l=0, d=0, q=0, f=0, a=0)
    for r in rows:
        c[outcome(r)] += 1
        c["f"] += r["score"][0]
        c["a"] += r["score"][1]
    return c


def style(lights):
    """the measures of play over games with a record. The game's "held" time for the machine gun runs on outside the game
    (30,000 s in a ten-minute game), so that weapon's time is what the others leave of the game."""
    sec = sum(x["sec"] for x in lights) or 1
    w = {}
    for x in lights:
        for k, v in x["w"].items():
            c = w.setdefault(k, [0, 0, 0, 0])
            for i in range(4):
                c[i] += v[i]
    other = sum(c[3] for k, c in w.items() if k != "machinegun")
    w.setdefault("machinegun", [0, 0, 0, 0])[3] = max(0, sec - other)
    items = [[sum(x["items"][i][j] for x in lights) for j in range(2)] for i in range(3)]
    dist = sorted(d for x in lights for d in x["dist"])
    dealt, taken = sum(x["dealt"] for x in lights), sum(x["taken"] for x in lights)
    kills = sum(c[2] for c in w.values())
    return dict(n=len(lights), w=w, kills=kills, held={k: c[3] / sec for k, c in w.items()},
                kill={k: c[2] / max(1, kills) for k, c in w.items()}, acc={k: c[1] / c[0] for k, c in w.items() if c[0] >= 50},
                item=[i[1] / max(1, sum(i)) for i in items], takes=[i[1] for i in items], dist=dist[len(dist) // 2] if dist else 0,
                ratio=dealt / max(1, taken), dmin=dealt / (sec / 60.0))


def typical(field):
    """the median person: field = the styles of people with enough games"""
    def med(f):
        v = sorted(x for x in (f(s) for s in field) if x is not None)
        return v[len(v) // 2] if v else None
    if len(field) < MIN_FIELD:
        return None
    return dict(item=[med(lambda s, i=i: s["item"][i]) for i in range(3)], dist=med(lambda s: s["dist"]), ratio=med(lambda s: s["ratio"]),
                dmin=med(lambda s: s["dmin"]), acc={k: med(lambda s, k=k: s["acc"].get(k)) for k in ("rocket", "lightning", "railgun")},
                held={k: med(lambda s, k=k: s["held"].get(k, 0.0)) for k in ("rocket", "lightning", "railgun")})


def tags(s, t):
    """a person's tags: only where they differ clearly from the typical player"""
    if s is None or t is None or s["n"] < MIN_GAMES_STYLE:
        return []
    out = []
    if s["item"][0] - t["item"][0] >= 0.10 and s["item"][1] - t["item"][1] >= 0.10:
        out.append("Item controller")
    if s["held"].get("rocket", 0) >= 0.5 and s["held"].get("rocket", 0) - t["held"]["rocket"] >= 0.10:
        out.append("Rocket main")
    if s["kill"].get("lightning", 0) >= 0.25 and s["kill"]["lightning"] >= 2 * s["held"].get("lightning", 0):
        out.append("Lightning finisher")
    if s["kill"].get("railgun", 0) >= 0.30:
        out.append("Rail specialist")
    if t["dist"] and s["dist"]:
        if s["dist"] <= 0.8 * t["dist"]:
            out.append("Close range")
        elif s["dist"] >= 1.2 * t["dist"]:
            out.append("Long range")
    for k, n in (("rocket", "Accurate rockets"), ("lightning", "Accurate lightning"), ("railgun", "Accurate rail")):
        if s["acc"].get(k) is not None and t["acc"].get(k) is not None and s["acc"][k] - t["acc"][k] >= 0.05:
            out.append(n)
    return out


def rating_chart(rows):
    """the rating after each game, oldest first (a row per game); a dashed line where a new version of Bobby came"""
    W, H, L, Rt, T, Bt = 960, 200, 46, 14, 14, 28
    v = [r["r"][0] for r in rows]
    lo, hi = min(v) - 15, max(v) + 15
    step = 100 if hi - lo > 300 else 50
    lo, hi = step * int(lo // step), step * int(-(-hi // step))
    x = lambda i: L + (W - L - Rt) * i / max(1, len(rows) - 1)
    y = lambda a: T + (H - T - Bt) * (1 - (a - lo) / max(1, hi - lo))
    s = ['<svg class="trend" viewBox="0 0 {} {}" role="img" aria-label="Rating after each of {} games: now {}, peak {}">'.format(W, H, len(rows), v[-1], max(v))]
    a = lo
    while a <= hi:
        s.append('<line class="grid" x1="{}" x2="{}" y1="{:.1f}" y2="{:.1f}"/><text class="ax" x="{}" y="{:.1f}" text-anchor="end">{}</text>'.format(L, W - Rt, y(a), y(a), L - 6, y(a) + 4, a))
        a += step
    spans, start = [], 0
    for i in range(1, len(rows) + 1):
        if i == len(rows) or rows[i].get("ver") != rows[start].get("ver"):
            spans.append((start, i - 1, rows[start].get("ver") or ""))
            start = i
    for k, (i, j, ver) in enumerate(spans):
        left = (x(i - 1) + x(i)) / 2 if i else L
        right = (x(j) + x(j + 1)) / 2 if j + 1 < len(rows) else W - Rt
        if i:
            s.append('<line class="vline" x1="{0:.1f}" x2="{0:.1f}" y1="{1}" y2="{2}"/>'.format(left, T, H - Bt))
        if right - left >= 56:
            s.append('<text class="ax vname" x="{:.1f}" y="{}" text-anchor="middle">{}</text>'.format((left + right) / 2, H - 8, e(ver)))
    s.append('<polyline class="ln p" points="{}"/>'.format(" ".join("{:.1f},{:.1f}".format(x(i), y(a)) for i, a in enumerate(v))))
    pk = v.index(max(v))
    s.append('<circle class="pt p" cx="{:.1f}" cy="{:.1f}" r="4"/><text class="val" x="{:.1f}" y="{:.1f}" text-anchor="middle">{}</text>'.format(x(pk), y(v[pk]), x(pk), y(v[pk]) - 8, v[pk]))
    if pk != len(v) - 1:
        s.append('<text class="val" x="{:.1f}" y="{:.1f}" text-anchor="end">{}</text>'.format(x(len(v) - 1), y(v[-1]) + 18, v[-1]))
    s.append('<circle class="pt now p" cx="{:.1f}" cy="{:.1f}" r="5"/></svg>'.format(x(len(v) - 1), y(v[-1])))
    return "".join(s)


def cells_path(cells, x0, y1):
    """a set of cells as one path: a run of neighbours in a row is one rectangle"""
    rows, out = {}, []
    for x, y in cells:
        rows.setdefault(y, []).append(x)
    for y, xs in rows.items():
        xs.sort()
        a = b = xs[0]
        for x in xs[1:] + [None]:
            if x is not None and x == b + 1:
                b = x
                continue
            out.append("M{} {}h{}v1h-{}z".format(a - x0, y1 - y, b - a + 1, b - a + 1))
            a = b = x
    return "".join(out)


def heat_svg(name, heat, mf):
    """where a person spends the time on a map: the map's floor, four levels of time, the big items"""
    B = HEAT_BIN
    floor = set()
    if mf:
        fl = mf["floor"]
        floor = {(int(round(fl[i] / float(B))), int(round(fl[i + 1] / float(B)))) for i in range(0, len(fl), 2)}
    al = list(floor) + list(heat)
    x0, x1 = min(c[0] for c in al), max(c[0] for c in al)
    y0, y1 = min(c[1] for c in al), max(c[1] for c in al)
    vals = sorted(heat.values())
    cuts = [vals[int(len(vals) * f)] for f in (.5, .8, .95)]
    lv = [[], [], [], []]
    for c, n in heat.items():
        lv[sum(n > t for t in cuts)].append(c)
    s = ['<svg class="heat" viewBox="-1 -1 {} {}" shape-rendering="crispEdges" role="img" aria-label="Where this player spends the time on {}">'.format(x1 - x0 + 3, y1 - y0 + 3, e(name)),
         '<path class="fl" d="{}"/>'.format(cells_path(floor, x0, y1))]
    for cs, op in zip(lv, (.25, .45, .7, 1)):
        s.append('<path class="ht" fill-opacity="{}" d="{}"/>'.format(op, cells_path(cs, x0, y1)))
    for it in (mf or {}).get("items") or []:
        s.append('<text class="it" x="{:.1f}" y="{:.1f}" text-anchor="middle">{}</text>'.format(round(it[1] / float(B)) - x0 + .5, y1 - round(it[2] / float(B)) + 1.4, e(it[0])))
    return "".join(s) + "</svg>"


def games_table(rows):
    b = ['<div class="tbl"><table class="num"><thead><tr><th>Date</th><th>Result</th><th class="n">Score</th><th>Map</th><th class="n">Aim</th>'
         '<th>Bobby</th><th class="n">Rating after</th></tr></thead><tbody>']
    for r in rows:
        o = outcome(r)
        res = "Quit at {}".format(mmss(r["len"])) if r.get("forfeit") else {"w": "Won", "l": "Lost", "d": "Draw"}[o]
        b.append('<tr><td><a href="../games/{}.html">{}</a></td><td class="{}">{}{}</td><td class="n">{}–{}</td><td>{}</td><td class="n">{}</td><td>{}</td>'
                 '<td class="n">{} <small>({})</small></td></tr>'.format(
                     e(r["id"], quote=True), when(r["t0"]), {"w": "p", "l": "b"}.get(o, "mu"), e(res), " (counts as a loss)" if r.get("forfeit") and o == "l" else "",
                     r["score"][0], r["score"][1], e(map_name(r["map"])), e(r.get("aim") or "–"), e(r.get("ver") or ""), num(r["r"][0]), signed(r["dr"][0])))
    return "".join(b) + "</tbody></table></div>"


def record_table(head, groups, cls=""):
    b = ['<div class="tbl"><table class="num"><thead><tr><th>{}</th><th class="n">Games</th><th class="n">Won–lost</th><th class="n">Quit</th><th class="n">Frags</th>'
         '<th class="n">Frag share</th></tr></thead><tbody>'.format(head)]
    for name, rows in groups:
        c = tally(rows)
        b.append('<tr><td class="{}">{}</td><td class="n">{}</td><td class="n">{}</td><td class="n">{}</td><td class="n">{}–{}</td><td class="n">{:.0%}</td></tr>'.format(
            cls, e(name), c["g"], wl(c), c["q"], c["f"], c["a"], c["f"] / max(1, c["f"] + c["a"])))
    return "".join(b) + "</tbody></table></div>"


def groups_of(rows, key):
    d = {}
    for r in rows:
        d.setdefault(key(r), []).append(r)
    return sorted(d.items(), key=lambda kv: -len(kv[1]))


def player_page(name, rating, rd, rank, frags, servers, rows, lights, heats, maps, t, now_ver):
    """a person's page. rows: their games, newest first; lights: light() of those with a record; heats: {map: Counter of cells};
    maps: {map: map_file()}; t: typical() or None; now_ver: Bobby's version now"""
    old = rows[::-1]
    c = tally(rows)
    s = style(lights) if lights else None
    if s is None or s["n"] < MIN_GAMES_STYLE:
        t = None                                             # (a game or two says too little to set beside others)
    played = sum(r["len"] for r in rows)
    streak = best = 0
    for r in old:
        o = outcome(r)
        if o == "w":
            streak += 1
            best = max(best, streak)
        elif o != "q":
            streak = 0
    facts = ["Rating {} ±{:.0f}".format(num(rating), 2 * rd)]
    if rows:
        facts.append("Peak {}".format(num(max(r["r"][0] for r in rows))))
    facts.append(servers or "–")
    if rows:
        facts += ["First game {}".format(when(old[0]["t0"])), "Last game {}".format(when(rows[0]["t0"]))]
    b = [nav("board", "../"), '<header class="pl-head"><div class="eyebrow">Player · {}</div><h1 class="pname">{}</h1><div class="facts">{}</div>'.format(
        e(rank), e(name), "".join("<span>{}</span>".format(f) for f in facts))]
    tg = tags(s, t)
    if tg:
        b.append('<div class="chips">{}</div>'.format("".join('<span class="chip">{}</span>'.format(e(x)) for x in tg)))
    b.append("</header>")
    tiles = [("{}".format(wl(c)) if rows else "–", "full games, won–lost" + (", and {} quit".format(c["q"]) if c["q"] else "")),
             ("{}–{}".format(frags[0], frags[1]), "frags with BobbyBones ({:.0%})".format(frags[0] / max(1, sum(frags))))]
    if rows:
        tiles.append(("{} h {} m".format(played // 3600, played % 3600 // 60), "played in {} game{}".format(len(rows), "" if len(rows) == 1 else "s")))
        tiles.append((str(best), "longest winning streak"))
        cur = [r for r in rows if r.get("ver") == now_ver]
        if cur:
            tiles.append((wl(tally(cur)), "against the current BobbyBones ({})".format(e(now_ver))))
    b.append('<section class="pstats"><div class="stats pl-tiles">{}</div></section>'.format(
        "".join('<div class="stat"><b>{}</b><span>{}</span></div>'.format(a, d) for a, d in tiles)))
    if not rows:
        b.append('<section><h2>No full games yet</h2><p class="note">Frags against BobbyBones count from the first one; the rest of this page '
                 "fills in from the first full ten-minute duel.</p></section>")
    if len(rows) >= 2:
        b.append('<section><h2>Rating over time</h2><p class="sub">After each game. The dashed lines mark a new version of BobbyBones.</p>{}</section>'.format(rating_chart(old)))
    if rows:
        by_map = groups_of(rows, lambda r: map_name(r["map"]))
        b.append('<section><h2>Favorite maps</h2>' + record_table("Map", by_map, "p"))
        figs = []
        for mp, h in sorted(heats.items(), key=lambda kv: -sum(kv[1].values()))[:2]:
            if sum(h.values()) >= 200:
                n = sum(1 for r in rows if r["map"] == mp and "_chance" in r)
                figs.append('<figure class="map">{}<figcaption>{}: where they spend their time, {} game{}</figcaption></figure>'.format(
                    heat_svg(map_name(mp), h, maps.get(mp)), e(map_name(mp)), n, "" if n == 1 else "s"))
        if figs:
            b.append('<div class="maps">{}</div>'.format("".join(figs)))
        b.append("</section>")
    if s:
        tq = lambda k: ' <small>({:.0f})</small>'.format(100 * t["acc"][k]) if t and t["acc"].get(k) is not None else ""
        w = ['<section><h2>Weapons</h2><p class="sub">Over {} game{} with a full record.{}</p><div class="tbl"><table class="num"><thead><tr><th>Weapon</th><th class="n">Frags</th>'
             '<th>Share of frags</th><th class="n">In hand</th><th class="n">Accuracy</th></tr></thead><tbody>'.format(
                 s["n"], "" if s["n"] == 1 else "s", " Accuracy of the typical player in brackets." if t else "")]
        for k, v in sorted(s["w"].items(), key=lambda kv: (-kv[1][2], -kv[1][3])):
            if not v[2] and not v[0]:
                continue
            w.append('<tr><td class="p">{}</td><td class="n">{}</td><td><div class="track"><div class="fill" style="width:{:.0f}%"></div></div></td><td class="n">{:.0%}</td><td class="n">{}{}</td></tr>'.format(
                e(WEAPONS.get(k, k.title())), v[2], 100 * s["kill"].get(k, 0), s["held"].get(k, 0), "{:.0%}".format(s["acc"][k]) if k in s["acc"] else "–", tq(k)))
        w.append("</tbody></table></div></section>")
        p = ['<section><h2>Playstyle</h2><p class="sub">Share of the big items they took.{}</p><div class="items">'.format(
            " The white tick is the typical player (the median of those with {} or more games).".format(MIN_GAMES_STYLE) if t else "")]
        for i, n in enumerate(("Mega", "Red armor", "Yellow armor")):
            tick = '<div class="tick" style="left:{:.0f}%"></div>'.format(100 * t["item"][i]) if t else ""
            p.append('<div class="item"><span>{}</span><div class="track"><div class="fill" style="width:{:.0f}%"></div>{}</div><span>{:.0%}{}, {:.1f} a game</span></div>'.format(
                n, 100 * s["item"][i], tick, s["item"][i], " ({:.0f})".format(100 * t["item"][i]) if t else "", s["takes"][i] / float(s["n"])))
        tt = lambda k, f: " <small>({})</small>".format(f.format(t[k])) if t and t.get(k) is not None else ""
        p.append('</div><div class="tbl"><table class="num"><tbody><tr><td>Typical frag distance</td><td class="n">{} units{}</td></tr>'
                 '<tr><td>Damage dealt per minute</td><td class="n">{:.0f}{}</td></tr><tr><td>Damage dealt ÷ taken</td><td class="n">{:.2f}{}</td></tr></tbody></table></div></section>'.format(
                     s["dist"], tt("dist", "{}"), s["dmin"], tt("dmin", "{:.0f}"), s["ratio"], tt("ratio", "{:.2f}")))
        b.append('<div class="two2">{}{}</div>'.format("".join(w), "".join(p)))
    if rows:
        vers = sorted(groups_of(rows, lambda r: r.get("ver") or "–"), key=lambda kv: -max(r["t0"] for r in kv[1]))
        left = ['<section><h2>Against each BobbyBones</h2>', record_table("Version", vers, "b"), "<h2>By aim level</h2>",
                record_table("Aim", sorted(groups_of(rows, lambda r: r.get("aim") or "–"))), "</section>"]
        hl = highlights(rows, lights)
        right = []
        if hl:
            right.append('<h2>Highlights</h2><div class="stats pl-hl">{}</div>'.format("".join(
                '<div class="stat"><b>{}</b><span>{} <a href="../games/{}.html">{}, {}</a></span></div>'.format(a, d, e(r["id"], quote=True), e(map_name(r["map"])), utc(r["t0"])[:10]) for a, d, r in hl)))
        mind = [x["mind"] for x in lights if x["mind"]]
        if mind:
            n = float(len(mind))
            right.append('<h2>How Bobby reads them</h2><p class="sub">From Bobby&rsquo;s mind log, {} game{}.</p><div class="tbl"><table class="num"><tbody>'
                         '<tr><td>Bobby&rsquo;s guess of their place when unseen</td><td class="n">{:.0f} units off</td></tr>'
                         '<tr><td>Just remembering the last sighting</td><td class="n">{:.0f} units off</td></tr>'
                         '<tr><td>Bobby&rsquo;s top guess of their next item</td><td class="n">right {:.0%}</td></tr>'
                         '<tr><td>Times Bobby sighted them</td><td class="n">{:.0f} a game</td></tr></tbody></table></div>'.format(
                             int(n), "" if n == 1 else "s", sum(m["brain"] for m in mind) / n, sum(m["last"] for m in mind) / n, sum(m["top1"] for m in mind) / n, sum(m["sightings"] for m in mind) / n))
        if right:
            b.append('<div class="two2">{}<section>{}</section></div>'.format("".join(left), "".join(right)))
        else:
            b.append("".join(left))
        b.append("<section><h2>Recent games</h2>" + games_table(rows[:6]))
        if len(rows) > 6:
            b.append('<details class="allg"><summary>All {} games</summary>{}</details>'.format(len(rows), games_table(rows[6:])))
        b.append("</section>")
    b.append('<div class="notes"><p>Rating, rank and frags are the leaderboard&rsquo;s. Won&ndash;lost counts full ten-minute duels; a quit is a game the player left or '
             "stopped before its end (a quit while well behind counts as a loss). Games and their details go back 180 days.</p>"
             "<p>Type <b>!anonymous</b> in the game to take this page down and show as Anonymous everywhere (<b>!anonymous off</b> to undo it).</p></div>")
    return page("{} – BobbyBones Player".format(name), "\n".join(b), "../", ("site.js",), "{} against BobbyBones on its Quake Live duel servers".format(name))


def highlights(rows, lights_by):
    """(number, words, row): the biggest win, the best comeback, the one that got away"""
    won = [r for r in rows if outcome(r) == "w"]
    out = []
    if won:
        r = max(won, key=lambda x: (x["score"][0] - x["score"][1], x["t0"]))
        out.append(("{}–{}".format(*r["score"]), "biggest win.", r))
    ch = {r["id"]: r.get("_chance") for r in rows if r.get("_chance")}
    back = [(min(ch[r["id"]]), r) for r in won if r["id"] in ch and min(ch[r["id"]]) < 25]
    if back:
        lo, r = min(back, key=lambda x: x[0])
        out.append(("{}–{}".format(*r["score"]), "best comeback, from a {:.0f}% chance of winning.".format(lo), r))
    lost = [(max(ch[r["id"]]), r) for r in rows if outcome(r) == "l" and r["id"] in ch and max(ch[r["id"]]) > 75]
    if lost:
        hi, r = max(lost, key=lambda x: x[0])
        out.append(("{}–{}".format(*r["score"]), "the one that got away, from a {:.0f}% chance of winning.".format(hi), r))
    return out


def player_pages(board, rows, lights, heats, maps):
    """{page id: html} for everyone on the board with a name who has not said !anonymous"""
    players, people = board.get("players") or {}, board.get("people") or {}
    private = set(board.get("private") or [])
    bobby = board.get("bobby")
    table = R.Table()
    table.players = players
    ranked = {k: n for n, (k, _) in enumerate(table.board(bobby), 1)}
    n_ranked = len(ranked)
    by_who = {}
    for r in rows:
        if r.get("who"):
            by_who.setdefault(r["who"], []).append(r)
    field = []
    for who, rs in by_who.items():
        ls = [lights[r["id"]] for r in rs if r["id"] in lights]
        if len(ls) >= MIN_GAMES_STYLE:
            field.append(style(ls))
    t = typical(field)
    now_ver = R.version_of(bobby[len(R.BOT):]) if bobby else ""
    out = {}
    for k, p in players.items():
        if k.startswith(R.BOT) or k in private or not p.get("name") or p["name"] == k:
            continue
        who = R.page_id(k)
        pp = people.get(k) or {}
        fr = pp.get("frags") or {}
        srv = " + ".join(SERVERS.get(s, s.upper()) for s in sorted(fr) if sum(fr[s])) or ""
        rs = by_who.get(who, [])
        for r in rs:
            if r["id"] in lights:
                r["_chance"] = lights[r["id"]]["chance"]
        rank = "rank {} of {}".format(ranked[k], n_ranked) if k in ranked else "not ranked yet"
        out[who] = player_page(p["name"], p["r"], p["rd"], rank, [p["won"], p["lost"]], srv, rs, [lights[r["id"]] for r in rs if r["id"] in lights],
                               {mp: h for (w, mp), h in heats.items() if w == who}, maps, t, now_ver)
    return out


# ---------------------------------------------------------------------- Bobby's page
BOBBY_PAGE = "bobby"                                         # players/bobby.html (a person's page id is 12 hex digits)
MIN_GAMES_READ = 5                                           # games of a version with a record before its strengths and weaknesses are worked out
ITEM_NAMES = ("Mega", "Red armor", "Yellow armor")
TRUTH_NAMES = {"MH": "Mega", "YA": "Yellow armor", "RA": "Red armor", "LG": "Lightning", "RG": "Rail", "RL": "Rocket launcher"}


def bobby_measures(lights):
    """Bobby and the people he played, over games with a record ("held" as in style(); frags without a player's own deaths)"""
    sec = sum(x["sec"] for x in lights) or 1
    W = {"b": {}, "p": {}}
    for x in lights:
        for side, w in (("b", x["b"].get("w") or {}), ("p", x["w"])):
            for k, v in w.items():
                c = W[side].setdefault(k, [0, 0, 0, 0])
                for i in range(4):
                    c[i] += v[i]
    for side in W:
        other = sum(c[3] for k, c in W[side].items() if k != "machinegun")
        W[side].setdefault("machinegun", [0, 0, 0, 0])[3] = max(0, sec - other)
    items = [[sum(x["items"][i][j] for x in lights) for j in range(2)] for i in range(3)]
    mins = [[0, 0] for _ in range(10)]
    bands = [[0, 0] for _ in range(4)]
    for x in lights:
        for m, bobby_died, d in x["frags"]:
            mins[m][1 if bobby_died == 0 else 0] += 1
            if d > 0:
                bands[0 if d < 200 else 1 if d < 500 else 2 if d < 900 else 3][1 if bobby_died == 0 else 0] += 1
    return dict(n=len(lights), sec=sec, w=W, items=items, mins=mins, bands=bands)


def bobby_reads(m, mind):
    """(strengths, weaknesses), each a list of (number, words), by fixed rules on the version's own games"""
    good, bad = [], []
    if mind:
        t = [x for ms in mind for x in ms["track"] if x["label"] == "3-6 s"]
        if t:
            br, la = sum(x["brain"] for x in t) / len(t), sum(x["last"] for x in t) / len(t)
            if br < 0.7 * la:
                good.append(("{:.0f} units".format(br), "off the enemy&rsquo;s place 3&ndash;6 s after losing sight. Just remembering the last sighting: {:.0f}.".format(la)))
        sights = sum(x["sightings"] for x in mind)
        if sights and sum(x["surprises"] for x in mind) / sights < 0.10:
            good.append(("{:.0%}".format(sum(x["surprises"] for x in mind) / sights), "of sightings catch him by surprise."))
    share = [(i, c[0] / sum(c), c) for i, c in enumerate(m["items"]) if sum(c)]
    share.sort(key=lambda x: -x[1])
    if share and share[0][1] > 0.5:
        i, s, c = share[0]
        good.append(("{:.0%}".format(s), "of {}s are his ({} of {}).".format(ITEM_NAMES[i].lower(), c[0], sum(c))))
    b, p = m["w"]["b"], m["w"]["p"]
    acc = []
    for k in ("rocket", "lightning", "railgun", "plasma"):
        if b.get(k, [0])[0] >= 100 and p.get(k, [0])[0] >= 100:
            x, y = b[k][1] / b[k][0], p[k][1] / p[k][0]
            if x - y >= 0.03:
                acc.append((p[k][2], k, x, y))
    acc.sort(reverse=True)
    if acc:
        _, k, x, y = acc[0]
        more = " {}: {:.0%} vs {:.0%}.".format(WEAPONS[acc[1][1]], acc[1][2], acc[1][3]) if len(acc) > 1 else ""
        good.append(("{:.0%} vs {:.0%}".format(x, y), "{} accuracy, his against theirs.{}".format(WEAPONS[k].lower(), more)))
    low = [x for x in reversed(share) if x[1] < 0.5]
    if low:
        i, s, c = low[0]
        more = ", and {:.0%} of {}s".format(low[1][1], ITEM_NAMES[low[1][0]].lower()) if len(low) > 1 else ""
        bad.append(("{:.0%}".format(s), "of {}s are his ({} of {}){}.".format(ITEM_NAMES[i].lower(), c[0], sum(c), more)))
    gap = sorted(((p[k][2] - b.get(k, [0, 0, 0, 0])[2], k) for k in p if p[k][2] >= 20), reverse=True)
    sec = float(m["sec"])
    far = None
    for d, k in gap:                                         # (the weapon people out-frag him with most for want of holding it)
        if b.get(k, [0, 0, 0, 0])[3] < 0.5 * p[k][3]:
            far = k
            break
    if far:
        bb = b.get(far, [0, 0, 0, 0])
        bad.append(("{} vs {}".format(bb[2], p[far][2]), "{} frags, his against theirs. He holds it {:.0%} of the time; they hold it {:.0%}.".format(
            WEAPONS[far].lower(), bb[3] / sec, p[far][3] / sec)))
    total = [sum(x[i] for x in m["mins"]) for i in range(2)]
    overall = total[0] / max(1, sum(total))
    lg = [sum(m["bands"][i][j] for i in (2, 3)) for j in range(2)]
    if sum(lg) >= 20 and lg[0] / sum(lg) < 0.75 * overall:
        bad.append(("{}&ndash;{}".format(*lg), "frags at 500 units or more."))
    fm = m["mins"][0]
    if sum(fm) >= 10 and fm[0] / sum(fm) < 0.75 * overall:
        bad.append(("{}&ndash;{}".format(*fm), "frags in the first minute of a game."))
    return good[:4], bad[:4]


def minutes_svg(mins):
    H, U = 170, 1.0
    top = max(x[0] for x in mins) or 1
    down = max(x[1] for x in mins) or 1
    U = 120.0 / (top + down)
    mid = 12 + top * U + 4
    s = ['<svg class="trend mins" viewBox="0 0 480 {:.0f}" role="img" aria-label="Frags by minute of the game: {}">'.format(mid + down * U + 34, ", ".join(
        "minute {}: Bobby {}, people {}".format(i, a, c) for i, (a, c) in enumerate(mins)))]
    for i, (a, c) in enumerate(mins):
        x = 8 + 47.5 * i
        s.append('<rect class="mb" x="{0:.1f}" y="{1:.1f}" width="30" height="{2:.1f}"/><rect class="mp" x="{0:.1f}" y="{3:.1f}" width="30" height="{4:.1f}"/>'.format(
            x, mid - 2 - a * U, a * U, mid + 2, c * U))
        s.append('<text class="val" x="{0:.1f}" y="{1:.1f}" text-anchor="middle">{2}</text><text class="val" x="{0:.1f}" y="{3:.1f}" text-anchor="middle">{4}</text>'.format(
            x + 15, mid - 6 - a * U, a, mid + 14 + c * U, c))
        s.append('<text class="ax" x="{:.1f}" y="{:.1f}" text-anchor="middle">{}</text>'.format(x + 15, mid + down * U + 30, i))
    return "".join(s) + "</svg>"


def bobby_page(board, rows, lights, pages, rank, now_ver):
    """Bobby's page: rows = every game, newest first; lights = light() by game id; pages = the people with a page"""
    bp = board["players"][board["bobby"]]
    cur = [r for r in rows if r.get("ver") == now_ver]
    cl = [lights[r["id"]] for r in cur if r["id"] in lights]
    duels = board.get("duels") or {}
    rec = lambda v: "{}–{}".format(*(list(v or [0, 0, 0]) + [0, 0])[:2])
    versions = {R.version_of(k[len(R.BOT):]): p for k, p in board["players"].items() if k.startswith(R.BOT)}
    best = max(versions.items(), key=lambda kv: kv[1]["r"]) if versions else (now_ver, bp)
    out = [nav("board", "../"), '<header class="pl-head"><div class="eyebrow">The bot · {}</div><h1 class="pname bo">BobbyBones {}</h1><div class="facts"><span>Rating {} ±{:.0f}</span>'
           "<span>Best version {} at {}</span><span>US + EU servers</span></div></header>".format(e(rank), e(now_ver), num(bp["r"]), 2 * bp["rd"], e(best[0]), num(best[1]["r"]))]
    cf, ca = sum(r["score"][1] for r in cur), sum(r["score"][0] for r in cur)
    c = {"w": 0, "q": 0}
    for r in cur:
        o = outcome(r)
        if o in c:
            c[o] += 1
    tiles = [(rec(duels.get(now_ver)), "full games with {}, won–lost{}".format(e(now_ver), ", and {} quit".format(c["q"]) if c["q"] else "")),
             ("{:.0%}".format(cf / max(1, cf + ca)), "of the frags with people in {} ({}–{})".format(e(now_ver), cf, ca)),
             (rec(duels.get("all")), "all versions, won–lost"), (num(len(rows)), "games on record")]
    won = [r for r in cur if outcome(r) == "l"]              # (outcome is the person's side: their loss is his win)
    if won:
        r = max(won, key=lambda x: (x["score"][1] - x["score"][0], x["t0"]))
        tiles.append(("{}–{}".format(r["score"][1], r["score"][0]), 'biggest win with {}. <a href="../games/{}.html">{}, {}</a>'.format(
            e(now_ver), e(r["id"], quote=True), e(map_name(r["map"])), utc(r["t0"])[:10])))
    out.append('<section><div class="stats pl-tiles">{}</div></section>'.format("".join('<div class="stat"><b>{}</b><span>{}</span></div>'.format(a, d) for a, d in tiles)))
    m = bobby_measures(cl) if cl else None
    mind = [x["mind"] for x in cl if x["mind"]]
    if m and m["n"] >= MIN_GAMES_READ:
        good, bad = bobby_reads(m, mind)
        card = lambda rows_: "".join('<div class="stat"><b>{}</b><span>{}</span></div>'.format(a, d) for a, d in rows_) or '<p class="note">Nothing stands out yet.</p>'
        out.append('<div class="two2"><section class="reads"><h2 class="b-h">Strengths right now</h2><p class="sub">{} against the people he has played, {} games with a full record, all aim levels.</p><div class="pl-hl">{}</div></section>'
                   '<section class="reads bad"><h2 class="p-h">Weaknesses right now</h2><p class="sub">Same games. These are where people beat him most clearly.</p><div class="pl-hl">{}</div></section></div>'.format(
                       e(now_ver), m["n"], card(good), card(bad)))
    by_who = {}
    for r in rows:
        if r.get("who") in pages:
            by_who.setdefault(r["who"], []).append(r)
    opp = []
    for who, rs in by_who.items():
        t = tally(rs)
        if t["w"] + t["l"] + t["d"] >= 3:
            opp.append((t["a"] / max(1, t["f"] + t["a"]), who, rs, t))
    if opp:
        opp.sort(key=lambda x: x[0])
        def otable(head, part):
            b = ['<div class="tbl"><table class="num"><thead><tr><th>{}</th><th class="n">Won–lost</th><th class="n">Frags</th><th class="n">Share</th><th class="n">{}</th></tr></thead><tbody>'.format(head, e(now_ver))]
            for sh, who, rs, t in part:
                nw = [r for r in rs if r.get("ver") == now_ver]
                tn = tally(nw) if nw else None
                b.append('<tr><td class="p"><a class="plink" href="{}.html">{}</a></td><td class="n">{}–{}</td><td class="n">{}–{}</td><td class="n">{:.0%}</td><td class="n">{}</td></tr>'.format(
                    who, e(rs[0].get("name") or ""), t["l"], t["w"], num(t["a"]), num(t["f"]), sh, "{}–{}".format(tn["l"], tn["w"]) if tn else "–"))
            return "".join(b) + "</tbody></table></div>"
        n = min(4, (len(opp) + 1) // 2)
        out.append('<section><h2>Toughest and best opponents</h2><p class="sub">People with 3 or more full games, all versions, by share of the frags. Won&ndash;lost from Bobby&rsquo;s side.</p><div class="two2">{}{}</div></section>'.format(
            otable("He does best against", opp[::-1][:n]), otable("Toughest for him", opp[:n])))
    if cur:
        def side_table(head, groups):
            b = ['<div class="tbl"><table class="num"><thead><tr><th>{}</th><th class="n">Games</th><th class="n">Won–lost</th><th class="n">Quit</th><th class="n">Frags</th><th class="n">Share</th></tr></thead><tbody>'.format(head)]
            for name, rs in groups:
                t = tally(rs)
                b.append('<tr><td class="b">{}</td><td class="n">{}</td><td class="n">{}–{}{}</td><td class="n">{}</td><td class="n">{}–{}</td><td class="n">{:.0%}</td></tr>'.format(
                    e(name), t["g"], t["l"], t["w"], "–{}".format(t["d"]) if t["d"] else "", t["q"], num(t["a"]), num(t["f"]), max(0, t["a"]) / max(1, max(0, t["a"]) + max(0, t["f"]))))
            return "".join(b) + "</tbody></table></div>"
        over = ""
        if m:
            over = '<h2>Over a game</h2><p class="sub">Frags by minute, {}.</p>{}<div class="legend"><span><i class="key" style="background:var(--bobby)"></i>Bobby&rsquo;s frags</span><span><i class="key" style="background:var(--player)"></i>People&rsquo;s frags</span><span>minute of the game</span></div>'.format(e(now_ver), minutes_svg(m["mins"]))
        out.append('<div class="two2"><section><h2>By map</h2><p class="sub">{0}. A map with one or two games says little.</p>{1}</section><section><h2>By aim level</h2><p class="sub">{0}. The level the player picks with !aim.</p>{2}{3}</section></div>'.format(
            e(now_ver), side_table("Map", groups_of(cur, lambda r: map_name(r["map"]))), side_table("Aim", groups_of(cur, lambda r: r.get("aim") or "–")), over))
    if m:
        b_w, p_w, sec = m["w"]["b"], m["w"]["p"], float(m["sec"])
        wr = ['<section><h2>Weapons</h2><p class="sub">{}: Bobby against the people he played, whose numbers are in brackets. The bar is his share of the frags with that weapon.</p><div class="tbl"><table class="num"><thead><tr><th>Weapon</th><th class="n">Frags</th><th>His share</th><th class="n">In hand</th><th class="n">Accuracy</th></tr></thead><tbody>'.format(e(now_ver))]
        zero = [0, 0, 0, 0]
        for k in sorted(set(b_w) | set(p_w), key=lambda k: -b_w.get(k, zero)[2] * 1000 - b_w.get(k, zero)[3]):
            x, y = b_w.get(k, zero), p_w.get(k, zero)
            if not (x[0] or x[2] or y[2]):
                continue
            ac = lambda v: "{:.0%}".format(v[1] / v[0]) if v[0] >= 50 else "–"
            wr.append('<tr><td class="b">{}</td><td class="n">{}–{}</td><td><div class="track vs"><div class="fill" style="width:{:.0f}%"></div></div></td><td class="n">{:.0%} <small>({:.0%})</small></td><td class="n">{} <small>({})</small></td></tr>'.format(
                e(WEAPONS.get(k, k.title())), x[2], y[2], 100 * x[2] / max(1, x[2] + y[2]), x[3] / sec, y[3] / sec, ac(x), ac(y)))
        wr.append('</tbody></table></div><div class="tbl"><table class="num"><thead><tr><th>Frag distance</th><th class="n">Frags</th><th class="n">His share</th></tr></thead><tbody>')
        for n_, c_ in zip(("Under 200 units", "200–500", "500–900", "900 and over"), m["bands"]):
            wr.append('<tr><td>{}</td><td class="n">{}–{}</td><td class="n">{:.0%}</td></tr>'.format(n_, c_[0], c_[1], c_[0] / max(1, sum(c_))))
        wr.append("</tbody></table></div></section>")
        kn = ""
        if mind:
            kn = ['<section><h2>What he knows</h2><p class="sub">From his mind log, {}, {} games.</p><div class="tbl"><table class="num"><thead><tr><th>The enemy out of sight for</th><th class="n">Bobby&rsquo;s guess</th><th class="n">Last sighting</th></tr></thead><tbody>'.format(e(now_ver), len(mind))]
            for lab, name in (("0-1 s", "Under 1 s"), ("1-3 s", "1–3 s"), ("3-6 s", "3–6 s"), ("6-15 s", "6–15 s")):
                t = [x for ms in mind for x in ms["track"] if x["label"] == lab]
                if t:
                    kn.append('<tr><td>{}</td><td class="n">{:.0f} units off</td><td class="n">{:.0f}</td></tr>'.format(name, sum(x["brain"] for x in t) / len(t), sum(x["last"] for x in t) / len(t)))
            kn.append('</tbody></table></div><div class="tbl"><table class="num"><thead><tr><th>Where the enemy will be</th><th class="n">Bobby&rsquo;s guess</th><th class="n">&ldquo;Stays put&rdquo;</th></tr></thead><tbody>')
            for h in (1, 2, 4):
                t = [x for ms in mind for x in ms["ahead"] if x.get("h") == h and x.get("brain") is not None and x.get("stay") is not None]
                if t:
                    kn.append('<tr><td>{} s ahead</td><td class="n">{:.0f} units off</td><td class="n">{:.0f}</td></tr>'.format(h, sum(x["brain"] for x in t) / len(t), sum(x["stay"] for x in t) / len(t)))
            kn.append('</tbody></table></div><div class="tbl"><table class="num"><thead><tr><th>Enemy&rsquo;s next pickup was</th><th class="n">Bobby&rsquo;s top guess was right</th></tr></thead><tbody>')
            tr = []
            for k, name in TRUTH_NAMES.items():
                n_ = sum((ms["truth"].get(k) or {}).get("n", 0) for ms in mind)
                if n_:
                    tr.append((sum((ms["truth"].get(k) or {}).get("n", 0) * ((ms["truth"].get(k) or {}).get("right") or 0) for ms in mind) / n_, name))
            for s_, name in sorted(tr, reverse=True):
                kn.append('<tr><td>{}</td><td class="n">{:.0%}</td></tr>'.format(name, s_))
            kn.append("</tbody></table></div></section>")
            kn = "".join(kn)
        out.append('<div class="two2">{}{}</div>'.format("".join(wr), kn))
    vs = sorted(groups_of(rows, lambda r: r.get("ver") or "–"), key=lambda kv: -max(r["t0"] for r in kv[1]))
    if vs:
        b = ['<section><h2>Every version</h2><p class="sub">Rating against people, newest first. Share is of the frags in full games and quits.</p><div class="tbl"><table class="num"><thead><tr><th>Version</th><th class="n">Rating</th><th class="n">Games</th><th class="n">Won–lost</th><th class="n">Quit</th><th class="n">Frags</th><th class="n">Share</th></tr></thead><tbody>']
        for v, rs in vs:
            t = tally(rs)
            b.append('<tr><td class="b">{}{}</td><td class="n">{}</td><td class="n">{}</td><td class="n">{}–{}</td><td class="n">{}</td><td class="n">{}–{}</td><td class="n">{:.0%}</td></tr>'.format(
                e(v), " <small>now</small>" if v == now_ver else "", num(versions[v]["r"]) if v in versions else "–", t["g"], t["l"], t["w"], t["q"], num(t["a"]), num(t["f"]), max(0, t["a"]) / max(1, max(0, t["a"]) + max(0, t["f"]))))
        b.append("</tbody></table></div></section>")
        out.append("".join(b))
    out.append('<div class="notes"><p>Won&ndash;lost counts full ten-minute duels from Bobby&rsquo;s side. Numbers in brackets are the people he played, in the same games. Strengths and weaknesses are worked out afresh from the games of the version playing now, over all aim levels. Games go back 180 days.</p></div>')
    return page("BobbyBones – BobbyBones Player", "\n".join(out), "../", ("site.js",), "BobbyBones against everyone on its Quake Live duel servers: strengths, weaknesses and opponents")


# ---------------------------------------------------------------------- the whole part of the site
def write_site(out_dir, rows, games_dir, maps_dir=None, items_path=None, board=None):
    """writes history/, games/, maps/, assets/ and, with the board, players/ into out_dir; returns {relative path: text} of what it wrote"""
    have = {}
    for d in (games_dir if isinstance(games_dir, (list, tuple)) else [games_dir]):
        if d and os.path.isdir(d):
            for n in os.listdir(d):
                if n.endswith(".json") and not n.startswith("_"):
                    have[n[:-5]] = os.path.join(d, n)
    try:
        items = json.load(open(items_path, encoding="utf-8")) if items_path else {}
    except Exception:                                        # noqa: BLE001
        items = {}
    files = {}
    for n, t in history_pages(rows, have).items():
        files["history/" + n] = t
    pages = set()
    if board:
        private = set(board.get("private") or [])
        pages = {R.page_id(k) for k, p in (board.get("players") or {}).items()
                 if not k.startswith(R.BOT) and k not in private and p.get("name") and p["name"] != k}
    lights, heats = {}, {}
    for r in rows:
        g = None
        if r["id"] in have:
            try:
                g = json.load(open(have[r["id"]], encoding="utf-8"))
            except Exception:                                # noqa: BLE001 - a broken summary: the header only
                g = None
        files["games/{}.html".format(r["id"])] = game_page(r, g, pages)
        x = light(r, g) if g else None
        if x:
            lights[r["id"]] = x
        if g and r.get("who") in pages:
            pos =(g.get("pos") or {}).get("p") or []
            h = heats.setdefault((r["who"], r["map"]), collections.Counter())
            for i in range(0, len(pos) - 1, 2):
                h[(int(round(pos[i] / float(HEAT_BIN))), int(round(pos[i + 1] / float(HEAT_BIN))))] += 1
    maps = {}
    for mp in sorted({r["map"] for r in rows if r.get("map")}):
        m = map_file(mp, maps_dir, items)
        if m is not None:
            maps[mp] = m
            files["maps/{}.json".format(mp)] = json.dumps(m, separators=(",", ":"))
    if board:
        for who, t in player_pages(board, rows, lights, heats, maps).items():
            files["players/{}.html".format(who)] = t
        bobby = board.get("bobby")
        if bobby in (board.get("players") or {}):
            table = R.Table()
            table.players = board["players"]
            n, of = table.rank(bobby, bobby)
            files["players/{}.html".format(BOBBY_PAGE)] = bobby_page(board, rows, lights, pages, "rank {} of {}".format(n, of), R.version_of(bobby[len(R.BOT):]))
    for n in ("site.css", "site.js", "report.js"):
        with open(os.path.join(SITE, n), encoding="utf-8") as f:
            files["assets/" + n] = f.read()
    for rel, text in files.items():
        p = os.path.join(out_dir, *rel.split("/"))
        os.makedirs(os.path.dirname(p), exist_ok=True)
        with open(p, "w", encoding="utf-8", newline="\n") as f:
            f.write(text)
    return files


def clear(out_dir):
    """the generated folders, emptied before a new site is written (a pruned game leaves with its page)"""
    for d in ("history", "games", "maps", "assets", "players"):
        shutil.rmtree(os.path.join(out_dir, d), ignore_errors=True)

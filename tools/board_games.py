"""board_games.py: the leaderboard site's game history and game reports (owner, 2026-10-25). Called by tools/board_page.py.

    history/index.html, history/page-<n>.html   the history: 50 games a page, newest first, the last 180 days
                                                 (tools/board_merge.py --history-out: older games are not in it, so
                                                 they leave the site at the next publish)
    games/<id>.html                              a game's report: the game's data inline, drawn by assets/report.js; a
                                                 game without its summary (tools/game_summary.py) gets the header only
    maps/<map>.json                              a map's floor (the walking graph's nodes, data/maps/nav_<map>_sim.json)
                                                 and its big items (plugins/duel_items.json), in units of 8
    assets/site.css, site.js, report.js          (tools/board_site/)

Names: the history's (the board's last name for a person); a person who said !anonymous, or one with no name known, is
"Anonymous". Nothing else about a person leaves: no key, no Steam id, no address.
"""
import html
import json
import os
import shutil
import time

HERE = os.path.dirname(os.path.abspath(__file__))
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


def page(title, body, up, scripts=(), description=""):
    return ("<!doctype html>\n<html lang=\"en\"><head><meta charset=\"utf-8\">"
            '<meta name="viewport" content="width=device-width,initial-scale=1">'
            "<title>{}</title><meta name=\"description\" content=\"{}\">{}"
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
                "A row opens its game report.</p>"]
        body.append('<div class="tbl"><table id="hist"><thead><tr><th>Date</th><th>Players</th><th>Score</th><th>Map</th>'
                    '<th class="n">Length</th><th class="n">Aim</th><th>Bobby</th><th>Server</th><th>Rating after (change)</th>'
                    "</tr></thead><tbody>")
        if not part:
            body.append('<tr><td colspan="9">No games yet.</td></tr>')
        for r in part:
            tag, cls = result(r)
            href = "../games/{}.html".format(e(r["id"], quote=True))
            body.append(('<tr><td><a class="row" href="{h}">{w}</a></td><td><a class="row" href="{h}"><span class="pl p">{pn}</span> vs '
                         '<span class="b">BobbyBones</span></a></td><td><b>{p}–{b}</b> <span class="tag {c}">{tag}</span></td>'
                         '<td>{m}</td><td class="n">{ln}</td><td class="n">{aim}</td><td>{v}</td><td>{s}</td><td class="rt">{rt}</td></tr>').format(
                h=href, w=when(r["t0"]), pn=e(pname(r)), p=r["score"][0], b=r["score"][1], c=cls, tag=e(tag), m=e(map_name(r["map"])),
                ln=mmss(r["len"]), aim=e(r.get("aim") or "–"), v=e(r.get("ver") or ""), s=e(SERVERS.get(r.get("srv"), str(r.get("srv") or "").upper())),
                rt=ratings(r, "<br>")))
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
def game_page(row, g):
    """the report of one game: row = its history row, g = its summary (tools/game_summary.py) or None"""
    tag, cls = result(row)
    pn = pname(row)
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
         '<div class="side b"><span class="n">{}</span><span class="name">BobbyBones</span></div></div>'.format(e(pn), row["score"][0], row["score"][1]),
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


# ---------------------------------------------------------------------- the whole part of the site
def write_site(out_dir, rows, games_dir, maps_dir=None, items_path=None):
    """writes history/, games/, maps/ and assets/ into out_dir; returns {relative path: text} of what it wrote"""
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
    for r in rows:
        g = None
        if r["id"] in have:
            try:
                g = json.load(open(have[r["id"]], encoding="utf-8"))
            except Exception:                                # noqa: BLE001 - a broken summary: the header only
                g = None
        files["games/{}.html".format(r["id"])] = game_page(r, g)
    for mp in sorted({r["map"] for r in rows if r.get("map")}):
        m = map_file(mp, maps_dir, items)
        if m is not None:
            files["maps/{}.json".format(mp)] = json.dumps(m, separators=(",", ":"))
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
    for d in ("history", "games", "maps", "assets"):
        shutil.rmtree(os.path.join(out_dir, d), ignore_errors=True)

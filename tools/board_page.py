"""board_page.py: the public leaderboard page from the shared board (owner, 2026-10-23).

    python3 tools/board_page.py board.json <out folder> [--history history.json --games <summaries> [--games <more>]
                                                         --maps data/maps --items plugins/duel_items.json]
        writes <out folder>/index.html, README.md and .nojekyll and, with --history, the game history and the game reports
        (tools/board_games.py: history/, games/, maps/, assets/); prints the site's content hash (without its times) on
        the last line

board.json is tools/board_merge.py's. The page shows what the servers' !top shows, for everyone: the in-game name a
person was last seen with, the rating (Glicko-1 per frag, plugins/ratings.py), the frags with BobbyBones, the full duel
games against him (won-lost, and on which server), and BobbyBones' own line. Nothing else leaves: no Steam id, no
anonymous key, no QLStats number. A person who said !anonymous (board.json "private") is "Anonymous" here too: his rating
after his last game is on the game history, so a name beside it on the board would give him away. The site is published
by the server that merges the board, a few minutes after a change (private/tools/board/publish.sh).
"""
import argparse
import hashlib
import html
import json
import os
import sys
import time

HERE = os.path.dirname(os.path.abspath(__file__))
for p_ in (HERE, os.path.join(os.path.dirname(HERE), "plugins")):
    if os.path.exists(os.path.join(p_, "ratings.py")):
        sys.path.insert(0, p_)
        break
import ratings as R  # noqa: E402
import board_games as BG  # noqa: E402

REPO = "https://github.com/dclark202/bobbybones-quake"
README = ("# BobbyBones leaderboard\n\nThe public board of people against BobbyBones on its Quake Live duel servers, published at "
          "https://dclark202.github.io/bobbybones-leaderboard/ (the leaderboard and the game history), refreshed a few minutes after "
          "a game. The bot itself: " + REPO + "\n")

def site_css():
    """the game history's stylesheet (tools/board_site/site.css), inline so the front page stands alone"""
    with open(os.path.join(BG.SITE, "site.css"), encoding="utf-8") as f:
        return f.read()


def vname(net):
    """v0.3.10 for duel_gru_v0_3_10; the run's short name for the old ones (v14end)"""
    v = R.version_of(net)
    return R.label(net) if v == str(net) else v


def wld(r, draws=True):
    r = list(r or [0, 0, 0]) + [0, 0, 0]
    return "{}&ndash;{}".format(r[0], r[1]) + ("&ndash;{}".format(r[2]) if draws and r[2] else "")


def render(b, stamp):
    players = b["players"]
    bobby = b.get("bobby")
    rows = R.Table()
    rows.players = players
    board = rows.board(bobby)
    people = b.get("people") or {}
    private = set(b.get("private") or [])
    e = html.escape
    out = []
    bp = players.get(bobby) if bobby else None
    ver = vname(bobby[len(R.BOT):]) if bobby else "-"
    if bp is not None:
        n, of = rows.rank(bobby, bobby)
        rec_all, rec_now = (b.get("duels") or {}).get("all", [0, 0, 0]), (b.get("duels") or {}).get(ver, [0, 0, 0])
        tot = bp["won"] + bp["lost"]
        out.append('<section class="bobby"><h2>BobbyBones {}</h2><div class="stats">'.format(e(ver)))
        out.append('<div class="stat"><b>{:.0f}</b><span>rating (&plusmn;{:.0f}), rank {} of {}</span></div>'.format(bp["r"], 2 * bp["rd"], n, of))
        out.append('<div class="stat"><b>{}&ndash;{}</b><span>frags with people, made&ndash;taken ({:.0%})</span></div>'.format(
            bp["won"], bp["lost"], bp["won"] / max(1, tot)))
        out.append('<div class="stat"><b>{}</b><span>his full ten-minute games, won&ndash;lost ({})</span></div>'.format(wld(rec_now), e(ver)))
        out.append('<div class="stat"><b>{}</b><span>all versions</span></div></div>'.format(wld(rec_all)))
        out.append("</section>")
    out.append('<section><div class="tools"><input id="q" type="search" placeholder="Search players" aria-label="Search players by name"></div>')
    out.append('<div class="tbl"><table id="board"><thead><tr><th class="n">#</th><th>Player</th><th class="n">Rating</th>'
               '<th class="n">Games</th><th class="n">W&ndash;L vs Bobby</th><th class="n">Frags vs Bobby</th><th>Played on</th></tr></thead><tbody>')
    ranked = [(n, k, p) for n, (k, p) in enumerate(board, 1)]
    unranked = sorted(((None, k, p) for k, p in players.items() if not k.startswith(R.BOT) and p["won"] + p["lost"] < R.MIN_FRAGS),
                      key=lambda x: -x[2]["r"])
    for n, k, p in ranked + unranked:
        num = n if n else '<small title="ranked from {} frags with BobbyBones">&ndash;</small>'.format(R.MIN_FRAGS)
        if k == bobby:
            rec = (b.get("duels") or {}).get("all") or [0, 0, 0]
            out.append('<tr class="me" data-name="bobbybones"><td class="n">{}</td><td class="nm">BobbyBones <small>{}</small></td>'
                       '<td class="n">{:.0f} <small>&plusmn;{:.0f}</small></td><td class="n">{}</td><td class="n">{} <small>(his own)</small></td>'
                       '<td class="n"><small>the bot</small></td><td>both</td></tr>'.format(
                           num, e(ver), p["r"], 2 * p["rd"], sum(rec), wld(rec)))
            continue
        pp = people.get(k) or {}
        nm = "Anonymous" if (k in private or not p.get("name") or p["name"] == k) else p["name"]
        fr, du = pp.get("frags") or {}, pp.get("duels") or {}
        tot_d = [sum(v[i] for v in du.values()) for i in range(3)]
        by = " &middot; ".join("{} {}".format(s.upper(), wld(v)) for s, v in sorted(du.items()) if sum(v))
        on = " + ".join(s.upper() for s in sorted(fr) if sum(fr[s])) or "-"
        out.append('<tr data-name="{}"><td class="n">{}</td><td class="nm">{}</td><td class="n">{:.0f} <small>&plusmn;{:.0f}</small></td><td class="n">{}</td>'
                   '<td class="n">{}{}</td><td class="n">{}&ndash;{}</td><td>{}</td></tr>'.format(
                       e(nm.lower(), quote=True), num, e(nm), p["r"], 2 * p["rd"], sum(tot_d) or "-",
                       wld(tot_d) if sum(tot_d) else "-", " <small>({})</small>".format(by) if len(du) > 1 and by else "",
                       p["won"], p["lost"], on))
    out.append('</tbody></table></div>')
    out.append('<div class="pager"><button id="prev" type="button">&larr; Prev</button><span id="pn"></span>'
               '<button id="next" type="button">Next &rarr;</button></div></section>')
    trend = sorted(((k, p) for k, p in players.items() if k.startswith(R.BOT)), key=lambda kp: float(kp[1].get("since") or 0))
    if len(trend) > 1:
        out.append('<section><h2>BobbyBones by version</h2>' + trend_svg(trend, bobby)
                   + '<p class="note">Each version&rsquo;s rating against people, oldest to newest; the filled point is the version playing now.</p></section>')
    out.append('<div class="notes">')
    if unranked:
        out.append("<p>A player is ranked from {} frags with BobbyBones; {} {} not ranked yet (# &ndash;).</p>".format(
            R.MIN_FRAGS, len(unranked), "is" if len(unranked) == 1 else "are"))
    out.append("<p>Every frag between a person and BobbyBones in a live game counts, on either server (warmup frags do not count). The rating is "
               "Glicko-1, one update per frag (a frag counts as a quarter of a game); everyone starts at 1500. A difference of "
               "100 points means the higher one makes about 64% of the frags between the two. &plusmn; is twice the rating's "
               "uncertainty. Games are full ten-minute duels against BobbyBones, won&ndash;lost from the player's side.</p>")
    out.append("<p>Names are the in-game name a player was last seen with; <b>!anonymous</b> in the game shows a player as "
               "Anonymous here and in the game history. Updated a few minutes after a game. {}</p>".format(e(stamp)))
    out.append('<p>About the bot: <a href="{0}">{0}</a></p></div>'.format(REPO))
    body = "\n".join(out)
    return ("<!doctype html>\n"
            '<html lang="en"><head><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1">\n'
            '<title>BobbyBones Leaderboard</title><meta name="description" content="The shared leaderboard of the BobbyBones Quake Live duel servers">\n'
            + BG.ICON + BG.FONTS + "<style>" + site_css() + "</style></head>\n<body><div class=\"wrap\">\n" + BG.nav("board", "")
            + "\n<h1>BobbyBones leaderboard</h1>\n" + body + "\n<script>" + JS + "</script>\n</div></body></html>\n")


def trend_svg(trend, bobby):
    """Bobby's rating by version, oldest to newest (inline SVG, no library); the version playing now is the last point"""
    e = html.escape
    W, H, L, Rt, T, Bt = 560, 240, 46, 30, 26, 42
    vals = [p["r"] for _, p in trend]
    lo, hi = min(vals) - 30, max(vals) + 30
    step = 50 if hi - lo > 150 else 25
    lo, hi = step * int(lo // step), step * int(-(-hi // step))
    x = lambda i: L + (W - L - Rt) * (i / max(1, len(trend) - 1))
    y = lambda v: T + (H - T - Bt) * (1 - (v - lo) / max(1.0, hi - lo))
    s = ['<svg class="trend" viewBox="0 0 {} {}" role="img" aria-label="BobbyBones rating by version">'.format(W, H)]
    v = lo
    while v <= hi:
        s.append('<line class="grid" x1="{}" x2="{}" y1="{:.1f}" y2="{:.1f}"/><text class="ax" x="{}" y="{:.1f}" text-anchor="end">{}</text>'.format(
            L, W - Rt, y(v), y(v), L - 6, y(v) + 4, v))
        v += step
    s.append('<polyline class="ln" points="{}"/>'.format(" ".join("{:.1f},{:.1f}".format(x(i), y(p["r"])) for i, (_, p) in enumerate(trend))))
    for i, (k, p) in enumerate(trend):
        now = k == bobby
        s.append('<circle class="{}" cx="{:.1f}" cy="{:.1f}" r="{}"><title>{} {:.0f}</title></circle>'.format(
            "pt now" if now else "pt", x(i), y(p["r"]), 5 if now else 3.5, e(vname(k[len(R.BOT):])), p["r"]))
        s.append('<text class="val" x="{:.1f}" y="{:.1f}" text-anchor="middle">{:.0f}</text>'.format(x(i), y(p["r"]) - 9, p["r"]))
        s.append('<text class="ax{}" x="{:.1f}" y="{}" text-anchor="middle">{}</text>'.format(
            " nowt" if now else "", x(i), H - Bt + 18, e(vname(k[len(R.BOT):]))))
    s.append("</svg>")
    return "".join(s)


JS = """
(function(){var rows=[].slice.call(document.querySelectorAll('#board tbody tr')),q=document.getElementById('q'),
pn=document.getElementById('pn'),pv=document.getElementById('prev'),nx=document.getElementById('next'),P=50,page=0;
function draw(){var s=q.value.trim().toLowerCase(),hit=rows.filter(function(r){return !s||r.getAttribute('data-name').indexOf(s)>=0;}),
n=Math.max(1,Math.ceil(hit.length/P));if(page>=n)page=n-1;rows.forEach(function(r){r.style.display='none';});
hit.slice(page*P,page*P+P).forEach(function(r){r.style.display='';});
var np=hit.filter(function(r){return r.className!='me';}).length;
pn.textContent='Page '+(page+1)+' of '+n+' \\u00b7 '+np+(np==1?' player':' players');pv.disabled=page<=0;nx.disabled=page>=n-1;}
q.addEventListener('input',function(){page=0;draw();});pv.addEventListener('click',function(){if(page>0){page--;draw();}});
nx.addEventListener('click',function(){page++;draw();});draw();})();
"""


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("board")
    ap.add_argument("out")
    ap.add_argument("--history", default=None, help="tools/board_merge.py --history-out")
    ap.add_argument("--games", action="append", default=[], help="folders of game summaries (tools/game_summary.py)")
    ap.add_argument("--maps", default=None, help="the walking graphs (data/maps/nav_<map>_sim.json)")
    ap.add_argument("--items", default=None, help="plugins/duel_items.json (the maps' big items)")
    a = ap.parse_args()
    src, out_dir = a.board, a.out
    b = R.load_board(src)
    if b is None:
        sys.exit("no board in {}".format(src))
    stamp = "Board as of {} UTC.".format(time.strftime("%Y-%m-%d %H:%M", time.gmtime(float(b.get("saved") or time.time()))))
    page = render(b, stamp)
    os.makedirs(out_dir, exist_ok=True)
    tmp = os.path.join(out_dir, "index.html.tmp")
    with open(tmp, "w", encoding="utf-8", newline="\n") as f:
        f.write(page)
    os.replace(tmp, os.path.join(out_dir, "index.html"))
    open(os.path.join(out_dir, ".nojekyll"), "w").close()
    with open(os.path.join(out_dir, "README.md"), "w", encoding="utf-8", newline="\n") as f:
        f.write(README)
    h = hashlib.sha256(render(b, "").encode("utf-8"))
    if a.history:
        with open(a.history, encoding="utf-8") as f:
            rows = json.load(f)["games"]
        BG.clear(out_dir)
        files = BG.write_site(out_dir, rows, a.games, a.maps, a.items)
        for rel in sorted(files):
            h.update(rel.encode("utf-8"))
            h.update(files[rel].encode("utf-8"))
    print(h.hexdigest())


if __name__ == "__main__":
    main()

/* A game report of the BobbyBones leaderboard site (tools/board_page.py writes the page with the game's data in
   <script id="game" type="application/json">; the map's floor comes from ../maps/<map>.json). Positions are stored in
   units of G.q game units. No library. */
(function () {
  "use strict";
  var el = document.getElementById("game");
  if (!el) return;
  var G = JSON.parse(el.textContent);
  if (!G.frags) return;                                     // (a game without its detailed record: the header only)
  var q = G.q || 8, PN = G.pname || "Player", LEN = Math.max(G.len || 600, 1);
  var css = function (n) { return getComputedStyle(document.documentElement).getPropertyValue(n).trim(); };
  var $ = function (id) { return document.getElementById(id); };
  var esc = function (s) { return String(s).replace(/[&<>"']/g, function (c) { return {"&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;", "'": "&#39;"}[c]; }); };
  var mmss = function (t) { t = Math.max(0, Math.floor(t)); return Math.floor(t / 60) + ":" + String(t % 60).padStart(2, "0"); };
  var pairs = function (a) { var o = []; for (var i = 0; i + 1 < a.length; i += 2) o.push([a[i] * q, a[i + 1] * q]); return o; };
  var WNUM = {1: "Gauntlet", 2: "Machine gun", 3: "Shotgun", 4: "Grenade", 5: "Rocket", 6: "Lightning", 7: "Rail", 8: "Plasma", 9: "BFG", 14: "Heavy MG"};
  var W = ["rocket", "railgun", "lightning", "plasma", "grenade", "shotgun", "machinegun", "gauntlet", "hmg"];
  var WN = {rocket: "Rocket launcher", railgun: "Railgun", lightning: "Lightning gun", plasma: "Plasma gun", grenade: "Grenade launcher",
            shotgun: "Shotgun", machinegun: "Machine gun", gauntlet: "Gauntlet", hmg: "Heavy machine gun"};
  var INAME = ["Mega", "Red armor", "Yellow armor"];
  var posB = pairs(G.pos.b || []), posP = pairs(G.pos.p || []);
  var frags = G.frags.map(function (f) {
    return {t: f[0], bobbyDied: f[1] === 0, at: [f[2] * q, f[3] * q], weapon: WNUM[f[4]] || "", dist: f[5], inView: f[6] === 1,
            own: f[7] === -1, score: [f[8], f[9]]};
  });
  var stat = function (s) {
    s = s || {k: 0, d: 0, dealt: 0, taken: 0, w: {}};
    var w = {};
    Object.keys(s.w || {}).forEach(function (k) { var v = s.w[k]; w[k] = {shots: v[0], hits: v[1], kills: v[2], held: v[3]}; });
    return {kills: s.k, deaths: s.d, dealt: s.dealt, taken: s.taken, weapons: w};
  };
  var P = stat((G.stats || {}).p), B = stat((G.stats || {}).b);
  if (G.stats && G.stats.p && G.stats.b && $("dmgline"))
    $("dmgline").textContent = "damage " + P.dealt.toLocaleString("en-US") + " – " + B.dealt.toLocaleString("en-US");

  // ------------------------------------------------------------ How the game went
  function drawWin() {
    var s = $("win"); if (!s || !G.win || !G.win.length) return;
    var x0 = 40, x1 = 940, y0 = 20, y1 = 180;
    var X = function (t) { return x0 + (x1 - x0) * t / LEN; }, Y = function (p) { return y1 - (y1 - y0) * p; };
    var h = "";
    [0, .25, .5, .75, 1].forEach(function (p) {
      h += '<line x1="' + x0 + '" x2="' + x1 + '" y1="' + Y(p) + '" y2="' + Y(p) + '" stroke="var(--line)" stroke-width="1"/>' +
           '<text x="' + (x0 - 6) + '" y="' + (Y(p) + 4) + '" text-anchor="end">' + (p * 100) + '%</text>';
    });
    var step = LEN > 900 ? 240 : 120;
    for (var m = 0; m <= LEN + 1; m += step) h += '<text x="' + X(m) + '" y="' + (y1 + 18) + '" text-anchor="middle">' + mmss(m) + '</text>';
    if (LEN > 602) h += '<line x1="' + X(600) + '" x2="' + X(600) + '" y1="' + y0 + '" y2="' + y1 + '" stroke="var(--muted)" stroke-dasharray="4 4"/>' +
                        '<text x="' + (X(600) + 4) + '" y="' + (y0 + 10) + '">overtime</text>';
    var pts = G.win.map(function (w) { return X(w[0]).toFixed(1) + "," + Y(w[1] / 1000).toFixed(1); });
    h += '<path d="M' + X(G.win[0][0]) + "," + Y(0) + " L" + pts.join(" L") + " L" + X(G.win[G.win.length - 1][0]) + "," + Y(0) + ' Z" fill="var(--bobby-soft)"/>';
    h += '<polyline points="' + pts.join(" ") + '" fill="none" stroke="var(--bobby)" stroke-width="2"/>';
    frags.forEach(function (f) {
      var c = f.own ? "var(--muted)" : f.bobbyDied ? "var(--player)" : "var(--bobby)";
      var who = f.own ? (f.bobbyDied ? "BobbyBones" : PN) + " dies by his own hand" : (f.bobbyDied ? PN : "BobbyBones") + " scores";
      h += '<line x1="' + X(f.t) + '" x2="' + X(f.t) + '" y1="' + (y1 + 24) + '" y2="' + (y1 + 36) + '" stroke="' + c + '" stroke-width="3"><title>' +
           mmss(f.t) + " " + esc(who) + '</title></line>';
    });
    h += '<text x="' + x0 + '" y="' + (y1 + 48) + '">frags: green = ' + esc(PN) + ' scores, purple = Bobby scores, grey = a death by one’s own hand</text>';
    s.setAttribute("viewBox", "0 0 960 " + (y1 + 56)); s.innerHTML = h;
  }

  // ------------------------------------------------------------ Where it was fought
  var mode = "both", MAP = null;
  var rgba = function (v, a) {
    var d = document.createElement("div"); d.style.color = v; document.body.appendChild(d);
    var r = getComputedStyle(d).color; d.remove();
    var m = r.match(/[\d.]+/g) || [0, 0, 0]; return "rgba(" + m[0] + "," + m[1] + "," + m[2] + "," + a + ")";
  };
  function drawHeat() {
    var c = $("heat"); if (!c) return;
    var x = c.getContext("2d"), N = c.width;
    var floor = MAP ? pairs(MAP.floor || []) : [];
    var all = floor.length ? floor : posB.concat(posP);
    if (!all.length) return;
    var mnx = Infinity, mxx = -Infinity, mny = Infinity, mxy = -Infinity;
    all.forEach(function (p) { if (p[0] < mnx) mnx = p[0]; if (p[0] > mxx) mxx = p[0]; if (p[1] < mny) mny = p[1]; if (p[1] > mxy) mxy = p[1]; });
    mnx -= 150; mxx += 150; mny -= 150; mxy += 150;
    var sp = Math.max(mxx - mnx, mxy - mny), ox = (sp - (mxx - mnx)) / 2, oy = (sp - (mxy - mny)) / 2;
    var PX = function (v) { return (v - mnx + ox) / sp * N; }, PY = function (v) { return N - (v - mny + oy) / sp * N; };
    var R = Math.max(5, Math.round(N * 26 / 900));
    x.clearRect(0, 0, N, N);
    x.fillStyle = css("--floor");
    floor.forEach(function (p) { x.beginPath(); x.arc(PX(p[0]), PY(p[1]), 7, 0, 7); x.fill(); });
    var layer = function (pts, col) {
      var c0 = rgba(col, 0.10), c1 = rgba(col, 0);
      pts.forEach(function (p) {
        var g = x.createRadialGradient(PX(p[0]), PY(p[1]), 0, PX(p[0]), PY(p[1]), R);
        g.addColorStop(0, c0); g.addColorStop(1, c1); x.fillStyle = g; x.fillRect(PX(p[0]) - R, PY(p[1]) - R, 2 * R, 2 * R);
      });
    };
    var bel = G.mind && G.mind.bel ? pairs(G.mind.bel) : null;
    if (mode === "bel" && bel) { layer(posP, css("--player")); layer(bel, css("--bobby")); }
    else {
      if (mode !== "b") layer(posP, css("--player"));
      if (mode !== "p") layer(posB, css("--bobby"));
    }
    var note = $("heatnote");
    if (note) note.textContent = mode === "bel" ? "Green: where " + PN + " really was. Purple: where Bobby believed he was while out of sight." : "";
    x.font = "bold 22px IBM Plex Mono, monospace"; x.textAlign = "center"; x.textBaseline = "middle";
    frags.forEach(function (f) {
      if (mode === "bel" || (mode === "p" && f.bobbyDied) || (mode === "b" && !f.bobbyDied)) return;
      x.fillStyle = f.bobbyDied ? css("--bobby") : css("--player"); x.fillText("×", PX(f.at[0]), PY(f.at[1]));
    });
    x.font = "500 18px IBM Plex Mono, monospace"; x.fillStyle = css("--ink");
    ((MAP && MAP.items) || []).forEach(function (it) { x.fillText("◆ " + it[0], PX(it[1] * q), PY(it[2] * q) - 16); });
  }
  ["both", "p", "b", "bel"].forEach(function (m) {
    var b = $("t-" + m); if (!b) return;
    b.addEventListener("click", function () {
      mode = m;
      ["both", "p", "b", "bel"].forEach(function (n) { var e = $("t-" + n); if (e) e.setAttribute("aria-pressed", String(n === m)); });
      drawHeat();
    });
  });

  // ------------------------------------------------------------ Item control, frag feed, weapons
  function tables() {
    var it = {};
    (G.items || []).forEach(function (r) { var n = INAME[r[1]]; it[n] = it[n] || {player: 0, bobby: 0}; it[n][r[2] === 0 ? "bobby" : "player"]++; });
    var tb = document.querySelector("#items tbody");
    if (tb) tb.innerHTML = INAME.map(function (n) {
      var v = it[n] || {player: 0, bobby: 0}, tot = v.player + v.bobby || 1;
      return "<tr><td>" + n + '</td><td class="p">' + v.player + '</td><td class="b">' + v.bobby + '</td><td><div class="bar"><i style="width:' +
             (100 * v.player / tot) + '%;background:var(--player)"></i><i style="width:' + (100 * v.bobby / tot) + '%;background:var(--bobby)"></i></div></td></tr>';
    }).join("");
    var held = function (s) { return Object.keys(s.weapons).reduce(function (a, k) { return a + s.weapons[k].held; }, 0) || 1; };
    var hp = held(P), hb = held(B);
    var cell = function (s, w, tot) {
      var v = s.weapons[w]; if (!v || !(v.shots || v.held || v.kills)) return "<td>–</td><td>–</td><td>–</td>";
      return "<td>" + (v.shots ? Math.round(100 * v.hits / v.shots) + "%" : "–") + ' <span style="color:var(--muted)">(' + v.shots + ")</span></td><td>" +
             v.kills + "</td><td>" + Math.round(100 * v.held / tot) + "%</td>";
    };
    var wt = document.querySelector("#weap tbody");
    if (wt) wt.innerHTML = W.filter(function (w) { return P.weapons[w] || B.weapons[w]; }).map(function (w) {
      return "<tr><td>" + WN[w] + "</td>" + cell(P, w, hp) + cell(B, w, hb) + "</tr>";
    }).join("") || '<tr><td colspan="7">The game’s own table was not recorded for this game.</td></tr>';
    var fd = $("feed");
    if (fd) fd.innerHTML = frags.map(function (f) {
      var txt, col;
      if (f.own) { txt = (f.bobbyDied ? "BobbyBones" : esc(PN)) + " died by his own hand"; col = "var(--muted)"; }
      else { txt = f.bobbyDied ? esc(PN) + " fragged Bobby" : "Bobby fragged " + esc(PN); col = f.bobbyDied ? "var(--player)" : "var(--bobby)"; }
      var w = f.own ? "suicide or the map" : (f.weapon || "?") + (f.dist ? ", " + f.dist + " u" : "") + (f.inView ? "" : ", out of sight");
      return "<div><span>" + mmss(f.t) + '</span><span style="color:' + col + '">' + txt + '</span><span class="w">' + w +
             '</span><span class="s">' + f.score[0] + "–" + f.score[1] + "</span></div>";
    }).join("") || '<div><span></span><span>No frags.</span></div>';
  }

  // ------------------------------------------------------------ What Bobby was thinking (only with a mind log)
  var NM = {MH: "Mega", RA: "Red armor", YA: "Yellow armor", RL: "Rocket launcher", RG: "Railgun", LG: "Lightning gun"};
  function mindSection() {
    var M = G.mind; if (!M || !$("mindstats")) return;
    var t3 = M.track.filter(function (r) { return r.label === "3-6 s"; })[0] || M.track[0];
    var cards = [];
    if (t3 && t3.brain != null) cards.push([t3.brain + " u", "off about " + PN + "’s place 3–6 s after losing sight (remembering the last sighting: " + t3.last + " u)"]);
    cards.push([Math.round(100 * M.target.top1) + "%", "of the time his top guess named " + PN + "’s next big item or weapon"]);
    cards.push([M.surprises + " of " + M.sightings, "of " + PN + "’s appearances caught him by surprise"]);
    cards.push([Math.round(100 * M.seen_share) + "%", "of the game he had " + PN + " in sight"]);
    $("mindstats").innerHTML = cards.map(function (c) { return '<div class="stat"><b>' + esc(c[0]) + "</b><span>" + esc(c[1]) + "</span></div>"; }).join("");
    var mx = Math.max.apply(null, M.track.map(function (r) { return Math.max(r.brain || 0, r.last || 0); })) || 1;
    $("trackbars").innerHTML = M.track.filter(function (r) { return r.brain != null; }).map(function (r) {
      return '<div class="brow"><span>' + r.label + '<br><span style="color:var(--muted)">' + Math.round(100 * r.share) + '% of the time</span></span><div class="btrack">' +
             '<div class="bline"><i style="width:' + (70 * r.brain / mx) + '%;background:var(--bobby)"></i><span>' + r.brain + ' u Bobby</span></div>' +
             '<div class="bline"><i style="width:' + (70 * (r.last || 0) / mx) + '%;background:var(--line)"></i><span>' + r.last + " u last seen</span></div></div></div>";
    }).join("");
    document.querySelector("#ahead tbody").innerHTML = M.ahead.filter(function (a) { return a.brain != null; }).map(function (a) {
      var g = a.stay - a.brain;
      return "<tr><td>" + a.h + " s</td><td>" + a.brain + " u</td><td>" + a.stay + ' u</td><td style="color:' + (g > 20 ? "var(--bobby)" : "var(--muted)") + '">' + (g > 0 ? "+" : "") + g + " u</td></tr>";
    }).join("");
    var bt = Object.keys(M.target.by_truth).map(function (k) { return [k, M.target.by_truth[k]]; }).sort(function (a, b) { return b[1].n - a[1].n; });
    $("recall").innerHTML = bt.map(function (e) {
      return '<div class="brow"><span>' + (NM[e[0]] || esc(e[0])) + '</span><div class="bline"><i style="width:' + Math.max(2, 70 * e[1].right) +
             '%;background:var(--bobby)"></i><span>' + Math.round(100 * e[1].right) + "% of " + e[1].n + "</span></div></div>";
    }).join("");
    document.querySelector("#misses tbody").innerHTML = M.target.misses.map(function (m) {
      return "<tr><td>" + (NM[m[0]] || esc(m[0])) + "</td><td>" + (NM[m[1]] || esc(m[1])) + "</td><td>" + m[2] + "</td></tr>";
    }).join("");
    var s = $("errline"), x0 = 50, x1 = 940, y0 = 14, y1 = 130, mxe = 2000;
    var X = function (t) { return x0 + (x1 - x0) * t / LEN; }, Y = function (e) { return y1 - (y1 - y0) * Math.min(e, mxe) / mxe; };
    var h = "";
    [0, 500, 1000, 1500, 2000].forEach(function (e) { h += '<line x1="' + x0 + '" x2="' + x1 + '" y1="' + Y(e) + '" y2="' + Y(e) + '" stroke="var(--line)"/><text x="' + (x0 - 6) + '" y="' + (Y(e) + 4) + '" text-anchor="end">' + e + "</text>"; });
    for (var m = 0; m <= LEN + 1; m += 120) h += '<text x="' + X(m) + '" y="' + (y1 + 18) + '" text-anchor="middle">' + mmss(m) + "</text>";
    h += '<polyline points="' + M.err_timeline.map(function (p) { return X(p[0]).toFixed(1) + "," + Y(p[1]).toFixed(1); }).join(" ") + '" fill="none" stroke="var(--bobby)" stroke-width="1.6"/>';
    h += '<text x="' + x0 + '" y="' + (y0 - 2) + '">units</text>';
    s.setAttribute("viewBox", "0 0 960 " + (y1 + 26)); s.innerHTML = h;
  }

  drawWin(); tables(); mindSection();
  var heatNow = function () { if (document.fonts && document.fonts.ready) document.fonts.ready.then(drawHeat); else drawHeat(); };
  heatNow();
  if (window.fetch && G.map) {
    fetch("../maps/" + encodeURIComponent(G.map) + ".json").then(function (r) { return r.ok ? r.json() : null; })
      .then(function (m) { if (m) { MAP = m; heatNow(); } }).catch(function () {});
  }
  if (window.matchMedia) {
    var mq = matchMedia("(prefers-color-scheme: dark)");
    if (mq.addEventListener) mq.addEventListener("change", function () { drawHeat(); drawWin(); });
  }
})();

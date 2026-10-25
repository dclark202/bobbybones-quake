/* The leaderboard site's small helper: a game's time is written in UTC and shown in the viewer's own time when scripts run. */
(function () {
  "use strict";
  var pad = function (n) { return String(n).padStart(2, "0"); };
  [].forEach.call(document.querySelectorAll("time[data-t]"), function (e) {
    var d = new Date(1000 * Number(e.getAttribute("data-t")));
    if (isNaN(d.getTime())) return;
    e.title = e.textContent;
    e.textContent = d.getFullYear() + "-" + pad(d.getMonth() + 1) + "-" + pad(d.getDate()) + " " + pad(d.getHours()) + ":" + pad(d.getMinutes());
  });
})();
/* A history row opens its game report wherever it is clicked (its links still work for a new tab or the keyboard). */
(function () {
  "use strict";
  [].forEach.call(document.querySelectorAll("tr[data-href]"), function (tr) {
    tr.addEventListener("click", function (ev) {
      if (ev.defaultPrevented || ev.button !== 0 || ev.target.closest("a")) return;
      if (window.getSelection && String(window.getSelection())) return;
      var h = tr.getAttribute("data-href");
      if (ev.ctrlKey || ev.metaKey) window.open(h, "_blank"); else location.href = h;
    });
  });
})();

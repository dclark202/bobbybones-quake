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

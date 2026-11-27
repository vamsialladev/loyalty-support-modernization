/* Wakes the Stage 9 live demo, then opens it (LIVE-06). Served from vamsialla.com as /assets/demo-wake.js.
 *
 * The demo runs on Cloud Run with at most one instance and none while idle, so a first visit waits about 10 s while
 * it starts (longer on the day's first visit, when the daily reset runs). This script asks the demo for /login (never /healthz: Cloud Run reserves paths ending in "z" and
 * answers them itself, without waking the instance), waits for any answer, then sends the visitor there.
 *
 * The request is "no-cors": the browser hides the reply from this site, so the script can't tell a working demo
 * from Google's "paused" page (the monthly spending cap). Any answer counts as "awake"; the page says so.
 */
(function () {
  "use strict";
  var link = document.getElementById("wake-link");
  if (!link || !window.fetch) { return; }  // no script support: the visible link still works
  var target = link.href;  // the demo's /login, in the HTML only, so there is one place to change it
  var root = document.documentElement.dataset;
  var retryMs = Number(root.wakeRetryMs || 3000);
  var slowMs = Number(root.wakeSlowMs || 120000);
  var giveUpMs = Number(root.wakeGiveUpMs || 300000);
  var attemptMs = 60000;  // Cloud Run holds the request while the instance starts: one try can take ~20-90 s
  var started = Date.now();
  var status = document.getElementById("wake-status");
  var elapsed = document.getElementById("wake-elapsed");
  var slow = document.getElementById("wake-slow");
  var done = false;

  var timer = window.setInterval(function () {
    var ms = Date.now() - started;
    if (elapsed) { elapsed.textContent = String(Math.floor(ms / 1000)); }
    if (slow && ms >= slowMs) { slow.hidden = false; }
  }, 1000);

  function finish(text) {
    done = true;
    window.clearInterval(timer);
    if (status) { status.textContent = text; }
  }

  function attempt() {
    if (done) { return; }
    if (Date.now() - started >= giveUpMs) {
      finish("The demo didn't answer. It may be paused for the month, or its host may be down. Try the link below later.");
      return;
    }
    var controller = window.AbortController ? new AbortController() : null;
    var cutoff = controller ? window.setTimeout(function () { controller.abort(); }, attemptMs) : null;
    window.fetch(target, {
      mode: "no-cors",
      cache: "no-store",
      credentials: "omit",
      redirect: "follow",
      signal: controller ? controller.signal : undefined
    }).then(function () {
      if (cutoff) { window.clearTimeout(cutoff); }
      finish("Ready. Opening the demo…");
      window.location.replace(target);
    }, function () {
      if (cutoff) { window.clearTimeout(cutoff); }
      window.setTimeout(attempt, retryMs);
    });
  }

  attempt();
})();

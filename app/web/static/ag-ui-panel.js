// The live-run panel (spec G.5; protocols/ag_ui). Watch only: starting stays on the Investigate button.
// Reads the AG-UI 1.0 SSE stream with fetch and shows each event as plain text (textContent only, never HTML).
// The case page refreshes itself with htmx, which replaces the button, so one delegated listener on the document
// handles every click, and a flag keeps it from being added twice when htmx runs this script again.
(function () {
  "use strict";
  if (window.lsmLiveRunBound) { return; }
  window.lsmLiveRunBound = true;
  var list = null;

  function line(text) {
    var item = document.createElement("li");
    item.textContent = text;
    list.appendChild(item);
  }

  function describe(e) {
    switch (e.type) {
      case "RUN_STARTED": return "Watching run " + e.runId;
      case "STATE_SNAPSHOT":
        var run = e.snapshot && e.snapshot.run;
        return "Case " + e.snapshot.case.status + (run ? " · investigation " + run.status : " · no AI run yet");
      case "STEP_STARTED": return "Step: " + e.stepName;
      case "TOOL_CALL_START": return "Tool: " + e.toolCallName + " (" + ((e.metadata && e.metadata.status) || "") + ")";
      case "TEXT_MESSAGE_CONTENT": return "AI summary: " + e.delta;
      case "RUN_FINISHED": return "Finished · engine: " + (e.result && e.result.engine_action) + " · approval happens on this page";
      case "RUN_ERROR": return "Stopped: " + e.message;
      default: return null;
    }
  }

  function id() {
    return (window.crypto && window.crypto.randomUUID) ? window.crypto.randomUUID() : String(Date.now());
  }

  document.addEventListener("click", function (event) {
    var button = event.target && event.target.closest ? event.target.closest("#live-run-watch") : null;
    if (!button || button.disabled) { return; }
    list = document.getElementById("live-run-events");
    if (!list) { return; }
    list.textContent = "";
    button.disabled = true;
    var body = { threadId: button.dataset.thread, runId: id(), messages: [], tools: [], context: [] };
    fetch("/ag-ui/cases/" + encodeURIComponent(button.dataset.case) + "/runs", {
      method: "POST",
      credentials: "same-origin",
      headers: { "Content-Type": "application/json", "Accept": "text/event-stream" },
      body: JSON.stringify(body)
    }).then(function (response) {
      if (!response.ok || !response.body) { line("The live view isn't available (" + response.status + ")."); return null; }
      var reader = response.body.getReader();
      var decoder = new TextDecoder();
      var buffer = "";
      function pump() {
        return reader.read().then(function (chunk) {
          if (chunk.done) { return; }
          buffer += decoder.decode(chunk.value, { stream: true });
          var parts = buffer.split("\n\n");
          buffer = parts.pop();
          parts.forEach(function (part) {
            part.split("\n").forEach(function (row) {
              if (row.indexOf("data: ") !== 0) { return; }  // AG-UI: ignore event:, id: and retry:
              try { var text = describe(JSON.parse(row.slice(6))); if (text) { line(text); } } catch (err) { /* skip */ }
            });
          });
          return pump();
        });
      }
      return pump();
    }).catch(function () { line("The live view stopped. The page shows the current state."); })
      .then(function () { button.disabled = false; });
  });
})();

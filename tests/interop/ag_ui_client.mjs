// One AG-UI run with the official TypeScript client, @ag-ui/client (an independent client; spec G.5, Appendix C M11).
// Called by tests/interop/test_ag_ui_client.py. Settings come from the environment, never from arguments, so the
// test session cookie doesn't appear in a process list:
//   AG_UI_CLIENT_DIR  folder where `npm install --save-exact @ag-ui/client@1.0.4` ran
//   AGUI_URL, AGUI_THREAD, AGUI_RUN_ID, AGUI_START ("1" asks for an investigation), AGUI_COOKIE, AGUI_CSRF
// Prints one JSON line: the event types the client accepted, any RUN_ERROR, any failure, and the final state.
import { readFileSync } from "node:fs";
import { createRequire } from "node:module";
import { join } from "node:path";

const dir = process.env.AG_UI_CLIENT_DIR;
const require = createRequire(join(dir, "package.json"));
const { HttpAgent } = require("@ag-ui/client");
const version = JSON.parse(readFileSync(join(dir, "node_modules", "@ag-ui", "client", "package.json"), "utf8")).version;

const headers = { Accept: "text/event-stream" };
if (process.env.AGUI_COOKIE) headers.Cookie = process.env.AGUI_COOKIE;
if (process.env.AGUI_CSRF) headers["X-CSRF-Token"] = process.env.AGUI_CSRF;

const agent = new HttpAgent({ url: process.env.AGUI_URL, headers, threadId: process.env.AGUI_THREAD });
const types = [];
let runError = null;
let failed = null;
try {
  await agent.runAgent(
    { runId: process.env.AGUI_RUN_ID, forwardedProps: process.env.AGUI_START === "1" ? { start: true } : {} },
    {
      onEvent({ event }) {
        types.push(event.type);
      },
      onRunErrorEvent({ event }) {
        runError = { code: event.code ?? null, message: event.message };
      },
      onRunFailed({ error }) {
        failed = String(error?.message ?? error);
      },
    },
  );
} catch (error) {
  failed = failed ?? String(error?.message ?? error);
}
console.log(JSON.stringify({ client: `@ag-ui/client@${version}`, node: process.version, types, runError, failed, state: agent.state }));

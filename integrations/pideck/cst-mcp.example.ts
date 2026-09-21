import { execFileSync } from "node:child_process";
import { readFileSync } from "node:fs";
import { join } from "node:path";
import { createMcpAdapter } from "pi-mcp-adapter";

// Configure an existing adapter installation; do not install/upgrade on startup.
export default function (pi) {
  const project = process.cwd();
  const id = process.env.PIDECK_SESSION_ID;
  if (!id) throw new Error("A stable PiDeck session ID is required");
  const config = JSON.parse(readFileSync(join(project, ".cst-workspace.json"), "utf8"));
  const backend = JSON.parse(execFileSync(config.python,
    ["-m", "mcp_cst_studio.workbench_service", "ensure", "--project", project, "--session", id],
    { encoding: "utf8", windowsHide: true, env: { ...process.env, PYTHONUTF8: "1", PYTHONPATH: config.source } }));
  return createMcpAdapter({ config: { settings: { hostConfigDiscovery: "off", notifyOnStartupConnect: false },
    mcpServers: { cst: { url: backend.url + "/mcp/", headers: { Authorization: "Bearer " + backend.token },
      httpTransport: "streamable-http", protocolVersion: "legacy", lifecycle: "lazy-keep-alive",
      requestTimeoutMs: 120000, directTools: false } } } })(pi);
}

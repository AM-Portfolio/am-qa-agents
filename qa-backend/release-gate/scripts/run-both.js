/**
 * Start gateway + worker as child processes (local lab).
 * Ctrl+C stops both.
 */
const { spawn } = require("child_process");

const kids = [];

function run(label, args) {
  const child = spawn("python", args, { stdio: "inherit", shell: true });
  child.on("exit", (code) => {
    console.log(`[${label}] exited ${code}`);
    process.exit(code || 0);
  });
  kids.push(child);
}

run("gateway", ["-m", "am_qa_agent.gateway"]);
run("worker", ["-m", "am_qa_agent.orchestrator"]);

function shutdown() {
  for (const c of kids) {
    try {
      c.kill("SIGTERM");
    } catch (_) {}
  }
  process.exit(0);
}

process.on("SIGINT", shutdown);
process.on("SIGTERM", shutdown);

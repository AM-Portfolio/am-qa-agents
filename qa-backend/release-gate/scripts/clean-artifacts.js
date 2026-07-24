/**
 * Remove local artifacts/pdf and sqlite db (keeps .env).
 */
const fs = require("fs");
const path = require("path");

const root = path.join(__dirname, "..");
const targets = [
  path.join(root, "artifacts"),
  path.join(root, ".pytest_cache"),
];

for (const t of targets) {
  if (fs.existsSync(t)) {
    fs.rmSync(t, { recursive: true, force: true });
    console.log("removed", t);
  }
}
console.log("done");

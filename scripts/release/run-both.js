const { spawn } = require("child_process");

function run(name, args) {
  const child = spawn("python", args, { stdio: "inherit", shell: true });
  child.on("exit", (code) => {
    console.error(name + " exited", code);
    process.exit(code || 0);
  });
  return child;
}

run("unified", ["-m", "composition.main"]);

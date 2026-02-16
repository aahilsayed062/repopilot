import { spawn } from "node:child_process";

const host = process.env.HOST || "0.0.0.0";
const port = process.env.PORT || "3000";

const nextBin = process.platform === "win32"
  ? "node_modules\\.bin\\next.cmd"
  : "node_modules/.bin/next";

const child = spawn(nextBin, ["start", "-H", host, "-p", port], {
  stdio: "inherit",
  env: process.env,
});

child.on("exit", (code, signal) => {
  if (signal) {
    process.kill(process.pid, signal);
    return;
  }
  process.exit(code ?? 1);
});

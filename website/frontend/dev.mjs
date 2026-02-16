import http from "node:http";
import next from "next";

const host = process.env.HOST || "0.0.0.0";
const port = Number(process.env.PORT || "3000");

const app = next({
  dev: true,
  hostname: host,
  port,
});

const handle = app.getRequestHandler();

app.prepare().then(() => {
  const server = http.createServer((req, res) => handle(req, res));
  server.listen(port, host, () => {
    console.log(`> Dev server ready on http://${host}:${port}`);
  });
}).catch((error) => {
  console.error("Failed to start Next.js dev server:", error);
  process.exit(1);
});

// Keeps the broker running in local workerd for the installer tests
// (tests/free_address.bats). Usage: node test/e2e/serve.mjs STATE_DIR
//
// When ready, STATE_DIR/ready holds two lines: the broker URL and an
// inspection URL that answers the fake Cloudflare state as JSON (after any
// queued job has finished). Runs until killed.

import { mkdirSync, renameSync, writeFileSync } from "node:fs";
import { createServer } from "node:http";
import { join } from "node:path";
import { startBroker } from "./harness.mjs";

const stateDir = process.argv[2];
if (!stateDir) {
  console.error("usage: node test/e2e/serve.mjs STATE_DIR");
  process.exit(2);
}
mkdirSync(stateDir, { recursive: true });

const b = await startBroker();
const inspect = createServer(async (_req, res) => {
  await b.settle();
  res.writeHead(200, { "Content-Type": "application/json" });
  res.end(JSON.stringify(b.fake.snapshot()));
});
await new Promise((ok) => inspect.listen(0, "127.0.0.1", ok));
const inspectUrl = `http://127.0.0.1:${inspect.address().port}/state`;

const tmp = join(stateDir, "ready.tmp");
writeFileSync(tmp, `${b.url}\n${inspectUrl}\n`);
renameSync(tmp, join(stateDir, "ready"));
console.log(`broker ${b.url}  inspect ${inspectUrl}`);

const stop = async () => {
  inspect.close();
  await b.close();
  process.exit(0);
};
process.on("SIGTERM", stop);
process.on("SIGINT", stop);

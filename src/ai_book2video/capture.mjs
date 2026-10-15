// Render frames of a motion page. The page must define window.setT(seconds).
// usage: node capture.mjs <page.html> <outdir> <width> <height> <chrome> <times.json>
// times.json is an array of seconds; frame i is saved as f<i padded to 5>.jpg in outdir.
import { spawn } from "node:child_process";
import { mkdirSync, mkdtempSync, readFileSync, rmSync, writeFileSync } from "node:fs";
import { tmpdir } from "node:os";
import { join, resolve } from "node:path";
import { pathToFileURL } from "node:url";

const [page, outdir, widthArg, heightArg, chrome, timesFile] = process.argv.slice(2);
const width = Number(widthArg);
const height = Number(heightArg);
const times = JSON.parse(readFileSync(timesFile, "utf8"));
mkdirSync(outdir, { recursive: true });

const profile = mkdtempSync(join(tmpdir(), "b2v-chrome-"));
const browser = spawn(
  chrome,
  ["--headless=new", "--no-sandbox", "--disable-gpu", "--hide-scrollbars", "--remote-debugging-port=0",
    `--user-data-dir=${profile}`, `--window-size=${width},${height}`, "about:blank"],
  { stdio: ["ignore", "ignore", "pipe"] },
);

const port = await new Promise((resolvePort, reject) => {
  let buffer = "";
  const timer = setTimeout(() => reject(new Error("Chrome did not report a DevTools port")), 20000);
  browser.stderr.on("data", (chunk) => {
    buffer += chunk.toString();
    const match = buffer.match(/DevTools listening on ws:\/\/127\.0\.0\.1:(\d+)\//);
    if (match) { clearTimeout(timer); resolvePort(match[1]); }
  });
  browser.on("exit", (code) => reject(new Error(`Chrome exited early (${code})`)));
});

const targets = await (await fetch(`http://127.0.0.1:${port}/json/list`)).json();
const target = targets.find((item) => item.type === "page");
const socket = new WebSocket(target.webSocketDebuggerUrl);
await new Promise((ok, fail) => { socket.onopen = ok; socket.onerror = fail; });

let nextId = 1;
const pending = new Map();
socket.onmessage = (event) => {
  const message = JSON.parse(event.data);
  if (message.method === "Runtime.exceptionThrown") {
    console.error("page error:", message.params.exceptionDetails.exception?.description ?? message.params.exceptionDetails.text);
  }
  if (message.id && pending.has(message.id)) {
    const { ok, fail } = pending.get(message.id);
    pending.delete(message.id);
    if (message.error) fail(new Error(message.error.message)); else ok(message.result);
  }
};
const send = (method, params = {}) => new Promise((ok, fail) => {
  const id = nextId++;
  pending.set(id, { ok, fail });
  socket.send(JSON.stringify({ id, method, params }));
});

const evaluate = async (expression) => {
  const result = await send("Runtime.evaluate", { expression, awaitPromise: true, returnByValue: true });
  if (result.exceptionDetails) throw new Error(result.exceptionDetails.exception?.description ?? "evaluate failed");
  return result.result.value;
};

try {
  await send("Page.enable");
  await send("Runtime.enable");
  await send("Emulation.setDeviceMetricsOverride", { width, height, deviceScaleFactor: 1, mobile: false });
  await send("Page.navigate", { url: pathToFileURL(resolve(page)).href });
  for (let attempt = 0; attempt < 200; attempt++) {
    if ((await evaluate("document.readyState")) === "complete" && (await evaluate("typeof window.setT")) === "function") break;
    await new Promise((ok) => setTimeout(ok, 50));
  }
  const digits = String(times.length).length > 5 ? String(times.length).length : 5;
  for (let index = 0; index < times.length; index++) {
    await evaluate(`window.setT(${Number(times[index]).toFixed(4)}); true`);
    const shot = await send("Page.captureScreenshot", { format: "jpeg", quality: 92, captureBeyondViewport: false });
    writeFileSync(join(outdir, `f${String(index).padStart(digits, "0")}.jpg`), Buffer.from(shot.data, "base64"));
  }
  console.log(`captured ${times.length} frames`);
} finally {
  socket.close();
  await new Promise((done) => {
    browser.once("exit", done);
    browser.kill("SIGKILL");
    setTimeout(done, 1500);
  });
  try { rmSync(profile, { recursive: true, force: true }); } catch { /* Chrome may still hold a lock; the temp folder is harmless */ }
}

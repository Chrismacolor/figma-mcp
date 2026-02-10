import * as esbuild from "esbuild";
import * as fs from "fs";
import * as path from "path";

const isWatch = process.argv.includes("--watch");

// Build code.ts -> dist/code.js
const codeBuild = {
  entryPoints: ["src/code.ts"],
  bundle: true,
  outfile: "dist/code.js",
  format: "iife",
  target: "es2015",
  logLevel: "info",
};

// Build ui.ts -> temp file, then inline into dist/ui.html
const uiBuild = {
  entryPoints: ["src/ui.ts"],
  bundle: true,
  outfile: "dist/ui.js.tmp",
  format: "iife",
  target: "es2015",
  logLevel: "info",
};

function inlineHtml() {
  const js = fs.readFileSync("dist/ui.js.tmp", "utf-8");
  const html = `<!DOCTYPE html>
<html>
<head>
  <style>
    * { box-sizing: border-box; margin: 0; padding: 0; }
    body { font-family: Inter, system-ui, sans-serif; font-size: 12px; padding: 12px; background: #2c2c2c; color: #e0e0e0; }
    .field { margin-bottom: 8px; }
    .field label { display: block; margin-bottom: 2px; color: #aaa; font-size: 11px; }
    .field input { width: 100%; padding: 6px 8px; border: 1px solid #555; border-radius: 4px; font-size: 12px; background: #3a3a3a; color: #e0e0e0; }
    .field input:focus { outline: none; border-color: #0d99ff; }
    button { padding: 6px 14px; border: none; border-radius: 4px; font-size: 12px; cursor: pointer; }
    #connectBtn { background: #0d99ff; color: white; width: 100%; }
    #connectBtn:hover { background: #0b87e0; }
    #connectBtn.connected { background: #e74c3c; }
    #connectBtn.connected:hover { background: #c0392b; }
    .status { display: flex; align-items: center; gap: 6px; margin: 10px 0; font-size: 11px; }
    .dot { width: 8px; height: 8px; border-radius: 50%; }
    .dot.off { background: #666; }
    .dot.on { background: #2ecc71; }
    .dot.error { background: #e74c3c; }
    #log { margin-top: 8px; padding: 6px; background: #1e1e1e; border-radius: 4px; max-height: 200px; overflow-y: auto; font-family: monospace; font-size: 10px; line-height: 1.5; color: #bbb; }
    .log-entry { border-bottom: 1px solid #333; padding: 2px 0; }
  </style>
</head>
<body>
  <div class="field">
    <label>Server URL</label>
    <input id="serverUrl" value="http://localhost:8400" />
  </div>
  <div class="field">
    <label>Auth Token</label>
    <input id="authToken" placeholder="Paste token from server output" />
  </div>
  <button id="connectBtn">Connect</button>
  <div class="status">
    <span class="dot off" id="statusDot"></span>
    <span id="statusText">Disconnected</span>
  </div>
  <div id="log"></div>
  <script>${js}</script>
</body>
</html>`;
  fs.mkdirSync("dist", { recursive: true });
  fs.writeFileSync("dist/ui.html", html);
  try { fs.unlinkSync("dist/ui.js.tmp"); } catch {}
  console.log("  dist/ui.html written");
}

async function build() {
  if (isWatch) {
    const codeCtx = await esbuild.context(codeBuild);
    const uiCtx = await esbuild.context({
      ...uiBuild,
      plugins: [{
        name: "inline-html",
        setup(build) {
          build.onEnd(() => inlineHtml());
        },
      }],
    });
    await codeCtx.watch();
    await uiCtx.watch();
    console.log("Watching for changes...");
  } else {
    await esbuild.build(codeBuild);
    await esbuild.build(uiBuild);
    inlineHtml();
  }
}

build().catch((e) => { console.error(e); process.exit(1); });

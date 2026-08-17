// validate-mermaid.mjs
//
// Standalone Mermaid syntax validator. Reads a JSON array of {file, line, code}
// objects from stdin (one per fenced mermaid block), calls mermaid.parse() for
// each, and prints a JSON array of {file, line, status, error?} to stdout.
//
// Designed for the crackerjack CI guard (test_mermaid_renders.py +
// `crackerjack docs check-mermaid`). Uses mermaid.parse() — the lexer-only
// path — so it does NOT need a Chrome/Puppeteer runtime. The mermaid v11
// library still loads DOMPurify and `addHook` at import time, so we set up
// a minimal DOM via jsdom before importing mermaid.
//
// Run:
//   node validate-mermaid.mjs <path-to-mermaid-core.mjs> [<path-to-jsdom>]
//
// The Python wrapper (crackerjack.services.mermaid_renderer) computes both
// absolute paths and passes them as argv[2] and argv[3]. Each path is loaded
// via dynamic `import()` because Node ESM does NOT honor NODE_PATH for
// static imports (v18+).

const mermaidPath = process.argv[2];
const jsdomPath = process.argv[3];
if (!mermaidPath) {
  console.error(
    "usage: node validate-mermaid.mjs <path-to-mermaid-core.mjs> [<path-to-jsdom>]",
  );
  process.exit(2);
}
if (!jsdomPath) {
  console.error(
    "jsdom path is required: Mermaid v11 needs a DOM environment. " +
      "Install jsdom (npm install --save-dev jsdom) and pass the path " +
      "as argv[3].",
  );
  process.exit(2);
}

// Set up a minimal DOM before importing mermaid. Mermaid v11's parse()
// pipeline calls DOMPurify.addHook at import time, which requires
// window/document globals to exist. Node 26 makes some properties
// (e.g. `navigator`) read-only, so we use defineProperty for the ones
// that aren't writable on the global object.
const { JSDOM } = await import(jsdomPath);
const dom = new JSDOM("<!DOCTYPE html><html><body></body></html>", {
  url: "http://localhost/",
  pretendToBeVisual: true,
});
const { window } = dom;

function setGlobal(name, value) {
  try {
    globalThis[name] = value;
  } catch (e) {
    if (e instanceof TypeError) {
      // Read-only property; use defineProperty to override.
      Object.defineProperty(globalThis, name, {
        value,
        writable: true,
        configurable: true,
        enumerable: true,
      });
    } else {
      throw e;
    }
  }
}

setGlobal("window", window);
setGlobal("document", window.document);
setGlobal("navigator", window.navigator);
setGlobal("HTMLElement", window.HTMLElement);
setGlobal("Element", window.Element);
setGlobal("Node", window.Node);
setGlobal("DOMParser", window.DOMParser);
setGlobal("MutationObserver", window.MutationObserver);
setGlobal("getComputedStyle", window.getComputedStyle.bind(window));
setGlobal("requestAnimationFrame", (cb) => setTimeout(() => cb(0), 0));
setGlobal("cancelAnimationFrame", (id) => clearTimeout(id));

const mermaid = (await import(mermaidPath)).default;

const blocks = await new Promise((resolve, reject) => {
  let data = "";
  process.stdin.setEncoding("utf8");
  process.stdin.on("data", (chunk) => (data += chunk));
  process.stdin.on("end", () => {
    try {
      resolve(JSON.parse(data));
    } catch (e) {
      reject(new Error(`invalid JSON on stdin: ${e.message}`));
    }
  });
  process.stdin.on("error", reject);
});

const results = [];
for (const { file, line, code } of blocks) {
  try {
    await mermaid.parse(code);
    results.push({ file, line, status: "ok" });
  } catch (e) {
    const message = e?.message ?? String(e);
    // mermaid.parse() emits errors as strings; trim to first line for readability
    const trimmed = String(message).split("\n")[0].slice(0, 500);
    results.push({ file, line, status: "error", error: trimmed });
  }
}

process.stdout.write(JSON.stringify(results));

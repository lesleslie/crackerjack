// validate-mermaid.mjs
//
// Standalone Mermaid syntax validator. Reads a JSON array of {file, line, code}
// objects from stdin (one per fenced mermaid block), calls mermaid.parse() for
// each, and prints a JSON array of {file, line, status, error?} to stdout.
//
// Designed for the crackerjack CI guard (test_mermaid_renders.py +
// `crackerjack docs check-mermaid`). Uses mermaid.parse() — the lexer-only
// path — so it does NOT need a Chrome/Puppeteer runtime. Just Node.js + the
// mermaid npm package.
//
// Run:
//   node validate-mermaid.mjs <path-to-mermaid-core.mjs>
//
// The Python wrapper (crackerjack.services.mermaid_renderer) computes the
// absolute path to mermaid/dist/mermaid.core.mjs from the `mmdc` symlink
// and passes it as argv[2]. The path lookup uses Node's dynamic
// `import()` (parameterized) rather than a static `import` statement, because
// Node ESM does NOT honor NODE_PATH for static imports in v18+.

const mermaidPath = process.argv[2];
if (!mermaidPath) {
  console.error("usage: node validate-mermaid.mjs <path-to-mermaid-core.mjs>");
  process.exit(2);
}

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

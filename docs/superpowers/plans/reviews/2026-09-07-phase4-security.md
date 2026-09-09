# Security Lens Review — Crackerjack Phase 4 (Web) Plan

**Plan:** `/Users/les/Projects/crackerjack/docs/superpowers/plans/2026-09-07-crackerjack-multi-language-phase4.md`
**Spec:** `/Users/les/Projects/crackerjack/docs/superpowers/specs/2026-09-07-crackerjack-multi-language-design.md` (Rev 2)
**Precedent:** `/Users/les/Projects/crackerjack/docs/superpowers/plans/reviews/2026-09-07-phase3-security.md`
**Reviewer lens:** Security (subprocess safety, hybrid fallback auth, `project_root` validation, symlink traversal, parser safety)
**Review date:** 2026-09-09

## Summary

The plan correctly carries forward the Phase 2/3 security controls for subprocess argv lists (no `shell=True`), the `_validate_project_root` allowlist, and `_require_auth_config` for mutation. However, **three new critical exposures** are introduced by Phase 4 specifically: (1) **symlink traversal** in `format_jinja_templates` allows reading and overwriting files outside the validated `project_dir`; (2) the **`eslint_tsc` hook is broken** — a literal `;` token in an argv list is not interpreted as a command separator by `subprocess.run`, so `tsc --noEmit` never executes; (3) **glob patterns** (`**/*.css`, `**/*.html`) are passed as literal argv elements that `subprocess.run` will not expand. Two Phase 2/3 carry-over bugs (inverted `_validate_project_root` allowlist, config-only auth) are inherited without fix. Two MEDIUM parser-safety issues (`html_fallback` ReDoS surface, `format_jinja_templates` error-message leakage) need pre-implementation test coverage.

3 HIGH findings, 4 MEDIUM findings, 3 LOW findings, 4 INFO confirmations. No BLOCKER (the broken `eslint_tsc` hook is a HIGH because it silently disables half the Web lint coverage, not because of direct compromise).

---

## Findings (most-severe first)

### F-1 [HIGH] `format_jinja_templates` symlink traversal — reads and writes outside `project_dir`

**Location:** Task 6 Step 3 line 1221-1234 (`format_jinja_templates` tool body). `Path(project_dir).rglob("*")` followed by `path.read_text()` / `path.write_text(formatted)`.

**What's wrong.** The MCP tool calls `_validate_project_root(p)` for each `projects` entry, then walks each directory with `Path(project_dir).rglob("*")`. `rglob` does NOT resolve symlinks during enumeration — it yields the symlink path itself. The subsequent checks `if not path.is_file() or path.suffix not in {".html", ".j2", ".jinja"}: continue` use `path.is_file()`, which **follows symlinks** and returns `True` if the symlink target is a regular file. `path.read_text()` and `path.write_text()` also follow symlinks.

**Attack chain.**

1. Attacker controls a directory `templates/` anywhere under a validated `project_root` (or — per Phase 3 F-2 — a path outside the allowlist when `MAHAVISHNU_PROJECT_ROOTS` is unset, since the validator is inverted).
2. Attacker places `templates/secret → /Users/les/.ssh/id_rsa` (symlink).
3. Attacker calls `format_jinja_templates(projects=["templates"])`.
4. `rglob("*")` yields `templates/secret`; `is_file()` returns `True` (target exists); `path.suffix` is empty — wait, this is wrong. `Path("templates/secret").suffix` is `""` because the symlink has no `.html`/`.j2`/`.jinja` suffix. So this exact chain doesn't work.

**Refined attack chain.** Attacker creates `templates/innocent.html → /etc/something` (the suffix is on the symlink name itself). The `.suffix` check passes; `read_text()` reads through the symlink target. The file content is then lexed, formatted, and **written back through the symlink** — overwriting `/etc/something` with the formatted version. If `/etc/something` is `/etc/nginx/nginx.conf` or any other config file the crackerjack process has write access to, the file is overwritten with Jinja-template-shaped content.

**Why it matters.** Combined with the `_validate_project_root` inverted-allowlist bug (F-2) and the auth config-only posture (F-3), the attacker's directory can live anywhere on disk. The MCP tool mutates files outside the intended scope, breaking the integrity guarantee of the `project_root` allowlist. The auth check (`_require_auth_config`) gates who can call the tool but not what files the tool touches.

**How to fix.**

1. In `format_jinja_templates`, after the `is_file()` check, add `if path.is_symlink(): continue` (or raise `ValueError("symlink not allowed")` per the threat model).
2. Better: use `path.resolve(strict=True)` and assert `resolved.is_relative_to(project_root.resolve())`. Skip (or raise) when not relative.
3. Add a test asserting `format_jinja_templates` raises (or skips) when a symlink in `templates/` points outside `templates/`.
4. Add a test asserting the resolved path of every written file is a descendant of the resolved `project_dir`.

---

### F-2 [HIGH] Inherited Phase 2/3 F-2: `_validate_project_root` is inverted when `MAHAVISHNU_PROJECT_ROOTS` unset

**Location:** Plan line 36 (Global Constraints: "Phase 3 fixed `_validate_project_root` to fail-closed"). Task 6 Step 3 line 1216 (`for p in projects: _validate_project_root(p)`).

**What's wrong.** Phase 3 security review F-2 documented that `_validate_project_root` is inverted: when `MAHAVISHNU_PROJECT_ROOTS` is unset (the default in dev / single-tenant setups), the function silently accepts any path. The Phase 4 plan's Global Constraint (line 36) states "Phase 3 fixed `_validate_project_root` to fail-closed" — but Phase 3 review F-2 found no fix was made. Phase 4 inherits the unfixed helper.

**Why it matters.** Both new MCP tools (`check_web_lint`, `format_jinja_templates`) call `_validate_project_root(project_root)` / `_validate_project_root(p)`. When the env var is unset, the allowlist is empty, the inverted logic allows the call through, and `format_jinja_templates` mutates files anywhere on disk (compounded by F-1). `check_web_lint` reads package.json and pyproject.toml from any path — disclosing local project metadata to the MCP caller.

**How to fix.**

1. Re-read `crackerjack/mcp/tools/_project_root_validator.py` (or wherever the helper lives; plan doesn't cite the exact path). Flip the empty-allowlist branch to deny (`if not allowlist: raise PermissionError("MAHAVISHNU_PROJECT_ROOTS not configured; refusing all project paths")`).
2. Add the regression test Phase 3 review F-2 recommended: `_validate_project_root("/tmp/foo")` raises when env var unset.
3. Update Plan line 36 to accurately reflect the post-fix state, OR add a "carry-over fix" Task 0 that addresses both Phase 2 final-review IMPORTANT-1 and Phase 3 review F-2 before Phase 4 ships.

---

### F-3 [HIGH] Inherited Phase 2/3 F-1: `_require_auth_config` is config-only, no JWT validation

**Location:** Task 6 Step 3 line 1214 (`_require_auth_config()`). Global Constraints line 36 ("Phase 3 fixed `_validate_project_root` to fail-closed" — also implies `_require_auth_config` is correctly enforced).

**What's wrong.** Phase 3 security review F-1 documented that `_require_auth_config` only checks env-var presence (`MAHAVISHNU_AUTH_ENABLED=true` + `MAHAVISHNU_JWT_SECRET` non-empty) and performs no JWT decode, signature verification, expiry, or audience check. Any process that sets the two env vars gets full mutation authority. The plan line 36 wording implies the helper is correctly enforcing auth; it is not.

**Why it matters.** `format_jinja_templates` overwrites template files (F-1 chain). With auth config-only, a local process that can `export MAHAVISHNU_AUTH_ENABLED=true MAHAVISHNU_JWT_SECRET=x` and invoke the MCP server gets full write authority. The MCP server runs as a long-lived process; env vars set at startup persist. Combined with F-2 (allowlist inverted), a single-tenant dev setup has no auth barrier at all.

**How to fix.**

1. Add a JWT decode call inside `_require_auth_config`: `jwt.decode(token, secret, algorithms=["HS256"], audience=..., options={"require": ["exp"]})`. Token must come from the request, not env vars; reject missing/invalid/expired tokens with `PermissionError`.
2. Add a test: a token signed with a different secret raises `PermissionError`.
3. Bind the validated `sub` claim into log lines and (eventually) into formatter metadata.
4. Until JWT validation lands, the helper name `_require_auth_config` is honest (it checks config) but does not satisfy the spec's "auth posture" intent. Update Plan line 36 to clarify.

---

### F-4 [HIGH] `eslint_tsc` hook has broken argv list — literal `;` token does not chain commands

**Location:** Task 3 Step 5 line 582-587 (`_eslt_hook`).

**What's wrong.** The combined `eslint + tsc` hook builds the argv list with a literal `;` token:

```python
cmd = _npx_command("eslint", ".", "--ext", ".ts,.tsx,.js,.jsx") + (";", "tsc", "--noEmit")
# Produces: ("npx", "--no-install", "eslint", ".", "--ext", ".ts,.tsx,.js,.jsx", ";", "tsc", "--noEmit")
```

`subprocess.run` with an argv list does not interpret `;` as a command separator — it tries to execute a binary literally named `;`. The hook fails (likely with `FileNotFoundError` from the missing `;` binary) and **never invokes `tsc --noEmit`**.

The plan line 357-358 even acknowledges this: *"cli_command encodes both eslint and tsc invocations (combined as fallback chain)"* — the comment hints at the intent but the implementation is broken.

**Why it matters.** The hook silently fails half of its declared coverage. Users running `check_web_lint` on a TS project see ESLint pass/fail and think TypeScript was also checked — but `tsc` never ran. The "combined" hook is a lie.

Additionally, even if the `;` token were correctly chained (it isn't), passing it through an argv list conflates command chaining with command injection. The same construction in a different shape (e.g., `; rm -rf /` somewhere in a future hook) would be syntactically suspect. A future contributor reading the code might think the `;` is harmless because `subprocess.run` doesn't interpret it — but the precedent of "literal separator tokens in argv lists" is bad.

**How to fix.**

1. **Split the hook.** Make `web.eslint_tsc` two separate `Hook` entries (`web.eslint` and `web.tsc`) in the `Hooks` tuple. The runner iterates and runs each independently. Each has a proper argv list.
2. OR: encode as a shell script wrapper that the runner invokes. But that requires `shell=True`, which violates the global constraint.
3. Add a test asserting `web.tsc` (or `web.eslint_tsc`) actually invokes `tsc` — currently the test asserts only that `"tsc"` appears as a substring of `cli_command`, which passes for a broken hook.
4. Drop the `;` token construction from the plan entirely.

---

### F-5 [MEDIUM] Glob patterns (`**/*.css`, `**/*.html`) passed as literal argv elements — no shell expansion, behavior depends on tool's glob handling

**Location:** Task 3 Step 5 line 569, 592 (`_npx_command("stylelint", "**/*.css")`, `_npx_command("html-validate", "**/*.html")`).

**What's wrong.** With argv lists, `subprocess.run` does NOT expand globs — the literal string `**/*.css` is passed to `stylelint`. Whether stylelint interprets the glob depends on the tool: stylelint does expand globs internally (it accepts glob patterns as input), html-validate may behave differently. The current argv-list pattern is correct in principle, but the plan should explicitly note that the tool is expected to expand the glob, not the shell.

For `npx`, the additional concern: `npx --no-install stylelint '**/*.css'` — `npx` runs `stylelint` as a binary and forwards argv. Whether `stylelint` itself expands the glob depends on the tool version. If a user has a file literally named `**/*.css` (highly unusual, but possible), stylelint would target that single file.

**Why it matters.** Behavior divergence across tools is a maintenance hazard. When tests pass with one version of `stylelint` and break with another, the root cause is hard to find.

**How to fix.**

1. Document the per-tool glob-expansion contract in the hook docstring: "stylelint expands the glob internally; do not rely on shell expansion."
2. Add an integration test asserting the hook actually lints a multi-file fixture, not just a single literal `**/*.css` file.
3. Alternative: drop the glob and let the tool default to its project-root scan (most linters auto-discover). Less precise, but more portable.

---

### F-6 [MEDIUM] `html_fallback` regex — ReDoS surface on pathological input

**Location:** Task 3 Step 4 line 495 (`html_fallback`).

**What's wrong.** The fallback regex `re.finditer(r"<!--|</?([a-zA-Z][a-zA-Z0-9]*)\b[^>]*?>|>", content)` has the lazy quantifier `[^>]*?` and the alternation `<!--|...|...`. On pathological input — e.g., a long string of `<` characters with no closing `>` — each `<` starts a new attempt; the `[^>]*?` tries to match empty, then advances. Python's `re` engine has linear worst-case for this particular pattern in practice, but the alternation between `<!--` and the tag pattern creates a backtracking surface.

In `css_fallback` (line 455): `re.finditer(r"[^{}]+\{\s*\}", content)` — simpler, no ReDoS surface.

In `js_ts_fallback` (line 461-482): no regex — manual char loop. Safe.

**Why it matters.** `html_fallback` is invoked when `html-validate` CLI is missing. The tool runs against attacker-influenceable file content (a malicious HTML file in the project). The fallback is supposed to be a safety net; a 10-second hang on a 1MB file is a DoS.

**How to fix.**

1. Add an adversarial test: `html_fallback` on `content = "<" * 1_000_000` should complete in <1 second.
2. Bound the regex: replace `[^>]*?` with `[^>]{0,1000}?` (cap at 1000 chars per attempt). Or use a non-backtracking approach: split content on `<` and process linearly.
3. Alternative: drop the regex entirely and use a hand-rolled state machine (same as `js_ts_fallback`). Slightly more code, no regex surface.

---

### F-7 [MEDIUM] `format_jinja_templates` error path leaks `OSError` details (path, errno, strerror)

**Location:** Task 6 Step 3 line 1232-1233 (`except (OSError, UnicodeDecodeError) as exc: errors.append({"path": str(path), "error": str(exc)})`).

**What's wrong.** `OSError` and `UnicodeDecodeError` stringify to messages like `[Errno 13] Permission denied: '/Users/les/private/secrets.txt'`. The MCP tool returns these errors verbatim to the caller. If `format_jinja_templates` is invoked against a project that contains symlinks pointing to sensitive paths (per F-1), the error path can leak the full target path and errno.

**Why it matters.** Combined with F-1 (symlink traversal), the error message confirms which symlink targets are reachable. In multi-tenant MCP deployments, this is an information disclosure.

**How to fix.**

1. Sanitize the error message: `error = type(exc).__name__` only, or a short canned message ("file read failed").
2. Log the full exception via `logger.exception(...)` (per Global Constraint line 28), and return only the safe summary to the caller.
3. Test that `str(exc)` is NOT present in the tool's return value when an `OSError` is raised.

---

### F-8 [MEDIUM] `npx --no-install` does not fully prevent supply-chain fetch

**Location:** Task 3 Step 5 line 549 (`_npx_command`).

**What's wrong.** `npx --no-install` prevents npx from **auto-installing** missing packages, but it does not prevent npx from contacting the npm registry for known packages. If the project's `package.json` declares `stylelint` in `devDependencies` but the lockfile is missing or out-of-date, npx can still fetch from the registry. The `--no-install` flag is a partial mitigation, not a full sandbox.

More importantly: when `package.json` pins the version (the `_has_pinned_version` branch), the plan invokes `stylelint` (not `npx`) directly. The plan assumes `stylelint` is on `PATH` — which is only true if the user has a global install. If `shutil.which("stylelint")` returns the global install, the lockfile is bypassed entirely.

**Why it matters.** The plan's `npx --no-install` is documented as a "supply chain mitigation" in spirit, but it's actually a behavior-mode flag for npx. The supply-chain guarantee depends on the lockfile being checked — which the plan doesn't enforce.

**How to fix.**

1. Document explicitly: "Supply chain safety depends on the user maintaining a lockfile (`package-lock.json`, `pnpm-lock.yaml`, or `yarn.lock`). crackerjack does NOT enforce this."
2. Optional: add a pre-flight check that a lockfile exists when the project has a `package.json`. Warn (not fail) if missing.
3. The pinned-version branch (`_has_pinned_version`) should resolve the binary from `node_modules/.bin/` rather than relying on global `PATH`. Add `(project_root / "node_modules" / ".bin" / "stylelint")` as a `shutil.which`-equivalent lookup.

---

### F-9 [LOW] `_has_pinned_version` reads entire `package.json` for one field — DoS surface on huge files

**Location:** Task 3 Step 5 line 553-564 (`_has_pinned_version`).

**What's wrong.** `data = json.loads(pkg.read_text())` reads the entire `package.json` into memory just to look up one key in `devDependencies`. A 1GB `package.json` (unlikely but possible via a malicious or malformed file) consumes 1GB of RAM. `json.loads` is bounded by Python's recursion limit but not by file size.

**Why it matters.** Low likelihood in practice (most `package.json` files are <10KB), but the parser is invoked once per hook creation (3 times per Web project). On a CI server processing many Web projects, repeated large reads compound.

**How to fix.**

1. Stream-parse with `ijson` (third-party dep) or use `json.JSONDecoder().raw_decode()` after a small buffer read.
2. Cap the read: `pkg.read_text()[:1_000_000]` with a truncation warning if exceeded.
3. Add a test: a 50MB `package.json` does not cause OOM.

---

### F-10 [LOW] TOML detection has no file-size guard

**Location:** Task 2 Step 3 line 273-277 (`tomllib.load(f)`).

**What's wrong.** `tomllib.load(f)` reads the entire `pyproject.toml` to parse it. Same DoS surface as F-9. Python's `tomllib` is reasonably efficient, but a 100MB `pyproject.toml` consumes significant memory.

**Why it matters.** Lower than F-9 because `pyproject.toml` is typically <50KB. Still worth a size guard for adversarial cases.

**How to fix.**

1. Same as F-9: cap the read size, warn on truncation.
2. Document: `tomllib` is the safest option; no code-execution risk.

---

### F-11 [LOW] `_env()` in `jinja_formatter.py` does not validate delimiter kwargs

**Location:** Task 4 Step 4 line 823-832 (`_env`).

**What's wrong.** If a future MCP caller passes `delimiters={"block_start": "", "block_end": ""}`, `jinja2.Environment(block_start_string="", block_end_string="", ...)` raises `TemplateSyntaxError`. The plan's `format_template` catches `TemplateSyntaxError` and returns `source` unchanged (line 858-860) — that's a safe fallback. But if a caller passes partial overlap (e.g., `block_start = "%}"` and `block_end = "%}"`), the Environment may accept it but produce garbage tokens. `lex()` doesn't evaluate, so no code execution — but the formatter silently corrupts output.

**Why it matters.** Currently `format_jinja_templates` calls `format_template` with default delimiters (no user input). Low exposure today, but if delimiters become an MCP argument, validation is needed.

**How to fix.**

1. Add a `_validate_delimiters(delims)` helper that asserts no empty strings, no overlapping delimiters, and all 6 keys present.
2. If/when delimiters become an MCP argument, gate them through the validator.
3. Add a test: `format_template(src, delimiters={"block_start": ""})` raises `ValueError` (or returns `source` with a warning logged).

---

### F-12 [INFO] `shell=True` is absent everywhere

**Verified.** All 4 subprocess invocations in the plan (Task 3 `_npx_command` + `subprocess.run` in `run_hook_with_fallback`; no Phase 4 gradlew / git / gh calls) use argv lists. ✓

---

### F-13 [INFO] Argv lists are used throughout Task 3

**Verified.** `_npx_command("stylelint", "**/*.css")` returns a tuple. `subprocess.run(cmd, ...)` consumes the tuple. The broken `;` token (F-4) is the only argv-list anomaly. ✓

---

### F-14 [INFO] `--` separator before user-influenced positionals

**Verified.** `cmd.append(str(project_root))` appends after the tool args; `cmd.extend(str(p) for p in file_paths)` appends user paths at the end. No tool in Task 3 accepts `--` explicitly, so the user paths can't be interpreted as flags by stylelint/eslint/tsc/html-validate (none of them have a flag starting with a path-like prefix that would be ambiguous). ✓ (with caveat: see F-5 for the glob pattern issue)

---

### F-15 [INFO] `lex()` is tokenizer-only, no code execution

**Verified.** `jinja2.Environment.lex()` returns `(lineno, token_type, value)` tuples. It does not parse, compile, or evaluate. `TemplateSyntaxError` on bad delimiters is caught. ✓

---

## Coverage Statement

This review covered:

- All 4 subprocess invocations in Task 3 (the 3 hook builders + `run_hook_with_fallback`) — argv list vs. shell, glob handling, returncode ambiguity, broken `;` token.
- All MCP mutation surfaces in Task 6 — auth check order, path validation, symlink traversal, error leakage.
- All Python fallbacks in Task 3 Step 4 — regex ReDoS surface, error handling consistency.
- Jinja formatter in Task 4 — delimiter validation, lex() safety, environment construction.
- Configuration parsing in Task 2 (TOML) and Task 3 (JSON) — DoS surface, parser safety.
- Phase 2/3 carry-over: 2 of 13 prior security findings are correctly inherited (no shell, argv lists); 2 are inherited without fix (inverted allowlist, config-only auth).

**Out of scope:**

- Test fixtures (Task 7) — no security surface beyond F-1 symlink test.
- CHANGELOG entry — documentation, no security impact.
- Pyproject entry-point declaration (Task 1) — minimal surface, no security risk.
- PyCharm parity (deferred to Phase 4.5) — not in Phase 4 scope.
- Web detection guard itself — not a subprocess concern; covered by other lenses.
- Spec consistency with Phase 2/3 — covered by other lenses.

---

## Spec Coverage Summary

| Spec Requirement | Plan Coverage | Verdict |
|---|---|---|
| **MCP F5** — auth posture for mutation tools | Stated; helper is config-only (Phase 3 F-1 carry-over) | Partial — F-3 |
| **Security F2** — `_validate_project_root` allowlist | Stated; inverted semantics inherited | Partial — F-2 |
| **Writing F2** — hybrid fallback, single interpretation | Stated; canonical in `run_hook_with_fallback` | ✓ |
| **Jinja F1** — `lex()` not `parse()`, preserves comments | Implemented in Task 4 Step 4 | ✓ |
| **Jinja F2** — all 6 delimiter kwargs | Implemented | ✓ |
| **Jinja F11** — explicit `jinja2>=3.1.6` dep | Task 1 Step 3 | ✓ |
| **Web detection guard (Writing F3)** | Task 2 Step 3, package.json OR pyproject opt-in | ✓ |
| **Subprocess safety** | argv lists everywhere; `--no-install` partial supply-chain mitigation | ✓ (with caveats — F-5, F-8) |
| **Round-trip invariant (Testing F9)** | Test in Task 4 Step 2 | ✓ |
| **Spec 2-tier canonical policy (Jinja F3)** | Tier 1 always-on, Tier 2 opt-in | ✓ |

---

## Plan Quality Verdict

**Verdict: Implementable after addressing the 3 HIGH findings.**

The Phase 4 plan is structurally sound: argv lists are correct everywhere except for the broken `;` token, the auth check is at least present, the path validator is referenced, and the Jinja formatter correctly uses `lex()`. The 3 HIGH findings are addressable in <40 lines of net change:

- F-1 (symlink traversal) needs an `is_symlink()` check or `resolve(strict=True)` + `is_relative_to(project_dir)` assertion before each read/write in `format_jinja_templates`.
- F-2 (inverted allowlist) is a single-line flip in the inherited helper — best done in a Phase 0 carry-over task before Phase 4 ships.
- F-3 (config-only auth) is a JWT decode addition — same as Phase 2/3 recommendation; could be a Phase 0 carry-over.
- F-4 (broken `;` token) is a refactor of `_eslt_hook` to return two separate `Hook` entries instead of one combined hook.

The 4 MEDIUM findings are real but each independently patchable without redesigning the plan:
- F-5 (glob patterns) is a documentation + test fix.
- F-6 (ReDoS surface) is a regex tightening or hand-roll.
- F-7 (error leakage) is a string sanitization in one except clause.
- F-8 (npx supply chain) is a documentation + lockfile check.

The 3 LOW findings are quality-of-implementation concerns. F-12 through F-15 confirm the subprocess and parser foundations are correct.

**Do not implement before HIGH findings are fixed.** F-1 is a new vulnerability unique to Phase 4 — Phase 2 and Phase 3 didn't have file-mutation MCP tools over `rglob`. F-2 and F-3 are inherited defects that compound F-1's exposure. F-4 means the Web lint coverage advertised in the plan is not what ships.

The recommended pre-implementation carry-over (Phase 0 or early Phase 4):
1. Flip `_validate_project_root` to deny when `MAHAVISHNU_PROJECT_ROOTS` is unset. (Resolves F-2.)
2. Add JWT decode to `_require_auth_config`. (Resolves F-3.)
3. Split the `eslint_tsc` hook in the plan into two separate hooks before implementation. (Resolves F-4.)
4. Add the symlink guard to `format_jinja_templates` at implementation time. (Resolves F-1.)

# Writing Lens Review

**Plan:** `/Users/les/Projects/crackerjack/docs/superpowers/plans/2026-09-07-crackerjack-multi-language-phase4.md` (~1,437 lines, 7 tasks).
**Spec:** `/Users/les/Projects/crackerjack/docs/superpowers/specs/2026-09-07-crackerjack-multi-language-design.md` (Rev 2).
**Lens:** Writing quality for a new contributor, documentation completeness, docstring/comment accuracy, CHANGELOG quality, plan clarity.

---

## Findings (most-severe first)

### HIGH-1 — `jinja_formatter.py` `_normalize_one_space_inside_delimiters` regex drops first and last character of the inner content; the docstring claims "exactly one space inside each delimiter pair" but the code does not preserve the inner. Tier 2 is broken.

**Plan location:** Task 4 Step 4, `_normalize_one_space_inside_delimiters` (lines 884-902) and the test `test_tier2_when_normalize_true` (lines 775-779).

**Plan code (verbatim):**

```python
def _normalize_one_space_inside_delimiters(source: str, delims: Mapping[str, str]) -> str:
    """Tier 2: ensure exactly one space inside each delimiter pair."""
    out = source
    for open_key, close_key in [
        ("block_start", "block_end"),
        ("variable_start", "variable_end"),
        ("comment_start", "comment_end"),
    ]:
        open_d, close_d = delims[open_key], delims[close_key]
        # Match `open_d<not-whitespace>...<not-whitespace>close_d` and replace
        # with `open_d<one-space>...<one-space>close_d`. Preserves the body.
        # Use a non-greedy match for the inner content.
        pattern = re.escape(open_d) + r"(\S)(.*?)(\S)" + re.escape(close_d)
        # Apply only when current delimiters don't have internal whitespace
        # (idempotent: don't keep adding spaces).
        def repl(m: re.Match[str]) -> str:
            return f"{open_d} {m.group(2)} {close_d}"
        out = re.sub(pattern, repl, out, flags=re.DOTALL)
    return out
```

**Why this is a writing defect (not just a code bug):**

1. **The docstring and inline comment both claim behavior the code does not deliver.** The docstring says "ensure exactly one space inside each delimiter pair"; the comment says "Preserves the body." Neither is true. For `{%if x%}`:
   - The regex `(\S)(.*?)(\S)` captures `i` (group 1), `f ` (group 2, lazy match), `x` (group 3).
   - The replacement uses `m.group(2)` only — group 1 (`i`) and group 3 (`x`) are dropped.
   - Result: `{% f  %}` (two spaces between `f` and `%}`, with `i` and `x` removed).

2. **The corresponding test (`test_tier2_when_normalize_true`, lines 775-779) would FAIL** when run against the implementation:
   ```python
   src = "{%if x%}A{%endif%}"
   result = format_template(src, delimiters=DEFAULT_DELIMITERS, normalize=True)
   assert "{% if x %}" in result  # NEVER matches; result is "{% f  %}"
   ```
   The plan ships a test that contradicts the implementation. TDD caught this if the test was run first (which is what the plan's TDD structure intends). The plan's "Expected: 9 passed" at Step 6 would not match reality.

3. **The "idempotent: don't keep adding spaces" comment is also inaccurate.** The regex matches when the inner content starts/ends with non-whitespace, but the replacement puts a space there, so the next iteration would NOT match (because the new inner starts/ends with whitespace). So the comment's claim about "idempotent" is technically correct, but it's the wrong justification — the function drops characters entirely, so even with idempotence the function corrupts the template.

4. **Recommended fix** (preserve full inner):

   ```python
   def _normalize_one_space_inside_delimiters(source: str, delims: Mapping[str, str]) -> str:
       """Tier 2: ensure exactly one space inside each delimiter pair.

       Idempotent: a second call produces the same output (whitespace is
       already correct, so the regex no longer matches).
       """
       out = source
       for open_key, close_key in [
           ("block_start", "block_end"),
           ("variable_start", "variable_end"),
           ("comment_start", "comment_end"),
       ]:
           open_d, close_d = delims[open_key], delims[close_key]
           # Match delimiters whose inner content does NOT already start/end
           # with whitespace, then insert exactly one space on each side.
           # Pattern: open_d + non-space + ... + non-space + close_d.
           pattern = re.escape(open_d) + r"(\S.*?\S)" + re.escape(close_d)
           def repl(m: re.Match[str]) -> str:
               return f"{open_d} {m.group(1)} {close_d}"
           out = re.sub(pattern, repl, out, flags=re.DOTALL)
       return out
   ```

   This requires at least 2 non-whitespace chars in the inner; the test inputs `{%if x%}` and `{%endif%}` satisfy this. For single-char inner (e.g., `{%i%}`), the regex would not match — Tier 2 would skip, which is a documented limitation worth noting.

5. **Why this matters:** This is a Day 1 bug. A new contributor running the TDD steps as written hits a failing test on Step 6 and has to debug the formatter. The plan's "Expected: 9 passed" gives them confidence the test will pass, which is a documentation lie.

---

### HIGH-2 — `_eslt_hook` encodes `;` in argv list; `subprocess.run(cmd)` without `shell=True` will fail. The comment claims "the runner treats as sequential" but no such runner exists.

**Plan location:** Task 3 Step 5, `_eslt_hook` (lines 573-587) and `run_hook_with_fallback` (lines 601-635).

**Plan code (verbatim, both snippets):**

```python
def _eslt_hook(project_root: Path) -> Hook:
    """Combines eslint (JS/TS) + tsc --noEmit into one hook."""
    eslint_pinned = _has_pinned_version(project_root, "eslint")
    tsc_pinned = _has_pinned_version(project_root, "typescript")
    # The combined hook uses a single subprocess.run in the hook runner; the
    # cli_command encodes the eslint invocation, and tsc is appended by the
    # runner as a follow-up. For the brief, we encode the combined command
    # as a shell-style argv that the runner treats as sequential.
    if eslint_pinned and tsc_pinned:
        cmd = ("eslint", ".", "--ext", ".ts,.tsx,.js,.jsx", ";", "tsc", "--noEmit")
    elif eslint_pinned:
        cmd = ("eslint", ".", ";", "tsc", "--noEmit")
    else:
        cmd = _npx_command("eslint", ".", "--ext", ".ts,.tsx,.js,.jsx") + (";", "tsc", "--noEmit")
    return Hook(name="web.eslint_tsc", cli_command=cmd, fallback=js_ts_fallback, timeout_seconds=600)
```

```python
def run_hook_with_fallback(
    hook: Hook, project_root: Path, file_paths: list[Path] | None = None,
) -> list[tuple[Path, int, str]]:
    """..."""
    cli_name = hook.cli_command[0]
    if cli_name != "npx" and shutil.which(cli_name) is None:
        # ... fallback path ...
    # CLI present (or npx-prefixed); run subprocess (simplified; full runner is a Phase 4.5 concern)
    cmd = list(hook.cli_command)
    if file_paths:
        cmd.extend(str(p) for p in file_paths)
    else:
        cmd.append(str(project_root))
    result = subprocess.run(cmd, capture_output=True, text=True, cwd=project_root)
```

**Why this is a writing defect:**

1. **`subprocess.run` with `shell=False` (default) treats `;` as a literal argv element**, not a command separator. The `cmd = ("eslint", ".", ";", "tsc", "--noEmit")` tuple, when passed to `subprocess.run`, becomes argv `["eslint", ".", ";", "tsc", "--noEmit"]`. This will fail with `eslint: ERROR: ;` (eslint interprets `;` as a filename argument).

2. **Global Constraints (lines 26-32) forbid shell:** "argv list, no shell for all subprocess invocations." Adding `shell=True` to satisfy the `;` separator would violate this constraint.

3. **The comment "the runner treats as sequential" describes a non-existent runner.** The plan's `run_hook_with_fallback` (lines 601-635) does NOT split `;`-separated commands. It does NOT iterate. It does NOT sequence anything. The comment is a docstring lie — it explains what the author WISHED the code did, not what it does.

4. **The Phase 3 writing review (HIGH-2) flagged the same defect class** for `_build_hooks` in Kotlin — "dead code AND a misleading comment." Phase 4 inherits the defect class.

**Recommended fix:** Pick one of three approaches:

1. **Two separate hooks** (simplest, no comment needed):
   ```python
   hooks.append(Hook(name="web.eslint", cli_command=eslint_cmd, fallback=js_ts_fallback, timeout_seconds=300))
   hooks.append(Hook(name="web.tsc", cli_command=tsc_cmd, fallback=None, timeout_seconds=300))
   ```
   Renames `web.eslint_tsc` to two hooks. Update the architecture claim, CHANGELOG, MCP tool test.

2. **Define `Hook` to support multiple commands** (changes Hook contract):
   ```python
   @dataclass
   class Hook:
       name: str
       cli_commands: tuple[tuple[str, ...], ...]  # each tuple is a separate invocation
       fallback: Callable | None = None
       timeout_seconds: int = 300
   ```
   Then `run_hook_with_fallback` iterates. This is a bigger change and requires updating Phase 2/3 Swift/Kotlin adapters.

3. **Use a shell wrapper script** (the plan's current design, but be explicit):
   Document that the Web adapter uses shell — and amend Global Constraints to allow it. Bad: violates the project-wide rule.

**The current plan's approach (3) is incompatible with (1) and (2).** The comment "the runner treats as sequential" must be replaced with one of the above fixes. Otherwise the implementation will fail at runtime.

---

### HIGH-3 — Spec Revision Notes section is empty despite a real spec deviation (Phase 4 deliverable scope reduction)

**Plan location:** Spec Revision Notes (lines 1428-1431); Out of scope (line 15).

**Plan text:**

```
## Spec Revision Notes

(Spec amendments for the next revision pass — to be filled in after multi-agent review.)
```

**Spec says** (line 420):

> **Phase 4 deliverable**: shared `jinja-test-fixtures/` Bodai sibling package with 30+ input templates and golden-master expected outputs. Both `crackerjack format` and PyCharm (via reproducible script) tested against the same corpus.

**Plan reduces scope** (line 15):

> **Out of scope:** shared `jinja-test-fixtures/` Bodai sibling package (Phase 4 deliverable per spec line 420) — separate plan.

**Why this is a writing defect:**

1. **The plan makes a SPEC DEVIATION** — the spec says the deliverable is a Bodai sibling package; the plan ships 3 jinja fixture files inside `tests/fixtures/web-vanilla/tests/fixtures/jinja-templates/`. The "separate plan" claim is informal; there's no Spec Revision Note recording the reduction.

2. **The Phase 3 writing review (HIGH-1) flagged this exact defect class** — "Spec Revision Notes claims 'None for Phase 3' but the plan adds a tool that diverges from the spec." Phase 4 has the SAME defect: empty Spec Revision Notes + a real deviation.

3. **Future spec revisions will not know why the change happened.** A reader sees "deliverable per spec line 420" in the spec and "separate plan" in the plan; nothing in either file says why. The "separate plan" status (deferred? never? combined into another phase?) is lost.

4. **The Phase 2 final-review pattern set precedent** for recording deviations. Phase 3 also failed to follow this pattern. Phase 4 inherits the regression.

**Recommended fix:**

```
## Spec Revision Notes

- Spec amended (Phase 4): The shared `jinja-test-fixtures/` Bodai sibling
  package (spec line 420) is deferred to a separate plan. Phase 4 ships
  3 inline golden-master fixtures inside
  `tests/fixtures/web-vanilla/tests/fixtures/jinja-templates/`
  (basic.html, custom_delimiters.html, whitespace.html). When the
  sibling package lands, the inline fixtures should migrate.
```

Or, if the plan author intends to add the sibling package in a follow-up phase, mark the plan with a TODO:

> Phase 4 ledger entry: `tests/fixtures/web-vanilla/tests/fixtures/jinja-templates/` is PLACEHOLDER for the spec-deferred `jinja-test-fixtures/` Bodai sibling package. Migrate when sibling package ships.

Either way, Spec Revision Notes must NOT be empty.

---

### HIGH-4 — Plan has no self-review section; Phase 2 ≥ Phase 3 ≥ Phase 4 regression

**Plan location:** Plan body — no "Self-Review" or equivalent section after Task 7.

**Why this is a writing defect:**

The Phase 3 writing review (HIGH-4) flagged this exact defect. Phase 4 inherits without remediation:

1. **Without self-review, the implementer has no checklist** to verify spec coverage. The Spec Revision Notes defect (HIGH-3) would have been caught if the author enumerated spec items row-by-row.

2. **Without self-review, future reviewers cannot quickly verify** that every spec invariant from the Rev 2 Jinja rewrite was implemented. Specifically:
   - Jinja F1: lex() vs parse() ✓ (plan uses lex)
   - Jinja F2: all 6 delimiter kwargs ✓ (plan passes all 6)
   - Jinja F3: two-tier canonical policy ⚠ (Tier 2 implementation broken — see HIGH-1)
   - Jinja F7: lex() tolerates unknown tags ✓ (test_format_handles_unknown_tags covers this)
   - Jinja F10: PyCharm parity deferred ✓ (out of scope per plan)
   - Jinja F11: jinja2 direct dep ✓ (Task 1 Step 3)
   - Writing F2: hybrid fallback canonical interpretation ✓ (spec quoted in Global Constraints)
   - Writing F3: Web detection guard ✓ (Task 2)
   - MCP F5: per-invocation auth check ✓ (Task 6, Phase 3 carry-over)
   - Testing F9: round-trip invariant ✓ (Task 4 Step 2)

3. **Without self-review, two high-severity bugs (HIGH-1, HIGH-2) ship** — both are the kind of bug a row-by-row self-review would have caught.

**Recommended fix:**

Add a Self-Review section before Spec Revision Notes:

```
## Self-Review

| Spec item | Plan coverage | Status |
|---|---|---|
| Web detection guard (Writing F3) | Task 2 | ✓ |
| Jinja F1: lex() preserves comments | Task 4 | ✓ |
| Jinja F2: 6 delimiter kwargs | Task 4 | ✓ |
| Jinja F3 Tier 1: trailing newline + no trailing whitespace | Task 4 | ✓ |
| Jinja F3 Tier 2: opt-in normalize | Task 4 Step 4 | ✗ BROKEN — see writing review HIGH-1 |
| Jinja F7: lex() tolerates unknown tags | Task 4 test | ✓ |
| Jinja F10: PyCharm parity deferred | Plan Out of scope | ✓ |
| Jinja F11: jinja2>=3.1.6 direct dep | Task 1 | ✓ |
| Hooks: stylelint, eslint+tsc, html-validate | Task 3 | ✗ BROKEN — see writing review HIGH-2 |
| Hybrid pattern (CLI primary + Python fallback) | Task 3 | ✓ |
| `crackerjack.language_adapters` entry-point | Task 1 | ✓ |
| MCP `check_web_lint` + `format_jinja_templates` | Task 6 | ✓ |
| MCP F5: per-invocation auth check | Task 6 | ✓ (Phase 3 carry-over) |
| Spec Revision Notes | Empty | ✗ WRONG — see writing review HIGH-3 |
```

---

### HIGH-5 — Plan has no spec coverage table (Phase 3 regression persists)

**Plan location:** Plan body — no spec coverage table anywhere.

The Phase 3 writing review (HIGH-5) flagged this. Phase 4 has zero rows. See HIGH-4 above for the combined fix.

---

### MEDIUM-1 — `_eslt_hook` function name is inconsistent with the hook name and uses a non-obvious abbreviation; weakens cross-file naming

**Plan location:** Task 3 Step 5 (line 573).

**Plan code:**

```python
def _eslt_hook(project_root: Path) -> Hook:
    """Combines eslint (JS/TS) + tsc --noEmit into one hook."""
    ...
    return Hook(name="web.eslint_tsc", cli_command=cmd, fallback=js_ts_fallback, timeout_seconds=600)
```

**Naming inconsistency:**

- Function: `_eslt_hook` (abbreviated; reads as "e-s-l-t" or "es-lint-t-sc" if you squint)
- Hook name: `web.eslint_tsc` (full)
- Test name: `test_eslint_tsc_hook_combines_eslint_and_tsc`

A new contributor reading `_eslt_hook` in `web_hooks(tmp_path)` won't know if it's `eslt` (es-lint) or `_es_lt_hook` (es + lt) or `_eslint_hook` (typo).

The other two hook factories follow consistent naming:

```python
def _css_hook(project_root: Path) -> Hook:
    ...
    return Hook(name="web.stylelint", ...)

def _html_hook(project_root: Path) -> Hook:
    ...
    return Hook(name="web.html_validate", ...)
```

Wait — even these are inconsistent. `_css_hook` produces `web.stylelint` (not `web.css_something`), and `_html_hook` produces `web.html_validate` (not `web.html_something`). The prefix differs per hook.

The cleanest naming would be either:
- Function name matches the tool: `_stylelint_hook`, `_eslint_tsc_hook`, `_html_validate_hook`
- Or function name matches the hook name (minus `web.`): `_stylelint_hook`, `_eslint_tsc_hook`, `_html_validate_hook`

**Recommended fix:**

```python
def _stylelint_hook(project_root: Path) -> Hook:
    """stylelint (CSS) — `web.stylelint`."""
    ...

def _eslint_tsc_hook(project_root: Path) -> Hook:
    """eslint (JS/TS) + tsc --noEmit (combined) — `web.eslint_tsc`."""
    ...

def _html_validate_hook(project_root: Path) -> Hook:
    """html-validate (HTML) — `web.html_validate`."""
    ...
```

The function names then match the hook names (sans prefix) and read clearly in stack traces.

---

### MEDIUM-2 — Three hook factory functions (`_css_hook`, `_eslt_hook`, `_html_hook`) lack docstrings; only the module docstring explains them

**Plan location:** Task 3 Step 5 (lines 567-593).

**Plan code (verbatim, all three functions):**

```python
def _css_hook(project_root: Path) -> Hook:
    pinned = _has_pinned_version(project_root, "stylelint")
    cmd = _npx_command("stylelint", "**/*.css") if pinned is None else ("stylelint", "**/*.css")
    return Hook(name="web.stylelint", cli_command=cmd, fallback=css_fallback, timeout_seconds=300)


def _eslt_hook(project_root: Path) -> Hook:
    """Combines eslint (JS/TS) + tsc --noEmit into one hook."""
    eslint_pinned = _has_pinned_version(project_root, "eslint")
    tsc_pinned = _has_pinned_version(project_root, "typescript")
    ...
    return Hook(name="web.eslint_tsc", cli_command=cmd, fallback=js_ts_fallback, timeout_seconds=600)


def _html_hook(project_root: Path) -> Hook:
    pinned = _has_pinned_version(project_root, "html-validate")
    cmd = _npx_command("html-validate", "**/*.html") if pinned is None else ("html-validate", "**/*.html")
    return Hook(name="web.html_validate", cli_command=cmd, fallback=html_fallback, timeout_seconds=300)
```

**Why this is a writing defect:**

1. `_css_hook` and `_html_hook` have NO docstrings. `_eslt_hook` has a one-liner that mentions "Combines eslint + tsc" but doesn't explain the pinning logic.

2. A new contributor reading `web_hooks(tmp_path)` and stepping into `_css_hook` has no inline explanation. The module docstring (lines 522-530) describes the pattern but doesn't enumerate the per-hook semantics.

3. The pinning logic (`if pinned is None ... else`) is non-obvious. A reader doesn't know:
   - What `pinned` means (it's the version from `package.json` devDependencies)
   - Why use `npx` when not pinned but the bare command when pinned
   - What the timeout_seconds means

4. **Phase 3 writing review HIGH-3 (Module docstrings absent)** flagged a related issue — module docstrings for `version_source.py`, `hooks.py`, `__init__.py`. Phase 4 fixes the module docstring requirement but still misses the function-level docstrings.

**Recommended fix:**

Add docstrings to all three factories:

```python
def _css_hook(project_root: Path) -> Hook:
    """Build the stylelint hook for CSS files.

    If `stylelint` is pinned in `package.json` devDependencies, run it
    directly (no `npx`). Otherwise use `npx --no-install stylelint` to
    pick up the latest CLI on PATH. Falls back to the Python `css_fallback`
    when stylelint is not installed.
    """
    ...


def _eslint_tsc_hook(project_root: Path) -> Hook:
    """Build the combined eslint (JS/TS) + tsc --noEmit hook.

    Both commands run in sequence (see writing review HIGH-2 for the
    current implementation note). Falls back to `js_ts_fallback` when
    neither CLI is installed.
    """
    ...


def _html_hook(project_root: Path) -> Hook:
    """Build the html-validate hook for HTML files.

    Mirrors the stylelint pinning logic — direct invocation when pinned,
    `npx` fallback otherwise. Falls back to `html_fallback`.
    """
    ...
```

---

### MEDIUM-3 — Task 6 tests use `monkeypatch` (sync) inside `async def`, with explicit `monkeypatch.undo()`; same defect Phase 3 writing review LOW-8 flagged

**Plan location:** Task 6 Step 1, all four test functions (lines 1073-1135).

**Plan code (verbatim, first test):**

```python
async def test_check_web_lint_returns_three_hook_names(tmp_path: Path) -> None:
    from crackerjack.adapters.web import WebAdapter
    (tmp_path / "package.json").write_text("{}")
    monkeypatch = pytest.MonkeyPatch()
    try:
        monkeypatch.setenv("MAHAVISHNU_PROJECT_ROOTS", str(tmp_path))
        _, tools = asyncio.run(_register())
        tool = tools["check_web_lint"]
        result = asyncio.run(tool.fn(project_root=str(tmp_path)))
    finally:
        monkeypatch.undo()
    assert isinstance(result, dict)
```

**Why this is a writing defect:**

The Phase 3 writing review (LOW-8) flagged this exact pattern. Phase 4 inherits without remediation:

1. **The tests are declared `async def` but use `asyncio.run()` inside the body.** If `_register()` is async, `await` should be used. If `_register()` is sync, the test should be `def`, not `async def`.

2. **`monkeypatch.undo()` in a `try/finally`** is the pattern from old-style `unittest.mock.patch` usage. Pytest's `monkeypatch` fixture is designed to be used as a function argument (pytest cleans it up automatically). The plan creates a fresh `pytest.MonkeyPatch()` and manually undoes it — bypasses the fixture's lifecycle.

3. **The pattern is verbose and error-prone.** A reader has to verify the `try/finally` is there; if a future edit adds code after the `try` block, the `finally` may not catch all paths.

**Recommended fix (mirror Phase 2's pattern):**

Use `monkeypatch` as a fixture argument (no `try/finally`):

```python
async def test_check_web_lint_returns_three_hook_names(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch,
) -> None:
    (tmp_path / "package.json").write_text("{}")
    monkeypatch.setenv("MAHAVISHNU_PROJECT_ROOTS", str(tmp_path))
    _, tools = _register()  # sync helper
    tool = tools["check_web_lint"]
    result = asyncio.run(tool.fn(project_root=str(tmp_path)))
    assert isinstance(result, dict)
```

Or make the test fully async (requires changing the helper's signature):

```python
async def test_check_web_lint_returns_three_hook_names(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch,
) -> None:
    (tmp_path / "package.json").write_text("{}")
    monkeypatch.setenv("MAHAVISHNU_PROJECT_ROOTS", str(tmp_path))
    _, tools = await _register()  # async helper
    tool = tools["check_web_lint"]
    result = await tool.fn(project_root=str(tmp_path))
    assert isinstance(result, dict)
```

The fix choice depends on `_register()`'s actual signature — the plan should commit to one.

---

### MEDIUM-4 — `format_jinja_templates` reads file outside the thread executor, violating "All I/O async" Global Constraint

**Plan location:** Task 6 Step 3, `format_jinja_templates` tool (lines 1219-1233).

**Plan code (verbatim):**

```python
files: list[str] = []
errors: list[dict[str, str]] = []
for project_dir in projects:
    proj = Path(project_dir)
    for path in proj.rglob("*"):
        if not path.is_file() or path.suffix not in {".html", ".j2", ".jinja"}:
            continue
        try:
            formatted = await asyncio.to_thread(
                format_template, path.read_text(),
            )
            path.write_text(formatted)
            files.append(str(path))
        except (OSError, UnicodeDecodeError) as exc:
            errors.append({"path": str(path), "error": str(exc)})
return {"files": files, "errors": errors}
```

**Why this is a writing defect:**

1. **`path.read_text()` is synchronous I/O.** Per Global Constraints line 29: "All I/O async. Subprocess via `asyncio.to_thread` or `loop.run_in_executor`. Sync only at CLI entry points." `path.read_text()` blocks the event loop.

2. **`path.write_text(formatted)` is also synchronous I/O.** It runs after `await asyncio.to_thread(format_template, ...)` but is still on the main thread.

3. **`asyncio.to_thread` only wraps `format_template`** (CPU-bound, not I/O), so wrapping it provides no benefit. The actual I/O (`read_text`/`write_text`) runs on the main thread.

**Recommended fix:**

```python
for path in proj.rglob("*"):
    if not path.is_file() or path.suffix not in {".html", ".j2", ".jinja"}:
        continue
    try:
        # Read on the thread to avoid blocking the event loop
        raw = await asyncio.to_thread(path.read_text)
        formatted = await asyncio.to_thread(format_template, raw)
        await asyncio.to_thread(path.write_text, formatted)
        files.append(str(path))
    except (OSError, UnicodeDecodeError) as exc:
        errors.append({"path": str(path), "error": str(exc)})
```

Or use `aiofiles` (if already a dep) for true async I/O.

---

### MEDIUM-5 — `test_format_jinja_templates_runs_with_auth` does not verify the file was actually mutated

**Plan location:** Task 6 Step 1 (lines 1118-1134).

**Plan code (verbatim):**

```python
async def test_format_jinja_templates_runs_with_auth(tmp_path: Path) -> None:
    """Happy-path test (per MCP HIGH-3 / Testing HIGH-1 Phase 3 analog)."""
    (tmp_path / "package.json").write_text("{}")
    (tmp_path / "templates").mkdir()
    (tmp_path / "templates" / "test.html").write_text("{% if x %}A{% endif %}")
    monkeypatch = pytest.MonkeyPatch()
    try:
        monkeypatch.setenv("MAHAVISHNU_AUTH_ENABLED", "true")
        monkeypatch.setenv("MAHAVISHNU_JWT_SECRET", "test-secret")
        monkeypatch.setenv("MAHAVISHNU_PROJECT_ROOTS", str(tmp_path))
        _, tools = asyncio.run(_register())
        tool = tools["format_jinja_templates"]
        result = asyncio.run(tool.fn(projects=[str(tmp_path / "templates")]))
    finally:
        monkeypatch.undo()
    assert "files" in result
    assert any("test.html" in f for f in result["files"])
```

**Why this is a writing defect:**

The test asserts that `result["files"]` contains `"test.html"` — but doesn't assert that the file **on disk** was actually formatted. The tool could:
- Return a list of filenames without actually writing.
- Write the original (unformatted) contents and still pass.
- Crash silently during `write_text` and the exception handler could add it to `errors` instead (test would still pass if `errors` is not asserted).

For a mutation tool, the test should verify:
1. The file on disk has the formatted content.
2. No entries in `errors` for successful files.
3. The list of `files` matches the actual file list.

**Recommended fix:**

```python
async def test_format_jinja_templates_runs_with_auth(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Happy-path test: file is actually formatted on disk."""
    (tmp_path / "package.json").write_text("{}")
    (tmp_path / "templates").mkdir()
    test_file = tmp_path / "templates" / "test.html"
    original = "{% if x %}A{% endif %}"  # no trailing newline
    test_file.write_text(original)

    monkeypatch.setenv("MAHAVISHNU_AUTH_ENABLED", "true")
    monkeypatch.setenv("MAHAVISHNU_JWT_SECRET", "test-secret")
    monkeypatch.setenv("MAHAVISHNU_PROJECT_ROOTS", str(tmp_path))
    _, tools = _register()
    result = await tool_call(tools["format_jinja_templates"], projects=[str(tmp_path / "templates")])

    assert result["errors"] == []
    assert any("test.html" in f for f in result["files"])
    # Verify the file was actually mutated
    assert test_file.read_text() != original
    assert test_file.read_text().endswith("\n")  # Tier 1 trailing newline applied
```

---

### MEDIUM-6 — Plan claims `typer 0.26+` in Tech Stack but no Typer code is shown; the claim is misleading

**Plan location:** Plan header (line 11); Plan body — no Typer code anywhere.

**Plan text:**

> **Tech Stack:** Python 3.14, FastMCP 4.x, typer 0.26+, hatchling, jinja2 ≥3.1.6 (NEW direct dep per spec Jinja F11), subprocess (npx wrappers), typer 0.26+ for CLI surface.

**Why this is a writing defect:**

1. **No Typer code is shown** in any of the 7 tasks. The plan's deliverables are MCP tools (`check_web_lint`, `format_jinja_templates`) — not CLI commands.

2. **The plan body never imports or uses Typer.** No `@app.command()` decorators, no `typer.Option(...)`, no CLI invocation patterns.

3. **A reviewer reading the Tech Stack might expect Typer-related tasks** and waste time looking for them.

4. **Mentioning Typer twice** ("typer 0.26+, hatchling, jinja2 ≥3.1.6, subprocess (npx wrappers), typer 0.26+ for CLI surface") makes the duplication even more conspicuous.

**Recommended fix:**

Either:
- Remove "typer 0.26+" from Tech Stack (since the plan doesn't add Typer code).
- Or add a Task that adds a Typer CLI command for the Web adapter (e.g., `crackerjack web lint <path>`), with tests.

The current state has the claim but no implementation backing it.

---

### MEDIUM-7 — Inline comment in `run_hook_with_fallback` describes a Phase 4.5 follow-up that is not in the plan's Out of Scope section

**Plan location:** Task 3 Step 5, `run_hook_with_fallback` (lines 622-635).

**Plan code (verbatim):**

```python
# CLI present (or npx-prefixed); run subprocess (simplified; full runner is a Phase 4.5 concern)
cmd = list(hook.cli_command)
if file_paths:
    cmd.extend(str(p) for p in file_paths)
else:
    cmd.append(str(project_root))
result = subprocess.run(cmd, capture_output=True, text=True, cwd=project_root)
# For Phase 4 we surface only fallback-shaped issues; CLI parsing is a Phase 4.5 concern
if result.returncode != 0:
    logger.warning(
        "Web hook %r exited %d: %s", hook.name, result.returncode, result.stderr[:500]
    )
```

**Why this is a writing defect:**

1. **The comment references "Phase 4.5" twice** — both in the line "run subprocess (simplified; full runner is a Phase 4.5 concern)" and "CLI parsing is a Phase 4.5 concern". Phase 4.5 is not mentioned anywhere else in the plan.

2. **The Out of Scope section (line 15) only lists the shared `jinja-test-fixtures/` package.** A reader has no way to find what Phase 4.5 is, when it's planned, or what's in scope for it.

3. **A new contributor sees `subprocess.run` succeed and wonders "is this it? where's the CLI output parsing?"** The comment says it's deferred but doesn't say to what.

**Recommended fix:**

Either:
- Add "Phase 4.5" to the Out of Scope section:
  > **Out of scope:** Web hook CLI output parsing (Phase 4.5 follow-up). Phase 4 surfaces issues only via the Python fallback.
- Or remove the Phase 4.5 references and replace with a TODO:
  ```python
  # TODO(crackerjack): parse subprocess output into structured issues.
  # Currently only the Python fallback surface is exercised; CLI tools
  # return text that would need per-tool parsing (e.g., stylelint JSON).
  ```

The current comment hides a known gap behind "Phase 4.5" with no plan reference.

---

### LOW-1 — Phase 2/3 short-hand references not inlined; Phase 3 writing review MEDIUM-2 again

**Plan locations:** Global Constraints (lines 33-48); Task 2 Step 2 (line 161); Task 5 (line 926); Task 6 Step 3 (line 1066).

**Examples:**

- Line 36: "Phase 3 fixed `_validate_project_root` to fail-closed; Phase 4 reuses the fixed helpers." (no inline summary)
- Line 161: "Per spec Writing F3" (no inline summary of what F3 says)
- Line 926: "Per Phase 2 final-review CF-2 fix" (no inline summary of what CF-2 was)
- Line 1066: "Per Phase 3 carry-over: the existing `_validate_project_root` (fail-closed) and `_require_auth_config` (diagnostic) helpers are reused." (no inline summary)
- Line 1267: "Per Phase 3 final-review fix precedent" (no inline summary)

**Why this is a writing defect:**

Phase 3 writing review MEDIUM-2 flagged this exact pattern. Phase 4 inherits:

A new contributor without Phase 2/3 plans in hand has to reverse-engineer:
- What was CF-2? (Phase 2 final-review CF-2 was "don't construct lifecycle in `capabilities()`; build lazily")
- Why does `_validate_project_root` matter? (because the prior version was permissive, not fail-closed)
- What was the "Phase 3 final-review fix"? (fixture-reference test pattern)

The Phase 3 writing review's recommended fix was to inline 3-5 lines per reference. Phase 4 has 5 references and inlines 0.

**Recommended fix:**

Inline 2-3 lines per reference. For example, line 36:

> **Why per-invocation auth check matters (Phase 3 final-review fix):** Phase 3 changed `_validate_project_root` from permissive (warn-and-continue) to fail-closed (raise `PermissionError`). Phase 4 reuses the fail-closed helper. Without fail-closed, a mutation tool could write to a project outside `MAHAVISHNU_PROJECT_ROOTS`. The Phase 3 fix made this a hard error.

This adds ~30 lines but eliminates "what was that?" questions for a new contributor.

---

### LOW-2 — Plan does not mention that the Phase 4 web fixture path `tests/fixtures/web-vanilla/tests/fixtures/jinja-templates/` is unusual nesting

**Plan location:** Task 7 Step 1, fixture file paths (lines 1278-1344).

**Plan code (verbatim):**

```
tests/fixtures/web-vanilla/                               # Real Web fixture (package.json + minimal src/)
    ├── package.json
    ...
    └── tests/fixtures/jinja-templates/         # Golden-master test inputs
        ├── basic.html
        ├── custom_delimiters.html
        └── whitespace.html
```

**Why this is a writing defect:**

1. **The Jinja fixture path is `tests/fixtures/web-vanilla/tests/fixtures/jinja-templates/`** — nesting `tests/fixtures/` inside `tests/fixtures/`. The path reads as `tests/fixtures/web-vanilla/tests/fixtures/jinja-templates/`.

2. **A new contributor is likely to rename this** to `tests/fixtures/web-vanilla/jinja-templates/` (no nested `tests/fixtures/`), breaking the spec line 420 reference (which says "shared `jinja-test-fixtures/` Bodai sibling package"). If the future migration moves the files to the sibling package, having `tests/fixtures/jinja-templates/` inside the web fixture is correct; if it stays, the path is awkward.

3. **No rationale is given** for the nested path. The plan shows the file structure as a tree but doesn't explain why the nesting exists.

**Recommended fix:**

Either:
- Inline a rationale: "Nested `tests/fixtures/jinja-templates/` inside `tests/fixtures/web-vanilla/` mirrors the eventual `jinja-test-fixtures/` Bodai sibling package location (spec line 420). When the sibling package ships, the files move there and the web fixture's nested path is deleted."
- Or simplify the path now: rename to `tests/fixtures/web-vanilla/jinja-templates/`. Update the test code (`FIXTURE_ROOT / "jinja-templates"`) accordingly.

---

### LOW-3 — CHANGELOG entry mentions 4 adapter languages but doesn't enumerate the entry-point group update clearly

**Plan location:** Task 7 Step 3, CHANGELOG entry (lines 1380-1398).

**Plan text (verbatim, last sentence):**

> `crackerjack.language_adapters` entry-point group now registers Python, Swift, Kotlin, and Web adapters.

**Why this is a writing defect:**

1. **The spelling is correct** (`crackerjack.language_adapters`) — Phase 3 writing review found this also correct. Good.

2. **But the entry says "now registers"** as if the Web entry is the only addition. A reader unfamiliar with Phase 2/3 might wonder when Python/Swift/Kotlin were added. The CHANGELOG should anchor on Phase 4 alone, not retell the entry-point history.

3. **The "Python, Swift, Kotlin, and Web" list is alphabetical** — good. But it could be more explicit:

   > `crackerjack.language_adapters` entry-point group now includes the Web adapter (added in Phase 4); Python, Swift, and Kotlin were registered in earlier phases.

**Recommended fix:**

Trim the sentence to Phase 4 scope:

> `crackerjack.language_adapters` entry-point group now includes the Web adapter (joining Python, Swift, and Kotlin from earlier phases).

---

### LOW-4 — Plan header says "Status: Ready for execution" but Task 2's pre-flight check ("verify CLI commands") and Task 4's "verify jinja2 delimiter kwargs" are pre-conditions, not actions

**Plan location:** Plan header (line 5); Task 3 Step 1 (lines 309-316); Task 4 Step 1 (lines 675-689).

**Why this is a writing defect:**

1. **Task 3 Step 1 is titled "Verify CLI commands"** but is followed by a 4-line bash block that may FAIL (if any of `npx stylelint --version`, etc., fail). The plan does not say what to do if the verify fails — note the failure and proceed? Skip Task 3 entirely?

2. **Task 4 Step 1 is titled "Verify jinja2 delimiter kwargs"** but is followed by a Python -c command that may fail (if `jinja2` is not yet installed or the version is wrong). Same issue.

3. **A "Ready for execution" plan should not have un-handled pre-conditions.** The implementer hits the pre-flight, it fails, and has no instruction.

**Recommended fix:**

For each pre-flight, add an explicit failure path:

```markdown
- [ ] **Step 1: Verify CLI commands**

Run: ... (commands)

If any command fails:
- Note the failure in the commit message: `npx <tool> not installed locally; Python fallback exercised in tests`.
- DO NOT skip Task 3 — the fallback path is testable even without the CLI installed.
- Continue to Step 2.
```

Or split the task: Task 3.0 = verify CLI; Task 3.1 = write tests; if verify fails, switch to "fallback-only" mode for all hooks.

---

### LOW-5 — `WebHookError` raised in `run_hook_with_fallback` is never unit-tested

**Plan location:** Task 3 Step 5, `WebHookError` (lines 638-639); Task 3 Step 2 (tests at lines 321-403).

**Plan code:**

```python
class WebHookError(RuntimeError):
    """Raised when a Web hook cannot run (CLI missing, no fallback)."""
```

**Why this is a writing defect:**

1. **The error class is defined** but the test file (`test_hooks.py`) does not contain a test that exercises the error path. The 8 tests cover happy paths (hooks returned, hooks invoked, fallbacks work) but never raise `WebHookError`.

2. **`run_hook_with_fallback` raises `WebHookError` when `shutil.which(cli_name) is None and hook.fallback is None`.** But every hook in `_css_hook`, `_eslt_hook`, `_html_hook` has a fallback set. So the error path is unreachable in the current design.

3. **If the error is dead code, the class shouldn't be in the implementation.** If the error is part of the contract for future hooks without fallback, it should be tested.

**Recommended fix:**

Either:
- Add a test that constructs a Hook without a fallback and verifies `WebHookError` is raised:
  ```python
  def test_run_hook_with_fallback_raises_when_cli_missing_and_no_fallback(tmp_path):
      hook = Hook(name="test.no_fallback", cli_command=("nonexistent_cli",), fallback=None)
      with pytest.raises(WebHookError, match="not installed"):
          run_hook_with_fallback(hook, tmp_path)
  ```
- Or document that `WebHookError` is reserved for future hooks without fallbacks and remove the class from Phase 4 (move to a Phase 4.5 follow-up).

---

### LOW-6 — Plan's CHANGELOG entry omits the `Tier 2 = opt-in` opt-in mechanism location

**Plan location:** Task 7 Step 3, CHANGELOG entry (lines 1380-1398).

**Plan text (excerpt):**

> two-tier canonical policy (Tier 1: trailing newline + no trailing whitespace + preserve whitespace-control markers; Tier 2 opt-in via `normalize=True`)

**Why this is a writing defect:**

1. **The spec (line 407) says Tier 2 is opt-in via `[tool.crackerjack.jinja] normalize = true` in `pyproject.toml`.** The plan's implementation (Task 4 Step 4) has `normalize: bool = False` as a function parameter — so the opt-in is via direct function call, not via `pyproject.toml`.

2. **The CHANGELOG entry says `normalize=True`** (function parameter) but the spec says `[tool.crackerjack.jinja] normalize = true` (config file).

3. **These are different mechanisms.** A user reading the CHANGELOG might wonder why the spec says one thing and the entry says another.

**Recommended fix:**

Either:
- Update the implementation to read `pyproject.toml` and pick up `[tool.crackerjack.jinja] normalize` (matches spec).
- Or document the deviation:
  > Tier 2 is opt-in via the `normalize=True` parameter to `format_template()`. The spec's `[tool.crackerjack.jinja] normalize = true` config-file mechanism is deferred (not implemented in Phase 4).

The current state is a spec/plan mismatch that the CHANGELOG papered over.

---

## Spec Coverage Summary

| Spec item | Plan coverage | Status |
|---|---|---|
| Web detection guard (Writing F3) | Task 2 | ✓ |
| Hybrid pattern (CLI primary + Python fallback) per Writing F2 | Task 3 | ✓ (with HIGH-2 caveat on combined-hook argv) |
| Hooks: stylelint, eslint+tsc, html-validate | Task 3 | ✗ BROKEN — see HIGH-2 |
| Jinja F1: lex() (NOT parse()) | Task 4 | ✓ |
| Jinja F1: lex() preserves comments | Task 4 test | ✓ |
| Jinja F1: lex() tolerates unknown tags | Task 4 test | ✓ |
| Jinja F2: all 6 delimiter kwargs | Task 4 | ✓ |
| Jinja F3 Tier 1: trailing newline | Task 4 | ✓ |
| Jinja F3 Tier 1: no trailing whitespace | Task 4 | ✓ |
| Jinja F3 Tier 1: preserve `{%-` / `-%}` / `{{-` / `-}}` | Task 4 | ✓ |
| Jinja F3 Tier 2: opt-in normalize | Task 4 Step 4 | ✗ BROKEN — see HIGH-1 |
| Jinja F7: lex() tolerates unknown tags | Task 4 test | ✓ |
| Jinja F10: PyCharm parity deferred | Plan Out of scope | ✓ |
| Jinja F11: jinja2>=3.1.6 direct dep | Task 1 | ✓ |
| Round-trip invariant (Testing F9 + Jinja F1) | Task 4 test | ✓ |
| MCP `check_web_lint` (read-only) | Task 6 | ✓ |
| MCP `format_jinja_templates` (mutation; auth required) | Task 6 | ✓ |
| MCP F5: per-invocation auth check | Task 6 | ✓ (Phase 3 carry-over) |
| `crackerjack.language_adapters` entry-point registration | Task 1 | ✓ |
| Spec Revision Notes | Empty | ✗ WRONG — see HIGH-3 |
| Module docstrings on every new file | All 5 files | ✓ |
| Function docstrings on hook factories | 0 of 3 | ✗ INCOMPLETE — see MEDIUM-2 |
| Plan self-review | Absent | ✗ MISSING — see HIGH-4 |
| Spec coverage table | Absent | ✗ MISSING — see HIGH-5 |

**Spec deviations found: 1 confirmed** (Phase 4 deliverable scope reduction — shared `jinja-test-fixtures/` Bodai sibling package is deferred per HIGH-3).

**Plan defects (non-spec): 5 (HIGH-1, HIGH-2, HIGH-3, HIGH-4, HIGH-5, plus several MEDIUM and LOW).**

---

## Plan Quality Verdict

**The plan is broadly well-structured** at the task/test/commit level, but ships two Day 1 bugs (HIGH-1 broken Tier 2, HIGH-2 broken `;` argv) that the TDD discipline would surface as test failures. The plan's "Expected: N passed" claims for Task 4 (9 passed) and Task 6 (17 passed) do not match reality once the implementation matches the spec.

**What the plan does well (writing lens):**

1. **TDD structure is consistent and complete.** Every task has explicit "write failing tests → run → implement → run → commit" steps. Tasks 2-7 show full test code (38+ tests visible).
2. **Module docstrings are present on every new file** (`detection.py`, `hooks.py`, `python_fallbacks.py`, `jinja_formatter.py`, `__init__.py`). This is a marked improvement over Phase 3.
3. **CHANGELOG entry uses correct spelling** (`crackerjack.language_adapters` — no `crackageck` typo).
4. **Function-level docstrings on the major public surface** (`web_enabled`, `format_template`, `_env`, `_normalize_one_space_inside_delimiters`, `_strip_trailing_whitespace`, `web_hooks`, `run_hook_with_fallback`, `WebAdapter`, `WebHookError`, `css_fallback`, `js_ts_fallback`, `html_fallback`, `package_json_present`).
5. **Naming is consistent** across tasks: `WebAdapter`, `web_hooks`, `web_enabled`, `package_json_present`, `format_template`, `DEFAULT_DELIMITERS`, `check_web_lint`, `format_jinja_templates`.
6. **Phase 3 carry-over is referenced** (`_validate_project_root` fail-closed, fixture-reference test, per-invocation auth check, `capabilities()` lazy construction).
7. **Spec invariants are pinned.** All 6 delimiter kwargs required, round-trip invariant, two-tier policy, Web detection guard — each repeated in the relevant task.
8. **Pre-flight verification steps** for CLI tools (Task 3 Step 1) and jinja2 kwargs (Task 4 Step 1).
9. **Commit messages are traceable** with consistent `feat(adapters.web):` / `feat(mcp):` / `docs(changelog):` prefixes.
10. **Architecture paragraph names each deliverable** with line references to the spec.
11. **Three new MCP tools covered by tests** (4 web tests, extending Phase 2's 13).

**What the plan does less well (writing lens):**

1. **HIGH-1: `_normalize_one_space_inside_delimiters` regex drops first/last char** — the docstring comment says "Preserves the body" but the implementation does not preserve it. Test would fail.
2. **HIGH-2: `_eslt_hook` encodes `;` in argv** — comment claims runner handles sequential execution, no such runner exists; `subprocess.run(cmd)` without shell=True will fail.
3. **HIGH-3: Spec Revision Notes empty** — Phase 4 reduces scope from spec (shared `jinja-test-fixtures/` sibling package is deferred) but the deviation is not recorded.
4. **HIGH-4/5: No self-review section, no spec coverage table** — Phase 3 inherited this regression from Phase 2; Phase 4 inherits again.
5. **MEDIUM-1: `_eslt_hook` function name is non-obvious** (compare to `_stylelint_hook` / `_eslint_tsc_hook` / `_html_validate_hook`).
6. **MEDIUM-2: Three hook factory functions lack docstrings.**
7. **MEDIUM-3: Task 6 tests use sync `monkeypatch` inside `async def`** — Phase 3 writing review LOW-8 already flagged this; Phase 4 inherits.
8. **MEDIUM-4: `format_jinja_templates` reads/writes files synchronously**, violating Global Constraints.
9. **MEDIUM-5: `test_format_jinja_templates_runs_with_auth` doesn't verify file actually mutated.**
10. **MEDIUM-6: `typer 0.26+` in Tech Stack but no Typer code** — misleading claim.
11. **MEDIUM-7: "Phase 4.5" referenced in comments but not in Out of Scope** — orphan reference.
12. **LOW-1: Phase 2/3 short-hand references not inlined** — Phase 3 MEDIUM-2 not addressed.
13. **LOW-2: Nested `tests/fixtures/web-vanilla/tests/fixtures/jinja-templates/` is unusual** — no rationale given.
14. **LOW-3: CHANGELOG entry mentions Python/Swift/Kotlin/Web but those were added in earlier phases** — out of scope for Phase 4 changelog.
15. **LOW-4: Pre-flight checks lack failure paths.**
16. **LOW-5: `WebHookError` defined but never tested.**
17. **LOW-6: CHANGELOG says Tier 2 opt-in via `normalize=True`** (function param) but spec says `[tool.crackerjack.jinja] normalize = true` (config file) — discrepancy.

**Reviewer recommendations (priority order):**

1. **(HIGH)** Fix the `_normalize_one_space_inside_delimiters` regex (HIGH-1). The pattern should preserve the full inner content, not drop first/last char.
2. **(HIGH)** Replace the `;`-separated argv in `_eslt_hook` with two separate hooks OR explicit shell handling OR `Hook.cli_commands: tuple[tuple[str, ...], ...]` (HIGH-2).
3. **(HIGH)** Fill in Spec Revision Notes with the `jinja-test-fixtures/` scope reduction (HIGH-3).
4. **(HIGH)** Add a Self-Review section with spec coverage table (HIGH-4, HIGH-5).
5. **(MEDIUM)** Rename `_eslt_hook` to `_eslint_tsc_hook` (MEDIUM-1).
6. **(MEDIUM)** Add docstrings to `_css_hook`, `_eslt_hook`/`_eslint_tsc_hook`, `_html_hook` (MEDIUM-2).
7. **(MEDIUM)** Resolve the `async def` + `monkeypatch.setenv` ambiguity in Task 6 tests (MEDIUM-3).
8. **(MEDIUM)** Move `path.read_text()`/`path.write_text()` into `asyncio.to_thread` (MEDIUM-4).
9. **(MEDIUM)** Strengthen `test_format_jinja_templates_runs_with_auth` to verify file mutation (MEDIUM-5).
10. **(MEDIUM)** Remove `typer 0.26+` from Tech Stack or add a Typer CLI task (MEDIUM-6).
11. **(MEDIUM)** Replace "Phase 4.5" comments with explicit TODOs and add to Out of Scope (MEDIUM-7).
12. **(LOW)** Inline 2-3 lines per Phase 2/3 short-hand reference (LOW-1).
13. **(LOW)** Document the nested `jinja-templates/` path or simplify (LOW-2).
14. **(LOW)** Trim CHANGELOG entry-point sentence to Phase 4 scope (LOW-3).
15. **(LOW)** Add failure paths to pre-flight steps (LOW-4).
16. **(LOW)** Add a `WebHookError` test or remove the class (LOW-5).
17. **(LOW)** Reconcile CHANGELOG's `normalize=True` mention with the spec's `[tool.crackerjack.jinja] normalize` (LOW-6).

---

## Summary

The plan is **well-structured at the level of organization and naming** — Tasks 1-7 follow a consistent rhythm, module docstrings are present on every new file (a real improvement over Phase 3), and the CHANGELOG entry is correctly spelled and substantive.

The 5 HIGH-severity findings cluster around three categories: **broken implementation** (HIGH-1, HIGH-2 — code that won't run as shown), **spec adherence** (HIGH-3 — empty Spec Revision Notes despite a real scope reduction), and **structural completeness** (HIGH-4, HIGH-5 — no self-review or spec coverage table). The first two are show-stoppers; the third is a Phase 2 → Phase 3 → Phase 4 regression.

The most actionable improvements are:

1. **Fix the `_normalize_one_space_inside_delimiters` regex** (HIGH-1). One pattern fix; one test starts passing.
2. **Fix the `_eslt_hook` argv separator** (HIGH-2). Pick one of three approaches; one test starts passing.
3. **Fill in Spec Revision Notes** (HIGH-3). One paragraph; preserves the deviation rationale for future maintainers.
4. **Add a Self-Review section** (HIGH-4, HIGH-5). 20-30 lines; catches the regressions a reviewer would catch.

The MEDIUM and LOW findings are polish and can be filed as a Phase 4 ledger entry for a future polish pass.

**Recommended action before implementation begins:** Address HIGH-1, HIGH-2, HIGH-3, HIGH-4, and HIGH-5. The MEDIUM and LOW findings can be deferred.

---

## Status

**REVIEW_COMPLETE** — review file written. Plan implementation can proceed with the recommended HIGH-severity fixes tracked in a Phase 4 ledger entry before Task 3 begins.

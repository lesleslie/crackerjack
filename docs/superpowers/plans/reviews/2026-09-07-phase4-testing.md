# Testing Lens Review — Phase 4 (Web)

**Plan:** `2026-09-07-crackerjack-multi-language-phase4.md`
**Spec:** `2026-09-07-crackerjack-multi-language-design.md` (Rev 2)
**Lens:** Test automation
**Verdict:** CONDITIONAL PASS — plan has correct TDD structure, addresses Phase 2 CRITICAL-1 (Task 6 happy-path) and Phase 3 spec-mandate idiom (`monkeypatch.setattr`), but has 3 HIGH-severity gaps that block Task 7 closure, plus 4 medium and 4 low items.

---

## Findings (most-severe first)

### HIGH-1: Task 3 hybrid two-path test plan is incomplete — 6 of 8 tests are structural assertions on `cli_command`, not exercising the runtime branch per spec Testing F3

**Plan reference:** Task 3, lines ~336-403.

**Spec reference:** Testing F3 (line 617-634):
> For every hook with a `fallback`: `test_<hook>_uses_cli_when_present` AND `test_<hook>_falls_back_to_python_when_cli_missing` is mandatory.

The plan's 8 tests:

| Test | Type | Mandate satisfied? |
|---|---|---|
| `test_web_hooks_returns_three_hooks` | structural | n/a |
| `test_stylelint_hook_uses_npx_subprocess` | structural (`assert cli_command[0] == "npx"`) | NO — does not exercise runtime branch |
| `test_eslint_tsc_hook_combines_eslint_and_tsc` | structural (`assert "eslint" in cmd_str`) | NO |
| `test_html_validate_hook_uses_npx_subprocess` | structural | NO |
| `test_css_fallback_parses_stylesheet` | fallback unit | n/a |
| `test_js_ts_fallback_parses_typescript` | fallback unit | n/a |
| `test_html_fallback_parses_html` | fallback unit | n/a |
| `test_web_hooks_invokes_python_fallback_when_cli_missing` | one combined monkeypatch test | PARTIAL — does not pin per-hook, only asserts `result == []` |

**Risk:**
1. **Zero `test_<hook>_uses_cli_when_present` tests.** A regression where the runner short-circuits to fallback regardless of `shutil.which` would pass every test. The structural assertions check `cli_command` shape but never invoke the runner with `shutil.which` mocked to return a CLI path.
2. **The single fallback test is structurally weak.** It calls `for hook in hooks: result = mock_run.return_value; assert result == []` — this loops but doesn't distinguish hooks, doesn't pin that the right `hook.fallback` was invoked, and doesn't check that the right hook fired in the right order.
3. **Spec Testing F3 is mandatory for hybrid hooks** — the spec uses the word "mandatory" twice. The plan has 1 of 6 required tests.

**Recommendation:**
Add 6 tests to `test_hooks.py` (one pair per hook + a "no-fallback → WebHookError" test):

```python
def test_stylelint_hook_uses_cli_when_present(tmp_path, monkeypatch):
    """Per spec Testing F3: CLI present → subprocess.run invoked, fallback NOT used."""
    (tmp_path / "package.json").write_text("{}")
    monkeypatch.setattr(shutil, "which", lambda cmd: "/usr/bin/stylelint" if cmd == "stylelint" else None)
    with mock.patch("crackerjack.adapters.web.hooks.subprocess.run") as mock_sub:
        mock_sub.return_value = mock.Mock(returncode=0, stdout="", stderr="")
        hook = next(h for h in web_hooks(tmp_path) if h.name == "web.stylelint")
        run_hook_with_fallback(hook, tmp_path)
        mock_sub.assert_called_once()
        args = mock_sub.call_args[0][0]
        assert "stylelint" in args


def test_stylelint_hook_falls_back_to_python_when_cli_missing(tmp_path, monkeypatch):
    """Per spec Testing F3: CLI missing → fallback invoked."""
    (tmp_path / "package.json").write_text("{}")
    monkeypatch.setattr(shutil, "which", lambda cmd: None)
    with mock.patch.object(css_fallback, "__call__", return_value=[]) as mock_css:
        hook = next(h for h in web_hooks(tmp_path) if h.name == "web.stylelint")
        run_hook_with_fallback(hook, tmp_path)
        mock_css.assert_called_once()  # fallback ran, not subprocess


# Repeat for web.eslint_tsc (js_ts_fallback) and web.html_validate (html_fallback).


def test_hook_without_fallback_raises_webhook_error_when_cli_missing(tmp_path, monkeypatch):
    """Per spec Writing F2: CLI missing AND no fallback → WebHookError with install instructions."""
    monkeypatch.setattr(shutil, "which", lambda cmd: None)
    hook = Hook(name="test.no_fallback", cli_command=("fake-cli",), fallback=None)
    with pytest.raises(WebHookError, match="npm install"):
        run_hook_with_fallback(hook, tmp_path)
```

This brings the test count for Task 3 to **14 tests** (8 existing + 6 new), still well within reason for 3 hybrid hooks + 1 error branch.

---

### HIGH-2: Task 4 has NO golden-master expected-output tests — fixtures created in Task 7 are unreferenced from any test

**Plan reference:** Task 4, lines ~693-780. Task 7 fixture creation, lines ~1325-1343.

**Spec reference:** Jinja F1 + Testing F9 (line 412 + line 654):
> Round-trip invariant: `format_lex(format_lex(x)) == format_lex(x)`. **Test asserts with golden-master expected output** for every fixture.

The plan creates 3 fixture files in Task 7:
- `tests/fixtures/web-vanilla/tests/fixtures/jinja-templates/basic.html`
- `tests/fixtures/web-vanilla/tests/fixtures/jinja-templates/custom_delimiters.html`
- `tests/fixtures/web-vanilla/tests/fixtures/jinja-templates/whitespace.html`

But **no test in Task 4 references these fixture files**. All 9 tests use inline `src = "..."` strings:

```python
def test_round_trip_invariant() -> None:
    src = "{# c #}\n{% if x %}\nA\n{% else %}\nB\n{% endif %}\n"  # INLINE
    once = format_template(src, delimiters=DEFAULT_DELIMITERS)
    twice = format_template(once, delimiters=DEFAULT_DELIMITERS)
    assert once == twice
```

**Risk:**
1. **The committed fixture files are decorative.** Per spec Testing F9, the round-trip invariant must be asserted "for every fixture" using "golden-master expected output" — not just round-trip on inline strings.
2. **The custom-delimiters fixture is the load-bearing case** for Jinja F2 (all 6 delimiter kwargs). Task 4 only tests custom delimiters with inline strings (`test_format_uses_custom_delimiters`); the fixture file goes unused.
3. **The whitespace fixture is the load-bearing case** for Jinja F1 (`{%-`/`-%}` preservation). Task 4 only tests whitespace markers inline (`test_format_preserves_whitespace_control_markers`); the fixture file goes unused.
4. **Phase 4 deliverable per spec line 420**: the shared `jinja-test-fixtures/` Bodai sibling package uses these exact fixtures. If Phase 4 doesn't have pytest-level golden-master tests, the shared package has no upstream contract to verify against.

**Note:** The round-trip invariant test (line 759-764) uses inline source — that's correct as a smoke check, but doesn't satisfy "golden-master expected output for every fixture." The difference matters: round-trip alone catches `format(format(x)) == format(x)` regressions; golden-master catches regressions where the canonical form itself changes (e.g., a future maintainer "improves" Tier 1 normalization and shifts the output).

**Recommendation:**
Replace (or supplement) the inline tests with fixture-driven tests:

```python
# tests/adapters/web/test_jinja_formatter.py (additions)
import pytest
from pathlib import Path

FIXTURES_DIR = Path(__file__).parent.parent.parent / "fixtures" / "web-vanilla" / "tests" / "fixtures" / "jinja-templates"


@pytest.mark.parametrize("fixture_name", ["basic.html", "custom_delimiters.html", "whitespace.html"])
def test_format_matches_golden_master(fixture_name: str) -> None:
    """Per spec Testing F9: round-trip + golden-master for every fixture."""
    src = (FIXTURES_DIR / fixture_name).read_text()
    once = format_template(src, delimiters=DEFAULT_DELIMITERS)
    twice = format_template(once, delimiters=DEFAULT_DELIMITERS)
    # Round-trip invariant: golden-master must be its own fixed point
    assert once == twice
    # No "golden_expected.html" file is checked against — the fixture IS the
    # canonical input. To get true golden-master, commit a `*.expected.html`
    # sibling and assert equality.


@pytest.mark.parametrize("fixture_name", ["basic.html", "custom_delimiters.html", "whitespace.html"])
def test_format_fixture_against_expected(fixture_name: str) -> None:
    """True golden-master: compare against `*.expected.html` sibling."""
    src_path = FIXTURES_DIR / fixture_name
    expected_path = FIXTURES_DIR / f"{fixture_name}.expected"
    actual = format_template(src_path.read_text(), delimiters=DEFAULT_DELIMITERS)
    expected = expected_path.read_text()
    assert actual == expected, (
        f"{fixture_name} golden-master mismatch:\n"
        f"  expected: {expected!r}\n  actual:   {actual!r}"
    )
```

The `.expected.html` siblings need to be created in Task 7 alongside the input fixtures.

---

### HIGH-3: Task 7 fixture is decorative — real-CLI smoke test never invokes `npx stylelint`, `npx eslint`, `npx tsc`, or `npx html-validate` against the fixture

**Plan reference:** Task 7, lines ~1269-1343 (fixture creation), lines ~1405-1416 (smoke verification).

**Spec reference:** Writing F2 + Phase 3 review HIGH-4 precedent.

The fixture commits:
- `package.json` with pinned devDependencies (stylelint, eslint, typescript, html-validate)
- `.stylelintrc.json`, `.eslintrc.json`, `tsconfig.json`
- `src/style.css`, `src/app.ts`, `src/index.html`

The smoke step (Task 7 step 5) only runs:
```python
from crackerjack.adapters.registry import discover_adapters
print(sorted(discover_adapters().keys()))
from crackerjack.adapters.web import WebAdapter
print(WebAdapter().detect(__import__('pathlib').Path('tests/fixtures/web-vanilla')))
```

This verifies **detect + registry wiring** only. It does NOT:
1. Run `npx stylelint "tests/fixtures/web-vanilla/src/style.css"` to confirm stylelint is actually installed and finds the `.stylelintrc.json`.
2. Run `npx eslint "tests/fixtures/web-vanilla/src/app.ts"` to confirm eslint + typescript-eslint parser work together.
3. Run `npx tsc --noEmit -p tests/fixtures/web-vanilla/` to confirm TypeScript compiles the fixture.
4. Run `npx html-validate "tests/fixtures/web-vanilla/src/index.html"` to confirm html-validate is installed.

**Risk:**
1. **Fixture validity is unverified.** If `npx stylelint` fails on the committed `.stylelintrc.json` (e.g., a schema change in stylelint 16.x makes `{"rules": {}}` invalid), the fixture is broken but CI passes because no test invokes stylelint.
2. **Pin-version drift.** The `package.json` pins `"stylelint": "^15.0.0"` and `"typescript": "^5.0.0"`. By the time Phase 4 ships, stylelint 16/17 may have become standard and `^15` install may fail on Node 22. There's no signal in CI.
3. **Phase 3 HIGH-4 precedent**: the same gap surfaced in the Kotlin fixture review — a decorative fixture passes the test suite without proving end-to-end validity.

**Recommendation:**
Add a Task 7 step that runs each CLI against the fixture, gated on availability:

```python
# tests/adapters/web/test_web_vanilla_fixture.py (additions)
import shutil
import subprocess

WEB_FIXTURE = Path(__file__).parent.parent.parent / "fixtures" / "web-vanilla"


@pytest.mark.real_web_smoke
def test_stylelint_runs_against_fixture():
    """Gate on `npx stylelint` availability."""
    if shutil.which("npx") is None:
        pytest.skip("npx not available")
    result = subprocess.run(
        ["npx", "--no-install", "stylelint", str(WEB_FIXTURE / "src" / "style.css")],
        capture_output=True, text=True, cwd=WEB_FIXTURE,
    )
    # stylelint exits 0 if clean, 2 if issues found. Both are "fixture works."
    assert result.returncode in (0, 2), f"stylelint crashed: {result.stderr}"


@pytest.mark.real_web_smoke
def test_tsc_compiles_fixture():
    if shutil.which("npx") is None:
        pytest.skip("npx not available")
    result = subprocess.run(
        ["npx", "--no-install", "tsc", "--noEmit"],
        capture_output=True, text=True, cwd=WEB_FIXTURE,
    )
    assert result.returncode == 0, f"tsc failed: {result.stderr}"


@pytest.mark.real_web_smoke
def test_html_validate_runs_against_fixture():
    if shutil.which("npx") is None:
        pytest.skip("npx not available")
    result = subprocess.run(
        ["npx", "--no-install", "html-validate", str(WEB_FIXTURE / "src" / "index.html")],
        capture_output=True, text=True, cwd=WEB_FIXTURE,
    )
    assert result.returncode in (0, 1), f"html-validate crashed: {result.stderr}"
```

And add to `pyproject.toml` `[tool.pytest.ini_options].markers`:
```toml
markers = [
    "real_web_smoke: requires npx + stylelint + eslint + tsc + html-validate",
]
```

This brings fixture validity into CI as an opt-in smoke (per Phase 3 HIGH-4 recommendation).

---

### MEDIUM-1: Task 6 MCP tests use `pytest.MonkeyPatch()` direct instantiation instead of the `monkeypatch` pytest fixture — fragile cleanup semantics

**Plan reference:** Task 6, lines ~1071-1135.

All 4 new MCP tests instantiate `pytest.MonkeyPatch()` directly and call `monkeypatch.undo()` in `finally`:

```python
async def test_check_web_lint_returns_three_hook_names(tmp_path: Path) -> None:
    monkeypatch = pytest.MonkeyPatch()
    try:
        monkeypatch.setenv("MAHAVISHNU_PROJECT_ROOTS", str(tmp_path))
        _, tools = asyncio.run(_register())
        ...
    finally:
        monkeypatch.undo()
```

**Risk:**
1. **Idiom mismatch** — the rest of the test suite (e.g., Task 3 tests) uses `monkeypatch` as a pytest fixture. Future maintainers will copy-paste this pattern and break isolation if they forget `finally`. The pytest fixture is automatically scoped to the test.
2. **Async + `pytest.MonkeyPatch()` interaction** — `pytest.MonkeyPatch()` does work in async tests, but the pytest fixture is the canonical idiom for async code.
3. **Exception safety** — if `asyncio.run(_register())` succeeds and the assertion fails, `finally: monkeypatch.undo()` runs correctly. But if `asyncio.run(_register())` raises BEFORE setting up state, the env vars from prior tests leak.

**Recommendation:**
Convert all 4 tests to use the `monkeypatch` fixture:

```python
async def test_check_web_lint_returns_three_hook_names(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setenv("MAHAVISHNU_PROJECT_ROOTS", str(tmp_path))
    _, tools = asyncio.run(_register())
    tool = tools["check_web_lint"]
    result = asyncio.run(tool.fn(project_root=str(tmp_path)))
    assert isinstance(result, dict)
    assert "hooks" in result
    names = {h["name"] for h in result["hooks"]}
    assert names == {"web.stylelint", "web.eslint_tsc", "web.html_validate"}
```

This also reduces boilerplate (4 fewer `try/finally` blocks).

---

### MEDIUM-2: No `pytest --cov` verification step in Task 7 — coverage gate may fail late

**Plan reference:** Task 7, line ~1401-1403.

The Task 7 step 4 runs:
```bash
uv run pytest tests/adapters/web/ tests/mcp/tools/test_language_tools.py tests/adapters/test_registry.py --no-cov -q
```

The `--no-cov` flag explicitly disables coverage measurement.

**Risk:**
Per project CLAUDE.md, coverage gate is 89% (`pytest --cov-fail-under`). Phase 4 adds 5 new files:
- `crackerjack/adapters/web/detection.py`
- `crackerjack/adapters/web/hooks.py`
- `crackerjack/adapters/web/python_fallbacks.py`
- `crackerjack/adapters/web/jinja_formatter.py`
- `crackerjack/adapters/web/__init__.py`

Plus modifications to `language_tools.py`. The 8-test detection suite covers most of `detection.py`, but `hooks.py` and `jinja_formatter.py` have branches that may not be covered:
- `hooks.py`: WebHookError branch (no-fallback), pinned-version branches (eslint_pinned, tsc_pinned, both pinned)
- `jinja_formatter.py`: Tier 2 normalize path, lex error fallthrough

**Recommendation:**
Add to Task 7 step 4:
```bash
uv run pytest tests/adapters/web/ tests/mcp/tools/test_language_tools.py tests/adapters/test_registry.py --cov=crackerjack.adapters.web --cov=crackerjack.mcp.tools.language_tools --cov-report=term-missing -q
```

If coverage drops below 89%, identify the gaps (likely WebHookError branch + Tier 2 normalize path) and add tests before Task 7 commits.

---

### MEDIUM-3: `test_capabilities_exposes_jinja_formatter_factory` is a degenerate assertion

**Plan reference:** Task 5, lines ~980-986.

```python
def test_capabilities_exposes_jinja_formatter_factory(tmp_path: Path) -> None:
    (tmp_path / "package.json").write_text("{}")
    caps = WebAdapter().capabilities(tmp_path)
    # Phase 4 doesn't define a "formatter" field on Capabilities; the formatter
    # is exposed via the MCP tool (Task 6). This test just verifies capabilities
    # doesn't break; the MCP tool test covers formatter reachability.
    assert caps is not None
```

`assert caps is not None` is a degenerate assertion — `Capabilities` is a dataclass, so `WebAdapter().capabilities(...)` either returns a `Capabilities` instance or raises. The test asserts neither case explicitly.

**Risk:**
1. **False confidence.** A reviewer reading "8 passed" thinks the formatter is tested. It isn't.
2. **Phase 3 MEDIUM-3 precedent** — the review called out similar degenerate tests in earlier phases.

**Recommendation:**
Either:
- **Option A**: Delete this test (its absence is preferable to a misleading pass).
- **Option B**: Strengthen the assertion to verify the capabilities object has the expected fields:
  ```python
  def test_capabilities_exposes_jinja_formatter_factory(tmp_path):
      (tmp_path / "package.json").write_text("{}")
      caps = WebAdapter().capabilities(tmp_path)
      assert caps.hooks == tuple(h for h in web_hooks(tmp_path))
      assert caps.has_lifecycle is False
      assert caps.version_source is None
  ```

The formatter reachability is correctly tested via Task 6's `test_format_jinja_templates_runs_with_auth` (the happy-path test), so Option A is acceptable.

---

### MEDIUM-4: No pytest-level test that `discover_adapters()` returns `{'kotlin', 'python', 'swift', 'web'}` after Task 5

**Plan reference:** Task 5 step 5, lines ~1046-1048.

The plan has a CLI smoke check:
```bash
uv run python -c "from crackerjack.adapters.registry import discover_adapters; print(sorted(discover_adapters().keys()))"
```

But no pytest-level integration test.

**Risk:**
Per Phase 3 LOW-4 carry-forward, the entry-point contract should be pinned in pytest, not just smoke-tested in CLI. A future maintainer who accidentally removes the entry-point from `pyproject.toml` would pass Task 5 step 5 only if they also smoke-tested manually.

**Recommendation:**
Add to `tests/adapters/test_registry.py`:
```python
def test_discover_adapters_includes_web():
    from crackerjack.adapters.registry import discover_adapters
    from crackerjack.adapters.web import WebAdapter
    adapters = discover_adapters()
    assert "web" in adapters
    assert isinstance(adapters["web"], WebAdapter)
```

---

### LOW-1: `_tool_manager._tools` private attribute carry-forward from Phase 3 MEDIUM-4

**Plan reference:** Task 6, the `_register()` helper at line ~1079-1081 (and Phase 3 carry-forward).

Task 6's MCP tests call `asyncio.run(_register())` to access `tools["check_web_lint"]`. Phase 3's review (MEDIUM-4) flagged that `_register()` depends on `_tool_manager._tools` (private attribute). Phase 4 inherits this carry-forward without explicit acknowledgment.

**Risk:** Same as Phase 3 — future FastMCP version bump could rename or remove `_tool_manager._tools`.

**Recommendation:**
Either:
- Verify that `mcp-common` exposes a `get_registered_tools(mcp_app)` helper (per spec Testing F2). If yes, use it.
- Add an explicit Phase 4 follow-up ledger entry acknowledging the carry-forward.

---

### LOW-2: No `@pytest.mark.real_web_smoke` marker in `pyproject.toml`

**Plan reference:** Task 7 + HIGH-3 above.

Per Phase 3 HIGH-4 precedent, real-CLI tests should be opt-in via a marker. Phase 4 should add the marker to `[tool.pytest.ini_options].markers`.

**Recommendation:**
Add to `pyproject.toml`:
```toml
[tool.pytest.ini_options]
markers = [
    "real_web_smoke: requires npx + stylelint + eslint + tsc + html-validate",
]
```

And gate the HIGH-3 fixture-validation tests with `@pytest.mark.real_web_smoke`.

---

### LOW-3: Task 3 `_eslt_hook` uses `;` as a cli's argv separator — execution semantics not tested

**Plan reference:** Task 3, lines ~582-587 (implementation), `test_eslint_tsc_hook_combines_eslint_and_tsc` at lines ~352-359 (test).

The implementation builds:
```python
cmd = _npx_command("eslint", ".", "--ext", ".ts,.tsx,.js,.jsx") + (";", "tsc", "--noEmit")
```

`;` is a shell metacharacter — passing it as an argv element to `subprocess.run(shell=False)` will NOT execute `tsc --noEmit` after eslint. The hook runner will likely try to execute a binary literally named `;`.

**Risk:**
1. The hook structural test passes (`assert "eslint" in cmd_str; assert "tsc" in cmd_str`), but the hook will FAIL at runtime.
2. This is a wiring bug masquerading as a hybrid hook.

**Recommendation:**
Fix the `_eslt_hook` to encode the two-step invocation differently. Options:
- **Option A**: Use a single `combined` Hook that takes a callable rather than `cli_command` — `Hook(name="web.eslint_tsc", fallback=js_ts_fallback, runner=_run_eslint_then_tsc)`. The runner does `subprocess.run([eslint, ...])` then `subprocess.run([tsc, ...])`.
- **Option B**: Create two separate hooks (`web.eslint`, `web.tsc`) instead of one combined hook.
- **Option C**: Have the hook runner detect `;` and execute sequentially (fragile).

Add a HIGH-priority integration test that actually invokes the runner against a mocked subprocess and asserts BOTH eslint and tsc were called.

This is more of a design review finding than a testing review finding, but it's surfaced by the test pattern.

---

### LOW-4: Plan doesn't define pytest markers per project CLAUDE.md convention

**Plan reference:** Throughout.

Per project CLAUDE.md test conventions:
- `unit`, `integration`, `e2e`, `property`, `slow`, `timeout`, `ci`, `crackerjack` (plus adapter-specific).
- Tests >10s should be `@pytest.mark.slow`.

Phase 4 tests don't use these markers. The `tests/adapters/web/` tests are pure unit tests; they should run without any marker. But the `real_web_smoke` tests (HIGH-3) should be marked appropriately.

**Recommendation:**
Apply markers consistently:
- All `tests/adapters/web/test_*.py` tests: no marker (auto-discovered as unit).
- `tests/adapters/web/test_web_vanilla_fixture.py`: existing tests = no marker; new HIGH-3 tests = `@pytest.mark.real_web_smoke`.

---

## Spec Coverage Summary

| Spec Ref | Requirement | Plan coverage | Status |
|---|---|---|---|
| Testing F2 | mcp-common testing helpers verification | Inherited from Phase 2/3 (LOW-1 carry-forward) | Gap noted in LOW-1 |
| Testing F3 | Hybrid two-path test plan with `monkeypatch.setattr(shutil, "which", ...)` | Task 3 has 1 of 6 required tests; uses `monkeypatch.setattr` in that one test | HIGH-1 |
| Testing F4 | PyCharm parity = Phase 4 deliverable | Correctly tracked as out-of-scope (Phase 4.5) | OK (per Jinja F10) |
| Testing F5 | FakeHookRunner abstraction | Not used in Phase 4 (no shared hook runner built — hooks invoke subprocess directly) | OK |
| Testing F7 | Phase 1 budget and cache | Phase 4 tests are unit-level (<5s each); no real CLI in unit tests | OK |
| Testing F8 | Cross-language fixture split — `web-vanilla/` exists; spec lists `web-only/`, `mixed/`, `real-repo-weekly-smoke/` | Phase 4 creates only `web-vanilla/`; `web-only/`, `mixed/`, `real-repo-weekly-smoke/` deferred | Gap noted (out of scope per plan) |
| Testing F9 | Jinja corpus + golden-master expected output | Fixture files created in Task 7 but NOT referenced from any test | HIGH-2 |
| Jinja F1 | `Environment.lex()` (NOT `parse()`) + round-trip invariant | `lex()` used in implementation; round-trip tested inline (no fixtures) | HIGH-2 |
| Jinja F2 | All 6 delimiter kwargs required | `_env()` passes all 6; tested inline with custom delimiters | OK (but HIGH-2 fixture missing) |
| Jinja F3 | Two-tier canonical policy | Tier 1 + Tier 2 tested inline | OK |
| Jinja F10 | PyCharm parity as one-way fixed-point | Deferred to Phase 4.5; correctly tracked | OK |
| Writing F2 | Hybrid fallback canonical interpretation | Implementation correct; tests don't pin per-hook (HIGH-1) | HIGH-1 |
| Writing F3 | Web detection guard | 8 tests cover all branches (no-package, no-opt-in, opt-in-true, opt-in-false, both-signals, malformed-toml, missing-pyproject) | OK |

---

## Coverage Statement

### What's covered (37 tests across 7 tasks)

| Component | Tests | Coverage |
|---|---|---|
| `web_enabled` / `package_json_present` (detection) | 8 | package.json present/absent, opt-in true/false, both-signals, malformed-toml, missing-pyproject |
| `web_hooks` + `python_fallbacks` (hooks) | 7 | 3 hook names, npx subprocess, eslint+tsc combined, 3 fallback units, 1 combined fallback-invocation |
| `format_template` (Jinja) | 9 | trailing newline, strip trailing whitespace, preserve markers, preserve comments, custom delimiters, unknown tags, round-trip, tier1-only, tier2-normalize |
| `WebAdapter` (adapter) | 8 | subclass of base, name=web, 3 detect branches, no-lifecycle, 3 hooks exposed, capabilities is not None |
| MCP tools | 4 | check_web_lint returns 3 hooks; check_web_lint rejects python-no-opt-in; format_jinja_templates requires auth; format_jinja_templates happy-path-with-auth |
| Fixture-reference | 3 | fixture reachable, adapter detects fixture, adapter capabilities on fixture |

### What's NOT covered (gaps)

1. **(HIGH)** `test_<hook>_uses_cli_when_present` × 3 — only structural assertions on `cli_command`, no runtime exercise (HIGH-1)
2. **(HIGH)** `test_<hook>_falls_back_to_python_when_cli_missing` × 3 — only 1 combined fallback test, no per-hook (HIGH-1)
3. **(HIGH)** `test_<hook>_raises_webhook_error_when_no_fallback` — no error-branch test (HIGH-1)
4. **(HIGH)** Golden-master expected-output tests for `basic.html`, `custom_delimiters.html`, `whitespace.html` fixtures (HIGH-2)
5. **(HIGH)** Real-CLI smoke tests against fixture (HIGH-3)
6. **(MEDIUM)** `pytest --cov` step in Task 7 (MEDIUM-2)
7. **(MEDIUM)** `test_discover_adapters_includes_web` pytest-level integration test (MEDIUM-4)
8. **(MEDIUM)** Strengthen or delete `test_capabilities_exposes_jinja_formatter_factory` (MEDIUM-3)
9. **(MEDIUM)** Convert `pytest.MonkeyPatch()` direct instantiation to `monkeypatch` fixture (MEDIUM-1)
10. **(LOW)** `_tool_manager._tools` carry-forward acknowledgement (LOW-1)
11. **(LOW)** `@pytest.mark.real_web_smoke` marker in `pyproject.toml` (LOW-2)
12. **(LOW)** `_eslt_hook` `;`-separator wiring fix (LOW-3, more design than testing)
13. **(LOW)** Pytest markers per project CLAUDE.md convention (LOW-4)
14. **(CONTEXT)** `tests/fixtures/web-only/` (CSS/HTML only, no Python) — spec Testing F8 lists this; Phase 4 creates only `web-vanilla/`. The plan defers this as out of scope, which is consistent with the spec's "deliver in phases" intent.
15. **(CONTEXT)** `tests/fixtures/mixed/` (fastblocks-like, Python + Web) — same as above.
16. **(CONTEXT)** `tests/fixtures/real-repo-weekly-smoke/` — weekly smoke target; not Phase 4 scope.

### Pytest markers / gating

The plan does NOT define:
- `@pytest.mark.real_web_smoke` for the recommended fixture-validation tests (HIGH-3, LOW-2)
- Any `@pytest.mark.slow` markers (Phase 4 tests appear fast; HIGH-3 smoke tests could exceed 10s on slow CI runners and should be marked)

Per project CLAUDE.md, tests >10s should be `@pytest.mark.slow`.

---

## Suggested additional tests (priority order)

1. **(HIGH)** Add 6 hybrid two-path tests to Task 3 (3 "uses CLI when present" + 3 "falls back when CLI missing").
2. **(HIGH)** Add `test_hook_without_fallback_raises_webhook_error` to Task 3.
3. **(HIGH)** Add `test_format_fixture_against_expected` parameterized test to Task 4; create `*.expected.html` siblings in Task 7.
4. **(HIGH)** Add 3 `real_web_smoke` fixture-validation tests in Task 7.
5. **(HIGH)** Fix `_eslt_hook` `;`-separator design and add an integration test that asserts BOTH eslint and tsc were called.
6. **(MEDIUM)** Convert Task 6 `pytest.MonkeyPatch()` instantiation to `monkeypatch` fixture.
7. **(MEDIUM)** Add `pytest --cov` step to Task 7.
8. **(MEDIUM)** Add `test_discover_adapters_includes_web` pytest test.
9. **(MEDIUM)** Strengthen or delete `test_capabilities_exposes_jinja_formatter_factory`.
10. **(LOW)** Add `@pytest.mark.real_web_smoke` to `pyproject.toml`.

---

## Plan Quality Verdict

**CONDITIONAL PASS** — plan is fundamentally sound:
- Correct TDD discipline (failing test → run → implement → run → commit) in every task
- Phase 2 CRITICAL-1 lesson applied (Task 6 happy-path `test_format_jinja_templates_runs_with_auth` correctly mirrors Phase 2 happy-path test)
- Phase 3 spec-mandate idiom (`monkeypatch.setattr(shutil, "which", ...)`) correctly used in Task 3's one fallback test
- Web detection guard correctly tested with 8 tests covering all branches (Phase 3 HIGH-4 precedent applied to detection)
- Real Web fixture committed under `tests/fixtures/web-vanilla/`
- PyCharm parity correctly deferred to Phase 4.5 (per Jinja F10)
- Tier 1 + Tier 2 policy correctly tested

**HIGH-severity gaps are concentrated in:**
1. Task 3 hybrid two-path test plan incomplete (6 of 6 mandated tests missing)
2. Task 4 has no golden-master expected-output tests
3. Task 7 fixture is decorative (no real-CLI smoke)

**Recommended action before Task 7 closes:** Address HIGH-1, HIGH-2, HIGH-3. The MEDIUM items can be filed as Phase 4 follow-ups if not blocking. LOW-3 (`_eslt_hook` design bug) should be addressed during Task 3 implementation, not after.

---

## Status

**REVIEW_COMPLETE** — review file written. Plan implementation can proceed with the recommended follow-ups tracked in a Phase 4 ledger entry.

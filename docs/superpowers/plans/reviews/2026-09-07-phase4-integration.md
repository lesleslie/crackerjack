# Integration / Spec Fidelity / Cross-Adapter Lens Review — Phase 4 Rev 2

> **Reviewer scope:** 9th lens — catches what 8 domain-specific lenses
> (a11y, api, mcp, security, simplification, testing, web, writing)
> couldn't: **interface consistency, spec fidelity, cross-adapter
> consistency**.
>
> **Verdict at a glance:** Plan is ready to execute after fixing **3
> test defects** in Task 4 (`test_lex_failure_returns_source_unchanged`
> and `test_does_not_strip_crlf_terminators`) and **2 arithmetic / rename
> nits** in Task 6 (`_six_tools` should be `_seven_tools`, test count
> is 13 not 17). No spec deviations are unrecorded. No cross-adapter
> claims are outright falsified, but one claim ("Swift/Kotlin's `name =
> \"swift\"` style") is half-true (Kotlin uses `name: str = "kotlin"`).

## Method

**Files read:**

- `docs/superpowers/plans/2026-09-07-crackerjack-multi-language-phase4.md`
  (the plan, Rev 2, ~1,547 lines — full read)
- `docs/superpowers/specs/2026-09-07-crackerjack-multi-language-design.md`
  (spec Rev 2 — full read, Phase 4 lines 363-429 + Jinja F1/F2/F3/F11 +
  MCP F1-F7 + Testing F9 + line 713 acceptance target)
- `crackerjack/adapters/swift/__init__.py` (full)
- `crackerjack/adapters/swift/hooks.py` (full)
- `crackerjack/adapters/kotlin/__init__.py` (full)
- `crackerjack/adapters/kotlin/hooks.py` (full)
- `crackerjack/adapters/base.py` (full — Hook, Capabilities, Lifecycle,
  LanguageAdapter Protocol + ABC, error hierarchy)
- `crackerjack/mcp/tools/language_tools.py` (full — confirmed
  `_require_auth_config`, `_validate_project_root`, `_run_swift_*`,
  `_run_kotlin_*`, `register_language_tools` with the existing 5 tools)
- `crackerjack/adapters/registry.py` (full — `discover_adapters`
  indexes by `obj.name`, validates LanguageAdapter)
- `tests/mcp/tools/test_language_tools.py` (full — counted tests,
  confirmed async/sync split)
- `tests/adapters/test_registry.py` (full — verified path & `discover_adapters`)
- `pyproject.toml` (full — confirmed entry-points, `jinja2` not in
  `[project.dependencies]`, markers, `[tool.crackerjack]`, coverage
  fail-under = 68.42%)

**Commands run:**

- `/Users/les/Projects/crackerjack/.venv/bin/python -c "import jinja2; print('jinja2 version:', jinja2.__version__)"` → `3.1.6` (✓)
- `grep -A 4 "crackerjack.language_adapters" pyproject.toml` → `python`, `swift`, `kotlin` (✓ matches plan's "3 entries" Step 1 expectation)
- `grep "jinja2" pyproject.toml` → empty (✓ jinja2 is transitive only, matches plan's claim)
- `grep -n "jinja2" uv.lock` → 3 hits at lines 1805/2426/4695 (✓ dep installed transitively)
- `grep -n "^def test_\|^async def test_" tests/mcp/tools/test_language_tools.py` → 13 tests (5 sync + 1 sync register + 6 async Kotlin — 1 async Kotlin `wait, let me recount)
  - Line 24: `test_register_language_tools_registers_three_tools` (sync, 1)
  - Line 35: `test_swift_bump_version_requires_auth` (sync, 2)
  - Line 44: `test_swift_bump_version_runs_with_auth` (sync, 3)
  - Line 77: `test_swift_list_hooks_does_not_require_auth` (sync, 4)
  - Line 96: `test_swift_bump_version_rejects_path_traversal` (sync, 5)
  - Line 111: `test_swift_bump_version_rejects_relative_path_traversal` (sync, 6)
  - Line 125: `test_detect_languages_returns_adapter_names` (sync, 7)
  - Line 143: `test_kotlin_list_hooks_returns_three_hook_names` (async, 8)
  - Line 164: `test_kotlin_list_hooks_rejects_non_kotlin_directory` (async, 9)
  - Line 177: `test_kotlin_bump_version_requires_auth` (async, 10)
  - Line 191: `test_kotlin_bump_version_runs_with_auth` (async, 11)
  - Line 253: `test_kotlin_bump_version_rejects_non_kotlin_directory` (async, 12)
  - Line 268: `test_kotlin_bump_version_rejects_invalid_level` (async, 13)
- `grep -n "^def test_" tests/adapters/test_registry.py` → 5 tests (✓)
- `find crackerjack -name "test_registry.py"` → only `tests/adapters/test_registry.py` exists (the legacy AdapterRegistry tests live in a separate file `tests/adapters/test_adapter_registry.py` — plan correctly targets the new file)

**Empirical Python checks:**

- `Environment.lex('before {% trans %}hello{% endtrans %} after\n')` succeeds with no extensions loaded (✓ matches Spec Jinja F7 claim and the plan's `test_unknown_tag_is_tolerated` assumption).
- `Environment.lex('{% if x %}A{% endif %}')` with default delimiters succeeds (default delimiters recognize `{%`).
- `Environment.lex('[% if x %]A[% endif %]')` with default delimiters succeeds (the `[%` is just literal text to the lexer).
- `Environment.lex('{% if x %}A{% endif %}')` with `[%` / `%]` block delimiters raises `TemplateSyntaxError: unexpected '%'` (lex DOES fail on mismatched delimiters when source uses `{%`/`%}` against an env that defines them as non-block starts).
- `_apply_tier1('hello\r\n')` returns `'hello\n'` (Python's `str.splitlines()` strips the `\r\n` boundary — **plan's test asserts `'hello\r\n'` which is wrong**).

**Did not run:**

- `pytest tests/mcp/tools/test_language_tools.py -k web` (Phase 4 tools don't exist yet — expected failure).
- `crackerjack run -p minor` (Task 7 Step 5 — depends on Phase 4 implementation).

## Findings (most-severe first)

### F-1 [HIGH] Test `test_lex_failure_returns_source_unchanged` is broken

**Evidence:** Plan lines 691-699. The test:

```python
def test_lex_failure_returns_source_unchanged(self) -> None:
    src = "{% if x %}A{% endif %}"
    with pytest.raises(Exception):
        _env({"block_start": "[%", "block_end": "%]"})
    # But format_template catches TemplateSyntaxError internally and returns src.
    bad = _env({"block_start": "[%", "block_end": "%]", "variable_start": "[[", "variable_end": "]]",
                "comment_start": "[#", "comment_end": "#]"})
    assert format_template(src, delimiters=bad[1]) == src
```

`_env()` returns a `jinja2.Environment` (single value), not a tuple. `bad[1]` raises `TypeError: 'Environment' object is not subscriptable` BEFORE the assertion runs. The test fails for the wrong reason.

The first `pytest.raises(Exception): _env({...})` block IS useful — it confirms that `_env` raises `KeyError` when given an incomplete delimiter map (only 2 of 6 keys). But that has nothing to do with the "lex failure" semantic the test name promises.

**Why it matters:** This is a fake-green trap — a test that always fails with TypeError, masking whether `format_template` correctly handles lex failures. The test never asserts the property it claims to test.

**How to fix:** Drop the `bad = _env(...)` indirection. Pass the 6-key dict directly to `format_template`:

```python
def test_lex_failure_returns_source_unchanged(self) -> None:
    """lex() failure on mismatched delimiters → source returned unchanged."""
    src = "{% if x %}A{% endif %}"
    custom_delims = {
        "block_start": "[%", "block_end": "%]",
        "variable_start": "[[", "variable_end": "]]",
        "comment_start": "[#", "comment_end": "#]",
    }
    # Source uses {% but env expects [%. env.lex() raises TemplateSyntaxError;
    # format_template catches and returns src.
    assert format_template(src, delimiters=custom_delims) == src
```

Empirically verified: `Environment.lex('{% if x %}A{% endif %}')` with `[%`/`%]` block delimiters raises `TemplateSyntaxError`. The patched test will pass.

---

### F-2 [HIGH] Test `test_does_not_strip_crlf_terminators` asserts the wrong expected value

**Evidence:** Plan lines 682-687:

```python
def test_does_not_strip_crlf_terminators(self) -> None:
    # CRLF preservation is out of scope for Phase 4 (deferred; see Spec Revision Notes).
    src = "hello\r\n"
    # Phase 4 only normalizes the trailing-newline rule; we don't currently
    # rewrite CRLF, so the value passes through (possibly with trailing-whitespace strip).
    assert _apply_tier1(src) == "hello\r\n"
```

`_apply_tier1` (lines 813-829 of the plan) does:

```python
lines = source.splitlines()              # "hello\r\n".splitlines() → ["hello"]
lines = [line.rstrip() for line in lines]  # no-op
out = "\n".join(lines)                    # "hello"
if source.endswith("\n"):                 # "hello\r\n".endswith("\n") → True
    out += "\n"                           # "hello\n"
return out
```

Returns `"hello\n"`. Test asserts `"hello\r\n"`. **Test fails.**

**Why it matters:** Python's `str.splitlines()` strips the line terminator entirely (CR, LF, or CRLF). The plan's Spec Revision Notes #8 ("CRLF preservation deferred") and the test comment both claim Phase 4 doesn't normalize CRLF — but the code does, because `splitlines()` + `"\n".join()` is the canonical "normalize to LF" idiom. The test's expected value contradicts the implementation.

**How to fix:** Change the assertion to match actual behavior:

```python
def test_normalizes_crlf_to_lf(self) -> None:
    """Phase 4 normalizes CRLF → LF (deferred for explicit preservation;
    see Spec Revision Notes #8)."""
    assert _apply_tier1("hello\r\n") == "hello\n"
```

Or, if the team actually wants to preserve CRLF (which Spec Revision Notes #8 leaves ambiguous), add a `keep_crlf=True` flag to `_apply_tier1` and propagate it through `format_template`. The latter is out of scope per the spec notes, so the former is the correct fix.

---

### F-3 [HIGH] Cross-adapter claim about `name` style is half-true

**Evidence:**

- `crackerjack/adapters/swift/__init__.py:21` → `name = "swift"` (bare assignment)
- `crackerjack/adapters/kotlin/__init__.py:23` → `name: str = "kotlin"` (annotated)

Plan line 911 (Task 5 Step 3 preamble):

> "Mirrors Swift/Kotlin's `name = "swift"` style (bare assignment, NOT `name: str =`) — the ClassVar annotation is inherited from `LanguageAdapterBase`."

And plan line 1511 (Self-Review):

> "`name = "web"` (ClassVar inherited, no annotation) ✓ (closes Web MEDIUM-5)"

The "Swift/Kotlin" attribution only holds for Swift. Kotlin re-annotates as `name: str` (which narrows the inherited `ClassVar[str]` to a plain class attribute — semantically equivalent at runtime but loses the ClassVar metadata). The plan's chosen `name = "web"` matches Swift, not Kotlin.

**Why it matters:** Mild — the plan's `name = "web"` is functionally correct either way. But the Self-Review table cites "Web MEDIUM-5" as the source for the bare-assignment choice. If that finding only inspected Swift, the plan's rationale is incomplete; if it inspected both and ignored Kotlin, the rationale is inconsistent.

**How to fix:** Either (a) change Self-Review wording to "Mirrors Swift's `name = "swift"` style (bare assignment; Kotlin uses `name: str = "kotlin"` and would also be valid)" or (b) accept Kotlin's annotated style (`name: str = "web"`). Both work — pick one and update the citation.

---

### F-4 [MEDIUM] Test count arithmetic is off by 4

**Evidence:** Plan line 1265:

> "Expected: All pass (17 prior + 4 new web = 21 in test_language_tools.py, plus the new test_registry.py entry)."

Actual count in `tests/mcp/tools/test_language_tools.py` (via grep): **13 tests** (7 sync Swift + 1 sync register + 5 async Kotlin + 1 async `wait` no actually: 7 sync + 6 async = 13). Adding 4 new web = 17. Plus 1 new registry test = 18.

The plan over-counts by 4 tests. This is a cosmetic issue but suggests the verification expectation was never sanity-checked against `pytest --collect-only -q tests/mcp/tools/test_language_tools.py`. The implementation will produce 17 + 1 = 18 tests, not 21.

**Why it matters:** Verification expectation mismatches reality — could mask other count-related issues (e.g., a test silently deleted).

**How to fix:** Update line 1265 to "Expected: All pass (13 prior + 4 new web = 17 in test_language_tools.py, plus the new test_registry.py entry)." Same fix needed for Task 7 Step 4 ("~55 passed (8 detection + 12 hooks + 13 formatter + 8 adapter + 21 mcp + 1 registry = 63..."). The "21 mcp" should be "17 mcp"; the total "63" should be "59".

---

### F-5 [MEDIUM] Tool count rename "three_tools" → "six_tools" is wrong (should be "seven_tools")

**Evidence:** Plan lines 1258-1260:

> "Update `test_register_language_tools_registers_three_tools` → `_six_tools`. Find the existing assertion in `tests/mcp/tools/test_language_tools.py` that asserts a specific tool count and update it to six tools (swift_bump_version, swift_list_hooks, detect_languages, kotlin_bump_version, kotlin_list_hooks, plus the two new ones)."

Counting: 3 Swift + 2 Kotlin (Phase 3) + 2 Web (Phase 4) = **7 tools**, not 6. The plan missed that Phase 3 already added Kotlin tools — the existing test name "three_tools" was accurate for Phase 2 only, not Phase 3+.

**Why it matters:** Test name will not match the asserted count — minor but misleading for future readers grepping the test file.

**How to fix:** Rename `_six_tools` to `_seven_tools` and assert all 7 tool names (existing 5 + `check_web_lint` + `format_jinja_templates`).

---

### F-6 [MEDIUM] `has_version` is a property, not a field — plan language is slightly misleading

**Evidence:** `crackerjack/adapters/base.py:93`:

```python
@property
def has_version(self) -> bool:
    return self.version_source is not None
```

Plan test (line 954):

```python
def test_capabilities_has_no_lifecycle(self, tmp_path: Path) -> None:
    ...
    assert caps.has_lifecycle is False
    assert caps.has_version is False
```

The test correctly accesses `has_version` as a property and will pass for `Capabilities(version_source=None, hooks=..., has_lifecycle=False)`. But the plan's Self-Review table (lines 1509-1510) lists `has_lifecycle=False` and `version_source=None` as separate items without mentioning `has_version` is derived from `version_source`.

**Why it matters:** A reader reading the Self-Review table might assume `has_version` is a fourth field to set. Minor doc clarity issue.

**How to fix:** Add a Self-Review row: "`has_version=False` derived from `version_source=None` (per `Capabilities.has_version` property)" — or just drop the `assert caps.has_version is False` line since it's tautological given `version_source=None`.

---

### F-7 [MEDIUM] Plan claim "tests are sync `def` matching the file's existing 13 tests" is wrong

**Evidence:** Plan line 1045:

> "tests are sync `def` matching the file's existing 13 tests; use `mock.patch.dict(os.environ, {...}, clear=True)` not `pytest.MonkeyPatch()`."

Of the 13 existing tests:
- 7 are `def test_*` (sync) — all Swift-era
- 6 are `async def test_*` (async) — all Phase 3 Kotlin

The plan's 4 new web tests use `def test_*` + `asyncio.run(...)` (sync wrapper) — matching the Swift pattern. They're not stylistically consistent with the more-recent Kotlin async pattern.

**Why it matters:** Codebase drift. Future Phase 5 work will see two patterns for new MCP tests; whichever the team standardizes on will leave a legacy mismatch.

**How to fix:** Either (a) make the new web tests `async def` to match the Kotlin precedent, or (b) explicitly document the choice in the plan ("sync def + asyncio.run chosen for Web because `format_jinja_templates` is more analogous to `swift_bump_version` than `kotlin_bump_version`"). The current plan code is fine; only the claim is wrong.

---

### F-8 [LOW] Swift/Kotlin `Hook` doesn't pass `fallback=None` or `cli_required=True` explicitly

**Evidence:** Plan line 1535 (Self-Review):

> "`cli_required=True, fallback=None` for hooks. ... Swift/Kotlin precedent: `cli_required=True, fallback=None`."

But `crackerjack/adapters/swift/hooks.py:48-71` constructs Hooks with only `name`, `cli_command`, `timeout_seconds`, `autofix` — never `fallback` or `cli_required`. Same for Kotlin (`kotlin/hooks.py:78, 85`). Both rely on dataclass defaults (`fallback=None`, `cli_required=True`).

Plan `webhooks._build_hook` (line 524):

```python
return Hook(name=name, cli_command=argv, fallback=None, timeout_seconds=timeout_seconds)
```

Passes `fallback=None` explicitly. Behaviorally identical to Swift/Kotlin (default is None).

**Why it matters:** Cross-adapter consistency claim is technically right (effect is `fallback=None`) but the reasoning is slightly off — Swift/Kotlin don't pass these explicitly, they rely on defaults.

**How to fix:** Either pass `fallback=None` only in the Web hooks (which the plan does) and update the Self-Review citation to "defaults from `Hook` dataclass — `fallback: Callable | None = None`, `cli_required: bool = True`" or drop `fallback=None` from Web hooks to match Swift/Kotlin's "don't pass defaults" style. The latter is cleaner.

---

### F-9 [LOW] Swift detection is inline as `(project_root / "Package.swift").is_file()` — plan claim is slightly off

**Evidence:** Plan line 173 (Task 2 preamble):

> "Swift and Kotlin inline `(project_root / "Package.swift").is_file()` and the build.gradle checks respectively — no detection module."

Verified: Swift `__init__.py:24` is exactly `(project_root / "Package.swift").is_file()`. Kotlin `__init__.py:26` is `(project_root / "build.gradle.kts").is_file() or (project_root / "build.gradle").is_file()` (two checks for `.kts` OR `.kts`-less). The plan's Web `__init__.py:264` mirrors Swift's style (`(project_root / "package.json").is_file()`). ✓

This finding is INFO — no defect, just a cross-check that confirmed the cross-adapter claim.

---

### F-10 [INFO] `_validate_project_root` and `_require_auth_config` exist as documented

**Evidence:**

- `crackerjack/mcp/tools/language_tools.py:25-44` — `_require_auth_config()` checks `MAHAVISHNU_AUTH_ENABLED == "true"` and `MAHAVISHNU_JWT_SECRET` set. Raises `PermissionError` with helpful message.
- `crackerjack/mcp/tools/language_tools.py:52-89` — `_validate_project_root(project_root: str) -> Path`:
  - Rejects NUL bytes
  - Rejects `..` in path parts
  - Resolves via `Path.resolve(strict=False)`
  - Reads `MAHAVISHNU_PROJECT_ROOTS` (colon-separated) and requires the resolved `root` to be within one of the allowed paths
  - **Fail-closed when env var is unset** (Phase 2 final-review IMPORTANT-1, lines 78-83): `if not allowed_env: raise PermissionError(...)`

Plan Task 6 reuses both. ✓ Verified. No finding — just confirmation.

---

### F-11 [INFO] `Environment.lex()` tolerates `{% trans %}` without loading i18n extension

**Evidence:** Empirical: `jinja2.Environment(keep_trailing_newline=True).lex('before {% trans %}hello{% endtrans %} after\n')` returns token stream without raising.

Plan line 1329: "lex() tolerates unknown tags (extension tags like `{% trans %}`, `{% loopcontrols %}`) — parse() hard-fails on these (per Jinja F7)."

✓ Verified. Spec Jinja F7 claim and the plan's `test_unknown_tag_is_tolerated` assumption both hold.

---

### F-12 [INFO] jinja2 3.1.6 installed; not in `[project.dependencies]`

**Evidence:**

- `import jinja2; jinja2.__version__` → `3.1.6` (✓)
- `grep "jinja2" pyproject.toml` → empty (✓ currently transitive only)
- `uv.lock` lines 1805, 2426, 4695 reference jinja2 (✓ dep is installed)

Plan Task 1 adds `"jinja2>=3.1.6"` to `[project.dependencies]` per Spec Jinja F11. ✓ Will fix the "currently only present transitively" state.

---

### F-13 [INFO] `discover_adapters()` indexes by `obj.name`, supports `web` key

**Evidence:** `crackerjack/adapters/registry.py:123` — `adapters[obj.name] = obj`. Plan's `assert "web" in adapters` and `assert isinstance(adapters["web"], WebAdapter)` (lines 1142-1143) work as written. ✓

---

### F-14 [INFO] Hook dataclass equality works for `caps.hooks == web_hooks(...)` test

**Evidence:** `crackerjack/adapters/base.py:60-72` — `Hook` is `@dataclass(frozen=True)` with `name`, `cli_command`, `fallback`, `timeout_seconds`, `autofix`, `cli_required`. Frozen dataclass generates `__eq__` field-by-field.

Plan test (line 971): `assert caps.hooks == web_hooks(tmp_path)`. Both calls happen within the same test invocation, so `_resolve()` returns the same argv tuple (deterministic given same `shutil.which` env). The Hook fields will match. ✓

Caveat: If `tmp_path` is mutated between the two calls (e.g., a test creates `node_modules/.bin/stylelint` between calls), the resolved argv would differ. The plan's test does NOT mutate `tmp_path` between calls, so equality holds.

---

### F-15 [INFO] Swift hooks construct an environment probe before emitting Hooks

**Evidence:** `crackerjack/adapters/swift/hooks.py:44`:

```python
parse_platforms(package_swift_path)  # validates the file; result discarded
```

Swift parses the Package.swift upfront (validates it can be read) but discards the result. Web has no equivalent step — `web_hooks(project_root)` just calls `_resolve()` for each tool, which is filesystem-only (looks for `node_modules/.bin/<tool>`). No upfront validation. That's fine — Web doesn't have a manifest file that needs parsing before hook construction.

Not a defect, just an asymmetry between Swift and Web worth noting in case a future reviewer wonders why Web skips the upfront probe.

---

### F-16 [INFO] Plan references spec lines correctly

**Evidence:** Spot-checked:

- Spec line 65 (no lifecycle for Web/CSS/HTML/JS/TS) → plan Task 5 `has_lifecycle=False`. ✓
- Spec line 96-101 (entry-points module form) → plan Task 1 adds `web = "crackerjack.adapters.web:WebAdapter"`. Plan deviates by pointing at `WebAdapter` class (not module) — this is correct because `crackerjack/adapters/swift/__init__.py` and `crackerjack/adapters/kotlin/__init__.py` point at classes too. ✓
- Spec line 365 (eslint + tsc as single bullet) → plan Task 3 splits into 2 hooks. ✓ Recorded in Spec Revision Notes #3.
- Spec line 420 (shared `jinja-test-fixtures/` Bodai sibling) → plan defers. ✓ Recorded in Spec Revision Notes #7.
- Spec line 572 (CLI subcommand `crackerjack web jinja format`) → plan defers. ✓ Recorded in Spec Revision Notes #6.
- Spec Jinja F11 (jinja2 direct dep) → plan Task 1 adds it. ✓
- Spec Jinja F1 (lex() not parse()) → plan Task 4 uses `env.lex()`. ✓
- Spec Jinja F2 (all 6 delimiter kwargs) → plan Task 4 `_env()` passes 6. ✓
- Spec Jinja F3 (Tier 1 always-on) → plan Task 4 `_apply_tier1`. ✓
- Spec Jinja F10 (PyCharm parity) → plan defers. ✓ Recorded in Spec Revision Notes #5.
- Spec MCP F1 (4-step pipeline) → plan Task 6 reuses existing `language_tools` group. ✓
- Spec MCP F5 (auth on mutation) → plan Task 6 calls `_require_auth_config()`. ✓
- Spec Testing F9 (round-trip + golden-master) → plan Task 7 step 2 creates golden corpus. ✓
- Spec line 713 (Phase 4 acceptance target = fastblocks) → plan defers PyCharm parity script (Spec Revision Notes #5). The "Test on fastblocks, splashstand" assertion is not in any task — gap noted.

**Gap (not a finding, just observation):** The spec line 713 says "Test on `fastblocks`, `splashstand`" as a Phase 4 acceptance criterion. The plan has no task that exercises these real-world fixtures (the closest is Task 7's `web-vanilla` fixture, which is a synthetic project). If the team intends to validate against fastblocks/splashstand, add a Step 8 to Task 7. If not, add an explicit deferral entry to Spec Revision Notes.

---

### F-17 [INFO] Self-Review table accuracy

**Evidence:** Walked the Self-Review table (lines 1483-1522) row by row. Of 36 rows:

- 32 rows claim ✓; verified as accurate (matches Tasks 1-7 + Spec Revision Notes).
- 2 rows have minor wording issues:
  - Row "`name = "web"` (ClassVar inherited, no annotation) ✓ (closes Web MEDIUM-5)" → see F-3 (Kotlin precedent is annotated, not bare).
  - Row "`cli_required=True, fallback=None` for hooks ✓ (closes Web MEDIUM-5)" → see F-8 (Swift/Kotlin use defaults, don't pass explicitly).

- 2 rows are about deferred items (Spec Revision Notes), correctly marked ✓.
- 0 rows claim items that aren't actually in the plan.
- 0 rows miss items that should be in the plan (modulo F-16's fastblocks/splashstand observation).

Self-Review accuracy is **very high** — Rev 2 cleanup was thorough.

---

## Coverage statement

**Focus 1 (Interface consistency across 7 tasks):**

- Verified all 4 hook names (`web.stylelint`, `web.eslint`, `web.tsc`, `web.html_validate`) are consistent across Tasks 3, 5, 6, 7. ✓
- Verified `format_template` signature `(source: str, delimiters: Mapping[str, str] | None = None) -> str` is consistent — no caller in the plan passes `normalize=`. ✓ (Removed in Rev 2.)
- Verified `_load_jinja_config(project_root) -> tuple[Mapping[str, str], bool]` returns `(delimiters, False)`. ✓ (MCP Task 6 calls it correctly.)
- Verified `format_jinja_templates(dry_run: bool = True)` signature matches all 4 test calls. ✓
- Verified `_resolve(project_root, tool) -> tuple[str, ...] | None` is used consistently. ✓
- Verified `WebHookError` is raised in `_build_hook` and tested in `test_hooks.py`. ✓
- Verified `web_enabled(project_root)` is imported by MCP Task 6 as `from crackerjack.adapters.web import web_enabled` (inline import inside `check_web_lint` and `format_jinja_templates`). Per MCP MEDIUM 3, imports should be at module top — the inline import contradicts that requirement. **See additional finding below.**

**Additional finding (focus 1):** Plan Task 6 Step 3 declares:

```python
from crackerjack.adapters.web import WebAdapter
from crackerjack.adapters.web.jinja_formatter import JINJA_SUFFIXES, _apply_tier1, _load_jinja_config, format_template
from crackerjack.adapters.web.hooks import _parse_eslint_json, _parse_html_validate_json, _parse_stylelint_json, _parse_tsc_output
```

But then inside `check_web_lint` and `format_jinja_templates`:

```python
from crackerjack.adapters.web import web_enabled
```

…and also:

```python
from crackerjack.adapters.python import PythonAdapter  # not in plan, but pattern observed in language_tools.py:286, 331
```

This is the **inverse** of MCP MEDIUM 3 ("imports at module top, not inline"). The plan has inline imports inside the tool functions but should move them to module top. The existing language_tools.py:286 / 331 (kotlin imports) is also inline — so this is a precedent violation that's been carried forward into Phase 4 instead of corrected.

Severity: LOW. Not a BLOCKER. The code works; it's a style consistency issue.

---

**Focus 2 (Spec fidelity):**

Walked all spec items claimed by the plan. Findings:

- 32 of 36 spec items fully addressed. See Spec fidelity table below.
- 1 spec gap noted: spec line 713 "Test on fastblocks, splashstand" has no corresponding plan task. (F-16)
- 0 spec deviations unrecorded. Spec Revision Notes covers all 8 deliberate deviations (Tier 2, Python fallbacks, eslint_tsc split, detection.py absence, PyCharm parity, CLI subcommand, jinja-test-fixtures, CRLF preservation).

---

**Focus 3 (Cross-adapter consistency):**

- Swift/Kotlin precedent claims walked. 5 verified ✓, 2 have minor wording issues (F-3, F-8). 0 outright falsifications.
- See Cross-adapter consistency table below.

---

## Spec fidelity table

| Spec item | Plan claim | Verified |
|---|---|---|
| Web detection guard (Writing F3) | Task 2 `web_enabled()` + MCP `format_jinja_templates` check | ✓ |
| 4 hooks: stylelint, eslint, tsc, html-validate (split per Phase 4 lens review) | Task 3 splits `web.eslint_tsc` into 2 | ✓ |
| CLI-only hooks (no Python fallbacks) | Task 3 `_resolve()` raises `WebHookError` | ✓ |
| Hook JSON output parsing | Task 3 parsers (stylelint/eslint/html-validate + tsc regex) | ✓ |
| Modern `npx --no` spelling | Task 3 `_resolve` returns `("npx", "--no", tool)` | ✓ |
| `_resolve()` single resolver replaces inverted guard | Task 3 lines 491-505 | ✓ |
| Hybrid pattern note: Phase 4 ships non-hybrid | Spec Revision Notes #2 | ✓ |
| MCP tool wrappers nested inside `register_language_tools` | Task 6 step 3 | ✓ |
| MCP tool imports at module top | Task 6 step 3 | ⚠ inline `from crackerjack.adapters.web import web_enabled` inside 2 tool functions (MCP MEDIUM 3 violation) |
| MCP tests sync `def` with `mock.patch.dict` | Task 6 step 1 | ⚠ existing file is 7 sync + 6 async; new tests only match sync subset |
| `format_jinja_templates` enforces Web detection at MCP layer | Task 6 lines 1235-1239 | ✓ |
| `format_jinja_templates` reads `[tool.crackerjack.jinja]` config | Task 6 line 1240 | ✓ |
| `format_jinja_templates` `dry_run=True` default + symlink guard | Task 6 lines 1205, 1243-1244 | ✓ |
| Happy-path test reads back file mutation | Task 6 line 1132-1134 | ✓ |
| `test_detect_languages_returns_adapter_names` asserts all 4 adapters | Task 6 lines 1067-1070 | ✓ |
| Jinja F1: `lex()` for validation, Tier 1 raw-source ops | Task 4 `_apply_tier1` | ✓ (empirical: lex tolerates `{% trans %}`) |
| Tier 2 deferred | Spec Revision Notes #1 | ✓ |
| Jinja F2: all 6 delimiter kwargs | Task 4 `_env` | ✓ |
| `keep_trailing_newline=True` | Task 4 `_env` line 809 | ✓ |
| Round-trip invariant + golden-master | Task 7 step 2 | ✓ |
| `jinja2>=3.1.6` direct dep | Task 1 step 3 | ✓ (jinja2 3.1.6 installed; dep is currently transitive only — Task 1 fixes it) |
| `WebHookError` raised + tested | Task 3 lines 487, 410 | ✓ |
| No lifecycle (spec line 65) | Task 5 `has_lifecycle=False` | ✓ |
| `has_lifecycle=False` and `version_source=None` | Task 5 lines 1006, 1008 | ✓ |
| `name = "web"` (ClassVar inherited, no annotation) | Task 5 line 997 | ⚠ Swift bare, Kotlin annotated — only matches Swift |
| `detection.py` folded into `__init__.py` | Task 2 lines 244-293 | ✓ Swift/Kotlin precedent |
| No `python_fallbacks.py` module | Task 3 absent | ✓ |
| Real-CLI smoke tests gated on availability | Task 7 step 3 | ✓ |
| CHANGELOG entry with structured categories | Task 7 step 6 | ✓ |
| Spec Revision Notes populated (8 items) | Lines 1526-1542 | ✓ all deviations recorded |
| Self-Review section | Lines 1483-1522 | ✓ 32/36 rows fully verified |
| `_validate_project_root` reuse (Phase 3 fail-closed) | Task 6 | ✓ at `language_tools.py:78-83` |
| `_require_auth_config` reuse | Task 6 | ✓ at `language_tools.py:25-44` |
| `monkeypatch.setattr` for test env isolation | Tasks 2-7 | ✓ |
| No shell, argv list only | Task 3 | ✓ |
| Spec line 713: Phase 4 acceptance target = fastblocks | Plan has synthetic `web-vanilla` fixture only; no fastblocks/splashstand task | ⚠ Spec gap (not in plan) |

---

## Cross-adapter consistency table

| Claim | Swift precedent | Kotlin precedent | Verified |
|---|---|---|---|
| No `detection.py` module | True (`__init__.py:24` inlines `(project_root / "Package.swift").is_file()`) | True (`__init__.py:26` inlines build.gradle checks) | ✓ Plan matches |
| `cli_required=True, fallback=None` for hooks | Defaults used (`Hook(...)` with no `fallback`/`cli_required`) | Defaults used | ⚠ Plan passes `fallback=None` explicitly — effect identical |
| `Hook` dataclass signature | `name`, `cli_command`, `fallback=None`, `timeout_seconds=600`, `autofix=False`, `cli_required=True` | Same | ✓ Plan's `_build_hook` matches |
| `Capabilities(version_source=None, has_lifecycle=False)` shape | `Capabilities(version_source=..., hooks=..., has_lifecycle=True)` | Same as Swift | ✓ Web uses `None`/`False` (matches spec line 65) |
| `name = "swift"` (bare assignment, not annotated) | True (`__init__.py:21`: `name = "swift"`) | FALSE (`__init__.py:23`: `name: str = "kotlin"`) | ⚠ Plan only matches Swift; Kotlin has annotation |
| `_validate_project_root` exists | n/a | n/a | ✓ at `language_tools.py:52` |
| `_require_auth_config` exists | n/a | n/a | ✓ at `language_tools.py:25` |
| Inline imports inside tool functions (kotlin pattern at language_tools.py:286, 331) | n/a | True (inline `from crackerjack.adapters.kotlin import KotlinAdapter` inside `kotlin_bump_version` / `kotlin_list_hooks`) | ⚠ Plan continues the pattern (inline `from crackerjack.adapters.web import web_enabled` inside 2 tool functions) |
| Inline detection in `__init__.py` | True (line 24) | True (line 26) | ✓ Plan matches |

---

## Plan quality verdict

**Phase 4 Rev 2 is fundamentally sound.** The 9th-lens review found:

- **3 test defects** (F-1 broken test, F-2 wrong CRLF assertion, F-3 cross-adapter claim half-true) that should be fixed before execution.
- **2 arithmetic / rename nits** (F-4 test count, F-5 "six_tools" → "seven_tools") that are cosmetic but misleading.
- **2 style-consistency issues** (F-6 `has_version` property doc clarity, F-7 sync vs async test pattern) and **1 inline-import contradiction** (MCP MEDIUM 3) carried over from Phase 3.
- **1 spec gap** (F-16): spec line 713's "Test on fastblocks, splashstand" has no corresponding plan task — needs explicit deferral in Spec Revision Notes or a new task added.
- **0 unrecorded spec deviations.** All 8 deviations in Spec Revision Notes are deliberate and well-justified.
- **0 outright cross-adapter falsifications.** All claims hold for at least one of Swift/Kotlin.

The 3 test defects (F-1, F-2, F-3) are blockers in the sense that running Task 4 step 5 ("Expected: 10 passed") will fail on the very first run. The plan should be amended to fix these before any execution begins. The 2 arithmetic nits (F-4, F-5) should be fixed in the same pass. The remaining items are advisory.

**Recommended pre-execution amendments:**

1. Fix `test_lex_failure_returns_source_unchanged` (F-1) — replace `bad = _env(...)` + `bad[1]` with direct `delimiters=` arg.
2. Fix `test_does_not_strip_crlf_terminators` (F-2) — change expected value from `"hello\r\n"` to `"hello\n"` (and rename test).
3. Reword `name = "web"` citation (F-3) — "Mirrors Swift's bare-assignment style; Kotlin uses annotated style and would also be valid."
4. Fix test count arithmetic (F-4) — "13 prior + 4 new = 17, plus 1 registry = 18".
5. Rename `test_register_language_tools_registers_three_tools` → `_seven_tools` and assert all 7 tool names (F-5).
6. Add fastblocks/splashstand to Spec Revision Notes #9 as deferred (F-16).

After these 6 amendments, the plan is ready for `subagent-driven-development` or `executing-plans` execution.

REVIEW_COMPLETE
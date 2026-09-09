# Testing Lens Review

**Plan:** `2026-09-07-crackerjack-multi-language-phase3.md`
**Spec:** `2026-09-07-crackerjack-multi-language-design.md` (Rev 2)
**Lens:** Test automation
**Verdict:** CONDITIONAL PASS — plan is broadly sound (correct TDD structure, ~50 tests across 8 tasks, real Gradle fixture, constructor injection) but has 4 high-severity gaps that should be addressed before Task 8 finalization, plus 5 medium and 4 low items.

---

## Findings (most-severe first)

### HIGH-1: Task 7 has only 2 MCP tests — missing the happy-path "with auth" test that Phase 2 caught as CRITICAL-1 fake-green

**Plan reference:** Task 7, lines ~994-1016.

The two new tests are:
1. `test_kotlin_list_hooks_returns_three_hook_names` — exercises `kotlin_list_hooks` end-to-end (good).
2. `test_kotlin_bump_version_requires_auth` — only verifies the auth-rejection branch (raises `PermissionError`).

**Risk:** Phase 2 final review's CRITICAL-1 was the fake-green `test_swift_bump_version_runs_with_auth`. It was caught because the lifecycle was patched instead of exercised. Phase 3 has the symmetric gap: `kotlin_bump_version` has only an auth-rejection test, no happy-path test. A regression where the tool fails silently after auth passes (e.g., wrong lifecycle construction, missing imports inside the tool body, exception in `asyncio.to_thread`) would not be caught.

**Recommendation:**
- Add `test_kotlin_bump_version_runs_with_auth` mirroring the Phase 2 Swift test:
  ```python
  async def test_kotlin_bump_version_runs_with_auth(tmp_path: Path) -> None:
      (tmp_path / "gradle.properties").write_text("version=1.2.3\n")
      (tmp_path / "build.gradle.kts").write_text("")
      (tmp_path / ".git").mkdir()  # minimal git context
      with mock.patch.dict(
          os.environ,
          {"MAHAVISHNU_PROJECT_ROOTS": str(tmp_path), "MAHAVISHNU_JWT_SECRET": "x" * 32},
          clear=False,
      ):
          _, tools = asyncio.run(_register())
          tool = tools["kotlin_bump_version"]
          result = asyncio.run(tool.fn(level="minor", project_root=str(tmp_path), dry_run=True))
      assert result["new_version"] == "1.3.0"
      assert result["commit_sha"] is None  # dry_run=True
      assert "dry_run" in result["skipped_steps"]
  ```
- This closes the symmetric gap to Phase 2 CRITICAL-1 and pins the contract that `kotlin_bump_version` actually constructs `KotlinLifecycle` + `make_git_backend` and runs end-to-end.

### HIGH-2: `mock.patch.object(shutil, "which", ...)` violates spec Testing F3's mandated `monkeypatch.setattr(shutil, "which", ...)` pattern

**Plan reference:** Task 3 (lines ~372, ~380, ~388, ~396, ~403, ~411, ~419); Task 4 (lines ~572, ~584); Task 5 (line ~780).

**Spec reference:** Testing F3 (line ~634):
> `monkeypatch.setattr(shutil, "which", ...)` is the mandated pattern.

The plan mixes:
- `mock.patch.object(shutil, "which", return_value="/usr/bin/gradlew")` (Tasks 3, 4)
- `monkeypatch.setattr(shutil, "which", ...)` (Task 2 — implicit, Task 5)

**Risk:**
1. Inconsistent test idiom: future maintainers can't tell which pattern is canonical by reading the plan.
2. `mock.patch.object` and `monkeypatch.setattr` differ in cleanup semantics — `mock.patch.object` exits immediately after the `with` block, while `monkeypatch` is undone at test teardown. If a test uses `mock.patch.object` outside a `with` block (e.g., as a decorator), the patch leaks into subsequent tests. The plan's Task 3 examples are inside `with` blocks, so they're safe — but the pattern is fragile.
3. Per Phase 2 review precedent (MEDIUM-1), Swift's `test_swift_format_hook_prefers_third_party_swift_format` was too loose because the assertion didn't bind to the specific mocked path. Phase 3 inherits this risk: Task 3's `mock.patch.object(shutil, "which", return_value="/usr/bin/gradlew")` returns the same value for any `which(cmd)` call, so the test passes even if the hook uses `which("kotlinc")` or `which("detekt")` instead of `which("gradlew")`. The spec-mandated `monkeypatch.setattr(shutil, "which", lambda cmd: ... if cmd == "X" else None)` is more discriminating.

**Recommendation:**
- Standardize on `monkeypatch.setattr(shutil, "which", lambda cmd: "/path/to/X" if cmd == "X" else None)` across all tasks. Rewrite Task 3 + Task 4 tests to match the spec example at line ~622-632.
- This is a small mechanical change but enforces the spec mandate.

### HIGH-3: Task 3 hooks have probe-vs-no-probe two-path semantics but no pytest-level test that exercises the "task absent" branch through `kotlin_hooks()` end-to-end

**Plan reference:** Task 3, lines ~370-427.

The plan tests `GradleTaskProbe.has_task()` directly for present/absent (lines ~402-426) but does NOT test:
1. What does `kotlin_hooks()` return when the project's `build.gradle.kts` declares NO ktlint plugin?
2. What does `kotlin_hooks()` return when `GradleTaskProbe.has_task("ktlintCheck")` returns `False`?
3. The `hook_with_probe` helper (lines ~473-477) is constructed without any probe integration — the comment says "If probe fails (task absent), the hook still emits; CLI invocation will skip-with-warning at execution time" — but no test pins this contract.

**Risk:** The probe-then-emit pattern is a behavioral contract from spec Kotlin F2:
> `kotlin.ktlint` → probe for `ktlintCheck` task (and `ktlintFormat` for autofix). If absent, skip-with-warning.

A regression where `kotlin_hooks()` always emits `cli_command=("./gradlew", "ktlintCheck")` regardless of whether ktlint is installed would pass all current tests. The probe integration is untested at the hook level.

**Note:** The hooks don't have a Python `fallback` callback, so Testing F3's hybrid-fallback two-path test plan (mandatory for hybrid hooks per the spec) does not directly apply. But the probe-then-emit is its own two-path contract that needs two tests:
- probe-true → hook emits with `cli_command=("./gradlew", "ktlintCheck")`
- probe-false → hook still emits (or skips — verify the contract)

**Recommendation:**
- Add two tests to `test_hooks.py`:
  ```python
  def test_kotlin_hooks_includes_ktlint_only_when_task_present(tmp_path, monkeypatch):
      """When GradleTaskProbe reports ktlintCheck absent, hooks still emit but cli_command marks skip."""
      (tmp_path / "build.gradle.kts").write_text("")
      # ... mock has_task to return False for ktlintCheck, True for others
      # Assert that the ktlint hook's cli_command encodes "skip" or has a marker.

  def test_kotlin_hooks_all_emitted_when_all_probes_true(tmp_path, monkeypatch):
      """When all probes return True, all 3 hooks are emitted with standard cli_command."""
  ```
- If the contract is "always emit, skip-with-warning at exec time", assert that. If the contract is "skip if probe fails", assert THAT. Either way, pin the behavior.

### HIGH-4: Task 8 fixture lacks any plugin declaration — the real-CLI smoke test cannot exercise task probing end-to-end

**Plan reference:** Task 8, lines ~1114-1148.

The fixture declares `kotlin("jvm")` plugin only. No `ktlint`, no `detekt`. The plan's Task 8 step 4 (line ~1180) smoke test only runs `adapter.detect()` + `adapter.capabilities()` — it does NOT invoke `./gradlew tasks --all` to verify probe behavior against a real Gradle CLI.

**Risk:**
1. **Fixture is decorative.** A real CI run against this fixture (per spec Phase 3 plan line ~700: "Test on `jinja2-custom-delimiters` (the named Phase 3 fixture)") would not exercise any of the 3 hooks (ktlint, detekt, test) because no plugin is declared.
2. **Spec Phase 3 fixture is `gradle-plugin/` (IntelliJ Platform plugin, `jinja2-custom-delimiters`), not `gradle-vanilla/`.** The plan deviates from the spec's named fixture. The `gradle-vanilla/` is fine for the adapter detect/capabilities test, but it should be either (a) named correctly, or (b) augmented with the plugins that match the hooks being tested.
3. **No `@pytest.mark.real_gradle_smoke` gated test.** Per Phase 2 review precedent (HIGH-2), the spec's intent is pytest-level fixtures, not just CLI smoke. A future contributor running pytest without Gradle installed will get 0 Kotlin probe coverage.

**Recommendation:**
- Add a ktlint plugin declaration to `gradle-vanilla/build.gradle.kts` (e.g., `id("org.jlleitschuh.gradle.ktlint") version "11.0.0"`) so the fixture exercises task probing end-to-end. This is a one-line addition.
- Add a `@pytest.mark.real_gradle_smoke` pytest-level test in `test_hooks.py`:
  ```python
  @pytest.mark.real_gradle_smoke
  def test_hooks_against_real_gradle_fixture(tmp_path):
      """Gate on `./gradlew` availability; runs against tests/fixtures/gradle-vanilla/."""
      fixture = Path(__file__).parent.parent.parent / "fixtures" / "gradle-vanilla"
      if not (fixture / "gradlew").exists():
          pytest.skip("gradlew not present")
      # ... invoke GradleTaskProbe(fixture) and assert has_task("ktlintCheck") == True
  ```
- Document the fixture split in plan's "Critical context" section, noting that spec Phase 3 actually lists `gradle-plugin/` as the named fixture (IntelliJ Platform plugin) — the plan should explain why `gradle-vanilla/` is chosen instead, and whether a `gradle-plugin/` fixture is deferred to a follow-up.

---

### MEDIUM-1: Task 5 lifecycle rollback test only covers `_push` failure — missing `_gh_release` failure rollback test (Phase 2 MEDIUM-3 carry-forward)

**Plan reference:** Task 5, lines ~778-786.

The single rollback test is:
```python
def test_kotlin_lifecycle_rollback_on_push_failure(tmp_path: Path) -> None:
    ...
    lifecycle._push.side_effect = RuntimeError("network down")
```

Phase 2's review explicitly called out the symmetric gap:
> Additionally, add a test for `_gh_release` failure (currently only `_push` failure is tested). The lifecycle should also rollback on `gh release create` failure.

Phase 3 has the same gap. If `_gh_release` fails AFTER `_push` succeeds, the rollback should still run (delete tag, reset commit) — and this path is untested.

**Recommendation:**
- Add:
  ```python
  def test_kotlin_lifecycle_rollback_on_gh_release_failure(tmp_path):
      ...
      lifecycle._gh_release.side_effect = RuntimeError("gh API error")
      with pytest.raises(RuntimeError, match="gh API error"):
          lifecycle.run(LifecycleOptions(level="minor", release=True))
      lifecycle._delete_tag.assert_called_once_with("v1.3.0")
      lifecycle._reset.assert_called_once()
  ```
- Pin the contract: regardless of which post-commit step fails (push OR gh_release), the rollback is identical.

### MEDIUM-2: Task 5 lifecycle test doesn't assert rollback order (Phase 2 MEDIUM-3 carry-forward)

**Plan reference:** Task 5, lines ~785-786.

The test asserts `lifecycle._delete_tag.assert_called_once_with("v1.3.0")` and `lifecycle._reset.assert_called_once()` but does not assert the order. Phase 2's review flagged this — the implementation deletes the tag BEFORE resetting the commit (correct), but the test doesn't pin this order.

**Risk:** A future maintainer who swaps the order (reset before delete_tag) would pass the test but introduce a regression where the tag briefly points at a soon-to-be-deleted commit.

**Recommendation:**
- Add an order assertion:
  ```python
  # delete_tag must be called BEFORE reset (tag must not point at a soon-to-be-deleted commit)
  delete_idx = next(i for i, call in enumerate(lifecycle.mock_calls) if call == mock.call._delete_tag("v1.3.0"))
  reset_idx = next(i for i, call in enumerate(lifecycle.mock_calls) if call.startswith("reset"))
  assert delete_idx < reset_idx
  ```
- Or, simpler, use `mock_calls` ordering with explicit index check.

### MEDIUM-3: Task 2 test 5 (`test_read_raises_version_not_found_when_nothing_matches`) hits a real subprocess for the gradlew fallback — slow and brittle

**Plan reference:** Task 2, lines ~223-227; implementation at lines ~281-291.

```python
def test_read_raises_version_not_found_when_nothing_matches(tmp_path: Path) -> None:
    src = GradlePropertiesVersionSource(tmp_path)
    with pytest.raises(VersionNotFoundError):
        src.read()
```

When neither `gradle.properties` nor `build.gradle.kts` exist, the implementation falls through to `_read_via_gradle()` which calls `subprocess.run(["./gradlew", "properties", ...])`. With no `./gradlew` in `tmp_path`, the subprocess returns non-zero exit code (or raises `FileNotFoundError` on Python 3.10+ for shell=False). The implementation catches `returncode != 0` and raises `VersionNotFoundError`.

**Risk:**
1. **Real subprocess invocation** — adds ~50-200ms per test run, plus dependency on shell behavior on the host (macOS `command not found` exit 127, Linux varies).
2. **Brittle to Python version** — Python 3.10+ changed `subprocess.run` to raise `FileNotFoundError` for missing executables in some cases. If the implementation doesn't catch this, the test may fail with `FileNotFoundError` instead of `VersionNotFoundError`.
3. **Doesn't test the gradle fallback path** — the test name suggests "VersionNotFoundError when nothing matches", but it actually tests the subprocess-error case (because no gradle.properties, no build.gradle.kts). The gradle-fallback happy path (subprocess succeeds, parses `version:`) is never tested.

**Recommendation:**
- Mock `subprocess.run` and test BOTH branches:
  ```python
  def test_read_falls_back_to_gradlew_properties(tmp_path, monkeypatch):
      (tmp_path / "settings.gradle.kts").write_text("")  # has gradlew context but no version files
      mock_result = mock.Mock(returncode=0, stdout="version: 1.2.3\n", stderr="")
      with mock.patch("subprocess.run", return_value=mock_result):
          assert GradlePropertiesVersionSource(tmp_path).read() == "1.2.3"

  def test_read_raises_when_gradlew_also_fails(tmp_path, monkeypatch):
      # No gradle.properties, no build.gradle.kts; gradlew returns non-zero.
      mock_result = mock.Mock(returncode=1, stdout="", stderr="gradlew: error")
      with mock.patch("subprocess.run", return_value=mock_result):
          with pytest.raises(VersionNotFoundError, match="gradlew properties failed"):
              GradlePropertiesVersionSource(tmp_path).read()
  ```
- This pins BOTH branches of the fallback and removes the real-subprocess dependency.

### MEDIUM-4: Task 7 MCP tool registration test depends on `_tool_manager._tools` private attribute (Phase 2 LOW-2 carry-forward)

**Plan reference:** Task 7, lines ~1001-1007.

The test pattern uses `tools["kotlin_list_hooks"]` via a `_register()` helper. Phase 2 LOW-2 flagged that the `_register()` helper accesses `_tool_manager._tools` (private attribute). Per the Phase 2 recommendation:
> Check `mcp-common` for a `get_registered_tools(mcp_app)` helper. If no helper exists, wrap the access in `try/except AttributeError`.

The plan doesn't mention this carry-forward. The same fragility applies.

**Recommendation:**
- Verify that `mcp-common` exposes a public testing helper (per spec Testing F2 verification). If yes, use it. If no, document the carry-forward risk and add the try/except wrapper.
- Note: Phase 2 already raised this concern — Phase 3 should explicitly acknowledge it inherited the risk.

### MEDIUM-5: Task 8 doesn't include coverage verification

**Plan reference:** Task 8, lines ~1175-1198.

The plan runs Phase 3 tests (`uv run pytest tests/adapters/kotlin/ tests/mcp/tools/test_language_tools.py tests/adapters/test_registry.py -v`) but does NOT run `pytest --cov` to verify the 89% coverage gate is maintained.

**Risk:** Per project CLAUDE.md, coverage gate is 89% via `pytest --cov-fail-under`. Phase 3 adds 5 new files (`version_source.py`, `hooks.py`, `lifecycle.py`, `git_backend.py`, `__init__.py`) plus modifies `language_tools.py`. If these don't reach 89% coverage (e.g., `git_backend.py` has uncovered `_gh_release` happy path), the gate fails late.

**Recommendation:**
- Add a step to Task 8: `uv run pytest tests/adapters/kotlin/ tests/mcp/tools/test_language_tools.py tests/adapters/test_registry.py --cov=crackerjack.adapters.kotlin --cov=crackerjack.mcp.tools.language_tools --cov-report=term-missing`
- If coverage drops, identify missing test cases and add them before Task 8 commits.

---

### LOW-1: Mixed `monkeypatch` and `mock.patch` idiom across the plan (also relates to HIGH-2)

Already covered in HIGH-2. Listed here for completeness as a low-severity style issue.

### LOW-2: `_gradle_helpers.py` is misnamed — it sets up git, not Gradle

**Plan reference:** Task 4, line ~509.

The helper file is `tests/adapters/kotlin/_gradle_helpers.py` but its content (per the plan and per the Phase 2 `_git_helpers.py` mirror) is `init_git_repo(tmp_path)`. It does NOT set up a Gradle project.

**Risk:** Future readers expect `_gradle_helpers.py` to contain Gradle-specific setup (e.g., write `build.gradle.kts`). They'll be confused when they find `git init` calls.

**Recommendation:**
- Rename to `tests/adapters/kotlin/_git_helpers.py` to match Phase 2's precedent exactly. The "Gradle" naming was a misnomer.

### LOW-3: Task 6 degenerate test — `test_detect_returns_false_when_neither_present` passes even if `detect()` is broken

**Plan reference:** Task 6, line ~900-901.

```python
def test_detect_returns_false_when_neither_present(tmp_path: Path) -> None:
    assert KotlinAdapter().detect(tmp_path) is False
```

`tmp_path` is empty (no files written). If `detect()` is implemented as `return True` (broken), this test FAILS correctly — but the test depends on `tmp_path` being empty, which pytest guarantees. The test is fine but its value is low (degenerate case).

**Risk:** Minimal — but adds noise. The test asserts that `detect()` returns `False` when no `build.gradle.kts`/`build.gradle` exist. This is the most common case (every non-Kotlin project) and is worth testing. Keep.

**Recommendation:**
- Add a comment explaining why this degenerate case matters (it's the "non-Kotlin project" case — the most common scenario).

### LOW-4: Task 7 missing `discover_tools` integration assertion

**Plan reference:** Task 7 (overall).

Phase 2 LOW-3 flagged the missing pytest-level test that `discover_adapters()` returns `{'python', 'swift'}`. Phase 3 has the same gap: no pytest-level test that `discover_adapters()` returns `{'python', 'kotlin', 'swift'}` after Task 6.

The plan only has a CLI smoke step (Task 6 step 5, line ~963-966) and Task 8 step 5. Both are `python -c "..."` invocations, not pytest tests.

**Recommendation:**
- Add to `tests/adapters/test_registry.py` or `tests/adapters/kotlin/test_kotlin_adapter.py`:
  ```python
  def test_discover_adapters_includes_kotlin():
      from crackerjack.adapters.registry import discover_adapters
      adapters = discover_adapters()
      assert "kotlin" in adapters
      assert isinstance(adapters["kotlin"], KotlinAdapter)
  ```
- This pins the entry-point contract.

---

## Spec Coverage Summary

| Spec Ref | Requirement | Plan coverage | Status |
|---|---|---|---|
| Testing F1 | (Not numbered in spec, but referenced) | N/A | — |
| Testing F2 | mcp-common testing helpers verification | Inherited from Phase 2 (LOW-2 carry-forward) | Gap noted in MEDIUM-4 |
| Testing F3 | Hybrid two-path test plan with `monkeypatch.setattr(shutil, "which", ...)` | Task 3 uses `mock.patch.object` instead | HIGH-2 |
| Testing F4 | PyCharm parity = Phase 4 deliverable | Out of scope for Phase 3 | OK |
| Testing F5 | FakeHookRunner abstraction | Not used in Phase 3 (no hook runners built — only CLI hooks via Gradle) | OK |
| Testing F6 | (Not numbered explicitly) | — | — |
| Testing F7 | Phase 1 budget and cache | Inherited; Phase 3 tests are unit-level (<5s each), no budget impact | OK |
| Testing F8 | Cross-language fixture split — `gradle-vanilla/` exists; `gradle-plugin/` (named in spec) is NOT created | HIGH-4 |
| Testing F9 | Jinja corpus + golden-master | Out of scope (Phase 4) | OK |

## Coverage Statement

### What's covered (50+ tests across 8 tasks)

| Component | Tests | Coverage |
|---|---|---|
| `GradlePropertiesVersionSource` | 5 | pluginVersion, projectVersion, version keys; build.gradle.kts fallback; raises on nothing matches |
| `GradleTaskProbe` + `kotlin_hooks` | 7 | 3 hook names; cli_command prefixes; probe-true/probe-false; daemon flag passes |
| `git_backend` (6 funcs + factory) | 9 | commit, tag ordering, push remote config, factory returns 6, reset preserves, gh_release errors, notes-file usage |
| `KotlinLifecycle` | 10 | bump major/minor/patch, bump from 0, invalid level, dry_run no-mutation, run bumps+tags, rollback on push failure, rejects invalid level (delegated), build.gradle.kts untouched |
| `KotlinAdapter` | 6 | subclass of base, name=kotlin, detect on .kts/.gradle, !detect when neither, capabilities includes 3 hooks |
| MCP tools | 2 | list_hooks returns 3 hook names; bump_version requires auth |

### What's NOT covered (gaps)

1. **Task 7 happy-path `kotlin_bump_version` with auth** — only auth-rejection tested (HIGH-1, mirrors Phase 2 CRITICAL-1)
2. **`mock.patch.object(shutil, "which", ...)` violates spec Testing F3** — pattern inconsistency across tasks (HIGH-2)
3. **Task 3 hook probe integration at hook level** — `has_task()` tested directly but `kotlin_hooks()` behavior when probe returns False is untested (HIGH-3)
4. **Task 8 Gradle fixture lacks ktlint plugin declaration** — real-CLI smoke doesn't exercise task probing (HIGH-4)
5. **`kotlin_bump_version` rollback on `_gh_release` failure** — only `_push` failure tested (MEDIUM-1, Phase 2 MEDIUM-3 carry-forward)
6. **Rollback order assertion** — no explicit order test (MEDIUM-2, Phase 2 MEDIUM-3 carry-forward)
7. **Task 2 gradle fallback subprocess mocked** — currently hits real subprocess (MEDIUM-3)
8. **`mcp-common` testing helper verification** — Phase 2 LOW-2 not carried forward explicitly (MEDIUM-4)
9. **Coverage verification in Task 8** — no `pytest --cov` step (MEDIUM-5)
10. **`_gradle_helpers.py` misnomer** — actually contains `init_git_repo`, not Gradle setup (LOW-2)
11. **`discover_adapters()` pytest-level integration test** — only CLI smoke, not pytest (LOW-4, Phase 2 LOW-3 carry-forward)
12. **`gradle.properties` write edge cases** — write verification (`if verified != new_version: raise VersionWriteError`) untested
13. **`write()` when no existing key** — the `content.rstrip("\n") + f"\nversion={new_version}\n"` append path is untested
14. **`build.gradle` (Groovy) variant** — Task 2 tests `build.gradle.kts` only; the implementation falls back from `.kts` to `.gradle` (line ~272), but the Groovy variant is untested
15. **`MAHAVISHNU_GIT_REMOTE` env var unset case** — Task 4 tests default-to-origin AND explicit-set; the third case (unset via `monkeypatch.delenv`) is also tested (line ~581). OK.
16. **`pytest.raises(ValueError, match="level must be")` from `LifecycleOptions.__post_init__`** — Task 5 line ~789-794. Test exists. OK.

### Pytest markers / gating

The plan does NOT define:
- `@pytest.mark.real_gradle_smoke` for the optional Gradle-CLI smoke (per Phase 2 review HIGH-2 precedent)
- Any marker for Kotlin-only tests that require Gradle toolchain
- Any marker for slow tests (Phase 3 tests appear fast — no real Gradle invocation in unit tests, mocked subprocess)

Per project CLAUDE.md, tests >10s should be `@pytest.mark.slow`. Phase 3 tests appear fast.

### Verifiability against external CLI

Per memory `multi-agent-review-catches-blind-spots.md`:
- Task 8 step 4 smoke assumes `KotlinAdapter().detect()` returns True for the fixture — this is verified by test_kotlin_adapter.py.
- Task 8 step 4 smoke assumes `KotlinAdapter().capabilities()` returns 3 hooks — this is verified by test_kotlin_adapter.py.
- The smoke does NOT verify that real `./gradlew` tasks probing works — that's the HIGH-4 gap.

### Suggested additional tests (priority order)

1. **(HIGH)** Add `test_kotlin_bump_version_runs_with_auth` to Task 7 (mirrors Phase 2 happy-path).
2. **(HIGH)** Standardize on `monkeypatch.setattr(shutil, "which", ...)` per spec Testing F3.
3. **(HIGH)** Add Task 3 probe-true/probe-false two-path tests through `kotlin_hooks()`.
4. **(HIGH)** Augment Task 8 fixture with `ktlint` plugin declaration OR add a real-CLI gated pytest test.
5. **(MEDIUM)** Add `_gh_release` failure rollback test.
6. **(MEDIUM)** Add rollback order assertion.
7. **(MEDIUM)** Mock `subprocess.run` in Task 2 test 5; add gradlew-fallback happy path test.
8. **(MEDIUM)** Verify `mcp-common` testing helper exists; use it in Task 7 (or document carry-forward).
9. **(MEDIUM)** Add `pytest --cov` step to Task 8.
10. **(LOW)** Rename `_gradle_helpers.py` to `_git_helpers.py`.
11. **(LOW)** Add `test_discover_adapters_includes_kotlin` pytest test.
12. **(LOW)** Add `VersionWriteError` test (Task 2 `write()` verification branch).
13. **(LOW)** Add `write()` append branch test (no existing key).
14. **(LOW)** Add `build.gradle` (Groovy) variant test for Task 2.

---

## Plan Quality Verdict

**CONDITIONAL PASS** — plan is fundamentally sound:

- Correct TDD discipline (failing test → run → implement → run → commit) in every task
- Constructor injection over monkey-patching (Phase 2 ruling carried forward)
- Real Gradle fixture committed under `tests/fixtures/gradle-vanilla/`
- 50+ tests across 8 tasks, reasonable distribution
- Cross-adapter `_bump` divergence documented (real-semver for Kotlin, pre-1.0 for Swift)
- Auth posture correctly applied to mutation tool (`kotlin_bump_version`)
- Path validation via `_validate_project_root` reused (Phase 2 ruling)

**HIGH-severity gaps are concentrated in:**
1. Task 7 missing happy-path (CRITICAL-1 pattern)
2. Spec mandate violation (`mock.patch.object` vs `monkeypatch.setattr`)
3. Task 3 probe integration untested at hook level
4. Task 8 fixture insufficient for real-CLI smoke

The MEDIUM gaps are mostly Phase 2 review items carried forward into Phase 3 without resolution. The LOW gaps are minor cleanups.

**Recommended action before Task 8 closes:** Address HIGH-1, HIGH-2, HIGH-3, and HIGH-4. The MEDIUM items can be filed as Phase 3 follow-ups if not blocking.

---

## Status

**REVIEW_COMPLETE** — review file written. Plan implementation can proceed with the recommended follow-ups tracked in a Phase 3 ledger entry.

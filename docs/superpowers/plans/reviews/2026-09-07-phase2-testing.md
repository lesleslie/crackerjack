# Testing Lens Review

**Plan:** `2026-09-07-crackerjack-multi-language-phase2.md`
**Spec:** `2026-09-07-crackerjack-multi-language-design.md` (Rev 2)
**Lens:** Test automation
**Verdict:** CONDITIONAL PASS — plan is broadly sound but has 7 gaps (2 high, 3 medium, 2 low) that should be addressed before Task 8 finalization. None are blockers if the implementer resolves them during Task 8.

---

## Findings (most-severe first)

### HIGH-1: No real SwiftPM fixture project; all tests use `tempfile.TemporaryDirectory()` + inline `Package.swift` strings

**Spec reference:** Testing F8 — "Cross-language fixture split":
> `tests/fixtures/swift-lib/` — vanilla SwiftPM library
> `tests/fixtures/swift-ios-app/` — iOS-only package (destination handling)
> `tests/fixtures/real-repo-weekly-smoke/` — actual `swiftui-ipc-client` … (run weekly, not every PR)

**Plan reality:** Every test in Tasks 2-6 constructs `Package.swift` via `_write_package_swift(tmp_path, body)` with hard-coded strings. No `tests/fixtures/swift-lib/`, no `tests/fixtures/swift-ios-app/`. The spec listed these as required Phase 2 deliverables.

**Risk:**
1. **Drift between test strings and real `Package.swift` semantics.** E.g., the regex `_PLATFORM_PATTERN = re.compile(r"\.([A-Za-z]+)\s*\(")` was verified against a 5-line fixture, not against real swiftui-ipc-client's `Package.swift`. Real files have comments, multi-line platform lists, versioned `.v16` suffixes that the regex may handle by accident.
2. **No test for visionOS / macCatalyst / multi-platform with 3+ platforms.** Only 3 platform cases tested (macOS-only, iOS-only, macOS+iOS). The spec lists visionOS support implicitly (Swift 5.9+ supports it).
3. **iOS detection edge case:** The plan tests "iOS-only" via `.iOS(.v16)` alone, but real iOS-only packages often have additional conditional platforms (`#if os(...)`) and `Package.swift` product/target structures.
4. **`_PLATFORM_PATTERN` has a name-clash risk:** it matches `.v13)` as a substring of `.macOS(.v13)` because `v13` starts with `v`. Actually no — the regex captures `[A-Za-z]+` and looks at the `\s*(` after. `.v13)` would not match because there's no `\s*(` immediately after `v13` — there's `)`. So this case is OK, but `.v13,` would match — i.e., the platform block regex would erroneously include `.v13` as a platform because `_PLATFORMS_BLOCK` captures everything inside `[...]`. Let me re-check:
   - `_PLATFORMS_BLOCK = re.compile(r"platforms\s*:\s*\[([^\]]*)\]", re.DOTALL)` — captures `[^\]]*` between `[` and `]`. This works only if there are no nested `[ ]` (which is fine for platforms).
   - `_PLATFORM_PATTERN = re.compile(r"\.([A-Za-z]+)\s*\(")` — applied to the block. For `.macOS(.v13), .iOS(.v16)`, captures `macOS` and `iOS`. But for `.macOS(.v13)` only, it captures `macOS` (because `\.macOS(` matches). However for `.macOS(.v13, .v14)` (range expression), it would also capture `macOS`. Edge case OK.
   - But for `#if os(macOS)` strings inside the platforms block (Swift 6.0 conditional), the regex would erroneously match `macOS` as a platform.

**Recommendation:**
- Add `tests/fixtures/swift-lib/` (vanilla macOS-only SwiftPM lib with real `Package.swift`, no `_write_package_swift` synthesis).
- Add `tests/fixtures/swift-ios-app/` (iOS-only, mirroring `swiftui-ipc-client`'s structure).
- Refactor `test_platforms.py` to use these fixtures in at least 1-2 cases (one fixture-driven, the rest inline for edge cases).
- Add a visionOS test case: `platforms: [.visionOS(.v1)]` → `requires_ios_destination=False` (visionOS does not need iOS-Simulator destination).
- Add a `#if os(...)` test case verifying that the parser either correctly ignores or fails explicitly (not silently).
- Add a `platforms: []` empty-list test to verify the default-to-macOS branch (current implementation falls through to `if not platforms: return macos`, which is correct — but untested).

### HIGH-2: Phase 1 lesson (testing F8 cross-language fixture split) is named but not applied

**Spec reference:** Testing F8 lists `tests/fixtures/swift-lib/` and `tests/fixtures/swift-ios-app/` as required fixtures for Phase 2.

**Plan reality:** Task 8.5 mentions "real SwiftPM lib smoke (gated)" against `/Users/les/Projects/swiftui-ipc-client`, but only as a manual smoke test gated on toolchain availability, not as a pytest fixture. The spec's intent was pytest-level fixtures, not just CLI smoke.

**Risk:** The plan satisfies the *letter* of Phase 1's fixture lesson (by saying "we'll smoke against the real repo") but misses the *spirit* (reusable, committed, version-controlled test fixtures that any future contributor can use without `swift toolchain` access). A future contributor running pytest without Swift installed will get 0 Swift test coverage.

**Recommendation:**
- Commit `tests/fixtures/swift-lib/` and `tests/fixtures/swift-ios-app/` as static files (no Swift toolchain needed to use them in parsing-only tests).
- For real-repo smoke (Task 8.5), use a dedicated `@pytest.mark.real_repo_smoke` marker (Phase 1 pattern) so it runs only on `pytest -m real_repo_smoke` (weekly/CI nightly), not on every PR. Per `memory: review-before-release-tag`, real-repo smoke should be gated separately from unit tests.
- Document the fixture split in the plan's "Critical context" section so implementers don't skip it.

### MEDIUM-1: `test_swift_format_hook_prefers_third_party_swift_format` is too loose

**Plan reference:** Task 4, line ~717.

The test asserts:
```python
assert format_hook.cli_command[-1] == "format"
assert format_hook.cli_command[0] in ("swift-format", "swift")
```

This passes regardless of which is installed, defeating the test's stated purpose: "If `swift-format` (third-party) is installed, the hook uses it."

**Risk:** The test gives no signal about whether the third-party preference logic actually works. A regression where `_swift_format_command()` always returns `("swift", "format")` would pass.

**Recommendation:**
- Test BOTH branches explicitly using `monkeypatch.setattr(shutil, "which", ...)`:
  ```python
  def test_swift_format_prefers_third_party_when_installed(monkeypatch):
      monkeypatch.setattr(shutil, "which", lambda cmd: "/usr/bin/swift-format" if cmd == "swift-format" else None)
      with tempfile.TemporaryDirectory() as td:
          root = _write_package_swift(Path(td), _PACKAGE_SWIFT_MACOS_ONLY)
          hooks = swift_hooks(root / "Package.swift")
          format_hook = next(h for h in hooks if h.name == "swift.format")
          assert format_hook.cli_command[0] == "swift-format"

  def test_swift_format_falls_back_to_built_in_when_third_party_missing(monkeypatch):
      monkeypatch.setattr(shutil, "which", lambda cmd: None)
      # ... assert cli_command[0] == "swift"
  ```
- This matches the spec's Hybrid two-path test plan (Testing F3): "This pair is **mandatory** for every hybrid hook."

### MEDIUM-2: `test_swift_format_hook_reads_swift_format_config` verifies by absence, not by presence

**Plan reference:** Task 4, line ~728.

The test creates a `.swift-format` file, then asserts `--configuration` is NOT in `cli_command`. This proves only that the code doesn't override the config — it doesn't prove the config is read.

**Risk:** If the implementation silently ignores `.swift-format` (e.g., calls `swift format` without any config awareness), the test still passes.

**Verification needed:**
- `swift format` (built-in) reads `.swift-format` automatically? **Verify against the actual `swift --help` output.** Per the spec (Swift F2): "the built-in reads `.swift-format` config automatically" — this is a claim that needs verification. Per memory `multi-agent-review-catches-blind-spots.md`, brief claims about external CLI behavior should be verified before being encoded as test contracts.
- If the verification confirms the behavior, the test is fine as a regression guard. If not, the test should be expanded or removed.

**Recommendation:**
- Add a verification step (similar to Task 4.3 "Verify Swift CLI assumptions"): `swift format --help | grep -i configuration` or test on actual config file. Document findings in the plan.
- If the claim is verified, add a comment in the test explaining the contract: "Per spec Swift F2: built-in `swift format` reads `.swift-format` automatically; this test guards against regressions where the hook adds an explicit `--configuration` flag that would override the config."

### MEDIUM-3: Lifecycle rollback test mocks `_delete_tag` and `_reset` but does not verify rollback order

**Plan reference:** Task 5, line ~980-997.

The test asserts both `mock_delete.assert_called_once_with("v1.1.0")` and `mock_reset.assert_called_once_with("abc123")`, but does not verify the order. The implementation deletes the tag BEFORE resetting the commit.

**Risk:** The order matters in some failure scenarios. Specifically:
1. If `_reset` fails, the tag is still there → orphan tag → next run would see a tag pointing to a commit that no longer exists in some configurations.
2. If `_delete_tag` fails, the reset still proceeds → cleaner state.

Actually, the current order (delete tag → reset commit) is correct because:
- Deleting the tag first means remote state doesn't show a tag pointing at a soon-to-be-deleted commit.
- Resetting the commit after removes local evidence.
- If either step fails, we've still made progress (best-effort rollback).

**However:** the spec doesn't pin the order. A future maintainer could reasonably swap the order, and the test would still pass. This isn't a bug, but it's a contract that should be explicit.

**Recommendation:**
- Add an order assertion using `mock_calls`:
  ```python
  assert lifecycle._delete_tag.call_args_list[0] < lifecycle._reset.call_args_list[0]  # tag first
  ```
  Or use `mock_calls` ordering with `assert mock_delete.call_args_list[0] == mock.call("v1.1.0")` BEFORE the reset mock.

- Additionally, add a test for `_gh_release` failure (currently only `_push` failure is tested). The lifecycle should also rollback on `gh release create` failure:
  ```python
  def test_swift_lifecycle_rollback_on_gh_release_failure():
      # When _push succeeds but _gh_release fails, rollback should run.
  ```

### LOW-1: `test_swift_adapter_skips_projects_without_package_swift` runs `git init` unnecessarily

**Plan reference:** Task 6, line ~1265.

```python
def test_swift_adapter_skips_projects_without_package_swift() -> None:
    with tempfile.TemporaryDirectory() as td:
        subprocess.run(["git", "init", "-q"], cwd=tmp_path_safe := Path(td), check=True)
        assert SwiftAdapter().detect(Path(td)) is False
```

The implementation: `def detect(self, project_root: Path) -> bool: return (project_root / "Package.swift").is_file()`

`detect()` only checks for `Package.swift` presence. `git init` is irrelevant to this test.

**Risk:** Minor — adds noise to test runtime and dependency on `git` being installed. If `git` is missing, the test fails for the wrong reason. Also, `tmp_path_safe :=` walrus assignment in a `subprocess.run(...)` arg is a Ruff readability issue.

**Recommendation:**
- Remove the `git init` call. Test should be:
  ```python
  def test_swift_adapter_skips_projects_without_package_swift() -> None:
      with tempfile.TemporaryDirectory() as td:
          assert SwiftAdapter().detect(Path(td)) is False
  ```
- Also: `is_file()` returns False for directories named `Package.swift` (rare but possible); consider using `.exists() and not .is_dir()` if the directory case matters.

### LOW-2: MCP tool tests access `_tool_manager._tools` (private attribute)

**Plan reference:** Task 7, line ~1414.

```python
registered = [t.name for t in mcp_app._tool_manager._tools.values()]
```

This reaches into FastMCP's private internals. FastMCP may break this in a minor version bump, causing Phase 2's MCP tests to fail for unrelated reasons.

**Risk:** Vendor lock-in to a specific FastMCP version. If `mcp-common` provides a public testing helper (per spec Testing F2), it should be used instead.

**Recommendation:**
- Check `mcp-common` for a `get_registered_tools(mcp_app)` helper. Per spec Testing F2, this verification was supposed to happen before Phase 2 implementation. If the helper exists, use it.
- If no helper exists, the access to `_tool_manager._tools` should at minimum be wrapped in a `try/except AttributeError` so future FastMCP API changes produce a clear error message instead of a confusing test failure.

### LOW-3: Missing `discover_adapters()` pytest-level integration test

**Plan reference:** Task 8.3 has a CLI smoke (`python -c "..."`), but Task 6 has no pytest-level test that `discover_adapters()` actually returns `{'python', 'swift'}`.

**Risk:** The entry-point discovery could silently drop Swift (e.g., wrong class name in pyproject.toml) and the only signal would be the manual smoke step.

**Recommendation:**
- Add to `tests/adapters/swift/test_swift_adapter.py` or a new `tests/adapters/test_registry.py`:
  ```python
  def test_discover_adapters_includes_swift():
      from crackerjack.adapters.registry import discover_adapters
      adapters = discover_adapters()
      assert "swift" in adapters
      assert isinstance(adapters["swift"], SwiftAdapter)
  ```
- This is the entry-point contract test that pins Task 1.4's commit message.

---

## Coverage Statement

### What's covered (29 unit tests + 5 MCP tests = 34 total)

| Component | Tests | Coverage |
|---|---|---|
| `parse_platforms` | 5 | macOS-only, iOS-only, multi-platform, missing file, no directive (defaults to macOS) |
| `GitTagVersionSource` | 5 | reads stripped tag, strips only leading v, raises on no match, raises on no tags, write raises |
| `swift_hooks` | 8 | non-empty, distinct names, iOS destination for iOS package, no destination for macOS, autofix=true for format, autofix=false for package.update, format prefers swift-format, format reads `.swift-format` |
| `SwiftLifecycle` | 7 | bump minor, bump major (pre-1.0), bump patch, dry-run no mutation, run minor bumps+tags+pushes, rollback on push failure, no Package.swift mutation |
| `SwiftAdapter` | 4 | isinstance LanguageAdapter, detects Package.swift, skips without, capabilities include lifecycle+hooks+version_source |
| `language_tools` MCP | 5 | registers 3 tools, bump requires auth, bump runs with auth, run_hooks no auth, detect_languages returns adapter names |

### What's NOT covered (gaps)

1. **Real SwiftPM fixtures** — only inline strings (HIGH-1, HIGH-2)
2. **visionOS / macCatalyst** — only macOS + iOS tested (HIGH-1)
3. **`platforms: []` empty list** — defaults to macOS but untested (HIGH-1)
4. **`#if os(...)` conditional platforms** — untested (HIGH-1)
5. **`swift-format` preference via `monkeypatch.setattr(shutil, "which", ...)`** — assertion is too loose (MEDIUM-1)
6. **Built-in `swift format` `.swift-format` config reading** — claim unverified against actual CLI (MEDIUM-2)
7. **`_gh_release` failure rollback** — only `_push` failure tested (MEDIUM-3)
8. **Rollback order** — no explicit order assertion (MEDIUM-3)
9. **`detect_languages` MCP tool returns adapter names when `Package.swift` present** — only tested with empty dir (LOW)
10. **`SwiftLifecycle` with `release=True`** — no test that verifies `release_url` propagates correctly through the rollback path (LOW)
11. **`discover_adapters()` pytest-level test** — only manual CLI smoke (LOW-3)
12. **Auth posture with only `MAHAVISHNU_AUTH_ENABLED=true` (no JWT secret)** — `_require_auth` should reject this combo (per spec: both required) (LOW)
13. **`swift_run_hooks` with `hook_names` filter** — `hook_names` parameter is in the implementation but not tested (LOW)

### Pytest markers / gating

The plan does NOT define:
- `@pytest.mark.real_repo_smoke` for Task 8.5 (per Phase 1 lesson, should be gated)
- Any marker for Swift-only tests that require Swift toolchain
- Any marker for slow tests (none currently slow — all tests are <5s — but worth declaring)

Per project CLAUDE.md "per-test timeout: 300s ceiling, not target", tests >10s should be `@pytest.mark.slow`. The Phase 2 tests appear fast (no real Swift invocation in unit tests), so this is likely OK as-is.

### Verifiability against external CLI

Per memory `multi-agent-review-catches-blind-spots.md` and Phase 1 lesson "implementers verified the brief against reality and corrected where the brief was wrong":

The plan correctly includes Task 4.3 (Verify Swift CLI assumptions). This is good. However:
- Task 7's MCP tests assume `_tool_manager._tools` is the correct way to introspect registered tools — verify this against the actual FastMCP version installed.
- Task 5's lifecycle tests assume `subprocess.run` is the right level to mock — verify against `crackerjack/services/git.py` (the plan says to grep for tag/reset methods but doesn't verify it).
- Task 3's `git describe --tags --abbrev=0 --match "v*"` is correct, but verify the flag combination against `git describe --help` (especially `--abbrev=0` which only works with `--tags`).

### Suggested additional tests (priority order)

1. **(HIGH)** Add `tests/fixtures/swift-lib/Package.swift` and `tests/fixtures/swift-ios-app/Package.swift` real fixtures; refactor 1-2 platforms tests to use them.
2. **(HIGH)** Add `@pytest.mark.real_repo_smoke` to Task 8.5 smoke.
3. **(HIGH)** Add visionOS + empty-platforms + `#if os(...)` test cases to `test_platforms.py`.
4. **(MEDIUM)** Split `test_swift_format_hook_prefers_third_party_swift_format` into two tests using `monkeypatch.setattr(shutil, "which", ...)`.
5. **(MEDIUM)** Add `_gh_release` rollback test.
6. **(MEDIUM)** Add rollback order assertion (delete_tag before reset).
7. **(LOW)** Remove `git init` from `test_swift_adapter_skips_projects_without_package_swift`.
8. **(LOW)** Add `test_discover_adapters_includes_swift`.
9. **(LOW)** Add `swift_run_hooks` with `hook_names` filter test.
10. **(LOW)** Add auth posture test for `MAHAVISHNU_AUTH_ENABLED=true` + missing JWT secret.

### Summary

The plan is fundamentally sound: it correctly applies Phase 1 lessons (Pattern B for lifecycle, 4-step MCP pipeline, auth posture, no Package.swift mutation), uses appropriate testing primitives (`tempfile.TemporaryDirectory`, `subprocess.run`, `mock.patch.object`, `pytest.raises`), and achieves a reasonable test count (34 tests).

The HIGH-severity gaps are around Phase 1's Testing F8 fixture split being named but not implemented. The MEDIUM-severity gaps are around loose assertions and missing rollback coverage. The LOW-severity gaps are minor cleanups.

**Recommended action before Task 8 closes:** Address HIGH-1, HIGH-2, MEDIUM-1, MEDIUM-3, and LOW-3. The rest can be filed as Phase 2 follow-ups.

---

## Status

**REVIEW_COMPLETE** — review file written. Plan implementation can proceed with the recommended follow-ups tracked in a Phase 2 ledger entry.
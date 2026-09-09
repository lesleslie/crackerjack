# Swift Lens Review

**Reviewer:** swift-expert
**Date:** 2026-09-08
**Subject:** `/Users/les/Projects/crackerjack/docs/superpowers/plans/2026-09-07-crackerjack-multi-language-phase2.md` (8 tasks, ~700 lines, ~10 commits)

## Findings (most-severe first)

### 1. **BLOCKER** — `swift test -destination` and `swift build -destination` are INVALID flags

**Line(s):** 39, 184, 186, 593, 597, 678, 686, 774–781, 812–820, 855–856, 1153–1156

**Summary:** The plan asserts that `swift test` and `swift build` accept `-destination 'generic/platform=iOS Simulator'`. Verified empirically:

```
$ swift test -destination 'generic/platform=iOS Simulator'
error: Unknown option '-d'
Usage: swift test <options> <subcommand>

$ swift build -destination 'generic/platform=iOS Simulator'
error: Unknown option '-destination'
Usage: swift build <options>
```

`-destination` is an **xcodebuild** flag, not a Swift Package Manager flag. `swift test --help` and `swift build --help` (verified on Swift 6.3.1) document only SwiftPM-native options (`--package-path`, `--sdk`, `--swift-sdk`, `--toolset`, etc.) — no `-destination`. The Swift F4 spec line 282 ("adds `-destination 'generic/platform=iOS Simulator'`") is also wrong; both spec and plan share this defect.

**Failure scenario:** On a real iOS-only Package.swift (e.g., `swiftui-ipc-client` if it were iOS-only), the hooks would invoke `swift test -destination 'generic/platform=iOS Simulator'` → subprocess fails with `error: Unknown option '-destination'` → hook reports failure → `crackerjack run` exits non-zero. Unit tests pass because they assert on the string in `cli_command`, not on actual subprocess invocation.

**Category:** CLI reality check (Phase 1 lesson re-applied).

**Recommendation:**
- Either:
  1. **Switch to `xcodebuild test`** for iOS destination handling: `xcodebuild test -scheme <SchemeName> -destination 'generic/platform=iOS Simulator'`. Requires extracting the scheme name from `Package.swift` (default = package name) and requires Xcode installed. Loses pure-SwiftPM portability.
  2. **Drop the `-destination` flag entirely** for `swift test`. For iOS-only packages, recommend users run `xcrun simctl` or `xcodebuild test` themselves. Add a SwiftPM hook `swift.test.xcodebuild` that uses xcodebuild when iOS is detected.
  3. **Use `--sdk iphonesimulator`** instead of `-destination`: `swift test --sdk iphonesimulator` is a SwiftPM-accepted flag (verified) and selects the iOS Simulator SDK. Caveat: tests still need a host target and an explicit destination; many iOS packages require `xcodebuild test` to actually run tests.

The Phase 1 brief-vs-reality rule applies here. Verify against `swift test --help` (the plan even tells implementers to do this in Step 4.3 at line 747 — but Step 4.3 runs *after* writing the implementation, which is too late).

### 2. **HIGH** — `_reset(commit_sha)` resets TO the bump commit instead of removing it

**Line(s):** 1148–1149 (interface), 1589–1593 (Task 7 implementation)

**Summary:** The plan's `_reset(commit_sha)` is documented as "resets TO the bump commit (preserves bump, drops tag)" per the review prompt. The implementation in Task 7 line 1589:

```python
def _reset(commit_sha: str) -> None:
    subprocess.run(
        ["git", "reset", "--hard", commit_sha],
        cwd=project_root, check=True,
    )
```

This resets HEAD to the bump commit (since `commit_sha` IS the bump commit captured immediately after `_commit`). Result: the bump commit remains in history; only the index is "cleared". This **does not undo the bump**.

Spec line 558 says the rollback is `git reset --hard HEAD~1` (parent of HEAD) — which actually removes the bump commit. The plan's `_reset(commit_sha)` should be `_reset_to_parent()` with `git reset --hard HEAD~1` (or `commit_sha~1`).

**Failure scenario:** Push fails → rollback runs → tag deleted, then `git reset --hard <bump-sha>` runs (HEAD stays on bump-sha, working tree cleared) → user thinks the bump was reverted, but the commit is still in history. Next `git describe --tags --match "v*"` returns the new tag (now deleted, but the commit is there), and a subsequent bump run would treat the current state as "post-bump" rather than "pre-bump".

**Category:** Correctness bug in rollback contract (spec MCP F2).

**Recommendation:** Change `_reset` semantics to reset to the pre-bump state. Either:
- Capture the pre-bump HEAD SHA in `run()` before `_commit` and pass it to `_reset`. `_reset(pre_bump_sha)` resets to before the bump.
- Or implement `_reset` as `git reset --hard HEAD~1` (parent). The "Pattern B split methods" chosen by the plan accommodates this.

### 3. **HIGH** — `_run_swift_lifecycle` monkeypatches instance methods, blocking services/git.py integration

**Line(s):** 1539–1608 (Task 7 `_run_swift_lifecycle`)

**Summary:** Task 7's implementation rewires the lifecycle's instance methods via attribute assignment:

```python
lifecycle._commit = _commit  # type: ignore[method-assign]
lifecycle._tag = _tag
...
```

This bypasses the constructor's clean dependency-injection opportunity. The plan's Task 5 implementer note (line 1155) says "Phase 2 should call into `crackerjack/services/git.py` for git operations" — but Task 7 hardcodes `subprocess.run(["git", ...])` calls instead. This duplicates the very rollback-prone logic that the spec (line 494) explicitly warns about: "The 2026-08-24 git incident pattern in `crackerjack/services/git.py:63-65, 639` is acknowledged; this design is the fix."

**Failure scenario:** A future bug fix to `services/git.py` (e.g., auth fallback for `git push`) does NOT propagate to `_run_swift_lifecycle` because it uses subprocess directly. Two parallel git implementations diverge.

**Category:** Architectural — duplicated subprocess integration seam.

**Recommendation:** Construct the lifecycle with an injected git service:

```python
class SwiftLifecycle(Lifecycle):
    def __init__(
        self,
        version_source: GitTagVersionSource,
        git_service: GitService | None = None,  # NEW: optional injection
        project_root: Path,
    ) -> None:
        self._version_source = version_source
        self._git = git_service or GitService(project_root)
        self._project_root = project_root
```

`GitService` already has `commit()`, `push()`, `push_with_tags()`, `reset_hard()`. Add `create_tag()`, `delete_tag()` methods to `GitService` in Task 5 (a small addition), and Task 7's `_run_swift_lifecycle` becomes:

```python
def _commit(message: str) -> str:
    self._git.commit(message)  # type: ignore[name-defined]
    return self._git.get_current_commit_hash() or ""
```

This eliminates the monkeypatch pattern, removes `# type: ignore[method-assign]`, and aligns with the spec's rollback contract.

### 4. **MEDIUM** — VisionOS / macCatalyst destination handling is missing

**Line(s):** 318–320, 354–356 (platforms regex and `requires_ios_destination` logic), 774–781 (`_ios_destination_args`)

**Summary:** The platforms parser correctly extracts `visionos` and `maccatalyst` (verified via regex test). However, `requires_ios_destination` is set to `"ios" in platforms` — only true for `ios`. VisionOS-only packages would build against macOS by default (wrong), and macCatalyst packages would build against macOS (wrong). Both need their own destination strategies:

- VisionOS-only: `-destination 'generic/platform=visionOS Simulator'`
- MacCatalyst-only: `-destination 'generic/platform=macOS,variant=Mac Catalyst'` (or use iOS simulator + `--triplet`)
- Multi-platform with iOS: `-destination 'generic/platform=iOS Simulator'` (current behavior)

**Failure scenario:** A visionOS-only Package.swift (`platforms: [.visionOS(.v1)]`) would produce a hook `("swift", "test")` with no destination flag. On a Mac with visionOS SDK installed, this builds against macOS host (likely a mismatch). On a Linux runner or a Mac without visionOS SDK, it fails entirely.

**Category:** Incomplete platform coverage.

**Recommendation:** Add `PlatformInfo.requires_destination: tuple[str, ...]` that enumerates all required destinations (could be multiple for multi-platform packages, or use a default + override). The hook picks one default destination per run:

```python
def _destination_arg(info: PlatformInfo) -> tuple[str, ...]:
    if "ios" in info.platforms:
        return ("-destination", "generic/platform=iOS Simulator")
    if "visionos" in info.platforms:
        return ("-destination", "generic/platform=visionOS Simulator")
    return ()
```

Note: this fix is moot if Finding #1 (the `-destination` flag itself is invalid for `swift test`) is resolved by switching to `xcodebuild test`. In that case, the hook chain would invoke `xcodebuild` with platform-specific destinations.

### 5. **MEDIUM** — `_run_swift_lifecycle` swallows `gh` failures and fabricates a URL

**Line(s):** 1595–1600

**Summary:** The `_gh_release` implementation in Task 7:

```python
def _gh_release(tag_name: str) -> str:
    result = subprocess.run(
        ["gh", "release", "create", tag_name, "--generate-notes"],
        cwd=project_root, capture_output=True, text=True,
    )
    return result.stdout.strip() if result.stdout else f"https://github.com/local/{project_root.name}/releases/tag/{tag_name}"
```

Two defects:
1. **No `check=True`**: If `gh release create` fails (auth missing, repo not found, network), `subprocess.run` returns non-zero, but the function returns the fabricated fallback URL. Caller thinks release succeeded.
2. **Fallback URL is fabricated**: `https://github.com/local/{project_root.name}/...` does not exist. The user is told a release exists at a URL that 404s.

`gh release create --generate-notes` is verified to exist (`gh release create --help` shows the flag). The output goes to stdout in JSON mode only; default mode prints the URL to stdout. But if stderr contains an error, stdout may be empty.

**Failure scenario:** `gh` not authenticated → subprocess exits non-zero → `_gh_release` returns `https://github.com/local/myrepo/releases/tag/v1.0.0` (fake URL) → `LifecycleResult.release_url` is the fake URL → MCP tool returns fake URL to caller → user thinks the release succeeded and shares the link.

**Category:** Silent error / fabricated output.

**Recommendation:** Use `check=True` and `subprocess.CompletedProcess` properly:

```python
def _gh_release(tag_name: str) -> str:
    result = subprocess.run(
        ["gh", "release", "create", tag_name, "--generate-notes"],
        cwd=project_root, capture_output=True, text=True, check=True,
    )
    url = result.stdout.strip()
    if not url:
        raise RuntimeError(f"gh release create returned no URL for {tag_name}")
    return url
```

This way, `gh` failure raises an exception → rollback fires (delete tag, reset commit) → caller sees a real error. Remove the fabricated fallback URL entirely.

### 6. **MEDIUM** — `_run_swift_lifecycle` is sync, called from async MCP tool handler, blocks event loop

**Line(s):** 1539–1543 (sync def), 1632–1642 (async tool handler)

**Summary:** Per spec MCP F7 ("All I/O is async") and crackerjack's project CLAUDE.md ("All I/O in the orchestration layer is async. No blocking calls ... inside async functions"), the MCP tool handler should not block on subprocess. The plan's `swift_bump_version` is `async def` (line 1632) but calls `_run_swift_lifecycle(...)` synchronously (line 1642). `_run_swift_lifecycle` runs `subprocess.run` calls (blocking) inside the async function.

**Failure scenario:** While `swift_bump_version` is running, the MCP event loop cannot process other tool calls. With `crackerjack`'s default 1800s timeout for `swift.test`, an iOS build holds the event loop for up to 30 minutes. Other clients requesting `swift_run_hooks` or `detect_languages` time out.

**Category:** Concurrency violation.

**Recommendation:** Wrap the call in `asyncio.to_thread`:

```python
@mcp_app.tool()
async def swift_bump_version(
    project_root: str,
    level: Literal["major", "minor", "patch"] = "minor",
    release: bool = False,
) -> dict[str, str | None]:
    """Bump Swift project version via git tags (no Package.swift mutation)."""
    _require_auth()
    return await asyncio.to_thread(
        _run_swift_lifecycle, Path(project_root), level, release,
    )
```

Or convert `_run_swift_lifecycle` to `async def` and use `asyncio.create_subprocess_exec` throughout. The spec MCP F7 example (line 522–524) uses `loop.run_in_executor` — `asyncio.to_thread` is the modern equivalent.

### 7. **MEDIUM** — `_delete_tag` order is wrong: should reset before deleting tag

**Line(s):** 1119–1120

**Summary:** Plan rollback order: `_delete_tag(tag_name)` then `_reset(commit_sha)`. Spec (line 510–512) gives the same order. But this order has a subtle issue: if `_reset` fails (e.g., due to a dirty working tree from a concurrent process), the local tag is already gone but the bump commit remains. The reverse order (reset first, then delete tag) is safer because tag deletion is a pure ref operation that doesn't depend on working tree state.

**Failure scenario:** User has uncommitted changes in their working tree (unrelated to the bump). Push fails → rollback runs. `_delete_tag` succeeds (refs/tags/v1.1.0 gone). `_reset` fails with "Your local changes would be overwritten" — but the function uses `git reset --hard` which would overwrite them anyway. If we fix Finding #2 to use `commit_sha~1` semantics, `_reset` may refuse to clobber dirty working tree.

**Category:** Rollback ordering (defensive correctness).

**Recommendation:** Reverse the order: reset first (cleaner history state), then delete the tag. If reset fails, the tag can still be deleted as a fallback. Document the order rationale in the docstring.

### 8. **MEDIUM** — Platforms regex misses edge cases

**Line(s):** 316–320

**Summary:** The `_PLATFORM_PATTERN` regex `\.([A-Za-z]+)\s*\(` was verified against these cases:

| Input | Result |
|---|---|
| `platforms: [.iOS(.v16)]` | `['ios']` |
| `platforms: [.macOS(.v13), .iOS(.v16)]` | `['macos', 'ios']` |
| `platforms: [.visionOS(.v1)]` | `['visionos']` |
| `platforms: [.macCatalyst(.v14)]` | `['maccatalyst']` |
| Multi-line indented | `['macos', 'ios']` |
| `platforms:  [  .iOS  (  .v16  )  ]` | `['ios']` |
| `platforms: [.iOS(.v16, .v17)]` | `['ios']` |
| `platforms: [.iOS, .v16]` (malformed) | `[]` (default macOS) |
| `platforms: nil` | No match (default macOS) |

Defects:
- **Malformed-but-parseable Swift**: `platforms: [.iOS, .v16]` is parseable by SwiftPM but the regex finds nothing → silently treated as macOS-only.
- **`.vN` constants**: The regex `\.([A-Za-z]+)\s*\(` would match `.v16` IF followed by `(`. `.v16)` (closing paren only) doesn't match, so `.v16` is correctly skipped.
- **Lowercase normalization**: `.iOS` → `ios` (lowercase). Correct for the comparison `"ios" in platforms`.
- **Platform block across lines with comments inside**: `// iOS only\nplatforms: [.iOS(.v16)]` → works (comments outside the block).
- **`#if os(macOS)` conditional blocks**: If `platforms:` is inside a conditional, the block regex still finds it. The plugin's Package.swift convention doesn't typically wrap `platforms:` in conditionals, so this is fine.

**Failure scenario:** A package with the malformed-but-valid `platforms: [.iOS, .v16]` would silently misclassify as macOS-only, missing the iOS destination (which is moot per Finding #1, but indicates the parser is fragile).

**Category:** Regex coverage gap.

**Recommendation:** Document the parser's assumptions (only SwiftPM-conformant `platforms:` directive is supported; malformed directives fall back to macOS-only). Add a "WARNING: malformed `platforms:` directive in Package.swift" log message when the block matches but `_PLATFORM_PATTERN` finds nothing, so implementers notice the fallback.

### 9. **MEDIUM** — `git describe` with multiple v* tags on a commit is order-dependent

**Line(s):** 526–543 (Task 3)

**Summary:** `git describe --tags --abbrev=0 --match "v*"` selects the most recent reachable tag. With multiple v* tags on the same commit (e.g., `v1.0.0` and `v1.0.0-rc1` both on commit C), `git describe` picks based on tag-creation order, not commit time (because both tags point to the same commit). Verified:

```
$ git tag v1.0.0       # lightweight
$ git tag v1.0.1       # lightweight
$ git tag v1.0.0-rc1   # lightweight (later)
$ git describe --tags --abbrev=0 --match "v*"
v1.0.0-rc1            # most recently CREATED tag wins
```

If `v1.0.0` is annotated (`git tag -a`) and `v1.0.0-rc1` is lightweight, `git describe --tags` prefers the annotated tag:

```
$ git tag -d v1.0.0
$ git tag -a v1.0.0 -m "..."
$ git describe --tags --abbrev=0 --match "v*"
v1.0.0                # annotated wins
```

**Failure scenario:** A repo has both `v1.0.0` (annotated, stable) and `v1.0.0-rc1` (lightweight, pre-release) on the same commit. `GitTagVersionSource.read()` returns `1.0.0` (correct) or `1.0.0-rc1` (incorrect), depending on tag creation order. The plan's tests use a single tag per commit and don't cover the multi-tag-on-commit case.

**Category:** Tag selection ambiguity.

**Recommendation:** Use `git describe --tags --abbrev=0 --match "v[0-9]*"` (exclude `v*-rc*` and `v*-alpha*` patterns) for stable reads, OR sort candidates and pick the most recent semver, OR document the ambiguity and accept that maintainers should delete obsolete pre-release tags.

### 10. **LOW** — Spec/plan divergence on case-sensitivity for `MAHAVISHNU_AUTH_ENABLED`

**Line(s):** 1528 (plan), spec line 487

**Summary:** Spec (line 487): `if not os.environ.get("MAHAVISHNU_AUTH_ENABLED") == "true":` (exact match, lowercase only). Plan (line 1528): `if os.environ.get("MAHAVISHNU_AUTH_ENABLED", "").lower() != "true":` (accepts `True`, `TRUE`, `tRuE`, etc.).

The plan is more permissive than the spec without justification. If the spec is the source of truth, the plan should match. If the plan is right, the spec should be amended. Verified canonical naming convention in `/Users/les/Projects/mahavishnu/tests/unit/test_websocket_auth.py` — tests use lowercase `"true"` and `"false"`.

**Category:** Spec consistency.

**Recommendation:** Pick one. Either tighten the plan to match spec (exact `"true"`), or amend the spec to allow case-insensitive (`.lower() == "true"`). The crackerjack-side `mcp-backend-wiring-discipline.md` decision should also be aligned. Document the choice.

### 11. **LOW** — `swift package update` vs `swift package upgrade`

**Line(s):** 593, 828–832

**Summary:** Plan only provides `swift.package.update` hook (per spec Swift F3). SwiftPM distinguishes:
- `swift package update`: refreshes `Package.resolved` to the latest commits within existing constraints (does NOT change version constraints in `Package.swift`).
- `swift package upgrade`: similar, but uses more relaxed constraints (does change version constraints).

Spec chose `update`. Plan matches spec. No defect, but the plan should document why `upgrade` was rejected (it modifies `Package.swift`'s dependency ranges, which is a mutation of project source beyond just `Package.resolved`).

**Category:** Spec rationale (informational).

**Recommendation:** Add a one-line rationale in the `_swift_package_update` docstring explaining the `update`-not-`upgrade` choice.

### 12. **LOW** — `_bump` pre-1.0 semantics are non-standard semver

**Line(s):** 1048–1069

**Summary:** Plan's `_bump`:
- `level == "major"` on `0.1.0` → `0.2.0` (increments minor, not major).
- `level == "minor"` on `0.1.0` → `0.2.0` (same as major).
- `level == "patch"` on `0.1.0` → `0.1.1`.

This conflates major and minor for pre-1.0 versions. Standard semver (per semver.org): `0.y.z` is for initial development; anything may change. Incrementing major for pre-1.0 typically signals breaking changes. The plan's choice means `crackerjack run -p major` and `crackerjack run -p minor` produce the same output for `0.x.y`. This is a known "crackerjack Python semantic" but the docstring (line 1049–1050) is opaque.

**Category:** API documentation clarity.

**Recommendation:** Expand the docstring with examples: "Pre-1.0 convention (matches crackerjack Python lifecycle): major and minor both increment the minor component; patch increments the patch. This avoids polluting 1.0+ with unintended major bumps during initial development."

### 13. **LOW** — `swift.build` timeout is excessive

**Line(s):** 816–820

**Summary:** Both `swift.test` and `swift.build` get `timeout_seconds=1800` (30 minutes). `swift.build` rarely needs more than 10 minutes (the heavy lifting is `swift test`'s test execution, not build). Plan should distinguish.

**Category:** Timeout tuning.

**Recommendation:** `swift.test: 1800` (iOS cold cache), `swift.build: 600` (matches `Hook` default). Document the rationale in the commit message.

### 14. **LOW** — Plan's `--abbrev=0` comment is misleading

**Line(s):** 567–576 (commit message), 526–530 (implementation)

**Summary:** `--abbrev=0` in `git describe` controls the abbreviation length of the commit SHA in the output (0 = full SHA, no abbreviation). It does NOT affect tag suffix stripping. Verified: tag `v1.0.0-rc1` is returned with the suffix intact. The plan's commit message says "Verified: rc tags (v1.2.3-rc1) strip the leading v but preserve the suffix" — this is correct behavior, but the plan should clarify that `--abbrev=0` does NOT strip suffixes; the plan's `tag[1:]` does.

**Category:** Documentation clarity.

**Recommendation:** Add a comment in the implementation: `# --abbrev=0 disables SHA abbreviation; the tag suffix (e.g., -rc1) is preserved by git describe. We strip only the leading 'v' below.`

### 15. **LOW** — `PermissionError` may not surface correctly through FastMCP

**Line(s):** 1523–1536, 1632–1642

**Summary:** Plan raises Python built-in `PermissionError`. FastMCP converts tool exceptions to JSON-RPC error responses. The error envelope and HTTP status code depend on FastMCP's error-handling contract. If FastMCP treats `PermissionError` as a generic exception and returns a 500, the MCP client sees an unhelpful error.

**Category:** Error contract.

**Recommendation:** Verify FastMCP's behavior with `PermissionError` via a quick test. If FastMCP doesn't map it to a meaningful error code, consider raising `McpError` (from `fastmcp`) or a custom exception that FastMCP recognizes. Add an integration test that asserts the error response structure.

---

## Coverage Statement

This review covered:

1. **Task 1** (Foundation / entry-point registration): verified Python entry-point format (`module:ClassName`) is canonical; no Swift-specific concerns.
2. **Task 2** (`parse_platforms`): verified the regex against 10 real Package.swift patterns; identified edge cases for visionOS / macCatalyst / malformed directives.
3. **Task 3** (`GitTagVersionSource`): verified `git describe --tags --abbrev=0 --match "v*"` against pre-release tags (`v1.0.0-rc1` preserved with suffix), multi-tag repos (creation-order dependent), annotated vs lightweight (annotated preferred), detached HEAD vs branch checkout. Confirmed the plan's `tag[1:]` correctly strips only the leading `v`.
4. **Task 4** (`swift_hooks`): **CRITICAL FINDING** — verified `swift test --help` and `swift build --help` on Swift 6.3.1 do NOT document `-destination`. Empirically confirmed `swift test -destination 'generic/platform=iOS Simulator'` fails with `error: Unknown option`. The plan's hooks will fail at runtime against real iOS packages.
5. **Task 5** (`SwiftLifecycle`): identified rollback semantics bug (Finding #2 — `_reset(commit_sha)` resets TO the bump commit, not AWAY from it). Verified `services/git.py` has `commit()`, `push()`, `push_with_tags()`, `reset_hard()` but lacks `tag()` / `delete_tag()` methods.
6. **Task 6** (`SwiftAdapter`): wiring is straightforward; no Swift-specific concerns beyond Findings #1 and #4.
7. **Task 7** (MCP `language_tools`): identified monkeypatch seam (Finding #3), fabricated URL fallback (Finding #5), blocking event loop (Finding #6), auth env-var case sensitivity divergence (Finding #10), `PermissionError` envelope concerns (Finding #15).
8. **Task 8** (Verification): `swift test --help` reality check is critical (covered in Finding #1). Real-swiftui-ipc-client smoke test is gated correctly.

**Not covered:**
- Python-side concerns (entry-point loading, MCP 4-step pipeline registration correctness) — left to other lenses.
- Auth/JWT verification of `MAHAVISHNU_JWT_SECRET` semantics — left to MCP lens.
- Test isolation between Swift and Python suites — left to testing lens.

**Headline blocker:** Finding #1 (`swift test -destination` is invalid). Both the spec (Swift F4, line 282) and the plan share this defect. Resolving it requires either switching to `xcodebuild test`, dropping the destination flag entirely, or using `--sdk iphonesimulator`. The Phase 1 lesson about "verify against reality before transcribing brief claims" applies directly here — Step 4.3 (line 747) tells implementers to verify, but it runs AFTER the implementation is written.

**Headline correctness bug:** Finding #2 (`_reset(commit_sha)` does not undo the bump). The plan's rollback contract per spec MCP F2 is "delete tag, reset commit via `git reset --hard HEAD~1`" — but the implementation resets TO the bump SHA, not AWAY from it.

# Simplification Lens Review

Phase 2 plan: `/Users/les/Projects/crackerjack/docs/superpowers/plans/2026-09-07-crackerjack-multi-language-phase2.md` (Tasks 1-8, 8 commits, ~1918 lines including code blocks).

Spec: `/Users/les/Projects/crackerjack/docs/superpowers/specs/2026-09-07-crackerjack-multi-language-design.md` (Rev 2).

Focus: implementation-level over-engineering and YAGNI within the user's stated scope (Swift lifecycle + hooks + MCP tools + auth posture). Scope choices themselves are not second-guessed.

## Findings (most-severe first)

### F1. `_run_swift_lifecycle` monkey-patches 6 instance methods after construction — the plan's worst code smell

**Task 7, Step 7.4.** The MCP helper constructs `SwiftLifecycle(...)`, then patches six stub methods (`_commit`, `_tag`, `_push`, `_delete_tag`, `_reset`, `_gh_release`) with closure-based subprocess implementations:

```python
lifecycle._commit = _commit  # type: ignore[method-assign]
lifecycle._tag = _tag  # type: ignore[method-assign]
lifecycle._push = _push  # type: ignore[method-assign]
lifecycle._delete_tag = _delete_tag  # type: ignore[method-assign]
lifecycle._reset = _reset  # type: ignore[method-assign]
lifecycle._gh_release = _gh_release  # type: ignore[method-assign]
```

Six `# type: ignore[method-assign]` lines that all exist because the design is fighting Python's type system. The implementation note even says "Phase 2: subprocess delegation happens here. Phase 3 may replace with `crackerjack.services.git.GitService` integration" — confirming this is a placeholder.

**Root cause:** Pattern B (stub instance methods as the test seam) was the right call for Phase 1 unit tests, but reusing it for the MCP-tool-to-real-git wiring inverts the seam: production code now has to monkey-patch the lifecycle to make it functional.

**Simplification:** constructor-inject a `git_service` callable/Protocol. Tests pass a fake. The MCP tool passes a real subprocess-backed implementation. Stub methods on the class disappear entirely:

```python
class SwiftLifecycle(Lifecycle):
    def __init__(
        self,
        version_source: GitTagVersionSource,
        project_root: Path,
        git_service: GitService,  # Protocol with commit/tag/push/delete_tag/reset/release
    ) -> None:
        self._version_source = version_source
        self._project_root = project_root
        self._git_service = git_service

    def run(self, options: LifecycleOptions) -> LifecycleResult:
        ...
        try:
            self._git_service.push(commit_sha, tag_name)
        except Exception:
            ...
            self._git_service.delete_tag(tag_name)
            self._git_service.reset(commit_sha)
            raise
        ...
```

This collapses 6 monkey-patches + 6 stub method declarations into one constructor parameter, removes 6 type-ignores, and eliminates `_run_swift_lifecycle` as a separate helper (it becomes a 5-line constructor call).

**Severity:** High. The plan author already flagged this as "Phase 3 may replace" — addressing it now avoids a Phase 3 refactor.

---

### F2. `swift_run_hooks` returns metadata but its name says it runs hooks

**Task 7, Step 7.4.** Tool docstring: "Run the configured Swift hooks against project_root." Tool body returns `{hook_name: {"cli_command": [...], "autofix": bool, "timeout_seconds": int}}` — i.e., metadata about hooks, not execution results.

Two interpretations, both worse than the current shape:
- If the tool is meant to **execute** hooks: the implementation is incomplete. It does no `subprocess.run`. It never invokes `swift test`/`swift build`/etc. The MCP tool is half-wired.
- If the tool is meant to **list** hooks: the name lies. `swift_run_hooks` should be `swift_list_hooks` (or `swift_get_hooks`), and the docstring should say "Return the configured Swift hooks and their metadata."

**Plus, the `hook_names: list[str] | None` parameter is filtered but never executed**, so the filter just narrows the metadata returned. If the tool were actually executing, the filter would make sense. As a metadata lister, the filter is YAGNI — list-all is simpler and the consumer can ignore what they don't want.

**Simplification:** rename to `swift_list_hooks`, drop the `hook_names` parameter, fix the docstring. If actual execution is desired, that's a separate tool (`swift_run_hook` taking a single hook name, returning execution output). Don't ship a half-tool.

**Severity:** High. Naming and behavior must align before MCP tools ship to consumers.

---

### F3. `_bump` reinvents semver parsing — `packaging.version` doesn't quite cover pre-1.0 semantics, but the current code is fine

**Task 5, Step 5.3.** `_bump("0.1.0", "major")` returns `"0.2.0"` — pre-1.0 crackerjack convention: "major" bumps the minor component. This is non-standard semver.

The user's brief explicitly suggests `packaging.version` could simplify this. It can't cleanly, because:
- `packaging.version.Version("0.1.0").major` is `0`, not the bumped value.
- `packaging` doesn't expose a "bump" operation; you'd still write the increment logic.

The current ~20-line implementation handles the pre-1.0 case correctly and is test-covered. **Verdict: keep as-is.** Not actually over-engineered — the alternatives are worse.

The brief's hint may have been a red herring. If the spec author intended standard semver, the test `test_bump_major` asserting `"0.1.0" → "0.2.0"` is what locks the behavior. Either accept the current code or amend the spec, but don't substitute `packaging.version` blindly.

**Severity:** None. Disposition: leave alone, note in commit message that the brief-vs-reality check confirmed the custom logic is necessary.

---

### F4. `PlatformInfo.platforms` tuple is exposed but unused downstream

**Task 2, Step 2.3.** `PlatformInfo` is a frozen dataclass with two fields:
- `platforms: tuple[str, ...]` — every detected platform, normalized lowercase
- `requires_ios_destination: bool` — derived from `"ios" in platforms`

Production consumer (Task 4 `_ios_destination_args`) reads only `requires_ios_destination`. The `platforms` tuple is consumed by tests for assertion but never by production code.

The tests assert `info.platforms == ("macos",)` etc., so the tuple is part of the test contract. But it's API surface area that pays no production dividend.

**Simplification options:**
1. Drop `platforms` from the dataclass; return `tuple[bool, tuple[str, ...]]` is uglier, so prefer just `requires_ios_destination: bool`.
2. Keep the tuple, drop the tests that assert on it (only assert `requires_ios_destination`).

Option 2 preserves debuggability (operators can inspect `info.platforms` if the dataclass is logged) without bloating the test surface. But the dataclass has only two fields and the tuple is one line — the savings are marginal.

**Severity:** Low. Not worth changing unless other findings force a touch.

---

### F5. `_init_git_repo` test helper duplicated across three test files

**Tasks 3, 5, 6.** Three test files all define a near-identical `_init_git_repo(tmp_path, tag=None)`:

- `tests/adapters/swift/test_version_source.py` (Step 3.1)
- `tests/adapters/swift/test_lifecycle.py` (Step 5.1)
- `tests/adapters/swift/test_swift_adapter.py` (Step 6.1, with extra body param)

**Simplification:** extract to `tests/adapters/swift/conftest.py` as a fixture (or shared helper module). The variations are minor — `tag` arg defaults to None, an optional `package_swift_body` override.

**Severity:** Medium-low. Three near-duplicates is a maintenance burden. The first Phase 3 adapter (Kotlin) would repeat the pattern again.

---

### F6. `import subprocess` is local inside `_run_swift_lifecycle`

**Task 7, Step 7.4.** The helper has `import subprocess` inside its body — local import — alongside the top-level imports. If the helper stays (see F1), the import should be top-level. If F1 is adopted, the import moves with the `git_service` and the question dissolves.

**Severity:** Trivial. Cosmetic.

---

### F7. Hook `timeout_seconds` literals duplicated and could be class-level constants

**Task 4, Step 4.4.** Hooks declare:
- `timeout_seconds=1800` (test, build)
- `timeout_seconds=300` (format, package.update)

The magic numbers 1800 (30min) and 300 (5min) appear twice each. Two options:
1. Hoist to module constants: `_SWIFT_LONG_TIMEOUT = 1800`, `_SWIFT_SHORT_TIMEOUT = 300`.
2. Use `Hook` defaults if available.

Phase 1 may already define these as `Hook` defaults; if so, drop the literal entirely.

**Severity:** Low. Cosmetic.

---

### F8. `swift_bump_version` `release: bool = False` is plausibly YAGNI for v1

**Task 7, Step 7.4.** The plan declares `release: bool = False` on `swift_bump_version` and surfaces a `release_url` in `LifecycleResult`. The spec table at line 1878 says "`gh release create` is necessary but not sufficient" — the wording is ambiguous (necessary for what?).

If `gh release create` is required for a complete v1 release flow, `release=False` default is wrong — most callers will silently skip it. If `gh release create` is optional/orthogonal (separate concern), `release` is YAGNI and belongs in a future `swift_create_release` tool.

**Simplification:** if `release` stays, default to `True` (since the spec says it's necessary). If `release` is YAGNI, drop the parameter from the tool (the lifecycle can still call `_gh_release` for callers that opt in via a future flag).

The plan's test `test_swift_lifecycle_run_minor_bumps_tags_pushes` uses `release=True` — implying the plan author considers it the canonical path. If so, default to True.

**Severity:** Medium. Either commit to "release=True is the default flow" or drop the parameter.

---

### F9. `detect_languages` returns `{name: bool}` but the name implies detection of which languages

**Task 7, Step 7.4.** Tool returns `dict[str, bool]` — `{python: True, swift: False}`. Test asserts `"python" in result` and `"swift" in result`. Behavior is fine; the name "detect_languages" could read either as "what languages are detected" or "do detection." Both interpretations work for the current output.

**Severity:** None. Cosmetic; not worth changing.

---

### F10. CHANGELOG entry is useful, not duplicative of git history

**Step 8.6.** A CHANGELOG bullet summarizing Phase 2 is conventional and serves discoverability for users who don't read commit history. Not a YAGNI issue.

The bullet could be tightened (the current draft is verbose — three sentences for one bullet), but that's editorial, not structural.

**Severity:** None.

---

### F11. The MCP tool descriptions are repetitive but only 3 tools — YAGNI to abstract

**Task 7, Step 7.4.** Three `@mcp_app.tool()` decorated functions follow the same shape (parse args, call helper, return dict). A `register_lifecycle_tool(adapter, level_field, ...)` helper could generate them, but for 3 tools the abstraction costs more than it saves.

If/when Phase 3+ adds 2-3 more adapters × 2-3 tools each, a `register_lifecycle_tool` helper becomes worthwhile. For Phase 2, leave it inline.

**Severity:** None for Phase 2. Note as a candidate for Phase 5 consolidation.

---

### F12. `_run_swift_lifecycle` redundant local `import subprocess` after top-level import

**Task 7, Step 7.4.** Lines 1508-1509 already have `import logging` and `import os` at top level. The body has `import subprocess` as a local import. Either move to top-level (cosmetic) or rely on closure scope. If F1 is adopted, this dissolves.

**Severity:** Trivial. Subsumed by F1.

---

## Coverage Statement

I reviewed the full Phase 2 plan (~1918 lines / 8 tasks / 8 commits) against the six focus areas:

1. **Over-engineering** — covered. The most significant instance is F1 (Pattern B seam reused for production wiring via monkey-patching). `_bump` is not over-engineered (F3); `PlatformInfo` is mildly over-engineered (F4).
2. **YAGNI** — covered. `swift_run_hooks` `hook_names` param (F2), `release: bool = False` default (F8), and MCP tool registration helper (F11) are the candidates; only F2 and F8 warrant action.
3. **Specific simplifications** — covered. Test helper extraction (F5), timeout constants (F7), local import (F6/F12).
4. **Hidden complexity** — covered. The 6-method Pattern B seam is the central example (F1); the three repeated test helpers are a smaller instance (F5).
5. **YAGNI vs. Spec Pressure** — covered. F8 surfaces an ambiguous spec phrase ("necessary but not sufficient") that the plan doesn't resolve.
6. **Phase 1/2 duplication** — covered. F5 (test helpers), F1 (Pattern B seam inherited from Phase 1). A shared template would help future phases but isn't worth retrofitting into Phase 2.

**Top 3 actions for the plan author:**

1. **F1**: Replace the monkey-patch seam with constructor-injected `git_service`. Eliminates 6 type-ignores, one local helper, and one Phase 3 refactor.
2. **F2**: Decide what `swift_run_hooks` actually does. Rename to `swift_list_hooks` and drop `hook_names`, OR actually execute hooks. The current half-tool will confuse MCP consumers.
3. **F8**: Either default `release=True` (per the test's usage pattern) or drop the parameter entirely. Spec ambiguity should be resolved before shipping.

REVIEW_COMPLETE
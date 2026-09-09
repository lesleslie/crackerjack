# Simplification Lens Review — Phase 3 (Kotlin/Gradle)

**Phase 3 plan:** `/Users/les/Projects/crackerjack/docs/superpowers/plans/2026-09-07-crackerjack-multi-language-phase3.md` (Tasks 1-8, 8 commits, ~1200 lines).
**Spec:** `/Users/les/Projects/crackerjack/docs/superpowers/specs/2026-09-07-crackerjack-multi-language-design.md` (Rev 2).
**Precedent:** `/Users/les/Projects/crackerjack/docs/superpowers/plans/reviews/2026-09-07-phase2-simplification.md`.

**Focus:** implementation-level over-engineering, YAGNI within the user's stated scope (Kotlin lifecycle + hooks + MCP tools). Scope choices themselves are not second-guessed.

---

## Findings (most-severe first)

### F1. `kotlin_hooks` constructs `GradleTaskProbe` but never calls it — the entire probe is dead code at runtime

**Task 3, Step 3.** The factory builds:

```python
def _build_hooks(project_root: Path) -> tuple[Hook, ...]:
    probe = GradleTaskProbe(project_root)
    gradlew = ("./gradlew",)

    def hook_with_probe(name: str, *cli_command: str) -> Hook:
        return Hook(name=name, cli_command=(*gradlew, *cli_command))

    hooks: list[Hook] = [
        hook_with_probe("kotlin.ktlint", "ktlintCheck"),
        hook_with_probe("kotlin.detekt", "detekt"),
        Hook(name="kotlin.test", cli_command=(*gradlew, "test")),
    ]
    return tuple(hooks)
```

`probe` is constructed and never referenced again. The inline comment says "If probe fails (task absent), the hook still emits; CLI invocation will skip-with-warning at execution time." But **no hook execution path in Phase 3 calls `probe.has_task()`** — the actual probing is deferred to runtime (somewhere unspecified outside this plan).

This is the same anti-pattern as Phase 2 F2 (`swift_run_hooks` returned metadata but the name said "run"): the API surface (`GradleTaskProbe`) suggests a probe-then-invoke pattern, but the runtime execution lives in code that isn't part of Phase 3. The hook runner (which lives in the Phase 1 hooks pipeline, not Phase 3) is where `probe.has_task()` should be called — but the plan never references the hook runner at all, leaving the probe orphaned.

**Simplification options:**

1. **Inline the probe into the hook tuple.** `Hook` dataclass currently doesn't have a `task_probe` field. Add one (`task_probe: Callable[[], bool] | None = None`). The hooks module produces hooks whose `task_probe` is bound to the Gradle task probe; the runner calls it. One change, no orphaned class.

2. **Drop `GradleTaskProbe` from this plan entirely.** Defer probing to the runtime hook runner. The 3 `test_gradle_task_probe_*` tests become Phase 1 hook-runner tests. The hooks module stays as a thin list of argv tuples.

3. **Keep the class but actually call it.** Either remove the `if absent, the hook still emits` fallback (skip-with-warning happens at the probe site, not at the runner), OR drop the comment. The current state — class exists, never invoked, comment admits it — is the worst of all worlds.

**Severity:** High. Either probe or don't. The plan ships a class with three tests but no caller — that is the textbook YAGNI violation. The class isn't even referenced in the MCP tool, the lifecycle, or the adapter; only by its own tests.

---

### F2. `gradle_properties_version_source()` factory is exported but never imported — dead public API

**Task 2, Step 3 (version_source.py).** The plan defines and exports a factory:

```python
def gradle_properties_version_source(project_root: Path) -> VersionSource:
    """Factory matching the Phase 1 VersionSource Protocol shape.

    Returns the underlying object typed as VersionSource; concrete class is
    `GradlePropertiesVersionSource`. Use this factory for parity with
    `git_tag_version_source()` (Phase 2).
    """
    return GradlePropertiesVersionSource(project_root)
```

`__all__` does not include it, but the docstring explicitly says "Use this factory for parity with `git_tag_version_source()` (Phase 2)". Phase 2's `git_tag_version_source()` is referenced in `version_source.py` for parity, but Phase 2's actual usage in `SwiftAdapter.capabilities()` is `GitTagVersionSource(project_root)` directly — not via the factory. Phase 3's `KotlinAdapter.capabilities()` also instantiates directly:

```python
version_source = GradlePropertiesVersionSource(project_root)
```

The factory is dead code at the import boundary. Phase 2 review's F4 (`PlatformInfo.platforms`) noted similar dead surface area and decided to leave it alone for debuggability — but Phase 3's factory isn't even reachable as a debug helper because no test imports it.

**Simplification:** delete the factory and its docstring. If Phase 2's analogous factory is similarly dead, that's a Phase 2.5 cleanup, not Phase 3's job.

**Severity:** Medium. Public-looking API with no caller creates confusion later.

---

### F3. `make_git_backend` import in `KotlinAdapter.capabilities()` exists only to silence a lint warning

**Task 6, Step 3.** The adapter code:

```python
def capabilities(self, project_root: Path) -> Capabilities:
    from crackerjack.adapters.kotlin.git_backend import make_git_backend

    version_source = GradlePropertiesVersionSource(project_root)
    # Per Phase 2 final-review CF-2: do not construct KotlinLifecycle here;
    # it's rebuilt inside the MCP handler. Keep capabilities() minimal.
    _ = make_git_backend  # silence unused-import lint (factory used by MCP layer)
    return Capabilities(
        version_source=version_source,
        hooks=kotlin_hooks(project_root),
        has_lifecycle=True,
    )
```

The comment says "factory used by MCP layer (Task 7)". But Task 7 imports `make_git_backend` directly from `crackerjack.adapters.kotlin.git_backend`, **not** from `KotlinAdapter`. The import in `capabilities()` is therefore unreferenced and dead.

The `_ = make_git_backend` is a code smell — it admits the import is unused and asks the lint to look the other way. This is exactly the anti-pattern Phase 2's CF-1 fix was meant to root out (dead defensive code that exists "just in case").

**Simplification:** delete the import and the comment. `capabilities()` becomes two lines of real work. The Task 7 MCP tool already imports what it needs.

**Severity:** Medium. Cargo-culted from a fix that doesn't apply; reads as defensive code with a post-hoc justification.

---

### F4. `_bump` divergence policy documents Phase 2.5 work as Phase 3 work

**Task 5, Step 3 + Spec Revision Notes.** The plan's cross-adapter `_bump` divergence section (lines 1209-1220) is a 12-line essay on a follow-up ticket that isn't part of Phase 3. The actual `_bump` implementation is 8 lines; the docstring is 6 lines; the cross-adapter prose is the bulk of the change.

The plan even hedges: "Phase 3 picks (b) implicitly (Kotlin uses real semver, Swift stays pre-1.0). ADR recommended before Phase 4 (JS/TS adapter) lands."

Two issues:

1. The cross-adapter prose belongs in a Phase 2.5 ticket, not Phase 3's plan. Phase 3's job is to document Kotlin's `_bump` semantics in its own docstring (which it does, correctly). The cross-cutting ADR is a separate work item.
2. The plan claims "Phase 3 also adds a cross-reference comment to `SwiftLifecycle._bump` (already documented as pre-1.0)" — but no such edit appears in Task 5's Step 3. This is a phantom step.

**Simplification:** remove the "Cross-adapter `_bump` divergence" section from this plan. Move the CF-3 follow-up to a Phase 2.5 issue. Keep the in-code docstring on `KotlinLifecycle._bump` (which is the actual documentation deliverable).

**Severity:** Medium-low. Plan bloat; creates phantom work; obscures the actual code change.

---

### F5. `test_kotlin_lifecycle_rejects_invalid_level` tests Phase 1 code, not KotlinLifecycle

**Task 5, Step 1 (test file).** The test:

```python
def test_kotlin_lifecycle_rejects_invalid_level(tmp_path: Path) -> None:
    # Per Phase 2 M-3 fix: LifecycleOptions.__post_init__ raises; SwiftLifecycle
    # no longer re-validates. Same applies here — KotlinLifecycle does NOT
    # re-validate either.
    with pytest.raises(ValueError, match="level must be"):
        LifecycleOptions(level="epic")
```

This asserts that `LifecycleOptions(level="epic")` raises — which is Phase 1 `LifecycleOptions.__post_init__` validation, not anything specific to `KotlinLifecycle`. The test name implies Kotlin-specific behavior; the comment explicitly states "KotlinLifecycle does NOT re-validate" (i.e., the test doesn't exercise KotlinLifecycle at all).

The test passes whether or not KotlinLifecycle exists. It would pass if you deleted the entire KotlinLifecycle class. That's the Phase 2 final-review fake-green-test pattern: trivially-passing tests that give a green checkmark without exercising the unit under test.

**Simplification:** delete this test. Phase 1 already has equivalent coverage (or should). If KotlinLifecycle doesn't re-validate, that's verified by the absence of a `__post_init__` body — no test needed. If Phase 1 is missing the equivalent test, file it against Phase 1, not Phase 3.

**Severity:** Medium. Fake-green test pattern; contributes to test count without adding coverage.

---

### F6. `git_backend.py` is byte-for-byte duplicated from Swift — copy-paste with two header lines changed

**Task 4.** The plan acknowledges this explicitly: "The implementations are IDENTICAL to Phase 2's `crackerjack/adapters/swift/git_backend.py`... Copy verbatim, with two header changes: Module docstring and Logger name."

This is the textbook "Rule of Three" violation. Two copies = OK (one is the original, one is coincidence). Three copies = extract. Phase 3 makes it two identical copies.

The plan's note ("Refactor to share later if duplication proves costly") is the correct hedge for v1. But the duplicated file is 130+ lines (the Phase 2 file is `lines 27-158` per the plan). For each Phase 3 fix to the git backend, two files must change in lockstep — and the Plan itself already references a fix that will be needed (the `--no-daemon` flag for Gradle is mentioned; if the Swift backend ever needs similar hygiene, drift begins).

**Simplification options (in order of preference):**

1. **Now:** extract `git_backend.py` to `crackerjack/adapters/_git_backend.py` and have both Swift and Kotlin import the same functions. Add per-language wrappers only where genuinely needed (e.g., auth env var, remote default). Saves 130 lines of duplicate code AND makes Phase 2's fix in commit `b2199190` apply to Kotlin automatically.
2. **Now:** at minimum, make the duplication explicit in code with `# MIRROR of swift/git_backend.py — keep in sync` at the top of the Kotlin file. The plan currently buries this in a parenthetical: "(For brevity, the full source is reproduced in the plan's appendix; the implementer should diff-verify against the Phase 2 file before copying.)" — this is a copy instruction, not an in-code annotation.
3. **Later:** file a Phase 3.5 ticket to extract. This is the worst option because the Phase 3 plan is currently a participant in the duplication, not just an inheritor.

**Severity:** Medium. Today's duplication becomes tomorrow's drift. The "Phase 2 already does this; copy it" framing understates the maintenance cost.

---

### F7. `_bump` extraction to `_semver.py` is documented as Phase 2.5 follow-up — but `test_bump_*` already documents the semantics

**Task 5, Step 1 + Plan § Cross-adapter `_bump` divergence.** Five tests document `_bump` semantics:

- `test_bump_major_real_semver` — 1.2.3 → 2.0.0
- `test_bump_minor_real_semver` — 1.2.3 → 1.3.0
- `test_bump_patch` — 1.2.3 → 1.2.4
- `test_bump_major_from_zero` — 0.1.0 → 1.0.0
- `test_bump_rejects_invalid_level` — phase 1 validation

Phase 2 ships its own `_bump` tests with pre-1.0 semantics. Phase 3 ships 4 of these tests with real-semver semantics. After Phase 3 lands, the codebase has 9 `_bump` tests across two adapter packages, plus the Python adapter.

This is fine for v1 (the tests live next to the code that implements them). But the plan's "Spec Revision Notes" / "Cross-adapter `_bump` divergence" section proposes extracting to `_semver.py` as Phase 2.5 work, with no test consolidation note. When that ticket lands, all 9 tests need to move — and the per-adapter tests become redundant.

**Simplification:** if Phase 2.5 extraction is on the roadmap, file it now with a test-migration plan. Don't ship Phase 3's `_bump` tests as if they're permanent; tag them with `@pytest.mark.phase_2_5_migration_target` so the consolidation is cheap.

**Severity:** Low. Test debt is acceptable when consolidation is planned; missing the consolidation note is what makes it problematic.

---

### F8. Hybrid fallback interpretation: Phase 3 hooks all have `cli_required=True`, no `fallback` callbacks — YAGNI-correct, but unverified

**Task 3 (hooks) + Spec Writing F2.** Per spec: "When a hook has `fallback` set AND the CLI is missing (`shutil.which(cmd) is None`), invoke `fallback()`. When fallback also raises or returns False, fail the hook."

Phase 3's three hooks (`kotlin.ktlint`, `kotlin.detekt`, `kotlin.test`) all use `./gradlew` as the command. None define a `fallback`. The Kotlin Gradle ecosystem doesn't have a meaningful Python fallback for `./gradlew ktlintCheck` — there's no portable pure-Python ktlint.

The plan correctly does NOT add `fallback` callbacks. This is YAGNI-correct.

**But:** the plan doesn't add the mandated hybrid two-path test pair from spec § Testing Strategy § Hybrid two-path test plan (per Testing F3). Phase 2 added these for Swift hooks (CLI-present + CLI-missing pair, per Phase 2 plan § Testing Strategy). Phase 3's `test_hooks.py` only verifies the CLI-present shape (via `mock.patch.object(shutil, "which", return_value="/usr/bin/gradlew")`) — it does not verify the CLI-missing shape, because there is no Python fallback to invoke.

**Is this YAGNI or under-implementation?** Per spec: "This pair is **mandatory** for every hybrid hook." If a hook has no `fallback`, is it still "hybrid"? The spec's hybrid policy could be interpreted as: "If `fallback` is None, the hook is non-hybrid and only the CLI-present test applies."

The plan should explicitly call this out: "Phase 3 hooks are non-hybrid (no Python fallback). Hybrid two-path test pair is N/A per spec. The CLI-present test pair verifies shape; runtime CLI-missing behavior is 'fail with installation instructions' (per spec Error Handling table)."

**Severity:** Low. Spec interpretation is reasonable; missing the explicit call-out risks Phase 4 reviewer asking the same question.

---

### F9. `Hook` for `kotlin.ktlint` ignores `autofix=True` opportunity

**Task 3, Step 3.** The `Hook` dataclass defaults `autofix=False`. Kotlin's `ktlintCheck` is paired with `ktlintFormat` (autofix). The plan hard-codes `ktlintCheck` for the hook and never wires up `ktlintFormat`.

If `crackerjack run --autofix` is a future capability, Kotlin autofix won't fire. Phase 2's Swift adapter also doesn't use autofix for `swift format`, so this is consistent — but the Kotlin case is different because ktlint explicitly provides a separate format task that maps to the autofix contract.

**Simplification:** this is intentional scope limitation, not over-engineering. Skip. (Note: if Phase 4 adds autofix detection, kotlin.ktlint will need a `format_task_name="ktlintFormat"` field on `Hook`. The Phase 1 `Hook` design has no such field.)

**Severity:** None. Note for Phase 4.

---

### F10. `make_git_backend` returns a `tuple[Callable, ...]` of 6 unnamed functions — positional destructuring is fragile

**Task 4.** `KotlinLifecycle.__init__` takes 6 keyword-only Callable parameters; the MCP tool destructures with:

```python
commit, tag, push, delete_tag, reset, gh_release = make_git_backend(root)
```

Order is implicit. A future re-order in `git_backend.py` silently swaps parameter meanings. Phase 2's SwiftLifecycle has the same shape; Phase 3 inherits the fragility.

**Simplification:** return a `GitBackend` frozen dataclass with 6 named fields. Destructuring becomes `backend = make_git_backend(root); ... backend.commit, backend.tag, ...`. Order becomes irrelevant; type checkers catch misuse.

This is a Phase 2 issue; Phase 3 inherits. Don't fix in Phase 3 (out of scope). File a Phase 2.5 ticket.

**Severity:** Low (Phase 3). Medium (cross-cutting if/when Rust/Go adapters land — same destructuring dance × 4 adapters).

---

### F11. `GradlePropertiesVersionSource.write()` verification read-back path is untested

**Task 2, Step 1 (tests) vs. Step 3 (write implementation).** The write path includes:

```python
verified = self.read()
if verified != new_version:
    raise VersionWriteError(...)
```

But the test suite has 5 tests, all on `read()`. None exercise `write()` or the verification read-back. The plan's commit message even claims "GradlePropertiesVersionSource reads from gradle.properties" — no mention of write.

The lifecycle test (`test_kotlin_lifecycle_run_minor_bumps_gradle_properties_tags_pushes`) reads back via `src.read()` and asserts it equals "1.3.0" — this exercises the round-trip but only via the happy path. The `VersionWriteError` raise path is dead code in the test suite.

**Simplification:** add one negative test:

```python
def test_write_raises_version_write_error_on_verification_mismatch(tmp_path: Path) -> None:
    # Force a verification mismatch by stubbing read after write
    src = GradlePropertiesVersionSource(tmp_path)
    (tmp_path / "gradle.properties").write_text("version=1.2.3\n")
    with mock.patch.object(src, "read", side_effect=["1.2.3", "WRONG"]):
        with pytest.raises(VersionWriteError, match="Verification"):
            src.write("1.3.0")
```

Or remove the verification code entirely (it's defensive code not justified by tests). The Phase 1 spec says `VersionSource.write()` "MUST verify by reading back after writing" — so the code stays, but it deserves a test.

**Severity:** Medium. Spec requires it; test doesn't cover it. Future bug surface.

---

### F12. `_make_lifecycle` helper in `test_lifecycle.py` is fine, but `mock.Mock(return_value="abc123def456" + "0" * 32)` is opaque

**Task 5, Step 1.** The SHA stub:

```python
commit = mock.Mock(return_value="abc123def456" + "0" * 32)
```

Generates `"abc123def4560000000000000000000000000000"` — a 40-char string. Two issues:

1. The constant `"0" * 32` is a magic number (SHA-1 length minus prefix).
2. The test asserts `len(sha) == 40` in the git_backend test (`test_commit_runs_git_commit_with_message`), but the lifecycle test never asserts the SHA length — the magic-string isn't load-bearing there.

**Simplification:** hoist a `_FAKE_SHA = "a" * 40` constant to `_gradle_helpers.py`. Other tests can import it. Currently only the lifecycle test uses it; if a future test needs a SHA, the constant exists.

**Severity:** Trivial. Cosmetic.

---

### F13. CHANGELOG entry is comprehensive but verbose — same as Phase 2 F10

**Task 8, Step 2.** The bullet is 8 lines covering the adapter, version source, hooks, MCP tools, and entry-point group. Phase 2's CHANGELOG bullet was similarly verbose. Phase 2's review (F10) said: "Not a YAGNI issue. The bullet could be tightened... but that's editorial, not structural."

Same verdict here. Leave it.

**Severity:** None.

---

### F14. Spec coverage check — minor: spec's "Per-adapter Kotlin" doesn't enumerate `_bump` semantics; plan picks real-semver arbitrarily

**Spec § Per-adapter Kotlin (Rev 2).** The spec describes `GradlePropertiesVersionSource` (probe order + gradlew fallback) and `GradleTaskProbe` (task existence). It does NOT specify `_bump` semantics — that's an adapter implementation detail. Phase 3 picks real-semver (matches Python, diverges from Swift).

This is correct scope discipline (the spec doesn't constrain adapter-level bump behavior), but the plan doesn't acknowledge the choice is unilateral. The "Cross-adapter `_bump` divergence" section notes the choice but doesn't justify it.

**Simplification:** add one sentence to the plan: "Phase 3 picks real-semver for Kotlin because Gradle/IntelliJ ecosystem convention is real-semver (e.g., `0.1.0` → `1.0.0` is a major release, not a minor one)." That gives reviewers a documented rationale.

**Severity:** Low. Documentation gap, not a code defect.

---

## Coverage Statement

I reviewed the full Phase 3 plan (~1200 lines / 8 tasks / 8 commits) against the focus areas:

1. **Over-engineering** — covered. F1 (orphan `GradleTaskProbe`), F2 (dead factory), F3 (lint-silencing import), F5 (fake-green test) are the central instances. F4 (cross-adapter prose) is plan bloat, not code bloat.
2. **YAGNI** — covered. F6 (`git_backend.py` duplication) is the rule-of-three threshold; F8 (hybrid test pair) is correctly skipped but under-documented; F9 (`autofix`) is correctly deferred.
3. **Pattern adherence** — Phase 2 patterns held. Constructor injection ✓, per-adapter `git_backend.py` (duplicated, not yet shared) ✓, Module:ClassName entry-point ✓, 4-step MCP registration ✓ (Task 7 calls out that `profiles.py` is unchanged because the group already exists — correct), per-invocation auth check ✓ (mutation tool calls `_require_auth_config()` at top of body, not at startup).
4. **Specific simplifications** — covered. F3 (drop the `make_git_backend` import), F5 (drop the fake-green test), F11 (add the missing negative test for write verification).
5. **Hidden complexity** — covered. F1 (the probe never called) is the central hidden complexity; F10 (positional destructuring) is inherited fragility.
6. **Phase 2 carry-over** — covered. CF-1 (dead defensive code) maps to F3 (lint-silenced import). CF-2 (dead lifecycle construction in `capabilities()`) is correctly handled — `KotlinAdapter.capabilities()` does NOT construct `KotlinLifecycle`. CF-3 (`_bump` divergence) is correctly documented but the plan balloons it into a 12-line cross-adapter essay (F4).
7. **YAGNI vs. Spec Pressure** — covered. F8 surfaces the hybrid-test spec ambiguity that the plan doesn't explicitly resolve.

**Top 3 actions for the plan author:**

1. **F1 + F3**: Either wire `GradleTaskProbe` into the runtime hook invocation path (Phase 1 hook runner, or Phase 3's MCP tool wrapper) or drop the class entirely. Drop the `_ = make_git_backend` import in `KotlinAdapter.capabilities()`. Both are dead code masquerading as defensive code.
2. **F5 + F11**: Delete `test_kotlin_lifecycle_rejects_invalid_level` (it's a Phase 1 test). Add a negative test for `GradlePropertiesVersionSource.write()` verification mismatch (it's spec-required, untested).
3. **F4 + F6**: Trim the cross-adapter `_bump` divergence essay (file as Phase 2.5 ticket); make the `git_backend.py` duplication explicit in code with a `MIRROR of swift/git_backend.py` comment OR (preferred) extract to a shared `_git_backend.py` module now while there are only 2 consumers.

---

## Spec Coverage Summary

Phase 3 implements the spec's Kotlin/Gradle section faithfully:

| Spec § Item | Plan Implementation | Verdict |
|---|---|---|
| Kotlin F1: probe `pluginVersion`/`projectVersion`/`version` with `\b` anchors | `_PROBE_KEYS = ("pluginVersion", "projectVersion", "version")` + regex with `\b` | ✓ |
| Kotlin F1: fallback to build.gradle.kts scan | `for gradle_file in ("build.gradle.kts", "build.gradle")` | ✓ |
| Kotlin F1: verify via `./gradlew properties` | `_read_via_gradle()` | ✓ but untested |
| Kotlin F1: `--no-daemon --no-configuration-cache` | In `_read_via_gradle` AND in `GradleTaskProbe.has_task` | ✓ |
| Kotlin F2: task-existence probe before invocation | `GradleTaskProbe` class exists; `kotlin_hooks()` constructs it but never calls it | ⚠ half-wired (F1) |
| Kotlin F2: skip-with-warning if absent | Comment-only; no code path | ⚠ deferred (F1) |
| Lifecycle rollback contract | Mirrors Swift's pattern; gradle.properties write happens before commit, so rollback is symmetric | ✓ |
| MCP F1: 4-step registration | Task 7 adds tools to existing `language_tools` group; `profiles.py` correctly unchanged | ✓ |
| MCP F5: auth posture for mutation tools | `_require_auth_config()` per-invocation | ✓ |
| MCP F7: async/sync split | `asyncio.to_thread` in `kotlin_bump_version` | ✓ |
| Writing F2: hybrid fallback single interpretation | Phase 3 hooks have no fallback (YAGNI-correct); under-documented (F8) | ⚠ |
| Testing F2: mcp-common helpers pre-verified | Out of scope for Phase 3 (Phase 1 responsibility) | ✓ (assumed) |
| Testing F3: hybrid two-path test pair | Not applicable (no fallback) but unstated | ⚠ |
| Testing F5: shared `FakeHookRunner` | Not used in Phase 3 tests (Phase 1 hook-runner concern) | ✓ (out of scope) |

---

## Plan Quality Verdict

**Approve with revisions.** Phase 3 follows Phase 2's patterns faithfully and implements the spec's Kotlin section correctly. The two material concerns are (1) the orphaned `GradleTaskProbe` class (F1) which suggests the runtime hook invocation path isn't fully thought through, and (2) the byte-for-byte `git_backend.py` duplication (F6) which is the rule-of-three threshold. The remaining findings are test/code hygiene that don't block execution but should be cleaned before merge.

**No BLOCKER findings.** One HIGH (F1). Three MEDIUM (F2, F3, F5). The plan can proceed to execution if F1 + F3 are resolved during implementation (the implementer should either wire `GradleTaskProbe` into the actual hook path or drop it; should drop the `_ = make_git_backend` line). F5 (fake-green test) and F11 (untested write verification) should be addressed in the same PR.

**Recommended next step:** dispatch a 9-lens multi-agent review (per Phase 2 process) before execution; this is one of the 9 lenses.

REVIEW_COMPLETE

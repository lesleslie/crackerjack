# Security Lens Review — Crackerjack Phase 3 (Kotlin/Gradle) Plan

**Plan:** `/Users/les/Projects/crackerjack/docs/superpowers/plans/2026-09-07-crackerjack-multi-language-phase3.md`
**Spec:** `/Users/les/Projects/crackerjack/docs/superpowers/specs/2026-09-07-crackerjack-multi-language-design.md` (Rev 2)
**Phase 2 precedent:** `/Users/les/Projects/crackerjack/docs/superpowers/plans/reviews/2026-09-07-phase2-security.md`
**Reviewer lens:** Security (subprocess, auth, project_root, arg injection, lifecycle rollback)
**Review date:** 2026-09-09

## Summary

The plan carries forward most Phase 2 security controls via the "mirror Swift" pattern. **Subprocess argv lists are correct**, no `shell=True`, `--notes-file` (not `--generate-notes`), `MAHAVISHNU_GIT_REMOTE` is configurable, and `git status --porcelain` is in the constraint list. The HIGH and BLOCKER findings below are concentrated in three places: (1) inherited Phase 2 bugs that Phase 3 does not fix; (2) one genuine new conflict between plan text and test (dry_run semantics); (3) the lifecycle skeleton is shown but not the body, so several guarantees are un-verifiable from the plan alone.

3 HIGH findings, 6 MEDIUM findings, 4 LOW findings, 4 INFO confirmations. No BLOCKER.

---

## Findings (most-severe first)

### F-1 [HIGH] Inherited Phase 2 F-1: auth helper is config-only, not JWT validation

**Location:** Plan line 38 (Global Constraints), Task 7 Step 3 line 1036 (`_require_auth_config()`), Task 7 Step 1 line 1010-1016 (test).

**What's wrong.** Phase 2 review F-1 documented that `_require_auth()` only checks for env-var presence and performs no JWT decode, signature verification, expiry, or audience check. Phase 3 calls this helper `_require_auth_config` (the rename Phase 2 F-1 recommended), but the plan does not implement or even mention JWT validation. The new test (plan line 1010-1016) only asserts env-var absence raises `PermissionError` — same surface check as Phase 2's failing test.

**Why it matters.** Any process that runs with `MAHAVISHNU_AUTH_ENABLED=true MAHAVISHNU_JWT_SECRET=x` set bypasses the guard. `kotlin_bump_version` mutates a real Kotlin repo (commit + tag + push + gh release), so the attack surface is identical to Phase 2's `swift_bump_version`. A local attacker who can `export` these two env vars before invoking the MCP server gets full release authority. The rename from `_require_auth` to `_require_auth_config` makes the false confidence clearer, but does not address the gap.

**How to fix.**
1. Add a JWT validation path: `jwt.decode(token, secret, algorithms=["HS256"], audience=..., options={"require": ["exp"]})`. Token must come from a request header or argument; reject missing/invalid/expired tokens with `PermissionError`.
2. Add a test that proves a token signed with a different secret raises `PermissionError`.
3. Bind the validated `sub` claim into the commit/tag message.
4. Until JWT validation lands, the `_require_auth_config` rename is honest but does not satisfy the spec's "auth posture" intent.

---

### F-2 [HIGH] Inherited Phase 2 final-review IMPORTANT-1 bug: `MAHAVISHNU_PROJECT_ROOTS` unset bypasses allowlist

**Location:** Plan line 46 (Global Constraints: "`project_root` validated via `Path(project_root).resolve(strict=True)` + `MAHAVISHNU_PROJECT_ROOTS` allowlist"). Task 7 Step 3 line 1037 calls `_validate_project_root(project_root)`.

**What's wrong.** Phase 2 final review IMPORTANT-1 found that `_validate_project_root` is inverted: when `MAHAVISHNU_PROJECT_ROOTS` is unset, the function silently accepts any path (the "safe-by-default" intent — block when no allowlist is configured — was flipped to "permissive-by-default"). Phase 3 inherits Phase 2's validator with no mention of fixing the inverted behavior. Every Kotlin mutation (`kotlin_bump_version`) and read (`kotlin_list_hooks`) flows through this validator, so the same path-traversal surface exists.

**Why it matters.** A request like `kotlin_bump_version(level="minor", project_root="/tmp/attacker/with/gradlew")` succeeds when `MAHAVISHNU_PROJECT_ROOTS` is not configured (the common case in dev). `cwd=/tmp/attacker/with/gradlew` then executes the attacker-controlled `./gradlew properties` and later `git add .` over arbitrary files. Combined with the unvalidated tag name (F-4), this is a release-t-pug through the MCP server.

**How to fix.**
1. Re-read Phase 2's `_validate_project_root` and flip the `MAHAVISHNU_PROJECT_ROOTS` empty-state to deny (`if not allowlist: raise PermissionError`).
3. Add a regression test: `_validate_project_root("/tmp/foo")` raises when env var unset.
4. Phase 3 plan line 46 should explicitly call out the fix, not just say "inherits."

---

### F-3 [HIGH] Dry-run semantics conflict: plan text mutates, test name says it doesn't

**Location:** Task 5 Step 3 line 826-828 (the "Kotlin-specific bump action" instruction): *"after computing `new_version`, call `self._version_source.write(new_version)` BEFORE the dry_run check."* Task 5 Step 1 line 760-766 (test `test_kotlin_lifecycle_run_dry_run_does_not_mutate`).

**What's wrong.** Two documents in the same task disagree:

- The test asserts that `dry_run=True` results in `commit_sha is None`, `tag_name is None`, and `"dry_run" in result.skipped_steps` — the test name says "does_not_mutate."
- The instruction says to call `self._version_source.write(new_version)` **before** the dry_run check. If the implementer follows the instruction literally, dry_run would still write to `gradle.properties` — a real on-disk mutation.

**Why it matters.** A test named "does_not_mutate" that passes after the file IS mutated is a false-positive test. Worse, dry_run is the standard "show me what would happen" gate for release engineers — silently mutating the file under dry_run corrupts the very thing the user wanted to inspect. This is the Kotlin-specific analog of Phase 2's CF-4 regression (silent failure mode).

**How to fix.**
1. Choose the intended semantics. Recommend: `if options.dry_run: skip write, return result with skipped_steps`.
2. Update the instruction in Task 5 Step 3 line 826 to: *"after computing new_version, if `options.dry_run`: return `LifecycleResult(new_version=..., skipped_steps=("dry_run",))`. Otherwise, call `self._version_source.write(new_version)`."*
3. Strengthen the test (line 760-766) with `assert (tmp_path / "gradle.properties").read_text() == "version=1.2.3\n"` so a regression where write happens pre-check fails the test.

---

### F-4 [MEDIUM] Tag-name semver regex stated as constraint, never operationalized in the plan

**Location:** Plan line 47 (Global Constraint: "Tag name format validated against semver regex (per Security F7, Phase 2)"). Task 4 Step 3 line 641-647 (says "mirror Swift's git_backend.py").

**What's wrong.** The constraint says tag names must be semver-validated, but the plan does not show WHERE in the lifecycle or `_tag` function this check lives. Task 5 does not show the `KotlinLifecycle.run()` body — only "mirror Phase 2's `crackerjack/adapters/swift/lifecycle.py` exactly." Task 4 instructs the implementer to "diff-verify against the Phase 2 file before copying" but does not mandate adding the regex check if Phase 2's file is missing it. The plan cannot be audited for the constraint.

**Why it matters.** Tag names flow into `git tag -a -- v1.2.3 -m ...`. Even with `--`, a malicious tag like `v1.2.3 --upload-pack=...` (crafted to defeat the separator) is rejected by modern git only when the regex check runs. Without it, an attacker who controls `level`/`new_version` (e.g., via a corrupted `gradle.properties`) could craft a tag that breaks git's parsing or, worse, causes `git push` to invoke an unintended remote helper. Lower risk than shell injection (argv list blocks that), but still an attack surface.

**How to fix.**
1. Either include the Phase 2 `_tag` source in Task 4 Step 3 explicitly, OR add an explicit Step 3.5 in Task 4 that asserts the regex (`re.fullmatch(r"v\d+\.\d+\.\d+(?:[-+][0-9A-Za-z.-]+)?", tag_name)`) lives inside the `tag()` callable.
2. Add a test asserting `_tag("v1;rm -rf /", "msg")` raises `ValueError`.
3. Add the same assertion to the `KotlinLifecycle` level (defense in depth: tag built from `f"v{new_version}"` should also be validated after composition).

---

### F-5 [MEDIUM] `kotlin_bump_version` skips `adapter.detect()` check; `kotlin_list_hooks` enforces it (inconsistent validation)

**Location:** Task 7 Step 3 line 1028-1082.

**What's wrong.** `kotlin_list_hooks` (line 1064-1081) calls `adapter.detect(root)` and raises `ValueError(f"No build.gradle(.kts) at {root}")` if absent. `kotlin_bump_version` (line 1028-1061) does NOT call `detect()`. The path flows: validate project_root → build `GradlePropertiesVersionSource(root)` → if no `gradle.properties` exists, fall back to `_read_via_gradle()` which runs `./gradlew properties` (FileNotFoundError if gradlew is missing).

**Why it matters.** A user invoking `kotlin_bump_version` on a Python project gets a confusing `VersionNotFoundError` or `FileNotFoundError` from `./gradle` instead of the cleaner "no Kotlin project at <root>" message that `kotlin_list_hooks` returns. Worse: if a Python project happens to contain a `gradle.properties` file (e.g., a docs project that borrowed the convention), the tool will silently try to bump it. This is a Phase 2 CF-4-style regression in the making — silent adoption by non-target projects.

**How to fix.**
1. In Task 7 Step 3, add `if not KotlinAdapter().detect(root): raise ValueError(...)` immediately after `_validate_project_root` in `kotlin_bump_version`, mirroring `kotlin_list_hooks`.
2. Add a test asserting `kotlin_bump_version(level="minor", project_root="/tmp/python-project")` raises `ValueError` with "No build.gradle" message.

---

### F-6 [MEDIUM] `GradleTaskProbe.has_task` ignores returncode; the probe class is dead code

**Location:** Task 3 Step 3 line 461-466 (`GradleTaskProbe.has_task`), line 469-477 (`_build_hooks`).

**What's wrong.**

1. `has_task` does `result = subprocess.run(...)` and immediately regex-searches `result.stdout` without checking `result.returncode`. If `./gradlew` is missing (FileNotFoundError → `subprocess.SubprocessError` propagates) or the build script has a syntax error (returncode != 0, stdout may be empty or partial), the regex doesn't match, `has_task` returns False, and any consumer interprets "task absent" when the truth is "couldn't determine."
2. `_build_hooks` constructs `probe = GradleTaskProbe(project_root)` but never calls `probe.has_task(...)`. The comment (line 473-476) acknowledges this: *"the hook still emits; CLI invocation will skip-with-warning at execution time."* But "CLI invocation" here means the downstream hook runner, which Phase 3 does not modify. So `GradleTaskProbe` is dead code in this plan.

**Why it matters.** Spec Kotlin F2 says "skip-with-warning if task absent" — this requires a probe call SOMEWHERE. The plan has the class but never wires it. Tests pass because tests don't check the wiring (tests only check that the probe's `has_task` method works in isolation). Result: `kotlin.ktlint` runs against a Kotlin project without `ktlintCheck` defined → cryptic Gradle failure instead of skip-with-warning.

**How to fix.**
1. In `has_task`, add `if result.returncode != 0: raise GradleProbeError(result.stderr)` so consumers can distinguish "task absent" from "couldn't probe."
2. In `_build_hooks`, actually call `probe.has_task(task_name)` and either skip the hook or include a `skip_reason` field on `Hook` (would need API change — Phase 2 final review found Phase 2 ignored similar issues).
3. Minimum viable: drop `GradleTaskProbe` from Phase 3 (move to Phase 3.5 follow-up) and document the hook runner does the probing at execution time.

---

### F-7 [MEDIUM] `shutil.which` mock in `test_kotlin_hooks_returns_three_hooks` is a no-op (implementation never calls `shutil.which`)

**Location:** Task 3 Step 1 lines 432-454. Test mocks `shutil.which`, but Task 3 Step 3 (line 437-489) implementation never invokes it.

**What's wrong.** Every test in Task 3 Step 1 wraps the call with `with mock.patch.object(shutil, "which", return_value="/usr/bin/gradlew"):`. The implementation in Step 3 has no `shutil.which` call. The mock is decorative — the test would pass with or without the mock. This indicates the implementer forgot to wire the pre-flight CLI-availability check.

**Why it matters.** When `./gradlew` is not present at `project_root / "gradlew"`, the user gets `FileNotFoundError: [Errno 2] No such file or directory: './gradlew'` from the first hook invocation. No pre-flight check, no actionable error message. The spec's "hybrid fallback" rule (Writing F2) requires a clear failure when CLI is missing AND no fallback is registered — without the pre-flight, the rule is silently bypassed.

**How to fix.**
1. Add `if not (project_root / "gradlew").exists(): raise RuntimeError("gradlew not found; run `gradle wrapper` to generate")` in `_build_hooks` or in a new `_ensure_gradlew(project_root)` helper.
2. Add an explicit test asserting the error is raised when gradlew is absent.
4. Update the existing tests to either match this behavior or drop the `shutil.which` mock that doesn't do anything.

---

### F-8 [MEDIUM] `./gradlew` is a relative path trusted from `cwd` — attacker-controlled `project_root` ⇒ attacker-controlled binary

**Location:** Task 2 Step 3 line 282-291 (`_read_via_gradle`), Task 3 Step 3 line 462-466 (`GradleTaskProbe.has_task`).

**What's wrong.** Every Gradle invocation passes `cwd=self._project_root` and `./gradlew` as a relative argv element. This means: whoever controls `project_root` controls the executed script. If `_validate_project_root` permits an attacker-chosen path (the inverted-allowlist bug F-2), the attacker places a malicious `./gradlew` shim and gets arbitrary code execution as the MCP server's UID.

**Why it matters.** Subprocess injection via relative path + cwd is a standard attack when the cwd is not integrity-checked. Phase 2 had the same shape (`swift` is a `swift` binary on PATH, which has its own integrity via system package manager), but `./gradlew` is a per-project script that can be replaced by anyone with write access to the directory. The risk profile is materially worse than Phase 2.

**How to fix.**
1. Resolve the binary absolutely: `gradlew = (project_root / "gradlew").resolve(strict=True)`.
2. Verify the resolved path starts with `project_root.resolve(strict=True)` (reject symlink escapes).
3. Verify executable bit is set.
4. OR: require `gradlew` on PATH via `shutil.which("gradle")` (system-installed Gradle) and document the wrapper requirement.

---

### F-9 [MEDIUM] No `.gitignore` exclusion enforcement before `git add .` — Kotlin secrets can leak

**Location:** Task 4 Step 3 line 641-647 (says "mirror Swift's git_backend.py"). Implicit commit via `commit(message)` calling `git add .`.

**What's wrong.** Phase 2 review did not flag this for Swift because Swift's `.build/` and `.swiftpm/` are typically in `.gitignore`. Kotlin projects frequently have:

- `local.properties` — contains `sdk.dir=...` and (sometimes, per JetBrains convention) signing credentials for plugin publishing.
- `.gradle/` — build cache, can contain cached credentials if `init.gradle.kts` references a credentials service.
- `build/` — built artifacts, may contain expanded secrets from Gradle properties.

The `commit(message)` function (per Phase 2 pattern, lines from the Swift file presumably `git add . && git commit -m <message>`) does not exclude any paths. If a Kotlin project does not have a `.gitignore` (a freshly-initialized test repo, for example), `gradle.properties` and `local.properties` get committed.

**Why it matters.** Phase 2 has the same shape but lower exposure. Phase 3 inherits this behavior. Even with a `.gitignore`, `git add .` does not delete already-tracked files — once a developer accidentally tracked a credential, every subsequent bump commits it again.

**How to fix.**
1. In `commit()`, use `git add -A -- <paths>` with an explicit allowlist (project source) rather than `git add .`.
2. OR: pre-flight check that `.gitignore` exists and contains at least `.gradle/`, `build/`, `local.properties`; refuse to commit if missing.
3. Document the convention in `KotlinAdapter.capabilities()` docstring.

---

### F-10 [LOW] `_validate_project_root` NUL-byte / `..` rejection not verified

**Location:** Plan line 46. Inherited from Phase 2.

**What's wrong.** Phase 2 review F-2 recommended: "Reject paths containing NUL bytes or control characters." Plan line 46 says "`project_root` validated via `Path(project_root).resolve(strict=True)` + `MAHAVISHNU_PROJECT_ROOTS` allowlist" — does not explicitly mention NUL byte rejection. The validator the plan inherits may or may not reject NULs.

**Why it matters.** `Path("\x00/etc/passwd")` on POSIX raises `ValueError`, but if the validator uses string concatenation instead of `Path`, NUL injection in `pathlib` operations can produce surprising behavior.

**How to fix.** Add a one-line assertion in Task 7's `kotlin_bump_version`: `if "\x00" in project_root: raise ValueError("NUL byte in path")`. Mirror in `kotlin_list_hooks`. Test both.

---

### F-11 [LOW] No pre-Phase-3 gate for Gradle CLI availability (Phase 2 had one for mcp-common)

**Location:** Plan lacks any pre-flight gate analogous to Phase 2's BLOCKER B1.

**What's wrong.** Phase 2's final-review BLOCKER B1 was "verify mcp-common testing helpers exist before implementation starts." Phase 3 has no equivalent gate. The plan jumps to implementing the Gradle adapter without verifying that the runtime environment actually has `./gradlew` available — the plan will silently produce a failing test suite on hosts without Java/Gradle.

**Why it matters.** A CI run on a Python-only image will fail with confusing "ModuleNotFoundError: No module named 'crackerjack.adapters.kotlin'" or worse, passing registration + failing probe. A pre-flight gate documents the system requirement up front.

**How to fix.** Add to Task 8 verification: `command -v gradle && test -x tests/fixtures/gradle-vanilla/gradlew` (after creating the wrapper). Or document the gate in Task 1 Step 1's "Expected" output.

---

### F-12 [LOW] Lifecycle body and git_backend body are referenced but not shown — implementer has to "mirror" without verification

**Location:** Task 4 Step 3 line 641-647 (says "verified at `crackerjack/adapters/swift/git_backend.py` lines 27-158... Copy verbatim, with two header changes"). Task 5 Step 3 line 822-844 (says "Mirror Phase 2's `crackerjack/adapters/swift/lifecycle.py` exactly").

**What's wrong.** The plan tells the implementer to "copy Swift's git_backend.py" and "mirror Swift's lifecycle.py exactly" without showing the source. The implementer must read Phase 2's source and copy it. Risks: (a) drift — Phase 2 source has a bug not caught in Phase 2 review; (b) Phase 2 source gets updated between Phase 2 and Phase 3 implementation, breaking the mirror; (c) the implementer interprets "mirror" as "rough copy" and accidentally drops the regex check (F-4) or the returncode check.

**Why it matters.** Phase 2 review caught 4 findings via direct line references. Phase 3 review cannot do the same because the source isn't shown. Auditing a plan that says "trust me, it's a mirror" is not possible.

**How to fix.** Either (a) inline the source of `git_backend.py` and the lifecycle body in Task 4 / Task 5 Step 3 explicitly, OR (b) add a Phase 0 step that diffs Phase 2 sources vs. Phase 3 sources after implementation, with a CI guard.

---

### F-13 [INFO] `shell=True` is absent everywhere

Verified across all 7 subprocess invocations in the plan (`_read_via_gradle`, `GradleTaskProbe.has_task`, and the 6 mirror-from-Swift git/gh methods). All use argv lists with `cwd=`. ✓

---

### F-14 [INFO] `--notes-file` enforced; `--generate-notes` excluded

Task 4 Step 1 test line 620-631 asserts both invariants. The mirror-from-Swift carries Phase 2's fix. ✓

---

### F-15 [INFO] `MAHAVISHNU_GIT_REMOTE` env var with `origin` default

Task 4 Step 1 tests line 567-590 cover both "configured" and "default" cases. ✓

---

### F-16 [INFO] `git tag -a -m M -- N` ordering inherited from Phase 2 commit `b2199190`

Plan line 52 explicitly cites the fix. The mirror-from-Swift guarantees the ordering. ✓

---

## Coverage Statement

This review covered:

- All 7 subprocess invocations across Tasks 2, 3, 4 — argv list vs. shell, returncode handling, returncode-vs-fallback ambiguity, relative-vs-absolute binary paths.
- All MCP mutation surfaces in Task 7 — auth, path validation, dry_run semantics, detect() consistency.
- All version-source write paths in Task 2 — read-back verification, rollback ordering, file mutation under dry_run.
- All tag-name composition paths in Task 5 — semver regex presence (or absence), separator use.
- Phase 2 carry-over: 7 of 13 Phase 2 security findings are correctly inherited; 1 (F-1 auth helper) is inherited without fix; 1 (final-review IMPORTANT-1 path validator) is inherited without fix.
- Phase 2 CF-4 analog risk (silent-failure mode) — identified F-3 (dry_run), F-5 (detect skip), F-6 (probe unused).

**Out of scope:**

- Real Gradle fixture (Task 8) — fixture has no security surface.
- Spec consistency for Web (Phase 4) and Swift (Phase 2) — covered by other lenses.
- CHANGELOG entry (Task 8 Step 2) — documentation, no security impact.
- Pyproject entry-point declaration (Task 1) — minimal surface, covered by Phase 2 review F-2 analog.
- Build-script-level Kotlin security (Gradle init scripts, plugin trust) — out of plan scope.

---

## Spec Coverage Summary

| Spec Requirement | Plan Coverage | Verdict |
|---|---|---|
| **MCP F5** — auth posture for mutation tools | Stated; helper is config-only | Partial — inherits Phase 2 F-1 |
| **Kotlin F1** — `--no-daemon --no-configuration-cache` | Enforced in Task 2 line 283, Task 3 line 463; tested | ✓ |
| **Kotlin F2** — task probing, skip-with-warning | Class exists; never wired | Partial — dead code (F-6) |
| **Security F2** — `_validate_project_root` allowlist | Stated; inverted semantics inherited | Partial — F-2 |
| **Security F3** — `gh release` raises on non-zero | Test enforces (line 609-617) | ✓ |
| **Security F5** — `--notes-file`, not `--generate-notes` | Test enforces (line 620-631) | ✓ |
| **Security F6** — pre-flight `git status --porcelain` | Stated as constraint; not verified in shown code | Partial — relies on mirror |
| **Security F7** — tag name semver regex | Stated as constraint; not operationalized | Partial — F-4 |
| **Writing F2** — hybrid fallback, single interpretation | Spec written; CLI-availability pre-flight missing | Partial — F-7, F-11 |
| **Lifecycle rollback (spec MCP F2)** | Mentioned in Task 5 sub-step 5.1; body not shown | Partial — F-12 |

---

## Plan Quality Verdict

**Verdict: Implementable after addressing the 3 HIGH findings.**

The Phase 3 plan is structurally sound: it correctly mirrors Phase 2 for most security controls, all subprocess calls use argv lists, the auth path is at least present, the path validator is referenced, and the lifecycle/write/rollback order is described. The 3 HIGH findings are addressable in <30 lines of net change:

- F-1 needs a JWT decode call inside `_require_auth_config` (or a rename back to `_require_auth` once it actually validates).
- F-2 needs the `_validate_project_root` empty-state flipped to deny, with one new test.
- F-3 needs the order-of-operations swapped (`dry_run` check before `write`), plus a strengthened assertion.

The 6 MEDIUM findings are real but each independently patchable without redesigning the plan. The most concerning is F-8 (`./gradlew` is a relative path from attacker-influenceable `cwd`) — this is a Kotlin-specific exposure that Phase 2's Swift adapter doesn't have, and the plan should absolutize the binary before subprocess invocation.

The 4 LOW findings are quality-of-implementation concerns rather than security defects.

**Do not implement before HIGH findings are fixed.** F-1 and F-2 are the same defects Phase 2 introduced; Phase 3 is the right place to fix them in the shared `_require_auth_config` and `_validate_project_root` helpers (single edit, fixes both adapters). F-3 is a Phase 3-specific logic conflict that will cause the test named "does_not_mutate" to silently pass while gradle.properties is rewritten.
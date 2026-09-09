# Security Lens Review — Crackerjack Phase 2 (Swift) Plan

**Plan:** `/Users/les/Projects/crackerjack/docs/superpowers/plans/2026-09-07-crackerjack-multi-language-phase2.md`
**Spec:** `/Users/les/Projects/crackerjack/docs/superpowers/specs/2026-09-07-crackerjack-multi-language-design.md` (Rev 2)
**Reviewer lens:** Security
**Review date:** 2026-09-08

## Findings (most-severe first)

### F-1 [HIGH] Auth helper does not authenticate — it only checks config presence

**Location:** Task 7, `language_tools.py` `_require_auth()` (plan lines 1523-1536)

**Summary.** The helper is named `_require_auth` and the spec describes it as "auth posture" (MCP F5), but the implementation only verifies that two env vars are set to non-empty / literal `"true"`. It performs no JWT decode, no signature verification, no expiry check, no audience check, and no caller identification. The plan's own test (`test_swift_bump_version_requires_auth`, line 1420) only asserts that env-var absence raises `PermissionError`; it does not assert that a forged token is rejected.

**Failure scenario.** Any process that runs with the env vars set (or any local attacker who can `export MAHAVISHNU_AUTH_ENABLED=true MAHAVISHNU_JWT_SECRET=x` before invoking the MCP server) bypasses the guard completely.

**Recommendation.**

1. Rename `_require_auth` to `_require_auth_config()` and add a docstring that explicitly states: "config check only; does not validate JWTs."
2. Implement actual JWT validation: `jwt.decode(token, secret, algorithms=[...], audience=..., options={"require": ["exp"]})`. Reject tokens that fail to decode or are expired.
3. Bind the validated `sub` / `aud` claim to the resulting commit/tag message.
4. Add a test that proves a forged/invalid JWT raises `PermissionError`.

---

### F-2 [HIGH] `project_root` parameter is unvalidated — path traversal surface

**Location:** Task 7, all three MCP tools (lines 1631-1681).

**Summary.** All three MCP tools accept `project_root: str` and pass it directly to `Path(project_root)`. There is no normalization, no canonicalization, no whitelist, no rejection of traversal patterns.

**Recommendation.**

1. Immediately call `root = Path(project_root).resolve(strict=True).absolute()` and reject any path outside a configured allowlist (`MAHAVISHNU_PROJECT_ROOTS` env var or `[tool.crackerjack.allowed_roots]`).
2. Reject paths containing NUL bytes or control characters.
3. Add a regression test asserting that `project_root="../../etc"` is rejected before any subprocess is invoked.

---

### F-3 [MEDIUM] `_gh_release` does not check `result.returncode` — silently returns fake URL on failure

**Location:** Task 7, `_run_swift_lifecycle` `_gh_release` closure (lines 1595-1600).

**Failure scenario.** `gh` exits non-zero with auth error → caller is told the release was created. The user thinks they shipped v1.2.3; nothing was published. The synthetic fallback URL embeds `project_root.name`, leaking filesystem information.

**Recommendation.**

1. Check `result.returncode != 0` and raise `RuntimeError` with `result.stderr` attached.
2. Remove the synthetic fallback URL. Contract: "URL or exception," not "URL or fake URL."
3. Test that a non-zero `gh` exit raises.

---

### F-4 [MEDIUM] Method monkey-patching bypasses Lifecycle contract

**Location:** Task 7, `_run_swift_lifecycle` (lines 1602-1608).

**Failure scenario.** A future commit adds a `_audit` decorator to `SwiftLifecycle._commit` for compliance reasons. The Phase 2 wiring substitutes the raw closure; audit trail silently drops every version bump.

**Recommendation.** Refactor to constructor injection:

```python
lifecycle = SwiftLifecycle(
    version_source=version_source,
    project_root=project_root,
    commit=_commit, tag=_tag, push=_push,
    delete_tag=_delete_tag, reset=_reset,
    gh_release=_gh_release,
)
```

Update `SwiftLifecycle.__init__` to accept these as `Callable` parameters. Eliminates `# type: ignore[method-assign]`.

---

### F-5 [MEDIUM] `gh release create --generate-notes` publishes commit messages verbatim

**Location:** Task 7, `_gh_release`.

**Failure scenario.** If a Swift project carries secrets in commit messages, those tokens land on a public GitHub release page on the next `swift_bump_version(release=True)` call.

**Recommendation.**

1. Add `--notes-file` with an explicit body that summarizes commits without embedding raw messages.
2. Pre-release scan for token-shaped strings.
3. Document release policy.

---

### F-6 [LOW] `git reset --hard` in rollback can destroy uncommitted local work

**Recommendation.** Pre-flight: refuse to start when `git status --porcelain` is non-empty, unless `dry_run=False` and `force=True`. Or use `git reset --mixed` followed by `git checkout -- .` so untracked files survive.

---

### F-7 [LOW] Tag-name format is not validated

**Recommendation.**

1. Insert `--` before any user-influenced positional: `["git", "tag", "-a", "--", name, "-m", message]`.
2. Add a `re.fullmatch(r"v\d+\.\d+\.\d+(?:[-+][0-9A-Za-z.-]+)?", tag_name)` pre-check in `GitTagVersionSource.read()`.

---

### F-8 [LOW] `_bump` does not validate semver format

**Recommendation.** Add semver validation inside `GitTagVersionSource.read()` after `lstrip("v")`. Raise `VersionNotFoundError` with the original tag.

---

### F-9 [LOW] Auth check fires too late in `_run_swift_lifecycle`

**Recommendation.**

1. Add a second `_require_auth()` call inside `_run_swift_lifecycle` at the top.
2. Document the auth contract in the `Lifecycle` Protocol docstring.

---

### F-10 [LOW] `_run_swift_lifecycle` ignores subprocess-internal exceptions — leaks process state

**Recommendation.** Refactor `SwiftLifecycle.run()` to wrap `_commit`, `_tag`, and `_push` in a single try block (matching the spec's rollback contract).

---

### F-11 [INFO] No `eval` / `exec` / `compile` in the plan

Confirmed clean.

### F-12 [INFO] Subprocess command-injection surface — all argv lists

Verified each subprocess call uses argv lists, no `shell=True`. Argument-injection (separate from shell injection) flagged in F-7.

### F-13 [INFO] Linting-tool flags to expect

- `# type: ignore[method-assign]` appears six times. Pyright may flag differently; run `ty check` after Task 7.
- `import subprocess` is inside the function body (line 1558). Ruff TCH may flag as late import.
- `_init_git_repo` test helper duplicated 3x. Extract to `tests/adapters/swift/_git_helpers.py`.
- `fastmcp`'s `mcp_app._tool_manager._tools` is private API. Pin `fastmcp~=4.0.0` to lock the contract.

## Coverage Statement

This review covered subprocess command injection, auth bypass surface, token leakage, `project_root` validation, `gh release create` security, failure modes that leak info, Phase 1 lesson application, linting-tool flags, and absence of arbitrary code execution.

Out of scope: Phase 3 Kotlin, Phase 4 Web, Phase 5 Bodai umbrella, real-repo smoke.

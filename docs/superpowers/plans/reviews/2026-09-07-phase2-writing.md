# Writing Lens Review

**Plan:** `/Users/les/Projects/crackerjack/docs/superpowers/plans/2026-09-07-crackerjack-multi-language-phase2.md` (1,917 lines, 8 tasks).
**Spec:** `/Users/les/Projects/crackerjack/docs/superpowers/specs/2026-09-07-crackerjack-multi-language-design.md` (Rev 2).
**Lens:** Writing quality for a new contributor.

---

## Findings (most-severe first)

### HIGH-1 — Task 8.5 smoke step is syntactically broken shell; a new contributor running it as written will hit `command not found`

**Plan location:** Task 8.5 (Real SwiftPM lib smoke), lines ~1815-1825.

**Plan text:**

```bash
cd /Users/les/Projects/swiftui-ipc-client
# Test detection
.venv 2>/dev/null; /Users/les/Projects/mahavishnu/.venv/bin/python -c "
...
"
```

**Why this is a writing defect, not just a typo:**

Line 1818 begins with `.venv 2>/dev/null;` — that is, a literal invocation of a command named `.venv`. There is no such command on macOS or Linux. Zsh will print `(eval):1818: command not found: .venv` (or similar) and then proceed. A new contributor will not understand what the line was meant to do (presumably source the venv, or guard against the venv not existing). The reader has three plausible guesses, none of them right:

1. Source the venv (`source .venv/bin/activate`).
2. Guard against a missing venv (`[ -d .venv ] || true`).
3. Print a warning about a missing venv (`echo ".venv missing" 2>/dev/null`).

None match. The intent was almost certainly `[ -d .venv ] || echo ".venv missing" 2>/dev/null` or similar — but the typo was not caught.

**Risk:**
- A new contributor following the plan verbatim hits a shell error before the smoke test even starts.
- If the implementer decides to "fix it on the fly" without recording the change, future contributors reading the plan will see different behavior than the recorded plan.

**Recommended fix:**

Replace the broken line with an explicit `if [ -d .venv ]; then source .venv/bin/activate; fi` (or drop the line entirely — the next line uses an absolute path to `/Users/les/Projects/mahavishnu/.venv/bin/python`, so no venv activation is needed at all). Add a one-line comment explaining why the venv-activation step is unnecessary (absolute path bypasses PATH lookup).

---

### HIGH-2 — Task 5 implements `_commit` / `_tag` / `_push` / `_delete_tag` / `_reset` / `_gh_release` as `raise NotImplementedError` stubs; the plan delegates the real implementation to "Phase 2 should call into `crackerjack/services/git.py`" without verifying that file exists or supports these operations

**Plan location:** Task 5.3 implementation (lines ~1136-1153) and the "Implementer note (CRITICAL)" callout (lines ~1155-1157).

**Plan text (callout):**

> Same as Phase 1 Task 6 — the six `_commit` / `_tag` / `_push` / `_delete_tag` / `_reset` / `_gh_release` methods are the integration seam. **Phase 2 should call into `crackerjack/services/git.py` for git operations (or `subprocess.run` directly if `services/git.py` doesn't expose tag/delete operations — verify with `grep -n "def.*tag\|def.*reset" crackerjack/services/git.py`)**.

**Why this is ambiguous for a new contributor:**

The plan instructs the implementer to "verify with `grep -n "def.*tag\|def.*reset" crackerjack/services/git.py`" — but does not commit to either:

1. The file `crackerjack/services/git.py` exists.
2. It exposes `tag`, `delete_tag`, `reset` methods.
3. The fallback path (direct `subprocess.run`) is acceptable.

The implementation block then shows ALL SIX methods as `raise NotImplementedError("Phase 2: delegate to services/git.py")` stubs. The unit tests use `mock.patch.object(lifecycle, "_commit", ...)` to bypass the stubs. So the **tests will pass even if neither `services/git.py` is touched nor `subprocess.run` is wired in**.

**Concrete risk:**

A new contributor runs Task 5, sees the tests pass, marks the task done. The CLI tool (`crackerjack run -p minor` on a Swift project) then crashes at runtime with `NotImplementedError: Phase 2: delegate to services/git.py`. There is no integration test that exercises the end-to-end lifecycle against a real git repo (only the gated Task 8.5 smoke, which has its own broken shell issue — see HIGH-1).

**Recommended fix:**

Two complementary changes:

1. **In Task 5.3, replace the `NotImplementedError` stubs with real `subprocess.run` implementations** (mirroring what Task 7.4 does for `_run_swift_lifecycle`). The Phase 1 "Pattern B" lesson is about *testability of the seam* — the seam should still be overridable for tests, but the *default implementation* should work end-to-end.

2. **Add an integration test** that runs the lifecycle against a real git repo (not just mocked `_commit`/`_tag`/etc.). Something like:

```python
def test_swift_lifecycle_end_to_end_creates_tag(tmp_path):
    # Real git repo, real tag, real subprocess; lifecycle writes a tag.
    ...
```

This catches the NotImplementedError stubs.

---

### HIGH-3 — Task 1 says the Swift entry-point "will fail until Task 6 lands the `SwiftAdapter` class — that's expected. Phase 2 acceptance is that both entries are declared by the end of Task 1." A new contributor running Task 1.3 verification will see an error and may stop

**Plan location:** Task 1.3 (lines ~143-153) and the associated acceptance statement.

**Plan text:**

```bash
cd /Users/les/Projects/crackerjack
.venv/bin/python -c "
from importlib import metadata
eps = metadata.entry_points(group='crackerjack.language_adapters')
for ep in eps:
    print(ep.name, '->', ep.value)
"
```

**Expected output (per the plan):**

> Expected output (after Task 6 ships): `python -> crackerjack.adapters.python:PythonAdapter`, `swift -> crackerjack.adapters.swift:SwiftAdapter`. (The Python entry exists; the Swift one will fail until Task 6 lands the `SwiftAdapter` class — that's expected. Phase 2 acceptance is that both entries are declared by the end of Task 1.)

**Why this is a writing defect:**

The "Expected output" is contradictory:

- The script will print BOTH entries if both are declared.
- The plan admits the Swift entry "will fail until Task 6 lands."
- So during Task 1, only ONE entry will print.

A new contributor running the verification step will see one entry, not the two described in the "Expected output." They will then either (a) report the task is broken, or (b) spend time investigating why Swift isn't listed. The parenthetical "(after Task 6 ships)" is buried at the end of the paragraph and easy to miss.

**Recommended fix:**

Restate the verification to match the actual state at the end of Task 1:

```bash
# Expected at end of Task 1 (Python only — Swift lands in Task 6):
#   python -> crackerjack.adapters.python:PythonAdapter
#
# Expected at end of Task 6 (both):
#   python -> crackerjack.adapters.python:PythonAdapter
#   swift -> crackerjack.adapters.swift:SwiftAdapter
```

Then move the Task 6 verification to Task 6.4 (which already exists and expects `['python', 'swift']`).

---

### HIGH-4 — Task 7's `_require_auth` helper uses `os.environ.get("MAHAVISHNU_AUTH_ENABLED", "").lower() != "true"` but the spec (and the test) require exact `"true"`; the `.lower()` is a silent spec drift

**Plan location:** Task 7.4 implementation (lines ~1523-1536) vs spec (Rev 2, Auth posture section).

**Plan text (implementation):**

```python
if os.environ.get("MAHAVISHNU_AUTH_ENABLED", "").lower() != "true":
    raise PermissionError(...)
```

**Spec text (Rev 2, Auth posture):**

```python
if not os.environ.get("MAHAVISHNU_AUTH_ENABLED") == "true":
    raise PermissionError("MAHAVISHNU_AUTH_ENABLED=true required for mutation tools")
```

**Why this matters:**

The implementation is *more permissive* than the spec — it accepts `True`, `TRUE`, `TrUe`, etc. The spec requires exact `"true"`. A new contributor reading only the plan will see `.lower() != "true"` and assume the spec's `==` check was "improved." But the plan is a *spec implementation* — silent broadening of the contract is a defect.

The unit test (`test_swift_bump_version_requires_auth`) only tests the empty-env case, so it does not catch this divergence.

**Recommended fix:**

Match the spec exactly:

```python
if os.environ.get("MAHAVISHNU_AUTH_ENABLED") != "true":
    raise PermissionError(...)
```

Then add a test that verifies non-canonical values (`"True"`, `"TRUE"`, `"1"`) are rejected.

---

### HIGH-5 — Task 7.4 `_gh_release` fallback URL is a hand-rolled placeholder; a new contributor will ship it without realizing it is not real

**Plan location:** Task 7.4 implementation (line ~1600).

**Plan text:**

```python
def _gh_release(tag_name: str) -> str:
    result = subprocess.run(
        ["gh", "release", "create", tag_name, "--generate-notes"],
        cwd=project_root, capture_output=True, text=True,
    )
    return result.stdout.strip() if result.stdout else f"https://github.com/local/{project_root.name}/releases/tag/{tag_name}"
```

**Why this is wrong:**

The fallback URL `https://github.com/local/...` is fabricated. If `gh release create` exits 0 but produces no stdout (which happens if `--generate-notes` is omitted or if the release notes generation is async), the MCP tool returns a bogus URL that points nowhere. The user sees `"release_url": "https://github.com/local/myproject/releases/tag/v1.1.0"` and may paste it into a browser.

**Recommended fix:**

Either:
1. Raise `RuntimeError` when `gh release create` returns no URL: `if not result.stdout.strip(): raise RuntimeError("gh release create produced no URL")`. Match the spec's "best-effort rollback" — failure should fail loud.
2. Use `result.stderr` to surface the actual error.

Either way, drop the fake fallback URL. The spec's error-handling table says "Fail with clear message" — a placeholder URL is not a clear message.

---

### MEDIUM-1 — Phase 1 lessons are referenced by short-hand (`Pattern B`, "out-of-brief fix from Phase 1 Task 6", "Phase 1 ledger ruling #1") without inlining the lesson; a new contributor without Phase 1's plan in hand cannot apply them

**Plan locations:** Multiple — Task 5 ("Pattern B (split methods) per Phase 1 ledger ruling #1"), Task 1.2 ("module:ClassName form per the out-of-brief fix from Phase 1 Task 6"), and the Global Constraints block ("Phase 1 Task 8 documented this contract").

**Why this is a writing gap:**

The plan defers explanation of Phase 1 lessons to Phase 1 artifacts the reader is presumed to have:

- "Pattern B (split methods)" — what is Pattern A? Why is B better?
- "module:ClassName form per the out-of-brief fix from Phase 1 Task 6" — what was the out-of-brief defect?
- "Phase 1 ledger ruling #1" — the Phase 1 ledger is presumably a separate doc.

A new contributor who has never read Phase 1's plan has to reverse-engineer these references from git history or external docs. The plan should be self-contained enough that an implementer can apply the lessons from the plan text alone.

**Recommended fix:**

Inline a 3-5 line summary at each reference:

- Task 5: add "Pattern A = `_commit_and_tag_and_push` as one monolithic method (hard to mock). Pattern B = `_commit`, `_tag`, `_push`, etc. as separate methods (each overridable for tests). Phase 1 chose B."
- Task 1.2: add "Phase 1 Task 6 originally specified the entry-point as `swift = "crackerjack.adapters.swift"` (just the module). This failed at registration because the loader couldn't find the adapter class. The fix: use `module:ClassName` form so the registry can `import_module("crackerjack.adapters.swift")` and then call `getattr(module, "SwiftAdapter")`."

This adds ~10 lines total but eliminates three "why?" questions.

---

### MEDIUM-2 — The "Goal" section in the plan header says "8 tasks, ~10 commits, ~4-5 hours" but the plan header at line 5 of the brief is "~700 lines, 8 tasks"; the actual plan is 1,917 lines (≈2.7× the stated size) and the test commit count does not match the task count

**Plan locations:** Header (line 5 — "~700 lines"), Execution Handoff (lines ~1910-1911 — "8 tasks, ~10 commits, ~4-5 hours").

**Why this matters for new contributors:**

The "Goal" sub-bullets imply a quick read. A new contributor opens the plan expecting ~700 lines and gets nearly 2,000. This sets the wrong expectation for time-to-implement and review effort.

Also: "8 tasks, ~10 commits" — let me count the commits in each task:

- Task 1.4: 1 commit (entry-point)
- Task 2.6: 1 commit (platforms)
- Task 3.5: 1 commit (version_source)
- Task 4.6: 1 commit (hooks)
- Task 5.5: 1 commit (lifecycle)
- Task 6.5: 1 commit (SwiftAdapter)
- Task 7.9: 1 commit (MCP tools)
- Task 8.7: 1 commit (CHANGELOG)

That's exactly **8 commits**, not "~10." Minor but inaccurate.

**Recommended fix:**

Update the header to reflect the actual line count and commit count, or break Task 7 (the largest task, with 5 sub-tests + 1 implementation + 2 modifications + commit) into sub-tasks (Task 7a: implementation, Task 7b: registration map, Task 7c: profiles, Task 7d: tests). This both matches the "~10 commits" claim and reduces cognitive load per commit.

---

### MEDIUM-3 — Spec-vs-plan coverage table in Self-Review claims "Hooks run sequentially per spec; concurrency concerns (F5) | N/A — Phase 1 hooks run sequentially by default; documented" but the plan never documents this contract anywhere

**Plan location:** Self-Review section (line ~1877).

**Plan text:**

> Hooks run sequentially per spec; concurrency concerns (F5) | N/A — Phase 1 hooks run sequentially by default; documented

**Why this is a writing defect:**

The Self-Review table claims the contract is "documented," but `grep`-ing the plan for "sequential," "concurrency," "parallel," or "in parallel" produces nothing in the File Structure or per-task steps. The Hook contract is in `crackerjack.adapters.base` (Phase 1), not in the Phase 2 plan.

A new contributor looking for "where do I document that Swift hooks run sequentially?" has no answer in this plan.

**Recommended fix:**

Either:

1. Add a one-line note in Task 4 ("Hook ordering: per Phase 1's `Hook` protocol, hooks run sequentially in registration order. No Phase 2 change."), or
2. Drop the row from the Self-Review table.

The plan is doing Phase 2 work; leaving a coverage-table row that points at Phase 1 documentation is acceptable *if* the cross-reference is explicit. Currently it's not.

---

### MEDIUM-4 — Plan header claims "Tech Stack" includes `FastMCP 4.x` but Task 7's tests reach into `mcp_app._tool_manager._tools` (a FastMCP internal); if FastMCP 4.x renamed this attribute, the test breaks without warning

**Plan locations:** Tech Stack (line 9 — "FastMCP 4.x"), Task 7.2 (line ~1414).

**Plan text (Task 7.2):**

```python
registered = [t.name for t in mcp_app._tool_manager._tools.values()]
```

**Why this matters:**

This is the same finding the testing lens flagged (LOW-2 in `2026-09-07-phase2-testing.md`). From a writing perspective: the plan's "Tech Stack" claim of FastMCP 4.x is paired with code that pokes at private API. A new contributor who upgrades FastMCP later will see the test fail with no clear explanation.

**Recommended fix:**

Add a one-line note in Task 7.2:

```python
# NOTE: relies on FastMCP private API `_tool_manager._tools`.
# Verify against the installed FastMCP version; if FastMCP 4.x
# renames this, the test will fail with AttributeError.
# Spec Testing F2: prefer mcp-common's get_registered_tools() helper
# if available — Phase 2 should switch once the helper is verified.
```

---

### MEDIUM-5 — Plan body uses `subprocess.run` for `_run_swift_lifecycle`'s inline helper definitions inside `register_language_tools`; this contradicts the Phase 1 lesson about Pattern B's split methods being the *testable seam*

**Plan location:** Task 7.4 (lines ~1556-1608) — the `_run_swift_lifecycle` helper defines `_commit`, `_tag`, `_push`, etc. as nested closures that call `subprocess.run` directly, then assigns them to the `SwiftLifecycle` instance via `lifecycle._commit = _commit  # type: ignore[method-assign]`.

**Why this is a writing defect:**

The plan says Phase 1's Pattern B lesson is "split methods for testability." But Task 7.4 implements the seam in a way that is *harder* to test:

1. The closures are defined inside `_run_swift_lifecycle`, not at module level. They are not directly importable for test mocks.
2. The `lifecycle._commit = _commit  # type: ignore[method-assign]` is monkey-patching the instance, which is a code smell (and the `# type: ignore[method-assign]` admits it).
3. The test `test_swift_bump_version_runs_with_auth` mocks `_run_swift_lifecycle` entirely, bypassing the closures. This means the closures are never exercised in tests.

**Risk:**

A new contributor will read Task 7.4 and conclude this is "the way" to do Pattern B in Phase 3+. They'll reproduce the same monkey-patch pattern for Kotlin lifecycle in Phase 3. Then a refactor that *moves* `_run_swift_lifecycle` will silently break the closures (they reference local variables).

**Recommended fix:**

Either:

1. Move the `_commit` / `_tag` / `_push` / `_delete_tag` / `_reset` / `_gh_release` implementations into `SwiftLifecycle` itself (replacing the `NotImplementedError` stubs in Task 5.3 — see HIGH-2). Then `_run_swift_lifecycle` simply instantiates `SwiftLifecycle(version_source, project_root)` and calls `run()`. No monkey-patching.

2. Or: keep Task 5.3's stubs as-is (the Pattern B seam), and have `_run_swift_lifecycle` *subclass* `SwiftLifecycle` with overrides. The seam is then a class definition, not a closure.

Either approach is cleaner than monkey-patching.

---

### MEDIUM-6 — Plan's "Self-Review" section's Spec coverage table is accurate but incomplete: Kotlin, Web, Jinja, and the spec's "Cross-cutting" scope items are not enumerated as "out-of-scope verification" rows

**Plan location:** Self-Review section, lines ~1887-1902.

**Plan text (Out-of-scope verification):**

> - Kotlin / Web / Jinja — out of scope (Phases 3-4)
> - Crackerjack CLI behavior for existing Python commands — Phase 1 contract holds; Phase 2 doesn't touch Python CLI
> - Bodai CLI dispatcher — Phase 5 work
> - MarketPlace publishing for JetBrains plugins — out of scope

**Why this is incomplete:**

The plan covers Swift (Phase 2). But the spec's other Phase 2-relevant items are missing from the Self-Review's coverage table:

- **`gh release create` is "necessary but not sufficient"** (spec F2) — the plan implements `gh release create` but does not address what makes it "sufficient" (e.g., release notes generation strategy, asset uploads, draft releases). The coverage table just says "Task 5 (_gh_release method); Task 7 (calls gh release create)" — accepted as-is, but the "not sufficient" half is silently dropped.
- **Spec Open Questions carried into Phase 2** — `mcp-common` testing helpers verification (Testing F2) is mentioned in the "Global Constraints" section ("Phase 2 should not begin until this is verified") but has no Task dedicated to it. The Self-Review doesn't track it as a precondition.
- **PyCharm parity placeholder** — Phase 4 scope, but the plan's Risk table mentions "PyCharm parity disagreement with `jinja2-custom-delimiters`" (line 753). The plan doesn't have a placeholder for "track PyCharm parity API evolution so Phase 4 has a known contract."

**Recommended fix:**

Add three explicit rows to the Spec coverage table:

```
| `gh release create` sufficient (F2)         | Deferred to Phase 3+ — current implementation is "necessary only" |
| `mcp-common` testing helpers (Testing F2)  | Pre-Phase-2 gate (Step 0, before Task 1) — not in plan body |
| PyCharm parity API contract (Jinja F10)     | Tracked by Phase 4 (out of scope for Phase 2) |
```

These three rows force the implementer to acknowledge gaps the current table silently papers over.

---

### MEDIUM-7 — Plan does not define a single "verification of Swift CLI flags" result; Task 4.3 is "investigate, then adjust if wrong" with no explicit acceptance criterion for the result

**Plan location:** Task 4.3 (lines ~744-754).

**Plan text:**

> - [ ] **Step 4.3: Verify Swift CLI assumptions**
>
> ```bash
> cd /Users/les/Projects/crackerjack
> swift --version 2>&1 || echo "swift not available"
> swift test --help 2>&1 | head -30 || echo "swift test --help not available"
> swift package --help 2>&1 | head -20 || echo "swift package --help not available"
> which swift-format 2>&1 || echo "swift-format not in PATH"
> ```
>
> Document findings in the report. If `swift test -destination` flag is different, adjust accordingly. If `swift-format` doesn't exist as a separate binary, document.

**Why this is a writing gap:**

"Document findings in the report" is vague. A new contributor can:

1. Skip the verification if they don't have a Swift toolchain (the spec says it's optional).
2. Run the verification, find a discrepancy, and "adjust accordingly" — but the plan gives no criteria for "accordingly."
3. Find that `swift test -destination` exists but has a different name (`--destination` vs `-destination`).

Without an explicit "if Swift CLI is unavailable, the task is still considered complete because unit tests mock subprocess" clause, the implementer is left to guess what counts as done.

**Recommended fix:**

Add an acceptance line after the verification:

> **Acceptance for Task 4.3:** Either (a) the verification runs and results are recorded, or (b) Swift is unavailable, in which case the verification is skipped and the `CRITICAL` flag in Task 4's "Critical investigation step" is downgraded to "informational." The unit tests in 4.1/4.2/4.5 are still authoritative.

---

### MEDIUM-8 — Acronyms `MCP`, `FastMCP`, `SwiftPM`, `gh`, `Swift Tools`, `JetBrains`, `PyCharm` are used in Tech Stack but only `gh` is expanded; `SwiftPM` and `MCP` are not defined in the plan

**Plan location:** Tech Stack (line 9) and throughout the plan body.

**Tech Stack text:**

> Python 3.14, FastMCP 4.x, typer 0.26+, hatchling, Git CLI (via subprocess), SwiftPM CLI (subprocess invocation, no shell), gh CLI for GitHub release creation.

**Defined:** `gh CLI for GitHub release creation` — expanded.
**Undefined:** `FastMCP`, `SwiftPM CLI`, `typer`, `hatchling`, `Git CLI` — used as-is.

A new contributor who has never seen crackerjack's codebase may not know:

- `FastMCP` is the [FastMCP](https://github.com/jlowin/fastmcp) Python framework for MCP servers (vs. raw `mcp` SDK).
- `SwiftPM` is the Swift Package Manager (bundled with `swift` toolchain).
- `hatchling` is a Python build backend (vs. setuptools, poetry).

**Recommended fix:**

Expand on first use:

> Python 3.14, FastMCP 4.x (the FastMCP framework for building MCP servers), typer 0.26+ (CLI framework), hatchling (Python build backend), Git CLI (via subprocess), SwiftPM CLI (the `swift` toolchain's package manager, invoked via `swift package ...`), gh CLI (GitHub's official CLI) for GitHub release creation.

5 lines added, eliminates three "what is that?" questions.

---

### LOW-1 — Plan's Goal section (line 5) has a parenthetical "(Phase 0 design; Phase 1 (foundation + Python refactor) is next.)" — but Phase 1 has shipped by the time Phase 2 is being implemented, making this parenthetical actively misleading

**Plan location:** Header / Goal section (line 5).

**Plan text:**

> **Architecture:** Approach A — Language Adapters as first-class packages.
> **Phase 0 design; Phase 1 (foundation + Python refactor) is next.**

**Why this is wrong now:**

The plan header was written when Phase 0 was the design and Phase 1 was "next." By the time Phase 2 is being implemented, Phase 1 has shipped (the plan's Task 1 references "Phase 1's types are reusable" and Task 7 references "Phase 1 Task 8 documented this contract"). The parenthetical is now stale.

**Recommended fix:**

Replace with: "Phase 0 design (shipped); Phase 1 (foundation + Python refactor, shipped); Phase 2 (this plan) implements the Swift adapter." One line of state, eliminates the staleness.

---

### LOW-2 — Task 6's Step 6.1 includes the test `test_swift_adapter_skips_projects_without_package_swift` which runs `git init` unnecessarily; the testing lens flagged this (LOW-1 in `phase2-testing.md`) but the plan body still has it

**Plan location:** Task 6.1 (lines ~1265-1269).

**Plan text:**

```python
def test_swift_adapter_skips_projects_without_package_swift() -> None:
    with tempfile.TemporaryDirectory() as td:
        # Plain directory with no Package.swift
        subprocess.run(["git", "init", "-q"], cwd=tmp_path_safe := Path(td), check=True)
        assert SwiftAdapter().detect(Path(td)) is False
```

**Why this is a writing defect (not just a code defect):**

The `detect()` implementation is `(project_root / "Package.swift").is_file()`. `git init` is irrelevant. The walrus assignment `tmp_path_safe :=` inside `subprocess.run(...)` is a Ruff readability issue (per `multi-agent-review-catches-blind-spots.md` and project CLAUDE.md). The testing lens already flagged this; the plan has not been updated.

**Recommended fix:**

```python
def test_swift_adapter_skips_projects_without_package_swift() -> None:
    with tempfile.TemporaryDirectory() as td:
        assert SwiftAdapter().detect(Path(td)) is False
```

2 lines simpler, no `git` dependency, no walrus.

---

### LOW-3 — Plan has no "Out of scope" section (the spec has one, the plan's Self-Review has a 4-line out-of-scope-verification list, but neither is labeled clearly)

**Plan location:** Self-Review, lines ~1898-1902.

**Why this is a writing gap:**

The spec has a clear "Out of scope (deferred)" section with bullets. The plan's equivalent is buried as the last 5 lines of the Self-Review section, with no header. A reader scanning the plan for "what isn't this plan doing?" will miss it.

**Recommended fix:**

Move the 4 lines out of Self-Review into a dedicated "Out of scope (handled by other plans)" section near the top of the plan (after Goal / before File Structure). 4 bullets + a one-line header.

---

### LOW-4 — Plan has no "Risks" section (the spec has one; the plan's Risks are scattered across Tasks and Self-Review)

**Plan location:** Spec Risks table (lines 753-761) vs. plan body.

**Why this matters:**

The spec enumerates 11 risks with mitigations. The plan inherits these risks but does not surface them as a section. A new contributor looking for "what could go wrong with this plan?" has to read the spec + the Self-Review to assemble the picture.

**Recommended fix:**

Add a 4-6 row "Risks specific to this plan" table after Self-Review:

| Risk | Mitigation |
|---|---|
| Task 5 stubs raise NotImplementedError at runtime | See HIGH-2: replace with subprocess.run, add integration test |
| Task 7.4 `_gh_release` returns fake URL on missing stdout | See HIGH-5: raise RuntimeError instead |
| Task 8.5 smoke shell is broken | See HIGH-1: fix the `.venv 2>/dev/null` line |
| `mcp-common` testing helpers may not exist | Pre-Phase-2 gate (Step 0) |
| Python 3.14 + `from __future__ import annotations` + Pydantic runtime refs | Already flagged in project CLAUDE.md; no Phase 2 work introduces new instances |

5 rows, 15 lines, surfaces what the spec's Risks table doesn't.

---

### LOW-5 — Plan header references "spec dd9d9c05" (commit hash) in 5+ commit messages but never in the plan body itself; a new contributor cannot find the spec without grep

**Plan locations:** Task 1.4, 3.5, 4.6, 5.5, 6.5, 7.9, 8.7 — every commit message ends with "Spec dd9d9c05 (Rev 2)." The plan header (line 11) references "spec Rev 2, on `main` as of commit `b00b36f0`."

**Why this is mildly confusing:**

The commit messages cite commit `dd9d9c05`. The plan header cites commit `b00b36f0`. Are these the same spec revision? (Probably yes — `dd9d9c05` is the spec commit, `b00b36f0` is the spec's revision-2 commit on `main`.) But the plan doesn't say so. A new contributor running `git log --grep="dd9d9c05"` will find the spec; running `git show b00b36f0` will find the spec. Both work, but only by coincidence.

**Recommended fix:**

In the plan header, add: "Spec commit hash: `dd9d9c05` (also referenced as `b00b36f0` for the post-Rev-2 update)."

---

## Coverage Statement

### What the plan does well

1. **Test-first structure is consistent.** Every task has explicit "write failing tests → run → implement → run → commit" steps. New contributors can follow the rhythm.
2. **Files / Interfaces / Steps structure is consistent across all 8 tasks.** A new contributor can scan the Files list at the top of each task to know what's coming.
3. **Spec-vs-requirement coverage is explicit in Self-Review.** The 15-row coverage table is comprehensive enough that a reviewer can spot gaps.
4. **Phase 1 lessons are referenced** (Pattern B, module:ClassName, auth posture, no Package.swift mutation), even if inlining is incomplete (see MEDIUM-1).
5. **Test count math is internally consistent** (5+5+8+7+4 = 29 in Task 6.4, 5 in Task 7.8, 34 total in Task 8.2 — all match).
6. **Code blocks are mostly syntactically correct** — only Task 8.5 has a broken shell command.
7. **Tech Stack section names the libraries** (Python 3.14, FastMCP 4.x, typer, hatchling, gh) — though expansion is incomplete.
8. **Critical callouts are present** — Task 5's "**Implementer note (CRITICAL)**" marker for the `services/git.py` integration seam is visible.
9. **Commit messages are detailed and traceable** — each ends with "Spec dd9d9c05 (Rev 2)" so future `git log --grep` searches work.
10. **Acceptance criteria are listed** in Self-Review (5 bullets covering tests, regressions, CLI surface, MCP tools, auth posture).

### What the plan does less well

1. **Task 5's NotImplementedError stubs** (HIGH-2) — the implementation passes tests but crashes at runtime.
2. **Task 7.4's `_gh_release` fallback URL** (HIGH-5) — returns a fabricated `https://github.com/local/...` URL when `gh` produces no stdout.
3. **Task 8.5's broken shell command** (HIGH-1) — `.venv 2>/dev/null;` is not valid bash.
4. **Task 7.4's `_require_auth` spec drift** (HIGH-4) — uses `.lower() != "true"` instead of `!= "true"`.
5. **Task 1.3's contradictory expected output** (HIGH-3) — claims both entries will print but admits Swift fails until Task 6.
6. **Phase 1 lessons referenced by short-hand** (MEDIUM-1) — "Pattern B" / "out-of-brief fix from Phase 1 Task 6" / "Phase 1 ledger ruling #1" are unexplained.
7. **Plan header is stale** (LOW-1) — "Phase 1 is next" when Phase 1 has shipped.
8. **Test contract assertions are too loose** — `test_swift_format_hook_prefers_third_party_swift_format` accepts either swift-format or swift as the first arg (testing lens MEDIUM-1). Plan doesn't fix this.
9. **No "Out of scope" or "Risks" sections** — scattered across Self-Review and Tasks (LOW-3, LOW-4).
10. **Acronyms not expanded** — SwiftPM, FastMCP, hatchling (MEDIUM-8).
11. **Spec-vs-plan coverage table is incomplete** (MEDIUM-6) — missing rows for `gh release create` "sufficient" half, mcp-common pre-Phase-2 gate, PyCharm parity API.
12. **Plan references `_tool_manager._tools`** (MEDIUM-4) — private FastMCP API.
13. **Plan body uses monkey-patching** (MEDIUM-5) — `lifecycle._commit = _commit  # type: ignore[method-assign]` contradicts the Pattern B lesson.
14. **Acceptance for Swift CLI verification is vague** (MEDIUM-7) — "Document findings in the report" lacks a clear done-criterion.

### Reviewer recommendations (priority order)

1. **(HIGH)** Replace Task 5.3's NotImplementedError stubs with real subprocess.run implementations (HIGH-2).
2. **(HIGH)** Fix Task 8.5's broken `.venv 2>/dev/null` line (HIGH-1).
3. **(HIGH)** Replace Task 7.4's fake `_gh_release` fallback URL with a runtime error (HIGH-5).
4. **(HIGH)** Match Task 7.4's `_require_auth` to the spec's exact `!= "true"` check (HIGH-4).
5. **(HIGH)** Restate Task 1.3's expected output to reflect the actual state at end of Task 1 (HIGH-3).
6. **(MEDIUM)** Inline the Phase 1 lessons (Pattern B, module:ClassName fix) so the plan is self-contained (MEDIUM-1).
7. **(MEDIUM)** Add a `_require_auth` test for non-canonical values (`True`, `TRUE`).
8. **(MEDIUM)** Replace `lifecycle._commit = _commit  # type: ignore[method-assign]` with either subclassing or moving the implementation to SwiftLifecycle itself (MEDIUM-5).
9. **(MEDIUM)** Add an explicit "Phase 1 is shipped; Phase 2 implements the Swift adapter" header (LOW-1).
10. **(MEDIUM)** Expand Tech Stack acronyms (FastMCP, SwiftPM, hatchling) (MEDIUM-8).
11. **(MEDIUM)** Add three rows to the Spec coverage table for `gh release create` "sufficient" half, mcp-common pre-Phase-2 gate, PyCharm parity API (MEDIUM-6).
12. **(MEDIUM)** Add a one-line note in Task 7.2 about FastMCP private API dependence (MEDIUM-4).
13. **(LOW)** Drop the `git init` call from `test_swift_adapter_skips_projects_without_package_swift` (LOW-2).
14. **(LOW)** Add an "Out of scope" section near the top of the plan (LOW-3).
15. **(LOW)** Add a "Risks specific to this plan" section (LOW-4).

### Summary

The plan is **broadly well-structured** and a competent Swift developer with crackerjack context could implement ~70% of it without further help. The 5 HIGH-severity findings are all concentrated in Tasks 5 and 7 — the two most implementation-heavy tasks. Fixing the HIGH findings turns the plan from "compiles and tests pass" to "runs end-to-end without surprise crashes." The MEDIUM findings are polish; the LOW findings are nice-to-haves.

The plan correctly applies Phase 1 lessons (Pattern B for lifecycle, 4-step MCP pipeline, auth posture for mutation tools, no Package.swift mutation, module:ClassName entry-point form), uses appropriate testing primitives, and achieves a reasonable test count (34 tests). The most actionable improvement is replacing the NotImplementedError stubs in Task 5 with real subprocess implementations — without this change, the implementation will pass unit tests but crash on first real `crackerjack run -p minor` against a Swift project.

**Recommended action before implementation begins:** Address HIGH-1, HIGH-2, HIGH-3, HIGH-4, and HIGH-5. The MEDIUM and LOW findings can be filed as Phase 2 ledger entries for a future polish pass.

---

## Status

**REVIEW_COMPLETE** — review file written. Plan implementation can proceed with the recommended HIGH-severity fixes tracked in a Phase 2 ledger entry before Task 5 begins.
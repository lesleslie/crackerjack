# Writing Lens Review

**Plan:** `/Users/les/Projects/crackerjack/docs/superpowers/plans/2026-09-07-crackerjack-multi-language-phase3.md` (~1,221 lines, 8 tasks).
**Spec:** `/Users/les/Projects/crackerjack/docs/superpowers/specs/2026-09-07-crackerjack-multi-language-design.md` (Rev 2).
**Lens:** Writing quality for a new contributor, documentation completeness, docstring/comment accuracy, CHANGELOG quality, plan clarity.

---

## Findings (most-severe first)

### HIGH-1 — Spec Revision Notes claims "None for Phase 3" but the plan adds a tool (`kotlin_list_hooks`) that diverges from the spec's `kotlin_run_hooks`; this section must not be empty

**Plan locations:** Spec Revision Notes (lines 1203-1205); Architecture paragraph (line 9); Task 7 (lines 977-1102); CHANGELOG entry (lines 1152-1165).

**Spec says** (line 44 of spec):

> **MCP tools**: `kotlin_bump_version` (mutation; auth required), `kotlin_run_hooks`.

**Plan adds** (Architecture paragraph):

> New MCP tools (`kotlin_bump_version`, `kotlin_list_hooks`)

**Why this is a writing defect, not just a tracking miss:**

1. The two tools have different semantics:
   - `kotlin_run_hooks` (per spec) — implies running the hooks.
   - `kotlin_list_hooks` (per plan, line 1065: `"Return Kotlin/Gradle hook metadata (read-only; no auth)"`) — returns hook metadata only, explicitly read-only.

2. The plan perpetuates a divergence Phase 2 already introduced. The spec line 39 says Swift gets `swift_run_hooks`. Phase 2's writing review did not flag this in Phase 2's review file (`2026-09-07-phase2-writing.md`), which means Phase 2's implementation likely also used `swift_list_hooks` and the divergence went unreviewed. Phase 3 compounds the issue: the plan makes the divergence load-bearing (used in architecture header, CHANGELOG, tests) without amending the spec or recording the deviation.

3. The Spec Revision Notes section explicitly states "None for Phase 3 — the spec Rev 2 already covers Phase 3 adequately" — this is false. The plan makes a SPEC DEVIATION and the section should record it. The "no BLOCKER, HIGH, or MEDIUM findings required spec amendment" assertion is unfounded because the plan was not compared row-by-row against the spec (no Self-Review section exists — see HIGH-4/5).

**Why this matters:**

- Future maintainers will be confused: did the spec author intend `kotlin_list_hooks` or `kotlin_run_hooks`?
- Phase 4 (Web/Jinja) will copy this pattern; without spec amendment, the divergence multiplies.
- A reviewer reading only the spec would expect `kotlin_run_hooks` to execute hooks; the plan ships `kotlin_list_hooks` instead.

**Recommended fix:**

Either (pick one):

1. **Amend the spec** to use `kotlin_list_hooks` (with explicit "lists hook metadata, read-only" semantics) and add to Spec Revision Notes:
   > Spec amended (Phase 3): replaced `kotlin_run_hooks` with `kotlin_list_hooks`. Tool returns hook metadata only (read-only), matching Phase 2's `swift_list_hooks` pattern.

2. **Change the plan** to use `kotlin_run_hooks` and implement actual hook execution. Update Spec Revision Notes:
   > Plan implements `kotlin_list_hooks` (Phase 3 choice); spec retained `kotlin_run_hooks`. To unify with Phase 2, future spec revision should rename Swift/Kotlin tools to `*_list_hooks`.

Either way, Spec Revision Notes must NOT be empty. The current state silently deviates from spec.

---

### HIGH-2 — `_build_hooks` creates an unused `probe = GradleTaskProbe(project_root)` and a comment that claims probing happens but does not; dead code AND a misleading comment

**Plan location:** Task 3 Step 3, `crackerjack/adapters/kotlin/hooks.py` (lines 469-483).

**Plan code (verbatim):**

```python
def _build_hooks(project_root: Path) -> tuple[Hook, ...]:
    probe = GradleTaskProbe(project_root)
    gradlew = ("./gradlew",)

    def hook_with_probe(name: str, *cli_command: str) -> Hook:
        # If probe fails (task absent), the hook still emits; CLI invocation
        # will skip-with-warning at execution time. This matches spec Kotlin F2.
        return Hook(name=name, cli_command=(*gradlew, *cli_command))

    hooks: list[Hook] = [
        hook_with_probe("kotlin.ktlint", "ktlintCheck"),
        hook_with_probe("kotlin.detekt", "detekt"),
        Hook(name="kotlin.test", cli_command=(*gradlew, "test")),
    ]
    return tuple(hooks)
```

**Why this is a writing defect, not just lint noise:**

1. **Dead code:** `probe = GradleTaskProbe(project_root)` is created but never used. Ruff F841 (unused-variable) will flag this. The plan instructs the implementer to ship code that fails lint on day one.

2. **Misleading closure name:** the inner function is named `hook_with_probe` but does not probe. It is just a factory that builds `Hook` objects.

3. **Misleading comment:** "If probe fails (task absent), the hook still emits; CLI invocation will skip-with-warning at execution time" — but:
   - No probe is performed.
   - The "CLI invocation will skip-with-warning at execution time" is asserted but never implemented. The plan doesn't define where the skip-with-warning logic lives. Is it in the CLI runner? In the Hook runner? Where?

4. **Function naming:** the outer function is `_build_hooks` (no probe) but contains a closure named `hook_with_probe`. The naming drift tells the reader something the code does not.

**Why this matters:**

- A new contributor following the plan verbatim will ship code that fails lint (Ruff F841) and contains a comment that doesn't match reality.
- The Phase 2 writing review (MEDIUM-5) flagged the same defect class: "comment says X but code does Y." Phase 3 inherits this defect class.
- The Gradle task probing contract (spec Kotlin F2) is the plan's key Phase 3 differentiation from Phase 2 Swift. If the probe isn't actually performed in `_build_hooks`, the contract is opaque to readers.

**Recommended fix:**

Either:

1. **Drop the unused probe and misleading comment** (simplest):
   ```python
   def _build_hooks(project_root: Path) -> tuple[Hook, ...]:
       gradlew = ("./gradlew",)
       def make_hook(name: str, *cli_command: str) -> Hook:
           return Hook(name=name, cli_command=(*gradlew, *cli_command))
       return (
           make_hook("kotlin.ktlint", "ktlintCheck"),
           make_hook("kotlin.detekt", "detekt"),
           Hook(name="kotlin.test", cli_command=(*gradlew, "test")),
       )
   ```
   Then add a Global Constraint or new step clarifying "Gradle task probing happens in the CLI/Hook runner, not in `_build_hooks`. See `crackerjack.adapters.kotlin.hooks` (TODO: link to runner code in later phase)."

2. **Actually use the probe** to filter missing tasks:
   ```python
   def _build_hooks(project_root: Path) -> tuple[Hook, ...]:
       probe = GradleTaskProbe(project_root)
       gradlew = ("./gradlew",)
       
       def make_hook(name: str, task_name: str) -> Hook:
           if not probe.has_task(task_name):
               logger.warning("Gradle task %s not present; hook %s will skip-with-warning", task_name, name)
           return Hook(name=name, cli_command=(*gradlew, task_name))
       
       return (
           make_hook("kotlin.ktlint", "ktlintCheck"),
           make_hook("kotlin.detekt", "detekt"),
           Hook(name="kotlin.test", cli_command=(*gradlew, "test")),
       )
   ```
   This requires the Hook contract to support a "skip-with-warning" mode (currently absent from spec), so this is a larger change.

Either way, the dead code and misleading comment must be resolved.

---

### HIGH-3 — Module docstrings are absent from `version_source.py`, `hooks.py`, and `__init__.py`; only `git_backend.py` is explicitly required to have one

**Plan locations:**
- Task 2 Step 3 — `version_source.py` (lines 238-328) — no module docstring shown.
- Task 3 Step 3 — `hooks.py` (lines 438-489) — no module docstring shown.
- Task 4 Step 3 — `git_backend.py` (lines 641-647) — explicit instruction "Module docstring: replace 'Swift' with 'Kotlin'".
- Task 5 Step 3 — `lifecycle.py` (lines 821-844) — "Mirror Phase 2's `crackerjack/adapters/swift/lifecycle.py` exactly" — depends on Phase 2 having one.
- Task 6 Step 3 — `__init__.py` (lines 922-954) — no module docstring in the shown code block.

**Why this is a writing defect:**

The plan is INCONSISTENT: it requires a module docstring for one file (`git_backend.py`) but does not require for the other four. A new contributor will pick the pattern from whichever file they implement first.

Looking at the actual code blocks shown in the plan:

`version_source.py` begins:
```python
from __future__ import annotations

import logging
import re
import subprocess
from pathlib import Path

from crackerjack.adapters.base import VersionNotFoundError, VersionSource

logger = logging.getLogger(__name__)


class GradlePropertiesVersionSource:
    """Probe gradle.properties for version, with multiple key conventions.
```

There is no `"""..."""` between the imports and the first class. A new contributor mirrors this and ships a module without a docstring.

`hooks.py` begins:
```python
from __future__ import annotations

import logging
import re
import subprocess
from pathlib import Path

from crackerjack.adapters.base import Hook

logger = logging.getLogger(__name__)


class GradleTaskProbe:
```

Same pattern — no module docstring.

`__init__.py` begins:
```python
from __future__ import annotations

from pathlib import Path

from crackerjack.adapters.base import Capabilities, LanguageAdapterBase
from crackerjack.adapters.kotlin.hooks import kotlin_hooks
from crackerjack.adapters.kotlin.version_source import GradlePropertiesVersionSource

__all__ = ["KotlinAdapter", "gradle_properties_version_source"]


class KotlinAdapter(LanguageAdapterBase):
```

No module docstring.

`lifecycle.py` is "Mirror Phase 2's Swift" — relies on Phase 2 having one. The plan doesn't make this explicit or verify Phase 2 actually has one.

The plan instructs the implementer to "replace Swift with Kotlin" in the git_backend module docstring, but doesn't validate that a module docstring exists in Phase 2 to replace. If Phase 2's `git_backend.py` is itself missing a module docstring, the "replace" instruction is a no-op and the resulting Kotlin file will also lack one.

**Why this matters:**

- Module docstrings are a project convention (Python best practice). The plan should enforce them.
- A new contributor cannot tell from the plan whether module docstrings are required. They will mirror whichever file they read first.
- Phase 2's writing review (LOW-3, "Plan has no 'Out of scope' section") flagged inconsistency issues; this is similar.

**Recommended fix:**

Add a single line to the Global Constraints section:

> **Module docstrings required.** Every new file under `crackerjack/adapters/kotlin/` and `tests/adapters/kotlin/` must begin with a one-paragraph module docstring (after the `from __future__ import annotations` line) describing its purpose. The docstring must appear before any imports.

Or, simpler, inline a 2-3 line module docstring into each code block in Task 2/3/5/6. For example, Task 2 Step 3:

```python
"""Gradle properties-based version source for Kotlin/Gradle projects.

Reads versions from gradle.properties with pluginVersion/projectVersion/version
key probes, falling back to build.gradle.kts scan and `./gradlew properties`
as the Gradle-canonical source of truth. Writes bump the gradle.properties
key that was probed (read-back verified).
"""

from __future__ import annotations

import logging
...
```

---

### HIGH-4 — Plan has no self-review section; this is a regression from Phase 2

**Plan location:** Plan body, end of file. No "Self-Review" or equivalent section.

**Why this is a writing defect:**

Phase 2's plan had a Self-Review section (per Phase 2's writing review, which analyzed 15 rows of spec coverage). Phase 2's writing review (MEDIUM-6) flagged the spec coverage table as incomplete — but at least Phase 2 had a Self-Review to be incomplete.

Phase 3's plan has NO self-review section. A new contributor cannot:
- Verify spec coverage without a checklist.
- Spot spec-vs-plan divergences (like `kotlin_list_hooks` vs spec's `kotlin_run_hooks` — see HIGH-1).
- Confirm out-of-scope items are correctly enumerated.
- Catch the dead `probe` variable (HIGH-2) before the implementer ships it.

The Phase 2 writing review's recommended fix (drop incomplete rows, add explicit gaps) was: "Add three explicit rows to the Spec coverage table." Phase 3 has zero rows.

**Why this matters:**

- A self-review is the author's chance to catch their own defects before the implementer does. Phase 3 skips this step.
- The cross-adapter `_bump` divergence is documented in the plan body but not surfaced in a Self-Review checklist.
- The "Phase 2 BLOCKER B1-equivalent" reference (see LOW-4) would be more visible in a Self-Review.

**Recommended fix:**

Add a Self-Review section before "Spec Revision Notes":

```
## Self-Review

| Spec item | Plan coverage | Status |
|---|---|---|
| Per-adapter Kotlin: Detect via build.gradle(.kts) | Task 6 Step 3 | ✓ |
| Per-adapter Kotlin: VersionSource gradle.properties probe | Task 2 Step 3 | ✓ |
| Per-adapter Kotlin: Hooks with task probing | Task 3 Step 3 | ✓ (probe code itself is incomplete — see writing review HIGH-2) |
| Per-adapter Kotlin: All Gradle invocations pass --no-daemon --no-configuration-cache | Tasks 2, 3 | ✓ |
| Per-adapter Kotlin: Lifecycle bumps gradle.properties | Task 5 Step 3 | ✓ |
| MCP kotlin_bump_version (mutation; auth required) | Task 7 Step 3 | ✓ |
| MCP kotlin_run_hooks (spec tool) | Plan implements kotlin_list_hooks | ✗ DEVIATION — see writing review HIGH-1 |
| `crackerjack.language_adapters` entry-point registration | Task 1 | ✓ |

Out-of-scope verification:
- Web/Jinja — out of scope (Phase 4)
- Rust/Go — out of scope
- PyCharm parity — out of scope (Phase 4)
- JetBrains Marketplace publishing — out of scope
```

This forces the author to enumerate spec coverage and reveals the divergence in HIGH-1.

---

### HIGH-5 — Plan has no spec coverage table (regression from Phase 2)

**Plan location:** Plan body — no spec coverage table anywhere.

**Why this is a writing defect:**

Phase 2's writing review (MEDIUM-6) flagged the absence of three rows from the spec coverage table. Phase 3 has zero rows — the entire table is missing.

Without a spec coverage table, a reviewer (or implementer) cannot quickly verify:
- Each spec item is addressed by at least one task.
- No spec item is silently dropped.
- Deviations from spec are explicit (see HIGH-1 above).

**Recommended fix:**

Fold into the Self-Review section (see HIGH-4). One table; no duplication.

---

### MEDIUM-1 — Cross-adapter `_bump` divergence is documented inline but no ADR is proposed, queued, or stubbed

**Plan location:** Task 5 Sub-task 5.1 docstring (lines 678-685); "Cross-adapter `_bump` divergence" section (lines 1209-1220).

**Why this is a writing defect:**

The plan documents the divergence well:
- `_bump` docstring mentions Swift's pre-1.0 semantics ✓
- Cross-adapter section enumerates the three adapters and their semantics ✓
- Notes that Phase 3 picks (b) implicitly ✓

But:

- No ADR is created.
- No ADR draft is provided in the plan body.
- No TODO is filed for one.
- The plan says "ADR recommended before Phase 4" — but doesn't even include a stub ADR file path or checklist item.

The Phase 2 final review (CF-3) explicitly recommended considering (a) or (b). The plan picks (b) — but doesn't RECORD the choice as a documented architectural decision. Phase 4 (Web/Jinja) will face the same question; if no ADR exists, Phase 4's implementer will re-litigate.

**Recommended fix:**

Add a deliverable to the plan:

> **ADR deliverable (Phase 3):** Create `docs/adr/00XX-cross-adapter-bump-semantics.md` recording the per-adapter bump semantics (Python real semver, Swift pre-1.0, Kotlin real semver), the Phase 2 final review CF-3 precedent, and the Phase 3 (b) implicit choice. Required before Phase 4 lands.

Or include the ADR stub in the plan body under a new "Architectural decisions" section.

---

### MEDIUM-2 — Plan references Phase 2 by short-hand (`Phase 2 BLOCKER B2`, `Phase 2 ruling 7`, `Phase 2 final-review CF-3`, `Phase 2 commit b2199190`) without inlining the relevant lesson

**Plan locations:** Global Constraints block (lines 38-50); Task 5 Step 3 (line 828); Task 6 Step 3 (line 948).

**Examples:**

- "Phase 2 BLOCKER B2" — Global Constraints line 38: "Per Phase 2 BLOCKER B2, registration lives in `profiles.py`."
- "Phase 2 ruling 7" — Global Constraints line 39: "Per-invocation check (not startup-only — Phase 2 ruling 7 carries forward)."
- "Phase 2 final-review CF-3" — Global Constraints line 50: "per Phase 2 final review CF-3".
- "Phase 2 commit b2199190" — Global Constraints lines 51-52: "per Phase 2 fix in commit `b2199190`".
- "Phase 2 final-review CF-2" — Task 6 Step 3 line 948: "per Phase 2 final-review CF-2 fix".
- "Phase 2 BLOCKER B1-equivalent pre-flight check" — Task 4 line 523.

**Why this is a writing defect:**

A new contributor without Phase 2's plan in hand has to reverse-engineer:
- What was BLOCKER B2? (The plan says "registration lives in `profiles.py`" — but doesn't say WHY.)
- What was ruling 7? (The plan says "per-invocation check" — but doesn't say WHY startup-only is wrong.)
- What was CF-3? (The cross-adapter divergence — but see MEDIUM-1.)
- What was in commit `b2199190`? (The plan says it fixed git tag ordering — but doesn't say what the bug was.)

Phase 2's writing review (MEDIUM-1) flagged this exact issue. Phase 3 inherits it.

**Recommended fix:**

Inline 3-5 lines per reference. For BLOCKER B2 (Global Constraints line 38):

> **Why registration lives in `profiles.py` (Phase 2 BLOCKER B2):** Phase 1 initially put MCP tool registration in `crackerjack/mcp/server_core.py:204-224`. Phase 2's review surfaced that profile-gating logic lives in `crackerjack/mcp/tools/profiles.py`, so registration must be co-located there. If you add a new tool group, register in `profiles.py`, NOT `server_core.py`.

For ruling 7 (Global Constraints line 39):

> **Why auth is per-invocation (Phase 2 ruling 7):** Startup-only checks fail in test environments where env vars are set after server start. The per-invocation check reads `MAHAVISHNU_AUTH_ENABLED` and `MAHAVISHNU_JWT_SECRET` on every mutation call, raising `PermissionError` if absent.

For commit `b2199190` (Global Constraints lines 51-52):

> **Why `git tag -a -m M -- N` ordering (Phase 2 commit b2199190):** Earlier ordering `git tag -a N -m M` caused `git` to misinterpret the message as the tag name. The fix is `-a` first, then `-m message`, then `--`, then positional tag name: `["git", "tag", "-a", "-m", message, "--", tag_name]`.

This adds ~30 lines but eliminates "what was that?" questions.

---

### MEDIUM-3 — `lifecycle.py` and `git_backend.py` implementations are not shown in the plan; the plan says "Mirror Phase 2" without reproducing the source

**Plan locations:**
- Task 4 Step 3 (lines 641-647) — "The implementations are IDENTICAL to Phase 2's `crackerjack/adapters/swift/git_backend.py` (verified at `crackerjack/adapters/swift/git_backend.py` lines 27-158). Copy verbatim..."
- Task 5 Step 3 (lines 821-844) — "Mirror Phase 2's `crackerjack/adapters/swift/lifecycle.py` exactly, with these changes:..."

**Why this is a writing defect:**

A new contributor implementing Phase 3 must:
1. Find Phase 2's source files (the plan names them, but doesn't show contents).
2. Read and understand them.
3. Apply the listed changes.

The plan shows:
- Task 4 has 9 tests (full code) — but NOT the implementation.
- Task 5 has 11 tests (full code) — but NOT the implementation.

Tests verify behavior; the implementation is the body. Showing only tests is half the plan.

A plan should be self-contained. Phase 2's plan had the full source code for both `git_backend.py` and `lifecycle.py` (per Phase 2's writing review, which analyzed the full implementation). Phase 3 assumes Phase 2's source is at hand.

This is the same defect Phase 2's writing review (HIGH-2) flagged in a different form: "delegates the real implementation to 'Phase 2 should call into crackerjack/services/git.py' without verifying that file exists." Phase 3 makes a similar assumption (Phase 2's git_backend.py exists and is correct) without verification.

**Recommended fix:**

Either:

1. Reproduce the source code in the plan (Phase 2's approach). Add the full `git_backend.py` (132 lines) and `lifecycle.py` (with the `_bump` change) to Task 4 and Task 5 respectively.

2. Add a clear cross-reference with a pre-flight check:
   > **Pre-flight (mirror Phase 2 BLOCKER B1):** Read `crackerjack/adapters/swift/git_backend.py` and confirm it implements the 6 functions (`commit`, `tag`, `push`, `delete_tag`, `reset`, `gh_release`) with the Phase 2 commit `b2199190` fix. If Phase 2's source is missing or doesn't match, escalate BEFORE implementing Task 4.

Option 1 is more self-contained. Option 2 is more concise but requires Phase 2 source to be at hand.

---

### MEDIUM-4 — `gradle_properties_version_source` factory is exported in `__all__` but never used anywhere in the plan

**Plan locations:** Task 2 Step 3 (lines 320-327); Task 6 Step 3 (line 931: `__all__ = ["KotlinAdapter", "gradle_properties_version_source"]`).

**Plan code (factory, verbatim):**

```python
def gradle_properties_version_source(project_root: Path) -> VersionSource:
    """Factory matching the Phase 1 VersionSource Protocol shape.

    Returns the underlying object typed as VersionSource; concrete class is
    `GradlePropertiesVersionSource`. Use this factory for parity with
    `git_tag_version_source()` (Phase 2).
    """
    return GradlePropertiesVersionSource(project_root)
```

**Plan usage:**

- Task 6 Step 3: `from crackerjack.adapters.kotlin.version_source import GradlePropertiesVersionSource` — direct class import.
- Task 7 Step 3: `from crackerjack.adapters.kotlin.version_source import GradlePropertiesVersionSource` — direct class import.

**Why this is a writing defect:**

The factory is exported (`__all__ = [..., "gradle_properties_version_source"]`) but no module imports it. This is dead export.

The docstring says "Use this factory for parity with `git_tag_version_source()` (Phase 2)" — but the plan doesn't USE it. The parity claim is unfounded; if Phase 2's `git_tag_version_source()` is similarly unused, both are dead code.

A new contributor will either:
1. Ship the factory unused (Ruff F401, dead export).
2. Add usage of the factory throughout (more code churn than planned).

**Recommended fix:**

Either:

1. **Use the factory consistently.** Replace direct class construction with the factory:
   ```python
   # Task 6 Step 3
   from crackerjack.adapters.kotlin.version_source import gradle_properties_version_source
   version_source = gradle_properties_version_source(project_root)
   
   # Task 7 Step 3
   version_source = gradle_properties_version_source(root)
   ```

2. **Drop the factory from `__all__`** and document that the class is used directly. Remove `gradle_properties_version_source` from `__init__.py` exports.

The current state has it exported but unused — a contradiction the plan should resolve.

---

### MEDIUM-5 — Task 7 Step 4 hedging language suggests uncertainty about whether code change is needed

**Plan location:** Task 7 Step 4 (line 1086).

**Plan text (verbatim):**

> In the existing test helper (Phase 2 introduced `_register()`), ensure it discovers both new tools. No code change likely needed (the helper iterates `tools` dict), but verify by running tests.

**Why this is a writing defect:**

"No code change likely needed" — this is hedging. The plan should commit:
- Either: "No code change needed. The helper iterates `tools` dict, so new tools are auto-discovered."
- Or: "Update `_register()` to ensure new tools are discovered."

The current "likely needed but verify" leaves the implementer guessing. If the helper does need a change (e.g., to register tools under a specific name), the implementer will waste time discovering this. If it doesn't need a change, the implementer will worry about whether they missed something.

**Recommended fix:**

Replace with a definite statement:

> No change needed in the existing test helper (`_register()` introduced by Phase 2). The helper iterates the `tools` dict, so new tools added to `language_tools.register_language_tools` are auto-discovered. Verification: Task 7 Step 5 expects "All tests pass (existing 7 swift + 2 new kotlin = 9 minimum)."

---

### MEDIUM-6 — `GradlePropertiesVersionSource.write()` raises `FileNotFoundError` for missing gradle.properties instead of the spec's `VersionWriteError`; the design choice is undocumented

**Plan location:** Task 2 Step 3 (lines 293-298).

**Plan code (verbatim):**

```python
def write(self, new_version: str) -> None:
    properties_path = self._project_root / "gradle.properties"
    if not properties_path.exists():
        raise FileNotFoundError(
            f"gradle.properties not found at {properties_path}; cannot write version"
        )
    ...
```

**Spec says** (lines 198-204):

```python
class VersionSource(Protocol):
    def write(self, new_version: str) -> None:
        """Write a new version. Raise VersionWriteError on failure.

        Implementations MUST verify by reading back after writing.
        """
```

**Why this is a writing defect:**

The spec defines `VersionWriteError` for "failure" — but the implementation raises `FileNotFoundError` for missing file (a precondition failure). The plan doesn't explain the choice:

- Is `FileNotFoundError` correct because the file is missing (precondition failure, not write failure)?
- Or should `VersionWriteError` be raised for consistency with the rest of the write path?

A user catching `VersionWriteError` won't catch this case. The plan should document the design.

Looking at the implementation more carefully: the second raise (for read-back verification failure, lines 313-317) DOES use `VersionWriteError`. So the design is: precondition failures raise `FileNotFoundError`, write-side failures raise `VersionWriteError`. This is a reasonable distinction — but it's not stated.

**Recommended fix:**

Add a `write()` docstring (the spec defines a Protocol with a docstring; the implementation should mirror):

```python
def write(self, new_version: str) -> None:
    """Write new_version to gradle.properties.

    Raises:
        FileNotFoundError: if gradle.properties does not exist at the
            expected location (precondition failure, distinct from write
            failure).
        VersionWriteError: if the read-back verification fails (write
            completed but file contents did not match).
    """
    properties_path = self._project_root / "gradle.properties"
    if not properties_path.exists():
        raise FileNotFoundError(
            f"gradle.properties not found at {properties_path}; cannot write version"
        )
    ...
```

Or change to `VersionWriteError` and document the alternative design.

---

### MEDIUM-7 — `_bump` docstring has trailing whitespace after the first line and the prose/blank-line ratio is unidiomatic

**Plan location:** Task 5 Sub-task 5.1 (lines 678-685).

**Plan code (verbatim):**

```python
def _bump(version: str, level: str) -> str:
    """Real-semver bump: major/minor/patch each bump the named component.
    
    Cross-adapter divergence: SwiftLifecycle._bump uses pre-1.0 semantics
    (major bumps minor) per its docstring. Kotlin uses real semver, matching
    PythonLifecycle._bump. See docs/superpowers/specs/2026-09-07-crackerjack-
    multi-language-design.md for the cross-cutting Phase 2.5 follow-up (CF-3).
    """
```

**Why this is a writing defect:**

1. **Trailing whitespace on line 2.** After the first summary line, there is a blank line with trailing whitespace (spaces after the newline). Ruff W293 will flag this.
2. **Idiomatic docstring structure** typically puts the summary on one line, then a blank line, then detailed explanation. The current format is correct in structure but the trailing whitespace on the blank line is wrong.
3. **The summary line** says "major/minor/patch each bump the named component" — but technically `patch` does NOT bump `major` or `minor`; it bumps only `patch`. The phrase is technically true (each level bumps its named component) but could be misread as "all three levels bump all three components." This is a minor ambiguity.

**Recommended fix:**

```python
def _bump(version: str, level: str) -> str:
    """Real-semver bump: each level bumps the named component (and zeros lower).

    Cross-adapter divergence: SwiftLifecycle._bump uses pre-1.0 semantics
    (major bumps minor) per its docstring. Kotlin uses real semver, matching
    PythonLifecycle._bump. See docs/superpowers/specs/2026-09-07-crackerjack-
    multi-language-design.md for the cross-cutting Phase 2.5 follow-up (CF-3).
    """
```

(No trailing whitespace on the blank line; clearer summary.)

---

### LOW-1 — Acronyms `MCP`, `FastMCP` are used without expansion

**Plan location:** Tech Stack (line 11); throughout plan body.

**Plan text (Tech Stack, line 11):**

> **Tech Stack:** Python 3.14, FastMCP 4.x, typer 0.26+, hatchling, Git CLI (via subprocess), Gradle CLI (`./gradlew`, subprocess invocation, no shell), gh CLI for GitHub release creation.

**Why this is a writing defect:**

Phase 2's writing review (MEDIUM-8) flagged this. Phase 3 inherits it:
- `FastMCP` — Python MCP server framework (not expanded)
- `MCP` — Model Context Protocol (used without expansion throughout)
- `gradle` — Gradle build tool (used without expansion in some places)

Crackerjack's audience likely knows these, but the plan should expand them once on first use for newcomers and reviewers.

**Recommended fix:**

Expand on first use in Tech Stack:

> **Tech Stack:** Python 3.14, FastMCP 4.x (the FastMCP framework for building MCP servers), typer 0.26+ (CLI framework), hatchling (Python build backend), Git CLI (via subprocess), Gradle CLI (`./gradlew`, subprocess invocation, no shell), gh CLI (GitHub's official CLI) for GitHub release creation.

---

### LOW-2 — Plan references `_gradle_helpers.py::init_git_repo` but doesn't reproduce the function or its signature

**Plan location:** Task 4 Step 1 test code (lines 540-541); Task 4 Sub-task 4.2 (line 521).

**Plan text (Sub-task 4.2):**

> Implement `tests/adapters/kotlin/_gradle_helpers.py` mirroring Phase 2's `tests/adapters/swift/_git_helpers.py::init_git_repo`.

**Why this is a writing defect:**

The plan references `init_git_repo` from Phase 2 but doesn't show its signature or contents. A new contributor must:
1. Find Phase 2's `_git_helpers.py`.
2. Read it.
3. Implement the Kotlin equivalent.

The plan should either reproduce the signature or note where to find it explicitly. Currently the reference is a parenthetical hint, easy to miss.

**Recommended fix:**

Show the helper's expected signature:

```python
# tests/adapters/kotlin/_gradle_helpers.py
def init_git_repo(path: Path, *, author: str = "Test <test@example.com>") -> None:
    """Initialize a git repository at `path` for testing.

    Creates .git/, sets user.email/user.name, makes an initial commit
    on main branch. Mirrors Phase 2's tests/adapters/swift/_git_helpers.py.
    """
```

---

### LOW-3 — Plan header references "9-lens multi-agent review" but doesn't list the 9 lenses (and the spec says 11, not 9)

**Plan location:** Plan header (line 15).

**Plan text:**

> **Reviews:** None yet. Phase 3 plan should be reviewed via 9-lens multi-agent review before execution (mirror Phase 2's review process).

**Why this is a writing defect:**

The plan says "9-lens" but:
- Doesn't enumerate the lenses.
- The spec actually mentions "11-agent-review" (spec line 3, "post-11-agent-review").
- The actual reviews directory has files like `phase3-a11y`, `phase3-api`, `phase3-kotlin`, `phase3-mcp`, `phase3-security`, `phase3-simplification`, `phase3-testing`, `phase3-writing` — that's 8 lens files visible, not 9 or 11.

A new contributor / reviewer doesn't know which lenses are expected.

**Recommended fix:**

Either:

1. List the lenses:
   > Phase 3 review lenses (mirror Phase 2): a11y, api, mcp, security, simplification, testing, writing, kotlin. (8 lenses; spec mentions "11-agent-review" for the original spec review, but the per-phase lens set is smaller.)

2. OR drop the count:
   > Phase 3 plan should be reviewed via multi-agent review before execution (see spec review directory for lens list).

---

### LOW-4 — Plan references `Phase 2 BLOCKER B1-equivalent pre-flight check` without explaining what B1 was

**Plan location:** Task 4 (lines 523-524).

**Plan text (verbatim):**

> **Phase 2 BLOCKER B1-equivalent pre-flight check**: verify `git tag -a` accepts the message flag before `-m message` and the tag name after `--` (per Phase 2 fix in commit `b2199190`).

**Why this is a writing defect:**

A new contributor doesn't know what BLOCKER B1 was. The parenthetical says it's "per Phase 2 fix in commit b2199190" but doesn't summarize what was fixed. (See MEDIUM-2 for the broader Phase 2 short-hand issue.)

**Recommended fix:**

Inline the lesson:

> **Pre-flight check** (mirrors Phase 2 BLOCKER B1; Phase 2 fix in commit `b2199190`): verify `git tag -a` accepts the message flag before `-m message` and the tag name after `--`. Earlier ordering caused `git` to misinterpret the message as the tag name. The fix: `["git", "tag", "-a", "-m", message, "--", tag_name]`.

---

### LOW-5 — Task 6's `__init__.py` import of `make_git_backend` is lint-silenced via `_ = X` rather than the standard `# noqa: F401`

**Plan location:** Task 6 Step 3 (lines 942-948).

**Plan code (verbatim):**

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

**Why this is a writing defect:**

1. The inline import (`from ... import make_git_backend`) inside a method is unusual style.
2. The `_ = make_git_backend` idiom is non-standard; `# noqa: F401` is the Python convention.
3. The comment references Phase 2's CF-2 fix without explaining what CF-2 was (see MEDIUM-2).
4. The variable name `_` doesn't communicate intent; `# noqa: F401  # used by MCP layer` does.

**Recommended fix:**

Move the import to module level and use standard lint silencing:

```python
# crackerjack/adapters/kotlin/__init__.py
from __future__ import annotations

from pathlib import Path

from crackerjack.adapters.base import Capabilities, LanguageAdapterBase
from crackerjack.adapters.kotlin.hooks import kotlin_hooks
from crackerjack.adapters.kotlin.version_source import GradlePropertiesVersionSource
# make_git_backend is used by `mcp/tools/language_tools.py` to construct
# the lifecycle factory. Imported here for parity with Phase 2's Swift.
from crackerjack.adapters.kotlin.git_backend import make_git_backend  # noqa: F401

__all__ = ["KotlinAdapter", "gradle_properties_version_source"]


class KotlinAdapter(LanguageAdapterBase):
    """Kotlin/Gradle language adapter — activates on build.gradle(.kts) presence."""

    name: str = "kotlin"

    def detect(self, project_root: Path) -> bool:
        return (project_root / "build.gradle.kts").is_file() or (project_root / "build.gradle").is_file()

    def capabilities(self, project_root: Path) -> Capabilities:
        version_source = GradlePropertiesVersionSource(project_root)
        return Capabilities(
            version_source=version_source,
            hooks=kotlin_hooks(project_root),
            has_lifecycle=True,
        )
```

---

### LOW-6 — Task 2 commit message says "reads from gradle.properties" but the implementation also has `write()`

**Plan location:** Task 2 Step 5 commit message (line 342).

**Plan text:**

```bash
git commit -m "feat(adapters.kotlin): GradlePropertiesVersionSource reads from gradle.properties"
```

**Why this is a writing defect:**

The commit message says "reads from" but the implementation in Step 3 includes both `read()` and `write()`. The commit message is incomplete and would mislead `git log --grep` searches for the write implementation.

**Recommended fix:**

```bash
git commit -m "feat(adapters.kotlin): GradlePropertiesVersionSource reads and writes gradle.properties"
```

---

### LOW-7 — CHANGELOG entry doesn't mention the new `gradle-vanilla/` fixture

**Plan location:** Task 8.2 CHANGELOG entry (lines 1152-1165).

**Plan text (CHANGELOG entry):**

The entry covers: GradlePropertiesVersionSource, hooks, MCP tools, entry-point registration. It does NOT mention `tests/fixtures/gradle-vanilla/` (a real Kotlin lib fixture committed in Task 8.7).

**Why this is a writing defect:**

The fixture is a meaningful deliverable (smoke testing requires it), but a maintainer reading the CHANGELOG won't know the fixture exists. Phase 5 (polish) or future reviewers won't see it documented.

**Recommended fix:**

Append to the CHANGELOG entry:

> Added `tests/fixtures/gradle-vanilla/` — a real Kotlin/Gradle library fixture (kotlin("jvm") plugin, trivial `Hello.kt` source) for end-to-end smoke testing.

---

### LOW-8 — Task 7 tests mix `async def` with `asyncio.run` inside the body — a code-smell pattern

**Plan location:** Task 7 Step 1 test code (lines 996-1016).

**Plan code (verbatim, both tests):**

```python
async def test_kotlin_list_hooks_returns_three_hook_names(tmp_path: Path) -> None:
    from crackerjack.adapters.kotlin import KotlinAdapter
    (tmp_path / "build.gradle.kts").write_text("")
    with mock.patch.dict(os.environ, {"MAHAVISHNU_PROJECT_ROOTS": str(tmp_path)}, clear=False):
        _, tools = asyncio.run(_register())
        tool = tools["kotlin_list_hooks"]
        result = asyncio.run(tool.fn(project_root=str(tmp_path)))
    assert isinstance(result, dict)
    names = set(result.keys())
    assert "kotlin.ktlint" in names
    assert "kotlin.detekt" in names
    assert "kotlin.test" in names


async def test_kotlin_bump_version_requires_auth() -> None:
    with mock.patch.dict(os.environ, {}, clear=True):
        _, tools = asyncio.run(_register())
        tool = tools["kotlin_bump_version"]
        with pytest.raises(PermissionError):
            asyncio.run(tool.fn(level="minor", project_root="/tmp/nonexistent"))
```

**Why this is a writing defect:**

The tests are declared `async def` but use `asyncio.run()` inside the body. This is contradictory:

- If `_register()` is async, you should `await` it (don't use `asyncio.run`).
- If `_register()` is sync, the test should be `def` not `async def` (and `asyncio.run` for the tool call is fine).

The current pattern indicates either:
- The author was unsure whether `_register()` is sync or async, and defaulted to `asyncio.run` to handle either.
- The test framework doesn't natively support `async def` here (e.g., the file uses `pytest-asyncio` in `mode=strict`, requiring explicit `@pytest.mark.asyncio`).

This is the same defect class Phase 2's writing review (MEDIUM-4) flagged: tests reaching into private API. Here, the test reaches into sync/async semantics ambiguously.

**Recommended fix:**

Either:

1. Make the tests sync (`def`) since the helper is sync:
   ```python
   def test_kotlin_list_hooks_returns_three_hook_names(tmp_path: Path) -> None:
       (tmp_path / "build.gradle.kts").write_text("")
       with mock.patch.dict(os.environ, {"MAHAVISHNU_PROJECT_ROOTS": str(tmp_path)}, clear=False):
           _, tools = _register()
           tool = tools["kotlin_list_hooks"]
           result = asyncio.run(tool.fn(project_root=str(tmp_path)))
       assert "kotlin.ktlint" in result
       ...
   ```

2. Or make the helper and tool calls all async with proper `await`:
   ```python
   async def test_kotlin_list_hooks_returns_three_hook_names(tmp_path: Path) -> None:
       (tmp_path / "build.gradle.kts").write_text("")
       with mock.patch.dict(os.environ, {"MAHAVISHNU_PROJECT_ROOTS": str(tmp_path)}, clear=False):
           _, tools = await _register()
           tool = tools["kotlin_list_hooks"]
           result = await tool.fn(project_root=str(tmp_path))
       ...
   ```

---

## Spec Coverage Summary

| Spec item | Plan coverage | Status |
|---|---|---|
| Per-adapter Kotlin: Detect via build.gradle(.kts) | Task 6 Step 3 | ✓ |
| Per-adapter Kotlin: VersionSource gradle.properties probe order | Task 2 Step 3 | ✓ |
| Per-adapter Kotlin: build.gradle.kts fallback | Task 2 Step 3 | ✓ |
| Per-adapter Kotlin: `./gradlew properties` source of truth | Task 2 Step 3 | ✓ |
| Per-adapter Kotlin: Hooks with task probing | Task 3 Step 3 | ✓ (probe code itself is incomplete — see HIGH-2) |
| Per-adapter Kotlin: All Gradle invocations pass `--no-daemon --no-configuration-cache` | Tasks 2, 3 | ✓ |
| Per-adapter Kotlin: Lifecycle bumps gradle.properties | Task 5 Step 3 | ✓ |
| Per-adapter Kotlin: Real-semver `_bump` semantics | Task 5 Sub-task 5.1 | ✓ |
| MCP `kotlin_bump_version` (mutation; auth required) | Task 7 Step 3 | ✓ |
| MCP `kotlin_run_hooks` (spec tool) | Plan implements `kotlin_list_hooks` | **✗ DEVIATION** — see HIGH-1 |
| `crackerjack.language_adapters` entry-point registration | Task 1 | ✓ |
| Auth posture for mutation tools (per-invocation check) | Task 7 Step 3 | ✓ |
| Spec Revision Notes | Empty ("None for Phase 3") | **✗ WRONG** — see HIGH-1 |
| Module docstrings on every new file | `git_backend.py` only | **✗ INCOMPLETE** — see HIGH-3 |
| Plan self-review | Absent (regression) | **✗ MISSING** — see HIGH-4 |
| Spec coverage table | Absent (regression) | **✗ MISSING** — see HIGH-5 |

**Spec deviations found: 1 confirmed (`kotlin_list_hooks` vs spec's `kotlin_run_hooks`).**

**Plan defects (non-spec): 5 (HIGH-2, HIGH-3, HIGH-4, HIGH-5, plus several MEDIUM).**

---

## Plan Quality Verdict

**The plan is broadly well-structured.** A competent Kotlin/Gradle developer with crackerjack context could implement ~80% of it without further help.

**What the plan does well (writing lens):**

1. **TDD structure is consistent.** Every task has explicit "write failing tests → run → implement → run → commit" steps. New contributors can follow the rhythm.
2. **CHANGELOG entry uses correct spelling.** `crackerjack.language_adapters` is correct (no `crackageck` typo from Phase 2 HIGH H12). The entry mentions the cross-adapter `_bump` divergence, the three hook names with their CLI commands, and the entry-point group.
3. **Test code blocks are mostly complete.** Tasks 2-6 show full test code (40+ tests). The TDD discipline is applied consistently.
4. **Naming is consistent.** `KotlinAdapter`, `KotlinLifecycle`, `GradlePropertiesVersionSource`, `GradleTaskProbe`, `kotlin_hooks`, `gradle_properties_version_source`, `make_git_backend`, `KotlinAdapter.name = "kotlin"` — all consistent across tasks.
5. **Global Constraints block consolidates the lessons** from Phase 1/2 (auth posture, no assert in production, argv list no shell, async I/O, module-docstring-implicit-from-Phase-2). It references Phase 2 fix commits by hash, which aids cross-referencing.
6. **Cross-adapter `_bump` divergence is documented** inline in the docstring AND in a dedicated section at the plan's end. The semantics are explicit: real-semver for Kotlin, pre-1.0 for Swift.
7. **Spec invariants are pinned.** `--no-daemon --no-configuration-cache` for all Gradle invocations is repeated in Tasks 2 and 3. Per-invocation auth check is pinned. `_bump` semantics are pinned in Task 5.
8. **Constructor injection replaces Phase 2's monkey-patching.** Phase 2's writing review flagged `lifecycle._commit = _commit  # type: ignore[method-assign]`. Phase 3 avoids this by injecting the 6 git/gh methods as `Callable` constructor parameters (Global Constraints line 44). This is a clear improvement.
9. **Commit messages are traceable.** Each task ends with a `git commit -m` with a specific prefix (`feat(adapters.kotlin):`, `feat(mcp):`, `docs(changelog):`).
10. **`crackerjack.language_adapters` entry-point spelling is correct** — no `crackageck` typo carried from Phase 2 HIGH H12.

**What the plan does less well (writing lens):**

1. **HIGH-1: Empty Spec Revision Notes despite a real spec divergence** (`kotlin_list_hooks` vs spec's `kotlin_run_hooks`). The plan silently deviates.
2. **HIGH-2: Dead `probe` variable and misleading "with_probe" comment** in `_build_hooks`. Code claims to probe but doesn't. Lint will fail.
3. **HIGH-3: Module docstrings absent** from 4 of 5 new files. Only `git_backend.py` is explicitly required.
4. **HIGH-4/5: No self-review section, no spec coverage table** (regression from Phase 2).
5. **MEDIUM-1: Cross-adapter `_bump` divergence documented but no ADR** — Phase 4 will re-litigate.
6. **MEDIUM-2: Phase 2 short-hand references not inlined.** Same defect Phase 2's writing review flagged; Phase 3 inherits.
7. **MEDIUM-3: `lifecycle.py` and `git_backend.py` implementations not reproduced.** Phase 2's plan had full source; Phase 3 has only "Mirror".
8. **MEDIUM-4: `gradle_properties_version_source` factory exported but unused.** Dead export.
9. **MEDIUM-5: Task 7 Step 4 hedging language** ("No code change likely needed").
10. **MEDIUM-6: `write()` raises `FileNotFoundError` instead of `VersionWriteError`** for missing file; design choice undocumented.
11. **LOW-1: Acronyms `MCP`, `FastMCP` not expanded** (Phase 2's MEDIUM-8 not addressed).
12. **LOW-7: CHANGELOG entry doesn't mention `gradle-vanilla/` fixture.**
13. **LOW-8: Task 7 tests mix `async def` with `asyncio.run`** — code smell.

**Reviewer recommendations (priority order):**

1. **(HIGH)** Update Spec Revision Notes to record the `kotlin_list_hooks` deviation and the choice (HIGH-1).
2. **(HIGH)** Drop the unused `probe = GradleTaskProbe(...)` line and misleading comment in `_build_hooks` (HIGH-2).
3. **(HIGH)** Add explicit module-docstring requirements to `version_source.py`, `hooks.py`, `__init__.py`, and `lifecycle.py` (HIGH-3).
4. **(HIGH)** Add a Self-Review section with spec coverage table (HIGH-4, HIGH-5).
5. **(MEDIUM)** Create or stub an ADR for cross-adapter `_bump` semantics before Phase 4 lands (MEDIUM-1).
6. **(MEDIUM)** Inline 3-5 lines per Phase 2 short-hand reference so the plan is self-contained (MEDIUM-2).
7. **(MEDIUM)** Reproduce the full `git_backend.py` and `lifecycle.py` source in Task 4 and Task 5, or add an explicit pre-flight check that Phase 2 source exists (MEDIUM-3).
8. **(MEDIUM)** Either use `gradle_properties_version_source` factory consistently OR drop it from `__all__` (MEDIUM-4).
9. **(MEDIUM)** Replace Task 7 Step 4 hedging language with a definite statement (MEDIUM-5).
10. **(MEDIUM)** Add a `write()` docstring documenting the `FileNotFoundError` vs `VersionWriteError` distinction (MEDIUM-6).
11. **(LOW)** Expand Tech Stack acronyms (LOW-1).
12. **(LOW)** Show `_gradle_helpers.py::init_git_repo` signature (LOW-2).
13. **(LOW)** List the review lenses or drop the count claim (LOW-3).
14. **(LOW)** Inline the BLOCKER B1 lesson (LOW-4).
15. **(LOW)** Move `make_git_backend` import to module level with `# noqa: F401` (LOW-5).
16. **(LOW)** Update Task 2 commit message to say "reads and writes" (LOW-6).
17. **(LOW)** Add `gradle-vanilla/` fixture to CHANGELOG entry (LOW-7).
18. **(LOW)** Resolve the `async def` + `asyncio.run` ambiguity in Task 7 tests (LOW-8).

---

## Summary

The plan is **broadly well-structured** and applies Phase 2 lessons correctly (constructor injection over monkey-patching, `os.environ.get(...) == "true"` exact match, real `subprocess.run` in `git_backend.py`, no fabricated `_gh_release` fallback URL). The CHANGELOG entry uses correct spelling and is complete-but-concise. Naming is consistent.

The 5 HIGH-severity findings cluster around three categories: documentation completeness (HIGH-3, HIGH-4, HIGH-5), comment accuracy (HIGH-2), and spec adherence (HIGH-1). None are show-stoppers individually, but together they represent a regression in writing quality from Phase 2. Phase 2's writing review flagged "Phase 1 lessons referenced by short-hand," "spec coverage table incomplete," "module docstrings absent" — Phase 3 inherits these issues and adds new ones (`kotlin_list_hooks` divergence, dead `probe` variable).

The most actionable improvements are:

1. **Add the missing Spec Revision Notes entry** for `kotlin_list_hooks` (HIGH-1). This is a 5-minute fix that prevents the deviation from silently propagating to Phase 4.
2. **Drop the dead `probe = GradleTaskProbe(...)` line** (HIGH-2). A 2-line removal that prevents a Ruff F841 lint failure on day one.
3. **Add a one-line "Module docstrings required" rule** to Global Constraints (HIGH-3). One line; eliminates ambiguity for all 5 new files.
4. **Add a Self-Review section with spec coverage table** (HIGH-4, HIGH-5). 20-30 lines that catch the divergences a reviewer would catch.

The MEDIUM and LOW findings are polish and can be filed as Phase 3 ledger entries for a future polish pass.

**Recommended action before implementation begins:** Address HIGH-1, HIGH-2, HIGH-3, HIGH-4, and HIGH-5. The MEDIUM and LOW findings can be deferred.

---

## Status

**REVIEW_COMPLETE** — review file written. Plan implementation can proceed with the recommended HIGH-severity fixes tracked in a Phase 3 ledger entry before Task 3 begins.
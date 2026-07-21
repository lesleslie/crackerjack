---
status: active
role: implementation
topic: lifecycle
date: 2026-07-17
last_reviewed: 2026-07-17
superseded_by: null
blocks_on: []
---

# ty-ratchet pipeline cleanup (E.3 + missing-dir) Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Replace the negative `files_processed<0` sentinel with an explicit `HookResult.advisory_issues` field, and add missing-dir detection to `crackerjack.tools.ty_ratchet --split` so a wrong `--prod-dir` produces a clear stderr warning instead of a 1-diagnostic IO-error phantom.

**Architecture:** Two cohesive changes in the ty-ratchet pipeline. E.3 widens `HookResult` by one field (`advisory_issues: list[str] = field(default_factory=list)`) and rewires the `_parse_ty_ratchet` producer + `_display_hook_result` consumer to use it. The missing-dir fix adds a `_zero_result()` helper plus `Path(...).is_dir()` guards at the top of `_run_split` so missing dirs vacuously pass with a stderr warning instead of leaking IO-error diagnostics into the gate count.

**Tech Stack:** Python 3.13, pytest, dataclasses, subprocess, argparse, regex.

## Global Constraints

- **Python**: 3.13+ syntax (`list[str]`, `X | None`, `pathlib.Path`)
- **No `assert` in production code** under `crackerjack/**` — use exception hierarchy from `crackerjack/core/errors.py`. Enforced by bandit B101. Asserts ARE allowed in `tests/**`.
- **No `Any` in tool inputs or orchestration state.** Use `TYPE_CHECKING` and typed protocols.
- **First non-comment line of every source file**: `from __future__ import annotations`
- **Function arguments with default `None`** must be typed `X | None = None` (mypy `no_implicit_optional = true`)
- **Imports sorted within each section** (stdlib → third-party → first-party)
- **Use Oneiric logger** (`oneiric.logging`) — not stdlib `logging`, not `print()`. *Exception*: `crackerjack/tools/*.py` CLI scripts use `print()` for operator-facing output (existing pattern — `ty_ratchet.py` already does this).
- **Per-test timeout ceiling**: 300 s; tests >10 s should be `@pytest.mark.slow`
- **Async tests** don't need `@pytest.mark.asyncio` — `asyncio_mode = "auto"`
- **Subprocess-driven tests** for CLI tools: use `_CRACKERJACK_ROOT` + `_SUBPROCESS_ENV` pattern from existing `tests/tools/test_ty_ratchet.py:38-39`
- **ty uses `# ty: ignore[rule]`** (NOT `# type: ignore`)
- **Commit messages end with**: `Co-Authored-By: Claude <noreply@anthropic.com>`
- **Working tree is clean** at task start; each task ends with a commit

______________________________________________________________________

### Task 1: Add `advisory_issues` field to `HookResult`

**Files:**

- Modify: `crackerjack/models/task.py:35-71` (the `HookResult` dataclass)
- Test: `tests/test_hook_executor.py` (new test class `TestHookResultAdvisoryIssuesField`)

**Interfaces:**

- Consumes: nothing (independent)

- Produces: `HookResult.advisory_issues: list[str]` — new dataclass field

- [ ] **Step 1: Write the failing test**

In `tests/test_hook_executor.py`, add a new test class. Locate a good insertion point (after the last test class but before the helper functions at the bottom of the file). Add:

```python
class TestHookResultAdvisoryIssuesField:
    """``HookResult.advisory_issues`` carries per-tool advisory diagnostics.

    Currently used by the ty hook for test-ratchet diagnostics that are
    surfaced as a post-stage warning but don't flip the hook status.
    Default is an empty list — each instance gets its own list via
    ``field(default_factory=list)``.
    """

    def test_advisory_issues_default_is_empty_list(self) -> None:
        """A bare HookResult() has advisory_issues == []."""
        from crackerjack.models.task import HookResult

        result = HookResult()
        assert result.advisory_issues == []

    def test_advisory_issues_default_factory_not_shared_between_instances(
        self,
    ) -> None:
        """Mutating one instance's list doesn't affect another."""
        from crackerjack.models.task import HookResult

        a = HookResult()
        b = HookResult()
        a.advisory_issues.append("crackerjack/foo.py:10:5: error")
        assert b.advisory_issues == []

    def test_advisory_issues_field_preserved_through_construction(
        self,
    ) -> None:
        """Explicit construction preserves the list reference."""
        from crackerjack.models.task import HookResult

        adv = ["crackerjack/foo.py:10:5: error[invalid-argument-type] x"]
        result = HookResult(name="ty", advisory_issues=adv)
        assert result.advisory_issues is adv
```

- [ ] **Step 2: Run tests to verify they fail**

Run:

```bash
pytest tests/test_hook_executor.py::TestHookResultAdvisoryIssuesField -v
```

Expected: FAIL with `AttributeError: HookResult() got unexpected keyword argument 'advisory_issues'` (or `AttributeError: 'HookResult' object has no attribute 'advisory_issues'`).

- [ ] **Step 3: Add the field to `HookResult`**

In `crackerjack/models/task.py`, after the `qa_result: t.Any | None = None` line at line 54, add:

```python
    advisory_issues: list[str] = field(default_factory=list)
```

The `field` and `list` imports are already present (`field` is imported on line 35). No new imports needed.

- [ ] **Step 4: Run tests to verify they pass**

Run:

```bash
pytest tests/test_hook_executor.py::TestHookResultAdvisoryIssuesField -v
```

Expected: 3 tests PASS.

- [ ] **Step 5: Run full test suite to confirm no regressions**

Run:

```bash
pytest tests/test_hook_executor.py -v
```

Expected: All previously-passing tests still pass (plus the 3 new ones).

- [ ] **Step 6: Commit**

```bash
git add crackerjack/models/task.py tests/test_hook_executor.py
git commit -m "feat(models): add advisory_issues field to HookResult

Replaces the negative-files_processed<0 sentinel used by the ty
hook to encode test-ratchet advisory diagnostics. The new field
is list[str] and defaults to an empty list via field(default_factory=list)
so existing HookResult constructions are unaffected.

Co-Authored-By: Claude <noreply@anthropic.com>"
```

______________________________________________________________________

### Task 2: Rewrite `_parse_ty_ratchet` to return tuple

**Files:**

- Modify: `crackerjack/executors/hook_executor.py:1495-1520` (`_parse_ty_ratchet` method)
- Test: `tests/test_hook_executor.py` (rewrite `TestParseTyRatchetNonRegression` class at line 865)

**Interfaces:**

- Consumes: nothing (depends on `HookResult.advisory_issues` existing, which Task 1 ensures)

- Produces: `_parse_ty_ratchet(output: str) -> tuple[int, list[str]]` — `(files_processed, advisory_issues)`. Always returns `files_processed == 0`; the second element carries concise-format diagnostic lines when the test-gate fails.

- [ ] **Step 1: Rewrite the existing tests to expect the new tuple signature**

In `tests/test_hook_executor.py`, locate `TestParseTyRatchetNonRegression` (around line 865). The class currently has two tests asserting the negative sentinel. Replace the entire class with:

```python
class TestParseTyRatchetAdvisorySemantics:
    """``_parse_ty_ratchet`` returns (files_processed, advisory_issues).

    The advisory list carries the test-ratchet diagnostic lines when
    the test gate fails. ``files_processed`` is always 0 — the prior
    negative-encoding sentinel has been removed (see
    ``HookResult.advisory_issues``).
    """

    @pytest.fixture
    def executor(self, tmp_path: Path) -> HookExecutor:
        return HookExecutor(
            console=MagicMock(),
            pkg_path=tmp_path,
        )

    def test_parse_ty_ratchet_returns_advisories_on_test_fail(
        self, executor: HookExecutor
    ) -> None:
        """When the test gate fails, capture concise diagnostic lines."""
        output = (
            "ty ratchet [split] prod: PASS (0/50)\n"
            "ty ratchet [split] test: FAIL (5/30)\n"
            "crackerjack/foo.py:10:5: error[invalid-argument-type] x is wrong\n"
            "crackerjack/bar.py:42:9: warning[unused-type-ignore-comment] ...\n"
        )
        files_processed, advisories = executor._parse_ty_ratchet(output)
        assert files_processed == 0
        assert len(advisories) == 2
        assert advisories[0].startswith("crackerjack/foo.py:10:5")
        assert advisories[1].startswith("crackerjack/bar.py:42:9")

    def test_parse_ty_ratchet_returns_zero_on_clean(
        self, executor: HookExecutor
    ) -> None:
        """When the test gate passes, return (0, [])."""
        output = "ty ratchet [split] test: PASS (0/30)\n"
        files_processed, advisories = executor._parse_ty_ratchet(output)
        assert files_processed == 0
        assert advisories == []

    def test_parse_ty_ratchet_filters_out_summary_lines(
        self, executor: HookExecutor
    ) -> None:
        """The ratchet's own summary lines don't appear in advisories."""
        output = (
            "ty ratchet [split] prod: FAIL (24/50)\n"
            "ty ratchet [split] test: FAIL (679/30)\n"
            "⚠️  ty: test ratchet FAIL (679/30) — advisory only; "
            "prod gate FAIL (24/50) controls the exit code.\n"
            "crackerjack/foo.py:10:5: error[invalid-argument-type] ...\n"
        )
        files_processed, advisories = executor._parse_ty_ratchet(output)
        assert files_processed == 0
        assert len(advisories) == 1
        assert "crackerjack/foo.py:10:5" in advisories[0]
        # Summary and banner are filtered out by the concise-prefix regex.
        assert not any(a.startswith("ty ratchet") for a in advisories)
        assert not any(a.startswith("⚠️") for a in advisories)

    def test_parse_ty_ratchet_returns_empty_advisories_on_no_test_line(
        self, executor: HookExecutor
    ) -> None:
        """Output without a test-gate summary line yields empty advisories."""
        output = "ty ratchet [split] prod: PASS (0/50)\n"
        files_processed, advisories = executor._parse_ty_ratchet(output)
        assert files_processed == 0
        assert advisories == []
```

If `HookExecutor` isn't already imported in this test file, add `from crackerjack.executors.hook_executor import HookExecutor` at the top (verify with a quick grep; it likely is — `MagicMock` and `pytest.fixture` suggest it's already there from the original class).

- [ ] **Step 2: Run tests to verify they fail**

Run:

```bash
pytest tests/test_hook_executor.py::TestParseTyRatchetAdvisorySemantics -v
```

Expected: FAIL with `TypeError: cannot unpack non-iterable int object` (because the current method returns `int`, not `tuple`).

- [ ] **Step 3: Rewrite `_parse_ty_ratchet` in `hook_executor.py`**

Replace the entire method (lines 1495-1520 in the current file) with:

```python
    def _parse_ty_ratchet(self, output: str) -> tuple[int, list[str]]:
        """Extract the test-ratchet advisories from a ``--split`` run.

        Returns ``(files_processed, advisory_issues)``. ``files_processed``
        is always 0 (the prior negative-encoding sentinel has been
        removed — see ``HookResult.advisory_issues``).

        ``advisory_issues`` carries concise-format diagnostic lines from
        the test-gate run when that gate fails. It is the post-stage
        warning signal: the prod gate drives the exit code, and the
        test-gate diagnostics are surfaced via
        ``_display_hook_result``'s ``⚠️`` banner.
        """
        import re

        test_re = re.compile(
            r"ty ratchet \[split\] test:\s+(?P<status>PASS|FAIL)\s+"
            r"\((?P<count>\d+)/(?P<max>\d+)\)"
        )
        concise_diag_re = re.compile(
            r"^[\w./-]+:\d+:\d+:\s+(?:error|warning)\["
        )

        test_failed = False
        for line in output.splitlines():
            line = line.strip()
            if not line:
                continue
            m = test_re.search(line)
            if m and m.group("status") == "FAIL":
                test_failed = True
                break

        if not test_failed:
            return 0, []

        advisories = [
            raw.strip()
            for raw in output.splitlines()
            if concise_diag_re.match(raw.strip())
        ]
        return 0, advisories
```

- [ ] **Step 4: Run tests to verify they pass**

Run:

```bash
pytest tests/test_hook_executor.py::TestParseTyRatchetAdvisorySemantics -v
```

Expected: 4 tests PASS.

- [ ] **Step 5: Run full hook-executor suite to confirm no regressions**

Run:

```bash
pytest tests/test_hook_executor.py -v
```

Expected: Previous 51 tests still pass (their calls to `_parse_ty_ratchet` may exist in other classes — verify). New 4 tests pass.

- [ ] **Step 6: Commit**

```bash
git add crackerjack/executors/hook_executor.py tests/test_hook_executor.py
git commit -m "refactor(executor): _parse_ty_ratchet returns tuple[int, list[str]]

Returns (files_processed, advisory_issues) where files_processed is
always 0 and advisory_issues carries concise-format diagnostic lines
from a failed test gate. Replaces the negative-files_processed sentinel
that previously encoded the test-gate diagnostic count.

Co-Authored-By: Claude <noreply@anthropic.com>"
```

______________________________________________________________________

### Task 3: Wire `_parse_hook_output` + `_create_parse_result` for the new field

**Files:**

- Modify: `crackerjack/executors/hook_executor.py:1465-1493` (`_parse_hook_output`)
- Modify: `crackerjack/executors/hook_executor.py:1584-1596` (`_create_parse_result`)

**Interfaces:**

- Consumes: `_parse_ty_ratchet` (Task 2), `HookResult.advisory_issues` (Task 1)

- Produces: `_parse_hook_output` returns a dict that now always includes `"advisory_issues": list[str]`

- [ ] **Step 1: Update `_parse_hook_output` to destructure the tuple**

In `crackerjack/executors/hook_executor.py`, in the `_parse_hook_output` method (around line 1489), change the `ty` branch:

```python
# before:
elif hook_name == "ty":
    # ... existing docstring ...
    files_processed = self._parse_ty_ratchet(output)
else:
    files_processed = self._parse_generic_hook_output(output)

return self._create_parse_result(files_processed, result.returncode, output)
```

To:

```python
elif hook_name == "ty":
    # The ty ratchet (crackerjack.tools.ty_ratchet) prints two
    # structured lines in --split mode:
    #   ty ratchet [split] prod: PASS|FAIL (N/M)
    #   ty ratchet [split] test: PASS|FAIL (N/M)
    # The exit code is driven by the PROD gate only; the test
    # gate is advisory (see ty_ratchet.py). We extract the test
    # gate's advisory diagnostics via _parse_ty_ratchet and pass
    # them through HookResult.advisory_issues so the
    # _display_hook_result banner can surface them without
    # re-parsing.
    files_processed, advisory_issues = self._parse_ty_ratchet(output)
else:
    files_processed = self._parse_generic_hook_output(output)
    advisory_issues = []

parse_result = self._create_parse_result(
    files_processed, result.returncode, output
)
parse_result["advisory_issues"] = advisory_issues
return parse_result
```

- [ ] **Step 2: Update `_create_parse_result` to include the key**

In the same file, `_create_parse_result` method (around line 1584), update the returned dict to include the new key:

```python
    def _create_parse_result(
        self,
        files_processed: int,
        exit_code: int,
        output: str,
    ) -> dict[str, t.Any]:
        return {
            "hook_id": None,
            "exit_code": exit_code,
            "files_processed": files_processed,
            "advisory_issues": [],
            "issues": [],
            "raw_output": output,
        }
```

- [ ] **Step 3: Run existing tests to confirm no regressions**

Run:

```bash
pytest tests/test_hook_executor.py -v
```

Expected: All 51+4 tests pass. (The `_parse_hook_output` tests don't exist directly, but the flow is exercised via the broader tests that depend on it.)

- [ ] **Step 4: Commit**

```bash
git add crackerjack/executors/hook_executor.py
git commit -m "refactor(executor): thread advisory_issues through _parse_hook_output

The parse-result dict now always carries the advisory_issues key.
For the ty hook, it's populated by _parse_ty_ratchet; for all other
hooks it stays an empty list. Sets up the field for
_create_hook_result_from_process to consume.

Co-Authored-By: Claude <noreply@anthropic.com>"
```

______________________________________________________________________

### Task 4: Populate `HookResult.advisory_issues` in `_create_hook_result_from_process`

**Files:**

- Modify: `crackerjack/executors/hook_executor.py:597-652` (`_create_hook_result_from_process`)

**Interfaces:**

- Consumes: `_parse_hook_output` dict (Task 3), `HookResult` (Task 1)

- Produces: `HookResult.advisory_issues` is now set from `parsed_output["advisory_issues"]`

- [ ] **Step 1: Add the field to the HookResult construction**

In `crackerjack/executors/hook_executor.py`, in `_create_hook_result_from_process`, locate the `return HookResult(...)` statement (around line 637-652). Add `advisory_issues=parsed_output.get("advisory_issues", []),` to the constructor args. Place it near the other list-typed fields, e.g., right after `issues_found=`:

```python
        return HookResult(
            id=hook.name,
            name=hook.name,
            status=status,
            duration=duration,
            files_processed=parsed_output["files_processed"],
            issues_found=issues_found,
            issues_count=issues_count,
            stage=hook.stage.value,
            exit_code=exit_code,
            error_message=error_message,
            is_timeout=False,
            output=result.stdout,
            error=result.stderr,
            advisory_issues=parsed_output.get("advisory_issues", []),
            qa_result=qa_result,
        )
```

- [ ] **Step 2: Run hook-executor tests to verify the field flows through**

Run:

```bash
pytest tests/test_hook_executor.py -v
```

Expected: All tests pass (no existing test asserts on `advisory_issues` yet — that's Task 5).

- [ ] **Step 3: Commit**

```bash
git add crackerjack/executors/hook_executor.py
git commit -m "feat(executor): populate HookResult.advisory_issues from parse output

The field is now wired end-to-end: ty hook's test-gate diagnostics
flow through _parse_ty_ratchet -> _parse_hook_output ->
_create_hook_result_from_process -> HookResult.advisory_issues.

Co-Authored-By: Claude <noreply@anthropic.com>"
```

______________________________________________________________________

### Task 5: Update `_display_hook_result` to read `advisory_issues`

**Files:**

- Modify: `crackerjack/executors/hook_executor.py:1759-1768` (the warning banner inside `_display_hook_result`)
- Modify: `crackerjack/executors/hook_executor.py:735-743` (comment in `_update_status_for_reporting_tools`)

**Interfaces:**

- Consumes: `HookResult.advisory_issues` (Tasks 1, 4)

- Produces: visible `⚠️` banner reads `len(result.advisory_issues)` instead of `-result.files_processed`

- [ ] **Step 1: Update the warning banner in `_display_hook_result`**

In `crackerjack/executors/hook_executor.py`, in `_display_hook_result`, replace the `if` block (lines 1759-1768):

```python
# before:
if (
    result.name == "ty"
    and result.status == "passed"
    and result.files_processed < 0
):
    test_count = -result.files_processed
    self.console.print(
        f"⚠️  ty test ratchet FAIL: {test_count} diagnostic(s) in tests/ "
        f"(advisory only; prod gate controls stage)"
    )
```

With:

```python
# after:
if (
    result.name == "ty"
    and result.status == "passed"
    and result.advisory_issues
):
    self.console.print(
        f"⚠️  ty test ratchet FAIL: {len(result.advisory_issues)} "
        f"diagnostic(s) in tests/ (advisory only; prod gate controls stage)"
    )
```

- [ ] **Step 2: Update the doc comment in `_update_status_for_reporting_tools`**

The comment at lines 735-743 references the negative sentinel. Update the wording to reference the new field:

```python
# before:
# ty is excluded from the status-flip set because the ratchet's
# prod gate already drives the exit code (see
# crackerjack.tools.ty_ratchet: overall_exit is prod_gate). When
# only the test gate fails, the ratchet returns 0 and the hook
# is "passed" — the test-tail diagnostics are surfaced as
# advisory only via the negative ``files_processed`` sentinel
# and the warning banner in phase_coordinator. Flipping status
# here would regress that documented contract.
```

To:

```python
# after:
# ty is excluded from the status-flip set because the ratchet's
# prod gate already drives the exit code (see
# crackerjack.tools.ty_ratchet: overall_exit is prod_gate). When
# only the test gate fails, the ratchet returns 0 and the hook
# is "passed" — the test-tail diagnostics are surfaced as
# advisory only via ``HookResult.advisory_issues`` and the
# ``⚠️`` banner in ``_display_hook_result``. Flipping status
# here would regress that documented contract.
```

- [ ] **Step 3: Run hook-executor tests to confirm the banner logic still works**

Run:

```bash
pytest tests/test_hook_executor.py -v
```

Expected: All tests pass. The banner logic is exercised by integration tests that produce a ty hook result with advisories.

- [ ] **Step 4: Commit**

```bash
git add crackerjack/executors/hook_executor.py
git commit -m "feat(executor): warning banner reads HookResult.advisory_issues

Replaces the negative-files_processed<0 sentinel in
_display_hook_result with a direct read of the new field.
Same external behavior; cleaner internal encoding.

Co-Authored-By: Claude <noreply@anthropic.com>"
```

______________________________________________________________________

### Task 6: Add `_zero_result()` helper and `is_dir()` guards to `_run_split`

**Files:**

- Modify: `crackerjack/tools/ty_ratchet.py:168-175` (after `run_ty`, add `_zero_result`)
- Modify: `crackerjack/tools/ty_ratchet.py:178-273` (`_run_split` — add guards and `_zero_result` calls)
- Modify: `crackerjack/tools/ty_ratchet.py:227-248` (JSON envelope — add `prod_dir_exists` / `test_dir_exists`)

**Interfaces:**

- Consumes: `Path` from stdlib (already imported)

- Produces: `_zero_result() -> subprocess.CompletedProcess[str]` (new helper); `_run_split` now emits stderr warnings and uses `_zero_result` when a dir is missing; JSON envelope gains `prod_dir_exists` / `test_dir_exists` booleans

- [ ] **Step 1: Write the failing tests**

In `tests/tools/test_ty_ratchet.py`, add a new test class after `TestSplitModeDirFlags` (around line 393):

```python
class TestSplitModeMissingDirs:
    """``--split`` handles missing prod/test dirs gracefully.

    A missing dir produces a stderr warning and a vacuous-pass gate
    (0 ≤ any budget). No IO-error diagnostic leaks into the count.
    """

    def test_split_mode_missing_prod_dir_is_vacuous_pass(
        self, tmp_path: Path
    ) -> None:
        """Missing prod dir → exit 0, prod count = 0, stderr warning."""
        prod_missing = tmp_path / "does_not_exist"
        test_dir = tmp_path / "tests"
        test_dir.mkdir()
        (test_dir / "__init__.py").write_text("", encoding="utf-8")
        pyproject = tmp_path / "pyproject.toml"
        pyproject.write_text(
            "[tool.crackerjack]\n"
            "ty_max_errors_prod = 1000\n"
            "ty_max_errors_test = 1000\n",
            encoding="utf-8",
        )

        result = subprocess.run(
            [
                sys.executable,
                "-m",
                "crackerjack.tools.ty_ratchet",
                "--split",
                "--prod-dir",
                str(prod_missing),
                "--test-dir",
                str(test_dir),
                "--pyproject",
                str(pyproject),
                "--json",
            ],
            capture_output=True,
            text=True,
            env=_SUBPROCESS_ENV,
            cwd=tmp_path,
        )

        assert result.returncode == 0, (
            f"Vacuous-pass should exit 0; got {result.returncode}. "
            f"stderr={result.stderr!r}"
        )
        assert "does not exist" in result.stderr
        summary = json.loads(result.stdout)
        assert summary["prod"]["diagnostic_count"] == 0
        assert summary["prod"]["gate_passes"] is True
        assert summary["prod_dir_exists"] is False
        assert summary["test_dir_exists"] is True

    def test_split_mode_missing_test_dir_is_vacuous_pass(
        self, tmp_path: Path
    ) -> None:
        """Missing test dir → exit 0, test count = 0, stderr warning."""
        prod_dir = tmp_path / "pkg"
        test_missing = tmp_path / "does_not_exist"
        prod_dir.mkdir()
        (prod_dir / "__init__.py").write_text("", encoding="utf-8")
        pyproject = tmp_path / "pyproject.toml"
        pyproject.write_text(
            "[tool.crackerjack]\n"
            "ty_max_errors_prod = 1000\n"
            "ty_max_errors_test = 1000\n",
            encoding="utf-8",
        )

        result = subprocess.run(
            [
                sys.executable,
                "-m",
                "crackerjack.tools.ty_ratchet",
                "--split",
                "--prod-dir",
                str(prod_dir),
                "--test-dir",
                str(test_missing),
                "--pyproject",
                str(pyproject),
                "--json",
            ],
            capture_output=True,
            text=True,
            env=_SUBPROCESS_ENV,
            cwd=tmp_path,
        )

        assert result.returncode == 0
        assert "does not exist" in result.stderr
        summary = json.loads(result.stdout)
        assert summary["test"]["diagnostic_count"] == 0
        assert summary["test"]["gate_passes"] is True
        assert summary["test_dir_exists"] is False
        assert summary["prod_dir_exists"] is True

    def test_split_mode_both_dirs_missing_yields_exit_zero(
        self, tmp_path: Path
    ) -> None:
        """Both missing → exit 0, two stderr warnings."""
        pyproject = tmp_path / "pyproject.toml"
        pyproject.write_text(
            "[tool.crackerjack]\n"
            "ty_max_errors_prod = 1000\n"
            "ty_max_errors_test = 1000\n",
            encoding="utf-8",
        )

        result = subprocess.run(
            [
                sys.executable,
                "-m",
                "crackerjack.tools.ty_ratchet",
                "--split",
                "--prod-dir",
                str(tmp_path / "missing_a"),
                "--test-dir",
                str(tmp_path / "missing_b"),
                "--pyproject",
                str(pyproject),
                "--json",
            ],
            capture_output=True,
            text=True,
            env=_SUBPROCESS_ENV,
            cwd=tmp_path,
        )

        assert result.returncode == 0
        # Two warnings (one per missing dir).
        assert result.stderr.count("does not exist") == 2
        summary = json.loads(result.stdout)
        assert summary["prod_dir_exists"] is False
        assert summary["test_dir_exists"] is False
```

- [ ] **Step 2: Run tests to verify they fail**

Run:

```bash
pytest tests/tools/test_ty_ratchet.py::TestSplitModeMissingDirs -v
```

Expected: FAIL (either with a non-zero exit code because the missing dir produces a 1-diagnostic IO error, or with a JSON shape mismatch because `prod_dir_exists` doesn't exist yet).

- [ ] **Step 3: Add the `_zero_result` helper**

In `crackerjack/tools/ty_ratchet.py`, after the `run_ty` function (line 168-175), add:

```python
def _zero_result() -> subprocess.CompletedProcess[str]:
    """Synthetic CompletedProcess with empty output and returncode 0.

    Used in --split mode when a prod or test dir doesn't exist, so the
    gate math sees a vacuous pass (0 <= any_budget) instead of the
    IO-error diagnostic ``ty`` would emit on a missing path.
    """
    return subprocess.CompletedProcess(
        args=[],
        returncode=0,
        stdout="",
        stderr="",
    )
```

- [ ] **Step 4: Add `is_dir()` guards to `_run_split`**

In `crackerjack/tools/ty_ratchet.py`, in `_run_split` (line 178-273), after the `_read_split_budget` calls and before the existing `prod_result = run_ty(args.prod_dir)` line, add:

```python
    prod_exists = Path(args.prod_dir).is_dir()
    test_exists = Path(args.test_dir).is_dir()

    if not prod_exists:
        print(
            f"⚠️  ty_ratchet: prod dir {args.prod_dir!r} does not exist; "
            f"treating prod gate as 0/0 (vacuously passing).",
            file=sys.stderr,
        )
    if not test_exists:
        print(
            f"⚠️  ty_ratchet: test dir {args.test_dir!r} does not exist; "
            f"treating test gate as 0/0 (vacuously passing, advisory only).",
            file=sys.stderr,
        )

    prod_result = run_ty(args.prod_dir) if prod_exists else _zero_result()
    test_result = run_ty(args.test_dir) if test_exists else _zero_result()
```

- [ ] **Step 5: Add `prod_dir_exists` / `test_dir_exists` to the JSON envelope**

In the same method, in the `summary = {` block (around line 227-248), add the two new keys right after `"test_dir": args.test_dir,`:

```python
    summary = {
        "mode": "split",
        "target": "crackerjack",
        "prod_dir": args.prod_dir,
        "test_dir": args.test_dir,
        "prod_dir_exists": prod_exists,
        "test_dir_exists": test_exists,
        # ... rest unchanged ...
    }
```

- [ ] **Step 6: Run the missing-dir tests to verify they pass**

Run:

```bash
pytest tests/tools/test_ty_ratchet.py::TestSplitModeMissingDirs -v
```

Expected: 3 tests PASS.

- [ ] **Step 7: Run the full ratchet test suite to confirm no regressions**

Run:

```bash
pytest tests/tools/test_ty_ratchet.py -v
```

Expected: All 16 tests pass (13 prior + 3 new).

- [ ] **Step 8: Commit**

```bash
git add crackerjack/tools/ty_ratchet.py tests/tools/test_ty_ratchet.py
git commit -m "feat(ty_ratchet): missing-dir detection with vacuous-pass gate

Adds Path(...).is_dir() guards at the top of _run_split. Missing
prod or test dirs emit a stderr warning and produce a 0-count gate
result instead of leaking a 1-diagnostic IO-error phantom into the
operator-visible count.

JSON envelope gains prod_dir_exists / test_dir_exists booleans so
consumers can verify the guard fired without re-parsing stderr.

Co-Authored-By: Claude <noreply@anthropic.com>"
```

______________________________________________________________________

### Task 7: Add end-to-end integration test for the new banner

**Files:**

- Modify: `tests/test_hook_executor.py` (new test class `TestAdvisoryBannerEndToEnd`)

**Interfaces:**

- Consumes: `HookResult.advisory_issues` (Task 1), `_display_hook_result` (Task 5)

- Produces: a test that asserts the warning banner prints from `advisory_issues` end-to-end

- [ ] **Step 1: Write the failing test**

In `tests/test_hook_executor.py`, add a new test class. This tests the full flow from ratchet output → `_parse_hook_output` → `_create_hook_result_from_process` → `HookResult.advisory_issues` → `_display_hook_result` banner:

```python
class TestAdvisoryBannerEndToEnd:
    """The ⚠️ warning banner fires when HookResult.advisory_issues is set.

    Tests the full pipeline: ratchet stdout/stderr -> parse -> HookResult
    construction -> display -> console output. Locks in the E.3 contract.
    """

    def test_warning_banner_prints_advisory_count(
        self, tmp_path: Path
    ) -> None:
        """When ty hook has advisory_issues and status=passed, banner prints."""
        from crackerjack.executors.hook_executor import HookExecutor
        from crackerjack.models.task import HookResult

        console = MagicMock()
        executor = HookExecutor(console=console, pkg_path=tmp_path)

        result = HookResult(
            id="ty",
            name="ty",
            status="passed",
            duration=1.0,
            files_processed=0,
            issues_found=[],
            issues_count=0,
            stage="comp",
            exit_code=0,
            advisory_issues=[
                "crackerjack/foo.py:10:5: error[invalid-argument-type] x is wrong",
                "crackerjack/bar.py:42:9: warning[unused-type-ignore-comment] ...",
            ],
        )

        executor._display_hook_result(result)

        # Find the call that printed the warning banner.
        banner_calls = [
            call_args
            for call_args in console.print.call_args_list
            if call_args.args
            and "ty test ratchet FAIL" in str(call_args.args[0])
        ]
        assert len(banner_calls) == 1, (
            f"Expected exactly 1 warning banner; got {len(banner_calls)}. "
            f"All console.print calls: {console.print.call_args_list}"
        )
        banner_text = str(banner_calls[0].args[0])
        assert "2 diagnostic(s)" in banner_text
        assert "tests/" in banner_text
        assert "advisory only" in banner_text

    def test_no_banner_when_advisory_issues_empty(
        self, tmp_path: Path
    ) -> None:
        """When advisory_issues is empty, no warning banner prints."""
        from crackerjack.executors.hook_executor import HookExecutor
        from crackerjack.models.task import HookResult

        console = MagicMock()
        executor = HookExecutor(console=console, pkg_path=tmp_path)

        result = HookResult(
            id="ty",
            name="ty",
            status="passed",
            duration=1.0,
            files_processed=0,
            issues_found=[],
            issues_count=0,
            stage="comp",
            exit_code=0,
            advisory_issues=[],
        )

        executor._display_hook_result(result)

        banner_calls = [
            call_args
            for call_args in console.print.call_args_list
            if call_args.args
            and "ty test ratchet FAIL" in str(call_args.args[0])
        ]
        assert len(banner_calls) == 0

    def test_no_banner_when_status_failed(
        self, tmp_path: Path
    ) -> None:
        """When the hook status is 'failed', no advisory banner (gate is the signal)."""
        from crackerjack.executors.hook_executor import HookExecutor
        from crackerjack.models.task import HookResult

        console = MagicMock()
        executor = HookExecutor(console=console, pkg_path=tmp_path)

        result = HookResult(
            id="ty",
            name="ty",
            status="failed",
            duration=1.0,
            files_processed=0,
            issues_found=["some prod error"],
            issues_count=1,
            stage="comp",
            exit_code=1,
            advisory_issues=[
                "crackerjack/foo.py:10:5: error ...",  # would be advisory
            ],
        )

        executor._display_hook_result(result)

        banner_calls = [
            call_args
            for call_args in console.print.call_args_list
            if call_args.args
            and "ty test ratchet FAIL" in str(call_args.args[0])
        ]
        assert len(banner_calls) == 0, (
            "Banner must not fire when status=failed (gate is the visible signal)."
        )
```

- [ ] **Step 2: Run tests to verify they pass**

Run:

```bash
pytest tests/test_hook_executor.py::TestAdvisoryBannerEndToEnd -v
```

Expected: 3 tests PASS (the previous Tasks 1-5 have already wired the field, so this just locks in the behavior).

- [ ] **Step 3: Commit**

```bash
git add tests/test_hook_executor.py
git commit -m "test(executor): end-to-end advisory banner coverage

Locks in the E.3 contract: the warning banner fires when
HookResult.advisory_issues is non-empty AND status=passed.
No banner when status=failed (the gate's exit code is the
operator signal in that case).

Co-Authored-By: Claude <noreply@anthropic.com>"
```

______________________________________________________________________

### Task 8: Run full test suite + cross-project smoke

**Files:**

- None (verification only)

**Interfaces:**

- Consumes: All Tasks 1-7

- Produces: confidence that nothing regressed across crackerjack, oneiric, mahavishnu

- [ ] **Step 1: Run all ty-related test files**

Run:

```bash
pytest tests/test_hook_executor.py tests/tools/test_ty_ratchet.py tests/tools/test_ty_audit.py -v
```

Expected: 80 tests pass (51 + 3 + 4 + 13 + 3 + 6 = 80; some may shift due to test renames).

- [ ] **Step 2: Smoke test in crackerjack**

Run:

```bash
cd /Users/les/Projects/crackerjack
python -m crackerjack run --tool ty 2>&1 | head -30
```

Expected: Ty hook completes. If the test gate fails (it does — ~766 test debt), the warning banner prints with the test-gate count. No regression in the prod gate.

- [ ] **Step 3: Smoke test the missing-dir case**

Run:

```bash
cd /Users/les/Projects/crackerjack
python -m crackerjack.tools.ty_ratchet --split --prod-dir ./does_not_exist --test-dir ./tests --json
```

Expected: exit 0, JSON has `prod_dir_exists: false`, stderr has the "does not exist" warning.

- [ ] **Step 4: Cross-project smoke in oneiric**

Run:

```bash
cd /Users/les/Projects/oneiric
python -m crackerjack run --tool ty 2>&1 | tail -10
```

Expected: ty hook completes; prod diagnostic count is reported (likely 158 if prior state holds). Test-gate warning banner prints with the test-gate count (likely 680). No crash.

- [ ] **Step 5: Cross-project smoke in mahavishnu**

Run:

```bash
cd /Users/les/Projects/mahavishnu
python -m crackerjack run --tool ty 2>&1 | tail -10
```

Expected: ty hook completes; prod diagnostic count is reported (likely 482 if prior state holds). Test-gate warning banner prints with the test-gate count (likely 2056). No crash.

- [ ] **Step 6: Commit any final touch-ups**

If Steps 1-5 surface any issue, fix it and commit. Otherwise no commit needed — verification only.

______________________________________________________________________

## Self-Review Notes

- **Spec coverage**: All sections of `docs/superpowers/specs/2026-06-29-ty-ratchet-cleanup-design.md` are covered by Tasks 1-7. Task 8 verifies end-to-end.
- **Item 2 (per-project pyproject keys)**: Explicitly out of scope per the spec's "Out-of-scope follow-ups" section. No task addresses it. This is correct YAGNI behavior.
- **No placeholders**: All steps show concrete code, file paths, and commands.
- **Type consistency**: `HookResult.advisory_issues: list[str]` is referenced consistently across Tasks 1, 4, 5, 7. `_parse_ty_ratchet -> tuple[int, list[str]]` is consistent in Tasks 2, 3. `_zero_result` is referenced consistently in Task 6.
- **Order matters**: Tasks 1-5 must land in sequence (each builds on the previous). Task 6 is independent and could be reordered, but Tasks 7-8 should follow.

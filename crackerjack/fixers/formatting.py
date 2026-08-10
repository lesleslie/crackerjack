"""Deterministic ruff-wrapper and whitespace/tab-fixing formatter.

Extracted from ``crackerjack.agents.formatting_agent.FormattingAgent``, which
does not delegate to any ``agents/helpers/*`` class -- it is fully
self-contained aside from ``AgentContext`` (framework file-I/O wrapper) and
``SubAgent.run_command``/``SubAgent.log`` (framework subprocess/logging
wrappers). Confirmed via full read of the 506-line source file: no
LLM/bridge/coordinator/semantic-search references anywhere in the class.

What was intentionally dropped versus the original ``FormattingAgent``:

- ``SubAgent``/coordinator dispatch plumbing: ``__init__``, ``can_handle``,
  and ``get_supported_types`` -- these only ever decided *whether* and *how
  confidently* this fixer should run for a given ``Issue``; that routing job
  belongs to whatever calls into this module now, not to the module itself.
- ``agent_registry.register(FormattingAgent)`` -- registry plumbing.
- ``self.log(...)`` calls throughout -- ``SubAgent.log`` is a no-op ``pass``
  on the base class, so these calls had no observable effect (same
  treatment as every other ``crackerjack/fixers/*.py`` extraction so far).
- ``AgentContext``-specific file I/O: ``AgentContext.get_file_content``'s
  path-traversal/size checks and ``AgentContext.write_file_content``'s
  path-traversal check, ``wrap_long_lines`` post-processing (which itself
  imports from the to-be-removed ``crackerjack.ai_fix`` package -- doubly
  reason to drop it here), and syntax/duplicate-top-level-definition
  validation -- replaced with direct ``pathlib.Path`` reads/writes via
  ``_read_file``/``_write_file`` below (same helpers, byte-for-byte, as
  ``security.py``/``documentation.py``). Real file I/O is still performed;
  only the framework wrapper around it is gone. The original's trivial
  ``_validate_and_get_file_content`` method (existence/is-file check plus a
  passthrough to ``self.context.get_file_content``) is dropped in favor of
  calling ``_read_file`` directly at its one call site in
  ``_fix_specific_file``; a missing/unreadable file still yields ``None``
  either way since ``Path.read_text`` raises ``OSError`` (caught) for a
  missing path or a directory.
- ``SubAgent.run_command`` (always ran external tools with
  ``cwd=self.context.project_path`` and
  ``timeout=self.context.subprocess_timeout``) -- replaced with a
  module-level ``_run_command`` with a fixed 300s default timeout. Task 22a
  restored the ``cwd`` pinning: ``_run_command`` now requires an explicit
  ``cwd: Path`` parameter (not defaulted), and every call site
  (``_apply_ruff_fixes``/``_apply_whitespace_fixes``/``_apply_import_fixes``,
  which already threaded ``project_path`` through for the mtime-scan, plus
  ``_apply_spelling_fixes``, which needed ``project_path`` newly threaded in
  from ``fix_formatting_issue``) now passes ``cwd=project_path``. The
  ``_run_post_write_ruff_format``/``_apply_planned_changes`` path (a bare
  ``subprocess.run``, not ``_run_command``) got the same fix, with
  ``project_path`` newly threaded from ``execute_fix_plan``. Real subprocess
  execution is still performed, with the same async/timeout semantics as the
  original.
- ``AgentContext.project_path``: threaded through explicitly as a
  ``project_path: Path`` parameter on ``fix_formatting_issue``,
  ``execute_fix_plan``, ``_get_file_state``, ``_apply_ruff_fixes``,
  ``_apply_whitespace_fixes``, and ``_apply_import_fixes`` -- it is real,
  load-bearing logic (``_get_file_state``'s ``target == "."`` branch does a
  project-wide ``rglob("*.py")`` to snapshot mtimes before running a
  project-wide ruff/whitespace pass), not dropped.
- Two genuinely dead (unused) parameters, confirmed via careful re-reading
  of the original method bodies -- dropped as inert, not as a behavioral
  simplification (same treatment as ``documentation.py``'s dead
  ``re.escape(target_file)`` statement):
  - ``_get_modified_files``'s ``target: list[str]`` parameter is never
    referenced in its body (it only iterates ``files_before``).
  - ``_fix_specific_file``'s ``issue: Issue`` parameter is never referenced
    in its body (only ``file_path`` is used); the caller
    (``FormattingAgent.analyze_and_fix``) always passed ``issue`` anyway,
    but ``_fix_specific_file`` never read it.

Renames worth noting for anyone diffing against the original: the
``SubAgent.analyze_and_fix`` entry point becomes ``fix_formatting_issue``
below (same dispatch flow, minus the ``self``/``AgentContext`` plumbing).

``execute_fix_plan`` is kept (per the plan's precedent: ``FormattingAgent``
is one of four agent classes -- alongside ``ArchitectAgent``,
``DocumentationAgent``, and ``SecurityAgent`` -- with its own
``FixPlan``/``ChangeSpec`` applicator, independent of ``planning_agent.py``'s
plan-construction logic).

Pre-existing quirks preserved verbatim, not fixed, per CLAUDE.md Rule 7
("preserve functional requirements... fix the technical issue, not the
requirements"):

1. ``fix_formatting_issue`` does ``success=fixes_applied`` where
   ``FixResult.success`` is typed ``bool`` -- ``fixes_applied`` is a
   ``list[str]``, so this is a list-as-bool type mismatch (truthy when
   non-empty), marked ``# type: ignore`` in the original, preserved here.
2. ``execute_fix_plan``'s no-``plan.changes`` branch builds
   ``line_number=plan.changes[0].line_range[0] if plan.changes else None``.
   This line only executes when ``plan.changes`` is falsy (the
   ``if plan.changes: return _apply_planned_changes(plan)`` branch above it
   already returns whenever ``plan.changes`` is truthy), so
   ``plan.changes[0]`` is unreachable dead code in this position --
   ``plan.changes`` is always empty here, and the expression always
   evaluates to ``None``. A vestigial conditional, preserved verbatim rather
   than simplified to a bare ``None``.
3. **The significant one**: ``_apply_whitespace_fixes`` has an inverted
   exit-code check that silently under-reports real, successful whitespace
   fixes. ``crackerjack.tools.trailing_whitespace`` and
   ``crackerjack.tools.end_of_file_fixer`` (invoked as ``python -m ...``
   subprocesses) both return exit code **1** when they actually find and
   fix an issue (``modified_count > 0``), and exit code **0** when there
   was nothing to fix. Confirmed empirically:
   ``uv run python -m crackerjack.tools.trailing_whitespace <file-with-trailing-ws>``
   exits 1 and rewrites the file; the same command against an already-clean
   file exits 0 and leaves it untouched. But ``_apply_whitespace_fixes``
   only records a fix (appends to ``fixes`` and scans ``_get_modified_files``
   into ``files_modified``) inside an ``if returncode == 0:`` branch. Net
   effect: when trailing-whitespace/EOF issues are *actually* fixed on disk
   (real file mutation happens -- this is not mocked away), the function
   reports **nothing** happened (``returncode == 1`` skips the whole
   branch) for *that* subprocess call. Because both subprocess calls share
   one ``files_before`` mtime snapshot taken up front, a trailing-whitespace
   fix followed by a no-op end-of-file check still ends up reporting
   ``["Fixed end-of-file formatting"]`` and the file as modified -- the
   mtime bump from the *first* (unreported) subprocess call gets
   opportunistically picked up by the *second* (reported) one. When there
   is nothing to fix at all (``returncode == 0`` on both), it misleadingly
   appends both "Fixed ..." messages despite no file having changed (though
   ``files_modified`` correctly comes out empty in that case, since
   ``_get_modified_files``' mtime comparison finds no changes). Kept as-is;
   see ``TestApplyWhitespaceFixes`` in ``tests/fixers/test_formatting.py``
   for tests that pin this exact behavior against real subprocess
   invocations.
4. ``_apply_import_fixes`` passes ``"I, F401"`` (comma-*space*-F401) as a
   single CLI argument to ``ruff check --select``. Ruff parses each
   ``--select`` argument as its own token and does not tolerate the
   embedded space: this exits with returncode 2 and the error
   ``Unknown rule selector `` F401` in `select` from the CLI`` (confirmed
   empirically), so ``_apply_import_fixes`` *never* organizes/removes
   imports via this path -- the ``returncode == 0`` branch is unreachable
   for any real invocation, regardless of target content. Kept as-is; see
   ``TestApplyImportFixes.test_broken_select_argument_never_fixes_anything``.
5. ``_apply_spelling_fixes`` reads ``codespell``'s fix-report from
   **stdout** (``fixed_count = sum(1 for line in stdout.splitlines() if
   "FIXED" in line)`` and ``_extract_ambiguous_codespell_typos(stdout)``),
   but ``codespell -w`` actually writes its ``FIXED: <path>`` /
   ``<path>:<line>: <typo> ==> <suggestion>`` report to **stderr**
   (confirmed empirically via direct subprocess capture). ``stdout`` is
   always empty, so ``fixed_count`` is always 0 and ``ambiguous`` is always
   ``[]`` -- ``_apply_spelling_fixes`` never reports a fix, even though
   codespell *does* rewrite the file on disk. Kept as-is; see
   ``TestApplySpellingFixes.test_real_fix_on_disk_is_never_reported``.

Emergent consequence of the above (not a separate bug, but worth flagging
for anyone tuning ``fix_formatting_issue``'s confidence heuristic): ``ruff
format`` and ``ruff check --fix`` both exit 0 whether or not they changed
anything, so ``_apply_ruff_fixes`` appends its two "Applied ruff ..."
messages on *every* successful run against a real file -- clean or dirty.
Combined with quirk 3's "misleadingly reports a fix on a no-op" behavior,
this means ``fixes_applied`` is essentially never empty for any
syntactically-valid target file, so ``fix_formatting_issue`` reports
``confidence=0.9``/truthy ``success`` even when the file was already
perfectly clean and nothing on disk changed. Confirmed empirically and
pinned by ``TestFixFormattingIssue.test_already_clean_file_still_reports_high_confidence``.
"""

from __future__ import annotations

import asyncio
import re
from contextlib import suppress
from pathlib import Path

from crackerjack.models.fix_plan import ChangeSpec, FixPlan
from crackerjack.models.issues import FixResult, Issue, IssueType, Priority
from crackerjack.services.regex_patterns import apply_formatting_fixes


def _read_file(file_path: str | Path) -> str | None:
    try:
        return Path(file_path).read_text(encoding="utf-8")
    except OSError:
        return None


def _write_file(file_path: str | Path, content: str) -> bool:
    try:
        Path(file_path).write_text(content, encoding="utf-8")
        return True
    except OSError:
        return False


async def _run_command(
    cmd: list[str],
    cwd: Path,
    timeout: int = 300,
) -> tuple[int, str, str]:
    try:
        process = await asyncio.create_subprocess_exec(
            *cmd,
            cwd=cwd,
            stdout=asyncio.subprocess.PIPE,
            stderr=asyncio.subprocess.PIPE,
        )

        stdout, stderr = await asyncio.wait_for(
            process.communicate(),
            timeout=timeout,
        )

        return (
            process.returncode or 0,
            stdout.decode() if stdout else "",
            stderr.decode() if stderr else "",
        )
    except TimeoutError:
        return (-1, "", "Command timed out")
    except Exception as e:
        return (-1, "", f"Command failed: {e}")


# ---------------------------------------------------------------------------
# File-state / mtime-diff tracking (used to detect what a subprocess touched)
# ---------------------------------------------------------------------------


def _get_file_state(target: list[str], project_path: Path) -> dict[str, float]:
    files_before: dict[str, float] = {}

    for t in target:
        if t == ".":
            for py_file in project_path.rglob("*.py"):
                if py_file.is_file():
                    files_before[str(py_file)] = py_file.stat().st_mtime
        else:
            file_path = Path(t)
            if file_path.exists() and file_path.is_file():
                files_before[t] = file_path.stat().st_mtime

    return files_before


def _get_modified_files(files_before: dict[str, float]) -> list[str]:
    modified: list[str] = []

    for file_path, mtime_before in files_before.items():
        file_path_obj = Path(file_path)
        if file_path_obj.exists():
            with suppress(OSError):
                mtime_after = file_path_obj.stat().st_mtime
                if mtime_after > mtime_before:
                    modified.append(file_path)

    return modified


# ---------------------------------------------------------------------------
# ruff / whitespace / import subprocess wrappers
# ---------------------------------------------------------------------------


async def _apply_ruff_fixes(
    target: list[str], project_path: Path
) -> tuple[list[str], list[str]]:
    fixes: list[str] = []
    files_modified: list[str] = []

    files_before = _get_file_state(target, project_path)

    returncode, _, _stderr = await _run_command(
        ["uv", "run", "ruff", "format", *target],
        cwd=project_path,
    )

    if returncode == 0:
        fixes.append("Applied ruff code formatting")
        files_modified.extend(_get_modified_files(files_before))

    returncode, _, _stderr = await _run_command(
        ["uv", "run", "ruff", "check", *target, "--fix"],
        cwd=project_path,
    )

    if returncode == 0:
        fixes.append("Applied ruff linting fixes")
        files_modified.extend(_get_modified_files(files_before))

    return fixes, list(set(files_modified))


async def _apply_whitespace_fixes(
    target: list[str], project_path: Path
) -> tuple[list[str], list[str]]:
    fixes: list[str] = []
    files_modified: list[str] = []

    files_before = _get_file_state(target, project_path)

    returncode, _, _ = await _run_command(
        [
            "uv",
            "run",
            "python",
            "-m",
            "crackerjack.tools.trailing_whitespace",
            *target,
        ],
        cwd=project_path,
    )

    if returncode == 0:
        fixes.append("Fixed trailing whitespace")
        files_modified.extend(_get_modified_files(files_before))

    returncode, _, _ = await _run_command(
        [
            "uv",
            "run",
            "python",
            "-m",
            "crackerjack.tools.end_of_file_fixer",
            *target,
        ],
        cwd=project_path,
    )

    if returncode == 0:
        fixes.append("Fixed end-of-file formatting")
        files_modified.extend(_get_modified_files(files_before))

    return fixes, list(set(files_modified))


async def _apply_import_fixes(
    target: list[str], project_path: Path
) -> tuple[list[str], list[str]]:
    fixes: list[str] = []
    files_modified: list[str] = []

    files_before = _get_file_state(target, project_path)

    returncode, _, _ = await _run_command(
        [
            "uv",
            "run",
            "ruff",
            "check",
            *target,
            "--select",
            "I, F401",
            "--fix",
        ],
        cwd=project_path,
    )

    if returncode == 0:
        fixes.append("Organized imports and removed unused imports")
        files_modified.extend(_get_modified_files(files_before))

    return fixes, list(set(files_modified))


async def _apply_spelling_fixes(issue: Issue, project_path: Path) -> list[str]:
    fixes: list[str] = []

    if not issue.file_path:
        return fixes

    try:
        _returncode, stdout, _stderr = await _run_command(
            ["uv", "run", "codespell", "-w", issue.file_path],
            cwd=project_path,
        )

        fixed_count = sum(1 for line in stdout.splitlines() if "FIXED" in line)
        ambiguous = _extract_ambiguous_codespell_typos(stdout)

        if fixed_count > 0:
            fixes.append(f"Fixed {fixed_count} spelling error(s) in {issue.file_path}")

        if ambiguous:
            summary = ", ".join(ambiguous[:5])
            if len(ambiguous) > 5:
                summary += f" (+{len(ambiguous) - 5} more)"
            guidance = (
                f"codespell: {len(ambiguous)} ambiguous typo(s) in "
                f"{issue.file_path} need a human pick — {summary}. "
                f"Add the intended word(s) to .codespellrc "
                f"`ignore-words-list` or fix in-place."
            )
            fixes.append(guidance)

    except Exception:
        pass

    return fixes


def _extract_ambiguous_codespell_typos(stdout_text: str) -> list[str]:
    ambiguous: list[str] = []
    for line in stdout_text.splitlines():
        if "==>" not in line:
            continue
        _, _, after = line.partition("==>")
        suggestions = after.strip()

        if "," in suggestions:
            ambiguous.append(line.strip())
    return ambiguous


# ---------------------------------------------------------------------------
# Per-file content formatting (pure string transforms)
# ---------------------------------------------------------------------------


def _convert_tabs_to_spaces(content: str) -> str:
    lines = content.split("\n")
    fixed_lines = [line.expandtabs(4) for line in lines]
    return "\n".join(fixed_lines)


def _apply_content_formatting(content: str) -> str:
    content = apply_formatting_fixes(content)

    if content == "":
        content = "\n"
    elif not content.endswith("\n"):
        content += "\n"

    return _convert_tabs_to_spaces(content)


async def _fix_specific_file(file_path: str) -> list[str]:
    fixes: list[str] = []

    try:
        path = Path(file_path)
        content = _read_file(path)
        if not content:
            return fixes

        original_content = content
        cleaned_content = _apply_content_formatting(content)

        if cleaned_content != original_content:
            if _write_file(path, cleaned_content):
                fixes.append(f"Fixed formatting in {file_path}")

    except Exception:
        pass

    return fixes


# ---------------------------------------------------------------------------
# fix_formatting_issue dispatch (was SubAgent.analyze_and_fix)
# ---------------------------------------------------------------------------


async def fix_formatting_issue(issue: Issue, project_path: Path) -> FixResult:
    fixes_applied: list[str] = []
    files_modified: list[str] = []

    try:
        message_lower = issue.message.lower()
        if "spelling" in message_lower:
            spelling_fixes = await _apply_spelling_fixes(issue, project_path)
            fixes_applied.extend(spelling_fixes)
            if spelling_fixes and issue.file_path:
                files_modified.append(issue.file_path)

        target = [issue.file_path] if issue.file_path else ["."]

        ruff_fixes, ruff_files = await _apply_ruff_fixes(target, project_path)
        fixes_applied.extend(ruff_fixes)
        files_modified.extend(ruff_files)

        whitespace_fixes, whitespace_files = await _apply_whitespace_fixes(
            target, project_path
        )
        fixes_applied.extend(whitespace_fixes)
        files_modified.extend(whitespace_files)

        import_fixes, import_files = await _apply_import_fixes(target, project_path)
        fixes_applied.extend(import_fixes)
        files_modified.extend(import_files)

        if issue.file_path and "spelling" not in message_lower:
            file_fixes = await _fix_specific_file(issue.file_path)
            fixes_applied.extend(file_fixes)
            if file_fixes and issue.file_path not in files_modified:
                files_modified.append(issue.file_path)

        success = fixes_applied
        confidence = 0.9 if success else 0.3

        return FixResult(
            success=success,  # type: ignore
            confidence=confidence,
            fixes_applied=fixes_applied,
            files_modified=list(set(files_modified)),
            recommendations=[
                "Run ruff format regularly for consistent styling",
                "Configure pre-commit hooks for automatic formatting",
            ]
            if not success
            else [],
        )

    except Exception as e:
        return FixResult(
            success=False,
            confidence=0.0,
            remaining_issues=[f"Failed to apply formatting fixes: {e}"],
        )


# ---------------------------------------------------------------------------
# execute_fix_plan / ChangeSpec applicator
# ---------------------------------------------------------------------------


def _apply_change_spec(content: str, change: ChangeSpec) -> str | None:
    lines = content.splitlines()
    start, end = change.line_range
    if start < 1 or end < start or end > len(lines):
        return None

    current_segment = "\n".join(lines[start - 1 : end])
    if (
        current_segment != change.old_code
        and current_segment.strip() != change.old_code.strip()
    ):
        flexible_content = _replace_segment_flexibly(content, change)
        if flexible_content is not None:
            return flexible_content
        return None

    replacement_lines = change.new_code.split("\n")
    updated_lines = lines[: start - 1] + replacement_lines + lines[end:]
    updated_content = "\n".join(updated_lines)
    if content.endswith("\n"):
        updated_content += "\n"
    return updated_content


def _replace_segment_flexibly(content: str, change: ChangeSpec) -> str | None:
    needle = change.old_code.strip()
    if not needle:
        return None

    if needle in content:
        return content.replace(needle, change.new_code, 1)

    tokens = needle.split()
    if len(tokens) < 2:
        return None

    pattern = r"\s+".join(re.escape(token) for token in tokens)
    match = re.search(pattern, content, flags=re.DOTALL)
    if not match:
        return None

    return content[: match.start()] + change.new_code + content[match.end() :]


def _run_post_write_ruff_format(file_path: Path, project_path: Path) -> None:
    try:
        import subprocess

        subprocess.run(
            ["uv", "run", "ruff", "format", file_path],
            cwd=project_path,
            capture_output=True,
            text=True,
            timeout=30,
        )
    except Exception:
        pass


def _apply_planned_changes(plan: FixPlan, project_path: Path) -> FixResult:
    file_path = Path(plan.file_path)

    try:
        content = file_path.read_text(encoding="utf-8")
    except OSError as e:
        return FixResult(
            success=False,
            confidence=0.0,
            remaining_issues=[f"Could not read file: {e}"],
        )

    updated_content = content
    applied_changes: list[str] = []

    for index, change in enumerate(plan.changes):
        next_content = _apply_change_spec(updated_content, change)
        if next_content is None:
            return FixResult(
                success=False,
                confidence=0.0,
                remaining_issues=[
                    f"Failed to apply planned change {index}: {change.reason}"
                ],
                recommendations=[
                    "Regenerate the plan with a narrower line-range match"
                ],
            )
        updated_content = next_content
        applied_changes.append(f"Change {index}: {change.reason}")

    if not _write_file(file_path, updated_content):
        return FixResult(
            success=False,
            confidence=0.0,
            remaining_issues=[f"Failed to write file: {file_path}"],
        )

    if file_path.suffix == ".py":
        _run_post_write_ruff_format(file_path, project_path)

    return FixResult(
        success=True,
        confidence=0.9,
        fixes_applied=applied_changes,
        files_modified=[file_path],  # type: ignore
    )


async def execute_fix_plan(plan: FixPlan, project_path: Path) -> FixResult:
    if not plan.file_path:
        return FixResult(
            success=False,
            confidence=0.0,
            remaining_issues=["No file path in plan"],
        )

    try:
        if plan.changes:
            return _apply_planned_changes(plan, project_path)

        issue = Issue(
            type=IssueType.FORMATTING,
            severity=Priority.LOW,
            message=plan.rationale or "Formatting fix",
            file_path=plan.file_path,
            line_number=plan.changes[0].line_range[0] if plan.changes else None,
        )

        return await fix_formatting_issue(issue, project_path)

    except Exception as e:
        return FixResult(
            success=False,
            confidence=0.0,
            remaining_issues=[f"Formatting execution error: {e}"],
        )


__all__ = [
    "ChangeSpec",
    "FixPlan",
    "execute_fix_plan",
    "fix_formatting_issue",
]

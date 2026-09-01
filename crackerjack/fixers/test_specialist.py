"""Deterministic test-failure classification and templated fixer.

Extracted from ``crackerjack.agents.test_specialist_agent.TestSpecialistAgent``,
which uses plain string/regex matching (``_identify_failure_type``) followed by
templated fixture/import/mock fixes -- no LLM dependency.

What was intentionally dropped versus the original ``TestSpecialistAgent``:

- ``SubAgent``/coordinator dispatch plumbing: ``__init__`` (which only built
  ``common_test_patterns`` for ``can_handle``'s use -- see below),
  ``get_supported_types``, and ``can_handle`` plus its dedicated confidence
  helpers ``_check_perfect_test_matches``, ``_check_test_patterns``,
  ``_check_test_file_path``, and ``_check_general_test_failure``. These only
  ever decided *whether* and *how confidently* this fixer should run for a
  given ``Issue``; that routing job belongs to whatever calls into this
  module now, not to the module itself. Note ``_check_test_patterns``
  duplicates the same pattern-matching structure as the real classifier
  (``_identify_failure_type`` below) but only to produce a boolean-ish
  confidence signal, not to decide *which* fix path to run -- so unlike
  ``SecurityAgent``'s ``_check_enhanced_patterns``/``_check_bandit_patterns``/
  ``_check_legacy_patterns`` (which were kept because ``_identify_vulnerability_type``
  directly calls them), ``_check_test_patterns`` is genuinely just dispatch
  plumbing and is dropped.
- ``agent_registry.register(TestSpecialistAgent)`` -- registry plumbing.
- ``self.log(...)`` calls throughout -- ``SubAgent.log`` is a no-op ``pass``
  on the base class, so these calls had no observable effect; dropped along
  with the rest of the coordinator plumbing (same treatment as
  ``crackerjack/fixers/security.py`` and ``crackerjack/fixers/performance.py``).
- ``AgentContext``-specific file I/O: ``AgentContext.get_file_content``'s
  path-traversal check and file-size cap, and ``AgentContext.write_file_content``'s
  path-traversal check, ``wrap_long_lines`` post-processing (which itself
  imports from the to-be-removed ``crackerjack.ai_fix`` package), and
  syntax/duplicate-top-level-definition validation -- replaced with direct
  ``pathlib.Path`` reads/writes via ``_read_file``/``_write_file`` below. Real
  file I/O is still performed; only the framework wrapper around it is gone.
  The tiny ``_save_import_fixes``/``_save_mock_fixes`` wrappers are kept
  (minus the no-op ``self.log`` call) since they mirror the original's
  write-then-log shape.
- ``AgentContext.project_path``-derived subprocess ``cwd``: the original
  ``SubAgent.run_command`` always ran ``uv run python -m pytest
  --collect-only -q`` (in ``_apply_general_test_fixes``) with
  ``cwd=self.context.project_path``. Task 22a restored this pinning:
  ``fix_test_issue`` now takes an explicit ``project_root: Path`` parameter
  (newly threaded -- none of ``fix_test_issue``/``_apply_issue_fixes``/
  ``_apply_general_test_fixes`` accepted any project-path parameter before),
  passed down to ``_apply_general_test_fixes`` and on to ``_run_command`` as
  ``cwd`` (itself now requiring an explicit ``cwd`` parameter, not
  defaulted). Real subprocess execution is still performed, with the same
  async/timeout semantics as the original ``SubAgent.run_command`` (default
  300s timeout, matching ``AgentContext.subprocess_timeout``'s default).
- Redundant double-indirection in pattern lookup: the original's
  ``_identify_failure_type`` (and the dropped ``_check_test_patterns``)
  built a ``pattern_map`` keyed by *regex pattern string* -> canonical
  ``SAFE_PATTERNS`` key, then iterated ``self.common_test_patterns.items()``
  (friendly name -> regex string, built once in ``__init__``) purely to look
  the regex string back up in ``pattern_map`` and recover the same canonical
  key it started from. Since every ``common_test_patterns`` value maps
  1:1 back to a unique ``SAFE_PATTERNS`` key, this round trip is a no-op:
  collapsed below into a single ``_FAILURE_PATTERN_NAMES`` dict (friendly
  name -> canonical ``SAFE_PATTERNS`` key) iterated directly, in the same
  insertion order as the original ``common_test_patterns`` dict literal
  (this order matters -- it is match-priority order when a message could
  match more than one pattern).

``analyze_and_fix`` becomes ``fix_test_issue`` below (same
identify/dispatch/apply-additional-fixes flow, minus the ``self``/
``AgentContext`` plumbing).

One pre-existing behavioral quirk is preserved verbatim, not fixed, per
CLAUDE.md Rule 7 ("preserve functional requirements... fix the technical
issue, not the requirements"):

1. ``_fix_test_file_issues`` only appends a "fixes" message when it inserts
   a missing ``import pytest`` line. If ``apply_test_fixes`` (assert-spacing
   normalization) changes the content on its own -- with no missing pytest
   import -- the file is still written to disk, but the returned fix list is
   empty. Combined with quirk (1) above, this means ``files_modified`` can
   silently omit a file that was, in fact, modified on disk, whenever the
   only change was assert-statement normalization. See
   ``tests/fixers/test_test_specialist.py`` for a test that exercises this.
"""

from __future__ import annotations

import asyncio
from pathlib import Path

from crackerjack.models.issues import FixResult, Issue
from crackerjack.services.regex_patterns import SAFE_PATTERNS, apply_test_fixes

# Friendly failure-type name -> canonical crackerjack.services.regex_patterns
# SAFE_PATTERNS key. Order matters: it is match-priority order when a
# message could match more than one pattern (mirrors the original
# TestSpecialistAgent.__init__'s common_test_patterns dict literal order).
_FAILURE_PATTERN_NAMES: dict[str, str] = {
    "fixture_not_found": "fixture_not_found_pattern",
    "import_error": "import_error_pattern",
    "assertion_error": "assertion_error_pattern",
    "attribute_error": "attribute_error_pattern",
    "mock_spec_error": "mock_spec_error_pattern",
    "hardcoded_path": "hardcoded_path_pattern",
    "missing_import": "missing_name_pattern",
    "pydantic_validation": "pydantic_validation_pattern",
}


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


def _identify_failure_type(issue: Issue) -> str:
    message = issue.message

    for failure_type, pattern_name in _FAILURE_PATTERN_NAMES.items():
        if SAFE_PATTERNS[pattern_name].test(message):
            return failure_type

    return "unknown"


def _is_valid_file_path(file_path: str | None) -> bool:
    return file_path is not None and Path(file_path).exists()


def _needs_pytest_import(content: str) -> bool:
    return "pytest" not in content and "import pytest" not in content


def _needs_pathlib_import(content: str) -> bool:
    return "Path(" in content and "from pathlib import Path" not in content


def _needs_mock_import(content: str) -> bool:
    return "Mock()" in content and "from unittest.mock import Mock" not in content


def _find_import_section_end(lines: list[str]) -> int:
    import_section_end = 0
    for i, line in enumerate(lines):
        if line.strip().startswith(("import ", "from ")):
            import_section_end = i + 1
        elif line.strip() == "" and import_section_end > 0:
            break
    return import_section_end


def _add_pytest_import(lines: list[str]) -> None:
    import_section_end = _find_import_section_end(lines)
    lines.insert(import_section_end, "import pytest")


def _apply_import_fixes(
    lines: list[str],
    content: str,
    file_path: str,
) -> tuple[list[str], bool]:
    fixes: list[str] = []
    modified = False

    if _needs_pytest_import(content):
        _add_pytest_import(lines)
        fixes.append(f"Added missing pytest import to {file_path}")
        modified = True

    if _needs_pathlib_import(content):
        lines.insert(0, "from pathlib import Path")
        fixes.append(f"Added missing pathlib import to {file_path}")
        modified = True

    if _needs_mock_import(content):
        lines.insert(0, "from unittest.mock import Mock")
        fixes.append(f"Added missing Mock import to {file_path}")
        modified = True

    return fixes, modified


def _save_import_fixes(
    file_path: Path,
    lines: list[str],
    file_path_str: str,
) -> None:
    _write_file(file_path, "\n".join(lines))


async def _fix_import_errors(issue: Issue) -> list[str]:
    if not _is_valid_file_path(issue.file_path) or issue.file_path is None:
        return []

    file_path = Path(issue.file_path)
    content = _read_file(file_path)
    if not content:
        return []

    lines = content.split("\n")
    fixes, modified = _apply_import_fixes(lines, content, issue.file_path)

    if modified:
        _save_import_fixes(file_path, lines, issue.file_path)

    return fixes


async def _fix_hardcoded_paths(issue: Issue) -> list[str]:
    fixes: list[str] = []

    if not issue.file_path:
        return fixes

    file_path = Path(issue.file_path)
    content = _read_file(file_path)
    if not content:
        return fixes

    original_content = content

    content = (
        content.replace('Path("/test/path")', "tmp_path")
        .replace('"/test/path"', "tmp_path")
        .replace("'/test/path'", "tmp_path")
    )

    if content != original_content and _write_file(file_path, content):
        fixes.append(f"Fixed hardcoded paths in {issue.file_path}")

    return fixes


def _is_valid_mock_issue_file(file_path: str | None) -> bool:
    return file_path is not None


def _needs_console_mock_fix(content: str) -> bool:
    return "console = Mock()" in content and "Console" not in content


def _add_console_import_to_lines(lines: list[str]) -> list[str]:
    for i, line in enumerate(lines):
        if line.startswith("from rich") or "rich" in line:
            lines.insert(i + 1, "from rich.console import Console")
            return lines

    lines.insert(0, "from rich.console import Console")
    return lines


def _ensure_console_import(content: str) -> str:
    if "from rich.console import Console" in content:
        return content

    lines = content.split("\n")
    lines = _add_console_import_to_lines(lines)
    return "\n".join(lines)


def _fix_console_mock_usage(content: str) -> str:
    content = content.replace("console = Mock()", "console = Console()")
    return _ensure_console_import(content)


def _apply_mock_fixes_to_content(
    content: str,
    file_path: str,
) -> tuple[str, list[str]]:
    fixes: list[str] = []

    if _needs_console_mock_fix(content):
        content = _fix_console_mock_usage(content)
        fixes.append(f"Fixed Mock usage in {file_path}")

    return content, fixes


def _save_mock_fixes(
    file_path: Path,
    content: str,
    file_path_str: str,
) -> None:
    _write_file(file_path, content)


async def _fix_mock_issues(issue: Issue) -> list[str]:
    fixes: list[str] = []

    if not _is_valid_mock_issue_file(issue.file_path) or issue.file_path is None:
        return fixes

    file_path = Path(issue.file_path)
    content = _read_file(file_path)
    if not content:
        return fixes

    original_content = content
    content, mock_fixes = _apply_mock_fixes_to_content(content, issue.file_path)
    fixes.extend(mock_fixes)

    if content != original_content:
        _save_mock_fixes(file_path, content, issue.file_path)

    return fixes


async def _fix_pydantic_issues(issue: Issue) -> list[str]:
    # Preserved verbatim from TestSpecialistAgent._fix_pydantic_issues: this
    # is a real dispatch target (_apply_targeted_fixes routes
    # "pydantic_validation" failures here) but it has always been a no-op
    # stub -- no templated fix was ever implemented for Pydantic validation
    # errors. Not fixed, per CLAUDE.md Rule 7.
    return []


async def _add_temp_pkg_path_fixture(file_path: str | None) -> list[str]:
    if not file_path:
        return []

    fixes: list[str] = []
    path = Path(file_path)
    content = _read_file(path)
    if not content:
        return fixes

    if "@pytest.fixture" in content and "temp_pkg_path" in content:
        return fixes

    fixture_code = '''
@pytest.fixture
def temp_pkg_path(tmp_path) -> Path:
    """Create temporary package path."""
    return tmp_path
'''

    lines = content.split("\n")

    for i, line in enumerate(lines):
        if line.startswith("class Test") and i > 0:
            lines.insert(i + 1, fixture_code)
            break
    else:
        lines.append(fixture_code)

    if _write_file(path, "\n".join(lines)):
        fixes.append(f"Added temp_pkg_path fixture to {file_path}")

    return fixes


async def _add_console_fixture(file_path: str | None) -> list[str]:
    if not file_path:
        return []

    fixes: list[str] = []
    path = Path(file_path)
    content = _read_file(path)
    if not content:
        return fixes

    fixture_code = '''
@pytest.fixture
def console() -> Console:
    """Create console instance for testing."""
    return Console()
'''

    lines = content.split("\n")
    lines.append(fixture_code)

    if "from rich.console import Console" not in content:
        lines.insert(0, "from rich.console import Console")

    if _write_file(path, "\n".join(lines)):
        fixes.append(f"Added console fixture to {file_path}")

    return fixes


async def _add_temp_path_fixture(file_path: str | None) -> list[str]:
    return [
        f"Note: tmp_path is a built-in pytest fixture - check fixture usage in {file_path}",
    ]


async def _fix_missing_fixtures(issue: Issue) -> list[str]:
    fixes: list[str] = []

    fixture_pattern = SAFE_PATTERNS["fixture_not_found_pattern"]
    if not fixture_pattern.test(issue.message):
        return fixes

    match = fixture_pattern.search(issue.message)
    if not match:
        return fixes

    fixture_name = match.group(1)

    if fixture_name == "temp_pkg_path":
        fixes.extend(await _add_temp_pkg_path_fixture(issue.file_path))
    elif fixture_name == "console":
        fixes.extend(await _add_console_fixture(issue.file_path))
    elif fixture_name in ("tmp_path", "tmpdir"):
        fixes.extend(await _add_temp_path_fixture(issue.file_path))

    return fixes


async def _fix_test_file_issues(file_path: str) -> list[str]:
    fixes: list[str] = []

    path = Path(file_path)
    content = _read_file(path)
    if not content:
        return fixes

    original_content = content

    if "import pytest" not in content:
        lines = content.split("\n")
        lines.insert(0, "import pytest")
        content = "\n".join(lines)
        fixes.append(f"Added pytest import to {file_path}")

    content = apply_test_fixes(content)

    if content != original_content:
        _write_file(path, content)

    return fixes


async def _apply_general_test_fixes(project_root: Path) -> list[str]:
    fixes: list[str] = []

    returncode, _, stderr = await _run_command(
        ["uv", "run", "python", "-m", "pytest", "--collect-only", "-q"],
        cwd=project_root,
    )

    if returncode != 0 and "ImportError" in stderr:
        fixes.append("Identified import issues in test collection")

    return fixes


async def _apply_targeted_fixes(failure_type: str, issue: Issue) -> list[str]:
    if failure_type == "fixture_not_found":
        return await _fix_missing_fixtures(issue)
    if failure_type == "import_error":
        return await _fix_import_errors(issue)
    if failure_type == "hardcoded_path":
        return await _fix_hardcoded_paths(issue)
    if failure_type == "mock_spec_error":
        return await _fix_mock_issues(issue)
    if failure_type == "pydantic_validation":
        return await _fix_pydantic_issues(issue)
    return []


async def _apply_file_fixes(issue: Issue) -> tuple[list[str], bool]:
    if not issue.file_path or not (
        "test_" in issue.file_path or "/tests/" in issue.file_path
    ):
        return [], False

    file_fixes = await _fix_test_file_issues(issue.file_path)
    # Preserved verbatim from TestSpecialistAgent._apply_file_fixes:
    # the second tuple element is the *list* itself (not bool(file_fixes)),
    # so ``modified is fixes`` at the call site holds whenever fixes were
    # applied. See module docstring quirk 1 for context.
    return file_fixes, file_fixes  # ty: ignore[invalid-return-type]


def _get_failure_recommendations(fixes_applied: list[str]) -> list[str]:
    if fixes_applied:
        return []

    return [
        "Check test file imports and fixture definitions",
        "Verify mock objects are properly configured",
        "Ensure test data paths use tmp_path fixture",
        "Review assertion statements for correctness",
    ]


def _create_fix_result(
    fixes_applied: list[str],
    files_modified: list[str],
    recommendations: list[str],
) -> FixResult:
    success = bool(fixes_applied)
    confidence = 0.8 if success else 0.4

    return FixResult(
        success=success,
        confidence=confidence,
        fixes_applied=fixes_applied,
        files_modified=files_modified,
        recommendations=recommendations,
    )


def _create_error_fix_result(error: Exception) -> FixResult:
    return FixResult(
        success=False,
        confidence=0.0,
        remaining_issues=[f"Failed to fix test issue: {error}"],
    )


async def _apply_issue_fixes(
    issue: Issue, project_root: Path
) -> tuple[list[str], list[str]]:
    fixes_applied: list[str] = []
    files_modified: list[str] = []

    failure_type = _identify_failure_type(issue)

    targeted_fixes = await _apply_targeted_fixes(failure_type, issue)
    fixes_applied.extend(targeted_fixes)

    file_fixes, file_modified = await _apply_file_fixes(issue)
    fixes_applied.extend(file_fixes)
    if file_modified and issue.file_path:
        files_modified.append(issue.file_path)

    general_fixes = await _apply_general_test_fixes(project_root)
    fixes_applied.extend(general_fixes)

    return fixes_applied, files_modified


async def fix_test_issue(issue: Issue, project_root: Path) -> FixResult:
    try:
        fixes_applied, files_modified = await _apply_issue_fixes(issue, project_root)
        recommendations = _get_failure_recommendations(fixes_applied)

        return _create_fix_result(fixes_applied, files_modified, recommendations)

    except Exception as e:
        return _create_error_fix_result(e)


__all__ = [
    "fix_test_issue",
]

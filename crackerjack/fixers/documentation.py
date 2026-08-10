"""Deterministic changelog-generation and documentation-consistency fixer.

Extracted from ``crackerjack.agents.documentation_agent.DocumentationAgent``,
which (like ``SecurityAgent``) does not delegate to any ``agents/helpers/*``
class -- it is fully self-contained. Confirmed empirically (full read of the
888-line source file): zero LLM/bridge/coordinator references anywhere in
the class.

What was intentionally dropped versus the original ``DocumentationAgent``:

- ``SubAgent``/coordinator dispatch plumbing: ``get_supported_types`` and
  ``can_handle`` -- these only ever decided *whether* and *how confidently*
  this fixer should run for a given ``Issue``; that routing job belongs to
  whatever calls into this module now, not to the module itself.
- ``agent_registry.register(DocumentationAgent)`` -- registry plumbing.
- ``self.log(...)`` calls throughout -- ``SubAgent.log`` is a no-op ``pass``
  on the base class, so these calls had no observable effect (same
  treatment as ``crackerjack/fixers/security.py``/``performance.py``).
- ``AgentContext``-specific file I/O: ``AgentContext.get_file_content``'s /
  ``write_file_content``'s path-traversal checks -- replaced with direct
  ``pathlib.Path`` reads/writes via ``_read_file``/``_write_file`` below
  (same helpers, byte-for-byte, as ``security.py``). Real file I/O is still
  performed; only the framework wrapper around it is gone. The original's
  trivial ``_read_file_content`` method (a one-line passthrough to
  ``self.context.get_file_content``) is dropped in favor of calling
  ``_read_file`` directly at its one call site.
- ``AgentContext.project_path``: threaded through explicitly as a
  ``project_root: Path`` parameter on ``execute_fix_plan``,
  ``fix_documentation_issue``, and the broken-link-fixing call chain
  (``_fix_broken_link_from_plan``, ``_fix_broken_link``,
  ``_fix_or_remove_broken_link_line``, ``_attempt_link_fix``,
  ``_find_and_fix_link``, ``_find_best_link_target``) rather than dropped,
  since ``_find_best_link_target``'s project-wide fuzzy file search is real,
  tested logic that depends on knowing the project root (unlike
  ``security.py``'s ``_get_python_files_for_security_scan``, which could
  fall back to relying on ``get_files_by_extension``'s own git-root
  detection).
- ``_find_line_with_target``'s dead ``re.escape(target_file)`` statement
  (its result was never used) -- a pure, side-effect-free call whose removal
  changes nothing observable; dropped as inert dead code, not a behavioral
  simplification.

Task 22a fix: ``_get_commit_range``/``_get_commit_messages``/
``_detect_api_changes`` ran bare ``git describe``/``git log``/``git diff``
via ``subprocess.run`` with no ``cwd=`` and no project-path parameter
anywhere in their signatures -- a more severe instance of the same
cwd-pinning gap flagged (via docstring) in ``formatting.py``/``security.py``/
``test_specialist.py``, since these three had no parameter to thread through
at all. Task 22a added a ``project_root: Path`` parameter to all three and
their callers (``_get_recent_changes``, ``_update_changelog``,
``_update_api_documentation``), wired from ``fix_documentation_issue``'s and
``execute_fix_plan``'s existing ``project_root`` parameter (the latter via
the newly-parameterized ``_update_changelog_from_plan``). Judged in-scope
despite not matching the brief's literal "``_run_command``-style helper"
phrasing: it is the same root bug class (subprocess relying on ambient cwd
instead of an explicit project root), and arguably more severe here since
``git describe``/``git log`` would silently operate against whatever git
repository the ambient process happens to be inside, if any.

Renames worth noting for anyone diffing against the original: the
``SubAgent.analyze_and_fix`` entry point becomes ``fix_documentation_issue``
below (same dispatch flow, minus the ``self``/``AgentContext`` plumbing).

``execute_fix_plan`` is kept (per the plan's precedent: ``DocumentationAgent``
is one of four agent classes -- alongside ``ArchitectAgent``,
``SecurityAgent``, and ``FormattingAgent`` -- with its own
``FixPlan``/``ChangeSpec`` applicator, independent of ``planning_agent.py``'s
plan-construction logic).

Pre-existing quirks preserved verbatim, not fixed, per CLAUDE.md Rule 7
("preserve functional requirements... fix the technical issue, not the
requirements"):

1. ``_update_changelog_from_plan`` constructs an ``Issue`` with
   ``severity=plan.risk_level`` -- a ``str`` (``"low"``/``"medium"``/
   ``"high"``), not a ``Priority`` enum member. ``Issue`` is a plain
   dataclass with no runtime validation, so this "works" at runtime despite
   the type mismatch (marked ``# type: ignore`` in the original, preserved
   here).
2. ``_update_changelog``, ``_fix_documentation_consistency``, and
   ``_update_api_documentation`` each put a ``pathlib.Path`` object (not a
   ``str``) into ``FixResult.files_modified`` (typed ``list[str]``) --
   ``changelog_path``, the ``md_files`` entry, and ``readme_path``
   respectively (each marked ``# type: ignore`` in the original, preserved
   here). Contrast this with the broken-link-fixing functions
   (``_fix_broken_link_from_plan``/``_fix_broken_link``/
   ``_write_fixed_content``/``_apply_fix_plan_changes``), which already
   receive ``file_path`` as a ``str`` and so don't exhibit this quirk.
"""

from __future__ import annotations

import os
import re
import subprocess
import typing as t
from contextlib import suppress
from datetime import datetime
from pathlib import Path

from crackerjack.models.fix_plan import ChangeSpec, FixPlan
from crackerjack.models.issues import FixResult, Issue, IssueType
from crackerjack.services.regex_patterns import SAFE_PATTERNS


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


def _create_error_result(message: str) -> FixResult:
    return FixResult(
        success=False,
        confidence=0.0,
        remaining_issues=[message],
    )


# ---------------------------------------------------------------------------
# execute_fix_plan / broken-link plan detection
# ---------------------------------------------------------------------------


def _is_broken_link_plan(plan: FixPlan) -> bool:
    rationale_lower = plan.rationale.lower()
    return (
        "broken link" in rationale_lower
        or "file not found" in rationale_lower
        or ("link" in rationale_lower and "fix" in rationale_lower)
    )


def _extract_target_from_rationale(rationale: str) -> str | None:
    match = re.search(r"File not found:\s*([^\s\-]+)", rationale, re.IGNORECASE)
    if match:
        return match.group(1).strip()

    match = re.search(r"Broken link:\s*([^\s\-]+)", rationale, re.IGNORECASE)
    if match:
        return match.group(1).strip()

    match = re.search(r"link to\s+([^\s]+)", rationale, re.IGNORECASE)
    if match:
        return match.group(1).strip()

    match = re.search(r"([\.\/][^\s]*\.(md|rst|txt|html))", rationale)
    if match:
        return match.group(1).strip()

    return None


def _find_line_with_target(content: str, target_file: str) -> int | None:
    lines = content.split("\n")

    for i, line in enumerate(lines):
        if target_file in line and "](" in line:
            return i + 1

    return None


def _apply_fix_plan_changes(plan: FixPlan, content: str) -> FixResult:
    lines = content.split("\n")

    sorted_changes = sorted(plan.changes, key=lambda c: c.line_range[0], reverse=True)

    for change in sorted_changes:
        start_line = change.line_range[0] - 1
        end_line = change.line_range[1] - 1

        if start_line < 0 or end_line >= len(lines):
            continue

        new_lines = change.new_code.split("\n")
        lines[start_line : end_line + 1] = new_lines

    updated_content = "\n".join(lines)
    success = _write_file(plan.file_path, updated_content)

    if success:
        return FixResult(
            success=True,
            confidence=0.9,
            fixes_applied=[f"Applied {len(plan.changes)} fixes to {plan.file_path}"],
            files_modified=[plan.file_path],
        )

    return _create_error_result(f"Failed to write fixed content to {plan.file_path}")


async def _update_changelog_from_plan(plan: FixPlan, project_root: Path) -> FixResult:
    issue = Issue(
        type=IssueType.DOCUMENTATION,
        severity=plan.risk_level,  # type: ignore
        message=plan.rationale,
        file_path=plan.file_path,
    )
    return await _update_changelog(issue, project_root)


async def _fix_broken_link_from_plan(plan: FixPlan, project_root: Path) -> FixResult:
    target_file = _extract_target_from_rationale(plan.rationale)

    line_number = None
    if plan.changes:
        line_number = plan.changes[0].line_range[0]

    content = _read_file(plan.file_path)
    if content is None:
        return _create_error_result(f"Failed to read {plan.file_path}")

    if plan.changes:
        return _apply_fix_plan_changes(plan, content)

    if line_number is None and target_file:
        line_number = _find_line_with_target(content, target_file)

    updated_content = _fix_or_remove_broken_link_line(
        content, plan.file_path, line_number, target_file, project_root
    )

    return _write_fixed_content(plan.file_path, updated_content, target_file)


async def execute_fix_plan(plan: FixPlan, project_root: Path) -> FixResult:
    if _is_broken_link_plan(plan):
        return await _fix_broken_link_from_plan(plan, project_root)

    if "changelog" in plan.rationale.lower():
        return await _update_changelog_from_plan(plan, project_root)

    return FixResult(
        success=True,
        confidence=0.6,
        recommendations=[
            f"Documentation issue in {plan.file_path}: {plan.rationale}",
            "Manual review recommended for optimal documentation updates",
        ],
    )


# ---------------------------------------------------------------------------
# fix_documentation_issue dispatch (was SubAgent.analyze_and_fix)
# ---------------------------------------------------------------------------


async def fix_documentation_issue(issue: Issue, project_root: Path) -> FixResult:
    try:
        if (
            "broken documentation link" in issue.message.lower()
            or "broken link" in issue.message.lower()
            or "file not found" in issue.message.lower()
        ):
            return await _fix_broken_link(issue, project_root)
        if "changelog" in issue.message.lower():
            return await _update_changelog(issue, project_root)
        if (
            "agent count" in issue.message.lower()
            or "consistency" in issue.message.lower()
        ):
            return await _fix_documentation_consistency(issue)
        if "api" in issue.message.lower() or "readme" in issue.message.lower():
            return await _update_api_documentation(issue, project_root)
        return await _general_documentation_update(issue)

    except Exception as e:
        return FixResult(
            success=False,
            confidence=0.0,
            remaining_issues=[f"Error processing documentation: {e}"],
        )


# ---------------------------------------------------------------------------
# Changelog updating
# ---------------------------------------------------------------------------


async def _update_changelog(issue: Issue, project_root: Path) -> FixResult:
    changelog_path = Path("CHANGELOG.md")

    recent_changes = _get_recent_changes(project_root)

    if not recent_changes:
        return FixResult(
            success=True,
            confidence=0.7,
            recommendations=["No recent changes to add to changelog"],
        )

    changelog_entry = _generate_changelog_entry(recent_changes)

    if changelog_path.exists():
        content = _read_file(changelog_path)
        if content is None:
            return FixResult(
                success=False,
                confidence=0.0,
                remaining_issues=[f"Failed to read {changelog_path}"],
            )
        updated_content = _insert_changelog_entry(content, changelog_entry)
    else:
        updated_content = _create_initial_changelog(changelog_entry)

    success = _write_file(changelog_path, updated_content)

    if success:
        return FixResult(
            success=True,
            confidence=0.9,
            fixes_applied=[
                f"Updated CHANGELOG.md with {len(recent_changes)} recent changes",
            ],
            files_modified=[changelog_path],  # type: ignore
        )

    return FixResult(
        success=False,
        confidence=0.0,
        remaining_issues=["Failed to write changelog updates"],
    )


async def _fix_documentation_consistency(issue: Issue) -> FixResult:
    md_files = list[t.Any](Path().glob("*.md")) + list[t.Any](
        Path("docs").glob("*.md"),
    )

    agent_count_issues = _check_agent_count_consistency(md_files)

    files_modified: list[str] = []
    fixes_applied: list[str] = []

    for file_path, current_count, expected_count in agent_count_issues:
        content = _read_file(file_path)
        if content:
            updated_content = _fix_agent_count_references(
                content,
                current_count,
                expected_count,
            )
            if updated_content != content:
                success = _write_file(
                    file_path,
                    updated_content,
                )
                if success:
                    files_modified.append(file_path)  # type: ignore
                    fixes_applied.append(f"Updated agent count in {file_path.name}")

    if files_modified:
        return FixResult(
            success=True,
            confidence=0.85,
            fixes_applied=fixes_applied,
            files_modified=files_modified,
        )

    return FixResult(
        success=True,
        confidence=0.8,
        recommendations=["Documentation is already consistent"],
    )


async def _update_api_documentation(issue: Issue, project_root: Path) -> FixResult:
    api_changes = _detect_api_changes(project_root)

    if not api_changes:
        return FixResult(
            success=True,
            confidence=0.7,
            recommendations=[
                "No API changes detected requiring documentation updates",
            ],
        )

    readme_path = Path("README.md")
    if readme_path.exists():
        content = _read_file(readme_path)
        if content is None:
            return FixResult(
                success=False,
                confidence=0.0,
                remaining_issues=[f"Failed to read {readme_path}"],
            )
        updated_content = _update_readme_examples(content, api_changes)

        if updated_content != content:
            success = _write_file(readme_path, updated_content)
            if success:
                return FixResult(
                    success=True,
                    confidence=0.8,
                    fixes_applied=["Updated README.md examples for API changes"],
                    files_modified=[readme_path],  # type: ignore
                )

    return FixResult(
        success=False,
        confidence=0.5,
        remaining_issues=["Could not update API documentation"],
        recommendations=["Manual review of API documentation may be needed"],
    )


async def _general_documentation_update(issue: Issue) -> FixResult:
    return FixResult(
        success=False,
        confidence=0.0,
        recommendations=[
            f"Documentation issue identified: {issue.message}",
            "Manual review recommended for optimal documentation updates",
            "Consider adding specific patterns to DocumentationAgent",
        ],
        remaining_issues=["no automated fix path for this documentation issue"],
    )


# ---------------------------------------------------------------------------
# git-log-based changelog generation
# ---------------------------------------------------------------------------


def _get_recent_changes(project_root: Path) -> list[dict[str, str]]:
    try:
        commit_range = _get_commit_range(project_root)
        if not commit_range:
            return []

        commit_messages = _get_commit_messages(commit_range, project_root)
        return _parse_commit_messages(commit_messages)

    except Exception:
        return []


def _get_commit_range(project_root: Path) -> str:
    result = subprocess.run(
        ["git", "describe", "--tags", "--abbrev=0"],
        cwd=project_root,
        capture_output=True,
        text=True,
        check=False,
    )

    if result.returncode == 0:
        last_tag = result.stdout.strip()
        return f"{last_tag}..HEAD"

    return "-10"


def _get_commit_messages(commit_range: str, project_root: Path) -> str:
    result = subprocess.run(
        ["git", "log", commit_range, "--pretty=format: %s|%h|%an"],
        cwd=project_root,
        capture_output=True,
        text=True,
        check=False,
    )

    return result.stdout.strip() if result.returncode == 0 else ""


def _parse_commit_messages(commit_output: str) -> list[dict[str, str]]:
    changes: list[dict[str, str]] = []

    for line in commit_output.split("\n"):
        if line:
            parts = line.split("|")
            if len(parts) >= 2:
                change_info: dict[str, str] = {
                    "message": parts[0].strip(),
                    "hash": parts[1].strip(),
                    "author": parts[2].strip() if len(parts) > 2 else "Unknown",
                }
                changes.append(change_info)

    return changes


def _generate_changelog_entry(changes: list[dict[str, str]]) -> str:
    date_str = datetime.now().strftime("%Y-%m-%d")
    entry_lines = [f"## [Unreleased] - {date_str}", ""]

    categorized_changes = _categorize_changes(changes)
    _add_categorized_changes_to_entry(entry_lines, categorized_changes)

    return "\n".join(entry_lines)


def _categorize_changes(
    changes: list[dict[str, str]],
) -> dict[str, list[str]]:
    categories: dict[str, list[str]] = {
        "features": [],
        "fixes": [],
        "refactors": [],
        "other": [],
    }

    for change in changes:
        message = change["message"]
        category = _get_change_category(message)
        categories[category].append(message)

    return categories


def _get_change_category(message: str) -> str:
    if message.startswith(("feat: ", "feature: ")):
        return "features"
    if message.startswith("fix: "):
        return "fixes"
    if message.startswith(("refactor: ", "refact: ")):
        return "refactors"
    return "other"


def _add_categorized_changes_to_entry(
    entry_lines: list[str],
    categories: dict[str, list[str]],
) -> None:
    section_mappings = {
        "features": "### Added",
        "fixes": "### Fixed",
        "refactors": "### Changed",
        "other": "### Other",
    }

    for category, section_title in section_mappings.items():
        items = categories[category]
        if items:
            _add_section_to_entry(entry_lines, section_title, items)


def _add_section_to_entry(
    entry_lines: list[str],
    section_title: str,
    items: list[str],
) -> None:
    entry_lines.append(section_title)
    for item in items:
        entry_lines.extend((f"- {item}", ""))


def _insert_changelog_entry(content: str, entry: str) -> str:
    lines = content.split("\n")

    insert_index = 0
    for i, line in enumerate(lines):
        if line.startswith(("# ", "## ")) and i > 0:
            insert_index = i
            break

    new_lines = lines[:insert_index] + entry.split("\n") + [""] + lines[insert_index:]
    return "\n".join(new_lines)


def _create_initial_changelog(entry: str) -> str:
    return f"""# Changelog

All notable changes to this project will be documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.0.0/),
and this project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

{entry}
"""


# ---------------------------------------------------------------------------
# Agent-count documentation consistency
# ---------------------------------------------------------------------------


def _check_agent_count_consistency(
    md_files: list[Path],
) -> list[tuple[Path, int, int]]:
    expected_count = 9
    issues: list[tuple[Path, int, int]] = []
    patterns = _get_agent_count_patterns()

    for file_path in md_files:
        issue = _check_file_agent_count(file_path, patterns, expected_count)
        if issue:
            issues.append(issue)

    return issues


def _get_agent_count_patterns() -> list[str]:
    return [
        SAFE_PATTERNS["agent_count_pattern"].pattern,
        SAFE_PATTERNS["specialized_agent_count_pattern"].pattern,
        SAFE_PATTERNS["total_agents_config_pattern"].pattern,
        SAFE_PATTERNS["sub_agent_count_pattern"].pattern,
    ]


def _check_file_agent_count(
    file_path: Path,
    patterns: list[str],
    expected_count: int,
) -> tuple[Path, int, int] | None:
    with suppress(Exception):
        content = _read_file(file_path)
        if not content:
            return None

        return _analyze_file_content_for_agent_count(
            file_path,
            content,
            patterns,
            expected_count,
        )

    return None


def _analyze_file_content_for_agent_count(
    file_path: Path,
    content: str,
    patterns: list[str],
    expected_count: int,
) -> tuple[Path, int, int] | None:
    pattern_map = _get_safe_pattern_map()

    for pattern in patterns:
        result = _check_pattern_for_count_mismatch(
            pattern,
            pattern_map,
            content,
            file_path,
            expected_count,
        )
        if result:
            return result

    return None


def _get_safe_pattern_map() -> dict[str, str]:
    return {
        SAFE_PATTERNS["agent_count_pattern"].pattern: "agent_count_pattern",
        SAFE_PATTERNS[
            "specialized_agent_count_pattern"
        ].pattern: "specialized_agent_count_pattern",
        SAFE_PATTERNS[
            "total_agents_config_pattern"
        ].pattern: "total_agents_config_pattern",
        SAFE_PATTERNS["sub_agent_count_pattern"].pattern: "sub_agent_count_pattern",
    }


def _check_pattern_for_count_mismatch(
    pattern: str,
    pattern_map: dict[str, str],
    content: str,
    file_path: Path,
    expected_count: int,
) -> tuple[Path, int, int] | None:
    if pattern not in pattern_map:
        return None

    safe_pattern = SAFE_PATTERNS[pattern_map[pattern]]
    if not safe_pattern.test(content):
        return None

    return _find_count_mismatch_in_matches(
        safe_pattern,
        content,
        file_path,
        expected_count,
    )


def _find_count_mismatch_in_matches(
    safe_pattern: t.Any,
    content: str,
    file_path: Path,
    expected_count: int,
) -> tuple[Path, int, int] | None:
    matches = safe_pattern.findall(content)

    for match in matches:
        count = int(match)
        if _is_count_mismatch(count, expected_count):
            return (file_path, count, expected_count)

    return None


def _is_count_mismatch(count: int, expected_count: int) -> bool:
    return count != expected_count and count > 4


def _fix_agent_count_references(
    content: str,
    current_count: int,
    expected_count: int,
) -> str:
    updated_content = content

    agent_pattern = SAFE_PATTERNS["update_agent_count"]
    specialized_pattern = SAFE_PATTERNS["update_specialized_agent_count"]
    config_pattern = SAFE_PATTERNS["update_total_agents_config"]
    sub_agent_pattern = SAFE_PATTERNS["update_sub_agent_count"]

    updated_content = agent_pattern.apply(updated_content).replace(
        "NEW_COUNT",
        str(expected_count),
    )
    updated_content = specialized_pattern.apply(updated_content).replace(
        "NEW_COUNT",
        str(expected_count),
    )
    updated_content = config_pattern.apply(updated_content).replace(
        "NEW_COUNT",
        str(expected_count),
    )
    return sub_agent_pattern.apply(updated_content).replace(
        "NEW_COUNT",
        str(expected_count),
    )


def _detect_api_changes(project_root: Path) -> list[dict[str, str]]:
    try:
        result = subprocess.run(
            ["git", "diff", "--name-only", "HEAD~5..HEAD", "*.py"],
            cwd=project_root,
            capture_output=True,
            text=True,
            check=False,
        )

        if result.returncode != 0:
            return []

        changed_files = result.stdout.strip().split("\n")
        api_changes: list[dict[str, str]] = []

        for file_path in changed_files:
            if file_path and ("api" in file_path.lower() or "__init__" in file_path):
                change_info: dict[str, str] = {
                    "file": file_path,
                    "type": "potential_api_change",
                }
                api_changes.append(change_info)

        return api_changes

    except Exception:
        return []


def _update_readme_examples(
    content: str,
    api_changes: list[dict[str, str]],
) -> str:
    if api_changes and "TODO: Update examples" not in content:
        lines = content.split("\n")

        for i, line in enumerate(lines):
            if line.startswith("# ") and i < len(lines) - 1:
                lines.insert(
                    i + 2,
                    "<!-- TODO: Update examples after recent API changes -->",
                )
                break
        return "\n".join(lines)

    return content


# ---------------------------------------------------------------------------
# Broken-link fixing (Issue path)
# ---------------------------------------------------------------------------


async def _fix_broken_link(issue: Issue, project_root: Path) -> FixResult:
    if not issue.file_path:
        return _create_error_result("No file path provided for broken link fix")

    target_file = _extract_target_file_from_details(issue.details)
    content = _read_file(issue.file_path)
    if content is None:
        return _create_error_result(f"Failed to read {issue.file_path}")

    updated_content = _fix_or_remove_broken_link_line(
        content, issue.file_path, issue.line_number, target_file, project_root
    )

    return _write_fixed_content(issue.file_path, updated_content, target_file)


def _extract_target_file_from_details(details: list[str]) -> str | None:
    patterns = [
        r"Target file:\s*(.+)$",
        r"File not found:\s*(.+?)(?:\s*-\s*Broken link.*)?$",
        r"Broken link:\s*(.+?)(?:\s*-\s*Broken link.*)?$",
        r"Target path:\s*(.+)$",
        r"Path:\s*(.+)$",
    ]
    for detail in details:
        for pattern in patterns:
            match = re.search(pattern, detail, re.IGNORECASE)
            if match:
                return match.group(1).strip()
    return None


def _fix_or_remove_broken_link_line(
    content: str,
    file_path: str,
    line_number: int | None,
    target_file: str | None,
    project_root: Path,
) -> str:
    lines = content.split("\n")
    updated_lines = []
    fixed = False

    for i, line in enumerate(lines):
        should_fix = False
        if (
            line_number is not None
            and i + 1 == line_number
            or target_file
            and not fixed
            and target_file in line
        ):
            should_fix = True

        if should_fix:
            fixed_line = _attempt_link_fix(
                target_file, line, file_path, i + 1, project_root
            )
            if fixed_line is not None:
                updated_lines.append(fixed_line)
                fixed = True

        else:
            updated_lines.append(line)

    return "\n".join(updated_lines)


def _attempt_link_fix(
    target_file: str | None,
    line: str,
    file_path: str,
    line_number: int | None,
    project_root: Path,
) -> str | None:
    if target_file:
        fixed_link = _find_and_fix_link(target_file, line, file_path, project_root)
        if fixed_link != line:
            return fixed_link

    return None


def _write_fixed_content(
    file_path: str, updated_content: str, target_file: str | None
) -> FixResult:
    success = _write_file(file_path, updated_content)

    if not success:
        return _create_error_result(f"Failed to write fixed content to {file_path}")

    message = _create_success_message(file_path, target_file)
    return FixResult(
        success=True,
        confidence=0.85,
        fixes_applied=[message],
        files_modified=[file_path],
    )


def _create_success_message(file_path: str, target_file: str | None) -> str:
    if target_file:
        return f"Fixed broken link to '{target_file}' in {file_path}"
    return f"Removed broken link from {file_path}"


def _find_and_fix_link(
    target_file: str, line: str, source_file: str, project_root: Path
) -> str:
    search_paths = [
        Path(target_file),
        Path("docs") / target_file,
        Path("docs") / "reference" / target_file,
        Path("docs") / "features" / target_file,
        Path("docs") / "guides" / target_file,
    ]

    fuzzy_target = _find_best_link_target(target_file, project_root)
    if fuzzy_target is not None:
        search_paths.append(fuzzy_target)

    for path in dict.fromkeys(search_paths):
        if path.exists():
            source_path = Path(source_file).parent
            with suppress(ValueError):
                relative_path = os.path.relpath(path.resolve(), source_path.resolve())
                pattern = _build_link_match_pattern(target_file)

                def replace_link(match: t.Match[str]) -> str:
                    text = match.group(1)
                    return f"[{text}]({relative_path})"

                fixed_line = re.sub(pattern, replace_link, line)
                return fixed_line

    return line


def _find_best_link_target(target_file: str, project_root: Path) -> Path | None:
    target_path = Path(target_file)
    target_name = target_path.name
    if not target_name:
        return None

    candidates: list[Path] = []
    with suppress(Exception):
        search_suffix = target_path.suffix.lower()
        if search_suffix in {".md", ".rst", ".txt", ".html"}:
            candidates = [
                path
                for path in project_root.rglob(f"*{search_suffix}")
                if path.is_file()
            ]
        else:
            candidates = [
                path for path in project_root.rglob(target_name) if path.is_file()
            ]

    if not candidates:
        return None

    target_tokens = _path_tokens(target_path)
    best_path: Path | None = None
    best_score = -1
    best_depth = 1_000_000

    for candidate in candidates:
        candidate_tokens = _path_tokens(candidate)
        suffix_score = _suffix_token_score(target_tokens, candidate_tokens)
        depth_score = len(candidate.relative_to(project_root).parts)

        if suffix_score > best_score or (
            suffix_score == best_score and depth_score < best_depth
        ):
            best_score = suffix_score
            best_depth = depth_score
            best_path = candidate

    return best_path


def _path_tokens(path: Path) -> list[str]:
    tokens: list[str] = []
    for part in path.with_suffix("").parts:
        tokens.extend(
            token for token in re.split(r"[^a-zA-Z0-9]+", part.lower()) if token
        )
    return tokens


def _suffix_token_score(left: list[str], right: list[str]) -> int:
    score = 0
    for left_token, right_token in zip(reversed(left), reversed(right)):
        if left_token != right_token:
            break
        score += 1
    return score


def _build_link_match_pattern(target_file: str) -> str:
    candidates = [re.escape(target_file)]
    target_path = Path(target_file)

    if target_path.is_absolute():
        candidates.append(re.escape(target_path.name))

    target_pattern = "|".join(sorted(set(candidates), key=len, reverse=True))
    return rf"\[([^\]]+)\]\([^)]*(?:{target_pattern})\)"


__all__ = [
    "ChangeSpec",
    "FixPlan",
    "execute_fix_plan",
    "fix_documentation_issue",
]

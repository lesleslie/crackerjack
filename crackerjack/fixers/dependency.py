"""Deterministic pyproject.toml dependency-removal regex fixer.

Extracted from ``crackerjack.agents.dependency_agent.DependencyAgent``, which
(like ``SecurityAgent``/``DeadCodeRemovalAgent``) is self-contained -- it
does not delegate to any ``agents/helpers/*`` class (precedent 1 does not
apply; verified by reading the full 470-line original -- its only imports
are stdlib plus ``.base``).

What was intentionally dropped versus the original ``DependencyAgent``:

- ``SubAgent``/coordinator dispatch plumbing: ``__init__``,
  ``get_supported_types``, and ``can_handle`` -- these only ever decided
  *whether* and *how confidently* this fixer should run for a given
  ``Issue``; that routing job belongs to whatever calls into this module
  now.
- ``_is_likely_lazy_import_false_positive`` (plus the module constants
  ``_LAZY_IMPORT_PACKAGES``/``_STRING_CONTEXT_PACKAGES`` that fed it) --
  this helper has exactly one call site in the original, inside
  ``can_handle``, purely to discount the confidence score for known
  lazily-imported packages. It has zero involvement in the actual
  pyproject.toml edit -- ``analyze_and_fix`` never calls it. Dropped along
  with ``can_handle``, same treatment ``security.py`` gives confidence-only
  helpers.
- ``_is_lazily_imported``, ``_is_string_context_usage``,
  ``_search_source_files``, ``_is_excluded_path``, and
  ``_check_for_false_positive`` -- this entire five-method chain is
  unreachable dead code in the original (confirmed via
  ``grep -rn`` across ``crackerjack/`` and ``tests/``: zero call sites
  anywhere, including from within ``dependency_agent.py`` itself). It looks
  like an earlier, more elaborate false-positive-detection design that was
  superseded by the simpler ``_is_likely_lazy_import_false_positive`` and
  never deleted. Not ported: it has no behavioral surface to preserve.
- ``agent_registry.register(DependencyAgent)`` -- registry plumbing.
- ``AgentContext``-specific file I/O: ``AgentContext.get_file_content``'s
  path-traversal check and file-size cap, and
  ``AgentContext.write_file_content``'s path-traversal check,
  ``wrap_long_lines`` post-processing (a no-op for non-``.py`` files --
  confirmed by reading ``crackerjack/ai_fix/code_post_processor.py``, so it
  never affected ``pyproject.toml`` edits anyway), Python
  syntax/duplicate-top-level-definition validation (also skipped for
  non-``.py`` files), and the post-write read-back-and-compare integrity
  check. Replaced with direct ``pathlib.Path`` reads/writes via
  ``_read_file``/``_write_file`` below, same pattern as
  ``security.py``/``dead_code.py``. Real file I/O is still performed; only
  the framework wrapper around it is gone.

Renamed: ``analyze_and_fix`` -> ``fix_dependency_issue`` (same
validate/extract/read/branch/write flow, minus ``self``/``AgentContext``
plumbing), matching ``fix_dead_code_issue``/``fix_security_issue`` naming in
the sibling modules.

No ``execute_fix_plan`` exists in the original -- none invented here
(precedent 3: keep only if present).

No subprocess-invoking helpers exist in the original (verified: zero
``subprocess``/``run_command`` references anywhere in the file) -- nothing
to add to Task 22a's cwd-pinning file list.

## pyproject.toml editing safety characteristics (preserved verbatim)

This is the one fixer in the series whose job is editing ``pyproject.toml``
rather than Python source, so its safety characteristics are documented
here explicitly (see the task brief's "Special focus"). None of the
following are fixed in this extraction -- they are pre-existing behavior of
``DependencyAgent``, preserved verbatim and pinned by tests:

- **No backup/rollback.** Unlike ``dead_code.py``'s
  ``_backup_file``/``_rollback_file`` pair, there is no backup step
  anywhere in this agent, nor in ``AgentContext.write_file_content`` for
  non-``.py`` files. If the write fails partway through, the original
  content is not recoverable through this code path -- the caller only
  learns that the write failed.
- **No post-edit validation.** ``tomllib.loads`` is only ever used
  *before* editing (in ``_remove_dependency_from_content``, as a
  best-effort existence check against the pre-edit content). The actual
  edit is always a line-based regex/string transform
  (``_remove_dependency_from_toml`` / ``_remove_creosote_exclusion``)
  operating on raw text, and its output is never re-parsed to confirm it is
  still valid TOML before being written back.
- **Imprecise scoping in ``_remove_dependency_from_toml``.**
  ``_update_dependencies_state`` flips "inside a dependencies array" on for
  *any* line containing the substring ``"dependencies"`` plus ``"="``, and
  only flips off at the next ``[section]`` header whose text does *not*
  contain ``"dependencies"``. It does not distinguish
  ``[project.dependencies]`` from ``[project.optional-dependencies]`` (or
  any other ``*dependencies*``-named table) -- verified empirically:
  removing a dependency name that also appears under an unrelated
  ``[project.optional-dependencies]`` table strips it from *both* places,
  because the scanner still considers itself "inside a dependencies block"
  once it has seen any ``...dependencies... = `` line. By contrast,
  ``_remove_creosote_exclusion`` *is* precisely scoped -- it only starts
  looking for exclusions after matching the exact section header
  ``"[tool.creosote]"``.
- **Existence pre-check uses substring containment, not exact matching.**
  ``_remove_dependency_from_deps``'s list branch does
  ``dep_name not in dep`` (a substring test against each dependency
  string), so e.g. checking whether ``"pytest"`` exists returns a false
  positive against an entry like ``"pytest-snob>=0.1.0"``. Verified
  empirically that this does not cause an incorrect *removal*, though: the
  actual edit is always performed by the separately-scoped,
  exact-pattern-matching ``_remove_dependency_from_toml``, which correctly
  finds nothing to remove in that case and returns ``None``. The dict
  branch (a ``[project.dependencies]`` *table* rather than an array --
  non-standard per PEP 621, but tomllib will still parse it) uses exact
  dict-key membership, so it is not affected by this quirk.
"""

from __future__ import annotations

import re
import tomllib
from pathlib import Path

from crackerjack.models.issues import FixResult, Issue


def _extract_dependency_name(message: str | None) -> str | None:
    if not message:
        return None

    clean_message = re.sub(r"\x1b\[[0-9;]*m", "", message)
    # Pre-existing quirk: `{1, 3}` (with a space) is not a valid regex
    # quantifier, so re treats it as literal text. This line is a no-op for
    # any realistic input -- verified empirically against ANSI-coded
    # messages. Preserved verbatim, not fixed.
    clean_message = re.sub(r"\[\\[0-9]{1, 3}m", "", clean_message)

    if "Found dependencies in pyproject.toml:" in clean_message:
        return None
    if "Oh no, bloated venv!" in clean_message:
        return None

    match = re.search(
        r"unused dependency:\s*([a-zA-Z0-9_-]+)$", clean_message, re.IGNORECASE
    )
    if match:
        return match.group(1)

    match = re.search(
        r"dependency\s+['\"]([^'\"]+)['\"]\s+is\s+unused",
        clean_message,
        re.IGNORECASE,
    )
    if match:
        return match.group(1)

    match = re.search(r"^([a-zA-Z0-9_-]+)\s+is\s+unused", clean_message, re.IGNORECASE)
    if match:
        return match.group(1)

    match = re.search(
        r"unused dependencies found:\s*([a-zA-Z0-9_-]+)",
        clean_message,
        re.IGNORECASE,
    )
    if match:
        return match.group(1)

    match = re.search(
        r"[Rr]edundant exclusion\s+['\"]([^'\"]+)['\"]",
        clean_message,
    )
    if match:
        return match.group(1)

    match = re.search(
        r"[Ee]xcluded dependencies not found in virtual environment:\s*"
        r"([a-zA-Z0-9_-]+)",
        clean_message,
    )
    if match:
        return match.group(1)

    match = re.search(r"^([a-zA-Z0-9_-]+)$", clean_message.strip())
    if match and ("-" in match.group(1) or match.group(1).islower()):
        return match.group(1)

    return None


def _remove_dependency_from_toml(content: str, dep_name: str) -> str | None:
    lines = content.splitlines(keepends=True)
    new_lines = []
    in_dependencies = False
    removed = False

    for line in lines:
        in_dependencies = _update_dependencies_state(line, in_dependencies)

        if _should_remove_line(line, dep_name, in_dependencies):
            removed = True
            continue

        new_lines.append(line)

    return "".join(new_lines) if removed else None


def _update_dependencies_state(line: str, current_state: bool) -> bool:
    stripped = line.strip()

    if "dependencies" in line and "=" in line:
        return True

    if current_state and stripped.startswith("[") and "dependencies" not in line:
        return False

    return current_state


def _should_remove_line(line: str, dep_name: str, in_dependencies: bool) -> bool:
    if not in_dependencies:
        return False

    if dep_name not in line:
        return False

    if line.strip().startswith("#"):
        return False

    return _is_dependency_line(line, dep_name)


def _is_dependency_line(line: str, dep_name: str) -> bool:
    patterns = [
        f'"{dep_name}>=',
        f"'{dep_name}>=",
        f'"{dep_name}="',
        f"'{dep_name}='",
        f'"{dep_name}~',
        f"'{dep_name}~",
        f'"{dep_name}^',
        f"'{dep_name}^",
        f'"{dep_name}"',
        f"'{dep_name}'",
    ]

    line_stripped = line.strip()

    if line_stripped.startswith(dep_name):
        return True

    return any(pattern in line for pattern in patterns)


def _remove_dependency_from_content(content: str, dep_name: str) -> str | None:
    try:
        data = tomllib.loads(content)

        if "project" not in data or "dependencies" not in data["project"]:
            return None

        deps = data["project"]["dependencies"]
        removed = _remove_dependency_from_deps(deps, dep_name)

        if not removed:
            return None

        return _remove_dependency_from_toml(content, dep_name)

    except Exception:
        return _remove_dependency_from_toml(content, dep_name)


def _remove_dependency_from_deps(deps: list | dict, dep_name: str) -> bool:
    if isinstance(deps, list):
        original_length = len(deps)
        new_deps = [dep for dep in deps if dep_name not in dep]
        if len(new_deps) == original_length:
            return False
        deps.clear()
        deps.extend(new_deps)
        return True

    if isinstance(deps, dict):
        if dep_name not in deps:
            return False
        del deps[dep_name]
        return True

    return False


def _remove_creosote_exclusion(content: str, dep_name: str) -> str | None:
    lines = content.splitlines(keepends=True)
    new_lines: list[str] = []
    in_creosote_section = False
    in_exclude_deps_array = False
    removed = False

    for line in lines:
        stripped = line.strip()

        if stripped.startswith("[") and stripped.endswith("]"):
            in_creosote_section = stripped == "[tool.creosote]"
            in_exclude_deps_array = False
            new_lines.append(line)
            continue

        if in_creosote_section and "exclude-deps" in line and "=" in line:
            in_exclude_deps_array = True
            new_lines.append(line)
            continue

        if in_exclude_deps_array:
            if stripped in ("]", "],"):
                in_exclude_deps_array = False
                new_lines.append(line)
                continue

            if _is_exclusion_line(line, dep_name):
                removed = True
                continue

        new_lines.append(line)

    return "".join(new_lines) if removed else None


def _is_exclusion_line(line: str, dep_name: str) -> bool:
    stripped = line.strip()
    if not stripped or stripped.startswith("#"):
        return False

    no_trailing = re.sub(r",\s*(?:#.*)?$", "", stripped)
    return no_trailing in (f'"{dep_name}"', f"'{dep_name}'")


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


def _error_result(message: str) -> FixResult:
    return FixResult(
        success=False,
        confidence=0.0,
        remaining_issues=[message],
    )


def _validate_issue(issue: Issue) -> FixResult | None:
    if not issue.file_path:
        return FixResult(
            success=False,
            confidence=0.0,
            remaining_issues=["No file path provided"],
        )

    file_path = Path(issue.file_path)
    if file_path.name != "pyproject.toml":
        return FixResult(
            success=False,
            confidence=0.0,
            remaining_issues=[
                "DependencyAgent can only fix dependencies in pyproject.toml"
            ],
        )

    dep_name = _extract_dependency_name(issue.message)
    if not dep_name:
        return FixResult(
            success=False,
            confidence=0.0,
            remaining_issues=["Could not extract dependency name from message"],
        )

    return None


async def fix_dependency_issue(issue: Issue) -> FixResult:
    validation_result = _validate_issue(issue)
    if validation_result:
        return validation_result

    if issue.file_path is None:
        return _error_result("Issue has no file_path")
    file_path = Path(issue.file_path)
    dep_name = _extract_dependency_name(issue.message)
    if dep_name is None:
        return _error_result("Could not extract dependency name from issue")

    content = _read_file(file_path)
    if not content:
        return _error_result("Could not read pyproject.toml")

    clean_message = re.sub(r"\x1b\[[0-9;]*m", "", issue.message)
    is_creosote_exclusion = (
        "redundant exclusion" in clean_message.lower()
        or "excluded dependencies not found" in clean_message.lower()
    )

    if is_creosote_exclusion:
        new_content = _remove_creosote_exclusion(content, dep_name)
    else:
        new_content = _remove_dependency_from_content(content, dep_name)

    if not new_content:
        target = "[tool.creosote].exclude-deps" if is_creosote_exclusion else "TOML"
        return _error_result(f"Failed to remove dependency {dep_name} from {target}")

    if _write_file(file_path, new_content):
        fix_description = (
            f"Removed '{dep_name}' from [tool.creosote].exclude-deps"
            if is_creosote_exclusion
            else f"Removed unused dependency: {dep_name}"
        )
        return FixResult(
            success=True,
            confidence=0.9,
            fixes_applied=[fix_description],
            files_modified=[str(file_path)],
        )

    return _error_result("Failed to write modified pyproject.toml")

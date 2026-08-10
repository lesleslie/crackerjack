"""Deterministic DRY-violation regex detector/fixer.

Extracted from ``crackerjack.agents.dry_agent.DRYAgent``, which delegates to
one helper: ``crackerjack.agents.semantic_helpers.SemanticEnhancer`` (built
via ``create_semantic_enhancer``). That helper is *not* ported here -- it
wraps ``crackerjack.services.vector_store.VectorStore``, an
embeddings/similarity-search subsystem (``sentence-transformers`` model
config, a persistent ``.crackerjack/semantic_index.db``), i.e. exactly the
kind of AI-fix-adjacent machinery this extraction effort is removing, not
the deterministic regex logic it's trying to save. Only the regex-driven
duplicate-pattern detectors/fixers (``_detect_error_response_patterns``,
``_detect_path_conversion_patterns``, ``_detect_file_existence_patterns``,
``_detect_exception_patterns``, and their corresponding fix-application
methods) have no LLM/embedding dependency and are ported below.

What was intentionally dropped versus the original ``DRYAgent``:

- ``SubAgent``/coordinator dispatch plumbing: ``__init__`` (which only ever
  constructed the now-dropped ``semantic_enhancer``), ``can_handle``, and
  ``get_supported_types`` -- these only ever decided *whether* and *how
  confidently* this fixer should run for a given ``Issue``; that routing job
  belongs to whatever calls into this module now, not to the module itself.
- ``agent_registry.register(DRYAgent)`` -- registry plumbing.
- ``self.log(...)`` calls -- ``SubAgent.log`` is a no-op ``pass`` on the base
  class, so these calls had no observable effect (same treatment as the
  other extracted fixers).
- Semantic/session-buddy duplicate detection: ``_detect_semantic_violations``
  (which combined AST-ish function extraction with
  ``semantic_enhancer.find_duplicate_patterns``, an embeddings/vector-store
  lookup) and its *exclusive* support chain -- ``_extract_code_functions``,
  ``_should_skip_line``, ``_is_function_definition``,
  ``_handle_function_definition``, ``_handle_function_body_line``, and
  ``_is_line_inside_function`` -- were all called only to feed that one
  semantic-search call (verified via grep: no other caller of any of these
  six methods anywhere in the original file). Since the semantic call itself
  is dropped, the whole chain is dead weight and is dropped with it -- same
  treatment as ``performance.py``'s ``_detect_semantic_performance_issues``.
- Semantic-recommendation enhancement inside what is now
  ``_apply_and_save_dry_fixes``: the original's
  ``self.semantic_enhancer.enhance_recommendations(...)``,
  ``.get_semantic_context_summary(...)``, ``.store_insight_to_session(...)``,
  and the module-level ``get_session_enhanced_recommendations(...)`` call --
  all embeddings/session-storage lookups, dropped for the same reason as
  above. The base ``recommendations = ["Verify functionality after DRY
  fixes"]`` list (the real, dependency-free part) is kept as-is.
- ``AgentContext``-specific file I/O: ``AgentContext.get_file_content``'s
  path-traversal check, and ``AgentContext.write_file_content``'s
  path-traversal check, ``wrap_long_lines`` post-processing (which itself
  imports from the to-be-removed ``crackerjack.ai_fix`` package), and syntax
  validation -- replaced with direct ``pathlib.Path`` reads/writes via
  ``_read_file``/``_write_file`` below (same helpers, byte-for-byte, as the
  other extracted fixers). Real file I/O is still performed; only the
  framework wrapper around it is gone.

Renames worth noting for anyone diffing against the original: the
``SubAgent.analyze_and_fix`` entry point becomes ``fix_dry_violation`` below
(same validate/read/detect/apply/save flow, minus the semantic-detection
step and the ``self``/``AgentContext`` plumbing). ``_process_dry_violation``
and ``_apply_and_save_dry_fixes`` are no longer ``async`` -- once the
semantic (embeddings) branch is gone, neither function does anything that
needs to await; ``fix_dry_violation`` itself stays ``async def`` to match
the original entry point's signature (same treatment as
``performance.py``'s ``optimize_performance``).

``DRYAgent`` has no ``execute_fix_plan`` method (verified via full read of
the 589-line source file) -- unlike ``ArchitectAgent``/``SecurityAgent``/
``DocumentationAgent``/``FormattingAgent``, there is no separate
``FixPlan``/``ChangeSpec`` applicator to port here.

Pre-existing bugs/quirks preserved verbatim, not fixed, per CLAUDE.md Rule 7
("preserve functional requirements... fix the technical issue, not the
requirements"). All four are covered by explicit tests in
``tests/fixers/test_dry.py``:

1. ``detect_error_response_patterns`` (``_detect_error_response_patterns`` in
   the original): ``SAFE_PATTERNS["detect_error_response_patterns"]``'s regex
   has *zero* capturing groups, but the code unconditionally calls
   ``match.group(1)`` once the pattern matches. Any line that actually
   triggers the pattern (e.g. ``return '{"error": "msg"}'``) raises
   ``IndexError: no such group`` -- the ">= 3 occurrences" aggregation
   branch is unreachable in practice; the function crashes on the *first*
   real match instead of ever building a violation.
2. ``detect_file_existence_patterns`` and ``detect_exception_patterns``: both
   underlying ``SAFE_PATTERNS`` regexes require a literal trailing space
   immediately after the colon (``\\(\\): `` / ``as \\w+: ``), but both
   callers test against ``line.strip()``, which strips exactly that
   required trailing space whenever the colon is the last non-whitespace
   content on the line. A normally-formatted ``if not x.exists():`` or
   ``except Exception as e:`` (colon, then newline) therefore *never*
   matches; detection only fires when there is inline code after the colon
   on the same physical line (e.g. ``if not x.exists(): raise
   ValueError()``).
3. ``_apply_error_pattern_replacements`` (the fix step invoked for
   ``"error_response_pattern"`` violations) applies
   ``SAFE_PATTERNS["fix_path_conversion_with_ensure_path"]`` -- the *path
   conversion* fix pattern -- to the flagged lines, not any
   error-response-specific transform. That pattern never matches an
   error-response line, so ``.apply()`` is a no-op substitution: the "fix"
   only inserts unused ``_create_error_response``/``_ensure_path`` utility
   functions at the top of the file and leaves the flagged lines completely
   unchanged, while ``_fix_error_response_pattern`` still unconditionally
   reports ``modified=True``.
4. ``_apply_violation_fix``'s dispatch only handles
   ``"error_response_pattern"`` and ``"path_conversion_pattern"``;
   ``"file_existence_pattern"`` and ``"exception_handling_pattern"``
   violations are detected by ``detect_dry_violations`` but never routed to
   any fixer (falls through to ``return lines, False`` unmodified) -- these
   two violation types are detect-only in the original code.
"""

from __future__ import annotations

import typing as t
from pathlib import Path

from crackerjack.models.issues import FixResult, Issue
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


# ---------------------------------------------------------------------------
# Detection
# ---------------------------------------------------------------------------


def detect_error_response_patterns(content: str) -> list[dict[str, t.Any]]:
    """Detect repeated ``return '{"error": ...}'``-style literals.

    Pre-existing bug preserved verbatim (see module docstring, point 1):
    raises ``IndexError`` on the first line that actually matches the
    underlying pattern, since that pattern has no capturing groups.
    """
    violations: list[dict[str, t.Any]] = []
    lines = content.split("\n")

    error_pattern = SAFE_PATTERNS["detect_error_response_patterns"]

    error_responses: list[dict[str, t.Any]] = []
    for i, line in enumerate(lines):
        if error_pattern.test(line.strip()):
            compiled_pattern = error_pattern._get_compiled_pattern()
            match = compiled_pattern.search(line.strip())
            if match:
                error_responses.append(
                    {
                        "line_number": i + 1,
                        "content": line.strip(),
                        "error_message": match.group(1),
                    },
                )

    if len(error_responses) >= 3:
        violations.append(
            {
                "type": "error_response_pattern",
                "instances": error_responses,
                "suggestion": "Extract to error utility function",
            },
        )

    return violations


def detect_path_conversion_patterns(content: str) -> list[dict[str, t.Any]]:
    """Detect repeated ``Path(x) if isinstance(x, str) else x`` patterns."""
    violations: list[dict[str, t.Any]] = []
    lines = content.split("\n")

    path_pattern = SAFE_PATTERNS["detect_path_conversion_patterns"]

    path_conversions: list[dict[str, t.Any]] = [
        {
            "line_number": i + 1,
            "content": line.strip(),
        }
        for i, line in enumerate(lines)
        if path_pattern.test(line)
    ]

    if len(path_conversions) >= 2:
        violations.append(
            {
                "type": "path_conversion_pattern",
                "instances": path_conversions,
                "suggestion": "Extract to path utility function",
            },
        )

    return violations


def detect_file_existence_patterns(content: str) -> list[dict[str, t.Any]]:
    """Detect repeated ``if not x.exists(): ...`` checks.

    Pre-existing quirk preserved verbatim (see module docstring, point 2):
    only fires for lines with inline code after the colon, since the
    trailing-space-requiring pattern is tested against a stripped line.
    """
    violations: list[dict[str, t.Any]] = []
    lines = content.split("\n")

    existence_pattern = SAFE_PATTERNS["detect_file_existence_patterns"]

    existence_checks: list[dict[str, t.Any]] = [
        {
            "line_number": i + 1,
            "content": line.strip(),
        }
        for i, line in enumerate(lines)
        if existence_pattern.test(line.strip())
    ]

    if len(existence_checks) >= 3:
        violations.append(
            {
                "type": "file_existence_pattern",
                "instances": existence_checks,
                "suggestion": "Extract to file validation utility",
            },
        )

    return violations


def detect_exception_patterns(content: str) -> list[dict[str, t.Any]]:
    """Detect repeated ``except ...Exception as e: ...`` handlers whose next
    line re-raises/stringifies the error (``"error" in`` and ``"str(" in``
    the following line).

    Pre-existing quirk preserved verbatim (see module docstring, point 2):
    only fires for lines with inline code after the colon, for the same
    trailing-space-vs-strip reason as ``detect_file_existence_patterns``.
    """
    violations: list[dict[str, t.Any]] = []
    lines = content.split("\n")

    exception_pattern = SAFE_PATTERNS["detect_exception_patterns"]

    exception_handlers = [
        {
            "line_number": i + 1,
            "content": line.strip(),
            "next_line": lines[i + 1].strip(),
        }
        for i, line in enumerate(lines)
        if exception_pattern.test(line.strip())
        and (i + 1 < len(lines) and "error" in lines[i + 1] and "str(" in lines[i + 1])
    ]

    if len(exception_handlers) >= 3:
        violations.append(
            {
                "type": "exception_handling_pattern",
                "instances": exception_handlers,
                "suggestion": "Extract to error handling utility or decorator",
            },
        )

    return violations


def detect_dry_violations(content: str) -> list[dict[str, t.Any]]:
    """Run all four regex-driven duplicate-pattern detectors.

    Note: since ``detect_error_response_patterns`` runs first and can raise
    ``IndexError`` on real matches (see module docstring, point 1), any
    content with >= 1 matching error-response line aborts this whole
    aggregation with that exception -- callers should be prepared to catch
    it (``fix_dry_violation`` below does).
    """
    violations: list[dict[str, t.Any]] = []

    violations.extend(detect_error_response_patterns(content))
    violations.extend(detect_path_conversion_patterns(content))
    violations.extend(detect_file_existence_patterns(content))
    violations.extend(detect_exception_patterns(content))

    return violations


# ---------------------------------------------------------------------------
# Fix application
# ---------------------------------------------------------------------------


def apply_dry_fixes(content: str, violations: list[dict[str, t.Any]]) -> str:
    lines = content.split("\n")
    modified = False

    for violation in violations:
        lines, changed = _apply_violation_fix(lines, violation)
        modified = modified or changed

    return "\n".join(lines) if modified else content


def _apply_violation_fix(
    lines: list[str],
    violation: dict[str, t.Any],
) -> tuple[list[str], bool]:
    violation_type = violation["type"]

    if violation_type == "error_response_pattern":
        return _fix_error_response_pattern(lines, violation)
    if violation_type == "path_conversion_pattern":
        return _fix_path_conversion_pattern(lines, violation)

    return lines, False


def _fix_error_response_pattern(
    lines: list[str],
    violation: dict[str, t.Any],
) -> tuple[list[str], bool]:
    utility_lines = _add_error_response_utilities(lines)

    _apply_error_pattern_replacements(lines, violation, len(utility_lines))

    return lines, True


def _add_error_response_utilities(lines: list[str]) -> list[str]:
    utility_function = """
def _create_error_response(message: str, success: bool = False) -> str:

    import json
    return json.dumps({"error": message, "success": success})

def _ensure_path(path: str | Path) -> Path:

    return Path(path) if isinstance(path, str) else path
"""

    insert_pos = _find_utility_insert_position(lines)

    utility_lines: list[str] = t.cast(
        list[str], utility_function.strip().split("\n")
    ).copy()

    for i, util_line in enumerate(utility_lines):
        lines.insert(insert_pos + i, util_line)

    return utility_lines.copy()


def _find_utility_insert_position(lines: list[str]) -> int:
    insert_pos = 0
    for i, line in enumerate(lines):
        if line.strip().startswith(("import ", "from ")):
            insert_pos = i + 1
        elif line.strip() and not line.strip().startswith("#"):
            break
    return insert_pos


def _apply_error_pattern_replacements(
    lines: list[str],
    violation: dict[str, t.Any],
    utility_lines_count: int,
) -> None:
    path_pattern = SAFE_PATTERNS["fix_path_conversion_with_ensure_path"]

    for instance in violation["instances"]:
        line_number: int = int(instance["line_number"])
        line_idx = line_number - 1 + utility_lines_count

        if line_idx < len(lines):
            original_line: str = lines[line_idx]
            new_line: str = path_pattern.apply(original_line)
            lines[line_idx] = new_line


def _fix_path_conversion_pattern(
    lines: list[str],
    violation: dict[str, t.Any],
) -> tuple[list[str], bool]:
    utility_function_added = _check_ensure_path_exists(lines)
    adjustment = 0

    if not utility_function_added:
        adjustment = _add_ensure_path_utility(lines)

    modified = _apply_path_pattern_replacements(
        lines,
        violation,
        adjustment,
        utility_function_added,
    )

    return lines, modified


def _check_ensure_path_exists(lines: list[str]) -> bool:
    return any("_ensure_path" in line and "def _ensure_path" in line for line in lines)


def _add_ensure_path_utility(lines: list[str]) -> int:
    insert_pos = _find_utility_insert_position(lines)

    utility_lines = [
        "",
        "def _ensure_path(path: str | Path) -> Path: ",
        ' """Convert string path to Path object if needed."""',
        " return Path(path) if isinstance(path, str) else path",
        "",
    ]

    for i, util_line in enumerate(utility_lines):
        lines.insert(insert_pos + i, util_line)

    return len(utility_lines)


def _apply_path_pattern_replacements(
    lines: list[str],
    violation: dict[str, t.Any],
    adjustment: int,
    utility_function_added: bool,
) -> bool:
    path_pattern = SAFE_PATTERNS["fix_path_conversion_simple"]

    modified = False
    for instance in violation["instances"]:
        line_number: int = int(instance["line_number"])
        line_idx = line_number - 1 + (0 if utility_function_added else adjustment)

        if line_idx < len(lines):
            original_line: str = lines[line_idx]
            new_line = path_pattern.apply(original_line)

            if new_line != original_line:
                lines[line_idx] = new_line
                modified = True

    return modified


# ---------------------------------------------------------------------------
# Orchestration (validate -> read -> detect -> apply -> save)
# ---------------------------------------------------------------------------


def _validate_dry_issue(issue: Issue) -> FixResult | None:
    if not issue.file_path:
        return FixResult(
            success=False,
            confidence=0.0,
            remaining_issues=["No file path specified for DRY violation"],
        )

    file_path = Path(issue.file_path)
    if not file_path.exists():
        return FixResult(
            success=False,
            confidence=0.0,
            remaining_issues=[f"File not found: {file_path}"],
        )

    return None


def _create_no_fixes_result() -> FixResult:
    return FixResult(
        success=False,
        confidence=0.5,
        remaining_issues=["Could not automatically fix DRY violations"],
        recommendations=[
            "Manual refactoring required",
            "Consider extracting common patterns to utility functions",
            "Create base classes or mixins for repeated functionality",
        ],
    )


def _create_dry_error_result(error: Exception) -> FixResult:
    return FixResult(
        success=False,
        confidence=0.0,
        remaining_issues=[f"Error processing file: {error}"],
    )


def _apply_and_save_dry_fixes(
    file_path: Path,
    content: str,
    violations: list[dict[str, t.Any]],
) -> FixResult:
    fixed_content = apply_dry_fixes(content, violations)

    if fixed_content == content:
        return _create_no_fixes_result()

    success = _write_file(file_path, fixed_content)
    if not success:
        return FixResult(
            success=False,
            confidence=0.0,
            remaining_issues=[f"Failed to write fixed file: {file_path}"],
        )

    return FixResult(
        success=True,
        confidence=0.8,
        fixes_applied=[
            f"Fixed {len(violations)} DRY violations",
            "Consolidated repetitive patterns",
        ],
        files_modified=[str(file_path)],
        recommendations=["Verify functionality after DRY fixes"],
    )


def _process_dry_violation(file_path: Path) -> FixResult:
    content = _read_file(file_path)
    if not content:
        return FixResult(
            success=False,
            confidence=0.0,
            remaining_issues=[f"Could not read file: {file_path}"],
        )

    violations = detect_dry_violations(content)

    if not violations:
        return FixResult(
            success=True,
            confidence=0.7,
            recommendations=["No DRY violations detected"],
        )

    return _apply_and_save_dry_fixes(file_path, content, violations)


async def fix_dry_violation(issue: Issue) -> FixResult:
    validation_result = _validate_dry_issue(issue)
    if validation_result:
        return validation_result

    if issue.file_path is None:
        return _create_dry_error_result(
            ValueError("File path is required for DRY violation"),
        )

    file_path = Path(issue.file_path)

    try:
        return _process_dry_violation(file_path)
    except Exception as e:
        return _create_dry_error_result(e)


__all__ = [
    "apply_dry_fixes",
    "detect_dry_violations",
    "detect_error_response_patterns",
    "detect_exception_patterns",
    "detect_file_existence_patterns",
    "detect_path_conversion_patterns",
    "fix_dry_violation",
]

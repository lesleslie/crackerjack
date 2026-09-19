import logging
from collections.abc import Callable

logger = logging.getLogger(__name__)


# Pre-compiled at module load — referenced by both ``should_count_as_issue``
# and ``_is_filtered_line`` below. Kept as module-level constants (not
# inlined) so the cyclomatic complexity of each function stays low and
# the patterns are easy to audit in one place.
_SUCCESS_PREFIXES = ("✓", "✅", "PASSED", "All ")
_SUMMARY_KEYWORDS = ("failed to", "error", "errors found")
_NOTE_HELP_PATTERNS = (": note:", ": help:", "note: ", "help: ")
_SUMMARY_PREFIXES = (
    "Found",
    "Checked",
    "N errors found",
    "errors in",
    "Success",
    "Summary",
    "Total",
)
_SEPARATOR_PREFIXES = (
    "===",
    "Errors:",
    "┌",
    "└",
    "├",
    "┼",
    "┤",
    "┃",
    "│",
    "║",
    "═",
    "---",
    "────",
)
_SEPARATOR_BOX_CHARS = "─═│║┼┌└├"
_HEADER_EXACT_MATCHES = (
    "Path",
    "─────",
    "File",
    "Function",
    "Function | Complexity",
    "File | Function | Complexity",
    "Path | Function | Complexity",
    "File | Line | Issue",
)


def should_count_as_issue(
    line: str,
    tool_name: str = "",
    additional_filters: Callable[[str], bool] | None = None,
) -> bool:
    """Decide whether a single output line should count as a tool issue.

    Thin orchestrator — the per-pattern filter logic lives in
    :func:`_is_filtered_line` so each function stays below the
    cyclomatic-complexity threshold (15).
    """
    if not line or not line.strip():
        return False

    line_stripped = line.strip()

    if _is_filtered_line(line_stripped, tool_name):
        return False

    if additional_filters is not None and not additional_filters(line_stripped):
        logger.debug(f"Filtering out line via custom filter: {line_stripped[:100]}")
        return False

    return True


def _is_filtered_line(line_stripped: str, tool_name: str) -> bool:
    """Apply every generic and tool-specific exclusion pattern.

    Each ``if`` early-returns True (this line is filtered out / not an
    issue) and contributes one to cyclomatic complexity — kept in a
    separate function from :func:`should_count_as_issue` so the public
    entrypoint stays small.
    """
    if line_stripped.startswith(_SUCCESS_PREFIXES):
        logger.debug(f"Skipping success line: {line_stripped[:100]}")
        return True

    if line_stripped.startswith(("[", "{")):
        logger.debug(f"Skipping JSON output line from {tool_name}")
        return True

    # Tool-specific skip patterns — keep the generic line-counter from
    # over-counting lines that look like content but aren't issues.
    # linkcheckmd prints per-file timing between scan results; the Fast
    # Hook Results panel was inflating a single broken-link finding to
    # 4 because all three timing lines passed ``should_count_as_issue``.
    # check-added-large-files prints a ``Large files detected:`` header
    # followed by one line per offender — the header was being counted
    # as a fifth "issue".
    if tool_name == "linkcheckmd" and "seconds to check links" in line_stripped:
        logger.debug(f"Skipping linkcheckmd timing line: {line_stripped[:100]}")
        return True
    if tool_name == "check-added-large-files" and line_stripped.startswith(
        "Large files"
    ):
        logger.debug(f"Skipping check-added-large-files header: {line_stripped[:100]}")
        return True

    if (
        line_stripped
        and line_stripped[0].isdigit()
        and any(x in line_stripped.lower() for x in _SUMMARY_KEYWORDS)
    ):
        logger.debug(f"Skipping summary/error count line: {line_stripped[:100]}")
        return True

    if line_stripped.startswith("#"):
        logger.debug(f"Filtering out comment line: {line_stripped[:100]}")
        return True

    line_lower = line_stripped.lower()
    if any(pattern in line_lower for pattern in _NOTE_HELP_PATTERNS):
        logger.debug(f"Filtering out note/help line: {line_stripped[:100]}")
        return True

    if line_stripped.startswith(_SUMMARY_PREFIXES):
        logger.debug(f"Filtering out summary line: {line_stripped[:100]}")
        return True

    if line_stripped.startswith(_SEPARATOR_PREFIXES) or _is_only_box_drawing(
        line_stripped
    ):
        logger.debug(f"Filtering out separator line: {line_stripped[:100]}")
        return True

    if line_stripped in _HEADER_EXACT_MATCHES:
        logger.debug(f"Filtering out header line: {line_stripped[:100]}")
        return True

    if line_stripped.startswith("|") and line_stripped.count("|") >= 2:
        logger.debug(f"Filtering out markdown table row: {line_stripped[:100]}")
        return True

    return False


def _is_only_box_drawing(line: str) -> bool:
    """True when stripping every box-drawing char leaves an empty string."""
    return line.translate(str.maketrans("", "", _SEPARATOR_BOX_CHARS)).strip() == ""


def count_issues_from_output(
    output: str,
    tool_name: str = "",
    additional_filters: Callable[[str], bool] | None = None,
) -> int:
    if not output:
        return 0

    count = 0
    for line in output.split("\n"):
        if should_count_as_issue(line, tool_name, additional_filters):
            count += 1

    logger.debug(
        f"Counted {count} issues from {tool_name} output ({len(output.split(chr(10)))} lines)"
    )
    return count


def extract_issue_lines(
    output: str,
    tool_name: str = "",
    additional_filters: Callable[[str], bool] | None = None,
) -> list[str]:
    if not output:
        return []

    issue_lines: list[str] = []
    for line in output.split("\n"):
        line = line.strip()
        if should_count_as_issue(line, tool_name, additional_filters):
            issue_lines.append(line)

    logger.debug(f"Extracted {len(issue_lines)} issue lines from {tool_name}")
    return issue_lines

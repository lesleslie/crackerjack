import logging
from collections.abc import Callable

logger = logging.getLogger(__name__)


def should_count_as_issue(
    line: str,
    tool_name: str = "",
    additional_filters: Callable[[str], bool] | None = None,
) -> bool:
    if not line or not line.strip():
        return False

    if line.strip().startswith("#"):
        logger.debug(f"Filtering out comment line: {line.strip()[:100]}")
        return False

    line_lower = line.lower()
    line_stripped = line.strip()

    note_help_patterns = (": note:", ": help:", "note: ", "help: ")
    if any(pattern in line_lower for pattern in note_help_patterns):
        logger.debug(f"Filtering out note/help line: {line_stripped[:100]}")
        return False

    summary_patterns = (
        "Found",
        "Checked",
        "N errors found",
        "errors in",
        "Success",
        "Summary",
        "Total",
    )
    if line_stripped.startswith(summary_patterns):
        logger.debug(f"Filtering out summary line: {line_stripped[:100]}")
        return False

    separator_patterns = ("===", "Errors:", "┌", "└", "├", "┼", "┤", "┃", "---", "────")
    if (
        line_stripped.startswith(separator_patterns)
        or line_stripped.replace("─", "")
        .replace("┼", "")
        .replace("┌", "")
        .replace("└", "")
        .replace("├", "")
        .strip()
        == ""
    ):
        logger.debug(f"Filtering out separator line: {line_stripped[:100]}")
        return False

    header_exact_matches = (
        "Path",
        "─────",
        "File",
        "Function",
        "Function | Complexity",
        "File | Function | Complexity",
        "Path | Function | Complexity",
        "File | Line | Issue",
    )
    if line_stripped in header_exact_matches:
        logger.debug(f"Filtering out header line: {line_stripped[:100]}")
        return False

    if additional_filters and not additional_filters(line_stripped):
        logger.debug(f"Filtering out line via custom filter: {line_stripped[:100]}")
        return False

    return True


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

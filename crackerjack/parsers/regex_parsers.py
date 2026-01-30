"""Regex-based parsers for tools without JSON support.

This module implements regex parsers for tools that don't support JSON output.
These parsers are used as fallback when JSON is not available.

Note: For tools that DO support JSON (ruff, mypy, bandit), use the JSON parsers
in json_parsers.py instead.
"""

import logging
import re

from crackerjack.parsers.base import RegexParser
from crackerjack.agents.base import Issue, IssueType, Priority

logger = logging.getLogger(__name__)


class CodespellRegexParser(RegexParser):
    """Parse codespell output (text-based, no JSON support).

    Example output:
        tests/test_file.py:10: teh ==> the
    """

    def parse_text(self, output: str) -> list[Issue]:
        """Parse codespell text output.

        Args:
            output: Raw text output from codespell

        Returns:
            List of Issue objects
        """
        issues: list[Issue] = []

        for line in output.split("\n"):
            line = line.strip()
            if not self._should_parse_codespell_line(line):
                continue

            try:
                issue = self._parse_single_codespell_line(line)
                if issue:
                    issues.append(issue)
            except Exception as e:
                logger.debug(f"Failed to parse codespell line: {line} ({e})")

        logger.debug(f"Parsed {len(issues)} issues from codespell")
        return issues

    def _should_parse_codespell_line(self, line: str) -> bool:
        """Check if line should be parsed."""
        return bool(line and "==>" in line)

    def _parse_single_codespell_line(self, line: str) -> Issue | None:
        """Parse a single codespell line."""
        if ":" not in line:
            return None

        file_path, rest = line.split(":", 1)
        if ":" not in rest:
            file_path = file_path.strip()
            return Issue(
                type=IssueType.FORMATTING,
                severity=Priority.LOW,
                message=rest.strip(),
                file_path=file_path,
                line_number=None,
                stage="codespell",
            )

        line_number_str, message_part = rest.split(":", 1)
        try:
            line_number = int(line_number_str.strip())
        except ValueError:
            line_number = None

        message = self._format_codespell_message(message_part)

        return Issue(
            type=IssueType.FORMATTING,
            severity=Priority.LOW,
            message=message,
            file_path=file_path.strip(),
            line_number=line_number,
            stage="codespell",
        )

    def _format_codespell_message(self, message_part: str) -> str:
        """Format codespell message."""
        if "==>" in message_part:
            wrong_word, suggestions = message_part.split("==>", 1)
            return f"Spelling: '{wrong_word.strip()}' should be '{suggestions.strip()}'"
        return message_part.strip()


class RefurbRegexParser(RegexParser):
    """Parse refurb output (text-based, no JSON support).

    Example output:
        path/to/file.py:10:5: FURB101: Remove unnecessary noqa comment
    """

    def parse_text(self, output: str) -> list[Issue]:
        """Parse refurb text output.

        Args:
            output: Raw text output from refurb

        Returns:
            List of Issue objects
        """
        issues: list[Issue] = []

        for line in output.split("\n"):
            line = line.strip()
            if not line or line.startswith(("Found", "Checked")):
                continue

            if "FURB" in line and ":" in line:
                parts = line.split(":", 2)
                if len(parts) >= 2:
                    try:
                        file_path = parts[0].strip()
                        line_number = int(parts[1].strip())
                        message = parts[2].strip() if len(parts) > 2 else line

                        issues.append(
                            Issue(
                                type=IssueType.COMPLEXITY,
                                severity=Priority.MEDIUM,
                                message=message,
                                file_path=file_path,
                                line_number=line_number,
                                stage="refurb",
                            )
                        )
                    except (ValueError, IndexError) as e:
                        logger.debug(f"Failed to parse refurb line: {line} ({e})")

        logger.debug(f"Parsed {len(issues)} issues from refurb")
        return issues


class RuffFormatRegexParser(RegexParser):
    """Parse ruff-format output (text-based, no JSON support).

    Example output:
        Would reformat 5 files
        or
        1 file would be reformatted
    """

    def parse_text(self, output: str) -> list[Issue]:
        """Parse ruff-format text output.

        Args:
            output: Raw text output from ruff-format

        Returns:
            List of Issue objects
        """
        issues: list[Issue] = []

        if "would be reformatted" in output or "Failed to format" in output:
            import re

            file_count = 1
            if "file" in output:
                match = re.search(r"(\d+) files?", output)
                if match:
                    file_count = int(match.group(1))

            message = f"{file_count} file(s) require formatting"

            if "error:" in output:
                error_lines = [line for line in output.split("\n") if line.strip()]
                if error_lines:
                    message = f"Formatting error: {error_lines[0]}"

            issues.append(
                Issue(
                    type=IssueType.FORMATTING,
                    severity=Priority.MEDIUM,
                    message=message,
                    file_path=None,
                    line_number=None,
                    stage="ruff-format",
                    details=["Run 'uv run ruff format .' to fix"],
                )
            )

        logger.debug(f"Parsed {len(issues)} issues from ruff-format")
        return issues


class ComplexityRegexParser(RegexParser):
    """Parse complexipy output (text-based, no JSON support).

    Example output:
        Failed functions:
        - src/file.py:
            function_name :: 25
    """

    def parse_text(self, output: str) -> list[Issue]:
        """Parse complexipy text output.

        Args:
            output: Raw text output from complexipy

        Returns:
            List of Issue objects
        """
        issues: list[Issue] = []
        lines = output.split("\n")

        in_failed_section = False
        current_file = ""

        for line in lines:
            line_stripped = line.strip()

            if self._is_failed_section_start(line_stripped):
                in_failed_section = True
                continue

            if self._is_failed_section_end(line_stripped, in_failed_section):
                break

            if self._is_file_marker(line_stripped, in_failed_section):
                current_file = self._extract_file_from_marker(line_stripped)
                continue

            if self._is_function_line(
                line_stripped, in_failed_section, bool(current_file)
            ):
                issue = self._create_complexity_issue(line_stripped, current_file)
                issues.append(issue)

        logger.debug(f"Parsed {len(issues)} issues from complexity")
        return issues

    def _is_failed_section_start(self, line: str) -> bool:
        """Check if line marks the start of the failed functions section."""
        return line.startswith("Failed functions:")

    def _is_failed_section_end(self, line: str, in_section: bool) -> bool:
        """Check if line marks the end of the failed functions section."""
        return in_section and (not line or line.startswith("─"))

    def _is_file_marker(self, line: str, in_section: bool) -> bool:
        """Check if line is a file path marker."""
        return in_section and line.startswith("- ") and line.endswith(":")

    def _extract_file_from_marker(self, line: str) -> str:
        """Extract file path from a file marker line."""
        remaining = line[2:].strip()  # Remove "- " prefix
        return remaining[:-1].strip()  # Remove trailing ":"

    def _is_function_line(self, line: str, in_section: bool, has_file: bool) -> bool:
        """Check if line is a function with complexity issue."""
        return in_section and has_file and not line.startswith("- ") and "::" in line

    def _create_complexity_issue(self, line: str, file_path: str) -> Issue:
        """Create an Issue object for a complexity violation."""
        message = f"Complexity exceeded for {line}"
        return Issue(
            type=IssueType.COMPLEXITY,
            severity=Priority.MEDIUM,
            message=message,
            file_path=file_path,
            line_number=None,
            stage="complexity",
        )


class GenericRegexParser(RegexParser):
    """Generic parser for tools without specific parsers.

    This parser creates a single Issue from the raw output.
    """

    def __init__(
        self, tool_name: str, issue_type: IssueType = IssueType.FORMATTING
    ) -> None:
        """Initialize generic parser.

        Args:
            tool_name: Name of the tool
            issue_type: Type of issue to create
        """
        self.tool_name = tool_name
        self.issue_type = issue_type

    def parse_text(self, output: str) -> list[Issue]:
        """Parse text output generically.

        Args:
            output: Raw text output

        Returns:
            List with a single Issue object
        """
        if not output or not output.strip():
            return []

        return [
            Issue(
                type=self.issue_type,
                severity=Priority.MEDIUM,
                message=f"{self.tool_name} check failed",
                file_path=None,
                line_number=None,
                stage=self.tool_name,
                details=[output[:500]],
            )
        ]


class StructuredDataParser(RegexParser):
    """Parse structured data tool output (check-yaml, check-toml, check-json).

    These tools use a simple format:
    - ✓ file.ext: Valid YAML (success)
    - ✗ file.ext: error message (failure)
    """

    def parse_text(self, output: str) -> list[Issue]:
        """Parse structured data tool output.

        Args:
            output: Raw text output from check-yaml/check-toml/check-json

        Returns:
            List of Issue objects for each error line
        """
        issues: list[Issue] = []

        for line in output.split("\n"):
            line = line.strip()
            if not self._should_parse_structured_data_line(line):
                continue

            issue = self._parse_single_structured_data_line(line)
            if issue:
                issues.append(issue)

        logger.debug(f"Parsed {len(issues)} issues from structured data output")
        return issues

    def _should_parse_structured_data_line(self, line: str) -> bool:
        """Check if line should be parsed as an error.

        Args:
            line: Line to check

        Returns:
            True if line is an error, False otherwise
        """
        return bool(line and line.startswith("✗"))

    def _parse_single_structured_data_line(self, line: str) -> Issue | None:
        """Parse a single structured data error line.

        Args:
            line: Error line (e.g., "✗ config.yml: error message")

        Returns:
            Issue object or None if parsing fails
        """
        try:
            file_path, error_message = self._extract_structured_data_parts(line)
            if not file_path:
                return None

            return Issue(
                type=IssueType.FORMATTING,
                severity=Priority.MEDIUM,
                message=error_message,
                file_path=file_path,
                line_number=None,
                stage="structured-data",
            )
        except Exception as e:
            logger.debug(f"Failed to parse structured data line: {line} ({e})")
            return None

    def _extract_structured_data_parts(self, line: str) -> tuple[str, str]:
        """Extract file path and error message from structured data line.

        Args:
            line: Line like "✗ file.ext: error message"

        Returns:
            Tuple of (file_path, error_message)
        """
        if line.startswith("✗"):
            line = line[1:].strip()

        if ":" not in line:
            return "", line

        file_path, error_message = line.split(":", 1)
        return file_path.strip(), error_message.strip()


# Register parsers with factory
def register_regex_parsers(factory: "ParserFactory") -> None:
    """Register all regex parsers with the parser factory.

    Args:
        factory: ParserFactory instance to register parsers with
    """
    from crackerjack.parsers.factory import ParserFactory

    # Create parser instances
    codespell_parser = CodespellRegexParser()
    refurb_parser = RefurbRegexParser()
    ruff_format_parser = RuffFormatRegexParser()
    complexity_parser = ComplexityRegexParser()
    structured_data_parser = StructuredDataParser()

    # Register for specific tool names
    factory.register_regex_parser("codespell", CodespellRegexParser)
    factory.register_regex_parser("refurb", RefurbRegexParser)
    factory.register_regex_parser("ruff-format", RuffFormatRegexParser)
    factory.register_regex_parser("complexity", ComplexityRegexParser)

    # Register structured data parser for multiple tools
    factory.register_regex_parser("check-yaml", StructuredDataParser)
    factory.register_regex_parser("check-toml", StructuredDataParser)
    factory.register_regex_parser("check-json", StructuredDataParser)

    logger.info(
        "Registered regex parsers: codespell, refurb, ruff-format, complexity, "
        "check-yaml, check-toml, check-json"
    )

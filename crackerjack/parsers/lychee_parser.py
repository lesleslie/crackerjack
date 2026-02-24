"""Parser for lychee link checker output.

Lychee is a fast link checker that outputs broken links in the format:
    path/to/file.md:10: https://example.com (404 Not Found)
    path/to/file.md:20: https://badlink.com (Network error)
"""

import logging
import re

from crackerjack.agents.base import Issue, IssueType, Priority
from crackerjack.parsers.base import RegexParser

logger = logging.getLogger(__name__)


class LycheeRegexParser(RegexParser):
    """Parser for lychee link checker output.

    Parses output lines like:
        path/to/file.md:10: https://example.com (404 Not Found)
        path/to/file.md:20: https://badlink.com (Network error)
    """

    # Regex pattern to match lychee output format
    # Format: file_path:line_number: URL (error_message)
    LINE_PATTERN = re.compile(r"^(.+?):(\d+):\s*(https?://\S+)\s*\(([^)]+)\)$")

    def parse_text(self, output: str) -> list[Issue]:
        """Parse lychee output and return list of Issues.

        Args:
            output: Raw output from lychee link checker

        Returns:
            List of Issue objects for broken links
        """
        issues: list[Issue] = []

        for line in output.split("\n"):
            line = line.strip()
            if not self._should_parse_lychee_line(line):
                continue

            try:
                issue = self._parse_single_lychee_line(line)
                if issue:
                    issues.append(issue)
            except Exception as e:
                logger.debug(f"Failed to parse lychee line: {line} ({e})")

        logger.debug(f"Parsed {len(issues)} issues from lychee")
        return issues

    def _should_parse_lychee_line(self, line: str) -> bool:
        """Determine if a line should be parsed as a lychee error.

        Args:
            line: A single line from lychee output

        Returns:
            True if the line appears to be a broken link report
        """
        if not line:
            return False

        # Skip summary/progress lines
        skip_prefixes = (
            "🔍",
            "❌",
            "✅",
            "⚠️",
            "Stats:",
            "Found",
            "Checked",
            "Errors",
            "Success",
            "Total",
            "Running",
            "Finished",
            "[",
        )
        if line.startswith(skip_prefixes):
            return False

        # Must have URL pattern and parentheses for error
        return "https://" in line or "http://" in line

    def _parse_single_lychee_line(self, line: str) -> Issue | None:
        """Parse a single lychee error line into an Issue.

        Args:
            line: A line like "path/to/file.md:10: https://example.com (404 Not Found)"

        Returns:
            An Issue object if parsing succeeds, None otherwise
        """
        match = self.LINE_PATTERN.match(line)
        if not match:
            # Try alternative parsing for less structured output
            return self._parse_loose_format(line)

        file_path = match.group(1).strip()
        line_number = int(match.group(2))
        url = match.group(3)
        error_message = match.group(4)

        return self._create_lychee_issue(
            file_path=file_path,
            line_number=line_number,
            url=url,
            error_message=error_message,
        )

    def _parse_loose_format(self, line: str) -> Issue | None:
        """Parse less structured lychee output formats.

        Handles variations like:
        - file.md:10: https://example.com - 404 Not Found
        - file.md https://example.com (failed)

        Args:
            line: A line that didn't match the standard pattern

        Returns:
            An Issue object if parsing succeeds, None otherwise
        """
        # Try to extract URL first
        url_match = re.search(r"(https?://\S+)", line)
        if not url_match:
            return None

        url = url_match.group(1)

        # Try to extract error in parentheses
        error_match = re.search(r"\(([^)]+)\)", line)
        error_message = error_match.group(1) if error_match else "Unknown error"

        # Try to extract file path and line number
        file_path, line_number = self._extract_file_and_line(line, url_match.start())

        return self._create_lychee_issue(
            file_path=file_path,
            line_number=line_number,
            url=url,
            error_message=error_message,
        )

    def _extract_file_and_line(
        self, line: str, url_pos: int
    ) -> tuple[str | None, int | None]:
        """Extract file path and line number from line before URL.

        Args:
            line: The full line
            url_pos: Position where URL starts

        Returns:
            Tuple of (file_path, line_number), either may be None
        """
        prefix = line[:url_pos].strip().rstrip(":")

        if ":" in prefix:
            parts = prefix.rsplit(":", 1)
            file_path = parts[0].strip()
            try:
                line_number = int(parts[1].strip())
                return file_path, line_number
            except ValueError:
                return prefix, None

        return prefix if prefix else None, None

    def _create_lychee_issue(
        self,
        file_path: str | None,
        line_number: int | None,
        url: str,
        error_message: str,
    ) -> Issue:
        """Create an Issue object for a broken link.

        Args:
            file_path: Path to the file containing the link
            line_number: Line number where the link appears
            url: The broken URL
            error_message: The error from lychee

        Returns:
            An Issue object representing the broken link
        """
        message = f"Broken link: {url} ({error_message})"

        # Determine severity based on error type
        severity = self._get_severity(error_message)

        return Issue(
            type=IssueType.DOCUMENTATION,
            severity=severity,
            message=message,
            file_path=file_path,
            line_number=line_number,
            stage="lychee",
            details=[
                f"url: {url}",
                f"error: {error_message}",
            ],
        )

    def _get_severity(self, error_message: str) -> Priority:
        """Determine issue severity based on error message.

        Args:
            error_message: The error message from lychee

        Returns:
            Priority level for the issue
        """
        error_lower = error_message.lower()

        # 4xx errors are client errors (broken links)
        if any(code in error_message for code in ("404", "410", "403", "401")):
            return Priority.HIGH

        # Network errors may be temporary
        if "network" in error_lower or "timeout" in error_lower:
            return Priority.MEDIUM

        # Server errors might be temporary
        if any(code in error_message for code in ("500", "502", "503", "504")):
            return Priority.LOW

        return Priority.MEDIUM

import logging
import re

from crackerjack.agents.base import Issue, IssueType, Priority
from crackerjack.parsers.base import RegexParser

logger = logging.getLogger(__name__)


class LycheeRegexParser(RegexParser):
    LINE_PATTERN = re.compile(r"^(.+?):(\d+):\s*(https?://\S+)\s*\(([^)]+)\)$")

    def parse_text(self, output: str) -> list[Issue]:
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
        if not line:
            return False

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

        return "https://" in line or "http://" in line

    def _parse_single_lychee_line(self, line: str) -> Issue | None:
        match = self.LINE_PATTERN.match(line)
        if not match:
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

        url_match = re.search(r"(https?://\S+)", line)
        if not url_match:
            return None

        url = url_match.group(1)

        error_match = re.search(r"\(([^)]+)\)", line)
        error_message = error_match.group(1) if error_match else "Unknown error"

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
        prefix = line[:url_pos].strip().rstrip(":")

        if ":" in prefix:
            parts = prefix.rsplit(":", 1)
            file_path = parts[0].strip()
            try:
                line_number = int(parts[1].strip())
                return file_path, line_number
            except ValueError:
                return prefix, None

        return prefix or None, None

    def _create_lychee_issue(
        self,
        file_path: str | None,
        line_number: int | None,
        url: str,
        error_message: str,
    ) -> Issue:
        message = f"Broken link: {url} ({error_message})"

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
        error_lower = error_message.lower()

        if any(code in error_message for code in ("404", "410", "403", "401")):
            return Priority.HIGH

        if "network" in error_lower or "timeout" in error_lower:
            return Priority.MEDIUM

        if any(code in error_message for code in ("500", "502", "503", "504")):
            return Priority.LOW

        return Priority.MEDIUM

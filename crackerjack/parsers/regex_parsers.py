import logging
from typing import TYPE_CHECKING

from crackerjack.agents.base import Issue, IssueType, Priority
from crackerjack.parsers.base import RegexParser

if TYPE_CHECKING:
    from crackerjack.parsers.factory import ParserFactory

logger = logging.getLogger(__name__)


class CodespellRegexParser(RegexParser):
    def parse_text(self, output: str) -> list[Issue]:
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
        return bool(line and "==>" in line)

    def _parse_single_codespell_line(self, line: str) -> Issue | None:
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
        if "==>" in message_part:
            wrong_word, suggestions = message_part.split("==>", 1)
            return f"Spelling: '{wrong_word.strip()}' should be '{suggestions.strip()}'"
        return message_part.strip()


class RefurbRegexParser(RegexParser):
    def parse_text(self, output: str) -> list[Issue]:
        issues: list[Issue] = []

        for line in output.split("\n"):
            line = line.strip()
            if not self._should_parse_refurb_line(line):
                continue

            issue = self._parse_refurb_line(line)
            if issue:
                issues.append(issue)

        logger.debug(f"Parsed {len(issues)} issues from refurb")
        return issues

    def _should_parse_refurb_line(self, line: str) -> bool:
        return bool(
            line
            and "FURB" in line
            and ":" in line
            and not line.startswith(("Found", "Checked"))
        )

    def _parse_refurb_line(self, line: str) -> Issue | None:
        parts = line.split(":", 2)
        if len(parts) < 2:
            return None

        try:
            file_path = parts[0].strip()
            line_number = int(parts[1].strip())
            message = parts[2].strip() if len(parts) > 2 else line

            return Issue(
                type=IssueType.COMPLEXITY,
                severity=Priority.MEDIUM,
                message=message,
                file_path=file_path,
                line_number=line_number,
                stage="refurb",
            )
        except (ValueError, IndexError) as e:
            logger.debug(f"Failed to parse refurb line: {line} ({e})")
            return None


class RuffFormatRegexParser(RegexParser):
    def parse_text(self, output: str) -> list[Issue]:
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
    def parse_text(self, output: str) -> list[Issue]:
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
        return line.startswith("Failed functions:")

    def _is_failed_section_end(self, line: str, in_section: bool) -> bool:
        return in_section and (not line or line.startswith("─"))

    def _is_file_marker(self, line: str, in_section: bool) -> bool:
        return in_section and line.startswith("- ") and line.endswith(":")

    def _extract_file_from_marker(self, line: str) -> str:
        remaining = line[2:].strip()
        return remaining[:-1].strip()

    def _is_function_line(self, line: str, in_section: bool, has_file: bool) -> bool:
        return in_section and has_file and not line.startswith("- ") and "::" in line

    def _create_complexity_issue(self, line: str, file_path: str) -> Issue:
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
    def __init__(
        self, tool_name: str, issue_type: IssueType = IssueType.FORMATTING
    ) -> None:
        self.tool_name = tool_name
        self.issue_type = issue_type

    def parse_text(self, output: str) -> list[Issue]:
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
    def parse_text(self, output: str) -> list[Issue]:
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
        return bool(line and line.startswith("✗"))

    def _parse_single_structured_data_line(self, line: str) -> Issue | None:
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
        if line.startswith("✗"):
            line = line[1:].strip()

        if ":" not in line:
            return "", line

        file_path, error_message = line.split(":", 1)
        return file_path.strip(), error_message.strip()


class MypyRegexParser(RegexParser):
    def parse_text(self, output: str) -> list[Issue]:
        issues: list[Issue] = []

        for line in output.split("\n"):
            line = line.strip()
            if not self._should_parse_mypy_line(line):
                continue

            issue = self._parse_mypy_line(line)
            if issue:
                issues.append(issue)

        logger.debug(f"Parsed {len(issues)} issues from mypy/zuban")
        return issues

    def _should_parse_mypy_line(self, line: str) -> bool:
        if not line:
            return False
        if line.startswith(("Found", "Checked", "Success")):
            return False
        return bool(
            ":" in line and ("error" in line or "warning" in line or "note" in line)
        )

    def _parse_mypy_line(self, line: str) -> Issue | None:
        try:
            parts = line.split(":", 3)
            if len(parts) < 3:
                return None

            file_path = parts[0].strip()
            line_number = self._extract_mypy_line_number(parts)
            message = self._extract_mypy_message(parts, line)
            severity = self._extract_mypy_severity(line)

            return Issue(
                type=IssueType.TYPE_ERROR,
                severity=severity,
                message=message,
                file_path=file_path,
                line_number=line_number,
                stage="zuban",
            )
        except (ValueError, IndexError) as e:
            logger.debug(f"Failed to parse mypy line: {line} ({e})")
            return None

    def _extract_mypy_line_number(self, parts: list[str]) -> int | None:
        if len(parts) > 1 and parts[1].strip().isdigit():
            return int(parts[1].strip())
        return None

    def _extract_mypy_message(self, parts: list[str], full_line: str) -> str:
        if len(parts) >= 4:
            return parts[3].strip()
        return full_line

    def _extract_mypy_severity(self, line: str) -> Priority:
        if "error" in line.lower():
            return Priority.HIGH
        return Priority.MEDIUM


class CreosoteRegexParser(RegexParser):
    def parse_text(self, output: str) -> list[Issue]:
        issues: list[Issue] = []

        for line in output.split("\n"):
            line = line.strip()
            if not self._should_parse_creosote_line(line):
                continue

            line_issues = self._parse_creosote_line(line)
            issues.extend(line_issues)

        logger.debug(f"Parsed {len(issues)} issues from creosote")
        return issues

    def _should_parse_creosote_line(self, line: str) -> bool:
        if not line:
            return False
        if line.startswith(("Checked", "Found", "All dependencies")):
            return False
        return True

    def _parse_creosote_line(self, line: str) -> list[Issue]:
        if "Found unused dependencies:" in line:
            return self._parse_unused_dependencies_list(line)
        if line.startswith("- "):
            return self._parse_bulleted_dependency(line)
        if "unused-dependency" in line or "not being used" in line.lower():
            return self._parse_inline_dependency(line)
        return []

    def _parse_unused_dependencies_list(self, line: str) -> list[Issue]:
        deps_part = line.split(":", 1)[1].strip()
        deps = [d.strip() for d in deps_part.split(",")]
        return [self._create_creosote_issue(dep) for dep in deps if dep]

    def _parse_bulleted_dependency(self, line: str) -> list[Issue]:
        if line.startswith(("---", "====")):
            return []
        dep = line[2:].strip()
        if dep:
            return [self._create_creosote_issue(dep)]
        return []

    def _parse_inline_dependency(self, line: str) -> list[Issue]:
        import re

        match = re.search(r"\(([^)]+)\)", line)
        if match:
            dep = match.group(1)
            return [self._create_creosote_issue(dep)]
        return []

    def _create_creosote_issue(self, dep: str) -> Issue:
        return Issue(
            type=IssueType.COMPLEXITY,
            severity=Priority.MEDIUM,
            message=f"Unused dependency: {dep}",
            file_path="pyproject.toml",
            line_number=None,
            stage="creosote",
        )


def register_regex_parsers(factory: "ParserFactory") -> None:
    CodespellRegexParser()
    RefurbRegexParser()
    RuffFormatRegexParser()
    ComplexityRegexParser()
    CreosoteRegexParser()
    StructuredDataParser()

    factory.register_regex_parser("codespell", CodespellRegexParser)
    factory.register_regex_parser("refurb", RefurbRegexParser)
    factory.register_regex_parser("ruff-format", RuffFormatRegexParser)
    factory.register_regex_parser("complexity", ComplexityRegexParser)
    factory.register_regex_parser("creosote", CreosoteRegexParser)
    factory.register_regex_parser("mypy", MypyRegexParser)
    factory.register_regex_parser("zuban", MypyRegexParser)

    factory.register_regex_parser("check-yaml", StructuredDataParser)
    factory.register_regex_parser("check-toml", StructuredDataParser)
    factory.register_regex_parser("check-json", StructuredDataParser)

    logger.info(
        "Registered regex parsers: codespell, refurb, ruff-format, complexity, "
        "creosote, mypy, zuban, check-yaml, check-toml, check-json"
    )

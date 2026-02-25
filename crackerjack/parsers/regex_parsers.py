import logging
from typing import TYPE_CHECKING

from crackerjack.agents.base import Issue, IssueType, Priority
from crackerjack.parsers.base import RegexParser
from crackerjack.parsers.lychee_parser import LycheeRegexParser

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

        if not line:
            return False
        if line.startswith(
            ("Found", "Checked", "Success", "Running", "🔍", "✅", "❌", "⚠️")
        ):
            return False

        return ".py:" in line and len(line.split(":")) >= 3

    def _parse_refurb_line(self, line: str) -> Issue | None:
        parts = line.split(":", 3)
        if len(parts) < 3:
            return None

        try:
            file_path = parts[0].strip()
            line_number = int(parts[1].strip())
            message = parts[3].strip() if len(parts) > 3 else line

            refurb_code = self._extract_furb_code(message)

            return Issue(
                type=IssueType.REFURB,
                severity=Priority.MEDIUM,
                message=message,
                file_path=file_path,
                line_number=line_number,
                stage="refurb",
                details=[f"refurb_code: {refurb_code}"] if refurb_code else [],
            )
        except (ValueError, IndexError) as e:
            logger.debug(f"Failed to parse refurb line: {line} ({e})")
            return None

    def _extract_furb_code(self, message: str) -> str | None:
        import re

        match = re.search(r"\[?(FURB\d+)\]?:?", message)
        return match.group(1) if match else None


class PyscnRegexParser(RegexParser):
    def parse_text(self, output: str) -> list[Issue]:
        issues: list[Issue] = []

        for line in output.split("\n"):
            line = line.strip()
            if not self._should_parse_pyscn_line(line):
                continue

            issue = self._parse_pyscn_line(line)
            if issue:
                issues.append(issue)

        logger.debug(f"Parsed {len(issues)} issues from pyscn")
        return issues

    def _should_parse_pyscn_line(self, line: str) -> bool:
        if not line or not line.strip():
            return False

        skip_prefixes = (
            "🔍",
            "❌",
            "✅",
            "⚠️",
            "Running",
            "Usage:",
            "Available Commands",
            "Flags:",
            "Found",
            "Error:",
            "error:",
            "Warning:",
            "Checking",
            "Analyzing",
        )
        if line.startswith(skip_prefixes):
            return False

        return ".py:" in line and len(line.split(":")) >= 4

    def _parse_pyscn_line(self, line: str) -> Issue | None:
        parts = line.split(":", 3)
        if len(parts) < 4:
            return None

        try:
            file_path = parts[0].strip()
            line_number = int(parts[1].strip())
            message = parts[3].strip()

            severity = Priority.MEDIUM
            if "too complex" in message.lower():
                severity = Priority.HIGH
            elif "clone" in message.lower():
                severity = Priority.LOW

            return Issue(
                type=IssueType.COMPLEXITY,
                severity=severity,
                message=message,
                file_path=file_path,
                line_number=line_number,
                stage="pyscn",
            )
        except (ValueError, IndexError) as e:
            logger.debug(f"Failed to parse pyscn line: {line} ({e})")
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

        success_indicators = ("✓", "passed", "valid", "ok", "success", "no issues")
        output_lower = output.lower()
        if any(indicator in output_lower for indicator in success_indicators):
            logger.debug(f"{self.tool_name} passed (success indicators found)")
            return []

        failure_indicators = ("failed", "error", "invalid", "issue", "would be")
        if not any(indicator in output_lower for indicator in failure_indicators):
            logger.debug(
                f"{self.tool_name} produced unclear output, treating as success"
            )
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

        if line and not line.startswith(
            ("Checked", "Found", "All dependencies", "---", "====")
        ):
            return [self._create_creosote_issue(line)]
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
            type=IssueType.DEPENDENCY,
            severity=Priority.MEDIUM,
            message=f"Unused dependency: {dep}",
            file_path="pyproject.toml",
            line_number=None,
            stage="creosote",
        )


class LocalLinkCheckerRegexParser(RegexParser):
    def parse_text(self, output: str) -> list[Issue]:
        issues: list[Issue] = []

        for line in output.split("\n"):
            line = line.strip()
            if not line or ":" not in line:
                continue

            try:
                issue = self._parse_local_link_line(line)
                if issue:
                    issues.append(issue)
            except Exception as e:
                logger.debug(f"Failed to parse local link checker line: {line} ({e})")

        logger.debug(f"Parsed {len(issues)} issues from check-local-links")
        return issues

    def _parse_local_link_line(self, line: str) -> Issue | None:
        if " - " not in line:
            return None

        file_part, rest = line.split(" - ", 1)
        if ":" not in file_part:
            return None

        parts = file_part.split(":")
        if len(parts) < 2:
            return None

        file_path = parts[0]
        line_num = parts[1]

        link_parts = rest.split(" - ", 1) if " - " in rest else [rest]
        link_target = link_parts[0]
        message = link_parts[1] if len(link_parts) > 1 else "Broken link"

        return Issue(
            type=IssueType.DOCUMENTATION,
            severity=Priority.MEDIUM,
            message=f"Broken link: {link_target} - {message}",
            file_path=file_path,
            line_number=int(line_num) if line_num.isdigit() else None,
            stage="check-local-links",
            details=[f"Target file: {link_target}"],
        )


def register_regex_parsers(factory: "ParserFactory") -> None:
    factory.register_regex_parser("codespell", CodespellRegexParser)
    factory.register_regex_parser("refurb", RefurbRegexParser)
    factory.register_regex_parser("pyscn", PyscnRegexParser)
    factory.register_regex_parser("ruff", RuffRegexParser)
    factory.register_regex_parser("ruff-format", RuffFormatRegexParser)
    factory.register_regex_parser("complexipy", ComplexityRegexParser)
    factory.register_regex_parser("creosote", CreosoteRegexParser)
    factory.register_regex_parser("mypy", MypyRegexParser)
    factory.register_regex_parser("zuban", MypyRegexParser)
    factory.register_regex_parser("skylos", SkylosRegexParser)
    factory.register_regex_parser("check-local-links", LocalLinkCheckerRegexParser)
    factory.register_regex_parser("lychee", LycheeRegexParser)

    factory.register_regex_parser("check-yaml", StructuredDataParser)
    factory.register_regex_parser("check-toml", StructuredDataParser)
    factory.register_regex_parser("check-json", StructuredDataParser)

    factory.register_regex_parser(
        "validate-regex-patterns", ValidateRegexPatternsParser
    )
    factory.register_regex_parser("trailing-whitespace", TrailingWhitespaceParser)
    factory.register_regex_parser("end-of-file-fixer", EndOfFileFixerParser)
    factory.register_regex_parser("format-json", FormatJsonParser)
    factory.register_regex_parser("mdformat", MdformatParser)
    factory.register_regex_parser("uv-lock", UvLockParser)
    factory.register_regex_parser("check-added-large-files", CheckAddedLargeFilesParser)
    factory.register_regex_parser("check-ast", CheckAstParser)

    logger.info(
        "Registered regex parsers: codespell, refurb, pyscn, ruff, ruff-format, complexipy, "
        "creosote, mypy, zuban, skylos, check-local-links, lychee, check-yaml, check-toml, check-json, "
        "validate-regex-patterns, trailing-whitespace, end-of-file-fixer, format-json, "
        "mdformat, uv-lock, check-added-large-files, check-ast"
    )


class SkylosRegexParser(RegexParser):
    def parse_text(self, output: str) -> list[Issue]:
        issues: list[Issue] = []

        for line in output.split("\n"):
            line = line.strip()
            if not self._should_parse_skylos_line(line):
                continue

            try:
                issue = self._parse_skylos_line(line)
                if issue:
                    issues.append(issue)
            except Exception as e:
                logger.debug(f"Failed to parse skylos line: {line} ({e})")

        logger.debug(f"Parsed {len(issues)} issues from skylos")
        return issues

    def _should_parse_skylos_line(self, line: str) -> bool:
        return bool(line and "ERROR" in line and "-" in line and ":" in line)

    def _parse_skylos_line(self, line: str) -> Issue | None:

        error_idx = line.find(" - ERROR - ")
        if error_idx == -1:
            return None

        error_part = line[error_idx + 11 :].strip()

        if ":" not in error_part:
            return None

        file_end = error_part.find(":")
        file_path = error_part[:file_end].strip()
        message = error_part[file_end + 1 :].strip()

        line_number = None
        if "line " in message:
            import re

            match = re.search(r"line (\d+)", message)
            if match:
                line_number = int(match.group(1))

        return Issue(
            type=IssueType.DEAD_CODE,
            severity=Priority.MEDIUM,
            message=message[:200],
            file_path=file_path,
            line_number=line_number,
            details=[line],
            stage="skylos",
        )


class ValidateRegexPatternsParser(GenericRegexParser):
    def __init__(self) -> None:
        super().__init__("validate-regex-patterns", IssueType.FORMATTING)


class TrailingWhitespaceParser(GenericRegexParser):
    def __init__(self) -> None:
        super().__init__("trailing-whitespace", IssueType.FORMATTING)


class EndOfFileFixerParser(GenericRegexParser):
    def __init__(self) -> None:
        super().__init__("end-of-file-fixer", IssueType.FORMATTING)


class FormatJsonParser(GenericRegexParser):
    def __init__(self) -> None:
        super().__init__("format-json", IssueType.FORMATTING)


class MdformatParser(GenericRegexParser):
    def __init__(self) -> None:
        super().__init__("mdformat", IssueType.FORMATTING)


class UvLockParser(GenericRegexParser):
    def __init__(self) -> None:
        super().__init__("uv-lock", IssueType.DEPENDENCY)


class CheckAddedLargeFilesParser(RegexParser):
    def __init__(self) -> None:
        self.tool_name = "check-added-large-files"

    def parse_text(self, output: str) -> list[Issue]:
        issues: list[Issue] = []

        if not output or not output.strip():
            return []

        if "Large files detected:" not in output:
            return []

        lines = output.strip().split("\n")
        parsing_files = False

        for line in lines:
            line = line.strip()

            if "Large files detected:" in line:
                parsing_files = True
                continue

            if not parsing_files:
                continue

            if line and not line.startswith("Large files"):
                parts = line.split(":", 1)
                if len(parts) == 2:
                    file_path = parts[0].strip()
                    size_str = parts[1].strip()

                    issues.append(
                        Issue(
                            type=IssueType.FORMATTING,
                            severity=Priority.MEDIUM,
                            message=f"Large file detected: {file_path} ({size_str})",
                            file_path=file_path,
                            line_number=None,
                        )
                    )

        logger.debug(
            f"Parsed {len(issues)} large file issues from check-added-large-files"
        )
        return issues


class CheckAstParser(GenericRegexParser):
    def __init__(self) -> None:
        super().__init__("check-ast", IssueType.FORMATTING)


class RuffRegexParser(RegexParser):
    def __init__(self) -> None:
        self.tool_name = "ruff"

    def parse_text(self, output: str) -> list[Issue]:
        issues: list[Issue] = []
        lines = output.strip().split("\n")

        i = 0
        while i < len(lines):
            line = lines[i].strip()

            diagnostic_issue = self._try_parse_diagnostic_format(lines, i)
            if diagnostic_issue is not None:
                issues.append(diagnostic_issue)
                i = self._skip_multiline_context(lines, i)
                continue

            concise_issue = self._try_parse_concise_format(line)
            if concise_issue:
                issues.append(concise_issue)

            i += 1

        return issues

    def _try_parse_diagnostic_format(
        self, lines: list[str], current_index: int
    ) -> Issue | None:
        if current_index == 0:
            return None

        line = lines[current_index].strip()
        if not line.startswith("-->"):
            return None

        prev_line = lines[current_index - 1].strip()
        return self._parse_diagnostic_format(prev_line, line)

    def _skip_multiline_context(self, lines: list[str], start_index: int) -> int:
        i = start_index + 1
        while i < len(lines) and self._is_context_line(lines[i]):
            i += 1
        return i

    def _is_context_line(self, line: str) -> bool:
        return line.startswith("|") or line.strip() == ""

    def _try_parse_concise_format(self, line: str) -> Issue | None:
        if not self._is_concise_format_line(line):
            return None

        return self._parse_concise_format(line)

    def _is_concise_format_line(self, line: str) -> bool:
        return ":" in line and len(line.split(":")) >= 4

    def _parse_diagnostic_format(self, code_line: str, arrow_line: str) -> Issue | None:
        import re
        from pathlib import Path

        code_match = re.match(r"^([A-Z]+\d+)\s+(.+)$", code_line)
        if not code_match:
            return None

        code = code_match.group(1)
        message = code_match.group(2).strip()

        arrow_match = re.search(r"-->\s+(\S+):(\d+):(\d+)", arrow_line)
        if not arrow_match:
            return None

        try:
            file_path = Path(arrow_match.group(1))
            line_number = int(arrow_match.group(2))
            int(arrow_match.group(3))

            return Issue(
                type=IssueType.COMPLEXITY
                if code.startswith("C9")
                else IssueType.FORMATTING,
                severity=Priority.HIGH
                if code.startswith(("C9", "S", "E"))
                else Priority.MEDIUM,
                message=f"{code} {message}",
                file_path=file_path,
                line_number=line_number,
                stage="ruff-check",
                details=[f"code: {code}"],
            )
        except (ValueError, IndexError):
            return None

    def _parse_concise_format(self, line: str) -> Issue | None:
        from pathlib import Path

        parts = line.split(":", maxsplit=3)
        if len(parts) < 4:
            return None

        try:
            file_path = Path(parts[0].strip())
            line_number = int(parts[1].strip())
            (int(parts[2].strip()) if parts[2].strip().isdigit() else None)

            message_part = parts[3].strip()
            code, message = self._extract_code_and_message(message_part)

            return Issue(
                type=IssueType.COMPLEXITY
                if code and code.startswith("C9")
                else IssueType.FORMATTING,
                severity=Priority.HIGH
                if code and code.startswith(("C9", "S", "E"))
                else Priority.MEDIUM,
                message=f"{code} {message}" if code else message,
                file_path=file_path,
                line_number=line_number,
                stage="ruff-check",
                details=[f"code: {code}"] if code else [],
            )

        except (ValueError, IndexError):
            return None

    def _extract_code_and_message(self, message_part: str) -> tuple[str | None, str]:
        if " " not in message_part:
            return None, message_part

        code_candidate = message_part.split()[0]
        if code_candidate.strip():
            code = code_candidate
            message = message_part[len(code) :].strip()
            return code, message

        return None, message_part

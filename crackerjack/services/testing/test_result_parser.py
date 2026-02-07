
from __future__ import annotations

import json
import logging
import re
import typing as t
from dataclasses import dataclass, field
from enum import Enum
from pathlib import Path

from crackerjack.agents.base import Issue, IssueType, Priority

if t.TYPE_CHECKING:
    pass


logger = logging.getLogger(__name__)


class TestErrorType(str, Enum):

    FIXTURE_ERROR = "fixture_error"
    IMPORT_ERROR = "import_error"
    ASSERTION_ERROR = "assertion_error"
    ATTRIBUTE_ERROR = "attribute_error"
    MOCK_SPEC_ERROR = "mock_spec_error"
    MISSING_IMPORT = "missing_import"
    HARDCODED_PATH = "hardcoded_path"
    PYDANTIC_VALIDATION = "pydantic_validation"
    TYPE_ERROR = "type_error"
    RUNTIME_ERROR = "runtime_error"
    UNKNOWN = "unknown"


@dataclass
class TestFailure:

    test_name: str
    file_path: Path
    line_number: int | None
    error_type: TestErrorType
    error_message: str
    traceback: list[str] = field(default_factory=list)
    stage: str = "call"

    def to_issue(self) -> Issue:
        return Issue(
            type=IssueType.TEST_FAILURE,
            severity=Priority.HIGH,
            message=f"{self.error_type.value}: {self.error_message}",
            file_path=str(self.file_path),
            line_number=self.line_number,
            stage="pytest",
            details=[
                f"test_name: {self.test_name}",
                f"error_type: {self.error_type.value}",
                f"traceback: {'\n'.join(self.traceback)}",
                f"stage: {self.stage}",
            ],
        )


class TestResultParser:

    def __init__(self) -> None:
        self._error_patterns = self._build_error_patterns()

    def parse_text_output(self, output: str) -> list[TestFailure]:
        failures = []


        failure_sections = self._split_failure_sections(output)

        for section in failure_sections:
            failure = self._parse_failure_section(section)
            if failure:
                failures.append(failure)

        logger.info(
            "Parsed pytest text output",
            extra={
                "total_failures": len(failures),
                "error_types": {f.error_type.value for f in failures},
            },
        )

        return failures

    def parse_json_output(self, output: str) -> list[TestFailure]:
        try:
            data = json.loads(output)
        except json.JSONDecodeError as e:
            logger.error(f"Failed to parse pytest JSON output: {e}")
            return []

        failures = []


        for test in data.get("tests", []):
            if test.get("outcome") in ("failed", "error"):
                failure = self._parse_json_test(test)
                if failure:
                    failures.append(failure)

        logger.info(
            "Parsed pytest JSON output",
            extra={
                "total_failures": len(failures),
                "error_types": {f.error_type.value for f in failures},
            },
        )

        return failures

    def _split_failure_sections(self, output: str) -> list[str]:

        section_pattern = r"_{20,}\s+(.+?)\s+_{20,}"

        sections: list[str] = []
        current_section: list[str] = []

        lines = output.split("\n")
        in_failure = False

        for line in lines:
            match = re.match(section_pattern, line)

            if match:

                if in_failure and current_section:
                    sections.append("\n".join(current_section))


                current_section = [line]
                in_failure = True
            elif in_failure:
                current_section.append(line)


        if in_failure and current_section:
            sections.append("\n".join(current_section))

        return sections

    def _parse_failure_section(self, section: str) -> TestFailure | None:
        try:

            test_name = self._extract_test_name(section)
            if not test_name:
                return None


            file_path, line_number = self._extract_test_location(section, test_name)
            if not file_path:
                return None


            error_type, error_message = self._classify_error(section)


            traceback = self._extract_traceback(section)


            stage = self._determine_stage(section)

            return TestFailure(
                test_name=test_name,
                file_path=file_path,
                line_number=line_number,
                error_type=error_type,
                error_message=error_message,
                traceback=traceback,
                stage=stage,
            )

        except Exception as e:
            logger.warning(f"Failed to parse failure section: {e}")
            return None

    def _extract_test_name(self, section: str) -> str | None:

        header_pattern = r"_{20,}\s+(.+?)\s+_{20,}"

        match = re.search(header_pattern, section)
        if match:
            return match.group(1)


        lines = section.split("\n")[:5]
        for line in lines:
            if "::" in line and ("FAILED" in line or "ERROR" in line):
                parts = line.split()[0]
                return parts

        return None

    def _extract_test_location(
        self, section: str, test_name: str
    ) -> tuple[Path, int | None]:

        pattern1 = r"^(.+\.py):(\d+):"
        for line in section.split("\n")[:20]:
            match = re.match(pattern1, line)
            if match:
                return Path(match.group(1)), int(match.group(2))


        pattern2 = r'File "(.+\.py)", line (\d+)'
        match = re.search(pattern2, section)
        if match:
            return Path(match.group(1)), int(match.group(2))


        if "::" in test_name:
            file_part = test_name.split("::")[0]
            if file_part.endswith(".py"):
                return Path(file_part), None


        return Path("unknown.py"), None

        traceback_lines = []
        in_traceback = False

        for line in section.split("\n"):
            line = line.rstrip()

            if line.startswith("Traceback (most recent call last)"):
                in_traceback = True
                traceback_lines.append(line)
            elif in_traceback:

                if line and not line[0].isspace() and not line.startswith("Traceback"):
                    break
                traceback_lines.append(line)

        return traceback_lines

    def _determine_stage(self, section: str) -> str:
        section_lower = section.lower()

        if "error at teardown" in section_lower or "teardown error" in section_lower:
            return "teardown"
        if "error at setup" in section_lower or "setup error" in section_lower:
            return "setup"
        return "call"

    def _build_error_patterns(self) -> dict[TestErrorType, list[str]]:
        return {
            TestErrorType.FIXTURE_ERROR: [
                r"fixture '(\w+)' not found",
                r"FixtureError",
                r"cannot find fixture",
            ],
            TestErrorType.IMPORT_ERROR: [
                r"ImportError",
                r"ModuleNotFoundError",
                r"No module named '?(\w+)'?",
            ],
            TestErrorType.ASSERTION_ERROR: [
                r"AssertionError",
                r"assert .+ ==",
            ],
            TestErrorType.ATTRIBUTE_ERROR: [
                r"AttributeError: .+ has no attribute",
            ],
            TestErrorType.MOCK_SPEC_ERROR: [
                r"MockSpec",
                r"spec.*Mock",
            ],
            TestErrorType.PYDANTIC_VALIDATION: [
                r"ValidationError",
                r"validation error",
            ],
            TestErrorType.TYPE_ERROR: [
                r"TypeError",
            ],
        }


    def _parse_json_test(self, test_data: dict) -> TestFailure | None:
        try:
            test_name = test_data.get("nodeid", "")
            if not test_name:
                return None


            file_part = test_name.split("::")[0]
            file_path = Path(file_part)


            stage = "call"

            for key in ("setup", "call", "teardown"):
                if key in test_data:
                    stage = key
                    break


            stage_data = test_data.get(stage, {})
            traceback_list = stage_data.get("traceback", "").split("\n")
            longrepr = stage_data.get("longrepr", "")


            error_type, error_message = self._classify_error(longrepr)


            line_number = None
            if traceback_list:
                for line in traceback_list:
                    match = re.search(r'File "(.+\.py)", line (\d+)', line)
                    if match:
                        if match.group(1) == str(file_path):
                            line_number = int(match.group(2))
                            break

            return TestFailure(
                test_name=test_name,
                file_path=file_path,
                line_number=line_number,
                error_type=error_type,
                error_message=error_message,
                traceback=traceback_list,
                stage=stage,
            )

        except Exception as e:
            logger.warning(f"Failed to parse JSON test data: {e}")
            return None

    def _check_fixture_error(
        self, section: str, section_lower: str
    ) -> tuple[TestErrorType, str] | None:
        if "fixture" in section_lower and "not found" in section_lower:
            match = re.search(r"fixture '(\w+)' not found", section)
            fixture_name = match.group(1) if match else "unknown"
            return (TestErrorType.FIXTURE_ERROR, f"Fixture '{fixture_name}' not found")
        return None

    def _check_import_error(
        self, section: str, section_lower: str
    ) -> tuple[TestErrorType, str] | None:
        if any(
            x in section_lower for x in ("importerror", "modulenotfounderror", "no module named")
        ):
            match = re.search(r"(?:No module named|import).*?'(\w+)'", section)
            module_name = match.group(1) if match else "unknown"
            return (TestErrorType.IMPORT_ERROR, f"Cannot import module '{module_name}'")
        return None

    def _check_mock_spec_error(
        self, section: str, section_lower: str
    ) -> tuple[TestErrorType, str] | None:
        if "mockspec" in section_lower or ("spec" in section_lower and "mock" in section_lower):
            return (TestErrorType.MOCK_SPEC_ERROR, "Mock specification error")
        return None

    def _check_attribute_error(
        self, section: str, section_lower: str
    ) -> tuple[TestErrorType, str] | None:
        if "attributeerror" in section_lower:
            match = re.search(r"AttributeError: (.+)", section)
            message = match.group(1) if match else "has no attribute"
            return (TestErrorType.ATTRIBUTE_ERROR, message)
        return None

    def _check_validation_error(
        self, section: str, section_lower: str
    ) -> tuple[TestErrorType, str] | None:
        if "validationerror" in section_lower or "validation error" in section_lower:
            match = re.search(r"(?:ValidationError|validation error): (.+)", section)
            message = match.group(1) if match else "Validation failed"
            return (TestErrorType.PYDANTIC_VALIDATION, message)
        return None

    def _check_type_error(
        self, section: str, section_lower: str
    ) -> tuple[TestErrorType, str] | None:
        if "typeerror" in section_lower or "type error" in section_lower:
            match = re.search(r"TypeError: (.+)", section)
            message = match.group(1) if match else "Type mismatch"
            return (TestErrorType.TYPE_ERROR, message)
        return None

    def _check_assertion_error(
        self, section: str, section_lower: str
    ) -> tuple[TestErrorType, str] | None:
        if "assertionerror" in section_lower or "assert" in section_lower:
            match = re.search(r"AssertionError: (.+)", section)
            if match:
                return (TestErrorType.ASSERTION_ERROR, match.group(1))

            if "assert " in section and " ==" in section:
                return (
                    TestErrorType.ASSERTION_ERROR,
                    "Assertion failed: values are not equal",
                )

            return (TestErrorType.ASSERTION_ERROR, "Assertion failed")
        return None

    def _check_hardcoded_path(
        self, section: str, section_lower: str
    ) -> tuple[TestErrorType, str] | None:
        if re.search(r"['\"/]test/path['\"]", section):
            return (TestErrorType.HARDCODED_PATH, "Hardcoded test path detected")
        return None

    def _check_undefined_name(
        self, section: str, section_lower: str
    ) -> tuple[TestErrorType, str] | None:
        if "name '(.+?)' is not defined" in section or "is not defined" in section_lower:
            match = re.search(r"name '(\w+)' is not defined", section)
            name = match.group(1) if match else "unknown"
            return (TestErrorType.MISSING_IMPORT, f"Name '{name}' is not defined")
        return None

    def _check_generic_error(
        self, section: str
    ) -> tuple[TestErrorType, str]:
        match = re.search(r"(\w+Error): (.+)", section)
        if match:
            return (TestErrorType.RUNTIME_ERROR, f"{match.group(1)}: {match.group(2)}")

        return (TestErrorType.UNKNOWN, "Unknown test failure")

    def _classify_error(self, section: str) -> tuple[TestErrorType, str]:
        section_lower = section.lower()


        for handler in [
            self._check_fixture_error,
            self._check_import_error,
            self._check_mock_spec_error,
            self._check_attribute_error,
            self._check_validation_error,
            self._check_type_error,
            self._check_assertion_error,
            self._check_hardcoded_path,
            self._check_undefined_name,
        ]:
            result = handler(section, section_lower)
            if result:
                return result


        return self._check_generic_error(section)
_default_parser: TestResultParser | None = None


def get_test_result_parser() -> TestResultParser:
    global _default_parser
    if _default_parser is None:
        _default_parser = TestResultParser()
    return _default_parser

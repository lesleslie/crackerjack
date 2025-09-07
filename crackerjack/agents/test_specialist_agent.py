from pathlib import Path

from ..services.regex_patterns import SAFE_PATTERNS
from .base import (
    AgentContext,
    FixResult,
    Issue,
    IssueType,
    SubAgent,
    agent_registry,
)


class TestSpecialistAgent(SubAgent):
    def __init__(self, context: AgentContext) -> None:
        super().__init__(context)
        self.common_test_patterns = {
            "fixture_not_found": SAFE_PATTERNS["fixture_not_found_pattern"].pattern,
            "import_error": SAFE_PATTERNS["import_error_pattern"].pattern,
            "assertion_error": SAFE_PATTERNS["assertion_error_pattern"].pattern,
            "attribute_error": SAFE_PATTERNS["attribute_error_pattern"].pattern,
            "mock_spec_error": SAFE_PATTERNS["mock_spec_error_pattern"].pattern,
            "hardcoded_path": SAFE_PATTERNS["hardcoded_path_pattern"].pattern,
            "missing_import": SAFE_PATTERNS["missing_name_pattern"].pattern,
            "pydantic_validation": SAFE_PATTERNS["pydantic_validation_pattern"].pattern,
        }

    def get_supported_types(self) -> set[IssueType]:
        return {IssueType.TEST_FAILURE, IssueType.IMPORT_ERROR}

    async def can_handle(self, issue: Issue) -> float:
        if issue.type not in self.get_supported_types():
            return 0.0

        perfect_match_score = self._check_perfect_test_matches(issue.message)
        if perfect_match_score > 0:
            return perfect_match_score

        pattern_score = self._check_test_patterns(issue.message)
        if pattern_score > 0:
            return pattern_score

        file_score = self._check_test_file_path(issue.file_path)
        if file_score > 0:
            return file_score

        return self._check_general_test_failure(issue.type)

    def _check_perfect_test_matches(self, message: str) -> float:
        message_lower = message.lower()
        test_keywords = [
            "failed test",
            "test failed",
            "pytest",
            "fixture",
            "assertion",
            "mock",
            "conftest",
        ]

        return (
            1.0 if any(keyword in message_lower for keyword in test_keywords) else 0.0
        )

    def _check_test_patterns(self, message: str) -> float:
        pattern_map = {
            SAFE_PATTERNS[
                "fixture_not_found_pattern"
            ].pattern: "fixture_not_found_pattern",
            SAFE_PATTERNS["import_error_pattern"].pattern: "import_error_pattern",
            SAFE_PATTERNS["assertion_error_pattern"].pattern: "assertion_error_pattern",
            SAFE_PATTERNS["attribute_error_pattern"].pattern: "attribute_error_pattern",
            SAFE_PATTERNS["mock_spec_error_pattern"].pattern: "mock_spec_error_pattern",
            SAFE_PATTERNS["hardcoded_path_pattern"].pattern: "hardcoded_path_pattern",
            SAFE_PATTERNS["missing_name_pattern"].pattern: "missing_name_pattern",
            SAFE_PATTERNS[
                "pydantic_validation_pattern"
            ].pattern: "pydantic_validation_pattern",
        }

        for pattern in self.common_test_patterns.values():
            if pattern in pattern_map:
                safe_pattern = SAFE_PATTERNS[pattern_map[pattern]]
                if safe_pattern.test(message):
                    return 0.9
        return 0.0

    def _check_test_file_path(self, file_path: str | None) -> float:
        if file_path and ("test_" in file_path or "/tests/" in file_path):
            return 0.8
        return 0.0

    def _check_general_test_failure(self, issue_type: IssueType) -> float:
        return 0.7 if issue_type == IssueType.TEST_FAILURE else 0.0

    async def analyze_and_fix(self, issue: Issue) -> FixResult:
        self.log(f"Analyzing test issue: {issue.message}")

        try:
            fixes_applied, files_modified = await self._apply_issue_fixes(issue)
            recommendations = self._get_failure_recommendations(fixes_applied)

            return self._create_fix_result(
                fixes_applied,
                files_modified,
                recommendations,
            )

        except Exception as e:
            self.log(f"Error fixing test issue: {e}", "ERROR")
            return self._create_error_fix_result(e)

    async def _apply_issue_fixes(self, issue: Issue) -> tuple[list[str], list[str]]:
        fixes_applied: list[str] = []
        files_modified: list[str] = []

        failure_type = self._identify_failure_type(issue)
        self.log(f"Identified failure type: {failure_type}")

        targeted_fixes = await self._apply_targeted_fixes(failure_type, issue)
        fixes_applied.extend(targeted_fixes)

        file_fixes, file_modified = await self._apply_file_fixes(issue)
        fixes_applied.extend(file_fixes)
        if file_modified and issue.file_path:
            files_modified.append(issue.file_path)

        general_fixes = await self._apply_general_test_fixes()
        fixes_applied.extend(general_fixes)

        return fixes_applied, files_modified

    async def _apply_targeted_fixes(self, failure_type: str, issue: Issue) -> list[str]:
        if failure_type == "fixture_not_found":
            return await self._fix_missing_fixtures(issue)
        if failure_type == "import_error":
            return await self._fix_import_errors(issue)
        if failure_type == "hardcoded_path":
            return await self._fix_hardcoded_paths(issue)
        if failure_type == "mock_spec_error":
            return await self._fix_mock_issues(issue)
        if failure_type == "pydantic_validation":
            return await self._fix_pydantic_issues(issue)
        return []

    async def _apply_file_fixes(self, issue: Issue) -> tuple[list[str], bool]:
        if not issue.file_path or not (
            "test_" in issue.file_path or "/tests/" in issue.file_path
        ):
            return [], False

        file_fixes = await self._fix_test_file_issues(issue.file_path)
        return file_fixes, len(file_fixes) > 0

    def _get_failure_recommendations(self, fixes_applied: list[str]) -> list[str]:
        if fixes_applied:
            return []

        return [
            "Check test file imports and fixture definitions",
            "Verify mock objects are properly configured",
            "Ensure test data paths use tmp_path fixture",
            "Review assertion statements for correctness",
        ]

    def _create_fix_result(
        self,
        fixes_applied: list[str],
        files_modified: list[str],
        recommendations: list[str],
    ) -> FixResult:
        success = len(fixes_applied) > 0
        confidence = 0.8 if success else 0.4

        return FixResult(
            success=success,
            confidence=confidence,
            fixes_applied=fixes_applied,
            files_modified=files_modified,
            recommendations=recommendations,
        )

    def _create_error_fix_result(self, error: Exception) -> FixResult:
        return FixResult(
            success=False,
            confidence=0.0,
            remaining_issues=[f"Failed to fix test issue: {error}"],
        )

    def _identify_failure_type(self, issue: Issue) -> str:
        message = issue.message

        pattern_map = {
            SAFE_PATTERNS[
                "fixture_not_found_pattern"
            ].pattern: "fixture_not_found_pattern",
            SAFE_PATTERNS["import_error_pattern"].pattern: "import_error_pattern",
            SAFE_PATTERNS["assertion_error_pattern"].pattern: "assertion_error_pattern",
            SAFE_PATTERNS["attribute_error_pattern"].pattern: "attribute_error_pattern",
            SAFE_PATTERNS["mock_spec_error_pattern"].pattern: "mock_spec_error_pattern",
            SAFE_PATTERNS["hardcoded_path_pattern"].pattern: "hardcoded_path_pattern",
            SAFE_PATTERNS["missing_name_pattern"].pattern: "missing_name_pattern",
            SAFE_PATTERNS[
                "pydantic_validation_pattern"
            ].pattern: "pydantic_validation_pattern",
        }

        for pattern_name, pattern in self.common_test_patterns.items():
            if pattern in pattern_map:
                safe_pattern = SAFE_PATTERNS[pattern_map[pattern]]
                if safe_pattern.test(message):
                    return pattern_name

        return "unknown"

    async def _fix_missing_fixtures(self, issue: Issue) -> list[str]:
        fixes: list[str] = []

        fixture_pattern = SAFE_PATTERNS["fixture_not_found_pattern"]
        if not fixture_pattern.test(issue.message):
            return fixes

        match = fixture_pattern.search(issue.message)
        if not match:
            return fixes

        fixture_name = match.group(1)
        self.log(f"Attempting to fix missing fixture: {fixture_name}")

        if fixture_name == "temp_pkg_path":
            fixes.extend(await self._add_temp_pkg_path_fixture(issue.file_path))
        elif fixture_name == "console":
            fixes.extend(await self._add_console_fixture(issue.file_path))
        elif fixture_name in ("tmp_path", "tmpdir"):
            fixes.extend(await self._add_temp_path_fixture(issue.file_path))

        return fixes

    async def _fix_import_errors(self, issue: Issue) -> list[str]:
        if not self._is_valid_file_path(issue.file_path) or issue.file_path is None:
            return []

        file_path = Path(issue.file_path)
        content = self.context.get_file_content(file_path)
        if not content:
            return []

        lines = content.split("\n")
        fixes, modified = self._apply_import_fixes(lines, content, issue.file_path)

        if modified:
            self._save_import_fixes(file_path, lines, issue.file_path)

        return fixes

    def _is_valid_file_path(self, file_path: str | None) -> bool:
        return file_path is not None and Path(file_path).exists()

    def _apply_import_fixes(
        self,
        lines: list[str],
        content: str,
        file_path: str,
    ) -> tuple[list[str], bool]:
        fixes: list[str] = []
        modified = False

        if self._needs_pytest_import(content):
            self._add_pytest_import(lines)
            fixes.append(f"Added missing pytest import to {file_path}")
            modified = True

        if self._needs_pathlib_import(content):
            lines.insert(0, "from pathlib import Path")
            fixes.append(f"Added missing pathlib import to {file_path}")
            modified = True

        if self._needs_mock_import(content):
            lines.insert(0, "from unittest.mock import Mock")
            fixes.append(f"Added missing Mock import to {file_path}")
            modified = True

        return fixes, modified

    def _needs_pytest_import(self, content: str) -> bool:
        return "pytest" not in content and "import pytest" not in content

    def _needs_pathlib_import(self, content: str) -> bool:
        return "Path(" in content and "from pathlib import Path" not in content

    def _needs_mock_import(self, content: str) -> bool:
        return "Mock()" in content and "from unittest.mock import Mock" not in content

    def _add_pytest_import(self, lines: list[str]) -> None:
        import_section_end = self._find_import_section_end(lines)
        lines.insert(import_section_end, "import pytest")

    def _find_import_section_end(self, lines: list[str]) -> int:
        import_section_end = 0
        for i, line in enumerate(lines):
            if line.strip().startswith(("import ", "from ")):
                import_section_end = i + 1
            elif line.strip() == "" and import_section_end > 0:
                break
        return import_section_end

    def _save_import_fixes(
        self,
        file_path: Path,
        lines: list[str],
        file_path_str: str,
    ) -> None:
        if self.context.write_file_content(file_path, "\n".join(lines)):
            self.log(f"Fixed imports in {file_path_str}")

    async def _fix_hardcoded_paths(self, issue: Issue) -> list[str]:
        fixes: list[str] = []

        if not issue.file_path:
            return fixes

        file_path = Path(issue.file_path)
        content = self.context.get_file_content(file_path)
        if not content:
            return fixes

        original_content = content

        content = (
            content.replace('Path("/test/path")', "tmp_path")
            .replace('"/test/path"', "str(tmp_path)")
            .replace("'/test/path'", "str(tmp_path)")
        )

        if content != original_content:
            if self.context.write_file_content(file_path, content):
                fixes.append(f"Fixed hardcoded paths in {issue.file_path}")
                self.log(f"Fixed hardcoded paths in {issue.file_path}")

        return fixes

    async def _fix_mock_issues(self, issue: Issue) -> list[str]:
        fixes: list[str] = []

        if (
            not self._is_valid_mock_issue_file(issue.file_path)
            or issue.file_path is None
        ):
            return fixes

        file_path = Path(issue.file_path)
        content = self.context.get_file_content(file_path)
        if not content:
            return fixes

        original_content = content
        content, mock_fixes = self._apply_mock_fixes_to_content(
            content,
            issue.file_path,
        )
        fixes.extend(mock_fixes)

        if content != original_content:
            self._save_mock_fixes(file_path, content, issue.file_path)

        return fixes

    def _is_valid_mock_issue_file(self, file_path: str | None) -> bool:
        return file_path is not None

    def _apply_mock_fixes_to_content(
        self,
        content: str,
        file_path: str,
    ) -> tuple[str, list[str]]:
        fixes: list[str] = []

        if self._needs_console_mock_fix(content):
            content = self._fix_console_mock_usage(content)
            fixes.append(f"Fixed Mock usage in {file_path}")

        return content, fixes

    def _needs_console_mock_fix(self, content: str) -> bool:
        return "console = Mock()" in content and "Console" not in content

    def _fix_console_mock_usage(self, content: str) -> str:
        content = content.replace("console = Mock()", "console = Console()")
        return self._ensure_console_import(content)

    def _ensure_console_import(self, content: str) -> str:
        if "from rich.console import Console" in content:
            return content

        lines = content.split("\n")
        lines = self._add_console_import_to_lines(lines)
        return "\n".join(lines)

    def _add_console_import_to_lines(self, lines: list[str]) -> list[str]:
        for i, line in enumerate(lines):
            if line.startswith("from rich") or "rich" in line:
                lines.insert(i + 1, "from rich.console import Console")
                return lines

        lines.insert(0, "from rich.console import Console")
        return lines

    def _save_mock_fixes(
        self,
        file_path: Path,
        content: str,
        file_path_str: str,
    ) -> None:
        if self.context.write_file_content(file_path, content):
            self.log(f"Fixed Mock issues in {file_path_str}")

    async def _fix_pydantic_issues(self, issue: Issue) -> list[str]:
        return []

    async def _add_temp_pkg_path_fixture(self, file_path: str | None) -> list[str]:
        if not file_path:
            return []

        fixes: list[str] = []
        path = Path(file_path)
        content = self.context.get_file_content(path)
        if not content:
            return fixes

        if "@pytest.fixture" in content and "temp_pkg_path" in content:
            return fixes

        fixture_code = '''
@pytest.fixture
def temp_pkg_path(tmp_path) -> Path:
    """Create temporary package path."""
    return tmp_path
'''

        lines = content.split("\n")

        for i, line in enumerate(lines):
            if line.startswith("class Test") and i > 0:
                lines.insert(i + 1, fixture_code)
                break
        else:
            lines.append(fixture_code)

        if self.context.write_file_content(path, "\n".join(lines)):
            fixes.append(f"Added temp_pkg_path fixture to {file_path}")

        return fixes

    async def _add_console_fixture(self, file_path: str | None) -> list[str]:
        if not file_path:
            return []

        fixes: list[str] = []
        path = Path(file_path)
        content = self.context.get_file_content(path)
        if not content:
            return fixes

        fixture_code = '''
@pytest.fixture
def console() -> Console:
    """Create console instance for testing."""
    return Console()
'''

        lines = content.split("\n")
        lines.append(fixture_code)

        if "from rich.console import Console" not in content:
            lines.insert(0, "from rich.console import Console")

        if self.context.write_file_content(path, "\n".join(lines)):
            fixes.append(f"Added console fixture to {file_path}")

        return fixes

    async def _add_temp_path_fixture(self, file_path: str | None) -> list[str]:
        return [
            f"Note: tmp_path is a built-in pytest fixture - check fixture usage in {file_path}",
        ]

    async def _fix_test_file_issues(self, file_path: str) -> list[str]:
        fixes: list[str] = []

        path = Path(file_path)
        content = self.context.get_file_content(path)
        if not content:
            return fixes

        original_content = content

        if "import pytest" not in content:
            lines = content.split("\n")
            lines.insert(0, "import pytest")
            content = "\n".join(lines)
            fixes.append(f"Added pytest import to {file_path}")

        from crackerjack.services.regex_patterns import apply_test_fixes

        content = apply_test_fixes(content)

        if content != original_content:
            if self.context.write_file_content(path, content):
                self.log(f"Applied general fixes to {file_path}")

        return fixes

    async def _apply_general_test_fixes(self) -> list[str]:
        fixes: list[str] = []

        returncode, _, stderr = await self.run_command(
            ["uv", "run", "python", "-m", "pytest", "--collect-only", "-q"],
        )

        if returncode != 0 and "ImportError" in stderr:
            fixes.append("Identified import issues in test collection")

        return fixes


agent_registry.register(TestSpecialistAgent)

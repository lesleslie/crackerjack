
from __future__ import annotations

import logging
import re
import typing as t
from pathlib import Path

from crackerjack.agents.base import (
    AgentContext,
    FixResult,
    Issue,
    IssueType,
    SubAgent,
)

if t.TYPE_CHECKING:
    from crackerjack.services.safe_code_modifier import SafeCodeModifier


logger = logging.getLogger(__name__)


class TestEnvironmentAgent(SubAgent):

    def __init__(self, context: AgentContext) -> None:
        super().__init__(context)
        self.name = "TestEnvironmentAgent"
        self._safe_modifier: SafeCodeModifier | None = None

    def _get_safe_modifier(self) -> SafeCodeModifier:
        if self._safe_modifier is None:
            from crackerjack.services.safe_code_modifier import SafeCodeModifier
            from rich.console import Console

            console = Console()
            self._safe_modifier = SafeCodeModifier(
                console=console,
                project_path=self.context.project_path,
            )

        return self._safe_modifier

    def get_supported_types(self) -> set[IssueType]:
        return {
            IssueType.TEST_FAILURE,
            IssueType.IMPORT_ERROR,
            IssueType.TEST_ORGANIZATION,
        }

    async def can_handle(self, issue: Issue) -> float:
        if issue.type not in self.get_supported_types():
            return 0.0

        if not issue.message:
            return 0.0

        message_lower = issue.message.lower()


        if "fixture" in message_lower and "not found" in message_lower:
            return 0.8


        if any(
            x in message_lower
            for x in ("importerror", "modulenotfounderror", "no module named")
        ):
            return 0.9


        if "pytest" in message_lower and any(
            x in message_lower
            for x in ("config", "ini", "pyproject", "plugin")
        ):
            return 0.7


        if "test" in message_lower and any(
            x in message_lower for x in ("not found", "collected", "discovery")
        ):
            return 0.7

        return 0.0

    async def analyze_and_fix(self, issue: Issue) -> FixResult:
        if not issue.file_path:
            return FixResult(
                success=False,
                confidence=0.0,
                remaining_issues=["No file path provided"],
            )

        message_lower = issue.message.lower()


        if "fixture" in message_lower and "not found" in message_lower:
            return await self._fix_missing_fixture(issue)

        if any(
            x in message_lower
            for x in ("importerror", "modulenotfounderror", "no module named")
        ):
            return await self._fix_import_error(issue)

        if "pytest" in message_lower:
            return await self._fix_pytest_config(issue)

        return FixResult(
            success=False,
            confidence=0.0,
            remaining_issues=[f"Unhandled test environment issue: {issue.message}"],
        )

    async def _fix_missing_fixture(self, issue: Issue) -> FixResult:

        match = re.search(r"fixture '(\w+)' not found", issue.message)
        if not match:
            return FixResult(
                success=False,
                confidence=0.0,
                remaining_issues=["Could not extract fixture name"],
            )

        fixture_name = match.group(1)
        file_path = Path(issue.file_path)


        parent = file_path.parent
        conftest_path = parent / "conftest.py" if parent else file_path.parent


        if self._can_create_fixture(fixture_name):
            if await self._create_fixture(conftest_path, fixture_name):
                return FixResult(
                    success=True,
                    confidence=0.8,
                    fixes_applied=[f"Created fixture '{fixture_name}' in conftest.py"],
                    files_modified=[str(conftest_path)],
                )


        if await self._add_fixture_parameter(file_path, fixture_name):  # type: ignore[untyped]
            return FixResult(
                success=True,
                confidence=0.9,
                fixes_applied=[f"Added fixture parameter '{fixture_name}' to test"],
                files_modified=[str(file_path)],
            )

        return FixResult(
            success=False,
            confidence=0.0,
            remaining_issues=[f"Could not automatically create fixture '{fixture_name}'"],
            recommendations=[
                f"Manually create fixture '{fixture_name}' in conftest.py",
                f"Or add fixture parameter to test function",
            ],
        )

    def _can_create_fixture(self, fixture_name: str) -> bool:
        simple_fixtures = {
            "temp_dir",
            "tmp_path",
            "tmpdir",
            "console",
            "sample_data",
            "test_data",
            "mock_service",
            "test_client",
        }

        return fixture_name.lower() in simple_fixtures

    async def _create_fixture(
        self, conftest_path: Path, fixture_name: str
    ) -> bool:
        try:

            if conftest_path.exists():
                content = self.context.get_file_content(conftest_path)
                if not content:
                    return False
            else:
                content = "# Test fixtures\n\nimport pytest\nfrom pathlib import Path\n\n"


            fixture_code = self._generate_fixture_code(fixture_name)


            new_content = content.rstrip() + "\n\n" + fixture_code + "\n"


            modifier = self._get_safe_modifier()
            return await modifier.apply_content_with_validation(
                file_path=conftest_path,
                new_content=new_content,
                context=f"Create fixture '{fixture_name}' in conftest.py",
            )

        except Exception as e:
            logger.error(f"Failed to create fixture: {e}")
            return False

    def _generate_fixture_code(self, fixture_name: str) -> str:
        name_lower = fixture_name.lower()

        if "tmp_path" in name_lower or "temp_dir" in name_lower:
            return f"""@pytest.fixture
def {fixture_name}(tmp_path: Path) -> Path:
    \"\"\"Fixture for temporary directory path.\"\"\"
    return tmp_path"""

        if "console" in name_lower:
            return """@pytest.fixture
def console():
    \"\"\"Fixture for console output capture.\"\"\"
    from rich.console import Console
    return Console()"""

        if "sample_data" in name_lower or "test_data" in name_lower:
            return f"""@pytest.fixture
def {fixture_name}():
    \"\"\"Fixture providing sample test data.\"\"\"
    return {{"key": "value", "test": True}}"""


        return f"""@pytest.fixture
def {fixture_name}():
    \"\"\"Fixture for {fixture_name}.\"\"\"
    # TODO: Implement fixture logic
    return None"""


    async def _fix_import_error(self, issue: Issue) -> FixResult:

        match = re.search(r"(?:No module named|import).*?'(\w+)'", issue.message)
        if not match:
            match = re.search(r"Cannot import\s+(\w+)", issue.message, re.IGNORECASE)

        if not match:
            return FixResult(
                success=False,
                confidence=0.0,
                remaining_issues=["Could not extract module name"],
            )

        module_name = match.group(1)
        file_path = Path(issue.file_path)


        if await self._add_import(file_path, module_name):
            return FixResult(
                success=True,
                confidence=0.9,
                fixes_applied=[f"Added import for '{module_name}'"],
                files_modified=[str(file_path)],
            )

        return FixResult(
            success=False,
            confidence=0.0,
            remaining_issues=[f"Could not automatically add import for '{module_name}'"],
            recommendations=[
                f"Manually add: from {module_name} import ...",
                f"Or add: import {module_name}",
            ],
        )

    async def _add_import(self, file_path: Path, module_name: str) -> bool:
        try:
            content = self.context.get_file_content(file_path)
            if not content:
                return False

            lines: list[str] = content.split("\n")


            import_index = 0
            for i, line in enumerate(lines):
                if line.startswith(("import ", "from ")):
                    import_index = i
                elif line.startswith("# ") and i > 0:

                    break


            import_statement = f"import {module_name}"


            lines.insert(import_index + 1, import_statement)

            new_content = "\n".join(lines)


            modifier = self._get_safe_modifier()
            return await modifier.apply_content_with_validation(
                file_path=file_path,
                new_content=new_content,
                context=f"Add import for '{module_name}'",
            )

        except Exception as e:
            logger.error(f"Failed to add import: {e}")
            return False

    async def _fix_pytest_config(self, issue: Issue) -> FixResult:

        project_root = self.context.project_path
        pyproject_path = project_root / "pyproject.toml"

        if not pyproject_path.exists():
            return await self._create_pytest_config(project_root)


        if await self._ensure_pytest_section(pyproject_path):
            return FixResult(
                success=True,
                confidence=0.7,
                fixes_applied=["Added/updated pytest configuration"],
                files_modified=[str(pyproject_path)],
            )

        return FixResult(
            success=False,
            confidence=0.0,
            remaining_issues=["Could not automatically fix pytest configuration"],
        )

    async def _create_pytest_config(self, project_root: Path) -> FixResult:
        try:

            pyproject_path = project_root / "pyproject.toml"
            config_content = """[tool.pytest.ini_options]

    async def _add_fixture_parameter(
        self, test_file_path: Path, fixture_name: str
    ) -> bool:
        try:
            content = self.context.get_file_content(test_file_path)
            if not content:
                return False


            lines: list[str] = content.split("\n")
            modified_lines: list[str] = []


            for i, line in enumerate(lines):
                modified_lines.append(line)


                if re.match(r"^\\s*def\\s+test_\\w+\\s*\\(", line):  # noqa: W605 (regex escape)

                    j = i
                    while j < len(lines):
                        if ")" in lines[j]:

                            indent_match = re.match(r"^\s*", lines[j])
                            indent = indent_match.group(0) if indent_match else "    "


                            modified_lines[-1] = lines[j].replace(
                                ")",
                                f", {fixture_name}:",
                            )


                            if not lines[j].rstrip().endswith(")"):
                                modified_lines.append(f"{indent})")

                            break
                        j += 1

                    break

            new_content = "\n".join(modified_lines)


            modifier = self._get_safe_modifier()
            return await modifier.apply_content_with_validation(
                file_path=test_file_path,
                new_content=new_content,
                context=f"Add fixture parameter '{fixture_name}' to test",
            )

        except Exception as e:
            logger.error(f"Failed to add fixture parameter: {e}")
            return False
testpaths = ["tests"]
python_files = ["test_*.py"]
python_classes = ["Test*"]
python_functions = ["test_*"]
addopts = "-v --tb=short"

[build-system]
requires = ["setuptools>=61.0", "wheel"]
build-backend = "setuptools.build_meta"
"""


            modifier = self._get_safe_modifier()
            success = await modifier.apply_content_with_validation(
                file_path=pyproject_path,
                new_content=config_content,
                context="Create pyproject.toml with pytest configuration",
            )

            if success:
                return FixResult(
                    success=True,
                    confidence=0.7,
                    fixes_applied=["Created pyproject.toml with pytest configuration"],
                    files_modified=[str(pyproject_path)],
                )

        except Exception as e:
            logger.error(f"Failed to create pytest config: {e}")

        return FixResult(
            success=False,
            confidence=0.0,
            remaining_issues=["Failed to create pytest configuration"],
        )

    async def _ensure_pytest_section(self, pyproject_path: Path) -> bool:
        try:
            content = self.context.get_file_content(pyproject_path)
            if not content:
                return False


            if "[tool.pytest.ini_options]" in content:
                return True


            pytest_section = """
[tool.pytest.ini_options]
testpaths = ["tests"]
python_files = ["test_*.py"]
python_classes = ["Test*"]
python_functions = ["test_*"]
"""

            new_content = content.rstrip() + "\n" + pytest_section


            modifier = self._get_safe_modifier()
            return await modifier.apply_content_with_validation(
                file_path=pyproject_path,
                new_content=new_content,
                context="Add [tool.pytest.ini_options] section to pyproject.toml",
            )

        except Exception as e:
            logger.error(f"Failed to add pytest section: {e}")
            return False


agent_registry = t.Any

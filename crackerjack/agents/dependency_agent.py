import re
import tomllib
from pathlib import Path

from .base import (
    AgentContext,
    FixResult,
    Issue,
    IssueType,
    SubAgent,
    agent_registry,
)


class DependencyAgent(SubAgent):
    def __init__(self, context: AgentContext) -> None:
        super().__init__(context)
        self.name = "DependencyAgent"

    def get_supported_types(self) -> set[IssueType]:
        return {IssueType.DEPENDENCY}

    async def can_handle(self, issue: Issue) -> float:
        if issue.type != IssueType.DEPENDENCY:
            return 0.0

        if not issue.message:
            return 0.0

        import re

        clean_message = re.sub(r"\x1b\[[0-9;]*m", "", issue.message)
        message_lower = clean_message.lower()

        if "unused dependency" in message_lower:
            return 0.9

        if issue.stage == "creosote":
            return 0.9

        if "dependency" in message_lower:
            return 0.5

        return 0.0

    def _extract_dependency_name(self, message: str) -> str | None:
        if not message:
            return None

        clean_message = re.sub(r"\x1b\[[0-9;]*m", "", message)
        clean_message = re.sub(r"\[\\[0-9]{1,3}m", "", clean_message)

        if "Found dependencies in pyproject.toml:" in clean_message:
            return None
        if "Oh no, bloated venv!" in clean_message:
            return None

        match = re.search(
            r"unused dependency:\s*([a-zA-Z0-9_-]+)$", clean_message, re.IGNORECASE
        )
        if match:
            return match.group(1)

        match = re.search(
            r"dependency\s+['\"]([^'\"]+)['\"]\s+is\s+unused",
            clean_message,
            re.IGNORECASE,
        )
        if match:
            return match.group(1)

        match = re.search(
            r"^([a-zA-Z0-9_-]+)\s+is\s+unused", clean_message, re.IGNORECASE
        )
        if match:
            return match.group(1)

        match = re.search(
            r"unused dependencies found:\s*([a-zA-Z0-9_-]+)",
            clean_message,
            re.IGNORECASE,
        )
        if match:
            return match.group(1)

        match = re.search(r"^([a-zA-Z0-9_-]+)$", clean_message.strip())
        if match:
            if "-" in match.group(1) or match.group(1).islower():
                return match.group(1)

        return None

    def _remove_dependency_from_toml(self, content: str, dep_name: str) -> str | None:
        """Remove dependency line from TOML content using regex patterns."""
        lines = content.splitlines(keepends=True)
        new_lines = []
        in_dependencies = False
        removed = False

        for line in lines:
            # Track dependency section
            in_dependencies = self._update_dependencies_state(
                line, in_dependencies
            )

            # Skip lines containing the dependency
            if self._should_remove_line(line, dep_name, in_dependencies):
                removed = True
                continue

            new_lines.append(line)

        return "".join(new_lines) if removed else None

    def _update_dependencies_state(self, line: str, current_state: bool) -> bool:
        """Update whether we're in the dependencies section."""
        stripped = line.strip()

        # Enter dependencies section
        if "dependencies" in line and "=" in line:
            return True

        # Exit dependencies section (end of list/dict)
        if current_state and stripped.startswith("[") and "dependencies" not in line:
            return False

        # Maintain current state
        return current_state

    def _should_remove_line(
        self, line: str, dep_name: str, in_dependencies: bool
    ) -> bool:
        """Check if line should be removed (contains the dependency)."""
        if not in_dependencies:
            return False

        if dep_name not in line:
            return False

        if line.strip().startswith("#"):
            return False

        return self._is_dependency_line(line, dep_name)

    def _is_dependency_line(self, line: str, dep_name: str) -> bool:
        """Check if line contains a dependency specification."""
        # Check all dependency patterns
        patterns = [
            f'"{dep_name}>=',
            f"'{dep_name}>=",
            f'"{dep_name}="',
            f"'{dep_name}='",
            f'"{dep_name}~',
            f"'{dep_name}~",
            f'"{dep_name}^',
            f"'{dep_name}^",
            f'"{dep_name}"',
            f"'{dep_name}'",
        ]

        line_stripped = line.strip()

        # Direct match (e.g., "package-name")
        if line_stripped.startswith(dep_name):
            return True

        # Pattern match (e.g., "package-name>=1.0.0")
        return any(pattern in line for pattern in patterns)

    async def analyze_and_fix(self, issue: Issue) -> FixResult:
        """Remove unused dependency from pyproject.toml."""
        # Validate inputs
        validation_result = self._validate_issue(issue)
        if validation_result:
            return validation_result

        file_path = Path(issue.file_path)
        dep_name = self._extract_dependency_name(issue.message)

        # Read and process file
        content = self.context.get_file_content(file_path)
        if not content:
            return self._error_result("Could not read pyproject.toml")

        # Remove dependency and write result
        new_content = self._remove_dependency_from_content(content, dep_name)
        if not new_content:
            return self._error_result(f"Failed to remove dependency {dep_name} from TOML")

        if self.context.write_file_content(file_path, new_content):
            return FixResult(
                success=True,
                confidence=0.9,
                fixes_applied=[f"Removed unused dependency: {dep_name}"],
                files_modified=[str(file_path)],
            )

        return self._error_result("Failed to write modified pyproject.toml")

    def _validate_issue(self, issue: Issue) -> FixResult | None:
        """Validate issue has required information.

        Returns FixResult if validation fails, None if valid.
        """
        if not issue.file_path:
            return FixResult(
                success=False,
                confidence=0.0,
                remaining_issues=["No file path provided"],
            )

        file_path = Path(issue.file_path)
        if file_path.name != "pyproject.toml":
            return FixResult(
                success=False,
                confidence=0.0,
                remaining_issues=[
                    "DependencyAgent can only fix dependencies in pyproject.toml"
                ],
            )

        dep_name = self._extract_dependency_name(issue.message)
        if not dep_name:
            return FixResult(
                success=False,
                confidence=0.0,
                remaining_issues=["Could not extract dependency name from message"],
            )

        return None

    def _error_result(self, message: str) -> FixResult:
        """Create an error FixResult with the given message."""
        return FixResult(
            success=False,
            confidence=0.0,
            remaining_issues=[message],
        )

    def _remove_dependency_from_content(self, content: str, dep_name: str) -> str | None:
        """Remove dependency from pyproject.toml content.

        Uses both TOML parsing and regex-based removal for robustness.
        """
        # Try TOML-based removal first
        try:
            data = tomllib.loads(content)

            if "project" not in data or "dependencies" not in data["project"]:
                return None  # No dependencies section

            deps = data["project"]["dependencies"]
            removed = self._remove_dependency_from_deps(deps, dep_name)

            if not removed:
                return None  # Dependency not found

            # If TOML parsing succeeded, use regex-based removal for text preservation
            return self._remove_dependency_from_toml(content, dep_name)

        except Exception:
            # Fall back to regex-based removal if TOML parsing fails
            return self._remove_dependency_from_toml(content, dep_name)

    def _remove_dependency_from_deps(self, deps: list | dict, dep_name: str) -> bool:
        """Remove dependency from dependencies list or dict.

        Returns True if dependency was found and removed, False otherwise.
        """
        if isinstance(deps, list):
            original_length = len(deps)
            new_deps = [dep for dep in deps if dep_name not in dep]
            if len(new_deps) == original_length:
                return False  # Dependency not found
            deps.clear()
            deps.extend(new_deps)
            return True

        if isinstance(deps, dict):
            if dep_name not in deps:
                return False  # Dependency not found
            del deps[dep_name]
            return True

        return False


agent_registry.register(DependencyAgent)

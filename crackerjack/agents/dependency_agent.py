"""Agent for fixing unused dependency issues.

This agent handles removal of unused dependencies from pyproject.toml,
using tomllib for safe TOML parsing and modification.
"""

import re
import tomllib
from io import StringIO
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
    """Agent that removes unused dependencies from pyproject.toml.

    Only removes clearly unused dependencies detected by creosote.
    Uses tomllib for safe TOML parsing and modification.
    """

    def __init__(self, context: AgentContext) -> None:
        super().__init__(context)
        self.name = "DependencyAgent"

    def get_supported_types(self) -> set[IssueType]:
        return {IssueType.DEPENDENCY}

    async def can_handle(self, issue: Issue) -> float:
        """Check if we can safely remove this dependency."""
        if issue.type != IssueType.DEPENDENCY:
            return 0.0

        if not issue.message:
            return 0.0

        message_lower = issue.message.lower()

        # Check if it's an unused dependency issue
        if "unused dependency" in message_lower:
            return 0.9

        # Other dependency issues might not be safe to auto-fix
        if "dependency" in message_lower:
            return 0.5

        return 0.0

    async def analyze_and_fix(self, issue: Issue) -> FixResult:
        """Remove unused dependency from pyproject.toml.

        Args:
            issue: The dependency issue to fix

        Returns:
            FixResult with success status and details
        """
        if not issue.file_path:
            return FixResult(
                success=False,
                confidence=0.0,
                remaining_issues=["No file path provided"],
            )

        file_path = Path(issue.file_path)

        # Only fix pyproject.toml files
        if file_path.name != "pyproject.toml":
            return FixResult(
                success=False,
                confidence=0.0,
                remaining_issues=[
                    "DependencyAgent can only fix dependencies in pyproject.toml"
                ],
            )

        content = self.context.get_file_content(file_path)
        if not content:
            return FixResult(
                success=False,
                confidence=0.0,
                remaining_issues=["Could not read pyproject.toml"],
            )

        # Extract dependency name from message
        # Message formats:
        # - "Unused dependency: pytest-snob"
        # - "Dependency 'pytest-snob' is unused"
        dep_name = self._extract_dependency_name(issue.message)
        if not dep_name:
            return FixResult(
                success=False,
                confidence=0.0,
                remaining_issues=["Could not extract dependency name from message"],
            )

        # Use tomllib to safely parse and modify
        try:
            # Parse the TOML file
            data = tomllib.loads(content)

            # Check if dependencies exist
            if "project" not in data or "dependencies" not in data["project"]:
                return FixResult(
                    success=False,
                    confidence=0.0,
                    remaining_issues=["No dependencies section found in pyproject.toml"],
                )

            deps = data["project"]["dependencies"]

            # Check if it's a list-style dependency
            if isinstance(deps, list):
                # Find and remove the dependency
                original_length = len(deps)
                new_deps = [dep for dep in deps if dep_name not in dep]

                if len(new_deps) == original_length:
                    return FixResult(
                        success=False,
                        confidence=0.0,
                        remaining_issues=[f"Dependency {dep_name} not found in dependencies list"],
                    )

                data["project"]["dependencies"] = new_deps

            # Check if it's a table-style dependency (not supported yet)
            elif isinstance(deps, dict):
                # Check if dependency exists in dict
                if dep_name not in deps:
                    return FixResult(
                        success=False,
                        confidence=0.0,
                        remaining_issues=[
                            f"Dependency {dep_name} not found in dependencies"
                        ],
                    )

                # Remove from dict
                del deps[dep_name]

            # Write back to TOML
            # Note: tomllib doesn't support writing, so we need to use a workaround
            # We'll use simple string replacement for now
            new_content = self._remove_dependency_from_toml(content, dep_name)

            if not new_content:
                return FixResult(
                    success=False,
                    confidence=0.0,
                    remaining_issues=[
                        f"Failed to remove dependency {dep_name} from TOML"
                    ],
                )

            if self.context.write_file_content(file_path, new_content):
                return FixResult(
                    success=True,
                    confidence=0.9,
                    fixes_applied=[f"Removed unused dependency: {dep_name}"],
                    files_modified=[str(file_path)],
                )

            return FixResult(
                success=False,
                confidence=0.0,
                remaining_issues=["Failed to write modified pyproject.toml"],
            )

        except Exception as e:
            return FixResult(
                success=False,
                confidence=0.0,
                remaining_issues=[f"Failed to parse pyproject.toml: {e}"],
            )

    def _extract_dependency_name(self, message: str) -> str | None:
        """Extract dependency name from issue message.

        Args:
            message: The issue message

        Returns:
            Dependency name or None if not found
        """
        if not message:
            return None

        # Pattern 1: "Unused dependency: pytest-snob"
        match = re.search(r"unused dependency:\s*([a-zA-Z0-9_-]+)", message, re.IGNORECASE)
        if match:
            return match.group(1)

        # Pattern 2: "Dependency 'pytest-snob' is unused"
        match = re.search(r"dependency\s+['\"]([^'\"]+)['\"]\s+is\s+unused", message, re.IGNORECASE)
        if match:
            return match.group(1)

        # Pattern 3: "pytest-snob is unused"
        match = re.search(r"^([a-zA-Z0-9_-]+)\s+is\s+unused", message, re.IGNORECASE)
        if match:
            return match.group(1)

        return None

    def _remove_dependency_from_toml(self, content: str, dep_name: str) -> str | None:
        """Remove dependency from TOML content using string manipulation.

        This is a workaround since tomllib doesn't support writing.

        Args:
            content: The TOML file content
            dep_name: The dependency name to remove

        Returns:
            Modified TOML content or None if failed
        """
        lines = content.splitlines(keepends=True)
        in_dependencies = False
        in_array = False
        removed = False

        new_lines = []
        for line in lines:
            # Check if we're entering dependencies section
            if "dependencies" in line and "=" in line:
                in_dependencies = True
                new_lines.append(line)
                continue

            # Check if we're in an array
            if in_dependencies and line.strip().startswith("["):
                in_array = True

            # Check if we're leaving the section
            if in_dependencies and line.strip().startswith("[") and "dependencies" not in line:
                in_dependencies = False
                in_array = False

            # Remove the dependency line
            if in_dependencies and dep_name in line and not line.strip().startswith("#"):
                # Check if it's actually this dependency (not just contains the name)
                # e.g., "pytest" should not match "pytest-snob"
                line_stripped = line.strip()
                if (
                    f'"{dep_name}"' in line
                    or f"'{dep_name}'" in line
                    or f'"{dep_name}\'' in line
                    or f"'{dep_name}\"" in line
                    or line_stripped.startswith(dep_name)
                ):
                    removed = True
                    continue  # Skip this line (remove the dependency)

            new_lines.append(line)

        if removed:
            return "".join(new_lines)

        return None


# Register the agent
agent_registry.register(DependencyAgent)

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
        lines = content.splitlines(keepends=True)
        in_dependencies = False
        removed = False

        new_lines = []

        for line in lines:
            if "dependencies" in line and "=" in line:
                in_dependencies = True
                new_lines.append(line)
                continue

            if in_dependencies and line.strip().startswith("["):
                pass

            if (
                in_dependencies
                and line.strip().startswith("[")
                and "dependencies" not in line
            ):
                in_dependencies = False

            if (
                in_dependencies
                and dep_name in line
                and not line.strip().startswith("#")
            ):
                line_stripped = line.strip()

                if (
                    f'"{dep_name}>=' in line
                    or f"'{dep_name}>=" in line
                    or f'"{dep_name}="' in line
                    or f"'{dep_name}='" in line
                    or f'"{dep_name}~' in line
                    or f"'{dep_name}~" in line
                    or f'"{dep_name}^' in line
                    or f"'{dep_name}^" in line
                    or f'"{dep_name}"' in line
                    or f"'{dep_name}'" in line
                    or line_stripped.startswith(dep_name)
                ):
                    removed = True
                    continue

            new_lines.append(line)

        if removed:
            return "".join(new_lines)

        return None

    async def analyze_and_fix(self, issue: Issue) -> FixResult:
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

        content = self.context.get_file_content(file_path)
        if not content:
            return FixResult(
                success=False,
                confidence=0.0,
                remaining_issues=["Could not read pyproject.toml"],
            )

        dep_name = self._extract_dependency_name(issue.message)
        if not dep_name:
            return FixResult(
                success=False,
                confidence=0.0,
                remaining_issues=["Could not extract dependency name from message"],
            )

        try:
            data = tomllib.loads(content)

            if "project" not in data or "dependencies" not in data["project"]:
                return FixResult(
                    success=False,
                    confidence=0.0,
                    remaining_issues=[
                        "No dependencies section found in pyproject.toml"
                    ],
                )

            deps = data["project"]["dependencies"]

            if isinstance(deps, list):
                original_length = len(deps)
                new_deps = [dep for dep in deps if dep_name not in dep]

                if len(new_deps) == original_length:
                    return FixResult(
                        success=False,
                        confidence=0.0,
                        remaining_issues=[
                            f"Dependency {dep_name} not found in dependencies list"
                        ],
                    )

                data["project"]["dependencies"] = new_deps

            elif isinstance(deps, dict):
                if dep_name not in deps:
                    return FixResult(
                        success=False,
                        confidence=0.0,
                        remaining_issues=[
                            f"Dependency {dep_name} not found in dependencies"
                        ],
                    )

                del deps[dep_name]

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


agent_registry.register(DependencyAgent)

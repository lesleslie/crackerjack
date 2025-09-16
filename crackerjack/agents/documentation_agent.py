import subprocess
import typing as t
from contextlib import suppress
from datetime import datetime
from pathlib import Path

from ..services.regex_patterns import SAFE_PATTERNS
from .base import (
    FixResult,
    Issue,
    IssueType,
    SubAgent,
    agent_registry,
)


class DocumentationAgent(SubAgent):
    def get_supported_types(self) -> set[IssueType]:
        return {IssueType.DOCUMENTATION}

    async def can_handle(self, issue: Issue) -> float:
        if issue.type == IssueType.DOCUMENTATION:
            return 0.8
        return 0.0

    async def analyze_and_fix(self, issue: Issue) -> FixResult:
        self.log(f"Analyzing documentation issue: {issue.message}")

        try:
            if "changelog" in issue.message.lower():
                return await self._update_changelog(issue)
            if (
                "agent count" in issue.message.lower()
                or "consistency" in issue.message.lower()
            ):
                return await self._fix_documentation_consistency(issue)
            if "api" in issue.message.lower() or "readme" in issue.message.lower():
                return await self._update_api_documentation(issue)
            return await self._general_documentation_update(issue)

        except Exception as e:
            return FixResult(
                success=False,
                confidence=0.0,
                remaining_issues=[f"Error processing documentation: {e}"],
            )

    async def _update_changelog(self, issue: Issue) -> FixResult:
        self.log("Updating changelog with recent changes")

        changelog_path = Path("CHANGELOG.md")

        recent_changes = self._get_recent_changes()

        if not recent_changes:
            return FixResult(
                success=True,
                confidence=0.7,
                recommendations=["No recent changes to add to changelog"],
            )

        changelog_entry = self._generate_changelog_entry(recent_changes)

        if changelog_path.exists():
            content = self.context.get_file_content(changelog_path)
            if content is None:
                return FixResult(
                    success=False,
                    confidence=0.0,
                    remaining_issues=[f"Failed to read {changelog_path}"],
                )
            updated_content = self._insert_changelog_entry(content, changelog_entry)
        else:
            updated_content = self._create_initial_changelog(changelog_entry)

        success = self.context.write_file_content(changelog_path, updated_content)

        if success:
            return FixResult(
                success=True,
                confidence=0.9,
                fixes_applied=[
                    f"Updated CHANGELOG.md with {len(recent_changes)} recent changes",
                ],
                files_modified=[str(changelog_path)],
            )

        return FixResult(
            success=False,
            confidence=0.0,
            remaining_issues=["Failed to write changelog updates"],
        )

    async def _fix_documentation_consistency(self, issue: Issue) -> FixResult:
        self.log("Checking documentation consistency")

        md_files = list[t.Any](Path().glob("*.md")) + list[t.Any](
            Path("docs").glob("*.md")
        )

        agent_count_issues = self._check_agent_count_consistency(md_files)

        files_modified: list[str] = []
        fixes_applied: list[str] = []

        for file_path, current_count, expected_count in agent_count_issues:
            content = self.context.get_file_content(file_path)
            if content:
                updated_content = self._fix_agent_count_references(
                    content,
                    current_count,
                    expected_count,
                )
                if updated_content != content:
                    success = self.context.write_file_content(
                        file_path,
                        updated_content,
                    )
                    if success:
                        files_modified.append(str(file_path))
                        fixes_applied.append(f"Updated agent count in {file_path.name}")

        if files_modified:
            return FixResult(
                success=True,
                confidence=0.85,
                fixes_applied=fixes_applied,
                files_modified=files_modified,
            )

        return FixResult(
            success=True,
            confidence=0.8,
            recommendations=["Documentation is already consistent"],
        )

    async def _update_api_documentation(self, issue: Issue) -> FixResult:
        self.log("Updating API documentation")

        api_changes = self._detect_api_changes()

        if not api_changes:
            return FixResult(
                success=True,
                confidence=0.7,
                recommendations=[
                    "No API changes detected requiring documentation updates",
                ],
            )

        readme_path = Path("README.md")
        if readme_path.exists():
            content = self.context.get_file_content(readme_path)
            if content is None:
                return FixResult(
                    success=False,
                    confidence=0.0,
                    remaining_issues=[f"Failed to read {readme_path}"],
                )
            updated_content = self._update_readme_examples(content, api_changes)

            if updated_content != content:
                success = self.context.write_file_content(readme_path, updated_content)
                if success:
                    return FixResult(
                        success=True,
                        confidence=0.8,
                        fixes_applied=["Updated README.md examples for API changes"],
                        files_modified=[str(readme_path)],
                    )

        return FixResult(
            success=False,
            confidence=0.5,
            remaining_issues=["Could not update API documentation"],
            recommendations=["Manual review of API documentation may be needed"],
        )

    async def _general_documentation_update(self, issue: Issue) -> FixResult:
        self.log("Performing general documentation update")

        return FixResult(
            success=True,
            confidence=0.6,
            recommendations=[
                f"Documentation issue identified: {issue.message}",
                "Manual review recommended for optimal documentation updates",
                "Consider adding specific patterns to DocumentationAgent",
            ],
        )

    def _get_recent_changes(self) -> list[dict[str, str]]:
        try:
            commit_range = self._get_commit_range()
            if not commit_range:
                return []

            commit_messages = self._get_commit_messages(commit_range)
            return self._parse_commit_messages(commit_messages)

        except Exception:
            return []

    def _get_commit_range(self) -> str:
        result = subprocess.run(
            ["git", "describe", "--tags", "--abbrev=0"],
            capture_output=True,
            text=True,
            check=False,
        )

        if result.returncode == 0:
            last_tag = result.stdout.strip()
            return f"{last_tag}..HEAD"

        return "-10"

    def _get_commit_messages(self, commit_range: str) -> str:
        result = subprocess.run(
            ["git", "log", commit_range, "--pretty=format: %s|%h|%an"],
            capture_output=True,
            text=True,
            check=False,
        )

        return result.stdout.strip() if result.returncode == 0 else ""

    def _parse_commit_messages(self, commit_output: str) -> list[dict[str, str]]:
        changes: list[dict[str, str]] = []

        for line in commit_output.split("\n"):
            if line:
                parts = line.split("|")
                if len(parts) >= 2:
                    change_info: dict[str, str] = {
                        "message": parts[0].strip(),
                        "hash": parts[1].strip(),
                        "author": parts[2].strip() if len(parts) > 2 else "Unknown",
                    }
                    changes.append(change_info)

        return changes

    def _generate_changelog_entry(self, changes: list[dict[str, str]]) -> str:
        date_str = datetime.now().strftime("%Y-%m-%d")
        entry_lines = [f"## [Unreleased] - {date_str}", ""]

        categorized_changes = self._categorize_changes(changes)
        self._add_categorized_changes_to_entry(entry_lines, categorized_changes)

        return "\n".join(entry_lines)

    def _categorize_changes(
        self,
        changes: list[dict[str, str]],
    ) -> dict[str, list[str]]:
        categories: dict[str, list[str]] = {
            "features": [],
            "fixes": [],
            "refactors": [],
            "other": [],
        }

        for change in changes:
            message = change["message"]
            category = self._get_change_category(message)
            categories[category].append(message)

        return categories

    def _get_change_category(self, message: str) -> str:
        if message.startswith(("feat: ", "feature: ")):
            return "features"
        if message.startswith("fix: "):
            return "fixes"
        if message.startswith(("refactor: ", "refact: ")):
            return "refactors"
        return "other"

    def _add_categorized_changes_to_entry(
        self,
        entry_lines: list[str],
        categories: dict[str, list[str]],
    ) -> None:
        section_mappings = {
            "features": "### Added",
            "fixes": "### Fixed",
            "refactors": "### Changed",
            "other": "### Other",
        }

        for category, section_title in section_mappings.items():
            items = categories[category]
            if items:
                self._add_section_to_entry(entry_lines, section_title, items)

    def _add_section_to_entry(
        self,
        entry_lines: list[str],
        section_title: str,
        items: list[str],
    ) -> None:
        entry_lines.append(section_title)
        for item in items:
            entry_lines.append(f"- {item}")
        entry_lines.append("")

    def _insert_changelog_entry(self, content: str, entry: str) -> str:
        lines = content.split("\n")

        insert_index = 0
        for i, line in enumerate(lines):
            if line.startswith(("# ", "## ")):
                if i > 0:
                    insert_index = i
                    break

        new_lines = (
            lines[:insert_index] + entry.split("\n") + [""] + lines[insert_index:]
        )
        return "\n".join(new_lines)

    def _create_initial_changelog(self, entry: str) -> str:
        return f"""# Changelog

All notable changes to this project will be documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.0.0/),
and this project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

{entry}
"""

    def _check_agent_count_consistency(
        self,
        md_files: list[Path],
    ) -> list[tuple[Path, int, int]]:
        expected_count = 9
        issues: list[tuple[Path, int, int]] = []
        patterns = self._get_agent_count_patterns()

        for file_path in md_files:
            issue = self._check_file_agent_count(file_path, patterns, expected_count)
            if issue:
                issues.append(issue)

        return issues

    def _get_agent_count_patterns(self) -> list[str]:
        return [
            SAFE_PATTERNS["agent_count_pattern"].pattern,
            SAFE_PATTERNS["specialized_agent_count_pattern"].pattern,
            SAFE_PATTERNS["total_agents_config_pattern"].pattern,
            SAFE_PATTERNS["sub_agent_count_pattern"].pattern,
        ]

    def _check_file_agent_count(
        self,
        file_path: Path,
        patterns: list[str],
        expected_count: int,
    ) -> tuple[Path, int, int] | None:
        with suppress(Exception):
            content = self.context.get_file_content(file_path)
            if not content:
                return None

            return self._analyze_file_content_for_agent_count(
                file_path, content, patterns, expected_count
            )

        return None

    def _analyze_file_content_for_agent_count(
        self,
        file_path: Path,
        content: str,
        patterns: list[str],
        expected_count: int,
    ) -> tuple[Path, int, int] | None:
        pattern_map = self._get_safe_pattern_map()

        for pattern in patterns:
            result = self._check_pattern_for_count_mismatch(
                pattern, pattern_map, content, file_path, expected_count
            )
            if result:
                return result

        return None

    def _get_safe_pattern_map(self) -> dict[str, str]:
        return {
            SAFE_PATTERNS["agent_count_pattern"].pattern: "agent_count_pattern",
            SAFE_PATTERNS[
                "specialized_agent_count_pattern"
            ].pattern: "specialized_agent_count_pattern",
            SAFE_PATTERNS[
                "total_agents_config_pattern"
            ].pattern: "total_agents_config_pattern",
            SAFE_PATTERNS["sub_agent_count_pattern"].pattern: "sub_agent_count_pattern",
        }

    def _check_pattern_for_count_mismatch(
        self,
        pattern: str,
        pattern_map: dict[str, str],
        content: str,
        file_path: Path,
        expected_count: int,
    ) -> tuple[Path, int, int] | None:
        if pattern not in pattern_map:
            return None

        safe_pattern = SAFE_PATTERNS[pattern_map[pattern]]
        if not safe_pattern.test(content):
            return None

        return self._find_count_mismatch_in_matches(
            safe_pattern, content, file_path, expected_count
        )

    def _find_count_mismatch_in_matches(
        self,
        safe_pattern: t.Any,
        content: str,
        file_path: Path,
        expected_count: int,
    ) -> tuple[Path, int, int] | None:
        matches = safe_pattern.findall(content)

        for match in matches:
            count = int(match)
            if self._is_count_mismatch(count, expected_count):
                return (file_path, count, expected_count)

        return None

    def _is_count_mismatch(self, count: int, expected_count: int) -> bool:
        return count != expected_count and count > 4

    def _fix_agent_count_references(
        self,
        content: str,
        current_count: int,
        expected_count: int,
    ) -> str:
        updated_content = content

        agent_pattern = SAFE_PATTERNS["update_agent_count"]
        specialized_pattern = SAFE_PATTERNS["update_specialized_agent_count"]
        config_pattern = SAFE_PATTERNS["update_total_agents_config"]
        sub_agent_pattern = SAFE_PATTERNS["update_sub_agent_count"]

        updated_content = agent_pattern.apply(updated_content).replace(
            "NEW_COUNT", str(expected_count)
        )
        updated_content = specialized_pattern.apply(updated_content).replace(
            "NEW_COUNT", str(expected_count)
        )
        updated_content = config_pattern.apply(updated_content).replace(
            "NEW_COUNT", str(expected_count)
        )
        updated_content = sub_agent_pattern.apply(updated_content).replace(
            "NEW_COUNT", str(expected_count)
        )

        return updated_content

    def _detect_api_changes(self) -> list[dict[str, str]]:
        try:
            result = subprocess.run(
                ["git", "diff", "--name-only", "HEAD~5..HEAD", "*.py"],
                capture_output=True,
                text=True,
                check=False,
            )

            if result.returncode != 0:
                return []

            changed_files = result.stdout.strip().split("\n")
            api_changes: list[dict[str, str]] = []

            for file_path in changed_files:
                if file_path and (
                    "api" in file_path.lower() or "__init__" in file_path
                ):
                    change_info: dict[str, str] = {
                        "file": file_path,
                        "type": "potential_api_change",
                    }
                    api_changes.append(change_info)

            return api_changes

        except Exception:
            return []

    def _update_readme_examples(
        self,
        content: str,
        api_changes: list[dict[str, str]],
    ) -> str:
        if api_changes and "TODO: Update examples" not in content:
            lines = content.split("\n")

            for i, line in enumerate(lines):
                if line.startswith("# ") and i < len(lines) - 1:
                    lines.insert(
                        i + 2,
                        "<!-- TODO: Update examples after recent API changes -->",
                    )
                    break
            return "\n".join(lines)

        return content


agent_registry.register(DocumentationAgent)

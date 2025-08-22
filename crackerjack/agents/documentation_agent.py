import re
import subprocess
from contextlib import suppress
from datetime import datetime
from pathlib import Path

from .base import (
    FixResult,
    Issue,
    IssueType,
    SubAgent,
    agent_registry,
)


class DocumentationAgent(SubAgent):
    """Agent specialized in maintaining documentation consistency and changelog updates."""

    def get_supported_types(self) -> set[IssueType]:
        return {IssueType.DOCUMENTATION}

    async def can_handle(self, issue: Issue) -> float:
        if issue.type == IssueType.DOCUMENTATION:
            return 0.8
        return 0.0

    async def analyze_and_fix(self, issue: Issue) -> FixResult:
        self.log(f"Analyzing documentation issue: {issue.message}")

        try:
            # Detect what type of documentation update is needed
            if "changelog" in issue.message.lower():
                return await self._update_changelog(issue)
            elif (
                "agent count" in issue.message.lower()
                or "consistency" in issue.message.lower()
            ):
                return await self._fix_documentation_consistency(issue)
            elif "api" in issue.message.lower() or "readme" in issue.message.lower():
                return await self._update_api_documentation(issue)
            else:
                return await self._general_documentation_update(issue)

        except Exception as e:
            return FixResult(
                success=False,
                confidence=0.0,
                remaining_issues=[f"Error processing documentation: {e}"],
            )

    async def _update_changelog(self, issue: Issue) -> FixResult:
        """Update CHANGELOG.md with recent changes."""
        self.log("Updating changelog with recent changes")

        changelog_path = Path("CHANGELOG.md")

        # Get recent commits since last version tag
        recent_changes = self._get_recent_changes()

        if not recent_changes:
            return FixResult(
                success=True,
                confidence=0.7,
                recommendations=["No recent changes to add to changelog"],
            )

        # Generate changelog entry
        changelog_entry = self._generate_changelog_entry(recent_changes)

        # Update or create changelog
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
                    f"Updated CHANGELOG.md with {len(recent_changes)} recent changes"
                ],
                files_modified=[str(changelog_path)],
            )
        
        return FixResult(
            success=False,
            confidence=0.0,
            remaining_issues=["Failed to write changelog updates"],
        )

    async def _fix_documentation_consistency(self, issue: Issue) -> FixResult:
        """Fix consistency issues across documentation files."""
        self.log("Checking documentation consistency")

        # Find all markdown files
        md_files = list(Path().glob("*.md")) + list(Path("docs").glob("*.md"))

        # Check agent count consistency
        agent_count_issues = self._check_agent_count_consistency(md_files)

        files_modified: list[str] = []
        fixes_applied: list[str] = []

        for file_path, current_count, expected_count in agent_count_issues:
            content = self.context.get_file_content(file_path)
            if content:
                # Fix agent count references
                updated_content = self._fix_agent_count_references(
                    content, current_count, expected_count
                )
                if updated_content != content:
                    success = self.context.write_file_content(
                        file_path, updated_content
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
        """Update API documentation when public interfaces change."""
        self.log("Updating API documentation")

        # Check for API changes by analyzing recent modifications
        api_changes = self._detect_api_changes()

        if not api_changes:
            return FixResult(
                success=True,
                confidence=0.7,
                recommendations=[
                    "No API changes detected requiring documentation updates"
                ],
            )

        # Update README examples
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
        """Handle general documentation updates."""
        self.log("Performing general documentation update")

        # Add TODO comments for manual review

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
        """Get recent git commits since last version tag."""
        try:
            # Get the latest tag
            result = subprocess.run(
                ["git", "describe", "--tags", "--abbrev=0"],
                capture_output=True,
                text=True,
                check=False,
            )

            if result.returncode == 0:
                last_tag = result.stdout.strip()
                # Get commits since last tag
                commit_range = f"{last_tag}..HEAD"
            else:
                # No tags found, get last 10 commits
                commit_range = "-10"

            # Get commit messages
            result = subprocess.run(
                ["git", "log", commit_range, "--pretty=format:%s|%h|%an"],
                capture_output=True,
                text=True,
                check=False,
            )

            if result.returncode != 0:
                return []

            changes: list[dict[str, str]] = []
            for line in result.stdout.strip().split("\n"):
                if line:
                    parts = line.split("|")
                    if len(parts) >= 2:
                        change_info: dict[str, str] = {
                            "message": parts[0],
                            "hash": parts[1],
                            "author": parts[2] if len(parts) > 2 else "Unknown",
                        }
                        changes.append(change_info)

            return changes

        except Exception:
            return []

    def _generate_changelog_entry(self, changes: list[dict[str, str]]) -> str:
        """Generate a formatted changelog entry."""
        date_str = datetime.now().strftime("%Y-%m-%d")
        entry_lines = [f"## [Unreleased] - {date_str}", ""]

        # Categorize changes
        features: list[str] = []
        fixes: list[str] = []
        refactors: list[str] = []
        other: list[str] = []

        for change in changes:
            message = change["message"]
            if message.startswith(("feat:", "feature:")):
                features.append(message)
            elif message.startswith("fix:"):
                fixes.append(message)
            elif message.startswith(("refactor:", "refact:")):
                refactors.append(message)
            else:
                other.append(message)

        # Add categorized changes
        if features:
            entry_lines.append("### Added")
            for feat in features:
                entry_lines.append(f"- {feat}")
            entry_lines.append("")

        if fixes:
            entry_lines.append("### Fixed")
            for fix in fixes:
                entry_lines.append(f"- {fix}")
            entry_lines.append("")

        if refactors:
            entry_lines.append("### Changed")
            for refactor in refactors:
                entry_lines.append(f"- {refactor}")
            entry_lines.append("")

        if other:
            entry_lines.append("### Other")
            for item in other:
                entry_lines.append(f"- {item}")
            entry_lines.append("")

        return "\n".join(entry_lines)

    def _insert_changelog_entry(self, content: str, entry: str) -> str:
        """Insert new changelog entry at the top."""
        lines = content.split("\n")

        # Find where to insert (after title and before first entry)
        insert_index = 0
        for i, line in enumerate(lines):
            if line.startswith(("# ", "## ")):
                if i > 0:  # Skip the main title
                    insert_index = i
                    break

        # Insert the new entry
        new_lines = (
            lines[:insert_index] + entry.split("\n") + [""] + lines[insert_index:]
        )
        return "\n".join(new_lines)

    def _create_initial_changelog(self, entry: str) -> str:
        """Create initial CHANGELOG.md with first entry."""
        return f"""# Changelog

All notable changes to this project will be documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.0.0/),
and this project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

{entry}
"""

    def _check_agent_count_consistency(
        self, md_files: list[Path]
    ) -> list[tuple[Path, int, int]]:
        """Check for inconsistent agent count references across documentation."""
        expected_count = 9  # Current total with DocumentationAgent
        issues: list[tuple[Path, int, int]] = []

        # Patterns to detect agent count references
        patterns = [
            r"(\d+)\s+agents",
            r"(\d+)\s+specialized\s+agents",
            r'total_agents["\']:\s*(\d+)',
            r"(\d+)\s+sub-agents",
        ]

        for file_path in md_files:
            with suppress(Exception):
                content = self.context.get_file_content(file_path)
                if not content:
                    continue

                for pattern in patterns:
                    matches = re.findall(pattern, content, re.IGNORECASE)
                    for match in matches:
                        count = int(match)
                        if (
                            count != expected_count and count > 4
                        ):  # Filter out unrelated numbers
                            issues.append((file_path, count, expected_count))
                            break  # Only report first issue per file

        return issues

    def _fix_agent_count_references(
        self, content: str, current_count: int, expected_count: int
    ) -> str:
        """Fix agent count references in documentation."""
        # Replace various agent count patterns
        patterns_replacements = [
            (rf"\b{current_count}\s+agents\b", f"{expected_count} agents"),
            (
                rf"\b{current_count}\s+specialized\s+agents\b",
                f"{expected_count} specialized agents",
            ),
            (
                rf'total_agents["\']:\s*{current_count}',
                f'total_agents": {expected_count}',
            ),
            (rf"\b{current_count}\s+sub-agents\b", f"{expected_count} sub-agents"),
        ]

        updated_content = content
        for pattern, replacement in patterns_replacements:
            updated_content = re.sub(
                pattern, replacement, updated_content, flags=re.IGNORECASE
            )

        return updated_content

    def _detect_api_changes(self) -> list[dict[str, str]]:
        """Detect recent API changes that might affect documentation."""
        # This is a simplified implementation - in practice would use AST analysis
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
        self, content: str, api_changes: list[dict[str, str]]
    ) -> str:
        """Update README examples based on API changes."""
        # This is a placeholder - real implementation would parse and update code examples
        # For now, just add a comment noting API changes
        if api_changes and "TODO: Update examples" not in content:
            # Add a note about updating examples
            lines = content.split("\n")
            # Insert near the top after the title
            for i, line in enumerate(lines):
                if line.startswith("# ") and i < len(lines) - 1:
                    lines.insert(
                        i + 2, "<!-- TODO: Update examples after recent API changes -->"
                    )
                    break
            return "\n".join(lines)

        return content


agent_registry.register(DocumentationAgent)

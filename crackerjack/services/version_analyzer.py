"""Intelligent version bump analysis based on code changes and commit patterns."""

import re
from dataclasses import dataclass
from enum import Enum
from pathlib import Path
from typing import Any

from .changelog_automation import ChangelogEntry, ChangelogGenerator
from .git import GitService


class VersionBumpType(Enum):
    """Semantic versioning bump types."""

    MAJOR = "major"  # Breaking changes (x.y.z -> x+1.0.0)
    MINOR = "minor"  # New features (x.y.z -> x.y+1.0)
    PATCH = "patch"  # Bug fixes (x.y.z -> x.y.z+1)


@dataclass
class VersionBumpRecommendation:
    """Recommendation for version bump with reasoning."""

    bump_type: VersionBumpType
    confidence: float  # 0.0 to 1.0
    reasoning: list[str]
    current_version: str
    recommended_version: str
    breaking_changes: list[str]
    new_features: list[str]
    bug_fixes: list[str]
    commit_analysis: dict[str, Any]


class BreakingChangeAnalyzer:
    """Analyzes commits for breaking changes that require MAJOR version bump."""

    def __init__(self) -> None:
        # Patterns that indicate breaking changes
        self.breaking_patterns = [
            re.compile(
                r"BREAKING\s*CHANGE[:\s]", re.IGNORECASE
            ),  # REGEX OK: breaking change detection
            re.compile(
                r"^[^:\n]*!:", re.MULTILINE
            ),  # REGEX OK: conventional commit breaking marker
            re.compile(
                r"\bremove\s+\w+\s+(api|function|method|class)", re.IGNORECASE
            ),  # REGEX OK: API removal detection
            re.compile(
                r"\bdelete\s+\w+\s+(api|endpoint|interface)", re.IGNORECASE
            ),  # REGEX OK: API deletion detection
            re.compile(
                r"\bchange\s+\w+\s+(signature|interface|api)", re.IGNORECASE
            ),  # REGEX OK: API signature change
        ]

    def analyze(self, entries: list[ChangelogEntry]) -> tuple[bool, list[str], float]:
        """
        Analyze changelog entries for breaking changes.

        Returns:
            (has_breaking_changes, breaking_change_descriptions, confidence)
        """
        breaking_changes: list[str] = []

        for entry in entries:
            # Check if entry is already marked as breaking
            if entry.breaking_change:
                breaking_changes.append(entry.description)
                continue

            # Check description against breaking change patterns
            for pattern in self.breaking_patterns:
                if pattern.search(entry.description):
                    breaking_changes.append(entry.description)
                    break

        has_breaking = len(breaking_changes) > 0
        confidence = 0.9 if has_breaking else 0.0

        return has_breaking, breaking_changes, confidence


class FeatureAnalyzer:
    """Analyzes commits for new features that require MINOR version bump."""

    def __init__(self) -> None:
        # Patterns that indicate new features
        self.feature_patterns = [
            re.compile(
                r"^feat[(\[]", re.IGNORECASE
            ),  # REGEX OK: conventional commit feat
            re.compile(
                r"\badd\s+(new\s+)?\w+", re.IGNORECASE
            ),  # REGEX OK: addition detection
            re.compile(
                r"\bimplement\s+\w+", re.IGNORECASE
            ),  # REGEX OK: implementation detection
            re.compile(
                r"\bintroduce\s+\w+", re.IGNORECASE
            ),  # REGEX OK: introduction detection
            re.compile(
                r"\bcreate\s+(new\s+)?\w+", re.IGNORECASE
            ),  # REGEX OK: creation detection
        ]

    def analyze(self, entries: list[ChangelogEntry]) -> tuple[bool, list[str], float]:
        """
        Analyze changelog entries for new features.

        Returns:
            (has_new_features, feature_descriptions, confidence)
        """
        new_features: list[str] = []

        for entry in entries:
            # Check entry type
            if entry.type in ("Added", "feat"):
                new_features.append(entry.description)
                continue

            # Check description against feature patterns
            for pattern in self.feature_patterns:
                if pattern.search(entry.description):
                    new_features.append(entry.description)
                    break

        has_features = len(new_features) > 0
        confidence = 0.8 if has_features else 0.0

        return has_features, new_features, confidence


class ConventionalCommitAnalyzer:
    """Analyzes conventional commit messages for semantic versioning hints."""

    def __init__(self) -> None:
        # Commit type mappings to version bump types
        self.commit_type_mappings = {
            # MAJOR bump triggers
            "breaking": VersionBumpType.MAJOR,
            # MINOR bump triggers
            "feat": VersionBumpType.MINOR,
            "feature": VersionBumpType.MINOR,
            # PATCH bump triggers
            "fix": VersionBumpType.PATCH,
            "bugfix": VersionBumpType.PATCH,
            "patch": VersionBumpType.PATCH,
            "hotfix": VersionBumpType.PATCH,
            # No version bump (could be argued either way)
            "docs": None,
            "style": None,
            "refactor": None,
            "test": None,
            "chore": None,
            "build": None,
            "ci": None,
        }

    def analyze(self, entries: list[ChangelogEntry]) -> dict[str, Any]:
        """
        Analyze conventional commit patterns in changelog entries.

        Returns:
            Analysis results including type counts and recommendations
        """
        type_counts: dict[str, int] = {}
        recommended_bumps: list[VersionBumpType] = []

        for entry in entries:
            # Parse entry type and increment count
            entry_type = entry.type.lower()
            type_counts[entry_type] = type_counts.get(entry_type, 0) + 1

            # Determine recommended bump type
            if entry.breaking_change:
                recommended_bumps.append(VersionBumpType.MAJOR)
            elif entry_type in self.commit_type_mappings:
                bump_type = self.commit_type_mappings[entry_type]
                if bump_type:
                    recommended_bumps.append(bump_type)

        return {
            "type_counts": type_counts,
            "recommended_bumps": recommended_bumps,
            "total_entries": len(entries),
        }


class VersionAnalyzer:
    """Main service for analyzing changes and recommending version bumps."""

    def __init__(self, git_service: GitService) -> None:
        self.console = console
        self.git = git_service

        # Initialize specialized analyzers
        self.breaking_analyzer = BreakingChangeAnalyzer()
        self.feature_analyzer = FeatureAnalyzer()
        self.commit_analyzer = ConventionalCommitAnalyzer()

        # Initialize changelog generator for getting entries (ACB DI injects dependencies)
        self.changelog_generator = ChangelogGenerator()

    def _get_current_version(self) -> str | None:
        """Get current version from pyproject.toml."""
        pyproject_path = Path("pyproject.toml")
        if not pyproject_path.exists():
            return None

        try:
            from tomllib import loads

            content = pyproject_path.read_text(encoding="utf-8")
            data = loads(content)
            version: str | None = data.get("project", {}).get("version")
            return version
        except Exception:
            return None

    def _calculate_next_version(self, current: str, bump_type: VersionBumpType) -> str:
        """Calculate next version based on current version and bump type."""
        try:
            parts = current.split(".")
            if len(parts) != 3:
                msg = f"Invalid version format: {current}"
                raise ValueError(msg)

            major, minor, patch = map(int, parts)

            if bump_type == VersionBumpType.MAJOR:
                return f"{major + 1}.0.0"
            elif bump_type == VersionBumpType.MINOR:
                return f"{major}.{minor + 1}.0"
            elif bump_type == VersionBumpType.PATCH:
                return f"{major}.{minor}.{patch + 1}"
            else:
                # All enum cases are covered above
                from typing import assert_never

                assert_never(bump_type)

        except Exception as e:
            self.console.print(f"[red]❌[/red] Error calculating version: {e}")
            raise

    async def recommend_version_bump(
        self, since_version: str | None = None
    ) -> VersionBumpRecommendation:
        """
        Analyze changes since last version and recommend version bump.

        Args:
            since_version: Version/tag to analyze changes since (default: latest tag)

        Returns:
            VersionBumpRecommendation with analysis and recommendation
        """
        current_version = self._get_current_version()
        if not current_version:
            msg = "Could not determine current version from pyproject.toml"
            raise ValueError(msg)

        all_entries = self._collect_changelog_entries(since_version)

        if not all_entries:
            return self._create_no_changes_recommendation(current_version)

        return self._analyze_entries_and_recommend(current_version, all_entries)

    def _collect_changelog_entries(
        self, since_version: str | None
    ) -> list[ChangelogEntry]:
        """Collect and flatten changelog entries for analysis."""
        entries_by_type = self.changelog_generator.generate_changelog_entries(
            since_version
        )
        all_entries: list[ChangelogEntry] = []
        for entries in entries_by_type.values():
            all_entries.extend(entries)
        return all_entries

    def _create_no_changes_recommendation(
        self, current_version: str
    ) -> VersionBumpRecommendation:
        """Create recommendation when no changes are detected."""
        return VersionBumpRecommendation(
            bump_type=VersionBumpType.PATCH,
            confidence=1.0,
            reasoning=["No significant changes detected - patch bump recommended"],
            current_version=current_version,
            recommended_version=self._calculate_next_version(
                current_version, VersionBumpType.PATCH
            ),
            breaking_changes=[],
            new_features=[],
            bug_fixes=[],
            commit_analysis={
                "type_counts": {},
                "recommended_bumps": [],
                "total_entries": 0,
            },
        )

    def _analyze_entries_and_recommend(
        self, current_version: str, all_entries: list[ChangelogEntry]
    ) -> VersionBumpRecommendation:
        """Analyze entries and create version bump recommendation."""
        # Run specialized analyses
        has_breaking, breaking_changes, breaking_confidence = (
            self.breaking_analyzer.analyze(all_entries)
        )
        has_features, new_features, feature_confidence = self.feature_analyzer.analyze(
            all_entries
        )
        commit_analysis = self.commit_analyzer.analyze(all_entries)

        bug_fixes = [
            entry.description
            for entry in all_entries
            if entry.type.lower() in ("fixed", "fix", "bugfix", "patch")
        ]

        bump_type, confidence, reasoning = self._determine_bump_type(
            has_breaking,
            breaking_changes,
            breaking_confidence,
            has_features,
            new_features,
            feature_confidence,
            bug_fixes,
            all_entries,
        )

        recommended_version = self._calculate_next_version(current_version, bump_type)

        return VersionBumpRecommendation(
            bump_type=bump_type,
            confidence=confidence,
            reasoning=reasoning,
            current_version=current_version,
            recommended_version=recommended_version,
            breaking_changes=breaking_changes,
            new_features=new_features,
            bug_fixes=bug_fixes,
            commit_analysis=commit_analysis,
        )

    def _determine_bump_type(
        self,
        has_breaking: bool,
        breaking_changes: list[str],
        breaking_confidence: float,
        has_features: bool,
        new_features: list[str],
        feature_confidence: float,
        bug_fixes: list[str],
        all_entries: list[ChangelogEntry],
    ) -> tuple[VersionBumpType, float, list[str]]:
        """Determine the appropriate version bump type and reasoning."""
        if has_breaking:
            return (
                VersionBumpType.MAJOR,
                breaking_confidence,
                [
                    f"Breaking changes detected ({len(breaking_changes)} found)",
                    "MAJOR version bump required to maintain semantic versioning",
                ],
            )
        elif has_features:
            return (
                VersionBumpType.MINOR,
                feature_confidence,
                [
                    f"New features detected ({len(new_features)} found)",
                    "MINOR version bump recommended for backward-compatible functionality",
                ],
            )
        elif bug_fixes:
            return (
                VersionBumpType.PATCH,
                0.9,
                [
                    f"Bug fixes detected ({len(bug_fixes)} found)",
                    "PATCH version bump recommended for backward-compatible fixes",
                ],
            )
        return (
            VersionBumpType.PATCH,
            0.5,
            [
                f"Changes detected ({len(all_entries)} commits) with unclear impact",
                "PATCH version bump recommended as conservative choice",
            ],
        )

    def display_recommendation(self, recommendation: VersionBumpRecommendation) -> None:
        """Display version bump recommendation in a user-friendly format."""
        self._display_summary(recommendation)
        self._display_reasoning(recommendation)
        self._display_changes(recommendation)
        self._display_commit_analysis(recommendation)

    def _display_summary(self, recommendation: VersionBumpRecommendation) -> None:
        """Display the main version bump summary."""
        self.console.print("\n[cyan]📊 Version Bump Analysis[/cyan]")
        self.console.print(
            f"Current version: [bold]{recommendation.current_version}[/bold]"
        )
        self.console.print(
            f"Recommended version: [bold green]{recommendation.recommended_version}[/bold green]"
        )
        self.console.print(
            f"Bump type: [bold]{recommendation.bump_type.value.upper()}[/bold]"
        )
        self.console.print(f"Confidence: [bold]{recommendation.confidence:.0%}[/bold]")

    def _display_reasoning(self, recommendation: VersionBumpRecommendation) -> None:
        """Display the reasoning behind the recommendation."""
        self.console.print("\n[yellow]💡 Reasoning:[/yellow]")
        for reason in recommendation.reasoning:
            self.console.print(f"  • {reason}")

    def _display_changes(self, recommendation: VersionBumpRecommendation) -> None:
        """Display breaking changes, new features, and bug fixes."""
        self._display_change_list(
            recommendation.breaking_changes, "[red]⚠️  Breaking Changes", "red"
        )
        self._display_change_list(
            recommendation.new_features, "[green]✨ New Features", "green"
        )
        self._display_change_list(
            recommendation.bug_fixes, "[blue]🔧 Bug Fixes", "blue"
        )

    def _display_change_list(self, changes: list[str], title: str, color: str) -> None:
        """Display a list[t.Any] of changes with truncation."""
        if changes:
            self.console.print(f"\n{title} ({len(changes)}):[/{color}]")
            for change in changes[:3]:
                self.console.print(f"  • {change}")
            if len(changes) > 3:
                self.console.print(f"  • ... and {len(changes) - 3} more")

    def _display_commit_analysis(
        self, recommendation: VersionBumpRecommendation
    ) -> None:
        """Display commit analysis summary."""
        analysis = recommendation.commit_analysis
        if analysis.get("type_counts"):
            self.console.print("\n[dim]📈 Commit Analysis:[/dim]")
            total = analysis["total_entries"]
            for commit_type, count in sorted(analysis["type_counts"].items()):
                percentage = (count / total * 100) if total > 0 else 0
                self.console.print(f"  {commit_type}: {count} ({percentage:.0f}%)")

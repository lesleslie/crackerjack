"""Intelligent version bump analysis based on code changes and commit patterns."""

import re
from dataclasses import dataclass
from enum import Enum
from pathlib import Path
from typing import Any

from rich.console import Console

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
            if entry.type in ["Added", "feat"]:
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

    def __init__(self, console: Console, git_service: GitService) -> None:
        self.console = console
        self.git = git_service

        # Initialize specialized analyzers
        self.breaking_analyzer = BreakingChangeAnalyzer()
        self.feature_analyzer = FeatureAnalyzer()
        self.commit_analyzer = ConventionalCommitAnalyzer()

        # Initialize changelog generator for getting entries
        self.changelog_generator = ChangelogGenerator(console, git_service)

    def _get_current_version(self) -> str | None:
        """Get current version from pyproject.toml."""
        pyproject_path = Path("pyproject.toml")
        if not pyproject_path.exists():
            return None

        try:
            from tomllib import loads

            content = pyproject_path.read_text(encoding="utf-8")
            data = loads(content)
            return data.get("project", {}).get("version")
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
                msg = f"Invalid bump type: {bump_type}"
                raise ValueError(msg)

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

        # Generate changelog entries for analysis
        entries_by_type = self.changelog_generator.generate_changelog_entries(
            since_version
        )

        # Flatten all entries for analysis
        all_entries: list[ChangelogEntry] = []
        for entries in entries_by_type.values():
            all_entries.extend(entries)

        if not all_entries:
            # No changes - recommend patch version for consistency
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

        # Run specialized analyses
        has_breaking, breaking_changes, breaking_confidence = (
            self.breaking_analyzer.analyze(all_entries)
        )
        has_features, new_features, feature_confidence = self.feature_analyzer.analyze(
            all_entries
        )
        commit_analysis = self.commit_analyzer.analyze(all_entries)

        # Extract bug fixes
        bug_fixes = [
            entry.description
            for entry in all_entries
            if entry.type.lower() in ["fixed", "fix", "bugfix", "patch"]
        ]

        # Determine final recommendation
        if has_breaking:
            bump_type = VersionBumpType.MAJOR
            confidence = breaking_confidence
            reasoning = [
                f"Breaking changes detected ({len(breaking_changes)} found)",
                "MAJOR version bump required to maintain semantic versioning",
            ]
        elif has_features:
            bump_type = VersionBumpType.MINOR
            confidence = feature_confidence
            reasoning = [
                f"New features detected ({len(new_features)} found)",
                "MINOR version bump recommended for backward-compatible functionality",
            ]
        elif bug_fixes:
            bump_type = VersionBumpType.PATCH
            confidence = 0.9
            reasoning = [
                f"Bug fixes detected ({len(bug_fixes)} found)",
                "PATCH version bump recommended for backward-compatible fixes",
            ]
        else:
            bump_type = VersionBumpType.PATCH
            confidence = 0.5
            reasoning = [
                f"Changes detected ({len(all_entries)} commits) with unclear impact",
                "PATCH version bump recommended as conservative choice",
            ]

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

    def display_recommendation(self, recommendation: VersionBumpRecommendation) -> None:
        """Display version bump recommendation in a user-friendly format."""
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

        self.console.print("\n[yellow]💡 Reasoning:[/yellow]")
        for reason in recommendation.reasoning:
            self.console.print(f"  • {reason}")

        if recommendation.breaking_changes:
            self.console.print(
                f"\n[red]⚠️  Breaking Changes ({len(recommendation.breaking_changes)}):[/red]"
            )
            for change in recommendation.breaking_changes[:3]:
                self.console.print(f"  • {change}")
            if len(recommendation.breaking_changes) > 3:
                self.console.print(
                    f"  • ... and {len(recommendation.breaking_changes) - 3} more"
                )

        if recommendation.new_features:
            self.console.print(
                f"\n[green]✨ New Features ({len(recommendation.new_features)}):[/green]"
            )
            for feature in recommendation.new_features[:3]:
                self.console.print(f"  • {feature}")
            if len(recommendation.new_features) > 3:
                self.console.print(
                    f"  • ... and {len(recommendation.new_features) - 3} more"
                )

        if recommendation.bug_fixes:
            self.console.print(
                f"\n[blue]🔧 Bug Fixes ({len(recommendation.bug_fixes)}):[/blue]"
            )
            for fix in recommendation.bug_fixes[:3]:
                self.console.print(f"  • {fix}")
            if len(recommendation.bug_fixes) > 3:
                self.console.print(
                    f"  • ... and {len(recommendation.bug_fixes) - 3} more"
                )

        # Display commit analysis summary
        analysis = recommendation.commit_analysis
        if analysis.get("type_counts"):
            self.console.print("\n[dim]📈 Commit Analysis:[/dim]")
            total = analysis["total_entries"]
            for commit_type, count in sorted(analysis["type_counts"].items()):
                percentage = (count / total * 100) if total > 0 else 0
                self.console.print(f"  {commit_type}: {count} ({percentage:.0f}%)")

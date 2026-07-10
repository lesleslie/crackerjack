from __future__ import annotations

import re
from dataclasses import dataclass
from enum import Enum
from pathlib import Path
from typing import Any

from rich.console import Console

from .changelog_automation import ChangelogEntry, ChangelogGenerator
from .git import GitService


class VersionBumpType(Enum):
    MAJOR = "major"
    MINOR = "minor"
    PATCH = "patch"


@dataclass
class VersionBumpRecommendation:
    bump_type: VersionBumpType
    confidence: float
    reasoning: list[str]
    current_version: str
    recommended_version: str
    breaking_changes: list[str]
    new_features: list[str]
    bug_fixes: list[str]
    commit_analysis: dict[str, Any]


class BreakingChangeAnalyzer:
    def __init__(self) -> None:
        self.breaking_patterns = [
            re.compile(
                r"BREAKING\s*CHANGE[:\s]",
                re.IGNORECASE,
            ),  # REGEX OK: breaking change detection
            re.compile(
                r"^[^:\n]*!:",
                re.MULTILINE,
            ),  # REGEX OK: conventional commit breaking marker
            re.compile(
                r"\bremove\s+\w+\s+(api|function|method|class)",
                re.IGNORECASE,
            ),  # REGEX OK: API removal detection
            re.compile(
                r"\bdelete\s+\w+\s+(api|endpoint|interface)",
                re.IGNORECASE,
            ),  # REGEX OK: API deletion detection
            re.compile(
                r"\bchange\s+\w+\s+(signature|interface|api)",
                re.IGNORECASE,
            ),  # REGEX OK: API signature change
        ]

    def analyze(self, entries: list[ChangelogEntry]) -> tuple[bool, list[str], float]:
        breaking_changes: list[str] = []

        for entry in entries:
            if entry.breaking_change:
                breaking_changes.append(entry.description)
                continue

            for pattern in self.breaking_patterns:
                if pattern.search(entry.description):
                    breaking_changes.append(entry.description)
                    break

        has_breaking = bool(breaking_changes)
        confidence = 0.9 if has_breaking else 0.0

        return has_breaking, breaking_changes, confidence


class FeatureAnalyzer:
    def __init__(self) -> None:
        self.feature_patterns = [
            re.compile(
                r"^feat[(\[]",
                re.IGNORECASE,
            ),  # REGEX OK: conventional commit feat
            re.compile(
                r"\badd\s+(new\s+)?\w+",
                re.IGNORECASE,
            ),  # REGEX OK: addition detection
            re.compile(
                r"\bimplement\s+\w+",
                re.IGNORECASE,
            ),  # REGEX OK: implementation detection
            re.compile(
                r"\bintroduce\s+\w+",
                re.IGNORECASE,
            ),  # REGEX OK: introduction detection
            re.compile(
                r"\bcreate\s+(new\s+)?\w+",
                re.IGNORECASE,
            ),  # REGEX OK: creation detection
        ]

    def analyze(
        self, entries: list[ChangelogEntry]
    ) -> tuple[bool, list[str], list[str], float]:
        confident_features: list[str] = []
        heuristic_features: list[str] = []

        for entry in entries:
            if entry.type == "feat":
                confident_features.append(entry.description)
            elif entry.type == "Added":
                heuristic_features.append(entry.description)
            else:
                for pattern in self.feature_patterns:
                    if pattern.search(entry.description):
                        heuristic_features.append(entry.description)
                        break

        has_features = bool(confident_features) or bool(heuristic_features)
        if confident_features:
            confidence = 0.9
        elif heuristic_features:
            confidence = 0.4
        else:
            confidence = 0.0

        return has_features, confident_features, heuristic_features, confidence


class ConventionalCommitAnalyzer:
    def __init__(self) -> None:
        self.commit_type_mappings = {
            "breaking": VersionBumpType.MAJOR,
            "feat": VersionBumpType.MINOR,
            "feature": VersionBumpType.MINOR,
            "fix": VersionBumpType.PATCH,
            "bugfix": VersionBumpType.PATCH,
            "patch": VersionBumpType.PATCH,
            "hotfix": VersionBumpType.PATCH,
            "docs": None,
            "style": None,
            "refactor": None,
            "test": None,
            "chore": None,
            "build": None,
            "ci": None,
        }

    def analyze(self, entries: list[ChangelogEntry]) -> dict[str, Any]:
        type_counts: dict[str, int] = {}
        recommended_bumps: list[VersionBumpType] = []

        for entry in entries:
            entry_type = entry.type.lower()
            type_counts[entry_type] = type_counts.get(entry_type, 0) + 1

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
    def __init__(
        self,
        git_service: GitService,
        console: Console | None = None,
    ) -> None:
        self.console = console or Console()
        self.git = git_service

        self.breaking_analyzer = BreakingChangeAnalyzer()
        self.feature_analyzer = FeatureAnalyzer()
        self.commit_analyzer = ConventionalCommitAnalyzer()

        self.changelog_generator = ChangelogGenerator(
            console=self.console,
            git_service=self.git,
        )

    def _get_current_version(self) -> str | None:
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
        try:
            parts = current.split(".")
            if len(parts) != 3:
                msg = f"Invalid version format: {current}"
                raise ValueError(msg)

            major, minor, patch = map(int, parts)

            if bump_type == VersionBumpType.MAJOR:
                return f"{major + 1}.0.0"
            if bump_type == VersionBumpType.MINOR:
                return f"{major}.{minor + 1}.0"
            if bump_type == VersionBumpType.PATCH:
                return f"{major}.{minor}.{patch + 1}"
            from typing import assert_never

            assert_never(bump_type)

        except Exception as e:
            self.console.print(f"[red]❌[/red] Error calculating version: {e}")
            raise

    async def recommend_version_bump(
        self,
        since_version: str | None = None,
    ) -> VersionBumpRecommendation:
        current_version = self._get_current_version()
        if not current_version:
            msg = "Could not determine current version from pyproject.toml"
            raise ValueError(msg)

        all_entries = self._collect_changelog_entries(since_version)

        if not all_entries:
            return self._create_no_changes_recommendation(current_version)

        return self._analyze_entries_and_recommend(current_version, all_entries)

    def _collect_changelog_entries(
        self,
        since_version: str | None,
    ) -> list[ChangelogEntry]:
        entries_by_type = self.changelog_generator.generate_changelog_entries(
            since_version,
        )
        all_entries: list[ChangelogEntry] = []
        for entries in entries_by_type.values():
            all_entries.extend(entries)
        return all_entries

    def _create_no_changes_recommendation(
        self,
        current_version: str,
    ) -> VersionBumpRecommendation:
        return VersionBumpRecommendation(
            bump_type=VersionBumpType.PATCH,
            confidence=1.0,
            reasoning=["No significant changes detected - patch bump recommended"],
            current_version=current_version,
            recommended_version=self._calculate_next_version(
                current_version,
                VersionBumpType.PATCH,
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
        self,
        current_version: str,
        all_entries: list[ChangelogEntry],
    ) -> VersionBumpRecommendation:
        has_breaking, breaking_changes, breaking_confidence = (
            self.breaking_analyzer.analyze(all_entries)
        )
        has_features, confident_features, heuristic_features, feature_confidence = (
            self.feature_analyzer.analyze(all_entries)
        )
        new_features = confident_features + heuristic_features
        commit_analysis = self.commit_analyzer.analyze(all_entries)

        bug_fixes = [
            entry.description
            for entry in all_entries
            if entry.type.lower() in ("fixed", "fix", "bugfix", "patch")
        ]

        bump_type, confidence, reasoning = self._determine_bump_type(
            has_breaking=has_breaking,
            breaking_changes=breaking_changes,
            breaking_confidence=breaking_confidence,
            has_features=has_features,
            new_features=new_features,
            feature_confidence=feature_confidence,
            bug_fixes=bug_fixes,
            all_entries=all_entries,
            confident_features=confident_features,
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
        confident_features: list[str] | None = None,
    ) -> tuple[VersionBumpType, float, list[str]]:
        # TODO: wire LLM analysis via DocstringEnricher-style MiniMax call here
        if has_breaking:
            return (
                VersionBumpType.MAJOR,
                breaking_confidence,
                [
                    f"Breaking changes detected ({len(breaking_changes)} found)",
                    "MAJOR version bump required to maintain semantic versioning",
                ],
            )

        if has_features:
            effective_confidence = feature_confidence

            if bug_fixes and not confident_features and feature_confidence < 0.7:
                effective_confidence = feature_confidence * 0.5

            if effective_confidence >= 0.7:
                return (
                    VersionBumpType.MINOR,
                    effective_confidence,
                    [
                        f"New features detected ({len(new_features)} found)",
                        "MINOR version bump recommended for backward-compatible functionality",
                    ],
                )

            return (
                VersionBumpType.PATCH,
                0.9 if bug_fixes else 0.6,
                [
                    f"Bug fixes detected ({len(bug_fixes)} found)"
                    if bug_fixes
                    else f"Changes detected ({len(all_entries)} commits) with unclear impact",
                    "PATCH version bump recommended (feature detections are heuristic-only)",
                ],
            )

        if bug_fixes:
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
        self._display_summary(recommendation)
        self._display_reasoning(recommendation)
        self._display_changes(recommendation)
        self._display_commit_analysis(recommendation)

    def _display_summary(self, recommendation: VersionBumpRecommendation) -> None:
        self.console.print("\n[cyan]📊 Version Bump Analysis[/cyan]")
        self.console.print(
            f"Current version: [bold]{recommendation.current_version}[/bold]",
        )
        self.console.print(
            f"Recommended version: [bold green]{recommendation.recommended_version}[/bold green]",
        )
        self.console.print(
            f"Bump type: [bold]{recommendation.bump_type.value.upper()}[/bold]",
        )
        self.console.print(f"Confidence: [bold]{recommendation.confidence:.0%}[/bold]")

    def _display_reasoning(self, recommendation: VersionBumpRecommendation) -> None:
        self.console.print("\n[yellow]💡 Reasoning:[/yellow]")
        for reason in recommendation.reasoning:
            self.console.print(f" • {reason}")

    def _display_changes(self, recommendation: VersionBumpRecommendation) -> None:
        self._display_change_list(
            recommendation.breaking_changes,
            "[red]⚠️ Breaking Changes",
            "red",
        )
        self._display_change_list(
            recommendation.new_features,
            "[green]✨ New Features",
            "green",
        )
        self._display_change_list(
            recommendation.bug_fixes,
            "[blue]🔧 Bug Fixes",
            "blue",
        )

    def _display_change_list(self, changes: list[str], title: str, color: str) -> None:
        if changes:
            self.console.print(f"\n{title} ({len(changes)}):[/{color}]")
            for change in changes[:3]:
                self.console.print(f" • {change}")
            if len(changes) > 3:
                self.console.print(f" • ... and {len(changes) - 3} more")

    def _display_commit_analysis(
        self,
        recommendation: VersionBumpRecommendation,
    ) -> None:
        analysis = recommendation.commit_analysis
        if analysis.get("type_counts"):
            self.console.print("\n[dim]📈 Commit Analysis:[/dim]")
            total = analysis["total_entries"]
            for commit_type, count in sorted(analysis["type_counts"].items()):
                percentage = (count / total * 100) if total > 0 else 0
                self.console.print(f" {commit_type}: {count} ({percentage:.0f}%)")

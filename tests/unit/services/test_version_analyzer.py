from __future__ import annotations

import pytest

from crackerjack.services.changelog_automation import ChangelogEntry, ChangelogGenerator
from crackerjack.services.version_analyzer import (
    FeatureAnalyzer,
    VersionBumpType,
)


def _make_entry(entry_type: str, description: str) -> ChangelogEntry:
    return ChangelogEntry(entry_type=entry_type, description=description)


def _make_generator() -> ChangelogGenerator:
    from unittest.mock import MagicMock

    return ChangelogGenerator(git_service=MagicMock())


@pytest.mark.unit
class TestKeywordClassificationPriority:
    """Keyword priority fix: fix-intent keywords must outrank add/new/create."""

    def test_add_test_commit_classifies_as_fixed_not_added(self) -> None:
        gen = _make_generator()
        entry = gen._parse_non_conventional_commit(
            "Add unit test for login bug", "", ""
        )
        assert entry is not None
        assert entry.type == "Fixed", (
            f"'Add unit test for login bug' should be Fixed, got {entry.type!r}"
        )

    def test_add_error_handling_commit_classifies_as_fixed(self) -> None:
        gen = _make_generator()
        entry = gen._parse_non_conventional_commit(
            "Add error handling to fix crash", "", ""
        )
        assert entry is not None
        assert entry.type == "Fixed"

    def test_add_regression_test_classifies_as_fixed(self) -> None:
        gen = _make_generator()
        entry = gen._parse_non_conventional_commit(
            "Add regression test for issue #42", "", ""
        )
        assert entry is not None
        assert entry.type == "Fixed"

    def test_add_new_endpoint_classifies_as_added(self) -> None:
        """No veto words → should remain Added."""
        gen = _make_generator()
        entry = gen._parse_non_conventional_commit(
            "Add /users endpoint to REST API", "", ""
        )
        assert entry is not None
        assert entry.type == "Added"

    def test_add_validation_guard_remains_added(self) -> None:
        """m-new-3: 'validation' and 'guard' are NOT veto words — genuine feature words."""
        gen = _make_generator()
        entry = gen._parse_non_conventional_commit(
            "Add validation guard for empty input", "", ""
        )
        assert entry is not None
        assert entry.type == "Added"

    def test_add_boundary_check_classifies_as_fixed(self) -> None:
        gen = _make_generator()
        entry = gen._parse_non_conventional_commit(
            "Add boundary check to prevent crash", "", ""
        )
        assert entry is not None
        assert entry.type == "Fixed"

    def test_fix_keyword_takes_priority_over_add(self) -> None:
        """Pure fix keyword: should always be Fixed."""
        gen = _make_generator()
        entry = gen._parse_non_conventional_commit(
            "Fix login bug by adding null check", "", ""
        )
        assert entry is not None
        assert entry.type == "Fixed"


@pytest.mark.unit
class TestFeatureAnalyzerConfidenceSplit:
    """FeatureAnalyzer must distinguish conventional feat: from heuristic Added."""

    def test_feat_conventional_commit_is_high_confidence_feature(self) -> None:
        analyzer = FeatureAnalyzer()
        entries = [
            ChangelogEntry(
                entry_type="feat",
                description="Add user dashboard with analytics",
            )
        ]
        result = analyzer.analyze(entries)
        # New return: (has_features, confident_features, heuristic_features, confidence)
        assert len(result) == 4, (
            f"analyze() must return 4-tuple, got {len(result)}-tuple"
        )
        has_features, confident_features, heuristic_features, confidence = result
        assert has_features is True
        assert len(confident_features) == 1
        assert confidence >= 0.7

    def test_heuristic_added_only_is_low_confidence_feature(self) -> None:
        analyzer = FeatureAnalyzer()
        entries = [
            ChangelogEntry(entry_type="Added", description=f"Add component {i}")
            for i in range(6)
        ]
        result = analyzer.analyze(entries)
        assert len(result) == 4
        has_features, confident_features, heuristic_features, confidence = result
        assert has_features is True
        assert len(confident_features) == 0  # no conventional feat: commits
        assert len(heuristic_features) == 6
        assert confidence < 0.7

    def test_mixed_conventional_and_heuristic_sources_high_confidence(self) -> None:
        analyzer = FeatureAnalyzer()
        entries = [
            ChangelogEntry(entry_type="feat", description="Introduce plugin system"),
            ChangelogEntry(entry_type="Added", description="Add helper utility"),
        ]
        _, confident_features, heuristic_features, confidence = analyzer.analyze(entries)
        assert len(confident_features) == 1
        assert len(heuristic_features) == 1
        assert confidence >= 0.7  # confident features dominate

    def test_no_features_returns_zero_confidence(self) -> None:
        analyzer = FeatureAnalyzer()
        entries = [
            ChangelogEntry(entry_type="Fixed", description="Fix null pointer exception"),
        ]
        has_features, confident_features, heuristic_features, confidence = (
            analyzer.analyze(entries)
        )
        assert has_features is False
        assert confident_features == []
        assert heuristic_features == []
        assert confidence == 0.0


@pytest.mark.unit
class TestBumpTypeDecisions:
    """_determine_bump_type cross-validation and bump decisions."""

    def test_bug_fixes_with_heuristic_adds_yields_patch_not_minor(self) -> None:
        """3 fix commits + 4 'Add test' commits → PATCH, not MINOR."""
        from crackerjack.services.version_analyzer import VersionAnalyzer
        from unittest.mock import MagicMock

        git_svc = MagicMock()
        analyzer = VersionAnalyzer(git_service=git_svc)

        # Simulate 4 heuristic-only "Added" entries + 3 fix entries
        heuristic_features = [f"Add test for bug {i}" for i in range(4)]
        bug_fixes = [f"Fix crash scenario {i}" for i in range(3)]
        all_entries = [
            ChangelogEntry(entry_type="Added", description=desc)
            for desc in heuristic_features
        ] + [
            ChangelogEntry(entry_type="Fixed", description=desc)
            for desc in bug_fixes
        ]

        # With the new logic: heuristic-only + bug_fixes present → confidence halved
        # feature_confidence for heuristic-only = 0.4, halved = 0.2 < 0.7 → PATCH
        bump_type, confidence, reasoning = analyzer._determine_bump_type(
            has_breaking=False,
            breaking_changes=[],
            breaking_confidence=0.0,
            has_features=True,
            new_features=heuristic_features,
            feature_confidence=0.4,  # heuristic-only confidence
            bug_fixes=bug_fixes,
            all_entries=all_entries,
            confident_features=[],
        )
        assert bump_type == VersionBumpType.PATCH, (
            f"Heuristic-only features + bug fixes should be PATCH, got {bump_type}"
        )

    def test_true_feat_commits_yield_minor_bump(self) -> None:
        from crackerjack.services.version_analyzer import VersionAnalyzer
        from unittest.mock import MagicMock

        git_svc = MagicMock()
        analyzer = VersionAnalyzer(git_service=git_svc)

        bump_type, confidence, reasoning = analyzer._determine_bump_type(
            has_breaking=False,
            breaking_changes=[],
            breaking_confidence=0.0,
            has_features=True,
            new_features=["Introduce plugin system"],
            feature_confidence=0.9,  # conventional feat: commit
            bug_fixes=[],
            all_entries=[],
            confident_features=["Introduce plugin system"],
        )
        assert bump_type == VersionBumpType.MINOR

    def test_cross_validation_halves_heuristic_confidence_when_bugfixes_present(
        self,
    ) -> None:
        from crackerjack.services.version_analyzer import VersionAnalyzer
        from unittest.mock import MagicMock

        git_svc = MagicMock()
        analyzer = VersionAnalyzer(git_service=git_svc)

        # heuristic confidence 0.4, bug_fixes present, no conventional features
        bump_type, confidence, _ = analyzer._determine_bump_type(
            has_breaking=False,
            breaking_changes=[],
            breaking_confidence=0.0,
            has_features=True,
            new_features=["Add test"],
            feature_confidence=0.4,
            bug_fixes=["Fix crash"],
            all_entries=[],
            confident_features=[],  # no conventional feat: commits
        )
        # 0.4 * 0.5 = 0.2 < 0.7 → PATCH
        assert bump_type == VersionBumpType.PATCH

    def test_breaking_change_always_yields_major_regardless_of_features(
        self,
    ) -> None:
        from crackerjack.services.version_analyzer import VersionAnalyzer
        from unittest.mock import MagicMock

        git_svc = MagicMock()
        analyzer = VersionAnalyzer(git_service=git_svc)

        bump_type, _, _ = analyzer._determine_bump_type(
            has_breaking=True,
            breaking_changes=["Redesign API"],
            breaking_confidence=0.9,
            has_features=True,
            new_features=["Add feature"],
            feature_confidence=0.9,
            bug_fixes=[],
            all_entries=[],
            confident_features=["Add feature"],
        )
        assert bump_type == VersionBumpType.MAJOR

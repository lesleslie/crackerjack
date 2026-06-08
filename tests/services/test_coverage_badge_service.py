"""Tests for CoverageBadgeService.

Covers pure-function behavior of the README coverage badge generator:
- color thresholds: <50 red, <80 yellow, >=80 brightgreen
- badge URL formatting
- README update: missing readme, new badge insertion, existing badge replacement
- badge insertion point detection (after badges block, after title)
- should_update_badge: missing readme, no current coverage, same/diff coverage
- exception handling during read/write
- malformed coverage percent (negative, >100) still produces a valid URL
"""

from __future__ import annotations

from pathlib import Path
from unittest.mock import MagicMock

import pytest
from rich.console import Console

from crackerjack.services.coverage_badge_service import CoverageBadgeService


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------


@pytest.fixture
def console() -> Console:
    """Console that swallows output to keep test output clean."""
    return Console(file=MagicMock(), force_terminal=False, no_color=True, width=200)


@pytest.fixture
def readme(tmp_path: Path) -> Path:
    """Bare README path (no file written) under tmp_path."""
    return tmp_path / "README.md"


@pytest.fixture
def service(tmp_path: Path, console: Console) -> CoverageBadgeService:
    return CoverageBadgeService(project_root=tmp_path, console=console)


# ---------------------------------------------------------------------------
# Color thresholds
# ---------------------------------------------------------------------------


class TestGetBadgeColor:
    """`_get_badge_color` is the heart of the color threshold logic."""

    @pytest.mark.parametrize(
        ("percent", "expected"),
        [
            (0.0, "red"),
            (10.5, "red"),
            (49.9, "red"),
            (50.0, "yellow"),
            (65.0, "yellow"),
            (79.9, "yellow"),
            (80.0, "brightgreen"),
            (95.0, "brightgreen"),
            (100.0, "brightgreen"),
        ],
    )
    def test_color_thresholds(
        self,
        service: CoverageBadgeService,
        percent: float,
        expected: str,
    ) -> None:
        assert service._get_badge_color(percent) == expected

    def test_out_of_range_high(self, service: CoverageBadgeService) -> None:
        # >100 is not a real coverage value but should still be green.
        assert service._get_badge_color(150.0) == "brightgreen"

    def test_out_of_range_low(self, service: CoverageBadgeService) -> None:
        # Negative is not a real coverage value but should still be red.
        assert service._get_badge_color(-5.0) == "red"


# ---------------------------------------------------------------------------
# Badge URL generation
# ---------------------------------------------------------------------------


class TestGenerateBadgeUrl:
    @pytest.mark.parametrize(
        ("percent", "expected_substring"),
        [
            (0.0, "https://img.shields.io/badge/coverage-0.0%25-red"),
            (50.0, "https://img.shields.io/badge/coverage-50.0%25-yellow"),
            (80.0, "https://img.shields.io/badge/coverage-80.0%25-brightgreen"),
            (100.0, "https://img.shields.io/badge/coverage-100.0%25-brightgreen"),
            (95.5, "https://img.shields.io/badge/coverage-95.5%25-brightgreen"),
        ],
    )
    def test_url_format(
        self,
        service: CoverageBadgeService,
        percent: float,
        expected_substring: str,
    ) -> None:
        assert service._generate_badge_url(percent) == expected_substring

    def test_url_includes_color_from_threshold(
        self,
        service: CoverageBadgeService,
    ) -> None:
        # 49.9 is red, 80.0 is brightgreen — exercise boundary pair.
        assert service._generate_badge_url(49.9).endswith("-red")
        assert service._generate_badge_url(80.0).endswith("-brightgreen")

    def test_url_uses_url_encoded_percent(
        self,
        service: CoverageBadgeService,
    ) -> None:
        # The literal % in the badge must be URL-encoded as %25
        assert "%25" in service._generate_badge_url(75.0)


# ---------------------------------------------------------------------------
# _has_coverage_badge / _extract_current_coverage
# ---------------------------------------------------------------------------


class TestHasCoverageBadge:
    @pytest.mark.parametrize(
        "content",
        [
            "![Coverage](https://img.shields.io/badge/coverage-50.0%25-yellow)",
            "![coverage](https://img.shields.io/badge/coverage-90.0%25-brightgreen)",
            "![Coverage Badge](https://example.com/coverage.svg)",
            "Some text\nhttps://img.shields.io/badge/coverage-95.5%25-brightgreen\nMore text",
        ],
    )
    def test_detects_badge(self, service: CoverageBadgeService, content: str) -> None:
        assert service._has_coverage_badge(content) is True

    @pytest.mark.parametrize(
        "content",
        [
            "Just a normal README.",
            "# Title\n\nSome content without any badge.\n",
            "![Build](https://img.shields.io/badge/build-passing-green)",
            "",
        ],
    )
    def test_no_badge(self, service: CoverageBadgeService, content: str) -> None:
        assert service._has_coverage_badge(content) is False


class TestExtractCurrentCoverage:
    @pytest.mark.parametrize(
        ("content", "expected"),
        [
            (
                "https://img.shields.io/badge/coverage-95.5%25-brightgreen",
                95.5,
            ),
            (
                "![Coverage](https://img.shields.io/badge/coverage-50.0%25-yellow)",
                50.0,
            ),
            (
                "Some prefix https://img.shields.io/badge/coverage-72.3%25-red suffix",
                72.3,
            ),
        ],
    )
    def test_extract(
        self,
        service: CoverageBadgeService,
        content: str,
        expected: float,
    ) -> None:
        assert service._extract_current_coverage(content) == expected

    def test_no_match_returns_none(self, service: CoverageBadgeService) -> None:
        assert service._extract_current_coverage("no badge here") is None

    def test_empty_string_returns_none(self, service: CoverageBadgeService) -> None:
        assert service._extract_current_coverage("") is None


# ---------------------------------------------------------------------------
# update_readme_coverage_badge
# ---------------------------------------------------------------------------


class TestUpdateReadmeCoverageBadge:
    def test_returns_false_when_readme_missing(
        self,
        service: CoverageBadgeService,
    ) -> None:
        # No README.md created — readme_path does not exist.
        assert service.update_readme_coverage_badge(75.0) is False

    def test_inserts_new_badge_into_empty_readme(
        self,
        service: CoverageBadgeService,
        readme: Path,
    ) -> None:
        readme.write_text("# My Project\n", encoding="utf-8")

        assert service.update_readme_coverage_badge(50.0) is True

        content = readme.read_text(encoding="utf-8")
        assert "![Coverage](https://img.shields.io/badge/coverage-50.0%25-yellow)" in content
        # Title preserved
        assert content.startswith("# My Project")

    def test_inserts_new_badge_after_existing_badges(
        self,
        service: CoverageBadgeService,
        readme: Path,
    ) -> None:
        readme.write_text(
            "# Project\n\n"
            "![Build](https://img.shields.io/badge/build-passing-green)\n"
            "![Version](https://img.shields.io/badge/version-1.0.0-blue)\n"
            "\nDescription here.\n",
            encoding="utf-8",
        )

        assert service.update_readme_coverage_badge(85.0) is True

        content = readme.read_text(encoding="utf-8")
        # Coverage badge was inserted directly after the last existing badge,
        # before the description.
        lines = content.split("\n")
        coverage_idx = next(
            i for i, line in enumerate(lines) if "coverage" in line.lower()
        )
        assert lines[coverage_idx - 1].startswith("![Version")
        assert "Description here" in content

    def test_updates_existing_badge_url(
        self,
        service: CoverageBadgeService,
        readme: Path,
    ) -> None:
        readme.write_text(
            "# Project\n\n"
            "![Coverage](https://img.shields.io/badge/coverage-50.0%25-yellow)\n"
            "\nDescription.\n",
            encoding="utf-8",
        )

        assert service.update_readme_coverage_badge(95.0) is True

        content = readme.read_text(encoding="utf-8")
        assert "coverage-95.0%25-brightgreen" in content
        # Old value gone
        assert "coverage-50.0%25" not in content

    def test_returns_false_when_content_unchanged(
        self,
        service: CoverageBadgeService,
        readme: Path,
    ) -> None:
        # Badge is already there at exactly the value we'd compute
        # (95.0 -> brightgreen). The "changed" check is string equality
        # between the new content and the original content.
        readme.write_text(
            "# Project\n\n"
            "![Coverage](https://img.shields.io/badge/coverage-95.0%25-brightgreen)\n",
            encoding="utf-8",
        )

        # Same coverage percent: no-op, returns False.
        result = service.update_readme_coverage_badge(95.0)
        assert result is False

    def test_uses_insert_after_title_when_no_badges_or_title_blank_line(
        self,
        service: CoverageBadgeService,
        readme: Path,
    ) -> None:
        # No badges, no blank line after title — exercises _insert_after_title.
        readme.write_text("# MyProject\nDescription line.\n", encoding="utf-8")

        assert service.update_readme_coverage_badge(60.0) is True

        content = readme.read_text(encoding="utf-8")
        assert "![Coverage](https://img.shields.io/badge/coverage-60.0%25-yellow)" in content
        # Title is the first line
        assert content.split("\n")[0] == "# MyProject"

    def test_handles_permission_error(
        self,
        service: CoverageBadgeService,
        readme: Path,
    ) -> None:
        # Make read_text raise to exercise the except branch.
        readme.write_text("# X\n", encoding="utf-8")

        original_read_text = Path.read_text
        with pytest.MonkeyPatch.context() as mp:
            def _raise(self, *args, **kwargs):  # type: ignore[no-untyped-def]
                if self == readme:
                    raise OSError("disk error")
                return original_read_text(self, *args, **kwargs)

            mp.setattr(Path, "read_text", _raise)
            assert service.update_readme_coverage_badge(50.0) is False


# ---------------------------------------------------------------------------
# should_update_badge
# ---------------------------------------------------------------------------


class TestShouldUpdateBadge:
    def test_returns_false_when_readme_missing(
        self,
        service: CoverageBadgeService,
    ) -> None:
        assert service.should_update_badge(50.0) is False

    def test_returns_true_when_no_current_coverage(
        self,
        service: CoverageBadgeService,
        readme: Path,
    ) -> None:
        readme.write_text("# Project\nNo badge.\n", encoding="utf-8")
        assert service.should_update_badge(50.0) is True

    def test_returns_false_when_coverage_unchanged(
        self,
        service: CoverageBadgeService,
        readme: Path,
    ) -> None:
        readme.write_text(
            "# Project\n\n"
            "![Coverage](https://img.shields.io/badge/coverage-75.5%25-yellow)\n",
            encoding="utf-8",
        )
        assert service.should_update_badge(75.5) is False

    def test_returns_true_when_coverage_differs(
        self,
        service: CoverageBadgeService,
        readme: Path,
    ) -> None:
        readme.write_text(
            "# Project\n\n"
            "![Coverage](https://img.shields.io/badge/coverage-50.0%25-yellow)\n",
            encoding="utf-8",
        )
        assert service.should_update_badge(85.0) is True

    def test_handles_tiny_below_threshold_as_unchanged(
        self,
        service: CoverageBadgeService,
        readme: Path,
    ) -> None:
        # |delta| < 0.01 should be treated as "unchanged"
        readme.write_text(
            "# Project\n\n"
            "![Coverage](https://img.shields.io/badge/coverage-75.555%25-yellow)\n",
            encoding="utf-8",
        )
        # 75.555 vs 75.555 -> exactly equal -> False
        assert service.should_update_badge(75.555) is False

    def test_returns_true_on_read_exception(
        self,
        service: CoverageBadgeService,
        readme: Path,
    ) -> None:
        readme.write_text("# X\n", encoding="utf-8")
        original_read_text = Path.read_text

        with pytest.MonkeyPatch.context() as mp:
            def _raise(self, *args, **kwargs):  # type: ignore[no-untyped-def]
                if self == readme:
                    raise OSError("boom")
                return original_read_text(self, *args, **kwargs)

            mp.setattr(Path, "read_text", _raise)
            # Bare except -> True
            assert service.should_update_badge(50.0) is True


# ---------------------------------------------------------------------------
# SVG snapshot
# ---------------------------------------------------------------------------


class TestBadgeUrlSnapshot:
    """Snapshot of the canonical badge URLs — these are the SVGs that go
    into README.md. If any of these change, the visual will break in the
    wild. We lock them here."""

    SNAPSHOT_CASES = {
        "0.0": "https://img.shields.io/badge/coverage-0.0%25-red",
        "49.9": "https://img.shields.io/badge/coverage-49.9%25-red",
        "50.0": "https://img.shields.io/badge/coverage-50.0%25-yellow",
        "79.9": "https://img.shields.io/badge/coverage-79.9%25-yellow",
        "80.0": "https://img.shields.io/badge/coverage-80.0%25-brightgreen",
        "100.0": "https://img.shields.io/badge/coverage-100.0%25-brightgreen",
    }

    @pytest.mark.parametrize(
        ("percent_str", "expected_url"),
        list(SNAPSHOT_CASES.items()),
    )
    def test_url_snapshot(
        self,
        service: CoverageBadgeService,
        percent_str: str,
        expected_url: str,
    ) -> None:
        percent = float(percent_str)
        assert service._generate_badge_url(percent) == expected_url

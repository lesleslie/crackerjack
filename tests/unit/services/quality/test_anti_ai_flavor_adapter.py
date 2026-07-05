"""Tests for anti-AI-flavor Crackerjack adapter.

Spec: docs/superpowers/specs/2026-06-22-anti-ai-flavor-style-sop-design.md
Spec #6 from Phase 2 spec batch.

The adapter integrates with the existing crackerjack quality flow as a
hook callable. Reports match counts and file-level summary.
"""

from __future__ import annotations

from pathlib import Path

import pytest

from crackerjack.services.quality.anti_ai_flavor_adapter import (
    AntiAIFlavorReport,
    run_anti_ai_flavor_check,
)


class TestAntiAIFlavorReport:
    def test_empty_report(self):
        report = AntiAIFlavorReport(file="x.md", matches=[])
        assert report.file == "x.md"
        assert report.matches == []
        assert report.is_clean

    def test_dirty_report(self):
        from crackerjack.services.quality.anti_ai_flavor import AntiAIFlavorMatch

        matches = [AntiAIFlavorMatch(phrase="delve into", line=1, column=1)]
        report = AntiAIFlavorReport(file="x.md", matches=matches)
        assert not report.is_clean


class TestRunAntiAIFlavorCheck:
    def test_returns_report_with_no_matches_for_clean_file(self, tmp_path: Path):
        target = tmp_path / "mr.md"
        target.write_text("This is straightforward prose with no AI-tic phrases.\n")
        report = run_anti_ai_flavor_check(target)
        assert report.is_clean
        assert report.file == str(target)
        assert report.matches == []

    def test_returns_report_with_matches_for_flagged_file(self, tmp_path: Path):
        target = tmp_path / "mr.md"
        target.write_text("Let's delve into the parser implementation.\n")
        report = run_anti_ai_flavor_check(target)
        assert not report.is_clean
        assert any(m.phrase == "delve into" for m in report.matches)

    def test_respects_custom_yaml_phrases(self, tmp_path: Path):
        yaml_path = tmp_path / ".anti-ai-flavor.yaml"
        yaml_path.write_text("phrases:\n  - house_special\n")
        target = tmp_path / "mr.md"
        target.write_text(
            "house_special here, also delve into the parser.\n"
        )
        report = run_anti_ai_flavor_check(target, yaml_config=yaml_path)
        phrases = {m.phrase for m in report.matches}
        # YAML phrases are used; default 'delve into' is NOT included
        assert "house_special" in phrases
        assert "delve into" not in phrases

    def test_missing_file_raises_filenotfound(self, tmp_path: Path):
        with pytest.raises(FileNotFoundError):
            run_anti_ai_flavor_check(tmp_path / "does_not_exist.md")

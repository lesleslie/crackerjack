from __future__ import annotations

import json
from pathlib import Path

import pytest

from crackerjack.managers.test_manager import TestManager
from crackerjack.services.coverage_ratchet import CoverageRatchetService


@pytest.fixture
def fake_project(tmp_path: Path) -> tuple[Path, CoverageRatchetService]:
    ratchet = CoverageRatchetService(pkg_path=tmp_path)
    ratchet.initialize_baseline(50.0)
    ratchet.pyproject_file.write_text(
        '[tool.pytest.ini_options]\naddopts = "--cov-fail-under=50.0"\n'
    )
    (tmp_path / "coverage.json").write_text(
        json.dumps({"totals": {"percent_covered": 45.0}})
    )
    return tmp_path, ratchet


def test_test_stage_exits_1_on_drop(fake_project: tuple[Path, CoverageRatchetService]) -> None:
    pkg_path, ratchet = fake_project
    manager = TestManager(pkg_path=pkg_path, coverage_ratchet=ratchet)
    result = manager.run_with_ratchet_check()
    assert result.exit_code == 1
    assert "Coverage regression detected" in result.message


def test_test_stage_bumps_ratchet_and_mirrors_on_rise(fake_project: tuple[Path, CoverageRatchetService]) -> None:
    pkg_path, ratchet = fake_project
    (pkg_path / "coverage.json").write_text(
        json.dumps({"totals": {"percent_covered": 55.0}})
    )
    manager = TestManager(pkg_path=pkg_path, coverage_ratchet=ratchet)
    result = manager.run_with_ratchet_check()
    assert result.exit_code == 0
    data = ratchet.get_ratchet_data()
    assert data["current_minimum"] > 50.0
    assert "--cov-fail-under=55.0" in ratchet.pyproject_file.read_text()

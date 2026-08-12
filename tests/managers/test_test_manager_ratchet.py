from __future__ import annotations

import json
from pathlib import Path
from unittest.mock import patch

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


def test_process_coverage_ratchet_wrapper_fires_ratchet_gate(
    fake_project: tuple[Path, CoverageRatchetService],
) -> None:
    """Verify _process_coverage_ratchet actually invokes run_with_ratchet_check.

    The wrapper must chain both paths so the production test-stage flow sees
    the new ratchet gate (drop/bump semantics), not just the legacy
    process_coverage_ratchet() call.
    """
    pkg_path, ratchet = fake_project
    manager = TestManager(pkg_path=pkg_path, coverage_ratchet=ratchet)

    with patch.object(
        manager,
        "run_with_ratchet_check",
        wraps=manager.run_with_ratchet_check,
    ) as spy:
        manager._process_coverage_ratchet()

    spy.assert_called_once()


def test_process_coverage_ratchet_wrapper_skips_when_no_coverage_json(
    fake_project: tuple[Path, CoverageRatchetService],
) -> None:
    """Wrapper falls back to legacy-only behavior when coverage.json is absent.

    Some call sites (early/late lifecycle, ad-hoc tools) invoke the wrapper
    before tests produce coverage.json. The gate must skip cleanly without
    failing the process_coverage_ratchet result.
    """
    pkg_path, ratchet = fake_project
    (pkg_path / "coverage.json").unlink()
    manager = TestManager(pkg_path=pkg_path, coverage_ratchet=ratchet)

    with patch.object(
        manager,
        "run_with_ratchet_check",
        wraps=manager.run_with_ratchet_check,
    ) as spy:
        manager._process_coverage_ratchet()

    spy.assert_not_called()

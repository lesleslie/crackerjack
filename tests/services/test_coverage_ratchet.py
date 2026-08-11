from __future__ import annotations

import json
from pathlib import Path

import pytest

from crackerjack.services.coverage_ratchet import CoverageRatchetService


@pytest.fixture
def ratchet(tmp_path: Path) -> CoverageRatchetService:
    svc = CoverageRatchetService(pkg_path=tmp_path)
    svc.initialize_baseline(50.0)
    return svc


def test_lower_baseline_requires_reason(ratchet: CoverageRatchetService) -> None:
    with pytest.raises(ValueError, match="reason"):
        ratchet.lower_baseline(45.0, reason="")


def test_lower_baseline_updates_current_minimum(ratchet: CoverageRatchetService) -> None:
    ratchet.lower_baseline(45.0, reason="explicit ack")
    data = ratchet.get_ratchet_data()
    assert data["current_minimum"] == 45.0
    assert data["history"][-1]["reason"] == "explicit ack"


def test_mirror_to_pyproject_writes_cov_fail_under(ratchet: CoverageRatchetService, tmp_path: Path) -> None:
    ratchet.pyproject_file.write_text(
        '[tool.pytest.ini_options]\naddopts = "--cov-fail-under=80"\n'
    )
    ratchet.mirror_to_pyproject(50.0)
    content = ratchet.pyproject_file.read_text()
    assert "--cov-fail-under=50.0" in content


def test_mirror_to_pyproject_handles_array_form_addopts(ratchet: CoverageRatchetService, tmp_path: Path) -> None:
    ratchet.pyproject_file.write_text(
        '[tool.pytest.ini_options]\naddopts = [\n    "--cov=crackerjack",\n    "-n",\n    "auto",\n]\n'
    )
    ratchet.mirror_to_pyproject(68.43)
    content = ratchet.pyproject_file.read_text()
    assert '"--cov-fail-under=68.43"' in content
    # Array form preserved
    assert "addopts = [" in content
    assert '"--cov=crackerjack"' in content
    assert '"-n"' in content


def test_mirror_to_pyproject_handles_array_form_addopts_empty(ratchet: CoverageRatchetService, tmp_path: Path) -> None:
    ratchet.pyproject_file.write_text(
        '[tool.pytest.ini_options]\naddopts = []\n'
    )
    ratchet.mirror_to_pyproject(75.0)
    content = ratchet.pyproject_file.read_text()
    assert '"--cov-fail-under=75.0"' in content


def test_report_status_includes_baseline_and_next_milestone(ratchet: CoverageRatchetService) -> None:
    status = ratchet.report_status()
    assert "50.0%" in status
    assert "50" in status or "60" in status

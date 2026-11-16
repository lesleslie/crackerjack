from __future__ import annotations

import json
from datetime import datetime, timedelta
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
    # The enforced floor is the whole point below the measurement.
    assert '"--cov-fail-under=68.0"' in content
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


def test_mirror_to_pyproject_no_double_comma_in_array(ratchet: CoverageRatchetService, tmp_path: Path) -> None:
    """Regression test for the array-insertion double-comma bug (Task 9 akosha)."""
    ratchet.pyproject_file.write_text(
        '[tool.pytest.ini_options]\naddopts = [\n    "--cov=akosha",\n    "--cov-report=html",\n]\n'
    )
    ratchet.mirror_to_pyproject(87.62)
    content = ratchet.pyproject_file.read_text()
    assert ",," not in content, f"double comma found in:\n{content}"
    assert '"--cov-fail-under=87.0"' in content


def test_mirror_to_pyproject_writes_to_coverage_report_block(ratchet: CoverageRatchetService, tmp_path: Path) -> None:
    """Regression test: mirror site #2 is [tool.coverage.report].fail_under."""
    ratchet.pyproject_file.write_text(
        '[tool.coverage.report]\nfail_under = 85\nshow_missing = true\n'
    )
    ratchet.mirror_to_pyproject(90.0)
    content = ratchet.pyproject_file.read_text()
    assert "fail_under = 90.0" in content
    assert "show_missing = true" in content  # sibling keys preserved


def test_mirror_to_pyproject_writes_both_mirrors(ratchet: CoverageRatchetService, tmp_path: Path) -> None:
    """When both addopts AND [tool.coverage.report] exist, both are updated."""
    ratchet.pyproject_file.write_text(
        '[tool.pytest.ini_options]\naddopts = "--cov-fail-under=80"\n'
        '\n[tool.coverage.report]\nfail_under = 75\n'
    )
    ratchet.mirror_to_pyproject(85.5)
    content = ratchet.pyproject_file.read_text()
    # Both mirror sites carry the SAME floored value.
    assert "--cov-fail-under=85.0" in content
    assert "fail_under = 85.0" in content


def test_report_status_includes_baseline_and_next_milestone(ratchet: CoverageRatchetService) -> None:
    status = ratchet.report_status()
    assert "50.0%" in status
    assert "50" in status or "60" in status


# ---------------------------------------------------------------------------
# Freshness metadata on the maintained path
# ---------------------------------------------------------------------------


def test_maintained_path_refreshes_staleness_metadata(
    ratchet: CoverageRatchetService, tmp_path: Path
) -> None:
    """A flat-coverage measurement must still refresh the ratchet metadata.

    Regression test for the publish gate that refused a present,
    readable ratchet: the ratchet is only rewritten when the baseline
    *improves*, so a repo whose coverage is flat between releases goes
    data-stale as soon as the next test run rewrites ``coverage.json``
    — and time-stale 30 days later.
    """
    import os

    from crackerjack.checks.release_audit import _is_ratchet_stale

    coverage_file = tmp_path / "coverage.json"
    coverage_file.write_text(json.dumps({"totals": {"percent_covered": 50.0}}))

    ratchet.update_coverage(50.0)
    recorded = ratchet.get_ratchet_data()["coverage_data_mtime"]

    # The next test run rewrites coverage.json — its mtime moves.
    os.utime(coverage_file, (recorded + 10.0, recorded + 10.0))
    assert _is_ratchet_stale(ratchet.get_ratchet_data(), project_root=tmp_path), (
        "precondition: the ratchet should be data-stale after a re-measure"
    )

    result = ratchet.update_coverage(50.0)

    assert result["status"] == "maintained"
    refreshed = ratchet.get_ratchet_data()
    assert not _is_ratchet_stale(refreshed, project_root=tmp_path)
    assert refreshed["coverage_data_mtime"] == coverage_file.stat().st_mtime


def test_maintained_path_does_not_move_the_floor(
    ratchet: CoverageRatchetService, tmp_path: Path
) -> None:
    """Refreshing the metadata must not change the enforced floor."""
    coverage_file = tmp_path / "coverage.json"
    coverage_file.write_text(json.dumps({"totals": {"percent_covered": 50.0}}))

    ratchet.update_coverage(50.0)

    data = ratchet.get_ratchet_data()
    assert data["baseline"] == 50.0
    assert data["current_minimum"] == 50.0


def test_maintained_path_leaves_file_alone_without_a_new_measurement(
    ratchet: CoverageRatchetService, tmp_path: Path
) -> None:
    """No new measurement means no rewrite — the file stays byte-identical."""
    coverage_file = tmp_path / "coverage.json"
    coverage_file.write_text(json.dumps({"totals": {"percent_covered": 50.0}}))

    ratchet.update_coverage(50.0)
    before = ratchet.ratchet_file.read_text()

    ratchet.update_coverage(50.0)

    assert ratchet.ratchet_file.read_text() == before


# ---------------------------------------------------------------------------
# The enforced floor: both floor fields must agree
# ---------------------------------------------------------------------------


def test_lower_baseline_updates_both_floor_fields(tmp_path: Path) -> None:
    """Lowering the floor must move ``baseline`` as well as ``current_minimum``.

    The release audit reads ``current_minimum``; the ratchet gate reads
    ``baseline``. Writing only one of them leaves the two gates
    disagreeing about what the floor is — the audit would accept a
    coverage that the gate still calls a regression, so a lowered
    ratchet would block the very publish it was lowered to unblock.
    """
    svc = CoverageRatchetService(pkg_path=tmp_path)
    svc.initialize_baseline(95.0)

    svc.lower_baseline(90.0, reason="acknowledged regression")

    data = svc.get_ratchet_data()
    assert data["baseline"] == 90.0
    assert data["current_minimum"] == 90.0


def test_lowered_floor_unblocks_the_gate(tmp_path: Path) -> None:
    """After an operator lowers the floor, the gate must accept it."""
    from crackerjack.checks.release_audit import _read_ratchet_floor

    svc = CoverageRatchetService(pkg_path=tmp_path)
    svc.initialize_baseline(95.577)
    svc.lower_baseline(90.0, reason="acknowledged regression")

    assert _read_ratchet_floor(svc.ratchet_file) == 90.0
    result = svc.update_coverage(91.0)
    assert result["status"] != "regression"
    assert result["allowed"] is True


def test_raise_floor_updates_both_floor_fields(tmp_path: Path) -> None:
    """``raise_floor`` moves both floor fields together."""
    svc = CoverageRatchetService(pkg_path=tmp_path)
    svc.initialize_baseline(50.0)

    svc.raise_floor(55.0)

    data = svc.get_ratchet_data()
    assert data["baseline"] == 55.0
    assert data["current_minimum"] == 55.0


def test_raise_floor_refreshes_staleness_metadata(tmp_path: Path) -> None:
    """A ratchet written by ``raise_floor`` must carry fresh metadata.

    The legacy ratchet gate used to write the file directly, which left
    the recorded ``coverage_data_mtime`` pointing at the previous
    measurement — the ratchet was data-stale the moment it was written.
    """
    from crackerjack.checks.release_audit import _is_ratchet_stale

    coverage_file = tmp_path / "coverage.json"
    coverage_file.write_text(json.dumps({"totals": {"percent_covered": 55.0}}))

    svc = CoverageRatchetService(pkg_path=tmp_path)
    svc.initialize_baseline(50.0)

    svc.raise_floor(55.0)

    data = svc.get_ratchet_data()
    assert data["coverage_data_mtime"] == coverage_file.stat().st_mtime
    assert not _is_ratchet_stale(data, project_root=tmp_path)


# ---------------------------------------------------------------------------
# The two pyproject mirror sites must carry the same floor
# ---------------------------------------------------------------------------


def test_update_pyproject_requirement_updates_both_mirror_sites(
    tmp_path: Path,
) -> None:
    """pytest-cov and coverage.py must enforce the same floor.

    ``--cov-fail-under`` (pytest-cov) and ``fail_under``
    (``[tool.coverage.report]``, coverage.py) are two enforcement
    points for the same requirement. Updating only one leaves the repo
    enforcing whichever number nobody looked at.
    """
    pyproject = tmp_path / "pyproject.toml"
    pyproject.write_text(
        '[tool.pytest.ini_options]\naddopts = "--cov-fail-under=50.0"\n'
        "\n[tool.coverage.report]\nfail_under = 50.0\n"
    )
    svc = CoverageRatchetService(pkg_path=tmp_path)

    svc._update_pyproject_requirement(95.5)

    content = pyproject.read_text()
    assert "--cov-fail-under=95.5" in content
    assert "fail_under = 95.5" in content


def test_update_pyproject_requirement_leaves_absent_mirror_alone(
    tmp_path: Path,
) -> None:
    """A repo without the ``fail_under`` block must not gain one."""
    pyproject = tmp_path / "pyproject.toml"
    pyproject.write_text(
        '[tool.pytest.ini_options]\naddopts = "--cov-fail-under=50.0"\n'
    )
    svc = CoverageRatchetService(pkg_path=tmp_path)

    svc._update_pyproject_requirement(95.5)

    content = pyproject.read_text()
    assert "--cov-fail-under=95.5" in content
    assert "fail_under" not in content


# ---------------------------------------------------------------------------
# Timestamps are timezone-aware
# ---------------------------------------------------------------------------


def test_generated_at_is_timezone_aware_utc(ratchet: CoverageRatchetService) -> None:
    """``generated_at`` must be aware UTC, not naive local time.

    The release audit normalizes a naive timestamp to UTC, so a naive
    *local* timestamp is read as hours in the past — which shortens
    the 30-day staleness window by the machine's UTC offset.
    """
    generated_at = ratchet.get_ratchet_data()["generated_at"]
    parsed = datetime.fromisoformat(generated_at)
    assert parsed.tzinfo is not None
    assert parsed.utcoffset() == timedelta(0)

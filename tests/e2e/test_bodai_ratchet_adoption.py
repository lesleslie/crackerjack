from __future__ import annotations

import json
import shutil
from pathlib import Path

import pytest
from typer.testing import CliRunner

from crackerjack.cli.coverage_ratchet_cli import app


@pytest.fixture
def mcp_common_copy(tmp_path: Path) -> Path:
    """Copy a stripped-down version of mcp-common to tmp_path."""
    src = Path("/Users/les/Projects/mcp-common")
    dest = tmp_path / "mcp-common"
    if not src.exists():
        pytest.skip("mcp-common not available in this environment")
    dest.mkdir(parents=True, exist_ok=True)
    shutil.copy(src / "pyproject.toml", dest / "pyproject.toml")
    if (src / "coverage.json").exists():
        shutil.copy(src / "coverage.json", dest / "coverage.json")
    return dest


def test_init_then_run_keeps_ratchet_stable(mcp_common_copy: Path) -> None:
    runner = CliRunner()
    if not (mcp_common_copy / "coverage.json").exists():
        pytest.skip("coverage.json not present in mcp-common")
    initial = json.loads(
        (mcp_common_copy / "coverage.json").read_text()
    )["totals"]["percent_covered"]
    result = runner.invoke(app, ["init", "--pkg-path", str(mcp_common_copy)])
    assert result.exit_code == 0, result.output
    ratchet = json.loads((mcp_common_copy / ".coverage-ratchet.json").read_text())
    assert ratchet["baseline"] == initial
    assert ratchet["current_minimum"] == initial
    # Re-run init with --reinit should overwrite
    result2 = runner.invoke(
        app, ["init", "--reinit", "--pkg-path", str(mcp_common_copy)]
    )
    assert result2.exit_code == 0, result2.output


def test_init_refuses_overwrite_without_reinit(mcp_common_copy: Path) -> None:
    runner = CliRunner()
    if not (mcp_common_copy / "coverage.json").exists():
        pytest.skip("coverage.json not present in mcp-common")
    runner.invoke(app, ["init", "--pkg-path", str(mcp_common_copy)])
    result = runner.invoke(app, ["init", "--pkg-path", str(mcp_common_copy)])
    assert result.exit_code != 0, result.output
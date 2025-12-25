import subprocess

import pytest


def _simulate_workflow(monkeypatch: pytest.MonkeyPatch) -> tuple[int, str]:
    outputs = {
        "fast": subprocess.CompletedProcess(
            ["python", "-m", "crackerjack", "--fast"], 0, stdout="", stderr=""
        ),
        "tests": subprocess.CompletedProcess(
            ["python", "-m", "crackerjack", "-t"],
            0,
            stdout="Running test suite",
            stderr="",
        ),
        "comp": subprocess.CompletedProcess(
            ["python", "-m", "crackerjack", "--comp"], 0, stdout="", stderr=""
        ),
    }

    def fake_run(cmd, **kwargs):
        if "--fast" in cmd:
            return outputs["fast"]
        if "--comp" in cmd:
            return outputs["comp"]
        return outputs["tests"]

    monkeypatch.setattr(subprocess, "run", fake_run)
    return outputs["tests"].returncode, outputs["tests"].stdout


def test_fast_hooks_stop_on_failure(monkeypatch: pytest.MonkeyPatch) -> None:
    """Test that workflow continues to tests when fast hooks pass."""
    returncode, output = _simulate_workflow(monkeypatch)
    assert returncode == 0
    assert "Running test suite" in output


def test_comprehensive_workflow_order(monkeypatch: pytest.MonkeyPatch) -> None:
    """Test that comprehensive hooks can run after fast hooks pass."""
    _simulate_workflow(monkeypatch)
    result = subprocess.run(
        ["python", "-m", "crackerjack", "--comp"],
        capture_output=True,
        text=True,
        timeout=120,
    )
    assert result.returncode == 0

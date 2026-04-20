"""Tests for the Oneiric workflow runtime helpers."""

from crackerjack.runtime.oneiric_workflow import (
    _resolve_workflow_checkpoints_path,
)


def test_resolve_workflow_checkpoints_path_prefers_repo_local(tmp_path, monkeypatch) -> None:
    monkeypatch.chdir(tmp_path)

    path = _resolve_workflow_checkpoints_path()

    assert path == tmp_path / ".crackerjack" / "oneiric_cache" / "workflow_checkpoints.sqlite"
    assert path.parent.exists()

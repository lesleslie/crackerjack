"""Tests for ``crackerjack.config.loader`` public surface (REQ-002, REQ-007).

This file is the single canonical location for loader tests. The previous
version imported private helpers that were deleted in Task 4 (factory
swap); the wholesale replacement tests the public surface only.

Merged from ``tests/config/test_loader_oneiric.py`` (deleted in this
commit per R6.1) and the pre-existing env-overlay / XDG-override tests.

R3 — every fixture-based test uses ``monkeypatch.chdir(tmp_path)`` so
``load_settings`` (CWD-relative) and ``crackerjack_env_overlay`` resolve
against the fixture repo.

R5 — assertions reference real ``CrackerjackSettings.model_fields``
keys (``enable_orchestration``, ``cache_ttl``, ``default_timeout``,
``adapter_timeouts``, etc.). Do NOT introduce ``log_level`` — it is not
a field on CrackerjackSettings.
"""

from __future__ import annotations

import asyncio
import logging
from pathlib import Path

import pytest

from crackerjack.config.settings import CrackerjackSettings
from crackerjack.config.loader import (
    crackerjack_env_overlay,
    load_settings,
    load_settings_async,
)


# --- Fixtures ----------------------------------------------------------------


@pytest.fixture
def repo_with_settings(tmp_path: Path) -> Path:
    """Fixture: a repo layout with ``settings/crackerjack.yaml`` + ``pyproject.toml``.

    The pyproject.toml includes ``[tool.crackerjack]`` (a real scalar
    section read by load_settings) and ``[tool.crackerjack.betterleaks]``
    (a fictional sub-table used by the unknown-block warning test). The
    ``crackerjack/`` package marker is irrelevant to the loader but
    mirrors a real project layout.
    """
    repo = tmp_path / "repo"
    settings_dir = repo / "settings"
    settings_dir.mkdir(parents=True)
    (settings_dir / "crackerjack.yaml").write_text(
        "enable_orchestration: true\ncache_ttl: 3600\n",
        encoding="utf-8",
    )
    (repo / "pyproject.toml").write_text(
        "[tool.crackerjack]\nenable_orchestration = true\n\n"
        "[tool.crackerjack.betterleaks]\nenabled = true\n",
        encoding="utf-8",
    )
    (repo / "crackerjack").mkdir(exist_ok=True)
    return repo


# --- Public-surface behaviour tests (REQ-002, REQ-007) -----------------------


def test_load_settings_returns_typed_instance(
    repo_with_settings: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """``load_settings(CrackerjackSettings)`` returns a typed instance with
    ``enable_orchestration`` propagated from the YAML (R5: real field)."""
    monkeypatch.chdir(repo_with_settings)
    s = load_settings(CrackerjackSettings)
    assert isinstance(s, CrackerjackSettings)
    assert s.enable_orchestration is True


def test_load_settings_async_returns_same_instance(
    repo_with_settings: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """Async wrapper returns the same typed instance (REQ-007)."""
    monkeypatch.chdir(repo_with_settings)
    s = asyncio.run(load_settings_async(CrackerjackSettings))
    assert isinstance(s, CrackerjackSettings)
    assert s.enable_orchestration is True


def test_xdg_overrides_yaml(
    repo_with_settings: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """XDG user-local override beats project YAML (REQ-001, REQ-002).

    The Oneiric factory reads ``$XDG_CONFIG_HOME/crackerjack/config.yaml``
    after the project YAML; here we override ``cache_ttl`` (a real
    ``CrackerjackSettings`` field) and assert the XDG value wins.
    """
    xdg_root = repo_with_settings.parent / "xdg"
    (xdg_root / "crackerjack").mkdir(parents=True)
    (xdg_root / "crackerjack" / "config.yaml").write_text(
        "cache_ttl: 9999\n", encoding="utf-8"
    )
    monkeypatch.setenv("XDG_CONFIG_HOME", str(xdg_root))
    monkeypatch.chdir(repo_with_settings)
    s = load_settings(CrackerjackSettings)
    assert s.cache_ttl == 9999


def test_env_overlay_overrides_yaml(
    repo_with_settings: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """``CRACKERJACK_*`` env vars override YAML (REQ-006)."""
    monkeypatch.setenv("CRACKERJACK_ENABLE_ORCHESTRATION", "false")
    monkeypatch.chdir(repo_with_settings)
    s = load_settings(CrackerjackSettings)
    assert s.enable_orchestration is False


def test_unknown_pyproject_subtable_warns(
    repo_with_settings: Path,
    monkeypatch: pytest.MonkeyPatch,
    caplog: pytest.LogCaptureFixture,
) -> None:
    """``[tool.crackerjack.betterleaks]`` (fictional) emits a WARNING
    from ``crackerjack.config.validators`` (the post-merge validator in
    ``CrackerjackSettings._warn_unknown_pyproject_subtables`` — REQ-003)."""
    monkeypatch.chdir(repo_with_settings)
    with caplog.at_level(logging.WARNING, logger="crackerjack.config.validators"):
        load_settings(CrackerjackSettings)
    msgs = [r.getMessage() for r in caplog.records]
    assert any("betterleaks" in m for m in msgs)


def test_missing_settings_falls_back_to_defaults(
    repo_with_settings: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """With no settings files, the loader returns a default CrackerjackSettings."""
    empty_repo = repo_with_settings.parent / "empty_repo"
    empty_repo.mkdir(exist_ok=True)
    monkeypatch.chdir(empty_repo)
    # Should not raise — falls back to defaults + env-var-only.
    s = load_settings(CrackerjackSettings)
    assert isinstance(s, CrackerjackSettings)


def test_oneiric_loader_failure_falls_back(
    repo_with_settings: Path,
    monkeypatch: pytest.MonkeyPatch,
    caplog: pytest.LogCaptureFixture,
) -> None:
    """When the Oneiric factory raises, the loader must not propagate.

    ``crackerjack.config.loader.load_settings_for_project`` does
    ``from oneiric.core.config import load_settings as _oneiric_load``
    inside its body — so the local import re-resolves ``load_settings``
    on the source module each call. Patching
    ``oneiric.core.config.load_settings`` (the original symbol) is the
    correct attach point; patching ``crackerjack.config.loader._oneiric_load``
    would NOT work because that name is local-scope only.

    The ``log_settings`` exception path records the failure on the
    ``crackerjack.config.loader`` logger — we assert the canonical
    fingerprint (``oneiric_loader_failed``) is present in the log.
    """
    def _raise(*_a: object, **_kw: object) -> object:
        raise RuntimeError("simulated oneiric failure")

    monkeypatch.setattr("oneiric.core.config.load_settings", _raise)
    monkeypatch.chdir(repo_with_settings)
    with caplog.at_level(logging.ERROR, logger="crackerjack.config.loader"):
        s = load_settings(CrackerjackSettings)
    assert isinstance(s, CrackerjackSettings)
    assert any(
        "oneiric_loader_failed" in r.getMessage() for r in caplog.records
    )


def test_timeout_reshape_works(
    repo_with_settings: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """Regression guard for R6.2: top-level ``*_timeout`` keys reach the
    ``_reshape_adapter_timeouts`` validator (REQ-004) so values land in
    ``adapter_timeouts.<key>`` rather than being silently dropped by the
    per-key extras filter.

    Uses ``bandit_timeout`` and ``semgrep_timeout`` because both are
    declared on ``AdapterTimeouts`` (``crackerjack/config/settings.py:239-240``);
    earlier draft used ``ruff_timeout``/``mypy_timeout`` (review I1)
    which only worked because ``OneiricMCPConfig`` accepts extras —
    fragile against any future tighten of ``extra="allow"``.
    """
    settings_dir = repo_with_settings / "settings"
    (settings_dir / "crackerjack.yaml").write_text(
        "bandit_timeout: 60\nsemgrep_timeout: 120\n", encoding="utf-8"
    )
    monkeypatch.chdir(repo_with_settings)
    s = load_settings(CrackerjackSettings)
    assert s.adapter_timeouts.bandit_timeout == 60
    assert s.adapter_timeouts.semgrep_timeout == 120
    # The top-level ``*_timeout`` keys must NOT survive at the top
    # level — REQ-004's contract is reshape-into-sub-dict.
    dump = s.model_dump()
    assert "bandit_timeout" not in dump
    assert "semgrep_timeout" not in dump


# --- Helper-unit tests ------------------------------------------------------


def test_crackerjack_env_overlay_basic(monkeypatch: pytest.MonkeyPatch) -> None:
    """``crackerjack_env_overlay`` builds the nested-dict overlay shape
    and drops non-``model_fields`` keys (REQ-006).
    """
    monkeypatch.setenv("CRACKERJACK_DOC_UPDATES__MODEL", "claude-haiku-4-5")
    monkeypatch.delenv("CRACKERJACK_FOO", raising=False)
    overlay = crackerjack_env_overlay(CrackerjackSettings)
    assert overlay["doc_updates"]["model"] == "claude-haiku-4-5"
    # Unknown top-level keys (not in model_fields) are silently dropped.
    assert "foo" not in overlay


def test_crackerjack_env_overlay_drops_non_field_keys(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Keys not declared on ``CrackerjackSettings.model_fields`` are
    silently dropped (R5: respect the model's field set).
    """
    monkeypatch.setenv("CRACKERJACK_NONEXISTENT_FIELD_XYZ", "9999")
    overlay = crackerjack_env_overlay(CrackerjackSettings)
    assert "nonexistent_field_xyz" not in overlay
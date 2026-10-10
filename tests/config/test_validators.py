from __future__ import annotations

import logging
from pathlib import Path

from crackerjack.config.settings import (
    CrackerjackSettings,
    _KNOWN_PYPROJECT_SUBTABLES,
)


def test_reshape_adapter_timeouts_before() -> None:
    raw = {
        "ruff_timeout": 60,
        "mypy_timeout": 120,
        "console": {"width": 70},
    }
    settings = CrackerjackSettings.model_validate(raw)
    assert settings.adapter_timeouts.ruff_timeout == 60
    assert settings.adapter_timeouts.mypy_timeout == 120
    # Top-level timeouts removed
    assert "ruff_timeout" not in settings.model_dump()
    assert "mypy_timeout" not in settings.model_dump()


def test_warn_unknown_pyproject_subtables_after(
    tmp_path: Path, monkeypatch, caplog
) -> None:
    pyproject = tmp_path / "pyproject.toml"
    pyproject.write_text(
        '[tool.crackerjack.betterleaks]\nenabled = true\n',
        encoding="utf-8",
    )
    monkeypatch.chdir(tmp_path)
    with caplog.at_level(logging.WARNING, logger="crackerjack.config.validators"):
        CrackerjackSettings.model_validate({})
    msgs = [r.getMessage() for r in caplog.records]
    assert any("[tool.crackerjack.betterleaks]" in m for m in msgs), (
        f"expected betterleaks warning, got: {msgs!r}"
    )
    assert "jinja" in _KNOWN_PYPROJECT_SUBTABLES  # sanity


def test_known_pyproject_subtable_does_not_warn(
    tmp_path: Path, monkeypatch, caplog
) -> None:
    pyproject = tmp_path / "pyproject.toml"
    pyproject.write_text(
        '[tool.crackerjack.jinja]\nblock_start_string = "{%"\n'
        '[tool.crackerjack.betterleaks]\nenabled = true\n',
        encoding="utf-8",
    )
    monkeypatch.chdir(tmp_path)
    with caplog.at_level(logging.WARNING, logger="crackerjack.config.validators"):
        CrackerjackSettings.model_validate({})
    msgs = [r.getMessage() for r in caplog.records]
    assert not any("[tool.crackerjack.jinja]" in m for m in msgs), (
        f"jinja sub-table should not warn; got: {msgs!r}"
    )
    assert any("[tool.crackerjack.betterleaks]" in m for m in msgs)

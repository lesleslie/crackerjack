"""Tests for ``crackerjack.services.quality.anti_ai_flavor_adapter``.

This thin adapter wraps ``detect_anti_ai_flavor`` with an
``AntiAIFlavorReport`` dataclass that has a serializable ``to_dict`` form.
The YAML-config path loads custom phrases via
``AntiAIFlavorDetector.load_phrases_from_yaml`` (a real YAML file under
``tmp_path``).
"""

from __future__ import annotations

import textwrap
from pathlib import Path

import pytest

from crackerjack.services.quality.anti_ai_flavor_adapter import (
    AntiAIFlavorReport,
    run_anti_ai_flavor_check,
)
from crackerjack.services.quality.anti_ai_flavor import AntiAIFlavorMatch


def test_report_is_clean_when_no_matches() -> None:
    report = AntiAIFlavorReport(file="a.py", matches=[])
    assert report.is_clean is True


def test_report_is_not_clean_with_matches() -> None:
    match = AntiAIFlavorMatch(
        phrase="delve into",
        line=1,
        column=1,
    )
    report = AntiAIFlavorReport(file="a.py", matches=[match])
    assert report.is_clean is False


def test_report_to_dict_shape() -> None:
    match = AntiAIFlavorMatch(
        phrase="delve",
        line=5,
        column=3,
    )
    report = AntiAIFlavorReport(file="a.py", matches=[match])
    data = report.to_dict()
    assert data["file"] == "a.py"
    assert data["is_clean"] is False
    assert data["match_count"] == 1
    assert isinstance(data["matches"], list)
    assert data["matches"][0]["phrase"] == "delve"


def test_report_to_dict_clean() -> None:
    report = AntiAIFlavorReport(file="clean.py", matches=[])
    data = report.to_dict()
    assert data["is_clean"] is True
    assert data["match_count"] == 0


def test_run_check_missing_file_raises(tmp_path: Path) -> None:
    with pytest.raises(FileNotFoundError, match="File not found"):
        run_anti_ai_flavor_check(tmp_path / "nope.py")


def test_run_check_clean_file(tmp_path: Path) -> None:
    src = tmp_path / "clean.py"
    src.write_text("def foo():\n    return 1\n", encoding="utf-8")
    report = run_anti_ai_flavor_check(src)
    assert report.is_clean is True
    assert report.file == str(src)


def test_run_check_with_default_phrases_detects(
    tmp_path: Path,
) -> None:
    """A file with a default anti-AI phrase produces matches."""
    src = tmp_path / "ai_flavored.py"
    src.write_text("Let's delve into this topic.\n", encoding="utf-8")
    report = run_anti_ai_flavor_check(src)
    assert report.is_clean is False
    assert any(m.phrase == "delve" or "delve" in m.phrase for m in report.matches)


def test_run_check_with_yaml_config_loads_custom_phrases(
    tmp_path: Path,
) -> None:
    yaml = tmp_path / "phrases.yaml"
    yaml.write_text(
        textwrap.dedent(
            """\
            phrases:
              - "smorgasbord"
              - "multifaceted"
            """
        ),
        encoding="utf-8",
    )
    src = tmp_path / "doc.md"
    src.write_text("A smorgasbord of options.\n", encoding="utf-8")
    report = run_anti_ai_flavor_check(src, yaml_config=yaml)
    assert report.is_clean is False
    assert any("smorgasbord" in m.phrase for m in report.matches)


def test_run_check_yaml_empty_phrases_falls_back_to_defaults(
    tmp_path: Path,
) -> None:
    """An empty YAML phrases list falls back to default phrases (the
    ``phrases = None`` branch at line 45)."""
    yaml = tmp_path / "empty.yaml"
    yaml.write_text("phrases: []\n", encoding="utf-8")
    src = tmp_path / "ai.py"
    src.write_text("Let's delve into this.\n", encoding="utf-8")
    report = run_anti_ai_flavor_check(src, yaml_config=yaml)
    # Defaults still fire.
    assert report.is_clean is False


def test_run_check_yaml_returns_nothing_when_no_default_match(
    tmp_path: Path,
) -> None:
    """A YAML with only custom phrases, no defaults match, produces no matches."""
    yaml = tmp_path / "phrases.yaml"
    yaml.write_text(
        textwrap.dedent(
            """\
            phrases:
              - "smorgasbord"
            """
        ),
        encoding="utf-8",
    )
    src = tmp_path / "clean.py"
    src.write_text("def foo():\n    return 1\n", encoding="utf-8")
    report = run_anti_ai_flavor_check(src, yaml_config=yaml)
    assert report.is_clean is True

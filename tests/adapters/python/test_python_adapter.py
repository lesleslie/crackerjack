from __future__ import annotations

import tempfile
from pathlib import Path

from crackerjack.adapters.base import LanguageAdapter
from crackerjack.adapters.python import PythonAdapter


def test_python_adapter_is_a_language_adapter() -> None:
    assert isinstance(PythonAdapter(), LanguageAdapter)


def test_python_adapter_detects_pyproject(tmp_path: Path) -> None:
    (tmp_path / "pyproject.toml").write_text('[project]\nname = "x"\nversion = "0.1.0"\n')
    assert PythonAdapter().detect(tmp_path) is True


def test_python_adapter_skips_projects_without_pyproject(tmp_path: Path) -> None:
    assert PythonAdapter().detect(tmp_path) is False


def test_python_adapter_capabilities_includes_lifecycle_and_hooks(tmp_path: Path) -> None:
    (tmp_path / "pyproject.toml").write_text('[project]\nname = "x"\nversion = "0.1.0"\n')
    caps = PythonAdapter().capabilities(tmp_path)

    assert caps.has_lifecycle is True
    assert caps.version_source is not None
    assert len(caps.hooks) > 0

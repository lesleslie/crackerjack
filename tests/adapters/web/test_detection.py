"""Detection guard tests — Web adapter must NOT fire on Python projects without opt-in (per spec Writing F3)."""
from __future__ import annotations

from pathlib import Path

import pytest

from crackerjack.adapters.web import package_json_present, web_enabled


class TestPackageJsonPresent:
    def test_returns_true_when_present(self, tmp_path: Path) -> None:
        (tmp_path / "package.json").write_text("{}")
        assert package_json_present(tmp_path) is True

    def test_returns_false_when_missing(self, tmp_path: Path) -> None:
        assert package_json_present(tmp_path) is False


class TestWebEnabled:
    def test_true_when_package_json_present(self, tmp_path: Path) -> None:
        (tmp_path / "package.json").write_text("{}")
        assert web_enabled(tmp_path) is True

    def test_false_for_python_project_no_opt_in(self, tmp_path: Path) -> None:
        (tmp_path / "pyproject.toml").write_text("[project]\nname = 'foo'\n")
        assert web_enabled(tmp_path) is False

    def test_true_for_python_project_with_opt_in(self, tmp_path: Path) -> None:
        (tmp_path / "pyproject.toml").write_text(
            "[project]\nname = 'foo'\n[tool.crackerjack.web]\nenabled = true\n"
        )
        assert web_enabled(tmp_path) is True

    def test_package_json_wins_over_opt_in_false(self, tmp_path: Path) -> None:
        (tmp_path / "package.json").write_text("{}")
        (tmp_path / "pyproject.toml").write_text(
            "[tool.crackerjack.web]\nenabled = false\n"
        )
        assert web_enabled(tmp_path) is True

    def test_opt_in_false_without_package_json_is_false(self, tmp_path: Path) -> None:
        (tmp_path / "pyproject.toml").write_text(
            "[tool.crackerjack.web]\nenabled = false\n"
        )
        assert web_enabled(tmp_path) is False

    def test_malformed_pyproject_returns_false(self, tmp_path: Path) -> None:
        (tmp_path / "pyproject.toml").write_text("not valid toml {{{")
        assert web_enabled(tmp_path) is False

    def test_missing_pyproject_returns_false(self, tmp_path: Path) -> None:
        assert web_enabled(tmp_path) is False

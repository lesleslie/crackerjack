"""WebAdapter contract tests."""
from __future__ import annotations

from pathlib import Path

import pytest

from crackerjack.adapters.base import LanguageAdapterBase
from crackerjack.adapters.web import WebAdapter, web_hooks


class TestWebAdapter:
    def test_extends_language_adapter_base(self) -> None:
        assert issubclass(WebAdapter, LanguageAdapterBase)

    def test_name_is_web(self) -> None:
        assert WebAdapter().name == "web"

    def test_detect_returns_true_when_package_json_present(self, tmp_path: Path) -> None:
        (tmp_path / "package.json").write_text("{}")
        assert WebAdapter().detect(tmp_path) is True

    def test_detect_returns_false_for_python_project_no_opt_in(self, tmp_path: Path) -> None:
        (tmp_path / "pyproject.toml").write_text("[project]\nname = 'foo'\n")
        assert WebAdapter().detect(tmp_path) is False

    def test_detect_returns_true_for_python_project_with_opt_in(self, tmp_path: Path) -> None:
        (tmp_path / "pyproject.toml").write_text(
            "[project]\nname = 'foo'\n[tool.crackerjack.web]\nenabled = true\n"
        )
        assert WebAdapter().detect(tmp_path) is True

    def test_capabilities_has_no_lifecycle(self, tmp_path: Path) -> None:
        (tmp_path / "package.json").write_text("{}")
        caps = WebAdapter().capabilities(tmp_path)
        assert caps.has_lifecycle is False
        assert caps.has_version is False

    def test_capabilities_exposes_four_hooks(self, tmp_path: Path) -> None:
        (tmp_path / "package.json").write_text("{}")
        caps = WebAdapter().capabilities(tmp_path)
        names = {h.name for h in caps.hooks}
        assert names == {
            "web.stylelint",
            "web.eslint",
            "web.tsc",
            "web.html_validate",
        }

    def test_capabilities_hooks_match_web_hooks_function(self, tmp_path: Path) -> None:
        (tmp_path / "package.json").write_text("{}")
        caps = WebAdapter().capabilities(tmp_path)
        assert caps.hooks == web_hooks(tmp_path)

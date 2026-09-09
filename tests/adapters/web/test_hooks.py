"""Hook construction + CLI-missing branch + JSON output parsing smoke."""
from __future__ import annotations

import json
import subprocess
from pathlib import Path
from unittest import mock

import pytest

from crackerjack.adapters.web.hooks import (
    WebHookError,
    _parse_stylelint_json,
    _parse_eslint_json,
    _parse_html_validate_json,
    _parse_tsc_output,
    _resolve,
    web_hooks,
)


class TestResolve:
    def test_node_modules_bin_wins(self, tmp_path: Path) -> None:
        (tmp_path / "node_modules" / ".bin" / "stylelint").mkdir(parents=True)
        (tmp_path / "node_modules" / ".bin" / "stylelint" / "stylelint").write_text("#!/bin/sh\n")
        assert _resolve(tmp_path, "stylelint") == (
            str(tmp_path / "node_modules" / ".bin" / "stylelint" / "stylelint"),
        )

    def test_path_wins_when_no_node_modules(self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
        monkeypatch.setattr("shutil.which", lambda cmd: f"/usr/bin/{cmd}" if cmd == "stylelint" else None)
        assert _resolve(tmp_path, "stylelint") == ("/usr/bin/stylelint",)

    def test_npx_fallback(self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
        monkeypatch.setattr("shutil.which", lambda cmd: "/usr/bin/npx" if cmd == "npx" else None)
        assert _resolve(tmp_path, "stylelint") == ("npx", "--no", "stylelint")

    def test_returns_none_when_all_paths_missing(self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
        monkeypatch.setattr("shutil.which", lambda cmd: None)
        assert _resolve(tmp_path, "stylelint") is None


class TestWebHooks:
    def test_returns_four_hooks(self, tmp_path: Path) -> None:
        (tmp_path / "package.json").write_text("{}")
        hooks = web_hooks(tmp_path)
        names = {h.name for h in hooks}
        assert names == {
            "web.stylelint",
            "web.eslint",
            "web.tsc",
            "web.html_validate",
        }

    def test_hooks_have_no_fallback(self, tmp_path: Path) -> None:
        (tmp_path / "package.json").write_text("{}")
        hooks = web_hooks(tmp_path)
        assert all(h.fallback is None for h in hooks)

    def test_hooks_use_timeout_seconds(self, tmp_path: Path) -> None:
        (tmp_path / "package.json").write_text("{}")
        hooks = web_hooks(tmp_path)
        for h in hooks:
            assert h.timeout_seconds > 0

    def test_webhook_error_raised_when_resolve_fails(self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
        (tmp_path / "package.json").write_text("{}")
        monkeypatch.setattr("shutil.which", lambda cmd: None)
        with pytest.raises(WebHookError, match="npm install"):
            web_hooks(tmp_path)


class TestJsonParsers:
    def test_stylelint_json_parses_one_warning(self) -> None:
        payload = json.dumps(
            [{"source": "x.css", "warnings": [{"line": 3, "text": "no-empty-rules"}]}]
        )
        issues = _parse_stylelint_json(payload, Path("/proj"))
        assert len(issues) == 1
        assert issues[0][1] == 3  # line

    def test_eslint_json_parses_messages(self) -> None:
        payload = json.dumps(
            [{"filePath": "/proj/a.ts", "messages": [{"line": 7, "message": "no-unused-vars"}]}]
        )
        issues = _parse_eslint_json(payload, Path("/proj"))
        assert len(issues) == 1

    def test_html_validate_json_parses_messages(self) -> None:
        payload = json.dumps(
            [{"filePath": "/proj/a.html", "messages": [{"line": 2, "message": "no-trailing-whitespace"}]}]
        )
        issues = _parse_html_validate_json(payload, Path("/proj"))
        assert len(issues) == 1

    def test_tsc_output_parses_errors(self) -> None:
        out = "a.ts(5,10): error TS2304: Cannot find name 'foo'.\n"
        issues = _parse_tsc_output(out, Path("/proj"))
        assert len(issues) == 1
        assert "TS2304" in issues[0][2]

    def test_tsc_output_returns_empty_when_clean(self) -> None:
        assert _parse_tsc_output("", Path("/proj")) == []

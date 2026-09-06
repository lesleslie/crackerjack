"""Tests for ``crackerjack.adapters.type.pyright``.

The adapter wraps the ``pyright`` CLI to perform type checking. Tests
mock at the subprocess / base class level so the JSON parser, text
parser, and command builder can be exercised without invoking pyright.
"""

from __future__ import annotations

import json
from pathlib import Path
from uuid import UUID

import pytest

from crackerjack.adapters._tool_adapter_base import (
    ToolExecutionResult,
    ToolIssue,
)
from crackerjack.adapters.type.pyright import (
    MODULE_ID,
    MODULE_STATUS,
    PyrightAdapter,
    PyrightSettings,
)
from crackerjack.models.adapter_metadata import AdapterStatus
from crackerjack.models.qa_config import QACheckConfig
from crackerjack.models.qa_results import QACheckType


# ---------------------------------------------------------------------------
# Module constants
# ---------------------------------------------------------------------------


def test_module_id_is_uuid() -> None:
    assert isinstance(MODULE_ID, UUID)


def test_module_status_is_beta() -> None:
    assert MODULE_STATUS == AdapterStatus.BETA


# ---------------------------------------------------------------------------
# PyrightSettings
# ---------------------------------------------------------------------------


def test_pyright_settings_defaults() -> None:
    s = PyrightSettings()
    assert s.tool_name == "pyright"
    assert s.use_json_output is True
    assert s.strict_mode is False
    assert s.ignore_missing_imports is False
    assert s.type_checking_mode == "basic"
    assert s.report_unnecessary_type_ignore_comment == "warning"
    assert s.report_missing_type_stubs == "warning"


# ---------------------------------------------------------------------------
# PyrightAdapter init
# ---------------------------------------------------------------------------


def test_adapter_init_with_settings() -> None:
    s = PyrightSettings()
    adapter = PyrightAdapter(settings=s)
    assert adapter.settings is s


def test_adapter_init_without_settings() -> None:
    adapter = PyrightAdapter()
    assert adapter.settings is None


# ---------------------------------------------------------------------------
# adapter_name / module_id / tool_name
# ---------------------------------------------------------------------------


def test_adapter_name() -> None:
    adapter = PyrightAdapter(settings=PyrightSettings())
    assert "Pyright" in adapter.adapter_name


def test_module_id_property() -> None:
    adapter = PyrightAdapter(settings=PyrightSettings())
    assert adapter.module_id == MODULE_ID


def test_tool_name_property() -> None:
    adapter = PyrightAdapter(settings=PyrightSettings())
    assert adapter.tool_name == "pyright"


# ---------------------------------------------------------------------------
# async init
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_init_creates_default_settings_when_none() -> None:
    adapter = PyrightAdapter()
    await adapter.init()
    assert adapter.settings is not None
    assert adapter.settings.tool_name == "pyright"
    assert adapter.settings.timeout_seconds == 180
    assert adapter.settings.max_workers == 4


@pytest.mark.asyncio
async def test_init_preserves_existing_settings() -> None:
    s = PyrightSettings(timeout_seconds=999)
    adapter = PyrightAdapter(settings=s)
    await adapter.init()
    assert adapter.settings.timeout_seconds == 999


# ---------------------------------------------------------------------------
# build_command
# ---------------------------------------------------------------------------


def test_build_command_no_settings_raises() -> None:
    adapter = PyrightAdapter()
    with pytest.raises(RuntimeError, match="Settings not initialized"):
        adapter.build_command([])


def test_build_command_basic_mode(tmp_path: Path) -> None:
    adapter = PyrightAdapter(settings=PyrightSettings())
    cmd = adapter.build_command([tmp_path / "foo.py"])
    assert cmd[0] == "pyright"
    assert "--outputjson" in cmd
    assert "--skipunannotated" not in cmd
    assert "--level" not in cmd
    assert "--reportUnnecessaryTypeIgnoreComment=warning" in cmd
    assert "--reportMissingTypeStubs=warning" in cmd
    assert str(tmp_path / "foo.py") in cmd


def test_build_command_strict_mode(tmp_path: Path) -> None:
    adapter = PyrightAdapter(settings=PyrightSettings(type_checking_mode="strict"))
    cmd = adapter.build_command([tmp_path / "foo.py"])
    assert "--level" in cmd
    assert cmd[cmd.index("--level") + 1] == "strict"


def test_build_command_off_mode(tmp_path: Path) -> None:
    adapter = PyrightAdapter(settings=PyrightSettings(type_checking_mode="off"))
    cmd = adapter.build_command([tmp_path / "foo.py"])
    assert "--skipunannotated" in cmd


def test_build_command_without_json_output(tmp_path: Path) -> None:
    adapter = PyrightAdapter(settings=PyrightSettings(use_json_output=False))
    cmd = adapter.build_command([tmp_path / "foo.py"])
    assert "--outputjson" not in cmd


def test_build_command_multiple_files(tmp_path: Path) -> None:
    adapter = PyrightAdapter(settings=PyrightSettings())
    files = [tmp_path / "a.py", tmp_path / "b.py"]
    cmd = adapter.build_command(files)
    for f in files:
        assert str(f) in cmd


# ---------------------------------------------------------------------------
# parse_output — JSON branch
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_parse_output_empty_returns_empty() -> None:
    adapter = PyrightAdapter(settings=PyrightSettings())
    result = ToolExecutionResult(raw_output="")
    out = await adapter.parse_output(result)
    assert out == []


@pytest.mark.asyncio
async def test_parse_output_json_single_diagnostic(tmp_path: Path) -> None:
    adapter = PyrightAdapter(settings=PyrightSettings())
    diag = {
        "file": str(tmp_path / "foo.py"),
        "severity": "error",
        "message": "missing type",
        "rule": "reportMissingTypeArgument",
        "range": {"start": {"line": 0, "character": 0}},
    }
    result = ToolExecutionResult(raw_output=json.dumps({"generalDiagnostics": [diag]}))
    out = await adapter.parse_output(result)
    assert len(out) == 1
    issue = out[0]
    assert issue.file_path == tmp_path / "foo.py"
    assert issue.line_number == 1  # 0-indexed → 1-indexed
    assert issue.column_number == 1
    assert issue.message == "missing type"
    assert issue.code == "reportMissingTypeArgument"
    assert issue.severity == "error"


@pytest.mark.asyncio
async def test_parse_output_json_multiple_diagnostics(tmp_path: Path) -> None:
    adapter = PyrightAdapter(settings=PyrightSettings())
    diags = [
        {
            "file": str(tmp_path / "a.py"),
            "severity": "error",
            "message": "msg a",
            "rule": "rule1",
            "range": {"start": {"line": 0, "character": 0}},
        },
        {
            "file": str(tmp_path / "b.py"),
            "severity": "warning",
            "message": "msg b",
            "rule": "rule2",
            "range": {"start": {"line": 4, "character": 2}},
        },
    ]
    result = ToolExecutionResult(raw_output=json.dumps({"generalDiagnostics": diags}))
    out = await adapter.parse_output(result)
    assert len(out) == 2
    assert out[0].file_path == tmp_path / "a.py"
    assert out[1].file_path == tmp_path / "b.py"
    assert out[1].line_number == 5  # 4 → 5
    assert out[1].column_number == 3  # 2 → 3


@pytest.mark.asyncio
async def test_parse_output_json_missing_fields_use_defaults(tmp_path: Path) -> None:
    """Diagnostic with no file/severity/message/rule fields → defaults."""
    adapter = PyrightAdapter(settings=PyrightSettings())
    diag: dict[str, object] = {"range": {"start": {"line": 0, "character": 0}}}
    result = ToolExecutionResult(raw_output=json.dumps({"generalDiagnostics": [diag]}))
    out = await adapter.parse_output(result)
    assert len(out) == 1
    assert out[0].file_path == Path("")
    assert out[0].severity == "error"
    assert out[0].message == ""
    assert out[0].code == ""


@pytest.mark.asyncio
async def test_parse_output_json_invalid_falls_back_to_text() -> None:
    adapter = PyrightAdapter(settings=PyrightSettings())
    result = ToolExecutionResult(raw_output="not valid json")
    out = await adapter.parse_output(result)
    # Falls back to _parse_text_output → empty (no colon-separated entries).
    assert out == []


# ---------------------------------------------------------------------------
# parse_output — text branch (use_json_output=False)
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_parse_output_text_branch_uses_text_parser(tmp_path: Path) -> None:
    adapter = PyrightAdapter(settings=PyrightSettings(use_json_output=False))
    result = ToolExecutionResult(raw_output="")
    out = await adapter.parse_output(result)
    assert out == []


@pytest.mark.asyncio
async def test_parse_output_text_with_real_line() -> None:
    adapter = PyrightAdapter(settings=PyrightSettings(use_json_output=False))
    line = "/tmp/foo.py:10:5 - error: missing arg"
    result = ToolExecutionResult(raw_output=line)
    out = await adapter.parse_output(result)
    assert len(out) == 1


# ---------------------------------------------------------------------------
# _parse_text_output
# ---------------------------------------------------------------------------


def test_parse_text_output_no_colon_lines_ignored() -> None:
    adapter = PyrightAdapter(settings=PyrightSettings())
    out = adapter._parse_text_output("no colons here\nneither here")
    assert out == []


def test_parse_text_output_summary_line_skipped() -> None:
    """Lines mentioning 'error' and 'warning' and ' file(s) ' are summary lines."""
    adapter = PyrightAdapter(settings=PyrightSettings())
    out = adapter._parse_text_output("5 errors, 2 warnings in 3 files")
    assert out == []


def test_parse_text_output_warning_message() -> None:
    adapter = PyrightAdapter(settings=PyrightSettings())
    line = "/tmp/foo.py:1:1 - warning: deprecated"
    result = adapter._parse_text_output(line)
    assert len(result) == 1
    assert result[0].severity == "warning"
    assert result[0].message == "deprecated"


def test_parse_text_output_unknown_message_defaults_error() -> None:
    adapter = PyrightAdapter(settings=PyrightSettings())
    line = "/tmp/foo.py:1:1 - some other issue"
    result = adapter._parse_text_output(line)
    assert len(result) == 1
    assert result[0].severity == "error"


# ---------------------------------------------------------------------------
# _parse_text_line
# ---------------------------------------------------------------------------


# ---------------------------------------------------------------------------
# _parse_text_line
# ---------------------------------------------------------------------------


def test_parse_text_line_no_dash_returns_none() -> None:
    adapter = PyrightAdapter(settings=PyrightSettings())
    assert adapter._parse_text_line("no dash here") is None


def test_parse_text_line_too_few_colons_returns_none() -> None:
    adapter = PyrightAdapter(settings=PyrightSettings())
    assert adapter._parse_text_line("a:1 - error: x") is None  # only 2 colons


def test_parse_text_line_non_numeric_returns_none() -> None:
    """Pre-existing bug: ``except ValueError, IndexError:`` (Python 2 syntax).

    In Python 3 this binds ``IndexError`` as the alias name. ValueError
    is caught, but IndexError is NOT. Per CLAUDE.md Rule 7, preserve
    verbatim — tests document observable behavior.
    """
    adapter = PyrightAdapter(settings=PyrightSettings())
    # When line_number is not parseable as int, the ValueError IS caught.
    assert adapter._parse_text_line("foo.py:notanumber:1 - error: x") is None


def test_parse_text_line_error_severity() -> None:
    """Use absolute path with no special chars to avoid split issues.

    Pre-existing bug: ``location_parts = location_part.split(":")`` does
    NOT strip the column element, so trailing whitespace makes
    ``int(column)`` raise. Tests use a clean input to isolate the
    message parsing.
    """
    adapter = PyrightAdapter(settings=PyrightSettings())
    line = "/tmp/foo.py:10:5 - error: missing import"
    result = adapter._parse_text_line(line)
    assert result is not None
    assert result.line_number == 10
    assert result.column_number == 5
    assert result.severity == "error"
    assert result.message == "missing import"


def test_parse_text_line_warning_severity() -> None:
    adapter = PyrightAdapter(settings=PyrightSettings())
    line = "/tmp/foo.py:1:1 - warning: deprecated"
    result = adapter._parse_text_line(line)
    assert result is not None
    assert result.severity == "warning"
    assert result.message == "deprecated"


def test_parse_text_line_message_part_stripped() -> None:
    """Message after 'error:' / 'warning:' is stripped of prefix."""
    adapter = PyrightAdapter(settings=PyrightSettings())
    line = "/tmp/x.py:1:1 - error: spaces"
    result = adapter._parse_text_line(line)
    assert result is not None
    assert result.message == "spaces"


# ---------------------------------------------------------------------------
# _get_check_type
# ---------------------------------------------------------------------------


def test_get_check_type() -> None:
    adapter = PyrightAdapter(settings=PyrightSettings())
    assert adapter._get_check_type() == QACheckType.TYPE


# ---------------------------------------------------------------------------
# get_default_config
# ---------------------------------------------------------------------------


def test_get_default_config(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    """Without pyproject.toml, package_dir defaults to 'crackerjack'."""
    monkeypatch.setattr("pathlib.Path.cwd", lambda: tmp_path)
    adapter = PyrightAdapter(settings=PyrightSettings())
    config = adapter.get_default_config()
    assert isinstance(config, QACheckConfig)
    assert config.check_type == QACheckType.TYPE
    assert config.check_id == MODULE_ID
    assert config.enabled is False
    assert config.parallel_safe is True
    assert config.timeout_seconds == 180
    assert config.stage == "comprehensive"
    assert "crackerjack/**/*.py" in config.file_patterns


def test_get_default_config_with_pyproject(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    """If pyproject.toml has project.name matching an existing directory → use it."""
    monkeypatch.setattr("pathlib.Path.cwd", lambda: tmp_path)
    pkg_dir = tmp_path / "my_package"
    pkg_dir.mkdir()
    (tmp_path / "pyproject.toml").write_text('[project]\nname = "my-package"\n')
    adapter = PyrightAdapter(settings=PyrightSettings())
    config = adapter.get_default_config()
    assert "my_package/**/*.py" in config.file_patterns


def test_get_default_config_with_pyproject_no_matching_dir(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch,
) -> None:
    """If pyproject.toml has name but no matching directory → fall back to 'crackerjack'."""
    monkeypatch.setattr("pathlib.Path.cwd", lambda: tmp_path)
    (tmp_path / "pyproject.toml").write_text('[project]\nname = "missing-package"\n')
    adapter = PyrightAdapter(settings=PyrightSettings())
    config = adapter.get_default_config()
    assert "crackerjack/**/*.py" in config.file_patterns


def test_get_default_config_pyproject_corrupt(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    """Invalid pyproject.toml → suppress(Exception) catches, falls back."""
    monkeypatch.setattr("pathlib.Path.cwd", lambda: tmp_path)
    (tmp_path / "pyproject.toml").write_text("not valid toml")
    adapter = PyrightAdapter(settings=PyrightSettings())
    config = adapter.get_default_config()
    assert "crackerjack/**/*.py" in config.file_patterns


def test_get_default_config_excludes_test_files() -> None:
    adapter = PyrightAdapter(settings=PyrightSettings())
    config = adapter.get_default_config()
    assert "**/test_*.py" in config.exclude_patterns
    assert "**/tests/**" in config.exclude_patterns
    assert "**/__pycache__/**" in config.exclude_patterns


def test_get_default_config_settings_dict() -> None:
    adapter = PyrightAdapter(settings=PyrightSettings())
    config = adapter.get_default_config()
    assert config.settings["strict_mode"] is False
    assert config.settings["type_checking_mode"] == "basic"
    assert config.settings["use_json_output"] is True


# ---------------------------------------------------------------------------
# ToolIssue dataclass surface (used by adapter)
# ---------------------------------------------------------------------------


def test_tool_issue_to_dict(tmp_path: Path) -> None:
    issue = ToolIssue(
        file_path=tmp_path / "x.py",
        line_number=5,
        column_number=10,
        message="test",
        code="R001",
        severity="error",
    )
    d = issue.to_dict()
    assert d["file_path"] == str(tmp_path / "x.py")
    assert d["line_number"] == 5
    assert d["severity"] == "error"

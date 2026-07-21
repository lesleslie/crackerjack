from __future__ import annotations

import json
from pathlib import Path
from unittest.mock import patch

import pytest
from typer.testing import CliRunner

from crackerjack.cli.docs_cli import app
from crackerjack.services.frontmatter_validator import FrontmatterValidationResult


runner = CliRunner()


def test_docs_validate_clean(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    fake_result = FrontmatterValidationResult(
        success=True,
        files_scanned=10,
        errors=[],
        warnings=[],
        duration_ms=20,
    )
    with patch(
        "crackerjack.cli.docs_cli.FrontmatterValidator",
    ) as mock_cls:
        mock_cls.return_value.validate.return_value = fake_result
        result = runner.invoke(
            app, ["validate", "--path", str(tmp_path)],
        )
    assert result.exit_code == 0
    assert "10 files scanned" in result.stdout or "10" in result.stdout


def test_docs_validate_strict_returns_1(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    from crackerjack.services.frontmatter_validator import (
        FrontmatterValidationError,
        FrontmatterValidationResult,
        FrontmatterValidationIssue,
    )
    err_result = FrontmatterValidationResult(
        success=False,
        files_scanned=10,
        errors=[FrontmatterValidationIssue(
            file="x.md", line=1, code="missing", message="bad"
        )],
        warnings=[],
        duration_ms=5,
        error_count=1,
    )
    with patch(
        "crackerjack.cli.docs_cli.FrontmatterValidator",
    ) as mock_cls:
        mock_cls.return_value.validate_or_raise.side_effect = FrontmatterValidationError(
            "1 error", result=err_result, reason="errors"
        )
        result = runner.invoke(
            app, ["validate", "--strict", "--path", str(tmp_path)],
        )
    assert result.exit_code == 1


def test_docs_validate_json_output(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    fake_result = FrontmatterValidationResult(
        success=True, files_scanned=2, errors=[], warnings=[], duration_ms=10
    )
    with patch(
        "crackerjack.cli.docs_cli.FrontmatterValidator",
    ) as mock_cls:
        mock_cls.return_value.validate.return_value = fake_result
        result = runner.invoke(
            app, ["validate", "--json", "--path", str(tmp_path)],
        )
    assert result.exit_code == 0
    payload = json.loads(result.stdout)
    assert payload["files_scanned"] == 2
    assert payload["success"] is True

from __future__ import annotations

import json
from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest

from crackerjack.services.frontmatter_validator import (
    FrontmatterValidationError,
    FrontmatterValidationResult,
    FrontmatterValidator,
)


def _fake_completed_process(stdout: str, returncode: int = 0) -> MagicMock:
    m = MagicMock()
    m.returncode = returncode
    m.stdout = stdout
    m.stderr = ""
    return m


def test_validate_parses_clean_json() -> None:
    payload = json.dumps(
        {
            "files_scanned": 14,
            "errors": [],
            "warnings": [],
            "duration_ms": 123,
        }
    )
    with patch(
        "crackerjack.services.frontmatter_validator.secure_subprocess.run",
        return_value=_fake_completed_process(payload, returncode=0),
    ):
        v = FrontmatterValidator(pkg_path=Path("/tmp/repo"))
        result = v.validate()
    assert isinstance(result, FrontmatterValidationResult)
    assert result.success is True
    assert result.files_scanned == 14
    assert result.error_count == 0
    assert result.warning_count == 0


def test_validate_raises_on_errors() -> None:
    payload = json.dumps(
        {
            "files_scanned": 14,
            "errors": [
                {
                    "file": "docs/x.md",
                    "line": 1,
                    "code": "missing_status",
                    "message": "missing status",
                }
            ],
            "warnings": [],
            "duration_ms": 50,
        }
    )
    with patch(
        "crackerjack.services.frontmatter_validator.secure_subprocess.run",
        return_value=_fake_completed_process(payload, returncode=1),
    ):
        v = FrontmatterValidator(pkg_path=Path("/tmp/repo"))
        with pytest.raises(FrontmatterValidationError) as exc_info:
            v.validate_or_raise()
    assert exc_info.value.result.error_count == 1
    assert exc_info.value.result.errors[0]["code"] == "missing_status"


def test_validate_timeout_raises() -> None:
    with patch(
        "crackerjack.services.frontmatter_validator.secure_subprocess.run",
        side_effect=TimeoutError(),
    ):
        v = FrontmatterValidator(pkg_path=Path("/tmp/repo"), timeout_seconds=5)
        with pytest.raises(FrontmatterValidationError) as exc_info:
            v.validate()
    assert exc_info.value.reason == "timeout"
    assert exc_info.value.result is None


def test_validate_passes_store_flag() -> None:
    payload = json.dumps(
        {"files_scanned": 0, "errors": [], "warnings": [], "duration_ms": 1}
    )
    with patch(
        "crackerjack.services.frontmatter_validator.secure_subprocess.run",
        return_value=_fake_completed_process(payload),
    ) as mock_run:
        v = FrontmatterValidator(pkg_path=Path("/tmp/repo"))
        v.validate(store="docs/plans/")
    cmd = mock_run.call_args[0][0]
    assert "--store" in cmd
    assert "docs/plans/" in cmd

from __future__ import annotations

from pathlib import Path
from unittest.mock import patch, MagicMock

import pytest

from crackerjack.core.phase_coordinator import PhaseCoordinator
from crackerjack.services.frontmatter_validator import (
    FrontmatterValidationResult,
    FrontmatterValidationIssue,
)


@pytest.fixture
def coordinator(tmp_path: Path) -> PhaseCoordinator:
    pc = PhaseCoordinator.__new__(PhaseCoordinator)
    pc.console = MagicMock()
    pc.pkg_path = tmp_path
    pc.git_service = MagicMock()
    pc._settings = MagicMock()
    pc.session = MagicMock()
    return pc


class _Options:
    cleanup_docs = True
    docs_dry_run = True


def test_run_documentation_cleanup_phase_fails_on_validator_errors(
    coordinator: PhaseCoordinator,
) -> None:
    bad = FrontmatterValidationResult(
        success=False, files_scanned=5,
        errors=[FrontmatterValidationIssue(file="x.md", line=1, code="missing", message="bad")],
        warnings=[], duration_ms=1, error_count=1,
    )
    with patch(
        "crackerjack.core.phase_coordinator.FrontmatterValidator"
    ) as mock_v:
        mock_v.return_value.validate.return_value = bad
        with patch(
            "crackerjack.core.phase_coordinator.DocumentationCleanup"
        ) as mock_dc:
            mock_dc.return_value.cleanup_documentation.return_value = MagicMock(success=True)
            result = coordinator.run_documentation_cleanup_phase(_Options())
    assert result is False
    coordinator.session.fail_task.assert_called_once()


def test_run_documentation_cleanup_phase_proceeds_when_validator_clean(
    coordinator: PhaseCoordinator,
) -> None:
    ok = FrontmatterValidationResult(
        success=True, files_scanned=5, errors=[], warnings=[], duration_ms=1
    )
    with patch(
        "crackerjack.core.phase_coordinator.FrontmatterValidator"
    ) as mock_v:
        mock_v.return_value.validate.return_value = ok
        with patch(
            "crackerjack.core.phase_coordinator.DocumentationCleanup"
        ) as mock_dc:
            mock_dc.return_value.cleanup_documentation.return_value = MagicMock(success=True)
            result = coordinator.run_documentation_cleanup_phase(_Options())
    assert result is True
    mock_dc.return_value.cleanup_documentation.assert_called_once()

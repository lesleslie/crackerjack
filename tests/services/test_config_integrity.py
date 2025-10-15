from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest
from acb.console import Console

from crackerjack.exceptions.config import ConfigIntegrityError
from crackerjack.services.config_integrity import ConfigIntegrityService


@pytest.fixture
def mock_console() -> MagicMock:
    return MagicMock(spec=Console)


@pytest.fixture
def config_integrity_service(tmp_path: Path, mock_console: MagicMock) -> ConfigIntegrityService:
    # Ensure the cache directory is within tmp_path for isolated testing
    with patch("pathlib.Path.home", return_value=tmp_path):
        # Disable ACB dependency injection for testing by calling __init__ directly
        service = object.__new__(ConfigIntegrityService)
        service.console = mock_console
        service.project_path = tmp_path
        service.cache_dir = tmp_path / ".cache" / "crackerjack"
        service.cache_dir.mkdir(parents=True, exist_ok=True)
        return service


class TestConfigIntegrityService:
    def test_check_config_integrity_no_drift(self, config_integrity_service: ConfigIntegrityService, tmp_path: Path) -> None:
        pyproject_toml = tmp_path / "pyproject.toml"
        pyproject_toml.write_text("[tool.ruff]\n[tool.pyright]\n[tool.pytest.ini_options]")

        # Mock _has_required_config_sections to return True
        with patch.object(config_integrity_service, "_has_required_config_sections", return_value=True):
            drift_detected = config_integrity_service.check_config_integrity()
            assert drift_detected is False

    def test_check_config_integrity_drift_detected(self, config_integrity_service: ConfigIntegrityService, tmp_path: Path) -> None:
        pyproject_toml = tmp_path / "pyproject.toml"
        pyproject_toml.write_text("[tool.ruff]\n[tool.pyright]\n[tool.pytest.ini_options]")

        # Simulate drift by writing a different hash to cache
        cache_file = config_integrity_service.cache_dir / "pyproject.toml.hash"
        cache_file.write_text("12345")

        with patch.object(config_integrity_service, "_has_required_config_sections", return_value=True):
            drift_detected = config_integrity_service.check_config_integrity()
            assert drift_detected is True
            config_integrity_service.console.print.assert_called_with(
                f"[yellow]⚠️ {pyproject_toml.name} has been modified manually[/ yellow]"
            )

    def test_check_config_integrity_missing_sections(self, config_integrity_service: ConfigIntegrityService, tmp_path: Path) -> None:
        pyproject_toml = tmp_path / "pyproject.toml"
        pyproject_toml.write_text("[tool.ruff]") # Missing other sections

        drift_detected = config_integrity_service.check_config_integrity()
        assert drift_detected is True
        config_integrity_service.console.print.assert_called_with(
            f"[red]❌ Configuration integrity error: Missing required config section: tool.pyright in pyproject.toml[/ red]"
        )

    def test_check_file_drift_no_drift(self, config_integrity_service: ConfigIntegrityService, tmp_path: Path) -> None:
        file_path = tmp_path / "test_file.txt"
        file_path.write_text("content")

        drift = config_integrity_service._check_file_drift(file_path)
        assert drift is False

        # Check again to ensure cache is used and no drift
        drift = config_integrity_service._check_file_drift(file_path)
        assert drift is False

    def test_check_file_drift_with_drift(self, config_integrity_service: ConfigIntegrityService, tmp_path: Path) -> None:
        file_path = tmp_path / "test_file.txt"
        file_path.write_text("initial content")

        # First check to populate cache
        config_integrity_service._check_file_drift(file_path)

        # Modify content to simulate drift
        file_path.write_text("modified content")

        drift = config_integrity_service._check_file_drift(file_path)
        assert drift is True
        config_integrity_service.console.print.assert_called_with(
            f"[yellow]⚠️ {file_path.name} has been modified manually[/ yellow]"
        )

    def test_check_file_drift_os_error(self, config_integrity_service: ConfigIntegrityService, tmp_path: Path) -> None:
        file_path = tmp_path / "non_existent_file.txt"

        with pytest.raises(ConfigIntegrityError, match="Failed to check file drift"):
            config_integrity_service._check_file_drift(file_path)

    def test_has_required_config_sections_success(self, config_integrity_service: ConfigIntegrityService, tmp_path: Path) -> None:
        pyproject_toml = tmp_path / "pyproject.toml"
        pyproject_toml.write_text("[tool.ruff]\n[tool.pyright]\n[tool.pytest.ini_options]")

        assert config_integrity_service._has_required_config_sections() is True

    def test_has_required_config_sections_missing_file(self, config_integrity_service: ConfigIntegrityService, tmp_path: Path) -> None:
        with pytest.raises(ConfigIntegrityError, match="pyproject.toml not found."):
            config_integrity_service._has_required_config_sections()

    def test_has_required_config_sections_missing_section(self, config_integrity_service: ConfigIntegrityService, tmp_path: Path) -> None:
        pyproject_toml = tmp_path / "pyproject.toml"
        pyproject_toml.write_text("[tool.ruff]\n[tool.pyright]") # Missing tool.pytest.ini_options

        with pytest.raises(ConfigIntegrityError, match="Missing required config section: tool.pytest.ini_options in pyproject.toml"):
            config_integrity_service._has_required_config_sections()

    def test_has_required_config_sections_parsing_error(self, config_integrity_service: ConfigIntegrityService, tmp_path: Path) -> None:
        pyproject_toml = tmp_path / "pyproject.toml"
        pyproject_toml.write_text("invalid toml content")

        with pytest.raises(ConfigIntegrityError, match="Error parsing pyproject.toml"):
            config_integrity_service._has_required_config_sections()
